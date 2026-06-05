# 🌍 Climate & Carbon-Aware Planner

A household scheduling tool that recommends the best time windows to run flexible appliances — low-carbon, low-cost, and weather-suitable — and shows you the exact **£ saved** and **kg CO₂ avoided** vs running at the evening peak.

**[Live demo →](https://greenhours.ontwrpn.com)** · [Case study →](https://www.notion.so/3722ead75652815ca031f2deccb087a0)

> The UK grid swings from ~50 to ~380 gCO₂/kWh within a single day. This tool turns that signal into a named time window — no smart meter, no solar panels, no hardware required.

---

## What it does

Pick a city and tasks (laundry, EV charging, dishwasher, ventilation), choose your priority (Go Green / Save Money / Balanced), and get:

- **Primary + backup windows** with exact start/end times
- **Carbon saving** vs the evening-peak baseline (kg CO₂)
- **Cost saving** vs the evening-peak baseline (UK only — £, Octopus Agile pricing; EU cities show carbon only)
- **One-line reason** explaining why this window was chosen
- **7-day outlook** with an AI-generated weekly brief (Groq)
- **Scenario comparison** — all three optimisation modes side by side
- **Plan history** with ✓/✗ follow-through feedback
- **Light/dark theme**, an interactive (zoomable) 48-hour chart, and a first-run product tour

---

## Architecture

```
React + Vite (frontend)
    ↓  /api/*  JSON
FastAPI (backend)
    providers/   →  carbon_uk · carbon_fr · carbon_be · price_octopus · weather_openmeteo
    core/        →  scoring · scheduler · savings
    routers/     →  plan · compare · forecast · weekly · history
    db.py        →  SQLite locally / Postgres in prod
```

### 4-axis scoring engine

Every 30-minute slot in the 48-hour grid gets a composite 0–100 score:

| Axis | Go Green | Save Money | Balanced |
|---|---|---|---|
| Carbon intensity | 55% | 10% | 33% |
| Electricity price | 10% | 55% | 33% |
| Weather suitability | 35% | 35% | 34% |
| Comfort | hard gate | hard gate | hard gate |

Comfort is a hard gate — slots that violate a constraint (rain during outdoor drying, pollen spike during ventilation) are excluded, not penalised.

### Slide-window scheduler

For each task the scheduler scans every valid start in the grid, applies comfort gates, and ranks candidates by mean fit score over the task duration. Returns a primary window and the best non-overlapping backup.

### 7-day outlook

Days 1–2 use genuine API forecast data. Days 3–7 use a cyclical time-of-day proxy (each forward slot matched to the same time-of-day from recent actuals, 24h → 48h → 72h lag). Clearly labelled in the UI.

---

## Data sources

| Source | What | Coverage | Key needed |
|---|---|---|---|
| [UK Carbon Intensity API](https://carbonintensity.org.uk) | Grid carbon intensity + 48h forecast | UK (17 regions) | No |
| [RTE éco2mix via ODRE](https://odre.opendatasoft.com) | Grid carbon intensity actuals | France | No |
| [Elia open data ods192](https://opendata.elia.be) | Consumption-based CO₂ intensity | Belgium | No |
| [Octopus Agile API](https://octopus.energy/agile/) | 30-min electricity prices | UK | No |
| [Open-Meteo](https://open-meteo.com) | Weather forecast (10 variables) | Global | No |
| [Groq](https://console.groq.com) | AI weekly brief (llama-3.1-8b-instant) | — | Free tier |

---

## Local development

No database install needed — SQLite is created automatically.

**Terminal 1 — backend** (Python 3.10 required):

```bash
cd backend
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add GROQ_API_KEY if you want AI briefs
uvicorn app.main:app --reload --port 3001
```

**Terminal 2 — frontend:**

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies all `/api` requests to the FastAPI backend on port 3001.

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | No (uses SQLite) | Postgres connection string for production; blank locally falls back to SQLite |
| `GROQ_API_KEY` | No | Enables AI weekly briefs; falls back to template text without it |

Copy `.env.example` → `backend/.env` and fill in values.

---

## Running tests

```bash
cd backend
.venv/bin/python -m pytest tests/ -v
```

30 unit tests covering the scoring engine, scheduler, and savings calculator. All pure functions — no mocking, no network.

---

## API reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | `{ status, db }` — confirms database connectivity |
| `GET` | `/api/forecast` | 48-hour normalised slot grid (carbon + price + weather scores) |
| `POST` | `/api/plan` | Best windows for a list of tasks; saves plan to DB |
| `POST` | `/api/compare` | Same tasks across all three modes in one call |
| `POST` | `/api/weekly` | 7-day outlook + AI brief |
| `GET` | `/api/plans` | Recent plan history (last 20) |
| `POST` | `/api/feedback` | Record whether user followed a recommendation |

### POST /api/plan — example

```json
{
  "city": "london",
  "mode": "balanced",
  "tasks": [
    { "type": "ev_charge", "duration_mins": 240,
      "window_start": "22:00", "window_end": "23:59", "deadline": "07:00" },
    { "type": "laundry_airdry", "duration_mins": 120,
      "window_start": "08:00", "window_end": "20:00" }
  ]
}
```

Task types: `laundry_airdry` · `laundry_dryer` · `dishwasher` · `ev_charge` · `ventilation`  
Cities: `london` · `paris` · `antwerp`  
Modes: `balanced` · `green` · `money`

---

## Deploying

The app ships as a single Docker image (multi-stage: Vite build → Python runtime;
uvicorn serves both the API and the built SPA on port 3001). It runs on
[Coolify](https://coolify.io) (self-hosted Docker PaaS) at
[greenhours.ontwrpn.com](https://greenhours.ontwrpn.com), but the image is
platform-agnostic — any Docker host works.

1. Push to GitHub (auto-deploy fires on push to `main`).
2. Point the host at the repo's `Dockerfile`; expose port `3001`; health check `/api/health`.
3. Set environment variables:
   - `DATABASE_URL` — Postgres connection string (`postgresql://...`); omit to use SQLite. Add `?sslmode=require` only if your provider needs it (managed Postgres like Neon does; Coolify-internal Postgres does not).
   - `GROQ_API_KEY` — from [console.groq.com](https://console.groq.com) (free); optional, falls back to template briefs.

---

## Project structure

```
.
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py              FastAPI entry point, lifespan, CORS
│   │   ├── config.py            Settings (pydantic-settings, reads .env)
│   │   ├── db.py                SQLAlchemy engine — SQLite local / Postgres prod
│   │   ├── models.py            Plan · Task · Recommendation · Feedback
│   │   ├── schemas.py           Pydantic request/response models
│   │   ├── routers/             plan · compare · forecast · weekly · history
│   │   ├── providers/           carbon_uk · carbon_fr · carbon_be · price_octopus · weather_openmeteo · brief_groq
│   │   └── core/                scoring · scheduler · savings · tasks · city_registry
│   └── tests/
│       └── test_core.py         30 unit tests
├── frontend/
│   └── src/
│       ├── App.jsx
│       └── styles.css
├── Dockerfile                   Multi-stage: Node build → Python deps → runtime
├── .env.example
└── docs/
    ├── implementation-plan.md
    └── competitive-research.md
```
