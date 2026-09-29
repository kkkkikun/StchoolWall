<template>
  <view class="page-hot-users" :class="themeClass">
    <view class="header">
      <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />
      <view class="header-row">
        <text class="back-btn" @tap="goBack">‹</text>
        <text class="header-title">热门用户榜</text>
        <view class="header-right" />
      </view>
    </view>

    <view v-if="loading" class="state-box"><text class="state-text">加载中…</text></view>
    <view v-else-if="!users.length" class="state-box">
      <text class="state-emoji">👥</text>
      <text class="state-text">暂无热门用户</text>
    </view>
    <view v-else class="user-list">
      <view v-for="(u, i) in users" :key="u.id" class="user-row" @tap="goProfile(u.id)">
        <view class="rank" :class="{ top: i < 3 }">{{ i + 1 }}</view>
        <view v-if="u.avatar_url" class="avatar"><image :src="u.avatar_url" mode="aspectFill" /></view>
        <view v-else class="avatar" :style="{ background: colorOf(u.nickname) }">
          <text>{{ (u.nickname || '?').slice(0, 1) }}</text>
        </view>
        <view class="main">
          <text class="name">{{ u.nickname }}</text>
          <text class="heat">🔥 {{ fmtHeat(u.heat) }}</text>
        </view>
        <text class="arrow">›</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTheme } from '@/utils/theme'
import { onLoad } from '@dcloudio/uni-app'
import { getHotRanking, type HotUser } from '@/api/profile'

const { themeClass } = useTheme()

const statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0
const users = ref<HotUser[]>([])
const loading = ref(true)

const COLORS = ['#f8c8b8', '#e8d5f5', '#d5e8f5', '#d5f0d5', '#fbe3b5', '#f5d0d8']
const colorOf = (s: string) => {
  let h = 0
  for (let i = 0; i < (s || '').length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return COLORS[h % COLORS.length]
}
const fmtHeat = (n: number) => {
  if (n < 1000) return String(n)
  const k = n / 1000
  return `${k >= 100 ? Math.round(k) : k.toFixed(1).replace(/\.0$/, '')}k`
}

onLoad(async () => {
  try {
    const data = await getHotRanking(50)
    users.value = data.items
  } catch {
    /* 忽略 */
  } finally {
    loading.value = false
  }
})

const goProfile = (id: string) => uni.navigateTo({ url: `/pages/profile/index?id=${id}` })
const goBack = () => uni.navigateBack({ fail: () => uni.reLaunch({ url: '/pages/message/index' }) })
</script>

<style scoped>
.page-hot-users { min-height: 100vh; background-color: var(--bg-page); }

.header { background-color: var(--bg-page); border-bottom: 1rpx solid var(--border-light); }
.header-row { height: 88rpx; display: flex; align-items: center; padding: 0 24rpx; }
.back-btn { font-size: 56rpx; color: var(--text-1); line-height: 1; padding: 0 12rpx; }
.header-title { flex: 1; text-align: center; font-size: 32rpx; font-weight: 700; color: var(--text-1); }
.header-right { width: 80rpx; }

.state-box { padding-top: 200rpx; display: flex; flex-direction: column; align-items: center; }
.state-emoji { font-size: 96rpx; margin-bottom: 24rpx; opacity: 0.5; }
.state-text { font-size: 28rpx; color: var(--text-3); }

.user-list { padding: 20rpx 24rpx; }
.user-row { display: flex; align-items: center; background: var(--bg-card); border-radius: var(--radius-card); padding: 22rpx; margin-bottom: 16rpx; }
.rank { width: 48rpx; height: 48rpx; border-radius: 50%; background: var(--bg-card-2); color: var(--text-3); display: flex; align-items: center; justify-content: center; font-size: 24rpx; font-weight: bold; margin-right: 20rpx; }
.rank.top { background: var(--primary); color: var(--text-inverse); }
.avatar { width: 76rpx; height: 76rpx; border-radius: 50%; overflow: hidden; display: flex; align-items: center; justify-content: center; font-size: 34rpx; color: var(--text-inverse); font-weight: bold; margin-right: 20rpx; }
.avatar image { width: 100%; height: 100%; }
.main { flex: 1; min-width: 0; }
.name { font-size: 28rpx; font-weight: 600; color: var(--text-1); }
.heat { display: block; font-size: 24rpx; color: var(--primary-strong); margin-top: 6rpx; }
.arrow { font-size: 40rpx; color: var(--text-4); }
</style>
