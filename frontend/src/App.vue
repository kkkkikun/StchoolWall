<script setup lang="ts">
import { onLaunch, onShow, onHide } from "@dcloudio/uni-app";

onLaunch(() => {
  console.log("App Launch");
  // 微信小程序：静默登录（H5 预览走我的页 dev-login，不在此处理）
  // #ifdef MP-WEIXIN
  import("@/api/auth").then(({ wxLoginAndStore }) => wxLoginAndStore());
  // #endif
});
onShow(() => {
  console.log("App Show");
});
onHide(() => {
  console.log("App Hide");
});
</script>
<style>
/* ===== 鄂应墙全局样式与设计 token ===== */
page {
  /* CSS 变量：供 <style>（非 scoped 也可）与行内 style 使用 */
  /* 2026-09-01 客户反馈：整体改推特式干净配色，亮色部分用偏淡粉色 */
  --brand-red: #ef8a97;      /* 主强调色：亮红 → 柔粉 */
  --brand-red-dark: #e26d7d; /* 徽标/标签：艳红 → 深一档玫瑰粉 */
  --brand-red-soft: #fdf0f2; /* 浅粉底 */
  --brand-orange: #f7b8a6;   /* 渐变搭档：橙 → 蜜桃粉 */
  --bg-page: #f7f8fa;
  --bg-group: #fff9f5;
  --radius-card: 24rpx;
  --radius-btn: 44rpx;
  --text-1: #222222;
  --text-2: #555555;
  --text-3: #999999;

  background-color: var(--bg-page);
  color: var(--text-1);
  font-family: -apple-system, "PingFang SC", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 28rpx;
}

/* ===== 通用工具类（对齐 ref/ 的 flex-row / flex-col / space-between） ===== */
.flex-row { display: flex; flex-direction: row; align-items: center; }
.flex-col { display: flex; flex-direction: column; }
.space-between { justify-content: space-between; }
.justify-center { justify-content: center; }
.text-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.text-clamp-2 {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

/* 全局 image 去除默认间隙 */
image { display: block; }
</style>
