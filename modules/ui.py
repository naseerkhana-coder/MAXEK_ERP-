"""Global UI: CSS, shell, branding, login, and dashboard."""

import base64
import os
from datetime import datetime

import streamlit as st

from modules.database import (
    DASHBOARD_SECTION_ORDER_DEFAULT,
    dashboard_notifications,
    dashboard_recent_transactions,
    get_dashboard_settings,
    get_conn,
    get_dashboard_role_visibility,
    load_countries,
    load_districts,
    kpi_stats,
    load_managers,
    load_regions,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME_CSS_PATH = os.path.join(BASE_DIR, "styles", "theme.css")
LOGO_SVG_PATH = os.path.join(BASE_DIR, "assets", "logo", "maxek_logo.svg")
LOGO_PNG_PATH = os.path.join(BASE_DIR, "assets", "logo", "maxek_logo.png")

NAV_ITEMS = [
    ("dashboard", "Dashboard", "🏠"),
    ("employee_management", "Employee Management", "👥"),
    ("attendance", "Attendance", "🕒"),
    ("dpr", "DPR", "📋"),
    ("billing", "Billing", "🧾"),
    ("payroll", "Payroll", "💰"),
    ("finance", "Finance", "💳"),
    ("store", "Store", "🏬"),
    ("clients_projects", "Clients & Projects", "🏢"),
    ("subcontractors", "Sub Contractors", "🧱"),
    ("reports", "Reports", "📊"),
    ("settings", "Settings", "⚙️"),
]


def _logo_data_uri():
    if os.path.isfile(LOGO_PNG_PATH):
        with open(LOGO_PNG_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{b64}"
    if os.path.isfile(LOGO_SVG_PATH):
        with open(LOGO_SVG_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/svg+xml;base64,{b64}"
    return ""


def add_watermark():
    uri = _logo_data_uri()
    if not uri:
        return
    st.markdown(
        f'<img src="{uri}" class="maxek-watermark" alt="" />',
        unsafe_allow_html=True,
    )


def inject_global_css():
    css = ""
    if os.path.isfile(THEME_CSS_PATH):
        with open(THEME_CSS_PATH, encoding="utf-8") as f:
            css = f.read()
    css += """
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    """
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _select_index(options, default_value):
    if not options:
        return 0
    if default_value == "" and "" in options:
        return options.index("")
    return options.index(default_value) if default_value in options else 0


def location_dropdowns(
    key_prefix="loc",
    default_country="India",
    default_region=None,
    default_district=None,
    allow_blank=False,
):
    c1, c2, c3 = st.columns(3)
    countries = load_countries() or ["India"]
    if allow_blank:
        countries = [""] + countries
    country_index = _select_index(countries, default_country)
    with c1:
        country = st.selectbox("Country", countries, index=country_index, key=f"{key_prefix}_country")

    regions = load_regions(country) if country else []
    if allow_blank:
        regions = [""] + regions
    regions = regions or [""]
    region_index = _select_index(regions, default_region)
    with c2:
        region = st.selectbox("Region / State", regions, index=region_index, key=f"{key_prefix}_region")

    districts = load_districts(country, region) if country and region else []
    if allow_blank:
        districts = [""] + districts
    districts = districts or [""]
    district_index = _select_index(districts, default_district)
    with c3:
        district = st.selectbox("District", districts, index=district_index, key=f"{key_prefix}_district")

    return country, region, district


def render_sidebar(user_name: str, on_logout, allowed_pages=None):
    page = st.session_state.get("page", "dashboard")
    stats = kpi_stats()
    dashboard_settings = get_dashboard_settings()
    uri = _logo_data_uri()
    logo_img = f'<img src="{uri}" alt="MAXEK" />' if uri else ""
    user_role = st.session_state.get("user_role", "Admin")
    st.markdown(
        f"""
        <div class="maxek-sidebar-shell">
          <div class="maxek-sidebar-brand">
            {logo_img}
            <div>
              <div class="maxek-sidebar-title">MAXEK ERP</div>
              <div class="maxek-sidebar-subtitle">Construction ERP System</div>
            </div>
          </div>
          <div class="maxek-sidebar-section">Main Menu</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    allowed_pages = set(allowed_pages or [key for key, _, _ in NAV_ITEMS])
    for key, label, icon in NAV_ITEMS:
        if key not in allowed_pages:
            continue
        if st.button(
            f"{icon}  {label}",
            key=f"sidebar_{key}",
            width="stretch",
            type="primary" if page == key else "secondary",
        ):
            st.session_state.page = key
            st.rerun()

    if dashboard_settings.get("show_sidebar_cashflow", True):
        st.markdown(
            f"""
            <div class="maxek-cash-card">
              <div class="maxek-cash-title">Daily Cash Flow</div>
              <div class="maxek-cash-row"><span>Opening Balance</span><strong>Rs 0.00</strong></div>
              <div class="maxek-cash-row"><span>Cash In</span><strong>Rs {stats['cash_in']:,.2f}</strong></div>
              <div class="maxek-cash-row"><span>Cash Out</span><strong>Rs {stats['cash_out']:,.2f}</strong></div>
              <div class="maxek-cash-row maxek-cash-total"><span>Closing Balance</span><strong>Rs {stats['cash_in_hand']:,.2f}</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown(
        f"""
        <div class="maxek-sidebar-user">
          <strong>{user_name}</strong>
          <span>{user_role}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Logout", key="sidebar_logout", width="stretch"):
        on_logout()


def render_page_header(user_name: str):
    left, middle, right = st.columns([1.1, 2.2, 1.5])
    current_page = st.session_state.get("page", "dashboard").replace("_", " ").title()
    user_role = st.session_state.get("user_role", "Admin")
    with left:
        st.markdown(
            f"""
            <div class="maxek-header-pill">
              <div class="maxek-header-page">{current_page}</div>
              <div class="maxek-header-caption">MAXEK ERP System</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with middle:
        st.text_input(
            "Search",
            key="global_search",
            label_visibility="collapsed",
            placeholder="Search anything...",
        )
    with right:
        today = datetime.now()
        st.markdown(
            f"""
            <div class="maxek-header-actions">
              <div class="maxek-header-chip">Calendar</div>
              <div class="maxek-header-chip">Alerts</div>
              <div class="maxek-header-user">
                <div class="maxek-header-user-name">{user_name}</div>
                <div class="maxek-header-user-meta">{user_role} · {today.strftime('%d %b %Y')}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _overview_panel(title, items):
    html = f'<div class="maxek-overview-card"><div class="maxek-overview-title">{title}</div>'
    for label, value in items:
        html += (
            '<div class="maxek-overview-row">'
            f"<span>{label}</span><strong>{value}</strong>"
            "</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _render_dashboard_welcome(user_name: str):
    st.markdown(
        f"""
        <div class="maxek-dashboard-intro">
          <div>
            <h1>Welcome back, {user_name}</h1>
            <p>Here's what's happening with your business today.</p>
          </div>
          <div class="maxek-dashboard-date">
            <div>{datetime.now().strftime('%d %b %Y')}</div>
            <span>{datetime.now().strftime('%A, %I:%M %p')}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_dashboard_kpis(stats):
    cards = [
        ("👥", "Total Employees", stats["employees"], "Workforce"),
        ("👷", "Total Workers", stats["total_workers"], "Field teams"),
        ("📁", "Active Projects", stats["active_projects"], "Running sites"),
        ("🏢", "Total Clients", stats["clients"], "Business accounts"),
        ("💰", "Pending Salary", stats["pending_salary"], "Needs action"),
        ("🧾", "Monthly Expenses", f"Rs {stats['monthly_expense']:,.0f}", "Current month"),
    ]
    html_parts = ['<div class="maxek-kpi-grid">']
    for icon, label, value, helper in cards:
        html_parts.append(
            f'<div class="maxek-kpi-card">'
            f'<div class="maxek-kpi-icon">{icon}</div>'
            f'<div class="maxek-kpi-label">{label}</div>'
            f'<div class="maxek-kpi-value">{value}</div>'
            f'<div class="maxek-kpi-helper">{helper}</div>'
            f"</div>"
        )
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def _render_dashboard_overviews(stats, dashboard_settings):
    panels = []
    if dashboard_settings.get("show_attendance_overview", True):
        panels.append(
            (
                "Attendance Overview (Today)",
                [
                    ("Present Entries", stats["attendance_today"]),
                    ("Active Workers", stats["active_workers"]),
                    ("Pending Salary", stats["pending_salary"]),
                ],
            )
        )
    if dashboard_settings.get("show_project_overview", True):
        panels.append(
            (
                "Project Overview",
                [
                    ("Active Projects", stats["active_projects"]),
                    ("Clients", stats["clients"]),
                    ("Sub Contractors", stats["subcontractors"]),
                ],
            )
        )
    if dashboard_settings.get("show_expense_overview", True):
        panels.append(
            (
                "Expenses Overview",
                [
                    ("Cash In", f"Rs {stats['cash_in']:,.2f}"),
                    ("Cash Out", f"Rs {stats['cash_out']:,.2f}"),
                    ("Cash In Hand", f"Rs {stats['cash_in_hand']:,.2f}"),
                ],
            )
        )
    if not panels:
        return False

    columns = st.columns(len(panels))
    for col, (title, items) in zip(columns, panels):
        with col:
            _overview_panel(title, items)
    return True


def _render_dashboard_recent_payments():
    st.subheader("Recent Payments")
    payments_df = dashboard_recent_transactions()
    if payments_df.empty:
        st.info("No payments or payroll transactions available yet.")
    else:
        st.dataframe(payments_df, width="stretch", hide_index=True)


def _render_dashboard_notifications():
    st.subheader("Notifications")
    for item in dashboard_notifications():
        st.markdown(
            f"""
            <div class="maxek-note-item">
              <strong>{item['title']}</strong>
              <span>{item['detail']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_dashboard_home(user_name: str):
    stats = kpi_stats()
    dashboard_settings = get_dashboard_settings()
    role_visibility = get_dashboard_role_visibility()
    user_role = st.session_state.get("user_role", "Admin")
    rendered_any = False

    section_visibility = role_visibility.get(
        user_role,
        {section_key: True for section_key in DASHBOARD_SECTION_ORDER_DEFAULT},
    )
    section_order = dashboard_settings.get("section_order", DASHBOARD_SECTION_ORDER_DEFAULT[:])

    section_renderers = {
        "welcome": lambda: _render_dashboard_welcome(user_name),
        "kpis": lambda: _render_dashboard_kpis(stats),
        "overviews": lambda: _render_dashboard_overviews(stats, dashboard_settings),
        "recent_payments": _render_dashboard_recent_payments,
        "notifications": _render_dashboard_notifications,
    }
    section_enabled = {
        "welcome": dashboard_settings.get("show_welcome", True),
        "kpis": dashboard_settings.get("show_kpis", True),
        "overviews": any(
            [
                dashboard_settings.get("show_attendance_overview", True),
                dashboard_settings.get("show_project_overview", True),
                dashboard_settings.get("show_expense_overview", True),
            ]
        ),
        "recent_payments": dashboard_settings.get("show_recent_payments", True),
        "notifications": dashboard_settings.get("show_notifications", True),
    }

    for section_key in section_order:
        if not section_enabled.get(section_key, False):
            continue
        if not section_visibility.get(section_key, True):
            continue
        result = section_renderers[section_key]()
        if result is not False:
            rendered_any = True

    if not rendered_any:
        st.info("All dashboard sections are hidden. Enable them from Settings > Dashboard.")


def show_login_page():
    inject_global_css()
    st.markdown(
        """
        <div class="maxek-login-marker"></div>
        <script>
        setTimeout(function () {
            document.querySelectorAll('input').forEach(function (el) {
                el.setAttribute('autocomplete', el.type === 'password' ? 'new-password' : 'off');
                el.setAttribute('autocorrect', 'off');
                el.setAttribute('autocapitalize', 'off');
                el.setAttribute('spellcheck', 'false');
                el.setAttribute('data-lpignore', 'true');
                el.setAttribute('data-form-type', 'other');
                if (el.type === 'password') {
                    el.setAttribute('name', 'maxek-password-field');
                } else {
                    el.setAttribute('name', 'maxek-username-field');
                }
            });
        }, 150);
        </script>
        """,
        unsafe_allow_html=True,
    )
    uri = _logo_data_uri()
    logo_block = f'<img src="{uri}" class="maxek-login-logo" alt="MAXEK" />' if uri else ""
    if logo_block:
        st.markdown(logo_block, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="maxek-login-title">MAXEK ERP Login</div>
        <div class="maxek-login-subtitle">Construction company operations dashboard</div>
        """,
        unsafe_allow_html=True,
    )
    username = st.text_input("Username", key="login_user", placeholder="Enter username")
    password = st.text_input("Password", type="password", key="login_pass", placeholder="Enter password")
    if st.button("Login", type="primary", width="stretch"):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT full_name, role FROM users WHERE username=? AND password=?",
            (username, password),
        )
        row = cur.fetchone()
        conn.close()
        if row:
            st.session_state.logged_in = True
            st.session_state.user_name = row[0]
            st.session_state.user_role = row[1] or "Admin"
            st.session_state.page = "dashboard"
            st.rerun()
        st.error("Invalid username or password.")
    st.caption("Default login: admin / 1234")


def wrap_page(content_fn):
    content_fn()
