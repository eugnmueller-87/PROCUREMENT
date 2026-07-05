"""
Regression guard for Phase 2A: real-path dashboard spend units.
Asserts that totalSpend is emitted in millions (not thousands).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("PYTHONUTF8", "1")

import pandas as pd
import sqlite3
import tempfile
from pathlib import Path


def _build_test_db(tmp_path: str) -> sqlite3.Connection:
    """Seed a minimal in-memory-style DB with dummy_spend.csv data."""
    from modules.database import init_database, get_connection

    # Point CLIENT at a temp dir to avoid touching real data
    client = "test_units"
    db_dir = Path(tmp_path) / "clients" / client
    db_dir.mkdir(parents=True, exist_ok=True)

    # Patch the DB path
    import modules.database as db_mod
    orig_base = db_mod.BASE_DIR if hasattr(db_mod, "BASE_DIR") else None
    db_path = db_dir / "spendlens.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Init schema
    init_database(client)
    conn.close()
    conn = get_connection(client)

    # Insert a handful of rows totalling a known amount in EUR
    # 10 rows × 100_000 EUR = 1_000_000 EUR = 1.0 M
    from modules.database import log_upload
    upload_id = log_upload(conn, "test.csv", "accounting", 10, {})

    rows = [
        {
            "upload_id": upload_id, "supplier": f"Vendor{i}", "spend": 100_000.0,
            "currency": "EUR", "date": "2025-01-01", "po_number": f"PO-{i}",
            "description": "test", "region": "DE", "department": "IT",
            "contract_end": None, "single_source": 0, "row_hash": f"hash{i}",
            "spend_eur": 100_000.0, "fx_rate": 1.0,
        }
        for i in range(10)
    ]
    for r in rows:
        conn.execute("""
            INSERT OR IGNORE INTO transactions_raw
            (upload_id, supplier, spend, currency, date, po_number, description,
             region, department, contract_end, single_source, row_hash, spend_eur, fx_rate)
            VALUES (:upload_id,:supplier,:spend,:currency,:date,:po_number,:description,
                    :region,:department,:contract_end,:single_source,:row_hash,:spend_eur,:fx_rate)
        """, r)
    conn.commit()

    # Insert matching enriched rows
    raw_ids = [r[0] for r in conn.execute("SELECT id FROM transactions_raw WHERE upload_id=?", (upload_id,)).fetchall()]
    for raw_id in raw_ids:
        conn.execute("""
            INSERT OR IGNORE INTO transactions_enriched
            (raw_id, category_mapped, po_status, contract_status, maverick_flag,
             shadow_it_flag, freelancer_flag, spend_pattern, catalogue_flag)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (raw_id, "Cloud & Compute", "With PO", "Unknown", 0, 0, 0, "Recurring", "Unknown"))
    conn.commit()

    return conn, client


def test_total_spend_in_millions():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        # Temporarily override the client DB location
        import api as api_mod
        orig_client = api_mod.CLIENT

        # Build a seeded DB
        conn, client = _build_test_db(tmp)
        conn.close()

        # Monkey-patch _conn to return our test DB
        from modules.database import get_connection
        api_mod.CLIENT = client

        # Override get_connection to look in our tmp path
        import modules.database as db_mod
        orig_clients_dir = db_mod.CLIENTS_DIR if hasattr(db_mod, "CLIENTS_DIR") else None

        response = api_mod.dashboard()
        total_spend = response["kpis"]["totalSpend"]

        # 10 rows × 100_000 EUR = 1_000_000 EUR = 1.0 M
        # Allow ±0.05 for rounding
        assert 0.9 < total_spend < 1.1, (
            f"totalSpend={total_spend} — expected ~1.0 (millions). "
            "If this is ~1000, the /1e6 fix was reverted to /1000."
        )
        assert total_spend < 1000, (
            f"totalSpend={total_spend} looks like thousands, not millions."
        )

        api_mod.CLIENT = orig_client


if __name__ == "__main__":
    test_total_spend_in_millions()
    print("PASS: totalSpend is in millions range")
