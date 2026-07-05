"""
seed_dummy.py — Load dummy spend data into SpendLens for testing.

Runs the full pipeline (column mapping → cleanup → categorisation → flags → DB insert)
exactly as a real upload would. Data is tagged with upload source "dummy_seed" so it
can be identified and removed before going to production.

Usage:
    .venv/Scripts/python.exe seed_data/seed_dummy.py          # loads into clients/default
    .venv/Scripts/python.exe seed_data/seed_dummy.py --reset  # wipe DB first, then load
"""

import sys
import os
import argparse
from pathlib import Path

# Force UTF-8 output so emoji in module print statements don't crash on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)
    sys.stderr = open(sys.stderr.fileno(), mode="w", encoding="utf-8", buffering=1)

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import pandas as pd
from modules.column_mapper   import rule_based_mapping, apply_mapping
from modules.data_cleanup    import full_cleanup
from modules.category_mapper import run_category_mapping
from modules.flag_engine     import run_flag_engine
from modules.database        import (
    init_database, get_connection, log_upload,
    insert_raw_transactions, insert_enriched_transactions,
    upsert_vendor,
)
from modules.supplier_profiler import compute_and_save_profiles

CSV_PATH = Path(__file__).parent / "dummy_spend.csv"
CLIENT   = "default"


def log(msg):
    print(f"  {msg}")


def reset_db():
    db_path = ROOT / "clients" / CLIENT / "spendlens.db"
    if db_path.exists():
        db_path.unlink()
        print(f"Wiped {db_path}")


def run(reset: bool = False):
    if reset:
        reset_db()

    print(f"\nSeeding SpendLens with dummy data from {CSV_PATH.name}")
    print("=" * 55)

    # Step 1 — Read CSV
    log("Reading CSV...")
    df_raw = pd.read_csv(CSV_PATH)
    log(f"{len(df_raw)} rows, columns: {list(df_raw.columns)}")

    # Step 2 — Column mapping (rule-based only — CSV uses standard names)
    log("Mapping columns to standard schema...")
    mapping = rule_based_mapping(df_raw.columns.tolist())
    log(f"Mapping: {mapping}")
    df = apply_mapping(df_raw, mapping)
    # Preserve description column even if not in standard schema — needed for dedup hash
    if "description" in df_raw.columns and "description" not in df.columns:
        df["description"] = df_raw["description"].values

    # Step 3 — Clean data
    log("Cleaning data...")
    df, _cleanup_report = full_cleanup(df)
    log(f"{len(df)} rows after cleanup")

    # Step 4 — Category mapping (uses vendor_cache.json to avoid redundant API calls)
    log("Classifying vendors into categories...")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    df, _re_summary = run_category_mapping(df, api_key=api_key)
    log(f"Categories assigned: {df['category_mapped'].value_counts().to_dict()}")

    # Step 5 — Flag engine
    log("Running compliance & risk flags...")
    flagged_df, _report = run_flag_engine(df)
    maverick = int(flagged_df["maverick_flag"].sum()) if "maverick_flag" in flagged_df.columns else 0
    log(f"Maverick transactions: {maverick}")

    # Ensure all date-like columns are strings, not Timestamps
    for col in ["date", "contract_end"]:
        if col in df.columns:
            df[col] = df[col].astype(str).replace("NaT", "")

    # Step 6 — Database insert
    log("Initialising database...")
    init_database(CLIENT)
    conn = get_connection(CLIENT)

    upload_id = log_upload(
        conn,
        filename="dummy_spend.csv",
        source_type="dummy_seed",
        row_count=len(df),
        mapped_columns={k: v for k, v in mapping.items() if v},
    )
    insert_raw_transactions(conn, df, upload_id)
    insert_enriched_transactions(conn, df, flagged_df)
    conn.close()
    log("Saved to knowledge base")

    # Step 7 — Vendor knowledge base + supplier profiles
    log("Building vendor knowledge base...")
    conn = get_connection(CLIENT)
    spend_col = "spend_eur" if "spend_eur" in df.columns else "spend"
    df[spend_col] = pd.to_numeric(df[spend_col], errors="coerce").fillna(0)
    vendor_agg = (
        df.groupby("supplier")
        .agg(total_spend=(spend_col, "sum"), transaction_count=(spend_col, "count"))
        .reset_index()
    )
    inserted_vendors = 0
    for _, row in vendor_agg.iterrows():
        cat = df.loc[df["supplier"] == row["supplier"], "category_mapped"].iloc[0] \
              if "category_mapped" in df.columns else ""
        upsert_vendor(
            conn=conn,
            vendor_name=row["supplier"],
            category=cat,
            classification_source="dummy_seed",
        )
        inserted_vendors += 1
    conn.commit()
    conn.close()
    log(f"Vendor knowledge base: {inserted_vendors} vendors")

    log("Computing supplier ABC tiers...")
    conn = get_connection(CLIENT)
    compute_and_save_profiles(conn, CLIENT)
    conn.close()
    log("Supplier profiles done")

    # Step 8 — Push to Hermes watchlist
    log("Pushing vendors to Hermes watchlist...")
    try:
        from modules.hermes_client import HermesClient
        conn = get_connection(CLIENT)
        rows = conn.execute(
            "SELECT vendor_name, category, total_spend, oc_country FROM vendors ORDER BY total_spend DESC"
        ).fetchall()
        conn.close()
        vendor_list = [
            {"vendor_name": r["vendor_name"], "category": r["category"] or "",
             "spend_eur": float(r["total_spend"] or 0), "country": r["oc_country"] or ""}
            for r in rows
        ]
        result = HermesClient().push_vendor_list(vendor_list)
        log(f"Hermes: {result['registered']} new, {result['already_tracked']} already tracked")
    except Exception as e:
        log(f"Hermes sync skipped (not required for local test): {e}")

    # Summary
    conn = get_connection(CLIENT)
    tx_count   = conn.execute("SELECT COUNT(*) FROM transactions_raw").fetchone()[0]
    vend_count = conn.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]
    conn.close()

    print("\n" + "=" * 55)
    print(f"Done — {tx_count} transactions, {vend_count} vendors in DB")
    print(f"DB: {ROOT / 'clients' / CLIENT / 'spendlens.db'}")
    print("\nNOTE: This is dummy data. Tag: source_type='dummy_seed'")
    print("Run with --reset to wipe and reload cleanly.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Wipe the DB before seeding")
    args = parser.parse_args()
    run(reset=args.reset)
