<template>
  <view class="custom-nav-wrapper">
    <!-- 固定/非固定定位导航栏 -->
    <view
      class="custom-nav-bar"
      :class="[
        themeClass,
        {
          'is-fixed': fixed,
          'has-border': border,
        },
      ]"
      :style="{
        backgroundColor: background || 'var(--bg-page)',
        zIndex: zIndex,
      }"
    >
      <!-- 1. 状态栏安全占位 -->
      <view
        class="nav-status-bar"
        :style="{ height: metrics.statusBarHeight + 'px' }"
      />

      <!-- 2. 内容栏（自动右内边距避让胶囊） -->
      <view
        class="nav-content-row"
        :style="{
          height: metrics.navBarHeight + 'px',
          paddingRight: metrics.capsulePaddingRight + 'px',
        }"
      >
        <!-- 左侧区域：默认返回按钮，支持 slot="left" 覆盖 -->
        <view class="nav-left" @tap="handleBack">
          <slot name="left">
            <view v-if="showBack" class="back-trigger">
              <image class="back-arrow" src="/static/icons/common/back.svg" mode="aspectFit" />
              <text v-if="backText" class="back-label">{{ backText }}</text>
            </view>
          </slot>
        </view>

        <!-- 中间标题/自定义内容区域 -->
        <view class="nav-center">
          <slot>
            <text v-if="title" class="nav-title" :style="{ color: textColor || 'var(--text-1)' }">{{ title }}</text>
          </slot>
        </view>

        <!-- 右侧操作区：slot="right" -->
        <view class="nav-right">
          <slot name="right" />
        </view>
      </view>
    </view>

    <!-- 3. 文档流占位块：防止下方页面内容被 fixed 导航栏遮挡 -->
    <view
      v-if="fixed && placeholder"
      class="nav-placeholder"
      :style="{ height: metrics.totalHeight + 'px' }"
    />
  </view>
</template>

<script setup lang="ts">
import { computed, getCurrentInstance } from 'vue'
import { useTheme } from '@/utils/theme'
import { getNavBarMetrics, safeNavigateBack, acquireNavLock } from '@/utils/navbar'

const props = withDefaults(
  defineProps<{
    title?: string
    showBack?: boolean
    backText?: string
    background?: string
    border?: boolean
    fixed?: boolean
    placeholder?: boolean
    textColor?: string
    zIndex?: number
    fallbackUrl?: string
  }>(),
  {
    title: '',
    showBack: false,
    backText: '',
    background: '',
    border: true,
    fixed: true,
    placeholder: true,
    textColor: '',
    zIndex: 990,
    fallbackUrl: '/pages/index/index',
  }
)

const emit = defineEmits<{
  (e: 'back'): void
}>()

const { themeClass } = useTheme()
const metrics = computed(() => getNavBarMetrics())
const instance = getCurrentInstance()

const handleBack = () => {
  if (!props.showBack) return

  // 1. 若父组件监听了 @back 事件，由父组件负责返回逻辑，在此获取导航锁防快速连击
  if (instance?.vnode?.props?.onBack) {
    if (!acquireNavLock()) return
    emit('back')
    return
  }

  // 2. 无父监听器时：直接由 safeNavigateBack 执行默认安全返回（在 safeNavigateBack 内部获取导航锁）
  safeNavigateBack(props.fallbackUrl)
}
</script>

<style scoped>
.custom-nav-bar {
  width: 100%;
  box-sizing: border-box;
}

.custom-nav-bar.is-fixed {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
}

.custom-nav-bar.has-border {
  border-bottom: 1rpx solid var(--border-light);
}

.nav-status-bar {
  width: 100%;
  box-sizing: border-box;
}

.nav-content-row {
  width: 100%;
  display: flex;
  align-items: center;
  box-sizing: border-box;
  padding-left: 20rpx;
  position: relative;
}

.nav-left {
  display: flex;
  align-items: center;
  min-height: 100%;
  z-index: 2;
}

.back-trigger {
  display: flex;
  align-items: center;
  padding: 8rpx 12rpx;
}

.back-arrow {
  width: 40rpx;
  height: 40rpx;
  flex-shrink: 0;
}

.back-label {
  font-size: 26rpx;
  color: var(--text-2);
  margin-left: 4rpx;
}

.nav-center {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 10rpx;
  z-index: 1;
}

.nav-title {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-height: 100%;
  z-index: 2;
}
</style>
