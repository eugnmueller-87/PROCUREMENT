# Lab Summary — n8n Node Study Guide

## Most Useful Nodes

The most valuable nodes for building real-world automation workflows are the **Webhook** (entry point for any HTTP-triggered automation), **Code in Python** (essential for cleaning and transforming messy AI output into structured data), and the **Switch** node (enables multi-way routing logic that mirrors real business rules like approval matrices). The **Anthropic / Message a Model** node stands out as the most powerful — it replaces what would otherwise require complex rule engines with a single AI call that can interpret unstructured requests and return structured decisions.

## How I Pick Nodes for a Task

I follow the data flow: start with a **trigger** (Webhook for external input, Manual Trigger for testing), then add **transformation nodes** (Code, Edit Fields) to shape the data, then **logic nodes** (IF, Switch) to route based on business rules, and finally **action nodes** (HTTP Request, Respond to Webhook) to act on the result. The key question for each step is: *what shape is my data in, and what shape does the next node need it to be?* If the answer requires custom logic, Code node. If it's simple field mapping, Edit Fields. If it's an AI judgment call, Message a Model.

## Top Debugging Tip

Always click a node after execution and check the **INPUT vs OUTPUT panels side by side** — this immediately shows whether data is flowing correctly and what transformation occurred. The most common failure mode is a mismatch between what the upstream node outputs and what the downstream node expects: for example, the Anthropic node returns `content[0].text` as a raw string containing JSON, not a parsed object — which breaks any node trying to access `$json.risk_level` directly. The fix is always a Code node in between to parse and reshape the data before routing.
