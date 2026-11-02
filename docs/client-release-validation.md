# 前端依赖与客户端发布验收记录

核验日期：2026-10-30（管理台依赖项 2026-11-01 复验）。所有 npm 元数据与 audit 均使用官方 `https://registry.npmjs.org`；不执行 `audit --force`，不忽略高危。

## 当前结果

| 项目 | 结果 |
| --- | --- |
| 主前端全量 npm audit | **0 high / 0 critical**，20 moderate 告警包（17 条 `@intlify/core-base` 链 + 3 条 `openapi-typescript` → `@redocly/openapi-core` → `minimatch` 链） |
| 主前端 npm audit --omit=dev | **0 high / 0 critical**，16 moderate 告警包 |
| 管理后台 npm audit | **0 vulnerabilities**（2026-11-01 起，`vue-tsc` 3.1.8 → `@vue/language-core` 3.1.8 已不再依赖 `minimatch`） |
| 剩余 advisory 实际来源 | 主前端来自 `@intlify/core-base`（DOM XSS 与参数转义）两条与 `minimatch` 的 globparts 放大 ReDoS。**均为 devDependency 传递依赖，不进入任何客户端产物** |
| 主前端 vue-tsc / 生成 API 类型 | 通过 |
| Web / 微信小程序 / Android 代码构建 | Node 22 下全部通过 |
| 前端单元测试 | 55 passed（会话/导航/小程序登录/帖子映射/Web 登录守卫/错误文案） |
| 管理后台单元测试 | 12 passed（认证与文件下载） |
| 管理后台类型检查与生产构建 | 通过；Element Plus 改按需引入后首屏 **JS 93.3KB gzip**（全量 JS 483.0KB gzip、echarts 懒加载块 174.9KB gzip），主 chunk 255KB raw，仍有较大 chunk 提示待拆分 |

原始审计输出在 `release/frontend-audit.json` 和 `release/frontend-audit-production.json`。这些数字是 npm 依赖图的告警包数，不能解读为独立漏洞数，也不能解读为已无发布风险。

## 2026-10-30 高危清零的实际处置

2026-10-16 的基线是 21 high，唯一直接来源为 braces 3.0.3。重新审计后官方 advisory 库给出了新的一批高危，需要分别处置：

| 旧高危 | 处置 | 现状 |
| --- | --- | --- |
| braces 3.0.3 栈耗尽 DoS（GHSA-vfj7-8cjw-p6xm / CVE-2026-93687） | **上游已撤回该 advisory**（GitHub 页面标题为 “Withdrawn Advisory”），npm advisory 库随之不再下发；braces 最新版仍是 3.0.3，**未发生版本变更** | npm audit 不再报告该条；依赖树中仍存在 braces 3.0.3（chokidar → braces、fast-glob → micromatch → braces） |
| vue-i18n / @intlify 逃逸与原型污染 | 移除**未被任何源码引用**的 `vue-i18n` 依赖（官方已标记 v9/v10 不再维护）；`@intlify/*` overrides 回调到 uni-cli-shared 自身锁定的 9.1.9 / 9.14.4（此前误锁到 9.14.5，恰是唯一受影响的版本） | 全部 high 清除 |
| body-parser 1.20.8 压缩体尾字节 DoS | overrides → `^1.20.9` | 清除 |
| follow-redirects 1.16.0 跨域凭证头泄露 | overrides → `^1.16.2` | 清除 |

管理后台同步修复：follow-redirects → `^1.16.2`，Vite 由 6.4.3 升到 6.4.5（launch-editor 系列漏洞），审计归零。

残余的 20 moderate 告警里，17 条来自 `@intlify/core-base` 的两条 advisory（GHSA-x8qp-wqqm-57ph DOM XSS 与 GHSA-8rc2-428q-7ww3 参数转义），该包只作为 `@dcloudio/uni-cli-shared`（devDependency）的传递依赖存在；另 3 条来自 `openapi-typescript` → `@redocly/openapi-core`（1.x 精确锁定 `minimatch@5.1.9`）。已实测 `dist/build/h5` 与 `dist/build/mp-weixin` 产物中不含 `vue-i18n`、`intlify` 或 `escapeParameterHtml` 任何字样，即不进入客户端。9.x 线内不存在同时避开两条 advisory 的版本（>=9.14.5 引入新的 high），跨大版本覆盖到 11.x 会破坏 uni-cli-shared 对 `@intlify/runtime@9.1.9` 的精确锁定，因此维持现状并在此记录，不伪造清零。

管理后台的 3 moderate 已于 2026-11-01 清零：`vue-tsc` → `@vue/language-core` → `minimatch` 的 globparts 放大 ReDoS（GHSA-g3hv-75wg-m249）。上游条件已兑现 —— `@vue/language-core` 自 3.0.2 起改用 `picomatch`，不再依赖 `minimatch`。管理台 `vue-tsc` 由 `^2.2.0` 升到 `~3.1.8`（连带 `@vue/language-core` 3.1.8、`@volar/language-core` 与 `@volar/typescript` 2.4.26），`minimatch` 连同 `brace-expansion`/`balanced-match`/`de-indent`/`he` 一并从依赖树移除，官方 npm audit 归零（0 vulnerabilities）。**未使用 `overrides` 强行覆盖**。

版本选择不是随手取的：`vue-tsc` 3.2/3.3 线对本仓库模板会误报（3.3.14 在属性值含 `//` 时报 `Property 'value' does not exist`，3.2.9 起报 `:initial-index` 的索引类型错），而 3.0.5 / 3.0.11 / 3.1.8 三版对本仓库均 0 错，故锁 `~3.1.8`（含 3.1.x 补丁，不跨到 3.2+）。管理台类型检查、生产构建、12 项单测与全视图走查 34/34 均在 `~3.1.8` 下复验通过，产物体积与基线一致（首屏 93.3KB gzip、echarts 块 174.9KB gzip、全量 JS 483.0KB gzip）。

解除门禁仍只能依据可复核结果：真实密钥与镜像扫描（Trivy/Gitleaks）、独立越权与隐私数据流复核、目标环境 CI 回归。禁止伪造版本、隐藏 audit，或把“只在构建时使用”视为自动批准。

## 已执行的兼容升级

DCloud 编译器及目标平台包统一到稳定版本 `3.0.0-5020620260917001`（编译器 5.26）。仅保留用户指定 Web、微信小程序、Android 平台，移除未使用的其他小程序、鸿蒙及自动化依赖。安全修复覆盖 Babel7、Intlify9、WebSocket、PostCSS、JPEG、ZIP、Express4/qs/path-to-regexp、Cookie、source-map-js 等。

Vite 使用已修复的 7.3.7，esbuild 使用 0.25.12。DCloud 原始 peer 锁定旧 Vite，通过 npm overrides 明确替代；已在 Node22 实测三个代码目标构建。Vue 应用/编译器仍保留 DCloud 兼容的 3.4 分支；SSR renderer 工具依赖升级到 3.5.42，本项目未提供 SSR 构建/发布入口。升级后的真实 H5、微信运行时与原生 APK 集成仍须回归；静态构建不能证明全部运行时兼容。

类型工具使用 TypeScript5.9、vue-tsc3 与官方 openapi-typescript7.13；`npm run generate:api` 从 `release/openapi.json` 生成 `src/types/generated-api.ts`，登录、注册、找回密码、密码身份与学生证上传实际引用生成请求类型。后端接口变更应重新导出并生成，而非手改生成文件。

CI/本地编译要求 Node22.12+。Android 代码构建不生成签名 APK。

## 浏览器端走查（Playwright，2026-10-30）

新增两套覆盖脚本，作为「所有功能」的浏览器级回归：

- `frontend/scripts/all-pages-walkthrough.py`：遍历 `pages.json` 注册的全部 25 个页面 × 亮/暗双模式（50 个页面场景 + 主题切换断言），逐页校验路由可达、根节点非空、文档级横向溢出、可见文字裁切、WCAG AA 文字对比度、控制台错误与未处理异常。**57/57 通过**，0 控制台错误。
- `admin-frontend/scripts/all-views-walkthrough.py`：遍历管理台 router 的全部 17 个业务路由 × 1280 桌面 / 390 窄屏（34 个场景），追加管理台布局存在性与文字对比度断言。**34/34 通过**。
- 另有 15 套专项脚本（发布、图片上传、详情互动、登录守卫、桌面平板、看板、导航 SVG、各业务视图等）与 2 个永久审计脚本（`ui-contrast-audit.py` 客观缺陷扫描、`ui-perf-audit.py` 性能基线），已全部接入 CI。

对比度策略：正文按 WCAG AA（4.5:1，大字 3:1），输入占位符按 4.0:1（提示性文字）。判定**不写死色值**——静态守卫解析 `App.vue` 令牌的**实际色值**再计算对比度，品牌例外同样按 `--primary*` 令牌实际值识别，换品牌依然成立。当前**品牌既定例外为 0**：玫瑰红品牌色在亮暗两种底色下均已直接达 AA。

走查发现并已修复的真实缺陷：

- 夜间模式下 `.theme-dark` 只覆写背景令牌、未覆写字色，`verify` / `appeals` 页面继承亮色近黑文字、在纯黑底上不可见 → `.theme-dark` 补 `color: var(--text-1)`。
- 输入占位符使用 uni 默认 `#808080`（3.95:1）与 `--text-4 #8b98a5`（2.64:1）→ 新增 `--text-placeholder` 令牌并全局接管 uni 占位类，小程序端补 `placeholder-class="ph"`。
- 管理台沿用 Element Plus 默认语义色（success `#67c23a` / warning `#e6a23c` / danger `#f56c6c` / info `#909399`），标签文字对比度仅 2.0~3.1:1 → 保持色相压深一档（`#007a4d` / `#a85b00` / `#c93a3a` / `#536471`）。
- 管理台输入占位符沿用 Element Plus 默认 `#a8abb2`（白底仅 2.30:1）→ 覆写为亮 `#626d7a`（5.27:1）/ 暗 `#9b9296`（5.76:1）。
- 底栏激活标签用 `--primary` 压暗底仅 3.88:1（11.4px 小字需 4.5:1）→ 改用暗色下提亮的 `--primary-text`，并给底栏图标新增 `primary-dark` 变体使图标与文字同色。

## 外部验收仍待完成

- 正式域名 HTTPS、Cookie/CSRF、OAuth、Web Locks + BroadcastChannel 多标签刷新与退出、失效及回收流程的真实浏览器测试。缺少 Web Locks 或 BroadcastChannel 时自动 Cookie 刷新拒绝执行。
- 微信开发者工具及真机登录、拍照、媒体审核状态、认证/申诉/屏蔽与跨端配对回归。
- 与编译器版本匹配的 HBuilderX 签名 APK：合并 manifest、AndroidKeyStore、首次隐私同意前及拒绝后的权限/网络/SDK行为、目标 Android 版本回归。
- 私有 COS 实际版本/删除标记清理、复制/备份禁用、回滚孤儿与旧备份恢复实测，见 `docs/student-verification.md`。
- 真实运营主体、隐私政策域名与 SDK 清单、备案、微信类目资质和安卓商店审核。未实施上线或对外提交。
