import type { UserInfo } from '@/types/api'
import { get, post } from '@/utils/request'

export interface Report {
  id: number
  post_id: number
  reason: string
  description?: string
}

/** 获取举报列表 */
export async function getReports() {
  return get<Report[]>('/admin/reports')
}

/** 获取用户列表 */
export async function getUsers() {
  return get<UserInfo[]>('/admin/users')
}

/** 处理举报 */
export async function handleReport(reportId: number, approved: boolean) {
  return post(`/admin/reports/${reportId}/handle`, { approved })
}
