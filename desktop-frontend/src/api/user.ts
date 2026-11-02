import { request } from '@/utils/http'
import { mapHotUser, mapMyProfile, mapNotification, mapPublicProfile } from './mappers'
import type {
  HotUser,
  MyProfile,
  NotificationItem,
  PageData,
  PublicProfile,
  UnreadSummary,
} from './types'

type Raw = Record<string, any>

/** 自己的资料（含真实姓名与学号，后端只对本人与管理员返回）。 */
export async function getMyProfile(): Promise<MyProfile> {
  const data = await request<Raw>({ url: '/user/profile' })
  return mapMyProfile(data)
}

/** 修改资料。头像与横幅在生产必须传 media_id，提交后进入异步审核。 */
export function updateMyProfile(payload: {
  nickname?: string
  bio?: string
  wechat_id?: string
  avatar_media_id?: string
  banner_media_id?: string
}): Promise<unknown> {
  return request<unknown>({ url: '/user/profile', method: 'PUT', data: payload })
}

/** 他人主页资料（公开字段）。 */
export async function getPublicProfile(userId: string): Promise<PublicProfile> {
  const data = await request<Raw>({ url: `/users/${encodeURIComponent(userId)}/profile` })
  return mapPublicProfile(data)
}

/** 通知列表。公告也走这里（type=announcement，正文在 payload 里）。 */
export async function getNotifications(
  type?: string,
  cursor?: number,
): Promise<PageData<NotificationItem>> {
  const data = await request<PageData<Raw>>({
    url: '/notifications',
    params: { type, cursor },
  })
  return {
    items: (data.items ?? []).map(mapNotification),
    next_cursor: data.next_cursor ?? null,
    has_more: !!data.has_more,
  }
}

export function getUnreadSummary(): Promise<UnreadSummary> {
  return request<UnreadSummary>({ url: '/notifications/unread-summary' })
}

export function markNotificationRead(notificationId: string): Promise<unknown> {
  return request<unknown>({
    url: `/notifications/${encodeURIComponent(notificationId)}/read`,
    method: 'POST',
    data: {},
  })
}

export function markAllNotificationsRead(): Promise<unknown> {
  return request<unknown>({ url: '/notifications/read-all', method: 'POST', data: {} })
}

/** 热门用户榜。 */
export async function getHotUsers(limit = 5): Promise<HotUser[]> {
  const data = await request<{ items: Raw[] }>({ url: '/user/hot-ranking', params: { limit } })
  return (data.items ?? []).map(mapHotUser)
}

/** 我的互动统计。 */
export function getMyStats(): Promise<Raw> {
  return request<Raw>({ url: '/me/stats' })
}
