import { get, post, uploadMultipart } from '@/utils/request'
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
  created_at?: string | null
  screenshot_count?: number
}

export interface FeedbackItem {
  id: number
  category: FeedbackCategory
  severity: FeedbackSeverity
  title: string
  content: string
  status: string
  created_at?: string | null
  screenshot_count?: number
}

/** 创建反馈；返回的 upload_token 用于后续上传截图。 */
export function createFeedback(payload: FeedbackCreatePayload): Promise<FeedbackCreated> {
  return post<FeedbackCreated>('/feedback', payload)
}

/**
 * 上传一张截图（单文件 multipart）。
 * upload_token 必须放在表单字段里而不是请求头：后端按表单字段校验上传权限。
 */
export function uploadFeedbackScreenshot(
  feedbackId: number,
  uploadToken: string,
  filePath: string,
): Promise<{ id: number; screenshot_count: number }> {
  return uploadMultipart<{ id: number; screenshot_count: number }>(
    `/feedback/${feedbackId}/screenshot`,
    filePath,
    { upload_token: uploadToken },
  )
}

/** 我提交的反馈（仅登录用户可见）。 */
export function getMyFeedback(page = 1): Promise<{ items: FeedbackItem[] }> {
  return get<{ items: FeedbackItem[] }>('/feedback/mine', { page })
}
