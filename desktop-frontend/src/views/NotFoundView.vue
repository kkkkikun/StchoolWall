<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="sw-card sw-notfound">
    <p class="sw-notfound__code">404</p>
    <p class="sw-notfound__text">这个页面不存在</p>
    <el-button type="primary" @click="router.push({ name: 'feed' })">回到校园墙</el-button>
  </div>
</template>

<style scoped>
.sw-notfound {
  padding: var(--sw-space-6);
  text-align: center;
}

.sw-notfound__code {
  margin: 0;
  font-size: 56px;
  font-weight: 700;
  color: var(--sw-primary);
}

.sw-notfound__text {
  margin: var(--sw-space-2) 0 var(--sw-space-4);
  color: var(--sw-text-secondary);
}
</style>
