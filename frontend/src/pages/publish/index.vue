<template>
  <view class="page-publish" :class="themeClass">
    <!-- 1. 热搜标签 -->
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

    <!-- 2. 分类选择 -->
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

    <!-- 3. 正文 + 右侧工具栏 -->
    <view class="content-editor-wrapper">
      <textarea
        class="post-textarea"
        placeholder="在此处输入正文"
        placeholder-class="textarea-placeholder"
        :maxlength="1000"
        :value="content"
        @input="onContentInput"
      />
    </view>

    <!-- 4. 图片上传（≤6 张，服务端落 /static/posts/） -->
    <view class="media-upload-section">
      <view v-for="(img, i) in images" :key="img.local" class="img-cell">
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

    <!-- 6. 发布按钮 -->
    <view class="submit-bar">
      <button class="publish-btn" @tap="onSubmit">发 布</button>
    </view>

    <TabBar :current="2" />
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useTheme } from '@/utils/theme'
import TabBar from '@/components/tab-bar.vue'
import { POST_CATEGORIES } from '@/utils/mock'
import { getTags } from '@/api/tags'
import type { Tag } from '@/types/api'
import { createPost } from '@/api/posts'
import { tokenStorage } from '@/utils/storage'
import { uploadFile } from '@/utils/request'

const { themeClass } = useTheme()

const tags = ref<Tag[]>([])
const content = ref('')
const section = ref('')

const onContentInput = (e: { detail: { value: string } } | Event) => {
  content.value = (e as { detail: { value: string } }).detail.value
}

const onTagTap = (tag: Tag) => {
  content.value = `${content.value} #${tag.name} `
}

const loadTags = async () => {
  try {
    tags.value = await getTags()
  } catch { /* 标签非关键，失败静默 */ }
}

onMounted(loadTags)

const onSelectSection = () => {
  uni.showActionSheet({
    itemList: [...POST_CATEGORIES],
    success: (res) => {
      section.value = POST_CATEGORIES[res.tapIndex]
    },
  })
}

// ===== 图片上传（≤6 张；后端仅收 /static/posts/ 相对路径）=====
interface PendingImage {
  local: string      // chooseImage 的本地临时路径（网格预览用）
  url: string        // 上传完成后的 /static/posts/…（发布用）
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
        images.value.push({ local: p, url: '', status: 'uploading' })
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
    img.url = await uploadFile(img.local, 'posts')
    img.status = 'done'
  } catch (e) {
    img.status = 'failed'
    uni.showToast({ title: `图片上传失败：${(e as Error).message || '请重试'}`, icon: 'none' })
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
  // 图片未就绪禁止提交：上传中的等待，失败的引导处理
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
    const uploaded = images.value.filter((i) => i.status === 'done').map((i) => i.url)
    await createPost({ post_type: 'general', content: text, category: section.value, images: uploaded })
    uni.showToast({ title: '发布成功，审核通过后可见', icon: 'success' })
    setTimeout(() => {
      content.value = ''
      section.value = ''
      images.value = []
      uni.switchTab({ url: '/pages/index/index' })
    }, 1200)
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '发布失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.page-publish {
  background-color: var(--bg-page);
  padding: 0 0 60rpx;
  min-height: 100vh;
}

/* 1. 热搜 */
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

.tag-badge.selected {
  background-color: var(--primary);
  color: var(--text-inverse);
}

.tag-link { white-space: nowrap; }
.tag-check { margin-left: 8rpx; font-weight: bold; }

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

/* 2. 版块选择 */
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

/* 3. 正文 + 工具栏 */
.content-editor-wrapper {
  background-color: var(--bg-card);
  margin: 20rpx 24rpx 0;
  padding: 30rpx 24rpx;
  border-radius: var(--radius-card);
  height: 450rpx;
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
  color: var(--text-3);
}

/* 4. 媒体 */
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

/* 6. 发布按钮 */
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
