"""Standard MAXEK ERP approval workflow — shared statuses, transitions, and audit."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from modules.database import DATE_FMT, get_conn

WORKFLOW_STATUSES = (
    "Draft",
    "Prepared",
    "Checked",
    "Approved",
    "Payment Released",
    "Paid",
)

TERMINAL_STATUSES = frozenset({"Paid", "Rejected", "Cancelled", "Void"})

VALID_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "Draft": ("Prepared",),
    "Prepared": ("Checked", "Draft"),
    "Checked": ("Approved", "Prepared"),
    "Approved": ("Payment Released",),
    "Payment Released": ("Paid",),
    "Paid": (),
}

TRANSITION_ACTION = {
    "Prepared": "prepare",
    "Checked": "check",
    "Approved": "approve",
    "Payment Released": "release_payment",
    "Paid": "mark_paid",
    "Draft": "return_draft",
}

STEP_ACTOR_FIELDS = {
    "Prepared": ("prepared_by", "prepared_date"),
    "Checked": ("checked_by", "checked_date"),
    "Approved": ("approved_by", "approved_date"),
    "Payment Released": ("payment_released_by", "payment_released_date"),
    "Paid": ("paid_by", "paid_date"),
}

# Legacy stored values → canonical workflow status (read path; do not mutate DB in bulk).
STATUS_LEGACY_MAP: dict[str, str] = {
    # Generic
    "": "Draft",
    "Open": "Draft",
    "Pending": "Prepared",
    "Submitted": "Prepared",
    "Returned": "Draft",
    "Generated": "Draft",
    # Finance / expenses
    "Verified": "Checked",
    "PM Approved": "Checked",
    "Accounts Checked": "Checked",
    "MD Approved": "Approved",
    "Released": "Payment Released",
    "Settled": "Paid",
    "Posted": "Approved",
    # Payroll (staff)
    "Submitted to MD": "Prepared",
    "Sent Back": "Draft",
    # Payroll (worker)
    "Calculated": "Prepared",
    # Material
    "Issued": "Paid",
    # Petty / misc
    "Cancelled": "Cancelled",
    "Void": "Void",
}

ENTITY_TYPES = (
    "staff_payroll",
    "worker_payroll",
    "subcontractor_bill",
    "material_request",
    "purchase_order",
    "vendor_bill",
    "site_expense",
    "petty_cash",
    "client_bill",
    "direct_payment",
    "payment_voucher",
    "petty_cash_fund_request",
)

ENTITY_CONFIG: dict[str, dict[str, Any]] = {
    "staff_payroll": {
        "table": "payroll",
        "id_column": "payroll_id",
        "status_column": "workflow_status",
        "status_fallback": "salary_status",
        "payment_ref_column": "payment_mode",
    },
    "worker_payroll": {
        "table": "worker_payroll_runs",
        "id_column": "run_id",
        "status_column": "workflow_status",
        "payment_ref_column": "payment_reference",
    },
    "subcontractor_bill": {
        "table": "subcontractor_bills",
        "id_column": "bill_id",
        "status_column": "status",
    },
    "material_request": {
        "table": "material_requests",
        "id_column": "request_id",
        "status_column": "status",
    },
    "purchase_order": {
        "table": "purchase_orders",
        "id_column": "po_id",
        "status_column": "status",
    },
    "vendor_bill": {
        "table": "expense_invoices",
        "id_column": "invoice_id",
        "status_column": "status",
        "payment_ref_column": "payment_method",
    },
    "site_expense": {
        "table": "site_expenses",
        "id_column": "expense_id",
        "status_column": "status",
    },
    "petty_cash": {
        "table": "petty_cash_requests",
        "id_column": "request_id",
        "status_column": "status",
    },
    "client_bill": {
        "table": "client_bills",
        "id_column": "bill_id",
        "status_column": "status",
    },
    "direct_payment": {
        "table": "direct_payments",
        "id_column": "payment_id",
        "status_column": "status",
        "payment_ref_column": "reference_number",
    },
    "payment_voucher": {
        "table": "payment_vouchers",
        "id_column": "voucher_id",
        "status_column": "status",
        "payment_ref_column": "reference_no",
    },
    "petty_cash_fund_request": {
        "table": "petty_cash_fund_requests",
        "id_column": "request_id",
        "status_column": "status",
        "payment_ref_column": "payment_reference",
    },
}

# When writing canonical status, optional legacy alias for tables still filtered by old labels.
STATUS_WRITE_ALIAS: dict[str, dict[str, str]] = {
    "site_expense": {
        "Prepared": "Submitted",
        "Checked": "Verified",
        "Approved": "Approved",
        "Payment Released": "Approved",
        "Paid": "Approved",
    },
    "petty_cash": {
        "Prepared": "Submitted",
        "Checked": "Verified",
        "Approved": "Approved",
        "Payment Released": "Released",
    },
    "material_request": {
        "Prepared": "Pending",
        "Approved": "Approved",
        "Paid": "Issued",
    },
    "staff_payroll": {
        "Prepared": "Submitted to MD",
        "Approved": "MD Approved",
        "Paid": "Paid",
    },
    "worker_payroll": {
        "Prepared": "Calculated",
    },
    "subcontractor_bill": {
        "Draft": "Generated",
        "Prepared": "Generated",
    },
    "client_bill": {
        "Draft": "Generated",
        "Prepared": "Generated",
    },
    "vendor_bill": {
        "Prepared": "Submitted",
        "Checked": "Verified",
    },
    "purchase_order": {
        "Prepared": "Pending",
    },
    "payment_voucher": {
        "Prepared": "Submitted",
        "Checked": "Verified",
    },
    "petty_cash_fund_request": {
        "Prepared": "Submitted",
        "Checked": "Verified",
        "Payment Released": "Released",
        "Paid": "Paid",
    },
}

WORKFLOW_TABLES = tuple({cfg["table"] for cfg in ENTITY_CONFIG.values()})

WORKFLOW_EXTRA_COLUMNS = (
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
    ("approval_comment", "TEXT"),
    ("workflow_remarks", "TEXT"),
    ("payment_reference", "TEXT"),
)


def _ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def normalize_status(raw: str | None, entity_type: str | None = None) -> str:
    text = (raw or "").strip()
    if not text:
        return "Draft"
    if text in WORKFLOW_STATUSES:
        return text
    mapped = STATUS_LEGACY_MAP.get(text)
    if mapped:
        return mapped
    upper = text.upper()
    for key, val in STATUS_LEGACY_MAP.items():
        if key.upper() == upper:
            return val
    return text if text in WORKFLOW_STATUSES + tuple(TERMINAL_STATUSES) else "Draft"


def status_for_storage(entity_type: str, canonical: str) -> str:
    aliases = STATUS_WRITE_ALIAS.get(entity_type, {})
    return aliases.get(canonical, canonical)


def legacy_status_label(canonical: str) -> str:
    """Inverse hint for UI filters still using legacy labels."""
    for legacy, canon in STATUS_LEGACY_MAP.items():
        if canon == canonical and legacy not in WORKFLOW_STATUSES:
            return legacy
    return canonical


def can_transition(current: str, new_status: str) -> bool:
    cur = normalize_status(current)
    nxt = normalize_status(new_status)
    if cur == nxt:
        return True
    return nxt in VALID_TRANSITIONS.get(cur, ())


def _table_columns(conn, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def ensure_approval_workflow_schema(conn=None) -> None:
    own = conn is None
    if own:
        conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT,
            entity_id TEXT,
            action TEXT,
            actor TEXT,
            action_at TEXT,
            old_status TEXT,
            new_status TEXT,
            comments TEXT,
            payment_ref TEXT,
            changes_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT,
            title TEXT,
            detail TEXT,
            entity_type TEXT,
            entity_id TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT
        )
        """
    )
    for table in WORKFLOW_TABLES:
        cols = _table_columns(conn, table)
        for col, typ in WORKFLOW_EXTRA_COLUMNS:
            if col not in cols:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
                except Exception:
                    pass
    if own:
        conn.commit()
        conn.close()


def log_workflow_audit(
    conn,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: str,
    old_status: str = "",
    new_status: str = "",
    comments: str = "",
    payment_ref: str = "",
    changes: dict | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO workflow_audit_log(
            entity_type, entity_id, action, actor, action_at,
            old_status, new_status, comments, payment_ref, changes_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
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
            payment_ref or "",
            json.dumps(changes or {}),
        ),
    )


def load_workflow_audit(entity_type: str, entity_id: str, limit: int = 50):
    import pandas as pd

    ensure_approval_workflow_schema()
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT action_at, actor, action, old_status, new_status, comments, payment_ref
        FROM workflow_audit_log
        WHERE entity_type = ? AND entity_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(entity_type, entity_id, max(1, min(int(limit), 200))),
    )
    conn.close()
    return df


def _resolve_entity(entity_type: str) -> dict[str, Any]:
    if entity_type not in ENTITY_CONFIG:
        raise ValueError(f"Unknown entity_type: {entity_type}")
    return ENTITY_CONFIG[entity_type]


def _fetch_row(conn, cfg: dict, entity_id: str) -> dict | None:
    table = cfg["table"]
    id_col = cfg["id_column"]
    status_col = cfg["status_column"]
    fallback = cfg.get("status_fallback")
    status_expr = f"COALESCE({status_col}, '')"
    if fallback:
        status_expr = f"COALESCE(NULLIF({status_col}, ''), {fallback}, '')"
    cur = conn.execute(
        f"SELECT *, {status_expr} AS _workflow_status FROM {table} WHERE {id_col} = ?",
        (entity_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def _role_may_apply(role: str, action: str, entity_type: str) -> bool:
    from modules.roles import (
        can_approve_workflow,
        can_check_workflow,
        can_mark_paid_workflow,
        can_prepare_workflow,
        can_release_payment_workflow,
    )

    if action == "prepare":
        return can_prepare_workflow(role, entity_type)
    if action == "check":
        return can_check_workflow(role, entity_type)
    if action == "approve":
        return can_approve_workflow(role, entity_type)
    if action == "release_payment":
        return can_release_payment_workflow(role)
    if action == "mark_paid":
        return can_mark_paid_workflow(role)
    if action == "return_draft":
        return can_prepare_workflow(role, entity_type) or can_check_workflow(role, entity_type)
    return False


def transition(
    entity_type: str,
    entity_id: str,
    new_status: str,
    actor: str,
    role: str,
    comment: str = "",
    payment_ref: str = "",
) -> tuple[bool, str]:
    """
    Apply a workflow transition. Returns (success, message).
    Stores canonical status; may map to legacy alias per entity where configured.
    """
    ensure_approval_workflow_schema()
    cfg = _resolve_entity(entity_type)
    canonical_new = normalize_status(new_status, entity_type)
    action = TRANSITION_ACTION.get(canonical_new, "status_change")

    conn = get_conn()
    try:
        row = _fetch_row(conn, cfg, entity_id)
        if not row:
            return False, "Record not found."

        old_raw = row.get("_workflow_status") or row.get(cfg["status_column"]) or ""
        old_canon = normalize_status(old_raw, entity_type)

        if not can_transition(old_canon, canonical_new):
            return False, f"Cannot move from {old_canon} to {canonical_new}."

        if not _role_may_apply(role, action, entity_type):
            return False, f"Role '{role}' cannot perform '{action}' on {entity_type}."

        stored_status = status_for_storage(entity_type, canonical_new)
        table = cfg["table"]
        id_col = cfg["id_column"]
        status_col = cfg["status_column"]
        cols = _table_columns(conn, table)

        sets = [f"{status_col} = ?"]
        params: list[Any] = [stored_status]

        if cfg.get("status_fallback") and cfg["status_fallback"] in cols:
            sets.append(f"{cfg['status_fallback']} = ?")
            params.append(stored_status)

        actor_field, date_field = STEP_ACTOR_FIELDS.get(canonical_new, (None, None))
        if actor_field and actor_field in cols:
            sets.append(f"{actor_field} = ?")
            params.append(actor)
        if date_field and date_field in cols:
            sets.append(f"{date_field} = ?")
            params.append(_ts())

        if comment and "approval_comment" in cols:
            sets.append("approval_comment = ?")
            params.append(comment)
        if comment and "workflow_remarks" in cols:
            sets.append("workflow_remarks = ?")
            params.append(comment)

        pref_col = cfg.get("payment_ref_column") or "payment_reference"
        if payment_ref and pref_col in cols:
            sets.append(f"{pref_col} = ?")
            params.append(payment_ref)
        elif payment_ref and "payment_reference" in cols:
            sets.append("payment_reference = ?")
            params.append(payment_ref)

        params.append(entity_id)
        conn.execute(
            f"UPDATE {table} SET {', '.join(sets)} WHERE {id_col} = ?",
            params,
        )

        log_workflow_audit(
            conn,
            entity_type,
            entity_id,
            action,
            actor,
            old_raw,
            stored_status,
            comment,
            payment_ref,
        )
        conn.commit()

        try:
            from modules.notifications import notify_workflow_transition

            notify_workflow_transition(
                entity_type,
                entity_id,
                old_canon,
                canonical_new,
                actor,
                comment=comment,
            )
        except Exception:
            pass

        return True, f"Status updated to {canonical_new}."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def get_pending_for_role(user: str, role: str) -> list[dict[str, Any]]:
    """Items awaiting action by this role (by canonical status)."""
    from modules.roles import (
        can_approve_workflow,
        can_check_workflow,
        can_mark_paid_workflow,
        can_prepare_workflow,
        can_release_payment_workflow,
    )

    ensure_approval_workflow_schema()
    pending: list[dict[str, Any]] = []
    conn = get_conn()

    def _count_query(table: str, status_col: str, statuses: tuple[str, ...]) -> int:
        placeholders = ",".join("?" * len(statuses))
        try:
            row = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {status_col} IN ({placeholders})",
                statuses,
            ).fetchone()
            return int(row[0] or 0)
        except Exception:
            return 0

    checks: list[tuple[str, str, str, tuple[str, ...]]] = []

    if can_check_workflow(role, "site_expense"):
        checks.append(
            (
                "site_expense",
                "site_expenses",
                "expense_id",
                ("Submitted", "Prepared"),
            )
        )
    if can_approve_workflow(role, "site_expense"):
        checks.append(
            (
                "site_expense",
                "site_expenses",
                "expense_id",
                ("Verified", "PM Approved", "Checked"),
            )
        )
    if can_check_workflow(role, "petty_cash_fund_request"):
        checks.append(
            (
                "petty_cash_fund_request",
                "petty_cash_fund_requests",
                "request_id",
                ("Submitted", "Prepared"),
            )
        )
    if can_approve_workflow(role, "petty_cash_fund_request"):
        checks.append(
            (
                "petty_cash_fund_request",
                "petty_cash_fund_requests",
                "request_id",
                ("Verified", "Checked"),
            )
        )
    if can_release_payment_workflow(role):
        checks.append(
            (
                "petty_cash_fund_request",
                "petty_cash_fund_requests",
                "request_id",
                ("Approved",),
            )
        )
    if can_check_workflow(role, "petty_cash"):
        checks.append(("petty_cash", "petty_cash_requests", "request_id", ("Submitted", "Prepared")))
    if can_approve_workflow(role, "petty_cash"):
        checks.append(("petty_cash", "petty_cash_requests", "request_id", ("Verified", "Checked")))
    if can_release_payment_workflow(role):
        checks.append(
            ("petty_cash", "petty_cash_requests", "request_id", ("Approved",))
        )
    if can_prepare_workflow(role, "material_request"):
        checks.append(
            ("material_request", "material_requests", "request_id", ("Pending", "Draft"))
        )
    if can_approve_workflow(role, "material_request"):
        checks.append(
            ("material_request", "material_requests", "request_id", ("Pending", "Prepared"))
        )
    if can_approve_workflow(role, "staff_payroll"):
        checks.append(
            ("staff_payroll", "payroll", "payroll_id", ("Submitted to MD", "Prepared"))
        )
    if can_approve_workflow(role, "worker_payroll"):
        checks.append(
            ("worker_payroll", "worker_payroll_runs", "run_id", ("Calculated", "Prepared"))
        )
    if can_release_payment_workflow(role):
        checks.append(
            ("worker_payroll", "worker_payroll_runs", "run_id", ("Approved",))
        )
    if can_mark_paid_workflow(role):
        checks.append(
            ("worker_payroll", "worker_payroll_runs", "run_id", ("Approved", "Payment Released"))
        )
        checks.append(
            ("direct_payment", "direct_payments", "payment_id", ("Approved", "Payment Released"))
        )

    seen: set[tuple[str, str]] = set()
    for entity_type, table, id_col, statuses in checks:
        key = (entity_type, table)
        if key in seen:
            continue
        seen.add(key)
        n = _count_query(table, "status" if table != "payroll" else "COALESCE(workflow_status, salary_status)", statuses)
        if table == "payroll":
            n = _count_query(
                table,
                "COALESCE(workflow_status, salary_status)",
                statuses,
            )
        elif table == "worker_payroll_runs":
            n = _count_query(table, "workflow_status", statuses)
        if n > 0:
            pending.append(
                {
                    "entity_type": entity_type,
                    "table": table,
                    "count": n,
                    "statuses": list(statuses),
                    "for_user": user,
                }
            )

    conn.close()
    return pending


def workflow_status_counts() -> dict[str, int]:
    """Aggregate counts by canonical status across wired tables."""
    ensure_approval_workflow_schema()
    counts = {s: 0 for s in WORKFLOW_STATUSES}
    conn = get_conn()

    def _add_statuses(table: str, status_col: str) -> None:
        try:
            rows = conn.execute(
                f"SELECT {status_col} AS s, COUNT(*) AS c FROM {table} GROUP BY {status_col}"
            ).fetchall()
        except Exception:
            return
        for raw, c in rows:
            canon = normalize_status(raw)
            if canon in counts:
                counts[canon] += int(c or 0)

    for cfg in ENTITY_CONFIG.values():
        table = cfg["table"]
        col = cfg["status_column"]
        try:
            conn.execute(f"SELECT 1 FROM {table} LIMIT 1")
        except Exception:
            continue
        _add_statuses(table, col)

    conn.close()
    return counts


def pending_approval_count_for_role(role: str) -> int:
    return sum(item.get("count", 0) for item in get_pending_for_role("", role))
