<script setup lang="ts">
/** 标签总览。 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
import { getTags } from '@/api/content'
import type { TagItem } from '@/api/types'

const router = useRouter()
const tags = ref<TagItem[]>([])
const loading = ref(true)

onMounted(async () => {
  loading.value = false
  tags.value = await getTags().catch(() => [])
})
</script>

<template>
  <div v-loading="loading" class="sw-tags">
    <div class="sw-card sw-tags__card">
      <h3 class="sw-card__title">全部标签</h3>
      <p class="sw-muted">按标签浏览校园墙上的话题</p>
      <div class="sw-tags__list">
        <el-tag
          v-for="tag in tags"
          :key="tag.id"
          class="sw-tags__item"
          size="large"
          effect="plain"
          @click="router.push({ name: 'tag-posts', params: { name: tag.name } })"
        >
          # {{ tag.name }}
        </el-tag>
      </div>
    </div>
    <EmptyState v-if="!loading && !tags.length" text="还没有标签" />
  </div>
</template>

<style scoped>
.sw-tags__card {
  padding: var(--sw-space-5);
}

.sw-tags__list {
  margin-top: var(--sw-space-4);
  display: flex;
  flex-wrap: wrap;
  gap: var(--sw-space-3);
}

.sw-tags__item {
  cursor: pointer;
  min-height: var(--sw-control-size);
}
</style>
