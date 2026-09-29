<template>
  <view class="page-announcement" :class="themeClass">
    <view class="header">
      <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />
      <view class="header-row">
        <text class="back-btn" @tap="goBack">‹</text>
        <text class="header-title">公告详情</text>
        <view class="header-right" />
      </view>
    </view>

    <view v-if="loading" class="state-box">
      <text class="state-text">加载中…</text>
    </view>
    <view v-else-if="!detail" class="state-box">
      <text class="state-emoji">📭</text>
      <text class="state-text">公告不存在或已删除</text>
    </view>
    <view v-else class="detail-card">
      <view class="badge">📢 系统公告</view>
      <text class="title">{{ detail.payload?.title || '系统公告' }}</text>
      <text class="time">{{ fmtTime(detail.created_at) }}</text>
      <view class="divider" />
      <text class="content">{{ detail.payload?.content || '' }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTheme } from '@/utils/theme'
import { onLoad } from '@dcloudio/uni-app'
import { getNotificationDetail, readNotification, type NotificationItem } from '@/api/notification'

const { themeClass } = useTheme()

const statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0
const loading = ref(true)
const detail = ref<NotificationItem | null>(null)

const pad = (n: number) => String(n).padStart(2, '0')
const fmtTime = (iso: string) => {
  const d = new Date(iso)
  if (!d.getTime()) return ''
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onLoad(async (query) => {
  const id = Number(query?.id)
  if (!id) {
    loading.value = false
    return
  }
  try {
    detail.value = await getNotificationDetail(id)
    if (!detail.value.is_read) {
      await readNotification(id)
      detail.value.is_read = true
    }
  } catch {
    /* 加载失败按不存在展示 */
  } finally {
    loading.value = false
  }
})

const goBack = () => uni.navigateBack({ fail: () => uni.reLaunch({ url: '/pages/message/index' }) })
</script>

<style scoped>
.page-announcement { min-height: 100vh; background-color: var(--bg-page); }

.header { background-color: var(--bg-page); border-bottom: 1rpx solid var(--border-light); }
.header-row { height: 88rpx; display: flex; align-items: center; padding: 0 24rpx; }
.back-btn { font-size: 56rpx; color: var(--text-1); line-height: 1; padding: 0 12rpx; }
.header-title { flex: 1; text-align: center; font-size: 32rpx; font-weight: 700; color: var(--text-1); }
.header-right { width: 80rpx; }

.state-box { padding-top: 220rpx; display: flex; flex-direction: column; align-items: center; }
.state-emoji { font-size: 96rpx; margin-bottom: 24rpx; opacity: 0.5; }
.state-text { font-size: 28rpx; color: var(--text-3); }

.detail-card {
  background: var(--bg-card);
  border-radius: var(--radius-card);
  margin: 24rpx;
  padding: 32rpx 30rpx 40rpx;
}
.badge { display: inline-flex; align-items: center; font-size: 22rpx; color: var(--primary-strong); background: var(--primary-soft); border: 1rpx solid var(--primary); padding: 6rpx 16rpx; border-radius: 999rpx; }
.title { display: block; font-size: 36rpx; font-weight: bold; color: var(--text-1); line-height: 1.5; margin-top: 22rpx; }
.time { display: block; font-size: 24rpx; color: var(--text-3); margin-top: 16rpx; }
.divider { height: 1rpx; background: var(--bg-card-2); margin: 26rpx 0; }
.content { display: block; font-size: 29rpx; color: var(--text-1); line-height: 1.8; white-space: pre-wrap; }
</style>
