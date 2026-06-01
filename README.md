# Climate & Carbon-Aware Planner

A decision-support tool that recommends the best time windows to run flexible household and office tasks — based on grid carbon intensity, electricity price, weather, and comfort. Deployed free on Render (web service + managed Postgres), SQLite for local dev.

## Stack

- **Frontend:** React 18 + Vite 5 (JavaScript)
- **Backend:** Python 3.10+ · FastAPI · SQLAlchemy
- **Database:** SQLite locally (no install needed) · PostgreSQL on Render
- **Data sources:** UK Carbon Intensity API · Octopus Agile (price) · Open-Meteo (weather) — all free
- **Deploy:** Render free tier, provisioned via `render.yaml` Blueprint

## Project structure

```text
.
├── backend/
│   ├── requirements.txt
│   ├── .python-version        # 3.10 (local dev)
│   └── app/
│       ├── main.py            # FastAPI entry point
│       ├── config.py          # settings from env
│       ├── db.py              # SQLAlchemy, SQLite/Postgres from DATABASE_URL
│       ├── models.py          # ORM models
│       ├── routers/           # API routes
│       ├── providers/         # carbon / price / weather data clients
│       └── core/              # scoring, scheduling, savings engine
├── frontend/
│   ├── package.json
│   ├── vite.config.js         # dev proxy /api → localhost:3001
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       └── styles.css
├── Dockerfile                 # multi-stage: Node build → Python deps → runtime
├── render.yaml                # Blueprint: free web service + Postgres
├── .env.example
├── .gitignore
├── .dockerignore
└── docs/
    ├── implementation-plan.md
    └── competitive-research.md
```

## Local development

No database to install — SQLite is created automatically on first run.

**Terminal 1 — backend** (Python 3.10 required; 3.14 has no pydantic-core wheels yet):

```bash
cd backend
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 3001
```

**Terminal 2 — frontend:**

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite dev server proxies all `/api` requests to the FastAPI backend on port 3001.

## Deploy to Render

1. Push this repo to GitHub.
2. In Render, go to **New → Blueprint** and connect the repository.
3. Render reads `render.yaml` and provisions a free web service (Docker) and a free Postgres database. `DATABASE_URL` is wired automatically.

**Free-tier notes:**

- The web service sleeps after inactivity; expect a ~30s cold start on the first request.
- Render's free Postgres instance expires after 90 days and must be manually recreated.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/hello` | Returns a greeting message |
| `GET` | `/api/health` | Checks database connectivity, returns `{ status, db }` |
| `GET` | `*` | Serves the React SPA (production only) |
