<script setup lang="ts">
/** 他人主页：资料 + 帖子 + 关注。 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import EmptyState from '@/components/EmptyState.vue'
import PostCard from '@/components/PostCard.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import { getPublicProfile } from '@/api/user'
import { getUserPosts } from '@/api/posts'
import { followUser, unfollowUser } from '@/api/social'
import type { PostBrief, PublicProfile } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()

const profile = ref<PublicProfile | null>(null)
const posts = ref<PostBrief[]>([])
const loading = ref(true)

const userId = computed(() => String(route.params.id ?? ''))

async function load(): Promise<void> {
  loading.value = true
  try {
    const [info, page] = await Promise.all([getPublicProfile(userId.value), getUserPosts(userId.value)])
    profile.value = info
    posts.value = page.items
  } catch {
    profile.value = null
  } finally {
    loading.value = false
  }
}

async function toggleFollow(): Promise<void> {
  if (!profile.value) return
  if (!auth.loggedIn) {
    ElMessage.warning('登录后才能关注')
    return
  }
  const result = profile.value.isFollowing
    ? await unfollowUser(profile.value.id)
    : await followUser(profile.value.id)
  profile.value.isFollowing = result.followed
}

watch(userId, load, { immediate: true })
onMounted(load)
</script>

<template>
  <div v-loading="loading" class="sw-profile">
    <section v-if="profile" class="sw-card sw-profile__head">
      <UserAvatar :src="profile.avatarUrl" :nickname="profile.nickname" :size="64" />
      <div class="sw-profile__info">
        <h3 class="sw-profile__name">
          {{ profile.nickname }}
          <el-tag v-if="profile.isVerified" size="small" type="success" effect="plain">已认证</el-tag>
        </h3>
        <p v-if="profile.school" class="sw-muted">{{ profile.school }}</p>
        <p v-if="profile.bio" class="sw-profile__bio">{{ profile.bio }}</p>
        <p class="sw-profile__stats">
          <span>帖子 {{ profile.postsCount }}</span>
          <span>关注 {{ profile.followingCount }}</span>
          <span>粉丝 {{ profile.followersCount }}</span>
        </p>
      </div>
      <el-button v-if="!profile.isSelf" :type="profile.isFollowing ? 'default' : 'primary'" @click="toggleFollow">
        {{ profile.isFollowing ? '已关注' : '关注' }}
      </el-button>
    </section>

    <div class="sw-profile__list">
      <PostCard v-for="post in posts" :key="post.id" :post="post" />
      <EmptyState v-if="!loading && !posts.length" text="还没有发布过帖子" />
    </div>
  </div>
</template>

<style scoped>
.sw-profile {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-profile__head {
  display: flex;
  gap: var(--sw-space-4);
  padding: var(--sw-space-5);
  align-items: flex-start;
}

.sw-profile__info {
  flex: 1;
  min-width: 0;
}

.sw-profile__name {
  margin: 0;
  font-size: var(--sw-text-xl);
  display: flex;
  align-items: center;
  gap: var(--sw-space-2);
}

.sw-profile__bio {
  margin: var(--sw-space-2) 0 0;
  color: var(--sw-text-secondary);
}

.sw-profile__stats {
  margin: var(--sw-space-3) 0 0;
  display: flex;
  gap: var(--sw-space-4);
  color: var(--sw-text-muted);
  font-size: var(--sw-text-sm);
}

.sw-profile__list {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-3);
}
</style>
