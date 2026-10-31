import { get, post, uploadMultipart } from '@/utils/request'
import type { paths } from '@/types/generated-api'
type ProofFields = Omit<paths['/api/v1/student-verifications']['post']['requestBody']['content']['multipart/form-data'], 'file'>

export interface VerificationRecord {
  id: string
  school_id: string
  status: 'draft' | 'pending' | 'approved' | 'rejected' | 'expired' | 'revoked'
  review_reason?: string
  verified_until?: string
  evidence_delete_after?: string
}
export interface VerificationChallenge {
  verification_id: string
  challenge_id: string
  code: string
  expires_at: string
  school_id: string
  school_name: string
}
export function getVerification() {
  return get<{ enabled: boolean; school_name: string; verification: VerificationRecord | null }>(
    '/student-verifications/me',
  )
}
export function createVerificationChallenge() {
  return post<VerificationChallenge>('/student-verifications/challenge', {})
}
export function submitStudentCard(
  challenge: VerificationChallenge, studentId: string, filePath: string, validUntil = '',
) {
  const body: ProofFields = {
    verification_id: challenge.verification_id,
    challenge_code: challenge.code,
    student_id: studentId,
    consent_version: 'student-card-v1',
    ...(validUntil ? { card_valid_until: validUntil } : {}),
  }
  return uploadMultipart<VerificationRecord>('/student-verifications', filePath, body as Record<string, string>)
}
