"""MAXEK ERP — Final UI/UX shell configuration (Construction ERP standard)."""

from __future__ import annotations

APP_VERSION_LABEL = "MAXEK ERP v1.0"

GLOBAL_SEARCH_CATEGORIES = [
    {"key": "project", "label": "Project", "icon": "fa-diagram-project"},
    {"key": "boq", "label": "BOQ", "icon": "fa-table-list"},
    {"key": "dpr", "label": "DPR", "icon": "fa-clipboard-list"},
    {"key": "material", "label": "Material", "icon": "fa-boxes-stacked"},
    {"key": "employee", "label": "Employee", "icon": "fa-user"},
    {"key": "vendor", "label": "Vendor", "icon": "fa-truck-field"},
    {"key": "vehicle", "label": "Vehicle", "icon": "fa-truck"},
    {"key": "purchase_order", "label": "Purchase Order", "icon": "fa-file-invoice"},
    {"key": "invoice", "label": "Invoice", "icon": "fa-file-invoice-dollar"},
    {"key": "bill", "label": "Bill", "icon": "fa-file-invoice-dollar"},
    {"key": "work_order", "label": "Work Order", "icon": "fa-helmet-safety"},
]

HELP_CENTER_ITEMS = [
    {"label": "User Manual", "icon": "fa-book", "endpoint": "help_desk", "query": {}},
    {"label": "Video Tutorials", "icon": "fa-circle-play", "endpoint": "help_desk", "query": {"tab": "videos"}},
    {"label": "Contact Support", "icon": "fa-headset", "endpoint": "help_contact", "query": {}},
    {
        "label": "WhatsApp Support",
        "icon": "fa-brands fa-whatsapp",
        "href": "https://wa.me/919876543210",
        "external": True,
    },
    {"label": "Remote Support", "icon": "fa-desktop", "endpoint": "help_contact", "query": {"mode": "remote"}},
]

# Main Command Centre (/dashboard) — department head tiles only (3×3 grid + KPIs).
# No global top module toolbar or left command rail on /dashboard; users pick a
# department card to open /dept/<slug>, which shows that dept's tools in a single
# left sidebar (compact office-style tickets). Back link returns to /dashboard.
MAIN_DASHBOARD_DEPARTMENT_SLUGS: list[tuple[str, str]] = [
    ("projects", "Project"),
    ("hr-payroll", "HR and Payroll"),
    ("accounts", "Accounts"),
    ("qc", "QA/QC"),
    ("store", "Store"),
    ("subcontract", "Subcontractor"),
    ("planning-wbs", "Planning and Costing"),
    ("vehicle", "Vehicle"),
    ("plant-operations", "Plant"),
    ("asphalt-plant", "Asphalt Plant"),
    ("concrete-plant", "Concrete Plant"),
    ("precast-yard", "Precast Yard"),
    ("administration", "Office Administration"),
]

# Canonical department workspace sidebar menus (/dept/<slug>).
# These are the ONLY tools shown on department portals — never merged with NAV_GROUPS.
DEPARTMENT_PORTAL_MENUS: dict[str, list[dict]] = {
    "consultancy": [
        {"endpoint": "clients", "label": "Client & Enquiry Register", "icon": "fa-address-book", "active_endpoints": ["clients"]},
        {"endpoint": "projects", "label": "Project Assignment Master", "icon": "fa-folder-tree", "anchor": "project-list", "active_endpoints": ["projects"]},
        {"endpoint": "projects", "label": "Tender Review", "icon": "fa-file-signature", "anchor": "project-list", "active_endpoints": ["projects"]},
        {"endpoint": "project_documents", "label": "Drawing & Document Register", "icon": "fa-compass-drafting", "active_endpoints": ["project_documents", "project_document_download"]},
        {"endpoint": "boq_management", "label": "Quantity Take-Off / BOQ", "icon": "fa-table-list", "active_endpoints": ["boq_management", "boq_multiple_entry", "boq_print"]},
        {"endpoint": "cost_planning", "label": "Rate Analysis & Estimate", "icon": "fa-calculator", "active_endpoints": ["cost_planning", "cost_planning_reports"]},
        {"endpoint": "wbs_redirect", "label": "Planning & Cash Flow", "icon": "fa-timeline", "active_endpoints": ["wbs_redirect"]},
        {"endpoint": "client_billing_register", "label": "Consultancy Billing", "icon": "fa-file-invoice-dollar", "active_endpoints": ["client_billing_register", "client_billing_form", "client_billing_reports"]},
        {"endpoint": "reports", "label": "Corporate MIS Reports", "icon": "fa-chart-pie", "active_endpoints": ["reports", "download_report"]},
    ],
    "projects": [
        {"endpoint": "projects", "label": "Project Master", "icon": "fa-folder-tree", "active_endpoints": ["projects"]},
        {"endpoint": "boq_management", "label": "BOQ Management", "icon": "fa-table-list", "active_endpoints": ["boq_management", "boq_multiple_entry", "boq_print"]},
        {"endpoint": "dpr_entry", "label": "DPR Entry", "icon": "fa-clipboard-list", "active_endpoints": ["dpr_entry", "dpr_entry_legacy"]},
        {"endpoint": "client_billing_register", "label": "Client Billing", "icon": "fa-file-invoice-dollar", "active_endpoints": ["client_billing_register", "client_billing_form", "client_billing_reports"]},
        {"endpoint": "wbs_redirect", "label": "WBS Planning", "icon": "fa-sitemap", "active_endpoints": ["wbs_redirect"]},
        {"endpoint": "cost_planning", "label": "Costing", "icon": "fa-indian-rupee-sign", "active_endpoints": ["cost_planning", "project_expenses"]},
        {"endpoint": "reports", "label": "Project Reports", "icon": "fa-chart-pie", "active_endpoints": ["reports", "download_report"]},
    ],
    "accounts": [
        {"endpoint": "petty_cash", "label": "Petty Cash", "icon": "fa-wallet", "active_endpoints": ["petty_cash"]},
        {"endpoint": "accounts_expenses", "label": "Expenses", "icon": "fa-receipt", "active_endpoints": ["accounts_expenses", "head_office_expenses"]},
        {"endpoint": "accounts_receipts", "label": "Receipts", "icon": "fa-hand-holding-dollar", "active_endpoints": ["accounts_receipts"]},
        {"endpoint": "accounts_gst_register", "label": "GST", "icon": "fa-percent", "active_endpoints": ["accounts_gst_register", "account_gst"]},
        {"endpoint": "account_tds", "label": "TDS", "icon": "fa-file-contract", "active_endpoints": ["account_tds", "accounts_tds_register"]},
        {"endpoint": "accounts_expenses", "label": "Vendor Bills", "icon": "fa-file-invoice", "active_endpoints": ["accounts_expenses"]},
        {"endpoint": "accounts_bank_book_v2", "label": "Bank Book", "icon": "fa-building-columns", "active_endpoints": ["accounts_bank_book_v2", "bank_book"]},
        {"endpoint": "accounts_cash_book_v2", "label": "Cash Book", "icon": "fa-book", "active_endpoints": ["accounts_cash_book_v2", "cash_book"]},
        {"endpoint": "accounts_reports", "label": "Reports", "icon": "fa-chart-line", "active_endpoints": ["accounts_reports"]},
    ],
    "store": [
        {"endpoint": "material_request", "label": "Material Request", "icon": "fa-clipboard-list", "active_endpoints": ["material_request"]},
        {"endpoint": "store_receipt", "label": "Store Receipt", "icon": "fa-arrow-right-to-bracket", "active_endpoints": ["store_receipt"]},
        {"endpoint": "store_issue", "label": "Store Issue", "icon": "fa-arrow-right-from-bracket", "active_endpoints": ["store_issue"]},
        {"endpoint": "purchase_request", "label": "Purchase Request", "icon": "fa-file-circle-plus", "active_endpoints": ["purchase_request"]},
        {"endpoint": "inventory", "label": "Stock Register", "icon": "fa-boxes-stacked", "active_endpoints": ["inventory"]},
        {"endpoint": "inventory", "label": "Inventory Reports", "icon": "fa-chart-column", "active_endpoints": ["inventory"]},
    ],
    "hr-payroll": [
        {"endpoint": "staff", "label": "Employee Master", "icon": "fa-user-tie", "active_endpoints": ["staff", "employee_profile"]},
        {"endpoint": "attendance", "label": "Attendance", "icon": "fa-calendar-check", "active_endpoints": ["attendance"]},
        {"endpoint": "timesheet", "label": "Timesheet", "icon": "fa-clock", "active_endpoints": ["timesheet", "employee_timesheets"]},
        {"endpoint": "payroll", "label": "Payroll", "icon": "fa-money-check-dollar", "active_endpoints": ["payroll", "payroll_payments"]},
        {"endpoint": "salary", "label": "Salary Payment", "icon": "fa-wallet", "active_endpoints": ["salary"]},
        {"endpoint": "leave_request", "label": "Leave Management", "icon": "fa-plane-departure", "active_endpoints": ["leave_request"]},
        {"endpoint": "accounts_pf_register", "label": "PF / ESI", "icon": "fa-building", "active_endpoints": ["accounts_pf_register", "accounts_esi_register"]},
        {"endpoint": "reports", "label": "Reports", "icon": "fa-file-excel", "active_endpoints": ["reports", "download_report"]},
    ],
    "vehicle": [
        {"endpoint": "fleet_vehicles", "label": "Vehicle Master", "icon": "fa-car", "active_endpoints": ["fleet_vehicles", "fleet_vehicle_print"]},
        {"endpoint": "fleet_vehicle_documents", "label": "Vehicle Documents", "icon": "fa-id-card", "active_endpoints": ["fleet_vehicle_documents", "fleet_document_download"]},
        {"endpoint": "fleet_running_log", "label": "Running Log", "icon": "fa-road", "active_endpoints": ["fleet_running_log"]},
        {"endpoint": "fleet_diesel_purchase", "label": "Diesel Purchase", "icon": "fa-gas-pump", "active_endpoints": ["fleet_diesel_purchase"]},
        {"endpoint": "fleet_diesel_stock", "label": "Diesel Stock", "icon": "fa-oil-can", "active_endpoints": ["fleet_diesel_stock"]},
        {"endpoint": "fleet_diesel_issue", "label": "Diesel Issue", "icon": "fa-arrow-right-from-bracket", "active_endpoints": ["fleet_diesel_issue"]},
    ],
    "mechanical": [
        {"endpoint": "plant_plants", "label": "Plant Master", "icon": "fa-industry", "active_endpoints": ["plant_plants"]},
        {"endpoint": "plant_maintenance", "label": "Maintenance", "icon": "fa-screwdriver-wrench", "active_endpoints": ["plant_maintenance"]},
        {"endpoint": "fleet_diesel_stock", "label": "Fuel & Diesel", "icon": "fa-gas-pump", "active_endpoints": ["fleet_diesel_stock"]},
        {"endpoint": "plant_maintenance", "label": "Breakdown Log", "icon": "fa-triangle-exclamation", "active_endpoints": ["plant_maintenance"]},
        {"endpoint": "plant_dashboard", "label": "Equipment Dashboard", "icon": "fa-gauge-high", "active_endpoints": ["plant_dashboard"]},
        {"endpoint": "reports", "label": "Reports", "icon": "fa-chart-line", "active_endpoints": ["reports", "download_report"]},
    ],
    "plant-operations": [
        {"endpoint": "plant_dashboard", "label": "Plant Dashboard", "icon": "fa-gauge-high", "active_endpoints": ["plant_dashboard"]},
        {"endpoint": "plant_plants", "label": "Plant Master", "icon": "fa-industry", "active_endpoints": ["plant_plants"]},
        {"endpoint": "plant_360", "label": "Plant 360° View", "icon": "fa-circle-nodes", "active_endpoints": ["plant_360"]},
        {"endpoint": "plant_crusher_production", "label": "Crusher Production", "icon": "fa-hammer", "active_endpoints": ["plant_crusher_production"]},
        {"endpoint": "plant_wetmix_production", "label": "Wet Mix Production", "icon": "fa-layer-group", "active_endpoints": ["plant_wetmix_production"]},
        {"endpoint": "plant_qc", "label": "Plant QC", "icon": "fa-vial", "active_endpoints": ["plant_qc"]},
        {"endpoint": "plant_costing", "label": "Production Costing", "icon": "fa-indian-rupee-sign", "active_endpoints": ["plant_costing"]},
        {"endpoint": "plant_maintenance", "label": "Maintenance", "icon": "fa-screwdriver-wrench", "active_endpoints": ["plant_maintenance"]},
    ],
    "asphalt-plant": [
        {"endpoint": "plant_asphalt_production", "label": "Asphalt Production", "icon": "fa-flask", "active_endpoints": ["plant_asphalt_production"]},
        {"endpoint": "plant_asphalt_dispatch", "label": "Asphalt Dispatch", "icon": "fa-truck-ramp-box", "active_endpoints": ["plant_asphalt_dispatch", "plant_asphalt_dispatch_print"]},
        {"endpoint": "plant_qc", "label": "Asphalt QC", "icon": "fa-vial", "active_endpoints": ["plant_qc"]},
        {"endpoint": "plant_costing", "label": "Production Costing", "icon": "fa-indian-rupee-sign", "active_endpoints": ["plant_costing"]},
        {"endpoint": "plant_dashboard", "label": "All Plants", "icon": "fa-gauge-high", "active_endpoints": ["plant_dashboard"]},
    ],
    "concrete-plant": [
        {"endpoint": "plant_rmc_production", "label": "RMC Production", "icon": "fa-cubes", "active_endpoints": ["plant_rmc_production"]},
        {"endpoint": "plant_rmc_dispatch", "label": "RMC Dispatch", "icon": "fa-truck", "active_endpoints": ["plant_rmc_dispatch", "plant_rmc_dispatch_print"]},
        {"endpoint": "plant_qc", "label": "Concrete QC", "icon": "fa-vial", "active_endpoints": ["plant_qc"]},
        {"endpoint": "plant_costing", "label": "Production Costing", "icon": "fa-indian-rupee-sign", "active_endpoints": ["plant_costing"]},
        {"endpoint": "plant_dashboard", "label": "All Plants", "icon": "fa-gauge-high", "active_endpoints": ["plant_dashboard"]},
    ],
    "precast-yard": [
        {"endpoint": "precast_yard", "label": "Precast Dashboard", "icon": "fa-gauge-high", "active_endpoints": ["precast_yard"]},
        {"endpoint": "precast_yard_yards", "label": "Yard Master", "icon": "fa-warehouse", "active_endpoints": ["precast_yard_yards"]},
        {"endpoint": "plant_precast_production", "label": "Production", "icon": "fa-border-all", "active_endpoints": ["plant_precast_production"]},
        {"endpoint": "plant_precast_dispatch", "label": "Dispatch", "icon": "fa-dolly", "active_endpoints": ["plant_precast_dispatch"]},
        {"endpoint": "plant_qc", "label": "QC Records", "icon": "fa-vial", "active_endpoints": ["plant_qc"], "query": {"source": "Precast"}},
    ],
    "engineering": [
        {"endpoint": "boq_management", "label": "SmartQTO / BOQ", "icon": "fa-calculator", "active_endpoints": ["boq_management", "boq_multiple_entry", "boq_print"]},
        {"endpoint": "dpr_client_bill_pending", "label": "Measurement Book", "icon": "fa-book", "active_endpoints": ["dpr_client_bill_pending", "dpr_client_bill_print"]},
        {"endpoint": "cost_planning", "label": "Rate Analysis", "icon": "fa-chart-line", "active_endpoints": ["cost_planning", "cost_planning_reports"]},
        {"endpoint": "project_documents", "label": "Drawing Register", "icon": "fa-compass-drafting", "active_endpoints": ["project_documents", "project_document_download"]},
        {"endpoint": "reports", "label": "Engineering Reports", "icon": "fa-file-excel", "active_endpoints": ["reports", "download_report"]},
    ],
    "planning-wbs": [
        {"endpoint": "cost_planning", "label": "Cost Planning", "icon": "fa-calculator", "active_endpoints": ["cost_planning", "cost_planning_reports"]},
        {"endpoint": "wbs_redirect", "label": "WBS Planning", "icon": "fa-sitemap", "active_endpoints": ["wbs_redirect"]},
        {"endpoint": "boq_management", "label": "BOQ Management", "icon": "fa-table-list", "active_endpoints": ["boq_management", "boq_multiple_entry", "boq_print"]},
        {"endpoint": "project_expenses", "label": "Project Expenses", "icon": "fa-receipt", "active_endpoints": ["project_expenses"]},
        {"endpoint": "reports", "label": "Planning Reports", "icon": "fa-chart-pie", "active_endpoints": ["reports", "download_report"]},
    ],
    "subcontract": [
        {"endpoint": "subcontract_dashboard", "label": "Subcontract Dashboard", "icon": "fa-gauge-high", "active_endpoints": ["subcontract_dashboard"]},
        {"endpoint": "subcontractors", "label": "Subcontractors", "icon": "fa-user-plus", "active_endpoints": ["subcontractors"]},
        {"endpoint": "workers", "label": "Workers", "icon": "fa-hard-hat", "active_endpoints": ["workers"]},
        {"endpoint": "attendance", "label": "Worker Attendance", "icon": "fa-calendar-check", "query": {"nav": "subcontract"}, "active_endpoints": ["attendance"]},
        {"endpoint": "timesheet", "label": "Worker Timesheet", "icon": "fa-clock", "query": {"nav": "subcontract"}, "active_endpoints": ["timesheet", "employee_timesheets"]},
        {"endpoint": "sub_billing_register", "label": "Subcontract Bills", "icon": "fa-file-invoice", "active_endpoints": ["sub_billing_register", "sub_billing_form"]},
        {"endpoint": "subcontract_payments", "label": "Payments", "icon": "fa-money-bill-transfer", "active_endpoints": ["subcontract_payments"]},
    ],
    "procurement": [
        {"endpoint": "purchase_vendors", "label": "Vendor Master", "icon": "fa-truck-field", "active_endpoints": ["purchase_vendors", "masters_vendors"]},
        {"endpoint": "purchase_request", "label": "Purchase Request", "icon": "fa-file-circle-plus", "active_endpoints": ["purchase_request"]},
        {"endpoint": "purchase_orders", "label": "Purchase Orders", "icon": "fa-file-invoice", "active_endpoints": ["purchase_orders", "purchase"]},
        {"endpoint": "store_receipt", "label": "GRN / Receipt", "icon": "fa-dolly", "active_endpoints": ["store_receipt"]},
        {"endpoint": "purchase_orders", "label": "Vendor Bills", "icon": "fa-file-invoice-dollar", "active_endpoints": ["purchase_orders"]},
        {"endpoint": "inventory", "label": "Reports", "icon": "fa-chart-column", "active_endpoints": ["inventory"]},
    ],
    "qc": [
        {"endpoint": "qc_master", "label": "QC Test Master", "icon": "fa-vial", "active_endpoints": ["qc_master"]},
        {"endpoint": "plant_qc", "label": "Plant QC", "icon": "fa-flask", "active_endpoints": ["plant_qc"]},
        {"endpoint": "reports", "label": "QC Reports", "icon": "fa-file-excel", "active_endpoints": ["reports", "download_report"]},
    ],
    "tender": [
        {"endpoint": "projects", "label": "Tender Register", "icon": "fa-list", "anchor": "project-list", "active_endpoints": ["projects"]},
        {"endpoint": "projects", "label": "Bid Tracking", "icon": "fa-chart-line", "anchor": "project-list", "active_endpoints": ["projects"]},
        {"endpoint": "boq_management", "label": "BOQ / Estimation", "icon": "fa-calculator", "active_endpoints": ["boq_management"]},
        {"endpoint": "reports", "label": "Tender Reports", "icon": "fa-file-excel", "active_endpoints": ["reports", "download_report"]},
    ],
    "reports": [
        {"endpoint": "reports", "label": "Operational Reports", "icon": "fa-file-excel", "active_endpoints": ["reports", "download_report"]},
        {"endpoint": "accounts_reports", "label": "Financial Reports", "icon": "fa-chart-line", "active_endpoints": ["accounts_reports"]},
        {"endpoint": "cost_planning_reports", "label": "Project Reports", "icon": "fa-diagram-project", "active_endpoints": ["cost_planning_reports"]},
        {"endpoint": "inventory", "label": "Store Reports", "icon": "fa-warehouse", "active_endpoints": ["inventory"]},
        {"endpoint": "payroll", "label": "Payroll Reports", "icon": "fa-money-check-dollar", "active_endpoints": ["payroll"]},
    ],
    "administration": [
        {"endpoint": "office_admin", "label": "Office Dashboard", "icon": "fa-gauge-high", "active_endpoints": ["office_admin"]},
        {"endpoint": "office_inward", "label": "Letter In / Inward Register", "icon": "fa-inbox", "active_endpoints": ["office_inward"]},
        {"endpoint": "office_outward", "label": "Letter Out / Outward Register", "icon": "fa-paper-plane", "active_endpoints": ["office_outward"]},
        {"endpoint": "office_letters", "label": "Letter Preparation", "icon": "fa-envelope-open-text", "active_endpoints": ["office_letters", "office_letter_print"]},
        {"endpoint": "office_agreements", "label": "Agreements", "icon": "fa-handshake", "active_endpoints": ["office_agreements"]},
        {"endpoint": "office_legal", "label": "Legal Documents", "icon": "fa-scale-balanced", "active_endpoints": ["office_legal"]},
        {"endpoint": "corporate_dms", "label": "Corporate DMS", "icon": "fa-folder-tree", "active_endpoints": ["corporate_dms", "corporate_dms_file", "corporate_dms_download"]},
        {"endpoint": "fleet_dashboard", "label": "Fleet Dashboard", "icon": "fa-truck", "active_endpoints": ["fleet_dashboard"]},
    ],
}


def resolve_department_portal_slug(slug: str) -> str:
    """Map URL / legacy slugs to canonical department portal slug."""
    merged = {**MAIN_DASHBOARD_PORTAL_ALIASES, **DEPARTMENT_PORTAL_SLUG_ALIASES}
    return merged.get(slug, slug)


def get_department_portal_menu(slug: str) -> list[dict]:
    """Return a copy of the isolated department workspace menu for slug."""
    canonical = resolve_department_portal_slug(slug)
    return [dict(item) for item in DEPARTMENT_PORTAL_MENUS.get(canonical, [])]


_ENDPOINT_DEPARTMENT_SLUGS: dict[str, frozenset[str]] | None = None

_DEPT_PORTAL_SHELL_SKIP_ENDPOINTS = frozenset(
    {"dashboard", "dashboard_choice_b", "login", "logout", "index"}
)


def _endpoint_department_slug_index() -> dict[str, frozenset[str]]:
    """Map Flask endpoints to department portal slugs (from portal menus)."""
    global _ENDPOINT_DEPARTMENT_SLUGS
    if _ENDPOINT_DEPARTMENT_SLUGS is None:
        index: dict[str, set[str]] = {}
        for dept_slug, menu in DEPARTMENT_PORTAL_MENUS.items():
            canonical = resolve_department_portal_slug(dept_slug)
            for item in menu:
                endpoints = list(item.get("active_endpoints") or [])
                endpoint = item.get("endpoint")
                if endpoint and endpoint not in endpoints:
                    endpoints.append(endpoint)
                for ep in endpoints:
                    if ep:
                        index.setdefault(ep, set()).add(canonical)
        _ENDPOINT_DEPARTMENT_SLUGS = {key: frozenset(value) for key, value in index.items()}
    return _ENDPOINT_DEPARTMENT_SLUGS


def endpoint_belongs_to_department_portal(endpoint: str, dept_slug: str) -> bool:
    canonical = resolve_department_portal_slug(dept_slug)
    return canonical in _endpoint_department_slug_index().get(endpoint, frozenset())


def resolve_department_portal_for_request(
    endpoint: str,
    *,
    view_slug: str | None = None,
    dept_hint: str | None = None,
    session_slug: str | None = None,
    nav_toolbar_slug: str | None = None,
) -> str | None:
    """Resolve canonical department portal slug for the current request."""
    if endpoint in _DEPT_PORTAL_SHELL_SKIP_ENDPOINTS:
        return None
    if endpoint == "department_portal" and view_slug:
        return resolve_department_portal_slug(view_slug)
    if dept_hint:
        hinted = resolve_department_portal_slug(dept_hint)
        if endpoint == "department_portal" or endpoint_belongs_to_department_portal(
            endpoint, hinted
        ):
            return hinted
    if session_slug:
        session_canonical = resolve_department_portal_slug(session_slug)
        if endpoint == "department_portal" or endpoint_belongs_to_department_portal(
            endpoint, session_canonical
        ):
            return session_canonical
    candidates = set(_endpoint_department_slug_index().get(endpoint, frozenset()))
    if not candidates:
        return None
    if len(candidates) == 1:
        return next(iter(candidates))
    if nav_toolbar_slug:
        mapped = resolve_department_portal_slug(nav_toolbar_slug)
        if mapped in candidates:
            return mapped
    if session_slug:
        session_canonical = resolve_department_portal_slug(session_slug)
        if session_canonical in candidates:
            return session_canonical
    return sorted(candidates)[0]


def portal_menu_as_nav_group(portal: dict) -> dict:
    """Synthetic nav group containing only this department's portal menu."""
    return {
        "slug": portal.get("slug", ""),
        "label": portal.get("card_label") or portal.get("title") or "Department",
        "icon": portal.get("icon", "fa-folder"),
        "items": [dict(item) for item in portal.get("menu") or []],
    }


# Bottom-row widgets on the main dashboard (placeholders until feeds are wired).
MAIN_DASHBOARD_BOTTOM_WIDGETS: list[dict[str, str]] = [
    {
        "key": "project_progress",
        "title": "Project Progress",
        "subtitle": "Active sites vs plan",
        "icon": "fa-chart-area",
        "chart_type": "scatter",
    },
    {
        "key": "pending_approvals",
        "title": "Pending Approvals",
        "subtitle": "Workflow queue by module",
        "icon": "fa-clipboard-check",
        "chart_type": "bars",
    },
    {
        "key": "cash_vs_budget",
        "title": "Cash vs Budget",
        "subtitle": "Monthly variance trend",
        "icon": "fa-scale-balanced",
        "chart_type": "lines",
    },
    {
        "key": "expense_breakdown",
        "title": "Expense Breakdown",
        "subtitle": "OpEx by category",
        "icon": "fa-chart-pie",
        "chart_type": "hbar",
    },
]

# Sidebar favorites on the main dashboard shell (optional shortcuts above nav groups).
DASHBOARD_SHELL_FAVORITES: list[dict[str, str]] = []

# Settings link pinned to sidebar footer on the main dashboard shell.
DASHBOARD_SHELL_SETTINGS: dict[str, str] = {
    "endpoint": "settings",
    "label": "Settings",
    "icon": "fa-gear",
}

# Primary sidebar navigation groups for the main dashboard shell (mockup-aligned).
DASHBOARD_SHELL_NAV_GROUPS: list[dict] = [
    {
        "label": "Projects & Operations",
        "icon": "fa-diagram-project",
        "items": [
            {"endpoint": "projects", "label": "Projects", "icon": "fa-folder-tree"},
            {"endpoint": "boq_management", "label": "BOQ", "icon": "fa-table-list"},
            {"endpoint": "dpr_entry", "label": "DPR", "icon": "fa-clipboard-list"},
            {
                "endpoint": "department_portal",
                "label": "Planning & Costing",
                "icon": "fa-drafting-compass",
                "query": {"slug": "planning-wbs"},
            },
            {"endpoint": "wbs_redirect", "label": "WBS", "icon": "fa-sitemap"},
            {
                "endpoint": "department_portal",
                "label": "Subcontract",
                "icon": "fa-people-group",
                "query": {"slug": "subcontract"},
            },
        ],
    },
    {
        "label": "Procurement & Store",
        "icon": "fa-cart-shopping",
        "items": [
            {"endpoint": "purchase_orders", "label": "Purchase", "icon": "fa-file-invoice"},
            {
                "endpoint": "department_portal",
                "label": "Store & Inventory",
                "icon": "fa-warehouse",
                "query": {"slug": "store"},
            },
        ],
    },
    {
        "label": "Workforce",
        "icon": "fa-users",
        "items": [
            {"endpoint": "attendance", "label": "Attendance", "icon": "fa-calendar-check"},
            {"endpoint": "payroll", "label": "Payroll", "icon": "fa-money-check-dollar"},
        ],
    },
    {
        "label": "Fleet & Assets",
        "icon": "fa-truck",
        "items": [
            {"endpoint": "fleet_dashboard", "label": "Fleet", "icon": "fa-truck-fast"},
            {
                "endpoint": "department_portal",
                "label": "Plant & Machinery",
                "icon": "fa-industry",
                "query": {"slug": "plant-operations"},
            },
        ],
    },
    {
        "label": "Finance & Accounts",
        "icon": "fa-indian-rupee-sign",
        "items": [
            {"endpoint": "accounts_hub", "label": "Accounts", "icon": "fa-landmark"},
            {"endpoint": "accounts_expenses", "label": "Expenses", "icon": "fa-receipt"},
        ],
    },
]

# Overview tab quick links (mockup bottom-right panel).
DASHBOARD_OVERVIEW_QUICK_LINKS: list[dict[str, str]] = [
    {"endpoint": "dpr_entry", "label": "Create DPR", "icon": "fa-clipboard-list", "accent": "#22c55e"},
    {"endpoint": "material_request", "label": "Material Request", "icon": "fa-boxes-stacked", "accent": "#a855f7"},
    {"endpoint": "purchase_orders", "label": "New PO", "icon": "fa-file-invoice", "accent": "#f59e0b"},
    {"endpoint": "attendance", "label": "Attendance", "icon": "fa-calendar-check", "accent": "#3b82f6"},
]

# Resolve /dept/<slug> and legacy URLs to canonical department portal slugs.
DEPARTMENT_PORTAL_SLUG_ALIASES: dict[str, str] = {
    "project-management": "projects",
    "projects": "projects",
    "accounts-finance": "accounts",
    "accounts": "accounts",
    "store-procurement": "store",
    "store": "store",
    "hr-payroll": "hr-payroll",
    "workforce": "hr-payroll",
    "hr": "hr-payroll",
    "plant-machinery": "plant-operations",
    "plant-operations": "plant-operations",
    "plant": "plant-operations",
    "asphalt-plant": "asphalt-plant",
    "asphalt": "asphalt-plant",
    "concrete-plant": "concrete-plant",
    "rmc-plant": "concrete-plant",
    "concrete": "concrete-plant",
    "precast-yard": "precast-yard",
    "precast": "precast-yard",
    "mechanical": "mechanical",
    "procurement": "procurement",
    "quality-control": "qc",
    "qc": "qc",
    "tender": "tender",
    "reports": "reports",
    "engineering-smartqto": "engineering",
    "engineering": "engineering",
    "planning": "engineering",
    "planning-wbs": "planning-wbs",
    "cost-planning": "engineering",
    "subcontract-management": "subcontract",
    "subcontract": "subcontract",
    "fleet-mechanical": "vehicle",
    "equipment-fleet": "vehicle",
    "fleet": "vehicle",
    "vehicle": "vehicle",
    "admin-compliance": "administration",
    "administration": "administration",
    "office": "administration",
    "consultancy": "consultancy",
}

# Department portal accent colors — blue/slate family harmonized with Midnight Blue Executive
DEPARTMENT_PORTAL_ACCENTS: dict[str, str] = {
    "accounts": "#3b82f6",
    "projects": "#6366f1",
    "store": "#0ea5e9",
    "hr-payroll": "#818cf8",
    "vehicle": "#38bdf8",
    "planning-wbs": "#06b6d4",
    "plant-machinery": "#10b981",
    "plant-operations": "#10b981",
    "asphalt-plant": "#f59e0b",
    "concrete-plant": "#3b82f6",
    "precast-yard": "#8b5cf6",
    "planning-wbs": "#14b8a6",
    "administration": "#64748b",
    "qc": "#22d3ee",
    "subcontract": "#4f46e5",
    "consultancy": "#0284c7",
    "procurement": "#2563eb",
    "tender": "#7c3aed",
    "reports": "#6366f1",
    "mechanical": "#059669",
}


def get_department_portal_accent(slug: str) -> str | None:
    """Return accent hex for a department portal (icon/border only)."""
    canonical = resolve_department_portal_slug(slug)
    return DEPARTMENT_PORTAL_ACCENTS.get(canonical)

# Aliases resolving toolbar / legacy slugs to main dashboard department portals.
MAIN_DASHBOARD_PORTAL_ALIASES: dict[str, str] = {
    "accounts-finance": "accounts",
    "project-management": "projects",
    "store-procurement": "store",
    "hr": "hr-payroll",
    "workforce": "hr-payroll",
    "fleet-mechanical": "vehicle",
    "equipment-fleet": "vehicle",
    "fleet": "vehicle",
    "quality-control": "qc",
    "subcontract-management": "subcontract",
    "cost-planning": "planning-wbs",
    "planning": "planning-wbs",
    "plant-machinery": "plant-operations",
    "plant-operations": "plant-operations",
    "asphalt-plant": "asphalt-plant",
    "concrete-plant": "concrete-plant",
    "precast-yard": "precast-yard",
    "admin-compliance": "administration",
    "administration": "administration",
}

# Main toolbar: ordered slugs with display labels per UI/UX standard.
MAIN_TOOLBAR_SLUGS = [
    ("dashboard", "Dashboard"),
    ("project-management", "Projects"),
    ("engineering-smartqto", "Planning"),
    ("store-procurement", "Procurement"),
    ("store-section", "Store"),
    ("accounts-finance", "Accounts"),
    ("hr-payroll", "HR & Payroll"),
    ("fleet-mechanical", "Fleet & Mechanical"),
    ("plant-operations", "Plant Operations"),
    ("qc", "Quality Control"),
    ("admin-compliance", "Administration"),
    ("reports-analytics", "Reports"),
    ("settings", "Settings"),
]

# Virtual toolbar entries (not in NAV_GROUPS) — split plant/fleet and store.
VIRTUAL_TOOLBAR_ENTRIES: dict[str, dict] = {
    "store-section": {
        "label": "Store",
        "icon": "fa-warehouse",
        "endpoint": "store",
        "active_endpoints": ["store", "store_receipt", "store_issue", "material_transfer"],
        "items": [
            {"endpoint": "store_receipt", "label": "Material Receipt", "active_endpoints": ["store_receipt"]},
            {"endpoint": "store_issue", "label": "Material Issue", "active_endpoints": ["store_issue"]},
            {"endpoint": "material_transfer", "label": "Transfer", "active_endpoints": ["material_transfer"]},
            {"endpoint": "store", "label": "Stock Verification", "active_endpoints": ["store"]},
        ],
    },
    "fleet-mechanical": {
        "label": "Fleet & Mechanical",
        "icon": "fa-truck",
        "endpoint": "fleet_dashboard",
        "active_endpoints": [
            "fleet_dashboard",
            "fleet_vehicles",
            "fleet_running_log",
            "fleet_diesel_issue",
            "fleet_diesel_purchase",
            "fleet_diesel_stock",
            "fleet_vehicle_documents",
        ],
        "items": [
            {"endpoint": "fleet_vehicles", "label": "Vehicle Master", "active_endpoints": ["fleet_vehicles"]},
            {"endpoint": "fleet_diesel_issue", "label": "Fuel Entry", "active_endpoints": ["fleet_diesel_issue"]},
            {"endpoint": "plant_maintenance", "label": "Job Card", "active_endpoints": ["plant_maintenance"]},
            {"endpoint": "fleet_vehicle_documents", "label": "Tyre Register", "active_endpoints": ["fleet_vehicle_documents"]},
            {"endpoint": "fleet_running_log", "label": "Breakdown Register", "active_endpoints": ["fleet_running_log"]},
        ],
    },
    "plant-operations": {
        "label": "Plant Operations",
        "icon": "fa-industry",
        "endpoint": "plant_dashboard",
        "active_endpoints": [
            "plant_dashboard",
            "plant_asphalt_production",
            "plant_rmc_production",
            "plant_crusher_production",
            "plant_wetmix_production",
        ],
        "items": [
            {"endpoint": "plant_asphalt_production", "label": "Asphalt Plant", "active_endpoints": ["plant_asphalt_production"]},
            {"endpoint": "plant_rmc_production", "label": "RMC Plant", "active_endpoints": ["plant_rmc_production"]},
            {"endpoint": "plant_crusher_production", "label": "Crusher Plant", "active_endpoints": ["plant_crusher_production"]},
            {"endpoint": "plant_asphalt_production", "label": "Production", "active_endpoints": ["plant_asphalt_production", "plant_rmc_production"]},
            {"endpoint": "plant_asphalt_dispatch", "label": "Dispatch", "active_endpoints": ["plant_asphalt_dispatch", "plant_rmc_dispatch"]},
        ],
    },
}

# Standard sub-toolbar labels per department (slug → ordered label filters).
STANDARD_SUB_LABELS: dict[str, list[str]] = {
    "project-management": [
        "Project Master",
        "BOQ",
        "DPR",
        "Client Billing",
        "Photos",
        "Documents",
    ],
    "engineering-smartqto": [
        "Costing",
        "WBS",
        "Resource Planning",
        "Micro Planning",
        "Progress Tracking",
    ],
    "store-procurement": [
        "Material Request",
        "Purchase Request",
        "RFQ",
        "Quotation Comparison",
        "Purchase Order",
        "GRN",
    ],
    "store-section": [
        "Material Receipt",
        "Material Issue",
        "Transfer",
        "Stock Verification",
    ],
    "accounts-finance": [
        "Payment Voucher",
        "Receipt Voucher",
        "Journal Voucher",
        "GST",
        "TDS",
        "Reports",
    ],
    "hr-payroll": [
        "Employee Master",
        "Attendance",
        "Timesheet",
        "Payroll",
        "Leave",
    ],
    "fleet-mechanical": [
        "Vehicle Master",
        "Fuel Entry",
        "Job Card",
        "Tyre Register",
        "Breakdown Register",
    ],
    "plant-operations": [
        "Asphalt Plant",
        "RMC Plant",
        "Crusher Plant",
        "Production",
        "Dispatch",
    ],
    "qc": [
        "Material Testing",
        "Cube Register",
        "Asphalt Testing",
        "NCR Register",
    ],
}

# Label aliases: map existing nav item labels to standard sub-toolbar names.
SUB_LABEL_ALIASES: dict[str, str] = {
    "Project List": "Project Master",
    "Create Project": "Project Master",
    "BOQ Master": "BOQ",
    "Client Billing": "Client Billing",
    "Project Photos": "Photos",
    "Project Documents": "Documents",
    "Cost Planning": "Costing",
    "Planning": "Costing",
    "WBS": "WBS",
    "Material Request": "Material Request",
    "Purchase Request": "Purchase Request",
    "Purchase Order": "Purchase Order",
    "GRN": "GRN",
    "Staff Master": "Employee Master",
    "Attendance": "Attendance",
    "Payroll": "Payroll",
    "Leave Management": "Leave",
    "Vehicle Master": "Vehicle Master",
    "Diesel Issue": "Fuel Entry",
    "Running Log": "Breakdown Register",
    "QC Master": "Material Testing",
    "NCR": "NCR Register",
}

# Accounts department sub-toolbar — grouped sections (Masters | Transactions | Books).
ACCOUNTS_SUBTOOLBAR_SECTIONS: list[dict] = [
    {
        "label": "Masters",
        "items": [
            {"endpoint": "accounts_hub", "label": "Accounts Hub", "active_endpoints": ["accounts_hub"]},
            {"endpoint": "accounts_chart_of_accounts", "label": "Chart of Accounts", "active_endpoints": ["accounts_chart_of_accounts"]},
            {"endpoint": "treasury_bank_accounts", "label": "Bank Master", "active_endpoints": ["treasury_bank_accounts"]},
            {"endpoint": "petty_cash", "label": "Petty Cash", "active_endpoints": ["petty_cash"]},
        ],
    },
    {
        "label": "Transactions",
        "items": [
            {"endpoint": "head_office_expenses", "label": "Daily Expenses", "active_endpoints": ["head_office_expenses", "accounts_expenses"]},
            {"endpoint": "accounts_expenses", "label": "Expense / Purchase", "active_endpoints": ["accounts_expenses"]},
            {"endpoint": "accounts_receipts", "label": "Receipts", "active_endpoints": ["accounts_receipts"]},
            {"endpoint": "accounts_payments", "label": "Payments", "active_endpoints": ["accounts_payments"]},
        ],
    },
    {
        "label": "Books",
        "items": [
            {"endpoint": "accounts_cash_book_v2", "label": "Cash Book", "active_endpoints": ["accounts_cash_book_v2", "cash_book"]},
            {"endpoint": "accounts_bank_book_v2", "label": "Bank Book", "active_endpoints": ["accounts_bank_book_v2", "bank_book"]},
            {"endpoint": "accounts_day_book", "label": "Day Book", "active_endpoints": ["accounts_day_book"]},
            {"endpoint": "accounts_general_ledger", "label": "General Ledger", "active_endpoints": ["accounts_general_ledger", "ledger"]},
            {"endpoint": "accounts_gst_register", "label": "GST", "active_endpoints": ["accounts_gst_register", "account_gst"]},
            {"endpoint": "account_tds", "label": "TDS", "active_endpoints": ["account_tds", "accounts_tds_register"]},
            {"endpoint": "accounts_reports", "label": "Reports", "active_endpoints": ["accounts_reports"]},
        ],
    },
]


def accounts_sub_toolbar_sections() -> list[dict]:
    """Return grouped accounts sub-toolbar (no horizontal scroll grouping)."""
    return ACCOUNTS_SUBTOOLBAR_SECTIONS


# Context quick-panel links per active nav slug.
QUICK_PANEL_LINKS: dict[str, list[dict]] = {
    "project-management": [
        {"label": "New BOQ", "endpoint": "boq_management", "icon": "fa-table-list"},
        {"label": "New DPR", "endpoint": "dpr_entry", "icon": "fa-clipboard-list"},
        {"label": "New Bill", "endpoint": "client_billing_register", "icon": "fa-file-invoice-dollar"},
        {"label": "Project Dashboard", "endpoint": "projects_dashboard", "icon": "fa-gauge-high"},
    ],
    "store-procurement": [
        {"label": "New Material Request", "endpoint": "material_request", "icon": "fa-box"},
        {"label": "New Purchase Order", "endpoint": "purchase_orders", "icon": "fa-file-invoice"},
        {"label": "Store Dashboard", "endpoint": "store", "icon": "fa-warehouse"},
    ],
    "accounts-finance": [
        {"label": "Payment Voucher", "endpoint": "accounts_payments", "icon": "fa-money-bill-transfer"},
        {"label": "Receipt Voucher", "endpoint": "accounts_receipts", "icon": "fa-receipt"},
        {"label": "Accounts Hub", "endpoint": "accounts_hub", "icon": "fa-landmark"},
    ],
    "hr-payroll": [
        {"label": "New Employee", "endpoint": "staff", "icon": "fa-user-plus"},
        {"label": "Mark Attendance", "endpoint": "attendance", "icon": "fa-calendar-check"},
        {"label": "Run Payroll", "endpoint": "payroll", "icon": "fa-money-check-dollar"},
    ],
    "dashboard": [
        {"label": "Active Projects", "endpoint": "projects_dashboard", "icon": "fa-diagram-project"},
        {"label": "Pending Approvals", "endpoint": "approvals", "icon": "fa-clipboard-check"},
        {"label": "Notifications", "endpoint": "notifications", "icon": "fa-bell"},
    ],
}

# Badge keys for sub-toolbar items (endpoint → context key).
SUB_TOOLBAR_BADGE_KEYS: dict[str, str] = {
    "material_request": "material_request_count",
    "purchase_request": "purchase_request_count",
    "approvals": "approval_total",
}


def build_main_toolbar(nav_groups: list[dict]) -> list[dict]:
    """Build ordered main toolbar from NAV_GROUPS + virtual entries."""
    by_slug = {g["slug"]: dict(g) for g in nav_groups if g.get("slug")}
    by_slug.pop("plant-machinery", None)
    by_slug.pop("subcontract-management", None)
    by_slug.pop("approvals", None)
    by_slug.pop("erp-administration", None)

    toolbar: list[dict] = []
    for slug, label in MAIN_TOOLBAR_SLUGS:
        if slug in VIRTUAL_TOOLBAR_ENTRIES:
            entry = dict(VIRTUAL_TOOLBAR_ENTRIES[slug])
            entry["slug"] = slug
            entry["label"] = label
            toolbar.append(entry)
            continue
        group = by_slug.get(slug)
        if not group:
            continue
        group = dict(group)
        group["label"] = label
        toolbar.append(group)
    return toolbar


def filter_sub_toolbar_items(nav_group: dict | None) -> list[dict]:
    """Return sub-toolbar items aligned to UI standard where possible."""
    if not nav_group:
        return []
    slug = nav_group.get("slug", "")
    if slug in VIRTUAL_TOOLBAR_ENTRIES:
        return list(VIRTUAL_TOOLBAR_ENTRIES[slug].get("items", []))

    items = list(nav_group.get("items") or [])
    standard_labels = STANDARD_SUB_LABELS.get(slug)
    if not standard_labels:
        return items

    label_to_item: dict[str, dict] = {}
    for item in items:
        raw = item.get("label", "")
        canonical = SUB_LABEL_ALIASES.get(raw, raw)
        if canonical not in label_to_item:
            label_to_item[canonical] = dict(item)
            label_to_item[canonical]["label"] = canonical

    filtered: list[dict] = []
    for std_label in standard_labels:
        if std_label in label_to_item:
            filtered.append(label_to_item[std_label])
        else:
            for item in items:
                if item.get("label") == std_label:
                    filtered.append(item)
                    break
    return filtered if filtered else items


def quick_panel_for_slug(slug: str | None) -> list[dict]:
    if not slug:
        return QUICK_PANEL_LINKS.get("dashboard", [])
    return QUICK_PANEL_LINKS.get(slug, QUICK_PANEL_LINKS.get("dashboard", []))


def resolve_active_toolbar_slug(endpoint: str, nav_slug: str | None, nav_groups: list[dict]) -> str | None:
    """Map current route to main toolbar slug (including virtual entries)."""
    for vslug, ventry in VIRTUAL_TOOLBAR_ENTRIES.items():
        if endpoint in ventry.get("active_endpoints", []):
            return vslug
    for group in nav_groups:
        for item in group.get("items") or []:
            if endpoint in item.get("active_endpoints", []):
                return group.get("slug")
        if endpoint in group.get("active_endpoints", []):
            return group.get("slug")
    if nav_slug:
        return nav_slug
    return "dashboard"
