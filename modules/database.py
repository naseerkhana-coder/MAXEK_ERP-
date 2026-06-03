"""SQLite setup, migrations, and helpers for MAXEK ERP."""

import json
import os
import sqlite3
from datetime import datetime

import pandas as pd

from modules.regions import DEFAULT_LOCATION_TREE

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "maxek_payroll.db")
DATE_FMT = "%d/%m/%Y"
DATE_INPUT_FMT = "DD/MM/YYYY"
DASHBOARD_SECTION_ORDER_DEFAULT = [
    "welcome",
    "kpis",
    "cash_flow",
    "overviews",
    "recent_payments",
    "notifications",
]
DASHBOARD_SECTION_LABELS = {
    "welcome": "Welcome Header",
    "kpis": "KPI Cards",
    "cash_flow": "Daily Cash Flow",
    "overviews": "Overview Panels",
    "recent_payments": "Recent Payments",
    "notifications": "Notifications",
}
DASHBOARD_ROLES = [
    "Super Admin",
    "Admin",
    "MD",
    "HR & Payroll",
    "HR",
    "Accountant",
    "Accounts Manager",
    "Accounts Executive",
    "Project Manager",
    "Site Engineer",
    "Store Keeper",
]

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
FINANCE_STATUS_VOIDED = "Voided"
FINANCE_STATUS_POSTED = "Posted"

DOCUMENT_PREFIXES = {
    "expense_entry": "EXP",
    "purchase_invoice": "PINV",
    "payment_voucher": "PV",
    "receipt_voucher": "RV",
    "journal_voucher": "JV",
    "petty_cash_issue": "PCI",
    "material_request": "MR",
    "subcontractor_bill": "SCB",
    "inward_letter": "INW",
    "outward_letter": "OUT",
}

DEFAULT_LEDGER_ACCOUNTS = {
    "material_purchase": "Material Purchase",
    "material_cost": "Material Cost",
    "gst_input": "GST Input",
    "gst_payable": "GST Payable",
    "supplier": "Supplier",
    "creditor": "Creditors",
    "debtor": "Debtors",
    "cash": "Cash",
    "bank": "Bank",
    "petty_cash": "Petty Cash",
    "inventory": "Inventory",
    "general_expense": "General Expense",
    "site_expense": "Site Expense",
    "labour_expense": "Labour Expense",
    "contractor_expense": "Contractor Expense",
    "contract_revenue": "Contract Revenue",
    "salary_expense": "Salary Expense",
    "tds_payable": "TDS Payable",
}

ACCOUNTING_RULES = {
    "material_purchase": [
        ("debit", "material_purchase", "base_amount"),
        ("debit", "gst_input", "gst_amount"),
        ("credit", "supplier", "total_amount"),
    ],
    "supplier_payment": [
        ("debit", "supplier", "amount"),
        ("credit", "bank", "amount"),
    ],
    "petty_cash_expense": [
        ("debit", "site_expense", "amount"),
        ("credit", "petty_cash", "amount"),
    ],
    "tds_deduction": [
        ("debit", "contractor_expense", "amount"),
        ("credit", "tds_payable", "amount"),
    ],
    "gst_payment": [
        ("debit", "gst_payable", "amount"),
        ("credit", "bank", "amount"),
    ],
    "tds_payment": [
        ("debit", "tds_payable", "amount"),
        ("credit", "bank", "amount"),
    ],
}

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
        CREATE TABLE IF NOT EXISTS dpr_steel_shapes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shape_id TEXT,
            shape_code TEXT UNIQUE,
            shape_name TEXT,
            input_unit TEXT,
            terms_json TEXT,
            diagram_hint TEXT,
            is_builtin INTEGER DEFAULT 0,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS dpr_boq_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id TEXT,
            dpr_id TEXT,
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
            progress_quantity REAL
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
            remarks TEXT,
            whatsapp_number TEXT,
            gender TEXT
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
            account_holder_name TEXT,
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
        CREATE TABLE IF NOT EXISTS material_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE,
            project_name TEXT,
            item_name TEXT,
            quantity REAL,
            unit TEXT,
            required_date TEXT,
            remarks TEXT,
            status TEXT DEFAULT 'Pending',
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS expense_invoices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT UNIQUE,
            finance_transaction_id TEXT,
            expense_date TEXT,
            supplier TEXT,
            invoice_no TEXT,
            project_name TEXT,
            exp_type TEXT,
            taxable_amount REAL,
            tax_type TEXT,
            total_cgst REAL,
            total_sgst REAL,
            total_igst REAL,
            total_tax REAL,
            total_invoice_value REAL,
            remarks TEXT,
            payment_status TEXT,
            payment_method TEXT,
            payment_mode TEXT,
            paid_from TEXT,
            bill_upload TEXT,
            tax_slabs_json TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS expense_invoice_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id TEXT,
            invoice_id TEXT,
            item_name TEXT,
            hsn_code TEXT,
            unit TEXT,
            quantity REAL,
            rate REAL,
            amount REAL
        );
        CREATE TABLE IF NOT EXISTS petty_cash_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE,
            request_date TEXT,
            project_name TEXT,
            staff_id TEXT,
            staff_name TEXT,
            requested_by TEXT,
            current_balance REAL,
            requested_amount REAL,
            reason TEXT,
            priority TEXT DEFAULT 'Normal',
            remarks TEXT,
            attachment TEXT,
            status TEXT DEFAULT 'Submitted',
            verified_by TEXT,
            verified_at TEXT,
            approved_by TEXT,
            approved_at TEXT,
            released_by TEXT,
            released_at TEXT,
            released_amount REAL,
            rejection_reason TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS site_expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id TEXT UNIQUE,
            expense_date TEXT,
            project_name TEXT,
            supplier TEXT,
            invoice_no TEXT,
            expense_category TEXT,
            description TEXT,
            quantity REAL,
            rate REAL,
            taxable_amount REAL,
            gst_rate REAL,
            tax_type TEXT,
            total_cgst REAL,
            total_sgst REAL,
            total_igst REAL,
            total_tax REAL,
            total_invoice_value REAL,
            payment_source TEXT DEFAULT 'Petty Cash',
            invoice_upload TEXT,
            bill_photo TEXT,
            supporting_docs TEXT,
            remarks TEXT,
            status TEXT DEFAULT 'Draft',
            submitted_by TEXT,
            submitted_at TEXT,
            verified_by TEXT,
            verified_at TEXT,
            verification_remarks TEXT,
            pm_approved_by TEXT,
            pm_approved_at TEXT,
            pm_remarks TEXT,
            approved_by TEXT,
            approved_at TEXT,
            management_remarks TEXT,
            rejected_by TEXT,
            rejected_at TEXT,
            rejection_reason TEXT,
            returned_by TEXT,
            returned_at TEXT,
            return_reason TEXT,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS site_expense_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id TEXT,
            expense_id TEXT,
            line_no INTEGER,
            item_name TEXT,
            hsn_code TEXT,
            unit TEXT,
            quantity REAL,
            rate REAL,
            taxable_amount REAL,
            gst_rate REAL,
            tax_type TEXT,
            cgst REAL,
            sgst REAL,
            igst REAL,
            line_tax REAL,
            line_total REAL
        );
        CREATE TABLE IF NOT EXISTS direct_payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT UNIQUE,
            payment_date TEXT,
            payment_type TEXT,
            project_name TEXT,
            party_name TEXT,
            amount REAL,
            payment_method TEXT,
            reference_number TEXT,
            attachment TEXT,
            remarks TEXT,
            status TEXT DEFAULT 'Submitted',
            verified_by TEXT,
            verified_at TEXT,
            approved_by TEXT,
            approved_at TEXT,
            paid_by TEXT,
            paid_at TEXT,
            rejection_reason TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS finance_audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT,
            entity_id TEXT,
            action TEXT,
            actor TEXT,
            action_at TEXT,
            old_status TEXT,
            new_status TEXT,
            comments TEXT,
            changes_json TEXT
        );
        CREATE TABLE IF NOT EXISTS document_sequences(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_type TEXT NOT NULL,
            year INTEGER NOT NULL,
            last_number INTEGER NOT NULL DEFAULT 0,
            UNIQUE(doc_type, year)
        );
        CREATE TABLE IF NOT EXISTS chart_of_accounts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_code TEXT UNIQUE,
            account_name TEXT UNIQUE,
            account_type TEXT,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS journal_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_id TEXT UNIQUE,
            document_no TEXT,
            entry_date TEXT,
            source_type TEXT,
            source_id TEXT,
            narration TEXT,
            total_debit REAL,
            total_credit REAL,
            status TEXT DEFAULT 'Posted',
            posted_by TEXT,
            posted_at TEXT
        );
        CREATE TABLE IF NOT EXISTS ledger_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id TEXT UNIQUE,
            journal_id TEXT,
            account_name TEXT,
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            project_name TEXT,
            party_name TEXT,
            remarks TEXT
        );
        CREATE TABLE IF NOT EXISTS project_finance_settings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT UNIQUE,
            petty_cash_limit REAL DEFAULT 0,
            expense_budget REAL DEFAULT 0,
            petty_cash_handler_id TEXT,
            petty_cash_handler_name TEXT,
            updated_by TEXT,
            updated_at TEXT
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
        CREATE TABLE IF NOT EXISTS employee_advance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            advance_id TEXT,
            employee_id TEXT,
            employee_name TEXT,
            advance_date TEXT,
            amount REAL,
            remarks TEXT,
            deducted_payroll_id TEXT
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
            state TEXT,
            whatsapp_number TEXT,
            gender TEXT
        );
        CREATE TABLE IF NOT EXISTS company_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT UNIQUE,
            company_name TEXT,
            gst_number TEXT,
            address TEXT,
            phone TEXT,
            email TEXT,
            financial_year TEXT,
            updated_by TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS vendors(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id TEXT UNIQUE,
            vendor_type TEXT,
            supplier_name TEXT,
            gst_number TEXT,
            contact_person TEXT,
            mobile TEXT,
            email TEXT,
            address TEXT,
            status TEXT DEFAULT 'Active',
            subcontractor_id TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS expense_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id TEXT UNIQUE,
            document_no TEXT,
            expense_date TEXT,
            project_name TEXT,
            expense_head TEXT,
            amount REAL,
            status TEXT DEFAULT 'Submitted',
            entered_by TEXT,
            approved_by TEXT,
            remarks TEXT,
            journal_id TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS payment_vouchers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_id TEXT UNIQUE,
            voucher_no TEXT,
            supplier TEXT,
            payment_date TEXT,
            payment_mode TEXT,
            amount REAL,
            reference_no TEXT,
            project_name TEXT,
            status TEXT DEFAULT 'Submitted',
            journal_id TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS receipt_vouchers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_id TEXT UNIQUE,
            voucher_no TEXT,
            customer TEXT,
            receipt_date TEXT,
            amount REAL,
            mode TEXT,
            project_name TEXT,
            reference_no TEXT,
            status TEXT DEFAULT 'Submitted',
            journal_id TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS petty_cash_issues(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id TEXT UNIQUE,
            issue_no TEXT,
            employee_id TEXT,
            employee_name TEXT,
            site TEXT,
            issue_amount REAL,
            issue_date TEXT,
            status TEXT DEFAULT 'Issued',
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS petty_cash_expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_no TEXT UNIQUE,
            employee_id TEXT,
            employee_name TEXT,
            site TEXT,
            expense_type TEXT,
            amount REAL,
            bill_upload TEXT,
            status TEXT DEFAULT 'Submitted',
            journal_id TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS gst_ledger(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT,
            invoice_ref TEXT,
            supplier TEXT,
            gst_type TEXT,
            gst_amount REAL,
            source_type TEXT,
            source_id TEXT
        );
        CREATE TABLE IF NOT EXISTS gst_payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT UNIQUE,
            challan_no TEXT,
            period TEXT,
            payment_date TEXT,
            amount REAL,
            journal_id TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tds_deductions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deduction_id TEXT UNIQUE,
            vendor TEXT,
            invoice_ref TEXT,
            section TEXT,
            tds_pct REAL,
            amount REAL,
            journal_id TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tds_payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT UNIQUE,
            challan_no TEXT,
            period TEXT,
            payment_date TEXT,
            amount REAL,
            journal_id TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS subcontractor_work_orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wo_id TEXT UNIQUE,
            wo_number TEXT,
            project_name TEXT,
            subcontractor_name TEXT,
            value REAL,
            status TEXT DEFAULT 'Active',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS subcontractor_bill_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_entry_id TEXT UNIQUE,
            bill_no TEXT,
            document_no TEXT,
            project_name TEXT,
            subcontractor_name TEXT,
            gross_amount REAL,
            gst REAL,
            tds REAL,
            security_deposit REAL,
            net_amount REAL,
            status TEXT DEFAULT 'Submitted',
            journal_id TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS security_deposit_register(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            register_id TEXT UNIQUE,
            contractor TEXT,
            project_name TEXT,
            retained_amount REAL,
            released_amount REAL,
            balance REAL,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS material_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id TEXT UNIQUE,
            material_code TEXT,
            material_name TEXT,
            unit TEXT,
            status TEXT DEFAULT 'Active'
        );
        CREATE TABLE IF NOT EXISTS stock_register(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id TEXT UNIQUE,
            material_code TEXT,
            material_name TEXT,
            opening_qty REAL DEFAULT 0,
            received REAL DEFAULT 0,
            issued REAL DEFAULT 0,
            balance REAL DEFAULT 0,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS material_issues(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id TEXT UNIQUE,
            issue_no TEXT,
            project_name TEXT,
            material_code TEXT,
            material_name TEXT,
            quantity REAL,
            issue_date TEXT,
            status TEXT DEFAULT 'Issued',
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS asset_register(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT UNIQUE,
            asset_code TEXT,
            asset_name TEXT,
            purchase_date TEXT,
            cost REAL,
            location TEXT,
            assigned_to TEXT,
            status TEXT DEFAULT 'Active'
        );
        CREATE TABLE IF NOT EXISTS asset_transfers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_id TEXT UNIQUE,
            asset_id TEXT,
            from_location TEXT,
            to_location TEXT,
            transfer_date TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS asset_depreciation(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            depreciation_id TEXT UNIQUE,
            asset_id TEXT,
            period TEXT,
            amount REAL,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tools_register(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_id TEXT UNIQUE,
            tool_code TEXT,
            tool_name TEXT,
            project_name TEXT,
            quantity REAL DEFAULT 1,
            condition TEXT DEFAULT 'Good',
            status TEXT DEFAULT 'Available',
            updated_at TEXT
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
            ("gst_number", "TEXT"),
            ("vendor_type", "TEXT"),
            ("email", "TEXT"),
            ("mobile", "TEXT"),
        ),
        "workers": (
            ("region", "TEXT"),
            ("manager_name", "TEXT"),
            ("whatsapp_number", "TEXT"),
            ("gender", "TEXT"),
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
            ("present", "INTEGER DEFAULT 1"),
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
        "dpr_measurements": (
            ("measurement_method", "TEXT"),
            ("qty", "REAL"),
            ("avg_depth", "REAL"),
            ("dimensions_json", "TEXT"),
            ("boq_item_id", "TEXT"),
            ("boq_line_id", "TEXT"),
        ),
        "dpr_reports": (
            ("client_billed_quantity", "REAL"),
            ("client_name", "TEXT"),
            ("rejection_reason", "TEXT"),
            ("rejected_by", "TEXT"),
            ("rejected_at", "TEXT"),
        ),
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
            ("whatsapp_number", "TEXT"),
            ("gender", "TEXT"),
            ("weekly_off_day", "TEXT"),
            ("paid_holiday_eligibility", "TEXT"),
            ("payroll_status", "TEXT"),
            ("account_holder_name", "TEXT"),
            ("bank_account", "TEXT"),
            ("bank_name", "TEXT"),
            ("ifsc_code", "TEXT"),
            ("branch_name", "TEXT"),
        ),
        "employee_advance": (
            ("employee_id", "TEXT"),
            ("employee_name", "TEXT"),
            ("advance_date", "TEXT"),
            ("amount", "REAL"),
            ("remarks", "TEXT"),
            ("deducted_payroll_id", "TEXT"),
            ("payment_mode", "TEXT"),
            ("reason", "TEXT"),
            ("approved_by", "TEXT"),
            ("payment_status", "TEXT"),
            ("approved_at", "TEXT"),
            ("paid_at", "TEXT"),
            ("paid_by", "TEXT"),
            ("created_by", "TEXT"),
            ("created_at", "TEXT"),
            ("funding_source", "TEXT"),
            ("project_name", "TEXT"),
            ("payment_head", "TEXT"),
        ),
        "payroll": (
            ("employee_name", "TEXT"),
            ("payroll_year", "TEXT"),
            ("workflow_status", "TEXT"),
            ("payment_mode", "TEXT"),
            ("payment_status", "TEXT"),
            ("payroll_period_start", "TEXT"),
            ("payroll_period_end", "TEXT"),
            ("total_month_days", "INTEGER"),
            ("worked_days", "INTEGER"),
            ("leave_days", "INTEGER"),
            ("half_days", "INTEGER"),
            ("absent_days", "INTEGER"),
            ("paid_weekly_off_days", "INTEGER"),
            ("paid_holiday_days", "INTEGER"),
            ("total_worked_hours", "REAL"),
            ("total_ot_hours", "REAL"),
            ("holiday_ot_hours", "REAL"),
            ("weekly_off_ot_hours", "REAL"),
            ("normal_salary_amount", "REAL"),
            ("weekly_off_paid_amount", "REAL"),
            ("holiday_paid_amount", "REAL"),
            ("normal_ot_amount", "REAL"),
            ("ot_held_hours", "REAL"),
            ("md_remarks", "TEXT"),
            ("submitted_at", "TEXT"),
            ("approved_at", "TEXT"),
            ("paid_at", "TEXT"),
        ),
        "site_expenses": (
            ("document_no", "TEXT"),
            ("posted_at", "TEXT"),
            ("posted_by", "TEXT"),
            ("journal_id", "TEXT"),
            ("is_void", "INTEGER DEFAULT 0"),
        ),
        "expense_invoices": (
            ("document_no", "TEXT"),
            ("status", "TEXT DEFAULT 'Submitted'"),
            ("verified_by", "TEXT"),
            ("verified_at", "TEXT"),
            ("approved_by", "TEXT"),
            ("approved_at", "TEXT"),
            ("posted_by", "TEXT"),
            ("posted_at", "TEXT"),
            ("journal_id", "TEXT"),
            ("is_void", "INTEGER DEFAULT 0"),
        ),
        "finance_transactions": (
            ("document_no", "TEXT"),
            ("journal_id", "TEXT"),
            ("is_void", "INTEGER DEFAULT 0"),
        ),
        "direct_payments": (
            ("document_no", "TEXT"),
            ("journal_id", "TEXT"),
            ("is_void", "INTEGER DEFAULT 0"),
        ),
        "material_requests": (("document_no", "TEXT"),),
        "subcontractor_bills": (("document_no", "TEXT"),),
        "petty_cash_requests": (("document_no", "TEXT"),),
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
        UPDATE employees SET employee_type = 'Daily Wage Staff'
        WHERE employee_type = 'Company Staff' AND LOWER(COALESCE(salary_type, '')) = 'daily'
        """
    )
    cur.execute(
        """
        UPDATE employees SET employee_type = 'Monthly Staff'
        WHERE employee_type = 'Company Staff'
        """
    )
    cur.execute(
        """
        UPDATE employees SET weekly_off_day = COALESCE(NULLIF(weekly_off_day, ''), 'Sunday')
        WHERE COALESCE(weekly_off_day, '') = ''
          AND employee_type IN ('Monthly Staff', 'Daily Wage Staff', 'Company Staff')
        """
    )
    cur.execute(
        """
        UPDATE employees SET paid_holiday_eligibility = COALESCE(NULLIF(paid_holiday_eligibility, ''), 'Yes')
        WHERE COALESCE(paid_holiday_eligibility, '') = ''
          AND employee_type IN ('Monthly Staff', 'Daily Wage Staff')
        """
    )
    cur.execute(
        """
        UPDATE employees SET payroll_status = COALESCE(NULLIF(payroll_status, ''), 'Active')
        WHERE COALESCE(payroll_status, '') = ''
          AND employee_type IN ('Monthly Staff', 'Daily Wage Staff')
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

    try:
        from modules.dpr_steel_shapes import seed_steel_shapes_if_empty, sync_builtin_steel_shapes

        seed_steel_shapes_if_empty(conn)
        sync_builtin_steel_shapes(conn)
    except Exception:
        pass

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
    _add_column_if_missing(cur, "expense_invoice_lines", "hsn_code", "TEXT")
    _add_column_if_missing(cur, "petty_cash_requests", "staff_id", "TEXT")
    _add_column_if_missing(cur, "petty_cash_requests", "staff_name", "TEXT")
    _add_column_if_missing(cur, "project_finance_settings", "petty_cash_handler_id", "TEXT")
    _add_column_if_missing(cur, "project_finance_settings", "petty_cash_handler_name", "TEXT")

    for key, val in [
        ("finance_escalation_hours_submitted", "48"),
        ("finance_escalation_hours_verified", "48"),
        ("finance_escalation_hours_pm_approved", "72"),
        ("finance_escalation_auto_notify", "1"),
        ("supplier_payment_md_limit", "50000"),
    ]:
        cur.execute(
            "INSERT OR IGNORE INTO app_settings(setting_key, setting_value) VALUES(?, ?)",
            (key, val),
        )

    _seed_chart_of_accounts(conn)
    _seed_default_company(conn)
    _sync_vendors_from_subcontractors(cur)

    from modules.correspondence_data import ensure_correspondence_tables

    ensure_correspondence_tables(conn)
    for key, val in [
        ("corr_imap_enabled", "0"),
        ("corr_imap_host", "imap.gmail.com"),
        ("corr_imap_user", "info@maxexinindia.com"),
    ]:
        cur.execute(
            "INSERT OR IGNORE INTO app_settings(setting_key, setting_value) VALUES(?, ?)",
            (key, val),
        )

    from modules.erp_data import ensure_erp_extension_tables

    ensure_erp_extension_tables(conn)

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


_ID_COLUMN_BY_TABLE = {
    "projects": "project_id",
    "employees": "employee_id",
    "workers": "worker_id",
    "project_boq_items": "boq_item_id",
    "client_boq_items": "boq_item_id",
    "dpr_reports": "dpr_id",
    "dpr_measurements": "measurement_id",
    "dpr_boq_lines": "line_id",
    "dpr_manpower": "manpower_id",
    "client_bills": "bill_id",
    "client_bill_lines": "line_id",
    "subcontractors": "subcontractor_id",
    "finance_transactions": "transaction_id",
    "payroll": "payroll_id",
    "material_requests": "request_id",
    "expense_invoices": "invoice_id",
    "expense_invoice_lines": "line_id",
    "petty_cash_requests": "request_id",
    "site_expenses": "expense_id",
    "site_expense_lines": "line_id",
    "direct_payments": "payment_id",
    "journal_entries": "journal_id",
    "ledger_lines": "line_id",
    "company_master": "company_id",
    "vendors": "vendor_id",
    "expense_entries": "expense_id",
    "payment_vouchers": "voucher_id",
    "receipt_vouchers": "voucher_id",
    "petty_cash_issues": "issue_id",
    "petty_cash_expenses": "expense_no",
    "gst_payments": "payment_id",
    "tds_deductions": "deduction_id",
    "tds_payments": "payment_id",
    "subcontractor_work_orders": "wo_id",
    "subcontractor_bill_entries": "bill_entry_id",
    "security_deposit_register": "register_id",
    "material_master": "material_id",
    "stock_register": "stock_id",
    "material_issues": "issue_id",
    "asset_register": "asset_id",
    "asset_transfers": "transfer_id",
    "asset_depreciation": "depreciation_id",
    "tools_register": "tool_id",
}


def generate_id(prefix, table_name, id_column=None, conn=None):
    """Return next ID for prefix+table. Uses max existing suffix.

    Pass the same ``conn`` when inserting multiple rows in one transaction so each
    call sees IDs allocated earlier in that batch (avoids duplicate PB* IDs on BOQ save).
    """
    col = id_column or _ID_COLUMN_BY_TABLE.get(table_name)
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    cur = conn.cursor()
    if col:
        cur.execute(f"SELECT {col} FROM {table_name} WHERE {col} LIKE ?", (f"{prefix}%",))
        max_num = 100
        for (raw,) in cur.fetchall():
            text = str(raw or "")
            if not text.startswith(prefix):
                continue
            suffix = text[len(prefix) :]
            try:
                max_num = max(max_num, int(suffix))
            except ValueError:
                continue
        new_id = f"{prefix}{max_num + 1}"
    else:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0] + 101
        new_id = f"{prefix}{count}"
    if own_conn:
        conn.close()
    return new_id


def next_document_number(doc_type, conn=None, year=None):
    """Return next formatted document number, e.g. EXP-2026-0001."""
    prefix = DOCUMENT_PREFIXES.get(doc_type)
    if not prefix:
        raise ValueError(f"Unknown document type: {doc_type}")
    yr = int(year or datetime.now().year)
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT last_number FROM document_sequences WHERE doc_type = ? AND year = ?",
        (doc_type, yr),
    )
    row = cur.fetchone()
    if row:
        seq = int(row[0]) + 1
        cur.execute(
            "UPDATE document_sequences SET last_number = ? WHERE doc_type = ? AND year = ?",
            (seq, doc_type, yr),
        )
    else:
        seq = 1
        cur.execute(
            "INSERT INTO document_sequences(doc_type, year, last_number) VALUES(?,?,?)",
            (doc_type, yr, seq),
        )
    if own_conn:
        conn.commit()
        conn.close()
    return f"{prefix}-{yr}-{seq:04d}"


def _seed_chart_of_accounts(conn):
    accounts = (
        ("CASH", DEFAULT_LEDGER_ACCOUNTS["cash"], "Asset"),
        ("BANK", DEFAULT_LEDGER_ACCOUNTS["bank"], "Asset"),
        ("INV", DEFAULT_LEDGER_ACCOUNTS["inventory"], "Asset"),
        ("DEBT", DEFAULT_LEDGER_ACCOUNTS["debtor"], "Asset"),
        ("GSTIN", DEFAULT_LEDGER_ACCOUNTS["gst_input"], "Asset"),
        ("PCASH", DEFAULT_LEDGER_ACCOUNTS["petty_cash"], "Asset"),
        ("CRED", DEFAULT_LEDGER_ACCOUNTS["creditor"], "Liability"),
        ("SUPP", DEFAULT_LEDGER_ACCOUNTS["supplier"], "Liability"),
        ("GSTPY", DEFAULT_LEDGER_ACCOUNTS["gst_payable"], "Liability"),
        ("TDSPY", DEFAULT_LEDGER_ACCOUNTS["tds_payable"], "Liability"),
        ("CREV", DEFAULT_LEDGER_ACCOUNTS["contract_revenue"], "Income"),
        ("MPUR", DEFAULT_LEDGER_ACCOUNTS["material_purchase"], "Expense"),
        ("MCST", DEFAULT_LEDGER_ACCOUNTS["material_cost"], "Expense"),
        ("SEXP", DEFAULT_LEDGER_ACCOUNTS["site_expense"], "Expense"),
        ("CEXP", DEFAULT_LEDGER_ACCOUNTS["contractor_expense"], "Expense"),
        ("SALEXP", DEFAULT_LEDGER_ACCOUNTS["salary_expense"], "Expense"),
        ("LABEXP", DEFAULT_LEDGER_ACCOUNTS["labour_expense"], "Expense"),
        ("GENEXP", DEFAULT_LEDGER_ACCOUNTS["general_expense"], "Expense"),
    )
    for code, name, acc_type in accounts:
        conn.execute(
            """
            INSERT OR IGNORE INTO chart_of_accounts(account_code, account_name, account_type, is_active)
            VALUES(?,?,?,1)
            """,
            (code, name, acc_type),
        )


def _seed_default_company(conn):
    row = conn.execute("SELECT COUNT(*) FROM company_master").fetchone()
    if row and row[0] == 0:
        conn.execute(
            """
            INSERT INTO company_master(
                company_id, company_name, gst_number, address, phone, email, financial_year
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                "CMP101",
                "MAXEL PRIVATE LIMITED",
                "",
                "",
                "",
                "",
                f"{datetime.now().year}-{datetime.now().year + 1}",
            ),
        )


def _sync_vendors_from_subcontractors(cur):
    cur.execute(
        """
        SELECT subcontractor_id, COALESCE(company_name, subcontractor_name),
               contact_person, contact_number, address, gst_number, vendor_type
        FROM subcontractors
        WHERE COALESCE(subcontractor_id, '') != ''
        """
    )
    for sub_id, name, contact, mobile, address, gst, vtype in cur.fetchall():
        cur.execute("SELECT COUNT(*) FROM vendors WHERE subcontractor_id = ?", (sub_id,))
        if cur.fetchone()[0] == 0:
            vendor_id = generate_id("VND", "vendors", id_column="vendor_id")
            try:
                cur.execute(
                    """
                    INSERT INTO vendors(
                        vendor_id, vendor_type, supplier_name, gst_number, contact_person,
                        mobile, address, subcontractor_id, status, created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        vendor_id,
                        vtype or "Subcontractor",
                        name or "",
                        gst or "",
                        contact or "",
                        mobile or "",
                        address or "",
                        sub_id,
                        "Active",
                        _finance_timestamp(),
                    ),
                )
            except sqlite3.IntegrityError:
                pass


def _expense_category_ledger_account(category):
    cat = (category or "").strip().lower()
    if cat == "material":
        return DEFAULT_LEDGER_ACCOUNTS["material_purchase"]
    if cat == "labour":
        return DEFAULT_LEDGER_ACCOUNTS["labour_expense"]
    return DEFAULT_LEDGER_ACCOUNTS["site_expense"]


def _payment_source_credit_account(payment_source, payment_mode=""):
    src = (payment_source or "").strip().lower()
    mode = (payment_mode or "").strip().lower()
    if src == "petty cash":
        return DEFAULT_LEDGER_ACCOUNTS["petty_cash"]
    if src == "bank" or "bank" in mode:
        return DEFAULT_LEDGER_ACCOUNTS["bank"]
    return DEFAULT_LEDGER_ACCOUNTS["cash"]


def post_purchase_invoice_to_ledger(conn, invoice_row, actor):
    """Auto journal for purchase: Dr expense + Dr GST Input, Cr Supplier."""
    inv_id = invoice_row.get("invoice_id") or invoice_row.get("id")
    existing = conn.execute(
        "SELECT journal_id FROM journal_entries WHERE source_type = 'purchase_invoice' AND source_id = ?",
        (inv_id,),
    ).fetchone()
    if existing and existing[0]:
        return existing[0]

    taxable = float(invoice_row.get("taxable_amount") or 0)
    total_tax = float(invoice_row.get("total_tax") or 0)
    total = float(invoice_row.get("total_invoice_value") or 0)
    if total <= 0:
        return None

    exp_type = (invoice_row.get("exp_type") or "Purchase").strip()
    expense_acct = (
        DEFAULT_LEDGER_ACCOUNTS["material_purchase"]
        if exp_type.lower() == "purchase"
        else _expense_category_ledger_account(exp_type)
    )
    journal_id = generate_id("JRN", "journal_entries", id_column="journal_id", conn=conn)
    document_no = next_document_number("journal_voucher", conn=conn)
    entry_date = invoice_row.get("expense_date") or datetime.now().strftime(DATE_FMT)
    supplier = invoice_row.get("supplier") or ""
    project = invoice_row.get("project_name") or ""
    narration = f"Purchase invoice {invoice_row.get('document_no') or inv_id} — {supplier}"

    lines = []
    if taxable > 0:
        lines.append(
            {"account_name": expense_acct, "debit": taxable, "credit": 0, "party_name": supplier, "remarks": narration}
        )
    if total_tax > 0:
        lines.append(
            {
                "account_name": DEFAULT_LEDGER_ACCOUNTS["gst_input"],
                "debit": total_tax,
                "credit": 0,
                "party_name": supplier,
                "remarks": "GST Input",
            }
        )
    if total > 0:
        lines.append(
            {
                "account_name": DEFAULT_LEDGER_ACCOUNTS["supplier"],
                "debit": 0,
                "credit": total,
                "party_name": supplier,
                "remarks": narration,
            }
        )
    return _create_journal_entry(
        conn,
        journal_id,
        document_no,
        entry_date,
        "purchase_invoice",
        inv_id,
        narration,
        lines,
        actor,
        project,
    )


def post_site_expense_to_ledger(conn, expense_row, actor):
    """Auto journal on petty cash / site expense approval."""
    eid = expense_row.get("expense_id")
    existing = conn.execute(
        "SELECT journal_id FROM site_expenses WHERE expense_id = ? AND COALESCE(journal_id, '') != ''",
        (eid,),
    ).fetchone()
    if existing and existing[0]:
        return existing[0]

    taxable = float(expense_row.get("taxable_amount") or 0)
    total_tax = float(expense_row.get("total_tax") or 0)
    total = float(expense_row.get("total_invoice_value") or 0)
    if total <= 0:
        return None

    expense_acct = _expense_category_ledger_account(expense_row.get("expense_category"))
    credit_acct = _payment_source_credit_account(
        expense_row.get("payment_source"),
        expense_row.get("payment_source"),
    )
    journal_id = generate_id("JRN", "journal_entries", id_column="journal_id", conn=conn)
    document_no = next_document_number("journal_voucher", conn=conn)
    entry_date = expense_row.get("expense_date") or datetime.now().strftime(DATE_FMT)
    supplier = expense_row.get("supplier") or ""
    project = expense_row.get("project_name") or ""
    doc_no = expense_row.get("document_no") or eid
    narration = f"Expense {doc_no} — {supplier}"

    lines = []
    if taxable > 0:
        lines.append({"account_name": expense_acct, "debit": taxable, "credit": 0, "party_name": supplier, "remarks": narration})
    if total_tax > 0:
        lines.append(
            {
                "account_name": DEFAULT_LEDGER_ACCOUNTS["gst_input"],
                "debit": total_tax,
                "credit": 0,
                "party_name": supplier,
                "remarks": "GST Input",
            }
        )
    if total > 0:
        lines.append({"account_name": credit_acct, "debit": 0, "credit": total, "party_name": supplier, "remarks": narration})

    jid = _create_journal_entry(
        conn,
        journal_id,
        document_no,
        entry_date,
        "site_expense",
        eid,
        narration,
        lines,
        actor,
        project,
    )
    conn.execute(
        "UPDATE site_expenses SET journal_id=?, posted_by=?, posted_at=? WHERE expense_id=?",
        (jid, actor, _finance_timestamp(), eid),
    )
    return jid


def post_payment_to_ledger(conn, amount, party_name, payment_mode, project_name, source_type, source_id, actor, narration=""):
    """Dr creditor/party, Cr cash/bank on supplier payment settlement."""
    existing = conn.execute(
        "SELECT journal_id FROM journal_entries WHERE source_type = ? AND source_id = ?",
        (source_type, source_id),
    ).fetchone()
    if existing and existing[0]:
        return existing[0]

    amt = float(amount or 0)
    if amt <= 0:
        return None

    credit_acct = _payment_source_credit_account("", payment_mode)
    journal_id = generate_id("JRN", "journal_entries", id_column="journal_id", conn=conn)
    document_no = next_document_number("journal_voucher", conn=conn)
    entry_date = datetime.now().strftime(DATE_FMT)
    lines = [
        {
            "account_name": DEFAULT_LEDGER_ACCOUNTS["supplier"],
            "debit": amt,
            "credit": 0,
            "party_name": party_name,
            "remarks": narration or "Supplier payment",
        },
        {
            "account_name": credit_acct,
            "debit": 0,
            "credit": amt,
            "party_name": party_name,
            "remarks": narration or "Payment",
        },
    ]
    return _create_journal_entry(
        conn,
        journal_id,
        document_no,
        entry_date,
        source_type,
        source_id,
        narration or f"Payment {source_id}",
        lines,
        actor,
        project_name,
    )


def _create_journal_entry(
    conn,
    journal_id,
    document_no,
    entry_date,
    source_type,
    source_id,
    narration,
    lines,
    actor,
    project_name="",
):
    total_debit = round(sum(float(ln.get("debit") or 0) for ln in lines), 2)
    total_credit = round(sum(float(ln.get("credit") or 0) for ln in lines), 2)
    conn.execute(
        """
        INSERT INTO journal_entries(
            journal_id, document_no, entry_date, source_type, source_id, narration,
            total_debit, total_credit, status, posted_by, posted_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            journal_id,
            document_no,
            entry_date,
            source_type,
            source_id,
            narration,
            total_debit,
            total_credit,
            FINANCE_STATUS_POSTED,
            actor,
            _finance_timestamp(),
        ),
    )
    for ln in lines:
        line_id = generate_id("LED", "ledger_lines", id_column="line_id", conn=conn)
        conn.execute(
            """
            INSERT INTO ledger_lines(
                line_id, journal_id, account_name, debit, credit, project_name, party_name, remarks
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                line_id,
                journal_id,
                ln.get("account_name", ""),
                float(ln.get("debit") or 0),
                float(ln.get("credit") or 0),
                project_name,
                ln.get("party_name", ""),
                ln.get("remarks", ""),
            ),
        )
    return journal_id


def post_gl_lines(conn, journal_id, lines, project_name=""):
    """Insert GL lines for an existing journal entry."""
    for ln in lines:
        line_id = generate_id("LED", "ledger_lines", id_column="line_id", conn=conn)
        conn.execute(
            """
            INSERT INTO ledger_lines(
                line_id, journal_id, account_name, debit, credit, project_name, party_name, remarks
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                line_id,
                journal_id,
                ln.get("account_name", ""),
                float(ln.get("debit") or 0),
                float(ln.get("credit") or 0),
                project_name or ln.get("project_name", ""),
                ln.get("party_name", ""),
                ln.get("remarks", ""),
            ),
        )


def post_journal_entry(
    conn,
    rule_key,
    amounts,
    source_type,
    source_id,
    actor,
    entry_date=None,
    narration="",
    project_name="",
    party_name="",
):
    """Build and post a balanced journal from ACCOUNTING_RULES."""
    rule = ACCOUNTING_RULES.get(rule_key)
    if not rule:
        raise ValueError(f"Unknown accounting rule: {rule_key}")

    existing = conn.execute(
        "SELECT journal_id FROM journal_entries WHERE source_type = ? AND source_id = ?",
        (source_type, source_id),
    ).fetchone()
    if existing and existing[0]:
        return existing[0]

    lines = []
    for side, account_key, amount_key in rule:
        amt = round(float(amounts.get(amount_key) or 0), 2)
        if amt <= 0:
            continue
        account_name = DEFAULT_LEDGER_ACCOUNTS.get(account_key, account_key)
        if side == "debit":
            lines.append(
                {
                    "account_name": account_name,
                    "debit": amt,
                    "credit": 0,
                    "party_name": party_name,
                    "remarks": narration or rule_key,
                }
            )
        else:
            lines.append(
                {
                    "account_name": account_name,
                    "debit": 0,
                    "credit": amt,
                    "party_name": party_name,
                    "remarks": narration or rule_key,
                }
            )

    if not lines:
        return None

    journal_id = generate_id("JRN", "journal_entries", id_column="journal_id", conn=conn)
    document_no = next_document_number("journal_voucher", conn=conn)
    return _create_journal_entry(
        conn,
        journal_id,
        document_no,
        entry_date or datetime.now().strftime(DATE_FMT),
        source_type,
        source_id,
        narration or f"{rule_key} {source_id}",
        lines,
        actor,
        project_name,
    )


def post_to_ledger_on_approval(conn, entity_type, entity_row, actor):
    """Dispatch automatic GL posting when finance documents are approved/settled."""
    entity_type = (entity_type or "").strip().lower()
    if entity_type in ("purchase_invoice", "material_purchase", "expense_voucher"):
        return post_purchase_invoice_to_ledger(conn, entity_row, actor)
    if entity_type in ("site_expense", "petty_cash_expense"):
        return post_site_expense_to_ledger(conn, entity_row, actor)
    if entity_type in ("supplier_payment", "payment_out", "payment_voucher"):
        return post_payment_to_ledger(
            conn,
            entity_row.get("amount"),
            entity_row.get("party_name") or entity_row.get("supplier") or entity_row.get("pay_to_name"),
            entity_row.get("payment_mode", "Bank"),
            entity_row.get("project_name", ""),
            entity_type,
            entity_row.get("source_id") or entity_row.get("transaction_id") or entity_row.get("voucher_id"),
            actor,
            entity_row.get("narration", ""),
        )
    if entity_type == "tds_deduction":
        return post_journal_entry(
            conn,
            "tds_deduction",
            {"amount": entity_row.get("amount")},
            "tds_deduction",
            entity_row.get("deduction_id") or entity_row.get("source_id"),
            actor,
            entity_row.get("entry_date"),
            entity_row.get("narration", "TDS deduction"),
            entity_row.get("project_name", ""),
            entity_row.get("vendor", ""),
        )
    if entity_type == "gst_payment":
        jid = post_journal_entry(
            conn,
            "gst_payment",
            {"amount": entity_row.get("amount")},
            "gst_payment",
            entity_row.get("payment_id") or entity_row.get("source_id"),
            actor,
            entity_row.get("payment_date"),
            entity_row.get("narration", "GST payment"),
        )
        if jid and entity_row.get("payment_id"):
            conn.execute(
                "UPDATE gst_payments SET journal_id = ? WHERE payment_id = ?",
                (jid, entity_row.get("payment_id")),
            )
        return jid
    if entity_type == "petty_cash_expense_entry":
        return post_journal_entry(
            conn,
            "petty_cash_expense",
            {"amount": entity_row.get("amount")},
            "petty_cash_expense",
            entity_row.get("expense_no") or entity_row.get("source_id"),
            actor,
            entity_row.get("expense_date"),
            entity_row.get("narration", "Petty cash expense"),
            entity_row.get("site", ""),
            entity_row.get("employee_name", ""),
        )
    return None


def void_finance_entity(conn, table, id_column, entity_id, actor, reason="", entity_type=""):
    """Soft void — never hard-delete finance records."""
    conn.execute(
        f"UPDATE {table} SET status = ?, is_void = 1 WHERE {id_column} = ?",
        (FINANCE_STATUS_VOIDED, entity_id),
    )
    if entity_type:
        log_finance_audit(
            conn,
            entity_type,
            entity_id,
            "Void",
            actor,
            "",
            FINANCE_STATUS_VOIDED,
            reason,
        )


def get_supplier_payment_md_limit():
    return float(_finance_setting("supplier_payment_md_limit", "50000") or 50000)


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
    released = sum_query(
        """
        SELECT COALESCE(SUM(released_amount), 0) FROM petty_cash_requests
        WHERE project_name = ? AND status = 'Released'
        """,
        (project_name,),
    )
    spent_legacy = sum_query(
        """
        SELECT COALESCE(SUM(amount), 0) FROM finance_transactions
        WHERE transaction_type = 'expense_voucher' AND project_name = ? AND funding_source = 'Petty Cash'
          AND status = ?
        """,
        (project_name, FINANCE_STATUS_SETTLED),
    )
    spent_site = sum_query(
        """
        SELECT COALESCE(SUM(total_invoice_value), 0) FROM site_expenses
        WHERE project_name = ? AND payment_source = 'Petty Cash' AND status = 'Approved'
        """,
        (project_name,),
    )
    returned = sum_query(
        """
        SELECT COALESCE(SUM(amount), 0) FROM finance_transactions
        WHERE transaction_type = 'cash_receipt' AND project_name = ? AND category_head = 'Petty Cash Return'
          AND status = ?
        """,
        (project_name, FINANCE_STATUS_SETTLED),
    )
    return issued + released - spent_legacy - spent_site - returned


def load_petty_cash_balances():
    conn = get_conn()
    projects = pd.read_sql_query(
        """
        SELECT DISTINCT project_name FROM (
            SELECT project_name FROM projects WHERE COALESCE(project_name, '') != ''
            UNION
            SELECT project_name FROM finance_transactions WHERE COALESCE(project_name, '') != ''
            UNION
            SELECT project_name FROM petty_cash_requests WHERE COALESCE(project_name, '') != ''
        )
        ORDER BY project_name
        """,
        conn,
    )
    conn.close()
    rows = []
    for project_name in projects["project_name"].tolist():
        balance = get_petty_cash_balance(project_name)
        handler = get_petty_cash_handler(project_name)
        rows.append(
            {
                "Project": project_name,
                "Petty Cash Balance (Rs)": balance,
                "Handled By": handler.get("staff_name") or "—",
            }
        )
    return pd.DataFrame(rows, columns=["Project", "Petty Cash Balance (Rs)", "Handled By"])


def get_petty_cash_handler(project_name):
    if not project_name:
        return {"staff_id": "", "staff_name": ""}
    conn = get_conn()
    row = conn.execute(
        """
        SELECT petty_cash_handler_id, petty_cash_handler_name
        FROM project_finance_settings
        WHERE project_name = ?
        """,
        (project_name,),
    ).fetchone()
    if row and str(row[1] or "").strip():
        conn.close()
        return {"staff_id": str(row[0] or ""), "staff_name": str(row[1] or "")}
    row = conn.execute(
        """
        SELECT staff_id, staff_name
        FROM petty_cash_requests
        WHERE project_name = ? AND status = 'Released' AND COALESCE(staff_name, '') != ''
        ORDER BY id DESC
        LIMIT 1
        """,
        (project_name,),
    ).fetchone()
    conn.close()
    if row:
        return {"staff_id": str(row[0] or ""), "staff_name": str(row[1] or "")}
    return {"staff_id": "", "staff_name": ""}


def set_petty_cash_handler(project_name, staff_id, staff_name, actor):
    if not project_name:
        return
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO project_finance_settings(
            project_name, petty_cash_handler_id, petty_cash_handler_name, updated_by, updated_at
        )
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(project_name) DO UPDATE SET
            petty_cash_handler_id = excluded.petty_cash_handler_id,
            petty_cash_handler_name = excluded.petty_cash_handler_name,
            updated_by = excluded.updated_by,
            updated_at = excluded.updated_at
        """,
        (project_name, staff_id or "", staff_name or "", actor, _finance_timestamp()),
    )
    conn.commit()
    conn.close()


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
    doc_no = row.get("document_no") or ""
    if not doc_no:
        type_map = {
            "payment_out": "payment_voucher",
            "cash_receipt": "receipt_voucher",
            "petty_cash_issue": "petty_cash_issue",
            "expense_voucher": "purchase_invoice",
        }
        mapped = type_map.get(row.get("transaction_type"))
        if mapped:
            doc_no = next_document_number(mapped, conn=conn)
    conn.execute(
        """
        INSERT INTO finance_transactions(
            transaction_id, document_no, transaction_type, transaction_date, project_name, client_name,
            category_head, pay_to_type, pay_to_name, amount, payment_mode, funding_source,
            reference_number, remarks, document_upload, status, submitted_by, submitted_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            row["transaction_id"],
            doc_no,
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
    return doc_no


def update_finance_status(conn, transaction_id, new_status, actor, rejection_reason="", audit=True):
    now = _finance_timestamp()
    old_row = conn.execute(
        "SELECT status, transaction_type, amount, pay_to_name, payment_mode, project_name FROM finance_transactions WHERE transaction_id = ?",
        (transaction_id,),
    ).fetchone()
    old_status = old_row[0] if old_row else ""

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
        if old_row and old_row[1] == "payment_out":
            post_payment_to_ledger(
                conn,
                old_row[2],
                old_row[3],
                old_row[4],
                old_row[5],
                "finance_transaction",
                transaction_id,
                actor,
            )
        elif old_row and old_row[1] == "expense_voucher":
            inv = conn.execute(
                """
                SELECT invoice_id, document_no, expense_date, supplier, exp_type,
                       taxable_amount, total_tax, total_invoice_value, project_name
                FROM expense_invoices WHERE finance_transaction_id = ?
                """,
                (transaction_id,),
            ).fetchone()
            if inv:
                inv_dict = {
                    "invoice_id": inv[0],
                    "document_no": inv[1],
                    "expense_date": inv[2],
                    "supplier": inv[3],
                    "exp_type": inv[4],
                    "taxable_amount": inv[5],
                    "total_tax": inv[6],
                    "total_invoice_value": inv[7],
                    "project_name": inv[8],
                }
                jid = post_purchase_invoice_to_ledger(conn, inv_dict, actor)
                conn.execute(
                    """
                    UPDATE expense_invoices
                    SET status=?, posted_by=?, posted_at=?, journal_id=?
                    WHERE finance_transaction_id=?
                    """,
                    (FINANCE_STATUS_POSTED, actor, now, jid or "", transaction_id),
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
    else:
        conn.execute(
            "UPDATE finance_transactions SET status = ? WHERE transaction_id = ?",
            (new_status, transaction_id),
        )

    if audit:
        action = {
            FINANCE_STATUS_ACCOUNTS_CHECKED: "Accounts Manager Verification",
            FINANCE_STATUS_MD_APPROVED: "Finance Approval",
            FINANCE_STATUS_SETTLED: "Posted to Ledger",
            FINANCE_STATUS_REJECTED: "Rejected",
        }.get(new_status, new_status)
        log_finance_audit(
            conn,
            "finance_transaction",
            transaction_id,
            action,
            actor,
            old_status,
            new_status,
            rejection_reason,
        )


def resolve_project_id(project_name):
    name = (project_name or "").strip()
    if not name:
        return ""
    conn = get_conn()
    row = conn.execute(
        """
        SELECT project_id FROM projects
        WHERE TRIM(COALESCE(project_name, '')) = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (name,),
    ).fetchone()
    conn.close()
    return (row[0] or "").strip() if row else ""


def load_project_boq_by_project_id(project_id):
    pid = (project_id or "").strip()
    if not pid:
        return pd.DataFrame()
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT id, boq_item_id, project_id, project_name, client_name, boq_number, description,
               quantity, unit, approved_rate, amount
        FROM project_boq_items
        WHERE TRIM(COALESCE(project_id, '')) = ?
        ORDER BY boq_number, id
        """,
        conn,
        params=(pid,),
    )
    conn.close()
    return df


def load_project_boq_by_project(project_name):
    name = (project_name or "").strip()
    if not name:
        return pd.DataFrame()
    project_id = resolve_project_id(name)
    if project_id:
        df = load_project_boq_by_project_id(project_id)
        if not df.empty:
            return df
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT id, boq_item_id, project_id, project_name, client_name, boq_number, description,
               quantity, unit, approved_rate, amount
        FROM project_boq_items
        WHERE TRIM(COALESCE(project_name, '')) = ?
          AND (COALESCE(project_id, '') = '' OR project_id = ?)
        ORDER BY boq_number, id
        """,
        conn,
        params=(name, project_id or ""),
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
        SELECT COALESCE(SUM(q), 0) FROM (
            SELECT progress_quantity AS q FROM dpr_reports r
            WHERE r.boq_item_id = ? AND COALESCE(r.status, '') NOT IN ('Draft', 'Rejected')
              AND NOT EXISTS (SELECT 1 FROM dpr_boq_lines bl WHERE bl.dpr_id = r.dpr_id)
            UNION ALL
            SELECT bl.progress_quantity AS q FROM dpr_boq_lines bl
            INNER JOIN dpr_reports r ON r.dpr_id = bl.dpr_id
            WHERE bl.boq_item_id = ? AND COALESCE(r.status, '') NOT IN ('Draft', 'Rejected')
        )
        """,
        (boq_item_id, boq_item_id),
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
    """Active internal staff for DPR site incharge, petty cash, etc."""
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT employee_id, employee_name, COALESCE(designation, '') AS designation,
               COALESCE(employee_type, '') AS employee_type
        FROM employees
        WHERE COALESCE(employee_id, '') != ''
          AND employee_type IN ('Monthly Staff', 'Daily Wage Staff', 'Company Staff')
          AND UPPER(COALESCE(payroll_status, status, 'Active')) NOT IN (
              'RESIGNED', 'TERMINATED', 'INACTIVE', 'LEFT'
          )
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


def load_material_requests(status=None, limit=200):
    conn = get_conn()
    sql = """
        SELECT request_id, project_name, item_name, quantity, unit,
               required_date, remarks, status, created_by, created_at
        FROM material_requests
    """
    params = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def update_material_request_status(request_id, status):
    conn = get_conn()
    cur = conn.execute(
        "UPDATE material_requests SET status = ? WHERE request_id = ?",
        (status, request_id),
    )
    conn.commit()
    updated = cur.rowcount
    conn.close()
    return updated > 0


def save_expense_invoice(conn, header, lines):
    invoice_id = header["invoice_id"]
    document_no = header.get("document_no") or next_document_number("purchase_invoice", conn=conn)
    conn.execute(
        """
        INSERT INTO expense_invoices(
            invoice_id, document_no, finance_transaction_id, expense_date, supplier, invoice_no,
            project_name, exp_type, taxable_amount, tax_type, total_cgst, total_sgst,
            total_igst, total_tax, total_invoice_value, remarks, payment_status,
            payment_method, payment_mode, paid_from, bill_upload, tax_slabs_json,
            status, created_by, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            invoice_id,
            document_no,
            header.get("finance_transaction_id", ""),
            header.get("expense_date", ""),
            header.get("supplier", ""),
            header.get("invoice_no", ""),
            header.get("project_name", ""),
            header.get("exp_type", ""),
            float(header.get("taxable_amount") or 0),
            header.get("tax_type", ""),
            float(header.get("total_cgst") or 0),
            float(header.get("total_sgst") or 0),
            float(header.get("total_igst") or 0),
            float(header.get("total_tax") or 0),
            float(header.get("total_invoice_value") or 0),
            header.get("remarks", ""),
            header.get("payment_status", ""),
            header.get("payment_method", ""),
            header.get("payment_mode", ""),
            header.get("paid_from", ""),
            header.get("bill_upload", ""),
            json.dumps(header.get("tax_slabs") or {}),
            header.get("status", FINANCE_STATUS_SUBMITTED),
            header.get("created_by", ""),
            header.get("created_at", ""),
        ),
    )
    log_finance_audit(
        conn,
        "purchase_invoice",
        invoice_id,
        "Created",
        header.get("created_by", ""),
        "",
        header.get("status", FINANCE_STATUS_SUBMITTED),
        header.get("remarks", ""),
        {"document_no": document_no},
    )
    return document_no
    for line in lines:
        line_id = line.get("line_id") or generate_id("EXL", "expense_invoice_lines")
        conn.execute(
            """
            INSERT INTO expense_invoice_lines(
                line_id, invoice_id, item_name, hsn_code, unit, quantity, rate, amount
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                line_id,
                invoice_id,
                line.get("item_name", ""),
                line.get("hsn_code", ""),
                line.get("unit", ""),
                float(line.get("quantity") or 0),
                float(line.get("rate") or 0),
                float(line.get("amount") or 0),
            ),
        )
    return invoice_id


def load_expense_invoices(limit=200):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT invoice_id, expense_date, supplier, invoice_no, project_name, exp_type,
               taxable_amount, tax_type, total_tax, total_invoice_value, payment_status,
               payment_method, payment_mode, paid_from, finance_transaction_id, created_by, created_at
        FROM expense_invoices
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(max(1, min(int(limit), 500)),),
    )
    conn.close()
    return df


def log_finance_audit(conn, entity_type, entity_id, action, actor, old_status="", new_status="", comments="", changes=None):
    conn.execute(
        """
        INSERT INTO finance_audit_log(
            entity_type, entity_id, action, actor, action_at,
            old_status, new_status, comments, changes_json
        ) VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            entity_type,
            entity_id,
            action,
            actor,
            _finance_timestamp(),
            old_status or "",
            new_status or "",
            comments or "",
            json.dumps(changes or {}),
        ),
    )


def duplicate_site_expense_invoice(supplier, invoice_no, exclude_id=None):
    if not supplier.strip() or not invoice_no.strip():
        return False
    conn = get_conn()
    sql = """
        SELECT expense_id FROM site_expenses
        WHERE LOWER(supplier) = LOWER(?) AND LOWER(invoice_no) = LOWER(?)
          AND status NOT IN ('Rejected', 'Draft', 'Voided')
          AND COALESCE(is_void, 0) = 0
    """
    params = [supplier.strip(), invoice_no.strip()]
    if exclude_id:
        sql += " AND expense_id != ?"
        params.append(exclude_id)
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return row is not None


def get_site_expense(expense_id):
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM site_expenses WHERE expense_id = ?", conn, params=(expense_id,))
    conn.close()
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def load_site_expense_lines(expense_id):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT line_id, expense_id, line_no, item_name, hsn_code, unit, quantity, rate,
               taxable_amount, gst_rate, tax_type, cgst, sgst, igst, line_tax, line_total
        FROM site_expense_lines
        WHERE expense_id = ?
        ORDER BY line_no, id
        """,
        conn,
        params=(expense_id,),
    )
    conn.close()
    return df


def save_site_expense_lines(conn, expense_id, lines):
    conn.execute("DELETE FROM site_expense_lines WHERE expense_id = ?", (expense_id,))
    for idx, line in enumerate(lines, start=1):
        line_id = line.get("line_id") or generate_id("SEL", "site_expense_lines")
        conn.execute(
            """
            INSERT INTO site_expense_lines(
                line_id, expense_id, line_no, item_name, hsn_code, unit, quantity, rate,
                taxable_amount, gst_rate, tax_type, cgst, sgst, igst, line_tax, line_total
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                line_id,
                expense_id,
                idx,
                line.get("item_name", ""),
                line.get("hsn_code", ""),
                line.get("unit", "Nos"),
                float(line.get("quantity") or 0),
                float(line.get("rate") or 0),
                float(line.get("taxable_amount") or 0),
                float(line.get("gst_rate") or 0),
                line.get("tax_type", "CGST+SGST"),
                float(line.get("cgst") or 0),
                float(line.get("sgst") or 0),
                float(line.get("igst") or 0),
                float(line.get("line_tax") or 0),
                float(line.get("line_total") or 0),
            ),
        )


def load_site_expenses(status=None, project_name=None, limit=200):
    conn = get_conn()
    sql = "SELECT * FROM site_expenses WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if project_name:
        sql += " AND project_name = ?"
        params.append(project_name)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def load_petty_cash_requests(status=None, limit=200):
    conn = get_conn()
    sql = "SELECT * FROM petty_cash_requests WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def load_direct_payments(status=None, limit=200):
    conn = get_conn()
    sql = "SELECT * FROM direct_payments WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def load_finance_audit(entity_type=None, entity_id=None, limit=100):
    conn = get_conn()
    sql = "SELECT * FROM finance_audit_log WHERE 1=1"
    params = []
    if entity_type:
        sql += " AND entity_type = ?"
        params.append(entity_type)
    if entity_id:
        sql += " AND entity_id = ?"
        params.append(entity_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def get_finance_kpi_summary():
    """Company-level finance KPIs for dashboards."""
    now = datetime.now()
    month_like = f"%/{now.strftime('%m')}/{now.year}"
    cash_balance = sum_query(
        """
        SELECT COALESCE(SUM(CASE WHEN direction = 'In' THEN amount ELSE -amount END), 0)
        FROM (
            SELECT total_invoice_value AS amount, 'Out' AS direction FROM site_expenses
            WHERE status = 'Approved' AND payment_source IN ('Petty Cash', 'Cash')
            UNION ALL
            SELECT amount, 'Out' FROM direct_payments WHERE status = 'Paid' AND payment_method = 'Cash'
            UNION ALL
            SELECT amount, 'Out' FROM finance_transactions
            WHERE status = 'Settled' AND payment_mode = 'Cash'
            UNION ALL
            SELECT amount, 'In' FROM finance_transactions
            WHERE status = 'Settled' AND transaction_type = 'cash_receipt' AND payment_mode = 'Cash'
        )
        """
    )
    bank_balance = sum_query(
        """
        SELECT COALESCE(SUM(CASE WHEN direction = 'In' THEN amount ELSE -amount END), 0)
        FROM (
            SELECT total_invoice_value AS amount, 'Out' AS direction FROM site_expenses
            WHERE status = 'Approved' AND payment_source = 'Bank'
            UNION ALL
            SELECT amount, 'Out' FROM direct_payments
            WHERE status = 'Paid' AND payment_method IN ('Bank', 'Cheque', 'UPI', 'Bank Transfer')
            UNION ALL
            SELECT amount, 'Out' FROM finance_transactions
            WHERE status = 'Settled' AND payment_mode IN ('Bank Transfer', 'Cheque', 'UPI')
            UNION ALL
            SELECT amount, 'In' FROM finance_transactions
            WHERE status = 'Settled' AND transaction_type = 'cash_receipt'
              AND payment_mode IN ('Bank Transfer', 'Cheque', 'UPI')
        )
        """
    )
    creditors = sum_query(
        """
        SELECT COALESCE(SUM(total_invoice_value), 0) FROM site_expenses
        WHERE status IN ('Submitted', 'Verified', 'PM Approved', 'Approved')
          AND COALESCE(is_void, 0) = 0
        """
    ) + sum_query(
        """
        SELECT COALESCE(SUM(total_invoice_value), 0) FROM expense_invoices
        WHERE COALESCE(status, 'Submitted') NOT IN ('Posted', 'Rejected', 'Voided')
          AND COALESCE(is_void, 0) = 0
        """
    )
    debtors = sum_query(
        """
        SELECT COALESCE(SUM(grand_total), 0) FROM client_bills
        WHERE COALESCE(status, '') NOT IN ('Paid', 'Cancelled', 'Voided')
        """
    )
    monthly_expenses = sum_query(
        """
        SELECT COALESCE(SUM(total_invoice_value), 0) FROM site_expenses
        WHERE status = 'Approved' AND expense_date LIKE ?
        """,
        (month_like,),
    ) + sum_query(
        """
        SELECT COALESCE(SUM(amount), 0) FROM finance_transactions
        WHERE transaction_type IN ('expense_voucher', 'payment_out')
          AND status = 'Settled' AND transaction_date LIKE ?
        """,
        (month_like,),
    )
    petty_issued = sum_query(
        """
        SELECT COALESCE(SUM(amount), 0) FROM finance_transactions
        WHERE transaction_type = 'petty_cash_issue' AND status = 'Settled'
        """
    ) + sum_query(
        "SELECT COALESCE(SUM(released_amount), 0) FROM petty_cash_requests WHERE status = 'Released'"
    )
    petty_utilized = sum_query(
        """
        SELECT COALESCE(SUM(total_invoice_value), 0) FROM site_expenses
        WHERE status = 'Approved' AND payment_source = 'Petty Cash'
        """
    )
    petty_pending_verify = scalar_query(
        "SELECT COUNT(*) FROM site_expenses WHERE status = 'Submitted' AND payment_source = 'Petty Cash'"
    )
    return {
        "cash_balance": round(cash_balance, 2),
        "bank_balance": round(bank_balance, 2),
        "creditors": round(creditors, 2),
        "debtors": round(debtors, 2),
        "monthly_expenses": round(monthly_expenses, 2),
        "petty_issued": round(petty_issued, 2),
        "petty_utilized": round(petty_utilized, 2),
        "petty_pending_verify": int(petty_pending_verify or 0),
    }


def get_project_profit_kpis():
    """Per-project budget, actual, variance, profit (budget - actual)."""
    bva = load_budget_vs_actual()
    if bva.empty:
        return pd.DataFrame()
    bva = bva.copy()
    bva["profit"] = bva["budget"] - bva["actual_total"]
    return bva[["project_name", "budget", "actual_total", "variance", "profit", "utilization_pct"]]


def finance_dashboard_stats():
    today = datetime.now().strftime(DATE_FMT)
    fk = get_finance_kpi_summary()
    base = {
        "today_expenses": sum_query(
            "SELECT COALESCE(SUM(total_invoice_value),0) FROM site_expenses WHERE expense_date = ?",
            (today,),
        ),
        "pending_verification": scalar_query(
            "SELECT COUNT(*) FROM site_expenses WHERE status = 'Submitted'",
        ),
        "pending_pm": scalar_query(
            "SELECT COUNT(*) FROM site_expenses WHERE status = 'Verified'",
        ),
        "pending_management": scalar_query(
            "SELECT COUNT(*) FROM site_expenses WHERE status = 'PM Approved'",
        ),
        "approved_count": scalar_query(
            "SELECT COUNT(*) FROM site_expenses WHERE status = 'Approved'",
        ),
        "rejected_count": scalar_query(
            "SELECT COUNT(*) FROM site_expenses WHERE status = 'Rejected'",
        ),
        "pending_petty_requests": scalar_query(
            "SELECT COUNT(*) FROM petty_cash_requests WHERE status IN ('Submitted','Verified','Approved')",
        ),
        "gst_total": sum_query(
            "SELECT COALESCE(SUM(total_tax),0) FROM site_expenses WHERE status = 'Approved'",
        ),
        "escalated_count": len(load_escalated_finance_items()),
    }
    base.update(fk)
    return base


def load_finance_dashboard_table():
    """One standard finance dashboard table — project overview with pipeline counts."""
    stats = finance_dashboard_stats()
    conn = get_conn()
    try:
        budget_df = load_budget_vs_actual()
        bal_df = load_petty_cash_balances()
        limits_df = load_project_finance_settings()
        pending_df = pd.read_sql_query(
            """
            SELECT project_name,
                   SUM(CASE WHEN status = 'Submitted' THEN 1 ELSE 0 END) AS pending_verify,
                   SUM(CASE WHEN status IN ('Verified', 'PM Approved') THEN 1 ELSE 0 END) AS pending_approval
            FROM site_expenses
            GROUP BY project_name
            """,
            conn,
        )
    finally:
        conn.close()

    escalated = load_escalated_finance_items()
    escalated_by_project = {}
    for item in escalated:
        pname = str(item.get("project_name") or "")
        escalated_by_project[pname] = escalated_by_project.get(pname, 0) + 1

    project_names = set(load_project_names())
    if not budget_df.empty:
        project_names.update(budget_df["project_name"].astype(str).tolist())
    if not bal_df.empty and "Project" in bal_df.columns:
        project_names.update(bal_df["Project"].astype(str).tolist())
    if not limits_df.empty:
        project_names.update(limits_df["project_name"].astype(str).tolist())

    bal_map = {}
    if not bal_df.empty and "Project" in bal_df.columns:
        bal_map = dict(zip(bal_df["Project"], bal_df["Petty Cash Balance (Rs)"]))

    limit_map = {}
    handler_map = {}
    if not limits_df.empty:
        limit_map = dict(zip(limits_df["project_name"], limits_df["petty_cash_limit"]))
        for _, row in limits_df.iterrows():
            pname = str(row["project_name"])
            hname = str(row.get("petty_cash_handler_name") or "").strip()
            if hname:
                handler_map[pname] = hname
            else:
                handler_map[pname] = get_petty_cash_handler(pname).get("staff_name") or "—"

    budget_map = {}
    actual_map = {}
    variance_map = {}
    util_map = {}
    if not budget_df.empty:
        for _, row in budget_df.iterrows():
            pname = str(row["project_name"])
            budget_map[pname] = float(row.get("budget") or 0)
            actual_map[pname] = float(row.get("actual_total") or 0)
            variance_map[pname] = float(row.get("variance") or 0)
            util_map[pname] = float(row.get("utilization_pct") or 0)

    pending_verify_map = {}
    pending_approval_map = {}
    if not pending_df.empty:
        pending_verify_map = dict(zip(pending_df["project_name"], pending_df["pending_verify"]))
        pending_approval_map = dict(zip(pending_df["project_name"], pending_df["pending_approval"]))

    summary_row = {
        "S.No": "-",
        "Project Name": "ALL PROJECTS (Summary)",
        "Budget (Rs)": None,
        "Actual Spend (Rs)": None,
        "Variance (Rs)": None,
        "Budget Used %": None,
        "Petty Balance (Rs)": None,
        "Petty Limit (Rs)": None,
        "Petty Handler": "",
        "Today's Expense (Rs)": round(float(stats.get("today_expenses") or 0), 2),
        "Pending Verify": int(stats.get("pending_verification") or 0),
        "Pending Approval": int(stats.get("pending_pm") or 0) + int(stats.get("pending_management") or 0),
        "Approved": int(stats.get("approved_count") or 0),
        "Rejected": int(stats.get("rejected_count") or 0),
        "Petty Requests": int(stats.get("pending_petty_requests") or 0),
        "Escalated": int(stats.get("escalated_count") or 0),
        "Status": "Summary",
    }

    if not project_names:
        df = pd.DataFrame([summary_row])
        df["S.No"] = df["S.No"].astype(str)
        for col in [
            "Budget (Rs)", "Actual Spend (Rs)", "Variance (Rs)", "Budget Used %",
            "Petty Balance (Rs)", "Petty Limit (Rs)", "Today's Expense (Rs)",
        ]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        for col in [
            "Pending Verify", "Pending Approval", "Approved", "Rejected",
            "Petty Requests", "Escalated",
        ]:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        return df

    rows = [summary_row]
    for idx, pname in enumerate(sorted(project_names), start=1):
        budget = budget_map.get(pname, 0.0)
        actual = actual_map.get(pname, 0.0)
        variance = variance_map.get(pname, budget - actual)
        util = util_map.get(pname, round((actual / budget * 100), 1) if budget > 0 else 0.0)
        petty_bal = float(bal_map.get(pname, get_petty_cash_balance(pname)) or 0)
        petty_limit = float(limit_map.get(pname, 0) or 0)
        petty_handler = handler_map.get(pname) or get_petty_cash_handler(pname).get("staff_name") or "—"
        pending_v = int(pending_verify_map.get(pname, 0) or 0)
        pending_a = int(pending_approval_map.get(pname, 0) or 0)
        escalated_n = int(escalated_by_project.get(pname, 0) or 0)

        status = "OK"
        if escalated_n > 0:
            status = "Escalated"
        elif budget > 0 and util >= 100:
            status = "Over Budget"
        elif budget > 0 and util >= 90:
            status = "Near Budget Limit"
        elif petty_limit > 0 and petty_bal > petty_limit:
            status = "Petty Over Limit"
        elif pending_v > 0 or pending_a > 0:
            status = "Pending Action"

        rows.append(
            {
                "S.No": str(idx),
                "Project Name": pname,
                "Budget (Rs)": round(budget, 2),
                "Actual Spend (Rs)": round(actual, 2),
                "Variance (Rs)": round(variance, 2),
                "Budget Used %": util,
                "Petty Balance (Rs)": round(petty_bal, 2),
                "Petty Limit (Rs)": round(petty_limit, 2),
                "Petty Handler": petty_handler,
                "Today's Expense (Rs)": None,
                "Pending Verify": pending_v,
                "Pending Approval": pending_a,
                "Approved": None,
                "Rejected": None,
                "Petty Requests": None,
                "Escalated": escalated_n,
                "Status": status,
            }
        )

    df = pd.DataFrame(rows)
    money_cols = [
        "Budget (Rs)",
        "Actual Spend (Rs)",
        "Variance (Rs)",
        "Budget Used %",
        "Petty Balance (Rs)",
        "Petty Limit (Rs)",
        "Today's Expense (Rs)",
    ]
    count_cols = [
        "Pending Verify",
        "Pending Approval",
        "Approved",
        "Rejected",
        "Petty Requests",
        "Escalated",
    ]
    df["S.No"] = df["S.No"].astype(str)
    for col in money_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in count_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def _finance_setting(key, default=""):
    conn = get_conn()
    row = conn.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key = ?",
        (key,),
    ).fetchone()
    conn.close()
    return str(row[0]) if row else str(default)


def save_finance_setting(key, value):
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO app_settings(setting_key, setting_value)
        VALUES(?, ?)
        ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
        """,
        (key, str(value)),
    )
    conn.commit()
    conn.close()


def _parse_finance_ts(text):
    if not text:
        return None
    raw = str(text).strip()
    for fmt in ("%d/%m/%Y %H:%M", DATE_FMT, "%Y-%m-%d"):
        try:
            if fmt == "%d/%m/%Y %H:%M":
                return datetime.strptime(raw, fmt)
            return datetime.strptime(raw[:10], fmt)
        except ValueError:
            continue
    return None


def get_escalation_rules():
    return {
        "hours_submitted": float(_finance_setting("finance_escalation_hours_submitted", "48")),
        "hours_verified": float(_finance_setting("finance_escalation_hours_verified", "48")),
        "hours_pm_approved": float(_finance_setting("finance_escalation_hours_pm_approved", "72")),
    }


def load_escalated_finance_items():
    rules = get_escalation_rules()
    now = datetime.now()
    rows = []
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT expense_id, project_name, supplier, total_invoice_value, status,
               submitted_at, verified_at, pm_approved_at, created_at
        FROM site_expenses
        WHERE status IN ('Submitted', 'Verified', 'PM Approved')
        """,
        conn,
    )
    conn.close()
    for _, row in df.iterrows():
        status = row["status"]
        if status == "Submitted":
            ts = _parse_finance_ts(row.get("submitted_at") or row.get("created_at"))
            limit_h = rules["hours_submitted"]
            level = "Accounts verification overdue"
        elif status == "Verified":
            ts = _parse_finance_ts(row.get("verified_at"))
            limit_h = rules["hours_verified"]
            level = "PM approval overdue"
        else:
            ts = _parse_finance_ts(row.get("pm_approved_at"))
            limit_h = rules["hours_pm_approved"]
            level = "Management approval overdue"
        if not ts:
            continue
        hours = (now - ts).total_seconds() / 3600.0
        if hours >= limit_h:
            rows.append(
                {
                    "expense_id": row["expense_id"],
                    "project_name": row["project_name"],
                    "supplier": row["supplier"],
                    "amount": float(row["total_invoice_value"] or 0),
                    "status": status,
                    "escalation": level,
                    "hours_pending": round(hours, 1),
                    "limit_hours": limit_h,
                }
            )
    return rows


def get_project_petty_limit(project_name):
    if not project_name:
        return 0.0
    conn = get_conn()
    row = conn.execute(
        "SELECT petty_cash_limit FROM project_finance_settings WHERE project_name = ?",
        (project_name,),
    ).fetchone()
    conn.close()
    return float(row[0] or 0) if row else 0.0


def get_project_expense_budget(project_name):
    if not project_name:
        return 0.0
    conn = get_conn()
    row = conn.execute(
        """
        SELECT COALESCE(pfs.expense_budget, p.budget, 0)
        FROM projects p
        LEFT JOIN project_finance_settings pfs ON pfs.project_name = p.project_name
        WHERE p.project_name = ?
        LIMIT 1
        """,
        (project_name,),
    ).fetchone()
    conn.close()
    return float(row[0] or 0) if row else 0.0


def load_project_finance_settings():
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT p.project_name,
               COALESCE(p.budget, 0) AS project_budget,
               COALESCE(pfs.petty_cash_limit, 0) AS petty_cash_limit,
               COALESCE(NULLIF(pfs.expense_budget, 0), COALESCE(p.budget, 0)) AS expense_budget,
               COALESCE(pfs.petty_cash_handler_id, '') AS petty_cash_handler_id,
               COALESCE(pfs.petty_cash_handler_name, '') AS petty_cash_handler_name,
               pfs.updated_by,
               pfs.updated_at
        FROM projects p
        LEFT JOIN project_finance_settings pfs ON pfs.project_name = p.project_name
        WHERE COALESCE(p.project_name, '') != ''
        ORDER BY p.project_name
        """,
        conn,
    )
    conn.close()
    return df


def save_project_finance_settings(
    project_name,
    petty_cash_limit,
    expense_budget,
    actor,
    handler_id=None,
    handler_name=None,
):
    conn = get_conn()
    existing = conn.execute(
        "SELECT petty_cash_handler_id, petty_cash_handler_name FROM project_finance_settings WHERE project_name = ?",
        (project_name,),
    ).fetchone()
    hid = existing[0] if existing and handler_id is None else (handler_id or "")
    hname = existing[1] if existing and handler_name is None else (handler_name or "")
    conn.execute(
        """
        INSERT INTO project_finance_settings(
            project_name, petty_cash_limit, expense_budget,
            petty_cash_handler_id, petty_cash_handler_name, updated_by, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_name) DO UPDATE SET
            petty_cash_limit = excluded.petty_cash_limit,
            expense_budget = excluded.expense_budget,
            petty_cash_handler_id = excluded.petty_cash_handler_id,
            petty_cash_handler_name = excluded.petty_cash_handler_name,
            updated_by = excluded.updated_by,
            updated_at = excluded.updated_at
        """,
        (
            project_name,
            float(petty_cash_limit or 0),
            float(expense_budget or 0),
            hid,
            hname,
            actor,
            _finance_timestamp(),
        ),
    )
    conn.commit()
    conn.close()


def check_petty_cash_limit(project_name, extra_amount=0.0):
    limit = get_project_petty_limit(project_name)
    if limit <= 0:
        return True, ""
    balance = get_petty_cash_balance(project_name)
    projected = balance + float(extra_amount or 0)
    if projected > limit:
        return False, f"Petty cash limit for {project_name} is Rs {limit:,.2f}. Projected balance Rs {projected:,.2f} exceeds limit."
    return True, ""


def load_budget_vs_actual(project_name=None):
    conn = get_conn()
    params = []
    project_filter = ""
    if project_name:
        project_filter = " AND p.project_name = ?"
        params.append(project_name)
    df = pd.read_sql_query(
        f"""
        SELECT p.project_name,
               COALESCE(NULLIF(pfs.expense_budget, 0), COALESCE(p.budget, 0)) AS budget,
               COALESCE(se.actual_expense, 0) AS site_expenses,
               COALESCE(dp.actual_paid, 0) AS direct_payments,
               COALESCE(ft.actual_finance, 0) AS legacy_finance,
               COALESCE(se.actual_expense, 0) + COALESCE(dp.actual_paid, 0) + COALESCE(ft.actual_finance, 0) AS actual_total
        FROM projects p
        LEFT JOIN project_finance_settings pfs ON pfs.project_name = p.project_name
        LEFT JOIN (
            SELECT project_name, SUM(total_invoice_value) AS actual_expense
            FROM site_expenses WHERE status = 'Approved'
            GROUP BY project_name
        ) se ON se.project_name = p.project_name
        LEFT JOIN (
            SELECT project_name, SUM(amount) AS actual_paid
            FROM direct_payments WHERE status = 'Paid'
            GROUP BY project_name
        ) dp ON dp.project_name = p.project_name
        LEFT JOIN (
            SELECT project_name, SUM(amount) AS actual_finance
            FROM finance_transactions
            WHERE status = 'Settled'
              AND transaction_type IN ('expense_voucher', 'payment_out')
            GROUP BY project_name
        ) ft ON ft.project_name = p.project_name
        WHERE COALESCE(p.project_name, '') != ''{project_filter}
        ORDER BY p.project_name
        """,
        conn,
        params=params or None,
    )
    conn.close()
    if df.empty:
        return df
    df["variance"] = df["budget"] - df["actual_total"]
    df["utilization_pct"] = df.apply(
        lambda r: round((r["actual_total"] / r["budget"] * 100), 1) if float(r["budget"] or 0) > 0 else 0.0,
        axis=1,
    )
    return df


def load_cash_book(date_from=None, date_to=None):
    conn = get_conn()

    def _date_params():
        p = []
        if date_from:
            p.append(date_from)
        if date_to:
            p.append(date_to)
        return p

    df1 = pd.read_sql_query(
        f"""
        SELECT expense_date AS entry_date, expense_id AS voucher_no, 'Site Expense' AS entry_type,
               project_name, supplier AS party_name, total_invoice_value AS amount,
               payment_source AS method, 'Out' AS direction, status, remarks
        FROM site_expenses
        WHERE status = 'Approved' AND payment_source IN ('Petty Cash', 'Cash')
        {" AND expense_date >= ?" if date_from else ""}
        {" AND expense_date <= ?" if date_to else ""}
        """,
        conn,
        params=_date_params(),
    )
    df2 = pd.read_sql_query(
        f"""
        SELECT payment_date AS entry_date, payment_id AS voucher_no, payment_type AS entry_type,
               project_name, party_name, amount, payment_method AS method, 'Out' AS direction,
               status, remarks
        FROM direct_payments
        WHERE status = 'Paid' AND payment_method = 'Cash'
        {" AND payment_date >= ?" if date_from else ""}
        {" AND payment_date <= ?" if date_to else ""}
        """,
        conn,
        params=_date_params(),
    )
    df3 = pd.read_sql_query(
        f"""
        SELECT transaction_date AS entry_date, transaction_id AS voucher_no, transaction_type AS entry_type,
               project_name, pay_to_name AS party_name, amount, payment_mode AS method, 'Out' AS direction,
               status, remarks
        FROM finance_transactions
        WHERE status = 'Settled'
          AND (payment_mode = 'Cash' OR funding_source = 'Petty Cash')
        {" AND transaction_date >= ?" if date_from else ""}
        {" AND transaction_date <= ?" if date_to else ""}
        """,
        conn,
        params=_date_params(),
    )
    conn.close()
    df = pd.concat([df1, df2, df3], ignore_index=True)
    if df.empty:
        return df
    return df.sort_values("entry_date", ascending=False)


def load_bank_book(date_from=None, date_to=None):
    conn = get_conn()
    date_filter_se = date_filter_dp = date_filter_ft = ""
    params_se = params_dp = params_ft = []
    if date_from:
        date_filter_se += " AND expense_date >= ?"
        date_filter_dp += " AND payment_date >= ?"
        date_filter_ft += " AND transaction_date >= ?"
        params_se.append(date_from)
        params_dp.append(date_from)
        params_ft.append(date_from)
    if date_to:
        date_filter_se += " AND expense_date <= ?"
        date_filter_dp += " AND payment_date <= ?"
        date_filter_ft += " AND transaction_date <= ?"
        params_se.append(date_to)
        params_dp.append(date_to)
        params_ft.append(date_to)
    sql = f"""
        SELECT expense_date AS entry_date, expense_id AS voucher_no, 'Site Expense' AS entry_type,
               project_name, supplier AS party_name, total_invoice_value AS amount,
               payment_source AS method, status, remarks
        FROM site_expenses
        WHERE status = 'Approved' AND payment_source = 'Bank'
        {date_filter_se}
        UNION ALL
        SELECT payment_date, payment_id, payment_type, project_name, party_name, amount,
               payment_method, status, remarks
        FROM direct_payments
        WHERE status = 'Paid' AND payment_method IN ('Bank', 'Cheque', 'UPI', 'Bank Transfer')
        {date_filter_dp}
        UNION ALL
        SELECT transaction_date, transaction_id, transaction_type, project_name, pay_to_name, amount,
               payment_mode, status, remarks
        FROM finance_transactions
        WHERE status = 'Settled'
          AND payment_mode IN ('Bank Transfer', 'Cheque', 'UPI')
        {date_filter_ft}
        ORDER BY entry_date DESC
    """
    df = pd.read_sql_query(sql, conn, params=params_se + params_dp + params_ft or None)
    conn.close()
    return df


def load_gst_register(date_from=None, date_to=None):
    conn = get_conn()
    sql = """
        SELECT expense_date, expense_id, project_name, supplier, invoice_no, expense_category,
               taxable_amount, gst_rate, tax_type, total_cgst, total_sgst, total_igst,
               total_tax, total_invoice_value, status
        FROM site_expenses
        WHERE status = 'Approved'
    """
    params = []
    if date_from:
        sql += " AND expense_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND expense_date <= ?"
        params.append(date_to)
    sql += " ORDER BY expense_date DESC"
    df = pd.read_sql_query(sql, conn, params=params or None)
    conn.close()
    return df


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


def _alpha_key(text: str) -> str:
    return "".join(ch for ch in str(text or "") if ch.isalpha()).upper()


def _derive_unique_sub_code(sub_name: str) -> str:
    """
    Subcontractor code rules:
    - Prefer 1st + 2nd letter (MA for Maksood, IM for Imran)
    - If that 2-letter prefix is already used by another subcontractor, use 1st + 3rd letter.
    - If still colliding, try 1st + 4th, 1st + 5th... until unique.
    """
    letters = _alpha_key(sub_name)
    if len(letters) < 2:
        return (letters + "X")[:2] if letters else "WK"

    conn = get_conn()
    # Map existing 2-letter prefixes to names (best effort)
    rows = conn.execute(
        "SELECT subcontractor_id, subcontractor_name FROM subcontractors WHERE COALESCE(subcontractor_id, '') != ''"
    ).fetchall()
    conn.close()

    used = {}
    for sid, sname in rows:
        sid = str(sid or "").strip().upper()
        sname = str(sname or "").strip()
        if len(sid) >= 2 and sid[:2].isalpha():
            used.setdefault(sid[:2], set()).add(sname.casefold())

    # Candidate generator
    base = letters[0]
    preferred = letters[:2]
    if preferred not in used or used.get(preferred, set()) == {str(sub_name or "").strip().casefold()}:
        return preferred

    for idx in range(2, len(letters)):
        cand = (base + letters[idx]).upper()
        if cand not in used or used.get(cand, set()) == {str(sub_name or "").strip().casefold()}:
            return cand

    # Fallback: first two letters (still a collision, but numeric suffix will differ)
    return preferred


def next_subcontractor_id(sub_name: str) -> str:
    """Generate subcontractor_id like MA100, IM100 based on subcontractor name."""
    code = _derive_unique_sub_code(sub_name)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT subcontractor_id FROM subcontractors WHERE UPPER(COALESCE(subcontractor_id,'')) LIKE ?",
        (f"{code}%",),
    )
    max_num = 99
    for (raw,) in cur.fetchall():
        text = str(raw or "").strip().upper()
        if not text.startswith(code):
            continue
        try:
            max_num = max(max_num, int(text[len(code) :]))
        except ValueError:
            continue
    conn.close()
    return f"{code}{max_num + 1}"


def _sub_code_from_name_or_id(sub_name: str) -> str:
    """If subcontractor exists with alphabetic prefix, reuse it; else derive from name."""
    name = str(sub_name or "").strip()
    if not name:
        return "WK"
    conn = get_conn()
    row = conn.execute(
        "SELECT subcontractor_id FROM subcontractors WHERE TRIM(COALESCE(subcontractor_name,'')) = ? ORDER BY id DESC LIMIT 1",
        (name,),
    ).fetchone()
    conn.close()
    if row:
        sid = str(row[0] or "").strip().upper()
        if len(sid) >= 2 and sid[:2].isalpha():
            return sid[:2]
    return _derive_unique_sub_code(name)


def resolve_subcontractor_name(name):
    """Match subcontractor master name case-insensitively."""
    needle = str(name or "").strip()
    if not needle:
        return ""
    for candidate in load_subcontractor_names():
        if str(candidate or "").strip().casefold() == needle.casefold():
            return str(candidate).strip()
    return needle


def load_subcontractor_labour_rate(subcontractor_name, project_name, labour_type, working_hours):
    sub_name = resolve_subcontractor_name(subcontractor_name)
    project = str(project_name or "").strip()
    designation = str(labour_type or "").strip()
    hours_label = str(working_hours or "").strip()
    conn = get_conn()
    queries = (
        (sub_name, project, designation, hours_label),
        (sub_name, project, designation, ""),
        (sub_name, "", designation, hours_label),
        (sub_name, "", designation, ""),
    )
    for params in queries:
        df = pd.read_sql_query(
            """
            SELECT *
            FROM subcontractor_labour_rates
            WHERE LOWER(TRIM(COALESCE(subcontractor_name, ''))) = LOWER(TRIM(?))
              AND LOWER(TRIM(COALESCE(project_name, ''))) = LOWER(TRIM(?))
              AND LOWER(TRIM(COALESCE(labour_type, ''))) = LOWER(TRIM(?))
              AND (
                    TRIM(COALESCE(working_hours, '')) = TRIM(?)
                    OR TRIM(?) = ''
              )
              AND UPPER(COALESCE(status, 'ACTIVE')) = 'ACTIVE'
            ORDER BY id DESC
            LIMIT 1
            """,
            conn,
            params=(params[0], params[1], params[2], params[3], params[3]),
        )
        if not df.empty:
            conn.close()
            return df.iloc[0].to_dict()
    conn.close()
    return None


def subcontractor_timesheet_day_amount(status, applied_rate, ot_hours, applied_ot_rate, ot_allowed):
    """Daily labour + OT amount for one attendance row (manpower billing)."""
    status_u = str(status or "").strip().upper()
    if status_u in {"ABSENT", "LEAVE"}:
        return 0.0, 0.0, 0.0
    factor = 0.5 if status_u == "HALF DAY" else 1.0
    labour_pay = float(applied_rate or 0) * factor
    ot_pay = float(ot_hours or 0) * float(applied_ot_rate or 0) if ot_allowed else 0.0
    return round(labour_pay, 2), round(ot_pay, 2), round(labour_pay + ot_pay, 2)


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
    sub_name = resolve_subcontractor_name(subcontractor_name)

    conn = get_conn()
    labour_df = pd.read_sql_query(
        f"""
        SELECT COALESCE(applied_rate, 0) AS applied_rate,
               COALESCE(ot_hours, 0) AS ot_hours,
               COALESCE(applied_ot_rate, 0) AS applied_ot_rate,
               COALESCE(status, '') AS status
        FROM attendance
        WHERE LOWER(TRIM(COALESCE(sub_contractor, ''))) = LOWER(TRIM(?))
          AND UPPER(COALESCE(status, '')) IN ('PRESENT', 'HALF DAY')
          {month_filter}
        """,
        conn,
        params=[sub_name] + params,
    )
    boq_df = pd.read_sql_query(
        """
        SELECT COALESCE(amount, 0) AS amount
        FROM subcontractor_boq_entries
        WHERE LOWER(TRIM(COALESCE(subcontractor_name, ''))) = LOWER(TRIM(?))
          AND strftime('%m/%Y', substr(entry_date, 7, 4) || '-' || substr(entry_date, 4, 2) || '-01') = ?
        """,
        conn,
        params=(sub_name, payroll_month),
    )
    advance_df = pd.read_sql_query(
        """
        SELECT COALESCE(amount, 0) AS amount
        FROM subcontractor_advance
        WHERE LOWER(TRIM(COALESCE(subcontractor_name, ''))) = LOWER(TRIM(?))
          AND COALESCE(advance_date, '') LIKE ?
        """,
        conn,
        params=(sub_name, f"%/{payroll_month}"),
    ) if "advance_date" in _columns(conn.cursor(), "subcontractor_advance") else pd.DataFrame(columns=["amount"])
    conn.close()

    labour_amount = 0.0
    ot_amount = 0.0
    if not labour_df.empty:
        for _, row in labour_df.iterrows():
            labour, ot_pay, _ = subcontractor_timesheet_day_amount(
                row["status"],
                row["applied_rate"],
                row["ot_hours"],
                row["applied_ot_rate"],
                float(row["applied_ot_rate"] or 0) > 0,
            )
            labour_amount += labour
            ot_amount += ot_pay
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


def load_payroll_staff_options():
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT employee_id, employee_name, employee_type
        FROM employees
        WHERE COALESCE(employee_id, '') != ''
          AND employee_type IN ('Monthly Staff', 'Daily Wage Staff')
          AND UPPER(COALESCE(payroll_status, status, 'Active')) NOT IN ('RESIGNED', 'TERMINATED', 'INACTIVE', 'LEFT')
        ORDER BY employee_type, employee_name
        """,
        conn,
    )
    conn.close()
    return [(row.employee_id, row.employee_name, row.employee_type) for _, row in df.iterrows()]


def load_project_staff_options(project_name=None):
    """Active staff for petty cash / site requests — prefer staff assigned to the project."""
    conn = get_conn()
    base_sql = """
        SELECT employee_id, employee_name, employee_type, COALESCE(project_name, '') AS project_name
        FROM employees
        WHERE COALESCE(employee_id, '') != ''
          AND UPPER(COALESCE(payroll_status, status, 'Active')) NOT IN ('RESIGNED', 'TERMINATED', 'INACTIVE', 'LEFT')
    """
    if project_name:
        df = pd.read_sql_query(
            base_sql + " AND COALESCE(project_name, '') = ? ORDER BY employee_name",
            conn,
            params=(project_name,),
        )
        if df.empty:
            df = pd.read_sql_query(base_sql + " ORDER BY employee_name", conn)
    else:
        df = pd.read_sql_query(base_sql + " ORDER BY employee_name", conn)
    conn.close()
    return [
        (row.employee_id, row.employee_name, row.employee_type, row.project_name)
        for _, row in df.iterrows()
    ]


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
    code = _sub_code_from_name_or_id(sub_name)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT worker_id FROM workers WHERE UPPER(COALESCE(worker_id,'')) LIKE ?",
        (f"{code}%",),
    )
    max_num = 100
    for (raw,) in cur.fetchall():
        text = str(raw or "").strip().upper()
        if not text.startswith(code):
            continue
        try:
            max_num = max(max_num, int(text[len(code) :]))
        except ValueError:
            continue
    conn.close()
    return f"{code}{max_num + 1}"


ATTENDANCE_DEFAULT_IN_TIME = "08:00"
ATTENDANCE_DEFAULT_OUT_TIME = "17:00"
ATTENDANCE_DEFAULT_BREAK_HOURS = 1.0


def parse_flexible_time(value, *, is_out_time: bool = False) -> str:
    """Parse shorthand attendance times to HH:MM (24-hour).

    Examples: 8 -> 08:00, 830 -> 08:30, 8.30 / 8.3 -> 08:30, 22.3 -> 22:30,
    17 or 5 (out) -> 17:00, 08:00 unchanged.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""

    token = raw.upper().replace(" ", "")
    meridiem = None
    for suffix, tag in (("PM", "pm"), ("A.M.", "am"), ("AM", "am"), ("P.M.", "pm")):
        if token.endswith(suffix):
            meridiem = tag
            token = token[: -len(suffix)]
            break

    token = token.strip().replace(",", ".")
    hour = minute = None

    if ":" in token:
        left, right = token.split(":", 1)
        if not left.isdigit() or not right.isdigit():
            raise ValueError(f"Invalid time: {value!r}")
        hour = int(left)
        minute = int(right)
    elif "." in token:
        left, right = token.split(".", 1)
        if not left.isdigit() or not right.isdigit():
            raise ValueError(f"Invalid time: {value!r}")
        hour = int(left)
        minute = int(right) * 10 if len(right) == 1 else int(right[:2])
    elif token.isdigit():
        if len(token) <= 2:
            hour = int(token)
            minute = 0
        elif len(token) == 3:
            hour = int(token[0])
            minute = int(token[1:])
        elif len(token) == 4:
            hour = int(token[:2])
            minute = int(token[2:])
        else:
            raise ValueError(f"Invalid time: {value!r}")
    else:
        raise ValueError(f"Invalid time: {value!r}")

    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    elif meridiem is None and is_out_time and 1 <= hour <= 7:
        hour += 12

    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid time: {value!r}")

    return f"{hour:02d}:{minute:02d}"


def calculate_hours(start, end, break_hr, fixed_hours=8.0, ot_allowed=True):
    start_norm = parse_flexible_time(start, is_out_time=False)
    end_norm = parse_flexible_time(end, is_out_time=True)
    if not start_norm or not end_norm:
        raise ValueError("In Time and Out Time are required (e.g. 8 and 5, or 08:00 and 17:00).")
    start_time = datetime.strptime(start_norm, "%H:%M")
    end_time = datetime.strptime(end_norm, "%H:%M")
    total_seconds = (end_time - start_time).total_seconds()
    if total_seconds < 0:
        total_seconds += 24 * 3600
    total = total_seconds / 3600
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
    from modules.payroll_engine import payroll_preview as _engine_preview

    return _engine_preview(employee_id, payroll_month)


def get_payroll_record(employee_id, payroll_month):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT * FROM payroll
        WHERE employee_id = ? AND payroll_month = ?
        ORDER BY id DESC LIMIT 1
        """,
        conn,
        params=(employee_id, payroll_month),
    )
    conn.close()
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def save_payroll_record(summary, deductions, workflow_status, payment_mode="", payment_status="Pending"):
    payroll_id = generate_id("PY", "payroll")
    conn = get_conn()
    existing = conn.execute(
        "SELECT payroll_id FROM payroll WHERE employee_id = ? AND payroll_month = ?",
        (summary["employee_id"], summary["payroll_month"]),
    ).fetchone()
    net_salary = max(0.0, float(summary.get("net_salary") or 0) - float(deductions or 0))
    summary = dict(summary)
    summary["deductions"] = deductions
    summary["net_salary"] = net_salary
    params = (
        summary.get("employee_name") or "",
        summary.get("payroll_year") or summary["payroll_month"].split("/")[1],
        summary.get("normal_salary_amount") or summary.get("base_salary") or 0,
        summary.get("ot_amount") or 0,
        deductions,
        net_salary,
        net_salary,
        workflow_status,
        payment_mode,
        payment_status,
        summary.get("payroll_period_start") or "",
        summary.get("payroll_period_end") or "",
        summary.get("total_month_days") or 0,
        summary.get("worked_days") or 0,
        summary.get("leave_days") or 0,
        summary.get("half_days") or 0,
        summary.get("absent_days") or 0,
        summary.get("paid_weekly_off_days") or 0,
        summary.get("paid_holiday_days") or 0,
        summary.get("total_worked_hours") or 0,
        summary.get("total_ot_hours") or 0,
        summary.get("holiday_ot_hours") or 0,
        summary.get("weekly_off_ot_hours") or 0,
        summary.get("normal_salary_amount") or 0,
        summary.get("weekly_off_paid_amount") or 0,
        summary.get("holiday_paid_amount") or 0,
        summary.get("normal_ot_amount") or 0,
        summary.get("ot_held_hours") or 0,
        workflow_status,
    )
    if existing:
        payroll_id = existing[0]
        conn.execute(
            """
            UPDATE payroll SET
                employee_name = ?, payroll_year = ?, base_salary = ?, ot_amount = ?, deductions = ?,
                salary = ?, net_salary = ?, salary_status = ?, payment_mode = ?, payment_status = ?,
                payroll_period_start = ?, payroll_period_end = ?,
                total_month_days = ?, worked_days = ?, leave_days = ?, half_days = ?, absent_days = ?,
                paid_weekly_off_days = ?, paid_holiday_days = ?, total_worked_hours = ?, total_ot_hours = ?,
                holiday_ot_hours = ?, weekly_off_ot_hours = ?, normal_salary_amount = ?,
                weekly_off_paid_amount = ?, holiday_paid_amount = ?, normal_ot_amount = ?, ot_held_hours = ?,
                workflow_status = ?
            WHERE payroll_id = ?
            """,
            (*params, payroll_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO payroll(
                payroll_id, employee_id, worker_id, payroll_month, payroll_year, employee_name,
                base_salary, ot_amount, deductions, salary, net_salary, salary_status,
                payment_mode, payment_status, payroll_period_start, payroll_period_end, total_month_days, worked_days, leave_days, half_days,
                absent_days, paid_weekly_off_days, paid_holiday_days, total_worked_hours,
                total_ot_hours, holiday_ot_hours, weekly_off_ot_hours, normal_salary_amount,
                weekly_off_paid_amount, holiday_paid_amount, normal_ot_amount, ot_held_hours,
                workflow_status
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                payroll_id,
                summary["employee_id"],
                summary["employee_id"],
                summary["payroll_month"],
                *params,
            ),
        )
    conn.commit()
    conn.close()
    return payroll_id


def list_payroll_by_workflow(workflow_status, payment_status=None):
    conn = get_conn()
    sql = """
        SELECT payroll_id, employee_id, employee_name, payroll_month, payroll_year,
               worked_days, paid_weekly_off_days, paid_holiday_days, total_ot_hours,
               ot_amount, deductions, net_salary, workflow_status, payment_status, salary_status
        FROM payroll
        WHERE COALESCE(workflow_status, salary_status, '') = ?
    """
    params = [workflow_status]
    if payment_status:
        sql += " AND COALESCE(payment_status, 'Pending') = ?"
        params.append(payment_status)
    sql += " ORDER BY id DESC"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def update_payroll_workflow(payroll_id, workflow_status, md_remarks=""):
    conn = get_conn()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    if workflow_status == "Submitted to MD":
        conn.execute(
            "UPDATE payroll SET workflow_status = ?, salary_status = ?, submitted_at = ? WHERE payroll_id = ?",
            (workflow_status, workflow_status, now, payroll_id),
        )
    elif workflow_status == "MD Approved":
        conn.execute(
            "UPDATE payroll SET workflow_status = ?, salary_status = ?, approved_at = ?, md_remarks = ? WHERE payroll_id = ?",
            (workflow_status, workflow_status, now, md_remarks, payroll_id),
        )
    else:
        conn.execute(
            "UPDATE payroll SET workflow_status = ?, salary_status = ?, md_remarks = ? WHERE payroll_id = ?",
            (workflow_status, workflow_status, md_remarks, payroll_id),
        )
    conn.commit()
    conn.close()


def mark_payroll_paid(payroll_id, payment_mode):
    conn = get_conn()
    now = datetime.now().strftime(DATE_FMT)
    conn.execute(
        """
        UPDATE payroll SET payment_mode = ?, payment_status = 'Paid', salary_status = 'PAID',
               paid_date = ?, paid_at = ?
        WHERE payroll_id = ?
        """,
        (payment_mode, now, datetime.now().strftime("%d/%m/%Y %H:%M"), payroll_id),
    )
    conn.commit()
    conn.close()


def delete_payroll_record(payroll_id):
    conn = get_conn()
    conn.execute(
        "UPDATE employee_advance SET deducted_payroll_id = NULL WHERE deducted_payroll_id = ?",
        (payroll_id,),
    )
    conn.execute("DELETE FROM payroll WHERE payroll_id = ?", (payroll_id,))
    conn.commit()
    conn.close()


def list_employee_payrolls(employee_id, limit=24):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT payroll_id, payroll_month, net_salary, deductions, workflow_status,
               payment_status, paid_date
        FROM payroll
        WHERE employee_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(employee_id, limit),
    )
    conn.close()
    return df


def get_attendance_record(attendance_id):
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM attendance WHERE id = ?", conn, params=(attendance_id,))
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else None


def update_attendance_record(attendance_id, fields):
    allowed = {
        "project_name", "attendance_date", "in_time", "out_time", "break_hours",
        "total_hours", "ot_hours", "status", "remarks", "attendance_category",
        "payment_type", "holiday_name", "worked_hours", "overtime",
        "start_time", "end_time", "fixed_working_hours", "applied_rate", "applied_ot_rate",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    cols = ", ".join(f"{k} = ?" for k in updates)
    conn = get_conn()
    conn.execute(f"UPDATE attendance SET {cols} WHERE id = ?", (*updates.values(), attendance_id))
    conn.commit()
    conn.close()


def delete_attendance_record(attendance_id):
    conn = get_conn()
    conn.execute("DELETE FROM attendance WHERE id = ?", (attendance_id,))
    conn.commit()
    conn.close()


STAFF_ADVANCE_STATUSES = ("Pending", "Approved", "Paid", "Rejected")


def save_staff_advance(
    employee_id,
    employee_name,
    advance_date,
    amount,
    payment_mode="",
    reason="",
    remarks="",
    funding_source="Company Fund",
    project_name="",
    payment_head="",
    created_by="",
    payment_status="Pending",
):
    advance_id = generate_id("EADV", "employee_advance")
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO employee_advance(
            advance_id, employee_id, employee_name, advance_date, amount,
            payment_mode, reason, remarks, payment_status, created_by, created_at,
            funding_source, project_name, payment_head
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            advance_id,
            employee_id,
            employee_name,
            advance_date,
            float(amount),
            payment_mode or "",
            reason or "",
            remarks or "",
            payment_status or "Pending",
            created_by or "",
            now,
            funding_source or "Company Fund",
            project_name or "",
            payment_head or "",
        ),
    )
    conn.commit()
    conn.close()
    return advance_id


def save_employee_advance(employee_id, employee_name, advance_date, amount, remarks=""):
    """Legacy helper — creates a paid advance (finance should use save_staff_advance)."""
    return save_staff_advance(
        employee_id,
        employee_name,
        advance_date,
        amount,
        payment_mode="Cash",
        remarks=remarks,
        payment_status="Paid",
    )


def update_staff_advance_status(
    advance_id,
    payment_status,
    actor="",
    payment_mode="",
    approved_by="",
):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    conn = get_conn()
    cur = conn.cursor()
    if payment_status == "Approved":
        cur.execute(
            """
            UPDATE employee_advance
            SET payment_status = ?, approved_by = ?, approved_at = ?
            WHERE advance_id = ?
            """,
            (payment_status, approved_by or actor, now, advance_id),
        )
    elif payment_status == "Paid":
        cur.execute(
            """
            UPDATE employee_advance
            SET payment_status = ?, payment_mode = COALESCE(NULLIF(?, ''), payment_mode),
                paid_by = ?, paid_at = ?
            WHERE advance_id = ?
            """,
            (payment_status, payment_mode, actor, now, advance_id),
        )
    else:
        cur.execute(
            "UPDATE employee_advance SET payment_status = ? WHERE advance_id = ?",
            (payment_status, advance_id),
        )
    conn.commit()
    conn.close()


def list_staff_advances(employee_id=None, payment_status=None, limit=300):
    conn = get_conn()
    sql = """
        SELECT advance_id, employee_id, employee_name, advance_date, amount,
               payment_mode, funding_source, project_name, payment_head,
               reason, remarks, approved_by, payment_status,
               approved_at, paid_at, paid_by, deducted_payroll_id, created_by, created_at
        FROM employee_advance
        WHERE 1=1
    """
    params = []
    if employee_id:
        sql += " AND employee_id = ?"
        params.append(employee_id)
    if payment_status:
        sql += " AND COALESCE(payment_status, 'Paid') = ?"
        params.append(payment_status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def get_employee_advance_summary(employee_id, current_deduction=0.0):
    """Read-only payroll summary: taken, deducted, current deduction, remaining."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT amount, deducted_payroll_id, COALESCE(payment_status, 'Paid') AS payment_status
        FROM employee_advance
        WHERE employee_id = ?
        """,
        (employee_id,),
    ).fetchall()
    conn.close()

    advance_taken = 0.0
    already_deducted = 0.0
    open_balance = 0.0
    for amount, deducted_id, status in rows:
        if str(status) not in {"Paid", "PAID"}:
            continue
        amt = float(amount or 0)
        advance_taken += amt
        if deducted_id:
            already_deducted += amt
        else:
            open_balance += amt

    current_deduction = max(0.0, float(current_deduction or 0))
    balance_remaining = max(0.0, open_balance - current_deduction)
    return {
        "advance_taken": round(advance_taken, 2),
        "already_deducted": round(already_deducted, 2),
        "previous_balance": round(open_balance, 2),
        "current_deduction": round(current_deduction, 2),
        "balance_remaining": round(balance_remaining, 2),
        "open_balance": round(open_balance, 2),
    }


def get_employee_advance_ledger(employee_id, payroll_month):
    """Advances split by last paid salary vs current payroll month."""
    conn = get_conn()
    advances_df = pd.read_sql_query(
        """
        SELECT advance_id, advance_date, amount, remarks, deducted_payroll_id,
               payment_mode, reason, approved_by, payment_status, paid_at
        FROM employee_advance
        WHERE employee_id = ?
        ORDER BY advance_date DESC, id DESC
        """,
        conn,
        params=(employee_id,),
    )
    last_paid = conn.execute(
        """
        SELECT payroll_month, paid_date, net_salary
        FROM payroll
        WHERE employee_id = ?
          AND UPPER(COALESCE(payment_status, '')) = 'PAID'
        ORDER BY id DESC LIMIT 1
        """,
        (employee_id,),
    ).fetchone()
    conn.close()

    month, year = payroll_month.split("/")
    month_suffix = f"/{month}/{year}"
    open_advances = []
    before_salary = []
    after_last_paid = []
    for_month = []

    for _, row in advances_df.iterrows():
        item = row.to_dict()
        pay_st = str(item.get("payment_status") or "Paid")
        if item.get("deducted_payroll_id"):
            item["status"] = "Deducted"
        elif pay_st == "Paid":
            item["status"] = "Open"
            open_advances.append(item)
        else:
            item["status"] = pay_st
        if month_suffix in str(item.get("advance_date", "")):
            for_month.append(item)
        if last_paid and last_paid[1]:
            try:
                adv_dt = datetime.strptime(str(item["advance_date"])[:10], DATE_FMT)
                paid_dt = datetime.strptime(str(last_paid[1])[:10], DATE_FMT)
                if adv_dt <= paid_dt:
                    before_salary.append(item)
                else:
                    after_last_paid.append(item)
            except ValueError:
                after_last_paid.append(item)
        else:
            before_salary.append(item)

    return {
        "last_paid_month": last_paid[0] if last_paid else None,
        "last_paid_date": last_paid[1] if last_paid else None,
        "last_paid_amount": float(last_paid[2] or 0) if last_paid else 0.0,
        "open_balance": round(sum(float(a.get("amount") or 0) for a in open_advances), 2),
        "for_month_total": round(sum(float(a.get("amount") or 0) for a in for_month if a.get("status") == "Open"), 2),
        "open_advances": open_advances,
        "for_month": for_month,
        "before_last_paid": before_salary,
        "after_last_paid": after_last_paid,
        "all_advances": advances_df.to_dict("records") if not advances_df.empty else [],
    }


def mark_advances_deducted(employee_id, payroll_id, payroll_month):
    conn = get_conn()
    month, year = payroll_month.split("/")
    conn.execute(
        """
        UPDATE employee_advance SET deducted_payroll_id = ?
        WHERE employee_id = ?
          AND COALESCE(deducted_payroll_id, '') = ''
          AND COALESCE(payment_status, 'Paid') = 'Paid'
          AND advance_date LIKE ?
        """,
        (payroll_id, employee_id, f"%/{month}/{year}"),
    )
    conn.commit()
    conn.close()


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
    fk = get_finance_kpi_summary()
    monthly_expense = fk.get("monthly_expenses") or sum_query(
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
        "cash_balance": fk.get("cash_balance", 0),
        "bank_balance": fk.get("bank_balance", 0),
        "creditors": fk.get("creditors", 0),
        "debtors": fk.get("debtors", 0),
        "petty_issued": fk.get("petty_issued", 0),
        "petty_utilized": fk.get("petty_utilized", 0),
        "petty_pending_verify": fk.get("petty_pending_verify", 0),
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


# —— Master data CRUD ——


def load_company_master():
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT company_id, company_name, gst_number, address, phone, email, financial_year
        FROM company_master
        ORDER BY id
        LIMIT 1
        """,
        conn,
    )
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else {}


def save_company_master(data, actor=""):
    conn = get_conn()
    existing = conn.execute("SELECT company_id FROM company_master ORDER BY id LIMIT 1").fetchone()
    company_id = (existing[0] if existing else None) or data.get("company_id") or generate_id("CMP", "company_master", id_column="company_id", conn=conn)
    conn.execute(
        """
        INSERT INTO company_master(
            company_id, company_name, gst_number, address, phone, email, financial_year, updated_by, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(company_id) DO UPDATE SET
            company_name = excluded.company_name,
            gst_number = excluded.gst_number,
            address = excluded.address,
            phone = excluded.phone,
            email = excluded.email,
            financial_year = excluded.financial_year,
            updated_by = excluded.updated_by,
            updated_at = excluded.updated_at
        """,
        (
            company_id,
            data.get("company_name", ""),
            data.get("gst_number", ""),
            data.get("address", ""),
            data.get("phone", ""),
            data.get("email", ""),
            data.get("financial_year", ""),
            actor,
            _finance_timestamp(),
        ),
    )
    conn.commit()
    conn.close()
    return company_id


def load_vendors(vendor_type=None, limit=500):
    conn = get_conn()
    sql = """
        SELECT vendor_id, vendor_type, supplier_name, gst_number, contact_person,
               mobile, email, address, status, subcontractor_id
        FROM vendors
        WHERE 1=1
    """
    params = []
    if vendor_type:
        sql += " AND vendor_type = ?"
        params.append(vendor_type)
    sql += " ORDER BY supplier_name LIMIT ?"
    params.append(int(limit))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def save_vendor(data, actor=""):
    conn = get_conn()
    vendor_id = data.get("vendor_id") or generate_id("VND", "vendors", id_column="vendor_id", conn=conn)
    conn.execute(
        """
        INSERT INTO vendors(
            vendor_id, vendor_type, supplier_name, gst_number, contact_person,
            mobile, email, address, status, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(vendor_id) DO UPDATE SET
            vendor_type = excluded.vendor_type,
            supplier_name = excluded.supplier_name,
            gst_number = excluded.gst_number,
            contact_person = excluded.contact_person,
            mobile = excluded.mobile,
            email = excluded.email,
            address = excluded.address,
            status = excluded.status
        """,
        (
            vendor_id,
            data.get("vendor_type", "Supplier"),
            data.get("supplier_name", ""),
            data.get("gst_number", ""),
            data.get("contact_person", ""),
            data.get("mobile", ""),
            data.get("email", ""),
            data.get("address", ""),
            data.get("status", "Active"),
            _finance_timestamp(),
        ),
    )
    conn.commit()
    conn.close()
    return vendor_id


def load_chart_of_accounts(active_only=True):
    conn = get_conn()
    sql = "SELECT account_code, account_name, account_type, is_active FROM chart_of_accounts"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY account_type, account_code"
    df = pd.read_sql_query(sql, conn)
    conn.close()
    return df


def load_ledger_entries(account_name=None, from_date=None, to_date=None, limit=500):
    conn = get_conn()
    sql = """
        SELECT j.entry_date, j.document_no, j.source_type, j.source_id, j.narration,
               l.account_name, l.debit, l.credit, l.project_name, l.party_name
        FROM ledger_lines l
        INNER JOIN journal_entries j ON j.journal_id = l.journal_id
        WHERE 1=1
    """
    params = []
    if account_name:
        sql += " AND l.account_name = ?"
        params.append(account_name)
    if from_date:
        sql += " AND j.entry_date >= ?"
        params.append(from_date)
    if to_date:
        sql += " AND j.entry_date <= ?"
        params.append(to_date)
    sql += " ORDER BY j.id DESC, l.id LIMIT ?"
    params.append(int(limit))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def save_expense_entry(data, actor=""):
    conn = get_conn()
    expense_id = data.get("expense_id") or generate_id("EXP", "expense_entries", id_column="expense_id", conn=conn)
    doc_no = data.get("document_no") or next_document_number("expense_entry", conn=conn)
    conn.execute(
        """
        INSERT INTO expense_entries(
            expense_id, document_no, expense_date, project_name, expense_head, amount,
            status, entered_by, approved_by, remarks, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(expense_id) DO UPDATE SET
            expense_date = excluded.expense_date,
            project_name = excluded.project_name,
            expense_head = excluded.expense_head,
            amount = excluded.amount,
            status = excluded.status,
            approved_by = excluded.approved_by,
            remarks = excluded.remarks
        """,
        (
            expense_id,
            doc_no,
            data.get("expense_date", datetime.now().strftime(DATE_FMT)),
            data.get("project_name", ""),
            data.get("expense_head", ""),
            float(data.get("amount") or 0),
            data.get("status", "Submitted"),
            data.get("entered_by") or actor,
            data.get("approved_by", ""),
            data.get("remarks", ""),
            _finance_timestamp(),
        ),
    )
    conn.commit()
    conn.close()
    return expense_id, doc_no


def save_gst_payment(data, actor=""):
    conn = get_conn()
    payment_id = data.get("payment_id") or generate_id("GST", "gst_payments", id_column="payment_id", conn=conn)
    conn.execute(
        """
        INSERT INTO gst_payments(payment_id, challan_no, period, payment_date, amount, created_by, created_at)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(payment_id) DO UPDATE SET
            challan_no = excluded.challan_no,
            period = excluded.period,
            payment_date = excluded.payment_date,
            amount = excluded.amount
        """,
        (
            payment_id,
            data.get("challan_no", ""),
            data.get("period", ""),
            data.get("payment_date", datetime.now().strftime(DATE_FMT)),
            float(data.get("amount") or 0),
            actor,
            _finance_timestamp(),
        ),
    )
    if str(data.get("status", "")).lower() in ("approved", "posted", "settled"):
        post_to_ledger_on_approval(
            conn,
            "gst_payment",
            {"payment_id": payment_id, "amount": data.get("amount"), "payment_date": data.get("payment_date")},
            actor,
        )
    conn.commit()
    conn.close()
    return payment_id


def save_tds_deduction(data, actor=""):
    conn = get_conn()
    deduction_id = data.get("deduction_id") or generate_id("TDS", "tds_deductions", id_column="deduction_id", conn=conn)
    conn.execute(
        """
        INSERT INTO tds_deductions(
            deduction_id, vendor, invoice_ref, section, tds_pct, amount, created_at
        ) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(deduction_id) DO UPDATE SET
            vendor = excluded.vendor,
            invoice_ref = excluded.invoice_ref,
            section = excluded.section,
            tds_pct = excluded.tds_pct,
            amount = excluded.amount
        """,
        (
            deduction_id,
            data.get("vendor", ""),
            data.get("invoice_ref", ""),
            data.get("section", ""),
            float(data.get("tds_pct") or 0),
            float(data.get("amount") or 0),
            _finance_timestamp(),
        ),
    )
    if str(data.get("post_ledger", "")).lower() in ("1", "true", "yes"):
        jid = post_to_ledger_on_approval(
            conn,
            "tds_deduction",
            {
                "deduction_id": deduction_id,
                "amount": data.get("amount"),
                "vendor": data.get("vendor"),
                "narration": f"TDS {data.get('section', '')} — {data.get('vendor', '')}",
            },
            actor,
        )
        if jid:
            conn.execute("UPDATE tds_deductions SET journal_id = ? WHERE deduction_id = ?", (jid, deduction_id))
    conn.commit()
    conn.close()
    return deduction_id


def load_material_master(limit=500):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT material_id, material_code, material_name, unit, status
        FROM material_master
        ORDER BY material_name
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def save_material_master(data):
    conn = get_conn()
    material_id = data.get("material_id") or generate_id("MAT", "material_master", id_column="material_id", conn=conn)
    conn.execute(
        """
        INSERT INTO material_master(material_id, material_code, material_name, unit, status)
        VALUES(?,?,?,?,?)
        ON CONFLICT(material_id) DO UPDATE SET
            material_code = excluded.material_code,
            material_name = excluded.material_name,
            unit = excluded.unit,
            status = excluded.status
        """,
        (
            material_id,
            data.get("material_code", ""),
            data.get("material_name", ""),
            data.get("unit", "Nos"),
            data.get("status", "Active"),
        ),
    )
    conn.commit()
    conn.close()
    return material_id


def load_trial_balance(from_date=None, to_date=None):
    """Account-wise debit/credit totals from GL joined to chart of accounts."""
    conn = get_conn()
    sql = """
        SELECT c.account_code, c.account_name, c.account_type,
               ROUND(COALESCE(SUM(l.debit), 0), 2) AS total_debit,
               ROUND(COALESCE(SUM(l.credit), 0), 2) AS total_credit,
               ROUND(COALESCE(SUM(l.debit), 0) - COALESCE(SUM(l.credit), 0), 2) AS balance
        FROM chart_of_accounts c
        LEFT JOIN ledger_lines l ON l.account_name = c.account_name
        LEFT JOIN journal_entries j ON j.journal_id = l.journal_id
        WHERE c.is_active = 1
    """
    params: list = []
    if from_date:
        sql += " AND (j.entry_date IS NULL OR j.entry_date >= ?)"
        params.append(from_date)
    if to_date:
        sql += " AND (j.entry_date IS NULL OR j.entry_date <= ?)"
        params.append(to_date)
    sql += """
        GROUP BY c.account_code, c.account_name, c.account_type
        HAVING total_debit > 0 OR total_credit > 0
        ORDER BY c.account_type, c.account_code
    """
    df = pd.read_sql_query(sql, conn, params=params or None)
    conn.close()
    return df


def create_manual_journal(data, actor=""):
    """Post a balanced manual journal voucher."""
    lines = data.get("lines") or []
    total_debit = round(sum(float(ln.get("debit") or 0) for ln in lines), 2)
    total_credit = round(sum(float(ln.get("credit") or 0) for ln in lines), 2)
    if not lines or abs(total_debit - total_credit) > 0.01:
        raise ValueError("Journal lines must balance (total debit = total credit).")
    conn = get_conn()
    journal_id = generate_id("JRN", "journal_entries", id_column="journal_id", conn=conn)
    document_no = next_document_number("journal_voucher", conn=conn)
    jid = _create_journal_entry(
        conn,
        journal_id,
        document_no,
        data.get("entry_date") or datetime.now().strftime(DATE_FMT),
        "manual_journal",
        data.get("source_id") or journal_id,
        data.get("narration", "Manual journal voucher"),
        lines,
        actor,
        data.get("project_name", ""),
    )
    conn.commit()
    conn.close()
    return jid, document_no


def load_creditors_summary(limit=200):
    """Outstanding supplier balances from approved/unpaid site expenses."""
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT supplier AS party_name, project_name,
               COUNT(*) AS invoice_count,
               ROUND(COALESCE(SUM(total_invoice_value), 0), 2) AS outstanding
        FROM site_expenses
        WHERE status IN ('Submitted', 'Verified', 'PM Approved', 'Approved')
          AND COALESCE(is_void, 0) = 0
          AND COALESCE(supplier, '') != ''
        GROUP BY supplier, project_name
        ORDER BY outstanding DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def load_gst_payments(limit=200):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT payment_id, challan_no, period, payment_date, amount, journal_id, created_by, created_at
        FROM gst_payments
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def load_tds_deductions(limit=200):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT deduction_id, vendor, invoice_ref, section, tds_pct, amount, journal_id, created_at
        FROM tds_deductions
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def load_tds_payments(limit=200):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT payment_id, challan_no, period, payment_date, amount, journal_id, created_by, created_at
        FROM tds_payments
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def save_tds_payment(data, actor=""):
    conn = get_conn()
    payment_id = data.get("payment_id") or generate_id("TDP", "tds_payments", id_column="payment_id", conn=conn)
    conn.execute(
        """
        INSERT INTO tds_payments(payment_id, challan_no, period, payment_date, amount, created_by, created_at)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(payment_id) DO UPDATE SET
            challan_no = excluded.challan_no,
            period = excluded.period,
            payment_date = excluded.payment_date,
            amount = excluded.amount
        """,
        (
            payment_id,
            data.get("challan_no", ""),
            data.get("period", ""),
            data.get("payment_date", datetime.now().strftime(DATE_FMT)),
            float(data.get("amount") or 0),
            actor,
            _finance_timestamp(),
        ),
    )
    if str(data.get("post_ledger", "")).lower() in ("1", "true", "yes"):
        jid = post_journal_entry(
            conn,
            "tds_payment",
            {"amount": data.get("amount")},
            "tds_payment",
            payment_id,
            actor,
            data.get("payment_date"),
            data.get("narration", "TDS payment to government"),
        )
        if jid:
            conn.execute("UPDATE tds_payments SET journal_id = ? WHERE payment_id = ?", (jid, payment_id))
    conn.commit()
    conn.close()
    return payment_id


def load_subcontractor_work_orders(limit=200):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT wo_id, wo_number, project_name, subcontractor_name, value, status, created_at
        FROM subcontractor_work_orders
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def save_subcontractor_work_order(data):
    conn = get_conn()
    wo_id = data.get("wo_id") or generate_id("SWO", "subcontractor_work_orders", id_column="wo_id", conn=conn)
    conn.execute(
        """
        INSERT INTO subcontractor_work_orders(
            wo_id, wo_number, project_name, subcontractor_name, value, status, created_at
        ) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(wo_id) DO UPDATE SET
            wo_number = excluded.wo_number,
            project_name = excluded.project_name,
            subcontractor_name = excluded.subcontractor_name,
            value = excluded.value,
            status = excluded.status
        """,
        (
            wo_id,
            data.get("wo_number", ""),
            data.get("project_name", ""),
            data.get("subcontractor_name", ""),
            float(data.get("value") or 0),
            data.get("status", "Active"),
            _finance_timestamp(),
        ),
    )
    conn.commit()
    conn.close()
    return wo_id


def load_security_deposits(limit=200):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT register_id, contractor, project_name, retained_amount, released_amount, balance, updated_at
        FROM security_deposit_register
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def save_security_deposit(data):
    conn = get_conn()
    register_id = data.get("register_id") or generate_id(
        "SDR", "security_deposit_register", id_column="register_id", conn=conn
    )
    retained = float(data.get("retained_amount") or 0)
    released = float(data.get("released_amount") or 0)
    balance = round(retained - released, 2)
    conn.execute(
        """
        INSERT INTO security_deposit_register(
            register_id, contractor, project_name, retained_amount, released_amount, balance, updated_at
        ) VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(register_id) DO UPDATE SET
            contractor = excluded.contractor,
            project_name = excluded.project_name,
            retained_amount = excluded.retained_amount,
            released_amount = excluded.released_amount,
            balance = excluded.balance,
            updated_at = excluded.updated_at
        """,
        (
            register_id,
            data.get("contractor", ""),
            data.get("project_name", ""),
            retained,
            released,
            balance,
            _finance_timestamp(),
        ),
    )
    conn.commit()
    conn.close()
    return register_id


def load_assets(limit=200):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT asset_id, asset_code, asset_name, purchase_date, cost, location, assigned_to, status
        FROM asset_register
        ORDER BY asset_name
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def save_asset(data):
    conn = get_conn()
    asset_id = data.get("asset_id") or generate_id("AST", "asset_register", id_column="asset_id", conn=conn)
    conn.execute(
        """
        INSERT INTO asset_register(
            asset_id, asset_code, asset_name, purchase_date, cost, location, assigned_to, status
        ) VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(asset_id) DO UPDATE SET
            asset_code = excluded.asset_code,
            asset_name = excluded.asset_name,
            purchase_date = excluded.purchase_date,
            cost = excluded.cost,
            location = excluded.location,
            assigned_to = excluded.assigned_to,
            status = excluded.status
        """,
        (
            asset_id,
            data.get("asset_code", ""),
            data.get("asset_name", ""),
            data.get("purchase_date", ""),
            float(data.get("cost") or 0),
            data.get("location", ""),
            data.get("assigned_to", ""),
            data.get("status", "Active"),
        ),
    )
    conn.commit()
    conn.close()
    return asset_id


def load_asset_transfers(limit=200):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT transfer_id, asset_id, from_location, to_location, transfer_date, remarks, created_by, created_at
        FROM asset_transfers
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def save_asset_transfer(data, actor=""):
    conn = get_conn()
    transfer_id = data.get("transfer_id") or generate_id(
        "ATR", "asset_transfers", id_column="transfer_id", conn=conn
    )
    conn.execute(
        """
        INSERT INTO asset_transfers(
            transfer_id, asset_id, from_location, to_location, transfer_date, remarks, created_by, created_at
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            transfer_id,
            data.get("asset_id", ""),
            data.get("from_location", ""),
            data.get("to_location", ""),
            data.get("transfer_date", datetime.now().strftime(DATE_FMT)),
            data.get("remarks", ""),
            actor,
            _finance_timestamp(),
        ),
    )
    asset_id = data.get("asset_id")
    if asset_id and data.get("to_location"):
        conn.execute(
            "UPDATE asset_register SET location = ? WHERE asset_id = ?",
            (data.get("to_location"), asset_id),
        )
    conn.commit()
    conn.close()
    return transfer_id


def load_asset_depreciation(limit=200):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT depreciation_id, asset_id, period, amount, remarks, created_by, created_at
        FROM asset_depreciation
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def save_asset_depreciation(data, actor=""):
    conn = get_conn()
    depreciation_id = data.get("depreciation_id") or generate_id(
        "DEP", "asset_depreciation", id_column="depreciation_id", conn=conn
    )
    conn.execute(
        """
        INSERT INTO asset_depreciation(
            depreciation_id, asset_id, period, amount, remarks, created_by, created_at
        ) VALUES(?,?,?,?,?,?,?)
        """,
        (
            depreciation_id,
            data.get("asset_id", ""),
            data.get("period", ""),
            float(data.get("amount") or 0),
            data.get("remarks", ""),
            actor,
            _finance_timestamp(),
        ),
    )
    conn.commit()
    conn.close()
    return depreciation_id


def load_tools(limit=200):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT tool_id, tool_code, tool_name, project_name, quantity, condition, status, updated_at
        FROM tools_register
        ORDER BY tool_name
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def save_tool(data):
    conn = get_conn()
    tool_id = data.get("tool_id") or generate_id("TL", "tools_register", id_column="tool_id", conn=conn)
    conn.execute(
        """
        INSERT INTO tools_register(
            tool_id, tool_code, tool_name, project_name, quantity, condition, status, updated_at
        ) VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(tool_id) DO UPDATE SET
            tool_code = excluded.tool_code,
            tool_name = excluded.tool_name,
            project_name = excluded.project_name,
            quantity = excluded.quantity,
            condition = excluded.condition,
            status = excluded.status,
            updated_at = excluded.updated_at
        """,
        (
            tool_id,
            data.get("tool_code", ""),
            data.get("tool_name", ""),
            data.get("project_name", ""),
            float(data.get("quantity") or 1),
            data.get("condition", "Good"),
            data.get("status", "Available"),
            _finance_timestamp(),
        ),
    )
    conn.commit()
    conn.close()
    return tool_id


def load_material_issues(limit=200):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT issue_id, issue_no, project_name, material_code, material_name, quantity, issue_date, status, created_by
        FROM material_issues
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def save_material_issue(data, actor=""):
    conn = get_conn()
    issue_id = data.get("issue_id") or generate_id("MI", "material_issues", id_column="issue_id", conn=conn)
    issue_no = data.get("issue_no") or next_document_number("material_request", conn=conn)
    conn.execute(
        """
        INSERT INTO material_issues(
            issue_id, issue_no, project_name, material_code, material_name, quantity, issue_date, status, created_by, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            issue_id,
            issue_no,
            data.get("project_name", ""),
            data.get("material_code", ""),
            data.get("material_name", ""),
            float(data.get("quantity") or 0),
            data.get("issue_date", datetime.now().strftime(DATE_FMT)),
            data.get("status", "Issued"),
            actor,
            _finance_timestamp(),
        ),
    )
    conn.commit()
    conn.close()
    return issue_id, issue_no
