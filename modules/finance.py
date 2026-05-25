"""Unified Finance: petty cash, vouchers, payments, receipts, and approvals."""

from datetime import datetime

import pandas as pd
import streamlit as st

from modules.database import (
    DATE_FMT,
    FINANCE_STATUS_ACCOUNTS_CHECKED,
    FINANCE_STATUS_MD_APPROVED,
    FINANCE_STATUS_REJECTED,
    FINANCE_STATUS_SETTLED,
    FINANCE_STATUS_SUBMITTED,
    generate_id,
    get_conn,
    get_petty_cash_balance,
    insert_finance_transaction,
    load_client_names,
    load_employee_options,
    load_finance_transactions,
    load_lookup,
    load_petty_cash_balances,
    load_project_names,
    load_subcontractor_names,
    update_finance_status,
)
from modules.pages import _resolve_pay_to_name, _save_upload

FINANCE_TYPE_LABELS = {
    "expense_voucher": "Expense / Voucher",
    "payment_out": "Payment Out",
    "cash_receipt": "Cash Receipt",
    "petty_cash_issue": "Petty Cash Issue",
}
PAYMENT_MODES = ["Cash", "Bank Transfer", "Cheque", "UPI"]
FUNDING_SOURCES = ["Petty Cash", "Company Fund"]
RECEIPT_CATEGORIES = ["General Receipt", "Petty Cash Return", "Client Receipt", "Other"]


def _current_user():
    return st.session_state.get("user_name", "User")


def _current_role():
    return st.session_state.get("user_role", "Admin")


def _is_site_role():
    return _current_role() in {"Site Engineer", "Project Manager"}


def _can_accounts_action():
    return _current_role() in {"Admin", "Accountant"}


def _can_md_action():
    return _current_role() in {"Admin", "MD"}


def _can_create_payment_types():
    return _current_role() in {"Admin", "Accountant", "MD"}


def _render_petty_balances():
    balances_df = load_petty_cash_balances()
    if balances_df.empty:
        st.info("No project petty cash activity yet.")
        return
    st.markdown("#### Petty Cash Balance by Project")
    st.dataframe(balances_df, width="stretch", hide_index=True)


def _submit_finance_form(
    transaction_type,
    transaction_date,
    project_name,
    client_name,
    category_head,
    pay_to_type,
    pay_to_name,
    amount,
    payment_mode,
    funding_source,
    reference_number,
    remarks,
    document_upload,
):
    if amount <= 0:
        st.error("Amount must be greater than zero.")
        return False
    if transaction_type == "expense_voucher" and not category_head:
        st.error("Please select an expense head.")
        return False
    if transaction_type in {"payment_out", "petty_cash_issue"} and not category_head:
        st.error("Please select a payment head.")
        return False
    if transaction_type == "expense_voucher" and funding_source == "Petty Cash" and project_name:
        balance = get_petty_cash_balance(project_name)
        if amount > balance:
            st.error(f"Petty cash balance for this project is Rs {balance:,.2f}. Cannot exceed available float.")
            return False
    transaction_id = generate_id("FIN", "finance_transactions")
    doc_path = _save_upload(document_upload, "uploads/finance", transaction_id)
    conn = get_conn()
    insert_finance_transaction(
        conn,
        {
            "transaction_id": transaction_id,
            "transaction_type": transaction_type,
            "transaction_date": transaction_date.strftime(DATE_FMT),
            "project_name": project_name,
            "client_name": client_name,
            "category_head": category_head,
            "pay_to_type": pay_to_type,
            "pay_to_name": pay_to_name,
            "amount": amount,
            "payment_mode": payment_mode,
            "funding_source": funding_source,
            "reference_number": reference_number,
            "remarks": remarks,
            "document_upload": doc_path,
            "status": FINANCE_STATUS_SUBMITTED,
            "submitted_by": _current_user(),
        },
    )
    conn.commit()
    conn.close()
    st.success(f"Submitted for approval. ID: {transaction_id}")
    st.rerun()
    return True


def _render_expense_voucher_tab(clients, projects, expense_heads):
    st.markdown("### Expense / Voucher")
    st.caption("Site petty cash or company-funded expense. Submitted → Accounts check → MD approval → Settled.")
    with st.form("finance_expense_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        transaction_date = c1.date_input("Date")
        expense_head = c2.selectbox("Expense Head", expense_heads, index=0)
        funding_source = c3.selectbox("Funding Source", FUNDING_SOURCES)
        project_name = c1.selectbox("Project / Site", projects, index=0)
        client_name = c2.selectbox("Client", clients, index=0)
        paid_to = c3.text_input("Paid To")
        amount = c1.number_input("Amount (Rs)", min_value=0.0, step=100.0)
        payment_mode = c2.selectbox("Payment Mode", PAYMENT_MODES)
        reference_number = c3.text_input("Reference / Bill No")
        remarks = st.text_input("Remarks")
        bill_upload = st.file_uploader("Bill / Receipt Upload", key="finance_expense_doc")
        if project_name and funding_source == "Petty Cash":
            st.caption(f"Available petty cash for site: Rs {get_petty_cash_balance(project_name):,.2f}")
        if st.form_submit_button("SUBMIT FOR APPROVAL", type="primary", width="stretch"):
            _submit_finance_form(
                "expense_voucher",
                transaction_date,
                project_name,
                client_name,
                expense_head,
                "Vendor",
                paid_to,
                amount,
                payment_mode,
                funding_source,
                reference_number,
                remarks,
                bill_upload,
            )


def _render_payment_out_tab(clients, projects, payment_heads):
    st.markdown("### Payment Out")
    employee_options = load_employee_options()
    employee_labels = [f"{eid} - {ename}" for eid, ename in employee_options]
    subcontractors = [""] + load_subcontractor_names()
    with st.form("finance_payment_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        transaction_date = c1.date_input("Date")
        payment_head = c2.selectbox("Payment Head", payment_heads, index=0)
        payment_mode = c3.selectbox("Payment Mode", PAYMENT_MODES)
        pay_to_type = c1.selectbox("Pay To Type", ["Employee", "Sub Contractor", "Vendor", "Client", "Other"])
        if pay_to_type == "Employee":
            pay_to_name = c2.selectbox("Pay To Name", [""] + employee_labels, index=0)
        elif pay_to_type == "Sub Contractor":
            pay_to_name = c2.selectbox("Pay To Name", subcontractors, index=0)
        elif pay_to_type == "Client":
            pay_to_name = c2.selectbox("Pay To Name", clients, index=0)
        else:
            pay_to_name = c2.text_input("Pay To Name")
        project_name = c3.selectbox("Project", projects, index=0)
        client_name = c1.selectbox("Client", clients, index=0)
        amount = c2.number_input("Amount (Rs)", min_value=0.0, step=100.0)
        reference_number = c3.text_input("Reference Number")
        remarks = st.text_input("Remarks")
        bill_upload = st.file_uploader("Bill Upload", key="finance_payment_doc")
        if st.form_submit_button("SUBMIT FOR APPROVAL", type="primary", width="stretch"):
            resolved = _resolve_pay_to_name(pay_to_type, pay_to_name)
            if pay_to_type in {"Employee", "Sub Contractor", "Client"} and not resolved:
                st.error("Please select who the payment is for.")
            else:
                _submit_finance_form(
                    "payment_out",
                    transaction_date,
                    project_name,
                    client_name,
                    payment_head,
                    pay_to_type,
                    resolved,
                    amount,
                    payment_mode,
                    "Company Fund",
                    reference_number,
                    remarks,
                    bill_upload,
                )


def _render_cash_receipt_tab(clients, projects):
    st.markdown("### Cash Receipt")
    with st.form("finance_receipt_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        transaction_date = c1.date_input("Date")
        receipt_category = c2.selectbox("Receipt Type", RECEIPT_CATEGORIES)
        payment_mode = c3.selectbox("Payment Mode", PAYMENT_MODES)
        project_name = c1.selectbox("Project", projects, index=0)
        client_name = c2.selectbox("Client", clients, index=0)
        received_from = c3.text_input("Received From")
        amount = c1.number_input("Amount (Rs)", min_value=0.0, step=100.0)
        reference_number = c2.text_input("Reference / Receipt No")
        remarks = c3.text_input("Remarks")
        receipt_upload = st.file_uploader("Receipt Upload", key="finance_receipt_doc")
        if st.form_submit_button("SUBMIT FOR APPROVAL", type="primary", width="stretch"):
            _submit_finance_form(
                "cash_receipt",
                transaction_date,
                project_name,
                client_name,
                receipt_category,
                "Other",
                received_from,
                amount,
                payment_mode,
                "",
                reference_number,
                remarks,
                receipt_upload,
            )


def _load_staff_select_options():
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT employee_id, employee_name, COALESCE(designation, '') AS designation
        FROM employees
        WHERE COALESCE(employee_id, '') != ''
          AND COALESCE(employee_type, '') = 'Company Staff'
          AND COALESCE(status, 'Active') IN ('Active', 'ACTIVE')
        ORDER BY employee_name
        """,
        conn,
    )
    conn.close()
    if df.empty:
        return [""], {}
    labels = []
    label_to_name = {}
    for _, row in df.iterrows():
        label = (
            f"{row['employee_id']} - {row['employee_name']}"
            + (f" ({row['designation']})" if row["designation"] else "")
        )
        labels.append(label)
        label_to_name[label] = row["employee_name"]
    return [""] + labels, label_to_name


def _render_petty_issue_tab(projects):
    st.markdown("### Petty Cash Issue to Site")
    st.caption("Issue petty cash float to a company staff member for a project/site.")
    staff_labels, staff_name_map = _load_staff_select_options()
    if len(staff_labels) <= 1:
        st.info("Add Company Staff in Employee Management before issuing petty cash.")
    with st.form("finance_petty_issue_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        transaction_date = c1.date_input("Date")
        project_name = c2.selectbox("Project / Site", projects, index=0)
        staff_pick = c3.selectbox("Staff (Issued To)", staff_labels, index=0, key="petty_issue_staff")
        amount = c1.number_input("Amount to Issue (Rs)", min_value=0.0, step=500.0)
        payment_mode = c2.selectbox("Payment Mode", PAYMENT_MODES)
        reference_number = c3.text_input("Reference Number")
        remarks = st.text_input("Remarks")
        doc_upload = st.file_uploader("Supporting Document", key="finance_petty_doc")
        if st.form_submit_button("SUBMIT FOR APPROVAL", type="primary", width="stretch"):
            if not project_name:
                st.error("Project / Site is required.")
            elif not staff_pick:
                st.error("Please select the staff member receiving petty cash.")
            else:
                staff_name = staff_name_map.get(staff_pick, _resolve_pay_to_name("Employee", staff_pick))
                _submit_finance_form(
                    "petty_cash_issue",
                    transaction_date,
                    project_name,
                    "",
                    "Petty Cash",
                    "Employee",
                    staff_name,
                    amount,
                    payment_mode,
                    "Company Fund",
                    reference_number,
                    remarks,
                    doc_upload,
                )


def _approval_queue_df(status):
    df = load_finance_transactions(status=status, limit=500)
    if df.empty:
        return df
    df["transaction_type"] = df["transaction_type"].map(
        lambda value: FINANCE_TYPE_LABELS.get(value, value)
    )
    return df


def _render_approval_actions(df, status, next_status, action_label, roles_ok, need_reason_on_reject=False):
    if not roles_ok or df.empty:
        return
    options = {
        f"{row['transaction_id']} | {row['transaction_type']} | {row['project_name']} | Rs {row['amount']:,.2f}": row[
            "transaction_id"
        ]
        for _, row in df.iterrows()
    }
    selected_label = st.selectbox(f"Select entry ({status})", [""] + list(options.keys()), key=f"pick_{status}")
    if not selected_label:
        return
    transaction_id = options[selected_label]
    c1, c2 = st.columns(2)
    rejection_reason = ""
    if need_reason_on_reject:
        rejection_reason = st.text_input("Rejection reason", key=f"reject_reason_{status}")
    if c1.button(action_label, type="primary", width="stretch", key=f"approve_{status}_{transaction_id}"):
        conn = get_conn()
        update_finance_status(conn, transaction_id, next_status, _current_user())
        conn.commit()
        conn.close()
        st.success(f"Marked as {next_status}.")
        st.rerun()
    if c2.button("REJECT", type="secondary", width="stretch", key=f"reject_{status}_{transaction_id}"):
        if need_reason_on_reject and not rejection_reason.strip():
            st.error("Rejection reason is required.")
        else:
            conn = get_conn()
            update_finance_status(
                conn,
                transaction_id,
                FINANCE_STATUS_REJECTED,
                _current_user(),
                rejection_reason.strip(),
            )
            conn.commit()
            conn.close()
            st.success("Transaction rejected.")
            st.rerun()


def _render_approvals_tab():
    st.markdown("### Approvals")
    st.caption("Flow: Submitted → Accounts Checked → MD Approved → Settled (no amount limit; all need MD approval).")

    submitted_df = _approval_queue_df(FINANCE_STATUS_SUBMITTED)
    if not submitted_df.empty:
        st.markdown("#### Pending Accounts Check")
        st.dataframe(submitted_df, width="stretch", hide_index=True)
        _render_approval_actions(
            submitted_df,
            FINANCE_STATUS_SUBMITTED,
            FINANCE_STATUS_ACCOUNTS_CHECKED,
            "ACCOUNTS CHECKED",
            _can_accounts_action(),
            need_reason_on_reject=True,
        )
    elif _can_accounts_action():
        st.info("No transactions pending accounts check.")

    accounts_df = _approval_queue_df(FINANCE_STATUS_ACCOUNTS_CHECKED)
    if not accounts_df.empty:
        st.markdown("#### Pending MD Approval")
        st.dataframe(accounts_df, width="stretch", hide_index=True)
        _render_approval_actions(
            accounts_df,
            FINANCE_STATUS_ACCOUNTS_CHECKED,
            FINANCE_STATUS_MD_APPROVED,
            "MD APPROVED",
            _can_md_action(),
            need_reason_on_reject=True,
        )
    elif _can_md_action():
        st.info("No transactions pending MD approval.")

    md_df = _approval_queue_df(FINANCE_STATUS_MD_APPROVED)
    if not md_df.empty:
        st.markdown("#### Pending Settlement (Accounts)")
        st.dataframe(md_df, width="stretch", hide_index=True)
        _render_approval_actions(
            md_df,
            FINANCE_STATUS_MD_APPROVED,
            FINANCE_STATUS_SETTLED,
            "MARK SETTLED / PAID",
            _can_accounts_action(),
        )
    elif _can_accounts_action():
        st.info("No transactions pending settlement.")


def _render_register_tab():
    st.markdown("### Finance Register")
    df = load_finance_transactions(limit=500)
    if df.empty:
        st.info("No finance transactions yet.")
        return
    df["transaction_type"] = df["transaction_type"].map(
        lambda value: FINANCE_TYPE_LABELS.get(value, value)
    )
    st.dataframe(df, width="stretch", hide_index=True)


def page_finance():
    st.subheader("Finance")
    role = _current_role()
    clients = [""] + load_client_names()
    projects = [""] + load_project_names()
    expense_heads = [""] + load_lookup("expense_heads", "head_name")
    payment_heads = [""] + load_lookup("payment_heads", "head_name")

    _render_petty_balances()

    if _is_site_role():
        tabs = st.tabs(["Expense / Voucher", "Register"])
        with tabs[0]:
            _render_expense_voucher_tab(clients, projects, expense_heads)
        with tabs[1]:
            _render_register_tab()
        return

    tab_labels = [
        "Expense / Voucher",
        "Payment Out",
        "Cash Receipt",
        "Petty Cash Issue",
        "Approvals",
        "Register",
    ]
    tabs = st.tabs(tab_labels)
    with tabs[0]:
        _render_expense_voucher_tab(clients, projects, expense_heads)
    with tabs[1]:
        if _can_create_payment_types():
            _render_payment_out_tab(clients, projects, payment_heads)
        else:
            st.warning("Your role cannot create payment-out entries.")
    with tabs[2]:
        if _can_create_payment_types():
            _render_cash_receipt_tab(clients, projects)
        else:
            st.warning("Your role cannot create cash receipts.")
    with tabs[3]:
        if _can_create_payment_types():
            _render_petty_issue_tab(projects)
        else:
            st.warning("Your role cannot issue petty cash.")
    with tabs[4]:
        if role in {"Admin", "Accountant", "MD"}:
            _render_approvals_tab()
        else:
            st.warning("Approvals are for Accounts and MD only.")
    with tabs[5]:
        _render_register_tab()
