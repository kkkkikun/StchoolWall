/** 路由：登录守卫 + 后台布局。 */
import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/utils/request'

const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { title: '登录' } },
  {
    path: '/',
    component: () => import('@/layouts/AdminLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '看板' } },
      { path: 'posts', name: 'posts', component: () => import('@/views/PostsView.vue'), meta: { title: '帖子管理' } },
      { path: 'moderation-jobs', name: 'moderation-jobs', component: () => import('@/views/ModerationJobsView.vue'), meta: { title: '人工审核' } },
      { path: 'appeals', name: 'appeals', component: () => import('@/views/AppealsView.vue'), meta: { title: '申诉处理' } },
      { path: 'moderation-records', name: 'moderation-records', component: () => import('@/views/ModerationRecordsView.vue'), meta: { title: '审核记录' } },
      { path: 'sensitive-words', name: 'sensitive-words', component: () => import('@/views/SensitiveWordsView.vue'), meta: { title: '敏感词库' } },
      { path: 'student-verifications', name: 'student-verifications', component: () => import('@/views/StudentVerificationsView.vue'), meta: { title: '学生证认证' } },
      { path: 'users', name: 'users', component: () => import('@/views/UsersView.vue'), meta: { title: '用户管理' } },
      { path: 'reports', name: 'reports', component: () => import('@/views/ReportsView.vue'), meta: { title: '举报处理' } },
      { path: 'comments', name: 'comments', component: () => import('@/views/CommentsView.vue'), meta: { title: '评论管理' } },
      { path: 'parties', name: 'parties', component: () => import('@/views/PartiesView.vue'), meta: { title: '组局管理' } },
      { path: 'banners', name: 'banners', component: () => import('@/views/BannersView.vue'), meta: { title: '轮播广告' } },
      { path: 'announcements', name: 'announcements', component: () => import('@/views/AnnouncementsView.vue'), meta: { title: '公告群发' } },
      { path: 'logs', name: 'logs', component: () => import('@/views/LogsView.vue'), meta: { title: '操作日志' } },
      { path: 'admins', name: 'admins', component: () => import('@/views/AdminAccountsView.vue'), meta: { title: '管理员账号' } },
      { path: 'tags', name: 'tags', component: () => import('@/views/TagsView.vue'), meta: { title: '标签管理' } },
      { path: 'activities', name: 'activities', component: () => import('@/views/ActivitiesView.vue'), meta: { title: '站内活动' } },
    ],
  },
]

const router = createRouter({
  // 部署在 /admin/ 子路径时随 vite base 自动对齐（build --base=/admin/）
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach((to) => {
  if (to.path !== '/login' && !getToken()) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  document.title = `${to.meta.title || '管理后台'} · 鄂应墙`
})

export default router
