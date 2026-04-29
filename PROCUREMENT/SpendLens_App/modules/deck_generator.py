"""
deck_generator.py — Category Strategy HTML Slide Deck Generator

Produces a self-contained, single-file HTML presentation that the category
manager opens in any browser. SpendLens logo appears top-right on every slide.
Arrow keys and on-screen buttons navigate between slides.
"""

from datetime import datetime, timezone
from html import escape

# ── SpendLens logo (SVG, inline) ─────────────────────────────────────────────
_LOGO_SVG = """<svg width="32" height="32" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
  <polygon points="50,4 93,27 93,73 50,96 7,73 7,27" fill="#EDF0F7" stroke="#1B2A5E" stroke-width="3"/>
  <line x1="50" y1="4" x2="50" y2="96" stroke="#9BAACF" stroke-width="0.8" opacity="0.5"/>
  <line x1="7" y1="27" x2="93" y2="73" stroke="#9BAACF" stroke-width="0.8" opacity="0.5"/>
  <line x1="93" y1="27" x2="7" y2="73" stroke="#9BAACF" stroke-width="0.8" opacity="0.5"/>
  <path d="M28,50 Q50,28 72,50 Q50,72 28,50 Z" fill="none" stroke="#1D9E75" stroke-width="2.5"/>
  <circle cx="50" cy="50" r="11" fill="none" stroke="#1D9E75" stroke-width="2"/>
  <circle cx="50" cy="50" r="6" fill="#1D9E75"/>
  <circle cx="53" cy="47" r="2.5" fill="#9FE1CB" opacity="0.8"/>
</svg>"""

_LOGO_HEADER = f"""
<div class="slide-logo">
  {_LOGO_SVG}
  <span class="slide-logo-text">SpendLens</span>
</div>"""

# ── Slide deck CSS ────────────────────────────────────────────────────────────
_DECK_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --navy:   #1B2A4A;
  --navy2:  #2E5BA8;
  --green:  #00A86B;
  --green2: #1D9E75;
  --green-l:#E1F5EE;
  --red:    #E24B4A;
  --red-l:  #FCEBEB;
  --amber:  #B8860B;
  --amber-l:#FFF3E0;
  --border: #E2E8F0;
  --text:   #1A1A2E;
  --dim:    #64748B;
  --bg:     #F8F9FA;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #1a1a2e;
  overflow: hidden;
  height: 100vh;
}

/* ── Navigation ── */
.nav-bar {
  position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
  display: flex; align-items: center; gap: 12px; z-index: 100;
  background: rgba(27,42,74,0.92); border-radius: 99px;
  padding: 8px 16px; backdrop-filter: blur(8px);
}
.nav-btn {
  width: 32px; height: 32px; border-radius: 50%; border: none;
  background: rgba(255,255,255,0.15); color: white; cursor: pointer;
  font-size: 14px; display: flex; align-items: center; justify-content: center;
  transition: background 0.15s;
}
.nav-btn:hover { background: rgba(255,255,255,0.3); }
.nav-btn:disabled { opacity: 0.3; cursor: default; }
.nav-counter { color: rgba(255,255,255,0.7); font-size: 12px; min-width: 48px; text-align: center; }

/* ── Slides ── */
.slide {
  display: none; position: fixed; inset: 0;
  overflow-y: auto; overflow-x: hidden;
}
.slide.active { display: flex; flex-direction: column; }

/* Slide chrome */
.slide-logo {
  position: absolute; top: 18px; right: 22px;
  display: flex; align-items: center; gap: 7px; z-index: 10;
}
.slide-logo-text {
  font-size: 11px; font-weight: 700; letter-spacing: 0.5px;
}
.slide-footer {
  position: absolute; bottom: 60px; left: 0; right: 0;
  display: flex; justify-content: space-between; padding: 0 40px;
  font-size: 10px; opacity: 0.5;
}

/* ── Cover slide ── */
.slide-cover {
  background: var(--navy);
  color: white;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.slide-cover .slide-logo-text { color: rgba(255,255,255,0.6); }
.cover-badge {
  font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px;
  color: var(--green2); background: rgba(29,158,117,0.15);
  padding: 5px 14px; border-radius: 99px; margin-bottom: 24px;
  display: inline-block; border: 1px solid rgba(29,158,117,0.3);
}
.cover-title {
  font-size: 42px; font-weight: 800; line-height: 1.15; margin-bottom: 12px;
  max-width: 700px;
}
.cover-subtitle {
  font-size: 16px; color: rgba(255,255,255,0.55); margin-bottom: 32px;
}
.cover-divider {
  width: 48px; height: 3px; background: var(--green2); margin: 0 auto 28px;
  border-radius: 99px;
}
.cover-meta { font-size: 12px; color: rgba(255,255,255,0.4); }

/* ── Content slides ── */
.slide-content {
  background: white;
  padding: 48px 52px 90px;
}
.slide-content .slide-logo-text { color: var(--dim); }
.slide-section-label {
  font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px;
  color: var(--green2); margin-bottom: 8px;
}
.slide-title {
  font-size: 26px; font-weight: 800; color: var(--navy); margin-bottom: 24px;
  line-height: 1.2;
}
.slide-footer-content { color: var(--dim); }

/* ── KPI cards (spend overview slide) ── */
.kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 24px; }
.kpi-card {
  border: 1px solid var(--border); border-radius: 10px; padding: 16px;
  background: var(--bg);
}
.kpi-value { font-size: 28px; font-weight: 800; color: var(--navy); line-height: 1; margin-bottom: 4px; }
.kpi-label { font-size: 11px; color: var(--dim); font-weight: 500; }
.kpi-accent { border-top: 3px solid var(--green2); }

/* ── Kraljic ── */
.kraljic-wrap { display: flex; gap: 20px; align-items: flex-start; }
.kraljic-matrix {
  display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr;
  gap: 6px; width: 340px; height: 240px; flex-shrink: 0;
}
.kq { border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; justify-content: flex-end; opacity: 0.5; }
.kq.active { opacity: 1; box-shadow: 0 0 0 3px var(--navy); }
.kq-strategic   { background: #EBF0FB; }
.kq-bottleneck  { background: #FFF3E0; }
.kq-leverage    { background: var(--green-l); }
.kq-non-critical{ background: var(--bg); border: 1px dashed #ddd; }
.kq-name  { font-size: 11px; font-weight: 700; color: var(--navy); }
.kq-desc  { font-size: 9px; color: var(--dim); margin-top: 1px; }
.kq-marker{ font-size: 14px; }
.kraljic-side { flex: 1; }
.k-scores { display: flex; gap: 10px; margin-bottom: 14px; }
.k-score-box { flex: 1; background: var(--bg); border-radius: 8px; padding: 10px; text-align: center; }
.k-score-num { font-size: 24px; font-weight: 800; color: var(--navy); }
.k-score-lbl { font-size: 10px; color: var(--dim); }
.k-rationale { font-size: 12px; color: #444; line-height: 1.65; margin-bottom: 12px; }
.k-posture { font-size: 12px; font-weight: 600; color: #0F6E56; background: var(--green-l); padding: 8px 12px; border-radius: 6px; margin-bottom: 12px; }
.k-actions { list-style: none; display: flex; flex-direction: column; gap: 5px; }
.k-actions li { font-size: 11px; color: #333; padding: 5px 9px; background: var(--bg); border-radius: 5px; }
.k-actions li::before { content: "→ "; color: var(--navy); font-weight: 700; }

/* ── PESTEL ── */
.pestel-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.p-cell { border-radius: 8px; padding: 12px 14px; border: 1px solid var(--border); }
.p-letter { font-size: 20px; font-weight: 900; margin-bottom: 2px; }
.p-dim { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--dim); margin-bottom: 8px; }
.p-points { list-style: none; display: flex; flex-direction: column; gap: 4px; }
.p-points li { font-size: 11px; color: #444; line-height: 1.5; padding-left: 10px; position: relative; }
.p-points li::before { content: "•"; position: absolute; left: 0; color: var(--dim); }
.pc-P  { border-top: 3px solid #4A90D9; } .pc-P  .p-letter { color: #4A90D9; }
.pc-E  { border-top: 3px solid #639922; } .pc-E  .p-letter { color: #639922; }
.pc-S  { border-top: 3px solid #D4537E; } .pc-S  .p-letter { color: #D4537E; }
.pc-T  { border-top: 3px solid #534AB7; } .pc-T  .p-letter { color: #534AB7; }
.pc-En { border-top: 3px solid #1D9E75; } .pc-En .p-letter { color: #1D9E75; }
.pc-L  { border-top: 3px solid #BA7517; } .pc-L  .p-letter { color: #BA7517; }

/* ── SWOT ── */
.swot-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; height: 340px; }
.sw-cell { border-radius: 8px; padding: 14px 16px; }
.sw-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }
.sw-points { list-style: none; display: flex; flex-direction: column; gap: 5px; }
.sw-points li { font-size: 11px; color: #333; line-height: 1.5; }
.sw-strengths    { background: #E8F5E9; border: 1px solid #A5D6A7; }
.sw-strengths .sw-label { color: #2E7D32; }
.sw-weaknesses   { background: #FFEBEE; border: 1px solid #FFCDD2; }
.sw-weaknesses .sw-label { color: #C62828; }
.sw-opportunities{ background: #E3F2FD; border: 1px solid #BBDEFB; }
.sw-opportunities .sw-label { color: #1565C0; }
.sw-threats      { background: #FFF8E1; border: 1px solid #FFE082; }
.sw-threats .sw-label { color: #E65100; }

/* ── Porter's ── */
.porter-grid {
  display: grid; grid-template-columns: 1fr 1.4fr 1fr;
  grid-template-rows: 1fr 1.4fr 1fr; gap: 8px; height: 300px;
}
.pf { border-radius: 8px; padding: 10px 12px; border: 1px solid var(--border); display: flex; flex-direction: column; justify-content: center; }
.pf-center { background: var(--navy); color: white; border: none; grid-column: 2; grid-row: 2; }
.pf-empty  { opacity: 0; pointer-events: none; }
.pf-name   { font-size: 11px; font-weight: 700; color: var(--navy); margin-bottom: 3px; }
.pf-center .pf-name { color: white; font-size: 12px; }
.pf-badge  { font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 99px; margin-bottom: 5px; display: inline-block; }
.pf-high   { background: var(--red-l); color: var(--red); }
.pf-medium { background: var(--amber-l); color: var(--amber); }
.pf-low    { background: var(--green-l); color: #0F6E56; }
.pf-facts  { list-style: none; display: flex; flex-direction: column; gap: 2px; }
.pf-facts li { font-size: 9px; color: #555; line-height: 1.4; }
.porter-summary { font-size: 12px; color: #444; line-height: 1.65; padding: 12px 14px; background: var(--bg); border-radius: 8px; margin-top: 10px; }

/* ── TCO ── */
.tco-bars { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.tco-row  { display: flex; align-items: center; gap: 10px; }
.tco-lbl  { font-size: 11px; color: #333; width: 200px; flex-shrink: 0; }
.tco-outer{ flex: 1; background: #f0f0f0; border-radius: 4px; height: 16px; overflow: hidden; }
.tco-inner{ height: 100%; background: var(--navy); border-radius: 4px; transition: width 0.6s; }
.tco-pct  { font-size: 11px; font-weight: 700; color: var(--navy); width: 38px; text-align: right; flex-shrink: 0; }
.tco-note { font-size: 10px; color: var(--dim); width: 180px; flex-shrink: 0; }
.tco-insight { background: var(--green-l); color: #0F6E56; font-size: 12px; font-weight: 500; padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; }
.tco-levers-hdr { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--dim); margin: 14px 0 6px; }
.tco-levers-list { list-style: none; display: flex; flex-wrap: wrap; gap: 6px; }
.tco-levers-list li { font-size: 11px; background: var(--bg); color: #333; padding: 4px 10px; border-radius: 99px; border: 1px solid var(--border); }
.tco-levers-list li::before { content: "→ "; color: var(--navy); font-weight: 700; }

/* ── Levers ── */
.lever-row {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; margin-bottom: 6px;
}
.lever-bar { width: 6px; border-radius: 99px; align-self: stretch; flex-shrink: 0; }
.lever-bar.high   { background: var(--green2); }
.lever-bar.medium { background: var(--amber); }
.lever-bar.low    { background: #ccc; }
.lever-name   { flex: 1; font-size: 12px; color: #333; font-weight: 500; line-height: 1.5; }
.lever-saving { font-size: 13px; font-weight: 700; color: var(--green2); white-space: nowrap; }
.lever-effort { font-size: 10px; color: var(--dim); background: var(--bg); padding: 2px 7px; border-radius: 99px; margin-top: 3px; display: inline-block; }
.lever-approach { font-size: 12px; color: #444; padding: 10px 13px; background: #eef3ff; border-radius: 6px; border-left: 3px solid var(--navy2); margin-bottom: 10px; }
.lever-timing   { font-size: 11px; color: var(--dim); font-style: italic; }

/* ── Recommendation ── */
.rec-headline { font-size: 22px; font-weight: 800; color: var(--navy); line-height: 1.3; margin-bottom: 10px; }
.rec-posture  { font-size: 13px; color: #444; line-height: 1.7; padding: 12px 14px; background: var(--bg); border-radius: 8px; border-left: 3px solid var(--green2); margin-bottom: 20px; }
.rec-timeline { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 20px; }
.rec-yr { border: 1px solid var(--border); border-radius: 10px; padding: 14px; }
.rec-yr-lbl { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }
.rec-yr-1 .rec-yr-lbl { color: var(--navy); border-bottom: 2px solid var(--navy); padding-bottom: 6px; }
.rec-yr-2 .rec-yr-lbl { color: var(--navy2); border-bottom: 2px solid var(--navy2); padding-bottom: 6px; }
.rec-yr-3 .rec-yr-lbl { color: var(--dim); border-bottom: 2px solid #ccc; padding-bottom: 6px; }
.rec-yr-items { list-style: none; display: flex; flex-direction: column; gap: 5px; }
.rec-yr-items li { font-size: 11px; color: #333; padding-left: 12px; position: relative; line-height: 1.5; }
.rec-yr-items li::before { content: "→"; position: absolute; left: 0; font-weight: 700; }
.rec-yr-1 .rec-yr-items li::before { color: var(--navy); }
.rec-yr-2 .rec-yr-items li::before { color: var(--navy2); }
.rec-yr-3 .rec-yr-items li::before { color: var(--dim); }
.rec-kpi-hdr { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--dim); margin-bottom: 8px; }
.rec-kpis { display: flex; flex-wrap: wrap; gap: 8px; }
.rec-kpi  { font-size: 11px; font-weight: 600; background: var(--green-l); color: #0F6E56; padding: 5px 14px; border-radius: 99px; }

/* ── Print ── */
@media print {
  body { background: white; overflow: visible; height: auto; }
  .slide { display: flex !important; position: relative; page-break-after: always; min-height: 100vh; }
  .slide.active { display: flex; }
  .nav-bar { display: none; }
}
"""

# ── Deck JS ───────────────────────────────────────────────────────────────────
_DECK_JS = """
var _cur = 0;
var _slides = document.querySelectorAll('.slide');
var _total = _slides.length;
document.getElementById('total').textContent = _total;

function _show(n) {
  _slides[_cur].classList.remove('active');
  _cur = Math.max(0, Math.min(n, _total - 1));
  _slides[_cur].classList.add('active');
  document.getElementById('curr').textContent = _cur + 1;
  document.getElementById('prevBtn').disabled = _cur === 0;
  document.getElementById('nextBtn').disabled = _cur === _total - 1;
}

document.addEventListener('keydown', function(e) {
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown')  _show(_cur + 1);
  if (e.key === 'ArrowLeft'  || e.key === 'ArrowUp')    _show(_cur - 1);
});
"""


# ── Slide builder helpers ─────────────────────────────────────────────────────

def _e(s): return escape(str(s)) if s else ""


def _content_slide(section_label: str, title: str, body_html: str, category: str, date_str: str) -> str:
    return f"""
<div class="slide slide-content">
  {_LOGO_HEADER}
  <div class="slide-section-label">{_e(section_label)}</div>
  <div class="slide-title">{_e(title)}</div>
  {body_html}
  <div class="slide-footer">
    <span class="slide-footer-content">{_e(category)} Category Strategy</span>
    <span class="slide-footer-content">{_e(date_str)}</span>
  </div>
</div>"""


def _slide_cover(category: str, date_str: str) -> str:
    return f"""
<div class="slide slide-cover active">
  {_LOGO_HEADER.replace('class="slide-logo"', 'class="slide-logo" style="top:24px;right:28px;"')}
  <div class="cover-badge">Category Strategy</div>
  <div class="cover-title">{_e(category)}</div>
  <div class="cover-divider"></div>
  <div class="cover-subtitle">Procurement Strategy Analysis · SpendLens</div>
  <div class="cover-meta">{_e(date_str)}</div>
</div>"""


def _slide_spend(spend_data: dict, category: str, date_str: str) -> str:
    total   = f"€{spend_data.get('total_spend', 0):,.0f}" if spend_data.get("total_spend") else "N/A"
    vendors = str(spend_data.get("vendor_count", "N/A"))
    mav     = f"{spend_data.get('maverick_rate', 0):.1f}%" if spend_data.get("maverick_rate") is not None else "N/A"
    po      = f"{spend_data.get('po_coverage', 0):.1f}%" if spend_data.get("po_coverage") is not None else "N/A"
    top_v   = spend_data.get("top_vendors", [])
    top_html = "".join(
        f'<div style="padding:5px 0;border-bottom:1px solid #f0f0f0;font-size:12px;color:#333;">'
        f'<span style="font-weight:600;">{i+1}. {_e(v)}</span></div>'
        for i, v in enumerate(top_v)
    ) or '<div style="font-size:12px;color:#bbb;">No vendor data</div>'

    body = f"""
<div class="kpi-row">
  <div class="kpi-card kpi-accent">
    <div class="kpi-value">{_e(total)}</div>
    <div class="kpi-label">Total Spend</div>
  </div>
  <div class="kpi-card kpi-accent">
    <div class="kpi-value">{_e(vendors)}</div>
    <div class="kpi-label">Active Vendors</div>
  </div>
  <div class="kpi-card kpi-accent">
    <div class="kpi-value">{_e(mav)}</div>
    <div class="kpi-label">Maverick Spend</div>
  </div>
  <div class="kpi-card kpi-accent">
    <div class="kpi-value">{_e(po)}</div>
    <div class="kpi-label">PO Coverage</div>
  </div>
</div>
<div style="font-size:12px;font-weight:700;color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">Top Vendors by Spend</div>
{top_html}"""

    return _content_slide("Spend Overview", "Category Spend Analytics", body, category, date_str)


def _slide_kraljic(data: dict, category: str, date_str: str) -> str:
    q            = data.get("quadrant", "Strategic")
    risk_score   = data.get("supply_risk_score", 5)
    impact_score = data.get("spend_impact_score", 5)
    rationale    = _e(data.get("rationale", ""))
    posture      = _e(data.get("recommended_posture", ""))
    actions      = data.get("key_actions", [])

    q_map = {"Strategic": "kq-strategic", "Leverage": "kq-leverage",
              "Bottleneck": "kq-bottleneck", "Non-critical": "kq-non-critical"}

    def _qc(label, css, desc, icon):
        active = "active" if css == q_map.get(q) else ""
        mark   = f'<div class="kq-marker">{icon}</div>' if active else ""
        return f'<div class="kq {css} {active}">{mark}<div class="kq-name">{label}</div><div class="kq-desc">{desc}</div></div>'

    actions_li = "".join(f"<li>{_e(a)}</li>" for a in actions)

    body = f"""
<div class="kraljic-wrap">
  <div>
    <div style="font-size:10px;color:var(--dim);font-weight:600;text-align:center;margin-bottom:4px;">← Low Impact &nbsp;|&nbsp; High Impact →</div>
    <div style="display:flex;gap:6px;">
      <div style="writing-mode:vertical-rl;transform:rotate(180deg);font-size:10px;color:var(--dim);font-weight:600;text-align:center;flex-shrink:0;width:18px;">
        High Risk &uarr;
      </div>
      <div class="kraljic-matrix">
        {_qc("Bottleneck",   "kq-bottleneck",   "High risk · Low impact",  "⚠")}
        {_qc("Strategic",    "kq-strategic",    "High risk · High impact", "★")}
        {_qc("Non-Critical", "kq-non-critical", "Low risk · Low impact",   "○")}
        {_qc("Leverage",     "kq-leverage",     "Low risk · High impact",  "↑")}
      </div>
    </div>
    <div style="font-size:10px;color:var(--dim);font-weight:600;text-align:center;margin-top:4px;">↓ Low Risk</div>
  </div>
  <div class="kraljic-side">
    <div class="k-scores">
      <div class="k-score-box"><div class="k-score-num">{risk_score}/10</div><div class="k-score-lbl">Supply Risk</div></div>
      <div class="k-score-box"><div class="k-score-num">{impact_score}/10</div><div class="k-score-lbl">Profit Impact</div></div>
    </div>
    <div class="k-rationale">{rationale}</div>
    {'<div class="k-posture">' + posture + '</div>' if posture else ''}
    {'<ul class="k-actions">' + actions_li + '</ul>' if actions_li else ''}
  </div>
</div>"""

    return _content_slide("Strategic Positioning", f"Kraljic Matrix — {_e(q)} Category", body, category, date_str)


def _slide_pestel(data: dict, category: str, date_str: str) -> str:
    dims = [
        ("P",  "Political",     data.get("political", []),     "pc-P"),
        ("E",  "Economic",      data.get("economic", []),      "pc-E"),
        ("S",  "Social",        data.get("social", []),        "pc-S"),
        ("T",  "Technological", data.get("technological", []), "pc-T"),
        ("En", "Environmental", data.get("environmental", []), "pc-En"),
        ("L",  "Legal",         data.get("legal", []),         "pc-L"),
    ]
    cells = ""
    for letter, label, points, cls in dims:
        li = "".join(f"<li>{_e(p)}</li>" for p in points)
        cells += f"""
<div class="p-cell {cls}">
  <div class="p-letter">{letter}</div>
  <div class="p-dim">{label}</div>
  <ul class="p-points">{li}</ul>
</div>"""

    body = f'<div class="pestel-grid">{cells}</div>'
    return _content_slide("Market Environment", "PESTEL Analysis", body, category, date_str)


def _slide_swot(data: dict, category: str, date_str: str) -> str:
    def _cell(label, cls, points):
        li = "".join(f"<li>{_e(p)}</li>" for p in points)
        return f'<div class="sw-cell {cls}"><div class="sw-label">{label}</div><ul class="sw-points">{li}</ul></div>'

    body = f"""<div class="swot-grid">
  {_cell("Strengths",     "sw-strengths",     data.get("strengths", []))}
  {_cell("Weaknesses",    "sw-weaknesses",    data.get("weaknesses", []))}
  {_cell("Opportunities", "sw-opportunities", data.get("opportunities", []))}
  {_cell("Threats",       "sw-threats",       data.get("threats", []))}
</div>"""

    return _content_slide("Internal & External Analysis", "SWOT Analysis", body, category, date_str)


def _slide_porter(data: dict, category: str, date_str: str) -> str:
    def _force(key, label, grid_pos):
        f = data.get(key, {})
        rating = f.get("rating", "Medium").lower()
        facts = "".join(f"<li>{_e(x)}</li>" for x in f.get("factors", []))
        return f"""
<div class="pf" style="grid-{grid_pos};">
  <div class="pf-name">{label}</div>
  <div class="pf-badge pf-{rating}">{f.get('rating', '—')} ({f.get('score', '—')}/10)</div>
  <ul class="pf-facts">{facts}</ul>
</div>"""

    center_html = f"""
<div class="pf pf-center">
  <div class="pf-name">Competitive Rivalry</div>
  <div style="font-size:10px;color:rgba(255,255,255,0.6);margin-top:4px;">
    {data.get('competitive_rivalry', {}).get('rating', '—')} ({data.get('competitive_rivalry', {}).get('score', '—')}/10)
  </div>
</div>"""

    body = f"""
<div class="porter-grid">
  <div class="pf-empty"></div>
  {_force("supplier_power",       "Supplier Power",        "column:2;row:1")}
  <div class="pf-empty"></div>
  {_force("buyer_power",          "Buyer Power",           "column:1;row:2")}
  {center_html}
  {_force("threat_of_substitutes","Threat of Substitutes", "column:3;row:2")}
  <div class="pf-empty"></div>
  {_force("threat_of_new_entrants","New Entrants",         "column:2;row:3")}
  <div class="pf-empty"></div>
</div>
<div class="porter-summary">{_e(data.get('summary', ''))}</div>"""

    return _content_slide("Market Power", "Porter's Five Forces", body, category, date_str)


def _slide_tco(data: dict, category: str, date_str: str) -> str:
    components = data.get("components", [])
    bars = ""
    for c in components:
        pct   = c.get("percentage", 0)
        width = min(pct, 100)
        bars += f"""
<div class="tco-row">
  <div class="tco-lbl">{_e(c.get('name', ''))}</div>
  <div class="tco-outer"><div class="tco-inner" style="width:{width}%;"></div></div>
  <div class="tco-pct">{pct}%</div>
  <div class="tco-note">{_e(c.get('notes', ''))}</div>
</div>"""

    levers = data.get("reduction_levers", [])
    levers_li = "".join(f"<li>{_e(l)}</li>" for l in levers)

    body = f"""
{'<div class="tco-insight">' + _e(data.get("key_insight", "")) + '</div>' if data.get("key_insight") else ''}
<div class="tco-bars">{bars}</div>
{'<div class="tco-levers-hdr">Cost Reduction Levers</div><ul class="tco-levers-list">' + levers_li + '</ul>' if levers_li else ''}"""

    return _content_slide("True Cost of Ownership", "TCO Breakdown", body, category, date_str)


def _slide_levers(data: dict, category: str, date_str: str) -> str:
    levers = data.get("levers", [])
    rows = ""
    for lev in levers:
        pri = lev.get("priority", "Medium").lower()
        rows += f"""
<div class="lever-row">
  <div class="lever-bar {pri}"></div>
  <div style="flex:1;">
    <div class="lever-name">{_e(lev.get('lever', ''))}</div>
    <div class="lever-effort">{_e(lev.get('effort', ''))} effort</div>
  </div>
  <div style="text-align:right;flex-shrink:0;">
    <div class="lever-saving">{_e(lev.get('saving_potential', ''))}</div>
  </div>
</div>"""

    body = f"""
{'<div class="lever-approach">' + _e(data.get("recommended_approach", "")) + '</div>' if data.get("recommended_approach") else ''}
{rows}
{'<div class="lever-timing">' + _e(data.get("optimal_timing", "")) + '</div>' if data.get("optimal_timing") else ''}"""

    return _content_slide("Value Capture", "Negotiation Levers", body, category, date_str)


def _slide_recommendation(data: dict, category: str, date_str: str) -> str:
    y1 = data.get("year1_priorities", [])
    y2 = data.get("year2_priorities", [])
    y3 = data.get("year3_vision", "")
    kpis = data.get("success_metrics", [])

    y1_li = "".join(f"<li>{_e(p)}</li>" for p in y1)
    y2_li = "".join(f"<li>{_e(p)}</li>" for p in y2)
    kpi_pills = "".join(f'<div class="rec-kpi">{_e(k)}</div>' for k in kpis)

    body = f"""
<div class="rec-headline">{_e(data.get('headline', ''))}</div>
<div class="rec-posture">{_e(data.get('strategic_posture', ''))}</div>
<div class="rec-timeline">
  <div class="rec-yr rec-yr-1">
    <div class="rec-yr-lbl">Year 1 — Execute</div>
    <ul class="rec-yr-items">{y1_li}</ul>
  </div>
  <div class="rec-yr rec-yr-2">
    <div class="rec-yr-lbl">Year 2 — Build</div>
    <ul class="rec-yr-items">{y2_li}</ul>
  </div>
  <div class="rec-yr rec-yr-3">
    <div class="rec-yr-lbl">Year 3 — Vision</div>
    <div style="font-size:11px;color:#555;line-height:1.6;">{_e(y3)}</div>
  </div>
</div>
{'<div class="rec-kpi-hdr">Success Metrics</div><div class="rec-kpis">' + kpi_pills + '</div>' if kpi_pills else ''}"""

    return _content_slide("3-Year Roadmap", "Strategy Recommendation", body, category, date_str)


# ── Public entry point ────────────────────────────────────────────────────────

def generate_strategy_deck(category: str, strategy: dict, spend_data: dict) -> str:
    """
    Return a self-contained HTML string for a category strategy slide deck.
    strategy = {framework_key: {data: dict, updated_at: str}}
    """
    date_str = datetime.now(timezone.utc).strftime("%d %b %Y")

    def _data(key): return strategy.get(key, {}).get("data", {})

    slides = [_slide_cover(category, date_str)]
    slides.append(_slide_spend(spend_data, category, date_str))

    if "kraljic" in strategy:
        slides.append(_slide_kraljic(_data("kraljic"), category, date_str))
    if "pestel" in strategy:
        slides.append(_slide_pestel(_data("pestel"), category, date_str))
    if "swot" in strategy:
        slides.append(_slide_swot(_data("swot"), category, date_str))
    if "porter" in strategy:
        slides.append(_slide_porter(_data("porter"), category, date_str))
    if "tco" in strategy:
        slides.append(_slide_tco(_data("tco"), category, date_str))
    if "levers" in strategy:
        slides.append(_slide_levers(_data("levers"), category, date_str))
    if "recommendation" in strategy:
        slides.append(_slide_recommendation(_data("recommendation"), category, date_str))

    slides_html = "\n".join(slides)
    n_slides    = len(slides)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(category)} — Category Strategy · SpendLens</title>
  <style>{_DECK_CSS}</style>
</head>
<body>
{slides_html}

<nav class="nav-bar">
  <button class="nav-btn" id="prevBtn" onclick="_show(_cur-1)" disabled>&#9664;</button>
  <span class="nav-counter"><span id="curr">1</span> / <span id="total">{n_slides}</span></span>
  <button class="nav-btn" id="nextBtn" onclick="_show(_cur+1)">&#9654;</button>
</nav>

<script>
{_DECK_JS}
</script>
</body>
</html>"""
