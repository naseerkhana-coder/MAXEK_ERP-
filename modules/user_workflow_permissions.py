"""Per-user, per-module Maker / Checker / Approver / Handler permissions."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from modules.approval_workflow import ENTITY_TYPES
from modules.database import generate_id, get_conn

CAPABILITY_MAKER = "maker"
CAPABILITY_CHECKER = "checker"
CAPABILITY_APPROVER = "approver"
CAPABILITY_HANDLER = "handler"

CAPABILITY_LABELS = {
    CAPABILITY_MAKER: "Maker (create / submit)",
    CAPABILITY_CHECKER: "Checker (verify)",
    CAPABILITY_APPROVER: "Approver (final sign-off)",
    CAPABILITY_HANDLER: "Handler (MD follow-up / site / accounts)",
}

# Modules shown in settings (workflow-enabled + common site modules).
CONFIGURABLE_MODULES: dict[str, str] = {
    "petty_cash_fund_request": "Petty Cash — Fund Request",
    "petty_cash": "Petty Cash — Legacy Request",
    "site_expense": "Petty Cash — Site Expense",
    "payment_voucher": "Payment Voucher",
    "direct_payment": "Direct Payment",
    "vendor_bill": "Vendor Bill",
    "material_request": "Material Request",
    "purchase_order": "Purchase Order",
    "staff_payroll": "Staff Payroll",
    "worker_payroll": "Worker Payroll",
    "subcontractor_bill": "Subcontractor Bill",
    "client_bill": "Client Bill",
    "dpr": "Daily Progress (DPR)",
    "timesheet": "Timesheet / Attendance",
}

STEP_TO_CAPABILITY = {
    "Prepared": CAPABILITY_MAKER,
    "Checked": CAPABILITY_CHECKER,
    "Approved": CAPABILITY_APPROVER,
    "Payment Released": CAPABILITY_APPROVER,
    "Paid": CAPABILITY_APPROVER,
}


def _ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def ensure_user_workflow_permissions_schema(conn=None) -> None:
    own = conn is None
    if own:
        conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_module_workflow_permissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            permission_id TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            module_key TEXT NOT NULL,
            capability TEXT NOT NULL,
            assigned_by TEXT,
            assigned_at TEXT,
            is_active INTEGER DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_mod_cap
        ON user_module_workflow_permissions(user_id, module_key, capability)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_follow_ups(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follow_up_id TEXT UNIQUE NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            assigned_to_username TEXT NOT NULL,
            assigned_by TEXT,
            assigned_at TEXT,
            note TEXT,
            status TEXT DEFAULT 'Open',
            closed_at TEXT
        )
        """
    )
    if own:
        conn.commit()
        conn.close()


def _valid_module(module_key: str) -> bool:
    return module_key in CONFIGURABLE_MODULES or module_key in ENTITY_TYPES


def list_users_for_permissions() -> list[dict]:
    ensure_user_workflow_permissions_schema()
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT user_id, username, full_name, role
        FROM users
        WHERE COALESCE(is_disabled, 0) = 0
        ORDER BY full_name, username
        """
    ).fetchall()
    conn.close()
    return [
        {
            "user_id": r[0],
            "username": r[1],
            "full_name": r[2],
            "role": r[3],
            "label": f"{r[2]} ({r[1]}) — {r[3]}",
        }
        for r in rows
    ]


def load_user_permissions(user_id: str) -> dict[str, list[str]]:
    ensure_user_workflow_permissions_schema()
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT module_key, capability FROM user_module_workflow_permissions
        WHERE user_id = ? AND is_active = 1
        ORDER BY module_key, capability
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    out: dict[str, list[str]] = {
        CAPABILITY_MAKER: [],
        CAPABILITY_CHECKER: [],
        CAPABILITY_APPROVER: [],
        CAPABILITY_HANDLER: [],
    }
    for mod, cap in rows:
        cap = (cap or "").lower()
        if cap in out and mod not in out[cap]:
            out[cap].append(mod)
    return out


def save_user_permissions(
    user_id: str,
    username: str,
    *,
    maker_modules: list[str],
    checker_modules: list[str],
    approver_modules: list[str],
    handler_modules: list[str],
    actor: str = "",
) -> tuple[bool, str]:
    ensure_user_workflow_permissions_schema()
    conn = get_conn()
    try:
        conn.execute(
            "DELETE FROM user_module_workflow_permissions WHERE user_id = ?",
            (user_id,),
        )
        count = _insert_permission_rows(
            conn,
            user_id,
            username,
            maker_modules,
            checker_modules,
            approver_modules,
            handler_modules,
            actor,
        )
        conn.commit()
        return True, f"Saved {count} module permission(s) for **{username}**."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def _insert_permission_rows(
    conn,
    user_id: str,
    username: str,
    maker_modules: list[str],
    checker_modules: list[str],
    approver_modules: list[str],
    handler_modules: list[str],
    actor: str,
) -> int:
    batches = [
        (CAPABILITY_MAKER, maker_modules),
        (CAPABILITY_CHECKER, checker_modules),
        (CAPABILITY_APPROVER, approver_modules),
        (CAPABILITY_HANDLER, handler_modules),
    ]
    count = 0
    for capability, modules in batches:
        for mod in sorted({m.strip() for m in modules if m and m.strip()}):
            if not _valid_module(mod):
                continue
            conn.execute(
                """
                INSERT INTO user_module_workflow_permissions(
                    permission_id, user_id, username, module_key, capability,
                    assigned_by, assigned_at, is_active
                ) VALUES(?,?,?,?,?,?,?,1)
                """,
                (
                    generate_id(
                        "UMP",
                        "user_module_workflow_permissions",
                        conn=conn,
                    ),
                    user_id,
                    username,
                    mod,
                    capability,
                    actor,
                    _ts(),
                ),
            )
            count += 1
    return count


def add_modules_for_capability(
    user_id: str,
    username: str,
    capability: str,
    modules: list[str],
    *,
    actor: str = "",
) -> tuple[bool, str]:
    """Add one or more modules for a role without removing existing ones."""
    cap = (capability or "").lower()
    if cap not in CAPABILITY_LABELS:
        return False, f"Unknown role: {capability}"

    mods = sorted({m.strip() for m in modules if m and m.strip() and _valid_module(m.strip())})
    if not mods:
        return False, "Select at least one valid module to add."

    ensure_user_workflow_permissions_schema()
    conn = get_conn()
    try:
        added = 0
        for mod in mods:
            row = conn.execute(
                """
                SELECT 1 FROM user_module_workflow_permissions
                WHERE user_id = ? AND module_key = ? AND capability = ? AND is_active = 1
                LIMIT 1
                """,
                (user_id, mod, cap),
            ).fetchone()
            if row:
                continue
            conn.execute(
                """
                INSERT INTO user_module_workflow_permissions(
                    permission_id, user_id, username, module_key, capability,
                    assigned_by, assigned_at, is_active
                ) VALUES(?,?,?,?,?,?,?,1)
                """,
                (
                    generate_id(
                        "UMP",
                        "user_module_workflow_permissions",
                        conn=conn,
                    ),
                    user_id,
                    username,
                    mod,
                    cap,
                    actor,
                    _ts(),
                ),
            )
            added += 1
        conn.commit()
        label = CAPABILITY_LABELS[cap]
        if added == 0:
            return True, f"No new modules added — **{username}** already has those **{label}** permissions."
        return True, f"Added {added} module(s) as **{label}** for **{username}**."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def remove_modules_for_capability(
    user_id: str,
    capability: str,
    modules: list[str],
) -> tuple[bool, str]:
    """Remove selected modules for a role; other roles for the same module are kept."""
    cap = (capability or "").lower()
    if cap not in CAPABILITY_LABELS:
        return False, f"Unknown role: {capability}"

    mods = sorted({m.strip() for m in modules if m and m.strip()})
    if not mods:
        return False, "Select at least one module to remove."

    ensure_user_workflow_permissions_schema()
    conn = get_conn()
    try:
        removed = 0
        for mod in mods:
            cur = conn.execute(
                """
                DELETE FROM user_module_workflow_permissions
                WHERE user_id = ? AND module_key = ? AND capability = ?
                """,
                (user_id, mod, cap),
            )
            removed += cur.rowcount
        conn.commit()
        label = CAPABILITY_LABELS[cap]
        if removed == 0:
            return True, f"No **{label}** permissions were removed (nothing matched)."
        return True, f"Removed {removed} **{label}** module permission(s)."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def clear_capability_permissions(user_id: str, capability: str) -> tuple[bool, str]:
    """Remove all modules for one role (Maker, Checker, etc.)."""
    cap = (capability or "").lower()
    if cap not in CAPABILITY_LABELS:
        return False, f"Unknown role: {capability}"
    ensure_user_workflow_permissions_schema()
    conn = get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM user_module_workflow_permissions WHERE user_id = ? AND capability = ?",
            (user_id, cap),
        )
        conn.commit()
        label = CAPABILITY_LABELS[cap]
        return True, f"Cleared all **{label}** permissions ({cur.rowcount} removed)."
    except Exception as exc:
        conn.rollback()
        return False, str(exc)
    finally:
        conn.close()


def user_has_any_module_permissions(username: str) -> bool:
    ensure_user_workflow_permissions_schema()
    conn = get_conn()
    row = conn.execute(
        """
        SELECT COUNT(*) FROM user_module_workflow_permissions
        WHERE LOWER(username) = LOWER(?) AND is_active = 1
        """,
        ((username or "").strip(),),
    ).fetchone()
    conn.close()
    return int(row[0] or 0) > 0


def user_has_module_capability(
    username: str,
    module_key: str,
    capability: str,
) -> bool:
    ensure_user_workflow_permissions_schema()
    conn = get_conn()
    row = conn.execute(
        """
        SELECT 1 FROM user_module_workflow_permissions
        WHERE LOWER(username) = LOWER(?)
          AND module_key = ?
          AND capability = ?
          AND is_active = 1
        LIMIT 1
        """,
        ((username or "").strip(), module_key, capability.lower()),
    ).fetchone()
    conn.close()
    return row is not None


def check_user_module_permission(
    username: str,
    module_key: str,
    workflow_step: str,
    erp_role: str,
) -> tuple[bool, str]:
    """Enforce per-module permissions when configured for this user."""
    from modules.roles import is_super_admin

    if is_super_admin(erp_role):
        return True, ""

    if not user_has_any_module_permissions(username):
        return True, ""

    capability = STEP_TO_CAPABILITY.get(workflow_step)
    if not capability:
        return True, ""

    if user_has_module_capability(username, module_key, capability):
        return True, ""

    mod_label = CONFIGURABLE_MODULES.get(module_key, module_key)
    cap_label = CAPABILITY_LABELS.get(capability, capability)
    return False, (
        f"You are not assigned as **{cap_label}** for **{mod_label}**. "
        "Ask Super Admin to update **Maker–Checker Setup**."
    )


def list_handlers_for_module(module_key: str) -> list[str]:
    ensure_user_workflow_permissions_schema()
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT DISTINCT username FROM user_module_workflow_permissions
        WHERE module_key = ? AND capability = ? AND is_active = 1
        ORDER BY username
        """,
        (module_key, CAPABILITY_HANDLER),
    ).fetchall()
    conn.close()
    handlers = [str(r[0]) for r in rows if r[0]]
    if handlers:
        return handlers
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT DISTINCT username FROM user_module_workflow_permissions
        WHERE module_key = ? AND capability IN (?, ?) AND is_active = 1
        ORDER BY username
        """,
        (module_key, CAPABILITY_MAKER, CAPABILITY_CHECKER),
    ).fetchall()
    conn.close()
    return [str(r[0]) for r in rows if r[0]]


def create_follow_up(
    entity_type: str,
    entity_id: str,
    assigned_to_username: str,
    *,
    assigned_by: str = "",
    note: str = "",
    conn=None,
) -> None:
    ensure_user_workflow_permissions_schema()
    own = conn is None
    if own:
        conn = get_conn()
    conn.execute(
        """
        INSERT INTO workflow_follow_ups(
            follow_up_id, entity_type, entity_id, assigned_to_username,
            assigned_by, assigned_at, note, status
        ) VALUES(?,?,?,?,?,?,?,'Open')
        """,
        (
            generate_id("WFU", "workflow_follow_ups", conn=conn),
            entity_type,
            entity_id,
            assigned_to_username,
            assigned_by,
            _ts(),
            note or "",
        ),
    )
    if own:
        conn.commit()
        conn.close()


def load_permissions_matrix() -> pd.DataFrame:
    ensure_user_workflow_permissions_schema()
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT u.full_name, p.username, p.module_key, p.capability, p.assigned_by, p.assigned_at
        FROM user_module_workflow_permissions p
        LEFT JOIN users u ON u.user_id = p.user_id
        WHERE p.is_active = 1
        ORDER BY u.full_name, p.module_key, p.capability
        """,
        conn,
    )
    conn.close()
    if not df.empty:
        df = df.copy()
        df["module"] = df["module_key"].map(
            lambda m: CONFIGURABLE_MODULES.get(m, m)
        )
        df["access"] = df["capability"].map(
            lambda c: CAPABILITY_LABELS.get(c, c)
        )
    return df


def load_open_follow_ups(username: str | None = None) -> pd.DataFrame:
    ensure_user_workflow_permissions_schema()
    conn = get_conn()
    query = """
        SELECT follow_up_id, entity_type, entity_id, assigned_to_username,
               assigned_by, assigned_at, note, status
        FROM workflow_follow_ups
        WHERE status = 'Open'
    """
    params: tuple = ()
    if username:
        query += " AND LOWER(assigned_to_username) = LOWER(?)"
        params = (username.strip(),)
    query += " ORDER BY id DESC"
    df = pd.read_sql_query(query, conn, params=params or None)
    conn.close()
    return df
