/** 站内活动 / 专题页 API。 */
import { get } from '@/utils/request'

export interface ActivityDetail {
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

export function getActivity(id: number) {
  return get<ActivityDetail>(`/activities/${id}`)
}
