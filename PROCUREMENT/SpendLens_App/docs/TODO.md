# SpendLens — TODO
**Last updated:** 2026-05-27  
**Strategic context:** See `../ROADMAP.md` for the full platform roadmap. SpendLens is the analytics + data layer. TrueSpend (separate) is the reasoning + action layer.

Priority: 🔴 High · 🟡 Medium · 🟢 Nice-to-have · ⚫ Parked

---

## Phase 0 — Commit Backlog (Do First)

| Pri | Task | Notes |
|-----|------|-------|
| 🔴 | **Verify + commit `data_cleanup.py`** | ECB FX conversion — verify on test dataset before committing |
| 🔴 | **Commit `icarus.py`** | Grok integration, query filtering, Deep Scan mode |
| 🔴 | **Commit `icarus_ui.py`** | Feedback bridge wiring, XSS fix |
| 🔴 | **Commit `database.py`** | Schema updates for new tables |
| 🔴 | **Commit `modules/supplier_profiler.py`** | `previous_compliance_score` column + migration |
| 🟡 | **Create `run.bat`** | Activates `.venv`, sets `PYTHONUTF8=1`, starts `panel serve app.py` |

---

## Icarus

| Pri | Task | Notes |
|-----|------|-------|
| 🔴 | **Wire feedback buttons to DB** | `icarusFeedback()` JS does visual toggle only. Need Python bridge via Panel `param.watch`. `icarus.record_feedback(sig_id, value)` is ready. |
| 🔴 | **Ask Icarus with query context** | `run(query)` currently ignores query string — always runs full RSS scan. Should filter/re-rank based on query, or targeted Claude call with query as focus. |
| 🟡 | **Auto-submit on voice recognition** | After voice fills TextInput, dispatch click on Panel Button via Bokeh model JS or `param.watch` with debounce. |
| 🟡 | **Icarus refresh without full re-scan** | "Load recent" button to show cached signals without firing API. |
| 🟢 | **Voice language toggle** | Hardcoded to `de-DE`. Add flag toggle DE/EN or auto-detect from browser locale. |

---

## Dashboard

| Pri | Task | Notes |
|-----|------|-------|
| 🔴 | **Dataset label fix** | Default dataset label reads empty. Set `dataset_label.object = "**Dataset:** Default"` in initial render. |
| 🔴 | **UTF-8 launch** | Add `PYTHONIOENCODING=utf-8` to `.env` or launch script — remove manual `PYTHONUTF8=1` requirement. |
| 🟡 | **Risk Map drill-down** | Clicking a bubble should show category supplier list + contract detail. Treemap drill-down is live; Risk Map click not wired. |
| 🟡 | **Deep Dive: supplier-level table** | Tabulator below charts showing individual vendor rows with flags for selected year. |
| 🟡 | **Upload error UX** | Pipeline errors show as plain text in `status_log`. Add red banner or modal for critical failures. |
| 🟢 | **CFO Report download in-place** | Currently appends download widget to sidebar after export. Replace with proper button that replaces itself after click. |

---

## Infrastructure

| Pri | Task | Notes |
|-----|------|-------|
| 🟡 | **SpendLens REST API (FastAPI)** | ~1 day. Prerequisite for TrueSpend integration, n8n, and Jira agent. Thin layer over existing SQLite queries. |
| 🟡 | **`watchfiles` install** | `pip install watchfiles` removes Panel FutureWarning about `--autoreload`. |
| 🟢 | **Multi-client selector** | `database.py` supports `clients/{client_name}/` isolation. Add dropdown to sidebar. |

---

## Security (for first corporate deployment)

| Pri | Task | Effort | Notes |
|-----|------|--------|-------|
| 🟡 | **S1: HTTPS/TLS** | 0.5 day | nginx reverse proxy |
| 🟡 | **S3: SSO** | 1 day | Cloudflare Access / Azure AD / Google IAP |
| 🟢 | **S2: Encryption at rest** | 1 day | LUKS volume + SQLCipher |
| 🟢 | **S4: Secrets management** | 0.5 day | Keys out of `.env` into vault/systemd |
| 🟢 | **S5: RBAC** | 3 days | IdP groups → reader/editor/administrator |
| 🟢 | **S6: Audit logging** | 1 day | `audit_log` table in SQLite |
| 🟢 | **S7: Docker packaging** | 1 day | For IT handover |

Running cost with S1+S3: ~€6/month (Hetzner VPS + Cloudflare Access)

---

## Parked — Not a Priority

These were on the roadmap but are deprioritized given the new strategic direction. Do not invest time here without a specific reason.

| Item | Why parked |
|------|-----------|
| Commodity taxonomy maintenance | Agent categorizes from text; taxonomy is optional enrichment |
| SRM structured workflows | Replaced by AI-derived health signal in TrueSpend |
| Complex supplier scorecard | Simplified to green/watch/red signal |
| Category strategy frameworks (7 AI frameworks) | Useful analysis tool, not core product |
| Telegram / Slack mobile bot | Still valuable, but Phase 2 after TrueSpend core is built |

---

## Things That Must Not Break

- `sc_edit_bridge` named model — JS reads by name via `Bokeh.documents[0].get_model_by_name('sc_edit_bridge')`. Do not rename.
- `_SC_CSS_JS` — plain Python string, not f-string. All `{` and `}` inside are literal CSS/JS.
- `previous_compliance_score` migration — the `try/except ALTER TABLE` in `init_supplier_profiles()` must stay.
- `PYTHONUTF8=1` — required on Windows when starting server until UTF-8 launch fix is done.
- `--autoreload` only watches `app.py` — always restart after changing any imported module.
