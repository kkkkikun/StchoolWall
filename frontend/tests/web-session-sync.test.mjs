import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'
const source = await readFile(new URL('../src/utils/web-session-sync.ts', import.meta.url), 'utf8')
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText
const { createWebSessionSync, withWebRefreshLock } = await import('data:text/javascript;base64,' + Buffer.from(output).toString('base64'))

function pair() {
  const listeners = [[], []]
  const sent = []
  return { sent, channels: [0, 1].map((id) => ({
    addEventListener: (_, listener) => listeners[id].push(listener),
    postMessage(message) {
      sent.push(message)
      for (const listener of listeners[1 - id]) queueMicrotask(() => listener({ data: structuredClone(message) }))
    },
  })) }
}
const session = (token = 'access-1', csrf = 'csrf-current') => ({
  access_token: token, refresh_token: 'must-never-broadcast', csrf_token: csrf,
  session_id: 'session-1', role: 'student', user_info: { id: 'u1', nickname: '学生', is_verified: true },
})
test('another tab receives current access in memory, with no refresh token in channel', async () => {
  const { channels, sent } = pair()
  let received = null
  const first = createWebSessionSync(channels[0], { current: () => session(), csrf: () => 'csrf-current', apply: () => {}, clear: () => {} })
  const second = createWebSessionSync(channels[1], { current: () => received, csrf: () => 'csrf-current', apply: (data) => { received = data }, clear: () => {} })
  await second.request()
  assert.equal(received.access_token, 'access-1')
  assert.ok(sent.filter((message) => message.type === 'session').every((message) => !('refresh_token' in message.data)))
  first.publish(session('rotated-access'))
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.equal(received.access_token, 'rotated-access')
})
test('a late broadcast with the previous CSRF cookie cannot overwrite a newer session', async () => {
  const { channels } = pair()
  let received = null
  const first = createWebSessionSync(channels[0], { current: () => null, csrf: () => 'csrf-old', apply: () => {}, clear: () => {} })
  createWebSessionSync(channels[1], { current: () => null, csrf: () => 'csrf-new', apply: (data) => { received = data }, clear: () => {} })
  first.publish(session('stale-access', 'csrf-old'))
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.equal(received, null)
})
test('logout clears the other tab without rebroadcast or token persistence', async () => {
  const { channels, sent } = pair()
  let clears = 0
  const first = createWebSessionSync(channels[0], { current: () => null, csrf: () => '', apply: () => {}, clear: () => {} })
  createWebSessionSync(channels[1], { current: () => null, csrf: () => '', apply: () => {}, clear: () => { clears++ } })
  first.logout()
  await new Promise((resolve) => setTimeout(resolve, 0))
  assert.equal(clears, 1)
  assert.deepEqual(sent, [{ type: 'logout' }])
})
test('browser without atomic Web Locks fails closed before cookie refresh', async () => {
  let refreshCalls = 0
  await assert.rejects(withWebRefreshLock(null, async () => { refreshCalls++ }), /Web Locks/)
  assert.equal(refreshCalls, 0)
})
test('Web Locks serializes concurrent refresh contenders', async () => {
  let queue = Promise.resolve()
  const locks = { request: (_name, callback) => {
    const result = queue.then(callback); queue = result.catch(() => {}); return result
  } }
  let access = 'old'
  let refreshes = 0
  const refresh = async () => {
    if (access !== 'old') return
    refreshes++
    await new Promise((resolve) => setTimeout(resolve, 5))
    access = 'new'
  }
  await Promise.all([withWebRefreshLock(locks, refresh), withWebRefreshLock(locks, refresh)])
  assert.equal(refreshes, 1)
})
