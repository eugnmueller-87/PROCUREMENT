# SpendLens — Handover Document
**Date:** 2026-04-29  
**Last commit:** `5ebdcaa` — feat: Icarus Deep Scan, 16 RSS sources, UI layout overhaul  
**Session additions (2026-04-29):** Category Strategy tab — Kraljic, PESTEL, SWOT, Porter's Five Forces, TCO, Negotiation Levers, Strategy Recommendation + HTML slide deck export

---

## What SpendLens Is

An AI-powered procurement intelligence platform built with Python + Panel (HoloViz).  
Data flows through a 5-stage upload pipeline, persists in SQLite, and is visualised in a multi-tab dashboard. Icarus provides live market intelligence. Category Strategy is the workbench where category managers prepare and export their procurement strategy.

**Start the app:**
```bash
source .venv/Scripts/activate   # Git Bash
PYTHONUTF8=1 panel serve app.py --show --port 5006
```
`PYTHONUTF8=1` is required on Windows to handle German umlauts and non-ASCII vendor names.  
`--autoreload` only watches `app.py` — changes to any imported module require a manual server restart.

---

## Architecture

```
app.py                      — Panel dashboard, tab layout, upload orchestration
icarus.py                   — Market intelligence agent (RSS, Claude API, SQLite)
icarus_ui.py                — Icarus Panel UI component
category_strategy_ui.py     — Category Strategy Panel UI component
modules/
  column_mapper.py          — Schema normalisation (fuzzy + Claude fallback)
  data_cleanup.py           — Spend normalisation, deduplication
  category_mapper.py        — AI vendor classification (chunked + cached)
  flag_engine.py            — Compliance & risk flag derivation
  database.py               — SQLite persistence (WAL mode, hash dedup)
  cfo_reports.py            — Excel export generation
  category_strategy.py      — Category strategy AI calls + SQLite persistence
  deck_generator.py         — Standalone HTML slide deck generator
  supplier_profiler.py      — (stub) future supplier financial health scoring
```

**Persistence:**
- `clients/default/spendlens.db` — per-client SQLite (WAL mode). Tables: `uploads`, `transactions_raw`, `transactions_enriched`, `vendors`, `matches`, `category_strategies`
- `clients/default/icarus_memory.db` — Icarus signals, user feedback, category weights
- `vendor_cache.json` — vendor→category cache, persists across restarts

---

## Dashboard Tabs

| Tab | Index | Content |
|---|---|---|
| Dashboard | 0 | KPI cards, spend evolution, budget vs actuals, procurement health gauges |
| Deep Dive | 1 | Treemap with supplier drill-down, spend comparison chart, Capex/Opex, Risk & Bottlenecks bubble chart, ICARUS AI insight strips |
| Compliance Scorecard | 2 | EcoVadis-style supplier cards, ABC tier classification, contract status icons, compliance score with trend, inline editing |
| Icarus | 3 | Market intelligence feed, Ask Icarus, RFP/negotiation brief, document upload |
| Category Strategy | 4 | AI-generated strategy frameworks per category + HTML slide deck export |

Sidebar is hidden on tabs 3 and 4 — both are full-width experiences.

---

## Category Strategy Tab

**Primary user:** Category manager preparing their procurement strategy.  
**Trigger:** Select a category from the dropdown, click **Generate All Frameworks**.

### Frameworks (Claude Haiku, ~25 seconds total, sequential)

| Framework | What Claude generates |
|---|---|
| **Kraljic Matrix** | Quadrant (Strategic / Leverage / Bottleneck / Non-critical), supply risk score 1–10, profit impact score 1–10, rationale, recommended posture, key actions |
| **PESTEL** | 3 bullet points per dimension (P, E, S, T, En, L) seeded from Icarus market signals for the category |
| **SWOT** | Buyer-perspective 2×2 — Strengths, Weaknesses, Opportunities, Threats — from spend data + signals |
| **Porter's Five Forces** | High/Medium/Low rating + score + 2 factors per force; overall market summary |
| **TCO Breakdown** | % breakdown across 5 cost components (invoice, onboarding, integration, resource, compliance); key insight; reduction levers |
| **Negotiation Levers** | 5 levers with saving potential (e.g. "8–15%"), effort (Low/Medium/High), priority (High/Medium/Low); recommended approach; optimal timing |
| **Strategy Recommendation** | Headline, strategic posture, Year 1 / Year 2 priorities, Year 3 vision, 3 success KPIs |

### Persistence
Results saved to `category_strategies` table in `spendlens.db` via UPSERT. Returning to a previously generated category loads instantly — no re-generation needed unless market conditions have changed.

### Slide Deck Output
**"Generate Strategy Deck"** downloads a self-contained HTML file:
- 10 slides: Cover → Spend Overview → Kraljic → PESTEL → SWOT → Porter's → TCO → Levers → Recommendation
- SpendLens logo top-right on every slide
- Navy `#1B2A4A` / green `#1D9E75` colour scheme
- Keyboard arrow keys or on-screen buttons navigate
- `Ctrl+P` prints each slide as a page (CSS `@media print` handles page breaks)

### Key files
- `category_strategy_ui.py` — Panel component (same static-JS-pane pattern as `icarus_ui.py`)
- `modules/category_strategy.py` — Claude Haiku prompts, `init_strategy_table()`, `load_strategy()`, `save_framework()`, `generate_all_frameworks(progress_cb)`
- `modules/deck_generator.py` — `generate_strategy_deck(category, strategy, spend_data) -> str`

---

## Icarus — Market Intelligence Agent

### RSS Sources (16 feeds)
| Group | Feeds |
|---|---|
| General tech/business | Reuters Business, Reuters Technology, The Register, Ars Technica, ZDNet |
| Procurement & supply chain | Spend Matters, Supply Chain Dive, Supply Chain Brain, CPO Rising (Ardent Partners) |
| European/German business | Handelsblatt, WirtschaftsWoche, Euractiv |
| Data centre infrastructure | DatacenterDynamics |
| Commodity & energy | OilPrice |
| HR & freelancer | FreelancerMap |
| Travel | Business Travel News |

**Why no McKinsey/Deloitte/PwC/KPMG RSS?** They don't publish reliable RSS. Their reports are surfaced via Grok cluster queries that explicitly name these firms.

### Grok Live Search (4 clusters)
1. **Tech & Cloud Procurement** — cloud pricing, SaaS, AI APIs, semiconductors, hardware
2. **People & Professional Services** — freelancer rates, consulting M&A, marketing fees
3. **Facilities, Real Estate & Travel** — leases, energy, corporate travel, hotels
4. **Procurement Strategy & Regulation** — supply chain risk, EU AI Act, tariffs, ISM/Spend Matters

**Known limitation:** Grok live search only works with `grok-4` family models. The current xAI account has `grok-3-mini` only — Grok silently returns `[]` and RSS feeds carry the full load. Upgrading the xAI tier unlocks live search with no code changes.

### Scan Modes
```python
SCAN_PROFILES = {
    "small": {"articles_per_feed": 5,  "use_grok": False},  # ~$0.05/scan
    "big":   {"articles_per_feed": 15, "use_grok": True},   # ~$0.13/scan
}
```

### AI Cost Reference
| Operation | Cost |
|---|---|
| Quick Scan (5 articles × 16 feeds) | ~$0.05 |
| Deep Scan (15 articles × 16 feeds) | ~$0.12 |
| Grok clusters (when active) | ~$0.008 |
| Ask Icarus / RFP / Weekly Brief | ~$0.01–0.05 each |
| Category Strategy (all 7 frameworks) | ~$0.03 |
| €2 budget | ~15 Deep Scans or ~40 Quick Scans |

### Icarus UI — Static JS Pane Pattern
Panel updates HTML panes via `innerHTML`, which **does not re-execute `<script>` tags**. All JS functions (`toggleCard`, `filterCat`, `icarusFeedback`) are defined once in `_js_pane` (height=0, never updated). Dynamic panes contain only HTML — no `<script>` tags. Category Strategy uses the same pattern.

---

## Upload Pipeline

1. **column_mapper.py** — fuzzy-matches arbitrary column names to 14-field standard schema; Claude API fallback for unmapped columns
2. **data_cleanup.py** — deduplicates rows, normalises spend (German `1.234,56` + English `$1,234.56` formats), strips junk rows
3. **category_mapper.py** — classifies vendors into 11 categories; chunked batching; cached in `vendor_cache.json` (~$0.05/1000 vendors)
4. **flag_engine.py** — derives compliance flags (maverick, shadow IT, freelancer, PO status, contract expiry); uses "Unknown" when data is absent
5. **database.py** — inserts raw + enriched records; hash-based dedup prevents double-inserts

**Known flag_engine fix (in current code):** Guard against duplicate column names returning `pd.Series` instead of scalar in `flag_contract_status`:
```python
contract_val = row[contract_col]
if isinstance(contract_val, pd.Series):
    contract_val = contract_val.iloc[0]
```

---

## Compliance Scorecard

- **ABC tiers:** A = top 80% spend, B = next 15%, C = remainder; criticality bump for sole-source/Critical-risk suppliers
- **Compliance score:** PO coverage 35% · contract coverage 35% · concentration 20% · maverick 10%
- **Contract icons:** 🟢 Under Contract · 🟡 Expiring Soon · 🔴 No Contract / Expired
- **Inline editing** — Category, Tier, Relationship persists to SQLite + back-propagates to `vendor_cache.json`

---

## API Keys

All keys in `.env` at project root:
```
ANTHROPIC_API_KEY=sk-ant-...   # Claude API — required for all AI features
XAI_API_KEY=...                # xAI Grok — optional; Grok live search needs grok-4 tier
```

The API key input widget in the sidebar is **cosmetic** — it does not set the runtime key. Keys must be in `.env`.

---

## What Is Complete

| Component | Status |
|---|---|
| Upload pipeline (all 5 stages) | ✅ Complete |
| 11-category taxonomy | ✅ Complete |
| Dashboard — all chart tabs | ✅ Complete |
| Dashboard — ICARUS AI insight strips (period-aware) | ✅ Complete |
| Compliance Scorecard with inline editing | ✅ Complete |
| CFO Excel export | ✅ Complete |
| Icarus — RSS signal scanner (16 feeds, parallel fetch) | ✅ Live |
| Icarus — Quick Scan / Deep Scan modes | ✅ Live |
| Icarus — Ask / query mode | ✅ Live |
| Icarus — RFP & negotiation brief | ✅ Live |
| Icarus — Weekly intelligence brief | ✅ Live |
| Icarus — Document upload (in-memory, AI summary) | ✅ Live |
| Icarus — Signal deduplication | ✅ Live |
| Icarus — Signals load on dashboard startup | ✅ Live |
| Icarus — Grok cluster queries | ✅ Code complete (blocked by xAI tier — needs grok-4) |
| Icarus — Feedback learning loop | 🔨 Partially wired — `record_feedback()` exists; Bokeh bridge needs end-to-end test |
| Category Strategy tab — 7 AI frameworks | ✅ Live |
| Category Strategy — HTML slide deck export | ✅ Live |

---

## What Is Planned Next (TODO.md Priority Order)

### 1. ECB FX Rates — Multi-currency → EUR conversion ✦ Free
**Where:** `modules/data_cleanup.py` — after spend normalisation, before DB insert  
**How:** Fetch daily EUR rates from ECB XML API at upload time; convert all non-EUR amounts to EUR; store original currency + FX rate per transaction  
**Value:** Datasets from international operations currently show raw currency amounts, distorting spend totals  
**Effort:** ~1 day

### 2. OpenCorporates — Supplier legal registration enrichment ✦ Free tier
**Where:** `modules/category_mapper.py` batch loop, cached in `vendor_cache.json`  
**How:** For each new vendor, query OpenCorporates free API for legal name, jurisdiction, incorporation date, company status (active / dissolved)  
**Value:** Flags offshore/shell/dissolved vendors; enables jurisdiction-based risk scoring  
**Effort:** ~1 day

### 3. Quandl / Nasdaq Data Link — Commodity price context ✦ Free tier
**Where:** `icarus.py` — new `fetch_commodity_context(category)` called before `query_with_claude()`  
**How:** Fetch benchmark indices (energy, metals, semiconductors) at scan time; inject as context into Icarus answers and negotiation briefs  
**Value:** Gives Icarus hard data to challenge vendor price increase claims  
**Effort:** ~2 days

### 4. User Profiles & Role-Based Access Control ✦ No external API
**Where:** New `modules/auth.py` + `app.py` login gate  
**Roles:** Reader (view + export) · Editor (+ upload, edit, Ask Icarus) · Administrator (+ user management, audit log)  
**How:** `users` table in SQLite with bcrypt password hashes; Panel login pane before dashboard; `pn.state.user` cookie; role-gated widgets  
**Effort:** ~3 days

### 5. Creditsafe / D&B — Supplier financial health ✦ Paid API
**Where:** `modules/supplier_profiler.py` (stub exists)  
**How:** API lookup per supplier; `financial_health_score` column in `vendors` table; surfaced in Compliance Scorecard  
**Effort:** ~3 days

### Backlog
- [ ] QBR deck — per Tier A supplier HTML deck (performance review, pricing context, risks, commitments). Design complete, build deferred.
- [ ] Scheduled Icarus background scans (`pn.state.schedule_task` or external cron)
- [ ] Spend Variance Analysis tab
- [ ] Supplier Risk Score (composite: compliance + financial health + single-source)
- [ ] Spend Forecast (Q+1) — linear extrapolation
- [ ] Multi-client support (client selector in sidebar)
- [ ] NewsAPI.org integration
- [ ] Slack / Teams webhook for proactive procurement alerts

---

## Known Technical Gotchas

| Issue | Root Cause | Status |
|---|---|---|
| Panel autoreload ignores imported modules | `--autoreload` watches only `app.py` | Permanent — always restart after changing any module |
| Grok live search returns [] silently | `grok-3-mini` doesn't support `web_search` tool; only `grok-4` does | Code correct — needs xAI account upgrade |
| Windows Unicode errors in terminal | Python default encoding is cp1252 on Windows | Always start with `PYTHONUTF8=1` |
| Haiku batch JSON cut-off | 15 articles × ~150 tokens exceeded old max_tokens=2000 | Fixed — now 4000 tokens |
| Duplicate column → pd.Series TypeError | Pandas returns Series when a column appears twice | Fixed in flag_engine.py with isinstance guard |
| Category Strategy deck filename | FileDownload filename is fixed at generation time — doesn't include category name dynamically in Panel's current FileDownload widget | Known UX limitation — filename shows as `category_strategy.html` regardless of category |

---

## File Map

```
SpendLens_App/
├── app.py                        Dashboard + upload orchestration
├── icarus.py                     Market intelligence agent
├── icarus_ui.py                  Icarus Panel UI component
├── category_strategy_ui.py       Category Strategy Panel UI component
├── icarus_schedule.py            (standalone) Scheduled Icarus runner
├── modules/
│   ├── column_mapper.py          Schema normalisation
│   ├── data_cleanup.py           Data normalisation
│   ├── category_mapper.py        AI vendor classification
│   ├── flag_engine.py            Compliance & risk flagging
│   ├── database.py               SQLite persistence
│   ├── cfo_reports.py            Excel export
│   ├── category_strategy.py      Category strategy AI + SQLite persistence
│   ├── deck_generator.py         HTML slide deck generator
│   └── supplier_profiler.py      (stub) Supplier financial health
├── clients/
│   └── default/
│       ├── spendlens.db          Per-client spend data + category strategies
│       └── icarus_memory.db      Icarus signals + feedback
├── vendor_cache.json             Vendor→category cache
├── docs/
│   ├── logo.svg                  SpendLens hexagon logo
│   ├── PROFILE_README.md         GitHub profile README
│   └── screenshots/              Dashboard screenshots for README
├── .env                          API keys (not in git)
├── requirements.txt              Python dependencies
├── CLAUDE.md                     Instructions for AI coding assistant
├── HANDOVER.md                   This document
├── TODO.md                       API integration roadmap + backlog
└── README.md                     Public-facing project README
```
