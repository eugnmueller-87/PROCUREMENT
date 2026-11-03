// SpendLens — CLM (Contract Lifecycle Management) screen
const { useState: useS, useEffect: useE, useRef: useR } = React;

function CLM({ openDrawer, api }) {
  const [contracts, setContracts] = useS([]);
  const [scanning, setScanning] = useS(false);
  const [saving, setSaving] = useS(false);
  const [result, setResult] = useS(null);
  const [error, setError] = useS("");
  const [vendorName, setVendorName] = useS("");
  const [contractType, setContractType] = useS("MSA");
  const [file, setFile] = useS(null);
  const [dragOver, setDragOver] = useS(false);
  const fileRef = useR(null);

  useE(() => { loadContracts(); }, []);

  const loadContracts = async () => {
    try {
      const r = await fetch(`${api}/api/contracts`);
      const d = await r.json();
      setContracts(d.contracts || []);
    } catch (e) {}
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  };

  const scan = async () => {
    if (!file) { setError("Please select a contract file first"); return; }
    setScanning(true);
    setError("");
    setResult(null);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("vendor_name", vendorName);
    fd.append("contract_type", contractType);
    try {
      const res = await fetch(`${api}/api/contracts/scan`, { method: "POST", body: fd });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Scan failed"); }
      const d = await res.json();
      setResult(d);
    } catch (e) {
      setError(e.message);
    }
    setScanning(false);
  };

  const save = async () => {
    if (!file) return;
    setSaving(true);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("vendor_name", vendorName);
    fd.append("contract_type", contractType);
    try {
      const res = await fetch(`${api}/api/contracts/save`, { method: "POST", body: fd });
      if (!res.ok) throw new Error("Save failed");
      await loadContracts();
      setResult(null);
      setFile(null);
      setVendorName("");
    } catch (e) {
      setError(e.message);
    }
    setSaving(false);
  };

  const flagColor = (f) => ({ green: "var(--good)", yellow: "var(--warn)", red: "var(--bad)" }[f] || "var(--ink-4)");
  const levelClass = (l) => ({ Low: "good", Medium: "warn", High: "bad", Critical: "bad" }[l] || "info");

  return (
    <div className="col">
      <div className="page-h">
        <div>
          <h1>Contract Lifecycle Management</h1>
          <div className="sub">AI clause extraction · risk flagging · playbook compliance · renewal tracking</div>
        </div>
      </div>

      {/* Upload form */}
      <div className="card">
        <div className="card-h"><h3>Scan Contract</h3></div>
        <div className="grid" style={{ gridTemplateColumns: "1fr auto auto", gap: 16, alignItems: "end" }}>
          {/* Drop zone */}
          <div
            className={`drop-zone${dragOver ? " over" : ""}`}
            onClick={() => fileRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
          >
            <div className="drop-icon"><Icons.Upload size={28} color={dragOver ? "var(--primary)" : "var(--ink-4)"} /></div>
            <div className="drop-label">{file ? file.name : "Drop PDF or DOCX here"}</div>
            <div className="drop-sub">{file ? `${(file.size / 1024).toFixed(0)} KB` : "or click to browse"}</div>
            <input ref={fileRef} type="file" accept=".pdf,.docx,.doc" style={{ display: "none" }}
              onChange={e => setFile(e.target.files[0])} />
          </div>

          {/* Meta fields */}
          <div className="col" style={{ gap: 10, minWidth: 200 }}>
            <div>
              <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--ink-3)", marginBottom: 6 }}>Vendor Name</div>
              <input className="input" style={{ width: "100%" }} placeholder="e.g. Salesforce GmbH (optional)"
                value={vendorName} onChange={e => setVendorName(e.target.value)} />
            </div>
            <div>
              <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--ink-3)", marginBottom: 6 }}>Contract Type</div>
              <select className="select" style={{ width: "100%" }} value={contractType} onChange={e => setContractType(e.target.value)}>
                {["MSA", "SaaS", "Freelancer", "NDA", "Lease", "Service Agreement", "Other"].map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
          </div>

          {/* Actions */}
          <div className="col" style={{ gap: 8 }}>
            <button className="btn primary" onClick={scan} disabled={scanning || !file}>
              {scanning ? <><div className="spin" style={{ width: 14, height: 14 }} />Scanning…</> : <><Icons.Search size={14} />Scan Contract</>}
            </button>
            {result && (
              <button className="btn good" onClick={save} disabled={saving}>
                {saving ? "Saving…" : <><Icons.Check size={14} />Save to SpendLens</>}
              </button>
            )}
          </div>
        </div>

        {error && <div style={{ marginTop: 12, padding: "10px 14px", background: "var(--bad-soft)", borderRadius: "var(--r-sm)", color: "var(--bad)", fontSize: 13 }}>{error}</div>}
      </div>

      {/* Scan result */}
      {result && <ScanResult result={result} openDrawer={openDrawer} flagColor={flagColor} levelClass={levelClass} />}

      {/* Contract history */}
      <div className="card">
        <div className="card-h">
          <h3>Contract History</h3>
          <span className="sub">{contracts.length} contracts scanned</span>
        </div>
        {contracts.length === 0
          ? <div style={{ padding: "24px 0", textAlign: "center", color: "var(--ink-3)" }}>No contracts scanned yet</div>
          : (
            <table className="t">
              <thead>
                <tr>
                  <th>Vendor</th>
                  <th>Type</th>
                  <th>Expiry</th>
                  <th className="num">Risk Score</th>
                  <th>Risk Level</th>
                  <th>Scanned</th>
                </tr>
              </thead>
              <tbody>
                {contracts.map(c => (
                  <tr key={c.id} style={{ cursor: "pointer" }} onClick={() => openDrawer({ kind: "contract", data: c })}>
                    <td style={{ fontWeight: 500 }}>{c.vendorName || c.filename}</td>
                    <td className="muted">{c.contractType}</td>
                    <td className="mono">{c.endDate || "—"}</td>
                    <td className="num mono">{c.riskScore?.toFixed(1) || "—"}</td>
                    <td><span className={`tag ${levelClass(c.riskLevel)}`}>{c.riskLevel}</span></td>
                    <td className="muted">{c.scannedAt?.slice(0, 10) || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        }
      </div>
    </div>
  );
}

function ScanResult({ result, openDrawer, flagColor, levelClass }) {
  const clauses = result._clauses || result;
  const flags = result.clause_flags ? (typeof result.clause_flags === "string" ? JSON.parse(result.clause_flags) : result.clause_flags) : {};
  const actions = result.required_actions ? (typeof result.required_actions === "string" ? JSON.parse(result.required_actions) : result.required_actions) : [];
  const score = result.risk_score || 0;
  const level = result.risk_level || "Medium";

  const clauseItems = [
    ["Start Date", clauses.start_date],
    ["End Date", clauses.end_date],
    ["Notice Period", clauses.notice_period_days ? `${clauses.notice_period_days} days` : null],
    ["Auto-Renewal", clauses.auto_renewal ? `Yes – ${clauses.auto_renewal_period || "period unknown"}` : "No"],
    ["Penalty Cap", clauses.penalty_cap_pct ? `${clauses.penalty_cap_pct}%` : null],
    ["Liability Cap", clauses.liability_cap],
    ["Jurisdiction", clauses.jurisdiction],
    ["Payment Terms", clauses.payment_terms],
    ["Price Adjustment", clauses.price_adjustment],
    ["SLA Terms", clauses.sla_terms],
    ["Termination Rights", clauses.termination_rights],
    ["Contract Value", clauses.contract_value],
  ].filter(([, v]) => v);

  return (
    <div className="col">
      {/* Risk gauge + summary */}
      <div className="grid" style={{ gridTemplateColumns: "auto 1fr", gap: 20 }}>
        <div className="card" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minWidth: 180 }}>
          <RiskArc score={score} level={level} />
        </div>
        <div className="card">
          <div className="card-h"><h3>Executive Summary</h3></div>
          <p style={{ margin: 0, fontSize: 13, lineHeight: 1.7, color: "var(--ink-2)" }}>{result.risk_summary || clauses.executive_summary || "No summary available."}</p>
          {result.missing_clauses && (
            <div style={{ marginTop: 12, fontSize: 12, color: "var(--warn)" }}>
              <strong>Missing clauses:</strong> {result.missing_clauses}
            </div>
          )}
        </div>
      </div>

      {/* Clause cards */}
      <div className="card">
        <div className="card-h"><h3>Extracted Clauses</h3><span className="sub">{clauseItems.length} clauses found</span></div>
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 10 }}>
          {clauseItems.map(([label, val]) => {
            const key = label.toLowerCase().replace(/ /g, "_");
            const flag = Object.entries(flags).find(([k]) => k.includes(key.split("_")[0]))?.[1];
            return (
              <div key={label} style={{ padding: "12px 14px", border: "1px solid var(--hairline)", borderRadius: "var(--r-sm)", borderLeft: flag ? `3px solid ${flagColor(flag)}` : undefined }}>
                <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--ink-3)", marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 13, color: "var(--ink)" }}>{String(val).slice(0, 120)}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Required actions */}
      {actions.length > 0 && (
        <div className="ai-card">
          <div className="ai-h">
            <div className="ai-mark"><Icons.Spark size={14} /></div>
            <div>
              <div className="ai-title">Required Actions</div>
              <div className="ai-sub">{actions.length} item{actions.length !== 1 ? "s" : ""} require attention</div>
            </div>
          </div>
          <div className="ai-insights">
            {actions.map((a, i) => (
              <div key={i} className={`ai-insight ${a.startsWith("[CRITICAL]") || a.startsWith("[MISSING]") ? "bad" : "warn"}`}>
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

window.CLM = CLM;
