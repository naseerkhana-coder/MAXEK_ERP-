"""ERP role definitions and permission helpers."""

from __future__ import annotations

ERP_USER_ROLES = [
    "Super Admin",
    "Admin",
    "MD",
    "HR & Payroll",
    "HR",
    "Accountant",
    "Accounts Manager",
    "Accounts Executive",
    "Project Manager",
    "Site Engineer",
    "Store Keeper",
    "Client",
]

CLIENT_PORTAL_ROLE = "Client"

SUPER_ADMIN_ROLES = frozenset({"Super Admin", "Admin", "MD"})
ACCOUNTS_MANAGER_ROLES = frozenset({"Admin", "Super Admin", "MD", "Accountant", "Accounts Manager"})
ACCOUNTS_EXECUTIVE_ROLES = frozenset({"Accounts Executive"})
ACCOUNTS_STAFF_ROLES = ACCOUNTS_MANAGER_ROLES | ACCOUNTS_EXECUTIVE_ROLES
MANAGEMENT_ROLES = frozenset({"Super Admin", "Admin", "MD"})
SITE_ROLES = frozenset({"Site Engineer", "Project Manager"})
PROJECT_MANAGER_ROLES = frozenset({"Project Manager"})
SITE_ENGINEER_ROLES = frozenset({"Site Engineer"})
STORE_KEEPER_ROLES = frozenset({"Store Keeper"})
HR_PAYROLL_ROLES = frozenset({"HR & Payroll", "HR"})

COMPANY_FINANCIAL_REPORT_PAGES = frozenset(
    {"acc_trial_balance", "acc_pl", "acc_balance_sheet", "rpt_cash_flow"}
)
SUPPLIER_PAYMENT_PAGES = frozenset(
    {
        "acc_payment",
        "purch_invoice",
        "acc_outstanding",
        "purch_vendor_payment",
        "proj_wo_sub",
    }
)
FINANCE_MODULE_SECTIONS = frozenset({"accounts", "petty_cash", "purchase"})

ROLE_DISPLAY_NAMES = {
    "Super Admin": "Super Admin (Owner / MD)",
    "MD": "Super Admin (Owner / MD)",
    "Admin": "System Admin",
}


def display_role_name(role: str) -> str:
    return ROLE_DISPLAY_NAMES.get(role or "", role or "User")


def normalize_role(role: str) -> str:
    """Map legacy stored roles to permission groups."""
    if role in {"Super Admin", "MD"}:
        return role
    return role or "Admin"


def is_super_admin(role: str) -> bool:
    return role in SUPER_ADMIN_ROLES


def is_accounts_manager(role: str) -> bool:
    return role in ACCOUNTS_MANAGER_ROLES


def is_accounts_executive(role: str) -> bool:
    return role in ACCOUNTS_EXECUTIVE_ROLES


def is_accounts_staff(role: str) -> bool:
    return role in ACCOUNTS_STAFF_ROLES


def can_manage_users(role: str) -> bool:
    """Create and manage login users — Super Admin / Owner / MD only."""
    return is_super_admin(role)


def can_approve_payments(role: str) -> bool:
    """Final payment and expense approval authority."""
    return is_super_admin(role) or role in {"Accounts Manager", "Accountant"}


def can_verify_finance(role: str) -> bool:
    """Verify invoices / site expenses (accounts check, not final approval)."""
    return role in ACCOUNTS_STAFF_ROLES


def can_settle_finance(role: str) -> bool:
    """Process payments and mark transactions settled."""
    return role in ACCOUNTS_MANAGER_ROLES


def can_create_payment_vouchers(role: str) -> bool:
    return role in ACCOUNTS_STAFF_ROLES | MANAGEMENT_ROLES


def can_delete_approved_finance(role: str) -> bool:
    return is_super_admin(role)


def is_management(role: str) -> bool:
    return role in MANAGEMENT_ROLES


def is_site_role(role: str) -> bool:
    return role in SITE_ROLES


def can_view_all_projects(role: str) -> bool:
    return is_super_admin(role) or role in {
        "Accountant",
        "Accounts Manager",
        "Accounts Executive",
        "Project Manager",
    }


def can_access_dpr_measurement_module(role: str) -> bool:
    """Daily Progress (DPR) and Measurement Book — Engineer, PM, Owner/MD."""
    return (
        is_super_admin(role)
        or is_management(role)
        or is_site_role(role)
        or role in {"General Manager", "Managing Director", "Admin"}
    )


def can_access_profitability_dashboard(role: str) -> bool:
    """Owner / MD / GM / Project Manager — PM scoped to assigned projects in UI."""
    if is_super_admin(role) or is_management(role):
        return True
    if is_project_manager(role):
        return True
    return (role or "").strip() in {"General Manager", "Managing Director"}


def can_view_financial_statements(role: str) -> bool:
    return is_super_admin(role) or role in {"Accountant", "Accounts Manager"}


def is_project_manager(role: str) -> bool:
    return role in PROJECT_MANAGER_ROLES


def is_site_engineer(role: str) -> bool:
    return role in SITE_ENGINEER_ROLES


def is_store_keeper(role: str) -> bool:
    return role in STORE_KEEPER_ROLES


def is_hr_payroll(role: str) -> bool:
    return role in HR_PAYROLL_ROLES


def can_approve_project_expenses(role: str) -> bool:
    return is_project_manager(role) or is_super_admin(role)


def can_approve_material_requests(role: str) -> bool:
    return is_project_manager(role) or is_super_admin(role)


def can_request_material(role: str) -> bool:
    return is_site_engineer(role) or is_project_manager(role) or is_super_admin(role)


def can_issue_materials(role: str) -> bool:
    return is_store_keeper(role) or is_super_admin(role)


def can_receive_materials(role: str) -> bool:
    return is_store_keeper(role) or is_super_admin(role)


def can_maintain_stock(role: str) -> bool:
    return is_store_keeper(role) or is_super_admin(role)


def is_client_role(role: str) -> bool:
    return role == CLIENT_PORTAL_ROLE


def can_access_internal_erp(role: str) -> bool:
    return not is_client_role(role)


def can_access_finance_module(role: str) -> bool:
    return not is_store_keeper(role) and not is_client_role(role)


def can_access_supplier_payments(role: str) -> bool:
    return not is_hr_payroll(role)


def can_prepare_workflow(role: str, entity_type: str = "") -> bool:
    """Submit draft documents (Draft → Prepared)."""
    if is_super_admin(role):
        return True
    if entity_type in {"staff_payroll", "worker_payroll"}:
        return is_hr_payroll(role) or role in ACCOUNTS_STAFF_ROLES
    if entity_type == "material_request":
        return can_request_material(role) or is_store_keeper(role)
    if entity_type in {
        "site_expense",
        "petty_cash",
        "petty_cash_fund_request",
        "vendor_bill",
        "direct_payment",
        "payment_voucher",
    }:
        return is_site_role(role) or is_accounts_staff(role)
    if entity_type in {"client_bill", "subcontractor_bill"}:
        return is_accounts_staff(role) or is_project_manager(role)
    if entity_type == "purchase_order":
        return is_store_keeper(role) or is_accounts_staff(role) or is_project_manager(role)
    return is_site_role(role) or is_hr_payroll(role) or is_accounts_staff(role)


def can_check_workflow(role: str, entity_type: str = "") -> bool:
    """Verify submitted documents (Prepared → Checked)."""
    if is_super_admin(role):
        return True
    if entity_type in {"staff_payroll", "worker_payroll"}:
        return is_hr_payroll(role) or is_accounts_staff(role)
    if entity_type in {
        "site_expense",
        "petty_cash",
        "petty_cash_fund_request",
        "vendor_bill",
        "direct_payment",
        "payment_voucher",
        "purchase_order",
    }:
        return can_verify_finance(role) or is_project_manager(role)
    if entity_type in {"client_bill", "subcontractor_bill"}:
        return can_verify_finance(role) or is_project_manager(role)
    if entity_type == "material_request":
        return is_project_manager(role) or is_store_keeper(role)
    return can_verify_finance(role) or is_project_manager(role)


def can_approve_workflow(role: str, entity_type: str = "") -> bool:
    """Final business approval (Checked → Approved)."""
    if is_super_admin(role):
        return True
    if entity_type in {"staff_payroll", "worker_payroll"}:
        return is_management(role) or is_accounts_manager(role)
    if entity_type in {"site_expense", "petty_cash"}:
        return is_project_manager(role) or can_approve_payments(role)
    if entity_type in {
        "client_bill",
        "subcontractor_bill",
        "vendor_bill",
        "purchase_order",
        "payment_voucher",
        "petty_cash_fund_request",
    }:
        return can_approve_payments(role) or is_management(role) or is_project_manager(role)
    return can_approve_payments(role) or is_management(role)


def can_release_payment_workflow(role: str) -> bool:
    """Release payment after approval (Approved → Payment Released)."""
    return can_settle_finance(role) or is_super_admin(role)


def can_mark_paid_workflow(role: str) -> bool:
    """Mark document paid (Payment Released → Paid)."""
    return can_settle_finance(role) or is_accounts_executive(role) or is_super_admin(role)


def can_edit_site_expense(role: str, status: str, creator: str, current_user: str) -> bool:
    """Site engineers may only edit their own draft/returned expenses."""
    if is_site_engineer(role):
        return status in {"Draft", "Returned"} and creator == current_user
    if status in {"Draft", "Returned"} and (
        creator == current_user or can_verify_finance(role) or is_super_admin(role)
    ):
        return True
    if status == "Submitted" and can_verify_finance(role):
        return True
    if status in {"Approved", "PM Approved", "Verified"} and can_delete_approved_finance(role):
        return True
    return False


def resolve_role_pages(role: str) -> str:
    """Map legacy stored role names to canonical permission keys."""
    if role == "Accountant":
        return "Accounts Manager"
    if role == "HR":
        return "HR & Payroll"
    return role or "Admin"
