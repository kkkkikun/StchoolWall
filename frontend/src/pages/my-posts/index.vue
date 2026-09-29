<template>
  <view class="container" :class="themeClass">
    <view class="type-tabs">
      <view
        v-for="tab in tabs"
        :key="tab.value"
        class="tab"
        :class="{ active: currentStatus === tab.value }"
        @tap="switchStatus(tab.value)"
      >
        {{ tab.label }}
      </view>
    </view>

    <scroll-view class="scroll-container" scroll-y>
      <view v-if="loading" class="loading">
        <text>加载中...</text>
      </view>
      <view v-else-if="posts.length === 0" class="empty">
        <text>暂无帖子</text>
      </view>
      <view v-else>
        <post-card v-for="post in posts" :key="post.id" :post="post" />
      </view>
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useTheme } from '@/utils/theme'
import type { PostBrief } from '@/types/api'
import { get } from '@/utils/request'
import PostCard from '@/components/post-card.vue'

const { themeClass } = useTheme()

interface Tab {
  label: string
  value: string
}

const tabs: Tab[] = [
  { label: '全部', value: '' },
  { label: '正常', value: '1' },
  { label: '审核中', value: '0' },
  { label: '已归档', value: '2' },
  { label: '封禁', value: '-1' },
]

const posts = ref<PostBrief[]>([])
const currentStatus = ref('')
const loading = ref(false)

const loadPosts = async () => {
  loading.value = true
  try {
    const res = await get<{ items: PostBrief[] }>('/posts/my', {
      status: currentStatus.value || undefined,
    })
    posts.value = res.items
  } catch (e) {
    uni.showToast({ title: (e as Error).message, icon: 'none' })
  } finally {
    loading.value = false
  }
}

const switchStatus = (status: string) => {
  if (currentStatus.value === status) return
  currentStatus.value = status
  loadPosts()
}

onMounted(() => {
  loadPosts()
})
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: var(--bg-card-2);
  display: flex;
  flex-direction: column;
}

/* 与首页吸顶 Tab 同规格：左对齐下划线式，弃用蓝色药丸 */
.type-tabs {
  display: flex;
  background: var(--bg-card);
  padding: 16rpx 24rpx;
  gap: 36rpx;
}

.tab {
  font-size: 28rpx;
  color: var(--text-2);
  padding-bottom: 12rpx;
}

.tab.active {
  color: var(--text-1);
  font-weight: bold;
  border-bottom: 6rpx solid var(--primary);
}

.scroll-container {
  flex: 1;
}

.loading, .empty {
  text-align: center;
  padding: 80rpx 0;
  color: var(--text-3);
  font-size: 26rpx;
}
</style>
