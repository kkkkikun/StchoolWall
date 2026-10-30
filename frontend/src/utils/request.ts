import { tokenStorage, userStorage, syncWebSession, type SessionData } from './storage'
import { clientType } from './platform-auth'
import { withWebRefreshLock } from './web-session-sync'

let DEFAULT_BASE = 'http://127.0.0.1:8000/api/v1'
// #ifdef H5
DEFAULT_BASE = '/api/v1'
// #endif
export const BASE_URL = import.meta.env.VITE_API_BASE_URL || DEFAULT_BASE

interface ApiResponse<T = unknown> { code: number; message?: string; data: T }
interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: Record<string, unknown> | object
  header?: Record<string, string>
  skipRefresh?: boolean
}
class HttpError extends Error {
  constructor(message: string, public status: number) { super(message) }
}
function errorMessage(data: any): string {
  const detail = data?.detail
  return data?.message || (typeof detail === 'string' ? detail : detail?.message) || '请求失败'
}
export function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'X-Client-Type': clientType() }
  const token = tokenStorage.getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const csrf = tokenStorage.getCsrfToken()
  if (csrf) headers['X-CSRF-Token'] = csrf
  return headers
}
function send<T>(options: RequestOptions): Promise<ApiResponse<T>> {
  let data = options.data
  if ((!options.method || options.method === 'GET') && data) {
    data = Object.fromEntries(Object.entries(data).filter(([, value]) =>
      value !== undefined && value !== null && value !== ''))
  }
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${BASE_URL}${options.url}`,
      method: options.method || 'GET', data,
      header: { 'Content-Type': 'application/json', ...authHeaders(), ...options.header },
      withCredentials: clientType() === 'web',
      success: (res) => {
        const body = res.data as ApiResponse<T>
        if (res.statusCode >= 400) return reject(new HttpError(errorMessage(body), res.statusCode))
        if (body.code !== 0) return reject(new Error(errorMessage(body)))
        resolve(body)
      },
      fail: (err) => reject(new Error(err.errMsg || '网络请求失败')),
    })
  })
}

let lastAuthToastTime = 0
export function notifyAuthRequired(msg = '登录会话已过期，请重新登录'): void {
  const now = Date.now()
  if (now - lastAuthToastTime > 4000) {
    lastAuthToastTime = now
    try { uni.showToast({ title: msg, icon: 'none' }) } catch {}
  }
}

let silentLoginPromise: Promise<boolean> | null = null
async function trySilentMpLogin(): Promise<boolean> {
  if (clientType() !== 'weixin') return false
  if (silentLoginPromise) return silentLoginPromise

  silentLoginPromise = (async () => {
    try {
      const code = await new Promise<string>((resolve, reject) => {
        uni.login({
          success: (r) => (r.code ? resolve(r.code) : reject(new Error('无登录 code'))),
          fail: (e) => reject(e),
        })
      })
      const res = await send<SessionData>({
        url: '/auth/login',
        method: 'POST',
        data: { code },
        skipRefresh: true,
      })
      if (res.data && res.data.access_token) {
        tokenStorage.setSession(res.data)
        return true
      }
      return false
    } catch {
      return false
    } finally {
      silentLoginPromise = null
    }
  })()

  return silentLoginPromise
}

let refreshing: Promise<void> | null = null
export function refreshSession(staleToken = tokenStorage.getToken()): Promise<void> {
  if (refreshing) return refreshing
  const refresh = async () => {
    if (clientType() === 'web') {
      await syncWebSession()
      if (tokenStorage.getToken() && tokenStorage.getToken() !== staleToken) return
    }
    const refreshToken = tokenStorage.getRefreshToken()
    if (clientType() !== 'web' && !refreshToken) throw new HttpError('请重新登录', 401)
    const result = await send<SessionData>({
      url: '/auth/refresh', method: 'POST',
      data: refreshToken ? { refresh_token: refreshToken } : {},
    })
    try { tokenStorage.setSession(result.data) }
    catch (error) { userStorage.clear(); tokenStorage.removeToken(); throw error }
  }
  const locks = typeof navigator !== 'undefined' ? (navigator as any).locks : null
  const pending: Promise<void> = (clientType() === 'web'
    ? withWebRefreshLock(locks, refresh)
    : refresh()).catch((error: unknown) => {
    if (error instanceof HttpError && (error.status === 401 || error.status === 403)) {
      userStorage.clear()
      tokenStorage.removeToken()
    }
    throw error
  }).finally(() => { refreshing = null })
  refreshing = pending
  return pending
}

export async function request<T = unknown>(options: RequestOptions): Promise<ApiResponse<T>> {
  const publicAuth = /^\/auth\/(login|web-login|mp-login|dev-login|register|recover|refresh)$/.test(options.url.split('?')[0])
  if (!publicAuth && !options.skipRefresh && !tokenStorage.getToken() && tokenStorage.isLoggedIn()) {
    try { await refreshSession() } catch {}
  }
  const sentToken = tokenStorage.getToken()
  try { return await send<T>(options) }
  catch (error) {
    if (!(error instanceof HttpError) || error.status !== 401 || options.skipRefresh || publicAuth) throw error
    try {
      await refreshSession(sentToken)
      return await send<T>(options)
    } catch (refreshErr) {
      if (clientType() === 'weixin') {
        const ok = await trySilentMpLogin()
        if (ok) return await send<T>(options)
      }
      tokenStorage.removeToken()
      userStorage.clear()
      try { uni.$emit('auth:expired') } catch {}
      notifyAuthRequired('登录会话已失效，请重新登录')
      throw refreshErr
    }
  }
}
export function get<T = unknown>(url: string, data?: object): Promise<T> {
  return request<T>({ url, data }).then((res) => res.data)
}
export function post<T = unknown>(url: string, data?: object): Promise<T> {
  return request<T>({ url, method: 'POST', data }).then((res) => res.data)
}
export function put<T = unknown>(url: string, data?: object): Promise<T> {
  return request<T>({ url, method: 'PUT', data }).then((res) => res.data)
}
export function del<T = unknown>(url: string, data?: object): Promise<T> {
  return request<T>({ url, method: 'DELETE', data }).then((res) => res.data)
}

export interface UploadedMedia {
  media_id: string
  status: 'quarantine' | 'approved' | 'rejected'
  public_url: string | null
}
export async function uploadMultipart<T>(
  path: string, filePath: string, formData: Record<string, string> = {}, retry = true,
): Promise<T> {
  if (!tokenStorage.getToken() && tokenStorage.isLoggedIn()) await refreshSession()
  const sentToken = tokenStorage.getToken()
  const result = await new Promise<{ status: number; data: any }>((resolve, reject) => {
    uni.uploadFile({
      url: `${BASE_URL}${path}`, filePath, name: 'file', formData,
      header: authHeaders(),
      success: (res) => {
        try { resolve({ status: res.statusCode, data: JSON.parse(res.data) }) }
        catch { reject(new Error('上传响应解析失败')) }
      },
      fail: (err) => reject(new Error(err.errMsg || '上传失败')),
    })
  })
  if (result.status === 401 && retry) {
    try {
      await refreshSession(sentToken)
      return await uploadMultipart<T>(path, filePath, formData, false)
    } catch (err) {
      if (clientType() === 'weixin') {
        const ok = await trySilentMpLogin()
        if (ok) return await uploadMultipart<T>(path, filePath, formData, false)
      }
      tokenStorage.removeToken()
      userStorage.clear()
      try { uni.$emit('auth:expired') } catch {}
      notifyAuthRequired('登录会话已失效，请重新登录')
      throw err
    }
  }
  if (result.status >= 400 || result.data.code !== 0) {
    throw new Error(errorMessage(result.data))
  }
  return result.data.data as T
}
export function uploadMedia(filePath: string, kind: string): Promise<UploadedMedia> {
  return uploadMultipart<UploadedMedia>(`/upload/direct?kind=${encodeURIComponent(kind)}`, filePath)
}
/** Legacy consumers may display an image only after review has approved its public derivative. */
export async function uploadFile(filePath: string, kind: string): Promise<string> {
  const media = await uploadMedia(filePath, kind)
  if (media.status === 'approved' && media.public_url) return media.public_url
  throw new Error('图片已上传，正在审核，请稍后再试')
}
