# Docker 部署说明

本文档对应开发计划阶段 1，提供本地 Docker 部署方式。

## 1. 准备环境

需要安装：

- Docker
- Docker Compose

复制环境模板：

```powershell
Copy-Item .env.example .env
```

同一个根目录 `.env` 也可用于本地 Python 启动器和 Vite 开发服务器；Compose 会使用其中的
`MEDIASPIDER_BACKEND_PORT` 作为后端宿主机端口。

## 2. 启动服务

在项目根目录运行：

```powershell
docker compose up --build
```

启动后访问：

- 前端：http://localhost:8080
- 后端健康检查：http://localhost:8180/health
- 后端接口文档：http://localhost:8180/docs

宿主机后端端口由 `MEDIASPIDER_BACKEND_PORT` 控制，默认是 `8180`；容器内部和
Nginx 服务发现仍固定使用 `8000`。

## 3. 默认存储

Compose 默认使用 SQLite repository，并把后端存储挂载到 Docker volume：

```text
mediaspider-storage:/app/backend/storage
```

SQLite 文件路径：

```text
/app/backend/storage/mediaspider-intel.sqlite3
```

Compose 默认启用一次性 JSON 迁移：

```text
MEDIASPIDER_AUTO_MIGRATE_JSON=true
```

后端容器只会在 SQLite 文件尚不存在时，把同一存储目录中的 JSON 数据导入
临时数据库；全部迁移成功后才原子替换为正式 SQLite 文件，然后再启动 API。
迁移失败不会留下被误判为完成的目标数据库。后续重启会跳过迁移，避免旧 JSON 覆盖已更新的 SQLite 数据。
升级前仍应先备份存储卷；若 SQLite 文件已经存在，需要手动执行迁移命令并核对计数。

## 4. 存储备份

本地或服务器上可以使用备份脚本把 `backend/storage` 打包成 zip：

```powershell
python backend/scripts/backup_storage.py --storage-dir backend/storage --output-dir backups
```

指定备份名称：

```powershell
python backend/scripts/backup_storage.py --storage-dir backend/storage --output-dir backups --name before-upgrade
```

## 5. 前端代理

前端容器使用 Nginx 托管静态文件，并把：

```text
/api/*
```

代理到：

```text
backend:8000/api/*
```

因此前端运行在 `http://localhost:8080` 时不需要额外配置 API 地址。

## 6. MediaCrawler 接入

平台主体不依赖 MediaCrawler 即可启动。需要执行真实采集任务时，在宿主机配置一个已授权的
MediaCrawler 工作目录：

```text
MEDIASPIDER_MEDIA_CRAWLER_HOST_PATH=/absolute/path/to/MediaCrawler
```

使用 crawler 覆盖文件构建并启动：

```bash
docker compose -f docker-compose.yml -f docker-compose.crawler.yml up --build -d
```

该镜像只安装 MediaCrawler 核心依赖、Chromium 和中文字体，不包含 PySide6 GUI。构建时会把
指定的 MediaCrawler 目录作为 BuildKit additional context 复制到 `/opt/mediacrawler`，运行时
后端通过内置的 `run_mediacrawler.py` 兼容启动器执行采集。浏览器状态保存在独立的
`mediaspider-browser-data` volume，采集输出和任务数据库仍保存在 `mediaspider-storage`。

Linux 无桌面服务器应创建 Cookie Profile，并把任务设置为 `headless=true`。二维码或手机号
登录需要可见浏览器，诊断接口会阻止它们与无头模式组合使用。

基础命令 `docker compose up --build` 仍只构建轻量 Web 平台，不包含真实采集环境。

## 7. 认证配置

默认开发模式不强制登录：

```text
MEDIASPIDER_AUTH_REQUIRED=false
```

需要启用登录保护时设置：

```text
MEDIASPIDER_AUTH_REQUIRED=true
MEDIASPIDER_AUTH_SECRET=change-me
MEDIASPIDER_AUTH_USERS=admin:admin:admin:Administrator,analyst:analyst:analyst:Analyst
```

用户格式：

```text
username:password:role:display_name
```

当前已支持的基础角色：

- `admin`
- `analyst`
- `operator`
- `viewer`

## 8. 后台调度器

默认不自动运行后台调度器：

```text
MEDIASPIDER_SCHEDULER_ENABLED=false
```

需要让平台定时扫描采集任务时设置：

```text
MEDIASPIDER_SCHEDULER_ENABLED=true
MEDIASPIDER_SCHEDULER_INTERVAL_SECONDS=60
MEDIASPIDER_SCHEDULER_EXECUTE_CRAWLER=true
MEDIASPIDER_TASK_MAX_CONCURRENT_RUNS=1
MEDIASPIDER_TASK_QUEUE_TIMEOUT_SECONDS=300
MEDIASPIDER_TASK_LEASE_SECONDS=30
MEDIASPIDER_INSTANCE_ID=backend-1
MEDIASPIDER_TASK_RECOVER_INTERRUPTED_RUNS=true
```

`MEDIASPIDER_TASK_MAX_CONCURRENT_RUNS` 控制单个后端进程同时执行的采集任务数。超出容量的运行会以
`pending` 状态等待；等待超过 `MEDIASPIDER_TASK_QUEUE_TIMEOUT_SECONDS` 后会记录失败并返回服务繁忙错误。

SQLite 任务仓储会为每次真实采集创建共享运行租约，并按租约时长的三分之一自动续租。同一 SQLite
文件上的多个后端进程不能重复执行同一任务；租约丢失时当前运行会终止并记录失败。
`MEDIASPIDER_INSTANCE_ID` 应为每个后端实例设置不同且稳定的值，便于在调度器状态中定位租约持有者。

建议保持 `MEDIASPIDER_TASK_RECOVER_INTERRUPTED_RUNS=true`。后端启动时会跳过仍有有效租约的运行，
只将没有租约或租约已过期的遗留 `pending` 运行取消，并将遗留 `running` 运行标记为失败。JSON 任务仓储
不支持共享租约，仅适用于单进程开发模式；多进程部署必须让所有实例共享同一个 SQLite 文件。

## 9. 常用命令

重建并启动：

```powershell
docker compose up --build
```

后台启动：

```powershell
docker compose up -d --build
```

查看日志：

```powershell
docker compose logs -f
```

停止：

```powershell
docker compose down
```

停止并删除存储卷：

```powershell
docker compose down -v
```
