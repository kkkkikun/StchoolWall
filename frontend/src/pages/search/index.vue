<template>
  <view class="page-search" :class="themeClass">
    <!-- 1. 沉浸式搜索头：兼顾状态栏与微信胶囊安全避让 -->
    <CustomNavBar :border="true" :placeholder="true">
      <template #left>
        <view class="back" @tap="goBack"><text>‹</text></view>
      </template>
      <view class="search-bar">
        <image class="icon" src="/static/icons/common/search.svg" mode="aspectFit" />
        <input
          class="input"
          v-model="keyword"
          placeholder="搜索帖子内容、标签…"
          placeholder-style="color: var(--text-2);"
          confirm-type="search"
          :focus="autoFocus"
          @input="onInput"
          @confirm="doSearch()"
        />
        <image v-if="keyword" class="clear" src="/static/icons/common/close.svg" mode="aspectFit" @tap="clearSearch" />
      </view>
      <template #right>
        <text class="search-btn" @tap="doSearch()">搜索</text>
      </template>
    </CustomNavBar>

    <!-- 2. 搜索前面板：搜索历史 + 热门探索 -->
    <view v-if="!searched" class="search-panel">
      <!-- 搜索历史 -->
      <view v-if="historyList.length" class="panel-section">
        <view class="section-header">
          <text class="section-title">搜索历史</text>
          <text class="clear-history" @tap="clearHistory">清空</text>
        </view>
        <view class="tags-cloud">
          <view
            v-for="(h, idx) in historyList"
            :key="idx"
            class="history-pill"
            @tap="applyKeyword(h)"
          >
            <text class="pill-text">{{ h }}</text>
          </view>
        </view>
      </view>

      <!-- 热门探索 -->
      <view class="panel-section">
        <view class="section-header">
          <text class="section-title">热门搜索</text>
        </view>
        <view class="tags-cloud">
          <view
            v-for="(hot, idx) in HOT_KEYWORDS"
            :key="idx"
            class="hot-pill"
            @tap="applyKeyword(hot)"
          >
            <text class="hot-tag-symbol">#</text>
            <text class="pill-text">{{ hot }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 3. 结果区域 -->
    <view v-else class="result-area">
      <view v-if="loading" class="tip"><text>搜索中…</text></view>
      <view v-else-if="results.length === 0" class="tip">
        <image class="empty-emoji" src="/static/icons/common/search.svg" mode="aspectFit" />
        <text class="empty-text">没有找到“{{ lastQ }}”相关的帖子</text>
        <text class="empty-sub">换个关键词试试，或点击上方热门搜索</text>
      </view>
      <view v-else class="list">
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
import { ref, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useTheme } from '@/utils/theme'
import CustomNavBar from '@/components/custom-nav-bar.vue'
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

const HISTORY_KEY = 'schoolwall_search_history'
const historyList = ref<string[]>([])

const HOT_KEYWORDS = ['二手交易', '失物招领', '校园拼车', '自习搭子', '四六级', '求助', '表白墙']

const loadHistory = () => {
  try {
    const raw = uni.getStorageSync(HISTORY_KEY)
    if (raw && Array.isArray(raw)) {
      historyList.value = raw
    }
  } catch {
    /* 忽略 */
  }
}

const saveHistory = (q: string) => {
  const trimmed = q.trim()
  if (!trimmed) return
  const set = new Set([trimmed, ...historyList.value])
  const updated = Array.from(set).slice(0, 10)
  historyList.value = updated
  try {
    uni.setStorageSync(HISTORY_KEY, updated)
  } catch {
    /* 忽略 */
  }
}

const clearHistory = () => {
  historyList.value = []
  uni.removeStorageSync(HISTORY_KEY)
}

const clearSearch = () => {
  keyword.value = ''
  searched.value = false
  results.value = []
}

const onInput = (e: any) => {
  const val = e?.detail?.value ?? keyword.value
  if (!val || !val.trim()) {
    searched.value = false
    results.value = []
  }
}

const applyKeyword = (q: string) => {
  keyword.value = q
  doSearch(q)
}

const doSearch = async (queryVal?: string) => {
  const q = (queryVal || keyword.value).trim()
  if (!q) return
  loading.value = true
  searched.value = true
  lastQ.value = q
  saveHistory(q)
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

onMounted(loadHistory)

onShow(() => {
  loadHistory()
  const pages = getCurrentPages()
  const cur = pages[pages.length - 1] as any
  const q = cur?.options?.q
  if (q) {
    keyword.value = decodeURIComponent(q)
    autoFocus.value = false
    doSearch()
  } else if (!keyword.value) {
    searched.value = false
    results.value = []
  }
})
</script>

<style scoped>
.page-search {
  min-height: 100vh;
  background: var(--bg-page);
  box-sizing: border-box;
  overflow-x: hidden;
}

.back {
  color: var(--text-1);
  font-size: 52rpx;
  line-height: 1;
  padding: 4rpx 10rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  /* 点击区 ≥64rpx（≈33px） */
  min-width: 64rpx;
  min-height: 64rpx;
}

.search-bar {
  flex: 1;
  width: 100%;
  height: 64rpx;
  background: var(--pill-bg);
  border: 1rpx solid var(--border-light);
  border-radius: var(--radius-btn);
  padding: 0 20rpx;
  display: flex;
  align-items: center;
  margin: 0 8rpx;
  box-sizing: border-box;
}

.icon {
  width: 28rpx;
  height: 28rpx;
  flex-shrink: 0;
}

.input {
  flex: 1;
  font-size: 26rpx;
  margin: 0 12rpx;
  color: var(--text-1);
  background: transparent;
}

.input::placeholder {
  color: var(--text-2);
}

.clear {
  width: 28rpx;
  height: 28rpx;
  padding: 8rpx 12rpx;
  flex-shrink: 0;
}

.search-btn {
  color: var(--primary-text);
  font-size: 28rpx;
  font-weight: 600;
  /* inline-block + 内边距：搜索按钮撑到 64rpx（≈33px）最小点击区 */
  display: inline-block;
  padding: 15rpx 16rpx;
  white-space: nowrap;
}

/* 搜索前推荐面板 */
.search-panel {
  padding: 32rpx 28rpx;
}

.panel-section {
  margin-bottom: 48rpx;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.section-title {
  font-size: 28rpx;
  font-weight: 700;
  color: var(--text-1);
}

.clear-history {
  font-size: 24rpx;
  color: var(--text-2);
  padding: 4rpx 8rpx;
}

.tags-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}

.history-pill {
  background: var(--bg-card-2);
  border: 1rpx solid var(--border-light);
  padding: 12rpx 24rpx;
  border-radius: var(--radius-btn);
  font-size: 26rpx;
  color: var(--text-1);
  word-break: break-all;
  max-width: 100%;
  box-sizing: border-box;
}

.history-pill:active {
  background: var(--hover-fill);
}

.hot-pill {
  background: var(--primary-soft);
  border: 1rpx solid var(--border-primary-soft);
  padding: 12rpx 24rpx;
  border-radius: var(--radius-btn);
  font-size: 26rpx;
  color: var(--primary-text);
  display: flex;
  align-items: center;
  gap: 4rpx;
  word-break: break-all;
  max-width: 100%;
  box-sizing: border-box;
}

.hot-pill:active {
  opacity: 0.8;
}

.hot-tag-symbol {
  font-weight: 700;
}

.pill-text {
  font-size: 26rpx;
}

.result-area {
  padding: 8rpx 0 32rpx;
  overflow-x: hidden;
}

.tip {
  text-align: center;
  color: var(--text-3);
  font-size: 26rpx;
  padding: 160rpx 40rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16rpx;
}

.empty-emoji {
  width: 64rpx;
  height: 64rpx;
  opacity: 0.6;
}

.empty-text {
  color: var(--text-1);
  font-size: 30rpx;
  font-weight: 600;
  word-break: break-word;
}

.empty-sub {
  color: var(--text-2);
  font-size: 24rpx;
}

.list {
  padding: 0;
}
</style>
