<template>
  <view class="page-group" :class="themeClass">
    <!-- 0. 标题栏（沉浸式：微信胶囊安全避让） -->
    <CustomNavBar title="组局" :show-back="false" />

    <view v-if="mode === 'mine'" class="back-all" @tap="setMode('all')">‹ 返回全部</view>

    <!-- 2. 双核动作卡 -->
    <view class="action-cards">
      <view class="action-card card-blue" @tap="setMode('mine')">
        <text class="card-title">我加入的局</text>
        <image class="card-icon" src="/static/icons/common/group-inverse.svg" mode="aspectFit" />
      </view>
      <view class="action-card card-orange" @tap="goCreate">
        <text class="card-title">发起攒局</text>
        <image class="card-icon" src="/static/icons/common/plus-inverse.svg" mode="aspectFit" />
      </view>
    </view>

    <!-- 3. 分类筛选（mode=all 时显示：图标 + 文字胶囊） -->
    <view v-if="mode === 'all'" class="filter-wrap scroll-x-wrap">
      <scroll-view class="filter-scroll" scroll-x :show-scrollbar="false" @scroll="onFilterScroll">
        <view class="filter-row">
          <view
            v-for="c in categories"
            :key="c.id"
            class="tag-pill"
            :class="{ active: activeFilter === c.id }"
            @tap="onFilter(c)"
          >
            <image class="tag-icon" :src="c.icon" mode="aspectFit" />
            <text class="tag-name">{{ c.name }}</text>
          </view>
        </view>
      </scroll-view>
      <view class="scroll-x-fade left" :class="{ show: showFadeLeft }" />
      <view class="scroll-x-fade right" :class="{ show: showFadeRight }" />
    </view>

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
        <view class="card-main">
          <view class="title-row">
            <view class="type-tag" :class="p.type === 'group' ? 'tag-group' : 'tag-pool'">
              <text>{{ p.type === 'group' ? '组局' : '拼单' }}</text>
            </view>
            <text class="party-title">{{ p.title }}</text>
          </view>
          <view class="owner-info">
            <view class="owner-avatar" :style="{ background: colorOf(p.user.nickname) }">
              <text>{{ (p.user.nickname || '?').slice(0, 1) }}</text>
            </view>
            <text class="owner-name">{{ p.user.nickname }}</text>
            <text class="divider">·</text>
            <text class="post-date">{{ timeShort(p.created_at) }}</text>
            <text v-if="p.location" class="divider">·</text>
            <view v-if="p.location" class="post-date post-loc">
              <image class="loc-dot" src="/static/icons/common/location.svg" mode="aspectFit" />
              <text>{{ p.location }}</text>
            </view>
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
          <image class="close-x" src="/static/icons/common/close.svg" mode="aspectFit" @tap="selectedParty = null" />
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
          <view class="loc-icon">
            <image class="loc-dot" src="/static/icons/common/location.svg" mode="aspectFit" />
            <text>地点：</text>
          </view>
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
import { avatarColor as colorOf } from '@/utils/avatar'
import { useTheme } from '@/utils/theme'
import { onShow } from '@dcloudio/uni-app'
import TabBar from '@/components/tab-bar.vue'
import CustomNavBar from '@/components/custom-nav-bar.vue'
import SkeletonCard from '@/components/skeleton-card.vue'
import { listParties, myParties, joinParty, leaveParty, type PartyItem } from '@/api/party'
import { tokenStorage } from '@/utils/storage'
import { useScrollFade } from '@/utils/scroll-fade'

const { themeClass } = useTheme()

// 分类筛选（第 1 项=有空位=only_vacant，其余=分类）
const categories = [
  { id: 'vacant', icon: '/static/icons/party/star.svg', name: '有空位' },
  { id: '自习', icon: '/static/icons/party/book.svg', name: '自习' },
  { id: '电影', icon: '/static/icons/party/film.svg', name: '电影' },
  { id: '聚餐', icon: '/static/icons/party/dining.svg', name: '聚餐' },
  { id: '拼车', icon: '/static/icons/party/car.svg', name: '拼车' },
  { id: '拼单', icon: '/static/icons/party/shopping.svg', name: '拼单' },
  { id: '运动', icon: '/static/icons/party/running.svg', name: '运动' },
  { id: '游戏', icon: '/static/icons/party/game.svg', name: '游戏' },
  { id: '旅行', icon: '/static/icons/party/palm.svg', name: '旅行' },
  { id: '其他', icon: '/static/icons/party/gear.svg', name: '其他' },
] as const

const parties = ref<PartyItem[]>([])
const loading = ref(false)
const mode = ref<'all' | 'mine'>('all')
const activeFilter = ref<string | null>(null)
const selectedParty = ref<PartyItem | null>(null)
/* 分类筛选行横向滚动：两侧渐隐，滚到端点时对应侧隐藏 */
const { showLeft: showFadeLeft, showRight: showFadeRight, onScroll: onFilterScroll } = useScrollFade('.filter-scroll')

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
  color: var(--primary-text);
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
  background: var(--primary-fill-gradient);
}
.card-orange {
  /* 原先两个入口卡片都是蓝色渐变，视觉上无法区分；改用深暖绿，
     白字 5.46:1 仍达 WCAG AA */
  background: linear-gradient(135deg, var(--accent-warm-fill), var(--accent-warm-fill-strong));
}
.card-title {
  font-size: 30rpx;
  font-weight: bold;
}
.card-icon {
  width: 44rpx;
  height: 44rpx;
  margin-left: auto;
}

.filter-scroll {
  width: 100%;
  margin-top: 24rpx;
  white-space: nowrap;
}
.filter-row {
  display: inline-flex;
  /* 左右内边距放在滚动内容上：容器可视宽度 == 测量宽度，滚动位移换算才准 */
  padding: 4rpx 72rpx 4rpx 24rpx;
}
.tag-pill {
  display: inline-flex;
  align-items: center;
  background-color: var(--bg-card);
  border: 1rpx solid var(--border-light);
  border-radius: 32rpx;
  /* 上下 16rpx + 行高 ≈34rpx = 66rpx（≈34px）点击区 */
  padding: 16rpx 24rpx;
  margin-right: 16rpx;
  font-size: 24rpx;
  color: var(--text-2);
  white-space: nowrap;
  gap: 8rpx;
  /* 分类多、可横向滚动：不压缩胶囊，否则分类名会被逐字竖排 */
  flex-shrink: 0;
}
.tag-pill.active {
  border-color: var(--primary);
  color: var(--primary-text);
  background-color: var(--primary-soft);
  font-weight: 600;
}
.tag-icon {
  width: 26rpx;
  height: 26rpx;
  flex-shrink: 0;
}
.tag-name {
  font-size: 24rpx;
  flex-shrink: 0;
  /* uni-app 的 <text> 默认 white-space: pre-wrap，需显式覆盖否则中文逐字换行 */
  white-space: nowrap;
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
/* 卡片类型标识：原先是贯穿卡片全高的饱和蓝条，单字悬在中间，视觉过重；
   改为标题行内的紧凑标签（X 风格的小色块标签） */
.type-tag {
  flex-shrink: 0;
  margin-top: 4rpx;
  font-size: 22rpx;
  font-weight: 600;
  line-height: 1;
  padding: 6rpx 12rpx;
  border-radius: 6rpx;
}
.tag-group { color: var(--primary-text); background: var(--primary-soft); }
.tag-pool { color: var(--accent-warm-text); background: var(--accent-warm-soft); }
.bg-red {
  background: var(--primary-fill-gradient);
}
.bg-orange {
  background: linear-gradient(180deg, var(--accent-warm-fill), var(--accent-warm-fill-strong));
}
.card-main {
  flex: 1;
  padding: 24rpx;
}
.title-row {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
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
  color: var(--on-avatar);
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
.post-loc {
  display: inline-flex;
  align-items: center;
}
.loc-dot {
  width: 24rpx;
  height: 24rpx;
  margin-right: 4rpx;
  flex-shrink: 0;
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
  color: var(--primary-text);
  font-weight: bold;
  font-size: 26rpx;
}
.join-btn {
  padding: 18rpx 30rpx;
  border-radius: 28rpx;
  background: var(--primary-fill-gradient);
  color: var(--text-inverse);
  font-size: 24rpx;
  font-weight: 600;
  /* 最小点击区 64rpx（≈33px） */
  min-height: 64rpx;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
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
  width: 36rpx;
  height: 36rpx;
  padding: 8rpx;
  flex-shrink: 0;
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
.loc-icon { display: inline-flex; align-items: center; }
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
