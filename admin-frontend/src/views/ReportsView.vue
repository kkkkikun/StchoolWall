<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-row">
        <span>待处理举报</span>
        <el-radio-group v-model="statusFilter" size="small" @change="() => load(1)">
          <el-radio-button value="pending">待处理</el-radio-button>
          <el-radio-button value="">全部</el-radio-button>
        </el-radio-group>
      </div>
    </template>

    <el-table :data="items" v-loading="loading">
      <el-table-column label="ID" prop="id" width="70" />
      <el-table-column label="举报人" prop="reporter.nickname" width="110" />
      <el-table-column label="理由" width="120">
        <template #default="{ row }">
          <el-tag type="danger" size="small">{{ row.reason }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="被举报内容" min-width="260">
        <template #default="{ row }">
          <div class="post-preview-cell">
            <el-image
              v-if="row.post_images && row.post_images.length"
              :src="row.post_images[0]"
              :preview-src-list="row.post_images"
              preview-teleported
              fit="cover"
              class="post-mini-thumb"
            />
            <div class="post-meta-text">
              <div class="post-content">{{ row.post_content }}</div>
              <div class="post-desc" v-if="row.description">举报补充：{{ row.description }}</div>
            </div>
          </div>
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
      <el-table-column label="处理状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'pending' ? 'warning' : 'info'" size="small">
            {{ row.status === 'pending' ? '待处理' : row.status === 'dismissed' ? '已驳回' : '已处理' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openDrawer(row as AdminReport)">查看原帖</el-button>
          <template v-if="row.status === 'pending'">
            <el-button link type="info" size="small" @click="onHandle(row as AdminReport, 'dismiss')">驳回</el-button>
            <el-button link type="danger" size="small" @click="onHandle(row as AdminReport, 'ban_post')">封帖</el-button>
            <el-button link type="danger" size="small" @click="onHandle(row as AdminReport, 'ban_user')">封号</el-button>
          </template>
          <span v-else class="done-text">—</span>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-bar" v-if="total > 0">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        @change="() => load()"
      />
    </div>

    <!-- 原帖图文审查抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :title="`原帖审查 - 帖子 #${selectedReport?.post_id || ''}`"
      size="520px"
      destroy-on-close
    >
      <div v-if="selectedReport" class="drawer-body">
        <el-alert
          :title="`被举报理由：${selectedReport.reason}`"
          :description="selectedReport.description ? `说明：${selectedReport.description}` : '举报人未提供额外补充说明'"
          type="error"
          show-icon
          :closable="false"
          class="report-alert"
        />

        <div class="section-title">帖子信息</div>
        <div class="post-info-box">
          <div class="info-row">
            <span class="info-label">发布作者：</span>
            <span class="info-value font-bold">{{ selectedReport.author?.nickname || '未知用户' }} (ID: {{ selectedReport.author?.id || '—' }})</span>
          </div>
          <div class="info-row">
            <span class="info-label">举报人：</span>
            <span class="info-value">{{ selectedReport.reporter.nickname }} (ID: {{ selectedReport.reporter.id }})</span>
          </div>
          <div class="info-row">
            <span class="info-label">当前状态：</span>
            <el-tag :type="selectedReport.post_status === 1 ? 'success' : 'danger'" size="small">
              {{ selectedReport.post_status === 1 ? '正常展示中' : '已被封禁/处理' }}
            </el-tag>
          </div>
          <div class="info-row" v-if="selectedReport.post_category">
            <span class="info-label">所属分类：</span>
            <el-tag size="small">{{ selectedReport.post_category }}</el-tag>
          </div>
        </div>

        <div class="section-title">原帖正文内容</div>
        <div class="post-full-text">
          {{ selectedReport.post_full_content || selectedReport.post_content }}
        </div>

        <div class="section-title" v-if="selectedReport.post_images && selectedReport.post_images.length">
          原帖配图 ({{ selectedReport.post_images.length }} 张，点击放大)
        </div>
        <div class="post-images-grid" v-if="selectedReport.post_images && selectedReport.post_images.length">
          <el-image
            v-for="(img, idx) in selectedReport.post_images"
            :key="idx"
            :src="img"
            :preview-src-list="selectedReport.post_images"
            :initial-index="idx"
            preview-teleported
            fit="cover"
            class="drawer-img"
          />
        </div>

        <div class="drawer-actions" v-if="selectedReport.status === 'pending'">
          <div class="section-title">审查处置</div>
          <div class="action-btn-group">
            <el-button type="info" @click="onHandle(selectedReport, 'dismiss')">驳回举报（不违规）</el-button>
            <el-button type="danger" plain @click="onHandle(selectedReport, 'ban_post')">违规封禁帖子</el-button>
            <el-button type="danger" @click="onHandle(selectedReport, 'ban_user')">封帖并封禁作者</el-button>
          </div>
        </div>
      </div>
    </el-drawer>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getReports, handleReport, type AdminReport } from '@/api/reports'

const items = ref<AdminReport[]>([])
const statusFilter = ref('pending')
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const drawerVisible = ref(false)
const selectedReport = ref<AdminReport | null>(null)

const fmtTime = (t: string) => (t ? t.slice(0, 16).replace('T', ' ') : '')

const load = async (targetPage?: number) => {
  if (targetPage) page.value = targetPage
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (statusFilter.value) params.status = statusFilter.value
    const data = await getReports(params)
    items.value = data.items
    total.value = data.total ?? data.items.length
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const openDrawer = (row: AdminReport) => {
  selectedReport.value = row
  drawerVisible.value = true
}

const onHandle = async (row: AdminReport, action: 'dismiss' | 'ban_post' | 'ban_user') => {
  const labels = { dismiss: '驳回该举报（判定帖子合规）', ban_post: '封禁该帖子', ban_user: '封禁帖子并冻结作者' }
  await ElMessageBox.confirm(`确定要「${labels[action]}」吗？`, '确认操作', { type: 'warning' })
  await handleReport(row.id, action)
  ElMessage.success('处理成功')
  drawerVisible.value = false
  load()
}

onMounted(() => load())
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.post-preview-cell { display: flex; align-items: flex-start; gap: 10px; }
.post-mini-thumb { width: 44px; height: 44px; border-radius: 4px; flex-shrink: 0; }
.post-meta-text { flex: 1; min-width: 0; }
.post-content { color: var(--el-text-color-primary); line-height: 1.4; word-break: break-all; }
.post-desc { font-size: 12px; color: var(--el-color-danger); margin-top: 4px; }
.done-text { color: var(--el-text-color-placeholder); }
.pagination-bar { margin-top: 20px; display: flex; justify-content: flex-end; }

/* 抽屉样式 */
.drawer-body { display: flex; flex-direction: column; gap: 16px; }
.report-alert { margin-bottom: 8px; }
.section-title { font-size: 14px; font-weight: bold; color: var(--el-text-color-primary); border-left: 3px solid var(--el-color-primary); padding-left: 8px; }
.post-info-box { background: var(--el-fill-color-light); border-radius: 6px; padding: 12px; display: flex; flex-direction: column; gap: 8px; font-size: 13px; }
.info-row { display: flex; align-items: center; }
.info-label { color: var(--el-text-color-secondary); width: 80px; flex-shrink: 0; }
.info-value { color: var(--el-text-color-primary); }
.font-bold { font-weight: 600; }
.post-full-text { font-size: 14px; color: var(--el-text-color-primary); line-height: 1.6; background: var(--el-fill-color-lighter); padding: 14px; border-radius: 6px; white-space: pre-wrap; word-break: break-all; }
.post-images-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.drawer-img { width: 100%; height: 110px; border-radius: 6px; }
.drawer-actions { margin-top: 10px; display: flex; flex-direction: column; gap: 12px; }
.action-btn-group { display: flex; flex-direction: column; gap: 8px; }

/* 窄屏适配：固定 520px 抽屉在 <520px 视口下会溢出，统一限宽 */
:deep(.el-drawer) { max-width: 92vw; }
</style>
