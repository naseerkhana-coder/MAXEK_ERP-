"""Measurement Book — cumulative DPR register and PDF export."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from modules.database import DATE_FMT, load_project_names
from modules.dpr_measurement_db import (
    load_boq_meta_for_item,
    load_measurement_book,
    load_measurement_book_detail,
    parse_dpr_date_for_filter,
)
from modules.document_pdfs import generate_bbs_report_pdf, generate_measurement_book_pdf
from modules.dpr_measurement_db import load_steel_bbs_report


def page_measurement_book():
    st.subheader("Measurement Book")
    st.caption(
        "Register of approved DPR measurements by project and BOQ item. "
        "Quantities sum across all measurement rows; use **Client Bill** for invoicing."
    )

    projects = [""] + load_project_names()
    c1, c2, c3, c4 = st.columns(4)
    project_name = c1.selectbox("Project", projects, key="mb_project")
    date_from = c2.date_input("From", value=None, key="mb_from")
    date_to = c3.date_input("To", value=None, key="mb_to")
    approved_only = c4.checkbox("Approved DPRs only", value=True, key="mb_approved")

    df_from = parse_dpr_date_for_filter(date_from) if date_from else ""
    df_to = parse_dpr_date_for_filter(date_to) if date_to else ""

    if not project_name:
        st.info("Select a project to view the measurement register.")
        return

    summary = load_measurement_book(
        project_name=project_name,
        date_from=df_from,
        date_to=df_to,
        approved_only=approved_only,
    )
    if summary.empty:
        st.warning("No measurements found for this filter.")
        return

    st.markdown("### Cumulative register (by BOQ item)")
    st.caption(
        "Total quantity = sum of all measurement row quantities on approved DPRs. "
        "Multiple rows on one DPR day are added together."
    )
    display = summary.rename(
        columns={
            "boq_number": "BOQ No",
            "boq_description": "Description",
            "unit": "Unit",
            "cumulative_qty": "Cumulative Qty",
            "dpr_count": "DPR Days",
            "measurement_rows": "Meas. Rows",
            "first_dpr_date": "First Date",
            "last_dpr_date": "Last Date",
        }
    )
    st.dataframe(display, width="stretch", hide_index=True)

    boq_options = [""] + [
        f"{r['boq_number']} | {str(r['boq_description'])[:40]}"
        for _, r in summary.iterrows()
    ]
    boq_map = {opt: row["boq_item_id"] for opt, (_, row) in zip(boq_options[1:], summary.iterrows())}

    st.markdown("---")
    st.markdown("### Measurement sheet detail")
    pick = st.selectbox("BOQ item (optional filter)", boq_options, key="mb_boq_pick")
    boq_item_id = boq_map.get(pick, "") if pick else ""
    if boq_item_id:
        meta = load_boq_meta_for_item(boq_item_id)
        if meta:
            m1, m2, m3 = st.columns(3)
            m1.metric("BOQ unit", meta.get("unit", "—"))
            m2.metric("Measurement type", meta.get("measurement_type", "—"))
            m3.metric("BOQ rate", f"₹ {meta.get('approved_rate', 0):,.2f}")

    detail = load_measurement_book_detail(
        project_name,
        boq_item_id=boq_item_id,
        date_from=df_from,
        date_to=df_to,
    )
    if detail.empty:
        st.info("No line-level measurements for this filter.")
    else:
        show = detail[
            [
                "dpr_date",
                "dpr_id",
                "boq_number",
                "measurement_type",
                "measurement_method",
                "avg_length",
                "avg_width",
                "avg_depth",
                "calculated_quantity",
                "unit",
                "location_text",
                "work_category",
                "include_in_client_bill",
            ]
        ].rename(
            columns={
                "dpr_date": "Date",
                "dpr_id": "DPR",
                "boq_number": "BOQ",
                "measurement_type": "Type",
                "measurement_method": "Method",
                "avg_length": "Avg L",
                "avg_width": "Avg W",
                "avg_depth": "Avg D",
                "calculated_quantity": "Qty",
                "unit": "Unit",
                "location_text": "Location",
                "work_category": "Category",
                "include_in_client_bill": "Client bill",
            }
        )
        st.dataframe(show, width="stretch", hide_index=True)

    c_pdf1, c_pdf2 = st.columns(2)
    safe_name = project_name.replace(" ", "_")[:40]
    if c_pdf1.button("Export measurement sheet (PDF)", type="primary", key="mb_export_pdf"):
        pdf_bytes = generate_measurement_book_pdf(
            project_name,
            summary_df=summary,
            detail_df=detail,
            date_from=df_from,
            date_to=df_to,
        )
        st.session_state["mb_pdf_bytes"] = pdf_bytes
    if st.session_state.get("mb_pdf_bytes"):
        st.download_button(
            "Download measurement sheet PDF",
            data=st.session_state["mb_pdf_bytes"],
            file_name=f"measurement_book_{safe_name}_{date.today().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            key="mb_pdf_dl",
        )

    bbs_df = load_steel_bbs_report(project_name, date_from=df_from, date_to=df_to)
    st.markdown("### Bar Bending Schedule (BBS)")
    if bbs_df.empty:
        st.caption("No steel BBS rows for this project/period.")
    else:
        st.dataframe(bbs_df, width="stretch", hide_index=True)
        if c_pdf2.button("Export BBS report (PDF)", key="mb_export_bbs_pdf"):
            st.session_state["mb_bbs_pdf_bytes"] = generate_bbs_report_pdf(
                project_name, bbs_df=bbs_df, date_from=df_from, date_to=df_to
            )
        if st.session_state.get("mb_bbs_pdf_bytes"):
            st.download_button(
                "Download BBS PDF",
                data=st.session_state["mb_bbs_pdf_bytes"],
                file_name=f"bbs_{safe_name}_{date.today().strftime('%Y%m%d')}.pdf",
                mime="application/pd