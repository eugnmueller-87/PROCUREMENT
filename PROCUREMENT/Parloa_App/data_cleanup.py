"""
Data Cleanup Engine
Handles the 80% of real-world data work: deduplication, normalization,
type fixing, vendor name standardization, currency conversion, etc.
"""

import pandas as pd
import re
from datetime import datetime


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names: lowercase, underscores, no special chars."""
    df = df.copy()
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"[^\w\s]", "", regex=True)
        .str.replace(r"\s+", "_", regex=True)
    )
    return df


def remove_junk_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Remove empty rows, subtotal rows, header duplicates."""
    initial = len(df)
    stats = {}

    # Drop fully empty rows
    df = df.dropna(how="all")
    stats["empty_rows_removed"] = initial - len(df)

    # Drop rows where all numeric cols are 0
    numeric_cols = df.select_dtypes(include="number").columns
    if len(numeric_cols) > 0:
        zero_mask = (df[numeric_cols] == 0).all(axis=1)
        df = df[~zero_mask]

    # Drop rows that look like subtotals
    if "category" in df.columns or "supplier" in df.columns:
        text_col = "category" if "category" in df.columns else "supplier"
        total_pattern = r"(?i)^(total|summe|subtotal|grand total|gesamt|sum)"
        total_mask = df[text_col].astype(str).str.match(total_pattern, na=False)
        stats["total_rows_removed"] = int(total_mask.sum())
        df = df[~total_mask]

    # Drop duplicates
    before_dedup = len(df)
    df = df.drop_duplicates()
    stats["duplicates_removed"] = before_dedup - len(df)

    stats["rows_remaining"] = len(df)
    return df, stats


def fix_spend_column(series: pd.Series) -> pd.Series:
    """Convert messy spend values to clean floats.
    Handles: €1,234.56 | 1.234,56 | $1234 | '1234' | (1234) for negatives
    """
    def clean_value(val):
        if pd.isna(val):
            return None
        s = str(val).strip()

        # Handle accounting negatives: (1234) → -1234
        negative = False
        if s.startswith("(") and s.endswith(")"):
            negative = True
            s = s[1:-1]

        # Remove currency symbols and whitespace
        s = re.sub(r"[€$£¥\s]", "", s)

        # Detect German number format: 1.234,56 vs English 1,234.56
        if re.search(r"\d\.\d{3},\d", s):  # German format
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")

        try:
            result = float(s)
            return -result if negative else result
        except ValueError:
            return None

    return series.apply(clean_value)


def fix_date_column(series: pd.Series) -> pd.Series:
    """Parse dates in various formats including German (dd.mm.yyyy)."""
    formats_to_try = [
        "%d.%m.%Y",     # German: 22.04.2026
        "%d.%m.%y",     # German short: 22.04.26
        "%Y-%m-%d",     # ISO: 2026-04-22
        "%d/%m/%Y",     # EU: 22/04/2026
        "%m/%d/%Y",     # US: 04/22/2026
        "%d-%m-%Y",     # 22-04-2026
        "%Y/%m/%d",     # 2026/04/22
        "%b %d, %Y",   # Apr 22, 2026
        "%d %b %Y",    # 22 Apr 2026
    ]

    def try_parse(val):
        if pd.isna(val):
            return pd.NaT
        s = str(val).strip()
        for fmt in formats_to_try:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return pd.NaT

    return pd.to_datetime(series.apply(try_parse))


# --- Vendor Name Standardization ---

# Common suffixes to strip for matching
COMPANY_SUFFIXES = [
    r"\bGmbH\b", r"\bAG\b", r"\bSE\b", r"\bInc\.?\b", r"\bLtd\.?\b",
    r"\bLLC\b", r"\bCorp\.?\b", r"\bCo\.?\b", r"\bKG\b", r"\b& Co\b",
    r"\bDeutschland\b", r"\bGermany\b", r"\bEurope\b", r"\bGroup\b",
    r"\bHolding\b", r"\bInternational\b", r"\bServices\b",
]

# Known vendor aliases → canonical name
VENDOR_ALIASES = {
    "aws": "Amazon Web Services",
    "amazon web services": "Amazon Web Services",
    "amazon": "Amazon Web Services",
    "gcp": "Google Cloud Platform",
    "google cloud": "Google Cloud Platform",
    "google": "Google Cloud Platform",
    "msft": "Microsoft",
    "microsoft azure": "Microsoft",
    "microsoft deutschland": "Microsoft",
    "ms": "Microsoft",
    "ibm deutschland": "IBM",
    "dt": "Deutsche Telekom",
    "deutsche telekom": "Deutsche Telekom",
    "telekom": "Deutsche Telekom",
    "t-systems": "Deutsche Telekom",
    "sap se": "SAP",
    "sap deutschland": "SAP",
    "dhl supply chain": "DHL",
    "dhl express": "DHL",
    "dhl": "DHL",
}


def standardize_vendor_name(name: str) -> str:
    """Normalize a single vendor name."""
    if pd.isna(name):
        return "Unknown"

    cleaned = str(name).strip()

    # Strip suffixes for matching
    match_key = cleaned
    for suffix in COMPANY_SUFFIXES:
        match_key = re.sub(suffix, "", match_key, flags=re.IGNORECASE).strip()

    # Check aliases
    lookup = match_key.lower().strip(" .,")
    if lookup in VENDOR_ALIASES:
        return VENDOR_ALIASES[lookup]

    return cleaned  # return original if no alias found


def standardize_vendors(df: pd.DataFrame, col: str = "supplier") -> pd.DataFrame:
    """Apply vendor standardization to a DataFrame column."""
    if col not in df.columns:
        return df
    df = df.copy()
    df[f"{col}_original"] = df[col]
    df[col] = df[col].apply(standardize_vendor_name)
    changed = (df[col] != df[f"{col}_original"]).sum()
    print(f"  ✅ Standardized {changed} vendor names")
    return df


def full_cleanup(df: pd.DataFrame, spend_col: str = None, date_col: str = None,
                 vendor_col: str = None) -> tuple[pd.DataFrame, dict]:
    """Run the full cleanup pipeline."""
    report = {"original_shape": df.shape}

    # 1. Clean column names
    df = clean_column_names(df)
    report["columns_cleaned"] = True

    # 2. Remove junk
    df, junk_stats = remove_junk_rows(df)
    report.update(junk_stats)

    # 3. Fix spend
    spend_candidates = [spend_col] if spend_col else [
        c for c in df.columns if any(k in c for k in ["spend", "amount", "total", "cost", "betrag"])
    ]
    for col in spend_candidates:
        if col in df.columns:
            df[col] = fix_spend_column(df[col])
            report[f"{col}_fixed"] = True

    # 4. Fix dates
    date_candidates = [date_col] if date_col else [
        c for c in df.columns if any(k in c for k in ["date", "datum", "end", "expiry"])
    ]
    for col in date_candidates:
        if col in df.columns:
            df[col] = fix_date_column(df[col])
            report[f"{col}_parsed"] = True

    # 5. Standardize vendors
    vendor_col = vendor_col or next(
        (c for c in df.columns if any(k in c for k in ["supplier", "vendor", "lieferant"])), None
    )
    if vendor_col:
        df = standardize_vendors(df, vendor_col)

    # 6. Fill missing categorical values
    for col in df.select_dtypes(include="object").columns:
        na_count = df[col].isna().sum()
        if na_count > 0:
            df[col] = df[col].fillna("Unknown")
            report[f"{col}_filled"] = na_count

    report["final_shape"] = df.shape
    return df, report


if __name__ == "__main__":
    # Quick test with messy data
    test_data = pd.DataFrame({
        "Vendor Name": ["SAP SE", "SAP Deutschland GmbH", "aws", "Microsoft Azure", None],
        " Total Amount ": ["€1.234,56", "1234.56", "$5,678.90", "(1000)", ""],
        "Date ": ["22.04.2026", "2026-04-22", "04/22/2026", "22 Apr 2026", None],
    })
    print("Before cleanup:")
    print(test_data)
    print()

    cleaned, report = full_cleanup(test_data)
    print("\nAfter cleanup:")
    print(cleaned)
    print("\nReport:", report)
