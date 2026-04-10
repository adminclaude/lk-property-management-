# ============================================================
# database.py — SQLite Database Setup for LK Property Group
# ============================================================
# This script creates and manages your local property database.
# Run this FIRST before any other scripts.
#
# Usage:
#   python database.py          — creates database and shows summary
#   python database.py --demo   — also adds sample data to test with
# ============================================================

import sqlite3
import sys
from datetime import date, timedelta
from config import DATABASE_PATH


def get_connection():
    """Open a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row   # lets you access columns by name
    return conn


def create_tables():
    """Create all database tables if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # --- Properties table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            address     TEXT,
            state       TEXT,
            type        TEXT,           -- 'Long-term rental', 'Airbnb / short-term', etc.
            rent        REAL,           -- monthly rent in dollars
            deposit     REAL,           -- security deposit amount
            beds        INTEGER,
            baths       REAL,
            notes       TEXT,
            color       TEXT,           -- color tag (hex code)
            created_at  TEXT DEFAULT (date('now'))
        )
    """)

    # --- Tenants table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            email        TEXT,
            phone        TEXT,
            property_id  TEXT REFERENCES properties(id),
            lease_start  TEXT,          -- date string: YYYY-MM-DD
            lease_end    TEXT,          -- date string: YYYY-MM-DD
            rent         REAL,
            deposit      REAL,
            pet_deposit  REAL,
            status       TEXT DEFAULT 'Active',   -- 'Active', 'Inactive', 'Prospective'
            notes        TEXT,
            created_at   TEXT DEFAULT (date('now'))
        )
    """)

    # --- Tasks / Maintenance Requests table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id           TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            property_id  TEXT REFERENCES properties(id),
            tenant_id    TEXT REFERENCES tenants(id),
            assignee     TEXT,
            priority     TEXT DEFAULT 'Medium',   -- 'Urgent', 'High', 'Medium', 'Low'
            status       TEXT DEFAULT 'To Do',    -- 'To Do', 'In Progress', 'Done'
            category     TEXT,                    -- 'Maintenance', 'Move-in', 'Move-out', etc.
            deadline     TEXT,                    -- date string: YYYY-MM-DD
            notes        TEXT,
            created_at   TEXT DEFAULT (date('now')),
            last_followup_sent TEXT              -- date last follow-up email was sent
        )
    """)

    # --- Rent Payments table ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rent_payments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id    TEXT REFERENCES tenants(id),
            property_id  TEXT REFERENCES properties(id),
            amount       REAL,
            due_date     TEXT,           -- date string: YYYY-MM-DD
            paid_date    TEXT,           -- NULL if not yet paid
            status       TEXT DEFAULT 'Pending',   -- 'Pending', 'Paid', 'Late'
            notes        TEXT,
            created_at   TEXT DEFAULT (date('now'))
        )
    """)

    # --- Email Log table (tracks what emails were sent and when) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            sent_at      TEXT DEFAULT (datetime('now')),
            to_email     TEXT,
            subject      TEXT,
            type         TEXT,           -- 'rent_reminder', 'lease_alert', 'maintenance', etc.
            tenant_id    TEXT,
            property_id  TEXT,
            status       TEXT DEFAULT 'sent'   -- 'sent' or 'failed'
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Database tables created successfully.")


def add_property(name, address="", state="", prop_type="Long-term rental",
                 rent=0, deposit=0, beds=0, baths=0, notes="", color="#7F77DD"):
    """
    Add a new property to the database.

    Example:
        add_property("Oakwood Ave Unit 2B", "123 Oakwood Ave", "FL", rent=1500, beds=2)
    """
    import uuid
    prop_id = str(uuid.uuid4())[:8]
    conn = get_connection()
    conn.execute("""
        INSERT INTO properties (id, name, address, state, type, rent, deposit, beds, baths, notes, color)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (prop_id, name, address, state, prop_type, rent, deposit, beds, baths, notes, color))
    conn.commit()
    conn.close()
    print(f"✅ Property added: {name} (ID: {prop_id})")
    return prop_id


def add_tenant(name, email, phone="", property_id=None,
               lease_start=None, lease_end=None, rent=0,
               deposit=0, pet_deposit=0, status="Active", notes=""):
    """
    Add a new tenant to the database.

    Example:
        add_tenant("Jane Smith", "jane@email.com", phone="555-0100",
                   property_id="abc12345", lease_start="2025-01-01",
                   lease_end="2025-12-31", rent=1500)
    """
    import uuid
    tenant_id = str(uuid.uuid4())[:8]
    conn = get_connection()
    conn.execute("""
        INSERT INTO tenants (id, name, email, phone, property_id, lease_start, lease_end,
                             rent, deposit, pet_deposit, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (tenant_id, name, email, phone, property_id, lease_start, lease_end,
          rent, deposit, pet_deposit, status, notes))
    conn.commit()
    conn.close()
    print(f"✅ Tenant added: {name} (ID: {tenant_id})")
    return tenant_id


def add_task(title, property_id=None, tenant_id=None, assignee="",
             priority="Medium", status="To Do", category="", deadline=None, notes=""):
    """
    Add a new task or maintenance request.

    Example:
        add_task("Fix leaking faucet in kitchen", property_id="abc12345",
                 priority="High", category="Maintenance", deadline="2025-06-10")
    """
    import uuid
    task_id = str(uuid.uuid4())[:8]
    conn = get_connection()
    conn.execute("""
        INSERT INTO tasks (id, title, property_id, tenant_id, assignee, priority,
                          status, category, deadline, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (task_id, title, property_id, tenant_id, assignee, priority, status,
          category, deadline, notes))
    conn.commit()
    conn.close()
    print(f"✅ Task added: {title} (ID: {task_id})")
    return task_id


def get_all_properties():
    """Return a list of all properties."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM properties ORDER BY name").fetchall()
    conn.close()
    return rows


def get_active_tenants():
    """Return all active tenants with their property info."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.*, p.name AS property_name, p.address AS property_address
        FROM tenants t
        LEFT JOIN properties p ON t.property_id = p.id
        WHERE t.status = 'Active'
        ORDER BY t.name
    """).fetchall()
    conn.close()
    return rows


def get_open_tasks():
    """Return all tasks that are not Done, sorted by priority."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.*, p.name AS property_name
        FROM tasks t
        LEFT JOIN properties p ON t.property_id = p.id
        WHERE t.status != 'Done'
        ORDER BY CASE t.priority
            WHEN 'Urgent' THEN 1
            WHEN 'High'   THEN 2
            WHEN 'Medium' THEN 3
            WHEN 'Low'    THEN 4
        END
    """).fetchall()
    conn.close()
    return rows


def print_summary():
    """Print a quick summary of your database contents."""
    conn = get_connection()
    props   = conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
    tenants = conn.execute("SELECT COUNT(*) FROM tenants WHERE status='Active'").fetchone()[0]
    tasks   = conn.execute("SELECT COUNT(*) FROM tasks WHERE status != 'Done'").fetchone()[0]
    conn.close()
    print("\n📊 LK Property Group — Database Summary")
    print("=" * 40)
    print(f"  Properties      : {props}")
    print(f"  Active tenants  : {tenants}")
    print(f"  Open tasks      : {tasks}")
    print("=" * 40)


def add_demo_data():
    """Add sample data so you can test all automations right away."""
    today = date.today()

    prop1 = add_property("Oakwood Ave Unit 2B", "123 Oakwood Ave, Tampa", "FL",
                         rent=1500, deposit=1500, beds=2, baths=1)
    prop2 = add_property("Maple Street House", "456 Maple St, Orlando", "FL",
                         rent=2200, deposit=2200, beds=3, baths=2, prop_type="Long-term rental")

    # Tenant whose lease expires in 85 days (triggers renewal alert)
    add_tenant("Sarah Johnson", "sarah.johnson@email.com", "555-0101",
               property_id=prop1,
               lease_start=str(today - timedelta(days=280)),
               lease_end=str(today + timedelta(days=85)),
               rent=1500, deposit=1500)

    # Tenant with rent due in 4 days (triggers rent reminder)
    add_tenant("Marcus Williams", "marcus.w@email.com", "555-0202",
               property_id=prop2,
               lease_start=str(today - timedelta(days=60)),
               lease_end=str(today + timedelta(days=305)),
               rent=2200, deposit=2200)

    # Open maintenance task older than 3 days
    add_task("Fix leaking faucet in bathroom", property_id=prop1,
             priority="High", category="Maintenance", status="In Progress",
             deadline=str(today + timedelta(days=2)))

    add_task("Replace broken window screen", property_id=prop2,
             priority="Medium", category="Maintenance", status="To Do",
             deadline=str(today + timedelta(days=7)))

    print("\n🎉 Demo data added! Run the automations to test them.")


# ============================================================
# Run directly to set up the database
# ============================================================
if __name__ == "__main__":
    print("Setting up LK Property Group database...")
    create_tables()

    if "--demo" in sys.argv:
        print("\nAdding demo data...")
        add_demo_data()

    print_summary()
    print(f"\nDatabase saved to: {DATABASE_PATH}")
    print("Next step: edit config.py with your Gmail settings, then run run_automations.py")
