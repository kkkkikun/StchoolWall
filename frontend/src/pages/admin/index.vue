<template>
  <view class="page-admin-deprecated" :class="themeClass">
    <view class="card">
      <image class="icon" src="/static/icons/state/desktop.svg" mode="aspectFit" />
      <text class="title">管理后台已升级</text>
      <text class="desc">精细化管理已迁移到独立的 Web 管理后台，请在电脑浏览器中访问：</text>
      <view class="url-box" @tap="copyUrl">
        <text class="url">{{ adminUrl }}</text>
        <text class="copy-tip">点击复制</text>
      </view>
      <text class="hint">使用管理员账号密码登录（首次使用请在后端执行 python -m app.create_admin 创建账号）</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { useTheme } from '@/utils/theme'

const { themeClass } = useTheme()
// 旧的内嵌管理页已下线（2026-08-31），运营管理统一走独立 Web 管理后台。
// 保留本页作为入口提示，避免旧版本用户的直达链接 404。
const adminUrl = import.meta.env.VITE_ADMIN_BASE_URL || location.origin + '/admin/'
const copyUrl = () => {
  uni.setClipboardData({ data: adminUrl })
}
</script>

<style scoped>
.page-admin-deprecated {
  min-height: 100vh;
  background: var(--bg-page);
  padding: 80rpx 40rpx;
}
.card {
  background: var(--bg-card);
  border-radius: var(--radius-card);
  padding: 60rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.icon { width: 80rpx; height: 80rpx; }
.title { font-size: 34rpx; font-weight: bold; color: var(--text-1); margin-top: 24rpx; }
.desc { font-size: 26rpx; color: var(--text-3); margin-top: 16rpx; text-align: center; line-height: 1.6; }
.url-box {
  margin-top: 32rpx;
  background: var(--bg-page);
  border-radius: 12rpx;
  padding: 24rpx 32rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.url { font-size: 30rpx; color: var(--primary-text); font-weight: 600; }
.copy-tip { font-size: 22rpx; color: var(--text-3); margin-top: 8rpx; }
.hint { font-size: 22rpx; color: var(--text-3); margin-top: 32rpx; text-align: center; }
</style>
