<template>
  <view class="page-home">
    <!-- 1. 顶部红色搜索（沉浸式：预留状态栏高度） -->
    <view class="header-search-box">
      <view class="status-bar-spacer" :style="{ height: statusBarHeight + 'px' }" />
      <view class="search-row">
        <view class="search-bar">
          <text class="icon-search">🔍</text>
          <input
            v-model="searchKeyword"
            class="search-input"
            placeholder="搜索内容/求助"
            placeholder-class="search-placeholder"
            confirm-type="search"
            @confirm="onSearch"
          />
          <text class="search-confirm" @tap="onSearch">搜索</text>
        </view>
      </view>
    </view>

    <!-- 2. 通知马灯 -->
    <view class="notice-bar" @tap="onNotice">
      <view class="notice-content">
        <text class="icon-ufo">🛸</text>
        <text class="notice-text">搭乘UFO，带你回到过去</text>
      </view>
      <text class="arrow-right">›</text>
    </view>

    <!-- 3. 十大热帖 -->
    <view class="hot-posts-section">
      <view class="hot-side-banner">
        <text class="hot-title">十大热帖</text>
        <text class="hot-arrow">›</text>
      </view>
      <view class="hot-list">
        <view
          v-for="item in hotPosts"
          :key="item.id"
          class="hot-item"
          @tap="goPost(item.id)"
        >
          <text class="rank-num" :class="rankClass(item.rank)">{{ item.rank }}</text>
          <text class="hot-item-title">{{ item.title }}</text>
          <text v-if="item.isHot" class="hot-tag">热</text>
          <text class="read-count">{{ item.reads }}</text>
        </view>
      </view>
    </view>

    <!-- 4. 金刚区 10 宫格 -->
    <view class="grid-menu">
      <view
        v-for="(item, idx) in menuItems"
        :key="idx"
        class="grid-item"
        @tap="onMenu(item)"
      >
        <view class="grid-icon-wrapper">
          <text class="grid-icon">{{ item.icon }}</text>
          <text v-if="item.badge" class="badge-dot" :class="{ all: item.badge === '全部' }">{{ item.badge }}</text>
        </view>
        <text class="grid-label">{{ item.name }}</text>
      </view>
    </view>

    <!-- 5. 广告位（可滑动轮播） -->
    <swiper
      class="ad-swiper"
      indicator-dots
      indicator-color="rgba(255,255,255,0.45)"
      indicator-active-color="#ffffff"
      autoplay
      circular
      :interval="4000"
      :duration="500"
    >
      <swiper-item v-for="ad in adBanners" :key="ad.id" @tap="onAd(ad)">
        <view class="ad-slide" :style="{ background: ad.bg }">
          <text class="ad-emoji">{{ ad.emoji }}</text>
          <view class="ad-text">
            <text class="ad-title">{{ ad.title }}</text>
            <text class="ad-desc">{{ ad.desc }}</text>
          </view>
          <text class="ad-tag">{{ ad.tag }}</text>
        </view>
      </swiper-item>
    </swiper>

    <!-- 6. 吸顶分类 Tab -->
    <view class="tab-bar-sticky">
      <scroll-view class="tab-scroll" scroll-x :show-scrollbar="false">
        <view
          v-for="(tab, idx) in tabs"
          :key="idx"
          class="tab-item"
          :class="{ active: currentTab === idx }"
          @tap="switchTab(idx)"
        >
          {{ tab }}
        </view>
      </scroll-view>
    </view>

    <!-- 7. 信息流 -->
    <view class="feed-list">
      <view v-if="feedTypeName" class="filter-chip" @tap="clearFilter">
        <text>分类：{{ feedTypeName }} ✕</text>
      </view>
      <view v-if="loadingFeeds && posts.length === 0" class="feed-tip"><text>加载中…</text></view>
      <view v-else-if="posts.length === 0" class="feed-tip"><text>暂无内容，下拉刷新或去发布</text></view>
      <FeedCard
        v-for="p in posts"
        :key="p.id"
        :post="p"
        @detail="goPost(p.id)"
      />
    </view>

    <!-- 8. 悬浮搜索 -->
    <view class="floating-search-btn" @tap="scrollToTop">
      <text class="fs-icon">🔍</text>
      <text class="fs-text">搜索</text>
    </view>

    <TabBar :current="0" />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import FeedCard from '@/components/feed-card.vue'
import TabBar from '@/components/tab-bar.vue'
import { HOME_TABS, MENU_ITEMS, AD_BANNERS } from '@/utils/mock'
import type { AdBanner, MenuItem } from '@/types/mock'
import type { PostBrief } from '@/types/api'
import { getPosts, getHotPosts } from '@/api/posts'

const tabs = HOME_TABS
const currentTab = ref(0)
interface HotItem { id: number; rank: number; title: string; isHot: boolean; reads: string }
const hotPosts = ref<HotItem[]>([])
const menuItems = MENU_ITEMS
const adBanners = AD_BANNERS
const posts = ref<PostBrief[]>([])
const loadingFeeds = ref(false)
const searchKeyword = ref('')
const feedType = ref<string>('') // 金刚区分类筛选
const feedTypeName = ref<string>('') // 当前筛选的中文名（展示用）

// 沉浸式头部：状态栏高度（custom 导航栏后内容会顶到状态栏，需让出空间）
const statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0

const loadFeeds = async () => {
  loadingFeeds.value = true
  try {
    const res = await getPosts(undefined, feedType.value || undefined)
    posts.value = res.items
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  } finally {
    loadingFeeds.value = false
  }
}

const loadHot = async () => {
  try {
    const list = await getHotPosts(5)
    hotPosts.value = list.map((p, i) => ({
      id: p.id,
      rank: i + 1,
      title: p.content,
      isHot: (p.like_count || 0) > 0,
      reads: `${p.view_count || 0} 浏览`,
    }))
  } catch {
    /* 热帖非关键，失败静默 */
  }
}

onShow(() => {
  loadFeeds()
  loadHot()
})

const rankClass = (rank: number) => `rank-${rank}`

const onSearch = () => {
  const q = searchKeyword.value.trim()
  uni.navigateTo({ url: q ? `/pages/search/index?q=${encodeURIComponent(q)}` : '/pages/search/index' })
}
const onNotice = () => uni.showToast({ title: '搭乘UFO～', icon: 'none' })
const onAd = (ad: AdBanner) => uni.showToast({ title: `${ad.title}（开发中）`, icon: 'none' })
const onMenu = (item: MenuItem) => {
  if (item.type) {
    // 映射到 post_type：过滤信息流并滚动到信息流
    feedType.value = item.type
    feedTypeName.value = item.name
    currentTab.value = 0
    loadFeeds()
    uni.pageScrollTo({ selector: '.feed-list', duration: 200 })
  } else if (item.name === '更多分类') {
    uni.navigateTo({ url: '/pages/search/index' })
  } else {
    // 无 post_type 映射：按分类名搜索
    uni.navigateTo({ url: `/pages/search/index?q=${encodeURIComponent(item.name)}` })
  }
}

const goPost = (id: number) => {
  uni.navigateTo({ url: `/pages/post-detail/index?id=${id}` })
}

const switchTab = (idx: number) => {
  if (currentTab.value === idx && idx === 0 && feedType.value) {
    // 再点「推荐」清除分类筛选
    feedType.value = ''
    feedTypeName.value = ''
    loadFeeds()
    return
  }
  if (currentTab.value === idx) return
  currentTab.value = idx
  if (idx === 0 && feedType.value) {
    feedType.value = ''
    feedTypeName.value = ''
    loadFeeds()
  }
}

const clearFilter = () => {
  feedType.value = ''
  feedTypeName.value = ''
  loadFeeds()
}

const scrollToTop = () => {
  uni.pageScrollTo({ scrollTop: 0, duration: 200 })
}
</script>

<style scoped>
.page-home {
  min-height: 100vh;
  background-color: var(--bg-page);
  padding-bottom: 40rpx;
}

/* 1. 红色头部（沉浸式） */
.header-search-box {
  background-color: var(--brand-red);
  display: flex;
  flex-direction: column;
}

.status-bar-spacer {
  width: 100%;
}

.search-row {
  padding: 24rpx 30rpx 34rpx;
  display: flex;
  align-items: center;
}

.search-bar {
  flex: 1;
  height: 68rpx;
  background-color: rgba(255, 255, 255, 0.25);
  border-radius: 34rpx;
  padding: 0 24rpx;
  display: flex;
  align-items: center;
}

.icon-search {
  font-size: 28rpx;
  color: #ffffff;
}

.search-input {
  flex: 1;
  font-size: 26rpx;
  margin-left: 14rpx;
  color: #ffffff;
}

.search-placeholder {
  color: rgba(255, 255, 255, 0.7);
}

.search-confirm {
  font-size: 26rpx;
  color: #ffffff;
  padding-left: 20rpx;
  border-left: 1rpx solid rgba(255, 255, 255, 0.3);
}

/* 2. 通知马灯 */
.notice-bar {
  background-color: #ffffff;
  margin: 20rpx 24rpx;
  padding: 18rpx 24rpx;
  border-radius: 12rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.notice-content {
  display: flex;
  align-items: center;
}

.icon-ufo {
  font-size: 34rpx;
  margin-right: 12rpx;
}

.notice-text {
  font-size: 24rpx;
  color: var(--text-2);
}

.arrow-right {
  color: var(--text-3);
  font-size: 32rpx;
}

/* 3. 十大热帖 */
.hot-posts-section {
  background-color: #ffffff;
  margin: 0 24rpx 24rpx;
  border-radius: var(--radius-card);
  padding: 24rpx;
  display: flex;
}

.hot-side-banner {
  width: 150rpx;
  height: 150rpx;
  background: linear-gradient(135deg, #ff4c3b, #ff7e40);
  border-radius: 16rpx;
  justify-content: center;
  align-items: center;
  display: flex;
  flex-direction: column;
  color: #ffffff;
}

.hot-title {
  font-size: 30rpx;
  font-weight: bold;
  text-align: center;
  width: 80rpx;
  line-height: 1.3;
}

.hot-arrow {
  font-size: 28rpx;
  margin-top: 6rpx;
  opacity: 0.8;
}

.hot-list {
  flex: 1;
  margin-left: 24rpx;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.hot-item {
  display: flex;
  align-items: center;
  font-size: 24rpx;
}

.rank-num {
  font-weight: bold;
  font-style: italic;
  margin-right: 12rpx;
  width: 30rpx;
  color: var(--text-3);
}

.rank-1 { color: #ff3b30; }
.rank-2 { color: #ff9500; }
.rank-3 { color: #ffcc00; }

.hot-item-title {
  flex: 1;
  color: var(--text-1);
  font-size: 26rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hot-tag {
  background-color: var(--brand-red-dark);
  color: #ffffff;
  font-size: 18rpx;
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
  margin-left: 10rpx;
}

.read-count {
  font-size: 22rpx;
  color: var(--text-3);
  margin-left: 16rpx;
}

/* 4. 金刚区 */
.grid-menu {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  row-gap: 28rpx;
  padding: 24rpx 10rpx;
  background-color: #ffffff;
  margin: 0 24rpx 24rpx;
  border-radius: var(--radius-card);
}

.grid-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.grid-icon-wrapper {
  position: relative;
  width: 84rpx;
  height: 84rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.grid-icon {
  font-size: 52rpx;
}

.badge-dot {
  position: absolute;
  top: -6rpx;
  right: -10rpx;
  background-color: var(--brand-red-dark);
  color: #ffffff;
  font-size: 18rpx;
  padding: 2rpx 8rpx;
  border-radius: 18rpx;
  font-weight: bold;
}

.badge-dot.all {
  background-color: #ff5e52;
}

.grid-label {
  font-size: 23rpx;
  color: #444444;
  margin-top: 12rpx;
}

/* 5. 广告位轮播 */
.ad-swiper {
  height: 180rpx;
  margin: 0 24rpx 24rpx;
}

.ad-slide {
  height: 100%;
  border-radius: var(--radius-card);
  padding: 0 28rpx;
  display: flex;
  align-items: center;
  position: relative;
}

.ad-emoji {
  font-size: 64rpx;
  margin-right: 22rpx;
}

.ad-text {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.ad-title {
  color: #ffffff;
  font-size: 30rpx;
  font-weight: bold;
}

.ad-desc {
  color: rgba(255, 255, 255, 0.88);
  font-size: 22rpx;
  margin-top: 6rpx;
}

.ad-tag {
  position: absolute;
  top: 16rpx;
  right: 20rpx;
  color: rgba(255, 255, 255, 0.85);
  font-size: 18rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.6);
  padding: 2rpx 12rpx;
  border-radius: 16rpx;
}

/* 6. 吸顶 Tab */
.tab-bar-sticky {
  position: sticky;
  top: 0;
  z-index: 10;
  background-color: var(--bg-page);
}

.tab-scroll {
  white-space: nowrap;
  padding: 16rpx 24rpx;
}

.tab-item {
  display: inline-block;
  font-size: 28rpx;
  color: #666666;
  margin-right: 36rpx;
  padding-bottom: 12rpx;
}

.tab-item.active {
  color: #111111;
  font-weight: bold;
  border-bottom: 6rpx solid var(--brand-red);
}

/* 7. 信息流 */
.feed-list {
  padding: 0 24rpx;
}
.filter-chip {
  display: inline-flex;
  align-items: center;
  background: var(--brand-red-soft);
  color: var(--brand-red);
  font-size: 24rpx;
  padding: 8rpx 20rpx;
  border-radius: 24rpx;
  margin: 8rpx 0 16rpx;
}
.feed-tip {
  text-align: center;
  padding: 60rpx 0;
  color: var(--text-3);
  font-size: 26rpx;
}

/* 8. 悬浮搜索 */
.floating-search-btn {
  position: fixed;
  bottom: 200rpx;
  right: 30rpx;
  background-color: var(--brand-red);
  color: #ffffff;
  padding: 18rpx 32rpx;
  border-radius: 44rpx;
  display: flex;
  align-items: center;
  box-shadow: 0 6rpx 20rpx rgba(247, 59, 67, 0.4);
  z-index: 99;
}

.fs-icon {
  font-size: 28rpx;
}

.fs-text {
  margin-left: 8rpx;
  font-size: 26rpx;
  font-weight: 500;
}
</style>
