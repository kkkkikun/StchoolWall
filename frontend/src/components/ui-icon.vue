<template>
  <text class="ui-icon" :style="styleObj">{{ glyph }}</text>
</template>

<script setup lang="ts">
/**
 * UiIcon —— 跨平台图标组件
 *
 * 为什么用 Unicode/emoji 而不是内联 <svg>：
 *   mp-weixin 不支持 <svg> 标签，也不支持 <image> 引用 .svg。
 *   Unicode 符号 + emoji 经 <text> 渲染，H5 与 mp-weixin 行为一致，且零外部资源。
 *   分类/彩色图标用 emoji；需要随 currentColor 变色的线条图标（› ∨ + ✓ ‹ ☆ ♡ ☰ ▤）用纯符号。
 */
import { computed } from 'vue'

interface Props {
  name: string
  /** 字号 rpx，默认 40 */
  size?: number
  /** 颜色，对纯符号生效（emoji 自带颜色不受影响）；默认继承 */
  color?: string
}

const props = withDefaults(defineProps<Props>(), {
  size: 40,
  color: '',
})

const GLYPHS: Record<string, string> = {
  // 线条/符号图标（可被 color 着色）
  arrowRight: '›',
  arrowDown: '∨',
  arrowUp: '∧',
  back: '‹',
  plus: '＋',
  publish: '✚',
  check: '✓',
  star: '☆',
  starFill: '★',
  heart: '♡',
  heartFill: '♥',
  list: '☰',
  layers: '▤',
  // 彩色/语义图标（emoji）
  search: '🔍',
  share: '↗',
  favorite: '☆',
  like: '♡',
  comment: '💬',
  location: '📍',
  emoji: '😀',
  folder: '📁',
  mic: '🎤',
  // tab（单色字形，可随 color 变色：选中深黑/未选中浅黑；后续可换 static/tabbar/ 下的 SVG）
  home: '⌂',
  group: '♟',
  message: '✉',
  mine: '☻',
  // 品牌/运营
  signin: '🐵',
  ufo: '🛸',
  verify: '✅',
  hot: '🔥',
  notice: '📢',
  // 菜单
  shield: '🛡️',
  help: '❓',
  invite: '🎁',
  settings: '⚙️',
  about: 'ℹ️',
  contact: '📞',
  stats: '📊',
}

const glyph = computed(() => GLYPHS[props.name] ?? props.name)

const styleObj = computed(() => {
  const s: Record<string, string | number> = {
    fontSize: `${props.size}rpx`,
    lineHeight: 1,
  }
  if (props.color) s.color = props.color
  return s
})
</script>

<style scoped>
.ui-icon {
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
