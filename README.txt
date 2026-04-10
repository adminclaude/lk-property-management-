============================================================
LK PROPERTY GROUP — AUTOMATION SYSTEM
Setup Guide for Katie
============================================================

WHAT THIS DOES
--------------
These Python scripts automate the most time-consuming parts
of managing your properties:

  ✅ Sends rent reminder emails to tenants automatically
  ✅ Alerts you (and tenants) when leases are expiring soon
  ✅ Follows up on overdue maintenance requests
  ✅ Sends move-in and move-out checklists with one command
  ✅ Syncs your data to Google Sheets (optional)


============================================================
STEP 1 — INSTALL PYTHON
============================================================
If you don't have Python installed:
  → Go to python.org/downloads
  → Download Python 3.10 or newer
  → Run the installer (check "Add to PATH" on Windows)

Verify it's installed by opening Terminal (Mac) or
Command Prompt (Windows) and typing:
  python --version


============================================================
STEP 2 — INSTALL REQUIRED LIBRARIES
============================================================
Open Terminal / Command Prompt, navigate to this folder,
and run:

  pip install gspread google-auth --break-system-packages

That's the only external library needed for Google Sheets.
Everything else uses Python's built-in libraries.


============================================================
STEP 3 — SET UP GMAIL APP PASSWORD
============================================================
This lets the scripts send emails from your Gmail account
without sharing your real password.

  1. Go to: myaccount.google.com
  2. Click "Security" in the left menu
  3. Under "How you sign in", click "2-Step Verification"
     (turn it on if it's not already)
  4. At the bottom, click "App passwords"
  5. Choose "Mail" as the app → Click "Generate"
  6. Copy the 16-character password shown

Now open config.py in a text editor and fill in:
  GMAIL_ADDRESS    = "admin@lkpropertygroup.com"
  GMAIL_APP_PASSWORD = "paste your 16 chars here"

Test it works by running:
  python gmail_sender.py
  (You should receive a test email at your Gmail address)


============================================================
STEP 4 — SET UP THE DATABASE
============================================================
Run this once to create your local database:

  python database.py

To add some test data to practice with:
  python database.py --demo

Then add YOUR real properties and tenants:
  Open database.py, scroll to the bottom, and use the
  add_property() and add_tenant() functions as shown.

OR use the HTML property management system you already have
and manually add matching records to the database.


============================================================
STEP 5 — TEST EACH AUTOMATION
============================================================
Use --preview to see what would happen without sending emails:

  python rent_reminders.py --preview
  python lease_alerts.py --preview
  python maintenance_followup.py --preview

When you're ready to actually send:
  python run_automations.py


============================================================
STEP 6 — SEND MOVE-IN / MOVE-OUT CHECKLISTS
============================================================
First, list your tenants to find their IDs:
  python checklist_emailer.py --list

Then send the checklist:
  python checklist_emailer.py --movein  <tenant_id>
  python checklist_emailer.py --moveout <tenant_id>

For Airbnb turnovers:
  python checklist_emailer.py --airbnb cleaner@email.com "Property Name" 2026-04-15


============================================================
STEP 7 — GOOGLE SHEETS SYNC (Optional)
============================================================
  1. Go to console.cloud.google.com
  2. Create a new project (e.g. "LK Property Automations")
  3. Search for "Google Sheets API" → Enable it
  4. Go to "APIs & Services" → "Credentials"
  5. Click "Create Credentials" → "Service Account"
  6. Give it a name → Continue → Done
  7. Click the service account → "Keys" tab → "Add Key" → JSON
  8. Save the downloaded file as: google_credentials.json
     (put it in the same folder as these scripts)
  9. Create a new Google Sheet at sheets.google.com
  10. Share it with the service account email (it looks like:
      yourproject@yourproject.iam.gserviceaccount.com)
  11. Copy the Spreadsheet ID from the URL:
      https://docs.google.com/spreadsheets/d/THIS_PART_HERE/edit
  12. Paste it into config.py as GOOGLE_SHEET_ID

Test the connection:
  python sheets_sync.py --check

Sync all data:
  python sheets_sync.py


============================================================
STEP 8 — SCHEDULE DAILY AUTOMATIC RUNS
============================================================

--- MAC / LINUX (using cron) ---
Open Terminal and type:  crontab -e

Add this line to run every day at 8:00 AM:
  0 8 * * * cd /path/to/lk_property_automations && python run_automations.py >> automation_log.txt 2>&1

Replace /path/to/lk_property_automations with your folder path.
Save and close the editor.

--- WINDOWS (using Task Scheduler) ---
  1. Open "Task Scheduler" from the Start menu
  2. Click "Create Basic Task"
  3. Name: "LK Property Automations"
  4. Trigger: Daily at 8:00 AM
  5. Action: "Start a program"
  6. Program: python
  7. Arguments: run_automations.py
  8. Start in: C:\path\to\lk_property_automations
  9. Click Finish


============================================================
FILE OVERVIEW
============================================================
  config.py              ← YOUR SETTINGS (edit this first!)
  database.py            ← Database setup and data entry
  gmail_sender.py        ← Email sending engine
  rent_reminders.py      ← Monthly rent reminder emails
  lease_alerts.py        ← Lease expiration alerts (90/60/30 days)
  maintenance_followup.py ← Follow-ups on open maintenance tasks
  checklist_emailer.py   ← Move-in / move-out checklist emails
  sheets_sync.py         ← Google Sheets sync
  run_automations.py     ← Run everything at once (daily script)
  lk_properties.db       ← Your data (created automatically)


============================================================
NEED HELP?
============================================================
Each script has detailed instructions at the top of the file.
Open any .py file in a text editor (Notepad, TextEdit, or VS Code)
to read the comments and customize it for your needs.

============================================================
