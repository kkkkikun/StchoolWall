<template>
  <view class="page-activity" :class="themeClass">
    <CustomNavBar show-back title="活动详情" />

    <view v-if="loading" class="state-box">
      <text class="state-text">加载中…</text>
    </view>
    <view v-else-if="!activity" class="state-box">
      <image class="state-emoji" :src="ICONS['state-inbox']" mode="aspectFit" />
      <text class="state-text">活动不存在或已下架</text>
    </view>
    <view v-else class="content">
      <image v-if="activity.image_url" class="cover" :src="activity.image_url" mode="aspectFill" />
      <view class="card">
        <view class="tag">
          <image class="tag-icon" :src="ICON_TONES['pin']['primary']" mode="aspectFit" />
          <text>校园活动</text>
        </view>
        <text class="title">{{ activity.title }}</text>
        <text v-if="activity.summary" class="summary">{{ activity.summary }}</text>

        <view v-if="activity.location" class="meta-row">
          <image class="meta-icon" :src="ICONS['location']" mode="aspectFit" />
          <text class="meta-text">{{ activity.location }}</text>
        </view>
        <view v-if="activity.start_at || activity.end_at" class="meta-row">
          <image class="meta-icon" :src="ICONS['clock']" mode="aspectFit" />
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
import CustomNavBar from '@/components/custom-nav-bar.vue'
import { getActivity, type ActivityDetail } from '@/api/activity'
import { ICONS, ICON_TONES } from '@/utils/icons'

const { themeClass } = useTheme()

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

.state-box { padding-top: 220rpx; display: flex; flex-direction: column; align-items: center; }
.state-emoji { width: 96rpx; height: 96rpx; margin-bottom: 24rpx; opacity: 0.5; }
.state-text { font-size: 28rpx; color: var(--text-3); }

.content { padding: 24rpx; }
.cover { width: 100%; height: 340rpx; border-radius: var(--radius-card); background: var(--primary-soft); }
.card {
  background: var(--bg-card);
  border-radius: var(--radius-card);
  margin-top: 24rpx;
  padding: 30rpx;
}
.tag-icon { width: 22rpx; height: 22rpx; margin-right: 6rpx; flex-shrink: 0; }
.tag { display: inline-flex; align-items: center; font-size: 22rpx; color: var(--primary-text); background: var(--primary-soft); border: 1rpx solid var(--primary); padding: 6rpx 16rpx; border-radius: 999rpx; }
.title { display: block; font-size: 38rpx; font-weight: bold; color: var(--text-1); line-height: 1.4; margin-top: 20rpx; }
.summary { display: block; font-size: 26rpx; color: var(--text-3); line-height: 1.6; margin-top: 14rpx; }
.meta-row { display: flex; align-items: flex-start; margin-top: 16rpx; }
.meta-icon { width: 26rpx; height: 26rpx; margin-right: 10rpx; flex-shrink: 0; }
.meta-text { font-size: 26rpx; color: var(--text-2); line-height: 1.5; }
.divider { height: 1rpx; background: var(--bg-card-2); margin: 26rpx 0; }
.body { display: block; font-size: 29rpx; color: var(--text-1); line-height: 1.8; white-space: pre-wrap; }
</style>
