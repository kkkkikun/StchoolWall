<template>
  <view class="page-webview">
    <web-view :src="url" />
    <!-- web-view 失败兜底（域名未配业务域名等场景） -->
    <view class="fallback" @tap="copyLink">
      <text>打不开？点此复制链接</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'

const url = ref('')

onLoad((options) => {
  // url 参数需 encodeURIComponent 传入
  url.value = decodeURIComponent(options?.url || '')
})

const copyLink = () => {
  if (!url.value) return
  uni.setClipboardData({ data: url.value })
}
</script>

<style scoped>
.page-webview {
  min-height: 100vh;
  background: var(--bg-page);
}
web-view {
  width: 100%;
  height: calc(100vh - 88rpx);
}
.fallback {
  height: 88rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border-top: 1rpx solid #eee;
}
.fallback text {
  font-size: 26rpx;
  color: var(--text-3);
}
</style>
