<template>
  <view class="page-settings">
    <!-- 账号卡片 -->
    <view class="account-card">
      <view class="avatar" :style="{ background: avatarColor }">
        <text class="avatar-letter">{{ avatarLetter }}</text>
      </view>
      <view class="account-meta">
        <view class="name-row">
          <text class="nickname">{{ user.nickname }}</text>
          <text v-if="user.is_verified" class="v-badge">✅ 已认证</text>
        </view>
        <text class="role-text">{{ roleText }}</text>
      </view>
    </view>

    <!-- 通用设置 -->
    <view class="group-card">
      <view class="group-title"><text>通用</text></view>
      <view class="cell" @tap="onClearCache">
        <view class="cell-left">
          <text class="cell-icon">🧹</text>
          <text class="cell-title">清除缓存</text>
        </view>
        <text class="cell-value">{{ cacheSize }}</text>
      </view>
      <view class="cell" @tap="goInfo('community')">
        <view class="cell-left">
          <text class="cell-icon">🛡️</text>
          <text class="cell-title">社区规范</text>
        </view>
        <text class="arrow">›</text>
      </view>
      <view class="cell" @tap="goInfo('invite')">
        <view class="cell-left">
          <text class="cell-icon">🎁</text>
          <text class="cell-title">邀请校友</text>
        </view>
        <text class="arrow">›</text>
      </view>
      <view class="cell" @tap="goInfo('about')">
        <view class="cell-left">
          <text class="cell-icon">ℹ️</text>
          <text class="cell-title">关于我们</text>
        </view>
        <text class="cell-value">v1.0.0</text>
      </view>
      <view class="cell" @tap="goInfo('contact')">
        <view class="cell-left">
          <text class="cell-icon">📞</text>
          <text class="cell-title">联系我们</text>
        </view>
        <text class="arrow">›</text>
      </view>
    </view>

    <!-- 账号操作 -->
    <view class="group-card">
      <view class="group-title"><text>账号</text></view>
      <view v-if="loggedIn" class="cell danger-cell" @tap="onLogout">
        <view class="cell-left">
          <text class="cell-icon">🚪</text>
          <text class="cell-title danger-text">退出登录</text>
        </view>
      </view>
      <view v-else class="cell" @tap="goLogin">
        <view class="cell-left">
          <text class="cell-icon">🔑</text>
          <text class="cell-title">去登录</text>
        </view>
        <text class="arrow">›</text>
      </view>
    </view>

    <!-- 底部版权 -->
    <text class="footer-text">鄂应墙 · 校园信息撮合平台</text>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { tokenStorage, userStorage } from '@/utils/storage'

const loggedIn = ref(tokenStorage.isLoggedIn())
const user = ref({
  nickname: userStorage.getUserInfo()?.nickname || '未登录',
  is_verified: !!userStorage.getUserInfo()?.is_verified,
})
const cacheSize = ref('计算中…')

const AVATAR_COLORS = ['#ffd591', '#adc6ff', '#b7eb8f', '#ffa39e', '#d3adf7', '#87e8de']
const avatarLetter = computed(() => (user.value.nickname || '?').slice(0, 1))
const avatarColor = computed(() => {
  let h = 0
  const s = user.value.nickname || ''
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[h % AVATAR_COLORS.length]
})

const roleText = computed(() => {
  if (!loggedIn.value) return '游客模式 · 仅可浏览'
  const role = userStorage.getUserInfo()?.role
  if (role === 'admin') return '管理员'
  if (role === 'student') return '已认证学生'
  return '游客'
})

const calcCache = () => {
  try {
    const info = uni.getStorageInfoSync()
    cacheSize.value = `${(info.currentSize / 1024).toFixed(1)} MB`
  } catch {
    cacheSize.value = '—'
  }
}

const onClearCache = () => {
  uni.showModal({
    title: '清除缓存',
    content: '将清除图片缓存等本地数据（不影响登录态和草稿），确定吗？',
    success: (r) => {
      if (!r.confirm) return
      try {
        uni.clearStorageSync()
        // 登录态与用户信息回写（clearStorageSync 全清了）
        const token = tokenStorage.getToken()
        const info = userStorage.getUserInfo()
        if (token) tokenStorage.setToken(token)
        if (info) userStorage.setUserInfo(info)
      } catch { /* 忽略 */ }
      calcCache()
      uni.showToast({ title: '已清除', icon: 'success' })
    },
  })
}

const onLogout = () => {
  uni.showModal({
    title: '退出登录',
    content: `确定退出「${user.value.nickname}」吗？`,
    confirmText: '退出',
    confirmColor: '#f73b43',
    success: (r) => {
      if (!r.confirm) return
      tokenStorage.removeToken()
      userStorage.removeUserInfo()
      loggedIn.value = false
      user.value = { nickname: '未登录', is_verified: false }
      uni.showToast({ title: '已退出', icon: 'success' })
      setTimeout(() => uni.navigateBack(), 600)
    },
  })
}

const goLogin = () => {
  uni.navigateBack()
  uni.showToast({ title: '请到「我的」页登录', icon: 'none' })
}

const goInfo = (type: 'community' | 'invite' | 'about' | 'contact') => {
  uni.navigateTo({ url: `/pages/info/index?type=${type}` })
}


onShow(() => {
  loggedIn.value = tokenStorage.isLoggedIn()
  const info = userStorage.getUserInfo()
  user.value = {
    nickname: info?.nickname || '未登录',
    is_verified: !!info?.is_verified,
  }
  calcCache()
})
</script>

<style scoped>
.page-settings {
  min-height: 100vh;
  background: var(--bg-page);
  padding: 24rpx 24rpx 60rpx;
}

.account-card {
  background: var(--brand-red);
  border-radius: var(--radius-card);
  padding: 36rpx 32rpx;
  display: flex;
  align-items: center;
}
.avatar {
  width: 110rpx;
  height: 110rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 6rpx rgba(255, 255, 255, 0.35);
}
.avatar-letter { font-size: 52rpx; font-weight: bold; color: #fff; }
.account-meta { margin-left: 26rpx; flex: 1; }
.name-row { display: flex; align-items: center; gap: 12rpx; }
.nickname { color: #fff; font-size: 36rpx; font-weight: bold; }
.v-badge { font-size: 20rpx; color: rgba(255, 255, 255, 0.9); }
.role-text { color: rgba(255, 255, 255, 0.8); font-size: 24rpx; margin-top: 8rpx; }

.group-card {
  background: #fff;
  border-radius: var(--radius-card);
  margin-top: 24rpx;
  padding: 0 32rpx;
}
.group-title {
  font-size: 24rpx;
  color: var(--text-3);
  padding: 28rpx 0 8rpx;
}
.cell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 30rpx 0;
  border-bottom: 1rpx solid #f5f6f7;
}
.group-card .cell:last-child { border-bottom: none; }
.cell-left { display: flex; align-items: center; }
.cell-icon { font-size: 36rpx; margin-right: 22rpx; }
.cell-title { font-size: 29rpx; color: #2b2b2b; }
.cell-value { font-size: 24rpx; color: var(--text-3); }
.arrow { font-size: 32rpx; color: #c8c9cc; }
.danger-cell .cell-title.danger-text { color: var(--brand-red); }

.footer-text {
  display: block;
  text-align: center;
  color: var(--text-3);
  font-size: 22rpx;
  margin-top: 48rpx;
}
</style>
