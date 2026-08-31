<template>
  <div>
    <el-card shadow="never">
      <!-- 筛选 -->
      <el-form inline @submit.prevent>
        <el-form-item label="搜索">
          <el-input v-model="filters.q" placeholder="昵称 / 学号 / 真名" clearable style="width: 200px" @keyup.enter="load(1)" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="filters.role" clearable placeholder="全部" style="width: 110px">
            <el-option label="游客" value="guest" />
            <el-option label="学生" value="student" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="认证">
          <el-select v-model="filters.is_verified" clearable placeholder="全部" style="width: 110px">
            <el-option label="已认证" :value="true" />
            <el-option label="未认证" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 110px">
            <el-option label="正常" :value="1" />
            <el-option label="已冻结" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load(1)">查询</el-button>
          <el-button type="success" plain @click="exportCsv">导出 CSV</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="items" v-loading="loading">
        <el-table-column label="昵称" prop="nickname" width="130" />
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-select :model-value="row.role" size="small" style="width: 90px" @change="(v: string) => onRole(row, v)">
              <el-option label="游客" value="guest" />
              <el-option label="学生" value="student" />
              <el-option label="管理员" value="admin" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="学号" width="120">
          <template #default="{ row }">{{ row.student_id || '—' }}</template>
        </el-table-column>
        <el-table-column label="真名" width="100">
          <template #default="{ row }">{{ row.real_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="认证" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_verified ? 'success' : 'info'" size="small">
              {{ row.is_verified ? '已认证' : '未认证' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '正常' : '已冻结' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="注册时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
            <el-button v-if="row.status === 1" link type="danger" size="small" @click="onFreeze(row)">冻结</el-button>
            <el-button v-else link type="success" size="small" @click="onUnfreeze(row)">解冻</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination class="pager" layout="total, prev, pager, next, sizes" :total="total"
                     v-model:current-page="page" v-model:page-size="pageSize"
                     :page-sizes="[10, 20, 50]" @change="load()" />
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="showDetail" :title="detail?.nickname || '用户详情'" size="400px">
      <div v-if="detail">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="昵称">{{ detail.nickname }}</el-descriptions-item>
          <el-descriptions-item label="真名">{{ detail.real_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="学号">{{ detail.student_id || '—' }}</el-descriptions-item>
          <el-descriptions-item label="角色">{{ detail.role }}</el-descriptions-item>
          <el-descriptions-item label="注册时间">{{ fmtTime(detail.created_at) }}</el-descriptions-item>
        </el-descriptions>
        <el-row :gutter="12" class="detail-stats">
          <el-col :span="6"><div class="d-stat"><b>{{ detail.posts_count }}</b><span>帖子</span></div></el-col>
          <el-col :span="6"><div class="d-stat"><b>{{ detail.comments_count }}</b><span>评论</span></div></el-col>
          <el-col :span="6"><div class="d-stat"><b>{{ detail.likes_received }}</b><span>获赞</span></div></el-col>
          <el-col :span="6"><div class="d-stat"><b class="danger">{{ detail.reported_count }}</b><span>被举报</span></div></el-col>
        </el-row>
        <h4 class="recent-title">最近帖子</h4>
        <div v-for="p in detail.recent_posts" :key="p.id" class="recent-post">
          <span class="rp-content">{{ p.content }}</span>
          <el-tag size="small" :type="p.status === 1 ? 'success' : p.status === 0 ? 'warning' : 'danger'">
            {{ p.status === 1 ? '正常' : p.status === 0 ? '待审' : '异常' }}
          </el-tag>
        </div>
        <el-empty v-if="!detail.recent_posts.length" description="暂无帖子" :image-size="60" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getUsers, getUserDetail, updateUserStatus, updateUserRole, exportUsersUrl, type AdminUser, type UserDetail } from '@/api/users'
import { getToken } from '@/utils/request'

const filters = reactive<{ q?: string; role?: string; is_verified?: boolean; status?: number }>({})
const items = ref<AdminUser[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const showDetail = ref(false)
const detail = ref<UserDetail | null>(null)

const fmtTime = (t: string) => (t ? t.slice(0, 16).replace('T', ' ') : '')

const load = async (targetPage?: number) => {
  if (targetPage) page.value = targetPage
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    if (filters.q) params.q = filters.q
    if (filters.role) params.role = filters.role
    if (filters.is_verified !== undefined && filters.is_verified !== null) params.is_verified = filters.is_verified
    if (filters.status !== undefined && filters.status !== null) params.status = filters.status
    const data = await getUsers(params)
    items.value = data.items
    total.value = data.total
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const onRole = async (row: AdminUser, role: string) => {
  try {
    await ElMessageBox.confirm(`确定把 ${row.nickname} 的角色改为「${role}」吗？`, '确认', { type: 'warning' })
  } catch {
    load() // 取消则还原
    return
  }
  await updateUserRole(row.id, role)
  ElMessage.success('角色已更新')
  load()
}

const onFreeze = async (row: AdminUser) => {
  await ElMessageBox.confirm(`确定冻结 ${row.nickname} 吗？冻结后无法登录。`, '确认', { type: 'warning' })
  await updateUserStatus(row.id, 0)
  ElMessage.success('已冻结')
  load()
}

const onUnfreeze = async (row: AdminUser) => {
  await updateUserStatus(row.id, 1)
  ElMessage.success('已解冻')
  load()
}

const openDetail = async (row: AdminUser) => {
  detail.value = await getUserDetail(row.id)
  showDetail.value = true
}

const exportCsv = () => {
  fetch(exportUsersUrl(), { headers: { Authorization: `Bearer ${getToken()}` } })
    .then(r => {
      if (!r.ok) throw new Error()
      return r.blob()
    })
    .then(blob => {
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `users-${Date.now()}.csv`
      a.click()
      URL.revokeObjectURL(a.href)
      ElMessage.success('已导出（本次导出已记录审计日志）')
    })
    .catch(() => ElMessage.error('导出失败'))
}

onMounted(() => load())
</script>

<style scoped>
.pager { margin-top: 16px; justify-content: flex-end; }
.detail-stats { margin: 16px 0; }
.d-stat {
  background: #f5f7fa; border-radius: 8px; padding: 12px 0;
  display: flex; flex-direction: column; align-items: center;
}
.d-stat b { font-size: 20px; color: #303133; }
.d-stat b.danger { color: #f73b43; }
.d-stat span { font-size: 12px; color: #909399; margin-top: 2px; }
.recent-title { margin: 12px 0 8px; color: #303133; }
.recent-post {
  display: flex; justify-content: space-between; align-items: center; gap: 8px;
  padding: 10px 12px; background: #f5f7fa; border-radius: 6px; margin-bottom: 8px;
}
.rp-content { font-size: 13px; color: #606266; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
