"""SQLite setup, migrations, and helpers for MAXEK ERP."""

import os
import sqlite3
from datetime import datetime

import pandas as pd

from modules.regions import DEFAULT_LOCATION_TREE

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "maxek_payroll.db")
DATE_FMT = "%d/%m/%Y"
DASHBOARD_SECTION_ORDER_DEFAULT = [
    "welcome",
    "kpis",
    "overviews",
    "recent_payments",
    "notifications",
]
DASHBOARD_SECTION_LABELS = {
    "welcome": "Welcome Header",
    "kpis": "KPI Cards",
    "overviews": "Overview Panels",
    "recent_payments": "Recent Payments",
    "notifications": "Notifications",
}
DASHBOARD_ROLES = ["Admin", "MD", "HR", "Accountant", "Project Manager", "Site Engineer"]

FINANCE_TRANSACTION_TYPES = (
    "expense_voucher",
    "payment_out",
    "cash_receipt",
    "petty_cash_issue",
)
FINANCE_STATUS_SUBMITTED = "Submitted"
FINANCE_STATUS_ACCOUNTS_CHECKED = "Accounts Checked"
FINANCE_STATUS_MD_APPROVED = "MD Approved"
FINANCE_STATUS_SETTLED = "Settled"
FINANCE_STATUS_REJECTED = "Rejected"

for folder in (
    os.path.join(BASE_DIR, "database"),
    os.path.join(BASE_DIR, "photos", "workers"),
    os.path.join(BASE_DIR, "uploads", "clients"),
    os.path.join(BASE_DIR, "uploads", "projects"),
    os.path.join(BASE_DIR, "uploads", "employees"),
    os.path.join(BASE_DIR, "uploads", "subcontractors"),
    os.path.join(BASE_DIR, "uploads", "bills"),
    os.path.join(BASE_DIR, "uploads", "finance"),
    os.path.join(BASE_DIR, "uploads", "dpr"),
    os.path.join(BASE_DIR, "reports"),
):
    os.makedirs(folder, exist_ok=True)


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def _columns(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return {r[1] for r in cur.fetchall()}


def _add_column_if_missing(cur, table, col, typ):
    if col not in _columns(cur, table):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")


def _seed_if_empty(cur, table, column, values):
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            f"INSERT INTO {table}({column}) VALUES(?)",
            [(value,) for value in values],
        )


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, full_name TEXT, username TEXT,
            password TEXT, role TEXT, mobile TEXT
        );
        CREATE TABLE IF NOT EXISTS app_settings(
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        );
        CREATE TABLE IF NOT EXISTS countries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS regions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_id INTEGER,
            region_name TEXT
        );
        CREATE TABLE IF NOT EXISTS districts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region_id INTEGER,
            district_name TEXT
        );
        CREATE TABLE IF NOT EXISTS departments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS designations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            designation_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS payment_heads(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            head_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS expense_heads(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            head_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS salary_rules(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS ot_rules(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS managers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manager_name TEXT,
            region TEXT,
            district TEXT,
            contact_number TEXT,
            country TEXT,
            state TEXT
        );
        CREATE TABLE IF NOT EXISTS clients(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT,
            client_name TEXT,
            company_name TEXT,
            contact_person TEXT,
            mobile TEXT,
            alternate_number TEXT,
            email TEXT,
            gst_number TEXT,
            pan_number TEXT,
            address TEXT,
            country TEXT,
            region TEXT,
            district TEXT,
            city TEXT,
            agreement_start_date TEXT,
            agreement_end_date TEXT,
            client_type TEXT,
            status TEXT,
            notes TEXT,
            document_upload TEXT,
            work_order_no TEXT,
            total_work_amount REAL
        );
        CREATE TABLE IF NOT EXISTS client_boq_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boq_item_id TEXT,
            client_id TEXT,
            client_name TEXT,
            boq_number TEXT,
            description TEXT,
            quantity REAL,
            unit TEXT,
            approved_rate REAL,
            amount REAL,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS project_boq_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boq_item_id TEXT,
            project_id TEXT,
            project_name TEXT,
            client_name TEXT,
            boq_number TEXT,
            description TEXT,
            quantity REAL,
            unit TEXT,
            approved_rate REAL,
            amount REAL,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS dpr_reports(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dpr_id TEXT,
            dpr_date TEXT,
            project_name TEXT,
            project_id TEXT,
            client_name TEXT,
            site_incharge_id TEXT,
            site_incharge_name TEXT,
            boq_item_id TEXT,
            boq_number TEXT,
            boq_description TEXT,
            unit TEXT,
            billing_measurement TEXT,
            total_boq_quantity REAL,
            done_quantity REAL,
            billed_quantity REAL,
            balance_quantity REAL,
            pending_billing_quantity REAL,
            progress_quantity REAL,
            remarks TEXT,
            document_upload TEXT,
            site_photo TEXT,
            weather TEXT,
            equipment_usage TEXT,
            delay_reason TEXT,
            engineer_approval TEXT,
            engineer_approved_by TEXT,
            engineer_approved_at TEXT,
            client_approval TEXT,
            client_approved_by TEXT,
            client_approved_at TEXT,
            status TEXT,
            created_by TEXT,
            created_at TEXT,
            client_billed_quantity REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS client_bills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id TEXT,
            bill_no TEXT,
            bill_date TEXT,
            client_name TEXT,
            project_name TEXT,
            total_amount REAL,
            gst_mode TEXT,
            gst_percent REAL,
            gst_amount REAL,
            grand_total REAL,
            remarks TEXT,
            status TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS client_bill_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id TEXT,
            bill_id TEXT,
            dpr_id TEXT,
            boq_item_id TEXT,
            boq_number TEXT,
            description TEXT,
            unit TEXT,
            quantity REAL,
            rate REAL,
            amount REAL
        );
        CREATE TABLE IF NOT EXISTS dpr_measurements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            measurement_id TEXT,
            dpr_id TEXT,
            measurement_type TEXT,
            width_1 REAL,
            width_2 REAL,
            length_1 REAL,
            length_2 REAL,
            height REAL,
            depth REAL,
            nos REAL,
            dia_mm REAL,
            bend REAL,
            avg_width REAL,
            avg_length REAL,
            calculated_quantity REAL,
            unit TEXT,
            billed INTEGER DEFAULT 0,
            billed_quantity REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS dpr_manpower(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manpower_id TEXT,
            dpr_id TEXT,
            labour_type TEXT,
            nos INTEGER,
            working_hours TEXT,
            remarks TEXT
        );
        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT,
            project_name TEXT,
            client_name TEXT,
            project_code TEXT,
            location TEXT,
            country TEXT,
            region TEXT,
            district TEXT,
            site_incharge TEXT,
            start_date TEXT,
            end_date TEXT,
            labour_count INTEGER,
            budget REAL,
            status TEXT,
            remarks TEXT,
            work_type TEXT,
            work_order_no TEXT,
            work_order_date TEXT,
            amount REAL
        );
        CREATE TABLE IF NOT EXISTS employees(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT,
            employee_type TEXT,
            employee_name TEXT,
            photo TEXT,
            mobile_number TEXT,
            address TEXT,
            country TEXT,
            region TEXT,
            district TEXT,
            native_place TEXT,
            blood_group TEXT,
            aadhaar_number TEXT,
            pan_number TEXT,
            date_of_birth TEXT,
            joining_date TEXT,
            leaving_date TEXT,
            status TEXT,
            company_or_subcontractor TEXT,
            project_name TEXT,
            department TEXT,
            designation TEXT,
            reporting_manager TEXT,
            salary_type TEXT,
            salary_amount REAL,
            basic_salary REAL,
            room_allowance REAL,
            food_allowance REAL,
            telephone_allowance REAL,
            other_allowance REAL,
            ot_applicable TEXT,
            ot_rate REAL,
            shift TEXT,
            experience TEXT,
            skills TEXT,
            remarks TEXT
        );
        CREATE TABLE IF NOT EXISTS subcontractors(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcontractor_id TEXT,
            subcontractor_name TEXT,
            company_name TEXT,
            contact_person TEXT,
            contact_number TEXT,
            aadhaar_number TEXT,
            pan_card_number TEXT,
            address TEXT,
            country TEXT,
            region TEXT,
            district TEXT,
            trade TEXT,
            agreement_upload TEXT,
            active_projects TEXT,
            worker_count INTEGER,
            status TEXT,
            project_name TEXT,
            joining_date TEXT,
            bank_account TEXT,
            bank_name TEXT,
            ifsc_code TEXT,
            branch_name TEXT,
            date_of_birth TEXT,
            state TEXT,
            manager_name TEXT
        );
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT,
            employee_name TEXT,
            employee_type TEXT,
            department TEXT,
            designation TEXT,
            project_name TEXT,
            sub_contractor TEXT,
            attendance_date TEXT,
            in_time TEXT,
            out_time TEXT,
            break_hours REAL,
            total_hours REAL,
            ot_hours REAL,
            status TEXT,
            remarks TEXT,
            worker_id TEXT,
            worker_name TEXT,
            start_time TEXT,
            end_time TEXT,
            worked_hours REAL,
            overtime REAL,
            work_description TEXT
        );
        CREATE TABLE IF NOT EXISTS payroll(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payroll_id TEXT,
            employee_id TEXT,
            worker_id TEXT,
            payroll_month TEXT,
            base_salary REAL,
            ot_amount REAL,
            deductions REAL,
            salary REAL,
            net_salary REAL,
            salary_status TEXT,
            paid_date TEXT
        );
        CREATE TABLE IF NOT EXISTS allowance_heads(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            head_name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS employee_allowance_components(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT,
            allowance_head TEXT,
            amount REAL,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS employee_salary_revisions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id TEXT,
            employee_id TEXT,
            revision_date TEXT,
            previous_salary REAL,
            revised_salary REAL,
            increment_amount REAL,
            reason TEXT,
            basic_salary REAL,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS employee_bonus(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bonus_id TEXT,
            employee_id TEXT,
            bonus_date TEXT,
            bonus_month TEXT,
            amount REAL,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS employee_bata(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bata_id TEXT,
            employee_id TEXT,
            bata_date TEXT,
            amount REAL,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_number TEXT,
            payment_date TEXT,
            payment_type TEXT,
            payment_head TEXT,
            pay_to_type TEXT,
            pay_to_name TEXT,
            project_name TEXT,
            client_name TEXT,
            amount REAL,
            payment_mode TEXT,
            reference_number TEXT,
            remarks TEXT,
            bill_upload TEXT,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id TEXT,
            expense_date TEXT,
            expense_head TEXT,
            project_name TEXT,
            client_name TEXT,
            paid_to TEXT,
            amount REAL,
            payment_mode TEXT,
            approved_by TEXT,
            bill_upload TEXT,
            remarks TEXT
        );
        CREATE TABLE IF NOT EXISTS finance_transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT,
            transaction_type TEXT,
            transaction_date TEXT,
            project_name TEXT,
            client_name TEXT,
            category_head TEXT,
            pay_to_type TEXT,
            pay_to_name TEXT,
            amount REAL,
            payment_mode TEXT,
            funding_source TEXT,
            reference_number TEXT,
            remarks TEXT,
            document_upload TEXT,
            status TEXT,
            submitted_by TEXT,
            submitted_at TEXT,
            accounts_checked_by TEXT,
            accounts_checked_at TEXT,
            md_approved_by TEXT,
            md_approved_at TEXT,
            settled_by TEXT,
            settled_at TEXT,
            rejected_by TEXT,
            rejected_at TEXT,
            rejection_reason TEXT
        );
        CREATE TABLE IF NOT EXISTS document_uploads(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT,
            entity_id TEXT,
            document_type TEXT,
            file_path TEXT,
            uploaded_at TEXT
        );
        CREATE TABLE IF NOT EXISTS subcontractor_advance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            advance_id TEXT,
            subcontractor_name TEXT,
            amount REAL,
            remarks TEXT
        );
        CREATE TABLE IF NOT EXISTS subcontractor_labour_rates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rate_id TEXT,
            subcontractor_name TEXT,
            project_name TEXT,
            labour_type TEXT,
            working_hours TEXT,
            fixed_hours REAL,
            rate REAL,
            ot_applicable TEXT,
            ot_rate REAL,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS subcontractor_boq_rates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boq_rate_id TEXT,
            project_name TEXT,
            boq_item TEXT,
            unit TEXT,
            rate REAL,
            subcontractor_name TEXT,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS subcontractor_boq_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boq_entry_id TEXT,
            entry_date TEXT,
            subcontractor_name TEXT,
            project_name TEXT,
            boq_item TEXT,
            unit TEXT,
            rate REAL,
            quantity REAL,
            amount REAL,
            remarks TEXT
        );
        CREATE TABLE IF NOT EXISTS subcontractor_bills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id TEXT,
            bill_date TEXT,
            bill_month TEXT,
            subcontractor_name TEXT,
            labour_amount REAL,
            boq_amount REAL,
            advance_amount REAL,
            total_amount REAL,
            net_amount REAL,
            remarks TEXT,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS holiday_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            holiday_id TEXT,
            holiday_name TEXT,
            holiday_date TEXT,
            holiday_type TEXT,
            applicable_for TEXT,
            payment_type TEXT,
            project_name TEXT,
            attendance_marking_type TEXT,
            approval_status TEXT,
            remarks TEXT
        );
        CREATE TABLE IF NOT EXISTS weekly_off_settings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weekly_off_id TEXT,
            weekly_off_day TEXT,
            payment_type TEXT,
            applicable_for TEXT,
            project_name TEXT,
            status TEXT,
            remarks TEXT
        );
        CREATE TABLE IF NOT EXISTS staff(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT,
            staff_name TEXT,
            department TEXT,
            designation TEXT,
            mobile TEXT,
            salary REAL,
            region TEXT,
            manager_name TEXT,
            country TEXT,
            state TEXT
        );
        CREATE TABLE IF NOT EXISTS workers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT,
            subcontractor_name TEXT,
            worker_name TEXT,
            age TEXT,
            trade_name TEXT,
            joining_date TEXT,
            salary REAL,
            overtime_rate REAL,
            photo TEXT,
            status TEXT,
            region TEXT,
            manager_name TEXT,
            country TEXT,
            state TEXT
        );
        """
    )

    migrations = {
        "regions": (("country_id", "INTEGER"),),
        "clients": (
            ("company_name", "TEXT"),
            ("alternate_number", "TEXT"),
            ("email", "TEXT"),
            ("gst_number", "TEXT"),
            ("pan_number", "TEXT"),
            ("country", "TEXT"),
            ("region", "TEXT"),
            ("district", "TEXT"),
            ("city", "TEXT"),
            ("agreement_start_date", "TEXT"),
            ("agreement_end_date", "TEXT"),
            ("client_type", "TEXT"),
            ("status", "TEXT"),
            ("notes", "TEXT"),
            ("document_upload", "TEXT"),
            ("work_order_no", "TEXT"),
            ("total_work_amount", "REAL"),
        ),
        "projects": (
            ("project_code", "TEXT"),
            ("location", "TEXT"),
            ("country", "TEXT"),
            ("region", "TEXT"),
            ("district", "TEXT"),
            ("site_incharge", "TEXT"),
            ("start_date", "TEXT"),
            ("end_date", "TEXT"),
            ("labour_count", "INTEGER"),
            ("budget", "REAL"),
            ("status", "TEXT"),
            ("remarks", "TEXT"),
            ("work_order_no", "TEXT"),
            ("work_order_date", "TEXT"),
            ("amount", "REAL"),
        ),
        "managers": (("region", "TEXT"), ("country", "TEXT"), ("district", "TEXT")),
        "subcontractors": (
            ("company_name", "TEXT"),
            ("contact_person", "TEXT"),
            ("aadhaar_number", "TEXT"),
            ("address", "TEXT"),
            ("country", "TEXT"),
            ("region", "TEXT"),
            ("district", "TEXT"),
            ("trade", "TEXT"),
            ("agreement_upload", "TEXT"),
            ("active_projects", "TEXT"),
            ("worker_count", "INTEGER"),
            ("status", "TEXT"),
        ),
        "workers": (
            ("region", "TEXT"),
            ("manager_name", "TEXT"),
        ),
        "staff": (
            ("region", "TEXT"),
            ("manager_name", "TEXT"),
        ),
        "attendance": (
            ("employee_id", "TEXT"),
            ("employee_name", "TEXT"),
            ("employee_type", "TEXT"),
            ("department", "TEXT"),
            ("designation", "TEXT"),
            ("sub_contractor", "TEXT"),
            ("in_time", "TEXT"),
            ("out_time", "TEXT"),
            ("total_hours", "REAL"),
            ("ot_hours", "REAL"),
            ("status", "TEXT"),
            ("remarks", "TEXT"),
            ("fixed_working_hours", "REAL"),
            ("applied_rate", "REAL"),
            ("applied_ot_rate", "REAL"),
            ("attendance_category", "TEXT"),
            ("payment_type", "TEXT"),
            ("holiday_name", "TEXT"),
        ),
        "payroll": (
            ("employee_id", "TEXT"),
            ("payroll_month", "TEXT"),
            ("base_salary", "REAL"),
            ("ot_amount", "REAL"),
            ("deductions", "REAL"),
            ("net_salary", "REAL"),
        ),
        "subcontractor_advance": (
            ("advance_date", "TEXT"),
        ),
        "dpr_reports": (("client_billed_quantity", "REAL"), ("client_name", "TEXT")),
        "subcontractor_bills": (
            ("bill_type", "TEXT"),
            ("ot_amount", "REAL"),
        ),
        "employees": (
            ("country", "TEXT"),
            ("district", "TEXT"),
            ("date_of_birth", "TEXT"),
            ("basic_salary", "REAL"),
            ("room_allowance", "REAL"),
            ("food_allowance", "REAL"),
            ("telephone_allowance", "REAL"),
            ("other_allowance", "REAL"),
        ),
    }
    for table, columns in migrations.items():
        for col, typ in columns:
            _add_column_if_missing(cur, table, col, typ)

    sub_cols = _columns(cur, "subcontractors")
    if "sub_code" in sub_cols:
        cur.execute(
            """
            UPDATE subcontractors SET subcontractor_id = sub_code
            WHERE (subcontractor_id IS NULL OR subcontractor_id = '')
              AND sub_code IS NOT NULL AND sub_code != ''
            """
        )
    if "sub_name" in sub_cols:
        cur.execute(
            """
            UPDATE subcontractors SET subcontractor_name = sub_name
            WHERE (subcontractor_name IS NULL OR subcontractor_name = '')
              AND sub_name IS NOT NULL AND sub_name != ''
            """
        )
    if "pan_number" in sub_cols:
        cur.execute(
            """
            UPDATE subcontractors SET pan_card_number = pan_number
            WHERE (pan_card_number IS NULL OR pan_card_number = '')
              AND pan_number IS NOT NULL AND pan_number != ''
            """
        )

    cur.execute(
        """
        UPDATE managers SET region = COALESCE(NULLIF(region, ''), NULLIF(state, ''), NULLIF(country, ''))
        WHERE COALESCE(region, '') = ''
        """
    )
    cur.execute(
        """
        UPDATE managers SET country = 'India'
        WHERE COALESCE(country, '') = '' AND COALESCE(region, '') != ''
        """
    )
    cur.execute(
        """
        UPDATE staff SET region = COALESCE(NULLIF(region, ''), NULLIF(state, ''), NULLIF(country, ''))
        WHERE COALESCE(region, '') = ''
        """
    )
    cur.execute(
        """
        UPDATE workers SET region = COALESCE(NULLIF(region, ''), NULLIF(state, ''), NULLIF(country, ''))
        WHERE COALESCE(region, '') = ''
        """
    )
    cur.execute(
        """
        UPDATE employees SET country = 'India'
        WHERE COALESCE(country, '') = '' AND COALESCE(region, '') != ''
        """
    )
    cur.execute(
        """
        UPDATE dpr_reports
        SET client_name = (
            SELECT p.client_name FROM projects p
            WHERE p.project_name = dpr_reports.project_name
            LIMIT 1
        )
        WHERE COALESCE(client_name, '') = ''
          AND COALESCE(project_name, '') != ''
        """
    )
    cur.execute(
        """
        UPDATE clients SET country = 'India'
        WHERE COALESCE(country, '') = '' AND COALESCE(region, '') != ''
        """
    )
    cur.execute(
        """
        UPDATE projects SET country = 'India'
        WHERE COALESCE(country, '') = '' AND COALESCE(region, '') != ''
        """
    )
    cur.execute(
        """
        UPDATE subcontractors
        SET country = COALESCE(NULLIF(country, ''), 'India'),
            region = COALESCE(NULLIF(region, ''), NULLIF(state, ''), NULLIF(country, ''))
        WHERE COALESCE(region, '') = '' OR COALESCE(country, '') = ''
        """
    )
    cur.execute(
        """
        UPDATE clients SET company_name = client_name
        WHERE COALESCE(company_name, '') = '' AND COALESCE(client_name, '') != ''
        """
    )
    cur.execute(
        """
        UPDATE projects SET budget = amount
        WHERE COALESCE(budget, 0) = 0 AND amount IS NOT NULL
        """
    )
    cur.execute(
        """
        UPDATE projects SET start_date = work_order_date
        WHERE COALESCE(start_date, '') = '' AND COALESCE(work_order_date, '') != ''
        """
    )

    _seed_location_masters(cur)
    _seed_if_empty(cur, "departments", "department_name", ["HR", "Accounts", "Operations", "Site", "Projects"])
    _seed_if_empty(cur, "designations", "designation_name", ["Manager", "Engineer", "Supervisor", "Staff", "Worker"])
    _seed_if_empty(cur, "payment_heads", "head_name", ["Salary", "Advance", "Sub Contractor", "Material", "Fuel", "Site", "Transport", "Office", "Labour", "Other"])
    _seed_if_empty(cur, "expense_heads", "head_name", ["Material", "Fuel", "Site", "Transport", "Office", "Labour", "Miscellaneous"])
    _seed_if_empty(
        cur,
        "allowance_heads",
        "head_name",
        [
            "Room Allowance",
            "Food Allowance",
            "Telephone Allowance",
            "Transport Allowance",
            "Special Allowance",
            "Site Allowance",
            "Other Allowance",
        ],
    )
    _seed_dashboard_settings(cur)

    cur.execute("SELECT COUNT(*) FROM salary_rules")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO salary_rules(rule_name, description) VALUES(?, ?)", ("Standard Payroll", "Base salary plus OT minus deductions"))
    cur.execute("SELECT COUNT(*) FROM ot_rules")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO ot_rules(rule_name, description) VALUES(?, ?)", ("8 Hour Shift", "Overtime starts after 8 working hours"))
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        cur.execute(
            """
            INSERT INTO users(user_id, full_name, username, password, role, mobile)
            VALUES('USR101','Administrator','admin','1234','Admin','9999999999')
            """
        )

    _sync_legacy_to_employees(cur)
    _sync_employee_columns(cur)

    conn.commit()
    conn.close()


def _sync_legacy_to_employees(cur):
    employee_cols = _columns(cur, "employees")
    if "employee_id" not in employee_cols:
        return

    cur.execute("SELECT staff_id, staff_name, department, designation, mobile, salary, region, manager_name FROM staff")
    for staff_id, name, dept, desig, mobile, salary, region, manager in cur.fetchall():
        cur.execute("SELECT COUNT(*) FROM employees WHERE employee_id=?", (staff_id,))
        if cur.fetchone()[0] == 0 and staff_id:
            cur.execute(
                """
                INSERT INTO employees(
                    employee_id, employee_type, employee_name, mobile_number, region,
                    department, designation, reporting_manager, salary_type, salary_amount, status
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    staff_id,
                    "Company Staff",
                    name,
                    mobile,
                    region,
                    dept,
                    desig,
                    manager,
                    "Monthly",
                    salary or 0,
                    "Active",
                ),
            )

    cur.execute(
        """
        SELECT worker_id, worker_name, subcontractor_name, trade_name, joining_date,
               salary, overtime_rate, photo, status, region, manager_name
        FROM workers
        """
    )
    for row in cur.fetchall():
        worker_id, name, subcontractor, trade, joining, salary, ot_rate, photo, status, region, manager = row
        cur.execute("SELECT COUNT(*) FROM employees WHERE employee_id=?", (worker_id,))
        if cur.fetchone()[0] == 0 and worker_id:
            cur.execute(
                """
                INSERT INTO employees(
                    employee_id, employee_type, employee_name, photo, region,
                    company_or_subcontractor, designation, joining_date, salary_type,
                    salary_amount, ot_applicable, ot_rate, status, reporting_manager
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    worker_id,
                    "Sub Contractor Worker",
                    name,
                    photo,
                    region,
                    subcontractor,
                    trade,
                    joining,
                    "Daily",
                    salary or 0,
                    "Yes" if (ot_rate or 0) > 0 else "No",
                    ot_rate or 0,
                    status or "Active",
                    manager,
                ),
            )


def _sync_employee_columns(cur):
    cols = _columns(cur, "employees")
    if "mobile_number" in cols:
        cur.execute(
            """
            UPDATE employees SET status='Active'
            WHERE COALESCE(status,'')=''
            """
        )
    if "country" in cols:
        cur.execute(
            """
            UPDATE employees SET country='India'
            WHERE COALESCE(country,'')='' AND COALESCE(region,'')!=''
            """
        )


def _seed_location_masters(cur):
    for country_name, regions in DEFAULT_LOCATION_TREE.items():
        cur.execute("INSERT OR IGNORE INTO countries(country_name) VALUES(?)", (country_name,))
        cur.execute("SELECT id FROM countries WHERE country_name = ?", (country_name,))
        country_id = cur.fetchone()[0]

        for region_name, districts in regions.items():
            cur.execute(
                """
                UPDATE regions SET country_id = ?
                WHERE region_name = ? AND COALESCE(country_id, 0) = 0
                """,
                (country_id, region_name),
            )
            cur.execute(
                "SELECT id FROM regions WHERE region_name = ? AND COALESCE(country_id, 0) = ?",
                (region_name, country_id),
            )
            region_row = cur.fetchone()
            if region_row:
                region_id = region_row[0]
            else:
                cur.execute(
                    "INSERT INTO regions(country_id, region_name) VALUES(?, ?)",
                    (country_id, region_name),
                )
                region_id = cur.lastrowid

            for district_name in districts:
                cur.execute(
                    "SELECT id FROM districts WHERE district_name = ? AND COALESCE(region_id, 0) = ?",
                    (district_name, region_id),
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO districts(region_id, district_name) VALUES(?, ?)",
                        (region_id, district_name),
                    )


def _seed_dashboard_settings(cur):
    defaults = {
        "dashboard_show_welcome": "1",
        "dashboard_show_kpis": "1",
        "dashboard_show_attendance_overview": "1",
        "dashboard_show_project_overview": "1",
        "dashboard_show_expense_overview": "1",
        "dashboard_show_recent_payments": "1",
        "dashboard_show_notifications": "1",
        "dashboard_show_sidebar_cashflow": "1",
        "dashboard_section_order": ",".join(DASHBOARD_SECTION_ORDER_DEFAULT),
    }
    for setting_key, setting_value in defaults.items():
        cur.execute(
            "INSERT OR IGNORE INTO app_settings(setting_key, setting_value) VALUES(?, ?)",
            (setting_key, setting_value),
        )
    for role in DASHBOARD_ROLES:
        for section_key in DASHBOARD_SECTION_ORDER_DEFAULT:
            cur.execute(
                "INSERT OR IGNORE INTO app_settings(setting_key, setting_value) VALUES(?, ?)",
                (f"dashboard_role_{role}_{section_key}", "1"),
            )


def generate_id(prefix, table_name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cur.fetchone()[0] + 101
    conn.close()
    return f"{prefix}{count}"


def table_count(table):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    value = cur.fetchone()[0]
    conn.close()
    return value


def scalar_query(sql, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    value = cur.fetchone()[0]
    conn.close()
    return value or 0


def sum_query(sql, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    value = cur.fetchone()[0]
    conn.close()
    return float(value or 0)


def _finance_timestamp():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def get_petty_cash_balance(project_name):
    if not project_name:
        return 0.0
    issued = sum_query(
        """
        SELECT COALESCE(SUM(amount), 0) FROM finance_transactions
        WHERE transaction_type = 'petty_cash_issue' AND project_name = ? AND status = ?
        """,
        (project_name, FINANCE_STATUS_SETTLED),
    )
    spent = sum_query(
        """
        SELECT COALESCE(SUM(amount), 0) FROM finance_transactions
        WHERE transaction_type = 'expense_voucher' AND project_name = ? AND funding_source = 'Petty Cash'
          AND status = ?
        """,
        (project_name, FINANCE_STATUS_SETTLED),
    )
    returned = sum_query(
        """
        SELECT COALESCE(SUM(amount), 0) FROM finance_transactions
        WHERE transaction_type = 'cash_receipt' AND project_name = ? AND category_head = 'Petty Cash Return'
          AND status = ?
        """,
        (project_name, FINANCE_STATUS_SETTLED),
    )
    return issued - spent - returned


def load_petty_cash_balances():
    conn = get_conn()
    projects = pd.read_sql_query(
        """
        SELECT DISTINCT project_name FROM (
            SELECT project_name FROM projects WHERE COALESCE(project_name, '') != ''
            UNION
            SELECT project_name FROM finance_transactions WHERE COALESCE(project_name, '') != ''
        )
        ORDER BY project_name
        """,
        conn,
    )
    conn.close()
    rows = []
    for project_name in projects["project_name"].tolist():
        balance = get_petty_cash_balance(project_name)
        rows.append({"Project": project_name, "Petty Cash Balance (Rs)": balance})
    return pd.DataFrame(rows)


def load_finance_transactions(status=None, transaction_type=None, limit=200):
    conn = get_conn()
    sql = """
        SELECT transaction_id, transaction_type, transaction_date, project_name, client_name,
               category_head, pay_to_type, pay_to_name, amount, payment_mode, funding_source,
               status, submitted_by, accounts_checked_by, md_approved_by, settled_by, remarks
        FROM finance_transactions
        WHERE 1=1
    """
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if transaction_type:
        sql += " AND transaction_type = ?"
        params.append(transaction_type)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def insert_finance_transaction(conn, row):
    conn.execute(
        """
        INSERT INTO finance_transactions(
            transaction_id, transaction_type, transaction_date, project_name, client_name,
            category_head, pay_to_type, pay_to_name, amount, payment_mode, funding_source,
            reference_number, remarks, document_upload, status, submitted_by, submitted_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            row["transaction_id"],
            row["transaction_type"],
            row["transaction_date"],
            row.get("project_name", ""),
            row.get("client_name", ""),
            row.get("category_head", ""),
            row.get("pay_to_type", ""),
            row.get("pay_to_name", ""),
            float(row["amount"]),
            row.get("payment_mode", ""),
            row.get("funding_source", ""),
            row.get("reference_number", ""),
            row.get("remarks", ""),
            row.get("document_upload", ""),
            row.get("status", FINANCE_STATUS_SUBMITTED),
            row.get("submitted_by", ""),
            row.get("submitted_at", _finance_timestamp()),
        ),
    )


def update_finance_status(conn, transaction_id, new_status, actor, rejection_reason=""):
    now = _finance_timestamp()
    if new_status == FINANCE_STATUS_ACCOUNTS_CHECKED:
        conn.execute(
            """
            UPDATE finance_transactions
            SET status = ?, accounts_checked_by = ?, accounts_checked_at = ?
            WHERE transaction_id = ?
            """,
            (new_status, actor, now, transaction_id),
        )
    elif new_status == FINANCE_STATUS_MD_APPROVED:
        conn.execute(
            """
            UPDATE finance_transactions
            SET status = ?, md_approved_by = ?, md_approved_at = ?
            WHERE transaction_id = ?
            """,
            (new_status, actor, now, transaction_id),
        )
    elif new_status == FINANCE_STATUS_SETTLED:
        conn.execute(
            """
            UPDATE finance_transactions
            SET status = ?, settled_by = ?, settled_at = ?
            WHERE transaction_id = ?
            """,
            (new_status, actor, now, transaction_id),
        )
    elif new_status == FINANCE_STATUS_REJECTED:
        conn.execute(
            """
            UPDATE finance_transactions
            SET status = ?, rejected_by = ?, rejected_at = ?, rejection_reason = ?
            WHERE transaction_id = ?
            """,
            (new_status, actor, now, rejection_reason, transaction_id),
        )


def load_project_boq_by_project(project_name):
    if not project_name:
        return pd.DataFrame()
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT boq_item_id, project_id, project_name, boq_number, description, quantity, unit,
               approved_rate, amount
        FROM project_boq_items
        WHERE project_name = ?
        ORDER BY boq_number
        """,
        conn,
        params=(project_name,),
    )
    conn.close()
    return df


def get_boq_progress_stats(boq_item_id):
    conn = get_conn()
    boq_df = pd.read_sql_query(
        """
        SELECT quantity, unit, boq_number, description, project_name
        FROM project_boq_items
        WHERE boq_item_id = ?
        LIMIT 1
        """,
        conn,
        params=(boq_item_id,),
    )
    if boq_df.empty:
        conn.close()
        return {
            "total_qty": 0.0,
            "done_qty": 0.0,
            "billed_qty": 0.0,
            "balance_qty": 0.0,
            "pending_billing_qty": 0.0,
            "unit": "",
            "boq_number": "",
            "description": "",
        }
    total_qty = float(boq_df.iloc[0]["quantity"] or 0)
    unit = boq_df.iloc[0]["unit"] or ""
    done_qty = scalar_query(
        """
        SELECT COALESCE(SUM(progress_quantity), 0) FROM dpr_reports
        WHERE boq_item_id = ? AND COALESCE(status, '') NOT IN ('Draft', 'Rejected')
        """,
        (boq_item_id,),
    )
    billed_qty = scalar_query(
        """
        SELECT COALESCE(SUM(billed_quantity), 0) FROM dpr_reports
        WHERE boq_item_id = ? AND UPPER(COALESCE(billing_measurement, '')) = 'YES'
          AND COALESCE(status, '') IN ('Engineer Approved', 'Client Approved', 'Billed')
        """,
        (boq_item_id,),
    )
    pending_billing = scalar_query(
        """
        SELECT COALESCE(SUM(progress_quantity), 0) FROM dpr_reports
        WHERE boq_item_id = ? AND UPPER(COALESCE(billing_measurement, '')) = 'YES'
          AND COALESCE(status, '') IN ('Engineer Approved', 'Client Approved')
          AND COALESCE(billed_quantity, 0) < COALESCE(progress_quantity, 0)
        """,
        (boq_item_id,),
    )
    conn.close()
    balance_qty = max(total_qty - float(done_qty), 0.0)
    return {
        "total_qty": total_qty,
        "done_qty": float(done_qty),
        "billed_qty": float(billed_qty),
        "balance_qty": balance_qty,
        "pending_billing_qty": float(pending_billing),
        "unit": unit,
        "boq_number": boq_df.iloc[0]["boq_number"] or "",
        "description": boq_df.iloc[0]["description"] or "",
    }


def load_company_staff_for_select():
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT employee_id, employee_name, COALESCE(designation, '') AS designation
        FROM employees
        WHERE COALESCE(employee_type, '') = 'Company Staff'
          AND COALESCE(status, 'Active') IN ('Active', 'ACTIVE')
        ORDER BY employee_name
        """,
        conn,
    )
    conn.close()
    return df


def load_lookup(table, column):
    conn = get_conn()
    df = pd.read_sql_query(
        f"SELECT {column} AS value FROM {table} WHERE COALESCE({column}, '') != '' ORDER BY value",
        conn,
    )
    conn.close()
    return df["value"].tolist() if not df.empty else []


def get_dashboard_settings():
    defaults = {
        "show_welcome": True,
        "show_kpis": True,
        "show_attendance_overview": True,
        "show_project_overview": True,
        "show_expense_overview": True,
        "show_recent_payments": True,
        "show_notifications": True,
        "show_sidebar_cashflow": True,
        "section_order": DASHBOARD_SECTION_ORDER_DEFAULT[:],
    }
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT setting_key, setting_value
        FROM app_settings
        WHERE setting_key LIKE 'dashboard_%'
        """,
        conn,
    )
    conn.close()
    if df.empty:
        return defaults

    settings = defaults.copy()
    for _, row in df.iterrows():
        key = row["setting_key"].replace("dashboard_", "", 1)
        raw_value = str(row["setting_value"]).strip()
        if key == "section_order":
            order = [item.strip() for item in raw_value.split(",") if item.strip() in DASHBOARD_SECTION_LABELS]
            remaining = [item for item in DASHBOARD_SECTION_ORDER_DEFAULT if item not in order]
            settings[key] = order + remaining
        elif not key.startswith("role_"):
            settings[key] = raw_value in {"1", "true", "True", "yes", "on"}
    return settings


def save_dashboard_settings(settings):
    conn = get_conn()
    cur = conn.cursor()
    for key, value in settings.items():
        if isinstance(value, list):
            setting_value = ",".join(value)
        elif isinstance(value, bool):
            setting_value = "1" if value else "0"
        else:
            setting_value = str(value)
        cur.execute(
            """
            INSERT INTO app_settings(setting_key, setting_value)
            VALUES(?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
            """,
            (f"dashboard_{key}", setting_value),
        )
    conn.commit()
    conn.close()


def get_dashboard_role_visibility():
    role_visibility = {
        role: {section_key: True for section_key in DASHBOARD_SECTION_ORDER_DEFAULT}
        for role in DASHBOARD_ROLES
    }
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT setting_key, setting_value
        FROM app_settings
        WHERE setting_key LIKE 'dashboard_role_%'
        """,
        conn,
    )
    conn.close()
    for _, row in df.iterrows():
        key = str(row["setting_key"])
        raw_value = str(row["setting_value"]).strip() in {"1", "true", "True", "yes", "on"}
        prefix = "dashboard_role_"
        if not key.startswith(prefix):
            continue
        for role_name in DASHBOARD_ROLES:
            role_prefix = f"{prefix}{role_name}_"
            if not key.startswith(role_prefix):
                continue
            section_key = key[len(role_prefix):]
            if section_key in DASHBOARD_SECTION_LABELS:
                role_visibility[role_name][section_key] = raw_value
            break
    return role_visibility


def save_dashboard_role_visibility(role_visibility):
    conn = get_conn()
    cur = conn.cursor()
    for role, section_map in role_visibility.items():
        for section_key, enabled in section_map.items():
            cur.execute(
                """
                INSERT INTO app_settings(setting_key, setting_value)
                VALUES(?, ?)
                ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
                """,
                (
                    f"dashboard_role_{role}_{section_key}",
                    "1" if enabled else "0",
                ),
            )
    conn.commit()
    conn.close()


def load_countries():
    countries = load_lookup("countries", "country_name")
    return countries if countries else ["India"]


def load_regions(country=None):
    conn = get_conn()
    if country:
        df = pd.read_sql_query(
            """
            SELECT r.region_name AS value
            FROM regions r
            JOIN countries c ON c.id = r.country_id
            WHERE COALESCE(r.region_name, '') != '' AND c.country_name = ?
            ORDER BY r.region_name
            """,
            conn,
            params=(country,),
        )
    else:
        df = pd.read_sql_query(
            """
            SELECT DISTINCT region_name AS value
            FROM regions
            WHERE COALESCE(region_name, '') != ''
            ORDER BY region_name
            """,
            conn,
        )
    conn.close()
    return df["value"].tolist() if not df.empty else []


def load_districts(country=None, region=None):
    conn = get_conn()
    sql = """
        SELECT d.district_name AS value
        FROM districts d
        LEFT JOIN regions r ON r.id = d.region_id
        LEFT JOIN countries c ON c.id = r.country_id
        WHERE COALESCE(d.district_name, '') != ''
    """
    params = []
    if country:
        sql += " AND c.country_name = ?"
        params.append(country)
    if region:
        sql += " AND r.region_name = ?"
        params.append(region)
    sql += " ORDER BY d.district_name"
    df = pd.read_sql_query(sql, conn, params=params or None)
    conn.close()
    return df["value"].tolist() if not df.empty else []


def load_managers(country=None, region=None, district=None):
    conn = get_conn()
    sql = "SELECT manager_name FROM managers WHERE COALESCE(manager_name, '') != ''"
    params = []
    if country:
        sql += " AND COALESCE(country, '') = ?"
        params.append(country)
    if region:
        sql += " AND COALESCE(region, '') = ?"
        params.append(region)
    if district:
        sql += " AND COALESCE(district, '') = ?"
        params.append(district)
    sql += " ORDER BY manager_name"
    df = pd.read_sql_query(sql, conn, params=params or None)
    conn.close()
    names = df["manager_name"].tolist() if not df.empty else []
    return names if names else ["— No manager —"]


def ensure_country(country_name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM countries WHERE LOWER(country_name) = LOWER(?)", (country_name,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0]
    cur.execute("INSERT INTO countries(country_name) VALUES(?)", (country_name,))
    conn.commit()
    country_id = cur.lastrowid
    conn.close()
    return country_id


def ensure_region(country_name, region_name):
    country_id = ensure_country(country_name)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE regions SET country_id = ?
        WHERE LOWER(region_name) = LOWER(?) AND COALESCE(country_id, 0) = 0
        """,
        (country_id, region_name),
    )
    cur.execute(
        "SELECT id FROM regions WHERE LOWER(region_name) = LOWER(?) AND COALESCE(country_id, 0) = ?",
        (region_name, country_id),
    )
    row = cur.fetchone()
    if row:
        conn.commit()
        conn.close()
        return row[0]
    cur.execute("INSERT INTO regions(country_id, region_name) VALUES(?, ?)", (country_id, region_name))
    conn.commit()
    region_id = cur.lastrowid
    conn.close()
    return region_id


def ensure_district(country_name, region_name, district_name):
    region_id = ensure_region(country_name, region_name)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM districts WHERE LOWER(district_name) = LOWER(?) AND COALESCE(region_id, 0) = ?",
        (district_name, region_id),
    )
    row = cur.fetchone()
    if row:
        conn.close()
        return row[0]
    cur.execute("INSERT INTO districts(region_id, district_name) VALUES(?, ?)", (region_id, district_name))
    conn.commit()
    district_id = cur.lastrowid
    conn.close()
    return district_id


def load_subcontractor_names():
    return load_lookup("subcontractors", "subcontractor_name")


def load_subcontractor_labour_rate(subcontractor_name, project_name, labour_type, working_hours):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT *
        FROM subcontractor_labour_rates
        WHERE COALESCE(subcontractor_name, '') = ?
          AND COALESCE(project_name, '') = ?
          AND COALESCE(labour_type, '') = ?
          AND COALESCE(working_hours, '') = ?
          AND UPPER(COALESCE(status, 'ACTIVE')) = 'ACTIVE'
        ORDER BY id DESC
        LIMIT 1
        """,
        conn,
        params=(subcontractor_name, project_name, labour_type, working_hours),
    )
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else None


def load_subcontractor_boq_rates(subcontractor_name=None, project_name=None):
    conn = get_conn()
    sql = """
        SELECT *
        FROM subcontractor_boq_rates
        WHERE UPPER(COALESCE(status, 'ACTIVE')) = 'ACTIVE'
    """
    params = []
    if subcontractor_name:
        sql += " AND COALESCE(subcontractor_name, '') = ?"
        params.append(subcontractor_name)
    if project_name:
        sql += " AND COALESCE(project_name, '') = ?"
        params.append(project_name)
    sql += " ORDER BY project_name, boq_item"
    df = pd.read_sql_query(sql, conn, params=params or None)
    conn.close()
    return df


def parse_month_value(month_value):
    month_text = str(month_value or "").strip()
    if not month_text:
        return ""
    if len(month_text) == 7 and month_text[2] == "/":
        return month_text
    return datetime.strptime(month_text, "%Y-%m-%d").strftime("%m/%Y")


def attendance_month_filter_sql(date_column, payroll_month):
    if not payroll_month:
        return "", []
    month, year = payroll_month.split("/")
    return f" AND {date_column} LIKE ?", [f"%/{month}/{year}"]


def subcontractor_bill_preview(subcontractor_name, bill_month):
    payroll_month = parse_month_value(bill_month)
    month_filter, params = attendance_month_filter_sql("attendance_date", payroll_month)

    conn = get_conn()
    labour_df = pd.read_sql_query(
        f"""
        SELECT COALESCE(applied_rate, 0) AS applied_rate,
               COALESCE(ot_hours, 0) AS ot_hours,
               COALESCE(applied_ot_rate, 0) AS applied_ot_rate
        FROM attendance
        WHERE COALESCE(sub_contractor, '') = ? {month_filter}
        """,
        conn,
        params=[subcontractor_name] + params,
    )
    boq_df = pd.read_sql_query(
        """
        SELECT COALESCE(amount, 0) AS amount
        FROM subcontractor_boq_entries
        WHERE COALESCE(subcontractor_name, '') = ?
          AND strftime('%m/%Y', substr(entry_date, 7, 4) || '-' || substr(entry_date, 4, 2) || '-01') = ?
        """,
        conn,
        params=(subcontractor_name, payroll_month),
    )
    advance_df = pd.read_sql_query(
        """
        SELECT COALESCE(amount, 0) AS amount
        FROM subcontractor_advance
        WHERE COALESCE(subcontractor_name, '') = ?
          AND COALESCE(advance_date, '') LIKE ?
        """,
        conn,
        params=(subcontractor_name, f"%/{payroll_month}"),
    ) if "advance_date" in _columns(conn.cursor(), "subcontractor_advance") else pd.DataFrame(columns=["amount"])
    conn.close()

    labour_amount = float(labour_df["applied_rate"].sum()) if not labour_df.empty else 0.0
    ot_amount = float((labour_df["ot_hours"] * labour_df["applied_ot_rate"]).sum()) if not labour_df.empty else 0.0
    boq_amount = float(boq_df["amount"].sum()) if not boq_df.empty else 0.0
    advance_amount = float(advance_df["amount"].sum()) if not advance_df.empty else 0.0
    total_amount = labour_amount + ot_amount + boq_amount
    net_amount = max(0.0, total_amount - advance_amount)
    return {
        "bill_month": payroll_month,
        "labour_amount": round(labour_amount, 2),
        "ot_amount": round(ot_amount, 2),
        "boq_amount": round(boq_amount, 2),
        "advance_amount": round(advance_amount, 2),
        "total_amount": round(total_amount, 2),
        "net_amount": round(net_amount, 2),
    }


def subcontractor_manpower_bill_preview(subcontractor_name, bill_month):
    preview = subcontractor_bill_preview(subcontractor_name, bill_month)
    total = preview["labour_amount"] + preview["ot_amount"]
    return {
        **preview,
        "total_amount": round(total, 2),
        "net_amount": round(max(0.0, total - preview["advance_amount"]), 2),
        "boq_amount": 0.0,
    }


def subcontractor_quantity_bill_preview(subcontractor_name, bill_month):
    preview = subcontractor_bill_preview(subcontractor_name, bill_month)
    total = preview["boq_amount"]
    return {
        **preview,
        "labour_amount": 0.0,
        "ot_amount": 0.0,
        "total_amount": round(total, 2),
        "net_amount": round(max(0.0, total - preview["advance_amount"]), 2),
    }


def load_pending_client_bill_dprs():
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT r.dpr_id, r.dpr_date, r.project_name,
               COALESCE(NULLIF(r.client_name, ''), p.client_name, '') AS client_name,
               r.boq_number, r.boq_description,
               r.unit, r.billed_quantity, COALESCE(r.client_billed_quantity, 0) AS client_billed_quantity,
               (r.billed_quantity - COALESCE(r.client_billed_quantity, 0)) AS pending_qty,
               r.boq_item_id, COALESCE(b.approved_rate, 0) AS approved_rate
        FROM dpr_reports r
        LEFT JOIN project_boq_items b ON b.boq_item_id = r.boq_item_id
        LEFT JOIN projects p ON p.project_name = r.project_name
        WHERE UPPER(COALESCE(r.billing_measurement, '')) = 'YES'
          AND COALESCE(r.billed_quantity, 0) > COALESCE(r.client_billed_quantity, 0)
          AND r.status IN ('Engineer Approved', 'Client Approved', 'Billed')
        ORDER BY r.id DESC
        """,
        conn,
    )
    conn.close()
    return df


def get_boq_approved_rate(boq_item_id):
    return scalar_query(
        "SELECT COALESCE(approved_rate, 0) FROM project_boq_items WHERE boq_item_id = ?",
        (boq_item_id,),
    )


def load_active_holidays(attendance_date=None, applicable_for=None, project_name=None, approval_status="Approved"):
    conn = get_conn()
    sql = """
        SELECT *
        FROM holiday_master
        WHERE COALESCE(approval_status, 'Approved') = ?
    """
    params = [approval_status]
    if attendance_date:
        sql += " AND holiday_date = ?"
        params.append(attendance_date)
    if applicable_for:
        sql += " AND applicable_for IN (?, 'All')"
        params.append(applicable_for)
    if project_name:
        sql += " AND COALESCE(project_name, 'All Projects') IN ('All Projects', ?, '')"
        params.append(project_name)
    sql += " ORDER BY holiday_date, holiday_name"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def load_weekly_off_rules(applicable_for=None, project_name=None):
    conn = get_conn()
    sql = """
        SELECT *
        FROM weekly_off_settings
        WHERE UPPER(COALESCE(status, 'ACTIVE')) = 'ACTIVE'
    """
    params = []
    if applicable_for:
        sql += " AND applicable_for IN (?, 'All')"
        params.append(applicable_for)
    if project_name:
        sql += " AND COALESCE(project_name, 'All Projects') IN ('All Projects', ?, '')"
        params.append(project_name)
    sql += " ORDER BY weekly_off_day"
    df = pd.read_sql_query(sql, conn, params=params or None)
    conn.close()
    return df


def load_client_names():
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT COALESCE(company_name, client_name) AS value
        FROM clients
        WHERE COALESCE(company_name, client_name, '') != ''
        ORDER BY value
        """,
        conn,
    )
    conn.close()
    return df["value"].tolist() if not df.empty else []


def load_project_names():
    return load_lookup("projects", "project_name")


def load_employee_options():
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT employee_id, employee_name
        FROM employees
        WHERE COALESCE(employee_id, '') != ''
        ORDER BY employee_name
        """,
        conn,
    )
    conn.close()
    return [(row.employee_id, row.employee_name) for _, row in df.iterrows()]


def get_employee(employee_id):
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM employees WHERE employee_id = ? LIMIT 1",
        conn,
        params=(employee_id,),
    )
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else None


def next_worker_id(sub_name):
    code = (sub_name[:2] if sub_name else "WK").upper()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM workers WHERE subcontractor_name=?", (sub_name,))
    count = cur.fetchone()[0] + 101
    conn.close()
    return f"{code}{count}"


def calculate_hours(start, end, break_hr, fixed_hours=8.0, ot_allowed=True):
    fmt = "%H:%M"
    start_time = datetime.strptime(start, fmt)
    end_time = datetime.strptime(end, fmt)
    total = (end_time - start_time).seconds / 3600
    worked = max(0.0, total - float(break_hr))
    overtime = max(0.0, worked - float(fixed_hours or 8)) if ot_allowed else 0.0
    return round(worked, 2), round(overtime, 2)


def _employee_applicable_for(employee):
    return "Company Staff" if employee.get("employee_type") == "Company Staff" else "Sub Contractor Workers"


def _parse_working_hours_label(value):
    text = str(value or "").strip()
    if not text:
        return 8.0
    try:
        return float(text.split()[0])
    except (ValueError, IndexError):
        return 8.0


def _month_date_range(payroll_month):
    month, year = payroll_month.split("/")
    start_date = datetime.strptime(f"01/{month}/{year}", DATE_FMT)
    if int(month) == 12:
        next_month = datetime.strptime(f"01/01/{int(year) + 1}", DATE_FMT)
    else:
        next_month = datetime.strptime(f"01/{int(month) + 1:02d}/{year}", DATE_FMT)
    return start_date, next_month


def _extra_paid_non_working_days(employee, payroll_month, attendance_dates):
    if not payroll_month:
        return {"count": 0, "dates": []}

    applicable_for = _employee_applicable_for(employee)
    project_name = employee.get("project_name", "")
    start_date, next_month = _month_date_range(payroll_month)
    paid_dates = []

    conn = get_conn()
    holiday_df = pd.read_sql_query(
        """
        SELECT holiday_date, payment_type
        FROM holiday_master
        WHERE COALESCE(approval_status, 'Approved') = 'Approved'
          AND applicable_for IN (?, 'All')
          AND COALESCE(project_name, 'All Projects') IN ('All Projects', ?, '')
        """,
        conn,
        params=(applicable_for, project_name),
    )
    weekly_df = pd.read_sql_query(
        """
        SELECT weekly_off_day, payment_type
        FROM weekly_off_settings
        WHERE UPPER(COALESCE(status, 'ACTIVE')) = 'ACTIVE'
          AND applicable_for IN (?, 'All')
          AND COALESCE(project_name, 'All Projects') IN ('All Projects', ?, '')
        """,
        conn,
        params=(applicable_for, project_name),
    )
    conn.close()

    for _, row in holiday_df.iterrows():
        if str(row.get("payment_type", "")).strip().lower() != "paid":
            continue
        holiday_date = datetime.strptime(row["holiday_date"], DATE_FMT)
        if start_date <= holiday_date < next_month:
            date_str = holiday_date.strftime(DATE_FMT)
            if date_str not in attendance_dates:
                paid_dates.append(date_str)

    current_date = start_date
    weekly_paid_days = {
        str(row["weekly_off_day"]).strip().lower()
        for _, row in weekly_df.iterrows()
        if str(row.get("payment_type", "")).strip().lower() == "paid"
    }
    while current_date < next_month:
        if current_date.strftime("%A").lower() in weekly_paid_days:
            date_str = current_date.strftime(DATE_FMT)
            if date_str not in attendance_dates and date_str not in paid_dates:
                paid_dates.append(date_str)
        current_date += pd.Timedelta(days=1)

    return {"count": len(paid_dates), "dates": paid_dates}


def payroll_preview(employee_id, payroll_month=None):
    employee = get_employee(employee_id)
    if not employee:
        return {"base_salary": 0.0, "ot_amount": 0.0, "deductions": 0.0, "net_salary": 0.0}

    conn = get_conn()
    month_filter = ""
    params = [employee_id]
    if payroll_month:
        month, year = payroll_month.split("/")
        month_filter = " AND attendance_date LIKE ?"
        params.append(f"%/{month}/{year}")

    attendance = pd.read_sql_query(
        f"""
        SELECT COALESCE(total_hours, worked_hours, 0) AS total_hours,
               COALESCE(ot_hours, overtime, 0) AS ot_hours,
               COALESCE(applied_rate, 0) AS applied_rate,
               COALESCE(applied_ot_rate, 0) AS applied_ot_rate,
               COALESCE(attendance_date, '') AS attendance_date
        FROM attendance
        WHERE COALESCE(employee_id, worker_id) = ? {month_filter}
        """,
        conn,
        params=params,
    )
    conn.close()

    ot_hours = float(attendance["ot_hours"].sum()) if not attendance.empty else 0.0
    working_days = len(attendance.index)
    salary_type = (employee.get("salary_type") or "Monthly").lower()
    salary_amount = float(employee.get("salary_amount") or 0)
    attendance_dates = set(attendance["attendance_date"].tolist()) if not attendance.empty else set()
    extra_paid_days = _extra_paid_non_working_days(employee, payroll_month, attendance_dates)

    if salary_type == "daily":
        attendance_base = float(attendance["applied_rate"].sum()) if not attendance.empty else 0.0
        base_salary = attendance_base if attendance_base > 0 else working_days * salary_amount
        if extra_paid_days["count"]:
            daily_rate = (attendance_base / working_days) if attendance_base > 0 and working_days else salary_amount
            base_salary += extra_paid_days["count"] * daily_rate
    else:
        base_salary = salary_amount

    if not attendance.empty and float(attendance["applied_ot_rate"].sum()) > 0:
        ot_amount = float((attendance["ot_hours"] * attendance["applied_ot_rate"]).sum())
    else:
        ot_amount = ot_hours * float(employee.get("ot_rate") or 0) if (employee.get("ot_applicable") or "").lower() == "yes" else 0.0
    deductions = 0.0
    net_salary = max(0.0, base_salary + ot_amount - deductions)
    return {
        "base_salary": round(base_salary, 2),
        "ot_amount": round(ot_amount, 2),
        "deductions": round(deductions, 2),
        "net_salary": round(net_salary, 2),
        "working_days": working_days,
        "ot_hours": round(ot_hours, 2),
        "paid_non_working_days": extra_paid_days["count"],
    }


def kpi_stats():
    today = datetime.now().strftime(DATE_FMT)
    employee_count = table_count("employees") or (table_count("staff") + table_count("workers"))
    worker_count = scalar_query("SELECT COUNT(*) FROM employees WHERE employee_type='Sub Contractor Worker'") or table_count("workers")
    active_workers = scalar_query("SELECT COUNT(*) FROM employees WHERE employee_type='Sub Contractor Worker' AND UPPER(COALESCE(status,'ACTIVE'))='ACTIVE'") or scalar_query("SELECT COUNT(*) FROM workers WHERE UPPER(COALESCE(status,'ACTIVE'))='ACTIVE'")
    active_projects = scalar_query(
        """
        SELECT COUNT(*) FROM projects
        WHERE UPPER(COALESCE(status,'')) IN ('ACTIVE', 'ON GOING')
           OR COALESCE(status,'') = 'On Going'
        """
    )
    pending_salary = scalar_query(
        """
        SELECT COUNT(*) FROM employees e
        WHERE COALESCE(employee_type, '') = 'Sub Contractor Worker'
          AND NOT EXISTS (
            SELECT 1 FROM payroll p
            WHERE p.employee_id = e.employee_id AND UPPER(COALESCE(p.salary_status,''))='PAID'
          )
        """
    )
    attendance_today = scalar_query("SELECT COUNT(*) FROM attendance WHERE attendance_date = ?", (today,))
    monthly_expense = sum_query(
        """
        SELECT COALESCE(SUM(amount),0) FROM expenses
        """
    ) + sum_query(
        """
        SELECT COALESCE(SUM(amount),0) FROM finance_transactions
        WHERE transaction_type = 'expense_voucher' AND status = ?
        """,
        (FINANCE_STATUS_SETTLED,),
    )
    cash_in = sum_query("SELECT COALESCE(SUM(amount),0) FROM payments") + sum_query(
        """
        SELECT COALESCE(SUM(amount),0) FROM finance_transactions
        WHERE transaction_type = 'cash_receipt' AND status = ?
        """,
        (FINANCE_STATUS_SETTLED,),
    )
    finance_out = sum_query(
        """
        SELECT COALESCE(SUM(amount),0) FROM finance_transactions
        WHERE transaction_type IN ('payment_out', 'petty_cash_issue') AND status = ?
        """,
        (FINANCE_STATUS_SETTLED,),
    )
    cash_out = (
        monthly_expense
        + finance_out
        + sum_query(
            "SELECT COALESCE(SUM(net_salary), COALESCE(SUM(salary),0)) FROM payroll WHERE UPPER(COALESCE(salary_status,''))='PAID'"
        )
        + sum_query("SELECT COALESCE(SUM(amount),0) FROM subcontractor_advance")
    )
    return {
        "employees": employee_count,
        "total_workers": worker_count,
        "active_workers": active_workers,
        "projects": active_projects or table_count("projects"),
        "active_projects": active_projects or table_count("projects"),
        "pending_salary": pending_salary,
        "attendance_today": attendance_today,
        "clients": table_count("clients"),
        "subcontractors": table_count("subcontractors"),
        "users": table_count("users"),
        "advances": table_count("subcontractor_advance"),
        "monthly_expense": monthly_expense,
        "cash_in": cash_in,
        "cash_out": cash_out,
        "cash_in_hand": cash_in - cash_out,
    }


def dashboard_recent_transactions(limit=5):
    conn = get_conn()
    df = pd.read_sql_query(
        f"""
        SELECT voucher_number AS voucher_no, payment_date AS entry_date, payment_type,
               pay_to_name AS pay_to, COALESCE(project_name, '') AS project_name,
               amount, COALESCE(status, 'Paid') AS status
        FROM payments
        UNION ALL
        SELECT expense_id AS voucher_no, expense_date AS entry_date, expense_head AS payment_type,
               paid_to AS pay_to, COALESCE(project_name, '') AS project_name,
               amount, 'Expense' AS status
        FROM expenses
        UNION ALL
        SELECT transaction_id AS voucher_no, transaction_date AS entry_date, transaction_type AS payment_type,
               pay_to_name AS pay_to, COALESCE(project_name, '') AS project_name,
               amount, status
        FROM finance_transactions
        UNION ALL
        SELECT payroll_id AS voucher_no, paid_date AS entry_date, 'Salary Payment' AS payment_type,
               COALESCE(employee_id, worker_id) AS pay_to, '' AS project_name,
               COALESCE(net_salary, salary, 0) AS amount, salary_status AS status
        FROM payroll
        ORDER BY entry_date DESC, voucher_no DESC
        LIMIT {int(limit)}
        """,
        conn,
    )
    conn.close()
    return df


def dashboard_notifications():
    stats = kpi_stats()
    notes = []
    if stats["pending_salary"]:
        notes.append({"title": f"Salary for {int(stats['pending_salary'])} workers is pending.", "detail": "Review payroll and process this month."})
    if stats["attendance_today"]:
        notes.append({"title": f"{int(stats['attendance_today'])} attendance entries captured today.", "detail": "Daily attendance is updating labor summaries."})
    if stats["active_projects"]:
        notes.append({"title": f"{int(stats['active_projects'])} active projects are running.", "detail": "Track project labor, expenses, and payments."})
    notes.append({"title": "Masters are ready for setup.", "detail": "Manage regions, departments, designations, and users from Settings."})
    return notes[:4]
