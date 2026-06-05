"""Payment voucher persistence, schema migration, and audit."""

from __future__ import annotations

import json
from datetime import datetime

from modules.database import (
    DATE_FMT,
    _add_column_if_missing,
    _columns,
    generate_id,
    get_conn,
    log_finance_audit,
    next_document_number,
)

PAYMENT_TYPES = (
    "Employee Payment",
    "Subcontractor Payment",
    "Vendor Payment",
    "Petty Cash Payment",
)

PAYMENT_MODES = ("Cash", "Bank Transfer", "UPI", "Cheque")

EDITABLE_STATUSES = frozenset({"Draft", "Prepared"})

PV_MIGRATION_COLUMNS = (
    ("payment_type", "TEXT"),
    ("payee_id", "TEXT"),
    ("payee_name", "TEXT"),
    ("voucher_date", "TEXT"),
    ("remarks", "TEXT"),
    ("attachment", "TEXT"),
    ("updated_at", "TEXT"),
    ("updated_by", "TEXT"),
    ("approval_comment", "TEXT"),
    ("workflow_remarks", "TEXT"),
    ("payment_reference", "TEXT"),
    ("prepared_by", "TEXT"),
    ("prepared_date", "TEXT"),
    ("checked_by", "TEXT"),
    ("checked_date", "TEXT"),
    ("approved_by", "TEXT"),
    ("approved_date", "TEXT"),
    ("payment_released_by", "TEXT"),
    ("payment_released_date", "TEXT"),
    ("paid_by", "TEXT"),
    ("paid_date", "TEXT"),
)


def _ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def ensure_payment_voucher_schema(conn=None) -> None:
    own = conn is None
    if own:
        conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
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
            status TEXT DEFAULT 'Draft',
            journal_id TEXT,
            created_by TEXT,
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_voucher_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_id TEXT,
            action TEXT,
            actor TEXT,
            action_at TEXT,
            old_status TEXT,
            new_status TEXT,
            comments TEXT,
            changes_json TEXT
        )
        """
    )
    for col, typ in PV_MIGRATION_COLUMNS:
        _add_column_if_missing(cur, "payment_vouchers", col, typ)

    cols = _columns(cur, "payment_vouchers")
    if "payee_name" in cols and "supplier" in cols:
        cur.execute(
            """
            UPDATE payment_vouchers
            SET payee_name = supplier
            WHERE (payee_name IS NULL OR payee_name = '')
              AND supplier IS NOT NULL AND supplier != ''
            """
        )
    if "voucher_date" in cols and "payment_date" in cols:
        cur.execute(
            """
            UPDATE payment_vouchers
            SET voucher_date = payment_date
            WHERE (voucher_date IS NULL OR voucher_date = '')
              AND payment_date IS NOT NULL AND payment_date != ''
            """
        )
    cur.execute(
        """
        UPDATE payment_vouchers SET status = 'Draft'
        WHERE status IS NULL OR TRIM(status) = ''
        """
    )
    if own:
        conn.commit()
        conn.close()


def log_payment_voucher_audit(
    conn,
    voucher_id: str,
    action: str,
    actor: str,
    *,
    old_status: str = "",
    new_status: str = "",
    comments: str = "",
    changes: dict | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO payment_voucher_audit(
            voucher_id, action, actor, action_at,
            old_status, new_status, comments, changes_json
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            voucher_id,
            action,
            actor,
            _ts(),
            old_status or "",
            new_status or "",
            comments or "",
            json.dumps(changes or {}),
        ),
    )
    log_finance_audit(
        conn,
        "payment_voucher",
        voucher_id,
        action,
        actor,
        old_status=old_status,
        new_status=new_status,
        comments=comments,
        changes=changes,
    )


def _normalize_row(row: dict) -> dict:
    out = dict(row)
    if not out.get("payee_name"):
        out["payee_name"] = out.get("supplier") or ""
    if not out.get("supplier"):
        out["supplier"] = out.get("payee_name") or ""
    vdate = out.get("voucher_date") or out.get("payment_date") or ""
    out["voucher_date"] = vdate
    out["payment_date"] = vdate
    return out


def get_payment_voucher(voucher_id: str) -> dict | None:
    ensure_payment_voucher_schema()
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM payment_vouchers WHERE voucher_id = ?",
        (voucher_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _normalize_row(dict(row))


def list_payment_vouchers(*, status: str | None = None, limit: int = 200):
    import pandas as pd

    ensure_payment_voucher_schema()
    conn = get_conn()
    sql = """
        SELECT voucher_id, voucher_no, payment_type, payee_name, supplier,
               payment_date, voucher_date, amount, payment_mode, reference_no,
               project_name, status, created_by, created_at
        FROM payment_vouchers
        WHERE 1=1
    """
    params: list = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    if not df.empty and "payee_name" in df.columns:
        df["payee_name"] = df["payee_name"].fillna(df.get("supplier", ""))
    return df


def load_payment_voucher_audit(voucher_id: str, limit: int = 50):
    import pandas as pd

    ensure_payment_voucher_schema()
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT action_at, actor, action, old_status, new_status, comments
        FROM payment_voucher_audit
        WHERE voucher_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(voucher_id, max(1, min(int(limit), 200))),
    )
    conn.close()
    return df


def voucher_is_editable(status: str | None) -> bool:
    from modules.approval_workflow import normalize_status

    return normalize_status(status, "payment_voucher") in EDITABLE_STATUSES


def save_payment_voucher(data: dict, actor: str) -> tuple[str, str]:
    """
    Create or update a payment voucher.
    Returns (voucher_id, voucher_no).
    """
    ensure_payment_voucher_schema()
    conn = get_conn()
    try:
        voucher_id = (data.get("voucher_id") or "").strip()
        existing = None
        if voucher_id:
            existing = get_payment_voucher(voucher_id)

        if existing and not voucher_is_editable(existing.get("status")):
            raise ValueError(
                f"Voucher cannot be edited in status '{existing.get('status')}'. "
                "Only Draft or Prepared vouchers are editable."
            )

        amount = float(data.get("amount") or 0)
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")

        payment_type = (data.get("payment_type") or "").strip()
        if payment_type not in PAYMENT_TYPES:
            raise ValueError("Please select a valid payment type.")

        payee_name = (data.get("payee_name") or data.get("supplier") or "").strip()
        if not payee_name:
            raise ValueError("Payee name is required.")

        voucher_date = data.get("voucher_date") or data.get("payment_date") or datetime.now().strftime(DATE_FMT)
        if hasattr(voucher_date, "strftime"):
            voucher_date = voucher_date.strftime(DATE_FMT)

        status = (data.get("status") or "Draft").strip() or "Draft"
        if existing:
            status = existing.get("status") or status

        if not voucher_id:
            voucher_id = generate_id("PV", "payment_vouchers", id_column="voucher_id", conn=conn)
            voucher_no = next_document_number("payment_voucher", conn=conn)
            created_at = _ts()
            conn.execute(
                """
                INSERT INTO payment_vouchers(
                    voucher_id, voucher_no, payment_type, payee_id, payee_name, supplier,
                    voucher_date, payment_date, payment_mode, amount, reference_no,
                    project_name, remarks, attachment, status, created_by, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    voucher_id,
                    voucher_no,
                    payment_type,
                    data.get("payee_id") or "",
                    payee_name,
                    payee_name,
                    voucher_date,
                    voucher_date,
                    data.get("payment_mode") or "Bank Transfer",
                    amount,
                    data.get("reference_no") or data.get("reference_number") or "",
                    data.get("project_name") or "",
                    data.get("remarks") or "",
                    data.get("attachment") or "",
                    status,
                    actor,
                    created_at,
                ),
            )
            log_payment_voucher_audit(
                conn,
                voucher_id,
                "Created",
                actor,
                new_status=status,
                changes={"voucher_no": voucher_no, "amount": amount},
            )
        else:
            voucher_no = existing.get("voucher_no") or ""
            conn.execute(
                """
                UPDATE payment_vouchers SET
                    payment_type = ?, payee_id = ?, payee_name = ?, supplier = ?,
                    voucher_date = ?, payment_date = ?, payment_mode = ?, amount = ?,
                    reference_no = ?, project_name = ?, remarks = ?,
                    attachment = COALESCE(?, attachment),
                    updated_at = ?, updated_by = ?
                WHERE voucher_id = ?
                """,
                (
                    payment_type,
                    data.get("payee_id") or "",
                    payee_name,
                    payee_name,
                    voucher_date,
                    voucher_date,
                    data.get("payment_mode") or "Bank Transfer",
                    amount,
                    data.get("reference_no") or "",
                    data.get("project_name") or "",
                    data.get("remarks") or "",
                    data.get("attachment") or None,
                    _ts(),
                    actor,
                    voucher_id,
                ),
            )
            log_payment_voucher_audit(
                conn,
                voucher_id,
                "Updated",
                actor,
                old_status=existing.get("status") if existing else "",
                new_status=status,
                changes={"amount": amount},
            )

        conn.commit()
        if existing:
            return voucher_id, existing.get("voucher_no") or ""
        return voucher_id, voucher_no
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def assign_voucher_numbers_on_save(voucher_id: str, conn) -> str:
    """Ensure voucher_no exists (for legacy rows)."""
    row = conn.execute(
        "SELECT voucher_no FROM payment_vouchers WHERE voucher_id = ?",
        (voucher_id,),
    ).fetchone()
    if row and row[0]:
        return row[0]
    voucher_no = next_document_number("payment_voucher", conn=conn)
    conn.execute(
        "UPDATE payment_vouchers SET voucher_no = ? WHERE voucher_id = ?",
        (voucher_no, voucher_id),
    )
    return voucher_no
