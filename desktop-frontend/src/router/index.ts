import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import DesktopLayout from '@/layouts/DesktopLayout.vue'

const router = createRouter({
  // base 用构建期注入的 /pc/，与管理台的 /admin/ 同理
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: DesktopLayout,
      children: [
        { path: '', name: 'feed', component: () => import('@/views/FeedView.vue') },
        { path: 'search', name: 'search', component: () => import('@/views/SearchView.vue') },
        { path: 'tags', name: 'tags', component: () => import('@/views/TagsView.vue') },
        { path: 'tags/:name', name: 'tag-posts', component: () => import('@/views/TagPostsView.vue') },
        { path: 'post/:id', name: 'post', component: () => import('@/views/PostDetailView.vue') },
        { path: 'user/:id', name: 'profile', component: () => import('@/views/ProfileView.vue') },
        { path: 'login', name: 'login', component: () => import('@/views/LoginView.vue') },
        { path: 'register', name: 'register', component: () => import('@/views/RegisterView.vue') },
        {
          path: 'publish',
          name: 'publish',
          component: () => import('@/views/PublishView.vue'),
          meta: { requiresAuth: true },
        },
        {
          path: 'me/posts',
          name: 'my-posts',
          component: () => import('@/views/MyPostsView.vue'),
          meta: { requiresAuth: true },
        },
        {
          path: 'notifications',
          name: 'notifications',
          component: () => import('@/views/NotificationsView.vue'),
          meta: { requiresAuth: true },
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
          meta: { requiresAuth: true },
        },
        {
          path: 'verify',
          name: 'verify',
          component: () => import('@/views/VerifyView.vue'),
          meta: { requiresAuth: true },
        },
        {
          path: 'blocks',
          name: 'blocks',
          component: () => import('@/views/BlocksView.vue'),
          meta: { requiresAuth: true },
        },
        {
          path: 'appeals',
          name: 'appeals',
          component: () => import('@/views/AppealsView.vue'),
          meta: { requiresAuth: true },
        },
        {
          // 信息页用路由参数区分内容：/info/community、/info/privacy 等
          path: 'info/:type',
          name: 'info',
          component: () => import('@/views/InfoView.vue'),
        },
      ],
    },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFoundView.vue') },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  // 刷新页面后内存态丢失，先用刷新通道把会话接回来
  if (!auth.loggedIn && !auth.user) {
    await auth.restore()
  }
  if (to.meta.requiresAuth && !auth.loggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
