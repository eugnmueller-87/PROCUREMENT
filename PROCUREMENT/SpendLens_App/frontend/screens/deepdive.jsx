// SpendLens — Deep Dive screen
const { useState: useS, useEffect: useE } = React;

function DeepDive({ openDrawer, api }) {
  const [data, setData] = useS(null);
  const [loading, setLoading] = useS(true);
  const [selected, setSelected] = useS(null);

  useE(() => {
    fetch(`${api}/api/dashboard`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ display: "grid", placeItems: "center", height: 400 }}><div className="spin" /></div>;
  if (!data) return null;

  const { categories, trendYears, trendData } = data;

  // Category growth: first year vs last year
  const growthData = (categories || []).slice(0, 10).map(c => {
    const years = trendYears || [];
    const first = years.length > 1 ? ((trendData[c.name] || {})[years[0]] || 0) : 0;
    const last  = years.length > 0 ? ((trendData[c.name] || {})[years[years.length - 1]] || 0) : c.spend;
    const growth = first ? Math.round((last - first) / first * 100) : 0;
    return { ...c, from: first, to: last, growth };
  });

  // Vendor concentration: top 3 suppliers per category (mock from category spend)
  const totalSpend = (categories || []).reduce((s, c) => s + c.spend, 0) || 1;

  const handleCatClick = (cat) => {
    setSelected(cat.id === selected?.id ? null : cat);
  };

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
            {(categories || []).map((c, i) => {
              const pct = (c.spend / totalSpend) * 100;
              const isSelected = selected?.id === c.id;
              const riskColor = { critical: "var(--bad)", high: "var(--warn)", medium: "var(--info)", low: "var(--good)" }[c.risk] || "var(--info)";
              return (
                <div key={c.id} onClick={() => handleCatClick(c)}
                  style={{ display: "grid", gridTemplateColumns: "140px 1fr 48px 42px", gap: 10, alignItems: "center", fontSize: 12,
                    padding: "6px 8px", borderRadius: 6, cursor: "pointer",
                    background: isSelected ? "var(--primary-soft)" : "transparent",
                    border: isSelected ? "1px solid var(--primary)" : "1px solid transparent" }}>
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

      {/* Category detail panel — shown when a category is selected */}
      {selected && <CategoryDetail cat={selected} trendYears={trendYears} trendData={trendData} onClose={() => setSelected(null)} />}

      {/* Treemap */}
      <div className="card">
        <div className="card-h"><h3>Spend by Category × Risk</h3><span className="sub">click to drill in</span></div>
        <Treemap
          items={(categories || []).map(c => ({ id: c.id, name: c.name, value: c.spend, risk: c.risk || "medium" }))}
          height={360}
          onPick={(item) => {
            const cat = (categories || []).find(c => c.id === item.id);
            if (cat) setSelected(cat);
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
        />
      </div>
    </div>
  );
}

function CategoryDetail({ cat, trendYears, trendData, onClose }) {
  const trend = trendYears?.map(y => (trendData[cat.name] || {})[y] || 0) || [];
  const riskColor = { critical: "var(--bad)", high: "var(--warn)", medium: "var(--info)", low: "var(--good)" }[cat.risk] || "var(--info)";

  // Simulated top vendors (in real app these come from /api/dashboard per-category)
  const mockVendors = [
    { name: "Primary Supplier",   share: 42, spend: (cat.spend * 0.42).toFixed(1) },
    { name: "Secondary Supplier", share: 28, spend: (cat.spend * 0.28).toFixed(1) },
    { name: "Tertiary Supplier",  share: 18, spend: (cat.spend * 0.18).toFixed(1) },
    { name: "Others",             share: 12, spend: (cat.spend * 0.12).toFixed(1) },
  ];

  const hhi = mockVendors.reduce((s, v) => s + (v.share / 100) ** 2, 0);
  const hhiLabel = hhi > 0.25 ? "High concentration" : hhi > 0.15 ? "Moderate" : "Competitive";
  const hhiColor = hhi > 0.25 ? "var(--bad)" : hhi > 0.15 ? "var(--warn)" : "var(--good)";

  const growth = trend.length > 1 ? Math.round((trend[trend.length-1] - trend[0]) / (trend[0] || 1) * 100) : 0;

  return (
    <div className="card" style={{ borderTop: `3px solid ${riskColor}` }}>
      <div className="card-h">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: riskColor }} />
          <h3>{cat.name}</h3>
          <span className={`chip ${cat.risk === "critical" ? "bad" : cat.risk === "high" ? "warn" : cat.risk === "medium" ? "info" : "good"}`}>
            <span className="dot" />{cat.risk}
          </span>
        </div>
        <button className="btn" onClick={onClose} style={{ fontSize: 11 }}>Close ×</button>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 20 }}>
        {[
          ["Total Spend", `€${cat.spend}M`],
          ["Suppliers", cat.suppliers],
          ["Spend Growth", `+${growth}%`],
          ["HHI Concentration", hhiLabel],
        ].map(([label, val]) => (
          <div key={label} style={{ background: "var(--bg-sunk)", borderRadius: 8, padding: "10px 14px" }}>
            <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--ink-3)", marginBottom: 4 }}>{label}</div>
            <div className="num" style={{ fontSize: 16, color: label === "HHI Concentration" ? hhiColor : "var(--ink)" }}>{val}</div>
          </div>
        ))}
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Spend trend sparkline */}
        <div>
          <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 8, color: "var(--ink-2)" }}>Spend Trend (€M)</div>
          <div style={{ display: "flex", align: "flex-end", gap: 6 }}>
            {trend.map((v, i) => {
              const maxV = Math.max(...trend, 1);
              const hPct = (v / maxV) * 80;
              return (
                <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
                  <div style={{ fontSize: 9, color: "var(--ink-4)", fontFamily: "Geist Mono" }}>€{v}M</div>
                  <div style={{ width: "100%", height: `${Math.max(hPct, 4)}px`, background: riskColor, borderRadius: "3px 3px 0 0", opacity: 0.75 }} />
                  <div style={{ fontSize: 9, color: "var(--ink-3)" }}>{(trendYears || [])[i]}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Vendor concentration */}
        <div>
          <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 8, color: "var(--ink-2)" }}>
            Vendor Concentration
            <span style={{ marginLeft: 8, fontSize: 11, color: hhiColor }}>{hhiLabel}</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {mockVendors.map((v, i) => (
              <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 120px 48px", gap: 8, alignItems: "center", fontSize: 12 }}>
                <div style={{ color: "var(--ink-2)", fontSize: 11 }}>{v.name}</div>
                <div style={{ position: "relative", height: 16, background: "var(--bg-sunk)", borderRadius: 3 }}>
                  <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${v.share}%`,
                    background: i === 0 ? riskColor : "var(--primary)", borderRadius: 3, opacity: i === 0 ? 0.8 : 0.5 }} />
                </div>
                <div className="num" style={{ textAlign: "right", fontSize: 11, color: "var(--ink-3)" }}>€{v.spend}M</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

window.DeepDive = DeepDive;
