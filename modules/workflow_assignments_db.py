"""Named maker / checker / approver assignments per module and optional project."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from modules.approval_workflow import ENTITY_TYPES, WORKFLOW_STATUSES
from modules.database import generate_id, get_conn

ASSIGNABLE_STEPS = (
    "Prepared",
    "Checked",
    "Approved",
    "Payment Released",
    "Paid",
)

STEP_BUSINESS_LABELS = {
    "Prepared": "Maker (Prepare / Submit)",
    "Checked": "Checker (Verify)",
    "Approved": "Approver (Final approval)",
    "Payment Released": "Payment release",
    "Paid": "Mark paid",
}

ENTITY_LABELS = {
    "staff_payroll": "Staff Payroll",
    "worker_payroll": "Worker Payroll",
    "subcontractor_bill": "Subcontractor Bill",
    "material_request": "Material Request",
    "purchase_order": "Purchase Order",
    "vendor_bill": "Vendor Bill",
    "site_expense": "Site Expense",
    "petty_cash": "Petty Cash (legacy)",
    "client_bill": "Client Bill",
    "direct_payment": "Direct Payment",
    "payment_voucher": "Payment Voucher",
    "petty_cash_fund_request": "Petty Cash Fund Request",
}

ENTITY_PROJECT_COLUMN: dict[str, str] = {
    "petty_cash_fund_request": "project_name",
    "site_expense": "project_name",
    "payment_voucher": "project_name",
    "petty_cash": "project_name",
    "material_request": "project_name",
    "client_bill": "project_name",
    "direct_payment": "project_name",
}


def _ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def ensure_workflow_assignments_schema(conn=None) -> None:
    own = conn is None
    if own:
        conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_step_assignees(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id TEXT UNIQUE NOT NULL,
            entity_type TEXT NOT NULL,
            workflow_step TEXT NOT NULL,
            username TEXT NOT NULL,
            project_name TEXT DEFAULT '',
            assigned_by TEXT,
            assigned_at TEXT,
            is_active INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_wf_assign_unique
        ON workflow_step_assignees(entity_type, workflow_step, username, project_name)
        """
    )
    if own:
        conn.commit()
        conn.close()


def list_active_usernames() -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT username FROM users
        WHERE COALESCE(is_disabled, 0) = 0
        ORDER BY username
        """
    ).fetchall()
    conn.close()
    return [str(r[0]) for r in rows if r[0]]


def list_project_names() -> list[str]:
    conn = get_conn()
    names: set[str] = set()
    for table, col in (
        ("projects", "project_name"),
        ("petty_cash_fund_requests", "project_name"),
    ):
        try:
            rows = conn.execute(
                f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL AND TRIM({col}) != ''"
            ).fetchall()
            names.update(str(r[0]).strip() for r in rows if r[0])
        except Exception:
            pass
    conn.close()
    return sorted(names)


def get_assignees(
    entity_type: str,
    workflow_step: str,
    project_name: str = "",
) -> list[str]:
    """Active usernames assigned to a workflow step (may be empty)."""
    ensure_workflow_assignments_schema()
    project = (project_name or "").strip()
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT username FROM workflow_step_assignees
        WHERE entity_type = ? AND workflow_step = ? AND project_name = ?
          AND is_active = 1
        ORDER BY username
        """,
        (entity_type, workflow_step, project),
    ).fetchall()
    conn.close()
    return [str(r[0]) for r in rows if r[0]]


def save_step_assignees(
    entity_type: str,
    workflow_step: str,
    usernames: list[str],
    *,
    project_name: str = "",
    actor: str = "",
) -> tuple[bool, str]:
    if entity_type not in ENTITY_TYPES:
        return False, f"Unknown module: {entity_type}"
    if workflow_step not in ASSIGNABLE_STEPS:
        return False, f"Invalid step: {workflow_step}"
    ensure_workflow_assignments_schema()
    project = (project_name or "").strip()
    cleaned = sorted({u.strip() for u in usernames if u and u.strip()})
    conn = get_conn()
    try:
        conn.execute(
            """
            DELETE FROM workflow_step_assignees
            WHERE entity_type = ? AND workflow_step = ? AND project_name = ?
            """,
            (entity_type, workflow_step, project),
        )
        for username in cleaned:
            conn.execute(
                """
                INSERT INTO workflow_step_assignees(
                    assignment_id, entity_type, workflow_step, username,
                    project_name, assigned_by, assigned_at, is_active
                ) VALUES(?,?,?,?,?,?,?,1)
                """,
                (
                    generate_id("WFA", "workflow_step_assignees"),
                    entity_type,
                    workflow_step,
                    username,
                    project,
                    actor,
                    _ts(),
                ),
            )
        conn.commit()
        scope = f" for project **{project}**" if project else " (all projects)"
        return True, f"Saved {len(cleaned)} assignee(s) for {ENTITY_LABELS.get(entity_type, entity_type)} · {STEP_BUSINESS_LABELS.get(workflow_step, workflow_step)}{scope}."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def load_assignments_table(
    entity_type: str | None = None,
    project_name: str | None = None,
) -> pd.DataFrame:
    ensure_workflow_assignments_schema()
    conn = get_conn()
    query = """
        SELECT entity_type, workflow_step, project_name, username, assigned_by, assigned_at
        FROM workflow_step_assignees
        WHERE is_active = 1
    """
    params: list[str] = []
    if entity_type:
        query += " AND entity_type = ?"
        params.append(entity_type)
    if project_name is not None:
        query += " AND project_name = ?"
        params.append((project_name or "").strip())
    query += " ORDER BY entity_type, workflow_step, project_name, username"
    df = pd.read_sql_query(query, conn, params=params or None)
    conn.close()
    if not df.empty:
        df = df.copy()
        df["module"] = df["entity_type"].map(lambda e: ENTITY_LABELS.get(e, e))
        df["step"] = df["workflow_step"].map(lambda s: STEP_BUSINESS_LABELS.get(s, s))
        df["project"] = df["project_name"].replace("", "All projects")
    return df


def resolve_entity_project(row: dict | None, entity_type: str) -> str:
    if not row:
        return ""
    col = ENTITY_PROJECT_COLUMN.get(entity_type)
    if not col:
        return ""
    return str(row.get(col) or "").strip()


def check_named_assignee(
    username: str,
    entity_type: str,
    workflow_step: str,
    project_name: str = "",
) -> tuple[bool, str]:
    """
    If assignees exist for this step, username must be listed.
    Project-specific list takes precedence; falls back to global (empty project).
    """
    project = (project_name or "").strip()
    assignees = get_assignees(entity_type, workflow_step, project)
    if not assignees and project:
        assignees = get_assignees(entity_type, workflow_step, "")
    if not assignees:
        return True, ""

    actor = (username or "").strip().lower()
    allowed = {u.lower() for u in assignees}
    if actor in allowed:
        return True, ""

    label = STEP_BUSINESS_LABELS.get(workflow_step, workflow_step)
    names = ", ".join(assignees)
    return False, (
        f"{label} is restricted to assigned user(s): {names}. "
        f"Your login ({username}) is not on that list."
    )


def assignment_summary_for_step(
    entity_type: str,
    workflow_step: str,
    project_name: str = "",
) -> str:
    project = (project_name or "").strip()
    assignees = get_assignees(entity_type, workflow_step, project)
    if not assignees and project:
        assignees = get_assignees(entity_type, workflow_step, "")
    if not assignees:
        return "Any user with the correct role may perform this step."
    label = STEP_BUSINESS_LABELS.get(workflow_step, workflow_step)
    return f"{label}: **{', '.join(assignees)}**"
