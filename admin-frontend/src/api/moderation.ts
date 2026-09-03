/** 自动审核 API：敏感词库管理 + 审核记录查询。 */
import request from '@/utils/request'

export interface SensitiveWord {
  id: number
  word: string
  /** hard=硬违规(直接拒绝) | gray=灰度(转人工) */
  level: 'hard' | 'gray'
  created_by: string | null
  created_at: string
}

export interface ModerationRecord {
  id: number
  post_id: number
  /** rule=本地敏感词/频率 | wechat=微信内容安全 */
  source: 'rule' | 'wechat'
  verdict: 'pass' | 'review' | 'reject' | 'error'
  matched: string[] | null
  reason: string | null
  trace_id: string | null
  created_at: string
}

interface Paged<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export function getSensitiveWords(params?: Record<string, unknown>) {
  return request.get<any, Paged<SensitiveWord>>('/admin/sensitive-words', { params })
}

export function createSensitiveWord(data: { word: string; level: 'hard' | 'gray' }) {
  return request.post('/admin/sensitive-words', data)
}

export function updateSensitiveWord(id: number, data: { word: string; level: 'hard' | 'gray' }) {
  return request.put(`/admin/sensitive-words/${id}`, data)
}

export function deleteSensitiveWord(id: number) {
  return request.delete(`/admin/sensitive-words/${id}`)
}

export function getModerationRecords(params?: Record<string, unknown>) {
  return request.get<any, Paged<ModerationRecord>>('/admin/moderation-records', { params })
}
