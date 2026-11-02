<script setup lang="ts">
/** 帖子详情：正文、互动与评论。 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import EmptyState from '@/components/EmptyState.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import { deletePost, getPostDetail } from '@/api/posts'
import { createComment, deleteComment, favoritePost, likePost, listComments, unfavoritePost, unlikePost } from '@/api/social'
import type { CommentItem, PostDetail } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { compactNumber, POST_TYPE_LABELS, relativeTime } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const post = ref<PostDetail | null>(null)
const comments = ref<CommentItem[]>([])
const commentText = ref('')
const submitting = ref(false)
const loading = ref(true)

const postId = computed(() => Number(route.params.id))
const typeLabel = computed(() => (post.value ? POST_TYPE_LABELS[post.value.postType] ?? post.value.postType : ''))

async function loadPost(): Promise<void> {
  loading.value = true
  try {
    post.value = await getPostDetail(postId.value)
    const page = await listComments(postId.value)
    comments.value = page.items
  } catch {
    post.value = null
  } finally {
    loading.value = false
  }
}

async function toggleLike(): Promise<void> {
  if (!post.value) return
  if (!auth.loggedIn) {
    router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  const result = post.value.isLiked ? await unlikePost(post.value.id) : await likePost(post.value.id)
  post.value.isLiked = result.liked
  post.value.likeCount = result.like_count
}

async function toggleFavorite(): Promise<void> {
  if (!post.value) return
  if (!auth.loggedIn) {
    router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  const result = post.value.isFavorited ? await unfavoritePost(post.value.id) : await favoritePost(post.value.id)
  post.value.isFavorited = result.favorited
  ElMessage.success(result.favorited ? '已收藏' : '已取消收藏')
}

async function submitComment(): Promise<void> {
  const content = commentText.value.trim()
  if (!content) {
    ElMessage.warning('评论内容不能为空')
    return
  }
  submitting.value = true
  try {
    const created = await createComment(postId.value, content)
    comments.value = [created, ...comments.value]
    commentText.value = ''
  } finally {
    submitting.value = false
  }
}

async function removeComment(comment: CommentItem): Promise<void> {
  await ElMessageBox.confirm('确定删除这条评论？', '删除评论', { type: 'warning' })
  await deleteComment(comment.id)
  comments.value = comments.value.filter((item) => item.id !== comment.id)
}

async function removePost(): Promise<void> {
  await ElMessageBox.confirm('删除后不可恢复，确定删除这条帖子？', '删除帖子', { type: 'warning' })
  await deletePost(postId.value)
  ElMessage.success('已删除')
  router.push({ name: 'feed' })
}

onMounted(loadPost)
</script>

<template>
  <div v-loading="loading" class="sw-detail">
    <template v-if="post">
      <article class="sw-card sw-detail__post">
        <header class="sw-detail__head">
          <UserAvatar :src="post.author.avatarUrl" :nickname="post.author.nickname" :size="44" />
          <div class="sw-detail__author">
            <span class="sw-detail__name">{{ post.author.nickname }}</span>
            <span class="sw-muted">{{ relativeTime(post.createdAt) }}</span>
          </div>
          <el-tag size="small" effect="plain">{{ typeLabel }}</el-tag>
        </header>

        <p class="sw-detail__content">{{ post.content }}</p>

        <div v-if="post.images.length" class="sw-detail__images">
          <el-image
            v-for="image in post.images"
            :key="image"
            :src="image"
            fit="cover"
            class="sw-detail__image"
            :preview-src-list="post.images"
            preview-teleported
          />
        </div>

        <footer class="sw-detail__actions">
          <el-button text @click="toggleLike">
            {{ post.isLiked ? '已赞' : '点赞' }} · {{ compactNumber(post.likeCount) }}
          </el-button>
          <el-button text @click="toggleFavorite">{{ post.isFavorited ? '已收藏' : '收藏' }}</el-button>
          <span class="sw-muted">浏览 {{ compactNumber(post.viewCount) }}</span>
          <span class="sw-muted">评论 {{ compactNumber(post.commentCount) }}</span>
          <el-button v-if="auth.user && post.userId === auth.user.id" text type="danger" @click="removePost">
            删除
          </el-button>
        </footer>
      </article>

      <section class="sw-card sw-detail__comments">
        <h3 class="sw-card__title">评论（{{ comments.length }}）</h3>

        <div class="sw-comment-editor">
          <el-input
            v-model="commentText"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="说点什么…"
          />
          <el-button type="primary" :loading="submitting" @click="submitComment">发表评论</el-button>
        </div>

        <ul class="sw-comment-list">
          <li v-for="comment in comments" :key="comment.id" class="sw-comment">
            <UserAvatar :src="comment.avatarUrl" :nickname="comment.nickname" :size="32" />
            <div class="sw-comment__body">
              <p class="sw-comment__meta">
                <span class="sw-comment__name">{{ comment.nickname }}</span>
                <span class="sw-muted">{{ relativeTime(comment.createdAt) }}</span>
              </p>
              <p class="sw-comment__content">{{ comment.content }}</p>
            </div>
            <el-button
              v-if="auth.user && comment.userId === auth.user.id"
              text
              type="danger"
              size="small"
              @click="removeComment(comment)"
            >
              删除
            </el-button>
          </li>
        </ul>

        <EmptyState v-if="!comments.length" text="还没有评论" hint="来抢第一条。" />
      </section>
    </template>

    <EmptyState v-else-if="!loading" text="帖子不存在或已被删除" />
  </div>
</template>

<style scoped>
.sw-detail {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-detail__post {
  padding: var(--sw-space-5);
}

.sw-detail__head {
  display: flex;
  align-items: center;
  gap: var(--sw-space-3);
}

.sw-detail__author {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.sw-detail__name {
  font-weight: 600;
}

.sw-detail__content {
  margin: var(--sw-space-4) 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: var(--sw-text-lg);
  line-height: 1.7;
}

.sw-detail__images {
  margin-top: var(--sw-space-4);
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--sw-space-2);
}

.sw-detail__image {
  width: 100%;
  aspect-ratio: 1;
  border-radius: var(--sw-radius-sm);
  background: var(--sw-surface-muted);
}

.sw-detail__actions {
  margin-top: var(--sw-space-4);
  padding-top: var(--sw-space-3);
  border-top: 1px solid var(--sw-border);
  display: flex;
  align-items: center;
  gap: var(--sw-space-3);
}

.sw-detail__comments {
  padding: var(--sw-space-5);
}

.sw-comment-editor {
  margin: var(--sw-space-4) 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--sw-space-2);
}

.sw-comment-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-comment {
  display: flex;
  gap: var(--sw-space-3);
  align-items: flex-start;
}

.sw-comment__body {
  flex: 1;
  min-width: 0;
}

.sw-comment__meta {
  margin: 0;
  display: flex;
  gap: var(--sw-space-2);
  align-items: baseline;
}

.sw-comment__name {
  font-weight: 600;
  font-size: var(--sw-text-sm);
}

.sw-comment__content {
  margin: var(--sw-space-1) 0 0;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
