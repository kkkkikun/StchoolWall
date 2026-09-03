/**
 * 互动模块 API：评论 / 点赞 / 收藏 / 足迹 / 个人统计。
 * 后端变更 openspec/changes/backend-social-layer 模块 A。
 */
import { get, post, del } from '@/utils/request'

/** 帖子互动视角字段（列表/详情共用） */
export interface PostInteraction {
  like_count: number
  comment_count: number
  view_count: number
  is_liked: boolean
  is_favorited: boolean
}

export interface CommentItem {
  id: number
  post_id: number
  user_id: string
  content: string
  user: { nickname: string }
  created_at: string
  comment_count?: number
}

export interface CursorList<T> {
  items: T[]
  next_cursor: number | null
  has_more: boolean
}

export interface UserStats {
  posts_count: number
  comments_count: number
  favorites_count: number
  footprints_count: number
}

/** 点赞（幂等） */
export function likePost(postId: number) {
  return post<{ liked: boolean; like_count: number }>(`/posts/${postId}/like`)
}

/** 取消赞 */
export function unlikePost(postId: number) {
  return del<{ liked: boolean; like_count: number }>(`/posts/${postId}/like`)
}

/** 发评论 */
export function createComment(postId: number, content: string) {
  return post<CommentItem>(`/posts/${postId}/comments`, { content })
}

/** 评论列表 */
export function listComments(postId: number, cursor?: number) {
  return get<CursorList<CommentItem>>(`/posts/${postId}/comments`, { cursor })
}

/** 删除评论（仅本人） */
export function deleteComment(commentId: number) {
  return del(`/comments/${commentId}`)
}

/** 收藏（幂等） */
export function favoritePost(postId: number) {
  return post<{ favorited: boolean }>(`/posts/${postId}/favorite`)
}

/** 取消收藏 */
export function unfavoritePost(postId: number) {
  return del<{ favorited: boolean }>(`/posts/${postId}/favorite`)
}

/** 我的收藏 */
export function myFavorites<T = unknown>(cursor?: number) {
  return get<CursorList<T>>(`/me/favorites`, { cursor })
}

/** 我的点赞（点赞过的帖子） */
export function myLikes<T = unknown>(cursor?: number) {
  return get<CursorList<T>>(`/me/likes`, { cursor })
}

export interface MyCommentItem {
  id: number
  post_id: number
  content: string
  post_excerpt: string
  post_author: string
  created_at: string
}

/** 我发表过的评论（含所属帖子摘要） */
export function myComments(cursor?: number) {
  return get<CursorList<MyCommentItem>>(`/me/comments`, { cursor })
}

/** 我的足迹 */
export function myFootprints(cursor?: number) {
  return get<CursorList<unknown>>(`/me/footprints`, { cursor })
}

/** 个人统计 */
export function myStats() {
  return get<UserStats>(`/me/stats`)
}

/** 关注某用户（幂等） */
export function followUser(userId: string) {
  return post<{ followed: boolean }>(`/users/${userId}/follow`)
}

/** 取消关注 */
export function unfollowUser(userId: string) {
  return del<{ followed: boolean }>(`/users/${userId}/follow`)
}
