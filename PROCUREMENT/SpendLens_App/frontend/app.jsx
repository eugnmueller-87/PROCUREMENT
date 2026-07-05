// SpendLens — main app router
const { useState: useS, useEffect: useE } = React;

const API = "";  // same origin

// Catches runtime errors in a screen so the shell/nav always survives
class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidUpdate(prev) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }
  render() {
    if (this.state.error) {
      return (
        <div className="card" style={{ maxWidth: 480, margin: "60px auto", textAlign: "center" }}>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>Something went wrong on this screen</div>
          <div style={{ fontSize: 13, color: "var(--ink-3)", marginBottom: 14 }}>{String(this.state.error?.message || this.state.error)}</div>
          <button className="btn" onClick={() => location.reload()}>Reload</button>
        </div>
      );
    }
    return this.props.children;
  }
}

function App() {
  const [route, setRoute] = useS(location.hash.replace("#", "") || "dashboard");
  const [sbExpanded, setSbExpanded] = useS(false);
  const [cmdOpen, setCmdOpen] = useS(false);
  const [drawer, setDrawer] = useS(null);

  useE(() => {
    function onHash() { setRoute(location.hash.replace("#", "") || "dashboard"); }
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useE(() => {
    function onKey(e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdOpen(o => !o);
      }
      if (e.key === "Escape") setCmdOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const nav = (id) => {
    if (id === "__open") { setCmdOpen(true); return; }
    location.hash = id;
    setRoute(id);
  };

  const openDrawer = (d) => setDrawer(d);
  const closeDrawer = () => setDrawer(null);

  // Make openDrawer globally accessible for screens
  useE(() => { window.__openDrawer = openDrawer; }, []);

  const screens = {
    dashboard:  window.Dashboard,
    deepdive:   window.DeepDive,
    compliance: window.Compliance,
    icarus:     window.Icarus,
    strategy:   window.Strategy,
    supplier:   window.SupplierDD,
    clm:        window.CLM,
  };

  const Screen = screens[route];

  function drawerTitle(d) {
    if (!d) return "";
    if (d.kind === "contract") return `Contract · ${d.data?.vendorName || d.data?.supplier || ""}`;
    if (d.kind === "supplier") return d.data?.name || "";
    if (d.kind === "signal")   return "Market signal";
    return d.kind || "";
  }

  return (
    <div className="app" data-sb={sbExpanded ? "expanded" : "collapsed"}
         onMouseLeave={() => setSbExpanded(false)}>
      <div onMouseEnter={() => setSbExpanded(true)} style={{ gridArea: "sb", display: "contents" }}>
        <Sidebar active={route} onNav={nav} />
      </div>
      <TopBar active={route} onOpenCmd={() => setCmdOpen(true)} onMenu={() => setSbExpanded(s => !s)} onNav={nav} api={API} />
      <main className="main">
        <ErrorBoundary resetKey={route}>
          {Screen
            ? <Screen openDrawer={openDrawer} api={API} />
            : <div style={{ padding: 40, color: "var(--ink-3)" }}>Screen not found: {route}</div>
          }
        </ErrorBoundary>
      </main>

      <CmdPalette open={cmdOpen} onClose={() => setCmdOpen(false)} onNav={nav} />

      <Drawer open={!!drawer} onClose={closeDrawer} title={drawerTitle(drawer)}>
        {drawer && <DrawerBody d={drawer} />}
      </Drawer>
    </div>
  );
}

function DrawerBody({ d }) {
  if (d.kind === "contract") {
    const c = d.data;
    const flags = c.clauseFlags || {};
    const dotColor = (f) => ({ green: "var(--good)", yellow: "var(--warn)", red: "var(--bad)" }[f] || "var(--ink-4)");
    return (
      <div className="col">
        <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          {[
            ["Risk Score", `${c.riskScore?.toFixed(1) || "—"} / 10`],
            ["Risk Level", c.riskLevel || "—"],
            ["Expires", c.endDate || "—"],
            ["Notice", c.noticePeriodDays ? `${c.noticePeriodDays} days` : "—"],
            ["Jurisdiction", c.jurisdiction || "—"],
            ["Payment", c.paymentTerms || "—"],
          ].map(([label, val]) => (
            <div key={label} className="card" style={{ padding: 14 }}>
              <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--ink-3)" }}>{label}</div>
              <div className="num" style={{ fontSize: 18, marginTop: 4 }}>{val}</div>
            </div>
          ))}
        </div>
        {c.riskSummary && (
          <div className="card">
            <div className="card-h"><h3>Risk Summary</h3></div>
            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: "var(--ink-2)" }}>{c.riskSummary}</p>
          </div>
        )}
        {Object.keys(flags).length > 0 && (
          <div className="card">
            <div className="card-h"><h3>Clause Flags</h3></div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {Object.entries(flags).map(([k, v]) => (
                <span key={k} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, padding: "3px 8px", borderRadius: 999, background: "var(--bg-sunk)" }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: dotColor(v), flexShrink: 0 }} />
                  {k.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          </div>
        )}
        {c.requiredActions?.length > 0 && (
          <div className="card">
            <div className="card-h"><h3>Required Actions</h3></div>
            <div className="ai-insights">
              {c.requiredActions.map((a, i) => (
                <div key={i} className={`ai-insight ${a.startsWith("[CRITICAL]") ? "bad" : a.startsWith("[REVIEW]") ? "warn" : ""}`}>
                  <div className="marker" />
                  <div>{a.replace(/^\[(CRITICAL|REVIEW|MISSING)\] /, "")}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  if (d.kind === "supplier") {
    const s = d.data;
    return (
      <div className="col">
        <div className="flex gap-3 center-y">
          <div className={`tier-av ${(s.tier || "C").toLowerCase()}`} style={{ width: 48, height: 48, fontSize: 18, borderRadius: 12 }}>{s.tier}</div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>{s.name}</div>
            <div className="txt-sm txt-muted">{s.cat} · {s.country}</div>
          </div>
          <div className="spacer" />
          <span className={`chip ${s.risk === "critical" ? "bad" : s.risk === "high" ? "warn" : s.risk === "medium" ? "info" : "good"}`}>
            <span className="dot" />{s.risk}
          </span>
        </div>
        <div className="grid" style={{ gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
          {[["Score", Math.round(s.score)], ["Spend", `€${s.spend}M`], ["Tier", s.tier]].map(([label, val]) => (
            <div key={label} className="card" style={{ padding: 14 }}>
              <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--ink-3)" }}>{label}</div>
              <div className="num" style={{ fontSize: 20, marginTop: 4 }}>{val}</div>
            </div>
          ))}
        </div>
        <div className="card">
          <div className="card-h"><h3>Coverage</h3></div>
          <div className="col">
            {[["PO Coverage", s.po], ["Contract", s.contract]].map(([lbl, v]) => (
              <div key={lbl}>
                <div className="flex between txt-sm" style={{ marginBottom: 4 }}>
                  <span>{lbl}</span>
                  <span className="num">{Math.round(v)}%</span>
                </div>
                <div className="bar-track">
                  <div className={`bar-fill ${v >= 80 ? "good" : v >= 60 ? "warn" : "bad"}`} style={{ width: `${v}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (d.kind === "category") {
    const c = d.data;
    const td = d.trendData || {};
    const ty = d.trendYears || [];
    const riskColor = { critical: "var(--bad)", high: "var(--warn)", medium: "var(--info)", low: "var(--good)" }[c.risk] || "var(--info)";
    const over = c.spend > c.budget;
    const variance = c.budget ? ((c.spend - c.budget) / c.budget * 100).toFixed(1) : "—";
    const trend = ty.map(y => (td[c.name] || {})[y] || 0);
    const maxTrend = Math.max(...trend, 1);
    const totalSupplierShare = c.suppliers > 0 ? [
      { label: "Primary",   pct: Math.round(60 - c.suppliers * 3) },
      { label: "Secondary", pct: Math.round(25 + c.suppliers) },
      { label: "Others",    pct: Math.round(15 + c.suppliers * 2) },
    ] : [];

    return (
      <div className="col">
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, paddingBottom: 4 }}>
          <span style={{ width: 12, height: 12, borderRadius: "50%", background: riskColor, flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 17, fontWeight: 600 }}>{c.name}</div>
            <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>{c.suppliers} suppliers · €{c.spend}M spend</div>
          </div>
          <span className={`chip ${c.risk === "critical" ? "bad" : c.risk === "high" ? "warn" : c.risk === "medium" ? "info" : "good"}`}>
            <span className="dot" />{c.risk}
          </span>
        </div>

        {/* KPI tiles */}
        <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {[
            ["Spend",     `€${c.spend}M`,   null],
            ["Budget",    `€${c.budget}M`,  null],
            ["Suppliers", c.suppliers,       null],
            ["Variance",  `${over ? "+" : ""}${variance}%`, over ? "bad" : "good"],
          ].map(([label, val, accent]) => (
            <div key={label} style={{ background: "var(--bg-sunk)", borderRadius: 8, padding: "10px 14px",
              borderTop: accent ? `2px solid var(--${accent})` : "none" }}>
              <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--ink-3)", marginBottom: 4 }}>{label}</div>
              <div className="num" style={{ fontSize: 18, color: accent ? `var(--${accent})` : "var(--ink)" }}>{val}</div>
            </div>
          ))}
        </div>

        {/* Spend trend mini bar chart */}
        {trend.length > 0 && (
          <div className="card" style={{ padding: "14px 16px" }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: "var(--ink-2)", marginBottom: 10 }}>Spend Trend (€M)</div>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 64 }}>
              {trend.map((v, i) => {
                const h = Math.max((v / maxTrend) * 56, 4);
                const isLast = i === trend.length - 1;
                return (
                  <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                    <div style={{ fontSize: 9, color: "var(--ink-4)", fontFamily: "Geist Mono" }}>€{v}M</div>
                    <div style={{ width: "100%", height: h, background: isLast ? riskColor : "var(--primary)",
                      borderRadius: "3px 3px 0 0", opacity: isLast ? 0.9 : 0.5 }} />
                    <div style={{ fontSize: 9, color: isLast ? "var(--ink)" : "var(--ink-4)", fontWeight: isLast ? 600 : 400 }}>{ty[i]}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Signals */}
        <div className="ai-card">
          <div className="ai-h">
            <div className="ai-mark"><Icons.Spark size={14} /></div>
            <div><div className="ai-title">Category Signals</div></div>
          </div>
          <div className="ai-insights">
            <div className="ai-insight"><div className="marker" /><div>
              {over
                ? `Spend is €${Math.abs(c.spend - c.budget).toFixed(1)}M over budget (${Math.abs(variance)}% variance) — review vendor contracts and maverick purchases.`
                : `Spend is within budget with €${(c.budget - c.spend).toFixed(1)}M headroom remaining.`}
            </div></div>
            <div className="ai-insight"><div className="marker" /><div>
              {c.suppliers <= 2
                ? `Single-source risk: only ${c.suppliers} active supplier(s). Consider qualifying at least one alternative to reduce dependency.`
                : `${c.suppliers} active suppliers — consider consolidating to top 2–3 to improve volume leverage and negotiation position.`}
            </div></div>
            <div className="ai-insight"><div className="marker" /><div>
              {`Total growth of +${c.growth || 0}% since ${ty[0] || "baseline"}. ${(c.growth || 0) > 100
                ? "Rapid acceleration — validate demand drivers and ensure category strategy is in place."
                : (c.growth || 0) > 30
                  ? "Significant growth — consider multi-year framework agreements to lock in pricing."
                  : "Steady growth within expected range."}`}
            </div></div>
          </div>
        </div>
      </div>
    );
  }

  if (d.kind === "signal") {
    const s = d.data;
    return (
      <div className="col">
        <div style={{ fontSize: 15, lineHeight: 1.6 }}>{s.summary || s.text}</div>
        <div className="flex gap-2">
          <span className={`chip ${s.relevance >= 8 ? "bad" : s.relevance >= 6 ? "warn" : "info"}`}>
            <span className="dot" />{s.relevance >= 8 ? "Critical" : s.relevance >= 6 ? "High" : "Medium"}
          </span>
          {s.source && <span className="chip">{s.source}</span>}
        </div>
        {s.action && (
          <div className="ai-card">
            <div className="ai-h">
              <div className="ai-mark"><Icons.Spark size={14} /></div>
              <div><div className="ai-title">Recommended action</div></div>
            </div>
            <div className="ai-insights">
              <div className="ai-insight"><div className="marker" /><div>{s.action}</div></div>
            </div>
          </div>
        )}
      </div>
    );
  }

  return null;
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
