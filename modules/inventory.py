"""Inventory — material master, issues, and tools."""

from datetime import datetime

import streamlit as st

from modules.database import (
    DATE_FMT,
    DATE_INPUT_FMT,
    StockInsufficientError,
    get_stock_balance,
    load_material_issues,
    load_material_master,
    load_project_names,
    load_tools,
    save_material_issue,
    save_material_master,
    save_tool,
)
from modules.store import page_store


def _actor():
    return st.session_state.get("user_name", "User")


def page_material_master():
    st.subheader("Material Master")
    st.caption("Standard materials for stock and site issues.")

    tab_add, tab_list = st.tabs(["Add / Edit", "Material List"])
    with tab_add:
        with st.form("material_master_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            code = c1.text_input("Material code")
            name = c2.text_input("Material name")
            unit = st.selectbox("Unit", ["Nos", "Kg", "Bag", "Meter", "Litre", "Ton", "SQM", "M3"])
            if st.form_submit_button("SAVE MATERIAL", type="primary", use_container_width=True):
                if not name.strip():
                    st.error("Material name is required.")
                else:
                    save_material_master(
                        {
                            "material_code": code.strip(),
                            "material_name": name.strip(),
                            "unit": unit,
                            "status": "Active",
                        }
                    )
                    st.success("Material saved.")
                    st.rerun()

    with tab_list:
        df = load_material_master()
        if df.empty:
            st.info("No materials in master yet.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)


def page_material_issue():
    st.subheader("Material Issue")
    st.caption("Issue materials from store to project sites.")

    projects = [""] + load_project_names()
    materials = load_material_master()
    mat_options = [""]
    if not materials.empty:
        mat_options += [
            f"{r['material_code']} | {r['material_name']}"
            for _, r in materials.iterrows()
        ]

    with st.form("material_issue_form", clear_on_submit=True):
        project = st.selectbox("Project", projects)
        mat_sel = st.selectbox("Material", mat_options)
        c1, c2 = st.columns(2)
        qty = c1.number_input("Quantity", min_value=0.01, step=1.0, value=1.0)
        issue_date = c2.date_input("Issue date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        if mat_sel:
            _parts = mat_sel.split(" | ", 1)
            _bal_code = _parts[0].strip()
            _bal_name = _parts[1].strip() if len(_parts) > 1 else _parts[0]
            _avail = get_stock_balance(_bal_code, _bal_name)
            st.caption(f"Available in store: {_avail:g}")
        if st.form_submit_button("ISSUE MATERIAL", type="primary", use_container_width=True):
            if not project:
                st.error("Select a project.")
            elif not mat_sel:
                st.error("Select a material.")
            else:
                parts = mat_sel.split(" | ", 1)
                code = parts[0].strip()
                name = parts[1].strip() if len(parts) > 1 else parts[0]
                try:
                    save_material_issue(
                        {
                            "project_name": project,
                            "material_code": code,
                            "material_name": name,
                            "quantity": qty,
                            "issue_date": issue_date.strftime(DATE_FMT),
                        },
                        _actor(),
                    )
                    st.success("Material issue recorded and stock deducted.")
                    st.rerun()
                except StockInsufficientError as exc:
                    st.error(str(exc))

    st.divider()
    issues = load_material_issues()
    if issues.empty:
        st.info("No material issues yet.")
    else:
        st.dataframe(issues, use_container_width=True, hide_index=True)


def page_tools():
    st.subheader("Tools Register")
    st.caption("Track tools and equipment assigned to projects.")

    projects = [""] + load_project_names()
    tab_add, tab_list = st.tabs(["Add / Update", "Tools List"])
    with tab_add:
        with st.form("tools_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            code = c1.text_input("Tool code")
            name = c2.text_input("Tool name")
            c3, c4, c5 = st.columns(3)
            project = c3.selectbox("Project / site", projects)
            qty = c4.number_input("Quantity", min_value=1.0, step=1.0, value=1.0)
            condition = c5.selectbox("Condition", ["Good", "Fair", "Repair needed"])
            status = st.selectbox("Status", ["Available", "Issued", "Under repair", "Retired"])
            if st.form_submit_button("SAVE TOOL", type="primary", use_container_width=True):
                if not name.strip():
                    st.error("Tool name is required.")
                else:
                    save_tool(
                        {
                            "tool_code": code.strip(),
                            "tool_name": name.strip(),
                            "project_name": project,
                            "quantity": qty,
                            "condition": condition,
                            "status": status,
                        }
                    )
                    st.success("Tool saved.")
                    st.rerun()

    with tab_list:
        df = load_tools()
        if df.empty:
            st.info("No tools registered yet.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)


def page_inv_purchase():
    page_store()
