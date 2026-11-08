/**
 * 后端返回体的前端类型（防腐蚀层）。
 *
 * 后端字段是 snake_case，这里统一成 camelCase，映射逻辑集中在 mappers.ts，
 * 视图层不直接接触后端原始结构。
 * 字段依据 backend/app/routers/*.py 与 release/openapi.json 核对。
 */

/** 统一响应封装：后端所有端点都返回这个形状。 */
export interface ApiEnvelope<T> {
  code: number
  message?: string
  data: T
}

/** 游标分页结果。 */
export interface PageData<T> {
  items: T[]
  next_cursor: number | null
  has_more: boolean
}

/** 帖子作者摘要。 */
export interface PostAuthor {
  id: number
  nickname: string
  avatarUrl?: string | null
}

/** 帖子标签。 */
export interface PostTag {
  id: number
  name: string
}

/** 信息流里的一条帖子。 */
export interface PostBrief {
  id: number
  postType: string
  content: string
  images: string[]
  price?: number
  status: number
  isPinned: boolean
  isFeatured: boolean
  createdAt: string
  updatedAt: string
  author: PostAuthor
  tags: PostTag[]
  category: string | null
  likeCount: number
  commentCount: number
  viewCount: number
  isLiked: boolean
  isFavorited: boolean
}

/** 帖子详情（信息流字段 + 详情独有字段）。 */
export interface PostDetail extends PostBrief {
  contactInfo?: string
  isReported: boolean
  userId?: string
  isFollowing: boolean
}

/** 一条评论。 */
export interface CommentItem {
  id: number
  postId: number
  userId: string
  nickname: string
  avatarUrl?: string | null
  content: string
  createdAt: string
}

/** 校园墙标签。 */
export interface TagItem {
  id: number
  name: string
}

/** 首页轮播位。 */
export interface BannerItem {
  id: number
  title: string
  desc: string
  tag: string
  imageUrl: string | null
  linkUrl: string | null
  postId?: number | null
  activityId?: number | null
}

/** 登录会话返回。 */
export interface SessionData {
  access_token: string
  refresh_token?: string
  session_id: string
  expires_in: number
  role: string
  user_info: SessionUser
  csrf_token?: string
}

/** 会话里的用户信息。 */
export interface SessionUser {
  id: string
  nickname: string
  is_verified: boolean
}

/** 自己的资料（含 real_name / student_id，仅本人与管理员可见）。 */
export interface MyProfile {
  nickname: string
  wechatId: string
  avatarUrl: string | null
  bannerUrl: string | null
  bio: string
  isVerified: boolean
  role: string
}

/** 他人主页资料（公开字段）。 */
export interface PublicProfile {
  id: string
  nickname: string
  avatarUrl: string | null
  bannerUrl: string | null
  bio: string
  isVerified: boolean
  school: string
  postsCount: number
  followingCount: number
  followersCount: number
  isFollowing: boolean
  isSelf: boolean
}

/** 站内通知。 */
export interface NotificationItem {
  id: string
  type: string
  actorNickname: string
  postId?: number | null
  commentId?: number | null
  isRead: boolean
  createdAt: string
  payload?: { title?: string; content?: string } | null
}

/** 未读消息概览。 */
export interface UnreadSummary {
  comment: number
  like: number
  favorite: number
  group: number
  moderation: number
  announcement: number
  im: number
}

/** 热门用户。 */
export interface HotUser {
  id: string
  nickname: string
  avatarUrl: string | null
  heat: number
}

/** 运行时开关（发布是否开放等）。 */
export interface RuntimeControls {
  publishing_enabled: boolean
}

/** 学生证认证状态。 */
export type VerificationStatus =
  | 'draft'
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'expired'
  | 'revoked'

/** 学生证认证记录（本人可见）。 */
export interface VerificationRecord {
  id: string
  schoolId: string
  status: VerificationStatus
  createdAt: string
  submittedAt: string | null
  reviewedAt: string | null
  /** 审核结论说明；被拒 / 撤销时会写明原因。 */
  reviewReason: string | null
  /** 认证有效期；为空表示未通过。 */
  verifiedUntil: string | null
  /** 证件照片的最迟删除时间（审核结束 7 天后删除，待审最长 14 天）。 */
  evidenceDeleteAfter: string | null
}

/** 已屏蔽的用户。 */
export interface BlockedUser {
  id: string
  nickname: string | null
}

/** 申诉对象类型。 */
export type AppealType = 'post' | 'comment' | 'party' | 'verification'

/** 申诉处理状态。 */
export type AppealStatus = 'pending' | 'accepted' | 'rejected'

/** 一条申诉记录。 */
export interface AppealRecord {
  id: string
  entityType: AppealType
  entityId: string
  reason: string
  status: AppealStatus
  /** 管理团队的处理说明。 */
  decisionReason: string | null
  createdAt: string
}

/** 发布帖子的入参。 */
export interface PostCreatePayload {
  post_type: string
  content: string
  category?: string
  media_ids?: string[]
  price?: number
  tag_ids?: number[]
}

/** 上传返回。 */
export interface UploadResult {
  media_id: string
  status: string
  public_url: string | null
}

/** 互动计数返回。 */
export interface LikeResult {
  liked: boolean
  like_count: number
}

/** 收藏状态返回。 */
export interface FavoriteResult {
  favorited: boolean
}
