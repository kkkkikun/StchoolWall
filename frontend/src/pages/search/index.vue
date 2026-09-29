<template>
  <view class="page-search" :class="themeClass">
    <!-- 搜索头 -->
    <view class="search-head">
      <view class="back" @tap="goBack"><text>‹</text></view>
      <view class="search-bar">
        <text class="icon">🔍</text>
        <input
          class="input"
          v-model="keyword"
          placeholder="搜索帖子内容…"
          confirm-type="search"
          :focus="autoFocus"
          @confirm="doSearch"
        />
        <text v-if="keyword" class="clear" @tap="keyword = ''">✕</text>
      </view>
      <text class="search-btn" @tap="doSearch">搜索</text>
    </view>

    <!-- 结果 -->
    <view class="result-area">
      <view v-if="loading" class="tip"><text>搜索中…</text></view>
      <view v-else-if="searched && results.length === 0" class="tip">
        <text>没有找到“{{ lastQ }}”相关的帖子</text>
      </view>
      <view v-else-if="!searched" class="tip"><text>输入关键词，搜索校园墙内容</text></view>
      <view class="list">
        <FeedCard
          v-for="p in results"
          :key="p.id"
          :post="p"
          @detail="goDetail"
        />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTheme } from '@/utils/theme'
import FeedCard from '@/components/feed-card.vue'
import type { PostBrief } from '@/types/api'
import { searchPosts } from '@/api/posts'

const { themeClass } = useTheme()

const keyword = ref('')
const lastQ = ref('')
const results = ref<PostBrief[]>([])
const searched = ref(false)
const loading = ref(false)
const autoFocus = ref(true)

const doSearch = async () => {
  const q = keyword.value.trim()
  if (!q) return
  loading.value = true
  searched.value = true
  lastQ.value = q
  try {
    const res = await searchPosts(q)
    results.value = res.items
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '搜索失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

const goDetail = (id: number) => uni.navigateTo({ url: `/pages/post-detail/index?id=${id}` })
const goBack = () => uni.navigateBack()

// 进入时若带 q 参数则直接搜
;(() => {
  const pages = getCurrentPages()
  const cur = pages[pages.length - 1] as any
  const q = cur?.options?.q
  if (q) {
    keyword.value = decodeURIComponent(q)
    autoFocus.value = false
    doSearch()
  }
})()
</script>

<style scoped>
.page-search { min-height: 100vh; background: var(--bg-page); }
.search-head {
  /* 主题B（X）：白/黑底 + 灰填充胶囊搜索框 */
  background: var(--bg-page);
  border-bottom: 1rpx solid var(--border-light);
  padding: 24rpx 24rpx 28rpx;
  display: flex;
  align-items: center;
}
.back { color: var(--text-1); font-size: 44rpx; width: 48rpx; text-align: center; }
.search-bar {
  flex: 1; height: 68rpx; background: var(--pill-bg); border-radius: var(--radius-btn);
  padding: 0 24rpx; display: flex; align-items: center; margin: 0 16rpx;
}
.icon { font-size: 28rpx; color: var(--text-3); }
.input { flex: 1; font-size: 26rpx; margin: 0 12rpx; color: var(--text-1); }
.clear { color: var(--text-3); font-size: 28rpx; }
.search-btn { color: var(--primary); font-size: 28rpx; font-weight: 600; }

.result-area { padding: 16rpx 0; }
.tip { text-align: center; color: var(--text-3); font-size: 26rpx; padding: 120rpx 40rpx; }
.list { padding: 0 24rpx; }
</style>
