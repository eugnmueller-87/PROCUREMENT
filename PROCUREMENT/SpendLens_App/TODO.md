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

---

## Enterprise Security & Deployment

> Required before deploying SpendLens to a corporate environment with real company spend data.

### Cost & Scale Summary

**Target team size: 1–5 users** (current architecture supports this without any scaling changes)

| Component | Recommended option | Monthly cost |
|---|---|---|
| Server | Hetzner VPS CX21 (2 vCPU / 4 GB) | €6/mo |
| TLS certificate | Let's Encrypt via certbot | Free |
| SSO proxy | Cloudflare Access (free ≤ 50 users, connects to Azure AD / Google / Okta) | Free |
| Secrets management | systemd EnvironmentFile (root-owned, chmod 600) | Free |
| Encryption at rest | LUKS disk encryption + SQLCipher | Free |
| Audit logging | SQLite `audit_log` table (built-in) | Free |
| **Total / month (1–5 users)** | | **~€6/mo** |

**Alternative: Azure App Service + Azure AD App Proxy** — €13–43/mo depending on whether Entra P1 licences are needed. Preferred if the company is Azure-native.

**One-off build cost (S1–S7, ~8 days total):**

| Scenario | Cost |
|---|---|
| Built in this project (in-house) | €0 cash, ~8 days time |
| Freelance developer (€100/hr) | ~€6,400 |
| Agency (€150/hr) | ~€9,600 |

**Scale limits with current architecture:**

| Team size | Status | Action needed |
|---|---|---|
| 1–5 users | ✅ Comfortable — no changes needed | None |
| 6–15 users | ⚠️ Concurrent AI calls may queue | Add `--num-procs 2` to Panel serve |
| 16–30 users | ⚠️ Scaling work required | Multi-worker + task queue (Celery + Redis) |
| 30+ users | ❌ Architecture rethink | Out of scope for this phase |

---

### S1. HTTPS / TLS — Reverse Proxy ✦ Free
**Priority:** Critical — baseline for any corporate deployment  
**What it adds:** All browser↔server traffic encrypted. Protects API keys, spend data, and session tokens in transit.  
**How:**
- Deploy nginx (or Caddy) as a reverse proxy in front of `panel serve`
- TLS cert via Let's Encrypt (`certbot`) or company-issued certificate
- Add HSTS and `X-Frame-Options: DENY` headers in nginx config
- Panel app binds to `localhost:5006` only; nginx is the public face

**nginx config sketch:**
```nginx
server {
    listen 443 ssl;
    ssl_certificate     /etc/letsencrypt/live/spendlens.company.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/spendlens.company.com/privkey.pem;
    location / { proxy_pass http://localhost:5006; }
}
```
**Effort:** ~0.5 day (server config, no code changes)

---

### S2. Data Encryption at Rest ✦ Free
**Priority:** High — protects `.db` files if server is compromised or disk is imaged  
**Two layers (both recommended for corporate use):**

**Layer 1 — Volume-level (zero code changes):**  
Deploy on a server with full-disk encryption: Linux LUKS, AWS EBS encryption, or Azure Disk Encryption. IT/cloud team manages the key. No SpendLens changes needed.

**Layer 2 — SQLCipher (database-level):**  
Encrypts `spendlens.db` and `icarus_memory.db` with a passphrase. Files are unreadable without the key even if copied off the server.  
**Where it hooks:** `modules/database.py` — swap `import sqlite3` for `from pysqlcipher3 import dbapi2 as sqlite3`; pass `PRAGMA key='<passphrase>'` on connection open.  
**Dependency:** `pip install pysqlcipher3` (requires libsqlcipher on the host OS)  
**Effort:** ~1 day (swap, test, key rotation procedure)

---

### S3. SSO — Identity-Aware Proxy (Recommended path) ✦ Free–Low cost
**Priority:** High — required for corporate deployment; removes password management from SpendLens entirely  
**What it adds:** Users log in via the company IdP (Azure AD, Okta, Google Workspace). SpendLens never sees passwords or tokens — the proxy handles auth and passes a verified email header.  

**Recommended stack:**
| IdP | Proxy layer | Cost |
|---|---|---|
| Azure Active Directory / Entra | Azure AD App Proxy or Cloudflare Access | Free–$3/user/month |
| Okta | Cloudflare Access or Okta Access Gateway | Free tier available |
| Google Workspace | Google Identity-Aware Proxy (Cloud IAP) | Free |

**How it works:**
1. DNS for `spendlens.company.com` points to Cloudflare / Azure proxy
2. Proxy checks session → redirects to IdP login if not authenticated
3. On success, proxy forwards request to SpendLens with header `CF-Access-Authenticated-User-Email: user@company.com`
4. SpendLens reads that header to identify the user and look up their role in the `users` table

**Code change in `app.py`:**
```python
# Read verified identity from proxy header (set by Cloudflare Access / Azure AD App Proxy)
user_email = pn.state.headers.get("cf-access-authenticated-user-email") \
          or pn.state.headers.get("x-ms-client-principal-name")
```
**Effort:** ~1 day (proxy config) + ~1 day (header reading + role lookup in SpendLens)  
**Depends on:** S1 (HTTPS), S5 (RBAC with SSO group mapping)

---

### S4. Secrets Management ✦ Free
**Priority:** Medium — removes API keys from `.env` files on the server  
**What it adds:** `ANTHROPIC_API_KEY`, `XAI_API_KEY`, and any future keys stored in a secrets manager, not a plaintext file.  

**Options by hosting environment:**
| Environment | Secrets manager |
|---|---|
| Azure | Azure Key Vault |
| AWS | AWS Secrets Manager |
| Self-hosted | HashiCorp Vault (free OSS) or environment variables injected by systemd |
| Simple self-hosted | `systemd` `EnvironmentFile` pointing to a root-owned, chmod 600 file |

**Minimal approach (self-hosted):** Move `.env` to `/etc/spendlens/secrets.env`, owned by `root`, readable only by the `spendlens` service user via systemd `EnvironmentFile=`. Remove `.env` from the app directory entirely.  
**Effort:** ~0.5 day (systemd unit + key migration)

---

### S5. Role-Based Access Control + SSO Group Mapping ✦ No external API
**Priority:** High — extends existing RBAC plan (item #5 above) to work with SSO  
**What it adds:** Maps company IdP groups to SpendLens roles so admins manage access in the IdP (Azure AD groups, Okta groups), not inside SpendLens.

**Group → role mapping:**
```
IdP group "SpendLens-Administrators"  →  administrator
IdP group "SpendLens-Editors"         →  editor
(any authenticated company user)       →  reader (default)
```

**Architecture:**
```
modules/auth.py
  ├── resolve_role(email, groups) — maps IdP claims to reader/editor/administrator
  ├── create_users_table()        — users table (email, role, last_login; no password_hash needed with SSO)
  ├── get_or_create_user()        — auto-provision on first login via SSO header
  └── verify_local_password()     — fallback for local admin account (break-glass)
```

**Effort:** ~3 days (auth module + login UI + role gating + group mapping + admin tab)  
**Depends on:** S3 (SSO proxy)

---

### S6. Audit Logging ✦ No external API
**Priority:** Medium — required for regulated industries; good practice for any corporate deployment  
**What it logs:** Every write action — uploads, supplier edits, role changes, data exports, Icarus RFP generation  
**Where:** New `audit_log` table in `spendlens.db`

```sql
CREATE TABLE audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,          -- ISO 8601 UTC
    user_email TEXT NOT NULL,
    action     TEXT NOT NULL,          -- e.g. "upload", "supplier_edit", "export_cfo"
    detail     TEXT,                   -- JSON: {vendor, field, old_value, new_value}
    ip_address TEXT
);
```

**Where it hooks:** Thin `log_action(action, detail)` helper called from upload pipeline, `_on_sc_edit`, CFO export, and user management.  
**Effort:** ~1 day

---

### S7. Deployment Packaging ✦ No external API
**Priority:** Low — quality of life for IT handover  
**What it adds:** A `Dockerfile` + `docker-compose.yml` so IT can spin up SpendLens in a container with a single command; volume mounts for `clients/` (persistent data) and secrets.  
**Effort:** ~1 day

---

---

## Commercial Roadmap

> SpendLens sits between €50,000+/year enterprise tools (SAP Ariba, Coupa) and spreadsheets. Target market: mid-size companies (100–2,000 employees) with a procurement team of 2–10 people spending €10M–500M/year. Pricing target: €2,000–15,000/year per client.

---

### Phase 0 — Internal Prototype ✅ Now
**Status:** Complete as a single-user local tool  
**Users:** 1  
**Running cost:** €0/month  
**Revenue:** €0  
**What exists:** Full upload pipeline, dashboard, Icarus, Category Strategy, Compliance Scorecard

---

### Phase 1 — First Paying Client · Target: Q3 2026
**Goal:** Deploy securely for one real company, 1–5 users, signed contract  
**Build:** Enterprise Security layer S1–S7 (see above, ~8 days)  
**Running cost:** ~€6–43/month (Hetzner VPS or Azure App Service)

**Suggested pricing for first client:**
| Tier | Users | Price | ARR |
|---|---|---|---|
| Pilot | 1–3 | €299/mo | €3,588 |
| Starter | 5 | €599/mo | €7,188 |

> First client is often a reduced "pilot price" in exchange for a reference / case study. Aim for €299–599/month. €7,200/year ARR from one client pays for ~18 months of hosting.

**Key milestones:**
- [ ] Security layer live (S1–S7)
- [ ] One signed pilot contract
- [ ] Data Processing Agreement (DPA) template signed (GDPR requirement)
- [ ] Client onboarded manually (you set up their instance)

---

### Phase 2 — Multi-Tenant Pilot SaaS · Target: Q4 2026 – Q1 2027
**Goal:** 3–5 paying clients, per-client data isolation, subscription billing, self-service onboarding  
**Running cost:** €50–120/month (containerised per-tenant SQLite or shared PostgreSQL)  
**Revenue target:** 5 clients × €599/mo = **€3,000/mo (~€36,000 ARR)**

**Build items:**

| Item | What | Effort |
|---|---|---|
| Multi-tenancy | Per-client Docker containers or per-tenant DB namespacing; client selector in sidebar | ~3 days |
| Stripe / Paddle billing | Subscription checkout, webhook → provision new client DB on payment | ~2 days |
| Demo environment | Synthetic spend dataset, pre-loaded Icarus signals, no login required | ~1 day |
| Landing page | Product website with pricing page, feature list, and "Request demo" CTA | ~2 days |
| GDPR compliance | Cookie consent banner, DPA template, privacy policy, right-to-deletion endpoint | ~2 days |
| Client management UI | Admin view: active clients, usage stats, billing status | ~2 days |

**Total Phase 2 build:** ~12 days  
**Pricing tiers:**

| Tier | Users | Monthly | Annual (−15%) |
|---|---|---|---|
| Starter | 1–3 | €299 | €3,048 |
| Professional | 5 | €599 | €6,108 |
| Team | 10 | €999 | €10,188 |

---

### Phase 3 — Commercial SaaS · Target: Q2–Q3 2027
**Goal:** 10–20 clients, self-service signup, SOC 2 Type I readiness, first marketing motion  
**Running cost:** €200–600/month (load-balanced containers, monitoring, backups)  
**Revenue target:** 15 clients × avg €799/mo = **€12,000/mo (~€144,000 ARR)**

**Build items:**

| Item | What | Effort |
|---|---|---|
| Self-service signup | Email signup → Stripe checkout → auto-provisioned instance, onboarding email | ~3 days |
| SOC 2 Type I readiness | Audit log completeness, access controls, incident response runbook, vendor risk register | ~5 days + external auditor |
| CI/CD pipeline | GitHub Actions: test → lint → Docker build → deploy on merge to main | ~2 days |
| Monitoring & alerting | Sentry (error tracking) + Grafana / Datadog Lite (uptime, latency, API cost per client) | ~2 days |
| Trial flow | 14-day free trial with synthetic data; converts to paid on Stripe checkout | ~1 day |
| G2 / Capterra listing | Public review profile, collect pilot client testimonials | ~0.5 day |

**Total Phase 3 build:** ~13 days + auditor cost (~€5,000–15,000 for SOC 2 Type I)

**Estimated SOC 2 cost:** €5,000–15,000 (one-off audit) + ~€2,000/year renewal. Required by most enterprise procurement departments before they allow third-party tools to handle spend data.

---

### Phase 4 — Enterprise SaaS · Target: 2028+
**Goal:** 30+ clients, ERP integrations, white-label option, enterprise contracts  
**Revenue target:** Mix of 25 Professional clients (€999/mo) + 5 Enterprise (€5,000–15,000/mo custom) = **~€55,000–90,000/mo ARR**

**Build items:**

| Item | What | Notes |
|---|---|---|
| SAP / Oracle / Coupa connector | Pull transaction data via ERP API instead of CSV upload | Removes the biggest adoption friction |
| ISO 27001 certification | Full ISMS — required by large corporates and public sector | ~€15,000–30,000 audit + 6 months work |
| White-label theming | Client logo, custom domain, custom color scheme | ~3 days per-client config |
| Dedicated instances | Per-enterprise isolated deployment (VPC, dedicated DB, dedicated Icarus) | Infra automation via Terraform |
| SLA (99.9% uptime) | Contractual uptime guarantee + incident response SLA | Requires redundant infra (multi-AZ) |
| Channel partners | Reseller agreements with procurement consultancies (e.g. Efficio, Proxima) | Business development, not engineering |
| Spend Forecast module | Q+1 linear extrapolation + AI scenario modelling | ~3 days |
| Supplier Risk Score | Composite score: compliance + financial health + single-source + Icarus signals | ~2 days |

---

### Commercial Summary

| Phase | Timeline | Clients | Monthly Revenue | Cumulative Build |
|---|---|---|---|---|
| 0 — Prototype | Now | 0 | €0 | Done |
| 1 — First client | Q3 2026 | 1 | €299–599 | +8 days |
| 2 — Pilot SaaS | Q4 2026–Q1 2027 | 3–5 | €900–3,000 | +12 days |
| 3 — Commercial SaaS | Q2–Q3 2027 | 10–20 | €8,000–16,000 | +13 days + SOC 2 |
| 4 — Enterprise | 2028+ | 30+ | €55,000–90,000 | +ERP + ISO 27001 |

**The path from Phase 0 to Phase 1 is ~8 days of build.** Everything after that is incremental on a working, revenue-generating product.

---

## Other Open Items

### In Progress
- [ ] Icarus feedback learning loop — wire `record_feedback()` through Bokeh bridge (partially done, needs testing)
- [ ] Icarus tab wired into `app.py` tab set (done — index 3)

### Backlog
- [ ] Create separate Git branches for each agent (Icarus, Category Strategy, Supplier Profiler, future agents) to enable isolated development and clean PRs per agent
- [ ] QBR (Quarterly Business Review) deck — per Tier A supplier; HTML deck with performance review, pricing context, risk, strategic agenda, action items. Triggered from Compliance Scorecard supplier card. *(Design complete, build deferred)*
- [ ] Scheduled Icarus background scans (`pn.state.schedule_task` or external cron)
- [ ] Document upload summarisation — Haiku pre-summary to reduce context cost ~90%
- [ ] Spend Variance Analysis tab
- [ ] Supplier Risk Score (composite: compliance + financial health + single-source)
- [ ] Spend Forecast (Q+1) — simple linear extrapolation from historical data
- [ ] Multi-client support (client selector in sidebar)
- [ ] NewsAPI.org integration for broader Icarus signal coverage
- [ ] Slack / Teams webhook for proactive procurement alerts
