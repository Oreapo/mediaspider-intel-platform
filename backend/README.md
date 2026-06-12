# Backend

The backend is a FastAPI application organized into API, application, domain, and persistence layers.

## Run Locally

From the repository root:

```powershell
.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.venv\Scripts\python.exe -m backend.app
```

On Linux or macOS, replace `.venv\Scripts\python.exe` with `.venv/bin/python`.

Default endpoints:

- API documentation: http://127.0.0.1:8180/docs
- Health check: http://127.0.0.1:8180/health

Configuration is read from the root `.env` file. Copy `.env.example` to `.env` before changing storage, authentication, scheduler, or crawler settings.

## Test

```powershell
.venv\Scripts\python.exe -m pytest backend\tests
```

SQLite is the recommended repository mode. JSON repositories remain available for migration and compatibility testing.
