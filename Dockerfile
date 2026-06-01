# Stage 1: build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: install Python production deps
FROM python:3.12-slim AS backend-deps
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: runtime
FROM python:3.12-slim AS runtime
ENV NODE_ENV=production
ENV PORT=3001
WORKDIR /app/backend
COPY backend/ ./
COPY --from=backend-deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-deps /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=frontend-build /app/frontend/dist ./public
EXPOSE 3001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001"]
