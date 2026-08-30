/** 管理后台 API：对齐后端 /admin/* 真实契约。 */
import { get, put } from '@/utils/request'

// ---- 举报 ----

export interface AdminReport {
  id: number
  post_id: number
  post_content: string
  post_status: number
  reporter: { id: string; nickname: string }
  reason: string
  description?: string | null
  status: 'pending' | 'dismissed' | 'resolved'
  created_at: string
}

export type ReportAction = 'dismiss' | 'ban_post' | 'ban_user'

export function getReports(status?: string, cursor?: number) {
  return get<{ items: AdminReport[]; next_cursor: number | null; has_more: boolean }>(
    '/admin/reports', { status, cursor }
  )
}

/** 处理举报：PUT /admin/reports/{id} body {action} */
export function handleReport(reportId: number, action: ReportAction) {
  return put<{ report_id: number; status: string }>(`/admin/reports/${reportId}`, { action })
}

// ---- 用户 ----

export interface AdminUser {
  id: string
  nickname: string
  role: string
  is_verified: boolean
  student_id?: string | null
  real_name?: string | null
  status: number
  created_at: string
}

export function getUsers(cursor?: string) {
  return get<{ items: AdminUser[]; next_cursor: string | null; has_more: boolean }>(
    '/admin/users', { cursor }
  )
}

/** 冻结/解冻：PUT /admin/users/{id}/status?status=0|1 */
export function updateUserStatus(userId: string, status: 0 | 1) {
  return put<{ status: number }>(`/admin/users/${userId}/status?status=${status}`)
}

// ---- 帖子管理 ----

export interface AdminPost {
  id: number
  post_type: string
  category?: string | null
  content: string
  images_count: number
  price?: number | null
  status: number
  is_pinned: boolean
  author: { nickname: string; id: string }
  like_count: number
  comment_count: number
  view_count: number
  created_at: string
}

export function getAdminPosts(status?: number, q?: string, cursor?: number) {
  return get<{ items: AdminPost[]; next_cursor: number | null; has_more: boolean }>(
    '/admin/posts', { status, q, cursor }
  )
}

/** 状态流转：PUT /admin/posts/{id}/status?status=（0→1 过审 / 0→-1 拒审 / 1→-1 封禁 / -1→1 恢复） */
export function updateAdminPostStatus(postId: number, status: number) {
  return put<{ status: number }>(`/admin/posts/${postId}/status?status=${status}`)
}

/** 置顶/取消置顶 */
export function pinPost(postId: number, pinned: boolean) {
  return put<{ is_pinned: boolean }>(`/admin/posts/${postId}/pin`, { pinned })
}

// ---- 看板 ----

export interface AdminStats {
  pending_posts: number
  pending_reports: number
  total_posts: number
  total_users: number
  frozen_users: number
  posts_today: number
}

export function getAdminStats() {
  return get<AdminStats>('/admin/stats')
}
