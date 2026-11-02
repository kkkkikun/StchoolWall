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

const {
  recordError,
  recordApiFailure,
  setCurrentRoute,
  clearDiagnostics,
  collectDiagnostics,
  diagnosticsCount,
  installDiagnostics,
  APP_VERSION,
} = await import('../src/utils/diagnostics.ts')

describe('诊断采集', () => {
  beforeEach(() => {
    clearDiagnostics()
  })

  it('收集页面报错与失败请求', () => {
    recordError('白屏了', 'app.vue', 'Error: boom')
    recordApiFailure('get', '/posts?cursor=1', 500, '服务异常')

    const snapshot = collectDiagnostics()
    assert.equal(snapshot.errors.length, 1)
    assert.equal(snapshot.errors[0].message, '白屏了')
    assert.equal(snapshot.errors[0].source, 'app.vue')
    assert.equal(snapshot.api_failures.length, 1)
    assert.equal(snapshot.api_failures[0].method, 'GET')
    assert.equal(snapshot.api_failures[0].status, 500)
    assert.equal(diagnosticsCount(), 2)
  })

  it('错误与失败请求各自有上限，超出丢最旧的', () => {
    for (let index = 0; index < 40; index += 1) {
      recordError(`错误 ${index}`, 'test')
    }
    for (let index = 0; index < 30; index += 1) {
      recordApiFailure('post', `/posts/${index}`, 400, '参数错误')
    }
    const snapshot = collectDiagnostics()
    assert.equal(snapshot.errors.length, 30)
    assert.equal(snapshot.api_failures.length, 20)
    assert.equal(snapshot.errors[0].message, '错误 10')
    assert.equal(snapshot.api_failures[0].url, '/posts/10')
  })

  it('记录当前路由与端标识', () => {
    setCurrentRoute('/pc/post/42')
    const snapshot = collectDiagnostics()
    assert.equal(snapshot.route, '/pc/post/42')
    assert.equal(snapshot.app_version, APP_VERSION)
    assert.equal(APP_VERSION, 'pc')
  })

  it('清空后不留痕迹', () => {
    recordError('x', 'y')
    clearDiagnostics()
    assert.equal(diagnosticsCount(), 0)
    assert.equal(collectDiagnostics().errors.length, 0)
  })

  it('在 Node 环境下采集不会因为缺少 window 而崩溃', () => {
    const snapshot = collectDiagnostics()
    assert.equal(snapshot.viewport, '')
    assert.equal(snapshot.theme, 'light')
    assert.equal(snapshot.network, 'unknown')
    // Node 自带 navigator.userAgent，但不应被当成浏览器 UA 上报
    assert.ok(!snapshot.user_agent.includes('Mozilla'))
  })

  it('重复安装采集器不会叠加监听', () => {
    installDiagnostics()
    installDiagnostics()
    recordError('只记一次', 'test')
    assert.equal(collectDiagnostics().errors.length, 1)
  })
})
