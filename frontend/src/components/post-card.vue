<template>
  <view class="post-card" @tap="goDetail">
    <view class="card-header">
      <!-- 无头像：昵称首字符色块兜底（不再引用不存在的 default-avatar.png，防 EISDIR） -->
      <image v-if="author.avatar_url" class="avatar" :src="author.avatar_url" mode="aspectFill" />
      <view v-else class="avatar avatar-fallback" :style="{ background: fallbackColor }">
        <text class="avatar-letter">{{ (author.nickname || '?').slice(0, 1) }}</text>
      </view>
      <view class="author-info">
        <text class="nickname">{{ author.nickname }}</text>
        <text class="post-type">{{ POST_TYPE_MAP[post.post_type] }}</text>
      </view>
      <text v-if="post.is_pinned" class="pinned-badge">置顶</text>
    </view>

    <view class="card-content">
      <text class="content-text">{{ post.content }}</text>
      <view v-if="post.images && post.images.length > 0" class="images-grid">
        <!-- 单图：widthFix 自适应铺开；多图：1:1 排开（最多 3 张 + 计数） -->
        <image
          v-for="(img, idx) in displayImages"
          :key="idx"
          :class="post.images.length === 1 ? 'post-image-single' : 'post-image'"
          :src="img"
          :mode="post.images.length === 1 ? 'widthFix' : 'aspectFill'"
        />
        <text v-if="post.images.length > 3" class="more-images">+{{ post.images.length - 3 }}</text>
      </view>
      <view v-if="post.tags && post.tags.length > 0" class="tags">
        <text v-for="tag in post.tags" :key="tag.id" class="tag">#{{ tag.name }}</text>
      </view>
      <text v-if="post.price" class="price">¥{{ post.price }}</text>
    </view>

    <view class="card-footer">
      <text class="time">{{ formatTime(post.created_at) }}</text>
      <text v-if="post._is_my_post" class="my-badge">我的</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { PostBrief } from '@/types/api'
import { computed } from 'vue'
import { POST_TYPE_MAP } from '@/types/api'

interface Props {
  post: PostBrief
}

const props = defineProps<Props>()

// 作者信息归一化：/posts/my 返回 user.nickname，信息流返回 author.*——两头兼容
// （修复：此前 my-posts 页头像/昵称区因字段不匹配从未渲染过）
const author = computed(() => {
  const p = props.post as PostBrief & { user?: { nickname?: string; avatar_url?: string | null } }
  return p.author ?? p.user ?? { nickname: '同学', avatar_url: null }
})

// 无头像兜底色：昵称哈希取色（与个人主页 colorOf 同款思路）
const AVATAR_COLORS = ['#f8c8b8', '#e8d5f5', '#d5e8f5', '#d5f0d5', '#fbe3b5']
const fallbackColor = computed(() => {
  const s = author.value?.nickname || ''
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[h % AVATAR_COLORS.length]
})

const displayImages = computed(() => {
  return props.post.images?.slice(0, 3) || []
})

const formatTime = (time: string) => {
  const date = new Date(time)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return `${date.getMonth() + 1}-${date.getDate()}`
}

const goDetail = () => {
  uni.navigateTo({ url: `/pages/post-detail/index?id=${props.post.id}` })
}
</script>

<style scoped>
.post-card {
  background: #fff;
  margin: 20rpx;
  padding: 24rpx;
  border-radius: 16rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.06);
}

.card-header {
  display: flex;
  align-items: center;
  margin-bottom: 16rpx;
}

.avatar {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  margin-right: 16rpx;
}

.avatar-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-letter {
  font-size: 30rpx;
  font-weight: bold;
  color: #ffffff;
}

.author-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.nickname {
  font-size: 28rpx;
  font-weight: 600;
  color: #333;
}

.post-type {
  font-size: 22rpx;
  color: #999;
  margin-top: 4rpx;
}

.pinned-badge {
  font-size: 20rpx;
  color: #fff;
  background: #ff6b6b;
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}

.card-content {
  margin-bottom: 16rpx;
}

.content-text {
  font-size: 28rpx;
  color: #333;
  line-height: 1.6;
  display: block;
  margin-bottom: 12rpx;
}

.images-grid {
  display: flex;
  gap: 8rpx;
  margin: 12rpx 0;
  position: relative;
}

.post-image {
  width: 200rpx;
  height: 200rpx;
  border-radius: 12rpx;
}

.post-image-single {
  width: 100%;
  border-radius: 12rpx;
}

.more-images {
  position: absolute;
  right: 8rpx;
  bottom: 8rpx;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 22rpx;
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
  margin: 12rpx 0;
}

.tag {
  font-size: 22rpx;
  color: #1296db;
  background: #e6f3ff;
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}

.price {
  font-size: 32rpx;
  font-weight: 600;
  color: #ff6b6b;
  display: block;
  margin-top: 12rpx;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.time {
  font-size: 22rpx;
  color: #999;
}

.my-badge {
  font-size: 20rpx;
  color: #1296db;
  border: 1rpx solid #1296db;
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
}
</style>
