"""Workflow notification email hooks."""

from unittest.mock import patch

from modules.notifications import (
    NOTIFY_STATUSES,
    _STATUS_EMAIL_SUBJECT,
    notify_workflow_transition,
    smtp_config,
)


def test_notify_statuses_and_subjects():
    assert "Prepared" in NOTIFY_STATUSES
    assert "Paid" in NOTIFY_STATUSES
    assert "Prepared" in _STATUS_EMAIL_SUBJECT


@patch("modules.notifications.send_email_notification", return_value=True)
@patch("modules.notifications.resolve_notification_emails", return_value=["ops@example.com"])
def test_notify_workflow_calls_send(mock_emails, mock_send, tmp_db):
    notify_workflow_transition(
        "client_bill",
        "CB-001",
        "Draft",
        "Prepared",
        "Accounts User",
        comment="Please check",
    )
    mock_send.assert_called_once()
    args = mock_send.call_args[0]
    assert args[0] == "ops@example.com"
    assert "Prepared" in args[1] or "MAXEK" in args[1]
    assert "CB-001" in args[2]


def test_smtp_config_reads_env(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.test.local")
    monkeypatch.setenv("SMTP_USER", "user@test.local")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    cfg = smtp_config()
    assert cfg["host"] == "smtp.test.local"
    assert cfg["configured"]
