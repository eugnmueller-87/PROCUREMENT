"""
flag_engine.py — SpendLens Compliance & Risk Flag Engine
=========================================================
Takes the enriched DataFrame from category_mapper.py and derives
all compliance and risk flags per transaction.

HOW IT WORKS (step by step):
─────────────────────────────
1. SCAN         — detect which fields are available in this dataset
                  never assumes a column exists, reports data coverage

2. PO FLAGS     — classify each transaction's PO status
                  With PO / Blanket PO / No PO / Unknown

3. CONTRACT     — classify contract status per vendor
                  Under Contract / Expired / No Contract / Unknown

4. MAVERICK     — flag off-contract or off-PO spend above threshold
                  configurable per client, honest about data gaps

5. SHADOW IT    — detect unauthorized SaaS/IT spend
                  multi-signal: category + amount + pattern + cost center

6. FREELANCER   — detect spend under personal names
                  multi-signal: description + name pattern + cost center + amount

7. SPEND PATTERN — classify transaction cadence per vendor
                  Recurring / Blanket PO / One-off / Irregular

8. CATALOGUE    — detect catalogue vs off-catalogue purchases
                  based on catalogue ID field or description signals

9. COVERAGE     — report what % of flags could be fully derived
                  vs marked Unknown due to missing fields

Philosophy: be honest about data gaps.
A missing PO column → "Unknown", not "No PO".
Never punish a company for their ERP's export format.
"""

import pandas as pd
import numpy as np
import re
from datetime import datetime, date
from typing import Optional


# ── DEFAULT CONFIG ─────────────────────────────────────────────────────────────
# Used when no config.json is provided. All values are overridable per client.

DEFAULT_CONFIG = {
    "maverick": {
        "require_po": True,           # flag as maverick if no PO
        "require_contract": False,     # flag as maverick if no contract
        "min_amount_for_po": 1000,    # below this amount, missing PO is OK
    },
    "shadow_it": {
        "enabled": True,
        "max_amount_per_month": 2000,  # typical SaaS subscription range
        "min_amount_per_month": 50,
        "flag_categories": [
            "Cloud & Compute", "IT Software & SaaS", "AI/ML APIs & Data"
        ],
    },
    "freelancer": {
        "enabled": True,
        "description_keywords": [
            "honorar", "freiberufler", "freelance", "honorarrechnung",
            "contractor", "self-employed", "freie mitarbeit", "werkvertrag"
        ],
        "hr_cost_centers": ["hr", "people", "talent", "recruiting", "personal"],
        "max_single_invoice": 50000,   # above this, probably not a freelancer
    },
    "recurring": {
        "min_occurrences": 3,          # min transactions to call it recurring
        "amount_tolerance_pct": 15,    # how much amount can vary and still be recurring
    }
}

# ── COMPANY SUFFIXES (used for personal name detection) ───────────────────────
COMPANY_SUFFIXES = [
    "gmbh", "ag", "se", "inc", "ltd", "llc", "corp", "co", "kg",
    "group", "holding", "international", "services", "solutions",
    "consulting", "gmbh & co", "ug", "bv", "sas", "sarl", "plc",
    "technologies", "tech", "systems", "partners", "associates"
]


# ── 1. FIELD SCANNER ──────────────────────────────────────────────────────────

def scan_available_fields(df: pd.DataFrame) -> dict:
    """
    Detect which standard fields are available in the dataset.
    Returns a dict of field_name → column_name (or None if not found).

    This is the foundation — every subsequent flag function checks here
    before trying to access a column, so we never crash on missing data.
    """
    # Standard field candidates — ordered by priority
    field_candidates = {
        "supplier":     ["supplier", "vendor", "lieferant", "kreditor", "company"],
        "spend":        ["spend", "amount", "total", "betrag", "invoice_total"],
        "date":         ["date", "invoice_date", "datum", "posting_date", "buchungsdatum"],
        "description":  ["description", "text", "booking_text", "verwendungszweck", "memo", "notes"],
        "po_number":    ["po_number", "purchase_order", "bestellnummer", "po", "order_number"],
        "contract_id":  ["contract_id", "contract_ref", "contract_number", "vertragsnummer"],
        "contract_end": ["contract_end", "expiry_date", "end_date", "vertragslaufzeit"],
        "cost_center":  ["cost_center", "kostenstelle", "department", "dept", "abteilung"],
        "gl_account":   ["gl_account", "gl", "konto", "account", "sachkonto"],
        "catalogue_id": ["catalogue_id", "catalog_id", "item_number", "article_number"],
        "region":       ["region", "country", "land", "location"],
        "category":     ["category", "category_mapped", "warengruppe"],
    }

    available = {}
    cols_lower = {col.lower(): col for col in df.columns}

    for field, candidates in field_candidates.items():
        found = None
        for candidate in candidates:
            if candidate in cols_lower:
                found = cols_lower[candidate]
                break
        available[field] = found

    # Report what we found
    found_fields = [f for f, col in available.items() if col is not None]
    missing_fields = [f for f, col in available.items() if col is None]

    print(f"  📋 Fields found ({len(found_fields)}): {', '.join(found_fields)}")
    if missing_fields:
        print(f"  ⚠ Fields not found ({len(missing_fields)}): {', '.join(missing_fields)}")
        print(f"     → Flags depending on these fields will be marked 'Unknown'")

    return available


# ── 2. PO STATUS FLAG ─────────────────────────────────────────────────────────

def flag_po_status(df: pd.DataFrame, fields: dict) -> pd.Series:
    """
    Classify PO status per transaction.

    With PO      — PO number present and looks valid
    Blanket PO   — same PO number appears on multiple transactions (framework)
    No PO        — PO column exists but value is empty/null
    Unknown      — PO column not in dataset at all

    Why the distinction between No PO and Unknown matters:
    A company whose SAP export doesn't include PO numbers shouldn't be
    flagged as 100% maverick. That's a data gap, not a compliance failure.
    """
    po_col = fields.get("po_number")

    # No PO column in dataset at all → Unknown
    if not po_col:
        print("  ℹ PO column not found — po_status set to 'Unknown' for all rows")
        return pd.Series("Unknown", index=df.index)

    result = pd.Series("Unknown", index=df.index)

    # Count how many times each PO number appears (for blanket PO detection)
    po_counts = df[po_col].value_counts()

    for idx, row in df.iterrows():
        po_val = row[po_col]

        if pd.isna(po_val) or str(po_val).strip() in ["", "nan", "None", "0"]:
            result[idx] = "No PO"
        else:
            po_str = str(po_val).strip()
            # Blanket PO: same PO number on 3+ transactions
            if po_counts.get(po_str, 0) >= 3:
                result[idx] = "Blanket PO"
            else:
                result[idx] = "With PO"

    counts = result.value_counts().to_dict()
    print(f"  ✅ PO Status: {counts}")
    return result


# ── 3. CONTRACT STATUS FLAG ───────────────────────────────────────────────────

def flag_contract_status(df: pd.DataFrame, fields: dict) -> pd.Series:
    """
    Classify contract status per transaction.

    Under Contract  — contract_id present AND contract_end is in the future
    Expired         — contract_id present BUT contract_end is in the past
    No Contract     — contract columns exist but values are empty
    Unknown         — contract columns not in dataset

    Uses today's date for expiry comparison.
    """
    contract_col = fields.get("contract_id")
    expiry_col = fields.get("contract_end")
    today = pd.Timestamp(datetime.today())

    # No contract columns at all → Unknown
    if not contract_col and not expiry_col:
        print("  ℹ Contract columns not found — contract_status set to 'Unknown'")
        return pd.Series("Unknown", index=df.index)

    result = pd.Series("Unknown", index=df.index)

    for idx, row in df.iterrows():
        has_contract = False
        is_expired = False

        # Check contract ID
        if contract_col:
            contract_val = row.get(contract_col)
            has_contract = not (pd.isna(contract_val) or
                                str(contract_val).strip() in ["", "nan", "None"])

        # Check expiry date
        if expiry_col and has_contract:
            expiry_val = row.get(expiry_col)
            if not pd.isna(expiry_val):
                try:
                    expiry_date = pd.Timestamp(expiry_val)
                    is_expired = expiry_date < today
                except Exception:
                    pass  # unparseable date → treat as unknown expiry

        # Assign status
        if has_contract:
            result[idx] = "Expired" if is_expired else "Under Contract"
        elif contract_col:
            # Column exists but value empty → explicitly no contract
            result[idx] = "No Contract"
        # else: stays Unknown (column didn't exist)

    counts = result.value_counts().to_dict()
    print(f"  ✅ Contract Status: {counts}")
    return result


# ── 4. MAVERICK SPEND FLAG ────────────────────────────────────────────────────

def flag_maverick(df: pd.DataFrame, fields: dict,
                  po_status: pd.Series, contract_status: pd.Series,
                  config: dict = None) -> pd.Series:
    """
    Flag transactions as maverick spend.

    Maverick = spend that bypasses approved procurement channels.
    Definition is configurable — different companies define it differently.

    Default logic:
    - No PO AND spend above min_amount_for_po threshold → Maverick
    - Expired contract AND spend above threshold → Maverick
    - Unknown PO/contract → Not flagged (honest about data gaps)
    - Below threshold → Not flagged (petty cash / small purchases)

    Returns True/False per row. Unknown cases return None.
    """
    cfg = (config or DEFAULT_CONFIG).get("maverick", DEFAULT_CONFIG["maverick"])
    spend_col = fields.get("spend")
    threshold = cfg.get("min_amount_for_po", 1000)
    require_po = cfg.get("require_po", True)
    require_contract = cfg.get("require_contract", False)

    result = pd.Series(None, index=df.index, dtype=object)

    for idx in df.index:
        po = po_status[idx]
        contract = contract_status[idx]
        spend = df.loc[idx, spend_col] if spend_col else None

        # Skip if we can't determine spend amount
        if spend is None or pd.isna(spend):
            result[idx] = None
            continue

        is_maverick = False

        # PO-based check
        if require_po and po == "No PO" and float(spend) >= threshold:
            is_maverick = True

        # Contract-based check
        if require_contract and contract == "Expired":
            is_maverick = True

        # Unknown data → don't flag, but don't clear either
        if po == "Unknown" and contract == "Unknown":
            result[idx] = None  # genuinely can't tell
        else:
            result[idx] = is_maverick

    true_count = (result == True).sum()
    unknown_count = result.isna().sum()
    print(f"  ✅ Maverick: {true_count} flagged | {unknown_count} unknown (data gap)")
    return result


# ── KNOWN ENTERPRISE VENDORS ──────────────────────────────────────────────────
# Well-known companies that should never be flagged as shadow IT or freelancers
# regardless of how their name appears in the data (no suffix, short name etc.)
# Extend this list via config.json for client-specific known vendors.

KNOWN_ENTERPRISE_VENDORS = {
    # Cloud & IT
    "aws", "amazon web services", "google cloud", "gcp", "microsoft", "azure",
    "sap", "salesforce", "oracle", "ibm", "servicenow", "atlassian", "workday",
    # Telecom
    "deutsche telekom", "telekom", "vodafone", "telefonica", "o2", "dt",
    # Consulting & Legal
    "mckinsey", "bcg", "bain", "deloitte", "pwc", "kpmg", "ey", "accenture",
    "freshfields", "linklaters", "clifford chance", "cms", "hogan lovells",
    # Facilities & Logistics
    "iss", "cbre", "jll", "dhl", "db schenker", "ups", "fedex", "bcd travel",
    "lufthansa", "swiss", "austrian", "air france", "british airways",
    # HR & Staffing
    "randstad", "adecco", "hays", "manpower", "personio", "workday",
    # Finance & Insurance
    "allianz", "axa", "munich re", "zurich", "generali",
    # Office & Facilities suppliers
    "lyreco", "staples", "buromarkt", "otto office",
}


# ── 5. SHADOW IT FLAG ─────────────────────────────────────────────────────────

def flag_shadow_it(df: pd.DataFrame, fields: dict,
                   po_status: pd.Series, config: dict = None) -> pd.Series:
    """
    Detect suspected unauthorized SaaS/IT spend.

    Shadow IT = IT-related tools purchased outside central IT procurement.
    Common pattern: individual employees expensing SaaS subscriptions.

    KEY RULE: If a transaction has a PO → not shadow IT.
    A vendor with an approved PO went through procurement. Full stop.

    Multi-signal detection (only applies when no PO):
    - Category is IT-adjacent (Cloud, SaaS, AI/ML) — strong signal
    - Amount in typical SaaS subscription range (€50–€2000/month) — medium
    - No PO — required (gate condition, not just a signal)
    - Cost center is NOT central IT — medium signal
    - Description mentions "subscription", "license", "plan" — medium signal
    - Vendor NOT in known enterprise vendor list — medium signal

    Returns True/False per row.
    """
    cfg = (config or DEFAULT_CONFIG).get("shadow_it", DEFAULT_CONFIG["shadow_it"])

    if not cfg.get("enabled", True):
        return pd.Series(False, index=df.index)

    spend_col = fields.get("spend")
    category_col = fields.get("category") or "category_mapped"
    description_col = fields.get("description")
    cost_center_col = fields.get("cost_center")
    supplier_col = fields.get("supplier")

    flag_categories = cfg.get("flag_categories", DEFAULT_CONFIG["shadow_it"]["flag_categories"])
    min_amt = cfg.get("min_amount_per_month", 50)
    max_amt = cfg.get("max_amount_per_month", 2000)

    saas_keywords = [
        "subscription", "license", "licence", "plan", "monthly", "annual",
        "abonnement", "lizenz", "software as a service", "saas", "cloud plan"
    ]

    result = pd.Series(False, index=df.index)

    for idx, row in df.iterrows():

        # ── GATE: With PO or Blanket PO → never shadow IT ──
        # A procurement-approved purchase cannot be shadow IT by definition.
        if po_status[idx] in ["With PO", "Blanket PO"]:
            result[idx] = False
            continue

        # ── GATE: Known enterprise vendor → never shadow IT ──
        if supplier_col and supplier_col in df.columns:
            vendor = str(row.get(supplier_col, "")).lower().strip()
            if any(kev in vendor for kev in KNOWN_ENTERPRISE_VENDORS):
                result[idx] = False
                continue

        signals = 0

        # Signal 1 (strong): IT-adjacent category
        if category_col in df.columns:
            cat = str(row.get(category_col, ""))
            if any(fc.lower() in cat.lower() for fc in flag_categories):
                signals += 2

        # Signal 2 (medium): Amount in SaaS range
        if spend_col:
            spend = row.get(spend_col)
            if spend and not pd.isna(spend):
                if min_amt <= float(spend) <= max_amt:
                    signals += 1

        # Signal 3 (medium): SaaS keywords in description
        if description_col and description_col in df.columns:
            desc = str(row.get(description_col, "")).lower()
            if any(kw in desc for kw in saas_keywords):
                signals += 1

        # Signal 4 (medium): Cost center is not central IT
        if cost_center_col and cost_center_col in df.columns:
            cc = str(row.get(cost_center_col, "")).lower()
            it_centers = ["it", "information technology", "tech", "infrastructure"]
            if not any(it in cc for it in it_centers):
                signals += 1

        # Threshold: need at least 3 signals
        result[idx] = signals >= 3

    flagged = result.sum()
    print(f"  ✅ Shadow IT: {flagged} transactions flagged")
    return result


# ── 6. FREELANCER FLAG ────────────────────────────────────────────────────────

def flag_freelancer(df: pd.DataFrame, fields: dict,
                    config: dict = None) -> pd.Series:
    """
    Detect spend under personal names (freelancers).

    The challenge: we can't reliably detect personal names without legal
    entity suffixes. So we use multi-signal detection instead.

    KEY RULE: Known enterprise vendors are never freelancers.
    ISS, Lufthansa, Randstad etc. have no GmbH suffix in common usage
    but are clearly not personal names — whitelist guards against this.

    Signals:
    - Description contains freelancer keywords (Honorar, Freiberufler etc.) — strong
    - Vendor name has NO company suffix AND not a known enterprise vendor — medium
    - Vendor name looks like 1-2 words with no suffix — medium
    - Cost center is HR/People/Talent — medium

    Threshold: 1 strong OR 2+ medium signals → flag as freelancer.
    """
    cfg = (config or DEFAULT_CONFIG).get("freelancer", DEFAULT_CONFIG["freelancer"])

    if not cfg.get("enabled", True):
        return pd.Series(False, index=df.index)

    supplier_col = fields.get("supplier")
    description_col = fields.get("description")
    cost_center_col = fields.get("cost_center")

    keywords = [kw.lower() for kw in cfg.get("description_keywords",
                DEFAULT_CONFIG["freelancer"]["description_keywords"])]
    hr_centers = cfg.get("hr_cost_centers",
                         DEFAULT_CONFIG["freelancer"]["hr_cost_centers"])

    result = pd.Series(False, index=df.index)

    for idx, row in df.iterrows():

        # ── GATE: Known enterprise vendor → never a freelancer ──
        if supplier_col and supplier_col in df.columns:
            vendor_raw = str(row.get(supplier_col, "")).lower().strip()
            if any(kev in vendor_raw for kev in KNOWN_ENTERPRISE_VENDORS):
                result[idx] = False
                continue

        strong_signals = 0
        medium_signals = 0

        # Strong signal: freelancer keywords in description
        if description_col and description_col in df.columns:
            desc = str(row.get(description_col, "")).lower()
            if any(kw in desc for kw in keywords):
                strong_signals += 1

        # Medium signals: vendor name analysis
        if supplier_col and supplier_col in df.columns:
            vendor = str(row.get(supplier_col, "")).lower().strip()
            has_suffix = any(suffix in vendor for suffix in COMPANY_SUFFIXES)

            # No company suffix → medium signal
            if not has_suffix and vendor not in ["", "unknown", "nan"]:
                medium_signals += 1

            # Looks like 1-2 word personal name with no suffix → medium signal
            words = [w for w in vendor.split() if len(w) > 1]
            if 1 <= len(words) <= 2 and not has_suffix:
                medium_signals += 1

        # Medium signal: HR/People cost center
        if cost_center_col and cost_center_col in df.columns:
            cc = str(row.get(cost_center_col, "")).lower()
            if any(hr in cc for hr in hr_centers):
                medium_signals += 1

        # Threshold: 1 strong OR 2+ medium
        result[idx] = (strong_signals >= 1) or (medium_signals >= 2)

    flagged = result.sum()
    print(f"  ✅ Freelancer: {flagged} transactions flagged")
    return result


# ── 7. SPEND PATTERN ──────────────────────────────────────────────────────────

def flag_spend_pattern(df: pd.DataFrame, fields: dict,
                       po_status: pd.Series, config: dict = None) -> pd.Series:
    """
    Classify transaction cadence per vendor.

    Recurring   — same vendor, similar amount, regular timing (monthly/quarterly)
    Blanket PO  — same PO number across multiple transactions
    One-off     — single transaction from this vendor
    Irregular   — multiple transactions, no clear pattern

    Requires date column for timing analysis.
    Falls back to transaction count only if date not available.
    """
    cfg = (config or DEFAULT_CONFIG).get("recurring", DEFAULT_CONFIG["recurring"])
    supplier_col = fields.get("supplier")
    spend_col = fields.get("spend")
    date_col = fields.get("date")

    min_occurrences = cfg.get("min_occurrences", 3)
    tolerance = cfg.get("amount_tolerance_pct", 15) / 100

    result = pd.Series("Unknown", index=df.index)

    if not supplier_col:
        print("  ⚠ No supplier column — spend_pattern set to 'Unknown'")
        return result

    for vendor in df[supplier_col].dropna().unique():
        vendor_mask = df[supplier_col] == vendor
        vendor_df = df[vendor_mask].copy()
        vendor_indices = vendor_df.index

        # Blanket PO — already detected in po_status
        if (po_status[vendor_indices] == "Blanket PO").any():
            result[vendor_indices] = "Blanket PO"
            continue

        # One-off — single transaction
        if len(vendor_df) == 1:
            result[vendor_indices] = "One-off"
            continue

        # Check for recurring pattern
        is_recurring = False
        if len(vendor_df) >= min_occurrences and spend_col:
            amounts = vendor_df[spend_col].dropna()
            if len(amounts) >= min_occurrences:
                mean_amt = amounts.mean()
                # All amounts within tolerance of the mean → recurring
                if mean_amt > 0:
                    deviation = (amounts - mean_amt).abs() / mean_amt
                    if (deviation <= tolerance).all():
                        # Also check timing regularity if date available
                        if date_col and date_col in df.columns:
                            dates = pd.to_datetime(vendor_df[date_col], errors="coerce").dropna()
                            if len(dates) >= 2:
                                dates_sorted = dates.sort_values()
                                gaps = dates_sorted.diff().dropna().dt.days
                                # Regular if gaps are roughly monthly (25-35 days)
                                # or quarterly (80-100 days)
                                mean_gap = gaps.mean()
                                gap_std = gaps.std()
                                if gap_std < mean_gap * 0.3:  # consistent timing
                                    is_recurring = True
                        else:
                            is_recurring = True  # amounts consistent, no date to check

        if is_recurring:
            result[vendor_indices] = "Recurring"
        else:
            result[vendor_indices] = "Irregular"

    counts = result.value_counts().to_dict()
    print(f"  ✅ Spend Pattern: {counts}")
    return result


# ── 8. CATALOGUE FLAG ─────────────────────────────────────────────────────────

def flag_catalogue(df: pd.DataFrame, fields: dict) -> pd.Series:
    """
    Detect catalogue vs off-catalogue purchases.

    Catalogue    — catalogue_id field present and populated
    Off-catalogue — catalogue column exists but empty
    Unknown      — no catalogue column in dataset

    Catalogue purchasing means items were bought through a pre-approved
    vendor catalogue (SAP SRM, Ariba, Coupa catalogue etc.)
    This is the gold standard for controlled spend.
    """
    catalogue_col = fields.get("catalogue_id")

    if not catalogue_col:
        print("  ℹ No catalogue column — catalogue_flag set to 'Unknown'")
        return pd.Series("Unknown", index=df.index)

    result = df[catalogue_col].apply(
        lambda v: "Catalogue" if (
            not pd.isna(v) and str(v).strip() not in ["", "nan", "None", "0"]
        ) else "Off-catalogue"
    )

    counts = result.value_counts().to_dict()
    print(f"  ✅ Catalogue: {counts}")
    return result


# ── 9. COVERAGE REPORT ────────────────────────────────────────────────────────

def generate_coverage_report(df: pd.DataFrame, fields: dict) -> dict:
    """
    Report what % of flags could be fully derived vs marked Unknown.

    This is the transparency layer — the CFO sees exactly how much
    of the analysis is based on complete data vs data gaps.

    Returns a dict like:
    {
      "po_status":       {"complete": 85%, "unknown": 15%},
      "contract_status": {"complete": 0%,  "unknown": 100%},  ← column missing
      ...
    }
    """
    total = len(df)
    report = {}

    flag_cols = [
        "po_status", "contract_status", "maverick_flag",
        "shadow_it_flag", "freelancer_flag", "spend_pattern", "catalogue_flag"
    ]

    for col in flag_cols:
        if col in df.columns:
            unknown_count = df[col].isna().sum() + (df[col] == "Unknown").sum()
            complete_pct = round((total - unknown_count) / total * 100, 1)
            report[col] = {
                "complete_pct": complete_pct,
                "unknown_pct": round(100 - complete_pct, 1),
                "total_rows": total
            }

    return report


# ── 10. FULL PIPELINE ─────────────────────────────────────────────────────────

def run_flag_engine(df: pd.DataFrame, config: dict = None) -> tuple[pd.DataFrame, dict]:
    """
    Full flag engine pipeline.

    Takes enriched DataFrame (output of category_mapper.py) and adds
    all compliance and risk flag columns.

    Usage:
        flagged_df, coverage = run_flag_engine(enriched_df)
        flagged_df, coverage = run_flag_engine(enriched_df, config=client_config)

    Args:
        df      — enriched DataFrame with category_mapped column
        config  — optional client config dict (uses DEFAULT_CONFIG if None)

    Returns:
        flagged_df  — original df + all flag columns
        coverage    — data coverage report (% complete vs unknown per flag)
    """
    print("\n── Flag Engine Pipeline ────────────────────────────────")

    df = df.copy()

    # Step 1: Scan available fields
    print("Step 1: Scanning available fields...")
    fields = scan_available_fields(df)

    # Step 2: PO Status
    print("Step 2: Flagging PO status...")
    df["po_status"] = flag_po_status(df, fields)

    # Step 3: Contract Status
    print("Step 3: Flagging contract status...")
    df["contract_status"] = flag_contract_status(df, fields)

    # Step 4: Maverick Spend
    print("Step 4: Flagging maverick spend...")
    df["maverick_flag"] = flag_maverick(df, fields, df["po_status"],
                                         df["contract_status"], config)

    # Step 5: Shadow IT
    print("Step 5: Flagging shadow IT...")
    df["shadow_it_flag"] = flag_shadow_it(df, fields, df["po_status"], config)

    # Step 6: Freelancer
    print("Step 6: Flagging freelancers...")
    df["freelancer_flag"] = flag_freelancer(df, fields, config)

    # Step 7: Spend Pattern
    print("Step 7: Classifying spend patterns...")
    df["spend_pattern"] = flag_spend_pattern(df, fields, df["po_status"], config)

    # Step 8: Catalogue
    print("Step 8: Flagging catalogue spend...")
    df["catalogue_flag"] = flag_catalogue(df, fields)

    # Step 9: Coverage Report
    print("Step 9: Generating data coverage report...")
    coverage = generate_coverage_report(df, fields)

    print("\n── Coverage Report ─────────────────────────────────────")
    for flag, stats in coverage.items():
        bar = "█" * int(stats["complete_pct"] / 5) + "░" * (20 - int(stats["complete_pct"] / 5))
        print(f"  {flag:<20} [{bar}] {stats['complete_pct']}% complete")

    print("── Done ✅ ─────────────────────────────────────────────\n")
    return df, coverage


# ── QUICK TEST ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Test with a realistic accounting dataset that has mixed data quality —
    some rows have POs, some don't, some have contracts, some don't.
    This simulates what a real SAP export looks like.
    """
    test_df = pd.DataFrame({
        "supplier": [
            "WeWork GmbH", "WeWork GmbH", "ISS Deutschland", "Amazon Web Services",
            "Amazon Web Services", "SAP SE", "J. Schmidt", "Anna Becker Consulting",
            "Lufthansa", "Freshfields Bruckhaus", "Randstad Deutschland",
            "ShadowTool Inc", "ShadowTool Inc", "Deutsche Telekom AG"
        ],
        "spend": [
            12500, 12500, 3200, 45000,
            47000, 8500, 4800, 3200,
            1800, 15000, 6000,
            299, 299, 2800
        ],
        "date": [
            "2026-01-01", "2026-02-01", "2026-01-15", "2026-01-31",
            "2026-02-28", "2026-01-10", "2026-02-15", "2026-03-01",
            "2026-01-20", "2026-02-10", "2026-01-05",
            "2026-01-15", "2026-02-15", "2026-01-10"
        ],
        "description": [
            "Miete Büro Berlin Mitte", "Miete Büro Berlin Mitte",
            "Reinigungsservice Q1", "AWS Compute EC2 January",
            "AWS Compute EC2 February", "SAP License Annual",
            "Honorarrechnung Januar", "Freiberufliche Beratung",
            "Flug FRA-LHR Business", "Legal Advisory M&A",
            "Temp Staff IT", "Software subscription plan",
            "Software subscription plan", "Telekommunikation Q1"
        ],
        "po_number": [
            None, None, "PO-2026-001", "PO-2026-002",
            "PO-2026-002", "PO-2026-003", None, None,
            "PO-2026-004", "PO-2026-005", "PO-2026-006",
            None, None, "PO-2026-007"
        ],
        "contract_end": [
            "2027-12-31", "2027-12-31", "2027-06-30", "2027-12-31",
            "2027-12-31", "2026-03-31", None, None,
            None, "2026-08-31", "2026-12-31",
            None, None, "2027-12-31"
        ],
        "cost_center": [
            "Facilities", "Facilities", "Facilities", "IT",
            "IT", "IT", "HR", "HR",
            "Sales", "Legal", "HR",
            "Marketing", "Marketing", "IT"
        ],
        "category_mapped": [
            "Real Estate", "Real Estate", "Facilities & Office", "Cloud & Compute",
            "Cloud & Compute", "IT Software & SaaS", "Recruitment & HR", "Recruitment & HR",
            "Travel & Expenses", "Professional Services", "Recruitment & HR",
            "IT Software & SaaS", "IT Software & SaaS", "Telecom & Voice"
        ]
    })

    print("Test dataset:")
    print(test_df[["supplier", "spend", "po_number", "category_mapped"]].to_string(index=False))
    print()

    flagged_df, coverage = run_flag_engine(test_df)

    print("Flagged dataset:")
    print(flagged_df[[
        "supplier", "spend", "po_status", "contract_status",
        "maverick_flag", "shadow_it_flag", "freelancer_flag",
        "spend_pattern", "catalogue_flag"
    ]].to_string(index=False))
