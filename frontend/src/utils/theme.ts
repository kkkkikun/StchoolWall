/**
 * 主题B「X」白天/夜晚双模式状态与切换
 *
 * - 默认亮色（X Light：白底 + #eff3f4 分隔线 + #0f1419 文字）
 * - 夜间为 X「Lights out」（纯黑 + #16181c 表面 + #2f3336 分隔线）
 * - 原理：App.vue 全局样式 page{} 定义亮色令牌，.theme-dark{} 覆写暗色令牌；
 *   各页面根节点绑定 themeClass，令牌随子树生效（H5 与 mp-weixin 通用）。
 *   H5 下额外在 <html> 上同步类名，保证滚动溢出区域底色一致。
 */
import { computed, ref } from 'vue'

export type ThemeMode = 'light' | 'dark'

const THEME_KEY = 'sw_theme_mode'

function readStored(): ThemeMode {
  try {
    return uni.getStorageSync(THEME_KEY) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

const mode = ref<ThemeMode>(readStored())

function applyNativeChrome() {
  const dark = mode.value === 'dark'
  try {
    uni.setNavigationBarColor({
      frontColor: dark ? '#ffffff' : '#000000',
      backgroundColor: dark ? '#000000' : '#ffffff',
    })
  } catch { /* 自定义导航页无原生导航栏，静默 */ }
  try {
    uni.setBackgroundColor({ backgroundColor: dark ? '#000000' : '#ffffff' })
  } catch { /* 忽略 */ }
  // #ifdef H5
  if (typeof document !== 'undefined') {
    document.documentElement.classList.toggle('theme-dark', dark)
  }
  // #endif
}

/** 设置主题模式（持久化 + 同步原生导航/窗口底色） */
export function setThemeMode(next: ThemeMode) {
  mode.value = next
  try {
    uni.setStorageSync(THEME_KEY, next)
  } catch { /* 忽略 */ }
  applyNativeChrome()
}

/**
 * 页面级主题绑定：模板根节点 :class="themeClass"
 * 页面 setup 时同步一次原生导航栏/窗口底色（pages.json 只能声明亮色默认值）
 */
export function useTheme() {
  applyNativeChrome()
  const themeClass = computed(() => (mode.value === 'dark' ? 'theme-dark' : ''))
  return { themeClass, mode, setThemeMode }
}
