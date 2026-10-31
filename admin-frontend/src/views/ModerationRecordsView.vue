<template>
  <el-card shadow="never">
    <template #header>
      <span>机器审核记录（每次审核按来源落一行，人工过审时可参考判定原因）</span>
    </template>

    <el-form inline @submit.prevent>
      <el-form-item label="判定">
        <el-select v-model="filters.verdict" clearable placeholder="全部" style="width: 130px">
          <el-option label="拒绝" value="reject" />
          <el-option label="转人工" value="review" />
          <el-option label="通过" value="pass" />
          <el-option label="故障" value="error" />
        </el-select>
      </el-form-item>
      <el-form-item label="来源">
        <el-select v-model="filters.source" clearable placeholder="全部" style="width: 150px">
          <el-option label="本地规则" value="rule" />
          <el-option label="微信内容安全" value="wechat" />
        </el-select>
      </el-form-item>
      <el-form-item label="帖子ID">
        <el-input v-model.number="filters.post_id" placeholder="精确匹配" clearable style="width: 130px" @keyup.enter="load(1)" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="load(1)">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="items" v-loading="loading">
      <el-table-column label="ID" prop="id" width="80" />
      <el-table-column label="帖子" width="100">
        <template #default="{ row }">
          <el-link type="primary" :underline="false" @click="goPost(row.post_id)">
            #{{ row.post_id }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column label="来源" width="130">
        <template #default="{ row }">
          <el-tag :type="row.source === 'rule' ? 'warning' : 'success'" size="small" effect="plain">
            {{ row.source === 'rule' ? '本地规则' : '微信' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="判定" width="100">
        <template #default="{ row }">
          <el-tag :type="VERDICT_TAG[row.verdict]" size="small">{{ VERDICT[row.verdict] }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="命中词" min-width="140">
        <template #default="{ row }">
          <span v-if="row.matched?.length" class="matched">{{ row.matched.join('、') }}</span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="原因" min-width="220">
        <template #default="{ row }">
          <span class="muted">{{ row.reason || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="trace_id" width="120">
        <template #default="{ row }">
          <span class="muted">{{ row.trace_id || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="160">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!items.length && !loading" description="暂无审核记录（学生发帖后自动产生）" />

    <el-pagination class="pager" layout="total, prev, pager, next" :total="total"
                   v-model:current-page="page" :page-size="pageSize" @change="load()" />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getModerationRecords, type ModerationRecord } from '@/api/moderation'

const router = useRouter()

const goPost = (postId: number) => {
  router.push({ path: '/posts', query: { post_id: postId } })
}

const VERDICT: Record<string, string> = { reject: '拒绝', review: '转人工', pass: '通过', error: '故障' }
const VERDICT_TAG: Record<string, string> = { reject: 'danger', review: 'warning', pass: 'success', error: 'info' }

const filters = reactive<{ verdict?: string; source?: string; post_id?: number }>({})
const items = ref<ModerationRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

const fmtTime = (t: string) => (t ? t.slice(0, 16).replace('T', ' ') : '')

const load = async (targetPage?: number) => {
  if (targetPage) page.value = targetPage
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize }
    if (filters.verdict) params.verdict = filters.verdict
    if (filters.source) params.source = filters.source
    if (filters.post_id) params.post_id = filters.post_id
    const data = await getModerationRecords(params)
    items.value = data.items
    total.value = data.total
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

onMounted(() => load())
</script>

<style scoped>
.pager { margin-top: 16px; justify-content: flex-end; }
.muted { color: var(--el-text-color-secondary); font-size: 12px; }
.matched { color: var(--el-color-danger); font-size: 12px; font-weight: 600; }
</style>
