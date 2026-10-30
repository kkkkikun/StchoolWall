<template>
  <view class="page" :class="themeClass">
    <text class="hint">屏蔽后，双方的内容与互动将受限制。解除仅取消你发起的屏蔽。</text>
    <view v-for="item in items" :key="item.id" class="row">
      <text class="name">{{ item.nickname || '用户' }}</text>
      <button size="mini" :disabled="busyId === item.id" @tap="remove(item)">解除屏蔽</button>
    </view>
    <text v-if="!loading && !items.length" class="empty">暂无屏蔽的用户</text>
    <button v-if="hasMore" :loading="loading" :disabled="loading" @tap="load(true)">加载更多</button>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useTheme } from '@/utils/theme'
import { listBlockedUsers, unblockUser, type BlockedUser } from '@/api/blocks'
const { themeClass } = useTheme()
const items = ref<BlockedUser[]>([])
const hasMore = ref(false)
const cursor = ref<string | null>(null)
const loading = ref(false)
const busyId = ref('')
const load = async (append = false) => {
  if (loading.value) return
  loading.value = true
  try {
    const result = await listBlockedUsers(append ? cursor.value || undefined : undefined)
    items.value = append ? [...items.value, ...result.items] : result.items
    cursor.value = result.next_cursor
    hasMore.value = result.has_more
  } catch (error) { uni.showToast({ title: (error as Error).message, icon: 'none' }) }
  finally { loading.value = false }
}
const remove = (item: BlockedUser) => {
  uni.showModal({ title: '解除屏蔽', content: `解除对「${item.nickname || '该用户'}」的屏蔽？对方发起的屏蔽仍然有效。`,
    success: async (result) => {
      if (!result.confirm) return
      busyId.value = item.id
      try { await unblockUser(item.id); items.value = items.value.filter((row) => row.id !== item.id) }
      catch (error) { uni.showToast({ title: (error as Error).message, icon: 'none' }) }
      finally { busyId.value = '' }
    } })
}
onShow(() => load())
</script>

<style scoped>
.page { min-height: 100vh; background: var(--bg-page); padding: 32rpx; }
.hint, .empty { display: block; color: var(--text-3); font-size: 26rpx; line-height: 1.7; padding: 20rpx 0; }
.row { display: flex; align-items: center; gap: 24rpx; padding: 28rpx 0; border-bottom: 1rpx solid var(--border-light); }
.name { flex: 1; color: var(--text-1); font-size: 30rpx; }
button { color: var(--primary); background: var(--bg-card); }
</style>
