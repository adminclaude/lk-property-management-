# ============================================================
# rent_reminders.py — Automated Rent Reminder Emails
# ============================================================
# Sends a friendly reminder email to tenants a few days before
# rent is due. Run this script daily (see scheduler.py).
#
# How it works:
#   - Looks at each active tenant's lease and monthly rent due date
#   - If rent is due in X days (set in config.py), sends reminder
#   - Logs every email sent so it doesn't send duplicates
#
# Usage:
#   python rent_reminders.py           — send reminders for today
#   python rent_reminders.py --preview — show who would get emails (no sending)
# ============================================================

import sys
import sqlite3
from datetime import date, timedelta
from config import (DATABASE_PATH, RENT_REMINDER_DAYS_BEFORE,
                    OWNER_EMAIL, COMPANY_NAME)
from gmail_sender import send_email, build_email_html
from database import get_active_tenants, get_connection


def get_due_date_this_month(lease_start_str):
    """
    Figure out what day of the month rent is due.
    We use the same day as the lease start date.
    Example: lease started on the 1st → rent is due the 1st each month.
    """
    if not lease_start_str:
        return 1   # default to 1st of month
    try:
        return int(lease_start_str.split("-")[2])  # day part of YYYY-MM-DD
    except Exception:
        return 1


def get_tenants_due_soon():
    """
    Return a list of tenants whose rent is due within RENT_REMINDER_DAYS_BEFORE days
    AND who haven't already received a reminder this month.
    """
    today = date.today()
    target_date = today + timedelta(days=RENT_REMINDER_DAYS_BEFORE)
    due_tenants = []

    tenants = get_active_tenants()
    conn = get_connection()

    for tenant in tenants:
        if not tenant["email"]:
            continue   # skip tenants with no email

        due_day = get_due_date_this_month(tenant["lease_start"])

        # Build the due date for this month
        try:
            due_this_month = date(target_date.year, target_date.month, due_day)
        except ValueError:
            continue   # e.g. Feb 30 doesn't exist

        # Is rent due exactly on the target date?
        if due_this_month != target_date:
            continue

        # Check if we already sent a reminder this month
        month_start = date(today.year, today.month, 1).isoformat()
        already_sent = conn.execute("""
            SELECT id FROM email_log
            WHERE type = 'rent_reminder'
              AND tenant_id = ?
              AND sent_at >= ?
        """, (tenant["id"], month_start)).fetchone()

        if already_sent:
            print(f"  ⏭  Skipping {tenant['name']} — reminder already sent this month")
            continue

        due_tenants.append({
            "tenant":   dict(tenant),
            "due_date": due_this_month,
        })

    conn.close()
    return due_tenants


def build_reminder_email(tenant, due_date):
    """Build the HTML for a rent reminder email."""
    name        = tenant["name"].split()[0]   # first name only
    amount      = f"${tenant['rent']:,.0f}" if tenant["rent"] else "your rent"
    prop_name   = tenant.get("property_name", "")
    days_away   = (due_date - date.today()).days

    if days_away == 1:
        days_label = "tomorrow"
    elif days_away == 0:
        days_label = "today"
    else:
        days_label = f"in {days_away} days"

    paragraphs = [
        f"This is a friendly reminder that your rent payment of <b>{amount}</b> "
        f"is due <b>{days_label}</b> ({due_date.strftime('%B %d, %Y')}).",
        f"Please ensure your payment is received on time to avoid any late fees.",
    ]

    if prop_name:
        paragraphs.append(f"Property: <b>{prop_name}</b>")

    paragraphs += [
        "If you have already made your payment or have any questions, "
        "please don't hesitate to reach out to us.",
        "Thank you for being a great tenant!",
    ]

    return build_email_html(
        title             = "Rent Reminder",
        greeting          = f"Hi {name},",
        body_paragraphs   = paragraphs,
    )


def send_rent_reminders(preview=False):
    """
    Main function: check who needs a reminder and send emails.

    Set preview=True to see who would get emails without actually sending.
    """
    print(f"\n🏠 Rent Reminders — {date.today().strftime('%B %d, %Y')}")
    print(f"   Looking for tenants with rent due in {RENT_REMINDER_DAYS_BEFORE} days...")
    print("-" * 50)

    due_tenants = get_tenants_due_soon()

    if not due_tenants:
        print("✅ No rent reminders to send today.")
        return

    print(f"Found {len(due_tenants)} tenant(s) to remind:\n")

    emails_to_send = []
    for item in due_tenants:
        tenant   = item["tenant"]
        due_date = item["due_date"]
        amount   = f"${tenant['rent']:,.0f}" if tenant["rent"] else ""

        print(f"  • {tenant['name']} ({tenant['email']})")
        print(f"    Property: {tenant.get('property_name', 'N/A')}")
        print(f"    Rent due: {due_date.strftime('%B %d, %Y')}  {amount}")
        print()

        if not preview:
            html = build_reminder_email(tenant, due_date)
            emails_to_send.append({
                "to_email"    : tenant["email"],
                "subject"     : f"Rent Reminder — Due {due_date.strftime('%B %d')}",
                "html_body"   : html,
                "email_type"  : "rent_reminder",
                "tenant_id"   : tenant["id"],
                "property_id" : tenant.get("property_id"),
            })

    if preview:
        print(f"[PREVIEW MODE] Would send {len(due_tenants)} reminder email(s).")
        return

    # Send all reminder emails
    print("Sending reminder emails...")
    for email_data in emails_to_send:
        send_email(**email_data)

    # Also send a summary to the owner
    _send_owner_summary(due_tenants)

    print(f"\n✅ Done! Sent {len(emails_to_send)} rent reminder(s).")


def _send_owner_summary(due_tenants):
    """Send Katie a summary of who received rent reminders today."""
    rows = "".join(
        f"<tr>"
        f"<td style='padding:8px;border-bottom:1px solid #eee;'>{t['tenant']['name']}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee;'>{t['tenant'].get('property_name','')}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee;'>${t['tenant']['rent']:,.0f}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #eee;'>{t['due_date'].strftime('%b %d')}</td>"
        f"</tr>"
        for t in due_tenants
    )

    html = build_email_html(
        title           = "Rent Reminders Sent",
        greeting        = "Hi Katie,",
        body_paragraphs = [
            f"Rent reminder emails were automatically sent to <b>{len(due_tenants)} tenant(s)</b> today.",
            f"""<table style="width:100%;border-collapse:collapse;font-size:13px;">
              <tr style="background:#f5f5f5;">
                <th style="padding:8px;text-align:left;">Tenant</th>
                <th style="padding:8px;text-align:left;">Property</th>
                <th style="padding:8px;text-align:left;">Amount</th>
                <th style="padding:8px;text-align:left;">Due Date</th>
              </tr>
              {rows}
            </table>""",
        ]
    )

    send_email(
        to_email    = OWNER_EMAIL,
        subject     = f"📧 {len(due_tenants)} Rent Reminder(s) Sent Today",
        html_body   = html,
        email_type  = "owner_summary",
    )


# ============================================================
# Run directly
# ============================================================
if __name__ == "__main__":
    preview_mode = "--preview" in sys.argv
    send_rent_reminders(preview=preview_mode)
