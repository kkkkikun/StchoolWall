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
  --primary: #1f5c45;            /* 主品牌色：头部/主按钮/激活态（墨绿） */
  --primary-strong: #174a38;     /* 深一档：角标/热标/按下态 */
  --primary-soft: #edf2ef;       /* 品牌浅底：标签/胶囊背景 */
  --accent-warm: #2e7a5e;        /* 渐变搭档：浅一档墨绿 */
  --accent-warm-strong: #246249; /* 渐变尾色：深一档 */
  --primary-gradient: linear-gradient(135deg, #1f5c45, #2e7a5e);
  --primary-gradient-rev: linear-gradient(135deg, #2e7a5e, #1f5c45);
  --hero-gradient: linear-gradient(160deg, #1f5c45 0%, #2e7a5e 100%);
  --soft-gradient: linear-gradient(135deg, #edf2ef, #e3ebe6);
  --card-gradient: linear-gradient(90deg, #ffffff, #fdfcfa);
  --shimmer-gradient: linear-gradient(90deg, #eceae4 25%, #f5f4ef 37%, #eceae4 63%);
  --primary-alpha: rgba(31, 92, 69, 0.5);

  /* —— 背景表面 —— */
  --bg-page: #faf9f6;            /* 页面底：纸白 */
  --bg-group: #f7f5f0;           /* 组局页：米纸底 */
  --bg-card: #ffffff;            /* 卡片 */
  --bg-card-2: #f0eee8;          /* 卡内次级面 */
  --bg-input: #ffffff;           /* 输入框底 */
  --bg-disabled: #d8d5cd;        /* 禁用面 */

  /* —— 文本 —— */
  --text-1: #191919;             /* 主文本：墨黑 */
  --text-2: #4d4d4d;             /* 次级 */
  --text-3: #8c8c8c;             /* 辅助/时间 */
  --text-4: #b8b5ad;             /* 占位/禁用 */
  --text-inverse: #ffffff;       /* 品牌色/深底上的文字 */

  /* —— 边框（杂志细线框，本主题的灵魂） —— */
  --border-light: #e8e5dd;       /* 常规发丝线 */
  --border-strong: #d6d2c8;      /* 强分隔/控件描边 */
  --border-primary-soft: #cdd9d2;/* 品牌色浅描边 */

  /* —— 功能色 & 点缀（低饱和印刷色） —— */
  --link: #21694e;               /* 话题/链接：随品牌墨绿 */
  --info: #3a6b8a;
  --info-gradient: linear-gradient(135deg, #3a6b8a 0%, #2a4f68 100%);
  --success: #3d8b5f;
  --warning: #c07f2d;
  --warning-soft: #f7efdf;
  --danger: #b5442d;
  --rank-2: #c07f2d;             /* 榜单第 2 名 */
  --rank-3: #a98b2d;             /* 榜单第 3 名 */
  --accent-violet: #6b5f8f;
  --accent-violet-strong: #574d75;
  --accent-violet-soft: #eeecf3;
  --accent-blue-soft: #e9eff3;

  /* —— 圆角（近直角，印刷卡片感） —— */
  --radius-card: 8rpx;
  --radius-inner: 6rpx;          /* 卡内图/嵌套元素 */
  --radius-btn: 10rpx;           /* 方正按钮 */
  --radius-tag: 2rpx;            /* 角标/小标签 */

  /* —— 阴影（无弥散阴影：用 1px 发丝线描边代替） —— */
  --shadow-card: 0 0 0 1rpx var(--border-light);
  --shadow-float: 0 12rpx 28rpx rgba(25, 25, 25, 0.05);
  --shadow-primary: none;
  --shadow-primary-lg: 0 8rpx 20rpx rgba(25, 25, 25, 0.08);

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
