# Stage 1: build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim AS runtime
ENV NODE_ENV=production
ENV PORT=3001
WORKDIR /app/backend

# Install deps — psycopg2-binary is added here (Python 3.12 has wheels);
# it is intentionally absent from requirements.txt so local dev on 3.10/3.14
# works without a Postgres adapter (SQLite is used locally).
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary==2.9.10

COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist ./public

EXPOSE 3001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001"]
