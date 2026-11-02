import { http, request } from '@/utils/http'
import type { Diagnostics } from '@/utils/diagnostics'

export type FeedbackCategory = 'bug' | 'ui' | 'feature' | 'other'
export type FeedbackSeverity = 'low' | 'medium' | 'high'

export interface FeedbackCreatePayload {
  category: FeedbackCategory
  severity: FeedbackSeverity
  title: string
  content: string
  page_url?: string
  route?: string
  viewport?: string
  theme?: string
  app_version?: string
  reporter_name?: string
  test_code?: string
  diagnostics?: Diagnostics
}

export interface FeedbackCreated {
  id: number
  upload_token: string
  status: string
  created_at: string | null
  screenshot_count: number
}

export interface FeedbackItem {
  id: number
  category: FeedbackCategory
  severity: FeedbackSeverity
  title: string
  content: string
  status: string
  created_at: string | null
  screenshot_count: number
}

export function createFeedback(payload: FeedbackCreatePayload): Promise<FeedbackCreated> {
  return request<FeedbackCreated>({
    url: '/feedback',
    method: 'POST',
    data: payload,
  })
}

/**
 * 上传一张截图。走 http 而不是 request 包装：需要自己拼 multipart 表单，
 * 且要单独把 upload_token 作为表单字段传（不是请求头）。
 */
export async function uploadFeedbackScreenshot(
  feedbackId: number,
  uploadToken: string,
  file: File,
): Promise<{ id: number; screenshot_count: number }> {
  const form = new FormData()
  form.append('file', file)
  form.append('upload_token', uploadToken)
  const response = await http.post(`/feedback/${feedbackId}/screenshot`, form)
  return response.data.data
}

export function getMyFeedback(page = 1): Promise<{ items: FeedbackItem[] }> {
  return request<{ items: FeedbackItem[] }>({ url: '/feedback/mine', params: { page } })
}
