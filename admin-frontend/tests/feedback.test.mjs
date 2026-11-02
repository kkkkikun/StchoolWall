import { describe, it, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { register } from 'node:module'
import { pathToFileURL } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

// Node 环境下的浏览器全局 Mock
const noop = () => {}
globalThis.localStorage = {
  store: {},
  removeItem: (k) => { delete globalThis.localStorage.store[k] },
  getItem: (k) => globalThis.localStorage.store[k] || null,
  setItem: (k, v) => { globalThis.localStorage.store[k] = v },
}

let cookieStore = new Map()
globalThis.document = {
  createElement: () => ({ setAttribute: noop, appendChild: noop, style: {}, click: noop }),
  head: { appendChild: noop },
  body: { appendChild: noop },
  addEventListener: noop,
  removeEventListener: noop,
}
Object.defineProperty(globalThis.document, 'cookie', {
  get: () => Array.from(cookieStore.entries()).map(([k, v]) => `${k}=${v}`).join('; '),
  set: (val) => {
    const [pair] = val.split(';')
    const eqIdx = pair.indexOf('=')
    if (eqIdx !== -1) {
      const key = pair.slice(0, eqIdx).trim()
      const value = pair.slice(eqIdx + 1).trim()
      if (val.includes('Max-Age=0') || !value) cookieStore.delete(key)
      else cookieStore.set(key, value)
    }
  },
  configurable: true,
})

globalThis.location = { pathname: '/feedback', assign: noop }
globalThis.window = {
  location: globalThis.location,
  addEventListener: noop,
  removeEventListener: noop,
  navigator: { userAgent: 'Mozilla/5.0 Node.js' },
}

import { ElMessage } from 'element-plus'
ElMessage.error = noop
ElMessage.success = noop
ElMessage.warning = noop

// 解析 hook：支持 '@/...' 别名与自动补 .ts
const aliasLoader = `
import { pathToFileURL } from "node:url";
import path from "node:path";
import fs from "node:fs";

function withExt(target) {
  if (fs.existsSync(target) && fs.statSync(target).isFile()) return target;
  for (const ext of [".ts", ".js", ".mjs"]) {
    if (fs.existsSync(target + ext)) return target + ext;
  }
  return null;
}

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("@/")) {
    const sub = specifier.slice(2);
    const roots = [path.resolve(process.cwd(), "src", sub)];
    // 仓库根目录运行时再兜一层，避免 cwd 不同导致解析失败
    roots.push(path.resolve(process.cwd(), "admin-frontend/src", sub));
    for (const candidate of roots) {
      const resolved = withExt(candidate);
      if (resolved) return nextResolve(pathToFileURL(resolved).href, context);
    }
  }
  return nextResolve(specifier, context);
}
`
register('data:text/javascript,' + encodeURIComponent(aliasLoader), import.meta.url)

const { default: request } = await import('../src/utils/request.ts')
const {
  getFeedbackList,
  getFeedbackStats,
  getFeedbackDetail,
  getFeedbackScreenshot,
  updateFeedback,
} = await import('../src/api/feedback.ts')

describe('管理台反馈 API', { concurrency: false }, () => {
  let intercepted = []

  beforeEach(() => {
    intercepted = []
    request.defaults.adapter = async (config) => {
      intercepted.push(config)
      const payload = {
        code: 0,
        data: config.url?.includes('/screenshot/')
          ? new Blob(['fake-jpeg'], { type: 'image/jpeg' })
          : { items: [], total: 0, page: 1 },
      }
      return {
        data: payload,
        status: 200,
        statusText: 'OK',
        headers: { 'content-type': 'application/json' },
        config,
      }
    }
  })

  it('列表请求带上筛选与分页参数', async () => {
    await getFeedbackList({ status: 'open', category: 'bug', keyword: '白屏', page: 2 })
    const config = intercepted[0]
    assert.equal(config.url, '/admin/feedback')
    assert.equal(config.method, 'get')
    assert.equal(config.params.status, 'open')
    assert.equal(config.params.category, 'bug')
    assert.equal(config.params.keyword, '白屏')
    assert.equal(config.params.page, 2)
  })

  it('统计与详情路径正确', async () => {
    await getFeedbackStats()
    await getFeedbackDetail(42)
    assert.equal(intercepted[0].url, '/admin/feedback/stats')
    assert.equal(intercepted[1].url, '/admin/feedback/42')
  })

  it('截图按 blob 取回，否则 img 标签拿不到鉴权头的内容', async () => {
    const blob = await getFeedbackScreenshot(42, 0)
    assert.equal(intercepted[0].url, '/admin/feedback/42/screenshot/0')
    assert.equal(intercepted[0].responseType, 'blob')
    assert.ok(blob instanceof Blob)
  })

  it('更新走 multipart，备注允许为空字符串以便清空', async () => {
    await updateFeedback(42, { status: 'resolved', note: '' })
    const config = intercepted[0]
    assert.equal(config.url, '/admin/feedback/42')
    assert.equal(config.method, 'put')
    assert.ok(config.data instanceof FormData)
    assert.equal(config.data.get('status'), 'resolved')
    assert.equal(config.data.get('note'), '')
  })
})
