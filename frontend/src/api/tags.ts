import type { Tag } from '@/types/api'
import { get } from '@/utils/request'

/** 获取所有标签 */
export function getTags() {
  return get<Tag[]>('/tags')
}
