from flask import Flask, request, jsonify
import sqlite3, json
from datetime import datetime, date
import webbrowser

try:
    from config import DATABASE_PATH, COMPANY_NAME, GMAIL_ADDRESS
except:
    DATABASE_PATH = "lk_properties.db"
    COMPANY_NAME = "LK Property Group"
    GMAIL_ADDRESS = ""

app = Flask(__name__)

def seed_templates(conn):
    if conn.execute("SELECT COUNT(*) FROM checklist_templates").fetchone()[0] > 0:
        return
    templates = [
        ("Tenant move-in", json.dumps([
            "Verify ID and signed lease", "Collect first month rent and deposit",
            "Complete move-in inspection with tenant", "Document condition with photos",
            "Test all appliances (stove, fridge, dishwasher)", "Check all doors and locks",
            "Test smoke and CO detectors", "Review utility setup with tenant",
            "Provide keys and all access items", "Share emergency contact info",
            "Have tenant sign move-in checklist"
        ])),
        ("Tenant move-out", json.dumps([
            "Send move-out instructions 30 days prior", "Schedule move-out inspection",
            "Conduct move-out inspection with photos", "Compare to move-in condition",
            "Document any damages beyond normal wear", "Collect all keys and access items",
            "Calculate deposit deductions if any", "Send deposit return within 30 days",
            "Change locks", "Schedule cleaning and repairs"
        ])),
        ("Property inspection", json.dumps([
            "Exterior: roof, gutters, siding", "Check windows and doors",
            "Inspect HVAC filter and system", "Test smoke and CO detectors",
            "Check plumbing for leaks", "Inspect electrical outlets",
            "Check all appliances", "Document condition with photos"
        ])),
        ("Lease renewal", json.dumps([
            "Send renewal offer 90 days before expiry", "Confirm new rent amount",
            "Prepare updated lease agreement", "Get signed lease from tenant",
            "Update tenant records in system", "File signed lease copy"
        ]))
    ]
    for name, steps in templates:
        conn.execute("INSERT INTO checklist_templates (name, steps) VALUES (?,?)", (name, steps))
    conn.commit()

def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, address TEXT NOT NULL, unit TEXT, notes TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS tenants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER, full_name TEXT NOT NULL, email TEXT NOT NULL,
        phone TEXT, rent_amount REAL NOT NULL, rent_due_day INTEGER DEFAULT 1,
        lease_start TEXT, lease_end TEXT, is_active INTEGER DEFAULT 1)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS maintenance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER, tenant_id INTEGER, description TEXT NOT NULL,
        status TEXT DEFAULT "open", date_reported TEXT, date_resolved TEXT,
        last_followup_sent TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS email_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        to_email TEXT, subject TEXT, type TEXT,
        tenant_id INTEGER, property_id INTEGER,
        status TEXT, sent_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER, title TEXT NOT NULL, assignee TEXT DEFAULT "Katie",
        priority TEXT DEFAULT "medium", status TEXT DEFAULT "todo",
        deadline TEXT, category TEXT DEFAULT "general", notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS checklist_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, steps TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS checklist_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER, property_id INTEGER, name TEXT NOT NULL,
        notes TEXT, status TEXT DEFAULT "active",
        started_at TEXT DEFAULT CURRENT_TIMESTAMP, completed_at TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS checklist_steps_done (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL, step_index INTEGER NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER, description TEXT NOT NULL, amount REAL DEFAULT 0,
        due_date TEXT, paid_date TEXT, status TEXT DEFAULT "unpaid",
        category TEXT DEFAULT "other", notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    seed_templates(conn)
    conn.close()
    print("✅ Database ready.")

HTML = '''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>LK Property Group</title>

<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0f1117;--surface:#1a1d27;--surface2:#22263a;--accent:#6c63ff;--accent2:#a78bfa;--green:#22c55e;--red:#ef4444;--amber:#f59e0b;--text:#f0f0f8;--muted:#8b8fa8;--border:#2e3350}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex}
a{color:inherit;text-decoration:none;cursor:pointer}
.sidebar{width:220px;background:var(--surface);border-right:1px solid var(--border);padding:24px 0;display:flex;flex-direction:column;position:fixed;height:100vh;z-index:10}
.logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.logo h1{font-family:Georgia,serif;font-size:18px;color:var(--accent2);line-height:1.2}
.logo p{font-size:11px;color:var(--muted);margin-top:2px}
.nav-link{display:flex;align-items:center;gap:10px;padding:10px 20px;font-size:13px;color:var(--muted);transition:.15s;border-left:3px solid transparent;cursor:pointer}
.nav-link:hover,.nav-link.active{color:var(--text);background:var(--surface2);border-left-color:var(--accent)}
.main{margin-left:220px;flex:1;padding:32px}
.page{display:none}.page.active{display:block}
.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px}
.page-title{font-family:Georgia,serif;font-size:28px}
.btn{padding:9px 18px;border-radius:8px;border:none;cursor:pointer;font-family:system-ui,sans-serif;font-size:13px;font-weight:500;transition:.15s}
.btn-primary{background:var(--accent);color:#fff}.btn-primary:hover{background:#5a52e0}
.btn-primary:disabled{opacity:.5;cursor:not-allowed}
.btn-danger{background:transparent;color:var(--red);border:1px solid var(--red)}
.btn-success{background:var(--green);color:#000}
.btn-sm{padding:5px 12px;font-size:12px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:20px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px}
.stat-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.stat-value{font-size:36px;font-family:Georgia,serif;margin-top:8px}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:500}
.badge-green{background:rgba(34,197,94,.15);color:var(--green)}
.badge-red{background:rgba(239,68,68,.15);color:var(--red)}
.badge-amber{background:rgba(245,158,11,.15);color:var(--amber)}
.badge-purple{background:rgba(108,99,255,.15);color:var(--accent2)}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;padding:10px 14px;border-bottom:1px solid var(--border)}
td{padding:12px 14px;font-size:13px;border-bottom:1px solid var(--border)}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--surface2)}
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:100;align-items:center;justify-content:center}
.modal-bg.open{display:flex}
.modal{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:28px;width:500px;max-width:95vw;max-height:90vh;overflow-y:auto}
.modal h2{font-family:Georgia,serif;font-size:22px;margin-bottom:20px}
.form-group{margin-bottom:14px}
.form-group label{display:block;font-size:12px;color:var(--muted);margin-bottom:5px}
.form-group input,.form-group select,.form-group textarea{width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:9px 12px;color:var(--text);font-family:system-ui,sans-serif;font-size:13px;outline:none}
.form-group input:focus,.form-group select:focus,.form-group textarea:focus{border-color:var(--accent)}
.form-group select option{background:var(--surface2)}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.modal-footer{display:flex;gap:10px;justify-content:flex-end;margin-top:16px}
.btn-ghost{background:var(--surface2);color:var(--text)}
.ai-tab-btn{background:var(--surface2);color:var(--muted);border:1px solid var(--border);margin-bottom:2px}
.ai-tab-btn.active,.ai-tab-btn:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
.toast{position:fixed;bottom:24px;right:24px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 20px;font-size:13px;z-index:999;transform:translateY(100px);opacity:0;transition:.3s;pointer-events:none}
.toast.show{transform:translateY(0);opacity:1}
.empty{color:var(--muted);text-align:center;padding:40px;font-size:14px}
.spinner{display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite;margin-right:6px;vertical-align:middle}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<aside class="sidebar">
  <div class="logo"><h1>LK Property</h1><p>Management System</p></div>
  <a class="nav-link active" onclick="showPage('dashboard', this)"><span>📊</span> Dashboard</a>
  <a class="nav-link" onclick="showPage('properties', this)"><span>🏠</span> Properties</a>
  <a class="nav-link" onclick="showPage('tenants', this)"><span>👥</span> Tenants</a>
  <a class="nav-link" onclick="showPage('maintenance', this)"><span>🔧</span> Maintenance</a>
  <a class="nav-link" onclick="showPage('tasks', this)"><span>✅</span> Tasks</a>
  <a class="nav-link" onclick="showPage('checklists', this)"><span>📋</span> Checklists</a>
  <a class="nav-link" onclick="showPage('bills', this)"><span>💰</span> Bills</a>
  <a class="nav-link" onclick="showPage('ai', this)"><span>✨</span> AI Generate</a>
</aside>

<main class="main">

<!-- DASHBOARD -->
<div id="page-dashboard" class="page active">
  <div class="page-header">
    <h1 class="page-title">Dashboard</h1>
  </div>
  <div class="stats">
    <div class="stat" style="border-top:3px solid var(--accent)"><div class="stat-label">Properties</div><div class="stat-value" id="stat-props">—</div></div>
    <div class="stat" style="border-top:3px solid var(--green)"><div class="stat-label">Active Tenants</div><div class="stat-value" id="stat-tenants">—</div></div>
    <div class="stat" style="border-top:3px solid var(--amber)"><div class="stat-label">Open Maintenance</div><div class="stat-value" id="stat-maint">—</div></div>
    <div class="stat" style="border-top:3px solid var(--accent2)"><div class="stat-label">Emails Sent</div><div class="stat-value" id="stat-emails">—</div></div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
    <div class="card"><h3 style="font-size:14px;margin-bottom:16px;color:var(--muted)">⚠️ Leases Expiring Soon</h3><div id="dash-leases"><div class="empty">Loading...</div></div></div>
    <div class="card"><h3 style="font-size:14px;margin-bottom:16px;color:var(--muted)">📧 Recent Emails</h3><div id="dash-emails"><div class="empty">Loading...</div></div></div>
  </div>
</div>

<!-- PROPERTIES -->
<div id="page-properties" class="page">
  <div class="page-header">
    <h1 class="page-title">Properties</h1>
    <button class="btn btn-primary" onclick="openModal('modal-add-property')">+ Add Property</button>
  </div>
  <div class="card"><div id="props-table"><div class="empty">Loading...</div></div></div>
</div>

<!-- TENANTS -->
<div id="page-tenants" class="page">
  <div class="page-header">
    <h1 class="page-title">Tenants</h1>
    <button class="btn btn-primary" onclick="openModal('modal-add-tenant')">+ Add Tenant</button>
  </div>
  <div class="card"><div id="tenants-table"><div class="empty">Loading...</div></div></div>
</div>

<!-- MAINTENANCE -->
<div id="page-maintenance" class="page">
  <div class="page-header">
    <h1 class="page-title">Maintenance</h1>
    <button class="btn btn-primary" onclick="openModal('modal-add-maint')">+ Add Task</button>
  </div>
  <div class="card"><div id="maint-table"><div class="empty">Loading...</div></div></div>
</div>

<!-- TASKS -->
<div id="page-tasks" class="page">
  <div class="page-header"><h1 class="page-title">Tasks</h1><button class="btn btn-primary" onclick="openAddTask()">+ Add Task</button></div>
  <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">
    <select id="tf-status" onchange="loadTasks()" style="background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:7px 12px;color:var(--text);font-size:13px;outline:none">
      <option value="">All Status</option><option value="todo">To Do</option><option value="in-progress">In Progress</option><option value="done">Done</option>
    </select>
    <select id="tf-priority" onchange="loadTasks()" style="background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:7px 12px;color:var(--text);font-size:13px;outline:none">
      <option value="">All Priority</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
    </select>
  </div>
  <div class="card"><div id="tasks-table"><div class="empty">Loading...</div></div></div>
</div>

<!-- CHECKLISTS -->
<div id="page-checklists" class="page">
  <div class="page-header"><h1 class="page-title">Checklists</h1><button class="btn btn-primary" onclick="openModal('modal-start-checklist');loadChecklistSelects()">+ Start Checklist</button></div>
  <div class="card"><div id="checklists-table"><div class="empty">Loading...</div></div></div>
</div>

<!-- BILLS -->
<div id="page-bills" class="page">
  <div class="page-header"><h1 class="page-title">Bills</h1><button class="btn btn-primary" onclick="openAddBill()">+ Add Bill</button></div>
  <div style="display:flex;gap:8px;margin-bottom:16px">
    <select id="bf-status" onchange="loadBills()" style="background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:7px 12px;color:var(--text);font-size:13px;outline:none">
      <option value="">All Bills</option><option value="unpaid">Unpaid</option><option value="paid">Paid</option>
    </select>
  </div>
  <div class="card"><div id="bills-table"><div class="empty">Loading...</div></div></div>
</div>

<!-- AI GENERATE -->
<div id="page-ai" class="page">
  <div class="page-header"><h1 class="page-title">AI Generate</h1></div>
  <p style="color:var(--muted);font-size:13px;margin-bottom:20px">Fill out a form and generate a ready-to-use document powered by AI.</p>
  <div style="display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap">
    <button class="btn ai-tab-btn active" onclick="switchAiTab('lease-draft',this)">📄 Lease draft</button>
    <button class="btn ai-tab-btn" onclick="switchAiTab('deposit-return',this)">💵 Deposit return</button>
    <button class="btn ai-tab-btn" onclick="switchAiTab('moveout-notice',this)">📦 Move-out notice</button>
    <button class="btn ai-tab-btn" onclick="switchAiTab('maint-notice',this)">🔧 Maintenance notice</button>
    <button class="btn ai-tab-btn" onclick="switchAiTab('welcome',this)">🏠 Tenant welcome</button>
  </div>
  <div id="ai-lease-draft" class="ai-form card">
    <h3 style="font-size:16px;margin-bottom:16px">Lease Draft</h3>
    <div class="form-row"><div class="form-group"><label>Property</label><select id="ai-ld-prop"><option value="">Select...</option></select></div><div class="form-group"><label>Tenant Name</label><input id="ai-ld-tenant" placeholder="Full name"></div></div>
    <div class="form-row"><div class="form-group"><label>Lease Start</label><input id="ai-ld-start" type="date"></div><div class="form-group"><label>Lease End</label><input id="ai-ld-end" type="date"></div></div>
    <div class="form-row"><div class="form-group"><label>Monthly Rent ($)</label><input id="ai-ld-rent" type="number" placeholder="e.g. 1500"></div><div class="form-group"><label>Security Deposit ($)</label><input id="ai-ld-dep" type="number" placeholder="e.g. 1500"></div></div>
    <div class="form-row"><div class="form-group"><label>State</label><input id="ai-ld-state" placeholder="e.g. GA"></div><div class="form-group"><label>Pets Allowed?</label><select id="ai-ld-pets"><option value="No">No</option><option value="Yes">Yes</option></select></div></div>
    <div class="form-group"><label>Special Terms</label><textarea id="ai-ld-terms" rows="2" placeholder="Parking, utilities, early termination, etc."></textarea></div>
    <button class="btn btn-primary" onclick="generateAi('lease-draft')">Generate lease draft</button>
  </div>
  <div id="ai-deposit-return" class="ai-form card" style="display:none">
    <h3 style="font-size:16px;margin-bottom:16px">Deposit Return Letter</h3>
    <div class="form-row"><div class="form-group"><label>Property</label><select id="ai-dr-prop"><option value="">Select...</option></select></div><div class="form-group"><label>Tenant Name</label><input id="ai-dr-tenant" placeholder="Full name"></div></div>
    <div class="form-row"><div class="form-group"><label>Deposit Paid ($)</label><input id="ai-dr-deposit" type="number" placeholder="e.g. 1500"></div><div class="form-group"><label>Deductions ($)</label><input id="ai-dr-deduct" type="number" placeholder="0 if none"></div></div>
    <div class="form-group"><label>Deduction Reasons</label><textarea id="ai-dr-reasons" rows="2" placeholder="e.g. carpet cleaning $200, hole in wall $150"></textarea></div>
    <button class="btn btn-primary" onclick="generateAi('deposit-return')">Generate letter</button>
  </div>
  <div id="ai-moveout-notice" class="ai-form card" style="display:none">
    <h3 style="font-size:16px;margin-bottom:16px">Move-Out Notice</h3>
    <div class="form-row"><div class="form-group"><label>Property</label><select id="ai-mo-prop"><option value="">Select...</option></select></div><div class="form-group"><label>Tenant Name</label><input id="ai-mo-tenant" placeholder="Full name"></div></div>
    <div class="form-row"><div class="form-group"><label>Move-Out Date</label><input id="ai-mo-date" type="date"></div><div class="form-group"><label>Deposit Amount ($)</label><input id="ai-mo-deposit" type="number" placeholder="e.g. 1500"></div></div>
    <button class="btn btn-primary" onclick="generateAi('moveout-notice')">Generate notice</button>
  </div>
  <div id="ai-maint-notice" class="ai-form card" style="display:none">
    <h3 style="font-size:16px;margin-bottom:16px">Maintenance Notice</h3>
    <div class="form-row"><div class="form-group"><label>Property</label><select id="ai-mn-prop"><option value="">Select...</option></select></div><div class="form-group"><label>Tenant Name</label><input id="ai-mn-tenant" placeholder="Full name"></div></div>
    <div class="form-row"><div class="form-group"><label>Work Date</label><input id="ai-mn-date" type="date"></div><div class="form-group"><label>Work Time</label><input id="ai-mn-time" placeholder="e.g. 9 AM - 12 PM"></div></div>
    <div class="form-group"><label>Work Description</label><textarea id="ai-mn-desc" rows="2" placeholder="e.g. HVAC inspection and filter replacement"></textarea></div>
    <button class="btn btn-primary" onclick="generateAi('maint-notice')">Generate notice</button>
  </div>
  <div id="ai-welcome" class="ai-form card" style="display:none">
    <h3 style="font-size:16px;margin-bottom:16px">Tenant Welcome Letter</h3>
    <div class="form-row"><div class="form-group"><label>Property</label><select id="ai-wl-prop"><option value="">Select...</option></select></div><div class="form-group"><label>Tenant Name</label><input id="ai-wl-tenant" placeholder="Full name"></div></div>
    <div class="form-row"><div class="form-group"><label>Move-In Date</label><input id="ai-wl-date" type="date"></div><div class="form-group"><label>Monthly Rent ($)</label><input id="ai-wl-rent" type="number" placeholder="e.g. 1500"></div></div>
    <button class="btn btn-primary" onclick="generateAi('welcome')">Generate letter</button>
  </div>
  <div id="ai-output" style="display:none;margin-top:20px"><div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <h3 style="font-size:14px">Generated Document</h3>
      <button class="btn btn-ghost btn-sm" onclick="copyAiOutput()">📋 Copy</button>
    </div>
    <textarea id="ai-output-text" rows="20" style="width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:12px;color:var(--text);font-family:monospace;font-size:12px;resize:vertical;outline:none;line-height:1.6"></textarea>
  </div></div>
</div>

</main>

<!-- MODALS -->
<div id="modal-add-property" class="modal-bg" onclick="if(event.target===this)closeModal('modal-add-property')">
  <div class="modal">
    <h2>Add Property</h2>
    <div class="form-group"><label>Property Name *</label><input id="p-name" placeholder="e.g. Sunset Apartments"></div>
    <div class="form-group"><label>Full Address *</label><input id="p-address" placeholder="e.g. 123 Rizal St, Quezon City"></div>
    <div class="form-row">
      <div class="form-group"><label>Unit Number</label><input id="p-unit" placeholder="e.g. Unit 2A"></div>
      <div class="form-group"><label>Notes</label><input id="p-notes" placeholder="Optional"></div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal('modal-add-property')">Cancel</button>
      <button class="btn btn-primary" id="btn-add-property" onclick="addProperty()">Add Property</button>
    </div>
  </div>
</div>

<div id="modal-add-tenant" class="modal-bg" onclick="if(event.target===this)closeModal('modal-add-tenant')">
  <div class="modal">
    <h2>Add Tenant</h2>
    <div class="form-row">
      <div class="form-group"><label>Full Name *</label><input id="t-name" placeholder="Juan dela Cruz"></div>
      <div class="form-group"><label>Property *</label><select id="t-prop"><option value="">Select property...</option></select></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>Email *</label><input id="t-email" type="email" placeholder="tenant@email.com"></div>
      <div class="form-group"><label>Phone</label><input id="t-phone" placeholder="09XX-XXX-XXXX"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>Monthly Rent (PHP) *</label><input id="t-rent" type="number" placeholder="15000"></div>
      <div class="form-group"><label>Rent Due Day (1-28) *</label><input id="t-due" type="number" min="1" max="28" placeholder="1"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>Lease Start</label><input id="t-start" type="date"></div>
      <div class="form-group"><label>Lease End</label><input id="t-end" type="date"></div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal('modal-add-tenant')">Cancel</button>
      <button class="btn btn-primary" id="btn-add-tenant" onclick="addTenant()">Add Tenant</button>
    </div>
  </div>
</div>

<div id="modal-add-maint" class="modal-bg" onclick="if(event.target===this)closeModal('modal-add-maint')">
  <div class="modal">
    <h2>Add Maintenance Task</h2>
    <div class="form-group"><label>Property *</label><select id="m-prop"><option value="">Select property...</option></select></div>
    <div class="form-group"><label>Issue Description *</label><textarea id="m-desc" rows="3" placeholder="Describe the issue..."></textarea></div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal('modal-add-maint')">Cancel</button>
      <button class="btn btn-primary" id="btn-add-maint" onclick="addMaintenance()">Add Task</button>
    </div>
  </div>
</div>

<!-- ADD/EDIT TASK MODAL -->
<div id="modal-add-task" class="modal-bg" onclick="if(event.target===this)closeTaskModal()">
  <div class="modal">
    <h2 id="task-modal-title">Add Task</h2>
    <input type="hidden" id="tk-id">
    <div class="form-group"><label>Task Title *</label><input id="tk-title" placeholder="What needs to be done?"></div>
    <div class="form-row">
      <div class="form-group"><label>Property</label><select id="tk-prop"><option value="">No property</option></select></div>
      <div class="form-group"><label>Assignee</label><input id="tk-assignee" placeholder="Katie / Micah / Vendor"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>Priority</label><select id="tk-priority"><option value="high">High</option><option value="medium" selected>Medium</option><option value="low">Low</option></select></div>
      <div class="form-group"><label>Status</label><select id="tk-status"><option value="todo">To Do</option><option value="in-progress">In Progress</option><option value="done">Done</option></select></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>Deadline</label><input id="tk-deadline" type="date"></div>
      <div class="form-group"><label>Category</label><select id="tk-category"><option value="general">General</option><option value="maintenance">Maintenance</option><option value="legal">Legal</option><option value="financial">Financial</option><option value="cleaning">Cleaning</option></select></div>
    </div>
    <div class="form-group"><label>Notes</label><textarea id="tk-notes" rows="2" placeholder="Details, next steps, context..."></textarea></div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeTaskModal()">Cancel</button>
      <button class="btn btn-primary" id="btn-save-task" onclick="saveTask()">Add Task</button>
    </div>
  </div>
</div>

<!-- START CHECKLIST MODAL -->
<div id="modal-start-checklist" class="modal-bg" onclick="if(event.target===this)closeModal('modal-start-checklist')">
  <div class="modal">
    <h2>Start a Checklist</h2>
    <div class="form-group"><label>Checklist Name *</label><input id="cl-name" placeholder="e.g. Sonya move-out · May 2026"></div>
    <div class="form-row">
      <div class="form-group"><label>SOP Template *</label><select id="cl-template"><option value="">Select...</option></select></div>
      <div class="form-group"><label>Property</label><select id="cl-prop"><option value="">No property</option></select></div>
    </div>
    <div class="form-group"><label>Notes</label><input id="cl-notes" placeholder="Any context for this checklist run"></div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal('modal-start-checklist')">Cancel</button>
      <button class="btn btn-primary" id="btn-start-checklist" onclick="startChecklist()">Start Checklist</button>
    </div>
  </div>
</div>

<!-- ADD/EDIT BILL MODAL -->
<div id="modal-add-bill" class="modal-bg" onclick="if(event.target===this)closeModal('modal-add-bill')">
  <div class="modal">
    <h2 id="bill-modal-title">Add Bill</h2>
    <input type="hidden" id="bl-id">
    <div class="form-group"><label>Description *</label><input id="bl-desc" placeholder="e.g. Water bill April"></div>
    <div class="form-row">
      <div class="form-group"><label>Property</label><select id="bl-prop"><option value="">No property</option></select></div>
      <div class="form-group"><label>Category</label><select id="bl-category"><option value="mortgage">Mortgage</option><option value="insurance">Insurance</option><option value="repairs">Repairs</option><option value="utilities">Utilities</option><option value="taxes">Taxes</option><option value="other" selected>Other</option></select></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>Amount ($)</label><input id="bl-amount" type="number" placeholder="0.00"></div>
      <div class="form-group"><label>Due Date</label><input id="bl-due" type="date"></div>
    </div>
    <div class="form-group"><label>Notes</label><input id="bl-notes" placeholder="Optional notes"></div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal('modal-add-bill')">Cancel</button>
      <button class="btn btn-primary" id="btn-save-bill" onclick="saveBill()">Add Bill</button>
    </div>
  </div>
</div>

<!-- EDIT PROPERTY MODAL -->
<div id="modal-edit-property" class="modal-bg" onclick="if(event.target===this)closeModal('modal-edit-property')">
  <div class="modal">
    <h2>Edit Property</h2>
    <input type="hidden" id="ep-id">
    <div class="form-group"><label>Property Name *</label><input id="ep-name" placeholder="e.g. Sunset Apartments"></div>
    <div class="form-group"><label>Full Address *</label><input id="ep-address" placeholder="e.g. 123 Main St, Atlanta, GA"></div>
    <div class="form-row">
      <div class="form-group"><label>Unit Number</label><input id="ep-unit" placeholder="e.g. Unit 2A"></div>
      <div class="form-group"><label>Notes</label><input id="ep-notes" placeholder="Optional"></div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal('modal-edit-property')">Cancel</button>
      <button class="btn btn-primary" id="btn-save-property" onclick="saveEditProperty()">Save Changes</button>
    </div>
  </div>
</div>

<!-- EDIT TENANT MODAL -->
<div id="modal-edit-tenant" class="modal-bg" onclick="if(event.target===this)closeModal('modal-edit-tenant')">
  <div class="modal">
    <h2>Edit Tenant</h2>
    <input type="hidden" id="et-id">
    <div class="form-row">
      <div class="form-group"><label>Full Name *</label><input id="et-name"></div>
      <div class="form-group"><label>Property *</label><select id="et-prop"><option value="">Select property...</option></select></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>Email *</label><input id="et-email" type="email"></div>
      <div class="form-group"><label>Phone</label><input id="et-phone"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>Monthly Rent (PHP) *</label><input id="et-rent" type="number"></div>
      <div class="form-group"><label>Rent Due Day (1-28)</label><input id="et-due" type="number" min="1" max="28"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>Lease Start</label><input id="et-start" type="date"></div>
      <div class="form-group"><label>Lease End</label><input id="et-end" type="date"></div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal('modal-edit-tenant')">Cancel</button>
      <button class="btn btn-primary" id="btn-save-tenant" onclick="saveEditTenant()">Save Changes</button>
    </div>
  </div>
</div>

<div id="toast" class="toast"></div>

<script>
// ── helpers ──────────────────────────────────────────────
function showPage(name, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-link').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  if (el) el.classList.add('active');
  if (name === 'dashboard')   loadDashboard();
  if (name === 'properties')  loadProperties();
  if (name === 'tenants')     loadTenants();
  if (name === 'maintenance') loadMaintenance();
  if (name === 'tasks')       loadTasks();
  if (name === 'checklists')  loadChecklists();
  if (name === 'bills')       loadBills();
  if (name === 'ai')          loadAiProps();
}

function openModal(id) {
  document.getElementById(id).classList.add('open');
  if (id === 'modal-add-tenant' || id === 'modal-add-maint') loadPropertySelects();
}
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

function showToast(msg, ok = true) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.borderColor = ok ? 'var(--green)' : 'var(--red)';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3500);
}

function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  btn.disabled = loading;
  btn.innerHTML = loading
    ? '<span class="spinner"></span>Saving...'
    : btn.dataset.label || btn.textContent;
}

async function api(url, data = null) {
  const opts = data !== null
    ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }
    : {};
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error('Server error ' + r.status);
  return r.json();
}

// ── dashboard ─────────────────────────────────────────────
async function loadDashboard() {
  try {
    const d = await api('/api/dashboard');
    document.getElementById('stat-props').textContent   = d.total_properties;
    document.getElementById('stat-tenants').textContent = d.total_tenants;
    document.getElementById('stat-maint').textContent   = d.open_maintenance;
    document.getElementById('stat-emails').textContent  = d.emails_sent;

    const leases = document.getElementById('dash-leases');
    leases.innerHTML = d.expiring_leases.length
      ? '<table><tr><th>Tenant</th><th>Lease End</th></tr>' +
        d.expiring_leases.map(l => `<tr><td>${l.full_name}</td><td><span class="badge badge-amber">${l.lease_end}</span></td></tr>`).join('') +
        '</table>'
      : '<div class="empty">No leases expiring in 90 days</div>';

    const emails = document.getElementById('dash-emails');
    emails.innerHTML = d.recent_emails.length
      ? '<table><tr><th>To</th><th>Subject</th><th>Status</th></tr>' +
        d.recent_emails.map(e => `<tr><td style="color:var(--muted)">${e.to_email}</td><td>${e.subject.substring(0,30)}${e.subject.length>30?'…':''}</td><td><span class="badge ${e.status==='sent'?'badge-green':'badge-red'}">${e.status}</span></td></tr>`).join('') +
        '</table>'
      : '<div class="empty">No emails sent yet</div>';
  } catch(e) {
    showToast('Failed to load dashboard: ' + e.message, false);
  }
}

// ── properties ────────────────────────────────────────────
async function loadProperties() {
  try {
    const d = await api('/api/properties');
    const el = document.getElementById('props-table');
    if (!d.length) {
      el.innerHTML = '<div class="empty">No properties yet. Click "+ Add Property" to get started!</div>';
      return;
    }
    el.innerHTML = '<table><tr><th>Name</th><th>Address</th><th>Unit</th><th>Tenants</th><th>Notes</th><th></th></tr>' +
      d.map(p => `<tr>
        <td><strong>${p.name}</strong></td>
        <td>${p.address}</td>
        <td>${p.unit || '—'}</td>
        <td><span class="badge badge-purple">${p.tenant_count} tenant${p.tenant_count!=1?'s':''}</span></td>
        <td style="color:var(--muted)">${p.notes || '—'}</td>
        <td style="display:flex;gap:6px"><button class="btn btn-ghost btn-sm" onclick="openEditProperty(${p.id})">Edit</button><button class="btn btn-danger btn-sm" onclick="deleteProperty(${p.id})">Remove</button></td>
      </tr>`).join('') + '</table>';
  } catch(e) {
    showToast('Failed to load properties: ' + e.message, false);
  }
}

async function addProperty() {
  const name    = document.getElementById('p-name').value.trim();
  const address = document.getElementById('p-address').value.trim();
  if (!name)    { showToast('Property name is required', false); return; }
  if (!address) { showToast('Address is required', false); return; }

  const btn = document.getElementById('btn-add-property');
  btn.dataset.label = 'Add Property';
  setLoading('btn-add-property', true);

  try {
    const r = await api('/api/properties/add', {
      name, address,
      unit:  document.getElementById('p-unit').value.trim(),
      notes: document.getElementById('p-notes').value.trim()
    });
    if (r.success) {
      // clear fields
      ['p-name','p-address','p-unit','p-notes'].forEach(id => document.getElementById(id).value = '');
      closeModal('modal-add-property');
      showToast('✅ Property added!');
      loadProperties();
    } else {
      showToast('Error: ' + (r.error || 'Could not add property'), false);
    }
  } catch(e) {
    showToast('Server error: ' + e.message, false);
  } finally {
    setLoading('btn-add-property', false);
  }
}

async function deleteProperty(id) {
  if (!confirm('Remove this property? This cannot be undone.')) return;
  try {
    const r = await api('/api/properties/delete/' + id, {});
    if (r.success) { showToast('Property removed'); loadProperties(); }
    else showToast('Error: ' + (r.error || 'Could not remove'), false);
  } catch(e) {
    showToast('Server error: ' + e.message, false);
  }
}

// ── tenants ───────────────────────────────────────────────
async function loadTenants() {
  try {
    const d = await api('/api/tenants');
    const el = document.getElementById('tenants-table');
    if (!d.length) {
      el.innerHTML = '<div class="empty">No tenants yet. Add a property first, then add tenants!</div>';
      return;
    }
    el.innerHTML = '<table><tr><th>Name</th><th>Property</th><th>Email</th><th>Phone</th><th>Rent (PHP)</th><th>Due Day</th><th>Lease End</th><th></th></tr>' +
      d.map(t => `<tr>
        <td><strong>${t.full_name}</strong></td>
        <td style="color:var(--muted)">${t.property_name || '—'}</td>
        <td style="color:var(--muted)">${t.email}</td>
        <td style="color:var(--muted)">${t.phone || '—'}</td>
        <td>${Number(t.rent_amount).toLocaleString('en-PH',{minimumFractionDigits:2})}</td>
        <td>${t.rent_due_day}</td>
        <td>${t.lease_end ? `<span class="badge badge-amber">${t.lease_end}</span>` : '—'}</td>
        <td style="display:flex;gap:6px"><button class="btn btn-ghost btn-sm" onclick="openEditTenant(${t.id})">Edit</button><button class="btn btn-danger btn-sm" onclick="deactivateTenant(${t.id},'${t.full_name.replace(/'/g,"\\'")}')">Move Out</button></td>
      </tr>`).join('') + '</table>';
  } catch(e) {
    showToast('Failed to load tenants: ' + e.message, false);
  }
}

async function addTenant() {
  const name  = document.getElementById('t-name').value.trim();
  const prop  = document.getElementById('t-prop').value;
  const email = document.getElementById('t-email').value.trim();
  const rent  = document.getElementById('t-rent').value;
  const due   = document.getElementById('t-due').value;

  if (!name)  { showToast('Full name is required', false); return; }
  if (!prop)  { showToast('Please select a property', false); return; }
  if (!email) { showToast('Email is required', false); return; }
  if (!rent)  { showToast('Monthly rent is required', false); return; }
  if (!due)   { showToast('Rent due day is required', false); return; }

  const btn = document.getElementById('btn-add-tenant');
  btn.dataset.label = 'Add Tenant';
  setLoading('btn-add-tenant', true);

  try {
    const r = await api('/api/tenants/add', {
      full_name:    name,
      property_id:  parseInt(prop),
      email,
      phone:        document.getElementById('t-phone').value.trim(),
      rent_amount:  parseFloat(rent),
      rent_due_day: parseInt(due),
      lease_start:  document.getElementById('t-start').value,
      lease_end:    document.getElementById('t-end').value
    });
    if (r.success) {
      ['t-name','t-email','t-phone','t-rent','t-due','t-start','t-end'].forEach(id => document.getElementById(id).value = '');
      document.getElementById('t-prop').value = '';
      closeModal('modal-add-tenant');
      showToast('✅ Tenant added!');
      loadTenants();
    } else {
      showToast('Error: ' + (r.error || 'Could not add tenant'), false);
    }
  } catch(e) {
    showToast('Server error: ' + e.message, false);
  } finally {
    setLoading('btn-add-tenant', false);
  }
}

async function deactivateTenant(id, name) {
  if (!confirm(`Mark ${name} as moved out?`)) return;
  try {
    const r = await api('/api/tenants/deactivate/' + id, {});
    if (r.success) { showToast('Tenant marked as moved out'); loadTenants(); }
    else showToast('Error: ' + (r.error || 'Could not deactivate'), false);
  } catch(e) {
    showToast('Server error: ' + e.message, false);
  }
}

// ── maintenance ───────────────────────────────────────────
async function loadMaintenance() {
  try {
    const d = await api('/api/maintenance');
    const el = document.getElementById('maint-table');
    if (!d.length) {
      el.innerHTML = '<div class="empty">No maintenance tasks yet.</div>';
      return;
    }
    el.innerHTML = '<table><tr><th>Property</th><th>Description</th><th>Tenant</th><th>Reported</th><th>Status</th><th></th></tr>' +
      d.map(t => `<tr>
        <td><strong>${t.property_name || t.address || '—'}</strong></td>
        <td>${t.description}</td>
        <td style="color:var(--muted)">${t.tenant_name || '—'}</td>
        <td style="color:var(--muted)">${t.date_reported}</td>
        <td><span class="badge ${t.status==='open'?'badge-red':'badge-green'}">${t.status}</span></td>
        <td>${t.status==='open' ? `<button class="btn btn-success btn-sm" onclick="resolveMaint(${t.id})">Resolve</button>` : ''}</td>
      </tr>`).join('') + '</table>';
  } catch(e) {
    showToast('Failed to load maintenance: ' + e.message, false);
  }
}

async function addMaintenance() {
  const prop = document.getElementById('m-prop').value;
  const desc = document.getElementById('m-desc').value.trim();
  if (!prop) { showToast('Please select a property', false); return; }
  if (!desc) { showToast('Please describe the issue', false); return; }

  const btn = document.getElementById('btn-add-maint');
  btn.dataset.label = 'Add Task';
  setLoading('btn-add-maint', true);

  try {
    const r = await api('/api/maintenance/add', {
      property_id:  parseInt(prop),
      description:  desc
    });
    if (r.success) {
      document.getElementById('m-prop').value = '';
      document.getElementById('m-desc').value = '';
      closeModal('modal-add-maint');
      showToast('✅ Maintenance task added!');
      loadMaintenance();
    } else {
      showToast('Error: ' + (r.error || 'Could not add task'), false);
    }
  } catch(e) {
    showToast('Server error: ' + e.message, false);
  } finally {
    setLoading('btn-add-maint', false);
  }
}

async function resolveMaint(id) {
  if (!confirm('Mark as resolved?')) return;
  try {
    const r = await api('/api/maintenance/resolve/' + id, {});
    if (r.success) { showToast('Task resolved!'); loadMaintenance(); }
    else showToast('Error: ' + (r.error || 'Could not resolve'), false);
  } catch(e) {
    showToast('Server error: ' + e.message, false);
  }
}

// ── edit property ─────────────────────────────────────────
async function openEditProperty(id) {
  try {
    const props = await api('/api/properties');
    const p = props.find(x => x.id === id);
    if (!p) return showToast('Property not found', false);
    document.getElementById('ep-id').value      = p.id;
    document.getElementById('ep-name').value    = p.name;
    document.getElementById('ep-address').value = p.address;
    document.getElementById('ep-unit').value    = p.unit  || '';
    document.getElementById('ep-notes').value   = p.notes || '';
    openModal('modal-edit-property');
  } catch(e) { showToast('Could not load property: ' + e.message, false); }
}

async function saveEditProperty() {
  const id      = document.getElementById('ep-id').value;
  const name    = document.getElementById('ep-name').value.trim();
  const address = document.getElementById('ep-address').value.trim();
  if (!name)    { showToast('Property name is required', false); return; }
  if (!address) { showToast('Address is required', false); return; }
  const btn = document.getElementById('btn-save-property');
  btn.dataset.label = 'Save Changes';
  setLoading('btn-save-property', true);
  try {
    const r = await api('/api/properties/update/' + id, {
      name, address,
      unit:  document.getElementById('ep-unit').value.trim(),
      notes: document.getElementById('ep-notes').value.trim()
    });
    if (r.success) {
      closeModal('modal-edit-property');
      showToast('✅ Property updated!');
      loadProperties();
    } else showToast('Error: ' + (r.error || 'Could not update'), false);
  } catch(e) {
    showToast('Server error: ' + e.message, false);
  } finally { setLoading('btn-save-property', false); }
}

// ── edit tenant ───────────────────────────────────────────
async function openEditTenant(id) {
  try {
    const [tenants, props] = await Promise.all([api('/api/tenants'), api('/api/properties')]);
    const t = tenants.find(x => x.id === id);
    if (!t) return showToast('Tenant not found', false);
    const sel = document.getElementById('et-prop');
    sel.innerHTML = '<option value="">Select property...</option>' +
      props.map(p => `<option value="${p.id}"${p.id == t.property_id ? ' selected' : ''}>${p.name}</option>`).join('');
    document.getElementById('et-id').value    = t.id;
    document.getElementById('et-name').value  = t.full_name;
    document.getElementById('et-email').value = t.email;
    document.getElementById('et-phone').value = t.phone       || '';
    document.getElementById('et-rent').value  = t.rent_amount;
    document.getElementById('et-due').value   = t.rent_due_day;
    document.getElementById('et-start').value = t.lease_start || '';
    document.getElementById('et-end').value   = t.lease_end   || '';
    openModal('modal-edit-tenant');
  } catch(e) { showToast('Could not load tenant: ' + e.message, false); }
}

async function saveEditTenant() {
  const id    = document.getElementById('et-id').value;
  const name  = document.getElementById('et-name').value.trim();
  const prop  = document.getElementById('et-prop').value;
  const email = document.getElementById('et-email').value.trim();
  const rent  = document.getElementById('et-rent').value;
  if (!name)  { showToast('Full name is required', false); return; }
  if (!prop)  { showToast('Please select a property', false); return; }
  if (!email) { showToast('Email is required', false); return; }
  if (!rent)  { showToast('Monthly rent is required', false); return; }
  const btn = document.getElementById('btn-save-tenant');
  btn.dataset.label = 'Save Changes';
  setLoading('btn-save-tenant', true);
  try {
    const r = await api('/api/tenants/update/' + id, {
      full_name:    name,
      property_id:  parseInt(prop),
      email,
      phone:        document.getElementById('et-phone').value.trim(),
      rent_amount:  parseFloat(rent),
      rent_due_day: parseInt(document.getElementById('et-due').value) || 1,
      lease_start:  document.getElementById('et-start').value,
      lease_end:    document.getElementById('et-end').value
    });
    if (r.success) {
      closeModal('modal-edit-tenant');
      showToast('✅ Tenant updated!');
      loadTenants();
    } else showToast('Error: ' + (r.error || 'Could not update'), false);
  } catch(e) {
    showToast('Server error: ' + e.message, false);
  } finally { setLoading('btn-save-tenant', false); }
}

// ── tasks ─────────────────────────────────────────────────
async function openAddTask() {
  document.getElementById('task-modal-title').textContent = 'Add Task';
  document.getElementById('btn-save-task').textContent = 'Add Task';
  document.getElementById('btn-save-task').dataset.label = 'Add Task';
  ['tk-title','tk-assignee','tk-notes'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('tk-id').value = '';
  document.getElementById('tk-assignee').value = 'Katie';
  document.getElementById('tk-priority').value = 'medium';
  document.getElementById('tk-status').value = 'todo';
  document.getElementById('tk-category').value = 'general';
  document.getElementById('tk-deadline').value = '';
  await loadTaskPropSelect();
  openModal('modal-add-task');
}
async function loadTaskPropSelect() {
  const props = await api('/api/properties').catch(() => []);
  const s = document.getElementById('tk-prop');
  if (s) s.innerHTML = '<option value="">No property</option>' + props.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
}
async function loadTasks() {
  try {
    const st = document.getElementById('tf-status')?.value || '';
    const pr = document.getElementById('tf-priority')?.value || '';
    let url = '/api/tasks';
    const p = []; if (st) p.push('status='+st); if (pr) p.push('priority='+pr);
    if (p.length) url += '?' + p.join('&');
    const d = await api(url);
    const el = document.getElementById('tasks-table');
    const pc = {high:'var(--red)',medium:'var(--amber)',low:'var(--muted)'};
    const sc = {todo:'badge-purple','in-progress':'badge-amber',done:'badge-green'};
    const sl = {todo:'To Do','in-progress':'In Progress',done:'Done'};
    if (!d.length) { el.innerHTML = '<div class="empty">No tasks yet. Click "+ Add Task" to get started!</div>'; return; }
    el.innerHTML = '<table><tr><th>Task</th><th>Property</th><th>Assignee</th><th>Priority</th><th>Status</th><th>Deadline</th><th></th></tr>' +
      d.map(t => `<tr>
        <td><strong>${t.title}</strong>${t.notes?`<br><span style="color:var(--muted);font-size:11px">${t.notes}</span>`:''}</td>
        <td style="color:var(--muted)">${t.property_name||'—'}</td>
        <td style="color:var(--muted)">${t.assignee||'—'}</td>
        <td><span style="color:${pc[t.priority]||'var(--muted)'}">●</span> ${t.priority}</td>
        <td><span class="badge ${sc[t.status]||'badge-purple'}">${sl[t.status]||t.status}</span></td>
        <td style="color:var(--muted)">${t.deadline||'—'}</td>
        <td style="display:flex;gap:6px">
          <button class="btn btn-ghost btn-sm" onclick="openEditTask(${t.id})">Edit</button>
          ${t.status!=='done'?`<button class="btn btn-success btn-sm" onclick="completeTask(${t.id})">Done</button>`:''}
          <button class="btn btn-danger btn-sm" onclick="deleteTask(${t.id})">Delete</button>
        </td></tr>`).join('') + '</table>';
  } catch(e) { showToast('Failed to load tasks: ' + e.message, false); }
}
async function openEditTask(id) {
  try {
    const d = await api('/api/tasks/' + id);
    document.getElementById('task-modal-title').textContent = 'Edit Task';
    document.getElementById('btn-save-task').textContent = 'Save Changes';
    document.getElementById('btn-save-task').dataset.label = 'Save Changes';
    document.getElementById('tk-id').value       = d.id;
    document.getElementById('tk-title').value    = d.title;
    document.getElementById('tk-assignee').value = d.assignee||'';
    document.getElementById('tk-notes').value    = d.notes||'';
    document.getElementById('tk-deadline').value = d.deadline||'';
    document.getElementById('tk-priority').value = d.priority||'medium';
    document.getElementById('tk-status').value   = d.status||'todo';
    document.getElementById('tk-category').value = d.category||'general';
    await loadTaskPropSelect();
    if (d.property_id) document.getElementById('tk-prop').value = d.property_id;
    openModal('modal-add-task');
  } catch(e) { showToast('Could not load task: ' + e.message, false); }
}
async function saveTask() {
  const title = document.getElementById('tk-title').value.trim();
  if (!title) { showToast('Task title is required', false); return; }
  const id  = document.getElementById('tk-id').value;
  const url = id ? '/api/tasks/update/' + id : '/api/tasks/add';
  const btn = document.getElementById('btn-save-task');
  btn.dataset.label = btn.textContent;
  setLoading('btn-save-task', true);
  try {
    const r = await api(url, { title, property_id: document.getElementById('tk-prop').value||null,
      assignee: document.getElementById('tk-assignee').value.trim(),
      priority: document.getElementById('tk-priority').value,
      status:   document.getElementById('tk-status').value,
      deadline: document.getElementById('tk-deadline').value,
      category: document.getElementById('tk-category').value,
      notes:    document.getElementById('tk-notes').value.trim() });
    if (r.success) { closeTaskModal(); showToast(id?'✅ Task updated!':'✅ Task added!'); loadTasks(); }
    else showToast('Error: ' + (r.error||'Could not save task'), false);
  } catch(e) { showToast('Server error: ' + e.message, false); }
  finally { setLoading('btn-save-task', false); }
}
function closeTaskModal() { closeModal('modal-add-task'); }
async function completeTask(id) {
  try { const r = await api('/api/tasks/update/'+id,{status:'done'}); if(r.success){showToast('Task marked done!');loadTasks();}else showToast('Error: '+(r.error||''),false); }
  catch(e){showToast('Server error: '+e.message,false);}
}
async function deleteTask(id) {
  if(!confirm('Delete this task?'))return;
  try { const r = await api('/api/tasks/delete/'+id,{}); if(r.success){showToast('Task deleted');loadTasks();}else showToast('Error: '+r.error,false); }
  catch(e){showToast('Server error: '+e.message,false);}
}

// ── checklists ────────────────────────────────────────────
function loadChecklistSelects() {
  api('/api/checklist-templates').then(ts => {
    const s = document.getElementById('cl-template');
    if(s) s.innerHTML = '<option value="">Select...</option>' + ts.map(t=>`<option value="${t.id}">${t.name}</option>`).join('');
  }).catch(()=>{});
  api('/api/properties').then(props => {
    const s = document.getElementById('cl-prop');
    if(s) s.innerHTML = '<option value="">No property</option>' + props.map(p=>`<option value="${p.id}">${p.name}</option>`).join('');
  }).catch(()=>{});
}
async function loadChecklists() {
  try {
    const d = await api('/api/checklists');
    const el = document.getElementById('checklists-table');
    if(!d.length){el.innerHTML='<div class="empty">No checklists yet. Click "+ Start Checklist" to begin!</div>';return;}
    el.innerHTML = d.map(r=>{
      const pct = r.total_steps>0?Math.round(r.done_steps/r.total_steps*100):0;
      return `<div style="border-bottom:1px solid var(--border);padding:16px 0">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
          <div><strong style="font-size:14px">${r.name}</strong>
          <div style="font-size:12px;color:var(--muted);margin-top:2px">${r.template_name} · ${r.property_name||'No property'}</div></div>
          <div style="display:flex;align-items:center;gap:8px">
            <span style="font-size:12px;color:var(--muted)">${r.done_steps}/${r.total_steps} steps</span>
            <span class="badge ${r.status==='completed'?'badge-green':'badge-amber'}">${r.status}</span>
            ${r.status==='active'?`<button class="btn btn-ghost btn-sm" onclick="viewChecklist(${r.id})">Open</button>`:''}
            <button class="btn btn-danger btn-sm" onclick="deleteChecklist(${r.id})">Delete</button>
          </div>
        </div>
        <div style="height:6px;background:var(--border);border-radius:4px;overflow:hidden">
          <div style="height:100%;width:${pct}%;background:${pct===100?'var(--green)':'var(--accent)'};border-radius:4px;transition:.3s"></div>
        </div></div>`;
    }).join('');
  } catch(e){showToast('Failed to load checklists: '+e.message,false);}
}
async function startChecklist() {
  const name=document.getElementById('cl-name').value.trim();
  const tmpl=document.getElementById('cl-template').value;
  if(!name){showToast('Checklist name is required',false);return;}
  if(!tmpl){showToast('Please select a template',false);return;}
  const btn=document.getElementById('btn-start-checklist');btn.dataset.label='Start Checklist';setLoading('btn-start-checklist',true);
  try {
    const r=await api('/api/checklists/start',{name,template_id:parseInt(tmpl),property_id:document.getElementById('cl-prop').value||null,notes:document.getElementById('cl-notes').value.trim()});
    if(r.success){closeModal('modal-start-checklist');document.getElementById('cl-name').value='';document.getElementById('cl-notes').value='';showToast('✅ Checklist started!');loadChecklists();viewChecklist(r.id);}
    else showToast('Error: '+(r.error||''),false);
  }catch(e){showToast('Server error: '+e.message,false);}finally{setLoading('btn-start-checklist',false);}
}
async function viewChecklist(id) {
  try {
    const d=await api('/api/checklists/'+id);
    const steps=JSON.parse(d.steps);const done=d.done_step_indices||[];
    document.getElementById('checklists-table').innerHTML=`
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <div><h3 style="font-size:16px">${d.name}</h3><div style="font-size:12px;color:var(--muted)">${d.template_name} · ${d.property_name||'No property'}</div></div>
        <button class="btn btn-ghost btn-sm" onclick="loadChecklists()">← Back</button>
      </div>
      ${steps.map((step,i)=>{const isDone=done.includes(i);
        return `<div onclick="toggleStep(${id},${i})" style="display:flex;align-items:center;gap:12px;padding:10px;border-radius:8px;cursor:pointer;margin-bottom:4px;background:${isDone?'rgba(34,197,94,0.08)':'transparent'}">
          <div style="width:22px;height:22px;border-radius:50%;border:2px solid ${isDone?'var(--green)':'var(--border)'};background:${isDone?'var(--green)':'transparent'};display:flex;align-items:center;justify-content:center;flex-shrink:0">
            ${isDone?'<span style="color:#000;font-size:13px">✓</span>':''}
          </div>
          <span style="font-size:13px;${isDone?'text-decoration:line-through;color:var(--muted)':''}">${step}</span>
        </div>`;}).join('')}
      ${d.status==='active'&&done.length===steps.length?`<button class="btn btn-success" style="width:100%;margin-top:12px" onclick="completeChecklist(${id})">✓ Mark All Complete</button>`:''}`;
  }catch(e){showToast('Could not open checklist: '+e.message,false);}
}
async function toggleStep(runId,stepIndex) {
  try{await api('/api/checklists/toggle',{run_id:runId,step_index:stepIndex});viewChecklist(runId);}
  catch(e){showToast('Could not update step: '+e.message,false);}
}
async function completeChecklist(id) {
  try{const r=await api('/api/checklists/complete/'+id,{});if(r.success){showToast('✅ Checklist complete!');loadChecklists();}else showToast('Error: '+r.error,false);}
  catch(e){showToast('Server error: '+e.message,false);}
}
async function deleteChecklist(id) {
  if(!confirm('Delete this checklist run?'))return;
  try{const r=await api('/api/checklists/delete/'+id,{});if(r.success){showToast('Checklist deleted');loadChecklists();}else showToast('Error: '+r.error,false);}
  catch(e){showToast('Server error: '+e.message,false);}
}

// ── bills ─────────────────────────────────────────────────
async function openAddBill() {
  document.getElementById('bill-modal-title').textContent='Add Bill';
  document.getElementById('btn-save-bill').textContent='Add Bill';
  document.getElementById('btn-save-bill').dataset.label='Add Bill';
  ['bl-desc','bl-notes'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('bl-id').value='';document.getElementById('bl-amount').value='';document.getElementById('bl-due').value='';document.getElementById('bl-category').value='other';
  const props=await api('/api/properties').catch(()=>[]);
  document.getElementById('bl-prop').innerHTML='<option value="">No property</option>'+props.map(p=>`<option value="${p.id}">${p.name}</option>`).join('');
  openModal('modal-add-bill');
}
async function openEditBill(id) {
  try {
    const bills=await api('/api/bills');const b=bills.find(x=>x.id===id);if(!b)return showToast('Bill not found',false);
    document.getElementById('bill-modal-title').textContent='Edit Bill';document.getElementById('btn-save-bill').textContent='Save Changes';document.getElementById('btn-save-bill').dataset.label='Save Changes';
    document.getElementById('bl-id').value=b.id;document.getElementById('bl-desc').value=b.description;document.getElementById('bl-amount').value=b.amount;document.getElementById('bl-due').value=b.due_date||'';document.getElementById('bl-notes').value=b.notes||'';document.getElementById('bl-category').value=b.category||'other';
    const props=await api('/api/properties');document.getElementById('bl-prop').innerHTML='<option value="">No property</option>'+props.map(p=>`<option value="${p.id}"${p.id==b.property_id?' selected':''}>${p.name}</option>`).join('');
    openModal('modal-add-bill');
  }catch(e){showToast('Could not load bill: '+e.message,false);}
}
async function saveBill() {
  const desc=document.getElementById('bl-desc').value.trim();if(!desc){showToast('Description is required',false);return;}
  const id=document.getElementById('bl-id').value;const url=id?'/api/bills/update/'+id:'/api/bills/add';
  const btn=document.getElementById('btn-save-bill');btn.dataset.label=btn.textContent;setLoading('btn-save-bill',true);
  try {
    const r=await api(url,{description:desc,property_id:document.getElementById('bl-prop').value||null,amount:parseFloat(document.getElementById('bl-amount').value)||0,due_date:document.getElementById('bl-due').value,category:document.getElementById('bl-category').value,notes:document.getElementById('bl-notes').value.trim()});
    if(r.success){closeModal('modal-add-bill');showToast(id?'✅ Bill updated!':'✅ Bill added!');loadBills();}else showToast('Error: '+(r.error||''),false);
  }catch(e){showToast('Server error: '+e.message,false);}finally{setLoading('btn-save-bill',false);}
}
async function loadBills() {
  try {
    const sf=document.getElementById('bf-status')?.value||'';
    const d=await api('/api/bills'+(sf?'?status='+sf:''));
    const el=document.getElementById('bills-table');
    if(!d.length){el.innerHTML='<div class="empty">No bills yet. Click "+ Add Bill" to track expenses!</div>';return;}
    const tot=d.reduce((s,b)=>s+(b.status==='unpaid'?b.amount:0),0);
    el.innerHTML=`<div style="margin-bottom:12px;font-size:13px;color:var(--muted)">Total unpaid: <strong style="color:var(--red)">$${tot.toLocaleString('en-US',{minimumFractionDigits:2})}</strong></div>`+
      '<table><tr><th>Description</th><th>Property</th><th>Category</th><th>Amount</th><th>Due Date</th><th>Status</th><th></th></tr>'+
      d.map(b=>`<tr>
        <td><strong>${b.description}</strong>${b.notes?`<br><span style="color:var(--muted);font-size:11px">${b.notes}</span>`:''}</td>
        <td style="color:var(--muted)">${b.property_name||'—'}</td>
        <td style="color:var(--muted);text-transform:capitalize">${b.category}</td>
        <td>$${Number(b.amount).toLocaleString('en-US',{minimumFractionDigits:2})}</td>
        <td style="color:var(--muted)">${b.due_date||'—'}</td>
        <td><span class="badge ${b.status==='paid'?'badge-green':'badge-red'}">${b.status}</span></td>
        <td style="display:flex;gap:6px">
          ${b.status==='unpaid'?`<button class="btn btn-success btn-sm" onclick="markBillPaid(${b.id})">Paid</button>`:''}
          <button class="btn btn-ghost btn-sm" onclick="openEditBill(${b.id})">Edit</button>
          <button class="btn btn-danger btn-sm" onclick="deleteBill(${b.id})">Delete</button>
        </td></tr>`).join('')+'</table>';
  }catch(e){showToast('Failed to load bills: '+e.message,false);}
}
async function markBillPaid(id){try{const r=await api('/api/bills/paid/'+id,{});if(r.success){showToast('Bill marked as paid!');loadBills();}else showToast('Error: '+(r.error||''),false);}catch(e){showToast('Server error: '+e.message,false);}}
async function deleteBill(id){if(!confirm('Delete this bill?'))return;try{const r=await api('/api/bills/delete/'+id,{});if(r.success){showToast('Bill deleted');loadBills();}else showToast('Error: '+r.error,false);}catch(e){showToast('Server error: '+e.message,false);}}

// ── AI Generate ───────────────────────────────────────────
function switchAiTab(tab,btn){
  document.querySelectorAll('.ai-form').forEach(f=>f.style.display='none');
  document.querySelectorAll('.ai-tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('ai-'+tab).style.display='block';btn.classList.add('active');
  document.getElementById('ai-output').style.display='none';
}
function loadAiProps(){
  api('/api/properties').then(props=>{
    const opts='<option value="">Select...</option>'+props.map(p=>`<option value="${p.name}">${p.name}</option>`).join('');
    ['ai-ld-prop','ai-dr-prop','ai-mo-prop','ai-mn-prop','ai-wl-prop'].forEach(id=>{const s=document.getElementById(id);if(s)s.innerHTML=opts;});
  }).catch(()=>{});
}
function generateAi(type){
  const td=new Date().toLocaleDateString('en-US',{year:'numeric',month:'long',day:'numeric'});
  let text='';
  if(type==='lease-draft'){
    const prop=document.getElementById('ai-ld-prop').value||'[Property Address]';
    const tenant=document.getElementById('ai-ld-tenant').value||'[Tenant Name]';
    const start=document.getElementById('ai-ld-start').value||'[Start Date]';
    const end=document.getElementById('ai-ld-end').value||'[End Date]';
    const rent=document.getElementById('ai-ld-rent').value||'[Rent]';
    const dep=document.getElementById('ai-ld-dep').value||'[Deposit]';
    const state=document.getElementById('ai-ld-state').value||'[State]';
    const pets=document.getElementById('ai-ld-pets').value;
    const terms=document.getElementById('ai-ld-terms').value;
    text=`RESIDENTIAL LEASE AGREEMENT\n\nDate: ${td}\n\nLANDLORD: LK Property Group\nTENANT: ${tenant}\nPROPERTY: ${prop}\n\n1. LEASE TERM\nThis lease begins on ${start} and ends on ${end}.\n\n2. RENT\nMonthly rent is $${rent}, due on the 1st of each month. A late fee of $50 applies after the 5th.\n\n3. SECURITY DEPOSIT\nTenant has paid a security deposit of $${dep}. This will be returned within 30 days of move-out, less deductions for damages beyond normal wear and tear.\n\n4. UTILITIES\nTenant is responsible for all utilities unless otherwise agreed in writing.\n\n5. PETS\nPets are ${pets==='Yes'?'permitted with prior written approval and a pet deposit':'NOT permitted on the premises'}.\n\n6. MAINTENANCE\nTenant agrees to keep the property clean and promptly report any maintenance issues.\n\n7. ENTRY\nLandlord may enter with 24 hours notice except in emergencies.\n\n8. TERMINATION\nEither party must provide 30 days written notice to terminate after the initial term.\n\n9. GOVERNING LAW\nThis lease is governed by the laws of the State of ${state}.${terms?'\n\n10. SPECIAL TERMS\n'+terms:''}\n\nSIGNATURES\n\nLandlord: _________________________ Date: ____________\nLK Property Group\n\nTenant: __________________________ Date: ____________\n${tenant}`;
  } else if(type==='deposit-return'){
    const prop=document.getElementById('ai-dr-prop').value||'[Property]';
    const tenant=document.getElementById('ai-dr-tenant').value||'[Tenant Name]';
    const dep=parseFloat(document.getElementById('ai-dr-deposit').value)||0;
    const ded=parseFloat(document.getElementById('ai-dr-deduct').value)||0;
    const reasons=document.getElementById('ai-dr-reasons').value;
    const refund=Math.max(0,dep-ded);
    text=`SECURITY DEPOSIT RETURN LETTER\n\nDate: ${td}\n\nTo: ${tenant}\nRe: Security Deposit Return – ${prop}\n\nDear ${tenant},\n\nThis letter confirms the return of your security deposit.\n\nSecurity Deposit Paid:  $${dep.toFixed(2)}\n${ded>0?`Deductions:             $${ded.toFixed(2)}\n${reasons?reasons.split('\n').map(r=>'  - '+r).join('\n'):''}`:''}\nTotal Refund Amount:    $${refund.toFixed(2)}\n\n${refund>0?`A check for $${refund.toFixed(2)} will be mailed to your forwarding address within 30 days of your move-out date.`:'Based on the itemized deductions above, no refund is owed.'}\n\nSincerely,\nLK Property Group\nadmin@lkpropertygroup.com`;
  } else if(type==='moveout-notice'){
    const prop=document.getElementById('ai-mo-prop').value||'[Property]';
    const tenant=document.getElementById('ai-mo-tenant').value||'[Tenant Name]';
    const dt=document.getElementById('ai-mo-date').value||'[Move-Out Date]';
    const dep=document.getElementById('ai-mo-deposit').value||'[Deposit Amount]';
    text=`MOVE-OUT INSTRUCTIONS\n\nDate: ${td}\n\nTo: ${tenant}\nProperty: ${prop}\nMove-Out Date: ${dt}\n\nDear ${tenant},\n\nPlease follow these instructions for a smooth move-out.\n\nBEFORE YOU LEAVE:\n☐ Clean all rooms thoroughly\n☐ Clean inside all appliances\n☐ Remove ALL personal belongings\n☐ Patch nail holes and clean scuff marks\n☐ Return all keys, fobs, mailbox keys, and remotes\n☐ Cancel or transfer utilities in your name\n\nSECURITY DEPOSIT:\nYour deposit of $${dep} will be returned within 30 days after move-out, minus any deductions for damages beyond normal wear and tear.\n\nPlease schedule a move-out walkthrough: admin@lkpropertygroup.com\n\nSincerely,\nLK Property Group\nadmin@lkpropertygroup.com`;
  } else if(type==='maint-notice'){
    const prop=document.getElementById('ai-mn-prop').value||'[Property]';
    const tenant=document.getElementById('ai-mn-tenant').value||'[Tenant Name]';
    const dt=document.getElementById('ai-mn-date').value||'[Date]';
    const time=document.getElementById('ai-mn-time').value||'[Time]';
    const desc=document.getElementById('ai-mn-desc').value||'[Work Description]';
    text=`MAINTENANCE NOTICE\n\nDate: ${td}\n\nTo: ${tenant}\nProperty: ${prop}\n\nDear ${tenant},\n\nMaintenance work will be performed at your property:\n\nDate: ${dt}\nTime: ${time}\nDescription: ${desc}\n\nOur team or authorized vendor will need access during this time. If you will not be home, access will be made using our key per your lease agreement.\n\nWe apologize for any inconvenience. Contact us with questions: admin@lkpropertygroup.com\n\nSincerely,\nLK Property Group`;
  } else if(type==='welcome'){
    const prop=document.getElementById('ai-wl-prop').value||'[Property]';
    const tenant=document.getElementById('ai-wl-tenant').value||'[Tenant Name]';
    const dt=document.getElementById('ai-wl-date').value||'[Move-In Date]';
    const rent=document.getElementById('ai-wl-rent').value||'[Rent]';
    text=`WELCOME LETTER\n\nDate: ${td}\n\nDear ${tenant},\n\nWelcome to your new home at ${prop}! We are so excited to have you as part of the LK Property Group community.\n\nYOUR LEASE DETAILS:\nMove-In Date: ${dt}\nMonthly Rent: $${rent} (due on the 1st of each month)\n\nIMPORTANT CONTACTS:\nManagement: admin@lkpropertygroup.com\nMaintenance Requests: admin@lkpropertygroup.com (include photos)\n\nQUICK REMINDERS:\n• Rent is due on the 1st — grace period until the 5th\n• Report maintenance issues promptly\n• Renters insurance is strongly recommended\n• Review your lease for all community policies\n\nWe are committed to being responsive landlords. Don't hesitate to reach out!\n\nWarmly,\nLK Property Group\nadmin@lkpropertygroup.com`;
  }
  document.getElementById('ai-output-text').value=text;
  document.getElementById('ai-output').style.display='block';
  document.getElementById('ai-output').scrollIntoView({behavior:'smooth'});
}
function copyAiOutput(){navigator.clipboard.writeText(document.getElementById('ai-output-text').value).then(()=>showToast('📋 Copied to clipboard!'));}

// ── property selects ──────────────────────────────────────
function loadPropertySelects() {
  api('/api/properties').then(props => {
    ['t-prop','m-prop'].forEach(id => {
      const s = document.getElementById(id);
      if (!s) return;
      s.innerHTML = '<option value="">Select property...</option>' +
        props.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    });
  }).catch(e => showToast('Could not load properties: ' + e.message, false));
}

// ── init ──────────────────────────────────────────────────
loadDashboard();
</script>
</body>
</html>'''

@app.route("/")
def index():
    return HTML

@app.route("/api/dashboard")
def api_dashboard():
    try:
        conn = get_conn()
        data = {
            "total_properties": conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0],
            "total_tenants":    conn.execute("SELECT COUNT(*) FROM tenants WHERE is_active=1").fetchone()[0],
            "open_maintenance": conn.execute("SELECT COUNT(*) FROM maintenance WHERE status='open'").fetchone()[0],
            "emails_sent":      conn.execute("SELECT COUNT(*) FROM email_log WHERE status='sent'").fetchone()[0],
            "recent_emails":    [dict(r) for r in conn.execute("SELECT to_email, subject, status FROM email_log ORDER BY id DESC LIMIT 5").fetchall()],
            "expiring_leases":  [dict(r) for r in conn.execute(
                "SELECT full_name, lease_end FROM tenants WHERE is_active=1 AND lease_end IS NOT NULL "
                "AND DATE(lease_end) <= DATE('now', 'localtime', '+90 days') AND DATE(lease_end) >= DATE('now', 'localtime') "
                "ORDER BY lease_end LIMIT 5").fetchall()]
        }
        conn.close()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/properties")
def api_properties():
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT p.*, COUNT(t.id) as tenant_count FROM properties p "
            "LEFT JOIN tenants t ON p.id=t.property_id AND t.is_active=1 GROUP BY p.id"
        ).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/properties/add", methods=["POST"])
def api_add_property():
    try:
        d = request.json
        if not d.get("name") or not d.get("address"):
            return jsonify({"success": False, "error": "Name and address are required"})
        conn = get_conn()
        conn.execute(
            "INSERT INTO properties (name, address, unit, notes) VALUES (?,?,?,?)",
            (d["name"], d["address"], d.get("unit",""), d.get("notes",""))
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/properties/delete/<int:pid>", methods=["POST"])
def api_delete_property(pid):
    try:
        conn = get_conn()
        conn.execute("DELETE FROM properties WHERE id=?", (pid,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/properties/update/<int:pid>", methods=["POST"])
def api_update_property(pid):
    try:
        d = request.json
        if not d.get("name") or not d.get("address"):
            return jsonify({"success": False, "error": "Name and address are required"})
        conn = get_conn()
        conn.execute(
            "UPDATE properties SET name=?, address=?, unit=?, notes=? WHERE id=?",
            (d["name"], d["address"], d.get("unit", ""), d.get("notes", ""), pid)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/tenants")
def api_tenants():
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT t.*, p.name as property_name FROM tenants t "
            "LEFT JOIN properties p ON t.property_id=p.id WHERE t.is_active=1 ORDER BY t.full_name"
        ).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tenants/add", methods=["POST"])
def api_add_tenant():
    try:
        d = request.json
        required = ["full_name", "property_id", "email", "rent_amount", "rent_due_day"]
        for f in required:
            if not d.get(f) and d.get(f) != 0:
                return jsonify({"success": False, "error": f"'{f}' is required"})
        conn = get_conn()
        conn.execute(
            "INSERT INTO tenants (property_id,full_name,email,phone,rent_amount,rent_due_day,lease_start,lease_end,is_active) "
            "VALUES (?,?,?,?,?,?,?,?,1)",
            (d["property_id"], d["full_name"], d["email"], d.get("phone",""),
             d["rent_amount"], d["rent_due_day"], d.get("lease_start",""), d.get("lease_end",""))
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/tenants/update/<int:tid>", methods=["POST"])
def api_update_tenant(tid):
    try:
        d = request.json
        conn = get_conn()
        conn.execute(
            "UPDATE tenants SET full_name=?, property_id=?, email=?, phone=?, "
            "rent_amount=?, rent_due_day=?, lease_start=?, lease_end=? WHERE id=?",
            (d["full_name"], d["property_id"], d["email"], d.get("phone", ""),
             d["rent_amount"], d.get("rent_due_day", 1),
             d.get("lease_start", ""), d.get("lease_end", ""), tid)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/tenants/deactivate/<int:tid>", methods=["POST"])
def api_deactivate_tenant(tid):
    try:
        conn = get_conn()
        conn.execute("UPDATE tenants SET is_active=0 WHERE id=?", (tid,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/maintenance")
def api_maintenance():
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT m.*, p.name as property_name, p.address, t.full_name as tenant_name "
            "FROM maintenance m "
            "LEFT JOIN properties p ON m.property_id=p.id "
            "LEFT JOIN tenants t ON m.tenant_id=t.id "
            "ORDER BY CASE m.status WHEN 'open' THEN 0 ELSE 1 END, m.date_reported DESC"
        ).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/maintenance/add", methods=["POST"])
def api_add_maintenance():
    try:
        d = request.json
        if not d.get("property_id"):
            return jsonify({"success": False, "error": "Property is required"})
        if not d.get("description"):
            return jsonify({"success": False, "error": "Description is required"})
        conn = get_conn()
        t = conn.execute(
            "SELECT id FROM tenants WHERE property_id=? AND is_active=1 LIMIT 1",
            (d["property_id"],)
        ).fetchone()
        conn.execute(
            "INSERT INTO maintenance (property_id,tenant_id,description,date_reported,status) VALUES (?,?,?,?,?)",
            (d["property_id"], t["id"] if t else None, d["description"], date.today().strftime("%Y-%m-%d"), "open")
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/maintenance/resolve/<int:mid>", methods=["POST"])
def api_resolve_maintenance(mid):
    try:
        conn = get_conn()
        conn.execute(
            "UPDATE maintenance SET status='resolved', date_resolved=? WHERE id=?",
            (date.today().strftime("%Y-%m-%d"), mid)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── tasks ──────────────────────────────────────────────────
@app.route("/api/tasks")
def api_tasks():
    try:
        conn = get_conn()
        status   = request.args.get('status')
        priority = request.args.get('priority')
        q = "SELECT t.*, p.name as property_name FROM tasks t LEFT JOIN properties p ON t.property_id=p.id WHERE 1=1"
        params = []
        if status:   q += " AND t.status=?";   params.append(status)
        if priority: q += " AND t.priority=?"; params.append(priority)
        q += " ORDER BY CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, t.deadline"
        rows = conn.execute(q, params).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tasks/<int:tid>")
def api_get_task(tid):
    try:
        conn = get_conn()
        row  = conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        conn.close()
        return jsonify(dict(row)) if row else (jsonify({"error": "Not found"}), 404)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tasks/add", methods=["POST"])
def api_add_task():
    try:
        d = request.json
        if not d.get("title"):
            return jsonify({"success": False, "error": "Title is required"})
        conn = get_conn()
        conn.execute(
            "INSERT INTO tasks (property_id,title,assignee,priority,status,deadline,category,notes) VALUES (?,?,?,?,?,?,?,?)",
            (d.get("property_id"), d["title"], d.get("assignee",""), d.get("priority","medium"),
             d.get("status","todo"), d.get("deadline",""), d.get("category","general"), d.get("notes",""))
        )
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/tasks/update/<int:tid>", methods=["POST"])
def api_update_task(tid):
    try:
        d    = request.json
        conn = get_conn()
        task = dict(conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())
        conn.execute(
            "UPDATE tasks SET property_id=?,title=?,assignee=?,priority=?,status=?,deadline=?,category=?,notes=? WHERE id=?",
            (d.get("property_id", task.get("property_id")), d.get("title", task["title"]),
             d.get("assignee", task.get("assignee","")), d.get("priority", task.get("priority","medium")),
             d.get("status", task.get("status","todo")), d.get("deadline", task.get("deadline","")),
             d.get("category", task.get("category","general")), d.get("notes", task.get("notes","")), tid)
        )
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/tasks/delete/<int:tid>", methods=["POST"])
def api_delete_task(tid):
    try:
        conn = get_conn()
        conn.execute("DELETE FROM tasks WHERE id=?", (tid,))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── checklists ─────────────────────────────────────────────
@app.route("/api/checklist-templates")
def api_checklist_templates():
    try:
        conn = get_conn()
        rows = conn.execute("SELECT * FROM checklist_templates ORDER BY name").fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/checklists")
def api_checklists():
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT r.*, t.name as template_name, t.steps, p.name as property_name,"
            "(SELECT COUNT(*) FROM checklist_steps_done WHERE run_id=r.id) as done_steps,"
            "(SELECT json_array_length(t2.steps) FROM checklist_templates t2 WHERE t2.id=r.template_id) as total_steps "
            "FROM checklist_runs r "
            "LEFT JOIN checklist_templates t ON r.template_id=t.id "
            "LEFT JOIN properties p ON r.property_id=p.id "
            "ORDER BY CASE r.status WHEN 'active' THEN 0 ELSE 1 END, r.started_at DESC"
        ).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/checklists/<int:rid>")
def api_get_checklist(rid):
    try:
        conn = get_conn()
        row  = conn.execute(
            "SELECT r.*, t.name as template_name, t.steps, p.name as property_name "
            "FROM checklist_runs r LEFT JOIN checklist_templates t ON r.template_id=t.id "
            "LEFT JOIN properties p ON r.property_id=p.id WHERE r.id=?", (rid,)
        ).fetchone()
        done = conn.execute("SELECT step_index FROM checklist_steps_done WHERE run_id=?", (rid,)).fetchall()
        conn.close()
        if not row: return jsonify({"error": "Not found"}), 404
        d = dict(row)
        d["done_step_indices"] = [r["step_index"] for r in done]
        return jsonify(d)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/checklists/start", methods=["POST"])
def api_start_checklist():
    try:
        d = request.json
        if not d.get("name"):        return jsonify({"success": False, "error": "Name is required"})
        if not d.get("template_id"): return jsonify({"success": False, "error": "Template is required"})
        conn = get_conn()
        cur  = conn.execute(
            "INSERT INTO checklist_runs (template_id,property_id,name,notes) VALUES (?,?,?,?)",
            (d["template_id"], d.get("property_id"), d["name"], d.get("notes",""))
        )
        run_id = cur.lastrowid
        conn.commit(); conn.close()
        return jsonify({"success": True, "id": run_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/checklists/toggle", methods=["POST"])
def api_toggle_step():
    try:
        d   = request.json
        conn = get_conn()
        ex  = conn.execute(
            "SELECT id FROM checklist_steps_done WHERE run_id=? AND step_index=?",
            (d["run_id"], d["step_index"])
        ).fetchone()
        if ex: conn.execute("DELETE FROM checklist_steps_done WHERE run_id=? AND step_index=?", (d["run_id"], d["step_index"]))
        else:  conn.execute("INSERT INTO checklist_steps_done (run_id,step_index) VALUES (?,?)", (d["run_id"], d["step_index"]))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/checklists/complete/<int:rid>", methods=["POST"])
def api_complete_checklist(rid):
    try:
        conn = get_conn()
        conn.execute("UPDATE checklist_runs SET status='completed', completed_at=? WHERE id=?",
                     (date.today().strftime("%Y-%m-%d"), rid))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/checklists/delete/<int:rid>", methods=["POST"])
def api_delete_checklist(rid):
    try:
        conn = get_conn()
        conn.execute("DELETE FROM checklist_steps_done WHERE run_id=?", (rid,))
        conn.execute("DELETE FROM checklist_runs WHERE id=?", (rid,))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── bills ──────────────────────────────────────────────────
@app.route("/api/bills")
def api_bills():
    try:
        conn   = get_conn()
        status = request.args.get('status')
        q      = "SELECT b.*, p.name as property_name FROM bills b LEFT JOIN properties p ON b.property_id=p.id WHERE 1=1"
        params = []
        if status: q += " AND b.status=?"; params.append(status)
        q += " ORDER BY CASE b.status WHEN 'unpaid' THEN 0 ELSE 1 END, b.due_date"
        rows = conn.execute(q, params).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/bills/add", methods=["POST"])
def api_add_bill():
    try:
        d = request.json
        if not d.get("description"): return jsonify({"success": False, "error": "Description is required"})
        conn = get_conn()
        conn.execute(
            "INSERT INTO bills (property_id,description,amount,due_date,category,notes) VALUES (?,?,?,?,?,?)",
            (d.get("property_id"), d["description"], d.get("amount",0),
             d.get("due_date",""), d.get("category","other"), d.get("notes",""))
        )
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/bills/update/<int:bid>", methods=["POST"])
def api_update_bill(bid):
    try:
        d = request.json
        conn = get_conn()
        conn.execute(
            "UPDATE bills SET property_id=?,description=?,amount=?,due_date=?,category=?,notes=? WHERE id=?",
            (d.get("property_id"), d["description"], d.get("amount",0),
             d.get("due_date",""), d.get("category","other"), d.get("notes",""), bid)
        )
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/bills/paid/<int:bid>", methods=["POST"])
def api_mark_bill_paid(bid):
    try:
        conn = get_conn()
        conn.execute("UPDATE bills SET status='paid', paid_date=? WHERE id=?",
                     (date.today().strftime("%Y-%m-%d"), bid))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/bills/delete/<int:bid>", methods=["POST"])
def api_delete_bill(bid):
    try:
        conn = get_conn()
        conn.execute("DELETE FROM bills WHERE id=?", (bid,))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    setup_database()
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=False, port=5000)
