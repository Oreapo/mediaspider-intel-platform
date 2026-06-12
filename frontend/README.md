# Frontend

The frontend is a Vue 3, TypeScript, Vue Router, and Vite application.

## Run Locally

Start the backend first, then run from the repository root:

```powershell
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open http://127.0.0.1:5173.

Vite proxies `/api` and `/health` to `MEDIASPIDER_API_TARGET`, which defaults to http://127.0.0.1:8180.

## Build

```powershell
npm --prefix frontend run build
```

The production Docker image serves the generated application through Nginx and proxies API requests to the backend container.
