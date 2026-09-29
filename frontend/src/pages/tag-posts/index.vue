<template>
  <view class="page-tag-posts" :class="themeClass">
    <view class="header">
      <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />
      <view class="header-row">
        <text class="back-btn" @tap="goBack">‹</text>
        <text class="header-title">#{{ tagName }}</text>
        <view class="header-right" />
      </view>
    </view>

    <view class="tabs">
      <view
        v-for="t in tabs"
        :key="t.mode"
        class="tab"
        :class="{ on: mode === t.mode }"
        @tap="switchMode(t.mode)"
      >
        {{ t.label }}
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
import { useTheme } from '@/utils/theme'
import { onLoad } from '@dcloudio/uni-app'
import FeedCard from '@/components/feed-card.vue'
import SkeletonCard from '@/components/skeleton-card.vue'
import { getPosts, getFeaturedPosts, getFollowingFeed } from '@/api/posts'
import { tokenStorage } from '@/utils/storage'
import type { PostBrief } from '@/types/api'

const { themeClass } = useTheme()

const statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0
const tagName = ref('')
const mode = ref<'all' | 'latest' | 'following' | 'featured'>('all')
const tabs = [
  { mode: 'all' as const, label: '精选' },
  { mode: 'latest' as const, label: '最新' },
  { mode: 'following' as const, label: '关注' },
  { mode: 'featured' as const, label: '精华' },
]
const posts = ref<PostBrief[]>([])
const cursor = ref<number | null>(null)
const hasMore = ref(false)
const loading = ref(false)

const load = async (refresh = true) => {
  if (loading.value || !tagName.value) return
  loading.value = true
  try {
    const c = refresh ? undefined : (cursor.value ?? undefined)
    let res
    if (mode.value === 'latest') {
      res = await getPosts(c, undefined, undefined, 'time', undefined, tagName.value)
    } else if (mode.value === 'following') {
      if (!tokenStorage.isLoggedIn()) {
        posts.value = []
        uni.showToast({ title: '请先登录', icon: 'none' })
        return
      }
      res = await getFollowingFeed(c, tagName.value)
    } else if (mode.value === 'featured') {
      res = await getFeaturedPosts(c, tagName.value)
    } else {
      res = await getPosts(c, undefined, undefined, undefined, undefined, tagName.value)
    }
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

const switchMode = (m: typeof mode.value) => {
  if (mode.value === m) return
  mode.value = m
  cursor.value = null
  load(true)
}

const loadMore = () => load(false)
const goPost = (id: number) => uni.navigateTo({ url: `/pages/post-detail/index?id=${id}` })
const goBack = () => uni.navigateBack({ fail: () => uni.reLaunch({ url: '/pages/index/index' }) })
</script>

<style scoped>
.page-tag-posts { min-height: 100vh; background-color: var(--bg-page); }

.header { background-color: var(--bg-page); border-bottom: 1rpx solid var(--border-light); }
.header-row { height: 88rpx; display: flex; align-items: center; padding: 0 24rpx; }
.back-btn { font-size: 56rpx; color: var(--text-1); line-height: 1; padding: 0 12rpx; }
.header-title { flex: 1; text-align: center; font-size: 32rpx; font-weight: 700; color: var(--text-1); }
.header-right { width: 80rpx; }

.tabs { display: flex; background: var(--bg-card); padding: 0 16rpx; border-bottom: 1rpx solid var(--border-light); }
.tab { position: relative; flex: 1; text-align: center; font-size: 28rpx; color: var(--text-2); padding: 24rpx 0 20rpx; }
.tab.on { color: var(--text-1); font-weight: bold; }
.tab.on::after { content: ''; position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 56rpx; height: 6rpx; border-radius: 3rpx; background: var(--primary); }

.skeleton-list { padding: 20rpx 24rpx; }
.feed-list { padding: 20rpx 24rpx 40rpx; }
.feed-foot { text-align: center; color: var(--text-3); font-size: 24rpx; padding: 24rpx 0; }
.more { color: var(--primary-strong); }
.empty { text-align: center; color: var(--text-3); font-size: 26rpx; padding: 140rpx 0; }
</style>
