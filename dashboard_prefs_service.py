"""Per-user dashboard customization."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from user_context_service import ensure_user_context_schema

VALID_UI_THEMES = frozenset({"command-dark", "pro-light", "ultra-color"})
DEFAULT_UI_THEME = "command-dark"


def normalize_ui_theme(theme: str | None) -> str:
    if theme and theme in VALID_UI_THEMES:
        return theme
    return DEFAULT_UI_THEME

DEFAULT_ROLE_PROFILES: dict[str, dict[str, Any]] = {
    "accounts": {
        "favorite_modules": ["accounts_payments", "accounts_receipts", "accounts_gst", "accounts_reports"],
        "dashboard_cards": ["payments", "receipts", "gst", "pending_bills"],
        "quick_actions": ["payment_voucher", "receipt_voucher", "journal"],
        "reports": ["accounts_reports", "gst_summary"],
    },
    "project_engineer": {
        "favorite_modules": ["boq_management", "dpr_entry", "client_billing_register", "projects"],
        "dashboard_cards": ["active_projects", "boq", "dpr", "billing"],
        "quick_actions": ["new_boq", "new_dpr", "new_bill"],
        "reports": ["project_reports"],
    },
    "store": {
        "favorite_modules": ["store_receipt", "material_request", "store", "purchase_orders"],
        "dashboard_cards": ["grn", "material_request", "stock_status", "low_stock"],
        "quick_actions": ["material_request", "grn", "material_issue"],
        "reports": ["store_reports"],
    },
    "default": {
        "favorite_modules": ["dashboard", "approvals", "notifications"],
        "dashboard_cards": ["active_projects", "pending_approvals", "notifications"],
        "quick_actions": ["new_dpr", "material_request"],
        "reports": ["reports"],
    },
}


def _merge_defaults(prefs: dict[str, Any] | None, role_profile: str) -> dict[str, Any]:
    base = dict(DEFAULT_ROLE_PROFILES.get(role_profile, DEFAULT_ROLE_PROFILES["default"]))
    base["ui_theme"] = DEFAULT_UI_THEME
    if not prefs:
        return base
    for key in ("favorite_modules", "dashboard_cards", "quick_actions", "reports"):
        if prefs.get(key):
            base[key] = prefs[key]
    if prefs.get("ui_theme"):
        base["ui_theme"] = normalize_ui_theme(prefs.get("ui_theme"))
    return base


def load_dashboard_preferences(db, user_id: int | None) -> dict[str, Any]:
    if not user_id:
        return _merge_defaults(None, "default")
    ensure_user_context_schema(db)
    row = db.execute(
        "SELECT * FROM user_dashboard_preferences WHERE user_id=?",
        (user_id,),
    ).fetchone()
    if not row:
        return _merge_defaults(None, "default")
    role_profile = row["role_profile"] or "default"
    parsed: dict[str, Any] = {"role_profile": role_profile}
    for col in ("favorite_modules", "dashboard_cards", "quick_actions", "reports"):
        raw = row[col]
        if raw:
            try:
                parsed[col] = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                parsed[col] = []
        else:
            parsed[col] = []
    if "ui_theme" in row.keys():
        parsed["ui_theme"] = normalize_ui_theme(row["ui_theme"])
    return _merge_defaults(parsed, role_profile)


def save_dashboard_preferences(
    db,
    user_id: int,
    *,
    role_profile: str | None = None,
    favorite_modules: list[str] | None = None,
    dashboard_cards: list[str] | None = None,
    quick_actions: list[str] | None = None,
    reports: list[str] | None = None,
    ui_theme: str | None = None,
) -> dict[str, Any]:
    ensure_user_context_schema(db)
    existing = load_dashboard_preferences(db, user_id)
    payload = {
        "role_profile": role_profile or existing.get("role_profile", "default"),
        "favorite_modules": favorite_modules if favorite_modules is not None else existing.get("favorite_modules", []),
        "dashboard_cards": dashboard_cards if dashboard_cards is not None else existing.get("dashboard_cards", []),
        "quick_actions": quick_actions if quick_actions is not None else existing.get("quick_actions", []),
        "reports": reports if reports is not None else existing.get("reports", []),
        "ui_theme": normalize_ui_theme(ui_theme if ui_theme is not None else existing.get("ui_theme")),
    }
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """
        INSERT INTO user_dashboard_preferences(
            user_id, role_profile, favorite_modules, dashboard_cards, quick_actions, reports, ui_theme, updated_at
        ) VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
            role_profile=excluded.role_profile,
            favorite_modules=excluded.favorite_modules,
            dashboard_cards=excluded.dashboard_cards,
            quick_actions=excluded.quick_actions,
            reports=excluded.reports,
            ui_theme=excluded.ui_theme,
            updated_at=excluded.updated_at
        """,
        (
            user_id,
            payload["role_profile"],
            json.dumps(payload["favorite_modules"]),
            json.dumps(payload["dashboard_cards"]),
            json.dumps(payload["quick_actions"]),
            json.dumps(payload["reports"]),
            payload["ui_theme"],
            now,
        ),
    )
    db.commit()
    return payload


def infer_role_profile(department: str | None, role: str | None) -> str:
    text = f"{department or ''} {role or ''}".lower()
    if any(k in text for k in ("account", "finance", "treasury")):
        return "accounts"
    if any(k in text for k in ("store", "procurement", "inventory")):
        return "store"
    if any(k in text for k in ("project", "engineer", "planning", "site")):
        return "project_engineer"
    return "default"


# Maps Settings → dashboard card checkboxes to Command Centre KPI keys
_DASHBOARD_CARD_TO_KPI_KEYS: dict[str, set[str]] = {
    "active_projects": {"active_projects"},
    "payments": {"pending_expenses"},
    "receipts": {"revenue"},
    "gst": {"journal_entries"},
    "pending_approvals": {"pending_expenses", "journal_entries", "open_pos"},
    "boq": {"active_projects"},
    "dpr": {"active_projects"},
    "billing": {"revenue"},
    "grn": {"open_pos"},
    "material_request": {"open_pos"},
    "stock_status": {"open_pos"},
}

# Maps favourite module endpoints to department workspace slugs on Command Centre
_FAVORITE_MODULE_TO_DEPT_SLUG: dict[str, str] = {
    "accounts_payments": "accounts",
    "accounts_receipts": "accounts",
    "accounts_gst": "accounts",
    "accounts_reports": "accounts",
    "cost_planning": "planning-wbs",
    "boq_management": "projects",
    "dpr_entry": "projects",
    "client_billing_register": "projects",
    "projects": "projects",
    "store": "store",
    "material_request": "store",
    "purchase_orders": "store",
    "store_receipt": "store",
    "payroll": "hr-payroll",
    "fleet_dashboard": "vehicle",
    "fleet_vehicles": "vehicle",
    "qc_master": "qc",
    "plant_qc": "qc",
    "plant_dashboard": "plant-machinery",
    "subcontractors": "subcontract",
    "approvals": "accounts",
}

COMMAND_CENTRE_QUICK_ACTIONS: list[dict[str, str]] = [
    {"key": "payment_voucher", "label": "New voucher", "icon": "fa-file-invoice-dollar", "endpoint": "petty_cash"},
    {"key": "receipt_voucher", "label": "Receipt entry", "icon": "fa-hand-holding-dollar", "endpoint": "accounts_receipts"},
    {"key": "journal", "label": "Payment voucher", "icon": "fa-book", "endpoint": "accounts_payments"},
    {"key": "material_request", "label": "Material request", "icon": "fa-cart-shopping", "endpoint": "material_request"},
    {"key": "new_dpr", "label": "New DPR", "icon": "fa-clipboard-list", "endpoint": "dpr_entry"},
    {"key": "new_boq", "label": "New BOQ", "icon": "fa-table-list", "endpoint": "boq_management"},
    {"key": "new_bill", "label": "Client billing", "icon": "fa-file-invoice", "endpoint": "client_billing_register"},
    {"key": "grn", "label": "Store receipt (GRN)", "icon": "fa-dolly", "endpoint": "store_receipt"},
    {"key": "accounts_reports", "label": "Financial report", "icon": "fa-chart-line", "endpoint": "accounts_reports"},
]


def filter_command_centre_kpis(kpis: list[dict], dashboard_cards: list[str] | None) -> list[dict]:
    """Show KPIs matching user dashboard card preferences; empty prefs = show all."""
    if not dashboard_cards:
        return kpis
    allowed: set[str] = {"workforce"}
    for card in dashboard_cards:
        allowed.update(_DASHBOARD_CARD_TO_KPI_KEYS.get(card, set()))
    if not allowed - {"workforce"}:
        return kpis
    filtered = [k for k in kpis if k.get("key") in allowed]
    return filtered if filtered else kpis


def filter_command_centre_dept_cards(
    cards: list[dict], favorite_modules: list[str] | None
) -> list[dict]:
    """Show department tiles linked to user's favourite modules; empty prefs = show all."""
    if not favorite_modules:
        return cards
    slugs: set[str] = set()
    for mod in favorite_modules:
        slug = _FAVORITE_MODULE_TO_DEPT_SLUG.get(mod)
        if slug:
            slugs.add(slug)
    if not slugs:
        return cards
    filtered = [c for c in cards if c.get("slug") in slugs]
    return filtered if filtered else cards


def filter_command_centre_quick_actions(
    quick_actions: list[str] | None,
) -> list[dict[str, str]]:
    """Return quick-action buttons for Command Centre; empty prefs = defaults from role profile."""
    catalog = COMMAND_CENTRE_QUICK_ACTIONS
    if not quick_actions:
        return catalog
    allowed = set(quick_actions)
    filtered = [a for a in catalog if a["key"] in allowed]
    return filtered if filtered else catalog
