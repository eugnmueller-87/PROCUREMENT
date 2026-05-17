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

      {/* Risk map */}
      <div className="card">
        <div className="card-h"><h3>Risk Map — Category Share of Total Spend</h3><span className="sub">bubble size = no. of suppliers</span></div>
        <RiskBubble
          data={(categories || []).map((c, i) => ({
            name: c.name,
            x: c.spend,
            y: { critical: 9, high: 7, medium: 4, low: 2 }[c.risk] || 4,
            r: c.suppliers || 3,
            risk: c.risk || "medium",
          }))}
          height={320}
          xLabel="Spend (€M)"
          yLabel="Risk Level"
        />
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

window.Dashboard = Dashboard;
