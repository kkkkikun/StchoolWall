/**
 * 客户端诊断采集：反馈提交时附带「出错当时的现场」。
 *
 * 只在内存里保留最近若干条，刷新页面即清空——反馈通道面向内部测试，
 * 采集的是出错现场，不该长期留存用户的浏览轨迹。
 *
 * 无第三方依赖：只依赖 uni 全局 API 与仓库既有的主题状态。
 */
import { useThemeMode } from './theme'

export interface DiagnosticError {
  message: string
  source: string
  stack?: string
  time: string
}

export interface DiagnosticApiFailure {
  method: string
  url: string
  status: number
  message: string
  time: string
}

export interface Diagnostics {
  errors: DiagnosticError[]
  api_failures: DiagnosticApiFailure[]
  route: string
  viewport: string
  theme: string
  platform: string
  network: string
  app_version: string
  collected_at: string
}

/** 环形缓冲上限：超出丢最旧的（异常现场的价值随时间衰减）。 */
const MAX_ERRORS = 50
/** 接口失败单独限 20 条：再多会把真正的异常现场挤掉。 */
const MAX_API_FAILURES = 20
/** 后端 diagnostics 字段有 32KB 上限，超了会整包丢弃；客户端先自己裁到 24KB。 */
const MAX_PAYLOAD_CHARS = 24000
/** 同一异常在 Vue errorHandler 与 uni.onError 里各来一次，去重窗口取 3 秒。 */
const DUP_WINDOW_MS = 3000

export const APP_VERSION = 'h5'

const errors: DiagnosticError[] = []
const apiFailures: DiagnosticApiFailure[] = []
let installed = false
let lastNetwork = 'unknown'

function now(): string {
  return new Date().toISOString()
}

function pushBounded<T>(list: T[], item: T, limit: number): void {
  list.push(item)
  if (list.length > limit) list.splice(0, list.length - limit)
}

/** 与最近一条消息相同且时间很近时视为同一次异常（Vue 与 uni 会各报一次）。 */
function isDuplicate(message: string): boolean {
  const last = errors[errors.length - 1]
  if (!last || last.message !== message) return false
  return Date.now() - Date.parse(last.time) < DUP_WINDOW_MS
}

/** 异常对象/字符串统一成可读消息。 */
function normalizeMessage(value: unknown): string {
  if (typeof value === 'string') return value.slice(0, 500)
  if (value instanceof Error) return (value.message || String(value)).slice(0, 500)
  if (value && typeof value === 'object' && 'message' in value) {
    return String((value as { message?: unknown }).message ?? '').slice(0, 500)
  }
  return String(value ?? '').slice(0, 500)
}

/** 记录一条未捕获异常（脚本错误 / 未处理的 Promise 拒绝）。 */
export function recordError(message: unknown, source: string, stack?: string): void {
  const text = normalizeMessage(message)
  if (isDuplicate(text)) return
  pushBounded(errors, {
    message: text,
    source: String(source ?? '').slice(0, 120),
    stack: stack?.slice(0, 800),
    time: now(),
  }, MAX_ERRORS)
}

/** 记录一次失败的接口请求（网络层失败 / HTTP 4xx-5xx / 业务 code≠0）。 */
export function recordApiFailure(method: string, url: string, status: number, message: string): void {
  pushBounded(apiFailures, {
    method: String(method ?? '').toUpperCase().slice(0, 10),
    url: String(url ?? '').slice(0, 300),
    status: Number(status) || 0,
    message: String(message ?? '').slice(0, 300),
    time: now(),
  }, MAX_API_FAILURES)
}

/** 当前页面路由：uni 的页面实例带 route，H5 与小程序一致。 */
function currentRoute(): string {
  try {
    if (typeof getCurrentPages !== 'function') return ''
    const pages = getCurrentPages() as Array<{ route?: string }>
    const current = pages[pages.length - 1]
    return String(current?.route || '').replace(/^\//, '').slice(0, 120)
  } catch {
    return ''
  }
}

function currentTheme(): string {
  try {
    return useThemeMode().value
  } catch {
    return 'light'
  }
}

function systemInfo(): Record<string, any> | null {
  try {
    return uni.getSystemInfoSync() as unknown as Record<string, any>
  } catch {
    return null
  }
}

/** 网络类型是异步 API：收集时要等它回来，失败就用上一次的值兜底。 */
function detectNetwork(): Promise<string> {
  return new Promise((resolve) => {
    try {
      uni.getNetworkType({
        success: (res) => resolve(String(res.networkType || 'unknown')),
        fail: () => resolve(lastNetwork),
      })
    } catch {
      resolve(lastNetwork)
    }
  })
}

/** 现场条数（异常 + 接口失败），用于页面上提示「会附带多少条日志」。 */
export function diagnosticsCount(): number {
  return errors.length + apiFailures.length
}

export function clearDiagnostics(): void {
  errors.length = 0
  apiFailures.length = 0
}

/** 超出后端 32KB 上限时，先丢最旧的记录，保证现场仍有内容。 */
function trimToBudget(payload: Diagnostics): Diagnostics {
  let size = JSON.stringify(payload).length
  while (size > MAX_PAYLOAD_CHARS && payload.errors.length) {
    payload.errors.shift()
    size = JSON.stringify(payload).length
  }
  while (size > MAX_PAYLOAD_CHARS && payload.api_failures.length) {
    payload.api_failures.shift()
    size = JSON.stringify(payload).length
  }
  return payload
}

/** 采集当前现场；调用方决定是否随反馈一起上传。 */
export async function collectDiagnostics(): Promise<Diagnostics> {
  lastNetwork = await detectNetwork()
  const info = systemInfo()
  const payload: Diagnostics = {
    errors: [...errors],
    api_failures: [...apiFailures],
    route: currentRoute(),
    viewport: info ? `${info.windowWidth || 0}x${info.windowHeight || 0}` : '',
    theme: currentTheme(),
    platform: info ? `${info.platform || ''} ${info.system || ''}`.trim() : '',
    network: lastNetwork,
    app_version: APP_VERSION,
    collected_at: now(),
  }
  return trimToBudget(payload)
}

/**
 * 挂上全局异常捕获。只装一次，重复调用直接返回。
 *
 * 为什么同时用 uni.onError 和 Vue 的 errorHandler：
 *   H5 上 Vue 的 errorHandler 与 uni.onError 会先后收到同一个异常（uni 内部
 *   把 errorHandler 包了一层再派发 app 级 ON_ERROR），两者都收才不漏场景；
 *   去重交给 recordError。
 */
export function installDiagnostics(): void {
  if (installed) return
  installed = true

  try {
    uni.onError((error: unknown) => {
      const stack = (error as { stack?: string } | null)?.stack
      recordError(error, 'uni.onError', stack)
    })
  } catch {
    /* 个别平台没有该 API，忽略 */
  }

  // uni.onUnhandledRejection 并非所有平台都有（安卓 App 暂不支持）：
  // 缺失时靠 Vue 的 errorHandler 与关键调用点的 try/catch 兜底。
  const onUnhandled = (uni as unknown as { onUnhandledRejection?: (cb: (res: { reason?: unknown }) => void) => void }).onUnhandledRejection
  if (typeof onUnhandled === 'function') {
    try {
      onUnhandled.call(uni, (res) => {
        const reason = res?.reason
        const message = reason instanceof Error ? reason.message : String(reason ?? '未处理的 Promise 拒绝')
        const stack = reason instanceof Error ? reason.stack : undefined
        recordError(message, 'unhandledRejection', stack)
      })
    } catch {
      /* 忽略 */
    }
  }
}
