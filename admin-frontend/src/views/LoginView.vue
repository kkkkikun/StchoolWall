<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <div class="logo">鄂</div>
        <h1>鄂应墙 · 管理后台</h1>
        <p class="sub">SchoolWall Admin Console</p>
      </div>
      <el-form :model="form" @keyup.enter="onLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" size="large" :prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" size="large"
                    :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="onLogin">
          登 录
        </el-button>
      </el-form>
      <p class="tip">初始账号请在后端执行 python -m app.create_admin 创建</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const form = reactive({ username: '', password: '' })
const loading = ref(false)

const onLogin = async () => {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push((route.query.redirect as string) || '/')
  } catch {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(45% 40% at 50% 0%, rgba(29, 155, 240, 0.10) 0%, transparent 70%),
    var(--app-bg);
}
.login-card {
  width: 380px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter, #eff3f4);
  border-radius: 16px;
  padding: 40px 36px 28px;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.08);
}
html.dark .login-card { box-shadow: 0 24px 70px rgba(0, 0, 0, 0.6); }
.login-header { text-align: center; margin-bottom: 28px; }
.logo {
  width: 64px; height: 64px;
  margin: 0 auto 14px;
  border-radius: 50%;
  background: #1d9bf0;
  color: #fff;
  font-size: 32px;
  font-weight: 800;
  display: flex; align-items: center; justify-content: center;
}
h1 { font-size: 22px; color: var(--el-text-color-primary); font-weight: 800; }
.sub { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 6px; letter-spacing: 1px; }
.login-btn { width: 100%; margin-top: 6px; border-radius: 9999px; font-weight: 700; }
.tip { font-size: 12px; color: var(--el-text-color-placeholder); text-align: center; margin-top: 16px; }
</style>
