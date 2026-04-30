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

先启动后端：

```powershell
cd H:\MediaCrawler-main\products\mediaspider-intel-platform
uv run python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

再启动前端：

```powershell
cd H:\MediaCrawler-main\products\mediaspider-intel-platform\frontend
npm install
npm run dev
```

访问：

- 前端：[http://127.0.0.1:5173](http://127.0.0.1:5173)
- 后端健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

说明：

- 开发环境已通过 `vite.config.ts` 把 `/api` 代理到 `127.0.0.1:8000`
- 如需直连其他后端地址，可通过 `VITE_API_BASE_URL` 覆盖默认 API 根路径
