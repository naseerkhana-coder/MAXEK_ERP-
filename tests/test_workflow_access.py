"""Tests for Maker / Checker / Approver workflow access tags."""

from modules.workflow_access import (
    check_workflow_access_for_step,
    get_user_workflow_access,
)


def test_auto_access_allows_any_step(tmp_db):
    ok, msg = check_workflow_access_for_step("user1", "Site Engineer", "Checked")
    assert ok is True
    assert msg == ""


def test_maker_cannot_check(tmp_db):
    from modules.database import get_conn
    from modules.user_account import ensure_user_account_schema

    ensure_user_account_schema()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO users(user_id, full_name, username, password, role, workflow_role)
        VALUES ('U1', 'Site User', 'site1', 'x', 'Site Engineer', 'Maker')
        """
    )
    conn.commit()
    conn.close()

    assert get_user_workflow_access("site1") == "Maker"
    ok_prepare, _ = check_workflow_access_for_step("site1", "Site Engineer", "Prepared")
    ok_check, err = check_workflow_access_for_step("site1", "Site Engineer", "Checked")
    assert ok_prepare is True
    assert ok_check is False
    assert "Checker" in err


def test_checker_cannot_approve(tmp_db):
    from modules.database import get_conn
    from modules.user_account import ensure_user_account_schema

    ensure_user_account_schema()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO users(user_id, full_name, username, password, role, workflow_role)
        VALUES ('U2', 'Accounts', 'acc1', 'x', 'Accounts Executive', 'Checker')
        """
    )
    conn.commit()
    conn.close()

    ok, _ = check_workflow_access_for_step("acc1", "Accounts Executive", "Checked")
    denied, err = check_workflow_access_for_step("acc1", "Accounts Executive", "Approved")
    assert ok is True
    assert denied is False
    assert "Approver" in err


def test_md_bypasses_workflow_tag(tmp_db):
    from modules.database import get_conn
    from modules.user_account import ensure_user_account_schema

    ensure_user_account_schema()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO users(user_id, full_name, username, password, role, workflow_role)
        VALUES ('U3', 'Owner', 'md1', 'x', 'MD', 'Maker')
        """
    )
    conn.commit()
    conn.close()

    ok, _ = check_workflow_access_for_step("md1", "MD", "Approved")
    assert ok is True
