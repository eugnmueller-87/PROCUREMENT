# SpendLens
### AI-Powered Procurement Intelligence

> *Procurement has been running on static reports and manual analysis for decades. SpendLens changes that.*

---

## The Problem

Enterprise procurement teams are sitting on top of some of the most valuable data in a company — and they can't read it.

Not because the data doesn't exist. It does. It lives in SAP exports, Coupa reports, accounting spreadsheets, and Excel files that get emailed around at month end. The problem is what happens next: someone spends three days cleaning it, another week building pivot tables, and by the time a report lands on the CFO's desk it's already stale.

Meanwhile:
- Shadow IT keeps growing. Nobody knows how many SaaS tools are being expensed without IT approval.
- Freelancers are being paid under personal names with no PO, no contract, no visibility.
- A vendor justifies a 22% price increase with "market conditions" — and procurement has no data to push back.
- A contract expires quietly. The auto-renewal kicks in. Another year at last year's price.

The tools that exist — SAP Analytics, Coupa Accelerate, Ivalua — were built for a different era. Rigid data models. Manual configuration. Static rules. They work if your data is already clean and your processes are already mature. Most companies aren't there.

**SpendLens is built for the real world.**

---

## What SpendLens Does

SpendLens takes raw accounting and procurement data — messy, inconsistent, multi-source — and turns it into a living procurement intelligence platform.

It doesn't generate a one-time report. It builds a knowledge base that gets smarter with every upload.

**It sees what other tools miss:**

- Invoices with no PO, no contract, no approval trail
- SaaS subscriptions buried in expense reports
- Freelancers paid under personal names across multiple cost centers
- Vendors whose price increases don't hold up against market indices
- Contracts about to expire with no renegotiation in progress
- Spend patterns that only emerge across 12 months of transaction history

**It works with the data you actually have** — not the data you wish you had.

---

## How It Works

SpendLens is built around a five-stage AI pipeline that transforms raw data into enriched, actionable intelligence.

```
Raw Upload (CSV / Excel / Multi-source)
         │
         ▼
   Column Mapper        — maps any column names to standard schema
         │               rule-based + Claude API fallback
         ▼
   Data Cleanup         — normalizes formats, deduplicates vendors,
         │               handles German/English/ERP data formats
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

Every stage is designed to handle the reality of enterprise data — missing fields, inconsistent formats, multiple source systems, and the kind of vendor naming that only makes sense if you've worked in SAP.

---

## The Intelligence

### 11-Category Procurement Taxonomy
Transactions are classified into a purpose-built taxonomy — not generic accounting codes, but procurement-meaningful categories that drive real decisions:

Cloud & Compute · AI/ML APIs & Data · IT Software & SaaS · Telecom & Voice · Recruitment & HR · Professional Services · Marketing & Campaigns · Facilities & Office · Real Estate · Hardware & Equipment · Travel & Expenses

### Compliance & Risk Flags
Every transaction carries a set of derived flags that answer the questions a CPO actually cares about:

| Flag | What it detects |
|------|----------------|
| PO Status | With PO / Blanket PO / No PO / Unknown |
| Contract Status | Under Contract / Expired / No Contract / Unknown |
| Maverick Spend | Off-contract or off-PO spend above configurable threshold |
| Shadow IT | Unauthorized SaaS/IT spend hidden in expenses or cost centers |
| Freelancer | Spend under personal names across HR sub-commodity |
| Spend Pattern | Recurring / Blanket PO / One-off / Irregular |
| Catalogue | Purchased through approved catalogue vs off-catalogue |

### Real Estate Intelligence
Office rent is tracked by location — city, country, entity. A CFO can see exactly which offices are paying what, compare lease costs across locations, and flag contracts approaching renewal.

### Multi-Source Matching
Upload an accounting export and a procurement PO list simultaneously. SpendLens identifies the source type, fuzzy-matches transactions to purchase orders, and surfaces the gap — what was paid that was never approved, and what was approved that was never invoiced.

### Persistent Knowledge Base
SpendLens never overwrites previous data. Every upload appends to a transaction timeline. Vendor classifications, spend patterns, and matching logic accumulate over time. The platform gets more accurate with every file it processes.

---

## Icarus — Market Intelligence Agent

SpendLens ships with Icarus, a live market intelligence layer that answers the question procurement teams can never answer today: *is this price increase actually justified?*

Icarus monitors RSS feeds from Reuters, The Register, Handelsblatt, DatacenterDynamics, Spend Matters, and specialised procurement sources. It maps news signals to the categories in your spend data and tells you what to do about them — before the invoice arrives.

**What Icarus does:**

- **On-demand RSS scan** — Fetches and deduplicates articles across 9 curated sources, scores each for procurement relevance (1–10), classifies impact as positive/negative/neutral, and suggests a concrete action. Results are grouped by spend category in a collapsible card view.
- **Ask Icarus** — Natural language queries against current signals + live article context. Ask *"What are the risks in cloud spend this week?"* and get a structured answer with supporting signals.
- **RFP & Negotiation Prep** — Type *"RFP"*, *"negotiation"*, or *"tender"* in any query to generate a structured negotiation brief: market context, leverage points, key requirements, risk areas, suggested contract terms, and next steps — built from real market signals.
- **Weekly Intelligence Brief** — One click generates an executive summary of the past 7 days: top risks, opportunities, priority actions, and per-category highlights.
- **Learns over time** — User feedback (relevant / not relevant) adjusts per-category weights so signals surface in the right order as the system learns your priorities.

When AWS raises your bill 18%, SpendLens doesn't just show you the number. It shows you that GPU spot prices rose 6%, US data center energy costs rose 4%, and the remaining 8% gap has no market justification. That's a negotiation, not an invoice to approve.

---

## Running SpendLens

```bash
# 1. Activate virtual environment
source .venv/Scripts/activate       # Git Bash / macOS
.venv\Scripts\activate              # Windows PowerShell

# 2. Add your Anthropic API key to .env
echo "ANTHROPIC_API_KEY=sk-..." > .env

# 3. Start the dashboard
PYTHONUTF8=1 panel serve app.py --show --port 5006
```

Requires Python 3.11+ and the packages in `requirements.txt`.

---

## Built With

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
| Language | Python 3.11+ |

---

## Status

SpendLens is in active development, built as part of the Ironhack AI Bootcamp and extended as a serious procurement intelligence product.

| Component | Status |
|-----------|--------|
| AI column mapper | ✅ Complete |
| Data cleanup engine | ✅ Complete |
| Category mapper (chunked + cached) | ✅ Complete |
| Flag engine | ✅ Complete |
| Icarus — RSS signal scanner | ✅ Live |
| Icarus — Ask / query mode | ✅ Live |
| Icarus — RFP & negotiation prep | ✅ Live |
| Icarus — Weekly intelligence brief | ✅ Live |
| Icarus — Feedback learning loop | 🔨 In progress |
| Multi-source PO merger | 📋 Planned |
| Multi-client support | 📋 Planned |

---

## Background

SpendLens is built by someone who has worked in enterprise procurement — not just around it.

The features aren't designed from a product spec. They come from knowing what a category manager actually needs at 11pm before a supplier negotiation, what a CFO asks when they see a budget variance, and what a procurement audit looks like when the data comes from four different systems and none of them talk to each other.

The AI layer doesn't replace procurement expertise. It amplifies it.

---

*Interested in the architecture, the approach, or a demo? Get in touch.*
