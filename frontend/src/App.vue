<script setup lang="ts">
import { onLaunch, onShow, onHide } from "@dcloudio/uni-app";
import { wxLoginAndStore } from "@/api/auth";

onLaunch(() => {
  // 微信小程序：静默登录（H5 预览走我的页 dev-login，不在此处理）
  // #ifdef MP-WEIXIN
  wxLoginAndStore();
  // #endif
});
onShow(() => {
});
onHide(() => {
});
</script>
<style>
/* ===== 鄂应墙设计令牌 · 玫瑰红品牌 · 白天/夜晚双模式 =====
   主品牌沿用 main 分支的红色/粉色系（#ef8a97 家族），但主色下压到 #c2455c：
   原来的 #ef8a97 压白字只有 2.27:1，做不了实心按钮底；#c2455c 白字 4.88:1、
   白底文字 4.88:1，两端都达 WCAG AA。
   换肤入口：本文件 + uni.scss（亮色镜像）+ pages.json（导航默认值）。
   暗色由 .theme-dark 覆写令牌；小字用 --primary-text（随主题提亮），填充用 --primary。 */
page {
  /* —— 品牌色 —— */
  --primary: #c2455c;            /* 玫瑰红品牌色：白字 4.88:1 / 白底文字 4.88:1 */
  --primary-strong: #9b374a;     /* 深一档：按下态；白字 6.91:1 */
  --primary-soft: #fdf0f2;       /* 浅粉底：标签/胶囊背景 */
  --primary-text: #ad3649;       /* 品牌色小字：白底 6.18:1 / 浅粉底 5.56:1 */
  --primary-badge: #b23b50;      /* 玫底白字徽章：5.78:1 */
  --primary-fill: #c2455c;       /* 实心填充面（按钮/卡片）：白字 4.88:1 */
  --primary-fill-strong: #9b374a;/* 填充面深端：白字 6.91:1 */
  --primary-fill-gradient: linear-gradient(135deg, #c2455c, #9b374a);
  --primary-fill-gradient-rev: linear-gradient(135deg, #9b374a, #c2455c);
  --like: #c2255c;               /* 点赞玫红：白底 5.66:1 */
  --favorite: #8f6908;           /* 收藏深金：页底 4.71:1 / 卡底 5.01:1 */
  --accent-warm: #f7b8a6;        /* 暖色点缀（装饰用，不承载小字） */
  --accent-warm-strong: #f2a091; /* 暖色点缀深一档 */
  --accent-warm-fill: #b85c38;   /* 暖底白字填充面：5.28:1 */
  --accent-warm-fill-strong: #8f4a2d;
  --accent-warm-text: #8f4a2d;   /* 暖色标签文字：白底 6.59:1 */
  --accent-warm-soft: #fdf0f2;   /* 暖色标签底 */
  --primary-gradient: linear-gradient(135deg, #c2455c, #9b374a);
  --primary-gradient-rev: linear-gradient(135deg, #9b374a, #c2455c);
  --hero-gradient: linear-gradient(160deg, #e07a8a 0%, #c2455c 55%, #9b374a 120%);
  --soft-gradient: linear-gradient(135deg, #fdf0f2, #fbe8ec);
  --card-gradient: linear-gradient(180deg, #ffffff, #ffffff);
  --shimmer-gradient: linear-gradient(90deg, #faf6f7 25%, #fdf0f2 37%, #faf6f7 63%);
  --primary-alpha: rgba(194, 69, 92, 0.5);

  /* —— 背景表面 —— */
  --bg-page: #f7f8fa;            /* 页面底 */
  --bg-group: #fff9f5;           /* 组局页暖底 */
  --bg-card: #ffffff;            /* 卡片 */
  --bg-card-2: #f2f3f5;          /* 卡内次级面：占位图/分段控件底 */
  --bg-input: #ffffff;           /* 输入框底 */
  --bg-disabled: #ccc;           /* 禁用面 */

  /* —— 文本 —— */
  --text-1: #222222;             /* 主文本 */
  --text-2: #555555;             /* 次级：白底 7.46:1 */
  --text-3: #626d7a;             /* 辅助/时间：页底 4.96:1 / 卡底 5.27:1 / 灰底 4.75:1（原 #999999 仅 2.85:1） */
  --text-4: #626d7a;             /* 占位/禁用：页底 4.96:1 */
  --text-placeholder: #5f6b78;   /* 输入占位：白底 5.44:1 / 灰底 4.90:1 */
  --text-inverse: #ffffff;       /* 品牌色/深底上的文字 */
  --on-avatar: #1a2229;          /* 头像首字：深墨，全调色板最差 8.42:1 */

  /* —— 边框 —— */
  --border-light: #f0f0f0;       /* 常规发丝线 */
  --border-strong: #e5e6eb;      /* 强分隔/控件描边 */
  --border-primary-soft: #f6dfe3;/* 品牌色浅描边 */

  /* —— 交互填充 —— */
  --pill-bg: #eff3f4;            /* 胶囊/分段控件填充 */
  --pill-active-bg: #222222;     /* 胶囊激活底 */
  --pill-active-text: #ffffff;   /* 胶囊激活字 */
  --hover-fill: rgba(34, 34, 34, 0.06); /* 行悬停/按压 */

  /* —— 横向滚动行渐隐（小程序不支持 mask，用覆盖层实现） —— */
  --scroll-fade-from: rgba(247, 248, 250, 0);
  --scroll-fade-to: #f7f8fa;

  /* —— 功能色 —— */
  --link: var(--primary-text);   /* 话题/链接：与品牌小字同源，暗色自动跟随 */
  --info: var(--primary-text);
  --info-gradient: linear-gradient(135deg, #c2455c 0%, #9b374a 100%);
  --success: #00a870;
  --success-text: #007a4d;       /* 绿字：白底 5.40:1 */
  --warning: #8a5a00;            /* 警示/收藏文字：白底 5.93:1 */
  --warning-soft: #fff8e6;
  --danger: #d9374e;             /* 语义红：白底 4.66:1 */
  --danger-soft: rgba(217, 55, 78, 0.10);
  --danger-strong: #b42318;      /* 深一档语义红：小字在浅红底上达 AA */
  --rank-2: #8a6408;             /* 榜单第 2 名（金）：白底 5.37:1 */
  --rank-3: #a85836;             /* 榜单第 3 名（铜）：白底 5.10:1 */
  --accent-violet: #7856ff;      /* 紫罗兰点缀 */
  --accent-violet-strong: #6b46c1; /* 紫点缀深一档：页底 6.04:1，达 AA */
  --accent-violet-soft: rgba(120, 86, 255, 0.14);
  --accent-blue-soft: #eef4fb;

  /* —— 圆角 —— */
  --radius-card: 24rpx;
  --radius-inner: 16rpx;         /* 卡内图/嵌套元素 */
  --radius-btn: 44rpx;           /* 胶囊按钮 */
  --radius-tag: 6rpx;            /* 角标/小标签 */

  /* —— 阴影 —— */
  --shadow-card: 0 6rpx 18rpx rgba(194, 69, 92, 0.08);
  --shadow-float: 0 4rpx 20rpx rgba(0, 0, 0, 0.06);
  --shadow-primary: 0 2rpx 12rpx rgba(155, 55, 74, 0.18);
  --shadow-primary-lg: 0 10rpx 26rpx rgba(194, 69, 92, 0.24);

  background-color: var(--bg-page);
  color: var(--text-1);
  font-family: -apple-system, "PingFang SC", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 28rpx;
}

/* ===== 夜间模式：玫瑰暗色 =====
   子树文字色随主题覆写：page{} 继承的是亮色近黑字，暗底上会看不见。 */
.theme-dark {
  --primary-soft: rgba(194, 69, 92, 0.18);
  color: var(--text-1);

  --bg-page: #121012;            /* 页面底 */
  --bg-group: #121012;
  --bg-card: #1c191c;            /* 深灰面 */
  --bg-card-2: #242124;          /* 搜索框/胶囊填充 */
  --bg-input: #121012;
  --bg-disabled: #3a3437;

  --text-1: #ece7e9;             /* 近白 */
  --text-2: #a9a0a4;             /* 次级：深底 7.44:1 */
  --text-3: #9b9296;             /* 辅助灰：最差底(#1c191c) 4.93:1，达 AA */
  --text-4: #9b9296;             /* 占位/禁用 */
  --text-placeholder: #a89fa3;   /* 输入占位：深底上保持可读 */
  /* 暗色下品牌小字必须提亮：深玫红在深底上不可读 */
  --primary-text: #e07087;       /* 品牌色小字：深底 5.67:1 */
  --primary-badge: #c2455c;      /* 白字 4.88:1 */
  --like: #e0608f;
  --favorite: #d4a63a;

  --border-light: #322d30;
  --border-strong: #4a4447;

  --pill-bg: #242124;
  --pill-active-bg: #ece7e9;
  --pill-active-text: #121012;
  --hover-fill: rgba(236, 231, 233, 0.06);

  --scroll-fade-from: rgba(18, 16, 18, 0);
  --scroll-fade-to: #121012;

  --accent-warm-text: #e8a87f;   /* 暖色标签文字：深底达 AA */
  --accent-warm-soft: rgba(184, 92, 56, 0.18);
  --success-text: #3fd6a0;
  --warning: #e0a33a;             /* 暗底警示/收藏文字 */
  --warning-soft: rgba(255, 212, 0, 0.10);
  --rank-2: #d4a63a;             /* 暗底金 */
  --rank-3: #e09070;             /* 暗底铜 */
  --danger-strong: #ff7a86;       /* 暗底上的浅红 */
  --danger-soft: rgba(217, 55, 78, 0.18);
  --accent-violet-soft: rgba(120, 86, 255, 0.16);
  --accent-blue-soft: rgba(120, 86, 255, 0.10);

  --card-gradient: linear-gradient(180deg, #1c191c, #1c191c);
  --shimmer-gradient: linear-gradient(90deg, #1c191c 25%, #242124 37%, #1c191c 63%);
  --hero-gradient: linear-gradient(160deg, #7a2c3c 0%, #a83a4e 60%, #c2455c 130%);
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
html.theme-dark { background: #121012; }
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

/* 关掉 uni-app H5 框架的导航阴影图预加载：
   框架用 body:after 挂一个隐藏伪元素，3 秒后从 dcloud 公网 CDN
   （cdn.dcloud.net.cn/img/shadow-*.png）拉图。后果有三：
   ① 每次打开页面都多一次外网请求，首屏被第三方 CDN 拖住；
   ② CDN 不可达时浏览器控制台报 ERR_CONNECTION_CLOSED，
      会被客观缺陷扫描当成真实缺陷，走查随机挂掉；
   ③ 用户的 IP 与访问时间被泄漏给第三方。
   本项目导航一律自定义，用不到框架自带的阴影图，直接让伪元素不生成。
   选择器比框架的 body:after 多一层 html（0,0,3 > 0,0,2），
   不依赖样式加载顺序。 */
/* #ifdef H5 */
html body::after {
  content: none;
  animation: none;
}
/* #endif */
</style>
