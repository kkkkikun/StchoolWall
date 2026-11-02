import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { register } from 'node:module'
import { pathToFileURL } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

// 解析 hook：支持 '@/...' 别名、相对路径自动补 .ts
const aliasLoader = `
import { pathToFileURL } from "node:url";
import path from "node:path";
import fs from "node:fs";

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("@/")) {
    const resolved = path.resolve(process.cwd(), "src", specifier.slice(2));
    return nextResolve(pathToFileURL(withExt(resolved)).href, context);
  }
  if (specifier.startsWith(".") && !path.extname(specifier)) {
    const base = path.resolve(process.cwd(), path.dirname(context.parentURL.replace("file://", "")), specifier);
    return nextResolve(pathToFileURL(withExt(base)).href, context);
  }
  return nextResolve(specifier, context);
}

function withExt(target) {
  if (fs.existsSync(target)) return target;
  for (const ext of [".ts", ".js", ".mjs"]) {
    if (fs.existsSync(target + ext)) return target + ext;
  }
  if (fs.existsSync(path.join(target, "index.ts"))) return path.join(target, "index.ts");
  return target;
}
`
register('data:text/javascript,' + encodeURIComponent(aliasLoader), import.meta.url)

const { mapPostBrief, mapPostDetail, mapComment, mapNotification, mapPublicProfile } = await import(
  '../src/api/mappers.ts'
)
const { relativeTime, compactNumber, POST_TYPE_LABELS } = await import('../src/utils/format.ts')

describe('后端结构到前端类型的映射', () => {
  it('信息流条目按后端字段名映射成 camelCase', () => {
    const mapped = mapPostBrief({
      id: 42,
      post_type: 'second_hand',
      content: '出一张桌子',
      images: ['/api/v1/upload/media/abc/content'],
      price: 30,
      status: 1,
      is_pinned: true,
      is_featured: false,
      user: { nickname: '小张', avatar_url: '/static/avatars/a.png' },
      like_count: 3,
      comment_count: 2,
      view_count: 10,
      is_liked: true,
      is_favorited: false,
      created_at: '2026-11-02T00:00:00Z',
    })
    assert.equal(mapped.id, 42)
    assert.equal(mapped.postType, 'second_hand')
    assert.equal(mapped.author.nickname, '小张')
    assert.equal(mapped.likeCount, 3)
    assert.equal(mapped.isLiked, true)
    assert.equal(mapped.isPinned, true)
    assert.equal(mapped.price, 30)
  })

  it('缺字段的条目不抛异常，退回安全默认值', () => {
    const mapped = mapPostBrief({})
    assert.equal(mapped.postType, 'general')
    assert.equal(mapped.author.nickname, '匿名')
    assert.deepEqual(mapped.images, [])
    assert.equal(mapped.likeCount, 0)
  })

  it('非对象输入也返回合法结构', () => {
    const mapped = mapPostBrief(null)
    assert.equal(mapped.id, 0)
    assert.equal(mapped.content, '')
  })

  it('详情额外带出联系方式与举报状态', () => {
    const mapped = mapPostDetail({ id: 1, user_id: 'uuid-1', contact_wechat: 'wxid_x', is_reported: true })
    assert.equal(mapped.userId, 'uuid-1')
    assert.equal(mapped.contactInfo, 'wxid_x')
    assert.equal(mapped.isReported, true)
  })

  it('评论映射出作者昵称与头像', () => {
    const mapped = mapComment({ id: 7, post_id: 42, user_id: 'u1', content: '同求', user: { nickname: '小李' }, created_at: '2026-11-02T00:00:00Z' })
    assert.equal(mapped.nickname, '小李')
    assert.equal(mapped.postId, 42)
    assert.equal(mapped.content, '同求')
  })

  it('公告通知的正文从 payload 里取', () => {
    const mapped = mapNotification({ id: 'n1', type: 'announcement', is_read: false, payload: { title: '国庆放假', content: '10 月 1 日起停机' } })
    assert.equal(mapped.type, 'announcement')
    assert.equal(mapped.payload?.title, '国庆放假')
    assert.equal(mapped.isRead, false)
  })

  it('他人主页资料按公开字段名映射', () => {
    const mapped = mapPublicProfile({ id: 'u9', nickname: '小王', posts_count: 12, following_count: 3, followers_count: 8, is_self: false })
    assert.equal(mapped.postsCount, 12)
    assert.equal(mapped.followersCount, 8)
    assert.equal(mapped.isSelf, false)
  })
})

describe('展示层格式化', () => {
  it('相对时间按量级给出不同表述', () => {
    const now = Date.now()
    assert.equal(relativeTime(new Date(now - 30 * 1000).toISOString()), '刚刚')
    assert.equal(relativeTime(new Date(now - 5 * 60 * 1000).toISOString()), '5 分钟前')
    assert.equal(relativeTime(new Date(now - 3 * 3600 * 1000).toISOString()), '3 小时前')
    assert.equal(relativeTime(new Date(now - 2 * 86400 * 1000).toISOString()), '2 天前')
  })

  it('非法时间字符串原样返回', () => {
    assert.equal(relativeTime('not-a-date'), 'not-a-date')
  })

  it('大数字压缩成 k', () => {
    assert.equal(compactNumber(999), '999')
    assert.equal(compactNumber(1500), '1.5k')
    assert.equal(compactNumber(25000), '25k')
  })

  it('帖子类型有中文标签', () => {
    assert.equal(POST_TYPE_LABELS.general, '闲聊')
    assert.equal(POST_TYPE_LABELS.second_hand, '二手交易')
  })
})
