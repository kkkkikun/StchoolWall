import type { PostBrief, PostCreate, PostDetail, PostListResponse } from '@/types/api'
import { get, post, put } from '@/utils/request'

/**
 * 后端响应 → 前端类型映射（防腐蚀层）。
 * 后端列表项：{..., user:{nickname}, like_count, comment_count, view_count, is_liked, is_favorited}
 * 前端 PostBrief：{author:{...}, is_pinned, updated_at, tags?, + 互动字段}
 */
export type RawPost = Record<string, any>

export function mapBrief(raw: RawPost): PostBrief {
  if (!raw || typeof raw !== 'object') {
    return {
      id: 0,
      post_type: 'general',
      content: '',
      images: [],
      status: 1,
      is_pinned: false,
      is_featured: false,
      created_at: '',
      updated_at: '',
      author: { id: 0, nickname: '匿名' },
      tags: [],
      category: null,
      like_count: 0,
      comment_count: 0,
      view_count: 0,
      is_liked: false,
      is_favorited: false,
    }
  }

  return {
    id: Number(raw.id) || 0,
    post_type: raw.post_type || 'general',
    content: typeof raw.content === 'string' ? raw.content : '',
    images: Array.isArray(raw.images) ? raw.images : [],
    price: raw.price !== null && raw.price !== undefined ? Number(raw.price) : undefined,
    status: typeof raw.status === 'number' ? (raw.status as any) : 1,
    is_pinned: !!raw.is_pinned,
    is_featured: !!raw.is_featured,
    created_at: raw.created_at || '',
    updated_at: raw.updated_at || raw.created_at || '',
    author: {
      id: raw.author?.id ?? 0,
      nickname: raw.user?.nickname ?? raw.author?.nickname ?? '匿名',
      avatar_url: raw.user?.avatar_url ?? raw.author?.avatar_url,
    },
    tags: Array.isArray(raw.tags) ? raw.tags : [],
    category: raw.category ?? null,
    like_count: typeof raw.like_count === 'number' && !isNaN(raw.like_count) ? raw.like_count : 0,
    comment_count: typeof raw.comment_count === 'number' && !isNaN(raw.comment_count) ? raw.comment_count : 0,
    view_count: typeof raw.view_count === 'number' && !isNaN(raw.view_count) ? raw.view_count : 0,
    is_liked: !!raw.is_liked,
    is_favorited: !!raw.is_favorited,
  }
}

export function mapDetail(raw: RawPost): PostDetail {
  const brief = mapBrief(raw)
  return {
    ...brief,
    view_count: brief.view_count || 0,
    contact_info: raw.contact_wechat ?? raw.contact_info,
    is_reported: !!raw.is_reported,
    user_id: raw.user_id ? String(raw.user_id) : undefined,
    is_following: !!raw.is_following,
  }
}

/** 获取帖子列表（可按 post_type/category/tag_id/tag 过滤；order='time' 为最新流） */
export async function getPosts(
  cursor?: number, postType?: string, category?: string, order?: 'time', tagId?: number, tagText?: string,
): Promise<PostListResponse> {
  const data = await get<PostListResponse>('/posts', { cursor, post_type: postType, category, order, tag_id: tagId, tag: tagText })
  return {
    items: (data.items || []).map(mapBrief),
    next_cursor: data.next_cursor,
    has_more: data.has_more,
  }
}

/** 获取帖子详情 */
export async function getPostDetail(postId: number): Promise<PostDetail> {
  const raw = await get<RawPost>(`/posts/${postId}`)
  return mapDetail(raw)
}

/** 十大热帖 */
export async function getHotPosts(limit = 10): Promise<PostBrief[]> {
  const data = await get<{ items: RawPost[] }>('/posts/hot', { limit })
  return (data.items || []).map(mapBrief)
}

/** 精华流：经验贴等长尾内容，历史热度排序（无时间衰减） */
export async function getFeaturedPosts(cursor?: number, tagText?: string): Promise<PostListResponse> {
  const data = await get<PostListResponse>('/posts/featured', { cursor, tag: tagText })
  return {
    items: (data.items || []).map(mapBrief),
    next_cursor: data.next_cursor,
    has_more: data.has_more,
  }
}

/** 关注流（已关注用户的帖子） */
export async function getFollowingFeed(cursor?: number, tagText?: string): Promise<PostListResponse> {
  const data = await get<PostListResponse>('/posts/following', { cursor, tag: tagText })
  return {
    items: (data.items || []).map(mapBrief),
    next_cursor: data.next_cursor,
    has_more: data.has_more,
  }
}

/** 搜索帖子 */
export async function searchPosts(q: string, cursor?: number): Promise<PostListResponse> {
  const data = await get<PostListResponse>('/posts/search', { q, cursor })
  return {
    items: (data.items || []).map(mapBrief),
    next_cursor: data.next_cursor,
    has_more: data.has_more,
  }
}

/** 发布帖子 */
export function createPost(data: PostCreate) {
  return post<{ post_id: number; status: number }>('/posts', data)
}

/** 更新帖子状态（status: -2 软删除 / 2 归档 / 1 恢复 / -1 封禁） */
export function updatePostStatus(postId: number, status: number) {
  return put<{ status: number }>(`/posts/${postId}/status?status=${status}`)
}

/** 删除自己的帖子（软删除，status = -2） */
export function deletePost(postId: number) {
  return updatePostStatus(postId, -2)
}

/** 举报帖子 */
export function reportPost(postId: number, reason: string, description?: string) {
  return post(`/posts/${postId}/report`, { reason, description })
}
