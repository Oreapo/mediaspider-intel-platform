# 当前工作总结与待完成事项

生成日期：2026-06-30

本文基于当前工作区、`docs/development-plan.md`、README、部署文档以及关键代码/测试改动整理。当前工作树仍包含未提交变更，本文用于阶段复盘和后续排期参考。

## 一、当前总体状态

- 平台已经形成 FastAPI 后端、Vue 3 前端、SQLite 持久化、Docker 本地部署、基础 CI 和自动化测试的完整工作台骨架。
- 核心业务链路已经覆盖采集任务、数据集、分析任务、风险信号、风险实体、案件、证据包、报告、通知、审计和平台 Profile。
- 本轮改动重点集中在真实 MediaCrawler 接入、采集失败诊断与重试、采集后自动信号/分析、前端任务配置、i18n 完善、CI 检查和部署文档。
- 当前前端本地开发端口已调整为 `5200`，后端默认仍为 `8180`。

## 二、已完成工作

### 1. 部署与运行基础

- 已具备后端 Dockerfile、前端 Dockerfile、`docker-compose.yml`、Nginx 前端代理、环境变量模板和部署说明。
- `.env.example` 已补充 `MEDIASPIDER_FRONTEND_PORT`、`MEDIASPIDER_FRONTEND_URL`、`MEDIASPIDER_MEDIA_CRAWLER_COMMAND`、`MEDIASPIDER_MEDIA_CRAWLER_HOST_PATH` 等配置。
- 后端新增根路径 `/`，可返回 API 状态、前端地址、文档地址和健康检查地址。
- CORS 默认来源已覆盖 `http://127.0.0.1:5200` 和 `http://localhost:5200`。

### 2. 认证、角色与权限

- 已完成后端认证骨架、前端登录态保护、角色权限策略基础和前端菜单/操作入口控制。
- 已覆盖任务、案件等关键写操作的角色限制。
- 新增任务运行重试接口的权限验证，分析师无权重试，运营角色可访问对应操作。

### 3. 任务调度与运行队列

- 已完成后台 scheduler 基础、任务运行队列、同任务并发防重、全局并发上限、队列优先级、运行超时、失败重试记录和重启恢复。
- 已支持 pending 运行取消、运行中 MediaCrawler 子进程树终止、SQLite 原子抢占、心跳续租和过期恢复。
- 当前任务详情页可查看运行记录、运行日志、进度、诊断结果、关联数据集和失败建议。

### 4. MediaCrawler 深度接入

- `MediaCrawlerProcessRunner` 已支持外部 MediaCrawler 根目录配置、命令前缀覆盖、自动优先使用 `<MediaCrawler>/.venv`，无虚拟环境时回退到 `uv run`。
- 采集命令已支持平台、采集类型、登录方式、起始页、关键词/详情 ID/创作者 ID、保存格式、保存目录、评论开关、无头模式、评论数、并发数、代理参数和 Cookie。
- 诊断接口已覆盖未配置根目录、根目录缺入口、运行时缺失、交互登录与无头模式冲突、Cookie 脱敏、平台/任务字段校验等场景。
- 失败分类已增强，可识别配置错误、认证失败、浏览器运行时缺失、Python 依赖缺失、网络/代理/超时/存储等常见问题。
- 新增 `backend/scripts/run_mediacrawler.py` 作为兼容启动器，用于 Web 后端调用外部 MediaCrawler CLI。
- 新增 `backend/requirements-mediacrawler.txt`，精简 Web 采集运行所需依赖，避免引入原桌面 GUI 的 PySide6 相关依赖。

### 5. MediaCrawler 容器化覆盖

- 新增 `backend/Dockerfile.crawler`，用于构建包含 Chromium、中文字体、MediaCrawler 依赖和外部 MediaCrawler 代码的后端镜像。
- 新增 `docker-compose.crawler.yml`，通过 BuildKit additional context 复制外部 MediaCrawler 到 `/opt/mediacrawler`。
- 采集浏览器状态已规划为独立 `mediaspider-browser-data` volume，平台业务存储仍使用原有 storage volume。
- `docs/deployment.md` 已补充 crawler 覆盖文件启动方式和无桌面服务器使用说明。

### 6. 兼容旧 Crawler API

- 新增 `/api/crawler/start`、`/api/crawler/stop`、`/api/crawler/status`、`/api/crawler/logs`。
- 兼容 API 会把旧式 crawler payload 转换为平台采集任务并提交后台运行。
- 已支持 search/detail/creator 三类采集输入映射、登录方式、Cookie、无头模式、评论参数、保存格式和日志读取。
- 已新增 `backend/tests/test_crawler_compat_api.py` 覆盖启动、状态、日志和必填输入校验。

### 7. 采集后处理链路

- 采集成功后，输出文件会自动导入为数据集。
- 已把任务服务和信号服务、分析服务装配起来，采集成功后可按任务 `analysis_profile_json` 自动执行信号提取和分析任务创建。
- 运行结果中会记录 `dataset_ids`、`signal_ids`、`signal_failures`、`analysis_job_ids`、`analysis_failures`，便于追踪后续处理。
- 信号提取已增加幂等去重能力，同一数据集重复提取不会重复生成相同风险信号。
- 信号可记录来源 `task_run_id`，方便从风险信号追溯到具体采集运行。

### 8. 失败诊断与一键重试

- 新增 `POST /api/tasks/{task_id}/runs/{run_id}/retry`。
- 仅允许对失败且诊断标记为可重试的运行发起重试。
- 新运行会记录 `retry_of_run_id`、`retry_root_run_id`、`retry_attempt`，形成可追溯重试链路。
- 重试操作已写入审计日志，便于追踪操作者、来源运行和重试次数。
- 任务详情页已新增失败诊断区的一键重试按钮和重试来源展示。

### 9. 前端任务与设置体验

- 采集任务创建表单已补充认证 Profile、登录方式、保存格式、单条最大评论数、最大并发数、信号提取器和分析类型。
- 前端会按任务平台过滤可用 Profile，并排除不再支持新任务使用的 `state_file` Profile。
- 任务详情页已支持运行轮询、失败诊断、可重试状态、重试操作和重试链路显示。
- 设置页、日志审计页、任务页、任务详情页等关键页面文案和状态展示进一步迁移到 i18n。
- 通用 EmptyState 已接入语言包。

### 10. 国际化与 CI

- 前端已具备 `zh-CN`、`en-US` 两套语言包（繁体 `zh-TW` 已于 2026-07-01 移除，详见 `docs/lightweighting-audit.md`）。
- 已完成应用外壳、通用组件、路由标题、首页、任务、任务详情、数据集、信号、实体、案件、证据包、报告、日志审计、情报分析、设置、登录和使用说明等主流程文案迁移。
- 新增 `frontend/scripts/check-i18n.mjs`，自动检查三语 key 和占位符一致性。
- `frontend/package.json` 新增 `npm run check:i18n`。
- GitHub Actions 已接入前端 i18n 检查，CI 覆盖后端测试、i18n 字典检查和前端构建。

### 11. 文档与测试覆盖

- README、前端 README、部署文档、用户指南和开发计划已同步更新到当前端口、i18n 检查和 MediaCrawler 新接入方式。
- 新增 `docs/integrations/mediacrawler-cli.md`，记录后端调用外部 MediaCrawler CLI 的平台、采集类型、参数、输出文件和诊断契约。
- 后端测试已扩展覆盖任务重试、诊断分类、MediaCrawler 运行时选择、Profile 校验、信号幂等、采集后分析/信号链路、Crawler 兼容 API、Docker crawler overlay、端口配置和根路径响应。

## 三、待完成工作

### 1. 认证与权限继续产品化

- 完善真实多用户管理、用户/角色管理入口、Token 或 Session 生命周期、安全密钥轮换和生产环境认证默认策略。
- 继续补齐更细粒度的前后端权限矩阵，确保所有敏感操作都有一致的后端强校验和前端可见性控制。

### 2. 任务队列生产化

- 将当前有界后台工作队列升级为独立进程或外部任务队列，降低 Web 进程重启、扩容和长任务阻塞风险。
- 为自定义 crawler runner 统一实现 `cancel(run_id)` 契约，保证所有 runner 都能支持运行中终止。
- 继续验证多进程、多实例、SQLite 锁竞争和任务租约恢复在真实部署中的边界情况。

### 3. 存储与迁移

- 补齐 Postgres repository 或 ORM 适配。
- 引入数据库迁移版本管理，形成 JSON 到 SQLite 到 Postgres 的稳定升级路径。
- 完善备份、恢复、数据清理、归档和索引策略。
- 对迁移脚本做重复执行、部分失败恢复和大数据量场景测试。

### 4. MediaCrawler 真实环境验收

- 使用授权的真实 MediaCrawler checkout 完成端到端冒烟：创建 Profile、提交任务、真实采集、输出入库、自动信号提取、自动分析、失败诊断和重试。
- 分平台验证 `xhs`、`dy`、`ks`、`bili`、`wb`、`tieba`、`zhihu` 的 CLI 参数兼容性和输出格式。
- 明确 `qrcode`、`phone`、`cookie` 三类登录方式在本地、服务器和 Docker 环境中的操作边界。
- 对 Cookie 过期、验证码、频控、代理失败、浏览器缺失和依赖缺失等场景补充真实日志样本和诊断规则。
- `state_file` Profile 当前仅保留旧数据兼容，新任务应迁移到 Cookie 或交互登录方案。

### 5. 采集后分析能力深化

- 扩展自动分析类型和信号提取器配置，形成更清晰的平台默认模板。
- 将采集运行、数据集、信号、实体、案件之间的追溯关系做成更完整的前端导航。
- 对自动分析失败、部分成功、重复执行和异步排队增加更清晰的用户反馈。

### 6. 通知与审计增强

- 通知发送仍需加强生产级 SMTP/Webhook 配置、失败重试策略、模板管理、密钥保护和发送限流。
- 审计链路需要继续补齐数据变更历史、敏感配置变更、Profile 使用记录和更强的证据链不可抵赖设计。
- 日志中心可继续增加导出、保留策略和运行级别过滤。

### 7. 国际化收尾

- 继续排查零散页面内部文案、枚举、错误消息和后端返回消息，确保所有用户可见文本都能通过语言包展示。
- 做双语文案校对（zh-CN / en-US），统一领域术语。
- 补充语言切换后的端到端 UI 回归，避免布局溢出和占位符缺失。

### 8. 测试、CI 与发布流程

- 补齐前端组件测试和核心用户路径 E2E 测试。
- 扩展后端 API 回归测试到更多异常路径和真实存储模式。
- 补齐 Docker 镜像构建、发布、版本标记和可复现构建流程。
- 在合并前持续运行：
  - `.venv\Scripts\python.exe -m pytest backend\tests`
  - `npm --prefix frontend run check:i18n`
  - `npm --prefix frontend run build`
  - `docker compose -f docker-compose.yml -f docker-compose.crawler.yml up --build -d`

## 四、建议下一步优先级

1. 先跑完整本地验证，确认当前未提交改动全部通过后再提交。
2. 用真实 MediaCrawler checkout 做一次最小端到端采集验收，优先选择 Cookie + headless 的无人值守路径。
3. 把任务队列生产化方案定下来，明确是独立 worker、外部队列还是容器内多进程模型。
4. 补前端 E2E：创建 Profile、创建任务、运行采集、查看数据集、查看信号、重试失败运行。
5. 开始 Postgres 与迁移版本管理设计，避免后续数据规模扩大后再补成本过高。
