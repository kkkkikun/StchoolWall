/** 评论/组局/公告/日志 API。 */
import request from '@/utils/request'

// ---- 评论 ----

export interface AdminComment {
  id: number
  post_id: number
  post_content: string
  author: { nickname: string; id: string }
  content: string
  status: number
  created_at: string
}

export function getComments(params: Record<string, unknown>) {
  return request.get<any, { items: AdminComment[]; total: number }>('/admin/comments', { params })
}

export function deleteComment(id: number) {
  return request.delete(`/admin/comments/${id}`)
}

/** 评论状态流转：0 待审 → 1 过审 / -1 拒审；1 → -1 下架 */
export function updateCommentStatus(id: number, status: number) {
  return request.put(`/admin/comments/${id}/status`, null, { params: { status } })
}

// ---- 组局 ----

export interface AdminParty {
  id: number
  type: string
  category: string
  title: string
  content: string
  total: number
  joined_count: number
  status: number
  meet_time: string | null
  location: string | null
  organizer: { nickname: string; id: string }
  created_at: string
}

export function getParties(params: Record<string, unknown>) {
  return request.get<any, { items: AdminParty[]; total: number }>('/admin/parties', { params })
}

export function updatePartyStatus(id: number, status: number) {
  return request.put(`/admin/parties/${id}/status`, null, { params: { status } })
}

export interface PartyMember {
  user_id: string
  nickname: string
  student_id: string | null
  real_name: string | null
  joined_at: string
}

export function getPartyMembers(id: number) {
  return request.get<any, { items: PartyMember[]; total: number; page: number; page_size: number }>(
    `/admin/parties/${id}/members`,
  )
}

// ---- 公告 ----

export interface Announcement {
  batch_id: string
  title: string
  content: string
  recipients: number
  created_at: string
}

export function sendAnnouncement(data: { title: string; content: string; audience: 'all' | 'verified' }) {
  return request.post<any, { batch_id: string; recipients: number }>('/admin/announcements', data)
}

export function getAnnouncements(params: Record<string, unknown>) {
  return request.get<any, { items: Announcement[]; total: number }>('/admin/announcements', { params })
}

// ---- 操作日志 ----

export interface AdminLogItem {
  id: number
  admin_id: string
  admin_name: string
  source: string
  action: string
  target_type: string | null
  target_id: string | null
  detail: Record<string, unknown> | null
  ip: string | null
  created_at: string
}

export function getLogs(params: Record<string, unknown>) {
  return request.get<any, { items: AdminLogItem[]; next_cursor: number | null; has_more: boolean }>(
    '/admin/logs', { params },
  )
}
