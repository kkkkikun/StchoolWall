import type { LoginResponse, UserInfo } from '@/types/api'
import { post } from '@/utils/request'
import { tokenStorage, userStorage } from '@/utils/storage'

/** 微信登录（小程序 wx.login 换 code 后调用） */
export function login(code: string) {
  return post<LoginResponse>('/auth/login', { code })
}

/** 学籍认证 */
export function verifyStudent(studentId: string, password: string) {
  return post<LoginResponse>('/auth/verify', {
    student_id: studentId,
    password,
  })
}

/**
 * 开发环境一键登录（演示身份）。
 * 仅后端 ENVIRONMENT=development 暴露；用于 H5 预览联调，绕过 wx.login。
 * asAdmin=true 登演示管理员（管理后台联调用）。
 */
export function devLogin(asAdmin = false) {
  return post<LoginResponse>(`/auth/dev-login?as_admin=${asAdmin}`, {})
}

/**
 * 网页版登录（账号不存在即注册，昵称即用户名）。
 * H5 部署用；与微信登录共存（openid 命名空间 web:*）。
 */
export function webLogin(username: string, password: string) {
  return post<LoginResponse>('/auth/web-login', { username, password })
}

/**
 * 公众号网页授权登录（H5 经公众号入口）：OAuth 回调 code → 后端 /auth/mp-login。
 */
export function mpLogin(code: string) {
  return post<LoginResponse>('/auth/mp-login', { code })
}

/**
 * 微信小程序：静默登录（uni.login 换 code → 后端 /auth/login 换 token → 落地存储）。
 * 真机/小程序环境用；H5 预览请用 devLogin。
 * 返回是否登录成功（失败不应阻塞应用启动，按游客态继续）。
 */
export async function wxLoginAndStore(): Promise<boolean> {
  try {
    const res = await uni.login()
    const code = (res as { code?: string }).code
    if (!code) return false
    const data = await login(code)
    tokenStorage.setToken(data.access_token)
    userStorage.setUserInfo({
      id: data.user_info.id,
      nickname: data.user_info.nickname,
      role: data.role,
      is_verified: data.user_info.is_verified,
    })
    return true
  } catch (e) {
    console.warn('wx login failed', e)
    return false
  }
}

