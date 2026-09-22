/** 标签管理 API。 */
import request from '@/utils/request'

export interface AdminTag {
  id: number
  name: string
}

export function getAdminTags() {
  return request.get<any, { items: AdminTag[] }>('/admin/tags')
}

export function createAdminTag(name: string) {
  return request.post<any, AdminTag>('/admin/tags', { name })
}

export function deleteAdminTag(id: number) {
  return request.delete(`/admin/tags/${id}`)
}
