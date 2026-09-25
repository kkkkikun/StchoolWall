/** Banner（首页轮播广告位）API：公开列表 + 管理端 CRUD。 */
import { get, post, put, del } from '@/utils/request'

/** 首页轮播项（后端下发，公开视角） */
export interface BannerItem {
  id: number
  title: string
  desc?: string | null
  tag?: string | null
  image_url?: string | null
  link_url?: string | null
  post_id?: number | null
  activity_id?: number | null
}

/** 管理端 Banner（含投放管理字段） */
export interface AdminBanner extends BannerItem {
  sort: number
  status: number
  start_at?: string | null
  end_at?: string | null
  created_at?: string
}

export interface BannerPayload {
  title: string
  desc?: string
  tag?: string
  image_url?: string
  link_url?: string
  post_id?: number
  activity_id?: number
  sort?: number
  status?: number
  start_at?: string | null
  end_at?: string | null
}

/** 首页轮播列表（公开，仅投放中） */
export async function getBanners(): Promise<BannerItem[]> {
  const res = await get<{ items: BannerItem[] }>('/banners')
  return res.items
}

/** 管理端：Banner 列表（全量含下架） */
export async function listBanners(status?: number) {
  return get<{ items: AdminBanner[]; next_cursor: number | null; has_more: boolean }>(
    '/admin/banners',
    status !== undefined ? { status } : undefined,
  )
}

/** 管理端：创建 Banner */
export async function createBanner(data: BannerPayload) {
  return post<AdminBanner>('/admin/banners', data)
}

/** 管理端：更新 Banner（部分字段） */
export async function updateBanner(id: number, data: Partial<BannerPayload>) {
  return put<AdminBanner>(`/admin/banners/${id}`, data)
}

/** 管理端：删除 Banner */
export async function deleteBanner(id: number) {
  return del<null>(`/admin/banners/${id}`)
}
