import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, unlink } from 'node:fs/promises'
import ts from 'typescript'

// =============================================================================
// utils/diagnostics.ts 诊断采集测试（转译真实生产源码，非复制实现）
// =============================================================================

const compiledPath = new URL('./.temp-diagnostics-module.mjs', import.meta.url)
const themeStubPath = new URL('./.temp-diagnostics-theme.mjs', import.meta.url)

// 主题来自 utils/theme.ts（依赖 vue + uni 存储），测试里用固定值替身
await writeFile(
  themeStubPath,
  `export function useThemeMode() { return { value: 'dark' } }\n`,
)

let source = await readFile(new URL('../src/utils/diagnostics.ts', import.meta.url), 'utf8')
source = source.replace(/from\s+['"]\.\/theme['"]/g, 'from "./.temp-diagnostics-theme.mjs"')
await writeFile(compiledPath, ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText)

// uni 全局替身：覆盖诊断采集用到的 API
const uniStub = {
  getSystemInfoSync: () => ({ windowWidth: 390, windowHeight: 844, platform: 'ios', system: 'iOS 17' }),
  getNetworkType: (options) => options.success({ networkType: 'wifi' }),
  onError: () => {},
  onUnhandledRejection: () => {},
}
globalThis.uni = uniStub
globalThis.getCurrentPages = () => [{ route: 'pages/index/index' }]

let mod
try {
  mod = await import(compiledPath.href)
} finally {
  await unlink(compiledPath).catch(() => {})
  await unlink(themeStubPath).catch(() => {})
}

const { recordError, recordApiFailure, clearDiagnostics, collectDiagnostics, diagnosticsCount } = mod

describe('utils/diagnostics.ts 诊断采集（真实源码）', () => {
  it('1. 异常环形缓冲上限 50 条：超出丢最旧的', async () => {
    clearDiagnostics()
    for (let i = 0; i < 60; i += 1) recordError(`异常 ${i}`, 'test')
    const data = await collectDiagnostics()
    assert.equal(data.errors.length, 50)
    assert.equal(data.errors[0].message, '异常 10')
  })

  it('2. 采集结果：路由/视口/主题/网络/应用版本齐全且可 JSON 序列化', async () => {
    clearDiagnostics()
    recordError('boom', 'test', 'stack-line')
    recordApiFailure('GET', '/posts', 500, '服务器错误')
    const data = await collectDiagnostics()
    assert.equal(data.route, 'pages/index/index')
    assert.equal(data.viewport, '390x844')
    assert.equal(data.theme, 'dark')
    assert.equal(data.network, 'wifi')
    assert.equal(data.app_version, 'h5')
    assert.equal(data.errors.length, 1)
    assert.equal(data.api_failures.length, 1)
    assert.equal(data.api_failures[0].status, 500)
    assert.doesNotThrow(() => JSON.stringify(data))
  })

  it('3. 同一条异常连报两次只留一条（Vue errorHandler 与 uni.onError 会各报一次）', async () => {
    clearDiagnostics()
    recordError('同一个异常', 'vue:errorHandler', 'stack')
    recordError('同一个异常', 'uni.onError', 'stack')
    const data = await collectDiagnostics()
    assert.equal(data.errors.length, 1)
  })

  it('4. 接口失败最多保留 20 条，最旧的先丢', async () => {
    clearDiagnostics()
    for (let i = 0; i < 25; i += 1) recordApiFailure('POST', `/api/${i}`, 500, '失败')
    const data = await collectDiagnostics()
    assert.equal(data.api_failures.length, 20)
    assert.equal(data.api_failures[0].url, '/api/5')
  })

  it('5. clearDiagnostics 清空现场，计数归零', () => {
    clearDiagnostics()
    recordError('一条', 'test')
    recordApiFailure('GET', '/x', 404, '未找到')
    assert.equal(diagnosticsCount(), 2)
    clearDiagnostics()
    assert.equal(diagnosticsCount(), 0)
  })

  it('6. 诊断包裁到后端上限以内（后端 32KB 上限，超了整包丢弃）', async () => {
    clearDiagnostics()
    for (let i = 0; i < 50; i += 1) recordError(`很长的异常消息 ${i}`.repeat(20), 'test', 'x'.repeat(800))
    const data = await collectDiagnostics()
    assert.ok(JSON.stringify(data).length <= 24000, `实际 ${JSON.stringify(data).length}`)
  })
})
