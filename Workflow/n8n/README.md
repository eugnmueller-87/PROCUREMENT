# Procurement AI Approval Workflow — n8n

Automates procurement request triage using AI. A purchase request is submitted via webhook, analyzed by Claude AI, logged to Airtable, routed by risk level, and either auto-approved or sent for human approval via email.

## Workflow Overview

```
Webhook → Message a Model (Claude) → Code in Python → Create a Record (Airtable) → Switch
  ├── LOW    → Edit Fields (auto-approve) → IF → true: HTTP Request (FX rate check)
  │                                             └── false: Wait
  ├── MEDIUM → Edit Fields (Mid Risk) → Send message and wait for response → Wait
  └── HIGH   → Edit Fields (High Risk) → Send message and wait for response
```

![Workflow Screenshot](Screenshot/Screenshot%202026-05-13%20150218.png)

---

## Real-World Context

In mid-sized companies, procurement requests arrive through email or Slack with no consistent triage, no audit trail, and no systematic risk assessment. This workflow automates that intake process: a purchase request submitted via webhook is instantly analyzed by Claude AI, classified by risk level (LOW / MEDIUM / HIGH), logged to Airtable with a full audit trail, and escalated via email only where needed — no human intervention for low-risk items.

---

## Node Reference

| # | Node | What It Does | Key Notes |
|---|------|--------------|-----------|
| 1 | **Webhook** | Receives HTTP POST and passes body into workflow | Body fields via `$json.body.fieldname` |
| 2 | **Message a Model (Claude)** | Sends prompt to Claude, returns risk assessment | Output is `content[0].text` — JSON wrapped in markdown backticks |
| 3 | **Code in Python** | Strips backticks, parses AI response into clean JSON | Outputs `risk_level`, `risk_reason`, `suggested_action`, `summary` |
| 4 | **Create a record (Airtable)** | Logs request + AI assessment to Airtable | Amount must be cast: `Number($json.body.amount)` |
| 5 | **Switch** | Routes to LOW / MEDIUM / HIGH branch on `risk_level` | Routing only — no data transformation |
| 6 | **Edit Fields — LOW** | Sets `approval_status = "auto-approved"` | Drops other fields unless "Include Other Input Fields" is ON |
| 7 | **IF** | Routes auto-approved items to FX check, others to Wait | Boolean split |
| 8 | **HTTP Request (WECHSELKURS)** | Fetches EUR exchange rates for currency validation | Returns API JSON |
| 9 | **Edit Fields — Mid Risk** | Prepares fields for MEDIUM risk email | Field prep for manager notification |
| 10 | **Send message and wait (MEDIUM)** | Emails manager, suspends workflow until approval | SMTP credential required |
| 11 | **Wait** | Pauses workflow for timeout buffer | No data transformation |
| 12 | **Edit Fields — High Risk** | Prepares fields for HIGH risk email | Field prep for VP/CFO notification |
| 13 | **Send message and wait (HIGH)** | Escalation email, suspends until senior approval | SMTP credential required |
| 14 | **Manual Trigger** | Starts workflow manually for testing | Outputs empty `{}` |

---

## Routing Logic

| Risk Level | Path | Action |
|------------|------|--------|
| LOW | Edit Fields → IF → HTTP Request | Auto-approve + EUR FX check |
| LOW (false) | Edit Fields → IF → Wait | Timeout / manual fallback |
| MEDIUM | Edit Fields → Send & Wait → Wait | Manager email approval |
| HIGH | Edit Fields → Send & Wait | CFO/VP email escalation |

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

**After Code in Python (parsed):**
```json
{
  "risk_level": "LOW",
  "risk_reason": "Routine software license purchase from established vendor.",
  "suggested_action": "auto-approve",
  "summary": "Anna Schmidt requests $4,500 for Adobe Creative Cloud licenses."
}
```

**After Airtable (record created):**
```json
{
  "REQUESTER": "Anna Schmidt",
  "Vendor": "Adobe Inc",
  "AMOUNT": 4500,
  "Category": "Software",
  "Risk Level": "LOW",
  "SUGGESTED ACTION": "auto-approve",
  "TIMESTAMP": "2026-05-13T14:35:42.344Z"
}
```

---

## Key Concepts

- **Expression syntax:** `{{ $json.fieldname }}` — e.g. `{{ Number($json.body.amount) }}` to cast string to number
- **Reference upstream node:** `{{ $('Webhook').item.json.body.amount }}`
- **Multiple outputs:** Switch (0/1/2), IF (true/false)
- **Data persistence:** Fields are dropped unless explicitly passed through or "Include Other Input Fields" is ON

---

## Debugging

| Issue | Cause | Fix |
|-------|-------|-----|
| Red border on node | Execution error | Click node → check OUTPUT panel |
| `name 'items' is not defined` | Wrong Python variable | Use `_items` not `items` |
| Switch not routing | Upstream data is raw text | Verify Code node is parsing JSON before Switch |
| Webhook timeout | No request sent while listening | Click "Listen for test event" first, then fire PowerShell |
| `INVALID_VALUE_FOR_COLUMN` | Amount sent as string to Airtable | Wrap in `Number()` |
| "Unused Respond to Webhook" warning | Webhook set to "Immediately" | Delete the Respond node or change Webhook respond setting |
| Credential missing (red triangle) | Node not authenticated | Configure credentials on all nodes before activating |

**Top tip:** Always compare INPUT vs OUTPUT panels side by side. The Anthropic node returns `content[0].text` as a raw string — always add a Code node to parse it before any routing or Airtable write.

---

## Files

| File | Description |
|------|-------------|
| `Procurement AI approval.json` | Importable n8n workflow JSON |
| `n8n_node_reference.md` | Full node reference table with JSON examples |
| `lab_summary.md` | Integration rationale, field mapping, and reflection |
| `Screenshot/` | Workflow canvas screenshot |
