# syntax=docker/dockerfile:1

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="Cyber Risk Intelligence Backend" \
      org.opencontainers.image.description="FastAPI backend for the digital forensics / anti-black-grey intelligence platform" \
      org.opencontainers.image.source="https://github.com/Oreapo/mediaspider-intel-platform"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

# Dependencies first so source-only changes reuse this layer.
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY --chown=10001:10001 backend/app ./app
COPY --chown=10001:10001 backend/scripts ./scripts

# Fixed-UID non-root user; storage stays writable for SQLite/JSON data
# and seeds the named volume with the right ownership on first use.
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/backend/storage \
    && chown -R app:app /app/backend/storage

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('MEDIASPIDER_BACKEND_PORT', '8000') + '/health', timeout=4).read()"

CMD ["python", "scripts/start_backend.py"]
