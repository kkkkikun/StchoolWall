/** 组局 API（模块 D）。 */
import { get, post, del } from '@/utils/request'

export type PartyType = 'group' | 'purchase'

export interface PartyItem {
  id: number
  type: PartyType
  category: string
  title: string
  content: string
  total: number
  joined_count: number
  status: number // 1招募中 2已满
  meet_time: string | null
  location: string | null
  user: { nickname: string }
  is_joined: boolean
  created_at: string
}

export interface PartyCreateBody {
  type: PartyType
  category: string
  title: string
  content: string
  total: number
  location?: string
}

export function listParties(params: { category?: string; only_vacant?: boolean; cursor?: number } = {}) {
  return get<{ items: PartyItem[]; next_cursor: number | null; has_more: boolean }>('/parties', params)
}

export function partiesSummary() {
  return get<{ total_members: number }>('/parties/summary')
}

export function createParty(body: PartyCreateBody) {
  return post<PartyItem>('/parties', body)
}

export function joinParty(id: number) {
  return post<{ joined: boolean; joined_count: number; full?: boolean }>(`/parties/${id}/join`)
}

export function leaveParty(id: number) {
  return del<{ joined: boolean; joined_count: number }>(`/parties/${id}/join`)
}

export function myParties(cursor?: number) {
  return get<{ items: PartyItem[]; next_cursor: number | null; has_more: boolean }>('/me/parties', { cursor })
}
