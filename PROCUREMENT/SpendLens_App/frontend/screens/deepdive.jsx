// SpendLens — Deep Dive screen
const { useState: useS, useEffect: useE } = React;

function DeepDive({ openDrawer, api }) {
  const [data, setData] = useS(null);
  const [loading, setLoading] = useS(true);

  useE(() => {
    fetch(`${api}/api/dashboard`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ display: "grid", placeItems: "center", height: 400 }}><div className="spin" /></div>;
  if (!data) return null;

  const { categories, trendYears, trendData } = data;

  const drillIn = (cat) => openDrawer({ kind: "category", data: cat, trendData, trendYears });

  const totalSpend = (categories || []).reduce((s, c) => s + c.spend, 0) || 1;

  // Category growth: first year vs last year
  const growthData = (categories || []).slice(0, 10).map(c => {
    const years = trendYears || [];
    const first = years.length > 1 ? ((trendData[c.name] || {})[years[0]] || 0) : 0;
    const last  = years.length > 0 ? ((trendData[c.name] || {})[years[years.length - 1]] || 0) : c.spend;
    const growth = first ? Math.round((last - first) / first * 100) : 0;
    return { ...c, from: first, to: last, growth };
  });

  return (
    <div className="col">
      <div className="page-h">
        <div><h1>Deep Dive Analysis</h1><div className="sub">Category growth · concentration · budget variance · drill-in</div></div>
      </div>

      {/* Row 1: Growth + Budget variance */}
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="card">
          <div className="card-h"><h3>Spend Growth by Category</h3><span className="sub">{trendYears?.[0]} → {trendYears?.[trendYears.length - 1]}</span></div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {growthData.map(d => {
              const maxV = Math.max(...growthData.map(x => x.to), 1);
              const fromPct = (d.from / maxV) * 100;
              const toPct   = (d.to   / maxV) * 100;
              const positive = d.growth >= 0;
              return (
                <div key={d.name} style={{ display: "grid", gridTemplateColumns: "140px 1fr 72px", gap: 10, alignItems: "center", fontSize: 12 }}>
                  <div style={{ color: "var(--ink-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.name}</div>
                  <div style={{ position: "relative", height: 20, background: "var(--bg-sunk)", borderRadius: 4 }}>
                    <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${fromPct}%`, background: "var(--primary)", borderRadius: 4, opacity: 0.6 }} />
                    <div style={{ position: "absolute", left: `${fromPct}%`, top: 0, bottom: 0, width: `${Math.max(toPct - fromPct, 0)}%`, background: "var(--info)", borderRadius: "0 4px 4px 0" }} />
                  </div>
                  <div className="num" style={{ textAlign: "right", fontSize: 11, color: positive ? "var(--good)" : "var(--bad)", fontWeight: 600 }}>
                    {positive ? "+" : ""}{d.growth}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card">
          <div className="card-h"><h3>Spend vs Budget</h3><span className="sub">current period</span></div>
          <SpendVsBudget data={(categories || []).slice(0, 10).map(c => ({ name: c.name, spend: c.spend, budget: c.budget }))} />
        </div>
      </div>

      {/* Row 2: Spend share + Supplier concentration */}
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="card">
          <div className="card-h"><h3>Spend Share by Category</h3><span className="sub">% of total · click to drill in</span></div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {(categories || []).map(c => {
              const pct = (c.spend / totalSpend) * 100;
              const riskColor = { critical: "var(--bad)", high: "var(--warn)", medium: "var(--info)", low: "var(--good)" }[c.risk] || "var(--info)";
              return (
                <div key={c.id} onClick={() => drillIn(c)}
                  style={{ display: "grid", gridTemplateColumns: "140px 1fr 48px 42px", gap: 10, alignItems: "center", fontSize: 12,
                    padding: "6px 8px", borderRadius: 6, cursor: "pointer" }}
                  onMouseEnter={e => e.currentTarget.style.background = "var(--bg-sunk)"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <div style={{ color: "var(--ink-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: riskColor, flexShrink: 0 }} />
                    {c.name}
                  </div>
                  <div style={{ position: "relative", height: 18, background: "var(--bg-sunk)", borderRadius: 4 }}>
                    <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${pct}%`, background: riskColor, borderRadius: 4, opacity: 0.7 }} />
                  </div>
                  <div className="num" style={{ textAlign: "right", color: "var(--ink-3)", fontSize: 11 }}>{pct.toFixed(1)}%</div>
                  <div className="num" style={{ textAlign: "right", color: "var(--ink-2)", fontSize: 11 }}>€{c.spend}M</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card">
          <div className="card-h"><h3>Supplier Count by Category</h3><span className="sub">fragmentation indicator</span></div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {(categories || []).map(c => {
              const maxS = Math.max(...(categories || []).map(x => x.suppliers || 0), 1);
              const pct = ((c.suppliers || 0) / maxS) * 100;
              const riskColor = { critical: "var(--bad)", high: "var(--warn)", medium: "var(--info)", low: "var(--good)" }[c.risk] || "var(--info)";
              const spendPerSupplier = c.suppliers ? (c.spend / c.suppliers).toFixed(1) : "—";
              return (
                <div key={c.id} style={{ display: "grid", gridTemplateColumns: "140px 1fr 32px 56px", gap: 10, alignItems: "center", fontSize: 12 }}>
                  <div style={{ color: "var(--ink-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.name}</div>
                  <div style={{ position: "relative", height: 18, background: "var(--bg-sunk)", borderRadius: 4 }}>
                    <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${pct}%`, background: riskColor, borderRadius: 4, opacity: 0.6 }} />
                  </div>
                  <div className="num" style={{ textAlign: "right", color: "var(--ink-2)", fontSize: 11, fontWeight: 600 }}>{c.suppliers || 0}</div>
                  <div style={{ textAlign: "right", color: "var(--ink-3)", fontSize: 10 }}>€{spendPerSupplier}M/sup</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Treemap */}
      <div className="card">
        <div className="card-h"><h3>Spend by Category × Risk</h3><span className="sub">click to drill in</span></div>
        <Treemap
          items={(categories || []).map(c => ({ id: c.id, name: c.name, value: c.spend, risk: c.risk || "medium" }))}
          height={360}
          onPick={(item) => {
            const cat = (categories || []).find(c => c.id === item.id);
            if (cat) drillIn(cat);
          }}
        />
      </div>
    </div>
  );
}

window.DeepDive = DeepDive;
