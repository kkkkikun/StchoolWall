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
      // 用户上传图由后端 :8000 的 /static 提供；子目录 = 上传 kind 全集
      // （与 backend/app/routers/upload.py UPLOAD_KINDS、deploy/nginx.schoolwall.conf 保持同步）
      // 这些子目录在 src/static 下不存在，不会劫持 uni 自带图标资源
      "/static/avatars": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/static/banners": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/static/posts": {
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
