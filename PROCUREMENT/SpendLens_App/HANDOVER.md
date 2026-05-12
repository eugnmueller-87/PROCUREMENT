# SpendLens — Handover (2026-05-09)

## What SpendLens is

AI-powered procurement intelligence platform. Processes messy enterprise spend data (CSV/Excel from SAP, Coupa, Excel) through a 5-stage AI pipeline and surfaces compliance risks, supplier scorecards, and market context.

Runs locally as a Panel web app:
```bash
PYTHONUTF8=1 panel serve app.py --show --autoreload
```
→ http://localhost:5006/app

---

## The three systems and how they relate

| System | What it does | Where it runs |
|--------|-------------|---------------|
| **SpendLens** | Spend analysis, compliance, supplier scorecards | Local (your machine) |
| **Hermes** | Market intelligence crawler, RAG over signals | Railway (hermes crawler agent) |
| **Icarus** | Telegram bot, routes commands to tools | Railway (icarus-prod) |

**Current connections:**
- SpendLens reads Hermes signals via `modules/hermes_client.py` (Upstash Redis) — partially wired
- Icarus talks to Hermes via HTTP (`HERMES_URL` env var) — fully wired
- SpendLens and Icarus (Telegram) have NO connection — SpendLens data is invisible to Telegram

**SpendLens has its own internal "Icarus" agent (`icarus.py`)** — an RSS crawler that predates the Telegram bot. It's confusing but both exist. The goal is to replace SpendLens' internal crawler with calls to the real Hermes instead.

---

## Current architecture

```
Browser (localhost:5006)
    │
    ▼
Panel Dashboard (app.py)
    ├── Upload pipeline
    │   ├── column_mapper.py     (Claude Haiku — schema normalization)
    │   ├── data_cleanup.py      (currency conversion, vendor dedup, date parsing)
    │   ├── category_mapper.py   (Claude Haiku — vendor → category, cached in vendor_cache.json)
    │   ├── flag_engine.py       (PO status, maverick, shadow IT, freelancer flags)
    │   └── database.py          (SQLite insert — immutable raw + recomputable enriched)
    │
    ├── icarus_ui.py → icarus.py
    │   (OWN RSS crawler — 20+ feeds, Claude Haiku signal analysis)
    │   (should be replaced with Hermes HTTP calls)
    │
    ├── category_strategy_ui.py → category_strategy.py
    │   (7 strategy frameworks via Claude Sonnet)
    │
    └── supplier_profiler.py
        (ABC tier assignment, compliance scoring)

Storage:
    clients/default/spendlens.db       — 6 tables
    clients/default/icarus_memory.db   — signals, queries, weights
    vendor_cache.json                  — vendor→category cache (never delete)
```

---

## Database schema

**File:** `clients/default/spendlens.db`

| Table | Purpose |
|-------|---------|
| `uploads` | Audit log of all file uploads |
| `transactions_raw` | Immutable source of truth (deduped by row_hash) |
| `transactions_enriched` | Derived flags — recomputable, references raw |
| `vendors` | Persistent vendor knowledge (category, risk, OpenCorporates data) |
| `matches` | Accounting ↔ Procurement linking with confidence score |
| `supplier_profiles` | ABC tier + compliance score + relationship status |

Key design rule: `transactions_raw` is immutable. Never update rows there. All intelligence goes into `transactions_enriched` or `vendors`.

---

## What works well — don't break

1. **5-stage upload pipeline** — production quality, leave it alone
2. **vendor_cache.json** — accumulated classification memory, never delete
3. **flag_engine.py** — complex compliance logic, read fully before touching
4. **supplier_profiler.py** — ABC tier with manual override that survives recomputation
5. **category_strategy workbench** — 7 frameworks, HTML export, results cached in SQLite
6. **hermes_client.py** — already reads Hermes signals from Redis, partially wired

---

## What's missing — integration tasks

### Task 1 — Replace internal RSS crawler with Hermes
**Files:** `icarus_ui.py`, `icarus.py`

When user clicks "Scan Market", call the real Hermes HTTP API instead of running `icarus.py`'s own RSS crawler.

`modules/hermes_client.py` already has `get_procurement_briefing()` — wire this into the scan button handler in `icarus_ui.py`. The scan result format needs to match what `icarus_ui.py` expects (use `to_icarus_signals()` converter already in `hermes_client.py`).

```python
# hermes_client.py already has this — just call it
signals = hermes_client.get_procurement_briefing(limit=20)
icarus_signals = hermes_client.to_icarus_signals(signals)
```

### Task 2 — Push top vendors to Hermes watchlist on upload
**Files:** `app.py` (upload handler ~line 200), `modules/hermes_client.py`

After upload pipeline completes, extract top 20 vendors by spend → call Hermes `/watchlist/{company}` endpoint.

```python
# Add to hermes_client.py
def watch_vendor(vendor_name: str):
    requests.post(
        f"{HERMES_URL}/watchlist/{vendor_name}",
        headers={"x-api-key": HERMES_API_KEY},
        timeout=10
    )

# Call from app.py after pipeline completes
top_vendors = db.get_top_vendors(limit=20)
for vendor in top_vendors:
    hermes_client.watch_vendor(vendor["name"])
```

Result: Hermes crawls RSS every 2 hours specifically for your uploaded suppliers.

### Task 3 — Expose SpendLens data as Icarus Telegram tools
**New file:** `api.py` — FastAPI wrapper around `database.py`

Endpoints needed:
```
GET /spend/summary          — total spend by category, current period
GET /spend/maverick         — maverick spend transactions
GET /vendors/top            — top vendors by spend + compliance scores
GET /vendors/{name}         — single vendor profile
GET /health                 — liveness check
```

Then add `bot/skills/spendlens.py` in the Icarus repo with tools that call this API. Telegram bot can then answer "what's our Cloud spend this month?" from SpendLens data.

### Task 4 — Show Hermes signals per vendor in SpendLens dashboard (optional)
In the vendor detail view, fetch `GET /query/{vendor_name}` from Hermes and show the last 5 signals inline. Gives market context next to spend data without leaving SpendLens.

### Task 5 — Deploy SpendLens to Railway (later)
- SQLite → Postgres (Railway provides this natively)
- `panel serve app.py` → deploy as Railway service
- Multi-client support already built (`clients/{name}/spendlens.db`)

---

## Environment variables

**File:** `.env` at project root

```
ANTHROPIC_API_KEY=...           # Claude API
XAI_API_KEY=...                 # Grok live search (optional)
UPSTASH_REDIS_REST_URL=...      # Same Upstash as Icarus bot
UPSTASH_REDIS_REST_TOKEN=...    # Same Upstash as Icarus bot
HERMES_URL=...                  # ADD THIS — Hermes Railway URL
HERMES_API_KEY=...              # ADD THIS — Hermes API key
```

Get `HERMES_URL` and `HERMES_API_KEY` from Railway → hermes crawler agent → Variables.

---

## Claude model usage

| Task | Model | Reason |
|------|-------|--------|
| Column mapping | `claude-haiku-4-5-20251001` | Fast, cheap, rule-based fallback |
| Vendor classification | `claude-haiku-4-5-20251001` | Batched, cached after first run |
| Signal analysis | `claude-haiku-4-5-20251001` | High volume batches |
| NL queries | `claude-sonnet-4-6` | Complex reasoning |
| Strategy frameworks | `claude-sonnet-4-6` | Long-form generation |

Do NOT upgrade haiku tasks to sonnet — batch volumes make cost spike significantly.

---

## What NOT to do

- Don't delete `vendor_cache.json` — accumulated classification memory
- Don't modify `transactions_raw` rows — immutable by design
- Don't replace Panel with another UI framework — too much state tied to Panel widgets
- Don't add LangChain — Claude native tool use is cleaner and already in place
- Don't add n8n — Railway + GitHub Actions already handles orchestration
- Don't merge SpendLens' internal `icarus.py` with the Telegram bot — replace it with Hermes calls instead
