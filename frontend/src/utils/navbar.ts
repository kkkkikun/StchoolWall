/**
 * 跨端导航栏与胶囊避让尺寸计算器。
 * 兼容 H5、微信小程序 (MP-WEIXIN) 与 App。
 */

export interface NavBarMetrics {
  /** 状态栏高度 (px) */
  statusBarHeight: number
  /** 导航内容栏高度 (px) */
  navBarHeight: number
  /** 整个顶部导航总高度 = 状态栏 + 导航内容 (px) */
  totalHeight: number
  /** 右侧需要为微信胶囊按钮避让的内边距 (px) */
  capsulePaddingRight: number
  /** 胶囊按钮高度 (px) */
  capsuleHeight: number
  /** 胶囊按钮宽度 (px) */
  capsuleWidth: number
  /** 是否存在微信右上角胶囊按钮 */
  hasCapsule: boolean
  /** 屏幕可用宽度 (px) */
  windowWidth: number
}

let cachedMetrics: NavBarMetrics | null = null

export function getNavBarMetrics(): NavBarMetrics {
  if (cachedMetrics) return cachedMetrics

  const sys = uni.getSystemInfoSync()
  const statusBarHeight = sys.statusBarHeight || 0
  let navBarHeight = 44
  let capsulePaddingRight = 0
  let capsuleHeight = 32
  let capsuleWidth = 87
  let hasCapsule = false

  // #ifdef MP-WEIXIN
  try {
    const rect = uni.getMenuButtonBoundingClientRect()
    if (rect && rect.top && rect.width) {
      hasCapsule = true
      capsuleHeight = rect.height
      capsuleWidth = rect.width
      // 导航内容栏高度 = (胶囊top - 状态栏高度) * 2 + 胶囊高度
      navBarHeight = (rect.top - statusBarHeight) * 2 + rect.height
      // 右侧避让 padding = 屏幕宽度 - 胶囊左边界 + 8px 安全间隙
      capsulePaddingRight = Math.max(0, sys.windowWidth - rect.left + 8)
    }
  } catch (e) {
    // 降级兜底
    hasCapsule = true
    capsulePaddingRight = 95
    navBarHeight = 44
  }
  // #endif

  // #ifndef MP-WEIXIN
  navBarHeight = 44
  capsulePaddingRight = 0
  hasCapsule = false
  // #endif

  cachedMetrics = {
    statusBarHeight,
    navBarHeight,
    totalHeight: statusBarHeight + navBarHeight,
    capsulePaddingRight,
    capsuleHeight,
    capsuleWidth,
    hasCapsule,
    windowWidth: sys.windowWidth,
  }

  return cachedMetrics
}

/** 导航节流锁：防止用户快速连击导致重复导航 */
let isNavigating = false
let navTimer: ReturnType<typeof setTimeout> | null = null

/**
 * 尝试获取导航锁。
 * 若当前已在导航中，返回 false；否则锁定并在 duration 毫秒后自动释放。
 */
export function acquireNavLock(duration = 400): boolean {
  if (isNavigating) return false
  isNavigating = true
  if (navTimer) clearTimeout(navTimer)
  navTimer = setTimeout(() => {
    isNavigating = false
    navTimer = null
  }, duration)
  return true
}

/** 重置导航锁（仅用于单元测试） */
export function resetNavLockForTest(): void {
  isNavigating = false
  if (navTimer) {
    clearTimeout(navTimer)
    navTimer = null
  }
}

/**
 * 非原生 tabBar 架构下的安全跳转首页/顶层页。
 * 优先使用 redirectTo 替换当前页面，若失败则降级使用 reLaunch。
 */
export function safeNavigateToHome(fallbackUrl = '/pages/index/index'): void {
  uni.redirectTo({
    url: fallbackUrl,
    fail: () => {
      uni.reLaunch({ url: fallbackUrl })
    },
  })
}

/**
 * 跨端安全返回上一页：
 * - 页面栈多于 1 页时：调用 uni.navigateBack()，失败则降级到 safeNavigateToHome
 * - 页面栈仅 1 页（直接链接进入或单页落地）：调用 safeNavigateToHome(fallbackUrl)
 */
export function safeNavigateBack(fallbackUrl = '/pages/index/index'): void {
  if (!acquireNavLock()) return

  const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
  if (pages.length > 1) {
    uni.navigateBack({
      fail: () => {
        safeNavigateToHome(fallbackUrl)
      },
    })
  } else {
    safeNavigateToHome(fallbackUrl)
  }
}

