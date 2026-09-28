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
/* ===== 鄂应墙设计令牌 · 主题B「X · Lights out」 =====
   参考 X（Twitter）成熟设计语言：纯黑底、X 蓝 #1d9bf0、胶囊控件、发丝分隔线、无弥散阴影。
   换肤三件套：本文件 + uni.scss + pages.json。 */
page {
  color-scheme: dark;

  /* —— 品牌色（X Blue） —— */
  --primary: #1d9bf0;            /* 主品牌色：X 蓝 */
  --primary-strong: #1a8cd8;     /* 深一档：按下态 */
  --primary-soft: rgba(29, 155, 240, 0.14);   /* 蓝色浅底 */
  --like: #f918b6;               /* X 点赞粉 */
  --accent-warm: #00ba7c;        /* 点缀：X 绿（转发色） */
  --accent-warm-strong: #00a06a; /* 点缀深一档 */
  --primary-gradient: linear-gradient(135deg, #1d9bf0, #1a8cd8);
  --primary-gradient-rev: linear-gradient(135deg, #1a8cd8, #1d9bf0);
  --hero-gradient: linear-gradient(160deg, #0d3a5c 0%, #1d6aa8 60%, #1d9bf0 130%);
  --soft-gradient: linear-gradient(135deg, rgba(29, 155, 240, 0.20), rgba(0, 186, 124, 0.14));
  --card-gradient: linear-gradient(180deg, #16181c, #16181c);
  --shimmer-gradient: linear-gradient(90deg, #16181c 25%, #202327 37%, #16181c 63%);
  --primary-alpha: rgba(29, 155, 240, 0.5);

  /* —— 背景表面（Lights out 纯黑分层） —— */
  --bg-page: #000000;            /* 页面底：纯黑 */
  --bg-group: #000000;           /* 组局页：同纯黑 */
  --bg-card: #16181c;            /* 卡片：X 深灰面 */
  --bg-card-2: #202327;          /* 次级面：搜索框/悬停填充 */
  --bg-input: #000000;           /* 输入框底：X 式黑底描边 */
  --bg-disabled: #2f3336;        /* 禁用面 */

  /* —— 文本（X 灰阶） —— */
  --text-1: #e7e9ea;             /* 主文本：近白 */
  --text-2: #71767b;             /* 次级：X meta 灰 */
  --text-3: #71767b;             /* 辅助/时间 */
  --text-4: #4c4f52;             /* 占位/禁用 */
  --text-inverse: #ffffff;       /* 主按钮/蓝底上的文字 */

  /* —— 边框（X 分隔线灰） —— */
  --border-light: #2f3336;       /* 发丝分隔线 */
  --border-strong: #536471;      /* 控件描边 */
  --border-primary-soft: rgba(29, 155, 240, 0.4);

  /* —— 功能色（X 官方功能色板） —— */
  --link: #1d9bf0;               /* 话题/链接 */
  --info: #1d9bf0;
  --info-gradient: linear-gradient(135deg, #1d9bf0 0%, #1a8cd8 100%);
  --success: #00ba7c;
  --warning: #ffd400;
  --warning-soft: rgba(255, 212, 0, 0.10);
  --danger: #f4212e;
  --rank-2: #ffd400;             /* 榜单第 2 名 */
  --rank-3: #ff7a00;             /* 榜单第 3 名：X 橙 */
  --accent-violet: #7856ff;      /* X 紫 */
  --accent-violet-strong: #9a86ff;
  --accent-violet-soft: rgba(120, 86, 255, 0.16);
  --accent-blue-soft: rgba(29, 155, 240, 0.14);

  /* —— 圆角（胶囊控件是 X 的签名） —— */
  --radius-card: 16rpx;
  --radius-inner: 12rpx;         /* 卡内图：X 媒体圆角 */
  --radius-btn: 999rpx;          /* 全胶囊按钮 */
  --radius-tag: 4rpx;            /* 角标：近直角 */

  /* —— 阴影（X 无弥散阴影：发丝线代替） —— */
  --shadow-card: none;
  --shadow-float: 0 8rpx 24rpx rgba(0, 0, 0, 0.6);
  --shadow-primary: none;
  --shadow-primary-lg: none;

  background-color: var(--bg-page);
  color: var(--text-1);
  font-family: -apple-system, "Segoe UI", "PingFang SC", "Helvetica Neue", Helvetica, Arial, sans-serif;
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
