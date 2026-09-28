<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-row">
        <span>待处理举报</span>
        <el-radio-group v-model="statusFilter" size="small" @change="load">
          <el-radio-button value="pending">待处理</el-radio-button>
          <el-radio-button value="">全部</el-radio-button>
        </el-radio-group>
      </div>
    </template>

    <el-table :data="items" v-loading="loading">
      <el-table-column label="ID" prop="id" width="70" />
      <el-table-column label="举报人" prop="reporter.nickname" width="110" />
      <el-table-column label="理由" width="130">
        <template #default="{ row }">
          <el-tag type="danger" size="small">{{ row.reason }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="被举报内容" min-width="280">
        <template #default="{ row }">
          <div class="post-content">{{ row.post_content }}</div>
          <div class="post-desc" v-if="row.description">补充：{{ row.description }}</div>
        </template>
      </el-table-column>
      <el-table-column label="帖子状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.post_status === 1 ? 'success' : 'danger'" size="small">
            {{ row.post_status === 1 ? '展示中' : '已处理' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="举报时间" width="160">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'pending' ? 'warning' : 'info'" size="small">
            {{ row.status === 'pending' ? '待处理' : row.status === 'dismissed' ? '已驳回' : '已处理' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <template v-if="row.status === 'pending'">
            <el-button link type="info" size="small" @click="onHandle(row, 'dismiss')">驳回</el-button>
            <el-button link type="danger" size="small" @click="onHandle(row, 'ban_post')">封帖</el-button>
            <el-button link type="danger" size="small" @click="onHandle(row, 'ban_user')">封号</el-button>
          </template>
          <span v-else class="done-text">—</span>
        </template>
      </el-table-column>
    </el-table>

    <div class="load-more-row" v-if="hasMore">
      <el-button @click="loadMore" :loading="loading">加载更多</el-button>
    </div>
    <el-empty v-if="!items.length && !loading" description="暂无举报" />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getReports, handleReport, type AdminReport } from '@/api/reports'

const items = ref<AdminReport[]>([])
const statusFilter = ref('pending')
const cursor = ref<number | null>(null)
const hasMore = ref(false)
const loading = ref(false)

const fmtTime = (t: string) => (t ? t.slice(0, 16).replace('T', ' ') : '')

const load = async (append = false) => {
  if (typeof append === 'string') append = false // radio change 事件传入值
  loading.value = true
  try {
    const params: Record<string, unknown> = {}
    if (statusFilter.value) params.status = statusFilter.value
    if (append && cursor.value) params.cursor = cursor.value
    const data = await getReports(params)
    items.value = append ? [...items.value, ...data.items] : data.items
    cursor.value = data.next_cursor
    hasMore.value = data.has_more
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const loadMore = () => load(true)

const onHandle = async (row: AdminReport, action: 'dismiss' | 'ban_post' | 'ban_user') => {
  const labels = { dismiss: '驳回该举报（不处罚）', ban_post: '封禁该帖子', ban_user: '封禁帖子并冻结作者' }
  await ElMessageBox.confirm(`确定要「${labels[action]}」吗？`, '确认操作', { type: 'warning' })
  await handleReport(row.id, action)
  ElMessage.success('处理成功')
  load()
}

onMounted(() => load())
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.post-content { color: var(--el-text-color-primary); }
.post-desc { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }
.done-text { color: var(--el-text-color-placeholder); }
.load-more-row { margin-top: 16px; text-align: center; }
</style>
