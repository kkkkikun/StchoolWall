/**
 * 统一的用户可读网络错误映射（纯函数，无平台依赖，便于 Node 单测）。
 * 底层网络/超时错误统一为友好可重试提示；后端业务错误原样保留。
 */

const NETWORK_ERROR_PATTERN = /request:fail|uploadfile:fail|downloadfile:fail|failed to fetch|fetch failed|networkerror|timeout|timed out|abort/i

export const NETWORK_ERROR_MESSAGE = '网络连接失败，请检查网络后重试'

export function isNetworkError(e: unknown): boolean {
  return NETWORK_ERROR_PATTERN.test((e as Error)?.message || '')
}

export function friendlyNetworkError(e: unknown, fallback: string): string {
  const msg = (e as Error)?.message || ''
  if (isNetworkError(e)) return NETWORK_ERROR_MESSAGE
  return msg || fallback
}
