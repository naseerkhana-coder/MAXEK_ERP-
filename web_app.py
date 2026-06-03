"""MAXEK ERP Streamlit entry point."""

import streamlit as st

from modules.branding import ERP_DISPLAY_NAME
from modules.database import init_db
from modules.erp_router import PAGE_HANDLERS
from modules.navigation import allowed_pages_for_role, normalize_page_key
from modules.ui import (
    add_watermark,
    inject_global_css,
    render_page_header,
    render_sidebar,
    show_login_page,
    wrap_page,
)


def _init_session_state():
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("user_name", "")
    st.session_state.setdefault("user_role", "Admin")
    st.session_state.setdefault("page", "dash_mgmt")
    st.session_state.page = normalize_page_key(st.session_state.get("page"))


def _logout():
    for key in (
        "logged_in",
        "user_name",
        "user_role",
        "page",
        "worker_id",
        "worker_name",
        "finance_view",
        "_finance_hide_toolbar",
        "_finance_hub_entry_type",
        "settings_focus",
        "sidebar_open_section",
        "sidebar_favorites",
        "sidebar_recent",
        "sidebar_menu_search",
        "sidebar_collapsed",
        "login_remember_user",
        "login_saved_username",
        "clients_projects_tab",
        "store_tab",
        "subcontractor_hint",
    ):
        st.session_state.pop(key, None)
    st.rerun()


def _allowed_pages():
    return allowed_pages_for_role(st.session_state.get("user_role", "Admin"))


def _render_current_page():
    current_page = st.session_state.get("page", "dash_mgmt")
    if current_page not in _allowed_pages():
        st.warning("This role does not have access to that page.")
        st.session_state.page = "dash_mgmt"
        st.rerun()
        return

    page_handler = PAGE_HANDLERS.get(current_page)
    if page_handler is None:
        st.session_state.page = "dash_mgmt"
        st.rerun()
        return

    wrap_page(page_handler)


def main():
    st.set_page_config(
        page_title=ERP_DISPLAY_NAME,
        page_icon="🏗️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_db()
    _init_session_state()

    if not st.session_state.logged_in:
        show_login_page()
        return

    inject_global_css()
    add_watermark()
    st.markdown('<div class="maxek-app-layer">', unsafe_allow_html=True)
    with st.sidebar:
        render_sidebar(
            st.session_state.get("user_name", "User"),
            _logout,
            _allowed_pages(),
        )
    render_page_header(
        st.session_state.get("user_name", "User"),
        _logout,
        _allowed_pages(),
    )
    _render_current_page()
    st.markdown("</div>", unsafe_allow_html=True)


main()
