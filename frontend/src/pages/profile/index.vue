<template>
  <view class="page-profile" :class="themeClass">
    <view v-if="loading" class="state"><text>加载中…</text></view>

    <view v-else-if="!profile" class="state"><text>用户不存在</text></view>

    <view v-else>
      <!-- 1. 粉色横幅（同"我的"：有照片用照片，否则渐变兜底；沉浸式） -->
      <view class="banner">
        <image v-if="profile.banner_url" class="banner-img" :src="profile.banner_url" mode="aspectFill" />
        <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />
        <view class="back-btn" @tap="goBack"><text>‹</text></view>
      </view>

      <!-- 2. 白色圆角面板（头像悬浮 4/7，同"我的"） -->
      <view class="sheet">
        <view class="avatar-row">
          <view class="avatar-ring">
            <image v-if="profile.avatar_url" class="avatar avatar-img" :src="profile.avatar_url" mode="aspectFill" />
            <view v-else class="avatar" :style="{ background: avatarColor }">
              <text class="avatar-letter">{{ avatarLetter }}</text>
            </view>
            <view v-if="profile.is_verified" class="v-badge">
              <image class="v-badge-icon" src="/static/icons/common/check-inverse.svg" mode="aspectFit" />
            </view>
          </view>
        </view>

        <!-- 昵称 + 关注按钮 -->
        <view class="name-row">
          <text class="nickname">{{ profile.nickname }}</text>
          <text v-if="profile.is_verified" class="v-text">已认证</text>
          <view
            v-if="!profile.is_self && loggedIn"
            class="follow-btn"
            :class="{ on: profile.is_following }"
            @tap="onFollow"
          >
            <text>{{ profile.is_following ? '已关注' : '+ 关注' }}</text>
          </view>
        </view>

        <!-- 简介 + 认证学校 -->
        <view class="bio">
          <text>{{ profile.bio || '这位同学还没有简介～' }}</text>
          <text v-if="profile.school" class="school-line">{{ profile.school }}</text>
        </view>

        <!-- 统计：帖子 / 关注 / 粉丝（可点） -->
        <view class="stats-row">
          <view class="stat" @tap="goSection('posts')">
            <text class="num">{{ profile.posts_count }}</text>
            <text class="label">帖子</text>
          </view>
          <view class="stat" @tap="goSection('following')">
            <text class="num">{{ profile.following_count }}</text>
            <text class="label">关注</text>
          </view>
          <view class="stat" @tap="goSection('followers')">
            <text class="num">{{ profile.followers_count }}</text>
            <text class="label">粉丝</text>
          </view>
        </view>

        <!-- 关注/粉丝列表 -->
        <view v-if="section !== 'posts'" class="follow-list">
          <view class="fl-head">
            <text class="fl-title">{{ section === 'following' ? '关注的人' : '粉丝' }}（{{ list.length }}）</text>
            <view class="back-posts" @tap="section = 'posts'">
              <text>看帖子</text>
              <image class="chev" src="/static/icons/common/arrow-right-primary.svg" mode="aspectFit" />
            </view>
          </view>
          <view v-if="list.length === 0" class="empty"><text>暂无{{ section === 'following' ? '关注' : '粉丝' }}</text></view>
          <view v-for="u in list" :key="u.id" class="user-row" @tap="goProfile(u.id)">
            <image v-if="u.avatar_url" class="u-avatar u-avatar-img" :src="u.avatar_url" mode="aspectFill" />
            <view v-else class="u-avatar" :style="{ background: colorOf(u.nickname) }">
              <text>{{ (u.nickname || '?').slice(0, 1) }}</text>
            </view>
            <view class="u-meta">
              <text class="u-name">{{ u.nickname }}</text>
              <text v-if="u.is_verified" class="u-v">已认证</text>
            </view>
            <view
              v-if="!u.is_following && !isSelfId(u.id)"
              class="mini-follow"
              @tap.stop="onQuickFollow(u)"
            >
              <text>关注</text>
            </view>
          </view>
        </view>

        <!-- 内容区 -->
        <view v-else class="content-panel">
          <!-- 自己的主页：四栏 Tab（帖/评/藏/赞，同"我的"下划线式） -->
          <view v-if="isSelf" class="content-tabs">
            <view
              v-for="t in CONTENT_TABS"
              :key="t.key"
              class="ct-item"
              :class="{ on: contentTab === t.key }"
              @tap="switchContentTab(t.key)"
            >
              <image class="ct-icon-img" :src="t.icon" mode="aspectFit" />
              <view v-if="contentTab === t.key" class="ct-underline" />
            </view>
          </view>
          <text v-else class="content-title">TA 的内容</text>

          <!-- 帖子 -->
          <template v-if="contentTab === 'posts'">
            <view v-if="posts.length === 0" class="empty"><text>{{ isSelf ? '还没有发过帖子' : '暂无帖子' }}</text></view>
            <view
              v-for="p in posts"
              :key="p.id"
              class="post-card"
              @tap="goDetail(p.id)"
            >
              <view class="pc-main">
                <text class="pc-title">{{ titleOf(p) }}</text>
                <text class="pc-excerpt">{{ excerptOf(p) }}</text>
                <view class="pc-meta">
                  <text class="pc-date">{{ dateOf(p.created_at) }}</text>
                  <view class="pc-stat">
                    <image class="pc-stat-svg" src="/static/icons/common/eye.svg" mode="aspectFit" />
                    <text>{{ fmtCount(p.view_count) }}</text>
                  </view>
                  <view class="pc-stat">
                    <image class="pc-stat-svg" src="/static/icons/common/comment.svg" mode="aspectFit" />
                    <text>{{ fmtCount(p.comment_count) }}</text>
                  </view>
                </view>
              </view>
              <image
                v-if="p.images && p.images.length"
                class="pc-thumb"
                :src="p.images[0]"
                mode="aspectFill"
              />
              <view v-else class="pc-thumb pc-thumb-ph">
                <image class="pc-thumb-ph-svg" src="/static/icons/settings/doc.svg" mode="aspectFit" />
              </view>
            </view>
          </template>

          <!-- 评论过的 -->
          <template v-else-if="contentTab === 'comments'">
            <view v-if="myCommentList.length === 0" class="empty"><text>还没有发表过评论</text></view>
            <view
              v-for="c in myCommentList"
              :key="c.id"
              class="post-card"
              @tap="goDetail(c.post_id)"
            >
              <view class="pc-main">
                <text class="pc-title">{{ c.content }}</text>
                <text class="pc-excerpt">在「{{ c.post_author }}」的帖子下：{{ c.post_excerpt }}</text>
                <view class="pc-meta">
                  <text class="pc-date">{{ dateOf(c.created_at) }}</text>
                </view>
              </view>
            </view>
          </template>

          <!-- 收藏 / 点赞：帖子流 -->
          <template v-else>
            <view v-if="interactionPosts.length === 0" class="empty">
              <text>{{ contentTab === 'favorites' ? '还没有收藏帖子' : '还没有点赞帖子' }}</text>
            </view>
            <view
              v-for="p in interactionPosts"
              :key="p.id"
              class="post-card"
              @tap="goDetail(p.id)"
            >
              <view class="pc-main">
                <text class="pc-title">{{ titleOf(p) }}</text>
                <text class="pc-excerpt">{{ excerptOf(p) }}</text>
                <view class="pc-meta">
                  <text class="pc-date">{{ dateOf(p.created_at) }}</text>
                  <view class="pc-stat">
                    <image class="pc-stat-svg" src="/static/icons/common/eye.svg" mode="aspectFit" />
                    <text>{{ fmtCount(p.view_count) }}</text>
                  </view>
                  <view class="pc-stat">
                    <image class="pc-stat-svg" src="/static/icons/common/comment.svg" mode="aspectFit" />
                    <text>{{ fmtCount(p.comment_count) }}</text>
                  </view>
                </view>
              </view>
              <image
                v-if="p.images && p.images.length"
                class="pc-thumb"
                :src="p.images[0]"
                mode="aspectFill"
              />
              <view v-else class="pc-thumb pc-thumb-ph">
                <image class="pc-thumb-ph-svg" src="/static/icons/settings/doc.svg" mode="aspectFit" />
              </view>
            </view>
          </template>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { avatarColor as colorOf } from '@/utils/avatar'
import { useTheme } from '@/utils/theme'
import type { PostBrief } from '@/types/api'
import {
  getProfile, getFollowing, getFollowers, getUserPosts, followUser, unfollowUser,
  type UserProfile, type UserBrief,
} from '@/api/profile'
import { myComments, myLikes, myFavorites, type MyCommentItem } from '@/api/interaction'
import { tokenStorage, userStorage } from '@/utils/storage'

const { themeClass } = useTheme()

// 沉浸式横幅：预留状态栏（H5 下为 0）
const statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0

const profile = ref<UserProfile | null>(null)
const posts = ref<PostBrief[]>([])
const list = ref<UserBrief[]>([])
const section = ref<'posts' | 'following' | 'followers'>('posts')

// ===== 自己主页的内容四栏（与"我的"页同款）=====
// 说明：产品上"转发"功能后端暂未实现，此位暂以「收藏」承担
const CONTENT_TABS = [
  { key: 'posts', icon: '/static/icons/common/note.svg' },
  { key: 'comments', icon: '/static/icons/common/comment.svg' },
  { key: 'favorites', icon: '/static/icons/common/bookmark.svg' },
  { key: 'likes', icon: '/static/icons/common/heart.svg' },
] as const
type ContentTab = (typeof CONTENT_TABS)[number]['key']
const contentTab = ref<ContentTab>('posts')
const myCommentList = ref<MyCommentItem[]>([])
const interactionPosts = ref<PostBrief[]>([])
const loadedTabs = ref(new Set<string>(['posts']))
const loading = ref(true)
const loggedIn = tokenStorage.isLoggedIn()


const avatarLetter = computed(() => (profile.value?.nickname || '?').slice(0, 1))
const avatarColor = computed(() => colorOf(profile.value?.nickname || ''))

const isSelfId = (id: string) => userStorage.getUserInfo()?.id === id
const isSelf = computed(() => !!profile.value && isSelfId(profile.value.id))

// ---- 内容卡格式化（与"我的"页一致） ----
const titleOf = (p: PostBrief) => {
  const first = (p.content || '').split('\n').find((s) => s.trim()) || '（无标题）'
  return first.length > 22 ? first.slice(0, 22) : first
}
const excerptOf = (p: PostBrief) => {
  const lines = (p.content || '').split('\n').filter((s) => s.trim())
  const rest = lines.length > 1 ? lines.slice(1).join(' ') : lines[0] || ''
  const t = rest.length > 40 ? rest.slice(0, 40) + '…' : rest
  return t
}
const pad = (n: number) => String(n).padStart(2, '0')
const dateOf = (iso?: string) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
const fmtCount = (n?: number) => {
  const v = n || 0
  if (v < 10000) return String(v)
  const w = v / 10000
  return `${w >= 100 ? Math.round(w) : w.toFixed(1).replace(/\.0$/, '')}万`
}

const load = async (id: string) => {
  try {
    profile.value = await getProfile(id)
    const res = await getUserPosts(id)
    posts.value = res.items
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

const goSection = async (s: 'posts' | 'following' | 'followers') => {
  if (s === 'posts') { section.value = 'posts'; return }
  section.value = s
  if (!profile.value) return
  try {
    const res = s === 'following' ? await getFollowing(profile.value.id) : await getFollowers(profile.value.id)
    list.value = res.items
  } catch { /* 忽略 */ }
}

const onFollow = async () => {
  if (!profile.value) return
  const prev = profile.value.is_following
  profile.value.is_following = !prev
  try {
    await (prev ? unfollowUser(profile.value.id) : followUser(profile.value.id))
    // 计数同步
    profile.value.followers_count += prev ? -1 : 1
  } catch (e) {
    profile.value.is_following = prev
    uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' })
  }
}

const onQuickFollow = async (u: UserBrief) => {
  try {
    await followUser(u.id)
    u.is_following = true
    uni.showToast({ title: '已关注', icon: 'none' })
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '操作失败', icon: 'none' })
  }
}

const switchContentTab = async (t: ContentTab) => {
  contentTab.value = t
  if (loadedTabs.value.has(t)) return
  loadedTabs.value.add(t)
  try {
    if (t === 'comments') {
      myCommentList.value = (await myComments()).items
    } else if (t === 'favorites') {
      interactionPosts.value = (await myFavorites<PostBrief>()).items as PostBrief[]
    } else if (t === 'likes') {
      interactionPosts.value = (await myLikes<PostBrief>()).items as PostBrief[]
    }
  } catch (e) {
    loadedTabs.value.delete(t)
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  }
}

const goBack = () => uni.navigateBack()
const goDetail = (id: number) => uni.navigateTo({ url: `/pages/post-detail/index?id=${id}` })
const goProfile = (id: string) => {
  if (isSelfId(id)) return
  uni.navigateTo({ url: `/pages/profile/index?id=${id}` })
}

;(() => {
  const pages = getCurrentPages()
  const cur = pages[pages.length - 1] as any
  const id = cur?.options?.id
  const sec = cur?.options?.section
  if (!id) {
    uni.showToast({ title: '用户不存在', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 800)
    loading.value = false
    return
  }
  if (sec === 'following' || sec === 'followers') {
    section.value = sec
  }
  load(String(id)).then(() => goSection(section.value))
})()
</script>

<style scoped>
.page-profile { min-height: 100vh; background: var(--bg-page); }
.state { text-align: center; padding: 160rpx 0; color: var(--text-3); }

/* 1. 横幅（同"我的"：无照片时粉色渐变兜底） */
.banner {
  height: 460rpx;
  background: var(--hero-gradient);
  position: relative;
  overflow: hidden;
}
.banner::after {
  content: '';
  position: absolute;
  right: -80rpx;
  top: -60rpx;
  width: 400rpx;
  height: 400rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
}
.banner-img { width: 100%; height: 100%; }
.back-btn {
  position: absolute;
  left: 24rpx;
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.25);
  color: var(--text-inverse);
  font-size: 44rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

/* 2. 白色圆角面板（头像悬浮几何与"我的"一致） */
.sheet {
  background: var(--bg-card);
  border-radius: 40rpx 40rpx 0 0;
  padding: 0 40rpx 40rpx;
  position: relative;
  min-height: 60vh;
}
.avatar-row {
  transform: translateY(-108rpx);
  margin-bottom: -80rpx;
}
.avatar-ring {
  display: inline-flex;
  position: relative;
  padding: 8rpx;
  background: var(--bg-card);
  border-radius: 50%;
  box-shadow: var(--shadow-float);
}
.avatar {
  width: 176rpx;
  height: 176rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.avatar-img { width: 176rpx; height: 176rpx; }
.avatar-letter { font-size: 80rpx; font-weight: bold; color: var(--on-avatar); }
/* 认证徽章：圆形对勾（原先塞「已认证」三字在 48rpx 圆里，被压成逐字竖排） */
.v-badge {
  position: absolute;
  right: 4rpx;
  bottom: 4rpx;
  width: 44rpx;
  height: 44rpx;
  border-radius: 50%;
  background: var(--primary-badge);
  border: 3rpx solid var(--bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28rpx;
  z-index: 2;
}

/* 昵称行 + 关注按钮 */
.name-row { display: flex; align-items: center; margin-top: 24rpx; }
.v-badge-icon { width: 26rpx; height: 26rpx; }
.nickname { font-size: 40rpx; font-weight: bold; color: var(--text-1); }
.v-text {
  margin-left: 14rpx;
  font-size: 22rpx;
  color: var(--primary-text);
  background: var(--primary-soft);
  border-radius: 6rpx;
  padding: 2rpx 10rpx;
  white-space: nowrap;
}
.follow-btn {
  margin-left: auto;
  background: var(--primary-badge);
  color: var(--text-inverse);
  font-size: 26rpx;
  font-weight: 600;
  padding: 14rpx 34rpx;
  border-radius: 36rpx;
}
.follow-btn.on { background: var(--primary-soft); color: var(--primary-text); }

.bio { margin-top: 18rpx; display: flex; flex-direction: column; gap: 8rpx; }
.bio text { font-size: 24rpx; color: var(--text-3); line-height: 1.6; }
.school-line { color: var(--primary-text); }

/* 统计行 */
.stats-row {
  display: flex;
  margin-top: 30rpx;
  background: var(--bg-card-2);
  border-radius: 20rpx;
  padding: 24rpx 0;
}
.stat { flex: 1; display: flex; flex-direction: column; align-items: center; }
.num { font-size: 34rpx; font-weight: bold; color: var(--text-1); }
.label { font-size: 22rpx; color: var(--text-3); margin-top: 6rpx; }

/* 关注/粉丝列表 */
.follow-list { margin-top: 30rpx; }
.fl-head { display: flex; align-items: center; justify-content: space-between; padding: 8rpx 8rpx 20rpx; }
.fl-title { font-size: 30rpx; font-weight: bold; color: var(--text-1); }
.back-posts { font-size: 24rpx; color: var(--primary-text); display: inline-flex; align-items: center; }
.chev { width: 20rpx; height: 20rpx; margin-left: 2rpx; flex-shrink: 0; }
.user-row { display: flex; align-items: center; padding: 20rpx 8rpx; border-bottom: 1rpx solid var(--border-light); }
.user-row:last-child { border-bottom: none; }
.u-avatar { width: 88rpx; height: 88rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: var(--on-avatar); font-size: 40rpx; font-weight: bold; margin-right: 20rpx; flex-shrink: 0; }
.u-avatar-img { width: 88rpx; height: 88rpx; }
.u-meta { flex: 1; display: flex; align-items: center; gap: 12rpx; min-width: 0; }
.u-name { font-size: 28rpx; color: var(--text-1); }
.u-v { font-size: 22rpx; color: var(--text-3); }
.mini-follow { background: var(--primary-badge); color: var(--text-inverse); font-size: 22rpx; padding: 10rpx 26rpx; border-radius: 24rpx; }

/* 内容区（同"我的"） */
.content-tabs {
  display: flex;
  margin-top: 36rpx;
  border-bottom: 1rpx solid var(--border-light);
}
.ct-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10rpx;
  padding-bottom: 18rpx;
  position: relative;
}
.ct-icon { font-size: 40rpx; line-height: 1; opacity: 0.55; }
.ct-icon-img { width: 40rpx; height: 40rpx; opacity: 0.55; }
.ct-item.on .ct-icon, .ct-item.on .ct-icon-img { opacity: 1; }
.ct-underline {
  position: absolute;
  bottom: -2rpx;
  width: 80rpx;
  height: 6rpx;
  border-radius: 3rpx;
  background: var(--primary);
}

.content-panel { margin-top: 30rpx; }
.content-title { font-size: 30rpx; font-weight: bold; color: var(--text-1); }

.post-card {
  background: var(--bg-card-2);
  border-radius: 20rpx;
  padding: 26rpx;
  margin-top: 20rpx;
  display: flex;
  gap: 20rpx;
}
.pc-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.pc-title { font-size: 28rpx; font-weight: bold; color: var(--text-1); line-height: 1.5; }
.pc-excerpt {
  font-size: 24rpx;
  color: var(--text-3);
  margin-top: 10rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pc-meta { display: flex; align-items: center; gap: 28rpx; margin-top: 16rpx; }
.pc-date { font-size: 22rpx; color: var(--text-3); margin-right: auto; }
.pc-stat { display: flex; align-items: center; gap: 6rpx; font-size: 22rpx; color: var(--text-3); }
.pc-stat-icon { font-size: 24rpx; }
.pc-stat-svg { width: 24rpx; height: 24rpx; flex-shrink: 0; }
.pc-thumb {
  width: 160rpx;
  height: 160rpx;
  border-radius: var(--radius-inner);
  flex-shrink: 0;
}
.pc-thumb-ph {
  background: var(--soft-gradient);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48rpx;
  opacity: 0.7;
}
.pc-thumb-ph-svg { width: 48rpx; height: 48rpx; opacity: 0.5; }

.empty { text-align: center; color: var(--text-3); font-size: 24rpx; padding: 80rpx 0; }
</style>
