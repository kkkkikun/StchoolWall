import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, unlink } from 'node:fs/promises'
import ts from 'typescript'

// =============================================================================
// 测试脚手架：编译并受控加载真实生产源码 src/api/posts.ts
// =============================================================================

const tempReqPath = new URL('./.temp-posts-req.mjs', import.meta.url)
const tempPostsPath = new URL('./.temp-posts-api.mjs', import.meta.url)

await writeFile(
  tempReqPath,
  `
  let mockResp = { items: [] };
  let lastCall = null;
  export function setMockResponse(r) { mockResp = r; }
  export function getLastCall() { return lastCall; }
  export const get = async (url, params) => {
    lastCall = { url, params };
    return mockResp;
  };
  export const post = async (url, data) => { lastCall = { url, data }; return {}; };
  export const put = async (url, data) => { lastCall = { url, data }; return {}; };
  export const del = async (url) => { lastCall = { url }; return {}; };
  `,
)

let postsTs = await readFile(new URL('../src/api/posts.ts', import.meta.url), 'utf8')
postsTs = postsTs.replace(/from\s+['"]@\/utils\/request['"]/g, 'from "./.temp-posts-req.mjs"')
const postsJs = ts.transpileModule(postsTs, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText

await writeFile(tempPostsPath, postsJs)

let postsModule, reqModule
try {
  reqModule = await import(tempReqPath.href)
  postsModule = await import(tempPostsPath.href)
} finally {
  await unlink(tempReqPath).catch(() => {})
  await unlink(tempPostsPath).catch(() => {})
}

const { mapBrief, mapDetail, getPosts, getHotPosts, getPostDetail } = postsModule
const { setMockResponse, getLastCall } = reqModule

describe('Posts & Hot Posts Mapping Suite (真实后端契约回归)', () => {
  it('1. 标准后端响应正常映射：严格按照 _post_to_dict 结构提取 content、view_count 与作者互动信息', () => {
    // 对应后端 backend/app/services/post.py _post_to_dict 标准格式
    const rawPost = {
      id: 101,
      post_type: 'general',
      category: '学习考研',
      content: '期末周自习室推荐！附空位情况\n图书馆二楼南侧采光好且插座充足，推荐大家去。',
      images: ['/static/images/study.jpg'],
      price: null,
      status: 1,
      is_pinned: false,
      is_featured: false,
      user: { nickname: '自习达人', avatar_url: '/static/avatar.png' },
      like_count: 12,
      comment_count: 5,
      view_count: 38000,
      is_liked: false,
      is_favorited: false,
      created_at: '2026-10-21T08:00:00Z',
    }

    const brief = mapBrief(rawPost)
    assert.equal(brief.id, 101)
    assert.equal(brief.post_type, 'general')
    assert.equal(brief.category, '学习考研')
    assert.equal(brief.content, '期末周自习室推荐！附空位情况\n图书馆二楼南侧采光好且插座充足，推荐大家去。')
    assert.deepEqual(brief.images, ['/static/images/study.jpg'])
    assert.equal(brief.view_count, 38000)
    assert.equal(brief.like_count, 12)
    assert.equal(brief.comment_count, 5)
    assert.equal(brief.author.nickname, '自习达人')
    assert.equal(brief.author.avatar_url, '/static/avatar.png')
    assert.equal(brief.is_pinned, false)
    assert.equal(brief.is_featured, false)
    assert.equal(brief.created_at, '2026-10-21T08:00:00Z')
  })

  it('2. 极值与空值安全防御：null/undefined/空对象及非标准类型入参安全兜底不崩溃', () => {
    assert.doesNotThrow(() => {
      const briefNull = mapBrief(null)
      assert.equal(briefNull.id, 0)
      assert.equal(briefNull.content, '')
      assert.equal(briefNull.view_count, 0)
      assert.equal(briefNull.like_count, 0)
      assert.equal(briefNull.comment_count, 0)
      assert.equal(briefNull.author.nickname, '匿名')
    })

    assert.doesNotThrow(() => {
      const briefEmpty = mapBrief({})
      assert.equal(briefEmpty.id, 0)
      assert.equal(briefEmpty.content, '')
      assert.equal(briefEmpty.view_count, 0)
      assert.equal(briefEmpty.author.nickname, '匿名')
      assert.deepEqual(briefEmpty.images, [])
      assert.deepEqual(briefEmpty.tags, [])
    })

    assert.doesNotThrow(() => {
      const briefMalformed = mapBrief({
        id: 'invalid-id',
        content: null,
        view_count: 'not-a-number',
        like_count: NaN,
        comment_count: null,
        images: 'not-array',
        user: null,
      })
      assert.equal(briefMalformed.id, 0)
      assert.equal(briefMalformed.content, '')
      assert.equal(briefMalformed.view_count, 0)
      assert.equal(briefMalformed.like_count, 0)
      assert.equal(briefMalformed.comment_count, 0)
      assert.equal(briefMalformed.author.nickname, '匿名')
      assert.deepEqual(briefMalformed.images, [])
    })
  })

  it('3. getHotPosts 与 getPosts 调用参数正确性', async () => {
    setMockResponse({ items: [] })

    await getHotPosts(4)
    const hotCall = getLastCall()
    assert.equal(hotCall.url, '/posts/hot')
    assert.deepEqual(hotCall.params, { limit: 4 })

    await getPosts(100, 'general', '广场', 'time')
    const feedCall = getLastCall()
    assert.equal(feedCall.url, '/posts')
    assert.deepEqual(feedCall.params, {
      cursor: 100,
      post_type: 'general',
      category: '广场',
      order: 'time',
      tag_id: undefined,
      tag: undefined,
    })
  })

  it('4. 热帖（getHotPosts）与普通信息流（getPosts）的一致性映射与隐私隔离', async () => {
    const rawPost = {
      id: 201,
      post_type: 'second_hand',
      content: '转让九成新山地自行车，可小刀',
      view_count: 500,
      like_count: 6,
      comment_count: 3,
      user: { nickname: '骑行同学', avatar_url: null },
      contact_wechat: 'private_wx_123', // 敏感隐私字段
      contact_info: '13800000000',     // 敏感隐私字段
    }

    setMockResponse({ items: [rawPost] })

    const [hotList, feedResponse] = await Promise.all([
      getHotPosts(1),
      getPosts(),
    ])

    assert.equal(hotList.length, 1)
    assert.equal(feedResponse.items.length, 1)

    // 两者 mapBrief 输出结构严格一致
    assert.deepEqual(hotList[0], feedResponse.items[0])

    // 关键隐私保护：PostBrief 绝对不泄露 contact_wechat 与 contact_info
    assert.equal(hotList[0].contact_wechat, undefined)
    assert.equal(hotList[0].contact_info, undefined)
    assert.equal(feedResponse.items[0].contact_wechat, undefined)
    assert.equal(feedResponse.items[0].contact_info, undefined)

    // 详情页 mapDetail 才受控提取联系方式
    const detail = mapDetail(rawPost)
    assert.equal(detail.contact_info, 'private_wx_123')
  })

  it('5. 十大热帖（getHotPosts 10条）：完整映射10条数据，每项均具备合法 content、view_count 与作者信息', async () => {
    const rawItems = Array.from({ length: 10 }, (_, i) => ({
      id: i + 1,
      post_type: 'general',
      category: '校园生活',
      content: `热帖测试内容第 ${i + 1} 条\n详细副标题与正文描述`,
      images: [],
      price: null,
      status: 1,
      is_pinned: false,
      is_featured: false,
      user: { nickname: `用户_${i + 1}`, avatar_url: null },
      like_count: (10 - i) * 3,
      comment_count: (10 - i) * 2,
      view_count: (10 - i) * 1000,
      is_liked: false,
      is_favorited: false,
      created_at: '2026-10-21T08:00:00Z',
    }))

    setMockResponse({ items: rawItems })
    const list = await getHotPosts(10)
    assert.equal(list.length, 10)
    for (let i = 0; i < 10; i++) {
      assert.equal(list[i].id, i + 1)
      assert.ok(list[i].content.startsWith(`热帖测试内容第 ${i + 1} 条`))
      assert.equal(list[i].view_count, (10 - i) * 1000)
      assert.equal(list[i].author.nickname, `用户_${i + 1}`)
    }
  })
})
