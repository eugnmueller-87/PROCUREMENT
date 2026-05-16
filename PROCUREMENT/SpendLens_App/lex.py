"""
Lex — Contract Lifecycle Management Engine
==========================================
Extracts clauses from PDF/DOCX contracts using Claude, then evaluates
each clause against a standard procurement playbook to produce a risk
score and required actions.

Usage:
    from lex import scan_contract
    result = scan_contract(file_bytes, filename, vendor_name, contract_type)
    # result is a dict ready to INSERT INTO contracts
"""

import os
import json
import re
import sqlite3
from datetime import datetime, date
from pathlib import Path
import anthropic

# ── Optional document parsers (graceful degradation) ──────────────────────────
try:
    import fitz          # PyMuPDF
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False

try:
    from docx import Document as DocxDocument
    DOCX_OK = True
except ImportError:
    DOCX_OK = False

CLIENT = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
MODEL  = "claude-sonnet-4-6"

# ── Playbook — acceptable / risky thresholds ──────────────────────────────────
PLAYBOOK = {
    "notice_period_days": {
        "green":  lambda v: v is not None and v >= 30,
        "yellow": lambda v: v is not None and 14 <= v < 30,
        "red":    lambda v: v is None or v < 14,
        "label":  "Termination Notice Period",
        "guidance": "Minimum 30 days required. Below 14 days is critical.",
    },
    "auto_renewal": {
        "green":  lambda v: v == 0,
        "yellow": lambda v: False,
        "red":    lambda v: v == 1,
        "label":  "Auto-Renewal",
        "guidance": "Auto-renewal clauses require active opt-out tracking.",
    },
    "auto_renewal_period": {
        # only relevant if auto_renewal is True
        "green":  lambda v: v is None or _months(v) <= 12,
        "yellow": lambda v: v is not None and 12 < _months(v) <= 24,
        "red":    lambda v: v is not None and _months(v) > 24,
        "label":  "Auto-Renewal Period",
        "guidance": "Auto-renewal >12 months creates long lock-in risk.",
    },
    "penalty_cap_pct": {
        "green":  lambda v: v is not None and v <= 10,
        "yellow": lambda v: v is not None and 10 < v <= 20,
        "red":    lambda v: v is None or v > 20,
        "label":  "Penalty / Pönale Cap",
        "guidance": "Penalty cap should not exceed 10% of contract value.",
    },
    "liability_cap": {
        "green":  lambda v: v and any(x in v.lower() for x in (
            "contract value", "fees paid", "total fees", "annual fee",
            "12 months", "twelve months", "capped", "shall not exceed",
            "limited to", "limited liability",
        )),
        "yellow": lambda v: v and len(v) > 0,
        "red":    lambda v: not v,
        "label":  "Liability Cap",
        "guidance": "Liability must be capped. Unlimited liability is critical risk.",
    },
    "jurisdiction": {
        "green":  lambda v: v and any(x in v.upper() for x in (
            "DE", "EU", "GERMANY", "DEUTSCH", "MÜNCHEN", "MUNICH",
            "BERLIN", "HAMBURG", "FRANKFURT", "KÖLN", "COLOGNE",
            "DÜSSELDORF", "STUTTGART", "AUSTRIA", "AT", "WIEN",
            "SWISS", "CH", "ZURICH", "ZÜRICH", "NETHERLANDS", "NL",
            "FRANCE", "FR", "PARIS", "ITALY", "IT", "SPAIN", "ES",
        )),
        "yellow": lambda v: v and any(x in v.upper() for x in ("UK", "ENGLAND", "SCOTLAND")),
        "red":    lambda v: not v or any(x in v.upper() for x in ("US", "USA", "DELAWARE", "NEW YORK", "CALIFORNIA", "CAYMAN", "BVI", "SINGAPORE", "HONG KONG")),
        "label":  "Jurisdiction / Governing Law",
        "guidance": "DE/EU jurisdiction preferred. Non-EU jurisdiction raises enforcement cost.",
    },
    "payment_terms": {
        "green":  lambda v: v and _days(v) >= 30,
        "yellow": lambda v: v and 14 <= _days(v) < 30,
        "red":    lambda v: not v or _days(v) < 14,
        "label":  "Payment Terms",
        "guidance": "Net 30 minimum. Shorter terms strain cash flow.",
    },
    "price_adjustment": {
        "green":  lambda v: not v,
        "yellow": lambda v: v and "cpi" in v.lower(),
        "red":    lambda v: v and any(x in v.lower() for x in ("unilateral", "sole discretion", "at any time")),
        "label":  "Price Adjustment Clause",
        "guidance": "Unilateral price changes are high risk. CPI-indexed is acceptable.",
    },
    "end_date": {
        "green":  lambda v: v and _days_until(v) > 90,
        "yellow": lambda v: v and 30 <= _days_until(v) <= 90,
        "red":    lambda v: not v or _days_until(v) < 30,
        "label":  "Contract Expiry",
        "guidance": "Contracts expiring within 30 days require immediate action.",
    },
}

MISSING_CLAUSE_PENALTIES = {
    "end_date":          2.0,
    "notice_period_days": 1.5,
    "liability_cap":     2.0,
    "jurisdiction":      1.0,
    "payment_terms":     0.5,
}


def _months(text: str) -> int:
    if not text:
        return 0
    t = text.lower()
    m = re.search(r"(\d+)\s*month", t)
    y = re.search(r"(\d+)\s*year", t)
    return (int(m.group(1)) if m else 0) + (int(y.group(1)) * 12 if y else 0)


def _days(text: str) -> int:
    if not text:
        return 0
    t = text.lower()
    m = re.search(r"(\d+)\s*day", t)
    if m:
        return int(m.group(1))
    if "net 30" in t:
        return 30
    if "net 14" in t:
        return 14
    if "net 60" in t:
        return 60
    if "immediate" in t or "upon receipt" in t:
        return 0
    return 30  # default assumption


def _days_until(date_str: str) -> int:
    if not date_str:
        return 999
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        return (d - date.today()).days
    except Exception:
        return 999


# ── Text extraction ────────────────────────────────────────────────────────────

def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from PDF or DOCX bytes."""
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        if PYMUPDF_OK:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            pages = [page.get_text() for page in doc]
            return "\n\n".join(pages)
        # fallback: raw byte decode (rough but functional)
        text = file_bytes.decode("latin-1", errors="ignore")
        return re.sub(r"[^\x20-\x7E\n]", " ", text)

    if ext in (".docx", ".doc"):
        if DOCX_OK:
            import io
            doc = DocxDocument(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return file_bytes.decode("utf-8", errors="ignore")

    # Plain text fallback
    return file_bytes.decode("utf-8", errors="ignore")


def _chunk_text(text: str, max_chars: int = 12000) -> str:
    """Return the first max_chars of text — contracts are usually front-loaded with key clauses."""
    return text[:max_chars]


# ── Claude extraction ──────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """You are a procurement contract analyst. Extract key clauses from the contract text below and return ONLY a valid JSON object with these exact fields:

{
  "start_date": "YYYY-MM-DD or null",
  "end_date": "YYYY-MM-DD or null",
  "notice_period_days": integer_or_null,
  "auto_renewal": true_or_false,
  "auto_renewal_period": "e.g. 12 months or null",
  "penalty_cap_pct": float_or_null,
  "liability_cap": "clause text summary or null",
  "price_adjustment": "clause text summary or null",
  "jurisdiction": "country/city or null",
  "sla_terms": "SLA summary or null",
  "payment_terms": "e.g. Net 30 or null",
  "termination_rights": "termination for convenience summary or null",
  "contract_value": "e.g. EUR 120,000 or null",
  "missing_clauses": ["list", "of", "clauses", "not", "found"],
  "executive_summary": "2-3 sentence summary of what this contract is about and key commercial terms"
}

Rules:
- Extract only what is explicitly stated. Do not infer or assume.
- For dates, convert to YYYY-MM-DD format.
- For notice_period_days, convert any unit (weeks, months) to days.
- For penalty_cap_pct, express as a percentage number (e.g. 10 for 10%).
- missing_clauses should list clause types that could not be found in the text.
- Return ONLY the JSON. No explanation. No markdown code blocks.

CONTRACT TEXT:
"""


def _call_claude(text: str, contract_type: str) -> dict:
    prompt = EXTRACTION_PROMPT + text
    if contract_type:
        prompt += f"\n\nContract type context: {contract_type}"

    msg = CLIENT.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON object from response
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
        return {}


# ── Risk engine ────────────────────────────────────────────────────────────────

def _evaluate_playbook(clauses: dict) -> tuple[dict, float, str, list[str]]:
    """
    Run extracted clauses against PLAYBOOK rules.
    Returns:
      flags        — dict of clause_key -> color (green/yellow/red)
      risk_score   — 1.0-10.0
      risk_level   — Low/Medium/High/Critical
      actions      — list of required action strings
    """
    flags   = {}
    actions = []
    red_count    = 0
    yellow_count = 0

    for key, rules in PLAYBOOK.items():
        val = clauses.get(key)
        if rules["red"](val):
            flags[key] = "red"
            red_count += 1
            actions.append(f"[CRITICAL] {rules['label']}: {rules['guidance']}")
        elif rules["green"](val):
            flags[key] = "green"
        elif rules["yellow"](val):
            flags[key] = "yellow"
            yellow_count += 1
            actions.append(f"[REVIEW] {rules['label']}: {rules['guidance']}")
        else:
            flags[key] = "green"

    # Missing clause penalties
    missing = clauses.get("missing_clauses") or []
    for clause in missing:
        c = clause.lower().replace(" ", "_").replace("-", "_")
        for key, penalty in MISSING_CLAUSE_PENALTIES.items():
            if key in c or c in key:
                red_count += penalty
                actions.append(f"[MISSING] {clause} — add this clause before signing")

    # Score: base 3, +1 per yellow, +2 per red, capped at 10
    score = min(10.0, 1.0 + yellow_count * 1.0 + red_count * 1.5)
    score = max(1.0, score)

    if score <= 3.5:
        level = "Low"
    elif score <= 6.0:
        level = "Medium"
    elif score <= 8.0:
        level = "High"
    else:
        level = "Critical"

    return flags, round(score, 1), level, actions


# ── Main entry point ───────────────────────────────────────────────────────────

def scan_contract(
    file_bytes: bytes,
    filename: str,
    vendor_name: str = "",
    contract_type: str = "MSA",
) -> dict:
    """
    Full contract scan pipeline:
      1. Extract text from PDF/DOCX
      2. Send to Claude for clause extraction
      3. Run playbook risk evaluation
      4. Return structured dict ready for DB insert

    Returns dict with all contracts table columns.
    """
    # Step 1: text extraction
    text = extract_text(file_bytes, filename)
    chunk = _chunk_text(text, max_chars=14000)

    # Step 2: Claude clause extraction
    clauses = _call_claude(chunk, contract_type)

    # Step 3: Risk evaluation
    flags, risk_score, risk_level, actions = _evaluate_playbook(clauses)

    # Step 4: Build risk narrative
    red_flags = [k for k, v in flags.items() if v == "red"]
    risk_summary = clauses.get("executive_summary", "")
    if red_flags:
        risk_summary += (
            f" Risk assessment: {len(red_flags)} critical clause issue(s) identified "
            f"({', '.join(PLAYBOOK[k]['label'] for k in red_flags if k in PLAYBOOK)})."
        )

    missing_str = ", ".join(clauses.get("missing_clauses") or [])

    return {
        "scanned_at":           datetime.now().isoformat(),
        "filename":             filename,
        "vendor_name":          vendor_name or None,
        "contract_type":        contract_type,
        "start_date":           clauses.get("start_date"),
        "end_date":             clauses.get("end_date"),
        "notice_period_days":   clauses.get("notice_period_days"),
        "auto_renewal":         1 if clauses.get("auto_renewal") else 0,
        "auto_renewal_period":  clauses.get("auto_renewal_period"),
        "penalty_cap_pct":      clauses.get("penalty_cap_pct"),
        "liability_cap":        clauses.get("liability_cap"),
        "price_adjustment":     clauses.get("price_adjustment"),
        "jurisdiction":         clauses.get("jurisdiction"),
        "sla_terms":            clauses.get("sla_terms"),
        "payment_terms":        clauses.get("payment_terms"),
        "termination_rights":   clauses.get("termination_rights"),
        "missing_clauses":      missing_str,
        "risk_score":           risk_score,
        "risk_level":           risk_level,
        "risk_summary":         risk_summary,
        "required_actions":     json.dumps(actions),
        "clause_flags":         json.dumps(flags),
        "claude_raw":           json.dumps(clauses),
        # Extra field not in DB — passed through to UI
        "_clauses":             clauses,
    }


def save_contract(conn: sqlite3.Connection, result: dict) -> int:
    """Insert a scan result into the contracts table. Returns the new contract id."""
    fields = [k for k in result if not k.startswith("_")]
    placeholders = ", ".join("?" for _ in fields)
    cols = ", ".join(fields)
    values = [result[k] for k in fields]

    cursor = conn.execute(
        f"INSERT INTO contracts ({cols}) VALUES ({placeholders})", values
    )
    conn.commit()

    # Back-propagate key fields to vendors table
    vendor = result.get("vendor_name")
    if vendor:
        conn.execute("""
            UPDATE vendors SET
                lex_contract_id        = ?,
                lex_contract_risk_score = ?,
                lex_contract_risk_level = ?,
                lex_contract_end        = ?,
                lex_notice_period_days  = ?,
                lex_auto_renewal        = ?,
                lex_scan_date           = ?
            WHERE vendor_name = ?
        """, (
            cursor.lastrowid,
            result.get("risk_score"),
            result.get("risk_level"),
            result.get("end_date"),
            result.get("notice_period_days"),
            result.get("auto_renewal"),
            datetime.now().strftime("%Y-%m-%d"),
            vendor,
        ))
        conn.commit()

    return cursor.lastrowid
