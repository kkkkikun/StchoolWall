<template>
  <view class="container" :class="themeClass">
    <view class="header">
      <text class="title">学生证认证</text>
      <text class="subtitle">通过人工核对学生证，开通校园发帖与互动</text>
    </view>
    <view class="form">
      <text v-if="loading" class="tips-text">正在读取申请状态…</text>
      <template v-else>
        <text class="status">{{ statusText }}</text>
        <text v-if="record?.review_reason" class="tips-text">{{ record.review_reason }}</text>
        <button v-if="record && ['rejected', 'revoked', 'expired'].includes(record.status)" @tap="goAppeal">对认证结果提出申诉</button>
        <text v-if="record?.verified_until"  class="tips-text">认证有效期至 {{ formatDate(record.verified_until) }}</text>
        <text v-if="record?.status === 'pending'" class="tips-text">请耐心等待人工审核。超过 14 天未处理将自动过期，可重新提交。</text>
        <template v-if="canSubmit">
          <text class="label">学校：{{ challenge?.school_name || schoolName }}</text>
          <view class="tips">
            <text class="tips-title">请先阅读拍摄与隐私说明</text>
            <text class="tips-text">1. 准备本人的有效学生证。可遮挡姓名、照片等无关信息，保留学校、学号和有效期。</text>
            <text class="tips-text">2. 获取拍摄码后，将手写拍摄码与学生证放在同一画面拍照。请勿上传截图或他人的证件。</text>
            <text class="tips-text">3. 证件照片仅供授权管理员核验，不公开、不发送至外部内容审核服务。审核结束 7 天后删除，待审最长保留 14 天。</text>
            <text class="tips-text">4. 学号只保留不可逆的学校身份指纹，不保存明文学号或姓名。认证最长有效 12 个月。</text>
          </view>
          <view class="consent" @tap="consent = !consent">
            <checkbox :checked="consent" />
            <text>我已了解用途与保留期限，自愿提交学生证进行身份认证</text>
          </view>
          <button :disabled="!consent || submitting" @tap="newChallenge">获取 / 更新拍摄码</button>
          <template v-if="challenge">
            <text class="challenge">{{ challenge.code }}</text>
            <text class="tips-text">10 分钟内拍摄并提交；更新拍摄码后需重新拍照。</text>
            <view class="form-item">
              <text class="label">学号</text>
              <input v-model="studentId" class="input" :maxlength="32" placeholder="输入学生证上的学号" placeholder-class="ph" />
            </view>
            <view class="form-item">
              <text class="label">学生证有效期（证件标明时请填写）</text>
              <picker mode="date" :value="validUntil" @change="validUntil = $event.detail.value">
                <view class="input">{{ validUntil || '选择有效期' }}</view>
              </picker>
            </view>
            <button @tap="takePhoto">{{ photoPath ? '重新拍摄' : '拍摄同框照片' }}</button>
            <image v-if="photoPath" class="proof-preview" :src="photoPath" mode="aspectFit" />
            <button class="submit-btn" :disabled="submitting || !photoPath || !studentId || !consent" @tap="submit">
              {{ submitting ? '正在安全提交…' : '提交人工审核' }}
            </button>
          </template>
        </template>
        <text v-if="!enabled" class="tips-text">学生证认证暂未开放，请稍后再试。</text>
      </template>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onShow, onUnload } from '@dcloudio/uni-app'
import { useTheme } from '@/utils/theme'
import { getVerification, createVerificationChallenge, submitStudentCard,
  type VerificationRecord, type VerificationChallenge } from '@/api/verification'
import { tokenStorage } from '@/utils/storage'

const { themeClass } = useTheme()
const record = ref<VerificationRecord | null>(null)
const challenge = ref<VerificationChallenge | null>(null)
const enabled = ref(false)
const schoolName = ref('本校')
const loading = ref(true)
const submitting = ref(false)
const consent = ref(false)
const studentId = ref('')
const validUntil = ref('')
const photoPath = ref('')
const canSubmit = computed(() => enabled.value && !['pending', 'approved'].includes(record.value?.status || ''))
const statusText = computed(() => ({
  draft: '请完成认证申请', pending: '申请审核中', approved: '已认证',
  rejected: '申请未通过，可重新提交', expired: '认证或申请已过期，请重新提交',
  revoked: '认证已撤销，如有异议请联系支持',
}[record.value?.status || 'draft']))
const goAppeal = () => uni.navigateTo({ url: '/pages/appeals/index?type=verification&id=' + encodeURIComponent(record.value?.id || '') })
const formatDate = (value: string) => value.slice(0, 10)
const showError = (error: unknown) => uni.showToast({ title: (error as Error).message || '操作失败', icon: 'none' })

const load = async () => {
  loading.value = true
  try {
    const result = await getVerification()
    record.value = result.verification
    enabled.value = result.enabled
    schoolName.value = result.school_name
  } catch (error) { showError(error) }
  finally { loading.value = false }
}
const newChallenge = async () => {
  if (!consent.value) return
  try {
    challenge.value = await createVerificationChallenge()
    photoPath.value = ''
  } catch (error) { showError(error) }
}
const takePhoto = () => uni.chooseImage({
  count: 1, sizeType: ['compressed'], sourceType: ['camera'],
  success: (result) => { photoPath.value = result.tempFilePaths[0] || '' },
})
const submit = async () => {
  if (submitting.value || !challenge.value || !consent.value || !photoPath.value) return
  if (new Date(challenge.value.expires_at).getTime() <= Date.now()) {
    return showError(new Error('拍摄码已过期，请重新获取并拍照'))
  }
  submitting.value = true
  try {
    record.value = await submitStudentCard(challenge.value, studentId.value.trim(), photoPath.value, validUntil.value)
    challenge.value = null
    photoPath.value = ''
    studentId.value = ''
    validUntil.value = ''
    uni.showToast({ title: '申请已提交', icon: 'success' })
  } catch (error) { showError(error) }
  finally { submitting.value = false }
}
onShow(() => {
  if (!tokenStorage.isLoggedIn()) {
    loading.value = false
    showError(new Error('请先登录'))
    return
  }
  load()
})
onUnload(() => { photoPath.value = ''; studentId.value = ''; challenge.value = null })
</script>

<style scoped>
.container { min-height: 100vh; background: var(--bg-page); padding-bottom: 60rpx; }
.header { background: var(--primary-fill-gradient); padding: 50rpx 32rpx; color: var(--text-inverse); }
.title { display: block; font-size: 42rpx; font-weight: 600; margin-bottom: 16rpx; }
.subtitle { font-size: 26rpx; }
.form { padding: 32rpx; }
.status { display: block; font-size: 32rpx; font-weight: 600; margin-bottom: 24rpx; }
.form-item { margin-top: 28rpx; }
.label { display: block; margin-bottom: 12rpx; color: var(--text-2); font-size: 28rpx; }
.input { box-sizing: border-box; padding: 22rpx; background: var(--bg-card-2); border-radius: 12rpx; font-size: 28rpx; }
.tips { padding: 24rpx; background: var(--bg-card-2); border-radius: 12rpx; }
.tips-title, .tips-text { display: block; font-size: 25rpx; color: var(--text-2); line-height: 1.9; }
.tips-title { font-weight: 600; }
.consent { display: flex; gap: 12rpx; align-items: flex-start; margin: 28rpx 0; font-size: 25rpx; color: var(--text-2); }
.challenge { display: block; text-align: center; font-size: 64rpx; font-weight: bold; letter-spacing: 12rpx; margin: 28rpx 0; color: var(--primary-text); }
button { margin: 24rpx 0; font-size: 28rpx; border-radius: 40rpx; }
.submit-btn { background: var(--primary-fill); color: var(--text-inverse); }
.proof-preview { width: 100%; height: 440rpx; }
</style>
