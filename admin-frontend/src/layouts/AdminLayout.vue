<template>
  <el-container class="layout">
    <!-- 侧边栏（桌面端） -->
    <el-aside width="220px" class="aside desktop-aside">
      <div class="brand">
        <span class="brand-mark">鄂</span>
        <span class="brand-text">鄂应墙管理后台</span>
      </div>
      <el-menu :default-active="activeMenu" router class="menu">
        <el-menu-item v-for="item in visibleMenus" :key="item.path" :index="item.path">
          <el-icon class="menu-icon" :size="18"><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="main-container">
      <!-- 顶栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-button class="mobile-toggle" text circle @click="drawerVisible = true" aria-label="打开侧边导航">
            <el-icon :size="20"><Expand /></el-icon>
          </el-button>
          <div class="breadcrumb">{{ currentTitle }}</div>
        </div>
        <div class="header-right">
          <el-button circle text class="theme-btn" @click="toggleTheme" aria-label="切换主题">
            <el-icon :size="18">
              <Sunny v-if="isDark" />
              <Moon v-else />
            </el-icon>
          </el-button>
          <el-dropdown @command="onCommand">
            <span class="user-chip">
              <el-icon><UserFilled /></el-icon>
              <span class="user-name">{{ auth.adminName || '管理员' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容 -->
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>

    <!-- 移动端抽屉导航（窄屏） -->
    <el-drawer
      v-model="drawerVisible"
      direction="ltr"
      :size="260"
      :with-header="false"
      class="mobile-drawer"
    >
      <div class="drawer-content">
        <div class="drawer-brand">
          <div class="brand">
            <span class="brand-mark">鄂</span>
            <span class="brand-text">鄂应墙管理后台</span>
          </div>
          <el-button circle text class="drawer-close" @click="drawerVisible = false" aria-label="关闭导航">
            <el-icon :size="18"><Close /></el-icon>
          </el-button>
        </div>
        <el-scrollbar class="drawer-menu-scroll">
          <el-menu :default-active="activeMenu" router class="menu" @select="onMenuSelect">
            <el-menu-item v-for="item in visibleMenus" :key="item.path" :index="item.path">
              <el-icon class="menu-icon" :size="18"><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
            </el-menu-item>
          </el-menu>
        </el-scrollbar>
        <div class="drawer-footer">
          <div class="drawer-user">
            <el-icon><UserFilled /></el-icon>
            <span class="drawer-username">{{ auth.adminName || '管理员' }}</span>
          </div>
          <div class="drawer-actions">
            <el-button size="small" text @click="openPwdFromDrawer">改密</el-button>
            <el-button size="small" text type="danger" @click="logoutFromDrawer">退出</el-button>
            <el-button circle text size="small" @click="toggleTheme" aria-label="切换主题">
              <el-icon :size="16">
                <Sunny v-if="isDark" />
                <Moon v-else />
              </el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </el-drawer>

    <ChangePasswordDialog v-model="showPwd" />
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  UserFilled,
  ArrowDown,
  Sunny,
  Moon,
  Expand,
  Close,
  DataBoard,
  Document,
  View,
  Message,
  Finished,
  CircleClose,
  School,
  User,
  WarningFilled,
  ChatLineSquare,
  ChatDotRound,
  Basketball,
  Picture,
  Promotion,
  Memo,
  Lock,
  PriceTag,
  Calendar,
  ChatLineSquare,
  Setting,
} from '@element-plus/icons-vue'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import ChangePasswordDialog from '@/components/ChangePasswordDialog.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { isDark, toggle: toggleTheme } = useThemeStore()

interface MenuItem {
  path: string
  title: string
  icon: Component
}

// 图标使用 SVG 组件（currentColor 继承主题文字色），避免系统 Emoji 字体差异
const menus: MenuItem[] = [
  { path: '/dashboard', title: '看板', icon: DataBoard },
  { path: '/runtime-controls', title: '内测设置', icon: Setting },
  { path: '/posts', title: '帖子管理', icon: Document },
  { path: '/moderation-jobs', title: '人工审核', icon: View },
  { path: '/appeals', title: '申诉处理', icon: Message },
  { path: '/moderation-records', title: '审核记录', icon: Finished },
  { path: '/sensitive-words', title: '敏感词库', icon: CircleClose },
  { path: '/student-verifications', title: '学生证认证', icon: School },
  { path: '/users', title: '用户管理', icon: User },
  { path: '/reports', title: '举报处理', icon: WarningFilled },
  { path: '/feedback', title: '反馈箱', icon: ChatLineSquare },
  { path: '/comments', title: '评论管理', icon: ChatDotRound },
  { path: '/parties', title: '组局管理', icon: Basketball },
  { path: '/banners', title: '轮播广告', icon: Picture },
  { path: '/announcements', title: '公告群发', icon: Promotion },
  { path: '/logs', title: '操作日志', icon: Memo },
  { path: '/admins', title: '管理员账号', icon: Lock },
  { path: '/tags', title: '标签管理', icon: PriceTag },
  { path: '/activities', title: '站内活动', icon: Calendar },
]

// 仅 owner 可见的菜单：内测开关（能改线上发布与审核开关）与反馈箱
// （含用户上报截图、诊断日志与客户端 IP，属隐私数据）
const ownerOnlyPaths = ['/runtime-controls', '/feedback']
const visibleMenus = computed(() => menus.filter(item => !ownerOnlyPaths.includes(item.path) || auth.isOwner))
const activeMenu = computed(() => route.path)
const currentTitle = computed(() => (route.meta.title as string) || '')

const showPwd = ref(false)
const drawerVisible = ref(false)

const onMenuSelect = () => {
  drawerVisible.value = false
}

const openPwdFromDrawer = () => {
  drawerVisible.value = false
  showPwd.value = true
}

const logoutFromDrawer = async () => {
  drawerVisible.value = false
  await onCommand('logout')
}

onMounted(() => { auth.fetchMe() })

const onCommand = async (cmd: string) => {
  if (cmd === 'password') {
    showPwd.value = true
  } else if (cmd === 'logout') {
    await ElMessageBox.confirm('确定退出登录吗？', '提示', { type: 'warning' })
    await auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.layout { height: 100%; }
.aside {
  background: var(--app-aside-bg);
  display: flex; flex-direction: column;
  border-right: 1px solid var(--border-light, rgba(255, 255, 255, 0.07));
  flex-shrink: 0;
}
.brand {
  height: 60px;
  display: flex; align-items: center; gap: 10px;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-light, rgba(255, 255, 255, 0.07));
}
.brand-mark {
  width: 32px; height: 32px;
  border-radius: 10px;
  background: var(--app-brand-grad);
  color: #fff; font-weight: bold;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 12px rgba(29, 155, 240, 0.35);
}
.brand-text { color: var(--app-title-color); font-size: 15px; font-weight: 600; white-space: nowrap; }

/* 菜单：X 侧栏风——黑底、灰字、激活近白 + 悬停填充灰（颜色全走主题令牌） */
.menu {
  border-right: none; flex: 1;
  --el-menu-bg-color: var(--app-aside-bg);
  --el-menu-text-color: var(--app-aside-text);
  --el-menu-active-color: var(--app-aside-active);
  --el-menu-hover-bg-color: var(--app-aside-active-bg);
  padding: 8px 10px;
}
.menu :deep(.el-menu-item) {
  border-radius: 10px;
  margin-bottom: 2px;
  height: 42px; line-height: 42px;
}
.menu :deep(.el-menu-item.is-active) {
  background: var(--app-aside-active-bg);
  font-weight: 600;
}
.menu-icon { margin-right: 8px; flex-shrink: 0; }

.main-container {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.header {
  background: var(--app-header-bg);
  backdrop-filter: blur(16px);
  border-bottom: var(--app-header-border);
  display: flex; align-items: center; justify-content: space-between;
  box-shadow: none;
  padding: 0 20px;
}
.header-left {
  display: flex;
  align-items: center;
  min-width: 0;
}
.mobile-toggle {
  display: none;
  margin-right: 8px;
  color: var(--app-aside-text);
}
.breadcrumb {
  font-size: 16px;
  font-weight: 600;
  color: var(--app-title-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-chip {
  display: flex; align-items: center; gap: 6px;
  cursor: pointer; color: var(--app-aside-text); font-size: 14px;
  padding: 6px 12px; border-radius: 18px;
}
.user-chip:hover { background: var(--app-aside-active-bg); }
.user-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.header-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.theme-btn { color: var(--app-aside-text); }
.main { background: var(--app-bg); padding: 20px; overflow-y: auto; flex: 1; }

/* 移动端抽屉样式 */
:deep(.mobile-drawer .el-drawer__body) {
  padding: 0 !important;
  height: 100%;
  overflow: hidden;
  background: var(--app-aside-bg);
}
.drawer-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--app-aside-bg);
}
.drawer-brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-light, rgba(255, 255, 255, 0.07));
  padding-right: 12px;
}
.drawer-brand .brand {
  border-bottom: none;
  flex: 1;
}
.drawer-close {
  color: var(--app-aside-text);
}
.drawer-menu-scroll {
  flex: 1;
}
.drawer-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border-light, rgba(255, 255, 255, 0.07));
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--app-aside-bg);
}
.drawer-user {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--app-title-color);
  font-size: 13px;
  font-weight: 600;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.drawer-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

@media (max-width: 768px) {
  .desktop-aside {
    display: none !important;
  }
  .mobile-toggle {
    display: inline-flex !important;
  }
  .header {
    padding: 0 12px;
  }
  .main {
    padding: 12px;
  }
  .user-name {
    max-width: 70px;
  }
}
</style>
