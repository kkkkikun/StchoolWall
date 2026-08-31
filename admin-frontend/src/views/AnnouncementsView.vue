<template>
  <div>
    <!-- 发送表单 -->
    <el-card shadow="never" class="send-card">
      <template #header><span>发送公告</span></template>
      <el-form label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="form.title" maxlength="100" show-word-limit placeholder="如：系统维护通知" style="width: 480px" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="form.content" type="textarea" :rows="4" maxlength="2000" show-word-limit
                    placeholder="公告正文，将以系统通知发送给用户" style="width: 480px" />
        </el-form-item>
        <el-form-item label="受众">
          <el-radio-group v-model="form.audience">
            <el-radio value="all">全部用户</el-radio>
            <el-radio value="verified">仅认证学生</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="sending" @click="onSend">发送公告</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 历史 -->
    <el-card shadow="never">
      <template #header><span>发送历史</span></template>
      <el-table :data="items" v-loading="loading">
        <el-table-column label="标题" prop="title" min-width="160" />
        <el-table-column label="内容" min-width="280">
          <template #default="{ row }">
            <span class="content-text">{{ row.content }}</span>
          </template>
        </el-table-column>
        <el-table-column label="送达" width="90">
          <template #default="{ row }">{{ row.recipients }} 人</template>
        </el-table-column>
        <el-table-column label="发送时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination class="pager" layout="total, prev, pager, next" :total="total"
                     v-model:current-page="page" :page-size="pageSize" @change="load()" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { sendAnnouncement, getAnnouncements, type Announcement } from '@/api/operations'

const form = reactive({ title: '', content: '', audience: 'all' as 'all' | 'verified' })
const sending = ref(false)

const items = ref<Announcement[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

const fmtTime = (t: string) => (t ? t.slice(0, 16).replace('T', ' ') : '')

const onSend = async () => {
  if (!form.title.trim() || !form.content.trim()) {
    ElMessage.warning('标题和内容必填')
    return
  }
  await ElMessageBox.confirm(
    `确定发送给「${form.audience === 'all' ? '全部用户' : '认证学生'}」吗？发送后不可撤回。`,
    '确认发送', { type: 'warning' },
  )
  sending.value = true
  try {
    const result = await sendAnnouncement(form)
    ElMessage.success(`已发送给 ${result.recipients} 位用户`)
    form.title = ''
    form.content = ''
    load(1)
  } catch { /* 拦截器已提示 */ } finally {
    sending.value = false
  }
}

const load = async (targetPage?: number) => {
  if (targetPage) page.value = targetPage
  loading.value = true
  try {
    const data = await getAnnouncements({ page: page.value, page_size: pageSize })
    items.value = data.items
    total.value = data.total
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

onMounted(() => load())
</script>

<style scoped>
.send-card { margin-bottom: 16px; }
.content-text { color: #606266; font-size: 13px; }
.pager { margin-top: 16px; justify-content: flex-end; }
</style>
