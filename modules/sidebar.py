"""ERP sidebar — accordion menu, search, and quick access."""

from __future__ import annotations

import base64
import os

import streamlit as st

from modules.branding import ERP_BRAND, ERP_DISPLAY_NAME, ERP_SIDEBAR_TAGLINE
from modules.navigation import (
    MENU_SECTIONS,
    QUICK_ACCESS_ITEMS,
    page_label,
    section_for_page,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_SVG_PATH = os.path.join(BASE_DIR, "assets", "logo", "maxek_logo.svg")
LOGO_PNG_PATH = os.path.join(BASE_DIR, "assets", "logo", "maxek_logo.png")


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
    st.session_state.setdefault("sidebar_menu_search", "")
    st.session_state.setdefault("sidebar_collapsed", False)
    st.session_state.setdefault("sidebar_open_section", None)


def _collapsed() -> bool:
    return bool(st.session_state.get("sidebar_collapsed"))


def _navigate(page_key: str) -> None:
    section = section_for_page(page_key)
    if section:
        st.session_state.sidebar_open_section = section
    st.session_state.page = page_key
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


def _render_quick_access(allowed: set[str], page: str) -> None:
    items = [(k, lbl, icon) for k, lbl, icon in QUICK_ACCESS_ITEMS if k in allowed]
    if not items or _collapsed():
        return
    st.markdown('<div class="maxek-sidebar-block-title">⭐ Quick Access</div>', unsafe_allow_html=True)
    cols = st.columns(len(items))
    for col, (key, label, icon) in zip(cols, items):
        with col:
            if st.button(
                icon,
                key=f"sidebar_quick_{key}",
                help=label,
                type=_sidebar_btn_type(page == key),
            ):
                _navigate(key)


def _render_menu_item(section_id: str, key: str, label: str, page: str) -> None:
    if st.button(
        label,
        key=f"sidebar_{section_id}_{key}",
        width="stretch",
        type=_sidebar_btn_type(page == key),
    ):
        _navigate(key)


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

        arrow = "▼" if is_open else "▶"
        header_active = current_section == section_id
        if st.button(
            _section_label(section_icon, section_label, arrow),
            key=f"sidebar_hdr_{section_id}",
            width="stretch",
            type=_sidebar_btn_type(header_active and (collapsed or not is_open)),
            help=section_label if collapsed else None,
        ):
            _toggle_section(section_id)

        if is_open:
            st.markdown(f'<div class="maxek-sidebar-submenu" data-section="{section_id}">', unsafe_allow_html=True)
            for _group_id, group_label, visible_items in visible_groups:
                for key, label in visible_items:
                    display = f"  {label}" if group_label else label
                    _render_menu_item(section_id, key, display, page)
            st.markdown("</div>", unsafe_allow_html=True)


def render_erp_sidebar(user_name: str, allowed_pages=None) -> None:
    """Render the full ERP sidebar inside ``st.sidebar``."""
    page = st.session_state.get("page", "dash_mgmt")
    _init_sidebar_state(page)
    allowed = set(allowed_pages or {"dash_mgmt"})

    _render_state_marker()
    st.markdown('<div class="maxek-sidebar-shell">', unsafe_allow_html=True)
    _render_collapse_control()
    _render_brand()
    search_query = _render_search_box()
    _render_quick_access(allowed, page)
    if not _collapsed():
        st.markdown('<div class="maxek-sidebar-menu-title">Modules</div>', unsafe_allow_html=True)
    st.markdown('<div class="maxek-sidebar-nav-start"></div>', unsafe_allow_html=True)
    _render_sections(allowed, page, search_query)
    st.markdown('<div class="maxek-sidebar-nav-end"></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if not _collapsed():
        st.markdown(
            """
            <div class="maxek-sidebar-help-card">
              <strong>Need Help?</strong>
              <span>Contact your system administrator or open Administration → Users for access requests.</span>
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
