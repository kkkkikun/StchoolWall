import { describe, it, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { register } from 'node:module'
import { pathToFileURL } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

// 解析 hook：支持 '@/...' 别名、相对路径自动补 .ts
const aliasLoader = `
import { pathToFileURL } from "node:url";
import path from "node:path";
import fs from "node:fs";

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("@/")) {
    const resolved = path.resolve(process.cwd(), "src", specifier.slice(2));
    return nextResolve(pathToFileURL(withExt(resolved)).href, context);
  }
  if (specifier.startsWith(".") && !path.extname(specifier)) {
    const base = path.resolve(process.cwd(), path.dirname(context.parentURL.replace("file://", "")), specifier);
    return nextResolve(pathToFileURL(withExt(base)).href, context);
  }
  return nextResolve(specifier, context);
}

function withExt(target) {
  if (fs.existsSync(target)) return target;
  for (const ext of [".ts", ".js", ".mjs"]) {
    if (fs.existsSync(target + ext)) return target + ext;
  }
  if (fs.existsSync(path.join(target, "index.ts"))) return path.join(target, "index.ts");
  return target;
}
`
register('data:text/javascript,' + encodeURIComponent(aliasLoader), import.meta.url)

// 浏览器环境 mock：localStorage 与 <html> 的 class 列表
const store = new Map()
globalThis.localStorage = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, value) => store.set(key, value),
  removeItem: (key) => store.delete(key),
}
const classes = new Set()
globalThis.document = {
  // Vue 的运行时在加载时会取一次 document.createElement
  createElement: () => ({ setAttribute: () => {}, style: {}, children: [] }),
  documentElement: {
    classList: {
      add: (name) => classes.add(name),
      remove: (name) => classes.delete(name),
      contains: (name) => classes.has(name),
      toggle: (name, force) => {
        const next = force === undefined ? !classes.has(name) : force
        if (next) classes.add(name)
        else classes.delete(name)
        return next
      },
    },
  },
}

const { createPinia, setActivePinia } = await import('pinia')
const { useThemeStore } = await import('../src/stores/theme.ts')

describe('亮暗模式状态', () => {
  beforeEach(() => {
    store.clear()
    classes.clear()
    // Pinia 的 store 必须在激活实例下才能取用
    setActivePinia(createPinia())
  })

  it('默认是浅色模式，初始化后不挂暗色类名', () => {
    const theme = useThemeStore()
    theme.init()
    assert.equal(theme.dark, false)
    assert.equal(classes.has('theme-dark'), false)
    assert.equal(theme.modeLabel, '浅色模式')
  })

  it('切到深色时给 <html> 挂上 theme-dark 类名并持久化', () => {
    const theme = useThemeStore()
    theme.init()
    theme.setDark(true)
    assert.equal(theme.dark, true)
    assert.equal(classes.has('theme-dark'), true)
    assert.equal(store.get('sw_theme'), 'dark')
    assert.equal(theme.modeLabel, '深色模式')
  })

  it('再次初始化时从本地存储恢复深色模式', () => {
    store.set('sw_theme', 'dark')
    const theme = useThemeStore()
    theme.init()
    assert.equal(theme.dark, true)
    assert.equal(classes.has('theme-dark'), true)
  })

  it('toggle 在两种模式之间来回切换', () => {
    const theme = useThemeStore()
    theme.init()
    theme.toggle()
    assert.equal(theme.dark, true)
    theme.toggle()
    assert.equal(theme.dark, false)
    assert.equal(classes.has('theme-dark'), false)
  })
})
