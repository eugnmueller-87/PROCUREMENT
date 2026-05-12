"""
icarus_schedule.py — Daily Icarus scan for Windows Task Scheduler.

Designed to run headless at 07:00 each morning via Task Scheduler.
Results land in icarus_memory.db; load_recent() surfaces them when
the dashboard opens.

Run manually to test:
    .venv/Scripts/python.exe icarus_schedule.py
"""

import os
import sys

# Force UTF-8 stdout/stderr so emoji in icarus.py print() calls don't crash
# on Windows consoles that default to CP1252.
os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import logging
from datetime import datetime, timezone
from pathlib import Path

# ── Working directory ─────────────────────────────────────────────────────────
# Task Scheduler may start from System32; pin to this script's directory so
# relative paths (clients/default/icarus_memory.db, .env) resolve correctly.
os.chdir(Path(__file__).parent)

from dotenv import load_dotenv
load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "icarus_schedule.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("icarus_schedule")

# ── Categories (all 11 — matches IcarusPanel default) ────────────────────────
CLIENT_CATEGORIES = [
    "Cloud & Compute",
    "AI/ML APIs & Data",
    "IT Software & SaaS",
    "Telecom & Voice",
    "Recruitment & HR",
    "Professional Services",
    "Marketing & Campaigns",
    "Facilities & Office",
    "Real Estate",
    "Hardware & Equipment",
    "Travel & Expenses",
]

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set — aborting")
        sys.exit(1)

    log.info("=== Icarus daily scan started ===")

    import icarus
    try:
        result = icarus.run(
            client_categories=CLIENT_CATEGORIES,
            client_name="SpendLens",
        )
        log.info(
            "Scan complete — %d signals from %d articles (query_id=%s)",
            len(result["signals"]),
            result["article_count"],
            result["query_id"],
        )
    except Exception as e:
        log.exception("Scan failed: %s", e)
        sys.exit(1)

    log.info("=== Done ===")


if __name__ == "__main__":
    main()
