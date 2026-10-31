/** axios 封装：Bearer token 注入 / 401 跳登录 / 统一错误提示。 */
import axios from 'axios'
// ElMessage 由 unplugin-auto-import 按需注入（含样式），此处不显式 import

const TOKEN_KEY = 'sw_admin_token'
let accessToken = ''
localStorage.removeItem(TOKEN_KEY)
const csrf = () => document.cookie.split('; ').find(v => v.startsWith('sw_admin_csrf='))?.split('=')[1] || ''

// 管理台可能部署在 /admin/ 子路径：401 跳登录需带 base，否则生产环境会 404
const base = import.meta.env?.BASE_URL || '/'
const LOGIN_PATH = base.endsWith('/') ? `${base}login` : `${base}/login`

export function getToken(): string {
  return accessToken || (csrf() ? '__cookie_session__' : '')
}

export function setToken(token: string) {
  accessToken = token
}

export function clearToken() {
  accessToken = ''
  localStorage.removeItem(TOKEN_KEY)
  document.cookie = 'sw_admin_csrf=; Max-Age=0; Path=/'
}

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  withCredentials: true,
})

request.interceptors.request.use((config) => {
  const token = getToken()
  if (token && token !== '__cookie_session__') config.headers.Authorization = `Bearer ${token}`
  if (csrf()) config.headers['X-CSRF-Token'] = csrf()
  return config
})

request.interceptors.response.use(
  (resp) => {
    // 后端统一 {code, message, data}；code !== 0 视为业务失败
    const body = resp.data
    if (body && typeof body === 'object' && 'code' in body && body.code !== 0) {
      const msg = body.message || '操作失败'
      ElMessage.error(msg)
      return Promise.reject(new Error(msg))
    }
    return body?.data !== undefined ? body.data : body
  },
  (err) => {
    const status = err.response?.status
    const detail = err.response?.data?.detail
    if (status === 401) {
      clearToken()
      // 避免登录页自身 401 造成循环；跟随 BASE_URL 支持 /admin/ 子路径部署
      if (!location.pathname.startsWith(LOGIN_PATH)) {
        ElMessage.error('登录已失效，请重新登录')
        window.location.assign(LOGIN_PATH)
      }
    } else {
      ElMessage.error(typeof detail === 'string' ? detail : err.message || '请求失败')
    }
    return Promise.reject(err)
  },
)

export default request
