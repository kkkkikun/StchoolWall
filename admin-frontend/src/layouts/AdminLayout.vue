<template>
  <el-container class="layout">
    <!-- 侧边栏 -->
    <el-aside width="220px" class="aside">
      <div class="brand">
        <span class="brand-mark">鄂</span>
        <span class="brand-text">鄂应墙管理后台</span>
      </div>
      <el-menu :default-active="activeMenu" router background-color="#1d2b36" text-color="#a7b7c7"
               active-text-color="#ffffff" class="menu">
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
.aside { background: #1d2b36; display: flex; flex-direction: column; }
.brand {
  height: 60px;
  display: flex; align-items: center; gap: 10px;
  padding: 0 20px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.brand-mark {
  width: 32px; height: 32px;
  border-radius: 8px;
  background: #f73b43;
  color: #fff; font-weight: bold;
  display: flex; align-items: center; justify-content: center;
}
.brand-text { color: #fff; font-size: 15px; font-weight: 600; }
.menu { border-right: none; flex: 1; }
.menu-icon { margin-right: 8px; }

.header {
  background: #fff;
  display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0,21,41,0.08);
}
.breadcrumb { font-size: 16px; font-weight: 600; color: #303133; }
.user-chip {
  display: flex; align-items: center; gap: 6px;
  cursor: pointer; color: #606266; font-size: 14px;
}
.main { background: #f5f7fa; padding: 20px; overflow-y: auto; }
</style>
