# n8n Node Reference Table
## Procurement AI Approval Workflow — Node Study Guide
**Author:** Eugen Müller  
**Date:** May 2026  
**Workflow:** Procurement AI Approval (SpendLens Intake Agent)

---

## Workflow Overview

This workflow automates procurement request triage using AI. A purchase request is submitted via webhook, analyzed by Claude AI, parsed, stored in Airtable, routed by risk level, and processed accordingly — with email approval for MEDIUM and HIGH risk items.

```
Webhook → Message a Model (Claude) → Code in Python → Create a Record (Airtable) → Switch → ...
  ├── LOW   → Edit Fields (auto-approve) → IF → true: HTTP Request (FX rate) / false: Wait
  ├── MEDIUM → Edit Fields (Mid Risk) → Send message and wait for response → Wait
  └── HIGH  → Edit Fields (High Risk) → Send message and wait for response
```

---

## Node Reference Table

| # | Node | Parameters | Settings | What It Does | JSON Input | JSON Output | Key Transformations |
|---|------|------------|----------|--------------|------------|-------------|---------------------|
| 1 | **Webhook** | Method: POST, Path: auto-generated UUID, Authentication: None, Respond: Immediately | Response Code, Headers | Receives incoming HTTP POST requests and passes body data into the workflow | HTTP POST request with JSON body | n8n data format with headers, body, params, query fields | HTTP request → n8n JSON format. Body fields become accessible via `$json.body.fieldname` |
| 2 | **Anthropic (Message a Model)** | Credential: Anthropic API Key, Model: claude-haiku-4-5-20251001, Messages: User prompt with expressions, Simplify Output: ON | Resource: Text, Operation: Message a Model | Sends a prompt to Claude AI and returns the model's response | Procurement request fields from webhook body | `content[0].text` containing AI-generated JSON response | Transforms structured input fields into an AI-generated risk assessment. Raw text output contains JSON wrapped in markdown backticks |
| 3 | **Code in Python** | Language: Python, Mode: Run Once for All Items | None | Executes custom Python code to parse and transform data | Raw AI response with `content[0].text` as JSON string in markdown | Clean JSON object with `risk_level`, `risk_reason`, `suggested_action`, `summary` | Strips markdown backticks from AI response using regex, parses JSON string into structured fields accessible downstream |
| 4 | **Create a record (Airtable)** | Operation: Create, Base: Procurement base, Table: Requests, Fields: all mapped columns | Credential: Airtable PAT | Writes the incoming request + AI assessment to Airtable | Clean JSON with all fields | Airtable record confirmation | Maps `requester`, `vendor`, `Number($json.amount)`, `category`, `risk_level`, `suggested_action`, `$now` to Airtable columns. Amount must be cast to Number() |
| 5 | **Switch** | Mode: Rules, Routing Rules: Rule 1 = LOW, Rule 2 = MEDIUM, Rule 3 = HIGH (all compare `$json.risk_level`) | Convert types: OFF | Routes data to different branches based on the value of `risk_level` | Clean JSON with `risk_level` field | Same JSON routed to output 0 (LOW), 1 (MEDIUM), or 2 (HIGH) | Multi-way conditional routing. No data transformation — only routing based on field value |
| 6 | **Edit Fields — LOW risk auto approve** | Mode: Manual Mapping, Fields: `approval_status` = "auto-approved", `message` = "Low risk - auto approved by system" | Include Other Input Fields: OFF | Sets approval fields for low-risk items | JSON from Switch output 0 | JSON with `approval_status` and `message` fields | Adds approval decision fields |
| 7 | **IF** | Conditions: `$json.approval_status` is equal to "auto-approved" | Convert types: OFF | Routes auto-approved items to FX check, others to Wait | JSON with `approval_status` | Same JSON routed to True or False branch | Boolean routing — true = currency check, false = wait for manual review |
| 8 | **HTTP Request (WECHSELKURS)** | Method: GET, URL: `https://api.exchangerate-api.com/v4/latest/EUR`, Authentication: None | Response Format: Auto | Fetches current EUR exchange rates for currency validation | Any JSON | API response with exchange rate data | External API call for vendor currency check |
| 9 | **Edit Fields — Mid Risk** | Mode: Manual Mapping | None | Prepares data for MEDIUM risk email notification | JSON from Switch output 1 | JSON with mid risk fields | Field preparation for manager notification |
| 10 | **Send message and wait for response (MEDIUM)** | Operation: Send and Wait for Response, Response Type: Approval | Credential: SMTP | Sends approval email to manager and pauses workflow until response | Mid risk JSON | Approval/rejection response | Converts workflow data to email + suspends execution pending human decision |
| 11 | **Wait** | Resume: After Time Interval, Wait Amount: 5, Wait Unit: Seconds | None | Pauses workflow execution | Any JSON | Same JSON after delay | No data transformation. Timeout buffer before next action |
| 12 | **Edit Fields — High Risk** | Mode: Manual Mapping | None | Prepares data for HIGH risk email notification | JSON from Switch output 2 | JSON with high risk fields | Field preparation for VP/CFO notification |
| 13 | **Send message and wait for response (HIGH)** | Operation: Send and Wait for Response, Response Type: Approval | Credential: SMTP | Sends escalation email for high-risk items and waits for senior approval | High risk JSON | Approval/rejection response | Senior approval loop — workflow suspended until CFO/VP responds |
| 14 | **Manual Trigger** | None | None | Starts the workflow manually when "Execute workflow" is clicked | None | Empty item `{}` | Entry point with no data. Used for testing |

---

## JSON Data Flow Example

### Input (via Webhook POST)
```json
{
  "requester": "Anna Schmidt",
  "vendor": "Adobe Inc",
  "amount": 4500,
  "category": "Software",
  "description": "Creative Cloud licenses for design team"
}
```

### After Anthropic Node (raw)
```json
{
  "content": [
    {
      "type": "text",
      "text": "```json\n{\n  \"risk_level\": \"LOW\",\n  \"risk_reason\": \"Routine software license purchase from established vendor\",\n  \"suggested_action\": \"auto-approve\",\n  \"summary\": \"Anna Schmidt requests $4,500 for Adobe Creative Cloud licenses.\"\n}\n```"
    }
  ]
}
```

### After Code in Python Node (parsed)
```json
{
  "risk_level": "LOW",
  "risk_reason": "Routine software license purchase from established vendor within typical spend parameters for design team tools.",
  "suggested_action": "auto-approve",
  "summary": "Anna Schmidt requests $4,500 for Adobe Creative Cloud licenses to support the design team's software needs."
}
```

### After Airtable Node (record created)
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

### After Edit Fields Node (LOW path)
```json
{
  "approval_status": "auto-approved",
  "message": "Low risk - auto approved by system"
}
```

---

## Routing Logic

| Risk Level | Switch Output | Path | Action |
|------------|--------------|------|--------|
| LOW | 0 | Edit Fields → IF → HTTP Request | Auto-approve + FX rate check |
| LOW (false branch) | 0 | Edit Fields → IF → Wait | Timeout/manual fallback |
| MEDIUM | 1 | Edit Fields → Send & Wait → Wait | Manager email approval |
| HIGH | 2 | Edit Fields → Send & Wait | CFO/VP email escalation |

---

## Key Concepts Learned

### Expression Syntax
n8n uses `{{ $json.fieldname }}` to reference data from the previous node:
- `{{ $json.body.vendor }}` — access webhook body field
- `{{ $json.risk_level }}` — access parsed field
- `{{ $json.content[0].text }}` — access AI response text
- `{{ Number($json.body.amount) }}` — cast string to number (required for numeric Airtable fields)
- `{{ $('Webhook').item.json.body.amount }}` — reference specific node output by name

### Node Connection Types
- **Single output:** Webhook, Code, Edit Fields, HTTP Request, Wait, Airtable
- **Multiple outputs:** Switch (0/1/2 branches), IF (true/false branches)

### Data Persistence
Each node receives the full output of the previous node. Fields are only preserved if explicitly passed through or if "Include Other Input Fields" is enabled on Set nodes.

### Testing Approach
- **Test mode:** Webhook requires "Listen for test event" to be active before sending request
- **Production mode:** Activate workflow → use Production URL (no `-test` in URL) → runs permanently
- Individual nodes can be tested with "Execute step" + "set mock data"
- PowerShell trigger: `Invoke-RestMethod -Uri <url> -Method POST -ContentType "application/json" -Body '<json>'`

---

## Debugging Tips

| Issue | Cause | Fix |
|-------|-------|-----|
| Node shows red border | Execution error | Click node → check OUTPUT panel for error details |
| `name 'items' is not defined` | Wrong Python variable name | Use `_items` not `items` in n8n Python nodes |
| Switch not routing | Value comparison failing | Check if upstream data is clean JSON or raw text string |
| Webhook timeout | No HTTP call made while listening | Use PowerShell `Invoke-RestMethod` — click "Listen for test event" first |
| Empty output | Data not flowing from previous node | Check connection arrows and run "Execute previous nodes" |
| `INVALID_VALUE_FOR_COLUMN` | Airtable field type mismatch | Wrap numeric fields in `Number()` — e.g. `Number($('Webhook').item.json.body.amount)` |
| "Unused Respond to Webhook node" | Respond node exists but Webhook is set to "Immediately" | Delete the Respond to Webhook node or change Webhook respond setting |
| "There was a problem executing the workflow" | Node credential missing (red triangle) | Configure credentials on all nodes before activating |
| Python not found in PowerShell | Python not in system PATH | Use full venv path or switch to `Invoke-RestMethod` directly |

---

## Workflow Architecture Diagram

```
[Webhook] 
    ↓ POST request received
[Message a Model - Claude]
    ↓ AI risk assessment (raw text with markdown)
[Code in Python]
    ↓ Parsed + cleaned JSON fields
[Create a record - Airtable]
    ↓ Record logged with all fields
[Switch — routes by risk_level]
    │
    ├── 0: LOW  → [Edit Fields: auto-approve] → [IF]
    │                                            ├── true:  [HTTP Request: FX rate check]
    │                                            └── false: [Wait]
    │
    ├── 1: MEDIUM → [Edit Fields: Mid Risk] → [Send & Wait for Response] → [Wait]
    │
    └── 2: HIGH   → [Edit Fields: High Risk] → [Send & Wait for Response]

[Manual Trigger] — standalone, used for testing
```
