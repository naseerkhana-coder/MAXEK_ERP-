"""MAXEK ERP Streamlit entry point."""

import time

import streamlit as st

from modules.branding import ERP_DISPLAY_NAME
from modules.database import _finance_setting, init_db
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
    st.session_state.setdefault("user_id", "")
    st.session_state.setdefault("username", "")
    st.session_state.setdefault("user_name", "")
    st.session_state.setdefault("user_role", "Admin")
    st.session_state.setdefault("page", "dash_mgmt")
    st.session_state.page = normalize_page_key(st.session_state.get("page"))


def _session_timeout_seconds() -> int:
    try:
        minutes = int(_finance_setting("session_timeout_minutes", "480") or 480)
    except ValueError:
        minutes = 480
    return max(15, minutes) * 60


def _check_session_timeout() -> bool:
    """Return True if session was expired and user logged out."""
    if not st.session_state.get("logged_in"):
        return False
    now = time.time()
    last = st.session_state.get("last_activity", now)
    if now - last > _session_timeout_seconds():
        _logout(silent=True)
        return True
    st.session_state.last_activity = now
    return False


def _logout(silent: bool = False):
    for key in (
        "logged_in",
        "user_id",
        "username",
        "user_name",
        "user_role",
        "account_focus",
        "last_activity",
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
    if silent:
        st.session_state["session_expired_msg"] = True
    st.rerun()


def _hydrate_user_id_from_session():
    """Backfill user_id for sessions created before profile/password feature."""
    if st.session_state.get("user_id") or not st.session_state.get("logged_in"):
        return
    name = st.session_state.get("user_name", "")
    role = st.session_state.get("user_role", "")
    if not name:
        return
    from modules.database import get_conn

    conn = get_conn()
    rows = conn.execute(
        "SELECT user_id, username FROM users WHERE full_name = ? AND role = ?",
        (name, role),
    ).fetchall()
    conn.close()
    if len(rows) == 1:
        st.session_state.user_id = rows[0][0]
        st.session_state.username = rows[0][1]


def _allowed_pages():
    return allowed_pages_for_role(st.session_state.get("user_role", "Admin"))


def _enforce_password_change():
    user_id = st.session_state.get("user_id", "")
    if not user_id:
        return
    from modules.user_account import user_must_change_password

    if not user_must_change_password(user_id):
        return
    if st.session_state.get("page") == "account_profile":
        return
    st.warning("Change your password to continue. You are being redirected to My Account.")
    st.session_state.page = "account_profile"
    st.session_state.account_focus = "password"
    st.rerun()


def _render_current_page():
    _enforce_password_change()
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
        if st.session_state.pop("session_expired_msg", False):
            st.warning("Your session expired due to inactivity. Please log in again.")
        show_login_page()
        return

    if _check_session_timeout():
        return

    _hydrate_user_id_from_session()

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
    user_id = st.session_state.get("user_id", "")
    if user_id:
        from modules.user_account import user_must_change_password

        if user_must_change_password(user_id):
            st.warning(
                "Your password must be changed before you can use the ERP. "
                "Open **My Profile** from the menu (top right) → **Change Password**."
            )
    _render_current_page()
    st.markdown("</div>", unsafe_allow_html=True)


main()
