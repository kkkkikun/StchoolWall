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
/* ===== 鄂应墙设计令牌 · 主题A「校园清新」 =====
   薄荷绿 + 奶油白：校园手账感。大圆角、柔和绿晕阴影、清新渐变。
   换肤三件套：本文件 + uni.scss + pages.json。 */
page {
  /* —— 品牌色 —— */
  --primary: #33b381;            /* 主品牌色：头部/主按钮/激活态 */
  --primary-strong: #219a6b;     /* 深一档：角标/热标/按下态 */
  --primary-soft: #e8f7f0;       /* 品牌浅底：标签/胶囊背景 */
  --accent-warm: #8fdcb8;        /* 清爽点缀：渐变搭档（薄荷） */
  --accent-warm-strong: #6fcba2; /* 点缀深一档：渐变尾色 */
  --primary-gradient: linear-gradient(135deg, #2fae7e, #8fdcb8);
  --primary-gradient-rev: linear-gradient(135deg, #8fdcb8, #219a6b);
  --hero-gradient: linear-gradient(160deg, #a8e6cf 0%, #7fd4ab 45%, #62c99a 100%);
  --soft-gradient: linear-gradient(135deg, #e3f9ee, #c5f0dc);
  --card-gradient: linear-gradient(90deg, #f7fcfa, #ffffff);
  --shimmer-gradient: linear-gradient(90deg, #e8f2ed 25%, #f4faf7 37%, #e8f2ed 63%);
  --primary-alpha: rgba(33, 154, 107, 0.55);

  /* —— 背景表面 —— */
  --bg-page: #f5f9f6;            /* 页面底：奶油薄荷灰 */
  --bg-group: #f2faf5;           /* 组局页：更清爽的浅绿底 */
  --bg-card: #ffffff;            /* 卡片 */
  --bg-card-2: #eef3ef;          /* 卡内次级面：占位图/分段控件底 */
  --bg-input: #ffffff;           /* 输入框底 */
  --bg-disabled: #c2ccc6;        /* 禁用面 */

  /* —— 文本 —— */
  --text-1: #1f2d27;             /* 主文本：墨绿黑 */
  --text-2: #52655d;             /* 次级 */
  --text-3: #93a49c;             /* 辅助/时间 */
  --text-4: #b3c2ba;             /* 占位/禁用 */
  --text-inverse: #ffffff;       /* 品牌色/深底上的文字 */

  /* —— 边框 —— */
  --border-light: #e8efe9;       /* 常规发丝线 */
  --border-strong: #d7e2da;      /* 强分隔/控件描边 */
  --border-primary-soft: #cde9db;/* 品牌色浅描边 */

  /* —— 功能色 & 点缀 —— */
  --link: #1d9bf0;               /* 话题/链接 */
  --info: #3aa0d8;
  --info-gradient: linear-gradient(135deg, #3aa0d8 0%, #2a7fb8 100%);
  --success: #3cb878;
  --warning: #f5a623;
  --warning-soft: #fff6e6;
  --danger: #f26d6d;
  --rank-2: #f0a04b;             /* 榜单第 2 名 */
  --rank-3: #e3b94f;             /* 榜单第 3 名 */
  --accent-violet: #8a5cf5;
  --accent-violet-strong: #6b46d6;
  --accent-violet-soft: #f1ecfe;
  --accent-blue-soft: #e8f4fd;

  /* —— 圆角（清新主题整体加大一档） —— */
  --radius-card: 28rpx;
  --radius-inner: 20rpx;         /* 卡内图/嵌套元素 */
  --radius-btn: 48rpx;           /* 胶囊按钮 */
  --radius-tag: 8rpx;            /* 角标/小标签 */

  /* —— 阴影（绿晕，柔和弥散） —— */
  --shadow-card: 0 8rpx 20rpx rgba(47, 158, 108, 0.08);
  --shadow-float: 0 6rpx 24rpx rgba(31, 77, 55, 0.08);
  --shadow-primary: 0 4rpx 14rpx rgba(33, 154, 107, 0.22);
  --shadow-primary-lg: 0 12rpx 28rpx rgba(33, 154, 107, 0.24);

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
