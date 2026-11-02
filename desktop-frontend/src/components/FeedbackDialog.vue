<script setup lang="ts">
/**
 * 快速反馈弹窗。
 *
 * 面向内部测试人员：类型 + 标题 + 描述 + 截图 + 一键附带"当时的现场"（诊断日志）。
 * 未登录时用内部测试口令提交，避免测试人员必须先注册账号。
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Camera, ChatDotRound, WarningFilled } from '@element-plus/icons-vue'
import type { UploadFile, UploadFiles } from 'element-plus'

import { useAuthStore } from '@/stores/auth'
import {
  createFeedback,
  uploadFeedbackScreenshot,
  type FeedbackCategory,
  type FeedbackSeverity,
} from '@/api/feedback'
import { collectDiagnostics, diagnosticsCount } from '@/utils/diagnostics'

const visible = defineModel<boolean>({ default: false })

const auth = useAuthStore()

const CATEGORY_OPTIONS: { value: FeedbackCategory; label: string; hint: string }[] = [
  { value: 'bug', label: '功能异常', hint: '报错、卡住、数据不对' },
  { value: 'ui', label: '界面问题', hint: '排版、配色、样式错乱' },
  { value: 'feature', label: '功能建议', hint: '希望增加的能力' },
  { value: 'other', label: '其他', hint: '说不清归到哪类' },
]

const SEVERITY_OPTIONS: { value: FeedbackSeverity; label: string }[] = [
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
]

const category = ref<FeedbackCategory>('bug')
const severity = ref<FeedbackSeverity>('medium')
const title = ref('')
const content = ref('')
const testCode = ref('')
const reporterName = ref('')
const withDiagnostics = ref(true)
const files = ref<UploadFiles>([])
const submitting = ref(false)

const diagCount = ref(0)

const canSubmit = computed(
  () =>
    title.value.trim().length > 0 &&
    content.value.trim().length > 0 &&
    (auth.loggedIn || testCode.value.trim().length > 0),
)

watch(visible, (open) => {
  if (open) diagCount.value = diagnosticsCount()
})

function handleChange(_file: UploadFile, list: UploadFiles): void {
  files.value = list.slice(0, 5)
}

function handleRemove(_file: UploadFile, list: UploadFiles): void {
  files.value = list.slice(0, 5)
}

function reset(): void {
  category.value = 'bug'
  severity.value = 'medium'
  title.value = ''
  content.value = ''
  testCode.value = ''
  reporterName.value = ''
  withDiagnostics.value = true
  files.value = []
}

async function uploadScreenshots(feedbackId: number, uploadToken: string): Promise<number> {
  let uploaded = 0
  for (const item of files.value) {
    if (!item.raw) continue
    try {
      await uploadFeedbackScreenshot(feedbackId, uploadToken, item.raw)
      uploaded += 1
    } catch {
      // 单张失败不阻断其余截图，失败数量在提交结果里如实告知
    }
  }
  return uploaded
}

async function submit(): Promise<void> {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  try {
    const created = await createFeedback({
      category: category.value,
      severity: severity.value,
      title: title.value.trim(),
      content: content.value.trim(),
      page_url: window.location.href.slice(0, 500),
      route: window.location.pathname.slice(0, 120),
      viewport: `${window.innerWidth}x${window.innerHeight}`,
      theme: document.documentElement.classList.contains('theme-dark') ? 'dark' : 'light',
      app_version: 'pc',
      test_code: auth.loggedIn ? '' : testCode.value.trim(),
      reporter_name: auth.loggedIn ? '' : reporterName.value.trim(),
      diagnostics: withDiagnostics.value ? collectDiagnostics() : undefined,
    })
    const uploaded = await uploadScreenshots(created.id, created.upload_token)
    const failed = files.value.length - uploaded
    visible.value = false
    reset()
    if (failed > 0) {
      ElMessage.warning(`反馈 #${created.id} 已收到，但有 ${failed} 张截图没传上去`)
    } else {
      ElMessage.success(`反馈 #${created.id} 已收到，感谢反馈`)
    }
  } catch (error) {
    ElMessage.error((error as Error).message || '提交失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="意见反馈" width="640px" :close-on-click-modal="false">
    <div class="sw-fb">
      <div class="sw-fb__row">
        <span class="sw-fb__label">类型</span>
        <el-radio-group v-model="category" size="default">
          <el-radio-button v-for="option in CATEGORY_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </el-radio-button>
        </el-radio-group>
      </div>
      <p class="sw-muted sw-fb__hint">{{ CATEGORY_OPTIONS.find((o) => o.value === category)?.hint }}</p>

      <div class="sw-fb__row">
        <span class="sw-fb__label">严重程度</span>
        <el-radio-group v-model="severity">
          <el-radio v-for="option in SEVERITY_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </el-radio>
        </el-radio-group>
      </div>

      <el-form label-position="top" class="sw-fb__form">
        <el-form-item label="标题">
          <el-input v-model="title" maxlength="120" show-word-limit placeholder="一句话说明问题" />
        </el-form-item>
        <el-form-item label="详细描述">
          <el-input
            v-model="content"
            type="textarea"
            :rows="5"
            maxlength="4000"
            show-word-limit
            placeholder="什么操作触发的？预期是什么？实际发生了什么？"
          />
        </el-form-item>
      </el-form>

      <div class="sw-fb__row sw-fb__row--top">
        <span class="sw-fb__label">
          <el-icon><Camera /></el-icon>
          截图（最多 5 张）
        </span>
        <el-upload
          class="sw-fb__upload"
          :auto-upload="false"
          :limit="5"
          list-type="picture-card"
          accept="image/*"
          :on-change="handleChange"
          :on-remove="handleRemove"
        >
          <el-icon><Camera /></el-icon>
        </el-upload>
      </div>

      <div class="sw-fb__row sw-fb__row--top">
        <span class="sw-fb__label">
          <el-icon><ChatDotRound /></el-icon>
          附带诊断信息
        </span>
        <div class="sw-fb__diag">
          <el-switch v-model="withDiagnostics" />
          <span class="sw-muted">
            将附带本次会话的页面报错、失败请求、路由与浏览器环境（当前 {{ diagCount }} 条）
          </span>
        </div>
      </div>

      <template v-if="!auth.loggedIn">
        <el-alert type="info" :closable="false" class="sw-fb__alert">
          未登录也可以反馈，请填写内部测试口令。
        </el-alert>
        <el-form label-position="top">
          <el-form-item label="内部测试口令">
            <el-input v-model="testCode" type="password" show-password placeholder="测试口令" />
          </el-form-item>
          <el-form-item label="你的昵称（方便负责人联系你）">
            <el-input v-model="reporterName" maxlength="64" placeholder="例如：测试员小王" />
          </el-form-item>
        </el-form>
      </template>

      <div v-if="!canSubmit" class="sw-fb__tip">
        <el-icon><WarningFilled /></el-icon>
        请填写标题与描述{{ auth.loggedIn ? '' : '，并填写内部测试口令' }}
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">
        提交反馈
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.sw-fb__row {
  display: flex;
  align-items: center;
  gap: var(--sw-space-3);
  margin-bottom: var(--sw-space-2);
}

.sw-fb__row--top {
  align-items: flex-start;
  margin-top: var(--sw-space-4);
}

.sw-fb__label {
  display: inline-flex;
  align-items: center;
  gap: var(--sw-space-1);
  min-width: 112px;
  font-size: var(--sw-text-sm);
  color: var(--sw-text-secondary);
}

.sw-fb__hint {
  margin: 0 0 var(--sw-space-3);
}

.sw-fb__form {
  margin-top: var(--sw-space-4);
}

.sw-fb__diag {
  display: flex;
  align-items: center;
  gap: var(--sw-space-2);
  font-size: var(--sw-text-sm);
}

.sw-fb__alert {
  margin-top: var(--sw-space-4);
}

.sw-fb__tip {
  display: flex;
  align-items: center;
  gap: var(--sw-space-1);
  font-size: var(--sw-text-sm);
  color: var(--sw-warning);
}
</style>
