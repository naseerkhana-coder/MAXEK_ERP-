"""Subcontract work-order ledger and payment management."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from accounts_service import _safe_float

MODULE_ID = "subcontract_payments"
WORK_ORDER_TABLE = "subcontract_work_orders"
PAYMENT_TABLE = "subcontract_payment_entries"


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


def _round2(value: float) -> float:
    return round(float(value or 0), 2)


def _recalc_work_order_balances(db, work_order_id: int) -> None:
    wo = db.execute(
        "SELECT work_order_value, certified_value, paid_amount, retention_percent, tds_percent "
        "FROM subcontract_work_orders WHERE id=?",
        (work_order_id,),
    ).fetchone()
    if not wo:
        return
    certified = _round2(wo["certified_value"])
    paid = _round2(wo["paid_amount"])
    retention_pct = _round2(wo["retention_percent"])
    tds_pct = _round2(wo["tds_percent"])
    retention_amt = _round2(certified * retention_pct / 100.0)
    tds_amt = _round2(certified * tds_pct / 100.0)
    balance = _round2(certified - paid - retention_amt - tds_amt)
    db.execute(
        "UPDATE subcontract_work_orders SET retention_amount=?, tds_amount=?, balance_amount=?, modified_at=? "
        "WHERE id=?",
        (retention_amt, tds_amt, balance, _now_ts(), work_order_id),
    )


def ensure_subcontract_payment_schema(db) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS subcontract_work_orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_order_no TEXT UNIQUE NOT NULL,
            project_id INTEGER,
            subcontractor_id INTEGER NOT NULL,
            work_description TEXT,
            work_order_value REAL DEFAULT 0,
            certified_value REAL DEFAULT 0,
            paid_amount REAL DEFAULT 0,
            retention_percent REAL DEFAULT 0,
            retention_amount REAL DEFAULT 0,
            tds_percent REAL DEFAULT 1,
            tds_amount REAL DEFAULT 0,
            balance_amount REAL DEFAULT 0,
            start_date TEXT,
            remarks TEXT,
            created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id)
        )
    """)
    for col, ctype in (
        ("work_order_no", "TEXT"), ("project_id", "INTEGER"), ("subcontractor_id", "INTEGER"),
        ("work_description", "TEXT"), ("work_order_value", "REAL DEFAULT 0"),
        ("certified_value", "REAL DEFAULT 0"), ("paid_amount", "REAL DEFAULT 0"),
        ("retention_percent", "REAL DEFAULT 0"), ("retention_amount", "REAL DEFAULT 0"),
        ("tds_percent", "REAL DEFAULT 1"), ("tds_amount", "REAL DEFAULT 0"),
        ("balance_amount", "REAL DEFAULT 0"), ("start_date", "TEXT"), ("remarks", "TEXT"),
        ("created_by", "TEXT"), ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "subcontract_work_orders", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS subcontract_payment_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_order_id INTEGER NOT NULL,
            payment_date TEXT,
            payment_amount REAL DEFAULT 0,
            tds_deducted REAL DEFAULT 0,
            retention_held REAL DEFAULT 0,
            net_paid REAL DEFAULT 0,
            payment_mode TEXT,
            reference_no TEXT,
            remarks TEXT,
            created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            created_at TEXT,
            FOREIGN KEY(work_order_id) REFERENCES subcontract_work_orders(id) ON DELETE CASCADE
        )
    """)
    for col, ctype in (
        ("work_order_id", "INTEGER"), ("payment_date", "TEXT"), ("payment_amount", "REAL DEFAULT 0"),
        ("tds_deducted", "REAL DEFAULT 0"), ("retention_held", "REAL DEFAULT 0"),
        ("net_paid", "REAL DEFAULT 0"), ("payment_mode", "TEXT"), ("reference_no", "TEXT"),
        ("remarks", "TEXT"), ("created_by", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"), ("created_at", "TEXT"),
    ):
        _ensure_column(db, "subcontract_payment_entries", col, ctype)
    db.commit()


def _next_work_order_no(db) -> str:
    year = datetime.now().strftime("%Y")
    row = db.execute(
        "SELECT work_order_no FROM subcontract_work_orders WHERE work_order_no LIKE ? ORDER BY id DESC LIMIT 1",
        (f"SWO-{year}-%",),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"-(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"SWO-{year}-{seq:04d}"


def save_work_order(db, form, username: str, work_order_id: int | None = None) -> int:
    project_id = form.get("project_id") or None
    subcontractor_id = form.get("subcontractor_id")
    if not subcontractor_id:
        raise ValueError("Select a subcontractor.")
    subcontractor_id = int(subcontractor_id)
    work_description = (form.get("work_description") or "").strip()
    if not work_description:
        raise ValueError("Work description is required.")
    work_order_value = _round2(_safe_float(form.get("work_order_value")))
    certified_value = _round2(_safe_float(form.get("certified_value")))
    retention_percent = _round2(_safe_float(form.get("retention_percent")))
    tds_percent = _round2(_safe_float(form.get("tds_percent")) or 1)
    start_date = (form.get("start_date") or "").strip()
    remarks = (form.get("remarks") or "").strip()
    now = _now_ts()
    if work_order_id:
        db.execute(
            "UPDATE subcontract_work_orders SET project_id=?, subcontractor_id=?, work_description=?, "
            "work_order_value=?, certified_value=?, retention_percent=?, tds_percent=?, start_date=?, "
            "remarks=?, modified_at=? WHERE id=?",
            (
                project_id, subcontractor_id, work_description, work_order_value, certified_value,
                retention_percent, tds_percent, start_date, remarks, now, work_order_id,
            ),
        )
        _recalc_work_order_balances(db, work_order_id)
        return work_order_id
    work_order_no = _next_work_order_no(db)
    db.execute(
        "INSERT INTO subcontract_work_orders("
        "work_order_no, project_id, subcontractor_id, work_description, work_order_value, certified_value, "
        "paid_amount, retention_percent, tds_percent, start_date, remarks, created_by, approval_status, "
        "created_at, modified_at"
        ") VALUES(?,?,?,?,?,?,0,?,?,?,?,?,'Pending Checker',?,?)",
        (
            work_order_no, project_id, subcontractor_id, work_description, work_order_value,
            certified_value, retention_percent, tds_percent, start_date, remarks, username, now, now,
        ),
    )
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    _recalc_work_order_balances(db, new_id)
    return new_id


def save_payment_entry(db, form, username: str, payment_id: int | None = None) -> int:
    work_order_id = form.get("work_order_id")
    if not work_order_id:
        raise ValueError("Select a work order.")
    work_order_id = int(work_order_id)
    payment_date = (form.get("payment_date") or "").strip()
    payment_amount = _round2(_safe_float(form.get("payment_amount")))
    if payment_amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")
    tds_deducted = _round2(_safe_float(form.get("tds_deducted")))
    retention_held = _round2(_safe_float(form.get("retention_held")))
    net_paid = _round2(payment_amount - tds_deducted - retention_held)
    if net_paid < 0:
        raise ValueError("Net paid cannot be negative.")
    payment_mode = (form.get("payment_mode") or "").strip()
    reference_no = (form.get("reference_no") or "").strip()
    remarks = (form.get("remarks") or "").strip()
    now = _now_ts()
    if payment_id:
        old = db.execute(
            "SELECT payment_amount, work_order_id FROM subcontract_payment_entries WHERE id=?",
            (payment_id,),
        ).fetchone()
        if not old:
            raise ValueError("Payment entry not found.")
        db.execute(
            "UPDATE subcontract_payment_entries SET work_order_id=?, payment_date=?, payment_amount=?, "
            "tds_deducted=?, retention_held=?, net_paid=?, payment_mode=?, reference_no=?, remarks=? WHERE id=?",
            (
                work_order_id, payment_date, payment_amount, tds_deducted, retention_held,
                net_paid, payment_mode, reference_no, remarks, payment_id,
            ),
        )
        wo_id = work_order_id
    else:
        db.execute(
            "INSERT INTO subcontract_payment_entries("
            "work_order_id, payment_date, payment_amount, tds_deducted, retention_held, net_paid, "
            "payment_mode, reference_no, remarks, created_by, approval_status, created_at"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,'Pending Checker',?)",
            (
                work_order_id, payment_date, payment_amount, tds_deducted, retention_held,
                net_paid, payment_mode, reference_no, remarks, username, now,
            ),
        )
        payment_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        wo_id = work_order_id
    total_paid = db.execute(
        "SELECT COALESCE(SUM(net_paid), 0) AS total FROM subcontract_payment_entries "
        "WHERE work_order_id=? AND approval_status='Approved'",
        (wo_id,),
    ).fetchone()
    pending_paid = db.execute(
        "SELECT COALESCE(SUM(net_paid), 0) AS total FROM subcontract_payment_entries "
        "WHERE work_order_id=? AND approval_status != 'Approved'",
        (wo_id,),
    ).fetchone()
    paid = _round2((total_paid["total"] if total_paid else 0) + (pending_paid["total"] if pending_paid else 0))
    db.execute(
        "UPDATE subcontract_work_orders SET paid_amount=?, modified_at=? WHERE id=?",
        (paid, now, wo_id),
    )
    _recalc_work_order_balances(db, wo_id)
    return payment_id


def refresh_work_order_paid_totals(db, work_order_id: int) -> None:
    total_paid = db.execute(
        "SELECT COALESCE(SUM(net_paid), 0) AS total FROM subcontract_payment_entries "
        "WHERE work_order_id=? AND approval_status='Approved'",
        (work_order_id,),
    ).fetchone()
    paid = _round2(total_paid["total"] if total_paid else 0)
    db.execute(
        "UPDATE subcontract_work_orders SET paid_amount=?, modified_at=? WHERE id=?",
        (paid, _now_ts(), work_order_id),
    )
    _recalc_work_order_balances(db, work_order_id)


def apply_payment_on_approval(db, payment_id: int) -> None:
    row = db.execute(
        "SELECT work_order_id FROM subcontract_payment_entries WHERE id=?",
        (payment_id,),
    ).fetchone()
    if not row:
        return
    refresh_work_order_paid_totals(db, row["work_order_id"])


def get_work_order(db, work_order_id: int) -> dict | None:
    row = db.execute(
        "SELECT w.*, p.project_name, s.subcontractor_name, s.subcontractor_code "
        "FROM subcontract_work_orders w "
        "LEFT JOIN projects p ON w.project_id = p.id "
        "LEFT JOIN subcontractors s ON w.subcontractor_id = s.id "
        "WHERE w.id=?",
        (work_order_id,),
    ).fetchone()
    if not row:
        return None
    result = dict(row)
    payments = db.execute(
        "SELECT * FROM subcontract_payment_entries WHERE work_order_id=? ORDER BY payment_date DESC, id DESC",
        (work_order_id,),
    ).fetchall()
    result["payments"] = [dict(p) for p in payments]
    return result


def list_work_order_ledger(db, search: str = "") -> list[dict]:
    sql = (
        "SELECT w.*, p.project_name, s.subcontractor_name "
        "FROM subcontract_work_orders w "
        "LEFT JOIN projects p ON w.project_id = p.id "
        "LEFT JOIN subcontractors s ON w.subcontractor_id = s.id "
    )
    params: tuple[Any, ...] = ()
    if search.strip():
        sql += (
            "WHERE w.work_order_no LIKE ? OR s.subcontractor_name LIKE ? OR w.work_description LIKE ? "
        )
        q = f"%{search.strip()}%"
        params = (q, q, q)
    sql += "ORDER BY w.id DESC"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def list_subcontractors_for_payments(db) -> list[dict]:
    rows = db.execute(
        "SELECT id, subcontractor_name, subcontractor_code FROM subcontractors "
        "WHERE status IS NULL OR status != 'Inactive' ORDER BY subcontractor_name"
    ).fetchall()
    return [dict(r) for r in rows]


def ledger_summary(db) -> dict[str, float]:
    row = db.execute(
        "SELECT "
        "COALESCE(SUM(work_order_value), 0) AS total_wo_value, "
        "COALESCE(SUM(certified_value), 0) AS total_certified, "
        "COALESCE(SUM(paid_amount), 0) AS total_paid, "
        "COALESCE(SUM(retention_amount), 0) AS total_retention, "
        "COALESCE(SUM(tds_amount), 0) AS total_tds, "
        "COALESCE(SUM(balance_amount), 0) AS total_balance "
        "FROM subcontract_work_orders"
    ).fetchone()
    if not row:
        return {
            "total_wo_value": 0.0,
            "total_certified": 0.0,
            "total_paid": 0.0,
            "total_retention": 0.0,
            "total_tds": 0.0,
            "total_balance": 0.0,
        }
    return {k: _round2(row[k]) for k in row.keys()}
