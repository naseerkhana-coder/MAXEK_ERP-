"""ERP sidebar — accordion menu, search, favorites, and recent pages."""

from __future__ import annotations

import base64
import os

import streamlit as st

from modules.branding import ERP_BRAND, ERP_DISPLAY_NAME, ERP_SIDEBAR_TAGLINE
from modules.navigation import (
    MENU_DASHBOARD,
    MENU_SECTIONS,
    group_for_page,
    page_label,
    section_for_page,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_SVG_PATH = os.path.join(BASE_DIR, "assets", "logo", "maxek_logo.svg")
LOGO_PNG_PATH = os.path.join(BASE_DIR, "assets", "logo", "maxek_logo.png")

_MAX_RECENT = 6
_QUICK_ACCESS = (
    ("acc_payment", "Payment Voucher"),
    ("acc_receipt", "Receipt Voucher"),
    ("purch_invoice", "Purchase Invoice"),
    ("proj_boq", "BOQ Entry"),
    ("store_issue", "Material Issue"),
    ("hr_payroll", "Payroll Processing"),
)


def _logo_data_uri() -> str:
    if os.path.isfile(LOGO_PNG_PATH):
        with open(LOGO_PNG_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{b64}"
    if os.path.isfile(LOGO_SVG_PATH):
        with open(LOGO_SVG_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/svg+xml;base64,{b64}"
    return ""


def _init_sidebar_state(page: str) -> None:
    st.session_state.setdefault("sidebar_favorites", [])
    st.session_state.setdefault("sidebar_recent", [])
    st.session_state.setdefault("sidebar_menu_search", "")
    st.session_state.setdefault("sidebar_collapsed", False)
    st.session_state.setdefault("sidebar_open_groups", [])
    if "sidebar_open_section" not in st.session_state:
        st.session_state.sidebar_open_section = section_for_page(page)
    loc = group_for_page(page)
    if loc:
        key = f"{loc[0]}:{loc[1]}"
        open_groups = list(st.session_state.get("sidebar_open_groups") or [])
        if key not in open_groups:
            open_groups.append(key)
        st.session_state.sidebar_open_groups = open_groups


def _collapsed() -> bool:
    return bool(st.session_state.get("sidebar_collapsed"))


def _record_recent(page_key: str) -> None:
    if page_key == MENU_DASHBOARD[0]:
        return
    recent: list[str] = st.session_state.setdefault("sidebar_recent", [])
    if page_key in recent:
        recent.remove(page_key)
    recent.insert(0, page_key)
    st.session_state.sidebar_recent = recent[:_MAX_RECENT]


def _navigate(page_key: str) -> None:
    _record_recent(page_key)
    section = section_for_page(page_key)
    if section:
        st.session_state.sidebar_open_section = section
    st.session_state.page = page_key
    st.rerun()


def _toggle_favorite(page_key: str) -> None:
    favorites: list[str] = st.session_state.setdefault("sidebar_favorites", [])
    if page_key in favorites:
        favorites.remove(page_key)
    else:
        favorites.append(page_key)
    st.session_state.sidebar_favorites = favorites
    st.rerun()


def _toggle_section(section_id: str) -> None:
    if _collapsed():
        st.session_state.sidebar_collapsed = False
        st.session_state.sidebar_open_section = section_id
        st.rerun()
        return
    current = st.session_state.get("sidebar_open_section")
    st.session_state.sidebar_open_section = None if current == section_id else section_id
    st.rerun()


def _toggle_collapse() -> None:
    st.session_state.sidebar_collapsed = not _collapsed()
    st.rerun()


def _menu_matches_search(label: str, query: str) -> bool:
    return query.lower() in label.lower()


def _sidebar_btn_type(is_active: bool) -> str:
    return "primary" if is_active else "secondary"


def _section_label(icon: str, label: str, arrow: str = "") -> str:
    if _collapsed():
        return icon
    suffix = f"  {arrow}" if arrow else ""
    return f"{icon}  {label}{suffix}"


def _render_state_marker() -> None:
    collapsed = "true" if _collapsed() else "false"
    st.markdown(
        f'<div class="maxek-sidebar-state" data-collapsed="{collapsed}"></div>',
        unsafe_allow_html=True,
    )


def _render_collapse_control() -> None:
    label = "☰  Expand" if _collapsed() else "☰  Collapse"
    if st.button(label, key="sidebar_collapse_btn", width="stretch", type="secondary"):
        _toggle_collapse()


def _render_brand() -> None:
    uri = _logo_data_uri()
    logo_img = f'<img src="{uri}" alt="{ERP_BRAND}" />' if uri else ""
    if _collapsed():
        st.markdown(
            f'<div class="maxek-sidebar-brand maxek-sidebar-brand-collapsed">{logo_img}</div>',
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f"""
        <div class="maxek-sidebar-brand">
          {logo_img}
          <div>
            <div class="maxek-sidebar-title">{ERP_DISPLAY_NAME}</div>
            <div class="maxek-sidebar-subtitle">{ERP_SIDEBAR_TAGLINE}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_search_box() -> str:
    if _collapsed():
        return ""
    st.markdown('<div class="maxek-sidebar-search-label">🔍 Search Menu</div>', unsafe_allow_html=True)
    return st.text_input(
        "Search menu",
        key="sidebar_menu_search",
        placeholder="BOQ, Purchase Order, DPR, Petty Cash…",
        label_visibility="collapsed",
    ).strip()


def _render_favorites(allowed: set[str], page: str) -> None:
    favorites = [k for k in st.session_state.get("sidebar_favorites", []) if k in allowed]
    if _collapsed():
        return
    st.markdown('<div class="maxek-sidebar-block-title">⭐ Favorites</div>', unsafe_allow_html=True)
    if not favorites:
        st.caption("Pin screens with ☆ on any menu item.")
        return
    for key in favorites:
        label = page_label(key)
        if st.button(
            f"⭐  {label}",
            key=f"sidebar_favrow_{key}",
            width="stretch",
            type=_sidebar_btn_type(page == key),
        ):
            _navigate(key)


def _render_recent(allowed: set[str], page: str) -> None:
    if _collapsed():
        return
    recent = [k for k in st.session_state.get("sidebar_recent", []) if k in allowed]
    if not recent:
        return
    st.markdown('<div class="maxek-sidebar-block-title">Recently used</div>', unsafe_allow_html=True)
    for key in recent:
        label = page_label(key)
        if st.button(
            f"🕐  {label}",
            key=f"sidebar_recent_{key}",
            width="stretch",
            type=_sidebar_btn_type(page == key),
        ):
            _navigate(key)


def _render_dashboard(allowed: set[str], page: str) -> None:
    dash_key, dash_label, dash_icon = MENU_DASHBOARD
    if dash_key not in allowed:
        return
    st.markdown('<div class="maxek-sidebar-nav-start"></div>', unsafe_allow_html=True)
    if st.button(
        _section_label(dash_icon, dash_label),
        key=f"sidebar_{dash_key}",
        width="stretch",
        type=_sidebar_btn_type(page == dash_key),
        help=dash_label if _collapsed() else None,
    ):
        _navigate(dash_key)


def _toggle_group(section_id: str, group_id: str) -> None:
    key = f"{section_id}:{group_id}"
    open_groups = list(st.session_state.get("sidebar_open_groups") or [])
    if key in open_groups:
        open_groups.remove(key)
    else:
        open_groups.append(key)
    st.session_state.sidebar_open_groups = open_groups
    st.rerun()


def _group_open(section_id: str, group_id: str, search_query: str, has_active: bool) -> bool:
    if search_query:
        return True
    if has_active:
        return True
    return f"{section_id}:{group_id}" in list(st.session_state.get("sidebar_open_groups") or [])


def _render_menu_item(section_id: str, key: str, label: str, page: str) -> None:
    fav = key in st.session_state.get("sidebar_favorites", [])
    col_nav, col_star = st.columns([6, 1], gap="small")
    with col_nav:
        if st.button(
            label,
            key=f"sidebar_{section_id}_{key}",
            width="stretch",
            type=_sidebar_btn_type(page == key),
        ):
            _navigate(key)
    with col_star:
        star = "⭐" if fav else "☆"
        if st.button(star, key=f"sidebar_star_{section_id}_{key}", help="Toggle favorite"):
            _toggle_favorite(key)


def _render_sections(allowed: set[str], page: str, search_query: str) -> None:
    open_section = st.session_state.get("sidebar_open_section")
    current_section = section_for_page(page)
    collapsed = _collapsed()

    for section_id, section_label, section_icon, groups in MENU_SECTIONS:
        visible_groups: list[tuple[str, str | None, list[tuple[str, str]]]] = []
        for group_id, group_label, items in groups:
            visible_items = [(k, lbl) for k, lbl in items if k in allowed]
            if search_query:
                visible_items = [
                    (k, lbl)
                    for k, lbl in visible_items
                    if _menu_matches_search(lbl, search_query)
                    or _menu_matches_search(section_label, search_query)
                    or (group_label and _menu_matches_search(group_label, search_query))
                ]
            if visible_items:
                visible_groups.append((group_id, group_label, visible_items))

        if not visible_groups:
            continue

        is_open = not collapsed and (
            open_section == section_id or (bool(search_query) and bool(visible_groups))
        )
        if not collapsed and current_section == section_id and open_section is None:
            is_open = True

        arrow = "▼" if is_open else "▶"
        header_active = current_section == section_id and page != MENU_DASHBOARD[0]
        if st.button(
            _section_label(section_icon, section_label, arrow),
            key=f"sidebar_hdr_{section_id}",
            width="stretch",
            type=_sidebar_btn_type(header_active and (collapsed or not is_open)),
            help=section_label if collapsed else None,
        ):
            _toggle_section(section_id)

        if is_open:
            for group_id, group_label, visible_items in visible_groups:
                has_active = any(k == page for k, _ in visible_items)
                group_is_open = _group_open(section_id, group_id, search_query, has_active)
                if group_label:
                    group_arrow = "▼" if group_is_open else "▶"
                    if st.button(
                        f"  {group_arrow}  {group_label}",
                        key=f"sidebar_grp_{section_id}_{group_id}",
                        width="stretch",
                        type=_sidebar_btn_type(has_active),
                    ):
                        _toggle_group(section_id, group_id)
                    if not group_is_open:
                        continue
                for key, label in visible_items:
                    display = f"    {label}" if group_label else label
                    _render_menu_item(section_id, key, display, page)


def render_erp_sidebar(user_name: str, allowed_pages=None) -> None:
    """Render the full ERP sidebar inside ``st.sidebar``."""
    page = st.session_state.get("page", "dash_mgmt")
    _init_sidebar_state(page)
    allowed = set(allowed_pages or {MENU_DASHBOARD[0]})

    _render_state_marker()
    st.markdown('<div class="maxek-sidebar-shell">', unsafe_allow_html=True)
    _render_collapse_control()
    _render_brand()
    search_query = _render_search_box()
    _render_favorites(allowed, page)
    _render_recent(allowed, page)
    if not _collapsed():
        st.markdown('<div class="maxek-sidebar-menu-title">Modules</div>', unsafe_allow_html=True)
    _render_dashboard(allowed, page)
    _render_sections(allowed, page, search_query)
    st.markdown('<div class="maxek-sidebar-nav-end"></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if not _collapsed():
        st.markdown(
            f"""
            <div class="maxek-sidebar-footer">
              <div class="maxek-sidebar-user-name">{user_name}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <script>
        (function () {
          var marker = document.querySelector(".maxek-sidebar-state");
          if (!marker) return;
          document.body.classList.toggle("maxek-sidebar-collapsed", marker.dataset.collapsed === "true");
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )
