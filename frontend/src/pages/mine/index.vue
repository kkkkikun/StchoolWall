<template>
  <view class="page-mine">
    <!-- 1. 粉色校园横幅（照片位：BANNER_IMG 配置，空则渐变兜底） -->
    <!-- 点击横幅直接更换（QQ式）；BANNER_IMG 为静态兜底图位 -->
    <view class="banner">
      <image v-if="bannerUrl || BANNER_IMG" class="banner-img" :src="bannerUrl || BANNER_IMG" mode="aspectFill" />
    </view>

    <!-- 2. 白色圆角面板（上浮盖住横幅底部） -->
    <view class="sheet">
      <view class="avatar-row">
        <view class="avatar-ring">
          <image v-if="avatarUrl" class="avatar avatar-img" :src="avatarUrl" mode="aspectFill" />
          <view v-else class="avatar" :style="{ background: avatarColor }">
            <text class="avatar-letter">{{ avatarLetter }}</text>
          </view>
        </view>
      </view>

      <!-- 昵称 + 编辑资料 + 设置齿轮 -->
      <view class="name-row">
        <text class="nickname">{{ user.nickname }}</text>
        <view class="name-actions">
          <view class="edit-btn" @tap="goEditProfile">
            <text>编辑资料</text>
          </view>
          <view class="gear-btn" @tap="goSettings">
            <text class="gear-icon">⚙️</text>
          </view>
        </view>
      </view>

      <!-- 简介：编辑资料页可改；未设置时用默认文案 -->
      <view class="bio">
        <text>{{ user.bio || '热爱生活，热爱分享～' }}</text>
        <text v-if="!user.bio">在校园里发现美好，记录点滴日常 ✨</text>
      </view>

      <!-- 未登录：网页版登录入口（H5 部署用，注册/登录合一） -->
      <!-- #ifdef H5 -->
      <view v-if="!loggedIn" class="dev-login-row">
        <view class="dev-capsule" @tap="showWebLogin = true">
          <text>🔑 登录 / 注册</text>
        </view>
      </view>
      <!-- #endif -->
      <!-- 未登录：本地联调演示入口（仅 VITE_DEV_LOGIN=true 的构建渲染，生产构建自动隐藏） -->
      <view v-if="!loggedIn && DEV_LOGIN_ON" class="dev-login-row">
        <view class="dev-capsule" @tap="doDevLogin(false)">
          <text>一键登录（演示学生）</text>
        </view>
        <view class="dev-capsule admin" @tap="doDevLogin(true)">
          <text>🛡️ 演示管理员</text>
        </view>
      </view>
      <!-- 未认证提示 / 管理员入口（功能性保留，弱化为细条） -->
      <view v-if="loggedIn && !isVerified" class="slim-tip" @tap="goVerify">
        <text>🎓 学籍认证（发帖/互动需认证） ›</text>
      </view>
      <view v-if="isAdmin" class="slim-tip admin" @tap="goAdmin">
        <text>🛡️ 管理后台 ›</text>
      </view>

      <!-- 3. 四栏内容 Tab（帖/评/藏/赞，下划线式与全 app 统一） -->
      <view class="content-tabs">
        <view
          v-for="(t, i) in CONTENT_TABS"
          :key="t.key"
          class="ct-item"
          :class="{ on: contentTab === t.key }"
          @tap="switchTab(t.key)"
        >
          <text class="ct-icon">{{ t.icon }}</text>
          <view v-if="contentTab === t.key" class="ct-underline" />
        </view>
      </view>

      <!-- 4. 内容区 -->
      <view class="content-panel">
        <text class="content-title">{{ activeTitle }}</text>

        <!-- 帖子 / 收藏 / 点赞：紧凑内容卡（标题+摘要+日期+浏览+评论+缩略图） -->
        <template v-if="contentTab !== 'comments'">
          <view v-if="!posts.length" class="empty">
            <text>{{ emptyText }}</text>
          </view>
          <view
            v-for="p in posts"
            :key="`${contentTab}-${p.id}`"
            class="post-card"
            @tap="goDetail(p.id)"
          >
            <view class="pc-main">
              <text class="pc-title">{{ titleOf(p) }}</text>
              <text class="pc-excerpt">{{ excerptOf(p) }}</text>
              <view class="pc-meta">
                <text class="pc-date">{{ dateOf(p.created_at) }}</text>
                <view class="pc-stat">
                  <text class="pc-stat-icon">👁</text>
                  <text>{{ fmtCount(p.view_count) }}</text>
                </view>
                <view class="pc-stat">
                  <text class="pc-stat-icon">💬</text>
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
              <text>🖼</text>
            </view>
          </view>
        </template>

        <!-- 评论过的 -->
        <template v-else>
          <view v-if="!myCommentList.length" class="empty"><text>还没有发表过评论</text></view>
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
      </view>
    </view>

    <TabBar :current="4" />

    <!-- 网页版登录弹窗（H5） -->
    <!-- #ifdef H5 -->
    <view v-if="showWebLogin" class="wl-mask" @tap="showWebLogin = false">
      <view class="wl-card" @tap.stop>
        <text class="wl-title">登录 / 注册</text>
        <text class="wl-sub">昵称即用户名，首次输入自动注册</text>
        <input v-model="wlForm.username" class="wl-input" :maxlength="20" placeholder="用户名（2-20 字）"
               placeholder-class="ph" />
        <input v-model="wlForm.password" class="wl-input" :maxlength="64" password placeholder="密码（至少 6 位）"
               placeholder-class="ph" />
        <view class="wl-btn" :class="{ saving: wlSaving }" @tap="doWebLogin">
          <text>{{ wlSaving ? '登录中…' : '进入鄂应墙' }}</text>
        </view>
        <view v-if="WECHAT_MP_APP_ID" class="wl-wechat" @tap="beginMpOAuth">
          <text>微信登录（公众号）</text>
        </view>
      </view>
    </view>
    <!-- #endif -->
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import TabBar from '@/components/tab-bar.vue'
import { myStats } from '@/api/interaction'
import { devLogin, webLogin } from '@/api/auth'
import { getProfile } from '@/api/profile'
import { get } from '@/utils/request'
import { tokenStorage, userStorage } from '@/utils/storage'
import type { PostBrief } from '@/types/api'

/**
 * 横幅照片更换位：把校园照片放到 src/static/（如 mine-banner.jpg）后填路径即可，
 * 空值走粉色渐变兜底。H5/小程序均支持 jpg/png。
 */
const BANNER_IMG = '' // 静态兜底图；用户上传后以 bannerUrl 优先

const avatarUrl = ref('')
const bannerUrl = ref('')

const CONTENT_TABS = [
  { key: 'posts', icon: '📄' },
  { key: 'comments', icon: '💬' },
  { key: 'favorites', icon: '🔖' },
  { key: 'likes', icon: '🤍' },
] as const
type ContentTab = (typeof CONTENT_TABS)[number]['key']

const contentTab = ref<ContentTab>('posts')
const user = ref({ nickname: '未登录', bio: '' })
const loggedIn = ref(tokenStorage.isLoggedIn())
const isVerified = ref(!!userStorage.getUserInfo()?.is_verified)
const isAdmin = computed(() => userStorage.getUserInfo()?.role === 'admin')

const posts = ref<PostBrief[]>([])
const myCommentList = ref<
  Array<{ id: number; post_id: number; content: string; post_excerpt: string; post_author: string; created_at: string }>
>([])
const loadedTabs = ref(new Set<string>())
const loading = ref(false)

const avatarLetter = computed(() => (user.value.nickname || '?').slice(0, 1))
const AVATAR_COLORS = ['#f8c8b8', '#e8d5f5', '#d5e8f5', '#d5f0d5', '#fbe3b5']
const avatarColor = computed(() => {
  const s = user.value.nickname || ''
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[h % AVATAR_COLORS.length]
})

const activeTitle = computed(
  () =>
    (({ posts: '我发出的内容', comments: '我评论过的', favorites: '我收藏的', likes: '我点赞的' }) as Record<ContentTab, string>)[
      contentTab.value
    ],
)
const emptyText = computed(
  () =>
    (({ posts: '还没有发过帖子', comments: '还没有发表过评论', favorites: '还没有收藏', likes: '还没有点赞' }) as Record<
      ContentTab,
      string
    >)[contentTab.value],
)

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

interface MyCommentItem {
  id: number
  post_id: number
  content: string
  post_excerpt: string
  post_author: string
  created_at: string
}

const fetchMyPosts = async () => {
  const res = await get<{ items: PostBrief[] }>('/posts/my')
  posts.value = res.items || []
}
const fetchFavorites = async () => {
  const res = await get<{ items: PostBrief[] }>('/me/favorites')
  posts.value = res.items || []
}
const fetchLikes = async () => {
  const res = await get<{ items: PostBrief[] }>('/me/likes')
  posts.value = res.items || []
}
const fetchComments = async () => {
  const res = await get<{ items: MyCommentItem[] }>('/me/comments')
  myCommentList.value = res.items || []
}

const LOADERS: Record<ContentTab, () => Promise<void>> = {
  posts: fetchMyPosts,
  comments: fetchComments,
  favorites: fetchFavorites,
  likes: fetchLikes,
}

const switchTab = async (t: ContentTab) => {
  contentTab.value = t
  if (!loggedIn.value || loadedTabs.value.has(t)) return
  loading.value = true
  try {
    await LOADERS[t]()
    loadedTabs.value.add(t)
  } catch (e) {
    loadedTabs.value.delete(t)
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

const loadProfile = async () => {
  loggedIn.value = tokenStorage.isLoggedIn()
  const info = userStorage.getUserInfo()
  if (info) {
    user.value = { nickname: info.nickname || '同学', bio: user.value.bio }
    isVerified.value = !!info.is_verified
  } else {
    user.value = { nickname: '未登录', bio: '' }
  }
  // 拉取头像/横幅（登录后）
  if (loggedIn.value) {
    try {
      const p = await get<{ avatar_url?: string; banner_url?: string; bio?: string; nickname?: string; is_verified?: boolean }>('/user/profile')
      avatarUrl.value = p.avatar_url || ''
      bannerUrl.value = p.banner_url || ''
      user.value = { nickname: p.nickname || user.value.nickname, bio: p.bio || '' }
      // 学籍认证状态以后端为准，避免认证完成后「我的」页仍显示未认证
      isVerified.value = !!p.is_verified
      const local = userStorage.getUserInfo()
      if (local) {
        userStorage.setUserInfo({ ...local, is_verified: !!p.is_verified })
      }
    } catch { /* 忽略 */ }
  } else {
    avatarUrl.value = ''
    bannerUrl.value = ''
  }
  if (loggedIn.value && !loadedTabs.value.has('posts')) {
    try {
      await fetchMyPosts()
      loadedTabs.value.add('posts')
    } catch { /* 忽略 */ }
  }
}

const doDevLogin = async (asAdmin: boolean) => {
  try {
    const res = await devLogin(asAdmin)
    tokenStorage.setToken(res.access_token)
    userStorage.setUserInfo({
      id: res.user_info.id,
      nickname: res.user_info.nickname,
      role: res.role,
      is_verified: res.user_info.is_verified,
    })
    loggedIn.value = true
    isVerified.value = !!res.user_info.is_verified
    uni.showToast({ title: asAdmin ? '已登录（管理员）' : '已登录（演示）', icon: 'success' })
    loadedTabs.value.clear()
    await loadProfile()
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '登录失败', icon: 'none' })
  }
}

// ===== 网页版登录（H5）：注册/登录合一，与 devLogin 共用落地流程 =====
const DEV_LOGIN_ON = import.meta.env.VITE_DEV_LOGIN === 'true'
const WECHAT_MP_APP_ID = import.meta.env.VITE_WECHAT_MP_APP_ID || ''
const showWebLogin = ref(false)
const wlSaving = ref(false)
const wlForm = ref({ username: '', password: '' })

const doWebLogin = async () => {
  const username = wlForm.value.username.trim()
  const password = wlForm.value.password
  if (username.length < 2 || password.length < 6) {
    uni.showToast({ title: '用户名≥2字，密码≥6位', icon: 'none' })
    return
  }
  wlSaving.value = true
  try {
    const res = await webLogin(username, password)
    tokenStorage.setToken(res.access_token)
    userStorage.setUserInfo({
      id: res.user_info.id,
      nickname: res.user_info.nickname,
      role: res.role,
      is_verified: res.user_info.is_verified,
    })
    showWebLogin.value = false
    loggedIn.value = true
    isVerified.value = !!res.user_info.is_verified
    uni.showToast({ title: `欢迎，${res.user_info.nickname}`, icon: 'success' })
    loadedTabs.value.clear()
    await loadProfile()
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '登录失败', icon: 'none' })
  } finally {
    wlSaving.value = false
  }
}

// 公众号网页授权：跳转微信换取 code，回跳 oauth-callback 页完成登录
const beginMpOAuth = () => {
  if (!WECHAT_MP_APP_ID) {
    uni.showToast({ title: '未配置公众号登录', icon: 'none' })
    return
  }
  const redirect = window.location.origin + '/#/pages/oauth-callback/index'
  const url = 'https://open.weixin.qq.com/connect/oauth2/authorize?appid=' + WECHAT_MP_APP_ID +
    '&redirect_uri=' + encodeURIComponent(redirect) +
    '&response_type=code&scope=snsapi_base&state=eywall#wechat_redirect'
  window.location.href = url
}

onShow(() => loadProfile())

const goEditProfile = () => {
  if (!loggedIn.value) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  uni.navigateTo({ url: '/pages/profile-edit/index' })
}
const goSettings = () => uni.navigateTo({ url: '/pages/settings/index' })
const goVerify = () => uni.navigateTo({ url: '/pages/verify/index' })
const goAdmin = () => uni.navigateTo({ url: '/pages/admin/index' })
const goDetail = (id: number) => uni.navigateTo({ url: `/pages/post-detail/index?id=${id}` })
</script>

<style scoped>
.page-mine { min-height: 100vh; background: var(--bg-page); padding-bottom: 40rpx; }

/* 1. 横幅（无照片时粉色渐变兜底） */
.banner {
  height: 460rpx;
  background: linear-gradient(160deg, #fbc6d0 0%, #f7a8bc 45%, #f2b8c8 100%);
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

.avatar-cam {
  position: absolute;
  right: -4rpx;
  bottom: -4rpx;
  width: 52rpx;
  height: 52rpx;
  border-radius: 50%;
  background: var(--brand-red-dark);
  border: 4rpx solid #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  z-index: 2;
}
.avatar-ring { position: relative; }
.avatar-img { width: 176rpx; height: 176rpx; border-radius: 50%; }

/* 2. 白色圆角面板 */
/* 头像悬浮几何（transform 实现，免疫负 margin 塌陷/兼容性差异）：
   头像(176rpx) 上移 100rpx ≈ 4/7 压横幅、3/7 落白面板；
   margin-bottom 负值回收位移产生的空隙，保留 24rpx 与昵称的间距 */
.sheet {
  background: #ffffff;
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
  padding: 8rpx;
  background: #ffffff;
  border-radius: 50%;
  box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.06);
}
.avatar {
  width: 176rpx;
  height: 176rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.avatar-letter { font-size: 80rpx; font-weight: bold; color: #ffffff; }

/* 昵称行 + 编辑资料 + 齿轮 */
.name-row { display: flex; align-items: center; margin-top: 24rpx; }
.nickname { font-size: 40rpx; font-weight: bold; color: var(--text-1); }
.name-actions { margin-left: auto; display: flex; align-items: center; gap: 18rpx; }
.edit-btn {
  border: 2rpx solid #e5e6eb;
  border-radius: 36rpx;
  padding: 14rpx 34rpx;
  font-size: 26rpx;
  color: var(--text-1);
  background: #ffffff;
}
.gear-btn { padding: 8rpx; }
.gear-icon { font-size: 40rpx; line-height: 1; }

.bio { margin-top: 18rpx; display: flex; flex-direction: column; gap: 8rpx; }
.bio text { font-size: 24rpx; color: var(--text-3); line-height: 1.6; }

.dev-login-row { display: flex; gap: 16rpx; margin-top: 24rpx; }
.dev-capsule {
  background: var(--brand-red-dark);
  color: #ffffff;
  font-size: 24rpx;
  padding: 14rpx 28rpx;
  border-radius: 30rpx;
}
.dev-capsule.admin { background: #8a5cf5; }

/* 网页版登录弹窗（H5） */
.wl-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}
.wl-card {
  width: 580rpx;
  background: #ffffff;
  border-radius: 32rpx;
  padding: 48rpx 40rpx 40rpx;
  display: flex;
  flex-direction: column;
}
.wl-title { font-size: 36rpx; font-weight: bold; color: var(--text-1); text-align: center; }
.wl-sub { font-size: 22rpx; color: var(--text-3); text-align: center; margin-top: 10rpx; }
.wl-input {
  margin-top: 28rpx;
  background: var(--bg-page);
  border-radius: 16rpx;
  padding: 22rpx 26rpx;
  font-size: 28rpx;
  color: var(--text-1);
}
.wl-btn {
  margin-top: 36rpx;
  background: var(--brand-red-dark);
  color: #ffffff;
  font-size: 30rpx;
  font-weight: 600;
  text-align: center;
  padding: 22rpx 0;
  border-radius: 40rpx;
}
.wl-btn.saving { opacity: 0.6; }

.slim-tip {
  margin-top: 20rpx;
  background: var(--brand-red-soft);
  border-radius: 12rpx;
  padding: 14rpx 22rpx;
  font-size: 24rpx;
  color: var(--brand-red-dark);
}
.slim-tip.admin { background: #f1ecfe; color: #6b46d6; }

/* 3. 四栏内容 Tab（下划线式） */
.content-tabs {
  display: flex;
  margin-top: 36rpx;
  border-bottom: 1rpx solid #f0f0f2;
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
.ct-item.on .ct-icon { opacity: 1; }
.ct-underline {
  position: absolute;
  bottom: -2rpx;
  width: 80rpx;
  height: 6rpx;
  border-radius: 3rpx;
  background: var(--brand-red);
}

/* 4. 内容区 */
.content-panel { margin-top: 30rpx; }
.content-title { font-size: 30rpx; font-weight: bold; color: var(--text-1); }

.post-card {
  background: #fafafb;
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
.pc-thumb {
  width: 160rpx;
  height: 160rpx;
  border-radius: 16rpx;
  flex-shrink: 0;
}
.pc-thumb-ph {
  background: linear-gradient(135deg, #fce4ec, #f8bbd0);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48rpx;
  opacity: 0.7;
}

.empty { text-align: center; color: var(--text-3); font-size: 24rpx; padding: 80rpx 0; }
.wl-wechat {
  margin-top: 20rpx;
  padding: 24rpx 0;
  border: 2rpx solid #07c160;
  border-radius: var(--radius-btn);
  text-align: center;
}
.wl-wechat text {
  color: #07c160;
  font-size: 30rpx;
  font-weight: 600;
}
</style>
