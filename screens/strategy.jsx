// SpendLens — Category Strategy screen
const { useState: useS, useEffect: useE } = React;

const FRAMEWORKS = ["Kraljic Matrix", "PESTEL", "SWOT", "Porter's Five Forces", "TCO Breakdown", "Negotiation Levers", "Strategy Recommendation"];

function Strategy({ openDrawer, api }) {
  const [cat, setCat] = useS("Cloud & Compute");
  const [activeFrame, setActiveFrame] = useS(0);
  const [generating, setGenerating] = useS(false);
  const [error, setError] = useS("");
  const [content, setContent] = useS({});

  const CATS = [
    "Cloud & Compute", "AI/ML APIs & Data", "IT Software & SaaS",
    "Telecom & Voice", "Recruitment & HR", "Professional Services",
    "Marketing & Campaigns", "Facilities & Office", "Real Estate",
    "Hardware & Equipment", "Travel & Expenses",
  ];

  const hasContent = !!content[cat];

  const generate = async () => {
    setGenerating(true);
    setError("");
    try {
      const res = await fetch(`${api}/api/strategy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: cat }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      const data = await res.json();
      const s = data.strategy;
      setContent(prev => ({
        ...prev,
        [cat]: {
          kraljic: {
            quadrant: `${s.kraljic.quadrant} — ${s.kraljic.rationale}`,
            label: s.kraljic.quadrant,
          },
          pestel: s.pestel,
          swot: s.swot,
          porter: s.porter,
          tco: s.tco,
          levers: s.levers,
          recommendation: s.recommendation,
        },
      }));
    } catch (e) {
      setError(e.message || "Generation failed");
    }
    setGenerating(false);
  };

  const c = content[cat];

  return (
    <div className="col">
      <div className="page-h">
        <div><h1>Category Strategy</h1><div className="sub">Kraljic · PESTEL · SWOT · negotiation playbooks</div></div>
        <div className="flex gap-2 center-y">
          <select className="select" value={cat} onChange={e => { setCat(e.target.value); setActiveFrame(0); }}>
            {CATS.map(c => <option key={c}>{c}</option>)}
          </select>
          <button className="btn primary" onClick={generate} disabled={generating}>
            {generating ? <><div className="spin" style={{ width: 14, height: 14 }} />Generating…</> : <><Icons.Spark size={14} />Generate All Frameworks</>}
          </button>
        </div>
      </div>

      {error && <div style={{ padding: "10px 14px", background: "var(--bad-soft)", borderRadius: "var(--r-sm)", color: "var(--bad)", fontSize: 13 }}>{error}</div>}

      {/* Framework tabs */}
      <div className="seg" style={{ width: "100%" }}>
        {FRAMEWORKS.map((f, i) => (
          <div key={f} className={`seg-opt${activeFrame === i ? " on" : ""}`} onClick={() => setActiveFrame(i)}>{f}</div>
        ))}
      </div>

      {!hasContent
        ? (
          <div className="card" style={{ padding: 80, textAlign: "center", color: "var(--ink-3)" }}>
            <Icons.Strategy size={40} color="var(--ink-4)" />
            <div style={{ marginTop: 16, fontWeight: 500, fontSize: 16 }}>No strategy generated yet for <strong style={{ color: "var(--ink)" }}>{cat}</strong></div>
            <div className="txt-sm" style={{ marginTop: 6 }}>Click <strong>Generate All Frameworks</strong> to start the analysis</div>
          </div>
        )
        : activeFrame === 0 ? <KraljicView data={c.kraljic} cat={cat} />
        : activeFrame === 1 ? <ListFramework title="PESTEL Analysis" items={c.pestel} />
        : activeFrame === 2 ? <SwotView data={c.swot} />
        : activeFrame === 3 ? <ListFramework title="Porter's Five Forces" items={c.porter} />
        : activeFrame === 4 ? <ListFramework title="TCO Breakdown" items={c.tco} />
        : activeFrame === 5 ? <ListFramework title="Negotiation Levers" items={c.levers} />
        : <RecommendationView text={c.recommendation} cat={cat} />
      }
    </div>
  );
}

function KraljicView({ data, cat }) {
  const quadrants = [
    { label: "Bottleneck",    desc: "Low spend, high risk",  color: "var(--warn-soft)" },
    { label: "Strategic",     desc: "High spend, high risk", color: "var(--bad-soft)"  },
    { label: "Non-critical",  desc: "Low spend, low risk",   color: "var(--bg-sunk)"   },
    { label: "Leverage",      desc: "High spend, low risk",  color: "var(--good-soft)" },
  ];
  const activeLabel = data.label || "Strategic";
  return (
    <div className="card">
      <div className="card-h"><h3>Kraljic Matrix</h3><span className="sub">{cat}</span></div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gridTemplateRows: "1fr 1fr", gap: 2, height: 320, border: "1px solid var(--hairline)", borderRadius: "var(--r-sm)", overflow: "hidden" }}>
        {quadrants.map(q => (
          <div key={q.label} style={{ background: q.color, padding: 16, position: "relative", display: "flex", flexDirection: "column", justifyContent: "flex-end" }}>
            <div style={{ fontWeight: 600, fontSize: 13 }}>{q.label}</div>
            <div style={{ fontSize: 11, color: "var(--ink-3)" }}>{q.desc}</div>
            {q.label === activeLabel && (
              <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: 36, height: 36, borderRadius: "50%", background: "var(--primary)", display: "grid", placeItems: "center", color: "#fff", fontSize: 10, fontWeight: 600 }}>
                {cat.split(" ")[0].slice(0, 3)}
              </div>
            )}
          </div>
        ))}
      </div>
      <div style={{ marginTop: 12, padding: "10px 14px", background: "var(--primary-soft)", borderRadius: "var(--r-sm)", fontSize: 13, color: "var(--primary)" }}>
        <strong>{data.quadrant}</strong>
      </div>
    </div>
  );
}

function ListFramework({ title, items }) {
  return (
    <div className="card">
      <div className="card-h"><h3>{title}</h3></div>
      <div className="ai-insights">
        {items.map((item, i) => (
          <div key={i} className="ai-insight"><div className="marker" /><div>{item}</div></div>
        ))}
      </div>
    </div>
  );
}

function SwotView({ data }) {
  const sections = [
    { label: "Strengths", items: data.strengths, color: "var(--good)", bg: "var(--good-soft)" },
    { label: "Weaknesses", items: data.weaknesses, color: "var(--bad)", bg: "var(--bad-soft)" },
    { label: "Opportunities", items: data.opportunities, color: "var(--info)", bg: "var(--info-soft)" },
    { label: "Threats", items: data.threats, color: "var(--warn)", bg: "var(--warn-soft)" },
  ];
  return (
    <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 12 }}>
      {sections.map(s => (
        <div key={s.label} className="card" style={{ borderTop: `3px solid ${s.color}` }}>
          <div style={{ fontWeight: 600, marginBottom: 10, color: s.color }}>{s.label}</div>
          <ul style={{ margin: 0, padding: "0 0 0 16px", fontSize: 13, lineHeight: 1.7 }}>
            {s.items.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      ))}
    </div>
  );
}

function RecommendationView({ text, cat }) {
  return (
    <div className="ai-card">
      <div className="ai-h">
        <div className="ai-mark"><Icons.Spark size={14} /></div>
        <div>
          <div className="ai-title">Strategy Recommendation — {cat}</div>
          <div className="ai-sub">Based on Kraljic position, market signals, and spend data</div>
        </div>
      </div>
      <div className="ai-insights">
        <div className="ai-insight"><div className="marker" /><div>{text}</div></div>
      </div>
    </div>
  );
}

window.Strategy = Strategy;
