import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

/**
 * 亮/暗双模式状态。
 *
 * 与学生端一致：暗色只覆写设计令牌（styles/tokens.css 的 .theme-dark），
 * 结构与组件不变。模式落在 <html> 的 class 上，全局令牌随子树生效，
 * 滚动溢出区域与 Element Plus 组件也一起切换。
 *
 * 读取与写入都做了容错：浏览器禁用 localStorage 时仍可正常切换。
 */
const THEME_KEY = 'sw_theme'

export const useThemeStore = defineStore('theme', () => {
  const dark = ref(false)

  /** 当前模式的中文名，用于设置页回显。 */
  const modeLabel = computed(() => (dark.value ? '深色模式' : '浅色模式'))

  function apply(): void {
    if (typeof document === 'undefined') return
    document.documentElement.classList.toggle('theme-dark', dark.value)
  }

  /** 从本地存储恢复模式，页面启动时调用一次。 */
  function init(): void {
    try {
      dark.value = localStorage.getItem(THEME_KEY) === 'dark'
    } catch {
      dark.value = false
    }
    apply()
  }

  function setDark(next: boolean): void {
    dark.value = next
    try {
      localStorage.setItem(THEME_KEY, next ? 'dark' : 'light')
    } catch {
      // 隐私模式下写入会失败：模式仍在本页生效，只是下次打开不记住
    }
    apply()
  }

  function toggle(): void {
    setDark(!dark.value)
  }

  return { dark, modeLabel, init, setDark, toggle }
})
