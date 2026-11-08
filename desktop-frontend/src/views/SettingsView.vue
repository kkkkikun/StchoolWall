<script setup lang="ts">
/**
 * 账号设置：资料修改、学生证认证、登录设备、跨端配对、密码与账号安全、
 * 内容管理（屏蔽 / 申诉）、外观（深色模式）、意见反馈与信息页入口。
 */
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  changePassword,
  claimPairing,
  createPairing,
  deactivateAccount,
  getSessions,
  revokeAllSessions,
  revokeSession,
  setLoginPassword,
} from '@/api/auth'
import type { SessionItem } from '@/api/auth'
import { getMyProfile, updateMyProfile } from '@/api/user'
import type { MyProfile } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

const auth = useAuthStore()
const router = useRouter()
const theme = useThemeStore()

// 反馈弹窗带上传、诊断等交互，懒加载避免把 Element Plus 表单组件拖进首屏包
const FeedbackDialog = defineAsyncComponent(() => import('@/components/FeedbackDialog.vue'))

const feedbackOpen = ref(false)

const profile = ref<MyProfile | null>(null)
const sessions = ref<SessionItem[]>([])
const nickname = ref('')
const bio = ref('')
const wechatId = ref('')
const saving = ref(false)

/** 修改密码 / 设置登录密码的表单。 */
const passwordOpen = ref(false)
/** false = 修改已有密码；true = 该账号还没有网页密码，需要设置一个。 */
const passwordMode = ref<'change' | 'set'>('change')
const currentPassword = ref('')
const loginName = ref('')
const newPassword = ref('')
const passwordSaving = ref(false)

/** 跨端配对码。 */
const pairingOpen = ref(false)
const pairingCode = ref('')
const pairingExpires = ref(0)
const pairingSaving = ref(false)
const claimCode = ref('')
const claimSaving = ref(false)

/** 注销账号。 */
const deactivateOpen = ref(false)
const deactivatePassword = ref('')
const deactivateSaving = ref(false)

const ROLE_LABELS: Record<string, string> = {
  guest: '游客',
  student: '已认证学生',
  admin: '管理员',
}

const roleLabel = computed(() => ROLE_LABELS[auth.role] ?? (auth.role || '游客'))

/** 配对码剩余有效秒数（后端固定 10 分钟）。 */
const pairingCountdown = computed(() => {
  const seconds = pairingExpires.value - Math.floor(Date.now() / 1000)
  return seconds > 0 ? Math.ceil(seconds / 60) : 0
})

async function load(): Promise<void> {
  const info = await getMyProfile().catch(() => null)
  if (info) {
    profile.value = info
    nickname.value = info.nickname
    bio.value = info.bio
    wechatId.value = info.wechatId
  }
  sessions.value = (await getSessions().catch(() => ({ items: [] }))).items
}

async function save(): Promise<void> {
  saving.value = true
  try {
    await updateMyProfile({ nickname: nickname.value, bio: bio.value, wechat_id: wechatId.value })
    ElMessage.success('资料已提交，审核通过后生效')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function revoke(item: SessionItem): Promise<void> {
  await revokeSession(item.id)
  ElMessage.success('已下线该设备')
  await load()
}

/**
 * 下线全部其它设备。
 *
 * 后端的 revoke-all 会撤销该账号的全部会话（含当前设备），
 * 因此当前设备的会话也会一并失效，这里提示用户重新登录。
 */
async function revokeAll(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '将下线该账号在所有设备上的登录状态，当前设备也需要重新登录。确定继续吗？',
      '下线全部其它设备',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await revokeAllSessions()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '操作失败')
    return
  }
  ElMessage.success('已下线全部设备，请重新登录')
  // revoke-all 已撤销当前设备的会话，再调 /auth/logout 会 401，
  // 因此只清本地会话态。
  auth.clear()
  router.push({ name: 'login' })
}

/**
 * 修改密码。
 *
 * 已有网页密码的账号走 PUT /user/password（需校验原密码）；
 * 还没有网页密码的账号（如仅用微信登录注册的）走 POST /auth/password 设置密码。
 * 两条路径成功后后端都会撤销全部会话，因此提示用户重新登录。
 */
async function submitPassword(): Promise<void> {
  if (newPassword.value.length < 10) {
    ElMessage.error('新密码至少 10 位')
    return
  }
  passwordSaving.value = true
  try {
    if (passwordMode.value === 'change') {
      if (!currentPassword.value) {
        ElMessage.error('请输入当前密码')
        return
      }
      await changePassword(currentPassword.value, newPassword.value)
    } else {
      if (!loginName.value.trim()) {
        ElMessage.error('请输入登录名')
        return
      }
      await setLoginPassword(loginName.value.trim(), newPassword.value)
    }
    passwordOpen.value = false
    currentPassword.value = ''
    loginName.value = ''
    newPassword.value = ''
    ElMessage.success('密码已更新，请重新登录')
    // 后端改密后会撤销全部会话，此时再调 /auth/logout 会 401，
    // 因此只清本地会话态并回到登录页。
    auth.clear()
    router.push({ name: 'login' })
  } catch (error) {
    const message = error instanceof Error ? error.message : '密码修改失败'
    // 账号还没有网页密码时，后端提示「当前账号未设置网页密码」，改为走设置密码路径
    if (passwordMode.value === 'change' && message.includes('未设置网页密码')) {
      passwordMode.value = 'set'
      ElMessage.warning('该账号还没有设置网页登录密码，请设置一个')
    } else {
      ElMessage.error(message)
    }
  } finally {
    passwordSaving.value = false
  }
}

async function generatePairing(): Promise<void> {
  pairingSaving.value = true
  try {
    const result = await createPairing()
    pairingCode.value = result.code
    pairingExpires.value = Math.floor(Date.now() / 1000) + result.expires_in
    ElMessage.success('配对码已生成，10 分钟内有效')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '生成失败')
  } finally {
    pairingSaving.value = false
  }
}

async function bindPairing(): Promise<void> {
  const code = claimCode.value.trim()
  if (!code) {
    ElMessage.error('请输入原账号生成的配对码')
    return
  }
  claimSaving.value = true
  try {
    const session = await claimPairing(code)
    auth.adopt(session)
    claimCode.value = ''
    pairingCode.value = ''
    ElMessage.success('已绑定原账号')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '绑定失败')
  } finally {
    claimSaving.value = false
  }
}

async function deactivate(): Promise<void> {
  deactivateSaving.value = true
  try {
    await deactivateAccount(deactivatePassword.value)
    deactivateOpen.value = false
    ElMessage.success('账号已注销')
    // 注销会撤销全部会话并把账号置为已注销态，再调 /auth/logout 会失败，
    // 因此只清本地会话态。
    auth.clear()
    router.push({ name: 'feed' })
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '注销失败')
  } finally {
    deactivateSaving.value = false
  }
}

async function logout(): Promise<void> {
  await auth.logout()
  ElMessage.success('已退出登录')
  router.push({ name: 'feed' })
}

onMounted(load)
</script>

<template>
  <div class="sw-settings">
    <section class="sw-card sw-settings__card">
      <h3 class="sw-card__title">个人资料</h3>
      <el-form label-width="88px" class="sw-settings__form">
        <el-form-item label="昵称">
          <el-input v-model="nickname" maxlength="50" />
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="bio" type="textarea" :rows="3" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="微信号">
          <el-input v-model="wechatId" maxlength="50" placeholder="仅交易类帖子对其他认证同学可见" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        </el-form-item>
      </el-form>
    </section>

    <section class="sw-card sw-settings__card">
      <h3 class="sw-card__title">学生证认证</h3>
      <p class="sw-muted">
        通过人工核对学生证开通校园发帖与互动。当前状态：{{ profile?.isVerified ? '已认证' : '未认证' }}。
      </p>
      <el-button class="sw-settings__action" @click="router.push({ name: 'verify' })">
        前往认证 / 查看进度
      </el-button>
    </section>

    <section class="sw-card sw-settings__card">
      <h3 class="sw-card__title">登录设备</h3>
      <ul class="sw-settings__sessions">
        <li v-for="item in sessions" :key="item.id" class="sw-settings__session">
          <span>{{ item.client_type }}</span>
          <span class="sw-muted">{{ item.last_seen_at ?? item.created_at }}</span>
          <el-button v-if="!item.is_current" text type="danger" size="small" @click="revoke(item)">
            下线
          </el-button>
          <el-tag v-else size="small" effect="plain">当前设备</el-tag>
        </li>
      </ul>
      <p v-if="!sessions.length" class="sw-muted">暂无登录设备记录</p>
      <el-button
        class="sw-settings__action"
        type="danger"
        plain
        @click="revokeAll"
      >
        下线全部其它设备
      </el-button>
    </section>

    <section class="sw-card sw-settings__card">
      <h3 class="sw-card__title">账号</h3>
      <p class="sw-muted">
        当前角色：{{ roleLabel }}（{{ auth.canPublish ? '可发布' : '需完成学生身份认证后才能发布' }}）
      </p>
      <div class="sw-settings__actions">
        <el-button @click="router.push({ name: 'blocks' })">屏蔽的用户</el-button>
        <el-button @click="router.push({ name: 'appeals' })">申诉与处理记录</el-button>
        <el-button @click="passwordOpen = true">修改密码</el-button>
        <el-button @click="pairingOpen = true">跨端配对</el-button>
      </div>
    </section>

    <section class="sw-card sw-settings__card">
      <h3 class="sw-card__title">外观</h3>
      <div class="sw-settings__theme">
        <span>深色模式</span>
        <el-switch
          :model-value="theme.dark"
          @update:model-value="(value: string | number | boolean) => theme.setDark(!!value)"
        />
      </div>
      <p class="sw-muted">当前：{{ theme.modeLabel }}</p>
    </section>

    <section class="sw-card sw-settings__card">
      <h3 class="sw-card__title">更多</h3>
      <div class="sw-settings__actions">
        <el-button @click="router.push({ name: 'info', params: { type: 'community' } })">社区规范</el-button>
        <el-button @click="router.push({ name: 'info', params: { type: 'privacy' } })">隐私政策</el-button>
        <el-button @click="router.push({ name: 'info', params: { type: 'agreement' } })">用户协议</el-button>
        <el-button @click="router.push({ name: 'info', params: { type: 'about' } })">关于我们</el-button>
        <el-button @click="router.push({ name: 'info', params: { type: 'contact' } })">联系我们</el-button>
        <el-button @click="router.push({ name: 'info', params: { type: 'invite' } })">邀请校友</el-button>
        <el-button type="primary" plain @click="feedbackOpen = true">意见反馈</el-button>
      </div>
    </section>

    <section class="sw-card sw-settings__card sw-settings__card--danger">
      <h3 class="sw-card__title">危险操作</h3>
      <p class="sw-muted">注销后无法恢复，历史帖子将显示为「已注销用户」。</p>
      <div class="sw-settings__actions">
        <el-button type="danger" plain @click="logout">退出登录</el-button>
        <el-button type="danger" @click="deactivateOpen = true">注销账号</el-button>
      </div>
    </section>

    <el-dialog v-model="passwordOpen" title="修改密码" width="480px">
      <el-form label-width="88px">
        <template v-if="passwordMode === 'change'">
          <el-form-item label="当前密码">
            <el-input
              v-model="currentPassword"
              type="password"
              show-password
              placeholder="当前登录密码"
            />
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="登录名">
            <el-input v-model="loginName" maxlength="20" placeholder="2-20 位，用于网页登录" />
          </el-form-item>
        </template>
        <el-form-item label="新密码">
          <el-input v-model="newPassword" type="password" show-password placeholder="至少 10 位" />
        </el-form-item>
      </el-form>
      <p class="sw-muted">密码修改成功后，当前设备的登录状态会失效，需要重新登录。</p>
      <template #footer>
        <el-button @click="passwordOpen = false">取消</el-button>
        <el-button type="primary" :loading="passwordSaving" @click="submitPassword">确认修改</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="pairingOpen" title="跨端配对" width="480px">
      <el-form label-width="96px">
        <el-form-item label="生成配对码">
          <el-button :loading="pairingSaving" @click="generatePairing">生成配对码</el-button>
        </el-form-item>
        <el-form-item label="对方配对码">
          <el-input v-model="claimCode" maxlength="32" placeholder="输入原账号生成的配对码" />
        </el-form-item>
      </el-form>
      <p v-if="pairingCode" class="sw-settings__pairing-code">{{ pairingCode }}</p>
      <p class="sw-muted">
        在另一端（手机 / 平板）的设置中输入配对码即可绑定原账号。配对码 10 分钟内有效
        <template v-if="pairingCountdown">，剩余约 {{ pairingCountdown }} 分钟</template>；此码可绑定登录身份，请勿转发给他人。
      </p>
      <template #footer>
        <el-button @click="pairingOpen = false">关闭</el-button>
        <el-button type="primary" :loading="claimSaving" @click="bindPairing">绑定原账号</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deactivateOpen" title="注销账号" width="480px">
      <p class="sw-muted">
        注销后无法恢复，历史帖子将显示为「已注销用户」，学生会证认证与登录设备记录一并清除。
      </p>
      <el-form label-width="88px" class="sw-settings__form">
        <el-form-item label="登录密码">
          <el-input
            v-model="deactivatePassword"
            type="password"
            show-password
            placeholder="网页账号需输入密码确认"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deactivateOpen = false">取消</el-button>
        <el-button type="danger" :loading="deactivateSaving" @click="deactivate">确认注销</el-button>
      </template>
    </el-dialog>

    <FeedbackDialog v-model="feedbackOpen" />
  </div>
</template>

<style scoped>
.sw-settings {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-settings__card {
  padding: var(--sw-space-5);
}

.sw-settings__card--danger {
  border-color: var(--sw-danger);
}

.sw-settings__form {
  margin-top: var(--sw-space-4);
}

.sw-settings__sessions {
  margin: var(--sw-space-4) 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-2);
}

.sw-settings__session {
  display: flex;
  align-items: center;
  gap: var(--sw-space-3);
  min-height: var(--sw-control-size);
}

.sw-settings__action {
  margin-top: var(--sw-space-3);
}

.sw-settings__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sw-space-2);
  margin-top: var(--sw-space-3);
}

.sw-settings__theme {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: var(--sw-control-size);
}

.sw-settings__pairing-code {
  margin: var(--sw-space-2) 0;
  font-size: var(--sw-text-xl);
  font-weight: 700;
  letter-spacing: 6px;
  color: var(--sw-primary-text);
}
</style>
