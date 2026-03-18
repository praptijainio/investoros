"""
CSV Client — handles all read/write operations on local CSV files.
Replaces the Google Sheets client. No API credentials needed.

Files:
  data/master.csv       — 262 funds (exported from Google Sheets)
  data/partners.csv     — partner-level contacts
  data/activity_feed.csv — enrichment log (news + YouTube)
"""
import csv
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

MASTER_FILE = config.MASTER_CSV
PARTNERS_FILE = config.PARTNERS_CSV
ACTIVITY_FILE = config.ACTIVITY_CSV


# ── Helpers ──────────────────────────────────────────────────────────────────

def _read_csv(filepath):
    """Returns list of dicts from a CSV file."""
    if not os.path.exists(filepath):
        return []
    with open(filepath, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def _write_csv(filepath, rows, fieldnames):
    """Overwrites a CSV file with the given rows."""
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def _append_csv(filepath, rows, fieldnames):
    """Appends rows to a CSV. Creates file with header if it doesn't exist."""
    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            if isinstance(row, list):
                row = dict(zip(fieldnames, row))
            writer.writerow(row)


# ── Master sheet (funds) ──────────────────────────────────────────────────────

def get_all_funds():
    """Returns list of dicts, one per fund row in master.csv."""
    funds = _read_csv(MASTER_FILE)
    if not funds:
        print(f"  [Warning] {MASTER_FILE} not found or empty. Run Step 1 in SETUP.md.")
    return funds

def get_fund_names():
    """Returns just the list of fund names."""
    funds = _read_csv(MASTER_FILE)
    return [f.get("Fund Name", "").strip() for f in funds if f.get("Fund Name", "").strip()]

def ensure_columns_exist():
    """
    Adds new columns to master.csv if they don't exist.
    Run once during setup.
    """
    funds = _read_csv(MASTER_FILE)
    if not funds:
        print(f"  Cannot run setup — {MASTER_FILE} not found. Export your sheet first.")
        return

    existing_cols = list(funds[0].keys())
    new_cols = [
        "Website", "YouTube Channel", "Twitter/X Handle",
        "Partner LinkedIn URLs", "Recent Investments (Auto)",
        "Recent News (Auto)", "Last Enriched"
    ]
    added = []
    for col in new_cols:
        if col not in existing_cols:
            existing_cols.append(col)
            added.append(col)
            for row in funds:
                row[col] = ""

    if added:
        _write_csv(MASTER_FILE, funds, existing_cols)
        for col in added:
            print(f"  Added column: {col}")
    else:
        print("  All columns already exist.")

def update_fund_field(fund_name, column_name, value):
    """Updates a specific field for a fund by matching fund name."""
    funds = _read_csv(MASTER_FILE)
    if not funds:
        return
    fieldnames = list(funds[0].keys())
    if column_name not in fieldnames:
        fieldnames.append(column_name)
        for f in funds:
            f.setdefault(column_name, "")

    updated = False
    for f in funds:
        if f.get("Fund Name", "").strip().lower() == fund_name.strip().lower():
            f[column_name] = value
            updated = True
            break

    if updated:
        _write_csv(MASTER_FILE, funds, fieldnames)
    else:
        print(f"  Fund not found: {fund_name}")


# ── Partners CSV ──────────────────────────────────────────────────────────────

PARTNERS_FIELDNAMES = ["Partner Name", "Fund Name", "Role",
                       "LinkedIn URL", "Twitter/X Handle", "Notes"]

def ensure_partners_file():
    """Creates partners.csv with headers if it doesn't exist."""
    if not os.path.exists(PARTNERS_FILE) or os.path.getsize(PARTNERS_FILE) == 0:
        with open(PARTNERS_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=PARTNERS_FIELDNAMES)
            writer.writeheader()
        print(f"  Created: {PARTNERS_FILE}")
    else:
        print(f"  Already exists: {PARTNERS_FILE}")


# ── Activity Feed CSV ─────────────────────────────────────────────────────────

ACTIVITY_FIELDNAMES = ["Date", "Fund Name", "Partner", "Source", "Headline", "URL", "Summary"]

def ensure_activity_file():
    """Creates activity_feed.csv with headers if it doesn't exist."""
    if not os.path.exists(ACTIVITY_FILE) or os.path.getsize(ACTIVITY_FILE) == 0:
        with open(ACTIVITY_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=ACTIVITY_FIELDNAMES)
            writer.writeheader()
        print(f"  Created: {ACTIVITY_FILE}")
    else:
        print(f"  Already exists: {ACTIVITY_FILE}")

def write_activity_rows(rows):
    """
    Appends new activity rows to activity_feed.csv.
    rows = list of [date, fund_name, partner, source, headline, url, summary]
    """
    if not rows:
        return
    _append_csv(ACTIVITY_FILE, rows, ACTIVITY_FIELDNAMES)
    print(f"  Written {len(rows)} activity rows to {ACTIVITY_FILE}")
