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
              <span>{today.strftime('%a · %H:%M')}</span>
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
        menu_label = f"{user_name} ▾"
        with st.popover(menu_label, use_container_width=True):
            st.caption(user_role_label)
            if st.button("My Profile", key="header_my_profile", use_container_width=True):
                st.session_state.pop("account_focus", None)
                _navigate_to("account_profile")
            if st.button("Change Password", key="header_change_password", use_container_width=True):
                st.session_state.account_focus = "password"
                _navigate_to("account_profile")
            if on_logout and st.button("Logout", key="header_logout", use_container_width=True):
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
    today = datetime.now()
    st.markdown(
        f"""
        <div class="maxek-breadcrumbs">Home › Dashboard</div>
        <div class="maxek-dashboard-intro">
          <div>
            <h1>Welcome back, {user_name}</h1>
            <p>Projects · Procurement · HR &amp; Payroll · Finance · Store · Correspondence</p>
          </div>
          <div class="maxek-dashboard-date">
            <div>{today.strftime('%d %b %Y')}</div>
            <span>{today.strftime('%A')}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_dashboard_kpis(stats):
    cards = [
        ("📁", "Total Projects", stats.get("total_projects", stats["active_projects"]), "All sites", "accent-blue"),
        ("🏗️", "Active Projects", stats["active_projects"], "On site now", "accent-green"),
        ("👷", "Active Workers", stats.get("active_workers", 0), "Site workforce", "accent-green"),
        ("🏢", "Staff", stats.get("staff_count", 0), "Office & payroll staff", "accent-slate"),
        ("🧾", "Pending Bills", stats.get("pending_bills", 0), "Awaiting payment", "accent-red"),
        ("🛒", "Pending PO", stats.get("pending_po", 0), "Purchase orders", "accent-orange"),
        ("💵", "Cash Balance", f"Rs {stats.get('cash_balance', 0):,.0f}", "Petty + cash book", "accent-purple"),
        ("🏦", "Bank Balance", f"Rs {stats.get('bank_balance', 0):,.0f}", "Settled bank position", "accent-blue"),
        ("📋", "Open MRs", stats.get("material_requests_open", 0), "Material requests", "accent-yellow"),
        ("💰", "Payroll Runs", stats.get("worker_payroll_open", 0), "Worker payroll in progress", "accent-orange"),
        (
            "✅",
            "Workflow Queue",
            stats.get("workflow_pending", 0),
            "Prepared / checked / approved",
            "accent-yellow",
        ),
    ]
    html_parts = ['<div class="maxek-kpi-grid maxek-kpi-grid-wide">']
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
                "HR & Payroll (Today)",
                [
                    ("Present Today", stats.get("attendance_present", stats["attendance_today"])),
                    ("Attendance %", f"{stats.get('attendance_pct', 0):g}%"),
                    ("Active Workers", stats["active_workers"]),
                    ("Staff (Office)", stats.get("staff_count", 0)),
                    ("Pending Worker Salary", stats["pending_salary"]),
                    ("Open Payroll Runs", stats.get("worker_payroll_open", 0)),
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
                "Finance & Expenses",
                [
                    ("Cash Balance", f"Rs {stats.get('cash_balance', 0):,.2f}"),
                    ("Bank Balance", f"Rs {stats.get('bank_balance', 0):,.2f}"),
                    ("Debtors", f"Rs {stats.get('debtors', 0):,.2f}"),
                    ("Creditors", f"Rs {stats.get('creditors', 0):,.2f}"),
                    ("Petty Pending Verify", stats.get("petty_pending_verify", 0)),
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
    from modules.approval_workflow import get_pending_for_role
    from modules.database import kpi_workflow_pending_for_role
    from modules.finance_workflow import render_approval_inbox

    st.subheader("Pending Approvals")
    role = st.session_state.get("user_role", "Admin")
    user = st.session_state.get("user_name", "User")
    my_count = kpi_workflow_pending_for_role(role)
    if my_count:
        st.caption(f"**{my_count}** item(s) need action for your role ({role}).")
    pending = get_pending_for_role(user, role)
    if pending:
        st.dataframe(
            pd.DataFrame(pending)[["entity_type", "count", "statuses"]],
            width="stretch",
            hide_index=True,
        )
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
    show_overviews = any(
        dashboard_settings.get(flag, True)
        for flag in (
            "show_attendance_overview",
            "show_project_overview",
            "show_expense_overview",
        )
    )
    section_enabled = {
        "welcome": dashboard_settings.get("show_welcome", True),
        "kpis": dashboard_settings.get("show_kpis", True),
        "cash_flow": dashboard_settings.get("show_sidebar_cashflow", True),
        "overviews": show_overviews,
        "pending_approvals": dashboard_settings.get("show_recent_payments", True),
        "recent_activities": dashboard_settings.get("show_recent_payments", True),
        "site_updates": dashboard_settings.get("show_project_overview", True),
        "notifications": dashboard_settings.get("show_notifications", True),
    }

    for section_key in section_order:
        if section_key in ("pending_approvals", "recent_activities", "site_updates"):
            continue
        if not section_enabled.get(section_key, True):
            continue
        if not section_visibility.get(section_key, True):
            continue
        result = section_renderers[section_key]()
        if result is not False:
            rendered_any = True

    action_blocks = [
        ("pending_approvals", _render_dashboard_pending_approvals),
        ("site_updates", _render_dashboard_site_updates),
        ("recent_activities", _render_dashboard_recent_activities),
        ("notifications", _render_dashboard_notifications),
    ]
    if any(section_enabled.get(key, True) for key, _ in action_blocks):
        st.markdown('<div class="maxek-section-title">Action centre</div>', unsafe_allow_html=True)
        b1, b2 = st.columns(2)
        with b1:
            if section_enabled.get("pending_approvals", True):
                _render_dashboard_pending_approvals()
                rendered_any = True
            if section_enabled.get("site_updates", True) and section_visibility.get("site_updates", True):
                _render_dashboard_site_updates()
                rendered_any = True
        with b2:
            if section_enabled.get("recent_activities", True):
                _render_dashboard_recent_activities()
                rendered_any = True
            if section_enabled.get("notifications", True) and section_visibility.get("notifications", True):
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


def _login_reset_token_from_query() -> str:
    try:
        raw = st.query_params.get("reset_token")
        if isinstance(raw, list):
            raw = raw[0] if raw else ""
        return (raw or "").strip()
    except Exception:
        return ""


def _render_login_reset_password_form(token: str) -> None:
    from modules.user_account import lookup_token_username, reset_password_with_token, validate_new_password

    hint_user = lookup_token_username(token)
    st.markdown("### Set a new password")
    if hint_user:
        st.caption(f"Resetting password for **{hint_user}**")
    else:
        st.warning("This reset link is invalid or has expired. Use **Forgot password?** on the login page to request a new link.")

    new_pwd = st.text_input("New password", type="password", key="reset_new_password")
    confirm = st.text_input("Confirm new password", type="password", key="reset_confirm_password")
    if st.button("Save new password", type="primary", key="reset_save_password"):
        err = validate_new_password(new_pwd, confirm)
        if err:
            st.error(err)
        else:
            ok, msg = reset_password_with_token(token, new_pwd)
            if ok:
                try:
                    del st.query_params["reset_token"]
                except Exception:
                    pass
                st.success(msg)
            else:
                st.error(msg)
    if st.button("Back to login", key="reset_back_login"):
        try:
            del st.query_params["reset_token"]
        except Exception:
            pass
        st.rerun()


def _handle_forgot_password_request(email: str) -> None:
    import secrets
    import string

    from modules.notifications import (
        _ensure_users_email_column,
        send_password_reset_email,
        send_password_reset_link_email,
        smtp_config,
    )
    from modules.password_security import hash_password
    from modules.user_account import (
        app_base_url,
        create_password_reset_token_by_email,
        password_reset_token_hours,
    )

    email_reset = (email or "").strip()
    if not email_reset or "@" not in email_reset:
        st.warning("Enter the email address registered to your account.")
        return

    base = app_base_url()
    cfg = smtp_config()
    if base and cfg.get("configured"):
        token, _uid, err = create_password_reset_token_by_email(email_reset)
        if err:
            st.error(err)
            return
        if not token:
            st.error("Could not create a reset link. Contact your administrator.")
            return
        reset_url = f"{base}/?reset_token={token}"
        if send_password_reset_link_email(
            email_reset,
            email_reset.split("@")[0],
            reset_url,
            password_reset_token_hours(),
        ):
            st.success(f"Password reset link sent to {email_reset}. Check your inbox.")
        else:
            st.error("Email could not be sent. Contact your administrator.")
        return

    conn = get_conn()
    cur = conn.cursor()
    _ensure_users_email_column(conn)
    cur.execute(
        "SELECT user_id, username, COALESCE(email, '') FROM users WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))",
        (email_reset,),
    )
    row_reset = cur.fetchone()
    if not row_reset:
        conn.close()
        st.error("No account found for this email address.")
        return
    reset_user_id, uname_reset, email_addr = row_reset[0], row_reset[1], (row_reset[2] or "").strip()
    if not email_addr or "@" not in email_addr:
        conn.close()
        st.error(
            "No email on file for this user. Ask your administrator to set your email under Settings → Users."
        )
        return
    if not cfg.get("configured"):
        conn.close()
        st.info(
            "SMTP is not configured on this server. Contact your system administrator to reset your password."
        )
        return
    if not base:
        st.caption(
            "Tip: set APP_BASE_URL on the server to receive a secure reset link instead of a temporary password."
        )
    alphabet = string.ascii_letters + string.digits
    temp_password = "".join(secrets.choice(alphabet) for _ in range(12))
    cur.execute(
        "UPDATE users SET password=?, must_change_password=1 WHERE user_id=?",
        (hash_password(temp_password), reset_user_id),
    )
    conn.commit()
    conn.close()
    if send_password_reset_email(email_addr, uname_reset, temp_password):
        st.success(f"Temporary password sent to {email_addr}. Log in and change it under My Account → Change Password.")
    else:
        st.error("Email could not be sent. Contact your administrator.")


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

    reset_token = _login_reset_token_from_query()
    if reset_token:
        _render_login_reset_password_form(reset_token)
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
        return

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

    st.divider()
    if st.button("Client Portal sign-in", key="login_go_portal", use_container_width=True):
        st.session_state.login_portal_mode = True
        st.rerun()

    with st.expander("Forgot password?", expanded=False):
        st.caption(
            "Enter your registered email. When SMTP and APP_BASE_URL are configured, you receive a reset link. "
            "Otherwise a temporary password may be emailed."
        )
        reset_email = st.text_input("Email address", key="login_reset_email", placeholder="you@company.com")
        if st.button("Send reset link", key="login_reset_btn"):
            _handle_forgot_password_request(reset_email)

    if login_clicked:
        import time

        from modules.database import log_login_attempt
        from modules.password_security import hash_password, password_needs_rehash, verify_password

        uname = username.strip()
        from modules.user_account import login_allowed_for_username, record_successful_login, user_must_change_password

        allowed, block_msg = login_allowed_for_username(uname)
        if not allowed:
            log_login_attempt(uname, False)
            st.error(block_msg)
            return

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id, full_name, role, password, COALESCE(must_change_password, 0)
            FROM users WHERE LOWER(username)=LOWER(?)
            """,
            (uname,),
        )
        row = cur.fetchone()
        if row and verify_password(password, row[3] or ""):
            if password_needs_rehash(row[3] or ""):
                cur.execute(
                    "UPDATE users SET password=? WHERE user_id=?",
                    (hash_password(password), row[0]),
                )
                conn.commit()
            conn.close()
            log_login_attempt(uname, True)
            record_successful_login(row[0])
            st.session_state.logged_in = True
            st.session_state.user_id = row[0]
            st.session_state.username = uname
            st.session_state.user_name = row[1]
            st.session_state.user_role = row[2] or "Admin"
            if user_must_change_password(row[0]) or row[4]:
                st.session_state.page = "account_profile"
                st.session_state.account_focus = "password"
            else:
                st.session_state.page = "dash_mgmt"
            st.session_state.last_activity = time.time()
            st.session_state.login_remember_user = remember
            st.session_state.login_saved_username = uname if remember else ""
            st.rerun()
        conn.close()
        log_login_attempt(uname, False)
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
