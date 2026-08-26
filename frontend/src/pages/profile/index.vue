<template>
  <view class="page-profile">
    <view v-if="loading" class="state"><text>加载中…</text></view>

    <view v-else-if="!profile" class="state"><text>用户不存在</text></view>

    <view v-else>
      <!-- 头部 -->
      <view class="profile-header">
        <view class="avatar-ring">
          <view class="avatar" :style="{ background: colorOf(profile.nickname) }">
            <text class="avatar-letter">{{ (profile.nickname || '?').slice(0, 1) }}</text>
          </view>
          <text v-if="profile.is_verified" class="v-badge">✅</text>
        </view>
        <view class="meta">
          <view class="name-row">
            <text class="nickname">{{ profile.nickname }}</text>
          </view>
          <view v-if="profile.school" class="school-capsule"><text>{{ profile.school }}</text></view>
        </view>
        <view
          v-if="!profile.is_self && loggedIn"
          class="follow-btn"
          :class="{ on: profile.is_following }"
          @tap="onFollow"
        >
          <text>{{ profile.is_following ? '已关注' : '+ 关注' }}</text>
        </view>
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
      <view v-if="section !== 'posts'" class="user-list-card">
        <view class="list-title">
          <text>{{ section === 'following' ? '关注的人' : '粉丝' }}（{{ list.length }}）</text>
          <text class="back-posts" @tap="section = 'posts'">看帖子 ›</text>
        </view>
        <view v-if="list.length === 0" class="empty"><text>暂无{{ section === 'following' ? '关注' : '粉丝' }}</text></view>
        <view v-for="u in list" :key="u.id" class="user-row" @tap="goProfile(u.id)">
          <view class="u-avatar" :style="{ background: colorOf(u.nickname) }">
            <text>{{ (u.nickname || '?').slice(0, 1) }}</text>
          </view>
          <view class="u-meta">
            <text class="u-name">{{ u.nickname }}</text>
            <text v-if="u.is_verified" class="u-v">✅ 已认证</text>
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

      <!-- 帖子列表 -->
      <view v-else class="posts-area">
        <view class="list-title"><text>TA 的帖子</text></view>
        <view v-if="posts.length === 0" class="empty"><text>暂无帖子</text></view>
        <view class="posts-inner">
          <FeedCard v-for="p in posts" :key="p.id" :post="p" @detail="goDetail" />
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import FeedCard from '@/components/feed-card.vue'
import type { PostBrief } from '@/types/api'
import {
  getProfile, getFollowing, getFollowers, getUserPosts, followUser, unfollowUser,
  type UserProfile, type UserBrief,
} from '@/api/profile'
import { tokenStorage, userStorage } from '@/utils/storage'

const profile = ref<UserProfile | null>(null)
const posts = ref<PostBrief[]>([])
const list = ref<UserBrief[]>([])
const section = ref<'posts' | 'following' | 'followers'>('posts')
const loading = ref(true)
const loggedIn = tokenStorage.isLoggedIn()

const COLORS = ['#ffd591', '#adc6ff', '#b7eb8f', '#ffa39e', '#d3adf7', '#87e8de', '#ffccc7']
const colorOf = (s: string) => {
  let h = 0
  for (let i = 0; i < (s || '').length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return COLORS[h % COLORS.length]
}

const isSelfId = (id: string) => userStorage.getUserInfo()?.id === id

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

.profile-header { background: var(--brand-red); padding: 36rpx 32rpx 60rpx; display: flex; align-items: center; }
.avatar-ring { position: relative; }
.avatar { width: 128rpx; height: 128rpx; border-radius: 50%; background: #fff; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 0 6rpx rgba(255,255,255,0.4); }
.avatar-letter { font-size: 60rpx; font-weight: bold; color: #fff; }
.v-badge { position: absolute; bottom: 0; right: -6rpx; font-size: 32rpx; }
.meta { flex: 1; margin-left: 24rpx; }
.name-row { display: flex; align-items: center; }
.nickname { color: #fff; font-size: 38rpx; font-weight: bold; }
.school-capsule { align-self: flex-start; background: rgba(255,255,255,0.22); padding: 6rpx 22rpx; border-radius: 24rpx; margin-top: 12rpx; }
.school-capsule text { color: #fff; font-size: 22rpx; }
.follow-btn { background: #fff; color: var(--brand-red); font-size: 26rpx; font-weight: 600; padding: 12rpx 28rpx; border-radius: 30rpx; }
.follow-btn.on { background: rgba(255,255,255,0.25); color: #fff; }

.stats-row { background: #fff; margin: -32rpx 24rpx 20rpx; border-radius: var(--radius-card); padding: 28rpx 0; display: flex; box-shadow: 0 4rpx 16rpx rgba(0,0,0,0.04); position: relative; }
.stat { flex: 1; display: flex; flex-direction: column; align-items: center; }
.num { font-size: 36rpx; font-weight: bold; color: var(--text-1); }
.label { font-size: 22rpx; color: var(--text-3); margin-top: 6rpx; }

.list-title { display: flex; align-items: center; justify-content: space-between; padding: 24rpx 32rpx 8rpx; font-size: 28rpx; font-weight: bold; color: var(--text-1); }
.back-posts { font-size: 24rpx; color: var(--brand-red); font-weight: normal; }

.user-list-card { background: #fff; margin: 0 24rpx 20rpx; border-radius: var(--radius-card); padding-bottom: 12rpx; }
.user-row { display: flex; align-items: center; padding: 20rpx 32rpx; border-bottom: 1rpx solid #f7f7f7; }
.u-avatar { width: 72rpx; height: 72rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 34rpx; font-weight: bold; margin-right: 20rpx; }
.u-meta { flex: 1; display: flex; align-items: center; gap: 12rpx; }
.u-name { font-size: 28rpx; color: var(--text-1); }
.u-v { font-size: 20rpx; color: var(--text-3); }
.mini-follow { background: var(--brand-red); color: #fff; font-size: 22rpx; padding: 8rpx 24rpx; border-radius: 24rpx; }

.posts-area { padding-bottom: 40rpx; }
.posts-inner { padding: 8rpx 24rpx; }
.empty { text-align: center; color: var(--text-3); font-size: 24rpx; padding: 48rpx 0; }
</style>
