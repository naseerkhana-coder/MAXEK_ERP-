"""Bank & Treasury Management — schema, business logic, reports."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any

BANK_ACCOUNT_TYPES = ("Current", "Savings", "OD", "Escrow", "Security Deposit")
BANK_PAYMENT_TYPES = ("Vendor", "Salary", "Petty Cash", "Expense", "Subcontractor", "GST", "TDS")
BG_TYPES = ("Bid Bond", "EMD BG", "Performance BG", "Advance BG", "Retention BG")
RECON_STATUSES = ("matched", "unmatched", "pending")
CHEQUE_STATUSES = ("Issued", "Deposited", "Cleared", "Cancelled", "Bounced")
CHEQUE_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "Issued": ("Deposited", "Cancelled"),
    "Deposited": ("Cleared", "Bounced", "Cancelled"),
    "Cleared": (),
    "Cancelled": (),
    "Bounced": (),
}
PDC_TYPES = ("Received", "Issued")
PDC_STATUSES = ("Pending", "Deposited", "Cleared", "Bounced", "Cancelled")
PDC_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "Pending": ("Deposited", "Cancelled"),
    "Deposited": ("Cleared", "Bounced", "Cancelled"),
    "Cleared": (),
    "Bounced": (),
    "Cancelled": (),
}
PDC_DUE_ALERT_DAYS = (7, 3)
PDC_ACTIVE_STATUSES = ("Pending", "Deposited")
FD_STATUSES = ("Active", "Matured", "Renewed", "Closed")
FD_MATURITY_ALERT_DAYS = (90, 60, 30, 7)
FD_ACTIVE_STATUSES = ("Active",)
LC_STATUSES = ("Active", "Utilized", "Expired", "Closed")
SECURITY_DEPOSIT_TYPES = ("EMD", "SD", "PBG", "Other")
SECURITY_DEPOSIT_STATUSES = ("Active", "Released", "Forfeited", "Matured")
BG_EXPIRY_ALERT_DAYS = (90, 60, 30, 7)
BANK_DOCUMENT_TYPES = (
    "Bank Account Opening Form",
    "BG Copy",
    "FD Receipt",
    "Security Deposit Receipt",
    "Treasury Document",
    "Loan Document",
)
BANK_DOCUMENT_ENTITY_TYPES = (
    "bank_account",
    "bank_guarantee",
    "fixed_deposit",
    "security_deposit",
    "contract",
)
DOCUMENT_TYPE_DEFAULT_ENTITY = {
    "Bank Account Opening Form": "bank_account",
    "BG Copy": "bank_guarantee",
    "FD Receipt": "fixed_deposit",
    "Security Deposit Receipt": "security_deposit",
    "Contract Agreement": "contract",
    "Treasury Document": "bank_account",
    "Loan Document": "bank_account",
}
TREASURY_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".xlsx", ".xls"}
MAX_TREASURY_UPLOAD_BYTES = 10 * 1024 * 1024

DEFAULT_PAYMENT_APPROVAL_MATRIX = [
    (0, 50000, "Accounts Manager"),
    (50000.01, 500000, "Managing Director"),
    (500000.01, 999999999, "Managing Director"),
]


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_column(db, table: str, column: str, col_type: str) -> None:
    if not _table_exists(db, table):
        return
    cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def log_treasury_audit(
    db,
    entity_type: str,
    entity_id: int,
    action: str,
    actor: str = "",
    details: str = "",
) -> None:
    db.execute(
        "INSERT INTO treasury_audit_log(entity_type, entity_id, action, actor, details, created_at) "
        "VALUES(?,?,?,?,?,?)",
        (entity_type, entity_id, action, actor, details, _now_ts()),
    )


def ensure_treasury_schema(db) -> None:
    """Idempotent treasury schema for Phase 1 foundation."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS bank_accounts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_name TEXT NOT NULL,
            branch TEXT,
            account_number TEXT NOT NULL,
            ifsc_swift TEXT,
            account_type TEXT DEFAULT 'Current',
            currency TEXT DEFAULT 'INR',
            opening_balance REAL DEFAULT 0,
            authorized_signatory TEXT,
            od_limit REAL DEFAULT 0,
            interest_rate REAL DEFAULT 0,
            current_balance REAL DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT
        )
    """)
    for column, col_type in (
        ("bank_name", "TEXT"),
        ("branch", "TEXT"),
        ("account_number", "TEXT"),
        ("ifsc_swift", "TEXT"),
        ("account_type", "TEXT DEFAULT 'Current'"),
        ("currency", "TEXT DEFAULT 'INR'"),
        ("opening_balance", "REAL DEFAULT 0"),
        ("authorized_signatory", "TEXT"),
        ("od_limit", "REAL DEFAULT 0"),
        ("interest_rate", "REAL DEFAULT 0"),
        ("current_balance", "REAL DEFAULT 0"),
        ("is_active", "INTEGER DEFAULT 1"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "bank_accounts", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS bank_payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_date TEXT,
            bank_account_id INTEGER NOT NULL,
            payment_type TEXT DEFAULT 'Vendor',
            beneficiary TEXT,
            utr_number TEXT,
            amount REAL DEFAULT 0,
            remarks TEXT,
            status TEXT DEFAULT 'Pending',
            approval_status TEXT DEFAULT 'Pending Checker',
            approver_tier TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            FOREIGN KEY(bank_account_id) REFERENCES bank_accounts(id)
        )
    """)
    for column, col_type in (
        ("payment_date", "TEXT"),
        ("bank_account_id", "INTEGER"),
        ("payment_type", "TEXT"),
        ("beneficiary", "TEXT"),
        ("utr_number", "TEXT"),
        ("amount", "REAL DEFAULT 0"),
        ("remarks", "TEXT"),
        ("status", "TEXT DEFAULT 'Pending'"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
        ("approver_tier", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "bank_payments", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS bank_receipts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_date TEXT,
            bank_account_id INTEGER NOT NULL,
            client TEXT,
            utr_number TEXT,
            amount REAL DEFAULT 0,
            receipt_type TEXT DEFAULT 'Client Receipt',
            remarks TEXT,
            status TEXT DEFAULT 'Pending',
            approval_status TEXT DEFAULT 'Pending Checker',
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            FOREIGN KEY(bank_account_id) REFERENCES bank_accounts(id)
        )
    """)
    for column, col_type in (
        ("receipt_date", "TEXT"),
        ("bank_account_id", "INTEGER"),
        ("client", "TEXT"),
        ("utr_number", "TEXT"),
        ("amount", "REAL DEFAULT 0"),
        ("receipt_type", "TEXT"),
        ("remarks", "TEXT"),
        ("status", "TEXT DEFAULT 'Pending'"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "bank_receipts", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS bank_guarantees(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bg_number TEXT,
            bank_account_id INTEGER,
            bg_type TEXT DEFAULT 'Performance BG',
            project_id INTEGER,
            beneficiary TEXT,
            amount REAL DEFAULT 0,
            issue_date TEXT,
            expiry_date TEXT,
            status TEXT DEFAULT 'Active',
            approval_status TEXT DEFAULT 'Pending Checker',
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            FOREIGN KEY(bank_account_id) REFERENCES bank_accounts(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for column, col_type in (
        ("bg_number", "TEXT"),
        ("bank_account_id", "INTEGER"),
        ("bg_type", "TEXT"),
        ("project_id", "INTEGER"),
        ("beneficiary", "TEXT"),
        ("amount", "REAL DEFAULT 0"),
        ("issue_date", "TEXT"),
        ("expiry_date", "TEXT"),
        ("status", "TEXT DEFAULT 'Active'"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
        ("remarks", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "bank_guarantees", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS bank_overdrafts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_account_id INTEGER NOT NULL UNIQUE,
            od_limit REAL DEFAULT 0,
            utilized REAL DEFAULT 0,
            interest_rate REAL DEFAULT 0,
            updated_at TEXT,
            FOREIGN KEY(bank_account_id) REFERENCES bank_accounts(id)
        )
    """)
    for column, col_type in (
        ("bank_account_id", "INTEGER"),
        ("od_limit", "REAL DEFAULT 0"),
        ("utilized", "REAL DEFAULT 0"),
        ("interest_rate", "REAL DEFAULT 0"),
        ("updated_at", "TEXT"),
    ):
        _ensure_column(db, "bank_overdrafts", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS bank_reconciliation(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_account_id INTEGER NOT NULL,
            erp_txn_id INTEGER,
            erp_txn_type TEXT,
            bank_stmt_ref TEXT,
            txn_date TEXT,
            amount REAL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            remarks TEXT,
            created_at TEXT,
            FOREIGN KEY(bank_account_id) REFERENCES bank_accounts(id)
        )
    """)
    for column, col_type in (
        ("bank_account_id", "INTEGER"),
        ("erp_txn_id", "INTEGER"),
        ("erp_txn_type", "TEXT"),
        ("bank_stmt_ref", "TEXT"),
        ("txn_date", "TEXT"),
        ("amount", "REAL DEFAULT 0"),
        ("status", "TEXT DEFAULT 'pending'"),
        ("remarks", "TEXT"),
        ("created_at", "TEXT"),
    ):
        _ensure_column(db, "bank_reconciliation", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS bank_cheques(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_account_id INTEGER NOT NULL,
            cheque_number TEXT,
            issue_date TEXT,
            beneficiary TEXT,
            amount REAL DEFAULT 0,
            status TEXT DEFAULT 'Issued',
            remarks TEXT,
            created_at TEXT,
            FOREIGN KEY(bank_account_id) REFERENCES bank_accounts(id)
        )
    """)
    for column, col_type in (
        ("bank_account_id", "INTEGER"),
        ("cheque_number", "TEXT"),
        ("issue_date", "TEXT"),
        ("beneficiary", "TEXT"),
        ("amount", "REAL DEFAULT 0"),
        ("status", "TEXT DEFAULT 'Issued'"),
        ("remarks", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "bank_cheques", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS pdc_register(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pdc_type TEXT DEFAULT 'Received',
            bank_account_id INTEGER NOT NULL,
            cheque_number TEXT,
            cheque_date TEXT,
            transaction_date TEXT,
            party_name TEXT,
            amount REAL DEFAULT 0,
            status TEXT DEFAULT 'Pending',
            project_id INTEGER,
            vendor_id INTEGER,
            client_name TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            FOREIGN KEY(bank_account_id) REFERENCES bank_accounts(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for column, col_type in (
        ("pdc_type", "TEXT DEFAULT 'Received'"),
        ("bank_account_id", "INTEGER"),
        ("cheque_number", "TEXT"),
        ("cheque_date", "TEXT"),
        ("transaction_date", "TEXT"),
        ("party_name", "TEXT"),
        ("amount", "REAL DEFAULT 0"),
        ("status", "TEXT DEFAULT 'Pending'"),
        ("project_id", "INTEGER"),
        ("vendor_id", "INTEGER"),
        ("client_name", "TEXT"),
        ("remarks", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "pdc_register", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS fixed_deposits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_account_id INTEGER NOT NULL,
            fd_number TEXT,
            amount REAL DEFAULT 0,
            interest_rate REAL DEFAULT 0,
            start_date TEXT,
            maturity_date TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT,
            FOREIGN KEY(bank_account_id) REFERENCES bank_accounts(id)
        )
    """)
    for column, col_type in (
        ("bank_account_id", "INTEGER"),
        ("fd_number", "TEXT"),
        ("amount", "REAL DEFAULT 0"),
        ("interest_rate", "REAL DEFAULT 0"),
        ("start_date", "TEXT"),
        ("maturity_date", "TEXT"),
        ("status", "TEXT DEFAULT 'Active'"),
        ("accrued_interest", "REAL DEFAULT 0"),
        ("remarks", "TEXT"),
        ("renewed_from_id", "INTEGER"),
        ("last_interest_posted_at", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "fixed_deposits", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS letters_of_credit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lc_number TEXT,
            bank_account_id INTEGER,
            vendor TEXT,
            amount REAL DEFAULT 0,
            issue_date TEXT,
            expiry_date TEXT,
            utilized_amount REAL DEFAULT 0,
            status TEXT DEFAULT 'Active',
            remarks TEXT,
            created_at TEXT,
            FOREIGN KEY(bank_account_id) REFERENCES bank_accounts(id)
        )
    """)
    for column, col_type in (
        ("lc_number", "TEXT"),
        ("bank_account_id", "INTEGER"),
        ("vendor", "TEXT"),
        ("amount", "REAL DEFAULT 0"),
        ("issue_date", "TEXT"),
        ("expiry_date", "TEXT"),
        ("utilized_amount", "REAL DEFAULT 0"),
        ("status", "TEXT"),
        ("remarks", "TEXT"),
        ("created_at", "TEXT"),
    ):
        _ensure_column(db, "letters_of_credit", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS treasury_security_deposits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            bank_account_id INTEGER,
            deposit_type TEXT DEFAULT 'SD',
            amount REAL DEFAULT 0,
            status TEXT DEFAULT 'Active',
            deposit_date TEXT,
            maturity_date TEXT,
            remarks TEXT,
            created_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(bank_account_id) REFERENCES bank_accounts(id)
        )
    """)
    for column, col_type in (
        ("project_id", "INTEGER"),
        ("bank_account_id", "INTEGER"),
        ("deposit_type", "TEXT"),
        ("amount", "REAL DEFAULT 0"),
        ("status", "TEXT"),
        ("deposit_date", "TEXT"),
        ("maturity_date", "TEXT"),
        ("remarks", "TEXT"),
        ("created_at", "TEXT"),
    ):
        _ensure_column(db, "treasury_security_deposits", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS bank_documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            document_type TEXT,
            file_path TEXT NOT NULL,
            original_filename TEXT,
            file_size INTEGER DEFAULT 0,
            uploaded_by TEXT,
            uploaded_at TEXT,
            notes TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    for column, col_type in (
        ("entity_type", "TEXT"),
        ("entity_id", "INTEGER"),
        ("document_type", "TEXT"),
        ("file_path", "TEXT"),
        ("original_filename", "TEXT"),
        ("file_size", "INTEGER DEFAULT 0"),
        ("uploaded_by", "TEXT"),
        ("uploaded_at", "TEXT"),
        ("notes", "TEXT"),
        ("is_active", "INTEGER DEFAULT 1"),
    ):
        _ensure_column(db, "bank_documents", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS payment_approval_matrix(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            min_amount REAL DEFAULT 0,
            max_amount REAL DEFAULT 0,
            approver_role TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)
    for column, col_type in (
        ("min_amount", "REAL DEFAULT 0"),
        ("max_amount", "REAL DEFAULT 0"),
        ("approver_role", "TEXT"),
        ("sort_order", "INTEGER DEFAULT 0"),
        ("is_active", "INTEGER DEFAULT 1"),
    ):
        _ensure_column(db, "payment_approval_matrix", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS treasury_audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT,
            entity_id INTEGER,
            action TEXT,
            actor TEXT,
            details TEXT,
            created_at TEXT
        )
    """)
    for column, col_type in (
        ("entity_type", "TEXT"),
        ("entity_id", "INTEGER"),
        ("action", "TEXT"),
        ("actor", "TEXT"),
        ("details", "TEXT"),
        ("created_at", "TEXT"),
    ):
        _ensure_column(db, "treasury_audit_log", column, col_type)

    _seed_payment_approval_matrix(db)
    _seed_demo_cheques(db)
    _seed_demo_pdc(db)
    _seed_demo_fds(db)
    _seed_demo_bank_documents(db)


def _seed_payment_approval_matrix(db) -> None:
    count = db.execute("SELECT COUNT(*) AS c FROM payment_approval_matrix").fetchone()["c"]
    if count:
        return
    for idx, (lo, hi, role) in enumerate(DEFAULT_PAYMENT_APPROVAL_MATRIX):
        db.execute(
            "INSERT INTO payment_approval_matrix(min_amount, max_amount, approver_role, sort_order) "
            "VALUES(?,?,?,?)",
            (lo, hi, role, idx * 10),
        )


def resolve_payment_approver_role(db, amount: float) -> str:
    row = db.execute(
        "SELECT approver_role FROM payment_approval_matrix "
        "WHERE is_active=1 AND ? >= min_amount AND ? <= max_amount "
        "ORDER BY sort_order, min_amount LIMIT 1",
        (amount, amount),
    ).fetchone()
    if row:
        return row["approver_role"]
    return "Managing Director"


def list_bank_accounts(db, active_only: bool = False) -> list[dict]:
    sql = (
        "SELECT ba.*, COALESCE(bo.utilized, 0) AS od_utilized "
        "FROM bank_accounts ba "
        "LEFT JOIN bank_overdrafts bo ON bo.bank_account_id = ba.id "
    )
    if active_only:
        sql += "WHERE ba.is_active=1 "
    sql += "ORDER BY ba.bank_name, ba.account_number"
    return [dict(r) for r in db.execute(sql).fetchall()]


def get_bank_account(db, account_id: int) -> dict | None:
    row = db.execute(
        "SELECT ba.*, COALESCE(bo.od_limit, ba.od_limit, 0) AS od_limit_live, "
        "COALESCE(bo.utilized, 0) AS od_utilized, COALESCE(bo.interest_rate, ba.interest_rate, 0) AS od_interest "
        "FROM bank_accounts ba "
        "LEFT JOIN bank_overdrafts bo ON bo.bank_account_id = ba.id "
        "WHERE ba.id=?",
        (account_id,),
    ).fetchone()
    return dict(row) if row else None


def save_bank_account(db, form, username: str, account_id: int | None = None) -> int:
    bank_name = (form.get("bank_name") or "").strip()
    account_number = (form.get("account_number") or "").strip()
    if not bank_name or not account_number:
        raise ValueError("Bank name and account number are required.")
    opening = _safe_float(form.get("opening_balance"))
    od_limit = _safe_float(form.get("od_limit"))
    interest_rate = _safe_float(form.get("interest_rate"))
    is_active = 1 if (form.get("is_active") or "1") in ("1", "on", "true", "yes") else 0
    payload = (
        bank_name,
        (form.get("branch") or "").strip(),
        account_number,
        (form.get("ifsc_swift") or "").strip(),
        (form.get("account_type") or "Current").strip(),
        (form.get("currency") or "INR").strip(),
        opening,
        (form.get("authorized_signatory") or "").strip(),
        od_limit,
        interest_rate,
    )
    if account_id:
        db.execute(
            "UPDATE bank_accounts SET bank_name=?, branch=?, account_number=?, ifsc_swift=?, "
            "account_type=?, currency=?, opening_balance=?, authorized_signatory=?, od_limit=?, "
            "interest_rate=?, is_active=?, modified_by=?, modified_at=? WHERE id=?",
            (*payload, is_active, username, _now_ts(), account_id),
        )
        log_treasury_audit(db, "bank_account", account_id, "updated", username)
        _sync_overdraft_row(db, account_id, od_limit, interest_rate)
        return account_id
    current_balance = opening
    cur = db.execute(
        "INSERT INTO bank_accounts("
        "bank_name, branch, account_number, ifsc_swift, account_type, currency, "
        "opening_balance, authorized_signatory, od_limit, interest_rate, current_balance, "
        "is_active, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (*payload, current_balance, is_active, username, _now_ts()),
    )
    new_id = cur.lastrowid
    _sync_overdraft_row(db, new_id, od_limit, interest_rate)
    log_treasury_audit(db, "bank_account", new_id, "created", username)
    return new_id


def _sync_overdraft_row(db, account_id: int, od_limit: float, interest_rate: float) -> None:
    existing = db.execute(
        "SELECT id FROM bank_overdrafts WHERE bank_account_id=?",
        (account_id,),
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE bank_overdrafts SET od_limit=?, interest_rate=?, updated_at=? WHERE bank_account_id=?",
            (od_limit, interest_rate, _now_ts(), account_id),
        )
    elif od_limit > 0:
        db.execute(
            "INSERT INTO bank_overdrafts(bank_account_id, od_limit, utilized, interest_rate, updated_at) "
            "VALUES(?,?,0,?,?)",
            (account_id, od_limit, interest_rate, _now_ts()),
        )


def save_bank_payment(db, form, username: str, record_id: int | None = None) -> int:
    amount = _safe_float(form.get("amount"))
    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")
    bank_account_id = int(form.get("bank_account_id") or 0)
    if not bank_account_id:
        raise ValueError("Select a bank account.")
    approver_tier = resolve_payment_approver_role(db, amount)
    payload = (
        (form.get("payment_date") or datetime.now().strftime("%Y-%m-%d")).strip(),
        bank_account_id,
        (form.get("payment_type") or "Vendor").strip(),
        (form.get("beneficiary") or "").strip(),
        (form.get("utr_number") or "").strip(),
        amount,
        (form.get("remarks") or "").strip(),
        approver_tier,
    )
    if record_id:
        db.execute(
            "UPDATE bank_payments SET payment_date=?, bank_account_id=?, payment_type=?, "
            "beneficiary=?, utr_number=?, amount=?, remarks=?, approver_tier=?, "
            "modified_by=?, modified_at=? WHERE id=?",
            (*payload, username, _now_ts(), record_id),
        )
        log_treasury_audit(db, "bank_payment", record_id, "updated", username)
        return record_id
    cur = db.execute(
        "INSERT INTO bank_payments("
        "payment_date, bank_account_id, payment_type, beneficiary, utr_number, amount, "
        "remarks, approver_tier, status, approval_status, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (*payload, "Pending", "Pending Checker", username, _now_ts()),
    )
    new_id = cur.lastrowid
    log_treasury_audit(
        db, "bank_payment", new_id, "created", username,
        f"Approver tier: {approver_tier}",
    )
    return new_id


def save_bank_receipt(db, form, username: str, record_id: int | None = None) -> int:
    amount = _safe_float(form.get("amount"))
    if amount <= 0:
        raise ValueError("Receipt amount must be greater than zero.")
    bank_account_id = int(form.get("bank_account_id") or 0)
    if not bank_account_id:
        raise ValueError("Select a bank account.")
    payload = (
        (form.get("receipt_date") or datetime.now().strftime("%Y-%m-%d")).strip(),
        bank_account_id,
        (form.get("client") or "").strip(),
        (form.get("utr_number") or "").strip(),
        amount,
        (form.get("receipt_type") or "Client Receipt").strip(),
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        db.execute(
            "UPDATE bank_receipts SET receipt_date=?, bank_account_id=?, client=?, "
            "utr_number=?, amount=?, receipt_type=?, remarks=?, modified_by=?, modified_at=? WHERE id=?",
            (*payload, username, _now_ts(), record_id),
        )
        log_treasury_audit(db, "bank_receipt", record_id, "updated", username)
        return record_id
    cur = db.execute(
        "INSERT INTO bank_receipts("
        "receipt_date, bank_account_id, client, utr_number, amount, receipt_type, "
        "remarks, status, approval_status, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (*payload, "Pending", "Pending Checker", username, _now_ts()),
    )
    new_id = cur.lastrowid
    log_treasury_audit(db, "bank_receipt", new_id, "created", username)
    return new_id


def save_bank_guarantee(db, form, username: str, record_id: int | None = None) -> int:
    amount = _safe_float(form.get("amount"))
    bank_account_id = form.get("bank_account_id")
    bank_account_id = int(bank_account_id) if bank_account_id else None
    project_id = form.get("project_id")
    project_id = int(project_id) if project_id else None
    payload = (
        (form.get("bg_number") or "").strip(),
        bank_account_id,
        (form.get("bg_type") or "Performance BG").strip(),
        project_id,
        (form.get("beneficiary") or "").strip(),
        amount,
        (form.get("issue_date") or "").strip(),
        (form.get("expiry_date") or "").strip(),
        (form.get("status") or "Active").strip(),
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        db.execute(
            "UPDATE bank_guarantees SET bg_number=?, bank_account_id=?, bg_type=?, project_id=?, "
            "beneficiary=?, amount=?, issue_date=?, expiry_date=?, status=?, remarks=?, "
            "modified_by=?, modified_at=? WHERE id=?",
            (*payload, username, _now_ts(), record_id),
        )
        log_treasury_audit(db, "bank_guarantee", record_id, "updated", username)
        return record_id
    cur = db.execute(
        "INSERT INTO bank_guarantees("
        "bg_number, bank_account_id, bg_type, project_id, beneficiary, amount, "
        "issue_date, expiry_date, status, remarks, approval_status, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (*payload, "Pending Checker", username, _now_ts()),
    )
    new_id = cur.lastrowid
    log_treasury_audit(db, "bank_guarantee", new_id, "created", username)
    return new_id


def save_letter_of_credit(db, form, username: str, record_id: int | None = None) -> int:
    bank_account_id = form.get("bank_account_id")
    bank_account_id = int(bank_account_id) if bank_account_id else None
    payload = (
        (form.get("lc_number") or "").strip(),
        bank_account_id,
        (form.get("vendor") or "").strip(),
        _safe_float(form.get("amount")),
        (form.get("issue_date") or "").strip(),
        (form.get("expiry_date") or "").strip(),
        _safe_float(form.get("utilized_amount")),
        (form.get("status") or "Active").strip(),
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        db.execute(
            "UPDATE letters_of_credit SET lc_number=?, bank_account_id=?, vendor=?, amount=?, "
            "issue_date=?, expiry_date=?, utilized_amount=?, status=?, remarks=? WHERE id=?",
            (*payload, record_id),
        )
        return record_id
    cur = db.execute(
        "INSERT INTO letters_of_credit("
        "lc_number, bank_account_id, vendor, amount, issue_date, expiry_date, "
        "utilized_amount, status, remarks, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?)",
        (*payload, _now_ts()),
    )
    return cur.lastrowid


def save_treasury_security_deposit(db, form, username: str, record_id: int | None = None) -> int:
    project_id = form.get("project_id")
    project_id = int(project_id) if project_id else None
    bank_account_id = form.get("bank_account_id")
    bank_account_id = int(bank_account_id) if bank_account_id else None
    payload = (
        project_id,
        bank_account_id,
        (form.get("deposit_type") or "SD").strip(),
        _safe_float(form.get("amount")),
        (form.get("status") or "Active").strip(),
        (form.get("deposit_date") or "").strip(),
        (form.get("maturity_date") or "").strip(),
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        db.execute(
            "UPDATE treasury_security_deposits SET project_id=?, bank_account_id=?, "
            "deposit_type=?, amount=?, status=?, deposit_date=?, maturity_date=?, remarks=? WHERE id=?",
            (*payload, record_id),
        )
        return record_id
    cur = db.execute(
        "INSERT INTO treasury_security_deposits("
        "project_id, bank_account_id, deposit_type, amount, status, deposit_date, "
        "maturity_date, remarks, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?)",
        (*payload, _now_ts()),
    )
    return cur.lastrowid


def list_bank_payments(db, account_id: int | None = None) -> list[dict]:
    sql = (
        "SELECT p.*, ba.bank_name, ba.account_number "
        "FROM bank_payments p "
        "LEFT JOIN bank_accounts ba ON p.bank_account_id = ba.id "
    )
    args: tuple = ()
    if account_id:
        sql += "WHERE p.bank_account_id=? "
        args = (account_id,)
    sql += "ORDER BY p.payment_date DESC, p.id DESC"
    return [dict(r) for r in db.execute(sql, args).fetchall()]


def list_bank_receipts(db, account_id: int | None = None) -> list[dict]:
    sql = (
        "SELECT r.*, ba.bank_name, ba.account_number "
        "FROM bank_receipts r "
        "LEFT JOIN bank_accounts ba ON r.bank_account_id = ba.id "
    )
    args: tuple = ()
    if account_id:
        sql += "WHERE r.bank_account_id=? "
        args = (account_id,)
    sql += "ORDER BY r.receipt_date DESC, r.id DESC"
    return [dict(r) for r in db.execute(sql, args).fetchall()]


def list_bank_guarantees(db, account_id: int | None = None) -> list[dict]:
    sql = (
        "SELECT g.*, ba.bank_name, ba.account_number, p.project_name "
        "FROM bank_guarantees g "
        "LEFT JOIN bank_accounts ba ON g.bank_account_id = ba.id "
        "LEFT JOIN projects p ON g.project_id = p.id "
    )
    args: tuple = ()
    if account_id:
        sql += "WHERE g.bank_account_id=? "
        args = (account_id,)
    sql += "ORDER BY g.expiry_date ASC, g.id DESC"
    return [dict(r) for r in db.execute(sql, args).fetchall()]


def list_letters_of_credit(db) -> list[dict]:
    rows = db.execute(
        "SELECT lc.*, ba.bank_name, ba.account_number "
        "FROM letters_of_credit lc "
        "LEFT JOIN bank_accounts ba ON lc.bank_account_id = ba.id "
        "ORDER BY lc.expiry_date ASC, lc.id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def list_treasury_security_deposits(db) -> list[dict]:
    rows = db.execute(
        "SELECT sd.*, p.project_name, ba.bank_name "
        "FROM treasury_security_deposits sd "
        "LEFT JOIN projects p ON sd.project_id = p.id "
        "LEFT JOIN bank_accounts ba ON sd.bank_account_id = ba.id "
        "ORDER BY sd.id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def list_bank_reconciliation(db, account_id: int | None = None, status: str | None = None) -> list[dict]:
    sql = (
        "SELECT br.*, ba.bank_name, ba.account_number "
        "FROM bank_reconciliation br "
        "LEFT JOIN bank_accounts ba ON br.bank_account_id = ba.id WHERE 1=1 "
    )
    args: list = []
    if account_id:
        sql += "AND br.bank_account_id=? "
        args.append(account_id)
    if status:
        sql += "AND br.status=? "
        args.append(status)
    sql += "ORDER BY br.txn_date DESC, br.id DESC"
    return [dict(r) for r in db.execute(sql, args).fetchall()]


def _cheque_view_sql() -> str:
    return (
        "SELECT c.*, ba.bank_name, ba.account_number "
        "FROM bank_cheques c "
        "LEFT JOIN bank_accounts ba ON c.bank_account_id = ba.id "
    )


def list_cheques(
    db,
    account_id: int | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    sql = _cheque_view_sql() + "WHERE 1=1 "
    args: list = []
    if account_id:
        sql += "AND c.bank_account_id=? "
        args.append(account_id)
    if status:
        sql += "AND c.status=? "
        args.append(status)
    if date_from:
        sql += "AND c.issue_date >= ? "
        args.append(date_from)
    if date_to:
        sql += "AND c.issue_date <= ? "
        args.append(date_to)
    sql += "ORDER BY c.issue_date DESC, c.id DESC"
    return [dict(r) for r in db.execute(sql, args).fetchall()]


def get_cheque(db, cheque_id: int) -> dict | None:
    row = db.execute(_cheque_view_sql() + "WHERE c.id=?", (cheque_id,)).fetchone()
    return dict(row) if row else None


def _validate_cheque_payload(form) -> tuple:
    bank_account_id = int(form.get("bank_account_id") or 0)
    if not bank_account_id:
        raise ValueError("Select a bank account.")
    cheque_number = (form.get("cheque_number") or "").strip()
    if not cheque_number:
        raise ValueError("Cheque number is required.")
    beneficiary = (form.get("beneficiary") or "").strip()
    if not beneficiary:
        raise ValueError("Beneficiary is required.")
    amount = _safe_float(form.get("amount"))
    if amount <= 0:
        raise ValueError("Cheque amount must be greater than zero.")
    issue_date = (form.get("issue_date") or datetime.now().strftime("%Y-%m-%d")).strip()
    return bank_account_id, cheque_number, issue_date, beneficiary, amount


def create_cheque(db, form, username: str) -> int:
    bank_account_id, cheque_number, issue_date, beneficiary, amount = _validate_cheque_payload(form)
    remarks = (form.get("remarks") or "").strip()
    cur = db.execute(
        "INSERT INTO bank_cheques("
        "bank_account_id, cheque_number, issue_date, beneficiary, amount, status, remarks, "
        "created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?)",
        (
            bank_account_id, cheque_number, issue_date, beneficiary, amount,
            "Issued", remarks, username, _now_ts(),
        ),
    )
    new_id = cur.lastrowid
    log_treasury_audit(
        db, "bank_cheque", new_id, "created", username,
        f"Cheque #{cheque_number} for ₹{amount:,.2f} to {beneficiary}",
    )
    return new_id


def update_cheque(db, form, username: str, cheque_id: int) -> int:
    existing = get_cheque(db, cheque_id)
    if not existing:
        raise ValueError("Cheque not found.")
    if existing.get("status") in ("Cleared", "Cancelled", "Bounced"):
        raise ValueError("Cannot edit a cheque in terminal status.")
    bank_account_id, cheque_number, issue_date, beneficiary, amount = _validate_cheque_payload(form)
    remarks = (form.get("remarks") or "").strip()
    db.execute(
        "UPDATE bank_cheques SET bank_account_id=?, cheque_number=?, issue_date=?, "
        "beneficiary=?, amount=?, remarks=?, modified_by=?, modified_at=? WHERE id=?",
        (
            bank_account_id, cheque_number, issue_date, beneficiary, amount, remarks,
            username, _now_ts(), cheque_id,
        ),
    )
    log_treasury_audit(db, "bank_cheque", cheque_id, "updated", username)
    return cheque_id


def allowed_cheque_status_transitions(current_status: str) -> tuple[str, ...]:
    return CHEQUE_STATUS_TRANSITIONS.get(current_status or "Issued", ())


def update_cheque_status(
    db,
    cheque_id: int,
    new_status: str,
    username: str,
    remarks: str = "",
) -> int:
    if new_status not in CHEQUE_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    existing = get_cheque(db, cheque_id)
    if not existing:
        raise ValueError("Cheque not found.")
    current = existing.get("status") or "Issued"
    if new_status == current:
        raise ValueError("Cheque is already in this status.")
    allowed = allowed_cheque_status_transitions(current)
    if new_status not in allowed:
        raise ValueError(f"Cannot change status from {current} to {new_status}.")
    db.execute(
        "UPDATE bank_cheques SET status=?, remarks=?, modified_by=?, modified_at=? WHERE id=?",
        (
            new_status,
            remarks.strip() if remarks else existing.get("remarks") or "",
            username,
            _now_ts(),
            cheque_id,
        ),
    )
    if remarks.strip():
        audit_details = f"{current} → {new_status}: {remarks.strip()}"
    else:
        audit_details = f"{current} → {new_status}"
    log_treasury_audit(
        db, "bank_cheque", cheque_id, "status_changed", username, audit_details,
    )
    return cheque_id


def _seed_demo_cheques(db) -> None:
    if os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        return
    count = db.execute("SELECT COUNT(*) AS c FROM bank_cheques").fetchone()["c"]
    if count > 0:
        return
    accounts = db.execute("SELECT id FROM bank_accounts ORDER BY id LIMIT 2").fetchall()
    if not accounts:
        return
    acct1 = accounts[0]["id"]
    acct2 = accounts[1]["id"] if len(accounts) > 1 else acct1
    today = datetime.now()
    samples = (
        (acct1, "100042", (today - timedelta(days=5)).strftime("%Y-%m-%d"),
         "ABC Steel Suppliers", 75000, "Issued", "Material payment cheque"),
        (acct1, "100043", (today - timedelta(days=12)).strftime("%Y-%m-%d"),
         "Velu Contractors", 125000, "Deposited", "RA bill — deposited at bank"),
        (acct2, "200018", (today - timedelta(days=30)).strftime("%Y-%m-%d"),
         "NHAI Regional Office", 50000, "Cleared", "Refund cheque cleared"),
    )
    for bank_account_id, cheque_number, issue_date, beneficiary, amount, status, remarks in samples:
        db.execute(
            "INSERT INTO bank_cheques("
            "bank_account_id, cheque_number, issue_date, beneficiary, amount, status, remarks, "
            "created_by, created_at"
            ") VALUES(?,?,?,?,?,?,?,?,?)",
            (
                bank_account_id, cheque_number, issue_date, beneficiary, amount,
                status, remarks, "demo", _now_ts(),
            ),
        )


def _pdc_view_sql() -> str:
    return (
        "SELECT p.*, ba.bank_name, ba.account_number, "
        "pr.project_name, v.name AS vendor_name, v.code AS vendor_code "
        "FROM pdc_register p "
        "LEFT JOIN bank_accounts ba ON p.bank_account_id = ba.id "
        "LEFT JOIN projects pr ON p.project_id = pr.id "
        "LEFT JOIN vendors v ON p.vendor_id = v.id "
    )


def list_pdc(
    db,
    pdc_type: str | None = None,
    account_id: int | None = None,
    status: str | None = None,
    due_soon: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    sql = _pdc_view_sql() + "WHERE 1=1 "
    args: list = []
    if pdc_type:
        sql += "AND p.pdc_type=? "
        args.append(pdc_type)
    if account_id:
        sql += "AND p.bank_account_id=? "
        args.append(account_id)
    if status:
        sql += "AND p.status=? "
        args.append(status)
    if due_soon:
        today = datetime.now().date()
        horizon = (today + timedelta(days=PDC_DUE_ALERT_DAYS[0])).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")
        placeholders = ",".join("?" for _ in PDC_ACTIVE_STATUSES)
        sql += (
            f"AND p.status IN ({placeholders}) "
            "AND p.cheque_date IS NOT NULL AND p.cheque_date >= ? AND p.cheque_date <= ? "
        )
        args.extend(PDC_ACTIVE_STATUSES)
        args.extend([today_str, horizon])
    if date_from:
        sql += "AND p.cheque_date >= ? "
        args.append(date_from)
    if date_to:
        sql += "AND p.cheque_date <= ? "
        args.append(date_to)
    sql += "ORDER BY p.cheque_date ASC, p.id DESC"
    return [dict(r) for r in db.execute(sql, args).fetchall()]


def get_pdc(db, pdc_id: int) -> dict | None:
    row = db.execute(_pdc_view_sql() + "WHERE p.id=?", (pdc_id,)).fetchone()
    return dict(row) if row else None


def _parse_optional_int(value) -> int | None:
    raw = (value or "").strip() if value is not None else ""
    if not raw:
        return None
    return int(raw)


def _validate_pdc_payload(form) -> tuple:
    pdc_type = (form.get("pdc_type") or "").strip()
    if pdc_type not in PDC_TYPES:
        raise ValueError("Select PDC type (Received or Issued).")
    bank_account_id = int(form.get("bank_account_id") or 0)
    if not bank_account_id:
        raise ValueError("Select a bank account.")
    cheque_number = (form.get("cheque_number") or "").strip()
    if not cheque_number:
        raise ValueError("Cheque number is required.")
    party_name = (form.get("party_name") or "").strip()
    if not party_name:
        raise ValueError("Party / beneficiary name is required.")
    amount = _safe_float(form.get("amount"))
    if amount <= 0:
        raise ValueError("PDC amount must be greater than zero.")
    cheque_date = (form.get("cheque_date") or "").strip()
    if not cheque_date:
        raise ValueError("Cheque date (maturity) is required.")
    transaction_date = (
        form.get("transaction_date") or datetime.now().strftime("%Y-%m-%d")
    ).strip()
    project_id = _parse_optional_int(form.get("project_id"))
    vendor_id = _parse_optional_int(form.get("vendor_id"))
    client_name = (form.get("client_name") or "").strip() or None
    return (
        pdc_type, bank_account_id, cheque_number, cheque_date, transaction_date,
        party_name, amount, project_id, vendor_id, client_name,
    )


def create_pdc(db, form, username: str) -> int:
    (
        pdc_type, bank_account_id, cheque_number, cheque_date, transaction_date,
        party_name, amount, project_id, vendor_id, client_name,
    ) = _validate_pdc_payload(form)
    remarks = (form.get("remarks") or "").strip()
    cur = db.execute(
        "INSERT INTO pdc_register("
        "pdc_type, bank_account_id, cheque_number, cheque_date, transaction_date, "
        "party_name, amount, status, project_id, vendor_id, client_name, remarks, "
        "created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            pdc_type, bank_account_id, cheque_number, cheque_date, transaction_date,
            party_name, amount, "Pending", project_id, vendor_id, client_name, remarks,
            username, _now_ts(),
        ),
    )
    new_id = cur.lastrowid
    log_treasury_audit(
        db, "pdc_register", new_id, "created", username,
        f"{pdc_type} PDC #{cheque_number} for ₹{amount:,.2f} — {party_name} (due {cheque_date})",
    )
    return new_id


def update_pdc(db, form, username: str, pdc_id: int) -> int:
    existing = get_pdc(db, pdc_id)
    if not existing:
        raise ValueError("PDC not found.")
    if existing.get("status") in ("Cleared", "Cancelled", "Bounced"):
        raise ValueError("Cannot edit a PDC in terminal status.")
    (
        pdc_type, bank_account_id, cheque_number, cheque_date, transaction_date,
        party_name, amount, project_id, vendor_id, client_name,
    ) = _validate_pdc_payload(form)
    remarks = (form.get("remarks") or "").strip()
    db.execute(
        "UPDATE pdc_register SET pdc_type=?, bank_account_id=?, cheque_number=?, "
        "cheque_date=?, transaction_date=?, party_name=?, amount=?, project_id=?, "
        "vendor_id=?, client_name=?, remarks=?, modified_by=?, modified_at=? WHERE id=?",
        (
            pdc_type, bank_account_id, cheque_number, cheque_date, transaction_date,
            party_name, amount, project_id, vendor_id, client_name, remarks,
            username, _now_ts(), pdc_id,
        ),
    )
    log_treasury_audit(db, "pdc_register", pdc_id, "updated", username)
    return pdc_id


def allowed_pdc_status_transitions(current_status: str) -> tuple[str, ...]:
    return PDC_STATUS_TRANSITIONS.get(current_status or "Pending", ())


def update_pdc_status(
    db,
    pdc_id: int,
    new_status: str,
    username: str,
    remarks: str = "",
) -> int:
    if new_status not in PDC_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    existing = get_pdc(db, pdc_id)
    if not existing:
        raise ValueError("PDC not found.")
    current = existing.get("status") or "Pending"
    if new_status == current:
        raise ValueError("PDC is already in this status.")
    allowed = allowed_pdc_status_transitions(current)
    if new_status not in allowed:
        raise ValueError(f"Cannot change status from {current} to {new_status}.")
    db.execute(
        "UPDATE pdc_register SET status=?, remarks=?, modified_by=?, modified_at=? WHERE id=?",
        (
            new_status,
            remarks.strip() if remarks else existing.get("remarks") or "",
            username,
            _now_ts(),
            pdc_id,
        ),
    )
    if remarks.strip():
        audit_details = f"{current} → {new_status}: {remarks.strip()}"
    else:
        audit_details = f"{current} → {new_status}"
    log_treasury_audit(
        db, "pdc_register", pdc_id, "status_changed", username, audit_details,
    )
    return pdc_id


def upcoming_pdc_due_alerts(db) -> list[dict]:
    today = datetime.now().date()
    alerts = []
    rows = list_pdc(db)
    for row in rows:
        if row.get("status") not in PDC_ACTIVE_STATUSES:
            continue
        cheque_raw = row.get("cheque_date")
        if not cheque_raw:
            continue
        try:
            due = datetime.strptime(str(cheque_raw)[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        days_left = (due - today).days
        if days_left < 0:
            continue
        for threshold in PDC_DUE_ALERT_DAYS:
            if days_left <= threshold:
                alerts.append({**row, "days_left": days_left, "alert_threshold": threshold})
                break
    alerts.sort(key=lambda x: x.get("days_left", 999))
    return alerts


def _seed_demo_pdc(db) -> None:
    if os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        return
    count = db.execute("SELECT COUNT(*) AS c FROM pdc_register").fetchone()["c"]
    if count > 0:
        return
    accounts = db.execute("SELECT id FROM bank_accounts ORDER BY id LIMIT 2").fetchall()
    if not accounts:
        return
    acct1 = accounts[0]["id"]
    acct2 = accounts[1]["id"] if len(accounts) > 1 else acct1
    project = db.execute("SELECT id FROM projects ORDER BY id LIMIT 1").fetchone()
    project_id = project["id"] if project else None
    vendor = db.execute("SELECT id FROM vendors ORDER BY id LIMIT 1").fetchone()
    vendor_id = vendor["id"] if vendor else None
    today = datetime.now()
    samples = (
        (
            "Received", acct1, "PDC-8801",
            (today + timedelta(days=5)).strftime("%Y-%m-%d"),
            (today - timedelta(days=10)).strftime("%Y-%m-%d"),
            "NHAI Regional Office", 350000, "Pending",
            project_id, None, "NHAI Regional Office",
            "Client PDC — RA bill collection, due soon",
        ),
        (
            "Received", acct1, "PDC-8802",
            (today + timedelta(days=45)).strftime("%Y-%m-%d"),
            (today - timedelta(days=3)).strftime("%Y-%m-%d"),
            "State Highway Authority", 180000, "Pending",
            project_id, None, "State Highway Authority",
            "Second instalment PDC from client",
        ),
        (
            "Issued", acct2, "PDC-5501",
            (today + timedelta(days=20)).strftime("%Y-%m-%d"),
            today.strftime("%Y-%m-%d"),
            "ABC Steel Suppliers", 95000, "Pending",
            project_id, vendor_id, None,
            "Vendor PDC for steel supply",
        ),
    )
    for (
        pdc_type, bank_account_id, cheque_number, cheque_date, transaction_date,
        party_name, amount, status, proj_id, vend_id, client_name, remarks,
    ) in samples:
        db.execute(
            "INSERT INTO pdc_register("
            "pdc_type, bank_account_id, cheque_number, cheque_date, transaction_date, "
            "party_name, amount, status, project_id, vendor_id, client_name, remarks, "
            "created_by, created_at"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                pdc_type, bank_account_id, cheque_number, cheque_date, transaction_date,
                party_name, amount, status, proj_id, vend_id, client_name, remarks,
                "demo", _now_ts(),
            ),
        )


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def calculate_interest(
    amount: float,
    interest_rate: float,
    start_date: str | None,
    as_of: str | None = None,
    maturity_date: str | None = None,
) -> float:
    """Simple interest stub: I = P × R × T / 100 (T in years)."""
    principal = _safe_float(amount)
    rate = _safe_float(interest_rate)
    if principal <= 0 or rate <= 0:
        return 0.0
    start = _parse_date(start_date)
    if not start:
        return 0.0
    end = _parse_date(as_of) or datetime.now().date()
    maturity = _parse_date(maturity_date)
    if maturity and end > maturity:
        end = maturity
    if end <= start:
        return 0.0
    days = (end - start).days
    years = days / 365.0
    return round(principal * rate * years / 100.0, 2)


def _fd_view_sql() -> str:
    return (
        "SELECT fd.*, ba.bank_name, ba.account_number "
        "FROM fixed_deposits fd "
        "LEFT JOIN bank_accounts ba ON fd.bank_account_id = ba.id "
    )


def _enrich_fd_row(row: dict, as_of: str | None = None) -> dict:
    enriched = dict(row)
    accrued = calculate_interest(
        enriched.get("amount"),
        enriched.get("interest_rate"),
        enriched.get("start_date"),
        as_of,
        enriched.get("maturity_date"),
    )
    enriched["accrued_interest_calc"] = accrued
    maturity = _parse_date(enriched.get("maturity_date"))
    if maturity:
        enriched["days_to_maturity"] = (maturity - datetime.now().date()).days
    else:
        enriched["days_to_maturity"] = None
    return enriched


def list_fds(
    db,
    account_id: int | None = None,
    status: str | None = None,
    maturing_soon: bool = False,
) -> list[dict]:
    sql = _fd_view_sql() + "WHERE 1=1 "
    args: list = []
    if account_id:
        sql += "AND fd.bank_account_id=? "
        args.append(account_id)
    if status:
        sql += "AND fd.status=? "
        args.append(status)
    if maturing_soon:
        today = datetime.now().date()
        horizon = (today + timedelta(days=FD_MATURITY_ALERT_DAYS[0])).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")
        placeholders = ",".join("?" for _ in FD_ACTIVE_STATUSES)
        sql += (
            f"AND fd.status IN ({placeholders}) "
            "AND fd.maturity_date IS NOT NULL AND fd.maturity_date >= ? AND fd.maturity_date <= ? "
        )
        args.extend(FD_ACTIVE_STATUSES)
        args.extend([today_str, horizon])
    sql += "ORDER BY fd.maturity_date ASC, fd.id DESC"
    return [_enrich_fd_row(dict(r)) for r in db.execute(sql, args).fetchall()]


def get_fd(db, fd_id: int) -> dict | None:
    row = db.execute(_fd_view_sql() + "WHERE fd.id=?", (fd_id,)).fetchone()
    return _enrich_fd_row(dict(row)) if row else None


def _validate_fd_payload(form) -> tuple:
    bank_account_id = int(form.get("bank_account_id") or 0)
    if not bank_account_id:
        raise ValueError("Select a bank account.")
    fd_number = (form.get("fd_number") or "").strip()
    if not fd_number:
        raise ValueError("FD number is required.")
    amount = _safe_float(form.get("amount"))
    if amount <= 0:
        raise ValueError("FD amount must be greater than zero.")
    interest_rate = _safe_float(form.get("interest_rate"))
    if interest_rate < 0:
        raise ValueError("Interest rate cannot be negative.")
    start_date = (form.get("start_date") or "").strip()
    maturity_date = (form.get("maturity_date") or "").strip()
    if not start_date:
        raise ValueError("Start date is required.")
    if not maturity_date:
        raise ValueError("Maturity date is required.")
    start = _parse_date(start_date)
    maturity = _parse_date(maturity_date)
    if not start or not maturity:
        raise ValueError("Invalid date format.")
    if maturity <= start:
        raise ValueError("Maturity date must be after start date.")
    return bank_account_id, fd_number, amount, interest_rate, start_date, maturity_date


def create_fd(db, form, username: str) -> int:
    (
        bank_account_id, fd_number, amount, interest_rate, start_date, maturity_date,
    ) = _validate_fd_payload(form)
    remarks = (form.get("remarks") or "").strip()
    accrued = calculate_interest(amount, interest_rate, start_date, maturity_date=maturity_date)
    cur = db.execute(
        "INSERT INTO fixed_deposits("
        "bank_account_id, fd_number, amount, interest_rate, start_date, maturity_date, "
        "status, accrued_interest, remarks, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            bank_account_id, fd_number, amount, interest_rate, start_date, maturity_date,
            "Active", accrued, remarks, username, _now_ts(),
        ),
    )
    new_id = cur.lastrowid
    log_treasury_audit(
        db, "fixed_deposit", new_id, "created", username,
        f"FD #{fd_number} ₹{amount:,.2f} @ {interest_rate}% — matures {maturity_date}",
    )
    return new_id


def update_fd(db, form, username: str, fd_id: int) -> int:
    existing = get_fd(db, fd_id)
    if not existing:
        raise ValueError("Fixed deposit not found.")
    if existing.get("status") not in FD_ACTIVE_STATUSES:
        raise ValueError("Cannot edit a fixed deposit that is not Active.")
    (
        bank_account_id, fd_number, amount, interest_rate, start_date, maturity_date,
    ) = _validate_fd_payload(form)
    remarks = (form.get("remarks") or "").strip()
    accrued = calculate_interest(amount, interest_rate, start_date, maturity_date=maturity_date)
    db.execute(
        "UPDATE fixed_deposits SET bank_account_id=?, fd_number=?, amount=?, interest_rate=?, "
        "start_date=?, maturity_date=?, accrued_interest=?, remarks=?, "
        "modified_by=?, modified_at=? WHERE id=?",
        (
            bank_account_id, fd_number, amount, interest_rate, start_date, maturity_date,
            accrued, remarks, username, _now_ts(), fd_id,
        ),
    )
    log_treasury_audit(db, "fixed_deposit", fd_id, "updated", username)
    return fd_id


def close_fd(db, fd_id: int, username: str, remarks: str = "") -> int:
    existing = get_fd(db, fd_id)
    if not existing:
        raise ValueError("Fixed deposit not found.")
    if existing.get("status") == "Closed":
        raise ValueError("Fixed deposit is already closed.")
    if existing.get("status") == "Renewed":
        raise ValueError("This FD was renewed — close the renewed FD instead.")
    accrued = existing.get("accrued_interest_calc") or calculate_interest(
        existing.get("amount"), existing.get("interest_rate"),
        existing.get("start_date"), maturity_date=existing.get("maturity_date"),
    )
    note = remarks.strip() if remarks else existing.get("remarks") or ""
    db.execute(
        "UPDATE fixed_deposits SET status='Closed', accrued_interest=?, remarks=?, "
        "modified_by=?, modified_at=? WHERE id=?",
        (accrued, note, username, _now_ts(), fd_id),
    )
    post_fd_interest_to_accounts(db, fd_id, accrued, username, action="close")
    log_treasury_audit(
        db, "fixed_deposit", fd_id, "closed", username,
        f"Closed — accrued interest ₹{accrued:,.2f}",
    )
    return fd_id


def renew_fd(db, fd_id: int, form, username: str) -> int:
    existing = get_fd(db, fd_id)
    if not existing:
        raise ValueError("Fixed deposit not found.")
    if existing.get("status") != "Active":
        raise ValueError("Only active fixed deposits can be renewed.")
    (
        bank_account_id, fd_number, amount, interest_rate, start_date, maturity_date,
    ) = _validate_fd_payload(form)
    remarks = (form.get("remarks") or "").strip()
    accrued = existing.get("accrued_interest_calc") or calculate_interest(
        existing.get("amount"), existing.get("interest_rate"),
        existing.get("start_date"), maturity_date=existing.get("maturity_date"),
    )
    db.execute(
        "UPDATE fixed_deposits SET status='Renewed', accrued_interest=?, "
        "modified_by=?, modified_at=? WHERE id=?",
        (accrued, username, _now_ts(), fd_id),
    )
    post_fd_interest_to_accounts(db, fd_id, accrued, username, action="renew")
    log_treasury_audit(
        db, "fixed_deposit", fd_id, "renewed", username,
        f"Renewed into FD #{fd_number}",
    )
    new_accrued = calculate_interest(amount, interest_rate, start_date, maturity_date=maturity_date)
    cur = db.execute(
        "INSERT INTO fixed_deposits("
        "bank_account_id, fd_number, amount, interest_rate, start_date, maturity_date, "
        "status, accrued_interest, remarks, renewed_from_id, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            bank_account_id, fd_number, amount, interest_rate, start_date, maturity_date,
            "Active", new_accrued, remarks, fd_id, username, _now_ts(),
        ),
    )
    new_id = cur.lastrowid
    log_treasury_audit(
        db, "fixed_deposit", new_id, "created", username,
        f"Renewed from FD #{existing.get('fd_number')} — #{fd_number} ₹{amount:,.2f}",
    )
    return new_id


def upcoming_maturity_alerts(db) -> list[dict]:
    today = datetime.now().date()
    alerts = []
    for row in list_fds(db):
        if row.get("status") not in FD_ACTIVE_STATUSES:
            continue
        maturity_raw = row.get("maturity_date")
        if not maturity_raw:
            continue
        maturity = _parse_date(maturity_raw)
        if not maturity:
            continue
        days_left = (maturity - today).days
        if days_left < 0:
            continue
        for threshold in FD_MATURITY_ALERT_DAYS:
            if days_left <= threshold:
                alerts.append({**row, "days_left": days_left, "alert_threshold": threshold})
                break
    alerts.sort(key=lambda x: x.get("days_left", 999))
    return alerts


def post_fd_interest_to_accounts(
    db,
    fd_id: int,
    interest_amount: float,
    actor: str = "system",
    action: str = "accrual",
) -> None:
    """Stub GL hook — logs audit entry; full journal posting is Phase 2+."""
    db.execute(
        "UPDATE fixed_deposits SET last_interest_posted_at=? WHERE id=?",
        (_now_ts(), fd_id),
    )
    log_treasury_audit(
        db, "fixed_deposit", fd_id, "interest_posted_stub", actor,
        f"{action}: ₹{interest_amount:,.2f} interest (GL posting stub — not yet wired to accounts)",
    )


def _seed_demo_fds(db) -> None:
    if os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        return
    count = db.execute("SELECT COUNT(*) AS c FROM fixed_deposits").fetchone()["c"]
    if count > 0:
        return
    accounts = db.execute("SELECT id, bank_name FROM bank_accounts ORDER BY id LIMIT 2").fetchall()
    if not accounts:
        return
    acct1 = accounts[0]["id"]
    acct2 = accounts[1]["id"] if len(accounts) > 1 else acct1
    today = datetime.now()
    samples = (
        (
            acct1, "FD-2026-0142", 1500000, 7.25,
            (today - timedelta(days=335)).strftime("%Y-%m-%d"),
            (today + timedelta(days=22)).strftime("%Y-%m-%d"),
            "Active", "Corporate FD — maturing within 30 days (demo alert)",
        ),
        (
            acct2, "FD-2025-0088", 800000, 6.75,
            (today - timedelta(days=120)).strftime("%Y-%m-%d"),
            (today + timedelta(days=245)).strftime("%Y-%m-%d"),
            "Active", "Short-term surplus parking FD",
        ),
    )
    for bank_account_id, fd_number, amount, rate, start_date, maturity_date, status, remarks in samples:
        accrued = calculate_interest(amount, rate, start_date, maturity_date=maturity_date)
        db.execute(
            "INSERT INTO fixed_deposits("
            "bank_account_id, fd_number, amount, interest_rate, start_date, maturity_date, "
            "status, accrued_interest, remarks, created_by, created_at"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                bank_account_id, fd_number, amount, rate, start_date, maturity_date,
                status, accrued, remarks, "demo", _now_ts(),
            ),
        )


def list_overdrafts(db) -> list[dict]:
    rows = db.execute(
        "SELECT bo.*, ba.bank_name, ba.account_number, ba.current_balance "
        "FROM bank_overdrafts bo "
        "JOIN bank_accounts ba ON bo.bank_account_id = ba.id "
        "ORDER BY ba.bank_name"
    ).fetchall()
    return [dict(r) for r in rows]


def bg_expiry_alerts(db) -> list[dict]:
    today = datetime.now().date()
    alerts = []
    rows = list_bank_guarantees(db)
    for row in rows:
        expiry_raw = row.get("expiry_date")
        if not expiry_raw or row.get("status") not in ("Active", "Expiring Soon"):
            continue
        try:
            expiry = datetime.strptime(str(expiry_raw)[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        days_left = (expiry - today).days
        if days_left < 0:
            continue
        for threshold in BG_EXPIRY_ALERT_DAYS:
            if days_left <= threshold:
                alerts.append({**row, "days_left": days_left, "alert_threshold": threshold})
                break
    alerts.sort(key=lambda x: x.get("days_left", 999))
    return alerts


def treasury_hub_stats(db) -> dict:
    accounts = db.execute("SELECT COUNT(*) AS c FROM bank_accounts WHERE is_active=1").fetchone()["c"]
    balance_row = db.execute(
        "SELECT COALESCE(SUM(current_balance), 0) AS total FROM bank_accounts WHERE is_active=1"
    ).fetchone()
    pending_payments = db.execute(
        "SELECT COUNT(*) AS c FROM bank_payments WHERE approval_status != 'Approved'"
    ).fetchone()["c"]
    pending_receipts = db.execute(
        "SELECT COUNT(*) AS c FROM bank_receipts WHERE approval_status != 'Approved'"
    ).fetchone()["c"]
    bg_exposure = db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM bank_guarantees WHERE status='Active'"
    ).fetchone()["total"]
    od_utilized = db.execute(
        "SELECT COALESCE(SUM(utilized), 0) AS total FROM bank_overdrafts"
    ).fetchone()["total"]
    unmatched = db.execute(
        "SELECT COUNT(*) AS c FROM bank_reconciliation WHERE status='unmatched'"
    ).fetchone()["c"]
    return {
        "active_accounts": accounts,
        "total_balance": round(_safe_float(balance_row["total"]), 2),
        "pending_payments": pending_payments,
        "pending_receipts": pending_receipts,
        "bg_exposure": round(_safe_float(bg_exposure), 2),
        "od_utilized": round(_safe_float(od_utilized), 2),
        "unmatched_recon": unmatched,
        "bg_alerts": len(bg_expiry_alerts(db)),
        "pdc_due_alerts": len(upcoming_pdc_due_alerts(db)),
        "fd_maturity_alerts": len(upcoming_maturity_alerts(db)),
        "active_fd_amount": round(
            _safe_float(
                db.execute(
                    "SELECT COALESCE(SUM(amount), 0) AS total FROM fixed_deposits WHERE status='Active'"
                ).fetchone()["total"]
            ),
            2,
        ),
    }


def account_dashboard_stats(db, account_id: int) -> dict:
    acct = get_bank_account(db, account_id)
    if not acct:
        return {}
    pending_pay = db.execute(
        "SELECT COUNT(*) AS c, COALESCE(SUM(amount), 0) AS total "
        "FROM bank_payments WHERE bank_account_id=? AND approval_status != 'Approved'",
        (account_id,),
    ).fetchone()
    pending_rec = db.execute(
        "SELECT COUNT(*) AS c, COALESCE(SUM(amount), 0) AS total "
        "FROM bank_receipts WHERE bank_account_id=? AND approval_status != 'Approved'",
        (account_id,),
    ).fetchone()
    bg_row = db.execute(
        "SELECT COUNT(*) AS c, COALESCE(SUM(amount), 0) AS total "
        "FROM bank_guarantees WHERE bank_account_id=? AND status='Active'",
        (account_id,),
    ).fetchone()
    return {
        "account": acct,
        "pending_payment_count": pending_pay["c"],
        "pending_payment_amount": round(_safe_float(pending_pay["total"]), 2),
        "pending_receipt_count": pending_rec["c"],
        "pending_receipt_amount": round(_safe_float(pending_rec["total"]), 2),
        "bg_count": bg_row["c"],
        "bg_exposure": round(_safe_float(bg_row["total"]), 2),
    }


def account_360_data(db, account_id: int) -> dict:
    return {
        "account": get_bank_account(db, account_id),
        "payments": list_bank_payments(db, account_id),
        "receipts": list_bank_receipts(db, account_id),
        "guarantees": list_bank_guarantees(db, account_id),
        "reconciliation": list_bank_reconciliation(db, account_id),
        "cheques": [
            dict(r) for r in db.execute(
                "SELECT * FROM bank_cheques WHERE bank_account_id=? ORDER BY issue_date DESC",
                (account_id,),
            ).fetchall()
        ],
        "fixed_deposits": list_fds(db, account_id),
        "letters_of_credit": [
            dict(r) for r in db.execute(
                "SELECT * FROM letters_of_credit WHERE bank_account_id=? ORDER BY expiry_date",
                (account_id,),
            ).fetchall()
        ],
        "audit": [
            dict(r) for r in db.execute(
                "SELECT * FROM treasury_audit_log WHERE entity_type='bank_account' AND entity_id=? "
                "ORDER BY created_at DESC LIMIT 20",
                (account_id,),
            ).fetchall()
        ],
    }


def get_bank_book_rows(db, account_id: int | None = None) -> list[dict]:
    rows = []
    pay_sql = (
        "SELECT p.id, p.payment_date AS txn_date, 'Payment' AS txn_type, p.beneficiary AS party, "
        "p.amount, p.utr_number, p.approval_status, ba.bank_name, ba.account_number "
        "FROM bank_payments p JOIN bank_accounts ba ON p.bank_account_id = ba.id "
        "WHERE p.approval_status='Approved' "
    )
    rec_sql = (
        "SELECT r.id, r.receipt_date AS txn_date, 'Receipt' AS txn_type, r.client AS party, "
        "r.amount, r.utr_number, r.approval_status, ba.bank_name, ba.account_number "
        "FROM bank_receipts r JOIN bank_accounts ba ON r.bank_account_id = ba.id "
        "WHERE r.approval_status='Approved' "
    )
    args: tuple = ()
    if account_id:
        pay_sql += "AND p.bank_account_id=? "
        rec_sql += "AND r.bank_account_id=? "
        args = (account_id,)
    for row in db.execute(pay_sql + "ORDER BY p.payment_date", args).fetchall():
        d = dict(row)
        d["debit"] = 0
        d["credit"] = d["amount"]
        rows.append(d)
    for row in db.execute(rec_sql + "ORDER BY r.receipt_date", args).fetchall():
        d = dict(row)
        d["debit"] = d["amount"]
        d["credit"] = 0
        rows.append(d)
    rows.sort(key=lambda x: (x.get("txn_date") or "", x.get("id", 0)))
    balance = 0.0
    for row in rows:
        balance += _safe_float(row.get("debit")) - _safe_float(row.get("credit"))
        row["balance"] = round(balance, 2)
    return rows


def get_od_register_rows(db) -> list[dict]:
    return list_overdrafts(db)


def get_bg_register_rows(db) -> list[dict]:
    return list_bank_guarantees(db)


def get_treasury_cash_flow_summary(db) -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    inflows = db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM bank_receipts "
        "WHERE approval_status='Approved' AND receipt_date >= ?",
        (month_start,),
    ).fetchone()["total"]
    outflows = db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM bank_payments "
        "WHERE approval_status='Approved' AND payment_date >= ?",
        (month_start,),
    ).fetchone()["total"]
    return {
        "month_start": month_start,
        "today": today,
        "inflows_mtd": round(_safe_float(inflows), 2),
        "outflows_mtd": round(_safe_float(outflows), 2),
        "net_mtd": round(_safe_float(inflows) - _safe_float(outflows), 2),
        "total_balance": treasury_hub_stats(db)["total_balance"],
    }


CASH_FLOW_FORECAST_PERIODS = {
    "7": {"label": "7 Days", "days": 7},
    "30": {"label": "30 Days", "days": 30},
    "90": {"label": "90 Days", "days": 90},
    "project": {"label": "Project Completion", "days": None},
}


def _forecast_item(
    *,
    flow_type: str,
    category: str,
    source: str,
    source_id: int,
    expected_date: str | None,
    amount: float,
    party: str = "",
    status: str = "",
    approval_status: str = "",
    project_id: int | None = None,
    project_name: str | None = None,
    remarks: str = "",
) -> dict:
    return {
        "flow_type": flow_type,
        "category": category,
        "source": source,
        "source_id": source_id,
        "expected_date": (expected_date or "")[:10] if expected_date else "",
        "amount": round(_safe_float(amount), 2),
        "party": party or "—",
        "status": status or "—",
        "approval_status": approval_status or "—",
        "project_id": project_id,
        "project_name": project_name or "",
        "remarks": remarks or "",
    }


def _collect_cash_flow_forecast_items(db) -> list[dict]:
    """Pending / scheduled treasury flows not yet cleared in bank."""
    items: list[dict] = []

    receipt_rows = db.execute(
        "SELECT id, receipt_date, client, amount, status, approval_status, remarks "
        "FROM bank_receipts "
        "WHERE approval_status != 'Approved' OR status != 'Cleared'"
    ).fetchall()
    for row in receipt_rows:
        items.append(
            _forecast_item(
                flow_type="inflow",
                category="Expected Receipt",
                source="bank_receipt",
                source_id=row["id"],
                expected_date=row["receipt_date"],
                amount=row["amount"],
                party=row["client"],
                status=row["status"],
                approval_status=row["approval_status"],
                remarks=row["remarks"],
            )
        )

    payment_rows = db.execute(
        "SELECT id, payment_date, beneficiary, amount, status, approval_status, remarks "
        "FROM bank_payments "
        "WHERE approval_status != 'Approved' OR status != 'Processed'"
    ).fetchall()
    for row in payment_rows:
        items.append(
            _forecast_item(
                flow_type="outflow",
                category="Expected Payment",
                source="bank_payment",
                source_id=row["id"],
                expected_date=row["payment_date"],
                amount=row["amount"],
                party=row["beneficiary"],
                status=row["status"],
                approval_status=row["approval_status"],
                remarks=row["remarks"],
            )
        )

    if _table_exists(db, "pdc_register"):
        pdc_rows = db.execute(
            "SELECT p.id, p.pdc_type, p.cheque_date, p.party_name, p.amount, p.status, "
            "p.project_id, p.remarks, pr.project_name "
            "FROM pdc_register p "
            "LEFT JOIN projects pr ON p.project_id = pr.id "
            "WHERE p.status IN ('Pending', 'Deposited')"
        ).fetchall()
        for row in pdc_rows:
            flow_type = "inflow" if (row["pdc_type"] or "Received") == "Received" else "outflow"
            category = "PDC Receipt" if flow_type == "inflow" else "PDC Payment"
            items.append(
                _forecast_item(
                    flow_type=flow_type,
                    category=category,
                    source="pdc_register",
                    source_id=row["id"],
                    expected_date=row["cheque_date"],
                    amount=row["amount"],
                    party=row["party_name"],
                    status=row["status"],
                    project_id=row["project_id"],
                    project_name=row["project_name"],
                    remarks=row["remarks"],
                )
            )

    if _table_exists(db, "fixed_deposits"):
        fd_rows = db.execute(
            "SELECT fd.id, fd.fd_number, fd.amount, fd.interest_rate, fd.start_date, "
            "fd.maturity_date, fd.status, fd.remarks, ba.bank_name "
            "FROM fixed_deposits fd "
            "LEFT JOIN bank_accounts ba ON fd.bank_account_id = ba.id "
            "WHERE fd.status = 'Active' AND fd.maturity_date IS NOT NULL AND fd.maturity_date != ''"
        ).fetchall()
        for row in fd_rows:
            accrued = calculate_interest(
                row["amount"],
                row["interest_rate"],
                row["start_date"],
                as_of=row["maturity_date"],
                maturity_date=row["maturity_date"],
            )
            maturity_amount = round(_safe_float(row["amount"]) + accrued, 2)
            items.append(
                _forecast_item(
                    flow_type="inflow",
                    category="FD Maturity",
                    source="fixed_deposit",
                    source_id=row["id"],
                    expected_date=row["maturity_date"],
                    amount=maturity_amount,
                    party=row["bank_name"] or row["fd_number"],
                    status=row["status"],
                    remarks=row["remarks"] or f"Principal + accrued interest ({row['fd_number']})",
                )
            )

    if _table_exists(db, "projects"):
        project_rows = db.execute(
            "SELECT id, project_name, end_date, approved_total_amount, budget, status "
            "FROM projects "
            "WHERE status = 'Active' AND end_date IS NOT NULL AND end_date != ''"
        ).fetchall()
        for row in project_rows:
            contract_value = _safe_float(row["approved_total_amount"]) or _safe_float(row["budget"])
            if contract_value <= 0:
                continue
            received = 0.0
            if _table_exists(db, "bank_receipts"):
                rec = db.execute(
                    "SELECT COALESCE(SUM(amount), 0) AS total FROM bank_receipts "
                    "WHERE approval_status = 'Approved' AND client LIKE ?",
                    (f"%{row['project_name'][:20]}%",),
                ).fetchone()
                received = _safe_float(rec["total"]) if rec else 0.0
            outstanding = max(contract_value - received, 0.0)
            if outstanding <= 0:
                continue
            items.append(
                _forecast_item(
                    flow_type="inflow",
                    category="Project Collection",
                    source="project",
                    source_id=row["id"],
                    expected_date=row["end_date"],
                    amount=outstanding,
                    party=row["project_name"],
                    status=row["status"],
                    project_id=row["id"],
                    project_name=row["project_name"],
                    remarks="Estimated balance due at project completion",
                )
            )

    items.sort(key=lambda x: (x.get("expected_date") or "9999-12-31", x.get("category", "")))
    return items


def _forecast_period_bounds(
    period_key: str,
    project_id: int | None,
    db,
) -> tuple[datetime.date, datetime.date, int | None, str | None]:
    today = datetime.now().date()
    period_key = period_key if period_key in CASH_FLOW_FORECAST_PERIODS else "30"
    project_name = None
    resolved_project_id = project_id

    if period_key == "project" or project_id:
        if project_id:
            row = db.execute(
                "SELECT id, project_name, end_date FROM projects WHERE id=?",
                (project_id,),
            ).fetchone()
        else:
            row = db.execute(
                "SELECT id, project_name, end_date FROM projects "
                "WHERE status='Active' AND end_date IS NOT NULL AND end_date != '' "
                "ORDER BY end_date DESC LIMIT 1"
            ).fetchone()
        if row:
            resolved_project_id = row["id"]
            project_name = row["project_name"]
            end = _parse_date(row["end_date"])
            if end and end >= today:
                return today, end, resolved_project_id, project_name

    days = CASH_FLOW_FORECAST_PERIODS.get(period_key, {}).get("days") or 30
    return today, today + timedelta(days=days), resolved_project_id, project_name


def _forecast_item_in_period(
    item: dict,
    period_start: datetime.date,
    period_end: datetime.date,
    project_id: int | None,
) -> bool:
    expected = _parse_date(item.get("expected_date"))
    if not expected:
        return False
    if expected > period_end:
        return False
    if item.get("source") == "project" and project_id and item.get("project_id") != project_id:
        return False
    if project_id and item.get("project_id") and item.get("project_id") != project_id:
        if item.get("source") in ("pdc_register", "project"):
            return False
    return True


def _build_forecast_buckets(
    inflows: list[dict],
    outflows: list[dict],
    period_start: datetime.date,
    period_end: datetime.date,
) -> list[dict]:
    span_days = (period_end - period_start).days + 1
    step = 1 if span_days <= 14 else 7
    buckets: list[dict] = []
    cursor = period_start
    while cursor <= period_end:
        bucket_end = min(cursor + timedelta(days=step - 1), period_end)

        def _sum_for_period(items: list[dict]) -> float:
            total = 0.0
            for item in items:
                expected = _parse_date(item.get("expected_date"))
                if expected is None:
                    continue
                if cursor <= expected <= bucket_end:
                    total += _safe_float(item.get("amount"))
            return round(total, 2)

        bin_in = _sum_for_period(inflows)
        bin_out = _sum_for_period(outflows)
        buckets.append({
            "label": (
                cursor.strftime("%d %b")
                if cursor == bucket_end
                else f"{cursor.strftime('%d %b')} – {bucket_end.strftime('%d %b')}"
            ),
            "start": cursor.isoformat(),
            "end": bucket_end.isoformat(),
            "inflows": bin_in,
            "outflows": bin_out,
            "net": round(bin_in - bin_out, 2),
        })
        cursor = bucket_end + timedelta(days=1)
    return buckets


def get_cash_flow_forecast(
    db,
    period_key: str = "30",
    project_id: int | None = None,
) -> dict:
    """Rolling cash position from current bank balance plus expected flows."""
    period_key = period_key if period_key in CASH_FLOW_FORECAST_PERIODS else "30"
    period_start, period_end, resolved_project_id, project_name = _forecast_period_bounds(
        period_key, project_id, db,
    )
    all_items = _collect_cash_flow_forecast_items(db)
    inflows = [
        item for item in all_items
        if item["flow_type"] == "inflow"
        and _forecast_item_in_period(item, period_start, period_end, resolved_project_id)
    ]
    outflows = [
        item for item in all_items
        if item["flow_type"] == "outflow"
        and _forecast_item_in_period(item, period_start, period_end, resolved_project_id)
    ]
    opening_balance = treasury_hub_stats(db)["total_balance"]
    expected_inflows = round(sum(_safe_float(i["amount"]) for i in inflows), 2)
    expected_outflows = round(sum(_safe_float(i["amount"]) for i in outflows), 2)
    net_cash_position = round(opening_balance + expected_inflows - expected_outflows, 2)
    max_bucket = 1.0
    buckets = _build_forecast_buckets(inflows, outflows, period_start, period_end)
    for bucket in buckets:
        max_bucket = max(max_bucket, bucket["inflows"], bucket["outflows"])
    for bucket in buckets:
        bucket["inflow_pct"] = round((bucket["inflows"] / max_bucket) * 100, 1) if max_bucket else 0
        bucket["outflow_pct"] = round((bucket["outflows"] / max_bucket) * 100, 1) if max_bucket else 0
    projects = []
    if _table_exists(db, "projects"):
        projects = [
            dict(r) for r in db.execute(
                "SELECT id, project_name, end_date FROM projects "
                "WHERE status='Active' AND end_date IS NOT NULL AND end_date != '' "
                "ORDER BY project_name"
            ).fetchall()
        ]
    return {
        "today": period_start.strftime("%Y-%m-%d"),
        "period_key": period_key,
        "period_label": CASH_FLOW_FORECAST_PERIODS[period_key]["label"],
        "period_start": period_start.strftime("%Y-%m-%d"),
        "period_end": period_end.strftime("%Y-%m-%d"),
        "project_id": resolved_project_id,
        "project_name": project_name,
        "opening_balance": opening_balance,
        "expected_inflows": expected_inflows,
        "expected_outflows": expected_outflows,
        "net_cash_position": net_cash_position,
        "inflow_items": inflows,
        "outflow_items": outflows,
        "buckets": buckets,
        "periods": CASH_FLOW_FORECAST_PERIODS,
        "projects": projects,
    }


def _format_file_size(size_bytes: int | None) -> str:
    size = int(size_bytes or 0)
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def validate_treasury_document_upload(file_storage) -> str | None:
    if not file_storage or not file_storage.filename:
        return "Please choose a file to upload."
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in TREASURY_ALLOWED_EXTENSIONS:
        return "Allowed file types: PDF, JPG, PNG, XLS, XLSX."
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_TREASURY_UPLOAD_BYTES:
        return f"{file_storage.filename} is too large (maximum 10 MB)."
    return None


def _resolve_entity_label(db, entity_type: str | None, entity_id: int | None) -> str:
    if not entity_type or not entity_id:
        return "—"
    if entity_type == "bank_account":
        row = db.execute(
            "SELECT bank_name, account_number FROM bank_accounts WHERE id=?",
            (entity_id,),
        ).fetchone()
        if row:
            return f"{row['bank_name']} — {row['account_number']}"
    elif entity_type == "bank_guarantee":
        row = db.execute(
            "SELECT bg_number, beneficiary FROM bank_guarantees WHERE id=?",
            (entity_id,),
        ).fetchone()
        if row:
            return f"{row['bg_number'] or 'BG'} — {row['beneficiary'] or '—'}"
    elif entity_type == "fixed_deposit":
        row = db.execute(
            "SELECT fd_number, amount FROM fixed_deposits WHERE id=?",
            (entity_id,),
        ).fetchone()
        if row:
            return f"FD #{row['fd_number'] or entity_id} — ₹{_safe_float(row['amount']):,.2f}"
    elif entity_type == "security_deposit":
        row = db.execute(
            "SELECT tsd.deposit_type, tsd.amount, p.project_name "
            "FROM treasury_security_deposits tsd "
            "LEFT JOIN projects p ON tsd.project_id = p.id WHERE tsd.id=?",
            (entity_id,),
        ).fetchone()
        if row:
            project = row["project_name"] or "—"
            return f"{row['deposit_type']} — ₹{_safe_float(row['amount']):,.2f} ({project})"
    elif entity_type == "contract":
        row = db.execute(
            "SELECT pc.contract_number, pc.contract_type, p.project_name "
            "FROM project_contracts pc "
            "LEFT JOIN projects p ON pc.project_id = p.id WHERE pc.id=?",
            (entity_id,),
        ).fetchone()
        if row:
            return (
                f"{row['contract_number'] or 'Contract'} — {row['contract_type'] or '—'}"
                f" ({row['project_name'] or '—'})"
            )
    return f"{entity_type.replace('_', ' ').title()} #{entity_id}"


def _enrich_bank_document(db, row: dict) -> dict:
    doc = dict(row)
    doc["entity_label"] = _resolve_entity_label(db, doc.get("entity_type"), doc.get("entity_id"))
    doc["entity_type_label"] = (doc.get("entity_type") or "").replace("_", " ").title()
    doc["file_size_display"] = _format_file_size(doc.get("file_size"))
    doc["has_file"] = bool((doc.get("file_path") or "").strip())
    return doc


def get_bank_document_entity_options(db) -> dict[str, list[dict]]:
    options: dict[str, list[dict]] = {key: [] for key in BANK_DOCUMENT_ENTITY_TYPES}
    for row in list_bank_accounts(db, active_only=False):
        options["bank_account"].append({
            "id": row["id"],
            "label": f"{row['bank_name']} — {row['account_number']}",
        })
    for row in list_bank_guarantees(db):
        options["bank_guarantee"].append({
            "id": row["id"],
            "label": f"{row.get('bg_number') or 'BG'} — {row.get('beneficiary') or '—'}",
        })
    for row in list_fds(db):
        options["fixed_deposit"].append({
            "id": row["id"],
            "label": f"FD #{row.get('fd_number') or row['id']} — ₹{_safe_float(row.get('amount')):,.2f}",
        })
    for row in list_treasury_security_deposits(db):
        options["security_deposit"].append({
            "id": row["id"],
            "label": (
                f"{row.get('deposit_type') or 'SD'} — ₹{_safe_float(row.get('amount')):,.2f}"
                f" ({row.get('project_name') or '—'})"
            ),
        })
    if _table_exists(db, "project_contracts"):
        for row in db.execute(
            "SELECT pc.id, pc.contract_number, pc.contract_type, p.project_name "
            "FROM project_contracts pc "
            "LEFT JOIN projects p ON pc.project_id = p.id "
            "ORDER BY pc.contract_number"
        ).fetchall():
            options["contract"].append({
                "id": row["id"],
                "label": (
                    f"{row['contract_number'] or 'Contract'} — {row['contract_type'] or '—'}"
                    f" ({row['project_name'] or '—'})"
                ),
            })
    return options


def list_bank_documents(
    db,
    document_type: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    search: str | None = None,
) -> list[dict]:
    sql = (
        "SELECT * FROM bank_documents WHERE COALESCE(is_active, 1)=1 "
    )
    params: list[Any] = []
    if document_type:
        sql += "AND document_type=? "
        params.append(document_type)
    if entity_type:
        sql += "AND entity_type=? "
        params.append(entity_type)
    if entity_id:
        sql += "AND entity_id=? "
        params.append(entity_id)
    if search and search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (original_filename LIKE ? OR notes LIKE ? OR document_type LIKE ?) "
        params.extend([q, q, q])
    sql += "ORDER BY uploaded_at DESC, id DESC"
    return [_enrich_bank_document(db, dict(r)) for r in db.execute(sql, params).fetchall()]


def get_bank_document(db, doc_id: int) -> dict | None:
    row = db.execute(
        "SELECT * FROM bank_documents WHERE id=? AND COALESCE(is_active, 1)=1",
        (doc_id,),
    ).fetchone()
    if not row:
        return None
    doc = _enrich_bank_document(db, dict(row))
    audit_rows = [
        dict(r) for r in db.execute(
            "SELECT * FROM treasury_audit_log WHERE entity_type='bank_document' AND entity_id=? "
            "ORDER BY created_at DESC LIMIT 20",
            (doc_id,),
        ).fetchall()
    ]
    doc["audit_rows"] = audit_rows
    return doc


def upload_bank_document(
    db,
    form,
    saved_filename: str,
    original_filename: str,
    file_size: int,
    username: str,
) -> int:
    document_type = (form.get("document_type") or "").strip()
    entity_type = (form.get("entity_type") or "").strip()
    entity_id_raw = (form.get("entity_id") or "").strip()
    notes = (form.get("notes") or "").strip()
    if document_type not in BANK_DOCUMENT_TYPES:
        raise ValueError("Select a valid document type.")
    if entity_type not in BANK_DOCUMENT_ENTITY_TYPES:
        raise ValueError("Select a valid linked entity type.")
    if not entity_id_raw:
        raise ValueError("Select the linked record.")
    entity_id = int(entity_id_raw)
    if not saved_filename:
        raise ValueError("File upload failed.")
    _validate_entity_exists(db, entity_type, entity_id)
    now = _now_ts()
    cur = db.execute(
        "INSERT INTO bank_documents("
        "entity_type, entity_id, document_type, file_path, original_filename, "
        "file_size, uploaded_by, uploaded_at, notes, is_active"
        ") VALUES(?,?,?,?,?,?,?,?,?,1)",
        (
            entity_type,
            entity_id,
            document_type,
            saved_filename,
            original_filename,
            file_size,
            username,
            now,
            notes,
        ),
    )
    doc_id = int(cur.lastrowid)
    log_treasury_audit(
        db,
        "bank_document",
        doc_id,
        "uploaded",
        username,
        f"{document_type} — {original_filename} ({_format_file_size(file_size)})",
    )
    return doc_id


def delete_bank_document(db, doc_id: int, username: str) -> None:
    doc = get_bank_document(db, doc_id)
    if not doc:
        raise ValueError("Document not found.")
    db.execute(
        "UPDATE bank_documents SET is_active=0 WHERE id=?",
        (doc_id,),
    )
    log_treasury_audit(
        db,
        "bank_document",
        doc_id,
        "archived",
        username,
        f"Archived {doc.get('document_type') or 'document'} — {doc.get('original_filename') or doc_id}",
    )


def _validate_entity_exists(db, entity_type: str, entity_id: int) -> None:
    table_map = {
        "bank_account": ("bank_accounts", "Bank account"),
        "bank_guarantee": ("bank_guarantees", "Bank guarantee"),
        "fixed_deposit": ("fixed_deposits", "Fixed deposit"),
        "security_deposit": ("treasury_security_deposits", "Security deposit"),
    }
    table, label = table_map.get(entity_type, (None, "Record"))
    if not table:
        raise ValueError("Invalid entity type.")
    row = db.execute(f"SELECT id FROM {table} WHERE id=?", (entity_id,)).fetchone()
    if not row:
        raise ValueError(f"{label} not found.")


def _seed_demo_bank_documents(db) -> None:
    if os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        return
    count = db.execute("SELECT COUNT(*) AS c FROM bank_documents").fetchone()["c"]
    if count > 0:
        return
    bg = db.execute("SELECT id FROM bank_guarantees ORDER BY id LIMIT 1").fetchone()
    fd = db.execute("SELECT id FROM fixed_deposits ORDER BY id LIMIT 1").fetchone()
    now = _now_ts()
    if bg:
        db.execute(
            "INSERT INTO bank_documents("
            "entity_type, entity_id, document_type, file_path, original_filename, "
            "file_size, uploaded_by, uploaded_at, notes, is_active"
            ") VALUES(?,?,?,?,?,?,?,?,?,1)",
            (
                "bank_guarantee",
                bg["id"],
                "BG Copy",
                "",
                "BG-copy-demo-placeholder.pdf",
                0,
                "demo",
                now,
                "Demo placeholder — upload the scanned BG copy using Upload Document.",
            ),
        )
    if fd:
        db.execute(
            "INSERT INTO bank_documents("
            "entity_type, entity_id, document_type, file_path, original_filename, "
            "file_size, uploaded_by, uploaded_at, notes, is_active"
            ") VALUES(?,?,?,?,?,?,?,?,?,1)",
            (
                "fixed_deposit",
                fd["id"],
                "FD Receipt",
                "",
                "FD-receipt-demo-placeholder.pdf",
                0,
                "demo",
                now,
                "Demo placeholder — upload the bank FD receipt to attach it here.",
            ),
        )


def post_treasury_on_approval(db, record_table: str, record_id: int, actor: str = "system") -> None:
    """Stub accounting hook — updates bank balance; full GL posting is Phase 2."""
    if record_table == "bank_payments":
        row = db.execute(
            "SELECT bank_account_id, amount, approval_status FROM bank_payments WHERE id=?",
            (record_id,),
        ).fetchone()
        if not row or row["approval_status"] != "Approved":
            return
        amount = _safe_float(row["amount"])
        db.execute(
            "UPDATE bank_accounts SET current_balance = current_balance - ? WHERE id=?",
            (amount, row["bank_account_id"]),
        )
        db.execute(
            "UPDATE bank_payments SET status='Processed' WHERE id=?",
            (record_id,),
        )
        log_treasury_audit(
            db, "bank_payment", record_id, "approved_posted", actor,
            f"Balance reduced by {amount} (stub GL hook)",
        )
    elif record_table == "bank_receipts":
        row = db.execute(
            "SELECT bank_account_id, amount, approval_status FROM bank_receipts WHERE id=?",
            (record_id,),
        ).fetchone()
        if not row or row["approval_status"] != "Approved":
            return
        amount = _safe_float(row["amount"])
        db.execute(
            "UPDATE bank_accounts SET current_balance = current_balance + ? WHERE id=?",
            (amount, row["bank_account_id"]),
        )
        db.execute(
            "UPDATE bank_receipts SET status='Cleared' WHERE id=?",
            (record_id,),
        )
        log_treasury_audit(
            db, "bank_receipt", record_id, "approved_posted", actor,
            f"Balance increased by {amount} (stub GL hook)",
        )
    elif record_table == "bank_guarantees":
        log_treasury_audit(
            db, "bank_guarantee", record_id, "approved", actor,
            "BG record approved (no balance movement)",
        )


def void_treasury_on_reversal(db, record_table: str, record_id: int, actor: str = "system") -> None:
    if record_table == "bank_payments":
        row = db.execute(
            "SELECT bank_account_id, amount, status FROM bank_payments WHERE id=?",
            (record_id,),
        ).fetchone()
        if row and row["status"] == "Processed":
            db.execute(
                "UPDATE bank_accounts SET current_balance = current_balance + ? WHERE id=?",
                (_safe_float(row["amount"]), row["bank_account_id"]),
            )
            db.execute("UPDATE bank_payments SET status='Pending' WHERE id=?", (record_id,))
            log_treasury_audit(db, "bank_payment", record_id, "reversed", actor)
    elif record_table == "bank_receipts":
        row = db.execute(
            "SELECT bank_account_id, amount, status FROM bank_receipts WHERE id=?",
            (record_id,),
        ).fetchone()
        if row and row["status"] == "Cleared":
            db.execute(
                "UPDATE bank_accounts SET current_balance = current_balance - ? WHERE id=?",
                (_safe_float(row["amount"]), row["bank_account_id"]),
            )
            db.execute("UPDATE bank_receipts SET status='Pending' WHERE id=?", (record_id,))
            log_treasury_audit(db, "bank_receipt", record_id, "reversed", actor)


def seed_treasury_demo_data(db) -> None:
    if os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        return
    count = db.execute("SELECT COUNT(*) AS c FROM bank_accounts").fetchone()["c"]
    if count > 0:
        return
    today = datetime.now()
    near_expiry = (today + timedelta(days=25)).strftime("%Y-%m-%d")
    issue_date = (today - timedelta(days=180)).strftime("%Y-%m-%d")
    cur = db.execute(
        "INSERT INTO bank_accounts("
        "bank_name, branch, account_number, ifsc_swift, account_type, currency, "
        "opening_balance, authorized_signatory, od_limit, interest_rate, current_balance, "
        "is_active, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "State Bank of India", "Walajabad", "12345678901", "SBIN0001234",
            "Current", "INR", 2500000, "Managing Director", 500000, 10.5,
            2500000, 1, "system", _now_ts(),
        ),
    )
    acct1 = cur.lastrowid
    cur = db.execute(
        "INSERT INTO bank_accounts("
        "bank_name, branch, account_number, ifsc_swift, account_type, currency, "
        "opening_balance, authorized_signatory, od_limit, interest_rate, current_balance, "
        "is_active, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "HDFC Bank", "Chennai Main", "98765432100", "HDFC0000456",
            "OD", "INR", 800000, "Accounts Manager", 1000000, 11.25,
            800000, 1, "system", _now_ts(),
        ),
    )
    acct2 = cur.lastrowid
    _sync_overdraft_row(db, acct2, 1000000, 11.25)
    db.execute(
        "UPDATE bank_overdrafts SET utilized=150000 WHERE bank_account_id=?",
        (acct2,),
    )
    project = db.execute(
        "SELECT id FROM projects WHERE status='Active' ORDER BY id LIMIT 1"
    ).fetchone()
    project_id = project["id"] if project else None
    db.execute(
        "INSERT INTO bank_payments("
        "payment_date, bank_account_id, payment_type, beneficiary, utr_number, amount, "
        "remarks, status, approval_status, approver_tier, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            today.strftime("%Y-%m-%d"), acct1, "Vendor", "ABC Steel Suppliers",
            "UTR20260619001", 125000, "Material advance", "Pending", "Pending Checker",
            "Accounts Manager", "demo", _now_ts(),
        ),
    )
    db.execute(
        "INSERT INTO bank_payments("
        "payment_date, bank_account_id, payment_type, beneficiary, utr_number, amount, "
        "remarks, status, approval_status, approver_tier, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            (today - timedelta(days=3)).strftime("%Y-%m-%d"), acct1, "Subcontractor",
            "Velu Contractors", "UTR20260616002", 85000, "RA Bill payment", "Processed",
            "Approved", "Accounts Manager", "demo", _now_ts(),
        ),
    )
    db.execute(
        "INSERT INTO bank_receipts("
        "receipt_date, bank_account_id, client, utr_number, amount, receipt_type, "
        "remarks, status, approval_status, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            today.strftime("%Y-%m-%d"), acct1, "NHAI Regional Office",
            "UTR20260619003", 500000, "Client Receipt", "RA-3 mobilization", "Pending",
            "Pending Checker", "demo", _now_ts(),
        ),
    )
    db.execute(
        "INSERT INTO bank_payments("
        "payment_date, bank_account_id, payment_type, beneficiary, utr_number, amount, "
        "remarks, status, approval_status, approver_tier, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            (today + timedelta(days=14)).strftime("%Y-%m-%d"), acct1, "GST",
            "GST Department", "UTR-FUTURE-GST", 42000, "Scheduled GST payment", "Pending",
            "Pending Checker", "Accounts Manager", "demo", _now_ts(),
        ),
    )
    db.execute(
        "INSERT INTO bank_receipts("
        "receipt_date, bank_account_id, client, utr_number, amount, receipt_type, "
        "remarks, status, approval_status, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            (today + timedelta(days=60)).strftime("%Y-%m-%d"), acct1, "State Highway Authority",
            "UTR-FUTURE-RA", 275000, "Client Receipt", "RA-4 expected receipt", "Pending",
            "Pending Checker", "demo", _now_ts(),
        ),
    )
    db.execute(
        "INSERT INTO bank_guarantees("
        "bg_number, bank_account_id, bg_type, project_id, beneficiary, amount, "
        "issue_date, expiry_date, status, approval_status, remarks, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "BG-2026-0042", acct1, "Performance BG", project_id, "NHAI",
            1500000, issue_date, near_expiry, "Active", "Approved",
            "Demo BG expiring in ~25 days", "demo", _now_ts(),
        ),
    )
    db.execute(
        "INSERT INTO bank_reconciliation("
        "bank_account_id, erp_txn_id, erp_txn_type, bank_stmt_ref, txn_date, amount, status, created_at"
        ") VALUES(?,?,?,?,?,?,?,?)",
        (acct1, 2, "bank_payment", "STMT-001", today.strftime("%Y-%m-%d"), 85000, "matched", _now_ts()),
    )
    db.execute(
        "INSERT INTO bank_reconciliation("
        "bank_account_id, erp_txn_id, erp_txn_type, bank_stmt_ref, txn_date, amount, status, created_at"
        ") VALUES(?,?,?,?,?,?,?,?)",
        (acct1, None, None, "STMT-002", today.strftime("%Y-%m-%d"), 1200, "unmatched", _now_ts()),
    )
    if project_id:
        db.execute(
            "INSERT INTO treasury_security_deposits("
            "project_id, bank_account_id, deposit_type, amount, status, deposit_date, remarks, created_at"
            ") VALUES(?,?,?,?,?,?,?,?)",
            (project_id, acct1, "EMD", 250000, "Active", issue_date, "Tender EMD", _now_ts()),
        )
    db.execute(
        "INSERT INTO letters_of_credit("
        "lc_number, bank_account_id, vendor, amount, issue_date, expiry_date, "
        "utilized_amount, status, remarks, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            "LC-2026-001", acct1, "Global Equipment Ltd", 2000000,
            issue_date, (today + timedelta(days=120)).strftime("%Y-%m-%d"),
            450000, "Active", "Plant machinery LC", _now_ts(),
        ),
    )
    _seed_demo_cheques(db)
    _seed_demo_pdc(db)
    _seed_demo_fds(db)
