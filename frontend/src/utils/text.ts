/** 把正文中的 #标签 拆成可点击的段落（X/Twitter 式）。 */
export interface ContentSegment {
  type: 'text' | 'tag'
  text: string
  tag: string
}

export function parseHashtags(text: string): ContentSegment[] {
  const parts: ContentSegment[] = []
  const re = /(#[\u4e00-\u9fa5A-Za-z0-9_-]+)/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text || ''))) {
    if (m.index > last) parts.push({ type: 'text', text: text.slice(last, m.index), tag: '' })
    const raw = m[1]
    parts.push({ type: 'tag', text: raw, tag: raw.slice(1) })
    last = m.index + raw.length
  }
  if (last < (text || '').length) parts.push({ type: 'text', text: text.slice(last), tag: '' })
  return parts.length ? parts : [{ type: 'text', text: text || '', tag: '' }]
}
