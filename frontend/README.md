# Frontend

这个目录现在已经不是纯占位，而是可运行的 Vue 3 + Vite 前端骨架。

当前已接入页面：

- `dashboard`
- `tasks`
- `datasets`
- `analysis`
- `reports`
- `logs`
- `settings`

当前已接入能力：

- 多平台任务模型读取
- 任务创建 / 启用 / 禁用 / 启动运行
- 数据集创建 / 删除 / 预览
- 分析任务创建 / 输出查看

## 本地启动

可选：复制根目录环境模板，后端启动器和 Vite 会共同读取该文件：

```powershell
Copy-Item .env.example .env
```

在项目根目录先启动后端：

```powershell
.venv\Scripts\python.exe -m backend.app
```

再启动前端：

```powershell
cd frontend
npm install
npm run dev
```

访问：

- 前端：[http://127.0.0.1:5173](http://127.0.0.1:5173)
- 后端健康检查：[http://127.0.0.1:8180/health](http://127.0.0.1:8180/health)

说明：

- 本地启动入口读取 `MEDIASPIDER_BACKEND_HOST`、`MEDIASPIDER_BACKEND_PORT` 和 `MEDIASPIDER_BACKEND_RELOAD`
- 开发环境已通过 `vite.config.ts` 把 `/api` 和 `/health` 代理到 `127.0.0.1:8180`
- 如需代理到其他后端地址，可设置 `MEDIASPIDER_API_TARGET`
- `VITE_API_BASE_URL` 用于覆盖浏览器请求使用的 API 根路径
- Docker 容器内部仍使用 `8000`，不受本地开发端口影响
