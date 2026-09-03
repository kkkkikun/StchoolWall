<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-head">
        <span>敏感词库（命中即生效：硬违规直接拒绝，灰度转人工）</span>
        <el-button type="primary" @click="openForm()">＋ 添加敏感词</el-button>
      </div>
    </template>

    <el-form inline @submit.prevent>
      <el-form-item label="关键词">
        <el-input v-model="filters.q" placeholder="搜索敏感词" clearable style="width: 200px" @keyup.enter="load(1)" />
      </el-form-item>
      <el-form-item label="级别">
        <el-select v-model="filters.level" clearable placeholder="全部" style="width: 140px">
          <el-option label="硬违规" value="hard" />
          <el-option label="灰度（转人工）" value="gray" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="load(1)">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="items" v-loading="loading">
      <el-table-column label="ID" prop="id" width="80" />
      <el-table-column label="敏感词" prop="word" min-width="180" />
      <el-table-column label="级别" width="150">
        <template #default="{ row }">
          <el-tag :type="row.level === 'hard' ? 'danger' : 'warning'" size="small">
            {{ row.level === 'hard' ? '硬违规' : '灰度' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="添加时间" width="160">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openForm(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!items.length && !loading" description="暂无敏感词" />

    <el-pagination class="pager" layout="total, prev, pager, next" :total="total"
                   v-model:current-page="page" :page-size="pageSize" @change="load()" />

    <el-dialog v-model="showForm" :title="editing ? '编辑敏感词' : '添加敏感词'" width="420px">
      <el-form label-width="70px">
        <el-form-item label="敏感词">
          <el-input v-model="form.word" maxlength="50" placeholder="1-50 字，支持全角/插空格变体命中" />
        </el-form-item>
        <el-form-item label="级别">
          <el-radio-group v-model="form.level">
            <el-radio value="hard">硬违规（直接拒绝）</el-radio>
            <el-radio value="gray">灰度（转人工）</el-radio>
          </el-radio-group>
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
import {
  getSensitiveWords, createSensitiveWord, updateSensitiveWord, deleteSensitiveWord,
  type SensitiveWord,
} from '@/api/moderation'

const filters = reactive<{ q?: string; level?: string }>({})
const items = ref<SensitiveWord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

const showForm = ref(false)
const saving = ref(false)
const editing = ref<SensitiveWord | null>(null)
const form = reactive<{ word: string; level: 'hard' | 'gray' }>({ word: '', level: 'hard' })

const fmtTime = (t: string) => (t ? t.slice(0, 16).replace('T', ' ') : '')

const load = async (targetPage?: number) => {
  if (targetPage) page.value = targetPage
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize }
    if (filters.q) params.q = filters.q
    if (filters.level) params.level = filters.level
    const data = await getSensitiveWords(params)
    items.value = data.items
    total.value = data.total
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const openForm = (row?: SensitiveWord) => {
  editing.value = row ?? null
  form.word = row?.word ?? ''
  form.level = row?.level ?? 'hard'
  showForm.value = true
}

const save = async () => {
  const word = form.word.trim()
  if (!word) {
    ElMessage.warning('敏感词不能为空')
    return
  }
  saving.value = true
  try {
    if (editing.value) await updateSensitiveWord(editing.value.id, { word, level: form.level })
    else await createSensitiveWord({ word, level: form.level })
    ElMessage.success('保存成功')
    showForm.value = false
    load()
  } finally {
    saving.value = false
  }
}

const onDelete = async (row: SensitiveWord) => {
  await ElMessageBox.confirm(`确定删除敏感词「${row.word}」吗？删除后立即生效。`, '确认', { type: 'warning' })
  await deleteSensitiveWord(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(() => load())
</script>

<style scoped>
.card-head { display: flex; align-items: center; justify-content: space-between; }
.pager { margin-top: 16px; justify-content: flex-end; }
</style>
