/** 举报处理 API。 */
import request from '@/utils/request'

export interface AdminReport {
  id: number
  post_id: number
  post_content: string
  post_status: number
  reporter: { id: string; nickname: string }
  reason: string
  description: string | null
  status: 'pending' | 'dismissed' | 'resolved'
  created_at: string
}

export function getReports(params: Record<string, unknown>) {
  return request.get<any, { items: AdminReport[]; next_cursor: number | null; has_more: boolean }>(
    '/admin/reports', { params },
  )
}

export function handleReport(id: number, action: 'dismiss' | 'ban_post' | 'ban_user') {
  return request.put(`/admin/reports/${id}`, { action })
}
