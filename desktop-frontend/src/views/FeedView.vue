<script setup lang="ts">
/** 首页信息流：推荐 / 最新 / 热门 / 精华四个视角，游标翻页。 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
import PostCard from '@/components/PostCard.vue'
import { getBanners } from '@/api/content'
import { getFeaturedPosts, getHotPosts, getPosts } from '@/api/posts'
import type { BannerItem, PostBrief } from '@/api/types'

type FeedTab = 'recommend' | 'latest' | 'hot' | 'featured'

const router = useRouter()

const TABS: { key: FeedTab; label: string }[] = [
  { key: 'recommend', label: '推荐' },
  { key: 'latest', label: '最新' },
  { key: 'hot', label: '热门' },
  { key: 'featured', label: '精华' },
]

const HOT_LIMIT = 20
const activeTab = ref<FeedTab>('recommend')
const posts = ref<PostBrief[]>([])
const banners = ref<BannerItem[]>([])
const cursor = ref<number | null>(null)
const hasMore = ref(true)
const loading = ref(false)

async function loadFirstPage(): Promise<void> {
  loading.value = true
  try {
    if (activeTab.value === 'hot') {
      posts.value = await getHotPosts(HOT_LIMIT)
      hasMore.value = false
      return
    }
    if (activeTab.value === 'featured') {
      const page = await getFeaturedPosts({ limit: HOT_LIMIT })
      posts.value = page.items
      cursor.value = page.next_cursor
      hasMore.value = page.has_more
      return
    }
    const page = await getPosts(activeTab.value === 'latest' ? { order: 'time' } : {})
    posts.value = page.items
    cursor.value = page.next_cursor
    hasMore.value = page.has_more
  } finally {
    loading.value = false
  }
}

async function loadMore(): Promise<void> {
  if (loading.value || !hasMore.value || cursor.value === null) return
  loading.value = true
  try {
    if (activeTab.value === 'featured') {
      const page = await getFeaturedPosts({ cursor: cursor.value, limit: HOT_LIMIT })
      posts.value = [...posts.value, ...page.items]
      cursor.value = page.next_cursor
      hasMore.value = page.has_more
      return
    }
    const page = await getPosts({
      cursor: cursor.value,
      ...(activeTab.value === 'latest' ? { order: 'time' } : {}),
    })
    posts.value = [...posts.value, ...page.items]
    cursor.value = page.next_cursor
    hasMore.value = page.has_more
  } finally {
    loading.value = false
  }
}

function switchTab(tab: FeedTab): void {
  if (activeTab.value === tab) return
  activeTab.value = tab
  posts.value = []
  cursor.value = null
  hasMore.value = true
  loadFirstPage()
}

function openBanner(banner: BannerItem): void {
  if (banner.postId) router.push(`/post/${banner.postId}`)
}

onMounted(async () => {
  banners.value = await getBanners().catch(() => [])
  await loadFirstPage()
})
</script>

<template>
  <div class="sw-feed">
    <section v-if="banners.length" class="sw-banners">
      <el-carousel height="120px" :interval="5000" arrow="hover">
        <el-carousel-item v-for="banner in banners" :key="banner.id">
          <div class="sw-banner" @click="openBanner(banner)">
            <img v-if="banner.imageUrl" :src="banner.imageUrl" :alt="banner.title" class="sw-banner__image" />
            <div class="sw-banner__text">
              <span class="sw-banner__tag">{{ banner.tag }}</span>
              <span class="sw-banner__title">{{ banner.title }}</span>
              <span v-if="banner.desc" class="sw-banner__desc sw-clamp-1">{{ banner.desc }}</span>
            </div>
          </div>
        </el-carousel-item>
      </el-carousel>
    </section>

    <div class="sw-tabs">
      <button
        v-for="tab in TABS"
        :key="tab.key"
        class="sw-tabs__item"
        :class="{ 'is-active': activeTab === tab.key }"
        type="button"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <div v-loading="loading && !posts.length" class="sw-feed__list">
      <PostCard v-for="post in posts" :key="post.id" :post="post" />
      <EmptyState v-if="!loading && !posts.length" text="还没有帖子" hint="换个视角看看，或者发一条。" />
    </div>

    <div class="sw-feed__more">
      <el-button v-if="hasMore" :loading="loading" @click="loadMore">加载更多</el-button>
      <p v-else-if="posts.length" class="sw-muted">已经到底了</p>
    </div>
  </div>
</template>

<style scoped>
.sw-feed {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-banner {
  position: relative;
  height: 120px;
  border-radius: var(--sw-radius);
  overflow: hidden;
  background: var(--sw-surface-muted);
  cursor: pointer;
}

.sw-banner__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.sw-banner__text {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: var(--sw-space-3);
  display: flex;
  align-items: center;
  gap: var(--sw-space-2);
  /* 图片上的文字要有暗化层，否则最坏情况对比度不达标 */
  background: linear-gradient(transparent, rgb(0 0 0 / 65%));
  color: #fff;
}

.sw-banner__tag {
  padding: 0 6px;
  border-radius: var(--sw-radius-sm);
  background: var(--sw-primary);
  font-size: var(--sw-text-xs);
}

.sw-banner__title {
  font-weight: 600;
}

.sw-banner__desc {
  opacity: 0.85;
  font-size: var(--sw-text-xs);
}

.sw-tabs {
  display: flex;
  gap: var(--sw-space-1);
  background: var(--sw-surface);
  border: 1px solid var(--sw-border);
  border-radius: var(--sw-radius);
  padding: var(--sw-space-1);
}

.sw-tabs__item {
  min-height: var(--sw-control-size);
  padding: 0 var(--sw-space-4);
  border: none;
  border-radius: var(--sw-radius-sm);
  background: transparent;
  color: var(--sw-text-secondary);
  font-size: var(--sw-text-base);
  cursor: pointer;
}

.sw-tabs__item.is-active {
  background: var(--sw-primary-soft);
  color: var(--sw-primary);
  font-weight: 600;
}

.sw-feed__list {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-3);
  min-height: 120px;
}

.sw-feed__more {
  display: flex;
  justify-content: center;
  padding: var(--sw-space-3) 0 var(--sw-space-5);
}
</style>
