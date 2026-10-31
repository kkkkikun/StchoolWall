/**
 * 玫瑰红品牌白天/夜晚双模式状态与切换
 *
 * - 默认亮色（#f7f8fa 页底 + #ffffff 卡片 + #f0f0f0 分隔线 + #222222 文字）
 * - 夜间为暖玫瑰暗色（#121012 页底 + #1c191c 表面 + #322d30 分隔线）
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
      backgroundColor: dark ? '#121012' : '#ffffff',
    })
  } catch { /* 自定义导航页无原生导航栏，静默 */ }
  try {
    uni.setBackgroundColor({ backgroundColor: dark ? '#121012' : '#f7f8fa' })
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

/**
 * 只读主题模式（供全局组件使用）：不触发原生 chrome 副作用，
 * 供需要按主题切换静态资源的组件（如底栏激活图标变体）订阅。
 */
export function useThemeMode() {
  return mode
}
