# ============================================================
# config.py — LK Property Group Automation Settings
# ============================================================
# Edit this file with YOUR information before running any scripts.
# ============================================================

# ----------------------------------------------------------
# YOUR GMAIL SETTINGS
# ----------------------------------------------------------
# Step 1: Enable 2-Factor Authentication on your Google account
# Step 2: Go to myaccount.google.com > Security > App Passwords
# Step 3: Create an App Password for "Mail" and paste it below

GMAIL_ADDRESS = "admin@lkpropertygroup.com"   # Your Gmail address
GMAIL_APP_PASSWORD = "iarg jfwx fmrd edhz"    # Paste your 16-char App Password here

# Who gets all alert emails (you / your manager)
OWNER_EMAIL = "admin@lkpropertygroup.com"

# ----------------------------------------------------------
# AUTOMATION SETTINGS
# ----------------------------------------------------------

# How many days before rent is due to send the reminder email
RENT_REMINDER_DAYS_BEFORE = 5

# How many days before lease expires to send a renewal alert
LEASE_RENEWAL_ALERT_DAYS = 90

# How many days an open maintenance task can sit before a follow-up is sent
MAINTENANCE_FOLLOWUP_DAYS = 3

# ----------------------------------------------------------
# DATABASE FILE PATH
# ----------------------------------------------------------
# This is where your property data will be stored locally.
# You can change this path if you want it somewhere else.

DATABASE_PATH = "lk_properties.db"

# ----------------------------------------------------------
# GOOGLE SHEETS SYNC (optional)
# ----------------------------------------------------------
# To sync data to Google Sheets, follow the guide in README.txt
# then paste your Spreadsheet ID here.

GOOGLE_SHEET_ID = ""          # e.g. "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
GOOGLE_CREDENTIALS_FILE = "google_credentials.json"   # Downloaded from Google Cloud

# ----------------------------------------------------------
# COMPANY INFO (used in email templates)
# ----------------------------------------------------------

COMPANY_NAME = "LK Property Group"
COMPANY_PHONE = ""     # e.g. "(555) 123-4567"
COMPANY_WEBSITE = ""   # e.g. "www.lkpropertygroup.com"
