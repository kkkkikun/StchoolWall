<template>
  <view class="page-settings" :class="themeClass">
    <!-- 账号卡片 -->
    <view class="account-card">
      <view class="avatar" :style="{ background: avatarColor }">
        <text class="avatar-letter">{{ avatarLetter }}</text>
      </view>
      <view class="account-meta">
        <view class="name-row">
          <text class="nickname">{{ user.nickname }}</text>
          <text v-if="user.is_verified" class="v-badge">已认证</text>
        </view>
        <text class="role-text">{{ roleText }}</text>
      </view>
    </view>

    <!-- 外观 -->
    <view class="group-card">
      <view class="group-title"><text>外观</text></view>
      <view class="cell">
        <view class="cell-left">
          <image class="cell-icon-svg" :src="ICONS['moon']" mode="aspectFit" />
          <text class="cell-title">深色模式</text>
        </view>
        <switch :checked="mode === 'dark'" color="#c2455c" @change="onToggleTheme" />
      </view>
    </view>

    <!-- 通用设置 -->
    <view class="group-card">
      <view class="group-title"><text>通用</text></view>
      <view class="cell" @tap="onClearCache">
        <view class="cell-left">
          <image class="cell-icon-svg" :src="ICONS['broom']" mode="aspectFit" />
          <text class="cell-title">清除缓存</text>
        </view>
        <text class="cell-value">{{ cacheSize }}</text>
      </view>
      <view class="cell" @tap="goInfo('community')">
        <view class="cell-left">
          <image class="cell-icon-svg" :src="ICONS['shield']" mode="aspectFit" />
          <text class="cell-title">社区规范</text>
        </view>
        <image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
      <view class="cell" @tap="goInfo('privacy')">
        <view class="cell-left">
          <image class="cell-icon-svg" :src="ICONS['lock']" mode="aspectFit" />
          <text class="cell-title">隐私政策</text>
        </view>
        <image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
      <view class="cell" @tap="goInfo('agreement')">
        <view class="cell-left">
          <image class="cell-icon-svg" :src="ICONS['edit']" mode="aspectFit" />
          <text class="cell-title">用户协议</text>
        </view>
        <image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
      <view class="cell" @tap="goInfo('invite')">
        <view class="cell-left">
          <image class="cell-icon-svg" :src="ICONS['invite']" mode="aspectFit" />
          <text class="cell-title">邀请校友</text>
        </view>
        <image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
      <view class="cell" @tap="goInfo('about')">
        <view class="cell-left">
          <image class="cell-icon-svg" :src="ICONS['about']" mode="aspectFit" />
          <text class="cell-title">关于我们</text>
        </view>
        <text class="cell-value">v1.0.0</text>
      </view>
      <view class="cell" @tap="goInfo('contact')">
        <view class="cell-left">
          <image class="cell-icon-svg" :src="ICONS['contact']" mode="aspectFit" />
          <text class="cell-title">联系我们</text>
        </view>
        <image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
    </view>

    <!-- 账号操作 -->
    <view class="group-card">
      <view class="group-title"><text>账号</text></view>
      <view v-if="loggedIn" class="cell" @tap="onRecoveryCodes">
        <view class="cell-left"><image class="cell-icon-svg" :src="ICONS['key']" mode="aspectFit" /><text class="cell-title">生成离线找回码</text></view><image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
      <view v-if="loggedIn" class="cell" @tap="goBlocks">
        <view class="cell-left"><image class="cell-icon-svg" :src="ICONS['block']" mode="aspectFit" /><text class="cell-title">屏蔽的用户</text></view><image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
      <view v-if="loggedIn" class="cell" @tap="goAppeals">
        <view class="cell-left"><image class="cell-icon-svg" :src="ICONS['appeal']" mode="aspectFit" /><text class="cell-title">申诉与处理记录</text></view><image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
      <view v-if="loggedIn" class="cell" @tap="onSessions">
        <view class="cell-left"><image class="cell-icon-svg" :src="ICONS['device']" mode="aspectFit" /><text class="cell-title">登录设备与会话</text></view><image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
      <view v-if="loggedIn" class="cell" @tap="onCreatePairing">
        <view class="cell-left"><image class="cell-icon-svg" :src="ICONS['link']" mode="aspectFit" /><text class="cell-title">生成跨端配对码</text></view><image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
      <view v-if="loggedIn" class="cell" @tap="onClaimPairing">
        <view class="cell-left"><image class="cell-icon-svg" :src="ICONS['key']" mode="aspectFit" /><text class="cell-title">输入原账号配对码</text></view><image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
      <view v-if="loggedIn" class="cell" @tap="onChangePassword">
        <view class="cell-left">
          <image class="cell-icon-svg" :src="ICONS['key']" mode="aspectFit" />
          <text class="cell-title">修改密码</text>
        </view>
        <image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
      <view v-if="loggedIn" class="cell danger-cell" @tap="onDeleteAccount">
        <view class="cell-left">
          <image class="cell-icon-svg" :src="ICONS['trash']" mode="aspectFit" />
          <text class="cell-title danger-text">注销账号</text>
        </view>
        <image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
      <view v-if="loggedIn" class="cell danger-cell" @tap="onLogout">
        <view class="cell-left">
          <image class="cell-icon-svg" :src="ICONS['logout']" mode="aspectFit" />
          <text class="cell-title danger-text">退出登录</text>
        </view>
      </view>
      <view v-else class="cell" @tap="goLogin">
        <view class="cell-left">
          <image class="cell-icon-svg" :src="ICONS['key']" mode="aspectFit" />
          <text class="cell-title">去登录</text>
        </view>
        <image class="arrow" :src="ICONS['arrow-right']" mode="aspectFit" />
      </view>
    </view>

    <!-- 底部版权 -->
    <text class="footer-text">鄂应墙 · 校园信息撮合平台</text>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { avatarColor as avatarColorOf } from '@/utils/avatar'
import { useTheme } from '@/utils/theme'
import { onShow } from '@dcloudio/uni-app'
import { tokenStorage, userStorage } from '@/utils/storage'
import { logout, getSessions, revokeSession, createPairing, claimPairing, generateRecoveryCodes } from '@/api/auth'
import { get, post, put } from '@/utils/request'
import { ICONS } from '@/utils/icons'

const { themeClass, mode, setThemeMode } = useTheme()

const onToggleTheme = (e: any) => setThemeMode(e.detail.value ? 'dark' : 'light')

const loggedIn = ref(tokenStorage.isLoggedIn())
const localInfo = userStorage.getUserInfo()
const user = ref({
  nickname: localInfo?.nickname || '未登录',
  is_verified: !!localInfo?.is_verified,
})
const role = ref<'guest' | 'student' | 'admin'>((localInfo?.role as 'guest' | 'student' | 'admin') || 'guest')
const cacheSize = ref('计算中…')

const avatarLetter = computed(() => (user.value.nickname || '?').slice(0, 1))
const avatarColor = computed(() => avatarColorOf(user.value.nickname))

const roleText = computed(() => {
  if (!loggedIn.value) return '游客模式 · 仅可浏览'
  if (role.value === 'admin') return '管理员'
  if (role.value === 'student') return '已认证学生'
  return '游客'
})

const calcCache = () => {
  try {
    const info = uni.getStorageInfoSync()
    cacheSize.value = `${(info.currentSize / 1024).toFixed(1)} MB`
  } catch {
    cacheSize.value = '—'
  }
}

const onClearCache = () => {
  uni.showModal({
    title: '清除缓存',
    content: '将清除图片缓存等本地数据（不影响登录态和草稿），确定吗？',
    success: (r) => {
      if (!r.confirm) return
      try {
        const protectedKeys = new Set(['access_token', 'refresh_token', 'sw_android_refresh_encrypted',
          'user_info', 'post_draft', 'schoolwall_publish_draft', 'theme-mode'])
        for (const key of uni.getStorageInfoSync().keys) {
          if (!protectedKeys.has(key)) uni.removeStorageSync(key)
        }
      } catch { /* 忽略 */ }
      calcCache()
      uni.showToast({ title: '已清除', icon: 'success' })
    },
  })
}

const onLogout = () => {
  uni.showModal({
    title: '退出登录',
    content: `确定退出「${user.value.nickname}」吗？`,
    confirmText: '退出',
    confirmColor: '#c2455c',
    success: async (r) => {
      if (!r.confirm) return
      try { await logout() }
      catch (error) { uni.showToast({ title: (error as Error).message || '退出失败，请重试', icon: 'none' }); return }
      loggedIn.value = false
      user.value = { nickname: '未登录', is_verified: false }
      uni.showToast({ title: '已退出', icon: 'success' })
      setTimeout(() => uni.navigateBack(), 600)
    },
  })
}

const goLogin = () => {
  uni.navigateBack()
  uni.showToast({ title: '请到「我的」页登录', icon: 'none' })
}

const goInfo = (type: 'community' | 'invite' | 'about' | 'contact' | 'privacy' | 'agreement') => {
  uni.navigateTo({ url: `/pages/info/index?type=${type}` })
}


const promptText = (title: string, placeholder: string): Promise<string | null> => {
  return new Promise((resolve) => {
    uni.showModal({
      title,
      editable: true,
      placeholderText: placeholder,
      success: (r) => {
        if (!r.confirm) return resolve(null)
        resolve((r as any).content || '')
      },
      fail: () => resolve(null),
    })
  })
}

const goBlocks = () => uni.navigateTo({ url: '/pages/blocks/index' })
const goAppeals = () => uni.navigateTo({ url: '/pages/appeals/index' })
const onRecoveryCodes = () => {
  uni.showModal({ title: '生成离线找回码', content: '请先确认近期已登录。生成后旧码失效，新码仅显示一次；请抄写到安全的离线位置，勿发送给任何人。',
    success: async (result) => {
      if (!result.confirm) return
      try {
        const data = await generateRecoveryCodes()
        uni.showModal({ title: '找回码（仅显示一次）',
          content: data.codes.join('\n') + '\n每个码只能使用一次，请离线妥善保存。',
          showCancel: false, confirmText: '我已保存' })
      } catch (error) { uni.showToast({ title: (error as Error).message, icon: 'none' }) }
    },
  })
}

const onSessions = async () => {
  try {
    const data = await getSessions()
    if (!data.items.length) return uni.showToast({ title: '暂无有效会话', icon: 'none' })
    uni.showActionSheet({
      itemList: data.items.slice(0, 6).map((item) =>
        `${item.client_type} · ${item.created_at.slice(0, 16).replace('T', ' ')}${item.id === tokenStorage.getSessionId() ? '（当前）' : ''}`),
      success: async ({ tapIndex }) => {
        const item = data.items[tapIndex]
        uni.showModal({ title: '撤销登录会话', content: '此设备将需要重新登录，确定撤销吗？',
          success: async (result) => {
            if (!result.confirm) return
            try {
              await revokeSession(item.id)
              if (item.id === tokenStorage.getSessionId()) { userStorage.clear(); await refreshAuth() }
              uni.showToast({ title: '会话已撤销', icon: 'success' })
            } catch (error) { uni.showToast({ title: (error as Error).message, icon: 'none' }) }
          },
        })
      },
    })
  } catch (error) { uni.showToast({ title: (error as Error).message, icon: 'none' }) }
}
const onCreatePairing = async () => {
  try {
    const result = await createPairing()
    uni.showModal({ title: '跨端配对码', content: `${result.code}\n10 分钟内在另一端新账号的设置中输入。此码可绑定登录身份，请勿转发给他人。`, showCancel: false })
  } catch (error) { uni.showToast({ title: (error as Error).message, icon: 'none' }) }
}
const onClaimPairing = async () => {
  const code = await promptText('绑定原账号', '输入原账号生成的配对码')
  if (!code) return
  try {
    await claimPairing(code.trim())
    await refreshAuth()
    uni.showToast({ title: '已绑定原账号', icon: 'success' })
  } catch (error) { uni.showToast({ title: (error as Error).message, icon: 'none' }) }
}

const onChangePassword = async () => {
  if (!loggedIn.value) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  const oldPwd = await promptText('修改密码', '请输入原密码')
  if (oldPwd === null) return
  const newPwd = await promptText('修改密码', '请输入新密码（至少 10 位）')
  if (newPwd === null) return
  if (newPwd.length < 10) {
    uni.showToast({ title: '新密码至少 10 位', icon: 'none' })
    return
  }
  try {
    await put('/user/password', { old_password: oldPwd, new_password: newPwd })
    uni.showToast({ title: '密码已更新，请重新登录', icon: 'success' })
    userStorage.clear()
    loggedIn.value = false
    setTimeout(() => uni.navigateBack(), 700)
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '修改失败', icon: 'none' })
  }
}

const onDeleteAccount = async () => {
  if (!loggedIn.value) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  const r = await new Promise<boolean>((resolve) => {
    uni.showModal({
      title: '注销账号',
      content: '注销后无法恢复，历史帖子将显示为「已注销用户」。确定继续吗？',
      confirmText: '确认注销',
      confirmColor: '#c2455c',
      success: (res) => resolve(!!res.confirm),
      fail: () => resolve(false),
    })
  })
  if (!r) return

  const pwd = await promptText('注销账号', '网页账号请输入密码；微信用户可留空')
  if (pwd === null) return
  try {
    await post('/user/account/deactivate', { password: pwd || null })
    uni.showToast({ title: '账号已注销', icon: 'success' })
    userStorage.clear()
    loggedIn.value = false
    setTimeout(() => uni.reLaunch({ url: '/pages/index/index' }), 700)
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '注销失败', icon: 'none' })
  }
}

const syncProfile = async () => {
  if (!tokenStorage.isLoggedIn()) return
  try {
    const p = await get<{ nickname?: string; is_verified?: boolean; role?: string }>('/user/profile')
    user.value = {
      nickname: p.nickname || user.value.nickname,
      is_verified: !!p.is_verified,
    }
    role.value = (p.role as 'guest' | 'student' | 'admin') || role.value
    const local = userStorage.getUserInfo()
    userStorage.setUserInfo({
      id: local?.id || '',
      nickname: p.nickname || local?.nickname || '未登录',
      role: (p.role as 'guest' | 'student' | 'admin') || (local?.role as 'guest' | 'student' | 'admin') || 'guest',
      is_verified: !!p.is_verified,
    })
  } catch { /* 忽略：未登录或网络异常时不覆盖现有状态 */ }
}

const refreshAuth = async () => {
  loggedIn.value = tokenStorage.isLoggedIn()
  const info = userStorage.getUserInfo()
  user.value = {
    nickname: info?.nickname || '未登录',
    is_verified: !!info?.is_verified,
  }
  role.value = info?.role || 'guest'
  calcCache()
  if (loggedIn.value) await syncProfile()
}

onShow(refreshAuth)

onMounted(() => {
  // H5 多标签页场景：切回该页时 onShow 不一定触发，补 focus/visibility 刷新登录态
  if (typeof window !== 'undefined') {
    window.addEventListener('focus', refreshAuth)
    document.addEventListener('visibilitychange', refreshAuth)
  }
})

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('focus', refreshAuth)
    document.removeEventListener('visibilitychange', refreshAuth)
  }
})
</script>

<style scoped>
.page-settings {
  min-height: 100vh;
  background: var(--bg-page);
  padding: 24rpx 24rpx 60rpx;
}

.account-card {
  /* 主题B（X）：设置页账号行为扁平卡（不再整块品牌色） */
  background: var(--bg-card);
  border: 1rpx solid var(--border-light);
  border-radius: var(--radius-card);
  padding: 36rpx 32rpx;
  display: flex;
  align-items: center;
}
.avatar {
  width: 110rpx;
  height: 110rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 6rpx rgba(255, 255, 255, 0.35);
}
.avatar-letter { font-size: 52rpx; font-weight: bold; color: var(--on-avatar); }
.account-meta { margin-left: 26rpx; flex: 1; }
.name-row { display: flex; align-items: center; gap: 12rpx; }
.nickname { color: var(--text-1); font-size: 36rpx; font-weight: 700; }
.v-badge { font-size: 22rpx; color: var(--primary-text); font-weight: 600; }
.role-text { color: var(--text-2); font-size: 24rpx; margin-top: 8rpx; }

.group-card {
  background: var(--bg-card);
  border-radius: var(--radius-card);
  margin-top: 24rpx;
  padding: 0 32rpx;
}
.group-title {
  font-size: 24rpx;
  color: var(--text-3);
  padding: 28rpx 0 8rpx;
}
.cell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 30rpx 0;
  border-bottom: 1rpx solid var(--border-light);
}
.group-card .cell:last-child { border-bottom: none; }
.cell-left { display: flex; align-items: center; }
.cell-icon { font-size: 36rpx; margin-right: 22rpx; }
.cell-icon-svg { width: 36rpx; height: 36rpx; margin-right: 22rpx; flex-shrink: 0; }
.cell-title { font-size: 29rpx; color: var(--text-1); }
.cell-value { font-size: 24rpx; color: var(--text-3); }
.arrow { width: 26rpx; height: 26rpx; flex-shrink: 0; }
.danger-cell .cell-title.danger-text { color: var(--primary-text); }

.footer-text {
  display: block;
  text-align: center;
  color: var(--text-3);
  font-size: 22rpx;
  margin-top: 48rpx;
}
</style>
