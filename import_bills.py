"""
NOTION BILLS IMPORTER
=====================
This script imports your Notion Bills & Payment Tracker CSV
into your LK Property app database (lk_properties.db).

HOW TO USE:
1. Upload this file to your project on GitHub (same folder as app.py)
2. Also upload the CSV file renamed to: notion_bills.csv
3. In Render, go to your service → Shell (or run locally)
4. Run: python import_bills.py
5. Done! All bills will appear in your app.

OR run locally:
1. Put this file and notion_bills.csv in the same folder as your lk_properties.db
2. Run: python import_bills.py
"""

import csv
import sqlite3
import re
import os

# ── CONFIG ──────────────────────────────────────────────────
CSV_FILE = "notion_bills.csv"        # rename your exported CSV to this
DB_FILE  = "lk_properties.db"       # your app database

# Map Notion Payment Status → app status (paid / unpaid)
STATUS_MAP = {
    "Paid":                    "paid",
    "Upcoming":                "unpaid",
    "Unpaid":                  "unpaid",
    "Scheduled":               "unpaid",
    "Pending":                 "unpaid",
    "TBD":                     "unpaid",
    "Expired":                 "paid",
    "Inactive":                "paid",
    "Canceled":                "paid",
    "Sold":                    "paid",
    "NA":                      "paid",
    "Transferred to Tenant":   "paid",
    "Transferred back to Owner": "unpaid",
    "":                        "unpaid",
}

# Map Notion Payment Type → app category
CATEGORY_MAP = {
    "Mortgage":               "mortgage",
    "LOAN(HELOC)":            "mortgage",
    "Seller Finance Loan":    "mortgage",
    "PML":                    "mortgage",
    "Insurance":              "insurance",
    "Property Tax":           "taxes",
    "School Tax":             "taxes",
    "Bond Bill Debt":         "taxes",
    "Electric":               "utilities",
    "Gas":                    "utilities",
    "Natural Gas":            "utilities",
    "Propane Gas":            "utilities",
    "Water":                  "utilities",
    "Sewer":                  "utilities",
    "Sewer, Water":           "utilities",
    "Sewer, Utilities, Water":"utilities",
    "Domestic, Water":        "utilities",
    "Fire Protection, Water": "utilities",
    "Electric, Water":        "utilities",
    "Water-Well":             "utilities",
    "Sewer, Water-FREE":      "utilities",
    "Wifi":                   "utilities",
    "HOA":                    "other",
    "HOA Fees":               "other",
    "Annual Registration, Hoa Assessment": "other",
    "Garbage/Trash":          "other",
    "Snow Plowing":           "other",
    "Landscaping":            "other",
    "Property Management Fee":"other",
    "Annual Registration":    "other",
    "Trust Services":         "other",
    "Utilities":              "utilities",
    "Service":                "other",
    "Lease":                  "other",
    "Attorney's Fee":         "other",
    "Porta Potty Rental  / Lapierre": "other",
    "":                       "other",
}

def clean_amount(val):
    """Convert '$1,234.56' → 1234.56"""
    if not val:
        return 0.0
    cleaned = re.sub(r'[^\d.]', '', val)
    try:
        return float(cleaned)
    except:
        return 0.0

def clean_date(val):
    """Try to normalize date strings"""
    if not val or val.strip() in ("", "No Date"):
        return ""
    val = val.strip()
    # Try MM/DD/YYYY → YYYY-MM-DD
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', val)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return val

def get_or_create_property(conn, name):
    """Find existing property by name (fuzzy) or create new one."""
    if not name or not name.strip():
        return None
    name = name.strip()
    # Exact match first
    row = conn.execute(
        "SELECT id FROM properties WHERE LOWER(name)=LOWER(?)", (name,)
    ).fetchone()
    if row:
        return row[0]
    # Partial match (property name contains the address)
    row = conn.execute(
        "SELECT id FROM properties WHERE LOWER(?) LIKE '%' || LOWER(name) || '%' OR LOWER(name) LIKE '%' || LOWER(?) || '%'",
        (name, name)
    ).fetchone()
    if row:
        return row[0]
    # Create new property
    cur = conn.execute(
        "INSERT INTO properties (name, address) VALUES (?, ?)",
        (name, name)
    )
    print(f"  ➕ Created property: {name}")
    return cur.lastrowid

def main():
    if not os.path.exists(CSV_FILE):
        print(f"❌ CSV file not found: {CSV_FILE}")
        print(f"   Please rename your Notion export to '{CSV_FILE}' and place it in the same folder.")
        return

    if not os.path.exists(DB_FILE):
        print(f"❌ Database not found: {DB_FILE}")
        print(f"   Make sure you run this from the same folder as your app.")
        return

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row

    imported = 0
    skipped  = 0
    errors   = 0

    with open(CSV_FILE, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\n📂 Found {len(rows)} rows in CSV")
    print("─" * 50)

    for i, row in enumerate(rows):
        try:
            property_name = row.get('Property Name', '').strip()
            payment_type  = row.get('Payment Type', '').strip()
            pay_status    = row.get('Payment Status', '').strip()
            amount_due    = clean_amount(row.get('Amount Due', ''))
            last_paid_amt = clean_amount(row.get('Last Paid Amount', ''))
            due_date      = clean_date(row.get('Due Date', ''))
            next_bill     = clean_date(row.get('Next Bill Date', ''))
            notes_parts   = []

            # Build description from payment type + billing details
            billing_details = row.get('Billing Details', '').strip()
            billing_freq    = row.get('Billing Frequency', '').strip()
            provider        = row.get('Provider', '').strip()
            policy_type     = row.get('Policy Type', '').strip()

            description = payment_type or policy_type or "Bill"
            if provider:
                description += f" - {provider}"

            # Build notes
            if billing_details:
                notes_parts.append(billing_details)
            if billing_freq:
                notes_parts.append(f"Frequency: {billing_freq}")
            if row.get('Notes', '').strip():
                notes_parts.append(row['Notes'].strip())
            if row.get('Account/Loan Number', '').strip():
                notes_parts.append(f"Account: {row['Account/Loan Number'].strip()}")
            if row.get('Policy Number', '').strip():
                notes_parts.append(f"Policy: {row['Policy Number'].strip()}")
            if row.get('LLC/Account Name', '').strip():
                notes_parts.append(f"LLC: {row['LLC/Account Name'].strip()}")
            if row.get('Paid Month/Year/Invoice', '').strip():
                notes_parts.append(f"Paid: {row['Paid Month/Year/Invoice'].strip()}")

            notes = " | ".join(notes_parts)[:500]  # cap at 500 chars

            # Determine amount (use last paid if amount due is 0)
            amount = amount_due if amount_due > 0 else last_paid_amt

            # Determine status
            status = STATUS_MAP.get(pay_status, "unpaid")

            # Determine category
            category = CATEGORY_MAP.get(payment_type, "other")

            # Effective due date (use next_bill if no due_date)
            effective_date = due_date or next_bill

            # Get or create property
            property_id = get_or_create_property(conn, property_name)

            # Insert bill
            conn.execute(
                "INSERT INTO bills (property_id, description, amount, due_date, status, category, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (property_id, description, amount, effective_date, status, category, notes)
            )
            imported += 1

            if imported % 20 == 0:
                print(f"  ✅ Imported {imported} bills...")

        except Exception as e:
            print(f"  ⚠️  Row {i+1} error: {e}")
            errors += 1

    conn.commit()
    conn.close()

    print("─" * 50)
    print(f"\n🎉 Import complete!")
    print(f"   ✅ Imported: {imported} bills")
    print(f"   ⚠️  Errors:   {errors}")
    print(f"\nOpen your app and go to Bills — filter by property to see everything!")

if __name__ == "__main__":
    main()
