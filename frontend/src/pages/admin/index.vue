<template>
  <view class="page-admin">
    <!-- 红色头部：标题 + 看板速览 -->
    <view class="admin-header">
      <text class="header-title">管理后台</text>
      <view class="stats-strip">
        <view class="strip-item">
          <text class="strip-num">{{ stats.pending_posts }}</text>
          <text class="strip-label">待审</text>
        </view>
        <view class="strip-item">
          <text class="strip-num">{{ stats.pending_reports }}</text>
          <text class="strip-label">举报</text>
        </view>
        <view class="strip-item">
          <text class="strip-num">{{ stats.posts_today }}</text>
          <text class="strip-label">今日新帖</text>
        </view>
        <view class="strip-item">
          <text class="strip-num">{{ stats.frozen_users }}</text>
          <text class="strip-label">冻结用户</text>
        </view>
      </view>
    </view>

    <!-- tab 栏 -->
    <view class="tab-row">
      <scroll-view class="tab-scroll" scroll-x :show-scrollbar="false">
        <view
          v-for="t in TABS"
          :key="t.value"
          class="tab-item"
          :class="{ active: currentTab === t.value }"
          @tap="switchTab(t.value)"
        >
          {{ t.label }}
          <text v-if="t.value === 'pending' && stats.pending_posts > 0" class="tab-badge">{{ stats.pending_posts }}</text>
          <text v-if="t.value === 'reports' && stats.pending_reports > 0" class="tab-badge">{{ stats.pending_reports }}</text>
        </view>
      </scroll-view>
    </view>

    <view class="tab-content">
      <!-- 待审核 -->
      <view v-if="currentTab === 'pending'">
        <view v-if="pendingPosts.length === 0" class="empty"><text>没有待审帖子 🎉</text></view>
        <view v-for="p in pendingPosts" :key="p.id" class="card">
          <view class="card-head">
            <text class="card-author">{{ p.author.nickname }}</text>
            <text class="card-time">{{ timeAgo(p.created_at) }}</text>
          </view>
          <text class="card-content">{{ p.content }}</text>
          <view class="card-meta">
            <text>{{ p.category || '未分类' }} · {{ p.images_count }}图 · {{ p.view_count }}浏览</text>
          </view>
          <view class="card-actions">
            <view class="act-btn approve" @tap="onApprove(p.id)"><text>通过</text></view>
            <view class="act-btn reject" @tap="onReject(p.id)"><text>拒绝</text></view>
          </view>
        </view>
      </view>

      <!-- 举报 -->
      <view v-if="currentTab === 'reports'">
        <view v-if="reports.length === 0" class="empty"><text>暂无待处理举报</text></view>
        <view v-for="r in reports" :key="r.id" class="card">
          <view class="card-head">
            <text class="card-author">{{ r.reporter.nickname }} 举报</text>
            <text class="card-time">{{ timeAgo(r.created_at) }}</text>
          </view>
          <view class="report-reason"><text>理由：{{ r.reason }}</text></view>
          <view class="report-target" @tap="goPost(r.post_id)">
            <text class="card-content">{{ r.post_content }}</text>
          </view>
          <view class="card-actions">
            <view class="act-btn dismiss" @tap="onHandleReport(r.id, 'dismiss')"><text>驳回举报</text></view>
            <view class="act-btn reject" @tap="onHandleReport(r.id, 'ban_post')"><text>封禁帖子</text></view>
            <view class="act-btn danger" @tap="onHandleReport(r.id, 'ban_user')"><text>封号</text></view>
          </view>
        </view>
      </view>

      <!-- 帖子管理 -->
      <view v-if="currentTab === 'posts'">
        <view class="search-row">
          <input v-model="searchQ" class="search-input" placeholder="搜索帖子内容…" confirm-type="search" @confirm="loadAdminPosts(true)" />
          <view class="search-btn" @tap="loadAdminPosts(true)"><text>搜索</text></view>
        </view>
        <view v-if="adminPosts.length === 0" class="empty"><text>没有匹配的帖子</text></view>
        <view v-for="p in adminPosts" :key="p.id" class="card">
          <view class="card-head">
            <text class="card-author">{{ p.author.nickname }}</text>
            <view class="status-chip" :class="`s-${p.status}`">
              <text>{{ STATUS_TEXT[p.status] || p.status }}</text>
            </view>
          </view>
          <text class="card-content">{{ p.content }}</text>
          <view class="card-meta">
            <text>{{ timeAgo(p.created_at) }} · {{ p.like_count }}赞 {{ p.comment_count }}评 {{ p.view_count }}览</text>
          </view>
          <view class="card-actions">
            <view class="act-btn pin" :class="{ on: p.is_pinned }" @tap="onPin(p)">
              <text>{{ p.is_pinned ? '取消置顶' : '置顶' }}</text>
            </view>
            <view v-if="p.status === 1" class="act-btn reject" @tap="onBanPost(p.id)"><text>封禁</text></view>
            <view v-if="p.status === -1" class="act-btn approve" @tap="onRestorePost(p.id)"><text>恢复</text></view>
            <view v-if="p.status === 0" class="act-btn approve" @tap="onApprove(p.id)"><text>过审</text></view>
            <view class="act-btn plain" @tap="goPost(p.id)"><text>查看</text></view>
          </view>
        </view>
        <view v-if="adminHasMore" class="load-more" @tap="loadAdminPosts(false)"><text>加载更多</text></view>
      </view>

      <!-- Banner 投放 -->
      <view v-if="currentTab === 'banners'">
        <view class="card add-banner" @tap="openBannerForm()">
          <text class="add-icon">＋</text>
          <text>新建轮播广告</text>
        </view>
        <view v-if="banners.length === 0" class="empty"><text>暂无轮播广告</text></view>
        <view v-for="b in banners" :key="b.id" class="card banner-card">
          <image v-if="b.image_url" class="banner-thumb" :src="b.image_url" mode="aspectFill" />
          <view v-else class="banner-thumb banner-grad"><text>🎨</text></view>
          <view class="banner-info">
            <view class="banner-title-row">
              <text class="card-author">{{ b.title }}</text>
              <text v-if="b.tag" class="banner-tag">{{ b.tag }}</text>
            </view>
            <text class="card-meta">{{ b.desc || '无描述' }}</text>
            <text class="card-meta">跳转：{{ b.post_id ? `帖子#${b.post_id}` : (b.link_url || '未设置') }}</text>
          </view>
          <view class="banner-ops">
            <view class="act-btn" :class="b.status === 1 ? 'dismiss' : 'approve'" @tap="onToggleBanner(b)">
              <text>{{ b.status === 1 ? '下架' : '上架' }}</text>
            </view>
            <view class="act-btn plain" @tap="openBannerForm(b)"><text>编辑</text></view>
            <view class="act-btn danger" @tap="onDeleteBanner(b.id)"><text>删除</text></view>
          </view>
        </view>
      </view>

      <!-- 用户 -->
      <view v-if="currentTab === 'users'">
        <view v-if="users.length === 0" class="empty"><text>暂无用户</text></view>
        <view v-for="u in users" :key="u.id" class="card">
          <view class="card-head">
            <text class="card-author">{{ u.nickname }}</text>
            <text v-if="u.status === 0" class="frozen-chip">已冻结</text>
          </view>
          <view class="card-meta">
            <text>{{ u.role }} · {{ u.is_verified ? '已认证' : '未认证' }}{{ u.student_id ? ` · ${u.student_id}` : '' }}</text>
          </view>
          <view class="card-actions">
            <view v-if="u.status === 1" class="act-btn danger" @tap="onFreeze(u)"><text>冻结</text></view>
            <view v-else class="act-btn approve" @tap="onUnfreeze(u)"><text>解冻</text></view>
          </view>
        </view>
        <view v-if="usersHasMore" class="load-more" @tap="loadUsers(false)"><text>加载更多</text></view>
      </view>
    </view>

    <!-- Banner 编辑弹层 -->
    <view v-if="showBannerForm" class="form-mask" @tap="showBannerForm = false">
      <view class="form-sheet" @tap.stop>
        <text class="form-title">{{ editingBanner ? '编辑广告' : '新建广告' }}</text>
        <view class="form-field">
          <text class="form-label">标题 *</text>
          <input v-model="bannerForm.title" class="form-input" placeholder="如：毕业季活动" :maxlength="50" />
        </view>
        <view class="form-field">
          <text class="form-label">描述</text>
          <input v-model="bannerForm.desc" class="form-input" placeholder="副标题" :maxlength="100" />
        </view>
        <view class="form-field-row">
          <view class="form-field half">
            <text class="form-label">角标</text>
            <input v-model="bannerForm.tag" class="form-input" placeholder="活动/热门…" :maxlength="10" />
          </view>
          <view class="form-field half">
            <text class="form-label">排序权重</text>
            <input v-model="bannerForm.sort" class="form-input" type="number" placeholder="越大越靠前" />
          </view>
        </view>
        <view class="form-field">
          <text class="form-label">图片 URL（留空走渐变样式）</text>
          <input v-model="bannerForm.image_url" class="form-input" placeholder="https://…" />
        </view>
        <view class="form-field">
          <text class="form-label">跳转帖子 ID（与外链二选一）</text>
          <input v-model="bannerForm.post_id" class="form-input" type="number" placeholder="如 42" />
        </view>
        <view class="form-field">
          <text class="form-label">外链 URL</text>
          <input v-model="bannerForm.link_url" class="form-input" placeholder="https://…" />
        </view>
        <view class="form-field-row">
          <view class="form-field half">
            <text class="form-label">开始时间（可空）</text>
            <input v-model="bannerForm.start_at" class="form-input" placeholder="2026-09-01T00:00:00Z" />
          </view>
          <view class="form-field half">
            <text class="form-label">结束时间（可空）</text>
            <input v-model="bannerForm.end_at" class="form-input" placeholder="2026-09-30T00:00:00Z" />
          </view>
        </view>
        <view class="form-actions">
          <view class="act-btn plain" @tap="showBannerForm = false"><text>取消</text></view>
          <view class="act-btn approve" @tap="onSaveBanner"><text>保存</text></view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import {
  getReports, handleReport, getUsers, updateUserStatus,
  getAdminPosts, updateAdminPostStatus, pinPost, getAdminStats,
  type AdminReport, type AdminUser, type AdminPost, type AdminStats,
} from '@/api/admin'
import { listBanners, createBanner, updateBanner, deleteBanner, type AdminBanner, type BannerPayload } from '@/api/banner'
import { userStorage } from '@/utils/storage'

const TABS = [
  { label: '待审核', value: 'pending' },
  { label: '举报', value: 'reports' },
  { label: '帖子', value: 'posts' },
  { label: '轮播广告', value: 'banners' },
  { label: '用户', value: 'users' },
] as const

const STATUS_TEXT: Record<number, string> = { '-2': '已删除', '-1': '已封禁', 0: '待审核', 1: '正常', 2: '已归档' }

const currentTab = ref<string>('pending')
const stats = ref<AdminStats>({ pending_posts: 0, pending_reports: 0, total_posts: 0, total_users: 0, frozen_users: 0, posts_today: 0 })

const pendingPosts = ref<AdminPost[]>([])
const reports = ref<AdminReport[]>([])
const adminPosts = ref<AdminPost[]>([])
const adminCursor = ref<number | null>(null)
const adminHasMore = ref(false)
const searchQ = ref('')
const banners = ref<AdminBanner[]>([])
const users = ref<AdminUser[]>([])
const usersCursor = ref<string | null>(null)
const usersHasMore = ref(false)

const showBannerForm = ref(false)
const editingBanner = ref<AdminBanner | null>(null)
const bannerForm = ref<{ title: string; desc: string; tag: string; sort: string; image_url: string; post_id: string; link_url: string; start_at: string; end_at: string }>({
  title: '', desc: '', tag: '', sort: '0', image_url: '', post_id: '', link_url: '', start_at: '', end_at: '',
})

const timeAgo = (t: string) => {
  const ts = new Date(t).getTime()
  if (!ts) return ''
  const diff = Date.now() - ts
  const m = Math.floor(diff / 60000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m}分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}小时前`
  return `${Math.floor(h / 24)}天前`
}

const loadStats = async () => {
  try { stats.value = await getAdminStats() } catch { /* 忽略 */ }
}

const loadPending = async () => {
  try {
    const res = await getAdminPosts(0)
    pendingPosts.value = res.items
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  }
}

const loadReports = async () => {
  try {
    const res = await getReports('pending')
    reports.value = res.items
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  }
}

const loadAdminPosts = async (refresh: boolean) => {
  try {
    const cursor = refresh ? undefined : adminCursor.value ?? undefined
    const res = await getAdminPosts(undefined, searchQ.value.trim() || undefined, cursor)
    adminPosts.value = refresh ? res.items : [...adminPosts.value, ...res.items]
    adminCursor.value = res.next_cursor
    adminHasMore.value = res.has_more
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  }
}

const loadBanners = async () => {
  try {
    const res = await listBanners()
    banners.value = res.items
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  }
}

const loadUsers = async (refresh: boolean) => {
  try {
    const cursor = refresh ? undefined : usersCursor.value ?? undefined
    const res = await getUsers(cursor)
    users.value = refresh ? res.items : [...users.value, ...res.items]
    usersCursor.value = res.next_cursor
    usersHasMore.value = res.has_more
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  }
}

const refreshCurrent = () => {
  loadStats()
  if (currentTab.value === 'pending') loadPending()
  else if (currentTab.value === 'reports') loadReports()
  else if (currentTab.value === 'posts') loadAdminPosts(true)
  else if (currentTab.value === 'banners') loadBanners()
  else if (currentTab.value === 'users') loadUsers(true)
}

const switchTab = (t: string) => {
  currentTab.value = t
  refreshCurrent()
}

const goPost = (id: number) => uni.navigateTo({ url: `/pages/post-detail/index?id=${id}` })

// ---- 帖子动作 ----
const onApprove = async (id: number) => {
  try {
    await updateAdminPostStatus(id, 1)
    uni.showToast({ title: '已通过', icon: 'success' })
    refreshCurrent()
  } catch (e) { uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' }) }
}
const onReject = async (id: number) => {
  try {
    await updateAdminPostStatus(id, -1)
    uni.showToast({ title: '已拒绝', icon: 'none' })
    refreshCurrent()
  } catch (e) { uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' }) }
}
const onBanPost = async (id: number) => {
  try {
    await updateAdminPostStatus(id, -1)
    uni.showToast({ title: '已封禁', icon: 'none' })
    refreshCurrent()
  } catch (e) { uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' }) }
}
const onRestorePost = async (id: number) => {
  try {
    await updateAdminPostStatus(id, 1)
    uni.showToast({ title: '已恢复', icon: 'success' })
    refreshCurrent()
  } catch (e) { uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' }) }
}
const onPin = async (p: AdminPost) => {
  try {
    await pinPost(p.id, !p.is_pinned)
    uni.showToast({ title: p.is_pinned ? '已取消置顶' : '已置顶', icon: 'success' })
    refreshCurrent()
  } catch (e) { uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' }) }
}

// ---- 举报动作 ----
const onHandleReport = (id: number, action: 'dismiss' | 'ban_post' | 'ban_user') => {
  const label = { dismiss: '驳回举报', ban_post: '封禁帖子', ban_user: '封禁帖子并冻结作者' }[action]
  uni.showModal({
    title: '确认操作',
    content: `确定要${label}吗？`,
    success: async (r) => {
      if (!r.confirm) return
      try {
        await handleReport(id, action)
        uni.showToast({ title: '处理成功', icon: 'success' })
        refreshCurrent()
      } catch (e) { uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' }) }
    },
  })
}

// ---- Banner ----
const openBannerForm = (b?: AdminBanner) => {
  editingBanner.value = b || null
  bannerForm.value = {
    title: b?.title || '',
    desc: b?.desc || '',
    tag: b?.tag || '',
    sort: String(b?.sort ?? 0),
    image_url: b?.image_url || '',
    post_id: b?.post_id ? String(b.post_id) : '',
    link_url: b?.link_url || '',
    start_at: b?.start_at || '',
    end_at: b?.end_at || '',
  }
  showBannerForm.value = true
}

const onSaveBanner = async () => {
  const f = bannerForm.value
  if (!f.title.trim()) {
    uni.showToast({ title: '标题必填', icon: 'none' })
    return
  }
  const data: BannerPayload = {
    title: f.title.trim(),
    desc: f.desc.trim() || undefined,
    tag: f.tag.trim() || undefined,
    image_url: f.image_url.trim() || undefined,
    post_id: f.post_id ? Number(f.post_id) : undefined,
    link_url: f.link_url.trim() || undefined,
    sort: Number(f.sort) || 0,
    start_at: f.start_at.trim() || null,
    end_at: f.end_at.trim() || null,
  }
  if (data.post_id && data.link_url) {
    uni.showToast({ title: '帖子 ID 与外链只能二选一', icon: 'none' })
    return
  }
  try {
    if (editingBanner.value) await updateBanner(editingBanner.value.id, data)
    else await createBanner(data)
    uni.showToast({ title: '保存成功', icon: 'success' })
    showBannerForm.value = false
    loadBanners()
  } catch (e) { uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' }) }
}

const onToggleBanner = async (b: AdminBanner) => {
  try {
    await updateBanner(b.id, { status: b.status === 1 ? 0 : 1 })
    loadBanners()
  } catch (e) { uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' }) }
}

const onDeleteBanner = (id: number) => {
  uni.showModal({
    title: '删除广告',
    content: '确定删除这条轮播广告吗？',
    success: async (r) => {
      if (!r.confirm) return
      try {
        await deleteBanner(id)
        uni.showToast({ title: '已删除', icon: 'success' })
        loadBanners()
      } catch (e) { uni.showToast({ title: (e as Error).message || '删除失败', icon: 'none' }) }
    },
  })
}

// ---- 用户 ----
const onFreeze = (u: AdminUser) => {
  uni.showModal({
    title: '冻结用户',
    content: `确定冻结 ${u.nickname} 吗？冻结后无法登录。`,
    success: async (r) => {
      if (!r.confirm) return
      try {
        await updateUserStatus(u.id, 0)
        uni.showToast({ title: '已冻结', icon: 'success' })
        refreshCurrent()
      } catch (e) { uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' }) }
    },
  })
}
const onUnfreeze = async (u: AdminUser) => {
  try {
    await updateUserStatus(u.id, 1)
    uni.showToast({ title: '已解冻', icon: 'success' })
    refreshCurrent()
  } catch (e) { uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' }) }
}

onMounted(() => {
  const userInfo = userStorage.getUserInfo()
  if (!userInfo || userInfo.role !== 'admin') {
    uni.showToast({ title: '无权访问', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 1000)
    return
  }
  refreshCurrent()
})

onShow(() => {
  if (userStorage.getUserInfo()?.role === 'admin') refreshCurrent()
})
</script>

<style scoped>
.page-admin { min-height: 100vh; background: var(--bg-page); padding-bottom: 60rpx; }

.admin-header { background: var(--brand-red); padding: 30rpx 32rpx 26rpx; }
.header-title { color: #fff; font-size: 36rpx; font-weight: bold; }
.stats-strip { display: flex; margin-top: 24rpx; }
.strip-item { flex: 1; display: flex; flex-direction: column; align-items: center; }
.strip-num { color: #fff; font-size: 40rpx; font-weight: bold; }
.strip-label { color: rgba(255,255,255,0.75); font-size: 22rpx; margin-top: 4rpx; }

.tab-row { background: #fff; position: sticky; top: 0; z-index: 10; }
.tab-scroll { white-space: nowrap; padding: 0 12rpx; }
.tab-item { display: inline-flex; align-items: center; padding: 24rpx 26rpx; font-size: 28rpx; color: #666; position: relative; }
.tab-item.active { color: var(--brand-red); font-weight: bold; }
.tab-item.active::after { content: ''; position: absolute; left: 50%; transform: translateX(-50%); bottom: 8rpx; width: 40rpx; height: 6rpx; border-radius: 3rpx; background: var(--brand-red); }
.tab-badge { margin-left: 8rpx; background: var(--brand-red); color: #fff; font-size: 18rpx; padding: 2rpx 10rpx; border-radius: 16rpx; }

.tab-content { padding: 24rpx; }
.card { background: #fff; border-radius: var(--radius-card); padding: 24rpx; margin-bottom: 20rpx; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12rpx; }
.card-author { font-size: 28rpx; font-weight: bold; color: #333; }
.card-time { font-size: 22rpx; color: #999; }
.card-content { font-size: 28rpx; color: #333; line-height: 1.5; display: block; }
.card-meta { font-size: 22rpx; color: #999; margin-top: 10rpx; }
.card-actions { display: flex; gap: 14rpx; margin-top: 18rpx; }

.act-btn { flex: 1; height: 60rpx; display: flex; align-items: center; justify-content: center; border-radius: 30rpx; font-size: 24rpx; }
.act-btn.approve { background: #e8f8ee; color: #2ba245; }
.act-btn.reject { background: #fdeeee; color: #e34d59; }
.act-btn.danger { background: #e34d59; color: #fff; }
.act-btn.dismiss { background: #f0f1f2; color: #666; }
.act-btn.plain { background: #f7f8fa; color: #666; border: 1rpx solid #e8e9eb; }
.act-btn.pin { background: #fff5e6; color: #d48806; }
.act-btn.pin.on { background: #d48806; color: #fff; }

.status-chip { font-size: 20rpx; padding: 4rpx 14rpx; border-radius: 16rpx; }
.status-chip.s-0 { background: #fff5e6; color: #d48806; }
.status-chip.s-1 { background: #e8f8ee; color: #2ba245; }
.status-chip.s--1 { background: #fdeeee; color: #e34d59; }
.status-chip.s--2 { background: #f0f1f2; color: #999; }
.frozen-chip { font-size: 20rpx; background: #fdeeee; color: #e34d59; padding: 4rpx 14rpx; border-radius: 16rpx; }

.report-reason { font-size: 24rpx; color: #e34d59; margin-bottom: 10rpx; }
.report-target { background: var(--bg-page); border-radius: 12rpx; padding: 16rpx; }

.search-row { display: flex; gap: 14rpx; margin-bottom: 20rpx; }
.search-input { flex: 1; height: 68rpx; background: #fff; border-radius: 34rpx; padding: 0 28rpx; font-size: 26rpx; }
.search-btn { background: var(--brand-red); color: #fff; border-radius: 34rpx; padding: 0 32rpx; height: 68rpx; display: flex; align-items: center; font-size: 26rpx; }

.add-banner { display: flex; align-items: center; justify-content: center; gap: 10rpx; color: var(--brand-red); font-size: 28rpx; }
.add-icon { font-size: 36rpx; }
.banner-card { display: flex; flex-wrap: wrap; gap: 16rpx; align-items: center; }
.banner-thumb { width: 120rpx; height: 68rpx; border-radius: 10rpx; background: var(--bg-page); }
.banner-grad { display: flex; align-items: center; justify-content: center; font-size: 32rpx; }
.banner-info { flex: 1; min-width: 240rpx; }
.banner-title-row { display: flex; align-items: center; gap: 10rpx; }
.banner-tag { font-size: 18rpx; color: var(--brand-red); border: 1rpx solid var(--brand-red); padding: 2rpx 10rpx; border-radius: 8rpx; }
.banner-ops { display: flex; gap: 10rpx; width: 100%; }
.banner-ops .act-btn { flex: 1; }

.empty { text-align: center; padding: 100rpx 0; color: #999; font-size: 26rpx; }
.load-more { text-align: center; padding: 24rpx; color: var(--brand-red); font-size: 26rpx; }

.form-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 100; display: flex; align-items: flex-end; }
.form-sheet { width: 100%; max-height: 85vh; overflow-y: auto; background: #fff; border-radius: 32rpx 32rpx 0 0; padding: 32rpx 32rpx calc(32rpx + env(safe-area-inset-bottom)); }
.form-title { font-size: 32rpx; font-weight: bold; color: #333; display: block; margin-bottom: 24rpx; }
.form-field { margin-bottom: 20rpx; }
.form-field-row { display: flex; gap: 20rpx; }
.form-field.half { flex: 1; }
.form-label { font-size: 24rpx; color: #666; display: block; margin-bottom: 8rpx; }
.form-input { height: 68rpx; background: var(--bg-page); border-radius: 12rpx; padding: 0 20rpx; font-size: 26rpx; width: 100%; box-sizing: border-box; }
.form-actions { display: flex; gap: 20rpx; margin-top: 28rpx; }
</style>
