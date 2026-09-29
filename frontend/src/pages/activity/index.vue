<template>
  <view class="page-activity" :class="themeClass">
    <view class="header">
      <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />
      <view class="header-row">
        <text class="back-btn" @tap="goBack">‹</text>
        <text class="header-title">活动详情</text>
        <view class="header-right" />
      </view>
    </view>

    <view v-if="loading" class="state-box">
      <text class="state-text">加载中…</text>
    </view>
    <view v-else-if="!activity" class="state-box">
      <text class="state-emoji">📭</text>
      <text class="state-text">活动不存在或已下架</text>
    </view>
    <view v-else class="content">
      <image v-if="activity.image_url" class="cover" :src="activity.image_url" mode="aspectFill" />
      <view class="card">
        <view class="tag">📌 校园活动</view>
        <text class="title">{{ activity.title }}</text>
        <text v-if="activity.summary" class="summary">{{ activity.summary }}</text>

        <view v-if="activity.location" class="meta-row">
          <text class="meta-icon">📍</text>
          <text class="meta-text">{{ activity.location }}</text>
        </view>
        <view v-if="activity.start_at || activity.end_at" class="meta-row">
          <text class="meta-icon">🕐</text>
          <text class="meta-text">{{ timeText }}</text>
        </view>

        <view class="divider" />
        <text class="body">{{ activity.content }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTheme } from '@/utils/theme'
import { onLoad } from '@dcloudio/uni-app'
import { getActivity, type ActivityDetail } from '@/api/activity'

const { themeClass } = useTheme()

const statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0
const loading = ref(true)
const activity = ref<ActivityDetail | null>(null)

const pad = (n: number) => String(n).padStart(2, '0')
const fmt = (iso: string) => {
  const d = new Date(iso)
  if (!d.getTime()) return ''
  return `${d.getMonth() + 1}月${d.getDate()}日 ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const timeText = () => {
  const a = activity.value
  if (!a) return ''
  const s = a.start_at ? fmt(a.start_at) : ''
  const e = a.end_at ? fmt(a.end_at) : ''
  if (s && e) return `${s} - ${e}`
  return s || e || ''
}

onLoad(async (query) => {
  const id = Number(query?.id)
  if (!id) {
    loading.value = false
    return
  }
  try {
    activity.value = await getActivity(id)
  } catch {
    /* 按不存在展示 */
  } finally {
    loading.value = false
  }
})

const goBack = () => uni.navigateBack({ fail: () => uni.reLaunch({ url: '/pages/index/index' }) })
</script>

<style scoped>
.page-activity { min-height: 100vh; background-color: var(--bg-page); }

.header { background-color: var(--bg-page); border-bottom: 1rpx solid var(--border-light); }
.header-row { height: 88rpx; display: flex; align-items: center; padding: 0 24rpx; }
.back-btn { font-size: 56rpx; color: var(--text-1); line-height: 1; padding: 0 12rpx; }
.header-title { flex: 1; text-align: center; font-size: 32rpx; font-weight: 700; color: var(--text-1); }
.header-right { width: 80rpx; }

.state-box { padding-top: 220rpx; display: flex; flex-direction: column; align-items: center; }
.state-emoji { font-size: 96rpx; margin-bottom: 24rpx; opacity: 0.5; }
.state-text { font-size: 28rpx; color: var(--text-3); }

.content { padding: 24rpx; }
.cover { width: 100%; height: 340rpx; border-radius: var(--radius-card); background: var(--primary-soft); }
.card {
  background: var(--bg-card);
  border-radius: var(--radius-card);
  margin-top: 24rpx;
  padding: 30rpx;
}
.tag { display: inline-flex; align-items: center; font-size: 22rpx; color: var(--primary-strong); background: var(--primary-soft); border: 1rpx solid var(--primary); padding: 6rpx 16rpx; border-radius: 999rpx; }
.title { display: block; font-size: 38rpx; font-weight: bold; color: var(--text-1); line-height: 1.4; margin-top: 20rpx; }
.summary { display: block; font-size: 26rpx; color: var(--text-3); line-height: 1.6; margin-top: 14rpx; }
.meta-row { display: flex; align-items: flex-start; margin-top: 16rpx; }
.meta-icon { font-size: 26rpx; margin-right: 10rpx; }
.meta-text { font-size: 26rpx; color: var(--text-2); line-height: 1.5; }
.divider { height: 1rpx; background: var(--bg-card-2); margin: 26rpx 0; }
.body { display: block; font-size: 29rpx; color: var(--text-1); line-height: 1.8; white-space: pre-wrap; }
</style>
