<template>
  <view class="tab-bar-placeholder" />
  <view class="tab-bar">
    <view
      v-for="(t, i) in tabs"
      :key="t.path"
      class="tab-item"
      :class="{ active: current === i }"
      @tap="onTap(t.path)"
    >
      <UiIcon
        :name="t.icon"
        :size="44"
        :color="current === i ? '#f73b43' : '#7f8c8d'"
      />
      <text class="tab-label" :class="{ active: current === i }">{{ t.text }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import UiIcon from './ui-icon.vue'

interface Props {
  /** 当前高亮的 tab 序号 0-4 */
  current: number
}
defineProps<Props>()

const tabs = [
  { text: '首页', icon: 'home', path: '/pages/index/index' },
  { text: '组局', icon: 'group', path: '/pages/group/index' },
  { text: '发布', icon: 'publish', path: '/pages/publish/index' },
  { text: '消息', icon: 'message', path: '/pages/message/index' },
  { text: '我的', icon: 'mine', path: '/pages/mine/index' },
] as const

const onTap = (path: string) => {
  // 不使用原生 tabBar（避免跨平台图标配置差异），用 reLaunch 在 5 个主页面间切换。
  uni.reLaunch({ url: path })
}
</script>

<style scoped>
/* 占位：把页面内容顶高，避免被 fixed 底栏遮挡 */
.tab-bar-placeholder {
  height: calc(100rpx + env(safe-area-inset-bottom));
}

.tab-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 999;
  display: flex;
  background-color: #ffffff;
  border-top: 1rpx solid #f0f0f0;
  padding-bottom: env(safe-area-inset-bottom);
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100rpx;
}

.tab-label {
  font-size: 20rpx;
  color: #7f8c8d;
  margin-top: 4rpx;
}

.tab-label.active {
  color: #f73b43;
  font-weight: bold;
}
</style>
