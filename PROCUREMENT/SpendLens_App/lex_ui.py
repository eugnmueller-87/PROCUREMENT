"""
Lex CLM UI — Contract Lifecycle Management Tab for SpendLens
"""

import os
import json
import threading
import panel as pn
import param
from datetime import datetime

# ── Theme (matches SpendLens / app.py) ────────────────────────────────────────
NAVY   = "#1B3A6B"
NAVY2  = "#2E5BA8"
CARD   = "#F8F9FA"
BORDER = "#E2E8F0"
TEXT   = "#1A1A2E"
DIM    = "#64748B"
GREEN  = "#1A7A4A"
YELLOW = "#B8860B"
ORANGE = "#E67E22"
RED    = "#C0392B"

RISK_COLOR = {"Low": GREEN, "Medium": YELLOW, "High": ORANGE, "Critical": RED}

CONTRACT_TYPES = ["MSA", "SaaS / License", "Freelancer / Dienstleistung", "NDA", "Rahmenvertrag", "Other"]

CLAUSE_LABELS = {
    "start_date":          "Start Date",
    "end_date":            "End Date / Expiry",
    "notice_period_days":  "Termination Notice",
    "auto_renewal":        "Auto-Renewal",
    "auto_renewal_period": "Auto-Renewal Period",
    "penalty_cap_pct":     "Penalty Cap",
    "liability_cap":       "Liability Cap",
    "price_adjustment":    "Price Adjustment",
    "jurisdiction":        "Jurisdiction",
    "sla_terms":           "SLA Terms",
    "payment_terms":       "Payment Terms",
    "termination_rights":  "Termination Rights",
}

FLAG_COLORS = {"green": GREEN, "yellow": YELLOW, "red": RED}
FLAG_ICONS  = {"green": "✓", "yellow": "⚠", "red": "✗"}


def _flag_badge(color: str) -> str:
    c = FLAG_COLORS.get(color, DIM)
    i = FLAG_ICONS.get(color, "?")
    return (
        f"<span style='display:inline-flex;align-items:center;justify-content:center;"
        f"width:22px;height:22px;border-radius:50%;background:{c}22;"
        f"border:1.5px solid {c};font-size:12px;color:{c};font-weight:700'>{i}</span>"
    )


def _clause_row(label: str, value, color: str, detail: str = "") -> str:
    badge = _flag_badge(color)
    val_str = "—" if value is None or value == "" else str(value)
    if label == "Auto-Renewal" and isinstance(value, int):
        val_str = "Yes ⚠" if value else "No ✓"
    if label == "Termination Notice" and isinstance(value, int):
        val_str = f"{value} days"
    if label == "Penalty Cap" and value is not None:
        val_str = f"{value}% of contract value"

    detail_html = ""
    if detail and len(detail) > 4:
        detail_html = (
            f"<div style='font-size:11px;color:{DIM};margin-top:3px;"
            f"padding-left:32px;line-height:1.5'>{detail[:200]}</div>"
        )

    return (
        f"<div style='display:flex;align-items:flex-start;gap:10px;padding:8px 0;"
        f"border-bottom:1px solid {BORDER}'>"
        f"<div style='flex-shrink:0;margin-top:1px'>{badge}</div>"
        f"<div style='flex:1'>"
        f"<div style='display:flex;justify-content:space-between'>"
        f"<span style='font-size:12px;font-weight:600;color:{TEXT}'>{label}</span>"
        f"<span style='font-size:12px;color:{DIM}'>{val_str}</span>"
        f"</div>"
        f"{detail_html}"
        f"</div></div>"
    )


def _risk_gauge(score: float, level: str) -> str:
    color = RISK_COLOR.get(level, DIM)
    pct   = int(score * 10)
    return (
        f"<div style='display:flex;align-items:center;gap:16px'>"
        f"<div style='text-align:center'>"
        f"<div style='font-size:44px;font-weight:900;color:{color};line-height:1'>{score:.1f}</div>"
        f"<div style='font-size:11px;color:{color};font-weight:700;text-transform:uppercase;"
        f"letter-spacing:1px'>{level}</div>"
        f"</div>"
        f"<div style='flex:1'>"
        f"<div style='height:12px;background:{BORDER};border-radius:6px;overflow:hidden'>"
        f"<div style='width:{pct}%;height:100%;background:{color};border-radius:6px;"
        f"transition:width 0.8s ease'></div></div>"
        f"<div style='display:flex;justify-content:space-between;"
        f"font-size:10px;color:{DIM};margin-top:3px'>"
        f"<span>1 Low</span><span>5 Medium</span><span>8 High</span><span>10 Critical</span>"
        f"</div></div></div>"
    )


class LexPanel(param.Parameterized):
    def __init__(self, client_name: str = "default", **params):
        super().__init__(**params)
        self.client_name = client_name
        self._result: dict | None = None
        self._file_bytes: bytes | None = None
        self._filename: str = ""

        # ── Widgets ───────────────────────────────────────────────────────────
        self._file_input = pn.widgets.FileInput(
            accept=".pdf,.docx,.doc,.txt",
            multiple=False,
            name="",
        )
        self._vendor_input = pn.widgets.TextInput(
            placeholder="e.g. Salesforce GmbH (optional)",
            name="", width=300,
        )
        self._type_sel = pn.widgets.Select(
            options=CONTRACT_TYPES,
            value="MSA",
            name="", width=200,
        )
        self._scan_btn = pn.widgets.Button(
            name="🔍  Scan Contract", button_type="primary", width=180,
            stylesheets=[f":host .bk-btn{{background:{NAVY};border-color:{NAVY};font-size:13px;font-weight:600;}}"],
        )
        self._save_btn = pn.widgets.Button(
            name="💾  Save to SpendLens", button_type="success", width=200,
            disabled=True,
            stylesheets=[f":host .bk-btn{{background:{GREEN};border-color:{GREEN};font-size:13px;font-weight:600;}}"],
        )
        self._status_md = pn.pane.Markdown("", width=500,
                                            stylesheets=[f"p{{color:{DIM};font-size:13px;margin:0}}"])
        self._clause_pane  = pn.pane.HTML("", sizing_mode="stretch_width")
        self._report_pane  = pn.pane.HTML("", sizing_mode="stretch_width")
        self._history_pane = pn.pane.HTML("", sizing_mode="stretch_width")

        self._scan_btn.on_click(self._on_scan)
        self._save_btn.on_click(self._on_save)
        self._file_input.param.watch(self._on_file_change, "value")

        self._load_history()

    def _on_file_change(self, event):
        if self._file_input.value:
            self._status_md.object = f"📄 File loaded: **{self._file_input.filename}** — click Scan to analyse"

    def _on_scan(self, event):
        if not self._file_input.value:
            self._status_md.object = "⚠️ Please upload a contract file first."
            return

        self._scan_btn.disabled = True
        self._save_btn.disabled = True
        self._clause_pane.object = ""
        self._report_pane.object = ""
        self._status_md.object = "🔍 Scanning contract — extracting clauses with AI…"

        file_bytes = self._file_input.value
        filename   = self._file_input.filename or "contract.pdf"
        vendor     = self._vendor_input.value.strip()
        ctype      = self._type_sel.value

        threading.Thread(
            target=self._run_scan,
            args=(file_bytes, filename, vendor, ctype),
            daemon=True,
        ).start()

    def _run_scan(self, file_bytes: bytes, filename: str, vendor: str, ctype: str):
        try:
            from lex import scan_contract
            result = scan_contract(file_bytes, filename, vendor, ctype)
            self._result   = result
            self._filename = filename
            pn.state.execute(lambda: self._render_result(result))
        except Exception as e:
            pn.state.execute(lambda: self._show_error(str(e)))
        finally:
            pn.state.execute(lambda: setattr(self._scan_btn, "disabled", False))

    def _show_error(self, msg: str):
        self._status_md.object = f"❌ {msg}"

    def _render_result(self, result: dict):
        clauses   = result.get("_clauses", {})
        flags     = json.loads(result.get("clause_flags") or "{}")
        actions   = json.loads(result.get("required_actions") or "[]")
        score     = result.get("risk_score", 0)
        level     = result.get("risk_level", "Unknown")
        summary   = result.get("risk_summary", "")
        missing   = result.get("missing_clauses", "")
        vendor    = result.get("vendor_name") or "—"
        filename  = result.get("filename", "")

        # ── Result header ─────────────────────────────────────────────────────
        color = RISK_COLOR.get(level, DIM)
        header = (
            f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:12px;"
            f"padding:20px 24px;margin-bottom:14px'>"
            f"<div style='display:flex;align-items:flex-start;gap:24px;flex-wrap:wrap'>"
            f"<div style='flex:1;min-width:200px'>"
            f"<div style='font-size:18px;font-weight:700;color:{NAVY}'>{filename}</div>"
            f"<div style='font-size:12px;color:{DIM};margin-top:2px'>"
            f"Vendor: {vendor} &nbsp;·&nbsp; Type: {result.get('contract_type','—')} "
            f"&nbsp;·&nbsp; Scanned: {datetime.now().strftime('%Y-%m-%d')}</div>"
            f"</div>"
            f"<div style='min-width:280px'>{_risk_gauge(score, level)}</div>"
            f"</div>"
            f"</div>"
        )

        # ── Executive summary ─────────────────────────────────────────────────
        exec_html = ""
        if summary:
            exec_html = (
                f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:10px;"
                f"padding:14px 18px;margin-bottom:14px'>"
                f"<div style='font-size:11px;font-weight:700;color:{NAVY};text-transform:uppercase;"
                f"letter-spacing:1px;margin-bottom:6px'>Contract Summary</div>"
                f"<div style='font-size:13px;color:{TEXT};line-height:1.6'>{summary}</div>"
                f"</div>"
            )

        # ── Clause Explorer ───────────────────────────────────────────────────
        clause_rows = ""
        detail_map = {
            "liability_cap":      clauses.get("liability_cap"),
            "price_adjustment":   clauses.get("price_adjustment"),
            "termination_rights": clauses.get("termination_rights"),
            "sla_terms":          clauses.get("sla_terms"),
            "jurisdiction":       clauses.get("jurisdiction"),
            "payment_terms":      clauses.get("payment_terms"),
        }
        for key, label in CLAUSE_LABELS.items():
            val   = result.get(key) if key in result else clauses.get(key)
            color_key = flags.get(key, "green")
            detail = detail_map.get(key, "")
            clause_rows += _clause_row(label, val, color_key, detail or "")

        # Missing clauses
        missing_html = ""
        if missing:
            items = "".join(
                f"<span style='display:inline-block;background:#FFF0F0;border:1px solid {RED}44;"
                f"border-radius:4px;padding:2px 8px;font-size:11px;color:{RED};"
                f"margin:2px'>{c.strip()}</span>"
                for c in missing.split(",") if c.strip()
            )
            missing_html = (
                f"<div style='padding:10px 0;border-bottom:1px solid {BORDER}'>"
                f"<div style='font-size:11px;font-weight:700;color:{RED};margin-bottom:6px'>"
                f"MISSING CLAUSES</div>{items}</div>"
            )

        clauses_card = (
            f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:10px;"
            f"padding:16px 20px;margin-bottom:14px'>"
            f"<div style='font-size:11px;font-weight:700;color:{NAVY};text-transform:uppercase;"
            f"letter-spacing:1px;margin-bottom:10px'>Clause Explorer</div>"
            + missing_html
            + clause_rows
            + "</div>"
        )

        # ── Required actions ──────────────────────────────────────────────────
        actions_html = ""
        if actions:
            critical = [a for a in actions if a.startswith("[CRITICAL]") or a.startswith("[MISSING]")]
            review   = [a for a in actions if a.startswith("[REVIEW]")]

            def _action_items(items, color):
                return "".join(
                    f"<li style='margin-bottom:6px;font-size:13px;color:{TEXT};line-height:1.5'>"
                    f"<span style='color:{color};font-weight:700'>"
                    f"{items[i][:items[i].index(']')+1]}</span>"
                    f"{items[i][items[i].index(']')+1:]}</li>"
                    for i in range(len(items))
                )

            actions_html = (
                f"<div style='background:#FFF8E1;border:1px solid {YELLOW}44;"
                f"border-radius:10px;padding:16px 20px;margin-bottom:14px'>"
                f"<div style='font-size:11px;font-weight:700;color:{YELLOW};text-transform:uppercase;"
                f"letter-spacing:1px;margin-bottom:10px'>Required Actions</div>"
                f"<ul style='margin:0;padding-left:18px'>"
                + _action_items(critical, RED)
                + _action_items(review, YELLOW)
                + "</ul></div>"
            )

        self._clause_pane.object  = header + exec_html
        self._report_pane.object  = clauses_card + actions_html
        self._save_btn.disabled   = False
        self._status_md.object    = f"✅ Scan complete — **{filename}** · Risk: **{level}** ({score}/10)"

    def _on_save(self, event):
        if not self._result:
            return
        try:
            from modules.database import get_connection, init_database
            from lex import save_contract
            init_database(self.client_name)
            conn = get_connection(self.client_name)
            contract_id = save_contract(conn, self._result)
            conn.close()
            self._save_btn.disabled = True
            self._status_md.object = f"✅ Contract saved to SpendLens — ID #{contract_id}"
            self._load_history()
        except Exception as e:
            self._status_md.object = f"❌ Save failed: {e}"

    def _load_history(self):
        try:
            from modules.database import get_connection, get_contracts, init_database
            init_database(self.client_name)
            conn = get_connection(self.client_name)
            df = get_contracts(conn)
            conn.close()
        except Exception:
            self._history_pane.object = ""
            return

        if df.empty:
            self._history_pane.object = (
                f"<div style='color:{DIM};font-size:13px;padding:16px'>No contracts scanned yet.</div>"
            )
            return

        rows = ""
        for _, row in df.iterrows():
            level = row.get("risk_level") or "Unknown"
            color = RISK_COLOR.get(level, DIM)
            score = row.get("risk_score") or 0
            end   = row.get("end_date") or "—"
            vendor = row.get("vendor_name") or "—"
            fname = row.get("filename") or "—"
            ctype = row.get("contract_type") or "—"
            scanned = (row.get("scanned_at") or "")[:10]
            rows += (
                f"<tr style='border-bottom:1px solid {BORDER}'>"
                f"<td style='padding:8px 10px;font-size:12px;color:{TEXT}'>{vendor}</td>"
                f"<td style='padding:8px 10px;font-size:12px;color:{DIM}'>{ctype}</td>"
                f"<td style='padding:8px 10px;font-size:12px;color:{DIM}'>{end}</td>"
                f"<td style='padding:8px 10px;text-align:center'>"
                f"<span style='font-size:13px;font-weight:700;color:{color}'>{score:.1f} {level}</span>"
                f"</td>"
                f"<td style='padding:8px 10px;font-size:11px;color:{DIM}'>{scanned}</td>"
                f"</tr>"
            )

        self._history_pane.object = (
            f"<div style='background:{CARD};border:1px solid {BORDER};border-radius:10px;"
            f"padding:16px 20px'>"
            f"<div style='font-size:11px;font-weight:700;color:{NAVY};text-transform:uppercase;"
            f"letter-spacing:1px;margin-bottom:12px'>Contract History ({len(df)} scanned)</div>"
            f"<table style='width:100%;border-collapse:collapse'>"
            f"<thead><tr>"
            f"<th style='text-align:left;font-size:11px;color:{DIM};padding:4px 10px'>Vendor</th>"
            f"<th style='text-align:left;font-size:11px;color:{DIM};padding:4px 10px'>Type</th>"
            f"<th style='text-align:left;font-size:11px;color:{DIM};padding:4px 10px'>Expiry</th>"
            f"<th style='text-align:center;font-size:11px;color:{DIM};padding:4px 10px'>Risk</th>"
            f"<th style='text-align:left;font-size:11px;color:{DIM};padding:4px 10px'>Scanned</th>"
            f"</tr></thead><tbody>{rows}</tbody></table></div>"
        )

    def view(self) -> pn.viewable.Viewable:
        def _label(text):
            return pn.pane.HTML(
                f"<div style='font-size:10px;color:{DIM};font-weight:700;"
                f"text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px'>{text}</div>"
            )

        # ── Header ────────────────────────────────────────────────────────────
        header = pn.pane.HTML(
            f"<div style='background:{NAVY};border-radius:12px;padding:20px 28px;"
            f"margin-bottom:20px;display:flex;align-items:center;gap:16px'>"
            f"<div>"
            f"<div style='font-size:22px;font-weight:800;color:#fff'>📄 Lex — Contract Review</div>"
            f"<div style='font-size:13px;color:rgba(255,255,255,0.7);margin-top:2px'>"
            f"AI clause extraction · Risk flagging · Playbook compliance · Renewal tracking</div>"
            f"</div></div>",
            sizing_mode="stretch_width",
        )

        # ── Upload form ───────────────────────────────────────────────────────
        upload_row = pn.Row(
            pn.Column(_label("Contract File (PDF / DOCX)"), self._file_input),
            pn.Column(_label("Vendor Name"), self._vendor_input),
            pn.Column(_label("Contract Type"), self._type_sel),
            align="start", margin=(0, 0, 16, 0),
        )
        btn_row = pn.Row(
            self._scan_btn, self._save_btn, self._status_md,
            align="center", margin=(0, 0, 20, 0),
        )

        form_section = pn.Column(
            upload_row, btn_row,
            pn.layout.Divider(margin=(4, 0, 20, 0)),
            self._clause_pane,
            self._report_pane,
            sizing_mode="stretch_width",
            stylesheets=[f"""
                :host {{
                    background:{CARD};border:1px solid {BORDER};
                    border-radius:12px;padding:22px 26px;
                }}
            """],
        )

        return pn.Column(
            header,
            form_section,
            pn.layout.Divider(margin=(20, 0, 16, 0)),
            self._history_pane,
            sizing_mode="stretch_width",
            margin=(16, 24),
        )
