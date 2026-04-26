# SpendLens — Project Handover Document
*Last updated: April 26, 2026*

---

## What is SpendLens?

An AI-native procurement intelligence platform. It turns raw accounting/ERP exports (CSV, Excel) into CFO-ready insights. Built with Python + Panel + Plotly + Claude API.

**Not** a one-time report generator — a living intelligence platform that gets smarter with every upload.

---

## Tech Stack

- **Frontend/UI:** Panel (Python), Plotly, HTML/CSS
- **AI:** Anthropic Claude API (`claude-sonnet-4-6`)
- **Database:** SQLite (local, per-client)
- **Language:** Python 3.11+
- **Dependencies:** panel, plotly, pandas, anthropic, feedparser, python-dotenv

---

## Folder Structure

```
SpendLens_App/
├── app.py                  ← Main dashboard (Panel app, run with: python app.py)
├── icarus.py               ← Market intelligence agent (scraping + AI analysis)
├── icarus_ui.py            ← Icarus UI Panel component
├── .env                    ← ANTHROPIC_API_KEY=sk-ant-... (UTF-8, no BOM)
├── requirements.txt
├── vendor_cache.json       ← Cached vendor classifications
├── clients/
│   └── default/
│       ├── spendlens.db    ← SQLite database (gitignored)
│       └── icarus_memory.db← Icarus memory/feedback (gitignored)
└── modules/
    ├── __init__.py
    ├── column_mapper.py    ← Maps uploaded file columns to standard schema
    ├── data_cleanup.py     ← Deduplication, type fixing, normalization
    ├── category_mapper.py  ← AI-based vendor → spend category classification
    ├── flag_engine.py      ← Compliance flags (maverick, shadow IT, freelancer)
    ├── database.py         ← SQLite operations
    └── cfo_reports.py      ← Excel export
```

---

## How to Run

```bash
# Activate venv
.venv\Scripts\Activate.ps1   # Windows PowerShell

# Start dashboard
python app.py
# Opens at http://localhost:5006

# Run Icarus standalone (market intelligence)
python icarus.py
```

---

## Dashboard (app.py)

### Tabs
1. **Dashboard** — KPI cards, spend charts, risk map, contracts, EBITDA
2. **Deep Dive** — CAGR, Capex/Opex, Treemap
3. **🪶 Icarus** — Market intelligence agent (see below)

### Sidebar
- Year filter
- File upload (CSV/Excel)
- Export CFO Report
- Status log

### Upload Pipeline (runs in background thread)
1. Read file → `pd.read_csv` or `pd.read_excel`
2. Column mapping → `modules/column_mapper.py`
3. Data cleanup → `modules/data_cleanup.py`
4. AI category classification → `modules/category_mapper.py`
5. Compliance flags → `modules/flag_engine.py`
6. Save to SQLite → `modules/database.py`
7. Update dashboard charts

### Default Dataset
Hardcoded Parloa-like SaaS company spend data (11 categories, 2022-2026).
When user uploads real data, dashboard updates with uploaded data.

**Important:** Remove `dataset_label` display — client data should not be shown. Currently `dataset_label = pn.pane.Markdown("")` (already emptied).

---

## Database Schema (SQLite)

**Tables in `clients/default/spendlens.db`:**
- `uploads` — log of every file upload
- `transactions_raw` — raw rows from uploaded files
- `transactions_enriched` — processed rows with category + flags
- `vendors` — canonical vendor knowledge base
- `matches` — accounting ↔ procurement links

---

## Icarus — Market Intelligence Agent

### Files
- `icarus.py` — Core agent logic
- `icarus_ui.py` — Panel UI component

### What it does
On-demand procurement signal detection:
1. Scrapes RSS feeds (Reuters, The Register, Handelsblatt, DatacenterDynamics, Euractiv, Spend Matters)
2. Filters by client's spend categories
3. Claude API analyzes articles → extracts procurement signals with relevance score (1-10), impact (positive/negative/neutral), and suggested action
4. Saves to `icarus_memory.db` and learns from user feedback

### Key function
```python
result = icarus.run(
    client_categories=["Cloud & Compute", "Hardware", ...],
    client_name="Client Name"
)
# Returns: {"signals": [...], "query_id": int, "article_count": int}
```

### Memory / Learning
- Every query saved to `icarus_memory.db`
- User can mark signals as "relevant" / "not_relevant"
- Category weights update automatically (+0.1 for relevant, -0.05 for not_relevant)
- Next run re-ranks signals using learned weights

### Icarus UI Component
```python
from icarus_ui import IcarusPanel

icarus_panel = IcarusPanel(
    client_categories=list(df_meta["category"].dropna().unique()),
    client_name="Client"
)
icarus_panel.load_recent()  # Load previously saved signals
icarus_panel.view()          # Returns Panel layout object
```

### UI Features
- SpendLens logo (hexagon + green eye) animates/blinks during loading
- Category tabs (All, Cloud & Compute, Hardware, etc.) with signal counts
- Signal cards — collapse/expand with full summary + action + source link
- Text input + voice input (Web Speech API, Chrome only)
- Feedback buttons (Yes/No) per signal → feeds learning system

---

## Spend Categories (11)

Standard taxonomy used across app and Icarus:
1. Cloud & Compute
2. Hardware
3. Software & SaaS
4. Professional Services
5. Facilities
6. Logistics
7. AI & ML
8. Telecom
9. Freelancer & Contractors
10. Travel & Expenses
11. Marketing

---

## Known Issues / TODOs

### Immediate fixes needed in app.py:
1. **`AI SETTINGS` field in sidebar** — `api_key_input` widget visible to users, should be removed. The API key comes from `.env` file, no need for UI input.
   - Search for `api_key_input` in `app.py` and remove the widget + sidebar entry
2. **Icarus tab** — Currently loads but may fail if import error. Check terminal output after `python app.py` for errors.
3. **Dataset label** — Already fixed to `""` but sidebar still shows "Dataset: Default" from somewhere. Check for second occurrence.

### Icarus RSS feeds
Some feeds return 403 in server environments. On local machine (user's Windows laptop) most work fine. The `User-Agent` header is set to avoid blocks.

### Voice input
Uses `window.SpeechRecognition` — only works in Chrome. No fallback for other browsers.

---

## Environment

- **OS:** Windows 11 (user's machine)
- **Shell:** PowerShell (not bash — `head`, `cat` etc. don't work, use `Get-Content`)
- **Python env:** `.venv` in project folder
- **IDE:** VS Code
- **API Key:** In `.env` as `ANTHROPIC_API_KEY` — must be UTF-8 without BOM

---

## Design System

**Colors:**
- `NAVY = "#1B3A6B"` — primary
- `NAVY2 = "#2E5BA8"` — secondary
- `GREEN = "#1A7A4A"` — positive/success
- `YELLOW = "#B8860B"` — warning
- `RED = "#C0392B"` — danger
- `BG = "#FFFFFF"` — background
- `CARD = "#F8F9FA"` — card background

**Font:** Georgia, serif (dashboard); system-ui sans-serif (Icarus UI)

**Logo:** Hexagon with geometric inner lines + green eye. SVG hardcoded in `app.py` (white version for dark header) and `icarus_ui.py` (navy/green version for light background).

---

## Phase Roadmap

| Phase | Name | Status |
|-------|------|--------|
| Phase 1 | Core Dashboard & AI Pipeline | 🔨 90% done |
| Phase 2 | Market Intelligence (Icarus) | 🔨 In progress |
| Phase 3 | Multi-client / SaaS | 💡 Future |

### Phase 1 remaining:
- Remove `api_key_input` from sidebar
- Fix Icarus tab integration
- Test full upload pipeline with real data

### Phase 2 remaining:
- Icarus text query → search saved signals + live scan combined
- Voice input refinement
- Feedback loop fully wired
- Scheduled background scans (optional)

---

## Git

Repository exists. `.gitignore` includes:
- `.env`
- `clients/default/spendlens.db`
- `clients/default/icarus_memory.db`
- `vendor_cache.json`
- `__pycache__/`
- `.venv/`
