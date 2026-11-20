<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <div class="logo">鄂</div>
        <h1>鄂应墙 · 管理后台</h1>
        <p class="sub">SchoolWall Admin Console</p>
      </div>

      <template v-if="!setupRequired">
        <div class="login-kind" role="tablist" aria-label="管理员类型">
          <button type="button" :class="{ active: loginKind === 'admin' }" @click="switchKind('admin')">普通管理员</button>
          <button type="button" :class="{ active: loginKind === 'owner' }" @click="switchKind('owner')">超级管理员</button>
        </div>
        <el-form :model="form" @keyup.enter="onLogin">
          <el-form-item>
            <el-input v-model="form.username" placeholder="用户名" size="large" :prefix-icon="User" autocomplete="username" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.password" type="password" placeholder="密码" size="large"
                      :prefix-icon="Lock" show-password autocomplete="current-password" />
          </el-form-item>
          <el-form-item v-if="loginKind === 'owner'">
            <el-input v-model="form.totpCode" placeholder="验证器六位动态码（新账号留空）" maxlength="6"
                      inputmode="numeric" size="large" autocomplete="one-time-code" />
          </el-form-item>
          <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="onLogin">
            {{ loginKind === 'owner' ? '安全登录' : '登 录' }}
          </el-button>
        </el-form>
        <p class="tip">{{ loginKind === 'owner' ? '超级管理员使用密码和独立双重验证' : '普通管理员使用账号密码登录' }}</p>
      </template>

      <div v-else class="setup-panel">
        <div class="setup-badge">首次安全设置</div>
        <h2>绑定超级管理员 2FA</h2>
        <p class="setup-user">{{ setup.username }} · 每个超级管理员使用独立密钥</p>
        <ol class="setup-steps">
          <li>打开验证器（如 Microsoft Authenticator、腾讯身份验证器）。</li>
          <li>选择“手动输入密钥”，添加下面的密钥。</li>
          <li>输入验证器生成的六位动态码完成绑定。</li>
        </ol>
        <el-form label-position="top" @keyup.enter="onMfaSetup">
          <el-form-item label="绑定密钥（请勿转发）">
            <div class="secret-row">
              <el-input v-model="setup.secret" readonly />
              <el-button @click="copySecret">复制</el-button>
            </div>
          </el-form-item>
          <el-form-item label="六位动态码">
            <el-input v-model="setup.code" maxlength="6" inputmode="numeric" size="large"
                      placeholder="000000" autocomplete="one-time-code" />
          </el-form-item>
          <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="onMfaSetup">
            验证并进入后台
          </el-button>
        </el-form>
        <button type="button" class="back-login" @click="resetSetup">返回登录</button>
        <p class="expiry">绑定会话 10 分钟内有效，超时请重新登录。</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import type { AdminRole } from '@/api/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const loginKind = ref<AdminRole>('admin')
const form = reactive({ username: '', password: '', totpCode: '' })
const loading = ref(false)
const setupRequired = ref(false)
const setup = reactive({ setupToken: '', secret: '', otpauthUrl: '', username: '', code: '' })

const switchKind = (kind: AdminRole) => {
  loginKind.value = kind
  form.totpCode = ''
}

const destination = () => (route.query.redirect as string) || '/'

const onLogin = async () => {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const result = await auth.login(form.username, form.password, loginKind.value, form.totpCode)
    if ('mfa_setup_required' in result) {
      setup.setupToken = result.setup_token
      setup.secret = result.secret
      setup.otpauthUrl = result.otpauth_url
      setup.username = result.admin.username
      setup.code = ''
      setupRequired.value = true
      return
    }
    ElMessage.success('登录成功')
    router.push(destination())
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const onMfaSetup = async () => {
  if (!/^\d{6}$/.test(setup.code)) {
    ElMessage.warning('请输入验证器中的六位动态码')
    return
  }
  loading.value = true
  try {
    await auth.completeMfaSetup(setup.setupToken, setup.code)
    ElMessage.success('双重验证绑定成功')
    router.push(destination())
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const copySecret = async () => {
  try {
    await navigator.clipboard.writeText(setup.secret)
    ElMessage.success('密钥已复制，请仅粘贴到自己的验证器')
  } catch {
    ElMessage.warning('复制失败，请手动选择密钥复制')
  }
}

const resetSetup = () => {
  setupRequired.value = false
  setup.setupToken = ''
  setup.secret = ''
  setup.code = ''
  form.password = ''
  form.totpCode = ''
}
</script>

<style scoped>
.login-page { min-height: 100%; display: flex; align-items: center; justify-content: center; padding: 24px 16px; box-sizing: border-box; background: radial-gradient(45% 40% at 50% 0%, var(--el-color-primary-light-9), transparent 70%), var(--app-bg); }
.login-card { width: 100%; max-width: 400px; box-sizing: border-box; background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter); border-radius: 16px; padding: 36px 32px 28px; box-shadow: 0 24px 70px rgba(0, 0, 0, 0.08); }
.login-header { text-align: center; margin-bottom: 24px; }
.logo { width: 60px; height: 60px; margin: 0 auto 14px; border-radius: 50%; background: var(--el-color-primary); color: #fff; font-size: 30px; font-weight: 800; display: flex; align-items: center; justify-content: center; }
h1 { font-size: 22px; color: var(--el-text-color-primary); font-weight: 800; }
.sub { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 6px; letter-spacing: 1px; }
.login-kind { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; padding: 4px; margin-bottom: 22px; border-radius: 10px; background: var(--el-fill-color-light); }
.login-kind button { border: 0; border-radius: 7px; padding: 9px 6px; background: transparent; color: var(--el-text-color-secondary); cursor: pointer; font-size: 14px; }
.login-kind button.active { background: var(--el-bg-color); color: var(--el-color-primary); font-weight: 600; box-shadow: 0 1px 4px rgba(0, 0, 0, .08); }
.login-btn { width: 100%; margin-top: 6px; border-radius: 9999px; font-weight: 700; }
.tip { font-size: 12px; color: var(--el-text-color-secondary); text-align: center; margin-top: 16px; }
.setup-badge { color: var(--el-color-primary); font-size: 11px; font-weight: 700; letter-spacing: 1px; margin-bottom: 7px; }
.setup-panel h2 { color: var(--el-text-color-primary); font-size: 20px; }
.setup-user { color: var(--el-text-color-secondary); font-size: 13px; margin-top: 7px; overflow-wrap: anywhere; }
.setup-steps { color: var(--el-text-color-regular); font-size: 13px; line-height: 1.8; padding-left: 20px; margin: 18px 0 22px; }
.secret-row { display: flex; gap: 8px; width: 100%; }
.secret-row .el-input { font-family: monospace; }
.back-login { display: block; margin: 16px auto 0; border: 0; background: none; color: var(--el-color-primary); cursor: pointer; }
.expiry { color: var(--el-text-color-secondary); font-size: 11px; text-align: center; margin-top: 12px; }
html.dark .login-card { box-shadow: 0 24px 70px rgba(0, 0, 0, 0.6); }
@media (max-width: 480px) { .login-card { padding: 28px 20px 22px; } }
</style>
