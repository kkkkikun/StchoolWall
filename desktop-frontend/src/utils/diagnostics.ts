/**
 * 客户端诊断采集：反馈提交时附带「当时的现场」。
 *
 * 只在内存里保留最近若干条，刷新页面即清空——
 * 反馈通道面向内部测试，采集的是出错现场，不该长期留存用户的浏览轨迹。
 */

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
  user_agent: string
  app_version: string
  network: string
  collected_at: string
}

const MAX_ERRORS = 30
const MAX_API_FAILURES = 20
export const APP_VERSION = 'pc'

const errors: DiagnosticError[] = []
const apiFailures: DiagnosticApiFailure[] = []
let currentRoute = ''
let installed = false

function now(): string {
  return new Date().toISOString()
}

function pushBounded<T>(list: T[], item: T, limit: number): void {
  list.push(item)
  if (list.length > limit) list.splice(0, list.length - limit)
}

export function recordError(message: string, source: string, stack?: string): void {
  pushBounded(
    errors,
    { message: String(message ?? '').slice(0, 500), source: String(source ?? '').slice(0, 200), stack: stack?.slice(0, 800), time: now() },
    MAX_ERRORS,
  )
}

export function recordApiFailure(method: string, url: string, status: number, message: string): void {
  pushBounded(
    apiFailures,
    { method: method.toUpperCase(), url: String(url ?? '').slice(0, 300), status, message: String(message ?? '').slice(0, 300), time: now() },
    MAX_API_FAILURES,
  )
}

export function setCurrentRoute(path: string): void {
  currentRoute = String(path ?? '').slice(0, 120)
}

export function clearDiagnostics(): void {
  errors.length = 0
  apiFailures.length = 0
}

export function diagnosticsCount(): number {
  return errors.length + apiFailures.length
}

function viewport(): string {
  if (typeof window === 'undefined') return ''
  return `${window.innerWidth}x${window.innerHeight}`
}

function theme(): string {
  if (typeof document === 'undefined') return 'light'
  return document.documentElement.classList.contains('theme-dark') ? 'dark' : 'light'
}

function userAgent(): string {
  if (typeof navigator === 'undefined') return ''
  return navigator.userAgent ?? ''
}

function network(): string {
  // Node 也有 navigator，但它的 onLine 没有浏览器语义，只能当作未知
  if (typeof navigator === 'undefined' || typeof window === 'undefined') return 'unknown'
  return navigator.onLine ? 'online' : 'offline'
}

/** 采集当前现场；调用方决定是否随反馈一起上传。 */
export function collectDiagnostics(): Diagnostics {
  return {
    errors: [...errors],
    api_failures: [...apiFailures],
    route: currentRoute,
    viewport: viewport(),
    theme: theme(),
    user_agent: userAgent(),
    app_version: APP_VERSION,
    network: network(),
    collected_at: now(),
  }
}

/**
 * 挂上全局错误捕获。只装一次，重复调用直接返回。
 * console.error 被包了一层：Element Plus 内部的报错也会冒泡到控制台，
 * 那是 UI 类问题最常见的线索来源，但必须保留原行为，否则会掩盖真实堆栈。
 */
export function installDiagnostics(): void {
  if (installed || typeof window === 'undefined') return
  installed = true

  window.addEventListener('error', (event) => {
    recordError(event.message ?? '未捕获异常', event.filename ?? 'unknown', event.error?.stack)
  })

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason as { message?: string; stack?: string } | undefined
    recordError(reason?.message ?? '未处理的 Promise 拒绝', 'unhandledrejection', reason?.stack)
  })

  const originalError = console.error.bind(console)
  console.error = (...args: unknown[]) => {
    try {
      recordError(args.map((item) => String(item)).join(' '), 'console.error')
    } catch {
      // 采集本身不能影响原有报错流程
    }
    originalError(...args)
  }
}
