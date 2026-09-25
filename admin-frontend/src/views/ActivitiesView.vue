<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-head">
        <span>站内活动页</span>
        <el-button type="primary" @click="openForm()">＋ 新建活动</el-button>
      </div>
    </template>

    <el-form inline @submit.prevent>
      <el-form-item label="搜索">
        <el-input v-model="filters.q" placeholder="活动标题" clearable style="width: 200px" @keyup.enter="load(1)" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.status" clearable placeholder="全部" style="width: 120px">
          <el-option label="上架" :value="1" />
          <el-option label="下架" :value="0" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="load(1)">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="items" v-loading="loading">
      <el-table-column label="ID" prop="id" width="72" />
      <el-table-column label="标题" min-width="180" prop="title" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '上架' : '下架' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="地点" min-width="120">
        <template #default="{ row }">{{ row.location || '—' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="160">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openForm(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination class="pager" layout="total, prev, pager, next" :total="total"
                   v-model:current-page="page" :page-size="pageSize" @change="load()" />

    <el-dialog v-model="showForm" :title="editing ? '编辑活动' : '新建活动'" width="680px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="封面图">
          <div class="upload-row">
            <el-upload :show-file-list="false" accept="image/*" :http-request="onUpload" :disabled="uploading">
              <el-button :loading="uploading">{{ uploading ? '上传中…' : '上传图片' }}</el-button>
            </el-upload>
            <el-input v-if="form.image_url" v-model="form.image_url" class="url-input" placeholder="图片 URL" />
          </div>
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="form.summary" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="正文" required>
          <el-input v-model="form.content" type="textarea" :rows="6" maxlength="5000" show-word-limit />
        </el-form-item>
        <el-form-item label="地点">
          <el-input v-model="form.location" maxlength="100" />
        </el-form-item>
        <el-form-item label="活动时间">
          <el-date-picker v-model="form.range" type="datetimerange" value-format="YYYY-MM-DDTHH:mm:ss[Z]"
                          start-placeholder="开始" end-placeholder="结束" style="width: 340px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" active-text="上架" inactive-text="下架" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showForm = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getActivities, createActivity, updateActivity, deleteActivity, type AdminActivity } from '@/api/activities'
import { uploadImage } from '@/api/banners'

const filters = reactive<{ q?: string; status?: number }>({})
const items = ref<AdminActivity[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

const showForm = ref(false)
const saving = ref(false)
const uploading = ref(false)
const editing = ref<AdminActivity | null>(null)

const form = reactive({
  title: '', image_url: '', summary: '', content: '', location: '',
  status: 1,
  range: null as [string, string] | null,
})

const fmtTime = (t: string) => (t ? t.slice(0, 16).replace('T', ' ') : '')

const load = async (targetPage?: number) => {
  if (targetPage) page.value = targetPage
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize }
    if (filters.q) params.q = filters.q
    if (filters.status !== undefined && filters.status !== null) params.status = filters.status
    const data = await getActivities(params)
    items.value = data.items
    total.value = data.total
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const openForm = (row?: AdminActivity) => {
  editing.value = row ?? null
  form.title = row?.title || ''
  form.image_url = row?.image_url || ''
  form.summary = row?.summary || ''
  form.content = row?.content || ''
  form.location = row?.location || ''
  form.status = row?.status ?? 1
  form.range = (row?.start_at && row?.end_at) ? [row.start_at, row.end_at] : null
  showForm.value = true
}

const onUpload = async (option: any) => {
  uploading.value = true
  try {
    const result = await uploadImage(option.file as File)
    form.image_url = result.public_url
    ElMessage.success('上传成功')
  } catch { /* 拦截器已提示 */ } finally {
    uploading.value = false
  }
}

const save = async () => {
  if (!form.title.trim() || !form.content.trim()) {
    ElMessage.warning('标题和正文必填')
    return
  }
  const data: Record<string, unknown> = {
    title: form.title.trim(),
    image_url: form.image_url.trim() || null,
    summary: form.summary.trim() || null,
    content: form.content,
    location: form.location.trim() || null,
    start_at: form.range ? form.range[0] : null,
    end_at: form.range ? form.range[1] : null,
    status: form.status,
  }
  saving.value = true
  try {
    if (editing.value) await updateActivity(editing.value.id, data)
    else await createActivity(data)
    ElMessage.success('保存成功')
    showForm.value = false
    load()
  } catch { /* 拦截器已提示 */ } finally {
    saving.value = false
  }
}

const onDelete = async (row: AdminActivity) => {
  try {
    await ElMessageBox.confirm(`确定删除活动「${row.title}」吗？`, '确认', { type: 'warning' })
  } catch {
    return
  }
  await deleteActivity(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(() => load())
</script>

<style scoped>
.card-head { display: flex; align-items: center; justify-content: space-between; }
.pager { margin-top: 16px; justify-content: flex-end; }
.upload-row { display: flex; gap: 12px; align-items: center; width: 100%; }
.url-input { flex: 1; }
</style>
