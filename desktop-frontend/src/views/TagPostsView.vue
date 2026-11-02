<script setup lang="ts">
/** 某个标签下的帖子。 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
import PostCard from '@/components/PostCard.vue'
import { getPosts } from '@/api/posts'
import type { PostBrief } from '@/api/types'

const route = useRoute()
const posts = ref<PostBrief[]>([])
const loading = ref(false)

const tagName = computed(() => String(route.params.name ?? ''))

async function load(): Promise<void> {
  loading.value = true
  try {
    const page = await getPosts({ tag: tagName.value })
    posts.value = page.items
  } finally {
    loading.value = false
  }
}

watch(tagName, load, { immediate: true })
onMounted(load)
</script>

<template>
  <div v-loading="loading" class="sw-tag-posts">
    <div class="sw-card sw-tag-posts__head">
      <h3 class="sw-card__title"># {{ tagName }}</h3>
      <p class="sw-muted">共 {{ posts.length }} 条</p>
    </div>
    <div class="sw-tag-posts__list">
      <PostCard v-for="post in posts" :key="post.id" :post="post" />
      <EmptyState v-if="!loading && !posts.length" text="这个标签下还没有帖子" />
    </div>
  </div>
</template>

<style scoped>
.sw-tag-posts {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-tag-posts__head {
  padding: var(--sw-space-4);
}

.sw-tag-posts__list {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-3);
  min-height: 140px;
}
</style>
