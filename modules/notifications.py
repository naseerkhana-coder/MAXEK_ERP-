"""In-app and email notification hooks for MAXEK ERP workflow events.

SMTP (set in environment before starting Streamlit):

- ``SMTP_HOST`` — mail server hostname (required for live send)
- ``SMTP_PORT`` — default ``587``
- ``SMTP_USER`` — auth username
- ``SMTP_PASSWORD`` or ``SMTP_PASS`` — auth password
- ``SMTP_FROM`` — from address (defaults to ``SMTP_USER``)
- ``SMTP_TLS`` — ``1``/true (default) or ``0``/false for plain SMTP

See ``modules/email_config.py`` and ``DEPLOY.md``. Test: ``python scripts/test_smtp.py``.
Recipients: ``users.email`` for roles mapped in ``_ENTITY_NOTIFY_ROLES``.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from modules.database import get_conn

logger = logging.getLogger("maxek.notifications")

NOTIFY_STATUSES = frozenset(
    {"Prepared", "Checked", "Approved", "Payment Released", "Paid"}
)

_STATUS_EMAIL_SUBJECT: dict[str, str] = {
    "Prepared": "[MAXEK ERP] Document prepared — action required (check)",
    "Checked": "[MAXEK ERP] Document checked — approval required",
    "Approved": "[MAXEK ERP] Document approved — payment release pending",
    "Payment Released": "[MAXEK ERP] Payment released — mark paid when complete",
    "Paid": "[MAXEK ERP] Document marked paid",
}

# entity_type → roles that should receive email on workflow advance
_ENTITY_NOTIFY_ROLES: dict[str, tuple[str, ...]] = {
    "site_expense": ("Accounts Manager", "Accounts Executive", "Accountant", "Project Manager", "MD", "Admin", "Super Admin"),
    "client_bill": ("Accounts Manager", "Accountant", "MD", "Admin", "Super Admin"),
    "vendor_bill": ("Accounts Manager", "Accounts Executive", "Accountant", "MD", "Admin", "Super Admin"),
    "purchase_order": ("Accounts Manager", "Store Keeper", "Project Manager", "MD", "Admin", "Super Admin"),
    "subcontractor_bill": ("Accounts Manager", "Accountant", "Project Manager", "MD", "Admin", "Super Admin"),
    "worker_payroll": ("HR & Payroll", "HR", "Accounts Manager", "MD", "Admin", "Super Admin"),
    "staff_payroll": ("HR & Payroll", "HR", "Accounts Manager", "MD", "Admin", "Super Admin"),
    "petty_cash": ("Accounts Manager", "Accounts Executive", "Project Manager", "MD", "Admin", "Super Admin"),
    "material_request": ("Store Keeper", "Project Manager", "MD", "Admin", "Super Admin"),
    "direct_payment": ("Accounts Manager", "Accounts Executive", "MD", "Admin", "Super Admin"),
}


def _ts() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def smtp_config() -> dict:
    """Read SMTP settings from environment."""
    host = (os.environ.get("SMTP_HOST") or "").strip()
    port_raw = (os.environ.get("SMTP_PORT") or "587").strip()
    try:
        port = int(port_raw)
    except ValueError:
        port = 587
    return {
        "host": host,
        "port": port,
        "user": (os.environ.get("SMTP_USER") or "").strip(),
        "password": (os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS") or "").strip(),
        "from_addr": (os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "").strip(),
        "use_tls": (os.environ.get("SMTP_TLS", "1").strip().lower() not in ("0", "false", "no")),
        "configured": bool(host and (os.environ.get("SMTP_USER") or os.environ.get("SMTP_FROM"))),
    }


def queue_in_app_notification(
    user_name: str,
    title: str,
    detail: str = "",
    entity_type: str = "",
    entity_id: str = "",
) -> None:
    try:
        conn = get_conn()
        conn.execute(
            """
            INSERT INTO dashboard_notifications(
                user_name, title, detail, entity_type, entity_id, is_read, created_at
            ) VALUES(?,?,?,?,?,0,?)
            """,
            (user_name or "", title, detail, entity_type, entity_id, _ts()),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.debug("in-app notification skipped: %s", exc)


def send_email_notification(
    to_address: str,
    subject: str,
    body: str,
    *,
    smtp_configured: bool | None = None,
) -> bool:
    """
    Send email when SMTP is configured (SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_TLS).
    Otherwise log intent only (stub).
    """
    to_address = (to_address or "").strip()
    if not to_address:
        logger.info(
            "would send email (no recipient) subject=%s body_preview=%s",
            subject,
            (body or "")[:120],
        )
        return False

    cfg = smtp_config()
    if smtp_configured is None:
        smtp_configured = cfg["configured"] and bool(cfg.get("password") or cfg["port"] == 25)

    if not smtp_configured:
        logger.info(
            "would send email to=%s subject=%s body_preview=%s",
            to_address,
            subject,
            (body or "")[:120],
        )
        return False

    from_addr = cfg["from_addr"] or cfg["user"]
    if not from_addr:
        logger.warning("SMTP_FROM / SMTP_USER not set; email skipped.")
        return False

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.attach(MIMEText(body or "", "plain", "utf-8"))

    try:
        if cfg["use_tls"]:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if cfg["password"]:
                    server.login(cfg["user"], cfg["password"])
                server.sendmail(from_addr, [to_address], msg.as_string())
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
                if cfg["password"]:
                    server.login(cfg["user"], cfg["password"])
                server.sendmail(from_addr, [to_address], msg.as_string())
        logger.info("email sent to=%s subject=%s", to_address, subject)
        return True
    except Exception as exc:
        logger.error("email send failed to=%s: %s", to_address, exc)
        return False


def _ensure_users_email_column(conn) -> bool:
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "email" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
            conn.commit()
        return "email" in cols or True
    except Exception:
        return False


def resolve_notification_emails(entity_type: str, new_status: str) -> list[str]:
    """Role-based recipients for workflow step; falls back to admin users."""
    roles = _ENTITY_NOTIFY_ROLES.get(entity_type, ("Admin", "Super Admin", "MD"))
    conn = get_conn()
    _ensure_users_email_column(conn)
    emails: list[str] = []
    try:
        placeholders = ",".join("?" * len(roles))
        rows = conn.execute(
            f"""
            SELECT DISTINCT COALESCE(email, '') AS email
            FROM users
            WHERE role IN ({placeholders})
              AND COALESCE(email, '') != ''
            """,
            tuple(roles),
        ).fetchall()
        emails = [r[0].strip() for r in rows if r[0] and "@" in str(r[0])]
    except Exception:
        pass
    if not emails:
        try:
            rows = conn.execute(
                """
                SELECT DISTINCT COALESCE(email, '') AS email
                FROM users
                WHERE role IN ('Admin', 'Super Admin', 'MD')
                  AND COALESCE(email, '') != ''
                """
            ).fetchall()
            emails = [r[0].strip() for r in rows if r[0] and "@" in str(r[0])]
        except Exception:
            pass
    conn.close()
    return emails


def notify_workflow_transition(
    entity_type: str,
    entity_id: str,
    old_status: str,
    new_status: str,
    actor: str,
    comment: str = "",
) -> None:
    if new_status not in NOTIFY_STATUSES:
        return

    title = f"{entity_type.replace('_', ' ').title()} {entity_id}: {old_status} → {new_status}"
    detail = f"By {actor}."
    if comment:
        detail += f" {comment}"

    queue_in_app_notification("", title, detail, entity_type, entity_id)

    entity_label = entity_type.replace("_", " ").title()
    subject = _STATUS_EMAIL_SUBJECT.get(
        new_status,
        f"[MAXEK ERP] {entity_label} {entity_id}: {new_status}",
    )
    body = (
        f"MAXEK ERP workflow notification\n\n"
        f"Document: {entity_label}\n"
        f"Reference: {entity_id}\n"
        f"Status: {old_status} → {new_status}\n"
        f"Actor: {actor}\n"
        f"Time: {_ts()}\n"
    )
    if comment:
        body += f"\nComments:\n{comment}\n"
    body += "\nLog in to MAXEK ERP to review or take the next workflow step."

    for addr in resolve_notification_emails(entity_type, new_status):
        send_email_notification(addr, subject, body)


def build_password_reset_email(username: str, temporary_password: str) -> tuple[str, str]:
    subject = "[MAXEK ERP] Password reset"
    body = (
        "MAXEK ERP password reset\n\n"
        f"Username: {username}\n"
        f"Temporary password: {temporary_password}\n\n"
        "Log in, then open My Account → My Profile → Change Password to set a permanent password.\n\n"
        "If you did not request this reset, contact your system administrator immediately."
    )
    return subject, body


def build_password_reset_link_email(username: str, reset_url: str, hours_valid: int) -> tuple[str, str]:
    subject = "[MAXEK ERP] Reset your password"
    body = (
        "MAXEK ERP password reset\n\n"
        f"Username: {username}\n\n"
        f"Open this link to set a new password (valid for {hours_valid} hours):\n"
        f"{reset_url}\n\n"
        "After signing in, you can also change your password anytime under "
        "My Account → My Profile → Change Password.\n\n"
        "If you did not request this reset, contact your system administrator immediately."
    )
    return subject, body


def send_password_reset_email(to_address: str, username: str, temporary_password: str) -> bool:
    """Send temporary password when SMTP is configured; otherwise log only."""
    subject, body = build_password_reset_email(username, temporary_password)
    return send_email_notification(to_address, subject, body)


def send_password_reset_link_email(
    to_address: str,
    username: str,
    reset_url: str,
    hours_valid: int = 24,
) -> bool:
    """Send password reset link when SMTP is configured."""
    subject, body = build_password_reset_link_email(username, reset_url, hours_valid)
    return send_email_notification(to_address, subject, body)


def build_payment_released_email(
    entity_label: str,
    entity_id: str,
    amount: str,
    project_name: str = "",
) -> tuple[str, str]:
    subject = f"[MAXEK ERP] Payment released — {entity_id}"
    body = (
        "MAXEK ERP payment notification\n\n"
        f"Document: {entity_label}\n"
        f"Reference: {entity_id}\n"
        f"Amount: {amount}\n"
    )
    if project_name:
        body += f"Project: {project_name}\n"
    body += "\nPayment has been released. Log in to MAXEK ERP to complete settlement or mark paid."
    return subject, body


def send_payment_released_email(
    to_address: str,
    entity_label: str,
    entity_id: str,
    amount: str,
    project_name: str = "",
) -> bool:
    subject, body = build_payment_released_email(entity_label, entity_id, amount, project_name)
    return send_email_notification(to_address, subject, body)


def build_user_notification_email(title: str, message: str, actor: str = "") -> tuple[str, str]:
    subject = f"[MAXEK ERP] {title}"
    body = f"MAXEK ERP notification\n\n{title}\n\n{message}\n"
    if actor:
        body += f"\nFrom: {actor}\n"
    body += f"\nTime: {_ts()}\n"
    return subject, body


def send_user_notification_email(
    to_address: str,
    title: str,
    message: str,
    actor: str = "",
) -> bool:
    subject, body = build_user_notification_email(title, message, actor)
    return send_email_notification(to_address, subject, body)


def load_unread_notifications(user_name: str = "", limit: int = 20):
    import pandas as pd

    conn = get_conn()
    try:
        if user_name:
            df = pd.read_sql_query(
                """
                SELECT title, detail, entity_type, entity_id, created_at
                FROM dashboard_notifications
                WHERE is_read = 0 AND (user_name = '' OR user_name = ?)
                ORDER BY id DESC
                LIMIT ?
                """,
                conn,
                params=(user_name, max(1, min(int(limit), 50))),
            )
        else:
            df = pd.read_sql_query(
                """
                SELECT title, detail, entity_type, entity_id, created_at
                FROM dashboard_notifications
                WHERE is_read = 0
                ORDER BY id DESC
                LIMIT ?
                """,
                conn,
                params=(max(1, min(int(limit), 50)),),
            )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df
