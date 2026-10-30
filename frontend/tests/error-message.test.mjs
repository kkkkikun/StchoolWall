import test, { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, unlink } from 'node:fs/promises'
import ts from 'typescript'

// =============================================================================
// utils/errors.ts 网络错误映射纯函数测试（转译真实生产源码，非复制实现）
// =============================================================================

const compiledPath = new URL('./.temp-errors-module.mjs', import.meta.url)
const source = await readFile(new URL('../src/utils/errors.ts', import.meta.url), 'utf8')
await writeFile(compiledPath, ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText)

let mod
try {
  mod = await import(compiledPath.href)
} finally {
  await unlink(compiledPath).catch(() => {})
}

const { friendlyNetworkError, isNetworkError, NETWORK_ERROR_MESSAGE } = mod

describe('utils/errors.ts friendlyNetworkError (真实源码)', () => {
  it('request:fail 系列（uni/微信小程序网络层）映射为友好提示', () => {
    for (const msg of ['request:fail', 'request:fail timeout', 'request:fail abort']) {
      assert.equal(friendlyNetworkError(new Error(msg), '兜底'), NETWORK_ERROR_MESSAGE, msg)
    }
  })

  it('uni.uploadFile/downloadFile 网络失败（H5 XHR abort 实测 errMsg）映射为友好提示', () => {
    // 真实浏览器实测：路由 abort 后 uni.uploadFile 的 errMsg 恰为「uploadFile:fail」
    assert.equal(friendlyNetworkError(new Error('uploadFile:fail'), '请重试'), NETWORK_ERROR_MESSAGE)
    assert.equal(friendlyNetworkError(new Error('uploadFile:fail timeout'), '请重试'), NETWORK_ERROR_MESSAGE)
    assert.equal(friendlyNetworkError(new Error('downloadFile:fail'), '请重试'), NETWORK_ERROR_MESSAGE)
  })

  it('fetch/浏览器网络错误映射为友好提示', () => {
    for (const msg of ['fetch failed', 'Failed to fetch', 'NetworkError when attempting to fetch resource.']) {
      assert.equal(friendlyNetworkError(new TypeError(msg), '兜底'), NETWORK_ERROR_MESSAGE, msg)
    }
  })

  it('超时与中止类错误映射为友好提示', () => {
    for (const msg of ['timeout of 10000ms exceeded', 'Request timed out', 'The user aborted a request.']) {
      assert.equal(friendlyNetworkError(new Error(msg), '兜底'), NETWORK_ERROR_MESSAGE, msg)
    }
  })

  it('后端业务错误原样保留，不被映射吞掉', () => {
    assert.equal(friendlyNetworkError(new Error('内容包含敏感词，请修改后重试'), '兜底'),
      '内容包含敏感词，请修改后重试')
    assert.equal(friendlyNetworkError(new Error('账号或密码错误'), '兜底'), '账号或密码错误')
  })

  it('空消息使用调用方兜底文案', () => {
    assert.equal(friendlyNetworkError(new Error(''), '发布失败'), '发布失败')
    assert.equal(friendlyNetworkError(null, '登录失败，请稍后重试'), '登录失败，请稍后重试')
    assert.equal(friendlyNetworkError(undefined, '请重试'), '请重试')
  })

  it('isNetworkError 不泄露内部堆栈且仅匹配网络类消息', () => {
    assert.equal(isNetworkError(new Error('request:fail')), true)
    assert.equal(isNetworkError(new Error('内容包含敏感词')), false)
    assert.equal(isNetworkError({}), false)
  })
})
