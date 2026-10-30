<template>
  <view class="page-detail" :class="themeClass">
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
        <text v-if="isAuthor" class="del-btn" @tap="onDeletePost">删除</text>
        <text v-else-if="canReport" class="report-btn" @tap="onAuthorActions">···</text>
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
          <text class="meta-item"><text class="meta-num">{{ post.view_count || 0 }}</text> 浏览</text>
          <text class="dot">·</text>
          <text class="meta-item"><text class="meta-num">{{ likeCount }}</text> 赞</text>
          <text class="dot">·</text>
          <text class="meta-item"><text class="meta-num">{{ post.comment_count || 0 }}</text> 评论</text>
        </view>
      </view>

      <!-- 互动条 -->
      <view class="action-bar">
        <view class="act" :class="{ on: isLiked, 'on-like': isLiked }" @tap="onLike">
          <image class="act-icon"
                 :src="isLiked ? '/static/icons/common/heart-on.svg' : '/static/icons/common/heart.svg'"
                 mode="aspectFit" /><text>赞 {{ likeCount }}</text>
        </view>
        <view class="act" :class="{ on: isFav, 'on-fav': isFav }" @tap="onFavorite">
          <image class="act-icon"
                 :src="isFav ? '/static/icons/common/star-on.svg' : '/static/icons/common/star.svg'"
                 mode="aspectFit" /><text>{{ isFav ? '已藏' : '收藏' }}</text>
        </view>
        <view class="act" @tap="focusComment">
          <image class="act-icon" src="/static/icons/common/comment.svg" mode="aspectFit" /><text>评论</text>
        </view>
        <view class="act" @tap="onShare">
          <image class="act-icon" src="/static/icons/common/share.svg" mode="aspectFit" /><text>转发</text>
        </view>
      </view>

      <!-- 评论区 -->
      <view class="comments">
        <view class="comments-title">评论 {{ post.comment_count || 0 }}</view>
        <view v-if="comments.length === 0" class="empty-comment"><text>暂无评论，来抢沙发～</text></view>
        <view
          v-for="c in comments"
          :key="c.id"
          class="comment"
          @tap="onCommentTap(c)"
        >
          <image v-if="c.user.avatar_url" class="c-avatar" :src="c.user.avatar_url" mode="aspectFill" />
          <view v-else class="c-avatar" :style="{ background: colorOf(c.user.nickname) }">
            <text class="c-letter">{{ (c.user.nickname || '?').slice(0, 1) }}</text>
          </view>
          <view class="c-main">
            <view class="c-top">
              <text class="c-name">{{ c.user.nickname }}</text>
              <view class="c-right-acts">
                <text v-if="c.user_id === currentUserId" class="c-del" @tap.stop="onDeleteComment(c.id)">删除</text>
                <text v-else class="c-reply-btn" @tap.stop="onCommentTap(c)">回复</text>
              </view>
            </view>
            <text class="c-text">{{ c.content }}</text>
          </view>
        </view>

        <!-- 评论分页加载 / 到底提示 -->
        <view v-if="hasMoreComments" class="comment-load-more" @tap="loadMoreComments">
          <text>{{ loadingComments ? '加载中...' : '点击加载更多评论 ›' }}</text>
        </view>
        <view v-else-if="comments.length > 0" class="comment-no-more">
          <text>已显示全部评论</text>
        </view>
      </view>

      <!-- 底部安全留白占位，防 fixed 评论输入栏遮挡 -->
      <view class="bottom-spacer" />
    </view>

    <view v-else class="state"><text>帖子不存在或已删除</text></view>

    <!-- 底部评论输入 -->
    <view v-if="post" class="comment-input-bar">
      <view v-if="replyTarget" class="reply-target-tag">
        <text class="reply-tip">回复 @{{ replyTarget.user.nickname }}</text>
        <image class="reply-cancel" src="/static/icons/common/close.svg" mode="aspectFit" @tap="cancelReply" />
      </view>
      <input
        ref="commentInput"
        v-model="commentText"
        class="comment-input"
        :placeholder="replyTarget ? `回复 @${replyTarget.user.nickname}:` : '说点什么…'"
        placeholder-style="color: var(--text-2);"
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
import { onReachBottom } from '@dcloudio/uni-app'
import { useTheme } from '@/utils/theme'
import type { PostDetail } from '@/types/api'
import { parseHashtags } from '@/utils/text'
import { POST_TYPE_MAP } from '@/types/api'
import { getPostDetail, reportPost, deletePost } from '@/api/posts'
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
import { friendlyNetworkError } from '@/utils/errors'
import { blockUser } from '@/api/blocks'

const { themeClass } = useTheme()

const post = ref<PostDetail | null>(null)
const contentSegments = computed(() => parseHashtags(post.value?.content || ''))
const onTag = (tag: string) => uni.navigateTo({ url: `/pages/tag-posts/index?name=${encodeURIComponent(tag)}` })
const loading = ref(true)
const comments = ref<CommentItem[]>([])
const commentCursor = ref<number | null>(null)
const hasMoreComments = ref(false)
const loadingComments = ref(false)
const replyTarget = ref<CommentItem | null>(null)
const commentText = ref('')
const sending = ref(false)
const commentInput = ref<any>(null)
const currentUserId = ref<string>(userStorage.getUserInfo()?.id || '')

const isLiked = ref(false)
const likeCount = ref(0)
const isFav = ref(false)
const isFollowing = ref(false)

const typeLabel = computed(() => (POST_TYPE_MAP as Record<string, string>)[post.value?.post_type || ''] || '动态')
const isAuthor = computed(() => !!(post.value?.user_id && currentUserId.value && post.value.user_id === currentUserId.value))
const canReport = computed(() => tokenStorage.isLoggedIn() && !isAuthor.value)
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
    uni.showToast({ title: friendlyNetworkError(e, '操作失败'), icon: 'none' })
  }
}

const loadComments = async (append = false) => {
  if (!post.value) return
  loadingComments.value = true
  try {
    const cur = append ? (commentCursor.value || undefined) : undefined
    const res = await listComments(post.value.id, cur)
    comments.value = append ? [...comments.value, ...res.items] : res.items
    commentCursor.value = res.next_cursor
    hasMoreComments.value = res.has_more
  } catch {
    /* 忽略 */
  } finally {
    loadingComments.value = false
  }
}

const loadMoreComments = () => {
  if (!hasMoreComments.value || loadingComments.value) return
  loadComments(true)
}

onReachBottom(() => {
  if (hasMoreComments.value && !loadingComments.value) {
    loadMoreComments()
  }
})

const onCommentTap = (c: CommentItem) => {
  if (c.user_id === currentUserId.value) {
    onDeleteComment(c.id)
    return
  }
  replyTarget.value = c
  if (!commentText.value.startsWith(`@${c.user.nickname}`)) {
    commentText.value = `@${c.user.nickname} `
  }
}

const cancelReply = () => {
  replyTarget.value = null
  if (commentText.value.startsWith('@')) {
    commentText.value = ''
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
    uni.showToast({ title: friendlyNetworkError(e, '操作失败'), icon: 'none' })
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
    uni.showToast({ title: friendlyNetworkError(e, '操作失败'), icon: 'none' })
  }
}

const onShare = () => {
  // #ifdef MP-WEIXIN
  uni.showToast({ title: '点击右上角 ··· 即可分享到微信', icon: 'none' })
  // #endif
  // #ifdef H5
  if (typeof window !== 'undefined') {
    uni.setClipboardData({
      data: window.location.href,
      success: () => uni.showToast({ title: '链接已复制，可分享给好友', icon: 'success' }),
    })
  }
  // #endif
}

const onDeletePost = () => {
  if (!post.value) return
  uni.showModal({
    title: '删除帖子',
    content: '确定要删除这条帖子吗？删除后将不再公开展示。',
    confirmText: '删除',
    confirmColor: '#f4212e',
    success: async (res) => {
      if (!res.confirm || !post.value) return
      try {
        await deletePost(post.value.id)
        uni.showToast({ title: '已删除', icon: 'success' })
        setTimeout(() => {
          uni.navigateBack()
        }, 600)
      } catch (e) {
        uni.showToast({ title: friendlyNetworkError(e, '删除失败'), icon: 'none' })
      }
    },
  })
}

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
    replyTarget.value = null
    if (created.status === 0) {
      // 灰词转人工：审核通过后才公开
      uni.showToast({ title: '已提交，审核通过后可见', icon: 'none' })
    } else {
      if (post.value) post.value.comment_count = (post.value.comment_count || 0) + 1
      await loadComments(false)
      uni.showToast({ title: '评论成功', icon: 'success' })
    }
  } catch (e) {
    uni.showToast({ title: friendlyNetworkError(e, '评论失败'), icon: 'none' })
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
        await loadComments(false)
      } catch (e) {
        uni.showToast({ title: friendlyNetworkError(e, '删除失败'), icon: 'none' })
      }
    },
  })
}

const goAuthor = () => {
  if (post.value?.user_id) uni.navigateTo({ url: `/pages/profile/index?id=${post.value.user_id}` })
}

const onAuthorActions = () => {
  if (!post.value || !requireLogin()) return
  uni.showActionSheet({ itemList: ['举报帖子', '屏蔽作者'], success: ({ tapIndex }) => {
    if (tapIndex === 0) return onReport()
    const authorId = post.value?.user_id
    if (!authorId) return
    uni.showModal({ title: '屏蔽作者', content: '屏蔽后将隐藏彼此内容并限制互动，可在设置中解除。',
      success: async (result) => {
        if (!result.confirm) return
        try {
          await blockUser(authorId)
          post.value = null
          comments.value = []
          uni.showToast({ title: '已屏蔽', icon: 'success' })
          setTimeout(() => uni.reLaunch({ url: '/pages/index/index' }), 500)
        } catch (error) { uni.showToast({ title: friendlyNetworkError(error, '操作失败'), icon: 'none' }) }
      } })
  } })
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
        uni.showToast({ title: friendlyNetworkError(e, '举报失败'), icon: 'none' })
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
.page-detail {
  min-height: 100vh;
  background: var(--bg-page);
  box-sizing: border-box;
  overflow-x: hidden;
}

.state {
  text-align: center;
  padding: 120rpx 0;
  color: var(--text-3);
  font-size: 26rpx;
}

.body {
  background: var(--bg-card);
  margin: 0;
  overflow-x: hidden;
}

.author {
  display: flex;
  align-items: center;
  padding: 24rpx 28rpx;
  border-bottom: 1rpx solid var(--border-light);
}

.avatar {
  width: 84rpx;
  height: 84rpx;
  border-radius: 50%;
  margin-right: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar-letter {
  font-size: 40rpx;
  font-weight: bold;
  color: var(--text-inverse);
}

.author-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.name-row {
  display: flex;
  align-items: center;
  min-width: 0;
}

.nickname {
  font-size: 30rpx;
  font-weight: bold;
  color: var(--text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.featured-chip {
  margin-left: 12rpx;
  font-size: 18rpx;
  color: var(--primary-strong);
  background: var(--primary-soft);
  border: 1rpx solid var(--primary);
  padding: 1rpx 10rpx;
  border-radius: var(--radius-tag);
  white-space: nowrap;
  flex-shrink: 0;
}

.sub {
  font-size: 24rpx;
  color: var(--text-2);
  margin-top: 6rpx;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.report-btn {
  font-size: 24rpx;
  color: var(--text-3);
  border: 1rpx solid var(--border-light);
  padding: 8rpx 20rpx;
  border-radius: var(--radius-btn);
  white-space: nowrap;
  flex-shrink: 0;
}

.del-btn {
  font-size: 24rpx;
  color: var(--danger-strong);
  border: 1rpx solid var(--danger);
  padding: 8rpx 20rpx;
  border-radius: var(--radius-btn);
  background: rgba(244, 33, 46, 0.08);
  white-space: nowrap;
  flex-shrink: 0;
}

.follow-btn {
  font-size: 24rpx;
  color: var(--text-inverse);
  background: var(--primary);
  padding: 10rpx 24rpx;
  border-radius: var(--radius-btn);
  margin-right: 16rpx;
  white-space: nowrap;
  flex-shrink: 0;
  font-weight: 600;
}

.follow-btn.on {
  background: var(--bg-card-2);
  color: var(--text-2);
  border: 1rpx solid var(--border-light);
}

.content {
  padding: 28rpx;
  overflow-x: hidden;
  word-break: break-word;
  overflow-wrap: break-word;
}

.content-text {
  font-size: 34rpx;
  color: var(--text-1);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: break-word;
  display: block;
}

.content-text .hashtag {
  color: var(--link);
  margin: 0 4rpx;
}

.images {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin: 24rpx 0;
}

.post-image {
  width: 220rpx;
  height: 220rpx;
  border-radius: var(--radius-inner);
  background: var(--bg-card-2);
  border: 1rpx solid var(--border-light);
  box-sizing: border-box;
}

.post-image-single {
  width: 100%;
  max-height: 800rpx;
  border-radius: var(--radius-inner);
  background: var(--bg-card-2);
  border: 1rpx solid var(--border-light);
  box-sizing: border-box;
}

.price {
  font-size: 40rpx;
  font-weight: bold;
  color: var(--primary);
  display: block;
  margin-top: 16rpx;
}

.contact {
  background: var(--bg-page);
  border: 1rpx solid var(--border-light);
  padding: 16rpx 20rpx;
  border-radius: var(--radius-inner);
  margin-top: 20rpx;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}

.contact-label {
  font-size: 24rpx;
  color: var(--text-2);
  font-weight: 500;
}

.contact-value {
  font-size: 28rpx;
  color: var(--primary);
  margin-left: 8rpx;
  font-weight: 500;
  word-break: break-all;
}

.meta {
  display: flex;
  align-items: center;
  margin-top: 24rpx;
  font-size: 24rpx;
  color: var(--text-2);
}

.meta-item {
  color: var(--text-2);
}

.meta-num {
  color: var(--text-1);
  font-weight: 600;
  margin-right: 4rpx;
}

.dot {
  margin: 0 12rpx;
  color: var(--text-3);
}

.action-bar {
  display: flex;
  border-top: 1rpx solid var(--border-light);
  border-bottom: 16rpx solid var(--bg-page);
  padding: 24rpx 28rpx;
  justify-content: space-around;
  align-items: center;
}

.act {
  display: flex;
  align-items: center;
  color: var(--text-1);
  font-size: 26rpx;
  font-weight: 500;
  padding: 8rpx 16rpx;
  border-radius: var(--radius-btn);
}

.act:active {
  background-color: var(--hover-fill);
}

.act.on {
  color: var(--primary);
}

.act.on-like {
  color: var(--like);
}

.act.on-fav {
  color: var(--favorite);
}

.act-icon {
  width: 34rpx;
  height: 34rpx;
  margin-right: 8rpx;
  flex-shrink: 0;
}

/* 图标颜色由 SVG 变体承载（点赞粉/收藏深金），这里只保留文字态 */

.comments {
  padding: 28rpx;
}

.comments-title {
  font-size: 30rpx;
  font-weight: bold;
  color: var(--text-1);
  margin-bottom: 24rpx;
}

.empty-comment {
  text-align: center;
  color: var(--text-2);
  font-size: 26rpx;
  padding: 60rpx 0;
}

.comment {
  display: flex;
  padding: 20rpx 0;
  border-bottom: 1rpx solid var(--border-light);
}

.c-avatar {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  margin-right: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.c-letter {
  font-size: 34rpx;
  font-weight: bold;
  color: var(--text-inverse);
}

.c-main {
  flex: 1;
  min-width: 0;
}

.c-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.c-name {
  font-size: 28rpx;
  color: var(--text-1);
  font-weight: bold;
}

.c-right-acts {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.c-del {
  font-size: 22rpx;
  color: var(--text-2);
  padding: 4rpx 8rpx;
  font-weight: 500;
}

.c-reply-btn {
  font-size: 22rpx;
  color: var(--primary);
  padding: 4rpx 8rpx;
}

.c-text {
  font-size: 28rpx;
  color: var(--text-1);
  margin-top: 8rpx;
  display: block;
  line-height: 1.5;
  word-break: break-word;
  overflow-wrap: break-word;
}

.comment-load-more {
  text-align: center;
  padding: 28rpx 0;
  color: var(--primary);
  font-size: 26rpx;
  font-weight: 500;
}

.comment-no-more {
  text-align: center;
  padding: 28rpx 0;
  color: var(--text-2);
  font-size: 24rpx;
}

.bottom-spacer {
  height: calc(140rpx + env(safe-area-inset-bottom));
}

.comment-input-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  background: var(--bg-card);
  border-top: 1rpx solid var(--border-light);
  padding: 16rpx 24rpx;
  padding-bottom: calc(16rpx + env(safe-area-inset-bottom));
  z-index: 100;
  box-sizing: border-box;
}

.reply-target-tag {
  position: absolute;
  top: -52rpx;
  left: 24rpx;
  background: var(--primary-soft);
  border: 1rpx solid var(--border-primary-soft);
  border-radius: var(--radius-btn);
  padding: 6rpx 18rpx;
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.reply-tip {
  font-size: 22rpx;
  color: var(--primary);
  font-weight: 500;
}

.reply-cancel {
  width: 24rpx;
  height: 24rpx;
  padding: 4rpx;
  flex-shrink: 0;
}

.comment-input {
  flex: 1;
  height: 72rpx;
  background: var(--pill-bg);
  border: 1rpx solid var(--border-light);
  border-radius: var(--radius-btn);
  padding: 0 28rpx;
  font-size: 28rpx;
  color: var(--text-1);
  box-sizing: border-box;
}

.comment-input::placeholder {
  color: var(--text-2);
}

.send-btn {
  margin-left: 16rpx;
  background: var(--primary);
  color: var(--text-inverse);
  font-size: 28rpx;
  font-weight: 600;
  padding: 0 32rpx;
  height: 72rpx;
  line-height: 72rpx;
  border-radius: var(--radius-btn);
  white-space: nowrap;
}

.send-btn.disabled {
  opacity: 0.4;
}
</style>
