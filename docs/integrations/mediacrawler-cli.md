# MediaCrawler CLI 接口契约

本文档记录当前后端 `MediaCrawlerProcessRunner` 对外部 MediaCrawler / MediaSpiderGUI 的调用契约。实际采集代码位于外部目录，通过 `MEDIASPIDER_MEDIA_CRAWLER_ROOT` 指向。

当前验证目录：

```text
C:\Users\K4m1to_2er02\Downloads\MediaSpiderGUI-main
```

该目录必须包含：

```text
main.py
pyproject.toml
cmd_arg/arg.py
media_platform/
```

## 启动命令

后端默认在 `MEDIASPIDER_MEDIA_CRAWLER_ROOT` 下执行：

```powershell
uv run python main.py [options]
```

如需替换命令前缀，可在测试或自定义 runner 中覆盖 `command_prefix`。

## 支持平台

外部 CLI 的 `PlatformEnum` 支持：

| 平台 | 参数值 |
| --- | --- |
| 小红书 | `xhs` |
| 抖音 | `dy` |
| 快手 | `ks` |
| Bilibili | `bili` |
| 微博 | `wb` |
| 贴吧 | `tieba` |
| 知乎 | `zhihu` |

当前后端只应对这些平台下发真实采集命令。`xianyu` 等平台可以作为平台配置存在，但不能调用该 MediaCrawler CLI。

## 采集类型

| 类型 | 参数值 | 后端来源 |
| --- | --- | --- |
| 搜索 | `search` | `task_mode=search`，需要 `task_payload_json.keywords` |
| 详情 | `detail` | `task_mode=detail`，需要 `task_payload_json.specified_ids` |
| 创作者 | `creator` | `task_mode=creator`，需要 `task_payload_json.creator_ids` |

`monitor` 任务运行时必须在 `runtime_payload_json.crawler_type` 或 `task_payload_json.crawler_type` 中指定 `search`、`detail` 或 `creator`。

## 后端下发参数

| CLI 参数 | 后端字段 | 说明 |
| --- | --- | --- |
| `--platform` | `task.platform` | 平台标识 |
| `--type` | `task.task_mode` / `crawler_type` | 采集类型 |
| `--start` | `filter_payload_json.start_page` 或 `runtime_payload_json.start_page` | 起始页，默认 `1` |
| `--keywords` | `task_payload_json.keywords` | 搜索关键词，逗号拼接 |
| `--specified_id` | `task_payload_json.specified_ids` | 详情 ID 或 URL，逗号拼接 |
| `--creator_id` | `task_payload_json.creator_ids` | 创作者 ID，逗号拼接 |
| `--save_data_option` | `storage_profile_json.save_option` | 后端可入库格式为 `jsonl`、`json`、`csv` |
| `--save_data_path` | 后端运行输出目录 | 每次运行独立目录 |
| `--get_comment` | `runtime_payload_json.enable_comments` | 默认 `true` |
| `--get_sub_comment` | `runtime_payload_json.enable_sub_comments` | 默认 `false` |
| `--headless` | `runtime_payload_json.headless` | 默认 `false` |
| `--max_comments_count_singlenotes` | `runtime_payload_json.max_comments_count_singlenotes` | 默认 `10` |
| `--max_concurrency_num` | `runtime_payload_json.max_concurrency_num` | 默认 `1` |
| `--enable_ip_proxy` | `runtime_payload_json.enable_ip_proxy` | 默认 `false` |
| `--ip_proxy_provider_name` | `runtime_payload_json.ip_proxy_provider_name` | 可选 |
| `--ip_proxy_pool_count` | `runtime_payload_json.ip_proxy_pool_count` | 可选 |
| `--cookies` | `runtime_payload_json.cookies` | 日志和诊断中必须脱敏 |

## 输出文件

后端当前会从 `--save_data_path` 下递归发现以下非空文件并导入为数据集：

```text
*.jsonl
*.json
*.csv
```

MediaSpiderGUI CLI 还支持 `sqlite`、`db`、`mongodb`、`excel`、`postgres` 等保存方式，但这些格式当前不进入后端数据集自动入库链路。生产任务应优先使用 `jsonl`。

## 运行前检查

后端诊断接口会检查：

- `MEDIASPIDER_MEDIA_CRAWLER_ROOT` 是否已配置。
- 目录下是否存在 `main.py`。
- 平台是否在 CLI 支持范围内。
- 不同采集类型所需字段是否齐全。
- Cookie 是否会被脱敏。

如果未配置 MediaCrawler，错误应为：

```text
MediaCrawler root is not configured. Set MEDIASPIDER_MEDIA_CRAWLER_ROOT to an authorized MediaCrawler checkout.
```

如果配置路径不存在入口，错误应为：

```text
MediaCrawler root not found: <path>
```
