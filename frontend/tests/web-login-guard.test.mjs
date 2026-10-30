import test, { describe, it, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, unlink } from 'node:fs/promises'
import ts from 'typescript'
import { parse, compileScript } from 'vue/compiler-sfc'

// =============================================================================
// H5 网页登录弹窗防重复提交专项回归（真实生产源码 src/pages/mine/index.vue）
// 脚手架与 mp-login.test.mjs 一致：编译真实 SFC，用 bridge 受控依赖。
// =============================================================================

const bridgePath = new URL('./.temp-wlg-bridge.mjs', import.meta.url)
const reqPath = new URL('./.temp-wlg-req.mjs', import.meta.url)
const storagePath = new URL('./.temp-wlg-storage.mjs', import.meta.url)
const authAdapterPath = new URL('./.temp-wlg-auth-adapter.mjs', import.meta.url)
const errorsCompiledPath = new URL('./.temp-wlg-errors.mjs', import.meta.url)
const sfcCompiledPath = new URL('./.temp-wlg-mine-sfc.mjs', import.meta.url)

const loginOk = { access_token: 'mock-access-token', role: 'student', user_info: { id: 'u-test-01', is_verified: true, nickname: '测试同学' } }

const bridgeCode = `
export const bridge = {
  post: async () => ({}),
  get: async (url) => url === '/user/profile' ? { is_verified: true, nickname: '测试同学' } : { items: [] },
  del: async () => ({}),
  request: async () => ({}),
  isLoggedIn: () => false,
  setSession: () => {},
  getUserInfo: () => null,
  setUserInfo: () => {},
  clearUser: () => {},
  showToast: () => {},
  webLogin: async () => (${JSON.stringify(loginOk)}),
  register: async () => (${JSON.stringify(loginOk)}),
  recoverPassword: async () => ({}),
  storeLoginSession: async () => {},
};
export function resetBridge() {
  bridge.post = async () => ({});
  bridge.get = async (url) => url === '/user/profile' ? { is_verified: true, nickname: '测试同学' } : { items: [] };
  bridge.del = async () => ({});
  bridge.request = async () => ({});
  bridge.isLoggedIn = () => false;
  bridge.setSession = () => {};
  bridge.getUserInfo = () => null;
  bridge.setUserInfo = () => {};
  bridge.clearUser = () => {};
  bridge.showToast = () => {};
  bridge.webLogin = async () => (${JSON.stringify(loginOk)});
  bridge.register = async () => (${JSON.stringify(loginOk)});
  bridge.recoverPassword = async () => ({});
  bridge.storeLoginSession = async () => {};
}
`
await writeFile(bridgePath, bridgeCode)

await writeFile(reqPath, `
import { bridge } from "./.temp-wlg-bridge.mjs";
export const post = (...args) => bridge.post(...args);
export const get = (...args) => bridge.get(...args);
export const del = (...args) => bridge.del(...args);
export const request = (...args) => bridge.request(...args);
`)

await writeFile(storagePath, `
import { bridge } from "./.temp-wlg-bridge.mjs";
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

// 认证 API 适配层：全部委托 bridge，测试可逐一替换为受控实现
await writeFile(authAdapterPath, `
import { bridge } from "./.temp-wlg-bridge.mjs";
export const devLogin = async () => ({});
export const webLogin = (...args) => bridge.webLogin(...args);
export const register = (...args) => bridge.register(...args);
export const storeLoginSession = (...args) => bridge.storeLoginSession(...args);
export const recoverPassword = (...args) => bridge.recoverPassword(...args);
export const wxLoginAndStore = async () => true;
`)

// 转译真实的 utils/errors.ts（零依赖纯函数，直接以真实源码参与 SFC 测试）
const errorsTs = await readFile(new URL('../src/utils/errors.ts', import.meta.url), 'utf8')
await writeFile(errorsCompiledPath, ts.transpileModule(errorsTs, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText)

// 编译并转译真实 src/pages/mine/index.vue SFC
const sfcContent = await readFile(new URL('../src/pages/mine/index.vue', import.meta.url), 'utf8')
const sfc = parse(sfcContent)
const script = compileScript(sfc.descriptor, { id: 'mine-page', inlineTemplate: false })

let sfcCode = script.content
sfcCode = sfcCode.replaceAll('import.meta.env', '({ VITE_DEV_LOGIN: "true", VITE_WECHAT_MP_APP_ID: "" })')
sfcCode = sfcCode.replace(/import\s+{\s*onShow\s*}\s+from\s+['"]@dcloudio\/uni-app['"]/g, 'const onShow = (fn) => {}')
sfcCode = sfcCode.replace(/import\s+TabBar\s+from\s+['"]@\/components\/tab-bar\.vue['"]/g, 'const TabBar = {}')
sfcCode = sfcCode.replace(/import\s+{\s*useTheme\s*}\s+from\s+['"]@\/utils\/theme['"]/g, 'const useTheme = () => ({ themeClass: "neon" })')
sfcCode = sfcCode.replace(/import\s+{\s*myStats\s*}\s+from\s+['"]@\/api\/interaction['"]/g, 'const myStats = async () => ({})')
sfcCode = sfcCode.replace(/import\s+{\s*beginWechatOAuth,\s*clientType\s*}\s+from\s+['"]@\/utils\/platform-auth['"]/g, 'const beginWechatOAuth = () => {}, clientType = () => "web"')
sfcCode = sfcCode.replace(/from\s+['"]@\/utils\/request['"]/g, 'from "./.temp-wlg-req.mjs"')
sfcCode = sfcCode.replace(/from\s+['"]@\/api\/auth['"]/g, 'from "./.temp-wlg-auth-adapter.mjs"')
sfcCode = sfcCode.replace(/from\s+['"]@\/utils\/storage['"]/g, 'from "./.temp-wlg-storage.mjs"')
sfcCode = sfcCode.replace(/from\s+['"]@\/utils\/errors['"]/g, 'from "./.temp-wlg-errors.mjs"')

const sfcJs = ts.transpileModule(sfcCode, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
await writeFile(sfcCompiledPath, sfcJs)

let bridgeModule, MineComponentModule
try {
  bridgeModule = await import(bridgePath.href)
  MineComponentModule = (await import(sfcCompiledPath.href)).default
} finally {
  await unlink(bridgePath).catch(() => {})
  await unlink(reqPath).catch(() => {})
  await unlink(storagePath).catch(() => {})
  await unlink(authAdapterPath).catch(() => {})
  await unlink(errorsCompiledPath).catch(() => {})
  await unlink(sfcCompiledPath).catch(() => {})
}

const { bridge, resetBridge } = bridgeModule

globalThis.uni = {
  login: async () => ({ code: 'unused' }),
  showToast: (opts) => bridge.showToast(opts),
}

function createMineInstance() {
  return MineComponentModule.setup({}, { expose: () => {} })
}

// 可手动释放的 Promise，模拟在途网络请求
function deferred() {
  let resolve, reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

function fillLoginForm(mine, { password = 'pass123456' } = {}) {
  mine.wlForm.value.username = 'testuser'
  mine.wlForm.value.password = password
}

// =============================================================================
describe('H5 Mine Page Web Login Guard Suite (真实生产源码回归)', () => {
  beforeEach(() => {
    resetBridge()
  })

  it('1. [模板回归] 登录按钮与模式切换绑定到受 guard 保护的处理函数', async () => {
    const rawSfc = await readFile(new URL('../src/pages/mine/index.vue', import.meta.url), 'utf8')
    assert.ok(rawSfc.includes('if (wlSaving.value) return'), 'doWebLogin 必须有请求中入口保护')
    assert.ok(rawSfc.includes(':class="{ saving: wlSaving }"'), '必须保留 saving 视觉态')
    assert.ok(rawSfc.includes('@tap="toggleRegisterMode"'), '注册/登录切换必须走受控处理函数')
    assert.ok(rawSfc.includes('@tap="toggleRecoveryMode"'), '找回密码切换必须走受控处理函数')
    assert.ok(rawSfc.includes('wlSaving.value = false'), '必须保留 wlSaving 释放逻辑')
  })

  it('2. 登录模式：请求进行中连续点击仅发起一次 webLogin，成功后释放可重试', async () => {
    const mine = createMineInstance()
    fillLoginForm(mine)

    const gate = deferred()
    let loginCalls = 0
    let sessionCalls = 0
    bridge.webLogin = async () => { loginCalls++; return gate.promise }
    bridge.storeLoginSession = async () => { sessionCalls++ }

    const p1 = mine.doWebLogin()
    const p2 = mine.doWebLogin()
    const p3 = mine.doWebLogin()
    assert.equal(loginCalls, 1, '请求在途时重复点击不得再次调用 webLogin')
    assert.equal(mine.wlSaving.value, true, '在途期间 wlSaving 必须为 true')

    gate.resolve(loginOk)
    await Promise.all([p1, p2, p3])
    assert.equal(loginCalls, 1, '整轮只应产生一次真实登录请求')
    assert.equal(sessionCalls, 1, '会话只应持久化一次')
    assert.equal(mine.wlSaving.value, false, '成功后 wlSaving 必须释放')

    // 释放后允许再次提交
    await mine.doWebLogin()
    assert.equal(loginCalls, 2, '释放后再次点击应允许新的登录请求')
    assert.equal(mine.wlSaving.value, false)
  })

  it('3. 登录模式：接口失败后 wlSaving 恢复，可立即重试成功', async () => {
    const mine = createMineInstance()
    fillLoginForm(mine)

    const toasts = []
    bridge.showToast = (o) => toasts.push(o)
    let loginCalls = 0
    bridge.webLogin = async () => {
      loginCalls++
      if (loginCalls === 1) throw new Error('账号或密码错误')
      return loginOk
    }

    await mine.doWebLogin()
    assert.equal(mine.wlSaving.value, false, '接口错误后 wlSaving 必须恢复 false')
    assert.ok(toasts.some(t => t.title === '账号或密码错误'), '应展示后端错误提示')

    await mine.doWebLogin()
    assert.equal(loginCalls, 2, '失败后应允许重试')
    assert.equal(mine.wlSaving.value, false)
    assert.ok(toasts.some(t => t.icon === 'success'), '重试成功应展示欢迎提示')
  })

  it('4. 登录模式：网络异常（非接口错误）同样释放并可重试，提示为友好中文', async () => {
    const mine = createMineInstance()
    fillLoginForm(mine)

    const toasts = []
    bridge.showToast = (o) => toasts.push(o)
    let loginCalls = 0
    bridge.webLogin = async () => {
      loginCalls++
      if (loginCalls === 1) throw new TypeError('fetch failed')
      return loginOk
    }

    await mine.doWebLogin()
    assert.equal(mine.wlSaving.value, false, '网络异常后 wlSaving 必须恢复 false')
    assert.ok(
      toasts.some(t => t.title === '网络连接失败，请检查网络后重试'),
      `网络异常应映射为友好提示，实际 toast: ${JSON.stringify(toasts)}`
    )
    assert.ok(!toasts.some(t => /fetch failed|TypeError/.test(t.title || '')), '不得把底层错误原文暴露给用户')
    await mine.doWebLogin()
    assert.equal(loginCalls, 2, '网络异常后应允许重试')
    assert.equal(mine.wlSaving.value, false)
  })

  it('5. 注册模式：连续点击仅注册一次，成功落地后释放', async () => {
    const mine = createMineInstance()
    fillLoginForm(mine, { password: 'newpassword10' })
    mine.wlRegister.value = true

    const gate = deferred()
    let registerCalls = 0
    bridge.register = async () => { registerCalls++; return gate.promise }

    const p1 = mine.doWebLogin()
    const p2 = mine.doWebLogin()
    assert.equal(registerCalls, 1, '注册请求在途时重复点击不得重复注册')

    gate.resolve(loginOk)
    await Promise.all([p1, p2])
    assert.equal(registerCalls, 1)
    assert.equal(mine.wlSaving.value, false, '注册成功后 wlSaving 必须释放')
  })

  it('6. 找回模式：连续点击仅提交一次，成功后退出找回模式并释放', async () => {
    const mine = createMineInstance()
    fillLoginForm(mine, { password: 'newpassword10' })
    mine.recoveryMode.value = true
    mine.recoveryCode.value = 'RECOVER-CODE-123'

    const gate = deferred()
    let recoverCalls = 0
    bridge.recoverPassword = async () => { recoverCalls++; return gate.promise }

    const p1 = mine.doWebLogin()
    const p2 = mine.doWebLogin()
    assert.equal(recoverCalls, 1, '找回请求在途时重复点击不得重复提交')

    gate.resolve({})
    await Promise.all([p1, p2])
    assert.equal(recoverCalls, 1)
    assert.equal(mine.recoveryMode.value, false, '重置成功后应退出找回模式')
    assert.equal(mine.recoveryCode.value, '', '找回码必须被清空')
    assert.equal(mine.wlSaving.value, false, '找回成功后 wlSaving 必须释放')
  })

  it('7. 请求在途时模式切换被锁定，完成后恢复可切换', async () => {
    const mine = createMineInstance()
    fillLoginForm(mine)

    const gate = deferred()
    bridge.webLogin = async () => gate.promise

    const p1 = mine.doWebLogin()
    assert.equal(mine.wlSaving.value, true)

    mine.toggleRegisterMode()
    assert.equal(mine.wlRegister.value, false, '在途时切换注册模式必须被忽略')
    mine.toggleRecoveryMode()
    assert.equal(mine.recoveryMode.value, false, '在途时切换找回模式必须被忽略')

    gate.resolve(loginOk)
    await p1
    assert.equal(mine.wlSaving.value, false)

    mine.toggleRegisterMode()
    assert.equal(mine.wlRegister.value, true, '释放后模式切换应恢复可用')
    mine.toggleRecoveryMode()
    assert.equal(mine.recoveryMode.value, true)
    assert.equal(mine.wlRegister.value, false, '切到找回模式应同时退出注册模式')
  })

  it('8. 输入校验失败不占用 wlSaving，修正后可直接提交', async () => {
    const mine = createMineInstance()
    mine.wlForm.value.username = 'a' // 过短
    mine.wlForm.value.password = '123'

    await mine.doWebLogin()
    assert.equal(mine.wlSaving.value, false, '校验失败不得残留 saving 态')

    fillLoginForm(mine)
    let loginCalls = 0
    bridge.webLogin = async () => { loginCalls++; return loginOk }
    await mine.doWebLogin()
    assert.equal(loginCalls, 1, '修正输入后应能正常提交')
    assert.equal(mine.wlSaving.value, false)
  })

  // ---- 畸形/不完整成功响应加固 ----
  it('9. 缺 user_info 的成功响应：不写会话、不关弹窗、友好提示、无 TypeError', async () => {
    const mine = createMineInstance()
    fillLoginForm(mine)
    mine.showWebLogin.value = true

    const toasts = []
    bridge.showToast = (o) => toasts.push(o)
    let sessionCalls = 0
    let storedUsers = 0
    bridge.storeLoginSession = async () => { sessionCalls++ }
    bridge.setUserInfo = () => { storedUsers++ }
    bridge.webLogin = async () => ({ access_token: 'token-x', role: 'student' }) // 缺 user_info

    await mine.doWebLogin()
    assert.equal(sessionCalls, 0, '畸形响应不得调用 storeLoginSession 持久化会话')
    assert.equal(storedUsers, 0, '畸形响应不得写入用户信息')
    assert.equal(mine.loggedIn.value, false, '畸形响应不得切换 loggedIn')
    assert.equal(mine.showWebLogin.value, true, '畸形响应时弹窗必须保持打开')
    assert.equal(mine.wlSaving.value, false, 'finally 必须释放 wlSaving')
    assert.ok(toasts.some(t => t.title === '登录响应异常，请稍后重试'),
      `应展示友好中文提示，实际: ${JSON.stringify(toasts)}`)
    assert.ok(!toasts.some(t => /TypeError|undefined/.test(t.title || '')),
      '不得向用户暴露 TypeError/undefined 原文')

    // 后端恢复返回完整契约后，同一弹窗可直接重试成功
    // （mock 会话落盘后 isLoggedIn 翻转为 true，模拟真实 setSession 效果）
    bridge.storeLoginSession = async () => { sessionCalls++; bridge.isLoggedIn = () => true }
    bridge.webLogin = async () => loginOk
    await mine.doWebLogin()
    assert.equal(sessionCalls, 1, '恢复后重试应正常持久化会话')
    assert.equal(mine.showWebLogin.value, false, '重试成功后弹窗关闭')
    assert.equal(mine.loggedIn.value, true)
  })

  it('10. 缺 access_token 的成功响应：同样拒绝落地', async () => {
    const mine = createMineInstance()
    fillLoginForm(mine)
    mine.showWebLogin.value = true

    const toasts = []
    bridge.showToast = (o) => toasts.push(o)
    let sessionCalls = 0
    bridge.storeLoginSession = async () => { sessionCalls++ }
    bridge.webLogin = async () => ({ user_info: { id: 'u1', nickname: '同学', is_verified: false }, role: 'student' })

    await mine.doWebLogin()
    assert.equal(sessionCalls, 0, '缺 access_token 不得持久化会话')
    assert.equal(mine.showWebLogin.value, true, '弹窗保持打开')
    assert.equal(mine.loggedIn.value, false)
    assert.equal(mine.wlSaving.value, false)
    assert.ok(toasts.some(t => t.title === '登录响应异常，请稍后重试'))
  })

  it('11. 注册模式收到畸形响应同样拦截，不落地会话', async () => {
    const mine = createMineInstance()
    fillLoginForm(mine, { password: 'newpassword10' })
    mine.wlRegister.value = true
    mine.showWebLogin.value = true

    const toasts = []
    bridge.showToast = (o) => toasts.push(o)
    let sessionCalls = 0
    bridge.storeLoginSession = async () => { sessionCalls++ }
    bridge.register = async () => ({}) // 空响应

    await mine.doWebLogin()
    assert.equal(sessionCalls, 0, '注册畸形响应不得持久化会话')
    assert.equal(mine.showWebLogin.value, true)
    assert.equal(mine.wlSaving.value, false)
    assert.ok(toasts.some(t => t.title === '登录响应异常，请稍后重试'))
  })

  it('12. 微信/uni 风格网络错误 request:fail 映射为友好中文提示', async () => {
    const mine = createMineInstance()
    fillLoginForm(mine)

    const toasts = []
    bridge.showToast = (o) => toasts.push(o)
    bridge.webLogin = async () => { throw new Error('request:fail timeout') }

    await mine.doWebLogin()
    assert.ok(toasts.some(t => t.title === '网络连接失败，请检查网络后重试'),
      `request:fail 应映射为友好提示，实际: ${JSON.stringify(toasts)}`)
    assert.ok(!toasts.some(t => (t.title || '').includes('request:fail')), '不得暴露 request:fail 原文')
    assert.equal(mine.wlSaving.value, false)
  })

  it('13. 后端明确认证错误原样保留，不被网络映射吞掉', async () => {
    const mine = createMineInstance()
    fillLoginForm(mine)

    const toasts = []
    bridge.showToast = (o) => toasts.push(o)
    bridge.webLogin = async () => { throw new Error('账号或密码错误') }

    await mine.doWebLogin()
    assert.ok(toasts.some(t => t.title === '账号或密码错误'), '后端错误信息必须原样展示')
    assert.ok(!toasts.some(t => t.title === '网络连接失败，请检查网络后重试'), '不得误映射为网络错误')
  })

  it('14. 缺 role 或 role 越界的成功响应：拒绝落地会话', async () => {
    for (const bad of [
      { access_token: 't', user_info: { id: 'u1', nickname: '同学', is_verified: false } }, // 缺 role
      { access_token: 't', role: 'superuser', user_info: { id: 'u1', nickname: '同学', is_verified: false } }, // 越界 role
    ]) {
      const mine = createMineInstance()
      fillLoginForm(mine)
      mine.showWebLogin.value = true

      const toasts = []
      bridge.showToast = (o) => toasts.push(o)
      let sessionCalls = 0
      bridge.storeLoginSession = async () => { sessionCalls++ }
      bridge.webLogin = async () => bad

      await mine.doWebLogin()
      assert.equal(sessionCalls, 0, `畸形 role 响应不得持久化会话: ${JSON.stringify(bad)}`)
      assert.equal(mine.showWebLogin.value, true, '弹窗保持打开')
      assert.equal(mine.loggedIn.value, false)
      assert.equal(mine.wlSaving.value, false)
      assert.ok(toasts.some(t => t.title === '登录响应异常，请稍后重试'),
        `应展示友好提示，实际: ${JSON.stringify(toasts)}`)
      resetBridge()
    }
  })
})
