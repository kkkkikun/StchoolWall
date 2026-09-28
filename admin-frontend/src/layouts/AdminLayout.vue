<template>
  <el-container class="layout">
    <!-- 侧边栏 -->
    <el-aside width="220px" class="aside">
      <div class="brand">
        <span class="brand-mark">鄂</span>
        <span class="brand-text">鄂应墙管理后台</span>
      </div>
      <el-menu :default-active="activeMenu" router class="menu">
        <el-menu-item v-for="item in menus" :key="item.path" :index="item.path">
          <span class="menu-icon">{{ item.icon }}</span>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶栏 -->
      <el-header class="header">
        <div class="breadcrumb">{{ currentTitle }}</div>
        <el-dropdown @command="onCommand">
          <span class="user-chip">
            <el-icon><UserFilled /></el-icon>
            {{ auth.adminName || '管理员' }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="password">修改密码</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <!-- 内容 -->
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>

    <ChangePasswordDialog v-model="showPwd" />
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { UserFilled, ArrowDown } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import ChangePasswordDialog from '@/components/ChangePasswordDialog.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const menus = [
  { path: '/dashboard', title: '看板', icon: '📊' },
  { path: '/posts', title: '帖子管理', icon: '📝' },
  { path: '/moderation-records', title: '审核记录', icon: '🛡️' },
  { path: '/sensitive-words', title: '敏感词库', icon: '🚫' },
  { path: '/users', title: '用户管理', icon: '👥' },
  { path: '/reports', title: '举报处理', icon: '🚨' },
  { path: '/comments', title: '评论管理', icon: '💬' },
  { path: '/parties', title: '组局管理', icon: '🎉' },
  { path: '/banners', title: '轮播广告', icon: '🖼️' },
  { path: '/announcements', title: '公告群发', icon: '📢' },
  { path: '/logs', title: '操作日志', icon: '📋' },
  { path: '/admins', title: '管理员账号', icon: '🔐' },
  { path: '/tags', title: '标签管理', icon: '🏷️' },
  { path: '/activities', title: '站内活动', icon: '📌' },
]

const activeMenu = computed(() => route.path)
const currentTitle = computed(() => (route.meta.title as string) || '')

const showPwd = ref(false)

onMounted(() => { auth.fetchMe() })

const onCommand = async (cmd: string) => {
  if (cmd === 'password') {
    showPwd.value = true
  } else if (cmd === 'logout') {
    await ElMessageBox.confirm('确定退出登录吗？', '提示', { type: 'warning' })
    auth.logout()
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
.brand-text { color: var(--app-title-color); font-size: 15px; font-weight: 600; }

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
.menu-icon { margin-right: 8px; }

.header {
  background: var(--app-header-bg);
  backdrop-filter: blur(16px);
  border-bottom: var(--app-header-border);
  display: flex; align-items: center; justify-content: space-between;
  box-shadow: none;
}
.breadcrumb { font-size: 16px; font-weight: 600; color: var(--app-title-color); }
.user-chip {
  display: flex; align-items: center; gap: 6px;
  cursor: pointer; color: var(--app-aside-text); font-size: 14px;
  padding: 6px 12px; border-radius: 18px;
}
.user-chip:hover { background: var(--app-aside-active-bg); }
.main { background: var(--app-bg); padding: 20px; overflow-y: auto; }
</style>
