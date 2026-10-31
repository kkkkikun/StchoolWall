<template>
  <el-card shadow="never">
    <template #header>人工审核与故障队列</template>
    <el-alert title="先查看全部文字和图片再作决定；人工审核将记录操作人和理由。重试只用于恢复机器审核。" :closable="false" />
    <el-space class="filters">
      <el-select v-model="status" style="width: 180px" @change="page = 1; load()">
        <el-option v-for="s in statuses" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-button @click="load">刷新</el-button>
    </el-space>
    <el-table :data="items" v-loading="loading">
      <el-table-column prop="kind" label="类型" width="170" />
      <el-table-column prop="text" label="待审文字" show-overflow-tooltip />
      <el-table-column prop="attempts" label="尝试次数" width="90" />
      <el-table-column prop="last_error" label="故障" width="160" />
      <el-table-column label="操作" width="220"><template #default="{ row }">
        <el-button link type="primary" @click="open(row as Job)">查看 / 决定</el-button>
        <el-button v-if="['review','dead'].includes(row.status)" link @click="retry(row as Job)">重试机器审核</el-button>
      </template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="total, prev, pager, next" @current-change="load" />
    <el-dialog v-model="visible" title="审核申请" width="760px" @closed="clearImages">
      <p style="white-space: pre-wrap">{{ selected?.text || '请核对图片内容' }}</p>
      <el-space wrap><img v-for="url in urls" :key="url" :src="url" class="preview" alt="待审图片" /></el-space>
      <el-input v-model="reason" type="textarea" maxlength="300" placeholder="填写决定理由；不要录入个人敏感信息" />
      <template #footer>
        <el-button @click="visible = false">关闭</el-button>
        <el-button v-if="canReview" type="danger" :loading="saving" @click="decide('reject')">拒绝</el-button>
        <el-button v-if="canReview" type="primary" :loading="saving" @click="decide('approve')">确认全部通过</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import request from '@/utils/request'
interface Job { id: string; kind: string; status: string; text: string; media_ids: string[]; attempts: number; last_error: string | null }
const statuses = [{value:'review',label:'待人工审核'},{value:'dead',label:'重试耗尽'},{value:'pending',label:'等待机器审核'},{value:'rejected',label:'已拒绝'},{value:'succeeded',label:'已通过'}]
const items = ref<Job[]>([]), selected = ref<Job | null>(null), status = ref('review'), page = ref(1), total = ref(0)
const loading = ref(false), saving = ref(false), visible = ref(false), reason = ref(''), urls = ref<string[]>([])
const canReview = computed(() => !!selected.value && ['review','dead','pending','rejected'].includes(selected.value.status))
async function load() {
  loading.value = true
  try { const data = await request.get<never, {items: Job[]; total: number}>('/admin/moderation-jobs', {params:{status:status.value,page:page.value}}); items.value = data.items; total.value = data.total }
  catch { /* 拦截器已提示 */ }
  finally { loading.value = false }
}
function clearImages() { urls.value.forEach(URL.revokeObjectURL); urls.value = [] }
async function open(job: Job) {
  clearImages(); selected.value = job; reason.value = ''
  try {
    for (const id of job.media_ids) {
      const blob = await request.get<never, Blob>(`/admin/moderation-jobs/${job.id}/media/${id}`, {responseType:'blob'})
      urls.value.push(URL.createObjectURL(blob))
    }
    visible.value = true
  } catch { clearImages() }
}
async function retry(job: Job) {
  try { await request.post(`/admin/moderation-jobs/${job.id}/retry`); ElMessage.success('已进入重试队列'); await load() }
  catch { /* 拦截器已提示；保留列表与重试能力 */ }
}
async function decide(decision: 'approve'|'reject') {
  if (!selected.value || reason.value.trim().length < 2) { ElMessage.warning('请填写至少两个字的理由'); return }
  saving.value = true
  try { await request.post(`/admin/moderation-jobs/${selected.value.id}/review`, {decision,reason:reason.value.trim()}); visible.value = false; clearImages(); await load() }
  catch { /* 拦截器已提示；弹窗保持打开以便重试 */ }
  finally { saving.value = false }
}
onMounted(load)
onUnmounted(clearImages)
</script>
<style scoped>.filters{margin:20px 0}.preview{max-width:330px;max-height:420px;object-fit:contain}.el-input{margin-top:16px}.el-pagination{margin-top:20px}

/* 窄屏适配：固定 760px 弹窗在 <760px 视口下会溢出，统一限宽 */
:deep(.el-dialog) { max-width: 92vw; }
</style>
