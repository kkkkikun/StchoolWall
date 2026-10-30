import { get, post, del } from '@/utils/request'

export interface BlockedUser { id: string; nickname: string | null }
export interface BlockedUsersPage { items: BlockedUser[]; has_more: boolean; next_cursor: string | null }
export const blockUser = (id: string) => post<{ blocked: boolean }>(`/users/${encodeURIComponent(id)}/block`, {})
export const unblockUser = (id: string) => del<{ blocked: boolean }>(`/users/${encodeURIComponent(id)}/block`)
export function listBlockedUsers(cursor?: string) {
  return get<BlockedUsersPage>('/user/blocks', { limit: 20, ...(cursor ? { cursor } : {}) })
}
