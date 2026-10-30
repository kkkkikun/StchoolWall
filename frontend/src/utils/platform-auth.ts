/** Platform login/refresh adapter. Android refresh tokens are encrypted with Android Keystore. */
declare const plus: any

export type ClientType = 'web' | 'android' | 'weixin'
export function clientType(): ClientType {
  let result: ClientType = 'web'
  // #ifdef MP-WEIXIN
  result = 'weixin'
  // #endif
  // #ifdef APP-PLUS
  result = 'android'
  // #endif
  return result
}

const SECURE_KEY = 'sw_android_refresh_encrypted'
const KEY_ALIAS = 'schoolwall.session.refresh.v1'

function androidCipher() {
  if (typeof plus === 'undefined' || !plus.android || plus.os.name !== 'Android') {
    throw new Error('当前设备安全存储不可用，请使用网页版登录')
  }
  const java = (name: string) => plus.android.importClass(name)
  const store = java('java.security.KeyStore').getInstance('AndroidKeyStore')
  store.load(null)
  if (!store.containsAlias(KEY_ALIAS)) {
    const generator = java('javax.crypto.KeyGenerator').getInstance('AES', 'AndroidKeyStore')
    const Builder = java('android.security.keystore.KeyGenParameterSpec$Builder')
    const spec = new Builder(KEY_ALIAS, 3)
    spec.setBlockModes(['GCM'])
    spec.setEncryptionPaddings(['NoPadding'])
    spec.setRandomizedEncryptionRequired(true)
    generator.init(spec.build())
    generator.generateKey()
  }
  return { java, key: store.getKey(KEY_ALIAS, null) }
}

export const refreshAdapter = {
  get(): string {
    if (clientType() === 'web') return ''
    if (clientType() === 'weixin') return uni.getStorageSync('refresh_token') || ''
    const saved = uni.getStorageSync(SECURE_KEY)
    if (!saved) return ''
    try {
      const { java, key } = androidCipher()
      const entry = typeof saved === 'string' ? JSON.parse(saved) : saved
      const Base64 = java('android.util.Base64')
      const cipher = java('javax.crypto.Cipher').getInstance('AES/GCM/NoPadding')
      const Spec = java('javax.crypto.spec.GCMParameterSpec')
      cipher.init(2, key, new Spec(128, Base64.decode(entry.iv, 2)))
      const StringClass = java('java.lang.String')
      return String(new StringClass(cipher.doFinal(Base64.decode(entry.data, 2)), 'UTF-8'))
    } catch {
      uni.removeStorageSync(SECURE_KEY)
      throw new Error('设备安全会话已失效，请重新登录')
    }
  },
  set(token: string): void {
    if (clientType() === 'web') return
    if (clientType() === 'weixin') {
      uni.setStorageSync('refresh_token', token)
      return
    }
    try {
      const { java, key } = androidCipher()
      const cipher = java('javax.crypto.Cipher').getInstance('AES/GCM/NoPadding')
      cipher.init(1, key)
      const StringClass = java('java.lang.String')
      const Base64 = java('android.util.Base64')
      const encrypted = {
        iv: String(Base64.encodeToString(cipher.getIV(), 2)),
        data: String(Base64.encodeToString(cipher.doFinal(new StringClass(token).getBytes('UTF-8')), 2)),
      }
      uni.setStorageSync(SECURE_KEY, JSON.stringify(encrypted))
      uni.removeStorageSync('refresh_token')
    } catch {
      throw new Error('安全存储不可用，无法保留登录会话，请使用网页版')
    }
  },
  clear(): void {
    uni.removeStorageSync('refresh_token')
    uni.removeStorageSync(SECURE_KEY)
  },
}

export function csrfCookie(): string {
  if (clientType() !== 'web' || typeof document === 'undefined') return ''
  const entry = document.cookie.split('; ').find((value) => value.startsWith('sw_csrf='))
  return entry ? decodeURIComponent(entry.slice('sw_csrf='.length)) : ''
}

export function beginWechatOAuth(appId: string): void {
  // #ifdef H5
  if (!appId || typeof window === 'undefined') throw new Error('未配置公众号登录')
  const bytes = new Uint8Array(24)
  window.crypto.getRandomValues(bytes)
  const state = Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('')
  sessionStorage.setItem('sw_oauth_state', state)
  const redirect = window.location.origin + '/#/pages/oauth-callback/index'
  window.location.assign('https://open.weixin.qq.com/connect/oauth2/authorize?appid=' +
    encodeURIComponent(appId) + '&redirect_uri=' + encodeURIComponent(redirect) +
    '&response_type=code&scope=snsapi_base&state=' + state + '#wechat_redirect')
  // #endif
}
