<template>
  <view class="page-message" :class="themeClass">
    <!-- 1. 标题栏（沉浸式：微信胶囊安全避让） -->
    <CustomNavBar title="消息" :show-back="false" />

    <!-- 2. 热门用户榜（横滑 Top5，皇冠+TOP徽章+热度火焰） -->
    <view class="panel" v-if="hotUsers.length">
      <view class="panel-head">
        <text class="panel-title">热门用户榜</text>
        <view class="panel-more" @tap="onMoreRank">
          <text>更多</text>
          <image class="chev" :src="ICONS['arrow-right']" mode="aspectFit" />
        </view>
      </view>
      <scroll-view scroll-x :show-scrollbar="false" class="rank-scroll">
        <view
          v-for="(u, i) in hotUsers"
          :key="u.id"
          class="rank-user"
          @tap="goProfile(u.id)"
        >
          <image v-if="i < 3" class="crown" :src="ICON_TONES['state-crown']['primary']" mode="aspectFit" />
          <image v-if="u.avatar_url" class="rank-avatar" :src="u.avatar_url" mode="aspectFill" />
          <view v-else class="rank-avatar" :style="{ background: colorOf(u.nickname) }">
            <text>{{ (u.nickname || '?').slice(0, 1) }}</text>
          </view>
          <text class="rank-badge" :class="{ dim: i >= 3 }">TOP{{ i + 1 }}</text>
          <text class="rank-name">{{ u.nickname }}</text>
          <view class="rank-heat">
            <image class="heat-icon" :src="ICON_TONES['hot']['primary']" mode="aspectFit" />
            <text>{{ fmtHeat(u.heat) }}</text>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- 3. 互动提醒（横滑最新几条赞/藏/评；更多→互动二级页） -->
    <view class="panel" v-if="reminders.length">
      <view class="panel-head">
        <text class="panel-title">互动提醒</text>
        <view class="panel-more" @tap="goInteractions">
          <text>更多</text>
          <image class="chev" :src="ICONS['arrow-right']" mode="aspectFit" />
        </view>
      </view>
      <view class="rem-list">
        <view
          v-for="r in reminders"
          :key="r.id"
          class="rem-row"
          @tap="goInteractions"
        >
          <view class="rem-icon" :class="`ic-${r.type}`">
            <image class="rem-icon-img" :src="iconOf(r.type)" mode="aspectFit" />
          </view>
          <view class="rem-main">
            <text class="rem-name">{{ r.nickname }} {{ r.action }}</text>
            <text class="rem-time">{{ r.time }}</text>
          </view>
          <image class="rem-arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
        </view>
      </view>
    </view>

    <!-- 4. 动态列表（全部通知；时间右侧+未读红点） -->
    <view class="panel list-panel">
      <view class="panel-head">
        <text class="panel-title">动态</text>
        <view v-if="messages.length" class="panel-more" @tap="onMarkAllRead">
          <image class="more-check" :src="ICONS['check']" mode="aspectFit" />
          <text>全部已读</text>
        </view>
      </view>
      <view v-if="messages.length === 0" class="empty-state">
        <image class="empty-emoji" :src="ICONS['state-inbox']" mode="aspectFit" />
        <text class="empty-text">{{ loggedIn ? '暂无消息' : '登录后查看消息' }}</text>
      </view>
      <view
        v-for="m in messages"
        :key="m.id"
        class="msg-row"
        :class="{ unread: !m.is_read }"
        @tap="onMessage(m)"
      >
        <view class="sender-avatar" :class="{ sys: m._system }" :style="{ background: m._system ? 'var(--primary-soft)' : colorOf(m.nickname) }">
          <image v-if="m._type === 'announcement'" class="sys-icon"
                 :src="ICON_TONES['notice']['primary']" mode="aspectFit" />
          <image v-else-if="m._type === 'moderation'" class="sys-icon"
                 :src="ICON_TONES['shield']['primary']" mode="aspectFit" />
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
import { avatarColor as colorOf } from '@/utils/avatar'
import { useTheme } from '@/utils/theme'
import { onShow } from '@dcloudio/uni-app'
import TabBar from '@/components/tab-bar.vue'
import CustomNavBar from '@/components/custom-nav-bar.vue'
import { unreadSummary, listNotifications, readAllNotifications, readNotification } from '@/api/notification'
import type { NotificationItem, NotificationType } from '@/api/notification'
import { getHotRanking, type HotUser } from '@/api/profile'
import { tokenStorage } from '@/utils/storage'
import { ICONS, ICON_TONES } from '@/utils/icons'

const { themeClass } = useTheme()

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
  ({
    like: ICON_TONES['heart-on']['inverse'],
    favorite: ICON_TONES['star-on']['inverse'],
    comment: ICON_TONES['comment']['inverse'],
  } as Record<string, string>)[type] || ICON_TONES['comment']['inverse']


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
const onMoreRank = () => uni.navigateTo({ url: '/pages/hot-users/index' })

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

.message-header { background-color: var(--bg-page); border-bottom: 1rpx solid var(--border-light); padding: 30rpx 40rpx; text-align: center; }
.header-title { color: var(--text-1); font-size: 34rpx; font-weight: 700; letter-spacing: 2rpx; }

/* 面板（参考稿：白卡圆角 + 标题行 + 更多） */
.panel { background: var(--bg-card); border-radius: var(--radius-card); margin: 20rpx 24rpx 0; padding: 24rpx 24rpx 20rpx; }
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20rpx; }
.panel-title { font-size: 30rpx; font-weight: bold; color: var(--text-1); }
.panel-more { font-size: 24rpx; color: var(--text-3); display: inline-flex; align-items: center; min-height: 64rpx; }
.chev { width: 20rpx; height: 20rpx; margin-left: 2rpx; flex-shrink: 0; }
.more-check { width: 22rpx; height: 22rpx; margin-right: 4rpx; flex-shrink: 0; }

/* 热门用户榜 */
.rank-scroll { white-space: nowrap; }
.rank-user { display: inline-flex; flex-direction: column; align-items: center; width: 138rpx; vertical-align: top; }
.crown { width: 34rpx; height: 34rpx; flex-shrink: 0; }
.rank-avatar { width: 96rpx; height: 96rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 44rpx; color: var(--on-avatar); font-weight: bold; }
.rank-badge { margin-top: -12rpx; background: var(--primary-badge); color: var(--text-inverse); font-size: 22rpx; font-weight: bold; padding: 2rpx 14rpx; border-radius: var(--radius-inner); border: 3rpx solid #fff; line-height: 1.5; }
.rank-badge.dim { background: var(--primary-fill); }
.rank-name { margin-top: 8rpx; font-size: 22rpx; color: var(--text-1); max-width: 130rpx; overflow: hidden; text-overflow: ellipsis; }
.rank-heat { margin-top: 4rpx; font-size: 22rpx; color: var(--primary-text); font-weight: 600;
  display: inline-flex; align-items: center; }
.heat-icon { width: 20rpx; height: 20rpx; margin-right: 4rpx; flex-shrink: 0; }

/* 互动提醒 */
.rem-list { margin-top: -4rpx; }
.rem-row { display: flex; align-items: center; padding: 18rpx 0; border-bottom: 1rpx solid var(--border-light); }
.rem-row:last-child { border-bottom: none; }
.rem-icon { width: 68rpx; height: 68rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.rem-icon-img { width: 32rpx; height: 32rpx; }
.ic-like { background: var(--danger); }
.ic-favorite { background: var(--favorite); }
.ic-comment { background: var(--accent-violet); }
.rem-main { flex: 1; min-width: 0; margin-left: 18rpx; }
.rem-name { display: block; font-size: 26rpx; color: var(--text-1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rem-time { display: block; font-size: 22rpx; color: var(--text-3); margin-top: 4rpx; }
.rem-arrow { width: 28rpx; height: 28rpx; margin-left: 10rpx; flex-shrink: 0; }

/* 动态列表 */
.list-panel { padding-bottom: 8rpx; margin-bottom: 24rpx; }
.msg-row { display: flex; align-items: center; padding: 24rpx 4rpx; border-bottom: 1rpx solid var(--border-light); }
.msg-row:last-child { border-bottom: none; }
.msg-row.unread { background: var(--card-gradient); border-radius: var(--radius-inner); padding-left: 12rpx; padding-right: 12rpx; }
.sender-avatar { width: 88rpx; height: 88rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 40rpx; color: var(--on-avatar); font-weight: bold; flex-shrink: 0; }
.sender-avatar.sys { color: var(--primary-text); font-size: 40rpx; }
.sys-icon { width: 40rpx; height: 40rpx; }
.msg-main { flex: 1; min-width: 0; margin-left: 20rpx; }
.msg-title-row { display: flex; align-items: center; gap: 12rpx; }
.msg-name { font-size: 28rpx; font-weight: bold; color: var(--text-1); }
.sys-tag { font-size: 22rpx; color: var(--primary-text); background: var(--primary-soft); border: 1rpx solid var(--primary); padding: 2rpx 10rpx; border-radius: 999rpx; }
.msg-text { display: block; font-size: 25rpx; color: var(--text-2); margin-top: 8rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.msg-sub { display: block; font-size: 22rpx; color: var(--text-3); margin-top: 4rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.msg-right { display: flex; flex-direction: column; align-items: flex-end; margin-left: 16rpx; gap: 12rpx; }
.msg-time { font-size: 22rpx; color: var(--text-3); }
.unread-dot { width: 16rpx; height: 16rpx; border-radius: 50%; background: var(--primary-strong); }

.empty-state { padding: 60rpx 0 70rpx; display: flex; flex-direction: column; align-items: center; }
.empty-emoji { width: 80rpx; height: 80rpx; margin-bottom: 20rpx; opacity: 0.5; }
.empty-text { font-size: 26rpx; color: var(--text-3); letter-spacing: 2rpx; }
</style>
