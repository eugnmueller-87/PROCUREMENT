"""
api.py — SpendLens REST API
Exposes spend intelligence to external consumers (Telegram Icarus bot, etc.).

Run:
    .venv/Scripts/python.exe -m uvicorn api:app --port 8000 --reload

Endpoints:
    GET /health
    GET /spend/summary
    GET /spend/maverick
    GET /vendors/top
    GET /vendors/{name}
"""

import os
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv

load_dotenv()

from modules.database import get_connection, get_full_transaction_view, get_maverick_transactions

app = FastAPI(title="SpendLens API", version="1.0")

CLIENT = os.environ.get("SPENDLENS_CLIENT", "default")


def _conn():
    return get_connection(CLIENT)


# ── /health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    try:
        conn = _conn()
        count = conn.execute("SELECT COUNT(*) FROM transactions_raw").fetchone()[0]
        conn.close()
        return {"status": "ok", "transactions": count, "client": CLIENT}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── /spend/summary ─────────────────────────────────────────────────────────────

@app.get("/spend/summary")
def spend_summary():
    """Total spend by category + overall KPIs."""
    conn = _conn()
    try:
        df = get_full_transaction_view(conn)
    finally:
        conn.close()

    if df.empty:
        return {"total_eur": 0, "categories": [], "transaction_count": 0}

    spend_col = "spend_eur" if "spend_eur" in df.columns and df["spend_eur"].notna().any() else "spend"
    df["_spend"] = df[spend_col].fillna(0)

    total = float(df["_spend"].sum())
    tx_count = len(df)

    by_cat = (
        df.groupby("category_mapped")["_spend"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    categories = [
        {"category": row["category_mapped"] or "Uncategorised", "spend_eur": round(float(row["_spend"]), 2)}
        for _, row in by_cat.iterrows()
    ]

    maverick_spend = float(df[df["maverick_flag"] == 1]["_spend"].sum()) if "maverick_flag" in df.columns else 0
    maverick_pct = round(maverick_spend / total * 100, 1) if total else 0

    return {
        "total_eur": round(total, 2),
        "transaction_count": tx_count,
        "maverick_spend_eur": round(maverick_spend, 2),
        "maverick_pct": maverick_pct,
        "categories": categories,
    }


# ── /spend/maverick ────────────────────────────────────────────────────────────

@app.get("/spend/maverick")
def maverick_spend(limit: int = 20):
    """Maverick spend transactions — no PO, outside contract."""
    conn = _conn()
    try:
        df = get_maverick_transactions(conn)
    finally:
        conn.close()

    if df.empty:
        return {"count": 0, "total_eur": 0, "transactions": []}

    df = df.head(limit)
    total = float(df["spend"].fillna(0).sum())

    transactions = [
        {
            "supplier": row.get("supplier"),
            "spend_eur": round(float(row.get("spend") or 0), 2),
            "date": str(row.get("date") or ""),
            "description": str(row.get("description") or "")[:80],
            "po_status": row.get("po_status"),
            "contract_status": row.get("contract_status"),
            "category": row.get("category_mapped"),
        }
        for _, row in df.iterrows()
    ]

    return {"count": len(transactions), "total_eur": round(total, 2), "transactions": transactions}


# ── /vendors/top ───────────────────────────────────────────────────────────────

@app.get("/vendors/top")
def top_vendors(limit: int = 20, category: str = None):
    """Top vendors by spend. Optionally filter by category (fuzzy match)."""
    conn = _conn()
    try:
        if category:
            rows = conn.execute("""
                SELECT
                    v.vendor_name, v.category, v.total_spend, v.risk_level,
                    v.single_source, v.oc_country,
                    sp.tier, sp.compliance_score, sp.contract_status,
                    sp.po_coverage_pct, sp.relationship_status
                FROM vendors v
                LEFT JOIN supplier_profiles sp
                    ON sp.vendor_name = v.vendor_name AND sp.client_name = ?
                WHERE LOWER(v.category) LIKE LOWER(?)
                ORDER BY v.total_spend DESC
                LIMIT ?
            """, (CLIENT, f"%{category}%", limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT
                    v.vendor_name, v.category, v.total_spend, v.risk_level,
                    v.single_source, v.oc_country,
                    sp.tier, sp.compliance_score, sp.contract_status,
                    sp.po_coverage_pct, sp.relationship_status
                FROM vendors v
                LEFT JOIN supplier_profiles sp
                    ON sp.vendor_name = v.vendor_name AND sp.client_name = ?
                ORDER BY v.total_spend DESC
                LIMIT ?
            """, (CLIENT, limit)).fetchall()
    finally:
        conn.close()

    vendors = [
        {
            "vendor_name": r["vendor_name"],
            "category": r["category"],
            "total_spend_eur": round(float(r["total_spend"] or 0), 2),
            "risk_level": r["risk_level"],
            "single_source": bool(r["single_source"]),
            "country": r["oc_country"],
            "tier": r["tier"],
            "compliance_score": round(float(r["compliance_score"] or 0), 1),
            "contract_status": r["contract_status"],
            "po_coverage_pct": round(float(r["po_coverage_pct"] or 0), 1),
            "relationship_status": r["relationship_status"],
        }
        for r in rows
    ]

    return {"count": len(vendors), "vendors": vendors, "category_filter": category}


# ── /spend/category/{category} ─────────────────────────────────────────────────

@app.get("/spend/category/{category}")
def spend_by_category(category: str, limit: int = 10):
    """Spend breakdown for a single category — total, top vendors, what they're used for."""
    conn = _conn()
    try:
        df = get_full_transaction_view(conn)
        if df.empty:
            conn.close()
            return {"category": category, "total_eur": 0, "vendors": []}

        spend_col = "spend_eur" if "spend_eur" in df.columns and df["spend_eur"].notna().any() else "spend"
        df["_spend"] = df[spend_col].fillna(0)

        # Fuzzy category match
        mask = df["category_mapped"].str.lower().str.contains(category.lower(), na=False)
        cat_df = df[mask]

        if cat_df.empty:
            conn.close()
            return {"category": category, "matched_category": None, "total_eur": 0, "vendors": []}

        matched_category = cat_df["category_mapped"].mode()[0]
        total = float(cat_df["_spend"].sum())
        tx_count = len(cat_df)

        # Top vendors in category with what they were paid for
        by_vendor = (
            cat_df.groupby("supplier")
            .agg(spend=("_spend", "sum"), txns=("_spend", "count"))
            .sort_values("spend", ascending=False)
            .head(limit)
            .reset_index()
        )

        vendors = []
        for _, vrow in by_vendor.iterrows():
            vendor_name = vrow["supplier"]
            # Sample descriptions to show what the vendor was paid for
            descriptions = (
                cat_df[cat_df["supplier"] == vendor_name]["description"]
                .dropna()
                .unique()
                .tolist()[:3]
            )
            vendors.append({
                "vendor_name": vendor_name,
                "spend_eur": round(float(vrow["spend"]), 2),
                "transaction_count": int(vrow["txns"]),
                "pct_of_category": round(float(vrow["spend"]) / total * 100, 1) if total else 0,
                "used_for": [str(d)[:60] for d in descriptions],
            })

        conn.close()
        return {
            "category": category,
            "matched_category": matched_category,
            "total_eur": round(total, 2),
            "transaction_count": tx_count,
            "vendor_count": len(by_vendor),
            "vendors": vendors,
        }
    except Exception:
        conn.close()
        raise


# ── /vendors/{name} ────────────────────────────────────────────────────────────

@app.get("/vendors/{name}")
def vendor_profile(name: str):
    """Full profile for a single vendor — spend history, flags, compliance."""
    conn = _conn()
    try:
        # Exact match first, then case-insensitive
        row = conn.execute(
            "SELECT * FROM vendors WHERE vendor_name = ?", (name,)
        ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM vendors WHERE LOWER(vendor_name) = LOWER(?)", (name,)
            ).fetchone()
        if not row:
            raise HTTPException(404, f"Vendor '{name}' not found")

        vendor_name = row["vendor_name"]

        sp = conn.execute(
            "SELECT * FROM supplier_profiles WHERE vendor_name = ? AND client_name = ?",
            (vendor_name, CLIENT)
        ).fetchone()

        # Last 5 transactions
        txns = conn.execute("""
            SELECT r.date, r.spend, r.spend_eur, r.description, r.po_number,
                   e.po_status, e.contract_status, e.maverick_flag
            FROM transactions_raw r
            LEFT JOIN transactions_enriched e ON e.raw_id = r.id
            WHERE r.supplier = ?
            ORDER BY r.date DESC
            LIMIT 5
        """, (vendor_name,)).fetchall()

        # Maverick transaction count
        maverick_count = conn.execute("""
            SELECT COUNT(*) FROM transactions_enriched e
            JOIN transactions_raw r ON r.id = e.raw_id
            WHERE r.supplier = ? AND e.maverick_flag = 1
        """, (vendor_name,)).fetchone()[0]

    finally:
        conn.close()

    return {
        "vendor_name": vendor_name,
        "category": row["category"],
        "country": row["oc_country"],
        "jurisdiction": row["oc_jurisdiction"],
        "entity_type": row["oc_entity_type"],
        "total_spend_eur": round(float(row["total_spend"] or 0), 2),
        "transaction_count": row["transaction_count"],
        "risk_level": row["risk_level"],
        "single_source": bool(row["single_source"]),
        "is_freelancer": bool(row["is_freelancer"]),
        "first_seen": row["first_seen"],
        "last_seen": row["last_seen"],
        "compliance": {
            "tier": sp["tier"] if sp else None,
            "compliance_score": round(float(sp["compliance_score"] or 0), 1) if sp else None,
            "contract_status": sp["contract_status"] if sp else "Unknown",
            "contract_end": sp["contract_end"] if sp else None,
            "po_coverage_pct": round(float(sp["po_coverage_pct"] or 0), 1) if sp else None,
            "relationship_status": sp["relationship_status"] if sp else None,
        },
        "maverick_transaction_count": maverick_count,
        "recent_transactions": [
            {
                "date": t["date"],
                "spend_eur": round(float(t["spend_eur"] or t["spend"] or 0), 2),
                "description": str(t["description"] or "")[:80],
                "po_number": t["po_number"],
                "po_status": t["po_status"],
                "maverick": bool(t["maverick_flag"]),
            }
            for t in txns
        ],
    }
