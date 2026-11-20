import { request } from '@/utils/http'
import { mapComment } from './mappers'
import type { CommentItem, FavoriteResult, LikeResult, PageData } from './types'

type Raw = Record<string, any>

export async function listComments(postId: number, cursor?: number): Promise<PageData<CommentItem>> {
  const data = await request<PageData<Raw>>({
    url: `/posts/${postId}/comments`,
    params: { cursor },
  })
  return {
    items: (data.items ?? []).map(mapComment),
    next_cursor: data.next_cursor ?? null,
    has_more: !!data.has_more,
  }
}

export function createComment(postId: number, content: string): Promise<CommentItem> {
  return request<CommentItem>({
    url: `/posts/${postId}/comments`,
    method: 'POST',
    data: { content },
  })
}

export function deleteComment(commentId: number): Promise<unknown> {
  return request<unknown>({ url: `/comments/${commentId}`, method: 'DELETE' })
}

export function likePost(postId: number): Promise<LikeResult> {
  return request<LikeResult>({ url: `/posts/${postId}/like`, method: 'POST' })
}

export function unlikePost(postId: number): Promise<LikeResult> {
  return request<LikeResult>({ url: `/posts/${postId}/like`, method: 'DELETE' })
}

export function favoritePost(postId: number): Promise<FavoriteResult> {
  return request<FavoriteResult>({ url: `/posts/${postId}/favorite`, method: 'POST' })
}

export function unfavoritePost(postId: number): Promise<FavoriteResult> {
  return request<FavoriteResult>({ url: `/posts/${postId}/favorite`, method: 'DELETE' })
}

export function followUser(userId: string): Promise<{ followed: boolean }> {
  return request<{ followed: boolean }>({
    url: `/users/${encodeURIComponent(userId)}/follow`,
    method: 'POST',
  })
}

export function unfollowUser(userId: string): Promise<{ followed: boolean }> {
  return request<{ followed: boolean }>({
    url: `/users/${encodeURIComponent(userId)}/follow`,
    method: 'DELETE',
  })
}
