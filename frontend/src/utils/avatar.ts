/**
 * 头像底色 / 首字前景色 —— 全站唯一来源。
 *
 * 背景：原先 10 个文件各自复制了一份「哈希取色」逻辑，且存在 5 套互不一致的调色板，
 * 导致同一用户在不同页面头像底色不同；且白字在浅色底上对比度仅 1.2~1.6:1，远低于 AA。
 *
 * 方案：统一一套柔和底色 + 统一深墨前景字。深墨在全部底色上最差 8.42:1，远超 WCAG AA 4.5:1。
 */

/** 统一头像底色（柔和色系，避免大面积高饱和刺眼） */
export const AVATAR_PALETTE = [
  '#ffd591', // 杏黄
  '#adc6ff', // 雾蓝
  '#b7eb8f', // 浅绿
  '#ffa39e', // 浅粉
  '#d3adf7', // 浅紫
  '#87e8de', // 薄荷
  '#ffccc7', // 浅橘粉
] as const

/**
 * 头像首字前景色（深墨）。
 * 与 AVATAR_PALETTE 全部底色组合后最差对比度 8.42:1（@ #ffa39e），满足 WCAG AA。
 * 该色不随主题翻转：头像底色是固定浅色系，深色模式下同样需要深墨字。
 */
export const AVATAR_INK = '#1a2229'

/** 昵称 → 头像底色：同一昵称在全站得到同一底色 */
export function avatarColor(seed: string | undefined | null): string {
  const s = seed || ''
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return AVATAR_PALETTE[h % AVATAR_PALETTE.length]
}
