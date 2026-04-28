"""
Icarus 🪶 — SpendLens Market Intelligence Agent
On-demand procurement signal detection via news scraping + AI analysis.
Learns from user feedback over time.
"""

import sqlite3
import feedparser
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    # ── General business & tech news ──────────────────────────────────────────
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
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "categories": ["Cloud & Compute", "AI/ML APIs & Data", "IT Software & SaaS",
                       "Hardware & Equipment"],
    },
    {
        "name": "ZDNet",
        "url": "https://www.zdnet.com/news/rss.xml",
        "categories": ["Cloud & Compute", "IT Software & SaaS", "AI/ML APIs & Data",
                       "Telecom & Voice", "Hardware & Equipment"],
    },
    # ── Procurement & supply chain ────────────────────────────────────────────
    {
        "name": "Spend Matters",
        "url": "https://spendmatters.com/feed/",
        "categories": ["Professional Services", "IT Software & SaaS", "Recruitment & HR",
                       "Marketing & Campaigns"],
    },
    {
        "name": "Supply Chain Dive",
        "url": "https://www.supplychaindive.com/feeds/news/",
        "categories": ["Hardware & Equipment", "Facilities & Office", "Professional Services",
                       "Cloud & Compute", "Recruitment & HR"],
    },
    {
        "name": "Supply Chain Brain",
        "url": "https://www.supplychainbrain.com/rss/allnews.aspx",
        "categories": ["Hardware & Equipment", "Facilities & Office", "Professional Services",
                       "Travel & Expenses"],
    },
    {
        "name": "CPO Rising (Ardent Partners)",
        "url": "https://cporising.com/feed/",
        "categories": ["Professional Services", "IT Software & SaaS", "Recruitment & HR",
                       "Cloud & Compute", "Marketing & Campaigns", "Hardware & Equipment",
                       "Facilities & Office", "Travel & Expenses"],
    },
    # ── European & German business ────────────────────────────────────────────
    {
        "name": "Handelsblatt",
        "url": "https://www.handelsblatt.com/contentexport/feed/top-themen",
        "categories": ["Facilities & Office", "Professional Services", "Real Estate",
                       "Recruitment & HR", "Travel & Expenses"],
    },
    {
        "name": "WirtschaftsWoche",
        "url": "https://www.wiwo.de/rss/feed/",
        "categories": ["Professional Services", "Real Estate", "Recruitment & HR",
                       "Facilities & Office", "Travel & Expenses"],
    },
    {
        "name": "Euractiv",
        "url": "https://www.euractiv.com/feed/",
        "categories": ["Facilities & Office", "Professional Services", "Real Estate", "Travel & Expenses"],
    },
    # ── Infrastructure & data centres ─────────────────────────────────────────
    {
        "name": "DatacenterDynamics",
        "url": "https://www.datacenterdynamics.com/en/rss/",
        "categories": ["Cloud & Compute", "Facilities & Office", "Hardware & Equipment"],
    },
    # ── Commodity & energy pricing ────────────────────────────────────────────
    {
        "name": "OilPrice",
        "url": "https://oilprice.com/rss/main",
        "categories": ["Facilities & Office", "Travel & Expenses", "Hardware & Equipment"],
    },
    # ── HR & freelancer markets ───────────────────────────────────────────────
    {
        "name": "FreelancerMap",
        "url": "https://www.freelancermap.de/blog/feed/",
        "categories": ["Recruitment & HR"],
    },
    # ── Travel ────────────────────────────────────────────────────────────────
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
    """Persist signals from a query run, skipping any URL already stored today."""
    conn = sqlite3.connect(ICARUS_DB)
    c = conn.cursor()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for s in signals:
        url = s.get("url") or ""
        if url:
            c.execute(
                "SELECT 1 FROM signals WHERE url = ? AND timestamp LIKE ? LIMIT 1",
                (url, f"{today}%"),
            )
            if c.fetchone():
                continue  # already stored today — skip
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
    # Dedup in-Python so stale DB duplicates never reach the UI
    seen_urls: set = set()
    seen_heads: set = set()
    unique: list = []
    for row in rows:
        url  = (row.get("url") or "").strip()
        head = (row.get("headline") or "").strip().lower()
        if url and url in seen_urls:
            continue
        if head and head in seen_heads:
            continue
        if url:
            seen_urls.add(url)
        if head:
            seen_heads.add(head)
        unique.append(row)
    return unique


# ── Document text extraction (in-memory only — nothing written to disk) ───────

def extract_text(filename: str, content: bytes) -> str:
    """
    Extract plain text from uploaded file bytes.
    Supports PDF (pypdf), DOCX (python-docx), XLSX (pandas), TXT/CSV (utf-8).
    Documents are kept in memory only and never persisted to disk.
    """
    import io
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "txt"

    if ext in ("txt", "csv", "md"):
        return content.decode("utf-8", errors="replace")

    if ext == "pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("pypdf not installed — run: pip install pypdf")
        reader = PdfReader(io.BytesIO(content))
        pages = [p.extract_text() or "" for p in reader.pages]
        return "\n\n".join(t for t in pages if t.strip())

    if ext == "docx":
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx not installed — run: pip install python-docx")
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if ext in ("xlsx", "xls"):
        import pandas as pd
        df = pd.read_excel(io.BytesIO(content))
        return df.to_string(index=False)

    return content.decode("utf-8", errors="replace")


# ── Grok live-search ──────────────────────────────────────────────────────────
# Groups the 11 spend categories into 3 topic clusters → 3 Grok calls per scan
# instead of 11. Each call uses xAI live search to surface X posts + breaking news
# that RSS feeds miss (exec announcements, regulatory filings, market moves).

_GROK_CLUSTERS = [
    {
        "name": "Tech & Cloud Procurement",
        "categories": ["Cloud & Compute", "IT Software & SaaS", "AI/ML APIs & Data",
                       "Telecom & Voice", "Hardware & Equipment"],
        "query": (
            "latest news about cloud computing pricing, SaaS vendor consolidation, "
            "AI API costs, semiconductor supply, hardware shortages, telecom regulation — "
            "include insights from Gartner, McKinsey, Deloitte, PwC, KPMG, BCG on IT spend trends. "
            "Anything that affects corporate procurement or IT spend decisions."
        ),
    },
    {
        "name": "People & Professional Services",
        "categories": ["Recruitment & HR", "Professional Services", "Marketing & Campaigns"],
        "query": (
            "latest news about freelancer market, contractor rates, professional services pricing, "
            "consulting firm M&A, marketing agency fees, recruitment costs — "
            "include McKinsey, Deloitte, PwC, KPMG, BCG, Mercer reports on workforce and outsourcing trends. "
            "Anything that affects procurement of external labour and professional services."
        ),
    },
    {
        "name": "Facilities, Real Estate & Travel",
        "categories": ["Facilities & Office", "Real Estate", "Travel & Expenses"],
        "query": (
            "latest news about commercial real estate, office lease rates, corporate travel costs, "
            "airline pricing, hotel rates, facilities management, energy costs for offices — "
            "include JLL, CBRE, Deloitte, PwC real estate and corporate travel outlooks. "
            "Anything relevant to corporate facility and travel procurement."
        ),
    },
    {
        "name": "Procurement Strategy & Regulation",
        "categories": ["Professional Services", "IT Software & SaaS", "Cloud & Compute",
                       "Hardware & Equipment", "Facilities & Office"],
        "query": (
            "latest procurement strategy reports, supply chain risk alerts, vendor concentration risk, "
            "EU AI Act and GDPR implications for software procurement, tariffs and trade policy affecting "
            "corporate spend — include ISM reports, Spend Matters analysis, McKinsey Operations, "
            "Deloitte CFO insights, PwC procurement benchmarks, KPMG supply chain reports."
        ),
    },
]

# ── Scan profiles ─────────────────────────────────────────────────────────────
# small: fast, cheap (~$0.05/scan) — 5 articles per feed, no Grok live search
# big:   thorough (~$0.13/scan)    — 15 articles per feed + all 4 Grok clusters
SCAN_PROFILES = {
    "small": {"articles_per_feed": 5,  "use_grok": False},
    "big":   {"articles_per_feed": 15, "use_grok": True},
}


def _fetch_grok_articles(client_categories: list) -> list:
    """
    Fetch real-time procurement signals via Grok (xAI) live search.
    Queries 3 topic clusters in parallel. Returns articles in the same
    format as _fetch_feed() so they flow into Haiku batch analysis unchanged.
    Silently returns [] if XAI_API_KEY is not set or any call fails.
    """
    api_key = os.environ.get("XAI_API_KEY", "")
    if not api_key:
        return []

    try:
        from openai import OpenAI as _OAI
    except ImportError:
        print("[Icarus] openai SDK not installed — pip install openai to enable Grok")
        return []

    client_cat_set = set(client_categories)
    grok = _OAI(api_key=api_key, base_url="https://api.x.ai/v1")

    def _query_cluster(cluster):
        relevant = client_cat_set.intersection(set(cluster["categories"]))
        if not relevant:
            return []

        prompt = (
            "You are a procurement intelligence analyst with access to live news and social media.\n"
            f"Search for the 5 most recent (last 7 days) high-impact news items about:\n{cluster['query']}\n\n"
            "Prioritise: price shocks, supply disruptions, M&A, regulatory changes, executive statements.\n\n"
            "Return ONLY a JSON array, no other text:\n"
            '[{"headline":"...","summary":"max 120 chars","url":"https://...","source":"publisher","published":"YYYY-MM-DD"}]'
        )

        try:
            resp = grok.responses.create(
                model="grok-3-mini",
                input=[{"role": "user", "content": prompt}],
                tools=[{"type": "web_search"}],
            )
            raw = resp.output_text or ""
            items = _parse_json(raw)
            if not isinstance(items, list):
                return []

            articles = []
            for item in items:
                if not isinstance(item, dict) or not item.get("headline"):
                    continue
                articles.append({
                    "source":               f"Grok · {item.get('source', cluster['name'])}",
                    "headline":             str(item.get("headline", ""))[:200],
                    "summary":              str(item.get("summary", ""))[:500],
                    "url":                  item.get("url", ""),
                    "relevant_categories":  list(relevant),
                    "published":            item.get(
                        "published",
                        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    ),
                })
            return articles

        except Exception as e:
            print(f"[Icarus] Grok cluster error ({cluster['name']}): {e}")
            return []

    results = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for cluster_articles in ex.map(_query_cluster, _GROK_CLUSTERS):
            results.extend(cluster_articles)

    if results:
        print(f"[Icarus] Grok live search: {len(results)} articles fetched")
    return results


# ── Scraping ──────────────────────────────────────────────────────────────────

def fetch_articles(client_categories, mode="small"):
    """
    Fetch articles from RSS feeds relevant to client's spend categories.
    mode="small": 5 articles/feed, no Grok (~$0.05/scan, ~8s)
    mode="big":   15 articles/feed + all Grok clusters (~$0.13/scan, ~12s)
    All feeds are fetched in parallel. Returns deduplicated list of article dicts.
    """
    profile   = SCAN_PROFILES.get(mode, SCAN_PROFILES["small"])
    per_feed  = profile["articles_per_feed"]
    use_grok  = profile["use_grok"]
    client_cat_set = set(client_categories)

    def _fetch_feed(feed_cfg):
        relevant = client_cat_set.intersection(set(feed_cfg["categories"]))
        if not relevant:
            return []
        try:
            feed = feedparser.parse(
                feed_cfg["url"],
                agent="Mozilla/5.0 (compatible; SpendLens/1.0; procurement intelligence)"
            )
            results = []
            for entry in feed.entries[:per_feed]:
                pub_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub_parsed:
                    pub_str = datetime(*pub_parsed[:6], tzinfo=timezone.utc).isoformat()
                else:
                    pub_str = datetime.now(timezone.utc).isoformat()
                results.append({
                    "source": feed_cfg["name"],
                    "headline": entry.get("title", ""),
                    "summary": entry.get("summary", entry.get("description", ""))[:500],
                    "url": entry.get("link", ""),
                    "relevant_categories": list(relevant),
                    "published": pub_str,
                })
            return results
        except Exception as e:
            print(f"[Icarus] Feed error ({feed_cfg['name']}): {e}")
            return []

    # Fetch RSS feeds; optionally also run Grok live-search concurrently.
    articles = []
    grok_result: list = []

    if use_grok:
        def _run_grok():
            grok_result.extend(_fetch_grok_articles(client_categories))
        grok_thread = threading.Thread(target=_run_grok, daemon=True)
        grok_thread.start()

    with ThreadPoolExecutor(max_workers=len(RSS_SOURCES)) as executor:
        for feed_articles in executor.map(_fetch_feed, RSS_SOURCES):
            articles.extend(feed_articles)

    if use_grok:
        grok_thread.join(timeout=25)
        articles.extend(grok_result)

    # Deduplicate by URL first, then headline
    seen_urls: set = set()
    seen_heads: set = set()
    unique: list = []
    for a in articles:
        url  = (a.get("url") or "").strip()
        head = a.get("headline", "").strip().lower()
        if url and url in seen_urls:
            continue
        if head and head in seen_heads:
            continue
        if url:
            seen_urls.add(url)
        if head:
            seen_heads.add(head)
        unique.append(a)
    return unique


# ── Analysis ──────────────────────────────────────────────────────────────────

_ANALYSIS_BATCH_SIZE = 15  # articles per Claude call
_ANALYSIS_WORKERS    = 5   # parallel Claude calls

def _analyze_batch(batch, client_categories, client_name):
    """Analyze a single batch of articles with Haiku (fast, structured extraction)."""
    articles_text = "\n\n".join(
        f"SOURCE: {a['source']}\nDATE: {a.get('published','')[:10]}\n"
        f"HEADLINE: {a['headline']}\nSUMMARY: {a['summary']}\n"
        f"URL: {a['url']}\nCATEGORIES: {', '.join(a['relevant_categories'])}"
        for a in batch
    )
    prompt = (
        f"You are Icarus, a procurement intelligence agent.\n"
        f"Client spend categories: {', '.join(client_categories)}\n\n"
        "Analyze each article below. For each one relevant to procurement decisions, "
        "return a signal. Skip irrelevant articles.\n\n"
        "Return ONLY a JSON array. Each object must have:\n"
        '"source", "headline", "summary" (2-3 sentences on procurement impact), '
        '"category" (from client list), "relevance" (1-10 int), '
        '"impact" ("positive"|"negative"|"neutral"), "action" (one concrete action), '
        '"url", "published" (YYYY-MM-DD)\n\n'
        f"Articles:\n{articles_text}"
    )
    try:
        client = Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_json(resp.content[0].text.strip())
    except Exception as e:
        print(f"[Icarus] batch analysis error: {e}")
        return []


def analyze_with_claude(articles, client_categories, client_name="the client"):
    """
    Batch articles into groups of _ANALYSIS_BATCH_SIZE and analyze all batches
    in parallel using Haiku. ~5x faster than a single sequential Sonnet call.
    """
    if not articles:
        return []

    batches = [articles[i:i + _ANALYSIS_BATCH_SIZE]
               for i in range(0, len(articles), _ANALYSIS_BATCH_SIZE)]

    all_signals = []
    with ThreadPoolExecutor(max_workers=_ANALYSIS_WORKERS) as executor:
        futures = {
            executor.submit(_analyze_batch, batch, client_categories, client_name): i
            for i, batch in enumerate(batches)
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                if isinstance(result, list):
                    all_signals.extend(result)
            except Exception as e:
                print(f"[Icarus] batch future error: {e}")

    return all_signals


# ── Targeted query ────────────────────────────────────────────────────────────

def query_with_claude(query: str, client_categories: list, client_name: str = "Client",
                      doc_context: list = None) -> dict:
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

    # Fresh headlines — pre-filtered by query keyword overlap
    articles = fetch_articles(client_categories)
    query_words = {w for w in query.lower().split() if len(w) > 3}
    if query_words:
        def _matches(a):
            text = (a.get("headline", "") + " " + a.get("summary", "")).lower()
            return any(w in text for w in query_words)
        filtered = [a for a in articles if _matches(a)]
        articles = filtered if len(filtered) >= 5 else articles
    art_text = "\n".join(
        f"- {a['headline']} ({a['source']}, {a.get('published','')[:10]})"
        for a in articles[:25]
    )

    doc_section = ""
    if doc_context:
        doc_section = "\n\nUploaded contracts / documents (reference these directly):\n"
        for i, doc in enumerate(doc_context, 1):
            doc_section += f"\n--- Document {i} ---\n{doc}\n"

    prompt = (
        f"You are Icarus, a procurement intelligence agent for SpendLens.\n\n"
        f"Client: {client_name}\n"
        f"Spend categories: {', '.join(client_categories)}\n\n"
        f"User question: {query}\n"
        f"{doc_section}\n"
        f"Stored signals (context):\n{ctx}\n\n"
        f"Recent headlines:\n{art_text}\n\n"
        "Answer the question in 3-5 sentences with concrete recommendations for the procurement team. "
        "Where documents are provided, reference specific clauses or figures. "
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
            model="claude-sonnet-4-6", max_tokens=3000,
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

def generate_rfp_brief(query: str, client_categories: list, client_name: str = "Client",
                       doc_context: list = None) -> dict:
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

    doc_section = ""
    if doc_context:
        doc_section = "\n\nUploaded contracts / documents (treat as primary reference — extract specific terms, prices, clauses):\n"
        for i, doc in enumerate(doc_context, 1):
            doc_section += f"\n--- Document {i} ---\n{doc}\n"

    prompt = f"""You are Icarus, a senior procurement intelligence agent for SpendLens.
Client: {client_name}
Spend Categories: {', '.join(client_categories)}
Request: {query}
{doc_section}
Market intelligence context (current signals from news sources):
{ctx}

Based on the uploaded documents (where provided) and current market signals, prepare a detailed procurement negotiation brief and RFP preparation. Reference specific contract terms, prices, or clauses from the documents where relevant.

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
            model="claude-sonnet-4-6", max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp.content[0].text.strip()
        print(f"[Icarus] generate_rfp_brief raw ({len(raw)} chars): {raw[:400]}")
        try:
            return _parse_json(raw)
        except Exception as parse_err:
            print(f"[Icarus] JSON parse failed ({parse_err}), returning raw text")
            # Fall back: return the raw text as executive summary so the user sees something
            return {
                "title": f"Negotiation Brief",
                "executive_summary": raw[:3000],
                "market_context": [], "negotiation_levers": [],
                "key_requirements": [], "risk_areas": [],
                "suggested_terms": [], "next_steps": [],
            }
    except Exception as e:
        print(f"[Icarus] generate_rfp_brief error: {type(e).__name__}: {e}")
        return {"title": "RFP Brief",
                "executive_summary": f"Generation error: {type(e).__name__} – {e}",
                "market_context": [], "negotiation_levers": [], "key_requirements": [],
                "risk_areas": [], "suggested_terms": [], "next_steps": []}


# ── Document summarisation ───────────────────────────────────────────────────

def summarize_doc(filename: str, text: str) -> str:
    """
    Summarise a document with Haiku in ~800 tokens.
    Focuses on procurement-relevant content: prices, dates, vendors,
    contract terms, obligations, renewal/termination clauses.
    Input is capped at 100k chars (~25k tokens) to stay within context.
    """
    truncated = text[:100_000]
    prompt = (
        f"Document: {filename}\n\n{truncated}\n\n"
        "Summarise this document in 600-800 tokens. Focus on: contract terms, "
        "prices and pricing structures, dates (start, end, renewal, termination), "
        "vendor and counterparty names, key obligations, SLAs, and any data "
        "relevant to procurement decisions. Be specific — include actual figures, "
        "names, and dates. Write in plain prose, no headers."
    )
    client = Anthropic()
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


# ── Main entry point ──────────────────────────────────────────────────────────

def run(client_categories=None, client_name="Client", mode="small"):
    """
    Main Icarus scan — called by the dashboard scan buttons.

    Args:
        client_categories: list of spend category names active for this client
        client_name: display name for the client
        mode: "small" (quick, ~$0.05) or "big" (deep, ~$0.13 + Grok)

    Returns:
        dict with keys: signals (list), query_id (int), article_count (int)
    """
    init_db()

    if not client_categories:
        client_categories = [
            "Cloud & Compute", "Software & SaaS", "Professional Services",
            "Hardware", "Facilities", "Logistics"
        ]

    print(f"[Icarus 🪶] Scanning feeds ({mode}) for: {', '.join(client_categories)}")

    # 1. Fetch articles
    articles = fetch_articles(client_categories, mode=mode)
    print(f"[Icarus] Fetched {len(articles)} articles from {len(RSS_SOURCES)} sources (mode={mode})")

    # 2. Analyze with Claude
    signals = analyze_with_claude(articles, client_categories, client_name)
    # Deduplicate by URL first (canonical), then by normalised headline as fallback.
    # Claude sometimes rephrases headlines slightly, so headline-only dedup misses dupes.
    seen_urls: set = set()
    seen_heads: set = set()
    deduped: list = []
    for s in signals:
        url  = (s.get("url") or "").strip()
        head = s.get("headline", "").strip().lower()
        url_key  = url  if url  else None
        head_key = head if head else None
        if url_key and url_key in seen_urls:
            continue
        if head_key and head_key in seen_heads:
            continue
        if url_key:
            seen_urls.add(url_key)
        if head_key:
            seen_heads.add(head_key)
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
        client_categories=[
            "Cloud & Compute", "AI/ML APIs & Data", "IT Software & SaaS", "Telecom & Voice",
            "Recruitment & HR", "Professional Services", "Marketing & Campaigns",
            "Facilities & Office", "Real Estate", "Hardware & Equipment", "Travel & Expenses",
        ],
        client_name="SpendLens",
        mode="big",
    )
    print(f"\n{'─'*60}")
    print(f"🪶 Icarus returned {len(result['signals'])} signals from {result['article_count']} articles\n")
    for s in result["signals"][:5]:
        impact_icon = {"positive": "📈", "negative": "📉", "neutral": "➡️"}.get(s.get("impact"), "•")
        print(f"{impact_icon} [{s.get('category')}] {s.get('headline')}")
        print(f"   → {s.get('action')}")
        print(f"   Relevance: {s.get('relevance')}/10 | Score: {s.get('weighted_score')}")
        print()
