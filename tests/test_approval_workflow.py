"""Tests for standard MAXEK ERP approval workflow."""

from modules.approval_workflow import (
    STATUS_LEGACY_MAP,
    VALID_TRANSITIONS,
    can_transition,
    normalize_status,
    status_for_storage,
)
from modules.roles import (
    can_approve_workflow,
    can_check_workflow,
    can_mark_paid_workflow,
    can_prepare_workflow,
    can_release_payment_workflow,
)


def test_normalize_legacy_expense_statuses():
    assert normalize_status("Submitted", "site_expense") == "Prepared"
    assert normalize_status("Verified", "site_expense") == "Checked"
    assert normalize_status("PM Approved", "site_expense") == "Checked"
    assert normalize_status("Released", "petty_cash") == "Payment Released"
    assert normalize_status("Calculated", "worker_payroll") == "Prepared"
    assert normalize_status("Submitted to MD", "staff_payroll") == "Prepared"
    assert normalize_status("MD Approved", "staff_payroll") == "Approved"


def test_valid_transition_chain():
    assert can_transition("Draft", "Prepared")
    assert can_transition("Prepared", "Checked")
    assert can_transition("Checked", "Approved")
    assert can_transition("Approved", "Payment Released")
    assert can_transition("Payment Released", "Paid")
    assert not can_transition("Draft", "Approved")
    assert not can_transition("Paid", "Draft")


def test_status_write_alias_material():
    assert status_for_storage("material_request", "Prepared") == "Pending"
    assert status_for_storage("material_request", "Paid") == "Issued"


def test_role_guards_accounts_executive():
    role = "Accounts Executive"
    assert can_check_workflow(role, "site_expense")
    assert can_mark_paid_workflow(role)
    assert not can_approve_workflow(role, "staff_payroll")


def test_role_guards_hr():
    role = "HR & Payroll"
    assert can_prepare_workflow(role, "staff_payroll")
    assert can_check_workflow(role, "worker_payroll")


def test_role_guards_md():
    role = "MD"
    assert can_approve_workflow(role, "staff_payroll")
    assert can_release_payment_workflow(role)


def test_legacy_map_covers_common_values():
    for legacy in ("Submitted", "Verified", "Calculated", "Pending", "Released"):
        assert legacy in STATUS_LEGACY_MAP


def test_transition_graph_keys():
    assert set(VALID_TRANSITIONS.keys()) >= {"Draft", "Prepared", "Checked", "Approved", "Payment Released", "Paid"}
