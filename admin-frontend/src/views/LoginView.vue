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
  background: linear-gradient(135deg, #2fae7e 0%, #8fdcb8 55%, #d9f4e6 100%);
}
.login-card {
  width: 380px;
  background: #fff;
  border-radius: 18px;
  padding: 40px 36px 28px;
  box-shadow: 0 20px 60px rgba(23, 90, 62, 0.25);
}
.login-header { text-align: center; margin-bottom: 28px; }
.logo {
  width: 64px; height: 64px;
  margin: 0 auto 14px;
  border-radius: 18px;
  background: linear-gradient(135deg, #2fae7e, #8fdcb8);
  color: #fff;
  font-size: 34px;
  font-weight: bold;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 18px rgba(33, 154, 107, 0.35);
}
h1 { font-size: 20px; color: #1f2d27; }
.sub { font-size: 12px; color: #93a49c; margin-top: 6px; letter-spacing: 1px; }
.login-btn { width: 100%; margin-top: 6px; border-radius: 22px; }
.tip { font-size: 12px; color: #b3c2ba; text-align: center; margin-top: 16px; }
</style>
