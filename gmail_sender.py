# ============================================================
# gmail_sender.py — Send Emails via Gmail
# ============================================================
# This module handles all email sending for the automations.
# It uses Gmail's secure App Password — no OAuth needed.
#
# SETUP (one-time):
#   1. Go to myaccount.google.com
#   2. Security → 2-Step Verification (turn it on)
#   3. Security → App Passwords → "Mail" → Generate
#   4. Copy the 16-character password into config.py
# ============================================================

import smtplib
import sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, COMPANY_NAME, COMPANY_PHONE, DATABASE_PATH


def send_email(to_email, subject, html_body, email_type="general",
               tenant_id=None, property_id=None):
    """
    Send a single HTML email via Gmail.

    Parameters:
        to_email    : recipient email address (str)
        subject     : email subject line (str)
        html_body   : full HTML content of the email (str)
        email_type  : label for logging ('rent_reminder', 'lease_alert', etc.)
        tenant_id   : optional, for the log
        property_id : optional, for the log

    Returns True if sent successfully, False if it failed.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = f"{COMPANY_NAME} <{GMAIL_ADDRESS}>"
        msg["To"]      = to_email
        msg["Subject"] = subject

        # Attach HTML version (utf-8 to support special characters)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Connect to Gmail's SMTP server and send
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        print(f"  ✅ Email sent to {to_email}: {subject}")
        _log_email(to_email, subject, email_type, tenant_id, property_id, "sent")
        return True

    except Exception as e:
        print(f"  ❌ Failed to send to {to_email}: {e}")
        _log_email(to_email, subject, email_type, tenant_id, property_id, "failed")
        return False


def send_bulk_emails(email_list):
    """
    Send multiple emails from a list of dicts.

    Each dict should have: to_email, subject, html_body,
    and optionally: email_type, tenant_id, property_id

    Example:
        send_bulk_emails([
            {"to_email": "tenant@email.com", "subject": "Rent due soon",
             "html_body": "<p>Your rent is due in 5 days.</p>"}
        ])
    """
    success_count = 0
    for item in email_list:
        result = send_email(
            to_email    = item["to_email"],
            subject     = item["subject"],
            html_body   = item["html_body"],
            email_type  = item.get("email_type", "general"),
            tenant_id   = item.get("tenant_id"),
            property_id = item.get("property_id"),
        )
        if result:
            success_count += 1

    print(f"\n📧 Sent {success_count}/{len(email_list)} emails successfully.")
    return success_count


def _log_email(to_email, subject, email_type, tenant_id, property_id, status):
    """Save a record of every email sent to the database."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.execute("""
            INSERT INTO email_log (to_email, subject, type, tenant_id, property_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (to_email, subject, email_type, tenant_id, property_id, status))
        conn.commit()
        conn.close()
    except Exception:
        pass   # Don't crash just because logging failed


# ============================================================
# Email Template Helper
# ============================================================

def build_email_html(title, greeting, body_paragraphs, action_text=None, action_url=None):
    """
    Build a clean, professional HTML email.

    Parameters:
        title            : bold header line (e.g. "Rent Reminder")
        greeting         : first line (e.g. "Hi Sarah,")
        body_paragraphs  : list of paragraph strings
        action_text      : optional button label (e.g. "Pay Now")
        action_url       : optional button URL

    Returns an HTML string.
    """
    button_html = ""
    if action_text and action_url:
        button_html = f"""
        <tr>
          <td style="padding: 24px 0 8px;">
            <a href="{action_url}"
               style="background-color:#7F77DD;color:#fff;padding:12px 24px;
                      border-radius:6px;text-decoration:none;font-weight:600;
                      font-size:14px;">
              {action_text}
            </a>
          </td>
        </tr>"""

    paragraphs_html = "".join(
        f'<tr><td style="padding:6px 0;font-size:14px;color:#333;line-height:1.6;">{p}</td></tr>'
        for p in body_paragraphs
    )

    footer_parts = [COMPANY_NAME]
    if COMPANY_PHONE:
        footer_parts.append(COMPANY_PHONE)

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;background-color:#f5f5f5;font-family:Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td align="center" style="padding:30px 16px;">
            <table width="560" cellpadding="0" cellspacing="0"
                   style="background:#fff;border-radius:10px;overflow:hidden;
                          border:1px solid #e0e0e0;max-width:560px;width:100%;">

              <!-- Header -->
              <tr>
                <td style="background:#7F77DD;padding:20px 28px;">
                  <p style="margin:0;color:#fff;font-size:13px;opacity:0.85;">{COMPANY_NAME}</p>
                  <h1 style="margin:4px 0 0;color:#fff;font-size:20px;">{title}</h1>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:24px 28px;">
                  <table width="100%">
                    <tr>
                      <td style="font-size:15px;font-weight:600;color:#111;padding-bottom:12px;">
                        {greeting}
                      </td>
                    </tr>
                    {paragraphs_html}
                    {button_html}
                    <tr>
                      <td style="padding-top:28px;border-top:1px solid #eee;margin-top:20px;
                                 font-size:12px;color:#888;line-height:1.6;">
                        {" &middot; ".join(footer_parts)}<br>
                        This is an automated message from your property management system.
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """


# ============================================================
# Quick test — run this file directly to send a test email
# ============================================================
if __name__ == "__main__":
    print("Sending a test email to yourself...")
    html = build_email_html(
        title="Test Email",
        greeting="Hi Katie,",
        body_paragraphs=[
            "This is a test email from your LK Property Group automation system.",
            "If you received this, your Gmail settings in <b>config.py</b> are working correctly! 🎉",
            "You are now ready to run all the property management automations.",
        ]
    )
    send_email(
        to_email   = GMAIL_ADDRESS,
        subject    = "✅ Test — LK Property Group Automations Working",
        html_body  = html,
        email_type = "test"
    )
