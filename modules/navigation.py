"""ERP menu tree — sidebar sections and page keys."""

from __future__ import annotations

from modules.roles import is_super_admin, resolve_role_pages

# (page_key, label)
MENU_DASHBOARD = ("dashboard", "Dashboard")

MENU_SECTIONS = [
    (
        "masters",
        "Masters",
        [
            ("masters_company", "Company"),
            ("masters_projects", "Projects"),
            ("masters_vendors", "Vendors"),
            ("masters_employees", "Employees"),
            ("masters_accounts", "Accounts Master"),
            ("masters_users", "Users"),
        ],
    ),
    (
        "finance",
        "Finance",
        [
            ("fin_expense_entry", "Expense Entry"),
            ("fin_purchase_invoice", "Purchase Invoice"),
            ("fin_petty_cash", "Petty Cash"),
            ("fin_payments", "Payments"),
            ("fin_receipts", "Receipts"),
            ("fin_journal", "Journal Voucher"),
            ("fin_creditors", "Creditors"),
        ],
    ),
    (
        "gst_tds",
        "GST & TDS",
        [
            ("gst_register", "GST Register"),
            ("gst_payment", "GST Payment"),
            ("tds_register", "TDS Register"),
            ("tds_payment", "TDS Payment"),
        ],
    ),
    (
        "subcontractor",
        "Subcontractor",
        [
            ("sub_work_orders", "Work Orders"),
            ("sub_bill_entry", "Bill Entry"),
            ("sub_payments", "Payments"),
            ("sub_security", "Security Deposit"),
        ],
    ),
    (
        "inventory",
        "Inventory",
        [
            ("inv_purchase", "Purchase"),
            ("inv_stock", "Stock"),
            ("inv_material_issue", "Material Issue"),
            ("inv_tools", "Tools"),
        ],
    ),
    (
        "assets",
        "Assets",
        [
            ("asset_register", "Asset Register"),
            ("asset_transfer", "Asset Transfer"),
            ("asset_depreciation", "Depreciation"),
        ],
    ),
    (
        "payroll",
        "Payroll",
        [
            ("pay_attendance", "Attendance"),
            ("pay_payroll", "Payroll"),
            ("pay_payslips", "Payslips"),
        ],
    ),
    (
        "projects",
        "Projects",
        [
            ("proj_boq", "BOQ"),
            ("proj_budget", "Budget"),
            ("proj_cost_control", "Cost Control"),
            ("proj_progress", "Progress"),
        ],
    ),
    (
        "reports",
        "Reports",
        [
            ("rpt_financial", "Financial"),
            ("rpt_profit_loss", "Profit & Loss"),
            ("rpt_balance_sheet", "Balance Sheet"),
            ("rpt_gst", "GST"),
            ("rpt_tds", "TDS"),
            ("rpt_project", "Project"),
            ("rpt_inventory", "Inventory"),
            ("rpt_payroll", "Payroll"),
        ],
    ),
    (
        "approvals",
        "Approvals",
        [
            ("appr_pending", "Pending"),
            ("appr_returned", "Returned"),
            ("appr_approved", "Approved"),
            ("appr_rejected", "Rejected"),
        ],
    ),
]

# Legacy flat page keys → new leaf keys (after login / bookmarks)
LEGACY_PAGE_MAP = {
    "employee_management": "masters_employees",
    "attendance": "pay_attendance",
    "payroll": "pay_payroll",
    "finance": "fin_expense_entry",
    "store": "inv_purchase",
    "clients_projects": "masters_projects",
    "subcontractors": "sub_work_orders",
    "dpr": "proj_progress",
    "billing": "rpt_financial",
    "reports": "rpt_financial",
    "settings": "masters_accounts",
    "payments": "fin_payments",
    "expenses": "fin_expense_entry",
    "clients": "masters_projects",
    "projects": "masters_projects",
}


def all_page_keys() -> set[str]:
    keys = {MENU_DASHBOARD[0]}
    for _sid, _label, items in MENU_SECTIONS:
        keys.update(k for k, _ in items)
    return keys


def page_label(page_key: str) -> str:
    if page_key == MENU_DASHBOARD[0]:
        return MENU_DASHBOARD[1]
    for _sid, _label, items in MENU_SECTIONS:
        for key, label in items:
            if key == page_key:
                return label
    return page_key.replace("_", " ").title()


def section_for_page(page_key: str) -> str | None:
    for section_id, _label, items in MENU_SECTIONS:
        if any(k == page_key for k, _ in items):
            return section_id
    return None


def normalize_page_key(page_key: str | None) -> str:
    if not page_key:
        return MENU_DASHBOARD[0]
    return LEGACY_PAGE_MAP.get(page_key, page_key)


_ACCOUNTS_MANAGER_PAGES = {
    "dashboard",
    "masters_projects",
    "masters_vendors",
    "masters_accounts",
    "fin_expense_entry",
    "fin_purchase_invoice",
    "fin_petty_cash",
    "fin_payments",
    "fin_receipts",
    "fin_journal",
    "fin_creditors",
    "gst_register",
    "gst_payment",
    "tds_register",
    "tds_payment",
    "rpt_financial",
    "rpt_profit_loss",
    "rpt_balance_sheet",
    "rpt_gst",
    "rpt_tds",
    "appr_pending",
    "appr_returned",
}

_ACCOUNTS_EXECUTIVE_PAGES = {
    "dashboard",
    "masters_projects",
    "masters_vendors",
    "fin_expense_entry",
    "fin_purchase_invoice",
    "fin_petty_cash",
    "fin_payments",
    "fin_receipts",
    "appr_pending",
}

_HR_PAYROLL_PAGES = {
    "dashboard",
    "masters_employees",
    "masters_company",
    "pay_attendance",
    "pay_payroll",
    "pay_payslips",
    "rpt_payroll",
}

_STORE_KEEPER_PAGES = {
    "dashboard",
    "masters_projects",
    "inv_purchase",
    "inv_stock",
    "inv_material_issue",
    "inv_tools",
    "rpt_inventory",
}

_PROJECT_MANAGER_PAGES = {
    "dashboard",
    "masters_projects",
    "fin_expense_entry",
    "fin_petty_cash",
    "inv_purchase",
    "proj_boq",
    "proj_budget",
    "proj_cost_control",
    "proj_progress",
    "rpt_project",
    "appr_pending",
    "appr_returned",
    "appr_approved",
    "appr_rejected",
}

_SITE_ENGINEER_PAGES = {
    "dashboard",
    "masters_projects",
    "fin_expense_entry",
    "fin_petty_cash",
    "inv_purchase",
    "sub_work_orders",
    "proj_progress",
}

ROLE_PAGE_ACCESS: dict[str, set[str]] = {
    "Admin": all_page_keys(),
    "HR & Payroll": set(_HR_PAYROLL_PAGES),
    "HR": set(_HR_PAYROLL_PAGES),
    "MD": all_page_keys(),
    "Super Admin": all_page_keys(),
    "Accountant": set(_ACCOUNTS_MANAGER_PAGES),
    "Accounts Manager": set(_ACCOUNTS_MANAGER_PAGES),
    "Accounts Executive": set(_ACCOUNTS_EXECUTIVE_PAGES),
    "Project Manager": set(_PROJECT_MANAGER_PAGES),
    "Site Engineer": set(_SITE_ENGINEER_PAGES),
    "Store Keeper": set(_STORE_KEEPER_PAGES),
}


def allowed_pages_for_role(role: str) -> set[str]:
    if is_super_admin(role):
        return all_page_keys()
    canonical = resolve_role_pages(role)
    return ROLE_PAGE_ACCESS.get(canonical, ROLE_PAGE_ACCESS.get(role, {MENU_DASHBOARD[0]}))
