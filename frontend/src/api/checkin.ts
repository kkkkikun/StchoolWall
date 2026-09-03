/** 签到 API。收益体系定稿后在此扩展（奖励领取/积分等）。 */
import { get, post } from '@/utils/request'

export interface CheckinResult {
  already: boolean
  streak_days: number
  today: string
}

export interface CheckinStatus {
  today_checked: boolean
  streak_days: number
  month_count: number
  total_count: number
  today: string
}

/** 每日签到（重复签到返回 already=true） */
export function doCheckin() {
  return post<CheckinResult>('/user/checkin')
}

/** 签到状态：今日已签/连签/本月/累计 */
export function getCheckinStatus() {
  return get<CheckinStatus>('/user/checkin/status')
}
