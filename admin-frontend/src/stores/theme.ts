/**
 * 主题B「X」管理后台白天/夜晚双模式
 * 夜间 = X Lights out：Element Plus 官方 dark 机制（html.dark）+ theme.css 覆写
 * 状态持久化在 localStorage（sw_admin_theme），initTheme 在 main.ts 挂载前调用
 */
import { ref } from 'vue'

const KEY = 'sw_admin_theme'

const isDark = ref(
  typeof localStorage !== 'undefined' && localStorage.getItem(KEY) === 'dark',
)

function apply() {
  document.documentElement.classList.toggle('dark', isDark.value)
  try {
    localStorage.setItem(KEY, isDark.value ? 'dark' : 'light')
  } catch { /* 隐私模式等场景忽略 */ }
}

export function useThemeStore() {
  return { isDark, toggle: () => { isDark.value = !isDark.value; apply() } }
}

export function initTheme() {
  apply()
}
