// SpendLens — Dashboard screen
const { useState: useS, useEffect: useE, useRef: useR } = React;

const CAT_COLORS = [
  "oklch(0.22 0.06 262)", "oklch(0.62 0.13 165)", "oklch(0.70 0.13 75)",
  "oklch(0.58 0.18 25)",  "oklch(0.55 0.10 230)", "oklch(0.45 0.10 300)",
  "oklch(0.65 0.15 200)", "oklch(0.72 0.12 50)",  "oklch(0.50 0.14 150)",
  "oklch(0.60 0.10 320)", "oklch(0.68 0.08 90)",
];

function Dashboard({ openDrawer, api }) {
  const [data, setData] = useS(null);
  const [year, setYear] = useS(null);
  const [loading, setLoading] = useS(true);
  const [uploading, setUploading] = useS(false);
  const [uploadMsg, setUploadMsg] = useS("");
  const fileRef = useR(null);

  const load = async (y) => {
    setLoading(true);
    try {
      const url = y ? `${api}/api/dashboard?year=${y}` : `${api}/api/dashboard`;
      const res = await fetch(url);
      const d = await res.json();
      setData(d);
      setYear(y || null);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useE(() => { load(null); }, []);

  const onUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    setUploadMsg("Processing...");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch(`${api}/api/upload`, { method: "POST", body: fd });
      const r = await res.json();
      if (r.status === "ok") {
        setUploadMsg(`✓ ${r.rows_inserted} rows loaded`);
        await load(year);
      } else {
        setUploadMsg("Upload failed");
      }
    } catch (e) {
      setUploadMsg("Error: " + e.message);
    }
    setUploading(false);
  };

  if (loading) return <div style={{ display: "grid", placeItems: "center", height: 400 }}><div className="spin" /></div>;
  if (!data) return <div style={{ padding: 40, color: "var(--ink-3)" }}>No data</div>;

  const { kpis, categories, trendYears, trendData, expiringContracts, years, _demo } = data;

  // Build stacked area series
  const series = (categories || []).slice(0, 11).map((c, i) => ({
    id: c.id, name: c.name,
    data: trendYears.map(y => (trendData[c.name] || {})[y] || 0),
    color: CAT_COLORS[i],
  }));

  const riskChip = (r) => {
    const map = { Critical: "bad", High: "warn", Medium: "info", Low: "good", critical: "bad", high: "warn", medium: "info", low: "good" };
    return <span className={`chip ${map[r] || "info"}`}><span className="dot" />{r}</span>;
  };

  return (
    <div className="col">
      {/* Header */}
      <div className="page-h">
        <div>
          <h1>Dashboard</h1>
          <div className="sub">Spend intelligence overview{_demo ? " — demo data" : ""}</div>
        </div>
        <div className="flex gap-2 center-y">
          {(years || []).length > 0 && (
            <select className="select" value={year || ""} onChange={e => load(e.target.value ? parseInt(e.target.value) : null)}>
              <option value="">All years</option>
              {years.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          )}
          <button className="btn" onClick={() => fileRef.current?.click()} disabled={uploading}>
            <Icons.Upload size={14} />{uploading ? "Uploading…" : "Upload Data"}
          </button>
          {uploadMsg && <span style={{ fontSize: 12, color: "var(--good)" }}>{uploadMsg}</span>}
          <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" style={{ display: "none" }}
            onChange={e => { onUpload(e.target.files[0]); e.target.value = ""; }} />
        </div>
      </div>

      {/* KPI row */}
      <div className="grid" style={{ gridTemplateColumns: "repeat(5,1fr)" }}>
        <KpiCard label="Total Spend" value={`€${kpis.totalSpend}M`} sub={year ? `${year} spend` : "All years"} accent={null} />
        <KpiCard label="YoY Growth" value={`${kpis.yoyGrowth > 0 ? "+" : ""}${kpis.yoyGrowth}%`} sub="vs prior year" accent={kpis.yoyGrowth > 0 ? "warn" : "good"} />
        <KpiCard label="EBITDA Impact" value={`€${kpis.ebitdaImpact}K`} sub="savings + avoidance" accent="good" />
        <KpiCard label="Contract Coverage" value={`${kpis.contractCoverage}%`} sub={`target 100%`} accent={kpis.contractCoverage < 80 ? "warn" : "good"} />
        <KpiCard label="Maverick Spend" value={`${kpis.maverickPct}%`} sub="target <5%" accent={kpis.maverickPct > 10 ? "bad" : kpis.maverickPct > 5 ? "warn" : "good"} />
      </div>

      {/* Charts row */}
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="card">
          <div className="card-h"><h3>Spend Evolution by Category (€M)</h3>{year && <span className="sub">highlighted: {year}</span>}</div>
          {series.length > 0
            ? <StackedArea series={series} xLabels={trendYears.map(String)} height={280} highlightX={year ? String(year) : null} />
            : <div style={{ height: 280, display: "grid", placeItems: "center", color: "var(--ink-4)" }}>No trend data</div>
          }
        </div>
        <div className="card">
          <div className="card-h"><h3>Spend vs Budget (€M)</h3></div>
          <SpendVsBudget
            data={(categories || []).slice(0, 10).map(c => ({ name: c.name, spend: c.spend, budget: c.budget }))}
            absMax={Math.max(...Object.values(trendData).map(y => Math.max(...Object.values(y))))}
          />
        </div>
      </div>

      {/* Risk matrix table */}
      <div className="card">
        <div className="card-h"><h3>Category Risk Matrix</h3><span className="sub">spend · risk · supplier count · budget variance</span></div>
        <CategoryRiskMatrix categories={categories} />
      </div>

      {/* Expiring contracts */}
      {expiringContracts?.length > 0 && (
        <div className="card">
          <div className="card-h"><h3>Expiring Contracts</h3><span className="sub">next 180 days</span></div>
          <table className="t">
            <thead>
              <tr>
                <th>Supplier</th>
                <th>Category</th>
                <th className="num">Value</th>
                <th>Expiry</th>
                <th>Status</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {expiringContracts.map((c, i) => (
                <tr key={i} style={{ cursor: "pointer" }} onClick={() => openDrawer({ kind: "contract", data: c })}>
                  <td style={{ fontWeight: 500 }}>{c.supplier}</td>
                  <td className="muted">{c.cat}</td>
                  <td className="num">{c.value ? `€${(c.value / 1000).toFixed(1)}M` : "—"}</td>
                  <td className="num mono">{c.expiry}</td>
                  <td>
                    <span className={`chip ${c.daysLeft < 0 ? "bad" : c.daysLeft < 30 ? "warn" : "info"}`}>
                      {c.daysLeft < 0 ? `${-c.daysLeft}d overdue` : `${c.daysLeft}d left`}
                    </span>
                  </td>
                  <td>{riskChip(c.risk)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function KpiCard({ label, value, sub, accent }) {
  return (
    <div className={`kpi${accent ? ` accent-${accent}` : ""}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-foot"><span>{sub}</span></div>
    </div>
  );
}

function CategoryRiskMatrix({ categories }) {
  const totalSpend = (categories || []).reduce((s, c) => s + c.spend, 0) || 1;
  const maxSpend = Math.max(...(categories || []).map(c => c.spend), 1);

  const riskRank = { critical: 0, high: 1, medium: 2, low: 3 };
  const sorted = [...(categories || [])].sort((a, b) => {
    const rd = riskRank[a.risk] - riskRank[b.risk];
    return rd !== 0 ? rd : b.spend - a.spend;
  });

  const riskCfg = {
    critical: { label: "Critical", cls: "bad",  bg: "var(--bad-soft)",  color: "var(--bad)" },
    high:     { label: "High",     cls: "warn",  bg: "var(--warn-soft)", color: "var(--warn)" },
    medium:   { label: "Medium",   cls: "info",  bg: "var(--info-soft)", color: "var(--info)" },
    low:      { label: "Low",      cls: "good",  bg: "var(--good-soft)", color: "var(--good)" },
  };

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="t" style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={{ width: 180 }}>Category</th>
            <th>Risk</th>
            <th style={{ width: 200 }}>Spend vs Budget</th>
            <th className="num">Spend</th>
            <th className="num">Share</th>
            <th className="num">Suppliers</th>
            <th className="num">Variance</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((c, i) => {
            const cfg = riskCfg[c.risk] || riskCfg.medium;
            const spendPct = (c.spend / maxSpend) * 100;
            const budgetPct = (c.budget / maxSpend) * 100;
            const over = c.spend > c.budget;
            const variance = c.budget ? ((c.spend - c.budget) / c.budget * 100).toFixed(1) : 0;
            const sharePct = (c.spend / totalSpend * 100).toFixed(1);

            return (
              <tr key={c.id} style={{ borderLeft: `3px solid ${cfg.color}` }}>
                <td style={{ fontWeight: 500, fontSize: 13 }}>{c.name}</td>
                <td>
                  <span className={`chip ${cfg.cls}`} style={{ fontSize: 11 }}>
                    <span className="dot" />{cfg.label}
                  </span>
                </td>
                <td>
                  {/* Inline spend vs budget bar */}
                  <div style={{ position: "relative", height: 18, background: "var(--bg-sunk)", borderRadius: 3, minWidth: 120 }}>
                    {/* Budget marker */}
                    <div style={{ position: "absolute", left: `${budgetPct}%`, top: -2, bottom: -2, width: 2, background: "var(--ink-3)", opacity: 0.35, zIndex: 2 }} />
                    {/* Spend bar */}
                    <div style={{
                      position: "absolute", left: 0, top: 0, bottom: 0,
                      width: `${Math.min(spendPct, budgetPct)}%`,
                      background: "var(--primary)", borderRadius: "3px 0 0 3px",
                    }} />
                    {over && (
                      <div style={{
                        position: "absolute", left: `${budgetPct}%`, top: 0, bottom: 0,
                        width: `${spendPct - budgetPct}%`,
                        background: "var(--bad)", borderRadius: "0 3px 3px 0",
                      }} />
                    )}
                  </div>
                </td>
                <td className="num" style={{ fontWeight: 600 }}>€{c.spend}M</td>
                <td className="num" style={{ color: "var(--ink-3)" }}>{sharePct}%</td>
                <td className="num">{c.suppliers}</td>
                <td className="num" style={{ color: over ? "var(--bad)" : "var(--good)", fontWeight: 500 }}>
                  {over ? "+" : ""}{variance}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

window.Dashboard = Dashboard;
