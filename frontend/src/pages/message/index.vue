<template>
  <view class="page-message">
    <!-- 1. 红色标题栏 -->
    <view class="message-header">
      <text class="header-title">消息</text>
    </view>

    <!-- 2. 4 分类通知 -->
    <view class="msg-category-row">
      <view
        v-for="c in categories"
        :key="c.type"
        class="category-item"
        @tap="onCategory(c.type)"
      >
        <view class="icon-wrapper" :class="`bg-${c.colorClass}`">
          <text class="category-icon">{{ c.icon }}</text>
          <text v-if="c.unread > 0" class="badge-num">
            {{ c.unread > 99 ? '99+' : c.unread }}
          </text>
        </view>
        <text class="category-label">{{ c.name }}</text>
      </view>
    </view>

    <!-- 3. 帖子动态标题 + 全部已读 -->
    <view class="dynamic-control-bar">
      <text class="section-title">{{ filterLabel }}</text>
      <view v-if="messages.length > 0" class="mark-read-btn" @tap="onMarkAllRead">
        <text>全部已读</text>
        <text class="icon-check">✓</text>
      </view>
    </view>

    <!-- 4. 内容区 -->
    <view class="message-content-area">
      <view v-if="messages.length === 0" class="empty-state">
        <text class="empty-emoji">📭</text>
        <text class="empty-text">{{ emptyText }}</text>
      </view>
      <view v-else>
        <view
          v-for="m in messages"
          :key="m.id"
          class="message-card"
          :class="{ unread: !m.is_read }"
          @tap="onMessage(m)"
        >
          <view class="sender-avatar" :style="{ background: colorOf(m.nickname) }">
            <text>{{ (m.nickname || '?').slice(0, 1) }}</text>
          </view>
          <view class="msg-main">
            <view class="msg-top">
              <text class="sender-name">{{ m.nickname }}</text>
              <text class="msg-time">{{ m.time }}</text>
            </view>
            <text class="msg-text">{{ m.brief }}</text>
          </view>
          <view v-if="!m.is_read" class="unread-dot" />
        </view>
      </view>
    </view>

    <TabBar :current="3" />
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import TabBar from '@/components/tab-bar.vue'
import { unreadSummary, listNotifications, readAllNotifications, readNotification } from '@/api/notification'
import type { NotificationItem, NotificationType } from '@/api/notification'
import { tokenStorage } from '@/utils/storage'

const summary = ref({ comment: 0, like: 0, group: 0, moderation: 0, im: 0 })
const messages = ref<Array<{ id: number; nickname: string; time: string; brief: string; post_id: number | null; is_read: boolean }>>([])
const filter = ref<NotificationType | ''>('')

const categories = computed(() => [
  { type: 'comment' as const, name: '评论', icon: '💬', colorClass: 'blue', unread: summary.value.comment },
  { type: 'like' as const, name: '赞', icon: '♡', colorClass: 'pink', unread: summary.value.like },
  { type: 'group' as const, name: '组局', icon: '👥', colorClass: 'yellow', unread: summary.value.group },
  { type: 'im' as const, name: '私信', icon: '✉️', colorClass: 'green', unread: summary.value.im },
])

const filterLabel = computed(() => {
  const m: Record<string, string> = { comment: '评论', like: '赞和收藏', group: '组局', moderation: '系统通知', '': '帖子动态' }
  return m[filter.value] || '帖子动态'
})
const emptyText = computed(() => (filter.value ? `暂无${filterLabel.value}通知` : '暂无消息'))

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

const briefOf = (n: NotificationItem) => {
  if (n.type === 'like') return '赞了你的帖子'
  if (n.type === 'comment') return '评论了你的帖子'
  if (n.type === 'group') return '邀请你加入组局'
  if (n.type === 'moderation') return '你发布的帖子未通过审核'
  return '有了新动态'
}

const loadSummary = async () => {
  if (!tokenStorage.isLoggedIn()) return
  try {
    summary.value = await unreadSummary()
  } catch { /* 忽略 */ }
}

const loadMessages = async () => {
  if (!tokenStorage.isLoggedIn()) return
  try {
    const res = await listNotifications(filter.value || undefined)
    messages.value = res.items.map((n) => ({
      id: n.id,
      nickname: n.type === 'moderation' ? '系统' : n.actor.nickname,
      time: timeAgo(n.created_at),
      brief: briefOf(n),
      post_id: n.post_id,
      is_read: n.is_read,
    }))
  } catch { /* 忽略 */ }
}

onShow(() => {
  loadSummary()
  loadMessages()
})

const onCategory = (type: string) => {
  if (type === 'im') {
    uni.showToast({ title: '私信暂未开放', icon: 'none' })
    return
  }
  filter.value = filter.value === type ? '' : (type as NotificationType)
  loadMessages()
}

const onMarkAllRead = async () => {
  try {
    await readAllNotifications()
    uni.showToast({ title: '已全部标记为已读', icon: 'success' })
    await loadSummary()
    await loadMessages()
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' })
  }
}

const onMessage = async (m: { id: number; post_id: number | null; is_read: boolean }) => {
  // 标记已读
  if (!m.is_read) {
    try {
      await readNotification(m.id)
      m.is_read = true
      await loadSummary()
    } catch { /* 忽略 */ }
  }
  if (m.post_id) {
    uni.navigateTo({ url: `/pages/post-detail/index?id=${m.post_id}` })
  }
}
</script>

<style scoped>
.page-message { background-color: #ffffff; min-height: 100vh; }

.message-header { background-color: var(--brand-red); padding: 30rpx 40rpx; text-align: center; }
.header-title { color: #ffffff; font-size: 34rpx; font-weight: bold; letter-spacing: 2rpx; }

.msg-category-row { padding: 40rpx 44rpx; background-color: #ffffff; border-bottom: 16rpx solid var(--bg-page); display: flex; justify-content: space-between; }
.category-item { display: flex; flex-direction: column; align-items: center; }
.icon-wrapper { width: 104rpx; height: 104rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; position: relative; }
.bg-blue { background-color: #2f86f6; }
.bg-pink { background-color: #ff5c7a; }
.bg-yellow { background-color: #ffb822; }
.bg-green { background-color: #2ed573; }
.category-icon { font-size: 44rpx; }
.badge-num { position: absolute; top: -4rpx; right: -8rpx; background-color: var(--brand-red-dark); color: #ffffff; font-size: 20rpx; font-weight: bold; padding: 2rpx 10rpx; border-radius: 20rpx; border: 4rpx solid #ffffff; line-height: 1.2; }
.category-label { font-size: 26rpx; color: var(--text-1); margin-top: 16rpx; font-weight: 500; }

.dynamic-control-bar { padding: 36rpx 32rpx; display: flex; align-items: center; justify-content: space-between; }
.section-title { font-size: 32rpx; font-weight: bold; color: #111; }
.mark-read-btn { display: flex; align-items: center; font-size: 24rpx; color: var(--text-3); }
.icon-check { margin-left: 8rpx; font-size: 24rpx; }

.empty-state { padding-top: 160rpx; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.empty-emoji { font-size: 96rpx; margin-bottom: 24rpx; opacity: 0.5; }
.empty-text { font-size: 28rpx; color: #aaa; letter-spacing: 2rpx; }

.message-card { padding: 24rpx 32rpx; border-bottom: 1rpx solid #f2f3f5; display: flex; align-items: center; position: relative; }
.message-card.unread { background: #fff8f8; }
.sender-avatar { width: 88rpx; height: 88rpx; border-radius: 50%; margin-right: 20rpx; display: flex; align-items: center; justify-content: center; font-size: 40rpx; color: #fff; font-weight: bold; }
.msg-main { flex: 1; display: flex; flex-direction: column; }
.msg-top { display: flex; justify-content: space-between; }
.sender-name { font-size: 28rpx; color: #323233; font-weight: 500; }
.msg-time { font-size: 22rpx; color: #c8c9cc; }
.msg-text { font-size: 24rpx; color: #969799; margin-top: 8rpx; }
.unread-dot { position: absolute; top: 36rpx; right: 24rpx; width: 16rpx; height: 16rpx; border-radius: 50%; background: var(--brand-red); }
</style>
