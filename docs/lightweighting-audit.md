# 代码轻量化体检报告

生成日期：2026-06-30
状态：体检清单（未改动代码），供选择后再执行

> 目的：在不破坏功能的前提下，找出可安全删减的代码，按「减重量 / 风险」排序。
> 重量基线：前端 src 17,989 行 · 后端 app 13,578 行。

---

## 排序总览

| # | 项 | 预估减重 | 风险 | 建议 |
|---|---|---|---|---|
| A | 删 zh-TW（繁体）语言包，保留 zh-CN + en-US | **-1,117 行**（已执行） | 低 | ✅ 已完成（2026-07-01；主包 gzip 96.5→80.6KB） |
| B | 前端视图重复 helper 抽公共 | ~120 行 + 一致性 | 低 | ✅ 优先做（现为首选减重项） |
| C | 删 JSON 仓储层 | ~1,781 行 | **高** | ⚠️ 需先改默认+测试+迁移，单独立项 |
| D | 拆超大文件 | 0（不减行） | 低 | 可维护性，非减重 |
| E | 清理遗留面 | 待确认 | 中 | 先确认用量再删 |

---

## A. 删除 zh-TW（繁体）语言包 —— ✅ 已完成（2026-07-01）

> **结论：保留 zh-CN（简体）+ en-US（英文），删除 zh-TW（繁体）。** 主用户是中文使用者、简体即可；英文留作对外/演示。
>
> 已执行：`messages.ts` 移除 zh-TW 块（-1,117 行，3363→2246 行）；`Locale` 类型与 `localeOptions` 去掉 zh-TW；`useI18n.ts` 浏览器语言探测不再返回 zh-TW（繁体/HK 浏览器回落到简体）。主包体积 gzip 96.5→80.6KB。check-i18n 动态读 locale，无需改。

**删什么：**
- `messages.ts` 删除 `zh-TW`、`en-US` 两个 locale 块（约 -2,200 行）。
- `Locale` 类型缩成 `'zh-CN'`，`localeOptions` 只剩一项。
- `TheHeader.vue` 的语言切换下拉可整块移除（或保留单项占位）。
- `scripts/check-i18n.mjs` 从「跨 3 locale 校验一致性」简化为「单 locale 存在性」——脚本大半逻辑可删。

**风险：低。** 需先确认没有测试断言「3 个 locale」（`check:i18n` 输出里有 "3 locales"，要核对 `test_frontend_config_contract.py` 之类是否硬断言数量）。改完跑 check:i18n + build 即可验证。

**附带机会（需再扫一遍）：** 1095 个 key 里可能有**从未被 `t()` 引用的死 key**。方法：抽出所有 `'xxx.yyy':` key，逐个 grep `t('xxx.yyy'`/模板用法，无引用者删。可能再减几十～上百行。建议作为 A 的后续子任务。

---

## B. 前端视图重复 helper 抽成公共 —— 优先

**现状：** `labelValue` / `scenarioLabel` / `parseList` / `toStringList` / `datasetScenarioLabel` 这几个 4~6 行的小函数，在 **13 个视图里被复制了 22 次**（同一段 `const key = ...; const translated = t(key); return translated === key ? value : translated`）。

**删什么：**
- 新建 `composables/useEnumLabel.ts`（或 `lib/labels.ts`）导出 `labelValue` / `scenarioLabel` 等，13 个视图改为 import。
- 列表解析 `parseList`/`toStringList` 合并到 `lib/list.ts`。

**减重：** ~120 行，且修掉之前 /simplify 审查就点过的「12 处 labelValue 复制」一致性问题。**风险低**（纯重构，build 可验证）。

---

## C. 删 JSON 仓储层 —— 高价值但不是快切

**现状：** persistence 有 23 个文件；JSON 实现 **12 个 / 1,781 行**，SQLite **11 个 / 2,932 行**。

**为什么不能直接删：**
1. **JSON 是代码里的默认值**：`container.py` 中 `REPOSITORY_MODE` 未设时落到 `JsonXxxRepository`（`.env.example` 才把它设成 sqlite）。直接删会让默认配置启动即崩。
2. **多个测试直接用 JSON 仓储**：`test_scheduler_service.py`、`test_notification_api.py`、`test_local_server_config.py` 等。
3. **JSON 是「JSON→SQLite 迁移」的源**，删了迁移路径就断了。

**要做需先：** ① 把代码默认翻成 SQLite；② 重写/迁移依赖 JSON 的测试；③ 决定迁移脚本去留。**属于一次独立的存储治理，不建议当「顺手减重」做。**

---

## D. 拆分超大文件 —— 可维护性，非减重

- ~~`task_service.py` **1,421 行**~~ ✅ **已完成（2026-07-01）**：拆成 `task_service/` 包，6 个 mixin 文件按职责分离（`_crud` / `_run_queue` / `_retry` / `_execution` / `_scheduler` / `_support`），`__init__.py` 里的 `CollectionTaskService` 组合类保持公开接口和导入路径不变，调用方与测试零改动。185 个后端测试全绿验证。
- `signal_service.py` **835 行**、`notification_service.py` 594 行仍未拆，行数不会少，但单文件认知负担下降。属于「整理」不是「减重」，按需做。

---

## E. 待确认的遗留面（先查用量再删）

- **`state_file` 旧登录方式**：定位里已不支持新任务，只留旧数据兼容。若确认无存量数据依赖，相关校验/分支可删。
- **`xianyu` 平台特例**：CLI 不支持，散落 if 分支。若产品上不要，可连同枚举清掉。
- **旧 `/api/crawler/*` 兼容 API**（`crawler.py` + schema + 测试）：若没有旧客户端依赖，整层可删（约数百行）。
- **视图内重复 scoped CSS**：每个 view 重复 card/section/bar 样式，可抽全局，但偏成本/收益一般，谨慎。

---

## 建议执行顺序

1. **A + B 一起做**（低风险、合计减 ~2,300 行，且都与定位一致）→ 跑 check:i18n + build 验证。
2. 跑一次 **i18n 死 key 扫描**，把 A 的附带机会落实。
3. C / E 各自**单独立项**评估，不要混进快速减重。
4. D 视维护痛点再排。

> 注：每 5 分钟的自动开发循环（`ffcf66f9`）仍在运行，会持续加码。真正动手减重时建议先 `CronDelete ffcf66f9` 暂停，避免边减边加。
