<template>
  <view class="page-feedback" :class="themeClass">
    <!-- 提交成功回执 -->
    <view v-if="result" class="card">
      <view class="result-head">
        <image class="result-icon" :src="ICONS['check']" mode="aspectFit" />
        <text class="result-title">已收到，反馈编号 #{{ result.id }}</text>
      </view>
      <text class="tip">内部同学会在管理台看到这条反馈{{ result.uploaded ? `，截图已上传 ${result.uploaded} 张` : '' }}。</text>
      <view v-if="result.failed.length" class="fail-box">
        <text class="fail-title">有 {{ result.failed.length }} 张截图没传上去：</text>
        <text v-for="item in result.failed" :key="item.index" class="fail-item">
          第 {{ item.index + 1 }} 张 —— {{ item.message }}
        </text>
      </view>
      <view class="result-actions">
        <view v-if="loggedIn" class="ghost-btn" @tap="toggleMine">
          <text>{{ showMine ? '收起我的反馈' : '查看我的反馈' }}</text>
        </view>
        <view class="primary-btn" @tap="resetForm"><text>再提交一条</text></view>
      </view>
      <view v-if="showMine" class="mine-list">
        <view v-for="item in myFeedback" :key="item.id" class="mine-item">
          <text class="mine-title">#{{ item.id }} {{ item.title }}</text>
          <text class="mine-meta">
            {{ statusLabel(item.status) }} · {{ formatTime(item.created_at) }} · 截图 {{ item.screenshot_count || 0 }} 张
          </text>
        </view>
        <text v-if="!myFeedback.length" class="tip">暂无历史反馈</text>
      </view>
    </view>

    <view v-if="!result" class="form-wrap">
      <!-- 类型 + 严重程度 -->
      <view class="card">
        <text class="label">问题类型</text>
        <view class="seg-row">
          <view
            v-for="option in CATEGORY_OPTIONS"
            :key="option.value"
            class="seg-item"
            :class="{ active: category === option.value }"
            @tap="category = option.value"
          >
            <text class="seg-text">{{ option.label }}</text>
          </view>
        </view>
        <text class="label label-gap">严重程度</text>
        <view class="seg-row">
          <view
            v-for="option in SEVERITY_OPTIONS"
            :key="option.value"
            class="seg-item"
            :class="{ active: severity === option.value }"
            @tap="severity = option.value"
          >
            <text class="seg-text">{{ option.label }}</text>
          </view>
        </view>
      </view>

      <!-- 标题 -->
      <view class="card">
        <view class="row-between">
          <text class="label">标题</text>
          <text class="counter">{{ title.length }}/{{ TITLE_MAX }}</text>
        </view>
        <input
          v-model="title"
          class="field"
          :maxlength="TITLE_MAX"
          placeholder="一句话描述问题，例如：首页头像点不动"
          placeholder-class="ph"
          :adjust-position="true"
        />
      </view>

      <!-- 详细描述 -->
      <view class="card">
        <view class="row-between">
          <text class="label">详细描述</text>
          <text class="counter">{{ content.length }}/{{ CONTENT_MAX }}</text>
        </view>
        <textarea
          v-model="content"
          class="field textarea"
          :maxlength="CONTENT_MAX"
          placeholder="复现步骤、出现的位置、期望效果，越具体越好"
          placeholder-class="ph"
          :adjust-position="true"
        />
      </view>

      <!-- 截图 -->
      <view class="card">
        <view class="row-between">
          <text class="label">截图（最多 {{ MAX_SCREENSHOTS }} 张）</text>
          <text class="counter">{{ images.length }}/{{ MAX_SCREENSHOTS }}</text>
        </view>
        <view class="image-grid">
          <view v-for="(image, index) in images" :key="image.path" class="image-cell">
            <image class="image-thumb" :src="image.path" mode="aspectFill" />
            <view class="image-del" @tap="removeImage(index)">
              <image class="image-del-icon" :src="ICON_TONES['close']['inverse']" mode="aspectFit" />
            </view>
          </view>
          <view v-if="images.length < MAX_SCREENSHOTS" class="image-add" @tap="pickImages">
            <image class="image-add-icon" :src="ICONS['image']" mode="aspectFit" />
            <text class="image-add-text">添加截图</text>
          </view>
        </view>
        <text class="tip">每张 ≤ 5MB，仅支持图片。</text>
      </view>

      <!-- 诊断信息 -->
      <view class="card">
        <view class="row-between">
          <view class="row-left">
            <text class="label">附带诊断信息</text>
            <text class="tip tip-inline">将附带 {{ diagCount }} 条现场记录（页面报错与失败请求）</text>
          </view>
          <switch :checked="withDiagnostics" color="#c2455c" @change="onToggleDiagnostics" />
        </view>
        <text class="tip">诊断信息只存在本机，提交时随本条反馈一起发出，提交后即清空。</text>
      </view>

      <!-- 免登录：口令 + 昵称 -->
      <view v-if="!loggedIn" class="card">
        <text class="label">内部测试口令</text>
        <input
          v-model="testCode"
          class="field"
          placeholder="向内部同学索取的口令"
          placeholder-class="ph"
          :adjust-position="true"
        />
        <text class="label label-gap">你的昵称</text>
        <input
          v-model="reporterName"
          class="field"
          :maxlength="64"
          placeholder="方便负责人辨认来源，可填工号或昵称"
          placeholder-class="ph"
          :adjust-position="true"
        />
      </view>

      <button class="submit-btn" :disabled="submitting" @tap="onSubmit">
        {{ submitting ? progressText : '提交反馈' }}
      </button>
      <text class="foot-tip">提交后可在「设置 → 意见反馈」或本页面查看处理状态。</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { useTheme } from '@/utils/theme'
import { tokenStorage } from '@/utils/storage'
import { APP_VERSION, clearDiagnostics, collectDiagnostics, diagnosticsCount } from '@/utils/diagnostics'
import {
  createFeedback,
  uploadFeedbackScreenshot,
  getMyFeedback,
  type FeedbackCategory,
  type FeedbackCreatePayload,
  type FeedbackItem,
  type FeedbackSeverity,
} from '@/api/feedback'
import { ICONS, ICON_TONES } from '@/utils/icons'

const { themeClass } = useTheme()

const TITLE_MAX = 120
const CONTENT_MAX = 4000
const MAX_SCREENSHOTS = 5
const MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024

const CATEGORY_OPTIONS: Array<{ value: FeedbackCategory; label: string }> = [
  { value: 'bug', label: 'Bug' },
  { value: 'ui', label: 'UI 问题' },
  { value: 'feature', label: '功能建议' },
  { value: 'other', label: '其他' },
]
const SEVERITY_OPTIONS: Array<{ value: FeedbackSeverity; label: string }> = [
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
]
const STATUS_LABELS: Record<string, string> = {
  open: '待处理', handling: '处理中', resolved: '已解决', closed: '已关闭',
}

interface LocalImage { path: string; size: number }
interface SubmitResult {
  id: number
  uploaded: number
  failed: Array<{ index: number; message: string }>
}

const category = ref<FeedbackCategory>('bug')
const severity = ref<FeedbackSeverity>('medium')
const title = ref('')
const content = ref('')
const testCode = ref('')
const reporterName = ref('')
const images = ref<LocalImage[]>([])
const withDiagnostics = ref(true)
const loggedIn = ref(tokenStorage.isLoggedIn())
const diagCount = ref(diagnosticsCount())
const submitting = ref(false)
const progressText = ref('提交中…')
const result = ref<SubmitResult | null>(null)
const myFeedback = ref<FeedbackItem[]>([])
const showMine = ref(false)
const entryRoute = ref('')
const entryUrl = ref('')

const toast = (message: string) => uni.showToast({ title: message, icon: 'none' })

/** uni 类型把返回值声明成 string | string[]，运行时恒为数组，这里统一成数组。 */
function toArray<T>(value: T | T[]): T[] {
  if (value === undefined || value === null) return []
  return Array.isArray(value) ? value : [value]
}

const pickImages = () => {
  const remain = MAX_SCREENSHOTS - images.value.length
  if (remain <= 0) return toast(`最多 ${MAX_SCREENSHOTS} 张截图`)
  uni.chooseImage({
    count: remain,
    sizeType: ['compressed'],
    sourceType: ['album', 'camera'],
    success: (res) => {
      const paths = toArray<string>(res.tempFilePaths)
      const files = toArray<{ size?: number }>(res.tempFiles as any)
      paths.forEach((path, index) => {
        const size = files[index]?.size || 0
        if (size > MAX_SCREENSHOT_BYTES) return toast('单张截图不能超过 5MB，已跳过')
        images.value.push({ path, size })
      })
    },
  })
}

const removeImage = (index: number) => {
  images.value.splice(index, 1)
}

const onToggleDiagnostics = (event: any) => {
  withDiagnostics.value = !!event.detail.value
}

function statusLabel(status: string): string {
  return STATUS_LABELS[status] || status
}

function formatTime(value?: string | null): string {
  if (!value) return ''
  return value.slice(0, 16).replace('T', ' ')
}

function validate(): string {
  if (!title.value.trim()) return '请填写标题'
  if (!content.value.trim()) return '请描述具体问题'
  if (!loggedIn.value && !testCode.value.trim()) return '请填写内部测试口令'
  return ''
}

async function buildPayload(): Promise<FeedbackCreatePayload> {
  const snapshot = await collectDiagnostics()
  const payload: FeedbackCreatePayload = {
    category: category.value,
    severity: severity.value,
    title: title.value.trim(),
    content: content.value.trim(),
    app_version: APP_VERSION,
  }
  if (snapshot.viewport) payload.viewport = snapshot.viewport
  if (snapshot.theme) payload.theme = snapshot.theme
  if (entryRoute.value || snapshot.route) payload.route = entryRoute.value || snapshot.route
  if (entryUrl.value) payload.page_url = entryUrl.value.slice(0, 500)
  if (!loggedIn.value) {
    payload.test_code = testCode.value.trim()
    payload.reporter_name = reporterName.value.trim().slice(0, 64)
  }
  if (withDiagnostics.value) payload.diagnostics = snapshot
  return payload
}

async function uploadScreenshots(id: number, token: string) {
  const failed: Array<{ index: number; message: string }> = []
  let uploaded = 0
  for (let index = 0; index < images.value.length; index += 1) {
    progressText.value = `上传截图 ${index + 1}/${images.value.length}…`
    try {
      await uploadFeedbackScreenshot(id, token, images.value[index].path)
      uploaded += 1
    } catch (error) {
      failed.push({ index, message: (error as Error).message || '上传失败' })
    }
  }
  return { uploaded, failed }
}

const onSubmit = async () => {
  if (submitting.value) return
  const error = validate()
  if (error) return toast(error)
  submitting.value = true
  progressText.value = '提交中…'
  try {
    const created = await createFeedback(await buildPayload())
    const outcome = await uploadScreenshots(created.id, created.upload_token)
    result.value = { id: created.id, ...outcome }
    // 现场已经随这条反馈发出，本地留着的旧记录没有价值了
    clearDiagnostics()
    diagCount.value = diagnosticsCount()
    toast(`已收到，反馈编号 #${created.id}`)
  } catch (error) {
    toast((error as Error).message || '提交失败，请重试')
  } finally {
    submitting.value = false
  }
}

const resetForm = () => {
  result.value = null
  showMine.value = false
  title.value = ''
  content.value = ''
  images.value = []
}

const toggleMine = async () => {
  showMine.value = !showMine.value
  if (!showMine.value || myFeedback.value.length) return
  try {
    const data = await getMyFeedback(1)
    myFeedback.value = data.items || []
  } catch (error) {
    toast((error as Error).message || '加载失败')
  }
}

onLoad((options) => {
  entryRoute.value = String(options?.from || '').slice(0, 120)
  entryUrl.value = String(options?.page_url || '').slice(0, 500)
})

onShow(() => {
  loggedIn.value = tokenStorage.isLoggedIn()
  diagCount.value = diagnosticsCount()
})
</script>

<style scoped>
.page-feedback {
  min-height: 100vh;
  background: var(--bg-page);
  padding: 24rpx 24rpx calc(160rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
}

.card {
  background: var(--bg-card);
  border: 1rpx solid var(--border-light);
  border-radius: var(--radius-card);
  padding: 28rpx;
  margin-bottom: 24rpx;
}

.label {
  display: block;
  font-size: 26rpx;
  color: var(--text-1);
  font-weight: 600;
}
.label-gap { margin-top: 24rpx; }
.tip {
  display: block;
  color: var(--text-3);
  font-size: 24rpx;
  line-height: 1.7;
  margin-top: 12rpx;
}
.tip-inline { margin-top: 6rpx; }
.counter { font-size: 24rpx; color: var(--text-3); }
.row-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.row-left {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.seg-row {
  display: flex;
  flex-wrap: wrap;
  margin-top: 16rpx;
}
.seg-item {
  min-height: 64rpx;
  padding: 0 26rpx;
  margin: 0 16rpx 16rpx 0;
  border-radius: var(--radius-btn);
  background: var(--pill-bg);
  display: flex;
  align-items: center;
  justify-content: center;
}
.seg-item.active {
  background: var(--primary-fill);
}
.seg-text {
  font-size: 26rpx;
  color: var(--text-2);
}
.seg-item.active .seg-text { color: var(--text-inverse); }

/* uni H5 的 input 内部控件是 height:100%，外层不给固定高度会塌成 0 高（点不中） */
.field {
  width: 100%;
  margin-top: 16rpx;
  height: 88rpx;
  padding: 0 24rpx;
  box-sizing: border-box;
  background: var(--bg-card-2);
  border-radius: var(--radius-inner);
  font-size: 26rpx;
  color: var(--text-1);
}
.textarea {
  height: 300rpx;
  padding: 20rpx 24rpx;
  line-height: 1.6;
}

.image-grid {
  display: flex;
  flex-wrap: wrap;
  margin-top: 16rpx;
}
.image-cell {
  position: relative;
  width: 160rpx;
  height: 160rpx;
  margin: 0 16rpx 16rpx 0;
}
.image-thumb {
  width: 100%;
  height: 100%;
  border-radius: var(--radius-inner);
  background: var(--bg-card-2);
}
.image-del {
  position: absolute;
  top: -10rpx;
  right: -10rpx;
  width: 44rpx;
  height: 44rpx;
  border-radius: 50%;
  background: var(--primary-fill);
  display: flex;
  align-items: center;
  justify-content: center;
}
.image-del-icon { width: 24rpx; height: 24rpx; }
.image-add {
  width: 160rpx;
  height: 160rpx;
  margin: 0 16rpx 16rpx 0;
  border: 2rpx dashed var(--border-strong);
  border-radius: var(--radius-inner);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.image-add-icon { width: 44rpx; height: 44rpx; }
.image-add-text {
  font-size: 24rpx;
  color: var(--text-3);
  margin-top: 8rpx;
}

.submit-btn {
  height: 88rpx;
  line-height: 88rpx;
  border-radius: var(--radius-btn);
  background: var(--primary-fill);
  color: var(--text-inverse);
  font-size: 30rpx;
  font-weight: 600;
}
.submit-btn[disabled] { opacity: 0.6; }
.foot-tip {
  display: block;
  text-align: center;
  color: var(--text-3);
  font-size: 24rpx;
  margin-top: 24rpx;
}

.result-head {
  display: flex;
  align-items: center;
}
.result-icon { width: 40rpx; height: 40rpx; margin-right: 14rpx; }
.result-title {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--text-1);
}
.fail-box {
  margin-top: 16rpx;
  padding: 20rpx;
  border-radius: var(--radius-inner);
  background: var(--danger-soft);
}
.fail-title {
  display: block;
  font-size: 24rpx;
  color: var(--danger-strong);
  font-weight: 600;
}
.fail-item {
  display: block;
  font-size: 24rpx;
  color: var(--text-2);
  margin-top: 8rpx;
}
.result-actions {
  display: flex;
  margin-top: 28rpx;
}
.ghost-btn {
  flex: 1;
  min-height: 80rpx;
  margin-right: 20rpx;
  border: 2rpx solid var(--border-strong);
  border-radius: var(--radius-btn);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26rpx;
  color: var(--text-2);
}
.primary-btn {
  flex: 1;
  min-height: 80rpx;
  border-radius: var(--radius-btn);
  background: var(--primary-fill);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26rpx;
  color: var(--text-inverse);
}
.mine-list { margin-top: 24rpx; }
.mine-item {
  padding: 20rpx 0;
  border-bottom: 1rpx solid var(--border-light);
}
.mine-title {
  display: block;
  font-size: 26rpx;
  color: var(--text-1);
}
.mine-meta {
  display: block;
  font-size: 24rpx;
  color: var(--text-3);
  margin-top: 6rpx;
}
</style>
