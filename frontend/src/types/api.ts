/** 帖子类型（对齐后端 post_type 取值） */
export type PostType = 'lost_found' | 'second_hand' | 'carpool' | 'general' | 'advertisement'

/** 帖子状态 */
export type PostStatus = -2 | -1 | 0 | 1 | 2

/** 帖子状态映射 */
export const POST_STATUS_MAP: Record<PostStatus, string> = {
  '-2': '已删除',
  '-1': '封禁',
  0: '待审核',
  1: '正常',
  2: '已归档',
}

/** 帖子类型映射 */
export const POST_TYPE_MAP: Record<PostType, string> = {
  lost_found: '失物招领',
  second_hand: '二手交易',
  carpool: '拼车出行',
  general: '校园生活',
  advertisement: '广告',
}

/** 标签 */
export interface Tag {
  id: number
  name: string
}

/** 帖子列表项（简略） */
export interface PostBrief {
  id: number
  post_type: PostType
  content: string
  images?: string[]
  price?: number
  status: PostStatus
  is_pinned: boolean
  created_at: string
  updated_at: string
  author: {
    id: number
    nickname: string
    avatar_url?: string
  }
  tags?: Tag[]
  // 互动字段（后端 backend-social-layer 模块 A）
  like_count?: number
  comment_count?: number
  view_count?: number
  is_liked?: boolean
  is_favorited?: boolean
  _is_my_post?: boolean
  _report_count?: number
}

/** 帖子详情（含隐私隔离） */
export interface PostDetail extends PostBrief {
  view_count: number
  contact_info?: string
  is_reported?: boolean
}

/** 帖子列表响应 */
export interface PostListResponse {
  items: PostBrief[]
  next_cursor: number | null
  has_more: boolean
}

/** 发帖请求 */
export interface PostCreate {
  post_type: PostType
  content: string
  images?: string[]
  price?: number
  tag_ids?: number[]
}

/** 用户角色 */
export type UserRole = 'guest' | 'student' | 'admin'

/** 用户信息 */
export interface UserInfo {
  id: string
  nickname: string
  role: UserRole
  is_verified: boolean
  avatar_url?: string
  student_id?: string
  real_name?: string
  created_at: string
}

/** 微信登录响应 */
export interface LoginResponse {
  access_token: string
  user_info: UserInfo
}

/** 举报请求 */
export interface ReportRequest {
  reason: string
  description?: string
}
