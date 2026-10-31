/**
 * Mock 数据类型 —— 仅用于前端预览，与真实后端契约（types/api.ts）分离。
 * 后端完善后，这些页面逐步切到真实 API，类型随之废弃。
 */

/** 十大热帖条目 */
export interface HotPost {
  id: number
  rank: number
  title: string
  isHot: boolean
  reads: string
}

/** 金刚区（首页宫格导航） */
export interface MenuItem {
  name: string
  icon: string // SVG 资源路径
  badge?: string
  path?: string
}

/** 首页广告位（可滑动轮播） */
export interface AdBanner {
  id: number
  icon?: string // SVG 资源路径
  title: string
  desc: string
  tag: string // 角标文字，如 "活动"/"热门"
  bg: string // CSS background（渐变）
}

/** 信息流动态 */
export interface Feed {
  id: number
  username: string
  avatar: string // SVG 资源路径（头像占位）
  avatarColor: string // 头像底色
  verified: boolean
  time: string
  content: string
  tag?: string
  images?: number // 占位图片张数
}

/** 组局分类筛选 */
export interface PartyCategory {
  id: number
  icon: string // SVG 资源路径
  name: string
  count: number
}

/** 组局/拼单条目 */
export interface PartyItem {
  id: number
  type: '组局' | '拼单'
  title: string
  username: string
  avatar: string
  avatarColor: string
  date: string
  joined: number
  total: number
  decorIcon?: string
}

/** 消息分类（4 圆） */
export interface MessageCategory {
  type: string
  name: string
  icon: string // SVG 资源路径
  colorClass: string
  unreadCount: number
}

/** 消息动态条目 */
export interface MessageItem {
  id: number
  postId: number
  avatar: string
  avatarColor: string
  nickname: string
  time: string
  brief: string
}

/** 个人页用户信息 */
export interface MineUser {
  avatarUrl: string
  nickName: string
  schoolName: string
}

/** 个人页统计 */
export interface MineStats {
  postsCount: number
  commentsCount: number
  favoritesCount: number
  footprintsCount: number
}

/** 个人页菜单项 */
export interface MineMenu {
  name: string
  icon: string // SVG 资源路径
  action: string
}
