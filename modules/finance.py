"""Unified Finance: petty cash, vouchers, payments, receipts, and approvals."""

from datetime import datetime

import pandas as pd
import streamlit as st

from modules.database import (
    DATE_FMT,
    DATE_INPUT_FMT,
    FINANCE_STATUS_ACCOUNTS_CHECKED,
    FINANCE_STATUS_MD_APPROVED,
    FINANCE_STATUS_REJECTED,
    FINANCE_STATUS_SETTLED,
    FINANCE_STATUS_SUBMITTED,
    generate_id,
    get_conn,
    get_petty_cash_balance,
    get_supplier_payment_md_limit,
    insert_finance_transaction,
    list_staff_advances,
    load_client_names,
    load_employee_options,
    load_expense_invoices,
    load_finance_transactions,
    load_lookup,
    load_payroll_staff_options,
    load_petty_cash_balances,
    load_project_names,
    load_subcontractor_names,
    save_expense_invoice,
    save_staff_advance,
    update_staff_advance_status,
    update_finance_status,
)
from modules.pages import _resolve_pay_to_name, _save_upload
from modules.roles import (
    can_create_payment_vouchers,
    can_settle_finance,
    can_verify_finance,
    is_accounts_manager,
    is_management,
    is_site_role as check_site_role,
)

FINANCE_TYPE_LABELS = {
    "expense_voucher": "Expense / Voucher",
    "payment_out": "Payment Out",
    "cash_receipt": "Cash Receipt",
    "petty_cash_issue": "Petty Cash Issue",
}
FINANCE_ENTRY_TYPES = {
    "expense_voucher": "Expense (Invoice + GST)",
    "payment_out": "Payment Out",
    "cash_receipt": "Cash Receipt",
    "petty_cash_issue": "Petty Cash Issue to Site",
    "staff_advance": "Staff Advance",
}
HEAD_REQUIRED_MSG = "Please select a Head of Account before submitting."
PAYMENT_MODES = ["Cash", "Bank Transfer", "UPI", "Cheque"]
FUNDING_SOURCES = ["Petty Cash", "Company Fund"]
RECEIPT_CATEGORIES = ["General Receipt", "Petty Cash Return", "Client Receipt", "Other"]
EXP_TYPES = ["Expense", "Purchase"]
TAX_TYPES = ["IGST", "CGST+SGST"]
PAYMENT_STATUSES = ["Paid", "Credit", "Unpaid"]
EXPENSE_PAY_METHODS = ["Petty Cash", "Bank"]
GST_RATES = [5, 12, 18, 28]
ITEM_UNITS = ["Nos", "Kg", "Bag", "Meter", "Litre", "Ton", "SQM", "M3"]
LINE_ITEM_ROWS = 10


def _current_user():
    return st.session_state.get("user_name", "User")


def _current_role():
    return st.session_state.get("user_role", "Admin")


def _is_site_role():
    return check_site_role(_current_role())


def _can_accounts_action():
    return can_settle_finance(_current_role())


def _can_accounts_verify():
    return can_verify_finance(_current_role())


def _can_md_action():
    return is_management(_current_role())


def _can_create_payment_types():
    return can_create_payment_vouchers(_current_role())


def _allowed_entry_types():
    if _is_site_role():
        return ["expense_voucher", "staff_advance"]
    allowed = ["expense_voucher"]
    if _can_accounts_action():
        allowed.extend(["payment_out", "cash_receipt", "petty_cash_issue"])
    elif _current_role() == "Accounts Executive":
        allowed.extend(["payment_out", "cash_receipt"])
    elif _can_create_payment_types():
        allowed.extend(["payment_out", "cash_receipt"])
    if _can_accounts_verify() or _can_md_action() or _is_site_role():
        if "staff_advance" not in allowed:
            allowed.append("staff_advance")
    return allowed


def _heads_for_entry_type(entry_type, expense_heads, payment_heads):
    if entry_type == "expense_voucher":
        return expense_heads, "Expense Head *"
    if entry_type == "cash_receipt":
        return [""] + RECEIPT_CATEGORIES, "Receipt Type *"
    return payment_heads, "Payment Head *"


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
    document_no = insert_finance_transaction(
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
    st.success(f"Submitted for approval. Document: {document_no or transaction_id}")
    st.rerun()
    return True


def _calc_gst_slab(taxable, rate_pct, tax_type):
    taxable = float(taxable or 0)
    if taxable <= 0:
        return {"taxable": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0}
    if tax_type == "IGST":
        igst = round(taxable * rate_pct / 100, 2)
        return {"taxable": taxable, "cgst": 0.0, "sgst": 0.0, "igst": igst}
    half = round(taxable * rate_pct / 200, 2)
    return {"taxable": taxable, "cgst": half, "sgst": half, "igst": 0.0}


def _parse_expense_line_items(form_prefix):
    lines = []
    for idx in range(LINE_ITEM_ROWS):
        item = st.session_state.get(f"{form_prefix}_item_{idx}", "").strip()
        hsn_code = st.session_state.get(f"{form_prefix}_hsn_{idx}", "").strip()
        unit = st.session_state.get(f"{form_prefix}_unit_{idx}", "Nos")
        qty = float(st.session_state.get(f"{form_prefix}_qty_{idx}", 0) or 0)
        rate = float(st.session_state.get(f"{form_prefix}_rate_{idx}", 0) or 0)
        if not item and qty <= 0:
            continue
        amount = round(qty * rate, 2)
        lines.append(
            {
                "item_name": item,
                "hsn_code": hsn_code,
                "unit": unit,
                "quantity": qty,
                "rate": rate,
                "amount": amount,
            }
        )
    return lines


def _line_items_total(form_prefix):
    return round(sum(line["amount"] for line in _parse_expense_line_items(form_prefix)), 2)


def _render_expense_voucher_tab(clients, projects, expense_heads, embedded=False, preset_head=None):
    if not embedded:
        st.markdown("### Expense")
        st.caption(
            "Enter supplier invoice with item lines, GST (IGST or CGST/SGST), and payment status. "
            "Submitted for Accounts → MD approval → Settled."
        )
    form_prefix = "exp_inv"

    with st.form("finance_expense_invoice_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        expense_date = c1.date_input("Date", format=DATE_INPUT_FMT)
        supplier = c2.text_input("Supplier")
        invoice_no = c3.text_input("Invoice no")
        project_name = c4.selectbox("Project", projects, index=0)

        c5, c6 = st.columns(2)
        exp_type = c5.selectbox("Exp Type", EXP_TYPES)
        if preset_head is not None:
            exp_head = preset_head
            c6.text_input("Exp / Purchase head", value=preset_head or "—", disabled=True)
        else:
            exp_head = c6.selectbox("Exp / Purchase head", expense_heads, index=0)

        st.markdown("#### Item · HSN · Unit · Qty · Rate")
        h1, h2, h3, h4, h5, h6 = st.columns([2, 1, 1, 1, 1, 1])
        h1.markdown("**Item**")
        h2.markdown("**HSN**")
        h3.markdown("**Unit**")
        h4.markdown("**Qty**")
        h5.markdown("**Rate**")
        h6.markdown("**Amount**")

        line_total = 0.0
        for idx in range(LINE_ITEM_ROWS):
            r1, r2, r3, r4, r5, r6 = st.columns([2, 1, 1, 1, 1, 1])
            r1.text_input("Item", key=f"{form_prefix}_item_{idx}", label_visibility="collapsed")
            r2.text_input("HSN", key=f"{form_prefix}_hsn_{idx}", label_visibility="collapsed")
            r3.selectbox(
                "Unit",
                ITEM_UNITS,
                key=f"{form_prefix}_unit_{idx}",
                label_visibility="collapsed",
            )
            qty = r4.number_input(
                "Qty",
                min_value=0.0,
                step=1.0,
                key=f"{form_prefix}_qty_{idx}",
                label_visibility="collapsed",
            )
            rate = r5.number_input(
                "Rate",
                min_value=0.0,
                step=1.0,
                key=f"{form_prefix}_rate_{idx}",
                label_visibility="collapsed",
            )
            row_amount = round(float(qty or 0) * float(rate or 0), 2)
            line_total += row_amount
            r6.markdown(f"**{row_amount:,.2f}**")

        c7, c8 = st.columns(2)
        c7.metric("Taxable Amount (from lines)", f"Rs {line_total:,.2f}")
        c7.caption("Auto-calculated from Item × Qty × Rate. Enter GST taxable amounts below.")
        tax_type = c8.radio("Type of Tax", TAX_TYPES, horizontal=True)

        st.markdown("#### GST breakdown")
        g1, g2, g3, g4 = st.columns(4)
        g1.markdown("**Rate**")
        g2.markdown("**Taxable**")
        g3.markdown("**CGST / IGST**")
        g4.markdown("**SGST**")

        tax_slabs = {}
        total_cgst = total_sgst = total_igst = 0.0
        slab_taxable_sum = 0.0
        for rate in GST_RATES:
            t1, t2, t3, t4 = st.columns(4)
            t1.markdown(f"**{rate}%**")
            slab_taxable = t2.number_input(
                f"Taxable {rate}%",
                min_value=0.0,
                step=100.0,
                key=f"{form_prefix}_slab_{rate}",
                label_visibility="collapsed",
            )
            slab = _calc_gst_slab(slab_taxable, rate, tax_type)
            tax_slabs[str(rate)] = slab
            slab_taxable_sum += slab["taxable"]
            total_cgst += slab["cgst"]
            total_sgst += slab["sgst"]
            total_igst += slab["igst"]
            if tax_type == "IGST":
                t3.markdown(f"{slab['igst']:,.2f}")
                t4.markdown("—")
            else:
                t3.markdown(f"{slab['cgst']:,.2f}")
                t4.markdown(f"{slab['sgst']:,.2f}")

        total_tax = round(total_cgst + total_sgst + total_igst, 2)
        total_invoice_value = round(float(line_total or 0) + total_tax, 2)

        m1, m2, m3 = st.columns(3)
        m1.metric("Total tax", f"Rs {total_tax:,.2f}")
        m2.metric("Total invoice value", f"Rs {total_invoice_value:,.2f}")
        m3.metric("Slab taxable total", f"Rs {slab_taxable_sum:,.2f}")

        remarks = st.text_area("Remarks", height=80)

        p1, p2, p3, p4 = st.columns(4)
        payment_status = p1.selectbox("Status", PAYMENT_STATUSES)
        payment_method = p2.selectbox("Method", EXPENSE_PAY_METHODS)
        payment_mode = p3.selectbox("Mode", PAYMENT_MODES)
        paid_from = p4.text_input("From")

        bill_upload = st.file_uploader("Bill / Invoice upload", key="finance_expense_doc")

        if payment_method == "Petty Cash" and project_name:
            st.caption(f"Available petty cash for site: Rs {get_petty_cash_balance(project_name):,.2f}")

        if st.form_submit_button("SUBMIT EXPENSE", type="primary", width="stretch"):
            if not supplier.strip():
                st.error("Supplier is required.")
            elif not exp_head:
                st.error("Please select Exp / Purchase head.")
            else:
                lines = _parse_expense_line_items(form_prefix)
                taxable_amount = _line_items_total(form_prefix)
                submit_tax_slabs = {}
                submit_cgst = submit_sgst = submit_igst = 0.0
                for rate in GST_RATES:
                    slab_taxable = float(st.session_state.get(f"{form_prefix}_slab_{rate}", 0) or 0)
                    slab = _calc_gst_slab(slab_taxable, rate, tax_type)
                    submit_tax_slabs[str(rate)] = slab
                    submit_cgst += slab["cgst"]
                    submit_sgst += slab["sgst"]
                    submit_igst += slab["igst"]
                submit_total_tax = round(submit_cgst + submit_sgst + submit_igst, 2)
                submit_total = round(float(taxable_amount or 0) + submit_total_tax, 2)
                funding_source = "Petty Cash" if payment_method == "Petty Cash" else "Company Fund"

                if not lines:
                    st.error("Add at least one item line with Qty and Rate.")
                elif taxable_amount <= 0:
                    st.error("Taxable amount from line items must be greater than zero.")
                elif submit_total <= 0:
                    st.error("Total invoice value must be greater than zero.")
                elif funding_source == "Petty Cash" and not project_name:
                    st.error("Project is required for petty cash expenses.")
                elif (
                    funding_source == "Petty Cash"
                    and project_name
                    and submit_total > get_petty_cash_balance(project_name)
                ):
                    st.error(f"Petty cash balance for this project is Rs {get_petty_cash_balance(project_name):,.2f}.")
                else:
                    invoice_id = generate_id("EXP", "expense_invoices")
                    transaction_id = generate_id("FIN", "finance_transactions")
                    doc_path = _save_upload(bill_upload, "uploads/finance", invoice_id)
                    conn = get_conn()
                    pinv_no = save_expense_invoice(
                        conn,
                        {
                            "invoice_id": invoice_id,
                            "finance_transaction_id": transaction_id,
                            "expense_date": expense_date.strftime(DATE_FMT),
                            "supplier": supplier.strip(),
                            "invoice_no": invoice_no.strip(),
                            "project_name": project_name or "",
                            "exp_type": exp_type,
                            "taxable_amount": float(taxable_amount),
                            "tax_type": tax_type,
                            "total_cgst": submit_cgst,
                            "total_sgst": submit_sgst,
                            "total_igst": submit_igst,
                            "total_tax": submit_total_tax,
                            "total_invoice_value": submit_total,
                            "remarks": remarks.strip(),
                            "payment_status": payment_status,
                            "payment_method": payment_method,
                            "payment_mode": payment_mode,
                            "paid_from": paid_from.strip(),
                            "bill_upload": doc_path,
                            "tax_slabs": submit_tax_slabs,
                            "created_by": _current_user(),
                            "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        },
                        lines,
                    )
                    fin_doc_no = insert_finance_transaction(
                        conn,
                        {
                            "transaction_id": transaction_id,
                            "transaction_type": "expense_voucher",
                            "transaction_date": expense_date.strftime(DATE_FMT),
                            "project_name": project_name or "",
                            "client_name": "",
                            "category_head": exp_head or exp_type,
                            "pay_to_type": "Vendor",
                            "pay_to_name": supplier.strip(),
                            "amount": submit_total,
                            "payment_mode": payment_mode,
                            "funding_source": funding_source,
                            "reference_number": invoice_no.strip() or invoice_id,
                            "remarks": remarks.strip()
                            or f"{exp_type} | Status: {payment_status} | From: {paid_from.strip()}",
                            "document_upload": doc_path,
                            "status": FINANCE_STATUS_SUBMITTED,
                            "submitted_by": _current_user(),
                        },
                    )
                    conn.commit()
                    conn.close()
                    st.success(
                        f"Purchase invoice submitted: {pinv_no} (approval: Accounts Manager → Finance → Posted)"
                    )
                    st.rerun()

    if not embedded:
        st.markdown("#### Recent expenses")
        recent = load_expense_invoices(limit=50)
        if recent.empty:
            st.info("No expense invoices recorded yet.")
        else:
            st.dataframe(recent, width="stretch", hide_index=True)


def _render_payment_out_tab(clients, projects, payment_heads, embedded=False, preset_head=None):
    if not embedded:
        st.markdown("### Payment Out")
    employee_options = load_employee_options()
    employee_labels = [f"{eid} - {ename}" for eid, ename in employee_options]
    subcontractors = [""] + load_subcontractor_names()
    with st.form("finance_payment_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        transaction_date = c1.date_input("Date")
        if preset_head is not None:
            payment_head = preset_head
            c2.text_input("Payment Head", value=preset_head or "—", disabled=True)
        else:
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


def _render_cash_receipt_tab(clients, projects, embedded=False, preset_head=None):
    if not embedded:
        st.markdown("### Cash Receipt")
    with st.form("finance_receipt_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        transaction_date = c1.date_input("Date")
        if preset_head is not None:
            receipt_category = preset_head
            c2.text_input("Receipt Type", value=preset_head or "—", disabled=True)
        else:
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


def _render_petty_issue_tab(projects, embedded=False, preset_head=None):
    if not embedded:
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
                    preset_head or "Petty Cash",
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
        row = df[df["transaction_id"] == transaction_id].iloc[0]
        amt = float(row.get("amount") or 0)
        is_payment = str(row.get("transaction_type", "")).lower() in {"payment out", "payment_out"}
        md_limit = get_supplier_payment_md_limit()
        if (
            status == FINANCE_STATUS_ACCOUNTS_CHECKED
            and is_payment
            and amt > md_limit
            and not _can_md_action()
        ):
            st.error(f"Payment above Rs {md_limit:,.0f} requires MD approval.")
            return
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
    st.markdown("#### Finance transaction queues")
    st.caption(
        "Purchase invoice: Accounts Entry → Accounts Manager Verification → Finance (MD) Approval → Posted to Ledger. "
        "Supplier payment: Executive → Manager → MD (above limit) → Settled."
    )

    submitted_df = _approval_queue_df(FINANCE_STATUS_SUBMITTED)
    if not submitted_df.empty:
        st.markdown("#### Pending Accounts Check")
        st.dataframe(submitted_df, width="stretch", hide_index=True)
        _render_approval_actions(
            submitted_df,
            FINANCE_STATUS_SUBMITTED,
            FINANCE_STATUS_ACCOUNTS_CHECKED,
            "ACCOUNTS CHECKED",
            _can_accounts_verify(),
            need_reason_on_reject=True,
        )
    elif _can_accounts_verify():
        st.info("No transactions pending accounts check.")

    accounts_df = _approval_queue_df(FINANCE_STATUS_ACCOUNTS_CHECKED)
    if not accounts_df.empty:
        st.markdown("#### Pending Finance / MD Approval")
        md_limit = get_supplier_payment_md_limit()
        st.caption(f"Supplier payments above Rs {md_limit:,.0f} require MD approval.")
        st.dataframe(accounts_df, width="stretch", hide_index=True)
        _render_approval_actions(
            accounts_df,
            FINANCE_STATUS_ACCOUNTS_CHECKED,
            FINANCE_STATUS_MD_APPROVED,
            "FINANCE / MD APPROVED",
            _can_md_action() or is_accounts_manager(_current_role()),
            need_reason_on_reject=True,
        )
    elif _can_md_action() or is_accounts_manager(_current_role()):
        st.info("No transactions pending finance approval.")

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


def _payroll_staff_select_options():
    options = [("", "Select employee")]
    for row in load_payroll_staff_options():
        if len(row) >= 3:
            eid, ename, etype = row[0], row[1], row[2]
            options.append((eid, f"{eid} - {ename} ({etype})"))
        else:
            eid, ename = row[0], row[1]
            options.append((eid, f"{eid} - {ename}"))
    return options


def _render_staff_advance_tab(embedded=False, entry_only=False, verify_only=False, preset_head=None):
    if not embedded and not verify_only:
        st.markdown("### Staff Advance")
        st.caption(
            "Create and pay employee advances here. Payroll only shows advance balance and deductions (read-only)."
        )
    staff_options = _payroll_staff_select_options()
    if not verify_only and len(staff_options) <= 1:
        st.info("Add Monthly Staff or Daily Wage Staff in Employee Management first.")
        if entry_only or embedded:
            return
    if verify_only:
        pass
    elif not verify_only:
        if not embedded:
            with st.expander("Add payment head (optional)", expanded=False):
                new_head = st.text_input("New Head of Account", key="fin_adv_new_head")
                if st.button("ADD HEAD", key="fin_adv_add_head"):
                    if new_head.strip():
                        conn = get_conn()
                        conn.execute("INSERT OR IGNORE INTO payment_heads(head_name) VALUES(?)", (new_head.strip(),))
                        conn.commit()
                        conn.close()
                        st.success("Head added.")
                        st.rerun()

        payment_heads = [""] + load_lookup("payment_heads", "head_name")
        is_site_role = _is_site_role()

        with st.form("finance_staff_advance_create", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            employee_id = c1.selectbox(
                "Employee *",
                [eid for eid, _ in staff_options],
                format_func=lambda eid: dict(staff_options).get(eid, "Select employee"),
                key="fin_adv_employee_id",
            )
            employee_name = (
                dict(staff_options).get(employee_id, "").split(" - ", 1)[-1].rsplit(" (", 1)[0] if employee_id else ""
            )
            advance_date = c2.date_input("Advance date *", key="fin_adv_date")
            amount = c3.number_input("Advance amount (Rs) *", min_value=0.0, step=100.0, key="fin_adv_amount")
            funding_source = c4.selectbox("Funding source *", FUNDING_SOURCES, key="fin_adv_funding")

            d1, d2, d3, d4 = st.columns(4)
            project_name = d1.selectbox(
                "Project/Site (for petty cash)", [""] + load_project_names(), key="fin_adv_project"
            )
            if preset_head is not None:
                payment_head = preset_head
                d2.text_input("Head of Account", value=preset_head or "—", disabled=True)
            else:
                payment_head = d2.selectbox("Head of Account *", payment_heads, key="fin_adv_head")
            payment_mode = d3.selectbox("Payment mode", PAYMENT_MODES, key="fin_adv_mode")
            reason = d4.text_input("Reason", key="fin_adv_reason")
            remarks = st.text_input("Remarks", key="fin_adv_remarks")

            submit_label = "PAY ADVANCE (PETTY CASH)" if is_site_role else "SUBMIT STAFF ADVANCE"
            if st.form_submit_button(submit_label, type="primary", width="stretch"):
                if not employee_id:
                    st.error("Select employee.")
                elif not payment_head:
                    st.error(HEAD_REQUIRED_MSG)
                elif amount <= 0:
                    st.error("Amount must be greater than zero.")
                elif (funding_source == "Petty Cash" or is_site_role) and not project_name:
                    st.error("Select Project/Site for petty cash advance.")
                elif (funding_source == "Petty Cash" or is_site_role) and amount > float(
                    get_petty_cash_balance(project_name) or 0
                ):
                    st.error(f"Petty cash balance for {project_name} is Rs {get_petty_cash_balance(project_name):,.2f}.")
                else:
                    if is_site_role:
                        funding_source = "Petty Cash"
                        payment_status = "Paid"
                    else:
                        payment_status = "Pending"
                    aid = save_staff_advance(
                        employee_id,
                        employee_name,
                        advance_date.strftime(DATE_FMT),
                        amount,
                        payment_mode=payment_mode,
                        reason=reason,
                        remarks=remarks,
                        funding_source=funding_source,
                        project_name=project_name if funding_source == "Petty Cash" else "",
                        payment_head=payment_head,
                        created_by=_current_user(),
                        payment_status=payment_status,
                    )
                    if is_site_role:
                        conn = get_conn()
                        insert_finance_transaction(
                            conn,
                            {
                                "transaction_id": generate_id("FIN", "finance_transactions"),
                                "transaction_type": "petty_cash_issue",
                                "transaction_date": advance_date.strftime(DATE_FMT),
                                "project_name": project_name,
                                "client_name": "",
                                "category_head": payment_head or "Staff Advance",
                                "pay_to_type": "Employee",
                                "pay_to_name": employee_name,
                                "amount": float(amount),
                                "payment_mode": payment_mode,
                                "funding_source": "Petty Cash",
                                "reference_number": aid,
                                "remarks": remarks or "Staff advance paid (petty cash).",
                                "document_upload": "",
                                "status": FINANCE_STATUS_SETTLED,
                                "submitted_by": _current_user(),
                                "submitted_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            },
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"Staff advance paid from petty cash. ID: {aid}")
                    else:
                        st.success(f"Staff advance submitted. ID: {aid}")
                    st.rerun()

    if entry_only:
        return

    pending = list_staff_advances(payment_status="Pending")
    if not pending.empty:
        st.markdown("#### Pending approval")
        st.dataframe(
            pending[
                [
                    "advance_id",
                    "employee_name",
                    "advance_date",
                    "amount",
                    "reason",
                    "payment_mode",
                    "remarks",
                    "created_by",
                ]
            ],
            width="stretch",
            hide_index=True,
        )
        if _can_accounts_action() or _can_md_action():
            approve_labels = {
                f"{r['advance_id']} | {r['employee_name']} | Rs {float(r['amount']):,.0f}": r["advance_id"]
                for _, r in pending.iterrows()
            }
            pick_label = st.selectbox(
                "Select to approve",
                list(approve_labels.keys()),
                key="fin_adv_approve_pick",
            )
            if st.button("APPROVE ADVANCE", type="primary", key="fin_adv_approve_btn"):
                update_staff_advance_status(
                    approve_labels[pick_label],
                    "Approved",
                    actor=_current_user(),
                    approved_by=_current_user(),
                )
                st.success("Advance approved. Ready for payment.")
                st.rerun()

    approved = list_staff_advances(payment_status="Approved")
    if not approved.empty:
        st.markdown("#### Approved — pay advance")
        st.dataframe(
            approved[
                ["advance_id", "employee_name", "advance_date", "amount", "reason", "approved_by"]
            ],
            width="stretch",
            hide_index=True,
        )
        if _can_accounts_action():
            pay_pick = st.selectbox(
                "Select to pay",
                approved["advance_id"].tolist(),
                key="fin_adv_pay_pick",
            )
            pay_mode = st.selectbox("Payment mode", PAYMENT_MODES, key="fin_adv_pay_mode")
            if st.button("MARK ADVANCE PAID", type="primary", key="fin_adv_pay_btn"):
                update_staff_advance_status(pay_pick, "Paid", actor=_current_user(), payment_mode=pay_mode)
                # If it was funded from petty cash, record petty issue for audit/balance
                row = approved[approved["advance_id"] == pay_pick].iloc[0].to_dict()
                if str(row.get("funding_source") or "") == "Petty Cash" and (row.get("project_name") or ""):
                    conn = get_conn()
                    insert_finance_transaction(
                        conn,
                        {
                            "transaction_id": generate_id("FIN", "finance_transactions"),
                            "transaction_type": "petty_cash_issue",
                            "transaction_date": str(row.get("advance_date") or datetime.now().strftime(DATE_FMT)),
                            "project_name": row.get("project_name") or "",
                            "client_name": "",
                            "category_head": row.get("payment_head") or "Staff Advance",
                            "pay_to_type": "Employee",
                            "pay_to_name": row.get("employee_name") or "",
                            "amount": float(row.get("amount") or 0),
                            "payment_mode": pay_mode,
                            "funding_source": "Petty Cash",
                            "reference_number": pay_pick,
                            "remarks": (row.get("remarks") or "") or "Staff advance paid (petty cash).",
                            "document_upload": "",
                            "status": FINANCE_STATUS_SETTLED,
                            "submitted_by": _current_user(),
                            "submitted_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        },
                    )
                    conn.commit()
                    conn.close()
                st.success("Advance marked as paid. Balance updated for payroll deduction.")
                st.rerun()

    if not embedded:
        st.markdown("#### Staff advance register")
        all_adv = list_staff_advances()
        if all_adv.empty:
            st.info("No staff advances recorded yet.")
        else:
            st.dataframe(all_adv, width="stretch", hide_index=True)


def _render_finance_entry_form(entry_type, category_head, clients, projects, expense_heads, payment_heads):
    """Show only the fields required for the selected transaction type + head."""
    if entry_type == "expense_voucher":
        st.info("Fill supplier invoice, item lines, GST, and payment details below.")
        _render_expense_voucher_tab(clients, projects, expense_heads, embedded=True, preset_head=category_head)
    elif entry_type == "payment_out":
        st.info("Enter payment details for the selected payment head.")
        _render_payment_out_tab(clients, projects, payment_heads, embedded=True, preset_head=category_head)
    elif entry_type == "cash_receipt":
        st.info("Enter cash receipt details.")
        _render_cash_receipt_tab(clients, projects, embedded=True, preset_head=category_head)
    elif entry_type == "petty_cash_issue":
        st.info("Issue petty cash float to site staff for the selected head.")
        _render_petty_issue_tab(projects, embedded=True, preset_head=category_head)
    elif entry_type == "staff_advance":
        st.info("Create staff advance for the selected payment head.")
        _render_staff_advance_tab(embedded=True, entry_only=True, preset_head=category_head)


def _render_verification_section():
    st.markdown("### Verification & Approval")
    st.caption("Accounts verify → MD approves → Accounts settles. All types in one queue.")

    role = _current_role()
    if not (_can_accounts_verify() or _can_md_action()):
        st.warning("Verification and approval actions are for Accounts and MD only.")
    else:
        _render_approvals_tab()

    if _can_accounts_verify() or _can_md_action():
        st.markdown("#### Staff advance verification")
        _render_staff_advance_tab(embedded=True, verify_only=True)


def _render_finance_register():
    st.markdown("### Finance Register")
    reg_type = st.selectbox(
        "Show register",
        ["All transactions", "Expense invoices", "Pending only", "Settled only"],
        key="fin_register_filter",
    )
    if reg_type == "Expense invoices":
        df = load_expense_invoices(limit=500)
        if df.empty:
            st.info("No expense invoices yet.")
        else:
            st.dataframe(df, width="stretch", hide_index=True)
            if "invoice_id" in df.columns:
                from modules.document_pdfs import generate_purchase_invoice_pdf

                inv_labels = {
                    f"{row.get('supplier', '')} | {row.get('invoice_no', '')} | {row.get('expense_date', '')}": row[
                        "invoice_id"
                    ]
                    for _, row in df.iterrows()
                }
                inv_pick = st.selectbox("Download purchase invoice PDF", [""] + list(inv_labels.keys()), key="fin_inv_pdf")
                if inv_pick and st.button("Generate invoice PDF", key="fin_inv_pdf_btn"):
                    try:
                        pdf_bytes = generate_purchase_invoice_pdf(inv_labels[inv_pick])
                        st.download_button(
                            "Download PDF",
                            data=pdf_bytes,
                            file_name=f"purchase_invoice_{inv_labels[inv_pick]}.pdf",
                            mime="application/pdf",
                            key="fin_inv_pdf_dl",
                        )
                    except Exception as exc:
                        st.error(str(exc))
            st.markdown("#### Vendor bill workflow")
            inv_wf = {
                f"{row.get('document_no') or row.get('invoice_id')} | {row.get('supplier', '')} | {row.get('status', '')}": row[
                    "invoice_id"
                ]
                for _, row in df.iterrows()
            }
            wf_pick = st.selectbox("Select invoice for approval", [""] + list(inv_wf.keys()), key="vendor_bill_wf")
            if wf_pick:
                from modules.approval_workflow import normalize_status
                from modules.workflow_ui import render_workflow_action_panel, render_workflow_status_steps

                invoice_id = inv_wf[wf_pick]
                inv_row = df[df["invoice_id"] == invoice_id].iloc[0]
                status = normalize_status(inv_row.get("status"), "vendor_bill")
                render_workflow_status_steps(status)
                if render_workflow_action_panel("vendor_bill", invoice_id, status, key_prefix="vbl"):
                    st.rerun()
        return

    status = None
    if reg_type == "Pending only":
        status = FINANCE_STATUS_SUBMITTED
    elif reg_type == "Settled only":
        status = FINANCE_STATUS_SETTLED
    df = load_finance_transactions(status=status, limit=500)
    if df.empty:
        st.info("No finance transactions yet.")
        return
    df["transaction_type"] = df["transaction_type"].map(
        lambda value: FINANCE_TYPE_LABELS.get(value, value)
    )
    st.dataframe(df, width="stretch", hide_index=True)


def _render_register_tab():
    _render_finance_register()


def page_finance_accounts_hub(entry_type=None):
    """Expense voucher, payment out, receipt, petty issue, and staff advance."""
    entry_type = entry_type or st.session_state.pop("_finance_hub_entry_type", None)
    titles = {
        "expense_voucher": "Purchase / Expense Invoice",
        "payment_out": "Payments",
        "cash_receipt": "Receipts",
        "petty_cash_issue": "Petty Cash Issue",
        "staff_advance": "Staff Advance",
    }
    st.markdown(f"#### {titles.get(entry_type, 'Payments & Receipts')}")
    st.caption("Select account head, then complete the form.")
    clients = [""] + load_client_names()
    projects = [""] + load_project_names()
    expense_heads = [""] + load_lookup("expense_heads", "head_name")
    payment_heads = [""] + load_lookup("payment_heads", "head_name")
    allowed = _allowed_entry_types()
    if entry_type and entry_type in allowed:
        allowed = [entry_type]
    if not allowed:
        st.warning("No payment types are available for your role.")
        return
    labels = [FINANCE_ENTRY_TYPES[k] for k in allowed]
    keys = allowed
    if len(keys) == 1:
        entry_type = keys[0]
        st.caption(f"Transaction: **{labels[0]}**")
        heads, head_label = _heads_for_entry_type(entry_type, expense_heads, payment_heads)
        head = st.selectbox(head_label, heads, key="fin_hub_head")
    else:
        c1, c2 = st.columns(2)
        with c1:
            pick = st.selectbox("Transaction type", labels, key="fin_hub_type_label")
        entry_type = keys[labels.index(pick)]
        heads, head_label = _heads_for_entry_type(entry_type, expense_heads, payment_heads)
        with c2:
            head = st.selectbox(head_label, heads, key="fin_hub_head")
    if not head:
        st.warning(HEAD_REQUIRED_MSG)
        return
    _render_finance_entry_form(entry_type, head, clients, projects, expense_heads, payment_heads)


def page_finance():
    from modules.finance_workflow import page_finance_workflow

    page_finance_workflow()
