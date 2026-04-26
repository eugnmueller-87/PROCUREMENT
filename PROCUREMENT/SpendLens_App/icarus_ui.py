"""
Icarus UI 🪶 — SpendLens Market Intelligence Panel
"""
import panel as pn
import param
import threading
from collections import defaultdict
from datetime import datetime, timezone

import icarus

pn.extension("floatpanel", sizing_mode="stretch_width")

# ── Colors aligned to SpendLens taxonomy ─────────────────────────────────────
CAT_COLORS = {
    "Cloud & Compute":          "#378ADD",
    "AI/ML APIs & Data":        "#D4537E",
    "IT Software & SaaS":       "#534AB7",
    "Telecom & Voice":          "#1D9E75",
    "Recruitment & HR":         "#639922",
    "Professional Services":    "#0F6E56",
    "Marketing & Campaigns":    "#7F77DD",
    "Facilities & Office":      "#993C1D",
    "Real Estate":              "#8B6914",
    "Hardware & Equipment":     "#BA7517",
    "Travel & Expenses":        "#185FA5",
}

CAT_BG = {
    "Cloud & Compute":          "#E6F1FB",
    "AI/ML APIs & Data":        "#FBEAF0",
    "IT Software & SaaS":       "#EEEDFE",
    "Telecom & Voice":          "#E1F5EE",
    "Recruitment & HR":         "#EAF3DE",
    "Professional Services":    "#E1F5EE",
    "Marketing & Campaigns":    "#EEEDFE",
    "Facilities & Office":      "#FAECE7",
    "Real Estate":              "#FDF3DD",
    "Hardware & Equipment":     "#FAEEDA",
    "Travel & Expenses":        "#E6F1FB",
}

IMPACT_COLOR = {"negative": "#E24B4A", "positive": "#639922", "neutral": "#888780"}

# RFP / negotiation trigger keywords
_RFP_KEYWORDS = ["rfp", "request for proposal", "negotiation", "verhandlung",
                  "ausschreibung", "tender", "rfp prep", "negotiation brief"]

# ── Logos ─────────────────────────────────────────────────────────────────────
LOGO_SVG_IDLE = """
<svg width="36" height="36" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
  <polygon points="50,4 93,27 93,73 50,96 7,73 7,27" fill="#EDF0F7" stroke="#1B2A5E" stroke-width="3"/>
  <line x1="50" y1="4" x2="50" y2="96" stroke="#9BAACF" stroke-width="0.8" opacity="0.5"/>
  <line x1="7" y1="27" x2="93" y2="73" stroke="#9BAACF" stroke-width="0.8" opacity="0.5"/>
  <line x1="93" y1="27" x2="7" y2="73" stroke="#9BAACF" stroke-width="0.8" opacity="0.5"/>
  <path d="M28,50 Q50,28 72,50 Q50,72 28,50 Z" fill="none" stroke="#1D9E75" stroke-width="2.5"/>
  <circle cx="50" cy="50" r="11" fill="none" stroke="#1D9E75" stroke-width="2"/>
  <circle cx="50" cy="50" r="6" fill="#1D9E75"/>
  <circle cx="53" cy="47" r="2.5" fill="#9FE1CB" opacity="0.8"/>
</svg>"""

LOGO_SVG_LOADING = """
<svg width="36" height="36" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .lid{animation:blink 1s ease-in-out infinite;transform-origin:50px 50px;}
    .pupil{animation:pulse 1s ease-in-out infinite;transform-origin:50px 50px;}
    @keyframes blink{0%,100%{transform:scaleY(1);}50%{transform:scaleY(0.05);}}
    @keyframes pulse{0%,100%{opacity:1;}50%{opacity:0;}}
  </style>
  <polygon points="50,4 93,27 93,73 50,96 7,73 7,27" fill="#EDF0F7" stroke="#1B2A5E" stroke-width="3"/>
  <g class="lid">
    <path d="M28,50 Q50,28 72,50 Q50,72 28,50 Z" fill="none" stroke="#1D9E75" stroke-width="2.5"/>
    <circle cx="50" cy="50" r="11" fill="none" stroke="#1D9E75" stroke-width="2"/>
  </g>
  <circle class="pupil" cx="50" cy="50" r="6" fill="#1D9E75"/>
</svg>"""

# ── CSS (included in every HTML pane) ────────────────────────────────────────
_CSS = """
<style>
/* Header */
.icarus-header{display:flex;align-items:center;justify-content:space-between;
  padding:14px 18px;border-bottom:1px solid #f0f0f0;}
.icarus-title{display:flex;align-items:center;gap:12px;}
.icarus-name{font-size:15px;font-weight:600;color:#111;}
.icarus-sub{font-size:11px;color:#888;margin-top:1px;}
.status-badge{font-size:11px;padding:3px 10px;border-radius:99px;font-weight:500;}
.status-done{background:#E1F5EE;color:#0F6E56;}
.status-loading{background:#FAC775;color:#633806;}

/* Category filter tabs */
.cat-tabs{display:flex;gap:6px;padding:12px 18px;border-bottom:1px solid #f0f0f0;
  overflow-x:auto;scrollbar-width:none;}
.cat-tabs::-webkit-scrollbar{display:none;}
.cat-tab{
  display:inline-flex;align-items:center;gap:5px;padding:5px 12px;
  border-radius:99px;cursor:pointer;border:1.5px solid #e0e0e0;background:#fafafa;
  white-space:nowrap;font-size:12px;font-weight:600;color:#666;
  transition:all 0.15s;flex-shrink:0;user-select:none;
}
.cat-tab:hover{border-color:#1B3A6B;color:#1B3A6B;background:#EFF3FB;}
.cat-tab.active{background:#1B3A6B;border-color:#1B3A6B;color:#fff;
  box-shadow:0 2px 8px rgba(27,58,107,0.25);}
.cat-tab.active .cat-count{background:rgba(255,255,255,0.25);color:#fff;}
.cat-dot{width:7px;height:7px;border-radius:50%;display:inline-block;flex-shrink:0;}
.cat-count{font-size:10px;min-width:17px;height:17px;border-radius:99px;
  display:inline-flex;align-items:center;justify-content:center;
  background:#e0e0e0;color:#555;font-weight:700;padding:0 4px;}

/* Category accordion sections */
.cat-section{border:1px solid #f0f0f0;border-radius:10px;overflow:hidden;margin-bottom:10px;}
.cat-section-hdr{
  display:flex;align-items:center;gap:8px;padding:11px 14px;
  background:#fafafa;cursor:pointer;user-select:none;
}
.cat-section-hdr:hover{background:#f0f0f0;}
.cat-section-label{font-size:13px;font-weight:700;flex:1;}
.cat-section-cnt{font-size:11px;padding:2px 9px;border-radius:99px;font-weight:700;}
.cat-section-date{font-size:11px;color:#aaa;margin-left:4px;}
.cat-section-chev{font-size:11px;color:#bbb;transition:transform 0.2s;margin-left:4px;}
.cat-section-body{padding:8px;display:flex;flex-direction:column;gap:6px;background:white;}
.cat-section-body.collapsed{display:none;}

/* Signal cards */
.signal-card{border:1px solid #efefef;border-radius:8px;overflow:hidden;}
.signal-card.hidden{display:none;}
.signal-header{
  display:flex;align-items:center;gap:10px;padding:9px 12px;
  background:#fafafa;cursor:pointer;user-select:none;
}
.signal-header:hover{background:#f0f0f0;}
.impact-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}
.signal-headline{font-size:13px;font-weight:500;flex:1;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.sig-meta{display:flex;align-items:center;gap:6px;flex-shrink:0;}
.sig-date{font-size:11px;color:#bbb;}
.sig-score{font-size:11px;color:#999;font-weight:600;}
.sig-chevron{font-size:10px;color:#ccc;transition:transform 0.2s;}

.signal-body{display:none;padding:12px 14px;border-top:1px solid #f0f0f0;background:white;}
.signal-body.open{display:block;}
.sig-summary{font-size:13px;color:#555;line-height:1.65;margin-bottom:8px;}
.sig-action{font-size:12px;color:#0F6E56;background:#E1F5EE;border-radius:6px;
  padding:7px 10px;display:flex;gap:6px;margin-bottom:6px;}
.sig-action-label{font-weight:700;flex-shrink:0;}
.sig-source{font-size:11px;color:#bbb;margin-top:4px;}
.sig-source a{color:#888;text-decoration:underline;}
.sig-feedback{display:flex;gap:6px;margin-top:8px;align-items:center;}
.sig-feedback-label{font-size:11px;color:#bbb;}
.fb-btn{font-size:11px;padding:2px 9px;border-radius:99px;cursor:pointer;
  border:1px solid #e0e0e0;background:white;color:#555;transition:all 0.15s;}
.fb-btn:hover{border-color:#1D9E75;color:#0F6E56;}
.fb-btn.selected-yes{background:#E1F5EE;border-color:#1D9E75;color:#0F6E56;}
.fb-btn.selected-no{background:#FCEBEB;border-color:#E24B4A;color:#E24B4A;}

/* Loading / empty */
.loading-row{display:none;align-items:center;gap:10px;padding:6px 0;
  font-size:13px;color:#888;}
.loading-row.visible{display:flex;}
.dot-pulse span{display:inline-block;width:5px;height:5px;border-radius:50%;
  background:#1D9E75;margin:0 2px;animation:dp 1.2s ease-in-out infinite;}
.dot-pulse span:nth-child(2){animation-delay:0.2s;}
.dot-pulse span:nth-child(3){animation-delay:0.4s;}
@keyframes dp{0%,100%{transform:translateY(0);opacity:0.3}50%{transform:translateY(-5px);opacity:1}}
.empty-msg{display:none;text-align:center;padding:2rem 1rem;font-size:13px;color:#bbb;}
.empty-msg.visible{display:block;}

/* Document section */
.doc-section-title{font-size:11px;font-weight:700;color:#555;text-transform:uppercase;
  letter-spacing:0.8px;margin-bottom:6px;display:flex;align-items:center;gap:6px;}
.doc-item{display:flex;align-items:center;gap:8px;padding:5px 0;
  border-bottom:1px solid #f5f5f5;}
.doc-item:last-child{border-bottom:none;}
.doc-icon{font-size:14px;flex-shrink:0;}
.doc-name{font-size:12px;color:#333;font-weight:500;flex:1;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.doc-meta{font-size:11px;color:#bbb;white-space:nowrap;flex-shrink:0;}
.doc-empty{font-size:12px;color:#bbb;font-style:italic;padding:4px 0;}

/* Query result box */
.query-result-box{background:#F0F7FF;border:1.5px solid #378ADD;border-radius:10px;
  padding:14px 16px;margin-bottom:4px;}
.query-result-q{font-size:11px;font-weight:700;color:#378ADD;text-transform:uppercase;
  letter-spacing:0.5px;margin-bottom:8px;}
.query-result-answer{font-size:13px;color:#1a1a2e;line-height:1.7;}
.query-loading-box{background:#FFF8E7;border:1.5px solid #FAC775;border-radius:10px;
  padding:14px 16px;display:flex;align-items:center;gap:10px;font-size:13px;color:#633806;}

/* Weekly brief box */
.weekly-box{background:#F8F9FA;border:1.5px solid #1B3A6B;border-radius:10px;
  padding:16px 18px;margin-bottom:4px;}
.weekly-week{font-size:11px;font-weight:700;color:#1B3A6B;text-transform:uppercase;
  letter-spacing:0.5px;margin-bottom:6px;}
.weekly-headline{font-size:14px;font-weight:600;color:#111;line-height:1.5;margin-bottom:14px;}
.weekly-section{margin-bottom:12px;}
.weekly-section-title{font-size:10px;font-weight:700;color:#999;text-transform:uppercase;
  letter-spacing:0.8px;margin-bottom:5px;}
.weekly-list{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:4px;}
.weekly-list li{font-size:12px;color:#333;display:flex;align-items:flex-start;
  gap:7px;line-height:1.5;padding:3px 0;}
.weekly-list li::before{flex-shrink:0;font-weight:900;font-size:13px;}
.weekly-risk li::before{content:"↓";color:#E24B4A;}
.weekly-opp li::before{content:"↑";color:#639922;}
.weekly-action li::before{content:"→";color:#1B3A6B;}
.weekly-cats{display:flex;flex-direction:column;gap:5px;}
.weekly-cat-row{display:flex;gap:8px;font-size:12px;color:#444;align-items:flex-start;}
.weekly-cat-tag{font-weight:700;padding:2px 8px;border-radius:99px;font-size:11px;
  white-space:nowrap;flex-shrink:0;}

/* RFP brief box */
.rfp-box{background:#FFF9F0;border:1.5px solid #BA7517;border-radius:10px;
  padding:16px 18px;margin-bottom:4px;}
.rfp-header{font-size:11px;font-weight:700;color:#BA7517;text-transform:uppercase;
  letter-spacing:0.5px;margin-bottom:6px;}
.rfp-title{font-size:14px;font-weight:600;color:#111;line-height:1.4;margin-bottom:6px;}
.rfp-summary{font-size:13px;color:#444;line-height:1.65;margin-bottom:14px;
  padding:8px 10px;background:rgba(186,117,23,0.06);border-radius:6px;}
.rfp-section{margin-bottom:12px;}
.rfp-section-title{font-size:10px;font-weight:700;color:#999;text-transform:uppercase;
  letter-spacing:0.8px;margin-bottom:5px;}
.rfp-list{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:4px;}
.rfp-list li{font-size:12px;color:#333;display:flex;align-items:flex-start;
  gap:7px;line-height:1.5;padding:4px 8px;border-radius:4px;}
.rfp-list li::before{content:"→";flex-shrink:0;font-weight:700;color:#BA7517;}
.rfp-mkt li{background:rgba(27,58,107,0.04);}
.rfp-mkt li::before{color:#1B3A6B;}
.rfp-lev li{background:rgba(99,153,34,0.05);}
.rfp-lev li::before{color:#639922;}
.rfp-risk li{background:rgba(226,75,74,0.05);}
.rfp-risk li::before{color:#E24B4A;}
.rfp-steps li{background:rgba(186,117,23,0.06);}
</style>
"""

# ── Voice button HTML ─────────────────────────────────────────────────────────
_VOICE_HTML = """
<style>
.iv-wrap{display:flex;align-items:center;height:36px;}
.iv-btn{width:36px;height:36px;border-radius:8px;border:1px solid #e0e0e0;
  background:#fafafa;cursor:pointer;display:flex;align-items:center;
  justify-content:center;transition:all 0.15s;flex-shrink:0;}
.iv-btn:hover{border-color:#1B3A6B;}.iv-btn.rec{background:#FCEBEB;border-color:#E24B4A;}
</style>
<div class="iv-wrap">
<button class="iv-btn" id="ivBtn" onclick="ivToggle()" title="Voice input (Chrome only)">
<svg width="14" height="14" viewBox="0 0 15 15" fill="none">
  <rect x="5" y="1" width="5" height="8" rx="2.5" fill="#888"/>
  <path d="M2 7.5C2 10.538 4.462 13 7.5 13S13 10.538 13 7.5"
        stroke="#888" stroke-width="1.3" stroke-linecap="round" fill="none"/>
  <line x1="7.5" y1="13" x2="7.5" y2="15" stroke="#888" stroke-width="1.3" stroke-linecap="round"/>
</svg>
</button>
</div>
<script>
var _ivRec=null,_ivOn=false;
function ivToggle(){
  var btn=document.getElementById('ivBtn');
  if(!('webkitSpeechRecognition' in window||'SpeechRecognition' in window)){
    alert('Voice input requires Chrome.');return;
  }
  if(_ivOn){if(_ivRec)_ivRec.stop();return;}
  var SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  _ivRec=new SR();_ivRec.lang='en-US';_ivRec.interimResults=false;
  _ivRec.onresult=function(e){
    var t=e.results[0][0].transcript;
    var inp=[].slice.call(document.querySelectorAll('input.bk-input'))
              .find(function(el){return el.placeholder&&el.placeholder.indexOf('Icarus')>-1;});
    if(inp){inp.focus();inp.value=t;
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new Event('change',{bubbles:true}));}
    _ivOn=false;if(btn)btn.classList.remove('rec');
  };
  _ivRec.onerror=function(){_ivOn=false;if(btn)btn.classList.remove('rec');};
  _ivRec.onend  =function(){_ivOn=false;if(btn)btn.classList.remove('rec');};
  _ivRec.start();_ivOn=true;btn.classList.add('rec');
}
</script>"""

_ENTER_KEY_HTML = """
<script>
(function waitForInput(){
  var inp=[].slice.call(document.querySelectorAll('input.bk-input'))
            .find(function(el){return el.placeholder&&el.placeholder.indexOf('Icarus')>-1;});
  if(inp){
    inp.addEventListener('keydown',function(e){
      if(e.key==='Enter'&&!e.shiftKey){
        e.preventDefault();
        var btns=[].slice.call(document.querySelectorAll('.bk-btn'));
        var ask=btns.find(function(b){return b.textContent&&b.textContent.trim()==='Ask';});
        if(ask)ask.click();
      }
    });
  }else{setTimeout(waitForInput,800);}
})();
</script>"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_date(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - dt
        secs = delta.total_seconds()
        if secs < 3600:
            return f"{int(secs/60)}m"
        if delta.days == 0:
            return f"{int(secs/3600)}h"
        if delta.days == 1:
            return "Yesterday"
        return dt.strftime("%d %b")
    except Exception:
        return ""


def _cat_id(cat: str) -> str:
    return cat.replace(" ", "_").replace("&", "and").replace("/", "_")


def _is_rfp_query(query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in _RFP_KEYWORDS)


# ── Result HTML builders ──────────────────────────────────────────────────────

def _build_query_result_html(query: str, answer: str) -> str:
    return f"""{_CSS}
<div class="query-result-box">
  <div class="query-result-q">🪶 Icarus: &ldquo;{query}&rdquo;</div>
  <div class="query-result-answer">{answer}</div>
</div>"""


def _build_query_loading_html(query: str) -> str:
    return f"""{_CSS}
<div class="query-loading-box">
  <div class="dot-pulse"><span></span><span></span><span></span></div>
  <span>Analyzing: &ldquo;{query}&rdquo;&hellip;</span>
</div>"""


def _build_weekly_summary_html(data: dict) -> str:
    week    = data.get("week", "")
    headline= data.get("headline", "")
    risks   = data.get("top_risks", [])
    opps    = data.get("top_opportunities", [])
    actions = data.get("actions", [])
    cats    = data.get("category_highlights", {})

    risks_li   = "".join(f"<li>{r}</li>" for r in risks)
    opps_li    = "".join(f"<li>{o}</li>" for o in opps)
    actions_li = "".join(f"<li>{a}</li>" for a in actions)

    cats_html = ""
    for cat, insight in cats.items():
        color = CAT_COLORS.get(cat, "#888")
        bg    = CAT_BG.get(cat, "#f0f0f0")
        cats_html += (
            f'<div class="weekly-cat-row">'
            f'<span class="weekly-cat-tag" style="background:{bg};color:{color}">{cat}</span>'
            f'<span>{insight}</span></div>'
        )

    return f"""{_CSS}
<div class="weekly-box">
  <div class="weekly-week">📋 Weekly Intelligence Brief &middot; {week}</div>
  <div class="weekly-headline">{headline}</div>
  {'<div class="weekly-section"><div class="weekly-section-title">Top Risks</div><ul class="weekly-list weekly-risk">' + risks_li + '</ul></div>' if risks else ''}
  {'<div class="weekly-section"><div class="weekly-section-title">Opportunities</div><ul class="weekly-list weekly-opp">' + opps_li + '</ul></div>' if opps else ''}
  {'<div class="weekly-section"><div class="weekly-section-title">Priority Actions</div><ul class="weekly-list weekly-action">' + actions_li + '</ul></div>' if actions else ''}
  {'<div class="weekly-section"><div class="weekly-section-title">Category Highlights</div><div class="weekly-cats">' + cats_html + '</div></div>' if cats_html else ''}
</div>"""


def _build_rfp_html(data: dict, query: str) -> str:
    title    = data.get("title", "RFP / Negotiation Brief")
    summary  = data.get("executive_summary", "")
    mkt      = data.get("market_context", [])
    levers   = data.get("negotiation_levers", [])
    reqs     = data.get("key_requirements", [])
    risks    = data.get("risk_areas", [])
    terms    = data.get("suggested_terms", [])
    steps    = data.get("next_steps", [])

    def _ul(items, extra_cls=""):
        return "".join(f"<li>{i}</li>" for i in items) if items else ""

    def _section(label, items, extra_cls=""):
        if not items:
            return ""
        return (f'<div class="rfp-section">'
                f'<div class="rfp-section-title">{label}</div>'
                f'<ul class="rfp-list {extra_cls}">{_ul(items)}</ul>'
                f'</div>')

    return f"""{_CSS}
<div class="rfp-box">
  <div class="rfp-header">📄 RFP / Negotiation Preparation &middot; &ldquo;{query}&rdquo;</div>
  <div class="rfp-title">{title}</div>
  {'<div class="rfp-summary">' + summary + '</div>' if summary else ''}
  {_section("Market Context", mkt, "rfp-mkt")}
  {_section("Negotiation Levers", levers, "rfp-lev")}
  {_section("Key Requirements", reqs, "")}
  {_section("Risk Areas", risks, "rfp-risk")}
  {_section("Suggested Contract Terms", terms, "")}
  {_section("Next Steps", steps, "rfp-steps")}
</div>"""


def _build_rfp_loading_html(query: str) -> str:
    return f"""{_CSS}
<div class="query-loading-box" style="border-color:#BA7517;background:#FFF9F0;color:#7A4A00;">
  <div class="dot-pulse"><span></span><span></span><span></span></div>
  <span>Preparing RFP brief: &ldquo;{query}&rdquo;&hellip;</span>
</div>"""


def _build_weekly_loading_html() -> str:
    return f"""{_CSS}
<div class="query-loading-box" style="border-color:#1B3A6B;background:#F0F4FF;color:#1B3A6B;">
  <div class="dot-pulse"><span></span><span></span><span></span></div>
  <span>Generating weekly intelligence brief&hellip;</span>
</div>"""


# ── Card / section HTML builders ──────────────────────────────────────────────

def build_cat_tabs(signals, active_cat="all"):
    from collections import Counter
    counts = Counter(s.get("category", "") for s in signals)
    total  = len(signals)

    active = "active" if active_cat == "all" else ""
    html = (
        f'<div class="cat-tabs" id="catTabs">'
        f'<div class="cat-tab {active}" onclick="filterCat(this,\'all\')">'
        f'All <span class="cat-count">{total}</span></div>'
    )
    for cat, color in CAT_COLORS.items():
        cnt = counts.get(cat, 0)
        act = "active" if active_cat == cat else ""
        short = cat.split(" & ")[0]
        html += (
            f'<div class="cat-tab {act}" onclick="filterCat(this,\'{cat}\')" data-cat="{cat}">'
            f'<span class="cat-dot" style="background:{color}"></span>'
            f'{short} <span class="cat-count">{cnt}</span>'
            f'</div>'
        )
    return html + "</div>"


def build_signal_card(s, idx):
    cat       = s.get("category", "")
    impact    = s.get("impact", "neutral")
    dot_color = IMPACT_COLOR.get(impact, "#888")
    score     = s.get("relevance", 0)
    headline  = s.get("headline", "")
    summary   = s.get("summary", "")
    action    = s.get("action", "")
    source    = s.get("source", "")
    url       = s.get("url") or "#"
    sig_id    = s.get("id", idx)
    date_str  = _fmt_date(s.get("published") or s.get("timestamp", ""))

    return f"""
<div class="signal-card" data-cat="{cat}" id="card-{idx}">
  <div class="signal-header" onclick="toggleCard({idx})">
    <div class="impact-dot" style="background:{dot_color}"></div>
    <a class="signal-headline" href="{url}" target="_blank"
       onclick="event.stopPropagation()" title="Open article"
       style="color:#111;text-decoration:none;">{headline}</a>
    <div class="sig-meta">
      <span class="sig-date">{date_str}</span>
      <span class="sig-score">{score}/10</span>
      <span class="sig-chevron" id="chev-{idx}">▼</span>
    </div>
  </div>
  <div class="signal-body" id="body-{idx}">
    <div class="sig-summary">{summary}</div>
    <div class="sig-action"><span class="sig-action-label">Action:</span> {action}</div>
    <div class="sig-source"><a href="{url}" target="_blank">{source}</a></div>
    <div class="sig-feedback">
      <span class="sig-feedback-label">Relevant?</span>
      <button class="fb-btn" id="fb-yes-{idx}" onclick="icarusFeedback({sig_id},{idx},'relevant')">Yes</button>
      <button class="fb-btn" id="fb-no-{idx}"  onclick="icarusFeedback({sig_id},{idx},'not_relevant')">No</button>
    </div>
  </div>
</div>"""


def _build_header_html(signals=None, loading=False, status_text=None):
    if signals is None:
        signals = []
    logo         = LOGO_SVG_LOADING if loading else LOGO_SVG_IDLE
    status_class = "status-loading" if loading else "status-done"
    if status_text is None:
        status_text = "scanning…" if loading else f"{len(signals)} signals"
    return f"""{_CSS}
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div class="icarus-header">
    <div class="icarus-title">
      {logo}
      <div><div class="icarus-name">Icarus</div><div class="icarus-sub">market intelligence</div></div>
    </div>
    <span class="status-badge {status_class}">{status_text}</span>
  </div>
  {build_cat_tabs(signals)}
</div>"""


def _build_cards_html(signals=None, loading=False):
    if signals is None:
        signals = []

    loading_cls = "visible" if loading else ""

    by_cat = defaultdict(list)
    for s in signals:
        by_cat[s.get("category", "Other")].append(s)

    global_idx = 0
    sections_html = ""

    for cat, color in CAT_COLORS.items():
        cat_signals = by_cat.get(cat, [])
        if not cat_signals:
            continue

        bg   = CAT_BG.get(cat, "#f0f0f0")
        cnt  = len(cat_signals)
        cid  = _cat_id(cat)

        dates = [s.get("published") or s.get("timestamp", "") for s in cat_signals]
        latest_date = _fmt_date(max((d for d in dates if d), default=""))

        cards = ""
        for s in cat_signals:
            cards += build_signal_card(s, global_idx)
            global_idx += 1

        sections_html += f"""
<div class="cat-section" data-cat="{cat}" id="catsec-{cid}">
  <div class="cat-section-hdr" onclick="toggleSection('{cid}')">
    <span class="cat-dot" style="background:{color}"></span>
    <span class="cat-section-label" style="color:{color}">{cat}</span>
    <span class="cat-section-cnt" style="background:{bg};color:{color}">{cnt}</span>
    {f'<span class="cat-section-date">{latest_date}</span>' if latest_date else ''}
    <span class="cat-section-chev" id="sechev-{cid}">▼</span>
  </div>
  <div class="cat-section-body" id="secbody-{cid}">
    {cards}
  </div>
</div>"""

    if not sections_html:
        sections_html = '<div class="empty-msg visible">Click &ldquo;Scan Feeds&rdquo; to load signals.</div>'

    return f"""{_CSS}
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
            padding:14px 18px;display:flex;flex-direction:column;gap:4px;">
  <div class="loading-row {loading_cls}" id="loadingRow">
    <div class="dot-pulse"><span></span><span></span><span></span></div>
    <span>Scanning feeds&hellip;</span>
  </div>
  <div id="signalSections">{sections_html}</div>
  <div class="empty-msg" id="emptyMsg"></div>
</div>

<script>
function toggleCard(idx){{
  var body=document.getElementById('body-'+idx);
  var chev=document.getElementById('chev-'+idx);
  if(!body)return;
  var open=body.classList.toggle('open');
  if(chev)chev.style.transform=open?'rotate(180deg)':'';
}}

function toggleSection(cid){{
  var body=document.getElementById('secbody-'+cid);
  var chev=document.getElementById('sechev-'+cid);
  if(!body)return;
  var collapsed=body.classList.toggle('collapsed');
  if(chev)chev.style.transform=collapsed?'rotate(-90deg)':'';
}}

function filterCat(tab,cat){{
  document.querySelectorAll('.cat-tab').forEach(function(t){{t.classList.remove('active');}});
  tab.classList.add('active');
  document.querySelectorAll('.cat-section').forEach(function(sec){{
    var match=(cat==='all'||sec.dataset.cat===cat);
    sec.style.display=match?'block':'none';
  }});
  var em=document.getElementById('emptyMsg');
  if(em){{
    var vis=[].slice.call(document.querySelectorAll('.cat-section'))
              .filter(function(s){{return s.style.display!=='none';}}).length;
    em.textContent=vis===0&&cat!=='all'?'No signals for this category.':'';
    em.classList.toggle('visible',vis===0&&cat!=='all');
  }}
}}

function icarusFeedback(sigId,idx,value){{
  var y=document.getElementById('fb-yes-'+idx);
  var n=document.getElementById('fb-no-'+idx);
  if(y)y.classList.toggle('selected-yes',value==='relevant');
  if(n)n.classList.toggle('selected-no',value==='not_relevant');
}}
</script>"""


# ── Panel Component ───────────────────────────────────────────────────────────

class IcarusPanel(param.Parameterized):
    client_categories = param.List(default=list(CAT_COLORS.keys()))
    client_name       = param.String(default="Client")

    def __init__(self, **params):
        super().__init__(**params)
        self._signals      = []
        self._loading      = False
        self._last_query   = ""
        self._header_pane  = pn.pane.HTML(_build_header_html(),  sizing_mode="stretch_width")
        self._cards_pane   = pn.pane.HTML(_build_cards_html(),   sizing_mode="stretch_width")
        self._result_pane  = pn.pane.HTML("", sizing_mode="stretch_width", visible=False)
        # Document store UI
        self._doc_list   = pn.Column(sizing_mode="stretch_width")
        self._doc_status = pn.pane.HTML("", sizing_mode="stretch_width", visible=False)
        # FileInput styled as a compact paperclip icon in the input row
        self._file_input = pn.widgets.FileInput(
            accept=".pdf,.docx,.txt,.csv,.xlsx",
            multiple=True,
            name="",
            width=36,
            stylesheets=["""
                :host{width:36px!important;flex-shrink:0;}
                .bk-input-group{
                    position:relative;width:36px;height:36px;overflow:hidden;
                    border-radius:8px;border:1px solid #e0e0e0;background:#fafafa;
                    display:flex;align-items:center;justify-content:center;
                    transition:border-color 0.15s;
                }
                .bk-input-group:hover{border-color:#534AB7;}
                .bk-input-group::before{
                    content:"📎";font-size:15px;position:absolute;pointer-events:none;
                }
                input[type="file"]{
                    position:absolute;opacity:0;width:100%;height:100%;
                    cursor:pointer;z-index:1;
                }
                .bk-input-container{display:none!important;}
            """],
        )
        # Auto-upload when files are selected — no separate Upload button needed
        self._file_input.param.watch(self._on_file_selected, 'value')
        self._refresh_doc_list()

    def _set_loading(self, loading: bool):
        self._loading = loading
        self._header_pane.object = _build_header_html(self._signals, loading)
        self._cards_pane.object  = _build_cards_html(self._signals, loading)

    def scan(self):
        """Trigger full RSS crawl — no query context."""
        if self._loading:
            return
        self._last_query   = ""
        self._result_pane.visible = False

        def _do():
            self._set_loading(True)
            try:
                result = icarus.run(
                    client_categories=self.client_categories,
                    client_name=self.client_name,
                )
                self._signals = result.get("signals", [])
                recent = icarus.get_recent_signals(limit=50)
                id_map = {s["headline"]: s["id"] for s in recent}
                for s in self._signals:
                    s["id"] = id_map.get(s.get("headline", ""), 0)
            except Exception as e:
                print(f"[IcarusPanel] scan error: {e}")
            finally:
                self._set_loading(False)

        threading.Thread(target=_do, daemon=True).start()

    def run(self, query: str = ""):
        """Dispatch: full scan if empty, RFP brief if RFP intent, else targeted query."""
        if not query.strip():
            self.scan()
            return
        if self._loading:
            return
        self._last_query = query.strip()

        if _is_rfp_query(self._last_query):
            self._run_rfp(self._last_query)
        else:
            self._run_query(self._last_query)

    def _run_query(self, query: str):
        doc_ctx = self._get_doc_context()

        def _do():
            self._set_loading(True)
            self._result_pane.object  = _build_query_loading_html(query)
            self._result_pane.visible = True
            try:
                result = icarus.query_with_claude(
                    query=query,
                    client_categories=self.client_categories,
                    client_name=self.client_name,
                    doc_context=doc_ctx or None,
                )
                self._result_pane.object = _build_query_result_html(
                    query, result.get("answer", "No response received.")
                )
                if result.get("signals"):
                    self._signals = result["signals"]
                    self._header_pane.object = _build_header_html(self._signals, loading=False)
                    self._cards_pane.object  = _build_cards_html(self._signals, loading=False)
            except Exception as e:
                print(f"[IcarusPanel] query error: {e}")
                self._result_pane.object = _build_query_result_html(
                    query, "Error – please try again."
                )
            finally:
                self._loading = False
                self._header_pane.object = _build_header_html(self._signals, loading=False)

        threading.Thread(target=_do, daemon=True).start()

    def _run_rfp(self, query: str):
        doc_ctx = self._get_doc_context()

        def _do():
            self._set_loading(True)
            self._result_pane.object  = _build_rfp_loading_html(query)
            self._result_pane.visible = True
            try:
                data = icarus.generate_rfp_brief(
                    query=query,
                    client_categories=self.client_categories,
                    client_name=self.client_name,
                    doc_context=doc_ctx or None,
                )
                self._result_pane.object = _build_rfp_html(data, query)
            except Exception as e:
                print(f"[IcarusPanel] rfp error: {e}")
                self._result_pane.object = _build_query_result_html(
                    query, "RFP generation failed – please try again."
                )
            finally:
                self._loading = False
                self._header_pane.object = _build_header_html(self._signals, loading=False)
                self._cards_pane.object  = _build_cards_html(self._signals, loading=False)

        threading.Thread(target=_do, daemon=True).start()

    def run_weekly_summary(self):
        """Generate and display a weekly intelligence brief."""
        if self._loading:
            return

        def _do():
            self._loading = True
            self._result_pane.object  = _build_weekly_loading_html()
            self._result_pane.visible = True
            try:
                data = icarus.weekly_summary(
                    client_categories=self.client_categories,
                    client_name=self.client_name,
                )
                self._result_pane.object = _build_weekly_summary_html(data)
            except Exception as e:
                print(f"[IcarusPanel] weekly_summary error: {e}")
                self._result_pane.object = _build_query_result_html(
                    "Weekly Brief", "Generation failed – please try again."
                )
            finally:
                self._loading = False

        threading.Thread(target=_do, daemon=True).start()

    # ── Document helpers ──────────────────────────────────────────────────────

    def _refresh_doc_list(self):
        """Rebuild the document list Panel column from the DB."""
        docs = icarus.get_documents(limit=20)
        self._doc_list.clear()
        if not docs:
            self._doc_list.append(
                pn.pane.HTML(f'{_CSS}<div class="doc-empty">No documents uploaded yet.</div>',
                             sizing_mode="stretch_width")
            )
            return
        for doc in docs:
            ext  = (doc.get("content_type") or "file").upper()
            icon = {"PDF": "📄", "DOCX": "📝", "TXT": "📃",
                    "CSV": "📊", "XLSX": "📊"}.get(ext, "📎")
            kc   = f"{doc['char_count']:,}" if doc.get("char_count") else "?"
            date = _fmt_date(doc.get("uploaded_at", ""))
            del_btn = pn.widgets.Button(
                name="×", width=28, height=28,
                button_type="light",
                stylesheets=[".bk-btn{padding:0;font-size:14px;color:#aaa;"
                              "border:none;background:none;cursor:pointer;}"
                              ".bk-btn:hover{color:#E24B4A;}"],
            )
            del_btn.on_click(lambda e, did=doc["id"], fn=doc["filename"]:
                             self._delete_doc(did, fn))
            self._doc_list.append(pn.Row(
                pn.pane.HTML(
                    f'{_CSS}<div class="doc-item">'
                    f'<span class="doc-icon">{icon}</span>'
                    f'<span class="doc-name" title="{doc["filename"]}">{doc["filename"]}</span>'
                    f'<span class="doc-meta">{kc} chars &middot; {date}</span>'
                    f'</div>',
                    sizing_mode="stretch_width",
                ),
                del_btn,
                align="center", sizing_mode="stretch_width",
            ))

    def _upload_docs(self):
        """Handle FileInput upload — extract text and save to DB."""
        if not self._file_input.value:
            return
        values    = self._file_input.value
        filenames = self._file_input.filename
        # Normalise to lists (FileInput gives single value when multiple=False)
        if not isinstance(values, list):
            values, filenames = [values], [filenames]

        uploaded, errors = [], []
        for content, filename in zip(values, filenames):
            try:
                text = icarus.extract_text(filename, content)
                ext  = filename.lower().rsplit(".", 1)[-1] if "." in filename else "txt"
                icarus.save_document(filename, text, ext)
                uploaded.append(filename)
            except Exception as e:
                errors.append(f"{filename}: {e}")
                print(f"[IcarusPanel] upload error: {e}")

        self._refresh_doc_list()
        if uploaded:
            self._doc_status.object = (
                f'{_CSS}<div style="font-size:11px;color:#0F6E56;padding:4px 0;">'
                f'✓ Uploaded: {", ".join(uploaded)}</div>'
            )
        if errors:
            self._doc_status.object += (
                f'<div style="font-size:11px;color:#E24B4A;padding:2px 0;">'
                f'⚠ Errors: {"; ".join(errors)}</div>'
            )
        self._doc_status.visible = True
        # Clear the input for next upload
        self._file_input.value    = None
        self._file_input.filename = None

    def _on_file_selected(self, event):
        """Triggered automatically when FileInput value changes."""
        if event.new is not None:
            self._upload_docs()

    def _delete_doc(self, doc_id: int, filename: str):
        """Delete a document from the store and refresh the list."""
        icarus.delete_document(doc_id)
        self._doc_status.object  = (
            f'{_CSS}<div style="font-size:11px;color:#888;padding:4px 0;">'
            f'Removed: {filename}</div>'
        )
        self._doc_status.visible = True
        self._refresh_doc_list()

    def _get_doc_context(self) -> list:
        """Return document excerpts for use in Claude prompts (empty list if none)."""
        return icarus.get_document_texts(limit=5, chars_per_doc=4000)

    def load_recent(self):
        self._signals = icarus.get_recent_signals(limit=50)
        self._header_pane.object = _build_header_html(self._signals, loading=False)
        self._cards_pane.object  = _build_cards_html(self._signals, loading=False)

    def view(self):
        # ── Query input row ───────────────────────────────────────────────────
        query_input = pn.widgets.TextInput(
            placeholder="Ask Icarus… e.g. cloud cost risks, RFP negotiation for AWS",
            name="",
            sizing_mode="stretch_width",
            stylesheets=["""
                :host{flex:1;margin:0;}
                label{display:none!important;}
                .bk-input{height:36px;border:1.5px solid #e0e0e0;border-radius:8px;
                           padding:0 12px;font-size:13px;background:#fafafa;color:#111;
                           font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}
                .bk-input:focus{border-color:#1B3A6B;background:white;outline:none;}
                .bk-FormGroup{margin:0;}
            """],
        )
        voice_pane = pn.pane.HTML(_VOICE_HTML, width=44, height=44)

        ask_btn = pn.widgets.Button(
            name="Ask",
            button_type="primary",
            stylesheets=["""
                .bk-btn{height:36px;padding:0 18px;border-radius:8px;
                  font-size:13px;font-weight:700;white-space:nowrap;
                  background:#1B3A6B;border-color:#1B3A6B;
                  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}
                .bk-btn:hover{background:#2E5BA8;border-color:#2E5BA8;}
            """],
        )
        ask_btn.on_click(lambda e: self.run(query=query_input.value))

        # Input row: text field · paperclip upload · mic · Ask
        input_row = pn.Row(
            query_input, self._file_input, voice_pane, ask_btn,
            align="center", sizing_mode="stretch_width",
            styles={"padding": "10px 18px", "border-bottom": "1px solid #f0f0f0",
                    "background": "white", "gap": "8px"},
        )

        # ── Compact quick-action pills ─────────────────────────────────────────
        scan_pill = pn.widgets.Button(
            name="🔍 Scan",
            button_type="light",
            stylesheets=["""
                .bk-btn{height:24px;padding:0 10px;border-radius:99px;font-size:11px;
                  font-weight:600;white-space:nowrap;border:1px solid #d0d8e8;
                  color:#1B3A6B;background:white;
                  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}
                .bk-btn:hover{background:#EFF3FB;border-color:#1B3A6B;}
            """],
        )
        scan_pill.on_click(lambda e: self.scan())

        weekly_pill = pn.widgets.Button(
            name="📋 Weekly Brief",
            button_type="light",
            stylesheets=["""
                .bk-btn{height:24px;padding:0 10px;border-radius:99px;font-size:11px;
                  font-weight:600;white-space:nowrap;border:1px solid #e8d8b0;
                  color:#7A4A00;background:white;
                  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}
                .bk-btn:hover{background:#FFF3E0;border-color:#BA7517;}
            """],
        )
        weekly_pill.on_click(lambda e: self.run_weekly_summary())

        hint_text = pn.pane.HTML(
            "<span style='font-size:11px;color:#ccc;"
            "font-family:-apple-system,sans-serif;'>"
            "Type <b style='color:#888'>RFP</b> or <b style='color:#888'>negotiation</b> to generate a brief"
            "</span>",
            sizing_mode="stretch_width",
        )

        action_row = pn.Row(
            scan_pill, weekly_pill, hint_text,
            align="center", sizing_mode="stretch_width",
            styles={"padding": "6px 18px", "background": "#fafafa",
                    "border-bottom": "1px solid #f0f0f0", "gap": "8px"},
        )

        # ── Document section (list + status only — upload via 📎 icon in input row)
        doc_section = pn.Column(
            pn.pane.HTML(
                f'{_CSS}<div class="doc-section-title">📎 Documents'
                '<span style="font-size:10px;font-weight:400;color:#aaa;margin-left:6px;">'
                'Click 📎 above to upload contracts, pricing sheets or agreements'
                '</span></div>',
                sizing_mode="stretch_width",
            ),
            self._doc_status,
            self._doc_list,
            sizing_mode="stretch_width",
            styles={"padding": "8px 18px 12px", "background": "#fafcff",
                    "border-bottom": "1px solid #f0f0f0"},
        )

        enter_key = pn.pane.HTML(_ENTER_KEY_HTML, height=0, margin=0)

        return pn.Column(
            self._header_pane,
            input_row,
            action_row,
            doc_section,
            enter_key,
            self._result_pane,
            self._cards_pane,
            sizing_mode="stretch_width",
            styles={"background": "white", "border": "1px solid #e8e8e8",
                    "border-radius": "12px", "overflow": "hidden"},
        )


# ── Standalone ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    panel = IcarusPanel(client_name="Demo")
    panel.load_recent()
    pn.template.FastListTemplate(
        title="Icarus", main=[panel.view()],
        accent_base_color="#1D9E75", header_background="#1B2A5E",
    ).servable()
