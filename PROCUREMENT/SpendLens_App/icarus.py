"""
Icarus 🪶 — SpendLens Market Intelligence Agent
On-demand procurement signal detection via news scraping + AI analysis.
Learns from user feedback over time.
"""

import sqlite3
import feedparser
import json
import os
from datetime import datetime, timezone
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# ── JSON helper ───────────────────────────────────────────────────────────────

def _parse_json(raw: str):
    """
    Robustly extract and parse the first well-formed JSON object from a string.
    Uses balanced-brace scanning to avoid greedy-regex issues where Claude
    prefixes the JSON with a prose sentence containing {}.
    """
    import re as _re
    # Strip markdown code fences
    raw = _re.sub(r'^```\w*\s*', '', raw.strip(), flags=_re.MULTILINE)
    raw = _re.sub(r'\s*```\s*$', '', raw, flags=_re.MULTILINE).strip()

    # Find the start of the first JSON object or array
    start = -1
    opener, closer = None, None
    for i, ch in enumerate(raw):
        if ch == '{':
            start, opener, closer = i, '{', '}'
            break
        if ch == '[':
            start, opener, closer = i, '[', ']'
            break
    if start == -1:
        raise ValueError("No JSON object/array found in response")

    # Walk forward counting depth to find the matching close
    depth = 0
    in_str = False
    escape = False
    for i, ch in enumerate(raw[start:], start):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                candidate = raw[start:i + 1]
                return json.loads(candidate)

    raise ValueError("Unbalanced braces — could not extract JSON")


# ── Config ────────────────────────────────────────────────────────────────────

ICARUS_DB = "clients/default/icarus_memory.db"

# RSS feeds mapped to the spend categories they influence
RSS_SOURCES = [
    {
        "name": "Reuters Business",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "categories": ["Cloud & Compute", "Hardware & Equipment", "Facilities & Office",
                       "Professional Services", "Recruitment & HR", "Marketing & Campaigns"],
    },
    {
        "name": "Reuters Technology",
        "url": "https://feeds.reuters.com/reuters/technologyNews",
        "categories": ["Cloud & Compute", "Hardware & Equipment", "IT Software & SaaS",
                       "AI/ML APIs & Data", "Telecom & Voice"],
    },
    {
        "name": "The Register",
        "url": "https://www.theregister.com/headlines.atom",
        "categories": ["Cloud & Compute", "Hardware & Equipment", "IT Software & SaaS",
                       "AI/ML APIs & Data", "Telecom & Voice"],
    },
    {
        "name": "Handelsblatt",
        "url": "https://www.handelsblatt.com/contentexport/feed/top-themen",
        "categories": ["Facilities & Office", "Professional Services", "Real Estate",
                       "Recruitment & HR", "Travel & Expenses"],
    },
    {
        "name": "DatacenterDynamics",
        "url": "https://www.datacenterdynamics.com/en/rss/",
        "categories": ["Cloud & Compute", "Facilities & Office", "Hardware & Equipment"],
    },
    {
        "name": "Euractiv",
        "url": "https://www.euractiv.com/feed/",
        "categories": ["Facilities & Office", "Professional Services", "Real Estate", "Travel & Expenses"],
    },
    {
        "name": "Spend Matters",
        "url": "https://spendmatters.com/feed/",
        "categories": ["Professional Services", "IT Software & SaaS", "Recruitment & HR",
                       "Marketing & Campaigns"],
    },
    {
        "name": "FreelancerMap",
        "url": "https://www.freelancermap.de/blog/feed/",
        "categories": ["Recruitment & HR"],
    },
    {
        "name": "Business Travel News",
        "url": "https://www.businesstravelnews.com/rss",
        "categories": ["Travel & Expenses"],
    },
]

# ── Database ──────────────────────────────────────────────────────────────────

def init_db():
    """Initialize Icarus memory database."""
    os.makedirs(os.path.dirname(ICARUS_DB), exist_ok=True)
    conn = sqlite3.connect(ICARUS_DB)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            categories  TEXT NOT NULL,       -- JSON list of categories queried
            article_count INTEGER,
            signal_count  INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id    INTEGER REFERENCES queries(id),
            timestamp   TEXT NOT NULL,
            published   TEXT,                -- article publish date from RSS
            source      TEXT NOT NULL,
            headline    TEXT NOT NULL,
            summary     TEXT NOT NULL,
            category    TEXT NOT NULL,
            relevance   INTEGER NOT NULL,    -- 1-10 score from Claude
            impact      TEXT NOT NULL,       -- 'positive' | 'negative' | 'neutral'
            action      TEXT,                -- suggested procurement action
            url         TEXT,
            feedback    TEXT                 -- 'relevant' | 'not_relevant' | NULL
        )
    """)
    # migration: add published column if DB already exists without it
    try:
        c.execute("ALTER TABLE signals ADD COLUMN published TEXT")
        conn.commit()
    except Exception:
        pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS category_weights (
            category    TEXT PRIMARY KEY,
            weight      REAL DEFAULT 1.0,    -- learned preference weight
            interactions INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def save_query(categories, article_count, signal_count):
    """Save a query run to memory."""
    conn = sqlite3.connect(ICARUS_DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO queries (timestamp, categories, article_count, signal_count) VALUES (?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), json.dumps(categories), article_count, signal_count)
    )
    query_id = c.lastrowid
    conn.commit()
    conn.close()
    return query_id


def save_signals(query_id, signals):
    """Persist signals from a query run."""
    conn = sqlite3.connect(ICARUS_DB)
    c = conn.cursor()
    for s in signals:
        c.execute("""
            INSERT INTO signals
            (query_id, timestamp, published, source, headline, summary,
             category, relevance, impact, action, url)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            query_id,
            datetime.now(timezone.utc).isoformat(),
            s.get("published"),
            s.get("source"), s.get("headline"), s.get("summary"),
            s.get("category"), s.get("relevance"), s.get("impact"),
            s.get("action"), s.get("url")
        ))
    conn.commit()
    conn.close()


def record_feedback(signal_id, feedback):
    """
    Record user feedback on a signal: 'relevant' or 'not_relevant'.
    Updates category weights so Icarus learns over time.
    """
    conn = sqlite3.connect(ICARUS_DB)
    c = conn.cursor()

    # Save feedback on signal
    c.execute("UPDATE signals SET feedback = ? WHERE id = ?", (feedback, signal_id))

    # Get category for this signal
    c.execute("SELECT category FROM signals WHERE id = ?", (signal_id,))
    row = c.fetchone()
    if row:
        category = row[0]
        delta = 0.1 if feedback == "relevant" else -0.05

        # Upsert weight
        c.execute("""
            INSERT INTO category_weights (category, weight, interactions)
            VALUES (?, MAX(0.1, 1.0 + ?), 1)
            ON CONFLICT(category) DO UPDATE SET
                weight = MAX(0.1, weight + ?),
                interactions = interactions + 1
        """, (category, delta, delta))

    conn.commit()
    conn.close()


def get_category_weights():
    """Return learned weights per category."""
    conn = sqlite3.connect(ICARUS_DB)
    c = conn.cursor()
    c.execute("SELECT category, weight FROM category_weights")
    weights = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return weights


def get_recent_signals(limit=20):
    """Fetch most recent signals from memory for dashboard display."""
    init_db()  # ensures published column exists
    conn = sqlite3.connect(ICARUS_DB)
    c = conn.cursor()
    c.execute("""
        SELECT id, timestamp, published, source, headline, summary, category,
               relevance, impact, action, url, feedback
        FROM signals
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    cols = ["id","timestamp","published","source","headline","summary","category",
            "relevance","impact","action","url","feedback"]
    rows = [dict(zip(cols, row)) for row in c.fetchall()]
    conn.close()
    return rows


# ── Scraping ──────────────────────────────────────────────────────────────────

def fetch_articles(client_categories):
    """
    Fetch articles from RSS feeds relevant to client's spend categories.
    Returns list of dicts: {source, headline, summary, url, categories}
    """
    articles = []
    client_cat_set = set(client_categories)

    for feed_cfg in RSS_SOURCES:
        # Only fetch from sources that overlap with client's categories
        relevant = client_cat_set.intersection(set(feed_cfg["categories"]))
        if not relevant:
            continue

        try:
            feed = feedparser.parse(
                feed_cfg["url"],
                agent="Mozilla/5.0 (compatible; SpendLens/1.0; procurement intelligence)"
            )
            if not feed.entries:
                continue
            for entry in feed.entries[:10]:  # max 10 per source
                    # extract publish date
                    pub_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
                    if pub_parsed:
                        from datetime import datetime as _dt
                        pub_str = _dt(*pub_parsed[:6], tzinfo=timezone.utc).isoformat()
                    else:
                        pub_str = datetime.now(timezone.utc).isoformat()
                    articles.append({
                        "source": feed_cfg["name"],
                        "headline": entry.get("title", ""),
                        "summary": entry.get("summary", entry.get("description", ""))[:500],
                        "url": entry.get("link", ""),
                        "relevant_categories": list(relevant),
                        "published": pub_str,
                    })
        except Exception as e:
            print(f"[Icarus] Feed error ({feed_cfg['name']}): {e}")

    # Deduplicate by headline (same story picked up by multiple feeds)
    seen_headlines: set = set()
    unique: list = []
    for a in articles:
        key = a["headline"].strip().lower()
        if key and key not in seen_headlines:
            seen_headlines.add(key)
            unique.append(a)
    return unique


# ── Analysis ──────────────────────────────────────────────────────────────────

def analyze_with_claude(articles, client_categories, client_name="the client"):
    """
    Send articles to Claude API for relevance scoring and signal extraction.
    Returns structured list of signals.
    """
    if not articles:
        return []

    client = Anthropic()

    articles_text = "\n\n".join([
        f"SOURCE: {a['source']}\nDATE: {a.get('published','')[:10]}\nHEADLINE: {a['headline']}\nSUMMARY: {a['summary']}\nURL: {a['url']}\nCATEGORIES: {', '.join(a['relevant_categories'])}"
        for a in articles
    ])

    prompt = f"""You are Icarus, a procurement intelligence agent for SpendLens.

The client ({client_name}) has spend in these categories: {', '.join(client_categories)}

Below are recent news articles. Analyze each one and extract procurement signals.

For each article that is genuinely relevant to procurement decisions, return a signal.
Skip articles that are not relevant to procurement or cost management.

Return ONLY a JSON array (no markdown, no preamble). Each signal object must have:
- "source": string — news source name
- "headline": string — original headline
- "summary": string — 2-3 sentence summary focused on procurement impact
- "category": string — the most relevant spend category from the client's list
- "relevance": integer 1-10 — how actionable is this for procurement?
- "impact": string — "positive", "negative", or "neutral" (for procurement costs/risk)
- "action": string — one concrete suggested action for the procurement team
- "url": string — article URL
- "published": string — article date (YYYY-MM-DD)

Articles:
{articles_text}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        signals = json.loads(raw.strip())
        return signals if isinstance(signals, list) else []
    except Exception as e:
        print(f"[Icarus] Claude API error: {e}")
        return []


# ── Targeted query ────────────────────────────────────────────────────────────

def query_with_claude(query: str, client_categories: list, client_name: str = "Client") -> dict:
    """
    Answer a specific procurement question using recent signals + fresh articles.
    Returns {"answer": str, "signals": list}.
    """
    init_db()
    client_api = Anthropic()

    # Context from memory
    recent = get_recent_signals(limit=30)
    ctx = "\n".join(
        f"- [{s['category']}] {s['headline']} → {s.get('action','')}"
        for s in recent
    ) if recent else "No stored signals yet."

    # Fresh headlines for context
    articles = fetch_articles(client_categories)
    art_text = "\n".join(
        f"- {a['headline']} ({a['source']}, {a.get('published','')[:10]})"
        for a in articles[:25]
    )

    prompt = (
        f"You are Icarus, a procurement intelligence agent for SpendLens.\n\n"
        f"Client: {client_name}\n"
        f"Spend categories: {', '.join(client_categories)}\n\n"
        f"User question: {query}\n\n"
        f"Stored signals (context):\n{ctx}\n\n"
        f"Recent headlines:\n{art_text}\n\n"
        "Answer the question in 3-5 sentences with concrete recommendations for the procurement team. "
        "Then return the 3-5 most relevant signals.\n\n"
        "Return ONLY valid JSON, no markdown, no extra text:\n"
        '{"answer": "...", "signals": [{"headline": "...", "category": "...", '
        '"relevance": 8, "impact": "negative", "action": "...", "source": "...", '
        '"url": "...", "published": "YYYY-MM-DD", "summary": "..."}]}'
    )

    try:
        resp = client_api.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        return _parse_json(raw)
    except Exception as e:
        print(f"[Icarus] query_with_claude error: {type(e).__name__}: {e}")
        return {"answer": "Analysis error – please try again.", "signals": []}


# ── Weekly summary ────────────────────────────────────────────────────────────

def weekly_summary(client_categories: list, client_name: str = "Client") -> dict:
    """
    Generate a structured weekly procurement intelligence brief from stored signals.
    Returns a dict with week, headline, top_risks, top_opportunities, actions,
    category_highlights, signals.
    """
    from datetime import timedelta
    init_db()
    client_api = Anthropic()

    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    conn = sqlite3.connect(ICARUS_DB)
    c = conn.cursor()
    c.execute("""
        SELECT source, headline, category, relevance, impact, action, summary, published
        FROM signals WHERE timestamp > ?
        ORDER BY relevance DESC LIMIT 50
    """, (week_ago,))
    cols = ["source","headline","category","relevance","impact","action","summary","published"]
    week_signals = [dict(zip(cols, row)) for row in c.fetchall()]
    conn.close()

    if not week_signals:
        week_signals = get_recent_signals(limit=30)

    week_label = datetime.now(timezone.utc).strftime("Week of %B %d, %Y")
    if not week_signals:
        return {"week": week_label, "headline": "No signals found. Run a scan first.",
                "top_risks": [], "top_opportunities": [], "actions": [],
                "category_highlights": {}, "signals": []}

    signals_text = "\n".join(
        f"[{s.get('category','?')}] {s.get('headline','')} "
        f"(Impact: {s.get('impact','?')}, Relevance: {s.get('relevance','?')}/10)\n  → {s.get('action','')}"
        for s in week_signals[:30]
    )

    prompt = f"""You are Icarus, a procurement intelligence agent for SpendLens.
Client: {client_name}
Spend Categories: {', '.join(client_categories)}

Generate a concise weekly procurement intelligence brief for {week_label}.

Signals from the past 7 days:
{signals_text}

Return ONLY valid JSON (no markdown, no extra text):
{{
  "week": "{week_label}",
  "headline": "one sentence executive summary of the week",
  "top_risks": ["risk 1", "risk 2", "risk 3"],
  "top_opportunities": ["opportunity 1", "opportunity 2"],
  "actions": ["priority action 1", "priority action 2", "priority action 3"],
  "category_highlights": {{
    "Category Name": "one sentence key insight"
  }},
  "signals": [
    {{"headline": "...", "category": "...", "impact": "...", "action": "..."}}
  ]
}}"""

    try:
        resp = client_api.messages.create(
            model="claude-sonnet-4-6", max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        print(f"[Icarus] weekly_summary raw ({len(raw)} chars): {raw[:300]}")
        data = _parse_json(raw)
        if not data.get("signals"):
            data["signals"] = [{"headline": s["headline"], "category": s["category"],
                                 "impact": s["impact"], "action": s["action"]}
                                for s in week_signals[:5]]
        return data
    except Exception as e:
        print(f"[Icarus] weekly_summary error: {type(e).__name__}: {e}")
        return {"week": week_label, "headline": "Summary generation failed – please try again.",
                "top_risks": [], "top_opportunities": [], "actions": [],
                "category_highlights": {}, "signals": week_signals[:5]}


# ── RFP / negotiation brief ───────────────────────────────────────────────────

def generate_rfp_brief(query: str, client_categories: list, client_name: str = "Client") -> dict:
    """
    Generate a structured procurement negotiation brief / RFP preparation.
    Detects topic from query, uses stored signals as market context.
    Returns dict with title, executive_summary, market_context, negotiation_levers,
    key_requirements, risk_areas, suggested_terms, next_steps.
    """
    init_db()
    client_api = Anthropic()

    recent = get_recent_signals(limit=40)
    ctx = "\n".join(
        f"- [{s['category']}] {s['headline']}: {s.get('action','')}"
        for s in recent
    ) if recent else "No stored signals."

    prompt = f"""You are Icarus, a senior procurement intelligence agent for SpendLens.
Client: {client_name}
Spend Categories: {', '.join(client_categories)}
Request: {query}

Based on current market signals, prepare a procurement negotiation brief and RFP preparation document.

Market Intelligence Context:
{ctx}

Return ONLY valid JSON (no markdown, no extra text):
{{
  "title": "RFP / Negotiation Brief: [specific topic]",
  "executive_summary": "2-3 sentences summarising market position and recommended approach",
  "market_context": ["key market fact 1", "key market fact 2", "key market fact 3"],
  "negotiation_levers": ["lever 1 with rationale", "lever 2 with rationale", "lever 3 with rationale"],
  "key_requirements": ["must-have requirement 1", "must-have requirement 2", "must-have requirement 3"],
  "risk_areas": ["risk 1", "risk 2"],
  "suggested_terms": ["suggested contractual term 1", "suggested contractual term 2", "suggested contractual term 3"],
  "next_steps": ["immediate action 1", "immediate action 2", "immediate action 3"]
}}"""

    try:
        resp = client_api.messages.create(
            model="claude-sonnet-4-6", max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        print(f"[Icarus] generate_rfp_brief raw ({len(raw)} chars): {raw[:300]}")
        return _parse_json(raw)
    except Exception as e:
        print(f"[Icarus] generate_rfp_brief error: {type(e).__name__}: {e}")
        return {"title": "RFP Brief", "executive_summary": "Generation failed – please try again.",
                "market_context": [], "negotiation_levers": [], "key_requirements": [],
                "risk_areas": [], "suggested_terms": [], "next_steps": []}


# ── Main entry point ──────────────────────────────────────────────────────────

def run(client_categories=None, client_name="Client"):
    """
    Main Icarus function — called by the dashboard when user clicks 'Ask Icarus'.
    
    Args:
        client_categories: list of spend category names active for this client
        client_name: display name for the client
    
    Returns:
        dict with keys: signals (list), query_id (int), article_count (int)
    """
    init_db()

    if not client_categories:
        client_categories = [
            "Cloud & Compute", "Software & SaaS", "Professional Services",
            "Hardware", "Facilities", "Logistics"
        ]

    print(f"[Icarus 🪶] Scanning feeds for: {', '.join(client_categories)}")

    # 1. Fetch articles
    articles = fetch_articles(client_categories)
    print(f"[Icarus] Fetched {len(articles)} articles from {len(RSS_SOURCES)} sources")

    # 2. Analyze with Claude
    signals = analyze_with_claude(articles, client_categories, client_name)
    # Deduplicate signals by headline
    seen_sig: set = set()
    deduped: list = []
    for s in signals:
        key = s.get("headline", "").strip().lower()
        if key and key not in seen_sig:
            seen_sig.add(key)
            deduped.append(s)
    signals = deduped
    print(f"[Icarus] Extracted {len(signals)} signals (after dedup)")

    # 3. Back-fill published date from article lookup
    url_to_pub = {a["url"]: a.get("published", "") for a in articles}
    for s in signals:
        if not s.get("published"):
            s["published"] = url_to_pub.get(s.get("url", ""), "")

    # 4. Apply learned weights — re-sort by (relevance × category_weight)
    weights = get_category_weights()
    for s in signals:
        w = weights.get(s.get("category", ""), 1.0)
        s["weighted_score"] = round(s.get("relevance", 5) * w, 2)
    signals.sort(key=lambda x: x["weighted_score"], reverse=True)

    # 4. Save to memory
    query_id = save_query(client_categories, len(articles), len(signals))
    save_signals(query_id, signals)
    print(f"[Icarus] Saved to memory as query #{query_id}")

    return {
        "query_id": query_id,
        "article_count": len(articles),
        "signals": signals,
    }


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = run(
        client_categories=["Cloud & Compute", "Hardware", "Facilities", "Professional Services"],
        client_name="Test Client"
    )
    print(f"\n{'─'*60}")
    print(f"🪶 Icarus returned {len(result['signals'])} signals from {result['article_count']} articles\n")
    for s in result["signals"][:5]:
        impact_icon = {"positive": "📈", "negative": "📉", "neutral": "➡️"}.get(s.get("impact"), "•")
        print(f"{impact_icon} [{s.get('category')}] {s.get('headline')}")
        print(f"   → {s.get('action')}")
        print(f"   Relevance: {s.get('relevance')}/10 | Score: {s.get('weighted_score')}")
        print()
