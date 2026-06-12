from flask import Flask, g, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
import sqlite3
import os
import pandas as pd
import bcrypt
from datetime import datetime, timedelta

from workflow_service import (
    ALLOWED_RECORD_TABLES,
    create_approval_request,
    advance_approval,
    reopen_transaction,
    resubmit_record,
    can_maker_edit,
    can_user_edit,
    get_edit_role_for_user,
    get_approval_request,
    get_pending_counts,
    get_pending_items,
    get_workflow_queue,
    get_workflow_for_module,
    seed_workflow_master,
    migrate_workflow_statuses,
    sync_workflow_designations,
    seed_demo_users,
    status_display,
    display_status_from_workflow,
    display_status,
    maker_status_message,
    get_dashboard_counters,
    get_approval_summary,
    get_workflow_audit_report,
    get_workflow_access_for_designation,
    get_workflow_access_label,
    user_workflow_capabilities,
    get_user_workflow_role,
    is_admin_role,
    get_recent_activities,
    get_approval_history,
    get_notifications,
    mark_notifications_read,
    WORKFLOW_STATUS,
    RECORD_PENDING_CHECKER,
    RECORD_PENDING_APPROVAL,
    RECORD_APPROVED,
    RECORD_REJECTED_CHECKER,
    RECORD_REJECTED_APPROVER,
)

APP_VERSION = "1.0.0"

BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def is_bcrypt_hash(stored_password):
    if not stored_password:
        return False
    return str(stored_password).startswith(BCRYPT_PREFIXES)


def verify_password(stored_password, provided_password):
    if stored_password is None or provided_password is None:
        return False
    stored = str(stored_password)
    provided = str(provided_password)
    if is_bcrypt_hash(stored):
        try:
            return bcrypt.checkpw(provided.encode("utf-8"), stored.encode("utf-8"))
        except (ValueError, TypeError):
            return False
    return stored == provided


def _is_truthy(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in ("1", "true", "yes", "y")


def user_is_active(user_row):
    if user_row is None:
        return False
    keys = user_row.keys()
    if "is_disabled" in keys or "account_locked" in keys:
        disabled = _is_truthy(user_row["is_disabled"]) if "is_disabled" in keys else False
        locked = _is_truthy(user_row["account_locked"]) if "account_locked" in keys else False
        return not disabled and not locked
    if "status" in keys:
        return str(user_row["status"] or "").strip().lower() == "active"
    return True


def get_user_id(user_row):
    if user_row is None:
        return None
    keys = user_row.keys()
    if "id" in keys and user_row["id"] is not None:
        return user_row["id"]
    if "user_id" in keys:
        return user_row["user_id"]
    return None


def _row_val(user_row, key, default=""):
    if key not in user_row.keys():
        return default
    val = user_row[key]
    return val if val is not None else default


def get_user_display_name(user_row):
    return (
        _row_val(user_row, "employee_name")
        or _row_val(user_row, "full_name")
        or _row_val(user_row, "username")
    )


def authenticate_user(db, username, password):
    user = db.execute(
        "SELECT * FROM users WHERE username=?",
        (username.strip(),),
    ).fetchone()
    if not user or not user_is_active(user):
        return None
    if not verify_password(user["password"], password):
        return None
    return user


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "maxek.db")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
PHOTOS_DIR = os.path.join(BASE_DIR, "static", "photos")
UPLOADS_DIR = os.path.join(BASE_DIR, "static", "uploads")
STAFF_DOCS_DIR = os.path.join(UPLOADS_DIR, "staff")
WORKER_DOCS_DIR = os.path.join(UPLOADS_DIR, "workers")

os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(PHOTOS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STAFF_DOCS_DIR, exist_ok=True)
os.makedirs(WORKER_DOCS_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "change-this-secret"
app.config["TEMPLATES_AUTO_RELOAD"] = True


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def save_file(file_storage, dest_folder):
    if file_storage and file_storage.filename:
        filename = secure_filename(file_storage.filename)
        timestamp = int(datetime.utcnow().timestamp())
        saved_name = f"{timestamp}_{filename}"
        path = os.path.join(dest_folder, saved_name)
        file_storage.save(path)
        return saved_name
    return None


def generate_employee_code(db):
    rows = db.execute(
        "SELECT employee_code FROM staff WHERE employee_code LIKE 'EMP%'"
    ).fetchall()
    max_code = 100
    for row in rows:
        code = str(row["employee_code"] or "").strip().upper()
        number = code[3:]
        if number.isdigit():
            max_code = max(max_code, int(number))
    return f"EMP{max_code + 1}"


def generate_worker_code(db, worker_category, subcontractor_id=None):
    if worker_category == "Sub Contractor Staff" and subcontractor_id:
        sub = db.execute(
            "SELECT subcontractor_name FROM subcontractors WHERE id=?",
            (subcontractor_id,),
        ).fetchone()
        if sub and sub["subcontractor_name"]:
            prefix = "".join(ch for ch in sub["subcontractor_name"].upper() if ch.isalnum())[:3] or "SUB"
            rows = db.execute(
                "SELECT worker_code FROM workers WHERE subcontractor_id=? AND worker_code LIKE ?",
                (subcontractor_id, f"{prefix}%"),
            ).fetchall()
            max_code = 100
            for row in rows:
                code = str(row["worker_code"] or "").strip().upper()
                number = code[len(prefix):]
                if number.isdigit():
                    max_code = max(max_code, int(number))
            return f"{prefix}{max_code + 1}"
    rows = db.execute("SELECT worker_code FROM workers WHERE worker_code LIKE 'WRK%'").fetchall()
    max_code = 100
    for row in rows:
        code = str(row["worker_code"] or "").strip().upper()
        number = code[3:]
        if number.isdigit():
            max_code = max(max_code, int(number))
    return f"WRK{max_code + 1}"


DEFAULT_DEPARTMENTS = [
    "Head Office", "Accounts", "Site Operations", "Store", "Purchase",
    "HR & Payroll", "Projects", "Management",
]


def ensure_department_master(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS departments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_name TEXT UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)
    cols = [row[1] for row in db.execute("PRAGMA table_info(departments)").fetchall()]
    if "department_name" not in cols:
        db.execute("ALTER TABLE departments ADD COLUMN department_name TEXT")
    if "description" not in cols:
        db.execute("ALTER TABLE departments ADD COLUMN description TEXT")
    if "status" not in cols:
        db.execute("ALTER TABLE departments ADD COLUMN status TEXT DEFAULT 'Active'")
    row = db.execute("SELECT COUNT(*) AS count FROM departments").fetchone()
    if int(row["count"]) == 0:
        db.executemany(
            "INSERT INTO departments(department_name, status) VALUES(?, 'Active')",
            [(dept,) for dept in DEFAULT_DEPARTMENTS],
        )
        db.commit()


def get_departments():
    ensure_department_master(get_db())
    rows = query_db("SELECT department_name FROM departments WHERE status='Active' ORDER BY department_name")
    return [row["department_name"] for row in rows] or DEFAULT_DEPARTMENTS


def _ensure_column(db, table, column, col_type):
    cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _create_transaction_tables(cursor):
    tables = [
        """CREATE TABLE IF NOT EXISTS material_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, request_date TEXT, item_name TEXT,
            quantity REAL, unit TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS purchase_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, request_date TEXT, item_description TEXT,
            quantity REAL, estimated_cost REAL, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS payroll_records(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT, department TEXT, total_amount REAL,
            employee_count INTEGER, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker')""",
        """CREATE TABLE IF NOT EXISTS daily_timesheets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, timesheet_date TEXT, supervisor TEXT,
            total_workers INTEGER, total_hours REAL, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS project_expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, expense_date TEXT, expense_category TEXT,
            amount REAL, description TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS head_office_expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date TEXT, expense_category TEXT, amount REAL,
            department TEXT, description TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker')""",
        """CREATE TABLE IF NOT EXISTS subcontract_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, subcontractor_id INTEGER, work_description TEXT,
            contract_amount REAL, start_date TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id))""",
        """CREATE TABLE IF NOT EXISTS boq_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, boq_date TEXT, item_code TEXT, item_description TEXT,
            quantity REAL, unit TEXT, rate REAL, amount REAL, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS dpr_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, report_date TEXT, prepared_by TEXT,
            work_done TEXT, manpower_count INTEGER, material_used TEXT,
            issues TEXT, progress_percent REAL, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS manager_tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, task_date TEXT, manager_name TEXT,
            action_item TEXT, priority TEXT, target_date TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS account_transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_type TEXT, project_id INTEGER, transaction_date TEXT,
            party_name TEXT, account_head TEXT, amount REAL, payment_mode TEXT,
            reference_no TEXT, tax_percent REAL, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS leave_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_name TEXT, leave_type TEXT, from_date TEXT, to_date TEXT,
            days REAL, reason TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker')""",
        """CREATE TABLE IF NOT EXISTS store_issues(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, issue_date TEXT, item_name TEXT,
            quantity REAL, unit TEXT, issued_to TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS store_receipts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, receipt_date TEXT, item_name TEXT,
            quantity REAL, unit TEXT, supplier TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
    ]
    for sql in tables:
        cursor.execute(sql)


def init_db():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT,
            staff_name TEXT,
            mobile TEXT,
            email TEXT,
            department TEXT,
            designation TEXT,
            salary_type TEXT,
            salary_amount REAL,
            ot_applicable TEXT,
            working_hours REAL,
            joining_date TEXT,
            photo TEXT,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subcontractors(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcontractor_name TEXT,
            company_name TEXT,
            mobile TEXT,
            email TEXT,
            address TEXT,
            work_type TEXT,
            payment_mode TEXT,
            working_hours REAL,
            gst_number TEXT,
            id_proof TEXT,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_name TEXT UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            company_name TEXT,
            mobile TEXT,
            email TEXT,
            address TEXT,
            gst_number TEXT,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            client_id INTEGER,
            location TEXT,
            start_date TEXT,
            end_date TEXT,
            project_manager TEXT,
            budget REAL,
            status TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_code TEXT,
            worker_name TEXT,
            mobile TEXT,
            aadhaar_number TEXT,
            photo TEXT,
            worker_category TEXT,
            designation TEXT,
            salary_type TEXT,
            salary_amount REAL,
            ot_applicable TEXT,
            working_hours REAL,
            subcontractor_id INTEGER,
            project_id INTEGER,
            joining_date TEXT,
            status TEXT,
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER,
            project_id INTEGER,
            attendance_date TEXT,
            in_time TEXT,
            out_time TEXT,
            break_hours REAL,
            total_hours REAL,
            ot_hours REAL,
            status TEXT,
            FOREIGN KEY(worker_id) REFERENCES workers(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS petty_cash(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            expense_date TEXT,
            expense_type TEXT,
            amount REAL,
            payment_mode TEXT,
            remarks TEXT,
            created_by TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS salary(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER,
            month TEXT,
            total_days INTEGER,
            normal_wage REAL,
            ot_amount REAL,
            advance_deduction REAL,
            final_salary REAL,
            payment_status TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(worker_id) REFERENCES workers(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS designations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            designation_name TEXT UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_name TEXT NOT NULL,
            module_id TEXT UNIQUE NOT NULL,
            workflow_role_mapping TEXT,
            maker_designation_id INTEGER,
            checker_designation_id INTEGER,
            approver_designation_id INTEGER,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY(maker_designation_id) REFERENCES designations(id),
            FOREIGN KEY(checker_designation_id) REFERENCES designations(id),
            FOREIGN KEY(approver_designation_id) REFERENCES designations(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            record_table TEXT NOT NULL,
            current_stage TEXT DEFAULT 'checker',
            workflow_status TEXT DEFAULT 'pending_checker',
            maker_user_id INTEGER,
            checker_user_id INTEGER,
            approver_user_id INTEGER,
            maker_action_at TEXT,
            checker_action_at TEXT,
            approver_action_at TEXT,
            rejection_reason TEXT,
            created_by TEXT,
            created_at TEXT,
            UNIQUE(module_id, record_id, record_table)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            notification_type TEXT,
            module_id TEXT,
            record_id INTEGER,
            record_table TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            approval_request_id INTEGER,
            module_id TEXT,
            record_id INTEGER,
            record_table TEXT,
            action TEXT,
            actor_user_id INTEGER,
            actor_username TEXT,
            remarks TEXT,
            created_at TEXT,
            FOREIGN KEY(approval_request_id) REFERENCES approval_requests(id)
        )
    """)
    _ensure_column(db, "users", "designation_id", "INTEGER")
    _ensure_column(db, "users", "workflow_role", "TEXT")
    _ensure_column(db, "users", "reporting_manager", "TEXT")
    _ensure_column(db, "users", "employee_name", "TEXT")
    _ensure_column(db, "users", "department", "TEXT")
    _ensure_column(db, "staff", "designation_id", "INTEGER")
    _ensure_column(db, "staff", "reporting_manager", "TEXT")
    _ensure_column(db, "staff", "workflow_role", "TEXT")
    _ensure_column(db, "staff", "aadhaar_number", "TEXT")
    _ensure_column(db, "staff", "pan_number", "TEXT")
    _ensure_column(db, "staff", "bank_account", "TEXT")
    _ensure_column(db, "staff", "bank_name", "TEXT")
    _ensure_column(db, "staff", "ifsc_code", "TEXT")
    _ensure_column(db, "staff", "branch_name", "TEXT")
    _ensure_column(db, "staff", "id_proof", "TEXT")
    _ensure_column(db, "staff", "aadhaar_document", "TEXT")
    _ensure_column(db, "staff", "pan_document", "TEXT")
    _ensure_column(db, "workers", "worker_code", "TEXT")
    _ensure_column(db, "workers", "bank_account", "TEXT")
    _ensure_column(db, "workers", "bank_name", "TEXT")
    _ensure_column(db, "workers", "ifsc_code", "TEXT")
    _ensure_column(db, "workers", "branch_name", "TEXT")
    _ensure_column(db, "workers", "pan_number", "TEXT")
    _ensure_column(db, "workers", "id_proof", "TEXT")
    _ensure_column(db, "workers", "aadhaar_document", "TEXT")
    _ensure_column(db, "workers", "pan_document", "TEXT")
    _ensure_column(db, "approval_requests", "checker_comment", "TEXT")
    _ensure_column(db, "approval_requests", "approver_comment", "TEXT")
    _ensure_column(db, "petty_cash", "approval_status", "TEXT DEFAULT 'Pending Checker'")
    _ensure_column(db, "attendance", "approval_status", "TEXT DEFAULT 'Pending Checker'")
    _ensure_column(db, "salary", "approval_status", "TEXT DEFAULT 'Pending Checker'")
    _create_transaction_tables(cursor)
    db.commit()
    ensure_department_master(db)
    seed_workflow_master(db)
    migrate_workflow_statuses(db)
    sync_workflow_designations(db)
    db.commit()
    cursor.execute("SELECT * FROM users LIMIT 1")
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users(username, password, role, status, employee_name, department, workflow_role) "
            "VALUES(?,?,?,?,?,?,?)",
            ("admin", "admin", "Admin", "Active", "System Administrator", "Head Office", "Administrator"),
        )
        db.commit()
    if not os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        seed_demo_users(db)
        db.commit()


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def login_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def is_admin_user():
    if not session.get("user_id"):
        return False
    wf = (session.get("workflow_role") or "").lower()
    role = (session.get("role") or "").lower()
    if wf == "administrator" or role in ("admin", "administrator"):
        return True
    return is_admin_role(get_db(), session.get("user_id"), session.get("role"))


def admin_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        if not is_admin_user():
            flash("Administrator access required.")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)

    return wrapper


MODULE_ROUTES = {
    "petty_cash": "petty_cash",
    "material_request": "material_request",
    "purchase_request": "purchase_request",
    "payroll": "salary",
    "daily_timesheet": "attendance",
    "project_expenses": "project_expenses",
    "head_office_expenses": "head_office_expenses",
    "subcontract": "subcontract_request",
    "boq": "boq_management",
    "dpr": "dpr_entry",
    "manager_tool": "manager_tool",
    "account_receipt": "account_receipts",
    "account_payment": "account_payments",
    "account_gst": "account_gst",
    "account_tds": "account_tds",
    "leave_request": "leave_request",
    "store_issue": "store_issue",
    "store_receipt": "store_receipt",
}


def _workflow_view_context(module_id, record_id, record_table, approval_status):
    db = get_db()
    user_id = session.get("user_id")
    admin = is_admin_user()
    history = get_approval_history(db, module_id, record_id, record_table)
    edit_role = get_edit_role_for_user(db, user_id, module_id, approval_status, admin)
    req = get_approval_request(db, module_id, record_id, record_table)
    return {
        "history": history,
        "edit_role": edit_role,
        "can_reopen": admin and approval_status == RECORD_APPROVED and req,
        "approval_id": req["id"] if req else None,
    }


def _enrich_approval_items(db, items):
    enriched = []
    for item in items:
        row = dict(item)
        table = row.get("record_table")
        if table in ALLOWED_RECORD_TABLES:
            rec = db.execute(
                f"SELECT approval_status FROM {table} WHERE id=?",
                (row["record_id"],),
            ).fetchone()
            row["record_status"] = rec["approval_status"] if rec else WORKFLOW_STATUS.get(
                row.get("workflow_status"), row.get("workflow_status")
            )
        else:
            row["record_status"] = WORKFLOW_STATUS.get(
                row.get("workflow_status"), row.get("workflow_status")
            )
        row["history"] = get_approval_history(
            db, row.get("module_id"), row["record_id"], row.get("record_table")
        )
        enriched.append(row)
    return enriched


def _history_for_record(module_id, record_id, record_table):
    return get_approval_history(get_db(), module_id, record_id, record_table)


NAV_GROUPS = [
    {
        "label": "Dashboard",
        "icon": "fa-gauge-high",
        "items": [
            {"endpoint": "dashboard", "label": "Overview", "active_endpoints": ["dashboard"]},
            {"endpoint": "dashboard_choice_b", "label": "Operations View", "active_endpoints": ["dashboard_choice_b"]},
        ],
    },
    {
        "label": "Projects",
        "icon": "fa-layer-group",
        "items": [
            {"endpoint": "projects", "label": "Project List", "active_endpoints": ["projects"]},
            {"endpoint": "boq_management", "label": "BOQ", "active_endpoints": ["boq_management"]},
            {"endpoint": "dpr_entry", "label": "Progress Monitoring", "active_endpoints": ["dpr_entry"]},
            {"endpoint": "project_expenses", "label": "Project Costing", "active_endpoints": ["project_expenses"]},
            {"endpoint": "reports", "label": "Project Reports", "active_endpoints": ["reports", "workflow_audit_report"]},
        ],
    },
    {
        "label": "Workforce",
        "icon": "fa-users",
        "items": [
            {"endpoint": "staff", "label": "Employees", "active_endpoints": ["staff"]},
            {"endpoint": "attendance", "label": "Attendance", "active_endpoints": ["attendance"]},
            {"endpoint": "timesheet", "label": "Timesheet", "active_endpoints": ["timesheet"]},
            {"endpoint": "salary", "label": "Salary Processing", "active_endpoints": ["salary"]},
        ],
    },
    {
        "label": "Subcontract",
        "icon": "fa-people-group",
        "items": [
            {"endpoint": "subcontractors", "label": "Subcontractors", "active_endpoints": ["subcontractors"]},
            {"endpoint": "workers", "label": "Worker Creation", "anchor": "add-worker", "active_endpoints": ["workers"]},
            {"endpoint": "subcontract_request", "label": "Bills & Payments", "active_endpoints": ["subcontract_request"]},
        ],
    },
    {
        "label": "Store & Procurement",
        "icon": "fa-warehouse",
        "items": [
            {"endpoint": "store", "label": "Store Dashboard", "active_endpoints": ["store"]},
            {"endpoint": "material_request", "label": "Material Request", "active_endpoints": ["material_request"]},
            {"endpoint": "purchase_request", "label": "Purchase Request", "active_endpoints": ["purchase_request"]},
            {"endpoint": "purchase", "label": "Purchase Order", "active_endpoints": ["purchase"]},
            {"endpoint": "store_receipt", "label": "Delivery / GRN", "active_endpoints": ["store_receipt"]},
            {"endpoint": "store_issue", "label": "Store Issue", "active_endpoints": ["store_issue"]},
            {"endpoint": "inventory", "label": "Inventory Stock", "active_endpoints": ["inventory"]},
        ],
    },
    {
        "label": "Accounts",
        "icon": "fa-landmark",
        "items": [
            {"endpoint": "petty_cash", "label": "Petty Cash", "active_endpoints": ["petty_cash"]},
            {"endpoint": "head_office_expenses", "label": "Daily Expenses", "active_endpoints": ["head_office_expenses", "project_expenses"]},
            {"endpoint": "account_receipts", "label": "Receipts", "active_endpoints": ["account_receipts"]},
            {"endpoint": "account_payments", "label": "Payments", "active_endpoints": ["account_payments"]},
            {"endpoint": "cash_book", "label": "Cash Book", "active_endpoints": ["cash_book"]},
            {"endpoint": "bank_book", "label": "Bank Book", "active_endpoints": ["bank_book"]},
            {"endpoint": "account_gst", "label": "GST", "active_endpoints": ["account_gst"]},
            {"endpoint": "account_tds", "label": "TDS", "active_endpoints": ["account_tds"]},
            {"endpoint": "ledger", "label": "Ledger", "active_endpoints": ["ledger"]},
            {"endpoint": "reports", "label": "Accounts Reports", "active_endpoints": ["reports"]},
        ],
    },
    {
        "label": "Approvals",
        "icon": "fa-clipboard-check",
        "items": [
            {"endpoint": "approvals", "label": "Approval Center", "active_endpoints": ["approvals", "approval_action"]},
        ],
    },
    {
        "label": "Settings",
        "icon": "fa-gear",
        "items": [
            {"endpoint": "user_settings", "label": "Users", "active_endpoints": ["user_settings"]},
            {"endpoint": "settings", "label": "Company & Departments", "active_endpoints": ["settings"]},
            {"endpoint": "workflow_settings", "label": "Workflow Settings", "active_endpoints": ["workflow_settings", "workflow_matrix"]},
        ],
    },
]

NAV_ITEMS = [
    item
    for group in NAV_GROUPS
    for item in (
        group.get("items")
        or [
            {
                "endpoint": group.get("endpoint"),
                "label": group["label"],
                "icon": group["icon"],
                "active_endpoints": group.get("active_endpoints", []),
            }
        ]
    )
]


def active_nav_group(endpoint):
    for group in NAV_GROUPS:
        for item in group.get("items", []):
            if endpoint in item.get("active_endpoints", []):
                return group
        if endpoint in group.get("active_endpoints", []):
            return group
    return NAV_GROUPS[0]


def get_approval_widgets():
    if not session.get("user_id"):
        return {"maker": 0, "checker": 0, "approver": 0}
    return get_pending_counts(get_db(), session.get("user_id"), is_admin_user())


@app.context_processor
def inject_maxek_layout():
    if not session.get("user_id"):
        return {}
    username = session.get("username") or "Administrator"
    user_id = session.get("user_id")
    db = get_db()
    widgets = get_pending_counts(db, user_id, is_admin_user())
    dashboard_counters = get_dashboard_counters(db, user_id, username, is_admin_user())
    approval_summary = get_approval_summary(db)
    workflow_caps = user_workflow_capabilities(db, user_id, is_admin_user())
    notifs = get_notifications(db, user_id, limit=10, unread_only=True)
    approval_total = widgets["maker"] + widgets["checker"] + widgets["approver"]
    current_nav_group = active_nav_group(request.endpoint)
    return {
        "nav_groups": NAV_GROUPS,
        "nav_items": NAV_ITEMS,
        "current_nav_group": current_nav_group,
        "timestamp": datetime.now().strftime("%A, %d %b %Y | %H:%M"),
        "admin_initial": username[0].upper(),
        "branches": ["Head Office", "Chennai Site", "Walajabad Unit"],
        "selected_branch": session.get("branch", "Head Office"),
        "notification_count": len(notifs) or approval_total,
        "approval_total": approval_total,
        "approval_widgets": widgets,
        "dashboard_counters": dashboard_counters,
        "approval_summary": approval_summary,
        "workflow_caps": workflow_caps,
        "user_notifications": notifs,
        "display_status": display_status,
        "maker_status_message": maker_status_message,
    }


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        remember = request.form.get("remember") == "on"
        user = authenticate_user(get_db(), username, password)
        if user:
            session.clear()
            session["user_id"] = get_user_id(user)
            session["username"] = user["username"]
            session["role"] = _row_val(user, "role")
            session["workflow_role"] = _row_val(user, "workflow_role")
            session["employee_name"] = get_user_display_name(user)
            if remember:
                session.permanent = True
                app.permanent_session_lifetime = timedelta(days=30)
            return redirect(url_for("dashboard"))
        flash("Invalid username or password, or account is inactive.")
    return render_template("login.html", app_version=APP_VERSION)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = query_db("SELECT * FROM users WHERE username=?", (username,), one=True)
        if user:
            flash("Password reset request received. Contact your system administrator.")
        else:
            flash("If that username exists, an administrator will reset your password.")
        return redirect(url_for("login"))
    return render_template("forgot_password.html", app_version=APP_VERSION)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def build_system_rows():
    rows = []
    for item in get_workflow_queue(get_db(), limit=10):
        status = item.get("workflow_status") or "pending_checker"
        status_label = display_status_from_workflow(status, "maker")
        if status in ("pending_checker", "rejected_checker"):
            priority, priority_class = "High", "high"
            action_label = "Review"
        elif status == "pending_approval":
            priority, priority_class = "Medium", "medium"
            action_label = "Approve"
        else:
            priority, priority_class = "Low", "low"
            action_label = "View"
        pill = "active" if status == "approved" else "pending"
        module_code = (item.get("module_id") or "WF").upper().replace("_", "")[:3]
        created = item.get("created_at") or "—"
        if len(created) >= 10:
            parts = created[:10].split("-")
            if len(parts) == 3:
                created = f"{parts[2]}/{parts[1]}/{parts[0]}"
        rows.append(
            {
                "ref": f"{module_code}-{item['record_id']}",
                "label": item.get("module_name") or item["module_id"],
                "date_created": created,
                "priority": priority,
                "priority_class": priority_class,
                "submitted_by": item.get("created_by") or item.get("maker_designation") or "—",
                "status": pill,
                "status_label": status_label,
                "action_url": url_for("approvals"),
                "action_label": action_label,
            }
        )
    return rows


def get_dashboard_stats(db):
    """Aggregate KPI and chart data for the home dashboard."""
    total_projects = query_db("SELECT COUNT(*) AS count FROM projects", one=True)["count"]
    active_projects = query_db(
        "SELECT COUNT(*) AS count FROM projects WHERE status='Active'", one=True
    )["count"]
    active_workers = query_db(
        "SELECT COUNT(*) AS count FROM workers WHERE status='Active'", one=True
    )["count"]
    active_staff = query_db(
        "SELECT COUNT(*) AS count FROM staff WHERE status='Active'", one=True
    )["count"]
    pending_mrs = 0
    try:
        pending_mrs = db.execute(
            "SELECT COUNT(*) AS c FROM material_requests "
            "WHERE approval_status IN ('Pending Checker', 'Pending Approval')"
        ).fetchone()["c"]
    except Exception:
        pass
    workflow_tasks = db.execute(
        "SELECT COUNT(*) AS c FROM approval_requests "
        "WHERE workflow_status NOT IN ('approved')"
    ).fetchone()["c"]

    featured = query_db(
        "SELECT project_name, location, status FROM projects "
        "WHERE status='Active' ORDER BY id DESC LIMIT 1",
        one=True,
    )
    progress_pct = 80
    if featured and total_projects:
        progress_pct = min(95, 50 + active_projects * 10)

    attendance_rows = query_db(
        "SELECT attendance_date, COUNT(*) AS cnt FROM attendance "
        "WHERE attendance_date >= date('now', '-6 days') "
        "GROUP BY attendance_date ORDER BY attendance_date ASC"
    )
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    counts_by_day = [row["cnt"] for row in attendance_rows]
    while len(counts_by_day) < 7:
        counts_by_day.append(0)
    counts_by_day = counts_by_day[-7:]
    max_cnt = max(counts_by_day) if counts_by_day else 1
    if max_cnt == 0:
        max_cnt = 1
    attendance_bars = []
    for i, label in enumerate(day_labels):
        cnt = counts_by_day[i] if i < len(counts_by_day) else 0
        attendance_bars.append(
            {
                "label": label,
                "count": cnt,
                "height": int((cnt / max_cnt) * 100) if cnt else 8,
            }
        )

    present_today = 0
    try:
        present_today = db.execute(
            "SELECT COUNT(*) AS c FROM attendance WHERE attendance_date=date('now') AND status='Present'"
        ).fetchone()["c"]
    except Exception:
        pass

    health_score = min(100, 40 + active_projects * 10 + min(active_workers, 30))
    health_segments = [
        {"label": "Product Dev", "pct": min(95, 60 + active_projects * 5), "color": "#3B82F6"},
        {"label": "Operations", "pct": min(90, 30 + active_workers), "color": "#10B981"},
        {"label": "Site Logistics", "pct": min(85, 20 + pending_mrs * 8), "color": "#F59E0B"},
    ]

    return {
        "total_projects": total_projects,
        "active_projects": active_projects,
        "active_workers": active_workers,
        "active_staff": active_staff,
        "pending_mrs": pending_mrs,
        "workflow_tasks": workflow_tasks,
        "featured_project": featured,
        "progress_pct": progress_pct,
        "attendance_bars": attendance_bars,
        "present_today": present_today or active_workers,
        "health_score": health_score,
        "health_segments": health_segments,
    }


def render_choice_b_dashboard():
    db = get_db()
    user_id = session.get("user_id")
    admin = is_admin_user()
    stats = get_dashboard_stats(db)
    counts = {
        "staff": stats["active_staff"],
        "workers": stats["active_workers"],
        "projects": stats["total_projects"],
    }
    approval_widgets = get_pending_counts(db, user_id, admin)
    system_rows = build_system_rows()
    total_pending = (
        approval_widgets["maker"]
        + approval_widgets["checker"]
        + approval_widgets["approver"]
    )
    username = session.get("username") or "Administrator"
    dashboard_counters = get_dashboard_counters(db, user_id, username, admin)
    approval_summary = get_approval_summary(db)
    recent_activities = get_recent_activities(db, limit=12)
    user_notifications = get_notifications(db, user_id, limit=8, unread_only=False)
    return render_template(
        "dashboard.html",
        counts=counts,
        stats=stats,
        approval_widgets=approval_widgets,
        dashboard_counters=dashboard_counters,
        approval_summary=approval_summary,
        recent_activities=recent_activities,
        user_notifications=user_notifications,
        system_rows=system_rows,
        alert_count=total_pending,
        welcome_name=session.get("employee_name") or (
            username.title() if username.islower() else username
        ),
    )


@app.route("/dashboard")
@login_required
def dashboard():
    return render_choice_b_dashboard()


@app.route("/dashboard/choice-b")
@login_required
def dashboard_choice_b():
    return render_choice_b_dashboard()


@app.route("/staff", methods=["GET", "POST"])
@login_required
def staff():
    db = get_db()
    edit_id = request.args.get("edit", type=int)
    editing_staff = None
    if edit_id:
        editing_staff = db.execute("SELECT * FROM staff WHERE id=?", (edit_id,)).fetchone()
        if not editing_staff:
            flash("Employee record not found.")
            return redirect(url_for("staff"))
    designations = query_db(
        "SELECT id, designation_name FROM designations WHERE status='Active' ORDER BY designation_name"
    )
    departments = get_departments()
    staff_list = query_db("SELECT staff_name FROM staff WHERE status='Active' ORDER BY staff_name")
    if request.method == "POST":
        staff_id = request.form.get("staff_id", "").strip()
        staff_name = request.form.get("staff_name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        email = request.form.get("email", "").strip()
        department = request.form.get("department", "").strip()
        designation_id = request.form.get("designation_id", "") or None
        reporting_manager = request.form.get("reporting_manager", "").strip()
        workflow_role = request.form.get("workflow_role", "").strip()
        salary_type = request.form.get("salary_type", "").strip()
        salary_amount = request.form.get("salary_amount", "0").strip()
        ot_applicable = request.form.get("ot_applicable", "No").strip()
        working_hours = request.form.get("working_hours", "0").strip()
        joining_date = request.form.get("joining_date", "").strip()
        status = request.form.get("status", "Active").strip()
        aadhaar_number = request.form.get("aadhaar_number", "").strip()
        pan_number = request.form.get("pan_number", "").strip()
        bank_account = request.form.get("bank_account", "").strip()
        bank_name = request.form.get("bank_name", "").strip()
        ifsc_code = request.form.get("ifsc_code", "").strip()
        branch_name = request.form.get("branch_name", "").strip()
        existing_staff = None
        if staff_id:
            existing_staff = db.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
            if not existing_staff:
                flash("Employee record not found.")
                return redirect(url_for("staff"))
        photo = save_file(request.files.get("photo"), PHOTOS_DIR)
        id_proof = save_file(request.files.get("id_proof"), STAFF_DOCS_DIR)
        aadhaar_document = save_file(request.files.get("aadhaar_document"), STAFF_DOCS_DIR)
        pan_document = save_file(request.files.get("pan_document"), STAFF_DOCS_DIR)
        if existing_staff:
            photo = photo or existing_staff["photo"]
            id_proof = id_proof or existing_staff["id_proof"]
            aadhaar_document = aadhaar_document or existing_staff["aadhaar_document"]
            pan_document = pan_document or existing_staff["pan_document"]
        employee_code = existing_staff["employee_code"] if existing_staff else generate_employee_code(db)
        designation_name = ""
        if designation_id:
            drow = db.execute(
                "SELECT designation_name FROM designations WHERE id=?", (designation_id,)
            ).fetchone()
            designation_name = drow["designation_name"] if drow else ""
        try:
            salary_amount_val = float(salary_amount or 0)
            working_hours_val = float(working_hours or 0)
        except ValueError:
            flash("Enter valid numeric values for salary and working hours.")
            return redirect(url_for("staff"))
        values = (
            employee_code, staff_name, mobile, email, department, designation_name,
            designation_id, reporting_manager, workflow_role or None,
            salary_type, salary_amount_val, ot_applicable, working_hours_val,
            joining_date, photo, status, aadhaar_number, pan_number,
            bank_account, bank_name, ifsc_code, branch_name,
            id_proof, aadhaar_document, pan_document,
        )
        if existing_staff:
            db.execute(
                "UPDATE staff SET employee_code=?, staff_name=?, mobile=?, email=?, department=?, "
                "designation=?, designation_id=?, reporting_manager=?, workflow_role=?, salary_type=?, "
                "salary_amount=?, ot_applicable=?, working_hours=?, joining_date=?, photo=?, status=?, "
                "aadhaar_number=?, pan_number=?, bank_account=?, bank_name=?, ifsc_code=?, "
                "branch_name=?, id_proof=?, aadhaar_document=?, pan_document=? WHERE id=?",
                values + (staff_id,),
            )
            flash(f"Employee updated. Employee Code: {employee_code}")
        else:
            db.execute(
                "INSERT INTO staff(employee_code, staff_name, mobile, email, department, designation, "
                "designation_id, reporting_manager, workflow_role, salary_type, salary_amount, "
                "ot_applicable, working_hours, joining_date, photo, status, aadhaar_number, pan_number, "
                "bank_account, bank_name, ifsc_code, branch_name, id_proof, aadhaar_document, pan_document) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            flash(f"Employee saved. Employee Code: {employee_code}")
        db.commit()
        return redirect(url_for("staff"))
    rows_raw = query_db(
        "SELECT s.*, d.designation_name AS designation_label "
        "FROM staff s LEFT JOIN designations d ON s.designation_id = d.id "
        "ORDER BY s.id DESC"
    )
    rows = []
    for r in rows_raw:
        row = dict(r)
        row["workflow_access"] = get_workflow_access_label(
            db, row.get("designation_id"), row.get("workflow_role")
        )
        if row.get("workflow_role"):
            row["workflow_access"] = row["workflow_role"]
        elif row.get("designation_id"):
            row["workflow_access"] = get_workflow_access_for_designation(
                db, row["designation_id"]
            )
        row["display_designation"] = row.get("designation_label") or row.get("designation") or "—"
        rows.append(row)
    return render_template(
        "staff.html",
        rows=rows,
        designations=designations,
        departments=departments,
        staff_list=staff_list,
        next_employee_code=generate_employee_code(db),
        editing_staff=editing_staff,
    )


@app.route("/subcontractors", methods=["GET", "POST"])
@login_required
def subcontractors():
    if request.method == "POST":
        subcontractor_name = request.form.get("subcontractor_name", "").strip()
        company_name = request.form.get("company_name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        work_type = request.form.get("work_type", "").strip()
        payment_mode = request.form.get("payment_mode", "").strip()
        working_hours = request.form.get("working_hours", "0").strip()
        gst_number = request.form.get("gst_number", "").strip()
        status = request.form.get("status", "Active").strip()
        id_proof_file = request.files.get("id_proof")
        id_proof = save_file(id_proof_file, UPLOADS_DIR)
        try:
            working_hours_val = float(working_hours or 0)
        except ValueError:
            flash("Please enter a valid number for working hours.")
            return redirect(url_for("subcontractors"))
        db = get_db()
        db.execute(
            "INSERT INTO subcontractors(subcontractor_name, company_name, mobile, email, address, work_type, payment_mode, working_hours, gst_number, id_proof, status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (subcontractor_name, company_name, mobile, email, address, work_type, payment_mode, working_hours_val, gst_number, id_proof, status)
        )
        db.commit()
        flash("Subcontractor saved.")
        return redirect(url_for("subcontractors"))
    rows = query_db("SELECT * FROM subcontractors ORDER BY id DESC")
    return render_template("subcontractors.html", rows=rows)


@app.route("/clients", methods=["GET", "POST"])
@login_required
def clients():
    if request.method == "POST":
        _create_client_from_form()
        flash("Client saved.")
        return redirect(url_for("clients"))
    rows = query_db("SELECT * FROM clients ORDER BY id DESC")
    return render_template("clients.html", rows=rows)


def _create_client_from_form():
    client_name = request.form.get("client_name", "").strip()
    company_name = request.form.get("company_name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    email = request.form.get("email", "").strip()
    address = request.form.get("address", "").strip()
    gst_number = request.form.get("gst_number", "").strip()
    status = request.form.get("status", "Active").strip()
    db = get_db()
    db.execute(
        "INSERT INTO clients(client_name, company_name, mobile, email, address, gst_number, status) VALUES(?,?,?,?,?,?,?)",
        (client_name, company_name, mobile, email, address, gst_number, status)
    )
    db.commit()


@app.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    clients = query_db("SELECT id, client_name FROM clients ORDER BY client_name")
    if request.method == "POST":
        if request.form.get("form_action") == "create_client":
            _create_client_from_form()
            flash("Client saved. Select it in the project form.")
            return redirect(url_for("projects") + "#add-project")
        project_name = request.form.get("project_name", "").strip()
        client_id = request.form.get("client_id", "")
        location = request.form.get("location", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        project_manager = request.form.get("project_manager", "").strip()
        budget = request.form.get("budget", "0").strip()
        status = request.form.get("status", "Active").strip()
        try:
            budget_val = float(budget or 0)
        except ValueError:
            flash("Enter a valid budget amount.")
            return redirect(url_for("projects"))
        db = get_db()
        db.execute(
            "INSERT INTO projects(project_name, client_id, location, start_date, end_date, project_manager, budget, status) VALUES(?,?,?,?,?,?,?,?)",
            (project_name, client_id or None, location, start_date, end_date, project_manager, budget_val, status)
        )
        db.commit()
        flash("Project saved.")
        return redirect(url_for("projects"))
    rows = query_db("SELECT p.*, c.client_name FROM projects p LEFT JOIN clients c ON p.client_id = c.id ORDER BY p.id DESC")
    return render_template("projects.html", rows=rows, clients=clients)


@app.route("/workers", methods=["GET", "POST"])
@login_required
def workers():
    subcontractors = query_db("SELECT id, subcontractor_name FROM subcontractors ORDER BY subcontractor_name")
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    if request.method == "POST":
        worker_name = request.form.get("worker_name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        aadhaar_number = request.form.get("aadhaar_number", "").strip()
        pan_number = request.form.get("pan_number", "").strip()
        bank_account = request.form.get("bank_account", "").strip()
        bank_name = request.form.get("bank_name", "").strip()
        ifsc_code = request.form.get("ifsc_code", "").strip()
        branch_name = request.form.get("branch_name", "").strip()
        worker_category = request.form.get("worker_category", "Company Staff").strip()
        designation = request.form.get("designation", "").strip()
        salary_type = request.form.get("salary_type", "").strip()
        salary_amount = request.form.get("salary_amount", "0").strip()
        ot_applicable = request.form.get("ot_applicable", "No").strip()
        working_hours = request.form.get("working_hours", "0").strip()
        subcontractor_id = request.form.get("subcontractor_id", "")
        project_id = request.form.get("project_id", "")
        joining_date = request.form.get("joining_date", "").strip()
        status = request.form.get("status", "Active").strip()
        photo_file = request.files.get("photo")
        photo = save_file(photo_file, PHOTOS_DIR)
        id_proof = save_file(request.files.get("id_proof"), WORKER_DOCS_DIR)
        aadhaar_document = save_file(request.files.get("aadhaar_document"), WORKER_DOCS_DIR)
        pan_document = save_file(request.files.get("pan_document"), WORKER_DOCS_DIR)
        try:
            salary_amount_val = float(salary_amount or 0)
            working_hours_val = float(working_hours or 0)
        except ValueError:
            flash("Enter valid numeric values for salary and working hours.")
            return redirect(url_for("workers"))
        db = get_db()
        worker_code = generate_worker_code(db, worker_category, subcontractor_id or None)
        db.execute(
            "INSERT INTO workers(worker_code, worker_name, mobile, aadhaar_number, pan_number, "
            "bank_account, bank_name, ifsc_code, branch_name, photo, id_proof, aadhaar_document, "
            "pan_document, worker_category, designation, salary_type, salary_amount, ot_applicable, "
            "working_hours, subcontractor_id, project_id, joining_date, status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                worker_code, worker_name, mobile, aadhaar_number, pan_number,
                bank_account, bank_name, ifsc_code, branch_name, photo,
                id_proof, aadhaar_document, pan_document,
                worker_category, designation, salary_type, salary_amount_val,
                ot_applicable, working_hours_val, subcontractor_id or None,
                project_id or None, joining_date, status,
            ),
        )
        db.commit()
        flash(f"Worker saved. Worker Code: {worker_code}")
        return redirect(url_for("workers"))
    rows = query_db(
        "SELECT w.*, s.subcontractor_name, p.project_name FROM workers w "
        "LEFT JOIN subcontractors s ON w.subcontractor_id = s.id "
        "LEFT JOIN projects p ON w.project_id = p.id ORDER BY w.id DESC"
    )
    db = get_db()
    subcontractor_options = []
    for item in subcontractors:
        subcontractor_options.append({
            "id": item["id"],
            "subcontractor_name": item["subcontractor_name"],
            "next_worker_code": generate_worker_code(db, "Sub Contractor Staff", item["id"]),
        })
    return render_template(
        "workers.html",
        rows=rows,
        subcontractors=subcontractor_options,
        projects=projects,
        next_worker_code=generate_worker_code(db, "Company Staff"),
    )


@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    module_id, table, endpoint = "daily_timesheet", "attendance", "attendance"
    record_sql = (
        "SELECT a.*, w.worker_name, p.project_name FROM attendance a "
        "LEFT JOIN workers w ON a.worker_id = w.id "
        "LEFT JOIN projects p ON a.project_id = p.id WHERE a.id=?"
    )
    workers = query_db("SELECT id, worker_name FROM workers ORDER BY worker_name")
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = query_db(record_sql, (view_id,), one=True)
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = query_db(record_sql, (edit_id,), one=True)
        if edit_record:
            edit_role = get_edit_role_for_user(
                get_db(), session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}
    if request.method == "POST":
        worker_id = request.form.get("worker_id", "")
        project_id = request.form.get("project_id", "")
        attendance_date = request.form.get("attendance_date", "").strip()
        in_time = request.form.get("in_time", "").strip()
        out_time = request.form.get("out_time", "").strip()
        break_hours = request.form.get("break_hours", "0").strip()
        status = request.form.get("status", "Present").strip()
        record_id = request.form.get("record_id", "").strip()
        try:
            start_dt = datetime.strptime(in_time, "%H:%M")
            end_dt = datetime.strptime(out_time, "%H:%M")
            break_hours_val = float(break_hours or 0)
            total_hours = (end_dt - start_dt).seconds / 3600 - break_hours_val
            if total_hours < 0:
                total_hours += 24
            ot_hours = max(total_hours - 8, 0)
        except Exception:
            flash("Enter valid attendance time values.")
            return redirect(url_for(endpoint))
        db = get_db()
        if record_id:
            ctx = _module_edit_context(module_id, table, endpoint)
            if ctx[0] == "redirect":
                return redirect(ctx[1])
            rid, edit_role = ctx
            db.execute(
                "UPDATE attendance SET worker_id=?, project_id=?, attendance_date=?, "
                "in_time=?, out_time=?, break_hours=?, total_hours=?, ot_hours=?, status=? WHERE id=?",
                (
                    worker_id or None, project_id or None, attendance_date,
                    in_time, out_time, break_hours_val, total_hours, ot_hours, status, rid,
                ),
            )
            _complete_module_save(db, module_id, table, rid, edit_role)
            return redirect(url_for(endpoint))
        db.execute(
            "INSERT INTO attendance(worker_id, project_id, attendance_date, in_time, out_time, break_hours, total_hours, ot_hours, status, approval_status) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (worker_id or None, project_id or None, attendance_date, in_time, out_time, break_hours_val, total_hours, ot_hours, status, "Pending Checker")
        )
        record_id_new = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        create_approval_request(
            db, module_id, record_id_new, table,
            session.get("username", ""), session.get("user_id")
        )
        db.commit()
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT a.*, w.worker_name, p.project_name FROM attendance a "
        "LEFT JOIN workers w ON a.worker_id = w.id "
        "LEFT JOIN projects p ON a.project_id = p.id ORDER BY a.id DESC"
    )
    return render_template(
        "attendance.html", rows=rows, workers=workers, projects=projects,
        view_record=view_record, edit_record=edit_record,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/petty_cash", methods=["GET", "POST"])
@login_required
def petty_cash():
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = None
    edit_record = None
    if view_id:
        view_record = query_db(
            "SELECT p.*, pr.project_name FROM petty_cash p "
            "LEFT JOIN projects pr ON p.project_id = pr.id WHERE p.id=?",
            (view_id,), one=True,
        )
    if edit_id:
        edit_record = query_db(
            "SELECT p.*, pr.project_name FROM petty_cash p "
            "LEFT JOIN projects pr ON p.project_id = pr.id WHERE p.id=?",
            (edit_id,), one=True,
        )
    if request.method == "POST":
        project_id = request.form.get("project_id", "")
        expense_date = request.form.get("expense_date", "").strip()
        expense_type = request.form.get("expense_type", "").strip()
        amount = request.form.get("amount", "0").strip()
        payment_mode = request.form.get("payment_mode", "Cash").strip()
        remarks = request.form.get("remarks", "").strip()
        record_id = request.form.get("record_id", "").strip()
        created_by = session.get("username", "")
        try:
            amount_val = float(amount or 0)
        except ValueError:
            flash("Enter a valid amount.")
            return redirect(url_for("petty_cash"))
        db = get_db()
        if record_id:
            existing = db.execute(
                "SELECT approval_status FROM petty_cash WHERE id=?", (record_id,)
            ).fetchone()
            if not existing:
                flash("Record not found.")
                return redirect(url_for("petty_cash"))
            edit_role = get_edit_role_for_user(
                db, session.get("user_id"), "petty_cash",
                existing["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for("petty_cash"))
            db.execute(
                "UPDATE petty_cash SET project_id=?, expense_date=?, expense_type=?, "
                "amount=?, payment_mode=?, remarks=? WHERE id=?",
                (project_id or None, expense_date, expense_type, amount_val, payment_mode,
                 remarks, record_id),
            )
            if edit_role == "maker":
                db.execute(
                    "UPDATE petty_cash SET approval_status=? WHERE id=?",
                    ("Pending Checker", record_id),
                )
                resubmit_record(db, "petty_cash", int(record_id), "petty_cash", session.get("user_id"))
            db.commit()
            if edit_role != "maker":
                flash("Changes saved. Record remains locked at current workflow stage.")
            else:
                flash("Saved. Status: Pending Checker.")
        else:
            db.execute(
                "INSERT INTO petty_cash(project_id, expense_date, expense_type, amount, "
                "payment_mode, remarks, created_by, approval_status) VALUES(?,?,?,?,?,?,?,?)",
                (project_id or None, expense_date, expense_type, amount_val, payment_mode,
                 remarks, created_by, "Pending Checker"),
            )
            new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            create_approval_request(
                db, "petty_cash", new_id, "petty_cash", created_by, session.get("user_id")
            )
            db.commit()
            flash("Saved. Status: Pending Checker.")
        return redirect(url_for("petty_cash"))
    rows = query_db(
        "SELECT p.*, pr.project_name FROM petty_cash p LEFT JOIN projects pr ON p.project_id = pr.id ORDER BY p.id DESC"
    )
    workflow = get_workflow_for_module(get_db(), "petty_cash")
    wf_ctx = {}
    if view_record:
        wf_ctx = _workflow_view_context(
            "petty_cash", view_record["id"], "petty_cash", view_record["approval_status"]
        )
    elif edit_record:
        edit_role = get_edit_role_for_user(
            get_db(), session.get("user_id"), "petty_cash",
            edit_record["approval_status"], is_admin_user(),
        )
        if not edit_role:
            flash("This record is locked and cannot be edited.")
            return redirect(url_for("petty_cash", view=edit_id))
        wf_ctx = {"edit_role": edit_role}
    return render_template(
        "petty_cash.html", rows=rows, projects=projects, workflow=workflow,
        view_record=view_record, edit_record=edit_record,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
        is_admin=is_admin_user(),
    )


@app.route("/salary", methods=["GET", "POST"])
@login_required
def salary():
    module_id, table, endpoint = "payroll", "salary", "salary"
    record_sql = (
        "SELECT s.*, w.worker_name FROM salary s "
        "LEFT JOIN workers w ON s.worker_id = w.id WHERE s.id=?"
    )
    workers = query_db("SELECT id, worker_name FROM workers ORDER BY worker_name")
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = query_db(record_sql, (view_id,), one=True)
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = query_db(record_sql, (edit_id,), one=True)
        if edit_record:
            edit_role = get_edit_role_for_user(
                get_db(), session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}
    if request.method == "POST":
        worker_id = request.form.get("worker_id", "")
        month = request.form.get("month", "").strip()
        total_days = request.form.get("total_days", "0").strip()
        normal_wage = request.form.get("normal_wage", "0").strip()
        ot_amount = request.form.get("ot_amount", "0").strip()
        advance_deduction = request.form.get("advance_deduction", "0").strip()
        payment_status = request.form.get("payment_status", "Pending").strip()
        record_id = request.form.get("record_id", "").strip()
        try:
            total_days_val = int(total_days or 0)
            normal_wage_val = float(normal_wage or 0)
            ot_amount_val = float(ot_amount or 0)
            advance_deduction_val = float(advance_deduction or 0)
            final_salary = normal_wage_val + ot_amount_val - advance_deduction_val
        except ValueError:
            flash("Enter valid numeric salary values.")
            return redirect(url_for(endpoint))
        db = get_db()
        if record_id:
            ctx = _module_edit_context(module_id, table, endpoint)
            if ctx[0] == "redirect":
                return redirect(ctx[1])
            rid, edit_role = ctx
            db.execute(
                "UPDATE salary SET worker_id=?, month=?, total_days=?, normal_wage=?, "
                "ot_amount=?, advance_deduction=?, final_salary=?, payment_status=? WHERE id=?",
                (
                    worker_id or None, month, total_days_val, normal_wage_val,
                    ot_amount_val, advance_deduction_val, final_salary, payment_status, rid,
                ),
            )
            _complete_module_save(db, module_id, table, rid, edit_role)
            return redirect(url_for(endpoint))
        db.execute(
            "INSERT INTO salary(worker_id, month, total_days, normal_wage, ot_amount, advance_deduction, final_salary, payment_status, approval_status) VALUES(?,?,?,?,?,?,?,?,?)",
            (worker_id or None, month, total_days_val, normal_wage_val, ot_amount_val, advance_deduction_val, final_salary, payment_status, "Pending Checker")
        )
        record_id_new = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        create_approval_request(
            db, module_id, record_id_new, table,
            session.get("username", ""), session.get("user_id")
        )
        db.commit()
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT s.*, w.worker_name FROM salary s LEFT JOIN workers w ON s.worker_id = w.id ORDER BY s.id DESC"
    )
    return render_template(
        "salary.html", rows=rows, workers=workers,
        view_record=view_record, edit_record=edit_record,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/reports", methods=["GET", "POST"])
@login_required
def reports():
    workers = query_db("SELECT id, worker_name FROM workers ORDER BY worker_name")
    report_rows = None
    file_url = None
    if request.method == "POST":
        report_type = request.form.get("report_type", "attendance")
        worker_id = request.form.get("worker_id", "")
        from_date = request.form.get("from_date", "").strip()
        to_date = request.form.get("to_date", "").strip()
        try:
            if report_type == "attendance":
                query = (
                    "SELECT a.attendance_date, w.worker_name, p.project_name, a.in_time, a.out_time, a.break_hours, a.total_hours, a.ot_hours, a.status "
                    "FROM attendance a LEFT JOIN workers w ON a.worker_id = w.id "
                    "LEFT JOIN projects p ON a.project_id = p.id "
                    "WHERE a.worker_id = ? AND a.attendance_date BETWEEN ? AND ?"
                )
                df = pd.read_sql_query(query, get_db(), params=(worker_id or None, from_date, to_date))
            else:
                query = (
                    "SELECT s.month, w.worker_name, s.total_days, s.normal_wage, s.ot_amount, s.advance_deduction, s.final_salary, s.payment_status "
                    "FROM salary s LEFT JOIN workers w ON s.worker_id = w.id "
                    "WHERE s.worker_id = ? AND s.month = ?"
                )
                df = pd.read_sql_query(query, get_db(), params=(worker_id or None, from_date))
            if df.empty:
                flash("No records found for the selected criteria.")
            else:
                filename = f"{report_type}_report_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
                file_path = os.path.join(REPORTS_DIR, filename)
                df.to_excel(file_path, index=False)
                file_url = url_for("download_report", filename=filename)
                report_rows = df.to_dict(orient="records")
        except Exception as exc:
            flash(f"Unable to generate report: {exc}")
    return render_template("reports.html", workers=workers, report_rows=report_rows, file_url=file_url)


@app.route("/reports/download/<filename>")
@login_required
def download_report(filename):
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    ensure_department_master(get_db())
    if request.method == "POST":
        department_name = request.form.get("department_name", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("status", "Active").strip()
        if not department_name:
            flash("Department name is required.")
            return redirect(url_for("settings") + "#department-master")
        db = get_db()
        try:
            db.execute(
                "INSERT INTO departments(department_name, description, status) VALUES(?,?,?)",
                (department_name, description, status),
            )
            db.commit()
            flash("Department created.")
        except sqlite3.IntegrityError:
            flash("Department already exists.")
        return redirect(url_for("settings") + "#department-master")
    departments = query_db("SELECT * FROM departments ORDER BY department_name")
    return render_template("settings.html", departments=departments)


@app.route("/settings/users", methods=["GET", "POST"])
@admin_required
def user_settings():
    db = get_db()
    designations = query_db(
        "SELECT id, designation_name FROM designations WHERE status='Active' ORDER BY designation_name"
    )
    departments = get_departments()
    workflow_roles = ["Maker", "Checker", "Approver", "Administrator"]
    system_roles = ["Maker", "Checker", "Approver", "Admin"]

    if request.method == "POST":
        action = request.form.get("action", "save")
        user_id = request.form.get("user_id", "").strip()
        if action == "toggle" and user_id:
            row = db.execute("SELECT status FROM users WHERE id=?", (user_id,)).fetchone()
            if row:
                new_status = "Inactive" if row["status"] == "Active" else "Active"
                db.execute("UPDATE users SET status=? WHERE id=?", (new_status, user_id))
                db.commit()
                flash(f"User status updated to {new_status}.")
            return redirect(url_for("user_settings"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        employee_name = request.form.get("employee_name", "").strip()
        department = request.form.get("department", "").strip()
        designation_id = request.form.get("designation_id") or None
        role = request.form.get("role", "Maker").strip()
        workflow_role = request.form.get("workflow_role", "Maker").strip()
        status = request.form.get("status", "Active").strip()

        if not username or not employee_name:
            flash("Username and Employee Name are required.")
            return redirect(url_for("user_settings"))

        if user_id:
            if password:
                db.execute(
                    "UPDATE users SET username=?, password=?, employee_name=?, department=?, "
                    "designation_id=?, role=?, workflow_role=?, status=? WHERE id=?",
                    (username, password, employee_name, department, designation_id,
                     role, workflow_role, status, user_id),
                )
            else:
                db.execute(
                    "UPDATE users SET username=?, employee_name=?, department=?, "
                    "designation_id=?, role=?, workflow_role=?, status=? WHERE id=?",
                    (username, employee_name, department, designation_id,
                     role, workflow_role, status, user_id),
                )
            flash("User updated successfully.")
        else:
            if not password:
                flash("Password is required for new users.")
                return redirect(url_for("user_settings"))
            try:
                db.execute(
                    "INSERT INTO users(username, password, employee_name, department, "
                    "designation_id, role, workflow_role, status) VALUES(?,?,?,?,?,?,?,?)",
                    (username, password, employee_name, department, designation_id,
                     role, workflow_role, status),
                )
                flash("User created successfully.")
            except sqlite3.IntegrityError:
                flash("Username already exists.")
                return redirect(url_for("user_settings"))
        db.commit()
        return redirect(url_for("user_settings"))

    edit_id = request.args.get("edit")
    edit_user = None
    if edit_id:
        edit_user = query_db(
            "SELECT u.*, d.designation_name FROM users u "
            "LEFT JOIN designations d ON u.designation_id = d.id WHERE u.id=?",
            (edit_id,),
            one=True,
        )

    rows = query_db(
        "SELECT u.*, d.designation_name FROM users u "
        "LEFT JOIN designations d ON u.designation_id = d.id ORDER BY u.id DESC"
    )
    enriched = []
    for row in rows:
        r = dict(row)
        r["workflow_access"] = get_workflow_access_label(
            db, r.get("designation_id"), r.get("workflow_role")
        )
        if r.get("workflow_role"):
            r["workflow_access"] = r["workflow_role"]
        enriched.append(r)

    return render_template(
        "users.html",
        rows=enriched,
        designations=designations,
        departments=departments,
        workflow_roles=workflow_roles,
        system_roles=system_roles,
        edit_user=edit_user,
    )


@app.route("/settings/workflow", methods=["GET", "POST"])
@app.route("/settings/workflow-matrix", methods=["GET", "POST"])
@login_required
def workflow_settings():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "add_designation":
            name = request.form.get("designation_name", "").strip()
            if name:
                try:
                    db.execute(
                        "INSERT INTO designations(designation_name, status) VALUES(?, 'Active')",
                        (name,),
                    )
                    db.commit()
                    flash(f"Designation '{name}' added.")
                except sqlite3.IntegrityError:
                    flash("Designation already exists.")
        else:
            module_id = request.form.get("module_id", "").strip()
            maker_id = request.form.get("maker_designation_id", "")
            checker_id = request.form.get("checker_designation_id", "")
            approver_id = request.form.get("approver_designation_id", "")
            maker_name = db.execute(
                "SELECT designation_name FROM designations WHERE id=?", (maker_id,)
            ).fetchone()
            checker_name = db.execute(
                "SELECT designation_name FROM designations WHERE id=?", (checker_id,)
            ).fetchone()
            approver_name = db.execute(
                "SELECT designation_name FROM designations WHERE id=?", (approver_id,)
            ).fetchone()
            flow = f"{maker_name['designation_name'] if maker_name else 'Maker'} → {checker_name['designation_name'] if checker_name else 'Checker'} → {approver_name['designation_name'] if approver_name else 'Approver'}"
            db.execute(
                "UPDATE workflow_master SET maker_designation_id=?, checker_designation_id=?, "
                "approver_designation_id=?, workflow_role_mapping=? WHERE module_id=?",
                (maker_id or None, checker_id or None, approver_id or None, flow, module_id),
            )
            db.commit()
            flash("Workflow configuration saved.")
        return redirect(url_for("workflow_settings"))

    workflows = query_db(
        "SELECT wm.*, "
        "dm.designation_name AS maker_designation, "
        "dc.designation_name AS checker_designation, "
        "da.designation_name AS approver_designation "
        "FROM workflow_master wm "
        "LEFT JOIN designations dm ON wm.maker_designation_id = dm.id "
        "LEFT JOIN designations dc ON wm.checker_designation_id = dc.id "
        "LEFT JOIN designations da ON wm.approver_designation_id = da.id "
        "ORDER BY wm.module_name"
    )
    designations = query_db(
        "SELECT * FROM designations WHERE status='Active' ORDER BY designation_name"
    )
    return render_template(
        "workflow_settings.html", workflows=workflows, designations=designations
    )


@app.route("/reports/workflow-audit")
@login_required
def workflow_audit_report():
    db = get_db()
    module_id = request.args.get("module_id", "")
    status_key = request.args.get("status", "")
    modules = query_db(
        "SELECT module_id, module_name FROM workflow_master ORDER BY module_name"
    )
    rows = get_workflow_audit_report(
        db,
        module_id=module_id or None,
        status_filter=status_key or None,
    )
    export = request.args.get("export")
    if export == "xlsx" and rows:
        df = pd.DataFrame(rows)
        filename = f"workflow_audit_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
        file_path = os.path.join(REPORTS_DIR, filename)
        df.to_excel(file_path, index=False)
        return send_from_directory(REPORTS_DIR, filename, as_attachment=True)
    return render_template(
        "workflow_audit_report.html",
        rows=rows,
        modules=modules,
        selected_module=module_id,
        selected_status=status_key,
    )


@app.route("/approvals")
@app.route("/approvals/<role>")
@login_required
def approvals(role="checker"):
    db = get_db()
    user_id = session.get("user_id")
    admin = is_admin_user()
    caps = user_workflow_capabilities(db, user_id, admin)
    if role == "maker" and not caps.get("can_create") and not admin:
        role = "checker"
    if role == "checker" and not caps.get("can_verify") and not admin:
        role = "approver" if caps.get("can_approve") else "maker"
    if role == "approver" and not caps.get("can_approve") and not admin:
        role = "checker" if caps.get("can_verify") else "maker"
    counts = get_pending_counts(db, user_id, admin)
    if role == "maker":
        items = _enrich_approval_items(
            db,
            get_pending_items(db, user_id, role, admin),
        )
    else:
        items = _enrich_approval_items(db, get_pending_items(db, user_id, role, admin))
    return render_template(
        "approvals.html", role=role, counts=counts, items=items, module_routes=MODULE_ROUTES
    )


@app.route("/approvals/action", methods=["POST"])
@login_required
def approval_action():
    approval_id = request.form.get("approval_id", "")
    action = request.form.get("action", "")
    comments = request.form.get("comments", "")
    ok, message = advance_approval(
        get_db(),
        int(approval_id),
        session.get("user_id"),
        action,
        comments,
        is_admin_user(),
    )
    get_db().commit()
    flash(message, "success" if ok else "warning")
    role = request.form.get("role") or request.args.get("role") or "checker"
    return redirect(request.referrer or url_for("approvals", role=role))


@app.route("/workflow/reopen", methods=["POST"])
@login_required
def workflow_reopen():
    if not is_admin_user():
        flash("Only System Administrator can reopen transactions.")
        return redirect(request.referrer or url_for("dashboard"))
    approval_id = request.form.get("approval_id", "")
    reason = request.form.get("reason", "")
    ok, message = reopen_transaction(
        get_db(), int(approval_id), session.get("user_id"), reason, True
    )
    get_db().commit()
    flash(message, "success" if ok else "warning")
    return redirect(request.referrer or url_for("approvals"))


@app.route("/workflow/delete", methods=["POST"])
@login_required
def workflow_delete_record():
    flash("Records cannot be deleted after Save. Contact Administrator to reopen if approved.")
    redirect_to = request.form.get("redirect_to", "dashboard")
    return redirect(url_for(redirect_to))


@app.route("/notifications")
@login_required
def notifications():
    db = get_db()
    user_id = session.get("user_id")
    items = get_notifications(db, user_id, limit=50)
    return render_template("notifications.html", items=items)


@app.route("/notifications/read", methods=["POST"])
@login_required
def notifications_read():
    mark_notifications_read(get_db(), session.get("user_id"))
    get_db().commit()
    return redirect(request.referrer or url_for("notifications"))


def _submit_module_request(module_id, table, fields_sql, values):
    db = get_db()
    db.execute(f"INSERT INTO {table}({fields_sql}) VALUES({','.join('?' * len(values))})", values)
    record_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    create_approval_request(
        db, module_id, record_id, table,
        session.get("username", ""), session.get("user_id")
    )
    db.commit()


def _module_edit_context(module_id, table, endpoint):
    record_id = request.form.get("record_id", "").strip()
    if not record_id:
        return None, None
    db = get_db()
    existing = db.execute(
        f"SELECT approval_status FROM {table} WHERE id=?", (record_id,)
    ).fetchone()
    if not existing:
        flash("Record not found.")
        return "redirect", url_for(endpoint)
    edit_role = get_edit_role_for_user(
        db, session.get("user_id"), module_id,
        existing["approval_status"], is_admin_user(),
    )
    if not edit_role:
        flash("This record is locked and cannot be edited.")
        return "redirect", url_for(endpoint)
    return int(record_id), edit_role


def _complete_module_save(db, module_id, table, record_id, edit_role):
    if edit_role == "maker":
        db.execute(
            f"UPDATE {table} SET approval_status=? WHERE id=?",
            ("Pending Checker", record_id),
        )
        resubmit_record(db, module_id, record_id, table, session.get("user_id"))
        flash("Saved. Status: Pending Checker.")
    else:
        flash("Changes saved. Record remains locked at current workflow stage.")
    db.commit()


def _module_page_state(module_id, table, endpoint, record_sql):
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = query_db(record_sql, (view_id,), one=True)
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = query_db(record_sql, (edit_id,), one=True)
        if edit_record:
            edit_role = get_edit_role_for_user(
                get_db(), session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return {"redirect": url_for(endpoint, view=edit_id)}
            wf_ctx = {"edit_role": edit_role}
    return {
        "view_record": view_record,
        "edit_record": edit_record,
        "history": wf_ctx.get("history"),
        "edit_role": wf_ctx.get("edit_role"),
        "can_reopen": wf_ctx.get("can_reopen", False),
        "approval_id": wf_ctx.get("approval_id"),
        "module_id": module_id,
    }


@app.route("/material-request", methods=["GET", "POST"])
@login_required
def material_request():
    module_id, table, endpoint = "material_request", "material_requests", "material_request"
    record_sql = (
        "SELECT m.*, p.project_name FROM material_requests m "
        "LEFT JOIN projects p ON m.project_id = p.id WHERE m.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE material_requests SET project_id=?, request_date=?, item_name=?, "
                "quantity=?, unit=?, remarks=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("request_date", ""),
                    request.form.get("item_name", ""),
                    float(request.form.get("quantity") or 0),
                    request.form.get("unit", ""),
                    request.form.get("remarks", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, request_date, item_name, quantity, unit, remarks, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("request_date", ""),
                request.form.get("item_name", ""),
                float(request.form.get("quantity") or 0),
                request.form.get("unit", ""),
                request.form.get("remarks", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT m.*, p.project_name FROM material_requests m "
        "LEFT JOIN projects p ON m.project_id = p.id ORDER BY m.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Store / Material Request",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "request_date", "label": "Request Date", "type": "date", "required": True},
            {"name": "item_name", "label": "Item Name", "type": "text", "required": True},
            {"name": "quantity", "label": "Quantity", "type": "number", "required": True},
            {"name": "unit", "label": "Unit", "type": "text", "required": False},
            {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
        ],
        table_columns=["Date", "Project", "Item", "Qty", "By"],
        row_keys=["request_date", "project_name", "item_name", "quantity", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/purchase-request", methods=["GET", "POST"])
@login_required
def purchase_request():
    module_id, table, endpoint = "purchase_request", "purchase_requests", "purchase_request"
    record_sql = (
        "SELECT pr.*, p.project_name FROM purchase_requests pr "
        "LEFT JOIN projects p ON pr.project_id = p.id WHERE pr.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE purchase_requests SET project_id=?, request_date=?, item_description=?, "
                "quantity=?, estimated_cost=?, remarks=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("request_date", ""),
                    request.form.get("item_description", ""),
                    float(request.form.get("quantity") or 0),
                    float(request.form.get("estimated_cost") or 0),
                    request.form.get("remarks", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, request_date, item_description, quantity, estimated_cost, remarks, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("request_date", ""),
                request.form.get("item_description", ""),
                float(request.form.get("quantity") or 0),
                float(request.form.get("estimated_cost") or 0),
                request.form.get("remarks", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT pr.*, p.project_name FROM purchase_requests pr "
        "LEFT JOIN projects p ON pr.project_id = p.id ORDER BY pr.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Purchase Request",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "request_date", "label": "Request Date", "type": "date", "required": True},
            {"name": "item_description", "label": "Item Description", "type": "text", "required": True},
            {"name": "quantity", "label": "Quantity", "type": "number", "required": True},
            {"name": "estimated_cost", "label": "Estimated Cost", "type": "number", "required": True},
            {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
        ],
        table_columns=["Date", "Project", "Description", "Cost", "By"],
        row_keys=["request_date", "project_name", "item_description", "estimated_cost", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/project-expenses", methods=["GET", "POST"])
@login_required
def project_expenses():
    module_id, table, endpoint = "project_expenses", "project_expenses", "project_expenses"
    record_sql = (
        "SELECT e.*, p.project_name FROM project_expenses e "
        "LEFT JOIN projects p ON e.project_id = p.id WHERE e.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE project_expenses SET project_id=?, expense_date=?, expense_category=?, "
                "amount=?, description=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("expense_date", ""),
                    request.form.get("expense_category", ""),
                    float(request.form.get("amount") or 0),
                    request.form.get("description", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, expense_date, expense_category, amount, description, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("expense_date", ""),
                request.form.get("expense_category", ""),
                float(request.form.get("amount") or 0),
                request.form.get("description", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT e.*, p.project_name FROM project_expenses e "
        "LEFT JOIN projects p ON e.project_id = p.id ORDER BY e.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Project Expenses",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "expense_date", "label": "Expense Date", "type": "date", "required": True},
            {"name": "expense_category", "label": "Category", "type": "text", "required": True},
            {"name": "amount", "label": "Amount", "type": "number", "required": True},
            {"name": "description", "label": "Description", "type": "textarea", "required": False},
        ],
        table_columns=["Date", "Project", "Category", "Amount", "By"],
        row_keys=["expense_date", "project_name", "expense_category", "amount", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/head-office-expenses", methods=["GET", "POST"])
@login_required
def head_office_expenses():
    module_id, table, endpoint = "head_office_expenses", "head_office_expenses", "head_office_expenses"
    record_sql = "SELECT * FROM head_office_expenses WHERE id=?"
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE head_office_expenses SET expense_date=?, expense_category=?, "
                "amount=?, department=?, description=? WHERE id=?",
                (
                    request.form.get("expense_date", ""),
                    request.form.get("expense_category", ""),
                    float(request.form.get("amount") or 0),
                    request.form.get("department", ""),
                    request.form.get("description", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "expense_date, expense_category, amount, department, description, created_by, approval_status",
            (
                request.form.get("expense_date", ""),
                request.form.get("expense_category", ""),
                float(request.form.get("amount") or 0),
                request.form.get("department", ""),
                request.form.get("description", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db("SELECT * FROM head_office_expenses ORDER BY id DESC")
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Head Office Expenses",
        workflow=workflow,
        form_fields=[
            {"name": "expense_date", "label": "Expense Date", "type": "date", "required": True},
            {"name": "expense_category", "label": "Category", "type": "text", "required": True},
            {"name": "amount", "label": "Amount", "type": "number", "required": True},
            {"name": "department", "label": "Department", "type": "text", "required": True},
            {"name": "description", "label": "Description", "type": "textarea", "required": False},
        ],
        table_columns=["Date", "Category", "Amount", "Department", "By"],
        row_keys=["expense_date", "expense_category", "amount", "department", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/subcontract-request", methods=["GET", "POST"])
@login_required
def subcontract_request():
    module_id, table, endpoint = "subcontract", "subcontract_requests", "subcontract_request"
    record_sql = (
        "SELECT s.*, p.project_name, sc.subcontractor_name FROM subcontract_requests s "
        "LEFT JOIN projects p ON s.project_id = p.id "
        "LEFT JOIN subcontractors sc ON s.subcontractor_id = sc.id WHERE s.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    subcontractors = query_db("SELECT id, subcontractor_name FROM subcontractors ORDER BY subcontractor_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE subcontract_requests SET project_id=?, subcontractor_id=?, work_description=?, "
                "contract_amount=?, start_date=?, remarks=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("subcontractor_id") or None,
                    request.form.get("work_description", ""),
                    float(request.form.get("contract_amount") or 0),
                    request.form.get("start_date", ""),
                    request.form.get("remarks", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, subcontractor_id, work_description, contract_amount, start_date, remarks, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("subcontractor_id") or None,
                request.form.get("work_description", ""),
                float(request.form.get("contract_amount") or 0),
                request.form.get("start_date", ""),
                request.form.get("remarks", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT s.*, p.project_name, sc.subcontractor_name FROM subcontract_requests s "
        "LEFT JOIN projects p ON s.project_id = p.id "
        "LEFT JOIN subcontractors sc ON s.subcontractor_id = sc.id ORDER BY s.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Subcontract",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "subcontractor_id", "label": "Subcontractor", "type": "select", "required": True,
             "options": [{"value": s["id"], "label": s["subcontractor_name"]} for s in subcontractors]},
            {"name": "work_description", "label": "Work Description", "type": "text", "required": True},
            {"name": "contract_amount", "label": "Contract Amount", "type": "number", "required": True},
            {"name": "start_date", "label": "Start Date", "type": "date", "required": True},
            {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
        ],
        table_columns=["Project", "Subcontractor", "Amount", "Start", "By"],
        row_keys=["project_name", "subcontractor_name", "contract_amount", "start_date", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


def _project_options():
    return [
        {"value": project["id"], "label": project["project_name"]}
        for project in query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    ]


def _render_standard_module(module_id, table, endpoint, module_title, form_fields,
                            table_columns, row_keys, record_sql, rows_sql,
                            insert_fields, value_getter, update_sql, update_getter):
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(update_sql, (*update_getter(), record_id))
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table, insert_fields,
            (*value_getter(), session.get("username", ""), "Pending Checker"),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(rows_sql)
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title=module_title,
        workflow=workflow,
        form_fields=form_fields,
        table_columns=table_columns,
        row_keys=row_keys,
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/boq-management", methods=["GET", "POST"])
@login_required
def boq_management():
    amount_expr = "ROUND(COALESCE(quantity, 0) * COALESCE(rate, 0), 2)"
    fields = [
        {"name": "project_id", "label": "Project", "type": "select", "required": True, "options": _project_options()},
        {"name": "boq_date", "label": "BOQ Date", "type": "date", "required": True},
        {"name": "item_code", "label": "Item Code", "type": "text", "required": False},
        {"name": "item_description", "label": "Item Description", "type": "textarea", "required": True},
        {"name": "quantity", "label": "Quantity", "type": "number", "required": True},
        {"name": "unit", "label": "Unit", "type": "text", "required": True},
        {"name": "rate", "label": "Rate", "type": "number", "required": True},
        {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
    ]
    return _render_standard_module(
        "boq", "boq_items", "boq_management", "BOQ Management", fields,
        ["Date", "Project", "Item", "Qty", "Amount"],
        ["boq_date", "project_name", "item_description", "quantity", "amount"],
        f"SELECT b.*, p.project_name, {amount_expr} AS amount FROM boq_items b LEFT JOIN projects p ON b.project_id = p.id WHERE b.id=?",
        f"SELECT b.*, p.project_name, {amount_expr} AS amount FROM boq_items b LEFT JOIN projects p ON b.project_id = p.id ORDER BY b.id DESC",
        "project_id, boq_date, item_code, item_description, quantity, unit, rate, amount, remarks, created_by, approval_status",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("boq_date", ""),
            request.form.get("item_code", ""),
            request.form.get("item_description", ""),
            float(request.form.get("quantity") or 0),
            request.form.get("unit", ""),
            float(request.form.get("rate") or 0),
            float(request.form.get("quantity") or 0) * float(request.form.get("rate") or 0),
            request.form.get("remarks", ""),
        ),
        "UPDATE boq_items SET project_id=?, boq_date=?, item_code=?, item_description=?, quantity=?, unit=?, rate=?, amount=?, remarks=? WHERE id=?",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("boq_date", ""),
            request.form.get("item_code", ""),
            request.form.get("item_description", ""),
            float(request.form.get("quantity") or 0),
            request.form.get("unit", ""),
            float(request.form.get("rate") or 0),
            float(request.form.get("quantity") or 0) * float(request.form.get("rate") or 0),
            request.form.get("remarks", ""),
        ),
    )


@app.route("/dpr-entry", methods=["GET", "POST"])
@login_required
def dpr_entry():
    fields = [
        {"name": "project_id", "label": "Project", "type": "select", "required": True, "options": _project_options()},
        {"name": "report_date", "label": "Report Date", "type": "date", "required": True},
        {"name": "prepared_by", "label": "Prepared By", "type": "text", "required": True},
        {"name": "work_done", "label": "Work Done", "type": "textarea", "required": True},
        {"name": "manpower_count", "label": "Manpower Count", "type": "number", "required": False},
        {"name": "material_used", "label": "Material Used", "type": "textarea", "required": False},
        {"name": "issues", "label": "Issues / Delay Reasons", "type": "textarea", "required": False},
        {"name": "progress_percent", "label": "Progress %", "type": "number", "required": False},
    ]
    return _render_standard_module(
        "dpr", "dpr_entries", "dpr_entry", "DPR Entry", fields,
        ["Date", "Project", "Prepared By", "Manpower", "Progress %"],
        ["report_date", "project_name", "prepared_by", "manpower_count", "progress_percent"],
        "SELECT d.*, p.project_name FROM dpr_entries d LEFT JOIN projects p ON d.project_id = p.id WHERE d.id=?",
        "SELECT d.*, p.project_name FROM dpr_entries d LEFT JOIN projects p ON d.project_id = p.id ORDER BY d.id DESC",
        "project_id, report_date, prepared_by, work_done, manpower_count, material_used, issues, progress_percent, created_by, approval_status",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("report_date", ""),
            request.form.get("prepared_by", ""),
            request.form.get("work_done", ""),
            int(float(request.form.get("manpower_count") or 0)),
            request.form.get("material_used", ""),
            request.form.get("issues", ""),
            float(request.form.get("progress_percent") or 0),
        ),
        "UPDATE dpr_entries SET project_id=?, report_date=?, prepared_by=?, work_done=?, manpower_count=?, material_used=?, issues=?, progress_percent=? WHERE id=?",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("report_date", ""),
            request.form.get("prepared_by", ""),
            request.form.get("work_done", ""),
            int(float(request.form.get("manpower_count") or 0)),
            request.form.get("material_used", ""),
            request.form.get("issues", ""),
            float(request.form.get("progress_percent") or 0),
        ),
    )


@app.route("/manager-tool", methods=["GET", "POST"])
@login_required
def manager_tool():
    fields = [
        {"name": "project_id", "label": "Project", "type": "select", "required": False, "options": _project_options()},
        {"name": "task_date", "label": "Task Date", "type": "date", "required": True},
        {"name": "manager_name", "label": "Manager Name", "type": "text", "required": True},
        {"name": "action_item", "label": "Action Item", "type": "textarea", "required": True},
        {"name": "priority", "label": "Priority", "type": "select", "required": True,
         "options": [{"value": "High", "label": "High"}, {"value": "Medium", "label": "Medium"}, {"value": "Low", "label": "Low"}]},
        {"name": "target_date", "label": "Target Date", "type": "date", "required": False},
        {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
    ]
    return _render_standard_module(
        "manager_tool", "manager_tasks", "manager_tool", "Manager Action Items", fields,
        ["Date", "Project", "Manager", "Priority", "Target"],
        ["task_date", "project_name", "manager_name", "priority", "target_date"],
        "SELECT m.*, p.project_name FROM manager_tasks m LEFT JOIN projects p ON m.project_id = p.id WHERE m.id=?",
        "SELECT m.*, p.project_name FROM manager_tasks m LEFT JOIN projects p ON m.project_id = p.id ORDER BY m.id DESC",
        "project_id, task_date, manager_name, action_item, priority, target_date, remarks, created_by, approval_status",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("task_date", ""),
            request.form.get("manager_name", ""),
            request.form.get("action_item", ""),
            request.form.get("priority", ""),
            request.form.get("target_date", ""),
            request.form.get("remarks", ""),
        ),
        "UPDATE manager_tasks SET project_id=?, task_date=?, manager_name=?, action_item=?, priority=?, target_date=?, remarks=? WHERE id=?",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("task_date", ""),
            request.form.get("manager_name", ""),
            request.form.get("action_item", ""),
            request.form.get("priority", ""),
            request.form.get("target_date", ""),
            request.form.get("remarks", ""),
        ),
    )


def _account_transaction_page(transaction_type, module_id, endpoint, title):
    fields = [
        {"name": "project_id", "label": "Project", "type": "select", "required": False, "options": _project_options()},
        {"name": "transaction_date", "label": "Date", "type": "date", "required": True},
        {"name": "party_name", "label": "Party Name", "type": "text", "required": True},
        {"name": "account_head", "label": "Account Head", "type": "text", "required": True},
        {"name": "amount", "label": "Amount", "type": "number", "required": True},
        {"name": "payment_mode", "label": "Payment Mode", "type": "select", "required": True,
         "options": [{"value": "Cash", "label": "Cash"}, {"value": "Bank", "label": "Bank"}, {"value": "UPI", "label": "UPI"}, {"value": "Cheque", "label": "Cheque"}]},
        {"name": "reference_no", "label": "Reference No", "type": "text", "required": False},
        {"name": "tax_percent", "label": "Tax %", "type": "number", "required": False},
        {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
    ]
    return _render_standard_module(
        module_id, "account_transactions", endpoint, title, fields,
        ["Date", "Project", "Party", "Head", "Amount"],
        ["transaction_date", "project_name", "party_name", "account_head", "amount"],
        "SELECT a.*, p.project_name FROM account_transactions a LEFT JOIN projects p ON a.project_id = p.id WHERE a.id=?",
        "SELECT a.*, p.project_name FROM account_transactions a LEFT JOIN projects p ON a.project_id = p.id "
        f"WHERE a.transaction_type='{transaction_type}' ORDER BY a.id DESC",
        "transaction_type, project_id, transaction_date, party_name, account_head, amount, payment_mode, reference_no, tax_percent, remarks, created_by, approval_status",
        lambda: (
            transaction_type,
            request.form.get("project_id") or None,
            request.form.get("transaction_date", ""),
            request.form.get("party_name", ""),
            request.form.get("account_head", ""),
            float(request.form.get("amount") or 0),
            request.form.get("payment_mode", ""),
            request.form.get("reference_no", ""),
            float(request.form.get("tax_percent") or 0),
            request.form.get("remarks", ""),
        ),
        "UPDATE account_transactions SET transaction_type=?, project_id=?, transaction_date=?, party_name=?, account_head=?, amount=?, payment_mode=?, reference_no=?, tax_percent=?, remarks=? WHERE id=?",
        lambda: (
            transaction_type,
            request.form.get("project_id") or None,
            request.form.get("transaction_date", ""),
            request.form.get("party_name", ""),
            request.form.get("account_head", ""),
            float(request.form.get("amount") or 0),
            request.form.get("payment_mode", ""),
            request.form.get("reference_no", ""),
            float(request.form.get("tax_percent") or 0),
            request.form.get("remarks", ""),
        ),
    )


@app.route("/accounts/receipts", methods=["GET", "POST"])
@login_required
def account_receipts():
    return _account_transaction_page("Receipt", "account_receipt", "account_receipts", "Accounts Receipts")


@app.route("/accounts/payments", methods=["GET", "POST"])
@login_required
def account_payments():
    return _account_transaction_page("Payment", "account_payment", "account_payments", "Accounts Payments")


@app.route("/accounts/gst", methods=["GET", "POST"])
@login_required
def account_gst():
    return _account_transaction_page("GST", "account_gst", "account_gst", "GST Entries")


@app.route("/accounts/tds", methods=["GET", "POST"])
@login_required
def account_tds():
    return _account_transaction_page("TDS", "account_tds", "account_tds", "TDS Entries")


def _accounts_book(title, payment_mode=None):
    params = []
    where = "WHERE a.approval_status='Approved'"
    if payment_mode:
        where += " AND a.payment_mode=?"
        params.append(payment_mode)
    rows = query_db(
        "SELECT a.*, p.project_name FROM account_transactions a "
        "LEFT JOIN projects p ON a.project_id = p.id "
        f"{where} ORDER BY a.transaction_date DESC, a.id DESC",
        tuple(params),
    )
    receipts = sum(float(row["amount"] or 0) for row in rows if row["transaction_type"] == "Receipt")
    payments = sum(float(row["amount"] or 0) for row in rows if row["transaction_type"] != "Receipt")
    return render_template(
        "accounts_book.html",
        page_title=title,
        rows=rows,
        receipts=receipts,
        payments=payments,
        balance=receipts - payments,
    )


@app.route("/accounts/cash-book")
@login_required
def cash_book():
    return _accounts_book("Cash Book", "Cash")


@app.route("/accounts/bank-book")
@login_required
def bank_book():
    return _accounts_book("Bank Book", "Bank")


@app.route("/accounts/ledger")
@login_required
def ledger():
    return _accounts_book("Ledger")


@app.route("/leave-request", methods=["GET", "POST"])
@login_required
def leave_request():
    module_id, table, endpoint = "leave_request", "leave_requests", "leave_request"
    record_sql = "SELECT * FROM leave_requests WHERE id=?"
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE leave_requests SET employee_name=?, leave_type=?, from_date=?, "
                "to_date=?, days=?, reason=? WHERE id=?",
                (
                    request.form.get("employee_name", ""),
                    request.form.get("leave_type", ""),
                    request.form.get("from_date", ""),
                    request.form.get("to_date", ""),
                    float(request.form.get("days") or 0),
                    request.form.get("reason", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "employee_name, leave_type, from_date, to_date, days, reason, created_by, approval_status",
            (
                request.form.get("employee_name", ""),
                request.form.get("leave_type", ""),
                request.form.get("from_date", ""),
                request.form.get("to_date", ""),
                float(request.form.get("days") or 0),
                request.form.get("reason", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db("SELECT * FROM leave_requests ORDER BY id DESC")
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Leave Request",
        workflow=workflow,
        form_fields=[
            {"name": "employee_name", "label": "Employee Name", "type": "text", "required": True},
            {"name": "leave_type", "label": "Leave Type", "type": "text", "required": True},
            {"name": "from_date", "label": "From Date", "type": "date", "required": True},
            {"name": "to_date", "label": "To Date", "type": "date", "required": True},
            {"name": "days", "label": "Days", "type": "number", "required": True},
            {"name": "reason", "label": "Reason", "type": "textarea", "required": False},
        ],
        table_columns=["Employee", "Type", "From", "To", "Days"],
        row_keys=["employee_name", "leave_type", "from_date", "to_date", "days"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/store-issue", methods=["GET", "POST"])
@login_required
def store_issue():
    module_id, table, endpoint = "store_issue", "store_issues", "store_issue"
    record_sql = (
        "SELECT s.*, p.project_name FROM store_issues s "
        "LEFT JOIN projects p ON s.project_id = p.id WHERE s.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE store_issues SET project_id=?, issue_date=?, item_name=?, "
                "quantity=?, unit=?, issued_to=?, remarks=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("issue_date", ""),
                    request.form.get("item_name", ""),
                    float(request.form.get("quantity") or 0),
                    request.form.get("unit", ""),
                    request.form.get("issued_to", ""),
                    request.form.get("remarks", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, issue_date, item_name, quantity, unit, issued_to, remarks, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("issue_date", ""),
                request.form.get("item_name", ""),
                float(request.form.get("quantity") or 0),
                request.form.get("unit", ""),
                request.form.get("issued_to", ""),
                request.form.get("remarks", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT s.*, p.project_name FROM store_issues s "
        "LEFT JOIN projects p ON s.project_id = p.id ORDER BY s.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Store Issue",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "issue_date", "label": "Issue Date", "type": "date", "required": True},
            {"name": "item_name", "label": "Item Name", "type": "text", "required": True},
            {"name": "quantity", "label": "Quantity", "type": "number", "required": True},
            {"name": "unit", "label": "Unit", "type": "text", "required": False},
            {"name": "issued_to", "label": "Issued To", "type": "text", "required": True},
            {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
        ],
        table_columns=["Date", "Project", "Item", "Qty", "Issued To", "By"],
        row_keys=["issue_date", "project_name", "item_name", "quantity", "issued_to", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/store-receipt", methods=["GET", "POST"])
@login_required
def store_receipt():
    module_id, table, endpoint = "store_receipt", "store_receipts", "store_receipt"
    record_sql = (
        "SELECT s.*, p.project_name FROM store_receipts s "
        "LEFT JOIN projects p ON s.project_id = p.id WHERE s.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE store_receipts SET project_id=?, receipt_date=?, item_name=?, "
                "quantity=?, unit=?, supplier=?, remarks=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("receipt_date", ""),
                    request.form.get("item_name", ""),
                    float(request.form.get("quantity") or 0),
                    request.form.get("unit", ""),
                    request.form.get("supplier", ""),
                    request.form.get("remarks", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, receipt_date, item_name, quantity, unit, supplier, remarks, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("receipt_date", ""),
                request.form.get("item_name", ""),
                float(request.form.get("quantity") or 0),
                request.form.get("unit", ""),
                request.form.get("supplier", ""),
                request.form.get("remarks", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT s.*, p.project_name FROM store_receipts s "
        "LEFT JOIN projects p ON s.project_id = p.id ORDER BY s.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Store Receipt",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "receipt_date", "label": "Receipt Date", "type": "date", "required": True},
            {"name": "item_name", "label": "Item Name", "type": "text", "required": True},
            {"name": "quantity", "label": "Quantity", "type": "number", "required": True},
            {"name": "unit", "label": "Unit", "type": "text", "required": False},
            {"name": "supplier", "label": "Supplier", "type": "text", "required": True},
            {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
        ],
        table_columns=["Date", "Project", "Item", "Qty", "Supplier", "By"],
        row_keys=["receipt_date", "project_name", "item_name", "quantity", "supplier", "created_by"],
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/timesheet")
@login_required
def timesheet():
    rows = query_db(
        "SELECT a.id, a.attendance_date, a.in_time AS start_time, a.out_time AS end_time, "
        "a.break_hours, a.total_hours AS worked_hours, a.ot_hours AS overtime, "
        "a.approval_status, w.worker_name, p.project_name "
        "FROM attendance a "
        "LEFT JOIN workers w ON a.worker_id = w.id "
        "LEFT JOIN projects p ON a.project_id = p.id "
        "ORDER BY a.id DESC LIMIT 50"
    )
    return render_template("timesheet.html", rows=rows)


@app.route("/accounts")
@login_required
def accounts():
    return redirect(url_for("head_office_expenses"))


@app.route("/store")
@login_required
def store():
    return redirect(url_for("material_request"))


@app.route("/purchase")
@login_required
def purchase():
    return redirect(url_for("purchase_request"))


@app.route("/inventory")
@login_required
def inventory():
    return render_template(
        "module_placeholder.html",
        page_title="Inventory",
        breadcrumb_section="Operations",
        module_description="Stock levels, batch tracking, and warehouse balances will appear here.",
    )


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
