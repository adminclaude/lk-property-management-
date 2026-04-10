# ============================================================
# menu.py — LK Property Group Easy Data Entry
# ============================================================
import sqlite3
from datetime import datetime
from config import DATABASE_PATH

def get_conn():
    return sqlite3.connect(DATABASE_PATH)

def clear():
    print("\n" * 2)

def header(title):
    print("=" * 50)
    print(f"  LK Property Group — {title}")
    print("=" * 50)

def pause():
    input("\nPress Enter to continue...")

# ----------------------------------------------------------
# VIEW HELPERS
# ----------------------------------------------------------
def view_properties():
    conn = get_conn()
    rows = conn.execute("SELECT id, name, address, unit FROM properties").fetchall()
    conn.close()
    if not rows:
        print("\n  No properties found.")
        return []
    print("\n  ID  Name                 Address")
    print("  " + "-" * 55)
    for r in rows:
        unit = f" (Unit {r[3]})" if r[3] else ""
        print(f"  {r[0]:<4} {r[1]:<20} {r[2]}{unit}")
    return rows

def view_tenants():
    conn = get_conn()
    rows = conn.execute("""
        SELECT t.id, t.full_name, t.email, t.rent_amount, t.rent_due_day,
               t.lease_end, p.address
        FROM tenants t
        LEFT JOIN properties p ON t.property_id = p.id
        WHERE t.is_active = 1
    """).fetchall()
    conn.close()
    if not rows:
        print("\n  No tenants found.")
        return []
    print("\n  ID  Name                 Email                        Rent         Due  Lease End")
    print("  " + "-" * 85)
    for r in rows:
        print(f"  {r[0]:<4} {r[1]:<20} {r[2]:<28} PHP {r[3]:>8,.2f}  {r[4]:>2}   {r[5] or 'N/A'}")
    return rows

def view_maintenance():
    conn = get_conn()
    rows = conn.execute("""
        SELECT m.id, m.description, m.status, m.date_reported,
               t.full_name, p.address
        FROM maintenance m
        LEFT JOIN tenants t ON m.tenant_id = t.id
        LEFT JOIN properties p ON m.property_id = p.id
        WHERE m.status = 'open'
    """).fetchall()
    conn.close()
    if not rows:
        print("\n  No open maintenance tasks.")
        return []
    print("\n  ID  Description                    Tenant               Reported")
    print("  " + "-" * 70)
    for r in rows:
        print(f"  {r[0]:<4} {r[1][:30]:<31} {(r[4] or 'N/A'):<20} {r[3]}")
    return rows

# ----------------------------------------------------------
# ADD PROPERTY
# ----------------------------------------------------------
def add_property():
    clear()
    header("Add New Property")
    print()
    name    = input("  Property name       : ").strip()
    address = input("  Full address        : ").strip()
    unit    = input("  Unit number (optional, press Enter to skip): ").strip()
    notes   = input("  Notes (optional)    : ").strip()

    if not name or not address:
        print("\n  ❌ Name and address are required.")
        pause()
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO properties (name, address, unit, notes) VALUES (?, ?, ?, ?)",
        (name, address, unit, notes)
    )
    conn.commit()
    prop_id = c.lastrowid
    conn.close()
    print(f"\n  ✅ Property added! (ID: {prop_id})")
    pause()

# ----------------------------------------------------------
# ADD TENANT
# ----------------------------------------------------------
def add_tenant():
    clear()
    header("Add New Tenant")

    print("\n  Available Properties:")
    props = view_properties()
    if not props:
        pause()
        return

    print()
    try:
        prop_id = int(input("  Enter Property ID   : ").strip())
    except ValueError:
        print("\n  ❌ Invalid ID.")
        pause()
        return

    print()
    full_name = input("  Tenant full name    : ").strip()
    email     = input("  Email address       : ").strip()
    phone     = input("  Phone number        : ").strip()

    try:
        rent_amount = float(input("  Monthly rent (PHP)  : ").strip())
        rent_due_day = int(input("  Rent due day (1-28) : ").strip())
    except ValueError:
        print("\n  ❌ Invalid rent amount or due day.")
        pause()
        return

    lease_start = input("  Lease start (YYYY-MM-DD): ").strip()
    lease_end   = input("  Lease end   (YYYY-MM-DD): ").strip()

    if not full_name or not email:
        print("\n  ❌ Name and email are required.")
        pause()
        return

    conn = get_conn()
    conn.execute("""
        INSERT INTO tenants
        (property_id, full_name, email, phone, rent_amount, rent_due_day,
         lease_start, lease_end, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (prop_id, full_name, email, phone, rent_amount, rent_due_day,
          lease_start, lease_end))
    conn.commit()
    conn.close()
    print(f"\n  ✅ Tenant '{full_name}' added successfully!")
    pause()

# ----------------------------------------------------------
# ADD MAINTENANCE TASK
# ----------------------------------------------------------
def add_maintenance():
    clear()
    header("Add Maintenance Task")

    print("\n  Available Properties:")
    props = view_properties()
    if not props:
        pause()
        return

    print()
    try:
        prop_id = int(input("  Enter Property ID   : ").strip())
    except ValueError:
        print("\n  ❌ Invalid ID.")
        pause()
        return

    print("\n  Active Tenants:")
    conn = get_conn()
    tenants = conn.execute(
        "SELECT id, full_name FROM tenants WHERE property_id = ? AND is_active = 1",
        (prop_id,)
    ).fetchall()
    conn.close()

    tenant_id = None
    if tenants:
        for t in tenants:
            print(f"    {t[0]}. {t[1]}")
        try:
            tenant_id = int(input("  Enter Tenant ID (or 0 to skip): ").strip())
            if tenant_id == 0:
                tenant_id = None
        except ValueError:
            tenant_id = None

    print()
    description = input("  Describe the issue  : ").strip()
    today = datetime.today().strftime("%Y-%m-%d")

    if not description:
        print("\n  ❌ Description is required.")
        pause()
        return

    conn = get_conn()
    conn.execute("""
        INSERT INTO maintenance (property_id, tenant_id, description, date_reported, status)
        VALUES (?, ?, ?, ?, 'open')
    """, (prop_id, tenant_id, description, today))
    conn.commit()
    conn.close()
    print(f"\n  ✅ Maintenance task added! (Reported: {today})")
    pause()

# ----------------------------------------------------------
# RESOLVE MAINTENANCE
# ----------------------------------------------------------
def resolve_maintenance():
    clear()
    header("Resolve Maintenance Task")

    print("\n  Open Tasks:")
    tasks = view_maintenance()
    if not tasks:
        pause()
        return

    print()
    try:
        task_id = int(input("  Enter Task ID to mark resolved: ").strip())
    except ValueError:
        print("\n  ❌ Invalid ID.")
        pause()
        return

    today = datetime.today().strftime("%Y-%m-%d")
    conn = get_conn()
    conn.execute(
        "UPDATE maintenance SET status = 'resolved', date_resolved = ? WHERE id = ?",
        (today, task_id)
    )
    conn.commit()
    conn.close()
    print(f"\n  ✅ Task #{task_id} marked as resolved!")
    pause()

# ----------------------------------------------------------
# DEACTIVATE TENANT
# ----------------------------------------------------------
def deactivate_tenant():
    clear()
    header("Remove / Deactivate Tenant")

    print("\n  Active Tenants:")
    tenants = view_tenants()
    if not tenants:
        pause()
        return

    print()
    try:
        tenant_id = int(input("  Enter Tenant ID to deactivate: ").strip())
    except ValueError:
        print("\n  ❌ Invalid ID.")
        pause()
        return

    confirm = input(f"  Are you sure? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("\n  Cancelled.")
        pause()
        return

    conn = get_conn()
    conn.execute("UPDATE tenants SET is_active = 0 WHERE id = ?", (tenant_id,))
    conn.commit()
    conn.close()
    print(f"\n  ✅ Tenant #{tenant_id} deactivated.")
    pause()

# ----------------------------------------------------------
# MAIN MENU
# ----------------------------------------------------------
def main():
    while True:
        clear()
        header("Main Menu")
        print("""
  --- ADD ---
  1. Add Property
  2. Add Tenant
  3. Add Maintenance Task

  --- VIEW ---
  4. View All Properties
  5. View All Tenants
  6. View Open Maintenance Tasks

  --- MANAGE ---
  7. Mark Maintenance as Resolved
  8. Deactivate Tenant (moved out)

  0. Exit
""")
        choice = input("  Choose an option: ").strip()

        if choice == "1":
            add_property()
        elif choice == "2":
            add_tenant()
        elif choice == "3":
            add_maintenance()
        elif choice == "4":
            clear(); header("All Properties"); view_properties(); pause()
        elif choice == "5":
            clear(); header("All Tenants"); view_tenants(); pause()
        elif choice == "6":
            clear(); header("Open Maintenance Tasks"); view_maintenance(); pause()
        elif choice == "7":
            resolve_maintenance()
        elif choice == "8":
            deactivate_tenant()
        elif choice == "0":
            print("\n  Goodbye! 👋\n")
            break
        else:
            print("\n  ❌ Invalid option, try again.")
            pause()

if __name__ == "__main__":
    main()
