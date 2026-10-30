<template>
  <div>
    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card">
      <el-form inline @submit.prevent>
        <el-form-item label="帖子 ID">
          <el-input v-model.number="filters.id" placeholder="精确 ID" clearable style="width: 110px" @keyup.enter="load(1)" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.q" placeholder="搜索帖子内容" clearable style="width: 180px" @keyup.enter="load(1)" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 120px">
            <el-option v-for="(label, s) in STATUS" :key="s" :label="label" :value="Number(s)" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="filters.post_type" clearable placeholder="全部" style="width: 130px">
            <el-option v-for="(label, t) in TYPES" :key="t" :label="label" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DDTHH:mm:ss[Z]"
                          start-placeholder="开始" end-placeholder="结束" style="width: 240px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load(1)">查询</el-button>
          <el-button @click="reset">重置</el-button>
          <el-button type="success" plain @click="exportCsv">
            导出 CSV
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 批量操作 -->
    <el-card shadow="never">
      <div class="toolbar">
        <span class="selected-tip" v-if="selected.length">已选 {{ selected.length }} 条</span>
        <el-button size="small" type="danger" plain :disabled="!selected.length"
                   @click="onBatch(-1)">批量封禁</el-button>
        <el-button size="small" type="success" plain :disabled="!selected.length"
                   @click="onBatch(1)">批量过审</el-button>
        <el-button size="small" type="warning" plain @click="openCandidates">精华候选</el-button>
      </div>

      <el-table :data="items" @selection-change="(rows: AdminPost[]) => selected = rows" v-loading="loading">
        <el-table-column type="selection" width="44" />
        <el-table-column label="ID" prop="id" width="72" />
        <el-table-column label="内容" min-width="280">
          <template #default="{ row }">
            <div class="content-cell">
              <div class="content-top">
                <span class="pin-flag" v-if="row.is_pinned">置顶</span>
                <span class="featured-flag" v-if="row.is_featured">精华</span>
                <span class="content-text">{{ row.content }}</span>
              </div>
              <!-- 图片画廊预览 -->
              <div v-if="row.images && row.images.length" class="post-thumbs">
                <el-image
                  v-for="(img, idx) in row.images"
                  :key="idx"
                  :src="img"
                  fit="cover"
                  class="thumb-img"
                  :preview-src-list="row.images"
                  :initial-index="idx"
                  preview-teleported
                />
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="作者" width="110" prop="author.nickname" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">{{ TYPES[row.post_type] || row.post_type }}</template>
        </el-table-column>
        <el-table-column label="分类" width="100">
          <template #default="{ row }">{{ row.category || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="88">
          <template #default="{ row }">
            <el-tag :type="STATUS_TAG[row.status]" size="small">{{ STATUS[row.status] || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="互动" width="130">
          <template #default="{ row }">
            <span class="stats-text">👍{{ row.like_count }} 💬{{ row.comment_count }} 👁{{ row.view_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="发布时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="onEdit(row)">编辑</el-button>
            <el-button link :type="row.is_pinned ? 'warning' : 'success'" size="small" @click="onPin(row)">
              {{ row.is_pinned ? '取消置顶' : '置顶' }}
            </el-button>
            <el-button link :type="row.is_featured ? 'warning' : 'success'" size="small" @click="onFeature(row)">
              {{ row.is_featured ? '取消精华' : '设精华' }}
            </el-button>
            <el-button v-if="row.status === 1" link type="danger" size="small" @click="onStatus(row, -1)">封禁</el-button>
            <el-button v-if="row.status === -1" link type="success" size="small" @click="onStatus(row, 1)">恢复</el-button>
            <el-button v-if="row.status === 0" link type="success" size="small" @click="onStatus(row, 1)">过审</el-button>
            <el-button v-if="row.status === 0" link type="danger" size="small" @click="onStatus(row, -1)">拒审</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination class="pager" layout="total, prev, pager, next, sizes" :total="total"
                     v-model:current-page="page" v-model:page-size="pageSize"
                     :page-sizes="[10, 20, 50]" @change="load()" />
    </el-card>

    <!-- 精华候选弹窗 -->
    <el-dialog v-model="showCandidates" title="精华候选（按互动排序，未设精）" width="640px">
      <el-table :data="candidates" v-loading="loadingCandidates" size="small">
        <el-table-column label="ID" prop="id" width="70" />
        <el-table-column label="内容" min-width="240">
          <template #default="{ row }"><span class="content-text">{{ row.content }}</span></template>
        </el-table-column>
        <el-table-column label="互动" width="150">
          <template #default="{ row }">
            <span class="stats-text">👍{{ row.like_count }} 💬{{ row.comment_count }} 👁{{ row.view_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="success" size="small" @click="adoptCandidate(row)">设为精华</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showCandidates = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="showEdit" title="编辑帖子" width="560px">
      <el-form label-width="70px">
        <el-form-item label="内容">
          <el-input v-model="editForm.content" type="textarea" :rows="5" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="editForm.category" maxlength="20" placeholder="如：校园广场" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getPosts, updatePostStatus, pinPost, featurePost, getFeatureCandidates, editPost, batchPostStatus, exportPosts, type AdminPost } from '@/api/posts'

import { useRoute } from 'vue-router'
const route = useRoute()

const STATUS: Record<number, string> = { '-2': '已删除', '-1': '已封禁', 0: '待审核', 1: '正常', 2: '已归档' }
const STATUS_TAG: Record<number, string> = { '-2': 'info', '-1': 'danger', 0: 'warning', 1: 'success', 2: 'info' }
const TYPES: Record<string, string> = {
  general: '动态', lost_found: '失物招领', second_hand: '二手', carpool: '拼车', advertisement: '广告',
}

const filters = reactive<{ q?: string; status?: number; post_type?: string; id?: number }>({})
const range = ref<[string, string] | null>(null)
const items = ref<AdminPost[]>([])
const selected = ref<AdminPost[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const showEdit = ref(false)
const saving = ref(false)
const editForm = reactive({ id: 0, content: '', category: '' })

const fmtTime = (t: string) => (t ? t.slice(0, 16).replace('T', ' ') : '')

const load = async (targetPage?: number) => {
  if (targetPage) page.value = targetPage
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: page.value, page_size: pageSize.value,
    }
    if (filters.id) params.post_id = filters.id
    if (filters.q) params.q = filters.q
    if (filters.status !== undefined && filters.status !== null) params.status = filters.status
    if (filters.post_type) params.post_type = filters.post_type
    if (range.value) {
      params.time_start = range.value[0]
      params.time_end = range.value[1]
    }
    const data = await getPosts(params)
    items.value = data.items
    total.value = data.total
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const reset = () => {
  filters.id = undefined
  filters.q = undefined
  filters.status = undefined
  filters.post_type = undefined
  range.value = null
  load(1)
}

const onStatus = async (row: AdminPost, status: number) => {
  const label = status === 1 ? (row.status === 0 ? '通过' : '恢复') : (row.status === 0 ? '拒绝' : '封禁')
  await ElMessageBox.confirm(`确定${label}帖子 #${row.id} 吗？`, '确认', { type: 'warning' })
  await updatePostStatus(row.id, status)
  ElMessage.success(`已${label}`)
  load()
}

const onPin = async (row: AdminPost) => {
  await pinPost(row.id, !row.is_pinned)
  ElMessage.success(row.is_pinned ? '已取消置顶' : '已置顶')
  load()
}

const onFeature = async (row: AdminPost) => {
  await featurePost(row.id, !row.is_featured)
  ElMessage.success(row.is_featured ? '已取消精华' : '已设为精华')
  load()
}

const showCandidates = ref(false)
const candidates = ref<AdminPost[]>([])
const loadingCandidates = ref(false)

const openCandidates = async () => {
  showCandidates.value = true
  loadingCandidates.value = true
  try {
    const data = await getFeatureCandidates()
    candidates.value = data.items
  } catch { /* 拦截器已提示 */ } finally {
    loadingCandidates.value = false
  }
}

const adoptCandidate = async (row: AdminPost) => {
  await featurePost(row.id, true)
  ElMessage.success(`帖子 #${row.id} 已设为精华`)
  candidates.value = candidates.value.filter(c => c.id !== row.id)
  load()
}

const onBatch = async (status: number) => {
  const ids = selected.value.map(p => p.id)
  const label = status === 1 ? '过审' : '封禁'
  await ElMessageBox.confirm(`确定批量${label} ${ids.length} 条帖子吗？`, '确认', { type: 'warning' })
  const result = await batchPostStatus(ids, status)
  ElMessage.success(`成功 ${result.succeeded.length} 条，失败 ${result.failed.length} 条`)
  load()
}

const onEdit = (row: AdminPost) => {
  editForm.id = row.id
  editForm.content = row.content
  editForm.category = row.category || ''
  showEdit.value = true
}

const saveEdit = async () => {
  if (!editForm.content.trim()) {
    ElMessage.warning('内容不能为空')
    return
  }
  saving.value = true
  try {
    await editPost(editForm.id, { content: editForm.content, category: editForm.category || undefined })
    ElMessage.success('已保存')
    showEdit.value = false
    load()
  } catch { /* 拦截器已提示 */ } finally {
    saving.value = false
  }
}

const exportCsv = async () => {
  try {
    const blob = await exportPosts(filters.status, filters.q)
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `posts-${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
    ElMessage.success('已导出')
  } catch {
    ElMessage.error('导出失败')
  }
}

onMounted(() => {
  if (route.query.post_id) {
    filters.id = Number(route.query.post_id)
  }
  load()
})
</script>

<style scoped>
.filter-card { margin-bottom: 16px; }
.toolbar { margin-bottom: 12px; display: flex; align-items: center; gap: 12px; }
.selected-tip { font-size: 13px; color: var(--el-color-primary); }
.content-cell { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; }
.content-top { display: flex; align-items: flex-start; gap: 6px; }
.post-thumbs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.thumb-img {
  width: 50px;
  height: 50px;
  border-radius: 4px;
  border: 1px solid var(--el-border-color-lighter);
}
.pin-flag {
  flex-shrink: 0;
  font-size: 11px; color: #fff; background: var(--el-color-primary);
  padding: 1px 6px; border-radius: 4px; margin-top: 2px;
}
.featured-flag {
  flex-shrink: 0;
  font-size: 11px; color: var(--el-color-primary-dark-2); background: var(--el-color-primary-light-9); border: 1px solid var(--el-color-primary-light-7);
  padding: 0 6px; border-radius: 4px; margin-top: 2px;
}
.content-text { color: var(--el-text-color-primary); }
.stats-text { font-size: 12px; color: var(--el-text-color-secondary); }
.pager { margin-top: 16px; justify-content: flex-end; }

/* 窄屏适配：固定像素宽的弹窗在 ≤560px 视口下会溢出，统一限宽 */
:deep(.el-dialog) { max-width: 92vw; }
</style>
