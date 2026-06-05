"""Payment voucher numbering, edits, and workflow transitions."""

import sqlite3

import pytest

from modules.approval_workflow import can_transition, normalize_status, transition
from modules.database import get_conn, init_db
from modules.payment_voucher_db import (
    ensure_payment_voucher_schema,
    save_payment_voucher,
    voucher_is_editable,
)


@pytest.fixture()
def pv_db(tmp_path, monkeypatch):
    db_file = tmp_path / "pv_test.db"
    monkeypatch.setattr("modules.database.DB_PATH", str(db_file))
    monkeypatch.setattr("modules.database.BASE_DIR", str(tmp_path))
    init_db()
    ensure_payment_voucher_schema()
    yield db_file


def test_voucher_number_format(pv_db):
    vid, vno = save_payment_voucher(
        {
            "payment_type": "Vendor Payment",
            "payee_name": "Test Supplier",
            "amount": 1000.0,
            "payment_mode": "Bank Transfer",
        },
        "Tester",
    )
    assert vid.startswith("PV")
    parts = vno.split("-")
    assert len(parts) == 3
    assert parts[0] == "PV"
    assert parts[1].isdigit()
    assert parts[2].isdigit() and len(parts[2]) == 4


def test_editable_only_draft_prepared():
    assert voucher_is_editable("Draft")
    assert voucher_is_editable("Prepared")
    assert not voucher_is_editable("Checked")
    assert voucher_is_editable(normalize_status("Submitted", "payment_voucher"))
    assert not voucher_is_editable("Approved")


def test_workflow_transition_chain(pv_db):
    vid, _ = save_payment_voucher(
        {
            "payment_type": "Employee Payment",
            "payee_name": "Jane Doe",
            "amount": 500.0,
        },
        "Tester",
    )
    assert can_transition("Draft", "Prepared")
    ok, msg = transition("payment_voucher", vid, "Prepared", "Acct", "Accounts Manager")
    assert ok, msg
    conn = get_conn()
    row = conn.execute(
        "SELECT status FROM payment_vouchers WHERE voucher_id = ?", (vid,)
    ).fetchone()
    conn.close()
    assert normalize_status(row[0], "payment_voucher") == "Prepared"
