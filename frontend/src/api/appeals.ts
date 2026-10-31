import { get, post } from '@/utils/request'

export type AppealType = 'post' | 'comment' | 'party' | 'verification'
export interface Appeal {
  id: string; entity_type: AppealType; entity_id: string; reason: string
  status: 'pending' | 'accepted' | 'rejected'; decision_reason?: string; created_at: string
}
export function submitAppeal(entityType: AppealType, entityId: string, reason: string) {
  return post<Appeal>('/appeals', { entity_type: entityType, entity_id: entityId, reason })
}
export function getAppeals(page = 1) { return get<{ items: Appeal[] }>('/appeals', { page }) }
