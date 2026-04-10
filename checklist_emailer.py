# ============================================================
# checklist_emailer.py — Move-In / Move-Out Checklist Emails
# ============================================================
# Sends a professional checklist email to a tenant when they
# are moving in or moving out. Run this manually when you have
# a new tenant or an upcoming move-out.
#
# Usage:
#   python checklist_emailer.py --movein  <tenant_id>   — send move-in checklist
#   python checklist_emailer.py --moveout <tenant_id>   — send move-out checklist
#   python checklist_emailer.py --list                  — list all tenant IDs
#
# Example:
#   python checklist_emailer.py --movein abc12345
# ============================================================

import sys
import sqlite3
from datetime import date
from config import OWNER_EMAIL, COMPANY_NAME, COMPANY_PHONE
from gmail_sender import send_email, build_email_html
from database import get_connection


# ============================================================
# Checklist Content
# ============================================================

MOVE_IN_CHECKLIST = [
    ("Lease agreement", "Make sure you have a fully signed copy of your lease."),
    ("First month's rent + security deposit", "Confirm both payments have cleared before collecting keys."),
    ("Move-in inspection", "We will do a walkthrough together — all rooms will be photographed and documented."),
    ("Welcome packet", "You'll receive house rules, emergency contacts, and maintenance instructions."),
    ("Key handover", "You will receive all keys, fobs, and access codes."),
    ("Utility transfer", "Please transfer electricity, water, and internet into your name by your move-in date."),
    ("Tenant portal access", "We'll set you up with online access to pay rent and submit maintenance requests."),
    ("Emergency contact", "Save our emergency maintenance number for urgent issues outside business hours."),
    ("Parking & mailbox", "We'll walk you through parking assignment and mailbox access."),
    ("Pets", "If you have pets, ensure the pet addendum and pet deposit are on file."),
]

MOVE_OUT_CHECKLIST = [
    ("Notice to vacate", "Ensure you submitted written notice as required by your lease."),
    ("Cleaning", "The unit must be returned in the same clean condition as move-in. "
                 "This includes: all rooms swept/mopped/vacuumed, oven and fridge cleaned, "
                 "bathrooms scrubbed, and all trash removed."),
    ("Walls & fixtures", "Fill any nail holes with spackle. Replace any burned-out light bulbs."),
    ("Keys returned", "Return ALL keys, fobs, garage openers, and mailbox keys on or before your last day."),
    ("Forwarding address", "Provide us with your new address so we can send your security deposit."),
    ("Move-out inspection", "We will conduct a final walkthrough and compare it to your move-in photos."),
    ("Security deposit timeline", "Your security deposit (minus any deductions) will be returned "
                                   "within the legally required timeframe for your state."),
    ("Final utility readings", "Cancel or transfer your utilities on or after your last day."),
    ("Personal belongings", "Remove all personal items — anything left behind may be disposed of."),
    ("Parking space", "Ensure your parking space is cleared of all vehicles and personal items."),
]

AIRBNB_TURNOVER_CHECKLIST = [
    ("Linen change", "Replace all bed linens, pillowcases, and towels with fresh ones."),
    ("Bathroom restock", "Restock: toilet paper (2+ rolls), hand soap, shampoo, conditioner, body wash."),
    ("Kitchen restock", "Restock: dish soap, sponge, paper towels, coffee/tea if provided."),
    ("Trash & recycling", "Empty all bins. Replace trash bags."),
    ("Vacuum & mop", "Vacuum all carpets and rugs. Mop hard floors."),
    ("Wipe down surfaces", "Wipe down counters, stovetop, microwave inside/outside, fridge exterior."),
    ("Check appliances", "Test TV remote, WiFi, AC/heat, and all appliances."),
    ("Check for damage", "Note and photograph any damage before the next guest checks in."),
    ("Lockbox / smart lock", "Confirm entry code is working and reset if needed."),
    ("Welcome note", "Leave a fresh welcome card and any check-in instructions."),
]


def get_tenant_by_id(tenant_id):
    """Look up a tenant by their ID."""
    conn = get_connection()
    row = conn.execute("""
        SELECT t.*, p.name AS property_name, p.address AS property_address
        FROM tenants t
        LEFT JOIN properties p ON t.property_id = p.id
        WHERE t.id = ?
    """, (tenant_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_all_tenants():
    """Print a table of all tenants and their IDs."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.id, t.name, t.email, t.status, p.name AS property_name
        FROM tenants t
        LEFT JOIN properties p ON t.property_id = p.id
        ORDER BY t.name
    """).fetchall()
    conn.close()

    print("\n📋 All Tenants:")
    print(f"{'ID':<12} {'Name':<25} {'Email':<30} {'Status':<12} {'Property'}")
    print("-" * 95)
    for r in rows:
        print(f"{r['id']:<12} {r['name']:<25} {r['email'] or 'no email':<30} {r['status']:<12} {r['property_name'] or '—'}")


def build_checklist_rows(items):
    """Convert a list of (title, description) tuples into HTML table rows."""
    rows = ""
    for i, (title, desc) in enumerate(items, 1):
        bg = "#fafafa" if i % 2 == 0 else "#ffffff"
        rows += f"""
        <tr style="background:{bg};">
          <td style="padding:10px 8px;border-bottom:1px solid #eee;width:28px;color:#7F77DD;
                     font-weight:bold;font-size:14px;vertical-align:top;">{i}.</td>
          <td style="padding:10px 8px;border-bottom:1px solid #eee;vertical-align:top;">
            <div style="font-weight:600;font-size:13px;color:#111;">{title}</div>
            <div style="font-size:12px;color:#555;margin-top:3px;">{desc}</div>
          </td>
        </tr>"""
    return rows


def send_move_in_checklist(tenant_id):
    """Send the move-in checklist email to a specific tenant."""
    tenant = get_tenant_by_id(tenant_id)
    if not tenant:
        print(f"❌ Tenant with ID '{tenant_id}' not found. Run --list to see all tenants.")
        return

    if not tenant["email"]:
        print(f"❌ {tenant['name']} has no email address on file.")
        return

    name       = tenant["name"].split()[0]
    prop_name  = tenant.get("property_name", "your new home")
    move_date  = tenant.get("lease_start") or "your move-in date"
    rent       = f"${tenant['rent']:,.0f}/month" if tenant["rent"] else ""

    checklist_rows = build_checklist_rows(MOVE_IN_CHECKLIST)

    html = build_email_html(
        title    = "Move-In Checklist",
        greeting = f"Welcome, {name}! 🎉",
        body_paragraphs = [
            f"We're so excited to welcome you to <b>{prop_name}</b>! "
            f"Please review this checklist to make sure your move-in goes smoothly.",
            f"""<table style="width:100%;border-collapse:collapse;margin:8px 0;">
              {checklist_rows}
            </table>""",
            f"If you have any questions before or during your move-in, "
            f"please don't hesitate to reach out. We're here to help!",
        ]
    )

    sent = send_email(
        to_email    = tenant["email"],
        subject     = f"Welcome to {prop_name} — Your Move-In Checklist",
        html_body   = html,
        email_type  = "move_in_checklist",
        tenant_id   = tenant["id"],
        property_id = tenant.get("property_id"),
    )

    # CC the owner
    send_email(
        to_email    = OWNER_EMAIL,
        subject     = f"📋 Move-In Checklist Sent — {tenant['name']} ({prop_name})",
        html_body   = html,
        email_type  = "move_in_checklist_copy",
        tenant_id   = tenant["id"],
    )

    if sent:
        print(f"✅ Move-in checklist sent to {tenant['name']} ({tenant['email']})")


def send_move_out_checklist(tenant_id):
    """Send the move-out checklist email to a specific tenant."""
    tenant = get_tenant_by_id(tenant_id)
    if not tenant:
        print(f"❌ Tenant with ID '{tenant_id}' not found. Run --list to see all tenants.")
        return

    if not tenant["email"]:
        print(f"❌ {tenant['name']} has no email address on file.")
        return

    name       = tenant["name"].split()[0]
    prop_name  = tenant.get("property_name", "your unit")
    move_date  = tenant.get("lease_end") or "your move-out date"

    checklist_rows = build_checklist_rows(MOVE_OUT_CHECKLIST)

    html = build_email_html(
        title    = "Move-Out Checklist",
        greeting = f"Hi {name},",
        body_paragraphs = [
            f"As your lease for <b>{prop_name}</b> comes to an end, "
            f"please review the following checklist to ensure a smooth move-out process "
            f"and the timely return of your security deposit.",
            f"""<table style="width:100%;border-collapse:collapse;margin:8px 0;">
              {checklist_rows}
            </table>""",
            f"<b>Move-out date:</b> {move_date}",
            "If you have any questions, please contact us as soon as possible. "
            "We appreciate your tenancy and wish you all the best in your next home!",
        ]
    )

    sent = send_email(
        to_email    = tenant["email"],
        subject     = f"Move-Out Checklist — {prop_name}",
        html_body   = html,
        email_type  = "move_out_checklist",
        tenant_id   = tenant["id"],
        property_id = tenant.get("property_id"),
    )

    # CC the owner
    send_email(
        to_email    = OWNER_EMAIL,
        subject     = f"📋 Move-Out Checklist Sent — {tenant['name']} ({prop_name})",
        html_body   = html,
        email_type  = "move_out_checklist_copy",
        tenant_id   = tenant["id"],
    )

    if sent:
        print(f"✅ Move-out checklist sent to {tenant['name']} ({tenant['email']})")


def send_airbnb_turnover_checklist(cleaning_crew_email, property_name, checkin_date):
    """
    Send the Airbnb turnover checklist to the cleaning crew.

    Example:
        send_airbnb_turnover_checklist("cleaner@email.com", "Oakwood Unit 2B", "2026-04-15")
    """
    checklist_rows = build_checklist_rows(AIRBNB_TURNOVER_CHECKLIST)

    html = build_email_html(
        title    = "Turnover Checklist",
        greeting = "Hi,",
        body_paragraphs = [
            f"Please complete the following turnover for <b>{property_name}</b> "
            f"before the next guest checks in on <b>{checkin_date}</b>.",
            f"""<table style="width:100%;border-collapse:collapse;margin:8px 0;">
              {checklist_rows}
            </table>""",
            "Please confirm by reply when the unit is guest-ready. Thank you!",
        ]
    )

    sent = send_email(
        to_email   = cleaning_crew_email,
        subject    = f"Turnover Checklist — {property_name} (Check-in: {checkin_date})",
        html_body  = html,
        email_type = "airbnb_turnover",
    )

    if sent:
        print(f"✅ Turnover checklist sent to {cleaning_crew_email}")


# ============================================================
# Command-line interface
# ============================================================
if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or "--help" in args:
        print("""
Usage:
  python checklist_emailer.py --list
      List all tenants and their IDs

  python checklist_emailer.py --movein <tenant_id>
      Send move-in checklist to a tenant

  python checklist_emailer.py --moveout <tenant_id>
      Send move-out checklist to a tenant

  python checklist_emailer.py --airbnb <cleaner_email> "<property_name>" <checkin_date>
      Send Airbnb turnover checklist to cleaning crew

Examples:
  python checklist_emailer.py --list
  python checklist_emailer.py --movein abc12345
  python checklist_emailer.py --moveout abc12345
  python checklist_emailer.py --airbnb cleaner@email.com "Oakwood Unit 2B" 2026-04-15
        """)

    elif "--list" in args:
        list_all_tenants()

    elif "--movein" in args:
        idx = args.index("--movein")
        if idx + 1 < len(args):
            send_move_in_checklist(args[idx + 1])
        else:
            print("❌ Please provide a tenant ID after --movein")

    elif "--moveout" in args:
        idx = args.index("--moveout")
        if idx + 1 < len(args):
            send_move_out_checklist(args[idx + 1])
        else:
            print("❌ Please provide a tenant ID after --moveout")

    elif "--airbnb" in args:
        idx = args.index("--airbnb")
        if idx + 3 < len(args):
            send_airbnb_turnover_checklist(args[idx+1], args[idx+2], args[idx+3])
        else:
            print("❌ Usage: --airbnb <email> \"<property>\" <date>")
