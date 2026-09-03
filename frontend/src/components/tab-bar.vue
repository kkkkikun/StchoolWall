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
      <!-- 自定义图标位（SVG/PNG）：在 CUSTOM_ICONS 里登记后自动生效 -->
      <image
        v-if="customIcon(t.icon, current === i)"
        class="tab-icon-img"
        :src="customIcon(t.icon, current === i)"
        mode="aspectFit"
      />
      <UiIcon v-else :name="t.icon" :size="36" :color="current === i ? COLOR_ACTIVE : COLOR_NORMAL" />
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

/** 选中深黑 / 未选中浅黑（2026-09-02 客户要求弃用粉色高亮） */
const COLOR_ACTIVE = '#111111'
const COLOR_NORMAL = '#a8a8a8'

const tabs = [
  { text: '首页', icon: 'home', path: '/pages/index/index' },
  { text: '组局', icon: 'group', path: '/pages/group/index' },
  { text: '发布', icon: 'publish', path: '/pages/publish/index' },
  { text: '消息', icon: 'message', path: '/pages/message/index' },
  { text: '我的', icon: 'mine', path: '/pages/mine/index' },
] as const

/**
 * 自定义图标映射（预留位）：设计师出图后，把文件放进 src/static/tabbar/，
 * 在下面按 key 登记路径即可整体替换默认字形，无需改模板。
 * 文件要求：PNG（普通态 + 选中态各一张）；mp-weixin 不支持 svg，H5 可用 svg。
 * 例：home: { normal: '/static/tabbar/home.png', active: '/static/tabbar/home-active.png' }
 */
const CUSTOM_ICONS: Record<string, { normal?: string; active?: string }> = {
  // home: { normal: '/static/tabbar/home.png', active: '/static/tabbar/home-active.png' },
  // group: { normal: '/static/tabbar/group.png', active: '/static/tabbar/group-active.png' },
  // publish: { normal: '/static/tabbar/publish.png', active: '/static/tabbar/publish-active.png' },
  // message: { normal: '/static/tabbar/message.png', active: '/static/tabbar/message-active.png' },
  // mine: { normal: '/static/tabbar/mine.png', active: '/static/tabbar/mine-active.png' },
}

const customIcon = (key: string, isActive: boolean) => {
  const conf = CUSTOM_ICONS[key]
  if (!conf) return ''
  return (isActive ? conf.active : conf.normal) || conf.normal || conf.active || ''
}

const onTap = (path: string) => {
  // 不使用原生 tabBar（避免跨平台图标配置差异），用 reLaunch 在 5 个主页面间切换。
  uni.reLaunch({ url: path })
}
</script>

<style scoped>
/* 占位：把页面内容顶高，避免被 fixed 底栏遮挡 */
.tab-bar-placeholder {
  height: calc(84rpx + env(safe-area-inset-bottom));
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
  height: 84rpx;
}

.tab-icon-img {
  width: 36rpx;
  height: 36rpx;
}

.tab-label {
  font-size: 18rpx;
  color: #a8a8a8;
  margin-top: 2rpx;
}

.tab-label.active {
  color: #111111;
  font-weight: bold;
}
</style>
