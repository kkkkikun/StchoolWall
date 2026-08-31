/** 消息通知 API（模块 C）。无私信，im 恒 0。 */
import { get, post } from '@/utils/request'

export type NotificationType = 'comment' | 'like' | 'group' | 'moderation' | 'announcement'

export interface NotificationItem {
  id: number
  type: NotificationType
  actor: { nickname: string }
  post_id: number | null
  comment_id: number | null
  is_read: boolean
  created_at: string
  /** 公告（type=announcement）时的标题/正文 */
  payload?: { title?: string; content?: string }
}

export interface UnreadSummary {
  comment: number
  like: number
  group: number
  moderation: number
  im: number
}

export function listNotifications(type?: NotificationType, cursor?: number) {
  return get<{ items: NotificationItem[]; next_cursor: number | null; has_more: boolean }>(
    '/notifications', { type, cursor }
  )
}

export function unreadSummary() {
  return get<UnreadSummary>('/notifications/unread-summary')
}

export function readAllNotifications() {
  return post('/notifications/read-all')
}

export function readNotification(id: number) {
  return post(`/notifications/${id}/read`)
}
