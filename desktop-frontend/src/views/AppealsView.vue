<script setup lang="ts">
/**
 * 申诉与处理记录。
 *
 * 只能申诉自己的内容：帖子 / 评论 / 组局的编号，或学生证认证申请编号。
 * 申诉被受理也不会直接改变内容状态，恢复内容仍需在对应审核页确认。
 */
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import EmptyState from '@/components/EmptyState.vue'
import { getAppeals, submitAppeal } from '@/api/appeals'
import type { AppealRecord, AppealStatus, AppealType } from '@/api/types'

const route = useRoute()

const TYPES: { value: AppealType; label: string }[] = [
  { value: 'post', label: '帖子' },
  { value: 'comment', label: '评论' },
  { value: 'party', label: '组局' },
  { value: 'verification', label: '学生证认证' },
]

const TYPE_LABELS: Record<AppealType, string> = {
  post: '帖子',
  comment: '评论',
  party: '组局',
  verification: '学生证认证',
}

const STATUS_LABELS: Record<AppealStatus, string> = {
  pending: '待处理',
  accepted: '申诉已受理',
  rejected: '申诉未通过',
}

const entityType = ref<AppealType>('post')
const entityId = ref('')
const reason = ref('')
const items = ref<AppealRecord[]>([])
const page = ref(1)
const saving = ref(false)
const loading = ref(true)

function showError(error: unknown): void {
  ElMessage.error(error instanceof Error ? error.message : '操作失败')
}

async function load(newPage = 1): Promise<void> {
  loading.value = true
  try {
    const data = await getAppeals(newPage)
    items.value = newPage === 1 ? data.items : [...items.value, ...data.items]
    page.value = newPage
  } catch (error) {
    showError(error)
  } finally {
    loading.value = false
  }
}

async function submit(): Promise<void> {
  if (!entityId.value.trim() || reason.value.trim().length < 5) {
    showError(new Error('请填写对象编号和至少 5 字的申诉理由'))
    return
  }
  if (saving.value) return
  saving.value = true
  try {
    await submitAppeal(entityType.value, entityId.value.trim(), reason.value.trim())
    reason.value = ''
    ElMessage.success('申诉已提交')
    await load()
  } catch (error) {
    showError(error)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  const type = String(route.query.type ?? '')
  const matched = TYPES.find((item) => item.value === type)
  if (matched) entityType.value = matched.value
  if (route.query.id) entityId.value = String(route.query.id)
  load()
})
</script>

<template>
  <div class="sw-appeals">
    <div class="sw-card sw-appeals__head">
      <h3 class="sw-card__title">申诉与处理记录</h3>
      <p class="sw-muted">
        仅可申诉自己的待审或受限制内容。请描述理由，勿填写密码、找回码、姓名或完整学号。
      </p>
    </div>

    <section class="sw-card sw-appeals__form">
      <el-form label-width="96px">
        <el-form-item label="申诉对象">
          <el-select v-model="entityType">
            <el-option v-for="item in TYPES" :key="item.value" :value="item.value" :label="item.label" />
          </el-select>
        </el-form-item>
        <el-form-item label="对象编号">
          <el-input v-model="entityId" maxlength="64" placeholder="帖子 / 评论 / 组局 / 认证申请编号" />
        </el-form-item>
        <el-form-item label="申诉理由">
          <el-input
            v-model="reason"
            type="textarea"
            :rows="4"
            maxlength="1000"
            show-word-limit
            placeholder="申诉理由（5–1000 字）"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="submit">提交申诉</el-button>
        </el-form-item>
      </el-form>
    </section>

    <div class="sw-card sw-appeals__records">
      <h3 class="sw-card__title">我的申诉</h3>
      <div v-loading="loading" class="sw-appeals__list">
        <article v-for="item in items" :key="item.id" class="sw-appeals__record">
          <p class="sw-appeals__record-title">
            {{ TYPE_LABELS[item.entityType] }} ·
            <el-tag size="small" effect="plain" :type="item.status === 'accepted' ? 'success' : 'info'">
              {{ STATUS_LABELS[item.status] }}
            </el-tag>
          </p>
          <p class="sw-muted">编号 {{ item.entityId }}</p>
          <p class="sw-appeals__reason">{{ item.reason }}</p>
          <p v-if="item.decisionReason" class="sw-muted">处理说明：{{ item.decisionReason }}</p>
        </article>
        <EmptyState v-if="!loading && !items.length" text="暂无申诉记录" />
      </div>
      <el-button v-if="items.length >= 20" :loading="loading" @click="load(page + 1)">加载更多</el-button>
    </div>
  </div>
</template>

<style scoped>
.sw-appeals {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-appeals__head {
  padding: var(--sw-space-4) var(--sw-space-5);
}

.sw-appeals__head p {
  margin: var(--sw-space-1) 0 0;
}

.sw-appeals__form {
  padding: var(--sw-space-5);
}

.sw-appeals__records {
  padding: var(--sw-space-4) var(--sw-space-5);
}

.sw-appeals__list {
  margin-top: var(--sw-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-3);
  min-height: 120px;
}

.sw-appeals__record {
  padding-bottom: var(--sw-space-3);
  border-bottom: 1px solid var(--sw-border);
}

.sw-appeals__record:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.sw-appeals__record-title {
  margin: 0 0 var(--sw-space-1);
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: var(--sw-space-2);
}

.sw-appeals__reason {
  margin: var(--sw-space-1) 0;
  color: var(--sw-text-secondary);
  white-space: pre-wrap;
}
</style>
