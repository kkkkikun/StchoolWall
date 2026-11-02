import { http, request } from '@/utils/http'
import { mapBanner, mapTag } from './mappers'
import type { BannerItem, RuntimeControls, TagItem, UploadResult } from './types'

type Raw = Record<string, any>

/** 校园墙标签列表。 */
export async function getTags(): Promise<TagItem[]> {
  const data = await request<Raw[]>({ url: '/tags' })
  return (data ?? []).map(mapTag)
}

/** 首页轮播位。 */
export async function getBanners(): Promise<BannerItem[]> {
  const data = await request<{ items: Raw[] }>({ url: '/banners' })
  return (data.items ?? []).map(mapBanner)
}

/** 运行时开关：发布是否开放。 */
export function getRuntimeControls(): Promise<RuntimeControls> {
  return request<RuntimeControls>({ url: '/runtime-controls' })
}

/** 上传前先问后端要上传配置（provider、限值）。 */
export function getUploadConfig(filename: string, contentType: string): Promise<Raw> {
  return request<Raw>({
    url: '/upload/config',
    params: { filename, content_type: contentType },
  })
}

/**
 * 直传图片。
 *
 * 生产环境发帖必须用 media_id：后端在生产会拒绝 images 字段，
 * 图片先进入隔离区待审核，审核通过后才写进帖子。
 */
export async function uploadImage(file: File, kind: 'avatars' | 'banners' | 'posts'): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  const response = await http.post<{ code: number; data: UploadResult }>('/upload/direct', form, {
    params: { kind },
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data.data
}

/** 查询已上传媒体的审核状态。 */
export function getMediaStatus(mediaId: string): Promise<Raw> {
  return request<Raw>({ url: `/upload/media/${encodeURIComponent(mediaId)}` })
}
