"""SMTP configuration reference for MAXEK ERP.

Environment variables (set on server or in `.env` loaded before Streamlit):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| SMTP_HOST | Yes* | — | Mail server hostname |
| SMTP_PORT | No | 587 | Port (587 TLS, 465 SSL, 25 plain) |
| SMTP_USER | Yes* | — | SMTP auth username |
| SMTP_PASSWORD | Yes* | — | SMTP password (alias: SMTP_PASS) |
| SMTP_FROM | No | SMTP_USER | From address on outbound mail |
| SMTP_TLS | No | 1 | Set 0/false/no to disable STARTTLS |

*Required for live email delivery. Without them, workflow transitions still queue
in-app notifications and log "would send email" in `modules/notifications.py`.

Test delivery: ``python scripts/test_smtp.py --to <email>`` (optional ``--scenario``:
``password_reset``, ``approval``, ``payment_released``, ``notification``).

Password reset on login page:

- With ``APP_BASE_URL`` (or ``ERP_BASE_URL``) and SMTP: secure link email via ``send_password_reset_link_email``.
- Otherwise: temporary password via ``send_password_reset_email`` when SMTP and ``users.email`` are set.

Optional: ``PASSWORD_RESET_TOKEN_HOURS`` (default 24) — reset link validity.
"""

from modules.notifications import smtp_config

__all__ = ["smtp_config", "SMTP_ENV_VARS"]

SMTP_ENV_VARS = (
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_PASS",
    "SMTP_FROM",
    "SMTP_TLS",
    "APP_BASE_URL",
    "ERP_BASE_URL",
    "PASSWORD_RESET_TOKEN_HOURS",
)
