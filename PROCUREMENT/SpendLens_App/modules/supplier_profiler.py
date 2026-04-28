"""
supplier_profiler.py — SpendLens Supplier Intelligence & ABC Classification
============================================================================
Computes ABC supplier tiers from spend data, scores each supplier on compliance,
and suggests relationship status based on tier + risk. Feeds the Compliance
Scorecard tab and persists supplier knowledge in supplier_profiles.

ABC logic:
  Base tier from cumulative Pareto spend (A=top 80%, B=next 15%, C=remaining 5%)
  Criticality bump: Critical risk or sole-source → upgrade to A regardless of spend
  tier_override: user-set tier wins and survives every recomputation
"""

import json
import os
import sqlite3
import pandas as pd
from datetime import datetime

# ── Path helpers ──────────────────────────────────────────────────────────────
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE_FILE = os.path.join(_MODULE_DIR, "vendor_cache.json")

TAXONOMY = [
    "Cloud & Compute", "AI/ML APIs & Data", "IT Software & SaaS",
    "Telecom & Voice", "Recruitment & HR", "Professional Services",
    "Marketing & Campaigns", "Facilities & Office", "Real Estate",
    "Hardware & Equipment", "Travel & Expenses",
]

RELATIONSHIP_OPTIONS = ["Strategic", "Preferred", "Approved", "Transactional"]

# ── Demo supplier master (used when no real data is uploaded) ─────────────────
_DEMO_SUPPLIERS = [
    {"vendor_name": "AWS",              "category": "Cloud & Compute",       "total_spend": 18000, "contract_status": "Under Contract", "contract_end": "2026-09-30", "risk_level": "High",     "single_source": False, "po_coverage_pct": 95},
    {"vendor_name": "WeWork GmbH",      "category": "Real Estate",           "total_spend": 3200,  "contract_status": "Under Contract", "contract_end": "2028-12-31", "risk_level": "Low",      "single_source": True,  "po_coverage_pct": 100},
    {"vendor_name": "Google Cloud",     "category": "Cloud & Compute",       "total_spend": 3200,  "contract_status": "Under Contract", "contract_end": "2026-09-30", "risk_level": "High",     "single_source": False, "po_coverage_pct": 90},
    {"vendor_name": "OpenAI",           "category": "AI/ML APIs & Data",     "total_spend": 2800,  "contract_status": "Under Contract", "contract_end": "2026-06-30", "risk_level": "High",     "single_source": False, "po_coverage_pct": 80},
    {"vendor_name": "Google Ads",       "category": "Marketing & Campaigns", "total_spend": 2200,  "contract_status": "No Contract",    "contract_end": "N/A",        "risk_level": "Medium",   "single_source": False, "po_coverage_pct": 45},
    {"vendor_name": "Twilio",           "category": "Telecom & Voice",       "total_spend": 2200,  "contract_status": "Under Contract", "contract_end": "2026-07-31", "risk_level": "Critical", "single_source": True,  "po_coverage_pct": 92},
    {"vendor_name": "Meta Ads",         "category": "Marketing & Campaigns", "total_spend": 1800,  "contract_status": "No Contract",    "contract_end": "N/A",        "risk_level": "Medium",   "single_source": False, "po_coverage_pct": 40},
    {"vendor_name": "ISS Deutschland",  "category": "Facilities & Office",   "total_spend": 1800,  "contract_status": "Under Contract", "contract_end": "2028-06-30", "risk_level": "Low",      "single_source": False, "po_coverage_pct": 70},
    {"vendor_name": "Azure",            "category": "Cloud & Compute",       "total_spend": 1800,  "contract_status": "Under Contract", "contract_end": "2026-09-30", "risk_level": "Medium",   "single_source": False, "po_coverage_pct": 88},
    {"vendor_name": "Hays",             "category": "Recruitment & HR",      "total_spend": 1500,  "contract_status": "Under Contract", "contract_end": "2026-12-31", "risk_level": "Medium",   "single_source": False, "po_coverage_pct": 60},
    {"vendor_name": "Anthropic",        "category": "AI/ML APIs & Data",     "total_spend": 1400,  "contract_status": "Under Contract", "contract_end": "2026-06-30", "risk_level": "High",     "single_source": False, "po_coverage_pct": 75},
    {"vendor_name": "Lufthansa",        "category": "Travel & Expenses",     "total_spend": 1200,  "contract_status": "Under Contract", "contract_end": "2026-09-30", "risk_level": "Low",      "single_source": False, "po_coverage_pct": 40},
    {"vendor_name": "LinkedIn",         "category": "Recruitment & HR",      "total_spend": 1200,  "contract_status": "No Contract",    "contract_end": "N/A",        "risk_level": "Medium",   "single_source": False, "po_coverage_pct": 55},
    {"vendor_name": "Deloitte",         "category": "Professional Services", "total_spend": 1200,  "contract_status": "Expired",        "contract_end": "2026-03-31", "risk_level": "Critical", "single_source": False, "po_coverage_pct": 55},
    {"vendor_name": "Hetzner",          "category": "Cloud & Compute",       "total_spend": 1000,  "contract_status": "Under Contract", "contract_end": "2027-03-31", "risk_level": "Low",      "single_source": False, "po_coverage_pct": 85},
    {"vendor_name": "Dell",             "category": "Hardware & Equipment",  "total_spend": 900,   "contract_status": "No Contract",    "contract_end": "N/A",        "risk_level": "Low",      "single_source": False, "po_coverage_pct": 90},
    {"vendor_name": "Navan",            "category": "Travel & Expenses",     "total_spend": 800,   "contract_status": "Under Contract", "contract_end": "2026-12-31", "risk_level": "Low",      "single_source": False, "po_coverage_pct": 45},
    {"vendor_name": "Personio",         "category": "Recruitment & HR",      "total_spend": 800,   "contract_status": "Under Contract", "contract_end": "2026-09-30", "risk_level": "Low",      "single_source": False, "po_coverage_pct": 70},
    {"vendor_name": "Baker McKenzie",   "category": "Professional Services", "total_spend": 800,   "contract_status": "Under Contract", "contract_end": "2026-12-31", "risk_level": "Medium",   "single_source": False, "po_coverage_pct": 60},
    {"vendor_name": "Apple",            "category": "Hardware & Equipment",  "total_spend": 800,   "contract_status": "No Contract",    "contract_end": "N/A",        "risk_level": "Low",      "single_source": False, "po_coverage_pct": 85},
    {"vendor_name": "Deutsche Telekom", "category": "Telecom & Voice",       "total_spend": 800,   "contract_status": "Under Contract", "contract_end": "2027-06-30", "risk_level": "High",     "single_source": False, "po_coverage_pct": 85},
    {"vendor_name": "GitHub",           "category": "IT Software & SaaS",    "total_spend": 800,   "contract_status": "Under Contract", "contract_end": "2026-12-31", "risk_level": "Low",      "single_source": False, "po_coverage_pct": 90},
    {"vendor_name": "Datadog",          "category": "IT Software & SaaS",    "total_spend": 600,   "contract_status": "Under Contract", "contract_end": "2027-01-31", "risk_level": "Low",      "single_source": False, "po_coverage_pct": 85},
    {"vendor_name": "Atlassian",        "category": "IT Software & SaaS",    "total_spend": 600,   "contract_status": "Under Contract", "contract_end": "2027-03-31", "risk_level": "Low",      "single_source": False, "po_coverage_pct": 88},
    {"vendor_name": "Lyreco",           "category": "Facilities & Office",   "total_spend": 600,   "contract_status": "Under Contract", "contract_end": "2027-06-30", "risk_level": "Low",      "single_source": False, "po_coverage_pct": 75},
    {"vendor_name": "BCD Travel",       "category": "Travel & Expenses",     "total_spend": 800,   "contract_status": "Under Contract", "contract_end": "2026-09-30", "risk_level": "Medium",   "single_source": False, "po_coverage_pct": 40},
]


# ── Scoring & classification ───────────────────────────────────────────────────

def compute_compliance_score(po_coverage_pct: float, contract_status: str,
                              single_source: bool, risk_level: str) -> float:
    """0–100 score: PO compliance (35) + contract coverage (35) + concentration (20) + maverick (10)."""
    po_score = (min(po_coverage_pct, 100) / 100) * 35
    contract_map = {"Under Contract": 35, "Expired": 14, "No Contract": 0, "Unknown": 17}
    contract_score = contract_map.get(contract_status, 17)
    concentration_score = 10 if single_source else 20
    maverick_score = (min(po_coverage_pct, 100) / 100) * 10
    return round(po_score + contract_score + concentration_score + maverick_score, 1)


def suggest_relationship_status(tier: str, risk_level: str,
                                 contract_status: str, single_source: bool) -> str:
    """Rule-based relationship status suggestion — user can always override."""
    if single_source or risk_level == "Critical":
        return "Strategic"
    if tier == "A":
        return "Strategic" if risk_level == "High" else "Preferred"
    if tier == "B":
        return "Preferred" if contract_status == "Under Contract" else "Approved"
    return "Transactional"


def assign_abc_tiers(records: list) -> list:
    """
    Assign ABC tiers to a list of supplier dicts (must have 'total_spend').
    Base tier = Pareto (A=top 80%, B=next 15%, C=bottom 5%).
    Criticality bump: Critical risk or sole_source → tier upgraded to A.
    tier_override wins over computed tier.
    Returns the same list with 'tier' and 'tier_computed' set on each record.
    """
    total = sum(r.get("total_spend", 0) for r in records)
    if not total:
        for r in records:
            r["tier_computed"] = "C"
            r["tier"] = r.get("tier_override") or "C"
        return records

    sorted_recs = sorted(records, key=lambda x: x.get("total_spend", 0), reverse=True)
    cumulative = 0
    for r in sorted_recs:
        cumulative += r.get("total_spend", 0)
        pct = cumulative / total
        r["tier_computed"] = "A" if pct <= 0.80 else "B" if pct <= 0.95 else "C"

    for r in sorted_recs:
        if r.get("risk_level") == "Critical" or r.get("single_source"):
            if r["tier_computed"] in ("B", "C"):
                r["tier_computed"] = "A"
        r["tier"] = r.get("tier_override") or r["tier_computed"]

    return sorted_recs


# ── Database helpers ───────────────────────────────────────────────────────────

def init_supplier_profiles(conn: sqlite3.Connection) -> None:
    """Create supplier_profiles table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS supplier_profiles (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name          TEXT NOT NULL,
            vendor_name          TEXT NOT NULL,
            category             TEXT,
            tier                 TEXT,
            tier_computed        TEXT,
            tier_override        TEXT,
            relationship_status  TEXT,
            total_spend          REAL DEFAULT 0,
            po_coverage_pct      REAL DEFAULT 0,
            contract_status      TEXT DEFAULT 'Unknown',
            contract_end         TEXT,
            risk_level           TEXT DEFAULT 'Medium',
            single_source        INTEGER DEFAULT 0,
            compliance_score     REAL DEFAULT 0,
            last_updated         TEXT,
            UNIQUE(client_name, vendor_name)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sp_client ON supplier_profiles(client_name)"
    )
    conn.commit()


def upsert_supplier_profile(conn: sqlite3.Connection, client_name: str,
                             record: dict) -> None:
    """Insert or update a single supplier profile. tier_override is preserved if already set."""
    existing = conn.execute(
        "SELECT tier_override, relationship_status FROM supplier_profiles "
        "WHERE client_name=? AND vendor_name=?",
        (client_name, record["vendor_name"])
    ).fetchone()

    override = (existing["tier_override"] if existing and existing["tier_override"]
                else record.get("tier_override"))
    rel_status = (existing["relationship_status"] if existing and existing["relationship_status"]
                  else record.get("relationship_status"))

    conn.execute("""
        INSERT INTO supplier_profiles
            (client_name, vendor_name, category, tier, tier_computed, tier_override,
             relationship_status, total_spend, po_coverage_pct, contract_status,
             contract_end, risk_level, single_source, compliance_score, last_updated)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(client_name, vendor_name) DO UPDATE SET
            category=excluded.category,
            tier=excluded.tier,
            tier_computed=excluded.tier_computed,
            tier_override=COALESCE(tier_override, excluded.tier_override),
            relationship_status=COALESCE(relationship_status, excluded.relationship_status),
            total_spend=excluded.total_spend,
            po_coverage_pct=excluded.po_coverage_pct,
            contract_status=excluded.contract_status,
            contract_end=excluded.contract_end,
            risk_level=excluded.risk_level,
            single_source=excluded.single_source,
            compliance_score=excluded.compliance_score,
            last_updated=excluded.last_updated
    """, (
        client_name,
        record["vendor_name"],
        record.get("category"),
        record.get("tier"),
        record.get("tier_computed"),
        override,
        rel_status,
        record.get("total_spend", 0),
        record.get("po_coverage_pct", 0),
        record.get("contract_status", "Unknown"),
        record.get("contract_end"),
        record.get("risk_level", "Medium"),
        int(bool(record.get("single_source", False))),
        record.get("compliance_score", 0),
        datetime.now().isoformat()[:10],
    ))
    conn.commit()


def compute_and_save_profiles(conn: sqlite3.Connection,
                               client_name: str = "default") -> pd.DataFrame:
    """
    Aggregate spend per vendor from transactions_enriched + transactions_raw,
    compute ABC tiers and compliance scores, upsert supplier_profiles.
    Falls back to demo data when no transactions exist.
    """
    init_supplier_profiles(conn)

    try:
        df_tx = pd.read_sql_query("""
            SELECT r.supplier AS vendor_name,
                   SUM(r.spend) AS total_spend,
                   e.category_mapped AS category,
                   e.contract_status,
                   e.po_status,
                   v.risk_level,
                   v.single_source,
                   v.contract_end_date
            FROM transactions_raw r
            LEFT JOIN transactions_enriched e ON e.raw_id = r.id
            LEFT JOIN vendors v ON v.vendor_name = r.supplier
            WHERE r.supplier IS NOT NULL
            GROUP BY r.supplier
            ORDER BY total_spend DESC
        """, conn)
    except Exception:
        df_tx = pd.DataFrame()

    if df_tx.empty:
        records = [dict(r) for r in _DEMO_SUPPLIERS]
    else:
        records = []
        for _, row in df_tx.iterrows():
            po_pct = 100 if row.get("po_status") == "With PO" else \
                     75 if row.get("po_status") == "Blanket PO" else \
                     0 if row.get("po_status") == "No PO" else 50
            records.append({
                "vendor_name":    row["vendor_name"],
                "category":       row.get("category") or "Unknown",
                "total_spend":    float(row.get("total_spend") or 0),
                "contract_status": row.get("contract_status") or "Unknown",
                "contract_end":   row.get("contract_end_date"),
                "risk_level":     row.get("risk_level") or "Medium",
                "single_source":  bool(row.get("single_source", False)),
                "po_coverage_pct": po_pct,
            })

    records = assign_abc_tiers(records)

    for r in records:
        r["compliance_score"] = compute_compliance_score(
            r.get("po_coverage_pct", 0),
            r.get("contract_status", "Unknown"),
            r.get("single_source", False),
            r.get("risk_level", "Medium"),
        )
        if not r.get("relationship_status"):
            r["relationship_status"] = suggest_relationship_status(
                r["tier"], r.get("risk_level", "Medium"),
                r.get("contract_status", "Unknown"),
                r.get("single_source", False),
            )
        upsert_supplier_profile(conn, client_name, r)

    return get_supplier_profiles(conn, client_name)


def get_supplier_profiles(conn: sqlite3.Connection,
                           client_name: str = "default") -> pd.DataFrame:
    """Return all supplier profiles as a DataFrame. Falls back to demo if table empty."""
    init_supplier_profiles(conn)
    try:
        df = pd.read_sql_query("""
            SELECT vendor_name, category, tier, relationship_status,
                   total_spend, po_coverage_pct, contract_status,
                   contract_end, risk_level, single_source, compliance_score
            FROM supplier_profiles
            WHERE client_name=?
            ORDER BY total_spend DESC
        """, conn, params=(client_name,))
    except Exception:
        df = pd.DataFrame()

    if df.empty:
        return build_demo_profiles()
    return df


def build_demo_profiles() -> pd.DataFrame:
    """Build supplier DataFrame from demo data without hitting the DB."""
    records = [dict(r) for r in _DEMO_SUPPLIERS]
    records = assign_abc_tiers(records)
    rows = []
    for r in records:
        score = compute_compliance_score(
            r["po_coverage_pct"], r["contract_status"],
            r["single_source"], r["risk_level"]
        )
        rows.append({
            "vendor_name":         r["vendor_name"],
            "category":            r["category"],
            "tier":                r["tier"],
            "relationship_status": suggest_relationship_status(
                r["tier"], r["risk_level"], r["contract_status"], r["single_source"]
            ),
            "total_spend":         r["total_spend"],
            "po_coverage_pct":     r["po_coverage_pct"],
            "contract_status":     r["contract_status"],
            "contract_end":        r["contract_end"],
            "risk_level":          r["risk_level"],
            "single_source":       r["single_source"],
            "compliance_score":    score,
        })
    return pd.DataFrame(rows)


def update_supplier_field(conn: sqlite3.Connection, client_name: str,
                           vendor_name: str, field: str, value) -> None:
    """
    Update a single editable field on a supplier profile.
    If field=='category': cascades to vendors table and vendor_cache.json.
    If field=='tier': stored as tier_override so it survives recomputation.
    """
    if field == "tier":
        conn.execute(
            "UPDATE supplier_profiles SET tier=?, tier_override=?, last_updated=? "
            "WHERE client_name=? AND vendor_name=?",
            (value, value, datetime.now().isoformat()[:10], client_name, vendor_name)
        )
    elif field == "category":
        conn.execute(
            "UPDATE supplier_profiles SET category=?, last_updated=? "
            "WHERE client_name=? AND vendor_name=?",
            (value, datetime.now().isoformat()[:10], client_name, vendor_name)
        )
        conn.execute(
            "UPDATE vendors SET category=?, classification_source='manual_override', "
            "manual_override=1 WHERE vendor_name=?",
            (value, vendor_name)
        )
        _update_vendor_cache(vendor_name, value)
    else:
        conn.execute(
            f"UPDATE supplier_profiles SET {field}=?, last_updated=? "
            "WHERE client_name=? AND vendor_name=?",
            (value, datetime.now().isoformat()[:10], client_name, vendor_name)
        )
    conn.commit()


def _update_vendor_cache(vendor_name: str, category: str) -> None:
    """Persist a category correction into vendor_cache.json so future uploads inherit it."""
    cache = {}
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    entry = cache.get(vendor_name, {})
    if isinstance(entry, dict):
        entry["category"] = category
    else:
        entry = {"category": category}
    cache[vendor_name] = entry
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"  💾 vendor_cache updated: {vendor_name} → {category}")
