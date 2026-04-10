# ============================================================
# sheets_sync.py — Sync Property Data to Google Sheets
# ============================================================
# Exports your properties, tenants, and tasks to a Google Sheet
# so you always have an up-to-date spreadsheet for reporting.
#
# ONE-TIME SETUP:
#   1. Go to console.cloud.google.com
#   2. Create a new project → Enable "Google Sheets API"
#   3. Create a Service Account → Download the JSON key file
#   4. Rename it "google_credentials.json" and put it here
#   5. Open your Google Sheet → Share it with the service account email
#   6. Copy the Spreadsheet ID from the URL and paste into config.py
#
# Install the required library:
#   pip install gspread --break-system-packages
#
# Usage:
#   python sheets_sync.py           — sync all data to Google Sheets
#   python sheets_sync.py --check   — verify connection without syncing
# ============================================================

import sys
import json
from datetime import date
from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE
from database import get_connection


def get_sheets_client():
    """Connect to Google Sheets using the service account credentials."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("❌ Missing library. Install it by running:")
        print("   pip install gspread google-auth --break-system-packages")
        return None

    if not GOOGLE_SHEET_ID:
        print("❌ GOOGLE_SHEET_ID is empty in config.py — please set it first.")
        return None

    try:
        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds  = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        print("✅ Connected to Google Sheets.")
        return client
    except FileNotFoundError:
        print(f"❌ Credentials file not found: {GOOGLE_CREDENTIALS_FILE}")
        print("   See the setup steps at the top of this file.")
        return None
    except Exception as e:
        print(f"❌ Google Sheets connection failed: {e}")
        return None


def clear_and_write(worksheet, headers, rows):
    """Overwrite a worksheet with fresh data."""
    worksheet.clear()
    all_data = [headers] + rows
    worksheet.update(all_data, value_input_option="USER_ENTERED")
    print(f"  ✅ Updated '{worksheet.title}' — {len(rows)} row(s)")


def sync_properties(spreadsheet):
    """Write all properties to the 'Properties' sheet."""
    conn = get_connection()
    props = conn.execute("SELECT * FROM properties ORDER BY name").fetchall()
    conn.close()

    headers = ["Name", "Address", "State", "Type", "Rent ($/mo)", "Deposit ($)",
               "Beds", "Baths", "Notes", "ID"]
    rows = [
        [p["name"], p["address"] or "", p["state"] or "", p["type"] or "",
         p["rent"] or "", p["deposit"] or "", p["beds"] or "", p["baths"] or "",
         p["notes"] or "", p["id"]]
        for p in props
    ]

    try:
        ws = spreadsheet.worksheet("Properties")
    except Exception:
        ws = spreadsheet.add_worksheet("Properties", rows=100, cols=15)

    clear_and_write(ws, headers, rows)


def sync_tenants(spreadsheet):
    """Write all tenants to the 'Tenants' sheet."""
    conn = get_connection()
    tenants = conn.execute("""
        SELECT t.*, p.name AS property_name
        FROM tenants t
        LEFT JOIN properties p ON t.property_id = p.id
        ORDER BY t.name
    """).fetchall()
    conn.close()

    today = date.today()
    headers = ["Name", "Email", "Phone", "Property", "Status",
               "Lease Start", "Lease End", "Days Left", "Rent ($/mo)",
               "Deposit ($)", "Pet Deposit ($)", "Notes", "Tenant ID"]
    rows = []
    for t in tenants:
        days_left = ""
        if t["lease_end"]:
            try:
                end = date.fromisoformat(t["lease_end"])
                days_left = (end - today).days
            except Exception:
                pass

        rows.append([
            t["name"], t["email"] or "", t["phone"] or "",
            t["property_name"] or "", t["status"] or "",
            t["lease_start"] or "", t["lease_end"] or "", days_left,
            t["rent"] or "", t["deposit"] or "", t["pet_deposit"] or "",
            t["notes"] or "", t["id"]
        ])

    try:
        ws = spreadsheet.worksheet("Tenants")
    except Exception:
        ws = spreadsheet.add_worksheet("Tenants", rows=200, cols=15)

    clear_and_write(ws, headers, rows)


def sync_tasks(spreadsheet):
    """Write all open tasks to the 'Tasks' sheet."""
    conn = get_connection()
    tasks = conn.execute("""
        SELECT t.*, p.name AS property_name
        FROM tasks t
        LEFT JOIN properties p ON t.property_id = p.id
        ORDER BY CASE t.priority
            WHEN 'Urgent' THEN 1 WHEN 'High' THEN 2
            WHEN 'Medium' THEN 3 WHEN 'Low'  THEN 4
        END, t.deadline
    """).fetchall()
    conn.close()

    headers = ["Title", "Property", "Priority", "Status", "Category",
               "Assignee", "Deadline", "Notes", "Task ID"]
    rows = [
        [t["title"], t["property_name"] or "", t["priority"] or "",
         t["status"] or "", t["category"] or "", t["assignee"] or "",
         t["deadline"] or "", t["notes"] or "", t["id"]]
        for t in tasks
    ]

    try:
        ws = spreadsheet.worksheet("Tasks")
    except Exception:
        ws = spreadsheet.add_worksheet("Tasks", rows=200, cols=12)

    clear_and_write(ws, headers, rows)


def sync_email_log(spreadsheet):
    """Write recent email history to the 'Email Log' sheet."""
    conn = get_connection()
    logs = conn.execute("""
        SELECT el.*, t.name AS tenant_name, p.name AS property_name
        FROM email_log el
        LEFT JOIN tenants t ON el.tenant_id = t.id
        LEFT JOIN properties p ON el.property_id = p.id
        ORDER BY el.sent_at DESC
        LIMIT 200
    """).fetchall()
    conn.close()

    headers = ["Sent At", "To", "Subject", "Type", "Tenant", "Property", "Status"]
    rows = [
        [l["sent_at"], l["to_email"], l["subject"], l["type"] or "",
         l["tenant_name"] or "", l["property_name"] or "", l["status"]]
        for l in logs
    ]

    try:
        ws = spreadsheet.worksheet("Email Log")
    except Exception:
        ws = spreadsheet.add_worksheet("Email Log", rows=300, cols=10)

    clear_and_write(ws, headers, rows)


def sync_all():
    """Sync all data to Google Sheets."""
    print(f"\n📊 Google Sheets Sync — {date.today().strftime('%B %d, %Y')}")
    print(f"   Sheet ID: {GOOGLE_SHEET_ID}")
    print("-" * 50)

    client = get_sheets_client()
    if not client:
        return

    try:
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
        print(f"  📄 Opened: {spreadsheet.title}\n")
    except Exception as e:
        print(f"❌ Could not open spreadsheet: {e}")
        print("   Make sure you shared the sheet with your service account email.")
        return

    sync_properties(spreadsheet)
    sync_tenants(spreadsheet)
    sync_tasks(spreadsheet)
    sync_email_log(spreadsheet)

    print(f"\n✅ Sync complete! View your sheet:")
    print(f"   https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}")


def check_connection():
    """Just test the connection without writing any data."""
    print("Testing Google Sheets connection...")
    client = get_sheets_client()
    if client:
        try:
            spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
            print(f"✅ Connection successful! Sheet: '{spreadsheet.title}'")
            worksheets = spreadsheet.worksheets()
            print(f"   Existing tabs: {[ws.title for ws in worksheets]}")
        except Exception as e:
            print(f"❌ Could not open spreadsheet: {e}")


# ============================================================
# Run directly
# ============================================================
if __name__ == "__main__":
    if "--check" in sys.argv:
        check_connection()
    else:
        sync_all()
