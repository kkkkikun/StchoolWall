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
      <text class="more-action" @tap.stop="onMoreAction">···</text>
    </view>

    <!-- 正文 -->
    <view class="feed-body" @tap="onDetail">
      <text class="feed-text">
        <text
          v-for="(seg, i) in contentSegments"
          :key="i"
          :class="{ 'hashtag': seg.type === 'tag' }"
          @tap.stop="seg.type === 'tag' && onTag(seg.tag)"
        >{{ seg.text }}</text>
      </text>
      <view v-if="post.images && post.images.length > 0" class="feed-images">
        <!-- 单图：widthFix 自适应铺开；多图：1:1 缩略排开（最多展示 3 张） -->
        <image
          v-for="(img, i) in post.images.slice(0, 3)"
          :key="i"
          :class="post.images.length === 1 ? 'img-single' : 'img-ph'"
          :src="img"
          :mode="post.images.length === 1 ? 'widthFix' : 'aspectFill'"
          @tap.stop="previewImage(i)"
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
import { parseHashtags } from '@/utils/text'
import { POST_TYPE_MAP } from '@/types/api'
import { likePost, unlikePost, favoritePost, unfavoritePost } from '@/api/interaction'
import { tokenStorage } from '@/utils/storage'

interface Props {
  post: PostBrief
}
const props = defineProps<Props>()

/**
 * 操作栏图标：统一走 SVG 资源（emoji 在各系统字形不一，且无法跟随主题变色）。
 * 图标几何由 scripts/gen_icons.py 统一生成，勿手改 .svg 文件。
 */
const FEED_ICONS = {
  comment: '/static/icons/common/comment.svg',
  heart: '/static/icons/common/heart.svg',
  heartOn: '/static/icons/common/heart-on.svg',
  view: '/static/icons/common/eye.svg',
  bookmark: '/static/icons/common/bookmark.svg',
  bookmarkOn: '/static/icons/common/bookmark-on.svg',
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

const contentSegments = computed(() => parseHashtags(props.post.content))
const onTag = (tag: string) => uni.navigateTo({ url: `/pages/tag-posts/index?name=${encodeURIComponent(tag)}` })

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

const previewImage = (index: number) => {
  if (!props.post.images || props.post.images.length === 0) return
  uni.previewImage({
    urls: props.post.images,
    current: index,
  })
}

const onMoreAction = () => {
  uni.showActionSheet({
    itemList: ['复制正文', '查看详情/举报'],
    success: (res) => {
      if (res.tapIndex === 0) {
        uni.setClipboardData({
          data: props.post.content,
          success: () => uni.showToast({ title: '已复制文本', icon: 'success' }),
        })
      } else if (res.tapIndex === 1) {
        onDetail()
      }
    },
  })
}

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
  /* 主题B（X）：平铺时间线行——无卡片底、发丝分隔线 */
  background-color: var(--bg-page);
  padding: 24rpx 28rpx;
  border-bottom: 1rpx solid var(--border-light);
}
.feed-header { display: flex; align-items: center; justify-content: space-between; }
.user-info { display: flex; align-items: center; flex: 1; }
.avatar {
  width: 84rpx; height: 84rpx; border-radius: 50%; margin-right: 20rpx;
  display: flex; align-items: center; justify-content: center;
}
.avatar-letter { font-size: 40rpx; font-weight: bold; color: var(--text-inverse); }
.user-meta { display: flex; flex-direction: column; }
.name-box { display: flex; align-items: center; }
.username { font-size: 30rpx; color: var(--text-1); font-weight: 700; }
.pinned-badge {
  margin-left: 10rpx;
  font-size: 18rpx;
  color: var(--text-inverse);
  background: var(--primary);
  padding: 2rpx 10rpx;
  border-radius: var(--radius-tag);
}

.featured-badge {
  margin-left: 10rpx;
  font-size: 18rpx;
  color: var(--primary-strong);
  background: var(--primary-soft);
  border: 1rpx solid var(--primary);
  padding: 1rpx 10rpx;
  border-radius: var(--radius-tag);
}
.time-ago { font-size: 24rpx; color: var(--text-2); margin-top: 4rpx; }
.more-action { color: var(--text-3); font-size: 36rpx; padding: 0 10rpx; letter-spacing: 2rpx; }
.feed-body { margin-top: 20rpx; }
.feed-text { font-size: 30rpx; color: var(--text-1); line-height: 1.55; white-space: pre-wrap; }
.feed-text .hashtag { color: var(--link); }
.feed-images { display: flex; gap: 12rpx; margin-top: 16rpx; }
.img-ph { width: 200rpx; height: 200rpx; border-radius: var(--radius-inner); background: var(--bg-card-2); }
.img-single { width: 100%; border-radius: var(--radius-inner); background: var(--bg-card-2); }
.feed-actions {
  display: flex; margin-top: 28rpx; border-top: 1rpx solid var(--border-light);
  padding-top: 24rpx; justify-content: space-between;
}
.action-item { display: flex; align-items: center; gap: 10rpx; color: var(--text-2); }
.action-item.on .act-num { color: var(--like); }
.act-icon { width: 36rpx; height: 36rpx; }
.act-num { font-size: 24rpx; color: var(--text-2); }
</style>
