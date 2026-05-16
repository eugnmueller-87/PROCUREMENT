"""
Hades Supplier Due Diligence UI
Two modes:
  - Compliance Check: run a standalone DD report without touching the DB
  - Onboard Supplier: run DD + add vendor to SpendLens DB on Approve/Conditional
"""

import os
import json
import threading
import requests
import panel as pn
import param
from datetime import datetime

# ── Theme ─────────────────────────────────────────────────────────────────────
BG      = "#0F172A"       # near-black background for premium feel
NAVY    = "#1E3A5F"
NAVY2   = "#2563EB"
CARD    = "#1E293B"       # dark card
CARD2   = "#F8FAFC"       # light card (for detail panels)
BORDER  = "#334155"
BORDER2 = "#E2E8F0"
TEXT    = "#F1F5F9"       # light text on dark cards
TEXT2   = "#1A202C"       # dark text on light cards
DIM     = "#94A3B8"
GREEN   = "#22C55E"
YELLOW  = "#F59E0B"
ORANGE  = "#F97316"
RED     = "#EF4444"
ACCENT  = "#3B82F6"

RISK_COLOR = {"Low": GREEN, "Medium": YELLOW, "High": ORANGE, "Critical": RED}
REC_COLOR  = {"Approve": GREEN, "Conditional Approval": YELLOW, "Block": RED}
REC_ICON   = {"Approve": "✅", "Conditional Approval": "⚠️", "Block": "🚫"}

# What each score band means for business
RISK_LEGEND = [
    (1, 3,  GREEN,  "Approve",             "Low risk — proceed with standard contract terms"),
    (4, 6,  YELLOW, "Conditional Approval", "Medium risk — additional due diligence required"),
    (7, 8,  ORANGE, "Caution",             "High risk — senior approval + remediation plan"),
    (9, 10, RED,    "Block",               "Critical — do not engage without compliance sign-off"),
]

HADES_URL = os.environ.get("HADES_URL", "")

SPENDLENS_CATEGORIES = [
    "Cloud & Compute", "AI/ML APIs & Data", "IT Software & SaaS",
    "Telecom & Voice", "Recruitment & HR", "Professional Services",
    "Marketing & Campaigns", "Facilities & Office", "Real Estate",
    "Hardware & Equipment", "Travel & Expenses",
]

PIPELINE_STEPS = [
    ("hermes_preflight",        "Hermes pre-flight check"),
    ("web_research",            "Web research & background"),
    ("news_sentiment_analysis", "News sentiment (90 days)"),
    ("sanctions_verification",  "Sanctions & watchlists (OFAC / UN SC)"),
    ("registry_lookups",        "Company registry lookup"),
    ("lksg_compliance_signals", "LkSG / CSDDD compliance signals"),
    ("esg_compliance_signals",  "ESG & labour signals"),
    ("synthesis",               "Risk synthesis (Claude)"),
    ("report_generation",       "Report generation (Claude)"),
    ("hermes_registration",     "Hermes watchlist registration"),
]

STEP_KEYS = [s[0] for s in PIPELINE_STEPS]

# Map API response keys → drill-down content extractors
DIM_DETAIL_KEYS = {
    "Sanctions":        ["sanctions_status", "sanctions_findings"],
    "LkSG / CSDDD":    ["lksg_csddd_assessment", "lksg_findings"],
    "Company Registry": ["registry_data", "registry_findings"],
    "News Sentiment":   ["news_analysis", "news_findings"],
    "ESG & Labour":     ["esg_assessment", "esg_findings"],
    "Hermes Intel":     ["hermes_data", "hermes_findings"],
}


def _hades_available() -> bool:
    if not HADES_URL:
        return False
    try:
        r = requests.get(f"{HADES_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _score_color(score: float) -> str:
    if score <= 3.9:
        return GREEN
    if score <= 6.4:
        return YELLOW
    if score <= 7.9:
        return ORANGE
    return RED


def _score_bar_dark(score: float, width: int = 200) -> str:
    """Progress bar styled for dark card backgrounds."""
    pct   = int(score * 10)
    color = _score_color(score)
    track = "#2D3748"
    return (
        f"<div style='display:flex;align-items:center;gap:10px'>"
        f"<div style='width:{width}px;height:10px;background:{track};border-radius:5px;"
        f"overflow:hidden;flex-shrink:0'>"
        f"<div style='width:{pct}%;height:100%;background:{color};"
        f"border-radius:5px;transition:width 0.6s ease'></div></div>"
        f"<span style='font-size:14px;color:{color};font-weight:700;min-width:28px'>{score:.1f}</span>"
        f"</div>"
    )


def _risk_legend_html() -> str:
    """Horizontal 1–10 scale with labelled zones — explains what scores mean."""
    segments = ""
    for lo, hi, color, label, desc in RISK_LEGEND:
        width_pct = int((hi - lo + 1) * 10)
        segments += (
            f"<div style='flex:{hi - lo + 1};padding:0 4px'>"
            f"<div style='height:8px;background:{color};border-radius:3px'></div>"
            f"<div style='font-size:10px;color:{color};font-weight:700;margin-top:3px'>{lo}–{hi}</div>"
            f"<div style='font-size:10px;color:{DIM};line-height:1.3'>{label}</div>"
            f"</div>"
        )
    return (
        f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:10px;"
        f"padding:14px 18px;margin-bottom:16px'>"
        f"<div style='font-size:11px;font-weight:700;color:{DIM};text-transform:uppercase;"
        f"letter-spacing:1px;margin-bottom:10px'>Risk Scale — What the score means for us</div>"
        f"<div style='display:flex;gap:2px;align-items:flex-start'>{segments}</div>"
        f"<div style='margin-top:10px;display:flex;flex-wrap:wrap;gap:12px'>"
        + "".join(
            f"<span style='font-size:11px;color:{DIM}'>"
            f"<span style='color:{color};font-weight:700'>{lo}–{hi}:</span> {desc}</span>"
            for lo, hi, color, label, desc in RISK_LEGEND
        )
        + f"</div></div>"
    )


def _step_row(label: str, state: str) -> str:
    """state: pending | running | pass | fail"""
    icons  = {"pending": "○", "running": "◎", "pass": "✓", "fail": "✗"}
    colors = {"pending": "#475569", "running": ACCENT, "pass": GREEN, "fail": RED}
    icon   = icons.get(state, "○")
    color  = colors.get(state, "#475569")
    spin   = " class='spinning'" if state == "running" else ""
    label_color = TEXT if state != "pending" else "#475569"
    return (
        f"<div style='display:flex;align-items:center;gap:10px;padding:7px 0;"
        f"border-bottom:1px solid {BORDER}'>"
        f"<span{spin} style='font-size:15px;color:{color};width:20px;"
        f"text-align:center;flex-shrink:0'>{icon}</span>"
        f"<span style='font-size:12px;color:{label_color}'>{label}</span>"
        f"</div>"
    )


def _extract_detail(data: dict, dim_name: str) -> str:
    """Pull raw evidence text from the Hades API response for a given dimension."""
    keys = DIM_DETAIL_KEYS.get(dim_name, [])
    report = data.get("report", {})
    sources = [data, report]
    for key in keys:
        for src in sources:
            val = src.get(key)
            if val:
                if isinstance(val, dict):
                    lines = []
                    for k, v in val.items():
                        if v not in (None, "", [], {}):
                            lines.append(f"<b>{k.replace('_', ' ').title()}:</b> {v}")
                    if lines:
                        return "<br>".join(lines)
                elif isinstance(val, list):
                    return "<br>".join(f"• {item}" for item in val if item)
                elif isinstance(val, str):
                    return val
    return "No detailed evidence available for this dimension."


def _dim_detail_card(dim_name: str, score: float, weight: str,
                     data: dict, open_by_default: bool = False) -> str:
    """Clickable accordion row for a risk dimension."""
    color   = _score_color(score)
    detail  = _extract_detail(data, dim_name)
    bar     = _score_bar_dark(score, 160)
    open_attr = " open" if open_by_default else ""

    return (
        f"<details{open_attr} style='border-bottom:1px solid {BORDER};padding:2px 0'>"
        f"<summary style='display:flex;align-items:center;gap:12px;padding:10px 4px;"
        f"cursor:pointer;list-style:none;outline:none'>"
        f"<span style='flex:1;font-size:13px;color:{TEXT}'>{dim_name}</span>"
        f"<span style='font-size:11px;color:{DIM};width:36px;text-align:center'>{weight}</span>"
        f"{bar}"
        f"</summary>"
        f"<div style='padding:10px 4px 14px 28px;font-size:12px;color:{DIM};"
        f"line-height:1.7;border-left:2px solid {color};margin-left:8px'>{detail}</div>"
        f"</details>"
    )


class HadesPanel(param.Parameterized):
    def __init__(self, client_name: str = "default", **params):
        super().__init__(**params)
        self.client_name  = client_name
        self._result: dict | None = None
        self._mode: str  = "check"
        self._step_states: dict = {k: "pending" for k in STEP_KEYS}

        # ── Input widgets ─────────────────────────────────────────────────────
        self._company_input = pn.widgets.TextInput(
            placeholder="e.g. Robert Bosch GmbH",
            name="", width=340,
            stylesheets=[f"""
                :host input {{
                    background:#1E293B;border:1.5px solid {BORDER};color:{TEXT};
                    border-radius:8px;padding:8px 12px;font-size:13px;
                }}
                :host input:focus {{border-color:{ACCENT};outline:none;}}
                :host input::placeholder {{color:{DIM};}}
            """],
        )
        self._category_sel = pn.widgets.Select(
            options=SPENDLENS_CATEGORIES, value="Professional Services",
            name="", width=220,
            stylesheets=[f"""
                :host select {{
                    background:#1E293B;border:1.5px solid {BORDER};color:{TEXT};
                    border-radius:8px;padding:8px 10px;font-size:13px;
                }}
            """],
        )
        self._country_input = pn.widgets.TextInput(
            value="DE", name="", width=70,
            stylesheets=[f"""
                :host input {{
                    background:#1E293B;border:1.5px solid {BORDER};color:{TEXT};
                    border-radius:8px;padding:8px 10px;font-size:13px;text-align:center;
                }}
                :host input:focus {{border-color:{ACCENT};outline:none;}}
            """],
        )
        self._mode_toggle = pn.widgets.RadioButtonGroup(
            options=["🔍 Compliance Check", "➕ Onboard Supplier"],
            value="🔍 Compliance Check",
            button_type="default", width=360,
            stylesheets=[f"""
                :host .bk-btn {{
                    background:#1E293B;border:1.5px solid {BORDER};
                    color:{DIM};font-size:13px;border-radius:8px;padding:8px 16px;
                    transition:all 0.2s;
                }}
                :host .bk-btn:hover {{border-color:{ACCENT};color:{TEXT};}}
                :host .bk-btn.bk-active {{
                    background:{ACCENT};border-color:{ACCENT};
                    color:#fff;font-weight:700;
                }}
            """],
        )
        self._run_btn = pn.widgets.Button(
            name="▶  Run Investigation", button_type="primary", width=200,
            stylesheets=[f"""
                :host .bk-btn {{
                    background:linear-gradient(135deg,{ACCENT},{NAVY2});
                    border:none;font-size:14px;font-weight:700;
                    border-radius:8px;padding:10px 20px;color:#fff;
                    box-shadow:0 4px 12px {ACCENT}44;transition:opacity 0.2s;
                }}
                :host .bk-btn:hover {{opacity:0.9;}}
                :host .bk-btn:disabled {{opacity:0.4;}}
            """],
        )
        self._status_md   = pn.pane.Markdown("", width=600,
                                              stylesheets=[f"p{{color:{DIM};font-size:13px;}}"])
        self._pipeline_pane = pn.pane.HTML("", width=420, sizing_mode="fixed")
        self._result_pane   = pn.pane.HTML("", sizing_mode="stretch_width")

        self._run_btn.on_click(self._on_run)
        self._mode_toggle.param.watch(self._on_mode_change, "value")
        self._mode_desc = pn.pane.HTML(self._mode_desc_html(), width=600)

    def _mode_desc_html(self) -> str:
        if "Onboard" in self._mode_toggle.value:
            return (
                f"<p style='font-size:12px;color:{DIM};margin:4px 0 0'>"
                f"Runs full DD — if result is <b style='color:{GREEN}'>Approve</b> or "
                f"<b style='color:{YELLOW}'>Conditional Approval</b>, "
                f"the supplier is added to SpendLens and registered with Hermes.</p>"
            )
        return (
            f"<p style='font-size:12px;color:{DIM};margin:4px 0 0'>"
            f"Standalone risk check — <b>no data is written</b> to SpendLens or Hermes.</p>"
        )

    def _on_mode_change(self, event):
        self._mode_desc.object = self._mode_desc_html()

    def _pipeline_html(self) -> str:
        rows = "".join(
            _step_row(label, self._step_states[key])
            for key, label in PIPELINE_STEPS
        )
        running_count = sum(1 for v in self._step_states.values() if v == "running")
        pass_count    = sum(1 for v in self._step_states.values() if v == "pass")
        progress_pct  = int(pass_count / len(STEP_KEYS) * 100)

        progress_bar = ""
        if pass_count > 0 or running_count > 0:
            progress_bar = (
                f"<div style='margin-bottom:12px'>"
                f"<div style='display:flex;justify-content:space-between;"
                f"font-size:10px;color:{DIM};margin-bottom:4px'>"
                f"<span>Progress</span><span>{progress_pct}%</span></div>"
                f"<div style='height:4px;background:#2D3748;border-radius:2px'>"
                f"<div style='width:{progress_pct}%;height:100%;background:{ACCENT};"
                f"border-radius:2px;transition:width 0.5s ease'></div></div>"
                f"</div>"
            )

        css = (
            "<style>"
            ".spinning{display:inline-block;animation:spin 1s linear infinite;}"
            "@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}"
            "details summary::-webkit-details-marker{display:none}"
            "details[open] summary::before{content:'▼ ';color:" + DIM + ";font-size:9px}"
            "details:not([open]) summary::before{content:'▶ ';color:" + DIM + ";font-size:9px}"
            "</style>"
        )
        return (
            css +
            f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:12px;"
            f"padding:18px 20px;'>"
            f"<div style='font-size:11px;font-weight:700;color:{ACCENT};text-transform:uppercase;"
            f"letter-spacing:1.5px;margin-bottom:12px'>Investigation Pipeline</div>"
            + progress_bar
            + rows
            + "</div>"
        )

    def _advance_steps(self, up_to_key: str, state: str = "pass"):
        for key, _ in PIPELINE_STEPS:
            if self._step_states[key] == "pending":
                self._step_states[key] = "running"
                self._pipeline_pane.object = self._pipeline_html()
                break
        for key, _ in PIPELINE_STEPS:
            if key == up_to_key:
                self._step_states[key] = state
                break
            if self._step_states[key] in ("pending", "running"):
                self._step_states[key] = state
        self._pipeline_pane.object = self._pipeline_html()

    def _reset_pipeline(self):
        self._step_states = {k: "pending" for k in STEP_KEYS}
        self._pipeline_pane.object = self._pipeline_html()

    def _on_run(self, event):
        company = self._company_input.value.strip()
        if not company:
            self._status_md.object = "⚠️ Please enter a company name."
            return
        if not HADES_URL:
            self._status_md.object = (
                "⚠️ **HADES_URL** not set — add it to Railway Variables:\n\n"
                "`HADES_URL=https://<your-hades-service>.up.railway.app`"
            )
            return

        self._mode = "onboard" if "Onboard" in self._mode_toggle.value else "check"
        self._run_btn.disabled = True
        self._result_pane.object = ""
        self._status_md.object  = f"🔍 Investigating **{company}** — this takes 60–120 seconds…"
        self._reset_pipeline()
        threading.Thread(target=self._run_investigation, args=(company,), daemon=True).start()

    def _run_investigation(self, company: str):
        category = self._category_sel.value
        country  = self._country_input.value.strip() or "DE"
        try:
            import time

            def _tick_steps(keys, delay=8.0):
                for k in keys:
                    time.sleep(delay)
                    self._advance_steps(k)

            anim_keys = [
                "hermes_preflight", "web_research", "news_sentiment_analysis",
                "sanctions_verification", "registry_lookups",
                "lksg_compliance_signals", "esg_compliance_signals",
            ]
            anim = threading.Thread(target=_tick_steps, args=(anim_keys, 8.0), daemon=True)
            anim.start()

            resp = requests.post(
                f"{HADES_URL}/investigate",
                json={"company": company, "category": category,
                      "country": country, "mode": "full"},
                timeout=180,
            )
            resp.raise_for_status()
            data = resp.json()

            self._advance_steps("synthesis")
            self._advance_steps("report_generation")
            self._advance_steps("hermes_registration")

            self._result = data
            pn.state.execute(lambda: self._render_result(data, company, category, country))

        except requests.exceptions.Timeout:
            pn.state.execute(lambda: self._show_error(
                "Investigation timed out (>180s). Hades may be under load — try again."
            ))
        except Exception as e:
            pn.state.execute(lambda: self._show_error(str(e)))
        finally:
            pn.state.execute(lambda: setattr(self._run_btn, "disabled", False))

    def _show_error(self, msg: str):
        for k in STEP_KEYS:
            if self._step_states[k] == "running":
                self._step_states[k] = "fail"
        self._pipeline_pane.object = self._pipeline_html()
        self._status_md.object = f"❌ {msg}"

    def _render_result(self, data: dict, company: str, category: str, country: str):
        report    = data.get("report", {})
        scores    = data.get("risk_scores", {})
        overall   = report.get("overall_risk_score") or scores.get("overall_score", 0)
        risk_lvl  = report.get("risk_level") or data.get("risk_level", "Unknown")
        rec       = report.get("recommendation") or data.get("recommendation", "Unknown")
        exec_sum  = report.get("executive_summary", "")
        next_steps = report.get("required_next_steps") or data.get("next_steps", [])
        hermes_reg = data.get("hermes_registered", False)

        score_dims = [
            ("Sanctions",         scores.get("sanctions_score",      overall), "25%"),
            ("LkSG / CSDDD",      scores.get("lksg_csddd_score",     overall), "20%"),
            ("Company Registry",  scores.get("registry_score",       overall), "15%"),
            ("News Sentiment",    scores.get("news_sentiment_score", overall), "15%"),
            ("ESG & Labour",      scores.get("esg_labour_score",     overall), "15%"),
            ("Hermes Intel",      scores.get("hermes_score",         overall), "10%"),
        ]

        rec_color = REC_COLOR.get(rec, ACCENT)
        rec_icon  = REC_ICON.get(rec, "")
        lvl_color = RISK_COLOR.get(risk_lvl, DIM)
        overall_color = _score_color(overall)

        # ── Header card ───────────────────────────────────────────────────────
        hermes_badge = (
            f"<div style='margin-top:6px;display:inline-block;background:{GREEN}22;"
            f"border:1px solid {GREEN}55;border-radius:20px;padding:2px 10px;"
            f"font-size:11px;color:{GREEN}'>✓ Added to Hermes</div>"
            if hermes_reg else ""
        )
        header = (
            f"<div style='background:linear-gradient(135deg,{CARD} 0%,#162032 100%);"
            f"border:1px solid {BORDER};border-radius:14px;"
            f"padding:24px 28px;margin-bottom:14px;"
            f"box-shadow:0 4px 24px #00000033'>"
            f"<div style='display:flex;align-items:flex-start;gap:24px;flex-wrap:wrap'>"

            # Company name + meta
            f"<div style='flex:1;min-width:200px'>"
            f"<div style='font-size:24px;font-weight:800;color:{TEXT};letter-spacing:-0.5px'>"
            f"{company}</div>"
            f"<div style='font-size:12px;color:{DIM};margin-top:4px'>"
            f"{category} &nbsp;·&nbsp; {country} &nbsp;·&nbsp; "
            f"{datetime.now().strftime('%Y-%m-%d')}</div>"
            f"{hermes_badge}"
            f"</div>"

            # Overall risk score — big number
            f"<div style='text-align:center;min-width:110px'>"
            f"<div style='font-size:10px;color:{DIM};text-transform:uppercase;"
            f"letter-spacing:1.5px;margin-bottom:4px'>Overall Risk</div>"
            f"<div style='font-size:52px;font-weight:900;color:{overall_color};"
            f"line-height:1;text-shadow:0 0 20px {overall_color}44'>{overall:.1f}</div>"
            f"<div style='font-size:12px;color:{overall_color};font-weight:700;"
            f"margin-top:4px;text-transform:uppercase;letter-spacing:1px'>{risk_lvl}</div>"
            f"</div>"

            # Recommendation pill
            f"<div style='text-align:center;min-width:160px'>"
            f"<div style='font-size:10px;color:{DIM};text-transform:uppercase;"
            f"letter-spacing:1.5px;margin-bottom:8px'>Recommendation</div>"
            f"<div style='display:inline-block;background:{rec_color}22;"
            f"border:2px solid {rec_color}66;border-radius:12px;"
            f"padding:8px 20px;font-size:17px;font-weight:800;color:{rec_color}'>"
            f"{rec_icon} {rec}</div>"
            f"</div>"

            f"</div></div>"
        )

        # ── Risk legend ───────────────────────────────────────────────────────
        legend = _risk_legend_html()

        # ── Score breakdown — clickable accordion ─────────────────────────────
        dim_rows = "".join(
            _dim_detail_card(dim, sc, weight, data)
            for dim, sc, weight in score_dims
        )
        scores_card = (
            f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:12px;"
            f"padding:18px 22px;margin-bottom:14px'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;"
            f"margin-bottom:12px'>"
            f"<div style='font-size:11px;font-weight:700;color:{ACCENT};text-transform:uppercase;"
            f"letter-spacing:1.5px'>Risk Score Breakdown</div>"
            f"<div style='font-size:11px;color:{DIM}'>Click a dimension to view evidence ▼</div>"
            f"</div>"
            f"<div style='display:flex;padding:4px 4px 8px;"
            f"font-size:10px;color:{DIM};gap:12px;border-bottom:1px solid {BORDER};margin-bottom:4px'>"
            f"<span style='flex:1'>Dimension</span>"
            f"<span style='width:36px;text-align:center'>Weight</span>"
            f"<span style='width:220px'>Score</span>"
            f"</div>"
            + dim_rows +
            f"</div>"
        )

        # ── Executive summary ─────────────────────────────────────────────────
        summary_card = ""
        if exec_sum:
            summary_card = (
                f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:12px;"
                f"padding:18px 22px;margin-bottom:14px'>"
                f"<div style='font-size:11px;font-weight:700;color:{ACCENT};text-transform:uppercase;"
                f"letter-spacing:1.5px;margin-bottom:10px'>Executive Summary</div>"
                f"<div style='font-size:13px;color:{DIM};line-height:1.7'>{exec_sum}</div>"
                f"</div>"
            )

        # ── Required next steps ───────────────────────────────────────────────
        steps_html = ""
        if next_steps:
            items = "".join(
                f"<li style='margin-bottom:8px;font-size:13px;color:{DIM};line-height:1.6'>{s}</li>"
                for s in next_steps
            )
            steps_html = (
                f"<div style='background:#1C1700;border:1px solid {YELLOW}44;"
                f"border-radius:12px;padding:18px 22px;margin-bottom:14px'>"
                f"<div style='font-size:11px;font-weight:700;color:{YELLOW};text-transform:uppercase;"
                f"letter-spacing:1.5px;margin-bottom:10px'>Required Next Steps</div>"
                f"<ul style='margin:0;padding-left:20px'>{items}</ul>"
                f"</div>"
            )

        # ── Onboard action card ───────────────────────────────────────────────
        onboard_html = ""
        if self._mode == "onboard":
            if rec == "Block":
                onboard_html = (
                    f"<div style='background:#1A0A0A;border:1px solid {RED}44;"
                    f"border-radius:12px;padding:18px 22px;margin-bottom:14px'>"
                    f"<div style='font-size:14px;color:{RED};font-weight:700'>"
                    f"🚫 Supplier blocked — not added to SpendLens</div>"
                    f"<div style='font-size:12px;color:{DIM};margin-top:6px'>"
                    f"Risk score exceeds onboarding threshold. Manual compliance review required "
                    f"before any engagement.</div>"
                    f"</div>"
                )
            else:
                saved = self._save_vendor(company, category, country, data)
                color = GREEN if saved else YELLOW
                msg   = "✅ Supplier added to SpendLens vendor database" if saved \
                        else "⚠️ Supplier already exists — Hades fields updated"
                onboard_html = (
                    f"<div style='background:#0A1A0E;border:1px solid {GREEN}44;"
                    f"border-radius:12px;padding:18px 22px;margin-bottom:14px'>"
                    f"<div style='font-size:14px;color:{color};font-weight:700'>{msg}</div>"
                    f"<div style='font-size:12px;color:{DIM};margin-top:6px'>"
                    f"Recommendation: <b style='color:{rec_color}'>{rec}</b> &nbsp;·&nbsp; "
                    f"Hermes: {'registered ✓' if hermes_reg else 'pending next Hermes cycle'}</div>"
                    f"</div>"
                )

        self._result_pane.object = (
            header + legend + scores_card + summary_card + steps_html + onboard_html
        )
        self._status_md.object = f"✅ Investigation complete — **{company}** · {risk_lvl} risk"

    def _save_vendor(self, company: str, category: str, country: str, data: dict) -> bool:
        try:
            from modules.database import get_connection, upsert_vendor
            report  = data.get("report", {})
            conn    = get_connection(self.client_name)
            existing = conn.execute(
                "SELECT id FROM vendors WHERE vendor_name = ?", (company,)
            ).fetchone()
            upsert_vendor(
                conn=conn,
                vendor_name=company,
                category=category,
                oc_country=country,
                classification_source="hades_onboard",
            )
            overall  = report.get("overall_risk_score") or data.get("risk_scores", {}).get("overall_score", 0)
            risk_lvl = report.get("risk_level") or data.get("risk_level", "")
            rec      = report.get("recommendation") or data.get("recommendation", "")
            next_s   = json.dumps(report.get("required_next_steps") or data.get("next_steps", []))
            sanctions_clear = not (report.get("sanctions_status") or {}).get("manual_review_required", False)
            lksg_sig = (report.get("lksg_csddd_assessment") or {}).get("compliance_signal", "")
            conn.execute("""
                UPDATE vendors SET
                    hades_risk_score      = ?,
                    hades_risk_level      = ?,
                    hades_recommendation  = ?,
                    hades_sanctions_clear = ?,
                    hades_lksg_signal     = ?,
                    hades_next_steps      = ?,
                    hades_report_date     = ?
                WHERE vendor_name = ?
            """, (overall, risk_lvl, rec, int(sanctions_clear), lksg_sig,
                  next_s, datetime.now().strftime("%Y-%m-%d"), company))
            conn.commit()
            conn.close()
            return existing is None
        except Exception as e:
            print(f"[Hades] DB save error: {e}")
            return False

    def view(self) -> pn.viewable.Viewable:
        # ── Label style ───────────────────────────────────────────────────────
        def _label(text: str) -> pn.pane.HTML:
            return pn.pane.HTML(
                f"<div style='font-size:10px;color:{DIM};font-weight:700;"
                f"text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px'>{text}</div>"
            )

        input_row = pn.Row(
            pn.Column(_label("Company Name"), self._company_input),
            pn.Column(_label("Category"),     self._category_sel),
            pn.Column(_label("Country"),      self._country_input),
            align="start", margin=(0, 0, 16, 0),
        )
        mode_row = pn.Column(
            _label("Investigation Mode"),
            self._mode_toggle,
            self._mode_desc,
            margin=(0, 0, 20, 0),
        )
        run_row = pn.Row(self._run_btn, self._status_md, align="center", margin=(0, 0, 24, 0))

        # ── Dark premium header ───────────────────────────────────────────────
        header_html = pn.pane.HTML(
            f"<div style='background:linear-gradient(135deg,#0F172A 0%,#1E3A5F 100%);"
            f"border-radius:14px;padding:24px 32px;margin-bottom:24px;"
            f"border:1px solid {BORDER};box-shadow:0 8px 32px #00000044;"
            f"display:flex;align-items:center;gap:20px'>"
            f"<div style='font-size:40px'>⚖️</div>"
            f"<div>"
            f"<div style='font-size:26px;font-weight:900;color:#fff;letter-spacing:-1px'>Hades</div>"
            f"<div style='font-size:13px;color:{DIM};margin-top:3px'>"
            f"Autonomous supplier due diligence &nbsp;·&nbsp; "
            f"Sanctions &nbsp;·&nbsp; LkSG/CSDDD &nbsp;·&nbsp; ESG &nbsp;·&nbsp; "
            f"News &nbsp;·&nbsp; Registry &nbsp;·&nbsp; Hermes</div>"
            f"</div>"
            f"<div style='margin-left:auto;text-align:right'>"
            f"<div style='font-size:10px;color:{DIM};text-transform:uppercase;"
            f"letter-spacing:1px'>Powered by</div>"
            f"<div style='font-size:13px;color:{ACCENT};font-weight:700'>Claude Sonnet 4.6</div>"
            f"</div>"
            f"</div>",
            sizing_mode="stretch_width",
        )

        # ── Form card ─────────────────────────────────────────────────────────
        form_card = pn.pane.HTML(
            f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:12px;"
            f"padding:22px 26px;margin-bottom:20px'>",
            width=0, height=0,
        )

        content = pn.Row(
            pn.Column(self._pipeline_pane, width=440, margin=(0, 24, 0, 0)),
            pn.Column(self._result_pane, sizing_mode="stretch_width"),
            sizing_mode="stretch_width",
        )

        warning = pn.pane.HTML("")
        if not HADES_URL:
            warning = pn.pane.HTML(
                f"<div style='background:#1C1400;border:1px solid {YELLOW}55;border-radius:10px;"
                f"padding:12px 18px;margin-bottom:18px;font-size:13px;color:{YELLOW}'>"
                f"⚠️ <b>HADES_URL</b> not configured — add it to Railway Variables to enable investigations."
                f"</div>",
                sizing_mode="stretch_width",
            )

        form_section = pn.Column(
            input_row, mode_row, run_row,
            pn.layout.Divider(margin=(4, 0, 20, 0)),
            content,
            stylesheets=[f"""
                :host {{
                    background:{CARD};border:1px solid {BORDER};border-radius:12px;
                    padding:22px 26px;
                }}
            """],
            sizing_mode="stretch_width",
            margin=(0, 0, 0, 0),
        )

        main = pn.Column(
            header_html,
            warning,
            form_section,
            sizing_mode="stretch_width",
            margin=(16, 24),
            stylesheets=[f":host{{background:{BG};}}"],
        )

        self._pipeline_pane.object = self._pipeline_html()
        return main
