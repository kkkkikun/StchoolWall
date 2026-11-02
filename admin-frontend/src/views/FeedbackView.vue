<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-row">
        <div class="header-left">
          <span class="header-title">内部测试反馈</span>
          <el-tag type="danger" size="large" effect="dark" class="open-badge">
            未处理 {{ stats.open }} 条
          </el-tag>
        </div>
        <el-button :icon="Refresh" :loading="loading" @click="refresh">刷新</el-button>
      </div>
    </template>

    <!-- 状态概览：负责人最先看的是未处理条数 -->
    <div class="stat-strip">
      <div
        v-for="card in statCards"
        :key="card.key"
        class="stat-card"
        :class="{ 'is-open': card.key === 'open' }"
      >
        <div class="stat-value">{{ card.value }}</div>
        <div class="stat-label">{{ card.label }}</div>
      </div>
    </div>

    <!-- 筛选区 -->
    <div class="filter-bar">
      <el-select v-model="filters.status" class="filter-select" @change="onFilterChange">
        <el-option label="全部状态" value="" />
        <el-option v-for="(label, value) in STATUS_LABEL" :key="value" :label="label" :value="value" />
      </el-select>
      <el-select v-model="filters.category" class="filter-select" @change="onFilterChange">
        <el-option label="全部类型" value="" />
        <el-option v-for="(label, value) in CATEGORY_LABEL" :key="value" :label="label" :value="value" />
      </el-select>
      <el-input
        v-model="filters.keyword"
        class="filter-keyword"
        placeholder="搜索标题或描述"
        clearable
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-button type="primary" @click="onFilterChange">搜索</el-button>
    </div>

    <el-table
      :data="items"
      v-loading="loading"
      row-class-name="clickable-row"
      @row-click="openDetail"
    >
      <el-table-column label="编号" prop="id" width="80" />
      <el-table-column label="类型" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="categoryType(row.category)">{{ categoryLabel(row.category) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="严重程度" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="severityType(row.severity)">{{ severityLabel(row.severity) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="标题" prop="title" min-width="220" show-overflow-tooltip />
      <el-table-column label="提交人" width="130">
        <template #default="{ row }">{{ row.reporter_name || '匿名' }}</template>
      </el-table-column>
      <el-table-column label="截图" width="80" align="center">
        <template #default="{ row }">{{ row.screenshot_count || '—' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="提交时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>

      <template #empty>
        <el-empty description="还没有收到反馈。用户在客户端提交反馈后会出现在这里。" />
      </template>
    </el-table>

    <div class="pagination-bar" v-if="total > 0">
      <el-pagination
        v-model:current-page="page"
        :page-size="PAGE_SIZE"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :title="`反馈详情 #${detail?.id ?? ''}`"
      size="620px"
      custom-class="feedback-drawer"
      destroy-on-close
      @closed="onDrawerClosed"
    >
      <div class="drawer-body" v-loading="detailLoading">
        <template v-if="detail">
          <div class="section-title">反馈内容</div>
          <div class="content-box">{{ detail.content }}</div>

          <div class="section-title">环境信息</div>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="页面 URL">{{ detail.page_url || '—' }}</el-descriptions-item>
            <el-descriptions-item label="路由">{{ detail.route || '—' }}</el-descriptions-item>
            <el-descriptions-item label="视口">{{ detail.viewport || '—' }}</el-descriptions-item>
            <el-descriptions-item label="主题">{{ detail.theme || '—' }}</el-descriptions-item>
            <el-descriptions-item label="客户端版本">{{ detail.app_version || '—' }}</el-descriptions-item>
            <el-descriptions-item label="客户端 IP">{{ detail.client_ip || '—' }}</el-descriptions-item>
            <el-descriptions-item label="提交时间">{{ fmtTime(detail.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="处理时间">{{ fmtTime(detail.handled_at) }}</el-descriptions-item>
            <el-descriptions-item label="User Agent">
              <span class="ua-text">{{ detail.user_agent || '—' }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <div class="section-title">诊断日志</div>
          <pre class="diagnostics-box">{{ diagnosticsText }}</pre>

          <div class="section-title">截图（{{ detail.screenshots.length }} 张，点击放大）</div>
          <div v-if="shotUrls.length" class="shot-grid">
            <el-image
              v-for="(url, idx) in shotUrls"
              :key="url"
              :src="url"
              :preview-src-list="shotUrls"
              :initial-index="idx"
              preview-teleported
              fit="cover"
              class="shot-item"
            />
          </div>
          <div v-else class="empty-hint">这条反馈没有附带截图</div>

          <div class="section-title">处理</div>
          <div class="handle-row">
            <el-select v-model="form.status" class="status-select">
              <el-option v-for="(label, value) in STATUS_LABEL" :key="value" :label="label" :value="value" />
            </el-select>
            <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          </div>
          <el-input
            v-model="form.note"
            type="textarea"
            :rows="4"
            maxlength="2000"
            show-word-limit
            placeholder="处理备注（最多 2000 字）"
          />
        </template>
      </div>
    </el-drawer>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import {
  getFeedbackDetail,
  getFeedbackList,
  getFeedbackScreenshot,
  getFeedbackStats,
  updateFeedback,
  type FeedbackCategory,
  type FeedbackDetail,
  type FeedbackItem,
  type FeedbackSeverity,
  type FeedbackStats,
  type FeedbackStatus,
} from '@/api/feedback'

/** 后端分页固定 20 条且不接收 page_size，这里保持一致。 */
const PAGE_SIZE = 20

const STATUS_LABEL: Record<FeedbackStatus, string> = {
  open: '待处理',
  handling: '处理中',
  resolved: '已解决',
  closed: '已关闭',
}

const CATEGORY_LABEL: Record<FeedbackCategory, string> = {
  bug: 'Bug',
  ui: 'UI 体验',
  feature: '功能建议',
  other: '其他',
}

const SEVERITY_LABEL: Record<FeedbackSeverity, string> = {
  low: '低',
  medium: '中',
  high: '高',
}

const items = ref<FeedbackItem[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const stats = ref<FeedbackStats>({ open: 0, handling: 0, resolved: 0, closed: 0, total: 0 })
const filters = reactive({ status: '', category: '', keyword: '' })

const drawerVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<FeedbackDetail | null>(null)
const shotUrls = ref<string[]>([])
const saving = ref(false)
const form = reactive<{ status: FeedbackStatus; note: string }>({ status: 'open', note: '' })

const statCards = computed(() => [
  { key: 'open', label: '待处理', value: stats.value.open },
  { key: 'handling', label: '处理中', value: stats.value.handling },
  { key: 'resolved', label: '已解决', value: stats.value.resolved },
  { key: 'closed', label: '已关闭', value: stats.value.closed },
  { key: 'total', label: '累计', value: stats.value.total },
])

const diagnosticsText = computed(() => {
  const diag = detail.value?.diagnostics
  return diag ? JSON.stringify(diag, null, 2) : '（这条反馈没有附带诊断数据）'
})

/** 后端存 UTC ISO 时间：转本地时区再截到分钟，避免管理端看到的时间比实际晚 8 小时。 */
const fmtTime = (t: string | null) => {
  if (!t) return '—'
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t.slice(0, 16).replace('T', ' ')
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const statusType = (s: FeedbackStatus) =>
  s === 'open' ? 'danger' : s === 'handling' ? 'warning' : s === 'resolved' ? 'success' : 'info'

const categoryType = (c: FeedbackCategory) => (c === 'bug' ? 'danger' : c === 'feature' ? 'success' : 'info')

const severityType = (s: FeedbackSeverity) => (s === 'high' ? 'danger' : s === 'medium' ? 'warning' : 'info')

// 后端可能返回枚举外的值：回退成原值而不是渲染成空白
const statusLabel = (s: FeedbackStatus) => STATUS_LABEL[s] ?? s
const categoryLabel = (c: FeedbackCategory) => CATEGORY_LABEL[c] ?? c
const severityLabel = (s: FeedbackSeverity) => SEVERITY_LABEL[s] ?? s

const load = async (targetPage?: number) => {
  if (targetPage) page.value = targetPage
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value }
    if (filters.status) params.status = filters.status
    if (filters.category) params.category = filters.category
    if (filters.keyword.trim()) params.keyword = filters.keyword.trim()
    const data = await getFeedbackList(params)
    items.value = data.items ?? []
    total.value = data.total ?? 0
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    stats.value = await getFeedbackStats()
  } catch { /* 拦截器已提示 */ }
}

const refresh = async () => {
  await Promise.all([load(), loadStats()])
}

const onFilterChange = () => {
  page.value = 1
  load()
}

const releaseShotUrls = () => {
  shotUrls.value.forEach((url) => URL.revokeObjectURL(url))
  shotUrls.value = []
}

const loadShotUrls = async (item: FeedbackDetail) => {
  const urls: string[] = []
  for (let i = 0; i < item.screenshots.length; i += 1) {
    try {
      const blob = await getFeedbackScreenshot(item.id, i)
      urls.push(URL.createObjectURL(blob))
    } catch { /* 单张截图失败不阻断其它截图 */ }
  }
  // 详情可能已被切换：过期 URL 直接回收，不覆盖当前详情
  if (detail.value?.id !== item.id) {
    urls.forEach((url) => URL.revokeObjectURL(url))
    return
  }
  shotUrls.value = urls
}

const openDetail = async (row: FeedbackItem) => {
  drawerVisible.value = true
  detailLoading.value = true
  detail.value = null
  releaseShotUrls()
  try {
    const data = await getFeedbackDetail(row.id)
    detail.value = data
    form.status = data.status
    form.note = data.note ?? ''
    await loadShotUrls(data)
  } catch { /* 拦截器已提示 */ } finally {
    detailLoading.value = false
  }
}

const save = async () => {
  if (!detail.value) return
  saving.value = true
  try {
    const updated = await updateFeedback(detail.value.id, { status: form.status, note: form.note })
    detail.value = { ...detail.value, ...updated }
    ElMessage.success('已保存处理结果')
    await refresh()
  } catch { /* 拦截器已提示 */ } finally {
    saving.value = false
  }
}

const onDrawerClosed = () => {
  releaseShotUrls()
  detail.value = null
}

onMounted(refresh)
</script>

<style scoped>
.header-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.header-left { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.header-title { font-size: 15px; font-weight: 600; color: var(--el-text-color-primary); }
.open-badge { font-size: 14px; font-weight: 600; }

.stat-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}
.stat-card {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  padding: 10px 12px;
  text-align: center;
}
.stat-card.is-open {
  background: var(--el-color-danger-light-9);
  border-color: var(--el-color-danger-light-7);
}
.stat-value { font-size: 20px; font-weight: 700; color: var(--el-text-color-primary); line-height: 1.3; }
.stat-card.is-open .stat-value { color: var(--el-color-danger); }
.stat-label { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px; }

.filter-bar { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }
.filter-select { width: 150px; }
.filter-keyword { width: 260px; }

:deep(.clickable-row) { cursor: pointer; }
.pagination-bar { margin-top: 16px; display: flex; justify-content: flex-end; }

.drawer-body { display: flex; flex-direction: column; gap: 14px; }
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  border-left: 3px solid var(--el-color-primary);
  padding-left: 8px;
}
.content-box {
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-primary);
  background: var(--el-fill-color-lighter);
  border-radius: 4px;
  padding: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}
.ua-text { font-size: 12px; word-break: break-all; color: var(--el-text-color-regular); }
.diagnostics-box {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  padding: 12px;
  margin: 0;
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
.shot-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.shot-item { width: 100%; height: 120px; border-radius: 4px; }
.empty-hint { font-size: 13px; color: var(--el-text-color-secondary); }
.handle-row { display: flex; align-items: center; gap: 10px; }
.status-select { width: 160px; }

/* 窄屏适配：固定 620px 抽屉在小视口下会溢出，统一限宽 */
@media (max-width: 900px) {
  .stat-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .filter-keyword { width: 100%; }
}
</style>

<!-- 抽屉被 teleport 到 body，scoped 选择器够不到：限宽规则放在全局并用独立类名限定在本页 -->
<style>
.feedback-drawer { max-width: 94vw; }
</style>
