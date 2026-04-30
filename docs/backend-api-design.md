# Backend API Design

## API 目标

后端不再只是提供“任务管理 + 分析结果”接口，而要支持完整反黑灰工作流：

1. 线索采集
2. 数据集沉淀
3. 风险信号提取
4. 实体与关系关联
5. 案件管理
6. 证据导出

## API 分层

建议继续按以下边界组织：

- `api/routes/`
- `application/services/`
- `domain/models/`
- `domain/repositories/`
- `infrastructure/persistence/`
- `analysis/`
- `ingestion/`
- `signals/`
- `entities/`
- `cases/`
- `evidence/`

## 顶层 API 分组

## `/api/dashboard`

用途：

- 首页概览
- 高风险主题统计
- 最新信号
- 待处理案件
- 平台状态

建议接口：

- `GET /api/dashboard/summary`
- `GET /api/dashboard/activity`
- `GET /api/dashboard/risk-overview`

## `/api/tasks`

用途：

- 采集任务 CRUD
- 启动 / 停止 / 调度
- 场景化任务模板
- 平台动态表单 schema

建议接口：

- `GET /api/tasks`
- `POST /api/tasks`
- `GET /api/tasks/{task_id}`
- `PATCH /api/tasks/{task_id}`
- `DELETE /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/start`
- `POST /api/tasks/{task_id}/stop`
- `GET /api/tasks/schema/platforms`
- `GET /api/tasks/templates/scenarios`

## `/api/task-runs`

用途：

- 查看任务运行历史
- 查看单次运行详情
- 查看单次运行产生的数据集与信号

建议接口：

- `GET /api/task-runs`
- `GET /api/task-runs/{run_id}`
- `GET /api/task-runs/{run_id}/logs`
- `GET /api/task-runs/{run_id}/datasets`
- `GET /api/task-runs/{run_id}/signals`

## `/api/datasets`

用途：

- 数据集列表
- 数据集抽样预览
- 数据集删除、归档、挂接案件

建议接口：

- `GET /api/datasets`
- `POST /api/datasets`
- `GET /api/datasets/{dataset_id}`
- `GET /api/datasets/{dataset_id}/preview`
- `POST /api/datasets/{dataset_id}/attach-case`
- `DELETE /api/datasets/{dataset_id}`

## `/api/signals`

用途：

- 风险信号列表
- 规则命中
- 风险评分
- 一键信号入案

建议接口：

- `GET /api/signals`
- `GET /api/signals/{signal_id}`
- `POST /api/signals/extract`
- `POST /api/signals/{signal_id}/attach-case`
- `PATCH /api/signals/{signal_id}/status`

## `/api/entities`

用途：

- 风险账号 / 卖家 / 商品 / 联系方式的统一管理
- 实体聚合与归并
- 实体详情和关系图谱

建议接口：

- `GET /api/entities`
- `GET /api/entities/{entity_id}`
- `GET /api/entities/{entity_id}/relations`
- `POST /api/entities/merge`

## `/api/cases`

用途：

- 案件列表
- 案件详情
- 线索、实体、数据集挂接
- 研判备注与结论

建议接口：

- `GET /api/cases`
- `POST /api/cases`
- `GET /api/cases/{case_id}`
- `PATCH /api/cases/{case_id}`
- `POST /api/cases/{case_id}/signals`
- `POST /api/cases/{case_id}/entities`
- `POST /api/cases/{case_id}/datasets`

## `/api/analysis`

用途：

- 触发通用风险分析
- 获取平台专属分析结果
- 获取跨平台关联分析结果

建议接口：

- `POST /api/analysis/jobs`
- `GET /api/analysis/jobs/{job_id}`
- `GET /api/analysis/jobs/{job_id}/outputs`
- `GET /api/analysis/platforms/{platform}`
- `GET /api/analysis/cross-platform`

## `/api/evidence`

用途：

- 生成证据包
- 下载证据导出文件
- 获取案件证据清单

建议接口：

- `POST /api/evidence/packets`
- `GET /api/evidence/packets`
- `GET /api/evidence/packets/{packet_id}`
- `GET /api/evidence/packets/{packet_id}/download`

## `/api/platforms`

用途：

- 平台能力声明
- 平台专属字段定义
- 平台专属信号提取能力声明
- 平台专属分析能力声明

建议接口：

- `GET /api/platforms`
- `GET /api/platforms/{platform}`
- `GET /api/platforms/{platform}/task-model`
- `GET /api/platforms/{platform}/signal-model`
- `GET /api/platforms/{platform}/analysis-model`

## WebSocket / SSE

建议保留：

- `/ws/task-runs/logs`
- `/ws/task-runs/status`
- `/ws/analysis/jobs`
- `/ws/signals/stream`
- `/ws/cases/alerts`

## 迁移建议

当前 `tasks / datasets / analysis` 最小骨架保留。  
下一阶段优先增加：

1. `signals`
2. `entities`
3. `cases`
4. `evidence`

不要先做大而全的仪表盘，先把案件化闭环打通。
