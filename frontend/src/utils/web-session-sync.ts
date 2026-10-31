import type { SessionData } from './storage'

type Message = { type: 'session'; data: SessionData } | { type: 'logout' } | { type: 'request' }
interface Channel {
  postMessage(message: Message): void
  addEventListener(type: 'message', listener: (event: { data: Message }) => void): void
}
export function createWebSessionSync(channel: Channel, options: {
  current: () => SessionData | null
  csrf: () => string
  apply: (data: SessionData) => void
  clear: () => void
}) {
  const accept = (data: SessionData) => !!data && typeof data.access_token === 'string'
    && !!data.access_token && !!data.user_info?.id && ['guest', 'student', 'admin'].includes(data.role)
    && !!data.csrf_token && data.csrf_token === options.csrf()
  const publish = (data: SessionData) => {
    // Refresh tokens never cross the channel or enter persistent browser storage.
    const { refresh_token: _refresh, ...safe } = data
    channel.postMessage({ type: 'session', data: safe })
  }
  channel.addEventListener('message', ({ data: message }) => {
    if (message?.type === 'session' && accept(message.data)) options.apply(message.data)
    else if (message?.type === 'logout') options.clear()
    else if (message?.type === 'request') {
      const data = options.current()
      if (data && accept(data)) publish(data)
    }
  })
  return {
    publish,
    logout: () => channel.postMessage({ type: 'logout' }),
    request: () => new Promise<void>((resolve) => {
      channel.postMessage({ type: 'request' })
      setTimeout(resolve, 100)
    }),
  }
}

export function withWebRefreshLock(locks: { request(name: string, callback: () => Promise<void>): Promise<void> } | null | undefined, refresh: () => Promise<void>): Promise<void> {
  if (!locks) return Promise.reject(new Error('浏览器不支持安全刷新，请使用支持 Web Locks 的浏览器并重新登录'))
  return locks.request('schoolwall-refresh-session', refresh)
}
