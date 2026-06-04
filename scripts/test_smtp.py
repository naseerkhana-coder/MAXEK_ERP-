#!/usr/bin/env python3
"""Send a test email when SMTP_* environment variables are configured."""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.email_config import SMTP_ENV_VARS, smtp_config
from modules.notifications import (
    build_password_reset_email,
    build_payment_released_email,
    build_user_notification_email,
    notify_workflow_transition,
    send_email_notification,
)

SCENARIOS = (
    "default",
    "password_reset",
    "approval",
    "payment_released",
    "notification",
)


def _missing_smtp_vars(cfg: dict) -> list[str]:
    missing = [k for k in ("SMTP_HOST", "SMTP_USER") if not os.environ.get(k)]
    if not cfg.get("password") and cfg.get("port") != 25:
        missing.append("SMTP_PASSWORD or SMTP_PASS")
    return missing


def _print_dry_run_help() -> None:
    print("SMTP dry-run: not configured. Set these environment variables:")
    for name in SMTP_ENV_VARS:
        print(f"  - {name}")
    print("\nExample (PowerShell):")
    print('  $env:SMTP_HOST="smtp.example.com"')
    print('  $env:SMTP_USER="erp@example.com"')
    print('  $env:SMTP_PASSWORD="***"')
    print('  $env:SMTP_FROM="erp@example.com"')
    print("  python scripts/test_smtp.py --to you@example.com")
    print("  python scripts/test_smtp.py --to you@example.com --scenario password_reset")


def _send_scenario(to_addr: str, scenario: str) -> bool:
    if scenario == "default":
        return send_email_notification(
            to_addr,
            "[MAXEK ERP] SMTP test",
            "This is a test message from scripts/test_smtp.py.\n\nIf you received this, workflow email is configured.",
        )
    if scenario == "password_reset":
        subject, body = build_password_reset_email("demo_user", "TempPass-1234")
        return send_email_notification(to_addr, subject, body)
    if scenario == "approval":
        notify_workflow_transition(
            "client_bill",
            "CB-SMTP-TEST",
            "Draft",
            "Prepared",
            "SMTP Test Script",
            comment="Scenario: approval workflow email",
        )
        return True
    if scenario == "payment_released":
        subject, body = build_payment_released_email(
            "Petty Cash Request",
            "PCR-SMTP-TEST",
            "Rs 10,000.00",
            project_name="Demo Site",
        )
        return send_email_notification(to_addr, subject, body)
    if scenario == "notification":
        subject, body = build_user_notification_email(
            "System notification test",
            "This is a generic user notification from test_smtp.py.",
            actor="SMTP Test Script",
        )
        return send_email_notification(to_addr, subject, body)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="MAXEK ERP SMTP connectivity test")
    parser.add_argument(
        "--to",
        default=os.environ.get("SMTP_TEST_TO", "").strip(),
        help="Recipient email (or set SMTP_TEST_TO)",
    )
    parser.add_argument(
        "--scenario",
        choices=SCENARIOS,
        default="default",
        help="Email template to exercise (default: simple SMTP test)",
    )
    args = parser.parse_args()

    cfg = smtp_config()
    missing = _missing_smtp_vars(cfg)
    if missing:
        _print_dry_run_help()
        print(f"\nScenario requested: {args.scenario} (not sent — SMTP unset).")
        return 0

    to_addr = (args.to or cfg.get("from_addr") or cfg.get("user") or "").strip()
    if not to_addr or "@" not in to_addr:
        print("Provide --to or SMTP_TEST_TO with a valid email address.")
        return 1

    if args.scenario == "approval":
        from unittest.mock import patch

        with patch(
            "modules.notifications.resolve_notification_emails",
            return_value=[to_addr],
        ):
            ok = _send_scenario(to_addr, args.scenario)
    else:
        ok = _send_scenario(to_addr, args.scenario)

    if ok:
        print(f"Test email sent to {to_addr} (scenario={args.scenario})")
        return 0
    print("Send failed — check SMTP_HOST, credentials, TLS/port, and firewall.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
