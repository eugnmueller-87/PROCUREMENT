// SpendLens — Supplier Due Diligence (Hades) screen
const { useState: useS, useEffect: useE } = React;

const HADES_URL = "https://hades-production-b86a.up.railway.app";

const HADES_STEPS = [
  { id: "preflight",    label: "Pre-flight check" },
  { id: "web",          label: "Web research & background" },
  { id: "news",         label: "News sentiment (90 days)" },
  { id: "sanctions",    label: "Sanctions & watchlists (OFAC / UN SC)" },
  { id: "registry",     label: "Company registry lookup" },
  { id: "lksg",         label: "LkSG / CSDDD compliance signals" },
  { id: "esg",          label: "ESG & labour signals" },
  { id: "synthesis",    label: "Risk synthesis" },
  { id: "report",       label: "Report generation" },
  { id: "watchlist",    label: "Watchlist registration" },
];

function SupplierDD({ openDrawer, api }) {
  const [vendor, setVendor] = useS("");
  const [category, setCategory] = useS("Professional Services");
  const [country, setCountry] = useS("DE");
  const [mode, setMode] = useS("compliance");
  const [running, setRunning] = useS(false);
  const [steps, setSteps] = useS({});
  const [report, setReport] = useS(null);
  const [error, setError] = useS("");
  const [hadesStatus, setHadesStatus] = useS("unknown"); // "online" | "offline" | "unknown"

  useE(() => {
    fetch(`${HADES_URL}/health`, { signal: AbortSignal.timeout(4000) })
      .then(r => setHadesStatus(r.ok ? "online" : "offline"))
      .catch(() => setHadesStatus("offline"));
  }, []);

  const CATS = [
    "Cloud & Compute", "AI/ML APIs & Data", "IT Software & SaaS",
    "Telecom & Voice", "Recruitment & HR", "Professional Services",
    "Marketing & Campaigns", "Facilities & Office", "Real Estate",
    "Hardware & Equipment", "Travel & Expenses",
  ];

  const run = async () => {
    if (!vendor.trim()) { setError("Please enter a company name"); return; }
    setRunning(true);
    setError("");
    setReport(null);
    setSteps({});

    if (hadesStatus === "offline") {
      setError("Hades service is currently offline. The due diligence agent runs on Railway — check the deployment status or try again shortly.");
      setRunning(false);
      return;
    }
    try {
      const res = await fetch(`${HADES_URL}/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vendor_name: vendor, category, country, mode }),
        signal: AbortSignal.timeout(10000),
      });
      if (!res.ok) throw new Error(`Hades returned ${res.status}`);
      const { task_id } = await res.json();
      poll(task_id);
    } catch (e) {
      setHadesStatus("offline");
      setError("Could not reach Hades. The service may be starting up — Railway cold-starts take ~30 seconds. Try again in a moment.");
      setRunning(false);
    }
  };

  const poll = async (taskId) => {
    const interval = setInterval(async () => {
      try {
        const r = await fetch(`${HADES_URL}/result/${taskId}`);
        const d = await r.json();
        if (d.steps) setSteps(d.steps);
        if (d.status === "done" || d.status === "error") {
          clearInterval(interval);
          setRunning(false);
          if (d.report) setReport(d.report);
          if (d.status === "error") setError(d.error || "Investigation failed");
        }
      } catch (e) {
        clearInterval(interval);
        setRunning(false);
        setError("Lost connection to Hades");
      }
    }, 2000);
  };

  const stepState = (id) => {
    const s = steps[id];
    if (!s) return "pending";
    if (s.status === "done") return "done";
    if (s.status === "running") return "running";
    if (s.status === "error") return "error";
    return "pending";
  };

  const statusBadge = () => {
    if (hadesStatus === "online")  return <span className="chip good" style={{ fontSize: 11 }}><span className="dot" />Hades online</span>;
    if (hadesStatus === "offline") return <span className="chip bad"  style={{ fontSize: 11 }}><span className="dot" />Hades offline</span>;
    return <span className="chip" style={{ fontSize: 11, opacity: 0.6 }}>Checking…</span>;
  };

  const riskColor = (score) => {
    if (!score) return "var(--ink-4)";
    if (score >= 7) return "var(--bad)";
    if (score >= 4) return "var(--warn)";
    return "var(--good)";
  };

  return (
    <div className="col">
      <div className="page-h">
        <div><h1>Supplier Due Diligence</h1><div className="sub">Sanctions · LkSG/CSDDD · ESG · News · Registry</div></div>
        <div className="flex gap-2 center-y">{statusBadge()}</div>
      </div>

      {/* Input form */}
      <div className="card">
        <div className="grid" style={{ gridTemplateColumns: "1fr 1fr auto", gap: 20, alignItems: "end" }}>
          <div>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--ink-3)", marginBottom: 6 }}>Company Name</div>
            <input className="input" style={{ width: "100%" }} placeholder="e.g. Robert Bosch GmbH"
              value={vendor} onChange={e => setVendor(e.target.value)}
              onKeyDown={e => e.key === "Enter" && run()} />
          </div>
          <div>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--ink-3)", marginBottom: 6 }}>Category</div>
            <select className="select" style={{ width: "100%" }} value={category} onChange={e => setCategory(e.target.value)}>
              {CATS.map(c => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--ink-3)", marginBottom: 6 }}>Country</div>
            <input className="input" style={{ width: 80 }} value={country} onChange={e => setCountry(e.target.value)} />
          </div>
        </div>

        <div style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "center" }}>
          <div className="seg">
            <div className={`seg-opt${mode === "compliance" ? " on" : ""}`} onClick={() => setMode("compliance")}>Compliance Check</div>
            <div className={`seg-opt${mode === "onboard" ? " on" : ""}`} onClick={() => setMode("onboard")}>Onboard Supplier</div>
          </div>
          <div className="txt-sm txt-muted">
            {mode === "compliance" ? "Standalone risk check — no data written to SpendLens" : "Runs DD and saves result to SpendLens vendor database"}
          </div>
          <div style={{ marginLeft: "auto" }}>
            <button className="btn primary" onClick={run} disabled={running}>
              {running ? <><div className="spin" style={{ width: 14, height: 14 }} />Running…</> : <><Icons.Bolt size={14} />Run Investigation</>}
            </button>
          </div>
        </div>

        {error && <div style={{ marginTop: 12, padding: "10px 14px", background: "var(--bad-soft)", borderRadius: "var(--r-sm)", color: "var(--bad)", fontSize: 13 }}>{error}</div>}
      </div>

      {/* Pipeline progress */}
      {(running || Object.keys(steps).length > 0) && (
        <div className="card">
          <div className="card-h"><h3>Investigation Pipeline</h3></div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {HADES_STEPS.map(step => {
              const state = stepState(step.id);
              return (
                <div key={step.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "8px 0", borderBottom: "1px solid var(--hairline)" }}>
                  <div style={{ width: 20, display: "grid", placeItems: "center" }}>
                    {state === "done"    && <Icons.Check size={16} color="var(--good)" />}
                    {state === "running" && <div className="spin" style={{ width: 16, height: 16 }} />}
                    {state === "error"   && <Icons.X size={16} color="var(--bad)" />}
                    {state === "pending" && <div style={{ width: 10, height: 10, borderRadius: "50%", border: "1.5px solid var(--border-2)" }} />}
                  </div>
                  <div style={{ flex: 1, fontSize: 13, color: state === "pending" ? "var(--ink-4)" : "var(--ink)" }}>{step.label}</div>
                  {steps[step.id]?.summary && (
                    <div style={{ fontSize: 11, color: "var(--ink-3)", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{steps[step.id].summary}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Report */}
      {report && (
        <div className="col">
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            <div className="card" style={{ borderTop: `3px solid ${riskColor(report.risk_score)}` }}>
              <div className="kpi-label">Risk Score</div>
              <div className="kpi-value" style={{ color: riskColor(report.risk_score) }}>{report.risk_score?.toFixed(1)}</div>
              <div className="kpi-foot"><span>{report.risk_level}</span></div>
            </div>
            <div className="card">
              <div className="kpi-label">Sanctions</div>
              <div className="kpi-value" style={{ color: report.sanctions_clear ? "var(--good)" : "var(--bad)" }}>
                {report.sanctions_clear ? "Clear" : "Flagged"}
              </div>
            </div>
            <div className="card">
              <div className="kpi-label">LkSG Signal</div>
              <div style={{ fontSize: 13, marginTop: 8, color: "var(--ink-2)", lineHeight: 1.5 }}>{report.lksg_signal || "No signals found"}</div>
            </div>
          </div>

          {report.recommendation && (
            <div className="ai-card">
              <div className="ai-h">
                <div className="ai-mark"><Icons.Spark size={14} /></div>
                <div><div className="ai-title">Recommendation</div></div>
              </div>
              <div className="ai-insights">
                <div className="ai-insight"><div className="marker" /><div>{report.recommendation}</div></div>
              </div>
            </div>
          )}

          {report.next_steps?.length > 0 && (
            <div className="card">
              <div className="card-h"><h3>Next Steps</h3></div>
              <div className="ai-insights">
                {report.next_steps.map((s, i) => (
                  <div key={i} className="ai-insight"><div className="marker" /><div>{s}</div></div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

window.SupplierDD = SupplierDD;
