import { useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, Legend,
} from "recharts";

// ── constants ──────────────────────────────────────────────────────────────

const CITIES = [
  { id: "london",  label: "🇬🇧 London",  tz: "Europe/London"   },
  { id: "paris",   label: "🇫🇷 Paris",   tz: "Europe/Paris"    },
  { id: "antwerp", label: "🇧🇪 Antwerp", tz: "Europe/Brussels" },
];

const MODES = [
  { id: "balanced", label: "⚖️ Balanced" },
  { id: "green",    label: "💚 Go Green" },
  { id: "money",    label: "💰 Save Money" },
];

const TASK_TYPES = [
  { id: "laundry_airdry", label: "🌬️ Laundry (air-dry)", defaultDuration: 120, windowStart: "08:00", windowEnd: "20:00" },
  { id: "laundry_dryer",  label: "🔄 Laundry + dryer",   defaultDuration: 120, windowStart: "08:00", windowEnd: "22:00" },
  { id: "dishwasher",     label: "🍽️ Dishwasher",         defaultDuration: 90,  windowStart: "20:00", windowEnd: "23:00" },
  { id: "ev_charge",      label: "⚡ EV / device charging", defaultDuration: 240, windowStart: "22:00", windowEnd: "23:59", deadline: "07:00" },
  { id: "ventilation",    label: "🪟 Ventilate",           defaultDuration: 30,  windowStart: "07:00", windowEnd: "21:00" },
];

// ── helpers ────────────────────────────────────────────────────────────────

function fmtTime(isoStr, tz = "Europe/London") {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  return d.toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: tz });
}

function fmtAxis(isoStr, tz = "Europe/London") {
  const d = new Date(isoStr);
  return d.toLocaleString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: tz });
}

const CustomTooltip = ({ active, payload, label, tz }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 6, padding: "8px 12px", fontSize: 12 }}>
      <p style={{ color: "#94a3b8", marginBottom: 4 }}>{fmtAxis(label, tz)}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: <b>{Math.round(p.value)}</b>
        </p>
      ))}
    </div>
  );
};

// ── components ─────────────────────────────────────────────────────────────

function RecCard({ rec, tz }) {
  return (
    <div className="rec-card">
      <div className="rec-header">
        <span className="rec-task">{rec.task_label}</span>
        <span className="rec-score">score {Math.round(rec.score)}/100</span>
      </div>

      <div className="rec-windows">
        <div className="rec-window-block">
          <span className="rec-window-label">Best window</span>
          <span className="rec-window-time">{fmtTime(rec.primary_start, tz)} – {fmtTime(rec.primary_end, tz)}</span>
        </div>
        {rec.backup_start && (
          <div className="rec-window-block">
            <span className="rec-window-label">Backup</span>
            <span className="rec-backup-time">{fmtTime(rec.backup_start, tz)} – {fmtTime(rec.backup_end, tz)}</span>
          </div>
        )}
      </div>

      <div className="rec-savings">
        {rec.carbon_saved_kg > 0.02 && (
          <span className="saving-pill co2">↓ {rec.carbon_saved_kg.toFixed(1)} kg CO₂</span>
        )}
        {rec.cost_saved_gbp > 0.01 && (
          <span className="saving-pill cost">↓ £{rec.cost_saved_gbp.toFixed(2)}</span>
        )}
      </div>

      <p className="rec-reason">{rec.reason}</p>
    </div>
  );
}

function WeeklyView({ result, tz }) {
  if (!result) return null;
  return (
    <div>
      <p className="results-header">
        7-Day Outlook · {result.location}
        {result.carbon_label && <span className="carbon-label"> · {result.carbon_label}</span>}
      </p>
      <div className="weekly-grid">
        {result.days.map(day => (
          <div key={day.date} className="weekly-day">
            <div className="weekly-day-header">
              <span className="weekly-day-label">{day.day_label}</span>
              <span className="rec-score">{Math.round(day.avg_carbon_score)}/100 avg</span>
            </div>
            <div className="weekly-tasks">
              {day.tasks.map(t => (
                <div key={t.task_type} className="weekly-task-rec">
                  <span className="weekly-task-name">{t.task_label}</span>
                  {t.best_start
                    ? <span className="weekly-task-time">
                        {fmtTime(t.best_start, tz)} · score {Math.round(t.score)}
                      </span>
                    : <span className="weekly-no-window">no window</span>
                  }
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      {result.brief && (
        <div className="weekly-brief">
          <div className="card-title">Weekly Brief</div>
          <p className="weekly-brief-text">{result.brief}</p>
        </div>
      )}
    </div>
  );
}

function CompareView({ result, tz }) {
  if (!result) return null;
  const taskTypes = result.tasks;
  const modeLabels = { balanced: "⚖️ Balanced", green: "💚 Go Green", money: "💰 Save Money" };

  // Group by task — show 3 mode cards per task
  const allTasks = result.modes.balanced.map((_, i) => ({
    balanced: result.modes.balanced[i],
    green:    result.modes.green[i],
    money:    result.modes.money[i],
  }));

  return (
    <div>
      <p className="results-header">
        Scenario comparison · {result.location}
        {result.carbon_label && <span className="carbon-label"> · {result.carbon_label}</span>}
      </p>
      {allTasks.map((group, i) => (
        <div key={i} className="compare-group">
          <div className="compare-task-name">{group.balanced.task_label}</div>
          <div className="compare-cols">
            {["balanced", "green", "money"].map(mode => (
              <div key={mode} className="compare-col">
                <div className="compare-mode-label">{modeLabels[mode]}</div>
                <RecCard rec={group[mode]} tz={tz} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function Timeline({ slots, recommendations, tz = "Europe/London" }) {
  if (!slots?.length) return null;

  const chartData = slots.map(s => ({
    start: s.start,
    "Carbon score": Math.round(s.carbon_score ?? 0),
    "Price score":  s.price_score != null ? Math.round(s.price_score) : null,
  }));

  const windowLines = (recommendations ?? []).flatMap(r => [
    r.primary_start ? { x: r.primary_start, label: r.task_label.split("(")[0].trim() } : null,
  ]).filter(Boolean);

  const tickInterval = Math.max(1, Math.floor(slots.length / 12));

  return (
    <div className="chart-wrap">
      <h3>48-hour conditions — {tz.split("/")[1].replace("_", " ")} (higher = better slot)</h3>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="gc" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#4ade80" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#4ade80" stopOpacity={0.0} />
            </linearGradient>
            <linearGradient id="gp" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#7dd3fc" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#7dd3fc" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
          <XAxis
            dataKey="start"
            tickFormatter={v => fmtAxis(v, tz)}
            interval={tickInterval}
            tick={{ fontSize: 11, fill: "#6b7280" }}
            tickLine={false}
          />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#6b7280" }} tickLine={false} axisLine={false} />
          <Tooltip content={<CustomTooltip tz={tz} />} />
          <Legend wrapperStyle={{ fontSize: 12, color: "#94a3b8" }} />
          <Area type="monotone" dataKey="Carbon score" stroke="#4ade80" fill="url(#gc)" strokeWidth={2} dot={false} connectNulls />
          <Area type="monotone" dataKey="Price score"  stroke="#7dd3fc" fill="url(#gp)" strokeWidth={2} dot={false} connectNulls />
          {windowLines.map((w, i) => (
            <ReferenceLine
              key={i} x={w.x}
              stroke="#fbbf24" strokeDasharray="4 3" strokeWidth={2}
              label={{ value: "▶", position: "top", fill: "#fbbf24", fontSize: 10 }}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── main App ───────────────────────────────────────────────────────────────

export default function App() {
  const [city, setCity]       = useState("london");
  const [mode, setMode]       = useState("balanced");
  const [tasks, setTasks]     = useState([
    { ...TASK_TYPES[0], duration_mins: TASK_TYPES[0].defaultDuration },
  ]);
  const [result, setResult]   = useState(null);
  const [compare, setCompare] = useState(null);
  const [weekly, setWeekly]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const cityTz = CITIES.find(c => c.id === city)?.tz ?? "Europe/London";

  function addTask(type) {
    if (tasks.find(t => t.id === type.id)) return;
    setTasks(prev => [...prev, { ...type, duration_mins: type.defaultDuration }]);
  }

  function removeTask(id) {
    setTasks(prev => prev.filter(t => t.id !== id));
  }

  function updateTask(id, field, value) {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, [field]: value } : t));
  }

  const taskPayload = () => tasks.map(t => ({
    type: t.id,
    duration_mins: Number(t.duration_mins),
    window_start: t.windowStart,
    window_end: t.windowEnd,
    deadline: t.deadline ?? null,
  }));

  async function getPlan() {
    setLoading(true); setError(null); setResult(null); setCompare(null); setWeekly(null);
    try {
      const res = await fetch("/api/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city, mode, tasks: taskPayload() }),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      setResult(await res.json());
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  async function getCompare() {
    setLoading(true); setError(null); setResult(null); setCompare(null); setWeekly(null);
    try {
      const res = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city, tasks: taskPayload() }),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      setCompare(await res.json());
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  async function getWeekly() {
    setLoading(true); setError(null); setResult(null); setCompare(null); setWeekly(null);
    try {
      const res = await fetch("/api/weekly", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city, tasks: taskPayload() }),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      setWeekly(await res.json());
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  const addedIds = new Set(tasks.map(t => t.id));

  return (
    <div className="container">
      {/* Hero */}
      <div className="hero">
        <h1>Climate &amp; Carbon-Aware <span>Planner</span></h1>
        <p className="muted">Find the best time window for your tasks — low-carbon, low-cost, weather-ready</p>
      </div>

      {/* City */}
      <div className="card">
        <div className="card-title">City</div>
        <div className="mode-group">
          {CITIES.map(c => (
            <button
              key={c.id}
              className={`mode-btn${city === c.id ? " active" : ""}`}
              onClick={() => { setCity(c.id); setResult(null); setCompare(null); setWeekly(null); }}
            >
              {c.label}
            </button>
          ))}
        </div>
        {city !== "london" && (
          <p className="city-note">
            {city === "paris"
              ? "Carbon: RTE éco2mix cyclical proxy · Price data not available"
              : "Carbon: Elia open data ods192 (consumption-based CO₂) · Price data not available"}
          </p>
        )}
      </div>

      {/* Mode */}
      <div className="card">
        <div className="card-title">Optimise for</div>
        <div className="mode-group">
          {MODES.map(m => (
            <button
              key={m.id}
              className={`mode-btn${mode === m.id ? " active" : ""}`}
              onClick={() => setMode(m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Task builder */}
      <div className="card">
        <div className="card-title">Add tasks</div>
        <div className="task-chips">
          {TASK_TYPES.map(t => (
            <button
              key={t.id}
              className={`chip${addedIds.has(t.id) ? " active" : ""}`}
              onClick={() => addTask(t)}
              disabled={addedIds.has(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="task-list">
          {tasks.map(t => (
            <div key={t.id} className="task-row">
              <span className="task-name">{t.label}</span>
              <span>
                <label>Duration (min) </label>
                <input
                  type="number" min={30} step={30} value={t.duration_mins}
                  onChange={e => updateTask(t.id, "duration_mins", e.target.value)}
                />
              </span>
              <span>
                <label>Between </label>
                <input type="time" value={t.windowStart} onChange={e => updateTask(t.id, "windowStart", e.target.value)} />
                <label> – </label>
                <input type="time" value={t.windowEnd}   onChange={e => updateTask(t.id, "windowEnd",   e.target.value)} />
              </span>
              <button className="remove-btn" onClick={() => removeTask(t.id)} title="Remove">✕</button>
            </div>
          ))}
        </div>

        <div className="action-row">
          <button className="plan-btn" onClick={getPlan} disabled={loading || tasks.length === 0}>
            {loading ? "Fetching conditions…" : "Get Recommendations →"}
          </button>
          <button className="compare-btn" onClick={getCompare} disabled={loading || tasks.length === 0}>
            Compare all modes
          </button>
          <button className="weekly-btn" onClick={getWeekly} disabled={loading || tasks.length === 0}>
            Weekly brief
          </button>
        </div>

        {error && <p className="error-msg">Error: {error}</p>}
      </div>

      {/* Single-mode results */}
      {result && (
        <>
          <p className="results-header">
            Recommendations · {result.location} · mode: <b>{result.mode}</b>
            {result.carbon_label && <span className="carbon-label"> · {result.carbon_label}</span>}
          </p>
          {result.recommendations.map((r, i) => <RecCard key={i} rec={r} tz={cityTz} />)}
          <Timeline slots={result.slots} recommendations={result.recommendations} tz={cityTz} />
        </>
      )}

      {/* Comparison results */}
      {compare && (
        <>
          <CompareView result={compare} tz={cityTz} />
          <Timeline slots={compare.slots} recommendations={compare.modes.balanced} tz={cityTz} />
        </>
      )}

      {/* Weekly brief */}
      {weekly && <WeeklyView result={weekly} tz={cityTz} />}
    </div>
  );
}
