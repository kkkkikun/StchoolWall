/** 管理员账号管理 API。 */
import request from '@/utils/request'

export interface AdminAccount {
  id: string
  username: string
  nickname: string
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

export function createAdminAccount(data: { username: string; nickname: string; password: string }) {
  return request.post<any, { id: string; username: string; nickname: string }>('/admin/admins', data)
}

export function updateAdminAccountStatus(id: string, isActive: boolean) {
  return request.put(`/admin/admins/${id}/status`, { is_active: isActive })
}

export function resetAdminAccountPassword(id: string, newPassword: string) {
  return request.put(`/admin/admins/${id}/password`, { new_password: newPassword })
}
