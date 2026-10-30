<template>
  <view class="page" :class="themeClass">
    <text class="title">申诉与处理记录</text>
    <text class="tip">仅可申诉自己的待审或受限制内容。请描述理由，勿填写密码、找回码、姓名或完整学号。</text>
    <picker :range="labels" :value="kindIndex" @change="kindIndex = Number($event.detail.value)">
      <view class="field">对象：{{ labels[kindIndex] }} ›</view>
    </picker>
    <input v-model="entityId" class="field" :maxlength="64" placeholder="输入帖子 / 评论 / 组局 / 认证申请编号" placeholder-class="ph" />
    <textarea v-model="reason" class="field reason" :maxlength="1000" placeholder="申诉理由（5–1000字）" placeholder-class="ph" />
    <button :disabled="saving" @tap="submit">{{ saving ? '提交中…' : '提交申诉' }}</button>
    <view class="records-title"><text>我的申诉</text><text @tap="load(1)">刷新</text></view>
    <view v-for="item in items" :key="item.id" class="record">
      <text>{{ typeLabels[item.entity_type] }} · {{ statusLabels[item.status] }}</text>
      <text class="tip">编号 {{ item.entity_id }}</text>
      <text>{{ item.reason }}</text>
      <text v-if="item.decision_reason" class="tip">处理说明：{{ item.decision_reason }}</text>
    </view>
    <text v-if="!items.length" class="tip">暂无申诉记录</text>
    <button v-if="canLoadMore" @tap="load(page + 1)">加载更多</button>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { useTheme } from '@/utils/theme'
import { getAppeals, submitAppeal, type Appeal, type AppealType } from '@/api/appeals'

const { themeClass } = useTheme()
const kinds: AppealType[] = ['post', 'comment', 'party', 'verification']
const labels = ['帖子', '评论', '组局', '学生证认证']
const typeLabels = { post: '帖子', comment: '评论', party: '组局', verification: '学生证认证' }
const statusLabels = { pending: '待处理', accepted: '申诉已受理', rejected: '申诉未通过' }
const kindIndex = ref(0)
const entityId = ref('')
const reason = ref('')
const items = ref<Appeal[]>([])
const page = ref(1)
const saving = ref(false)
const canLoadMore = ref(false)
const errorToast = (error: unknown) => uni.showToast({ title: (error as Error).message || '操作失败', icon: 'none' })
const load = async (newPage = 1) => {
  try {
    const data = await getAppeals(newPage)
    items.value = newPage === 1 ? data.items : [...items.value, ...data.items]
    page.value = newPage
    canLoadMore.value = data.items.length === 20
  } catch (error) { errorToast(error) }
}
const submit = async () => {
  if (!entityId.value.trim() || reason.value.trim().length < 5) {
    return errorToast(new Error('请填写对象编号和至少 5 字的申诉理由'))
  }
  if (saving.value) return
  saving.value = true
  try {
    await submitAppeal(kinds[kindIndex.value], entityId.value.trim(), reason.value.trim())
    reason.value = ''
    uni.showToast({ title: '申诉已提交', icon: 'success' })
    await load()
  } catch (error) { errorToast(error) }
  finally { saving.value = false }
}
onLoad((options) => {
  const index = kinds.indexOf(options?.type as AppealType)
  if (index >= 0) kindIndex.value = index
  entityId.value = options?.id || ''
  load()
})
</script>

<style scoped>
.page { min-height: 100vh; background: var(--bg-page); padding: 32rpx; box-sizing: border-box; }
.title { display: block; font-size: 34rpx; font-weight: 600; margin-bottom: 20rpx; }
.tip { display: block; color: var(--text-2); font-size: 24rpx; line-height: 1.8; }
.field { margin: 24rpx 0; padding: 24rpx; box-sizing: border-box; background: var(--bg-card-2); border-radius: 12rpx; font-size: 26rpx; }
.reason { width: 100%; height: 220rpx; }
button { font-size: 28rpx; background: var(--primary); color: var(--text-inverse); }
.records-title { display: flex; justify-content: space-between; margin: 44rpx 0 20rpx; font-size: 28rpx; }
.record { border-bottom: 1rpx solid var(--border-light); padding: 24rpx 0; }
.record > text { display: block; margin-bottom: 12rpx; font-size: 26rpx; }
</style>
