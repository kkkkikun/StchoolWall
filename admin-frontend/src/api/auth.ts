import request from '@/utils/request'

export type AdminRole = 'admin' | 'owner'

export interface AdminIdentity {
  id: string
  username: string
  nickname: string
  role: AdminRole
  mfa_enabled: boolean
}

export interface LoginResult {
  access_token: string
  admin: AdminIdentity
}

export interface MfaSetupResult {
  mfa_setup_required: true
  setup_token: string
  secret: string
  otpauth_url: string
  admin: AdminIdentity
}

export type LoginResponse = LoginResult | MfaSetupResult

export function login(username: string, password: string, loginKind: AdminRole, totpCode?: string) {
  return request.post<any, LoginResponse>('/admin/auth/login', {
    username, password, login_kind: loginKind, totp_code: totpCode || undefined,
  })
}

export function verifyMfaSetup(setupToken: string, totpCode: string) {
  return request.post<any, LoginResult>('/admin/auth/mfa/setup', {
    setup_token: setupToken, totp_code: totpCode,
  })
}

export function changePassword(oldPassword: string, newPassword: string) {
  return request.put('/admin/auth/password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}

export interface MeResult {
  id: string
  display_name: string
  source: string
  role: AdminRole
  username: string
}

export function me() {
  return request.get<any, MeResult>('/admin/auth/me')
}

export function logout() { return request.post('/admin/auth/logout') }
