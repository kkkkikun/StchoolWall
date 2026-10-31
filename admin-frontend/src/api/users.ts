/** 用户管理 API。 */
import request from '@/utils/request'

export interface AdminUser {
  id: string
  nickname: string
  role: string
  is_verified: boolean
  student_id: string | null
  real_name: string | null
  status: number
  created_at: string
}

export interface UsersPage {
  items: AdminUser[]
  total: number
  page: number
  page_size: number
}

export interface UserDetail extends AdminUser {
  wechat_id: string | null
  avatar_url: string | null
  posts_count: number
  comments_count: number
  likes_received: number
  reported_count: number
  recent_posts: { id: number; content: string; status: number; created_at: string | null }[]
}

export function getUsers(params: Record<string, unknown>) {
  return request.get<any, UsersPage>('/admin/users', { params })
}

export function getUserDetail(id: string) {
  return request.get<any, UserDetail>(`/admin/users/${id}`)
}

export function updateUserStatus(id: string, status: 0 | 1) {
  return request.put(`/admin/users/${id}/status`, null, { params: { status } })
}

export function updateUserRole(id: string, role: string) {
  return request.put(`/admin/users/${id}/role`, { role })
}

export function exportUsers(): Promise<Blob> {
  return request.get<never, Blob>('/admin/export/users', {
    responseType: 'blob',
  })
}

export function exportUsersUrl() {
  return '/api/v1/admin/export/users'
}
