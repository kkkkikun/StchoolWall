<script setup lang="ts">
/** 头像：后端下发的 avatar_url 是相对路径，同源直接用即可。 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    src?: string | null
    nickname?: string
    size?: number
  }>(),
  { src: null, nickname: '', size: 40 },
)

/** 没有头像时用昵称首字兜底，避免出现空白方块。 */
const initial = computed(() => (props.nickname || '匿').slice(0, 1))
const style = computed(() => ({ width: `${props.size}px`, height: `${props.size}px`, fontSize: `${props.size / 2.4}px` }))
</script>

<template>
  <el-avatar v-if="src" :src="src" :size="size" fit="cover" :alt="nickname" />
  <el-avatar v-else :size="size" :style="style" class="sw-avatar-fallback">{{ initial }}</el-avatar>
</template>

<style scoped>
.sw-avatar-fallback {
  background: var(--sw-primary-soft);
  color: var(--sw-primary);
  font-weight: 600;
}
</style>
