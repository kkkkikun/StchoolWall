<template>
  <view class="page-hot" :class="themeClass">
    <!-- 1. 头部（与首页/互动页同款粉色沉浸头） -->
    <view class="header">
      <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />
      <view class="header-row">
        <text class="back-btn" @tap="goBack">‹</text>
        <text class="header-title">十大热帖</text>
        <view class="header-right" />
      </view>
    </view>

    <!-- 2. 规则说明条 -->
    <view class="intro-bar">
      <text class="intro-text">🔥 近 7 天 · 赞×3 + 评论×2 + 浏览 加权排序</text>
    </view>

    <!-- 3. 完整榜单 -->
    <view v-if="loading" class="state"><text>加载中…</text></view>
    <view v-else-if="!items.length" class="state">
      <text class="state-emoji">🧊</text>
      <text>本周还没有热帖，发一帖点燃它吧</text>
    </view>
    <view v-else class="rank-card">
      <view
        v-for="it in items"
        :key="it.id"
        class="rank-row"
        :class="{ top3: it.rank <= 3 }"
        @tap="goPost(it.id)"
      >
        <text class="rank" :class="rankClass(it.rank)">{{ it.rank }}</text>
        <view class="mid">
          <view class="line1">
            <text class="title">{{ it.title }}</text>
            <text v-if="it.isHot" class="hot-tag">热</text>
          </view>
          <view class="line2">
            <text class="meta">♡ {{ it.likes }} · 💬 {{ it.comments }}</text>
            <text class="views">{{ it.reads }}</text>
          </view>
        </view>
        <text class="arrow">›</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTheme } from '@/utils/theme'
import { onShow } from '@dcloudio/uni-app'
import { getHotPosts } from '@/api/posts'
import type { PostBrief } from '@/types/api'

const { themeClass } = useTheme()

const statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0

interface HotRow {
  id: number
  rank: number
  title: string
  isHot: boolean
  likes: number
  comments: number
  reads: string
}

const items = ref<HotRow[]>([])
const loading = ref(true)

// 与首页热帖区同规则（标题截断/热标门槛），保证两处口径一致
const TITLE_MAX = 40 // 二级页行宽更大，截断上限比首页(30)宽
const HOT_TAG_MIN = 3

const load = async () => {
  loading.value = true
  try {
    const list: PostBrief[] = await getHotPosts(10)
    items.value = list.map((p, i) => {
      const firstLine =
        (p.content || '').split('\n').find((s) => s.trim()) || '（无文字）'
      return {
        id: p.id,
        rank: i + 1,
        title:
          firstLine.length > TITLE_MAX
            ? firstLine.slice(0, TITLE_MAX) + '…'
            : firstLine,
        isHot:
          (p.like_count || 0) >= HOT_TAG_MIN ||
          (p.comment_count || 0) >= HOT_TAG_MIN,
        likes: p.like_count || 0,
        comments: p.comment_count || 0,
        reads: `${p.view_count || 0} 浏览`,
      }
    })
  } catch {
    /* 保持空态 */
  } finally {
    loading.value = false
  }
}

onShow(() => load())

const rankClass = (rank: number) => `rank-${rank}`
const goPost = (id: number) =>
  uni.navigateTo({ url: `/pages/post-detail/index?id=${id}` })
const goBack = () =>
  uni.navigateBack({ fail: () => uni.reLaunch({ url: '/pages/index/index' }) })
</script>

<style scoped>
.page-hot {
  min-height: 100vh;
  background: var(--bg-page);
}

/* 头部：粉色沉浸式，与首页/互动页统一 */
.header { background-color: var(--bg-page); border-bottom: 1rpx solid var(--border-light); }
.header-row { height: 88rpx; display: flex; align-items: center; padding: 0 24rpx; }
.back-btn { font-size: 56rpx; color: var(--text-1); line-height: 1; padding: 0 12rpx; }
.header-title { flex: 1; text-align: center; font-size: 32rpx; font-weight: 700; color: var(--text-1); }
.header-right { width: 100rpx; }

.intro-bar { padding: 20rpx 32rpx 4rpx; }
.intro-text { font-size: 22rpx; color: var(--text-3); }

.rank-card {
  background: var(--bg-card);
  border-radius: var(--radius-card);
  margin: 20rpx 24rpx 40rpx;
  padding: 8rpx 28rpx;
}

.rank-row {
  display: flex;
  align-items: center;
  padding: 26rpx 0;
  border-bottom: 1rpx solid var(--border-light);
}
.rank-row:last-child { border-bottom: none; }

/* 名次：与首页榜单同配色；前三名放大强调 */
.rank {
  width: 64rpx;
  flex-shrink: 0;
  font-size: 32rpx;
  font-weight: bold;
  font-style: italic;
  color: var(--text-3);
  text-align: center;
}
.rank-row.top3 .rank { font-size: 44rpx; }
.rank-1 { color: var(--primary-strong); }
.rank-2 { color: var(--rank-2); }
.rank-3 { color: var(--rank-3); }

.mid { flex: 1; min-width: 0; margin-left: 20rpx; }

.line1 { display: flex; align-items: center; }
.title {
  flex: 1;
  min-width: 0;
  font-size: 28rpx;
  color: var(--text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hot-tag {
  flex-shrink: 0;
  background: var(--primary-strong);
  color: var(--text-inverse);
  font-size: 18rpx;
  padding: 2rpx 8rpx;
  border-radius: var(--radius-tag);
  margin-left: 10rpx;
}

.line2 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8rpx;
}
.meta { font-size: 22rpx; color: var(--text-3); }
.views { font-size: 22rpx; color: var(--text-3); }

.arrow { font-size: 40rpx; color: var(--text-4); margin-left: 12rpx; }

.state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 200rpx 0;
  color: var(--text-3);
  font-size: 26rpx;
}
.state-emoji { font-size: 96rpx; margin-bottom: 24rpx; opacity: 0.5; }
</style>
