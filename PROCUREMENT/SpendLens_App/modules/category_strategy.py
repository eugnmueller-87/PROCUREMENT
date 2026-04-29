"""
category_strategy.py — AI-powered category strategy analysis for SpendLens

Generates 7 procurement frameworks per category using Claude Haiku, persists
results in the spendlens.db `category_strategies` table, and provides spend
data extraction from the enriched transactions table.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import anthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

PROCUREMENT_CATEGORIES = [
    "Cloud & Compute",
    "AI/ML APIs & Data",
    "IT Software & SaaS",
    "Telecom & Voice",
    "Recruitment & HR",
    "Professional Services",
    "Marketing & Campaigns",
    "Facilities & Office",
    "Real Estate",
    "Hardware & Equipment",
    "Travel & Expenses",
]

FRAMEWORK_LABELS = {
    "kraljic":        "Kraljic Matrix",
    "pestel":         "PESTEL",
    "swot":           "SWOT",
    "porter":         "Porter's Five Forces",
    "tco":            "TCO Breakdown",
    "levers":         "Negotiation Levers",
    "recommendation": "Strategy Recommendation",
}


# ── Database helpers ──────────────────────────────────────────────────────────

def _db_path(client_name: str = "default") -> str:
    base = Path(__file__).parent.parent / "clients" / client_name
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "spendlens.db")


def init_strategy_table(client_name: str = "default"):
    conn = sqlite3.connect(_db_path(client_name))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS category_strategies (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name  TEXT NOT NULL,
            category     TEXT NOT NULL,
            framework    TEXT NOT NULL,
            content      TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            UNIQUE(client_name, category, framework)
        )
    """)
    conn.commit()
    conn.close()


def load_strategy(client_name: str, category: str) -> dict:
    """Return {framework: {data: dict, updated_at: str}} for a category."""
    try:
        conn = sqlite3.connect(_db_path(client_name))
        rows = conn.execute(
            "SELECT framework, content, updated_at FROM category_strategies "
            "WHERE client_name=? AND category=?",
            (client_name, category),
        ).fetchall()
        conn.close()
    except Exception:
        return {}
    result = {}
    for framework, content, updated_at in rows:
        try:
            result[framework] = {"data": json.loads(content), "updated_at": updated_at}
        except Exception:
            pass
    return result


def save_framework(client_name: str, category: str, framework: str, data: dict):
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(_db_path(client_name))
    conn.execute("""
        INSERT INTO category_strategies
            (client_name, category, framework, content, generated_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(client_name, category, framework) DO UPDATE SET
            content=excluded.content, updated_at=excluded.updated_at
    """, (client_name, category, framework, json.dumps(data), now, now))
    conn.commit()
    conn.close()


# ── Spend data extraction ─────────────────────────────────────────────────────

def get_category_spend_data(client_name: str, category: str) -> dict:
    """Pull key spend metrics for a category from transactions_enriched."""
    try:
        conn = sqlite3.connect(_db_path(client_name))

        row = conn.execute(
            "SELECT SUM(spend_amount), COUNT(DISTINCT vendor_name) "
            "FROM transactions_enriched WHERE category=?",
            (category,),
        ).fetchone()
        total_spend = row[0] or 0
        vendor_count = row[1] or 0

        vendors = conn.execute(
            "SELECT vendor_name, SUM(spend_amount) as s FROM transactions_enriched "
            "WHERE category=? GROUP BY vendor_name ORDER BY s DESC LIMIT 5",
            (category,),
        ).fetchall()
        top_vendors = [v[0] for v in vendors if v[0]]

        mav = conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN is_maverick=1 THEN 1 ELSE 0 END) "
            "FROM transactions_enriched WHERE category=?",
            (category,),
        ).fetchone()
        maverick_rate = round((mav[1] or 0) / mav[0] * 100, 1) if mav[0] else 0

        po = conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN po_status='With PO' THEN 1 ELSE 0 END) "
            "FROM transactions_enriched WHERE category=?",
            (category,),
        ).fetchone()
        po_coverage = round((po[1] or 0) / po[0] * 100, 1) if po[0] else 0

        conn.close()
        return {
            "total_spend":   total_spend,
            "vendor_count":  vendor_count,
            "top_vendors":   top_vendors,
            "maverick_rate": maverick_rate,
            "po_coverage":   po_coverage,
        }
    except Exception as e:
        print(f"[CategoryStrategy] spend data error: {e}")
        return {}


def _spend_summary(spend_data: dict) -> str:
    if not spend_data:
        return "No spend data available — use general market knowledge."
    parts = []
    if spend_data.get("total_spend"):
        parts.append(f"Total spend: €{spend_data['total_spend']:,.0f}")
    if spend_data.get("vendor_count"):
        parts.append(f"Vendors: {spend_data['vendor_count']}")
    if spend_data.get("top_vendors"):
        parts.append(f"Top vendors: {', '.join(spend_data['top_vendors'][:5])}")
    if spend_data.get("maverick_rate") is not None:
        parts.append(f"Maverick rate: {spend_data['maverick_rate']:.1f}%")
    if spend_data.get("po_coverage") is not None:
        parts.append(f"PO coverage: {spend_data['po_coverage']:.1f}%")
    return " | ".join(parts)


# ── Claude API ────────────────────────────────────────────────────────────────

def _call_claude(prompt: str) -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        system=(
            "You are a senior procurement strategy analyst. "
            "Always respond with valid JSON only — no markdown, no explanation, no code fences."
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]).strip()
    return json.loads(text)


# ── Framework generators ──────────────────────────────────────────────────────

def generate_kraljic(category: str, spend_data: dict, icarus_signals: list = None) -> dict:
    return _call_claude(f"""Position the "{category}" procurement category on a Kraljic Matrix.

Spend context: {_spend_summary(spend_data)}

Assess supply risk (1-10): market concentration, qualified supplier count, supply chain complexity, substitutability.
Assess profit impact (1-10): annual spend volume, operational criticality, competitive advantage impact.

Return JSON:
{{
  "quadrant": "Strategic|Leverage|Bottleneck|Non-critical",
  "supply_risk_score": <1-10>,
  "spend_impact_score": <1-10>,
  "rationale": "<2-3 sentences explaining the positioning>",
  "recommended_posture": "<one clear strategic stance>",
  "key_actions": ["<action>", "<action>", "<action>"]
}}""")


def generate_pestel(category: str, spend_data: dict, icarus_signals: list = None) -> dict:
    signals_ctx = ""
    if icarus_signals:
        relevant = [s for s in icarus_signals if s.get("category") == category][:5]
        if relevant:
            signals_ctx = "\nRecent market signals: " + " | ".join(
                s.get("headline", "") for s in relevant
            )

    return _call_claude(f"""Generate a PESTEL analysis for the "{category}" procurement category.

Spend context: {_spend_summary(spend_data)}{signals_ctx}

Focus on procurement impact. Return JSON with exactly 3 concise bullet points per dimension:
{{
  "political":     ["<point>", "<point>", "<point>"],
  "economic":      ["<point>", "<point>", "<point>"],
  "social":        ["<point>", "<point>", "<point>"],
  "technological": ["<point>", "<point>", "<point>"],
  "environmental": ["<point>", "<point>", "<point>"],
  "legal":         ["<point>", "<point>", "<point>"]
}}""")


def generate_swot(category: str, spend_data: dict, icarus_signals: list = None) -> dict:
    signals_ctx = ""
    if icarus_signals:
        relevant = [s for s in icarus_signals if s.get("category") == category][:5]
        if relevant:
            signals_ctx = "\nRecent market signals: " + " | ".join(
                s.get("headline", "") for s in relevant
            )

    return _call_claude(f"""Generate a SWOT analysis for the "{category}" procurement category from the buyer's perspective.

Spend context: {_spend_summary(spend_data)}{signals_ctx}

Strengths = current buyer advantages. Weaknesses = buyer gaps/vulnerabilities.
Opportunities = exploitable market conditions. Threats = external risks to our position.

Return JSON with exactly 3 points per quadrant:
{{
  "strengths":     ["<point>", "<point>", "<point>"],
  "weaknesses":    ["<point>", "<point>", "<point>"],
  "opportunities": ["<point>", "<point>", "<point>"],
  "threats":       ["<point>", "<point>", "<point>"]
}}""")


def generate_porter(category: str, spend_data: dict, icarus_signals: list = None) -> dict:
    return _call_claude(f"""Analyze Porter's Five Forces for the "{category}" procurement market from the buyer's perspective.

Spend context: {_spend_summary(spend_data)}

Return JSON:
{{
  "supplier_power":       {{"score": <1-10>, "rating": "High|Medium|Low", "factors": ["<factor>", "<factor>"]}},
  "buyer_power":          {{"score": <1-10>, "rating": "High|Medium|Low", "factors": ["<factor>", "<factor>"]}},
  "competitive_rivalry":  {{"score": <1-10>, "rating": "High|Medium|Low", "factors": ["<factor>", "<factor>"]}},
  "threat_of_substitutes":{{"score": <1-10>, "rating": "High|Medium|Low", "factors": ["<factor>", "<factor>"]}},
  "threat_of_new_entrants":{{"score": <1-10>, "rating": "High|Medium|Low", "factors": ["<factor>", "<factor>"]}},
  "summary": "<2 sentence overall market power assessment>"
}}""")


def generate_tco(category: str, spend_data: dict) -> dict:
    return _call_claude(f"""Estimate the Total Cost of Ownership breakdown for "{category}" procurement.

Spend context: {_spend_summary(spend_data)}

Return JSON (percentages must sum to 100):
{{
  "components": [
    {{"name": "Invoice / Contract Price",     "percentage": <number>, "notes": "<brief note>"}},
    {{"name": "Implementation & Onboarding",  "percentage": <number>, "notes": "<brief note>"}},
    {{"name": "Integration & Maintenance",    "percentage": <number>, "notes": "<brief note>"}},
    {{"name": "Internal Resource Cost",       "percentage": <number>, "notes": "<brief note>"}},
    {{"name": "Risk & Compliance Overhead",   "percentage": <number>, "notes": "<brief note>"}}
  ],
  "key_insight": "<most important TCO finding for this category>",
  "reduction_levers": ["<lever>", "<lever>", "<lever>"]
}}""")


def generate_levers(category: str, spend_data: dict, icarus_signals: list = None) -> dict:
    signals_ctx = ""
    if icarus_signals:
        relevant = [s for s in icarus_signals if s.get("category") == category][:3]
        if relevant:
            signals_ctx = "\nMarket signals: " + " | ".join(
                f"{s.get('headline', '')} → {s.get('action', '')}" for s in relevant
            )

    return _call_claude(f"""Generate concrete negotiation levers for "{category}" procurement.

Spend context: {_spend_summary(spend_data)}{signals_ctx}

Return JSON:
{{
  "levers": [
    {{"lever": "<specific lever>", "saving_potential": "<e.g. 5-12%>", "effort": "Low|Medium|High", "priority": "High|Medium|Low"}},
    {{"lever": "<specific lever>", "saving_potential": "<e.g. 3-7%>",  "effort": "Low|Medium|High", "priority": "High|Medium|Low"}},
    {{"lever": "<specific lever>", "saving_potential": "<e.g. 8-15%>", "effort": "Low|Medium|High", "priority": "High|Medium|Low"}},
    {{"lever": "<specific lever>", "saving_potential": "<e.g. 2-5%>",  "effort": "Low|Medium|High", "priority": "High|Medium|Low"}},
    {{"lever": "<specific lever>", "saving_potential": "<e.g. 10-20%>","effort": "Low|Medium|High", "priority": "High|Medium|Low"}}
  ],
  "recommended_approach": "<overall negotiation strategy in one sentence>",
  "optimal_timing": "<when to negotiate and why>"
}}""")


def generate_recommendation(category: str, frameworks: dict, spend_data: dict) -> dict:
    ctx = [f"Spend: {_spend_summary(spend_data)}"]

    if "kraljic" in frameworks:
        k = frameworks["kraljic"]["data"]
        ctx.append(f"Kraljic: {k.get('quadrant', '')} — {k.get('recommended_posture', '')}")
    if "swot" in frameworks:
        s = frameworks["swot"]["data"]
        opps = s.get("opportunities", [])
        threats = s.get("threats", [])
        if opps:   ctx.append(f"Top opportunity: {opps[0]}")
        if threats: ctx.append(f"Top threat: {threats[0]}")
    if "levers" in frameworks:
        high = [x for x in frameworks["levers"]["data"].get("levers", []) if x.get("priority") == "High"]
        if high:
            ctx.append(f"Top lever: {high[0].get('lever', '')} ({high[0].get('saving_potential', '')})")

    return _call_claude(f"""Generate a 3-year category strategy recommendation for "{category}" procurement.

{chr(10).join(ctx)}

Return JSON:
{{
  "headline":        "<one compelling strategic headline>",
  "strategic_posture": "<overall stance in 1-2 sentences>",
  "year1_priorities": ["<priority>", "<priority>", "<priority>"],
  "year2_priorities": ["<priority>", "<priority>"],
  "year3_vision":    "<where we want to be in 3 years>",
  "success_metrics": ["<KPI>", "<KPI>", "<KPI>"]
}}""")


# ── Orchestrator ──────────────────────────────────────────────────────────────

def generate_all_frameworks(
    client_name: str,
    category: str,
    icarus_signals: list = None,
    progress_cb=None,
) -> dict:
    """
    Run all 7 framework generators sequentially, save each to SQLite as it
    completes, and call progress_cb(framework_key, step_num, total) after each.
    Returns {framework_key: {data, updated_at}}.
    """
    spend_data = get_category_spend_data(client_name, category)
    results = {}

    steps = [
        ("kraljic", lambda: generate_kraljic(category, spend_data, icarus_signals)),
        ("pestel",  lambda: generate_pestel(category, spend_data, icarus_signals)),
        ("swot",    lambda: generate_swot(category, spend_data, icarus_signals)),
        ("porter",  lambda: generate_porter(category, spend_data, icarus_signals)),
        ("tco",     lambda: generate_tco(category, spend_data)),
        ("levers",  lambda: generate_levers(category, spend_data, icarus_signals)),
    ]
    total = len(steps) + 1  # +1 for recommendation

    for i, (name, fn) in enumerate(steps):
        if progress_cb:
            progress_cb(name, i + 1, total)
        try:
            data = fn()
            save_framework(client_name, category, name, data)
            results[name] = {"data": data, "updated_at": datetime.now(timezone.utc).isoformat()}
        except Exception as e:
            print(f"[CategoryStrategy] {name} error: {e}")

    if progress_cb:
        progress_cb("recommendation", total, total)
    try:
        rec = generate_recommendation(category, results, spend_data)
        save_framework(client_name, category, "recommendation", rec)
        results["recommendation"] = {"data": rec, "updated_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        print(f"[CategoryStrategy] recommendation error: {e}")

    return results
