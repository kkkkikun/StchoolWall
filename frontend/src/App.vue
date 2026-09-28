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
/* ===== 鄂应墙设计令牌 v2（语义化分层） =====
   换肤三件套：本文件 + uni.scss + pages.json，页面样式一律引用变量，不写死颜色。
   分层：品牌 → 背景表面 → 文本 → 边框 → 功能/点缀色 → 圆角 → 阴影 */
page {
  /* —— 品牌色 —— */
  --primary: #ef8a97;            /* 主品牌色：头部/主按钮/激活态 */
  --primary-strong: #e26d7d;     /* 深一档：角标/热标/按下态 */
  --primary-soft: #fdf0f2;       /* 品牌浅底：标签/胶囊背景 */
  --accent-warm: #f7b8a6;        /* 暖色点缀：渐变搭档 */
  --accent-warm-strong: #f2a091; /* 暖色点缀深一档：渐变尾色 */
  --primary-gradient: linear-gradient(135deg, #e8848f, #f6b8c0);
  --primary-gradient-rev: linear-gradient(135deg, #f6b8c0, #e26d7d);
  --hero-gradient: linear-gradient(160deg, #fbc6d0 0%, #f7a8bc 45%, #f2b8c8 100%);
  --soft-gradient: linear-gradient(135deg, #fce4ec, #f8bbd0);
  --card-gradient: linear-gradient(90deg, #fff7f8, #ffffff);
  --shimmer-gradient: linear-gradient(90deg, #f5e7ea 25%, #fdf0f2 37%, #f5e7ea 63%);
  --primary-alpha: rgba(226, 109, 125, 0.55);

  /* —— 背景表面 —— */
  --bg-page: #f7f8fa;            /* 页面底 */
  --bg-group: #fff9f5;           /* 组局页暖底 */
  --bg-card: #ffffff;            /* 卡片 */
  --bg-card-2: #f2f3f5;          /* 卡内次级面：占位图/代码块/分段控件底 */
  --bg-input: #ffffff;           /* 输入框底 */
  --bg-disabled: #ccc;           /* 禁用面 */

  /* —— 文本 —— */
  --text-1: #222222;             /* 主文本 */
  --text-2: #555555;             /* 次级 */
  --text-3: #999999;             /* 辅助/时间 */
  --text-4: #b9bcc2;             /* 占位/禁用 */
  --text-inverse: #ffffff;       /* 品牌色/深底上的文字 */

  /* —— 边框 —— */
  --border-light: #f0f0f0;       /* 常规发丝线 */
  --border-strong: #e5e6eb;      /* 强分隔/控件描边 */
  --border-primary-soft: #f2e7ea;/* 品牌色浅描边 */

  /* —— 功能色 & 点缀 —— */
  --link: #1d9bf0;               /* 话题/链接 */
  --info: #1296db;
  --info-gradient: linear-gradient(135deg, #1296db 0%, #0066cc 100%);
  --success: #07c160;
  --warning: #ffb822;
  --warning-soft: #fff9e6;
  --danger: #ff5c7a;
  --rank-2: #e8a23f;             /* 榜单第 2 名 */
  --rank-3: #d9b23f;             /* 榜单第 3 名 */
  --accent-violet: #8a5cf5;
  --accent-violet-strong: #6b46d6;
  --accent-violet-soft: #f1ecfe;
  --accent-blue-soft: #e6f3ff;

  /* —— 圆角 —— */
  --radius-card: 24rpx;
  --radius-inner: 16rpx;         /* 卡内图/嵌套元素 */
  --radius-btn: 44rpx;           /* 胶囊按钮 */
  --radius-tag: 6rpx;            /* 角标/小标签 */

  /* —— 阴影 —— */
  --shadow-card: 0 6rpx 18rpx rgba(239, 138, 151, 0.08);
  --shadow-float: 0 4rpx 20rpx rgba(0, 0, 0, 0.06);
  --shadow-primary: 0 2rpx 12rpx rgba(226, 109, 125, 0.18);
  --shadow-primary-lg: 0 10rpx 26rpx rgba(239, 138, 151, 0.24);

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
