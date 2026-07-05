# MediaSpider Intelligence Platform

MediaSpider Intelligence Platform is a full-stack investigation workbench for collecting public data, organizing datasets, extracting risk signals, linking entities, managing cases, and exporting evidence.

The repository contains a FastAPI backend, a Vue 3 frontend, SQLite persistence, Docker deployment, and automated tests. The default `main` branch is intended to be directly runnable.

## Features

- Multi-platform collection task management
- Dataset ingestion, filtering, preview, and pagination
- Analysis jobs and structured outputs
- Risk signals, entities, relations, and case workspaces
- Evidence packets and investigation reports
- Notification rules, delivery history, and inbox messages
- Audit events, role-based access control, and platform profiles
- JSON-to-SQLite migration and persistent Docker storage

## Quick Start With Docker

Requirements:

- Docker
- Docker Compose

Run:

```bash
git clone https://github.com/Oreapo/mediaspider-intel-platform.git
cd mediaspider-intel-platform
docker compose up --build
```

Open:

- Web application: http://localhost:8080
- API documentation: http://localhost:8180/docs
- Health check: http://localhost:8180/health

The default Docker configuration uses SQLite in a named volume and does not require login. Before exposing the service outside a trusted development environment, copy `.env.example` to `.env`, enable authentication, and replace the example secret and users.

## Local Development

Requirements:

- Python 3.10 or newer
- Node.js 20 or newer

Install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
npm --prefix frontend ci
Copy-Item .env.example .env
```

Start the backend:

```powershell
.venv\Scripts\python.exe -m backend.app
```

Start the frontend in another terminal:

```powershell
npm --prefix frontend run dev
```

The frontend is available at http://127.0.0.1:5200 and proxies API requests to http://127.0.0.1:8180.

On Linux or macOS, use `.venv/bin/python` instead of `.venv\Scripts\python.exe` and `cp .env.example .env` instead of `Copy-Item`.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest backend\tests
npm --prefix frontend run check:i18n
npm --prefix frontend run build
```

GitHub Actions runs the same backend test suite, i18n dictionary check, and frontend production build on `main`.

## Repository Layout

- `backend/`: FastAPI application, domain services, repositories, migrations, and tests
- `frontend/`: Vue 3 application and Nginx production configuration
- `docs/`: architecture, deployment, operations, and user documentation
- `data-contracts/`: shared data entity contracts
- `docker-compose.yml`: complete local deployment

## Documentation

- [User guide](docs/user-guide.md)
- [Deployment](docs/deployment.md)
- [Architecture](docs/architecture.md)
- [Persistence migration](docs/persistence-migration.md)
- [Development plan](docs/development-plan.md)

Real platform collection still depends on an authorized external MediaCrawler checkout configured through `MEDIASPIDER_MEDIA_CRAWLER_ROOT`. The rest of the application can run without it.
