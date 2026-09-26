<template>
  <view class="page-tag-posts">
    <view class="header">
      <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />
      <view class="header-row">
        <text class="back-btn" @tap="goBack">‹</text>
        <text class="header-title">#{{ tagName }}</text>
        <view class="header-right" />
      </view>
    </view>

    <view v-if="loading && posts.length === 0" class="skeleton-list">
      <SkeletonCard v-for="i in 3" :key="i" />
    </view>
    <view v-else-if="posts.length === 0" class="empty">
      <text>还没有带 #{{ tagName }} 标签的帖子</text>
    </view>
    <view v-else class="feed-list">
      <FeedCard v-for="p in posts" :key="p.id" :post="p" @detail="goPost(p.id)" />
      <view class="feed-foot">
        <text v-if="loading">加载中…</text>
        <text v-else-if="hasMore" @tap="loadMore" class="more">加载更多</text>
        <text v-else>没有更多了</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import FeedCard from '@/components/feed-card.vue'
import SkeletonCard from '@/components/skeleton-card.vue'
import { getPosts } from '@/api/posts'
import type { PostBrief } from '@/types/api'

const statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0
const tagName = ref('')
const posts = ref<PostBrief[]>([])
const cursor = ref<number | null>(null)
const hasMore = ref(false)
const loading = ref(false)

const load = async (refresh = true) => {
  if (loading.value || !tagName.value) return
  loading.value = true
  try {
    const c = refresh ? undefined : (cursor.value ?? undefined)
    const res = await getPosts(c, undefined, undefined, undefined, undefined, tagName.value)
    posts.value = refresh ? res.items : [...posts.value, ...res.items]
    cursor.value = res.next_cursor
    hasMore.value = res.has_more
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

onLoad((query) => {
  tagName.value = decodeURIComponent(query?.name || '')
  load(true)
})

const loadMore = () => load(false)
const goPost = (id: number) => uni.navigateTo({ url: `/pages/post-detail/index?id=${id}` })
const goBack = () => uni.navigateBack({ fail: () => uni.reLaunch({ url: '/pages/index/index' }) })
</script>

<style scoped>
.page-tag-posts { min-height: 100vh; background-color: var(--bg-page); }

.header { background-color: var(--brand-red); }
.header-row { height: 88rpx; display: flex; align-items: center; padding: 0 24rpx; }
.back-btn { font-size: 56rpx; color: #fff; line-height: 1; padding: 0 12rpx; }
.header-title { flex: 1; text-align: center; font-size: 32rpx; font-weight: bold; color: #fff; }
.header-right { width: 80rpx; }

.skeleton-list { padding: 20rpx 24rpx; }
.feed-list { padding: 20rpx 24rpx 40rpx; }
.feed-foot { text-align: center; color: var(--text-3); font-size: 24rpx; padding: 24rpx 0; }
.more { color: var(--brand-red-dark); }
.empty { text-align: center; color: var(--text-3); font-size: 26rpx; padding: 140rpx 0; }
</style>
