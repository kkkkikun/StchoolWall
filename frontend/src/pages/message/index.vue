<template>
  <view class="page-message">
    <!-- 1. 标题栏 -->
    <view class="message-header">
      <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />
      <text class="header-title">消息</text>
    </view>

    <!-- 2. 热门用户榜（横滑 Top5，皇冠+TOP徽章+🔥热度） -->
    <view class="panel" v-if="hotUsers.length">
      <view class="panel-head">
        <text class="panel-title">热门用户榜</text>
        <text class="panel-more" @tap="onMoreRank">更多 ›</text>
      </view>
      <scroll-view scroll-x :show-scrollbar="false" class="rank-scroll">
        <view
          v-for="(u, i) in hotUsers"
          :key="u.id"
          class="rank-user"
          @tap="goProfile(u.id)"
        >
          <text class="crown">{{ i < 3 ? '👑' : '' }}</text>
          <image v-if="u.avatar_url" class="rank-avatar" :src="u.avatar_url" mode="aspectFill" />
          <view v-else class="rank-avatar" :style="{ background: colorOf(u.nickname) }">
            <text>{{ (u.nickname || '?').slice(0, 1) }}</text>
          </view>
          <text class="rank-badge" :class="{ dim: i >= 3 }">TOP{{ i + 1 }}</text>
          <text class="rank-name">{{ u.nickname }}</text>
          <text class="rank-heat">🔥 {{ fmtHeat(u.heat) }}</text>
        </view>
      </scroll-view>
    </view>

    <!-- 3. 互动提醒（横滑最新几条赞/藏/评；更多→互动二级页） -->
    <view class="panel" v-if="reminders.length">
      <view class="panel-head">
        <text class="panel-title">互动提醒</text>
        <text class="panel-more" @tap="goInteractions">更多 ›</text>
      </view>
      <scroll-view scroll-x :show-scrollbar="false" class="rem-scroll">
        <view
          v-for="r in reminders"
          :key="r.id"
          class="rem-chip"
          @tap="goInteractions"
        >
          <view class="rem-icon" :class="`ic-${r.type}`">
            <text>{{ iconOf(r.type) }}</text>
          </view>
          <view class="rem-main">
            <text class="rem-name">{{ r.nickname }}</text>
            <text class="rem-action">{{ r.action }}</text>
            <text class="rem-time">{{ r.time }}</text>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- 4. 动态列表（全部通知；时间右侧+未读红点） -->
    <view class="panel list-panel">
      <view class="panel-head">
        <text class="panel-title">动态</text>
        <text v-if="messages.length" class="panel-more" @tap="onMarkAllRead">全部已读 ✓</text>
      </view>
      <view v-if="messages.length === 0" class="empty-state">
        <text class="empty-emoji">📭</text>
        <text class="empty-text">{{ loggedIn ? '暂无消息' : '登录后查看消息' }}</text>
      </view>
      <view
        v-for="m in messages"
        :key="m.id"
        class="msg-row"
        :class="{ unread: !m.is_read }"
        @tap="onMessage(m)"
      >
        <view class="sender-avatar" :class="{ sys: m._system }" :style="{ background: m._system ? '#fdf0f2' : colorOf(m.nickname) }">
          <text v-if="m._type === 'announcement'">📢</text>
          <text v-else-if="m._type === 'moderation'">🛡️</text>
          <text v-else>{{ (m.nickname || '?').slice(0, 1) }}</text>
        </view>
        <view class="msg-main">
          <view class="msg-title-row">
            <text class="msg-name">{{ m.nickname }}</text>
            <text v-if="m._type === 'announcement'" class="sys-tag">公告</text>
          </view>
          <text class="msg-text">{{ m.brief }}</text>
          <text v-if="m.sub" class="msg-sub">{{ m.sub }}</text>
        </view>
        <view class="msg-right">
          <text class="msg-time">{{ m.time }}</text>
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
import { getHotRanking, type HotUser } from '@/api/profile'
import { tokenStorage } from '@/utils/storage'

// 沉浸式标题栏：预留状态栏高度（H5 下为 0，真机防标题被状态栏压住）
const statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0

const loggedIn = tokenStorage.isLoggedIn()
const hotUsers = ref<HotUser[]>([])
const summary = ref({ comment: 0, like: 0, favorite: 0, group: 0, moderation: 0, im: 0 })

interface MsgRow {
  id: number
  nickname: string
  time: string
  brief: string
  sub: string
  post_id: number | null
  is_read: boolean
  _type: NotificationType
  _system: boolean
}
const messages = ref<MsgRow[]>([])

/** 赞/藏/评 聚合为互动提醒 chips（最新 5 条） */
const ACTION_TEXT: Partial<Record<NotificationType, string>> = {
  like: '赞了你的帖子',
  favorite: '收藏了你的帖子',
  comment: '评论了你的帖子',
}
const reminders = computed(() =>
  messages.value
    .filter((m) => m._type in ACTION_TEXT!)
    .slice(0, 5)
    .map((m) => ({
      id: m.id,
      type: m._type as string,
      nickname: m.nickname,
      action: ACTION_TEXT[m._type] || '与你互动',
      time: m.time,
    })),
)

const iconOf = (type: string) =>
  (({ like: '♥', favorite: '★', comment: '💬' }) as Record<string, string>)[type] || '•'

const AVATAR_COLORS = ['#f8c8b8', '#e8d5f5', '#d5e8f5', '#d5f0d5', '#fbe3b5', '#f5d0d8']
const colorOf = (s: string) => {
  let h = 0
  for (let i = 0; i < (s || '').length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[h % AVATAR_COLORS.length]
}

/** 热度格式化：≥1000 → 2.4k */
const fmtHeat = (n: number) => {
  if (n < 1000) return String(n)
  const k = n / 1000
  return `${k >= 100 ? Math.round(k) : k.toFixed(1).replace(/\.0$/, '')}k`
}

const pad = (n: number) => String(n).padStart(2, '0')
/** 列表时间：今天 HH:MM / 昨天 HH:MM / M-D */
const fmtTime = (iso: string) => {
  const d = new Date(iso)
  if (!d.getTime()) return ''
  const now = new Date()
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  if (d.toDateString() === now.toDateString()) return hm
  const yest = new Date(now)
  yest.setDate(now.getDate() - 1)
  if (d.toDateString() === yest.toDateString()) return `昨天 ${hm}`
  return `${d.getMonth() + 1}-${d.getDate()}`
}

const briefOf = (n: NotificationItem) => {
  if (n.type === 'like') return '赞了你的帖子'
  if (n.type === 'favorite') return '收藏了你的帖子'
  if (n.type === 'comment') return '评论了你的帖子'
  if (n.type === 'group') return '邀请你加入组局'
  if (n.type === 'moderation') return '你发布的帖子未通过审核'
  if (n.type === 'announcement') return (n as { payload?: { title?: string } }).payload?.title || '系统公告'
  return '有了新动态'
}

const loadHot = async () => {
  try {
    hotUsers.value = (await getHotRanking(5)).items
  } catch { /* 榜单非关键，失败静默 */ }
}

const loadMessages = async () => {
  if (!loggedIn) return
  try {
    const [res, sum] = await Promise.all([listNotifications(), unreadSummary()])
    summary.value = sum
    messages.value = res.items.map((n) => {
      const payload = (n as { payload?: { title?: string; content?: string } }).payload
      const system = n.type === 'moderation' || n.type === 'announcement'
      return {
        id: n.id,
        _type: n.type,
        nickname: system ? '系统' : n.actor.nickname,
        time: fmtTime(n.created_at),
        brief: n.type === 'announcement' ? (payload?.title || '系统公告') : briefOf(n),
        sub: n.type === 'announcement' ? (payload?.content ? payload.content.slice(0, 48) : '') : '',
        post_id: n.post_id,
        is_read: n.is_read,
        _system: system,
      }
    })
  } catch { /* 忽略 */ }
}

onShow(() => {
  loadHot()
  loadMessages()
})

const goInteractions = () => uni.navigateTo({ url: '/pages/interactions/index' })
const goProfile = (id: string) => uni.navigateTo({ url: `/pages/profile/index?id=${id}` })
const onMoreRank = () => uni.showToast({ title: '完整榜单即将上线', icon: 'none' })

const onMarkAllRead = async () => {
  try {
    await readAllNotifications()
    uni.showToast({ title: '已全部标记为已读', icon: 'success' })
    loadMessages()
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' })
  }
}

const onMessage = async (m: MsgRow) => {
  if (!m.is_read) {
    try {
      await readNotification(m.id)
      m.is_read = true
    } catch { /* 忽略 */ }
  }
  if (m._type === 'announcement') {
    uni.navigateTo({ url: `/pages/announcement-detail/index?id=${m.id}` })
    return
  }
  if (m.post_id) {
    uni.navigateTo({ url: `/pages/post-detail/index?id=${m.post_id}` })
  }
}
</script>

<style scoped>
.page-message { background-color: var(--bg-page); min-height: 100vh; }

.message-header { background-color: var(--brand-red); padding: 30rpx 40rpx; text-align: center; }
.header-title { color: #ffffff; font-size: 34rpx; font-weight: bold; letter-spacing: 2rpx; }

/* 面板（参考稿：白卡圆角 + 标题行 + 更多） */
.panel { background: #ffffff; border-radius: var(--radius-card); margin: 20rpx 24rpx 0; padding: 24rpx 24rpx 20rpx; }
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20rpx; }
.panel-title { font-size: 30rpx; font-weight: bold; color: var(--text-1); }
.panel-more { font-size: 24rpx; color: var(--text-3); }

/* 热门用户榜 */
.rank-scroll { white-space: nowrap; }
.rank-user { display: inline-flex; flex-direction: column; align-items: center; width: 138rpx; vertical-align: top; }
.crown { height: 40rpx; font-size: 34rpx; line-height: 1; }
.rank-avatar { width: 96rpx; height: 96rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 44rpx; color: #fff; font-weight: bold; }
.rank-badge { margin-top: -12rpx; background: var(--brand-red-dark); color: #fff; font-size: 18rpx; font-weight: bold; padding: 2rpx 14rpx; border-radius: 16rpx; border: 3rpx solid #fff; line-height: 1.5; }
.rank-badge.dim { background: #f0a7b1; }
.rank-name { margin-top: 8rpx; font-size: 22rpx; color: var(--text-1); max-width: 130rpx; overflow: hidden; text-overflow: ellipsis; }
.rank-heat { margin-top: 4rpx; font-size: 20rpx; color: var(--brand-red-dark); font-weight: 600; }

/* 互动提醒 */
.rem-scroll { white-space: nowrap; }
.rem-chip { display: inline-flex; align-items: flex-start; width: 300rpx; background: var(--bg-page); border-radius: 16rpx; padding: 20rpx; margin-right: 16rpx; vertical-align: top; }
.rem-icon { width: 72rpx; height: 72rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 32rpx; color: #fff; flex-shrink: 0; }
.ic-like { background: #ff5c7a; }
.ic-favorite { background: #ffb822; }
.ic-comment { background: #9b7df7; }
.rem-main { margin-left: 16rpx; min-width: 0; white-space: normal; }
.rem-name { display: block; font-size: 26rpx; font-weight: bold; color: var(--brand-red-dark); max-width: 170rpx; overflow: hidden; text-overflow: ellipsis; }
.rem-action { display: block; font-size: 24rpx; color: var(--text-1); margin-top: 6rpx; }
.rem-time { display: block; font-size: 20rpx; color: var(--text-3); margin-top: 10rpx; }

/* 动态列表 */
.list-panel { padding-bottom: 8rpx; margin-bottom: 24rpx; }
.msg-row { display: flex; align-items: center; padding: 24rpx 4rpx; border-bottom: 1rpx solid #f5f5f6; }
.msg-row:last-child { border-bottom: none; }
.msg-row.unread { background: linear-gradient(90deg, #fff7f8, #ffffff); border-radius: 16rpx; padding-left: 12rpx; padding-right: 12rpx; }
.sender-avatar { width: 88rpx; height: 88rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 40rpx; color: #fff; font-weight: bold; flex-shrink: 0; }
.sender-avatar.sys { color: var(--brand-red-dark); font-size: 40rpx; }
.msg-main { flex: 1; min-width: 0; margin-left: 20rpx; }
.msg-title-row { display: flex; align-items: center; gap: 12rpx; }
.msg-name { font-size: 28rpx; font-weight: bold; color: var(--text-1); }
.sys-tag { font-size: 20rpx; color: var(--brand-red-dark); background: #fdf0f2; border: 1rpx solid #ef8a97; padding: 2rpx 10rpx; border-radius: 999rpx; }
.msg-text { display: block; font-size: 25rpx; color: var(--text-2); margin-top: 8rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.msg-sub { display: block; font-size: 22rpx; color: var(--text-3); margin-top: 4rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.msg-right { display: flex; flex-direction: column; align-items: flex-end; margin-left: 16rpx; gap: 12rpx; }
.msg-time { font-size: 22rpx; color: var(--text-3); }
.unread-dot { width: 16rpx; height: 16rpx; border-radius: 50%; background: var(--brand-red-dark); }

.empty-state { padding: 60rpx 0 70rpx; display: flex; flex-direction: column; align-items: center; }
.empty-emoji { font-size: 80rpx; margin-bottom: 20rpx; opacity: 0.5; }
.empty-text { font-size: 26rpx; color: var(--text-3); letter-spacing: 2rpx; }
</style>
