<template>
  <view class="skeleton-card">
    <view class="sk-avatar" />
    <view class="sk-body">
      <view class="sk-line w45" />
      <view class="sk-line w90" />
      <view class="sk-line w70" />
    </view>
  </view>
</template>

<style scoped>
.skeleton-card {
  /* 主题B（X）：与时间线行一致的黑底骨架 */
  background: var(--bg-page);
  padding: 24rpx 28rpx;
  margin-bottom: 0;
  display: flex;
  gap: 20rpx;
  border-bottom: 1rpx solid var(--border-light);
}
.sk-avatar {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  background: var(--shimmer-gradient);
  background-size: 400% 100%;
  animation: shimmer 1.4s ease infinite;
  flex-shrink: 0;
}
.sk-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  padding-top: 6rpx;
}
.sk-line {
  height: 22rpx;
  border-radius: 12rpx;
  background: var(--shimmer-gradient);
  background-size: 400% 100%;
  animation: shimmer 1.4s ease infinite;
}
.w45 { width: 45%; }
.w70 { width: 70%; }
.w90 { width: 90%; }
@keyframes shimmer {
  0% { background-position: 100% 0; }
  100% { background-position: 0 0; }
}
</style>
