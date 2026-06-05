"""ERP menu tree — MAXEK INDIA Construction ERP sidebar sections and page keys.

Workflow:
  Client → Project → Site → BOQ → Work Order → Purchase → Store → Accounts → Billing → Reports
  Sub Contractor → Work Order → Attendance → Billing → Payment
  Site Petty Cash → Expense Entry → Invoice Upload → Accounts Verification → Approval → Settlement
"""

from __future__ import annotations

from modules.roles import CLIENT_PORTAL_ROLE, is_super_admin, resolve_role_pages

# Home screen (sidebar + top bar Dashboard)
MENU_DASHBOARD = ("dash_mgmt", "Dashboard", "🏠")

# Top bar: 5–7 primary modules only — detail lives in the left sidebar
TopNavItem = tuple[str, str, str]  # section_id, label, icon
TOP_NAV_ITEMS: list[TopNavItem] = [
    ("dashboard", "Dashboard", "🏠"),
    ("projects", "Projects", "🏗️"),
    ("procurement", "Procurement", "🛒"),
    ("inventory", "Inventory", "📦"),
    ("accounts", "Accounts", "💰"),
    ("reports", "Reports", "📊"),
    ("settings", "Settings", "⚙️"),
]

SECTION_DEFAULT_PAGE: dict[str, str] = {
    "dashboard": "dash_mgmt",
    "crm": "master_client",
    "projects": "proj_create",
    "tender": "proj_boq",
    "procurement": "purch_requisition",
    "inventory": "store_receipt",
    "hr": "master_employee",
    "accounts": "petty_dashboard",
    "contracts": "proj_wo_sub",
    "letters": "doc_incoming",
    "reports": "rpt_proj_status",
    "settings": "settings_users",
    "account": "account_profile",
}

# Available to every authenticated role (profile and password).
ACCOUNT_PAGE_KEYS = frozenset({"account_profile"})

QUICK_ADD_ACTIONS: list[tuple[str, str, str]] = [
    ("purch_requisition", "Material Request", "📋"),
    ("purch_order", "Purchase Order", "🛒"),
    ("proj_dpr_daily", "Daily Report", "📝"),
    ("petty_expense", "Site Expense", "💵"),
    ("store_issue", "Material Issue", "📦"),
    ("acc_payment", "Payment", "💳"),
    ("proj_wo_sub", "Subcontractor WO", "👷"),
]

# MenuGroup: (group_id, group_label | None, [(page_key, label), ...])
MenuItem = tuple[str, str]
MenuGroup = tuple[str, str | None, list[MenuItem]]
MenuSection = tuple[str, str, str, list[MenuGroup]]

MENU_SECTIONS: list[MenuSection] = [
    (
        "crm",
        "CRM",
        "👥",
        [
            (
                "crm_all",
                None,
                [
                    ("master_client_create", "Leads"),
                    ("master_client", "Clients"),
                    ("doc_followup", "Follow-up"),
                ],
            ),
        ],
    ),
    (
        "projects",
        "Projects",
        "🏗️",
        [
            (
                "projects_all",
                None,
                [
                    ("proj_create", "Project Creation"),
                    ("proj_dpr_weekly", "Project Progress"),
                    ("doc_site", "Site Photos"),
                    ("proj_dpr_daily", "Daily Progress (DPR)"),
                    ("proj_measurement_book", "Measurement Book"),
                    ("proj_material_planning", "Material Planning"),
                    ("proj_profitability", "Project Profitability"),
                    ("portal_admin_assign", "Client Portal Access"),
                ],
            ),
        ],
    ),
    (
        "tender",
        "Tender & Estimation",
        "📋",
        [
            (
                "tender_all",
                None,
                [
                    ("proj_boq", "BOQ"),
                    ("proj_boq_approval", "Estimation"),
                    ("purch_quotation", "Quotation"),
                    ("purch_rfq", "Tender Submission"),
                ],
            ),
        ],
    ),
    (
        "procurement",
        "Procurement",
        "🛒",
        [
            (
                "procurement_all",
                None,
                [
                    ("purch_requisition", "Material Request"),
                    ("purch_approval", "Purchase Request"),
                    ("purch_order", "Purchase Order"),
                    ("master_vendor", "Vendor Management"),
                ],
            ),
        ],
    ),
    (
        "inventory",
        "Inventory",
        "📦",
        [
            (
                "inventory_all",
                None,
                [
                    ("store_receipt", "Material Inward"),
                    ("store_site_stock", "Stock"),
                    ("store_issue", "Material Issue"),
                    ("store_consumption_control", "Consumption Control"),
                    ("asset_register", "Asset Register"),
                ],
            ),
        ],
    ),
    (
        "hr",
        "HR & Payroll",
        "👷",
        [
            (
                "hr_all",
                None,
                [
                    ("master_employee", "Employees"),
                    ("hr_attendance", "Attendance"),
                    ("hr_leave", "Leave"),
                    ("hr_payroll", "Worker Payroll"),
                    ("hr_staff_payroll", "Staff Payroll"),
                ],
            ),
        ],
    ),
    (
        "accounts",
        "Accounts",
        "💰",
        [
            (
                "accounts_all",
                None,
                [
                    ("petty_dashboard", "Petty Cash"),
                    ("petty_request", "Fund Requests"),
                    ("petty_allocation", "Fund Issue"),
                    ("petty_expense", "Petty Expenses"),
                    ("petty_verification", "Expense Approval"),
                    ("petty_reports", "Petty Reports"),
                    ("purch_invoice", "Invoices"),
                    ("acc_payment", "Payments"),
                    ("acc_payment_voucher", "Payment Voucher"),
                    ("acc_gst_reports", "GST"),
                ],
            ),
        ],
    ),
    (
        "contracts",
        "Contract Management",
        "📄",
        [
            (
                "contracts_all",
                None,
                [
                    ("master_client_contract", "Main Contract"),
                    ("master_contractor_sub", "Subcontractor"),
                    ("proj_wo_sub", "Work Orders"),
                    ("proj_bill_ra", "Running Bills"),
                ],
            ),
        ],
    ),
    (
        "letters",
        "Letter & DMS",
        "📨",
        [
            (
                "letters_all",
                None,
                [
                    ("doc_incoming", "Incoming Letter"),
                    ("doc_outgoing", "Outgoing Letter"),
                    ("doc_draft", "Letter Drafting"),
                    ("doc_contract", "Documents"),
                ],
            ),
        ],
    ),
    (
        "reports",
        "Reports",
        "📊",
        [
            (
                "reports_all",
                None,
                [
                    ("rpt_receivable", "Financial Reports"),
                    ("rpt_proj_status", "Project Reports"),
                    ("dash_profitability", "Project Profitability"),
                    ("rpt_phase3", "Phase 3 Integration"),
                    ("rpt_material_planning", "Material Planning Report"),
                    ("store_reports", "Inventory Reports"),
                ],
            ),
        ],
    ),
    (
        "account",
        "My Account",
        "👤",
        [
            (
                "account_all",
                None,
                [
                    ("account_profile", "My Profile"),
                ],
            ),
        ],
    ),
    (
        "settings",
        "Settings",
        "⚙️",
        [
            (
                "settings_all",
                None,
                [
                    ("settings_users", "Users"),
                    ("settings_roles", "Permissions"),
                    ("master_branch", "Company Setup"),
                ],
            ),
        ],
    ),
]

# Routed in erp_router but hidden from the sidebar (legacy bookmarks / deep links).
ROUTER_ONLY_PAGE_KEYS = frozenset({"hr_salary_slip"})

CORRESPONDENCE_PAGES = frozenset(
    {
        "doc_incoming",
        "doc_register",
        "doc_assign",
        "doc_followup",
        "doc_reply",
        "doc_outgoing",
        "doc_draft",
        "doc_approval",
        "doc_email",
        "doc_whatsapp",
    }
)

LEGACY_PAGE_MAP = {
    "dashboard": "dash_mgmt",
    "employee_management": "master_employee",
    "attendance": "hr_attendance",
    "payroll": "hr_payroll",
    "finance": "petty_expense",
    "store": "purch_order",
    "clients_projects": "proj_create",
    "subcontractors": "proj_wo_sub",
    "dpr": "proj_dpr_daily",
    "billing": "proj_bill_client",
    "reports": "rpt_proj_status",
    "settings": "settings_erp",
    "payments": "acc_payment",
    "expenses": "petty_expense",
    "clients": "master_client",
    "projects": "proj_create",
    "office": "doc_incoming",
    "masters_company": "master_branch",
    "masters_vendors": "master_vendor",
    "masters_employees": "master_employee",
    "masters_accounts": "acc_coa",
    "masters_users": "settings_users",
    "masters_projects": "proj_create",
    "proj_progress": "proj_dpr_daily",
    "boq_billing": "proj_bill_client",
    "inv_purchase": "purch_order",
    "fin_purchase_invoice": "purch_invoice",
    "inv_stock": "store_receipt",
    "inv_material_issue": "store_issue",
    "inv_tools": "master_equipment",
    "site_dpr": "proj_dpr_daily",
    "measurement_book": "proj_measurement_book",
    "fin_expense_entry": "petty_expense",
    "fin_petty_cash": "petty_dashboard",
    "pay_attendance": "hr_attendance",
    "sub_work_orders": "proj_wo_sub",
    "sub_bill_entry": "proj_wo_sub",
    "sub_payments": "purch_vendor_payment",
    "sub_security": "proj_wo_sub",
    "fin_payments": "acc_payment",
    "fin_receipts": "acc_receipt",
    "fin_journal": "acc_journal",
    "fin_creditors": "acc_outstanding",
    "gst_register": "acc_gst_reports",
    "gst_payment": "acc_gst_purchase",
    "tds_register": "acc_gst_reports",
    "tds_payment": "acc_gst_purchase",
    "pay_payroll": "hr_payroll",
    "pay_payslips": "hr_salary_slip",
    "asset_transfer": "asset_allocation",
    "asset_depreciation": "asset_costing",
    "proj_budget": "proj_site_budget",
    "proj_cost_control": "rpt_cost_analysis",
    "crm_clients": "master_client",
    "crm_projects": "proj_create",
    "corr_dashboard": "doc_incoming",
    "corr_incoming": "doc_incoming",
    "corr_outgoing": "doc_outgoing",
    "corr_drafting": "doc_draft",
    "corr_email": "doc_email",
    "corr_approval": "doc_approval",
    "corr_tracking": "doc_followup",
    "corr_authority": "doc_assign",
    "corr_archive": "doc_contract",
    "appr_pending": "dash_pending",
    "appr_returned": "appr_petty",
    "appr_approved": "appr_purchase",
    "appr_rejected": "appr_payment",
    "rpt_financial": "acc_trial_balance",
    "rpt_profit_loss": "acc_pl",
    "rpt_balance_sheet": "acc_balance_sheet",
    "rpt_tds": "acc_gst_reports",
    "rpt_project": "rpt_proj_status",
    "rpt_inventory": "store_reports",
    "settings_system": "settings_erp",
    "settings_dashboard": "dash_mgmt",
}


def section_groups(section: MenuSection) -> list[MenuGroup]:
    return section[3]


def iter_section_items(groups: list[MenuGroup]) -> list[MenuItem]:
    items: list[MenuItem] = []
    for _gid, _glbl, group_items in groups:
        items.extend(group_items)
    return items


def group_for_page(page_key: str) -> tuple[str, str] | None:
    for section_id, _label, _icon, groups in MENU_SECTIONS:
        for group_id, group_label, items in groups:
            if any(k == page_key for k, _ in items):
                return section_id, group_id
    return None


def all_page_keys() -> set[str]:
    keys = {MENU_DASHBOARD[0]} | set(ROUTER_ONLY_PAGE_KEYS) | set(_CLIENT_PORTAL_PAGES) | _INTERNAL_PORTAL_ADMIN_PAGES
    for _sid, _label, _icon, groups in MENU_SECTIONS:
        keys.update(k for k, _ in iter_section_items(groups))
    return keys


def pages_in_sections(*section_ids: str) -> set[str]:
    wanted = set(section_ids)
    keys: set[str] = set()
    for section_id, _label, _icon, groups in MENU_SECTIONS:
        if section_id in wanted:
            keys.update(k for k, _ in iter_section_items(groups))
    return keys


def page_label(page_key: str) -> str:
    _portal_labels = {
        "portal_dash": "Client Dashboard",
        "portal_projects": "Projects",
        "portal_invoices": "Invoices",
        "portal_bills": "Bills for Approval",
        "portal_documents": "Documents",
        "portal_progress": "Progress Reports",
        "portal_payments": "Payment History",
        "portal_admin_assign": "Client Portal Access",
    }
    if page_key in _portal_labels:
        return _portal_labels[page_key]
    if page_key == "hr_salary_slip":
        return "Worker Payroll — Salary Slip"
    if page_key == MENU_DASHBOARD[0]:
        return MENU_DASHBOARD[1]
    if page_key in {"dash_profitability", "proj_profitability"}:
        return "Project Profitability"
    for _sid, _label, _icon, groups in MENU_SECTIONS:
        for key, label in iter_section_items(groups):
            if key == page_key:
                return label
    return page_key.replace("_", " ").title()


def section_for_page(page_key: str) -> str | None:
    if page_key == MENU_DASHBOARD[0]:
        return "dashboard"
    for section_id, _label, _icon, groups in MENU_SECTIONS:
        if any(k == page_key for k, _ in iter_section_items(groups)):
            return section_id
    return None


def default_page_for_section(section_id: str) -> str:
    return SECTION_DEFAULT_PAGE.get(section_id, MENU_DASHBOARD[0])


def top_nav_section_active(section_id: str, page_key: str) -> bool:
    if section_id == "dashboard":
        return page_key == MENU_DASHBOARD[0] or page_key.startswith("dash_")
    current = section_for_page(page_key)
    return current == section_id


def normalize_page_key(page_key: str | None) -> str:
    if not page_key:
        return MENU_DASHBOARD[0]
    mapped = LEGACY_PAGE_MAP.get(page_key, page_key)
    if mapped in all_page_keys():
        return mapped
    return MENU_DASHBOARD[0]


_ACCOUNTS_MANAGER_PAGES = (
    pages_in_sections("accounts", "procurement", "reports", "contracts", "letters")
    | {MENU_DASHBOARD[0], "dash_pending", "dash_notifications", "dash_profitability", "proj_profitability"}
    | {
        "master_vendor",
        "master_client",
        "proj_create",
        "proj_site_budget",
        "rpt_cost_analysis",
        "acc_outstanding",
        "purch_invoice",
        "purch_vendor_payment",
        "petty_dashboard",
        "petty_request",
        "petty_allocation",
        "petty_reports",
        "petty_verification",
        "petty_settlement",
        "acc_receipt",
        "acc_journal",
    }
)

_ACCOUNTS_EXECUTIVE_PAGES = pages_in_sections("accounts", "procurement") | {
    MENU_DASHBOARD[0],
    "dash_pending",
    "acc_receipt",
    "acc_payment",
    "acc_payment_voucher",
    "purch_invoice",
    "petty_expense",
    "petty_dashboard",
    "petty_request",
    "petty_verification",
    "proj_create",
    "master_vendor",
}

_HR_PAYROLL_PAGES = pages_in_sections("hr", "reports") | {
    MENU_DASHBOARD[0],
    "master_employee",
    "master_labour",
    "master_branch",
    "master_department",
    "appr_leave",
    "hr_staff_payroll",
    "hr_salary_slip",
    "hr_reports",
}

_STORE_KEEPER_PAGES = pages_in_sections("inventory", "procurement", "reports") | {
    MENU_DASHBOARD[0],
    "proj_create",
    "proj_material_planning",
    "store_consumption_control",
    "master_material",
    "master_equipment",
    "purch_grn",
    "store_return",
}

_PROJECT_MANAGER_PAGES = (
    pages_in_sections("projects", "procurement", "inventory", "contracts", "letters", "reports", "tender", "crm")
    | {MENU_DASHBOARD[0], "dash_pending", "dash_notifications", "dash_profitability", "proj_profitability"}
    | {
        "master_client",
        "master_contractor_sub",
        "proj_wo_sub",
        "petty_dashboard",
        "petty_request",
        "petty_expense",
        "hr_labour_attendance",
        "appr_leave",
        "appr_purchase",
        "appr_work_order",
    }
)

_SITE_ENGINEER_PAGES = pages_in_sections("projects", "inventory", "accounts", "tender") | {
    MENU_DASHBOARD[0],
    "proj_create",
    "proj_material_planning",
    "store_consumption_control",
    "proj_wo_sub",
    "proj_wo_internal",
    "purch_requisition",
    "purch_order",
    "hr_labour_attendance",
    "petty_expense",
    "petty_dashboard",
    "petty_request",
    "doc_site",
}

_CLIENT_PORTAL_PAGES = frozenset(
    {
        "portal_dash",
        "portal_projects",
        "portal_invoices",
        "portal_bills",
        "portal_documents",
        "portal_progress",
        "portal_payments",
        "account_profile",
    }
)

_INTERNAL_PORTAL_ADMIN_PAGES = frozenset({"portal_admin_assign"})

ROLE_PAGE_ACCESS: dict[str, set[str]] = {
    "Admin": set(),  # resolved via _full_router_page_keys in allowed_pages_for_role
    "HR & Payroll": set(_HR_PAYROLL_PAGES),
    "HR": set(_HR_PAYROLL_PAGES),
    "MD": set(),
    "Super Admin": set(),
    "Accountant": set(_ACCOUNTS_MANAGER_PAGES) | CORRESPONDENCE_PAGES,
    "Accounts Manager": set(_ACCOUNTS_MANAGER_PAGES) | CORRESPONDENCE_PAGES,
    "Accounts Executive": set(_ACCOUNTS_EXECUTIVE_PAGES),
    "Project Manager": set(_PROJECT_MANAGER_PAGES) | _INTERNAL_PORTAL_ADMIN_PAGES,
    "Site Engineer": set(_SITE_ENGINEER_PAGES),
    "Store Keeper": set(_STORE_KEEPER_PAGES),
    CLIENT_PORTAL_ROLE: set(_CLIENT_PORTAL_PAGES),
}


def _full_router_page_keys() -> set[str]:
    from modules.erp_router import PAGE_HANDLERS

    return set(PAGE_HANDLERS.keys())


def allowed_pages_for_role(role: str) -> set[str]:
    if role == CLIENT_PORTAL_ROLE:
        return set(_CLIENT_PORTAL_PAGES)
    if is_super_admin(role):
        return _full_router_page_keys() | ACCOUNT_PAGE_KEYS
    canonical = resolve_role_pages(role)
    pages = ROLE_PAGE_ACCESS.get(canonical, ROLE_PAGE_ACCESS.get(role, {MENU_DASHBOARD[0]}))
    if canonical in ("Admin", "MD") or role in ("Admin", "MD"):
        return _full_router_page_keys() | ACCOUNT_PAGE_KEYS
    return pages | ACCOUNT_PAGE_KEYS
