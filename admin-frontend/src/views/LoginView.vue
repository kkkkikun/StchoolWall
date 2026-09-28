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
    radial-gradient(60% 50% at 18% 22%, rgba(124, 92, 255, 0.28) 0%, transparent 60%),
    radial-gradient(50% 45% at 82% 78%, rgba(34, 211, 238, 0.20) 0%, transparent 60%),
    #0f1219;
}
.login-card {
  width: 380px;
  background: rgba(23, 27, 38, 0.72);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 18px;
  padding: 40px 36px 28px;
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.55), 0 0 60px rgba(124, 92, 255, 0.12);
}
.login-header { text-align: center; margin-bottom: 28px; }
.logo {
  width: 64px; height: 64px;
  margin: 0 auto 14px;
  border-radius: 18px;
  background: linear-gradient(135deg, #7c5cff, #22d3ee);
  color: #fff;
  font-size: 34px;
  font-weight: bold;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 26px rgba(124, 92, 255, 0.55);
}
h1 { font-size: 20px; color: #e9ecf5; }
.sub { font-size: 12px; color: #737e96; margin-top: 6px; letter-spacing: 1px; }
.login-btn { width: 100%; margin-top: 6px; border-radius: 22px; }
.tip { font-size: 12px; color: #4d5670; text-align: center; margin-top: 16px; }
</style>
