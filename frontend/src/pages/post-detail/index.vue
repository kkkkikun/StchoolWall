<template>
  <view class="page-detail">
    <view v-if="loading" class="state"><text>加载中…</text></view>

    <view v-else-if="post" class="body">
      <!-- 作者 -->
      <view class="author">
        <image v-if="post.author.avatar_url" class="avatar" :src="post.author.avatar_url" mode="aspectFill" />
        <view v-else class="avatar" :style="{ background: avatarColor }">
          <text class="avatar-letter">{{ avatarLetter }}</text>
        </view>
        <view class="author-meta" @tap="goAuthor">
          <view class="name-row">
            <text class="nickname">{{ post.author.nickname }}</text>
            <text v-if="post.is_featured" class="featured-chip">精华</text>
          </view>
          <text class="sub">{{ timeText }} · {{ typeLabel }} ›</text>
        </view>
        <view v-if="canFollow" class="follow-btn" :class="{ on: isFollowing }" @tap="onFollow">
          <text>{{ isFollowing ? '已关注' : '+ 关注' }}</text>
        </view>
        <text v-if="canReport" class="report-btn" @tap="onReport">举报</text>
      </view>

      <!-- 正文 -->
      <view class="content">
        <text class="content-text">
          <text
            v-for="(seg, i) in contentSegments"
            :key="i"
            :class="{ 'hashtag': seg.type === 'tag' }"
            @tap.stop="seg.type === 'tag' && onTag(seg.tag)"
          >{{ seg.text }}</text>
        </text>
        <view v-if="post.images && post.images.length" class="images">
          <!-- 单图：widthFix 自适应铺开（高度随宽高比）；多图：1:1 方格排开 -->
          <image
            v-for="(img, i) in post.images"
            :key="i"
            :class="post.images.length === 1 ? 'post-image-single' : 'post-image'"
            :src="img"
            :mode="post.images.length === 1 ? 'widthFix' : 'aspectFill'"
            @tap="previewImage(i)"
          />
        </view>
        <text v-if="post.price" class="price">¥{{ post.price }}</text>
        <view v-if="post.contact_info" class="contact">
          <text class="contact-label">联系方式：</text>
          <text class="contact-value" @tap="copyContact">{{ post.contact_info }}</text>
        </view>
        <view class="meta">
          <text>{{ post.view_count || 0 }} 浏览</text>
          <text class="dot">·</text>
          <text>{{ likeCount }} 赞</text>
          <text class="dot">·</text>
          <text>{{ post.comment_count || 0 }} 评论</text>
        </view>
      </view>

      <!-- 互动条 -->
      <view class="action-bar">
        <view class="act" :class="{ on: isLiked }" @tap="onLike">
          <text class="act-icon">{{ isLiked ? '♥' : '♡' }}</text><text>赞 {{ likeCount }}</text>
        </view>
        <view class="act" :class="{ on: isFav }" @tap="onFavorite">
          <text class="act-icon">{{ isFav ? '★' : '☆' }}</text><text>{{ isFav ? '已藏' : '收藏' }}</text>
        </view>
        <view class="act" @tap="focusComment">
          <text class="act-icon">💬</text><text>评论</text>
        </view>
        <view class="act" @tap="onShare">
          <text class="act-icon">↗</text><text>转发</text>
        </view>
      </view>

      <!-- 评论区 -->
      <view class="comments">
        <view class="comments-title">评论 {{ post.comment_count || 0 }}</view>
        <view v-if="comments.length === 0" class="empty-comment"><text>暂无评论，来抢沙发～</text></view>
        <view v-for="c in comments" :key="c.id" class="comment">
          <image v-if="c.user.avatar_url" class="c-avatar" :src="c.user.avatar_url" mode="aspectFill" />
          <view v-else class="c-avatar" :style="{ background: colorOf(c.user.nickname) }">
            <text class="c-letter">{{ (c.user.nickname || '?').slice(0, 1) }}</text>
          </view>
          <view class="c-main">
            <view class="c-top">
              <text class="c-name">{{ c.user.nickname }}</text>
              <text v-if="c.user_id === currentUserId" class="c-del" @tap="onDeleteComment(c.id)">删除</text>
            </view>
            <text class="c-text">{{ c.content }}</text>
          </view>
        </view>
      </view>
    </view>

    <view v-else class="state"><text>帖子不存在或已删除</text></view>

    <!-- 底部评论输入 -->
    <view v-if="post" class="comment-input-bar">
      <input
        ref="commentInput"
        v-model="commentText"
        class="comment-input"
        placeholder="说点什么…"
        :maxlength="500"
        confirm-type="send"
        @confirm="onSendComment"
      />
      <view class="send-btn" :class="{ disabled: !commentText.trim() || sending }" @tap="onSendComment">
        <text>发送</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { PostDetail } from '@/types/api'
import { parseHashtags } from '@/utils/text'
import { POST_TYPE_MAP } from '@/types/api'
import { getPostDetail, reportPost } from '@/api/posts'
import {
  listComments,
  createComment,
  deleteComment,
  likePost,
  unlikePost,
  favoritePost,
  unfavoritePost,
  followUser,
  unfollowUser,
  type CommentItem,
} from '@/api/interaction'
import { tokenStorage, userStorage } from '@/utils/storage'

const post = ref<PostDetail | null>(null)
const contentSegments = computed(() => parseHashtags(post.value?.content || ''))
const onTag = (tag: string) => uni.navigateTo({ url: `/pages/tag-posts/index?name=${encodeURIComponent(tag)}` })
const loading = ref(true)
const comments = ref<CommentItem[]>([])
const commentText = ref('')
const sending = ref(false)
const commentInput = ref<any>(null)
const currentUserId = ref<string>(userStorage.getUserInfo()?.id || '')

const isLiked = ref(false)
const likeCount = ref(0)
const isFav = ref(false)
const isFollowing = ref(false)

const typeLabel = computed(() => (POST_TYPE_MAP as Record<string, string>)[post.value?.post_type || ''] || '动态')
const canReport = computed(() => tokenStorage.isLoggedIn())
const canFollow = computed(() => {
  if (!tokenStorage.isLoggedIn() || !post.value?.user_id) return false
  return post.value.user_id !== currentUserId.value
})

const timeText = computed(() => {
  const t = new Date(post.value?.created_at || '').getTime()
  if (!t) return ''
  const diff = Date.now() - t
  const m = Math.floor(diff / 60000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m}分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}小时前`
  const d = Math.floor(h / 24)
  if (d < 7) return `${d}天前`
  const dt = new Date(post.value?.created_at || '')
  return `${dt.getMonth() + 1}-${dt.getDate()}`
})

const AVATAR_COLORS = ['#ffd591', '#adc6ff', '#b7eb8f', '#ffa39e', '#d3adf7', '#87e8de', '#ffccc7']
const colorOf = (s: string) => {
  let h = 0
  for (let i = 0; i < (s || '').length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[h % AVATAR_COLORS.length]
}
const avatarLetter = computed(() => (post.value?.author.nickname || '?').slice(0, 1))
const avatarColor = computed(() => colorOf(post.value?.author.nickname || ''))

const applyInteractions = () => {
  if (!post.value) return
  isLiked.value = !!post.value.is_liked
  likeCount.value = post.value.like_count || 0
  isFav.value = !!post.value.is_favorited
  isFollowing.value = !!post.value.is_following
}

const onFollow = async () => {
  if (!post.value?.user_id || !requireLogin()) return
  const prev = isFollowing.value
  isFollowing.value = !prev
  try {
    await (prev ? unfollowUser(post.value.user_id) : followUser(post.value.user_id))
    uni.showToast({ title: prev ? '已取消关注' : '关注成功', icon: 'none' })
  } catch (e) {
    isFollowing.value = prev
    uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' })
  }
}

const loadComments = async () => {
  if (!post.value) return
  try {
    const res = await listComments(post.value.id)
    comments.value = res.items
  } catch {
    /* 忽略 */
  }
}

const initData = async (id: number) => {
  try {
    const data = await getPostDetail(id)
    post.value = data
    applyInteractions()
    await loadComments()
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

const requireLogin = (): boolean => {
  if (!tokenStorage.isLoggedIn()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return false
  }
  return true
}

const onLike = async () => {
  if (!post.value || !requireLogin()) return
  const prev = isLiked.value
  isLiked.value = !prev
  likeCount.value += prev ? -1 : 1
  try {
    await (prev ? unlikePost(post.value.id) : likePost(post.value.id))
    if (post.value) post.value.like_count = likeCount.value
  } catch (e) {
    isLiked.value = prev
    likeCount.value += prev ? 1 : -1
    uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' })
  }
}

const onFavorite = async () => {
  if (!post.value || !requireLogin()) return
  const prev = isFav.value
  isFav.value = !prev
  try {
    await (prev ? unfavoritePost(post.value.id) : favoritePost(post.value.id))
    uni.showToast({ title: prev ? '已取消收藏' : '已收藏', icon: 'none' })
  } catch (e) {
    isFav.value = prev
    uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' })
  }
}

const onShare = () => uni.showToast({ title: '转发（开发中）', icon: 'none' })
const focusComment = () => uni.pageScrollTo({ scrollTop: 99999, duration: 200 })

const onSendComment = async () => {
  if (!post.value) return
  if (!requireLogin()) return
  const text = commentText.value.trim()
  if (!text || sending.value) return
  sending.value = true
  try {
    const created = await createComment(post.value.id, text)
    commentText.value = ''
    if (created.status === 0) {
      // 灰词转人工：审核通过后才公开
      uni.showToast({ title: '已提交，审核通过后可见', icon: 'none' })
    } else {
      if (post.value) post.value.comment_count = (post.value.comment_count || 0) + 1
      await loadComments()
      uni.showToast({ title: '评论成功', icon: 'success' })
    }
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '评论失败', icon: 'none' })
  } finally {
    sending.value = false
  }
}

const onDeleteComment = (id: number) => {
  uni.showModal({
    title: '删除评论',
    content: '确定删除这条评论吗？',
    success: async (res) => {
      if (!res.confirm || !post.value) return
      try {
        await deleteComment(id)
        if (post.value) post.value.comment_count = Math.max(0, (post.value.comment_count || 0) - 1)
        await loadComments()
      } catch (e) {
        uni.showToast({ title: (e as Error).message || '删除失败', icon: 'none' })
      }
    },
  })
}

const goAuthor = () => {
  if (post.value?.user_id) uni.navigateTo({ url: `/pages/profile/index?id=${post.value.user_id}` })
}

const onReport = () => {
  if (!post.value) return
  uni.showActionSheet({
    itemList: ['虚假信息', '违规内容', '垃圾广告', '人身攻击'],
    success: async (r) => {
      const reason = ['虚假信息', '违规内容', '垃圾广告', '人身攻击'][r.tapIndex]
      try {
        await reportPost(post.value!.id, reason)
        uni.showToast({ title: '举报成功', icon: 'success' })
      } catch (e) {
        uni.showToast({ title: (e as Error).message || '举报失败', icon: 'none' })
      }
    },
  })
}

const previewImage = (idx: number) => {
  if (!post.value?.images?.length) return
  uni.previewImage({ urls: post.value.images, current: idx })
}

const copyContact = () => {
  if (!post.value?.contact_info) return
  uni.setClipboardData({ data: post.value.contact_info })
}

// 进入页面
;(() => {
  const pages = getCurrentPages()
  const cur = pages[pages.length - 1] as any
  const id = Number(cur?.options?.id)
  if (!id) {
    uni.showToast({ title: '帖子不存在', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 800)
    loading.value = false
    return
  }
  currentUserId.value = userStorage.getUserInfo()?.id || ''
  initData(id)
})()
</script>

<style scoped>
.page-detail { min-height: 100vh; background: var(--bg-page); padding-bottom: 140rpx; }
.state { text-align: center; padding: 120rpx 0; color: var(--text-3); font-size: 26rpx; }

.body { background: #fff; margin: 0; }
.author { display: flex; align-items: center; padding: 28rpx 24rpx; border-bottom: 1rpx solid #f5f5f5; }
.avatar { width: 84rpx; height: 84rpx; border-radius: 50%; margin-right: 20rpx; display: flex; align-items: center; justify-content: center; }
.avatar-letter { font-size: 40rpx; font-weight: bold; color: #fff; }
.author-meta { flex: 1; display: flex; flex-direction: column; }
.nickname { font-size: 30rpx; font-weight: bold; color: var(--text-1); }
.name-row { display: flex; align-items: center; }
.featured-chip { margin-left: 12rpx; font-size: 18rpx; color: var(--brand-red-dark); background: var(--brand-red-soft); border: 1rpx solid var(--brand-red); padding: 1rpx 10rpx; border-radius: 6rpx; }
.sub { font-size: 22rpx; color: var(--text-3); margin-top: 6rpx; }
.report-btn { font-size: 24rpx; color: var(--text-3); border: 1rpx solid #eee; padding: 8rpx 20rpx; border-radius: 24rpx; }
.follow-btn { font-size: 24rpx; color: #fff; background: var(--brand-red); padding: 8rpx 24rpx; border-radius: 24rpx; margin-right: 16rpx; }
.follow-btn.on { background: #f0f0f0; color: #888; }

.content { padding: 24rpx; }
.content-text { font-size: 30rpx; color: var(--text-1); line-height: 1.7; white-space: pre-wrap; }
.content-text .hashtag { color: #1d9bf0; }
.images { display: flex; flex-wrap: wrap; gap: 12rpx; margin: 20rpx 0; }
.post-image { width: 220rpx; height: 220rpx; border-radius: 12rpx; background: #f2f3f5; }
.post-image-single { width: 100%; border-radius: 12rpx; background: #f2f3f5; }
.price { font-size: 40rpx; font-weight: bold; color: var(--brand-red); display: block; margin-top: 16rpx; }
.contact { background: var(--bg-page); padding: 16rpx 20rpx; border-radius: 12rpx; margin-top: 20rpx; }
.contact-label { font-size: 24rpx; color: var(--text-3); }
.contact-value { font-size: 28rpx; color: var(--brand-red); margin-left: 8rpx; font-weight: 500; }
.meta { display: flex; align-items: center; margin-top: 24rpx; font-size: 22rpx; color: var(--text-3); }
.dot { margin: 0 12rpx; }

.action-bar { display: flex; border-top: 1rpx solid #f5f5f5; border-bottom: 16rpx solid var(--bg-page); padding: 20rpx 24rpx; justify-content: space-around; }
.act { display: flex; align-items: center; color: var(--text-2); font-size: 26rpx; }
.act.on { color: var(--brand-red); }
.act-icon { font-size: 34rpx; margin-right: 8rpx; }

.comments { padding: 24rpx; }
.comments-title { font-size: 30rpx; font-weight: bold; color: var(--text-1); margin-bottom: 20rpx; }
.empty-comment { text-align: center; color: var(--text-3); font-size: 24rpx; padding: 40rpx 0; }
.comment { display: flex; padding: 20rpx 0; border-bottom: 1rpx solid #f7f7f7; }
/* 评论者头像/昵称与楼主同规格（X 式层级：作者一致，正文小一号） */
.c-avatar { width: 84rpx; height: 84rpx; border-radius: 50%; margin-right: 20rpx; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.c-letter { font-size: 40rpx; font-weight: bold; color: #fff; }
.c-main { flex: 1; }
.c-top { display: flex; align-items: center; justify-content: space-between; }
.c-name { font-size: 30rpx; color: var(--text-1); font-weight: bold; }
.c-del { font-size: 22rpx; color: var(--text-3); }
.c-text { font-size: 25rpx; color: var(--text-2); margin-top: 8rpx; display: block; line-height: 1.5; }

.comment-input-bar { position: fixed; left: 0; right: 0; bottom: 0; display: flex; align-items: center; background: #fff; border-top: 1rpx solid #eee; padding: 16rpx 24rpx; padding-bottom: calc(16rpx + env(safe-area-inset-bottom)); z-index: 100; }
.comment-input { flex: 1; height: 72rpx; background: var(--bg-page); border-radius: 36rpx; padding: 0 28rpx; font-size: 28rpx; }
.send-btn { margin-left: 16rpx; background: var(--brand-red); color: #fff; font-size: 28rpx; padding: 0 32rpx; height: 72rpx; line-height: 72rpx; border-radius: 36rpx; }
.send-btn.disabled { opacity: 0.4; }
</style>
