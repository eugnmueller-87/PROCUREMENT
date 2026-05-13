# n8n Node Reference Table
## Procurement AI Approval Workflow — Node Study Guide
**Author:** Eugen Müller  
**Date:** May 2026  
**Workflow:** Procurement AI Approval (SpendLens Intake Agent)

---

## Workflow Overview

This workflow automates procurement request triage using AI. A purchase request is submitted via webhook, analyzed by Claude AI, parsed, routed by risk level, and processed accordingly.

```
Webhook → Message a Model (Claude) → Code in Python → Switch → Edit Fields → IF → HTTP Request / Wait → Respond to Webhook
```

---

## Node Reference Table

| # | Node | Parameters | Settings | What It Does | JSON Input | JSON Output | Key Transformations |
|---|------|------------|----------|--------------|------------|-------------|---------------------|
| 1 | **Webhook** | Method: POST, Path: auto-generated UUID, Authentication: None, Respond: Immediately | Response Code, Headers | Receives incoming HTTP POST requests and passes body data into the workflow | HTTP POST request with JSON body | n8n data format with headers, body, params, query fields | HTTP request → n8n JSON format. Body fields become accessible via `$json.body.fieldname` |
| 2 | **Anthropic (Message a Model)** | Credential: Anthropic API Key, Model: claude-haiku-4-5-20251001, Messages: User prompt with expressions, Simplify Output: ON | Resource: Text, Operation: Message a Model | Sends a prompt to Claude AI and returns the model's response | Procurement request fields from webhook body | `content[0].text` containing AI-generated JSON response | Transforms structured input fields into an AI-generated risk assessment. Raw text output contains JSON wrapped in markdown backticks |
| 3 | **Code in Python** | Language: Python, Mode: Run Once for All Items | None | Executes custom Python code to parse and transform data | Raw AI response with `content[0].text` as JSON string in markdown | Clean JSON object with `risk_level`, `risk_reason`, `suggested_action`, `summary` | Strips markdown backticks from AI response using regex, parses JSON string into structured fields accessible downstream |
| 4 | **Switch** | Mode: Rules, Routing Rules: 3 rules comparing `$json.risk_level` to LOW/MEDIUM/HIGH | Convert types: OFF | Routes data to different branches based on the value of a field | Clean JSON with `risk_level` field | Same JSON routed to output 0 (LOW), 1 (MEDIUM), or 2 (HIGH) | Multi-way conditional routing. No data transformation — only routing based on field value |
| 5 | **Edit Fields (Set)** | Mode: Manual Mapping, Fields: `approval_status` = "auto-approved", `message` = "Low risk - auto approved by system" | Include Other Input Fields: OFF | Sets or overwrites specific fields in the JSON data | Any JSON from Switch output | Same JSON plus new fields `approval_status` and `message` | Adds new fields to the data object. Existing fields are dropped unless "Include Other Input Fields" is toggled ON |
| 6 | **IF** | Conditions: `$json.approval_status` is equal to "auto-approved", Convert types: OFF | None | Routes data to True or False branch based on a condition | JSON with `approval_status` field | Same JSON routed to True (condition met) or False (condition not met) branch | Boolean conditional routing. No data transformation — splits flow into two paths |
| 7 | **HTTP Request** | Method: GET, URL: `https://api.exchangerate-api.com/v4/latest/EUR`, Authentication: None, Send Body: OFF | Response Format: Auto | Makes an external HTTP API call and returns the response | Any JSON (or empty) | API response as JSON (exchange rate data in this case) | External API call → n8n JSON. Useful for vendor lookups, ERP integrations, currency checks |
| 8 | **Wait** | Resume: After Time Interval, Wait Amount: 5, Wait Unit: Seconds | None | Pauses the workflow execution for a defined time interval | Any JSON | Same JSON passed through after delay | No data transformation. Suspends execution and resumes after interval. Useful for approval timeouts |
| 9 | **Respond to Webhook** | Respond With: First Incoming Item, Response Code: 200 | None | Sends an HTTP response back to the original webhook caller | Any JSON | HTTP response sent back to caller | Closes the webhook request loop. Converts n8n JSON back to HTTP response format |
| 10 | **Manual Trigger** | None | None | Starts the workflow manually when "Execute workflow" is clicked | None | Empty item `{}` | Entry point with no data. Useful for testing and one-off manual workflows |

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

### After Edit Fields Node
```json
{
  "approval_status": "auto-approved",
  "message": "Low risk - auto approved by system"
}
```

---

## Key Concepts Learned

### Expression Syntax
n8n uses `{{ $json.fieldname }}` to reference data from the previous node:
- `{{ $json.body.vendor }}` — access webhook body field
- `{{ $json.risk_level }}` — access parsed field
- `{{ $json.content[0].text }}` — access AI response text

### Node Connection Types
- **Single output:** Webhook, Code, Edit Fields, HTTP Request, Wait
- **Multiple outputs:** Switch (0/1/2 branches), IF (true/false branches)

### Data Persistence
Each node receives the full output of the previous node. Fields are only preserved if explicitly passed through or if "Include Other Input Fields" is enabled on Set nodes.

### Testing Approach
- Webhook nodes require an external HTTP call to trigger (used PowerShell `Invoke-RestMethod`)
- Individual nodes can be tested with "Execute step" + "set mock data"
- Full workflow test: "Execute workflow" then trigger the webhook

---

## Debugging Tips

| Issue | Cause | Fix |
|-------|-------|-----|
| Node shows red border | Execution error | Click node to see error details in OUTPUT panel |
| `name 'items' is not defined` | Wrong Python variable name | Use `_items` not `items` in n8n Python nodes |
| Switch not routing | Value comparison failing | Check if upstream data is clean JSON or raw text string |
| Webhook timeout | No HTTP call made | Use PowerShell `Invoke-RestMethod` or reqbin.com to POST test data |
| Empty output | Data not flowing from previous node | Check connection arrows and run "Execute previous nodes" |

---

## Workflow Architecture Diagram

```
[Webhook] 
    ↓ POST request received
[Message a Model - Claude]
    ↓ AI risk assessment (raw text)
[Code in Python]
    ↓ Parsed JSON fields
[Switch]
    ├── 0: LOW  → [Edit Fields] → [IF] ──→ true:  [HTTP Request] (vendor check)
    │                               └──→ false: [Wait] → [Respond to Webhook]
    ├── 1: MEDIUM → (manager review branch)
    └── 2: HIGH   → (VP approval branch)

[Manual Trigger] — standalone, used for testing
```
