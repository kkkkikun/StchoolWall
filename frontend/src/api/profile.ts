/** 个人主页 API：公开资料 / 关注列表 / 粉丝列表 / 主页帖子。 */
import { get, post, del } from '@/utils/request'
import type { PostBrief, PostListResponse } from '@/types/api'

export interface UserProfile {
  id: string
  nickname: string
  avatar_url: string | null
  banner_url?: string | null
  bio?: string | null
  is_verified: boolean
  school: string | null
  posts_count: number
  following_count: number
  followers_count: number
  is_following: boolean
  is_self: boolean
}

export interface UserBrief {
  id: string
  nickname: string
  avatar_url: string | null
  is_verified: boolean
  is_following: boolean
}

/** 公开资料 */
export function getProfile(userId: string) {
  return get<UserProfile>(`/users/${userId}/profile`)
}

/** 关注列表 */
export function getFollowing(userId: string) {
  return get<{ items: UserBrief[] }>(`/users/${userId}/following`)
}

/** 粉丝列表 */
export function getFollowers(userId: string) {
  return get<{ items: UserBrief[] }>(`/users/${userId}/followers`)
}

/** 主页帖子 */
export function getUserPosts(userId: string, cursor?: number): Promise<PostListResponse> {
  return get<PostListResponse>(`/users/${userId}/posts`, { cursor })
}

/** 关注（幂等） */
export function followUser(userId: string) {
  return post<{ followed: boolean }>(`/users/${userId}/follow`)
}

/** 取消关注 */
export function unfollowUser(userId: string) {
  return del<{ followed: boolean }>(`/users/${userId}/follow`)
}

export type { PostBrief }

/** 热门用户榜（公开）：按帖子获赞总数 Top N */
export interface HotUser {
  id: string
  nickname: string
  heat: number
}
export function getHotRanking(limit = 5) {
  return get<{ items: HotUser[] }>('/user/hot-ranking', { limit })
}
