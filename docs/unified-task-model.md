# Unified Task Model

## 任务不只是描述“怎么爬”

在反黑灰场景里，任务模型必须同时描述：

1. 从哪个平台获取线索
2. 采集哪类风险对象
3. 以什么输入条件和规则抓取
4. 结果进入哪个数据集或专题
5. 采集完成后要触发哪些信号提取与案件化流程

## 统一任务对象

```json
{
  "task_id": "tsk_xxx",
  "task_name": "XHS 灰产引流线索采集",
  "platform": "xhs",
  "entity_type": "content",
  "task_mode": "search",
  "scenario_type": "lead_diversion",
  "auth_profile": "default_cookie",
  "input_payload": {
    "keywords": ["兼职", "副业", "加V", "私聊"]
  },
  "filters": {
    "start_page": 1,
    "enable_comments": true
  },
  "storage_profile": {
    "save_option": "jsonl",
    "dataset_name": "xhs_lead_diversion_daily"
  },
  "analysis_profile": {
    "signal_extractors": ["risk_terms", "contact_points", "template_similarity"],
    "entity_targets": ["account", "content", "contact_point"],
    "case_target": "lead_diversion_watchlist"
  }
}
```

## 任务字段分组

### Base

- `task_name`
- `platform`
- `entity_type`
- `task_mode`
- `scenario_type`
- `enabled`

### Auth

- `login_type`
- `auth_profile`
- `cookies`

### Input

- `keywords`
- `specified_ids`
- `creator_ids`
- `product_ids`
- `watch_terms`

### Filters

- `start_page`
- `region`
- `price_range`
- `free_shipping`
- `personal_only`
- `time_window`

### Runtime

- `headless`
- `enable_comments`
- `enable_sub_comments`
- `rate_limit_profile`
- `evidence_capture`

### Output

- `save_option`
- `dataset_name`
- `case_target`
- `signal_extractors`
- `entity_targets`

## 模型目标

统一任务模型的重点不是“所有平台字段完全一样”，而是：

- 有统一外壳
- 允许平台专属字段扩展
- 任务创建时就知道它服务于哪类风险场景
- 分析层能直接接收“要抽哪些信号、沉淀哪些实体、归到哪个案件”

## 建议的场景枚举

建议优先内置的 `scenario_type`：

- `lead_diversion` 引流导流
- `gray_recruitment` 灰产招募
- `fraud_promotion` 欺诈推广
- `seller_risk` 卖家风险
- `product_risk` 商品风险
- `topic_watch` 主题监测
