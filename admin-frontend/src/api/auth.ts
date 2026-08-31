/** 认证 API。 */
import request from '@/utils/request'

export interface LoginResult {
  access_token: string
  admin: { id: string; username: string; nickname: string }
}

export function login(username: string, password: string) {
  return request.post<any, LoginResult>('/admin/auth/login', { username, password })
}

export function changePassword(oldPassword: string, newPassword: string) {
  return request.put('/admin/auth/password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}
