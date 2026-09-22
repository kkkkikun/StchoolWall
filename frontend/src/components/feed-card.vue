<template>
  <view class="feed-card">
    <!-- 头部 -->
    <view class="feed-header">
      <view class="user-info" @tap="onDetail">
        <image v-if="post.author.avatar_url" class="avatar" :src="post.author.avatar_url" mode="aspectFill" />
        <view v-else class="avatar" :style="{ background: avatarColor }">
          <text class="avatar-letter">{{ avatarLetter }}</text>
        </view>
        <view class="user-meta">
          <view class="name-box">
            <text class="username">{{ post.author.nickname }}</text>
            <text v-if="post.is_pinned" class="pinned-badge">置顶</text>
            <text v-if="post.is_featured" class="featured-badge">精华</text>
          </view>
          <text class="time-ago">{{ timeAgo }} · {{ typeLabel }}</text>
        </view>
      </view>
      <text class="more-action">···</text>
    </view>

    <!-- 正文 -->
    <view class="feed-body" @tap="onDetail">
      <text class="feed-text">{{ post.content }}</text>
      <view v-if="post.images && post.images.length > 0" class="feed-images">
        <!-- 单图：widthFix 自适应铺开；多图：1:1 缩略排开（最多展示 3 张） -->
        <image
          v-for="(img, i) in post.images.slice(0, 3)"
          :key="i"
          :class="post.images.length === 1 ? 'img-single' : 'img-ph'"
          :src="img"
          :mode="post.images.length === 1 ? 'widthFix' : 'aspectFill'"
        />
      </view>
    </view>

    <!-- 底部操作栏（参考稿样式：评论/点赞/浏览/收藏 均匀分布，SVG 图标） -->
    <view class="feed-actions">
      <view class="action-item" @tap="onDetail">
        <image class="act-icon" :src="FEED_ICONS.comment" mode="aspectFit" />
        <text class="act-num">{{ fmtCount(post.comment_count) }}</text>
      </view>
      <view class="action-item" :class="{ on: isLiked }" @tap="onLike">
        <image class="act-icon" :src="isLiked ? FEED_ICONS.heartOn : FEED_ICONS.heart" mode="aspectFit" />
        <text class="act-num">{{ fmtCount(likeCount) }}</text>
      </view>
      <view class="action-item" @tap="onDetail">
        <image class="act-icon" :src="FEED_ICONS.view" mode="aspectFit" />
        <text class="act-num">{{ fmtCount(post.view_count) }}</text>
      </view>
      <view class="action-item" :class="{ on: isFav }" @tap="onFavorite">
        <image class="act-icon" :src="isFav ? FEED_ICONS.bookmarkOn : FEED_ICONS.bookmark" mode="aspectFit" />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { PostBrief } from '@/types/api'
import { POST_TYPE_MAP } from '@/types/api'
import { likePost, unlikePost, favoritePost, unfavoritePost } from '@/api/interaction'
import { tokenStorage } from '@/utils/storage'

interface Props {
  post: PostBrief
}
const props = defineProps<Props>()

/**
 * 操作栏图标更换位：不满意自带线条稿时，把新文件放进 src/static/icons/feed/，
 * 改下面的路径即可（正方形最佳；SVG 仅 H5，微信真机请用 PNG）。
 */
const FEED_ICONS = {
  comment: '/static/icons/feed/comment.svg',
  heart: '/static/icons/feed/heart.svg',
  heartOn: '/static/icons/feed/heart-on.svg',
  view: '/static/icons/feed/view.svg',
  bookmark: '/static/icons/feed/bookmark.svg',
  bookmarkOn: '/static/icons/feed/bookmark-on.svg',
}

/** 计数格式化：≥1万 显示 x.x万（参考稿样式） */
const fmtCount = (n?: number): string => {
  const v = n || 0
  if (v < 10000) return String(v)
  const w = v / 10000
  return `${w >= 100 ? Math.round(w) : w.toFixed(1).replace(/\.0$/, '')}万`
}
const emit = defineEmits<{ (e: 'detail', id: number): void }>()

const isLiked = ref(!!props.post.is_liked)
const likeCount = ref(props.post.like_count || 0)
const isFav = ref(!!props.post.is_favorited)

const typeLabel = computed(() => (POST_TYPE_MAP as Record<string, string>)[props.post.post_type] || '动态')

const AVATAR_COLORS = ['#ffd591', '#adc6ff', '#b7eb8f', '#ffa39e', '#d3adf7', '#87e8de', '#ffccc7']
const avatarLetter = computed(() => (props.post.author.nickname || '?').slice(0, 1))
const avatarColor = computed(() => {
  const s = props.post.author.nickname || ''
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[h % AVATAR_COLORS.length]
})

const timeAgo = computed(() => {
  const t = new Date(props.post.created_at).getTime()
  if (!t) return ''
  const diff = Date.now() - t
  const m = Math.floor(diff / 60000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m}分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}小时前`
  const d = Math.floor(h / 24)
  if (d < 7) return `${d}天前`
  const dt = new Date(props.post.created_at)
  return `${dt.getMonth() + 1}-${dt.getDate()}`
})

const requireLogin = (): boolean => {
  if (!tokenStorage.isLoggedIn()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return false
  }
  return true
}

const onDetail = () => emit('detail', props.post.id)

const onLike = async () => {
  if (!requireLogin()) return
  // 乐观更新
  const prevLiked = isLiked.value
  isLiked.value = !prevLiked
  likeCount.value += prevLiked ? -1 : 1
  try {
    if (prevLiked) {
      await unlikePost(props.post.id)
    } else {
      await likePost(props.post.id)
    }
  } catch (e) {
    // 回滚
    isLiked.value = prevLiked
    likeCount.value += prevLiked ? 1 : -1
    uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' })
  }
}

const onFavorite = async () => {
  if (!requireLogin()) return
  const prev = isFav.value
  isFav.value = !prev
  try {
    if (prev) {
      await unfavoritePost(props.post.id)
    } else {
      await favoritePost(props.post.id)
      uni.showToast({ title: '已收藏', icon: 'success' })
    }
  } catch (e) {
    isFav.value = prev
    uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' })
  }
}

</script>

<style scoped>
.feed-card {
  background-color: #ffffff;
  border-radius: var(--radius-card);
  padding: 28rpx;
  margin-bottom: 20rpx;
}
.feed-header { display: flex; align-items: center; justify-content: space-between; }
.user-info { display: flex; align-items: center; flex: 1; }
.avatar {
  width: 84rpx; height: 84rpx; border-radius: 50%; margin-right: 20rpx;
  display: flex; align-items: center; justify-content: center;
}
.avatar-letter { font-size: 40rpx; font-weight: bold; color: #fff; }
.user-meta { display: flex; flex-direction: column; }
.name-box { display: flex; align-items: center; }
.username { font-size: 28rpx; color: var(--text-1); font-weight: bold; }
.pinned-badge {
  margin-left: 10rpx;
  font-size: 18rpx;
  color: #fff;
  background: var(--brand-red);
  padding: 2rpx 10rpx;
  border-radius: 6rpx;
}

.featured-badge {
  margin-left: 10rpx;
  font-size: 18rpx;
  color: var(--brand-red-dark);
  background: var(--brand-red-soft);
  border: 1rpx solid var(--brand-red);
  padding: 1rpx 10rpx;
  border-radius: 6rpx;
}
.time-ago { font-size: 22rpx; color: var(--text-3); margin-top: 6rpx; }
.more-action { color: var(--text-3); font-size: 36rpx; padding: 0 10rpx; letter-spacing: 2rpx; }
.feed-body { margin-top: 20rpx; }
.feed-text { font-size: 29rpx; color: var(--text-1); line-height: 1.6; white-space: pre-wrap; }
.feed-images { display: flex; gap: 12rpx; margin-top: 16rpx; }
.img-ph { width: 200rpx; height: 200rpx; border-radius: 16rpx; background: #f2f3f5; }
.img-single { width: 100%; border-radius: 16rpx; background: #f2f3f5; }
.feed-actions {
  display: flex; margin-top: 28rpx; border-top: 1rpx solid #f5f5f5;
  padding-top: 24rpx; justify-content: space-between;
}
.action-item { display: flex; align-items: center; gap: 10rpx; color: var(--text-2); }
.action-item.on .act-num { color: var(--brand-red-dark); }
.act-icon { width: 36rpx; height: 36rpx; }
.act-num { font-size: 24rpx; color: var(--text-2); }
</style>
