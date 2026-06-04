"""Project Profitability Dashboard — management P&L by project."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from modules.database import load_project_names
from modules.pdf_templates import PdfDocument, format_inr
from modules.project_profitability_db import (
    HEAD_LABOUR,
    HEAD_MACHINERY,
    HEAD_MATERIAL,
    HEAD_OVERHEAD,
    LABOUR_SUBHEADS,
    MACHINERY_SUBHEADS,
    MATERIAL_SUBHEADS,
    OVERHEAD_SUBHEADS,
    aggregate_project_costs,
    build_project_profitability_row,
    can_access_profitability,
    can_view_owner_profitability,
    labour_cost_detail,
    load_budget_vs_actual_profitability,
    load_profitability_summary,
    load_projects_base,
    material_cost_detail,
    owner_dashboard_metrics,
    pm_assigned_project_names,
    profit_traffic_light,
)
from modules.roles import is_project_manager, is_super_admin

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFIT_CSS_PATH = os.path.join(BASE_DIR, "styles", "profitability.css")

SUBHEAD_LABELS = {
    "worker_salary": "Worker Salary",
    "staff_salary": "Staff Salary",
    "ot_amount": "OT Amount",
    "cement": "Cement",
    "steel": "Steel",
    "sand": "Sand",
    "aggregate": "Aggregate",
    "blocks": "Blocks",
    "electrical": "Electrical",
    "plumbing": "Plumbing",
    "other_materials": "Other Materials",
    "excavator": "Excavator",
    "jcb": "JCB",
    "crane": "Crane",
    "generator": "Generator",
    "equipment_rental": "Equipment Rental",
    "fuel": "Fuel",
    "maintenance": "Maintenance",
    "office_salary": "Office Salary",
    "office_rent": "Office Rent",
    "electricity": "Electricity",
    "internet": "Internet",
    "mobile_bills": "Mobile Bills",
    "software": "Software",
    "administration": "Administration",
}


def _inject_profitability_css() -> None:
    if os.path.isfile(PROFIT_CSS_PATH):
        with open(PROFIT_CSS_PATH, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def _fmt_rs(value) -> str:
    return f"Rs {float(value or 0):,.2f}"


def _fmt_pct(value) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):,.1f}%"


def _badge_html(status_key: str, label: str) -> str:
    cls = {
        "green": "profit-badge-green",
        "yellow": "profit-badge-yellow",
        "red": "profit-badge-red",
        "critical": "profit-badge-critical",
    }.get(status_key, "profit-badge-red")
    return f'<span class="maxek-profit-badge {cls}">{label}</span>'


def _profit_card(label: str, value: str, sub: str = "", css_class: str = "") -> str:
    extra = f" {css_class}" if css_class else ""
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return (
        f'<div class="maxek-profit-card{extra}">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f"{sub_html}</div>"
    )


def _head_tiles(buckets: dict, head: str, subkeys: tuple[str, ...]) -> str:
    parts = []
    for key in subkeys:
        amt = buckets.get(head, {}).get(key, 0)
        lbl = SUBHEAD_LABELS.get(key, key.replace("_", " ").title())
        parts.append(
            f'<div class="maxek-profit-head-tile"><span>{lbl}</span>'
            f"<strong>{_fmt_rs(amt)}</strong></div>"
        )
    return '<div class="maxek-profit-head-grid">' + "".join(parts) + "</div>"


def _resolve_allowed_projects(role: str, user_name: str, username: str) -> set[str] | None:
    if is_super_admin(role) or not is_project_manager(role):
        return None
    return pm_assigned_project_names(user_name, username)


def _filter_controls(allowed: set[str] | None) -> tuple[str | None, str | None, str | None, str | None]:
    projects_df = load_projects_base(allowed_names=allowed)
    project_options = ["All Projects"] + (
        projects_df["project_name"].tolist() if not projects_df.empty else load_project_names()
    )
    clients = ["All Clients"]
    if not projects_df.empty and "client_name" in projects_df.columns:
        clients += sorted({c for c in projects_df["client_name"].dropna().astype(str) if c.strip()})
    c1, c2, c3, c4 = st.columns(4)
    proj_pick = c1.selectbox("Project", project_options, key="profit_filter_project")
    client_pick = c2.selectbox("Client", clients, key="profit_filter_client")
    default_end = date.today()
    default_start = default_end - timedelta(days=365)
    d_from = c3.date_input("From", value=default_start, key="profit_filter_from")
    d_to = c4.date_input("To", value=default_end, key="profit_filter_to")
    project = None if proj_pick == "All Projects" else proj_pick
    client = None if client_pick == "All Clients" else client_pick
    date_from = d_from.strftime("%Y-%m-%d") if d_from else None
    date_to = d_to.strftime("%Y-%m-%d") if d_to else None
    return project, client, date_from, date_to


def _render_project_dashboard(row: dict) -> None:
    buckets = row.get("buckets") or {}
    cards = (
        _profit_card("Project Value", _fmt_rs(row["project_value"]), "Contract + approved variations")
        + _profit_card("Total Cost", _fmt_rs(row["total_cost"]))
        + _profit_card(
            "Net P/L",
            _fmt_rs(row["net_profit"]),
            _fmt_pct(row["profit_pct"]),
            row.get("traffic_class", ""),
        )
    )
    st.markdown(
        f'<div class="maxek-profit-shell">'
        f'<div style="margin-bottom:0.5rem">{_badge_html(row["traffic_status"], row["traffic_label"])}</div>'
        f'<div class="maxek-profit-kpi-grid">{cards}</div></div>',
        unsafe_allow_html=True,
    )
    from modules.phase3_integration import render_project_integration_panel

    render_project_integration_panel(
        str(row.get("project_name") or ""),
        profitability_row=row,
    )
    st.markdown("#### Cost heads")
    h1, h2, h3, h4 = st.columns(4)
    with h1:
        st.markdown(f"**Labour** — {_fmt_rs(row['labour_total'])}")
        st.markdown(_head_tiles(buckets, HEAD_LABOUR, LABOUR_SUBHEADS), unsafe_allow_html=True)
    with h2:
        st.markdown(f"**Material** — {_fmt_rs(row['material_total'])}")
        st.markdown(_head_tiles(buckets, HEAD_MATERIAL, MATERIAL_SUBHEADS), unsafe_allow_html=True)
    with h3:
        st.markdown(f"**Machinery** — {_fmt_rs(row['machinery_total'])}")
        st.markdown(_head_tiles(buckets, HEAD_MACHINERY, MACHINERY_SUBHEADS), unsafe_allow_html=True)
    with h4:
        st.markdown(f"**Overhead** — {_fmt_rs(row['overhead_total'])}")
        st.markdown(_head_tiles(buckets, HEAD_OVERHEAD, OVERHEAD_SUBHEADS), unsafe_allow_html=True)


def _render_owner_dashboard(summary: pd.DataFrame) -> None:
    metrics = owner_dashboard_metrics(summary)
    cards = (
        _profit_card("Total Company Revenue", _fmt_rs(metrics["total_revenue"]))
        + _profit_card("Total Cost", _fmt_rs(metrics["total_cost"]))
        + _profit_card("Total Profit", _fmt_rs(metrics["total_profit"]))
    )
    st.markdown(f'<div class="maxek-profit-kpi-grid">{cards}</div>', unsafe_allow_html=True)
    if summary.empty:
        st.info("No project data for the selected filters.")
        return
    table = summary[
        [
            "project_name",
            "client_name",
            "project_value",
            "total_cost",
            "net_profit",
            "profit_pct",
            "traffic_label",
        ]
    ].copy()
    table["profit_pct"] = table["profit_pct"].apply(_fmt_pct)
    st.markdown("#### Project-wise profitability")
    st.dataframe(table, use_container_width=True, hide_index=True)
    if len(summary) > 1:
        chart_df = summary.set_index("project_name")[["net_profit"]]
        st.bar_chart(chart_df, height=280)
    top5 = summary.nlargest(5, "net_profit")[["project_name", "net_profit", "profit_pct"]]
    st.markdown("#### Top 5 profitable projects")
    st.dataframe(top5, use_container_width=True, hide_index=True)
    loss_df = summary[summary["net_profit"] < 0][
        ["project_name", "client_name", "project_value", "total_cost", "net_profit"]
    ]
    st.markdown("#### Loss-making projects")
    if loss_df.empty:
        st.success("No loss-making projects in this period.")
    else:
        st.dataframe(loss_df, use_container_width=True, hide_index=True)


def _csv_download(df: pd.DataFrame, filename: str, key: str) -> None:
    if df is None or df.empty:
        st.caption("No rows to export.")
        return
    st.download_button(
        "Download CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=key,
    )


def _pdf_profitability_report(row: dict, date_from: str | None, date_to: str | None) -> bytes:
    doc = PdfDocument()
    period = f"{date_from or '—'} to {date_to or '—'}"
    doc.add_company_block(
        "Project Profitability Report",
        ref_label="Project",
        ref_value=row.get("project_name", ""),
        date_value=datetime.now().strftime("%d/%m/%Y"),
    )
    doc.add_key_value_table(
        [
            ("Client", str(row.get("client_name") or "—")),
            ("Period", period),
            ("Contract value", format_inr(row.get("contract_value"))),
            ("Approved variations", format_inr(row.get("variation_value"))),
            ("Total project value", format_inr(row.get("project_value"))),
            ("Total cost", format_inr(row.get("total_cost"))),
            ("Net profit / (loss)", format_inr(row.get("net_profit"))),
            ("Profit %", _fmt_pct(row.get("profit_pct"))),
            ("Status", str(row.get("traffic_label") or "")),
        ]
    )
    doc.add_section("Cost head totals")
    doc.add_data_table(
        ["Head", "Amount (Rs)"],
        [
            ["Labour", format_inr(row.get("labour_total"))],
            ["Material", format_inr(row.get("material_total"))],
            ["Machinery", format_inr(row.get("machinery_total"))],
            ["Overhead", format_inr(row.get("overhead_total"))],
        ],
        col_widths=[8, 8],
    )
    doc.add_footer("Project profitability — system generated.")
    return doc.build()


def _render_reports_tab(
    project: str | None,
    date_from: str | None,
    date_to: str | None,
    allowed: set[str] | None,
) -> None:
    if not project:
        st.info("Select a single project in filters to run detailed cost reports.")
        return
    prow = load_projects_base(project_name=project, allowed_names=allowed)
    if prow.empty:
        st.warning("Project not found or not in your scope.")
        return
    row = build_project_profitability_row(prow.iloc[0], date_from=date_from, date_to=date_to)
    report = st.selectbox(
        "Report",
        [
            "Project Profitability Report",
            "Labour Cost Report",
            "Material Cost Report",
            "Machinery Cost Report",
            "Overhead Cost Report",
            "Budget vs Actual Report",
        ],
        key="profit_report_pick",
    )
    if report == "Project Profitability Report":
        df = pd.DataFrame([{k: v for k, v in row.items() if k != "buckets"}])
        _csv_download(df, f"profitability_{project}.csv", "profit_csv_main")
        pdf = _pdf_profitability_report(row, date_from, date_to)
        st.download_button(
            "Download PDF",
            data=pdf,
            file_name=f"profitability_{project}.pdf",
            mime="application/pdf",
            key="profit_pdf_main",
        )
    elif report == "Labour Cost Report":
        df = labour_cost_detail(project, date_from, date_to)
        _csv_download(df, f"labour_{project}.csv", "profit_csv_labour")
    elif report == "Material Cost Report":
        df = material_cost_detail(project, date_from, date_to)
        _csv_download(df, f"material_{project}.csv", "profit_csv_material")
    elif report == "Machinery Cost Report":
        costs = aggregate_project_costs(project, date_from=date_from, date_to=date_to)
        buckets = costs["buckets"][HEAD_MACHINERY]
        df = pd.DataFrame(
            [{"sub_head": SUBHEAD_LABELS.get(k, k), "amount": v} for k, v in buckets.items()]
        )
        _csv_download(df, f"machinery_{project}.csv", "profit_csv_machinery")
    elif report == "Overhead Cost Report":
        costs = aggregate_project_costs(project, date_from=date_from, date_to=date_to)
        buckets = costs["buckets"][HEAD_OVERHEAD]
        df = pd.DataFrame(
            [{"sub_head": SUBHEAD_LABELS.get(k, k), "amount": v} for k, v in buckets.items()]
        )
        _csv_download(df, f"overhead_{project}.csv", "profit_csv_overhead")
    elif report == "Budget vs Actual Report":
        bva = load_budget_vs_actual_profitability(project)
        _csv_download(bva, f"budget_actual_{project}.csv", "profit_csv_bva")
        if not bva.empty:
            st.dataframe(bva, use_container_width=True, hide_index=True)


def page_project_profitability() -> None:
    _inject_profitability_css()
    role = st.session_state.get("user_role", "")
    user_name = st.session_state.get("user_name", "")
    username = st.session_state.get("username", "")

    if not can_access_profitability(role):
        st.error("You do not have permission to view the Project Profitability Dashboard.")
        return

    st.subheader("Project Profitability Dashboard")
    st.caption(
        "Real-time project P&L — contract value, approved variations, cost heads, net profit, and traffic-light status."
    )

    allowed = _resolve_allowed_projects(role, user_name, username)
    if allowed is not None and not allowed:
        st.warning(
            "No projects are assigned to you. Ask an administrator to set **Site Incharge** on your projects "
            f"to match your name ({user_name or username})."
        )

    project, client, date_from, date_to = _filter_controls(allowed)
    summary = load_profitability_summary(
        project_name=project,
        client_name=client,
        date_from=date_from,
        date_to=date_to,
        allowed_names=allowed,
    )

    tabs = ["Project dashboard", "Owner dashboard", "Phase 3 integration", "Reports"]
    if not can_view_owner_profitability(role):
        tabs = ["Project dashboard", "Phase 3 integration", "Reports"]

    tab_objs = st.tabs(tabs)
    tab_idx = 0

    with tab_objs[tab_idx]:
        tab_idx += 1
        if project:
            prow = load_projects_base(project_name=project, allowed_names=allowed)
            if prow.empty:
                st.warning("Project not available in your scope.")
            else:
                row = build_project_profitability_row(prow.iloc[0], date_from=date_from, date_to=date_to)
                _render_project_dashboard(row)
        elif not summary.empty:
            pick = st.selectbox(
                "Select project",
                summary["project_name"].tolist(),
                key="profit_proj_pick_multi",
            )
            prow = load_projects_base(project_name=pick, allowed_names=allowed)
            row = build_project_profitability_row(prow.iloc[0], date_from=date_from, date_to=date_to)
            _render_project_dashboard(row)
        else:
            st.info("No projects match the filters.")

    if can_view_owner_profitability(role):
        with tab_objs[tab_idx]:
            tab_idx += 1
            _render_owner_dashboard(summary)

    with tab_objs[tab_idx]:
        tab_idx += 1
        from modules.phase3_integration import page_phase3_reports

        page_phase3_reports()

    with tab_objs[tab_idx]:
        _render_reports_tab(project, date_from, date_to, allowed)
