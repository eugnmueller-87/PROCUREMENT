# Hi, I'm Eugen 👋

**Procurement Leader → AI Engineer** | Berlin 🇩🇪

10+ years leading procurement and category management at **TeamViewer**, **Scout24**, and **Delivery Hero** — now engineering the AI systems that will transform the function I know inside out.

I don't just advise on AI transformation. I build the tools myself.

Every project here started with a real problem I personally encountered running procurement teams: manual triage, supplier compliance gaps, fragmented spend data, slow RFP cycles, and market intelligence that arrives too late. These are my answers — designed by someone who has lived them and built by someone who can now ship them.

Currently completing the **AI Integration Bootcamp @ Ironhack Berlin** (Week 5 of 9).

---

## Procurement AI Transformation

*AI-powered tools built from 10+ years of hands-on procurement experience — targeting the exact pain points category managers, CPOs, and procurement ops teams face daily.*

| Project/Description | GitHub |
|---|---|
| 🔴 **SpendLens** — Full-stack AI procurement intelligence platform. React 18 SPA served by FastAPI. Ingests any spend file (CSV, Excel, SAP/Coupa), auto-maps messy columns via Claude, runs a 5-stage pipeline: column mapping → data cleanup → vendor classification → compliance flagging → supplier intelligence. Dashboard with year-aware KPIs, YoY diverging bar chart, Category Risk Matrix, 5-year stacked area trend. Deep Dive with spend growth, treemap, drill-in category drawers. EcoVadis-style Compliance Scorecard (26 suppliers, ABC tiers, multi-filter). AI contract clause extraction with RiskArc gauge and renewal tracking (CLM). Category Strategy workbench — 7 AI frameworks (Kraljic, PESTEL, SWOT, Porter's, TCO, Negotiation Levers, 3-year Recommendation) + 10-slide HTML export. Icarus AI market signal feed with category tabs and Hermes integration. Deployed live on Railway. | [Link](https://github.com/eugnmueller-87/PROCUREMENT) |
| 🔁 **Autonomous Procurement Triage Agent** — End-to-end autonomous agent replacing manual PR triage. 5-tier routing by value (<€5k auto-approve → >€100k full RFP). Supplier NDA/DPA/MSA compliance check on every request via RAG. Guided business case builder for high-value purchases. RFQ/RFP document generation, multi-supplier outreach, quote collection, evaluation matrix, award recommendation. 6 importable n8n workflows. | [Link](https://github.com/eugnmueller-87/Triage-Agent) |
| 🔍 **Hermes — Market Intelligence Sub-Agent** — Autonomous sub-agent deployed on Railway. Crawls ~590 tech/procurement suppliers across 17 categories via 5 scheduled crawlers (RSS, EDGAR, Tavily, Jobs, Earnings transcripts). 11 signal types classified by Claude Haiku: NEW/CONTINUING/RESOLVED with delta tracking. Semantic RAG search via Upstash Vector (1024-dim BGE). Macro theme clustering. Trend memory per supplier. Powers SpendLens Icarus AI with live market signals injected on every scan. | [Link](https://github.com/eugnmueller-87/Hermes) |
| ⚡ **Hades — Supplier Due Diligence Agent** — Production-deployed autonomous DD agent. POST a company name → full risk report in under 2 minutes. 6 parallel LangGraph nodes: OFAC SDN + UN SC sanctions (free XML, no key), NorthData company registry, BAFA/NCP/NGO LkSG/CSDDD compliance signals, ESG & labour risk, 90-day news sentiment, Hermes market intelligence. Claude Sonnet 4.6 synthesises into weighted risk score (1–10) + recommendation: Approve / Conditional Approval / Block. Auto-registers every supplier to Hermes watchlist for ongoing monitoring. Integrated into SpendLens Supplier DD screen with live status badge and 10-step pipeline tracker. | [Link](https://github.com/eugnmueller-87/Hades) |

---

## What I've Built — Technical Capabilities

| Capability | Tools / Stack |
|---|---|
| Production REST APIs | FastAPI, uvicorn, Railway |
| React frontends (no build step) | React 18 UMD, Babel standalone, oklch design system |
| AI pipeline orchestration | LangGraph, Claude API (Sonnet 4.6, Haiku 4.5) |
| Autonomous agent workflows | n8n (6 importable workflows), LangGraph multi-node |
| Vector search & RAG | Upstash Vector (1024-dim BGE embeddings) |
| Market data pipelines | RSS (feedparser), EDGAR, Tavily, job board crawlers |
| Persistent data stores | SQLite (WAL, per-client), Upstash Redis |
| Document intelligence | pypdf, python-docx, AI clause extraction |
| Data engineering | Pandas, fuzzy column mapping, German/ERP format handling |
| Compliance data | OFAC SDN XML, UN SC, BAFA, NCP, NorthData registry |

---

## Procurement Domain Expertise

**10+ years across:**
- Category Management (Cloud, IT, Professional Services, Marketing, FM, Travel)
- Strategic Sourcing — RFQ/RFP design, evaluation matrices, award recommendations
- Supplier Relationship Management — ABC tiering, compliance scoring, LkSG/CSDDD
- Contract Lifecycle Management — MSA, NDA, DPA, SLA, auto-renewal risk
- Spend Analytics — P2P process design, maverick spend reduction, budget variance
- Market Intelligence — commodity pricing, vendor negotiation leverage, benchmark data

---

## Connect

- **LinkedIn:** [linkedin.com/in/eugen-mueller](https://linkedin.com/in/eugen-mueller)
- **Location:** Berlin, Germany
- **Email:** eugnmueller@googlemail.com
