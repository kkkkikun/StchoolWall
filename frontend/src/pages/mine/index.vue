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
          <view v-if="!loggedIn" class="dev-login-row">
            <view class="dev-login-capsule" @tap="doDevLogin(false)">
              <text>一键登录（演示学生）</text>
            </view>
            <view class="dev-login-capsule admin" @tap="doDevLogin(true)">
              <text>🛡️ 演示管理员</text>
            </view>
          </view>
          <view v-if="loggedIn && !isVerified" class="verify-capsule" @tap="goVerify">
            <text>🎓 学籍认证（发帖/互动需认证）</text>
          </view>
        </view>
      </view>

      <!-- 5 列统计（含关注/粉丝） -->
      <view class="stats-panel-row">
        <view class="stats-item" @tap="goStats('posts')">
          <text class="stats-label">帖子</text>
          <text class="stats-count">{{ profileStats.posts_count }}</text>
        </view>
        <view class="stats-divider" />
        <view class="stats-item" @tap="goMyProfile('following')">
          <text class="stats-label">关注</text>
          <text class="stats-count">{{ profileStats.following_count }}</text>
        </view>
        <view class="stats-divider" />
        <view class="stats-item" @tap="goMyProfile('followers')">
          <text class="stats-label">粉丝</text>
          <text class="stats-count">{{ profileStats.followers_count }}</text>
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
      <!-- 管理后台入口（仅 admin 可见） -->
      <view v-if="isAdmin" class="admin-entry-card" @tap="goAdmin">
        <view class="menu-item-left">
          <text class="menu-icon">🛡️</text>
          <text class="menu-title admin-title">管理后台</text>
        </view>
        <text class="arrow-icon">›</text>
      </view>

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
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import TabBar from '@/components/tab-bar.vue'
import { MINE_USER, MINE_STATS, MINE_MENU_1, MINE_MENU_2 } from '@/utils/mock'
import { myStats } from '@/api/interaction'
import { devLogin } from '@/api/auth'
import { getProfile, type UserProfile } from '@/api/profile'
import { tokenStorage, userStorage } from '@/utils/storage'

const menu1 = MINE_MENU_1
const menu2 = MINE_MENU_2
const user = ref(MINE_USER)
const stats = ref(MINE_STATS)
const profileStats = ref({ posts_count: 0, following_count: 0, followers_count: 0 })
const loggedIn = ref(tokenStorage.isLoggedIn())
const isVerified = ref(!!userStorage.getUserInfo()?.is_verified)
const isAdmin = computed(() => userStorage.getUserInfo()?.role === 'admin')

const loadProfile = async () => {
  if (!tokenStorage.isLoggedIn()) return
  const info = userStorage.getUserInfo()
  if (info) {
    user.value = { avatarUrl: '🦅', nickName: info.nickname || MINE_USER.nickName, schoolName: MINE_USER.schoolName }
    isVerified.value = !!info.is_verified
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
  // 关注/粉丝计数走公开资料接口（自己也是一份资料）
  if (info?.id) {
    try {
      const p: UserProfile = await getProfile(info.id)
      profileStats.value = {
        posts_count: p.posts_count,
        following_count: p.following_count,
        followers_count: p.followers_count,
      }
    } catch { /* 忽略 */ }
  }
}

const doDevLogin = async (asAdmin: boolean) => {
  try {
    const res = await devLogin(asAdmin)
    tokenStorage.setToken(res.access_token)
    userStorage.setUserInfo({
      id: res.user_info.id,
      nickname: res.user_info.nickname,
      // role 用后端下发（演示管理员/学生），不再写死
      role: res.role,
      is_verified: res.user_info.is_verified,
    })
    loggedIn.value = true
    isVerified.value = !!res.user_info.is_verified
    uni.showToast({ title: asAdmin ? '已登录（管理员）' : '已登录（演示）', icon: 'success' })
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

const goVerify = () => uni.navigateTo({ url: '/pages/verify/index' })

const goAdmin = () => uni.navigateTo({ url: '/pages/admin/index' })

const goMyProfile = (section: string) => {
  const id = userStorage.getUserInfo()?.id
  if (!id) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  uni.navigateTo({ url: `/pages/profile/index?id=${id}&section=${section}` })
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

.dev-login-row {
  display: flex;
  gap: 16rpx;
  margin-top: 14rpx;
}
.dev-login-capsule {
  align-self: flex-start;
  background-color: #ffffff;
  padding: 8rpx 24rpx;
  border-radius: 24rpx;
  margin-top: 14rpx;
}
.dev-login-row .dev-login-capsule {
  margin-top: 0;
}
.dev-login-capsule.admin {
  background-color: rgba(255, 255, 255, 0.22);
}
.dev-login-capsule.admin text {
  color: #ffffff;
}
.dev-login-capsule text {
  color: var(--brand-red);
  font-size: 22rpx;
  font-weight: 600;
}
.verify-capsule {
  align-self: flex-start;
  background-color: rgba(255, 255, 255, 0.22);
  padding: 8rpx 24rpx;
  border-radius: 24rpx;
  margin-top: 14rpx;
}
.verify-capsule text {
  color: #ffffff;
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

.admin-entry-card {
  background-color: #ffffff;
  border-radius: var(--radius-card);
  padding: 0 32rpx;
  margin-bottom: 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-left: 8rpx solid var(--brand-red);
}
.admin-title {
  color: var(--brand-red);
  font-weight: 600;
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
