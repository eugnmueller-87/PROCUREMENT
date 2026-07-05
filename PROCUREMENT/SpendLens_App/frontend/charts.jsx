// SpendLens — SVG chart primitives

// Shared risk utilities — used by all screens
const RISK_COLOR = { critical: "var(--bad)", high: "var(--warn)", medium: "var(--info)", low: "var(--good)" };
const RISK_CLASS = { critical: "bad", high: "warn", medium: "info", low: "good", Critical: "bad", High: "warn", Medium: "info", Low: "good" };
const riskColor = (r) => RISK_COLOR[r] || "var(--ink-3)";
const riskClass = (r) => RISK_CLASS[r] || "info";

const fmtK = (n) => {
  if (n == null) return "";
  if (Math.abs(n) >= 1000) return "€" + (n / 1000).toFixed(1) + "M";
  return "€" + n.toLocaleString() + "K";
};
const fmtM = (n) => n == null ? "" : "€" + n.toFixed(1) + "M";

// ── Shared hover tooltip ─────────────────────────────────────────────────────────
// A single floating tooltip driven by a hook. Charts call show(evt, node) on
// mouse move and hide() on leave; the tooltip follows the cursor and flips to
// stay on-screen. `node` is any JSX (rows of label + value).
function useTip() {
  const [tip, setTip] = React.useState(null); // { x, y, node }
  const show = React.useCallback((e, node) => {
    setTip({ x: e.clientX, y: e.clientY, node });
  }, []);
  const hide = React.useCallback(() => setTip(null), []);
  return { tip, show, hide };
}

function ChartTip({ tip }) {
  if (!tip) return null;
  // Flip left/up when near the right/bottom viewport edges.
  const vw = window.innerWidth, vh = window.innerHeight;
  const flipX = tip.x > vw - 220;
  const flipY = tip.y > vh - 160;
  const style = {
    position: "fixed",
    left: flipX ? tip.x - 14 : tip.x + 14,
    top: flipY ? tip.y - 14 : tip.y + 14,
    transform: `translate(${flipX ? "-100%" : "0"}, ${flipY ? "-100%" : "0"})`,
    zIndex: 80,
    pointerEvents: "none",
  };
  return <div className="chart-tip" style={style}>{tip.node}</div>;
}

// One row inside a tooltip: swatch + label on the left, value on the right.
function TipRow({ color, label, value, bold }) {
  return (
    <div className="chart-tip-row">
      {color && <span className="chart-tip-dot" style={{ background: color }} />}
      <span className="chart-tip-label" style={bold ? { fontWeight: 600, color: "var(--ink)" } : null}>{label}</span>
      <span className="chart-tip-val num" style={bold ? { fontWeight: 600 } : null}>{value}</span>
    </div>
  );
}

// ── Sparkline ──────────────────────────────────────────────────────────────────
function Sparkline({ data, color = "var(--primary)", height = 30 }) {
  if (!data || !data.length) return null;
  const w = 100, h = 28;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => [
    (i / (data.length - 1)) * w,
    h - ((v - min) / range) * h * 0.85 - 2,
  ]);
  const path = pts.map((p, i) => (i ? "L" : "M") + p[0] + " " + p[1]).join(" ");
  const areaPath = path + ` L ${w} ${h} L 0 ${h} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: "100%", height }} className="kpi-spark">
      <path d={areaPath} fill={color} opacity="0.10" />
      <path d={path} fill="none" stroke={color} strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="2.2" fill={color} />
    </svg>
  );
}

// ── Stacked Area ───────────────────────────────────────────────────────────────
function StackedArea({ series, xLabels, height = 280, highlightX = null }) {
  const w = 800, h = height - 30;
  const n = xLabels.length;
  const wrapRef = React.useRef(null);
  const [hoverI, setHoverI] = React.useState(-1);
  const { tip, show, hide } = useTip();

  const stacks = xLabels.map((_, i) => {
    let acc = 0;
    return series.map(s => { acc += (s.data[i] || 0); return acc; });
  });
  const maxY = Math.max(...stacks.map(s => s[s.length - 1]), 1);
  const x = (i) => (i / Math.max(n - 1, 1)) * w;
  const y = (v) => h - (v / maxY) * h;

  const COLORS = [
    "var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)",
    "var(--chart-5)", "var(--chart-6)", "var(--chart-7)", "var(--chart-8)",
    "var(--chart-9)", "var(--chart-10)", "var(--chart-11)",
  ];
  const colorOf = (si) => COLORS[si % COLORS.length];

  const polys = series.map((s, si) => {
    const top = xLabels.map((_, i) => [x(i), y(stacks[i][si])]);
    const bot = xLabels.map((_, i) => [x(i), y(si === 0 ? 0 : stacks[i][si - 1])]).reverse();
    const pts = [...top, ...bot].map(p => p.join(",")).join(" ");
    return { id: s.id || si, color: colorOf(si), pts, name: s.name };
  });

  const ticks = [0, 0.25, 0.5, 0.75, 1].map(t => ({ v: maxY * t, y: h - t * h }));
  const hlIdx = highlightX ? xLabels.indexOf(highlightX) : -1;
  const activeIdx = hoverI >= 0 ? hoverI : hlIdx;

  // Map a mouse position over the plot to the nearest year index.
  const onMove = (e) => {
    const box = wrapRef.current?.getBoundingClientRect();
    if (!box) return;
    const frac = (e.clientX - box.left) / box.width;
    const i = Math.max(0, Math.min(n - 1, Math.round(frac * (n - 1))));
    setHoverI(i);
    const yearTotal = stacks[i][series.length - 1];
    // Show categories present at this year, largest contribution first.
    const rows = series
      .map((s, si) => ({ name: s.name, v: s.data[i] || 0, color: colorOf(si) }))
      .filter(r => r.v > 0)
      .sort((a, b) => b.v - a.v);
    show(e, (
      <div>
        <div className="chart-tip-head">{xLabels[i]} · total {fmtM(yearTotal)}</div>
        {rows.map(r => <TipRow key={r.name} color={r.color} label={r.name} value={fmtM(r.v)} />)}
      </div>
    ));
  };
  const onLeave = () => { setHoverI(-1); hide(); };

  return (
    <div ref={wrapRef} style={{ width: "100%", overflow: "visible", position: "relative", cursor: "crosshair" }}
      onMouseMove={onMove} onMouseLeave={onLeave}>
      <svg viewBox={`-40 -8 ${w + 120} ${h + 36}`} preserveAspectRatio="none" style={{ width: "100%", height }}>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1="0" y1={t.y} x2={w} y2={t.y} stroke="var(--hairline)" strokeWidth="1" />
            <text x="-8" y={t.y + 3} fontSize="10" fill="var(--ink-3)" textAnchor="end" fontFamily="Geist Mono">
              {t.v >= 1 ? Math.round(t.v) + "M" : (t.v * 1000).toFixed(0) + "K"}
            </text>
          </g>
        ))}
        {polys.map((p, si) => (
          <polygon key={p.id} points={p.pts} fill={p.color}
            opacity={hoverI >= 0 ? 0.55 : 0.85} style={{ transition: "opacity 120ms" }} />
        ))}
        {/* Crosshair + emphasized points at the hovered/selected year */}
        {activeIdx >= 0 && (
          <g style={{ pointerEvents: "none" }}>
            <line x1={x(activeIdx)} y1={0} x2={x(activeIdx)} y2={h} stroke="var(--ink)" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.5" />
            {hoverI >= 0 && series.map((s, si) => (
              (s.data[activeIdx] || 0) > 0
                ? <circle key={si} cx={x(activeIdx)} cy={y(stacks[activeIdx][si])} r="2.6"
                    fill={colorOf(si)} stroke="var(--card)" strokeWidth="1" />
                : null
            ))}
            <rect x={x(activeIdx) - 18} y={-8} width={36} height={14} fill="var(--primary)" rx="3" />
            <text x={x(activeIdx)} y={1} fontSize="9" fill="var(--primary-ink)" textAnchor="middle" fontFamily="Geist Mono" fontWeight="600">{xLabels[activeIdx]}</text>
          </g>
        )}
        {xLabels.map((lbl, i) => (
          <text key={i} x={x(i)} y={h + 18} fontSize="10.5"
            fill={i === activeIdx ? "var(--primary)" : "var(--ink-3)"}
            fontWeight={i === activeIdx ? "700" : "400"}
            textAnchor="middle" fontFamily="Geist Mono">{lbl}</text>
        ))}
      </svg>
      <ChartTip tip={tip} />
    </div>
  );
}

// ── Horizontal Bar (spend vs budget) ──────────────────────────────────────────
function SpendVsBudget({ data, height = 320, absMax = null }) {
  const maxV = absMax || Math.max(...data.map(d => Math.max(d.spend || 0, d.budget || 0)), 1);
  const { tip, show, hide } = useTip();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
      {data.map(d => {
        const over = d.spend > d.budget;
        const spendPct = (d.spend / maxV) * 100;
        const budgetPct = (d.budget / maxV) * 100;
        const overPct = over ? ((d.spend - d.budget) / maxV) * 100 : 0;
        const variance = d.budget ? ((d.spend - d.budget) / d.budget * 100) : 0;
        const onMove = (e) => show(e, (
          <div>
            <div className="chart-tip-head">{d.name}</div>
            <TipRow color="var(--primary)" label="Spend" value={fmtM(d.spend)} />
            <TipRow color="var(--ink-3)" label="Budget" value={fmtM(d.budget)} />
            <TipRow color={over ? "var(--bad)" : "var(--good)"} label="Variance"
              value={`${over ? "+" : ""}${variance.toFixed(1)}%`} bold />
          </div>
        ));
        return (
          <div key={d.name} style={{ display: "grid", gridTemplateColumns: "150px 1fr 70px", gap: 12, alignItems: "center", fontSize: 12, cursor: "default" }}
            onMouseMove={onMove} onMouseLeave={hide}>
            <div style={{ color: "var(--ink-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={d.name}>{d.name}</div>
            <div style={{ position: "relative", height: 22, background: "var(--bg-sunk)", borderRadius: 4 }}>
              <div style={{ position: "absolute", left: `${budgetPct}%`, top: -2, bottom: -2, width: 2, background: "var(--ink-3)", opacity: 0.4 }} />
              <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: `${spendPct - overPct}%`, background: "var(--primary)", borderRadius: "4px 0 0 4px" }} />
              {over && <div style={{ position: "absolute", left: `${spendPct - overPct}%`, top: 0, bottom: 0, width: `${overPct}%`, background: "var(--bad)", borderRadius: "0 4px 4px 0" }} />}
            </div>
            <div className="num" style={{ textAlign: "right", color: "var(--ink-2)", fontSize: 11 }}>€{d.spend}M</div>
          </div>
        );
      })}
      <ChartTip tip={tip} />
    </div>
  );
}

// ── Bubble / Risk Map ──────────────────────────────────────────────────────────
function RiskBubble({ data, height = 320, xLabel = "Spend (€M)" }) {
  const w = 720, h = height - 30;
  const padL = 56, padR = 20, padT = 20, padB = 40;
  const innerW = w - padL - padR, innerH = h - padT - padB;
  const maxX = Math.max(...data.map(d => d.x || 0), 1) * 1.15;
  // Y axis: 0–10 risk scale
  const maxY = 10;
  const maxR = Math.max(...data.map(d => d.r || 0), 1);
  const colorFor = (r) => ({ critical: "var(--bad)", high: "var(--warn)", medium: "var(--info)", low: "var(--good)" }[r] || "var(--ink-3)");
  const sx = (v) => padL + (v / maxX) * innerW;
  const sy = (v) => padT + innerH - (v / maxY) * innerH;

  // Y-axis tick labels
  const yTicks = [
    { v: 2, label: "Low" },
    { v: 4, label: "Medium" },
    { v: 7, label: "High" },
    { v: 9, label: "Critical" },
  ];

  // Danger zone: high spend (right 40%) + high risk (top 50%)
  const dangerX = sx(maxX * 0.6);
  const dangerY = sy(6);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: "100%", height, overflow: "visible" }}>
      {/* Danger zone */}
      <rect x={dangerX} y={padT} width={w - padR - dangerX} height={dangerY - padT} fill="var(--bad-soft)" opacity="0.35" rx="4" />
      <text x={w - padR - 6} y={padT + 14} fontSize="10" textAnchor="end" fill="var(--bad)" fontWeight="600">DANGER ZONE</text>

      {/* Grid lines */}
      {yTicks.map(t => (
        <g key={t.v}>
          <line x1={padL} x2={w - padR} y1={sy(t.v)} y2={sy(t.v)} stroke="var(--hairline)" strokeDasharray="3 3" />
          <text x={padL - 6} y={sy(t.v) + 4} fontSize="10" fill="var(--ink-3)" textAnchor="end">{t.label}</text>
        </g>
      ))}

      {/* X axis ticks */}
      {[0, 0.25, 0.5, 0.75, 1].map(t => {
        const val = maxX * t / 1.15;
        return (
          <g key={t}>
            <line x1={sx(val)} x2={sx(val)} y1={padT + innerH} y2={padT + innerH + 4} stroke="var(--hairline)" />
            <text x={sx(val)} y={padT + innerH + 16} fontSize="10" fill="var(--ink-3)" textAnchor="middle">€{val.toFixed(0)}M</text>
          </g>
        );
      })}

      {/* Axis labels */}
      <text x={padL + innerW / 2} y={h - 4} fontSize="10.5" fill="var(--ink-3)" textAnchor="middle">{xLabel}</text>

      {/* Bubbles */}
      {data.map((d, i) => {
        const r = 10 + (d.r / maxR) * 26;
        const cx = sx(d.x), cy = sy(d.y);
        return (
          <g key={i}>
            <circle cx={cx} cy={cy} r={r} fill={colorFor(d.risk)} opacity="0.6" stroke={colorFor(d.risk)} strokeWidth="1.5" />
            <text x={cx} y={cy - r - 5} fontSize="10.5" fill="var(--ink-2)" textAnchor="middle" style={{ pointerEvents: "none" }}>
              {d.name.length > 14 ? d.name.split(" ")[0] : d.name}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ── Treemap ────────────────────────────────────────────────────────────────────
function Treemap({ items, height = 380, onPick }) {
  const colorFor = (r) => ({ critical: "var(--bad)", high: "var(--warn)", medium: "var(--info)", low: "var(--good)" }[r] || "var(--ink-3)");
  const { tip, show, hide } = useTip();
  const [hover, setHover] = React.useState(null);
  const sorted = [...items].sort((a, b) => b.value - a.value);
  const total = items.reduce((s, i) => s + i.value, 0) || 1;
  const W = 1000, H = height;

  // Simple weighted columns
  const col0 = [sorted[0]];
  const col1 = sorted.slice(1, 3);
  const col2 = sorted.slice(3, 6);
  const col3 = sorted.slice(6);
  const cols = [col0, col1, col2, col3].filter(c => c.length > 0);
  const colSums = cols.map(c => c.reduce((s, i) => s + i.value, 0));
  const totalColSum = colSums.reduce((a, b) => a + b, 0) || 1;

  const out = [];
  let cx = 0;
  cols.forEach((col, ci) => {
    const cw = (colSums[ci] / totalColSum) * W;
    const csum = colSums[ci] || 1;
    let cy = 0;
    col.forEach(it => {
      const ih = (it.value / csum) * H;
      out.push({ ...it, x: cx, y: cy, w: cw, h: ih });
      cy += ih;
    });
    cx += cw;
  });

  return (
    <div style={{ width: "100%", position: "relative" }}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height }}>
        {out.map((r, i) => {
          const onMove = (e) => {
            setHover(i);
            show(e, (
              <div>
                <div className="chart-tip-head">{r.name}</div>
                <TipRow color={colorFor(r.risk)} label="Spend" value={`€${r.value}M`} bold />
                <TipRow label="Share" value={`${(r.value / total * 100).toFixed(1)}%`} />
                <TipRow label="Risk" value={r.risk} />
              </div>
            ));
          };
          return (
            <g key={i} style={{ cursor: "pointer" }}
              onClick={() => onPick && onPick(r)}
              onMouseMove={onMove}
              onMouseLeave={() => { setHover(null); hide(); }}>
              <rect x={r.x + 2} y={r.y + 2} width={r.w - 4} height={r.h - 4} fill={colorFor(r.risk)}
                opacity={hover === i ? 1 : 0.85} rx="3" style={{ transition: "opacity 120ms" }} />
              <text x={r.x + 12} y={r.y + 22} fontSize="13" fill="var(--card)" fontWeight="600" style={{ pointerEvents: "none" }}>{r.name}</text>
              <text x={r.x + 12} y={r.y + 38} fontSize="11" fill="var(--card)" opacity="0.85" fontFamily="Geist Mono" style={{ pointerEvents: "none" }}>€{r.value}M</text>
            </g>
          );
        })}
      </svg>
      <ChartTip tip={tip} />
    </div>
  );
}

// ── Donut ──────────────────────────────────────────────────────────────────────
function Donut({ value, max = 100, size = 96, label, sub, color = "var(--primary)" }) {
  const r = 38, c = 2 * Math.PI * r;
  const pct = Math.min(1, value / max);
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <svg viewBox="0 0 100 100" width={size} height={size}>
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--bg-sunk)" strokeWidth="8" />
        <circle cx="50" cy="50" r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={`${c * pct} ${c}`} strokeDashoffset={c * 0.25} strokeLinecap="round"
          transform="rotate(-90 50 50)" />
        <text x="50" y="54" textAnchor="middle" fontSize="20" fill="var(--ink)" fontFamily="Geist Mono" fontWeight="500">{value}{max === 100 ? "%" : ""}</text>
      </svg>
      {label && <div style={{ fontSize: 11.5, color: "var(--ink-3)", letterSpacing: "0.05em", textTransform: "uppercase" }}>{label}</div>}
      {sub && <div style={{ fontSize: 11, color: "var(--ink-4)" }}>{sub}</div>}
    </div>
  );
}

// ── Risk score arc (CLM) ───────────────────────────────────────────────────────
function RiskArc({ score, level }) {
  const colors = { Low: "var(--good)", Medium: "var(--warn)", High: "var(--bad)", Critical: "var(--bad)" };
  const color = colors[level] || "var(--info)";
  const r = 42, c = Math.PI * r; // half circle
  const pct = score / 10;
  return (
    <div className="risk-arc-wrap">
      <svg viewBox="0 0 100 56" width="140" height="80">
        <path d="M 8 50 A 42 42 0 0 1 92 50" fill="none" stroke="var(--bg-sunk)" strokeWidth="9" strokeLinecap="round" />
        <path d="M 8 50 A 42 42 0 0 1 92 50" fill="none" stroke={color} strokeWidth="9" strokeLinecap="round"
          strokeDasharray={`${c * pct} ${c}`} />
        <text x="50" y="46" textAnchor="middle" fontSize="20" fill="var(--ink)" fontFamily="Geist Mono" fontWeight="600">{score.toFixed(1)}</text>
        <text x="50" y="56" textAnchor="middle" fontSize="9" fill="var(--ink-3)">/10</text>
      </svg>
      <span className={`tag ${level === "Low" ? "good" : level === "Medium" ? "warn" : "bad"}`}>{level}</span>
    </div>
  );
}

// ── Waterfall ──────────────────────────────────────────────────────────────────
function Waterfall({ data, height = 260 }) {
  const W = 700, H = height - 24;
  const padL = 36, padR = 8, padT = 10, padB = 36;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  let running = 0;
  const segs = data.map(d => {
    if (d.total) return { ...d, start: 0, end: d.total, isTotal: true };
    const start = running;
    running += d.delta;
    return { ...d, start, end: running };
  });
  const maxY = Math.max(...segs.map(s => s.end)) * 1.05 || 1;
  const bw = innerW / segs.length * 0.7;
  const gap = innerW / segs.length * 0.3;
  const sy = (v) => padT + innerH - (v / maxY) * innerH;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height }}>
      {[0, 0.5, 1].map(t => <line key={t} x1={padL} x2={W - padR} y1={padT + t * innerH} y2={padT + t * innerH} stroke="var(--hairline)" />)}
      {segs.map((s, i) => {
        const x = padL + i * (innerW / segs.length) + gap / 2;
        const y = sy(s.end), yStart = sy(s.start);
        const barH = Math.abs(yStart - y);
        const color = s.isTotal ? "var(--primary)" : s.type === "save" ? "var(--good)" : "var(--info)";
        return (
          <g key={i}>
            <rect x={x} y={Math.min(y, yStart)} width={bw} height={Math.max(2, barH)} fill={color} rx="2" />
            <text x={x + bw / 2} y={Math.min(y, yStart) - 5} fontSize="10.5" fill="var(--ink-2)" textAnchor="middle" fontFamily="Geist Mono">
              {s.isTotal ? `€${s.total}K` : `+€${s.delta}K`}
            </text>
            <text x={x + bw / 2} y={H - 10} fontSize="10" fill="var(--ink-3)" textAnchor="middle">{s.label}</text>
          </g>
        );
      })}
    </svg>
  );
}

Object.assign(window, { Sparkline, StackedArea, SpendVsBudget, RiskBubble, Treemap, Donut, RiskArc, Waterfall, fmtK, fmtM, riskColor, riskClass, RISK_COLOR, RISK_CLASS, useTip, ChartTip, TipRow });
