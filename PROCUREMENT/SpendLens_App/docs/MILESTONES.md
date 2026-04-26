# SpendLens — Session Milestones

## Session 2026-04-26

### Completed

| # | What | Files |
|---|------|-------|
| 1 | Created `CLAUDE.md` — guidance file for future agents | `CLAUDE.md` |
| 2 | Removed AI Settings input widget from sidebar (was cosmetic, key comes from `.env`) | `app.py` |
| 3 | Added **🪶 Run Icarus Scan** button to sidebar under new ICARUS section | `app.py` |
| 4 | Fixed syntax error — stray `)` after `IcarusPanel(...)` instantiation | `app.py` |
| 5 | Wired Icarus sidebar button to `icarus_panel.run()` with status log feedback | `app.py` |
| 6 | Fixed server startup Unicode crash on Windows (cp1252 terminal encoding) — solved by `PYTHONUTF8=1` env flag | run command |
| 7 | **Icarus UI refactor**: split monolithic HTML pane into `_header_pane` + Panel-native input row + `_cards_pane` | `icarus_ui.py` |
| 8 | **Signal headlines are now clickable links** — open article in new tab directly from the card header; `onclick="event.stopPropagation()"` keeps expand/collapse working | `icarus_ui.py` |
| 9 | **Ask Icarus input now wired to Python** — replaced broken `fetch('/icarus/ask')` with Panel-native `TextInput` + `Button.on_click` → `icarus_panel.run(query)` | `icarus_ui.py` |
| 10 | **Voice input** — mic button uses Web Speech API (Chrome); on recognition fills the Panel TextInput via DOM event dispatch | `icarus_ui.py` |

### Architecture decisions made

- **Panel-native widgets for interactivity**: HTML panes are rendering-only; all Python callbacks go through Panel widgets (`Button.on_click`, `TextInput`). The previous `fetch('/icarus/ask')` approach assumed custom server routes that Panel doesn't provide by default.
- **Split HTML panes**: `_header_pane` (header + cat tabs) and `_cards_pane` (loading + cards) update independently. JavaScript in the cards pane (`toggleCard`, `filterCat`) operates on the full DOM — elements from both panes are accessible since Panel doesn't use iframes.
- **Feedback buttons**: currently visual-only (CSS toggle works, no DB write). Saving feedback to SQLite requires either a Panel server route or a Bokeh model bridge — left as next session work (see TODO).
- **Voice language**: set to `de-DE` (German) matching user locale. Change `_ivRec.lang` in `icarus_ui.py` → `_VOICE_HTML` to adjust.
