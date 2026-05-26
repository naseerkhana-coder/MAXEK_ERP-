"""MAXEK ERP Streamlit entry point."""

import streamlit as st

from modules.database import init_db
from modules.billing import page_billing
from modules.dpr import page_dpr
from modules.finance import page_finance
from modules.pages import (
    page_attendance,
    page_clients_projects,
    page_employee_management,
    page_payroll,
    page_reports,
    page_settings,
    page_subcontractors,
)
from modules.store import page_store
from modules.ui import (
    inject_global_css,
    render_dashboard_home,
    render_page_header,
    render_sidebar,
    show_login_page,
    wrap_page,
)

PAGE_HANDLERS = {
    "employee_management": page_employee_management,
    "subcontractors": page_subcontractors,
    "attendance": page_attendance,
    "dpr": page_dpr,
    "billing": page_billing,
    "payroll": page_payroll,
    "finance": page_finance,
    "store": page_store,
    "clients_projects": page_clients_projects,
    "reports": page_reports,
    "settings": page_settings,
}

ROLE_PERMISSIONS = {
    "Admin": set(PAGE_HANDLERS.keys()) | {"dashboard"},
    "HR": {"dashboard", "employee_management", "attendance", "reports", "settings"},
    "MD": {"dashboard", "finance", "store", "dpr", "billing", "reports"},
    "Accountant": {"dashboard", "payroll", "finance", "store", "dpr", "billing", "reports"},
    "Project Manager": {"dashboard", "clients_projects", "subcontractors", "attendance", "finance", "store", "dpr", "reports"},
    "Site Engineer": {"dashboard", "attendance", "clients_projects", "subcontractors", "finance", "store", "dpr", "reports"},
}


def _init_session_state():
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("user_name", "")
    st.session_state.setdefault("user_role", "Admin")
    st.session_state.setdefault("page", "dashboard")
    legacy_page = st.session_state.get("page")
    if legacy_page in ("clients", "projects"):
        st.session_state.page = "clients_projects"
    elif legacy_page in ("payments", "expenses"):
        st.session_state.page = "finance"


def _logout():
    for key in ("logged_in", "user_name", "user_role", "page", "worker_id", "worker_name"):
        st.session_state.pop(key, None)
    st.rerun()


def _allowed_pages():
    return ROLE_PERMISSIONS.get(st.session_state.get("user_role", "Admin"), {"dashboard"})


def _render_current_page():
    current_page = st.session_state.get("page", "dashboard")
    if current_page not in _allowed_pages():
        st.warning("This role does not have access to that page.")
        st.session_state.page = "dashboard"
        st.rerun()
        return

    if current_page == "dashboard":
        render_dashboard_home(st.session_state.get("user_name", "User"))
        return

    page_handler = PAGE_HANDLERS.get(current_page)
    if page_handler is None:
        st.session_state.page = "dashboard"
        st.rerun()
        return

    wrap_page(page_handler)


def main():
    st.set_page_config(
        page_title="MAXEK ERP",
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
    st.markdown('<div class="maxek-app-layer">', unsafe_allow_html=True)
    with st.sidebar:
        render_sidebar(
            st.session_state.get("user_name", "User"),
            _logout,
            _allowed_pages(),
        )
    render_page_header(st.session_state.get("user_name", "User"))
    _render_current_page()
    st.markdown("</div>", unsafe_allow_html=True)


main()
