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

## Other Open Items

### In Progress
- [ ] Icarus feedback learning loop — wire `record_feedback()` through Bokeh bridge (partially done, needs testing)
- [ ] Icarus tab wired into `app.py` tab set (done — index 3)

### Backlog
- [ ] Scheduled Icarus background scans (`pn.state.schedule_task` or external cron)
- [ ] Document upload summarisation — Haiku pre-summary to reduce context cost ~90%
- [ ] Spend Variance Analysis tab
- [ ] Supplier Risk Score (composite: compliance + financial health + single-source)
- [ ] Spend Forecast (Q+1) — simple linear extrapolation from historical data
- [ ] Multi-client support (client selector in sidebar)
- [ ] NewsAPI.org integration for broader Icarus signal coverage
- [ ] Slack / Teams webhook for proactive procurement alerts
