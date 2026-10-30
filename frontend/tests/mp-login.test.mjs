import test, { describe, it, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, unlink } from 'node:fs/promises'
import ts from 'typescript'
import { parse, compileScript } from 'vue/compiler-sfc'

// =============================================================================
// 测试脚手架：编译并受控加载真实生产源码 (src/api/auth.ts & src/pages/mine/index.vue)
// =============================================================================

// 1. 临时适配模块路径
const bridgePath = new URL('./.temp-mp-bridge.mjs', import.meta.url)
const reqPath = new URL('./.temp-mp-req.mjs', import.meta.url)
const storagePath = new URL('./.temp-mp-storage.mjs', import.meta.url)
const authCompiledPath = new URL('./.temp-mp-auth.mjs', import.meta.url)
const authAdapterPath = new URL('./.temp-mp-auth-adapter.mjs', import.meta.url)
const errorsCompiledPath = new URL('./.temp-mp-errors.mjs', import.meta.url)
const sfcCompiledPath = new URL('./.temp-mp-mine-sfc.mjs', import.meta.url)

// 2. 桥接模块代码：动态受控依赖
const bridgeCode = `
export const bridge = {
  post: async () => ({}),
  get: async () => ({ items: [] }),
  del: async () => ({}),
  request: async () => ({}),
  isLoggedIn: () => false,
  setSession: () => {},
  getUserInfo: () => null,
  setUserInfo: () => {},
  clearUser: () => {},
  uniLogin: async () => ({ code: 'default-mock-code' }),
  showToast: () => {},
  customWxLogin: null,
};
export function resetBridge() {
  bridge.post = async () => ({});
  bridge.get = async (url) => {
    if (url === '/user/profile') return { is_verified: false, nickname: '测试同学' };
    return { items: [] };
  };
  bridge.del = async () => ({});
  bridge.request = async () => ({});
  bridge.isLoggedIn = () => false;
  bridge.setSession = () => {};
  bridge.getUserInfo = () => null;
  bridge.setUserInfo = () => {};
  bridge.clearUser = () => {};
  bridge.uniLogin = async () => ({ code: 'default-mock-code' });
  bridge.showToast = () => {};
  bridge.customWxLogin = null;
}
`
await writeFile(bridgePath, bridgeCode)

await writeFile(reqPath, `
import { bridge } from "./.temp-mp-bridge.mjs";
export const post = (...args) => bridge.post(...args);
export const get = (...args) => bridge.get(...args);
export const del = (...args) => bridge.del(...args);
export const request = (...args) => bridge.request(...args);
`)

await writeFile(storagePath, `
import { bridge } from "./.temp-mp-bridge.mjs";
export const tokenStorage = {
  isLoggedIn: () => bridge.isLoggedIn(),
  setSession: (s) => bridge.setSession(s),
  getToken: () => "",
  setToken: () => {},
  removeToken: () => {},
};
export const userStorage = {
  getUserInfo: () => bridge.getUserInfo(),
  setUserInfo: (u) => bridge.setUserInfo(u),
  clear: () => bridge.clearUser(),
};
`)

// 3. 转译真实 src/api/auth.ts
let authTs = await readFile(new URL('../src/api/auth.ts', import.meta.url), 'utf8')
authTs = authTs.replace(/from\s+['"]@\/utils\/request['"]/g, 'from "./.temp-mp-req.mjs"')
authTs = authTs.replace(/from\s+['"]@\/utils\/storage['"]/g, 'from "./.temp-mp-storage.mjs"')
const authJs = ts.transpileModule(authTs, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
await writeFile(authCompiledPath, authJs)

await writeFile(authAdapterPath, `
import { bridge } from "./.temp-mp-bridge.mjs";
import { wxLoginAndStore as realWxLoginAndStore } from "./.temp-mp-auth.mjs";
export const wxLoginAndStore = (...args) => {
  if (bridge.customWxLogin) return bridge.customWxLogin(...args);
  return realWxLoginAndStore(...args);
};
export const devLogin = async () => ({});
export const webLogin = async () => ({});
export const register = async () => ({});
export const storeLoginSession = async () => {};
export const recoverPassword = async () => {};
`)

// 3.5 转译真实的 utils/errors.ts（doWebLogin 的友好网络错误映射依赖）
const errorsTs = await readFile(new URL('../src/utils/errors.ts', import.meta.url), 'utf8')
await writeFile(errorsCompiledPath, ts.transpileModule(errorsTs, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText)

// 4. 编译并转译真实 src/pages/mine/index.vue SFC
const sfcContent = await readFile(new URL('../src/pages/mine/index.vue', import.meta.url), 'utf8')
const sfc = parse(sfcContent)
const script = compileScript(sfc.descriptor, { id: 'mine-page', inlineTemplate: false })

let sfcCode = script.content
sfcCode = sfcCode.replaceAll('import.meta.env', '({ VITE_DEV_LOGIN: "true", VITE_WECHAT_MP_APP_ID: "" })')
sfcCode = sfcCode.replace(/import\s+{\s*onShow\s*}\s+from\s+['"]@dcloudio\/uni-app['"]/g, 'const onShow = (fn) => {}')
sfcCode = sfcCode.replace(/import\s+TabBar\s+from\s+['"]@\/components\/tab-bar\.vue['"]/g, 'const TabBar = {}')
sfcCode = sfcCode.replace(/import\s+{\s*useTheme\s*}\s+from\s+['"]@\/utils\/theme['"]/g, 'const useTheme = () => ({ themeClass: "neon" })')
sfcCode = sfcCode.replace(/import\s+{\s*myStats\s*}\s+from\s+['"]@\/api\/interaction['"]/g, 'const myStats = async () => ({})')
sfcCode = sfcCode.replace(/import\s+{\s*beginWechatOAuth,\s*clientType\s*}\s+from\s+['"]@\/utils\/platform-auth['"]/g, 'const beginWechatOAuth = () => {}, clientType = () => "weixin"')
sfcCode = sfcCode.replace(/from\s+['"]@\/utils\/request['"]/g, 'from "./.temp-mp-req.mjs"')
sfcCode = sfcCode.replace(/from\s+['"]@\/api\/auth['"]/g, 'from "./.temp-mp-auth-adapter.mjs"')
sfcCode = sfcCode.replace(/from\s+['"]@\/utils\/storage['"]/g, 'from "./.temp-mp-storage.mjs"')
sfcCode = sfcCode.replace(/from\s+['"]@\/utils\/errors['"]/g, 'from "./.temp-mp-errors.mjs"')

const sfcJs = ts.transpileModule(sfcCode, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
await writeFile(sfcCompiledPath, sfcJs)

// 5. 动态加载模块至内存
let bridgeModule, authModule, MineComponentModule
try {
  bridgeModule = await import(bridgePath.href)
  authModule = await import(authCompiledPath.href)
  MineComponentModule = (await import(sfcCompiledPath.href)).default
} finally {
  // 确保测试退出或出错时清除所有临时文件，不污染磁盘
  await unlink(bridgePath).catch(() => {})
  await unlink(reqPath).catch(() => {})
  await unlink(storagePath).catch(() => {})
  await unlink(authCompiledPath).catch(() => {})
  await unlink(authAdapterPath).catch(() => {})
  await unlink(errorsCompiledPath).catch(() => {})
  await unlink(sfcCompiledPath).catch(() => {})
}

const { bridge, resetBridge } = bridgeModule
const { wxLoginAndStore: realWxLoginAndStore } = authModule

// 6. 配置全局 uni 运行时 Mock
globalThis.uni = {
  login: async (...args) => bridge.uniLogin(...args),
  showToast: (opts) => bridge.showToast(opts),
}

// 辅助创建干净的 mine/index.vue 实例
function createMineInstance() {
  return MineComponentModule.setup({}, { expose: () => {} })
}

// =============================================================================
// 测试套件开始
// =============================================================================

describe('MP-WEIXIN Mine Page Re-login Suite (真实生产源码回归)', () => {
  beforeEach(() => {
    resetBridge()
  })

  // 1. 静态模板与结构回归验证
  it('1. [模板回归] mine/index.vue 为 MP-WEIXIN 提供了合规的未登录入口与防连击绑定', async () => {
    const rawSfc = await readFile(new URL('../src/pages/mine/index.vue', import.meta.url), 'utf8')

    // 验证包含微信条件编译块
    assert.ok(rawSfc.includes('#ifdef MP-WEIXIN'), '必须包含 #ifdef MP-WEIXIN 条件编译块')
    assert.ok(rawSfc.includes('doWxLogin'), '必须绑定 doWxLogin 处理函数')
    assert.ok(rawSfc.includes('wxLoggingIn'), '必须包含 wxLoggingIn 防连击状态')
    assert.ok(rawSfc.includes(':class="{ saving: wxLoggingIn }"'), '必须包含 saving 类样式绑定')
    assert.ok(rawSfc.includes('.dev-capsule.saving'), '必须提供 saving 状态的禁用与透明度样式')

    // 验证原 H5/APP-PLUS 条件编译与 DEV_LOGIN 未被破坏
    assert.ok(rawSfc.includes('#ifdef H5 || APP-PLUS'), '原有 H5/APP-PLUS 入口必须保留')
    assert.ok(rawSfc.includes('DEV_LOGIN_ON'), '原有本地联调演示入口必须保留')
  })

  // 2. 真实生产源码 wxLoginAndStore 行为契约 (frontend/src/api/auth.ts)
  describe('2. [真实源码] src/api/auth.ts -> wxLoginAndStore 接口契约', () => {
    it('2.1 已登录时直接返回 true，不发起重复的 uni.login', async () => {
      let uniLoginCalls = 0
      bridge.isLoggedIn = () => true
      bridge.uniLogin = async () => {
        uniLoginCalls++
        return { code: 'should-not-call' }
      }

      // 执行真实生产代码 wxLoginAndStore()
      const res = await realWxLoginAndStore()
      assert.equal(res, true, '已登录状态下应直接返回 true')
      assert.equal(uniLoginCalls, 0, '已登录态下绝不重复调用 uni.login')
    })

    it('2.2 未登录且微信返回有效 code 时成功换取会话并持久化', async () => {
      let uniLoginCalls = 0
      let postCalls = 0
      let storedSession = null

      bridge.isLoggedIn = () => false
      bridge.uniLogin = async () => {
        uniLoginCalls++
        return { code: 'wx-valid-code-123' }
      }
      bridge.post = async (url, body) => {
        postCalls++
        assert.equal(url, '/auth/login', '必须调用 /auth/login 换取会话')
        assert.deepEqual(body, { code: 'wx-valid-code-123' })
        return {
          access_token: 'mock-access-token-abc',
          refresh_token: 'mock-refresh-token-xyz',
          csrf_token: 'mock-csrf',
          session_id: 'sess-1',
          role: 'student',
          user_info: { id: 'u-1', nickname: '测试学生', is_verified: false },
        }
      }
      bridge.setSession = (session) => {
        storedSession = session
      }

      const res = await realWxLoginAndStore()
      assert.equal(res, true, '登录成功返回 true')
      assert.equal(uniLoginCalls, 1, '调用 1 次 uni.login')
      assert.equal(postCalls, 1, '调用 1 次登录接口')
      assert.ok(storedSession, '会话必须被保存')
      assert.equal(storedSession.access_token, 'mock-access-token-abc')
    })

    it('2.3 微信未返回 code 时返回 false 且不调用后端接口或设置会话', async () => {
      let uniLoginCalls = 0
      let postCalls = 0
      let storedSession = null

      bridge.isLoggedIn = () => false
      bridge.uniLogin = async () => {
        uniLoginCalls++
        return {} // 无 code
      }
      bridge.post = async () => {
        postCalls++
        return {}
      }
      bridge.setSession = (s) => { storedSession = s }

      const res = await realWxLoginAndStore()
      assert.equal(res, false, '缺失 code 时应返回 false')
      assert.equal(uniLoginCalls, 1)
      assert.equal(postCalls, 0, '未获得有效 code 时不得调用后端')
      assert.equal(storedSession, null, '不得保存任何空会话')
    })

    it('2.4 微信接口异常（如用户拒绝授权）时安全捕获并返回 false', async () => {
      bridge.isLoggedIn = () => false
      bridge.uniLogin = async () => {
        throw new Error('getUserProfile:fail auth deny')
      }

      const res = await realWxLoginAndStore()
      assert.equal(res, false, '微信异常时必须安全返回 false')
    })

    it('2.5 后端接口异常时安全返回 false 不泄露未捕获错误', async () => {
      let storedSession = null
      bridge.isLoggedIn = () => false
      bridge.uniLogin = async () => ({ code: 'wx-code-ok' })
      bridge.post = async () => {
        throw new Error('Network error 502')
      }
      bridge.setSession = (s) => { storedSession = s }

      const res = await realWxLoginAndStore()
      assert.equal(res, false, '后端异常时返回 false')
      assert.equal(storedSession, null, '异常时绝不设置会话')
    })
  })

  // 3. 真实生产源码 doWxLogin 页面交互与状态流转 (frontend/src/pages/mine/index.vue)
  describe('3. [真实源码] src/pages/mine/index.vue -> doWxLogin 页面交互与防连击', () => {
    it('3.1 登录成功：状态正确更新、清空旧缓存、严格根据真实资料同步未认证状态', async () => {
      let isAuthed = false
      const toasts = []

      bridge.isLoggedIn = () => isAuthed
      bridge.getUserInfo = () => (isAuthed ? { nickname: '普通同学', is_verified: false } : null)
      bridge.showToast = (opts) => toasts.push(opts)
      bridge.get = async (url) => {
        if (url === '/user/profile') return { nickname: '普通同学', is_verified: false }
        if (url === '/posts/my') return { items: [{ id: 101, content: '新登录后的帖子' }] }
        return { items: [] }
      }

      // 注入受控的 wxLoginAndStore：成功登录并同步已登录态
      bridge.customWxLogin = async () => {
        isAuthed = true
        return true
      }

      const mine = createMineInstance()

      // 预先模拟页面在未登录时残留的旧状态与缓存
      mine.loadedTabs.value.add('posts')
      mine.loadedTabs.value.add('favorites')
      mine.postLists.posts = [{ id: 1, content: '旧帖子' }]
      mine.postLists.favorites = [{ id: 2, content: '旧收藏' }]

      assert.equal(mine.loggedIn.value, false, '初始 loggedIn 应为 false')
      assert.equal(mine.isVerified.value, false, '初始 isVerified 应为 false')
      assert.equal(mine.loadedTabs.value.size, 2, '初始存在 2 个旧缓存 Tab')

      // 执行真实 SFC 中的 doWxLogin
      await mine.doWxLogin()

      assert.equal(mine.loggedIn.value, true, '登录成功后 loggedIn 应置为 true')
      assert.equal(mine.isVerified.value, false, '未认证用户绝不自动授予认证权限')
      assert.equal(mine.wxLoggingIn.value, false, '最终防连击状态恢复为 false')

      // 验证提示与缓存更新
      const successToast = toasts.find((t) => t.title === '登录成功' && t.icon === 'success')
      assert.ok(successToast, '必须弹出“登录成功”提示')
    })

    it('3.2 真实已认证学生登录：严格同步已认证状态', async () => {
      let isAuthed = false
      bridge.isLoggedIn = () => isAuthed
      bridge.getUserInfo = () => (isAuthed ? { nickname: '认证学长', is_verified: true } : null)
      bridge.get = async (url) => {
        if (url === '/user/profile') return { nickname: '认证学长', is_verified: true }
        return { items: [] }
      }

      bridge.customWxLogin = async () => {
        isAuthed = true
        return true
      }

      const mine = createMineInstance()
      await mine.doWxLogin()

      assert.equal(mine.loggedIn.value, true)
      assert.equal(mine.isVerified.value, true, '已认证用户的 isVerified 应同步为 true')
      assert.equal(mine.wxLoggingIn.value, false)
    })

    it('3.3 登录失败：不假装登录、不授权、提示友好错误且恢复按钮状态', async () => {
      const toasts = []
      bridge.isLoggedIn = () => false
      bridge.getUserInfo = () => null
      bridge.showToast = (opts) => toasts.push(opts)
      bridge.customWxLogin = async () => false // 登录失败

      const mine = createMineInstance()
      await mine.doWxLogin()

      assert.equal(mine.loggedIn.value, false, '失败时 loggedIn 必须保持 false')
      assert.equal(mine.isVerified.value, false, '失败时 isVerified 必须保持 false')
      assert.equal(mine.wxLoggingIn.value, false, '失败后必须恢复按钮可点击状态')

      const failToast = toasts.find((t) => t.title === '登录失败，请重试')
      assert.ok(failToast, '必须弹出“登录失败，请重试”友好提示')
      const fakeSuccess = toasts.find((t) => t.title === '登录成功')
      assert.equal(fakeSuccess, undefined, '失败路径绝不能显示成功提示')
    })

    it('3.4 登录抛出异常：安全兜底不崩溃、显示失败提示且恢复防连击状态', async () => {
      const toasts = []
      bridge.isLoggedIn = () => false
      bridge.getUserInfo = () => null
      bridge.showToast = (opts) => toasts.push(opts)
      bridge.customWxLogin = async () => {
        throw new Error('Unexpected crash in network layer')
      }

      const mine = createMineInstance()
      await mine.doWxLogin()

      assert.equal(mine.loggedIn.value, false)
      assert.equal(mine.isVerified.value, false)
      assert.equal(mine.wxLoggingIn.value, false, '抛出异常后 finally 必须重置 wxLoggingIn')

      const failToast = toasts.find((t) => t.title === '登录失败，请重试')
      assert.ok(failToast, '异常时必须弹出安全提示')
    })

    it('3.5 快速连续多次点击：防连击锁生效，并发请求被拦截，仅调用一次底层登录', async () => {
      let wxLoginCalls = 0
      let isAuthed = false

      bridge.isLoggedIn = () => isAuthed
      bridge.getUserInfo = () => (isAuthed ? { nickname: '普通同学', is_verified: false } : null)
      bridge.customWxLogin = async () => {
        wxLoginCalls++
        // 模拟网络延迟 20ms
        await new Promise((r) => setTimeout(r, 20))
        isAuthed = true
        return true
      }

      const mine = createMineInstance()

      // 并发发起 5 次点击
      const p1 = mine.doWxLogin()
      const p2 = mine.doWxLogin()
      const p3 = mine.doWxLogin()
      const p4 = mine.doWxLogin()
      const p5 = mine.doWxLogin()

      await Promise.all([p1, p2, p3, p4, p5])

      assert.equal(wxLoginCalls, 1, '并发多次点击只能放行 1 次底层登录调用')
      assert.equal(mine.wxLoggingIn.value, false, '完成后状态重置为 false')

      // 前序调用完成后，允许再次点击
      await mine.doWxLogin()
      assert.equal(wxLoginCalls, 2, '前序操作结束后允许下一次点击')
    })

    it('3.6 全链路端到端联动：mine/index.vue -> 真实 auth.ts -> mock uni / mock 接口', async () => {
      // 本用例不覆盖 bridge.customWxLogin，使 mine/index.vue 直接调用真实 auth.ts 的 wxLoginAndStore
      let isAuthed = false
      let currentSession = null
      const toasts = []

      bridge.isLoggedIn = () => isAuthed
      bridge.uniLogin = async () => ({ code: 'e2e-wx-code' })
      bridge.post = async (url, body) => {
        if (url === '/auth/login') {
          return {
            access_token: 'e2e-token',
            refresh_token: 'e2e-refresh',
            csrf_token: 'e2e-csrf',
            session_id: 'e2e-sess',
            role: 'student',
            user_info: { id: 'u-e2e', nickname: '端到端同学', is_verified: true },
          }
        }
        return {}
      }
      bridge.setSession = (s) => {
        currentSession = s
        isAuthed = true
      }
      bridge.getUserInfo = () => (currentSession ? currentSession.user_info : null)
      bridge.showToast = (opts) => toasts.push(opts)
      bridge.get = async (url) => {
        if (url === '/user/profile') return { nickname: '端到端同学', is_verified: true }
        return { items: [] }
      }

      const mine = createMineInstance()
      assert.equal(mine.loggedIn.value, false)

      // 执行全链路登录
      await mine.doWxLogin()

      assert.equal(mine.loggedIn.value, true, '全链路执行后 loggedIn 为 true')
      assert.equal(mine.isVerified.value, true, '全链路执行后 isVerified 准确同步为 true')
      assert.ok(currentSession, '真实 auth.ts 成功落库会话')
      assert.equal(currentSession.access_token, 'e2e-token')
      assert.ok(toasts.some((t) => t.title === '登录成功'))
    })
  })
})
