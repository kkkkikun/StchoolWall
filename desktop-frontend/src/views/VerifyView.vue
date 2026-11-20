<script setup lang="ts">
/**
 * 学生证认证。
 *
 * 流程与学生端一致：先取拍摄码 → 手写拍摄码与学生证同框拍照 →
 * 连同学号一起提交，等待人工审核。证件照片只供授权管理员核验，
 * 不公开、不送交外部内容审核服务。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Camera, WarningFilled } from '@element-plus/icons-vue'
import type { UploadFile, UploadFiles } from 'element-plus'

import {
  createVerificationChallenge,
  getVerification,
  submitStudentCard,
  type VerificationChallenge,
} from '@/api/verification'
import type { VerificationRecord, VerificationStatus } from '@/api/types'

const router = useRouter()

const record = ref<VerificationRecord | null>(null)
const challenge = ref<VerificationChallenge | null>(null)
const enabled = ref(false)
const schoolName = ref('本校')
const loading = ref(true)
const submitting = ref(false)
const consent = ref(false)
const studentId = ref('')
const cardValidUntil = ref('')
const files = ref<UploadFiles>([])

/** 审核中或已通过时不允许再次提交。 */
const canSubmit = computed(
  () => enabled.value && !['pending', 'approved'].includes(record.value?.status ?? ''),
)

const STATUS_LABELS: Record<VerificationStatus, string> = {
  draft: '未提交认证',
  pending: '审核中',
  approved: '已认证',
  rejected: '未通过',
  expired: '已过期',
  revoked: '已撤销',
}

const statusText = computed(() => {
  const status = record.value?.status
  if (!status || status === 'draft') return '未认证：完成学生证核验后即可发帖与互动'
  return STATUS_LABELS[status]
})

/** 是否处于「可以申诉」的终态。 */
const appealable = computed(() =>
  ['rejected', 'revoked', 'expired'].includes(record.value?.status ?? ''),
)

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : ''
}

function showError(error: unknown): void {
  ElMessage.error(error instanceof Error ? error.message : '操作失败')
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const overview = await getVerification()
    record.value = overview.verification
    enabled.value = overview.enabled
    schoolName.value = overview.schoolName || '本校'
  } catch (error) {
    showError(error)
  } finally {
    loading.value = false
  }
}

async function newChallenge(): Promise<void> {
  if (!consent.value) {
    ElMessage.warning('请先阅读并同意学生证认证隐私说明')
    return
  }
  try {
    challenge.value = await createVerificationChallenge()
    files.value = []
  } catch (error) {
    showError(error)
  }
}

function handleChange(_file: UploadFile, list: UploadFiles): void {
  files.value = list.slice(0, 1)
}

function handleRemove(_file: UploadFile, list: UploadFiles): void {
  files.value = list.slice(0, 1)
}

async function submit(): Promise<void> {
  const raw = files.value[0]?.raw
  if (!challenge.value || !raw || !studentId.value.trim() || !consent.value) return
  if (new Date(challenge.value.expiresAt).getTime() <= Date.now()) {
    showError(new Error('拍摄码已过期，请重新获取并拍照'))
    return
  }
  submitting.value = true
  try {
    record.value = await submitStudentCard(
      challenge.value,
      studentId.value,
      raw,
      cardValidUntil.value,
    )
    challenge.value = null
    files.value = []
    studentId.value = ''
    cardValidUntil.value = ''
    ElMessage.success('申请已提交，请等待人工审核')
  } catch (error) {
    showError(error)
  } finally {
    submitting.value = false
  }
}

function goAppeal(): void {
  router.push({ name: 'appeals', query: { type: 'verification', id: record.value?.id ?? '' } })
}

onMounted(load)
</script>

<template>
  <div class="sw-verify">
    <section class="sw-card sw-verify__card">
      <h3 class="sw-card__title">学生证认证</h3>
      <p class="sw-muted">通过人工核对学生证，开通校园发帖与互动</p>

      <div v-loading="loading" class="sw-verify__body">
        <el-alert
          v-if="!loading && !enabled"
          type="info"
          :closable="false"
          title="学生证认证暂未开放，请稍后再试。"
        />

        <template v-else-if="!loading">
          <el-tag
            class="sw-verify__status"
            :type="record?.status === 'approved' ? 'success' : record?.status === 'rejected' ? 'danger' : 'info'"
            effect="plain"
          >
            {{ statusText }}
          </el-tag>

          <p v-if="record?.reviewReason" class="sw-verify__reason">{{ record.reviewReason }}</p>

          <p v-if="record?.verifiedUntil" class="sw-muted">
            认证有效期至 {{ formatDate(record.verifiedUntil) }}
          </p>
          <p v-if="record?.status === 'pending'" class="sw-muted">
            请耐心等待人工审核。超过 14 天未处理将自动过期，可重新提交。
          </p>

          <el-button v-if="appealable" text type="primary" @click="goAppeal">
            对认证结果提出申诉
          </el-button>

          <template v-if="canSubmit">
            <p class="sw-muted">学校：{{ challenge?.schoolName || schoolName }}</p>

            <div class="sw-verify__tips">
              <p class="sw-verify__tips-title">请先阅读拍摄与隐私说明</p>
              <p class="sw-muted">
                1. 准备本人的有效学生证。可遮挡姓名、照片等无关信息，保留学校、学号和有效期。
              </p>
              <p class="sw-muted">
                2. 获取拍摄码后，将手写拍摄码与学生证放在同一画面拍照。请勿上传截图或他人的证件。
              </p>
              <p class="sw-muted">
                3. 证件照片仅供授权管理员核验，不公开、不发送至外部内容审核服务。审核结束 7 天后删除，待审最长保留
                14 天。
              </p>
              <p class="sw-muted">
                4. 学号只保留不可逆的学校身份指纹，不保存明文学号或姓名。认证最长有效 12 个月。
              </p>
            </div>

            <el-checkbox v-model="consent" class="sw-verify__consent">
              我已了解用途与保留期限，自愿提交学生证进行身份认证
            </el-checkbox>

            <el-button :disabled="!consent" @click="newChallenge">
              {{ challenge ? '更新拍摄码' : '获取拍摄码' }}
            </el-button>

            <template v-if="challenge">
              <p class="sw-verify__code">{{ challenge.code }}</p>
              <p class="sw-muted">10 分钟内拍摄并提交；更新拍摄码后需重新拍照。</p>

              <el-form label-width="110px" class="sw-verify__form">
                <el-form-item label="学号">
                  <el-input v-model="studentId" maxlength="32" placeholder="输入学生证上的学号" />
                </el-form-item>
                <el-form-item label="证件有效期">
                  <el-input v-model="cardValidUntil" placeholder="如 2027-06-30，证件未标明可留空" />
                </el-form-item>
                <el-form-item label="同框照片">
                  <el-upload
                    :auto-upload="false"
                    :limit="1"
                    list-type="picture-card"
                    accept="image/*"
                    :on-change="handleChange"
                    :on-remove="handleRemove"
                  >
                    <el-icon><Camera /></el-icon>
                  </el-upload>
                </el-form-item>
              </el-form>

              <el-button
                type="primary"
                :loading="submitting"
                :disabled="!files.length || !studentId.trim() || !consent"
                @click="submit"
              >
                {{ submitting ? '正在安全提交…' : '提交人工审核' }}
              </el-button>
            </template>
          </template>
        </template>
      </div>
    </section>

    <el-alert type="warning" :closable="false">
      <template #title>
        <span class="sw-verify__alert">
          <el-icon><WarningFilled /></el-icon>
          认证期间请勿向任何人提供找回码或登录密码。
        </span>
      </template>
    </el-alert>
  </div>
</template>

<style scoped>
.sw-verify {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-verify__card {
  padding: var(--sw-space-5);
}

.sw-verify__body {
  margin-top: var(--sw-space-4);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sw-space-3);
  min-height: 120px;
}

.sw-verify__status {
  align-self: flex-start;
}

.sw-verify__reason {
  margin: 0;
  color: var(--sw-danger);
  font-size: var(--sw-text-sm);
}

.sw-verify__tips {
  width: 100%;
  padding: var(--sw-space-3) var(--sw-space-4);
  background: var(--sw-surface-muted);
  border-radius: var(--sw-radius-sm);
}

.sw-verify__tips-title {
  margin: 0 0 var(--sw-space-1);
  font-size: var(--sw-text-sm);
  font-weight: 600;
  color: var(--sw-text);
}

.sw-verify__tips p {
  margin: 0 0 var(--sw-space-1);
  line-height: 1.8;
}

.sw-verify__consent {
  margin-top: var(--sw-space-2);
  height: auto;
  white-space: normal;
}

.sw-verify__form {
  width: 100%;
  margin-top: var(--sw-space-4);
}

.sw-verify__code {
  margin: var(--sw-space-3) 0 0;
  font-size: var(--sw-text-2xl);
  font-weight: 700;
  letter-spacing: 8px;
  color: var(--sw-primary-text);
}

.sw-verify__alert {
  display: inline-flex;
  align-items: center;
  gap: var(--sw-space-2);
}
</style>
