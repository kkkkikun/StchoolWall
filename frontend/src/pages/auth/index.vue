<template>
  <view class="page-auth" :class="themeClass">
    <CustomNavBar :showBack="true" :border="false" background="var(--bg-page)" />

    <view class="auth-body">
      <!-- 1. 品牌区 -->
      <view class="brand">
        <view class="brand-mark">
          <image class="brand-logo" :src="ICONS['banner-grad']" mode="aspectFit" />
        </view>
        <text class="brand-name">鄂应墙</text>
        <text class="brand-slogan">校园信息聚合平台</text>
      </view>

      <!-- 2. 登录 / 注册 分段切换 -->
      <view class="auth-tabs">
        <view class="auth-tab" :class="{ on: authMode === 'login' }" @tap="switchMode('login')">
          <text class="auth-tab-text">登录</text>
          <view v-if="authMode === 'login'" class="auth-tab-bar" />
        </view>
        <view class="auth-tab" :class="{ on: authMode === 'register' }" @tap="switchMode('register')">
          <text class="auth-tab-text">注册</text>
          <view v-if="authMode === 'register'" class="auth-tab-bar" />
        </view>
      </view>

      <!-- 3. 表单 -->
      <view class="auth-form">
        <text class="auth-hint">{{ hintText }}</text>

        <view class="auth-field">
          <input
            v-model="form.username"
            class="auth-input"
            :maxlength="20"
            placeholder="用户名（2-20 字）"
            placeholder-class="ph"
          />
        </view>

        <view v-if="authMode === 'recovery'" class="auth-field">
          <input
            v-model="recoveryCode"
            class="auth-input"
            :maxlength="64"
            placeholder="离线找回码（请勿转发）"
            placeholder-class="ph"
          />
        </view>

        <view class="auth-field">
          <input
            v-model="form.password"
            class="auth-input auth-input-password"
            :maxlength="64"
            :password="!showPassword"
            :placeholder="authMode === 'login' ? '登录密码' : '设置密码（至少 10 位）'"
            placeholder-class="ph"
          />
          <view class="auth-eye-btn" @tap="togglePassword">
            <image class="auth-eye" :src="eyeSrc" mode="aspectFit" />
          </view>
        </view>

        <!-- 校验/网络错误就地提示，不打断用户输入 -->
        <view v-if="errorText" class="auth-error">
          <text class="auth-error-text">{{ errorText }}</text>
        </view>

        <view class="auth-submit" :class="{ saving: saving }" @tap="submit">
          <text class="auth-submit-text">{{ saving ? '处理中…' : submitLabel }}</text>
        </view>

        <!-- 4. 微信登录 -->
        <view v-if="showWechat" class="auth-alt">
          <view class="auth-divider">
            <view class="auth-divider-line" />
            <text class="auth-divider-text">或</text>
            <view class="auth-divider-line" />
          </view>
          <view class="auth-wechat" @tap="doWechatLogin">
            <text class="auth-wechat-text">{{ wechatLabel }}</text>
          </view>
        </view>

        <!-- 5. 辅助入口 -->
        <view class="auth-links">
          <text class="auth-link" @tap="toggleRecovery">{{ authMode === 'recovery' ? '返回登录' : '忘记密码' }}</text>
        </view>

        <text class="auth-note">登录即代表同意《鄂应墙社区规范》与《用户协议》</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useTheme } from '@/utils/theme'
import { onLoad } from '@dcloudio/uni-app'
import CustomNavBar from '@/components/custom-nav-bar.vue'
import {
  webLogin, register, storeLoginSession, recoverPassword,
} from '@/api/auth'
import type { LoginResponse } from '@/api/auth'
import { beginWechatOAuth, clientType } from '@/utils/platform-auth'
import { tokenStorage } from '@/utils/storage'
import { friendlyNetworkError } from '@/utils/errors'
import { ICONS } from '@/utils/icons'

const { themeClass, mode: themeMode } = useTheme()

type AuthMode = 'login' | 'register' | 'recovery'

const authMode = ref<AuthMode>('login')
const saving = ref(false)
const showPassword = ref(false)
const errorText = ref('')
const recoveryCode = ref('')
const form = ref({ username: '', password: '' })

const IS_WEB = clientType() === 'web'
const WECHAT_MP_APP_ID = import.meta.env.VITE_WECHAT_MP_APP_ID || ''

const hintText = computed(() => {
  if (authMode.value === 'register') return '注册密码至少 10 位'
  if (authMode.value === 'recovery') return '使用离线找回码重置密码'
  return '使用已注册的账号登录'
})

const submitLabel = computed(() => {
  if (authMode.value === 'register') return '注册并登录'
  if (authMode.value === 'recovery') return '重置密码'
  return '进入鄂应墙'
})

const showWechat = computed(() => IS_WEB && !!WECHAT_MP_APP_ID)
const wechatLabel = '微信登录（公众号）'

/**
 * 显示/隐藏密码的图标：SVG 描边色固化在文件里，无法用 CSS 染色，
 * 因此按主题挑变体——亮色用中性灰（#666 落在浅灰输入框上 5.7:1），
 * 暗色用反白（落在深灰输入框上 15.8:1）；两者都过非文本 3:1。
 */
const eyeSrc = computed(() => {
  const base = showPassword.value ? 'eye-off' : 'eye-open'
  return themeMode.value === 'dark'
    ? `/static/icons/common/${base}-inverse.svg`
    : `/static/icons/common/${base}.svg`
})

/**
 * 登录/注册成功响应的最小运行时校验：会话必需字段缺失视为异常响应，
 * 不落地不完整会话（对照 utils/storage.ts 的 SessionData 契约）
 * 与 utils/storage.ts 的 StoredUserInfo['role'] 保持一致，不得自行扩大取值
 */
const VALID_SESSION_ROLES = ['guest', 'student', 'admin'] as const

const isValidSessionResponse = (res: LoginResponse | null | undefined): res is LoginResponse =>
  !!res &&
  typeof res.access_token === 'string' && res.access_token.length > 0 &&
  (VALID_SESSION_ROLES as readonly string[]).includes(res.role as string) &&
  !!res.user_info &&
  typeof res.user_info.id === 'string' && res.user_info.id.length > 0 &&
  typeof res.user_info.nickname === 'string' &&
  typeof res.user_info.is_verified === 'boolean'

/** 底层网络错误翻译成可重试的中文提示；后端明确返回的错误原样保留 */
const friendlyLoginError = (e: unknown): string =>
  friendlyNetworkError(e, '登录失败，请稍后重试')

onLoad(() => {
  // 已登录用户无需再登一次，直接退回上一页
  if (tokenStorage.isLoggedIn()) {
    uni.navigateBack()
  }
})

/** 模式切换：请求进行中锁定，防止在途请求期间换模式造成语义错乱或绕过防重 */
const switchMode = (next: Exclude<AuthMode, 'recovery'>) => {
  if (saving.value) return
  errorText.value = ''
  recoveryCode.value = ''
  authMode.value = next
}

const toggleRecovery = () => {
  if (saving.value) return
  errorText.value = ''
  recoveryCode.value = ''
  authMode.value = authMode.value === 'recovery' ? 'login' : 'recovery'
}

const togglePassword = () => {
  showPassword.value = !showPassword.value
}

/** 登录成功后回到来源页；无来源页（如直接打开本页）则回到「我的」 */
const backAfterLogin = () => {
  const stack = getCurrentPages()
  if (stack.length > 1) {
    uni.navigateBack()
  } else {
    uni.reLaunch({ url: '/pages/mine/index' })
  }
}

const submit = async () => {
  // 请求进行中直接忽略后续点击：登录/注册/找回共用本入口，防重复提交
  if (saving.value) return
  const username = form.value.username.trim()
  const password = form.value.password
  const needLong = authMode.value === 'register' || authMode.value === 'recovery'
  if (username.length < 2 || password.length < (needLong ? 10 : 6)) {
    errorText.value = needLong ? '用户名至少 2 字，密码至少 10 位' : '请输入有效账号和密码'
    return
  }
  errorText.value = ''
  saving.value = true
  try {
    if (authMode.value === 'recovery') {
      if (!recoveryCode.value.trim()) throw new Error('请输入离线保存的找回码')
      await recoverPassword(username, recoveryCode.value.trim(), password)
      recoveryCode.value = ''
      form.value.password = ''
      authMode.value = 'login'
      uni.showToast({ title: '密码已重置，请登录', icon: 'success' })
      return
    }
    const res = await (authMode.value === 'register'
      ? register(username, password)
      : webLogin(username, password))
    if (!isValidSessionResponse(res)) throw new Error('登录响应异常，请稍后重试')
    await storeLoginSession(res)
    uni.showToast({ title: `欢迎，${res.user_info.nickname}`, icon: 'success' })
    backAfterLogin()
  } catch (e) {
    errorText.value = friendlyLoginError(e)
  } finally {
    saving.value = false
  }
}

/** 公众号网页授权：跳转微信换取 code，回跳 oauth-callback 页完成登录 */
const doWechatLogin = () => {
  try {
    beginWechatOAuth(WECHAT_MP_APP_ID)
  } catch (error) {
    errorText.value = (error as Error).message
  }
}
</script>

<style scoped>
.page-auth {
  min-height: 100vh;
  background: var(--bg-page);
}

.auth-body {
  padding: 0 44rpx calc(48rpx + env(safe-area-inset-bottom));
  /* 宽屏（桌面 H5）下不让表单拉满整屏，保持手机端的窄栏观感 */
  max-width: 480px;
  margin: 0 auto;
}

/* 1. 品牌区 */
.brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 56rpx 0 48rpx;
}
.brand-mark {
  width: 128rpx;
  height: 128rpx;
  border-radius: 34rpx;
  background: var(--primary-gradient);
  display: flex;
  align-items: center;
  justify-content: center;
}
.brand-logo {
  width: 74rpx;
  height: 74rpx;
}
.brand-name {
  margin-top: 26rpx;
  font-size: 46rpx;
  font-weight: 800;
  color: var(--text-1);
  letter-spacing: 4rpx;
}
.brand-slogan {
  margin-top: 10rpx;
  font-size: 24rpx;
  color: var(--text-3);
}

/* 2. 分段切换（X 顶部导航：粗体 + 蓝色指示条） */
.auth-tabs {
  display: flex;
  border-bottom: 1rpx solid var(--border-light);
}
.auth-tab {
  flex: 1;
  position: relative;
  padding: 20rpx 0 18rpx;
  text-align: center;
}
.auth-tab-text {
  font-size: 32rpx;
  color: var(--text-2);
}
.auth-tab.on .auth-tab-text {
  color: var(--text-1);
  font-weight: 700;
}
.auth-tab-bar {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 60rpx;
  height: 4rpx;
  border-radius: 4rpx;
  background: var(--primary);
}

/* 3. 表单 */
.auth-form {
  padding-top: 36rpx;
}
.auth-hint {
  display: block;
  font-size: 24rpx;
  color: var(--text-3);
  margin-bottom: 8rpx;
}
.auth-field {
  position: relative;
  margin-top: 22rpx;
}
.auth-input {
  height: 92rpx;
  border-radius: 46rpx;
  background: var(--bg-card-2);
  padding: 0 34rpx;
  font-size: 30rpx;
  color: var(--text-1);
  box-sizing: border-box;
}
.auth-input-password {
  padding-right: 88rpx;
}
/* 容器承载点击区（64rpx ≈33px），图形本身保持 36rpx 不放大 */
.auth-eye-btn {
  position: absolute;
  right: 14rpx;
  top: 50%;
  margin-top: -32rpx;
  width: 64rpx;
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.auth-eye {
  width: 36rpx;
  height: 36rpx;
}

.auth-error {
  margin-top: 20rpx;
  padding: 18rpx 24rpx;
  border-radius: var(--radius-inner);
  background: var(--danger-soft);
}
.auth-error-text {
  font-size: 24rpx;
  color: var(--danger-strong);
}

.auth-submit {
  margin-top: 36rpx;
  height: 92rpx;
  border-radius: var(--radius-btn);
  background: var(--primary-fill);
  display: flex;
  align-items: center;
  justify-content: center;
}
.auth-submit.saving {
  opacity: 0.6;
}
.auth-submit-text {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--text-inverse);
}

/* 4. 微信登录 */
.auth-alt {
  margin-top: 12rpx;
}
.auth-divider {
  display: flex;
  align-items: center;
  gap: 20rpx;
  margin-top: 32rpx;
}
.auth-divider-line {
  flex: 1;
  height: 1rpx;
  background: var(--border-light);
}
.auth-divider-text {
  font-size: 24rpx;
  color: var(--text-3);
}
.auth-wechat {
  margin-top: 26rpx;
  height: 88rpx;
  border-radius: var(--radius-btn);
  border: 1rpx solid var(--border-strong);
  display: flex;
  align-items: center;
  justify-content: center;
}
.auth-wechat-text {
  font-size: 30rpx;
  font-weight: 600;
  color: var(--text-1);
}

/* 5. 辅助入口 */
.auth-links {
  margin-top: 36rpx;
  display: flex;
  justify-content: center;
}
.auth-link {
  font-size: 26rpx;
  color: var(--text-2);
  display: inline-flex;
  align-items: center;
  /* 点击区 ≥64rpx（≈33px） */
  min-height: 64rpx;
}
.auth-note {
  display: block;
  margin-top: 28rpx;
  text-align: center;
  font-size: 22rpx;
  color: var(--text-4);
}
</style>
