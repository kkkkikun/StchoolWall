import { request } from '@/utils/http'
import { mapPostBrief, mapPostDetail } from './mappers'
import type { PageData, PostBrief, PostCreatePayload, PostDetail } from './types'

type Raw = Record<string, any>

export interface PostQuery {
  cursor?: number
  post_type?: string
  category?: string
  tag_id?: number
  tag?: string
  order?: 'time'
}

function mapPage(data: PageData<Raw>): PageData<PostBrief> {
  return {
    items: (data.items ?? []).map(mapPostBrief),
    next_cursor: data.next_cursor ?? null,
    has_more: !!data.has_more,
  }
}

export async function getPosts(query: PostQuery = {}): Promise<PageData<PostBrief>> {
  const data = await request<PageData<Raw>>({ url: '/posts', params: query })
  return mapPage(data)
}

export async function getPostDetail(postId: number): Promise<PostDetail> {
  const raw = await request<Raw>({ url: `/posts/${postId}` })
  return mapPostDetail(raw)
}

export async function getHotPosts(limit = 10): Promise<PostBrief[]> {
  const data = await request<{ items: Raw[] }>({ url: '/posts/hot', params: { limit } })
  return (data.items ?? []).map(mapPostBrief)
}

export async function getFeaturedPosts(query: { cursor?: number; limit?: number; tag?: string } = {}) {
  const data = await request<PageData<Raw>>({ url: '/posts/featured', params: query })
  return mapPage(data)
}

export async function getFollowingFeed(cursor?: number): Promise<PageData<PostBrief>> {
  const data = await request<PageData<Raw>>({ url: '/posts/following', params: { cursor } })
  return mapPage(data)
}

export async function searchPosts(query: string, cursor?: number): Promise<PageData<PostBrief>> {
  const data = await request<PageData<Raw>>({ url: '/posts/search', params: { q: query, cursor } })
  return mapPage(data)
}

export async function getMyPosts(status?: number): Promise<PostBrief[]> {
  const data = await request<{ items: Raw[] }>({ url: '/posts/my', params: { status } })
  return (data.items ?? []).map(mapPostBrief)
}

export async function getUserPosts(userId: string, cursor?: number): Promise<PageData<PostBrief>> {
  const data = await request<PageData<Raw>>({
    url: `/users/${encodeURIComponent(userId)}/posts`,
    params: { cursor },
  })
  return mapPage(data)
}

export function createPost(payload: PostCreatePayload): Promise<{ post_id: number; status: number }> {
  return request<{ post_id: number; status: number }>({
    url: '/posts',
    method: 'POST',
    data: payload,
  })
}

/** 帖子状态：-2 软删除 / 2 归档 / 1 恢复 / -1 封禁。 */
export function updatePostStatus(postId: number, status: number): Promise<{ status: number }> {
  return request<{ status: number }>({
    url: `/posts/${postId}/status`,
    method: 'PUT',
    params: { status },
  })
}

export function deletePost(postId: number): Promise<{ status: number }> {
  return updatePostStatus(postId, -2)
}

export function reportPost(postId: number, reason: string, description?: string): Promise<unknown> {
  return request<unknown>({
    url: `/posts/${postId}/report`,
    method: 'POST',
    data: { reason, description },
  })
}
