<template>
  <el-card shadow="never">
    <el-form inline @submit.prevent>
      <el-form-item label="动作">
        <el-select v-model="filters.action" clearable filterable placeholder="全部动作" style="width: 200px">
          <el-option v-for="a in ACTIONS" :key="a.value" :label="a.label" :value="a.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="时间">
        <el-date-picker v-model="range" type="datetimerange" value-format="YYYY-MM-DDTHH:mm:ss[Z]"
                        start-placeholder="开始" end-placeholder="结束" style="width: 340px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="load(1)">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="items" v-loading="loading">
      <el-table-column label="ID" prop="id" width="80" />
      <el-table-column label="操作者" width="130">
        <template #default="{ row }">
          <span>{{ row.admin_name }}</span>
          <el-tag size="small" :type="row.source === 'console' ? 'success' : 'warning'" class="src-chip">
            {{ row.source === 'console' ? '后台' : '小程序' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="动作" width="150">
        <template #default="{ row }">{{ actionLabel(row.action) }}</template>
      </el-table-column>
      <el-table-column label="目标" width="140">
        <template #default="{ row }">
          <span v-if="row.target_type">{{ row.target_type }} #{{ row.target_id }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="详情" min-width="200">
        <template #default="{ row }">
          <code class="detail-code">{{ row.detail ? JSON.stringify(row.detail) : '—' }}</code>
        </template>
      </el-table-column>
      <el-table-column label="IP" prop="ip" width="120" />
      <el-table-column label="时间" width="160">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
    </el-table>

    <div class="pagination-bar" v-if="total > 0">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @change="() => load()"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { getLogs, type AdminLogItem } from '@/api/operations'

const ACTIONS = [
  { value: 'report.handle', label: '处理举报' },
  { value: 'post.status', label: '帖子状态' },
  { value: 'post.batch_status', label: '批量帖子' },
  { value: 'post.edit', label: '编辑帖子' },
  { value: 'post.pin', label: '置顶' },
  { value: 'user.freeze', label: '冻结用户' },
  { value: 'user.unfreeze', label: '解冻用户' },
  { value: 'user.role', label: '改角色' },
  { value: 'comment.delete', label: '删评论' },
  { value: 'party.status', label: '组局状态' },
  { value: 'announcement.send', label: '群发公告' },
  { value: 'banner.create', label: '建广告' },
  { value: 'banner.update', label: '改广告' },
  { value: 'banner.delete', label: '删广告' },
  { value: 'export.posts', label: '导出帖子' },
  { value: 'export.users', label: '导出用户' },
  { value: 'image.upload', label: '传图片' },
  { value: 'post.featured', label: '设精华' },
  { value: 'comment.status', label: '评论审核' },
  { value: 'sensitive_word.create', label: '加敏感词' },
  { value: 'sensitive_word.update', label: '改敏感词' },
  { value: 'sensitive_word.delete', label: '删敏感词' },
  { value: 'admin.create', label: '建管理员' },
  { value: 'admin.status', label: '启停管理员' },
  { value: 'admin.password_reset', label: '重置管理员密码' },
  { value: 'tag.create', label: '建标签' },
  { value: 'tag.delete', label: '删标签' },
  { value: 'activity.create', label: '建活动' },
  { value: 'activity.update', label: '改活动' },
  { value: 'activity.delete', label: '删活动' },
]

const actionLabel = (action: string) => ACTIONS.find(a => a.value === action)?.label || action

const filters = reactive<{ action?: string }>({})
const range = ref<[string, string] | null>(null)
const items = ref<AdminLogItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const fmtTime = (t: string) => (t ? t.slice(0, 19).replace('T', ' ') : '')

const load = async (targetPage?: number) => {
  if (targetPage) page.value = targetPage
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (filters.action) params.action = filters.action
    if (range.value) {
      params.time_start = range.value[0]
      params.time_end = range.value[1]
    }
    const data = await getLogs(params)
    items.value = data.items
    total.value = data.total ?? data.items.length
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

onMounted(() => load(1))
</script>

<style scoped>
.src-chip { margin-left: 6px; }
.muted { color: var(--el-text-color-placeholder); }
.detail-code { font-size: 12px; color: var(--el-text-color-secondary); word-break: break-all; }
.pagination-bar { margin-top: 20px; display: flex; justify-content: flex-end; }
</style>
