# ============================================================
# run_automations.py — Master Automation Runner
# ============================================================
# This is the ONE script to run every day. It runs all automations
# in sequence: rent reminders, lease alerts, maintenance follow-ups,
# and Google Sheets sync.
#
# Set this up to run automatically every day using:
#   Mac/Linux: cron job (see instructions below)
#   Windows:   Task Scheduler (see instructions below)
#
# Usage:
#   python run_automations.py              — run all automations
#   python run_automations.py --preview    — show what would happen (no emails sent)
#   python run_automations.py --rent       — only run rent reminders
#   python run_automations.py --leases     — only run lease alerts
#   python run_automations.py --maintenance — only run maintenance follow-ups
#   python run_automations.py --sheets     — only sync to Google Sheets
# ============================================================

import sys
import os
from datetime import datetime

# Make sure we're running from the right folder
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def print_header(title):
    print("\n" + "=" * 55)
    print(f"  {title}")
    print(f"  {datetime.now().strftime('%A, %B %d %Y — %I:%M %p')}")
    print("=" * 55)


def run_all(preview=False):
    """Run every automation in sequence."""
    print_header("LK Property Group — Daily Automations")

    errors = []

    # --- 1. Rent Reminders ---
    try:
        from rent_reminders import send_rent_reminders
        send_rent_reminders(preview=preview)
    except Exception as e:
        print(f"\n❌ Rent reminders failed: {e}")
        errors.append(f"Rent reminders: {e}")

    # --- 2. Lease Expiration Alerts ---
    try:
        from lease_alerts import send_lease_alerts
        send_lease_alerts(preview=preview)
    except Exception as e:
        print(f"\n❌ Lease alerts failed: {e}")
        errors.append(f"Lease alerts: {e}")

    # --- 3. Maintenance Follow-Ups ---
    try:
        from maintenance_followup import send_maintenance_followups
        send_maintenance_followups(preview=preview)
    except Exception as e:
        print(f"\n❌ Maintenance follow-ups failed: {e}")
        errors.append(f"Maintenance follow-ups: {e}")

    # --- 4. Google Sheets Sync ---
    from config import GOOGLE_SHEET_ID
    if GOOGLE_SHEET_ID:
        try:
            from sheets_sync import sync_all
            sync_all()
        except Exception as e:
            print(f"\n❌ Google Sheets sync failed: {e}")
            errors.append(f"Sheets sync: {e}")
    else:
        print("\n⏭  Google Sheets sync skipped (GOOGLE_SHEET_ID not set in config.py)")

    # --- Summary ---
    print("\n" + "=" * 55)
    if errors:
        print(f"  ⚠️  Completed with {len(errors)} error(s):")
        for err in errors:
            print(f"     • {err}")
    else:
        print("  ✅ All automations completed successfully!")
    print("=" * 55 + "\n")


# ============================================================
# Command-line routing
# ============================================================
if __name__ == "__main__":
    args = sys.argv[1:]
    preview = "--preview" in args

    if "--rent" in args:
        from rent_reminders import send_rent_reminders
        send_rent_reminders(preview=preview)

    elif "--leases" in args:
        from lease_alerts import send_lease_alerts
        send_lease_alerts(preview=preview)

    elif "--maintenance" in args:
        from maintenance_followup import send_maintenance_followups
        send_maintenance_followups(preview=preview)

    elif "--sheets" in args:
        from sheets_sync import sync_all
        sync_all()

    else:
        run_all(preview=preview)
