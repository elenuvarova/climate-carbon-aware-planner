# Stage 1: build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
# npm ci uses the committed lockfile for a reproducible, deterministic install
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim AS runtime
ENV NODE_ENV=production
ENV PORT=3001
ENV PYTHONUNBUFFERED=1
WORKDIR /app/backend

# psycopg2-binary is pinned here for the Postgres adapter; Python 3.12 has wheels
# so no build toolchain is needed. requirements.txt is used for everything else.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary==2.9.10

COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist ./public

# Run as a non-root user
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 3001

# Probe the API health endpoint via Python (curl/wget are not guaranteed in
# python:3.12-slim). A non-200/exception exits non-zero -> container marked unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:3001/api/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001"]
