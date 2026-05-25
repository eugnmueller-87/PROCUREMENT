// SpendLens — Icarus AI market intelligence screen
const { useState: useS, useEffect: useE, useRef: useR } = React;

const CATS = ["All", "Cloud", "AI/ML APIs", "IT Software", "Telecom", "Recruitment", "Professional Services", "Marketing", "Facilities", "Real Estate", "Hardware", "Travel"];

function Icarus({ openDrawer, api }) {
  const [signals, setSignals] = useS([]);
  const [loading, setLoading] = useS(false);
  const [scanning, setScanning] = useS(false);
  const [cat, setCat] = useS("All");
  const [days, setDays] = useS(30);
  const [q, setQ] = useS("");
  const [scanMsg, setScanMsg] = useS("");

  const load = async (c, d) => {
    setLoading(true);
    try {
      const cat_param = c !== "All" ? `&category=${encodeURIComponent(c)}` : "";
      const r = await fetch(`${api}/api/signals?days=${d}${cat_param}&limit=100`);
      const data = await r.json();
      setSignals(data.signals || []);
    } catch (e) {}
    setLoading(false);
  };

  useE(() => { load(cat, days); }, [cat, days]);

  const runScan = async () => {
    setScanning(true);
    setScanMsg("Scanning feeds…");
    try {
      const r = await fetch(`${api}/api/signals/scan`, { method: "POST" });
      const d = await r.json();
      setScanMsg(`Done — ${d.new_signals || 0} new signals`);
      await load(cat, days);
    } catch (e) {
      setScanMsg("Scan failed");
    }
    setScanning(false);
  };

  const filtered = signals.filter(s => {
    if (q) return (s.summary || s.text || "").toLowerCase().includes(q.toLowerCase());
    return true;
  });

  const sevClass = (rel) => {
    if (rel >= 8) return "bad";
    if (rel >= 6) return "warn";
    return "info";
  };

  return (
    <div className="col">
      <div className="page-h">
        <div>
          <h1>Icarus AI</h1>
          <div className="sub">Market intelligence · RSS feeds · procurement signals</div>
        </div>
        <div className="flex gap-2 center-y">
          <select className="select" value={days} onChange={e => setDays(parseInt(e.target.value))}>
            <option value={1}>Today</option>
            <option value={7}>7 days</option>
            <option value={30}>30 days</option>
            <option value={9999}>All time</option>
          </select>
          <button className="btn primary" onClick={runScan} disabled={scanning}>
            {scanning ? <><div className="spin" style={{ width: 14, height: 14 }} />Scanning…</> : <><Icons.Bolt size={14} />Run Scan</>}
          </button>
          {scanMsg && <span style={{ fontSize: 12, color: "var(--good)" }}>{scanMsg}</span>}
        </div>
      </div>

      {/* Category tabs */}
      <div className="flex gap-2" style={{ flexWrap: "wrap" }}>
        {CATS.map(c => (
          <button key={c} className={`btn sm${cat === c ? " primary" : ""}`}
            onClick={() => setCat(c)}>
            {c}
            {c !== "All" && <span style={{ marginLeft: 4, fontSize: 10, opacity: 0.7 }}>
              {signals.filter(s => (s.category || "").toLowerCase().includes(c.toLowerCase().split(" ")[0])).length}
            </span>}
          </button>
        ))}
      </div>

      <input className="input" placeholder="Search signals…" value={q} onChange={e => setQ(e.target.value)} />

      {loading
        ? <div style={{ display: "grid", placeItems: "center", height: 300 }}><div className="spin" /></div>
        : filtered.length === 0
          ? (
            <div className="card" style={{ padding: 60, textAlign: "center", color: "var(--ink-3)" }}>
              <Icons.Bolt size={32} color="var(--ink-4)" />
              <div style={{ marginTop: 12, fontWeight: 500 }}>No signals yet</div>
              <div className="txt-sm" style={{ marginTop: 4 }}>Click "Run Scan" to fetch market intelligence from RSS feeds</div>
            </div>
          )
          : (
            <div className="col">
              {filtered.map((s, i) => (
                <div key={s.id || i} className="card" style={{ cursor: "pointer" }}
                  onClick={() => openDrawer({ kind: "signal", data: s })}>
                  <div className="flex gap-3 center-y" style={{ marginBottom: 8 }}>
                    <span className={`chip ${sevClass(s.relevance || 5)}`}>
                      <span className="dot" />
                      {s.relevance >= 8 ? "Critical" : s.relevance >= 6 ? "High" : "Medium"}
                    </span>
                    {s.category && <span className="chip">{s.category}</span>}
                    {s.source && <span className="chip">{s.source}</span>}
                    <span className="txt-sm txt-muted" style={{ marginLeft: "auto" }}>
                      {s.timestamp ? new Date(s.timestamp).toLocaleDateString() : ""}
                    </span>
                  </div>
                  <div style={{ fontSize: 14, lineHeight: 1.55, fontWeight: 500, marginBottom: 6 }}>{s.headline || s.summary?.slice(0, 100) || ""}</div>
                  {s.summary && <div style={{ fontSize: 12, color: "var(--ink-3)", lineHeight: 1.5 }}>{s.summary.slice(0, 200)}{s.summary.length > 200 ? "…" : ""}</div>}
                  {s.action && (
                    <div style={{ marginTop: 10, padding: "8px 12px", background: "var(--primary-soft)", borderRadius: "var(--r-sm)", fontSize: 12, color: "var(--primary)" }}>
                      <strong>Action:</strong> {s.action}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )
      }
    </div>
  );
}

window.Icarus = Icarus;
