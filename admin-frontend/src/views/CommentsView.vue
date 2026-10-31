<template>
  <el-card shadow="never">
    <el-form inline @submit.prevent>
      <el-form-item label="关键词">
        <el-input v-model="filters.q" placeholder="搜索评论内容" clearable style="width: 200px" @keyup.enter="load(1)" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable placeholder="全部" style="width: 120px">
          <el-option label="待审核" :value="0" />
          <el-option label="正常" :value="1" />
          <el-option label="已删除" :value="-1" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="load(1)">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="items" v-loading="loading">
      <el-table-column label="ID" prop="id" width="80" />
      <el-table-column label="评论内容" min-width="260">
        <template #default="{ row }">
          <span :class="{ deleted: row.status === -1 }">{{ row.content }}</span>
        </template>
      </el-table-column>
      <el-table-column label="评论者" prop="author.nickname" width="110" />
      <el-table-column label="所属帖子" min-width="180">
        <template #default="{ row }">
          <span class="muted">{{ row.post_content }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="STATUS_TAG[row.status] || 'info'" size="small">{{ STATUS[row.status] || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="160">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 0" link type="success" size="small" @click="onStatus(row, 1)">过审</el-button>
          <el-button v-if="row.status === 0" link type="danger" size="small" @click="onStatus(row, -1)">拒审</el-button>
          <el-button v-if="row.status === 1" link type="danger" size="small" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="pager" layout="total, prev, pager, next" :total="total"
                   v-model:current-page="page" :page-size="pageSize" @change="load()" />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getComments, deleteComment, updateCommentStatus, type AdminComment } from '@/api/operations'

const filters = reactive<{ q?: string; status?: number }>({})
const items = ref<AdminComment[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

const STATUS: Record<number, string> = { 0: '待审核', 1: '正常', '-1': '已删除' }
const STATUS_TAG: Record<number, string> = { 0: 'warning', 1: 'success', '-1': 'info' }

const onStatus = async (row: any, status: number) => {
  const label = status === 1 ? '通过' : '拒绝'
  await ElMessageBox.confirm(`确定${label}这条评论吗？`, '确认', { type: 'warning' })
  await updateCommentStatus(row.id, status)
  ElMessage.success(`已${label}`)
  load()
}

const fmtTime = (t: string) => (t ? t.slice(0, 16).replace('T', ' ') : '')

const load = async (targetPage?: number) => {
  if (targetPage) page.value = targetPage
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize }
    if (filters.q) params.q = filters.q
    if (filters.status !== undefined && filters.status !== null) params.status = filters.status
    const data = await getComments(params)
    items.value = data.items
    total.value = data.total
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const onDelete = async (row: AdminComment) => {
  await ElMessageBox.confirm('确定删除这条评论吗？（软删除）', '确认', { type: 'warning' })
  await deleteComment(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(() => load())
</script>

<style scoped>
.deleted { color: var(--el-text-color-placeholder); text-decoration: line-through; }
.muted { color: var(--el-text-color-secondary); font-size: 12px; }
.pager { margin-top: 16px; justify-content: flex-end; }
</style>
