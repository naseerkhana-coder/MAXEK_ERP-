"""Department-scoped tab/module permissions for MAXEK ERP users."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

# Department portals used in Settings > Users permission assignment (slug, label).
PERMISSION_DEPARTMENT_CHOICES: list[tuple[str, str]] = [
    ("accounts", "Accounts"),
    ("projects", "Projects"),
    ("store", "Store"),
    ("procurement", "Procurement"),
    ("hr-payroll", "HR & Payroll"),
    ("vehicle", "Vehicle & Fleet"),
    ("plant-machinery", "Plant & Machinery"),
    ("mechanical", "Mechanical"),
    ("engineering", "Engineering & Planning"),
    ("subcontract", "Subcontractor"),
    ("qc", "Quality Control"),
    ("administration", "Administration & Compliance"),
    ("tender", "Tender"),
    ("reports", "Reports"),
    ("consultancy", "Consultancy"),
]


def tab_key_for_item(item: dict[str, Any]) -> str:
    """Stable key for a portal/nav menu item."""
    endpoint = (item.get("endpoint") or "").strip()
    anchor = (item.get("anchor") or "").strip()
    label = (item.get("label") or "").strip()
    if anchor:
        return f"{endpoint}#{anchor}"
    if label:
        return f"{endpoint}::{label}"
    return endpoint


def _dedupe_tabs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    tabs: list[dict[str, Any]] = []
    for raw in items:
        if not raw.get("endpoint"):
            continue
        key = tab_key_for_item(raw)
        if key in seen:
            continue
        seen.add(key)
        tabs.append(
            {
                "tab_key": key,
                "endpoint": raw.get("endpoint", ""),
                "label": raw.get("label", key),
                "icon": raw.get("icon", "fa-folder"),
                "active_endpoints": list(raw.get("active_endpoints") or [raw.get("endpoint")]),
            }
        )
    return tabs


def build_department_tab_catalog(
    department_slug: str,
    *,
    portal: dict[str, Any] | None,
    nav_group: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Tabs/modules assignable for a department — portal menu only (never NAV_GROUPS)."""
    _ = department_slug
    _ = nav_group
    items: list[dict[str, Any]] = []
    if portal:
        items.extend(portal.get("menu") or [])
        items.extend(portal.get("quick_tabs") or [])
    return _dedupe_tabs(items)


def ensure_user_tab_permissions_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_tab_permissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            department_slug TEXT NOT NULL,
            tab_key TEXT NOT NULL,
            endpoint TEXT,
            label TEXT,
            granted INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT,
            UNIQUE(user_id, department_slug, tab_key),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_tab_perm_user "
        "ON user_tab_permissions(user_id, department_slug)"
    )


def user_has_tab_restrictions(db, user_id: int) -> bool:
    ensure_user_tab_permissions_schema(db)
    row = db.execute(
        "SELECT 1 FROM user_tab_permissions WHERE user_id=? AND granted=1 LIMIT 1",
        (user_id,),
    ).fetchone()
    return row is not None


def get_granted_tab_keys_for_department(db, user_id: int, department_slug: str) -> set[str]:
    ensure_user_tab_permissions_schema(db)
    rows = db.execute(
        """
        SELECT tab_key FROM user_tab_permissions
        WHERE user_id=? AND department_slug=? AND granted=1
        """,
        (user_id, department_slug),
    ).fetchall()
    return {row["tab_key"] for row in rows}


def get_granted_endpoints_for_user(db, user_id: int) -> set[str]:
    ensure_user_tab_permissions_schema(db)
    rows = db.execute(
        """
        SELECT endpoint FROM user_tab_permissions
        WHERE user_id=? AND granted=1 AND endpoint IS NOT NULL AND TRIM(endpoint)!=''
        """,
        (user_id,),
    ).fetchall()
    return {(row["endpoint"] or "").strip() for row in rows if row["endpoint"]}


def get_user_department_tab_state(
    db,
    user_id: int,
    department_slug: str,
    catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return catalog tabs with granted flag for UI checkboxes."""
    granted = get_granted_tab_keys_for_department(db, user_id, department_slug)
    has_dept_rows = bool(
        db.execute(
            "SELECT 1 FROM user_tab_permissions WHERE user_id=? AND department_slug=? LIMIT 1",
            (user_id, department_slug),
        ).fetchone()
    )
    result: list[dict[str, Any]] = []
    for tab in catalog:
        entry = dict(tab)
        if not has_dept_rows:
            entry["granted"] = True
        else:
            entry["granted"] = tab["tab_key"] in granted
        result.append(entry)
    return result


def save_user_department_tab_permissions(
    db,
    user_id: int,
    department_slug: str,
    granted_tab_keys: list[str],
    catalog: list[dict[str, Any]],
) -> None:
    ensure_user_tab_permissions_schema(db)
    catalog_by_key = {tab["tab_key"]: tab for tab in catalog}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "DELETE FROM user_tab_permissions WHERE user_id=? AND department_slug=?",
        (user_id, department_slug),
    )
    for tab_key in granted_tab_keys:
        tab = catalog_by_key.get(tab_key)
        if not tab:
            continue
        db.execute(
            """
            INSERT INTO user_tab_permissions(
                user_id, department_slug, tab_key, endpoint, label, granted, updated_at
            ) VALUES(?,?,?,?,?,1,?)
            """,
            (
                user_id,
                department_slug,
                tab_key,
                tab.get("endpoint"),
                tab.get("label"),
                now,
            ),
        )


def _item_allowed(
    item: dict[str, Any],
    *,
    granted_keys: set[str],
    granted_endpoints: set[str],
    has_dept_restrictions: bool,
    scope_endpoints_to_department: bool = False,
) -> bool:
    if not has_dept_restrictions:
        return True
    key = tab_key_for_item(item)
    if key in granted_keys:
        return True
    if scope_endpoints_to_department:
        return False
    active = item.get("active_endpoints") or [item.get("endpoint")]
    return any(ep in granted_endpoints for ep in active if ep)


def filter_portal_menu_for_user(
    db,
    user_id: int,
    department_slug: str,
    menu: list[dict[str, Any]],
    *,
    full_access: bool,
) -> list[dict[str, Any]]:
    if full_access or not user_has_tab_restrictions(db, user_id):
        return menu
    granted_keys = get_granted_tab_keys_for_department(db, user_id, department_slug)
    has_dept_rows = bool(
        db.execute(
            "SELECT 1 FROM user_tab_permissions WHERE user_id=? AND department_slug=? LIMIT 1",
            (user_id, department_slug),
        ).fetchone()
    )
    if not has_dept_rows:
        return menu
    return [
        item
        for item in menu
        if _item_allowed(
            item,
            granted_keys=granted_keys,
            granted_endpoints=set(),
            has_dept_restrictions=True,
            scope_endpoints_to_department=True,
        )
    ]


def apply_user_tab_permissions_to_nav_groups(
    db,
    user_id: int,
    nav_groups: list[dict[str, Any]],
    *,
    full_access: bool,
    department_slug_for_nav: Callable[[str], str | None] | None = None,
) -> list[dict[str, Any]]:
    """Filter nav group items based on per-department tab grants."""
    if full_access or not user_has_tab_restrictions(db, user_id):
        return nav_groups

    granted_endpoints = get_granted_endpoints_for_user(db, user_id)
    dept_grants: dict[str, set[str]] = {}

    def grants_for_slug(dept_slug: str) -> tuple[set[str], bool]:
        if dept_slug not in dept_grants:
            dept_grants[dept_slug] = get_granted_tab_keys_for_department(db, user_id, dept_slug)
        keys = dept_grants[dept_slug]
        has_rows = bool(
            db.execute(
                "SELECT 1 FROM user_tab_permissions WHERE user_id=? AND department_slug=? LIMIT 1",
                (user_id, dept_slug),
            ).fetchone()
        )
        return keys, has_rows

    filtered: list[dict[str, Any]] = []
    for group in nav_groups:
        slug = group.get("slug") or ""
        dept_slug = department_slug_for_nav(slug) if department_slug_for_nav else slug
        if not dept_slug:
            filtered.append(group)
            continue
        granted_keys, has_dept_rows = grants_for_slug(dept_slug)
        if not has_dept_rows:
            filtered.append(group)
            continue
        items = group.get("items") or []
        kept = [
            item
            for item in items
            if _item_allowed(
                item,
                granted_keys=granted_keys,
                granted_endpoints=granted_endpoints,
                has_dept_restrictions=True,
            )
        ]
        if not kept:
            continue
        copy = dict(group)
        copy["items"] = kept
        filtered.append(copy)
    return filtered


def nav_slug_to_permission_department(nav_slug: str) -> str | None:
    """Map NAV_GROUPS slug to primary permission department slug."""
    mapping = {
        "dashboard": "reports",
        "project-management": "projects",
        "engineering-smartqto": "engineering",
        "store-procurement": "procurement",
        "accounts-finance": "accounts",
        "hr-payroll": "hr-payroll",
        "plant-machinery": "plant-machinery",
        "qc": "qc",
        "subcontract-management": "subcontract",
        "admin-compliance": "administration",
        "reports-analytics": "reports",
        "settings": None,
        "approvals": None,
        "erp-administration": None,
        "fleet-mechanical": "vehicle",
        "plant-operations": "plant-machinery",
        "store-section": "store",
    }
    return mapping.get(nav_slug, nav_slug or None)
