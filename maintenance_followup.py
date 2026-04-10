# ============================================================
# maintenance_followup.py — Maintenance Task Follow-Ups
# ============================================================
# Automatically follows up on open maintenance tasks that haven't
# been updated in a while. Sends alerts to you (the owner) and
# optionally to the vendor/assignee.
#
# Usage:
#   python maintenance_followup.py           — send follow-ups
#   python maintenance_followup.py --preview — show open tasks without emailing
# ============================================================

import sys
import sqlite3
from datetime import date, timedelta
from config import DATABASE_PATH, MAINTENANCE_FOLLOWUP_DAYS, OWNER_EMAIL
from gmail_sender import send_email, build_email_html
from database import get_open_tasks, get_connection


def get_stale_tasks():
    """
    Return maintenance tasks that are overdue OR haven't had a follow-up
    sent in the last MAINTENANCE_FOLLOWUP_DAYS days.
    """
    today = date.today()
    stale = []
    tasks = get_open_tasks()
    conn = get_connection()

    for task in tasks:
        if task["category"] != "Maintenance":
            continue
        if task["status"] == "Done":
            continue

        is_overdue = False
        is_stale   = False

        # Check if the task is past its deadline
        if task["deadline"]:
            try:
                deadline = date.fromisoformat(task["deadline"])
                if deadline < today:
                    is_overdue = True
            except ValueError:
                pass

        # Check last follow-up date
        last_followup = task["last_followup_sent"]
        if last_followup:
            try:
                last_date = date.fromisoformat(last_followup)
                days_since = (today - last_date).days
                if days_since >= MAINTENANCE_FOLLOWUP_DAYS:
                    is_stale = True
            except ValueError:
                is_stale = True
        else:
            # Never had a follow-up — check how old the task is
            try:
                created = date.fromisoformat(task["created_at"])
                days_old = (today - created).days
                if days_old >= MAINTENANCE_FOLLOWUP_DAYS:
                    is_stale = True
            except ValueError:
                is_stale = True

        if is_overdue or is_stale:
            stale.append({
                "task":       dict(task),
                "is_overdue": is_overdue,
                "is_stale":   is_stale,
            })

    conn.close()
    return stale


def build_owner_followup_email(stale_tasks):
    """Build the maintenance follow-up summary email for the owner."""
    today = date.today()
    rows = ""
    for item in stale_tasks:
        t = item["task"]
        if item["is_overdue"] and t["deadline"]:
            deadline_label = f'<span style="color:#712B13;font-weight:600;">Overdue ({t["deadline"]})</span>'
        elif t["deadline"]:
            deadline_label = t["deadline"]
        else:
            deadline_label = "No deadline"

        priority_colors = {
            "Urgent": "#FAECE7;color:#712B13",
            "High":   "#FAEEDA;color:#633806",
            "Medium": "#E6F1FB;color:#0C447C",
            "Low":    "#EAF3DE;color:#27500A",
        }
        pri_style = priority_colors.get(t["priority"], "#f5f5f5;color:#333")

        rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">{t['title']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{t.get('property_name','—')}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">
            <span style="background:{pri_style};padding:2px 7px;border-radius:4px;font-size:12px;">
              {t['priority']}
            </span>
          </td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{t.get('assignee','Unassigned')}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{deadline_label}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{t['status']}</td>
        </tr>"""

    overdue_count = sum(1 for x in stale_tasks if x["is_overdue"])
    intro = f"You have <b>{len(stale_tasks)} open maintenance task(s)</b> that need attention"
    if overdue_count:
        intro += f", including <b>{overdue_count} overdue task(s)</b>"
    intro += "."

    return build_email_html(
        title = "Maintenance Follow-Up",
        greeting = "Hi Katie,",
        body_paragraphs = [
            intro,
            f"""<table style="width:100%;border-collapse:collapse;font-size:13px;">
              <tr style="background:#f5f5f5;">
                <th style="padding:8px;text-align:left;">Task</th>
                <th style="padding:8px;text-align:left;">Property</th>
                <th style="padding:8px;text-align:left;">Priority</th>
                <th style="padding:8px;text-align:left;">Assignee</th>
                <th style="padding:8px;text-align:left;">Deadline</th>
                <th style="padding:8px;text-align:left;">Status</th>
              </tr>
              {rows}
            </table>""",
            "Please review and update the status of each task in your property management system.",
        ]
    )


def mark_followup_sent(task_id):
    """Update the task record to record that a follow-up was sent today."""
    conn = get_connection()
    conn.execute(
        "UPDATE tasks SET last_followup_sent = ? WHERE id = ?",
        (date.today().isoformat(), task_id)
    )
    conn.commit()
    conn.close()


def send_maintenance_followups(preview=False):
    """
    Main function: find stale maintenance tasks and send follow-up alert.
    """
    print(f"\n🔧 Maintenance Follow-Ups — {date.today().strftime('%B %d, %Y')}")
    print(f"   Checking for tasks open more than {MAINTENANCE_FOLLOWUP_DAYS} days...")
    print("-" * 50)

    stale_tasks = get_stale_tasks()

    if not stale_tasks:
        print("✅ All maintenance tasks are on track — no follow-ups needed.")
        return

    print(f"Found {len(stale_tasks)} task(s) needing follow-up:\n")
    for item in stale_tasks:
        t = item["task"]
        status_label = "⚠️ OVERDUE" if item["is_overdue"] else "⏰ Stale"
        print(f"  • [{status_label}] {t['title']}")
        print(f"    Property  : {t.get('property_name', 'N/A')}")
        print(f"    Priority  : {t['priority']}")
        print(f"    Assignee  : {t.get('assignee', 'Unassigned')}")
        print(f"    Status    : {t['status']}")
        print(f"    Deadline  : {t.get('deadline', 'None')}")
        print()

    if preview:
        print(f"[PREVIEW MODE] Would send 1 follow-up summary to {OWNER_EMAIL}.")
        return

    # Send one summary email to the owner covering all stale tasks
    html = build_owner_followup_email(stale_tasks)
    overdue_count = sum(1 for x in stale_tasks if x["is_overdue"])
    subject = f"🔧 {len(stale_tasks)} Maintenance Task(s) Need Follow-Up"
    if overdue_count:
        subject = f"⚠️ {overdue_count} Overdue Maintenance Task(s) — Action Required"

    sent = send_email(
        to_email    = OWNER_EMAIL,
        subject     = subject,
        html_body   = html,
        email_type  = "maintenance_followup",
    )

    # Update follow-up timestamps
    if sent:
        for item in stale_tasks:
            mark_followup_sent(item["task"]["id"])

    print(f"✅ Follow-up summary sent to {OWNER_EMAIL}.")


# ============================================================
# Run directly
# ============================================================
if __name__ == "__main__":
    preview_mode = "--preview" in sys.argv
    send_maintenance_followups(preview=preview_mode)
