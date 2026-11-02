import { request } from '@/utils/http'
import type { SessionData } from './types'

/** 登录会话条目（用于「登录设备」列表）。 */
export interface SessionItem {
  id: string
  client_type: string
  created_at: string
  last_seen_at?: string
  is_current?: boolean
}

export function webLogin(username: string, password: string): Promise<SessionData> {
  return request<SessionData>({
    url: '/auth/web-login',
    method: 'POST',
    data: { username, password },
  })
}

export function register(username: string, password: string): Promise<SessionData> {
  return request<SessionData>({
    url: '/auth/register',
    method: 'POST',
    data: { username, password },
  })
}

export function logout(): Promise<unknown> {
  return request<unknown>({ url: '/auth/logout', method: 'POST', data: {} })
}

export function getSessions(): Promise<{ items: SessionItem[] }> {
  return request<{ items: SessionItem[] }>({ url: '/auth/sessions' })
}

export function revokeSession(id: string): Promise<unknown> {
  return request<unknown>({
    url: `/auth/sessions/${encodeURIComponent(id)}`,
    method: 'DELETE',
  })
}

export function revokeAllSessions(): Promise<unknown> {
  return request<unknown>({ url: '/auth/sessions/revoke-all', method: 'POST', data: {} })
}

/** 为已有账号设置网页登录密码。 */
export function setLoginPassword(username: string, password: string): Promise<unknown> {
  return request<unknown>({
    url: '/auth/password',
    method: 'POST',
    data: { username, password },
  })
}

export function createRecoveryCodes(): Promise<{ codes: string[] }> {
  return request<{ codes: string[] }>({ url: '/auth/recovery-codes', method: 'POST', data: {} })
}

export function recoverPassword(
  username: string,
  recoveryCode: string,
  newPassword: string,
): Promise<unknown> {
  return request<unknown>({
    url: '/auth/recover',
    method: 'POST',
    data: { username, recovery_code: recoveryCode, new_password: newPassword },
  })
}
