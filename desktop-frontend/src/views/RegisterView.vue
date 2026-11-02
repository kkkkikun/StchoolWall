<script setup lang="ts">
/** 注册网页端账号。 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const confirm = ref('')
const submitting = ref(false)

/** 后端要求登录名 2–20 位、密码至少 10 位，前端先拦一道，减少无谓往返。 */
const usernameValid = computed(() => username.value.trim().length >= 2 && username.value.trim().length <= 20)
const passwordValid = computed(() => password.value.length >= 10 && password.value.length <= 64)
const confirmed = computed(() => confirm.value.length > 0 && confirm.value === password.value)

async function submit(): Promise<void> {
  if (!usernameValid.value) {
    ElMessage.warning('登录名需要 2–20 位')
    return
  }
  if (!passwordValid.value) {
    ElMessage.warning('密码至少 10 位')
    return
  }
  if (!confirmed.value) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  submitting.value = true
  try {
    await auth.register(username.value.trim(), password.value)
    ElMessage.success('注册成功')
    await router.push({ name: 'feed' })
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '注册失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="sw-auth">
    <section class="sw-card sw-auth__card">
      <h2 class="sw-auth__title">注册账号</h2>
      <p class="sw-muted">注册后即可在电脑端发帖与互动；发布内容仍需通过学生身份与内容审核。</p>

      <el-form class="sw-auth__form" @submit.prevent="submit">
        <el-form-item label="登录名">
          <el-input v-model="username" placeholder="2–20 位字母或数字" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" show-password placeholder="至少 10 位" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="confirm"
            type="password"
            show-password
            placeholder="再输入一次"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button type="primary" class="sw-auth__submit" :loading="submitting" @click="submit">
          注册
        </el-button>
      </el-form>

      <p class="sw-auth__footer">
        已有账号？
        <RouterLink to="/login">直接登录</RouterLink>
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
