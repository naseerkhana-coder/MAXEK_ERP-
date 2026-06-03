"""ERP menu tree — MAXEK INDIA Construction ERP sidebar sections and page keys.

Workflow:
  Client → Project → Site → BOQ → Work Order → Purchase → Store → Accounts → Billing → Reports
  Sub Contractor → Work Order → Attendance → Billing → Payment
  Site Petty Cash → Expense Entry → Invoice Upload → Accounts Verification → Approval → Settlement
"""

from __future__ import annotations

from modules.roles import is_super_admin, resolve_role_pages

# Top-level quick access (Management Dashboard)
MENU_DASHBOARD = ("dash_mgmt", "Management Dashboard", "📊")

# MenuGroup: (group_id, group_label | None, [(page_key, label), ...])
MenuItem = tuple[str, str]
MenuGroup = tuple[str, str | None, list[MenuItem]]
MenuSection = tuple[str, str, str, list[MenuGroup]]

MENU_SECTIONS: list[MenuSection] = [
    (
        "dashboard",
        "Dashboard",
        "📊",
        [
            (
                "dash_overview",
                None,
                [
                    ("dash_mgmt", "Management Dashboard"),
                    ("dash_project", "Project Dashboard"),
                    ("dash_accounts", "Accounts Dashboard"),
                    ("dash_hr", "HR Dashboard"),
                    ("dash_store", "Store Dashboard"),
                    ("dash_pending", "Pending Approvals"),
                    ("dash_notifications", "Notifications"),
                    ("dash_calendar", "Calendar"),
                ],
            ),
        ],
    ),
    (
        "masters",
        "Master Management",
        "🏢",
        [
            (
                "master_client_grp",
                "Client Master",
                [
                    ("master_client", "Client Master"),
                    ("master_client_create", "Client Creation"),
                    ("master_client_contacts", "Contact Persons"),
                    ("master_client_gst", "GST Details"),
                    ("master_client_contract", "Contract Details"),
                    ("master_client_docs", "Client Documents"),
                ],
            ),
            (
                "master_contractor_grp",
                "Contractor Master",
                [
                    ("master_contractor", "Contractor Master"),
                    ("master_contractor_main", "Main Contractor Creation"),
                    ("master_contractor_sub", "Sub Contractor Creation"),
                    ("master_contractor_class", "Contractor Classification"),
                    ("master_contractor_agreement", "Agreement Upload"),
                ],
            ),
            (
                "master_vendor_grp",
                "Vendor Master",
                [
                    ("master_vendor", "Vendor Master"),
                    ("master_vendor_supplier", "Supplier Creation"),
                    ("master_vendor_service", "Service Vendor"),
                    ("master_vendor_material", "Material Vendor"),
                    ("master_vendor_rating", "Vendor Rating"),
                ],
            ),
            (
                "master_employee_grp",
                "Employee Master",
                [
                    ("master_employee", "Employee Master"),
                    ("master_employee_create", "Employee Creation"),
                    ("master_labour", "Labour Creation"),
                    ("master_staff_category", "Staff Category"),
                    ("master_designation", "Designation"),
                ],
            ),
            (
                "master_material_grp",
                "Material Master",
                [
                    ("master_material", "Material Master"),
                    ("master_material_create", "Material Creation"),
                    ("master_material_category", "Material Category"),
                    ("master_unit", "Unit Master"),
                ],
            ),
            (
                "master_equipment_grp",
                "Equipment Master",
                [
                    ("master_equipment", "Equipment Master"),
                    ("master_equipment_create", "Equipment Creation"),
                    ("master_machinery", "Machinery Register"),
                ],
            ),
            (
                "master_vehicle_grp",
                "Vehicle Master",
                [
                    ("master_vehicle", "Vehicle Master"),
                    ("master_vehicle_register", "Vehicle Register"),
                    ("master_driver", "Driver Register"),
                ],
            ),
            (
                "master_location_grp",
                "Location Master",
                [
                    ("master_location", "Location Master"),
                    ("master_branch", "Branch Creation"),
                    ("master_site", "Site Location Creation"),
                    ("master_department", "Department Creation"),
                ],
            ),
        ],
    ),
    (
        "projects",
        "Project Management",
        "🏗️",
        [
            (
                "proj_setup_grp",
                "Project Setup",
                [
                    ("proj_setup", "Project Setup"),
                    ("proj_create", "Project Creation"),
                    ("proj_code", "Project Code Generation"),
                    ("proj_client_link", "Client Linking"),
                    ("proj_contract_value", "Contract Value"),
                    ("proj_documents", "Project Documents"),
                ],
            ),
            (
                "proj_site_grp",
                "Site Management",
                [
                    ("proj_site_mgmt", "Site Management"),
                    ("proj_site_create", "Site Creation"),
                    ("proj_site_team", "Site Team Assignment"),
                    ("proj_site_budget", "Site Budget"),
                ],
            ),
            (
                "proj_boq_grp",
                "BOQ Management",
                [
                    ("proj_boq", "BOQ Entry"),
                    ("proj_boq_approval", "BOQ Approval"),
                    ("proj_boq_revision", "BOQ Revision"),
                ],
            ),
            (
                "proj_wo_grp",
                "Work Order Management",
                [
                    ("proj_wo_internal", "Internal Work Order"),
                    ("proj_wo_sub", "Sub Contractor Work Order"),
                ],
            ),
            (
                "proj_dpr_grp",
                "DPR",
                [
                    ("proj_dpr_daily", "Daily Progress Report"),
                    ("proj_dpr_weekly", "Weekly Progress Report"),
                    ("proj_dpr_monthly", "Monthly Progress Report"),
                ],
            ),
            (
                "proj_billing_grp",
                "Billing",
                [
                    ("proj_bill_client", "Client Billing"),
                    ("proj_bill_ra", "RA Bill"),
                    ("proj_bill_final", "Final Bill"),
                ],
            ),
            (
                "proj_cost_grp",
                "Project Costing",
                [
                    ("proj_cost_labour", "Labour Cost"),
                    ("proj_cost_material", "Material Cost"),
                    ("proj_cost_equipment", "Equipment Cost"),
                    ("proj_cost_overhead", "Overhead Cost"),
                    ("proj_cost_pnl", "Profit & Loss"),
                ],
            ),
        ],
    ),
    (
        "purchase",
        "Purchase Management",
        "🛒",
        [
            (
                "purchase_all",
                None,
                [
                    ("purch_requisition", "Purchase Requisition"),
                    ("purch_rfq", "RFQ Management"),
                    ("purch_quotation", "Quotation Comparison"),
                    ("purch_approval", "Purchase Approval"),
                    ("purch_order", "Purchase Order"),
                    ("purch_grn", "GRN (Goods Received Note)"),
                    ("purch_invoice", "Purchase Invoice"),
                    ("purch_vendor_payment", "Vendor Payment Tracking"),
                ],
            ),
        ],
    ),
    (
        "store",
        "Store & Inventory",
        "📦",
        [
            (
                "store_all",
                None,
                [
                    ("store_receipt", "Material Receipt"),
                    ("store_issue", "Material Issue"),
                    ("store_return", "Material Return"),
                    ("store_transfer", "Stock Transfer"),
                    ("store_adjustment", "Stock Adjustment"),
                    ("store_site_stock", "Site Wise Stock"),
                    ("store_low_stock", "Low Stock Alert"),
                    ("store_valuation", "Stock Valuation"),
                    ("store_reports", "Inventory Reports"),
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
                    ("hr_attendance", "Attendance"),
                    ("hr_leave", "Leave Management"),
                    ("hr_transfer", "Employee Transfer"),
                    ("hr_overtime", "Overtime Management"),
                    ("hr_payroll", "Payroll Processing"),
                    ("hr_salary_slip", "Salary Slip"),
                    ("hr_labour_attendance", "Labour Attendance"),
                    ("hr_reports", "HR Reports"),
                ],
            ),
        ],
    ),
    (
        "accounts",
        "Accounts & Finance",
        "💰",
        [
            (
                "acc_masters_grp",
                "Masters",
                [
                    ("acc_coa", "Chart of Accounts"),
                    ("acc_cost_center", "Cost Centers"),
                ],
            ),
            (
                "acc_txn_grp",
                "Transactions",
                [
                    ("acc_receipt", "Receipt Voucher"),
                    ("acc_payment", "Payment Voucher"),
                    ("acc_journal", "Journal Voucher"),
                    ("acc_contra", "Contra Voucher"),
                ],
            ),
            (
                "acc_banking_grp",
                "Banking",
                [
                    ("acc_bank_recon", "Bank Reconciliation"),
                    ("acc_cheque", "Cheque Management"),
                ],
            ),
            (
                "acc_gst_grp",
                "GST",
                [
                    ("acc_gst_purchase", "GST Purchase"),
                    ("acc_gst_sales", "GST Sales"),
                    ("acc_gst_reports", "GST Reports"),
                ],
            ),
            (
                "acc_reports_grp",
                "Finance Reports",
                [
                    ("acc_cash_book", "Cash Book"),
                    ("acc_bank_book", "Bank Book"),
                    ("acc_trial_balance", "Trial Balance"),
                    ("acc_pl", "P&L"),
                    ("acc_balance_sheet", "Balance Sheet"),
                    ("acc_outstanding", "Outstanding Reports"),
                ],
            ),
        ],
    ),
    (
        "petty_cash",
        "Petty Cash Management",
        "🏦",
        [
            (
                "petty_all",
                None,
                [
                    ("petty_request", "Petty Cash Request"),
                    ("petty_allocation", "Petty Cash Allocation"),
                    ("petty_expense", "Site Expense Entry"),
                    ("petty_invoice", "Invoice Upload"),
                    ("petty_verification", "Accounts Verification"),
                    ("petty_approval", "Approval Workflow"),
                    ("petty_settlement", "Settlement"),
                    ("petty_reports", "Petty Cash Reports"),
                ],
            ),
        ],
    ),
    (
        "assets",
        "Asset & Equipment Management",
        "🚜",
        [
            (
                "assets_all",
                None,
                [
                    ("asset_register", "Asset Register"),
                    ("asset_allocation", "Equipment Allocation"),
                    ("asset_fuel", "Fuel Consumption"),
                    ("asset_maintenance", "Maintenance Schedule"),
                    ("asset_breakdown", "Breakdown Register"),
                    ("asset_costing", "Equipment Costing"),
                ],
            ),
        ],
    ),
    (
        "vehicles",
        "Vehicle Management",
        "🚚",
        [
            (
                "vehicles_all",
                None,
                [
                    ("veh_allocation", "Vehicle Allocation"),
                    ("veh_trip", "Trip Sheet"),
                    ("veh_fuel", "Fuel Tracking"),
                    ("veh_service", "Service Tracking"),
                    ("veh_insurance", "Insurance Tracking"),
                    ("veh_cost", "Vehicle Cost Reports"),
                ],
            ),
        ],
    ),
    (
        "documents",
        "Document & Letter Management",
        "📄",
        [
            (
                "doc_incoming_grp",
                "Incoming Letters",
                [
                    ("doc_incoming", "Incoming Letters"),
                    ("doc_register", "Register Letter"),
                    ("doc_assign", "Assign Department"),
                    ("doc_followup", "Follow-up Tracking"),
                    ("doc_reply", "Reply Status"),
                ],
            ),
            (
                "doc_outgoing_grp",
                "Outgoing Letters",
                [
                    ("doc_outgoing", "Outgoing Letters"),
                    ("doc_draft", "Letter Drafting"),
                    ("doc_approval", "Approval"),
                    ("doc_email", "Email Sending"),
                    ("doc_whatsapp", "WhatsApp Sending"),
                ],
            ),
            (
                "doc_control_grp",
                "Document Control",
                [
                    ("doc_contract", "Contract Documents"),
                    ("doc_drawings", "Drawings"),
                    ("doc_site", "Site Documents"),
                    ("doc_legal", "Legal Documents"),
                ],
            ),
        ],
    ),
    (
        "approvals",
        "Approval Center",
        "✅",
        [
            (
                "approvals_all",
                None,
                [
                    ("appr_purchase", "Purchase Approval"),
                    ("appr_payment", "Payment Approval"),
                    ("appr_petty", "Petty Cash Approval"),
                    ("appr_leave", "Leave Approval"),
                    ("appr_work_order", "Work Order Approval"),
                    ("appr_vendor", "Vendor Approval"),
                    ("appr_client", "Client Approval"),
                    ("appr_project", "Project Approval"),
                ],
            ),
        ],
    ),
    (
        "reports",
        "Reports & MIS",
        "📈",
        [
            (
                "rpt_project_grp",
                "Project Reports",
                [
                    ("rpt_proj_status", "Project Status"),
                    ("rpt_cost_analysis", "Cost Analysis"),
                    ("rpt_budget_actual", "Budget Vs Actual"),
                ],
            ),
            (
                "rpt_accounts_grp",
                "Accounts Reports",
                [
                    ("rpt_receivable", "Receivable Reports"),
                    ("rpt_payable", "Payable Reports"),
                    ("rpt_gst", "GST Reports"),
                ],
            ),
            (
                "rpt_store_grp",
                "Store Reports",
                [
                    ("rpt_stock", "Stock Reports"),
                    ("rpt_material_consumption", "Material Consumption Reports"),
                ],
            ),
            (
                "rpt_hr_grp",
                "HR Reports",
                [
                    ("rpt_attendance", "Attendance Reports"),
                    ("rpt_payroll", "Payroll Reports"),
                ],
            ),
            (
                "rpt_mis_grp",
                "Management MIS",
                [
                    ("rpt_company_profit", "Company Profitability"),
                    ("rpt_project_profit", "Project Profitability"),
                    ("rpt_cash_flow", "Cash Flow Reports"),
                ],
            ),
        ],
    ),
    (
        "settings",
        "Settings & Administration",
        "⚙️",
        [
            (
                "settings_all",
                None,
                [
                    ("settings_users", "User Management"),
                    ("settings_roles", "Roles & Permissions"),
                    ("settings_email", "Email Configuration"),
                    ("settings_whatsapp", "WhatsApp Configuration"),
                    ("settings_number_series", "Number Series Setup"),
                    ("settings_backup", "Backup & Restore"),
                    ("settings_audit", "Audit Logs"),
                    ("settings_erp", "ERP Configuration"),
                ],
            ),
        ],
    ),
]

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
    "fin_expense_entry": "petty_expense",
    "fin_petty_cash": "petty_request",
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
    keys = {MENU_DASHBOARD[0]}
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
    if page_key == MENU_DASHBOARD[0]:
        return MENU_DASHBOARD[1]
    for _sid, _label, _icon, groups in MENU_SECTIONS:
        for key, label in iter_section_items(groups):
            if key == page_key:
                return label
    return page_key.replace("_", " ").title()


def section_for_page(page_key: str) -> str | None:
    for section_id, _label, _icon, groups in MENU_SECTIONS:
        if any(k == page_key for k, _ in iter_section_items(groups)):
            return section_id
    return None


def normalize_page_key(page_key: str | None) -> str:
    if not page_key:
        return MENU_DASHBOARD[0]
    mapped = LEGACY_PAGE_MAP.get(page_key, page_key)
    if mapped in all_page_keys():
        return mapped
    return MENU_DASHBOARD[0]


_ACCOUNTS_MANAGER_PAGES = pages_in_sections("dashboard", "accounts", "petty_cash", "purchase", "reports") | {
    "master_vendor",
    "master_client",
    "proj_create",
    "proj_site_budget",
    "rpt_cost_analysis",
    "acc_outstanding",
    "purch_invoice",
    "purch_vendor_payment",
}

_ACCOUNTS_EXECUTIVE_PAGES = pages_in_sections("dashboard", "petty_cash", "purchase") | {
    "acc_receipt",
    "acc_payment",
    "purch_invoice",
    "petty_expense",
    "petty_verification",
    "proj_create",
    "master_vendor",
}

_HR_PAYROLL_PAGES = pages_in_sections("dashboard", "hr", "reports") | {
    "master_employee",
    "master_labour",
    "master_branch",
    "master_department",
    "appr_leave",
}

_STORE_KEEPER_PAGES = pages_in_sections("dashboard", "store", "purchase", "reports") | {
    "proj_create",
    "master_material",
    "master_equipment",
}

_PROJECT_MANAGER_PAGES = (
    pages_in_sections("dashboard", "projects", "purchase", "store", "approvals", "reports", "documents")
    | {
        "master_client",
        "master_contractor_sub",
        "proj_wo_sub",
        "petty_expense",
        "petty_request",
        "hr_labour_attendance",
        "appr_leave",
    }
)

_SITE_ENGINEER_PAGES = pages_in_sections("dashboard", "projects", "store", "petty_cash") | {
    "proj_create",
    "proj_wo_sub",
    "proj_wo_internal",
    "purch_requisition",
    "purch_order",
    "hr_labour_attendance",
}

ROLE_PAGE_ACCESS: dict[str, set[str]] = {
    "Admin": all_page_keys(),
    "HR & Payroll": set(_HR_PAYROLL_PAGES),
    "HR": set(_HR_PAYROLL_PAGES),
    "MD": all_page_keys(),
    "Super Admin": all_page_keys(),
    "Accountant": set(_ACCOUNTS_MANAGER_PAGES) | CORRESPONDENCE_PAGES,
    "Accounts Manager": set(_ACCOUNTS_MANAGER_PAGES) | CORRESPONDENCE_PAGES,
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
