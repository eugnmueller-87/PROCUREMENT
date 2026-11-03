// SpendLens — Compliance Scorecard screen
const { useState: useS, useEffect: useE, useMemo: useM } = React;

function Compliance({ openDrawer, api }) {
  const [data, setData] = useS(null);
  const [loading, setLoading] = useS(true);
  const [catFilter, setCatFilter] = useS("All");
  const [riskFilter, setRiskFilter] = useS("All");
  const [contractFilter, setContractFilter] = useS("All");
  const [sortBy, setSortBy] = useS("score");
  const [q, setQ] = useS("");

  useE(() => {
    fetch(`${api}/api/suppliers`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const cats = useM(() => {
    if (!data) return [];
    return ["All", ...new Set(data.suppliers.map(s => s.cat).filter(Boolean))];
  }, [data]);

  const filtered = useM(() => {
    if (!data) return [];
    let list = data.suppliers;
    if (catFilter !== "All") list = list.filter(s => s.cat === catFilter);
    if (riskFilter !== "All") list = list.filter(s => s.risk === riskFilter.toLowerCase());
    if (contractFilter !== "All") list = list.filter(s =>
      contractFilter === "Under Contract" ? s.contract === 100 : s.contract < 100
    );
    if (q) list = list.filter(s => s.name.toLowerCase().includes(q.toLowerCase()));
    return [...list].sort((a, b) => {
      if (sortBy === "score") return b.score - a.score;
      if (sortBy === "spend") return b.spend - a.spend;
      if (sortBy === "name") return a.name.localeCompare(b.name);
      return 0;
    });
  }, [data, catFilter, riskFilter, contractFilter, sortBy, q]);

  if (loading) return <div style={{ display: "grid", placeItems: "center", height: 400 }}><div className="spin" /></div>;
  if (!data) return <div style={{ padding: 40, color: "var(--ink-3)" }}>No data</div>;

  const { summary } = data;

  const riskDot = (r) => {
    const colors = { critical: "var(--bad)", high: "var(--warn)", medium: "var(--info)", low: "var(--good)" };
    return <span style={{ width: 10, height: 10, borderRadius: "50%", background: colors[r] || "var(--ink-4)", display: "inline-block" }} />;
  };

  return (
    <div className="col">
      <div className="page-h">
        <div>
          <h1>Supplier Compliance Scorecard</h1>
          <div className="sub">ABC tiers · compliance scores · relationship status</div>
        </div>
      </div>

      {/* Summary bar */}
      <div style={{ background: "var(--primary)", borderRadius: "var(--r)", padding: "18px 24px", color: "var(--primary-ink)", display: "flex", alignItems: "center", gap: 32 }}>
        <div>
          <div style={{ fontSize: 42, fontWeight: 700, fontFamily: "Geist Mono", letterSpacing: "-0.03em", lineHeight: 1 }}>{Math.round(summary.score)}</div>
          <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>/ 100</div>
        </div>
        {[
          ["PO Coverage", `${summary.poCoverage}%`],
          ["Contract Coverage", `${summary.contractCoverage}%`],
          ["A Suppliers", summary.aSuppliers],
          ["B Suppliers", summary.bSuppliers],
          ["C Suppliers", summary.cSuppliers],
        ].map(([label, val]) => (
          <div key={label}>
            <div style={{ fontSize: 22, fontWeight: 600, fontFamily: "Geist Mono" }}>{val}</div>
            <div style={{ fontSize: 11, opacity: 0.65, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-2 center-y" style={{ flexWrap: "wrap" }}>
        <input className="input" placeholder="Search supplier…" value={q} onChange={e => setQ(e.target.value)} style={{ width: 200 }} />
        <select className="select" value={catFilter} onChange={e => setCatFilter(e.target.value)}>
          {cats.map(c => <option key={c}>{c}</option>)}
        </select>
        <select className="select" value={riskFilter} onChange={e => setRiskFilter(e.target.value)}>
          {["All", "Critical", "High", "Medium", "Low"].map(r => <option key={r}>{r}</option>)}
        </select>
        <select className="select" value={contractFilter} onChange={e => setContractFilter(e.target.value)}>
          {["All", "Under Contract", "No Contract"].map(c => <option key={c}>{c}</option>)}
        </select>
        <select className="select" value={sortBy} onChange={e => setSortBy(e.target.value)}>
          <option value="score">Sort: Score ↓</option>
          <option value="spend">Sort: Spend ↓</option>
          <option value="name">Sort: Name A–Z</option>
        </select>
        <span className="txt-sm txt-muted" style={{ marginLeft: "auto" }}>{filtered.length} suppliers</span>
      </div>

      {/* Supplier list */}
      <div className="card" style={{ padding: 0 }}>
        {filtered.length === 0
          ? <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>No suppliers match filters</div>
          : filtered.map(s => (
            <div key={s.id} className="row-link" onClick={() => openDrawer({ kind: "supplier", data: s })}>
              <div className={`tier-av ${s.tier.toLowerCase()}`}>{s.tier}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 500, fontSize: 14 }}>{s.name}</div>
                <div className="txt-sm txt-muted">{s.cat} · {s.country}</div>
              </div>
              <div className="flex gap-2 center-y">
                {riskDot(s.risk)}
                <span className="chip" style={{ fontSize: 11 }}>{s.rel || "Transactional"}</span>
                <div style={{ textAlign: "right", minWidth: 60 }}>
                  <div className="num" style={{ fontSize: 16, fontWeight: 600 }}>{Math.round(s.score)}</div>
                  <div style={{ fontSize: 10, color: "var(--ink-4)", textTransform: "uppercase" }}>Score</div>
                </div>
                <div style={{ textAlign: "right", minWidth: 60 }}>
                  <div className="num" style={{ fontSize: 14 }}>€{s.spend}M</div>
                  <div style={{ fontSize: 10, color: "var(--ink-4)", textTransform: "uppercase" }}>Spend</div>
                </div>
                <Icons.ChevR size={14} color="var(--ink-4)" />
              </div>
            </div>
          ))
        }
      </div>
    </div>
  );
}

window.Compliance = Compliance;
