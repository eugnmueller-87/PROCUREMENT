"""
Category Strategy UI — SpendLens

Panel component that lets category managers:
  1. Select a procurement category
  2. Generate all 7 strategy frameworks with one click (Claude Haiku)
  3. Browse each framework inline (results persist to SQLite)
  4. Download a standalone HTML slide deck with SpendLens branding

Pattern follows icarus_ui.py: one static JS pane (height=0) for all JS
functions; dynamic HTML panes updated server-side via Panel param.
"""

import io
import threading
from datetime import datetime
from html import escape

import panel as pn
import param

from modules.category_strategy import (
    PROCUREMENT_CATEGORIES,
    FRAMEWORK_LABELS,
    init_strategy_table,
    load_strategy,
    generate_all_frameworks,
    get_category_spend_data,
    save_framework,
    generate_kraljic,
    generate_pestel,
    generate_swot,
    generate_porter,
    generate_tco,
    generate_levers,
    generate_recommendation,
)
from modules.deck_generator import generate_strategy_deck

pn.extension(sizing_mode="stretch_width")

# ── Design tokens ─────────────────────────────────────────────────────────────
_NAVY   = "#1B2A4A"
_NAVY2  = "#2E5BA8"
_GREEN  = "#1D9E75"

# ── Shared CSS (injected into every HTML pane) ────────────────────────────────
_CSS = """<style>
.cs{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1A1A2E;}

/* Cards */
.cs-card{background:white;border:1px solid #e0e8f0;border-radius:12px;overflow:hidden;margin-bottom:12px;}
.cs-hdr{background:#1B2A4A;color:white;padding:13px 18px;display:flex;align-items:center;justify-content:space-between;}
.cs-hdr-title{font-size:13px;font-weight:700;letter-spacing:0.3px;}
.cs-hdr-meta{font-size:11px;color:rgba(255,255,255,0.5);}
.cs-body{padding:18px;}

/* Empty / generating */
.cs-empty{text-align:center;padding:3rem 2rem;color:#ccc;font-size:13px;}
.cs-empty-icon{font-size:32px;margin-bottom:10px;}
.cs-gen{padding:18px;}
.cs-gen-title{font-size:14px;font-weight:600;color:#1B2A4A;margin-bottom:14px;}
.cs-step{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:7px;
  margin-bottom:5px;font-size:12px;}
.cs-step.done{border-left:3px solid #1D9E75;background:#f0faf5;color:#0F6E56;}
.cs-step.active{border-left:3px solid #1B2A4A;background:#eef3ff;color:#1B2A4A;font-weight:600;}
.cs-step.pending{border-left:3px solid #e0e0e0;background:#f8f9fa;color:#bbb;}
.cs-step-icon{font-size:14px;width:20px;text-align:center;flex-shrink:0;}
.cs-hint{font-size:11px;color:#bbb;margin-top:10px;}

/* Kraljic */
.kq-wrap{display:flex;gap:18px;align-items:flex-start;}
.kq-matrix{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;
  gap:6px;width:400px;height:300px;flex-shrink:0;}
.kq{border-radius:9px;padding:14px 16px;display:flex;flex-direction:column;
  justify-content:flex-end;opacity:0.45;}
.kq.active{opacity:1;box-shadow:0 0 0 3px #1B2A4A;z-index:1;}
.kq-strategic{background:#EBF0FB;}.kq-bottleneck{background:#FFF3E0;}
.kq-leverage{background:#E1F5EE;}.kq-non-critical{background:#f8f9fa;border:1px dashed #ddd;}
.kq-name{font-size:14px;font-weight:700;color:#1B2A4A;}
.kq-desc{font-size:11px;color:#64748B;margin-top:3px;}
.kq-side{flex:1;}
.kq-scores{display:flex;gap:8px;margin-bottom:12px;}
.kq-score{flex:1;background:#f8f9fa;border-radius:7px;padding:8px;text-align:center;}
.kq-score-num{font-size:22px;font-weight:800;color:#1B2A4A;}
.kq-score-lbl{font-size:10px;color:#64748B;}
.kq-rationale{font-size:12px;color:#444;line-height:1.65;margin-bottom:10px;}
.kq-posture{font-size:12px;font-weight:600;color:#0F6E56;background:#E1F5EE;
  padding:7px 11px;border-radius:6px;margin-bottom:10px;}
.kq-actions{list-style:none;padding:0;display:flex;flex-direction:column;gap:5px;}
.kq-actions li{font-size:11px;color:#333;padding:5px 9px;background:#f8f9fa;
  border-radius:5px;display:flex;gap:7px;}
.kq-actions li::before{content:"→";color:#1B2A4A;font-weight:700;flex-shrink:0;}

/* PESTEL */
.pestel-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;}
.p-cell{border-radius:8px;padding:12px 14px;border:1px solid #e0e8f0;}
.p-letter{font-size:18px;font-weight:900;margin-bottom:2px;}
.p-dim{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;
  color:#64748B;margin-bottom:8px;}
.p-pts{list-style:none;padding:0;display:flex;flex-direction:column;gap:4px;}
.p-pts li{font-size:11px;color:#444;line-height:1.5;padding-left:10px;position:relative;}
.p-pts li::before{content:"•";position:absolute;left:0;color:#aaa;}
.pc-P{border-top:3px solid #4A90D9;}.pc-P .p-letter{color:#4A90D9;}
.pc-E{border-top:3px solid #639922;}.pc-E .p-letter{color:#639922;}
.pc-S{border-top:3px solid #D4537E;}.pc-S .p-letter{color:#D4537E;}
.pc-T{border-top:3px solid #534AB7;}.pc-T .p-letter{color:#534AB7;}
.pc-En{border-top:3px solid #1D9E75;}.pc-En .p-letter{color:#1D9E75;}
.pc-L{border-top:3px solid #BA7517;}.pc-L .p-letter{color:#BA7517;}

/* SWOT */
.swot-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.sw{border-radius:8px;padding:13px 15px;}
.sw-label{font-size:11px;font-weight:700;text-transform:uppercase;
  letter-spacing:0.5px;margin-bottom:8px;}
.sw-pts{list-style:none;padding:0;display:flex;flex-direction:column;gap:4px;}
.sw-pts li{font-size:11px;color:#333;line-height:1.5;}
.sw-S{background:#E8F5E9;border:1px solid #A5D6A7;}.sw-S .sw-label{color:#2E7D32;}
.sw-W{background:#FFEBEE;border:1px solid #FFCDD2;}.sw-W .sw-label{color:#C62828;}
.sw-O{background:#E3F2FD;border:1px solid #BBDEFB;}.sw-O .sw-label{color:#1565C0;}
.sw-T{background:#FFF8E1;border:1px solid #FFE082;}.sw-T .sw-label{color:#E65100;}

/* Porter's */
.porter-grid{display:grid;grid-template-columns:1fr 1.3fr 1fr;
  grid-template-rows:1fr 1.3fr 1fr;gap:7px;min-height:260px;}
.pf{border-radius:8px;padding:9px 11px;border:1px solid #e0e8f0;
  display:flex;flex-direction:column;justify-content:center;}
.pf-ctr{background:#1B2A4A;color:white;border:none;}
.pf-empty{opacity:0;}
.pf-name{font-size:11px;font-weight:700;color:#1B2A4A;margin-bottom:3px;}
.pf-ctr .pf-name{color:white;font-size:12px;}
.pf-badge{font-size:9px;font-weight:700;padding:2px 6px;border-radius:99px;
  margin-bottom:4px;display:inline-block;}
.pf-high{background:#FCEBEB;color:#E24B4A;}
.pf-medium{background:#FFF3E0;color:#B8860B;}
.pf-low{background:#E1F5EE;color:#0F6E56;}
.pf-facts{list-style:none;padding:0;display:flex;flex-direction:column;gap:2px;}
.pf-facts li{font-size:9px;color:#555;line-height:1.4;}
.porter-summary{font-size:12px;color:#444;line-height:1.65;padding:10px 12px;
  background:#f8f9fa;border-radius:7px;margin-top:8px;}

/* TCO */
.tco-bars{display:flex;flex-direction:column;gap:7px;margin-bottom:14px;}
.tco-row{display:flex;align-items:center;gap:9px;}
.tco-lbl{font-size:11px;color:#333;width:190px;flex-shrink:0;}
.tco-outer{flex:1;background:#f0f0f0;border-radius:3px;height:14px;overflow:hidden;}
.tco-inner{height:100%;background:#1B2A4A;border-radius:3px;}
.tco-pct{font-size:11px;font-weight:700;color:#1B2A4A;width:34px;
  text-align:right;flex-shrink:0;}
.tco-note{font-size:10px;color:#64748B;width:160px;flex-shrink:0;}
.tco-insight{background:#E1F5EE;color:#0F6E56;font-size:12px;font-weight:500;
  padding:9px 12px;border-radius:6px;margin-bottom:12px;}
.tco-lev-hdr{font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:0.5px;color:#64748B;margin:12px 0 6px;}
.tco-lev-list{list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:5px;}
.tco-lev-list li{font-size:11px;background:#f8f9fa;color:#333;
  padding:3px 9px;border-radius:99px;border:1px solid #e0e8f0;}
.tco-lev-list li::before{content:"→ ";color:#1B2A4A;font-weight:700;}

/* Levers */
.lev-approach{font-size:12px;color:#444;padding:9px 12px;background:#eef3ff;
  border-radius:6px;border-left:3px solid #2E5BA8;margin-bottom:10px;}
.lev-row{display:flex;align-items:flex-start;gap:8px;padding:9px 11px;
  border:1px solid #e0e8f0;border-radius:8px;margin-bottom:5px;}
.lev-bar{width:5px;border-radius:99px;align-self:stretch;flex-shrink:0;}
.lev-bar-High{background:#1D9E75;}.lev-bar-Medium{background:#B8860B;}.lev-bar-Low{background:#ccc;}
.lev-name{flex:1;font-size:12px;color:#333;font-weight:500;line-height:1.5;}
.lev-effort{font-size:9px;color:#64748B;background:#f8f9fa;padding:1px 6px;
  border-radius:99px;margin-top:2px;display:inline-block;}
.lev-saving{font-size:13px;font-weight:700;color:#1D9E75;white-space:nowrap;}
.lev-timing{font-size:11px;color:#64748B;font-style:italic;margin-top:8px;}

/* Recommendation */
.rec-headline{font-size:18px;font-weight:800;color:#1B2A4A;line-height:1.3;margin-bottom:10px;}
.rec-posture{font-size:12px;color:#444;line-height:1.7;padding:11px 13px;
  background:#f8f9fa;border-radius:7px;border-left:3px solid #1D9E75;margin-bottom:16px;}
.rec-timeline{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px;}
.rec-yr{border:1px solid #e0e8f0;border-radius:9px;padding:12px 14px;}
.rec-yr-lbl{font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:0.5px;padding-bottom:6px;margin-bottom:8px;}
.rec-yr-1 .rec-yr-lbl{color:#1B2A4A;border-bottom:2px solid #1B2A4A;}
.rec-yr-2 .rec-yr-lbl{color:#2E5BA8;border-bottom:2px solid #2E5BA8;}
.rec-yr-3 .rec-yr-lbl{color:#64748B;border-bottom:2px solid #ccc;}
.rec-yr-items{list-style:none;padding:0;display:flex;flex-direction:column;gap:5px;}
.rec-yr-items li{font-size:11px;color:#333;padding-left:12px;position:relative;line-height:1.5;}
.rec-yr-1 .rec-yr-items li::before{content:"→";position:absolute;left:0;color:#1B2A4A;font-weight:700;}
.rec-yr-2 .rec-yr-items li::before{content:"→";position:absolute;left:0;color:#2E5BA8;font-weight:700;}
.rec-yr-3 .rec-yr-items li::before{content:"→";position:absolute;left:0;color:#64748B;font-weight:700;}
.rec-kpi-hdr{font-size:10px;font-weight:700;text-transform:uppercase;
  letter-spacing:0.5px;color:#64748B;margin-bottom:7px;}
.rec-kpis{display:flex;flex-wrap:wrap;gap:6px;}
.rec-kpi{font-size:11px;font-weight:600;background:#E1F5EE;color:#0F6E56;
  padding:4px 12px;border-radius:99px;}
</style>"""


# ── HTML builders ─────────────────────────────────────────────────────────────

def _e(s): return escape(str(s)) if s else ""


def _fmt_ts(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y %H:%M")
    except Exception:
        return ts[:10]


def _build_empty_html(category: str) -> str:
    return f"""{_CSS}
<div class="cs">
  <div class="cs-empty">
    <div class="cs-empty-icon">📊</div>
    <div>No strategy generated yet for <b>{_e(category)}</b></div>
    <div style="margin-top:8px;font-size:12px;color:#bbb;">
      Click <b style="color:#888">Generate All Frameworks</b> to start the AI analysis
    </div>
  </div>
</div>"""


def _build_generating_html(category: str, current_fw: str, step_num: int, total: int) -> str:
    fw_order = list(FRAMEWORK_LABELS.items())
    steps_html = ""
    for i, (key, label) in enumerate(fw_order):
        if i < step_num - 1:
            cls, icon = "done",    "✓"
        elif i == step_num - 1:
            cls, icon = "active",  "⟳"
        else:
            cls, icon = "pending", "·"
        steps_html += (
            f'<div class="cs-step {cls}">'
            f'<span class="cs-step-icon">{icon}</span>{_e(label)}</div>'
        )

    return f"""{_CSS}
<div class="cs">
  <div class="cs-gen">
    <div class="cs-gen-title">Generating strategy for <b>{_e(category)}</b>…</div>
    {steps_html}
    <div class="cs-hint">Using Claude Haiku · ~25 seconds total</div>
  </div>
</div>"""


def _build_kraljic_html(data: dict, updated_at: str = None) -> str:
    q      = data.get("quadrant", "Strategic")
    risk   = data.get("supply_risk_score", 5)
    impact = data.get("spend_impact_score", 5)
    rat    = _e(data.get("rationale", ""))
    post   = _e(data.get("recommended_posture", ""))
    acts   = data.get("key_actions", [])

    q_css  = {"Strategic": "kq-strategic", "Leverage": "kq-leverage",
               "Bottleneck": "kq-bottleneck", "Non-critical": "kq-non-critical"}

    def _qd(label, css, desc, icon):
        a = "active" if css == q_css.get(q) else ""
        m = f'<span style="font-size:13px;">{icon}</span> ' if a else ""
        return (f'<div class="kq {css} {a}">'
                f'<div class="kq-name">{m}{label}</div>'
                f'<div class="kq-desc">{desc}</div></div>')

    acts_li = "".join(f"<li>{_e(a)}</li>" for a in acts)
    meta    = _fmt_ts(updated_at) if updated_at else ""

    return f"""{_CSS}
<div class="cs">
  <div class="cs-card">
    <div class="cs-hdr">
      <span class="cs-hdr-title">Kraljic Matrix &mdash; <b style="color:#7DBFEF">{_e(q)}</b></span>
      <span class="cs-hdr-meta">{meta}</span>
    </div>
    <div class="cs-body">
      <div class="kq-wrap">
        <div>
          <div style="font-size:11px;color:#64748B;font-weight:600;text-align:center;margin-bottom:5px;">
            &#x2190; Low Profit Impact &nbsp;|&nbsp; High Profit Impact &#x2192;
          </div>
          <div style="display:flex;gap:5px;">
            <div style="writing-mode:vertical-rl;transform:rotate(180deg);font-size:11px;
              color:#64748B;font-weight:600;text-align:center;flex-shrink:0;width:18px;">
              High Risk &uarr;
            </div>
            <div class="kq-matrix">
              {_qd("Bottleneck",   "kq-bottleneck",   "High risk &middot; Low impact",  "⚠")}
              {_qd("Strategic",    "kq-strategic",    "High risk &middot; High impact", "★")}
              {_qd("Non-Critical", "kq-non-critical", "Low risk &middot; Low impact",   "○")}
              {_qd("Leverage",     "kq-leverage",     "Low risk &middot; High impact",  "↑")}
            </div>
          </div>
          <div style="font-size:11px;color:#64748B;font-weight:600;text-align:center;margin-top:5px;">
            &#x2193; Low Risk
          </div>
        </div>
        <div class="kq-side">
          <div class="kq-scores">
            <div class="kq-score">
              <div class="kq-score-num">{risk}/10</div>
              <div class="kq-score-lbl">Supply Risk</div>
            </div>
            <div class="kq-score">
              <div class="kq-score-num">{impact}/10</div>
              <div class="kq-score-lbl">Profit Impact</div>
            </div>
          </div>
          <div class="kq-rationale">{rat}</div>
          {'<div class="kq-posture">' + post + '</div>' if post else ''}
          {'<ul class="kq-actions">' + acts_li + '</ul>' if acts_li else ''}
        </div>
      </div>
    </div>
  </div>
</div>"""


def _build_pestel_html(data: dict, updated_at: str = None) -> str:
    dims = [
        ("P",  "Political",     data.get("political", []),     "pc-P"),
        ("E",  "Economic",      data.get("economic", []),      "pc-E"),
        ("S",  "Social",        data.get("social", []),        "pc-S"),
        ("T",  "Technological", data.get("technological", []), "pc-T"),
        ("En", "Environmental", data.get("environmental", []), "pc-En"),
        ("L",  "Legal",         data.get("legal", []),         "pc-L"),
    ]
    cells = ""
    for letter, label, pts, cls in dims:
        li = "".join(f"<li>{_e(p)}</li>" for p in pts)
        cells += (
            f'<div class="p-cell {cls}">'
            f'<div class="p-letter">{letter}</div>'
            f'<div class="p-dim">{label}</div>'
            f'<ul class="p-pts">{li}</ul></div>'
        )
    meta = _fmt_ts(updated_at) if updated_at else ""
    return f"""{_CSS}
<div class="cs">
  <div class="cs-card">
    <div class="cs-hdr">
      <span class="cs-hdr-title">PESTEL Analysis</span>
      <span class="cs-hdr-meta">{meta}</span>
    </div>
    <div class="cs-body">
      <div class="pestel-grid">{cells}</div>
    </div>
  </div>
</div>"""


def _build_swot_html(data: dict, updated_at: str = None) -> str:
    def _cell(label, cls, pts):
        li = "".join(f"<li>{_e(p)}</li>" for p in pts)
        return f'<div class="sw {cls}"><div class="sw-label">{label}</div><ul class="sw-pts">{li}</ul></div>'

    meta = _fmt_ts(updated_at) if updated_at else ""
    return f"""{_CSS}
<div class="cs">
  <div class="cs-card">
    <div class="cs-hdr">
      <span class="cs-hdr-title">SWOT Analysis</span>
      <span class="cs-hdr-meta">{meta}</span>
    </div>
    <div class="cs-body">
      <div class="swot-grid">
        {_cell("Strengths",     "sw sw-S", data.get("strengths",     []))}
        {_cell("Weaknesses",    "sw sw-W", data.get("weaknesses",    []))}
        {_cell("Opportunities", "sw sw-O", data.get("opportunities", []))}
        {_cell("Threats",       "sw sw-T", data.get("threats",       []))}
      </div>
    </div>
  </div>
</div>"""


def _build_porter_html(data: dict, updated_at: str = None) -> str:
    def _force(key, label, grid_col, grid_row):
        f      = data.get(key, {})
        rating = f.get("rating", "Medium").lower()
        facts  = "".join(f"<li>{_e(x)}</li>" for x in f.get("factors", []))
        return (
            f'<div class="pf" style="grid-column:{grid_col};grid-row:{grid_row};">'
            f'<div class="pf-name">{label}</div>'
            f'<div class="pf-badge pf-{rating}">{f.get("rating","—")} ({f.get("score","—")}/10)</div>'
            f'<ul class="pf-facts">{facts}</ul></div>'
        )

    cr   = data.get("competitive_rivalry", {})
    meta = _fmt_ts(updated_at) if updated_at else ""
    return f"""{_CSS}
<div class="cs">
  <div class="cs-card">
    <div class="cs-hdr">
      <span class="cs-hdr-title">Porter&rsquo;s Five Forces</span>
      <span class="cs-hdr-meta">{meta}</span>
    </div>
    <div class="cs-body">
      <div class="porter-grid">
        <div class="pf-empty" style="grid-column:1;grid-row:1;"></div>
        {_force("supplier_power",        "Supplier Power",        2, 1)}
        <div class="pf-empty" style="grid-column:3;grid-row:1;"></div>
        {_force("buyer_power",           "Buyer Power",           1, 2)}
        <div class="pf pf-ctr" style="grid-column:2;grid-row:2;">
          <div class="pf-name">Competitive Rivalry</div>
          <div style="font-size:10px;color:rgba(255,255,255,0.6);margin-top:3px;">
            {_e(cr.get("rating","—"))} ({_e(str(cr.get("score","—")))}/10)
          </div>
        </div>
        {_force("threat_of_substitutes", "Threat of Substitutes", 3, 2)}
        <div class="pf-empty" style="grid-column:1;grid-row:3;"></div>
        {_force("threat_of_new_entrants","New Entrants",          2, 3)}
        <div class="pf-empty" style="grid-column:3;grid-row:3;"></div>
      </div>
      <div class="porter-summary">{_e(data.get("summary",""))}</div>
    </div>
  </div>
</div>"""


def _build_tco_html(data: dict, updated_at: str = None) -> str:
    components = data.get("components", [])
    bars = ""
    for c in components:
        pct   = c.get("percentage", 0)
        width = min(pct, 100)
        bars += (
            f'<div class="tco-row">'
            f'<div class="tco-lbl">{_e(c.get("name",""))}</div>'
            f'<div class="tco-outer"><div class="tco-inner" style="width:{width}%;"></div></div>'
            f'<div class="tco-pct">{pct}%</div>'
            f'<div class="tco-note">{_e(c.get("notes",""))}</div>'
            f'</div>'
        )
    levers = data.get("reduction_levers", [])
    lev_li = "".join(f"<li>{_e(lever)}</li>" for lever in levers)
    meta   = _fmt_ts(updated_at) if updated_at else ""
    return f"""{_CSS}
<div class="cs">
  <div class="cs-card">
    <div class="cs-hdr">
      <span class="cs-hdr-title">TCO Breakdown</span>
      <span class="cs-hdr-meta">{meta}</span>
    </div>
    <div class="cs-body">
      {'<div class="tco-insight">' + _e(data.get("key_insight","")) + '</div>' if data.get("key_insight") else ''}
      <div class="tco-bars">{bars}</div>
      {'<div class="tco-lev-hdr">Cost Reduction Levers</div><ul class="tco-lev-list">' + lev_li + '</ul>' if lev_li else ''}
    </div>
  </div>
</div>"""


def _build_levers_html(data: dict, updated_at: str = None) -> str:
    rows = ""
    for lev in data.get("levers", []):
        pri = lev.get("priority", "Medium")
        rows += (
            f'<div class="lev-row">'
            f'<div class="lev-bar lev-bar-{pri}"></div>'
            f'<div style="flex:1;">'
            f'<div class="lev-name">{_e(lev.get("lever",""))}</div>'
            f'<div class="lev-effort">{_e(lev.get("effort",""))} effort</div></div>'
            f'<div style="text-align:right;flex-shrink:0;">'
            f'<div class="lev-saving">{_e(lev.get("saving_potential",""))}</div></div>'
            f'</div>'
        )
    meta = _fmt_ts(updated_at) if updated_at else ""
    return f"""{_CSS}
<div class="cs">
  <div class="cs-card">
    <div class="cs-hdr">
      <span class="cs-hdr-title">Negotiation Levers</span>
      <span class="cs-hdr-meta">{meta}</span>
    </div>
    <div class="cs-body">
      {'<div class="lev-approach">' + _e(data.get("recommended_approach","")) + '</div>' if data.get("recommended_approach") else ''}
      {rows}
      {'<div class="lev-timing">' + _e(data.get("optimal_timing","")) + '</div>' if data.get("optimal_timing") else ''}
    </div>
  </div>
</div>"""


def _build_recommendation_html(data: dict, updated_at: str = None) -> str:
    y1    = data.get("year1_priorities", [])
    y2    = data.get("year2_priorities", [])
    y3    = data.get("year3_vision", "")
    kpis  = data.get("success_metrics", [])
    y1_li = "".join(f"<li>{_e(p)}</li>" for p in y1)
    y2_li = "".join(f"<li>{_e(p)}</li>" for p in y2)
    kpi_pills = "".join(f'<div class="rec-kpi">{_e(k)}</div>' for k in kpis)
    meta  = _fmt_ts(updated_at) if updated_at else ""
    return f"""{_CSS}
<div class="cs">
  <div class="cs-card">
    <div class="cs-hdr">
      <span class="cs-hdr-title">Strategy Recommendation</span>
      <span class="cs-hdr-meta">{meta}</span>
    </div>
    <div class="cs-body">
      <div class="rec-headline">{_e(data.get("headline",""))}</div>
      <div class="rec-posture">{_e(data.get("strategic_posture",""))}</div>
      <div class="rec-timeline">
        <div class="rec-yr rec-yr-1">
          <div class="rec-yr-lbl">Year 1 &mdash; Execute</div>
          <ul class="rec-yr-items">{y1_li}</ul>
        </div>
        <div class="rec-yr rec-yr-2">
          <div class="rec-yr-lbl">Year 2 &mdash; Build</div>
          <ul class="rec-yr-items">{y2_li}</ul>
        </div>
        <div class="rec-yr rec-yr-3">
          <div class="rec-yr-lbl">Year 3 &mdash; Vision</div>
          <div style="font-size:11px;color:#555;line-height:1.6;">{_e(y3)}</div>
        </div>
      </div>
      {'<div class="rec-kpi-hdr">Success Metrics</div><div class="rec-kpis">' + kpi_pills + '</div>' if kpi_pills else ''}
    </div>
  </div>
</div>"""


_FRAMEWORK_BUILDERS = {
    "kraljic":        _build_kraljic_html,
    "pestel":         _build_pestel_html,
    "swot":           _build_swot_html,
    "porter":         _build_porter_html,
    "tco":            _build_tco_html,
    "levers":         _build_levers_html,
    "recommendation": _build_recommendation_html,
}


# ── Panel Component ───────────────────────────────────────────────────────────

_COUNTRY_OPTIONS = {
    "All Regions":     None,
    "DE — Germany":    ["DE"],
    "EU — Europe":     ["EU", "DE", "FR", "NL", "ES", "IT", "PL", "AT", "BE"],
    "UK":              ["UK", "GB"],
    "US":              ["US"],
    "FR — France":     ["FR"],
    "Global":          ["Global"],
}


class CategoryStrategyPanel(param.Parameterized):
    client_name = param.String(default="default")

    def __init__(self, **params):
        super().__init__(**params)
        self._category       = PROCUREMENT_CATEGORIES[0]
        self._active_fw      = "kraljic"
        self._strategies     = {}
        self._loading        = False
        self._fw_buttons     = {}
        self._country_key    = "All Regions"
        self._gen_single_btn = None  # set in view()

        init_strategy_table(self.client_name)
        self._strategies = load_strategy(self.client_name, self._category)

        # Content pane (dynamic) — holds whatever framework is active
        self._content_pane = pn.pane.HTML(
            _build_empty_html(self._category),
            sizing_mode="stretch_width",
        )
        self._render_active()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render_active(self):
        fw  = self._active_fw
        rec = self._strategies.get(fw)
        if not rec:
            self._content_pane.object = _build_empty_html(self._category)
        else:
            builder = _FRAMEWORK_BUILDERS.get(fw)
            if builder:
                self._content_pane.object = builder(rec["data"], rec.get("updated_at"))

    # ── Framework selection ───────────────────────────────────────────────────

    def _select_fw(self, fw_key: str):
        self._active_fw = fw_key
        for k, btn in self._fw_buttons.items():
            btn.button_type = "primary" if k == fw_key else "light"
        if self._gen_single_btn is not None:
            label = FRAMEWORK_LABELS.get(fw_key, fw_key)
            self._gen_single_btn.name = f"↻ {label}"
        self._render_active()

    # ── Category change ───────────────────────────────────────────────────────

    def _on_category_change(self, event):
        self._category   = event.new
        self._strategies = load_strategy(self.client_name, self._category)
        self._render_active()

    # ── Generate ──────────────────────────────────────────────────────────────

    def generate_all(self):
        if self._loading:
            return
        self._loading = True

        def _progress(fw_key, step, total):
            self._content_pane.object = _build_generating_html(
                self._category, fw_key, step, total
            )

        selected_countries = _COUNTRY_OPTIONS.get(self._country_key)

        def _do():
            try:
                import icarus
                signals = icarus.get_recent_signals(limit=300)
            except Exception:
                signals = []
            try:
                self._strategies = generate_all_frameworks(
                    self.client_name,
                    self._category,
                    icarus_signals=signals,
                    progress_cb=_progress,
                    countries=selected_countries,
                )
            except Exception as e:
                print(f"[CategoryStrategyPanel] generate error: {e}")
            finally:
                self._loading = False
                self._render_active()

        threading.Thread(target=_do, daemon=True).start()

    def generate_single(self):
        """Generate only the currently active framework tab (uses signals ≤7 days)."""
        if self._loading:
            return
        fw_key = self._active_fw
        self._loading = True
        selected_countries = _COUNTRY_OPTIONS.get(self._country_key)

        _SINGLE_GENERATORS = {
            "kraljic": lambda sd, sig: generate_kraljic(self._category, sd, sig, selected_countries),
            "pestel":  lambda sd, sig: generate_pestel(self._category, sd, sig, selected_countries),
            "swot":    lambda sd, sig: generate_swot(self._category, sd, sig, selected_countries),
            "porter":  lambda sd, sig: generate_porter(self._category, sd, sig, selected_countries),
            "tco":     lambda sd, sig: generate_tco(self._category, sd, sig, selected_countries),
            "levers":  lambda sd, sig: generate_levers(self._category, sd, sig, selected_countries),
        }

        def _progress_single():
            self._content_pane.object = _build_generating_html(
                self._category, fw_key, 1, 1
            )

        def _do():
            _progress_single()
            try:
                import icarus
                signals = icarus.get_recent_signals(limit=300, days=7)
            except Exception:
                signals = []
            try:
                spend_data = get_category_spend_data(self.client_name, self._category)
                if fw_key == "recommendation":
                    data = generate_recommendation(self._category, self._strategies, spend_data)
                else:
                    fn = _SINGLE_GENERATORS.get(fw_key)
                    if fn is None:
                        return
                    data = fn(spend_data, signals)
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc).isoformat()
                save_framework(self.client_name, self._category, fw_key, data)
                self._strategies[fw_key] = {"data": data, "updated_at": now}
            except Exception as e:
                print(f"[CategoryStrategyPanel] generate_single error ({fw_key}): {e}")
            finally:
                self._loading = False
                self._render_active()

        threading.Thread(target=_do, daemon=True).start()

    # ── Deck download ─────────────────────────────────────────────────────────

    def _get_deck_bytes(self):
        spend_data = get_category_spend_data(self.client_name, self._category)
        html_str   = generate_strategy_deck(self._category, self._strategies, spend_data)
        return io.BytesIO(html_str.encode("utf-8"))

    # ── View ──────────────────────────────────────────────────────────────────

    def view(self) -> pn.Column:
        # ── Category selector ─────────────────────────────────────────────────
        _sel_ss = """
            :host{flex-shrink:0;}
            label{display:none!important;}
            .bk-input-group select{
              height:34px;border:1.5px solid #e0e0e0;border-radius:8px;
              padding:0 12px;font-size:13px;background:#fafafa;color:#1a1a2e;
              font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
              cursor:pointer;
            }
            .bk-input-group select:focus{border-color:#1B2A4A;outline:none;}
        """
        cat_select = pn.widgets.Select(
            options=PROCUREMENT_CATEGORIES,
            value=self._category,
            width=220,
            stylesheets=[_sel_ss],
        )
        cat_select.param.watch(self._on_category_change, "value")

        # ── Country / region selector ──────────────────────────────────────────
        country_select = pn.widgets.Select(
            options=list(_COUNTRY_OPTIONS.keys()),
            value=self._country_key,
            width=160,
            stylesheets=[_sel_ss],
        )

        def _on_country_change(event):
            self._country_key = event.new

        country_select.param.watch(_on_country_change, "value")

        # ── Framework tab buttons ─────────────────────────────────────────────
        _pill_ss = """
            :host{margin:0;}
            .bk-btn{
              height:28px;padding:0 13px;border-radius:99px;font-size:11px;
              font-weight:600;white-space:nowrap;
              font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
              border:1.5px solid #e0e0e0;transition:all 0.15s;
            }
        """
        _pill_active_ss = _pill_ss + """
            .bk-btn{background:#1B2A4A;border-color:#1B2A4A;color:white;}
        """
        _pill_light_ss = _pill_ss + """
            .bk-btn{background:#fafafa;color:#666;}
            .bk-btn:hover{border-color:#1B2A4A;color:#1B2A4A;background:#EFF3FB;}
        """

        self._fw_buttons = {}
        fw_pills = []
        for fw_key, fw_label in FRAMEWORK_LABELS.items():
            is_active = fw_key == self._active_fw
            btn = pn.widgets.Button(
                name=fw_label,
                button_type="primary" if is_active else "light",
                stylesheets=[_pill_active_ss if is_active else _pill_light_ss],
            )

            def _make_cb(k, active_ss, light_ss):
                def _cb(e):
                    self._select_fw(k)
                    for kk, bb in self._fw_buttons.items():
                        ss = active_ss if kk == k else light_ss
                        bb.stylesheets = [ss]
                return _cb

            btn.on_click(_make_cb(fw_key, _pill_active_ss, _pill_light_ss))
            self._fw_buttons[fw_key] = btn
            fw_pills.append(btn)

        fw_row = pn.Row(
            *fw_pills,
            align="center",
            sizing_mode="stretch_width",
            styles={
                "padding": "8px 18px",
                "background": "#fafafa",
                "border-bottom": "1px solid #f0f0f0",
                "gap": "6px",
                "flex-wrap": "wrap",
            },
        )

        # ── Generate button ───────────────────────────────────────────────────
        _btn_ss_primary = """
            .bk-btn{
              height:34px;padding:0 16px;border-radius:8px;font-size:12px;
              font-weight:700;background:#1B2A4A;border-color:#1B2A4A;color:white;
              font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
            }
            .bk-btn:hover{background:#2E5BA8;border-color:#2E5BA8;}
        """
        gen_btn = pn.widgets.Button(
            name="Generate All Frameworks",
            button_type="primary",
            stylesheets=[_btn_ss_primary],
        )
        gen_btn.on_click(lambda e: self.generate_all())

        first_label = FRAMEWORK_LABELS.get(self._active_fw, self._active_fw)
        gen_single_btn = pn.widgets.Button(
            name=f"↻ {first_label}",
            button_type="light",
            stylesheets=["""
                .bk-btn{
                  height:34px;padding:0 14px;border-radius:8px;font-size:12px;
                  font-weight:700;border:1.5px solid #1B2A4A;color:#1B2A4A;background:white;
                  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                }
                .bk-btn:hover{background:#EFF3FB;}
            """],
        )
        gen_single_btn.on_click(lambda e: self.generate_single())
        self._gen_single_btn = gen_single_btn

        freshness_note = pn.pane.HTML(
            "<span style='font-size:10px;color:#bbb;"
            "font-family:-apple-system,sans-serif;'>"
            "Signals: max 7 days"
            "</span>",
        )

        # ── Deck download ─────────────────────────────────────────────────────
        deck_btn = pn.widgets.FileDownload(
            callback=self._get_deck_bytes,
            filename="category_strategy.html",
            label="Generate Strategy Deck",
            button_type="success",
            stylesheets=["""
                .bk-btn{
                  height:34px;padding:0 16px;border-radius:8px;font-size:12px;
                  font-weight:700;background:#1D9E75;border-color:#1D9E75;color:white;
                  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                }
                .bk-btn:hover{background:#0F6E56;border-color:#0F6E56;}
            """],
        )

        hint = pn.pane.HTML(
            "<span style='font-size:11px;color:#ccc;"
            "font-family:-apple-system,sans-serif;'>"
            "HTML deck opens in browser &middot; keyboard ← → to navigate slides"
            "</span>",
            sizing_mode="stretch_width",
        )

        # ── Header row ────────────────────────────────────────────────────────
        header_row = pn.Row(
            pn.pane.HTML(
                "<span style='font-size:13px;font-weight:700;color:#1B2A4A;"
                "font-family:-apple-system,sans-serif;'>Category Strategy</span>",
                align="center",
            ),
            cat_select,
            country_select,
            pn.layout.HSpacer(),
            freshness_note,
            gen_single_btn,
            gen_btn,
            deck_btn,
            hint,
            align="center",
            sizing_mode="stretch_width",
            styles={
                "padding": "10px 18px",
                "border-bottom": "1px solid #f0f0f0",
                "background": "white",
                "gap": "10px",
            },
        )

        return pn.Column(
            header_row,
            fw_row,
            self._content_pane,
            sizing_mode="stretch_width",
            styles={
                "background": "white",
                "border": "1px solid #e8e8e8",
                "border-radius": "12px",
                "overflow": "hidden",
            },
        )


# ── Standalone ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    panel = CategoryStrategyPanel(client_name="default")
    pn.template.FastListTemplate(
        title="Category Strategy",
        main=[panel.view()],
        accent_base_color="#1D9E75",
        header_background="#1B2A4A",
    ).servable()
