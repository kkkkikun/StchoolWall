import { describe, it, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, unlink, writeFile } from 'node:fs/promises'
import ts from 'typescript'
import { parse, compileScript } from 'vue/compiler-sfc'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { compileTsModule } from './helpers/compile-ts.mjs'

// 模拟 uni 全局环境
function createMockUni() {
  const calls = {
    redirectTo: [],
    reLaunch: [],
    navigateBack: [],
    switchTab: [],
  }

  const uniMock = {
    getSystemInfoSync: () => ({ statusBarHeight: 20, windowWidth: 375 }),
    redirectTo(options) {
      calls.redirectTo.push(options)
    },
    reLaunch(options) {
      calls.reLaunch.push(options)
    },
    navigateBack(options) {
      calls.navigateBack.push(options || {})
    },
    switchTab(options) {
      calls.switchTab.push(options)
    },
  }

  return { uniMock, calls }
}

const { uniMock, calls } = createMockUni()
globalThis.uni = { ...uniMock }
globalThis.getCurrentPages = () => []

// 编译并加载 navbar.ts
const navbarTs = await readFile(new URL('../src/utils/navbar.ts', import.meta.url), 'utf8')
const navbarJs = ts.transpileModule(navbarTs, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText

const tempNavbarPath = new URL('./.temp-navbar.mjs', import.meta.url)
await writeFile(tempNavbarPath, navbarJs)

const {
  safeNavigateToHome,
  safeNavigateBack,
  acquireNavLock,
  resetNavLockForTest,
  getNavBarMetrics,
} = await import(tempNavbarPath.href)

// 编译并动态加载 custom-nav-bar.vue
const tempMockThemePath = new URL('./.mock-theme.mjs', import.meta.url)
await writeFile(tempMockThemePath, 'export function useTheme() { return { themeClass: "theme-light" }; }')

// 图标注册表走真实源码（nav-bar 的返回箭头来自注册表）
const iconsSpecifier = await compileTsModule('../../src/utils/icons.ts', '.temp-nav-icons.mjs')

const sfcContent = await readFile(new URL('../src/components/custom-nav-bar.vue', import.meta.url), 'utf8')
const sfc = parse(sfcContent)
const script = compileScript(sfc.descriptor, { id: 'custom-nav-bar' })
const componentCode = script.content
  .replaceAll('@/utils/theme', './.mock-theme.mjs')
  .replaceAll('@/utils/navbar', './.temp-navbar.mjs')
  .replaceAll('@/utils/icons', iconsSpecifier)

const componentJs = ts.transpileModule(componentCode, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText

const tempComponentPath = new URL('./.temp-custom-nav-bar.mjs', import.meta.url)
await writeFile(tempComponentPath, componentJs)

const CustomNavBar = (await import(tempComponentPath.href)).default

// 清理临时文件（保留已加载模块在内存中）
await unlink(tempMockThemePath)
await unlink(tempNavbarPath)
await unlink(tempComponentPath)
await unlink(new URL('./.temp-nav-icons.mjs', import.meta.url))

/**
 * 辅助函数：在真实 Vue 渲染上下文中挂载 CustomNavBar 并获取其 setup 暴露的 bindings
 */
async function mountCustomNavBar(props = {}, listeners = {}) {
  let exposedBindings = null
  const origSetup = CustomNavBar.setup
  CustomNavBar.setup = function (p, ctx) {
    const res = origSetup.call(this, p, ctx)
    exposedBindings = res
    return res
  }

  const app = createSSRApp({
    render() {
      return h(CustomNavBar, { ...props, ...listeners })
    },
  })
  await renderToString(app)
  return exposedBindings
}

describe('Navigation Suite (串行执行，确保全局 mock 隔离)', { concurrency: false }, () => {
  beforeEach(() => {
    resetNavLockForTest()
    calls.redirectTo.length = 0
    calls.reLaunch.length = 0
    calls.navigateBack.length = 0
    calls.switchTab.length = 0
    globalThis.uni.redirectTo = uniMock.redirectTo
    globalThis.uni.reLaunch = uniMock.reLaunch
    globalThis.uni.navigateBack = uniMock.navigateBack
    globalThis.uni.switchTab = uniMock.switchTab
    globalThis.getCurrentPages = () => []
  })

  // ==================== 单元测试：工具函数层 ====================

  it('1. safeNavigateToHome: 优先调用 redirectTo 跳转指定路径', () => {
    safeNavigateToHome('/pages/index/index')
    assert.equal(calls.redirectTo.length, 1)
    assert.equal(calls.redirectTo[0].url, '/pages/index/index')
    assert.equal(calls.reLaunch.length, 0)
  })

  it('2. safeNavigateToHome: 当 redirectTo 失败时自动降级到 reLaunch', () => {
    globalThis.uni.redirectTo = (options) => {
      calls.redirectTo.push(options)
      if (typeof options.fail === 'function') {
        options.fail(new Error('fail to redirect'))
      }
    }

    safeNavigateToHome('/pages/index/index')
    assert.equal(calls.redirectTo.length, 1)
    assert.equal(calls.reLaunch.length, 1)
    assert.equal(calls.reLaunch[0].url, '/pages/index/index')
  })

  it('3. safeNavigateBack: 页面栈有多页（>1）时正常调用 navigateBack', () => {
    globalThis.getCurrentPages = () => [{}, {}]

    safeNavigateBack('/pages/index/index')
    assert.equal(calls.navigateBack.length, 1)
    assert.equal(calls.redirectTo.length, 0)
    assert.equal(calls.switchTab.length, 0)
  })

  it('4. safeNavigateBack: 当 navigateBack 失败时降级跳转首页', () => {
    globalThis.getCurrentPages = () => [{}, {}]
    globalThis.uni.navigateBack = (options) => {
      calls.navigateBack.push(options)
      if (options && typeof options.fail === 'function') {
        options.fail(new Error('navigateBack fail'))
      }
    }

    safeNavigateBack('/pages/index/index')
    assert.equal(calls.navigateBack.length, 1)
    assert.equal(calls.redirectTo.length, 1)
    assert.equal(calls.redirectTo[0].url, '/pages/index/index')
  })

  it('5. safeNavigateBack: 单页栈（<=1）时绝不调用 switchTab，直接安全重定向到首页或指定兜底页', () => {
    globalThis.getCurrentPages = () => [{}]

    safeNavigateBack('/pages/index/index')
    assert.equal(calls.navigateBack.length, 0, '单页栈不得调用 navigateBack')
    assert.equal(calls.switchTab.length, 0, '无原生 tabBar 下严禁调用 switchTab')
    assert.equal(calls.redirectTo.length, 1, '应使用 safeNavigateToHome')
    assert.equal(calls.redirectTo[0].url, '/pages/index/index')

    resetNavLockForTest()
    calls.redirectTo.length = 0
    safeNavigateBack('/pages/message/index')
    assert.equal(calls.redirectTo.length, 1)
    assert.equal(calls.redirectTo[0].url, '/pages/message/index')
  })

  it('6. acquireNavLock: 防重复导航锁定，短时间内多次点击只放行首次', async () => {
    assert.equal(acquireNavLock(100), true, '首次调用应成功获取锁')
    assert.equal(acquireNavLock(100), false, '锁定期间第二次调用应被拦截')
    assert.equal(acquireNavLock(100), false, '锁定期间第三次调用应被拦截')

    await new Promise((resolve) => setTimeout(resolve, 120))
    assert.equal(acquireNavLock(100), true, '超时后应重新获得锁')
  })

  it('7. safeNavigateBack: 连续快速连击防抖，避免重复导航与页面双重出栈', () => {
    globalThis.getCurrentPages = () => [{}, {}, {}]

    safeNavigateBack()
    safeNavigateBack()

    assert.equal(calls.navigateBack.length, 1, '快速连击只能执行一次 navigateBack')
  })

  // ==================== 组件行为测试：CustomNavBar 真实调用链 ====================

  it('8. [组件回归] 无 @back 监听器且多页栈（>1）时，点击返回应正常执行 navigateBack', async () => {
    globalThis.getCurrentPages = () => [{}, {}] // 多页栈

    const comp = await mountCustomNavBar({ showBack: true, fallbackUrl: '/pages/index/index' })
    assert.ok(comp, '组件 bindings 必须成功挂载')

    comp.handleBack()
    assert.equal(calls.navigateBack.length, 1, '必须正常调用一次 navigateBack，不能因双重锁被吞掉')
    assert.equal(calls.redirectTo.length, 0, '多页栈不得调用 redirectTo')
  })

  it('9. [组件回归] 无 @back 监听器且单页栈（<=1）时，点击返回应进入指定 fallbackUrl', async () => {
    globalThis.getCurrentPages = () => [{}] // 单页栈

    const comp = await mountCustomNavBar({ showBack: true, fallbackUrl: '/pages/message/index' })
    comp.handleBack()

    assert.equal(calls.navigateBack.length, 0, '单页栈不得调用 navigateBack')
    assert.equal(calls.switchTab.length, 0, '无原生 tabBar 下严禁调用 switchTab')
    assert.equal(calls.redirectTo.length, 1, '单页栈必须调用 redirectTo 导向兜底页')
    assert.equal(calls.redirectTo[0].url, '/pages/message/index', '应进入指定的 fallbackUrl')
  })

  it('10. [组件回归] 有 @back 监听器时只通知父组件、不额外出栈', async () => {
    globalThis.getCurrentPages = () => [{}, {}]

    let parentBackCalled = 0
    const comp = await mountCustomNavBar(
      { showBack: true, fallbackUrl: '/pages/index/index' },
      { onBack: () => { parentBackCalled++ } }
    )

    comp.handleBack()
    assert.equal(parentBackCalled, 1, '父组件监听器必须被调用')
    assert.equal(calls.navigateBack.length, 0, '由父组件负责导航，组件内不得额外调用 navigateBack')
    assert.equal(calls.redirectTo.length, 0, '不得触发兜底重定向')
  })

  it('11. [组件回归] 用户快速双击不产生第二次导航', async () => {
    globalThis.getCurrentPages = () => [{}, {}, {}]

    const comp = await mountCustomNavBar({ showBack: true, fallbackUrl: '/pages/index/index' })

    // 连续快速双击
    comp.handleBack()
    comp.handleBack()

    assert.equal(calls.navigateBack.length, 1, '快速连击只能执行一次 navigateBack，第二次必须被拦截')
  })

  it('12. [组件回归] navigateBack 失败时的降级路径', async () => {
    globalThis.getCurrentPages = () => [{}, {}]

    // 模拟 navigateBack 失败（如平台页面栈状态异常）
    globalThis.uni.navigateBack = (options) => {
      calls.navigateBack.push(options)
      if (options && typeof options.fail === 'function') {
        options.fail(new Error('native navigateBack failed'))
      }
    }

    const comp = await mountCustomNavBar({ showBack: true, fallbackUrl: '/pages/index/index' })
    comp.handleBack()

    assert.equal(calls.navigateBack.length, 1, '应先尝试 navigateBack')
    assert.equal(calls.redirectTo.length, 1, 'navigateBack 失败后应降级调用 redirectTo')
    assert.equal(calls.redirectTo[0].url, '/pages/index/index')
  })
})
