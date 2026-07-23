<template>
  <view class="page-mine">
    <!-- 1. 红色沉浸式头部 -->
    <view class="profile-header-bg">
      <view class="user-info-wrapper">
        <view class="avatar-outer-ring">
          <text class="user-avatar">{{ user.avatarUrl }}</text>
        </view>
        <view class="user-meta-box">
          <text class="user-nickname">{{ user.nickName }}</text>
          <view v-if="user.schoolName" class="school-tag-capsule">
            <text>{{ user.schoolName }}</text>
          </view>
          <view v-if="!loggedIn" class="dev-login-capsule" @tap="doDevLogin">
            <text>一键登录（演示）</text>
          </view>
        </view>
      </view>

      <!-- 4 列统计 -->
      <view class="stats-panel-row">
        <view class="stats-item" @tap="goStats('posts')">
          <text class="stats-label">帖子</text>
          <text class="stats-count">{{ stats.postsCount }}</text>
        </view>
        <view class="stats-divider" />
        <view class="stats-item" @tap="goStats('comments')">
          <text class="stats-label">评论</text>
          <text class="stats-count">{{ stats.commentsCount }}</text>
        </view>
        <view class="stats-divider" />
        <view class="stats-item" @tap="goStats('favorites')">
          <text class="stats-label">收藏</text>
          <text class="stats-count">{{ stats.favoritesCount }}</text>
        </view>
        <view class="stats-divider" />
        <view class="stats-item" @tap="goStats('footprints')">
          <text class="stats-label">足迹</text>
          <text class="stats-count">{{ stats.footprintsCount }}</text>
        </view>
      </view>
    </view>

    <!-- 2. 菜单区（上浮覆盖红头） -->
    <view class="menu-container">
      <view class="menu-card-group">
        <view
          v-for="item in menu1"
          :key="item.action"
          class="menu-item"
          @tap="onMenu(item.action)"
        >
          <view class="menu-item-left">
            <text class="menu-icon">{{ item.icon }}</text>
            <text class="menu-title">{{ item.name }}</text>
          </view>
          <text class="arrow-icon">›</text>
        </view>
      </view>

      <view class="menu-card-group">
        <view
          v-for="item in menu2"
          :key="item.action"
          class="menu-item"
          @tap="onMenu(item.action)"
        >
          <view class="menu-item-left">
            <text class="menu-icon">{{ item.icon }}</text>
            <text class="menu-title">{{ item.name }}</text>
          </view>
          <text class="arrow-icon">›</text>
        </view>
      </view>
    </view>

    <TabBar :current="4" />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import TabBar from '@/components/tab-bar.vue'
import { MINE_USER, MINE_STATS, MINE_MENU_1, MINE_MENU_2 } from '@/utils/mock'
import { myStats } from '@/api/interaction'
import { devLogin } from '@/api/auth'
import { tokenStorage, userStorage } from '@/utils/storage'

const menu1 = MINE_MENU_1
const menu2 = MINE_MENU_2
const user = ref(MINE_USER)
const stats = ref(MINE_STATS)
const loggedIn = ref(tokenStorage.isLoggedIn())

const loadProfile = async () => {
  if (!tokenStorage.isLoggedIn()) return
  const info = userStorage.getUserInfo()
  if (info) {
    user.value = { avatarUrl: '🦅', nickName: info.nickname || MINE_USER.nickName, schoolName: MINE_USER.schoolName }
  }
  try {
    const s = await myStats()
    stats.value = {
      postsCount: s.posts_count,
      commentsCount: s.comments_count,
      favoritesCount: s.favorites_count,
      footprintsCount: s.footprints_count,
    }
  } catch {
    /* 未登录或失败时保留 mock 数据 */
  }
}

const doDevLogin = async () => {
  try {
    const res = await devLogin()
    tokenStorage.setToken(res.access_token)
    userStorage.setUserInfo({
      id: res.user_info.id,
      nickname: res.user_info.nickname,
      role: 'student',
      is_verified: true,
    })
    loggedIn.value = true
    uni.showToast({ title: '已登录（演示）', icon: 'success' })
    await loadProfile()
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '登录失败', icon: 'none' })
  }
}

onShow(() => {
  loadProfile()
})

const goStats = (type: string) => {
  if (type === 'posts') {
    uni.navigateTo({ url: '/pages/my-posts/index' })
    return
  }
  uni.showToast({ title: `${type} 列表（开发中）`, icon: 'none' })
}

const onMenu = (action: string) => {
  uni.showToast({ title: `${action}（开发中）`, icon: 'none' })
}
</script>

<style scoped>
.page-mine {
  background-color: var(--bg-page);
  min-height: 100vh;
}

/* 1. 红头 */
.profile-header-bg {
  background-color: var(--brand-red);
  padding: 40rpx 40rpx 80rpx;
}

.user-info-wrapper {
  display: flex;
  align-items: center;
  margin-top: 20rpx;
}

.avatar-outer-ring {
  width: 136rpx;
  height: 136rpx;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.1);
}

.user-avatar {
  width: 124rpx;
  height: 124rpx;
  border-radius: 50%;
  background-color: #ffffff;
  font-size: 72rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.user-meta-box {
  margin-left: 30rpx;
  display: flex;
  flex-direction: column;
}

.user-nickname {
  color: #ffffff;
  font-size: 38rpx;
  font-weight: bold;
  letter-spacing: 1rpx;
}

.school-tag-capsule {
  align-self: flex-start;
  background-color: rgba(255, 255, 255, 0.22);
  padding: 6rpx 24rpx;
  border-radius: 24rpx;
  margin-top: 14rpx;
}

.school-tag-capsule text {
  color: #ffffff;
  font-size: 22rpx;
  font-weight: 500;
}

.dev-login-capsule {
  align-self: flex-start;
  background-color: #ffffff;
  padding: 8rpx 24rpx;
  border-radius: 24rpx;
  margin-top: 14rpx;
}
.dev-login-capsule text {
  color: var(--brand-red);
  font-size: 22rpx;
  font-weight: 600;
}

.stats-panel-row {
  margin-top: 50rpx;
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 0 10rpx;
}

.stats-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.stats-label {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.75);
  margin-bottom: 12rpx;
}

.stats-count {
  font-size: 34rpx;
  font-weight: bold;
  color: #ffffff;
}

.stats-divider {
  width: 1rpx;
  height: 40rpx;
  background-color: rgba(255, 255, 255, 0.25);
}

/* 2. 菜单区（负 margin 上浮） */
.menu-container {
  margin-top: -36rpx;
  border-top-left-radius: 36rpx;
  border-top-right-radius: 36rpx;
  background-color: var(--bg-page);
  padding: 36rpx 24rpx 0;
}

.menu-card-group {
  background-color: #ffffff;
  border-radius: var(--radius-card);
  padding: 0 32rpx;
  margin-bottom: 24rpx;
}

.menu-item {
  padding: 36rpx 0;
  border-bottom: 1rpx solid #f5f6f7;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.menu-card-group .menu-item:last-child {
  border-bottom: none;
}

.menu-item-left {
  display: flex;
  align-items: center;
}

.menu-icon {
  font-size: 40rpx;
  margin-right: 24rpx;
}

.menu-title {
  font-size: 29rpx;
  color: #2b2b2b;
}

.arrow-icon {
  color: #c8c9cc;
  font-size: 32rpx;
}
</style>
