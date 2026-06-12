"""Logged-in profile, password change, token-based reset, and user security audit."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from modules.database import BASE_DIR, get_conn
from modules.password_security import hash_password, validate_password_policy, verify_password

# Hours until reset link expires (override via PASSWORD_RESET_TOKEN_HOURS).
DEFAULT_TOKEN_TTL_HOURS = 24

USER_ACCOUNT_COLUMNS = (
    ("email", "TEXT"),
    ("department", "TEXT"),
    ("designation", "TEXT"),
    ("profile_photo", "TEXT"),
    ("employee_id", "TEXT"),
    ("must_change_password", "INTEGER DEFAULT 0"),
    ("password_changed_at", "TEXT"),
    ("last_login_at", "TEXT"),
    ("is_disabled", "INTEGER DEFAULT 0"),
    ("account_locked", "INTEGER DEFAULT 0"),
    ("workflow_role", "TEXT"),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _local_ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def password_reset_token_hours() -> int:
    raw = (os.environ.get("PASSWORD_RESET_TOKEN_HOURS") or "").strip()
    try:
        return max(1, min(168, int(raw or DEFAULT_TOKEN_TTL_HOURS)))
    except ValueError:
        return DEFAULT_TOKEN_TTL_HOURS


def app_base_url() -> str:
    """Public ERP URL for reset links (no trailing slash). Set APP_BASE_URL in production."""
    return (os.environ.get("APP_BASE_URL") or os.environ.get("ERP_BASE_URL") or "").strip().rstrip("/")


def ensure_user_account_schema(conn=None) -> None:
    """Migrate users columns and user_account_audit table."""
    from modules.database import _add_column_if_missing, _columns
    from modules.notifications import _ensure_users_email_column

    own = conn is None
    if own:
        conn = get_conn()
    _ensure_users_email_column(conn)
    cur = conn.cursor()
    for col, typ in USER_ACCOUNT_COLUMNS:
        _add_column_if_missing(cur, "users", col, typ)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_account_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            actor TEXT,
            action_at TEXT NOT NULL,
            details TEXT
        )
        """
    )
    ensure_password_reset_table(conn)
    if own:
        conn.commit()
        conn.close()


def ensure_password_reset_table(conn=None) -> None:
    own = conn is None
    if own:
        conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT NOT NULL,
            user_id TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    if own:
        conn.commit()
        conn.close()


def log_user_account_audit(
    user_id: str,
    action: str,
    actor: str = "",
    *,
    details: str = "",
    conn=None,
) -> None:
    own = conn is None
    if own:
        conn = get_conn()
    ensure_user_account_schema(conn)
    conn.execute(
        """
        INSERT INTO user_account_audit(user_id, action, actor, action_at, details)
        VALUES(?,?,?,?,?)
        """,
        (user_id, action, actor or "", _local_ts(), details or ""),
    )
    if own:
        conn.commit()
        conn.close()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_new_password(password: str, confirm: str) -> str | None:
    pwd = (password or "").strip()
    if not pwd:
        return "New password is required."
    if pwd != (confirm or "").strip():
        return "New password and confirmation do not match."
    return validate_password_policy(pwd)


def _resolve_employee_fields(conn, user: dict) -> tuple[str, str, str]:
    """Return (employee_id, department, designation) from user row or employees match."""
    emp_id = (user.get("employee_id") or "").strip()
    dept = (user.get("department") or "").strip()
    desig = (user.get("designation") or "").strip()
    if emp_id:
        row = conn.execute(
            """
            SELECT COALESCE(department, ''), COALESCE(designation, '')
            FROM employees WHERE employee_id = ?
            """,
            (emp_id,),
        ).fetchone()
        if row:
            dept = dept or (row[0] or "").strip()
            desig = desig or (row[1] or "").strip()
    if not dept or not desig:
        name = (user.get("full_name") or "").strip()
        mobile = (user.get("mobile") or "").strip()
        if name or mobile:
            row = conn.execute(
                """
                SELECT employee_id, COALESCE(department, ''), COALESCE(designation, '')
                FROM employees
                WHERE (? != '' AND LOWER(employee_name) = LOWER(?))
                   OR (? != '' AND mobile_number = ?)
                LIMIT 1
                """,
                (name, name, mobile, mobile),
            ).fetchone()
            if row:
                emp_id = emp_id or (row[0] or "").strip()
                dept = dept or (row[1] or "").strip()
                desig = desig or (row[2] or "").strip()
    return emp_id, dept, desig


def get_user_by_id(user_id: str) -> dict | None:
    if not user_id:
        return None
    conn = get_conn()
    ensure_user_account_schema(conn)
    row = conn.execute(
        """
        SELECT user_id, full_name, username, role, mobile, COALESCE(email, '') AS email,
               password, COALESCE(department, '') AS department,
               COALESCE(designation, '') AS designation,
               COALESCE(profile_photo, '') AS profile_photo,
               COALESCE(employee_id, '') AS employee_id,
               COALESCE(must_change_password, 0) AS must_change_password,
               COALESCE(password_changed_at, '') AS password_changed_at,
               COALESCE(last_login_at, '') AS last_login_at,
               COALESCE(is_disabled, 0) AS is_disabled,
               COALESCE(account_locked, 0) AS account_locked
        FROM users WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    if not row:
        conn.close()
        return None
    user = {
        "user_id": row[0],
        "full_name": row[1] or "",
        "username": row[2] or "",
        "role": row[3] or "",
        "mobile": row[4] or "",
        "email": row[5] or "",
        "password": row[6] or "",
        "department": row[7] or "",
        "designation": row[8] or "",
        "profile_photo": row[9] or "",
        "employee_id": row[10] or "",
        "must_change_password": bool(row[11]),
        "password_changed_at": row[12] or "",
        "last_login_at": row[13] or "",
        "is_disabled": bool(row[14]),
        "account_locked": bool(row[15]),
    }
    emp_id, dept, desig = _resolve_employee_fields(conn, user)
    user["employee_id"] = emp_id
    user["department"] = dept
    user["designation"] = desig
    conn.close()
    return user


def user_must_change_password(user_id: str) -> bool:
    user = get_user_by_id(user_id)
    return bool(user and user.get("must_change_password"))


def login_allowed_for_username(username: str) -> tuple[bool, str]:
    """Check disabled/locked before password verification."""
    uname = (username or "").strip()
    if not uname:
        return False, "Enter your username."
    conn = get_conn()
    ensure_user_account_schema(conn)
    row = conn.execute(
        """
        SELECT COALESCE(is_disabled, 0), COALESCE(account_locked, 0)
        FROM users WHERE LOWER(username) = LOWER(?)
        """,
        (uname,),
    ).fetchone()
    conn.close()
    if not row:
        return True, ""
    if row[0]:
        return False, "This account is disabled. Contact your administrator."
    if row[1]:
        return False, "This account is locked. Ask your administrator to unlock it."
    return True, ""


def record_successful_login(user_id: str) -> None:
    conn = get_conn()
    ensure_user_account_schema(conn)
    conn.execute(
        "UPDATE users SET last_login_at = ? WHERE user_id = ?",
        (_local_ts(), user_id),
    )
    conn.commit()
    conn.close()


def get_security_summary(user_id: str, *, session_username: str = "") -> dict:
    user = get_user_by_id(user_id) or {}
    conn = get_conn()
    prev_login = ""
    if session_username:
        row = conn.execute(
            """
            SELECT login_at FROM login_history
            WHERE username = ? AND success = 1
            ORDER BY id DESC LIMIT 2
            """,
            (session_username,),
        ).fetchall()
        if len(row) >= 2:
            prev_login = row[1][0] or ""
        elif len(row) == 1 and user.get("last_login_at"):
            prev_login = user.get("last_login_at") or ""
    conn.close()
    return {
        "last_login_at": prev_login or user.get("last_login_at") or "—",
        "password_changed_at": user.get("password_changed_at") or "—",
        "username": user.get("username") or session_username,
        "is_disabled": user.get("is_disabled"),
        "account_locked": user.get("account_locked"),
    }


def save_profile_photo(user_id: str, uploaded_file) -> tuple[str | None, str]:
    if not user_id or not uploaded_file:
        return None, ""
    ext = os.path.splitext(uploaded_file.name)[1] or ".jpg"
    rel_path = os.path.join("uploads", "users", f"{user_id}{ext}")
    abs_path = os.path.join(BASE_DIR, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return rel_path.replace("\\", "/"), ""


def update_user_profile(
    user_id: str,
    *,
    full_name: str,
    mobile: str,
    email: str,
    profile_photo: str | None = None,
    actor: str = "",
) -> tuple[bool, str]:
    if not user_id:
        return False, "Not signed in."
    name = (full_name or "").strip()
    if not name:
        return False, "Employee name is required."
    mail = (email or "").strip()
    if mail and "@" not in mail:
        return False, "Enter a valid email address."
    conn = get_conn()
    ensure_user_account_schema(conn)
    if profile_photo is not None:
        conn.execute(
            """
            UPDATE users SET full_name = ?, mobile = ?, email = ?, profile_photo = ?
            WHERE user_id = ?
            """,
            (name, (mobile or "").strip(), mail, profile_photo, user_id),
        )
    else:
        conn.execute(
            """
            UPDATE users SET full_name = ?, mobile = ?, email = ?
            WHERE user_id = ?
            """,
            (name, (mobile or "").strip(), mail, user_id),
        )
    log_user_account_audit(
        user_id,
        "Profile Updated",
        actor or user_id,
        details=f"mobile={mobile or ''}; email={mail}",
        conn=conn,
    )
    conn.commit()
    conn.close()
    return True, "Profile updated."


def change_password(
    user_id: str,
    current_password: str,
    new_password: str,
    *,
    actor: str = "",
) -> tuple[bool, str]:
    err = validate_new_password(new_password, new_password)
    if err:
        return False, err
    user = get_user_by_id(user_id)
    if not user:
        return False, "User not found."
    if not verify_password((current_password or "").strip(), user["password"]):
        return False, "Current password is incorrect."
    conn = get_conn()
    ensure_user_account_schema(conn)
    ts = _local_ts()
    conn.execute(
        """
        UPDATE users SET password = ?, must_change_password = 0,
               password_changed_at = ?
        WHERE user_id = ?
        """,
        (hash_password(new_password.strip()), ts, user_id),
    )
    log_user_account_audit(user_id, "Password Changed", actor or user_id, conn=conn)
    conn.commit()
    conn.close()
    return True, "Password changed successfully."


def admin_reset_user_password(
    actor_role: str,
    target_user_id: str,
    new_password: str,
    *,
    actor_id: str = "",
    force_change: bool = True,
) -> tuple[bool, str]:
    from modules.roles import can_manage_users

    if not can_manage_users(actor_role):
        return False, "Only Super Admin can reset another user's password."
    err = validate_new_password(new_password, new_password)
    if err:
        return False, err
    if not target_user_id:
        return False, "Select a user."
    conn = get_conn()
    ensure_user_account_schema(conn)
    cur = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (target_user_id,))
    if not cur.fetchone():
        conn.close()
        return False, "User not found."
    must_flag = 1 if force_change else 0
    conn.execute(
        """
        UPDATE users SET password = ?, must_change_password = ?,
               password_changed_at = ?
        WHERE user_id = ?
        """,
        (hash_password(new_password.strip()), must_flag, _local_ts(), target_user_id),
    )
    log_user_account_audit(
        target_user_id,
        "Password Reset",
        actor_id or actor_role,
        details="admin reset",
        conn=conn,
    )
    conn.commit()
    conn.close()
    return True, "Password updated for selected user."


def admin_set_user_disabled(
    actor_role: str,
    target_user_id: str,
    disabled: bool,
    *,
    actor_id: str = "",
) -> tuple[bool, str]:
    from modules.roles import can_manage_users

    if not can_manage_users(actor_role):
        return False, "Only Super Admin can enable or disable users."
    if not target_user_id:
        return False, "Select a user."
    conn = get_conn()
    ensure_user_account_schema(conn)
    if not conn.execute("SELECT 1 FROM users WHERE user_id = ?", (target_user_id,)).fetchone():
        conn.close()
        return False, "User not found."
    conn.execute(
        "UPDATE users SET is_disabled = ? WHERE user_id = ?",
        (1 if disabled else 0, target_user_id),
    )
    log_user_account_audit(
        target_user_id,
        "User Disabled" if disabled else "User Enabled",
        actor_id or actor_role,
        conn=conn,
    )
    conn.commit()
    conn.close()
    verb = "disabled" if disabled else "enabled"
    return True, f"User account {verb}."


def admin_force_password_change(
    actor_role: str,
    target_user_id: str,
    *,
    actor_id: str = "",
) -> tuple[bool, str]:
    from modules.roles import can_manage_users

    if not can_manage_users(actor_role):
        return False, "Only Super Admin can force a password change."
    if not target_user_id:
        return False, "Select a user."
    conn = get_conn()
    ensure_user_account_schema(conn)
    if not conn.execute("SELECT 1 FROM users WHERE user_id = ?", (target_user_id,)).fetchone():
        conn.close()
        return False, "User not found."
    conn.execute(
        "UPDATE users SET must_change_password = 1 WHERE user_id = ?",
        (target_user_id,),
    )
    log_user_account_audit(
        target_user_id,
        "Force Password Change",
        actor_id or actor_role,
        conn=conn,
    )
    conn.commit()
    conn.close()
    return True, "User must change password on next login."


def admin_unlock_user_account(
    actor_role: str,
    target_user_id: str,
    *,
    actor_id: str = "",
) -> tuple[bool, str]:
    from modules.roles import can_manage_users

    if not can_manage_users(actor_role):
        return False, "Only Super Admin can unlock user accounts."
    if not target_user_id:
        return False, "Select a user."
    conn = get_conn()
    ensure_user_account_schema(conn)
    if not conn.execute("SELECT 1 FROM users WHERE user_id = ?", (target_user_id,)).fetchone():
        conn.close()
        return False, "User not found."
    conn.execute(
        "UPDATE users SET account_locked = 0 WHERE user_id = ?",
        (target_user_id,),
    )
    log_user_account_audit(
        target_user_id,
        "User Unlocked",
        actor_id or actor_role,
        conn=conn,
    )
    conn.commit()
    conn.close()
    return True, "User account unlocked."


def admin_lock_user_account(
    actor_role: str,
    target_user_id: str,
    *,
    actor_id: str = "",
) -> tuple[bool, str]:
    from modules.roles import can_manage_users

    if not can_manage_users(actor_role):
        return False, "Only Super Admin can lock user accounts."
    if not target_user_id:
        return False, "Select a user."
    conn = get_conn()
    ensure_user_account_schema(conn)
    if not conn.execute("SELECT 1 FROM users WHERE user_id = ?", (target_user_id,)).fetchone():
        conn.close()
        return False, "User not found."
    conn.execute(
        "UPDATE users SET account_locked = 1 WHERE user_id = ?",
        (target_user_id,),
    )
    log_user_account_audit(
        target_user_id,
        "User Locked",
        actor_id or actor_role,
        conn=conn,
    )
    conn.commit()
    conn.close()
    return True, "User account locked."


def _create_reset_token_for_user_id(conn, user_id: str) -> tuple[str | None, str]:
    plain = secrets.token_urlsafe(32)
    expires = _utc_now() + timedelta(hours=password_reset_token_hours())
    conn.execute(
        """
        INSERT INTO password_reset_tokens(token_hash, user_id, expires_at, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (_hash_token(plain), user_id, _iso(expires), _iso(_utc_now())),
    )
    return plain, ""


def create_password_reset_token(username: str) -> tuple[str | None, str, str]:
    """
    Create a reset token for username.
    Returns (plain_token, user_id, message_for_ui).
    """
    uname = (username or "").strip()
    if not uname:
        return None, "", "Enter your username."
    from modules.notifications import _ensure_users_email_column

    conn = get_conn()
    _ensure_users_email_column(conn)
    ensure_password_reset_table(conn)
    row = conn.execute(
        "SELECT user_id, COALESCE(email, '') FROM users WHERE LOWER(username) = LOWER(?)",
        (uname,),
    ).fetchone()
    if not row:
        conn.close()
        return None, "", "Username not found."
    user_id, email = row[0], (row[1] or "").strip()
    if not email or "@" not in email:
        conn.close()
        return None, user_id, "No email on file. Ask your administrator to set your email in Settings → Users."

    plain, err = _create_reset_token_for_user_id(conn, user_id)
    conn.commit()
    conn.close()
    return plain, user_id, err


def create_password_reset_token_by_email(email: str) -> tuple[str | None, str, str]:
    """Create reset token lookup by email address."""
    mail = (email or "").strip().lower()
    if not mail or "@" not in mail:
        return None, "", "Enter a valid email address."
    from modules.notifications import _ensure_users_email_column

    conn = get_conn()
    _ensure_users_email_column(conn)
    ensure_password_reset_table(conn)
    row = conn.execute(
        "SELECT user_id, username FROM users WHERE LOWER(TRIM(email)) = ?",
        (mail,),
    ).fetchone()
    if not row:
        conn.close()
        return None, "", "No account found for this email address."
    user_id = row[0]
    plain, err = _create_reset_token_for_user_id(conn, user_id)
    conn.commit()
    conn.close()
    return plain, user_id, err


def reset_password_with_token(token: str, new_password: str) -> tuple[bool, str]:
    err = validate_new_password(new_password, new_password)
    if err:
        return False, err
    plain = (token or "").strip()
    if not plain:
        return False, "Reset link is invalid or expired."
    conn = get_conn()
    ensure_password_reset_table(conn)
    ensure_user_account_schema(conn)
    row = conn.execute(
        """
        SELECT id, user_id, expires_at, used_at
        FROM password_reset_tokens
        WHERE token_hash = ?
        ORDER BY id DESC LIMIT 1
        """,
        (_hash_token(plain),),
    ).fetchone()
    if not row:
        conn.close()
        return False, "Reset link is invalid or expired."
    tok_id, user_id, expires_at, used_at = row
    if used_at:
        conn.close()
        return False, "This reset link was already used. Request a new one from the login page."
    try:
        exp = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        conn.close()
        return False, "Reset link is invalid or expired."
    if _utc_now() > exp:
        conn.close()
        return False, "Reset link has expired. Request a new one from the login page."
    ts = _local_ts()
    conn.execute(
        """
        UPDATE users SET password = ?, must_change_password = 0, password_changed_at = ?
        WHERE user_id = ?
        """,
        (hash_password(new_password.strip()), ts, user_id),
    )
    conn.execute(
        "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
        (_iso(_utc_now()), tok_id),
    )
    log_user_account_audit(user_id, "Password Reset", user_id, details="token reset", conn=conn)
    conn.commit()
    conn.close()
    return True, "Password updated. You can log in with your new password."


def lookup_token_username(token: str) -> str | None:
    """Return username for a valid unused token (for UI hint only)."""
    plain = (token or "").strip()
    if not plain:
        return None
    conn = get_conn()
    ensure_password_reset_table(conn)
    row = conn.execute(
        """
        SELECT t.user_id, t.expires_at, t.used_at, u.username
        FROM password_reset_tokens t
        JOIN users u ON u.user_id = t.user_id
        WHERE t.token_hash = ?
        ORDER BY t.id DESC LIMIT 1
        """,
        (_hash_token(plain),),
    ).fetchone()
    conn.close()
    if not row:
        return None
    _uid, expires_at, used_at, username = row
    if used_at:
        return None
    try:
        exp = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    if _utc_now() > exp:
        return None
    return username
