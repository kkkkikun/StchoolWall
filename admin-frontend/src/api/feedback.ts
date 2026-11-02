/** 内部测试反馈 API（管理台）。 */
import request from '@/utils/request'

export type FeedbackCategory = 'bug' | 'ui' | 'feature' | 'other'
export type FeedbackSeverity = 'low' | 'medium' | 'high'
export type FeedbackStatus = 'open' | 'handling' | 'resolved' | 'closed'

export interface FeedbackItem {
  id: number
  category: FeedbackCategory
  severity: FeedbackSeverity
  title: string
  content: string
  page_url: string | null
  route: string | null
  viewport: string | null
  theme: string | null
  app_version: string | null
  user_agent: string | null
  reporter_name: string | null
  status: FeedbackStatus
  note: string | null
  created_at: string | null
  handled_at: string | null
  screenshot_count: number
}

export interface FeedbackScreenshot {
  path: string
  size: number
  content_type: string
  sha256: string
}

export interface FeedbackDetail extends FeedbackItem {
  diagnostics: Record<string, unknown> | null
  screenshots: FeedbackScreenshot[]
  client_ip: string | null
}

export interface FeedbackStats {
  open: number
  handling: number
  resolved: number
  closed: number
  total: number
}

export interface FeedbackListParams {
  status?: string
  category?: string
  keyword?: string
  page?: number
}

export function getFeedbackList(params: FeedbackListParams) {
  return request.get<any, { items: FeedbackItem[]; total: number; page: number }>(
    '/admin/feedback',
    { params },
  )
}

export function getFeedbackStats() {
  return request.get<any, FeedbackStats>('/admin/feedback/stats')
}

export function getFeedbackDetail(id: number) {
  return request.get<any, FeedbackDetail>(`/admin/feedback/${id}`)
}

/** 截图接口直接返回图片字节：<img> 请求不会带鉴权头，只能取 Blob 再转 objectURL。 */
export function getFeedbackScreenshot(id: number, index: number) {
  return request.get<any, Blob>(`/admin/feedback/${id}/screenshot/${index}`, { responseType: 'blob' })
}

/** 后端只收 multipart/form-data 的 status 与 note 两个字段。 */
export function updateFeedback(id: number, data: { status: FeedbackStatus; note: string }) {
  const form = new FormData()
  form.append('status', data.status)
  form.append('note', data.note)
  return request.put<any, FeedbackDetail>(`/admin/feedback/${id}`, form)
}
