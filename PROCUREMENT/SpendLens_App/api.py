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
import logging
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
from contextlib import asynccontextmanager
from difflib import get_close_matches

import pandas as pd
from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Form, Depends, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

from modules.database import (  # noqa: E402
    get_connection, init_database,
    get_full_transaction_view, get_contracts, get_expiring_contracts,
)
from modules.supplier_profiler import (  # noqa: E402
    get_supplier_profiles, build_demo_profiles, compute_and_save_profiles, TAXONOMY,
)
from modules.column_mapper import rule_based_mapping, ai_column_mapping, apply_mapping  # noqa: E402
from modules.data_cleanup import full_cleanup  # noqa: E402
from modules.category_mapper import run_category_mapping  # noqa: E402
from modules.flag_engine import run_flag_engine  # noqa: E402
from modules.database import log_upload, insert_raw_transactions, insert_enriched_transactions  # noqa: E402

CLIENT = os.environ.get("SPENDLENS_CLIENT", "default")
HADES_URL = os.environ.get("HADES_URL", "")
FRONTEND_DIR = Path(__file__).parent / "frontend"

logger = logging.getLogger("spendlens.api")

# ── Auth ───────────────────────────────────────────────────────────────────────
# Shared-secret API key. Set SPENDLENS_API_KEY on Railway to enforce auth on all
# /api routes (clients must send an X-API-Key header). When unset (local dev),
# auth is disabled and the interactive docs stay available.

SPENDLENS_API_KEY = os.environ.get("SPENDLENS_API_KEY", "")

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_key(key: Optional[str] = Security(_api_key_header)):
    if not SPENDLENS_API_KEY:
        return  # auth not configured — dev mode
    if not key or not secrets.compare_digest(key, SPENDLENS_API_KEY):
        raise HTTPException(401, "Invalid or missing API key")


# ── Rate limiting (lightweight, in-process) ────────────────────────────────────
# Backstop against cost abuse on Anthropic-billed / expensive endpoints.

_rate_lock = threading.Lock()
_rate_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(name: str, max_calls: int, per_seconds: int):
    def _dep(request: Request):
        ip = request.client.host if request.client else "unknown"
        bucket_key = f"{name}:{ip}"
        now = time.monotonic()
        with _rate_lock:
            hits = _rate_hits[bucket_key]
            while hits and now - hits[0] > per_seconds:
                hits.popleft()
            if len(hits) >= max_calls:
                raise HTTPException(429, "Rate limit exceeded — try again later")
            hits.append(now)
    return _dep


# ── Upload limits ──────────────────────────────────────────────────────────────

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


async def _read_upload(file: UploadFile, allowed_exts: set[str]) -> bytes:
    """Read an upload with an extension allowlist and a hard size cap."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(415, f"Unsupported file type — expected {', '.join(sorted(allowed_exts))}")
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 25 MB)")
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1 << 20):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "File too large (max 25 MB)")
        chunks.append(chunk)
    return b"".join(chunks)

# ── Init DB ────────────────────────────────────────────────────────────────────
init_database(CLIENT)

# ── Hades proxy ────────────────────────────────────────────────────────────────

_hades_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def _lifespan(app):
    global _hades_client
    _hades_client = httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=120, write=10, pool=5))
    yield
    if _hades_client:
        await _hades_client.aclose()


# ── App ────────────────────────────────────────────────────────────────────────
# Interactive docs are disabled in production (i.e. whenever auth is enforced).
app = FastAPI(
    title="SpendLens API",
    version="2.0",
    docs_url=None if SPENDLENS_API_KEY else "/api/docs",
    lifespan=_lifespan,
    dependencies=[Depends(require_key)],
)

# Lock origins to the real domain in production via SPENDLENS_ALLOWED_ORIGINS
# (comma-separated), e.g. "https://spendlens.up.railway.app,http://localhost:8000".
# Defaults to "*" — the SPA is served same-origin, so CORS is barely needed.
_allowed_origins = [
    o.strip()
    for o in os.environ.get("SPENDLENS_ALLOWED_ORIGINS", "*").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept", "X-API-Key"],
)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # unsafe-inline/unsafe-eval are required by the inline theme script and
    # in-browser Babel JSX transpilation (see frontend/index.html).
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    return response


def _conn():
    return get_connection(CLIENT)


def _spend_col(df: pd.DataFrame) -> str:
    return "spend_eur" if "spend_eur" in df.columns and df["spend_eur"].notna().any() else "spend"


def _require_hades() -> str:
    if not HADES_URL:
        raise HTTPException(503, "Hades not configured")
    return HADES_URL


@app.get("/api/hades/health")
async def hades_health():
    if not HADES_URL:
        return {"status": "unconfigured"}
    try:
        r = await _hades_client.get(f"{HADES_URL}/health", timeout=5)
        return r.json()
    except Exception:
        return {"status": "offline"}

class HadesInvestigateRequest(BaseModel):
    """Shape of the Hades /investigate contract — only these keys are forwarded."""
    company: str = Field(..., min_length=1, max_length=200)
    category: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    mode: Optional[str] = Field(None, max_length=50)


@app.post("/api/hades/investigate", dependencies=[Depends(rate_limit("hades", 5, 60))])
async def hades_investigate(payload: HadesInvestigateRequest):
    url = _require_hades()
    try:
        r = await _hades_client.post(f"{url}/investigate", json=payload.model_dump(exclude_none=True), timeout=110)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Hades investigate returned %s: %s", e.response.status_code, e.response.text[:200])
        raise HTTPException(e.response.status_code, "Upstream service error")
    except Exception:
        logger.exception("Hades investigate failed")
        raise HTTPException(502, "Upstream service error")

@app.get("/api/hades/result/{task_id}")
async def hades_result(task_id: str):
    url = _require_hades()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", task_id):
        raise HTTPException(400, "Invalid task id")
    try:
        r = await _hades_client.get(f"{url}/result/{task_id}", timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Hades result returned %s: %s", e.response.status_code, e.response.text[:200])
        raise HTTPException(e.response.status_code, "Upstream service error")
    except Exception:
        logger.exception("Hades result fetch failed")
        raise HTTPException(502, "Upstream service error")


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    conn = _conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM transactions_raw").fetchone()[0]
        return {"status": "ok", "transactions": count, "client": CLIENT}
    except Exception:
        logger.exception("Health check failed")
        raise HTTPException(500, "Health check failed")
    finally:
        conn.close()


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
        return _demo_dashboard(year)

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
        trend_data[cat] = {int(y): round(float(v / 1e6), 1) for y, v in by_year.items()}

    # Category breakdown
    by_cat = (
        fdf.groupby("category_mapped")["_spend"]
        .sum().sort_values(ascending=False).reset_index()
    )
    supplier_counts = fdf.groupby("category_mapped")["supplier"].nunique()
    categories = [
        {
            "id": row["category_mapped"].lower().replace(" ", "_").replace("/", "_").replace("&", "and") if row["category_mapped"] else "other",
            "name": row["category_mapped"] or "Uncategorised",
            "spend": round(float(row["_spend"]) / 1e6, 1),
            "budget": round(float(row["_spend"]) * 0.92 / 1e6, 1),
            "risk": "high",
            "suppliers": int(supplier_counts.get(row["category_mapped"], 0)),
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
            "totalSpend": round(total / 1e6, 1),
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


def _demo_dashboard(year: Optional[int] = None):
    """Return demo data when no transactions are in the DB, filtered by year."""

    # Full trend data — all categories × all years
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

    all_years = [2022, 2023, 2024, 2025, 2026]

    # Per-category metadata (risk, suppliers, budget multiplier)
    cat_meta = [
        {"id": "cloud", "name": "Cloud & Compute",       "risk": "critical", "suppliers": 5, "budget_ratio": 0.92},
        {"id": "ai",    "name": "AI/ML APIs & Data",     "risk": "high",     "suppliers": 5, "budget_ratio": 0.97},
        {"id": "hr",    "name": "Recruitment & HR",       "risk": "high",     "suppliers": 5, "budget_ratio": 0.96},
        {"id": "mkt",   "name": "Marketing & Campaigns",  "risk": "high",     "suppliers": 4, "budget_ratio": 0.94},
        {"id": "fac",   "name": "Facilities & Office",    "risk": "high",     "suppliers": 5, "budget_ratio": 1.02},
        {"id": "re",    "name": "Real Estate",            "risk": "high",     "suppliers": 3, "budget_ratio": 1.07},
        {"id": "it",    "name": "IT Software & SaaS",     "risk": "low",      "suppliers": 5, "budget_ratio": 1.05},
        {"id": "prof",  "name": "Professional Services",  "risk": "high",     "suppliers": 5, "budget_ratio": 1.00},
        {"id": "trav",  "name": "Travel & Expenses",      "risk": "low",      "suppliers": 5, "budget_ratio": 0.93},
        {"id": "tel",   "name": "Telecom & Voice",        "risk": "critical", "suppliers": 4, "budget_ratio": 1.03},
        {"id": "hw",    "name": "Hardware & Equipment",   "risk": "high",     "suppliers": 4, "budget_ratio": 1.04},
    ]

    # Resolve selected year spend and prior year for YoY
    sel_year = year if year and year in all_years else None
    prev_year = (sel_year - 1) if sel_year and (sel_year - 1) in all_years else None

    def year_spend(name, y):
        return trend_data.get(name, {}).get(y, 0)

    # Build category list for selected year (or 2026 as "current" when all years)
    display_year = sel_year or 2026
    prev_display = prev_year or 2025

    cats = []
    for m in cat_meta:
        spend = year_spend(m["name"], display_year)
        first = year_spend(m["name"], 2022)
        growth = round((spend - first) / first * 100) if first else 0
        cats.append({
            "id": m["id"],
            "name": m["name"],
            "spend": spend,
            "budget": round(spend * m["budget_ratio"], 1),
            "risk": m["risk"],
            "suppliers": m["suppliers"],
            "growth": growth,
        })

    # KPIs
    total = round(sum(c["spend"] for c in cats), 1)
    prev_total = round(sum(year_spend(m["name"], prev_display) for m in cat_meta), 1)
    yoy = round((total - prev_total) / prev_total * 100, 1) if prev_total else 0

    # Maverick and PO coverage shift slightly by year
    maverick_pct = {2022: 18, 2023: 15, 2024: 13, 2025: 12, 2026: 12}.get(display_year, 12)
    po_coverage  = {2022: 60, 2023: 65, 2024: 70, 2025: 72, 2026: 74}.get(display_year, 74)

    expiring = [
        {"supplier": "OpenAI",     "cat": "AI/ML APIs & Data",    "value": 2800,  "expiry": "2026-06-30", "risk": "High",     "daysLeft": 44},
        {"supplier": "Deloitte",   "cat": "Professional Services", "value": 1200,  "expiry": "2026-03-31", "risk": "Critical", "daysLeft": -47},
        {"supplier": "Twilio",     "cat": "Telecom & Voice",       "value": 2200,  "expiry": "2026-07-31", "risk": "Critical", "daysLeft": 75},
        {"supplier": "AWS",        "cat": "Cloud & Compute",       "value": 18000, "expiry": "2026-09-30", "risk": "High",     "daysLeft": 136},
        {"supplier": "BCD Travel", "cat": "Travel & Expenses",     "value": 800,   "expiry": "2026-09-30", "risk": "Medium",   "daysLeft": 136},
        {"supplier": "Hays",       "cat": "Recruitment & HR",      "value": 1500,  "expiry": "2026-12-31", "risk": "Medium",   "daysLeft": 228},
        {"supplier": "Datadog",    "cat": "IT Software & SaaS",    "value": 600,   "expiry": "2027-01-31", "risk": "Low",      "daysLeft": 259},
    ]

    return {
        "years": all_years,
        "selectedYear": sel_year,
        "kpis": {
            "totalSpend": total,
            "yoyGrowth": yoy,
            "maverickPct": maverick_pct,
            "poCoverage": po_coverage,
            "contractCoverage": 75,
            "ebitdaImpact": round(total * 0.028 * 1000, 0),
        },
        "categories": cats,
        "trendYears": all_years,
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


@app.get("/api/suppliers/lookup/{name}")
def supplier_lookup(name: str):
    # Used by Icarus to answer "is X a supplier?" and "do we have DD on X?"
    conn = _conn()
    try:
        name_lower = name.lower().strip()
        # Exact match first
        row = conn.execute(
            "SELECT * FROM vendors WHERE lower(vendor_name) = ?", (name_lower,)
        ).fetchone()
        if row is None:
            # Fuzzy fallback — load names only, then fetch winner by exact name
            names = [r[0] for r in conn.execute("SELECT vendor_name FROM vendors").fetchall()]
            names_lower = [n.lower() for n in names]
            close = get_close_matches(name_lower, names_lower, n=1, cutoff=0.6)
            if not close:
                return {"found": False, "message": f"'{name}' not found in SpendLens spend data."}
            matched_name = names[names_lower.index(close[0])]
            row = conn.execute(
                "SELECT * FROM vendors WHERE vendor_name = ?", (matched_name,)
            ).fetchone()
        if row is None:
            return {"found": False, "message": f"'{name}' not found in SpendLens spend data."}
        matched_row = dict(row)
    finally:
        conn.close()

    return {
        "found": True,
        "vendor_name": matched_row["vendor_name"],
        "category": matched_row.get("category"),
        "country": matched_row.get("oc_country"),
        "first_seen": str(matched_row.get("first_seen") or "")[:10],
        "last_seen": str(matched_row.get("last_seen") or "")[:10],
        "transaction_count": matched_row.get("transaction_count", 0),
        "total_spend_eur": matched_row.get("total_spend", 0),
        "risk_level": matched_row.get("risk_level"),
        "single_source": bool(matched_row.get("single_source")),
        # Hades DD fields (populated when Hades has investigated this vendor)
        "hades": {
            "risk_score": matched_row.get("hades_risk_score"),
            "risk_level": matched_row.get("hades_risk_level"),
            "recommendation": matched_row.get("hades_recommendation"),
            "sanctions_clear": matched_row.get("hades_sanctions_clear"),
            "lksg_signal": matched_row.get("hades_lksg_signal"),
            "report_date": str(matched_row.get("hades_report_date") or "")[:10],
            "next_steps": matched_row.get("hades_next_steps"),
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


@app.post("/api/contracts/scan", dependencies=[Depends(rate_limit("contract_scan", 5, 60))])
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

    file_bytes = await _read_upload(file, {".pdf", ".docx"})
    try:
        result = lex_scan(file_bytes, file.filename, vendor_name, contract_type)
    except Exception:
        logger.exception("Contract scan failed")
        raise HTTPException(500, "Contract scan failed")

    return result


@app.post("/api/contracts/save", dependencies=[Depends(rate_limit("contract_scan", 5, 60))])
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

    file_bytes = await _read_upload(file, {".pdf", ".docx"})
    try:
        result = lex_scan(file_bytes, file.filename, vendor_name, contract_type)
    except Exception:
        logger.exception("Contract scan failed")
        raise HTTPException(500, "Contract scan failed")

    conn = _conn()
    try:
        contract_id = lex_save(conn, result)
    finally:
        conn.close()

    result["id"] = contract_id
    return result


# ── Spend upload pipeline ──────────────────────────────────────────────────────

@app.post("/api/upload", dependencies=[Depends(rate_limit("upload", 5, 60))])
async def upload_spend(file: UploadFile = File(...)):
    """Upload a CSV/Excel spend file and run the full 5-stage pipeline."""
    content = await _read_upload(file, {".csv", ".xlsx", ".xls"})
    filename = file.filename or "upload.csv"

    try:
        if filename.endswith(".csv"):
            df_raw = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
        else:
            df_raw = pd.read_excel(io.BytesIO(content))
    except Exception:
        logger.exception("Could not parse uploaded spend file")
        raise HTTPException(400, "Could not parse file — expected CSV or Excel")

    mapping = rule_based_mapping(df_raw.columns.tolist())
    unmapped = [c for c, v in mapping.items() if v is None]
    if unmapped:
        ai_result = ai_column_mapping(df_raw.columns.tolist(), df_raw.head(3).to_dict())
        mapping.update({k: v for k, v in ai_result.items() if v})

    df_mapped = apply_mapping(df_raw, mapping)
    df_clean, _cleanup_report = full_cleanup(df_mapped)

    if df_clean.empty:
        raise HTTPException(400, "No valid rows after cleanup")

    desc_col = next((c for c in df_clean.columns if "description" in c.lower()), None)
    enriched_df, _re_summary = run_category_mapping(
        df_clean, vendor_col="supplier", description_col=desc_col, spend_col="spend"
    )

    flagged_df, _coverage = run_flag_engine(enriched_df)

    conn = _conn()
    try:
        upload_id = log_upload(conn, filename, "accounting", len(df_clean), mapping)
        stats = insert_raw_transactions(conn, df_clean, upload_id)
        insert_enriched_transactions(conn, df_clean, flagged_df)
        compute_and_save_profiles(conn, CLIENT)
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

def _demo_signals():
    """Demo signals shown when icarus_memory.db is empty or missing."""
    return [
        {
            "id": "demo-1", "headline": "AWS announces 15% GPU spot price increase for H100 instances",
            "summary": "Amazon Web Services has raised spot pricing for H100 GPU instances by an average of 15% across us-east-1 and eu-west-1 regions, citing sustained demand from AI training workloads and constrained supply. On-demand pricing remains unchanged but reserved instance discounts have narrowed.",
            "category": "Cloud & Compute", "source": "DatacenterDynamics", "relevance": 9,
            "action": "Renegotiate AWS reserved instance terms before next renewal; benchmark against Azure and GCP spot pricing to build leverage.",
            "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
        },
        {
            "id": "demo-2", "headline": "OpenAI GPT-4o API pricing cut by 50% — enterprise contracts under review",
            "summary": "OpenAI has halved API pricing for GPT-4o effective immediately, impacting enterprise contracts signed under previous rate cards. Customers on annual agreements may have overpay clauses; legal teams recommend auditing MSA pricing schedules within 30 days.",
            "category": "AI/ML APIs & Data", "source": "Reuters", "relevance": 8,
            "action": "Audit OpenAI contract pricing schedule; request renegotiation or credit against overpayment vs new public rates.",
            "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
        },
        {
            "id": "demo-3", "headline": "Gartner: SaaS renewals in 2026 averaging 22% above 2024 contract values",
            "summary": "Gartner's Q1 2026 procurement benchmark shows SaaS renewal inflation averaging 22% above 2024 baseline contract values, driven by vendor consolidation post-M&A activity. IT Software & SaaS categories hardest hit; procurement teams urged to benchmark before entering renewal windows.",
            "category": "IT Software & SaaS", "source": "Spend Matters", "relevance": 7,
            "action": "Pull SaaS contract renewal calendar; flag contracts expiring in the next 90 days for benchmark analysis before vendor opens renewal conversation.",
            "timestamp": (datetime.now() - timedelta(days=3)).isoformat(),
        },
        {
            "id": "demo-4", "headline": "Twilio and Vonage price increases signal telecom consolidation pressure",
            "summary": "Both Twilio and Vonage have issued Q2 pricing notices averaging 8–12% increases on CPaaS (Communications-Platform-as-a-Service) contracts. The increases follow infrastructure cost rises and competitive pressure from hyperscaler voice offerings (AWS Connect, Azure Communication Services).",
            "category": "Telecom & Voice", "source": "Handelsblatt", "relevance": 7,
            "action": "Benchmark CPaaS rates against hyperscaler alternatives; use AWS Connect pricing as leverage in Twilio renewal negotiation.",
            "timestamp": (datetime.now() - timedelta(days=4)).isoformat(),
        },
        {
            "id": "demo-5", "headline": "Tech contractor day rates rise 18% in Germany as talent market tightens",
            "summary": "German IT contractor market shows 18% average day-rate increase YoY per Hays Technology report, with AI/ML specialists commanding 35% premium over 2024 rates. Supply constraints particularly acute in Munich and Berlin; companies with framework agreements signed pre-2025 face renegotiation pressure.",
            "category": "Recruitment & HR", "source": "Reuters", "relevance": 6,
            "action": "Review freelancer framework agreements; cap day-rate escalation clauses at CPI+5% in new contracts.",
            "timestamp": (datetime.now() - timedelta(days=5)).isoformat(),
        },
        {
            "id": "demo-6", "headline": "Deloitte and PwC raise consulting day rates by up to 20% for 2026 engagements",
            "summary": "The Big Four consulting firms have issued 2026 rate cards with increases of 15–20% vs 2025. Deloitte cites AI tooling investment costs; PwC references talent market inflation. Fixed-fee project structures increasingly favoured by procurement over T&M to contain exposure.",
            "category": "Professional Services", "source": "Spend Matters", "relevance": 6,
            "action": "Negotiate fixed-fee project structures for new consulting engagements; avoid time-and-materials for scopes exceeding 3 months.",
            "timestamp": (datetime.now() - timedelta(days=6)).isoformat(),
        },
        {
            "id": "demo-7", "headline": "European office vacancy rates reach 12% — subletting opportunities emerging",
            "summary": "European commercial real estate vacancy rates hit 12% in Q1 2026 (CBRE data), highest since 2010. Munich, Frankfurt, and Amsterdam seeing significant subletting activity as tech companies right-size post-remote-work. Procurement teams in lease renewals have strong negotiating position.",
            "category": "Facilities & Office", "source": "Handelsblatt", "relevance": 5,
            "action": "Request 15%+ rent reduction or rent-free period in any office lease renewal; benchmark against current market vacancy data.",
            "timestamp": (datetime.now() - timedelta(days=7)).isoformat(),
        },
        {
            "id": "demo-8", "headline": "Semiconductor shortage easing — hardware procurement window opening for H2 2026",
            "summary": "TSMC and Samsung both report increased fab capacity utilization for 2026 H2 production runs, signalling end of multi-year chip shortage cycle. Server and networking hardware lead times falling from 52 weeks back toward 14–18 weeks. Buyers who locked in futures-style agreements may find spot market competitive.",
            "category": "Hardware & Equipment", "source": "The Register", "relevance": 5,
            "action": "Defer non-urgent hardware purchases to Q3 2026 to benefit from improved availability and normalized pricing.",
            "timestamp": (datetime.now() - timedelta(days=8)).isoformat(),
        },
    ]


@app.get("/api/signals")
def signals(category: Optional[str] = None, days: int = 30, limit: int = 50):
    """Market intelligence signals from Icarus."""
    try:
        icarus_db = Path(__file__).parent / "clients" / CLIENT / "icarus_memory.db"
        if not icarus_db.exists():
            demo = _demo_signals()
            if category and category != "all":
                demo = [s for s in demo if category.lower().split(" ")[0] in (s.get("category") or "").lower()]
            return {"signals": demo[:limit], "total": len(demo), "_demo": True}

        conn = sqlite3.connect(str(icarus_db))
        conn.row_factory = sqlite3.Row
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        try:
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
        finally:
            conn.close()
        result = [dict(r) for r in rows]
        if not result:
            demo = _demo_signals()
            if category and category != "all":
                demo = [s for s in demo if category.lower().split(" ")[0] in (s.get("category") or "").lower()]
            return {"signals": demo[:limit], "total": len(demo), "_demo": True}
        return {"signals": result, "total": len(result)}
    except Exception:
        return {"signals": _demo_signals()[:limit], "total": 8, "_demo": True}


@app.post("/api/signals/scan", dependencies=[Depends(rate_limit("signals_scan", 2, 3600))])
def run_icarus_scan():
    """Trigger an Icarus RSS scan."""
    try:
        from icarus import run
        result = run(client_name=CLIENT)
        count = len(result.get("signals", [])) if isinstance(result, dict) else 0
        return {"status": "ok", "new_signals": count}
    except Exception:
        logger.exception("Icarus scan failed")
        raise HTTPException(500, "Icarus scan failed")


# ── ZEUS intelligence endpoints ───────────────────────────────────────────────

_hermes_client = None

def _get_hermes_client():
    global _hermes_client
    if _hermes_client is not None:
        return _hermes_client
    try:
        from modules.hermes_client import HermesClient
        _hermes_client = HermesClient()
        return _hermes_client
    except Exception:
        return None

def _require_hermes_client():
    client = _get_hermes_client()
    if client is None:
        raise HTTPException(503, "HermesClient unavailable")
    return client


@app.get("/api/zeus/macro")
def zeus_macro():
    """Latest ZEUS macro snapshot — market regime, VIX, sector momentum."""
    client = _require_hermes_client()
    data = client.get_zeus_macro()
    if data is None:
        return {"available": False, "message": "ZEUS has not written a macro snapshot yet."}
    return {"available": True, "macro": data}


@app.get("/api/zeus/decisions")
def zeus_decisions(limit: int = 20):
    """Recent ZEUS trade decisions — for Icarus AI screen display."""
    client = _require_hermes_client()
    decisions = client.get_zeus_decisions(limit=limit)
    signals = client.zeus_decisions_as_icarus_signals(limit=limit)
    return {
        "count": len(decisions),
        "decisions": decisions,
        "icarus_signals": signals,
    }


@app.get("/api/suppliers/{vendor_name}/zeus-risk")
def zeus_supplier_risk(vendor_name: str):
    """ZEUS/Hades compliance assessment for a specific supplier."""
    client = _require_hermes_client()
    risk = client.get_zeus_supplier_risk(vendor_name)
    if risk is None:
        return {"tracked_by_zeus": False, "vendor": vendor_name}
    return {"tracked_by_zeus": True, "vendor": vendor_name, "risk": risk}


# ── Category Strategy ─────────────────────────────────────────────────────────

@app.post("/api/strategy", dependencies=[Depends(rate_limit("strategy", 5, 60))])
async def generate_strategy(body: dict = Body(...)):
    """
    Generate procurement strategy frameworks for a spend category using Claude.
    Returns structured JSON: kraljic, pestel, swot, porter, tco, levers, recommendation.
    """
    import anthropic

    category = body.get("category", "")
    if not category:
        raise HTTPException(400, "category is required")
    # Closed vocabulary — prevents prompt injection via arbitrary category text
    if category not in TAXONOMY:
        raise HTTPException(400, "Unknown category")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured")

    # Pull real spend data for context
    conn = _conn()
    try:
        df = get_full_transaction_view(conn)
    finally:
        conn.close()

    spend_context = ""
    if not df.empty:
        sc = _spend_col(df)
        cat_df = df[df["category_mapped"] == category]
        if not cat_df.empty:
            total_spend = float(cat_df[sc].fillna(0).sum())
            suppliers = cat_df["supplier"].dropna().unique().tolist()[:10]
            spend_context = (
                f"Actual spend data: €{total_spend/1000:.0f}k total, "
                f"{len(suppliers)} active suppliers: {', '.join(suppliers[:5])}."
            )

    prompt = f"""You are a senior procurement strategist. Generate a complete procurement strategy analysis for the category: {category}.

{spend_context}

Respond ONLY with a valid JSON object using exactly this schema:
{{
  "kraljic": {{
    "quadrant": "Strategic|Leverage|Bottleneck|Non-critical",
    "spend_impact": "high|low",
    "supply_risk": "high|low",
    "rationale": "2-sentence explanation"
  }},
  "pestel": [
    "Political: ...",
    "Economic: ...",
    "Social: ...",
    "Technology: ...",
    "Environmental: ...",
    "Legal: ..."
  ],
  "swot": {{
    "strengths": ["...", "...", "..."],
    "weaknesses": ["...", "...", "..."],
    "opportunities": ["...", "...", "..."],
    "threats": ["...", "...", "..."]
  }},
  "porter": [
    "Supplier power: ...",
    "Buyer power: ...",
    "Substitutes: ...",
    "New entrants: ...",
    "Rivalry: ..."
  ],
  "tco": [
    "Acquisition: ...",
    "Operations: ...",
    "Integration: ...",
    "Exit/switching: ...",
    "Hidden costs: ..."
  ],
  "levers": ["...", "...", "...", "...", "..."],
  "recommendation": "3-4 sentence strategic recommendation with specific actions and target savings percentage."
}}

Make all content specific and actionable for the {category} procurement category in a European B2B context. Output only the JSON, no markdown."""

    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("Strategy generation returned invalid JSON")
        raise HTTPException(500, "Strategy generation returned invalid data")
    except Exception:
        logger.exception("Strategy generation failed")
        raise HTTPException(500, "Strategy generation failed")

    return {"category": category, "strategy": data}


# ── Alerts ─────────────────────────────────────────────────────────────────────

@app.get("/api/alerts")
def get_alerts():
    """
    Live notification feed: expiring contracts, budget overruns, Icarus signal count.
    Returns a list of alert objects for the TopBar notification bell.
    """
    alerts = []

    # Expiring contracts
    conn = _conn()
    try:
        contracts_df = get_expiring_contracts(conn, days=90)
        df = get_full_transaction_view(conn)
    finally:
        conn.close()

    if not contracts_df.empty:
        for _, r in contracts_df.iterrows():
            try:
                days_left = (datetime.strptime(str(r["end_date"])[:10], "%Y-%m-%d").date() - date.today()).days
            except Exception:
                days_left = 999
            vendor = str(r.get("vendor_name", "Unknown"))
            if days_left < 0:
                alerts.append({
                    "id": f"contract-expired-{r['id']}",
                    "type": "critical",
                    "title": "Contract overdue",
                    "body": f"{vendor} contract expired {abs(days_left)} days ago",
                    "action": "clm",
                })
            elif days_left <= 30:
                alerts.append({
                    "id": f"contract-expiring-{r['id']}",
                    "type": "critical",
                    "title": "Contract expiring soon",
                    "body": f"{vendor} expires in {days_left} days",
                    "action": "clm",
                })
            elif days_left <= 90:
                alerts.append({
                    "id": f"contract-warn-{r['id']}",
                    "type": "warn",
                    "title": "Contract expiring",
                    "body": f"{vendor} expires in {days_left} days",
                    "action": "clm",
                })

    # Budget overruns — categories spending >105% of budget proxy
    if not df.empty:
        sc = _spend_col(df)
        df["_spend"] = df[sc].fillna(0)
        by_cat = df.groupby("category_mapped")["_spend"].sum()
        for cat_name, spend in by_cat.items():
            # Budget proxy: same heuristic as dashboard (92% of spend as "budget")
            budget = spend * 0.92
            if spend > budget * 1.05:
                pct_over = round((spend / budget - 1) * 100, 1)
                alerts.append({
                    "id": f"budget-{cat_name}",
                    "type": "warn",
                    "title": "Budget overrun",
                    "body": f"{cat_name} {pct_over}% over budget",
                    "action": "deepdive",
                })

    # Icarus new signals (last 7 days)
    try:
        icarus_db = Path(__file__).parent / "clients" / CLIENT / "icarus_memory.db"
        if icarus_db.exists():
            iconn = sqlite3.connect(str(icarus_db))
            iconn.row_factory = sqlite3.Row
            cutoff = (datetime.now() - timedelta(days=7)).isoformat()
            try:
                count = iconn.execute(
                    "SELECT COUNT(*) FROM signals WHERE timestamp >= ?", (cutoff,)
                ).fetchone()[0]
            finally:
                iconn.close()
            if count > 0:
                alerts.append({
                    "id": "icarus-weekly",
                    "type": "info",
                    "title": "New Icarus signals",
                    "body": f"{count} new market signal{'s' if count != 1 else ''} this week",
                    "action": "icarus",
                })
    except Exception:
        pass

    return {"alerts": alerts}


# ── Static frontend ────────────────────────────────────────────────────────────
# Mount after all API routes so /api/* is never captured by static files

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {"message": "SpendLens API — frontend not built yet. Run from SpendLens_App/."}
