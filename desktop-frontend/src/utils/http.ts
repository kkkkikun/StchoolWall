/**
 * HTTP 封装。
 *
 * 与移动端 (frontend/src/utils/request.ts) 的关键差异与原因：
 * 1. 访问令牌只放内存，不写 localStorage —— 仓库规范要求令牌不持久化；
 * 2. 刷新通道随部署形态切换：
 *    - HTTPS 页面（window.isSecureContext）用客户端类型 web，刷新令牌由服务端
 *      下发的 HttpOnly cookie 持有，刷新请求带 X-CSRF-Token；
 *    - 纯 HTTP 页面里该 cookie 带 Secure 会被浏览器丢弃，退回客户端类型 native，
 *      由响应体带回 refresh_token，刷新时放进请求体。
 *    上线 HTTPS 后自动走 web 通道，无需改代码。
 * 3. 401 时单飞刷新并重放原请求，避免并发请求同时刷新把刷新令牌用废
 *    （刷新令牌一次性轮换，重放会撤销该用户全部会话）。
 */
import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

import type { ApiEnvelope } from '@/api/types'

// import.meta.env 是 Vite 注入的，模块在 Node 下被测试加载时不存在，取值要容错
const viteEnv = (import.meta as unknown as { env?: Record<string, string | undefined> }).env ?? {}

export const API_BASE = viteEnv.VITE_API_BASE_URL || '/api/v1'
export const REQUEST_TIMEOUT = 30000
export const REFRESH_TOKEN_KEY = 'sw_refresh_token'

export const CLIENT_TYPE: 'web' | 'native' =
  typeof window !== 'undefined' && window.isSecureContext ? 'web' : 'native'

/** 业务失败或 HTTP 失败都归一成这个错误，页面只需读 message。 */
export class ApiError extends Error {
  readonly status: number
  readonly code: number

  constructor(message: string, status: number, code: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

let accessToken: string | null = null
let csrfToken: string | null = null
let refreshToken: string | null = localStorage.getItem(REFRESH_TOKEN_KEY)
let refreshing: Promise<boolean> | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function setCsrfToken(token: string | null): void {
  csrfToken = token
}

export function setRefreshToken(token: string | null): void {
  refreshToken = token
  if (token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, token)
  } else {
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  }
}

export function hasRefreshCredential(): boolean {
  return CLIENT_TYPE === 'web' || !!refreshToken
}

function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)sw_csrf=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'X-Client-Type': CLIENT_TYPE }
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`
  }
  const csrf = csrfToken ?? readCsrfCookie()
  if (csrf) {
    headers['X-CSRF-Token'] = csrf
  }
  return headers
}

function errorMessage(body: unknown, fallback: string): string {
  const data = body as { detail?: unknown; message?: string } | null
  const detail = data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as { message: unknown }).message)
  }
  return data?.message || fallback
}

export const http: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: REQUEST_TIMEOUT,
  withCredentials: true,
})

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  config.headers.set(authHeaders())
  return config
})

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean
}

interface RefreshPayload {
  access_token: string
  refresh_token?: string
  csrf_token?: string
  role?: string
  user_info?: { id: string; nickname: string; is_verified: boolean }
}

async function performRefresh(): Promise<RefreshPayload> {
  if (!hasRefreshCredential()) throw new ApiError('请重新登录', 401, 0)
  const body = CLIENT_TYPE === 'native' && refreshToken ? { refresh_token: refreshToken } : {}
  const response = await http.post<ApiEnvelope<RefreshPayload>>('/auth/refresh', body)
  const data = response.data.data
  setAccessToken(data.access_token)
  if (data.refresh_token) setRefreshToken(data.refresh_token)
  if (data.csrf_token) setCsrfToken(data.csrf_token)
  return data
}

/**
 * 恢复会话：刷新页面后用刷新通道换回访问令牌。
 * 成功返回新的会话信息，失败返回 null（调用方按未登录处理）。
 */
export async function restoreSession(): Promise<RefreshPayload | null> {
  try {
    return await performRefresh()
  } catch {
    return null
  }
}

function ensureRefresh(): Promise<boolean> {
  if (!refreshing) {
    refreshing = performRefresh()
      .then(() => true)
      .catch(() => false)
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}

http.interceptors.response.use(
  (response) => {
    const envelope = response.data as ApiEnvelope<unknown>
    if (envelope && typeof envelope.code === 'number' && envelope.code !== 0) {
      throw new ApiError(errorMessage(envelope, '请求失败'), response.status, envelope.code)
    }
    return response
  },
  async (error: unknown) => {
    const axiosError = error as {
      response?: { status: number; data?: unknown }
      config?: RetriableConfig
    }
    const status = axiosError.response?.status ?? 0
    const config = axiosError.config
    if (status === 401 && config && !config._retried) {
      config._retried = true
      const refreshed = await ensureRefresh().catch(() => false)
      if (refreshed) {
        return http.request(config)
      }
    }
    const message = errorMessage(axiosError.response?.data, '网络请求失败')
    throw new ApiError(message, status, 0)
  },
)

/** 统一取 data 字段：后端所有端点都包在 {code,data} 里。 */
export async function request<T>(config: {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: unknown
  params?: object
}): Promise<T> {
  const response = await http.request<ApiEnvelope<T>>({
    url: config.url,
    method: config.method ?? 'GET',
    data: config.data,
    params: cleanParams(config.params as Record<string, unknown> | undefined),
  })
  return response.data.data
}

/** 查询串里去掉 undefined / null / 空串，避免把无效参数发给后端。 */
function cleanParams(params?: Record<string, unknown>): Record<string, unknown> | undefined {
  if (!params) return undefined
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')
  return entries.length ? Object.fromEntries(entries) : undefined
}
