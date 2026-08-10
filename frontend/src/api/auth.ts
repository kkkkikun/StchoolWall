import type { LoginResponse, UserInfo } from '@/types/api'
import { post } from '@/utils/request'
import { tokenStorage, userStorage } from '@/utils/storage'

/** 微信登录（小程序 wx.login 换 code 后调用） */
export function login(code: string) {
  return post<LoginResponse>('/auth/login', { code })
}

/** 学籍认证 */
export function verifyStudent(studentId: string, password: string) {
  return post<{ user_info: UserInfo }>('/auth/verify', {
    student_id: studentId,
    password,
  })
}

/**
 * 开发环境一键登录（演示学生）。
 * 仅后端 ENVIRONMENT=development 暴露；用于 H5 预览联调，绕过 wx.login。
 */
export function devLogin() {
  return post<LoginResponse>('/auth/dev-login', {})
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

