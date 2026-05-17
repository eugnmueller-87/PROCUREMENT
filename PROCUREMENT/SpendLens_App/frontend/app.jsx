// SpendLens — main app router
const { useState: useS, useEffect: useE } = React;

const API = "";  // same origin

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
  window.__openDrawer = openDrawer;

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
      <TopBar active={route} onOpenCmd={() => setCmdOpen(true)} onMenu={() => setSbExpanded(s => !s)} />
      <main className="main">
        {Screen
          ? <Screen openDrawer={openDrawer} api={API} />
          : <div style={{ padding: 40, color: "var(--ink-3)" }}>Screen not found: {route}</div>
        }
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
