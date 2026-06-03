"""Subcontractor work orders and security deposit screens."""

import streamlit as st

from modules.database import (
    load_project_names,
    load_security_deposits,
    load_subcontractor_names,
    load_subcontractor_work_orders,
    save_security_deposit,
    save_subcontractor_work_order,
)


def page_work_orders():
    st.subheader("Subcontractor Work Orders")
    st.caption("Register work orders against projects and subcontractors.")

    projects = [""] + load_project_names()
    subs = [""] + load_subcontractor_names()

    with st.form("work_order_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        wo_number = c1.text_input("Work order number")
        project = c2.selectbox("Project", projects)
        subcontractor = st.selectbox("Subcontractor", subs)
        c3, c4 = st.columns(2)
        value = c3.number_input("Order value (Rs)", min_value=0.0, step=1000.0, value=0.0)
        status = c4.selectbox("Status", ["Active", "Completed", "Cancelled", "On hold"])
        if st.form_submit_button("SAVE WORK ORDER", type="primary", use_container_width=True):
            if not wo_number.strip():
                st.error("Work order number is required.")
            elif not project:
                st.error("Select a project.")
            elif not subcontractor:
                st.error("Select a subcontractor.")
            else:
                save_subcontractor_work_order(
                    {
                        "wo_number": wo_number.strip(),
                        "project_name": project,
                        "subcontractor_name": subcontractor,
                        "value": value,
                        "status": status,
                    }
                )
                st.success("Work order saved.")
                st.rerun()

    st.divider()
    df = load_subcontractor_work_orders()
    if df.empty:
        st.info("No work orders yet.")
    else:
        st.metric("Total WO value", f"Rs {float(df['value'].sum()):,.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True)


def page_security_deposit():
    st.subheader("Security Deposit")
    st.caption("Retention and security deposits held from subcontractors.")

    projects = [""] + load_project_names()
    subs = [""] + load_subcontractor_names()

    with st.form("security_deposit_form", clear_on_submit=True):
        contractor = st.selectbox("Contractor", subs)
        project = st.selectbox("Project", projects)
        c1, c2 = st.columns(2)
        retained = c1.number_input("Retained amount (Rs)", min_value=0.0, step=100.0, value=0.0)
        released = c2.number_input("Released amount (Rs)", min_value=0.0, step=100.0, value=0.0)
        if st.form_submit_button("SAVE REGISTER", type="primary", use_container_width=True):
            if not contractor:
                st.error("Select a contractor.")
            else:
                save_security_deposit(
                    {
                        "contractor": contractor,
                        "project_name": project,
                        "retained_amount": retained,
                        "released_amount": released,
                    }
                )
                st.success("Security deposit register updated.")
                st.rerun()

    st.divider()
    df = load_security_deposits()
    if df.empty:
        st.info("No security deposit records yet.")
    else:
        st.metric("Total balance held", f"Rs {float(df['balance'].sum()):,.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True)
