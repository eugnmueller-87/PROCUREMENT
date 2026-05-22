<img src="docs/logo.svg" width="48" align="left" style="margin-right:12px;">
![Live](https://img.shields.io/badge/Live-Railway-brightgreen)
![Stack](https://img.shields.io/badge/Stack-React_+_FastAPI_+_SQLite-blue)
![AI](https://img.shields.io/badge/AI-Claude_API-orange)
![Data](https://img.shields.io/badge/Spend_Analytics-590%2B_Suppliers-purple)
![License](https://img.shields.io/badge/License-Private-lightgrey)

# SpendLens
### AI-Powered Procurement Intelligence

**Status:** Live on Railway (URL available on request)

> *Procurement has been running on static reports and manual analysis for decades. SpendLens changes that.*

> **Procurement AI stack:** Icarus (personal AI OS) · **SpendLens** (spend analytics) · Hades (supplier vetting) · Hermes (market intelligence)

---

## What is SpendLens?

SpendLens is a production-grade procurement intelligence platform — a React SPA served by FastAPI — that takes raw accounting and spend data and turns it into a living knowledge base with real-time market intelligence, supplier due diligence, and AI-powered contract analysis.

Built by someone who has worked in enterprise procurement. Every feature comes from knowing what a category manager actually needs, not from a product spec.

---

## Screenshots

### Dashboard — KPIs, spend evolution, YoY diverging bar, category risk matrix

![SpendLens Dashboard](docs/screenshots/Screenshot%202026-05-17%20202517.png)

### Deep Dive — spend growth, budget variance, spend share, supplier concentration, treemap

![SpendLens Deep Dive](docs/screenshots/Screenshot%202026-05-17%20202534.png)

### Compliance — supplier scorecard with ABC tiers, scores, relationship status

![SpendLens Compliance Scorecard](docs/screenshots/Screenshot%202026-05-17%20202556.png)

### CLM — contract drag-drop scan, risk arc gauge, clause cards, renewal tracking

![SpendLens CLM](docs/screenshots/Screenshot%202026-05-17%20202818.png)

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

### Dashboard
- **5 KPI cards** — Total Spend, YoY Growth, EBITDA Impact, Contract Coverage, Maverick Spend
- **Stacked area chart** — spend evolution by category across 5 years, with year-highlight on filter
- **YoY diverging bar chart** — per-category growth vs prior year, green/red, zero-centred
- **Category Risk Matrix table** — sortable by risk then spend, inline spend vs budget bar, variance %, supplier count, click to drill in
- **Expiring contracts table** — next 180 days, days-left countdown chips, click to contract drawer
- **Year filter** — updates all KPIs, charts, and tables in one fetch
- **CSV/Excel upload** — triggers the full 5-stage AI pipeline server-side

### Deep Dive Analysis
- **Spend Growth by Category** — dual-bar showing first-year vs last-year per category, YoY % badge
- **Spend vs Budget** — horizontal bar chart with absolute scaling across years
- **Spend Share %** — horizontal bars with risk-colour dots, click to drill into category drawer
- **Supplier Count by Category** — fragmentation indicator with spend-per-supplier metric
- **Treemap** — spend × risk colour, click any tile to open category drawer

### Compliance Scorecard
- EcoVadis-style supplier list with ABC tier avatars
- Summary header — avg score, PO coverage, contract coverage, tier counts
- Per-supplier: compliance score, relationship status (Strategic / Preferred / Transactional), spend, country
- Multi-filter: tier, risk, relationship; sort by score / spend / name
- Click any row → supplier drawer (tier, contract end, single-source flag, PO coverage, spend)

### Icarus AI — Market Intelligence
- Category-tabbed signal feed (Cloud · AI/ML · IT Software · Telecom · Recruitment · and more)
- Per-signal: relevance chip (Critical/High/Medium), source, headline, summary, recommended action
- Click signal → full signal drawer with AI context
- **Run Scan** — triggers RSS scan across 9 sources + Hermes market intelligence injection
- **Hermes integration** — signals from 590+ tracked suppliers fed in automatically
- Time filter: Today / 7 days / 30 days / All time
- Full-text search across signals
- Demo signals shown when database is empty (no blank state)

### Contract Lifecycle Management (CLM)
- Drag-and-drop PDF / DOCX upload
- AI clause extraction: start/end dates, notice period, auto-renewal, payment terms, jurisdiction, liability cap, penalty cap
- **RiskArc gauge** — visual risk score 0–10
- Clause flag cards — missing clauses, playbook deviations, required actions
- Contract history table — all previously scanned contracts, click to re-open in drawer
- Save to database — persists extracted data to SQLite for expiry monitoring

### Supplier Due Diligence (Hades)
- Company name + category + country inputs
- **Two modes** — Compliance Check (standalone, no data written) / Onboard Supplier (saves to vendor DB)
- Live Hades status badge — checks `/health` on load, shows online/offline before you run
- 10-step pipeline progress tracker — Pre-flight · Web research · News sentiment · Sanctions · Registry · LkSG · ESG · Synthesis · Report · Watchlist
- Report: risk score 0–10, sanctions clear/flagged, LkSG signal, AI recommendation, next steps

### Category Strategy
- AI-powered 7-framework workbench: Kraljic, PESTEL, SWOT, Porter's Five Forces, TCO, Negotiation Levers, 3-year Recommendation
- Results saved to SQLite per category — returns instantly on re-visit
- HTML slide deck export (10 branded slides, keyboard navigation, print-ready)

### Shell
- **AI Assistant** — slide-in chat panel with keyword-matched procurement answers (maverick spend, cloud costs, contracts, savings); quick-prompt chips
- **Notifications** — bell dropdown with 5 live alerts, per-item dismiss + mark all read, click navigates to screen
- **Settings** — real dark mode toggle (`data-theme`), density selector, account info
- **Command palette** — `⌘K` / `Ctrl+K` quick navigation

---

## Five-Stage Upload Pipeline

```
Raw Upload (CSV / Excel)
         │
         ▼
   Column Mapper        — maps any column names to standard 14-field schema
         │               rule-based first, Claude API fallback for unmapped cols
         ▼
   Data Cleanup         — deduplicates rows, normalizes spend values
         │               handles German 1.234,56 and English $1,234.56 formats
         ▼
   Category Mapper      — AI classification into 11 procurement categories
         │               chunked batching, vendor_cache.json, ~$0.05/1000 vendors
         ▼
   Flag Engine          — maverick spend, shadow IT, freelancer detection,
         │               missing POs, contract expiry flags
         ▼
   SQLite Persistence   — raw + enriched records, hash-based dedup,
                          WAL mode, per-client isolation
```

---

## 11-Category Procurement Taxonomy

> Cloud & Compute · AI/ML APIs & Data · IT Software & SaaS · Telecom & Voice · Recruitment & HR · Professional Services · Marketing & Campaigns · Facilities & Office · Real Estate · Hardware & Equipment · Travel & Expenses

---

## Stack Architecture

SpendLens is the data platform at the centre of a four-agent system. It provides the spend record and vendor knowledge base; three AI agents interact with it to add intelligence.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ICARUS (Personal AI OS)                          │
│                    Telegram · Claude Sonnet 4.6 · icarusai.de               │
│                                                                             │
│  "Is Bechtle a supplier?"                                                   │
│         │                                                                   │
│         ▼  (parallel)                                                       │
│  hades_supplier_lookup                                                      │
│    ├── GET /api/suppliers/lookup/Bechtle  ──→  SpendLens (this system)      │
│    └── GET /audit/Bechtle/latest          ──→  Hades                        │
│         │                                                                   │
│         ▼  (merged answer to user)                                          │
│  SpendLens: ✅ Active (€2.1M · IT Software · 47 txns)                       │
│  Hades DD:  ✅ Investigated 2026-05-14 · Low · Approve                      │
└─────────────────────────────────────────────────────────────────────────────┘
         │                             │
         ▼                             ▼
┌─────────────────┐         ┌──────────────────────────────┐
│   SPENDLENS     │         │         HADES (DD Agent)     │
│  (this system)  │         │                              │
│                 │◄────────│  POST /investigate           │
│  vendor DB      │  writes │  (new vendor onboarding)     │
│  spend records  │  back   │                              │
│  approval flow  │         │  Reads Hermes Redis          │
│  Hades UI       │         │  Writes audit to Redis       │
│  Icarus signals │         │  Registers to Hermes watchlist│
└─────────────────┘         └──────────────────────────────┘
         │                                    │
         │                                    │ shared
         └──────────────────────────────────► │ Upstash Redis
                                              ▼
                                  ┌──────────────────────┐
                                  │   HERMES (Intel)     │
                                  │  ~590 suppliers      │
                                  │  Redis + Vector      │
                                  │  RSS · EDGAR · Jobs  │
                                  └──────────────────────┘
```

### How SpendLens fits in

| Interaction | Direction | What |
|---|---|---|
| Hades → SpendLens | Hades writes back | After DD: `hades_risk_score`, `hades_recommendation`, `hades_lksg_signal` saved to vendor record |
| SpendLens → Hades | SpendLens calls | `POST /investigate` when new vendor created or periodic recheck triggered |
| Icarus → SpendLens | Icarus reads | `GET /api/suppliers/lookup/{name}` for dual-check supplier status queries |
| SpendLens → Hermes | SpendLens reads | Hermes market signals injected into the Icarus signals feed on scan |

### Supplier lookup endpoint (for Icarus)

```
GET /api/suppliers/lookup/{name}

Response:
{
  "found": true,
  "vendor_name": "Bechtle AG",
  "category": "IT Software & SaaS",
  "total_spend_eur": 2100000,
  "transaction_count": 47,
  "last_seen": "2026-04",
  "country": "DE",
  "single_source": false,
  "hades_risk_score": 3.2,
  "hades_risk_level": "Low",
  "hades_recommendation": "Approve"
}
```

Fuzzy name matching at 0.6 threshold — so "Bechtle", "Bechtle AG", and "bechtle" all resolve to the same vendor record.

---

## Architecture

```
api.py                          — FastAPI: all REST endpoints + StaticFiles serving
railway.toml                    — startCommand: uvicorn api:app --host 0.0.0.0 --port $PORT

frontend/
  index.html                    — entry point, loads React 18 UMD + Babel standalone
  styles.css                    — Claude Design system (oklch tokens, Geist, dark mode)
  icons.jsx                     — SVG icon set → window.Icons
  charts.jsx                    — StackedArea, SpendVsBudget, Treemap, RiskArc, Donut,
                                   Sparkline, Waterfall + shared riskColor()/riskClass()
  shell.jsx                     — Sidebar, TopBar, AIAssistant, SettingsPanel, CmdPalette
  app.jsx                       — hash router, DrawerBody (contract/supplier/category/signal)
  screens/
    dashboard.jsx               — KPIs, stacked area, YoY bar, risk matrix, expiring contracts
    deepdive.jsx                — growth bars, spend share, supplier count, treemap
    compliance.jsx              — supplier scorecard, multi-filter, sort
    icarus.jsx                  — market signal feed, category tabs, RSS scan trigger
    strategy.jsx                — Kraljic, PESTEL, SWOT, Porter's, TCO, Levers, Recommendation
    supplier.jsx                — Hades due diligence, pipeline tracker, report
    clm.jsx                     — contract scan/save, RiskArc, clause cards, history

modules/
  column_mapper.py              — schema normalization (fuzzy + Claude fallback)
  data_cleanup.py               — spend normalization, deduplication
  category_mapper.py            — AI vendor classification (chunked + cached)
  flag_engine.py                — compliance & risk flag derivation
  database.py                   — SQLite persistence (WAL mode, hash dedup)
  supplier_profiler.py          — supplier scoring, ABC tier computation
  hermes_client.py              — Upstash Redis client for Hermes market intelligence
  cfo_reports.py                — Excel export generation

icarus.py                       — market intelligence: RSS scan, Claude Haiku analysis,
                                   Hermes signal injection, saves to icarus_memory.db
lex.py                          — contract clause extraction + risk scoring
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Healthcheck — returns transaction count |
| GET | `/api/dashboard?year=` | KPIs, trend, categories, expiring contracts. Demo data if DB empty |
| GET | `/api/suppliers` | Supplier profiles with scores, tiers, risk |
| GET | `/api/suppliers/lookup/{name}` | Fuzzy supplier lookup for Icarus dual-check (spend + Hades status) |
| GET | `/api/contracts` | All scanned contracts |
| POST | `/api/contracts/scan` | Scan PDF/DOCX — calls `lex.py` |
| POST | `/api/contracts/save` | Scan + persist to SQLite |
| POST | `/api/upload` | Upload spend CSV/Excel — runs full 5-stage pipeline |
| GET | `/api/signals?days=&category=` | Icarus signals from `icarus_memory.db`; demo signals if empty |
| POST | `/api/signals/scan` | Trigger Icarus RSS + Hermes scan |
| GET | `/api/docs` | FastAPI auto-docs (Swagger UI) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 UMD + Babel standalone (no build step) |
| Backend | FastAPI + uvicorn |
| Data processing | Pandas |
| AI classification & intelligence | Claude API (Anthropic) — Sonnet 4.6 + Haiku 4.5 |
| Market intelligence | Hermes (Upstash Redis) + RSS feeds (feedparser) |
| Persistent storage | SQLite (WAL mode, per-client) |
| Document parsing | pypdf, python-docx |
| Deployment | Railway (auto-deploy from git) |
| Design system | Claude Design — oklch tokens, Geist font, dark mode |

---

## Running Locally

```bash
# 1. Activate virtual environment
.venv\Scripts\activate        # Windows PowerShell
source .venv/Scripts/activate  # Git Bash

# 2. Add your Anthropic API key
# Create .env at project root:
ANTHROPIC_API_KEY=sk-ant-...
SPENDLENS_CLIENT=default   # optional

# 3. Start the server
uvicorn api:app --reload --port 8000

# 4. Open http://localhost:8000
```

**Railway env vars** (set in Railway dashboard → Variables, never in git):
- `ANTHROPIC_API_KEY`
- `UPSTASH_REDIS_REST_URL` — for Hermes market intelligence
- `UPSTASH_REDIS_REST_TOKEN` — for Hermes market intelligence
- `PORT` — set automatically by Railway

**Never commit:** `.env`, `*.db`, `vendor_cache.json`, `screenshots2/`

---

## Design System

- **Font:** Geist + Geist Mono (Google Fonts CDN)
- **Colours:** oklch tokens — `--primary` (navy), `--good` (green), `--warn` (amber), `--bad` (red), `--info` (blue)
- **Dark mode:** `document.documentElement.setAttribute("data-theme", "dark")` — all tokens switch automatically
- **Layout:** CSS grid `"sb tb" / "sb main"` — 64px collapsed sidebar, 240px expanded on hover
- **Key classes:** `.card`, `.kpi`, `.chip`, `.tag`, `.btn`, `.btn.primary`, `.ai-card`, `.ai-insight`, `.tier-av.a/b/c`, `.drop-zone`, `.spin`, `.t`, `.row-link`, `.page-h`, `.col`, `.grid`

---

## Product Roadmap

### Layer 1 · Data Ingestion & Integration

| Component | Status | Notes |
|---|---|---|
| SpendLens upload pipeline (CSV / Excel) | ✅ Live | Fuzzy column mapping, German format support, dedup |
| ERP Live Connector (SAP S/4HANA, Ariba API) | 🔴 High priority | Eliminates manual exports — real-time spend feed |
| P-Card / Invoice OCR (unstructured docs) | ⬜ Optional | |

### Layer 2 · Spend Analytics & Intelligence

| Component | Status | Notes |
|---|---|---|
| Spend classification — 5-stage AI pipeline | ✅ Live | 11 categories, cached, ~$0.05/1000 vendors |
| Dashboard — year filter, YoY chart, risk matrix | ✅ Live | All charts update on year selection |
| Deep Dive — growth, treemap, spend share, drill-in | ✅ Live | Category drawer with trend mini-chart |
| Hermes market intelligence | ✅ Live | 590+ suppliers, 17 categories, Upstash Redis |
| Savings Tracker — budget vs. actual, variance | 🔴 High priority | CFOs expect this |

### Layer 3 · Sourcing & Supplier Management

| Component | Status | Notes |
|---|---|---|
| Compliance Scorecard — ABC tiers, scores, multi-filter | ✅ Live | EcoVadis-style, 26 demo suppliers |
| Hades Due Diligence — 6-node LangGraph agent | ✅ Live | Sanctions, LkSG, ESG, Registry, News, Hermes |
| Supplier Performance Scorecard — SLA tracking | 🔴 High priority | Closes the loop from onboarding to performance |

### Layer 4 · Contract Lifecycle Management (CLM)

| Component | Status | Notes |
|---|---|---|
| Contract Extraction — AI clause parsing, risk scoring | ✅ Live | PDF/DOCX → structured data, RiskArc gauge |
| Renewal Monitor — expiry alerts in Dashboard | ✅ Live | 180-day window, daysLeft countdown |
| Live notifications — overdue contracts + budget alerts | 🔴 High priority | Replace hardcoded array with `/api/alerts` |
| Negotiation Copilot — playbook AI, redlining | ⬜ Optional | |

### Layer 5 · Intelligence & AI

| Component | Status | Notes |
|---|---|---|
| Icarus market signals — RSS + Hermes | ✅ Live | 8 demo signals; real scan writes to SQLite |
| AI Assistant — chat panel | 🔴 High priority | Wire to Claude API (currently keyword-matched) |
| Category Strategy — 7 AI frameworks | ✅ Live | Kralj, PESTEL, SWOT, Porter's, TCO, Levers, Rec |
| Strategy screen — real API wiring | 🔴 High priority | Currently placeholder generate() |

### Layer 6 · Compliance, ESG & Risk

| Component | Status | Notes |
|---|---|---|
| Hades Risk Engine — OFAC, LkSG, ESG, NCP | ✅ Live | Integrated into SpendLens Supplier DD tab |
| Scope 3 / CO₂ Tracker | 🔴 High priority | CSRD mandatory reporting |
| Supplier Diversity Scorecard | ⬜ Optional | |

### Layer 7 · Reporting & CPO Dashboard

| Component | Status | Notes |
|---|---|---|
| CFO Excel Export | ✅ Live | Multi-tab workbook |
| Category Strategy slide deck (HTML export) | ✅ Live | 10 slides, branded |
| CPO Live Dashboard — real-time KPIs, RAG status | 🔴 High priority | Executive view |
| Natural Language Query | ⬜ Optional | |

### Additional Planned Capabilities

| Component | Status |
|---|---|
| ECB FX Rates — auto-convert multi-currency spend to EUR | 🔨 In progress |
| OpenCorporates — supplier legal registration enrichment | 🔨 In progress |
| Mobile — Telegram bot (signal push, scan on demand) | 📋 Planned |
| Mobile — Slack bot (weekly brief, scan on demand) | 📋 Planned |
| Real AI chat in Assistant panel — streaming Claude API | 📋 Planned |
| Settings density — `data-density` CSS attribute | 📋 Planned |
| Multi-client support with per-client isolation | 📋 Planned |
| Enterprise security — SSO, RBAC, audit log, encryption | 📋 Planned |

---

## Current Build Status

| Component | Status |
|-----------|--------|
| FastAPI backend + React SPA | ✅ Live on Railway |
| AI column mapper | ✅ Complete |
| Data cleanup engine | ✅ Complete |
| Category mapper (chunked + cached) | ✅ Complete |
| Flag engine | ✅ Complete |
| Dashboard — KPIs, year filter, stacked area | ✅ Complete |
| Dashboard — YoY diverging bar chart | ✅ Complete |
| Dashboard — Category Risk Matrix table | ✅ Complete |
| Dashboard — Expiring contracts table | ✅ Complete |
| Deep Dive — growth, treemap, spend share, drill-in | ✅ Complete |
| Compliance Scorecard — ABC tiers, multi-filter, drawer | ✅ Complete |
| Icarus — signal feed with category tabs | ✅ Complete |
| Icarus — Hermes integration | ✅ Complete |
| Icarus — demo signals fallback | ✅ Complete |
| CLM — drag-drop scan, RiskArc, clause cards, history | ✅ Complete |
| Supplier DD — Hades pipeline tracker, status badge | ✅ Complete |
| Category Strategy — 7 frameworks + slide deck | ✅ Complete |
| AI Assistant — chat panel (keyword-matched) | ✅ Complete |
| Notifications — bell dropdown, per-item dismiss | ✅ Complete |
| Settings — dark mode toggle, density, account | ✅ Complete |
| AI Assistant — real Claude API streaming | 🔴 Planned |
| Live notifications — `/api/alerts` endpoint | 🔴 Planned |
| Strategy screen — real API wiring | 🔴 Planned |

---

## Privacy & Data Handling

- **Uploaded documents** (contracts, pricing sheets) are processed in memory only. Nothing is written to disk beyond the structured extraction result. Refreshing clears session state.
- **Spend data** is stored in a per-client SQLite database. No raw data is sent to external services except vendor names for AI classification.
- **API key** is read from `.env` at startup and never logged or exposed in the UI.

---

## Part of the Procurement AI Stack

SpendLens is the data platform at the centre of a four-agent system:

| Agent | Role | Interaction with SpendLens |
|---|---|---|
| **Icarus** | Personal AI OS — user interface | Queries `/api/suppliers/lookup/{name}` for dual-check answers |
| **SpendLens** | Spend analytics, vendor records, approval workflows | Hosts vendor DB; calls Hades at onboarding; exposes lookup API |
| **Hades** | Supplier due diligence — autonomous research, risk scoring | Called by SpendLens; writes risk fields back to vendor record |
| **Hermes** | Market intelligence — 590+ suppliers, continuous crawling | Signals injected into SpendLens Icarus feed; shares Redis with Hades |

---

## Background

SpendLens is built by someone who has worked in enterprise procurement — not just around it.

The AI layer doesn't replace procurement expertise. It amplifies it.

---

*Interested in the architecture, a demo, or contributing? Get in touch.*
