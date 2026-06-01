import { useState, useEffect, useCallback } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, Legend, Brush,
} from "recharts";

// ── constants ──────────────────────────────────────────────────────────────

const CITIES = [
  { id: "london",  label: "🇬🇧 London",  tz: "Europe/London"   },
  { id: "paris",   label: "🇫🇷 Paris",   tz: "Europe/Paris"    },
  { id: "antwerp", label: "🇧🇪 Antwerp", tz: "Europe/Brussels" },
];

const MODES = [
  { id: "balanced", label: "⚖️ Balanced"   },
  { id: "green",    label: "💚 Go Green"   },
  { id: "money",    label: "💰 Save Money" },
];

const TASK_TYPES = [
  { id: "laundry_airdry", label: "🌬️ Laundry (air-dry)",    defaultDuration: 120, windowStart: "08:00", windowEnd: "20:00" },
  { id: "laundry_dryer",  label: "🔄 Laundry + dryer",       defaultDuration: 120, windowStart: "08:00", windowEnd: "22:00" },
  { id: "dishwasher",     label: "🍽️ Dishwasher",            defaultDuration: 90,  windowStart: "20:00", windowEnd: "23:00" },
  { id: "ev_charge",      label: "⚡ EV charging",            defaultDuration: 240, windowStart: "22:00", windowEnd: "23:59", deadline: "07:00" },
  { id: "ventilation",    label: "🪟 Ventilate",              defaultDuration: 30,  windowStart: "07:00", windowEnd: "21:00" },
];

const LOADING_LABELS = {
  plan:    "Fetching grid conditions…",
  compare: "Running scenario comparison…",
  weekly:  "Building 7-day outlook…",
  history: "Loading plan history…",
};

const CHART_COLORS = {
  dark:  { green: "#4ade80", blue: "#7dd3fc", yellow: "#fbbf24", grid: "#1c2128", tick: "#6b7280", brush: "#30363d", brushFill: "#161b22" },
  light: { green: "#16a34a", blue: "#0369a1", yellow: "#d97706", grid: "#e2e8f0", tick: "#94a3b8", brush: "#cbd5e1", brushFill: "#f0f4f8" },
};

// ── theme hook ─────────────────────────────────────────────────────────────

function useTheme() {
  const [theme, setTheme] = useState(() => localStorage.getItem("cp-theme") || "dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("cp-theme", theme);
  }, [theme]);

  const toggle = useCallback(() => setTheme(t => t === "dark" ? "light" : "dark"), []);
  return [theme, toggle];
}

// ── helpers ────────────────────────────────────────────────────────────────

function fmtTime(isoStr, tz = "Europe/London") {
  if (!isoStr) return "—";
  return new Date(isoStr).toLocaleString("en-GB", {
    weekday: "short", hour: "2-digit", minute: "2-digit", timeZone: tz,
  });
}

function fmtAxis(isoStr, tz = "Europe/London") {
  return new Date(isoStr).toLocaleString("en-GB", {
    hour: "2-digit", minute: "2-digit", timeZone: tz,
  });
}

// ── ui components ──────────────────────────────────────────────────────────

function ThemeToggle({ theme, onToggle }) {
  return (
    <button
      className="theme-toggle"
      onClick={onToggle}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
    >
      {theme === "dark" ? "☀" : "☾"}
    </button>
  );
}

const CustomTooltip = ({ active, payload, label, tz }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-time">{fmtAxis(label, tz)}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color }} className="chart-tooltip-row">
          {p.name}: <b>{Math.round(p.value)}</b>
        </p>
      ))}
    </div>
  );
};

function SkeletonCard() {
  return (
    <div className="rec-card skeleton-card" aria-hidden="true">
      <div className="sk-line sk-wide" />
      <div className="sk-line sk-medium" />
      <div className="sk-line sk-narrow" />
    </div>
  );
}

function LoadingResults({ action }) {
  return (
    <div className="loading-results" role="status" aria-live="polite">
      <p className="results-header loading-header">{LOADING_LABELS[action] || "Loading…"}</p>
      <SkeletonCard />
      <SkeletonCard />
    </div>
  );
}

function ErrorCard({ message, onRetry }) {
  return (
    <div className="error-card" role="alert">
      <span className="error-icon">⚠</span>
      <div className="error-body">
        <p className="error-title">Something went wrong</p>
        <p className="error-detail">{message}</p>
      </div>
      {onRetry && (
        <button className="error-retry" onClick={onRetry}>Try again</button>
      )}
    </div>
  );
}

// ── feature components ─────────────────────────────────────────────────────

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
          <span className="rec-window-time">
            {fmtTime(rec.primary_start, tz)} – {fmtTime(rec.primary_end, tz)}
          </span>
        </div>
        {rec.backup_start && (
          <div className="rec-window-block">
            <span className="rec-window-label">Backup</span>
            <span className="rec-backup-time">
              {fmtTime(rec.backup_start, tz)} – {fmtTime(rec.backup_end, tz)}
            </span>
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

function Timeline({ slots, recommendations, tz = "Europe/London", theme = "dark" }) {
  if (!slots?.length) return null;

  const c = CHART_COLORS[theme] || CHART_COLORS.dark;

  const chartData = slots.map(s => ({
    start: s.start,
    Carbon: Math.round(s.carbon_score ?? 0),
    Price:  s.price_score != null ? Math.round(s.price_score) : null,
  }));

  const windowLines = (recommendations ?? [])
    .filter(r => r.primary_start)
    .map(r => ({ x: r.primary_start, label: r.task_label.split("(")[0].trim() }));

  const tickInterval = Math.max(1, Math.floor(slots.length / 10));

  return (
    <div className="chart-wrap">
      <div className="chart-header">
        <h3 className="chart-title">
          48-h grid · {tz.split("/")[1].replace("_", " ")}
        </h3>
        <span className="chart-hint">drag handles to zoom · pan to explore</span>
      </div>
      <ResponsiveContainer width="100%" height={288}>
        <AreaChart data={chartData} margin={{ top: 6, right: 8, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="gc" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={c.green} stopOpacity={0.35} />
              <stop offset="95%" stopColor={c.green} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gp" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={c.blue} stopOpacity={0.35} />
              <stop offset="95%" stopColor={c.blue} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
          <XAxis
            dataKey="start"
            tickFormatter={v => fmtAxis(v, tz)}
            interval={tickInterval}
            tick={{ fontSize: 11, fill: c.tick }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: c.tick }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<CustomTooltip tz={tz} />} />
          <Legend wrapperStyle={{ fontSize: 12, color: c.tick, paddingTop: 6 }} />
          <Area
            type="monotone" dataKey="Carbon"
            stroke={c.green} fill="url(#gc)"
            strokeWidth={2} dot={false} connectNulls
            activeDot={{ r: 4, strokeWidth: 0, fill: c.green }}
          />
          <Area
            type="monotone" dataKey="Price"
            stroke={c.blue} fill="url(#gp)"
            strokeWidth={2} dot={false} connectNulls
            activeDot={{ r: 4, strokeWidth: 0, fill: c.blue }}
          />
          {windowLines.map((w, i) => (
            <ReferenceLine
              key={i} x={w.x}
              stroke={c.yellow} strokeDasharray="4 3" strokeWidth={2}
              label={{ value: "▶", position: "insideTopRight", fill: c.yellow, fontSize: 10 }}
            />
          ))}
          <Brush
            dataKey="start"
            height={26}
            stroke={c.brush}
            fill={c.brushFill}
            travellerWidth={8}
            tickFormatter={v => fmtAxis(v, tz)}
          />
        </AreaChart>
      </ResponsiveContainer>
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
                        {fmtTime(t.best_start, tz)} · {Math.round(t.score)}
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
  const modeLabels = { balanced: "⚖️ Balanced", green: "💚 Go Green", money: "💰 Save Money" };

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

function HistoryView({ plans, onFeedback, feedbackSent }) {
  if (!plans?.length) {
    return (
      <div className="empty-state">
        <p className="empty-icon">📋</p>
        <p className="empty-title">No plans yet</p>
        <p className="empty-body">Get a recommendation to start tracking your history.</p>
      </div>
    );
  }

  const modeLabel = { balanced: "⚖️ Balanced", green: "💚 Green", money: "💰 Money" };
  const modeClass = { balanced: "", green: "green", money: "money" };

  return (
    <div>
      <p className="results-header">Recent plans</p>
      <div className="history-list">
        {plans.map(plan => (
          <div key={plan.id} className="history-item">
            <div className="history-item-header">
              <span className="history-item-meta">
                {plan.location} · {new Date(plan.created_at).toLocaleString("en-GB", {
                  day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
                })}
              </span>
              <span className={`history-item-mode ${modeClass[plan.mode] || ""}`}>
                {modeLabel[plan.mode] || plan.mode}
              </span>
            </div>
            <div className="history-recs">
              {plan.recommendations.map(rec => {
                const key = `${plan.id}:${rec.task_type}`;
                const sent = feedbackSent.has(key);
                return (
                  <div key={rec.task_type} className="history-rec-row">
                    <span className="history-rec-label">{rec.task_label}</span>
                    <span className="history-rec-time">
                      {fmtTime(rec.primary_start, "Europe/London")}
                    </span>
                    {rec.carbon_saved_kg > 0.02 && (
                      <span className="history-rec-saving">
                        ↓ {rec.carbon_saved_kg.toFixed(1)} kg
                      </span>
                    )}
                    <div className="feedback-btns">
                      <button
                        className={`feedback-btn${sent ? " sent" : ""}`}
                        disabled={sent}
                        title="I followed this"
                        aria-label="Mark as followed"
                        onClick={() => !sent && onFeedback(plan.id, rec.task_type, true)}
                      >✓</button>
                      <button
                        className={`feedback-btn${sent ? " sent" : ""}`}
                        disabled={sent}
                        title="I didn't follow this"
                        aria-label="Mark as not followed"
                        onClick={() => !sent && onFeedback(plan.id, rec.task_type, false)}
                      >✗</button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── main App ───────────────────────────────────────────────────────────────

export default function App() {
  const [theme, toggleTheme] = useTheme();

  const [city, setCity]   = useState("london");
  const [mode, setMode]   = useState("balanced");
  const [tasks, setTasks] = useState([
    { ...TASK_TYPES[0], duration_mins: TASK_TYPES[0].defaultDuration },
  ]);

  const [result,  setResult]  = useState(null);
  const [compare, setCompare] = useState(null);
  const [weekly,  setWeekly]  = useState(null);
  const [history, setHistory] = useState(null);
  const [feedbackSent, setFeedbackSent] = useState(new Set());

  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState(null);
  const [lastAction, setLastAction] = useState(null);

  const cityTz = CITIES.find(c => c.id === city)?.tz ?? "Europe/London";

  function clearResults() {
    setResult(null); setCompare(null); setWeekly(null); setHistory(null); setError(null);
  }

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

  async function runAction(actionKey, fetchFn, onData) {
    setLoading(true);
    clearResults();
    setLastAction(actionKey);
    try {
      const res = await fetchFn();
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        let msg = `${res.status}`;
        try { const j = JSON.parse(body); if (j.detail) msg += `: ${j.detail}`; } catch (_) {}
        throw new Error(msg);
      }
      onData(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function getPlan() {
    return runAction("plan",
      () => fetch("/api/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city, mode, tasks: taskPayload() }),
      }),
      data => setResult(data),
    );
  }

  function getCompare() {
    return runAction("compare",
      () => fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city, tasks: taskPayload() }),
      }),
      data => setCompare(data),
    );
  }

  function getWeekly() {
    return runAction("weekly",
      () => fetch("/api/weekly", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city, tasks: taskPayload() }),
      }),
      data => setWeekly(data),
    );
  }

  function getHistory() {
    return runAction("history",
      () => fetch("/api/plans"),
      data => setHistory(data.plans),
    );
  }

  async function sendFeedback(planId, taskType, followed) {
    const key = `${planId}:${taskType}`;
    setFeedbackSent(prev => new Set([...prev, key]));
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: planId, task_type: taskType, followed }),
      });
    } catch (_) {}
  }

  function retry() {
    if (lastAction === "plan")    getPlan();
    else if (lastAction === "compare") getCompare();
    else if (lastAction === "weekly")  getWeekly();
    else if (lastAction === "history") getHistory();
  }

  const addedIds = new Set(tasks.map(t => t.id));

  return (
    <div className="container">
      {/* Hero */}
      <header className="hero">
        <div className="hero-text">
          <h1>Climate &amp; Carbon-Aware <span>Planner</span></h1>
          <p className="muted">Find the best time for your tasks — low-carbon, low-cost, weather-ready</p>
        </div>
        <ThemeToggle theme={theme} onToggle={toggleTheme} />
      </header>

      {/* City */}
      <div className="card">
        <div className="card-title">City</div>
        <div className="btn-group">
          {CITIES.map(c => (
            <button
              key={c.id}
              className={`seg-btn${city === c.id ? " active" : ""}`}
              onClick={() => { setCity(c.id); clearResults(); }}
            >
              {c.label}
            </button>
          ))}
        </div>
        {city !== "london" && (
          <p className="city-note">
            {city === "paris"
              ? "Carbon: RTE éco2mix cyclical proxy · Price data unavailable"
              : "Carbon: Elia ods192 (consumption-based CO₂) · Price data unavailable"}
          </p>
        )}
      </div>

      {/* Mode */}
      <div className="card">
        <div className="card-title">Optimise for</div>
        <div className="btn-group">
          {MODES.map(m => (
            <button
              key={m.id}
              className={`seg-btn${mode === m.id ? " active" : ""}`}
              onClick={() => setMode(m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Task builder */}
      <div className="card">
        <div className="card-title">Tasks</div>

        <div className="chip-row">
          {TASK_TYPES.map(t => (
            <button
              key={t.id}
              className={`chip${addedIds.has(t.id) ? " active" : ""}`}
              onClick={() => addTask(t)}
              disabled={addedIds.has(t.id)}
              aria-pressed={addedIds.has(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tasks.length > 0 && (
          <div className="task-list">
            {tasks.map(t => (
              <div key={t.id} className="task-row">
                <span className="task-name">{t.label}</span>
                <div className="task-controls">
                  <div className="task-field">
                    <label htmlFor={`dur-${t.id}`}>Duration</label>
                    <div className="input-with-unit">
                      <input
                        id={`dur-${t.id}`}
                        type="number" min={30} step={30}
                        value={t.duration_mins}
                        onChange={e => updateTask(t.id, "duration_mins", e.target.value)}
                      />
                      <span className="unit">min</span>
                    </div>
                  </div>
                  <div className="task-field">
                    <label>Window</label>
                    <div className="time-range">
                      <input
                        type="time" value={t.windowStart}
                        onChange={e => updateTask(t.id, "windowStart", e.target.value)}
                      />
                      <span className="time-sep">–</span>
                      <input
                        type="time" value={t.windowEnd}
                        onChange={e => updateTask(t.id, "windowEnd", e.target.value)}
                      />
                    </div>
                  </div>
                </div>
                <button
                  className="remove-btn"
                  onClick={() => removeTask(t.id)}
                  aria-label={`Remove ${t.label}`}
                >✕</button>
              </div>
            ))}
          </div>
        )}

        <div className="action-row">
          <button
            className="btn-primary"
            onClick={getPlan}
            disabled={loading || tasks.length === 0}
          >
            {loading && lastAction === "plan"
              ? <><span className="spinner" aria-hidden="true" /> Fetching…</>
              : "Get Recommendations →"}
          </button>
          <button
            className="btn-outline"
            onClick={getCompare}
            disabled={loading || tasks.length === 0}
          >
            {loading && lastAction === "compare"
              ? <><span className="spinner" aria-hidden="true" /> …</>
              : "Compare modes"}
          </button>
          <button
            className="btn-outline blue"
            onClick={getWeekly}
            disabled={loading || tasks.length === 0}
          >
            {loading && lastAction === "weekly"
              ? <><span className="spinner" aria-hidden="true" /> …</>
              : "7-day outlook"}
          </button>
          <button
            className="btn-outline purple"
            onClick={getHistory}
            disabled={loading}
          >
            {loading && lastAction === "history"
              ? <><span className="spinner" aria-hidden="true" /> …</>
              : "History"}
          </button>
        </div>
      </div>

      {/* Loading */}
      {loading && <LoadingResults action={lastAction} />}

      {/* Error */}
      {!loading && error && <ErrorCard message={error} onRetry={retry} />}

      {/* Recommendations */}
      {!loading && result && (
        <>
          <p className="results-header">
            Recommendations · {result.location} · <b>{result.mode}</b>
            {result.carbon_label && <span className="carbon-label"> · {result.carbon_label}</span>}
          </p>
          {result.recommendations.map((r, i) => (
            <RecCard key={i} rec={r} tz={cityTz} />
          ))}
          <Timeline
            slots={result.slots}
            recommendations={result.recommendations}
            tz={cityTz}
            theme={theme}
          />
        </>
      )}

      {/* Comparison */}
      {!loading && compare && (
        <>
          <CompareView result={compare} tz={cityTz} />
          <Timeline
            slots={compare.slots}
            recommendations={compare.modes.balanced}
            tz={cityTz}
            theme={theme}
          />
        </>
      )}

      {/* Weekly */}
      {!loading && weekly && <WeeklyView result={weekly} tz={cityTz} />}

      {/* History */}
      {!loading && history !== null && (
        <HistoryView
          plans={history}
          onFeedback={sendFeedback}
          feedbackSent={feedbackSent}
        />
      )}
    </div>
  );
}
