# 电脑端对比度整改前后对照（2026-11-03）

对应 `openspec/specs/optimization/spec.md` 的「电脑端弱化文字、占位符与暗色品牌小字未达对比度规范」条目。

## 采集方式

- 产物：`desktop-frontend/` 执行 `npm run build:desktop`（base `/pc/`），静态服务由
  `desktop-frontend/scripts/walkthrough_server.py` 提供，接口由 `desktop-frontend/scripts/desktop_mock_api.py`
  夹具提供（只含假数据，无真实姓名与学号）。
- 浏览器：Playwright 自带 Chromium，视口 1440×900，主题由 `localStorage.sw_theme` 决定（亮色 / 暗色各跑一遍）。
- 场景：信息流 `/`、帖子详情 `/post/1`、登录 `/login`（未登录时 `/publish` 跳回登录页，两页截图一致）。
- `before/` = 基线提交 `fa129bc`（合并「电脑端三道门禁」后的 main）的产物；
  `after/` = 本分支（`agent/desktop-contrast-gates-38dbdc5546c4`）的产物。
  两次采集的脚本、视口、主题与页面顺序完全一致。
- 对比度数值取自 `desktop-frontend/scripts/ui-contrast-audit.py` 的同一套合成算法
  （祖先链实色层 + 线性渐变按元素位置取实际 alpha），不是目视估计。

## 图与实测对比度对照

| 图 | 元素 | 整改前 | 整改后 |
| --- | --- | --- | --- |
| `zoom-banner-light.png` | 轮播位白字压暗化层后的底色 | `#ffffff` on `#a9a9a9` = **2.35:1** | `#ffffff` on `#3f3f3f` = **10.53:1** |
| `zoom-banner-dark.png` | 同上（暗色底） | 改前未触发门禁 | `#ffffff` on `#07090b` = **19.94:1** |
| `zoom-post-light.png` | 卡片内品牌小字（话题标签） | `#c2455c` on `#ffffff` = 4.88:1 | `#ad3649` on `#ffffff` = **6.18:1** |
| `zoom-post-light.png` | 卡片内弱化文字（时间 / 计数） | `#8b949e` on `#ffffff` = **3.08:1** | `#626d7a` on `#ffffff` = **5.27:1** |
| `zoom-post-dark.png` | 卡片内品牌小字（话题标签 / 版块标签） | `#c2455c` on `#171b21` = **3.54:1** | `#e07087` on `#171b21` = **5.63:1** |
| `zoom-post-dark.png` | 卡片内弱化文字（时间 / 计数） | `#7d8792` on `#171b21` = 4.73:1 | `#8b949e` on `#171b21` = **5.62:1** |
| `login-light.png` | 搜索框 / 登录框占位符 | `#a8abb2` on `#ffffff` = **2.30:1** | `#626d7a` on `#ffffff` = **5.27:1** |
| `zoom-header-light.png` / `zoom-header-dark.png` | 顶栏（品牌链接、plain 主按钮、实心主按钮） | 品牌链接 4.34:1 / 3.54:1 | 品牌链接 6.18:1 / 5.63:1 |
| `feed-light.png` / `feed-dark.png` | 信息流整页（顶栏、侧栏、卡片、轮播位） | 亮暗两套配色合计 80 处未达 4.5:1 | 阻断项 0 条、观察项 0 条 |
| `post-detail-light.png` | 帖子详情整页（含评论区、字数统计） | 同上 | 同上 |

顶栏「注册」按钮（Element Plus plain 主按钮）落在品牌浅底上：亮色由 `#c2455c` on `#fdeef0` = **4.34:1**
改为 `#ad3649` on `#fdf6f7` = **5.79:1**，暗色由 `#c2455c` on `#341c22` = **3.22:1**
改为 `#e07087` on `#341c22` = **5.12:1**。

客观判定仍以 `desktop-frontend/scripts/ui-contrast-audit.py` 的报告为准
（`ci-artifacts/desktop-ui/contrast-audit.json`），截图只用于呈现视觉差异。
