<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-head">
        <span>管理员账号</span>
        <el-button type="primary" @click="openCreate">＋ 新建账号</el-button>
      </div>
    </template>

    <el-form inline @submit.prevent>
      <el-form-item label="搜索">
        <el-input v-model="filters.q" placeholder="用户名 / 昵称" clearable style="width: 200px" @keyup.enter="load(1)" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="load(1)">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="items" v-loading="loading">
      <el-table-column label="用户名" prop="username" min-width="140" />
      <el-table-column label="昵称" prop="nickname" min-width="120" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="最近登录" width="160">
        <template #default="{ row }">{{ fmtTime(row.last_login_at) || '—' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="160">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <template v-if="row.id !== auth.adminId">
            <el-button v-if="row.is_active" link type="danger" size="small" @click="onToggle(row, false)">停用</el-button>
            <el-button v-else link type="success" size="small" @click="onToggle(row, true)">启用</el-button>
            <el-button link type="warning" size="small" @click="openReset(row)">重置密码</el-button>
          </template>
          <span v-else class="self-tip">当前账号</span>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="pager" layout="total, prev, pager, next" :total="total"
                   v-model:current-page="page" :page-size="pageSize" @change="load()" />

    <!-- 新建账号 -->
    <el-dialog v-model="showCreate" title="新建管理员账号" width="440px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="createForm.username" maxlength="50" placeholder="3-50 位，登录用" />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="createForm.nickname" maxlength="50" placeholder="用于审计日志显示" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="createForm.password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="createForm.confirm" type="password" show-password placeholder="再次输入" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">保存</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="showReset" :title="`重置「${resetTarget?.nickname || ''}」的密码`" width="440px">
      <el-form label-width="80px">
        <el-form-item label="新密码">
          <el-input v-model="resetForm.password" type="password" show-password placeholder="至少 8 位" />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="resetForm.confirm" type="password" show-password placeholder="再次输入" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReset = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onReset">确认重置</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAdminAccounts, createAdminAccount, updateAdminAccountStatus, resetAdminAccountPassword,
  type AdminAccount,
} from '@/api/adminAccounts'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const filters = reactive<{ q?: string }>({})
const items = ref<AdminAccount[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

const showCreate = ref(false)
const showReset = ref(false)
const saving = ref(false)
const resetTarget = ref<AdminAccount | null>(null)
const createForm = reactive({ username: '', nickname: '', password: '', confirm: '' })
const resetForm = reactive({ password: '', confirm: '' })

const fmtTime = (t: string | null) => (t ? t.slice(0, 16).replace('T', ' ') : '')

const load = async (targetPage?: number) => {
  if (targetPage) page.value = targetPage
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize }
    if (filters.q) params.q = filters.q
    const data = await getAdminAccounts(params)
    items.value = data.items
    total.value = data.total
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const openCreate = () => {
  createForm.username = ''
  createForm.nickname = ''
  createForm.password = ''
  createForm.confirm = ''
  showCreate.value = true
}

const onCreate = async () => {
  if (!createForm.username.trim() || !createForm.nickname.trim()) {
    ElMessage.warning('用户名和昵称必填')
    return
  }
  if (createForm.username.trim().length < 3) {
    ElMessage.warning('用户名至少 3 位')
    return
  }
  if (createForm.password.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  if (createForm.password !== createForm.confirm) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  saving.value = true
  try {
    await createAdminAccount({
      username: createForm.username.trim(),
      nickname: createForm.nickname.trim(),
      password: createForm.password,
    })
    ElMessage.success('创建成功')
    showCreate.value = false
    load(1)
  } catch { /* 拦截器已提示 */ } finally {
    saving.value = false
  }
}

const onToggle = async (row: AdminAccount, isActive: boolean) => {
  const action = isActive ? '启用' : '停用'
  await ElMessageBox.confirm(`确定${action}账号「${row.username}」吗？${isActive ? '' : '停用后该账号将立即无法登录。'}`, '确认', { type: 'warning' })
  await updateAdminAccountStatus(row.id, isActive)
  ElMessage.success(`已${action}`)
  load()
}

const openReset = (row: AdminAccount) => {
  resetTarget.value = row
  resetForm.password = ''
  resetForm.confirm = ''
  showReset.value = true
}

const onReset = async () => {
  if (!resetTarget.value) return
  if (resetForm.password.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  if (resetForm.password !== resetForm.confirm) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  saving.value = true
  try {
    await resetAdminAccountPassword(resetTarget.value.id, resetForm.password)
    ElMessage.success('密码已重置，该账号需用新密码重新登录')
    showReset.value = false
  } catch { /* 拦截器已提示 */ } finally {
    saving.value = false
  }
}

onMounted(() => load())
</script>

<style scoped>
.card-head { display: flex; align-items: center; justify-content: space-between; }
.pager { margin-top: 16px; justify-content: flex-end; }
.self-tip { color: var(--el-text-color-secondary); font-size: 13px; }
</style>
