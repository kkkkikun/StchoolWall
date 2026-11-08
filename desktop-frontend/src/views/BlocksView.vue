<script setup lang="ts">
/** 屏蔽的用户：列出我屏蔽过的用户，并支持解除屏蔽。 */
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import EmptyState from '@/components/EmptyState.vue'
import { listBlockedUsers, unblockUser } from '@/api/blocks'
import type { BlockedUser } from '@/api/types'

const items = ref<BlockedUser[]>([])
const hasMore = ref(false)
const cursor = ref<string | null>(null)
const loading = ref(false)
const busyId = ref('')

async function load(append = false): Promise<void> {
  if (loading.value) return
  loading.value = true
  try {
    const page = await listBlockedUsers(append ? cursor.value ?? undefined : undefined)
    items.value = append ? [...items.value, ...page.items] : page.items
    cursor.value = page.nextCursor
    hasMore.value = page.hasMore
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function remove(item: BlockedUser): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `解除对「${item.nickname || '该用户'}」的屏蔽？对方发起的屏蔽仍然有效。`,
      '解除屏蔽',
      { type: 'warning' },
    )
  } catch {
    // 用户取消
    return
  }
  busyId.value = item.id
  try {
    await unblockUser(item.id)
    items.value = items.value.filter((row) => row.id !== item.id)
    ElMessage.success('已解除屏蔽')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '解除失败')
  } finally {
    busyId.value = ''
  }
}

onMounted(() => load())
</script>

<template>
  <div class="sw-blocks">
    <div class="sw-card sw-blocks__head">
      <h3 class="sw-card__title">屏蔽的用户</h3>
      <p class="sw-muted">屏蔽后，双方的内容与互动将受限制。解除仅取消你发起的屏蔽。</p>
    </div>

    <div v-loading="loading" class="sw-blocks__list">
      <div v-for="item in items" :key="item.id" class="sw-card sw-blocks__row">
        <span class="sw-blocks__name">{{ item.nickname || '用户' }}</span>
        <el-button
          text
          type="primary"
          size="small"
          :loading="busyId === item.id"
          @click="remove(item)"
        >
          解除屏蔽
        </el-button>
      </div>
      <EmptyState v-if="!loading && !items.length" text="暂无屏蔽的用户" />
    </div>

    <el-button v-if="hasMore" :loading="loading" @click="load(true)">加载更多</el-button>
  </div>
</template>

<style scoped>
.sw-blocks {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-blocks__head {
  padding: var(--sw-space-4) var(--sw-space-5);
}

.sw-blocks__head p {
  margin: var(--sw-space-1) 0 0;
}

.sw-blocks__list {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-2);
  min-height: 120px;
}

.sw-blocks__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sw-space-3);
  padding: var(--sw-space-3) var(--sw-space-4);
}

.sw-blocks__name {
  font-size: var(--sw-text-base);
  color: var(--sw-text);
}
</style>
