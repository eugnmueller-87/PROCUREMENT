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

  const growthData = (categories || []).slice(0, 10).map(c => {
    const years = trendYears || [];
    const first = years.length > 1 ? ((trendData[c.name] || {})[years[0]] || 0) : 0;
    const last = years.length > 0 ? ((trendData[c.name] || {})[years[years.length - 1]] || 0) : c.spend;
    const growth = first ? Math.round((last - first) / first * 100) : 0;
    return { name: c.name, from: first, to: last, growth };
  });

  const bubbleData = (categories || []).map((c, i) => ({
    name: c.name, x: (i + 1) * 3, y: c.spend, r: c.suppliers || 3, risk: c.risk || "medium",
  }));

  return (
    <div className="col">
      <div className="page-h">
        <div><h1>Deep Dive Analysis</h1><div className="sub">Category growth · Capex vs Opex · risk concentration</div></div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="card">
          <div className="card-h"><h3>Spend by Category — Growth</h3></div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {growthData.map(d => {
              const maxV = Math.max(...growthData.map(x => x.to), 1);
              const fromPct = (d.from / maxV) * 100;
              const toPct = (d.to / maxV) * 100;
              return (
                <div key={d.name} style={{ display: "grid", gridTemplateColumns: "150px 1fr 100px", gap: 12, alignItems: "center", fontSize: 12 }}>
                  <div style={{ color: "var(--ink-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.name}</div>
                  <div style={{ position: "relative", height: 22, background: "var(--bg-sunk)", borderRadius: 4 }}>
                    <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${fromPct}%`, background: "var(--primary)", borderRadius: 4 }} />
                    <div style={{ position: "absolute", left: `${fromPct}%`, top: 0, bottom: 0, width: `${toPct - fromPct}%`, background: "var(--info)", borderRadius: "0 4px 4px 0", opacity: 0.65 }} />
                  </div>
                  <div className="num" style={{ textAlign: "right", fontSize: 11, color: "var(--good)" }}>+{d.growth}%</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card">
          <div className="card-h"><h3>Spend vs Budget by Category</h3></div>
          <SpendVsBudget data={(categories || []).slice(0, 10).map(c => ({ name: c.name, spend: c.spend, budget: c.budget }))} />
        </div>
      </div>

      <div className="card">
        <div className="card-h"><h3>Risk Map — Category Concentration</h3><span className="sub">bubble = supplier count</span></div>
        <RiskBubble data={bubbleData} height={340} />
      </div>

      <div className="card">
        <div className="card-h"><h3>Spend by Category × Risk</h3><span className="sub">click to drill in</span></div>
        <Treemap
          items={(categories || []).map(c => ({
            id: c.id, name: c.name, value: c.spend, risk: c.risk || "medium",
          }))}
          height={360}
          onPick={(item) => openDrawer({ kind: "category", data: item })}
        />
      </div>
    </div>
  );
}

window.DeepDive = DeepDive;
