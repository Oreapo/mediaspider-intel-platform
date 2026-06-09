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

## 6. MediaCrawler 接入预留

当前 Compose 已预留：

```text
MEDIASPIDER_MEDIA_CRAWLER_ROOT=/app/mediacrawler
```

后续阶段 5 会补充真实 MediaCrawler 挂载、登录态和采集运行配置。

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
```

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
