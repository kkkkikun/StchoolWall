<template>
  <view class="page-interactions">
    <!-- 1. 头部：返回 + 标题 -->
    <view class="header">
      <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />
      <view class="header-row">
        <text class="back-btn" @tap="goBack">‹</text>
        <text class="header-title">互动消息</text>
        <view class="header-right" @tap="onMarkAllRead">
          <text>全部已读</text>
        </view>
      </view>
    </view>

    <!-- 2. 筛选 chips：全部 / 赞 / 收藏 / 评论（抖音式聚合） -->
    <view class="chip-row">
      <view
        v-for="c in chips"
        :key="c.key"
        class="chip"
        :class="{ on: active === c.key }"
        @tap="switchChip(c.key)"
      >
        <text>{{ c.label }}</text>
        <text v-if="c.unread > 0" class="chip-badge">{{ c.unread > 99 ? '99+' : c.unread }}</text>
      </view>
    </view>

    <!-- 3. 聚合列表：点击直达被互动的帖子 -->
    <scroll-view scroll-y class="list-area">
      <view v-if="items.length === 0" class="empty-state">
        <text class="empty-emoji">💌</text>
        <text class="empty-text">还没有互动消息</text>
      </view>
      <view
        v-for="it in items"
        :key="it.id"
        class="interaction-card"
        :class="{ unread: !it.is_read }"
        @tap="onItem(it)"
      >
        <view class="avatar" :style="{ background: colorOf(it.nickname) }">
          <text>{{ (it.nickname || '?').slice(0, 1) }}</text>
        </view>
        <view class="main">
          <view class="line1">
            <text class="name">{{ it.nickname }}</text>
            <text class="action" :class="`act-${it.type}`">{{ it.action }}</text>
          </view>
          <text v-if="it.excerpt" class="excerpt">{{ it.excerpt }}</text>
          <view class="line2">
            <text class="post-ref">「{{ it.post_snippet }}」</text>
            <text class="time">{{ it.time }}</text>
          </view>
        </view>
        <view v-if="!it.is_read" class="unread-dot" />
        <text class="arrow">›</text>
      </view>
      <view class="list-foot" />
    </scroll-view>

    <TabBar :current="3" />
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import TabBar from '@/components/tab-bar.vue'
import {
  listNotifications,
  readNotification,
  readAllNotifications,
  unreadSummary,
  type NotificationItem,
} from '@/api/notification'
import { tokenStorage } from '@/utils/storage'

const statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0

type ChipKey = 'all' | 'like' | 'favorite' | 'comment'
const active = ref<ChipKey>('all')
const raw = ref<NotificationItem[]>([])
const summary = ref({ comment: 0, like: 0, favorite: 0, group: 0, moderation: 0, im: 0 })

const chips = computed(() => [
  { key: 'all' as const, label: '全部', unread: summary.value.like + summary.value.favorite + summary.value.comment },
  { key: 'like' as const, label: '赞', unread: summary.value.like },
  { key: 'favorite' as const, label: '收藏', unread: summary.value.favorite },
  { key: 'comment' as const, label: '评论', unread: summary.value.comment },
])

const ACTION_TEXT: Record<string, string> = {
  like: '赞了你的帖子',
  favorite: '收藏了你的帖子',
  comment: '评论了你的帖子',
}

interface Row {
  id: number
  type: string
  nickname: string
  action: string
  excerpt: string
  post_snippet: string
  time: string
  post_id: number | null
  is_read: boolean
}
const items = computed<Row[]>(() =>
  raw.value
    .filter((n) => n.type in ACTION_TEXT)
    .filter((n) => active.value === 'all' || n.type === active.value)
    .map((n) => {
      const payload = (n as { payload?: { content?: string; title?: string } }).payload
      return {
        id: n.id,
        type: n.type,
        nickname: n.actor?.nickname || '同学',
        action: ACTION_TEXT[n.type] || '与你互动',
        excerpt: n.type === 'comment' ? payload?.content || '' : '',
        post_snippet: postSnippetOf(n),
        time: timeAgo(n.created_at),
        post_id: n.post_id,
        is_read: n.is_read,
      }
    }),
)

// 通知未带帖子标题时，用不了内容就显示编号（列表页不额外拉帖，保持轻量）
const postSnippetOf = (n: NotificationItem) => (n.post_id ? `帖子 #${n.post_id}` : '已删除的帖子')

const AVATAR_COLORS = ['#2f86f6', '#ff5c7a', '#ffb822', '#2ed573', '#d3adf7', '#ffd591']
const colorOf = (s: string) => {
  let h = 0
  for (let i = 0; i < (s || '').length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[h % AVATAR_COLORS.length]
}

const timeAgo = (t: string) => {
  const ts = new Date(t).getTime()
  if (!ts) return ''
  const diff = Date.now() - ts
  const m = Math.floor(diff / 60000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m}分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}小时前`
  const d = Math.floor(h / 24)
  return d < 7 ? `${d}天前` : ''
}

const load = async () => {
  if (!tokenStorage.isLoggedIn()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  try {
    const [list, sum] = await Promise.all([listNotifications(), unreadSummary()])
    raw.value = list.items
    summary.value = sum
  } catch { /* 忽略 */ }
}

onShow(() => load())

const switchChip = (key: ChipKey) => {
  active.value = key
}

const onItem = async (it: Row) => {
  if (!it.is_read) {
    try {
      await readNotification(it.id)
      it.is_read = true
      summary.value = await unreadSummary()
    } catch { /* 忽略 */ }
  }
  // 精细跳转：直达被赞/被评/被藏的那条帖子
  if (it.post_id) {
    uni.navigateTo({ url: `/pages/post-detail/index?id=${it.post_id}` })
  }
}

const onMarkAllRead = async () => {
  try {
    await readAllNotifications()
    uni.showToast({ title: '已全部已读', icon: 'success' })
    await load()
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' })
  }
}

const goBack = () => uni.navigateBack({ fail: () => uni.reLaunch({ url: '/pages/message/index' }) })
</script>

<style scoped>
.page-interactions { min-height: 100vh; background-color: var(--bg-page); display: flex; flex-direction: column; }

.header { background-color: var(--brand-red); }
.header-row { height: 88rpx; display: flex; align-items: center; padding: 0 24rpx; }
.back-btn { font-size: 56rpx; color: var(--text-1); line-height: 1; padding: 0 12rpx; }
.header-title { flex: 1; text-align: center; font-size: 32rpx; font-weight: bold; color: var(--text-1); }
.header-right { font-size: 24rpx; color: var(--text-1); opacity: 0.75; }

/* 与首页吸顶 Tab 同规格：下划线式，弃用药丸 chips；未读数改为红色小角标 */
.chip-row { display: flex; gap: 36rpx; padding: 16rpx 24rpx; background: #ffffff; }
.chip { position: relative; font-size: 28rpx; color: var(--text-2); padding-bottom: 12rpx; line-height: 1.4; }
.chip.on { color: var(--text-1); font-weight: bold; border-bottom: 6rpx solid var(--brand-red); }
.chip-badge { margin-left: 8rpx; font-size: 20rpx; font-weight: normal; color: var(--brand-red-dark); }

.list-area { flex: 1; padding: 16rpx 24rpx 0; box-sizing: border-box; }

.interaction-card {
  position: relative;
  background: #ffffff;
  border-radius: var(--radius-card);
  padding: 24rpx;
  margin-bottom: 16rpx;
  display: flex;
  align-items: flex-start;
}
.interaction-card.unread { background: #fff8f8; }

.avatar { width: 80rpx; height: 80rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 36rpx; color: #fff; font-weight: bold; flex-shrink: 0; }
.main { flex: 1; min-width: 0; margin-left: 20rpx; }
.line1 { display: flex; align-items: center; flex-wrap: wrap; }
.name { font-size: 28rpx; font-weight: 600; color: var(--text-1); }
.action { font-size: 24rpx; color: var(--text-2); margin-left: 10rpx; }
.act-like { color: #ff5c7a; }
.act-favorite { color: #ffb822; }
.act-comment { color: #2f86f6; }
.excerpt { display: block; font-size: 26rpx; color: var(--text-1); margin-top: 10rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.line2 { display: flex; align-items: center; margin-top: 10rpx; }
.post-ref { font-size: 22rpx; color: var(--text-3); max-width: 380rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.time { font-size: 22rpx; color: var(--text-3); margin-left: 16rpx; }
.unread-dot { position: absolute; left: 12rpx; top: 12rpx; width: 14rpx; height: 14rpx; border-radius: 50%; background: var(--brand-red-dark); }
.arrow { font-size: 40rpx; color: #c8c9cc; margin-left: 8rpx; align-self: center; }

.empty-state { padding-top: 200rpx; display: flex; flex-direction: column; align-items: center; }
.empty-emoji { font-size: 96rpx; margin-bottom: 24rpx; opacity: 0.5; }
.empty-text { font-size: 28rpx; color: var(--text-3); }
.list-foot { height: 120rpx; }
</style>
