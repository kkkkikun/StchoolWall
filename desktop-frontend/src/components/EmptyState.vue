<script setup lang="ts">
/** 空态占位。 */
withDefaults(defineProps<{ text?: string; hint?: string }>(), { text: '暂无内容', hint: '' })
</script>

<template>
  <div class="sw-empty">
    <p class="sw-empty__text">{{ text }}</p>
    <p v-if="hint" class="sw-muted">{{ hint }}</p>
    <slot />
  </div>
</template>

<style scoped>
.sw-empty__text {
  margin: 0 0 var(--sw-space-2);
  font-size: var(--sw-text-base);
}
</style>
