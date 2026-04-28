"""
SpendLens — AI-Powered Procurement Intelligence Dashboard
=========================================================
Run with:
    PYTHONUTF8=1 panel serve app.py --show --autoreload

Dashboard URL:
    http://localhost:5006/app
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
from modules.cfo_reports        import export_cfo_excel
from modules.supplier_profiler import (
    compute_and_save_profiles, get_supplier_profiles, build_demo_profiles,
    update_supplier_field, TAXONOMY, RELATIONSHIP_OPTIONS,
)

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
# ICARUS AI — GRAPH INSIGHTS
# ─────────────────────────────────────────────────────────────────────────────
_BEST_PRACTICES = {
    "spend_delta": [
        {
            "text": "Maverick spend benchmark: world-class procurement organisations keep non-PO spend below 5% of total. Above 15%, a PO-mandate programme with finance sign-off gates is needed. PO compliance is the fastest lever to reduce invoice disputes and audit findings.",
            "source": "Hackett Group — Procurement Excellence Benchmark 2024",
            "url": "https://www.thehackettgroup.com/research/",
        },
        {
            "text": "Set sourcing event triggers at 20% YoY category growth — not after the budget overrun happens. Each percentage point of category savings outperforms volume reduction because it drops directly to EBITDA.",
            "source": "McKinsey — The CPO's Guide to Procurement Excellence",
            "url": "https://www.mckinsey.com/capabilities/operations/our-insights/the-cpos-guide-to-procurement-excellence",
        },
    ],
    "capex_opex": [
        {
            "text": "Cloud Reserved Instances and Savings Plans yield 30–60% vs on-demand pricing but behave like Capex commitments. Always model 1-year vs 3-year payback before committing — usage patterns change faster than RI terms.",
            "source": "FinOps Foundation — Cloud Rate Optimisation",
            "url": "https://www.finops.org/framework/capabilities/rate-optimization/",
        },
        {
            "text": "World-class IT organisations keep total Opex (SaaS + cloud subscriptions) below 12–15% of revenue. A SaaS rationalisation programme focused on licence utilisation and duplicate tooling typically returns 20–35% within 12 months.",
            "source": "Gartner — IT Key Metrics & IT Cost Benchmarks",
            "url": "https://www.gartner.com/en/information-technology/insights/it-metrics",
        },
    ],
    "treemap": [
        {
            "text": "No single supplier should represent >40% of category spend without a contracted price-lock and a qualified alternate. Single-source relationships without SLA financial penalties transfer all supply risk to the buyer with zero leverage.",
            "source": "ISM — Supply Chain Risk Management Framework",
            "url": "https://www.ismworld.org/supply-management-news-and-reports/reports/risk/",
        },
        {
            "text": "100% of spend above your materiality threshold should be under a signed contract. Contract coverage below 80% means invoices are approved against nothing — no price certainty, no SLA, no audit trail. Formalise spend before the next renewal cycle.",
            "source": "Ardent Partners — State of Procurement & Contract Management",
            "url": "https://ardentpartners.com/research/",
        },
    ],
}

# Categories displayed per chart (None = all 11 taxonomy categories)
_GRAPH_CATEGORIES = {
    "spend_delta": None,
    "capex_opex":  ["Cloud & Compute", "Hardware & Equipment", "Real Estate", "Facilities & Office"],
    "treemap":     None,
}

_GRAPH_KEYWORD_MAP = {
    "spend_delta": ["spend", "growth", "cost", "increase", "budget"],
    "capex_opex":  ["capex", "opex", "cloud", "hardware", "investment", "compute", "lease"],
    "treemap":     ["supplier", "concentration", "risk", "category", "single source"],
}

_IMPACT_PREFIX = {"negative": "↓", "positive": "↑", "neutral": "→"}
_IMPACT_C      = {"negative": RED, "positive": GREEN, "neutral": DIM}

# Category colour dots aligned to taxonomy
_CAT_DOT = {
    "Cloud & Compute":       "#378ADD",
    "AI/ML APIs & Data":     "#D4537E",
    "IT Software & SaaS":    "#534AB7",
    "Telecom & Voice":       "#1D9E75",
    "Recruitment & HR":      "#639922",
    "Professional Services": "#0F6E56",
    "Marketing & Campaigns": "#7F77DD",
    "Facilities & Office":   "#993C1D",
    "Real Estate":           "#8B6914",
    "Hardware & Equipment":  "#BA7517",
    "Travel & Expenses":     "#185FA5",
}

# Icarus AI eye SVG (for icon param on Panel buttons)
_ICARUS_AI_SVG = (
    '<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<polygon points="50,4 93,27 93,73 50,96 7,73 7,27" fill="rgba(255,255,255,0.15)" stroke="white" stroke-width="5"/>'
    '<path d="M28,50 Q50,28 72,50 Q50,72 28,50 Z" fill="none" stroke="#1D9E75" stroke-width="5"/>'
    '<circle cx="50" cy="50" r="10" fill="#1D9E75"/>'
    '</svg>'
)
# Inline eye used inside HTML panes
_EYE_HTML = (
    '<svg width="13" height="13" viewBox="0 0 100 100" fill="none" style="flex-shrink:0;vertical-align:middle">'
    '<polygon points="50,4 93,27 93,73 50,96 7,73 7,27" fill="#EDF0F7" stroke="#1B2A5E" stroke-width="5"/>'
    '<path d="M28,50 Q50,28 72,50 Q50,72 28,50 Z" fill="none" stroke="#1D9E75" stroke-width="4"/>'
    '<circle cx="50" cy="50" r="9" fill="#1D9E75"/></svg>'
)


def _signals_stale() -> bool:
    from datetime import timezone as _tz
    db = "clients/default/icarus_memory.db"
    if not os.path.exists(db):
        return True
    try:
        conn = sqlite3.connect(db)
        c    = conn.cursor()
        c.execute("SELECT timestamp FROM signals ORDER BY timestamp DESC LIMIT 1")
        row  = c.fetchone()
        conn.close()
        if not row:
            return True
        dt = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
        return (datetime.now(_tz.utc) - dt).days > 30
    except Exception:
        return True


def _build_data_bullets(graph_id: str, start_yr: int | None = None, end_yr: int | None = None) -> str:
    """Procurement insight bullets — period-specific for spend_delta, df_meta-driven for others."""
    try:
        dm = df_meta
    except NameError:
        dm = None

    def _row(icon, color, label, text):
        return (
            f'<div style="display:flex;gap:9px;align-items:flex-start;'
            f'padding:6px 0;border-bottom:1px solid #f4f6f8;">'
            f'<span style="color:{color};font-weight:700;font-size:14px;flex-shrink:0;margin-top:1px;">{icon}</span>'
            f'<div style="font-size:12px;font-family:-apple-system,sans-serif;flex:1;line-height:1.6;">'
            f'<span style="font-weight:700;color:#1B3A6B;">{label}:&nbsp;</span>'
            f'<span style="color:#333;">{text}</span>'
            f'</div></div>'
        )

    out = ""

    if graph_id == "spend_delta":
        # ── Period-specific analysis from CATEGORIES_RAW (zero API calls) ────────
        si = YEARS.index(start_yr) if start_yr in YEARS else 0
        ei = YEARS.index(end_yr)   if end_yr   in YEARS else len(YEARS) - 1
        if ei < si:
            si, ei = ei, si
            start_yr, end_yr = end_yr, start_yr
        n_yrs = ei - si  # number of years in the period

        # Build period deltas for all categories
        deltas = []
        for c in CATEGORIES_RAW:
            s0 = c["spend"][si]
            s1 = c["spend"][ei]
            delta = s1 - s0
            pct   = (s1 / s0 - 1) * 100 if s0 else 0.0
            cagr  = ((s1 / s0) ** (1 / n_yrs) - 1) * 100 if s0 and n_yrs > 0 else pct
            deltas.append({
                "name": c["name"], "s0": s0, "s1": s1, "delta": delta,
                "pct": pct, "cagr": cagr,
                "po": c["po_coverage_pct"], "cc": c["contract_coverage_pct"],
                "risk": c["risk"], "single_source": c["single_source"],
                "budget": c["budget"],
            })

        yrs_label = f"{start_yr}→{end_yr}" if start_yr != end_yr else str(start_yr)

        # 1 — Fastest growing categories in the selected period
        top3 = sorted(deltas, key=lambda x: x["pct"], reverse=True)[:3]
        lines = " · ".join(
            f"{d['name']} {d['pct']:+.0f}%" + (f" ({d['cagr']:+.0f}% pa)" if n_yrs > 1 else "")
            for d in top3
        )
        worst_pct = top3[0]["pct"] if top3 else 0
        color = RED if worst_pct > 50 else YELLOW if worst_pct > 25 else GREEN
        note = ("Growth above 25% outpaces typical savings — trigger sourcing events now before leverage is lost."
                if worst_pct > 25 else "Growth within manageable thresholds for the period.")
        out += _row("↑", color, f"Fastest growth {yrs_label}", f"{lines}. {note}")

        # 2 — Largest absolute spend increase & procurement action
        top_abs = max(deltas, key=lambda x: x["delta"])
        if top_abs["delta"] > 0:
            color = RED if top_abs["delta"] > 5000 else YELLOW if top_abs["delta"] > 2000 else GREEN
            action = ("Volume growth gives negotiating leverage — run competitive RFP before renewing."
                      if top_abs["pct"] > 30 else "Monitor trajectory; renew contract before next cycle.")
            out += _row("↑", color, "Largest spend increase",
                f"{top_abs['name']} +€{top_abs['delta']:,.0f}K ({top_abs['pct']:+.0f}% over "
                f"{n_yrs} yr{'s' if n_yrs > 1 else ''}). {action}")
        else:
            top_dec = min(deltas, key=lambda x: x["delta"])
            out += _row("↓", GREEN, "Spend reduction",
                f"{top_dec['name']} {top_dec['delta']:+,.0f}K ({top_dec['pct']:+.0f}%) — "
                "confirm cost avoidance is captured in savings tracker.")

        # 3 — PO compliance across all categories (maverick spend signal)
        low_po = [d for d in deltas if d["po"] < 70]
        if low_po:
            worst = min(low_po, key=lambda x: x["po"])
            out += _row("↓", RED, "Maverick spend risk",
                f"{worst['name']} PO coverage {worst['po']:.0f}% (target 80%+) — "
                f"{len(low_po)} categories below threshold. Mandate PO-first policy and block non-PO invoices.")
        else:
            avg_po = sum(d["po"] for d in deltas) / len(deltas) if deltas else 0
            out += _row("✓", GREEN, "PO compliance",
                f"Average PO coverage {avg_po:.0f}% — above 80% threshold across all categories. "
                "Continue enforcing PO-first policy.")

    elif graph_id == "capex_opex":
        if dm is None or dm.empty:
            return '<div style="color:#888;font-size:12px;padding:6px 0;font-family:-apple-system,sans-serif;">Upload spend data to see chart interpretation.</div>'
        if "capex_opex" in dm.columns and "spend_2026e" in dm.columns:
            capex = dm[dm["capex_opex"] == "Capex"]["spend_2026e"].sum()
            opex  = dm[dm["capex_opex"] == "Opex"]["spend_2026e"].sum()
            total = capex + opex
            if total > 0:
                opex_pct  = opex  / total * 100
                capex_pct = capex / total * 100

                # 1 — Opex/Capex ratio with industry benchmark
                color = YELLOW if opex_pct > 75 else GREEN
                note  = ("High Opex share — world-class IT Opex benchmark is <15% of revenue; "
                         "SaaS rationalisation typically delivers 20–35% reduction."
                         if opex_pct > 75 else
                         "Balanced investment/running-cost split. Review for hidden auto-renewal commitments.")
                out += _row("→", color, "Opex/Capex split",
                    f"Opex {opex_pct:.0f}% · Capex {capex_pct:.0f}% of managed spend. {note}")

                # 2 — Largest Capex exposure
                capex_cats = dm[dm["capex_opex"] == "Capex"].nlargest(1, "spend_2026e")
                if not capex_cats.empty:
                    top = capex_cats.iloc[0]
                    out += _row("↑", NAVY, "Largest Capex exposure",
                        f"{top['category']} €{top['spend_2026e']:,.0f}K. Evaluate Reserved Instances "
                        "or 3-year framework agreement to lock pricing before next renewal cycle.")

                # 3 — Fastest growing Opex (SaaS sprawl signal)
                if "cagr" in dm.columns:
                    opex_cats = dm[dm["capex_opex"] == "Opex"].nlargest(1, "cagr")
                    if not opex_cats.empty:
                        top   = opex_cats.iloc[0]
                        cagr  = top.get("cagr", 0)
                        color = RED if cagr > 30 else YELLOW if cagr > 15 else GREEN
                        out += _row("↑", color, "Fastest Opex growth",
                            f"{top['category']} {cagr:+.0f}% CAGR. Audit SLA terms, usage-based "
                            "pricing caps, and auto-renewal clauses before contract anniversary.")
        else:
            out += _row("→", DIM, "Classification", "Upload spend data with Capex/Opex classification to enable this analysis.")

    elif graph_id == "treemap":
        if dm is None or dm.empty:
            return '<div style="color:#888;font-size:12px;padding:6px 0;font-family:-apple-system,sans-serif;">Upload spend data to see chart interpretation.</div>'
        # 1 — Single source risk (highest priority procurement risk)
        if "single_source" in dm.columns and "spend_2026e" in dm.columns:
            ss = dm[dm["single_source"] == True].sort_values("spend_2026e", ascending=False)
            if not ss.empty:
                top = ss.iloc[0]
                out += _row("⚠", RED, "Single-source risk",
                    f"{len(ss)} categories single-sourced — {top['category']} "
                    f"€{top['spend_2026e']:,.0f}K highest exposure. "
                    "Issue RFI to qualify ≥1 alternative supplier and negotiate dual-source SLA.")

        # 2 — Contract coverage gap
        if "contract_coverage_pct" in dm.columns:
            low_cc = dm[dm["contract_coverage_pct"] < 80].sort_values("contract_coverage_pct")
            if not low_cc.empty:
                worst = low_cc.iloc[0]
                out += _row("↓", YELLOW, "Contract coverage gap",
                    f"{worst['category']} only {worst['contract_coverage_pct']:.0f}% of spend under contract "
                    f"({len(low_cc)} categories below 80% target). "
                    "Initiate contract formalisation — uncovered spend is maverick by definition.")
            else:
                avg_cc = dm["contract_coverage_pct"].mean()
                out += _row("✓", GREEN, "Contract coverage",
                    f"Average {avg_cc:.0f}% of spend under contract. Maintain renewal pipeline.")

        # 3 — Critical/High risk categories by spend
        if "risk" in dm.columns and "spend_2026e" in dm.columns:
            crit = dm[dm["risk"].isin(["Critical", "High"])].sort_values("spend_2026e", ascending=False)
            if not crit.empty:
                top   = crit.iloc[0]
                color = RED if top["risk"] == "Critical" else YELLOW
                out += _row("↓", color, "Risk-weighted spend",
                    f"{len(crit)} categories at Critical/High risk. Priority: "
                    f"{top['category']} €{top['spend_2026e']:,.0f}K — source second supplier, "
                    "negotiate financial SLA penalties, and set quarterly supplier scorecards.")

    return out or '<div style="color:#888;font-size:12px;padding:4px 0;">No data available.</div>'


def _build_signal_rows(cats: list) -> str:
    """Top 3 Icarus market signals for the relevant categories."""
    db = "clients/default/icarus_memory.db"
    _empty = (
        '<div style="color:#888;font-size:11.5px;font-family:-apple-system,sans-serif;padding:4px 0;">'
        'No market signals yet — click the ICARUS AI button or run a scan from the ICARUS tab.</div>'
    )
    if not os.path.exists(db):
        return _empty
    try:
        conn = sqlite3.connect(db)
        c    = conn.cursor()
        if cats:
            ph = ",".join("?" * len(cats))
            c.execute(
                f"SELECT headline, action, impact, category FROM signals "
                f"WHERE category IN ({ph}) ORDER BY relevance DESC, timestamp DESC LIMIT 3",
                cats,
            )
        else:
            c.execute(
                "SELECT headline, action, impact, category FROM signals "
                "ORDER BY relevance DESC, timestamp DESC LIMIT 3"
            )
        rows = c.fetchall()
        conn.close()
    except Exception:
        return _empty

    if not rows:
        return _empty

    out = ""
    for headline, action, impact, cat in rows:
        dot  = _CAT_DOT.get(cat, "#888")
        imp  = impact or "neutral"
        pre  = _IMPACT_PREFIX.get(imp, "→")
        ic   = _IMPACT_C.get(imp, DIM)
        head = (headline or "")[:90]
        act  = action or ""
        out += (
            f'<div style="display:flex;gap:8px;align-items:flex-start;'
            f'padding:4px 0;border-bottom:1px solid #f4f6f8;">'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{dot};'
            f'flex-shrink:0;margin-top:5px;"></span>'
            f'<div style="font-size:11.5px;font-family:-apple-system,sans-serif;flex:1;line-height:1.5;">'
            f'<span style="font-weight:600;color:{dot};">{cat}</span> '
            f'<span style="color:{ic};font-weight:600;">{pre}</span> '
            f'<span style="color:#333;">{head}</span>'
            + (f'<div style="font-size:10.5px;color:#0F6E56;margin-top:1px;">→ {act}</div>' if act else "")
            + '</div></div>'
        )
    return out


def _build_insight_html(graph_id: str, start_yr: int | None = None, end_yr: int | None = None) -> str:
    """Data interpretation + market signals + best practices for one Deep Dive chart."""
    _TITLES = {
        "spend_delta": "Spend Growth & Budget Analysis",
        "capex_opex":  "Capex vs Opex Interpretation",
        "treemap":     "Concentration & Risk Analysis",
    }
    title = _TITLES.get(graph_id, "Chart Analysis")
    cats  = _GRAPH_CATEGORIES.get(graph_id) or [c["name"] for c in CATEGORIES_RAW]
    stale = _signals_stale()
    stale_b = (
        '<span style="font-size:10px;color:#B8860B;background:#FFF8E0;padding:2px 7px;'
        'border-radius:99px;margin-left:8px;">market signals may be outdated — click 🔵 to refresh</span>'
        if stale else ""
    )

    data_html   = _build_data_bullets(graph_id, start_yr, end_yr)
    signal_html = _build_signal_rows(cats)
    bp_html     = ""
    for bp in _BEST_PRACTICES.get(graph_id, []):
        bp_html += (
            f'<div style="display:flex;gap:9px;align-items:flex-start;padding:5px 0;">'
            f'<span style="font-size:13px;flex-shrink:0;">📌</span>'
            f'<div style="font-size:12px;color:#444;line-height:1.55;font-family:-apple-system,sans-serif;">'
            f'{bp["text"]}'
            f'<a href="{bp["url"]}" target="_blank" rel="noopener noreferrer" '
            f'style="display:inline-flex;align-items:center;gap:3px;margin-left:6px;font-size:10px;'
            f'color:#2E5BA8;text-decoration:none;background:#EFF3FB;padding:1px 7px;'
            f'border-radius:99px;white-space:nowrap;">↗ {bp["source"]}</a>'
            f'</div></div>'
        )

    return (
        f'<div style="background:#F8FAFE;border:1px solid #E2E8F0;border-radius:8px;'
        f'padding:12px 16px;margin-top:4px;">'
        f'<div style="display:flex;align-items:center;margin-bottom:8px;gap:6px;">'
        f'{_EYE_HTML}'
        f'<span style="font-size:11px;font-weight:700;color:#1B3A6B;text-transform:uppercase;'
        f'letter-spacing:0.8px;font-family:-apple-system,sans-serif;">ICARUS AI — {title}</span>'
        f'</div>'
        f'{data_html}'
        f'<div style="border-top:1px solid #E2E8F0;margin:10px 0 8px;"></div>'
        f'<div style="display:flex;align-items:center;margin-bottom:6px;gap:5px;">'
        f'<span style="font-size:11px;font-weight:600;color:#64748B;text-transform:uppercase;'
        f'letter-spacing:0.7px;font-family:-apple-system,sans-serif;">Market Intelligence</span>'
        f'{stale_b}</div>'
        f'{signal_html}'
        f'<div style="border-top:1px solid #E2E8F0;margin:10px 0 8px;"></div>'
        f'<div style="display:flex;align-items:center;margin-bottom:6px;gap:6px;">'
        f'<span style="font-size:13px;">📚</span>'
        f'<span style="font-size:11px;font-weight:700;color:#1B3A6B;text-transform:uppercase;'
        f'letter-spacing:0.8px;font-family:-apple-system,sans-serif;">Best Practice</span>'
        f'</div>{bp_html}</div>'
    )


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

        # Step 7: Supplier profiles — ABC tiers + compliance scores
        status_callback("🏆 Computing supplier ABC tiers...")
        conn = get_connection("default")
        compute_and_save_profiles(conn, "default")
        conn.close()
        status_callback("🏆 Supplier profiles updated")

        # Step 8: Update dashboard
        status_callback("📊 Updating dashboard...")
        dashboard_callback(flagged_df, filename)
        refresh_compliance_tab()
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
_NO_MODEBAR = {"displayModeBar": False}
cagr_pane       = pn.pane.Plotly(sizing_mode="stretch_width", config=_NO_MODEBAR)
treemap_pane      = pn.pane.Plotly(sizing_mode="stretch_width", config=_NO_MODEBAR)
supplier_detail   = pn.pane.HTML("", sizing_mode="stretch_width")
supplier_news     = pn.pane.HTML("", sizing_mode="stretch_width")
fetch_signals_btn = pn.widgets.Button(name="🔍 Fetch latest signals", button_type="primary",
                                      width=200, margin=(8, 0, 0, 0))
treemap_back      = pn.widgets.Button(name="← Back to category view", button_type="light",
                                      width=200, margin=(0, 0, 8, 0))
treemap_frame     = pn.Column(sizing_mode="stretch_width")
_current_supplier = [""]  # mutable box for the fetch button callback

# ── Persistent insight strips (Deep Dive) ────────────────────────────────────
insight_spend_delta = pn.pane.HTML("", sizing_mode="stretch_width")
insight_capex_opex  = pn.pane.HTML("", sizing_mode="stretch_width")
insight_treemap     = pn.pane.HTML("", sizing_mode="stretch_width")

# ── Round animated ICARUS AI buttons ─────────────────────────────────────────
import icarus as _icarus_mod

_BTN_STYLE = ["""
    :host{display:inline-flex;align-items:center;}
    .bk-btn{
        width:34px!important;height:34px!important;border-radius:50%!important;
        padding:0!important;background:#1B3A6B!important;border-color:#1B3A6B!important;
        display:flex!important;align-items:center!important;justify-content:center!important;
        box-shadow:0 2px 10px rgba(27,58,107,0.35)!important;
    }
    .bk-btn:hover{background:#2E5BA8!important;border-color:#2E5BA8!important;
                  box-shadow:0 4px 14px rgba(27,58,107,0.45)!important;}
"""]


def _make_icarus_ai_btn(graph_id: str, insight_pane: pn.pane.HTML) -> pn.widgets.Button:
    """Round ICARUS AI button — spins (via Panel loading state) while refreshing."""
    btn = pn.widgets.Button(
        name="", icon=_ICARUS_AI_SVG, icon_size="18px",
        width=34, height=34, margin=(0, 0, 0, 0),
        stylesheets=_BTN_STYLE,
    )

    def _on_click(_):
        btn.loading = True
        def _do():
            try:
                cats   = list(df_meta["category"].dropna().unique()) if "category" in df_meta.columns else []
                kws    = ", ".join(_GRAPH_KEYWORD_MAP.get(graph_id, [])[:3])
                result = _icarus_mod.query_with_claude(
                    query=f"Latest procurement signals for {graph_id.replace('_', ' ')}: {kws}",
                    client_categories=cats, client_name="Client",
                )
                if result.get("signals"):
                    _icarus_mod.init_db()
                    qid = _icarus_mod.save_query(cats, 0, len(result["signals"]))
                    _icarus_mod.save_signals(qid, result["signals"])
            except Exception as e:
                print(f"[ICARUS AI] refresh error ({graph_id}): {e}")
            finally:
                insight_pane.object = _build_insight_html(graph_id)
                btn.loading = False
        threading.Thread(target=_do, daemon=True).start()

    btn.on_click(_on_click)
    return btn


icarus_btn_delta   = _make_icarus_ai_btn("spend_delta", insight_spend_delta)
icarus_btn_capex   = _make_icarus_ai_btn("capex_opex",  insight_capex_opex)
icarus_btn_treemap = _make_icarus_ai_btn("treemap",     insight_treemap)


def refresh_all_insights():
    """Populate all Deep Dive insight strips — spend_delta uses selected period."""
    insight_spend_delta.object = _build_insight_html("spend_delta", cagr_start.value, cagr_end.value)
    insight_capex_opex.object  = _build_insight_html("capex_opex")
    insight_treemap.object     = _build_insight_html("treemap")


# ─────────────────────────────────────────────────────────────────────────────
# COMPLIANCE SCORECARD TAB
# ─────────────────────────────────────────────────────────────────────────────

_RISK_BADGE  = {"Critical": RED, "High": YELLOW, "Medium": "#E67E22", "Low": GREEN}

# Holds the current supplier DataFrame shown in the tab
_sc_df: pd.DataFrame = build_demo_profiles()

# Panes updated by refresh functions
_sc_score_pane  = pn.pane.HTML("", sizing_mode="stretch_width")
_sc_table_pane  = pn.Column(sizing_mode="stretch_width")
_sc_maverick_pane = pn.pane.Plotly(sizing_mode="stretch_width", config=_NO_MODEBAR)
_sc_expiry_pane   = pn.pane.Plotly(sizing_mode="stretch_width", config=_NO_MODEBAR)

# Active tier filter ("All", "A", "B", "C")
_sc_tier_filter = pn.widgets.ToggleGroup(
    name="", options=["All", "A", "B", "C"], value="All",
    behavior="radio", button_type="light",
    stylesheets=["""
        :host{margin:0;}
        .bk-btn-group{display:flex;gap:6px;}
        .bk-btn{height:28px;padding:0 14px;border-radius:99px;font-size:12px;
                font-weight:600;border:1.5px solid #D0DAF0;color:#1B3A6B;
                background:white;font-family:-apple-system,sans-serif;}
        .bk-btn.bk-active{background:#1B3A6B;color:white;border-color:#1B3A6B;}
    """],
)


def _sc_overall_score(df: pd.DataFrame) -> dict:
    """Compute org-level compliance dimensions from the supplier DataFrame."""
    if df.empty:
        return {"score": 0, "po": 0, "cc": 0, "maverick": 12, "spm": 0}
    # Weight dimensions by tier: A=3, B=2, C=1
    w_map = {"A": 3, "B": 2, "C": 1}
    weights = df["tier"].map(w_map).fillna(1)
    po  = round((df["po_coverage_pct"] * weights).sum() / weights.sum())
    cc_num = df["contract_status"].map(
        {"Under Contract": 100, "Expired": 40, "No Contract": 0, "Unknown": 50}
    ).fillna(50)
    cc  = round((cc_num * weights).sum() / weights.sum())
    sc  = round((df["compliance_score"] * weights).sum() / weights.sum())
    return {"score": sc, "po": po, "cc": cc}


def _build_sc_score_html(df: pd.DataFrame) -> str:
    dims = _sc_overall_score(df)
    sc   = dims["score"]
    band = ("World-class" if sc >= 85 else "Improving" if sc >= 70
            else "At Risk" if sc >= 50 else "Critical")
    color = GREEN if sc >= 85 else NAVY2 if sc >= 70 else YELLOW if sc >= 50 else RED
    tier_counts = df["tier"].value_counts().to_dict()
    a_cnt = tier_counts.get("A", 0)
    b_cnt = tier_counts.get("B", 0)
    c_cnt = tier_counts.get("C", 0)
    return f"""
<div style="background:{NAVY};border-radius:12px;padding:20px 28px;
            display:flex;align-items:center;gap:32px;flex-wrap:wrap;
            font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="display:flex;flex-direction:column;align-items:center;min-width:90px;">
    <div style="font-size:48px;font-weight:800;color:{color};line-height:1;">{sc:.0f}</div>
    <div style="font-size:11px;color:rgba(255,255,255,0.6);margin-top:2px;">/ 100</div>
    <div style="font-size:12px;font-weight:700;color:{color};margin-top:4px;">{band}</div>
  </div>
  <div style="flex:1;display:flex;gap:24px;flex-wrap:wrap;">
    <div style="text-align:center;">
      <div style="font-size:22px;font-weight:700;color:white;">{dims['po']}%</div>
      <div style="font-size:10px;color:rgba(255,255,255,0.55);text-transform:uppercase;letter-spacing:1px;">PO Coverage</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:22px;font-weight:700;color:white;">{dims['cc']}%</div>
      <div style="font-size:10px;color:rgba(255,255,255,0.55);text-transform:uppercase;letter-spacing:1px;">Contract Coverage</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:22px;font-weight:700;color:white;">{a_cnt}</div>
      <div style="font-size:10px;color:rgba(255,255,255,0.55);text-transform:uppercase;letter-spacing:1px;">A Suppliers</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:22px;font-weight:700;color:white;">{b_cnt}</div>
      <div style="font-size:10px;color:rgba(255,255,255,0.55);text-transform:uppercase;letter-spacing:1px;">B Suppliers</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:22px;font-weight:700;color:white;">{c_cnt}</div>
      <div style="font-size:10px;color:rgba(255,255,255,0.55);text-transform:uppercase;letter-spacing:1px;">C Suppliers</div>
    </div>
  </div>
  <div style="font-size:10px;color:rgba(255,255,255,0.4);align-self:flex-end;">
    Score = PO(35%) · Contract(35%) · Concentration(20%) · Maverick(10%) · weighted by tier
  </div>
</div>"""


def _build_supplier_tabulator(df: pd.DataFrame, tier: str = "All") -> pn.widgets.Tabulator:
    """Build editable Tabulator for the compliance supplier table."""
    filtered = df if tier == "All" else df[df["tier"] == tier].copy()
    display = filtered[[
        "vendor_name", "category", "tier", "relationship_status",
        "total_spend", "po_coverage_pct", "contract_status",
        "contract_end", "risk_level", "compliance_score",
    ]].copy()
    display.columns = [
        "Supplier", "Category", "Tier", "Relationship",
        "Spend €K", "PO %", "Contract", "Expiry", "Risk", "Score",
    ]
    display["Spend €K"] = display["Spend €K"].round(0).astype(int)
    display["PO %"]     = display["PO %"].round(0).astype(int)
    display["Score"]    = display["Score"].round(1)

    table = pn.widgets.Tabulator(
        display,
        sizing_mode="stretch_width",
        height=420,
        theme="bootstrap",
        page_size=20,
        show_index=False,
        editors={
            "Category":     {"type": "select", "values": TAXONOMY},
            "Relationship": {"type": "select", "values": RELATIONSHIP_OPTIONS},
            "Tier":         {"type": "select", "values": ["A", "B", "C"]},
        },
        frozen_columns=["Supplier"],
        text_align={"Score": "center", "Tier": "center", "PO %": "center"},
        widths={
            "Supplier": 160, "Category": 170, "Tier": 60,
            "Relationship": 130, "Spend €K": 90, "PO %": 65,
            "Contract": 130, "Expiry": 95, "Risk": 80, "Score": 70,
        },
        stylesheets=["""
            .tabulator{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                       font-size:12px;border:1px solid #E2E8F0;border-radius:8px;}
            .tabulator .tabulator-header .tabulator-col{
                background:#F8F9FA;color:#1B3A6B;font-weight:700;
                font-size:11px;text-transform:uppercase;letter-spacing:0.5px;}
            .tabulator .tabulator-row:hover{background:#F0F4FF;}
        """],
    )

    def _on_edit(event):
        global _sc_df
        col_map = {
            "Category": "category", "Relationship": "relationship_status", "Tier": "tier"
        }
        field = col_map.get(event.column)
        if not field:
            return
        supplier = display.iloc[event.row]["Supplier"]
        try:
            conn = get_connection("default")
            update_supplier_field(conn, "default", supplier, field, event.value)
            conn.close()
            _sc_df.loc[_sc_df["vendor_name"] == supplier, field] = event.value
            _sc_score_pane.object = _build_sc_score_html(_sc_df)
        except Exception as e:
            print(f"[Scorecard] edit error: {e}")

    table.on_edit(_on_edit)
    return table


def _chart_maverick_trend() -> go.Figure:
    """Line chart of maverick spend % over 2022–2026 with 5% target line."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=YEARS, y=MAVERICK_PCT, mode="lines+markers",
        name="Maverick Spend", line=dict(color=RED, width=2.5),
        marker=dict(size=7, color=RED),
    ))
    fig.add_trace(go.Scatter(
        x=[YEARS[0], YEARS[-1]], y=[5, 5], mode="lines",
        name="Target 5%", line=dict(color=GREEN, width=1.5, dash="dash"),
    ))
    fig.add_hrect(y0=5, y1=max(MAVERICK_PCT) + 2,
                  fillcolor="rgba(192,57,43,0.06)", line_width=0)
    fig.update_layout(
        **LAYOUT,
        title=dict(text="Maverick Spend Trend (%)", font=dict(size=13, color=NAVY)),
        yaxis=dict(title="% of total spend", ticksuffix="%", range=[0, max(MAVERICK_PCT) + 3]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=280,
    )
    return fig


def _chart_expiry_gantt() -> go.Figure:
    """Contract expiry scatter — suppliers plotted by expiry date, sized by value."""
    rows = [r for r in CONTRACTS_DATA if r["Expiry"] != "N/A"]
    if not rows:
        return go.Figure()
    expiry_dates = [r["Expiry"] for r in rows]
    suppliers    = [r["Supplier"] for r in rows]
    values       = [r["Value €K"] for r in rows]
    risks        = [r["Risk"] for r in rows]
    colors       = [_RISK_BADGE.get(r, DIM) for r in risks]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=expiry_dates,
        y=suppliers,
        mode="markers+text",
        marker=dict(
            size=[max(10, min(v / 300, 40)) for v in values],
            color=colors, opacity=0.85,
            line=dict(width=1.5, color="white"),
        ),
        text=[f"€{v:,}K" for v in values],
        textposition="middle right",
        textfont=dict(size=10, color=TEXT),
        hovertemplate=(
            "<b>%{y}</b><br>Expiry: %{x}<br>"
            + "<br>".join(f"€{v:,}K" for v in values)
            + "<extra></extra>"
        ),
    ))
    fig.update_layout(
        **LAYOUT,
        title=dict(text="Contract Expiry Timeline (bubble = contract value)",
                   font=dict(size=13, color=NAVY)),
        xaxis=dict(title="", type="date"),
        yaxis=dict(title="", autorange="reversed"),
        height=320,
        margin=dict(l=130, r=80, t=50, b=40),
        showlegend=False,
    )
    return fig


def refresh_compliance_tab():
    """Reload supplier data and redraw all compliance scorecard panes."""
    global _sc_df
    try:
        conn = get_connection("default")
        _sc_df = get_supplier_profiles(conn, "default")
        conn.close()
    except Exception:
        _sc_df = build_demo_profiles()

    tier = _sc_tier_filter.value
    _sc_score_pane.object = _build_sc_score_html(_sc_df)
    _sc_table_pane.clear()
    _sc_table_pane.append(_build_supplier_tabulator(_sc_df, tier))
    _sc_maverick_pane.object = _chart_maverick_trend()
    _sc_expiry_pane.object   = _chart_expiry_gantt()


def _on_tier_filter(event):
    tier = event.new
    _sc_table_pane.clear()
    _sc_table_pane.append(_build_supplier_tabulator(_sc_df, tier))

_sc_tier_filter.param.watch(_on_tier_filter, "value")

# ── Build the static Compliance Scorecard tab column ─────────────────────────
_compliance_tab = pn.Column(
    pn.pane.HTML(
        f'<div style="font-family:Georgia,serif;font-size:18px;font-weight:700;'
        f'color:{NAVY};padding:8px 0 4px;">Supplier Compliance Scorecard</div>'
        f'<div style="font-size:12px;color:{DIM};font-family:-apple-system,sans-serif;'
        f'padding-bottom:12px;">ABC tiers auto-computed from spend. Edit Category, Tier, '
        f'or Relationship inline — changes persist and feed back into future uploads.</div>',
        sizing_mode="stretch_width",
    ),
    _sc_score_pane,
    pn.layout.Divider(),
    pn.Row(
        pn.pane.HTML(
            f'<span style="font-size:12px;font-weight:600;color:{NAVY};'
            f'font-family:-apple-system,sans-serif;">Filter by tier:</span>',
            align="center",
        ),
        _sc_tier_filter,
        sizing_mode="stretch_width",
        align="center",
        styles={"padding": "4px 0 10px"},
    ),
    _sc_table_pane,
    pn.layout.Divider(),
    pn.Row(
        pn.Column(
            section_header("📈 Maverick Spend Trend"),
            _sc_maverick_pane,
            sizing_mode="stretch_width",
        ),
        pn.Column(
            section_header("📅 Contract Expiry Timeline"),
            _sc_expiry_pane,
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
    ),
    sizing_mode="stretch_width",
)


# ── Floating ICARUS AI FAB — rendered into document.body via script ───────────
# Panel/Bokeh wraps components in transform containers which break position:fixed.
# Fix: render FAB as raw HTML and move it to document.body from a script so it
# sits outside any transformed ancestor. Python bridge uses named Bokeh models.

_fab_query_bridge = pn.widgets.TextInput(
    name="fab_query_bridge",
    value="",
    stylesheets=[":host{display:none!important;}"],
)
_fab_result_store = pn.pane.HTML(
    '<div id="sl-fab-result-store"></div>',
    sizing_mode="stretch_width",
    stylesheets=[":host{display:none!important;}"],
)

_fab_ui_html = pn.pane.HTML(f"""
<script>
// ── ICARUS AI FAB — injected directly into document.body/head ─────────────────
// Panel/Bokeh wraps pane content in transform:translate() containers which create
// a new stacking context and break position:fixed.  Fix: build the FAB elements
// in JS, inject CSS into <head> (outside any shadow/transform boundary), and
// append the DOM nodes straight to document.body so position:fixed is always
// relative to the viewport.
(function(){{
  if(document.getElementById('sl-fab-btn'))return; // guard against double-mount

  // ── 1. Inject CSS into <head> so it is never trapped in a stacking context ──
  var style=document.createElement('style');
  style.id='sl-fab-styles';
  style.textContent=[
    '#sl-fab-btn{{position:fixed;bottom:24px;right:24px;z-index:9999;width:52px;height:52px;',
    '  border-radius:50%;border:none;cursor:pointer;background:#1B3A6B;',
    '  box-shadow:0 4px 16px rgba(27,58,107,0.4);display:flex;align-items:center;',
    '  justify-content:center;transition:background 0.15s;padding:0;}}',
    '#sl-fab-btn:hover{{background:#2E5BA8;}}',
    '#sl-fab-chat{{position:fixed;bottom:84px;right:24px;z-index:9998;width:340px;',
    '  background:white;border-radius:14px;padding:16px;display:none;',
    '  box-shadow:0 8px 32px rgba(27,58,107,0.18);border:1px solid #E2E8F0;',
    '  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}}',
    '#sl-fab-hdr{{display:flex;align-items:center;gap:6px;margin-bottom:10px;}}',
    '#sl-fab-close{{margin-left:auto;background:none;border:none;cursor:pointer;',
    '  font-size:16px;color:#888;line-height:1;}}',
    '#sl-fab-input-row{{display:flex;gap:6px;}}',
    '#sl-fab-input{{flex:1;height:34px;border:1.5px solid #D0DAF0;border-radius:8px;',
    '  padding:0 10px;font-size:13px;background:#fafafa;outline:none;}}',
    '#sl-fab-input:focus{{border-color:#1B3A6B;background:white;}}',
    '#sl-fab-send{{width:36px;height:34px;border:none;border-radius:8px;cursor:pointer;',
    '  background:#1B3A6B;color:white;font-size:16px;font-weight:700;}}',
    '#sl-fab-send:hover{{background:#2E5BA8;}}',
    '#sl-fab-result{{margin-top:10px;font-size:13px;color:#1a1a2e;line-height:1.7;}}'
  ].join('');
  document.head.appendChild(style);

  // ── 2. Build FAB button and append to document.body ──────────────────────────
  var btn=document.createElement('button');
  btn.id='sl-fab-btn';
  btn.title='ICARUS AI';
  btn.innerHTML='{_ICARUS_AI_SVG}';
  document.body.appendChild(btn);

  // ── 3. Build chat panel and append to document.body ──────────────────────────
  var chat=document.createElement('div');
  chat.id='sl-fab-chat';
  chat.innerHTML=[
    '<div id="sl-fab-hdr">',
    '  {_EYE_HTML}',
    '  &nbsp;<span style="font-size:13px;font-weight:700;color:#1B3A6B;',
    '    font-family:-apple-system,sans-serif;">ICARUS AI</span>',
    '  <button id="sl-fab-close">&#x2715;</button>',
    '</div>',
    '<div id="sl-fab-input-row">',
    '  <input id="sl-fab-input" type="text" placeholder="Ask about your spend…">',
    '  <button id="sl-fab-send">&#x2192;</button>',
    '</div>',
    '<div id="sl-fab-result"></div>'
  ].join('');
  document.body.appendChild(chat);

  // ── 4. Wire interactions ──────────────────────────────────────────────────────
  var close=document.getElementById('sl-fab-close');
  var inp=document.getElementById('sl-fab-input');
  var send=document.getElementById('sl-fab-send');
  var result=document.getElementById('sl-fab-result');

  btn.onclick=function(){{
    chat.style.display=chat.style.display==='none'||chat.style.display===''?'block':'none';
  }};
  if(close)close.onclick=function(){{chat.style.display='none';}};

  function sendQ(){{
    var q=inp.value.trim();
    if(!q)return;
    result.innerHTML='<span style="color:#888;">Thinking…</span>';
    try{{
      var bridge=Bokeh.documents[0].get_model_by_name('fab_query_bridge');
      if(bridge){{bridge.value=q;}}
    }}catch(e){{result.textContent='Could not reach ICARUS AI.';}}
  }}
  send.onclick=sendQ;
  inp.onkeydown=function(e){{if(e.key==='Enter')sendQ();}};

  // ── 5. Watch result-store div for Python→JS response updates ─────────────────
  var observer=new MutationObserver(function(){{
    var store=document.getElementById('sl-fab-result-store');
    if(store&&store.innerHTML.trim()){{result.innerHTML=store.innerHTML;}}
  }});
  function attachObs(){{
    var store=document.getElementById('sl-fab-result-store');
    if(store){{observer.observe(store,{{childList:true,subtree:true,characterData:true}});}}
    else{{setTimeout(attachObs,500);}}
  }}
  attachObs();
}})();
</script>
""", sizing_mode="stretch_width")


def _fab_ask(event):
    q = (event.new or "").strip()
    if not q:
        return

    def _do():
        try:
            cats = list(df_meta["category"].dropna().unique()) if "category" in df_meta.columns else []
            res  = _icarus_mod.query_with_claude(q, cats, "Client")
            ans  = res.get("answer", "No response received.")
            _fab_result_store.object = (
                f'<div id="sl-fab-result-store" style="font-size:13px;color:#1a1a2e;'
                f'line-height:1.7;">{ans}</div>'
            )
        except Exception as ex:
            _fab_result_store.object = (
                f'<div id="sl-fab-result-store" style="color:{RED};font-size:12px;">Error: {ex}</div>'
            )
        finally:
            _fab_query_bridge.value = ""

    threading.Thread(target=_do, daemon=True).start()

_fab_query_bridge.param.watch(_fab_ask, "value")

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
            pn.pane.Plotly(chart_spend_stacked(ds_trend),              sizing_mode="stretch_width", config=_NO_MODEBAR),
            pn.pane.Plotly(chart_category_bars(dm, year_label),        sizing_mode="stretch_width", config=_NO_MODEBAR),
        ),
    ])

    # ── Section 2: Risk & Bottlenecks ──
    chart_s2.clear()
    chart_s2.extend([
        section_header("⚠ Risk & Bottlenecks"),
        pn.pane.Plotly(chart_risk_bubble(dm), sizing_mode="stretch_width", config=_NO_MODEBAR),
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
            pn.pane.Plotly(chart_ebitda_waterfall(ebitda_yr),          sizing_mode="stretch_width", config=_NO_MODEBAR),
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
            pn.Column(
                pn.Row(
                    pn.pane.HTML(f"<span style='font-size:13px;font-weight:600;color:{NAVY};font-family:Georgia,serif;'>Spend by category</span>",
                                 margin=(0, 0, 0, 0)),
                    pn.Spacer(sizing_mode="stretch_width"),
                    icarus_btn_delta,
                    align="center",
                    sizing_mode="stretch_width",
                ),
                cagr_pane,
                insight_spend_delta,
                sizing_mode="stretch_width",
            ),
            pn.Column(
                pn.Row(
                    pn.pane.HTML(f"<span style='font-size:13px;font-weight:600;color:{NAVY};font-family:Georgia,serif;'>Capex vs Opex spend per year</span>",
                                 margin=(0, 0, 0, 0)),
                    pn.Spacer(sizing_mode="stretch_width"),
                    icarus_btn_capex,
                    align="center",
                    sizing_mode="stretch_width",
                ),
                pn.pane.Plotly(chart_capex_opex(), sizing_mode="stretch_width", config=_NO_MODEBAR),
                insight_capex_opex,
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        ),
        pn.Row(
            pn.pane.HTML(f"<span style='font-size:13px;font-weight:600;color:{NAVY};font-family:Georgia,serif;'>Spend by Category × Risk</span>",
                         margin=(8, 0, 0, 0)),
            pn.Spacer(sizing_mode="stretch_width"),
            icarus_btn_treemap,
            align="center",
            sizing_mode="stretch_width",
        ),
        treemap_frame,
        insight_treemap,
    ])
    cagr_pane.object   = build_spend_delta_chart(cagr_start.value, cagr_end.value)
    treemap_pane.object = chart_treemap(dm)
    treemap_frame.objects = [treemap_pane]
    refresh_all_insights()

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
        refresh_all_insights()


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
    insight_spend_delta.object = _build_insight_html("spend_delta", cagr_start.value, cagr_end.value)

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
pn.state.onload(icarus_panel.load_recent)
pn.state.onload(refresh_all_insights)
pn.state.onload(refresh_compliance_tab)

def handle_icarus(event):
    status_log.object = "🪶 Icarus crawl started — check the Icarus tab for results..."
    icarus_panel.run()

icarus_btn.on_click(handle_icarus)

tabs = pn.Tabs(
    ("Dashboard", main_tab),
    ("Deep Dive", chart_deep),
    ("📋 Compliance", _compliance_tab),
    ("🪶 ICARUS AI", icarus_panel.view()),
    sizing_mode="stretch_width",
)

# Hide dashboard sidebar when user switches to the Icarus tab (index 2)
def _on_tab_change(event):
    _dash_sidebar.visible = (event.new != 3)  # hide sidebar on ICARUS AI tab (index 3)

tabs.param.watch(_on_tab_change, 'active')

template = pn.template.FastListTemplate(
    title="SpendLens",
    sidebar=[sidebar_col],
    main=[tabs, _fab_ui_html, _fab_result_store, _fab_query_bridge],
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
