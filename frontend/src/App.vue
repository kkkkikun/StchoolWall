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
/* ===== 鄂应墙设计令牌 · 主题B「X」白天/夜晚双模式 =====
   近乎复刻 X（Twitter）设计系统：X 蓝 #1d9bf0、胶囊控件、发丝分隔线、无弥散阴影。
   默认 = X Light（白底）；夜间 = X Lights out（纯黑），由 .theme-dark 覆写令牌。
   换肤入口：本文件 + uni.scss（亮色镜像）+ pages.json（亮色导航默认值）。 */
page {
  /* —— 品牌色（X Blue，全主题恒定） —— */
  --primary: #1d9bf0;            /* 主品牌色：X 蓝 */
  --primary-strong: #1a8cd8;     /* 深一档：按下态 */
  --primary-soft: rgba(29, 155, 240, 0.12);   /* 蓝色软底（标签/徽章） */
  --primary-text: #0d74ab;       /* 蓝色正文小字：白底 5.12:1 / 浅蓝底 4.52:1，达 WCAG AA */
  --primary-fill: #0d6fa5;        /* 蓝底白字填充面（主按钮/卡片）：白字 5.48:1，达 WCAG AA */
  --primary-fill-strong: #0a5f8f; /* 填充面渐变深端：白字 7.24:1 */
  --primary-fill-gradient: linear-gradient(135deg, #0d6fa5, #0a5f8f);
  --primary-badge: var(--primary-fill);  /* 徽章沿用填充面色 */
  --like: #f918b6;               /* X 点赞粉 */
  --favorite: #b8860b;           /* 收藏深金：白底 3.4:1，达 WCAG 非文本对比度 */
  --accent-warm: #00ba7c;        /* 点缀：X 转发绿 */
  --accent-warm-strong: #00a06a; /* 点缀深一档 */
  --accent-warm-fill: #00794f;    /* 绿底白字填充面：白字 5.46:1，达 WCAG AA */
  --accent-warm-fill-strong: #00663f;
  --accent-warm-text: var(--accent-warm-fill);   /* 绿色标签文字：浅绿底 4.87:1，达 WCAG AA */
  --accent-warm-soft: rgba(0, 186, 124, 0.12);   /* 绿色标签底 */
  --primary-gradient: linear-gradient(135deg, #1d9bf0, #1a8cd8);
  --hero-gradient: linear-gradient(160deg, #1d6aa8 0%, #1d9bf0 115%);
  --soft-gradient: linear-gradient(135deg, rgba(29, 155, 240, 0.16), rgba(0, 186, 124, 0.12));
  --card-gradient: linear-gradient(180deg, #ffffff, #ffffff);
  --shimmer-gradient: linear-gradient(90deg, #f7f9f9 25%, #eff3f4 37%, #f7f9f9 63%);
  --primary-alpha: rgba(29, 155, 240, 0.5);

  /* —— 背景表面（X Light：全白 + 灰填充面） —— */
  --bg-page: #ffffff;            /* 页面底：纯白 */
  --bg-group: #ffffff;           /* 组局页：同白 */
  --bg-card: #ffffff;            /* 卡片：X 时间线行无卡底，弹层/区块用白 */
  --bg-card-2: #eff3f4;          /* 次级面：搜索框/分类胶囊填充（X 招牌灰） */
  --bg-input: #ffffff;           /* 输入框底 */
  --bg-disabled: #cfd9de;        /* 禁用面 */

  /* —— 文本（X Light 灰阶） —— */
  --text-1: #0f1419;             /* 主文本：X 近黑 */
  --text-2: #536471;             /* 次级：X 灰蓝 */
  --text-3: #536471;             /* 辅助/时间 */
  --text-4: #6b7684;             /* 占位/禁用：白底 4.62:1，灰底 4.13:1，达占位符 4.0:1 */
  --text-placeholder: #5f6b78;   /* 输入占位：在白底与 #eff3f4 灰底上均达 WCAG AA */
  --text-inverse: #ffffff;       /* 品牌色/深底上的文字 */
  --on-avatar: #1a2229;          /* 头像首字：深墨，全调色板最差 8.42:1 */

  /* —— 边框（X Light 分隔线） —— */
  --border-light: #eff3f4;       /* 发丝分隔线 */
  --border-strong: #cfd9de;      /* 控件描边 */
  --border-primary-soft: rgba(29, 155, 240, 0.4);

  /* —— 交互填充（X 悬停/按压灰） —— */
  --pill-bg: #eff3f4;            /* 胶囊/分段控件填充 */
  --pill-active-bg: #0f1419;     /* 胶囊激活底：黑 */
  --pill-active-text: #ffffff;   /* 胶囊激活字：白 */
  --hover-fill: rgba(15, 20, 25, 0.06); /* 行悬停/按压 */

  /* —— 横向滚动行渐隐（小程序不支持 mask，用覆盖层实现） —— */
  --scroll-fade-from: rgba(255, 255, 255, 0);
  --scroll-fade-to: #ffffff;

  /* —— 功能色（X 官方功能色板，全主题恒定） —— */
  --link: var(--primary-text);     /* 话题/链接：与蓝色正文同源，暗色自动跟随 */
  --info: #1d9bf0;
  --info-gradient: linear-gradient(135deg, #1d9bf0 0%, #1a8cd8 100%);
  --success: #00ba7c;
  --warning: #9a6700;            /* 警示/收藏文字：白底 4.87:1 */
  --warning-soft: rgba(255, 212, 0, 0.14);
  --danger: #f4212e;
  --danger-soft: rgba(244, 33, 46, 0.10);
  --danger-strong: #b42318;       /* 深一档语义红：小字在浅红底上达 WCAG AA（5.8:1） */
  --rank-2: #9a6700;             /* 榜单第 2 名（金）：白底 4.87:1 */
  --rank-3: #b45309;             /* 榜单第 3 名（铜）：白底 5.02:1 */
  --accent-violet: #7856ff;      /* X 紫 */
  --accent-violet-strong: #9a86ff;
  --accent-violet-soft: rgba(120, 86, 255, 0.14);
  --accent-blue-soft: rgba(29, 155, 240, 0.12);

  /* —— 圆角（胶囊控件是 X 的签名） —— */
  --radius-card: 16rpx;
  --radius-inner: 12rpx;         /* 卡内图：X 媒体圆角 */
  --radius-btn: 999rpx;          /* 全胶囊按钮 */
  --radius-tag: 4rpx;            /* 角标：近直角 */

  /* —— 阴影（X 无弥散阴影） —— */
  --shadow-card: none;
  --shadow-float: 0 8rpx 24rpx rgba(0, 0, 0, 0.08);
  --shadow-primary: none;
  --shadow-primary-lg: none;

  background-color: var(--bg-page);
  color: var(--text-1);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Helvetica Neue", Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji", sans-serif;
  font-size: 28rpx;
}

/* ===== 夜间：X Lights out（纯黑）令牌覆写 =====
   各页面根节点绑定 .theme-dark 后，整套令牌随子树切换。 */
.theme-dark {
  --primary-soft: rgba(29, 155, 240, 0.14);
  /* 子树文字色：page{} 继承的是亮色近黑字，暗底上会看不见，必须随主题覆写 */
  color: var(--text-1);

  --bg-page: #000000;            /* 纯黑 */
  --bg-group: #000000;
  --bg-card: #16181c;            /* X 深灰面 */
  --bg-card-2: #202327;          /* 搜索框/胶囊填充 */
  --bg-input: #000000;           /* 输入框黑底描边 */
  --bg-disabled: #2f3336;

  --text-1: #e7e9ea;             /* X 近白 */
  --text-2: #9aa4b0;             /* X meta 浅灰（高对比）：深底 7.03:1 */
  --text-3: #8c9299;             /* X 辅助灰：最差底(#172a3a) 4.68:1，达 AA */
  --text-4: #8c9299;             /* 占位/禁用：达 AA */
  --text-placeholder: #8b98a5;   /* 输入占位：深底上保持可读 */
  /* 暗色下蓝色文字必须提亮：深蓝在深底上不可读 */
  --primary-text: #4ba3e3;       /* 蓝色正文小字：全部暗底 ≥5.35:1 */

  --border-light: #2f3336;       /* X 分隔线灰 */
  --border-strong: #536471;      /* 控件描边 */

  --pill-bg: #202327;
  --pill-active-bg: #e7e9ea;     /* 夜间胶囊激活：近白底黑字 */
  --pill-active-text: #0f1419;
  --hover-fill: rgba(231, 233, 234, 0.06);

  --scroll-fade-from: rgba(0, 0, 0, 0);
  --scroll-fade-to: #000000;

  --accent-warm-text: #3fd6a0;   /* 绿色标签文字：暗绿底 7.21:1 */
  --accent-warm-soft: rgba(0, 186, 124, 0.16);

  --card-gradient: linear-gradient(180deg, #16181c, #16181c);
  --shimmer-gradient: linear-gradient(90deg, #16181c 25%, #202327 37%, #16181c 63%);
  --hero-gradient: linear-gradient(160deg, #0d3a5c 0%, #1d6aa8 60%, #1d9bf0 130%);
  --warning: #ffb020;             /* 暗底警示/收藏文字：深底 9.72:1 */
  --warning-soft: rgba(255, 212, 0, 0.10);
  --rank-2: #ffd400;             /* 暗底金：12.42:1 */
  --rank-3: #ffa552;             /* 暗底铜：9.10:1 */
  --danger-soft: rgba(244, 33, 46, 0.16);
  --danger-strong: #ff6b74;       /* 暗底上的浅红：深底文字对比度 6.1:1 */
  --accent-violet-soft: rgba(120, 86, 255, 0.16);
  --accent-blue-soft: rgba(29, 155, 240, 0.14);

  --shadow-float: 0 8rpx 24rpx rgba(0, 0, 0, 0.6);
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

/* ===== 输入占位统一走令牌 =====
   uni 默认占位色是 #808080（浅底 3.95:1 / 深底 3.99:1，均不达 AA），
   这里统一换成 --text-placeholder；小程序端通过 placeholder-class="ph" 生效。 */
.uni-input-placeholder,
.uni-textarea-placeholder {
  color: var(--text-placeholder);
}
.ph {
  color: var(--text-placeholder);
}

/* ===== 横向滚动行渐隐（全局） =====
   横向滚动的分类/筛选行在容器边缘会把胶囊从字形中间硬切，看起来像渲染坏了。
   小程序不支持 CSS mask，故用绝对定位的渐变覆盖层实现；配合 utils/scroll-fade.ts 使用。 */
.scroll-x-wrap {
  position: relative;
}
.scroll-x-fade {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 48rpx;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s ease;
}
.scroll-x-fade.show {
  opacity: 1;
}
.scroll-x-fade.left {
  left: 0;
  /* 左缘：靠近左端不透明、向右淡出 */
  background: linear-gradient(270deg, var(--scroll-fade-from), var(--scroll-fade-to));
}
.scroll-x-fade.right {
  right: 0;
  /* 右缘：靠近右端不透明、向左淡出 */
  background: linear-gradient(90deg, var(--scroll-fade-from), var(--scroll-fade-to));
}

/* H5：夜间同步 <html> 底色，滚动溢出区域不露白 */
/* #ifdef H5 */
html.theme-dark { background: #000000; }
/* #endif */

/* H5 框架默认导航（未设 navigationStyle: custom 的页面）返回键只有 26×26，
   扩到 40×40 满足最小点击区，箭头图形保持 26×26 不变 */
/* #ifdef H5 */
.uni-page-head-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* #endif */
</style>
