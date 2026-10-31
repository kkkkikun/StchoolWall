# 本地验证与未完成验收

日期：2026-10-30。以下为本次工作区代码的实际检查结果，不代表已上线、已获准上架或已达到容量目标。现有用户界面改动保留；未部署生产或向平台提交审核。

## 已执行

| 检查 | 结果与范围 |
|---|---|
| 后端完整pytest回归 | **529 passed / 156.13秒**，真实隔离PostgreSQL14.24和Redis6.0.16；包含业务、权限、会话、审核、媒体和并发约束。不是目标PostgreSQL15/Redis7环境。 |
| 最后登录/会话定向回归 | **28 passed / 13.74秒**，覆盖生成安全默认昵称、短会话、全历史刷新重放、显式配对、撤销、找回码、管理MFA等；与全量有重叠，不合并计数。 |
| 最后生产配置定向回归 | **18 passed / 1.55秒**，含拒绝长度足够但仍是CHANGE_ME/REPLACE示例值的JWT及指纹密钥。 |
| 最后学生证定向回归 | **20 passed / 6.68秒**，含独立同意、重复认领、到期、清理，以及COS版本/无版本对象/删除标记的模拟测试。最后两个测试晚于全量收集，单独记录；未使用真实学生资料或真实COS。 |
| 运维脚本回归 | **20 passed**，覆盖备份失败不清理、保留顺序、发布证据/回滚/迁移恢复/压测种子保护，以及可信代理真实ASGI来源IP与伪造转发头边界。 |
| 数据库迁移 | 空库到head、上一版本合成用户/微信身份/重复足迹迁移、downgrade一版后重新upgrade及alembic check通过；用户UUID保留、旧认证和原始个人资料清理、足迹留最新。 |
| 逻辑备份恢复 | 合成测试数据库dump并恢复到另一个隔离数据库，核对成功；不是异机PITR、灾难切换或RPO/RTO演练。 |
| API契约 | 最终后端OpenAPI校验通过，**124 paths**；快照release/openapi.json，前端由openapi-typescript生成类型，认证/学生证请求实际引用。 |
| 主前端 | Node22独立运行时：类型检查、H5、微信小程序、Android代码构建通过；单元测试**55 passed**。未产出签名APK。 |
| 管理台 | 类型检查及生产构建通过；单元测试**12 passed**；有大chunk提示，仍需真实运行及加载性能检查。 |
| 依赖 | Python安装与pip check/pip-audit通过；**主前端官方npm audit 0 high / 0 critical**，管理台官方npm audit **0 vulnerabilities**。主前端残余17 moderate + 1 low 全部继承自 `@intlify/core-base` 一条构建期advisory，实测 H5 与微信小程序产物中不含该包。处置明细见[客户端验收记录](../client-release-validation.md)。 |
| 学生端全页面浏览器走查 | **53/53 通过**（`frontend/scripts/all-pages-walkthrough.py`）：`pages.json` 注册的全部26个页面 × 亮/暗双模式。逐页断言路由可达、根节点非空、文档级横向溢出、可见文字裁切、WCAG AA文字对比度、控制台错误与未处理异常；**0控制台错误**。 |
| 管理台全视图浏览器走查 | **34/34 通过**（`admin-frontend/scripts/all-views-walkthrough.py`）：全部17个业务路由 × 1280桌面 / 390窄屏，追加布局存在性与文字对比度断言。 |
| 既有专项走查回归 | 学生端6套（首页/发布/图片上传/详情/登录守卫/桌面平板）与管理台10套（看板/导航/帖子/举报/用户/评论/学生证/申诉/人工审核队列/布局）全部总体PASS。 |
| 前后端缺陷修复 | ① 夜间模式 `.theme-dark` 只覆写背景令牌、未覆写字色，`verify`/`appeals` 继承亮色近黑字在纯黑底上不可见；② 输入占位符使用 uni 默认 `#808080`（3.95:1）与 `--text-4`（2.64:1）；③ 管理台沿用 Element Plus 默认语义色，标签文字对比度仅2.0~3.1:1。三处均已修复，并由新增对比度断言长期守护。 |
| 图片顺序缺陷 | 发布页并发上传时 `media_ids` 的签发顺序 ≠ 用户选择顺序；后端 `bind_media` 用 `WHERE id IN (...)` 取数、`entity_media` 按 `created_at, id` 排序，用户排好的图片顺序在入库与发布环节丢失。已加 `media_assets.position` 列（迁移 `b7e2c4a91d30`）、`bind_media` 按传入顺序重排并落 position、`entity_media` 按 position 排序，并补后端回归测试与发布页 `data-media-id` 契约断言。**后端用例与迁移需 PostgreSQL 环境执行，本次未在本机运行。** |
| 图标体系 emoji → SVG | 全站 emoji 清零：`frontend/src`、`admin-frontend/src`、`backend/app` 扫描 **0 处** emoji。学生端 15 个页面 + `mock.ts` + 管理台 3 处全部改为 SVG；管理台 `route.meta.icon` 的 17 个 emoji 是死数据（侧边栏图标本就由 `AdminLayout` 的 Element Plus 组件提供），已删除该字段。学生端图标几何统一由 `frontend/scripts/gen_icons.py` 生成（**179 个 SVG / 87 个语义名**，含 default/primary/inverse/like/favorite 色调变体），产出 `frontend/src/utils/icons.ts` 注册表。浏览器实测 20 个页面共 **123 个图标全部加载成功、0 坏图**；H5 与微信小程序产物中 SVG 资源均已就位。 |
| 小程序 SVG 兼容性 | 微信官方 `image` 组件文档明确支持 SVG 格式；项目图标统一用 `<image src="*.svg" mode="aspectFit">`，全部 SVG 不含 `<style>` 元素与百分比单位，符合官方限制。**未在微信开发者工具或真机实测**（本机无 devtools/真机），需按 `frontend/README-MP.md` §4 清单补验。 |
| 走查断言同步 | `post-detail-walkthrough.py` 的点赞/收藏断言原按 emoji 字形匹配，图标换成 SVG 后必然失败；已改为断言实际 SVG 资源路径（`heart-on.svg` / `heart.svg` / `star-on.svg` / `star.svg`），**33/33 通过**，断言未被削弱或删除。 |
| 顺带修复的布局缺陷 | ① 组局页分类胶囊被 flex 压缩导致分类名逐字竖排（经 A/B 对比确认该问题在改动前已存在，非本次引入）；② 发起组局页「地点（选填）」标签被压成两行。两处均已修复，并用「短文本不得被压缩换行」的通用检测复验全站 22 个页面，仅剩 2 处 textarea 多行占位符（属预期）。 |
| 账号登录/注册独立页 | 新增 `pages/auth/index`：品牌区 + 登录/注册下划线标签 + 胶囊输入 + 显示/隐藏密码 + 全宽胶囊主按钮 + 公众号微信登录 + 就地错误提示，取代原「我的」页的登录弹窗（弹窗模板/逻辑/样式与相关 import 已整体移除）。宽屏下表单最大宽度 480px 居中；暗色模式显示/隐藏密码图标按主题换变体（浅底用中性灰 5.7:1、深底用反白 15.8:1，均过非文本 3:1）。**走查断言同步**：`web-login-guard-walkthrough.py` 11/11 通过（防连点、在途模式锁、接口错误重试、网络中断重试、畸形响应加固、暗色渲染全部保留，断言未削弱）；`tests/web-login-guard.test.mjs` 重定向到真实生产源码 `src/pages/auth/index.vue`，14 个子用例全过（此前指向 mine 页的旧弹窗实现，逻辑搬迁后已失效）。 |
| 发布配置 | 两份GitHub workflow通过actionlint1.7.7；生产、备份、监控Compose静态配置校验通过；镜像manifest模板远端只读校验通过。未在本机Docker构建/扫描/启动；Gitleaks与Trivy均未在本地执行，CI保留硬门禁。 |
| 视觉与体验全量优化（对标 X） | 逐页看图 + 自动化客观缺陷扫描（`frontend/scripts/ui-contrast-audit.py`，25 页 × 亮/暗）驱动。**本轮最终复扫：真实对比度缺陷 0、点击区不足 0、小字号 0、横向裁切 0、文字裁切 0、坏图 0、横向溢出 0、源码静态扫描 0**；仅余 6 处品牌蓝既定例外（底栏激活标签 `#1d9bf0` 压白底 3.0:1，X 签名元素、图标本体达非文本 3:1，单独计数不阻断）。修复内容包括：① 新增 `--primary-fill`/`--primary-fill-gradient` 令牌承载白字填充面（白字 5.48:1），主按钮、组局卡片、登录、申诉、发布等一律改用，品牌蓝只保留给图标/下划线/描边等非文字强调；② 广告位 banner 底色由后台下发、不可控，改为图片位用 180° 暗化层、纯色位用 90° 暗化层，角标自带 `rgba(0,0,0,.6)` 深色底（此前浅粉/浅绿渐变上白字仅 1.85:1）；③ 组局页两个入口卡片此前都用蓝色渐变（类名 `card-orange` 与渲染不符、视觉无法区分），改为深蓝 + 深暖绿；④ 徽标字号下限统一 22rpx；⑤ 所有真实可点击控件点击区扩到 ≥32×32px（图标视觉尺寸保持不变）；⑥ 头像配色收敛到 `frontend/src/utils/avatar.ts` 单一来源；⑦ 横向滚动行加渐隐、消除 swiper 1px 漏出；⑧ 「我的」页未登录态不再展示个人内容 Tab，认证徽章改为图标徽章。**复验**：学生端全页面走查 55/55、详情互动 33/33、桌面/平板 16/16、发布 6/6、图片上传 10/10、登录守卫 11/11、管理台全视图 34/34 全部 PASS；前端单测 55/55、管理台单测 12/12；type-check 0 错；H5/微信小程序/Android 三端构建通过。性能基线：FCP 32–184ms、DCL 24–79ms、DOM 36–640 节点、184 张图 0 坏图、无 >300ms 慢资源、无横向溢出；H5 产物 1.8M，主 chunk 301KB（gzip 103KB）。 |
| 走查断言升级 | 走查与审计脚本不再写死色值：① `h5_mock_api.py` 新增 `read_element_contrast()`/`assert_element_contrast()`，按 alpha 合成后实测对比度并断言 ≥4.5:1；② 审计脚本沿祖先链合成实色层与线性渐变（按元素位置取渐变实际 alpha，底色未知处按最坏情况纯白取下界），可判定图片/渐变背景上的文字；③ 点击区以 Vue 的 `Symbol(_vei)` 事件监听判定真实可点击元素，替代按类名猜测，消除装饰图标与信息性文本误报；④ 横向滚动容器自带渐隐层的按设计内处理。 |

外部微信、腾讯审核与COS使用模拟边界或SDK形状验证；没有把第三方服务的实际调用、资质或真机行为记为通过。自动化检查不替代人工安全复核。

## 已知发布阻断

主前端官方npm audit：**0 high / 0 critical**（17 moderate + 1 low 告警包，继承自 `@intlify/core-base` 一条构建期advisory，产物中不含该包）；管理台官方npm audit：**0 vulnerabilities**。旧基线里的 braces3.0.3 告警（GHSA-vfj7-8cjw-p6xm）已由**上游撤回该 advisory**，npm 不再下发，braces 本身仍是最新版3.0.3、未发生版本变更；同期新披露的 vue-i18n/@intlify、body-parser、follow-redirects 高危已通过移除未使用的 vue-i18n、回调 @intlify overrides 至9.1.9/9.14.4、overrides body-parser→^1.20.9 与 follow-redirects→^1.16.2 全部清除。详细依赖链、原始报告与解除条件见[客户端验收记录](../client-release-validation.md)。不忽略扫描、不伪造依赖版本。

新增迁移 `b7e2c4a91d30`（media_assets 加 position）已校验 revision 图为单头、链长21、无悬挂引用；**未在真实库执行 upgrade/downgrade**，新增的媒体顺序后端用例也未执行（当前环境无 Docker / PostgreSQL / Redis）。

此外尚未取得：

- 实际主体/备案/社区类目与商店准入、正式隐私政策、SDK清单和可响应的支持渠道。
- 目标PostgreSQL15/Redis7完整CI，真实镜像与密钥扫描，独立越权/隐私数据流复核。
- 本次新增的媒体顺序后端用例与迁移 `b7e2c4a91d30` 尚未在真实隔离PostgreSQL上执行；需在测试库跑通后再勾选。
- 私有COS访问与所有副本删除、腾讯审核故障/额度/费用、进程杀死和真实依赖故障演练。
- 同一制品预发布、应用回滚、异机备份/PITR和真实告警确认；RPO≤1小时、RTO≤4小时仍是目标。
- 1万用户/10万帖/50万评论下100req/s30分钟、200req/s5分钟及8小时长稳，p95与5xx验收；当前不声称承载500在线。
- 正式HTTPS域名的浏览器多标签与跨端联调，微信真机、Android签名包/安装升级/Keystore及SDK隐私行为。
- Web按50→200→全校的真实试运营、平台审核。

完整状态见[交付状态](implementation-status.md)、[发布门禁](release-gates.md)、[证件删除验收](../student-verification.md)。各阶段未执行项保持未勾选，禁止填虚构报告绕过门禁。

## 复验入口

后端：按README设置独立*_test数据库与Redis13/14/15，执行python -m pytest -q；pytest会清理该测试数据。运维：python -m unittest discover -s scripts/tests -v。前端：Node22.12+下npm ci，generate:api、type-check、test、build:h5、build:mp-weixin、build:android；管理台type-check及build。两个前端分别执行官方npm audit。浏览器走查需 Playwright Chromium：先构建产物，再执行 `frontend/scripts/all-pages-walkthrough.py` 与 `admin-frontend/scripts/all-views-walkthrough.py`（另有各页面/视图的专项走查脚本）。迁移与恢复脚本只允许显式ACK的隔离库，见运行手册及CI。

本次临时测试数据库和依赖位于被忽略的.pytest_cache，不属于生产基础设施；回归结束后已关闭55432/56379专用测试进程，未修改开发或生产数据库；私有媒体和证件目录同样已排除版本管理。首次迁移需备份、维护窗口和全员重新登录；旧认证和原始姓名/学号清理不可由downgrade还原。