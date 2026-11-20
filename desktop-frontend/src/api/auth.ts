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

/** 修改网页登录密码（需校验原密码）。修改成功后后端会撤销全部会话。 */
export function changePassword(oldPassword: string, newPassword: string): Promise<unknown> {
  return request<unknown>({
    url: '/user/password',
    method: 'PUT',
    data: { old_password: oldPassword, new_password: newPassword },
  })
}

/** 注销账号（软删除并清理隐私字段）；网页账号需带密码确认。 */
export function deactivateAccount(password?: string): Promise<unknown> {
  return request<unknown>({
    url: '/user/account/deactivate',
    method: 'POST',
    data: { password: password || null },
  })
}

/** 跨端配对码。 */
export interface PairingCode {
  code: string
  /** 有效秒数，后端固定 600 秒（10 分钟）。 */
  expires_in: number
}

/** 生成跨端配对码：在另一端输入该码即可绑定到本账号。 */
export function createPairing(): Promise<PairingCode> {
  return request<PairingCode>({ url: '/auth/pairing', method: 'POST', data: {} })
}

/**
 * 用原账号的配对码绑定原账号。
 *
 * 返回绑定后的新会话：当前账号的登录身份会并入原账号，
 * 调用方需要用新会话替换本地令牌。
 */
export function claimPairing(code: string): Promise<SessionData> {
  return request<SessionData>({
    url: '/auth/pairing/claim',
    method: 'POST',
    data: { code: code.trim().toUpperCase() },
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
