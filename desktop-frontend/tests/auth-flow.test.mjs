import { describe, it, beforeEach } from 'node:test'
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

// 浏览器环境 mock：localStorage 与 cookie
const store = new Map()
globalThis.localStorage = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, value) => store.set(key, value),
  removeItem: (key) => store.delete(key),
}
globalThis.document = { cookie: '' }
// 非安全上下文 = 纯 HTTP 部署，客户端类型应退化为 native
// axios 看到 window + document 会判定为浏览器环境，需要 location.href
globalThis.window = { isSecureContext: false, location: { href: 'http://localhost/' } }

const { http, setAccessToken, getAccessToken, setCsrfToken, setRefreshToken, restoreSession, CLIENT_TYPE } =
  await import('../src/utils/http.ts')

describe('HTTP 封装', () => {
  let calls = []

  beforeEach(() => {
    calls = []
    store.clear()
    setAccessToken(null)
    setCsrfToken(null)
    setRefreshToken(null)
  })

  function respond(config, data, status = 200) {
    calls.push(config)
    return {
      data: { code: 0, data },
      status,
      statusText: 'OK',
      headers: {},
      config,
    }
  }

  it('纯 HTTP 环境下客户端类型退化为 native，刷新令牌才能拿得到', () => {
    assert.equal(CLIENT_TYPE, 'native')
  })

  it('请求带上客户端类型与访问令牌', async () => {
    setAccessToken('token-abc')
    http.defaults.adapter = async (config) => respond(config, { ok: true })
    await http.get('/posts')
    const headers = calls[0].headers
    assert.equal(headers['X-Client-Type'], 'native')
    assert.equal(headers.Authorization, 'Bearer token-abc')
  })

  it('有 CSRF 令牌时一并带上', async () => {
    setAccessToken('token-abc')
    setCsrfToken('csrf-xyz')
    http.defaults.adapter = async (config) => respond(config, { ok: true })
    await http.get('/posts')
    assert.equal(calls[0].headers['X-CSRF-Token'], 'csrf-xyz')
  })

  it('业务码非 0 时抛出带后端提示的错误', async () => {
    http.defaults.adapter = async (config) => ({
      ...respond(config, null),
      data: { code: 400, message: '投稿暂时关闭' },
    })
    await assert.rejects(() => http.get('/posts'), (error) => {
      assert.equal(error.message, '投稿暂时关闭')
      assert.equal(error.code, 400)
      return true
    })
  })

  it('401 时先用刷新通道换令牌再重放原请求', async () => {
    setAccessToken('stale-token')
    setRefreshToken('refresh-token')
    let postsCalls = 0
    http.defaults.adapter = async (config) => {
      if (config.url.endsWith('/auth/refresh')) {
        return respond(config, { access_token: 'fresh-token', refresh_token: 'refresh-token-2' })
      }
      postsCalls += 1
      if (postsCalls === 1) {
        const error = new Error('Request failed with status code 401')
        error.response = { status: 401, data: { detail: 'Unauthorized' } }
        error.config = config
        throw error
      }
      return respond(config, { items: [] })
    }
    const response = await http.get('/posts')
    assert.equal(response.data.data.items.length, 0)
    assert.equal(getAccessToken(), 'fresh-token')
  })

  it('刷新后的新令牌会替换本地存储里的刷新令牌', async () => {
    setRefreshToken('refresh-token')
    http.defaults.adapter = async (config) => respond(config, { access_token: 'fresh', refresh_token: 'rotated' })
    const session = await restoreSession()
    assert.equal(session?.access_token, 'fresh')
    assert.equal(store.get('sw_refresh_token'), 'rotated')
  })
})
