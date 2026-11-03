<script setup lang="ts">
/**
 * PC 端骨架：顶部导航 + 左侧导航 + 内容区 + 右侧信息栏。
 * 与移动端五 Tab 的差异：电脑端用三栏布局承载更高的信息密度。
 */
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Bell, ChatDotRound, EditPen, Search } from '@element-plus/icons-vue'

import { useAuthStore } from '@/stores/auth'
import { getHotUsers, getNotifications, getUnreadSummary } from '@/api/user'
import { getTags } from '@/api/content'
import type { HotUser, NotificationItem, TagItem } from '@/api/types'

// 反馈弹窗带上传、诊断等交互，懒加载避免把 Element Plus 表单组件拖进首屏包
const FeedbackDialog = defineAsyncComponent(() => import('@/components/FeedbackDialog.vue'))

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const keyword = ref('')
const hotTags = ref<TagItem[]>([])
const hotUsers = ref<HotUser[]>([])
const announcements = ref<NotificationItem[]>([])
const unread = ref(0)
const feedbackOpen = ref(false)

/** 反馈入口做成快捷键，测试员遇到问题当场就能截图上报。 */
function onShortcut(event: KeyboardEvent): void {
  if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'f') {
    event.preventDefault()
    feedbackOpen.value = true
  }
}

const navItems = [
  { name: 'feed', label: '校园墙' },
  { name: 'search', label: '搜索' },
  { name: 'tags', label: '标签' },
]

const userNavItems = [
  { name: 'my-posts', label: '我的帖子' },
  { name: 'notifications', label: '消息' },
  { name: 'settings', label: '设置' },
]

const activeNav = computed(() => {
  if (route.name === 'tag-posts') return 'tags'
  if (route.name === 'post') return 'feed'
  return String(route.name ?? 'feed')
})

function submitSearch(): void {
  const value = keyword.value.trim()
  if (!value) return
  router.push({ name: 'search', query: { q: value } })
}

function toggleTheme(): void {
  const root = document.documentElement
  const isDark = root.classList.toggle('theme-dark')
  localStorage.setItem('sw_theme', isDark ? 'dark' : 'light')
}

async function loadAside(): Promise<void> {
  const [tags, users] = await Promise.all([
    getTags().catch(() => [] as TagItem[]),
    getHotUsers(5).catch(() => [] as HotUser[]),
  ])
  hotTags.value = tags
  hotUsers.value = users
}

async function loadAnnouncements(): Promise<void> {
  if (!auth.loggedIn) return
  const page = await getNotifications('announcement').catch(() => null)
  if (!page) return
  announcements.value = page.items.slice(0, 3)
  const summary = await getUnreadSummary().catch(() => null)
  if (summary) unread.value = Object.values(summary).reduce((sum, count) => sum + count, 0)
}

async function handleLogout(): Promise<void> {
  await auth.logout()
  ElMessage.success('已退出登录')
  router.push({ name: 'feed' })
}

onMounted(() => {
  const saved = localStorage.getItem('sw_theme')
  if (saved === 'dark') document.documentElement.classList.add('theme-dark')
  window.addEventListener('keydown', onShortcut)
  loadAside()
  loadAnnouncements()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onShortcut)
})
</script>

<template>
  <div class="sw-shell">
    <header class="sw-header">
      <div class="sw-header__inner">
        <RouterLink class="sw-logo" to="/">
          <span class="sw-logo__mark">墙</span>
          <span class="sw-logo__text">鄂应墙 · 电脑版</span>
        </RouterLink>

        <nav class="sw-header__nav">
          <RouterLink v-for="item in navItems" :key="item.name" :to="{ name: item.name }" class="sw-header__link">
            {{ item.label }}
          </RouterLink>
        </nav>

        <div class="sw-header__search">
          <el-input
            v-model="keyword"
            placeholder="搜帖子、找人、找标签"
            :prefix-icon="Search"
            clearable
            @keyup.enter="submitSearch"
          />
        </div>

        <div class="sw-header__actions">
          <el-tooltip content="发布帖子" placement="bottom">
            <el-button type="primary" :icon="EditPen" @click="router.push({ name: 'publish' })">发布</el-button>
          </el-tooltip>

          <el-tooltip content="消息通知" placement="bottom">
            <el-badge :value="unread" :hidden="unread === 0" class="sw-badge">
              <el-button circle :icon="Bell" @click="router.push({ name: 'notifications' })" />
            </el-badge>
          </el-tooltip>

          <el-tooltip content="意见反馈（Ctrl+Shift+F）" placement="bottom">
            <el-button
              class="sw-feedback-trigger"
              circle
              :icon="ChatDotRound"
              @click="feedbackOpen = true"
            />
          </el-tooltip>

          <el-button text @click="toggleTheme">暗色</el-button>

          <el-dropdown v-if="auth.loggedIn">
            <span class="sw-user">
              <el-avatar :size="28">{{ (auth.user?.nickname ?? '匿').slice(0, 1) }}</el-avatar>
              <span class="sw-user__name">{{ auth.user?.nickname }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push({ name: 'my-posts' })">我的帖子</el-dropdown-item>
                <el-dropdown-item @click="router.push({ name: 'settings' })">账号设置</el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <template v-else>
            <el-button text @click="router.push({ name: 'login' })">登录</el-button>
            <el-button type="primary" plain @click="router.push({ name: 'register' })">注册</el-button>
          </template>
        </div>
      </div>
    </header>

    <div class="sw-body">
      <aside class="sw-rail">
        <nav class="sw-rail__group">
          <RouterLink
            v-for="item in navItems"
            :key="item.name"
            :to="{ name: item.name }"
            class="sw-rail__item"
            :class="{ 'is-active': activeNav === item.name }"
          >
            {{ item.label }}
          </RouterLink>
        </nav>

        <nav v-if="auth.loggedIn" class="sw-rail__group">
          <p class="sw-rail__title">我的</p>
          <RouterLink
            v-for="item in userNavItems"
            :key="item.name"
            :to="{ name: item.name }"
            class="sw-rail__item"
            :class="{ 'is-active': activeNav === item.name }"
          >
            {{ item.label }}
          </RouterLink>
        </nav>

        <div class="sw-rail__group">
          <p class="sw-rail__title">热门标签</p>
          <RouterLink
            v-for="tag in hotTags.slice(0, 10)"
            :key="tag.id"
            class="sw-rail__item"
            :to="{ name: 'tag-posts', params: { name: tag.name } }"
          >
            # {{ tag.name }}
          </RouterLink>
        </div>
      </aside>

      <main class="sw-main">
        <RouterView />
      </main>

      <aside class="sw-aside">
        <section v-if="announcements.length" class="sw-card sw-aside__card">
          <h3 class="sw-card__title">公告</h3>
          <ul class="sw-aside__list">
            <li v-for="item in announcements" :key="item.id" class="sw-aside__item">
              {{ item.payload?.title ?? item.actorNickname }}
            </li>
          </ul>
        </section>

        <section class="sw-card sw-aside__card">
          <h3 class="sw-card__title">校园活跃榜</h3>
          <ul class="sw-aside__list">
            <li v-for="user in hotUsers" :key="user.id" class="sw-aside__item sw-aside__user">
              <span>{{ user.nickname }}</span>
              <span class="sw-muted">{{ user.heat }}</span>
            </li>
          </ul>
          <p v-if="!hotUsers.length" class="sw-muted">暂无数据</p>
        </section>
      </aside>
    </div>

    <FeedbackDialog v-model="feedbackOpen" />
  </div>
</template>

<style scoped>
.sw-shell {
  min-height: 100%;
}

.sw-header {
  position: sticky;
  top: 0;
  z-index: 20;
  height: var(--sw-header-height);
  background: var(--sw-surface);
  border-bottom: 1px solid var(--sw-border);
}

.sw-header__inner {
  max-width: 1360px;
  height: 100%;
  margin: 0 auto;
  padding: 0 var(--sw-space-5);
  display: flex;
  align-items: center;
  gap: var(--sw-space-5);
}

.sw-logo {
  display: flex;
  align-items: center;
  gap: var(--sw-space-2);
  color: var(--sw-text);
  font-weight: 700;
}

.sw-logo__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--sw-radius-sm);
  background: var(--sw-primary);
  color: #fff;
}

.sw-header__nav {
  display: flex;
  gap: var(--sw-space-4);
}

.sw-header__link {
  color: var(--sw-text-secondary);
  padding: 6px 0;
}

.sw-header__link.router-link-active {
  color: var(--sw-primary-text);
  font-weight: 600;
}

.sw-header__search {
  flex: 1;
  max-width: 420px;
}

.sw-header__actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--sw-space-2);
}

.sw-badge {
  margin-right: var(--sw-space-1);
}

.sw-user {
  display: flex;
  align-items: center;
  gap: var(--sw-space-2);
  cursor: pointer;
  color: var(--sw-text);
}

.sw-user__name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sw-body {
  max-width: 1360px;
  margin: 0 auto;
  padding: var(--sw-space-5);
  display: grid;
  grid-template-columns: var(--sw-rail-width) minmax(0, 1fr) var(--sw-aside-width);
  gap: var(--sw-space-5);
  align-items: start;
}

.sw-rail {
  position: sticky;
  top: calc(var(--sw-header-height) + var(--sw-space-5));
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-5);
}

.sw-rail__group {
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--sw-surface);
  border: 1px solid var(--sw-border);
  border-radius: var(--sw-radius);
  padding: var(--sw-space-2);
}

.sw-rail__title {
  margin: var(--sw-space-2) var(--sw-space-2) var(--sw-space-1);
  font-size: var(--sw-text-xs);
  color: var(--sw-text-muted);
}

.sw-rail__item {
  display: flex;
  align-items: center;
  min-height: var(--sw-control-size);
  padding: 0 var(--sw-space-2);
  border-radius: var(--sw-radius-sm);
  color: var(--sw-text-secondary);
}

.sw-rail__item:hover {
  background: var(--sw-surface-muted);
  color: var(--sw-text);
}

.sw-rail__item.is-active {
  background: var(--sw-primary-soft);
  color: var(--sw-primary-text);
  font-weight: 600;
}

.sw-main {
  min-width: 0;
  max-width: var(--sw-content-width);
}

.sw-aside {
  position: sticky;
  top: calc(var(--sw-header-height) + var(--sw-space-5));
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-aside__card {
  padding: var(--sw-space-4);
}

.sw-aside__list {
  margin: var(--sw-space-3) 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-2);
}

.sw-aside__item {
  font-size: var(--sw-text-sm);
  color: var(--sw-text-secondary);
}

.sw-aside__user {
  display: flex;
  justify-content: space-between;
}

@media (max-width: 1180px) {
  .sw-body {
    grid-template-columns: var(--sw-rail-width) minmax(0, 1fr);
  }

  .sw-aside {
    display: none;
  }
}
</style>
