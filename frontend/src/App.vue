<script setup lang="ts">
import { onLaunch, onShow, onHide } from "@dcloudio/uni-app";

onLaunch(() => {
  // 微信小程序：静默登录（H5 预览走我的页 dev-login，不在此处理）
  // #ifdef MP-WEIXIN
  import("@/api/auth").then(({ wxLoginAndStore }) => wxLoginAndStore());
  // #endif
});
onShow(() => {
});
onHide(() => {
});
</script>
<style>
/* ===== 鄂应墙设计令牌 · 主题B「夜间霓虹」 =====
   深夜蓝黑底 + 紫→青霓虹：玻璃拟态卡片、霓虹辉光、高对比文字。
   换肤三件套：本文件 + uni.scss + pages.json。 */
page {
  color-scheme: dark;

  /* —— 品牌色 —— */
  --primary: #7c5cff;            /* 主品牌色：头部/主按钮/激活态（电紫） */
  --primary-strong: #a78bfa;     /* 亮一档：深底上的强调文字/角标 */
  --primary-soft: rgba(124, 92, 255, 0.16);   /* 品牌浅底（暗色下为半透紫） */
  --accent-warm: #22d3ee;        /* 霓虹搭档：电青 */
  --accent-warm-strong: #0ea5e9; /* 点缀深一档：渐变尾色 */
  --primary-gradient: linear-gradient(135deg, #7c5cff, #22d3ee);
  --primary-gradient-rev: linear-gradient(135deg, #22d3ee, #7c5cff);
  --hero-gradient: linear-gradient(160deg, #312e81 0%, #6d28d9 50%, #0e7490 100%);
  --soft-gradient: linear-gradient(135deg, rgba(124, 92, 255, 0.28), rgba(34, 211, 238, 0.18));
  --card-gradient: linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.015));
  --shimmer-gradient: linear-gradient(90deg, #1c2030 25%, #262c40 37%, #1c2030 63%);
  --primary-alpha: rgba(124, 92, 255, 0.55);

  /* —— 背景表面（玻璃拟态分层） —— */
  --bg-page: #0f1219;            /* 页面底：深夜蓝黑 */
  --bg-group: #12151f;           /* 组局页：略紫夜色 */
  --bg-card: #171b26;            /* 卡片 */
  --bg-card-2: #202635;          /* 卡内次级面：占位图/分段控件底 */
  --bg-input: #1c2130;           /* 输入框底 */
  --bg-disabled: #2a3042;        /* 禁用面 */

  /* —— 文本 —— */
  --text-1: #e9ecf5;             /* 主文本：近白 */
  --text-2: #aab3c8;             /* 次级 */
  --text-3: #737e96;             /* 辅助/时间 */
  --text-4: #4d5670;             /* 占位/禁用 */
  --text-inverse: #ffffff;       /* 品牌色/深底上的文字 */

  /* —— 边框（半透霓虹发丝线） —— */
  --border-light: rgba(255, 255, 255, 0.07);
  --border-strong: rgba(255, 255, 255, 0.14);
  --border-primary-soft: rgba(124, 92, 255, 0.35);

  /* —— 功能色 & 点缀（霓虹系） —— */
  --link: #4cc2ff;               /* 话题/链接 */
  --info: #38bdf8;
  --info-gradient: linear-gradient(135deg, #38bdf8 0%, #0369a1 100%);
  --success: #34d399;
  --warning: #fbbf24;
  --warning-soft: rgba(251, 191, 36, 0.12);
  --danger: #fb7185;
  --rank-2: #fbbf24;             /* 榜单第 2 名 */
  --rank-3: #d4a437;             /* 榜单第 3 名 */
  --accent-violet: #a78bfa;
  --accent-violet-strong: #c4b5fd;
  --accent-violet-soft: rgba(167, 139, 250, 0.16);
  --accent-blue-soft: rgba(56, 189, 248, 0.14);

  /* —— 圆角 —— */
  --radius-card: 24rpx;
  --radius-inner: 16rpx;         /* 卡内图/嵌套元素 */
  --radius-btn: 44rpx;           /* 胶囊按钮 */
  --radius-tag: 6rpx;            /* 角标/小标签 */

  /* —— 阴影（深色投影 + 紫色辉光） —— */
  --shadow-card: 0 8rpx 24rpx rgba(0, 0, 0, 0.4);
  --shadow-float: 0 8rpx 28rpx rgba(0, 0, 0, 0.5);
  --shadow-primary: 0 4rpx 16rpx rgba(124, 92, 255, 0.35);
  --shadow-primary-lg: 0 12rpx 30rpx rgba(124, 92, 255, 0.4);

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
