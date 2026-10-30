import { post, get, del, request } from '@/utils/request'
import { tokenStorage, userStorage, type SessionData } from '@/utils/storage'
import type { components } from '@/types/generated-api'
type Schemas = components['schemas']

export type LoginResponse = SessionData
export function login(code: string) { const body: Schemas['WxLoginRequest'] = { code }; return post<LoginResponse>('/auth/login', body) }
export function devLogin(asAdmin = false) {
  return post<LoginResponse>(`/auth/dev-login?as_admin=${asAdmin}`, {})
}
export function webLogin(username: string, password: string) {
  const body: Schemas['WebLoginRequest'] = { username, password }
  return post<LoginResponse>('/auth/web-login', body)
}
export function register(username: string, password: string) {
  const body: Schemas['RegisterRequest'] = { username, password }
  return post<LoginResponse>('/auth/register', body)
}
export function setLoginPassword(username: string, password: string) {
  const body: Schemas['SetPasswordRequest'] = { username, password }
  return post('/auth/password', body)
}
export function mpLogin(code: string, _state: string) {
  const body: Schemas['MpLoginRequest'] = { code }
  return post<LoginResponse>('/auth/mp-login', body)
}
export async function storeLoginSession(data: SessionData): Promise<void> {
  try { tokenStorage.setSession(data) }
  catch (error) {
    userStorage.clear()
    try {
      await request({ url: '/auth/logout', method: 'POST', skipRefresh: true,
        header: { Authorization: `Bearer ${data.access_token}` } })
    } catch { /* Session expires server-side if the network is unavailable. */ }
    throw error
  }
}
export async function logout(): Promise<void> {
  await post('/auth/logout', {})
  userStorage.clear()
}
export interface SessionItem {
  id: string; client_type: string; created_at: string; last_seen_at?: string; is_current?: boolean
}
export function getSessions() { return get<{ items: SessionItem[] }>('/auth/sessions') }
export function revokeSession(id: string) { return del(`/auth/sessions/${encodeURIComponent(id)}`) }
export function createPairing() { return post<{ code: string; expires_in: number }>('/auth/pairing', {}) }
export async function claimPairing(code: string) {
  const response = await post<LoginResponse>('/auth/pairing/claim', { code })
  await storeLoginSession(response)
  return response
}
export async function wxLoginAndStore(): Promise<boolean> {
  try {
    if (tokenStorage.isLoggedIn()) return true
    const response = await uni.login()
    const code = (response as { code?: string }).code
    if (!code) return false
    await storeLoginSession(await login(code))
    return true
  } catch { return false }
}

export function generateRecoveryCodes() { return post<{ codes: string[] }>('/auth/recovery-codes', {}) }
export function recoverPassword(username: string, recoveryCode: string, newPassword: string) {
  const body: Schemas['RecoveryRequest'] = { username, recovery_code: recoveryCode, new_password: newPassword }
  return post('/auth/recover', body)
}
