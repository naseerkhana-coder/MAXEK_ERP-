"""Tests for named workflow step assignees."""

from modules.database import get_conn
from modules.workflow_assignments_db import (
    check_named_assignee,
    ensure_workflow_assignments_schema,
    get_assignees,
    save_step_assignees,
)


def _seed_users(conn):
    conn.execute(
        """
        INSERT INTO users(user_id, full_name, username, password, role)
        VALUES ('U1', 'Maker User', 'maker1', 'x', 'Site Engineer')
        """
    )
    conn.execute(
        """
        INSERT INTO users(user_id, full_name, username, password, role)
        VALUES ('U2', 'Checker User', 'checker1', 'x', 'Accounts Executive')
        """
    )
    conn.commit()


def test_no_assignees_allows_any_user(tmp_db):
    ensure_workflow_assignments_schema()
    ok, msg = check_named_assignee("anyone", "payment_voucher", "Checked")
    assert ok is True
    assert msg == ""


def test_named_assignee_restricts_users(tmp_db):
    ensure_workflow_assignments_schema()
    conn = get_conn()
    _seed_users(conn)
    conn.close()

    ok, _ = save_step_assignees(
        "petty_cash_fund_request",
        "Checked",
        ["checker1"],
        actor="Admin",
    )
    assert ok is True
    assert get_assignees("petty_cash_fund_request", "Checked") == ["checker1"]

    allowed, _ = check_named_assignee("checker1", "petty_cash_fund_request", "Checked")
    denied, err = check_named_assignee("maker1", "petty_cash_fund_request", "Checked")
    assert allowed is True
    assert denied is False
    assert "checker1" in err


def test_replace_assignees_on_save(tmp_db):
    ensure_workflow_assignments_schema()
    save_step_assignees("payment_voucher", "Approved", ["maker1"], actor="Admin")
    save_step_assignees("payment_voucher", "Approved", ["checker1"], actor="Admin")
    assert get_assignees("payment_voucher", "Approved") == ["checker1"]
