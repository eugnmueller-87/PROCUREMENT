"""
AI-Powered Column Mapper
Uses Claude API to intelligently map messy column names to a standard schema.
Recognizes synonyms like Vendor/Supplier/Provider/Lieferant etc.
"""

import json
import os

# Standard schema that all uploads should map to
STANDARD_SCHEMA = {
    "category":       ["category", "spend_category", "procurement_category", "cost_center",
                       "warengruppe", "kategorie", "commodity", "group"],
    "supplier":       ["supplier", "vendor", "provider", "lieferant", "kreditor", "creditor",
                       "supplier_name", "vendor_name", "company", "partner"],
    "spend":          ["spend", "amount", "total", "value", "cost", "betrag", "invoice_total",
                       "invoice_amount", "rechnungsbetrag", "net_amount", "spend_eur",
                       "spend_amount", "total_spend"],
    "currency":       ["currency", "curr", "währung", "ccy"],
    "date":           ["date", "invoice_date", "datum", "period", "month", "year",
                       "posting_date", "buchungsdatum", "doc_date"],
    "contract_end":   ["contract_end", "contract_expiry", "expiry_date", "end_date",
                       "vertragslaufzeit", "renewal_date"],
    "risk":           ["risk", "risk_level", "risiko", "risk_rating"],
    "region":         ["region", "country", "location", "land", "geography", "geo"],
    "department":     ["department", "dept", "business_unit", "bu", "abteilung", "org_unit"],
    "po_number":      ["po_number", "purchase_order", "bestellnummer", "po", "order_number"],
    "concentration":  ["concentration", "supplier_share", "market_share"],
    "lead_time_days": ["lead_time", "lead_time_days", "delivery_time", "lieferzeit"],
    "single_source":  ["single_source", "sole_source", "single_supplier"],
}


def rule_based_mapping(columns: list[str]) -> dict:
    """
    Fast mapping using fuzzy string matching against known synonyms.
    Returns {original_col: standard_col} for confident matches, None for unknowns.
    """
    mapping = {}
    normalized = {col: col.strip().lower().replace(" ", "_").replace("-", "_") for col in columns}

    for orig_col, norm_col in normalized.items():
        matched = False
        for standard_name, synonyms in STANDARD_SCHEMA.items():
            if norm_col in synonyms or any(syn in norm_col for syn in synonyms):
                mapping[orig_col] = standard_name
                matched = True
                break
        if not matched:
            mapping[orig_col] = None  # unknown — needs AI

    return mapping


def ai_column_mapping(columns: list[str], sample_rows: list[dict], api_key: str = None) -> dict:
    """
    Use Claude to map columns that rule-based matching couldn't figure out.
    Falls back to rule-based only if no API key is available.
    """
    # First pass: rule-based
    mapping = rule_based_mapping(columns)
    unknowns = [col for col, val in mapping.items() if val is None]

    if not unknowns:
        return mapping  # everything matched

    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        print("⚠ No API key — using rule-based mapping only. Unknown columns skipped.")
        return {k: v for k, v in mapping.items() if v is not None}

    # Build prompt for Claude
    schema_desc = "\n".join([f"  - {k}: {', '.join(v[:5])}" for k, v in STANDARD_SCHEMA.items()])
    sample_str = json.dumps(sample_rows[:3], indent=2, default=str)

    prompt = f"""You are a procurement data expert. Map these unknown column names to the standard schema.

Standard schema fields:
{schema_desc}

Unknown columns to map: {unknowns}

Sample data rows:
{sample_str}

Return ONLY a JSON object mapping each unknown column to either a standard field name or "skip" if irrelevant.
Example: {{"Lieferant Name": "supplier", "Unnamed: 0": "skip"}}
JSON:"""

    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        result = json.loads(response.content[0].text.strip())

        for col, mapped in result.items():
            if mapped != "skip" and mapped in STANDARD_SCHEMA:
                mapping[col] = mapped

    except Exception as e:
        print(f"⚠ AI mapping failed: {e}. Using rule-based results only.")

    return {k: v for k, v in mapping.items() if v is not None}


def apply_mapping(df, mapping: dict):
    """Apply column mapping to a DataFrame and return cleaned version."""
    import pandas as pd
    rename_map = {orig: standard for orig, standard in mapping.items() if standard}
    df_clean = df.rename(columns=rename_map)

    # Keep only mapped columns
    valid_cols = [c for c in df_clean.columns if c in STANDARD_SCHEMA]
    return df_clean[valid_cols] if valid_cols else df_clean


if __name__ == "__main__":
    # Quick test
    test_cols = ["Vendor Name", "Total Amount EUR", "Warengruppe", "PO Number",
                 "Unknown_Col_123", "Buchungsdatum"]
    result = rule_based_mapping(test_cols)
    print("Mapping results:")
    for orig, mapped in result.items():
        status = f"→ {mapped}" if mapped else "→ ❓ unknown"
        print(f"  {orig} {status}")
