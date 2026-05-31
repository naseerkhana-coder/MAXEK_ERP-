"""Store / material request module for MAXEK ERP."""

from datetime import datetime

import streamlit as st

from modules.database import (
    DATE_FMT,
    generate_id,
    get_conn,
    load_material_requests,
    load_project_names,
    log_finance_audit,
    next_document_number,
    update_material_request_status,
)

MATERIAL_STATUSES = ["Pending", "Approved", "Rejected", "Issued"]
MATERIAL_UNITS = ["Nos", "Kg", "Bag", "Meter", "Litre", "Ton", "SQM", "M3"]


def _current_user():
    return st.session_state.get("user_name", "User")


def _current_role():
    return st.session_state.get("user_role", "Admin")


def _can_approve_requests():
    return _current_role() in {"Admin", "MD", "Project Manager", "Site Engineer"}


def _timestamp():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _render_new_request_tab(projects):
    st.markdown("### New Material Request")
    st.caption("Site staff can raise material requests. Store / PM approves and issues items.")
    with st.form("material_request_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        project_name = c1.selectbox("Project", projects, index=0)
        item_name = c2.text_input("Item name")
        c3, c4, c5 = st.columns(3)
        quantity = c3.number_input("Quantity", min_value=0.01, step=1.0, value=1.0)
        unit = c4.selectbox("Unit", MATERIAL_UNITS, index=0)
        required_date = c5.date_input("Required date", value=datetime.now().date(), format=DATE_FMT)
        remarks = st.text_input("Remarks")
        if st.form_submit_button("SUBMIT REQUEST", type="primary", width="stretch"):
            if not item_name.strip():
                st.error("Item name is required.")
            elif quantity <= 0:
                st.error("Quantity must be greater than zero.")
            else:
                request_id = generate_id("MR", "material_requests")
                conn = get_conn()
                doc_no = next_document_number("material_request", conn=conn)
                conn.execute(
                    """
                    INSERT INTO material_requests(
                        request_id, document_no, project_name, item_name, quantity, unit,
                        required_date, remarks, status, created_by, created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        request_id,
                        doc_no,
                        project_name or "",
                        item_name.strip(),
                        float(quantity),
                        unit,
                        required_date.strftime(DATE_FMT),
                        remarks.strip(),
                        "Pending",
                        _current_user(),
                        _timestamp(),
                    ),
                )
                log_finance_audit(
                    conn,
                    "material_request",
                    request_id,
                    "Created",
                    _current_user(),
                    "",
                    "Pending",
                    remarks.strip(),
                    {"document_no": doc_no},
                )
                conn.commit()
                conn.close()
                st.success(f"Material request saved: {doc_no}")
                st.rerun()


def _request_options(df):
    return {
        (
            f"{row['request_id']} | {row['item_name']} | {row['project_name'] or '—'} | "
            f"{row['quantity']} {row['unit']} | {row['status']}"
        ): row["request_id"]
        for _, row in df.iterrows()
    }


def _render_action_block(df, title, actions, key_prefix):
    if df.empty:
        st.info(f"No {title.lower()}.")
        return
    st.markdown(f"#### {title}")
    st.dataframe(df, width="stretch", hide_index=True)
    if not _can_approve_requests():
        st.warning("Your role cannot update material request status.")
        return
    options = _request_options(df)
    selected = st.selectbox("Select request", [""] + list(options.keys()), key=f"pick_{key_prefix}")
    if not selected:
        return
    request_id = options[selected]
    cols = st.columns(len(actions))
    for col, (label, status) in zip(cols, actions):
        btn_type = "primary" if status == "Approved" or status == "Issued" else "secondary"
        if col.button(label, type=btn_type, width="stretch", key=f"{key_prefix}_{status}_{request_id}"):
            if update_material_request_status(request_id, status):
                st.success(f"Request {request_id} marked as {status}.")
                st.rerun()
            else:
                st.error("Could not update request.")


def _render_approvals_tab():
    st.markdown("### Approvals & Issue")
    st.caption("Flow: Pending → Approved / Rejected → Issued (for approved items).")
    pending_df = load_material_requests(status="Pending")
    _render_action_block(
        pending_df,
        "Pending approval",
        [("APPROVE", "Approved"), ("REJECT", "Rejected")],
        "pending",
    )
    approved_df = load_material_requests(status="Approved")
    _render_action_block(
        approved_df,
        "Approved — ready to issue",
        [("MARK ISSUED", "Issued")],
        "approved",
    )


def _render_register_tab():
    st.markdown("### All Material Requests")
    filter_status = st.selectbox("Filter by status", ["All"] + MATERIAL_STATUSES, index=0)
    status = None if filter_status == "All" else filter_status
    df = load_material_requests(status=status, limit=500)
    if df.empty:
        st.info("No material requests yet.")
        return
    st.dataframe(df, width="stretch", hide_index=True)


def page_store():
    st.subheader("Store / Materials")
    projects = [""] + load_project_names()
    focus = st.session_state.pop("store_tab", None)
    if focus == "register":
        _render_register_tab()
        with st.expander("New request & approvals", expanded=False):
            tab_new, tab_appr = st.tabs(["New Request", "Approvals"])
            with tab_new:
                _render_new_request_tab(projects)
            with tab_appr:
                _render_approvals_tab()
    elif focus == "new":
        _render_new_request_tab(projects)
        with st.expander("Approvals & stock register", expanded=False):
            tab_appr, tab_reg = st.tabs(["Approvals", "Register"])
            with tab_appr:
                _render_approvals_tab()
            with tab_reg:
                _render_register_tab()
    else:
        tabs = st.tabs(["New Request", "Approvals", "Register"])
        with tabs[0]:
            _render_new_request_tab(projects)
        with tabs[1]:
            _render_approvals_tab()
        with tabs[2]:
            _render_register_tab()
