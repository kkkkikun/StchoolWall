<script setup lang="ts">
/** 搜索结果。 */
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
import PostCard from '@/components/PostCard.vue'
import { searchPosts } from '@/api/posts'
import type { PostBrief } from '@/api/types'

const route = useRoute()
const keyword = ref('')
const posts = ref<PostBrief[]>([])
const loading = ref(false)
const searched = ref(false)

async function runSearch(query: string): Promise<void> {
  const value = query.trim()
  if (!value) {
    posts.value = []
    searched.value = false
    return
  }
  loading.value = true
  try {
    const page = await searchPosts(value)
    posts.value = page.items
    searched.value = true
  } catch {
    posts.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => route.query.q,
  (value) => {
    keyword.value = typeof value === 'string' ? value : ''
    runSearch(keyword.value)
  },
  { immediate: true },
)

onMounted(() => {
  keyword.value = typeof route.query.q === 'string' ? route.query.q : ''
})
</script>

<template>
  <div class="sw-search">
    <div class="sw-card sw-search__bar">
      <el-input
        v-model="keyword"
        placeholder="搜索帖子内容"
        clearable
        @keyup.enter="runSearch(keyword)"
      />
      <el-button type="primary" :loading="loading" @click="runSearch(keyword)">搜索</el-button>
    </div>

    <div v-loading="loading" class="sw-search__list">
      <PostCard v-for="post in posts" :key="post.id" :post="post" />
      <EmptyState
        v-if="searched && !loading && !posts.length"
        text="没有找到相关帖子"
        hint="换个关键词试试。"
      />
      <EmptyState v-if="!searched" text="输入关键词开始搜索" />
    </div>
  </div>
</template>

<style scoped>
.sw-search {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-search__bar {
  display: flex;
  gap: var(--sw-space-3);
  padding: var(--sw-space-4);
}

.sw-search__list {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-3);
  min-height: 160px;
}
</style>
