import request from '@/utils/request'

export interface VerificationItem {
  id: string; user_id: string; nickname: string; school_id: string
  status: string; challenge_code: string; card_valid_until?: string
  evidence_available: boolean; created_at: string; submitted_at?: string
  review_reason?: string; verified_until?: string
}
export function listVerifications(status: string, page: number) {
  return request.get<never, { items: VerificationItem[]; total: number }>(
    '/admin/student-verifications', { params: { status, page, page_size: 20 } },
  )
}
export async function evidenceBlob(id: string): Promise<Blob> {
  try {
    return await request.get<never, Blob>(
      `/admin/student-verifications/${encodeURIComponent(id)}/evidence`,
      { responseType: 'blob', headers: { 'Cache-Control': 'no-store' } },
    )
  } catch (error: any) {
    if (error?.response?.status === 401) {
      throw new Error('登录已失效，请重新登录')
    }
    if (error?.response?.status === 403) {
      throw new Error('需要有效管理员权限与多因素认证')
    }
    throw new Error('无法读取照片或已过保留期')
  }
}
export function reviewVerification(id: string, data: object) {
  return request.post(`/admin/student-verifications/${encodeURIComponent(id)}/review`, data)
}
export function revokeVerification(id: string, reason: string) {
  return request.post(`/admin/student-verifications/${encodeURIComponent(id)}/revoke`, { reason })
}
