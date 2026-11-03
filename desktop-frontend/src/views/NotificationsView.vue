<script setup lang="ts">
/** 消息通知。 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
import { getNotifications, markAllNotificationsRead, markNotificationRead } from '@/api/user'
import type { NotificationItem } from '@/api/types'
import { relativeTime } from '@/utils/format'

const router = useRouter()

const TYPES = [
  { value: '', label: '全部' },
  { value: 'comment', label: '评论' },
  { value: 'like', label: '点赞' },
  { value: 'favorite', label: '收藏' },
  { value: 'announcement', label: '公告' },
  { value: 'moderation', label: '审核' },
]

const activeType = ref('')
const items = ref<NotificationItem[]>([])
const loading = ref(true)

async function load(): Promise<void> {
  loading.value = true
  try {
    const page = await getNotifications(activeType.value || undefined)
    items.value = page.items
  } finally {
    loading.value = false
  }
}

async function open(item: NotificationItem): Promise<void> {
  if (!item.isRead) {
    await markNotificationRead(item.id).catch(() => undefined)
    item.isRead = true
  }
  if (item.postId) {
    router.push(`/post/${item.postId}`)
  }
}

async function readAll(): Promise<void> {
  await markAllNotificationsRead()
  await load()
}

function switchType(value: string): void {
  activeType.value = value
  load()
}

onMounted(load)
</script>

<template>
  <div class="sw-notifications">
    <div class="sw-card sw-notifications__head">
      <div class="sw-tabs">
        <button
          v-for="type in TYPES"
          :key="type.value"
          class="sw-tabs__item"
          :class="{ 'is-active': activeType === type.value }"
          type="button"
          @click="switchType(type.value)"
        >
          {{ type.label }}
        </button>
      </div>
      <el-button text @click="readAll">全部标为已读</el-button>
    </div>

    <div v-loading="loading" class="sw-notifications__list">
      <div
        v-for="item in items"
        :key="item.id"
        class="sw-card sw-notification"
        :class="{ 'is-unread': !item.isRead }"
        @click="open(item)"
      >
        <p class="sw-notification__title">
          {{ item.payload?.title ?? item.actorNickname ?? '校园墙消息' }}
        </p>
        <p v-if="item.payload?.content" class="sw-notification__content sw-clamp-2">
          {{ item.payload.content }}
        </p>
        <p class="sw-muted">{{ relativeTime(item.createdAt) }}</p>
      </div>
      <EmptyState v-if="!loading && !items.length" text="暂无消息" />
    </div>
  </div>
</template>

<style scoped>
.sw-notifications {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-notifications__head {
  display: flex;
  align-items: center;
  gap: var(--sw-space-3);
  padding: var(--sw-space-3) var(--sw-space-4);
}

.sw-tabs {
  display: flex;
  gap: var(--sw-space-1);
  flex: 1;
}

.sw-tabs__item {
  min-height: var(--sw-control-size);
  padding: 0 var(--sw-space-3);
  border: none;
  border-radius: var(--sw-radius-sm);
  background: transparent;
  color: var(--sw-text-secondary);
  cursor: pointer;
}

.sw-tabs__item.is-active {
  background: var(--sw-primary-soft);
  color: var(--sw-primary-text);
  font-weight: 600;
}

.sw-notifications__list {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-2);
  min-height: 160px;
}

.sw-notification {
  padding: var(--sw-space-3) var(--sw-space-4);
  cursor: pointer;
}

.sw-notification.is-unread {
  border-left: 3px solid var(--sw-primary);
}

.sw-notification__title {
  margin: 0;
  font-weight: 600;
}

.sw-notification__content {
  margin: var(--sw-space-1) 0;
  color: var(--sw-text-secondary);
}
</style>
