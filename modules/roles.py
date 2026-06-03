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
]

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


def can_access_finance_module(role: str) -> bool:
    return not is_store_keeper(role)


def can_access_supplier_payments(role: str) -> bool:
    return not is_hr_payroll(role)


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
