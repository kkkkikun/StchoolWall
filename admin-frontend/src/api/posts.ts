/** 帖子管理 API。 */
import request from '@/utils/request'

export interface AdminPost {
  id: number
  post_type: string
  category: string | null
  content: string
  images_count: number
  price: number | null
  status: number
  is_pinned: boolean
  is_featured?: boolean
  author: { nickname: string; id: string }
  like_count: number
  comment_count: number
  view_count: number
  created_at: string
}

export interface PostsPage {
  items: AdminPost[]
  total: number
  page: number
  page_size: number
}

export function getPosts(params: Record<string, unknown>) {
  return request.get<any, PostsPage>('/admin/posts', { params })
}

export function updatePostStatus(id: number, status: number) {
  return request.put(`/admin/posts/${id}/status`, null, { params: { status } })
}

export function pinPost(id: number, pinned: boolean) {
  return request.put(`/admin/posts/${id}/pin`, { pinned })
}

export function featurePost(id: number, featured: boolean) {
  return request.put(`/admin/posts/${id}/featured`, { pinned: featured })
}

export function getFeatureCandidates(limit = 20) {
  return request.get<any, { items: AdminPost[] }>('/admin/posts/feature-candidates', { params: { limit } })
}

export function editPost(id: number, data: Partial<{ content: string; category: string; images: string[]; price: number }>) {
  return request.put(`/admin/posts/${id}`, data)
}

export function batchPostStatus(postIds: number[], status: number) {
  return request.post<any, { succeeded: number[]; failed: { id: number; reason: string }[] }>(
    '/admin/posts/batch-status', { post_ids: postIds, status },
  )
}

export function exportPostsUrl(status?: number, q?: string) {
  const p = new URLSearchParams()
  if (status !== undefined && status !== null) p.set('status', String(status))
  if (q) p.set('q', q)
  const qs = p.toString()
  return `/api/v1/admin/export/posts${qs ? `?${qs}` : ''}`
}
