/**
 * 申诉与处理记录。
 *
 * 申诉是私密请求：只有申诉人本人和管理团队能看到，申诉被受理也不会
 * 直接改变内容的审核状态，恢复内容仍需在对应审核页确认。
 */
import { request } from '@/utils/http'
import { mapAppealRecord } from './mappers'
import type { AppealRecord, AppealType } from './types'

type Raw = Record<string, any>

/** 申诉列表的一页（后端按 20 条一页翻页）。 */
export interface AppealsPage {
  items: AppealRecord[]
  hasMore: boolean
}

/** 发起申诉。对象编号需与对象类型匹配：帖子/评论/组局填数字编号，学生证认证填认证编号。 */
export function submitAppeal(
  entityType: AppealType,
  entityId: string,
  reason: string,
): Promise<AppealRecord> {
  return request<Raw>({
    url: '/appeals',
    method: 'POST',
    data: { entity_type: entityType, entity_id: entityId, reason },
  }).then(mapAppealRecord)
}

/** 我发起的申诉列表。 */
export async function getAppeals(page = 1): Promise<AppealsPage> {
  const data = await request<Raw>({ url: '/appeals', params: { page } })
  const items = (data?.items ?? []).map(mapAppealRecord)
  return { items, hasMore: items.length === 20 }
}
