"""Petty Cash Fund Management — schema, balances, workflow, audit, reports."""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from modules.database import (
    DATE_FMT,
    _add_column_if_missing,
    _columns,
    generate_id,
    get_conn,
    load_lookup,
    next_document_number,
)

FUND_REQUEST_STATUSES = (
    "Draft",
    "Prepared",
    "Checked",
    "Approved",
    "Payment Released",
    "Paid",
)

EXPENSE_STATUSES = (
    "Draft",
    "Prepared",
    "Checked",
    "Approved",
    "Rejected",
    "Returned",
)

EXPENSE_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "Draft": ("Prepared",),
    "Prepared": ("Checked", "Draft"),
    "Checked": ("Approved", "Prepared", "Rejected", "Returned"),
    "Approved": (),
    "Rejected": (),
    "Returned": ("Draft",),
}

ATTACHMENT_TYPES = ("Invoice", "Bill", "Receipt", "Photo")

PAYMENT_MODES = ("Cash", "Bank Transfer", "UPI", "Cheque")

FUND_EDITABLE = frozenset({"Draft", "Prepared"})

EXPENSE_EDITABLE = frozenset({"Draft", "Returned"})

ISSUE_ALLOWED_FUND_STATUSES = frozenset({"Approved", "Payment Released", "Paid"})

FUND_REQUEST_MIGRATION = (
    ("document_no", "TEXT"),
    ("purpose", "TEXT"),
    ("parent_request_id", "TEXT"),
    ("payment_voucher_id", "TEXT"),
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
    ("payment_reference", "TEXT"),
    ("workflow_remarks", "TEXT"),
    ("updated_at", "TEXT"),
    ("updated_by", "TEXT"),
)

ISSUE_MIGRATION = (
    ("project_name", "TEXT"),
    ("payment_mode", "TEXT"),
    ("reference_no", "TEXT"),
    ("fund_request_id", "TEXT"),
    ("remarks", "TEXT"),
)

EXPENSE_MIGRATION = (
    ("project_name", "TEXT"),
    ("expense_date", "TEXT"),
    ("expense_category", "TEXT"),
    ("vendor_name", "TEXT"),
    ("description", "TEXT"),
    ("payment_mode", "TEXT"),
    ("prepared_by", "TEXT"),
    ("prepared_date", "TEXT"),
    ("checked_by", "TEXT"),
    ("checked_date", "TEXT"),
    ("approved_by", "TEXT"),
    ("approved_date", "TEXT"),
    ("rejected_by", "TEXT"),
    ("rejected_date", "TEXT"),
    ("returned_by", "TEXT"),
    ("returned_date", "TEXT"),
    ("rejection_reason", "TEXT"),
    ("return_reason", "TEXT"),
    ("updated_at", "TEXT"),
    ("updated_by", "TEXT"),
)


def _ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _fmt_date(value) -> str:
    if hasattr(value, "strftime"):
        return value.strftime(DATE_FMT)
    return str(value or datetime.now().strftime(DATE_FMT))


def _fetch_one(conn, sql: str, params: tuple) -> dict | None:
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row, strict=False))


def get_fund_request(request_id: str) -> dict | None:
    ensure_petty_cash_schema()
    conn = get_conn()
    row = _fetch_one(conn, "SELECT * FROM petty_cash_fund_requests WHERE request_id = ?", (request_id,))
    conn.close()
    return row


def get_expense(expense_no: str) -> dict | None:
    ensure_petty_cash_schema()
    conn = get_conn()
    row = _fetch_one(conn, "SELECT * FROM petty_cash_expenses WHERE expense_no = ?", (expense_no,))
    conn.close()
    return row


def ensure_petty_cash_schema(conn=None) -> None:
    own = conn is None
    if own:
        conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS petty_cash_fund_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE,
            document_no TEXT,
            request_date TEXT,
            project_name TEXT,
            requested_by TEXT,
            amount_requested REAL,
            purpose TEXT,
            remarks TEXT,
            status TEXT DEFAULT 'Draft',
            parent_request_id TEXT,
            payment_voucher_id TEXT,
            prepared_by TEXT,
            prepared_date TEXT,
            checked_by TEXT,
            checked_date TEXT,
            approved_by TEXT,
            approved_date TEXT,
            payment_released_by TEXT,
            payment_released_date TEXT,
            paid_by TEXT,
            paid_date TEXT,
            payment_reference TEXT,
            workflow_remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT,
            updated_by TEXT
        )
        """
    )
    for col, typ in FUND_REQUEST_MIGRATION:
        _add_column_if_missing(cur, "petty_cash_fund_requests", col, typ)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS petty_cash_issues(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id TEXT UNIQUE,
            issue_no TEXT,
            project_name TEXT,
            employee_id TEXT,
            employee_name TEXT,
            site TEXT,
            issue_amount REAL,
            issue_date TEXT,
            payment_mode TEXT,
            reference_no TEXT,
            fund_request_id TEXT,
            remarks TEXT,
            status TEXT DEFAULT 'Issued',
            created_by TEXT,
            created_at TEXT
        )
        """
    )
    for col, typ in ISSUE_MIGRATION:
        _add_column_if_missing(cur, "petty_cash_issues", col, typ)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS petty_cash_expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_no TEXT UNIQUE,
            project_name TEXT,
            expense_date TEXT,
            expense_category TEXT,
            vendor_name TEXT,
            description TEXT,
            amount REAL,
            payment_mode TEXT,
            employee_id TEXT,
            employee_name TEXT,
            site TEXT,
            expense_type TEXT,
            bill_upload TEXT,
            status TEXT DEFAULT 'Draft',
            journal_id TEXT,
            prepared_by TEXT,
            prepared_date TEXT,
            checked_by TEXT,
            checked_date TEXT,
            approved_by TEXT,
            approved_date TEXT,
            rejected_by TEXT,
            rejected_date TEXT,
            returned_by TEXT,
            returned_date TEXT,
            rejection_reason TEXT,
            return_reason TEXT,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT,
            updated_by TEXT
        )
        """
    )
    for col, typ in EXPENSE_MIGRATION:
        _add_column_if_missing(cur, "petty_cash_expenses", col, typ)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS petty_cash_attachments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attachment_id TEXT UNIQUE,
            expense_no TEXT,
            attachment_type TEXT,
            file_path TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS petty_cash_audit(
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
        )
        """
    )

    cols = _columns(cur, "petty_cash_issues")
    if "site" in cols and "project_name" in cols:
        cur.execute(
            """
            UPDATE petty_cash_issues
            SET project_name = site
            WHERE (project_name IS NULL OR TRIM(project_name) = '')
              AND site IS NOT NULL AND TRIM(site) != ''
            """
        )

    if own:
        conn.commit()
        conn.close()


def log_petty_cash_audit(
    conn,
    entity_type: str,
    entity_id: str,
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
        INSERT INTO petty_cash_audit(
            entity_type, entity_id, action, actor, action_at,
            old_status, new_status, comments, changes_json
        ) VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            entity_type,
            entity_id,
            action,
            actor,
            _ts(),
            old_status or "",
            new_status or "",
            comments or "",
            json.dumps(changes or {}),
        ),
    )


def load_expense_categories() -> list[str]:
    heads = load_lookup("expense_heads", "head_name")
    if heads:
        return list(heads)
    return [
        "Material",
        "Labour",
        "Transport",
        "Fuel",
        "Equipment",
        "Office Expense",
        "Site Expense",
        "Other",
    ]


def sum_fund_issued(project_name: str, conn=None) -> float:
    own = conn is None
    if own:
        conn = get_conn()
    row = conn.execute(
        """
        SELECT COALESCE(SUM(issue_amount), 0)
        FROM petty_cash_issues
        WHERE project_name = ? AND status = 'Issued'
        """,
        (project_name,),
    ).fetchone()
    if own:
        conn.close()
    return float(row[0] or 0)


def sum_expenses_by_status(project_name: str, statuses: tuple[str, ...], conn=None) -> float:
    if not statuses:
        return 0.0
    own = conn is None
    if own:
        conn = get_conn()
    placeholders = ",".join("?" * len(statuses))
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(amount), 0)
        FROM petty_cash_expenses
        WHERE project_name = ? AND status IN ({placeholders})
        """,
        (project_name, *statuses),
    ).fetchone()
    if own:
        conn.close()
    return float(row[0] or 0)


def get_project_petty_metrics(project_name: str) -> dict:
    if not project_name:
        return {
            "fund_issued": 0.0,
            "expenses_submitted": 0.0,
            "expenses_approved": 0.0,
            "pending_verification": 0.0,
            "balance_in_hand": 0.0,
        }
    fund_issued = sum_fund_issued(project_name)
    approved = sum_expenses_by_status(project_name, ("Approved",))
    submitted = sum_expenses_by_status(
        project_name,
        ("Prepared", "Checked", "Draft", "Returned"),
    )
    pending = sum_expenses_by_status(project_name, ("Prepared",))
    balance = fund_issued - approved
    return {
        "fund_issued": round(fund_issued, 2),
        "expenses_submitted": round(submitted, 2),
        "expenses_approved": round(approved, 2),
        "pending_verification": round(pending, 2),
        "balance_in_hand": round(balance, 2),
    }


def get_petty_balance(project_name: str) -> float:
    return get_project_petty_metrics(project_name)["balance_in_hand"]


def load_project_dashboard() -> pd.DataFrame:
    ensure_petty_cash_schema()
    conn = get_conn()
    projects = pd.read_sql_query(
        """
        SELECT DISTINCT project_name FROM (
            SELECT project_name FROM projects WHERE COALESCE(project_name, '') != ''
            UNION SELECT project_name FROM petty_cash_issues WHERE COALESCE(project_name, '') != ''
            UNION SELECT project_name FROM petty_cash_expenses WHERE COALESCE(project_name, '') != ''
            UNION SELECT project_name FROM petty_cash_fund_requests WHERE COALESCE(project_name, '') != ''
        )
        ORDER BY project_name
        """,
        conn,
    )
    conn.close()
    rows = []
    for pname in projects["project_name"].tolist():
        m = get_project_petty_metrics(pname)
        rows.append(
            {
                "Project": pname,
                "Fund Issued (Rs)": m["fund_issued"],
                "Expenses Submitted (Rs)": m["expenses_submitted"],
                "Expenses Approved (Rs)": m["expenses_approved"],
                "Pending Verification (Rs)": m["pending_verification"],
                "Balance in Hand (Rs)": m["balance_in_hand"],
            }
        )
    return pd.DataFrame(rows)


def owner_dashboard_metrics() -> dict:
    ensure_petty_cash_schema()
    conn = get_conn()
    total_issued = conn.execute(
        "SELECT COALESCE(SUM(issue_amount), 0) FROM petty_cash_issues WHERE status = 'Issued'"
    ).fetchone()[0]
    total_approved = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM petty_cash_expenses WHERE status = 'Approved'"
    ).fetchone()[0]
    total_submitted = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) FROM petty_cash_expenses
        WHERE status IN ('Prepared', 'Checked', 'Draft', 'Returned')
        """
    ).fetchone()[0]
    pending_funds = conn.execute(
        """
        SELECT COUNT(*) FROM petty_cash_fund_requests
        WHERE status IN ('Prepared', 'Checked', 'Approved', 'Payment Released')
        """
    ).fetchone()[0]
    pending_expenses = conn.execute(
        "SELECT COUNT(*) FROM petty_cash_expenses WHERE status IN ('Prepared', 'Checked')"
    ).fetchone()[0]
    conn.close()
    balance = float(total_issued or 0) - float(total_approved or 0)
    return {
        "total_issued": round(float(total_issued or 0), 2),
        "total_expenses": round(float(total_approved or 0), 2),
        "expenses_submitted": round(float(total_submitted or 0), 2),
        "pending_approvals": int(pending_funds or 0) + int(pending_expenses or 0),
        "balance_in_hand": round(balance, 2),
    }


def list_fund_requests(*, status: str | None = None, project: str | None = None, limit: int = 200) -> pd.DataFrame:
    ensure_petty_cash_schema()
    conn = get_conn()
    sql = "SELECT * FROM petty_cash_fund_requests WHERE 1=1"
    params: list = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if project:
        sql += " AND project_name = ?"
        params.append(project)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def save_fund_request(data: dict, actor: str) -> str:
    ensure_petty_cash_schema()
    conn = get_conn()
    try:
        request_id = (data.get("request_id") or "").strip()
        existing = get_fund_request(request_id) if request_id else None
        if existing and (existing.get("status") or "Draft") not in FUND_EDITABLE:
            raise ValueError(f"Fund request cannot be edited in status '{existing.get('status')}'.")

        amount = float(data.get("amount_requested") or 0)
        if amount <= 0:
            raise ValueError("Amount requested must be greater than zero.")
        project = (data.get("project_name") or "").strip()
        if not project:
            raise ValueError("Project is required.")
        requested_by = (data.get("requested_by") or actor).strip()
        request_date = _fmt_date(data.get("request_date"))

        if not request_id:
            request_id = generate_id("PCFR", "petty_cash_fund_requests", id_column="request_id", conn=conn)
            doc_no = next_document_number("petty_cash_fund_request", conn=conn)
            status = "Draft"
            conn.execute(
                """
                INSERT INTO petty_cash_fund_requests(
                    request_id, document_no, request_date, project_name, requested_by,
                    amount_requested, purpose, remarks, status, parent_request_id,
                    created_by, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    request_id,
                    doc_no,
                    request_date,
                    project,
                    requested_by,
                    amount,
                    data.get("purpose") or "",
                    data.get("remarks") or "",
                    status,
                    data.get("parent_request_id") or "",
                    actor,
                    _ts(),
                ),
            )
            log_petty_cash_audit(
                conn, "fund_request", request_id, "Created", actor, new_status=status,
                changes={"amount": amount, "project": project},
            )
        else:
            conn.execute(
                """
                UPDATE petty_cash_fund_requests SET
                    request_date = ?, project_name = ?, requested_by = ?,
                    amount_requested = ?, purpose = ?, remarks = ?,
                    parent_request_id = COALESCE(?, parent_request_id),
                    updated_at = ?, updated_by = ?
                WHERE request_id = ?
                """,
                (
                    request_date,
                    project,
                    requested_by,
                    amount,
                    data.get("purpose") or "",
                    data.get("remarks") or "",
                    data.get("parent_request_id") or None,
                    _ts(),
                    actor,
                    request_id,
                ),
            )
            log_petty_cash_audit(
                conn,
                "fund_request",
                request_id,
                "Updated",
                actor,
                old_status=existing.get("status") if existing else "",
                new_status=existing.get("status") if existing else "Draft",
            )
        conn.commit()
        return request_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def link_fund_request_payment_voucher(request_id: str, voucher_id: str, actor: str) -> None:
    conn = get_conn()
    conn.execute(
        "UPDATE petty_cash_fund_requests SET payment_voucher_id = ?, updated_at = ?, updated_by = ? WHERE request_id = ?",
        (voucher_id, _ts(), actor, request_id),
    )
    log_petty_cash_audit(
        conn,
        "fund_request",
        request_id,
        "LinkPaymentVoucher",
        actor,
        changes={"payment_voucher_id": voucher_id},
    )
    conn.commit()
    conn.close()


def save_fund_issue(data: dict, actor: str) -> str:
    ensure_petty_cash_schema()
    conn = get_conn()
    try:
        project = (data.get("project_name") or "").strip()
        if not project:
            raise ValueError("Project is required.")
        amount = float(data.get("issue_amount") or 0)
        if amount <= 0:
            raise ValueError("Issue amount must be greater than zero.")
        employee_name = (data.get("employee_name") or "").strip()
        if not employee_name:
            raise ValueError("Employee name is required.")

        fund_request_id = (data.get("fund_request_id") or "").strip()
        if fund_request_id:
            fr = get_fund_request(fund_request_id)
            if not fr:
                raise ValueError("Linked fund request not found.")
            if (fr.get("status") or "") not in ISSUE_ALLOWED_FUND_STATUSES:
                raise ValueError(
                    f"Fund request must be Approved or paid before issue (current: {fr.get('status')})."
                )

        issue_id = generate_id("PCI", "petty_cash_issues", id_column="issue_id", conn=conn)
        issue_no = next_document_number("petty_cash_issue", conn=conn)
        conn.execute(
            """
            INSERT INTO petty_cash_issues(
                issue_id, issue_no, project_name, employee_id, employee_name, site,
                issue_amount, issue_date, payment_mode, reference_no, fund_request_id,
                remarks, status, created_by, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                issue_id,
                issue_no,
                project,
                data.get("employee_id") or "",
                employee_name,
                project,
                amount,
                _fmt_date(data.get("issue_date")),
                data.get("payment_mode") or "Cash",
                data.get("reference_no") or "",
                fund_request_id,
                data.get("remarks") or "",
                "Issued",
                actor,
                _ts(),
            ),
        )
        log_petty_cash_audit(
            conn,
            "fund_issue",
            issue_id,
            "Issued",
            actor,
            new_status="Issued",
            changes={"project": project, "amount": amount, "issue_no": issue_no},
        )
        conn.commit()
        return issue_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_expenses(*, status: str | None = None, project: str | None = None, limit: int = 200) -> pd.DataFrame:
    ensure_petty_cash_schema()
    conn = get_conn()
    sql = "SELECT * FROM petty_cash_expenses WHERE 1=1"
    params: list = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if project:
        sql += " AND project_name = ?"
        params.append(project)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def list_expense_attachments(expense_no: str) -> pd.DataFrame:
    ensure_petty_cash_schema()
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM petty_cash_attachments WHERE expense_no = ? ORDER BY id",
        conn,
        params=(expense_no,),
    )
    conn.close()
    return df


def save_expense_attachments(
    conn,
    expense_no: str,
    attachments: list[tuple[str, str]],
    actor: str,
) -> None:
    for att_type, path in attachments:
        if not path:
            continue
        att_id = generate_id("PCA", "petty_cash_attachments", id_column="attachment_id", conn=conn)
        conn.execute(
            """
            INSERT INTO petty_cash_attachments(
                attachment_id, expense_no, attachment_type, file_path, uploaded_by, uploaded_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (att_id, expense_no, att_type, path, actor, _ts()),
        )


def save_expense(data: dict, actor: str, *, attachments: list[tuple[str, str]] | None = None) -> str:
    ensure_petty_cash_schema()
    conn = get_conn()
    try:
        expense_no = (data.get("expense_no") or "").strip()
        existing = get_expense(expense_no) if expense_no else None
        status = (existing.get("status") if existing else "Draft") or "Draft"
        if existing and status not in EXPENSE_EDITABLE:
            raise ValueError(f"Expense cannot be edited in status '{status}'.")

        project = (data.get("project_name") or "").strip()
        if not project:
            raise ValueError("Project is required.")
        amount = float(data.get("amount") or 0)
        if amount <= 0:
            raise ValueError("Expense amount must be greater than zero.")

        if not expense_no:
            expense_no = generate_id("PCE", "petty_cash_expenses", id_column="expense_no", conn=conn)
            conn.execute(
                """
                INSERT INTO petty_cash_expenses(
                    expense_no, project_name, expense_date, expense_category, vendor_name,
                    description, amount, payment_mode, status, created_by, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    expense_no,
                    project,
                    _fmt_date(data.get("expense_date")),
                    data.get("expense_category") or "",
                    data.get("vendor_name") or "",
                    data.get("description") or "",
                    amount,
                    data.get("payment_mode") or "Cash",
                    "Draft",
                    actor,
                    _ts(),
                ),
            )
            log_petty_cash_audit(
                conn, "expense", expense_no, "Created", actor, new_status="Draft",
                changes={"amount": amount, "project": project},
            )
        else:
            conn.execute(
                """
                UPDATE petty_cash_expenses SET
                    project_name = ?, expense_date = ?, expense_category = ?,
                    vendor_name = ?, description = ?, amount = ?, payment_mode = ?,
                    updated_at = ?, updated_by = ?
                WHERE expense_no = ?
                """,
                (
                    project,
                    _fmt_date(data.get("expense_date")),
                    data.get("expense_category") or "",
                    data.get("vendor_name") or "",
                    data.get("description") or "",
                    amount,
                    data.get("payment_mode") or "Cash",
                    _ts(),
                    actor,
                    expense_no,
                ),
            )
            log_petty_cash_audit(
                conn,
                "expense",
                expense_no,
                "Updated",
                actor,
                old_status=status,
                new_status=status,
            )

        if attachments:
            conn.execute("DELETE FROM petty_cash_attachments WHERE expense_no = ?", (expense_no,))
            save_expense_attachments(conn, expense_no, attachments, actor)

        conn.commit()
        return expense_no
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def expense_has_attachments(expense_no: str) -> bool:
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) FROM petty_cash_attachments WHERE expense_no = ?",
        (expense_no,),
    ).fetchone()[0]
    conn.close()
    return int(n or 0) > 0


def can_transition_expense(current: str, new_status: str) -> bool:
    from modules.approval_workflow import normalize_status

    cur = normalize_status(current, "petty_cash_expense")
    nxt = normalize_status(new_status, "petty_cash_expense")
    if cur in ("Rejected", "Approved"):
        return False
    if nxt == "Returned" and cur in ("Prepared", "Checked"):
        return True
    if nxt == "Rejected" and cur == "Checked":
        return True
    if nxt in EXPENSE_TRANSITIONS.get(cur, ()):
        return True
    return cur == nxt


def transition_expense(
    expense_no: str,
    new_status: str,
    actor: str,
    *,
    comments: str = "",
) -> tuple[bool, str]:
    from modules.approval_workflow import normalize_status

    row = get_expense(expense_no)
    if not row:
        return False, "Expense not found."
    cur = normalize_status(row.get("status"), "petty_cash_expense")
    nxt = normalize_status(new_status, "petty_cash_expense")
    if nxt == "Prepared" and not expense_has_attachments(expense_no):
        return False, "Upload at least one attachment before submitting."
    if nxt == "Approved":
        bal = get_petty_balance(row.get("project_name") or "")
        amt = float(row.get("amount") or 0)
        if amt > bal:
            return (
                False,
                f"Cannot approve: balance Rs {bal:,.2f} is less than expense Rs {amt:,.2f}.",
            )
    if not can_transition_expense(cur, nxt):
        return False, f"Cannot move from {cur} to {nxt}."

    conn = get_conn()
    try:
        updates = {"status": nxt, "updated_at": _ts(), "updated_by": actor}
        field_map = {
            "Prepared": ("prepared_by", "prepared_date"),
            "Checked": ("checked_by", "checked_date"),
            "Approved": ("approved_by", "approved_date"),
            "Rejected": ("rejected_by", "rejected_date"),
            "Returned": ("returned_by", "returned_date"),
        }
        if nxt in field_map:
            by_col, dt_col = field_map[nxt]
            updates[by_col] = actor
            updates[dt_col] = _ts()
        if nxt == "Rejected":
            updates["rejection_reason"] = comments
        if nxt == "Returned":
            updates["return_reason"] = comments

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE petty_cash_expenses SET {set_clause} WHERE expense_no = ?",
            (*updates.values(), expense_no),
        )
        log_petty_cash_audit(
            conn,
            "expense",
            expense_no,
            f"Status→{nxt}",
            actor,
            old_status=cur,
            new_status=nxt,
            comments=comments,
        )
        conn.commit()
        return True, f"Expense updated to {nxt}."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def load_petty_cash_audit(entity_type: str, entity_id: str, limit: int = 50) -> pd.DataFrame:
    ensure_petty_cash_schema()
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT action_at, actor, action, old_status, new_status, comments
        FROM petty_cash_audit
        WHERE entity_type = ? AND entity_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(entity_type, entity_id, max(1, min(int(limit), 200))),
    )
    conn.close()
    return df


def report_ledger(project: str | None = None) -> pd.DataFrame:
    ensure_petty_cash_schema()
    conn = get_conn()
    params: list = []
    issue_sql = """
        SELECT issue_date AS txn_date, 'Fund Issue' AS txn_type, issue_no AS ref_no,
               project_name, employee_name AS party, issue_amount AS amount,
               'Credit' AS dr_cr, status
        FROM petty_cash_issues WHERE status = 'Issued'
    """
    exp_sql = """
        SELECT expense_date AS txn_date, 'Expense' AS txn_type, expense_no AS ref_no,
               project_name, vendor_name AS party, amount,
               'Debit' AS dr_cr, status
        FROM petty_cash_expenses
        WHERE status NOT IN ('Rejected', 'Draft')
    """
    if project:
        issue_sql += " AND project_name = ?"
        exp_sql += " AND project_name = ?"
        params = [project, project]
    df = pd.read_sql_query(
        f"{issue_sql} UNION ALL {exp_sql} ORDER BY txn_date DESC, ref_no DESC",
        conn,
        params=params if project else [],
    )
    conn.close()
    return df


def report_balance() -> pd.DataFrame:
    return load_project_dashboard()


def report_expense_by_category(project: str | None = None) -> pd.DataFrame:
    ensure_petty_cash_schema()
    conn = get_conn()
    sql = """
        SELECT expense_category AS category,
               COUNT(*) AS expense_count,
               COALESCE(SUM(amount), 0) AS total_amount
        FROM petty_cash_expenses
        WHERE status = 'Approved'
    """
    params: list = []
    if project:
        sql += " AND project_name = ?"
        params.append(project)
    sql += " GROUP BY expense_category ORDER BY total_amount DESC"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def report_project_wise() -> pd.DataFrame:
    return load_project_dashboard()


def report_employee_wise() -> pd.DataFrame:
    ensure_petty_cash_schema()
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT COALESCE(employee_name, '—') AS employee,
               COALESCE(project_name, site, '—') AS project,
               COUNT(*) AS issue_count,
               COALESCE(SUM(issue_amount), 0) AS total_issued
        FROM petty_cash_issues
        WHERE status = 'Issued'
        GROUP BY employee_name, project_name, site
        ORDER BY total_issued DESC
        """,
        conn,
    )
    conn.close()
    return df


def report_fund_request_history(project: str | None = None) -> pd.DataFrame:
    ensure_petty_cash_schema()
    conn = get_conn()
    sql = """
        SELECT document_no, request_date, project_name, requested_by,
               amount_requested, purpose, status, parent_request_id, payment_voucher_id
        FROM petty_cash_fund_requests
        WHERE 1=1
    """
    params: list = []
    if project:
        sql += " AND project_name = ?"
        params.append(project)
    sql += " ORDER BY id DESC"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df
