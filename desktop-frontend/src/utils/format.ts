/** 展示层的格式化工具。 */

const MINUTE = 60
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

/** 相对时间：刚刚 / N 分钟前 / N 小时前 / N 天前 / 具体日期。 */
export function relativeTime(value: string): string {
  if (!value) return ''
  const timestamp = Date.parse(value)
  if (Number.isNaN(timestamp)) return value
  const diff = Date.now() - timestamp
  if (diff < MINUTE * 1000) return '刚刚'
  if (diff < HOUR * 1000) return `${Math.floor(diff / (MINUTE * 1000))} 分钟前`
  if (diff < DAY * 1000) return `${Math.floor(diff / (HOUR * 1000))} 小时前`
  if (diff < 30 * DAY * 1000) return `${Math.floor(diff / (DAY * 1000))} 天前`
  return new Date(timestamp).toLocaleDateString('zh-CN')
}

/** 数字缩写：1234 → 1.2k。 */
export function compactNumber(value: number): string {
  if (value < 1000) return String(value)
  if (value < 10000) return `${(value / 1000).toFixed(1)}k`
  return `${Math.floor(value / 1000)}k`
}

/** 帖子类型 → 中文标签。 */
export const POST_TYPE_LABELS: Record<string, string> = {
  lost_found: '失物招领',
  second_hand: '二手交易',
  carpool: '拼车',
  general: '闲聊',
  advertisement: '公告',
}
