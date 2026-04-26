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

# ── Config ────────────────────────────────────────────────────────────────────

ICARUS_DB = "clients/default/icarus_memory.db"

# RSS feeds mapped to the spend categories they influence
RSS_SOURCES = [
    {
        "name": "Reuters Business",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "categories": ["Cloud & Compute", "Hardware", "Facilities", "Logistics", "Professional Services"],
    },
    {
        "name": "Reuters Technology",
        "url": "https://feeds.reuters.com/reuters/technologyNews",
        "categories": ["Cloud & Compute", "Hardware", "Software & SaaS", "AI & ML"],
    },
    {
        "name": "The Register",
        "url": "https://www.theregister.com/headlines.atom",
        "categories": ["Cloud & Compute", "Hardware", "Software & SaaS", "AI & ML", "Telecom"],
    },
    {
        "name": "Handelsblatt",
        "url": "https://www.handelsblatt.com/contentexport/feed/top-themen",
        "categories": ["Facilities", "Professional Services", "Logistics", "Energy"],
    },
    {
        "name": "DatacenterDynamics",
        "url": "https://www.datacenterdynamics.com/en/rss/",
        "categories": ["Cloud & Compute", "Facilities", "Hardware", "Energy"],
    },
    {
        "name": "Euractiv",
        "url": "https://www.euractiv.com/feed/",
        "categories": ["Facilities", "Energy", "Logistics", "Professional Services"],
    },
    {
        "name": "Spend Matters",
        "url": "https://spendmatters.com/feed/",
        "categories": ["Professional Services", "Software & SaaS", "Freelancer & Contractors"],
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
            (query_id, timestamp, source, headline, summary, category, relevance, impact, action, url)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            query_id,
            datetime.now(timezone.utc).isoformat(),
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
    conn = sqlite3.connect(ICARUS_DB)
    c = conn.cursor()
    c.execute("""
        SELECT id, timestamp, source, headline, summary, category, 
               relevance, impact, action, url, feedback
        FROM signals
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    cols = ["id","timestamp","source","headline","summary","category",
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
                articles.append({
                    "source": feed_cfg["name"],
                    "headline": entry.get("title", ""),
                    "summary": entry.get("summary", entry.get("description", ""))[:500],
                    "url": entry.get("link", ""),
                    "relevant_categories": list(relevant),
                })
        except Exception as e:
            print(f"[Icarus] Feed error ({feed_cfg['name']}): {e}")

    return articles


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
        f"SOURCE: {a['source']}\nHEADLINE: {a['headline']}\nSUMMARY: {a['summary']}\nURL: {a['url']}\nCATEGORIES: {', '.join(a['relevant_categories'])}"
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

Articles:
{articles_text}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
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
    print(f"[Icarus] Extracted {len(signals)} signals")

    # 3. Apply learned weights — re-sort by (relevance × category_weight)
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
