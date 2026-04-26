# SpendLens — TODO

Priority: 🔴 High · 🟡 Medium · 🟢 Nice-to-have

---

## Icarus

| Pri | Task | Notes |
|-----|------|-------|
| 🔴 | **Wire feedback buttons to DB** | `icarusFeedback()` JS does visual toggle only. Need a Python bridge: either a Panel `TextInput` with Bokeh model name + `param.watch`, or a custom Bokeh server route. `icarus.record_feedback(sig_id, value)` is ready in `icarus.py`. |
| 🔴 | **Ask Icarus with query context** | Current `run(query)` ignores the query string — it always runs the full RSS scan. Should filter/re-rank signals based on query text, or do a targeted Claude call with the query as focus. |
| 🟡 | **Auto-submit on voice recognition** | After voice fills the TextInput, user still must click "Ask Icarus". Either dispatch a click on the Panel Button via Bokeh model JS (`model.clicks += 1`) or add a `param.watch` that triggers on value change after a debounce. |
| 🟡 | **Icarus refresh without full re-scan** | Add a "Load recent" button next to "Ask Icarus" to show cached signals without firing the API. |
| 🟢 | **Voice language toggle** | Currently hardcoded to `de-DE`. Add a small flag toggle (DE/EN) or auto-detect from browser locale. |
| 🟢 | **Signal deduplication** | Running Icarus multiple times stores duplicate headlines. Add dedup on `(headline, source)` before saving to DB. |

## Dashboard

| Pri | Task | Notes |
|-----|------|-------|
| 🔴 | **Dataset label shows "Default" correctly** | After file upload, label shows filename. Default dataset label reads empty. Fix: set `dataset_label.object = "**Dataset:** Default"` in initial render. |
| 🔴 | **Run startup with UTF-8 always** | Currently requires `PYTHONUTF8=1` env var. Add `# -*- coding: utf-8 -*-` or set `PYTHONIOENCODING=utf-8` in a `.env` / launch script so `panel serve app.py` works without flags. |
| 🟡 | **Drill-down from Risk Map bubble** | Clicking a bubble on the risk scatter chart should show the category's supplier list and contract detail in `drill_panel`. |
| 🟡 | **Deep Dive tab: supplier-level table** | Add a Tabulator below the charts showing individual vendor rows with flags for the selected year. |
| 🟡 | **Upload error UX** | Pipeline errors show in `status_log` as plain text. Add a red banner or modal for critical failures. |
| 🟢 | **Icarus Tab label** | Currently `"🪶 Icarus"`. Consider renaming to `"🪶 Market Intel"` to match the sidebar ICARUS section label. |
| 🟢 | **CFO Report download in-place** | Currently appends a download widget to `sidebar_col` after export. Replace with a proper download button that replaces itself after click. |

## Infrastructure

| Pri | Task | Notes |
|-----|------|-------|
| 🟡 | **Create a launch script** | `run.bat` or `run.sh` that activates `.venv` and starts panel with `PYTHONUTF8=1`. Removes manual setup friction. |
| 🟡 | **`watchfiles` install** | Panel prints a `FutureWarning` about `--autoreload` needing `watchfiles`. `pip install watchfiles` in `.venv` removes the warning. |
| 🟢 | **Multi-client support** | `database.py` supports `clients/{client_name}/` isolation. Add a client selector dropdown to the sidebar to switch between clients. |
