from flask import Flask, request, jsonify
import sqlite3, json, os
from datetime import datetime, date

try:
    from config import DATABASE_PATH, COMPANY_NAME, GMAIL_ADDRESS
except:
    DATABASE_PATH = "lk_properties.db"
    COMPANY_NAME = "LK Property Group"
    GMAIL_ADDRESS = ""

app = Flask(__name__)

def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    conn = get_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, address TEXT, unit TEXT, notes TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS tenants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT, property_id INTEGER, email TEXT, phone TEXT,
        rent_amount REAL, rent_due_day INTEGER,
        lease_start TEXT, lease_end TEXT, is_active INTEGER DEFAULT 1)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS maintenance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER, tenant_id INTEGER,
        description TEXT, status TEXT DEFAULT "open",
        date_reported TEXT, date_resolved TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS email_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        to_email TEXT, subject TEXT, type TEXT,
        tenant_id INTEGER, property_id INTEGER,
        status TEXT, sent_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER, title TEXT, assignee TEXT,
        priority TEXT DEFAULT "medium", status TEXT DEFAULT "todo",
        deadline TEXT, category TEXT DEFAULT "general", notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS checklist_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, steps TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS checklist_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER, property_id INTEGER,
        name TEXT, notes TEXT, status TEXT DEFAULT "active",
        started_at TEXT DEFAULT CURRENT_TIMESTAMP, completed_at TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS checklist_steps_done (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER, step_index INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER, description TEXT, amount REAL,
        due_date TEXT, category TEXT DEFAULT "other",
        status TEXT DEFAULT "unpaid", notes TEXT,
        paid_date TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    print("Database ready.")

# Seed default checklist templates
def seed_templates():
    conn = get_conn()
    if conn.execute("SELECT COUNT(*) FROM checklist_templates").fetchone()[0] > 0:
        conn.close()
        return
    templates = [
        ("Tenant move-in", json.dumps([
            "Verify ID and signed lease",
            "Collect first month rent and deposit",
            "Complete move-in inspection with tenant",
            "Document condition with photos",
            "Test all appliances",
            "Check all doors and locks",
            "Test smoke and CO detectors",
            "Review utility setup with tenant",
            "Provide keys and access items",
            "Share emergency contact info",
            "Have tenant sign move-in checklist"
        ])),
        ("Tenant move-out", json.dumps([
            "Send move-out instructions 30 days prior",
            "Schedule move-out inspection",
            "Conduct move-out inspection with photos",
            "Compare to move-in condition",
            "Document any damages beyond normal wear",
            "Collect all keys and access items",
            "Process security deposit return",
            "Clean and prepare unit for next tenant"
        ]))
    ]
    for name, steps in templates:
        conn.execute("INSERT INTO checklist_templates (name, steps) VALUES (?, ?)", (name, steps))
    conn.commit()
    conn.close()

HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LK Property Management</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0f1117;--surface:#1a1d27;--surface2:#22263a;
  --accent:#6c63ff;--accent2:#a78bfa;
  --green:#22c55e;--red:#ef4444;--amber:#f59e0b;
  --text:#f0f0f8;--muted:#8b8fa8;--border:#2e3350;
}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex}
a{color:inherit;text-decoration:none}
.sidebar{width:220px;background:var(--surface);border-right:1px solid var(--border);padding:24px 0;display:flex;flex-direction:column;position:fixed;height:100vh;z-index:10}
.logo{padding:0 20px 24px;border-bottom:1px solid var(--border);margin-bottom:16px}
.logo h1{font-size:18px;color:var(--accent2);line-height:1.2}
.logo p{font-size:11px;color:var(--muted);margin-top:2px}
.nav-link{display:flex;align-items:center;gap:10px;padding:10px 20px;font-size:13px;color:var(--muted);cursor:pointer;border-left:3px solid transparent;transition:.15s;user-select:none}
.nav-link:hover{color:var(--text);background:var(--surface2)}
.nav-link.active{color:var(--text);background:var(--surface2);border-left-color:var(--accent)}
.main{margin-left:220px;flex:1;padding:32px}
.page{display:none}
.page.active{display:block}
.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px}
.page-title{font-size:28px;font-weight:600;color:var(--text)}
.btn{padding:9px 18px;border-radius:8px;border:none;cursor:pointer;font-size:13px;font-weight:500;transition:.15s}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:#5a52e0}
.btn-danger{background:transparent;color:var(--red);border:1px solid var(--red)}
.btn-success{background:var(--green);color:#fff}
.btn-ghost{background:var(--surface2);color:var(--text);border:1px solid var(--border)}
.btn-sm{padding:5px 12px;font-size:12px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:20px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px}
.stat-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.stat-value{font-size:36px;font-weight:600;margin-top:8px}
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
.modal h2{font-size:22px;font-weight:600;margin-bottom:20px}
.modal-footer{display:flex;gap:10px;justify-content:flex-end;margin-top:16px}
.form-group{margin-bottom:16px}
.form-group label{display:block;font-size:12px;color:var(--muted);margin-bottom:6px}
.form-group input,.form-group select,.form-group textarea{width:100%;background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:9px 12px;color:var(--text);font-size:13px;outline:none}
.form-group input:focus,.form-group select:focus,.form-group textarea:focus{border-color:var(--accent)}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.toast{position:fixed;bottom:24px;right:24px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 20px;font-size:13px;z-index:999;transform:translateY(100px);opacity:0;transition:.3s}
.toast.show{transform:translateY(0);opacity:1}
.empty{color:var(--muted);text-align:center;padding:40px;font-size:13px}
.spinner{display:inline-block;width:12px;height:12px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite;margin-right:6px}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>

<aside class="sidebar">
  <div class="logo">
    <h1>LK Property</h1>
    <p>Management System</p>
  </div>
  <div class="nav-link active" onclick="showPage('dashboard', this)">Dashboard</div>
  <div class="nav-link" onclick="showPage('properties', this)">Properties</div>
  <div class="nav-link" onclick="showPage('tenants', this)">Tenants</div>
  <div class="nav-link" onclick="showPage('maintenance', this)">Maintenance</div>
  <div class="nav-link" onclick="showPage('tasks', this)">Tasks</div>
  <div class="nav-link" onclick="showPage('checklists', this)">Checklists</div>
  <div class="nav-link" onclick="showPage('bills', this)">Bills</div>
</aside>

<main class="main">

  <!-- DASHBOARD -->
  <div id="page-dashboard" class="page active">
    <div class="page-header">
      <h1 class="page-title">Dashboard</h1>
    </div>
    <div class="stats">
      <div class="stat" style="border-top:3px solid var(--accent)"><div class="stat-label">Properties</div><div class="stat-value" id="stat-props">-</div></div>
      <div class="stat" style="border-top:3px solid var(--green)"><div class="stat-label">Active Tenants</div><div class="stat-value" id="stat-tenants">-</div></div>
      <div class="stat" style="border-top:3px solid var(--amber)"><div class="stat-label">Open Maintenance</div><div class="stat-value" id="stat-maint">-</div></div>
      <div class="stat" style="border-top:3px solid var(--accent2)"><div class="stat-label">Emails Sent</div><div class="stat-value" id="stat-emails">-</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div class="card"><h3 style="font-size:14px;margin-bottom:16px;color:var(--muted)">Leases Expiring Soon</h3><div id="dash-leases"><div class="empty">Loading...</div></div></div>
      <div class="card"><h3 style="font-size:14px;margin-bottom:16px;color:var(--muted)">Recent Emails</h3><div id="dash-emails"><div class="empty">Loading...</div></div></div>
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
    <div style="display:flex;gap:8px;margin-bottom:16px">
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

<div id="modal-edit-property" class="modal-bg" onclick="if(event.target===this)closeModal('modal-edit-property')">
  <div class="modal">
    <h2>Edit Property</h2>
    <input type="hidden" id="ep-id">
    <div class="form-group"><label>Property Name *</label><input id="ep-name"></div>
    <div class="form-group"><label>Full Address *</label><input id="ep-address"></div>
    <div class="form-row">
      <div class="form-group"><label>Unit Number</label><input id="ep-unit"></div>
      <div class="form-group"><label>Notes</label><input id="ep-notes"></div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal('modal-edit-property')">Cancel</button>
      <button class="btn btn-primary" id="btn-save-property" onclick="saveEditProperty()">Save Changes</button>
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

<div id="modal-add-task" class="modal-bg" onclick="if(event.target===this)closeTaskModal()">
  <div class="modal">
    <h2 id="task-modal-title">Add Task</h2>
    <input type="hidden" id="tk-id">
    <div class="form-group"><label>Task Title *</label><input id="tk-title" placeholder="What needs to be done?"></div>
    <div class="form-row">
      <div class="form-group"><label>Property</label><select id="tk-prop"><option value="">No property</option></select></div>
      <div class="form-group"><label>Assignee</label><input id="tk-assignee" placeholder="Name"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>Priority</label><select id="tk-priority"><option value="high">High</option><option value="medium" selected>Medium</option><option value="low">Low</option></select></div>
      <div class="form-group"><label>Status</label><select id="tk-status"><option value="todo">To Do</option><option value="in-progress">In Progress</option><option value="done">Done</option></select></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>Deadline</label><input id="tk-deadline" type="date"></div>
      <div class="form-group"><label>Category</label><select id="tk-category"><option value="general">General</option><option value="maintenance">Maintenance</option><option value="legal">Legal</option><option value="financial">Financial</option><option value="cleaning">Cleaning</option></select></div>
    </div>
    <div class="form-group"><label>Notes</label><textarea id="tk-notes" rows="2" placeholder="Details..."></textarea></div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeTaskModal()">Cancel</button>
      <button class="btn btn-primary" id="btn-save-task" onclick="saveTask()">Add Task</button>
    </div>
  </div>
</div>

<div id="modal-start-checklist" class="modal-bg" onclick="if(event.target===this)closeModal('modal-start-checklist')">
  <div class="modal">
    <h2>Start Checklist</h2>
    <div class="form-group"><label>Checklist Name *</label><input id="cl-name" placeholder="e.g. Sonya move-out May 2026"></div>
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
      <div class="form-group"><label>Amount (PHP)</label><input id="bl-amount" type="number" placeholder="0.00"></div>
      <div class="form-group"><label>Due Date</label><input id="bl-due" type="date"></div>
    </div>
    <div class="form-group"><label>Notes</label><input id="bl-notes" placeholder="Optional notes"></div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal('modal-add-bill')">Cancel</button>
      <button class="btn btn-primary" id="btn-save-bill" onclick="saveBill()">Add Bill</button>
    </div>
  </div>
</div>

<div id="toast" class="toast"></div>

<script>
function showPage(name, el) {
  document.querySelectorAll('.page').forEach(function(p) { p.classList.remove('active'); });
  document.querySelectorAll('.nav-link').forEach(function(n) { n.classList.remove('active'); });
  document.getElementById('page-' + name).classList.add('active');
  if (el) el.classList.add('active');
  if (name === 'dashboard')   loadDashboard();
  if (name === 'properties')  loadProperties();
  if (name === 'tenants')     loadTenants();
  if (name === 'maintenance') loadMaintenance();
  if (name === 'tasks')       loadTasks();
  if (name === 'checklists')  loadChecklists();
  if (name === 'bills')       loadBills();
}

function openModal(id) {
  document.getElementById(id).classList.add('open');
  if (id === 'modal-add-tenant' || id === 'modal-add-maint') loadPropertySelects();
}
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

function showToast(msg, ok) {
  if (ok === undefined) ok = true;
  var t = document.getElementById('toast');
  t.textContent = msg;
  t.style.borderColor = ok ? 'var(--green)' : 'var(--red)';
  t.classList.add('show');
  setTimeout(function() { t.classList.remove('show'); }, 3500);
}

async function api(url, data) {
  try {
    var opts = data !== null && data !== undefined
      ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }
      : { method: 'GET' };
    var r = await fetch(url, opts);
    return await r.json();
  } catch(e) {
    showToast('Server error: ' + e.message, false);
    throw e;
  }
}

async function loadDashboard() {
  try {
    var d = await api('/api/dashboard');
    document.getElementById('stat-props').textContent   = d.total_properties;
    document.getElementById('stat-tenants').textContent = d.total_tenants;
    document.getElementById('stat-maint').textContent   = d.open_maintenance;
    document.getElementById('stat-emails').textContent  = d.emails_sent;
    var leases = document.getElementById('dash-leases');
    leases.innerHTML = d.expiring_leases.length
      ? '<table><tr><th>Tenant</th><th>Lease End</th></tr>' +
        d.expiring_leases.map(function(l) { return '<tr><td>' + l.full_name + '</td><td><span class="badge badge-amber">' + l.lease_end + '</span></td></tr>'; }).join('') + '</table>'
      : '<div class="empty">No leases expiring in 90 days</div>';
    var emails = document.getElementById('dash-emails');
    emails.innerHTML = d.recent_emails.length
      ? '<table><tr><th>To</th><th>Subject</th><th>Status</th></tr>' +
        d.recent_emails.map(function(e) { return '<tr><td style="color:var(--muted)">' + e.to_email + '</td><td>' + e.subject.substring(0,30) + '</td><td><span class="badge ' + (e.status==='sent'?'badge-green':'badge-red') + '">' + e.status + '</span></td></tr>'; }).join('') + '</table>'
      : '<div class="empty">No emails sent yet</div>';
  } catch(e) {}
}

async function loadProperties() {
  try {
    var d = await api('/api/properties');
    var el = document.getElementById('props-table');
    if (!d.length) { el.innerHTML = '<div class="empty">No properties yet. Click "+ Add Property" to get started!</div>'; return; }
    el.innerHTML = '<table><tr><th>Name</th><th>Address</th><th>Unit</th><th>Tenants</th><th>Notes</th><th></th></tr>' +
      d.map(function(p) { return '<tr><td><strong>' + p.name + '</strong></td><td>' + p.address + '</td><td>' + (p.unit||'-') + '</td><td><span class="badge badge-purple">' + p.tenant_count + ' tenant' + (p.tenant_count!=1?'s':'') + '</span></td><td style="color:var(--muted)">' + (p.notes||'-') + '</td><td style="display:flex;gap:6px"><button class="btn btn-ghost btn-sm" onclick="openEditProperty(' + p.id + ')">Edit</button><button class="btn btn-danger btn-sm" onclick="deleteProperty(' + p.id + ')">Remove</button></td></tr>'; }).join('') + '</table>';
  } catch(e) {}
}

async function addProperty() {
  var name = document.getElementById('p-name').value.trim();
  var address = document.getElementById('p-address').value.trim();
  if (!name || !address) { showToast('Name and address are required', false); return; }
  try {
    var r = await api('/api/properties/add', { name: name, address: address, unit: document.getElementById('p-unit').value, notes: document.getElementById('p-notes').value });
    if (r.success) { showToast('Property added!'); closeModal('modal-add-property'); ['p-name','p-address','p-unit','p-notes'].forEach(function(id) { document.getElementById(id).value = ''; }); loadProperties(); }
    else showToast(r.error || 'Error', false);
  } catch(e) {}
}

async function deleteProperty(id) {
  if (!confirm('Remove this property?')) return;
  try {
    var r = await api('/api/properties/delete/' + id, {});
    if (r.success) { showToast('Property removed!'); loadProperties(); }
    else showToast(r.error || 'Error', false);
  } catch(e) {}
}

async function openEditProperty(id) {
  try {
    var d = await api('/api/properties');
    var p = d.find(function(x) { return x.id === id; });
    if (!p) return;
    document.getElementById('ep-id').value      = p.id;
    document.getElementById('ep-name').value    = p.name;
    document.getElementById('ep-address').value = p.address;
    document.getElementById('ep-unit').value    = p.unit  || '';
    document.getElementById('ep-notes').value   = p.notes || '';
    openModal('modal-edit-property');
  } catch(e) {}
}

async function saveEditProperty() {
  var id = document.getElementById('ep-id').value;
  var name = document.getElementById('ep-name').value.trim();
  var address = document.getElementById('ep-address').value.trim();
  if (!name || !address) { showToast('Name and address are required', false); return; }
  try {
    var r = await api('/api/properties/update/' + id, { name: name, address: address, unit: document.getElementById('ep-unit').value, notes: document.getElementById('ep-notes').value });
    if (r.success) { showToast('Property updated!'); closeModal('modal-edit-property'); loadProperties(); }
    else showToast(r.error || 'Error', false);
  } catch(e) {}
}

async function loadTenants() {
  try {
    var d = await api('/api/tenants');
    var el = document.getElementById('tenants-table');
    if (!d.length) { el.innerHTML = '<div class="empty">No tenants yet. Add a property first, then add tenants!</div>'; return; }
    el.innerHTML = '<table><tr><th>Name</th><th>Property</th><th>Email</th><th>Phone</th><th>Rent (PHP)</th><th>Due Day</th><th>Lease End</th><th></th></tr>' +
      d.map(function(t) { return '<tr><td><strong>' + t.full_name + '</strong></td><td style="color:var(--muted)">' + (t.property_name||'-') + '</td><td style="color:var(--muted)">' + t.email + '</td><td style="color:var(--muted)">' + (t.phone||'-') + '</td><td>' + Number(t.rent_amount).toLocaleString() + '</td><td>' + t.rent_due_day + '</td><td>' + (t.lease_end ? '<span class="badge badge-amber">'+t.lease_end+'</span>' : '-') + '</td><td style="display:flex;gap:6px"><button class="btn btn-ghost btn-sm" onclick="openEditTenant(' + t.id + ')">Edit</button><button class="btn btn-danger btn-sm" onclick="deactivateTenant(' + t.id + ')">Move Out</button></td></tr>'; }).join('') + '</table>';
  } catch(e) {}
}

async function addTenant() {
  var name  = document.getElementById('t-name').value.trim();
  var prop  = document.getElementById('t-prop').value;
  var email = document.getElementById('t-email').value.trim();
  var rent  = document.getElementById('t-rent').value;
  var due   = document.getElementById('t-due').value;
  if (!name || !prop || !email || !rent || !due) { showToast('Please fill in all required fields', false); return; }
  try {
    var r = await api('/api/tenants/add', { full_name: name, property_id: parseInt(prop), email: email, phone: document.getElementById('t-phone').value, rent_amount: parseFloat(rent), rent_due_day: parseInt(due), lease_start: document.getElementById('t-start').value, lease_end: document.getElementById('t-end').value });
    if (r.success) { showToast('Tenant added!'); closeModal('modal-add-tenant'); ['t-name','t-email','t-phone','t-rent','t-due','t-start','t-end'].forEach(function(id) { document.getElementById(id).value = ''; }); document.getElementById('t-prop').value = ''; loadTenants(); }
    else showToast(r.error || 'Error', false);
  } catch(e) {}
}

async function openEditTenant(id) {
  try {
    var results = await Promise.all([api('/api/tenants'), api('/api/properties')]);
    var tenants = results[0]; var props = results[1];
    var t = tenants.find(function(x) { return x.id === id; });
    if (!t) return;
    var sel = document.getElementById('et-prop');
    sel.innerHTML = '<option value="">Select property...</option>' + props.map(function(p) { return '<option value="' + p.id + '"' + (p.id == t.property_id ? ' selected' : '') + '>' + p.name + '</option>'; }).join('');
    document.getElementById('et-id').value    = t.id;
    document.getElementById('et-name').value  = t.full_name;
    document.getElementById('et-email').value = t.email;
    document.getElementById('et-phone').value = t.phone       || '';
    document.getElementById('et-rent').value  = t.rent_amount;
    document.getElementById('et-due').value   = t.rent_due_day;
    document.getElementById('et-start').value = t.lease_start || '';
    document.getElementById('et-end').value   = t.lease_end   || '';
    document.getElementById('modal-edit-tenant').classList.add('open');
  } catch(e) {}
}

async function saveEditTenant() {
  var id    = document.getElementById('et-id').value;
  var name  = document.getElementById('et-name').value.trim();
  var prop  = document.getElementById('et-prop').value;
  var email = document.getElementById('et-email').value.trim();
  var rent  = document.getElementById('et-rent').value;
  if (!name || !prop || !email || !rent) { showToast('Please fill in required fields', false); return; }
  try {
    var r = await api('/api/tenants/update/' + id, { full_name: name, property_id: parseInt(prop), email: email, phone: document.getElementById('et-phone').value, rent_amount: parseFloat(rent), rent_due_day: parseInt(document.getElementById('et-due').value), lease_start: document.getElementById('et-start').value, lease_end: document.getElementById('et-end').value });
    if (r.success) { showToast('Tenant updated!'); closeModal('modal-edit-tenant'); loadTenants(); }
    else showToast(r.error || 'Error', false);
  } catch(e) {}
}

async function deactivateTenant(id) {
  if (!confirm('Mark this tenant as moved out?')) return;
  try {
    var r = await api('/api/tenants/deactivate/' + id, {});
    if (r.success) { showToast('Tenant deactivated'); loadTenants(); }
    else showToast(r.error || 'Error', false);
  } catch(e) {}
}

async function loadMaintenance() {
  try {
    var d = await api('/api/maintenance');
    var el = document.getElementById('maint-table');
    if (!d.length) { el.innerHTML = '<div class="empty">No maintenance tasks yet.</div>'; return; }
    el.innerHTML = '<table><tr><th>Property</th><th>Description</th><th>Tenant</th><th>Reported</th><th>Status</th><th></th></tr>' +
      d.map(function(t) { return '<tr><td>' + (t.property_name||'-') + '</td><td>' + t.description + '</td><td style="color:var(--muted)">' + (t.tenant_name||'-') + '</td><td style="color:var(--muted)">' + t.date_reported + '</td><td><span class="badge ' + (t.status==='open'?'badge-red':'badge-green') + '">' + t.status + '</span></td><td>' + (t.status==='open' ? '<button class="btn btn-success btn-sm" onclick="resolveMaint('+t.id+')">Resolve</button>' : '') + '</td></tr>'; }).join('') + '</table>';
  } catch(e) {}
}

async function addMaintenance() {
  var prop = document.getElementById('m-prop').value;
  var desc = document.getElementById('m-desc').value.trim();
  if (!prop || !desc) { showToast('Property and description are required', false); return; }
  try {
    var r = await api('/api/maintenance/add', { property_id: parseInt(prop), description: desc });
    if (r.success) { showToast('Maintenance task added!'); closeModal('modal-add-maint'); document.getElementById('m-prop').value = ''; document.getElementById('m-desc').value = ''; loadMaintenance(); }
    else showToast(r.error || 'Error', false);
  } catch(e) {}
}

async function resolveMaint(id) {
  try {
    var r = await api('/api/maintenance/resolve/' + id, {});
    if (r.success) { showToast('Marked as resolved!'); loadMaintenance(); }
    else showToast(r.error || 'Error', false);
  } catch(e) {}
}

async function loadTasks() {
  try {
    var st = document.getElementById('tf-status') ? document.getElementById('tf-status').value : '';
    var pr = document.getElementById('tf-priority') ? document.getElementById('tf-priority').value : '';
    var url = '/api/tasks';
    var p = []; if (st) p.push('status='+st); if (pr) p.push('priority='+pr);
    if (p.length) url += '?' + p.join('&');
    var d = await api(url);
    var el = document.getElementById('tasks-table');
    var pc = { high: 'var(--red)', medium: 'var(--amber)', low: 'var(--muted)' };
    var sc = { todo: 'badge-purple', 'in-progress': 'badge-amber', done: 'badge-green' };
    var sl = { todo: 'To Do', 'in-progress': 'In Progress', done: 'Done' };
    if (!d.length) { el.innerHTML = '<div class="empty">No tasks yet. Click "+ Add Task" to get started!</div>'; return; }
    el.innerHTML = '<table><tr><th>Task</th><th>Property</th><th>Assignee</th><th>Priority</th><th>Status</th><th>Deadline</th><th></th></tr>' +
      d.map(function(t) { return '<tr><td><strong>' + t.title + '</strong>' + (t.notes ? '<br><span style="color:var(--muted);font-size:11px">'+t.notes+'</span>' : '') + '</td><td style="color:var(--muted)">' + (t.property_name||'-') + '</td><td style="color:var(--muted)">' + (t.assignee||'-') + '</td><td style="color:' + (pc[t.priority]||'var(--muted)') + '">' + t.priority + '</td><td><span class="badge ' + (sc[t.status]||'badge-purple') + '">' + (sl[t.status]||t.status) + '</span></td><td style="color:var(--muted)">' + (t.deadline||'-') + '</td><td style="display:flex;gap:6px"><button class="btn btn-ghost btn-sm" onclick="openEditTask('+t.id+')">Edit</button>' + (t.status!=='done' ? '<button class="btn btn-success btn-sm" onclick="completeTask('+t.id+')">Done</button>' : '') + '<button class="btn btn-danger btn-sm" onclick="deleteTask('+t.id+')">Delete</button></td></tr>'; }).join('') + '</table>';
  } catch(e) {}
}

function openAddTask() {
  document.getElementById('task-modal-title').textContent = 'Add Task';
  document.getElementById('btn-save-task').textContent = 'Add Task';
  ['tk-title','tk-assignee','tk-notes'].forEach(function(id) { document.getElementById(id).value = ''; });
  document.getElementById('tk-id').value = '';
  document.getElementById('tk-priority').value = 'medium';
  document.getElementById('tk-status').value = 'todo';
  document.getElementById('tk-category').value = 'general';
  document.getElementById('tk-deadline').value = '';
  api('/api/properties').then(function(props) {
    var s = document.getElementById('tk-prop');
    if (s) s.innerHTML = '<option value="">No property</option>' + props.map(function(p) { return '<option value="'+p.id+'">'+p.name+'</option>'; }).join('');
  }).catch(function(){});
  document.getElementById('modal-add-task').classList.add('open');
}

async function openEditTask(id) {
  try {
    var d = await api('/api/tasks/' + id);
    document.getElementById('task-modal-title').textContent = 'Edit Task';
    document.getElementById('btn-save-task').textContent = 'Save Changes';
    document.getElementById('tk-id').value       = d.id;
    document.getElementById('tk-title').value    = d.title;
    document.getElementById('tk-assignee').value = d.assignee || '';
    document.getElementById('tk-notes').value    = d.notes || '';
    document.getElementById('tk-deadline').value = d.deadline || '';
    document.getElementById('tk-priority').value = d.priority || 'medium';
    document.getElementById('tk-status').value   = d.status || 'todo';
    document.getElementById('tk-category').value = d.category || 'general';
    var props = await api('/api/properties');
    var s = document.getElementById('tk-prop');
    s.innerHTML = '<option value="">No property</option>' + props.map(function(p) { return '<option value="'+p.id+'"'+(p.id==d.property_id?' selected':'')+'>'+p.name+'</option>'; }).join('');
    document.getElementById('modal-add-task').classList.add('open');
  } catch(e) {}
}

async function saveTask() {
  var title = document.getElementById('tk-title').value.trim();
  if (!title) { showToast('Task title is required', false); return; }
  var id  = document.getElementById('tk-id').value;
  var url = id ? '/api/tasks/update/' + id : '/api/tasks/add';
  try {
    var r = await api(url, { title: title, property_id: document.getElementById('tk-prop').value || null, assignee: document.getElementById('tk-assignee').value, priority: document.getElementById('tk-priority').value, status: document.getElementById('tk-status').value, deadline: document.getElementById('tk-deadline').value, category: document.getElementById('tk-category').value, notes: document.getElementById('tk-notes').value });
    if (r.success) { showToast(id ? 'Task updated!' : 'Task added!'); closeTaskModal(); loadTasks(); }
    else showToast(r.error || 'Error', false);
  } catch(e) {}
}

function closeTaskModal() { closeModal('modal-add-task'); }

async function completeTask(id) {
  try { var r = await api('/api/tasks/update/'+id, {status:'done'}); if(r.success){showToast('Task marked done!');loadTasks();}else showToast('Error',false); } catch(e){}
}

async function deleteTask(id) {
  if (!confirm('Delete this task?')) return;
  try { var r = await api('/api/tasks/delete/'+id, {}); if(r.success){showToast('Task deleted');loadTasks();}else showToast('Error',false); } catch(e){}
}

function loadChecklistSelects() {
  api('/api/checklist-templates').then(function(ts) {
    var s = document.getElementById('cl-template');
    if(s) s.innerHTML = '<option value="">Select...</option>' + ts.map(function(t){ return '<option value="'+t.id+'">'+t.name+'</option>'; }).join('');
  }).catch(function(){});
  api('/api/properties').then(function(props) {
    var s = document.getElementById('cl-prop');
    if(s) s.innerHTML = '<option value="">No property</option>' + props.map(function(p){ return '<option value="'+p.id+'">'+p.name+'</option>'; }).join('');
  }).catch(function(){});
}

async function loadChecklists() {
  try {
    var d = await api('/api/checklists');
    var el = document.getElementById('checklists-table');
    if(!d.length){el.innerHTML='<div class="empty">No checklists yet. Click "+ Start Checklist" to begin!</div>';return;}
    el.innerHTML = d.map(function(r){
      var pct = r.total_steps>0?Math.round(r.done_steps/r.total_steps*100):0;
      return '<div style="border-bottom:1px solid var(--border);padding:16px 0"><div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px"><div><strong style="font-size:14px">'+r.name+'</strong><div style="font-size:12px;color:var(--muted);margin-top:2px">'+r.template_name+' - '+(r.property_name||'No property')+'</div></div><div style="display:flex;align-items:center;gap:8px"><span style="font-size:12px;color:var(--muted)">'+r.done_steps+'/'+r.total_steps+' steps</span><span class="badge '+(r.status==='completed'?'badge-green':'badge-amber')+'">'+r.status+'</span>'+(r.status==='active'?'<button class="btn btn-ghost btn-sm" onclick="viewChecklist('+r.id+')">Open</button>':'')+'<button class="btn btn-danger btn-sm" onclick="deleteChecklist('+r.id+')">Delete</button></div></div><div style="height:6px;background:var(--border);border-radius:4px;overflow:hidden"><div style="height:100%;width:'+pct+'%;background:'+(pct===100?'var(--green)':'var(--accent)')+';border-radius:4px;transition:.3s"></div></div></div>';
    }).join('');
  } catch(e) {}
}

async function startChecklist() {
  var name = document.getElementById('cl-name').value.trim();
  var tmpl = document.getElementById('cl-template').value;
  if(!name||!tmpl){showToast('Name and template are required',false);return;}
  try {
    var r = await api('/api/checklists/start', {name:name,template_id:parseInt(tmpl),property_id:document.getElementById('cl-prop').value||null,notes:document.getElementById('cl-notes').value.trim()});
    if(r.success){closeModal('modal-start-checklist');document.getElementById('cl-name').value='';document.getElementById('cl-notes').value='';showToast('Checklist started!');loadChecklists();viewChecklist(r.id);}
    else showToast(r.error||'Error',false);
  } catch(e){}
}

async function viewChecklist(id) {
  try {
    var d = await api('/api/checklists/' + id);
    var steps = JSON.parse(d.steps);
    var done = d.done_step_indices || [];
    document.getElementById('checklists-table').innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px"><div><h3 style="font-size:16px">'+d.name+'</h3><div style="font-size:12px;color:var(--muted)">'+d.template_name+' - '+(d.property_name||'No property')+'</div></div><button class="btn btn-ghost btn-sm" onclick="loadChecklists()">Back</button></div>' +
      steps.map(function(step,i){
        var isDone = done.indexOf(i) !== -1;
        return '<div onclick="toggleStep('+id+','+i+')" style="display:flex;align-items:center;gap:12px;padding:10px;border-radius:8px;cursor:pointer;margin-bottom:4px;background:'+(isDone?'rgba(34,197,94,0.08)':'transparent')+'"><div style="width:22px;height:22px;border-radius:50%;border:2px solid '+(isDone?'var(--green)':'var(--border)')+';background:'+(isDone?'var(--green)':'transparent')+';display:flex;align-items:center;justify-content:center;flex-shrink:0">'+(isDone?'<span style="color:#000;font-size:13px">v</span>':'')+'</div><span style="font-size:13px;'+(isDone?'text-decoration:line-through;color:var(--muted)':'')+'">'+step+'</span></div>';
      }).join('') +
      (d.status==='active'&&done.length===steps.length?'<button class="btn btn-success" style="width:100%;margin-top:12px" onclick="completeChecklist('+id+')">Mark All Complete</button>':'');
  } catch(e){}
}

async function toggleStep(runId,stepIndex) {
  try { await api('/api/checklists/toggle',{run_id:runId,step_index:stepIndex}); viewChecklist(runId); } catch(e){}
}
async function completeChecklist(id) {
  try{var r=await api('/api/checklists/complete/'+id,{});if(r.success){showToast('Checklist complete!');loadChecklists();}else showToast('Error',false);}catch(e){}
}
async function deleteChecklist(id) {
  if(!confirm('Delete this checklist?'))return;
  try{var r=await api('/api/checklists/delete/'+id,{});if(r.success){showToast('Checklist deleted');loadChecklists();}else showToast('Error',false);}catch(e){}
}

async function openAddBill() {
  document.getElementById('bill-modal-title').textContent = 'Add Bill';
  document.getElementById('btn-save-bill').textContent = 'Add Bill';
  ['bl-desc','bl-notes'].forEach(function(id){document.getElementById(id).value='';});
  document.getElementById('bl-id').value='';
  document.getElementById('bl-amount').value='';
  document.getElementById('bl-due').value='';
  document.getElementById('bl-category').value='other';
  var props = await api('/api/properties').catch(function(){return [];});
  document.getElementById('bl-prop').innerHTML='<option value="">No property</option>'+props.map(function(p){return '<option value="'+p.id+'">'+p.name+'</option>';}).join('');
  document.getElementById('modal-add-bill').classList.add('open');
}

async function openEditBill(id) {
  try {
    var bills = await api('/api/bills');
    var b = bills.find(function(x){return x.id===id;});
    if(!b)return showToast('Bill not found',false);
    document.getElementById('bill-modal-title').textContent='Edit Bill';
    document.getElementById('btn-save-bill').textContent='Save Changes';
    document.getElementById('bl-id').value=b.id;
    document.getElementById('bl-desc').value=b.description;
    document.getElementById('bl-amount').value=b.amount;
    document.getElementById('bl-due').value=b.due_date||'';
    document.getElementById('bl-notes').value=b.notes||'';
    document.getElementById('bl-category').value=b.category||'other';
    var props=await api('/api/properties');
    document.getElementById('bl-prop').innerHTML='<option value="">No property</option>'+props.map(function(p){return '<option value="'+p.id+'"'+(p.id==b.property_id?' selected':'')+'>'+p.name+'</option>';}).join('');
    document.getElementById('modal-add-bill').classList.add('open');
  } catch(e){}
}

async function saveBill() {
  var desc=document.getElementById('bl-desc').value.trim();
  if(!desc){showToast('Description is required',false);return;}
  var id=document.getElementById('bl-id').value;
  var url=id?'/api/bills/update/'+id:'/api/bills/add';
  try {
    var r=await api(url,{description:desc,property_id:document.getElementById('bl-prop').value||null,amount:parseFloat(document.getElementById('bl-amount').value)||0,due_date:document.getElementById('bl-due').value,category:document.getElementById('bl-category').value,notes:document.getElementById('bl-notes').value.trim()});
    if(r.success){showToast(id?'Bill updated!':'Bill added!');closeModal('modal-add-bill');loadBills();}
    else showToast(r.error||'Error',false);
  } catch(e){}
}

async function loadBills() {
  try {
    var sf=document.getElementById('bf-status')?document.getElementById('bf-status').value:'';
    var d=await api('/api/bills'+(sf?'?status='+sf:''));
    var el=document.getElementById('bills-table');
    if(!d.length){el.innerHTML='<div class="empty">No bills yet. Click "+ Add Bill" to track expenses!</div>';return;}
    var tot=d.reduce(function(s,b){return s+(b.status==='unpaid'?b.amount:0);},0);
    el.innerHTML='<div style="margin-bottom:12px;font-size:13px;color:var(--muted)">Total unpaid: <strong style="color:var(--red)">PHP '+tot.toLocaleString('en-US',{minimumFractionDigits:2})+'</strong></div>' +
      '<table><tr><th>Description</th><th>Property</th><th>Category</th><th>Amount</th><th>Due Date</th><th>Status</th><th></th></tr>' +
      d.map(function(b){return '<tr><td><strong>'+b.description+'</strong>'+(b.notes?'<br><span style="color:var(--muted);font-size:11px">'+b.notes+'</span>':'')+'</td><td style="color:var(--muted)">'+(b.property_name||'-')+'</td><td style="color:var(--muted);text-transform:capitalize">'+b.category+'</td><td>PHP '+Number(b.amount).toLocaleString()+'</td><td style="color:var(--muted)">'+(b.due_date||'-')+'</td><td><span class="badge '+(b.status==='paid'?'badge-green':'badge-red')+'">'+b.status+'</span></td><td style="display:flex;gap:6px">'+(b.status==='unpaid'?'<button class="btn btn-success btn-sm" onclick="markBillPaid('+b.id+')">Paid</button>':'')+'<button class="btn btn-ghost btn-sm" onclick="openEditBill('+b.id+')">Edit</button><button class="btn btn-danger btn-sm" onclick="deleteBill('+b.id+')">Delete</button></td></tr>';}).join('') +
      '</table>';
  } catch(e){}
}

async function markBillPaid(id){
  try{var r=await api('/api/bills/paid/'+id,{});if(r.success){showToast('Bill marked as paid!');loadBills();}else showToast('Error',false);}catch(e){}
}
async function deleteBill(id){
  if(!confirm('Delete this bill?'))return;
  try{var r=await api('/api/bills/delete/'+id,{});if(r.success){showToast('Bill deleted');loadBills();}else showToast('Error',false);}catch(e){}
}

function loadPropertySelects() {
  api('/api/properties').then(function(props) {
    ['t-prop','m-prop'].forEach(function(id) {
      var s = document.getElementById(id);
      if (s) s.innerHTML = '<option value="">Select property...</option>' + props.map(function(p){ return '<option value="'+p.id+'">'+p.name+'</option>'; }).join('');
    });
  }).catch(function(e){ showToast('Could not load properties: ' + e.message, false); });
}

// Init
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
                "AND DATE(lease_end) <= DATE('now', '+90 days') AND DATE(lease_end) >= DATE('now') "
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
        conn = get_conn()
        conn.execute("INSERT INTO properties (name, address, unit, notes) VALUES (?, ?, ?, ?)",
                     (d["name"], d["address"], d.get("unit"), d.get("notes")))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/properties/delete/<int:pid>", methods=["POST"])
def api_delete_property(pid):
    try:
        conn = get_conn()
        conn.execute("DELETE FROM properties WHERE id=?", (pid,))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/properties/update/<int:pid>", methods=["POST"])
def api_update_property(pid):
    try:
        d = request.json
        conn = get_conn()
        conn.execute("UPDATE properties SET name=?, address=?, unit=?, notes=? WHERE id=?",
                     (d["name"], d["address"], d.get("unit"), d.get("notes"), pid))
        conn.commit(); conn.close()
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
        conn = get_conn()
        conn.execute(
            "INSERT INTO tenants (full_name, property_id, email, phone, rent_amount, rent_due_day, lease_start, lease_end) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (d["full_name"], d["property_id"], d["email"], d.get("phone"),
             d["rent_amount"], d["rent_due_day"], d.get("lease_start"), d.get("lease_end")))
        conn.commit(); conn.close()
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
            (d["full_name"], d["property_id"], d["email"], d.get("phone"),
             d["rent_amount"], d["rent_due_day"], d.get("lease_start"), d.get("lease_end"), tid))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/tenants/deactivate/<int:tid>", methods=["POST"])
def api_deactivate_tenant(tid):
    try:
        conn = get_conn()
        conn.execute("UPDATE tenants SET is_active=0 WHERE id=?", (tid,))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/maintenance")
def api_maintenance():
    try:
        conn = get_conn()
        rows = conn.execute(
            "SELECT m.*, p.name as property_name, t.full_name as tenant_name "
            "FROM maintenance m LEFT JOIN properties p ON m.property_id=p.id "
            "LEFT JOIN tenants t ON m.tenant_id=t.id ORDER BY m.id DESC"
        ).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/maintenance/add", methods=["POST"])
def api_add_maintenance():
    try:
        d = request.json
        conn = get_conn()
        t = conn.execute("SELECT id FROM tenants WHERE property_id=? AND is_active=1 LIMIT 1", (d["property_id"],)).fetchone()
        conn.execute(
            "INSERT INTO maintenance (property_id, tenant_id, description, date_reported) VALUES (?, ?, ?, ?)",
            (d["property_id"], t["id"] if t else None, d["description"], date.today().isoformat()))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/maintenance/resolve/<int:mid>", methods=["POST"])
def api_resolve_maintenance(mid):
    try:
        conn = get_conn()
        conn.execute("UPDATE maintenance SET status='resolved', date_resolved=? WHERE id=?", (date.today().isoformat(), mid))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

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
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        conn.close()
        return jsonify(dict(row) if row else {})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tasks/add", methods=["POST"])
def api_add_task():
    try:
        d = request.json
        conn = get_conn()
        conn.execute(
            "INSERT INTO tasks (property_id, title, assignee, priority, status, deadline, category, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (d.get("property_id"), d["title"], d.get("assignee"), d.get("priority","medium"),
             d.get("status","todo"), d.get("deadline"), d.get("category","general"), d.get("notes")))
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
            (d.get("property_id", task["property_id"]), d.get("title", task["title"]),
             d.get("assignee", task["assignee"]), d.get("priority", task["priority"]),
             d.get("status", task["status"]), d.get("deadline", task["deadline"]),
             d.get("category", task["category"]), d.get("notes", task["notes"]), tid))
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
            "SELECT r.*, t.name as template_name, p.name as property_name, "
            "(SELECT COUNT(*) FROM checklist_steps_done WHERE run_id=r.id) as done_steps,"
            "(SELECT json_array_length(t2.steps) FROM checklist_templates t2 WHERE t2.id=r.template_id) as total_steps "
            "FROM checklist_runs r LEFT JOIN checklist_templates t ON r.template_id=t.id "
            "LEFT JOIN properties p ON r.property_id=p.id ORDER BY r.id DESC"
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
        d = dict(row)
        d["done_step_indices"] = [r["step_index"] for r in done]
        return jsonify(d)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/checklists/start", methods=["POST"])
def api_start_checklist():
    try:
        d    = request.json
        conn = get_conn()
        cur  = conn.execute(
            "INSERT INTO checklist_runs (template_id, property_id, name, notes) VALUES (?, ?, ?, ?)",
            (d["template_id"], d.get("property_id"), d["name"], d.get("notes")))
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
            (d["run_id"], d["step_index"])).fetchone()
        if ex:
            conn.execute("DELETE FROM checklist_steps_done WHERE run_id=? AND step_index=?", (d["run_id"], d["step_index"]))
        else:
            conn.execute("INSERT INTO checklist_steps_done (run_id, step_index) VALUES (?, ?)", (d["run_id"], d["step_index"]))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/checklists/complete/<int:rid>", methods=["POST"])
def api_complete_checklist(rid):
    try:
        conn = get_conn()
        conn.execute("UPDATE checklist_runs SET status='completed', completed_at=? WHERE id=?",
                     (date.today().isoformat(), rid))
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
        conn = get_conn()
        conn.execute(
            "INSERT INTO bills (property_id, description, amount, due_date, category, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (d.get("property_id"), d["description"], d.get("amount", 0),
             d.get("due_date"), d.get("category","other"), d.get("notes")))
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
             d.get("due_date"), d.get("category","other"), d.get("notes"), bid))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/bills/paid/<int:bid>", methods=["POST"])
def api_mark_bill_paid(bid):
    try:
        conn = get_conn()
        conn.execute("UPDATE bills SET status='paid', paid_date=? WHERE id=?", (date.today().isoformat(), bid))
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

setup_database()
seed_templates()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
