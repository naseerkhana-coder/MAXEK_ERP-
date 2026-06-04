"""Phase 3 integration — orchestration, UI helpers, and report page."""

from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from modules.database import load_project_names
from modules.phase3_integration_db import (
    aggregate_project_revenue,
    billing_quantities_for_dpr,
    check_integration_alerts,
    estimate_material_consumption,
    get_boq_integration_stats,
    load_bbs_register,
    load_boq_consumption_report,
    load_client_billing_register,
    load_dpr_register,
    load_measurement_book_register,
    load_quantity_progress_report,
    sync_boq_item_quantities,
    sync_project_progress_percent,
    validate_client_bill_lines,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_after_dpr_recalc(dpr_id: str, conn=None) -> None:
    """Called after measurement totals are updated on a DPR."""
    from modules.database import get_conn

    own = conn is None
    conn = conn or get_conn()
    row = conn.execute(
        "SELECT project_id, project_name, boq_item_id FROM dpr_reports WHERE dpr_id = ?",
        (dpr_id,),
    ).fetchone()
    boq_ids = set()
    if row and row[2]:
        boq_ids.add(row[2])
    for (bid,) in conn.execute(
        "SELECT DISTINCT boq_item_id FROM dpr_boq_lines WHERE dpr_id = ? AND boq_item_id IS NOT NULL",
        (dpr_id,),
    ).fetchall():
        if bid:
            boq_ids.add(bid)
    for bid in boq_ids:
        sync_boq_item_quantities(boq_item_id=bid, conn=conn)
    if row:
        sync_project_progress_percent(
            project_id=str(row[0] or ""),
            project_name=str(row[1] or ""),
            conn=conn,
        )
    conn.commit()
    if own:
        conn.close()


def run_after_dpr_approval(dpr_id: str) -> None:
    """Called when a DPR is approved (engineer or client) — refresh BOQ / progress."""
    run_after_dpr_recalc(dpr_id)


def run_after_dpr_deleted(dpr_id: str = "", project_name: str = "", project_id: str = "") -> None:
    if project_name or project_id:
        sync_boq_item_quantities(project_id=project_name or project_id)
        sync_project_progress_percent(project_id=project_id, project_name=project_name)


def run_after_client_bill_saved(project_name: str = "") -> None:
    if project_name:
        sync_boq_item_quantities(project_id=project_name)
        sync_project_progress_percent(project_id=project_name, project_name=project_name)


def render_integration_alerts(
    *,
    boq_item_id: str = "",
    project_name: str = "",
    key_prefix: str = "p3",
) -> None:
    alerts = check_integration_alerts(boq_item_id=boq_item_id, project_name=project_name)
    for alert in alerts:
        st.warning(alert["message"], icon="⚠️")


def render_dpr_billing_metrics(boq_item_id: str, include_in_bill: bool) -> None:
    if not boq_item_id:
        return
    stats = get_boq_integration_stats(boq_item_id)
    render_integration_alerts(boq_item_id=boq_item_id)
    q1, q2, q3, q4, q5, q6 = st.columns(6)
    q1.metric("BOQ Qty", f"{stats['total_qty']:,.2f}")
    q2.metric("Executed", f"{stats['executed_qty']:,.2f}")
    q3.metric("Balance BOQ", f"{stats['balance_qty']:,.2f}")
    q4.metric("Billed", f"{stats['billed_qty']:,.2f}")
    q5.metric("Pending Bill", f"{stats['pending_billing_qty']:,.2f}")
    q6.metric("Revenue earned", f"₹ {stats['revenue_earned']:,.0f}")
    if include_in_bill:
        st.caption(
            "Client bill: **Pending** = billable approved qty − already billed · "
            "**Balance billing** = same until invoiced."
        )


def render_dpr_material_estimate(boq_item_id: str, progress_qty: float) -> None:
    if not boq_item_id or progress_qty <= 0:
        return
    est = estimate_material_consumption(boq_item_id, progress_qty)
    if est.empty:
        st.caption(
            "No BOQ→material mapping — configure under **Projects → Material Planning** "
            "(BOQ Mapping tab)."
        )
        return
    show = est.rename(columns={"estimated_qty": "planned_qty"})
    with st.expander("Planned material requirement (BOQ map × progress qty)", expanded=True):
        st.caption(
            "Planned qty = progress quantity × qty per BOQ unit. "
            "Compared with store issues on Material Planning screens."
        )
        st.dataframe(show, use_container_width=True, hide_index=True)


def render_project_integration_panel(project_name: str, profitability_row: dict | None = None) -> None:
    """BOQ / billing / P&L summary on project profitability dashboard."""
    if not project_name:
        return
    st.markdown("#### Phase 3 — Quantity & billing integration")
    render_integration_alerts(project_name=project_name)
    rev = aggregate_project_revenue(project_name)
    boq_df = load_quantity_progress_report(project_name)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Work done value", f"₹ {rev['work_done_value']:,.0f}")
    c2.metric("Revenue earned (executed)", f"₹ {rev['revenue_earned']:,.0f}")
    c3.metric("Billed revenue", f"₹ {rev['billed_revenue']:,.0f}")
    if profitability_row:
        c4.metric(
            "Net P/L",
            f"₹ {float(profitability_row.get('net_profit') or 0):,.0f}",
            f"{float(profitability_row.get('profit_pct') or 0):.1f}%",
        )
    if not boq_df.empty:
        show = boq_df[
            [
                "boq_number",
                "description",
                "unit",
                "boq_qty",
                "executed_qty",
                "balance_qty",
                "billed_qty",
                "revenue_earned",
            ]
        ].copy()
        st.dataframe(show, use_container_width=True, hide_index=True)


def _report_filters(key_prefix: str) -> tuple[str, str, str]:
    projects = [""] + load_project_names()
    c1, c2, c3 = st.columns(3)
    project = c1.selectbox("Project", projects, key=f"{key_prefix}_proj")
    default_end = date.today()
    default_start = default_end - timedelta(days=90)
    d_from = c2.date_input("From", value=default_start, key=f"{key_prefix}_from")
    d_to = c3.date_input("To", value=default_end, key=f"{key_prefix}_to")
    return (
        project,
        d_from.strftime("%Y-%m-%d") if d_from else "",
        d_to.strftime("%Y-%m-%d") if d_to else "",
    )


def _export_buttons(df: pd.DataFrame, basename: str, key: str) -> None:
    if df is None or df.empty:
        st.caption("No data for export.")
        return
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, f"{basename}.csv", "text/csv", key=f"{key}_csv")
    try:
        from modules.pdf_templates import PdfDocument

        doc = PdfDocument()
        doc.add_company_block(basename.replace("_", " ").title())
        rows = [[str(v) for v in row] for row in df.values.tolist()]
        doc.add_data_table([str(c) for c in df.columns.tolist()], rows)
        st.download_button(
            "Download PDF",
            doc.build(),
            f"{basename}.pdf",
            "application/pdf",
            key=f"{key}_pdf",
        )
    except Exception:
        st.caption("PDF export unavailable; use CSV.")


def page_phase3_reports() -> None:
    st.subheader("Phase 3 Integration Reports")
    st.caption("DPR, measurement book, billing, and BOQ progress registers.")
    tab_labels = [
        "DPR Register",
        "Measurement Book",
        "BBS Register",
        "Client Billing",
        "Quantity Progress",
        "BOQ Consumption",
    ]
    tabs = st.tabs(tab_labels)
    specs = [
        ("dpr", load_dpr_register, True),
        ("mb", load_measurement_book_register, True),
        ("bbs", load_bbs_register, True),
        ("bill", load_client_billing_register, True),
        ("qty", load_quantity_progress_report, False),
        ("cons", load_boq_consumption_report, False),
    ]
    for tab, (slug, loader, use_dates) in zip(tabs, specs):
        with tab:
            if use_dates:
                project, d_from, d_to = _report_filters(f"p3_{slug}")
                df = loader(project_name=project, date_from=d_from, date_to=d_to)
            else:
                project, _, _ = _report_filters(f"p3_{slug}")
                df = loader(project_name=project)
            st.dataframe(df, use_container_width=True, hide_index=True)
            _export_buttons(df, f"phase3_{slug}", f"p3_exp_{slug}")
