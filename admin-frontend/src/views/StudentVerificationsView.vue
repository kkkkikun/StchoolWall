<template>
  <el-card shadow="never">
    <template #header>学生证人工认证</template>
    <el-alert title="证件仅限身份核验；每次查看、审核和撤销均留审计。请勿下载转发或将姓名、学号写入理由。" type="warning" :closable="false" />
    <el-form inline class="filters">
      <el-form-item label="状态">
        <el-select v-model="status" style="width: 160px" @change="load(1)">
          <el-option v-for="value in statuses" :key="value.value" :label="value.label" :value="value.value" />
        </el-select>
      </el-form-item>
      <el-button @click="load()">刷新</el-button>
    </el-form>
    <el-table :data="items" v-loading="loading">
      <el-table-column prop="nickname" label="账户昵称" />
      <el-table-column prop="school_id" label="学校" />
      <el-table-column label="申请时间"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
      <el-table-column prop="status" label="状态" />
      <el-table-column label="操作">
        <template #default="{ row }">
          <el-button v-if="row.evidence_available" link type="primary" @click="open(row)">查看证件 / 审核</el-button>
          <el-button v-if="row.status === 'approved'" link type="danger" @click="revoke(row)">撤销认证</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination class="filters" v-model:current-page="page" :total="total" :page-size="20" layout="total, prev, pager, next" @current-change="load()" />
    <el-dialog v-model="visible" title="学生证核验" width="760px" @closed="close">
      <template v-if="selected">
        <p>照片中应有学校、学号、有效期及同框手写码：<strong>{{ selected.challenge_code }}</strong></p>
        <img v-if="proofUrl" class="proof" :src="proofUrl" alt="私有学生证照片，仅供授权核验" />
        <el-form v-if="selected.status === 'pending'" label-position="top">
          <el-form-item label="录入照片可见学号（仅作指纹比较，不落库）">
            <el-input v-model="form.student_id" maxlength="32" autocomplete="off" />
          </el-form-item>
          <el-form-item label="照片上标明的有效期；未注明可留空">
            <el-date-picker v-model="form.card_valid_until" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-checkbox v-model="form.challenge_matches">学生证与拍摄码同框且码一致</el-checkbox>
          <el-checkbox v-model="form.school_matches">学校与试点学校一致</el-checkbox>
          <el-checkbox v-model="form.student_number_matches">学号清晰且为本人有效学生证</el-checkbox>
          <el-checkbox v-model="form.validity_checked">已核对有效期（最长认证 12 个月）</el-checkbox>
          <el-form-item label="审核说明（拒绝必填，请勿写入姓名、学号等信息）">
            <el-input v-model="form.reason" type="textarea" maxlength="500" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="visible = false">关闭</el-button>
        <template v-if="selected?.status === 'pending'">
          <el-button type="danger" :loading="saving" @click="review('rejected')">拒绝</el-button>
          <el-button type="primary" :loading="saving" @click="review('approved')">通过核验</el-button>
        </template>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listVerifications, evidenceBlob, reviewVerification, revokeVerification, type VerificationItem } from '@/api/verification'

const statuses = [
  { value: 'pending', label: '待审核' }, { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已拒绝' }, { value: 'expired', label: '已过期' }, { value: 'revoked', label: '已撤销' },
]
const items = ref<VerificationItem[]>([])
const page = ref(1)
const total = ref(0)
const status = ref('pending')
const loading = ref(false)
const saving = ref(false)
const visible = ref(false)
const selected = ref<VerificationItem | null>(null)
const proofUrl = ref('')
const form = reactive({ student_id: '', card_valid_until: '', challenge_matches: false,
  school_matches: false, student_number_matches: false, validity_checked: false, reason: '' })
const formatDate = (value: string) => value?.slice(0, 16).replace('T', ' ')
const load = async (newPage?: number) => {
  if (newPage) page.value = newPage
  loading.value = true
  try {
    const data = await listVerifications(status.value, page.value)
    items.value = data.items
    total.value = data.total
  } finally { loading.value = false }
}
const close = () => {
  if (proofUrl.value) URL.revokeObjectURL(proofUrl.value)
  proofUrl.value = ''
  selected.value = null
  form.student_id = ''
}
const open = async (item: VerificationItem) => {
  close()
  try {
    const blob = await evidenceBlob(item.id)
    proofUrl.value = URL.createObjectURL(blob)
    selected.value = item
    Object.assign(form, { student_id: '', card_valid_until: item.card_valid_until || '',
      challenge_matches: false, school_matches: false, student_number_matches: false,
      validity_checked: false, reason: '' })
    visible.value = true
  } catch (error) { ElMessage.error((error as Error).message) }
}
const review = async (decision: 'approved' | 'rejected') => {
  if (!selected.value || saving.value) return
  if (decision === 'approved' && (!form.student_id || !form.challenge_matches ||
      !form.school_matches || !form.student_number_matches || !form.validity_checked)) {
    ElMessage.warning('请完成全部核对项目')
    return
  }
  if (decision === 'rejected' && !form.reason.trim()) {
    ElMessage.warning('请填写拒绝原因')
    return
  }
  saving.value = true
  try {
    await reviewVerification(selected.value.id, {
      ...form, decision, student_id: form.student_id || null,
      card_valid_until: form.card_valid_until || null,
    })
    visible.value = false
    close()
    ElMessage.success('审核结果已保存')
    await load()
  } finally { saving.value = false }
}
const revoke = async (item: VerificationItem) => {
  const result = await ElMessageBox.prompt('说明撤销原因，请勿填写姓名或学号', '撤销认证', {
    inputValidator: (value: string) => value.trim().length >= 2 || '至少输入 2 个字符',
  })
  await revokeVerification(item.id, result.value)
  ElMessage.success('认证已撤销')
  await load()
}
onMounted(() => load())
onUnmounted(close)
</script>

<style scoped>
.filters { margin-top: 20px; }
.proof { display: block; max-height: 420px; max-width: 100%; margin: 16px auto; }
.el-checkbox { display: flex; }

/* 窄屏适配：固定 760px 弹窗在 <760px 视口下会溢出，统一限宽 */
:deep(.el-dialog) { max-width: 92vw; }
</style>
