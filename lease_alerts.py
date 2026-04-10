# ============================================================
# lease_alerts.py — Lease Renewal & Expiration Alerts
# ============================================================
# Sends YOU (the owner) an alert when a lease is expiring soon.
# Also sends the tenant a heads-up so they can plan ahead.
#
# Sends alerts at: 90 days, 60 days, and 30 days before expiry.
#
# Usage:
#   python lease_alerts.py           — check and send today's alerts
#   python lease_alerts.py --preview — show upcoming expirations without emailing
# ============================================================

import sys
import sqlite3
from datetime import date, timedelta
from config import (DATABASE_PATH, LEASE_RENEWAL_ALERT_DAYS,
                    OWNER_EMAIL, COMPANY_NAME)
from gmail_sender import send_email, build_email_html
from database import get_active_tenants, get_connection


# Alert checkpoints (days before lease ends)
ALERT_DAYS = [90, 60, 30]


def get_expiring_leases():
    """
    Return tenants whose leases are expiring at one of the alert checkpoints
    (90, 60, or 30 days from today) AND who haven't been alerted at that checkpoint yet.
    """
    today = date.today()
    expiring = []
    conn = get_connection()
    tenants = get_active_tenants()

    for tenant in tenants:
        if not tenant["lease_end"]:
            continue

        try:
            lease_end = date.fromisoformat(tenant["lease_end"])
        except ValueError:
            continue

        days_until_end = (lease_end - today).days

        # Check if this is one of our alert checkpoints
        for checkpoint in ALERT_DAYS:
            if days_until_end != checkpoint:
                continue

            # Check if we already sent an alert at this checkpoint
            already_sent = conn.execute("""
                SELECT id FROM email_log
                WHERE type = 'lease_alert'
                  AND tenant_id = ?
                  AND subject LIKE ?
            """, (tenant["id"], f"%{checkpoint} day%")).fetchone()

            if already_sent:
                print(f"  ⏭  Skipping {tenant['name']} ({checkpoint}-day alert already sent)")
                continue

            expiring.append({
                "tenant":    dict(tenant),
                "lease_end": lease_end,
                "days_left": days_until_end,
                "checkpoint": checkpoint,
            })

    conn.close()
    return expiring


def get_all_upcoming_expirations(within_days=120):
    """
    Return all tenants with leases expiring within the next N days.
    Used for the preview report and owner summary.
    """
    today = date.today()
    upcoming = []
    tenants = get_active_tenants()

    for tenant in tenants:
        if not tenant["lease_end"]:
            continue
        try:
            lease_end = date.fromisoformat(tenant["lease_end"])
        except ValueError:
            continue

        days_left = (lease_end - today).days
        if 0 <= days_left <= within_days:
            upcoming.append({
                "tenant":    dict(tenant),
                "lease_end": lease_end,
                "days_left": days_left,
            })

    return sorted(upcoming, key=lambda x: x["days_left"])


def build_tenant_alert_email(tenant, lease_end, days_left):
    """Build the tenant-facing lease expiration email."""
    name      = tenant["name"].split()[0]
    prop_name = tenant.get("property_name", "your unit")
    end_str   = lease_end.strftime("%B %d, %Y")

    if days_left <= 30:
        urgency_note = "⚠️ Please respond as soon as possible so we can make the necessary arrangements."
    else:
        urgency_note = "No action is required right now, but we wanted to give you plenty of notice to plan ahead."

    return build_email_html(
        title = "Lease Expiration Notice",
        greeting = f"Hi {name},",
        body_paragraphs = [
            f"We wanted to let you know that your lease for <b>{prop_name}</b> "
            f"is set to expire on <b>{end_str}</b> — that's <b>{days_left} days</b> from today.",
            f"If you'd like to renew your lease, please contact us at your earliest convenience "
            f"so we can discuss terms and get everything set up.",
            urgency_note,
            "Thank you for being a valued tenant. We look forward to hearing from you!",
        ]
    )


def build_owner_alert_email(expiring_list):
    """Build the owner-facing lease expiration summary email."""
    rows = ""
    for item in expiring_list:
        t         = item["tenant"]
        days_left = item["days_left"]
        end_str   = item["lease_end"].strftime("%b %d, %Y")

        if days_left <= 30:
            badge = f'<span style="background:#FAECE7;color:#712B13;padding:2px 8px;border-radius:4px;font-size:12px;">⚠️ {days_left} days</span>'
        elif days_left <= 60:
            badge = f'<span style="background:#FAEEDA;color:#633806;padding:2px 8px;border-radius:4px;font-size:12px;">🟠 {days_left} days</span>'
        else:
            badge = f'<span style="background:#E6F1FB;color:#0C447C;padding:2px 8px;border-radius:4px;font-size:12px;">🔵 {days_left} days</span>'

        rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">{t['name']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{t.get('property_name','')}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{end_str}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{badge}</td>
        </tr>"""

    return build_email_html(
        title = "Lease Expiration Alert",
        greeting = "Hi Katie,",
        body_paragraphs = [
            f"The following <b>{len(expiring_list)} lease(s)</b> are expiring soon and need your attention:",
            f"""<table style="width:100%;border-collapse:collapse;font-size:13px;">
              <tr style="background:#f5f5f5;">
                <th style="padding:8px;text-align:left;">Tenant</th>
                <th style="padding:8px;text-align:left;">Property</th>
                <th style="padding:8px;text-align:left;">Lease End</th>
                <th style="padding:8px;text-align:left;">Time Left</th>
              </tr>
              {rows}
            </table>""",
            "Please follow up with each tenant to discuss renewal or move-out plans.",
        ]
    )


def send_lease_alerts(preview=False):
    """
    Main function: check for expiring leases and send alerts.
    """
    print(f"\n📋 Lease Expiration Alerts — {date.today().strftime('%B %d, %Y')}")
    print("-" * 50)

    if preview:
        # Show all upcoming expirations within 120 days
        upcoming = get_all_upcoming_expirations(within_days=120)
        if not upcoming:
            print("✅ No leases expiring in the next 120 days.")
            return
        print(f"Leases expiring in the next 120 days:\n")
        for item in upcoming:
            t = item["tenant"]
            print(f"  • {t['name']}")
            print(f"    Property  : {t.get('property_name', 'N/A')}")
            print(f"    Lease end : {item['lease_end'].strftime('%B %d, %Y')}")
            print(f"    Days left : {item['days_left']}")
            print()
        print("[PREVIEW MODE] No emails sent.")
        return

    # Find leases hitting an alert checkpoint today
    expiring = get_expiring_leases()

    if not expiring:
        print("✅ No lease alerts to send today.")
        return

    print(f"Found {len(expiring)} lease alert(s) to send:\n")

    for item in expiring:
        tenant    = item["tenant"]
        lease_end = item["lease_end"]
        days_left = item["days_left"]
        checkpoint = item["checkpoint"]

        print(f"  • {tenant['name']} — {days_left} days until lease ends")
        print(f"    Property  : {tenant.get('property_name', 'N/A')}")
        print(f"    Lease end : {lease_end.strftime('%B %d, %Y')}")

        # Email the tenant (if they have an email)
        if tenant["email"]:
            html = build_tenant_alert_email(tenant, lease_end, days_left)
            send_email(
                to_email    = tenant["email"],
                subject     = f"Your Lease Expires in {checkpoint} Days — {lease_end.strftime('%B %d, %Y')}",
                html_body   = html,
                email_type  = f"lease_alert_{checkpoint}_days",
                tenant_id   = tenant["id"],
                property_id = tenant.get("property_id"),
            )
        print()

    # Email owner with full summary
    if expiring:
        html = build_owner_alert_email(expiring)
        send_email(
            to_email  = OWNER_EMAIL,
            subject   = f"🏠 {len(expiring)} Lease(s) Expiring Soon — Action Required",
            html_body = html,
            email_type = "lease_alert_owner",
        )

    print(f"✅ Done! Sent {len(expiring)} lease alert(s).")


# ============================================================
# Run directly
# ============================================================
if __name__ == "__main__":
    preview_mode = "--preview" in sys.argv
    send_lease_alerts(preview=preview_mode)
