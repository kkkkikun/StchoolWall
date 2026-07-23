// H5 走 vite 代理（相对 /api/v1，由 vite.config 的 proxy 转发到后端），
// 避免浏览器直连后端时的跨域与 WSL 下 Windows 访问 127.0.0.1:8000 不可达问题；
// 小程序/App 直连绝对地址（无 vite 代理可用）。
let DEFAULT_BASE = 'http://127.0.0.1:8000/api/v1'
// #ifdef H5
DEFAULT_BASE = '/api/v1'
// #endif
const BASE_URL = import.meta.env.VITE_API_BASE_URL || DEFAULT_BASE

/** 标准 API 响应格式 */
interface ApiResponse<T = unknown> {
  code: number
  message?: string
  data: T
}

interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: Record<string, unknown> | object
  header?: Record<string, string>
}

function getToken(): string {
  return uni.getStorageSync('access_token') || ''
}

/** 核心请求方法 */
async function request<T = unknown>(options: RequestOptions): Promise<ApiResponse<T>> {
  const token = getToken()
  const header: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.header,
  }
  if (token) {
    header['Authorization'] = `Bearer ${token}`
  }

  // GET 查询参数过滤 undefined/null/空串，避免生成 cursor= 这样的无效参数触发后端 422
  let data = options.data
  const method = options.method || 'GET'
  if (method === 'GET' && data) {
    data = Object.fromEntries(
      Object.entries(data).filter(([, v]) => v !== undefined && v !== null && v !== '')
    )
  }

  return new Promise((resolve, reject) => {
    uni.request({
      url: `${BASE_URL}${options.url}`,
      method,
      data,
      header,
      success: (res) => {
        if (res.statusCode === 401) {
          uni.removeStorageSync('access_token')
          uni.removeStorageSync('user_info')
          reject(new Error('未登录或 Token 已失效'))
          return
        }
        if (res.statusCode >= 400) {
          reject(new Error((res.data as ApiResponse).message || '请求失败'))
          return
        }
        resolve(res.data as ApiResponse<T>)
      },
      fail: (err) => {
        reject(new Error(err.errMsg || '网络请求失败'))
      },
    })
  })
}

/** GET 请求 */
export function get<T = unknown>(url: string, data?: Record<string, unknown> | object): Promise<T> {
  return request<T>({
    url,
    method: 'GET',
    data,
  }).then((res) => res.data)
}

/** POST 请求 */
export function post<T = unknown>(url: string, data?: Record<string, unknown> | object): Promise<T> {
  return request<T>({
    url,
    method: 'POST',
    data,
  }).then((res) => res.data)
}

/** PUT 请求 */
export function put<T = unknown>(url: string, data?: Record<string, unknown> | object): Promise<T> {
  return request<T>({
    url,
    method: 'PUT',
    data,
  }).then((res) => res.data)
}

/** DELETE 请求 */
export function del<T = unknown>(url: string, data?: Record<string, unknown> | object): Promise<T> {
  return request<T>({
    url,
    method: 'DELETE',
    data,
  }).then((res) => res.data)
}

export { request }
