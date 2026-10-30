<template>
  <image v-if="src" class="ui-icon" :src="src" :style="styleObj" mode="aspectFit" />
</template>

<script setup lang="ts">
/**
 * UiIcon —— 跨平台图标组件（SVG）
 *
 * 为什么不用 emoji：
 *   emoji 在各系统/微信里的字形不一致（缺 emoji 字体时退化成黑白方块），
 *   也无法随主题变色；SVG 线条图标在 H5 / mp-weixin / App 三端渲染一致。
 *
 * 为什么不用内联 <svg>：
 *   mp-weixin 不支持 <svg> 标签，但支持 <image> 引用 .svg，
 *   因此统一走 static/icons 下的 .svg 资源 + <image mode="aspectFit">。
 *
 * 颜色：SVG 的描边色固化在文件里，所以「换色」通过 tone 变体实现
 *   default 中性 #666666 / primary 品牌蓝 #1d9bf0 / inverse 反白 / danger 语义红
 *   like 点赞粉 #f918b6 / favorite 收藏深金 #b8860b（激活态图标的基色）
 */
import { computed } from 'vue'
import { ICONS, ICON_TONES } from '@/utils/icons'

export type IconTone = 'default' | 'primary' | 'inverse' | 'danger' | 'like' | 'favorite'

interface Props {
  /** 图标语义名，见 utils/icons.ts 的 ICONS */
  name: string
  /** 尺寸 rpx，默认 40 */
  size?: number
  /** 颜色（兼容旧调用）：映射到 tone，仅识别品牌色系 */
  color?: string
  /** 显式色调，优先于 color */
  tone?: IconTone
}

const props = withDefaults(defineProps<Props>(), {
  size: 40,
  color: '',
  tone: undefined,
})

/** 旧 color 参数 → tone 映射（SVG 无法用 CSS 直接染色，只能选变体） */
const COLOR_TONES: Record<string, IconTone> = {
  '#1d9bf0': 'primary',
  '#1a8cd8': 'primary',
  '#ffffff': 'inverse',
  '#fff': 'inverse',
  '#c93a3a': 'danger',
  '#f56c6c': 'danger',
}

const activeTone = computed<IconTone>(() => {
  if (props.tone) return props.tone
  if (props.color) return COLOR_TONES[props.color.toLowerCase()] ?? 'default'
  return 'default'
})

const src = computed(() => {
  const toned = ICON_TONES[props.name]?.[activeTone.value]
  if (toned) return toned
  return ICONS[props.name] ?? ''
})

const styleObj = computed(() => ({
  width: `${props.size}rpx`,
  height: `${props.size}rpx`,
}))
</script>

<style scoped>
.ui-icon {
  display: inline-block;
  flex-shrink: 0;
}
</style>
