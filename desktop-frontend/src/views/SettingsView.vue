<script setup lang="ts">
/** 账号设置：资料修改、登录设备、退出登录。 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { getSessions, revokeSession } from '@/api/auth'
import type { SessionItem } from '@/api/auth'
import { getMyProfile, updateMyProfile } from '@/api/user'
import type { MyProfile } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const profile = ref<MyProfile | null>(null)
const sessions = ref<SessionItem[]>([])
const nickname = ref('')
const bio = ref('')
const wechatId = ref('')
const saving = ref(false)

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
    </section>

    <section class="sw-card sw-settings__card">
      <h3 class="sw-card__title">账号</h3>
      <p class="sw-muted">当前角色：{{ auth.role }}（{{ auth.canPublish ? '可发布' : '需完成学生身份认证后才能发布' }}）</p>
      <el-button type="danger" plain @click="logout">退出登录</el-button>
    </section>
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
</style>
