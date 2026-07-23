<template>
  <view class="page-group">
    <!-- 1. 累计攒局统计 -->
    <view class="header-stats" @tap="onViewStats">
      <text class="stats-text">已攒 <text class="highlight-num">{{ totalUser }}</text> 人</text>
      <text class="arrow-right">›</text>
    </view>

    <!-- 2. 轮播 Banner -->
    <swiper class="banner-swiper" indicator-dots indicator-color="rgba(0,0,0,0.1)" indicator-active-color="#ff4d4f" autoplay circular>
      <swiper-item>
        <view class="swiper-content" @tap="onManual">
          <text class="banner-emoji">📌</text>
          <view class="banner-meta">
            <text class="banner-title">组局新手手册</text>
            <text class="banner-desc">3 分钟学会发起你的第一场局</text>
          </view>
        </view>
      </swiper-item>
    </swiper>

    <!-- 3. 双核动作卡 -->
    <view class="action-cards">
      <view class="action-card card-blue" @tap="goMyGroups">
        <text class="card-title">我加入的局</text>
        <text class="card-icon">👥</text>
      </view>
      <view class="action-card card-orange" @tap="goCreate">
        <text class="card-title">发起攒局</text>
        <text class="card-icon">✚</text>
      </view>
    </view>

    <!-- 4. 分类筛选 -->
    <view class="filter-grid">
      <view
        v-for="c in categories"
        :key="c.id"
        class="tag-pill"
        :class="{ active: currentTag === c.id }"
        @tap="onTag(c.id)"
      >
        <text class="tag-icon">{{ c.icon }}</text>
        <text class="tag-name">{{ c.name }}</text>
        <text class="tag-count">({{ c.count }})</text>
      </view>
    </view>

    <!-- 5. 组局列表 -->
    <view class="party-list">
      <view
        v-for="item in partyList"
        :key="item.id"
        class="party-card"
        @tap="goDetail(item.id)"
      >
        <!-- 左侧垂直类型标 -->
        <view class="type-badge" :class="item.type === '组局' ? 'bg-red' : 'bg-orange'">
          <text>{{ item.type[0] }}</text>
          <text>{{ item.type[1] }}</text>
        </view>

        <!-- 右侧内容 -->
        <view class="card-main">
          <view class="title-wrapper">
            <text class="party-title">{{ item.title }}</text>
            <text v-if="item.decorIcon" class="decorative-icon">{{ item.decorIcon }}</text>
          </view>

          <view class="owner-info">
            <view class="owner-avatar" :style="{ background: item.avatarColor }">
              <text>{{ item.avatar }}</text>
            </view>
            <text class="owner-name">{{ item.username }}</text>
            <text class="divider">·</text>
            <text class="post-date">{{ item.date }}</text>
          </view>

          <view class="progress-section">
            <view class="progress-bar-bg">
              <view class="progress-bar-active" :style="{ width: progressOf(item) + '%' }" />
            </view>
            <view class="progress-meta">
              <text class="count-text"><text class="current-num">{{ item.joined }}</text>/{{ item.total }}人</text>
              <text class="status-label">已报名</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- 6. 悬浮搜索 -->
    <view class="floating-search" @tap="onFloatingSearch">
      <text>🔍</text>
    </view>

    <TabBar :current="1" />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import TabBar from '@/components/tab-bar.vue'
import { GROUP_TOTAL_USER, PARTY_CATEGORIES, PARTY_LIST } from '@/utils/mock'
import type { PartyItem } from '@/types/mock'

const totalUser = GROUP_TOTAL_USER
const categories = PARTY_CATEGORIES
const partyList = PARTY_LIST
const currentTag = ref(0)

onShow(() => {})

const progressOf = (item: PartyItem) => Math.min(100, Math.round((item.joined / item.total) * 100))

const onTag = (id: number) => {
  if (currentTag.value === id) return
  currentTag.value = id
  uni.showToast({ title: `筛选：${categories[id].name}`, icon: 'none' })
}

const onViewStats = () => uni.showToast({ title: '累计统计开发中', icon: 'none' })
const onManual = () => uni.showToast({ title: '组局手册开发中', icon: 'none' })
const goMyGroups = () => uni.showToast({ title: '我加入的局（开发中）', icon: 'none' })
const goCreate = () => uni.showToast({ title: '发起攒局（开发中）', icon: 'none' })
const goDetail = (id: number) => uni.showToast({ title: `组局详情 #${id}`, icon: 'none' })
const onFloatingSearch = () => uni.showToast({ title: '搜索组局（开发中）', icon: 'none' })
</script>

<style scoped>
.page-group {
  background-color: var(--bg-group);
  padding: 20rpx 24rpx 40rpx;
  min-height: 100vh;
}

.header-stats {
  display: flex;
  align-items: center;
  font-size: 26rpx;
  color: #666666;
  padding: 10rpx;
}

.highlight-num {
  color: var(--brand-red-dark);
  font-weight: bold;
  font-size: 32rpx;
  margin: 0 4rpx;
}

.arrow-right {
  margin-left: 6rpx;
  color: #ccc;
  font-size: 30rpx;
}

/* 2. 轮播 */
.banner-swiper {
  height: 180rpx;
  margin-top: 16rpx;
  border-radius: 20rpx;
  overflow: hidden;
}

.swiper-content {
  height: 100%;
  background: linear-gradient(135deg, #ffb199, #ff0844);
  display: flex;
  align-items: center;
  padding: 0 32rpx;
}

.banner-emoji {
  font-size: 60rpx;
  margin-right: 20rpx;
}

.banner-meta {
  display: flex;
  flex-direction: column;
}

.banner-title {
  color: #ffffff;
  font-size: 30rpx;
  font-weight: bold;
}

.banner-desc {
  color: rgba(255, 255, 255, 0.9);
  font-size: 22rpx;
  margin-top: 6rpx;
}

/* 3. 动作卡 */
.action-cards {
  display: flex;
  justify-content: space-between;
  margin-top: 24rpx;
}

.action-card {
  width: 48%;
  height: 120rpx;
  border-radius: 20rpx;
  padding: 0 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #ffffff;
}

.card-blue {
  background: linear-gradient(135deg, #69c0ff, #1890ff);
}

.card-orange {
  background: linear-gradient(135deg, #ff9c6e, #ff4d4f);
}

.card-title {
  font-size: 30rpx;
  font-weight: bold;
}

.card-icon {
  font-size: 44rpx;
}

/* 4. 分类筛选 */
.filter-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14rpx;
  margin-top: 30rpx;
  padding: 10rpx 0;
}

.tag-pill {
  background-color: #ffffff;
  border: 1rpx solid #f0f0f0;
  border-radius: 12rpx;
  padding: 12rpx 4rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20rpx;
  color: #777777;
  white-space: nowrap;
}

.tag-pill.active {
  border-color: var(--brand-red-dark);
  color: var(--brand-red-dark);
  background-color: #fff1f0;
}

.tag-icon {
  margin-right: 4rpx;
  font-size: 22rpx;
}

.tag-count {
  color: #aaaaaa;
  font-size: 18rpx;
  margin-left: 2rpx;
}

/* 5. 组局卡片 */
.party-list {
  margin-top: 24rpx;
}

.party-card {
  background-color: #ffffff;
  border-radius: var(--radius-card);
  margin-bottom: 24rpx;
  display: flex;
  overflow: hidden;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.03);
}

.type-badge {
  width: 50rpx;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #ffffff;
  font-size: 22rpx;
  font-weight: bold;
  line-height: 1.2;
}

.bg-red { background-color: #ff5e52; }
.bg-orange { background-color: #ff9f43; }

.card-main {
  flex: 1;
  padding: 24rpx;
}

.title-wrapper {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.party-title {
  flex: 1;
  font-size: 28rpx;
  color: var(--text-1);
  font-weight: 500;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.decorative-icon {
  font-size: 56rpx;
  margin-left: 16rpx;
}

.owner-info {
  display: flex;
  align-items: center;
  margin-top: 16rpx;
  font-size: 24rpx;
  color: #888888;
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
}

.owner-name {
  color: #555555;
}

.divider {
  margin: 0 8rpx;
}

.progress-section {
  display: flex;
  align-items: center;
  margin-top: 24rpx;
}

.progress-bar-bg {
  flex: 1;
  height: 12rpx;
  background-color: #f5f5f5;
  border-radius: 6rpx;
  overflow: hidden;
  margin-right: 30rpx;
}

.progress-bar-active {
  height: 100%;
  background: linear-gradient(90deg, #ff7875, #ff4d4f);
  border-radius: 6rpx;
}

.progress-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  min-width: 110rpx;
}

.count-text {
  font-size: 24rpx;
  color: var(--text-3);
  line-height: 1;
}

.current-num {
  color: var(--brand-red-dark);
  font-weight: bold;
  font-size: 26rpx;
}

.status-label {
  font-size: 18rpx;
  color: #bbbbbb;
  margin-top: 4rpx;
}

/* 6. 悬浮搜索 */
.floating-search {
  position: fixed;
  bottom: 200rpx;
  right: 40rpx;
  width: 90rpx;
  height: 90rpx;
  background-color: var(--brand-red-dark);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4rpx 16rpx rgba(255, 77, 79, 0.35);
  z-index: 99;
  font-size: 32rpx;
}
</style>
