"""
category_mapper.py — SpendLens AI Category Mapper
===================================================
Takes raw accounting/invoice data and assigns each row to one of the
11 SpendLens taxonomy categories. Also extracts office locations for
Real Estate transactions.

HOW IT WORKS (step by step):
─────────────────────────────
1. DEDUPLICATE  — extract unique vendors from the full dataset
                  (could be 1000+ rows, but typically 30–100 unique vendors)

2. CACHE CHECK  — load vendor_cache.json and skip vendors already classified.
                  Only new/unknown vendors go to Claude. Reruns are free.

3. ENRICH       — for each NEW vendor, collect sample transaction descriptions
                  so Claude has context, not just a name

4. BATCH CALL   — send only new vendors to Claude in ONE API call
                  → returns category + location (for Real Estate)

5. SAVE CACHE   — merge new results into vendor_cache.json for next time

6. APPLY        — merge full classification back onto all original rows

This keeps API costs low: 1 call instead of 1000, and $0 on reruns.
"""

import json
import os
import pandas as pd
from anthropic import Anthropic

# ── CACHE FILE ────────────────────────────────────────────────────────────────
# Stored next to this script. Persists between runs.
# Format: {"WeWork GmbH": {"category": "Real Estate", "location": "Berlin"}, ...}
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor_cache.json")


def load_cache() -> dict:
    """Load existing vendor classifications from disk. Returns empty dict if no cache yet."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        print(f"  💾 Cache loaded: {len(cache)} vendors already classified")
        return cache
    print("  💾 No cache found — starting fresh")
    return {}


def save_cache(cache: dict) -> None:
    """Save updated classifications to disk. Never overwrites — always merges."""
    # Load existing cache first to avoid losing anything
    existing = load_cache() if os.path.exists(CACHE_FILE) else {}
    merged = {**existing, **cache}  # new results take priority if vendor reappears
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"  💾 Cache saved: {len(merged)} total vendors stored in vendor_cache.json")


# ── 1. THE 11 TAXONOMY CATEGORIES ─────────────────────────────────────────────
# These are SpendLens standard categories. Claude will always pick from this list.

TAXONOMY = [
    "Cloud & Compute",       # AWS, GCP, Azure, hosting, infrastructure
    "AI/ML APIs & Data",     # OpenAI, Anthropic, data providers, ML tools
    "IT Software & SaaS",    # SAP, Salesforce, Microsoft 365, any software license
    "Telecom & Voice",       # Telekom, Vodafone, mobile, internet, VoIP
    "Recruitment & HR",      # Recruiters, Personio, job boards, payroll services
    "Professional Services", # Consulting, legal, audit, tax, advisory
    "Marketing & Campaigns", # Agencies, media buying, HubSpot, events
    "Facilities & Office",   # Cleaning, furniture, plants, security, office supplies
    "Real Estate",           # Office rent, WeWork, coworking, property leases
    "Hardware & Equipment",  # Laptops, servers, phones, physical devices
    "Travel & Expenses",     # Flights, hotels, BCD Travel, car rental
]

# ── 2. HELPER: COLLECT VENDOR SAMPLES ─────────────────────────────────────────

def build_vendor_samples(df: pd.DataFrame,
                          vendor_col: str = "supplier",
                          description_col: str = None,
                          max_vendors: int = 150,
                          samples_per_vendor: int = 3) -> list[dict]:
    """
    Group rows by vendor and collect sample descriptions.

    Why: Claude needs context to classify ambiguous vendors.
    E.g. "Amazon" alone is ambiguous — descriptions clarify if it's
    AWS (Cloud) or office supplies (Facilities & Office).

    Returns a list like:
    [
      {"vendor": "WeWork GmbH", "descriptions": ["Miete April Berlin", "Büro München Q2"]},
      {"vendor": "ISS Deutschland", "descriptions": ["Reinigungsservice", "Facility Management"]},
      ...
    ]
    """
    if vendor_col not in df.columns:
        raise ValueError(f"Column '{vendor_col}' not found. Available: {list(df.columns)}")

    vendor_samples = []

    # Get unique vendors (limit to max_vendors to keep prompt size manageable)
    unique_vendors = df[vendor_col].dropna().unique()[:max_vendors]

    for vendor in unique_vendors:
        vendor_rows = df[df[vendor_col] == vendor]

        # Collect description samples if a description column exists
        descriptions = []
        if description_col and description_col in df.columns:
            raw_descs = vendor_rows[description_col].dropna().astype(str).tolist()
            # Take up to N samples, strip whitespace
            descriptions = [d.strip() for d in raw_descs[:samples_per_vendor] if d.strip()]

        vendor_samples.append({
            "vendor": str(vendor),
            "descriptions": descriptions
        })

    print(f"  📦 Built samples for {len(vendor_samples)} unique vendors")
    return vendor_samples


# ── 3a. MOCK MODE (for testing without API credits) ───────────────────────────

# Simple keyword rules that simulate what Claude would return.
# Not as smart as Claude but good enough to test the full pipeline.
MOCK_RULES = [
    (["wework", "rent", "miete", "lease", "immobilien", "realty", "office park"], "Real Estate"),
    (["aws", "amazon web", "google cloud", "gcp", "azure", "cloud", "hosting"],   "Cloud & Compute"),
    (["openai", "anthropic", "huggingface", "dataiku", "snowflake", "palantir"],  "AI/ML APIs & Data"),
    (["sap", "salesforce", "microsoft", "oracle", "servicenow", "atlassian"],     "IT Software & SaaS"),
    (["telekom", "vodafone", "telefonica", "o2", "telecom", "internet", "voice"], "Telecom & Voice"),
    (["randstad", "personio", "stepstone", "linkedin", "hays", "adecco", "hr"],   "Recruitment & HR"),
    (["mckinsey", "bcg", "deloitte", "pwc", "kpmg", "accenture", "freshfields"], "Professional Services"),
    (["wpp", "publicis", "hubspot", "meta ads", "google ads", "marketing"],       "Marketing & Campaigns"),
    (["iss ", "cbre", "cleaning", "facility", "lyreco", "staples", "plants"],     "Facilities & Office"),
    (["dell", "lenovo", "apple", "hp ", "hardware", "laptop", "server"],          "Hardware & Equipment"),
    (["lufthansa", "bcd travel", "hotel", "airbnb", "booking", "travel", "flug"], "Travel & Expenses"),
]

def mock_classify_vendors(vendor_samples: list[dict]) -> dict:
    """
    Classify vendors using simple keyword rules — no API call needed.
    Used when MOCK_MODE=True. Good for testing the pipeline end-to-end.

    Not as accurate as Claude but covers the obvious cases in the test dataset.
    """
    print("  🧪 MOCK MODE — no API call, using keyword rules")
    result = {}

    for item in vendor_samples:
        vendor = item["vendor"]
        # Combine vendor name + descriptions into one searchable string
        text = (vendor + " " + " ".join(item.get("descriptions", []))).lower()

        matched_category = "Uncategorized"
        for keywords, category in MOCK_RULES:
            if any(kw in text for kw in keywords):
                matched_category = category
                break

        # Extract location hint for Real Estate from descriptions
        location = None
        if matched_category == "Real Estate":
            for desc in item.get("descriptions", []):
                # Look for common city names in description
                for city in ["Berlin", "Munich", "München", "Hamburg", "Frankfurt",
                             "London", "Paris", "Amsterdam", "Vienna", "Wien", "Zurich", "Zürich"]:
                    if city.lower() in desc.lower():
                        location = city
                        break

        result[vendor] = {"category": matched_category, "location": location}

    print(f"  ✅ Mock classified {len(result)} vendors")
    return result


# ── 3b. CORE: CLAUDE API CALL (with chunking for large vendor lists) ──────────

CHUNK_SIZE = 100  # vendors per API call — safe limit for token budget

def _classify_chunk(chunk: list[dict], client, taxonomy_text: str) -> dict:
    """
    Classify a single chunk of vendors in one API call.
    Called by classify_vendors_with_claude() in a loop.
    Kept separate so a failed chunk can be retried without redoing others.
    """
    vendors_json = json.dumps(chunk, ensure_ascii=False, indent=2)

    prompt = f"""You are a procurement data expert classifying accounting transactions.

TASK:
Classify each vendor into exactly one of the 11 categories below.
For "Real Estate" vendors, also extract the office location (city or country)
from the transaction descriptions. For all other categories, set location to null.

CATEGORIES:
{taxonomy_text}

CATEGORY GUIDANCE:
- "Real Estate": office rent, WeWork, coworking spaces, any property lease or Miete
- "Facilities & Office": cleaning, furniture, plants, security, catering, office supplies
- "Cloud & Compute": AWS, GCP, Azure, any cloud hosting or infrastructure
- "Professional Services": consulting, legal, audit, tax, advisory firms
- "IT Software & SaaS": software licenses, SaaS tools, ERP systems
- "Travel & Expenses": flights, hotels, travel agencies, car rental
- "Recruitment & HR": recruiters, HR software, job boards, staffing agencies
- "AI/ML APIs & Data": AI APIs, ML platforms, data providers
- "Telecom & Voice": mobile, internet, VoIP, telecom providers
- "Marketing & Campaigns": agencies, media, events, marketing tools
- "Hardware & Equipment": laptops, servers, phones, physical devices

VENDORS TO CLASSIFY:
{vendors_json}

Return ONLY a valid JSON object. No explanation, no markdown, no backticks.
Format:
{{
  "VendorName": {{"category": "Category Name", "location": "City or null"}},
  ...
}}
JSON:"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,  # enough for 100 vendors
        messages=[{"role": "user", "content": prompt}]
    )

    raw_text = response.content[0].text.strip()

    # Strip accidental markdown fences
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    return json.loads(raw_text)


def classify_vendors_with_claude(vendor_samples: list[dict],
                                  api_key: str = None) -> dict:
    """
    Classify vendors using Claude API — chunked for large vendor lists.

    Why chunking:
    - 1000 vendors in one prompt = token overflow + unreliable output
    - Split into chunks of 100 → 10 clean API calls, each reliable
    - Each chunk is saved to cache as it completes
      → if run crashes at chunk 7, chunks 1-6 are already cached

    Returns merged dict of all chunks:
    {
      "WeWork GmbH":         {"category": "Real Estate", "location": "Berlin"},
      "ISS Deutschland":     {"category": "Facilities & Office", "location": null},
      "Amazon Web Services": {"category": "Cloud & Compute", "location": null},
      ...
    }
    """
    # Resolve API key
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("No API key found. Set ANTHROPIC_API_KEY or pass api_key=")

    client = Anthropic(api_key=api_key)
    taxonomy_text = "\n".join([f"  - {cat}" for cat in TAXONOMY])

    # Split vendor list into chunks of CHUNK_SIZE
    chunks = [vendor_samples[i:i + CHUNK_SIZE]
              for i in range(0, len(vendor_samples), CHUNK_SIZE)]

    total_chunks = len(chunks)
    print(f"  🤖 {len(vendor_samples)} vendors → {total_chunks} chunks of {CHUNK_SIZE}")

    all_results = {}

    for i, chunk in enumerate(chunks, start=1):
        print(f"  📤 Chunk {i}/{total_chunks} — classifying {len(chunk)} vendors...")
        try:
            chunk_result = _classify_chunk(chunk, client, taxonomy_text)
            all_results.update(chunk_result)

            # Save to cache after every chunk — if crash happens, progress is kept
            save_cache(chunk_result)
            print(f"  ✅ Chunk {i}/{total_chunks} done — {len(chunk_result)} vendors classified")

        except json.JSONDecodeError as e:
            # JSON parse failed for this chunk — skip and continue with others
            print(f"  ⚠ Chunk {i} JSON parse error: {e} — skipping, will show as Uncategorized")
        except Exception as e:
            # API error for this chunk — skip and continue
            print(f"  ⚠ Chunk {i} API error: {e} — skipping")

    print(f"  ✅ All chunks done — {len(all_results)} vendors classified total")
    return all_results


# ── 4. APPLY MAPPING BACK TO ALL ROWS ─────────────────────────────────────────

def apply_category_mapping(df: pd.DataFrame,
                            classification: dict,
                            vendor_col: str = "supplier") -> pd.DataFrame:
    """
    Merge Claude's classification back onto every row in the full dataset.

    Steps:
    - Add 'category_mapped' column with the taxonomy category
    - Add 'office_location' column (filled only for Real Estate rows)
    - Rows with vendors not in classification → 'Uncategorized'

    Why a new column: we keep the original category column intact
    so you can always compare what the source data said vs what we mapped.
    """
    df = df.copy()

    # Extract category and location from the classification dict
    df["category_mapped"] = df[vendor_col].map(
        lambda v: classification.get(str(v), {}).get("category", "Uncategorized")
    )

    df["office_location"] = df[vendor_col].map(
        lambda v: classification.get(str(v), {}).get("location", None)
    )

    # Count and report results
    mapped = (df["category_mapped"] != "Uncategorized").sum()
    unmapped = (df["category_mapped"] == "Uncategorized").sum()
    real_estate_rows = (df["category_mapped"] == "Real Estate").sum()

    print(f"  ✅ Mapped {mapped} rows | ⚠ {unmapped} uncategorized")
    print(f"  🏢 Real Estate rows: {real_estate_rows}")

    return df


# ── 5. REAL ESTATE LOCATION SUMMARY ───────────────────────────────────────────

def real_estate_by_location(df: pd.DataFrame,
                              spend_col: str = "spend") -> pd.DataFrame:
    """
    Summarize Real Estate spend by office location.

    Used to power the 'which country/city pays which rent' view.

    Returns a DataFrame like:
    | office_location | total_spend | vendor_count | transactions |
    |-----------------|-------------|--------------|--------------|
    | Berlin          | €125,000    | 2            | 18           |
    | Munich          | €48,000     | 1            | 6            |
    | London          | €95,000     | 1            | 12           |
    """
    re_df = df[df["category_mapped"] == "Real Estate"].copy()

    if re_df.empty:
        print("  ℹ No Real Estate rows found")
        return pd.DataFrame()

    if spend_col not in re_df.columns:
        print(f"  ⚠ Spend column '{spend_col}' not found")
        return pd.DataFrame()

    # Fill missing locations with "Unknown"
    re_df["office_location"] = re_df["office_location"].fillna("Unknown")

    summary = re_df.groupby("office_location").agg(
        total_spend=(spend_col, "sum"),
        vendor_count=("supplier", "nunique"),
        transactions=(spend_col, "count")
    ).reset_index().sort_values("total_spend", ascending=False)

    return summary


# ── 6. FULL PIPELINE (entry point) ────────────────────────────────────────────

def run_category_mapping(df: pd.DataFrame,
                          vendor_col: str = "supplier",
                          description_col: str = None,
                          spend_col: str = "spend",
                          api_key: str = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Full pipeline: takes a cleaned DataFrame, returns it enriched with
    category_mapped and office_location columns.

    Also returns a Real Estate location summary as a second DataFrame.

    Usage:
        enriched_df, re_summary = run_category_mapping(cleaned_df)

    Args:
        df              — cleaned DataFrame (output of data_cleanup.py)
        vendor_col      — name of the vendor/supplier column
        description_col — optional: column with transaction descriptions
        spend_col       — name of the spend/amount column
        api_key         — Claude API key (or set ANTHROPIC_API_KEY env var)

    Returns:
        enriched_df     — original df + category_mapped + office_location
        re_summary      — Real Estate spend grouped by office location
    """
    print("\n── Category Mapping Pipeline ──────────────────────────")

    # Step 1: Load cache — vendors already classified won't cost API calls
    print("Step 1: Checking cache for already-classified vendors...")
    cache = load_cache()

    # Step 2: Extract unique vendors and find which ones are new (not in cache)
    print("Step 2: Extracting unique vendors and description samples...")
    all_vendor_samples = build_vendor_samples(df, vendor_col, description_col)

    new_vendor_samples = [v for v in all_vendor_samples if v["vendor"] not in cache]
    cached_count = len(all_vendor_samples) - len(new_vendor_samples)
    print(f"  ⚡ {cached_count} vendors from cache | {len(new_vendor_samples)} new vendors need classification")

    # Step 3: Only call Claude for new vendors
    new_classification = {}
    if new_vendor_samples:
        # ── Set MOCK_MODE=True to test pipeline without API credits ──
        MOCK_MODE = not bool(api_key or os.environ.get("ANTHROPIC_API_KEY"))

        if MOCK_MODE:
            print("Step 3: No API key found — running in MOCK MODE (keyword rules, no cost)...")
            new_classification = mock_classify_vendors(new_vendor_samples)
        else:
            print("Step 3: Classifying new vendors with Claude API...")
            new_classification = classify_vendors_with_claude(new_vendor_samples, api_key)

        # Save new results to cache so next run skips these too
        if new_classification:
            save_cache(new_classification)
    else:
        print("Step 3: All vendors already in cache — skipping API call 🎉")

    # Step 4: Merge cache + new results into one full classification dict
    full_classification = {**cache, **new_classification}

    if not full_classification:
        print("  ⚠ Classification failed — returning df with 'Uncategorized'")
        df["category_mapped"] = "Uncategorized"
        df["office_location"] = None
        return df, pd.DataFrame()

    # Step 5: Apply mapping back to all rows
    print("Step 4: Applying mapping to all rows...")
    enriched_df = apply_category_mapping(df, full_classification, vendor_col)

    # Step 6: Build Real Estate location summary
    print("Step 5: Building Real Estate location summary...")
    re_summary = real_estate_by_location(enriched_df, spend_col)

    if not re_summary.empty:
        print("\n  🏢 Real Estate by Location:")
        print(re_summary.to_string(index=False))

    print("── Done ✅ ────────────────────────────────────────────\n")
    return enriched_df, re_summary


# ── 7. QUICK TEST ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Test with a small fake dataset that mimics real accounting exports.
    Run: python category_mapper.py
    Requires ANTHROPIC_API_KEY in environment.
    """
    test_df = pd.DataFrame({
        "supplier": [
            "WeWork GmbH", "WeWork GmbH", "ISS Deutschland", "ISS Deutschland",
            "Amazon Web Services", "Amazon Web Services", "Lufthansa", "Lufthansa",
            "SAP SE", "Freshfields Bruckhaus", "Randstad Deutschland",
            "Deutsche Telekom AG", "Lyreco GmbH", "Lyreco GmbH",
        ],
        "spend": [
            12500, 12500, 3200, 3200,
            45000, 47000, 1800, 2200,
            8500, 15000, 6000,
            2800, 890, 920,
        ],
        "description": [
            "Miete April Büro Berlin Mitte", "Miete März Büro Berlin Mitte",
            "Reinigungsservice Q1", "Facility Management Q2",
            "AWS Compute EC2 April", "AWS S3 Storage March",
            "Flug FRA-LHR Business", "Flug MUC-JFK Economy",
            "SAP License Annual", "Legal Advisory M&A",
            "Temp Staff IT April", "Telekommunikation Q1",
            "Bürobedarf Papier", "Toner & Druckerzubehör",
        ]
    })

    print("Test dataset:")
    print(test_df.to_string(index=False))
    print()

    enriched, re_summary = run_category_mapping(
        test_df,
        vendor_col="supplier",
        description_col="description",
        spend_col="spend"
    )

    print("\nEnriched dataset (category_mapped + office_location):")
    print(enriched[["supplier", "spend", "description", "category_mapped", "office_location"]].to_string(index=False))

    if not re_summary.empty:
        print("\nReal Estate by Location:")
        print(re_summary.to_string(index=False))
