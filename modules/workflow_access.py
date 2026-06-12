"""Maker / Checker / Approver access — per user or employee (Flask staff.html model)."""

from __future__ import annotations

WORKFLOW_ACCESS_OPTIONS = (
    "",
    "Maker",
    "Checker",
    "Approver",
)

WORKFLOW_ACCESS_LABELS = {
    "": "Auto (use login role)",
    "Maker": "Maker — prepare / submit only",
    "Checker": "Checker — verify only",
    "Approver": "Approver — approve & payment steps",
}

# Canonical workflow step → required workflow access tag (when tag is set on user).
STEP_REQUIRED_ACCESS: dict[str, str] = {
    "Prepared": "Maker",
    "Checked": "Checker",
    "Approved": "Approver",
    "Payment Released": "Approver",
    "Paid": "Approver",
}


def load_workflow_role_options() -> list[str]:
    """Dropdown options for Employee Master and User Creation."""
    return list(WORKFLOW_ACCESS_OPTIONS)


def format_workflow_access(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return WORKFLOW_ACCESS_LABELS[""]
    return WORKFLOW_ACCESS_LABELS.get(text, text)


def get_user_workflow_access(username: str, full_name: str = "") -> str:
    """
    Resolve workflow tag: users.workflow_role, else linked employee work_flow,
    else employee name match.
    """
    from modules.database import get_conn
    from modules.user_account import ensure_user_account_schema

    ensure_user_account_schema()

    uname = (username or "").strip()
    name = (full_name or "").strip()
    if not uname and not name:
        return ""

    conn = get_conn()
    try:
        if uname:
            row = conn.execute(
                """
                SELECT COALESCE(workflow_role, ''), COALESCE(employee_id, ''), full_name
                FROM users WHERE LOWER(username) = LOWER(?)
                LIMIT 1
                """,
                (uname,),
            ).fetchone()
            if not row and name:
                row = conn.execute(
                    """
                    SELECT COALESCE(workflow_role, ''), COALESCE(employee_id, ''), full_name
                    FROM users WHERE LOWER(TRIM(full_name)) = LOWER(TRIM(?))
                    LIMIT 1
                    """,
                    (name,),
                ).fetchone()
            if row:
                tag = (row[0] or "").strip()
                if tag:
                    return tag
                emp_id = (row[1] or "").strip()
                lookup_name = name or (row[2] or "").strip()
                if emp_id:
                    erow = conn.execute(
                        "SELECT COALESCE(work_flow, '') FROM employees WHERE employee_id = ?",
                        (emp_id,),
                    ).fetchone()
                    if erow and (erow[0] or "").strip():
                        return str(erow[0]).strip()
                if lookup_name:
                    erow = conn.execute(
                        """
                        SELECT COALESCE(work_flow, '') FROM employees
                        WHERE LOWER(TRIM(employee_name)) = LOWER(TRIM(?))
                        LIMIT 1
                        """,
                        (lookup_name,),
                    ).fetchone()
                    if erow and (erow[0] or "").strip():
                        return str(erow[0]).strip()
        elif name:
            erow = conn.execute(
                """
                SELECT COALESCE(work_flow, '') FROM employees
                WHERE LOWER(TRIM(employee_name)) = LOWER(TRIM(?))
                LIMIT 1
                """,
                (name,),
            ).fetchone()
            if erow and (erow[0] or "").strip():
                return str(erow[0]).strip()
    except Exception:
        pass
    finally:
        conn.close()
    return ""


def check_workflow_access_for_step(
    username: str,
    erp_role: str,
    workflow_step: str,
    *,
    full_name: str = "",
) -> tuple[bool, str]:
    """
    When user has Maker/Checker/Approver tag, restrict to matching step only.
    Auto / empty tag → no extra restriction (ERP role rules apply).
    Super Admin / MD bypass.
    """
    from modules.roles import is_super_admin

    if is_super_admin(erp_role):
        return True, ""

    access = get_user_workflow_access(username, full_name)
    if not access or access.lower() == "auto":
        return True, ""

    required = STEP_REQUIRED_ACCESS.get(workflow_step)
    if not required:
        return True, ""

    if access == required:
        return True, ""

    label = WORKFLOW_ACCESS_LABELS.get(access, access)
    need = WORKFLOW_ACCESS_LABELS.get(required, required)
    return False, (
        f"Your workflow role is **{label}**. "
        f"This step requires **{need}**. Ask Super Admin to update Users or Employee Master."
    )
