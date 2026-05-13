# Procurement AI Approval Workflow — n8n

Automates procurement request triage using AI. A purchase request is submitted via webhook, analyzed by Claude AI, parsed, routed by risk level, and processed accordingly.

## Workflow Overview

```
Webhook → Message a Model (Claude) → Code in Python → Switch → Edit Fields → IF → HTTP Request / Wait → Respond to Webhook
```

![Workflow Screenshot](Screenshot/Screenshot%202026-05-13%20110314.png)

---

## Node Reference

| # | Node | What It Does | Key Notes |
|---|------|--------------|-----------|
| 1 | **Webhook** | Receives incoming HTTP POST and passes body into the workflow | Body fields accessible via `$json.body.fieldname` |
| 2 | **Message a Model (Claude)** | Sends prompt to Claude AI, returns risk assessment | Raw output is `content[0].text` — a JSON string wrapped in markdown backticks |
| 3 | **Code in Python** | Strips markdown backticks, parses AI response into clean JSON | Outputs `risk_level`, `risk_reason`, `suggested_action`, `summary` |
| 4 | **Switch** | Routes to LOW / MEDIUM / HIGH branch based on `risk_level` | No data transformation — routing only |
| 5 | **Edit Fields (Set)** | Sets `approval_status` and `message` for auto-approved items | Drops other fields unless "Include Other Input Fields" is ON |
| 6 | **IF** | Routes to true/false branch based on `approval_status` | Boolean split — no transformation |
| 7 | **HTTP Request** | External API call (e.g. exchange rate check, vendor lookup) | Returns API response as JSON |
| 8 | **Wait** | Pauses workflow for a defined interval | Useful for approval timeouts |
| 9 | **Respond to Webhook** | Sends HTTP 200 response back to the caller | Closes the webhook request loop |
| 10 | **Manual Trigger** | Starts workflow manually for testing | Entry point with empty item `{}` |

---

## Data Flow Example

**Input (Webhook POST):**
```json
{
  "requester": "Anna Schmidt",
  "vendor": "Adobe Inc",
  "amount": 4500,
  "category": "Software",
  "description": "Creative Cloud licenses for design team"
}
```

**After Claude (raw):** `content[0].text` contains a JSON string wrapped in markdown backticks.

**After Code in Python (parsed):**
```json
{
  "risk_level": "LOW",
  "risk_reason": "Routine software license purchase from established vendor.",
  "suggested_action": "auto-approve",
  "summary": "Anna Schmidt requests $4,500 for Adobe Creative Cloud licenses."
}
```

**After Edit Fields:**
```json
{
  "approval_status": "auto-approved",
  "message": "Low risk - auto approved by system"
}
```

---

## Key Concepts

- **Expression syntax:** `{{ $json.fieldname }}` to reference data from the previous node
- **Multiple outputs:** Switch (0/1/2 branches), IF (true/false branches)
- **Data persistence:** Fields are only preserved if explicitly passed through or "Include Other Input Fields" is enabled on Set nodes
- **Picking nodes:** Follow the data flow — trigger → transform → route → act. Use Code node for custom logic, Edit Fields for simple mapping, Message a Model for AI judgment calls

---

## Debugging

| Issue | Cause | Fix |
|-------|-------|-----|
| Node shows red border | Execution error | Click node → check OUTPUT panel |
| `name 'items' is not defined` | Wrong Python variable | Use `_items` not `items` |
| Switch not routing | Value comparison failing | Verify upstream data is clean JSON, not raw text |
| Webhook timeout | No HTTP call made | Use PowerShell `Invoke-RestMethod` or reqbin.com |
| Empty output | Data not flowing | Check connection arrows, run "Execute previous nodes" |

**Top tip:** Always compare the INPUT vs OUTPUT panels side by side after execution — the most common failure is a mismatch between what the upstream node outputs and what the downstream node expects. The Anthropic node returns `content[0].text` as a raw string, not a parsed object — always add a Code node to parse it before routing.

---

## Files

| File | Description |
|------|-------------|
| `Procurement AI approval.json` | Importable n8n workflow JSON |
| `n8n_node_reference.md` | Full node reference table with JSON examples |
| `lab_summary.md` | Study guide — node selection logic and debugging tips |
| `Screenshot/` | Workflow canvas screenshot |
