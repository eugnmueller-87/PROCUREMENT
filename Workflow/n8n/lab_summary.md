# Lab Summary — Multi-App Integration: Webhook + Airtable
## Procurement AI Approval Workflow (SpendLens Intake Agent)
**Author:** Eugen Müller | **Date:** May 2026

---

## Real-World Justification

In mid-sized companies, procurement requests arrive through email, Slack, or ad-hoc forms — with no consistent triage, no audit trail, and no systematic risk assessment. A procurement manager or category lead spends significant time manually reviewing requests, chasing approvals, and logging decisions into spreadsheets. This workflow automates that intake process: a purchase request submitted via webhook is instantly analyzed by Claude AI, classified by risk level (LOW / MEDIUM / HIGH), and logged to Airtable with a suggested action — all without human intervention for low-risk items.

The concrete context is a procurement team at a software company managing indirect spend (SaaS, tooling, services). The automation benefits both the requester (faster response, no inbox black hole) and the procurement lead (structured intake, automatic audit trail, escalation only where needed). It replaces manual copy-paste from email into a tracker, eliminates inconsistent risk judgments, and creates a compliance-ready record of every request and its disposition. The two tools fit because Airtable provides a lightweight, visible, shareable record store — and n8n's webhook + AI nodes handle the intake and classification without requiring a custom backend.

---

## Integration Pair, Field Mapping, and Reflection

**Integration pair:** HTTP Webhook (source) → Airtable (destination), with Claude AI (Anthropic node) and a Python Code node in between for transformation.

**Field mapping:** The webhook receives a JSON payload with `requester`, `vendor`, `amount`, `category`, and `description`. The Anthropic node receives these fields as a structured prompt and returns a JSON object (wrapped in markdown backticks) containing `risk_level`, `risk_reason`, `suggested_action`, and `summary`. The Code in Python node strips the markdown formatting and parses the JSON. The Airtable node then maps all fields — including the original webhook fields and the AI-generated fields — to matching columns: REQUESTER, Vendor, AMOUNT (cast to Number via `Number()`), Category, Risk Level, SUGGESTED ACTION, and TIMESTAMP.

**Hardest part:** The most painful debugging step was the `INVALID_VALUE_FOR_COLUMN` error from Airtable — caused by `amount` arriving as a string from the webhook body while Airtable expected a numeric field. The fix was wrapping the expression in `Number()`. The second challenge was the n8n test-mode behavior: the webhook only accepts requests while "Listen for test event" is active, which required careful coordination between the PowerShell trigger and the n8n UI.

**Extension idea:** Add a Slack notification node on the MEDIUM and HIGH risk branches that sends an approval request directly to the relevant manager's DM, with Approve/Reject buttons — turning this into a full async approval loop without email.

---

## Most Useful Nodes

The most valuable nodes for building real-world automation workflows are the **Webhook** (entry point for any HTTP-triggered automation), **Code in Python** (essential for cleaning and transforming messy AI output into structured data), and the **Switch** node (enables multi-way routing logic that mirrors real business rules like approval matrices). The **Anthropic / Message a Model** node stands out as the most powerful — it replaces what would otherwise require complex rule engines with a single AI call that can interpret unstructured requests and return structured decisions.

## How I Pick Nodes for a Task

I follow the data flow: start with a **trigger** (Webhook for external input, Manual Trigger for testing), then add **transformation nodes** (Code, Edit Fields) to shape the data, then **logic nodes** (IF, Switch) to route based on business rules, and finally **action nodes** (HTTP Request, Airtable, Email) to act on the result. The key question for each step is: *what shape is my data in, and what shape does the next node need it to be?* If the answer requires custom logic, Code node. If it's simple field mapping, Edit Fields. If it's an AI judgment call, Message a Model.

## Top Debugging Tip

Always click a node after execution and check the **INPUT vs OUTPUT panels side by side** — this immediately shows whether data is flowing correctly and what transformation occurred. The most common failure mode is a mismatch between what the upstream node outputs and what the downstream node expects: for example, the Anthropic node returns `content[0].text` as a raw string containing JSON, not a parsed object — which breaks any node trying to access `$json.risk_level` directly. The fix is always a Code node in between to parse and reshape the data before routing.
