"""
Google Sheets client — handles all read/write operations.
"""
import gspread
from google.oauth2.service_account import Credentials
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

def get_client():
    creds = Credentials.from_service_account_file(config.CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)

def get_sheet(tab_name):
    client = get_client()
    spreadsheet = client.open_by_key(config.SHEET_ID)
    return spreadsheet.worksheet(tab_name)

def get_all_funds():
    """Returns list of dicts, one per fund row in Master sheet."""
    sheet = get_sheet(config.MASTER_SHEET)
    return sheet.get_all_records()

def get_fund_names():
    """Returns just the list of fund names for matching against RSS."""
    sheet = get_sheet(config.MASTER_SHEET)
    col = sheet.col_values(1)
    return [name.strip() for name in col[1:] if name.strip()]  # skip header

def ensure_columns_exist():
    """
    Adds new columns to Master sheet if they don't exist yet.
    Run once during setup.
    """
    sheet = get_sheet(config.MASTER_SHEET)
    headers = sheet.row_values(1)
    new_cols = ["Website", "YouTube Channel", "Twitter/X Handle",
                "Partner LinkedIn URLs", "Recent Investments (Auto)",
                "Recent News (Auto)", "Last Enriched"]
    added = 0
    for col in new_cols:
        if col not in headers:
            sheet.update_cell(1, len(headers) + 1 + added, col)
            added += 1
            print(f"  Added column: {col}")
    if added == 0:
        print("  All columns already exist.")

def ensure_partners_sheet():
    """Creates Partners sheet if it doesn't exist."""
    client = get_client()
    spreadsheet = client.open_by_key(config.SHEET_ID)
    existing = [ws.title for ws in spreadsheet.worksheets()]
    if config.PARTNERS_SHEET not in existing:
        ws = spreadsheet.add_worksheet(title=config.PARTNERS_SHEET, rows=500, cols=10)
        ws.append_row(["Partner Name", "Fund Name", "Role",
                       "LinkedIn URL", "Twitter/X Handle", "Notes"])
        print(f"  Created sheet: {config.PARTNERS_SHEET}")
    else:
        print(f"  Sheet already exists: {config.PARTNERS_SHEET}")

def ensure_activity_sheet():
    """Creates Activity Feed sheet if it doesn't exist."""
    client = get_client()
    spreadsheet = client.open_by_key(config.SHEET_ID)
    existing = [ws.title for ws in spreadsheet.worksheets()]
    if config.ACTIVITY_SHEET not in existing:
        ws = spreadsheet.add_worksheet(title=config.ACTIVITY_SHEET, rows=2000, cols=7)
        ws.append_row(["Date", "Fund Name", "Partner", "Source", "Headline", "URL", "Summary"])
        print(f"  Created sheet: {config.ACTIVITY_SHEET}")
    else:
        print(f"  Sheet already exists: {config.ACTIVITY_SHEET}")

def write_activity_rows(rows):
    """
    Appends new activity rows to the Activity Feed sheet.
    rows = list of [date, fund_name, partner, source, headline, url, summary]
    """
    if not rows:
        return
    sheet = get_sheet(config.ACTIVITY_SHEET)
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"  Written {len(rows)} activity rows.")

def update_fund_field(fund_name, column_name, value):
    """Updates a specific cell for a fund by matching fund name."""
    sheet = get_sheet(config.MASTER_SHEET)
    headers = sheet.row_values(1)
    if column_name not in headers:
        print(f"  Column '{column_name}' not found.")
        return
    col_idx = headers.index(column_name) + 1
    fund_col = sheet.col_values(1)
    for i, name in enumerate(fund_col):
        if name.strip().lower() == fund_name.strip().lower():
            sheet.update_cell(i + 1, col_idx, value)
            return
    print(f"  Fund not found: {fund_name}")
