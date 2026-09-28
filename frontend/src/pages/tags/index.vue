<template>
  <view class="container">
    <view class="tags-grid">
      <view
        v-for="tag in tags"
        :key="tag.id"
        class="tag-card"
        @tap="selectTag(tag.id)"
      >
        <text class="tag-name">#{{ tag.name }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { Tag } from '@/types/api'
import { getTags } from '@/api/tags'

const tags = ref<Tag[]>([])

const selectTag = (tagId: number) => {
  uni.navigateBack({
    success: () => {
      const pages = getCurrentPages()
      const prevPage = pages[pages.length - 1] as any
      if (prevPage && prevPage.$vm && prevPage.$vm.onTagSelect) {
        prevPage.$vm.onTagSelect(tagId)
      }
    },
  })
}

onMounted(async () => {
  try {
    tags.value = await getTags()
  } catch (e) {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
})
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: var(--bg-card-2);
  padding: 20rpx;
}

.tags-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}

.tag-card {
  background: var(--bg-card);
  padding: 24rpx 32rpx;
  border-radius: 40rpx;
  box-shadow: var(--shadow-card);
}

.tag-name {
  font-size: 28rpx;
  color: var(--text-1);
}
</style>
