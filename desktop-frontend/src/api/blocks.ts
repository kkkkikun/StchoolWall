/**
 * 屏蔽管理。
 *
 * 屏蔽是双向生效的：被屏蔽方看不到我的内容，我也看不到对方的内容；
 * 解除屏蔽只取消我发起的屏蔽。
 */
import { request } from '@/utils/http'
import { mapBlockedUser } from './mappers'
import type { BlockedUser } from './types'

type Raw = Record<string, any>

/** 屏蔽列表的一页（游标分页，游标是被屏蔽用户 id）。 */
export interface BlockedUsersPage {
  items: BlockedUser[]
  hasMore: boolean
  nextCursor: string | null
}

/** 屏蔽某个用户。 */
export function blockUser(userId: string): Promise<{ blocked: boolean }> {
  return request<{ blocked: boolean }>({
    url: `/users/${encodeURIComponent(userId)}/block`,
    method: 'POST',
    data: {},
  })
}

/** 解除对某个用户的屏蔽。 */
export function unblockUser(userId: string): Promise<{ blocked: boolean }> {
  return request<{ blocked: boolean }>({
    url: `/users/${encodeURIComponent(userId)}/block`,
    method: 'DELETE',
  })
}

/** 我发起的屏蔽列表。 */
export async function listBlockedUsers(cursor?: string): Promise<BlockedUsersPage> {
  const data = await request<Raw>({
    url: '/user/blocks',
    params: { limit: 20, cursor },
  })
  const items = (data?.items ?? []).map(mapBlockedUser)
  return {
    items,
    hasMore: !!data?.has_more,
    nextCursor: data?.next_cursor ?? null,
  }
}
