// SpendLens — Supplier Due Diligence (Hades) screen
const { useState: useS, useEffect: useE } = React;

const HADES_URL = "/api/hades";

const normaliseReport = (r) => ({
  risk_score:        r.overall_risk_score,
  risk_level:        r.risk_level,
  recommendation:    r.recommendation,
  executive_summary: r.executive_summary,
  sanctions_clear:   r.sanctions_status?.is_sanctioned === false,
  lksg_signal:       r.lksg_csddd_assessment?.conclusion || r.lksg_csddd_assessment?.compliance_signal,
  next_steps:        r.required_next_steps || [],
  _raw:              r,
});

function SupplierDD({ openDrawer, api }) {
  const [vendor, setVendor] = useS("");
  const [category, setCategory] = useS("Professional Services");
  const [country, setCountry] = useS("DE");
  const [mode, setMode] = useS("compliance");
  const [running, setRunning] = useS(false);
  const [report, setReport] = useS(null);
  const [error, setError] = useS("");
  const [hadesStatus, setHadesStatus] = useS("unknown"); // "online" | "offline" | "unknown"

  useE(() => {
    fetch(`${HADES_URL}/health`, { signal: AbortSignal.timeout(8000) })
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

    try {
      const res = await fetch(`${HADES_URL}/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company: vendor, category, country, mode }),
        signal: AbortSignal.timeout(120000),
      });
      if (!res.ok) throw new Error(`Hades returned ${res.status}`);
      const data = await res.json();
      setHadesStatus("online");
      setRunning(false);
      if (data.report) setReport(normaliseReport(data.report));
      else setError("Investigation returned no report");
    } catch (e) {
      setHadesStatus("offline");
      setError("Could not reach Hades. The service may be cold-starting on Railway (~30s) — try again in a moment.");
      setRunning(false);
    }
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

      {/* Running indicator */}
      {running && (
        <div className="card" style={{ display: "flex", alignItems: "center", gap: 12, padding: 20 }}>
          <div className="spin" style={{ width: 20, height: 20, flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>Running investigation…</div>
            <div className="txt-sm txt-muted" style={{ marginTop: 2 }}>Sanctions · Registry · News · LkSG · ESG · Hermes — takes ~60s</div>
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

          {(report.recommendation || report.executive_summary) && (
            <div className="ai-card">
              <div className="ai-h">
                <div className="ai-mark"><Icons.Spark size={14} /></div>
                <div><div className="ai-title">Recommendation: {report.recommendation}</div></div>
              </div>
              {report.executive_summary && (
                <div className="ai-insights">
                  <div className="ai-insight"><div className="marker" /><div>{report.executive_summary}</div></div>
                </div>
              )}
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
