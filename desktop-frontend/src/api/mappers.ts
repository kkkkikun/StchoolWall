import type {
  AppealRecord,
  AppealStatus,
  AppealType,
  BannerItem,
  BlockedUser,
  CommentItem,
  HotUser,
  MyProfile,
  NotificationItem,
  PostBrief,
  PostDetail,
  PublicProfile,
  TagItem,
  VerificationRecord,
  VerificationStatus,
} from './types'

type Raw = Record<string, any>

function num(value: unknown): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function str(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function optionalStr(value: unknown): string | undefined {
  return typeof value === 'string' && value ? value : undefined
}

export function mapPostBrief(raw: Raw): PostBrief {
  if (!raw || typeof raw !== 'object') {
    return {
      id: 0,
      postType: 'general',
      content: '',
      images: [],
      status: 1,
      isPinned: false,
      isFeatured: false,
      createdAt: '',
      updatedAt: '',
      author: { id: 0, nickname: '匿名' },
      tags: [],
      category: null,
      likeCount: 0,
      commentCount: 0,
      viewCount: 0,
      isLiked: false,
      isFavorited: false,
    }
  }
  const author = raw.user ?? raw.author ?? {}
  return {
    id: num(raw.id),
    postType: str(raw.post_type) || 'general',
    content: str(raw.content),
    images: Array.isArray(raw.images) ? raw.images : [],
    price: raw.price === null || raw.price === undefined ? undefined : num(raw.price),
    status: num(raw.status) || 1,
    isPinned: !!raw.is_pinned,
    isFeatured: !!raw.is_featured,
    createdAt: str(raw.created_at),
    updatedAt: str(raw.updated_at) || str(raw.created_at),
    author: {
      id: num(author.id),
      nickname: str(author.nickname) || '匿名',
      avatarUrl: optionalStr(author.avatar_url) ?? null,
    },
    tags: Array.isArray(raw.tags)
      ? raw.tags.map((tag: Raw) => ({ id: num(tag.id), name: str(tag.name) }))
      : [],
    category: optionalStr(raw.category) ?? null,
    likeCount: num(raw.like_count),
    commentCount: num(raw.comment_count),
    viewCount: num(raw.view_count),
    isLiked: !!raw.is_liked,
    isFavorited: !!raw.is_favorited,
  }
}

export function mapPostDetail(raw: Raw): PostDetail {
  const brief = mapPostBrief(raw)
  return {
    ...brief,
    contactInfo: optionalStr(raw.contact_wechat),
    isReported: !!raw.is_reported,
    userId: optionalStr(raw.user_id),
    isFollowing: !!raw.is_following,
  }
}

export function mapComment(raw: Raw): CommentItem {
  const author = raw.user ?? raw.author ?? {}
  return {
    id: num(raw.id),
    postId: num(raw.post_id),
    userId: str(raw.user_id),
    nickname: str(author.nickname) || str(raw.nickname) || '匿名',
    avatarUrl: optionalStr(author.avatar_url) ?? null,
    content: str(raw.content),
    createdAt: str(raw.created_at),
  }
}

export function mapTag(raw: Raw): TagItem {
  return { id: num(raw.id), name: str(raw.name) }
}

export function mapBanner(raw: Raw): BannerItem {
  return {
    id: num(raw.id),
    title: str(raw.title),
    desc: str(raw.desc),
    tag: str(raw.tag),
    imageUrl: optionalStr(raw.image_url) ?? null,
    linkUrl: optionalStr(raw.link_url) ?? null,
    postId: raw.post_id === undefined ? null : num(raw.post_id),
    activityId: raw.activity_id === undefined ? null : num(raw.activity_id),
  }
}

export function mapMyProfile(raw: Raw): MyProfile {
  return {
    nickname: str(raw.nickname),
    wechatId: str(raw.wechat_id),
    avatarUrl: optionalStr(raw.avatar_url) ?? null,
    bannerUrl: optionalStr(raw.banner_url) ?? null,
    bio: str(raw.bio),
    isVerified: !!raw.is_verified,
    role: str(raw.role),
  }
}

export function mapPublicProfile(raw: Raw): PublicProfile {
  return {
    id: str(raw.id),
    nickname: str(raw.nickname) || '匿名',
    avatarUrl: optionalStr(raw.avatar_url) ?? null,
    bannerUrl: optionalStr(raw.banner_url) ?? null,
    bio: str(raw.bio),
    isVerified: !!raw.is_verified,
    school: str(raw.school),
    postsCount: num(raw.posts_count),
    followingCount: num(raw.following_count),
    followersCount: num(raw.followers_count),
    isFollowing: !!raw.is_following,
    isSelf: !!raw.is_self,
  }
}

export function mapNotification(raw: Raw): NotificationItem {
  const payload = raw.payload ?? null
  return {
    id: str(raw.id),
    type: str(raw.type),
    actorNickname: str(raw.actor?.nickname),
    postId: raw.post_id === null || raw.post_id === undefined ? null : num(raw.post_id),
    commentId: raw.comment_id === null || raw.comment_id === undefined ? null : num(raw.comment_id),
    isRead: !!raw.is_read,
    createdAt: str(raw.created_at),
    payload: payload && typeof payload === 'object' ? payload : null,
  }
}

export function mapHotUser(raw: Raw): HotUser {
  return {
    id: str(raw.id),
    nickname: str(raw.nickname) || '匿名',
    avatarUrl: optionalStr(raw.avatar_url) ?? null,
    heat: num(raw.heat),
  }
}

const VERIFICATION_STATUSES: VerificationStatus[] = [
  'draft',
  'pending',
  'approved',
  'rejected',
  'expired',
  'revoked',
]

/** 学生证认证记录。未知状态按草稿处理，避免视图层拿到意料之外的值。 */
export function mapVerificationRecord(raw: Raw): VerificationRecord {
  if (!raw || typeof raw !== 'object') {
    return {
      id: '',
      schoolId: '',
      status: 'draft',
      createdAt: '',
      submittedAt: null,
      reviewedAt: null,
      reviewReason: null,
      verifiedUntil: null,
      evidenceDeleteAfter: null,
    }
  }
  const status = str(raw.status) as VerificationStatus
  return {
    id: str(raw.id),
    schoolId: str(raw.school_id),
    status: VERIFICATION_STATUSES.includes(status) ? status : 'draft',
    createdAt: str(raw.created_at),
    submittedAt: optionalStr(raw.submitted_at) ?? null,
    reviewedAt: optionalStr(raw.reviewed_at) ?? null,
    reviewReason: optionalStr(raw.review_reason) ?? null,
    verifiedUntil: optionalStr(raw.verified_until) ?? null,
    evidenceDeleteAfter: optionalStr(raw.evidence_delete_after) ?? null,
  }
}

/** 已屏蔽的用户。 */
export function mapBlockedUser(raw: Raw): BlockedUser {
  return {
    id: str(raw.id),
    nickname: optionalStr(raw.nickname) ?? null,
  }
}

const APPEAL_TYPES: AppealType[] = ['post', 'comment', 'party', 'verification']
const APPEAL_STATUSES: AppealStatus[] = ['pending', 'accepted', 'rejected']

/** 申诉记录。 */
export function mapAppealRecord(raw: Raw): AppealRecord {
  const entityType = str(raw.entity_type) as AppealType
  const status = str(raw.status) as AppealStatus
  return {
    id: str(raw.id),
    entityType: APPEAL_TYPES.includes(entityType) ? entityType : 'post',
    entityId: str(raw.entity_id),
    reason: str(raw.reason),
    status: APPEAL_STATUSES.includes(status) ? status : 'pending',
    decisionReason: optionalStr(raw.decision_reason) ?? null,
    createdAt: str(raw.created_at),
  }
}
