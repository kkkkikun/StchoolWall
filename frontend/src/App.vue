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
  --like: #f918b6;               /* X 点赞粉 */
  --accent-warm: #00ba7c;        /* 点缀：X 转发绿 */
  --accent-warm-strong: #00a06a; /* 点缀深一档 */
  --primary-gradient: linear-gradient(135deg, #1d9bf0, #1a8cd8);
  --primary-gradient-rev: linear-gradient(135deg, #1a8cd8, #1d9bf0);
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
  --text-4: #8b98a5;             /* 占位/禁用 */
  --text-placeholder: #5f6b78;   /* 输入占位：在白底与 #eff3f4 灰底上均达 WCAG AA */
  --text-inverse: #ffffff;       /* 品牌色/深底上的文字 */

  /* —— 边框（X Light 分隔线） —— */
  --border-light: #eff3f4;       /* 发丝分隔线 */
  --border-strong: #cfd9de;      /* 控件描边 */
  --border-primary-soft: rgba(29, 155, 240, 0.4);

  /* —— 交互填充（X 悬停/按压灰） —— */
  --pill-bg: #eff3f4;            /* 胶囊/分段控件填充 */
  --pill-active-bg: #0f1419;     /* 胶囊激活底：黑 */
  --pill-active-text: #ffffff;   /* 胶囊激活字：白 */
  --hover-fill: rgba(15, 20, 25, 0.06); /* 行悬停/按压 */

  /* —— 功能色（X 官方功能色板，全主题恒定） —— */
  --link: #1d9bf0;               /* 话题/链接 */
  --info: #1d9bf0;
  --info-gradient: linear-gradient(135deg, #1d9bf0 0%, #1a8cd8 100%);
  --success: #00ba7c;
  --warning: #ffd400;
  --warning-soft: rgba(255, 212, 0, 0.14);
  --danger: #f4212e;
  --rank-2: #ffd400;             /* 榜单第 2 名 */
  --rank-3: #ff7a00;             /* 榜单第 3 名 */
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
  --text-2: #8b98a5;             /* X meta 浅灰（高对比） */
  --text-3: #71767b;             /* X 辅助灰 */
  --text-4: #71767b;             /* 占位/禁用 */
  --text-placeholder: #8b98a5;   /* 输入占位：深底上保持可读 */

  --border-light: #2f3336;       /* X 分隔线灰 */
  --border-strong: #536471;      /* 控件描边 */

  --pill-bg: #202327;
  --pill-active-bg: #e7e9ea;     /* 夜间胶囊激活：近白底黑字 */
  --pill-active-text: #0f1419;
  --hover-fill: rgba(231, 233, 234, 0.06);

  --card-gradient: linear-gradient(180deg, #16181c, #16181c);
  --shimmer-gradient: linear-gradient(90deg, #16181c 25%, #202327 37%, #16181c 63%);
  --hero-gradient: linear-gradient(160deg, #0d3a5c 0%, #1d6aa8 60%, #1d9bf0 130%);
  --warning-soft: rgba(255, 212, 0, 0.10);
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

/* H5：夜间同步 <html> 底色，滚动溢出区域不露白 */
/* #ifdef H5 */
html.theme-dark { background: #000000; }
/* #endif */
</style>
