<template>
  <view class="page-group">
    <!-- 0. 标题栏（沉浸式：预留状态栏，与消息页同款） -->
    <view class="page-header">
      <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />
      <text class="page-title">组局</text>
    </view>

    <!-- 1. 累计攒局人数 -->
    <view class="header-stats">
      <text class="stats-text">已攒 <text class="highlight-num">{{ totalMembers }}</text> 人</text>
      <text v-if="mode === 'mine'" class="back-all" @tap="setMode('all')">返回全部 ›</text>
    </view>

    <!-- 2. 双核动作卡 -->
    <view class="action-cards">
      <view class="action-card card-blue" @tap="setMode('mine')">
        <text class="card-title">我加入的局</text>
        <text class="card-icon">👥</text>
      </view>
      <view class="action-card card-orange" @tap="goCreate">
        <text class="card-title">发起攒局</text>
        <text class="card-icon">✚</text>
      </view>
    </view>

    <!-- 3. 分类筛选（mode=all 时显示） -->
    <view v-if="mode === 'all'" class="filter-grid">
      <view
        v-for="c in categories"
        :key="c.id"
        class="tag-pill"
        :class="{ active: activeFilter === c.id }"
        @tap="onFilter(c)"
      >
        <text class="tag-icon">{{ c.icon }}</text>
        <text class="tag-name">{{ c.name }}</text>
      </view>
    </view>

    <!-- 4. 组局列表 -->
    <view class="party-list">
      <view v-if="loading && parties.length === 0" class="tip"><text>加载中…</text></view>
      <view v-else-if="parties.length === 0" class="tip"><text>{{ mode === 'mine' ? '还没有加入任何局' : '暂无组局，去发起一个吧' }}</text></view>

      <view v-for="p in parties" :key="p.id" class="party-card">
        <view class="type-badge" :class="p.type === 'group' ? 'bg-red' : 'bg-orange'">
          <text>{{ p.type === 'group' ? '组' : '拼' }}</text>
        </view>
        <view class="card-main">
          <text class="party-title">{{ p.title }}</text>
          <view class="owner-info">
            <view class="owner-avatar" :style="{ background: colorOf(p.user.nickname) }">
              <text>{{ (p.user.nickname || '?').slice(0, 1) }}</text>
            </view>
            <text class="owner-name">{{ p.user.nickname }}</text>
            <text class="divider">·</text>
            <text class="post-date">{{ timeShort(p.created_at) }}</text>
            <text v-if="p.location" class="divider">·</text>
            <text v-if="p.location" class="post-date">📍{{ p.location }}</text>
          </view>
          <view class="progress-section">
            <view class="progress-bar-bg">
              <view class="progress-bar-active" :style="{ width: progressOf(p) + '%' }" />
            </view>
            <view class="progress-meta">
              <text class="count-text"><text class="current-num">{{ p.joined_count }}</text>/{{ p.total }}人</text>
              <view
                class="join-btn"
                :class="{ joined: p.is_joined, full: !p.is_joined && p.status === 2 }"
                @tap="onJoin(p)"
              >
                <text>{{ p.is_joined ? '退出' : (p.status === 2 ? '已满' : '报名') }}</text>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>

    <TabBar :current="1" />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import TabBar from '@/components/tab-bar.vue'
import { listParties, partiesSummary, myParties, joinParty, leaveParty, type PartyItem } from '@/api/party'
import { tokenStorage } from '@/utils/storage'

// 沉浸式标题栏：预留状态栏高度（H5 下为 0）
const statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0

// 分类筛选（第 1 项=有空位=only_vacant，其余=分类）
const categories = [
  { id: 'vacant', icon: '⭐', name: '有空位' },
  { id: '自习', icon: '📖', name: '自习' },
  { id: '电影', icon: '🎬', name: '电影' },
  { id: '聚餐', icon: '🍴', name: '聚餐' },
  { id: '拼车', icon: '🚗', name: '拼车' },
  { id: '拼单', icon: '🛍️', name: '拼单' },
  { id: '运动', icon: '🏃', name: '运动' },
  { id: '游戏', icon: '🎮', name: '游戏' },
  { id: '旅行', icon: '🌴', name: '旅行' },
  { id: '其他', icon: '⚙️', name: '其他' },
] as const

const totalMembers = ref(0)
const parties = ref<PartyItem[]>([])
const loading = ref(false)
const mode = ref<'all' | 'mine'>('all')
const activeFilter = ref<string | null>(null)

const COLORS = ['#ffd591', '#adc6ff', '#b7eb8f', '#ffa39e', '#d3adf7', '#87e8de', '#ffccc7']
const colorOf = (s: string) => {
  let h = 0
  for (let i = 0; i < (s || '').length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return COLORS[h % COLORS.length]
}
const timeShort = (t: string) => {
  const ts = new Date(t).getTime()
  if (!ts) return ''
  const d = new Date(t)
  return `${d.getMonth() + 1}-${d.getDate()}`
}
const progressOf = (p: PartyItem) => Math.min(100, Math.round(((p.joined_count || 0) / p.total) * 100))

const loadSummary = async () => {
  try {
    const s = await partiesSummary()
    totalMembers.value = s.total_members
  } catch { /* 忽略 */ }
}

const loadList = async () => {
  loading.value = true
  try {
    if (mode.value === 'mine') {
      if (!tokenStorage.isLoggedIn()) {
        parties.value = []
        uni.showToast({ title: '请先登录', icon: 'none' })
        return
      }
      const res = await myParties()
      parties.value = res.items
    } else {
      const params: { category?: string; only_vacant?: boolean } = {}
      if (activeFilter.value === 'vacant') params.only_vacant = true
      else if (activeFilter.value) params.category = activeFilter.value
      const res = await listParties(params)
      parties.value = res.items
    }
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

onShow(() => {
  loadSummary()
  loadList()
})

const setMode = (m: 'all' | 'mine') => {
  if (mode.value === m) return
  mode.value = m
  if (m === 'all') activeFilter.value = null
  loadList()
}

const onFilter = (c: { id: string }) => {
  activeFilter.value = activeFilter.value === c.id ? null : c.id
  mode.value = 'all'
  loadList()
}

const onJoin = async (p: PartyItem) => {
  if (!tokenStorage.isLoggedIn()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (!p.is_joined && p.status === 2) {
    uni.showToast({ title: '已满员', icon: 'none' })
    return
  }
  // 乐观更新
  const wasJoined = p.is_joined
  p.is_joined = !wasJoined
  p.joined_count += wasJoined ? -1 : 1
  try {
    if (wasJoined) {
      await leaveParty(p.id)
    } else {
      const r = await joinParty(p.id)
      if (r.full) {
        p.is_joined = false
        p.joined_count -= 1
        uni.showToast({ title: '手慢了，已满员', icon: 'none' })
      }
    }
    await loadSummary()
  } catch (e) {
    // 回滚
    p.is_joined = wasJoined
    p.joined_count += wasJoined ? 1 : -1
    uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' })
  }
}

const goCreate = () => {
  if (!tokenStorage.isLoggedIn()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  uni.navigateTo({ url: '/pages/party-create/index' })
}
</script>

<style scoped>
.page-group { background-color: var(--bg-group); padding: 20rpx 24rpx 40rpx; min-height: 100vh; }

/* 0. 标题栏（全宽出血：负 margin 抵消页面根 padding，与消息页同款） */
.page-header { background-color: var(--brand-red); margin: -20rpx -24rpx 0; }
.page-title { display: block; padding: 30rpx 40rpx; text-align: center; color: #ffffff; font-size: 34rpx; font-weight: bold; letter-spacing: 2rpx; }

.header-stats { display: flex; align-items: center; justify-content: space-between; font-size: 26rpx; color: #666; padding: 10rpx; }
.highlight-num { color: var(--brand-red-dark); font-weight: bold; font-size: 32rpx; margin: 0 4rpx; }
.back-all { color: var(--brand-red); font-size: 24rpx; }

.action-cards { display: flex; justify-content: space-between; margin-top: 16rpx; }
.action-card { width: 48%; height: 120rpx; border-radius: 20rpx; padding: 0 24rpx; display: flex; align-items: center; justify-content: space-between; color: #fff; }
.card-blue { background: linear-gradient(135deg, #69c0ff, #1890ff); }
.card-orange { background: linear-gradient(135deg, #ff9c6e, #ff4d4f); }
.card-title { font-size: 30rpx; font-weight: bold; }
.card-icon { font-size: 44rpx; }

.filter-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14rpx; margin-top: 24rpx; padding: 10rpx 0; }
.tag-pill { background-color: #fff; border: 1rpx solid #f0f0f0; border-radius: 12rpx; padding: 12rpx 4rpx; display: flex; align-items: center; justify-content: center; font-size: 20rpx; color: #777; white-space: nowrap; }
.tag-pill.active { border-color: var(--brand-red-dark); color: var(--brand-red-dark); background-color: #fff1f0; }
.tag-icon { margin-right: 4rpx; font-size: 22rpx; }

.tip { text-align: center; color: var(--text-3); font-size: 26rpx; padding: 80rpx 0; }

.party-list { margin-top: 16rpx; }
.party-card { background-color: #fff; border-radius: var(--radius-card); margin-bottom: 24rpx; display: flex; overflow: hidden; box-shadow: 0 4rpx 12rpx rgba(0,0,0,0.03); }
.type-badge { width: 50rpx; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 24rpx; font-weight: bold; }
.bg-red { background-color: #ff5e52; }
.bg-orange { background-color: #ff9f43; }
.card-main { flex: 1; padding: 24rpx; }
.party-title { font-size: 28rpx; color: var(--text-1); font-weight: 500; line-height: 1.5; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; }
.owner-info { display: flex; align-items: center; margin-top: 16rpx; font-size: 24rpx; color: #888; flex-wrap: wrap; }
.owner-avatar { width: 36rpx; height: 36rpx; border-radius: 50%; margin-right: 12rpx; display: flex; align-items: center; justify-content: center; font-size: 22rpx; color: #fff; font-weight: bold; }
.owner-name { color: #555; }
.divider { margin: 0 8rpx; }
.post-date { color: #aaa; }

.progress-section { margin-top: 20rpx; }
.progress-bar-bg { height: 12rpx; background-color: #f5f5f5; border-radius: 6rpx; overflow: hidden; }
.progress-bar-active { height: 100%; background: linear-gradient(90deg, #ff7875, #ff4d4f); border-radius: 6rpx; }
.progress-meta { display: flex; align-items: center; justify-content: space-between; margin-top: 12rpx; }
.count-text { font-size: 24rpx; color: var(--text-3); }
.current-num { color: var(--brand-red-dark); font-weight: bold; font-size: 26rpx; }
.join-btn { padding: 8rpx 28rpx; border-radius: 28rpx; background: var(--brand-red); color: #fff; font-size: 24rpx; }
.join-btn.joined { background: #f0f0f0; color: #888; }
.join-btn.full { background: #f0f0f0; color: #aaa; }
</style>
