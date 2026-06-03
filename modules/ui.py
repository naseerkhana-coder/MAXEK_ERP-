"""Global UI: CSS, shell, branding, login, and dashboard."""

import base64
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from modules.database import (
    DASHBOARD_SECTION_ORDER_DEFAULT,
    dashboard_monthly_revenue_series,
    dashboard_notifications,
    dashboard_project_progress_series,
    dashboard_recent_transactions,
    get_dashboard_settings,
    get_conn,
    get_dashboard_role_visibility,
    kpi_stats,
    load_countries,
    load_districts,
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
    ERP_TAGLINE,
    ERP_VERSION,
)

LOGO_SVG_PATH = os.path.join(BASE_DIR, "assets", "logo", "maxek_logo.svg")
LOGO_PNG_PATH = os.path.join(BASE_DIR, "assets", "logo", "maxek_logo.png")

from modules.navigation import (
    MENU_DASHBOARD,
    TOP_NAV_ITEMS,
    default_page_for_section,
    top_nav_section_active,
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


def _navigate_to(page_key: str) -> None:
    from modules.navigation import section_for_page as _section_for_page

    section = _section_for_page(page_key)
    if section:
        st.session_state.sidebar_open_section = section
    st.session_state.page = page_key
    st.rerun()


def render_page_breadcrumbs(*crumbs: str, title: str = "", subtitle: str = ""):
    """Render breadcrumb trail and page title block (mockup main-area header)."""
    trail = " › ".join(crumbs) if crumbs else ""
    subtitle_html = f'<p class="maxek-page-subtitle">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f"""
        <div class="maxek-page-head">
          <div class="maxek-breadcrumbs">{trail}</div>
          <h1 class="maxek-page-title">{title}</h1>
          {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(user_name: str, on_logout=None, allowed_pages=None):
    allowed = set(allowed_pages or {MENU_DASHBOARD[0]})
    page_key = st.session_state.get("page", MENU_DASHBOARD[0])
    user_role = st.session_state.get("user_role", "Admin")
    user_role_label = display_role_name(user_role)
    today = datetime.now()
    logo_uri = _logo_data_uri()
    notif_count = len(dashboard_notifications())

    st.markdown('<div class="maxek-top-bar">', unsafe_allow_html=True)

    brand_col, search_col, date_col, bell_col, profile_col = st.columns([0.75, 2.2, 1.1, 0.45, 1.3])

    with brand_col:
        if logo_uri:
            st.markdown(
                f'<img src="{logo_uri}" class="maxek-header-logo" alt="{ERP_BRAND}" />',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f'<div class="maxek-header-logo-text">{ERP_BRAND}</div>', unsafe_allow_html=True)

    with search_col:
        st.text_input(
            "Global search",
            key="header_global_search",
            label_visibility="collapsed",
            placeholder="Search anything…",
        )

    with date_col:
        st.markdown(
            f"""
            <div class="maxek-header-date-chip">
              <div>{today.strftime('%d %b %Y')}</div>
              <span>{today.strftime('%a')}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with bell_col:
        bell_label = f"🔔 {notif_count}" if notif_count else "🔔"
        if st.button(bell_label, key="header_notifications", help="Notifications"):
            if "dash_notifications" in allowed:
                _navigate_to("dash_notifications")

    with profile_col:
        st.markdown(
            f"""
            <div class="maxek-header-user-v2">
              <span class="maxek-header-avatar">{user_name[:1].upper()}</span>
              <div class="maxek-header-user-text">
                <div class="maxek-header-user-name">{user_name}</div>
                <div class="maxek-header-user-meta">{user_role_label}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if on_logout and st.button("Log out", key="header_logout", help="Log out"):
            on_logout()

    st.markdown('<div class="maxek-top-nav-row">', unsafe_allow_html=True)
    visible_nav = []
    for section_id, label, icon in TOP_NAV_ITEMS:
        target = default_page_for_section(section_id)
        if section_id == "dashboard" or target in allowed:
            visible_nav.append((section_id, label, icon, target))
    nav_slots = st.columns(max(len(visible_nav), 1))
    for slot, (section_id, label, icon, target) in zip(nav_slots, visible_nav):
        active = top_nav_section_active(section_id, page_key)
        with slot:
            if st.button(
                f"{icon} {label}",
                key=f"top_nav_{section_id}",
                width="stretch",
                type="primary" if active else "secondary",
            ):
                _navigate_to(target)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


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
    render_page_breadcrumbs(
        "Home",
        "Dashboard",
        title=f"Welcome back, {user_name}",
        subtitle="Projects · Procurement · Inventory · Subcontractor billing · Petty cash · Letters",
    )


def _render_dashboard_kpis(stats):
    cards = [
        ("📁", "Total Projects", stats.get("total_projects", stats["active_projects"]), "All sites", "accent-blue"),
        ("🏗️", "Active Projects", stats["active_projects"], "On site now", "accent-green"),
        ("🧾", "Pending Bills", stats.get("pending_bills", 0), "Awaiting payment", "accent-red"),
        ("🛒", "Pending PO", stats.get("pending_po", 0), "Purchase orders", "accent-orange"),
        ("💵", "Cash Balance", f"Rs {stats.get('cash_balance', 0):,.0f}", "Petty + cash book", "accent-purple"),
        ("📋", "Material Requests", stats.get("material_requests_open", 0), "Open MRs", "accent-yellow"),
    ]
    html_parts = ['<div class="maxek-kpi-grid">']
    for icon, label, value, helper, accent in cards:
        html_parts.append(
            f'<div class="maxek-kpi-card {accent}">'
            f'<div class="maxek-kpi-icon">{icon}</div>'
            f'<div class="maxek-kpi-label">{label}</div>'
            f'<div class="maxek-kpi-value">{value}</div>'
            f'<div class="maxek-kpi-helper">{helper}</div>'
            f"</div>"
        )
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def _render_dashboard_charts(stats):
    st.markdown('<div class="maxek-section-title">Operations snapshot</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    progress_df = dashboard_project_progress_series()
    with c1:
        st.markdown("**Project Progress**")
        if progress_df.empty:
            st.caption("Add projects to see progress.")
        else:
            chart_df = progress_df.set_index("project")[["progress"]]
            st.bar_chart(chart_df, height=220)
    with c2:
        st.markdown("**Cash Flow**")
        flow = {
            "Cash In": float(stats.get("cash_in", 0) or 0),
            "Cash Out": float(stats.get("cash_out", 0) or 0),
            "Balance": float(stats.get("cash_in_hand", 0) or 0),
        }
        st.bar_chart(pd.DataFrame(flow, index=["Today"]).T, height=220)
    with c3:
        st.markdown("**Monthly Revenue**")
        revenue_df = dashboard_monthly_revenue_series()
        if revenue_df.empty:
            st.caption("Record client receipts to build revenue trend.")
        else:
            st.line_chart(revenue_df.set_index("month")[["revenue"]], height=220)


def _render_dashboard_cash_flow(stats):
    _render_dashboard_charts(stats)


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


def _render_dashboard_pending_approvals():
    from modules.finance_workflow import render_approval_inbox

    st.subheader("Pending Approvals")
    render_approval_inbox("Pending", ["Submitted", "Verified", "PM Approved"])


def _render_dashboard_recent_activities():
    st.subheader("Recent Activities")
    payments_df = dashboard_recent_transactions(limit=8)
    if payments_df.empty:
        st.info("No recent transactions yet.")
    else:
        st.dataframe(payments_df, width="stretch", hide_index=True)


def _render_dashboard_site_updates():
    st.subheader("Site Updates")
    progress_df = dashboard_project_progress_series(limit=5)
    if progress_df.empty:
        st.caption("Daily reports and site photos will appear here.")
        return
    for _, row in progress_df.iterrows():
        st.markdown(
            f"""
            <div class="maxek-note-item">
              <strong>{row['project']}</strong>
              <span>Progress {float(row.get('progress', 0) or 0):.0f}% · check DPR for latest site update</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


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
        "pending_approvals": _render_dashboard_pending_approvals,
        "recent_activities": _render_dashboard_recent_activities,
        "site_updates": _render_dashboard_site_updates,
        "notifications": _render_dashboard_notifications,
    }
    section_enabled = {
        "welcome": dashboard_settings.get("show_welcome", True),
        "kpis": dashboard_settings.get("show_kpis", True),
        "cash_flow": dashboard_settings.get("show_sidebar_cashflow", True),
        "overviews": dashboard_settings.get("show_attendance_overview", False),
        "pending_approvals": dashboard_settings.get("show_recent_payments", True),
        "recent_activities": dashboard_settings.get("show_recent_payments", True),
        "site_updates": dashboard_settings.get("show_project_overview", True),
        "notifications": dashboard_settings.get("show_notifications", True),
    }

    for section_key in section_order:
        if section_key in ("pending_approvals", "recent_activities", "site_updates"):
            continue
        if not section_enabled.get(section_key, False):
            continue
        if not section_visibility.get(section_key, True):
            continue
        result = section_renderers[section_key]()
        if result is not False:
            rendered_any = True

    st.markdown('<div class="maxek-section-title">Action centre</div>', unsafe_allow_html=True)
    b1, b2 = st.columns(2)
    with b1:
        if section_enabled.get("pending_approvals", True):
            _render_dashboard_pending_approvals()
        if section_enabled.get("site_updates", True):
            _render_dashboard_site_updates()
    with b2:
        if section_enabled.get("recent_activities", True):
            _render_dashboard_recent_activities()
        if section_enabled.get("notifications", True):
            _render_dashboard_notifications()
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
