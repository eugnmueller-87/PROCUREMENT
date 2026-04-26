# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
# Activate virtual environment first
.venv\Scripts\activate       # Windows PowerShell
source .venv/Scripts/activate # Git Bash

# Start the dashboard
panel serve app.py --show --autoreload

# Start Icarus market intelligence agent (standalone)
python icarus.py
```

Requires `ANTHROPIC_API_KEY` in `.env` at project root.

## Architecture

SpendLens is a procurement analytics dashboard. Data flows through a 5-stage pipeline on upload, then persists in SQLite for the Panel dashboard to query and visualize.

### Upload pipeline (triggered in `app.py` on file upload)
1. **`modules/column_mapper.py`** — Maps arbitrary CSV/Excel columns to a 14-field standard schema using fuzzy matching, with Claude API fallback for unmapped columns
2. **`modules/data_cleanup.py`** — Deduplicates rows, normalizes spend values (handles German `1.234,56` and English `$1,234.56` formats), strips junk rows
3. **`modules/category_mapper.py`** — Classifies each vendor into one of 11 procurement categories using Claude API; results cached in `vendor_cache.json` to minimize API calls (~$0.05/1000 vendors)
4. **`modules/flag_engine.py`** — Derives compliance & risk flags: maverick spend, shadow IT, freelancer detection, missing POs, contract expiry; marks "Unknown" when data is absent rather than guessing
5. **`modules/database.py`** — Inserts raw + enriched records into SQLite; raw data is immutable; hash-based deduplication prevents double-inserts

### Persistence
- **`clients/default/spendlens.db`** — Per-client SQLite database (WAL mode). Tables: `uploads`, `transactions_raw`, `transactions_enriched`, `vendors`, `matches`
- **`vendor_cache.json`** — Vendor→category cache persisted across sessions; loaded on startup, saved after each batch classification

### Dashboard (`app.py`)
Panel app with two tabs (Dashboard, Deep Dive) plus an Icarus tab (in progress). Sidebar: year filter, file upload, CFO Excel export, status log. Color scheme: Navy (`#1B2A4A`) / White / Green accent (`#00A86B`).

### Icarus market intelligence (`icarus.py` + `icarus_ui.py`)
Scrapes RSS feeds (Reuters, The Register, Handelsblatt, etc.), sends articles to Claude API for procurement signal extraction (relevance 1–10, impact, suggested action), stores signals + feedback in `clients/default/icarus_memory.db`. The UI panel (`icarus_ui.py`) includes a category-tabbed signal card view and a voice input (Chrome only).

### Procurement taxonomy (11 categories)
Cloud & Compute · AI/ML APIs & Data · IT Software & SaaS · Telecom & Voice · Recruitment & HR · Professional Services · Marketing & Campaigns · Facilities & Office · Real Estate · Hardware & Equipment · Travel & Expenses

## Key modules reference
| File | Responsibility |
|------|---------------|
| `app.py` | Panel dashboard, upload orchestration |
| `icarus.py` | Market intelligence agent |
| `icarus_ui.py` | Icarus Panel UI component |
| `modules/column_mapper.py` | Schema normalization |
| `modules/data_cleanup.py` | Data normalization |
| `modules/category_mapper.py` | AI vendor classification |
| `modules/flag_engine.py` | Compliance & risk flagging |
| `modules/database.py` | SQLite persistence |
| `modules/cfo_reports.py` | Excel export generation |

## Known issues (from handover doc)
- Icarus tab not yet wired into the main `app.py` tab set
- API key input widget in sidebar is cosmetic (key must be in `.env`)
- Dataset label display for default hardcoded dataset needs polish
