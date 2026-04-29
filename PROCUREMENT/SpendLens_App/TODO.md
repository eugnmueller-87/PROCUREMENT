# SpendLens — TODO & API Integration Roadmap

## API Integrations (next build phase)

### 1. ECB FX Rates ✦ Free
**Priority:** High — affects every upload with non-EUR spend  
**API:** `https://data-api.ecb.europa.eu/service/data/EXR/`  
**What it adds:** Auto-detect currency column on upload; convert all spend to EUR using daily ECB rates before inserting into `transactions_raw`. Eliminates manual normalization for multi-currency datasets.  
**Where it hooks:** `modules/data_cleanup.py` — after spend normalization, before DB insert.  
**Effort:** ~1 day

---

### 2. OpenCorporates ✦ Free tier (paid for bulk)
**Priority:** High — enriches every supplier card with no cost  
**API:** `https://api.opencorporates.com/v0.4/companies/search?q=<vendor_name>`  
**What it adds:** For each new vendor, fetch legal name, jurisdiction, incorporation date, company status (active / dissolved). Surface in Compliance Scorecard expanded card. Flag dissolved companies as high risk.  
**Where it hooks:** `modules/category_mapper.py` batch loop — piggyback on the existing per-vendor Claude call, cache result in `vendor_cache.json` alongside category.  
**Effort:** ~1 day

---

### 3. Quandl / Nasdaq Data Link ✦ Free tier available
**Priority:** High — directly supports core value prop ("is this price increase justified?")  
**API:** `https://data.nasdaq.com/api/v3/datasets/<code>.json?api_key=<KEY>`  
**Key datasets:**
- `CHRIS/CME_CL1` — Crude Oil futures
- `CHRIS/CME_NG1` — Natural Gas
- `LME/PR_AL` — Aluminium
- `CHRIS/CME_GC1` — Gold
- `BCHAIN/CPTRV` — Cloud/compute proxy

**What it adds:** Icarus market signals include a price-trend fact card when a supplier's category maps to a tracked commodity. E.g. AWS price increase → show YoY energy cost index. Visible in supplier expanded card and Icarus query answers.  
**Where it hooks:** `icarus.py` — new `fetch_commodity_context(category)` function called before `query_with_claude()`.  
**Effort:** ~2 days

---

### 4. Creditsafe or D&B (Dun & Bradstreet) ✦ Paid API
**Priority:** Medium — enterprise differentiator, requires account  
**APIs:**
- Creditsafe: `https://connect.creditsafe.com/v1/companies?name=<vendor>&countries=DE`
- D&B Direct+: `https://plus.dnb.com/v1/data/duns`

**What it adds:** Financial health score (0–100), credit limit, insolvency risk flag, payment behaviour index per supplier. Feeds into Compliance Scorecard risk column and ABC tier logic (financial instability can force tier upgrade to A for contingency planning).  
**Where it hooks:** `modules/supplier_profiler.py` — `compute_and_save_profiles()` enrichment step. Cache result in `supplier_profiles.financial_health_score` (new column).  
**Effort:** ~3 days (API account setup + integration + UI)

---

---

### 5. User Profiles & Role-Based Access Control ✦ No external API required
**Priority:** High — required before any multi-user or client deployment  
**What it adds:** A login screen, a `users` table in SQLite, and role-gated UI so different people get different access.

**Three roles:**

| Role | Permissions |
|---|---|
| **Reader** | View all dashboard tabs, run Icarus scans, export CFO Excel report |
| **Editor** | Reader + upload data files, edit supplier fields (category / tier / relationship), submit Icarus feedback, use Ask Icarus / RFP brief |
| **Administrator** | Editor + manage users (invite, deactivate, change roles), view audit log, reset client data |

**Architecture:**

```
modules/auth.py
  ├── create_users_table(conn)       — SQLite users table (username, email, password_hash, role, active, last_login)
  ├── create_user(...)               — bcrypt-hashed password, role assignment
  ├── verify_password(...)           — login check
  ├── get_user(conn, username)       — return user dict
  └── list_users(conn)               — admin user list

app.py (login gate)
  ├── _login_pane                    — Panel Card shown before dashboard if no session
  ├── pn.state.user / pn.state.cookies — session token storage
  └── role_check(min_role)           — decorator/guard that hides widgets for insufficient role
```

**Role enforcement points:**
- Upload button → Editor+
- Icarus feedback / Ask / RFP → Editor+
- Inline supplier editing (category, tier, relationship) → Editor+
- CFO export → Reader+
- User management tab → Administrator only
- All view/read operations → Reader+

**Database table:**
```sql
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    email         TEXT,
    password_hash TEXT NOT NULL,   -- bcrypt
    role          TEXT NOT NULL CHECK(role IN ('reader','editor','administrator')),
    created_at    TEXT NOT NULL,
    last_login    TEXT,
    active        INTEGER DEFAULT 1
);
```

**Where it hooks:**  
- New `modules/auth.py` — all auth logic  
- `app.py` — login pane before main layout, `pn.state.user` set on success, role checks on widgets  
- `modules/database.py` — `create_users_table()` called in `init_database()`  

**Effort:** ~3 days (auth module + login UI + role gating + admin user management tab)

---

---

### 6. Category Strategy Tab ✦ Built-in (no external API)
**Priority:** High — core category manager workflow  
**What it adds:** A dedicated tab (next to Icarus) where category managers prepare and export their category strategy. AI pre-populates all frameworks from spend data + Icarus signals; category manager reviews and edits; exports a standalone HTML slide deck with SpendLens logo.

**Frameworks generated per category:**
1. **Kraljic Matrix** — supply risk × profit impact positioning with recommended posture
2. **PESTEL** — 6-dimension market environment analysis seeded from Icarus signals
3. **SWOT** — buyer-perspective analysis from spend + market data
4. **Porter's Five Forces** — market power assessment
5. **TCO Breakdown** — true cost beyond invoice price
6. **Negotiation Levers** — prioritised levers with saving potential + effort rating
7. **Strategy Recommendation** — 3-year roadmap with Year 1/2/3 priorities and KPIs

**Output:** HTML slide deck (standalone, opens in browser) — SpendLens logo top-right every slide, navy/green color scheme. Used by category managers to execute strategy and present to stakeholders.

**Where it hooks:**
- New `modules/category_strategy.py` — Claude Haiku API calls, SQLite persistence (`category_strategies` table in `spendlens.db`)
- New `modules/deck_generator.py` — self-contained HTML slide deck generator
- New `category_strategy_ui.py` — Panel component (same pattern as `icarus_ui.py`)
- `app.py` — new tab at index 4

**Effort:** ~1 day  
**Status:** ✅ Built

---

## Other Open Items

### In Progress
- [ ] Icarus feedback learning loop — wire `record_feedback()` through Bokeh bridge (partially done, needs testing)
- [ ] Icarus tab wired into `app.py` tab set (done — index 3)

### Backlog
- [ ] QBR (Quarterly Business Review) deck — per Tier A supplier; HTML deck with performance review, pricing context, risk, strategic agenda, action items. Triggered from Compliance Scorecard supplier card. *(Design complete, build deferred)*
- [ ] Scheduled Icarus background scans (`pn.state.schedule_task` or external cron)
- [ ] Document upload summarisation — Haiku pre-summary to reduce context cost ~90%
- [ ] Spend Variance Analysis tab
- [ ] Supplier Risk Score (composite: compliance + financial health + single-source)
- [ ] Spend Forecast (Q+1) — simple linear extrapolation from historical data
- [ ] Multi-client support (client selector in sidebar)
- [ ] NewsAPI.org integration for broader Icarus signal coverage
- [ ] Slack / Teams webhook for proactive procurement alerts
