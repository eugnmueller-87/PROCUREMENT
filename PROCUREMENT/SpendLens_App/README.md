# SpendLens
### AI-Powered Procurement Intelligence

> *Procurement has been running on static reports and manual analysis for decades. SpendLens changes that.*

---

## What is SpendLens?

SpendLens is a procurement intelligence platform that takes raw accounting and spend data — messy, inconsistent, multi-source — and turns it into a living knowledge base that gets smarter with every upload.

It combines a five-stage AI pipeline for data processing, a Panel-based analytics dashboard, and **Icarus** — an embedded market intelligence agent that monitors RSS feeds, answers procurement questions in natural language, and generates negotiation briefs on demand.

Built by someone who has worked in enterprise procurement. The features come from knowing what a category manager needs at 11pm before a supplier negotiation, not from a product spec.

---

## The Problem It Solves

Enterprise procurement teams are sitting on top of valuable data they cannot read.

It lives in SAP exports, Coupa reports, accounting spreadsheets, and Excel files emailed at month-end. Someone spends three days cleaning it, another week building pivot tables, and by the time a report lands on the CFO's desk it's already stale.

Meanwhile:
- Shadow IT keeps growing — nobody knows how many SaaS tools are being expensed without approval
- Freelancers are paid under personal names with no PO, no contract, no visibility
- A vendor justifies a 22% price increase with "market conditions" — and procurement has no data to push back
- A contract expires quietly, auto-renewal kicks in, another year at last year's price

**SpendLens is built for the real world** — not for companies whose data is already clean.

---

## Core Features

### Five-Stage Upload Pipeline

```
Raw Upload (CSV / Excel / Multi-source)
         │
         ▼
   Column Mapper        — maps any column names to standard schema
         │               rule-based + Claude API fallback
         ▼
   Data Cleanup         — normalizes formats, deduplicates vendors,
         │               handles German / English / ERP data formats
         ▼
   Category Mapper      — AI classification into 11 procurement categories
         │               chunked batching, persistent cache, ~$0.05/1000 vendors
         ▼
   Flag Engine          — derives compliance & risk flags per transaction
         │               maverick, shadow IT, freelancer, PO status, patterns
         ▼
   Intelligence Layer   — spend trends, anomalies, pattern detection
                          built on a persistent transaction timeline
```

Every stage is designed to handle the reality of enterprise data — missing fields, inconsistent formats, multiple source systems.

### 11-Category Procurement Taxonomy

> Cloud & Compute · AI/ML APIs & Data · IT Software & SaaS · Telecom & Voice · Recruitment & HR · Professional Services · Marketing & Campaigns · Facilities & Office · Real Estate · Hardware & Equipment · Travel & Expenses

### Compliance & Risk Flags

| Flag | What it detects |
|------|----------------|
| PO Status | With PO / Blanket PO / No PO / Unknown |
| Contract Status | Under Contract / Expired / No Contract / Unknown |
| Maverick Spend | Off-contract or off-PO spend above configurable threshold |
| Shadow IT | Unauthorized SaaS/IT spend hidden in expenses or cost centers |
| Freelancer | Spend under personal names across HR sub-commodity |
| Spend Pattern | Recurring / Blanket PO / One-off / Irregular |

### Persistent Knowledge Base

SpendLens never overwrites previous data. Every upload appends to a transaction timeline. Vendor classifications, spend patterns, and compliance flags accumulate over time.

---

## Icarus — Market Intelligence Agent

Icarus is the live intelligence layer embedded in SpendLens. It answers the question procurement teams can never answer today: *is this price increase actually justified?*

**Capabilities:**

| Feature | Description |
|---------|-------------|
| RSS Signal Scan | Fetches and deduplicates articles across 9 curated sources (Reuters, The Register, Handelsblatt, DatacenterDynamics, Spend Matters and more). Each article is scored for procurement relevance (1–10), classified by impact, and assigned a suggested action. |
| Ask Icarus | Natural language queries against current signals and live article context. Ask *"What are the cloud cost risks this week?"* and get a structured answer with supporting market signals. |
| RFP & Negotiation Prep | Type `RFP`, `negotiation`, or `tender` to generate a structured negotiation brief: market context, leverage points, key requirements, risk areas, suggested contract terms, and next steps — built from real market signals. |
| Document Context | Upload contracts, pricing sheets, or agreements (PDF, DOCX, XLSX, TXT) via the paperclip icon. Icarus reads the documents in-session and uses them as context in every query. Documents are stored in memory only — cleared on page refresh, never written to disk. |
| Weekly Intelligence Brief | One click generates an executive summary of the past 7 days: top risks, opportunities, priority actions, and per-category highlights. |
| Feedback Learning | Thumbs up / down on any signal feeds into per-category weights so Icarus learns your priorities over time. |

When AWS raises your bill 18%, SpendLens doesn't just show you the number. It shows you that GPU spot prices rose 6%, US data center energy costs rose 4%, and the remaining 8% gap has no market justification. That's a negotiation, not an invoice to approve.

---

## Architecture

```
app.py                      — Panel dashboard, tab layout, upload orchestration
icarus.py                   — Market intelligence agent (RSS, Claude API, SQLite)
icarus_ui.py                — Icarus Panel UI component
modules/
  column_mapper.py          — Schema normalization (fuzzy + Claude fallback)
  data_cleanup.py           — Spend normalization, deduplication
  category_mapper.py        — AI vendor classification (chunked + cached)
  flag_engine.py            — Compliance & risk flag derivation
  database.py               — SQLite persistence (WAL mode, hash dedup)
  cfo_reports.py            — Excel export generation
```

**Persistence:**
- `clients/{name}/spendlens.db` — per-client SQLite database. Tables: `uploads`, `transactions_raw`, `transactions_enriched`, `vendors`, `matches`
- `clients/{name}/icarus_memory.db` — Icarus signals, feedback, category weights
- `vendor_cache.json` — vendor→category cache; survives restarts, minimises API costs

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Dashboard | Panel (HoloViz) |
| Charts | Plotly |
| Data processing | Pandas |
| AI classification & intelligence | Claude API (Anthropic) |
| Persistent storage | SQLite |
| News scraping | feedparser |
| Validation | Pydantic |
| Export | openpyxl |
| Document parsing | pypdf, python-docx |
| Language | Python 3.11+ |

---

<<<<<<< HEAD
## Recent Updates

**April 2026**
- **Icarus 5x speed improvement** — RSS feeds now fetched in parallel (9 simultaneous connections); article analysis split into concurrent batches using Claude Haiku; full scan ~8s vs. 45s before
- **Icarus signals load on startup** — dashboard now shows cached signals immediately when the page opens, without needing to click Scan
- Risk & Bottlenecks chart redesigned — log-scale axis, enlarged bubbles, total spend badge; Cloud & Compute no longer dominates the visual
- Deep Dive treemap now shows top suppliers inside each category tile; click a supplier to open a procurement intel card (contract type, payment terms, price trend, discount, suggested action)
- Market signals panel wired into supplier cards — pulls live Icarus signals for the selected supplier; one-click RSS refresh filtered to that vendor (~5s, no API cost)
- Spend comparison chart replaces the fixed CAGR bar — pick any start/end year, see per-category growth as a stacked navy/blue bar sorted by size
- Capex/Opex rebuilt as a multi-year stacked bar showing all five years side by side

---

## Status
=======
## Running SpendLens
>>>>>>> 545fa1b6eaf9b3877b700922818d7d41a41252f2

```bash
# 1. Clone and activate virtual environment
git clone <repo-url>
cd SpendLens_App
python -m venv .venv
source .venv/Scripts/activate      # Git Bash / macOS
# .venv\Scripts\activate           # Windows PowerShell

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Anthropic API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# 4. Start the dashboard
PYTHONUTF8=1 panel serve app.py --show --port 5006
```

> **Note for Windows users:** The `PYTHONUTF8=1` prefix is required to handle non-ASCII vendor names and German umlauts in spend data. Without it, parsing may fail silently on certain datasets.

---

## Recent Updates — 2026-04-26

- **Risk Map redesigned** — log-scale x-axis prevents Cloud & Compute from dominating the chart; enlarged bubbles with full category labels; total spend badge pinned to top-left corner
- **Treemap supplier drill-down** — two-level treemap (category → top 5 suppliers by spend); click a supplier to open a procurement intel card in-place with contract details, payment terms, price trend, discount status, and suggested action
- **Market signals panel in Deep Dive** — supplier cards pull live Icarus signals from `icarus_memory.db`; "Fetch latest signals" button runs a fast RSS-only refresh (~5s, no Claude API call) filtered to the selected supplier
- **Interactive spend comparison chart** — replaced the fixed CAGR bar; pick any start/end year to compare per-category growth; navy = base year spend, light blue = growth to end year; sorted by largest growth
- **Capex/Opex redesigned as multi-year stacked bar** — shows all five years (2022–2026) side by side; Capex (navy) + Opex (green) stacked; built directly from category data, no year filter dependency

---

## Project Status

| Component | Status |
|-----------|--------|
| AI column mapper | ✅ Complete |
| Data cleanup engine | ✅ Complete |
| Category mapper (chunked + cached) | ✅ Complete |
| Flag engine | ✅ Complete |
| CFO Excel export | ✅ Complete |
| Dashboard — year-aware charts (all tabs) | ✅ Complete |
| Dashboard — Risk Map (log-scale, bubbles, spend badge) | ✅ Complete |
| Dashboard — Treemap with supplier drill-down | ✅ Complete |
| Dashboard — Supplier intel cards & market signals | ✅ Complete |
| Dashboard — Interactive spend comparison chart | ✅ Complete |
| Dashboard — Capex/Opex multi-year stacked bar | ✅ Complete |
| Icarus — RSS signal scanner | ✅ Live |
| Icarus — Ask / query mode | ✅ Live |
| Icarus — RFP & negotiation prep | ✅ Live |
| Icarus — Weekly intelligence brief | ✅ Live |
| Icarus — Document upload (in-memory) | ✅ Live |
| Icarus — Signal deduplication | ✅ Live |
<<<<<<< HEAD
| Icarus — Parallel fetch & batch analysis (5x faster) | ✅ Live |
| Icarus — Signals load on dashboard startup | ✅ Live |
=======
>>>>>>> 545fa1b6eaf9b3877b700922818d7d41a41252f2
| Icarus — Feedback learning loop | 🔨 In progress |
| Compliance Scorecard tab | 📋 Planned |
| Spend Variance Analysis | 📋 Planned |
| Supplier Risk Score | 📋 Planned |
| Spend Forecast (Q+1) | 📋 Planned |
| Multi-client support | 📋 Planned |

---

## Privacy & Data Handling

- **Uploaded documents** (contracts, pricing sheets) are held in memory only for the duration of the browser session. Nothing is written to disk. Refreshing the page clears all uploaded documents.
- **Spend data** is stored in a per-client SQLite database on the local machine. No data is sent to external services except vendor names and headlines for AI classification.
- **API key** is read from `.env` at startup and never logged or exposed in the UI.

---

## Background

SpendLens is built by someone who has worked in enterprise procurement — not just around it.

The AI layer doesn't replace procurement expertise. It amplifies it.

---

*Interested in the architecture, a demo, or contributing? Get in touch.*
