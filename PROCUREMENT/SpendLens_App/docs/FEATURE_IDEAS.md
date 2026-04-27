# SpendLens — Feature Ideas Log

> Generated: 2026-04-26  
> Source: automated project audit (bugs + performance scan)  
> Status legend: 💡 Idea · 🔨 In progress · ✅ Done

---

## Tier 1 — High value, low effort (1–2 days)

### 1. Compliance Scorecard tab 💡
**What:** Single CFO-ready view showing org-wide procurement health:
% spend with PO · % under contract · maverick % · shadow IT % · catalogue adherence.
Each metric as a gauge/KPI card with trend vs prior period.  
**Extends:** `modules/flag_engine.py` aggregations → new section in `app.py`  
**Why:** Most-asked question in a procurement audit; currently requires manual pivot table.

---

### 2. Vendor Concentration Alerts 💡
**What:** Flag any category where top 3 vendors exceed 80% of spend.
Banner on Deep Dive tab; exportable to CFO report.  
**Extends:** `modules/database.py` query + `app.py` alert banner  
**Why:** Single-source dependency = supply chain risk; simple to compute from existing data.

---

### 3. Category Spend Timeline 💡
**What:** Monthly bar chart per category showing spend trend + maverick overlay (red bars for non-compliant months).
Clickable from the main dashboard category cards.  
**Extends:** `app.py` chart section — reuses `transactions_enriched` already in DB  
**Why:** Trend spotting and seasonality analysis currently require Excel; one day of work.

---

### 4. Freelancer / Contractor Management View 💡
**What:** Dedicated tab filtering all `freelancer_flag = True` rows:
vendor name, total spend YTD, contract Y/N, PO Y/N, number of invoices, cost centre.  
**Extends:** `modules/database.py` filtered query + new tab in `app.py`  
**Why:** Freelancer spend is the #1 uncontrolled cost in mid-market companies; currently invisible.

---

## Tier 2 — High value, medium effort (3–5 days)

### 5. Icarus Feedback Learning Loop 🔨
**What:** The `record_feedback()` function already updates `category_weights` in the DB.
Missing piece: feed those weights into the weekly brief prompt and `analyze_with_claude` relevance filter so Icarus learns which categories the user cares about over time.  
**Extends:** `icarus.py` — `weekly_summary()` + `analyze_with_claude()` prompt construction  
**Why:** Currently feedback is stored but never used; closing the loop makes Icarus meaningfully smarter.  
**Note (2026-04-26):** Icarus signals now surface inline in the Deep Dive supplier card via a fast RSS-only fetch panel. Feedback wiring still open.

---

### 6. Spend Variance Analysis 💡
**What:** For each vendor, compare spend this period vs same period last year.
Table view: vendor · category · last year · this year · Δ% · flag if >15% increase.
Exportable to CFO Excel.  
**Extends:** `modules/database.py` time-windowed query + `modules/cfo_reports.py`  
**Why:** "Why did this vendor's cost go up?" is the most common CFO question after month-end close.

---

### 7. Supplier Risk Score 💡
**What:** Per-vendor composite score combining:
concentration % of category spend · contract coverage (Y/N) · PO coverage · single-source flag · invoice regularity.
Shown as a risk bubble on the existing Risk Map chart.  
**Extends:** `modules/flag_engine.py` + `app.py` Risk Map scatter chart  
**Why:** Risk Map currently uses manually computed axes; a real risk score drives procurement strategy.

---

### 8. Spend Forecast (Q+1) 💡
**What:** For categories with ≥3 months of data, project next quarter using
exponential smoothing (simple, no external deps). Show as dashed line on spend timeline.  
**Extends:** New `modules/spend_forecaster.py` + `app.py` timeline chart  
**Why:** Budgeting teams need spend projections by Q3; currently done in Excel by finance.

---

## Tier 3 — Strategic features (5+ days)

### 9. Contract Terms Extraction & Comparison 💡
**What:** Upload a contract PDF via the Icarus 📎 button.
Claude extracts: renewal date · payment terms · discount % · SLA · liability cap.
Side-by-side comparison table across vendors in same category.  
**Extends:** `icarus.extract_text()` → new `modules/contract_extractor.py` → `icarus_ui.py` result view  
**Why:** Benchmarking contract terms across vendors is a core procurement lever; currently manual.

---

### 10. Automated RFQ Generator 💡
**What:** "Rebid this category" button generates a full RFQ draft:
scope of work template · current vendor list · Icarus market benchmark · pricing guidance from signals.  
**Extends:** `icarus.py` new `generate_rfq_brief()` function; integrates into `icarus_ui.py`  
**Why:** RFQ boilerplate takes 20% of a category manager's time; Icarus context makes it instant.

---

### 11. Real Estate Portfolio Dashboard 💡
**What:** Dedicated tab for `Real Estate` category:
rent per sqm by city · lease expiry heat map · entity breakdown · renewal risk timeline.  
**Extends:** New `modules/real_estate_analytics.py` + `app.py` tab  
**Why:** Lease renewals are high-value, time-sensitive decisions; currently no visibility without manual tracking.

---

### 12. Procurement ROI / Savings Tracker 💡
**What:** User tags a rebid or renegotiation initiative (e.g. "AWS renegotiation Q2").
System tracks: baseline spend · new contract value · realised savings · payback period.
Dashboard shows cumulative savings vs target.  
**Extends:** New `modules/savings_tracker.py`; links to `transactions_enriched` via initiative tag  
**Why:** CPO accountability and board reporting; the single metric that justifies a procurement team's budget.

---

## Bug backlog (from same audit)

| Pri | File | Issue |
|-----|------|-------|
| 🔴 | `modules/flag_engine.py:213` | `.get()` called on pandas Series — `AttributeError` on every upload |
| 🔴 | `icarus.py:430` | `analyze_with_claude` uses bare `json.loads()` instead of `_parse_json()` — crashes on malformed Claude response |
| 🔴 | `app.py:571` | `== True` on pandas Series — maverick count always 0 when column missing |
| 🟡 | `icarus_ui.py:834` | Filename injected raw into HTML — XSS if filename contains `<script>` |
| 🟡 | `modules/flag_engine.py:280` | `float(spend)` can crash on non-numeric strings |
| 🟡 | `modules/category_mapper.py:105` | Silent truncation at 150 vendors — no warning to user |
| 🟡 | `icarus.py:305` | `extract_text()` loads entire file with no size limit — DoS risk |
| 🟢 | `icarus_ui.py:707` | Feedback ID looked up by headline — wrong signal updated if two headlines match |
