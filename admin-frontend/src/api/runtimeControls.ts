import request from '@/utils/request'

export interface RuntimeControls {
  publishing_enabled: boolean
  moderation_enabled: boolean
  sensitive_words_enabled: boolean
  registration_enabled: boolean
  guest_posting_enabled: boolean
  guest_interaction_enabled: boolean
}

export type RuntimeControlKey = keyof RuntimeControls

export function getRuntimeControls() {
  return request.get<any, RuntimeControls>('/admin/runtime-controls')
}

export function updateRuntimeControls(data: Partial<RuntimeControls>) {
  return request.put<any, RuntimeControls>('/admin/runtime-controls', data)
}
