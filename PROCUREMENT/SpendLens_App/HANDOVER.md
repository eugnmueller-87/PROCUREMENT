# SpendLens — Session Handover
**Date:** 2026-05-17  
**Session scope:** Full Panel → FastAPI + React migration + post-launch polish  
**Branch:** `main` — all changes live on Railway

---

## What changed this session

SpendLens was migrated from a Panel/Bokeh dashboard to a production-grade React SPA served by FastAPI.

| Before | After |
|--------|-------|
| `panel serve app.py` | `uvicorn api:app` |
| Panel widgets + Bokeh charts | React 18 (Babel standalone, no build step) |
| No REST API | FastAPI at `/api/*` |
| Bokeh WebSocket | Plain HTTP fetch from browser |

**All Python business logic is unchanged** — `modules/`, `lex.py`, `icarus.py`, SQLite all work exactly as before.

---

## File map

### Backend
| File | Role |
|------|------|
| `api.py` | FastAPI — all REST endpoints + static frontend serving |
| `railway.toml` | `startCommand = "uvicorn api:app --host 0.0.0.0 --port $PORT"` |
| `Procfile` | Same start command (Railway reads this too) |
| `requirements.txt` | Panel/Bokeh removed; `python-multipart`, `aiofiles`, `uvicorn[standard]` added |

### Frontend (`frontend/`)
| File | Role |
|------|------|
| `index.html` | Entry point — loads React 18 UMD, Babel standalone, all JSX in order |
| `styles.css` | Claude Design system — oklch tokens, layout grid, all component classes |
| `icons.jsx` | SVG icon set → `window.Icons` |
| `charts.jsx` | Chart primitives: `StackedArea`, `SpendVsBudget`, `Treemap`, `RiskArc`, `Donut`, `Sparkline`, `Waterfall`. Also exports `riskColor()` / `riskClass()` shared utilities |
| `shell.jsx` | `Sidebar`, `TopBar` (with AI chat, notifications, settings), `CmdPalette`, `Drawer` |
| `tweaks-panel.jsx` | Stub — all components return null, kept for compatibility |
| `app.jsx` | Hash router, global `DrawerBody` handling 4 drawer kinds |
| `screens/dashboard.jsx` | KPIs, stacked area trend, YoY diverging bar, category risk matrix table |
| `screens/deepdive.jsx` | Growth bars, spend share %, supplier count, treemap — all drill to drawer |
| `screens/compliance.jsx` | Supplier scorecard with tier avatars, multi-filter, sort, click-to-drawer |
| `screens/icarus.jsx` | Market signal feed, category tabs, RSS scan trigger |
| `screens/strategy.jsx` | Kraljic, PESTEL, SWOT, negotiation frameworks — **placeholder, not wired to API** |
| `screens/supplier.jsx` | Hades due diligence — proxied via `/api/hades/*` (URL set in Railway env var `HADES_URL`) |
| `screens/clm.jsx` | Contract scan/save, drag-drop, RiskArc gauge, clause cards, history table |

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Healthcheck — returns transaction count |
| GET | `/api/dashboard?year=` | KPIs, trend, categories, expiring contracts. Returns demo data if DB empty |
| GET | `/api/suppliers` | Supplier profiles with scores, tiers, risk |
| GET | `/api/contracts` | All scanned contracts |
| POST | `/api/contracts/scan` | Scan PDF/DOCX — calls `lex.py` |
| POST | `/api/contracts/save` | Scan + persist to SQLite |
| POST | `/api/upload` | Upload spend CSV/Excel — runs full 5-stage pipeline |
| GET | `/api/signals?days=&category=` | Icarus signals from `icarus_memory.db` |
| POST | `/api/signals/scan` | Trigger Icarus RSS scan |
| GET | `/api/docs` | FastAPI auto-docs (Swagger UI) |

---

## Demo data

`_demo_dashboard(year)` in `api.py` returns realistic synthetic data when SQLite is empty. It is **year-aware** — 2022 vs 2026 returns different per-category spend from the same trend table. Year filter, YoY chart, and risk matrix all work without uploading real data.

---

## Routing & global patterns

- Navigation: `window.location.hash` — `#dashboard`, `#clm`, `#supplier`, etc.
- Each screen ends with `window.ScreenName = ScreenName` — `app.jsx` resolves these at render time
- Drawer: opened via `openDrawer` prop (preferred) or `window.__openDrawer(d)` (fallback)
- Charts/utils: exposed via `Object.assign(window, {...})` in `charts.jsx` — consumed by all screens as globals

## Drawer kinds

| `kind` | Required `data` fields | Opened from |
|--------|----------------------|-------------|
| `"contract"` | CLM result fields (riskScore, clauseFlags, etc.) | Dashboard expiry table, CLM history |
| `"supplier"` | Supplier object (tier, score, spend, po, contract) | Compliance screen |
| `"category"` | Category object + `trendData` + `trendYears` | Dashboard risk matrix, Deep Dive |
| `"signal"` | Icarus signal object (relevance, summary, action) | Icarus screen |

---

## Topbar buttons

| Button | Component | Behaviour |
|--------|-----------|-----------|
| ✦ Sparkles | `AIAssistant` in shell.jsx | Slide-in chat panel. Canned answers matched by keyword ("maverick", "cloud", "contract", "saving"). Quick-prompt chips. |
| 🔔 Bell | Inline in `TopBar` | Dropdown with 5 hardcoded alerts. Clicking navigates to screen. Per-item dismiss + "mark all read". |
| ⚙ Cog | `SettingsPanel` in shell.jsx | Dark mode toggle (real — sets `data-theme`), density selector (UI only), account info, app version |

---

## Known gaps / next steps

| Item | Priority | Notes |
|------|----------|-------|
| Strategy screen API | High | `generate()` returns hardcoded mock — wire to `POST /api/strategy` calling Claude |
| Live notifications | Medium | Hardcoded `NOTIFICATIONS[]` in shell.jsx — replace with `GET /api/alerts` querying overdue contracts + budget overruns |
| Real AI chat | Medium | `AIAssistant` uses keyword matching — replace with streaming `POST /api/chat` via Claude claude-sonnet-4-6 |
| Settings density | Low | Dropdown renders but doesn't change CSS — add `data-density` attribute to `<html>` and CSS rules |
| Risk colour deduplication | Low | `riskColor()`/`riskClass()` now in `charts.jsx` but inline objects still remain in `compliance.jsx`, `supplier.jsx`, `clm.jsx` |
| `window.Sidebar` exports | Noise | Shell components exported to `window` but never consumed as globals — safe to remove from `Object.assign` |
| Upload real data | Ready | "Upload Data" on Dashboard runs the full 5-stage pipeline server-side — just needs a real CSV |

---

## Environment

```bash
# Local dev
uvicorn api:app --reload --port 8000
# Then open http://localhost:8000

# Requires .env at project root:
ANTHROPIC_API_KEY=sk-ant-...
SPENDLENS_CLIENT=default   # optional, defaults to "default"
```

**Never commit:** `.env`, `*.db`, `vendor_cache.json`, `screenshots2/` — all in `.gitignore`

**Railway env vars** (set in Railway dashboard → Variables, never in git):
- `ANTHROPIC_API_KEY`
- `PORT` (set automatically by Railway)

---

## Design system reference

- **Font:** Geist + Geist Mono (Google Fonts CDN in `index.html`)
- **Colours:** oklch tokens — `--primary` (navy), `--good` (green), `--warn` (amber), `--bad` (red), `--info` (blue)
- **Dark mode:** `document.documentElement.setAttribute("data-theme", "dark")` — all tokens switch automatically
- **Layout:** CSS grid `"sb tb" / "sb main"` — 64px collapsed sidebar, 240px expanded on hover
- **Key classes:** `.card`, `.kpi`, `.chip`, `.tag`, `.btn`, `.btn.primary`, `.ai-card`, `.ai-insight`, `.tier-av.a/b/c`, `.drop-zone`, `.spin`, `.t` (table), `.row-link`, `.page-h`, `.col`, `.grid`

---

## Recent commits

```
8b3df78 fix: code quality pass — dead code, shadow var, unused props, shared utils
5e5fe5f fix: category drill-in drawer fully wired across Dashboard and Deep Dive
ac0580d feat: replace spend-vs-budget chart with YoY diverging bar chart
ef129e8 feat: replace bubble chart with CategoryRiskMatrix table
e224f4f feat: wire topbar buttons — AI assistant, notifications, settings
de9666a fix: SpendVsBudget bars scale absolutely across years
6dc122b fix: year filter updates KPIs, categories and highlights chart column
e072bee fix: risk bubble axes, category drawer, deep dive screen
e644435 fix(railway): explicit uvicorn start command via railway.toml
a71ddbe feat: migrate SpendLens to FastAPI + React frontend (Claude Design)
```
