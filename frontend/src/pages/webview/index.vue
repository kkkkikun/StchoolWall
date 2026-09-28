<template>
  <view class="page-webview">
    <view v-if="!url" class="invalid">
      <text class="invalid-emoji">🔗</text>
      <text class="invalid-text">链接无效</text>
    </view>

    <!-- H5 用 iframe；小程序/App 用系统 web-view -->
    <!-- #ifdef H5 -->
    <iframe v-if="url" class="web-frame" :src="url" />
    <!-- #endif -->
    <!-- #ifndef H5 -->
    <web-view v-if="url" :src="url" />
    <!-- #endif -->

    <view v-if="url" class="hint">若上方页面空白，说明对方网站禁止被嵌入，请点「在浏览器打开」</view>

    <view class="toolbar">
      <view class="tool-btn" @tap="copyLink">
        <text>复制链接</text>
      </view>
      <!-- #ifdef H5 -->
      <view class="tool-btn primary" @tap="openExternal">
        <text>在浏览器打开</text>
      </view>
      <!-- #endif -->
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'

const url = ref('')

const normalizeUrl = (raw: string) => {
  const t = raw.trim()
  if (!t) return ''
  return /^https?:\/\//i.test(t) ? t : `https://${t}`
}

onLoad((options) => {
  // url 参数需 encodeURIComponent 传入；兼容未带协议的链接
  url.value = normalizeUrl(decodeURIComponent(options?.url || ''))
})

const copyLink = () => {
  if (!url.value) return
  uni.setClipboardData({ data: url.value })
}

// H5：iframe 被目标站点 X-Frame-Options/CSP 拦截时，直接跳到系统浏览器
const openExternal = () => {
  if (!url.value) return
  const win = window.open(url.value, '_blank', 'noopener,noreferrer')
  if (!win) window.location.href = url.value
}
</script>

<style scoped>
.page-webview {
  height: 100vh;
  min-height: 100vh;
  background: var(--bg-page);
  display: flex;
  flex-direction: column;
}

.web-frame {
  flex: 1;
  min-height: 0;
  width: 100%;
  border: 0;
  display: block;
}

.invalid {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.invalid-emoji { font-size: 96rpx; margin-bottom: 24rpx; opacity: 0.5; }
.invalid-text { font-size: 28rpx; color: var(--text-3); }

.hint {
  padding: 14rpx 24rpx;
  font-size: 22rpx;
  color: var(--text-3);
  background: var(--warning-soft);
  flex-shrink: 0;
}

.toolbar {
  height: 100rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24rpx;
  background: var(--bg-card);
  border-top: 1rpx solid var(--border-light);
  flex-shrink: 0;
}
.tool-btn {
  padding: 14rpx 40rpx;
  border: 2rpx solid var(--border-strong);
  border-radius: 999rpx;
  font-size: 26rpx;
  color: var(--text-1);
}
.tool-btn.primary {
  border-color: var(--primary);
  color: var(--primary-strong);
}
</style>
