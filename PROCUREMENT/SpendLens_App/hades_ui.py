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

# ── Theme (mirrors app.py) ────────────────────────────────────────────────────
BG     = "#FFFFFF"
NAVY   = "#1B3A6B"
NAVY2  = "#2E5BA8"
CARD   = "#F8F9FA"
BORDER = "#E2E8F0"
TEXT   = "#1A1A2E"
DIM    = "#64748B"
GREEN  = "#1A7A4A"
YELLOW = "#B8860B"
RED    = "#C0392B"

RISK_COLOR = {"Low": GREEN, "Medium": YELLOW, "High": "#E67E22", "Critical": RED}
REC_COLOR  = {"Approve": GREEN, "Conditional Approval": YELLOW, "Block": RED}
REC_ICON   = {"Approve": "✅", "Conditional Approval": "⚠️", "Block": "🚫"}

HADES_URL = os.environ.get("HADES_URL", "")

SPENDLENS_CATEGORIES = [
    "Cloud & Compute", "AI/ML APIs & Data", "IT Software & SaaS",
    "Telecom & Voice", "Recruitment & HR", "Professional Services",
    "Marketing & Campaigns", "Facilities & Office", "Real Estate",
    "Hardware & Equipment", "Travel & Expenses",
]

# Pipeline steps shown during investigation
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


def _hades_available() -> bool:
    if not HADES_URL:
        return False
    try:
        r = requests.get(f"{HADES_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _score_bar(score: float, width: int = 180) -> str:
    """Return an HTML progress bar for a 1–10 risk score."""
    pct   = int(score * 10)
    if score <= 3.9:
        color = GREEN
    elif score <= 6.4:
        color = YELLOW
    elif score <= 7.9:
        color = "#E67E22"
    else:
        color = RED
    return (
        f"<div style='display:flex;align-items:center;gap:8px'>"
        f"<div style='width:{width}px;height:8px;background:{BORDER};border-radius:4px;overflow:hidden'>"
        f"<div style='width:{pct}%;height:100%;background:{color};border-radius:4px'></div></div>"
        f"<span style='font-size:13px;color:{color};font-weight:700'>{score:.1f}</span>"
        f"</div>"
    )


def _step_row(label: str, state: str) -> str:
    """state: pending | running | pass | fail"""
    icons = {"pending": "○", "running": "⟳", "pass": "✓", "fail": "✗"}
    colors = {"pending": DIM, "running": NAVY2, "pass": GREEN, "fail": RED}
    icon  = icons.get(state, "○")
    color = colors.get(state, DIM)
    spin  = " class='spinning'" if state == "running" else ""
    return (
        f"<div style='display:flex;align-items:center;gap:10px;padding:6px 0;"
        f"border-bottom:1px solid {BORDER}'>"
        f"<span{spin} style='font-size:16px;color:{color};width:20px;text-align:center'>{icon}</span>"
        f"<span style='font-size:13px;color:{TEXT if state != 'pending' else DIM}'>{label}</span>"
        f"</div>"
    )


class HadesPanel(param.Parameterized):
    def __init__(self, client_name: str = "default", **params):
        super().__init__(**params)
        self.client_name = client_name
        self._result: dict | None = None
        self._mode: str = "check"   # "check" | "onboard"
        self._step_states: dict = {k: "pending" for k in STEP_KEYS}

        # ── Input widgets ─────────────────────────────────────────────────────
        self._company_input = pn.widgets.TextInput(
            placeholder="e.g. Robert Bosch GmbH",
            name="", width=340,
        )
        self._category_sel = pn.widgets.Select(
            options=SPENDLENS_CATEGORIES, value="Professional Services",
            name="", width=220,
        )
        self._country_input = pn.widgets.TextInput(
            value="DE", name="", width=80,
        )
        self._mode_toggle = pn.widgets.RadioButtonGroup(
            options=["🔍 Compliance Check", "➕ Onboard Supplier"],
            value="🔍 Compliance Check",
            button_type="default", width=360,
            stylesheets=[f"""
                :host .bk-btn {{ background:{CARD};border:1.5px solid {BORDER};
                    color:{TEXT};font-size:13px;border-radius:6px;padding:6px 14px; }}
                :host .bk-btn.bk-active {{ background:{NAVY};border-color:{NAVY};
                    color:#fff;font-weight:600; }}
            """],
        )
        self._run_btn = pn.widgets.Button(
            name="▶  Run Investigation", button_type="primary", width=200,
            stylesheets=[f":host .bk-btn{{background:{NAVY};border-color:{NAVY};font-size:13px;}}"],
        )
        self._status_md = pn.pane.Markdown("", width=600)
        self._pipeline_pane = pn.pane.HTML("", width=420, sizing_mode="fixed")
        self._result_pane   = pn.pane.HTML("", sizing_mode="stretch_width")

        self._run_btn.on_click(self._on_run)
        self._mode_toggle.param.watch(self._on_mode_change, "value")

        # ── Mode description ──────────────────────────────────────────────────
        self._mode_desc = pn.pane.HTML(self._mode_desc_html(), width=600)

    def _mode_desc_html(self) -> str:
        if "Onboard" in self._mode_toggle.value:
            return (
                f"<p style='font-size:12px;color:{DIM};margin:4px 0 0'>"
                f"Runs full DD — if result is <b>Approve</b> or <b>Conditional Approval</b>, "
                f"the supplier is added to SpendLens and registered with Hermes.</p>"
            )
        return (
            f"<p style='font-size:12px;color:{DIM};margin:4px 0 0'>"
            f"Standalone risk check — no data is written to SpendLens or Hermes.</p>"
        )

    def _on_mode_change(self, event):
        self._mode_desc.object = self._mode_desc_html()

    def _pipeline_html(self) -> str:
        rows = "".join(
            _step_row(label, self._step_states[key])
            for key, label in PIPELINE_STEPS
        )
        css = "<style>.spinning{display:inline-block;animation:spin 1s linear infinite;}" \
              "@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}</style>"
        return (
            css +
            f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:10px;"
            f"padding:16px 20px;'>"
            f"<div style='font-size:12px;font-weight:700;color:{NAVY};text-transform:uppercase;"
            f"letter-spacing:1px;margin-bottom:10px'>Investigation Pipeline</div>"
            + rows +
            "</div>"
        )

    def _advance_steps(self, up_to_key: str, state: str = "pass"):
        """Mark all steps up to (and including) up_to_key as the given state."""
        for key, _ in PIPELINE_STEPS:
            if self._step_states[key] == "pending":
                self._step_states[key] = "running"
                self._pipeline_pane.object = self._pipeline_html()
                break
        # mark all before up_to_key as pass
        reached = False
        for key, _ in PIPELINE_STEPS:
            if key == up_to_key:
                self._step_states[key] = state
                reached = True
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
            # Simulate step progression as we wait for the response
            # (Hades runs all 6 research nodes in parallel so we animate sequentially)
            import time

            def _tick_steps(keys, delay=3.0):
                for k in keys:
                    time.sleep(delay)
                    self._advance_steps(k)

            # Start parallel step animation in background
            anim_keys = [
                "hermes_preflight",
                "web_research",
                "news_sentiment_analysis",
                "sanctions_verification",
                "registry_lookups",
                "lksg_compliance_signals",
                "esg_compliance_signals",
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

            # Mark remaining steps
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
        report = data.get("report", {})
        scores = data.get("risk_scores", {})

        # Support both response shapes (flat dict or nested)
        overall   = report.get("overall_risk_score") or scores.get("overall_score", 0)
        risk_lvl  = report.get("risk_level") or data.get("risk_level", "Unknown")
        rec       = report.get("recommendation") or data.get("recommendation", "Unknown")
        exec_sum  = report.get("executive_summary", "")
        next_steps = report.get("required_next_steps") or data.get("next_steps", [])
        hermes_reg = data.get("hermes_registered", False)

        # Score breakdown
        score_dims = [
            ("Sanctions",         scores.get("sanctions_score",        overall), "25%"),
            ("LkSG / CSDDD",      scores.get("lksg_csddd_score",       overall), "20%"),
            ("Company Registry",  scores.get("registry_score",         overall), "15%"),
            ("News Sentiment",    scores.get("news_sentiment_score",   overall), "15%"),
            ("ESG & Labour",      scores.get("esg_labour_score",       overall), "15%"),
            ("Hermes Intel",      scores.get("hermes_score",           overall), "10%"),
        ]

        rec_color = REC_COLOR.get(rec, NAVY)
        rec_icon  = REC_ICON.get(rec, "")
        lvl_color = RISK_COLOR.get(risk_lvl, DIM)

        # Header card
        header = (
            f"<div style='display:flex;align-items:flex-start;gap:24px;flex-wrap:wrap;"
            f"background:{CARD};border:1px solid {BORDER};border-radius:12px;"
            f"padding:20px 24px;margin-bottom:16px'>"

            f"<div style='flex:1;min-width:200px'>"
            f"<div style='font-size:20px;font-weight:700;color:{NAVY}'>{company}</div>"
            f"<div style='font-size:12px;color:{DIM};margin-top:2px'>"
            f"{category} · {country} · {datetime.now().strftime('%Y-%m-%d')}</div>"
            f"</div>"

            f"<div style='text-align:center;min-width:100px'>"
            f"<div style='font-size:11px;color:{DIM};text-transform:uppercase;letter-spacing:1px'>Overall Risk</div>"
            f"<div style='font-size:36px;font-weight:800;color:{lvl_color};line-height:1.1'>{overall:.1f}</div>"
            f"<div style='font-size:12px;color:{lvl_color};font-weight:600'>{risk_lvl}</div>"
            f"</div>"

            f"<div style='text-align:center;min-width:140px'>"
            f"<div style='font-size:11px;color:{DIM};text-transform:uppercase;letter-spacing:1px'>Recommendation</div>"
            f"<div style='font-size:22px;font-weight:800;color:{rec_color};margin-top:4px'>"
            f"{rec_icon} {rec}</div>"
            f"{'<div style=\"font-size:11px;color:' + GREEN + ';margin-top:4px\">✓ Added to Hermes</div>' if hermes_reg else ''}"
            f"</div>"
            f"</div>"
        )

        # Score breakdown table
        score_rows = "".join(
            f"<tr>"
            f"<td style='padding:6px 10px;font-size:13px;color:{TEXT}'>{dim}</td>"
            f"<td style='padding:6px 10px;font-size:11px;color:{DIM};text-align:center'>{weight}</td>"
            f"<td style='padding:6px 10px'>{_score_bar(sc, 160)}</td>"
            f"</tr>"
            for dim, sc, weight in score_dims
        )
        scores_card = (
            f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:10px;"
            f"padding:16px 20px;margin-bottom:16px'>"
            f"<div style='font-size:12px;font-weight:700;color:{NAVY};text-transform:uppercase;"
            f"letter-spacing:1px;margin-bottom:10px'>Risk Score Breakdown</div>"
            f"<table style='width:100%;border-collapse:collapse'>"
            f"<thead><tr>"
            f"<th style='text-align:left;font-size:11px;color:{DIM};padding:4px 10px'>Dimension</th>"
            f"<th style='font-size:11px;color:{DIM};padding:4px 10px'>Weight</th>"
            f"<th style='text-align:left;font-size:11px;color:{DIM};padding:4px 10px'>Score</th>"
            f"</tr></thead><tbody>{score_rows}</tbody></table>"
            f"</div>"
        )

        # Executive summary
        summary_card = ""
        if exec_sum:
            summary_card = (
                f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:10px;"
                f"padding:16px 20px;margin-bottom:16px'>"
                f"<div style='font-size:12px;font-weight:700;color:{NAVY};text-transform:uppercase;"
                f"letter-spacing:1px;margin-bottom:8px'>Executive Summary</div>"
                f"<div style='font-size:13px;color:{TEXT};line-height:1.6'>{exec_sum}</div>"
                f"</div>"
            )

        # Next steps
        steps_html = ""
        if next_steps:
            items = "".join(
                f"<li style='margin-bottom:6px;font-size:13px;color:{TEXT}'>{s}</li>"
                for s in next_steps
            )
            steps_html = (
                f"<div style='background:#FFF8E1;border:1px solid {YELLOW}33;"
                f"border-radius:10px;padding:16px 20px;margin-bottom:16px'>"
                f"<div style='font-size:12px;font-weight:700;color:{YELLOW};text-transform:uppercase;"
                f"letter-spacing:1px;margin-bottom:8px'>Required Next Steps</div>"
                f"<ul style='margin:0;padding-left:20px'>{items}</ul>"
                f"</div>"
            )

        # Onboard action card
        onboard_html = ""
        if self._mode == "onboard":
            if rec == "Block":
                onboard_html = (
                    f"<div style='background:#FFF0F0;border:1px solid {RED}44;"
                    f"border-radius:10px;padding:16px 20px;margin-bottom:16px'>"
                    f"<div style='font-size:13px;color:{RED};font-weight:700'>"
                    f"🚫 Supplier blocked — not added to SpendLens</div>"
                    f"<div style='font-size:12px;color:{DIM};margin-top:4px'>"
                    f"Risk score exceeds onboarding threshold. Manual compliance review required.</div>"
                    f"</div>"
                )
            else:
                # Save to DB
                saved = self._save_vendor(company, category, country, data)
                color = GREEN if saved else YELLOW
                msg   = "✅ Supplier added to SpendLens vendor database" if saved \
                        else "⚠️ Supplier already exists — Hades fields updated"
                onboard_html = (
                    f"<div style='background:#F0FFF4;border:1px solid {GREEN}44;"
                    f"border-radius:10px;padding:16px 20px;margin-bottom:16px'>"
                    f"<div style='font-size:13px;color:{color};font-weight:700'>{msg}</div>"
                    f"<div style='font-size:12px;color:{DIM};margin-top:4px'>"
                    f"Recommendation: <b>{rec}</b> · Hermes watchlist: "
                    f"{'registered' if hermes_reg else 'pending next Hermes cycle'}</div>"
                    f"</div>"
                )

        self._result_pane.object = header + scores_card + summary_card + steps_html + onboard_html
        self._status_md.object  = f"✅ Investigation complete — **{company}** · {risk_lvl} risk"

    def _save_vendor(self, company: str, category: str, country: str, data: dict) -> bool:
        """Upsert vendor into SpendLens DB with Hades fields. Returns True if newly inserted."""
        try:
            from modules.database import get_connection, upsert_vendor
            report = data.get("report", {})
            conn   = get_connection(self.client_name)

            # Check if already exists
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

            # Write Hades-specific fields via UPDATE
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
        # ── Input row ─────────────────────────────────────────────────────────
        input_row = pn.Row(
            pn.Column(
                pn.pane.HTML(f"<div style='font-size:11px;color:{DIM};font-weight:600;"
                             f"text-transform:uppercase;letter-spacing:1px;margin-bottom:4px'>"
                             f"Company Name</div>"),
                self._company_input,
            ),
            pn.Column(
                pn.pane.HTML(f"<div style='font-size:11px;color:{DIM};font-weight:600;"
                             f"text-transform:uppercase;letter-spacing:1px;margin-bottom:4px'>"
                             f"Category</div>"),
                self._category_sel,
            ),
            pn.Column(
                pn.pane.HTML(f"<div style='font-size:11px;color:{DIM};font-weight:600;"
                             f"text-transform:uppercase;letter-spacing:1px;margin-bottom:4px'>"
                             f"Country</div>"),
                self._country_input,
            ),
            align="start", margin=(0, 0, 12, 0),
        )

        # ── Mode selector ─────────────────────────────────────────────────────
        mode_row = pn.Column(
            pn.pane.HTML(f"<div style='font-size:11px;color:{DIM};font-weight:600;"
                         f"text-transform:uppercase;letter-spacing:1px;margin-bottom:6px'>"
                         f"Investigation Mode</div>"),
            self._mode_toggle,
            self._mode_desc,
            margin=(0, 0, 16, 0),
        )

        # ── Run button + status ───────────────────────────────────────────────
        run_row = pn.Row(self._run_btn, self._status_md, align="center", margin=(0, 0, 20, 0))

        # ── Header ───────────────────────────────────────────────────────────
        header_html = pn.pane.HTML(
            f"<div style='background:{NAVY};border-radius:12px;padding:20px 28px;"
            f"margin-bottom:20px;display:flex;align-items:center;gap:16px'>"
            f"<div>"
            f"<div style='font-size:22px;font-weight:800;color:#fff'>⚖️ Hades</div>"
            f"<div style='font-size:13px;color:rgba(255,255,255,0.7);margin-top:2px'>"
            f"Autonomous supplier due diligence · Sanctions · LkSG/CSDDD · ESG · News · Registry</div>"
            f"</div></div>",
            sizing_mode="stretch_width",
        )

        # ── Two-column layout: pipeline left, results right ───────────────────
        content = pn.Row(
            pn.Column(self._pipeline_pane, width=440, margin=(0, 20, 0, 0)),
            pn.Column(self._result_pane, sizing_mode="stretch_width"),
            sizing_mode="stretch_width",
        )

        # ── HADES_URL warning ─────────────────────────────────────────────────
        warning = ""
        if not HADES_URL:
            warning = pn.pane.HTML(
                f"<div style='background:#FFF8E1;border:1px solid {YELLOW};border-radius:8px;"
                f"padding:10px 16px;margin-bottom:16px;font-size:13px;color:{YELLOW}'>"
                f"⚠️ <b>HADES_URL</b> not configured — add it to Railway Variables to enable investigations."
                f"</div>",
                sizing_mode="stretch_width",
            )

        main = pn.Column(
            header_html,
            warning if warning else pn.pane.HTML(""),
            pn.Column(
                input_row, mode_row, run_row,
                pn.layout.Divider(),
                content,
                sizing_mode="stretch_width",
                margin=(0, 0, 0, 0),
            ),
            sizing_mode="stretch_width",
            margin=(16, 24),
        )

        # Initialise pipeline display
        self._pipeline_pane.object = self._pipeline_html()

        return main
