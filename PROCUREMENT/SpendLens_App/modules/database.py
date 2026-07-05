"""
database.py — SpendLens Persistent Knowledge Base
===================================================
SQLite database layer for SpendLens. Stores all transaction history,
vendor knowledge, upload logs and source matches across sessions.

WHY SQLITE:
- File-based — no server needed, lives next to the app
- Readable in VS Code with SQLite Viewer extension
- Fast enough for 100K+ transactions
- Single file per client → easy backup, easy multi-client isolation

DATABASE STRUCTURE:
───────────────────
transactions_raw        Raw data exactly as uploaded — never modified
transactions_enriched   Derived flags and classifications — recomputable
vendors                 Persistent vendor knowledge base — grows over time
uploads                 Log of every file processed
matches                 Accounting ↔ Procurement linked transactions

PHILOSOPHY:
───────────
- Raw data is immutable. Once inserted, never updated.
- Enriched data is recomputable. Can be wiped and rebuilt anytime.
- Vendor knowledge accumulates. Never deleted, only enriched.
- Every upload is logged. Full audit trail of what came in and when.
- Duplicates are detected via hash — same transaction never inserted twice.
"""

import sqlite3
import hashlib
import json
import pandas as pd
from datetime import datetime
from pathlib import Path


# ── DATABASE LOCATION ──────────────────────────────────────────────────────────
# Default: clients/default/spendlens.db
# Multi-client: clients/{client_name}/spendlens.db
# Each client is fully isolated — their own DB, config, and vendor cache.

def get_db_path(client_name: str = "default") -> str:
    """
    Returns the database path for a given client.
    Creates the client folder if it doesn't exist.

    Structure:
        SpendLens_App/
        └── clients/
            ├── default/          ← single client / dev mode
            │   ├── spendlens.db
            │   ├── config.json
            │   └── vendor_cache.json
            └── parloa/           ← future: named client
                ├── spendlens.db
                └── config.json
    """
    base = Path(__file__).parent / "clients" / client_name
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "spendlens.db")


# ── CONNECTION ─────────────────────────────────────────────────────────────────

def get_connection(client_name: str = "default") -> sqlite3.Connection:
    """
    Open a connection to the client's database.
    Enables WAL mode for better concurrent read performance.
    Row factory set so results come back as dicts, not tuples.
    """
    db_path = get_db_path(client_name)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row          # results as dict-like objects
    conn.execute("PRAGMA journal_mode=WAL") # better read performance
    conn.execute("PRAGMA foreign_keys=ON")  # enforce relationships
    return conn


# ── SCHEMA CREATION ────────────────────────────────────────────────────────────

def init_database(client_name: str = "default") -> None:
    """
    Create all tables if they don't exist yet.
    Safe to run on every startup — uses CREATE TABLE IF NOT EXISTS.
    Never drops or modifies existing tables.
    """
    conn = get_connection(client_name)

    print("\n── Initializing Database ───────────────────────────────")
    print(f"  📁 Path: {get_db_path(client_name)}")

    conn.executescript("""

    -- ── TABLE 1: UPLOADS ──────────────────────────────────────────────────────
    -- Log of every file ever processed by SpendLens.
    -- Provides full audit trail: who uploaded what, when, how many rows.
    -- Source type tells us what kind of data this file contained.

    CREATE TABLE IF NOT EXISTS uploads (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        uploaded_at     TEXT NOT NULL,              -- ISO timestamp of upload
        filename        TEXT NOT NULL,              -- original filename
        source_type     TEXT NOT NULL,              -- accounting / procurement / contract / hr / unknown
        row_count       INTEGER,                    -- rows in the file
        mapped_columns  TEXT,                       -- JSON: which columns were found
        notes           TEXT                        -- free text, e.g. "Q1 2026 SAP export"
    );


    -- ── TABLE 2: TRANSACTIONS RAW ─────────────────────────────────────────────
    -- Every transaction row ever uploaded, exactly as it came in.
    -- NEVER modified after insert. This is the source of truth.
    -- Duplicate detection via row_hash — same data never inserted twice.

    CREATE TABLE IF NOT EXISTS transactions_raw (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        upload_id       INTEGER NOT NULL REFERENCES uploads(id),
        row_hash        TEXT NOT NULL UNIQUE,       -- MD5 of key fields, prevents duplicates
        inserted_at     TEXT NOT NULL,              -- when this row was inserted

        -- Core fields (mapped from source columns)
        supplier        TEXT,
        spend           REAL,
        currency        TEXT DEFAULT 'EUR',
        date            TEXT,                       -- ISO date string
        description     TEXT,
        cost_center     TEXT,
        po_number       TEXT,
        contract_id     TEXT,
        contract_end    TEXT,
        gl_account      TEXT,
        catalogue_id    TEXT,
        region          TEXT,
        category_source TEXT,                       -- category as it came in the source file

        -- Source metadata
        source_type     TEXT,                       -- inherited from upload
        raw_json        TEXT                        -- full original row as JSON (safety net)
    );

    CREATE INDEX IF NOT EXISTS idx_raw_supplier ON transactions_raw(supplier);
    CREATE INDEX IF NOT EXISTS idx_raw_date ON transactions_raw(date);
    CREATE INDEX IF NOT EXISTS idx_raw_upload ON transactions_raw(upload_id);


    -- ── TABLE 3: TRANSACTIONS ENRICHED ───────────────────────────────────────
    -- Derived intelligence for every raw transaction.
    -- Can be wiped and recomputed anytime as the pipeline improves.
    -- Links back to transactions_raw via raw_id.

    CREATE TABLE IF NOT EXISTS transactions_enriched (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_id              INTEGER NOT NULL UNIQUE REFERENCES transactions_raw(id),
        enriched_at         TEXT NOT NULL,          -- when enrichment was last run

        -- Category mapping (from category_mapper.py)
        category_mapped     TEXT,                   -- one of 11 taxonomy categories
        sub_commodity       TEXT,                   -- e.g. Freelancer under Recruitment & HR
        office_location     TEXT,                   -- city/country for Real Estate

        -- Compliance & risk flags (from flag_engine.py)
        po_status           TEXT,                   -- With PO / Blanket PO / No PO / Unknown
        contract_status     TEXT,                   -- Under Contract / Expired / No Contract / Unknown
        maverick_flag       INTEGER,                -- 0/1/NULL (NULL = unknown, honest data gap)
        shadow_it_flag      INTEGER,                -- 0/1
        freelancer_flag     INTEGER,                -- 0/1
        catalogue_flag      TEXT,                   -- Catalogue / Off-catalogue / Unknown
        spend_pattern       TEXT,                   -- Recurring / Blanket PO / One-off / Irregular

        -- Pipeline metadata
        pipeline_version    TEXT                    -- version tag so we know which engine produced this
    );

    CREATE INDEX IF NOT EXISTS idx_enriched_raw ON transactions_enriched(raw_id);
    CREATE INDEX IF NOT EXISTS idx_enriched_category ON transactions_enriched(category_mapped);
    CREATE INDEX IF NOT EXISTS idx_enriched_maverick ON transactions_enriched(maverick_flag);
    CREATE INDEX IF NOT EXISTS idx_enriched_shadow ON transactions_enriched(shadow_it_flag);


    -- ── TABLE 4: VENDORS ──────────────────────────────────────────────────────
    -- Persistent vendor knowledge base. Grows with every upload.
    -- This is the memory layer — SpendLens never forgets a vendor it has seen.
    -- Shared across all uploads for this client.

    CREATE TABLE IF NOT EXISTS vendors (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_name         TEXT NOT NULL UNIQUE,   -- canonical name after standardization
        first_seen          TEXT NOT NULL,          -- date first encountered
        last_seen           TEXT NOT NULL,          -- date last seen in an upload
        transaction_count   INTEGER DEFAULT 0,      -- total transactions ever seen
        total_spend         REAL DEFAULT 0,         -- cumulative spend across all uploads

        -- Classification (from category_mapper.py + Claude)
        category            TEXT,                   -- taxonomy category
        sub_commodity       TEXT,                   -- sub-category if applicable
        is_freelancer       INTEGER DEFAULT 0,      -- 0/1
        is_company          INTEGER DEFAULT 1,      -- 0/1 — result of whitelist/Claude check
        classification_source TEXT,                 -- rule / claude / manual_override
        classification_confidence TEXT,             -- high / medium / low

        -- Location (for Real Estate vendors)
        office_location     TEXT,                   -- city/country extracted from descriptions

        -- Risk profile
        risk_level          TEXT,                   -- Critical / High / Medium / Low
        single_source       INTEGER DEFAULT 0,      -- 0/1 — only supplier in their category
        vat_id              TEXT,                   -- VAT number if available (proof of company)

        -- Override (from config.json vendor_overrides)
        manual_override     INTEGER DEFAULT 0,      -- 0/1 — manually set, never auto-updated
        override_notes      TEXT,                   -- why this was overridden

        -- Raw Claude response for audit
        claude_response     TEXT                    -- full JSON response from last classification
    );

    CREATE INDEX IF NOT EXISTS idx_vendors_name ON vendors(vendor_name);
    CREATE INDEX IF NOT EXISTS idx_vendors_category ON vendors(category);
    CREATE INDEX IF NOT EXISTS idx_vendors_freelancer ON vendors(is_freelancer);


    -- ── TABLE 5: MATCHES ──────────────────────────────────────────────────────
    -- Links accounting transactions to procurement POs/contracts.
    -- Built by the multi-source merger when both sources are uploaded.
    -- Confidence score reflects how strong the match is.

    CREATE TABLE IF NOT EXISTS matches (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        matched_at          TEXT NOT NULL,

        -- The two sides of the match
        accounting_raw_id   INTEGER REFERENCES transactions_raw(id),
        procurement_raw_id  INTEGER REFERENCES transactions_raw(id),

        -- Match quality
        match_type          TEXT NOT NULL,          -- exact / fuzzy_amount / fuzzy_vendor / manual
        confidence          REAL,                   -- 0.0 to 1.0
        match_notes         TEXT,                   -- e.g. "amount matched within 2%, vendor standardized"

        -- Variance analysis
        po_amount           REAL,                   -- amount on the PO
        invoice_amount      REAL,                   -- amount on the invoice
        variance_amount     REAL,                   -- invoice - PO
        variance_pct        REAL                    -- variance as % of PO amount
    );

    CREATE INDEX IF NOT EXISTS idx_matches_accounting ON matches(accounting_raw_id);
    CREATE INDEX IF NOT EXISTS idx_matches_procurement ON matches(procurement_raw_id);


    -- ── TABLE 6: SUPPLIER PROFILES ───────────────────────────────────────────
    -- Persistent supplier intelligence: ABC tier, compliance score, relationship
    -- status. Grows with every upload. The SRM record for each vendor.
    -- tier_override survives every recomputation — user's manual tier wins.

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
    );

    CREATE INDEX IF NOT EXISTS idx_sp_client ON supplier_profiles(client_name);


    -- ── TABLE 7: CONTRACTS (Lex CLM) ─────────────────────────────────────────
    -- One row per scanned contract document.
    -- Stores extracted clauses, risk assessment, and raw Claude JSON.
    -- Links to vendors table via vendor_name for cross-module queries.

    CREATE TABLE IF NOT EXISTS contracts (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        scanned_at              TEXT NOT NULL,          -- ISO timestamp of scan
        filename                TEXT NOT NULL,          -- original filename
        vendor_name             TEXT,                   -- linked vendor (may be NULL if unknown)
        contract_type           TEXT,                   -- MSA / SaaS / Freelancer / NDA / Other

        -- Extracted clauses
        start_date              TEXT,                   -- contract start date
        end_date                TEXT,                   -- contract end date / expiry
        notice_period_days      INTEGER,                -- days notice required to terminate
        auto_renewal            INTEGER,                -- 0/1 — does it auto-renew?
        auto_renewal_period     TEXT,                   -- e.g. "12 months", "1 year"
        penalty_cap_pct         REAL,                   -- penalty/Pönale cap as % of contract value
        liability_cap           TEXT,                   -- liability limitation clause text
        price_adjustment        TEXT,                   -- price escalation / CPI clause text
        jurisdiction            TEXT,                   -- governing law / court jurisdiction
        sla_terms               TEXT,                   -- SLA obligations summary
        payment_terms           TEXT,                   -- payment terms (e.g. Net 30)
        termination_rights      TEXT,                   -- termination for convenience clause

        -- Missing clauses (comma-separated list)
        missing_clauses         TEXT,

        -- Risk assessment
        risk_score              REAL,                   -- 1-10 overall contract risk
        risk_level              TEXT,                   -- Low / Medium / High / Critical
        risk_summary            TEXT,                   -- one-paragraph risk narrative
        required_actions        TEXT,                   -- JSON list of required actions
        clause_flags            TEXT,                   -- JSON dict: clause -> flag color

        -- Raw Claude output (for audit/replay)
        claude_raw              TEXT                    -- full JSON from Claude extraction
    );

    CREATE INDEX IF NOT EXISTS idx_contracts_vendor ON contracts(vendor_name);
    CREATE INDEX IF NOT EXISTS idx_contracts_end ON contracts(end_date);

    """)

    conn.commit()

    # Add columns introduced in later versions — safe to run on existing databases
    migrations = [
        "ALTER TABLE transactions_raw ADD COLUMN spend_eur REAL",
        "ALTER TABLE transactions_raw ADD COLUMN fx_rate REAL",
        "ALTER TABLE vendors ADD COLUMN oc_country TEXT",
        "ALTER TABLE vendors ADD COLUMN oc_registration_number TEXT",
        "ALTER TABLE vendors ADD COLUMN oc_entity_type TEXT",
        "ALTER TABLE vendors ADD COLUMN oc_jurisdiction TEXT",
        # Hades due diligence fields
        "ALTER TABLE vendors ADD COLUMN hades_risk_score REAL",
        "ALTER TABLE vendors ADD COLUMN hades_risk_level TEXT",
        "ALTER TABLE vendors ADD COLUMN hades_recommendation TEXT",
        "ALTER TABLE vendors ADD COLUMN hades_sanctions_clear INTEGER",
        "ALTER TABLE vendors ADD COLUMN hades_lksg_signal TEXT",
        "ALTER TABLE vendors ADD COLUMN hades_next_steps TEXT",
        "ALTER TABLE vendors ADD COLUMN hades_report_date TEXT",
        # Lex CLM fields on vendors table
        "ALTER TABLE vendors ADD COLUMN lex_contract_id INTEGER",
        "ALTER TABLE vendors ADD COLUMN lex_contract_risk_score REAL",
        "ALTER TABLE vendors ADD COLUMN lex_contract_risk_level TEXT",
        "ALTER TABLE vendors ADD COLUMN lex_contract_end TEXT",
        "ALTER TABLE vendors ADD COLUMN lex_notice_period_days INTEGER",
        "ALTER TABLE vendors ADD COLUMN lex_auto_renewal INTEGER",
        "ALTER TABLE vendors ADD COLUMN lex_scan_date TEXT",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    conn.close()

    print("  ✅ Tables created: uploads, transactions_raw, transactions_enriched, vendors, matches, supplier_profiles, contracts")
    print("── Database ready ✅ ────────────────────────────────────\n")


# ── ROW HASHING ────────────────────────────────────────────────────────────────

def compute_row_hash(row: dict) -> str:
    """
    Generate a unique hash for a transaction row.
    Used to detect and prevent duplicate inserts across uploads.

    Hashes: supplier + spend + currency + date + description + po_number
    If these 6 fields match an existing row → it's a duplicate, skip it.
    """
    key_fields = [
        str(row.get("supplier", "") or ""),
        str(row.get("spend", "") or ""),
        str(row.get("currency", "") or ""),
        str(row.get("date", "") or ""),
        str(row.get("description", "") or ""),
        str(row.get("po_number", "") or ""),
    ]
    hash_string = "|".join(key_fields).lower().strip()
    return hashlib.md5(hash_string.encode()).hexdigest()


# ── INSERT UPLOAD LOG ──────────────────────────────────────────────────────────

def log_upload(conn: sqlite3.Connection, filename: str, source_type: str,
               row_count: int, mapped_columns: dict, notes: str = "") -> int:
    """
    Record a new upload in the uploads table.
    Returns the upload_id for use when inserting raw transactions.
    """
    cursor = conn.execute("""
        INSERT INTO uploads (uploaded_at, filename, source_type, row_count, mapped_columns, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        filename,
        source_type,
        row_count,
        json.dumps(mapped_columns),
        notes
    ))
    conn.commit()
    upload_id = cursor.lastrowid
    print(f"  📥 Upload logged: {filename} ({row_count} rows) → upload_id={upload_id}")
    return upload_id


# ── INSERT RAW TRANSACTIONS ────────────────────────────────────────────────────

def insert_raw_transactions(conn: sqlite3.Connection, df: pd.DataFrame,
                             upload_id: int, source_type: str = "accounting") -> dict:
    """
    Insert raw transaction rows into transactions_raw.
    Skips duplicates silently using row_hash deduplication.

    Returns stats: how many inserted vs skipped.
    """
    inserted = 0
    skipped = 0
    now = datetime.now().isoformat()

    for _, row in df.iterrows():
        row_dict = row.where(pd.notna(row), None).to_dict()
        row_hash = compute_row_hash(row_dict)

        try:
            conn.execute("""
                INSERT INTO transactions_raw (
                    upload_id, row_hash, inserted_at,
                    supplier, spend, currency, date, description,
                    cost_center, po_number, contract_id, contract_end,
                    gl_account, catalogue_id, region, category_source,
                    source_type, raw_json, spend_eur, fx_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                upload_id, row_hash, now,
                row_dict.get("supplier"), row_dict.get("spend"),
                row_dict.get("currency", "EUR"), str(row_dict.get("date", "") or ""),
                row_dict.get("description"), row_dict.get("cost_center"),
                row_dict.get("po_number"), row_dict.get("contract_id"),
                row_dict.get("contract_end"), row_dict.get("gl_account"),
                row_dict.get("catalogue_id"), row_dict.get("region"),
                row_dict.get("category") or row_dict.get("category_mapped"),
                source_type, json.dumps(row_dict, default=str),
                row_dict.get("spend_eur"), row_dict.get("fx_rate")
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            # row_hash already exists → duplicate, skip silently
            skipped += 1

    conn.commit()
    print(f"  ✅ Raw transactions: {inserted} inserted | {skipped} duplicates skipped")
    return {"inserted": inserted, "skipped": skipped}


# ── INSERT ENRICHED DATA ───────────────────────────────────────────────────────

def insert_enriched_transactions(conn: sqlite3.Connection,
                                  df_raw: pd.DataFrame,
                                  df_enriched: pd.DataFrame,
                                  pipeline_version: str = "1.0") -> int:
    """
    Insert or update enriched flag data for transactions.
    Uses INSERT OR REPLACE so re-running the pipeline updates existing records.

    df_raw      — the raw DataFrame (has row_hash)
    df_enriched — the enriched DataFrame (has flag columns)
    Both must have the same index alignment.
    """
    updated = 0
    now = datetime.now().isoformat()

    for idx in df_raw.index:
        row_hash = compute_row_hash(df_raw.loc[idx].where(
            pd.notna(df_raw.loc[idx]), None).to_dict())

        # Find the raw_id for this hash
        result = conn.execute(
            "SELECT id FROM transactions_raw WHERE row_hash = ?", (row_hash,)
        ).fetchone()

        if not result:
            continue  # raw row not found, skip

        raw_id = result["id"]
        e = df_enriched.loc[idx] if idx in df_enriched.index else None
        if e is None:
            continue

        conn.execute("""
            INSERT OR REPLACE INTO transactions_enriched (
                raw_id, enriched_at,
                category_mapped, sub_commodity, office_location,
                po_status, contract_status, maverick_flag,
                shadow_it_flag, freelancer_flag, catalogue_flag,
                spend_pattern, pipeline_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            raw_id, now,
            str(e.get("category_mapped") or ""),
            str(e.get("sub_commodity") or ""),
            str(e.get("office_location") or ""),
            str(e.get("po_status") or "Unknown"),
            str(e.get("contract_status") or "Unknown"),
            int(e.get("maverick_flag") or 0) if e.get("maverick_flag") is not None else None,
            int(bool(e.get("shadow_it_flag") or False)),
            int(bool(e.get("freelancer_flag") or False)),
            str(e.get("catalogue_flag") or "Unknown"),
            str(e.get("spend_pattern") or "Unknown"),
            pipeline_version
        ))
        updated += 1

    conn.commit()
    print(f"  ✅ Enriched: {updated} records written (pipeline v{pipeline_version})")
    return updated


# ── UPDATE VENDOR KNOWLEDGE BASE ──────────────────────────────────────────────

def upsert_vendor(conn: sqlite3.Connection, vendor_name: str,
                  category: str = None, is_freelancer: bool = False,
                  is_company: bool = True, classification_source: str = "rule",
                  confidence: str = "medium", office_location: str = None,
                  claude_response: dict = None, manual_override: bool = False,
                  override_notes: str = "",
                  oc_country: str = None, oc_registration_number: str = None,
                  oc_entity_type: str = None, oc_jurisdiction: str = None) -> None:
    """
    Insert or update a vendor in the knowledge base.

    If vendor already exists:
    - Updates last_seen, transaction_count, total_spend
    - Only updates classification if NOT manually overridden
    - Accumulates knowledge, never loses it

    If vendor is new:
    - Full insert with all available data
    """
    now = datetime.now().isoformat()[:10]  # date only

    existing = conn.execute(
        "SELECT * FROM vendors WHERE vendor_name = ?", (vendor_name,)
    ).fetchone()

    if existing:
        # Vendor seen before — update counts and last_seen
        # Only update classification if not manually overridden
        if not existing["manual_override"]:
            conn.execute("""
                UPDATE vendors SET
                    last_seen = ?,
                    transaction_count = transaction_count + 1,
                    category = COALESCE(?, category),
                    is_freelancer = ?,
                    is_company = ?,
                    classification_source = ?,
                    classification_confidence = ?,
                    office_location = COALESCE(?, office_location),
                    claude_response = COALESCE(?, claude_response),
                    oc_country = COALESCE(?, oc_country),
                    oc_registration_number = COALESCE(?, oc_registration_number),
                    oc_entity_type = COALESCE(?, oc_entity_type),
                    oc_jurisdiction = COALESCE(?, oc_jurisdiction)
                WHERE vendor_name = ?
            """, (
                now, category, int(is_freelancer), int(is_company),
                classification_source, confidence, office_location,
                json.dumps(claude_response) if claude_response else None,
                oc_country or None, oc_registration_number or None,
                oc_entity_type or None, oc_jurisdiction or None,
                vendor_name
            ))
        else:
            # Manually overridden — only update counts, not classification
            conn.execute("""
                UPDATE vendors SET last_seen = ?, transaction_count = transaction_count + 1
                WHERE vendor_name = ?
            """, (now, vendor_name))
    else:
        # New vendor — full insert
        conn.execute("""
            INSERT INTO vendors (
                vendor_name, first_seen, last_seen, transaction_count,
                category, is_freelancer, is_company,
                classification_source, classification_confidence,
                office_location, claude_response,
                manual_override, override_notes,
                oc_country, oc_registration_number, oc_entity_type, oc_jurisdiction
            ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vendor_name, now, now,
            category, int(is_freelancer), int(is_company),
            classification_source, confidence,
            office_location,
            json.dumps(claude_response) if claude_response else None,
            int(manual_override), override_notes,
            oc_country or None, oc_registration_number or None,
            oc_entity_type or None, oc_jurisdiction or None
        ))

    conn.commit()


def bulk_upsert_vendors(conn: sqlite3.Connection,
                         classification: dict) -> None:
    """
    Update vendor knowledge base from category_mapper classification results.
    Called after every Claude classification run.

    classification format (from category_mapper.py):
    {
      "WeWork GmbH": {"category": "Real Estate", "location": "Berlin"},
      "J. Schmidt":  {"category": "Recruitment & HR", "location": null},
      ...
    }
    """
    print(f"  📚 Updating vendor knowledge base ({len(classification)} vendors)...")

    for vendor_name, result in classification.items():
        category = result.get("category", "")
        location = result.get("location")
        is_freelancer = category == "Recruitment & HR" and result.get("sub_commodity") == "Freelancer"

        upsert_vendor(
            conn=conn,
            vendor_name=vendor_name,
            category=category,
            is_freelancer=is_freelancer,
            is_company=not is_freelancer,
            classification_source="claude",
            confidence="high",
            office_location=location,
            claude_response=result,
            oc_country=result.get("oc_country"),
            oc_registration_number=result.get("oc_registration_number"),
            oc_entity_type=result.get("oc_entity_type"),
            oc_jurisdiction=result.get("oc_jurisdiction"),
        )

    print("  ✅ Vendor knowledge base updated")


# ── QUERY HELPERS ─────────────────────────────────────────────────────────────

def get_full_transaction_view(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Join raw + enriched into a single DataFrame for dashboard use.
    This is what the dashboard reads — the full picture per transaction.
    """
    query = """
        SELECT
            r.id, r.supplier, r.spend, r.spend_eur, r.fx_rate, r.currency, r.date,
            r.description, r.cost_center, r.po_number,
            r.contract_id, r.contract_end, r.region,
            r.category_source, r.source_type,
            e.category_mapped, e.sub_commodity, e.office_location,
            e.po_status, e.contract_status,
            e.maverick_flag, e.shadow_it_flag, e.freelancer_flag,
            e.catalogue_flag, e.spend_pattern,
            e.pipeline_version, e.enriched_at
        FROM transactions_raw r
        LEFT JOIN transactions_enriched e ON e.raw_id = r.id
        ORDER BY r.date DESC
    """
    return pd.read_sql_query(query, conn)


def get_vendor_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return vendor knowledge base as DataFrame for dashboard."""
    return pd.read_sql_query(
        "SELECT * FROM vendors ORDER BY transaction_count DESC", conn
    )


def get_upload_history(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return upload log as DataFrame."""
    return pd.read_sql_query(
        "SELECT * FROM uploads ORDER BY uploaded_at DESC", conn
    )


def get_maverick_transactions(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return all maverick-flagged transactions joined with raw data."""
    query = """
        SELECT r.supplier, r.spend, r.date, r.description,
               r.po_number, r.cost_center,
               e.category_mapped, e.po_status, e.contract_status
        FROM transactions_enriched e
        JOIN transactions_raw r ON r.id = e.raw_id
        WHERE e.maverick_flag = 1
        ORDER BY r.spend DESC
    """
    return pd.read_sql_query(query, conn)


def get_vendor_detail_map(conn: sqlite3.Connection) -> dict:
    """
    Return per-vendor transaction detail for Compliance Scorecard expand panels.
    Dict keyed by vendor name, value has:
      recent_txns  — list of last 5 transactions (date, amount, po_number, description, po_status)
      monthly      — list of {month, amount} for last 6 months
      po_breakdown — {with_po, no_po, unknown} counts
      contracts    — sorted list of unique non-null contract IDs
    """
    try:
        df = pd.read_sql_query("""
            SELECT r.supplier,
                   COALESCE(r.spend_eur, r.spend, 0) AS amount,
                   r.date, r.description, r.po_number, r.contract_id,
                   e.po_status, e.contract_status
            FROM transactions_raw r
            LEFT JOIN transactions_enriched e ON e.raw_id = r.id
            WHERE r.supplier IS NOT NULL
            ORDER BY r.supplier, r.date DESC
        """, conn)
    except Exception:
        return {}

    if df.empty:
        return {}

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    cutoff = pd.Timestamp.now() - pd.DateOffset(months=6)
    result = {}

    for vendor, grp in df.groupby("supplier"):
        # recent transactions (last 5, newest first)
        recent = []
        for _, r in grp.head(5).iterrows():
            recent.append({
                "date":        r["date"].strftime("%Y-%m-%d") if pd.notna(r["date"]) else "—",
                "amount":      float(r["amount"] or 0),
                "po_number":   str(r["po_number"] or "—"),
                "description": str(r["description"] or "—")[:60],
                "po_status":   str(r["po_status"] or "Unknown"),
            })

        # 6-month spend trend
        recent6 = grp[grp["date"] >= cutoff].copy()
        recent6["month"] = recent6["date"].dt.to_period("M")
        monthly_raw = recent6.groupby("month")["amount"].sum().tail(6)
        monthly = [{"month": str(m), "amount": float(a)} for m, a in monthly_raw.items()]

        # PO breakdown
        ps = grp["po_status"].fillna("Unknown")
        with_po  = int((ps.str.contains("PO", case=False, na=False) & ~ps.str.contains("No PO", na=False)).sum())
        no_po    = int(ps.str.contains("No PO", case=False, na=False).sum())
        unknown  = int(ps.isin(["Unknown", ""]).sum())

        # unique contract IDs
        contracts = sorted({str(c) for c in grp["contract_id"].dropna() if str(c).strip() not in ("", "nan", "None")})

        result[str(vendor)] = {
            "recent_txns":  recent,
            "monthly":      monthly,
            "po_breakdown": {"with_po": with_po, "no_po": no_po, "unknown": unknown},
            "contracts":    contracts,
        }

    return result


def get_real_estate_by_location(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return Real Estate spend grouped by office location."""
    query = """
        SELECT
            e.office_location,
            COUNT(*) as transactions,
            SUM(r.spend) as total_spend,
            COUNT(DISTINCT r.supplier) as vendor_count
        FROM transactions_enriched e
        JOIN transactions_raw r ON r.id = e.raw_id
        WHERE e.category_mapped = 'Real Estate'
        GROUP BY e.office_location
        ORDER BY total_spend DESC
    """
    return pd.read_sql_query(query, conn)


def get_contracts(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return all scanned contracts ordered by scan date."""
    return pd.read_sql_query(
        "SELECT * FROM contracts ORDER BY scanned_at DESC", conn
    )


def get_expiring_contracts(conn: sqlite3.Connection, days: int = 90) -> pd.DataFrame:
    """Return contracts expiring within the next N days."""
    return pd.read_sql_query("""
        SELECT id, vendor_name, contract_type, end_date, notice_period_days,
               risk_score, risk_level, filename
        FROM contracts
        WHERE end_date IS NOT NULL
          AND date(end_date) BETWEEN date('now') AND date('now', ? || ' days')
        ORDER BY end_date ASC
    """, conn, params=(f"+{days}",))


# ── QUICK TEST ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Test: initialize DB, insert sample data, query it back.
    Run: python database.py
    Opens clients/default/spendlens.db — viewable in VS Code with SQLite Viewer.
    """
    print("Testing SpendLens database layer...")

    # Initialize
    init_database("default")
    conn = get_connection("default")

    # Sample data
    test_df = pd.DataFrame({
        "supplier":         ["WeWork GmbH", "WeWork GmbH", "Amazon Web Services", "J. Schmidt"],
        "spend":            [12500, 12500, 45000, 4800],
        "date":             ["2026-01-01", "2026-02-01", "2026-01-31", "2026-02-15"],
        "description":      ["Miete Büro Berlin", "Miete Büro Berlin", "AWS EC2 January", "Honorarrechnung"],
        "po_number":        [None, None, "PO-2026-001", None],
        "cost_center":      ["Facilities", "Facilities", "IT", "HR"],
        "category_mapped":  ["Real Estate", "Real Estate", "Cloud & Compute", "Recruitment & HR"],
        "po_status":        ["No PO", "No PO", "With PO", "No PO"],
        "maverick_flag":    [True, True, False, True],
        "shadow_it_flag":   [False, False, False, False],
        "freelancer_flag":  [False, False, False, True],
        "spend_pattern":    ["Recurring", "Recurring", "Irregular", "One-off"],
        "catalogue_flag":   ["Unknown", "Unknown", "Unknown", "Unknown"],
        "contract_status":  ["Unknown", "Unknown", "Unknown", "Unknown"],
        "office_location":  ["Berlin", "Berlin", None, None],
    })

    # Log upload
    upload_id = log_upload(conn, "test_accounting.csv", "accounting",
                           len(test_df), {"supplier": "supplier", "spend": "spend"})

    # Insert raw
    stats = insert_raw_transactions(conn, test_df, upload_id)

    # Insert enriched
    insert_enriched_transactions(conn, test_df, test_df)

    # Update vendor knowledge
    classification = {
        "WeWork GmbH":          {"category": "Real Estate", "location": "Berlin"},
        "Amazon Web Services":  {"category": "Cloud & Compute", "location": None},
        "J. Schmidt":           {"category": "Recruitment & HR", "location": None},
    }
    bulk_upsert_vendors(conn, classification)

    # Query back
    print("\n── Full Transaction View ───────────────────────────────")
    df_view = get_full_transaction_view(conn)
    print(df_view[["supplier", "spend", "category_mapped", "maverick_flag",
                   "freelancer_flag", "office_location"]].to_string(index=False))

    print("\n── Vendor Knowledge Base ───────────────────────────────")
    df_vendors = get_vendor_summary(conn)
    print(df_vendors[["vendor_name", "category", "is_freelancer",
                       "classification_source", "office_location"]].to_string(index=False))

    print("\n── Real Estate by Location ─────────────────────────────")
    df_re = get_real_estate_by_location(conn)
    print(df_re.to_string(index=False))

    conn.close()
    print("\n✅ Database test complete — open clients/default/spendlens.db in VS Code to browse")
