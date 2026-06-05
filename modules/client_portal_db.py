"""Client portal — schema, auth, scoped queries, bill workflow, and audit."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

from modules.database import BASE_DIR, generate_id, get_conn
from modules.password_security import hash_password, verify_password

CLIENT_ROLE = "Client"
MAX_LOGIN_FAILURES = 5
LOCKOUT_MINUTES = 15

CLIENT_REVIEW_PENDING = "Pending"
CLIENT_REVIEW_APPROVED = "Approved"
CLIENT_REVIEW_REJECTED = "Rejected"

BILL_STATUS_PENDING_CLIENT = "Pending Client Review"
BILL_STATUS_CLIENT_APPROVED = "Client Approved"
BILL_STATUS_CLIENT_REJECTED = "Client Rejected"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _local_ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def _add_column_if_missing(cur, table: str, column: str, col_type: str) -> None:
    from modules.database import _columns

    if column not in _columns(cur, table):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def ensure_client_portal_schema(conn=None) -> None:
    own = conn is None
    if own:
        conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS client_portal_users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portal_user_id TEXT UNIQUE NOT NULL,
            client_id TEXT NOT NULL,
            display_name TEXT,
            email TEXT,
            mobile TEXT,
            password_hash TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            failed_login_count INTEGER DEFAULT 0,
            locked_until TEXT,
            created_at TEXT NOT NULL,
            last_login_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS client_project_assignments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id TEXT UNIQUE NOT NULL,
            client_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            project_name TEXT NOT NULL,
            assigned_by TEXT,
            assigned_at TEXT NOT NULL,
            UNIQUE(client_id, project_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS client_bill_approvals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            approval_id TEXT UNIQUE NOT NULL,
            bill_id TEXT NOT NULL,
            client_id TEXT NOT NULL,
            action TEXT NOT NULL,
            comment TEXT,
            portal_user_id TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS client_comments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id TEXT UNIQUE NOT NULL,
            client_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            project_id TEXT,
            body TEXT NOT NULL,
            portal_user_id TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS client_portal_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portal_user_id TEXT,
            client_id TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            details TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    for col, typ in (
        ("client_review_status", "TEXT"),
        ("client_review_comment", "TEXT"),
        ("client_reviewed_at", "TEXT"),
        ("client_reviewed_by", "TEXT"),
        ("submitted_for_client_at", "TEXT"),
        ("submitted_for_client_by", "TEXT"),
    ):
        _add_column_if_missing(cur, "client_bills", col, typ)

    _add_column_if_missing(cur, "projects", "progress_percent", "REAL DEFAULT 0")

    if own:
        conn.commit()
        conn.close()


def log_portal_audit(
    action: str,
    *,
    portal_user_id: str = "",
    client_id: str = "",
    entity_type: str = "",
    entity_id: str = "",
    details: str | dict = "",
    ip_address: str = "",
    user_agent: str = "",
    conn=None,
) -> None:
    own = conn is None
    if own:
        conn = get_conn()
    ensure_client_portal_schema(conn)
    detail_str = json.dumps(details) if isinstance(details, dict) else (details or "")
    conn.execute(
        """
        INSERT INTO client_portal_audit(
            portal_user_id, client_id, action, entity_type, entity_id,
            details, ip_address, user_agent, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            portal_user_id or "",
            client_id or "",
            action,
            entity_type or "",
            entity_id or "",
            detail_str,
            ip_address or "",
            user_agent or "",
            _local_ts(),
        ),
    )
    if own:
        conn.commit()
        conn.close()


def _normalize_login_id(value: str) -> str:
    return (value or "").strip().lower()


def _portal_user_locked(row) -> tuple[bool, str]:
    locked_until = row.get("locked_until") if hasattr(row, "get") else None
    if not locked_until:
        return False, ""
    try:
        until = datetime.strptime(locked_until, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return False, ""
    if _utc_now() < until:
        return True, f"Account locked until {locked_until}. Try again later."
    return False, ""


def authenticate_portal_user(login_id: str, password: str) -> tuple[dict | None, str]:
    """Login with email or mobile + password."""
    lid = _normalize_login_id(login_id)
    if not lid or not password:
        return None, "Enter email or mobile and password."

    conn = get_conn()
    ensure_client_portal_schema(conn)
    row = conn.execute(
        """
        SELECT portal_user_id, client_id, display_name, email, mobile, password_hash,
               COALESCE(is_active, 1) AS is_active,
               COALESCE(failed_login_count, 0) AS failed_login_count,
               locked_until
        FROM client_portal_users
        WHERE LOWER(COALESCE(email, '')) = ? OR REPLACE(COALESCE(mobile, ''), ' ', '') = REPLACE(?, ' ', '')
        LIMIT 1
        """,
        (lid, login_id.strip()),
    ).fetchone()
    if not row:
        log_portal_audit("login_failed", details={"login_id": lid}, conn=conn)
        conn.commit()
        conn.close()
        return None, "Invalid credentials."

    keys = (
        "portal_user_id",
        "client_id",
        "display_name",
        "email",
        "mobile",
        "password_hash",
        "is_active",
        "failed_login_count",
        "locked_until",
    )
    user = dict(zip(keys, row))
    if not user["is_active"]:
        conn.close()
        return None, "This portal account is disabled."

    locked, msg = _portal_user_locked(user)
    if locked:
        conn.close()
        return None, msg

    if not verify_password(password, user["password_hash"]):
        fails = int(user["failed_login_count"] or 0) + 1
        locked_until = ""
        if fails >= MAX_LOGIN_FAILURES:
            locked_until = (_utc_now() + timedelta(minutes=LOCKOUT_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
            fails = MAX_LOGIN_FAILURES
        conn.execute(
            """
            UPDATE client_portal_users
            SET failed_login_count = ?, locked_until = ?
            WHERE portal_user_id = ?
            """,
            (fails, locked_until or None, user["portal_user_id"]),
        )
        log_portal_audit(
            "login_failed",
            portal_user_id=user["portal_user_id"],
            client_id=user["client_id"],
            details={"attempt": fails},
            conn=conn,
        )
        conn.commit()
        conn.close()
        if locked_until:
            return None, f"Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes."
        return None, "Invalid credentials."

    conn.execute(
        """
        UPDATE client_portal_users
        SET failed_login_count = 0, locked_until = NULL, last_login_at = ?
        WHERE portal_user_id = ?
        """,
        (_local_ts(), user["portal_user_id"]),
    )
    client_row = conn.execute(
        "SELECT client_name FROM clients WHERE client_id = ?",
        (user["client_id"],),
    ).fetchone()
    client_name = client_row[0] if client_row else ""
    log_portal_audit(
        "login",
        portal_user_id=user["portal_user_id"],
        client_id=user["client_id"],
        conn=conn,
    )
    conn.commit()
    conn.close()
    user["client_name"] = client_name
    user.pop("password_hash", None)
    return user, ""


def create_portal_user(
    client_id: str,
    *,
    email: str = "",
    mobile: str = "",
    display_name: str = "",
    password: str,
    actor: str = "",
) -> tuple[str | None, str]:
    if not client_id:
        return None, "Select a client."
    if not email.strip() and not mobile.strip():
        return None, "Email or mobile is required."
    if not password:
        return None, "Password is required."

    conn = get_conn()
    ensure_client_portal_schema(conn)
    portal_user_id = generate_id("CPU", "client_portal_users", "portal_user_id", conn=conn)
    try:
        conn.execute(
            """
            INSERT INTO client_portal_users(
                portal_user_id, client_id, display_name, email, mobile,
                password_hash, is_active, created_at
            ) VALUES(?,?,?,?,?,?,1,?)
            """,
            (
                portal_user_id,
                client_id,
                display_name.strip() or email.strip() or mobile.strip(),
                email.strip(),
                mobile.strip(),
                hash_password(password),
                _local_ts(),
            ),
        )
        log_portal_audit(
            "portal_user_created",
            client_id=client_id,
            entity_type="portal_user",
            entity_id=portal_user_id,
            details={"actor": actor, "email": email.strip(), "mobile": mobile.strip()},
            conn=conn,
        )
        conn.commit()
        return portal_user_id, ""
    except Exception as exc:
        conn.rollback()
        return None, str(exc)
    finally:
        conn.close()


def list_portal_users(client_id: str | None = None):
    import pandas as pd

    conn = get_conn()
    ensure_client_portal_schema(conn)
    if client_id:
        df = pd.read_sql_query(
            """
            SELECT portal_user_id, client_id, display_name, email, mobile,
                   COALESCE(is_active, 1) AS is_active, last_login_at, created_at
            FROM client_portal_users WHERE client_id = ?
            ORDER BY id DESC
            """,
            conn,
            params=(client_id,),
        )
    else:
        df = pd.read_sql_query(
            """
            SELECT u.portal_user_id, u.client_id, c.client_name, u.display_name,
                   u.email, u.mobile, COALESCE(u.is_active, 1) AS is_active,
                   u.last_login_at, u.created_at
            FROM client_portal_users u
            LEFT JOIN clients c ON c.client_id = u.client_id
            ORDER BY u.id DESC
            """,
            conn,
        )
    conn.close()
    return df


def assign_client_project(
    client_id: str,
    project_id: str,
    project_name: str,
    *,
    assigned_by: str = "",
) -> tuple[str | None, str]:
    if not client_id or not project_id:
        return None, "Client and project are required."
    conn = get_conn()
    ensure_client_portal_schema(conn)
    assignment_id = generate_id("CPA", "client_project_assignments", "assignment_id", conn=conn)
    try:
        conn.execute(
            """
            INSERT INTO client_project_assignments(
                assignment_id, client_id, project_id, project_name, assigned_by, assigned_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (assignment_id, client_id, project_id, project_name, assigned_by or "", _local_ts()),
        )
        log_portal_audit(
            "project_assigned",
            client_id=client_id,
            entity_type="project",
            entity_id=project_id,
            details={"project_name": project_name, "assigned_by": assigned_by},
            conn=conn,
        )
        conn.commit()
        return assignment_id, ""
    except Exception:
        conn.rollback()
        return None, "This project is already assigned to the client."
    finally:
        conn.close()


def remove_client_project_assignment(assignment_id: str, *, actor: str = "") -> bool:
    conn = get_conn()
    ensure_client_portal_schema(conn)
    row = conn.execute(
        "SELECT client_id, project_id FROM client_project_assignments WHERE assignment_id = ?",
        (assignment_id,),
    ).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute("DELETE FROM client_project_assignments WHERE assignment_id = ?", (assignment_id,))
    log_portal_audit(
        "project_unassigned",
        client_id=row[0],
        entity_type="project",
        entity_id=row[1],
        details={"actor": actor},
        conn=conn,
    )
    conn.commit()
    conn.close()
    return True


def list_assignments(client_id: str | None = None):
    import pandas as pd

    conn = get_conn()
    ensure_client_portal_schema(conn)
    if client_id:
        df = pd.read_sql_query(
            """
            SELECT assignment_id, client_id, project_id, project_name, assigned_by, assigned_at
            FROM client_project_assignments WHERE client_id = ?
            ORDER BY assigned_at DESC
            """,
            conn,
            params=(client_id,),
        )
    else:
        df = pd.read_sql_query(
            """
            SELECT a.assignment_id, a.client_id, c.client_name, a.project_id,
                   a.project_name, a.assigned_by, a.assigned_at
            FROM client_project_assignments a
            LEFT JOIN clients c ON c.client_id = a.client_id
            ORDER BY a.assigned_at DESC
            """,
            conn,
        )
    conn.close()
    return df


def _client_record(client_id: str, conn=None) -> tuple[str, str]:
    own = conn is None
    if own:
        conn = get_conn()
    row = conn.execute(
        "SELECT client_id, client_name FROM clients WHERE client_id = ?",
        (client_id,),
    ).fetchone()
    if own:
        conn.close()
    return (row[0], row[1]) if row else ("", "")


def client_assigned_project_ids(client_id: str, conn=None) -> set[str]:
    own = conn is None
    if own:
        conn = get_conn()
    ensure_client_portal_schema(conn)
    rows = conn.execute(
        "SELECT project_id FROM client_project_assignments WHERE client_id = ?",
        (client_id,),
    ).fetchall()
    ids = {r[0] for r in rows}
    if not ids:
        _, client_name = _client_record(client_id, conn)
        if client_name:
            fallback = conn.execute(
                "SELECT project_id FROM projects WHERE client_name = ?",
                (client_name,),
            ).fetchall()
            ids = {r[0] for r in fallback if r[0]}
    if own:
        conn.close()
    return ids


def client_assigned_project_names(client_id: str, conn=None) -> set[str]:
    own = conn is None
    if own:
        conn = get_conn()
    ensure_client_portal_schema(conn)
    rows = conn.execute(
        "SELECT project_name FROM client_project_assignments WHERE client_id = ?",
        (client_id,),
    ).fetchall()
    names = {r[0] for r in rows if r[0]}
    if not names:
        _, client_name = _client_record(client_id, conn)
        if client_name:
            fallback = conn.execute(
                "SELECT project_name FROM projects WHERE client_name = ?",
                (client_name,),
            ).fetchall()
            names = {r[0] for r in fallback if r[0]}
    if own:
        conn.close()
    return names


def project_belongs_to_client(client_id: str, project_id: str = "", project_name: str = "") -> bool:
    assigned = client_assigned_project_ids(client_id)
    if not assigned:
        return False
    if project_id and project_id in assigned:
        return True
    if project_name:
        names = client_assigned_project_names(client_id)
        return project_name in names
    return False


def load_client_projects(client_id: str):
    import pandas as pd

    conn = get_conn()
    ensure_client_portal_schema(conn)
    df = pd.read_sql_query(
        """
        SELECT p.project_id, p.project_name, p.client_name, p.location, p.status,
               p.start_date, p.end_date, COALESCE(p.progress_percent, 0) AS progress_percent,
               p.budget, p.amount
        FROM client_project_assignments a
        INNER JOIN projects p ON p.project_id = a.project_id
        WHERE a.client_id = ?
        ORDER BY p.project_name
        """,
        conn,
        params=(client_id,),
    )
    conn.close()
    if df.empty:
        return df
    for idx, row in df.iterrows():
        if float(row.get("progress_percent") or 0) <= 0:
            df.at[idx, "progress_percent"] = compute_project_progress_percent(
                row["project_id"], row["project_name"]
            )
    return df


def compute_project_progress_percent(project_id: str, project_name: str) -> float:
    """Estimate % complete from BOQ / DPR when progress_percent is not set."""
    conn = get_conn()
    boq = conn.execute(
        """
        SELECT COALESCE(SUM(quantity), 0), COALESCE(SUM(
            CASE WHEN quantity > 0 THEN quantity ELSE 0 END
        ), 0)
        FROM project_boq_items WHERE project_id = ? OR project_name = ?
        """,
        (project_id, project_name),
    ).fetchone()
    done = conn.execute(
        """
        SELECT COALESCE(SUM(done_quantity), 0), COALESCE(SUM(total_boq_quantity), 0)
        FROM dpr_reports WHERE project_id = ? OR project_name = ?
        """,
        (project_id, project_name),
    ).fetchone()
    conn.close()
    total_boq = float(boq[0] or 0) if boq else 0
    if total_boq <= 0 and done:
        total_boq = float(done[1] or 0)
    done_qty = float(done[0] or 0) if done else 0
    if total_boq <= 0:
        return 0.0
    return round(min(100.0, (done_qty / total_boq) * 100.0), 1)


def load_client_invoices(client_id: str, client_name: str):
    import pandas as pd

    names = client_assigned_project_names(client_id)
    if not names:
        return pd.DataFrame()
    conn = get_conn()
    placeholders = ",".join("?" * len(names))
    df = pd.read_sql_query(
        f"""
        SELECT bill_id, bill_no, bill_date, project_name, total_amount,
               COALESCE(grand_total, total_amount) AS grand_total, status,
               client_review_status
        FROM client_bills
        WHERE client_name = ? AND project_name IN ({placeholders})
        ORDER BY id DESC
        """,
        conn,
        params=(client_name, *sorted(names)),
    )
    conn.close()
    return df


def load_bills_pending_client_review(client_id: str, client_name: str):
    import pandas as pd

    names = client_assigned_project_names(client_id)
    if not names:
        return pd.DataFrame()
    conn = get_conn()
    placeholders = ",".join("?" * len(names))
    df = pd.read_sql_query(
        f"""
        SELECT bill_id, bill_no, bill_date, project_name, total_amount,
               COALESCE(grand_total, total_amount) AS grand_total,
               client_review_status, client_review_comment, status, remarks
        FROM client_bills
        WHERE client_name = ?
          AND project_name IN ({placeholders})
          AND (
            client_review_status = ?
            OR status = ?
          )
        ORDER BY submitted_for_client_at DESC, id DESC
        """,
        conn,
        params=(
            client_name,
            *sorted(names),
            CLIENT_REVIEW_PENDING,
            BILL_STATUS_PENDING_CLIENT,
        ),
    )
    conn.close()
    return df


def get_client_bill_for_portal(client_id: str, bill_id: str, client_name: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        """
        SELECT bill_id, bill_no, bill_date, client_name, project_name,
               total_amount, grand_total, status, client_review_status, remarks
        FROM client_bills WHERE bill_id = ?
        """,
        (bill_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    bill = {
        "bill_id": row[0],
        "bill_no": row[1],
        "bill_date": row[2],
        "client_name": row[3],
        "project_name": row[4],
        "total_amount": row[5],
        "grand_total": row[6] or row[5],
        "status": row[7],
        "client_review_status": row[8],
        "remarks": row[9],
    }
    if bill["client_name"] != client_name:
        return None
    names = client_assigned_project_names(client_id)
    if bill["project_name"] not in names:
        return None
    return bill


def submit_bill_for_client_review(bill_id: str, *, actor: str = "") -> tuple[bool, str]:
    conn = get_conn()
    ensure_client_portal_schema(conn)
    row = conn.execute(
        "SELECT bill_id, client_name, project_name, status, client_review_status FROM client_bills WHERE bill_id = ?",
        (bill_id,),
    ).fetchone()
    if not row:
        conn.close()
        return False, "Bill not found."
    if row[4] == CLIENT_REVIEW_PENDING:
        conn.close()
        return False, "Bill is already pending client review."
    conn.execute(
        """
        UPDATE client_bills SET
            status = ?,
            client_review_status = ?,
            submitted_for_client_at = ?,
            submitted_for_client_by = ?,
            client_review_comment = NULL,
            client_reviewed_at = NULL,
            client_reviewed_by = NULL
        WHERE bill_id = ?
        """,
        (
            BILL_STATUS_PENDING_CLIENT,
            CLIENT_REVIEW_PENDING,
            _local_ts(),
            actor or "",
            bill_id,
        ),
    )
    conn.commit()
    conn.close()
    return True, ""


def approve_client_bill(
    bill_id: str,
    client_id: str,
    client_name: str,
    *,
    portal_user_id: str = "",
    display_name: str = "",
    comment: str = "",
) -> tuple[bool, str]:
    bill = get_client_bill_for_portal(client_id, bill_id, client_name)
    if not bill:
        return False, "Bill not found or access denied."
    if bill.get("client_review_status") != CLIENT_REVIEW_PENDING:
        return False, "This bill is not awaiting your review."

    conn = get_conn()
    ensure_client_portal_schema(conn)
    conn.execute(
        """
        UPDATE client_bills SET
            status = ?,
            client_review_status = ?,
            client_review_comment = ?,
            client_reviewed_at = ?,
            client_reviewed_by = ?
        WHERE bill_id = ?
        """,
        (
            BILL_STATUS_CLIENT_APPROVED,
            CLIENT_REVIEW_APPROVED,
            (comment or "").strip(),
            _local_ts(),
            display_name or portal_user_id,
            bill_id,
        ),
    )
    approval_id = generate_id("CBA", "client_bill_approvals", "approval_id", conn=conn)
    conn.execute(
        """
        INSERT INTO client_bill_approvals(
            approval_id, bill_id, client_id, action, comment, portal_user_id, created_at
        ) VALUES(?,?,?,?,?,?,?)
        """,
        (
            approval_id,
            bill_id,
            client_id,
            "approved",
            (comment or "").strip(),
            portal_user_id,
            _local_ts(),
        ),
    )
    log_portal_audit(
        "bill_approved",
        portal_user_id=portal_user_id,
        client_id=client_id,
        entity_type="client_bill",
        entity_id=bill_id,
        details={"comment": comment},
        conn=conn,
    )
    conn.commit()
    conn.close()
    return True, ""


def reject_client_bill(
    bill_id: str,
    client_id: str,
    client_name: str,
    *,
    portal_user_id: str = "",
    display_name: str = "",
    comment: str = "",
) -> tuple[bool, str]:
    if not (comment or "").strip():
        return False, "A comment is required when rejecting a bill."
    bill = get_client_bill_for_portal(client_id, bill_id, client_name)
    if not bill:
        return False, "Bill not found or access denied."
    if bill.get("client_review_status") != CLIENT_REVIEW_PENDING:
        return False, "This bill is not awaiting your review."

    conn = get_conn()
    ensure_client_portal_schema(conn)
    conn.execute(
        """
        UPDATE client_bills SET
            status = ?,
            client_review_status = ?,
            client_review_comment = ?,
            client_reviewed_at = ?,
            client_reviewed_by = ?
        WHERE bill_id = ?
        """,
        (
            BILL_STATUS_CLIENT_REJECTED,
            CLIENT_REVIEW_REJECTED,
            comment.strip(),
            _local_ts(),
            display_name or portal_user_id,
            bill_id,
        ),
    )
    approval_id = generate_id("CBA", "client_bill_approvals", "approval_id", conn=conn)
    conn.execute(
        """
        INSERT INTO client_bill_approvals(
            approval_id, bill_id, client_id, action, comment, portal_user_id, created_at
        ) VALUES(?,?,?,?,?,?,?)
        """,
        (
            approval_id,
            bill_id,
            client_id,
            "rejected",
            comment.strip(),
            portal_user_id,
            _local_ts(),
        ),
    )
    log_portal_audit(
        "bill_rejected",
        portal_user_id=portal_user_id,
        client_id=client_id,
        entity_type="client_bill",
        entity_id=bill_id,
        details={"comment": comment},
        conn=conn,
    )
    conn.commit()
    conn.close()
    return True, ""


def add_client_comment(
    client_id: str,
    entity_type: str,
    entity_id: str,
    body: str,
    *,
    project_id: str = "",
    portal_user_id: str = "",
) -> tuple[str | None, str]:
    text = (body or "").strip()
    if not text:
        return None, "Comment cannot be empty."
    conn = get_conn()
    ensure_client_portal_schema(conn)
    comment_id = generate_id("CMC", "client_comments", "comment_id", conn=conn)
    conn.execute(
        """
        INSERT INTO client_comments(
            comment_id, client_id, entity_type, entity_id, project_id,
            body, portal_user_id, created_at
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            comment_id,
            client_id,
            entity_type,
            entity_id,
            project_id or "",
            text,
            portal_user_id,
            _local_ts(),
        ),
    )
    log_portal_audit(
        "comment_added",
        portal_user_id=portal_user_id,
        client_id=client_id,
        entity_type=entity_type,
        entity_id=entity_id,
        details={"preview": text[:200]},
        conn=conn,
    )
    conn.commit()
    conn.close()
    return comment_id, ""


def load_entity_comments(client_id: str, entity_type: str, entity_id: str):
    import pandas as pd

    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT comment_id, body, portal_user_id, created_at
        FROM client_comments
        WHERE client_id = ? AND entity_type = ? AND entity_id = ?
        ORDER BY id ASC
        """,
        conn,
        params=(client_id, entity_type, entity_id),
    )
    conn.close()
    return df


def load_project_documents(client_id: str, project_id: str):
    import pandas as pd

    if not project_belongs_to_client(client_id, project_id=project_id):
        return pd.DataFrame()
    conn = get_conn()
    docs = pd.read_sql_query(
        """
        SELECT document_type, file_path, uploaded_at
        FROM document_uploads
        WHERE entity_type = 'project' AND entity_id = ?
        ORDER BY id DESC
        """,
        conn,
        params=(project_id,),
    )
    drawings = pd.read_sql_query(
        """
        SELECT doc_title, file_path, version, uploaded_at, doc_type
        FROM controlled_documents
        WHERE project_name IN (
            SELECT project_name FROM projects WHERE project_id = ?
        )
        ORDER BY id DESC
        """,
        conn,
        params=(project_id,),
    )
    conn.close()
    return docs, drawings


def load_payment_history(client_id: str, client_name: str):
    import pandas as pd

    names = client_assigned_project_names(client_id)
    if not names:
        return pd.DataFrame()
    conn = get_conn()
    placeholders = ",".join("?" * len(names))
    receipts = pd.read_sql_query(
        f"""
        SELECT voucher_no, receipt_date, amount, mode, project_name, reference_no, status
        FROM receipt_vouchers
        WHERE customer = ? AND project_name IN ({placeholders})
        ORDER BY id DESC
        """,
        conn,
        params=(client_name, *sorted(names)),
    )
    paid_bills = pd.read_sql_query(
        f"""
        SELECT bill_no AS voucher_no, bill_date AS receipt_date,
               COALESCE(grand_total, total_amount) AS amount,
               'Invoice' AS mode, project_name, status, bill_id
        FROM client_bills
        WHERE client_name = ? AND project_name IN ({placeholders})
          AND status IN ('Paid', 'Client Approved', 'Approved')
        ORDER BY id DESC
        """,
        conn,
        params=(client_name, *sorted(names)),
    )
    conn.close()
    return receipts, paid_bills


def load_progress_reports(client_id: str):
    import pandas as pd

    names = client_assigned_project_names(client_id)
    if not names:
        return pd.DataFrame()
    conn = get_conn()
    placeholders = ",".join("?" * len(names))
    df = pd.read_sql_query(
        f"""
        SELECT dpr_id, dpr_date, project_name, progress_quantity, done_quantity,
               total_boq_quantity, status, remarks
        FROM dpr_reports
        WHERE project_name IN ({placeholders})
        ORDER BY dpr_date DESC, id DESC
        LIMIT 200
        """,
        conn,
        params=tuple(sorted(names)),
    )
    conn.close()
    return df


def load_clients_for_admin():
    import pandas as pd

    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT client_id, client_name, email, mobile, status
        FROM clients
        WHERE COALESCE(status, 'Active') != 'Inactive'
        ORDER BY client_name
        """,
        conn,
    )
    conn.close()
    return df


def load_projects_for_assignment():
    import pandas as pd

    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT project_id, project_name, client_name, status
        FROM projects
        WHERE COALESCE(project_name, '') != ''
        ORDER BY project_name
        """,
        conn,
    )
    conn.close()
    return df


def notify_accounts_bill_decision(bill_id: str, action: str, client_name: str, comment: str = "") -> bool:
    """Email accounts when client approves/rejects a bill."""
    from modules.notifications import send_email_notification, smtp_config

    cfg = smtp_config()
    if not cfg.get("configured"):
        return False
    notify_to = (cfg.get("user") or cfg.get("from_addr") or "").strip()
    if not notify_to:
        return False
    conn = get_conn()
    row = conn.execute(
        "SELECT bill_no, project_name, total_amount FROM client_bills WHERE bill_id = ?",
        (bill_id,),
    ).fetchone()
    conn.close()
    if not row:
        return False
    subject = f"Client {action}: Bill {row[0]} — {client_name}"
    body = (
        f"Client {client_name} has {action} bill {row[0]} for project {row[1]}.\n"
        f"Amount: Rs {float(row[2] or 0):,.2f}\n"
    )
    if comment:
        body += f"Comment: {comment}\n"
    body += "\n— MAXEK ERP Client Portal"
    return bool(send_email_notification(notify_to, subject, body))
