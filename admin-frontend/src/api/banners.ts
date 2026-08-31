/** 轮播广告 API。 */
import request from '@/utils/request'

export interface AdminBanner {
  id: number
  title: string
  desc: string | null
  tag: string | null
  image_url: string | null
  link_url: string | null
  post_id: number | null
  sort: number
  status: number
  start_at: string | null
  end_at: string | null
  created_at: string
}

export function getBanners(params?: Record<string, unknown>) {
  return request.get<any, { items: AdminBanner[]; next_cursor: number | null; has_more: boolean }>(
    '/admin/banners', { params },
  )
}

export function createBanner(data: Record<string, unknown>) {
  return request.post('/admin/banners', data)
}

export function updateBanner(id: number, data: Record<string, unknown>) {
  return request.put(`/admin/banners/${id}`, data)
}

export function deleteBanner(id: number) {
  return request.delete(`/admin/banners/${id}`)
}

/** 上传图片（multipart），返回 {public_url, path} */
export function uploadImage(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request.post<any, { public_url: string; path: string }>('/admin/upload/image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
