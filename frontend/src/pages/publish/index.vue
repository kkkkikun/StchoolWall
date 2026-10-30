<template>
  <view class="page-publish" :class="themeClass">
    <!-- 0. 草稿箱恢复横幅 -->
    <view v-if="draftBannerVisible" class="draft-banner">
      <view class="draft-info">
        <text class="draft-icon">📝</text>
        <text class="draft-text">检测到 {{ draftTimeText }} 未发布的草稿</text>
      </view>
      <view class="draft-actions">
        <text class="draft-btn restore" @tap="restoreDraft">恢复草稿</text>
        <text class="draft-btn discard" @tap="discardDraft">放弃</text>
      </view>
    </view>

    <!-- 1. 帖子类型选择胶囊 -->
    <view class="type-selector-section">
      <view
        v-for="item in TYPE_OPTIONS"
        :key="item.type"
        class="type-pill"
        :class="{ active: selectedType === item.type }"
        @tap="onSelectType(item)"
      >
        <text class="type-icon">{{ item.icon }}</text>
        <text class="type-label">{{ item.label }}</text>
      </view>
    </view>

    <!-- 2. 二手闲置价格输入 -->
    <view v-if="selectedType === 'second_hand'" class="extra-field-section">
      <view class="extra-field-row">
        <text class="extra-label">💰 期望价格</text>
        <input
          class="extra-input"
          type="digit"
          :value="price"
          placeholder="0.00 (元)"
          placeholder-class="textarea-placeholder"
          @input="onPriceInput"
        />
      </view>
    </view>

    <!-- 3. 热搜标签 -->
    <view class="hot-search-section">
      <view class="hot-label">
        <text>热</text>
        <text>搜</text>
      </view>
      <scroll-view class="tags-scroll" scroll-x :show-scrollbar="false">
        <view
          v-for="tag in tags"
          :key="tag.id"
          class="tag-badge"
          @tap="onTagTap(tag)"
        >
          #{{ tag.name }}
        </view>
        <text v-if="!tags.length" class="tag-empty">暂无标签，可在后台添加</text>
      </scroll-view>
    </view>

    <!-- 4. 分类选择 -->
    <view class="section-selector" @tap="onSelectSection">
      <view class="selector-left">
        <text class="icon-layers">▤</text>
        <view class="selector-meta">
          <text class="selector-title">{{ section || '选择分类' }}</text>
          <text class="selector-desc">选择合适的分类，能让更多同学看到哦~</text>
        </view>
      </view>
      <text class="arrow-right">›</text>
    </view>

    <!-- 5. 正文输入 -->
    <view class="content-editor-wrapper">
      <textarea
        class="post-textarea"
        :placeholder="currentPlaceholder"
        placeholder-class="textarea-placeholder"
        :maxlength="1000"
        :value="content"
        @input="onContentInput"
      />
    </view>

    <!-- 6. 图片上传（≤6 张，先进入私有待审区） -->
    <view class="media-upload-section">
      <view v-for="(img, i) in images" :key="img.local" class="img-cell" :data-media-id="img.mediaId">
        <image class="img-thumb" :src="img.local" mode="aspectFill" />
        <!-- 上传中遮罩 / 失败态 -->
        <view v-if="img.status === 'uploading'" class="img-mask">
          <text>…</text>
        </view>
        <view v-else-if="img.status === 'failed'" class="img-mask failed" @tap="retryUpload(i)">
          <text>↑</text>
          <text class="fail-text">重试</text>
        </view>
        <view class="img-del" @tap="removeImage(i)">
          <text>✕</text>
        </view>
      </view>
      <view v-if="images.length < MAX_IMAGES" class="upload-box" @tap="onAddImage">
        <text class="upload-icon">🖼️</text>
        <text class="upload-text">添加照片</text>
        <text class="upload-count">{{ images.length }}/{{ MAX_IMAGES }}</text>
      </view>
    </view>

    <!-- 7. 发布按钮 -->
    <view class="submit-bar">
      <button class="publish-btn" :loading="submitting" @tap="onSubmit">发 布</button>
    </view>

    <TabBar :current="2" />
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useTheme } from '@/utils/theme'
import TabBar from '@/components/tab-bar.vue'
import { POST_CATEGORIES } from '@/utils/mock'
import { getTags } from '@/api/tags'
import type { Tag, PostType } from '@/types/api'
import { createPost } from '@/api/posts'
import { tokenStorage } from '@/utils/storage'
import { uploadMedia } from '@/utils/request'
import { friendlyNetworkError } from '@/utils/errors'
import { safeNavigateToHome } from '@/utils/navbar'

const { themeClass } = useTheme()

interface TypeOption {
  type: PostType
  label: string
  icon: string
  defaultCategory: string
  placeholder: string
}

const TYPE_OPTIONS: TypeOption[] = [
  { type: 'general', label: '日常广场', icon: '💬', defaultCategory: '广场', placeholder: '在此处输入正文，分享校园新鲜事、吐槽或求助...' },
  { type: 'second_hand', label: '二手闲置', icon: '🏷️', defaultCategory: '二手', placeholder: '描述闲置物品成色、转手原因、取货地点等...' },
  { type: 'lost_found', label: '失物招领', icon: '🔍', defaultCategory: '失物', placeholder: '描述遗失/拾到物品特征、时间、地点及认领方式...' },
  { type: 'carpool', label: '拼车出行', icon: '🚗', defaultCategory: '广场', placeholder: '描述出发地、目的地、出发时间、余位要求...' },
]

const selectedType = ref<PostType>('general')
const price = ref('')
const tags = ref<Tag[]>([])
const content = ref('')
const section = ref('广场')

const currentPlaceholder = computed(() => {
  return TYPE_OPTIONS.find((t) => t.type === selectedType.value)?.placeholder || '在此处输入正文'
})

const onSelectType = (opt: TypeOption) => {
  selectedType.value = opt.type
  if (!section.value || section.value === '广场' || section.value === '二手' || section.value === '失物') {
    section.value = opt.defaultCategory
  }
  scheduleSaveDraft()
}

// ===== 草稿机制 =====
const DRAFT_KEY = 'schoolwall_publish_draft'
const draftBannerVisible = ref(false)
const draftTimeText = ref('')
let draftTimer: ReturnType<typeof setTimeout> | null = null

const scheduleSaveDraft = () => {
  if (draftTimer) clearTimeout(draftTimer)
  draftTimer = setTimeout(() => {
    if (!content.value.trim() && !price.value) {
      uni.removeStorageSync(DRAFT_KEY)
      return
    }
    const data = {
      type: selectedType.value,
      section: section.value,
      content: content.value,
      price: price.value,
      updated_at: Date.now(),
    }
    uni.setStorageSync(DRAFT_KEY, data)
  }, 500)
}

const checkDraft = () => {
  try {
    const raw = uni.getStorageSync(DRAFT_KEY)
    if (raw && (raw.content || raw.price)) {
      const diffMins = Math.floor((Date.now() - (raw.updated_at || 0)) / 60000)
      draftTimeText.value = diffMins < 1 ? '刚刚' : diffMins < 60 ? `${diffMins}分钟前` : `${Math.floor(diffMins / 60)}小时前`
      draftBannerVisible.value = true
    }
  } catch { /* storage 兼容 */ }
}

const restoreDraft = () => {
  try {
    const raw = uni.getStorageSync(DRAFT_KEY)
    if (raw) {
      if (raw.type) selectedType.value = raw.type
      if (raw.section) section.value = raw.section
      if (raw.content) content.value = raw.content
      if (raw.price) price.value = raw.price
      uni.showToast({ title: '已恢复草稿', icon: 'success' })
    }
  } catch { /* 忽略 */ }
  draftBannerVisible.value = false
}

const discardDraft = () => {
  uni.removeStorageSync(DRAFT_KEY)
  draftBannerVisible.value = false
}

const onContentInput = (e: { detail: { value: string } } | Event) => {
  content.value = (e as { detail: { value: string } }).detail.value
  scheduleSaveDraft()
}

const onPriceInput = (e: { detail: { value: string } } | Event) => {
  price.value = (e as { detail: { value: string } }).detail.value
  scheduleSaveDraft()
}

const onTagTap = (tag: Tag) => {
  content.value = `${content.value} #${tag.name} `
  scheduleSaveDraft()
}

const loadTags = async () => {
  try {
    tags.value = await getTags()
  } catch { /* 标签非关键，失败静默 */ }
}

onMounted(() => {
  loadTags()
  checkDraft()
})

const onSelectSection = () => {
  uni.showActionSheet({
    itemList: [...POST_CATEGORIES],
    success: (res) => {
      section.value = POST_CATEGORIES[res.tapIndex]
      scheduleSaveDraft()
    },
  })
}

// ===== 图片上传（≤6 张；后端仅收归属当前账户的 media ID）=====
interface PendingImage {
  local: string
  mediaId: string
  status: 'uploading' | 'done' | 'failed'
}

const MAX_IMAGES = 6
const images = ref<PendingImage[]>([])

const onAddImage = () => {
  const remain = MAX_IMAGES - images.value.length
  if (remain <= 0) {
    uni.showToast({ title: `最多 ${MAX_IMAGES} 张图片`, icon: 'none' })
    return
  }
  uni.chooseImage({
    count: remain,
    sizeType: ['compressed'],
    success: (res) => {
      for (const p of res.tempFilePaths) {
        if (images.value.length >= MAX_IMAGES) break
        images.value.push({ local: p, mediaId: '', status: 'uploading' })
        uploadOne(images.value.length - 1)
      }
    },
  })
}

const uploadOne = async (idx: number) => {
  const img = images.value[idx]
  if (!img) return
  img.status = 'uploading'
  try {
    const media = await uploadMedia(img.local, 'posts')
    img.mediaId = media.media_id
    img.status = 'done'
  } catch (e) {
    img.status = 'failed'
    uni.showToast({ title: `图片上传失败：${friendlyNetworkError(e, '请重试')}`, icon: 'none' })
  }
}

const retryUpload = (idx: number) => uploadOne(idx)

const removeImage = (idx: number) => {
  images.value.splice(idx, 1)
}

const submitting = ref(false)

const onSubmit = async () => {
  if (submitting.value) return
  if (!tokenStorage.isLoggedIn()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (!section.value) {
    uni.showToast({ title: '请选择分类', icon: 'none' })
    return
  }
  const text = content.value.trim()
  if (!text) {
    uni.showToast({ title: '请填写一点内容吧', icon: 'none' })
    return
  }

  // 二手闲置价格校验
  let parsedPrice: number | undefined
  if (selectedType.value === 'second_hand') {
    if (price.value.trim()) {
      const p = parseFloat(price.value.trim())
      if (isNaN(p) || p < 0) {
        uni.showToast({ title: '请输入有效的价格', icon: 'none' })
        return
      }
      parsedPrice = p
    }
  }

  if (images.value.some((i) => i.status === 'uploading')) {
    uni.showToast({ title: '图片还在上传中，稍等一下', icon: 'none' })
    return
  }
  if (images.value.some((i) => i.status === 'failed')) {
    uni.showToast({ title: '有图片上传失败，请重试或删除', icon: 'none' })
    return
  }

  submitting.value = true
  try {
    const uploaded = images.value.filter((i) => i.status === 'done').map((i) => i.mediaId)
    await createPost({
      post_type: selectedType.value,
      content: text,
      category: section.value,
      media_ids: uploaded,
      price: parsedPrice,
    })
    uni.removeStorageSync(DRAFT_KEY)
    uni.showToast({ title: '发布成功，审核通过后可见', icon: 'success' })
    setTimeout(() => {
      content.value = ''
      section.value = '广场'
      price.value = ''
      images.value = []
      safeNavigateToHome('/pages/index/index')
    }, 1200)
  } catch (e) {
    uni.showToast({ title: friendlyNetworkError(e, '发布失败'), icon: 'none' })
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.page-publish {
  background-color: var(--bg-page);
  padding: 0 0 100rpx;
  min-height: 100vh;
}

/* 0. 草稿箱横幅 */
.draft-banner {
  background-color: var(--primary-soft);
  border: 1rpx solid var(--border-primary-soft);
  margin: 16rpx 24rpx 0;
  padding: 16rpx 24rpx;
  border-radius: var(--radius-inner);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.draft-info {
  display: flex;
  align-items: center;
}

.draft-icon {
  font-size: 28rpx;
  margin-right: 12rpx;
}

.draft-text {
  font-size: 24rpx;
  color: var(--primary);
  font-weight: 500;
}

.draft-actions {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.draft-btn {
  font-size: 22rpx;
  padding: 6rpx 18rpx;
  border-radius: 20rpx;
}

.draft-btn.restore {
  background-color: var(--primary);
  color: var(--text-inverse);
  font-weight: bold;
}

.draft-btn.discard {
  color: var(--text-3);
}

/* 1. 帖子类型选择胶囊 */
.type-selector-section {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin: 20rpx 24rpx 0;
  overflow-x: auto;
}

.type-pill {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18rpx 0;
  background-color: var(--bg-card);
  border: 1rpx solid var(--border-light);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  transition: all 0.2s ease;
}

.type-pill.active {
  background-color: var(--primary-soft);
  border-color: var(--primary);
}

.type-icon {
  font-size: 28rpx;
  margin-right: 8rpx;
}

.type-label {
  font-size: 26rpx;
  color: var(--text-2);
  font-weight: 500;
}

.type-pill.active .type-label {
  color: var(--primary);
  font-weight: bold;
}

/* 2. 价格专有输入项 */
.extra-field-section {
  background-color: var(--bg-card);
  margin: 20rpx 24rpx 0;
  padding: 24rpx;
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
}

.extra-field-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.extra-label {
  font-size: 28rpx;
  color: var(--text-1);
  font-weight: 600;
}

.extra-input {
  flex: 1;
  text-align: right;
  font-size: 32rpx;
  color: var(--primary);
  font-weight: bold;
}

/* 3. 热搜 */
.hot-search-section {
  background-color: var(--bg-card);
  padding: 24rpx;
  margin: 20rpx 24rpx 0;
  border-radius: var(--radius-card);
  display: flex;
  align-items: center;
  box-shadow: var(--shadow-card);
}

.hot-label {
  color: var(--primary);
  font-size: 24rpx;
  font-weight: bold;
  line-height: 1.2;
  border-right: 2rpx solid var(--border-light);
  padding-right: 16rpx;
  margin-right: 16rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.tags-scroll {
  min-width: 0;
  max-width: 100%;
  white-space: nowrap;
  flex: 1;
}

.tag-empty {
  font-size: 24rpx;
  color: var(--text-3);
}

.tag-badge {
  display: inline-flex;
  align-items: center;
  background-color: var(--primary-soft);
  color: var(--primary);
  font-size: 24rpx;
  padding: 10rpx 24rpx;
  border-radius: 30rpx;
  margin-right: 16rpx;
}

/* 4. 版块选择 */
.section-selector {
  background-color: var(--bg-card);
  padding: 30rpx 24rpx;
  margin: 20rpx 24rpx 0;
  border-radius: var(--radius-card);
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: var(--shadow-card);
}

.selector-left {
  display: flex;
  align-items: flex-start;
}

.icon-layers {
  font-size: 38rpx;
  margin-right: 20rpx;
  margin-top: 2rpx;
  color: var(--primary);
  line-height: 1;
}

.selector-meta {
  display: flex;
  flex-direction: column;
}

.selector-title {
  font-size: 30rpx;
  color: var(--text-1);
  font-weight: 600;
}

.selector-desc {
  font-size: 24rpx;
  color: var(--text-3);
  margin-top: 6rpx;
}

.arrow-right {
  color: var(--text-3);
  font-size: 32rpx;
}

/* 5. 正文 + 工具栏 */
.content-editor-wrapper {
  background-color: var(--bg-card);
  margin: 20rpx 24rpx 0;
  padding: 30rpx 24rpx;
  border-radius: var(--radius-card);
  height: 420rpx;
  box-shadow: var(--shadow-card);
}

.post-textarea {
  width: 100%;
  height: 100%;
  font-size: 30rpx;
  color: var(--text-1);
  line-height: 1.6;
}

.textarea-placeholder {
  color: var(--text-placeholder);
}

/* 6. 媒体 */
.media-upload-section {
  background-color: var(--bg-card);
  margin: 20rpx 24rpx 0;
  padding: 24rpx;
  border-radius: var(--radius-card);
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
  box-shadow: var(--shadow-card);
}

.upload-box {
  width: 200rpx;
  height: 200rpx;
  border: 2rpx dashed var(--border-primary-soft);
  border-radius: var(--radius-inner);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: var(--primary-soft);
}

.upload-icon {
  font-size: 48rpx;
  margin-bottom: 12rpx;
}

.upload-text {
  font-size: 24rpx;
  color: var(--text-2);
}

.upload-count {
  font-size: 20rpx;
  color: var(--text-3);
  margin-top: 6rpx;
}

/* 已选图片网格 */
.img-cell {
  position: relative;
  width: 200rpx;
  height: 200rpx;
  border-radius: var(--radius-inner);
  overflow: hidden;
}

.img-thumb {
  width: 100%;
  height: 100%;
}

.img-mask {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-inverse);
  font-size: 32rpx;
}

.img-mask.failed {
  background: var(--primary-alpha);
}

.fail-text {
  font-size: 22rpx;
  margin-top: 6rpx;
}

.img-del {
  position: absolute;
  top: 8rpx;
  right: 8rpx;
  width: 40rpx;
  height: 40rpx;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.5);
  color: var(--text-inverse);
  font-size: 22rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 7. 发布按钮 */
.submit-bar {
  margin-top: 48rpx;
  padding: 0 32rpx;
}

.publish-btn {
  width: 100%;
  height: 88rpx;
  background: linear-gradient(135deg, var(--primary), var(--primary-strong));
  color: var(--text-inverse);
  border-radius: var(--radius-btn);
  font-size: 32rpx;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-primary-lg);
  line-height: 88rpx;
}
</style>
