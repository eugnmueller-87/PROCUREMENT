"""
SpendLens — AI-Powered Procurement Intelligence Dashboard
Built with Panel + Plotly + Claude AI

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
import param
import io
import os
from datetime import datetime

from modules.column_mapper import rule_based_mapping, ai_column_mapping, apply_mapping
from modules.data_cleanup import full_cleanup, clean_column_names
from modules.cfo_reports import export_cfo_excel, generate_executive_summary

# ─── Extensions ───
pn.extension("plotly", sizing_mode="stretch_width")

# ─── Theme ───
BG       = "#0B0E14"
CARD     = "#141820"
GRID     = "#1E2430"
TEXT     = "#E4E8F1"
DIM      = "#6B7A94"
ACCENT   = "#FF6B4A"
BLUE     = "#3B82F6"
GREEN    = "#34D399"
YELLOW   = "#FBBF24"
RED      = "#EF4444"

COLORS = ["#FF6B4A", "#3B82F6", "#34D399", "#FBBF24", "#A78BFA",
          "#F472B6", "#FB923C", "#06B6D4", "#E879F9", "#84CC16"]

RISK_COLORS = {"Critical": RED, "High": YELLOW, "Medium": "#FB923C", "Low": GREEN}

LAYOUT = dict(
    paper_bgcolor=BG,
    plot_bgcolor=CARD,
    font=dict(family="Arial, sans-serif", color=TEXT, size=12),
    margin=dict(l=60, r=30, t=50, b=40),
    xaxis=dict(gridcolor=GRID, linecolor=GRID),
    yaxis=dict(gridcolor=GRID, linecolor=GRID),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
)

CSS = """
body {
    background-color: #0B0E14 !important;
    color: #E4E8F1 !important;
}
.bk-root {
    background-color: #0B0E14 !important;
}
.card-style {
    background-color: #141820;
    border-radius: 12px;
    padding: 20px;
    border: 1px solid #1E2430;
}
"""
pn.config.raw_css.append(CSS)


# ─────────────────────────────────────────────
# LOAD DEFAULT DATA (from your Parloa notebook)
# ─────────────────────────────────────────────
def load_parloa_default() -> pd.DataFrame:
    """Load the default Parloa dataset from your notebook."""
    YEARS = [2022, 2023, 2024, 2025, 2026]
    categories_raw = [
        {"name": "Cloud & Compute", "spend": [4200, 7800, 12500, 17800, 24000],
         "concentration": 72, "risk": "Critical", "single_source": True,
         "suppliers": "AWS, Google Cloud, Azure", "lead_time_days": 0, "contract_end": "2026-09"},
        {"name": "AI/ML APIs & Data", "spend": [800, 2200, 4800, 6500, 9200],
         "concentration": 55, "risk": "High", "single_source": False,
         "suppliers": "OpenAI, Anthropic, Scale AI", "lead_time_days": 14, "contract_end": "2026-06"},
        {"name": "IT Software & SaaS", "spend": [900, 1400, 2200, 3100, 4200],
         "concentration": 22, "risk": "Low", "single_source": False,
         "suppliers": "GitHub, Datadog, Atlassian", "lead_time_days": 7, "contract_end": "Various"},
        {"name": "Recruitment", "spend": [600, 1100, 2400, 4200, 6800],
         "concentration": 35, "risk": "High", "single_source": False,
         "suppliers": "Personio, LinkedIn, Agencies", "lead_time_days": 45, "contract_end": "2026-12"},
        {"name": "Professional Services", "spend": [400, 700, 1200, 2100, 3200],
         "concentration": 40, "risk": "Medium", "single_source": False,
         "suppliers": "Big 4, Baker McKenzie", "lead_time_days": 21, "contract_end": "2026-03"},
        {"name": "Marketing & Events", "spend": [300, 800, 1800, 3500, 5500],
         "concentration": 28, "risk": "Medium", "single_source": False,
         "suppliers": "Event Agencies, Google Ads", "lead_time_days": 30, "contract_end": "Various"},
        {"name": "Facilities & Office", "spend": [500, 900, 1500, 2800, 4800],
         "concentration": 45, "risk": "High", "single_source": False,
         "suppliers": "Landlords, WeWork", "lead_time_days": 90, "contract_end": "2028-06"},
        {"name": "Travel & Entertainment", "spend": [200, 500, 1100, 2000, 3200],
         "concentration": 30, "risk": "Low", "single_source": False,
         "suppliers": "TMC, Airlines, Navan", "lead_time_days": 3, "contract_end": "2026-09"},
        {"name": "Hardware & Equipment", "spend": [300, 500, 900, 1500, 2400],
         "concentration": 38, "risk": "Medium", "single_source": False,
         "suppliers": "Apple, Dell, NVIDIA", "lead_time_days": 56, "contract_end": "N/A"},
        {"name": "Telco & Voice Infra", "spend": [400, 800, 1400, 2200, 3000],
         "concentration": 65, "risk": "Critical", "single_source": True,
         "suppliers": "Twilio, Vonage, DT", "lead_time_days": 30, "contract_end": "2026-07"},
    ]

    # Spend over time
    spend_rows = []
    for cat in categories_raw:
        for i, year in enumerate(YEARS):
            spend_rows.append({"category": cat["name"], "year": year, "spend": cat["spend"][i]})

    # Metadata
    meta_rows = [{
        "category": c["name"], "spend_2026e": c["spend"][4],
        "concentration": c["concentration"], "risk": c["risk"],
        "single_source": c["single_source"], "suppliers": c["suppliers"],
        "lead_time_days": c["lead_time_days"], "contract_end": c["contract_end"],
        "cagr": round(((c["spend"][4] / c["spend"][0]) ** (1/4) - 1) * 100, 1),
    } for c in categories_raw]

    return pd.DataFrame(spend_rows), pd.DataFrame(meta_rows)


# ─────────────────────────────────────────────
# CHARTS
# ─────────────────────────────────────────────
def chart_spend_over_time(df_spend: pd.DataFrame) -> go.Figure:
    """Stacked area chart of spend by category over time."""
    fig = go.Figure()
    categories = df_spend.groupby("category")["spend"].sum().sort_values().index

    for i, cat in enumerate(categories):
        cat_data = df_spend[df_spend["category"] == cat]
        fig.add_trace(go.Scatter(
            x=cat_data["year"], y=cat_data["spend"],
            name=cat[:25], mode="lines", stackgroup="one",
            line=dict(width=0.5, color=COLORS[i % len(COLORS)]),
        ))

    fig.update_layout(title="Spend Evolution by Category", **LAYOUT,
                      height=420, yaxis_title="Spend (€K)")
    return fig


def chart_category_bars(df_meta: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of 2026E spend by category."""
    df = df_meta.sort_values("spend_2026e", ascending=True)

    fig = go.Figure(go.Bar(
        y=df["category"], x=df["spend_2026e"], orientation="h",
        marker_color=[COLORS[i % len(COLORS)] for i in range(len(df))],
        text=[f"€{v:,.0f}K" for v in df["spend_2026e"]],
        textposition="outside",
    ))
    fig.update_layout(title="2026E Spend by Category", **LAYOUT,
                      height=420, xaxis_title="Spend (€K)")
    return fig


def chart_risk_bubble(df_meta: pd.DataFrame) -> go.Figure:
    """Bottleneck bubble map: concentration vs spend, bubble = lead time."""
    fig = go.Figure()

    for _, row in df_meta.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["concentration"]], y=[row["spend_2026e"]],
            mode="markers+text",
            marker=dict(
                size=row["lead_time_days"] + 15,
                color=RISK_COLORS.get(row["risk"], DIM),
                opacity=0.7,
            ),
            text=[row["category"][:18]],
            textposition="top center",
            textfont=dict(size=9, color=TEXT),
            name=row["category"],
            hovertemplate=(
                f"<b>{row['category']}</b><br>"
                f"Concentration: {row['concentration']}%<br>"
                f"Spend: €{row['spend_2026e']:,.0f}K<br>"
                f"Lead Time: {row['lead_time_days']}d<extra></extra>"
            ),
        ))

    # Danger zone
    fig.add_shape(type="rect", x0=50, x1=100, y0=0, y1=30000,
                  fillcolor="rgba(239,68,68,0.06)",
                  line=dict(color="rgba(239,68,68,0.3)", dash="dot"))
    fig.add_annotation(x=75, y=28000, text="⚠ DANGER ZONE",
                       showarrow=False, font=dict(size=11, color=RED))

    fig.update_layout(
        title="Bottleneck Map — Concentration vs Spend (bubble = lead time)",
        **LAYOUT, height=500, showlegend=False,
        xaxis_title="Supplier Concentration (%)",
        yaxis_title="2026E Spend (€K)",
    )
    return fig


def chart_treemap(df_meta: pd.DataFrame) -> go.Figure:
    """Treemap: size = spend, color = concentration."""
    df = df_meta.copy()
    df["label"] = df.apply(lambda r: f"{r['category']}\n€{r['spend_2026e']:,.0f}K", axis=1)

    fig = px.treemap(df, path=["label"], values="spend_2026e",
                     color="concentration",
                     color_continuous_scale=[GREEN, YELLOW, RED],
                     range_color=[0, 80])
    fig.update_layout(title="Spend (size) × Concentration (color)",
                      paper_bgcolor=BG, font=dict(color=TEXT), height=450,
                      coloraxis_colorbar=dict(title="Concentration %"))
    return fig


def chart_cagr(df_meta: pd.DataFrame) -> go.Figure:
    """CAGR horizontal bars."""
    df = df_meta.sort_values("cagr", ascending=True)
    fig = go.Figure(go.Bar(
        y=df["category"], x=df["cagr"], orientation="h",
        marker_color=[COLORS[i % len(COLORS)] for i in range(len(df))],
        text=[f"{v:.1f}%" for v in df["cagr"]],
        textposition="outside",
    ))
    fig.update_layout(title="Category CAGR (2022 → 2026E)", **LAYOUT,
                      height=420, xaxis_title="CAGR %")
    return fig


# ─────────────────────────────────────────────
# KPI CARDS
# ─────────────────────────────────────────────
def kpi_card(title: str, value: str, subtitle: str = "", color: str = ACCENT) -> pn.pane.HTML:
    """A styled KPI card."""
    return pn.pane.HTML(f"""
    <div style="background:{CARD}; border-radius:12px; padding:20px; text-align:center;
                border:1px solid {GRID}; min-width:160px;">
        <div style="color:{DIM}; font-size:12px; text-transform:uppercase; letter-spacing:1px;">
            {title}
        </div>
        <div style="color:{color}; font-size:32px; font-weight:bold; margin:8px 0;">
            {value}
        </div>
        <div style="color:{DIM}; font-size:11px;">{subtitle}</div>
    </div>
    """, sizing_mode="stretch_width")


# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────

# Load default data
df_spend, df_meta = load_parloa_default()

# ── Sidebar widgets ──
file_input = pn.widgets.FileInput(
    accept=".csv,.xlsx,.xls",
    name="Upload Spend Data",
    multiple=False,
)

dataset_label = pn.pane.Markdown(
    "**Active dataset:** Parloa (default)",
    styles={"color": TEXT, "font-size": "13px"}
)

api_key_input = pn.widgets.PasswordInput(
    name="Claude API Key (optional)",
    placeholder="sk-ant-...",
    width=250,
)

export_btn = pn.widgets.Button(name="📥 Export CFO Report", button_type="success", width=250)

status_log = pn.pane.Markdown("", styles={"color": DIM, "font-size": "11px"})


# ── Main content panels ──
kpi_row = pn.Row(sizing_mode="stretch_width")
chart_area = pn.Column(sizing_mode="stretch_width")
data_preview = pn.widgets.Tabulator(
    df_meta, sizing_mode="stretch_width", height=300,
    theme="midnight", page_size=15,
)


def update_dashboard(df_s=None, df_m=None):
    """Refresh all charts and KPIs."""
    global df_spend, df_meta
    if df_s is not None:
        df_spend = df_s
    if df_m is not None:
        df_meta = df_m

    total_spend = df_meta["spend_2026e"].sum()
    num_cats = len(df_meta)
    criticals = len(df_meta[df_meta["risk"] == "Critical"])
    single_sources = int(df_meta["single_source"].sum())
    avg_conc = df_meta["concentration"].mean()

    kpi_row.clear()
    kpi_row.extend([
        kpi_card("Total Spend 2026E", f"€{total_spend/1000:.1f}M", f"{num_cats} categories"),
        kpi_card("Critical Risks", str(criticals), "categories", RED if criticals > 0 else GREEN),
        kpi_card("Single Source", str(single_sources), "dependencies", YELLOW if single_sources > 0 else GREEN),
        kpi_card("Avg Concentration", f"{avg_conc:.0f}%", "supplier share",
                 RED if avg_conc > 50 else YELLOW if avg_conc > 35 else GREEN),
    ])

    chart_area.clear()
    chart_area.extend([
        pn.pane.Plotly(chart_spend_over_time(df_spend), sizing_mode="stretch_width"),
        pn.Row(
            pn.pane.Plotly(chart_category_bars(df_meta), sizing_mode="stretch_width"),
            pn.pane.Plotly(chart_cagr(df_meta), sizing_mode="stretch_width"),
        ),
        pn.pane.Plotly(chart_risk_bubble(df_meta), sizing_mode="stretch_width"),
        pn.pane.Plotly(chart_treemap(df_meta), sizing_mode="stretch_width"),
    ])

    data_preview.value = df_meta


def handle_upload(event):
    """Process uploaded file."""
    if file_input.value is None:
        return

    try:
        filename = file_input.filename
        raw_bytes = io.BytesIO(file_input.value)

        # Read file
        if filename.endswith(".csv"):
            df_new = pd.read_csv(raw_bytes)
        else:
            df_new = pd.read_excel(raw_bytes)

        status_log.object = f"✅ Loaded **{filename}** — {len(df_new)} rows × {len(df_new.columns)} columns"

        # Column mapping
        api_key = api_key_input.value or os.environ.get("ANTHROPIC_API_KEY")
        mapping = rule_based_mapping(list(df_new.columns))

        mapped_cols = {k: v for k, v in mapping.items() if v}
        unmapped = [k for k, v in mapping.items() if v is None]

        if unmapped and api_key:
            sample = df_new.head(3).to_dict("records")
            mapping = ai_column_mapping(list(df_new.columns), sample, api_key)

        status_log.object += f"\n\nMapped columns: {mapped_cols}"
        if unmapped:
            status_log.object += f"\nUnmapped: {unmapped}"

        # Cleanup
        df_clean, report = full_cleanup(df_new)
        status_log.object += f"\n\nCleanup: {report.get('duplicates_removed', 0)} duplicates removed, {report.get('rows_remaining', len(df_clean))} rows remaining"

        # Update dataset label
        dataset_label.object = f"**Active dataset:** {filename}"

        # For now, show cleaned data in preview
        data_preview.value = df_clean.head(50)

    except Exception as e:
        status_log.object = f"❌ Error: {str(e)}"


def handle_export(event):
    """Export CFO report."""
    try:
        excel_bytes = export_cfo_excel(df_meta, spend_col="spend_2026e")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"CFO_Spend_Report_{timestamp}.xlsx"

        # Create download widget
        download = pn.widgets.FileDownload(
            file=io.BytesIO(excel_bytes),
            filename=filename,
            button_type="success",
            label="⬇ Download Report",
        )
        status_log.object = f"✅ Report generated: **{filename}**"

        # Add download to sidebar
        sidebar_content.append(download)

    except Exception as e:
        status_log.object = f"❌ Export error: {str(e)}"


# Wire up events
file_input.param.watch(handle_upload, "value")
export_btn.on_click(handle_export)

# Initialize dashboard
update_dashboard()


# ── Layout ──
header = pn.pane.HTML(f"""
<div style="background:linear-gradient(135deg, {CARD}, #1a1f2e); padding:24px 32px;
            border-radius:16px; border:1px solid {GRID}; margin-bottom:20px;">
    <h1 style="color:{ACCENT}; margin:0; font-size:28px;">🔴 SpendLens</h1>
    <p style="color:{DIM}; margin:4px 0 0 0; font-size:14px;">
        AI-Powered Procurement Intelligence — Upload any spend data, get instant insights
    </p>
</div>
""", sizing_mode="stretch_width")


sidebar_content = pn.Column(
    pn.pane.HTML(f"<h3 style='color:{ACCENT};'>⚙ Data Source</h3>"),
    file_input,
    dataset_label,
    pn.layout.Divider(),
    pn.pane.HTML(f"<h3 style='color:{ACCENT};'>🤖 AI Settings</h3>"),
    api_key_input,
    pn.layout.Divider(),
    pn.pane.HTML(f"<h3 style='color:{ACCENT};'>📊 Reports</h3>"),
    export_btn,
    pn.layout.Divider(),
    status_log,
    width=280,
)

main_content = pn.Column(
    header,
    kpi_row,
    pn.layout.Divider(),
    chart_area,
    pn.layout.Divider(),
    pn.pane.HTML(f"<h2 style='color:{TEXT};'>📋 Data Explorer</h2>"),
    data_preview,
    sizing_mode="stretch_width",
)

# Final template
template = pn.template.FastListTemplate(
    title="SpendLens — Procurement Intelligence",
    sidebar=sidebar_content,
    main=[main_content],
    accent_base_color=ACCENT,
    header_background=CARD,
    background_color=BG,
    theme="dark",
)

template.servable()


# For development: python app.py
if __name__ == "__main__":
    pn.serve(template, port=5006, show=True, autoreload=True)
