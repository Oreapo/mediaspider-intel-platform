# 开发与修复待办清单（Backlog）

生成日期：2026-07-01
来源：汇总自 `product-positioning.md` 路线图、`lightweighting-audit.md`、`current-work-summary.md` 待完成项、`developer-handoff.md` 未完成项，以及本轮开发中发现的问题。

## 标记说明

- **[auto-ok]** — 小、低风险、不依赖外部资源或产品决策，自动循环可独立完成。
- **[needs-input]** — 需要你的决策 / API key / 真实环境 / 较大设计，自动循环应**跳过**，留给人。

> 自动循环规则：每轮只挑一个 **[auto-ok]** 的最小任务；改完跑 `pytest backend/tests`、`check:i18n`、`build` 验证；不自动 commit/push。

---

## ⚠️ 当前状态（2026-07-01，自适应循环第 11 轮）

**`[auto-ok]` 队列已清空——自动循环已达安全上限。** 连续多轮完成了：团伙聚合（端到端）、平台下钻（risk_levels + signal_types + 主导信号）、首页 hero 对齐风控态势、后端测试 179→185、删繁体 / helper 去重 / 空行清理。工作树累积约 90 个文件改动，**全部未提交**。

> 第 12 轮补漏：`enum.manual` 缺失 → 人工信号显示原值 "manual"，已补双语标签（人工 / Manual）。
> 第 14 轮补漏：实体类型（account/seller/contact_point 等）在团伙画像页显示英文原值，已补 7 个 `enum.*` 标签并改用 `labelValue`。**由此发现一条小任务流：本地化各页残留的原值枚举显示**（见下方 [auto-ok] 项），循环可继续消化。

**再往下没有「安全的小任务」了**：剩余全是需要你的 `[needs-input]` 大件。按循环规则，无安全小任务时循环只应空转/维护 backlog，不硬上大改动。

> 2026-07-01 追加：敏感信息复核已通过（无 Cookie/密钥/账号泄露），且完成了 `task_service.py` 拆分重构（mixin 包，185 测试全绿）。工作树改动持续累积、仍未提交。

**建议优先级（都需要你）：**
1. **审阅提交这批成果**（最紧要；工作树堆着没固化，含会话前那批可能有敏感信息，已复核过一轮但建议你自己再过一遍）。
2. 定一个大件方向：LLM 信号研判 / 证据包改名 / Postgres / 前端 E2E。
3. 真实 MediaCrawler 端到端验收（需授权环境）。

---

## P0 — 阻塞 / 基础（都需要人）

- **[needs-input]** 审阅并提交当前工作树（76 文件 / +2876−1486）。先用 `git diff` 扫敏感信息（Cookie / 真实账号 / 采集数据），再分组提交（见交接文档建议）。
- **[needs-input]** 真实 MediaCrawler 端到端验收：配置授权 checkout → 创建 Profile → 真实采集 → 入库 → 信号 → 分析 → 失败诊断/重试。需外部环境。

## P1 — 路线图核心（护城河：信号质量 + 团伙聚合）

- **团伙聚合**（核心价值：把分散信号按联系方式/群组收敛成团伙实体）
  - ~~**[auto-ok]** step1：后端 `SignalService` 增加 `cluster_by_contact(dataset_id)`，把含相同 `contact_point` / 群组的信号归为一组，返回分组结果 + 单元测试。~~ ✅ 已完成（2026-07-01）
  - ~~**[auto-ok]** step2：新增 API 端点 `GET /api/signals/clusters?dataset_id=` 暴露聚合结果 + 测试。~~ ✅ 已完成（2026-07-01）
  - ~~**[auto-ok]** step3：前端「团伙画像」页或信号页展示聚合分组。~~ ✅ 已完成（2026-07-01；线索研判页新增「团伙聚合」区块，按数据集展示候选团伙）
- **[auto-ok]（已降级）** 黑灰产场景默认提取器：~~数据集 `scenario_type ∈ {gray_recruitment, lead_diversion}` 时默认提取器纳入黑灰产提取器~~。**2026-07-01 评估：价值有限**——采集后管线要求任务显式配置提取器（`_extract_signals` 仅在 `signal_extractors` 非空时运行），场景默认只影响「手动 extract 且留空」的少数场景；若要真正生效需改管线逻辑，风险更高。留待与「采集后管线」一并设计。
- **[needs-input]** LLM 接入信号研判（招募话术/团伙识别）。需 API key + 设计，属大件。

## P1 — UI 一致性 / 体验

- ~~**[auto-ok]** 页面内部标题对齐新命名~~ ✅ 已完成（2026-07-01）。核查发现：列表页（线索研判/团伙画像/处置与案件/监测任务）**没有硬编码页内标题**，依赖路由/顶栏标题，已随 IA 改名生效；唯一不一致的是首页 hero（原「情报工作台」），已对齐为「黑灰产风险态势总览」+ 反黑灰产描述，双语维护。
- **[needs-input]** 品牌副标题 `app.subtitle`（现「情报分析平台」）是否改为「反黑灰产风控平台」——属整体产品命名，待你定。
- ~~**[auto-ok]** 本地化残留的原值枚举显示：逐页排查直接 `{{ item.xxx_type/status }}` 渲染原值的地方，补 `enum.*` 双语标签并改用 `labelValue`。~~ ✅ **基本完成**（2026-07-01）——信号类型/实体类型/案件类型/关系类型/运行状态/认证方式(auth_type) 全部本地化。剩余仅 `link_type`/`note_type`/DatasetDetailView `dataset_type` 等极边界值，价值可忽略。已完成：信号类型 `manual`、实体类型（account/seller/... 7 类）、案件类型 `case_type`（DashboardView + SignalDetailView 改用 `scenarioLabel`，与 CasesView 一致，复用已有 scenario 标签无需新 key）（2026-07-01）。关系类型 `relation_type`（系统值补标签）；**信号类型**（SignalsView/SignalDetailView/EntitiesView 3 处原值）、**实体类型**（TasksView）、**运行状态**（DashboardView 失败运行）—— 系统性排查后一批改用 `labelValue`（复用已有标签无新 key）（2026-07-01）。报告类型/状态、trigger_type 经核查已本地化。**主要枚举显示已覆盖**；剩余为技术性/边界值（`auth_type`、`link_type`、`note_type`、`DatasetDetailView` 的 `dataset_type`），价值低，视需要再补。
- ~~**[auto-ok]** 平台下钻深化：用已加的每平台 `risk_levels`，在平台对比卡或平台详情里展示「信号类型分布」（需后端在 `dashboard.py` 平台行补 `signal_types` 计数）。~~ ✅ 已完成（2026-07-01；后端补 `signal_types` 计数，前端平台卡展示「主导信号」）
- ~~**[auto-ok]** 清理重构后遗留的多余空行（如 `DatasetsView.vue` 去重处的双空行）。~~ ✅ 已完成（2026-07-01；13 个 view 文件的多余连续空行折叠为单空行）
- **[needs-input]** 整页重做首页为风控态势（大改版，需设计确认）。
- **[needs-input]** 「证据包 → 处置研判材料」改名（产品命名 + 广泛 i18n + 页面文案）。

## P1 — 减重 / 重构（lightweighting-audit C/D/E）

- ~~**[auto-ok]** D：拆分 `task_service.py`（1421 行）按职责分模块（run-queue / lease / retry / 采集后管线）。~~ ✅ 已完成（2026-07-01；拆成 mixin 包 `task_service/`，公开接口/导入路径不变，185 测试全绿）
- **[needs-input]** C：删 JSON 仓储层（1781 行）。需先把代码默认翻成 SQLite + 改依赖 JSON 的测试 + 定迁移去留，高风险，单独立项。
- **[needs-input]** E：清理遗留面（`state_file` 旧登录、`xianyu` 平台特例、旧 `/api/crawler/*` 兼容 API）。删前需确认无存量/外部依赖。

## P2 — 质量 / 基础设施

- **[auto-ok]（进行中）** 后端 API 异常路径回归测试扩展：逐个端点补边界/错误用例（404/409/校验失败等）。已覆盖：`/signals/clusters`（未知数据集→空、缺参/空参→422）、数据集级联删除（无 cascade→409，cascade→批量删信号）、任务重试运行不存在→404、取消运行不存在→404（2026-07-01）。Profile 平台校验错误路径经核查**已有覆盖**（missing/平台不匹配/state_file 拒绝，见 test_platform_profile_api）。**低垂的错误路径基本补齐**，剩余测试价值边际递减。
- **[needs-input]** 前端组件 / E2E 测试（需选型 vitest / playwright）。
- **[needs-input]** Postgres 仓储 + 迁移版本管理。
- **[needs-input]** 任务队列生产化（独立 worker / 外部队列）。
- **[needs-input]** 通知发送生产级（SMTP/Webhook 失败重试、模板管理、限流）。

---

## 自动循环可消化的 [auto-ok] 队列（建议顺序）

1. ~~团伙聚合 step1（后端服务 + 测试）~~ ✅ 完成
2. ~~团伙聚合 step2（API 端点 + 测试）~~ ✅ 完成（step3 前端展示需先加 `api/signals.ts` client + 「团伙画像」页区块）
3. 黑灰产场景默认提取器
4. ~~页面内部标题对齐（逐页）~~ ✅ 完成（列表页无硬编码标题；首页 hero 已对齐风控态势）
5. ~~平台信号类型分布（后端计数 + 前端展示）~~ ✅ 完成
6. ~~团伙聚合 step3（前端展示）~~ ✅ 完成 —— **团伙聚合 feature（step1-3）全部完成**
7. 后端异常路径测试扩展（逐端点）—— 进行中（已覆盖 `/signals/clusters`）
8. ~~拆分 task_service.py~~ ✅ 完成（2026-07-01；mixin 包重构，185 测试全绿）
9. ~~cosmetic 清理~~ ✅ 完成 —— **[auto-ok] 队列已全部清空**（剩余仅 [needs-input] 大件与边际测试）
