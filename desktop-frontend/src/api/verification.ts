/**
 * 学生证认证。
 *
 * 与 H5 端 frontend/src/api/verification.ts 语义一致，但按 PC 端的写法走
 * utils/http 的 request 封装与 api/mappers 的防腐蚀层。
 */
import { http, request } from '@/utils/http'
import { mapVerificationRecord } from './mappers'
import type { VerificationRecord } from './types'

type Raw = Record<string, any>

/** 拍摄码。拍摄码 10 分钟内有效，过期需重新获取。 */
export interface VerificationChallenge {
  verificationId: string
  challengeId: string
  /** 手写拍摄码，需与学生证同框拍照。 */
  code: string
  expiresAt: string
  schoolId: string
  schoolName: string
}

/** 当前认证状态（含是否开放认证开关）。 */
export interface VerificationOverview {
  /** 后端是否开放学生证认证。 */
  enabled: boolean
  schoolName: string
  verification: VerificationRecord | null
}

/** 学生证认证同意书版本；后端只认这一个版本。 */
export const STUDENT_CARD_CONSENT_VERSION = 'student-card-v1'

/** 读取当前用户的认证状态。 */
export async function getVerification(): Promise<VerificationOverview> {
  const data = await request<Raw>({ url: '/student-verifications/me' })
  return {
    enabled: !!data?.enabled,
    schoolName: typeof data?.school_name === 'string' ? data.school_name : '',
    verification: data?.verification ? mapVerificationRecord(data.verification) : null,
  }
}

/** 申请一个拍摄码（用于与学生证同框拍照）。 */
export async function createVerificationChallenge(): Promise<VerificationChallenge> {
  const data = await request<Raw>({ url: '/student-verifications/challenge', method: 'POST', data: {} })
  return {
    verificationId: String(data?.verification_id ?? ''),
    challengeId: String(data?.challenge_id ?? ''),
    code: String(data?.code ?? ''),
    expiresAt: String(data?.expires_at ?? ''),
    schoolId: String(data?.school_id ?? ''),
    schoolName: String(data?.school_name ?? ''),
  }
}

/**
 * 提交学生证照片与学号，走 multipart 表单。
 *
 * 证件照片只供授权管理员核验，不公开、不送交外部内容审核服务。
 */
export async function submitStudentCard(
  challenge: VerificationChallenge,
  studentId: string,
  file: File,
  cardValidUntil = '',
): Promise<VerificationRecord> {
  const form = new FormData()
  form.append('verification_id', challenge.verificationId)
  form.append('challenge_code', challenge.code)
  form.append('student_id', studentId.trim())
  form.append('consent_version', STUDENT_CARD_CONSENT_VERSION)
  if (cardValidUntil) {
    form.append('card_valid_until', cardValidUntil)
  }
  form.append('file', file)
  const response = await http.post<{ code: number; data: Raw }>('/student-verifications', form)
  return mapVerificationRecord(response.data.data)
}
