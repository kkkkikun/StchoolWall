<script setup lang="ts">
/** 信息流里的一条帖子。 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import UserAvatar from '@/components/UserAvatar.vue'
import type { PostBrief } from '@/api/types'
import { compactNumber, POST_TYPE_LABELS, relativeTime } from '@/utils/format'

const props = defineProps<{ post: PostBrief }>()
const router = useRouter()

const typeLabel = computed(() => POST_TYPE_LABELS[props.post.postType] ?? props.post.postType)
const imageCount = computed(() => props.post.images.length)
</script>

<template>
  <article class="sw-card sw-post" @click="router.push(`/post/${post.id}`)">
    <header class="sw-post__head">
      <UserAvatar :src="post.author.avatarUrl" :nickname="post.author.nickname" :size="40" />
      <div class="sw-post__author">
        <span class="sw-post__name">{{ post.author.nickname }}</span>
        <span class="sw-muted">{{ relativeTime(post.createdAt) }}</span>
      </div>
      <div class="sw-post__badges">
        <el-tag v-if="post.isPinned" type="danger" size="small" effect="plain">置顶</el-tag>
        <el-tag v-if="post.isFeatured" type="warning" size="small" effect="plain">精华</el-tag>
        <el-tag size="small" effect="plain">{{ typeLabel }}</el-tag>
      </div>
    </header>

    <p class="sw-post__content sw-clamp-3">{{ post.content }}</p>

    <div v-if="imageCount" class="sw-post__images">
      <el-image
        v-for="image in post.images.slice(0, 3)"
        :key="image"
        :src="image"
        fit="cover"
        class="sw-post__image"
        lazy
      />
      <div v-if="imageCount > 3" class="sw-post__more">+{{ imageCount - 3 }}</div>
    </div>

    <footer class="sw-post__foot">
      <span v-if="post.price !== undefined" class="sw-post__price">¥{{ post.price }}</span>
      <span v-for="tag in post.tags" :key="tag.id" class="sw-post__tag">#{{ tag.name }}</span>
      <span class="sw-post__counts">
        <span>浏览 {{ compactNumber(post.viewCount) }}</span>
        <span>点赞 {{ compactNumber(post.likeCount) }}</span>
        <span>评论 {{ compactNumber(post.commentCount) }}</span>
      </span>
    </footer>
  </article>
</template>

<style scoped>
.sw-post {
  padding: var(--sw-space-4);
  cursor: pointer;
  transition: box-shadow 0.15s ease, border-color 0.15s ease;
}

.sw-post:hover {
  border-color: var(--sw-border-strong);
  box-shadow: var(--sw-shadow);
}

.sw-post__head {
  display: flex;
  align-items: center;
  gap: var(--sw-space-3);
}

.sw-post__author {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  min-width: 0;
}

.sw-post__name {
  font-weight: 600;
  color: var(--sw-text);
}

.sw-post__badges {
  margin-left: auto;
  display: flex;
  gap: var(--sw-space-2);
}

.sw-post__content {
  margin: var(--sw-space-3) 0 0;
  color: var(--sw-text);
  white-space: pre-wrap;
  word-break: break-word;
}

.sw-post__images {
  margin-top: var(--sw-space-3);
  display: flex;
  gap: var(--sw-space-2);
  position: relative;
}

.sw-post__image {
  width: 96px;
  height: 96px;
  border-radius: var(--sw-radius-sm);
  background: var(--sw-surface-muted);
}

.sw-post__more {
  position: absolute;
  right: 0;
  bottom: 0;
  padding: 2px 8px;
  background: rgb(0 0 0 / 55%);
  color: #fff;
  border-radius: var(--sw-radius-sm);
  font-size: var(--sw-text-xs);
}

.sw-post__foot {
  margin-top: var(--sw-space-3);
  display: flex;
  align-items: center;
  gap: var(--sw-space-3);
  color: var(--sw-text-muted);
  font-size: var(--sw-text-sm);
}

.sw-post__price {
  color: var(--sw-primary-text);
  font-weight: 600;
}

.sw-post__tag {
  color: var(--sw-primary-text);
}

.sw-post__counts {
  margin-left: auto;
  display: flex;
  gap: var(--sw-space-3);
}
</style>
