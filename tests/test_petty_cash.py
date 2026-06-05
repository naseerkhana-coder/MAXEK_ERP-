"""Petty cash balance calculation and workflow transitions."""

import pytest

from modules.approval_workflow import can_transition, normalize_status, transition
from modules.database import init_db
from modules.petty_cash_db import (
    can_transition_expense,
    ensure_petty_cash_schema,
    get_petty_balance,
    get_project_petty_metrics,
    save_expense,
    save_expense_attachments,
    save_fund_issue,
    save_fund_request,
    transition_expense,
)


@pytest.fixture()
def pc_db(tmp_path, monkeypatch):
    db_file = tmp_path / "petty_cash_test.db"
    monkeypatch.setattr("modules.database.DB_PATH", str(db_file))
    monkeypatch.setattr("modules.database.BASE_DIR", str(tmp_path))
    init_db()
    ensure_petty_cash_schema()
    yield db_file


def test_balance_formula(pc_db):
    rid = save_fund_request(
        {
            "project_name": "Site A",
            "requested_by": "Engineer",
            "amount_requested": 10000.0,
            "purpose": "Initial float",
        },
        "Tester",
    )
    assert rid.startswith("PCFR")

    save_fund_issue(
        {
            "project_name": "Site A",
            "employee_name": "Raj",
            "issue_amount": 50000.0,
        },
        "Accounts",
    )

    metrics = get_project_petty_metrics("Site A")
    assert metrics["fund_issued"] == 50000.0
    assert metrics["balance_in_hand"] == 50000.0
    assert get_petty_balance("Site A") == 50000.0

    eno = save_expense(
        {
            "project_name": "Site A",
            "expense_category": "Material",
            "vendor_name": "Local Store",
            "amount": 5000.0,
        },
        "Engineer",
    )
    from modules.database import get_conn

    conn = get_conn()
    save_expense_attachments(conn, eno, [("Receipt", "uploads/test/receipt.pdf")], "Engineer")
    conn.commit()
    conn.close()

    ok, _ = transition_expense(eno, "Prepared", "Engineer")
    assert ok
    ok, _ = transition_expense(eno, "Checked", "Accounts")
    assert ok
    ok, _ = transition_expense(eno, "Approved", "MD")
    assert ok

    assert get_petty_balance("Site A") == 45000.0
    metrics = get_project_petty_metrics("Site A")
    assert metrics["expenses_approved"] == 5000.0
    assert metrics["balance_in_hand"] == 45000.0


def test_fund_request_workflow(pc_db):
    rid = save_fund_request(
        {
            "project_name": "Site B",
            "requested_by": "PM",
            "amount_requested": 20000.0,
        },
        "PM",
    )
    assert can_transition("Draft", "Prepared")
    ok, msg = transition("petty_cash_fund_request", rid, "Prepared", "PM", "Site Engineer")
    assert ok, msg
    ok, msg = transition("petty_cash_fund_request", rid, "Checked", "Acct", "Accounts Manager")
    assert ok, msg
    ok, msg = transition("petty_cash_fund_request", rid, "Approved", "MD", "MD")
    assert ok, msg
    assert normalize_status("Verified", "petty_cash_fund_request") == "Checked"


def test_expense_reject_and_return(pc_db):
    save_fund_issue(
        {"project_name": "Site C", "employee_name": "A", "issue_amount": 1000.0},
        "Accounts",
    )
    eno = save_expense(
        {"project_name": "Site C", "amount": 100.0, "expense_category": "Other"},
        "Eng",
    )
    conn = __import__("modules.database", fromlist=["get_conn"]).get_conn()
    save_expense_attachments(conn, eno, [("Bill", "uploads/x.pdf")], "Eng")
    conn.commit()
    conn.close()
    transition_expense(eno, "Prepared", "Eng")
    assert can_transition_expense("Prepared", "Checked")
    transition_expense(eno, "Checked", "Acct")
    ok, _ = transition_expense(eno, "Rejected", "Acct", comments="Invalid bill")
    assert ok
    assert not can_transition_expense("Rejected", "Approved")
