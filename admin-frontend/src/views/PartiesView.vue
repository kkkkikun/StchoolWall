<template>
  <el-card shadow="never">
    <el-form inline @submit.prevent>
      <el-form-item label="关键词">
        <el-input v-model="filters.q" placeholder="搜索标题/内容" clearable style="width: 200px" @keyup.enter="load(1)" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable placeholder="全部" style="width: 120px">
          <el-option label="招募中" :value="1" />
          <el-option label="已满" :value="2" />
          <el-option label="已关闭" :value="-1" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="load(1)">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="items" v-loading="loading">
      <el-table-column label="ID" prop="id" width="72" />
      <el-table-column label="标题" min-width="180" prop="title" />
      <el-table-column label="组织者" prop="organizer.nickname" width="110" />
      <el-table-column label="类型" width="90">
        <template #default="{ row }">{{ row.type === 'group' ? '组局' : '拼单' }}</template>
      </el-table-column>
      <el-table-column label="分类" prop="category" width="100" />
      <el-table-column label="进度" width="100">
        <template #default="{ row }">{{ row.joined_count }}/{{ row.total }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : row.status === 2 ? 'warning' : 'info'" size="small">
            {{ row.status === 1 ? '招募中' : row.status === 2 ? '已满' : '已关闭' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="集合时间" width="160">
        <template #default="{ row }">{{ fmtTime(row.meet_time) || '—' }}</template>
      </el-table-column>
      <el-table-column label="地点" width="120">
        <template #default="{ row }">{{ row.location || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status !== -1" link type="danger" size="small" @click="onClose(row)">关闭</el-button>
          <el-button v-else link type="success" size="small" @click="onRestore(row)">恢复</el-button>
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
import { getParties, updatePartyStatus, type AdminParty } from '@/api/operations'

const filters = reactive<{ q?: string; status?: number }>({})
const items = ref<AdminParty[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

const fmtTime = (t: string | null) => (t ? t.slice(0, 16).replace('T', ' ') : '')

const load = async (targetPage?: number) => {
  if (targetPage) page.value = targetPage
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize }
    if (filters.q) params.q = filters.q
    if (filters.status !== undefined && filters.status !== null) params.status = filters.status
    const data = await getParties(params)
    items.value = data.items
    total.value = data.total
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const onClose = async (row: AdminParty) => {
  await ElMessageBox.confirm(`确定关闭组局「${row.title}」吗？`, '确认', { type: 'warning' })
  await updatePartyStatus(row.id, -1)
  ElMessage.success('已关闭')
  load()
}

const onRestore = async (row: AdminParty) => {
  await updatePartyStatus(row.id, 1)
  ElMessage.success('已恢复')
  load()
}

onMounted(() => load())
</script>

<style scoped>
.pager { margin-top: 16px; justify-content: flex-end; }
</style>
