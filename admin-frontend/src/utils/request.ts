/** axios 封装：Bearer token 注入 / 401 跳登录 / 统一错误提示。 */
import axios from 'axios'
import { ElMessage } from 'element-plus'

const TOKEN_KEY = 'sw_admin_token'

// 管理台可能部署在 /admin/ 子路径：401 跳登录需带 base，否则生产环境会 404
const LOGIN_PATH = import.meta.env.BASE_URL.endsWith('/')
  ? `${import.meta.env.BASE_URL}login`
  : `${import.meta.env.BASE_URL}/login`

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

request.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
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
