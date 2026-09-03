import { defineConfig } from "vite";
import uni from "@dcloudio/vite-plugin-uni";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [uni()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      // 用户上传图（头像/横幅/组局图）由后端 :8000 的 /static 提供；
      // 这两个子目录在 src/static 下不存在，不会劫持 uni 自带图标资源
      "/static/avatars": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/static/banners": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/static/uploads": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/static/parties": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
