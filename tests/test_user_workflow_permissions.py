"""Tests for per-user module workflow permissions."""

from modules.user_workflow_permissions import (
    CAPABILITY_CHECKER,
    CAPABILITY_MAKER,
    check_user_module_permission,
    save_user_permissions,
    user_has_module_capability,
)


def test_module_permission_enforced(tmp_db):
    from modules.database import get_conn
    from modules.user_account import ensure_user_account_schema

    ensure_user_account_schema()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO users(user_id, full_name, username, password, role)
        VALUES ('U1', 'Site', 'site1', 'x', 'Site Engineer')
        """
    )
    conn.commit()
    conn.close()

    ok, _ = save_user_permissions(
        "U1",
        "site1",
        maker_modules=["petty_cash_fund_request", "dpr"],
        checker_modules=[],
        approver_modules=[],
        handler_modules=["petty_cash_fund_request"],
        actor="Admin",
    )
    assert ok is True
    assert user_has_module_capability("site1", "petty_cash_fund_request", CAPABILITY_MAKER)

    allowed, _ = check_user_module_permission("site1", "petty_cash_fund_request", "Prepared", "Site Engineer")
    denied, err = check_user_module_permission("site1", "petty_cash_fund_request", "Checked", "Site Engineer")
    assert allowed is True
    assert denied is False
    assert "Checker" in err

    allowed_dpr, _ = check_user_module_permission("site1", "dpr", "Prepared", "Site Engineer")
    denied_pv, _ = check_user_module_permission("site1", "payment_voucher", "Prepared", "Site Engineer")
    assert allowed_dpr is True
    assert denied_pv is False


def test_add_and_remove_module_permissions(tmp_db):
    from modules.database import get_conn
    from modules.user_account import ensure_user_account_schema
    from modules.user_workflow_permissions import (
        add_modules_for_capability,
        load_user_permissions,
        remove_modules_for_capability,
    )

    ensure_user_account_schema()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO users(user_id, full_name, username, password, role)
        VALUES ('U2', 'Accounts', 'acc1', 'x', 'Accounts')
        """
    )
    conn.commit()
    conn.close()

    ok, _ = save_user_permissions(
        "U2",
        "acc1",
        maker_modules=["petty_cash_fund_request"],
        checker_modules=[],
        approver_modules=[],
        handler_modules=[],
        actor="Admin",
    )
    assert ok is True

    ok, _ = add_modules_for_capability(
        "U2",
        "acc1",
        CAPABILITY_MAKER,
        ["dpr", "timesheet"],
        actor="Admin",
    )
    assert ok is True
    perms = load_user_permissions("U2")
    assert set(perms[CAPABILITY_MAKER]) == {
        "petty_cash_fund_request",
        "dpr",
        "timesheet",
    }

    ok, _ = add_modules_for_capability(
        "U2",
        "acc1",
        CAPABILITY_CHECKER,
        ["petty_cash_fund_request", "payment_voucher"],
        actor="Admin",
    )
    assert ok is True
    perms = load_user_permissions("U2")
    assert "payment_voucher" in perms[CAPABILITY_CHECKER]

    ok, _ = remove_modules_for_capability("U2", CAPABILITY_MAKER, ["dpr"])
    assert ok is True
    perms = load_user_permissions("U2")
    assert "dpr" not in perms[CAPABILITY_MAKER]
    assert "timesheet" in perms[CAPABILITY_MAKER]
    assert "petty_cash_fund_request" in perms[CAPABILITY_CHECKER]
