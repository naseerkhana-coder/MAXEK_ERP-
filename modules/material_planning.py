"""Material Planning & Consumption Control — UI."""

from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from modules.database import DATE_FMT, load_project_names
from modules.material_planning_db import (
    MATERIAL_CATEGORIES,
    delete_boq_material_map_row,
    load_boq_item_consumption_report,
    load_boq_material_map,
    load_planned_vs_actual,
    load_project_boq_items_for_mapping,
    load_project_material_summary,
    load_variance_report,
    save_boq_material_map_row,
    save_material_planning_snapshot,
)
from modules.roles import is_project_manager, is_store_keeper, is_super_admin

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MP_CSS_PATH = os.path.join(BASE_DIR, "styles", "material_planning.css")


def _inject_css() -> None:
    if os.path.isfile(MP_CSS_PATH):
        with open(MP_CSS_PATH, encoding="utf-8") as f:
            st.markdown(f'<div class="mp-wrap"><style>{f.read()}</style></div>', unsafe_allow_html=True)


def _can_edit_mapping(role: str) -> bool:
    return is_super_admin(role) or is_project_manager(role) or is_store_keeper(role)


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
        d_from.strftime(DATE_FMT) if d_from else "",
        d_to.strftime(DATE_FMT) if d_to else "",
    )


def _export_buttons(df: pd.DataFrame, basename: str, key: str) -> None:
    if df is None or df.empty:
        st.caption("No data for export.")
        return
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, f"{basename}.csv", "text/csv", key=f"{key}_csv")
    try:
        from modules.document_pdfs import generate_material_planning_report_pdf

        pdf_bytes = generate_material_planning_report_pdf(
            basename.replace("_", " ").title(),
            df,
        )
        st.download_button(
            "Download PDF",
            pdf_bytes,
            f"{basename}.pdf",
            "application/pdf",
            key=f"{key}_pdf",
        )
    except Exception:
        st.caption("PDF export unavailable; use CSV.")


def _style_variance_df(df: pd.DataFrame) -> None:
    if df.empty or "variance_status" not in df.columns:
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    def _row_style(row):
        if row.get("is_excess"):
            return ["background-color: #fef2f2"] * len(row)
        if float(row.get("variance_qty") or 0) < -0.0001:
            return ["background-color: #eff6ff"] * len(row)
        return [""] * len(row)

    styled = df.style.apply(_row_style, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)


def _tab_boq_mapping(role: str) -> None:
    st.markdown("Map **materials per BOQ unit** (e.g. 1 M³ concrete → 320 Kg cement).")
    projects = load_project_names()
    if not projects:
        st.warning("No projects found. Create a project and BOQ first.")
        return
    project = st.selectbox("Project", projects, key="mp_map_project")
    boq_df = load_project_boq_items_for_mapping(project)
    if boq_df.empty:
        st.info("No BOQ items for this project.")
        return
    labels = {
        f"{r['boq_number']} — {r['description']} ({r['unit']})": r["boq_item_id"]
        for _, r in boq_df.iterrows()
    }
    boq_label = st.selectbox("BOQ item", list(labels.keys()), key="mp_map_boq")
    boq_item_id = labels[boq_label]
    maps = load_boq_material_map(boq_item_id)
    if maps:
        st.dataframe(
            pd.DataFrame(maps),
            use_container_width=True,
            hide_index=True,
        )
        if _can_edit_mapping(role):
            del_id = st.selectbox(
                "Remove mapping",
                [""] + [m["map_id"] for m in maps],
                format_func=lambda x: x or "— Select —",
                key="mp_map_del",
            )
            if st.button("Delete selected mapping", key="mp_map_del_btn") and del_id:
                if delete_boq_material_map_row(del_id):
                    st.success("Mapping removed.")
                    st.rerun()
                else:
                    st.error("Could not delete mapping.")
    else:
        st.caption("No mappings yet for this BOQ item.")

    if not _can_edit_mapping(role):
        st.caption("Mapping edits require Project Manager, Store Keeper, or Admin.")
        return

    st.markdown("#### Add material row")
    with st.form("mp_boq_map_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        category = c1.selectbox("Category", MATERIAL_CATEGORIES, key="mp_cat")
        mat_name = c2.text_input("Material name", value=category if category != "Other" else "")
        mat_code = c3.text_input("Material code", placeholder="e.g. CEM-01")
        unit = c4.text_input("Unit", placeholder="Kg, M³, bag")
        qty = st.number_input("Qty per BOQ unit", min_value=0.0, value=0.0, step=0.01, key="mp_qty_per")
        remarks = st.text_input("Remarks", key="mp_map_remarks")
        if st.form_submit_button("Save mapping"):
            if not mat_name.strip():
                st.error("Material name is required.")
            elif qty <= 0:
                st.error("Qty per BOQ unit must be greater than zero.")
            else:
                save_boq_material_map_row(
                    boq_item_id,
                    mat_name.strip(),
                    qty,
                    material_code=mat_code.strip(),
                    unit=unit.strip(),
                    remarks=remarks.strip(),
                )
                st.success("BOQ material mapping saved.")
                st.rerun()


def _tab_planned_vs_actual() -> None:
    project, d_from, d_to = _report_filters("mp_pva")
    if not project:
        st.info("Select a project to compare planned vs actual consumption.")
        return
    df = load_planned_vs_actual(project, date_from=d_from, date_to=d_to)
    if df.empty:
        st.warning(
            "No planned or actual data. Add **BOQ material mappings** and **material issues** for this project."
        )
        return
    excess = int(df["is_excess"].sum()) if "is_excess" in df.columns else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Planned (total)", f"{df['planned_qty'].sum():,.2f}")
    c2.metric("Actual issued", f"{df['actual_qty'].sum():,.2f}")
    c3.metric("Variance", f"{df['variance_qty'].sum():,.2f}")
    c4.metric("Excess materials", str(excess))
    st.caption(
        "**Planned** = approved DPR progress × qty per BOQ unit · "
        "**Actual** = material issues · **Variance** = Actual − Planned"
    )
    _style_variance_df(df)
    _export_buttons(df, f"planned_vs_actual_{project}", "mp_pva_exp")


def _tab_variance_report() -> None:
    project, d_from, d_to = _report_filters("mp_var")
    df = load_variance_report(project_name=project, date_from=d_from, date_to=d_to)
    if df.empty:
        st.info("No variance data for the selected filters.")
        return
    if "is_excess" in df.columns:
        excess_df = df[df["is_excess"]]
        if not excess_df.empty:
            st.warning(f"**{len(excess_df)}** line(s) with excess issue (actual > planned).")
    _style_variance_df(df)
    _export_buttons(df, "material_variance_report", "mp_var_exp")


def _tab_project_summary() -> None:
    _, d_from, d_to = _report_filters("mp_sum")
    df = load_project_material_summary(date_from=d_from, date_to=d_to)
    if df.empty:
        st.info("No project summary data.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_buttons(df, "material_planning_project_summary", "mp_sum_exp")
    st.markdown("#### BOQ item consumption detail")
    project, _, _ = _report_filters("mp_boq_detail")
    if project:
        detail = load_boq_item_consumption_report(
            project_name=project, date_from=d_from, date_to=d_to
        )
        st.dataframe(detail, use_container_width=True, hide_index=True)
        _export_buttons(detail, f"boq_consumption_{project}", "mp_boq_exp")


def page_material_planning() -> None:
    _inject_css()
    st.subheader("Material Planning & Consumption Control")
    st.caption(
        "Compare **planned** consumption (BOQ map × approved DPR progress) with **actual** store issues. "
        "Variance = Actual − Planned; excess shown in red."
    )
    role = st.session_state.get("user_role", "Admin")
    tabs = st.tabs(
        [
            "BOQ Mapping",
            "Planned vs Actual",
            "Variance Report",
            "Project Summary",
        ]
    )
    with tabs[0]:
        _tab_boq_mapping(role)
    with tabs[1]:
        _tab_planned_vs_actual()
    with tabs[2]:
        _tab_variance_report()
    with tabs[3]:
        _tab_project_summary()

    with st.expander("Save period snapshot (optional)", expanded=False):
        project, d_from, d_to = _report_filters("mp_snap")
        if project and st.button("Save snapshot", key="mp_snap_btn"):
            df = load_planned_vs_actual(project, date_from=d_from, date_to=d_to)
            if df.empty:
                st.warning("Nothing to snapshot.")
            else:
                rows = df.to_dict("records")
                for r in rows:
                    r["material_key"] = (
                        (r.get("material_code") or r.get("material_name") or "").lower()
                    )
                sid = save_material_planning_snapshot(project, d_from, d_to, rows)
                st.success(f"Snapshot saved: {sid}")
