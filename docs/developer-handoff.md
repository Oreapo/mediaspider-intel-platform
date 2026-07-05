# 开发交接文档

生成日期：2026-06-30

本文面向下一位接手开发者，目标是快速恢复上下文、理解当前代码状态，并能继续推进开发。当前仓库仍有未提交改动，请先确认工作树状态后再开始新任务。

## 1. 先读这些文档

建议按下面顺序阅读：

1. `docs/current-work-summary.md`：当前已完成工作、待完成事项和下一步优先级。
2. `docs/development-plan.md`：按阶段拆分的长期开发计划和验收标准。
3. `docs/integrations/mediacrawler-cli.md`：后端调用外部 MediaCrawler CLI 的参数契约。
4. `docs/deployment.md`：Docker、本地部署和 crawler overlay 启动方式。
5. `docs/user-guide.md`：从用户视角理解任务、数据集、信号、案件、设置页等主流程。
6. `README.md`：本地启动、测试和仓库结构。

## 2. 当前仓库状态

当前工作树包含一批未提交改动，主要集中在：

- MediaCrawler 深度接入和兼容 API。
- 采集失败诊断与一键重试。
- 采集成功后的自动数据集入库、信号提取、分析任务创建。
- 前端任务创建表单、任务详情重试入口、设置页和日志页 i18n。
- i18n 字典一致性检查脚本和 CI 接入。
- crawler 专用 Dockerfile、compose overlay 和部署文档。
- 后端测试覆盖扩展。
- 新增 `docs/current-work-summary.md` 和本文档。

接手前建议先执行：

```powershell
git status --short
git diff --stat
```

不要直接丢弃未提交改动；这些改动是当前开发进度的一部分。

## 3. 本地环境与启动

基础要求：

- Python 3.10 或更高版本。
- Node.js 20 或更高版本。
- Docker 可选，用于完整容器验证。
- 外部真实采集需要授权的 MediaCrawler checkout。

首次安装：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
npm --prefix frontend ci
Copy-Item .env.example .env
```

启动后端：

```powershell
.venv\Scripts\python.exe -m backend.app
```

启动前端：

```powershell
npm --prefix frontend run dev
```

默认地址：

- 前端：`http://127.0.0.1:5200`
- 后端 API：`http://127.0.0.1:8180`
- API 文档：`http://127.0.0.1:8180/docs`
- 健康检查：`http://127.0.0.1:8180/health`

## 4. 必跑验证命令

合并或交接前优先跑：

```powershell
.venv\Scripts\python.exe -m pytest backend\tests
npm --prefix frontend run check:i18n
npm --prefix frontend run build
```

如果本轮涉及容器或真实采集，再跑：

```powershell
docker compose up --build
docker compose -f docker-compose.yml -f docker-compose.crawler.yml up --build -d
```

`docker-compose.crawler.yml` 需要配置：

```text
MEDIASPIDER_MEDIA_CRAWLER_HOST_PATH=/absolute/path/to/MediaCrawler
```

## 5. 关键模块入口

### 后端应用入口

- `backend/app/main.py`
  - FastAPI app、CORS、路由注册、根路径和 health check。
  - 当前已注册 `crawler_router`。

- `backend/app/api/dependencies/container.py`
  - 应用容器和服务装配。
  - 负责读取存储、SQLite、MediaCrawler root、MediaCrawler command 等配置。
  - 将 `TaskService` 与 `SignalService`、`AnalysisService` 连接起来。

### 任务与采集

- `backend/app/api/routes/tasks.py`
  - 任务 CRUD、运行、取消、诊断、重试 API。
  - 新增 `POST /api/tasks/{task_id}/runs/{run_id}/retry`。
  - 任务创建/更新时会校验 `auth_profile_id` 是否存在、平台是否匹配、是否为不支持的 `state_file`。

- `backend/app/application/task_service/`（2026-07-01 由单文件拆分为包，公开类 `CollectionTaskService` 与导入路径不变）
  - `__init__.py`：`CollectionTaskService` 组合类（构造函数、并发/队列状态、公开属性）。
  - `_crud.py`：任务 CRUD。
  - `_run_queue.py`：运行队列、并发控制、取消、租约、后台 worker（最大的一块）。
  - `_retry.py`：重试、失败诊断复用、重试链路计数。
  - `_execution.py`：采集执行、结果入库、信号提取、分析任务创建（采集后管线）。
  - `_scheduler.py`：cron 调度匹配与窗口判断。
  - `_support.py`：跨模块共享的失败处理 / 进度 / 诊断 / auth profile 注入等底层辅助。

- `backend/app/application/crawler_runner.py`
  - `MediaCrawlerProcessRunner`。
  - 构建外部 MediaCrawler CLI 命令。
  - 诊断 MediaCrawler root、运行时、登录方式、headless 组合、Cookie 脱敏。
  - 管理运行中子进程和取消。

- `backend/scripts/run_mediacrawler.py`
  - Web 后端调用外部 MediaCrawler 的兼容启动器。
  - 当前会 patch 小红书登录快速检查，避免 UI-only 检查造成误判。

- `backend/app/api/routes/crawler.py`
  - 兼容旧 crawler API：`/api/crawler/start`、`/stop`、`/status`、`/logs`。
  - 会把旧 payload 转换为平台任务并提交后台运行。

### 平台 Profile

- `backend/app/application/platform_profile_service.py`
  - 平台登录 Profile 管理和诊断。
  - 当前 `state_file` 对新 MediaCrawler CLI 任务不再支持，只作为旧数据兼容保留。

- `frontend/src/views/SettingsView.vue`
  - Profile、通知规则、站内通知、投递记录、最近运行等设置页主流程。

### 信号与分析

- `backend/app/application/signal_service.py`
  - 数据集信号提取。
  - 当前已增加幂等去重和 `task_run_id` 追溯。

- `backend/app/application/analysis_service.py`
  - 分析任务创建与输出生成。

- `backend/app/application/task_service/_execution.py`
  - 采集成功后根据任务 `analysis_profile_json` 调用信号提取和分析任务创建。

### 前端任务页面

- `frontend/src/views/TasksView.vue`
  - 任务创建表单。
  - 当前已支持 Profile、登录方式、保存格式、评论参数、并发数、信号提取器、分析类型。

- `frontend/src/views/TaskDetailView.vue`
  - 运行记录、诊断、取消、重试、关联数据集和运行轮询。

- `frontend/src/api/tasks.ts`
  - 任务相关 API client。
  - 新增 `retryTaskRun`。

### 国际化

- `frontend/src/i18n/messages.ts`
  - 双语语言包（`zh-CN`、`en-US`；繁体 `zh-TW` 已于 2026-07-01 移除）。

- `frontend/scripts/check-i18n.mjs`
  - 校验所有 locale 的 key 和占位符一致。

- `.github/workflows/ci.yml`
  - 已接入 `npm run check:i18n`。

新增或修改前端可见文案时必须同步维护双语 key（`zh-CN`、`en-US`），并运行：

```powershell
npm --prefix frontend run check:i18n
```

## 6. 当前设计决策与约束

- 默认本地前端端口是 `5200`，不是旧的 `5173`。
- 后端即使没有配置 MediaCrawler root，也必须能正常启动；只有真实采集和诊断会提示未配置。
- 外部 MediaCrawler root 通过 `MEDIASPIDER_MEDIA_CRAWLER_ROOT` 配置。
- 可通过 `MEDIASPIDER_MEDIA_CRAWLER_COMMAND` 覆盖启动命令。
- Docker crawler overlay 使用 `MEDIASPIDER_MEDIA_CRAWLER_HOST_PATH` 作为 BuildKit additional context。
- MediaCrawler 自动入库目前只支持 `jsonl`、`json`、`csv` 输出。
- Cookie 必须脱敏，不能在诊断结果、日志、审计或前端直接展示原值。
- `qrcode` 和 `phone` 登录需要可见浏览器，不能与 `headless=true` 组合。
- 无人值守采集优先使用 Cookie Profile 和 `headless=true`。
- `state_file` Profile 当前不支持新任务调用 MediaCrawler CLI。
- 当前任务队列仍是进程内队列，已经做了 SQLite 租约和恢复，但生产级外部队列仍未完成。
- 当前默认生产化存储仍以 SQLite 为主，Postgres repository 和迁移版本管理尚未完成。

## 7. 当前最重要的未完成工作

### P0：验证并提交当前改动

1. 跑后端测试、i18n 检查、前端 build。
2. 修复测试或类型错误。
3. 用 `git diff` 快速复核敏感信息，尤其是 Cookie、真实账号、真实采集数据。
4. 提交当前工作。

### P0：真实 MediaCrawler 端到端验收

最小验收路径：

1. 配置真实授权的 MediaCrawler checkout。
2. 创建 Cookie Profile。
3. 创建 `xhs` search 任务，保存格式用 `jsonl`。
4. 运行采集。
5. 确认输出文件入库为数据集。
6. 确认自动生成信号。
7. 确认自动创建分析任务。
8. 在任务详情页确认运行记录、进度、日志和关联数据。
9. 制造一次可重试失败，验证一键重试和审计记录。

建议记录真实失败日志样本，继续完善 `_failure_diagnosis` 和 `_process_error_message`。

### P1：任务队列生产化

当前排队和执行仍在 Web 进程内。下一步需要决定：

- 独立 worker 进程。
- 外部队列，如 Redis/RQ/Celery。
- 容器内多进程模型。

需要重点关注：

- 任务幂等。
- 运行租约续期。
- Worker 崩溃恢复。
- 重试链路和审计一致性。
- 取消信号跨进程传递。

### P1：前端 E2E

优先覆盖以下核心路径：

1. 创建平台 Profile。
2. 创建采集任务。
3. 启动任务运行。
4. 查看任务详情和运行记录。
5. 查看自动入库数据集。
6. 查看自动提取信号。
7. 对失败运行执行重试。
8. 切换语言并确认页面无明显溢出。

### P1：Postgres 与迁移版本管理

当前已有 JSON/SQLite 迁移基础，但生产级方案还缺：

- Postgres repository 或 ORM 适配。
- 迁移版本管理。
- 重复执行安全性。
- 大数据量迁移性能验证。
- 备份、恢复和清理策略。

## 8. 测试地图

重点测试文件：

- `backend/tests/test_task_api.py`
  - 任务 CRUD、运行、诊断、重试、采集后信号/分析链路、MediaCrawler runner 行为。

- `backend/tests/test_crawler_compat_api.py`
  - 旧 crawler API 兼容层。

- `backend/tests/test_platform_profile_api.py`
  - Profile 创建、诊断、任务绑定和平台校验。

- `backend/tests/test_signal_api.py`
  - 信号提取、追溯和幂等。

- `backend/tests/test_frontend_config_contract.py`
  - 前后端配置契约、Docker crawler overlay、前端任务表单字段。

- `backend/tests/test_local_server_config.py`
  - 本地环境加载、相对路径解析、MediaCrawler command 解析。

- `backend/tests/test_auth_api.py`
  - 权限矩阵，包括重试接口权限。

- `backend/tests/test_health_api.py`
  - health 和根路径响应。

新增后端行为时，优先补对应 API 层测试和服务层边界测试。新增前端可见配置时，注意 `test_frontend_config_contract.py` 可能也要同步。

## 9. 常见问题排查

### 后端启动后提示 MediaCrawler root 未配置

这是允许的。普通平台功能应继续可用。只有真实采集诊断或运行会失败。配置：

```text
MEDIASPIDER_MEDIA_CRAWLER_ROOT=C:\path\to\MediaCrawler
```

### 诊断提示 MediaCrawler runtime unavailable

两种修复方式任选其一：

1. 在 MediaCrawler 目录创建 `.venv` 并安装 `backend/requirements-mediacrawler.txt`。
2. 安装 `uv`，让 runner 使用 `uv run python backend/scripts/run_mediacrawler.py`。

### qrcode/phone 登录无法 headless

这是预期限制。二维码和手机号登录需要可见浏览器。无人值守任务应使用 Cookie Profile。

### i18n 检查失败

通常是新增了某个 locale 缺 key，或 `{placeholder}` 名称不一致。修复 `frontend/src/i18n/messages.ts` 后重跑：

```powershell
npm --prefix frontend run check:i18n
```

### 前端仍访问 5173

当前默认端口已改为 `5200`。检查 `.env`、`frontend/vite.config.ts` 和浏览器缓存。

## 10. 代码风格与协作注意事项

- 先读现有模块模式，再按同一风格扩展。
- 不要把 Cookie、Token、真实账号、真实采集敏感内容提交到仓库。
- 不要把 `backend/storage` 中真实运行产生的大文件当作业务代码提交。
- 后端 API 错误要能被前端直接展示或翻译；用户可见文案尽量走语言包。
- 新增前端文案必须维护 `zh-CN`、`en-US`（繁体 `zh-TW` 已于 2026-07-01 移除）。
- 新增任务运行状态、枚举值或错误分类时，要同步前端展示、i18n、测试和文档。
- 修改任务队列、运行状态、取消、重试时要特别小心状态机，避免 active run 泄漏或重复执行。

## 11. 建议接手后的第一天计划

1. 读完本文和 `docs/current-work-summary.md`。
2. 跑 `git status --short` 和 `git diff --stat`，确认工作树。
3. 跑完整测试和前端 build。
4. 修掉当前失败项并提交。
5. 配置真实 MediaCrawler checkout，做最小端到端采集验收。
6. 把真实验收结果补进 `docs/current-work-summary.md` 或新增验收记录。
7. 根据验收结果决定先补诊断规则、E2E，还是推进任务队列生产化。
