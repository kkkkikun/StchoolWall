import type { LoginResponse, UserInfo } from '@/types/api'
import { post } from '@/utils/request'

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

