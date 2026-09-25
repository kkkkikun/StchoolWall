/** 站内活动管理 API。 */
import request from '@/utils/request'

export interface AdminActivity {
  id: number
  title: string
  image_url: string | null
  summary: string | null
  content: string
  location: string | null
  start_at: string | null
  end_at: string | null
  status: number
  created_at: string
}

export interface ActivitiesPage {
  items: AdminActivity[]
  total: number
  page: number
  page_size: number
}

export function getActivities(params?: Record<string, unknown>) {
  return request.get<any, ActivitiesPage>('/admin/activities', { params })
}

export function createActivity(data: Record<string, unknown>) {
  return request.post('/admin/activities', data)
}

export function updateActivity(id: number, data: Record<string, unknown>) {
  return request.put(`/admin/activities/${id}`, data)
}

export function deleteActivity(id: number) {
  return request.delete(`/admin/activities/${id}`)
}
