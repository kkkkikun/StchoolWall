<template>
  <view class="tab-bar-placeholder" />
  <view class="tab-bar">
    <view
      v-for="(t, i) in tabs"
      :key="t.path"
      class="tab-item"
      :class="{ active: current === i }"
      @tap="onTap(t.path, i)"
    >
      <view class="icon-wrap">
        <!-- 优先使用清晰优雅的矢量图标 -->
        <image
          v-if="customIcon(t.icon, current === i)"
          class="tab-icon-img"
          :src="customIcon(t.icon, current === i)"
          mode="aspectFit"
        />
        <UiIcon v-else :name="t.icon" :size="40" />
        <!-- 消息 Tab 未读角标 -->
        <view v-if="t.icon === 'message' && unreadCount > 0" class="tab-badge">
          <text class="tab-badge-text">{{ unreadCount > 99 ? '99+' : unreadCount }}</text>
        </view>
      </view>
      <text class="tab-label" :class="{ active: current === i }">{{ t.text }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import UiIcon from './ui-icon.vue'
import { tokenStorage } from '@/utils/storage'
import { unreadSummary } from '@/api/notification'

interface Props {
  /** 当前高亮的 tab 序号 0-4 */
  current: number
}
const props = defineProps<Props>()

const tabs = [
  { text: '首页', icon: 'home', path: '/pages/index/index' },
  { text: '组局', icon: 'group', path: '/pages/group/index' },
  { text: '发布', icon: 'publish', path: '/pages/publish/index' },
  { text: '消息', icon: 'message', path: '/pages/message/index' },
  { text: '我的', icon: 'mine', path: '/pages/mine/index' },
] as const

/** 精致矢量图标映射 */
const CUSTOM_ICONS: Record<string, { normal?: string; active?: string }> = {
  home: { normal: '/static/tabbar/home.svg', active: '/static/tabbar/home-active.svg' },
  group: { normal: '/static/tabbar/group.svg', active: '/static/tabbar/group-active.svg' },
  publish: { normal: '/static/tabbar/publish.svg', active: '/static/tabbar/publish-active.svg' },
  message: { normal: '/static/tabbar/message.svg', active: '/static/tabbar/message-active.svg' },
  mine: { normal: '/static/tabbar/mine.svg', active: '/static/tabbar/mine-active.svg' },
}

const customIcon = (key: string, isActive: boolean) => {
  const conf = CUSTOM_ICONS[key]
  if (!conf) return ''
  return (isActive ? conf.active : conf.normal) || conf.normal || conf.active || ''
}

const unreadCount = ref(0)
const loadUnread = async () => {
  if (!tokenStorage.isLoggedIn()) return
  try {
    const s = await unreadSummary()
    const total = (s.comment || 0) + (s.like || 0) + (s.favorite || 0) + (s.group || 0) + (s.moderation || 0)
    unreadCount.value = total
  } catch {
    /* 静默 */
  }
}

onMounted(loadUnread)

const onTap = (path: string, index: number) => {
  // 点击当前正停留的 tab：平滑滚动回顶部，绝不 reload 重创页面
  if (props.current === index) {
    uni.pageScrollTo({ scrollTop: 0, duration: 250 })
    return
  }
  // 用 redirectTo 替换顶层页面，避免 reLaunch 全量清空 App 上下文
  uni.redirectTo({
    url: path,
    fail: () => {
      uni.reLaunch({ url: path })
    },
  })
}
</script>

<style scoped>
/* 占位：把页面内容顶高，避免被 fixed 底栏遮挡 */
.tab-bar-placeholder {
  height: calc(96rpx + env(safe-area-inset-bottom));
}

.tab-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 999;
  display: flex;
  background-color: var(--bg-page);
  border-top: 1rpx solid var(--border-light);
  padding-bottom: env(safe-area-inset-bottom);
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 96rpx;
  color: var(--text-2);
}
.tab-item.active {
  color: var(--primary);
}

.icon-wrap {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48rpx;
  height: 48rpx;
}

.tab-icon-img {
  width: 44rpx;
  height: 44rpx;
}

.tab-badge {
  position: absolute;
  top: -4rpx;
  right: -12rpx;
  background-color: #f4212e;
  border-radius: 20rpx;
  padding: 2rpx 8rpx;
  min-width: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tab-badge-text {
  color: #ffffff;
  font-size: 22rpx;
  font-weight: 700;
  line-height: 1;
}

.tab-label {
  font-size: 22rpx;
  color: inherit;
  margin-top: 2rpx;
}

.tab-label.active {
  color: var(--primary);
  font-weight: 700;
}
</style>
