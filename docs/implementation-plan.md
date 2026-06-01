# Implementation Plan — Climate & Carbon-Aware Planner

_Last updated 2026-06-01. Companion to [competitive-research.md](competitive-research.md)._

## 0. Decisions locked

| Decision | Choice | Why |
|---|---|---|
| Backend | **Python + FastAPI** (replaces the Express scaffold) | Portfolio goal = "senior Python: time-series + optimisation"; the scoring/scheduling core is the IP and reads naturally in pandas |
| Frontend | **React + Vite (JS)** — reuse existing scaffold | Already built; Recharts for the timeline |
| DB | **SQLAlchemy**, SQLite local / Postgres on Render, picked from `DATABASE_URL` | Mirrors the original `db.js` dialect-switch idea |
| Optimisation axes | **Carbon + Price + Weather + Comfort**, user-weighted (Money / CO₂ / Balanced) | Research: price motivates more than CO₂; nobody fuses all four |
| MVP sequence | **Phase 1 = MVP A+** (London home + laundry flagship) → **Phase 2 = MVP B** (Office/B2B) | One sharp wedge first; architecture supports both from day one |
| Deploy | Render free tier (web service + Postgres) via Blueprint | Same as scaffold; just swap the runtime to Python |

## 1. Positioning (the north star)

> **The only planner that turns a household's flexible tasks into named time windows that are low-carbon, low-cost AND weather-suitable — supplier-agnostic, no hardware — and tells you the exact £ and kg CO₂ you save.**

The defensible moat is **not** the grid signal (free/commoditised). It is: the **4-axis scoring engine + the weather fusion + per-action savings + personalisation** — none of which any competitor combines (see research §"the wedge").

Three rules every feature obeys:
1. **Output a named window** (primary + backup + one-line reason), never a raw chart to interpret.
2. **Lead with a number** (£ + kg CO₂ saved vs the naive default).
3. **Stay supplier- and hardware-agnostic.**

## 2. Target architecture

```
┌─────────────────────────────────────────────────────────┐
│  React + Vite (frontend/)                                │
│  Planner setup · Activity input · Day timeline ·         │
│  Recommendation cards · (P2) Scenarios · Weekly plan     │
└───────────────┬─────────────────────────────────────────┘
                │  JSON over /api/*  (Vite proxy in dev)
┌───────────────▼─────────────────────────────────────────┐
│  FastAPI (backend/)                                      │
│  routers/        → /api/health, /api/forecast, /api/plan │
│  providers/      → CarbonProvider, PriceProvider,        │
│                    WeatherProvider  (pluggable per city) │
│  core/                                                   │
│    slots.py      → normalise everything to 30-min slots  │
│    scoring.py    → carbon/price/weather/comfort scores   │
│    scheduler.py  → slide-window window picker            │
│    savings.py    → £ + kg CO₂ vs naive baseline          │
│    tasks.py      → task templates + weather profiles     │
│  models.py       → SQLAlchemy (Plan, Task, Recommendation)│
│  db.py           → engine from DATABASE_URL (sqlite/pg)  │
│  cache           → TTL cache of upstream API responses   │
└───────────────┬─────────────────────────────────────────┘
                │
        ┌───────┴───────┬──────────────┬─────────────────┐
        ▼               ▼              ▼                 ▼
  Open-Meteo     Carbon Intensity   Octopus Agile    (P2) RTE éCO2mix,
  (weather,      API (GB, free,     API (price,      Elia — via the same
  free, no key)  96h, regional)     free, public)    provider interfaces
```

Key design move: **`providers/` are interfaces.** Phase 1 ships `UKCarbonProvider`, `OctopusAgilePriceProvider`, `OpenMeteoWeatherProvider`. Phase 2 adds `RTECarbonProvider` (Paris), `EliaCarbonProvider` (Antwerp) behind the **same interface**, so the scoring/scheduler code never changes when adding a city.

### Backend layout
```
backend/
├── pyproject.toml          # or requirements.txt
├── app/
│   ├── main.py             # FastAPI app, static serving in prod, CORS
│   ├── db.py               # engine + session, DATABASE_URL switch
│   ├── models.py           # SQLAlchemy models
│   ├── schemas.py          # Pydantic request/response models
│   ├── config.py           # settings (env)
│   ├── routers/
│   │   ├── health.py
│   │   ├── forecast.py
│   │   └── plan.py
│   ├── providers/
│   │   ├── base.py         # CarbonProvider / PriceProvider / WeatherProvider ABCs
│   │   ├── carbon_uk.py
│   │   ├── price_octopus.py
│   │   └── weather_openmeteo.py
│   └── core/
│       ├── slots.py
│       ├── scoring.py
│       ├── scheduler.py
│       ├── savings.py
│       └── tasks.py
└── tests/                  # pytest — core/ is pure functions, easy to test
```

### Dependencies
`fastapi`, `uvicorn[standard]`, `httpx`, `pandas`, `numpy`, `pydantic`, `pydantic-settings`, `sqlalchemy`, `psycopg2-binary` (Postgres), `cachetools`. Dev: `pytest`, `respx` (mock httpx). **No** scipy/pulp/ortools for the MVP — the search space (≤192 slots × a handful of tasks) is tiny; a slide-window scan is exact and instant. Keep ortools as a documented "if constraints grow" note, not a dependency.

## 3. Data layer

### 3.1 Weather — Open-Meteo
- Endpoint: `https://api.open-meteo.com/v1/forecast` — no key, no auth, free non-commercial.
- Request hourly: `temperature_2m, relative_humidity_2m, dew_point_2m, precipitation_probability, precipitation, wind_speed_10m, cloud_cover, shortwave_radiation, uv_index`. Plus air-quality endpoint for `pm2_5, pm10` and pollen (where available) for the ventilate/walk profiles.
- `forecast_days` up to 16; we use 4 (96h) to match the carbon horizon.
- London: `latitude=51.5072&longitude=-0.1276&timezone=Europe/London`.

### 3.2 Carbon — UK Carbon Intensity API
- `https://api.carbonintensity.org.uk/regional/intensity/{from}/fw48h/regionid/{id}` (regional, 48h fw) and `/intensity/{from}/fw48h` (national). Free, CC-BY, no auth, 30-min resolution.
- Region 13 = London. Returns `forecast` gCO₂/kWh + `index` (very low…very high) per 30-min slot.
- The 96h horizon: chain national `fw24h`/`fw48h` calls; regional gives 48h — Phase 1 plans a 48h horizon to stay within regional coverage.

### 3.3 Price — Octopus Agile (free, public)
- `https://api.octopus.energy/v1/products/AGILE-FLEX-22-11-25/electricity-tariffs/E-1R-AGILE-FLEX-22-11-25-C/standard-unit-rates/` — 30-min unit rates in p/kWh, no key. (Region code letter, e.g. `-C` = London.)
- Handle **negative** rates (Agile can go below zero) → those are the best price slots.
- Framed as "indicative Agile pricing" — supplier-agnostic; user is not required to be on Agile (it's a reasonable proxy for time-of-use value). A later setting lets them pick their region letter or paste a flat tariff.

### 3.4 Normalisation & caching
- All three sources → a single **30-min slot grid** over the planning horizon (`core/slots.py`). Weather is hourly → forward-fill / linear-interpolate to 30-min. Carbon + price are already 30-min.
- Output: a pandas DataFrame indexed by slot start, columns `[ci_gco2, price_p, temp, humidity, dew_point, precip_prob, wind, cloud, radiation, uv, pm2_5, pollen]`.
- **Cache** each upstream response with a TTL (carbon/price ~30 min, weather ~1h) keyed by region+date. `cachetools.TTLCache` in-memory for MVP; a `cached_forecast` table if we need persistence across restarts. Keeps us well under rate limits and makes `/api/plan` fast.

## 4. Domain model

```python
# tasks.py — a task template knows its energy draw and which weather matters
@dataclass
class WeatherProfile:
    # weight 0..1 per variable; None = irrelevant for this task
    precip_prob: float | None
    humidity: float | None
    wind: float | None
    radiation: float | None
    temp_comfort: tuple[float, float] | None   # (min, max) feels-good band
    uv: float | None
    pollen: float | None
    aqi: float | None

TASK_TEMPLATES = {
  "laundry_dryer":   Task(kwh=1.0, default_weather="indoor", flexible=True),
  "laundry_airdry":  Task(kwh=0.0, weather=DRYING_PROFILE, avoided="dryer"),  # flagship
  "dishwasher":      Task(kwh=1.5, weather=None),     # carbon+price only
  "ev_charge":       Task(kwh=8.0, weather=None, deadline=True),
  "ventilation":     Task(kwh=0.0, weather=VENTILATION_PROFILE),
  # P2 office:
  "hvac_precool":    Task(kwh=3.0, weather=PRECOOL_PROFILE, comfort_priority="high"),
  "server_backup":   Task(kwh=2.0, weather=None),
  "device_charging": Task(kwh=1.0, weather=None),
}
```

### DB schema (SQLAlchemy)
- **Plan** — `id, created_at, location, region_id, mode (green|money|balanced), horizon_hours`
- **Task** — `id, plan_id (FK), type, duration_mins, window_start, window_end, deadline, kwh, energy_intensity`
- **Recommendation** — `id, task_id (FK), primary_start, primary_end, backup_start, backup_end, carbon_saved_kg, cost_saved_gbp, score, reason`
- **(P2) Profile** — comfort tolerances per user/session (cold, wind, humidity, pollen, UV)
- **(P2) Feedback** — `recommendation_id, rating, felt_too_cold|too_windy|...` → tunes the comfort band (the learning loop)

For the MVP, plans can be **anonymous/session-scoped** — no auth. A plan is created, scored, returned, and optionally persisted for the weekly view. Auth is explicitly out of scope until there's a reason.

## 5. The scoring engine (core IP)

All scores are **0–100, higher = better**, computed per 30-min slot over the horizon.

### 5.1 Carbon score
```
carbon_score[s] = 100 * (ci_max - ci[s]) / (ci_max - ci_min)
```
Normalised across the horizon (min/max of the forecast window). Lowest gCO₂/kWh → 100.

### 5.2 Price score
```
price_score[s] = 100 * (p_max - p[s]) / (p_max - p_min)
```
Negative Agile prices naturally score ≥100-region (clamp to 100). Cheapest → best.

### 5.3 Weather/comfort score (task-dependent)
Only for weather-dependent tasks. Each relevant variable → a 0–100 sub-score via a shaping function, then a weighted mean over the task's `WeatherProfile`:
- **Drying (flagship):** reward low `precip_prob`, low `humidity`/high dew-point spread, moderate `wind` (helps drying), high `shortwave_radiation`; penalise rain hard. → "will clothes actually dry."
- **Ventilation:** reward outdoor `humidity` < indoor assumption, no precip, comfortable `temp`; penalise high `pollen`/`pm2_5` (don't tell an allergy sufferer to open windows in a pollen spike).
- **Outdoor activity (P2 / walk-run):** comfortable feels-like temp band, low precip, low wind, non-extreme UV, low pollen.
- Weather-independent tasks (dishwasher, EV, backups): `weather_score = None` → its weight is redistributed to carbon+price.

### 5.4 Task Fit Score (per slot) — the weighting
Base weights by mode, then renormalised if weather is absent:

| Mode | carbon | price | weather |
|---|---|---|---|
| Go green (CO₂) | 0.55 | 0.10 | 0.35 |
| Save money | 0.10 | 0.55 | 0.35 |
| Balanced | 0.33 | 0.33 | 0.34 |

```
fit[s] = w_c·carbon_score[s] + w_p·price_score[s] + w_w·weather_score[s]
```
**Comfort = hard constraints**, applied before scoring: a slot is *invalid* if it violates a guardrail (e.g., feels-like outside the task's comfort band, pollen "very high" for ventilation, rain for outdoor drying). Invalid slots are excluded from window search, not just penalised — so recommendations are never absurd.

### 5.5 Window scheduler (`scheduler.py`)
For each task with duration `D` slots, flexibility `[a, b]`, deadline `t_d`:
```
candidates = []
for start in valid_starts(a, b, t_d, D):          # window fully inside flex & finishes by deadline
    window = slots[start : start+D]
    if any(slot invalid): continue                 # comfort hard-constraint
    candidates.append((start, mean(fit over window)))
rank candidates by score desc
primary  = candidates[0]
backup   = best candidate not overlapping primary
```
- Multi-task (Phase 1): tasks are independent → score each separately. (Optional later: a "don't run two High-draw tasks in the same slot" constraint — greedy assignment in priority order.)
- Output per task: primary window, backup window, the winning scores, and a generated `reason` string.

### 5.6 Savings (`savings.py`) — the number we lead with
```
baseline_slot = naive default (e.g., "run now" or the typical evening-peak slot 18:00–20:00)
co2_saved_kg  = task.kwh * (ci[baseline] - ci[chosen]) / 1000
cost_saved_£  = task.kwh * (p[baseline]  - p[chosen])  / 100
# laundry flagship: air-dry avoids the dryer entirely
co2_saved_kg  = DRYER_KWH * ci[would-run-slot] / 1000      # dryer avoided
cost_saved_£  = DRYER_KWH * p[would-run-slot] / 100
```
Reason string, e.g.: _"Run laundry 13:00–15:00: grid is 38% cleaner than this evening and it's dry & breezy outside — air-dry and skip the dryer to save ~1.4 kg CO₂ / £0.32."_

## 6. API contract

| Method | Path | Body / params | Returns |
|---|---|---|---|
| GET | `/api/health` | — | `{status, db}` |
| GET | `/api/forecast` | `region_id, horizon` | normalised 30-min slots: `[{start, ci, price, weather…, carbon_score, price_score}]` (for the timeline view) |
| POST | `/api/plan` | `{location, region_id, mode, tasks:[{type, duration_mins, window_start, window_end, deadline, kwh?}]}` | `{slots:[…], recommendations:[{task, primary, backup, co2_saved_kg, cost_saved_gbp, scores, reason}]}` |
| POST | `/api/feedback` _(P2)_ | `{recommendation_id, rating, flags}` | `{ok}` |
| GET | `/api/weekly` _(P2)_ | `region_id` | best days/windows per task across 7 days |

Pydantic schemas validate everything; the `/api/plan` response is the single source the frontend renders.

## 7. Frontend

Reuse the React/Vite scaffold; add Recharts. Screens map to the doc:

1. **Planner setup** — location (London for P1), mode toggle **Save money / Go green / Balanced**.
2. **Activity input** — add tasks from templates (laundry, dishwasher, EV/device charging, ventilation); each: duration, flexible-between, must-finish-by, energy intensity. Laundry has an **air-dry vs dryer** choice (flagship).
3. **Day timeline** — Recharts area/heat strip over 48h: carbon band + price band + weather suitability, with the recommended windows highlighted. "Avoid" zones (high carbon/peak) shaded.
4. **Recommendation cards** — per task: **named primary + backup window**, the savings number (£ + kg CO₂), one-line reason, "constraints satisfied" check.
5. **Scenario comparison** _(P2)_ — Convenience-first / Carbon-first / Balanced, side by side with their savings + inconvenience.
6. **Weekly plan** _(P2)_ — best days for laundry / outdoor / ventilation; high-carbon periods to avoid.

State: lightweight (React state + a small fetch hook like the scaffold's `useFetch`). No router needed in P1 (single flow); add `react-router` only if P2 needs distinct pages.

## 8. Deployment (Render)

- Swap the scaffold's Node Dockerfile for a **Python** one: install deps, copy `frontend/dist` into the FastAPI static dir, run `uvicorn app.main:app`. FastAPI serves the built SPA (catch-all → `index.html`) exactly like the Express scaffold did.
- `render.yaml`: keep the **exact** service names from the scaffold (`ai-workshop-db`, `ai-workshop-web` — or rename **once** now before first deploy if desired, then never again) and `runtime: docker`; `DATABASE_URL` wired via `fromDatabase`. Health check `/api/health`.
- `db.py`: `DATABASE_URL` starting `postgres://`→ Postgres (with SSL), else SQLite file — same logic as the original `db.js`.
- Local dev needs no Docker and no DB install (SQLite). Two terminals: `uvicorn --reload` + `vite`.

## 9. Phased milestones

### Phase 0 — Foundation (rework the scaffold) — ~0.5–1 day
- Replace `backend/` (Express) with the FastAPI skeleton + `db.py` dialect switch + `/api/health`.
- Repoint the React frontend's fetch at FastAPI; confirm dev proxy works.
- Update `Dockerfile` + `render.yaml` for Python; deploy a "hello + health" to Render to prove the pipeline end-to-end.
- **Done when:** health endpoint returns `{status:"ok", db:"sqlite"}` locally and `{… "postgres"}` on Render, and the React shell loads from the deployed service.

### Phase 1 — MVP A+ (London home + laundry flagship) — the core
- Providers: `OpenMeteoWeatherProvider`, `UKCarbonProvider`, `OctopusAgilePriceProvider` (+ TTL cache).
- `core/`: slots → scoring (4-axis) → scheduler (primary+backup) → savings. Unit-test each (pure functions).
- Task templates: laundry (air-dry vs dryer), dishwasher, EV/device charging, ventilation.
- Screens 1–4 wired to `/api/plan` and `/api/forecast`.
- **Done when:** a user picks London + mode + 3 tasks and gets named windows with £/CO₂ numbers and a day timeline; deployed to Render.

### Phase 2 — MVP B (Office/B2B) + depth
- Office task templates (HVAC pre-cool/pre-heat, server backups, device charging, cleaning, maintenance) with comfort priorities.
- **Scenario comparison** (Convenience / Carbon / Balanced) and **Weekly plan**.
- **Multi-city** via new providers behind the same interface: Paris (RTE éCO2mix), Antwerp (Elia — estimated CI from generation mix + emission factors, clearly labelled "estimate").
- **Personalisation profile + feedback loop** (comfort tolerances tune the guardrails/weather sub-scores).
- Outcome-framed **notifications** ("good drying window opens at 13:00").

### Phase 3 — RAG explanation layer (the senior flourish)
- Ingest sustainability policy / energy bills / building manuals (PDF/CSV).
- "Why is this schedule recommended?" + auto-generate a **weekly energy brief** grounded in the user's own docs, via the Claude API (with prompt caching).
- No SME competitor offers this (research §D) — strong portfolio differentiator.

## 10. Risks & mitigations
- **Carbon horizon vs regional coverage** — regional UK API is ~48h; national reaches further. P1 plans a 48h horizon (honest about it); weekly view (P2) blends climatology where forecast runs out (Visual Crossing pattern).
- **Octopus Agile ≠ everyone's tariff** — label as "indicative time-of-use pricing"; let users pick region letter / paste a flat rate; price weight is user-controlled (can set to 0).
- **Antwerp has no official CI endpoint** — compute estimated CI from Elia generation mix × emission factors, **clearly marked as an estimate** (per research note).
- **Scope creep** — A+ ships before B is touched; B before RAG. The provider/scoring abstraction is the only thing built "for later" up front, and it pays for itself the first time a city is added.
- **Free-tier cold start** — Render free web service sleeps (~30s wake). Acceptable for a portfolio demo; note it in the README.

## 11. Immediate next steps
1. Confirm/clean service names in `render.yaml` **now** (renaming after first deploy orphans Render resources).
2. Scaffold the FastAPI backend (Phase 0) and delete the Express backend.
3. Stand up the three providers with the TTL cache and a `/api/forecast` that returns a real normalised London 48h grid — that single endpoint de-risks the whole data layer before any scoring is written.
