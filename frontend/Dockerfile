# syntax=docker/dockerfile:1

FROM node:20-alpine AS build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund

COPY frontend ./
RUN npm run build

FROM nginx:1.27-alpine

LABEL org.opencontainers.image.title="Cyber Risk Intelligence Frontend" \
      org.opencontainers.image.description="Vue 3 SPA served by nginx, proxying /api to the backend" \
      org.opencontainers.image.source="https://github.com/Oreapo/mediaspider-intel-platform"

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
