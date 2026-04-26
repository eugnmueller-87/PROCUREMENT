"""
SpendLens — AI-Powered Procurement Intelligence Dashboard
=========================================================
Run with:
    panel serve app.py --show --autoreload

Or for development:
    python app.py
"""

import panel as pn
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import io
import os
import threading
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ── Load environment variables ──────────────────────────────────────────────
load_dotenv()
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Module imports ───────────────────────────────────────────────────────────
from modules.column_mapper   import rule_based_mapping, ai_column_mapping, apply_mapping
from modules.data_cleanup    import full_cleanup
from modules.category_mapper import run_category_mapping
from modules.flag_engine     import run_flag_engine
from modules.database        import (init_database, get_connection, log_upload,
                                      insert_raw_transactions, insert_enriched_transactions,
                                      bulk_upsert_vendors, get_full_transaction_view)
from modules.cfo_reports     import export_cfo_excel

# ── Initialize database ──────────────────────────────────────────────────────
init_database("default")

# ── Panel extensions ─────────────────────────────────────────────────────────
pn.extension("plotly", "tabulator", sizing_mode="stretch_width")

# ─────────────────────────────────────────────────────────────────────────────
# THEME — Navy / White Enterprise
# ─────────────────────────────────────────────────────────────────────────────
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
WHITE  = "#FFFFFF"

COLORS = [NAVY, NAVY2, "#1A7A4A", "#B8860B", "#C0392B",
          "#5B8DB8", "#2ECC71", "#E67E22", "#9B59B6", "#1ABC9C"]

RISK_COLORS = {"Critical": RED, "High": YELLOW, "Medium": "#E67E22", "Low": GREEN}

LAYOUT = dict(
    paper_bgcolor=BG,
    plot_bgcolor=CARD,
    font=dict(family="Georgia, serif", color=TEXT, size=12),
    margin=dict(l=60, r=30, t=50, b=40),
    xaxis=dict(gridcolor=BORDER, linecolor=BORDER, showgrid=True),
    yaxis=dict(gridcolor=BORDER, linecolor=BORDER, showgrid=True),
    legend=dict(bgcolor="rgba(255,255,255,0.9)", font=dict(size=10),
                bordercolor=BORDER, borderwidth=1),
)

CSS = f"""
body, .bk-root {{
    background-color: {BG} !important;
    color: {TEXT} !important;
    font-family: 'Georgia', serif !important;
}}
.pn-loading-spinner {{
    border-color: {NAVY} !important;
}}
.bk-btn-success {{
    background-color: {NAVY} !important;
    border-color: {NAVY} !important;
}}
.fast-list-header {{
    background: {NAVY} !important;
}}
"""
pn.config.raw_css.append(CSS)

# ─────────────────────────────────────────────────────────────────────────────
# DEFAULT DATA — Parloa SaaS Taxonomy
# ─────────────────────────────────────────────────────────────────────────────
YEARS = [2022, 2023, 2024, 2025, 2026]

CATEGORIES_RAW = [
    {"name": "Cloud & Compute",       "spend": [4200, 7800, 12500, 17800, 24000],
     "budget": 22000, "concentration": 72, "risk": "Critical", "single_source": True,
     "suppliers": "AWS, Google Cloud, Azure", "lead_time_days": 0,
     "contract_end": "2026-09", "capex_opex": "Opex", "region": "US",
     "po_coverage_pct": 95, "contract_coverage_pct": 90},
    {"name": "AI/ML APIs & Data",     "spend": [800, 2200, 4800, 6500, 9200],
     "budget": 8500, "concentration": 55, "risk": "High", "single_source": False,
     "suppliers": "OpenAI, Anthropic, Scale AI", "lead_time_days": 14,
     "contract_end": "2026-06", "capex_opex": "Opex", "region": "US",
     "po_coverage_pct": 80, "contract_coverage_pct": 75},
    {"name": "IT Software & SaaS",    "spend": [900, 1400, 2200, 3100, 4200],
     "budget": 4000, "concentration": 22, "risk": "Low", "single_source": False,
     "suppliers": "GitHub, Datadog, Atlassian", "lead_time_days": 7,
     "contract_end": "Various", "capex_opex": "Opex", "region": "Global",
     "po_coverage_pct": 85, "contract_coverage_pct": 88},
    {"name": "Telecom & Voice",       "spend": [400, 800, 1400, 2200, 3000],
     "budget": 2800, "concentration": 65, "risk": "Critical", "single_source": True,
     "suppliers": "Twilio, Vonage, DT", "lead_time_days": 30,
     "contract_end": "2026-07", "capex_opex": "Opex", "region": "US",
     "po_coverage_pct": 92, "contract_coverage_pct": 95},
    {"name": "Recruitment & HR",      "spend": [600, 1100, 2400, 4200, 6800],
     "budget": 6500, "concentration": 35, "risk": "High", "single_source": False,
     "suppliers": "Personio, LinkedIn, Agencies", "lead_time_days": 45,
     "contract_end": "2026-12", "capex_opex": "Opex", "region": "DACH",
     "po_coverage_pct": 60, "contract_coverage_pct": 70},
    {"name": "Professional Services", "spend": [400, 700, 1200, 2100, 3200],
     "budget": 3000, "concentration": 40, "risk": "Medium", "single_source": False,
     "suppliers": "Big 4, Baker McKenzie", "lead_time_days": 21,
     "contract_end": "2026-03", "capex_opex": "Opex", "region": "DACH",
     "po_coverage_pct": 55, "contract_coverage_pct": 65},
    {"name": "Marketing & Campaigns", "spend": [300, 800, 1800, 3500, 5500],
     "budget": 5000, "concentration": 28, "risk": "Medium", "single_source": False,
     "suppliers": "Event Agencies, Google Ads", "lead_time_days": 30,
     "contract_end": "Various", "capex_opex": "Opex", "region": "DACH",
     "po_coverage_pct": 45, "contract_coverage_pct": 55},
    {"name": "Facilities & Office",   "spend": [500, 900, 1500, 2800, 4800],
     "budget": 4500, "concentration": 45, "risk": "High", "single_source": False,
     "suppliers": "ISS, Lyreco, Catering", "lead_time_days": 90,
     "contract_end": "2028-06", "capex_opex": "Opex", "region": "DACH",
     "po_coverage_pct": 70, "contract_coverage_pct": 80},
    {"name": "Real Estate",           "spend": [1200, 1800, 2400, 3200, 4200],
     "budget": 4000, "concentration": 80, "risk": "High", "single_source": True,
     "suppliers": "WeWork, Office Landlords", "lead_time_days": 180,
     "contract_end": "2028-12", "capex_opex": "Opex", "region": "DACH",
     "po_coverage_pct": 100, "contract_coverage_pct": 100},
    {"name": "Hardware & Equipment",  "spend": [300, 500, 900, 1500, 2400],
     "budget": 2200, "concentration": 38, "risk": "Medium", "single_source": False,
     "suppliers": "Apple, Dell, NVIDIA", "lead_time_days": 56,
     "contract_end": "N/A", "capex_opex": "Capex", "region": "DACH",
     "po_coverage_pct": 90, "contract_coverage_pct": 60},
    {"name": "Travel & Expenses",     "spend": [200, 500, 1100, 2000, 3200],
     "budget": 3000, "concentration": 30, "risk": "Low", "single_source": False,
     "suppliers": "Lufthansa, Navan, Hotels", "lead_time_days": 3,
     "contract_end": "2026-09", "capex_opex": "Opex", "region": "DACH",
     "po_coverage_pct": 40, "contract_coverage_pct": 50},
]

EBITDA_DATA = [
    {"Initiative": "Cloud Cost Optimisation",    "Type": "Savings",        "Impact €K": 420, "Status": "Realised"},
    {"Initiative": "SaaS License Consolidation", "Type": "Savings",        "Impact €K": 280, "Status": "Realised"},
    {"Initiative": "Recruitment Agency Rebid",   "Type": "Savings",        "Impact €K": 350, "Status": "In Progress"},
    {"Initiative": "Telco Contract Renewal",     "Type": "Savings",        "Impact €K": 180, "Status": "Planned"},
    {"Initiative": "AWS Reserved Instances",     "Type": "Cost Avoidance", "Impact €K": 400, "Status": "Realised"},
    {"Initiative": "Hardware Bulk Purchase",     "Type": "Cost Avoidance", "Impact €K": 320, "Status": "In Progress"},
]

CONTRACTS_DATA = [
    {"Category": "AI/ML APIs & Data",     "Supplier": "OpenAI",          "Value €K": 2800, "Expiry": "2026-06-30", "Risk": "High"},
    {"Category": "Professional Services", "Supplier": "Deloitte",        "Value €K": 1200, "Expiry": "2026-03-31", "Risk": "Critical"},
    {"Category": "Telecom & Voice",       "Supplier": "Twilio",          "Value €K": 2200, "Expiry": "2026-07-31", "Risk": "Critical"},
    {"Category": "Cloud & Compute",       "Supplier": "AWS",             "Value €K": 18000, "Expiry": "2026-09-30", "Risk": "High"},
    {"Category": "Travel & Expenses",     "Supplier": "BCD Travel",      "Value €K": 800,  "Expiry": "2026-09-30", "Risk": "Medium"},
    {"Category": "Recruitment & HR",      "Supplier": "Hays",            "Value €K": 1500, "Expiry": "2026-12-31", "Risk": "Medium"},
    {"Category": "IT Software & SaaS",    "Supplier": "Datadog",         "Value €K": 600,  "Expiry": "2027-01-31", "Risk": "Low"},
    {"Category": "Facilities & Office",   "Supplier": "ISS Deutschland", "Value €K": 1800, "Expiry": "2028-06-30", "Risk": "Low"},
    {"Category": "Real Estate",           "Supplier": "WeWork GmbH",     "Value €K": 3200, "Expiry": "2028-12-31", "Risk": "Low"},
    {"Category": "Hardware & Equipment",  "Supplier": "Dell",            "Value €K": 900,  "Expiry": "N/A",        "Risk": "Low"},
]


def build_default_data():
    spend_rows = []
    for cat in CATEGORIES_RAW:
        for i, year in enumerate(YEARS):
            spend_rows.append({"category": cat["name"], "year": year, "spend": cat["spend"][i]})

    meta_rows = [{
        "category":             c["name"],
        "spend_2026e":          c["spend"][4],
        "spend_2025":           c["spend"][3],
        "budget_2026e":         c["budget"],
        "budget_variance":      c["spend"][4] - c["budget"],
        "concentration":        c["concentration"],
        "risk":                 c["risk"],
        "single_source":        c["single_source"],
        "suppliers":            c["suppliers"],
        "lead_time_days":       c["lead_time_days"],
        "contract_end":         c["contract_end"],
        "capex_opex":           c["capex_opex"],
        "region":               c["region"],
        "po_coverage_pct":      c["po_coverage_pct"],
        "contract_coverage_pct": c["contract_coverage_pct"],
        "cagr":                 round(((c["spend"][4] / c["spend"][0]) ** (1/4) - 1) * 100, 1),
    } for c in CATEGORIES_RAW]

    return pd.DataFrame(spend_rows), pd.DataFrame(meta_rows), \
           pd.DataFrame(EBITDA_DATA), pd.DataFrame(CONTRACTS_DATA)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
def traffic_color(value, target, lower_is_better=False):
    ratio = value / target if target else 1
    if lower_is_better:
        return RED if ratio > 1.5 else YELLOW if ratio > 1.0 else GREEN
    return GREEN if ratio >= 0.95 else YELLOW if ratio >= 0.75 else RED


def section_header(title: str) -> pn.pane.HTML:
    return pn.pane.HTML(f"""
    <h3 style="color:{NAVY}; margin:24px 0 8px 0; font-family:Georgia,serif;
               font-size:18px; border-bottom:2px solid {NAVY}; padding-bottom:8px;">
        {title}
    </h3>""", sizing_mode="stretch_width")


# ─────────────────────────────────────────────────────────────────────────────
# KPI CARDS
# ─────────────────────────────────────────────────────────────────────────────
def kpi_card(title, value, subtitle="", color=NAVY, clickable=False):
    cursor = "pointer" if clickable else "default"
    border = f"2px solid {color}" if clickable else f"1px solid {BORDER}"
    return pn.pane.HTML(f"""
    <div style="background:{WHITE}; border-radius:10px; padding:20px 16px;
                text-align:center; border:{border}; cursor:{cursor};
                box-shadow:0 2px 8px rgba(27,58,107,0.08); min-width:150px;">
        <div style="color:{DIM}; font-size:11px; text-transform:uppercase;
                    letter-spacing:1.5px; font-family:Georgia,serif;">{title}</div>
        <div style="color:{color}; font-size:30px; font-weight:700;
                    margin:10px 0 6px 0; font-family:Georgia,serif;">{value}</div>
        <div style="color:{DIM}; font-size:11px;">{subtitle}</div>
    </div>""", sizing_mode="stretch_width")


# ─────────────────────────────────────────────────────────────────────────────
# BATTERY DIAGRAMS
# ─────────────────────────────────────────────────────────────────────────────
def vertical_battery(title, value, target, lower_is_better=False):
    color = traffic_color(value, target, lower_is_better)
    fill_pct = min(100, (value / target * 100)) if not lower_is_better \
               else max(0, 100 - (value / target * 100))
    return pn.pane.HTML(f"""
    <div style="text-align:center; padding:16px; background:{WHITE};
                border:1px solid {BORDER}; border-radius:10px; min-width:140px;
                box-shadow:0 2px 8px rgba(27,58,107,0.06);">
        <div style="font-size:12px; color:{DIM}; margin-bottom:12px;
                    font-family:Georgia,serif; text-transform:uppercase;
                    letter-spacing:1px;">{title}</div>
        <div style="width:44px; height:110px; border:3px solid {color};
                    border-radius:6px; margin:0 auto; position:relative;
                    background:{CARD};">
            <div style="position:absolute; bottom:0; left:0; right:0;
                        height:{fill_pct}%; background:{color};
                        border-radius:3px; opacity:0.85;"></div>
            <div style="position:absolute; top:-10px; left:50%;
                        transform:translateX(-50%); width:16px; height:6px;
                        background:{color}; border-radius:2px 2px 0 0;"></div>
        </div>
        <div style="font-size:24px; font-weight:700; color:{color};
                    margin-top:12px; font-family:Georgia,serif;">{value}%</div>
        <div style="font-size:11px; color:{DIM};">target {target}%</div>
    </div>""", sizing_mode="stretch_width")


# ─────────────────────────────────────────────────────────────────────────────
# CHARTS
# ─────────────────────────────────────────────────────────────────────────────
def chart_spend_stacked(df_spend):
    fig = go.Figure()
    cats = df_spend.groupby("category")["spend"].sum().sort_values().index
    for i, cat in enumerate(cats):
        d = df_spend[df_spend["category"] == cat]
        fig.add_trace(go.Scatter(
            x=d["year"], y=d["spend"], name=cat[:22],
            mode="lines", stackgroup="one",
            line=dict(width=0.5, color=COLORS[i % len(COLORS)]),
            fillcolor=COLORS[i % len(COLORS)],
        ))
    fig.update_layout(title="Spend Evolution by Category (€K)",
                      **LAYOUT, height=400, yaxis_title="Spend (€K)")
    return fig


def chart_category_bars(df_meta):
    df = df_meta.sort_values("spend_2026e", ascending=True).copy()
    over = df["budget_variance"] > 0
    colors = [RED if o else NAVY for o in over]
    fig = go.Figure(go.Bar(
        y=df["category"], x=df["spend_2026e"], orientation="h",
        marker_color=colors,
        text=[f"€{v:,.0f}K" for v in df["spend_2026e"]],
        textposition="outside",
        customdata=df["budget_variance"],
        hovertemplate="<b>%{y}</b><br>Spend: €%{x:,.0f}K<br>Variance: €%{customdata:,.0f}K<extra></extra>",
    ))
    fig.update_layout(title="2026E Spend vs Budget (red = over budget)",
                      **LAYOUT, height=420, xaxis_title="Spend (€K)")
    return fig


def chart_risk_bubble(df_meta):
    fig = go.Figure()
    for _, row in df_meta.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["concentration"]], y=[row["spend_2026e"]],
            mode="markers+text",
            marker=dict(size=max(row["lead_time_days"] * 0.3 + 18, 18),
                        color=RISK_COLORS.get(row["risk"], DIM), opacity=0.75,
                        line=dict(color=WHITE, width=2)),
            text=[row["category"][:16]],
            textposition="top center",
            textfont=dict(size=9, color=TEXT),
            name=row["category"],
            customdata=[[row["category"], row["risk"], row["lead_time_days"],
                         row.get("suppliers", "")]],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Risk: %{customdata[1]}<br>"
                "Concentration: %{x}%%<br>"
                "Spend: €%{y:,.0f}K<br>"
                "Lead Time: %{customdata[2]}d<extra></extra>"
            ),
        ))
    fig.add_shape(type="rect", x0=50, x1=100, y0=0, y1=df_meta["spend_2026e"].max() * 1.1,
                  fillcolor="rgba(192,57,43,0.05)",
                  line=dict(color="rgba(192,57,43,0.3)", dash="dot"))
    fig.add_annotation(x=75, y=df_meta["spend_2026e"].max() * 1.0,
                       text="⚠ HIGH RISK ZONE", showarrow=False,
                       font=dict(size=11, color=RED))
    fig.update_layout(
        title="Risk Map — Concentration vs Spend (bubble size = lead time)",
        **LAYOUT, height=500, showlegend=False,
        xaxis_title="Supplier Concentration (%)",
        yaxis_title="2026E Spend (€K)",
    )
    return fig


def chart_ebitda_waterfall(df_ebitda):
    items = df_ebitda.copy()
    total = items["Impact €K"].sum()
    x_labels = list(items["Initiative"]) + ["Total Impact"]
    y_values = list(items["Impact €K"]) + [total]
    measure = ["relative"] * len(items) + ["total"]
    colors_wf = [GREEN if t == "Savings" else NAVY2 for t in items["Type"]] + [GREEN]

    fig = go.Figure(go.Waterfall(
        x=x_labels, y=y_values, measure=measure,
        connector=dict(line=dict(color=BORDER, width=1)),
        increasing=dict(marker_color=GREEN),
        decreasing=dict(marker_color=RED),
        totals=dict(marker_color=NAVY),
        text=[f"€{v:,.0f}K" for v in y_values],
        textposition="outside",
    ))
    fig.update_layout(title="EBITDA Impact Waterfall (€K)",
                      **LAYOUT, height=420, yaxis_title="Impact (€K)")
    return fig


def chart_treemap(df_meta):
    df = df_meta.copy()
    df["label"] = df.apply(
        lambda r: f"{r['category']}<br>€{r['spend_2026e']:,.0f}K", axis=1)
    fig = px.treemap(
        df, path=["label"], values="spend_2026e",
        color="concentration",
        color_continuous_scale=[[0, GREEN], [0.5, YELLOW], [1, RED]],
        range_color=[0, 80],
    )
    fig.update_layout(
        title="Spend by Category (size) × Concentration (color)",
        paper_bgcolor=BG, font=dict(color=TEXT, family="Georgia,serif"),
        height=450,
        coloraxis_colorbar=dict(title="Concentration %"),
    )
    fig.update_traces(textfont=dict(size=13))
    return fig


def chart_cagr(df_meta):
    df = df_meta.sort_values("cagr", ascending=True)
    colors = [GREEN if v < 20 else YELLOW if v < 40 else RED for v in df["cagr"]]
    fig = go.Figure(go.Bar(
        y=df["category"], x=df["cagr"], orientation="h",
        marker_color=colors,
        text=[f"{v:.1f}%" for v in df["cagr"]],
        textposition="outside",
    ))
    fig.update_layout(title="Category CAGR 2022→2026E",
                      **LAYOUT, height=420, xaxis_title="CAGR %")
    return fig


def chart_capex_opex(df_spend, df_meta):
    merged = df_spend[df_spend["year"] == 2026].merge(
        df_meta[["category", "capex_opex"]], on="category", how="left")
    summary = merged.groupby("capex_opex")["spend"].sum().reset_index()
    fig = go.Figure(go.Pie(
        labels=summary["capex_opex"], values=summary["spend"],
        marker_colors=[NAVY, GREEN],
        textinfo="label+percent+value",
        hovertemplate="%{label}: €%{value:,.0f}K<extra></extra>",
    ))
    fig.update_layout(title="Capex vs Opex Split 2026E",
                      paper_bgcolor=BG, font=dict(color=TEXT, family="Georgia,serif"),
                      height=380)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# TABLES
# ─────────────────────────────────────────────────────────────────────────────
def render_contracts_table(df_contracts):
    def risk_badge(risk):
        c = {"Critical": RED, "High": YELLOW, "Medium": "#E67E22", "Low": GREEN}.get(risk, DIM)
        return f'<span style="background:{c}; color:white; padding:2px 8px; border-radius:4px; font-size:11px;">{risk}</span>'

    rows = ""
    for _, row in df_contracts.iterrows():
        badge = risk_badge(row["Risk"])
        rows += f"""<tr style="border-bottom:1px solid {BORDER};">
            <td style="padding:8px 12px; color:{TEXT};">{row['Category']}</td>
            <td style="padding:8px 12px; color:{TEXT};">{row['Supplier']}</td>
            <td style="padding:8px 12px; color:{TEXT}; text-align:right;">€{row['Value €K']:,}K</td>
            <td style="padding:8px 12px; color:{TEXT};">{row['Expiry']}</td>
            <td style="padding:8px 12px;">{badge}</td>
        </tr>"""

    html = f"""
    <div style="background:{WHITE}; border:1px solid {BORDER}; border-radius:10px;
                overflow:hidden; margin-top:8px;">
        <table style="width:100%; border-collapse:collapse;">
            <thead>
                <tr style="background:{NAVY}; color:{WHITE};">
                    <th style="padding:10px 12px; text-align:left;">Category</th>
                    <th style="padding:10px 12px; text-align:left;">Supplier</th>
                    <th style="padding:10px 12px; text-align:right;">Value</th>
                    <th style="padding:10px 12px; text-align:left;">Expiry</th>
                    <th style="padding:10px 12px; text-align:left;">Risk</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>"""
    return pn.pane.HTML(html, sizing_mode="stretch_width")


def render_ebitda_table(df_ebitda):
    rows = ""
    for _, row in df_ebitda.iterrows():
        color = GREEN if row["Type"] == "Savings" else NAVY2
        status_color = GREEN if row["Status"] == "Realised" else YELLOW if row["Status"] == "In Progress" else DIM
        rows += f"""<tr style="border-bottom:1px solid {BORDER};">
            <td style="padding:8px 12px; color:{TEXT};">{row['Initiative']}</td>
            <td style="padding:8px 12px; color:{color}; font-weight:600;">{row['Type']}</td>
            <td style="padding:8px 12px; color:{GREEN}; text-align:right; font-weight:600;">
                €{row['Impact €K']:,}K</td>
            <td style="padding:8px 12px; color:{status_color};">{row['Status']}</td>
        </tr>"""

    total = df_ebitda["Impact €K"].sum()
    html = f"""
    <div style="background:{WHITE}; border:1px solid {BORDER}; border-radius:10px;
                overflow:hidden; margin-top:8px;">
        <table style="width:100%; border-collapse:collapse;">
            <thead>
                <tr style="background:{NAVY}; color:{WHITE};">
                    <th style="padding:10px 12px; text-align:left;">Initiative</th>
                    <th style="padding:10px 12px; text-align:left;">Type</th>
                    <th style="padding:10px 12px; text-align:right;">Impact</th>
                    <th style="padding:10px 12px; text-align:left;">Status</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
            <tfoot>
                <tr style="background:{CARD}; font-weight:700;">
                    <td colspan="2" style="padding:10px 12px; color:{NAVY};">Total EBITDA Impact</td>
                    <td style="padding:10px 12px; color:{GREEN}; text-align:right;">€{total:,}K</td>
                    <td></td>
                </tr>
            </tfoot>
        </table>
    </div>"""
    return pn.pane.HTML(html, sizing_mode="stretch_width")


# ─────────────────────────────────────────────────────────────────────────────
# LOGO SVG
# ─────────────────────────────────────────────────────────────────────────────
LOGO_SVG = f"""
<svg width="44" height="44" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <polygon points="100,4 182,52 182,148 100,196 18,148 18,52"
           fill="none" stroke="white" stroke-width="8"/>
  <line x1="100" y1="4"   x2="100" y2="100" stroke="white" stroke-width="3" opacity="0.5"/>
  <line x1="182" y1="52"  x2="100" y2="100" stroke="white" stroke-width="3" opacity="0.5"/>
  <line x1="182" y1="148" x2="100" y2="100" stroke="white" stroke-width="3" opacity="0.5"/>
  <line x1="100" y1="196" x2="100" y2="100" stroke="white" stroke-width="3" opacity="0.5"/>
  <line x1="18"  y1="148" x2="100" y2="100" stroke="white" stroke-width="3" opacity="0.5"/>
  <line x1="18"  y1="52"  x2="100" y2="100" stroke="white" stroke-width="3" opacity="0.5"/>
  <path d="M55,100 Q100,60 145,100 Q100,140 55,100 Z"
        fill="none" stroke="#1A7A4A" stroke-width="6"/>
  <circle cx="100" cy="97" r="18" fill="none" stroke="#1A7A4A" stroke-width="5"/>
  <circle cx="100" cy="94" r="8" fill="#1A7A4A"/>
</svg>"""


# ─────────────────────────────────────────────────────────────────────────────
# UPLOAD PIPELINE
# ─────────────────────────────────────────────────────────────────────────────
def run_pipeline(filename: str, file_bytes: bytes,
                 status_callback, dashboard_callback):
    """
    Full pipeline run in a background thread so UI stays responsive.

    Steps:
    1. Read file
    2. Column mapping
    3. Data cleanup
    4. Category mapping (AI)
    5. Flag engine
    6. Database storage
    7. Dashboard update
    """
    try:
        # Step 1: Read
        status_callback("📂 Reading file...")
        raw = io.BytesIO(file_bytes)
        df = pd.read_csv(raw) if filename.endswith(".csv") else pd.read_excel(raw)
        status_callback(f"📂 Loaded **{filename}** — {len(df)} rows × {len(df.columns)} cols")

        # Step 2: Column mapping
        status_callback("🔍 Mapping columns...")
        mapping = rule_based_mapping(list(df.columns))
        unknowns = [k for k, v in mapping.items() if v is None]
        if unknowns and API_KEY:
            sample = df.head(3).to_dict("records")
            mapping = ai_column_mapping(list(df.columns), sample, API_KEY)
        df = apply_mapping(df, mapping)
        status_callback(f"🔍 Columns mapped — {len([v for v in mapping.values() if v])} fields recognized")

        # Step 3: Data cleanup
        status_callback("🧹 Cleaning data...")
        df, report = full_cleanup(df)
        dupes = report.get("duplicates_removed", 0)
        rows = report.get("rows_remaining", len(df))
        status_callback(f"🧹 Cleaned — {rows} rows remaining, {dupes} duplicates removed")

        # Step 4: Category mapping
        status_callback("🤖 Classifying vendors with AI...")
        desc_col = next((c for c in df.columns if "description" in c.lower()), None)
        enriched_df, re_summary = run_category_mapping(
            df, vendor_col="supplier", description_col=desc_col,
            spend_col="spend", api_key=API_KEY
        )
        cats = enriched_df["category_mapped"].value_counts().to_dict()
        status_callback(f"🤖 Classified — {len(cats)} categories detected")

        # Step 5: Flag engine
        status_callback("🚩 Analysing compliance & risk flags...")
        flagged_df, coverage = run_flag_engine(enriched_df)
        maverick_count = int((flagged_df.get("maverick_flag", pd.Series()) == True).sum())
        shadow_count = int((flagged_df.get("shadow_it_flag", pd.Series()) == True).sum())
        status_callback(f"🚩 Flags — {maverick_count} maverick, {shadow_count} shadow IT")

        # Step 6: Database
        status_callback("💾 Saving to knowledge base...")
        conn = get_connection("default")
        upload_id = log_upload(conn, filename, "accounting", len(df),
                               {k: v for k, v in mapping.items() if v})
        insert_raw_transactions(conn, df, upload_id)
        insert_enriched_transactions(conn, df, flagged_df)
        conn.close()
        status_callback(f"💾 Saved to knowledge base")

        # Step 7: Update dashboard
        status_callback("📊 Updating dashboard...")
        dashboard_callback(flagged_df, filename)
        status_callback(f"✅ **Done** — {len(flagged_df)} rows processed from **{filename}**")

    except Exception as e:
        status_callback(f"❌ Pipeline error: {str(e)}")
        import traceback
        traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD STATE & WIDGETS
# ─────────────────────────────────────────────────────────────────────────────
df_spend, df_meta, df_ebitda, df_contracts = build_default_data()

# Widgets
year_select   = pn.widgets.Select(
    name="Year", options=["All years"] + [str(y) for y in YEARS],
    value="All years", width=240)
file_input    = pn.widgets.FileInput(accept=".csv,.xlsx,.xls", name="Upload spend data")
dataset_label = pn.pane.Markdown("",
                                  styles={"color": NAVY, "font-size": "13px"})
export_btn    = pn.widgets.Button(name="📥 Export CFO Report",
                                   button_type="primary", width=240)
icarus_btn    = pn.widgets.Button(name="🪶 Run Icarus Scan",
                                   button_type="success", width=240)
status_log    = pn.pane.Markdown("", styles={"color": DIM, "font-size": "12px"})

# Content panels
kpi_row      = pn.Row(sizing_mode="stretch_width")
detail_panel = pn.Column(sizing_mode="stretch_width")
chart_s1     = pn.Column(sizing_mode="stretch_width")
chart_s2     = pn.Column(sizing_mode="stretch_width")
chart_s3     = pn.Column(sizing_mode="stretch_width")
chart_s4     = pn.Column(sizing_mode="stretch_width")
chart_deep   = pn.Column(sizing_mode="stretch_width")
drill_panel  = pn.Column(sizing_mode="stretch_width")

data_preview = pn.widgets.Tabulator(
    df_meta[["category", "spend_2026e", "risk", "concentration", "contract_end"]],
    sizing_mode="stretch_width", height=320,
    theme="bootstrap", page_size=15,
)


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD UPDATE
# ─────────────────────────────────────────────────────────────────────────────
def update_dashboard(df_s=None, df_m=None, df_e=None, df_c=None, year_val=None):
    global df_spend, df_meta, df_ebitda, df_contracts
    if df_s is not None: df_spend    = df_s
    if df_m is not None: df_meta     = df_m
    if df_e is not None: df_ebitda   = df_e
    if df_c is not None: df_contracts = df_c
    if year_val is None: year_val = year_select.value

    # Filter by year
    if year_val != "All years":
        ds = df_spend[df_spend["year"] == int(year_val)].copy()
    else:
        ds = df_spend.copy()

    dm = df_meta.copy()
    total     = dm["spend_2026e"].sum()
    prev      = dm["spend_2025"].sum()
    yoy       = round((total - prev) / prev * 100, 1) if prev > 0 else 0
    ebitda    = df_ebitda["Impact €K"].sum()
    po_avg    = round(dm["po_coverage_pct"].mean())
    cc_avg    = round(dm["contract_coverage_pct"].mean())
    maverick  = 12
    spm_pct   = 60

    # ── KPI Cards ──
    kpi_row.clear()
    kpi_row.extend([
        kpi_card("Total Spend",       f"€{total/1000:.1f}M",   year_val),
        kpi_card("YoY Growth",        f"+{yoy:.0f}%",           "vs prior year",
                 RED if yoy > 30 else YELLOW if yoy > 15 else GREEN),
        kpi_card("EBITDA Impact",     f"€{ebitda:,}K",          "savings + avoidance",
                 GREEN, clickable=True),
        kpi_card("Contract Coverage", f"{cc_avg}%",             "target 100%",
                 traffic_color(cc_avg, 100), clickable=True),
        kpi_card("Maverick Spend",    f"{maverick}%",           "target 5%",
                 traffic_color(maverick, 5, lower_is_better=True), clickable=True),
    ])

    # ── Section 1: Spend Overview ──
    chart_s1.clear()
    chart_s1.extend([
        section_header("📊 Spend Overview"),
        pn.Row(
            pn.pane.Plotly(chart_spend_stacked(ds), sizing_mode="stretch_width"),
            pn.pane.Plotly(chart_category_bars(dm), sizing_mode="stretch_width"),
        ),
    ])

    # ── Section 2: Risk & Bottlenecks ──
    chart_s2.clear()
    chart_s2.extend([
        section_header("⚠ Risk & Bottlenecks"),
        pn.pane.Plotly(chart_risk_bubble(dm), sizing_mode="stretch_width"),
        drill_panel,
        section_header("📋 Expiring Contracts"),
        render_contracts_table(df_contracts),
    ])

    # ── Section 3: Procurement Health ──
    chart_s3.clear()
    chart_s3.extend([
        section_header("🏥 Procurement Health"),
        pn.Row(
            vertical_battery("PO Coverage",       po_avg,   100),
            vertical_battery("Contract Coverage", cc_avg,   100),
            vertical_battery("Maverick Spend",    maverick,   5, lower_is_better=True),
            vertical_battery("Spend Under Mgmt",  spm_pct,   80),
            sizing_mode="stretch_width",
        ),
    ])

    # ── Section 4: EBITDA Impact ──
    chart_s4.clear()
    chart_s4.extend([
        section_header("💶 EBITDA Impact"),
        pn.Row(
            pn.pane.Plotly(chart_ebitda_waterfall(df_ebitda), sizing_mode="stretch_width"),
            pn.pane.Plotly(chart_category_bars(dm),           sizing_mode="stretch_width"),
        ),
        render_ebitda_table(df_ebitda),
    ])

    # ── Deep Dive ──
    chart_deep.clear()
    chart_deep.extend([
        section_header("🔬 Deep Dive Analysis"),
        pn.Row(
            pn.pane.Plotly(chart_cagr(dm),             sizing_mode="stretch_width"),
            pn.pane.Plotly(chart_capex_opex(ds, dm),   sizing_mode="stretch_width"),
        ),
        pn.pane.Plotly(chart_treemap(dm), sizing_mode="stretch_width"),
    ])

    # ── Data preview ──
    if "category" in dm.columns:
        cols = [c for c in ["category", "spend_2026e", "risk", "concentration",
                            "contract_end", "po_coverage_pct"] if c in dm.columns]
        data_preview.value = dm[cols]


def update_from_uploaded(flagged_df: pd.DataFrame, filename: str):
    """Update dashboard after a successful upload pipeline run."""
    dataset_label.object = f"**Dataset:** {filename}"

    # Build summary meta from uploaded data for charts
    if "category_mapped" in flagged_df.columns and "spend" in flagged_df.columns:
        summary = flagged_df.groupby("category_mapped")["spend"].sum().reset_index()
        summary.columns = ["category", "spend_2026e"]
        summary["spend_2025"]           = summary["spend_2026e"] * 0.85
        summary["budget_2026e"]         = summary["spend_2026e"] * 0.95
        summary["budget_variance"]      = summary["spend_2026e"] - summary["budget_2026e"]
        summary["concentration"]        = 40
        summary["risk"]                 = "Medium"
        summary["single_source"]        = False
        summary["lead_time_days"]       = 30
        summary["contract_end"]         = "Unknown"
        summary["capex_opex"]           = "Opex"
        summary["region"]               = "Unknown"
        summary["po_coverage_pct"]      = 70
        summary["contract_coverage_pct"] = 75
        summary["cagr"]                 = 0.0
        summary["suppliers"]            = ""

        spend_rows = []
        for _, row in summary.iterrows():
            spend_rows.append({"category": row["category"],
                               "year": 2026, "spend": row["spend_2026e"]})

        update_dashboard(
            df_s=pd.DataFrame(spend_rows),
            df_m=summary,
        )
        data_preview.value = flagged_df[[
            c for c in ["supplier", "spend", "date", "category_mapped",
                        "po_status", "maverick_flag", "shadow_it_flag",
                        "freelancer_flag", "spend_pattern"] if c in flagged_df.columns
        ]].head(200)


# ── Year selector ──
def on_year_change(event):
    update_dashboard(year_val=event.new)
year_select.param.watch(on_year_change, "value")


# ── File upload ──
def handle_upload(event):
    if file_input.value is None:
        return
    status_log.object = "⏳ Processing..."

    def pipeline_thread():
        run_pipeline(
            filename=file_input.filename,
            file_bytes=file_input.value,
            status_callback=lambda msg: setattr(status_log, "object", msg),
            dashboard_callback=update_from_uploaded,
        )

    t = threading.Thread(target=pipeline_thread, daemon=True)
    t.start()

file_input.param.watch(handle_upload, "value")


# ── Export ──
def handle_export(event):
    try:
        excel_bytes = export_cfo_excel(
            df_meta, spend_col="spend_2026e",
            category_col="category", supplier_col="suppliers"
        )
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        fname = f"SpendLens_CFO_Report_{ts}.xlsx"
        dl = pn.widgets.FileDownload(
            file=io.BytesIO(excel_bytes),
            filename=fname,
            button_type="success",
            label="⬇ Download Report",
        )
        status_log.object = f"✅ Report ready: **{fname}**"
        sidebar_col.append(dl)
    except Exception as e:
        status_log.object = f"❌ Export error: {str(e)}"

export_btn.on_click(handle_export)

# ── KPI drill-down buttons ──
ebitda_btn   = pn.widgets.Button(name="💶 EBITDA",    button_type="light", width=130)
contract_btn = pn.widgets.Button(name="📋 Contracts", button_type="light", width=130)
maverick_btn = pn.widgets.Button(name="⚠ Maverick",  button_type="light", width=130)

def show_ebitda(e):
    detail_panel.clear()
    detail_panel.append(render_ebitda_table(df_ebitda))

def show_contracts(e):
    detail_panel.clear()
    detail_panel.append(render_contracts_table(df_contracts))

def show_maverick(e):
    detail_panel.clear()
    detail_panel.append(pn.pane.HTML(f"""
    <div style="background:{WHITE}; border:1px solid {BORDER}; border-radius:10px;
                padding:20px; margin-top:8px;">
        <div style="font-size:15px; font-weight:700; color:{NAVY}; margin-bottom:12px;
                    font-family:Georgia,serif;">Maverick Spend Analysis</div>
        <p style="color:{TEXT}; font-size:13px; line-height:1.6;">
            Current maverick spend is <b style="color:{RED};">12%</b> of total —
            target is <b>5%</b>.<br><br>
            <b>Main sources:</b><br>
            • Travel & Expenses — bookings outside Navan (30% non-compliant)<br>
            • Marketing — ad hoc agency spend without PO (60% non-PO)<br>
            • IT Software — shadow IT subscriptions (45% non-contracted)<br>
            • Recruitment — direct agency bookings bypassing procurement<br><br>
            <b style="color:{NAVY};">Action:</b> Enforce PO requirement for spend above €1,000.
        </p>
    </div>""", sizing_mode="stretch_width"))

ebitda_btn.on_click(show_ebitda)
contract_btn.on_click(show_contracts)
maverick_btn.on_click(show_maverick)

# Initial render
update_dashboard()

# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────────────────────────────────────

# ── Header ──
header = pn.pane.HTML(f"""
<div style="background:{NAVY}; padding:20px 28px; border-radius:10px;
            margin-bottom:16px; display:flex; align-items:center; gap:16px;">
    {LOGO_SVG}
    <div>
        <h1 style="color:white; margin:0; font-size:26px; font-weight:600;
                   font-family:Georgia,serif; letter-spacing:1px;">SpendLens</h1>
        <p style="color:rgba(255,255,255,0.7); margin:4px 0 0 0; font-size:13px;
                  font-family:Georgia,serif; font-style:italic;">
            procurement intelligence
        </p>
    </div>
</div>""", sizing_mode="stretch_width")

# ── Sidebar ──
sidebar_col = pn.Column(
    pn.pane.HTML(f"<div style='color:{NAVY}; font-weight:700; font-size:12px; "
                 f"text-transform:uppercase; letter-spacing:1px;'>Year</div>"),
    year_select,
    pn.layout.Divider(),
    pn.pane.HTML(f"<div style='color:{NAVY}; font-weight:700; font-size:12px; "
                 f"text-transform:uppercase; letter-spacing:1px;'>Data Source</div>"),
    file_input,
    dataset_label,
    pn.layout.Divider(),
    pn.pane.HTML(f"<div style='color:{NAVY}; font-weight:700; font-size:12px; "
                 f"text-transform:uppercase; letter-spacing:1px;'>Reports</div>"),
    export_btn,
    pn.layout.Divider(),
    pn.pane.HTML(f"<div style='color:{NAVY}; font-weight:700; font-size:12px; "
                 f"text-transform:uppercase; letter-spacing:1px;'>Icarus</div>"),
    icarus_btn,
    pn.layout.Divider(),
    status_log,
    width=270,
)

# ── Detail buttons ──
detail_buttons = pn.Row(
    pn.pane.HTML(f"<span style='color:{DIM}; font-size:12px; "
                 f"font-family:Georgia,serif;'>Show detail:</span>"),
    ebitda_btn, contract_btn, maverick_btn,
    sizing_mode="stretch_width",
)

# ── Main tab ──
main_tab = pn.Column(
    header,
    kpi_row,
    pn.layout.Divider(),
    detail_buttons,
    detail_panel,
    pn.layout.Divider(),
    chart_s1,
    pn.layout.Divider(),
    chart_s2,
    pn.layout.Divider(),
    chart_s3,
    pn.layout.Divider(),
    chart_s4,
    pn.layout.Divider(),
    section_header("📋 Data Explorer"),
    data_preview,
    sizing_mode="stretch_width",
)

from icarus_ui import IcarusPanel
icarus_panel = IcarusPanel(
    client_categories=list(df_meta["category"].dropna().unique()),
    client_name="Client"
)
icarus_panel.load_recent()

def handle_icarus(event):
    status_log.object = "🪶 Icarus crawl started — check the Icarus tab for results..."
    icarus_panel.run()

icarus_btn.on_click(handle_icarus)

tabs = pn.Tabs(
    ("Dashboard", main_tab),
    ("Deep Dive", chart_deep),
    ("🪶 Icarus", icarus_panel.view()),
    sizing_mode="stretch_width",
)

template = pn.template.FastListTemplate(
    title="SpendLens",
    sidebar=[sidebar_col],
    main=[tabs],
    accent_base_color=NAVY,
    header_background=NAVY,
    background_color=BG,
    theme="default",
)

template.servable()

if __name__ == "__main__":
    pn.serve(template, port=5006, show=True, autoreload=True)
