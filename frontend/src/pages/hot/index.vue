<template>
  <view class="page-hot" :class="themeClass">
    <CustomNavBar show-back title="十大热帖" />

    <!-- 2. 规则说明条 -->
    <view class="intro-bar">
      <image class="intro-icon" src="/static/icons/common/hot-primary.svg" mode="aspectFit" />
      <text class="intro-text">近 7 天 · 赞×3 + 评论×2 + 浏览 加权排序</text>
    </view>

    <!-- 3. 完整榜单 -->
    <view v-if="loading" class="state"><text>加载中…</text></view>
    <view v-else-if="!items.length" class="state">
      <image class="state-emoji" src="/static/icons/state/ice.svg" mode="aspectFit" />
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
            <view class="meta">
              <image class="meta-icon" src="/static/icons/common/heart.svg" mode="aspectFit" />
              <text>{{ it.likes }}</text>
              <text class="meta-sep">·</text>
              <image class="meta-icon" src="/static/icons/common/comment.svg" mode="aspectFit" />
              <text>{{ it.comments }}</text>
            </view>
            <text class="views">{{ it.reads }}</text>
          </view>
        </view>
        <image class="arrow" src="/static/icons/common/arrow-right.svg" mode="aspectFit" />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTheme } from '@/utils/theme'
import { onShow } from '@dcloudio/uni-app'
import CustomNavBar from '@/components/custom-nav-bar.vue'
import { getHotPosts } from '@/api/posts'
import type { PostBrief } from '@/types/api'

const { themeClass } = useTheme()

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

const fmtCount = (n?: number): string => {
  const v = n || 0
  if (v < 10000) return String(v)
  const w = v / 10000
  return `${w >= 100 ? Math.round(w) : w.toFixed(1).replace(/\.0$/, '')}万`
}

const load = async () => {
  loading.value = true
  try {
    const list: PostBrief[] = await getHotPosts(10)
    items.value = list.map((p, i) => {
      const firstLine =
        (p.content || '').split('\n').find((s: string) => s.trim()) || '（无文字）'
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
        reads: `${fmtCount(p.view_count)} 浏览`,
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

.intro-bar { padding: 20rpx 32rpx 4rpx; }
.intro-icon { width: 24rpx; height: 24rpx; margin-right: 6rpx; flex-shrink: 0; }
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
.meta { display: inline-flex; align-items: center; font-size: 22rpx; color: var(--text-3); }
.meta-icon { width: 22rpx; height: 22rpx; margin-right: 4rpx; flex-shrink: 0; }
.meta-sep { margin: 0 8rpx; }
.views { font-size: 22rpx; color: var(--text-3); }

.arrow { width: 32rpx; height: 32rpx; margin-left: 12rpx; flex-shrink: 0; }

.state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 200rpx 0;
  color: var(--text-3);
  font-size: 26rpx;
}
.state-emoji { width: 96rpx; height: 96rpx; margin-bottom: 24rpx; opacity: 0.5; }
</style>
