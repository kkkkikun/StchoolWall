<script setup lang="ts">
/** 电脑端登录。 */
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const username = ref('')
const password = ref('')
const submitting = ref(false)

async function submit(): Promise<void> {
  if (!username.value.trim() || !password.value) {
    ElMessage.warning('请填写登录名和密码')
    return
  }
  submitting.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    ElMessage.success(`欢迎回来，${auth.user?.nickname ?? ''}`)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.push(redirect)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '登录失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="sw-auth">
    <section class="sw-card sw-auth__card">
      <h2 class="sw-auth__title">登录鄂应墙</h2>
      <p class="sw-muted">用电脑访问校园墙，浏览、发帖、评论都在这里。</p>

      <el-form class="sw-auth__form" @submit.prevent="submit">
        <el-form-item label="登录名">
          <el-input v-model="username" autocomplete="username" placeholder="2–20 位登录名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            show-password
            autocomplete="current-password"
            placeholder="登录密码"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button type="primary" class="sw-auth__submit" :loading="submitting" @click="submit">
          登录
        </el-button>
      </el-form>

      <p class="sw-auth__footer">
        还没有账号？
        <RouterLink to="/register">注册一个</RouterLink>
      </p>
    </section>
  </div>
</template>

<style scoped>
.sw-auth {
  display: flex;
  justify-content: center;
  padding: var(--sw-space-6) 0;
}

.sw-auth__card {
  width: 100%;
  max-width: 420px;
  padding: var(--sw-space-6);
}

.sw-auth__title {
  margin: 0;
  font-size: var(--sw-text-xl);
}

.sw-auth__form {
  margin-top: var(--sw-space-5);
}

.sw-auth__submit {
  width: 100%;
  min-height: var(--sw-control-size);
}

.sw-auth__footer {
  margin: var(--sw-space-4) 0 0;
  color: var(--sw-text-secondary);
  font-size: var(--sw-text-sm);
}
</style>
