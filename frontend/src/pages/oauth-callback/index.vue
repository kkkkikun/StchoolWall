<template>
  <view class="page-oauth" :class="themeClass">
    <view class="card">
      <text class="title">{{ statusText }}</text>
      <text class="desc">正在完成微信登录，请稍候…</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTheme } from '@/utils/theme'
import { onLoad } from '@dcloudio/uni-app'
import { mpLogin } from '@/api/auth'
import { tokenStorage, userStorage } from '@/utils/storage'

const { themeClass } = useTheme()

const statusText = ref('微信登录中…')

function readCodeFromUrl(): string {
  // 兼容两种回跳形态：WeChat 可能把 code 放在 query，SPA hash 路由时也可能落在 hash 里
  const search = new URLSearchParams(window.location.search)
  let code = search.get('code') || ''
  if (!code && window.location.hash.includes('?')) {
    const hashQuery = new URLSearchParams(window.location.hash.split('?')[1])
    code = hashQuery.get('code') || ''
  }
  return code
}

onLoad(async () => {
  const code = readCodeFromUrl()
  if (!code) {
    statusText.value = '登录失败：缺少微信授权参数'
    setTimeout(() => uni.reLaunch({ url: '/pages/index/index' }), 1500)
    return
  }
  try {
    const data = await mpLogin(code)
    tokenStorage.setToken(data.access_token)
    userStorage.setUserInfo({
      id: data.user_info.id,
      nickname: data.user_info.nickname,
      role: data.role,
      is_verified: data.user_info.is_verified,
    })
    statusText.value = '登录成功'
    setTimeout(() => uni.reLaunch({ url: '/pages/index/index' }), 400)
  } catch (e) {
    statusText.value = '登录失败，请重试'
    setTimeout(() => uni.reLaunch({ url: '/pages/index/index' }), 1200)
  }
})
</script>

<style scoped>
.page-oauth {
  min-height: 100vh;
  background: var(--bg-page);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40rpx;
}
.card {
  background: var(--bg-card);
  border-radius: var(--radius-card);
  padding: 60rpx 40rpx;
  width: 100%;
  text-align: center;
}
.title {
  display: block;
  font-size: 34rpx;
  font-weight: bold;
  color: var(--text-1);
}
.desc {
  display: block;
  margin-top: 20rpx;
  font-size: 26rpx;
  color: var(--text-3);
}
</style>
