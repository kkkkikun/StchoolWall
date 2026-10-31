import { describe, it, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { register } from 'node:module'
import { pathToFileURL } from 'node:url'
import path from 'node:path'

// 1. 设置 Node 环境下的浏览器全局对象 Mock
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
    if (!val) {
      cookieStore.clear()
      return
    }
    const [pair] = val.split(';')
    const eqIdx = pair.indexOf('=')
    if (eqIdx !== -1) {
      const key = pair.slice(0, eqIdx).trim()
      const value = pair.slice(eqIdx + 1).trim()
      if (val.includes('Max-Age=0') || !value) {
        cookieStore.delete(key)
      } else {
        cookieStore.set(key, value)
      }
    }
  },
  configurable: true,
})

let assignedLocations = []
globalThis.location = {
  pathname: '/dashboard',
  assign: (url) => {
    assignedLocations.push(url)
    globalThis.location.pathname = url
  },
}
globalThis.window = {
  location: globalThis.location,
  addEventListener: noop,
  removeEventListener: noop,
  navigator: { userAgent: 'Mozilla/5.0 Node.js' },
}

// Mock Element Plus UI Message
import { ElMessage } from 'element-plus'
let messageLogs = []
ElMessage.error = (msg) => { messageLogs.push({ type: 'error', message: msg }) }
ElMessage.success = (msg) => { messageLogs.push({ type: 'success', message: msg }) }
ElMessage.warning = (msg) => { messageLogs.push({ type: 'warning', message: msg }) }
ElMessage.info = (msg) => { messageLogs.push({ type: 'info', message: msg }) }

// 2. 注册 ESM 解析 hook，支持 '@/...' 别名与自动补全 .ts
const aliasLoader = `
import { pathToFileURL } from "node:url";
import path from "node:path";
import fs from "node:fs";

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("@/")) {
    const sub = specifier.slice(2);
    let resolved = path.resolve(process.cwd(), "src", sub);
    if (!fs.existsSync(resolved) && !fs.existsSync(resolved + ".ts")) {
      resolved = path.resolve(process.cwd(), "admin-frontend/src", sub);
    }
    if (!fs.existsSync(resolved)) {
      if (fs.existsSync(resolved + ".ts")) resolved = resolved + ".ts";
      else if (fs.existsSync(resolved + ".js")) resolved = resolved + ".js";
    }
    return nextResolve(pathToFileURL(resolved).href, context);
  }
  return nextResolve(specifier, context);
}
`
register('data:text/javascript,' + encodeURIComponent(aliasLoader), import.meta.url)

// 3. 动态导入源码模块
const { default: request, getToken, setToken, clearToken } = await import('../src/utils/request.ts')
const { evidenceBlob } = await import('../src/api/verification.ts')
const postsApi = await import('../src/api/posts.ts')
const usersApi = await import('../src/api/users.ts')
const { exportPosts, exportPostsUrl } = postsApi
const { exportUsers, exportUsersUrl } = usersApi

describe('Admin File Downloads & Authentication Suite', { concurrency: false }, () => {
  let interceptedRequests = []

  beforeEach(() => {
    interceptedRequests = []
    assignedLocations = []
    messageLogs = []
    cookieStore.clear()
    clearToken()
    globalThis.location.pathname = '/dashboard'

    // 配置 Axios Adapter 拦截请求
    request.defaults.adapter = async (config) => {
      interceptedRequests.push(config)

      // 模拟 401
      if (config.headers?.['X-Simulate-401']) {
        const error = new Error('Request failed with status code 401')
        error.response = { status: 401, data: { detail: 'Unauthorized' } }
        throw error
      }
      // 模拟 403
      if (config.headers?.['X-Simulate-403']) {
        const error = new Error('Request failed with status code 403')
        error.response = { status: 403, data: { detail: 'Forbidden' } }
        throw error
      }

      // 默认返回模拟 Blob
      const isCsv = config.url?.includes('export')
      const mime = isCsv ? 'text/csv' : 'image/jpeg'
      const content = isCsv ? 'id,title,status\n1,mock-post,1\n' : 'mock-jpeg-binary-data'
      const blob = new Blob([content], { type: mime })

      return {
        data: blob,
        status: 200,
        statusText: 'OK',
        headers: { 'content-type': mime },
        config,
      }
    }
  })

  // ==================== 1. 缺陷复现（红测） ====================

  it('1. [红测复现] 原生 fetch 导出逻辑在 Cookie 会话下发送了非法的 Bearer __cookie_session__', async () => {
    // 模拟刷新后场景：内存无 token，但浏览器有合法的 CSRF Cookie
    clearToken()
    globalThis.document.cookie = 'sw_admin_csrf=valid-csrf-token'
    assert.equal(getToken(), '__cookie_session__', '刷新后内存无 token 时 getToken() 应返回 __cookie_session__ 哨兵值')

    let fetchCalledWith = null
    globalThis.fetch = async (url, options) => {
      fetchCalledWith = { url, options }
      // 模拟后端真实逻辑：若 Authorization 是非法 Bearer __cookie_session__，抛 401
      if (options?.headers?.Authorization === 'Bearer __cookie_session__') {
        return { ok: false, status: 401, statusText: 'Unauthorized' }
      }
      return { ok: true, status: 200, blob: async () => new Blob(['ok'], { type: 'text/csv' }) }
    }

    // 执行原有 PostsView/UsersView 里的原生 fetch 逻辑
    const legacyUrl = exportPostsUrl(1, 'keyword')
    const response = await fetch(legacyUrl, { headers: { Authorization: `Bearer ${getToken()}` } })

    // 断言：在原生 fetch 下，Authorization 确实被错误注入为 'Bearer __cookie_session__' 并导致 401
    assert.equal(fetchCalledWith?.options?.headers?.Authorization, 'Bearer __cookie_session__')
    assert.equal(response.status, 401, '后端因非法 Bearer 拒绝请求')
  })

  // ==================== 2. 绿测场景验证 ====================

  it('2. [绿测] 刷新后 Cookie 会话：evidenceBlob 不注入伪 Token，正确携带 CSRF 与 withCredentials', async () => {
    clearToken()
    globalThis.document.cookie = 'sw_admin_csrf=session-csrf-123'
    assert.equal(getToken(), '__cookie_session__')

    const blob = await evidenceBlob('rec-test-001')
    assert.ok(blob instanceof Blob, '应正常返回 Blob 实例')
    assert.equal(interceptedRequests.length, 1)

    const req = interceptedRequests[0]
    // 路径检查（避免 /api/v1/api/v1 重复）
    assert.equal(req.url, '/admin/student-verifications/rec-test-001/evidence')
    assert.equal(req.baseURL, '/api/v1')
    // 认证头检查：绝对不能有 Bearer __cookie_session__
    assert.equal(req.headers?.Authorization, undefined, 'Cookie 模式下不得发送 Authorization 头')
    assert.equal(req.headers?.['X-CSRF-Token'], 'session-csrf-123', '必须携带 X-CSRF-Token')
    assert.equal(req.withCredentials, true, '必须开启 withCredentials 携带 Cookie')
    assert.equal(req.responseType, 'blob', '必须以 blob 二进制接收')
    assert.equal(req.headers?.['Cache-Control'], 'no-store', '必须遵守 no-store 缓存限制')
  })

  it('3. [绿测] 刷新后 Cookie 会话：exportPosts 不注入伪 Token，正确携带参数且路径无重复', async () => {
    clearToken()
    globalThis.document.cookie = 'sw_admin_csrf=session-csrf-posts'

    const blob = await exportPosts(1, '校园通知')
    assert.ok(blob instanceof Blob)
    assert.equal(interceptedRequests.length, 1)

    const req = interceptedRequests[0]
    assert.equal(req.url, '/admin/export/posts', '路径不得含重复的 /api/v1')
    assert.equal(req.baseURL, '/api/v1')
    assert.equal(req.headers?.Authorization, undefined, '不得发送伪 Bearer 头')
    assert.equal(req.headers?.['X-CSRF-Token'], 'session-csrf-posts')
    assert.equal(req.withCredentials, true)
    assert.equal(req.responseType, 'blob')
    assert.deepEqual(req.params, { status: 1, q: '校园通知' }, '正确传递筛选参数')
  })

  it('4. [绿测] 刷新后 Cookie 会话：exportUsers 不注入伪 Token，正确请求用户导出端点', async () => {
    clearToken()
    globalThis.document.cookie = 'sw_admin_csrf=session-csrf-users'

    const blob = await exportUsers()
    assert.ok(blob instanceof Blob)
    assert.equal(interceptedRequests.length, 1)

    const req = interceptedRequests[0]
    assert.equal(req.url, '/admin/export/users', '路径不得含重复的 /api/v1')
    assert.equal(req.headers?.Authorization, undefined)
    assert.equal(req.headers?.['X-CSRF-Token'], 'session-csrf-users')
    assert.equal(req.withCredentials, true)
    assert.equal(req.responseType, 'blob')
  })

  it('5. [绿测] 有效内存 Bearer 会话：正常携带真实的 Bearer JWT Token', async () => {
    const REAL_JWT = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.valid-admin-token'
    setToken(REAL_JWT)
    globalThis.document.cookie = 'sw_admin_csrf=bearer-csrf'

    await exportPosts()
    assert.equal(interceptedRequests.length, 1)
    const req = interceptedRequests[0]

    assert.equal(req.headers?.Authorization, `Bearer ${REAL_JWT}`, '有真实 Token 时必须携带 Bearer 头')
    assert.equal(req.headers?.['X-CSRF-Token'], 'bearer-csrf')
  })

  it('6. [绿测] 无登录态场景：不发送 Authorization 头与 CSRF 头', async () => {
    clearToken()
    globalThis.document.cookie = ''
    assert.equal(getToken(), '')

    await exportUsers()
    assert.equal(interceptedRequests.length, 1)
    const req = interceptedRequests[0]

    assert.equal(req.headers?.Authorization, undefined)
    assert.equal(req.headers?.['X-CSRF-Token'], undefined)
    assert.equal(req.withCredentials, true)
  })

  it('7. [绿测] 403 权限不足响应处理（MFA 未启用或角色不足）', async () => {
    clearToken()
    globalThis.document.cookie = 'sw_admin_csrf=csrf-test'

    // 配置拦截器注入 403 测试标头
    request.defaults.adapter = async (config) => {
      const error = new Error('Forbidden')
      error.response = { status: 403, data: { detail: '需要多因素认证' } }
      throw error
    }

    await assert.rejects(
      async () => {
        await evidenceBlob('rec-no-mfa')
      },
      (err) => {
        assert.equal(err.message, '需要有效管理员权限与多因素认证')
        return true
      }
    )
  })

  it('8. [绿测] 二进制数据响应完整性：正确接收 Blob 数据', async () => {
    clearToken()
    globalThis.document.cookie = 'sw_admin_csrf=csrf-test'

    const blob = await exportPosts()
    assert.equal(blob.type, 'text/csv')
    const text = await blob.text()
    assert.ok(text.includes('id,title,status'), '导出的 CSV 内容应完整保留')
  })

  // ==================== 3. 401 会话失效回归验证 ====================

  it('9. [401 会话失效] Cookie 会话导出时后端返回 401：触发清理状态、登录跳转，且绝不返回虚假 Blob', async () => {
    clearToken()
    globalThis.document.cookie = 'sw_admin_csrf=session-csrf-401'
    assert.equal(getToken(), '__cookie_session__')
    globalThis.location.pathname = '/posts'

    // 配置 adapter 返回 401
    request.defaults.adapter = async (config) => {
      interceptedRequests.push(config)
      const error = new Error('Request failed with status code 401')
      error.response = { status: 401, data: { detail: 'Session expired' } }
      throw error
    }

    // 执行导出，断言必须 reject，调用方不能拿到 Blob
    await assert.rejects(
      async () => {
        await exportPosts(1, 'keyword')
      },
      (err) => {
        assert.equal(err.response?.status, 401)
        return true
      }
    )

    // 1) 登录状态被清理
    assert.equal(getToken(), '', '401 后 getToken() 应恢复为空字符串')
    assert.equal(globalThis.document.cookie, '', '401 后 sw_admin_csrf Cookie 应被清理')

    // 2) 页面重定向至登录页
    assert.equal(assignedLocations.length, 1, '必须触发 location.assign 跳转')
    assert.equal(assignedLocations[0], '/login', '跳转目标必须为登录页')
    assert.equal(globalThis.location.pathname, '/login')

    // 3) 触发统一的会话失效错误提示
    const errNotice = messageLogs.find((m) => m.type === 'error' && m.message.includes('登录已失效'))
    assert.ok(errNotice, '必须提示“登录已失效，请重新登录”')
  })

  it('10. [401 会话失效] evidenceBlob 收到 401 响应时保持明确的会话失效语义，不误报为无法读取照片', async () => {
    clearToken()
    globalThis.document.cookie = 'sw_admin_csrf=session-csrf-evidence-401'
    globalThis.location.pathname = '/student-verifications'

    request.defaults.adapter = async (config) => {
      interceptedRequests.push(config)
      const error = new Error('Request failed with status code 401')
      error.response = { status: 401, data: { detail: 'Unauthorized' } }
      throw error
    }

    // 断言 evidenceBlob 必须抛出语义清晰的会话失效错误，而不是“无法读取照片或已过保留期”
    await assert.rejects(
      async () => {
        await evidenceBlob('rec-expired-001')
      },
      (err) => {
        // 关键断言：会话失效不能被误掩盖为文件不存在
        assert.notEqual(err.message, '无法读取照片或已过保留期', '401 不得误报为照片不存在或过期')
        assert.equal(err.message, '登录已失效，请重新登录', '401 必须保持明确的会话失效语义')
        return true
      }
    )

    // 确认状态已清理并跳转登录
    assert.equal(getToken(), '')
    assert.equal(assignedLocations.includes('/login'), true)
  })

  it('11. [401 会话失效] 已经在登录页时收到 401：清理状态且不触发重复重定向', async () => {
    clearToken()
    globalThis.document.cookie = 'sw_admin_csrf=some-csrf'
    globalThis.location.pathname = '/login'

    request.defaults.adapter = async (config) => {
      interceptedRequests.push(config)
      const error = new Error('Request failed with status code 401')
      error.response = { status: 401, data: { detail: 'Unauthorized' } }
      throw error
    }

    await assert.rejects(async () => {
      await exportUsers()
    })

    // 登录页收到 401，不应再调用 assign 重复导航造成死循环
    assert.equal(assignedLocations.length, 0, '登录页自身 401 不得再次触发 assign 跳转')
    assert.equal(getToken(), '')
  })

  it('12. [错误边界] evidenceBlob 收到 404/500 等业务异常：保留原有照片读取失败提示', async () => {
    clearToken()
    globalThis.document.cookie = 'sw_admin_csrf=valid-csrf'

    request.defaults.adapter = async (config) => {
      interceptedRequests.push(config)
      const error = new Error('Not Found')
      error.response = { status: 404, data: { detail: 'Evidence not found' } }
      throw error
    }

    await assert.rejects(
      async () => {
        await evidenceBlob('rec-not-found')
      },
      (err) => {
        assert.equal(err.message, '无法读取照片或已过保留期')
        return true
      }
    )
    // 404 不属于会话失效，不应触发重定向
    assert.equal(assignedLocations.length, 0)
    assert.equal(getToken(), '__cookie_session__')
  })
})
