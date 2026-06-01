import { useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, Legend,
} from "recharts";

// ── constants ──────────────────────────────────────────────────────────────

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

function fmtTime(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  return d.toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
}

function fmtAxis(isoStr) {
  const d = new Date(isoStr);
  return d.toLocaleString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 6, padding: "8px 12px", fontSize: 12 }}>
      <p style={{ color: "#94a3b8", marginBottom: 4 }}>{fmtAxis(label)}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: <b>{Math.round(p.value)}</b>
        </p>
      ))}
    </div>
  );
};

// ── components ─────────────────────────────────────────────────────────────

function RecCard({ rec, idx }) {
  return (
    <div className="rec-card">
      <div className="rec-header">
        <span className="rec-task">{rec.task_label}</span>
        <span className="rec-score">score {Math.round(rec.score)}/100</span>
      </div>

      <div className="rec-windows">
        <div className="rec-window-block">
          <span className="rec-window-label">Best window</span>
          <span className="rec-window-time">{fmtTime(rec.primary_start)} – {fmtTime(rec.primary_end)}</span>
        </div>
        {rec.backup_start && (
          <div className="rec-window-block">
            <span className="rec-window-label">Backup</span>
            <span className="rec-backup-time">{fmtTime(rec.backup_start)} – {fmtTime(rec.backup_end)}</span>
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

function Timeline({ slots, recommendations }) {
  if (!slots?.length) return null;

  // Show every 4th slot label to avoid crowding
  const chartData = slots.map((s, i) => ({
    start: s.start,
    "Carbon score": Math.round(s.carbon_score ?? 0),
    "Price score":  s.price_score != null ? Math.round(s.price_score) : null,
  }));

  // Build reference lines for recommended windows (primary only)
  const windowLines = (recommendations ?? []).flatMap(r => [
    r.primary_start ? { x: r.primary_start, label: r.task_label.split("(")[0].trim() } : null,
  ]).filter(Boolean);

  const tickInterval = Math.max(1, Math.floor(slots.length / 12));

  return (
    <div className="chart-wrap">
      <h3>48-hour conditions — London (higher = better slot)</h3>
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
            tickFormatter={fmtAxis}
            interval={tickInterval}
            tick={{ fontSize: 11, fill: "#6b7280" }}
            tickLine={false}
          />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#6b7280" }} tickLine={false} axisLine={false} />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ fontSize: 12, color: "#94a3b8" }} />
          <Area
            type="monotone"
            dataKey="Carbon score"
            stroke="#4ade80"
            fill="url(#gc)"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          <Area
            type="monotone"
            dataKey="Price score"
            stroke="#7dd3fc"
            fill="url(#gp)"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          {windowLines.map((w, i) => (
            <ReferenceLine
              key={i}
              x={w.x}
              stroke="#fbbf24"
              strokeDasharray="4 3"
              strokeWidth={2}
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
  const [mode, setMode] = useState("balanced");
  const [tasks, setTasks] = useState([
    { ...TASK_TYPES[0], duration_mins: TASK_TYPES[0].defaultDuration },
  ]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  function addTask(type) {
    if (tasks.find(t => t.id === type.id)) return; // no duplicates
    setTasks(prev => [...prev, { ...type, duration_mins: type.defaultDuration }]);
  }

  function removeTask(id) {
    setTasks(prev => prev.filter(t => t.id !== id));
  }

  function updateTask(id, field, value) {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, [field]: value } : t));
  }

  async function getPlan() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          location: "London",
          region_id: 13,
          mode,
          tasks: tasks.map(t => ({
            type: t.id,
            duration_mins: Number(t.duration_mins),
            window_start: t.windowStart,
            window_end: t.windowEnd,
            deadline: t.deadline ?? null,
          })),
        }),
      });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      setResult(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const addedIds = new Set(tasks.map(t => t.id));

  return (
    <div className="container">
      {/* Hero */}
      <div className="hero">
        <h1>Climate &amp; Carbon-Aware <span>Planner</span></h1>
        <p className="muted">Find the best time window for your tasks — low-carbon, low-cost, weather-ready · London</p>
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
                  type="number"
                  min={30}
                  step={30}
                  value={t.duration_mins}
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

        <button className="plan-btn" onClick={getPlan} disabled={loading || tasks.length === 0}>
          {loading ? "Fetching conditions…" : "Get Recommendations →"}
        </button>

        {error && <p className="error-msg">Error: {error}</p>}
      </div>

      {/* Results */}
      {result && (
        <>
          <p className="results-header">
            Recommendations · {result.location} · mode: <b>{result.mode}</b>
          </p>
          {result.recommendations.map((r, i) => <RecCard key={i} rec={r} idx={i} />)}
          <Timeline slots={result.slots} recommendations={result.recommendations} />
        </>
      )}
    </div>
  );
}
