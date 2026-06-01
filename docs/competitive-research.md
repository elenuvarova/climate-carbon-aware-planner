# Competitive Research — Climate & Carbon-Aware Planner

_Compiled 2026-06-01 from a 4-stream competitive scan (carbon-aware computing, consumer home energy, weather-activity planners, B2B/ESG ops)._

## TL;DR — the wedge

Every competitor sits on **exactly one axis**:

- **Price** → Octopus Agile, Tibber
- **Carbon** → NESO/WhenToPlugIn, WWF Green Energy Forecast, Loop, Electricity Maps, WattTime
- **Weather** → Run Window, Peg It!/DryCast, AccuWeather indices, Weather.com GORun, Windguru
- **One device** → Ohme/Indra/ev.energy (EV), Nest Renew (HVAC, US-only), Samsung SmartThings (Samsung appliances)

And the *powerful* ones (real scheduling/automation) lock you into a **supplier** (Octopus/Tibber) or **hardware** (Ohme/Nest/Samsung/BMS). The only free, supplier-agnostic, no-hardware tools (NESO, WWF, Loop) are **passive dashboards** — they show a curve, they don't plan your task.

> **Whitespace nobody holds:** a supplier-agnostic, hardware-free, multi-task planner that fuses **carbon + price + weather + comfort** into a **named time window** with a concrete **£ + kg CO₂ saved** number.

The single closest cross-over product found is the **Humidity Window App** (recommends a "lowest-humidity 2-hour window to ventilate" and even mentions the energy penalty) — but it's ventilation-only, no carbon quantification, no grid data. It proves the exact UX is wanted and still shallow.

## Segment map

### A. Carbon-aware computing / grid data (our data layer + dev-scheduler mode)
| Product | What | Free tier reality | Gap |
|---|---|---|---|
| **Electricity Maps** | 200+ region carbon intensity, 72h forecast | 1 zone, **non-commercial, no forecast**; commercial €6k+/country/yr | priced out of indie/SMB; pure data, no UX |
| **WattTime** | marginal emissions (MOER), 24/72h forecast | 1 US region only; real data = Pro sales call | hard to self-serve; data only |
| **UK Carbon Intensity API** | GB national + 14 regions, **96h forecast** | **fully free, CC-BY, no auth** | raw feed, UK-only, no task UX ← **our backbone** |
| **RTE éCO2mix** (FR) | gCO₂/kWh, mix, regional | free, 50k calls/mo | raw, FR-only |
| **GSF Carbon Aware SDK / KEDA operator** | OSS "when is greenest" toolkit / k8s scaler | free OSS | toolkit not product; KEDA operator stale since 2023; needs paid data + ops |
| **Google Carbon-Intelligent / MS Carbon-aware** | internal/Azure-locked workload shifting | n/a | not buyable / locked-in; validates the idea works |
| **WhenToPlugIn, GridCarbon** | consumer "cleanest 48h" apps | free | UK-only, no weather, no price, no task model, no dev workloads |

**Opening:** the underserved middle — dev/AI/data teams too small for €6k data contracts and too non-Kubernetes for the OSS operators. Nothing exists between "read a free API yourself" and "buy enterprise data + deploy an abandoned operator."

### B. Consumer home energy (MVP A target)
| Product | Axis | Lock-in | Notes |
|---|---|---|---|
| **Octopus Agile / Intelligent** | price (carbon implicit) | switch supplier | dominant UK; EV-centric automation; blog literally shows users *manually* checking weather |
| **Tibber** | price | switch supplier | **not in UK**; NO/SE/DE/NL only |
| **ev.energy / Ohme / Indra** | price + carbon | EV + (hardware) | EV-only; Ohme has a rare explicit carbon/price toggle + leaf score |
| **NESO Carbon app / WWF / Loop** | carbon | none (free) | **passive dashboards**, 24–48h, no weather, no price, no task scheduling, no reminders |
| **Nest Renew** | carbon + price + comfort | Nest hardware, **US-only** | closest carbon+comfort blend, but HVAC-only, not in UK |
| **Samsung SmartThings Energy** | carbon + price | Samsung appliances | closed ecosystem |
| **Peg It! / DryCast / Washcast** | weather only | none | prove "best time to dry laundry" demand; zero carbon/price |
| **Home Assistant + Carbon Intensity** | carbon (+ DIY weather/price) | DIY/hobbyist | the capability exists only for technical tinkerers — productise it for families |

**Opening:** combine the accessibility of the free dashboards with the active scheduling that today requires a supplier/hardware — across *all* household tasks, not just EV.

### C. Weather-activity planners (weather modes)
- **Run Window** ⭐ — personalised, ranks *every hour* against your tolerances, returns **primary + backup window**, 16-day, learns from feedback. **This is the UX bar.** Running-only, no carbon.
- **Weather.com GORun / AccuWeather indices** — mainstream, but mostly *daily* 1–10 scores; user still hunts for the hour.
- **tenki.jp laundry index** — proves drying-index demand (Japan), but daily-only, no carbon, no dryer-avoidance framing.
- **Windguru/Windy/Tempest** — threshold alerts ("notify when wind 18–25kt") = a pattern worth stealing.
- **None combine weather suitability with carbon.** Confirmed.

### D. B2B / ESG ops (MVP B target)
- **BrainBox AI / 75F / Verdigris / Schneider / Siemens / JCI** — AI HVAC/BMS optimizers: powerful but **require hardware/BMS + integrators + enterprise budgets + sales calls.** None free/self-serve/SME.
- **Watershed / Greenly / Normative / Sweep / Persefoni / Aclymate / Sumday** — ESG carbon accounting: they **report** emissions, never tell you operationally **when** to run a task. (Aclymate/Sumday prove SMEs adopt cheap/free climate tools.)
- **Octopus "Shape Shifters" for Business** — closest SME analog: a *tariff + price portal*, supplier-locked, price-led, no task-level recommendations.
- **RAG over ESG docs** exists only inside enterprise suites (Microsoft Sustainability Copilot, Schneider Resource Advisor Copilot) or DIY AWS architectures — **no SME-priced "explain my plan + weekly brief" copilot.**

**Opening:** the white space between "carbon accounting" (backward-looking reporting) and "BMS control" (expensive automation) = **forward-looking operational recommendations, no hardware, for cafés/gyms/schools/coworking.** Empty.

## What to steal (proven patterns)
1. **Named window, not a chart** — primary + backup + one-line reason (Run Window).
2. **Personalisation + learning loop** — capture cold/wind/humidity/pollen tolerances; learn from feedback (Run Window).
3. **Explicit carbon-vs-price toggle** with comfort guardrails: "Save money / Go green / Balanced" (Ohme, but for the whole home).
4. **Threshold alerts / push** framed around the *outcome* ("good drying window opens at 1pm", "event risk crossed caution") (Windguru, Equiwatt, Tempest).
5. **Quantified dual savings per action** — "£0.45 / 1.5 kg CO₂ saved" (Loop "15% / 250kg", DryTime "0.03g vs 1.8kg per cycle").
6. **Climatology → near-term-forecast handoff** for event planning far out (Visual Crossing).

## Biggest improvements vs the original concept
1. **Elevate PRICE to a first-class axis** (doc had it at 10% "if available"). Research: money motivates more than CO₂ for most users, and the data is free (Octopus Agile API / éCO2mix-adjacent). Make carbon + price + weather + comfort all first-class, user-weighted.
2. **Lead every recommendation with a tangible number** (£ + kg CO₂ saved vs the naive default), not a score.
3. **Make laundry-drying a flagship** weather×carbon feature for the West (proven in JP, novel here, ties to dryer-avoidance carbon).
4. **Ship outcome-framed notifications**, not just a dashboard.
5. **Add a personalisation profile + feedback loop** as the moat the big players lack.
6. **Pick ONE killer wedge to launch:** carbon × weather × comfort for London households, with named windows + savings. Everything else (office, dev scheduler, RAG, multi-city) is roadmap.

## Threats to watch
- **Octopus** could bolt "what to run when" onto Agile/Shape Shifters and reach users via tariff distribution.
- **NESO/WWF** consumer apps could add weather or a "business" mode.
- Defensibility is **not** the grid signal (free/commoditised) — it's the **scoring/window engine + personalisation + the weather fusion + the explanation/brief layer.**
