<template>
  <view class="page-group" :class="themeClass">
    <!-- 0. 标题栏（沉浸式：微信胶囊安全避让） -->
    <CustomNavBar title="组局" :show-back="false" />

    <view v-if="mode === 'mine'" class="back-all" @tap="setMode('all')">‹ 返回全部</view>

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

    <!-- 3. 分类筛选（mode=all 时显示：图标 + 文字胶囊） -->
    <scroll-view v-if="mode === 'all'" class="filter-scroll" scroll-x :show-scrollbar="false">
      <view class="filter-row">
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
    </scroll-view>

    <!-- 4. 组局列表 -->
    <view class="party-list">
      <view v-if="loading && parties.length === 0" class="skeleton-list">
        <SkeletonCard v-for="i in 4" :key="i" />
      </view>
      <view v-else-if="parties.length === 0" class="tip">
        <text>{{ mode === 'mine' ? '还没有加入任何局' : '暂无组局，去发起一个吧' }}</text>
      </view>

      <view
        v-for="p in parties"
        :key="p.id"
        class="party-card"
        @tap="showDetail(p)"
      >
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
                @tap.stop="onJoin(p)"
              >
                <text>{{ p.is_joined ? '退出' : (p.status === 2 ? '已满' : '报名') }}</text>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- 5. 组局正文详情弹窗 -->
    <view v-if="selectedParty" class="party-modal-mask" @tap="selectedParty = null">
      <view class="party-modal-card" @tap.stop>
        <view class="modal-head">
          <view class="type-pill" :class="selectedParty.type === 'group' ? 'bg-red' : 'bg-orange'">
            <text>{{ selectedParty.type === 'group' ? '组局' : '拼单' }} · {{ selectedParty.category }}</text>
          </view>
          <text class="close-x" @tap="selectedParty = null">✕</text>
        </view>

        <text class="modal-title">{{ selectedParty.title }}</text>

        <view class="modal-owner-row">
          <view class="owner-avatar" :style="{ background: colorOf(selectedParty.user.nickname) }">
            <text>{{ (selectedParty.user.nickname || '?').slice(0, 1) }}</text>
          </view>
          <text class="owner-name">{{ selectedParty.user.nickname }}</text>
          <text class="divider">·</text>
          <text class="post-date">{{ timeShort(selectedParty.created_at) }} 发起</text>
        </view>

        <view v-if="selectedParty.location" class="modal-loc-row">
          <text class="loc-icon">📍 地点：</text>
          <text class="loc-text">{{ selectedParty.location }}</text>
        </view>

        <view class="modal-content-wrap">
          <text class="modal-content-label">详情说明：</text>
          <scroll-view scroll-y class="modal-content-scroll">
            <text class="modal-content-text">{{ selectedParty.content }}</text>
          </scroll-view>
        </view>

        <view class="modal-progress-row">
          <text class="count-text">报名进度：<text class="current-num">{{ selectedParty.joined_count }}</text> / {{ selectedParty.total }} 人</text>
          <view class="progress-bar-bg modal-pbar">
            <view class="progress-bar-active" :style="{ width: progressOf(selectedParty) + '%' }" />
          </view>
        </view>

        <view class="modal-btn-row">
          <view
            class="join-btn modal-act-btn"
            :class="{ joined: selectedParty.is_joined, full: !selectedParty.is_joined && selectedParty.status === 2 }"
            @tap="onJoin(selectedParty)"
          >
            <text>{{ selectedParty.is_joined ? '退出此局' : (selectedParty.status === 2 ? '名额已满' : '立即报名') }}</text>
          </view>
        </view>
      </view>
    </view>

    <TabBar :current="1" />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTheme } from '@/utils/theme'
import { onShow } from '@dcloudio/uni-app'
import TabBar from '@/components/tab-bar.vue'
import CustomNavBar from '@/components/custom-nav-bar.vue'
import SkeletonCard from '@/components/skeleton-card.vue'
import { listParties, myParties, joinParty, leaveParty, type PartyItem } from '@/api/party'
import { tokenStorage } from '@/utils/storage'

const { themeClass } = useTheme()

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

const parties = ref<PartyItem[]>([])
const loading = ref(false)
const mode = ref<'all' | 'mine'>('all')
const activeFilter = ref<string | null>(null)
const selectedParty = ref<PartyItem | null>(null)

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
  loadList()
})

const setMode = (m: 'all' | 'mine') => {
  mode.value = m
  loadList()
}

const onFilter = (c: (typeof categories)[number]) => {
  activeFilter.value = activeFilter.value === c.id ? null : c.id
  loadList()
}

const showDetail = (p: PartyItem) => {
  selectedParty.value = p
}

const onJoin = async (p: PartyItem) => {
  if (!tokenStorage.isLoggedIn()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  const wasJoined = p.is_joined
  p.is_joined = !wasJoined
  p.joined_count += wasJoined ? -1 : 1
  try {
    if (wasJoined) {
      await leaveParty(p.id)
      uni.showToast({ title: '已退出', icon: 'none' })
    } else {
      const r = await joinParty(p.id)
      p.joined_count = r.joined_count
      uni.showToast({ title: r.full ? '已满员' : '报名成功！', icon: 'success' })
    }
  } catch (e) {
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
.page-group {
  background-color: var(--bg-page);
  padding: 20rpx 24rpx 48rpx;
  min-height: 100vh;
}

.page-header {
  background-color: var(--bg-page);
  border-bottom: 1rpx solid var(--border-light);
  margin: -20rpx -24rpx 0;
}
.page-title {
  display: block;
  padding: 30rpx 40rpx;
  text-align: center;
  color: var(--text-1);
  font-size: 34rpx;
  font-weight: 700;
  letter-spacing: 2rpx;
}

.back-all {
  color: var(--primary);
  font-size: 26rpx;
  margin: 16rpx 0 8rpx;
  font-weight: 600;
}

.action-cards {
  display: flex;
  justify-content: space-between;
  gap: 20rpx;
  margin-top: 20rpx;
}
.action-card {
  flex: 1;
  height: 132rpx;
  border-radius: var(--radius-card);
  padding: 0 28rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--text-inverse);
  box-shadow: var(--shadow-primary-lg);
}
.card-blue {
  background: var(--primary-gradient);
}
.card-orange {
  background: var(--primary-gradient-rev);
}
.card-title {
  font-size: 30rpx;
  font-weight: bold;
}
.card-icon {
  font-size: 44rpx;
}

.filter-scroll {
  width: 100%;
  margin-top: 24rpx;
  white-space: nowrap;
}
.filter-row {
  display: inline-flex;
  padding: 4rpx 0;
}
.tag-pill {
  display: inline-flex;
  align-items: center;
  background-color: var(--bg-card);
  border: 1rpx solid var(--border-light);
  border-radius: 32rpx;
  padding: 12rpx 24rpx;
  margin-right: 16rpx;
  font-size: 24rpx;
  color: var(--text-2);
  white-space: nowrap;
  gap: 8rpx;
}
.tag-pill.active {
  border-color: var(--primary);
  color: var(--primary);
  background-color: var(--primary-soft);
  font-weight: 600;
}
.tag-icon {
  font-size: 26rpx;
  line-height: 1;
}
.tag-name {
  font-size: 24rpx;
}

.tip {
  text-align: center;
  color: var(--text-3);
  font-size: 26rpx;
  padding: 80rpx 0;
}

.party-list {
  margin-top: 16rpx;
}
.party-card {
  background-color: var(--bg-card);
  border-radius: var(--radius-card);
  margin-bottom: 24rpx;
  display: flex;
  overflow: hidden;
  box-shadow: var(--shadow-card);
  border: 1rpx solid var(--border-light);
}
.type-badge {
  width: 50rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-inverse);
  font-size: 24rpx;
  font-weight: bold;
}
.bg-red {
  background: linear-gradient(180deg, var(--primary), var(--primary-strong));
}
.bg-orange {
  background: linear-gradient(180deg, var(--accent-warm), var(--accent-warm-strong));
}
.card-main {
  flex: 1;
  padding: 24rpx;
}
.party-title {
  font-size: 30rpx;
  color: var(--text-1);
  font-weight: 600;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}
.owner-info {
  display: flex;
  align-items: center;
  margin-top: 16rpx;
  font-size: 24rpx;
  color: var(--text-3);
  flex-wrap: wrap;
}
.owner-avatar {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  margin-right: 12rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22rpx;
  color: var(--text-inverse);
  font-weight: bold;
}
.owner-name {
  color: var(--text-2);
}
.divider {
  margin: 0 8rpx;
}
.post-date {
  color: var(--text-3);
}

.progress-section {
  margin-top: 20rpx;
}
.progress-bar-bg {
  height: 12rpx;
  background-color: var(--bg-card-2);
  border-radius: var(--radius-tag);
  overflow: hidden;
}
.progress-bar-active {
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--accent-warm));
  border-radius: var(--radius-tag);
}
.progress-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12rpx;
}
.count-text {
  font-size: 24rpx;
  color: var(--text-3);
}
.current-num {
  color: var(--primary-strong);
  font-weight: bold;
  font-size: 26rpx;
}
.join-btn {
  padding: 10rpx 30rpx;
  border-radius: 28rpx;
  background: linear-gradient(135deg, var(--primary), var(--primary-strong));
  color: var(--text-inverse);
  font-size: 24rpx;
  font-weight: 600;
}
.join-btn.joined {
  background: var(--bg-card-2);
  color: var(--text-3);
}
.join-btn.full {
  background: var(--bg-card-2);
  color: var(--text-4);
}

/* 详情弹窗 */
.party-modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 36rpx;
}
.party-modal-card {
  width: 100%;
  max-height: 80vh;
  background: var(--bg-card);
  border-radius: 28rpx;
  padding: 36rpx;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-card);
  border: 1rpx solid var(--border-light);
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}
.type-pill {
  padding: 6rpx 20rpx;
  border-radius: 20rpx;
  color: #fff;
  font-size: 22rpx;
  font-weight: 700;
}
.close-x {
  font-size: 36rpx;
  color: var(--text-3);
  padding: 8rpx;
}
.modal-title {
  font-size: 34rpx;
  font-weight: 700;
  color: var(--text-1);
  line-height: 1.4;
  margin-bottom: 16rpx;
}
.modal-owner-row {
  display: flex;
  align-items: center;
  font-size: 24rpx;
  color: var(--text-3);
  margin-bottom: 16rpx;
}
.modal-loc-row {
  font-size: 26rpx;
  color: var(--text-2);
  margin-bottom: 20rpx;
  background: var(--bg-card-2);
  padding: 12rpx 18rpx;
  border-radius: 12rpx;
}
.modal-content-wrap {
  margin: 16rpx 0;
}
.modal-content-label {
  font-size: 24rpx;
  color: var(--text-3);
  margin-bottom: 8rpx;
  display: block;
}
.modal-content-scroll {
  max-height: 280rpx;
  background: var(--bg-page);
  border-radius: 16rpx;
  padding: 18rpx;
  border: 1rpx solid var(--border-light);
}
.modal-content-text {
  font-size: 28rpx;
  color: var(--text-1);
  line-height: 1.6;
  white-space: pre-wrap;
}
.modal-progress-row {
  margin-top: 20rpx;
}
.modal-pbar {
  margin-top: 8rpx;
}
.modal-btn-row {
  margin-top: 32rpx;
  display: flex;
  justify-content: center;
}
.modal-act-btn {
  width: 100%;
  text-align: center;
  padding: 20rpx 0;
  font-size: 30rpx;
  border-radius: 36rpx;
}
</style>
