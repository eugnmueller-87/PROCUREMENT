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

function TopBar({ active, onOpenCmd, onMenu }) {
  return (
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
        <div className="tb-btn"><Icons.Sparkles /></div>
        <div className="tb-btn"><Icons.Bell /><span className="dot" /></div>
        <div className="tb-btn"><Icons.Cog /></div>
      </div>
    </header>
  );
}

function CmdPalette({ open, onClose, onNav }) {
  const [q, setQ] = useState("");
  const inputRef = useRef(null);
  useEffect(() => { if (open) setTimeout(() => inputRef.current?.focus(), 50); else setQ(""); }, [open]);

  const items = useMemo(() => {
    const navItems = NAV.map(n => ({ kind: "Go to", label: n.label, action: () => { onNav(n.id); onClose(); }, ico: n.icon }));
    const actions = [
      { kind: "Action", label: "Upload spend data",       action: () => { onNav("dashboard"); onClose(); }, ico: "Upload" },
      { kind: "Action", label: "Scan contract (CLM)",     action: () => { onNav("clm"); onClose(); }, ico: "CLM" },
      { kind: "Action", label: "Run Icarus market scan",  action: () => { onNav("icarus"); onClose(); }, ico: "Bolt" },
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
