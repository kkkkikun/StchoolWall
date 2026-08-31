/** 看板 API。 */
import request from '@/utils/request'

export interface AdminStats {
  pending_posts: number
  pending_reports: number
  total_posts: number
  total_users: number
  frozen_users: number
  posts_today: number
}

export interface TrendPoint {
  date: string
  posts: number
  comments: number
  likes: number
  new_users: number
  active_users: number
}

export function getStats() {
  return request.get<any, AdminStats>('/admin/stats')
}

export function getTrends(days = 14) {
  return request.get<any, { days: number; series: TrendPoint[] }>('/admin/stats/trends', { params: { days } })
}
