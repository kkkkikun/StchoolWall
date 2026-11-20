import request from '@/utils/request'
import type { AdminRole } from '@/api/auth'

export interface AdminAccount {
  id: string
  username: string
  nickname: string
  role: AdminRole
  mfa_enabled: boolean
  is_active: boolean
  pwd_version: number
  last_login_at: string | null
  created_at: string
}

export interface AdminAccountsPage {
  items: AdminAccount[]
  total: number
  page: number
  page_size: number
}

export function getAdminAccounts(params?: Record<string, unknown>) {
  return request.get<any, AdminAccountsPage>('/admin/admins', { params })
}

export function createAdminAccount(data: { username: string; nickname: string; password: string; role: AdminRole }) {
  return request.post<any, { id: string; username: string; nickname: string; role: AdminRole }>('/admin/admins', data)
}

export function updateAdminAccountStatus(id: string, isActive: boolean) {
  return request.put(`/admin/admins/${id}/status`, { is_active: isActive })
}

export function resetAdminAccountPassword(id: string, newPassword: string) {
  return request.put(`/admin/admins/${id}/password`, { new_password: newPassword })
}
