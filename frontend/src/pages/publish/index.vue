<template>
  <view class="page-publish">
    <!-- 1. 热搜标签 -->
    <view class="hot-search-section">
      <view class="hot-label">
        <text>热</text>
        <text>搜</text>
      </view>
      <scroll-view class="tags-scroll" scroll-x :show-scrollbar="false">
        <view
          v-for="tag in hotTags"
          :key="tag"
          class="tag-badge"
          @tap="onTagTap(tag)"
        >
          #{{ tag }}
        </view>
      </scroll-view>
    </view>

    <!-- 2. 版块选择 -->
    <view class="section-selector" @tap="onSelectSection">
      <view class="selector-left">
        <text class="icon-layers">▤</text>
        <view class="selector-meta">
          <text class="selector-title">{{ section || '选择版块' }}</text>
          <text class="selector-desc">选择合适的版块，能让更多同学看到哦~</text>
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
      <view class="vertical-toolbar">
        <view v-for="t in tools" :key="t.type" class="toolbar-item" @tap="onTool(t.type)">
          <text>{{ t.icon }}</text>
        </view>
      </view>
    </view>

    <!-- 4. 媒体上传 -->
    <view class="media-upload-section">
      <view class="upload-box" @tap="onUpload('image')">
        <text class="upload-icon">🖼️</text>
        <text class="upload-text">添加照片</text>
      </view>
      <view class="upload-box" @tap="onUpload('video')">
        <text class="upload-icon">🎬</text>
        <text class="upload-text">添加视频</text>
      </view>
    </view>

    <!-- 5. AI 协助 -->
    <view class="ai-assist-card">
      <view class="ai-meta">
        <text class="ai-title">AI 协助</text>
        <text class="ai-desc">帮你优化内容，让表达更出色</text>
      </view>
      <switch color="#f73b43" :checked="aiEnabled" @change="onAiChange" />
    </view>

    <!-- 6. 发布按钮 -->
    <view class="submit-bar">
      <button class="publish-btn" @tap="onSubmit">发 布</button>
    </view>

    <TabBar :current="2" />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import TabBar from '@/components/tab-bar.vue'
import { PUBLISH_HOT_TAGS } from '@/utils/mock'
import { createPost } from '@/api/posts'
import type { PostType } from '@/types/api'
import { tokenStorage } from '@/utils/storage'

// 版块 → 后端 post_type 映射
const SECTIONS: { label: string; type: PostType }[] = [
  { label: '校园生活', type: 'general' },
  { label: '学习考研', type: 'general' },
  { label: '二手交易', type: 'second_hand' },
  { label: '失物招领', type: 'lost_found' },
  { label: '拼车出行', type: 'carpool' },
  { label: '情感树洞', type: 'general' },
]

const hotTags = PUBLISH_HOT_TAGS
const tools = [
  { type: 'expand', icon: '∨' },
  { type: 'location', icon: '📍' },
  { type: 'list', icon: '☰' },
  { type: 'emoji', icon: '😀' },
  { type: 'folder', icon: '📁' },
  { type: 'mic', icon: '🎤' },
] as const

const content = ref('')
const section = ref('')
const aiEnabled = ref(false)

onShow(() => {})

const onContentInput = (e: { detail: { value: string } } | Event) => {
  content.value = (e as { detail: { value: string } }).detail.value
}

const onTagTap = (tag: string) => {
  content.value = `${content.value} #${tag} `
}

const onSelectSection = () => {
  uni.showActionSheet({
    itemList: SECTIONS.map((s) => s.label),
    success: (res) => {
      section.value = SECTIONS[res.tapIndex].label
    },
  })
}

const onTool = (type: string) => {
  if (type === 'location') {
    uni.showToast({ title: '获取定位（开发中）', icon: 'none' })
    return
  }
  uni.showToast({ title: `工具：${type}`, icon: 'none' })
}

const onUpload = (type: 'image' | 'video') => {
  uni.showToast({ title: `添加${type === 'image' ? '照片' : '视频'}（开发中）`, icon: 'none' })
}

const onAiChange = (e: { detail: { value: boolean } } | Event) => {
  const val = (e as { detail: { value: boolean } }).detail.value
  aiEnabled.value = val
  if (val) uni.showToast({ title: 'AI 协助已开启（mock）', icon: 'none' })
}

const submitting = ref(false)

const onSubmit = async () => {
  if (submitting.value) return
  if (!tokenStorage.isLoggedIn()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  if (!section.value) {
    uni.showToast({ title: '请选择发布的版块', icon: 'none' })
    return
  }
  const text = content.value.trim()
  if (!text) {
    uni.showToast({ title: '请填写一点内容吧', icon: 'none' })
    return
  }
  const postType = SECTIONS.find((s) => s.label === section.value)?.type || 'general'
  submitting.value = true
  try {
    await createPost({ post_type: postType, content: text })
    uni.showToast({ title: '发布成功，审核通过后可见', icon: 'success' })
    setTimeout(() => {
      content.value = ''
      section.value = ''
      aiEnabled.value = false
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
  padding: 0 0 40rpx;
  min-height: 100vh;
}

/* 1. 热搜 */
.hot-search-section {
  background-color: #ffffff;
  padding: 24rpx;
  border-bottom: 1rpx solid #f2f3f5;
  display: flex;
  align-items: center;
}

.hot-label {
  color: var(--brand-red);
  font-size: 24rpx;
  font-weight: bold;
  line-height: 1.2;
  border-right: 2rpx solid #f2f3f5;
  padding-right: 16rpx;
  margin-right: 16rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.tags-scroll {
  white-space: nowrap;
  flex: 1;
}

.tag-badge {
  display: inline-block;
  background-color: var(--brand-red-soft);
  color: var(--brand-red);
  font-size: 24rpx;
  padding: 10rpx 24rpx;
  border-radius: 30rpx;
  margin-right: 16rpx;
}

/* 2. 版块选择 */
.section-selector {
  background-color: #ffffff;
  padding: 30rpx 24rpx;
  margin-top: 1rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.selector-left {
  display: flex;
  align-items: center;
}

.icon-layers {
  font-size: 40rpx;
  margin-right: 20rpx;
  color: var(--brand-red);
}

.selector-meta {
  display: flex;
  flex-direction: column;
}

.selector-title {
  font-size: 30rpx;
  color: #323233;
  font-weight: 500;
}

.selector-desc {
  font-size: 24rpx;
  color: #969799;
  margin-top: 6rpx;
}

.arrow-right {
  color: #c8c9cc;
  font-size: 32rpx;
}

/* 3. 正文 + 工具栏 */
.content-editor-wrapper {
  background-color: #ffffff;
  margin-top: 20rpx;
  padding: 30rpx 24rpx;
  position: relative;
  height: 450rpx;
}

.post-textarea {
  width: calc(100% - 90rpx);
  height: 100%;
  font-size: 30rpx;
  color: #323233;
  line-height: 1.6;
}

.textarea-placeholder {
  color: #c8c9cc;
}

.vertical-toolbar {
  position: absolute;
  right: 24rpx;
  top: 30rpx;
  width: 70rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.toolbar-item {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  background-color: var(--bg-page);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16rpx;
  font-size: 30rpx;
}

/* 4. 媒体 */
.media-upload-section {
  background-color: #ffffff;
  padding: 0 24rpx 40rpx;
  display: flex;
  gap: 24rpx;
}

.upload-box {
  width: 210rpx;
  height: 210rpx;
  border: 2rpx dashed #dcdee0;
  border-radius: 16rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: var(--bg-page);
}

.upload-icon {
  font-size: 48rpx;
  margin-bottom: 12rpx;
}

.upload-text {
  font-size: 24rpx;
  color: #969799;
}

/* 5. AI 协助 */
.ai-assist-card {
  background-color: #ffffff;
  margin-top: 20rpx;
  padding: 30rpx 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.ai-meta {
  display: flex;
  flex-direction: column;
}

.ai-title {
  font-size: 28rpx;
  color: #323233;
  font-weight: bold;
}

.ai-desc {
  font-size: 24rpx;
  color: #969799;
  margin-top: 6rpx;
}

/* 6. 发布按钮 */
.submit-bar {
  margin-top: 60rpx;
  padding: 0 32rpx;
}

.publish-btn {
  width: 100%;
  height: 88rpx;
  background: var(--brand-red);
  color: #ffffff;
  border-radius: var(--radius-btn);
  font-size: 32rpx;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(247, 59, 67, 0.3);
  line-height: 88rpx;
}
</style>
