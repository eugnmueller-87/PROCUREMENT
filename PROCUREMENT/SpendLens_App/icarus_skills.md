# Icarus Domain Skills
# Procurement intelligence knowledge base — loaded as context for Icarus queries.
# Each section defines what Icarus knows and how it reasons in that domain.

---

## 1. Core Procurement

### What good looks like
- **Source-to-Pay (S2P):** Full cycle from need identification → sourcing → contracting → PO issuance → goods receipt → invoice matching → payment. Gaps at any stage create maverick spend, fraud risk, or compliance failures.
- **Category management:** Spend is grouped into categories (e.g. Cloud & Compute, Professional Services) managed by a category manager who owns the supplier strategy, not just individual contracts.
- **Supplier segmentation:** Not all suppliers are equal. Strategic (high spend, high risk) → Preferred (approved, negotiated terms) → Transactional (low value, spot buy). Strategy differs per tier.
- **Total Cost of Ownership (TCO):** Price is only one input. Include onboarding cost, integration effort, switching cost, risk premium, compliance overhead.
- **Spend visibility:** You cannot manage what you cannot see. Clean, categorized spend data is the foundation. Without it, savings claims are estimates, not facts.

### Key metrics Icarus tracks
| Metric | What it signals |
|---|---|
| Maverick spend % | Spend outside approved suppliers/contracts — policy failure |
| PO coverage % | % of invoices with a matching PO — process discipline |
| Contract coverage % | % of spend under active contract — risk exposure |
| Single-source % | Supplier dependency risk |
| Payment terms | Cash flow leverage / early payment discount opportunity |
| Lead time days | Supply chain resilience |
| EBITDA impact | Procurement's contribution to bottom line |

### Common procurement failure modes
- No PO before invoice (three-way match breaks down)
- Contract expiry unmanaged (auto-renewal at list price)
- Shadow IT: software purchased outside IT/procurement visibility
- Freelancer/contractor spend classified as vendor spend (compliance risk)
- Duplicate invoices from same vendor across different cost centres
- FX exposure on international contracts with no hedging clause

---

## 2. Procurement Excellence

### Maturity model (5 levels)
| Level | Name | Characteristics |
|---|---|---|
| 1 | Reactive | Ad hoc buying, no policy, price-only focus |
| 2 | Operational | Basic PO process, approved vendor lists, some contracts |
| 3 | Tactical | Category plans, supplier scorecards, savings tracking |
| 4 | Strategic | Cross-functional, demand management, risk-adjusted sourcing |
| 5 | Value-creating | Procurement as competitive advantage, innovation sourcing, supplier co-development |

### Levers for moving up the maturity curve
- **Policy & governance:** Define who can buy what, from whom, up to what value. Approval matrices must be enforced in the system, not just on paper.
- **Supplier relationship management (SRM):** Regular QBRs, scorecards (quality, delivery, innovation, ESG), escalation paths. Strategic suppliers get development plans.
- **Demand management:** Challenge the need before sourcing. "Do we need this at all, at this spec, at this volume?"
- **Should-cost modelling:** Build a cost model from first principles (materials, labour, overhead, margin) to understand what a product/service *should* cost before entering negotiation.
- **Benchmarking:** Compare pricing against market indices, peer companies, or public procurement data.
- **Savings governance:** Distinguish hard savings (P&L impact) from soft savings (cost avoidance, rebates). Only count what hits the bottom line.

### Negotiation principles
- **BATNA first:** Know your Best Alternative To Negotiated Agreement before any conversation. Never negotiate without one.
- **Multi-variable negotiation:** Price, volume commitment, payment terms, SLA, IP ownership, exit clauses, audit rights. Trading across variables creates value both sides don't see in price-only talks.
- **Anchoring:** Open with a position that sets the reference point. Don't let the supplier anchor first.
- **Market signals as leverage:** News of supplier financial distress, new market entrants, or technology shifts changes negotiation power. Icarus monitors these.

---

## 3. Supply Chain

### Core frameworks
- **SCOR model:** Plan → Source → Make → Deliver → Return → Enable. Icarus focuses on Plan (demand sensing), Source (supplier risk), and Enable (data & analytics).
- **Bullwhip effect:** Small demand fluctuations amplify upstream. Avoid over-ordering in response to short-term signals.
- **Safety stock vs. just-in-time:** JIT reduces inventory cost but increases disruption risk. Post-COVID norm is buffer stock for critical components.

### Risk categories Icarus monitors
| Risk type | Examples | Early warning signals |
|---|---|---|
| Supply disruption | Factory fire, port closure, geopolitical | News from supplier's country/region |
| Single-source dependency | One supplier for critical input | Concentration flag in spend data |
| Financial distress | Supplier credit downgrade, layoffs | Reuters/financial press coverage |
| Regulatory / compliance | CBAM, GDPR, supply chain due diligence laws | Euractiv, regulatory press |
| Commodity price | Cloud compute costs, hardware component prices | DatacenterDynamics, Reuters |
| Geopolitical | Tariffs, sanctions, export controls | Reuters, Handelsblatt |

### Supply chain resilience levers
- Dual-source or multi-source critical categories
- Nearshoring / regional sourcing for long-lead-time items
- Demand-side flexibility (product variants that use common components)
- Inventory buffers with clear trigger rules for replenishment
- Supplier financial health monitoring (Dun & Bradstreet, annual reports)
- Contractual force majeure review — many COVID-era gaps remain

### Digital supply chain signals Icarus uses
- Port congestion indices (Bloomberg, Freightos)
- Semiconductor lead times (The Register, DatacenterDynamics)
- Cloud provider capacity announcements (Reuters Tech, provider blogs)
- EU regulatory changes (Euractiv, Handelsblatt)
- Freelancer market rate trends (FreelancerMap)

---

## 4. Business Transformation in Procurement

### What transformation means
Moving procurement from a cost centre that processes purchase orders to a strategic function that actively shapes business outcomes: innovation pipeline, ESG positioning, supply chain resilience, cash flow, and EBITDA.

### Transformation levers
- **Operating model redesign:** Centralise vs. decentralise? Centre-led category management with local execution is the common answer for mid-size companies.
- **Process digitisation:** Replace email-and-spreadsheet buying with a proper P2P system (Coupa, SAP Ariba, Jaggaer, or simpler tools like Pleo + procurement approval flows for startups).
- **Data foundation:** Without clean spend data, no transformation sticks. Taxonomy alignment, ERP integration, and vendor master cleanup come first.
- **Change management:** Procurement transformation always requires business-side buy-in. Finance, Legal, IT, and HR all touch procurement. Governance without relationships fails.
- **Capability building:** Upskill buyers from order-placers to category managers. Commercial negotiation, data literacy, and supplier development skills are the gaps in most teams.

### Transformation phases (typical 18-month arc)
| Phase | Months | Focus |
|---|---|---|
| Diagnose | 1–3 | Spend analysis, process mapping, maturity assessment |
| Stabilise | 3–6 | Quick wins: contract renewals, policy, approved lists |
| Build | 6–12 | Category strategies, supplier segmentation, P2P rollout |
| Optimise | 12–18 | SRM, savings governance, advanced analytics |

### Common transformation failures
- Starting with the tool, not the process (software doesn't fix bad process)
- No executive sponsor — procurement transformation needs CFO or COO backing
- Savings targets set before diagnosis — creates gaming, not real savings
- Ignoring the stakeholder (internal customer) experience — compliance drops if the process is painful
- Treating all categories the same — commodities need different strategy than professional services

---

## 5. Technical Business Transformation in Finance

### Finance function transformation context
Finance teams increasingly own or co-own procurement data. Key touchpoints:
- **AP automation:** Invoice processing, three-way match, payment runs. Icarus flags discrepancies that increase AP workload.
- **ERP data quality:** Most spend data quality issues originate in ERP master data (vendor master, cost centre mapping, GL coding). Clean GL = clean spend analysis.
- **FP&A integration:** Procurement savings should flow into the rolling forecast. If procurement and FP&A use different data sources, savings claims are disputed.
- **Cash flow management:** Payment terms optimisation is a procurement lever with direct treasury impact. Extending terms 30→60 days on €10M spend = €800K free cash flow (at 10% cost of capital).

### Technical stack Icarus understands
| Layer | Tools common in mid-market |
|---|---|
| ERP / source system | SAP S/4HANA, SAP Business One, Microsoft Dynamics, NetSuite, Datev (DE) |
| P2P / eProcurement | Coupa, SAP Ariba, Jaggaer, Pleo, Spendesk, Yokoy |
| Analytics | Power BI, Tableau, Python/pandas (SpendLens), Qlik |
| Contract management | Ironclad, Juro, DocuSign CLM, SharePoint (common but weak) |
| Expense management | Concur, Expensify, Pleo, Moss |

### Finance transformation signals Icarus watches
- ERP vendor announcements (SAP roadmap, Microsoft Dynamics updates)
- Regulatory changes affecting financial reporting (e.g. CSRD, e-invoicing mandates)
- Interest rate movements (affects payment term value, lease vs. buy decisions)
- AI tooling in finance automation (invoice AI, contract AI — adoption signals)

### Key finance-procurement interfaces
- **Month-end close:** Accruals for goods received not invoiced (GRNI). Icarus flags high-value open POs near month-end.
- **Budget vs. actuals:** Procurement commitments (POs raised but not yet invoiced) should be visible to FP&A as pipeline spend.
- **Audit readiness:** Procurement controls (three-way match, segregation of duties, contract evidence) are audit scope items. Gaps create findings.

---

## 6. Startup and Scale-Up Procurement Setup

### Startup phase (0–50 people, <€5M spend)
**Goal:** Avoid chaos, not build bureaucracy.
- Designate one person responsible for vendor decisions (usually COO, CFO, or a generalist ops hire)
- Set a simple approval matrix: <€500 self-service, €500–€5K manager approval, >€5K founder/CFO
- Use a company card tool (Pleo, Spendesk, Moss) with category tagging from day one — this becomes your spend database
- Centralise SaaS subscriptions: one list, one owner, one renewal calendar
- Standard contract terms for common buys (software, freelancers, agencies) — don't negotiate every deal from zero
- Freelancer vs. employee classification: get this right early. Misclassification is expensive to unwind.

### Scale-up phase (50–500 people, €5M–€50M spend)
**Goal:** Build the foundation before complexity breaks it.
- **Spend visibility first:** Connect ERP + card tool + expense tool into one taxonomy. SpendLens does this.
- **Category ownership:** Assign category owners for the top 5 spend categories (typically Cloud, Professional Services, HR/Recruitment, Facilities, Marketing). They own the strategy, not just the budget.
- **Vendor consolidation:** Scale-ups typically have 3–5x too many vendors in each category due to founder-era ad-hoc buying. Consolidation = savings and simplified management.
- **Contract management:** Build a contract register. At minimum: vendor name, value, start/end date, notice period, auto-renewal flag. A spreadsheet is fine at this stage.
- **P2P tool selection:** At ~€10M spend and 100+ people, a lightweight P2P tool pays for itself. Pleo/Spendesk for card + expense. Add a PO tool (Procurify, Precoro, or the P2P module of your ERP).
- **Procurement hire:** First dedicated procurement hire should be a generalist category manager / commercial analyst, not a CPO. CPO comes when you have a team to lead.

### Common scale-up procurement mistakes
- Letting SaaS subscriptions proliferate unchecked (shadow IT + budget leak)
- Renewing contracts on auto-pilot at list price — vendors expect a negotiation
- No vendor exit clauses (data portability, transition assistance, notice periods)
- Outsourcing too much to a single agency or consultancy — concentration risk
- Over-engineering process before you have enough spend to justify it
- Underinvesting in procurement capability because "we're too busy growing" — the cost of bad contracts compounds

### Signals Icarus watches for startups/scale-ups
- VC funding rounds (competitor or customer scale-up signals)
- SaaS pricing changes (Salesforce, AWS, Workday — common cost shocks)
- Freelancer/contractor market rates (FreelancerMap, LinkedIn salary data)
- Office market conditions (WeWork, Regus — relevant for flexible workspace decisions)
- HR tech and ATS pricing (relevant for high-growth hiring phases)
- Payment processing and fintech changes (relevant for embedded finance decisions)

---

## 7. Contract Lifecycle and Reporting

### Contract lifecycle stages
| Stage | Key activities | Procurement role |
|---|---|---|
| **Initiation** | Business need confirmed, supplier shortlisted | Define scope, risk level, contract type |
| **Negotiation** | Commercial & legal terms agreed | Lead commercial negotiation, legal liaison |
| **Execution** | Contract signed, PO raised, onboarding | Handover to operations, SLA baseline set |
| **Performance** | Delivery tracked, invoices matched | QBR cadence, KPI tracking, escalations |
| **Renewal / Exit** | Notice period managed, renegotiation or rebid | Trigger 90–180 days before expiry |

### Contract types and when to use them
- **Fixed-price / lump sum** — clear scope, low change frequency (IT projects, print, uniforms)
- **Time & materials** — variable scope, professional services, consulting
- **Framework / master agreement** — multiple call-offs over time (staffing agencies, cloud MSPs)
- **Subscription / SaaS** — per-seat or usage-based, annual or multi-year commitment
- **Index-linked** — price tied to CPI, PPI, or commodity index (energy, logistics)

### Contract key clauses Icarus monitors
- **Auto-renewal / notice period** — most SaaS contracts auto-renew with 30–90 day notice windows; missing them locks in another year at current pricing
- **Price escalation clauses** — CPI-linked escalation in facilities and professional services contracts; negotiate caps (e.g. max +3% per annum)
- **Exit / termination for convenience** — how painful is it to leave? Data portability, transition assistance, and notice period are key levers
- **SLA and penalty clauses** — service credits for downtime are standard in cloud; negotiate credit % and recovery time objective (RTO)
- **IP ownership** — for custom development or consulting deliverables, ensure IP assignment is explicit
- **Audit rights** — right to audit supplier costs (especially in cost-plus arrangements) and data handling practices (GDPR)
- **Change control** — how are scope changes priced? Uncapped change orders are a major cost overrun driver in IT projects

### Contract reporting — what to track
| Report | Frequency | Audience | Key content |
|---|---|---|---|
| Contract register | Weekly update | Procurement team | Supplier, value, expiry, notice date, risk flag |
| Expiry pipeline | Monthly | CPO / CFO | Contracts expiring in 90/180/365 days, renewal vs. rebid decision |
| Savings realised | Monthly | CFO | Hard savings vs. cost avoidance, by initiative and category |
| Compliance report | Quarterly | Board / Audit | PO coverage %, maverick spend %, contracts without signed copy |
| Vendor scorecard | Quarterly | Category owners | KPI attainment, delivery, quality, innovation, ESG |

### Red flags Icarus watches for contract risk
- Contract expiry within 90 days with no renewal plan visible in signals
- Supplier financial distress news (credit downgrades, layoffs, M&A activity) for sole-source suppliers
- Regulatory changes that invalidate existing contract terms (e.g. data localisation, new tax treatment)
- Commodity or index movements that will trigger price escalation clauses

---

## 8. Procurement Workflows

### Source-to-Pay (S2P) — core workflow
```
Business need identified
    → Purchase requisition (PR) raised and approved
    → Sourcing decision: spot buy / approved vendor / competitive RFQ / tender
    → Purchase Order (PO) issued
    → Goods / services received (GR)
    → Invoice received and matched (3-way match: PO ↔ GR ↔ Invoice)
    → Payment authorised and executed
    → Spend captured in ERP / analytics
```

### Approval workflows — what good looks like
| Value threshold | Approval level | Max cycle time |
|---|---|---|
| <€500 | Self-service (card or manager) | Same day |
| €500–€5K | Manager + procurement notified | 2 days |
| €5K–€50K | CPO or Head of Procurement | 5 days |
| €50K–€500K | CFO sign-off | 10 days |
| >€500K | Board / Investment Committee | Per board calendar |

### Sourcing workflow — by spend level
- **<€5K (spot buy):** Confirm supplier is on approved list. Issue PO. No RFQ required.
- **€5K–€50K (mini-competition):** 3 written quotes minimum, evaluate on price + quality. Award decision memo.
- **€50K–€500K (RFQ):** Formal request for quotation to 3–5 pre-qualified suppliers. Scoring matrix. Approval by CPO.
- **>€500K (RFP / tender):** Full competitive tender process. Supplier registration, RFP document, clarification Q&A, scored evaluation, board approval for award.

### Three-way match — the control that prevents fraud
When an invoice arrives:
1. Does a PO exist for this supplier and amount? → **PO match**
2. Has goods receipt been confirmed? → **GR match**
3. Does invoice amount ≤ PO amount (within tolerance)? → **Invoice match**

Tolerances: typically ±3–5% or €50 (whichever is smaller) for automatic approval. Outside tolerance → manual review.

### Common workflow breakdowns and fixes
| Symptom | Root cause | Fix |
|---|---|---|
| Invoices arrive before PO | Buying without approval | Enforce 'no PO, no pay' policy in AP |
| Long cycle times | Too many approval layers | Streamline: use delegation of authority, auto-approve repeat spend under €500 |
| Duplicate invoices | No invoice number dedup check | Enable duplicate detection in ERP or AP tool |
| Maverick spend | No approved vendor list, or list unknown to buyers | Publish and enforce preferred vendor list; make ordering from it easiest path |
| Late payments | Invoice disputes or matching failures | Fix upstream (PO quality, GR discipline) rather than chasing AP |

### Procurement workflow KPIs
| KPI | Target | Poor |
|---|---|---|
| PO-before-invoice rate | >90% | <70% |
| Invoice match rate (auto) | >85% | <70% |
| PR-to-PO cycle time | <3 days | >10 days |
| Invoice-to-payment cycle | <30 days | >45 days |
| Supplier on-time delivery | >95% | <85% |
| Contract utilisation rate | >80% | <60% |

### Workflow automation opportunities (by maturity stage)
- **Stage 1 (manual):** Excel PO tracker, email approvals, PDF invoices
- **Stage 2 (basic tools):** Company card tool (Pleo/Spendesk) + approval rules, ERP-generated POs
- **Stage 3 (integrated S2P):** Coupa/Ariba/Jaggaer — full PR→PO→GR→invoice in one system
- **Stage 4 (AI-augmented):** Intelligent contract extraction, AI invoice classification, anomaly detection, predictive spend analysis (SpendLens)

### Icarus monitoring of workflow signals
- ERP and P2P tool pricing/feature changes (vendor lock-in risk)
- Regulatory changes to e-invoicing mandates (EU mandatory e-invoicing rolling out 2025–2028)
- AI tooling in AP automation (opportunity to reduce manual matching cost)
- Labour market signals affecting AP and procurement staffing costs

---

## How Icarus uses this file

When answering a user question or generating a signal summary, Icarus should:
1. **Match the signal to a domain** from this file and apply the relevant framework
2. **Anchor recommendations** in the maturity level and phase of the client (startup vs. scale-up vs. enterprise)
3. **Be specific:** "Renegotiate your AWS contract" is less useful than "AWS Enterprise Discount Programme (EDP) commitments typically yield 20–40% discount vs. on-demand — prepare 3-year consumption forecast before the call"
4. **Flag early warnings:** Use the risk tables above to connect market news to a specific procurement lever
5. **Reference concrete tools and standards** where relevant (SCOR, BATNA, TCO, S2P) — clients use the same language with their boards
