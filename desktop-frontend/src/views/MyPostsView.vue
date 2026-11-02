<script setup lang="ts">
/** 我的帖子：可删除自己的帖子。 */
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import EmptyState from '@/components/EmptyState.vue'
import PostCard from '@/components/PostCard.vue'
import { deletePost, getMyPosts } from '@/api/posts'
import type { PostBrief } from '@/api/types'

const posts = ref<PostBrief[]>([])
const loading = ref(true)

async function load(): Promise<void> {
  loading.value = true
  try {
    posts.value = await getMyPosts()
  } finally {
    loading.value = false
  }
}

async function remove(post: PostBrief): Promise<void> {
  await ElMessageBox.confirm('删除后不可恢复，确定删除？', '删除帖子', { type: 'warning' })
  await deletePost(post.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="sw-myposts">
    <div class="sw-card sw-myposts__head">
      <h3 class="sw-card__title">我的帖子</h3>
      <p class="sw-muted">共 {{ posts.length }} 条</p>
    </div>

    <div v-loading="loading" class="sw-myposts__list">
      <div v-for="post in posts" :key="post.id" class="sw-myposts__item">
        <PostCard :post="post" />
        <el-button text type="danger" class="sw-myposts__delete" @click="remove(post)">删除</el-button>
      </div>
      <EmptyState v-if="!loading && !posts.length" text="还没有发过帖子" />
    </div>
  </div>
</template>

<style scoped>
.sw-myposts {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-myposts__head {
  padding: var(--sw-space-4);
}

.sw-myposts__list {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-3);
  min-height: 140px;
}

.sw-myposts__item {
  position: relative;
}

.sw-myposts__delete {
  position: absolute;
  top: var(--sw-space-3);
  right: var(--sw-space-3);
}
</style>
