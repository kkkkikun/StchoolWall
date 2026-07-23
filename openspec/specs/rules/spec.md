## Purpose

定义 SchoolWall 项目的编码规范与开发流程，整合三大规则体系（Karpathy Guidelines、务实编码原则、Workflow Designer），作为代码质量的唯一事实来源。CLAUDE.md 只做索引，规则全文以本文件为准。

> 版本：1.0 ｜ 最后更新：2026-07-06

## Requirements

### Requirement: Think Before Coding（Karpathy #1）

开发者 MUST 在编码前明确假设、暴露权衡，不假设、不隐藏困惑。

#### Scenario: 需求有多种解读

- **WHEN** 同一需求存在多种合理实现解读
- **THEN** 必须向用户全部呈现并询问，禁止 silently 选择其中一种

#### Scenario: 存在更简单方案

- **WHEN** 发现比用户设想更简单的方案
- **THEN** 必须主动说出并 push back，由用户决定是否采纳

### Requirement: Simplicity First（Karpathy #2）

实现 MUST 以最小代码解决问题，不添加未被要求的功能。

#### Scenario: 实现新功能

- **WHEN** 开发者实现新功能
- **THEN** 不添加未要求的"灵活性"或"可配置性"；单次使用的代码不抽象；不可能场景的错误处理不写；问自己"资深工程师会说这过度复杂吗"，是则简化

### Requirement: Surgical Changes（Karpathy #3）

改动 MUST 只触及必须改的部分，不"改进"相邻代码。

#### Scenario: 修改现有代码

- **WHEN** 开发者编辑现有代码
- **THEN** 不重构没坏的东西，匹配现有风格（即使自己做法不同）；注意到无关死代码只提及、不删除；改动产生的孤儿 import/变量必须清理，但先前存在的死代码不动；每行改动应能追溯到用户请求

### Requirement: Goal-Driven Execution（Karpathy #4）

任务 MUST 转化为可验证目标，循环直到验证通过。

#### Scenario: 接到任务

- **WHEN** 接到"修复 bug""添加验证""重构 X"类任务
- **THEN** 先转化为可验证目标（写复现测试→让它通过；写失败测试→实现至通过），多步任务先列计划并标注每步的 verify 检查

### Requirement: 命名即文档（务实 #1）

标识符 MUST 精准、可读、可搜索，揭示意图而非实现。

#### Scenario: 命名后端标识符

- **WHEN** 创建变量/函数/类/表字段
- **THEN** 名称揭示意图，避免缩写（循环计数器除外）；布尔值用 `is_`/`has_`/`can_` 开头（如 `is_verified`）；集合用复数；与业务术语一致

### Requirement: 函数单一职责（务实 #2）

函数 MUST 短小、只做一件事、无副作用。

#### Scenario: 编写或重构函数

- **WHEN** 编写后端 service 函数或前端方法
- **THEN** 理想 < 20 行，最多不超过一屏；只做一件事；不修改输入参数；抽象层级一致

### Requirement: DRY 与正交性（务实 #3）

代码 MUST 消除重复，模块保持独立（正交）。

#### Scenario: 出现重复代码

- **WHEN** 同一段逻辑复制出现两次
- **THEN** 第三次出现前必须抽象（三次法则）；一个模块的改动不应迫使其他无关模块改动；业务逻辑与基础设施（DB、Redis、存储）分离

### Requirement: 显式胜于隐式（务实 #4）

依赖 MUST 显式注入，避免全局状态与魔法值。

#### Scenario: 使用常量与依赖

- **WHEN** 代码中出现阈值、超时、重试次数等数值
- **THEN** 用命名常量（如 `MAX_RETRY_COUNT`）而非魔法数字；配置项走 `config.py` 的 `Settings`；依赖通过参数或 FastAPI Depends 注入，禁止隐式全局上下文

### Requirement: 可测试设计（务实 #6）

核心业务逻辑 MUST 可独立测试。

#### Scenario: 实现业务逻辑

- **WHEN** 实现核心业务逻辑（鉴权、审核、限流、存储）
- **THEN** 优先纯函数，依赖可注入便于 mock；按本项目测试体系（独立测试库 `ey_wall_test`、NullPool、每测试 TRUNCATE）补充测试，测试通过后再提交

### Requirement: 提交前自动化检查（务实 #9）

提交前 MUST 运行测试与类型检查并确认无新增警告。

#### Scenario: 准备提交

- **WHEN** 开发者完成代码变更
- **THEN** 后端运行 `python -m pytest` 全绿；前端运行 `npm run type-check` 无报错；确认无新增警告后才提交

### Requirement: 注释解释意图（务实 #10）

注释 MUST 只解释"为什么"，不注释"做什么"。

#### Scenario: 添加注释

- **WHEN** 编写注释
- **THEN** 注释解释非显而易见的决策（如"密码在此销毁以防落库"），不重复代码已表达的信息；过时注释立即更新或删除

### Requirement: Workflow 阶段与门控（Workflow Designer）

多步任务 MUST 按 Phase → Gate → Task → Loop 推进。

#### Scenario: 开始多步任务

- **WHEN** 任务涉及多文件、多阶段
- **THEN** 进入新 Phase 前必须 Gate PASS（检查项齐全）；Task 完成必须展示证据（命令输出/测试结果）；Gate BLOCK 必须记录原因；声明"完成"前必须验证证据

### Requirement: 安全与隐私铁律

本项目特有安全约束 MUST 被严格遵守，优先级最高。

#### Scenario: 接触密码或隐私字段

- **WHEN** 代码涉及教务系统密码、`real_name`、`wechat_id` 等敏感字段
- **THEN** 密码绝不持久化（不入库/日志/缓存）；`real_name` 不在 API 响应中暴露；日志中不得打印完整密码或敏感个人信息的明文
