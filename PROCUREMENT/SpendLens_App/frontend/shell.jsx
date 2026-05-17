// SpendLens — app shell (sidebar, topbar, command palette, drawer)
const { useState, useEffect, useRef, useMemo } = React;

const NAV = [
  { id: "dashboard",  label: "Dashboard",         icon: "Dashboard" },
  { id: "deepdive",   label: "Deep Dive",         icon: "DeepDive" },
  { id: "compliance", label: "Compliance",        icon: "Compliance", badge: null },
  { id: "icarus",     label: "Icarus AI",         icon: "Icarus",     mark: "ai" },
  { id: "strategy",   label: "Category Strategy", icon: "Strategy" },
  { id: "supplier",   label: "Supplier DD",       icon: "Supplier" },
  { id: "clm",        label: "CLM",               icon: "CLM" },
];

function Sidebar({ active, onNav }) {
  return (
    <aside className="sb">
      <div className="sb-logo">
        <div className="sb-logo-mark" />
        <div className="sb-logo-text">SpendLens</div>
      </div>
      <div className="sb-nav">
        <div className="sb-section">Workspace</div>
        {NAV.slice(0, 3).map(n => <NavItem key={n.id} item={n} active={active === n.id} onNav={onNav} />)}
        <div className="sb-section">Intelligence</div>
        {NAV.slice(3, 5).map(n => <NavItem key={n.id} item={n} active={active === n.id} onNav={onNav} />)}
        <div className="sb-section">Suppliers</div>
        {NAV.slice(5).map(n => <NavItem key={n.id} item={n} active={active === n.id} onNav={onNav} />)}
      </div>
      <div className="sb-foot">
        <div className="sb-user">
          <div className="sb-avatar">EM</div>
          <div className="sb-user-meta">
            <div className="sb-user-name">Eugen M.</div>
            <div className="sb-user-org">Procurement</div>
          </div>
        </div>
      </div>
    </aside>
  );
}

function NavItem({ item, active, onNav }) {
  const Ico = Icons[item.icon];
  return (
    <div className={`sb-item${active ? " active" : ""}`} onClick={() => onNav(item.id)}>
      <div className="sb-item-icon">{Ico && <Ico />}</div>
      <div className="sb-item-label">
        {item.label}
        {item.mark === "ai" && (
          <span style={{ marginLeft: 6, fontSize: 9.5, padding: "1px 5px", background: "var(--good-soft)", color: "var(--good)", borderRadius: 4, letterSpacing: "0.06em", fontWeight: 600 }}>AI</span>
        )}
      </div>
      {item.badge != null && <span className="sb-item-badge">{item.badge}</span>}
    </div>
  );
}

const NAV_LABELS = Object.fromEntries(NAV.map(n => [n.id, n.label]));

// ── Notifications data ──────────────────────────────────────────────────────────
const NOTIFICATIONS = [
  { id: 1, type: "critical", title: "Contract overdue", body: "Deloitte MSA expired 47 days ago", time: "Today", action: "clm" },
  { id: 2, type: "warn",     title: "Budget overrun",   body: "Cloud & Compute 9% over budget", time: "Today", action: "deepdive" },
  { id: 3, type: "warn",     title: "Contract expiring", body: "OpenAI API agreement expires in 44 days", time: "Yesterday", action: "clm" },
  { id: 4, type: "info",     title: "New Icarus signals", body: "3 new market signals in AI/ML category", time: "2h ago", action: "icarus" },
  { id: 5, type: "good",     title: "DD complete",      body: "Supplier due diligence for AWS finished", time: "3h ago", action: "supplier" },
];

function TopBar({ active, onOpenCmd, onMenu, onNav }) {
  const [bellOpen, setBellOpen] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [dismissed, setDismissed] = useState([]);
  const bellRef = useRef(null);

  const unread = NOTIFICATIONS.filter(n => !dismissed.includes(n.id));

  useEffect(() => {
    function handler(e) {
      if (bellRef.current && !bellRef.current.contains(e.target)) setBellOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <>
      <header className="tb">
        <div className="tb-btn" onClick={onMenu}><Icons.Menu /></div>
        <div className="crumbs">
          <span>SpendLens</span>
          <Icons.ChevR size={12} color="var(--ink-4)" />
          <strong>{NAV_LABELS[active] || active}</strong>
        </div>
        <div className="tb-search" onClick={onOpenCmd}>
          <Icons.Search size={14} />
          <span>Search suppliers, contracts, categories…</span>
          <span className="kbd">⌘K</span>
        </div>
        <div className="tb-actions">
          <div className="tb-btn" title="AI Assistant" onClick={() => { setAiOpen(true); setBellOpen(false); setSettingsOpen(false); }}>
            <Icons.Sparkles />
          </div>

          {/* Bell with dropdown */}
          <div style={{ position: "relative" }} ref={bellRef}>
            <div className="tb-btn" title="Notifications" onClick={() => { setBellOpen(o => !o); setAiOpen(false); setSettingsOpen(false); }}>
              <Icons.Bell />
              {unread.length > 0 && <span className="dot" style={{ position: "absolute", top: 6, right: 6 }} />}
            </div>
            {bellOpen && (
              <div style={{
                position: "absolute", top: "calc(100% + 8px)", right: 0, width: 320, zIndex: 200,
                background: "var(--bg)", border: "1px solid var(--border)", borderRadius: "var(--r)",
                boxShadow: "0 8px 32px rgba(0,0,0,0.12)", overflow: "hidden",
              }}>
                <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--hairline)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>Notifications</span>
                  {unread.length > 0 && (
                    <span style={{ fontSize: 11, color: "var(--primary)", cursor: "pointer" }}
                      onClick={() => setDismissed(NOTIFICATIONS.map(n => n.id))}>
                      Mark all read
                    </span>
                  )}
                </div>
                {unread.length === 0 ? (
                  <div style={{ padding: 24, textAlign: "center", color: "var(--ink-3)", fontSize: 13 }}>All caught up</div>
                ) : (
                  unread.map(n => (
                    <div key={n.id} style={{
                      padding: "10px 16px", borderBottom: "1px solid var(--hairline)", cursor: "pointer",
                      display: "grid", gridTemplateColumns: "8px 1fr 20px", gap: 10, alignItems: "start",
                    }}
                      onClick={() => { setBellOpen(false); if (n.action) onNav(n.action); }}>
                      <span style={{ width: 8, height: 8, borderRadius: "50%", marginTop: 4, flexShrink: 0,
                        background: n.type === "critical" ? "var(--bad)" : n.type === "warn" ? "var(--warn)" : n.type === "good" ? "var(--good)" : "var(--info)" }} />
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 500 }}>{n.title}</div>
                        <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 2 }}>{n.body}</div>
                        <div style={{ fontSize: 10, color: "var(--ink-4)", marginTop: 3 }}>{n.time}</div>
                      </div>
                      <div style={{ fontSize: 11, color: "var(--ink-4)", cursor: "pointer", padding: 2 }}
                        onClick={e => { e.stopPropagation(); setDismissed(d => [...d, n.id]); }}>×</div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Settings */}
          <div className="tb-btn" title="Settings" onClick={() => { setSettingsOpen(true); setBellOpen(false); setAiOpen(false); }}>
            <Icons.Cog />
          </div>
        </div>
      </header>

      {/* AI Assistant drawer */}
      {aiOpen && <AIAssistant onClose={() => setAiOpen(false)} />}

      {/* Settings drawer */}
      {settingsOpen && <SettingsPanel onClose={() => setSettingsOpen(false)} />}
    </>
  );
}

// ── AI Assistant panel ─────────────────────────────────────────────────────────
function AIAssistant({ onClose }) {
  const [msgs, setMsgs] = useState([
    { role: "ai", text: "Hi Eugen, I'm your procurement AI. Ask me anything about spend, suppliers, or contracts." }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const CANNED = {
    "maverick": "Based on current data, maverick spend is at 12% of total. Top offenders are in Travel & Expenses and Professional Services — both lack blanket PO coverage. Recommended action: issue framework agreements with top 3 suppliers in each category.",
    "cloud": "Cloud & Compute is your largest category at €24M (34% of total spend). It's classified Critical risk due to concentration with AWS (est. 60% share). Consider a multi-cloud strategy and renegotiate reserved instances before the AWS contract renewal in Sep 2026.",
    "contract": "You have 2 critical contract issues: Deloitte MSA expired 47 days ago (immediate action required) and Twilio renews in 75 days with auto-renewal risk. I recommend prioritizing Deloitte renegotiation this week.",
    "saving": "Top 3 savings opportunities identified:\n1. Cloud reserved instances: est. €2.1M (commit 1-year)\n2. Recruitment agency consolidation: est. €0.8M (reduce from 5 to 2 agencies)\n3. SaaS licence audit: est. €0.4M (remove unused seats)",
  };

  const send = async () => {
    const q = input.trim();
    if (!q) return;
    setMsgs(m => [...m, { role: "user", text: q }]);
    setInput("");
    setLoading(true);

    await new Promise(r => setTimeout(r, 800));

    const key = Object.keys(CANNED).find(k => q.toLowerCase().includes(k));
    const reply = key ? CANNED[key]
      : "I can help with spend analysis, supplier risk, contract management, and savings identification. Try asking about maverick spend, Cloud & Compute costs, contract status, or savings opportunities.";

    setMsgs(m => [...m, { role: "ai", text: reply }]);
    setLoading(false);
  };

  return (
    <div style={{
      position: "fixed", top: 0, right: 0, bottom: 0, width: 380, zIndex: 300,
      background: "var(--bg)", borderLeft: "1px solid var(--border)",
      boxShadow: "-8px 0 32px rgba(0,0,0,0.10)", display: "flex", flexDirection: "column",
    }}>
      <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--hairline)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: "var(--primary)", display: "grid", placeItems: "center" }}>
            <Icons.Spark size={14} color="#fff" />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Procurement AI</div>
            <div style={{ fontSize: 11, color: "var(--good)" }}>● Online</div>
          </div>
        </div>
        <div className="tb-btn" onClick={onClose}><Icons.X size={16} /></div>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
        {/* Quick prompts */}
        {msgs.length <= 1 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
            {["Maverick spend status", "Cloud cost risk", "Expiring contracts", "Top savings"].map(p => (
              <span key={p} style={{ fontSize: 11.5, padding: "4px 10px", borderRadius: 999, background: "var(--primary-soft)", color: "var(--primary)", cursor: "pointer", border: "1px solid var(--primary)" }}
                onClick={() => { setInput(p); }}>
                {p}
              </span>
            ))}
          </div>
        )}

        {msgs.map((m, i) => (
          <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "85%", padding: "10px 14px", borderRadius: m.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
              background: m.role === "user" ? "var(--primary)" : "var(--bg-sunk)",
              color: m.role === "user" ? "#fff" : "var(--ink)", fontSize: 13, lineHeight: 1.55,
              whiteSpace: "pre-line",
            }}>{m.text}</div>
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex" }}>
            <div style={{ padding: "10px 14px", borderRadius: "12px 12px 12px 2px", background: "var(--bg-sunk)", display: "flex", gap: 4 }}>
              {[0,1,2].map(i => <span key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--ink-3)", animation: `pulse 1s ${i*0.2}s infinite` }} />)}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ padding: "12px 16px", borderTop: "1px solid var(--hairline)", display: "flex", gap: 8 }}>
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && send()}
          placeholder="Ask about spend, suppliers, contracts…"
          style={{ flex: 1, padding: "8px 12px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--bg-sunk)", fontSize: 13, color: "var(--ink)", outline: "none" }} />
        <button className="btn primary" onClick={send} disabled={loading || !input.trim()}>
          <Icons.Bolt size={14} />
        </button>
      </div>
    </div>
  );
}

// ── Settings panel ─────────────────────────────────────────────────────────────
function SettingsPanel({ onClose }) {
  const [dark, setDark] = useState(document.documentElement.getAttribute("data-theme") === "dark");
  const [density, setDensity] = useState("comfortable");

  const toggleDark = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.setAttribute("data-theme", next ? "dark" : "light");
  };

  return (
    <>
      <div style={{ position: "fixed", inset: 0, zIndex: 290, background: "rgba(0,0,0,0.3)" }} onClick={onClose} />
      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0, width: 340, zIndex: 300,
        background: "var(--bg)", borderLeft: "1px solid var(--border)",
        boxShadow: "-8px 0 32px rgba(0,0,0,0.12)", display: "flex", flexDirection: "column",
      }}>
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--hairline)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontWeight: 600, fontSize: 15 }}>Settings</span>
          <div className="tb-btn" onClick={onClose}><Icons.X size={16} /></div>
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 24 }}>

          {/* Appearance */}
          <div>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--ink-3)", marginBottom: 12 }}>Appearance</div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0" }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>Dark mode</div>
                <div style={{ fontSize: 11, color: "var(--ink-3)" }}>Toggle light / dark theme</div>
              </div>
              <div onClick={toggleDark} style={{
                width: 40, height: 22, borderRadius: 11, background: dark ? "var(--primary)" : "var(--border-2)",
                position: "relative", cursor: "pointer", transition: "background 0.2s",
              }}>
                <div style={{
                  position: "absolute", top: 3, left: dark ? 21 : 3, width: 16, height: 16,
                  borderRadius: "50%", background: "#fff", transition: "left 0.2s",
                }} />
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderTop: "1px solid var(--hairline)" }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>Density</div>
                <div style={{ fontSize: 11, color: "var(--ink-3)" }}>Table and list row spacing</div>
              </div>
              <select className="select" value={density} onChange={e => setDensity(e.target.value)} style={{ fontSize: 12 }}>
                <option value="compact">Compact</option>
                <option value="comfortable">Comfortable</option>
                <option value="spacious">Spacious</option>
              </select>
            </div>
          </div>

          {/* Account */}
          <div>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--ink-3)", marginBottom: 12 }}>Account</div>
            <div style={{ background: "var(--bg-sunk)", borderRadius: 10, padding: "12px 14px", display: "flex", gap: 12, alignItems: "center" }}>
              <div style={{ width: 36, height: 36, borderRadius: "50%", background: "var(--primary)", display: "grid", placeItems: "center", color: "#fff", fontWeight: 600, fontSize: 14 }}>EM</div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>Eugen M.</div>
                <div style={{ fontSize: 11, color: "var(--ink-3)" }}>Procurement Manager</div>
              </div>
            </div>
          </div>

          {/* App info */}
          <div>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--ink-3)", marginBottom: 12 }}>About</div>
            {[["Version", "2.0.0 (React)"], ["Backend", "FastAPI + SQLite"], ["AI", "Claude claude-sonnet-4-6"]].map(([k, v]) => (
              <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--hairline)", fontSize: 12 }}>
                <span style={{ color: "var(--ink-3)" }}>{k}</span>
                <span className="num">{v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

function CmdPalette({ open, onClose, onNav }) {
  const [q, setQ] = useState("");
  const inputRef = useRef(null);
  useEffect(() => { if (open) setTimeout(() => inputRef.current?.focus(), 50); else setQ(""); }, [open]);

  const items = useMemo(() => {
    const navItems = NAV.map(n => ({ kind: "Go to", label: n.label, action: () => { onNav(n.id); onClose(); }, ico: n.icon }));
    const actions = [
      { kind: "Action", label: "Upload spend data",          action: () => { onNav("dashboard"); onClose(); }, ico: "Upload" },
      { kind: "Action", label: "Scan contract (CLM)",        action: () => { onNav("clm"); onClose(); }, ico: "CLM" },
      { kind: "Action", label: "Run Icarus market scan",     action: () => { onNav("icarus"); onClose(); }, ico: "Bolt" },
      { kind: "Action", label: "New supplier due diligence", action: () => { onNav("supplier"); onClose(); }, ico: "Supplier" },
    ];
    const all = [...actions, ...navItems];
    if (!q) return all;
    return all.filter(x => x.label.toLowerCase().includes(q.toLowerCase()));
  }, [q, onNav, onClose]);

  const grouped = items.reduce((m, it) => { (m[it.kind] = m[it.kind] || []).push(it); return m; }, {});

  return (
    <div className={`cmd-bg${open ? " open" : ""}`} onClick={onClose}>
      <div className="cmd" onClick={e => e.stopPropagation()}>
        <div className="cmd-input">
          <Icons.Search size={16} color="var(--ink-3)" />
          <input ref={inputRef} value={q} onChange={e => setQ(e.target.value)} placeholder="Type to search or run a command…" />
          <span className="chip">esc</span>
        </div>
        <div className="cmd-list">
          {Object.entries(grouped).map(([k, list]) => (
            <div key={k}>
              <div className="cmd-group">{k}</div>
              {list.map((it, i) => {
                const Ico = Icons[it.ico] || Icons.Search;
                return (
                  <div key={i} className="cmd-item" onClick={it.action}>
                    <div className="ico"><Ico size={15} /></div>
                    <span>{it.label}</span>
                  </div>
                );
              })}
            </div>
          ))}
          {items.length === 0 && <div style={{ padding: 20, textAlign: "center", color: "var(--ink-3)" }}>No matches.</div>}
        </div>
      </div>
    </div>
  );
}

function Drawer({ open, onClose, title, children }) {
  return (
    <>
      <div className={`drawer-bg${open ? " open" : ""}`} onClick={onClose} />
      <div className={`drawer${open ? " open" : ""}`}>
        <div className="drawer-h">
          <div style={{ fontWeight: 600, fontSize: 15 }}>{title}</div>
          <div className="tb-btn" onClick={onClose}><Icons.X size={16} /></div>
        </div>
        <div className="drawer-body">{children}</div>
      </div>
    </>
  );
}

Object.assign(window, { Sidebar, TopBar, CmdPalette, Drawer, NAV, NAV_LABELS });
