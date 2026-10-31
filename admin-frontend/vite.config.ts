import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需引入：只打包实际用到的 41 种 el-* 组件与样式，
    // 替代原来的 app.use(ElementPlus) + 全量 CSS（主 chunk 1.1MB / 首屏 411KB gzip）
    AutoImport({
      resolvers: [ElementPlusResolver()],
      dts: 'src/types/auto-imports.d.ts',
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'src/types/components.d.ts',
    }),
  ],
  resolve: {
    // tsconfig 的 paths 只对 vue-tsc 生效，vite 运行时必须显式配 alias
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5174,
    proxy: {
      '/api': 'http://localhost:8000',
      '/static': 'http://localhost:8000',
    },
  },
})
