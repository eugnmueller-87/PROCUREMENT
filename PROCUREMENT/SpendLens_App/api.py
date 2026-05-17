"""
api.py — SpendLens REST API + Static Frontend Server
=====================================================
Serves the React frontend and exposes all spend intelligence as REST endpoints.

Run locally:
    uvicorn api:app --reload --port 8000

Production (Railway):
    web: uvicorn api:app --host 0.0.0.0 --port $PORT
"""

import os
import io
import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from modules.database import (
    get_connection, init_database,
    get_full_transaction_view, get_maverick_transactions,
    get_contracts, get_expiring_contracts,
)
from modules.supplier_profiler import (
    get_supplier_profiles, build_demo_profiles, TAXONOMY,
)

CLIENT = os.environ.get("SPENDLENS_CLIENT", "default")
FRONTEND_DIR = Path(__file__).parent / "frontend"

# ── Init DB ────────────────────────────────────────────────────────────────────
init_database(CLIENT)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="SpendLens API", version="2.0", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _conn():
    return get_connection(CLIENT)


def _spend_col(df: pd.DataFrame) -> str:
    return "spend_eur" if "spend_eur" in df.columns and df["spend_eur"].notna().any() else "spend"


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    try:
        conn = _conn()
        count = conn.execute("SELECT COUNT(*) FROM transactions_raw").fetchone()[0]
        conn.close()
        return {"status": "ok", "transactions": count, "client": CLIENT}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Dashboard KPIs ─────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
def dashboard(year: Optional[int] = None):
    """Main dashboard payload — KPIs, spend trend, expiring contracts, risk map."""
    conn = _conn()
    try:
        df = get_full_transaction_view(conn)
        contracts_df = get_expiring_contracts(conn, days=180)
    finally:
        conn.close()

    if df.empty:
        return _demo_dashboard()

    sc = _spend_col(df)
    df["_spend"] = df[sc].fillna(0)
    df["_date"] = pd.to_datetime(df["date"], errors="coerce")
    df["_year"] = df["_date"].dt.year

    years = sorted(df["_year"].dropna().unique().tolist())

    if year and year in years:
        fdf = df[df["_year"] == year]
    else:
        fdf = df
        year = None

    total = float(fdf["_spend"].sum())
    prev_year = year - 1 if year else (max(years) - 1 if years else None)
    prev_df = df[df["_year"] == prev_year] if prev_year else pd.DataFrame()
    prev_total = float(prev_df["_spend"].sum()) if not prev_df.empty else 0
    yoy = round((total - prev_total) / prev_total * 100, 1) if prev_total else 0

    maverick_spend = float(fdf[fdf["maverick_flag"] == 1]["_spend"].sum()) if "maverick_flag" in fdf.columns else 0
    maverick_pct = round(maverick_spend / total * 100, 1) if total else 0

    with_po = fdf[fdf["po_status"].str.contains("With PO|Blanket", na=False)]["_spend"].sum() if "po_status" in fdf.columns else 0
    po_coverage = round(float(with_po) / total * 100, 1) if total else 0

    # Spend trend by year + category
    trend_data = {}
    for cat in TAXONOMY:
        cat_df = df[df["category_mapped"] == cat]
        by_year = cat_df.groupby("_year")["_spend"].sum()
        trend_data[cat] = {int(y): round(float(v / 1000), 1) for y, v in by_year.items()}

    # Category breakdown
    by_cat = (
        fdf.groupby("category_mapped")["_spend"]
        .sum().sort_values(ascending=False).reset_index()
    )
    categories = [
        {
            "id": row["category_mapped"].lower().replace(" ", "_").replace("/", "_").replace("&", "and") if row["category_mapped"] else "other",
            "name": row["category_mapped"] or "Uncategorised",
            "spend": round(float(row["_spend"]) / 1000, 1),
            "budget": round(float(row["_spend"]) * 0.92 / 1000, 1),
            "risk": "high",
            "suppliers": int(fdf[fdf["category_mapped"] == row["category_mapped"]]["supplier"].nunique()),
            "growth": 0,
        }
        for _, row in by_cat.iterrows() if row["category_mapped"]
    ]

    # Expiring contracts
    expiring = []
    if not contracts_df.empty:
        for _, r in contracts_df.iterrows():
            days_left = (datetime.strptime(str(r["end_date"])[:10], "%Y-%m-%d").date() - date.today()).days if r.get("end_date") else 999
            expiring.append({
                "supplier": r.get("vendor_name", "Unknown"),
                "cat": r.get("contract_type", ""),
                "value": 0,
                "expiry": str(r.get("end_date", ""))[:10],
                "risk": r.get("risk_level", "Medium"),
                "daysLeft": days_left,
            })

    return {
        "years": [int(y) for y in years],
        "selectedYear": year,
        "kpis": {
            "totalSpend": round(total / 1000, 1),
            "yoyGrowth": yoy,
            "maverickPct": maverick_pct,
            "poCoverage": po_coverage,
            "contractCoverage": 75,
            "ebitdaImpact": round(total * 0.028 / 1000, 1),
        },
        "categories": categories,
        "trendYears": sorted(set(int(y) for y in df["_year"].dropna())),
        "trendData": trend_data,
        "expiringContracts": expiring[:10],
    }


def _demo_dashboard():
    """Return demo data when no transactions are in the DB."""
    cats = [
        {"id": "cloud", "name": "Cloud & Compute",       "spend": 24.0, "budget": 22.0, "risk": "critical", "suppliers": 5, "growth": 471},
        {"id": "ai",    "name": "AI/ML APIs & Data",     "spend": 9.2,  "budget": 9.0,  "risk": "high",     "suppliers": 5, "growth": 1050},
        {"id": "hr",    "name": "Recruitment & HR",      "spend": 6.8,  "budget": 6.5,  "risk": "high",     "suppliers": 5, "growth": 1033},
        {"id": "mkt",   "name": "Marketing & Campaigns", "spend": 5.5,  "budget": 5.2,  "risk": "high",     "suppliers": 4, "growth": 1733},
        {"id": "fac",   "name": "Facilities & Office",   "spend": 4.8,  "budget": 4.9,  "risk": "high",     "suppliers": 5, "growth": 860},
        {"id": "re",    "name": "Real Estate",           "spend": 4.2,  "budget": 4.5,  "risk": "high",     "suppliers": 3, "growth": 250},
        {"id": "it",    "name": "IT Software & SaaS",    "spend": 4.2,  "budget": 4.4,  "risk": "low",      "suppliers": 5, "growth": 367},
        {"id": "prof",  "name": "Professional Services", "spend": 3.2,  "budget": 3.2,  "risk": "high",     "suppliers": 5, "growth": 700},
        {"id": "trav",  "name": "Travel & Expenses",     "spend": 3.2,  "budget": 3.0,  "risk": "low",      "suppliers": 5, "growth": 1500},
        {"id": "tel",   "name": "Telecom & Voice",       "spend": 3.0,  "budget": 3.1,  "risk": "critical", "suppliers": 4, "growth": 650},
        {"id": "hw",    "name": "Hardware & Equipment",  "spend": 2.4,  "budget": 2.5,  "risk": "high",     "suppliers": 4, "growth": 700},
    ]
    trend_data = {
        "Cloud & Compute":       {2022: 4.2,  2023: 7.1,  2024: 12.4, 2025: 18.8, 2026: 24.0},
        "AI/ML APIs & Data":     {2022: 0.8,  2023: 1.7,  2024: 3.9,  2025: 6.8,  2026: 9.2},
        "Recruitment & HR":      {2022: 0.6,  2023: 1.4,  2024: 2.9,  2025: 4.9,  2026: 6.8},
        "Marketing & Campaigns": {2022: 0.3,  2023: 0.9,  2024: 2.1,  2025: 3.8,  2026: 5.5},
        "Facilities & Office":   {2022: 0.5,  2023: 1.3,  2024: 2.5,  2025: 3.8,  2026: 4.8},
        "Real Estate":           {2022: 1.2,  2023: 1.7,  2024: 2.4,  2025: 3.3,  2026: 4.2},
        "IT Software & SaaS":    {2022: 0.9,  2023: 1.5,  2024: 2.4,  2025: 3.3,  2026: 4.2},
        "Professional Services": {2022: 0.4,  2023: 0.9,  2024: 1.7,  2025: 2.6,  2026: 3.2},
        "Travel & Expenses":     {2022: 0.2,  2023: 0.6,  2024: 1.4,  2025: 2.4,  2026: 3.2},
        "Telecom & Voice":       {2022: 0.4,  2023: 0.8,  2024: 1.5,  2025: 2.3,  2026: 3.0},
        "Hardware & Equipment":  {2022: 0.3,  2023: 0.7,  2024: 1.3,  2025: 1.9,  2026: 2.4},
    }
    expiring = [
        {"supplier": "OpenAI",      "cat": "AI/ML APIs & Data",    "value": 2800,  "expiry": "2026-06-30", "risk": "High",     "daysLeft": 44},
        {"supplier": "Deloitte",    "cat": "Professional Services", "value": 1200,  "expiry": "2026-03-31", "risk": "Critical", "daysLeft": -47},
        {"supplier": "Twilio",      "cat": "Telecom & Voice",       "value": 2200,  "expiry": "2026-07-31", "risk": "Critical", "daysLeft": 75},
        {"supplier": "AWS",         "cat": "Cloud & Compute",       "value": 18000, "expiry": "2026-09-30", "risk": "High",     "daysLeft": 136},
        {"supplier": "BCD Travel",  "cat": "Travel & Expenses",     "value": 800,   "expiry": "2026-09-30", "risk": "Medium",   "daysLeft": 136},
        {"supplier": "Hays",        "cat": "Recruitment & HR",      "value": 1500,  "expiry": "2026-12-31", "risk": "Medium",   "daysLeft": 228},
        {"supplier": "Datadog",     "cat": "IT Software & SaaS",    "value": 600,   "expiry": "2027-01-31", "risk": "Low",      "daysLeft": 259},
    ]
    return {
        "years": [2022, 2023, 2024, 2025, 2026],
        "selectedYear": None,
        "kpis": {"totalSpend": 70.5, "yoyGrowth": 44, "maverickPct": 12, "poCoverage": 74, "contractCoverage": 75, "ebitdaImpact": 1950},
        "categories": cats,
        "trendYears": [2022, 2023, 2024, 2025, 2026],
        "trendData": trend_data,
        "expiringContracts": expiring,
        "_demo": True,
    }


# ── Suppliers / Compliance ─────────────────────────────────────────────────────

@app.get("/api/suppliers")
def suppliers():
    """All suppliers with compliance scores, tiers, risk."""
    conn = _conn()
    try:
        profiles = get_supplier_profiles(conn, CLIENT)
        if profiles.empty:
            profiles = build_demo_profiles()
    finally:
        conn.close()

    result = []
    for _, r in profiles.iterrows():
        tier = str(r.get("tier") or r.get("tier_computed") or "C")
        score = float(r.get("compliance_score") or 0)
        spend = float(r.get("total_spend") or 0)
        risk = str(r.get("risk_level") or "Medium")
        result.append({
            "id": str(r.get("vendor_name", "")).lower().replace(" ", "_"),
            "name": str(r.get("vendor_name") or ""),
            "cat": str(r.get("category") or ""),
            "country": str(r.get("country") or r.get("oc_country") or ""),
            "tier": tier,
            "rel": str(r.get("relationship_status") or "Transactional"),
            "risk": risk.lower(),
            "po": float(r.get("po_coverage_pct") or 0),
            "contract": 100 if str(r.get("contract_status") or "") == "Under Contract" else 0,
            "score": round(score, 0),
            "spend": round(spend / 1000, 1),
            "contractEnd": str(r.get("contract_end") or ""),
            "singleSource": bool(r.get("single_source") or False),
        })

    result.sort(key=lambda x: -x["score"])

    # Summary stats
    a_count = sum(1 for s in result if s["tier"] == "A")
    b_count = sum(1 for s in result if s["tier"] == "B")
    c_count = sum(1 for s in result if s["tier"] == "C")
    avg_po = round(sum(s["po"] for s in result) / len(result), 1) if result else 0
    avg_contract = round(sum(s["contract"] for s in result) / len(result), 1) if result else 0
    avg_score = round(sum(s["score"] for s in result) / len(result), 0) if result else 0

    return {
        "suppliers": result,
        "summary": {
            "score": avg_score,
            "poCoverage": avg_po,
            "contractCoverage": avg_contract,
            "aSuppliers": a_count,
            "bSuppliers": b_count,
            "cSuppliers": c_count,
            "total": len(result),
        },
    }


# ── Contracts / CLM ────────────────────────────────────────────────────────────

@app.get("/api/contracts")
def list_contracts():
    """All scanned contracts."""
    conn = _conn()
    try:
        df = get_contracts(conn)
    finally:
        conn.close()

    if df.empty:
        return {"contracts": []}

    result = []
    for _, r in df.iterrows():
        flags = {}
        try:
            flags = json.loads(r.get("clause_flags") or "{}")
        except Exception:
            pass
        actions = []
        try:
            actions = json.loads(r.get("required_actions") or "[]")
        except Exception:
            pass
        result.append({
            "id": int(r["id"]),
            "scannedAt": str(r.get("scanned_at") or ""),
            "filename": str(r.get("filename") or ""),
            "vendorName": str(r.get("vendor_name") or ""),
            "contractType": str(r.get("contract_type") or ""),
            "startDate": str(r.get("start_date") or ""),
            "endDate": str(r.get("end_date") or ""),
            "noticePeriodDays": r.get("notice_period_days"),
            "autoRenewal": bool(r.get("auto_renewal")),
            "penaltyCapPct": r.get("penalty_cap_pct"),
            "liabilityCap": str(r.get("liability_cap") or ""),
            "jurisdiction": str(r.get("jurisdiction") or ""),
            "paymentTerms": str(r.get("payment_terms") or ""),
            "riskScore": float(r.get("risk_score") or 0),
            "riskLevel": str(r.get("risk_level") or ""),
            "riskSummary": str(r.get("risk_summary") or ""),
            "missingClauses": str(r.get("missing_clauses") or ""),
            "clauseFlags": flags,
            "requiredActions": actions,
        })

    return {"contracts": result}


@app.post("/api/contracts/scan")
async def scan_contract(
    file: UploadFile = File(...),
    vendor_name: str = Form(""),
    contract_type: str = Form("MSA"),
):
    """Scan a contract PDF/DOCX and return extracted clauses + risk assessment."""
    try:
        from lex import scan_contract as lex_scan
    except ImportError:
        raise HTTPException(500, "Lex module not available")

    file_bytes = await file.read()
    try:
        result = lex_scan(file_bytes, file.filename, vendor_name, contract_type)
    except Exception as e:
        raise HTTPException(500, f"Scan failed: {e}")

    return result


@app.post("/api/contracts/save")
async def save_contract(
    file: UploadFile = File(...),
    vendor_name: str = Form(""),
    contract_type: str = Form("MSA"),
):
    """Scan and save a contract to the database."""
    try:
        from lex import scan_contract as lex_scan, save_contract as lex_save
    except ImportError:
        raise HTTPException(500, "Lex module not available")

    file_bytes = await file.read()
    try:
        result = lex_scan(file_bytes, file.filename, vendor_name, contract_type)
    except Exception as e:
        raise HTTPException(500, f"Scan failed: {e}")

    conn = _conn()
    try:
        contract_id = lex_save(conn, result)
    finally:
        conn.close()

    result["id"] = contract_id
    return result


# ── Spend upload pipeline ──────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_spend(file: UploadFile = File(...)):
    """Upload a CSV/Excel spend file and run the full 5-stage pipeline."""
    from modules.column_mapper import rule_based_mapping, ai_column_mapping, apply_mapping
    from modules.data_cleanup import full_cleanup
    from modules.category_mapper import run_category_mapping
    from modules.flag_engine import run_flag_engine
    from modules.database import log_upload, insert_raw_transactions, insert_enriched_transactions, bulk_upsert_vendors

    content = await file.read()
    filename = file.filename or "upload.csv"

    try:
        if filename.endswith(".csv"):
            df_raw = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
        else:
            df_raw = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Could not parse file: {e}")

    mapping = rule_based_mapping(df_raw.columns.tolist())
    unmapped = [c for c, v in mapping.items() if v is None]
    if unmapped:
        ai_result = ai_column_mapping(df_raw.columns.tolist(), df_raw.head(3).to_dict())
        mapping.update({k: v for k, v in ai_result.items() if v})

    df_mapped = apply_mapping(df_raw, mapping)
    df_clean = full_cleanup(df_mapped)

    if df_clean.empty:
        raise HTTPException(400, "No valid rows after cleanup")

    vendor_cache_path = Path(__file__).parent / "vendor_cache.json"
    vendor_cache = {}
    if vendor_cache_path.exists():
        with open(vendor_cache_path) as f:
            vendor_cache = json.load(f)

    classification, vendor_cache = run_category_mapping(df_clean, vendor_cache)

    with open(vendor_cache_path, "w") as f:
        json.dump(vendor_cache, f, indent=2)

    df_enriched = run_flag_engine(df_clean, classification)

    conn = _conn()
    try:
        upload_id = log_upload(conn, filename, "accounting", len(df_clean), mapping)
        stats = insert_raw_transactions(conn, df_clean, upload_id)
        insert_enriched_transactions(conn, df_clean, df_enriched)
        bulk_upsert_vendors(conn, classification)
    finally:
        conn.close()

    return {
        "status": "ok",
        "filename": filename,
        "rows_processed": len(df_clean),
        "rows_inserted": stats.get("inserted", 0),
        "rows_skipped": stats.get("skipped", 0),
    }


# ── Icarus signals ─────────────────────────────────────────────────────────────

@app.get("/api/signals")
def signals(category: Optional[str] = None, days: int = 30, limit: int = 50):
    """Market intelligence signals from Icarus."""
    try:
        from modules.database import get_connection as _gc
        icarus_db = Path(__file__).parent / "clients" / CLIENT / "icarus_memory.db"
        if not icarus_db.exists():
            return {"signals": [], "total": 0}

        conn = sqlite3.connect(str(icarus_db))
        conn.row_factory = sqlite3.Row
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        if category and category != "all":
            rows = conn.execute("""
                SELECT * FROM signals
                WHERE timestamp >= ? AND category LIKE ?
                ORDER BY timestamp DESC LIMIT ?
            """, (cutoff, f"%{category}%", limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM signals
                WHERE timestamp >= ?
                ORDER BY timestamp DESC LIMIT ?
            """, (cutoff, limit)).fetchall()

        conn.close()
        result = [dict(r) for r in rows]
        return {"signals": result, "total": len(result)}
    except Exception:
        return {"signals": [], "total": 0}


@app.post("/api/signals/scan")
def run_icarus_scan():
    """Trigger an Icarus RSS scan."""
    try:
        from icarus import run_scan
        count = run_scan(client_name=CLIENT)
        return {"status": "ok", "new_signals": count}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Static frontend ────────────────────────────────────────────────────────────
# Mount after all API routes so /api/* is never captured by static files

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {"message": "SpendLens API — frontend not built yet. Run from SpendLens_App/."}
