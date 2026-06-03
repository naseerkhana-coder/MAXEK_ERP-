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
from modules.branding import (
    ERP_BRAND,
    ERP_DISPLAY_NAME,
    ERP_LEGAL_NAME,
    ERP_LOGIN_FOOTER,
    ERP_LOGIN_TITLE,
    ERP_SYSTEM_LABEL,
    ERP_TAGLINE,
    ERP_VERSION,
)

LOGO_SVG_PATH = os.path.join(BASE_DIR, "assets", "logo", "maxek_logo.svg")
LOGO_PNG_PATH = os.path.join(BASE_DIR, "assets", "logo", "maxek_logo.png")

from modules.navigation import (
    MENU_SECTIONS,
    page_label,
    section_for_page,
)
from modules.roles import display_role_name


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


def start_delete_confirm(confirm_key, item_label, payload=None):
    st.session_state[f"del_confirm_{confirm_key}"] = True
    st.session_state[f"del_confirm_{confirm_key}_label"] = item_label
    if payload is not None:
        st.session_state[f"del_confirm_{confirm_key}_payload"] = payload
    st.rerun()


def cancel_delete_confirm(confirm_key):
    st.session_state.pop(f"del_confirm_{confirm_key}", None)
    st.session_state.pop(f"del_confirm_{confirm_key}_label", None)
    st.session_state.pop(f"del_confirm_{confirm_key}_payload", None)


def render_delete_confirm_dialog(confirm_key, on_yes, message="Do you want to delete?"):
    if not st.session_state.get(f"del_confirm_{confirm_key}"):
        return False
    label = st.session_state.get(f"del_confirm_{confirm_key}_label", "this item")
    st.warning(f"{message} **{label}**")
    c_yes, c_no = st.columns(2)
    if c_yes.button("Yes, delete", type="primary", width="stretch", key=f"del_confirm_{confirm_key}_yes"):
        payload = st.session_state.pop(f"del_confirm_{confirm_key}_payload", None)
        cancel_delete_confirm(confirm_key)
        on_yes(payload)
        return True
    if c_no.button("No, cancel", width="stretch", key=f"del_confirm_{confirm_key}_no"):
        cancel_delete_confirm(confirm_key)
        st.rerun()
    return True


def location_dropdowns(
    key_prefix="loc",
    default_country="India",
    default_region=None,
    default_district=None,
    allow_blank=False,
    show_region=True,
    show_district=True,
):
    if show_region and show_district:
        c1, c2, c3 = st.columns(3)
    elif show_region or show_district:
        c1, c2 = st.columns(2)
        c3 = None
    else:
        c1 = st.container()
        c2 = None
        c3 = None
    countries = load_countries() or ["India"]
    if allow_blank:
        countries = [""] + countries
    country_index = _select_index(countries, default_country)
    with c1:
        country = st.selectbox("Country", countries, index=country_index, key=f"{key_prefix}_country")

    region = ""
    if show_region:
        regions = load_regions(country) if country else []
        if allow_blank:
            regions = [""] + regions
        regions = regions or [""]
        region_index = _select_index(regions, default_region)
        with c2:
            region = st.selectbox("Region / State", regions, index=region_index, key=f"{key_prefix}_region")
    else:
        st.session_state.pop(f"{key_prefix}_region", None)

    district = ""
    if show_district:
        districts = load_districts(country, region) if country and region else []
        if allow_blank:
            districts = [""] + districts
        districts = districts or [""]
        district_index = _select_index(districts, default_district)
        with c3 if c3 is not None else st.container():
            district = st.selectbox("District", districts, index=district_index, key=f"{key_prefix}_district")
    else:
        st.session_state.pop(f"{key_prefix}_district", None)

    return country, region, district


def render_sidebar(user_name: str, on_logout, allowed_pages=None):
    from modules.sidebar import render_erp_sidebar

    render_erp_sidebar(user_name, allowed_pages)


def render_page_header(user_name: str, on_logout=None):
    left, middle, right = st.columns([1.15, 2.15, 1.35])
    current_page = page_label(st.session_state.get("page", "dash_mgmt"))
    section = section_for_page(st.session_state.get("page", ""))
    if section:
        section_title = next(lbl for sid, lbl, _icon, _ in MENU_SECTIONS if sid == section)
        current_page = f"{section_title} · {current_page}"
    user_role = st.session_state.get("user_role", "Admin")
    user_role_label = display_role_name(user_role)
    today = datetime.now()
    with left:
        st.markdown(
            f"""
            <div class="maxek-header-pill">
              <div class="maxek-header-page">{current_page}</div>
              <div class="maxek-header-caption">{ERP_SYSTEM_LABEL}</div>
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
        st.markdown(
            f"""
            <div class="maxek-header-user-block">
              <div class="maxek-header-user-name">{user_name}</div>
              <div class="maxek-header-user-meta">{user_role_label} · {today.strftime('%d %b %Y')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if on_logout and st.button(
            "Log out",
            key="header_logout",
            type="secondary",
            use_container_width=True,
        ):
            on_logout()


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
        ("🧾", "Monthly Expenses", f"Rs {stats.get('monthly_expense', 0):,.0f}", "Current month"),
        ("💵", "Cash Balance", f"Rs {stats.get('cash_balance', 0):,.0f}", "Finance"),
        ("🏦", "Bank Balance", f"Rs {stats.get('bank_balance', 0):,.0f}", "Finance"),
        ("📉", "Creditors", f"Rs {stats.get('creditors', 0):,.0f}", "Outstanding payables"),
        ("📈", "Debtors", f"Rs {stats.get('debtors', 0):,.0f}", "Outstanding receivables"),
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


def _render_dashboard_cash_flow(stats):
    st.markdown(
        """
        <div class="maxek-section-title">Daily Cash Flow</div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Opening Balance", "Rs 0.00")
    c2.metric("Cash In", f"Rs {stats['cash_in']:,.2f}")
    c3.metric("Cash Out", f"Rs {stats['cash_out']:,.2f}")
    c4.metric("Closing Balance", f"Rs {stats['cash_in_hand']:,.2f}")


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
                "Petty Cash & Expenses",
                [
                    ("Petty Issued", f"Rs {stats.get('petty_issued', 0):,.2f}"),
                    ("Petty Utilized", f"Rs {stats.get('petty_utilized', 0):,.2f}"),
                    ("Pending Verification", stats.get("petty_pending_verify", 0)),
                    ("Monthly Expenses", f"Rs {stats.get('monthly_expense', 0):,.2f}"),
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
    user_role_label = display_role_name(user_role)
    rendered_any = False

    section_visibility = role_visibility.get(
        user_role,
        {section_key: True for section_key in DASHBOARD_SECTION_ORDER_DEFAULT},
    )
    section_order = dashboard_settings.get("section_order", DASHBOARD_SECTION_ORDER_DEFAULT[:])

    section_renderers = {
        "welcome": lambda: _render_dashboard_welcome(user_name),
        "kpis": lambda: _render_dashboard_kpis(stats),
        "cash_flow": lambda: _render_dashboard_cash_flow(stats),
        "overviews": lambda: _render_dashboard_overviews(stats, dashboard_settings),
        "recent_payments": _render_dashboard_recent_payments,
        "notifications": _render_dashboard_notifications,
    }
    section_enabled = {
        "welcome": dashboard_settings.get("show_welcome", True),
        "kpis": dashboard_settings.get("show_kpis", True),
        "cash_flow": dashboard_settings.get("show_sidebar_cashflow", True),
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


_LOGIN_PAGE_CSS = """
body.maxek-login-page {
  background: #eef1f6 !important;
}
body.maxek-login-page .maxek-watermark {
  opacity: 0.13 !important;
  width: min(58vw, 540px) !important;
  filter: saturate(1.1);
}
body.maxek-login-page section.main {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 1.5rem 1rem 5rem !important;
}
body.maxek-login-page section.main .block-container {
  max-width: min(92vw, 480px) !important;
  width: min(92vw, 480px) !important;
  margin-left: auto !important;
  margin-right: auto !important;
  padding: 2rem 2rem 1.5rem !important;
  background: #ffffff !important;
  border-radius: 16px !important;
  border: 1px solid #e2e8f0 !important;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.12) !important;
}
body.maxek-login-page .maxek-login-logo {
  display: block;
  width: 120px;
  height: auto;
  margin: 0 auto 1rem;
  object-fit: contain;
}
body.maxek-login-page .maxek-login-title {
  text-align: center;
  color: #0f172a;
  font-size: 1.55rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
  letter-spacing: -0.02em;
}
body.maxek-login-page .maxek-login-subtitle {
  text-align: center;
  color: #64748b;
  font-size: 0.9rem;
  margin-bottom: 1.35rem;
}
body.maxek-login-page [data-testid="stTextInput"],
body.maxek-login-page [data-testid="stTextInput"] > div,
body.maxek-login-page [data-testid="stTextInput"] > div > div {
  width: 100% !important;
  max-width: 100% !important;
}
body.maxek-login-page [data-testid="stTextInput"] label {
  font-size: 0.85rem !important;
  font-weight: 600 !important;
  color: #334155 !important;
}
body.maxek-login-page [data-testid="stTextInput"] input {
  width: 100% !important;
  max-width: 100% !important;
  min-width: 0 !important;
  height: 44px !important;
  font-size: 0.95rem !important;
  box-sizing: border-box !important;
  border-radius: 10px !important;
}
body.maxek-login-page [data-testid="stCheckbox"] label {
  font-size: 0.85rem !important;
  color: #475569 !important;
}
body.maxek-login-page div.stButton {
  width: 100% !important;
  margin-top: 0.35rem !important;
}
body.maxek-login-page div.stButton button {
  width: 100% !important;
  height: 45px !important;
  min-height: 45px !important;
  font-size: 0.95rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.06em !important;
  border-radius: 10px !important;
  background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
  color: #fff !important;
  border: none !important;
}
body.maxek-login-page div.stButton button:hover {
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.35) !important;
}
body.maxek-login-page .maxek-login-forgot {
  text-align: center;
  margin-top: 0.85rem;
  font-size: 0.82rem;
  color: #64748b;
}
body.maxek-login-page .maxek-login-forgot a {
  color: #2563eb;
  text-decoration: none;
  font-weight: 600;
}
body.maxek-login-page .maxek-login-page-footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  text-align: center;
  padding: 1rem 1rem 1.25rem;
  background: linear-gradient(180deg, transparent, rgba(238, 241, 246, 0.92) 35%);
  pointer-events: none;
  z-index: 2;
}
body.maxek-login-page .maxek-login-page-footer strong {
  display: block;
  color: #0f172a;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.03em;
}
body.maxek-login-page .maxek-login-page-footer span {
  display: block;
  color: #64748b;
  font-size: 0.76rem;
  margin-top: 0.2rem;
}
body.maxek-login-page .maxek-login-page-footer em {
  display: block;
  color: #94a3b8;
  font-size: 0.72rem;
  font-style: normal;
  margin-top: 0.35rem;
}
body.maxek-login-page input:-webkit-autofill {
  -webkit-box-shadow: 0 0 0 1000px #ffffff inset !important;
  box-shadow: 0 0 0 1000px #ffffff inset !important;
}
.maxek-login-decoy {
  position: absolute;
  left: -9999px;
  width: 0;
  height: 0;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
}
@media (max-width: 520px) {
  body.maxek-login-page section.main .block-container {
    padding: 1.5rem 1.25rem 1.25rem !important;
  }
}
"""


def show_login_page():
    inject_global_css()
    add_watermark()
    st.markdown(f"<style>{_LOGIN_PAGE_CSS}</style>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="maxek-login-marker"></div>
        <div class="maxek-login-decoy" aria-hidden="true">
            <input type="text" name="fake_username" tabindex="-1" autocomplete="username" />
            <input type="password" name="fake_password" tabindex="-1" autocomplete="current-password" />
        </div>
        <script>
        function maxekApplyLoginPage() {
            document.body.classList.toggle('maxek-login-page', !!document.querySelector('.maxek-login-marker'));
        }
        maxekApplyLoginPage();
        setTimeout(maxekApplyLoginPage, 80);
        </script>
        """,
        unsafe_allow_html=True,
    )

    uri = _logo_data_uri()
    if uri:
        st.markdown(
            f'<img src="{uri}" class="maxek-login-logo" alt="{ERP_BRAND}" />',
            unsafe_allow_html=True,
        )
    st.markdown(
        f"""
        <div class="maxek-login-title">{ERP_LOGIN_TITLE}</div>
        <div class="maxek-login-subtitle">{ERP_TAGLINE}</div>
        """,
        unsafe_allow_html=True,
    )

    remembered = st.session_state.get("login_remember_user", False)
    saved_user = st.session_state.get("login_saved_username", "")
    if remembered and saved_user and "login_user" not in st.session_state:
        st.session_state.login_user = saved_user
    username = st.text_input(
        "Username",
        key="login_user",
        placeholder="Enter username",
    )
    password = st.text_input("Password", type="password", key="login_pass", placeholder="Enter password")
    remember = st.checkbox("Remember me", value=remembered, key="login_remember")
    login_clicked = st.button("LOGIN", type="primary", key="login_btn")

    st.markdown(
        '<div class="maxek-login-forgot">Forgot password? Contact your system administrator.</div>',
        unsafe_allow_html=True,
    )

    if login_clicked:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT full_name, role FROM users WHERE username=? AND password=?",
            (username.strip(), password),
        )
        row = cur.fetchone()
        conn.close()
        if row:
            st.session_state.logged_in = True
            st.session_state.user_name = row[0]
            st.session_state.user_role = row[1] or "Admin"
            st.session_state.page = "dash_mgmt"
            st.session_state.login_remember_user = remember
            st.session_state.login_saved_username = username.strip() if remember else ""
            st.rerun()
        st.error("Invalid username or password.")

    st.markdown(
        f"""
        <div class="maxek-login-page-footer">
          <strong>{ERP_LEGAL_NAME}</strong>
          <span>{ERP_LOGIN_FOOTER}</span>
          <em>Version {ERP_VERSION}</em>
        </div>
        """,
        unsafe_allow_html=True,
    )


def wrap_page(content_fn):
    content_fn()
