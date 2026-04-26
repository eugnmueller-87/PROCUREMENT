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
import math
import os
import sqlite3
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
     "budget": 22000, "risk": "Critical", "single_source": True,
     "suppliers": "AWS, Google Cloud, Azure, OVH, Hetzner", "supplier_count": 5,
     "lead_time_days": 0, "contract_end": "2026-09", "capex_opex": "Opex", "region": "US",
     "po_coverage_pct": 95, "contract_coverage_pct": 90},
    {"name": "AI/ML APIs & Data",     "spend": [800, 2200, 4800, 6500, 9200],
     "budget": 8500, "risk": "High", "single_source": False,
     "suppliers": "OpenAI, Anthropic, Scale AI, Cohere, Mistral, Replicate", "supplier_count": 6,
     "lead_time_days": 14, "contract_end": "2026-06", "capex_opex": "Opex", "region": "US",
     "po_coverage_pct": 80, "contract_coverage_pct": 75},
    {"name": "IT Software & SaaS",    "spend": [900, 1400, 2200, 3100, 4200],
     "budget": 4000, "risk": "Low", "single_source": False,
     "suppliers": "GitHub, Datadog, Atlassian, Slack, Notion, Linear, Figma, Snyk, Vercel, Sentry, 1Password, Mixpanel",
     "supplier_count": 12, "lead_time_days": 7,
     "contract_end": "Various", "capex_opex": "Opex", "region": "Global",
     "po_coverage_pct": 85, "contract_coverage_pct": 88},
    {"name": "Telecom & Voice",       "spend": [400, 800, 1400, 2200, 3000],
     "budget": 2800, "risk": "Critical", "single_source": True,
     "suppliers": "Twilio, Vonage, Deutsche Telekom, Bandwidth", "supplier_count": 4,
     "lead_time_days": 30, "contract_end": "2026-07", "capex_opex": "Opex", "region": "US",
     "po_coverage_pct": 92, "contract_coverage_pct": 95},
    {"name": "Recruitment & HR",      "spend": [600, 1100, 2400, 4200, 6800],
     "budget": 6500, "risk": "High", "single_source": False,
     "suppliers": "Personio, LinkedIn, Stepstone, Xing, Hays, Michael Page, Kienbaum, boutique agencies",
     "supplier_count": 8, "lead_time_days": 45,
     "contract_end": "2026-12", "capex_opex": "Opex", "region": "DACH",
     "po_coverage_pct": 60, "contract_coverage_pct": 70},
    {"name": "Professional Services", "spend": [400, 700, 1200, 2100, 3200],
     "budget": 3000, "risk": "Medium", "single_source": False,
     "suppliers": "Deloitte, Baker McKenzie, KPMG, local law firm, advisor", "supplier_count": 5,
     "lead_time_days": 21, "contract_end": "2026-03", "capex_opex": "Opex", "region": "DACH",
     "po_coverage_pct": 55, "contract_coverage_pct": 65},
    {"name": "Marketing & Campaigns", "spend": [300, 800, 1800, 3500, 5500],
     "budget": 5000, "risk": "Medium", "single_source": False,
     "suppliers": "Google Ads, Meta, LinkedIn Ads, event agency A, event agency B, PR firm, creative agency",
     "supplier_count": 7, "lead_time_days": 30,
     "contract_end": "Various", "capex_opex": "Opex", "region": "DACH",
     "po_coverage_pct": 45, "contract_coverage_pct": 55},
    {"name": "Facilities & Office",   "spend": [500, 900, 1500, 2800, 4800],
     "budget": 4500, "risk": "High", "single_source": False,
     "suppliers": "ISS, Lyreco, catering provider, cleaning service, security, maintenance", "supplier_count": 6,
     "lead_time_days": 90, "contract_end": "2028-06", "capex_opex": "Opex", "region": "DACH",
     "po_coverage_pct": 70, "contract_coverage_pct": 80},
    {"name": "Real Estate",           "spend": [1200, 1800, 2400, 3200, 4200],
     "budget": 4000, "risk": "High", "single_source": True,
     "suppliers": "WeWork Berlin, WeWork Munich, external landlord", "supplier_count": 3,
     "lead_time_days": 180, "contract_end": "2028-12", "capex_opex": "Opex", "region": "DACH",
     "po_coverage_pct": 100, "contract_coverage_pct": 100},
    {"name": "Hardware & Equipment",  "spend": [300, 500, 900, 1500, 2400],
     "budget": 2200, "risk": "Medium", "single_source": False,
     "suppliers": "Apple, Dell, NVIDIA, Lenovo", "supplier_count": 4,
     "lead_time_days": 56, "contract_end": "N/A", "capex_opex": "Capex", "region": "DACH",
     "po_coverage_pct": 90, "contract_coverage_pct": 60},
    {"name": "Travel & Expenses",     "spend": [200, 500, 1100, 2000, 3200],
     "budget": 3000, "risk": "Low", "single_source": False,
     "suppliers": "Lufthansa, Deutsche Bahn, Navan, Marriott, Hilton, Sixt, Airbnb, IHG", "supplier_count": 8,
     "lead_time_days": 3, "contract_end": "2026-09", "capex_opex": "Opex", "region": "DACH",
     "po_coverage_pct": 40, "contract_coverage_pct": 50},
]

SUPPLIER_INTEL = {
    "AWS": {
        "contract":     "Enterprise Discount Program (EDP) — expires Sep 2026",
        "terms":        "Net 30 · Annual commitment €18M",
        "price_trend":  "+18% YoY (2024) — GPU & egress cost drivers",
        "discount":     "15% EDP volume discount currently in place",
        "risk":         "Hosts 65% of prod infra — no active failover in place",
        "action":       "Renegotiate before Sep 2026. GPU spot rates up 6%, energy costs up 4% — the remaining 8pp has no market justification. Push for 20%+ EDP discount or introduce Azure as leverage.",
    },
    "Google Cloud": {
        "contract":     "Committed Use Discount — rolling 12-month",
        "terms":        "Net 30 · Flex commitment",
        "price_trend":  "+9% YoY (2024) — BigQuery & Vertex pricing",
        "discount":     "10% committed use discount",
        "risk":         "Secondary cloud — used for data warehouse & ML pipelines",
        "action":       "Increase Google Cloud commitment to strengthen negotiation leverage against AWS at renewal.",
    },
    "Azure": {
        "contract":     "Microsoft Enterprise Agreement — expires Dec 2026",
        "terms":        "Net 30 · Bundled with M365",
        "price_trend":  "+11% YoY (2024) — Copilot add-on uplift",
        "discount":     "12% EA discount + MACC €5M",
        "risk":         "M365 dependency creates switching costs — moderate lock-in",
        "action":       "Challenge Copilot seat uplift in EA renewal — adoption below 30%. Remove unused seats before renewal.",
    },
    "OpenAI": {
        "contract":     "API pay-as-you-go — no committed contract",
        "terms":        "Monthly billing · No SLA",
        "price_trend":  "-22% YoY (2024) — GPT-4o pricing reduction",
        "discount":     "None — no volume agreement in place",
        "risk":         "No contract, no SLA, no price protection — rate can change any time",
        "action":       "Negotiate an annual API commitment for 20–30% discount. Evaluate Anthropic & Mistral as dual-source to reduce dependency.",
    },
    "Anthropic": {
        "contract":     "API pay-as-you-go — no committed contract",
        "terms":        "Monthly billing",
        "price_trend":  "Stable 2024 — Claude 3 pricing held",
        "discount":     "None",
        "risk":         "Low spend, high strategic value — early-stage dependency",
        "action":       "Lock in a committed API agreement before spend scales. Anthropic offers enterprise pricing at >€500K/yr.",
    },
    "Personio": {
        "contract":     "SaaS subscription — annual, auto-renews Dec 2026",
        "terms":        "Annual prepay",
        "price_trend":  "+25% YoY (2024) — seat expansion + tier upgrade",
        "discount":     "8% multi-year discount offered at last renewal",
        "risk":         "Core HRIS — data portability limited, high switching cost",
        "action":       "Freeze seat count growth. Audit active seats — last review found 18% inactive. Negotiate 3-year deal to lock current rate before next price uplift.",
    },
    "Twilio": {
        "contract":     "Volume-based — no formal agreement",
        "terms":        "Monthly · Pay per use",
        "price_trend":  "+14% YoY (2024) — SMS & voice rate increases",
        "discount":     "None negotiated",
        "risk":         "Single source for all SMS/voice — no fallback carrier",
        "action":       "Onboard Vonage as secondary carrier immediately. Then renegotiate Twilio volume pricing with dual-source as leverage.",
    },
    "WeWork Berlin": {
        "contract":     "Lease agreement — expires Dec 2028",
        "terms":        "Monthly · €2,400/desk",
        "price_trend":  "+8% YoY (2024) — CPI escalation clause",
        "discount":     "3 months free received at signing",
        "risk":         "WeWork financial instability — monitor covenant triggers",
        "action":       "Explore direct landlord negotiation before 2028 renewal. WeWork margin is ~40% — significant savings available going direct.",
    },
    "Deloitte": {
        "contract":     "Framework agreement — annual SOW renewal",
        "terms":        "Net 45 · Daily rate €1,800–2,400",
        "price_trend":  "+6% YoY (2024) — rate card inflation",
        "discount":     "10% framework discount vs. spot market",
        "risk":         "Key-person dependency — 3 named partners on critical projects",
        "action":       "Cap daily rate increases at CPI in next SOW. Build in knowledge transfer obligations to reduce key-person lock-in.",
    },
    "Lufthansa": {
        "contract":     "Corporate travel agreement — expires Sep 2026",
        "terms":        "Monthly settlement",
        "price_trend":  "+19% YoY (2024) — fuel surcharge + capacity reduction",
        "discount":     "12% negotiated discount vs. public fares",
        "risk":         "Low — multiple airline alternatives available",
        "action":       "Renegotiate with Ryanair/easyJet benchmarks in hand. 40% of routes have low-cost alternatives at 60% of Lufthansa price.",
    },
}

# Per-year scaling factors (index 0=2022 … 4=2026)
# Simulate procurement maturity growing over time
PO_SCALE     = [0.58, 0.67, 0.74, 0.86, 1.00]  # PO coverage improving
CC_SCALE     = [0.52, 0.63, 0.72, 0.85, 1.00]  # Contract coverage improving
MAVERICK_PCT = [24,   20,   17,   14,   12]     # Maverick spend shrinking
SPM_PCT      = [38,   46,   53,   60,   65]     # Spend under management growing
EBITDA_SCALE = [0.10, 0.22, 0.42, 0.70, 1.00]  # EBITDA impact compounding
# Lead times improve as supplier relationships and processes mature
LEAD_SCALE   = [1.70, 1.40, 1.20, 1.08, 1.00]  # 2022 slowest, 2026 most efficient

EBITDA_BY_YEAR = {
    2022: [
        {"Initiative": "Cloud Cost Optimisation",    "Type": "Savings",        "Impact €K": 42,  "Status": "Planned"},
        {"Initiative": "SaaS License Consolidation", "Type": "Savings",        "Impact €K": 28,  "Status": "Planned"},
        {"Initiative": "AWS Reserved Instances",     "Type": "Cost Avoidance", "Impact €K": 40,  "Status": "Planned"},
    ],
    2023: [
        {"Initiative": "Cloud Cost Optimisation",    "Type": "Savings",        "Impact €K": 130, "Status": "In Progress"},
        {"Initiative": "SaaS License Consolidation", "Type": "Savings",        "Impact €K": 85,  "Status": "Realised"},
        {"Initiative": "AWS Reserved Instances",     "Type": "Cost Avoidance", "Impact €K": 120, "Status": "Realised"},
        {"Initiative": "Hardware Bulk Purchase",     "Type": "Cost Avoidance", "Impact €K": 75,  "Status": "Planned"},
    ],
    2024: [
        {"Initiative": "Cloud Cost Optimisation",    "Type": "Savings",        "Impact €K": 210, "Status": "Realised"},
        {"Initiative": "SaaS License Consolidation", "Type": "Savings",        "Impact €K": 150, "Status": "Realised"},
        {"Initiative": "Recruitment Agency Rebid",   "Type": "Savings",        "Impact €K": 145, "Status": "In Progress"},
        {"Initiative": "AWS Reserved Instances",     "Type": "Cost Avoidance", "Impact €K": 200, "Status": "Realised"},
        {"Initiative": "Hardware Bulk Purchase",     "Type": "Cost Avoidance", "Impact €K": 110, "Status": "In Progress"},
    ],
    2025: [
        {"Initiative": "Cloud Cost Optimisation",    "Type": "Savings",        "Impact €K": 330, "Status": "Realised"},
        {"Initiative": "SaaS License Consolidation", "Type": "Savings",        "Impact €K": 230, "Status": "Realised"},
        {"Initiative": "Recruitment Agency Rebid",   "Type": "Savings",        "Impact €K": 280, "Status": "Realised"},
        {"Initiative": "Telco Contract Renewal",     "Type": "Savings",        "Impact €K": 100, "Status": "In Progress"},
        {"Initiative": "AWS Reserved Instances",     "Type": "Cost Avoidance", "Impact €K": 320, "Status": "Realised"},
        {"Initiative": "Hardware Bulk Purchase",     "Type": "Cost Avoidance", "Impact €K": 220, "Status": "In Progress"},
    ],
    2026: [
        {"Initiative": "Cloud Cost Optimisation",    "Type": "Savings",        "Impact €K": 420, "Status": "Realised"},
        {"Initiative": "SaaS License Consolidation", "Type": "Savings",        "Impact €K": 280, "Status": "Realised"},
        {"Initiative": "Recruitment Agency Rebid",   "Type": "Savings",        "Impact €K": 350, "Status": "In Progress"},
        {"Initiative": "Telco Contract Renewal",     "Type": "Savings",        "Impact €K": 180, "Status": "Planned"},
        {"Initiative": "AWS Reserved Instances",     "Type": "Cost Avoidance", "Impact €K": 400, "Status": "Realised"},
        {"Initiative": "Hardware Bulk Purchase",     "Type": "Cost Avoidance", "Impact €K": 320, "Status": "In Progress"},
    ],
}
EBITDA_DATA = EBITDA_BY_YEAR[2026]  # default for initial load

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

    total_spend_2026 = sum(c["spend"][4] for c in CATEGORIES_RAW)
    meta_rows = [{
        "category":             c["name"],
        "spend_2026e":          c["spend"][4],
        "spend_2025":           c["spend"][3],
        "budget_2026e":         c["budget"],
        "budget_variance":      c["spend"][4] - c["budget"],
        "concentration":        round(c["spend"][4] / total_spend_2026 * 100, 1),
        "risk":                 c["risk"],
        "single_source":        c["single_source"],
        "suppliers":            c["suppliers"],
        "supplier_count":       c["supplier_count"],
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


def build_year_meta(yr_idx: int) -> pd.DataFrame:
    """Build df_meta with spend values for the given year index (0=2022…4=2026)."""
    prev_idx    = max(0, yr_idx - 1)
    total_spend = sum(c["spend"][yr_idx] for c in CATEGORIES_RAW)
    rows = []
    for c in CATEGORIES_RAW:
        spend_yr   = c["spend"][yr_idx]
        spend_prev = c["spend"][prev_idx]
        growth_assumption = [0.30, 0.25, 0.20, 0.12, 0.08][yr_idx]
        budget_yr = round(spend_prev * (1 + growth_assumption)) if spend_prev else spend_yr
        # Concentration = this category's share of total company spend (%)
        # Changes naturally each year as spend mix shifts
        concentration = round(spend_yr / total_spend * 100, 1)
        # Supplier count grows ~25%/year; work backwards from 2026 base
        supplier_count = max(1, round(c["supplier_count"] / (1.25 ** (4 - yr_idx))))
        rows.append({
            "category":               c["name"],
            "spend_2026e":            spend_yr,
            "spend_2025":             spend_prev,
            "budget_2026e":           budget_yr,
            "budget_variance":        spend_yr - budget_yr,
            "concentration":          concentration,
            "risk":                   c["risk"],
            "single_source":          c["single_source"],
            "suppliers":              c["suppliers"],
            "supplier_count":         supplier_count,
            "lead_time_days":         round(c["lead_time_days"] * LEAD_SCALE[yr_idx]),
            "contract_end":           c["contract_end"],
            "capex_opex":             c["capex_opex"],
            "region":                 c["region"],
            "po_coverage_pct":        round(c["po_coverage_pct"]       * PO_SCALE[yr_idx]),
            "contract_coverage_pct":  round(c["contract_coverage_pct"] * CC_SCALE[yr_idx]),
            "cagr":                   round(((c["spend"][yr_idx] / c["spend"][0]) ** (1 / max(yr_idx, 1)) - 1) * 100, 1) if yr_idx > 0 else 0.0,
        })
    return pd.DataFrame(rows)


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


def chart_category_bars(df_meta, year_label="2026E"):
    df = df_meta.sort_values("spend_2026e", ascending=True).copy()
    within  = df[["spend_2026e", "budget_2026e"]].min(axis=1)   # capped at budget
    excess  = (df["spend_2026e"] - df["budget_2026e"]).clip(lower=0)  # over-budget portion only
    fig = go.Figure()
    # Base: spend up to budget (navy)
    fig.add_trace(go.Bar(
        y=df["category"], x=within, orientation="h",
        marker_color=NAVY, name="Within budget",
        hovertemplate="<b>%{y}</b><br>Within budget: €%{x:,.0f}K<extra></extra>",
    ))
    # Overlay: excess only (red)
    fig.add_trace(go.Bar(
        y=df["category"], x=excess, orientation="h",
        marker_color=RED, name="Over budget",
        text=[f"€{v:,.0f}K" if v > 0 else "" for v in df["spend_2026e"]],
        textposition="outside",
        customdata=df["budget_variance"],
        hovertemplate="<b>%{y}</b><br>Over budget: €%{x:,.0f}K<br>Total spend: €%{customdata:,.0f}K<extra></extra>",
    ))
    fig.update_layout(
        title=f"{year_label} Spend vs Budget (red = over-budget portion)",
        barmode="stack", **LAYOUT, height=420, xaxis_title="Spend (€K)",
        showlegend=False,
    )
    return fig


def chart_risk_bubble(df_meta):
    fig = go.Figure()
    for _, row in df_meta.iterrows():
        n = int(row.get("supplier_count", 3))
        fig.add_trace(go.Scatter(
            x=[row["concentration"]], y=[row["spend_2026e"]],
            mode="markers+text",
            marker=dict(size=max(n * 16, 32),
                        color=RISK_COLORS.get(row["risk"], DIM), opacity=0.80,
                        line=dict(color=WHITE, width=2)),
            text=[row["category"]],
            textposition="top center",
            textfont=dict(size=10, color=TEXT, family="Georgia, serif"),
            name=row["category"],
            customdata=[[row["category"], row["risk"], n,
                         row.get("suppliers", ""), row["concentration"]]],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Risk: %{customdata[1]}<br>"
                "Share of total spend: %{customdata[4]}%%<br>"
                "Spend: €%{y:,.0f}K<br>"
                "Suppliers (%{customdata[2]}): %{customdata[3]}<extra></extra>"
            ),
        ))
    # High-concentration zone: category absorbs >20% of total company spend
    x_min_data = df_meta["concentration"].min()
    x_max = df_meta["concentration"].max() * 1.25
    y_max = df_meta["spend_2026e"].max() * 1.1
    total_spend = df_meta["spend_2026e"].sum()
    fig.add_shape(type="rect", x0=20, x1=x_max, y0=0, y1=y_max,
                  fillcolor="rgba(192,57,43,0.05)",
                  line=dict(color="rgba(192,57,43,0.3)", dash="dot"))
    fig.add_annotation(x=25, y=y_max * 0.97,
                       text="⚠ HIGH CONCENTRATION ZONE", showarrow=False,
                       font=dict(size=11, color=RED), xanchor="left")
    fig.add_annotation(
        text=f"<b>Total Spend</b><br>€{total_spend:,.0f}K",
        xref="paper", yref="paper", x=0.01, y=0.99,
        showarrow=False, xanchor="left", yanchor="top",
        font=dict(size=12, color=WHITE, family="Georgia, serif"),
        bgcolor=NAVY, bordercolor=NAVY2, borderwidth=1, borderpad=8,
    )
    fig.update_layout(
        title="Risk Map — Category Share of Total Spend (bubble size = no. of suppliers)",
        **LAYOUT, height=560, showlegend=False,
        xaxis_title="Category Spend as % of Total Company Spend",
        xaxis_type="log",
        xaxis_tickvals=[1, 2, 3, 5, 8, 12, 20, 35, 50],
        xaxis_ticktext=["1%", "2%", "3%", "5%", "8%", "12%", "20%", "35%", "50%"],
        xaxis_range=[math.log10(max(x_min_data * 0.7, 0.8)), math.log10(x_max)],
        yaxis_title="Spend (€K)",
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
    rows = []
    for _, r in df_meta.iterrows():
        cat         = r["category"]
        spend_total = r["spend_2026e"]
        risk        = r["risk"]
        suppliers   = [s.strip() for s in str(r.get("suppliers", "")).split(",") if s.strip()][:5]
        if not suppliers:
            suppliers = ["Unknown"]
        weights = [1 / (i + 1) for i in range(len(suppliers))]
        wsum    = sum(weights)
        for i, sup in enumerate(suppliers):
            rows.append({
                "category": cat,
                "supplier": f"{i + 1}. {sup}",
                "spend":    round(spend_total * weights[i] / wsum),
                "risk":     risk,
            })
    df = pd.DataFrame(rows)
    fig = px.treemap(
        df,
        path=["category", "supplier"],
        values="spend",
        color="risk",
        color_discrete_map=RISK_COLORS,
        custom_data=["spend", "risk"],
    )
    fig.update_traces(
        textfont=dict(size=11),
        hovertemplate="<b>%{label}</b><br>Spend: €%{customdata[0]:,.0f}K<br>Risk: %{customdata[1]}<extra></extra>",
    )
    fig.update_layout(
        title="Spend by Category (size) × Risk (color) — click a category to expand suppliers",
        paper_bgcolor=BG, font=dict(color=TEXT, family="Georgia,serif"),
        height=680,
        legend=dict(title="Risk", bgcolor="rgba(255,255,255,0.9)",
                    font=dict(size=11), bordercolor=BORDER, borderwidth=1),
    )
    return fig


def chart_cagr(df_meta, year_label="2026E"):
    df = df_meta.sort_values("cagr", ascending=True)
    colors = [GREEN if v < 20 else YELLOW if v < 40 else RED for v in df["cagr"]]
    label = "YoY Growth" if year_label == "2023" else f"CAGR 2022→{year_label}"
    fig = go.Figure(go.Bar(
        y=df["category"], x=df["cagr"], orientation="h",
        marker_color=colors,
        text=[f"{v:.1f}%" for v in df["cagr"]],
        textposition="outside",
    ))
    fig.update_layout(title=f"Category {label}",
                      **LAYOUT, height=420, xaxis_title=f"{label} %")
    return fig



def build_spend_delta_chart(start_yr: int, end_yr: int):
    si = YEARS.index(start_yr)
    ei = YEARS.index(end_yr)
    if ei < si:
        si, ei = ei, si
        start_yr, end_yr = end_yr, start_yr

    # Base year — show absolute spend with 0% growth label
    if start_yr == end_yr:
        rows = [{"category": c["name"], "spend": c["spend"][si]} for c in CATEGORIES_RAW]
        df = pd.DataFrame(rows).sort_values("spend", ascending=True)
        fig = go.Figure(go.Bar(
            y=df["category"], x=df["spend"], orientation="h",
            marker_color=GREEN,
            text=[f"€{v:,.0f}K  (0% — base year)" for v in df["spend"]],
            textposition="outside",
        ))
        fig.update_layout(
            title=f"Baseline spend {start_yr}  (0% growth — comparison start)",
            **LAYOUT, height=420,
            xaxis_title="Spend (€K)",
            xaxis_range=[0, df["spend"].max() * 1.55],
        )
        return fig

    rows = []
    for c in CATEGORIES_RAW:
        s0, s1 = c["spend"][si], c["spend"][ei]
        delta = s1 - s0
        pct   = round((s1 / s0 - 1) * 100, 1) if s0 else 0.0
        rows.append({"category": c["name"], "delta": delta, "pct": pct, "s0": s0, "s1": s1})

    df = pd.DataFrame(rows).sort_values("delta", ascending=True)
    fig = go.Figure()
    # Base: from-year spend (dark navy)
    fig.add_trace(go.Bar(
        name=str(start_yr), y=df["category"], x=df["s0"],
        orientation="h", marker_color=NAVY,
        hovertemplate="<b>%{y}</b><br>" + str(start_yr) + ": €%{x:,.0f}K<extra></extra>",
    ))
    # Growth: delta on top (light blue), label shows increase
    fig.add_trace(go.Bar(
        name=f"Growth → {end_yr}", y=df["category"], x=df["delta"],
        orientation="h", marker_color="#5B9BD5",
        text=[f"+€{d:,.0f}K ({p:+.0f}%)" for d, p in zip(df["delta"], df["pct"])],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Growth: +€%{x:,.0f}K<extra></extra>",
    ))
    x_max = (df["s0"] + df["delta"]).max()
    fig.update_layout(
        title=f"Spend by category  {start_yr} → {end_yr}",
        **LAYOUT, height=420, barmode="stack",
        xaxis_title="Spend (€K)",
        xaxis_range=[0, x_max * 1.45],
        legend_orientation="h", legend_y=1.08, legend_x=0,
        showlegend=True,
    )
    return fig


def chart_capex_opex(*_):
    # Stacked bar: Capex and Opex spend per year across the full timeline
    capex_by_year = []
    opex_by_year  = []
    for yr_i in range(len(YEARS)):
        capex = sum(c["spend"][yr_i] for c in CATEGORIES_RAW if c["capex_opex"] == "Capex")
        opex  = sum(c["spend"][yr_i] for c in CATEGORIES_RAW if c["capex_opex"] == "Opex")
        capex_by_year.append(capex)
        opex_by_year.append(opex)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Opex",  x=YEARS, y=opex_by_year,  marker_color=GREEN,
                         text=[f"€{v:,.0f}K" for v in opex_by_year],
                         textposition="inside",
                         hovertemplate="Opex %{x}: €%{y:,.0f}K<extra></extra>"))
    fig.add_trace(go.Bar(name="Capex", x=YEARS, y=capex_by_year, marker_color=NAVY,
                         text=[f"€{v:,.0f}K" for v in capex_by_year],
                         textposition="inside",
                         hovertemplate="Capex %{x}: €%{y:,.0f}K<extra></extra>"))
    fig.update_layout(
        title="Capex vs Opex spend per year",
        **LAYOUT, height=420, barmode="stack",
        xaxis_tickvals=YEARS,
        xaxis_ticktext=[str(y) for y in YEARS],
        yaxis_title="Spend (€K)",
        legend_orientation="h", legend_y=1.08, legend_x=0,
    )
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
file_input    = pn.widgets.FileInput(
    accept=".csv,.xlsx,.xls", name="", width=240,
    stylesheets=["""
        :host { width:240px !important; }
        .bk-input-group {
            position:relative; width:240px; height:38px; border-radius:6px;
            background:#1B3A6B; border:none; display:flex; align-items:center;
            justify-content:center; cursor:pointer; transition:background 0.15s;
        }
        .bk-input-group:hover { background:#2E5BA8; }
        .bk-input-group::before {
            content:"📂  Upload Data"; color:white; font-size:13px;
            font-family:Georgia,serif; font-weight:600;
            pointer-events:none; position:absolute;
        }
        input[type="file"] {
            position:absolute; opacity:0; width:100%; height:100%;
            cursor:pointer; z-index:1;
        }
        .bk-input-container { display:none !important; }
    """],
)
dataset_label = pn.pane.Markdown("",
                                  styles={"color": NAVY, "font-size": "13px"})
export_btn    = pn.widgets.Button(name="📥 Report",
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
chart_deep      = pn.Column(sizing_mode="stretch_width")
drill_panel     = pn.Column(sizing_mode="stretch_width")
cagr_start      = pn.widgets.Select(name="From", options=YEARS, value=2022, width=100)
cagr_end        = pn.widgets.Select(name="To",   options=YEARS, value=2026, width=100)
cagr_pane       = pn.pane.Plotly(sizing_mode="stretch_width")
treemap_pane      = pn.pane.Plotly(sizing_mode="stretch_width")
supplier_detail   = pn.pane.HTML("", sizing_mode="stretch_width")
supplier_news     = pn.pane.HTML("", sizing_mode="stretch_width")
fetch_signals_btn = pn.widgets.Button(name="🔍 Fetch latest signals", button_type="primary",
                                      width=200, margin=(8, 0, 0, 0))
treemap_back      = pn.widgets.Button(name="← Back to category view", button_type="light",
                                      width=200, margin=(0, 0, 8, 0))
treemap_frame     = pn.Column(sizing_mode="stretch_width")
_current_supplier = [""]  # mutable box for the fetch button callback

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

    # ds_trend = full timeline up to selected year (for Spend Evolution area chart)
    if year_val != "All years":
        yr_filter = int(year_val)
        ds_trend  = df_spend[df_spend["year"] <= yr_filter].copy()
    else:
        ds_trend = df_spend.copy()

    # ── Resolve year and build year-specific data ──
    if year_val != "All years":
        yr      = int(year_val)
        yr_idx  = YEARS.index(yr) if yr in YEARS else 4
        prev_yr = YEARS[yr_idx - 1] if yr_idx > 0 else None
        total   = df_spend[df_spend["year"] == yr]["spend"].sum()
        prev    = df_spend[df_spend["year"] == prev_yr]["spend"].sum() if prev_yr else 0
        dm      = build_year_meta(yr_idx)
        ebitda_yr = pd.DataFrame(EBITDA_BY_YEAR.get(yr, EBITDA_BY_YEAR[2026]))
        year_label = str(yr)
    else:
        yr_idx    = 4
        total     = df_meta["spend_2026e"].sum()
        prev      = df_meta["spend_2025"].sum()
        dm        = df_meta.copy()
        ebitda_yr = pd.DataFrame(EBITDA_BY_YEAR[2026])
        year_label = "All years"

    yoy      = round((total - prev) / prev * 100, 1) if prev > 0 else 0
    ebitda   = ebitda_yr["Impact €K"].sum()
    po_avg   = round(dm["po_coverage_pct"].mean())
    cc_avg   = round(dm["contract_coverage_pct"].mean())
    maverick = MAVERICK_PCT[yr_idx]
    spm_pct  = SPM_PCT[yr_idx]

    # ── KPI Cards ──
    spend_label = str(year_val) if year_val != "All years" else "All years"
    kpi_row.clear()
    kpi_row.extend([
        kpi_card("Total Spend",       f"€{total/1000:.1f}M",   spend_label),
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
            pn.pane.Plotly(chart_spend_stacked(ds_trend),              sizing_mode="stretch_width"),
            pn.pane.Plotly(chart_category_bars(dm, year_label),        sizing_mode="stretch_width"),
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
            pn.pane.Plotly(chart_ebitda_waterfall(ebitda_yr),          sizing_mode="stretch_width"),
            pn.pane.Plotly(chart_category_bars(dm, year_label),        sizing_mode="stretch_width"),
        ),
        render_ebitda_table(ebitda_yr),
    ])

    # ── Deep Dive ──
    chart_deep.clear()
    chart_deep.extend([
        section_header("🔬 Deep Dive Analysis"),
        pn.Row(
            pn.Column(
                pn.pane.HTML("<b style='font-size:12px;color:#1B2A4A'>Compare period</b>",
                             margin=(16, 0, 8, 0)),
                cagr_start,
                cagr_end,
                width=130,
                margin=(0, 12, 0, 0),
            ),
            cagr_pane,
            pn.pane.Plotly(chart_capex_opex(), sizing_mode="stretch_width"),
            sizing_mode="stretch_width",
        ),
        treemap_frame,
    ])
    cagr_pane.object   = build_spend_delta_chart(cagr_start.value, cagr_end.value)
    treemap_pane.object = chart_treemap(dm)
    treemap_frame.objects = [treemap_pane]

    # ── Data preview — rename column to show the actual year ──
    if "category" in dm.columns:
        display_cols = [c for c in ["category", "spend_2026e", "risk", "concentration",
                                    "contract_end", "po_coverage_pct"] if c in dm.columns]
        display_dm = dm[display_cols].rename(columns={"spend_2026e": f"spend_{year_label} (€K)"})
        data_preview.value = display_dm


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

# ── Treemap supplier detail card ──
def _render_supplier_card(sup_name: str, spend: int, cat_name: str, risk: str) -> str:
    intel = SUPPLIER_INTEL.get(sup_name, {})
    risk_color = {"Critical": "#C0392B", "High": "#E67E22", "Medium": "#F1C40F", "Low": "#00A86B"}.get(risk, "#1B2A4A")

    def row(label, value, color="#1B2A4A"):
        return f"""
        <tr>
          <td style="padding:6px 12px 6px 0;color:#6c757d;font-size:12px;white-space:nowrap">{label}</td>
          <td style="padding:6px 0;color:{color};font-size:13px">{value}</td>
        </tr>"""

    intel_rows = ""
    if intel:
        intel_rows = (
            row("Contract",    intel.get("contract", "—"))
          + row("Terms",       intel.get("terms", "—"))
          + row("Price trend", intel.get("price_trend", "—"), "#C0392B")
          + row("Discount",    intel.get("discount", "—"), "#00A86B")
          + row("Risk note",   intel.get("risk", "—"), risk_color)
        )
        action_html = f"""
        <div style="margin-top:12px;padding:12px 16px;background:#EAF6F0;border-left:4px solid #00A86B;border-radius:4px">
          <div style="font-size:11px;color:#6c757d;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">Suggested Action</div>
          <div style="font-size:13px;color:#1B2A4A;line-height:1.5">{intel.get("action", "")}</div>
        </div>"""
    else:
        intel_rows = (
            row("Contract",    "Not yet captured")
          + row("Terms",       "Not yet captured")
          + row("Price trend", "Not yet captured")
          + row("Discount",    "Not yet captured")
          + row("Risk note",   "Not yet captured")
        )
        action_html = f"""
        <div style="margin-top:12px;padding:12px 16px;background:#F8F9FA;border-left:4px solid #DEE2E6;border-radius:4px">
          <div style="font-size:11px;color:#6c757d;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">⏳ Supplier Intel Pending</div>
          <div style="font-size:13px;color:#6c757d;line-height:1.5">
            No procurement intelligence recorded for <strong>{sup_name}</strong> yet.
            Upload a contract, pricing sheet, or supplier agreement via Icarus to populate this card automatically.
          </div>
        </div>"""

    return f"""
    <div style="margin:12px 0;padding:20px 24px;background:#fff;border:1px solid #DEE2E6;border-radius:8px;
                border-top:4px solid {risk_color};font-family:Georgia,serif">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px">
        <div>
          <div style="font-size:18px;font-weight:bold;color:#1B2A4A">{sup_name}</div>
          <div style="font-size:12px;color:#6c757d">{cat_name} &nbsp;·&nbsp;
            <span style="color:{risk_color};font-weight:600">{risk} Risk</span>
          </div>
        </div>
        <div style="text-align:right">
          <div style="font-size:22px;font-weight:bold;color:#1B2A4A">€{spend:,}K</div>
          <div style="font-size:11px;color:#6c757d">estimated spend</div>
        </div>
      </div>
      <table style="width:100%;border-collapse:collapse">
        {intel_rows}
      </table>
      {action_html}
    </div>"""


def _get_supplier_signals(sup_name: str, limit: int = 5) -> list:
    try:
        conn = sqlite3.connect("clients/default/icarus_memory.db")
        rows = conn.execute(
            """SELECT headline, source, published, relevance, impact, action, url
               FROM signals
               WHERE (headline LIKE ? OR summary LIKE ?)
                 AND relevance >= 6
               ORDER BY timestamp DESC
               LIMIT ?""",
            (f"%{sup_name}%", f"%{sup_name}%", limit),
        ).fetchall()
        conn.close()
        return [{"headline": r[0], "source": r[1], "published": r[2],
                 "relevance": r[3], "impact": r[4], "action": r[5], "url": r[6]}
                for r in rows]
    except Exception:
        return []


def _render_news_html(signals: list, sup_name: str) -> str:
    impact_color = {"positive": "#00A86B", "negative": "#C0392B", "neutral": "#6c757d"}
    if not signals:
        return f"""
        <div style="margin-top:8px;padding:12px 16px;background:#F8F9FA;
                    border:1px solid #DEE2E6;border-radius:8px;font-family:Georgia,serif">
          <div style="font-size:11px;color:#6c757d;text-transform:uppercase;
                      letter-spacing:.05em;margin-bottom:4px">📡 Market Intelligence</div>
          <div style="font-size:13px;color:#6c757d">
            No Icarus signals found for <strong>{sup_name}</strong> yet.
            Click <em>Fetch latest signals</em> to scan live news sources.
          </div>
        </div>"""
    items = ""
    for s in signals:
        col   = impact_color.get(s["impact"], "#6c757d")
        date  = (s["published"] or "")[:10]
        url   = s["url"] or "#"
        items += f"""
        <div style="padding:10px 0;border-bottom:1px solid #F0F0F0">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <a href="{url}" target="_blank"
               style="font-size:13px;color:#1B2A4A;text-decoration:none;font-weight:600;
                      flex:1;margin-right:12px;line-height:1.4">{s['headline']}</a>
            <span style="font-size:11px;color:{col};white-space:nowrap;font-weight:600">
              {s['impact'].upper()}</span>
          </div>
          <div style="font-size:11px;color:#6c757d;margin-top:3px">
            {s['source']} · {date} · Relevance {s['relevance']}/10
          </div>
          {f'<div style="font-size:12px;color:#1B2A4A;margin-top:4px;font-style:italic">{s["action"]}</div>' if s["action"] else ""}
        </div>"""
    return f"""
    <div style="margin-top:8px;padding:16px 20px;background:#fff;
                border:1px solid #DEE2E6;border-radius:8px;font-family:Georgia,serif">
      <div style="font-size:11px;color:#6c757d;text-transform:uppercase;
                  letter-spacing:.05em;margin-bottom:8px">📡 Latest Market Signals — {sup_name}</div>
      {items}
    </div>"""


def _show_treemap():
    treemap_frame.objects = [treemap_pane]


def _on_treemap_click(*_):
    cd = treemap_pane.click_data
    if not cd:
        return
    points = cd.get("points", [])
    if not points:
        return
    p = points[0]
    node_id = p.get("id", "")
    if "/" not in node_id:
        return
    cat_name  = node_id.split("/")[0]
    raw_label = p.get("label", "")
    sup_name  = raw_label.split(". ", 1)[-1] if ". " in raw_label else raw_label
    spend     = int(p.get("value", 0))
    risk      = p.get("customdata", [None, "Unknown"])[1] if p.get("customdata") else "Unknown"
    _current_supplier[0] = sup_name
    signals = _get_supplier_signals(sup_name)
    supplier_detail.object = _render_supplier_card(sup_name, spend, cat_name, risk)
    supplier_news.object   = _render_news_html(signals, sup_name)
    treemap_frame.objects  = [treemap_back, supplier_detail, supplier_news, fetch_signals_btn]


def _on_fetch_signals(_):
    sup_name = _current_supplier[0]
    if not sup_name:
        return
    fetch_signals_btn.name     = "⏳ Fetching RSS feeds…"
    fetch_signals_btn.disabled = True

    def _run():
        try:
            import icarus as _icarus
            all_categories = [c["name"] for c in CATEGORIES_RAW]
            articles = _icarus.fetch_articles(all_categories)
            sup_lower = sup_name.lower()
            matches = [
                a for a in articles
                if sup_lower in a.get("headline", "").lower()
                or sup_lower in a.get("summary", "").lower()
            ]
            if matches:
                # Convert raw articles to signal-shaped dicts for _render_news_html
                signals = [{
                    "headline":  a["headline"],
                    "source":    a["source"],
                    "published": (a.get("published") or "")[:10],
                    "relevance": 7,
                    "impact":    "neutral",
                    "action":    None,
                    "url":       a.get("url", "#"),
                } for a in matches[:5]]
                supplier_news.object = _render_news_html(signals, sup_name)
            else:
                supplier_news.object = f"""
                <div style="margin-top:8px;padding:12px 16px;background:#F8F9FA;
                            border:1px solid #DEE2E6;border-radius:8px;font-family:Georgia,serif">
                  <div style="font-size:11px;color:#6c757d;text-transform:uppercase;
                              letter-spacing:.05em;margin-bottom:4px">📡 Market Intelligence</div>
                  <div style="font-size:13px;color:#6c757d">
                    No articles mentioning <strong>{sup_name}</strong> in current RSS feeds.
                    Try again later or run a full Icarus scan from the Icarus tab.
                  </div>
                </div>"""
        except Exception as exc:
            supplier_news.object = f"""
            <div style="margin-top:8px;padding:12px 16px;background:#FDF2F2;
                        border:1px solid #F5C6CB;border-radius:8px;font-family:Georgia,serif">
              <div style="font-size:12px;color:#C0392B">⚠ RSS fetch error: {exc}</div>
            </div>"""
        fetch_signals_btn.name     = "🔍 Fetch latest signals"
        fetch_signals_btn.disabled = False

    threading.Thread(target=_run, daemon=True).start()


fetch_signals_btn.on_click(_on_fetch_signals)
def _update_cagr(*_):
    cagr_pane.object = build_spend_delta_chart(cagr_start.value, cagr_end.value)

cagr_start.param.watch(_update_cagr, "value")
cagr_end.param.watch(_update_cagr, "value")
treemap_back.on_click(lambda _: _show_treemap())
treemap_pane.param.watch(_on_treemap_click, "click_data")

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
# Dashboard-only sections (hidden when Icarus tab is active)
_dash_sidebar = pn.Column(
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
)

sidebar_col = pn.Column(
    _dash_sidebar,
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

# Hide dashboard sidebar when user switches to the Icarus tab (index 2)
def _on_tab_change(event):
    _dash_sidebar.visible = (event.new != 2)

tabs.param.watch(_on_tab_change, 'active')

template = pn.template.FastListTemplate(
    title="SpendLens",
    sidebar=[sidebar_col],
    main=[tabs],
    accent_base_color=NAVY,
    header_background=NAVY,
    background_color=BG,
    theme="default",
    theme_toggle=False,
    raw_css=["""
        /* Hide Panel header toolbar icons (settings, notifications, user) */
        .pn-header-design-provider,
        #header-design-provider,
        .pn-header-design-provider > *,
        fast-design-system-provider > fast-button,
        .bk-toolbar.bk-above,
        .title-bar > span:not(.title) {
            display: none !important;
        }
    """],
)

template.servable()

if __name__ == "__main__":
    pn.serve(template, port=5006, show=True, autoreload=True)
