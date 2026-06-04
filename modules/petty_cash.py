"""Petty Cash Fund Management — dashboard, requests, issues, expenses, reports."""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

from modules.approval_workflow import normalize_status
from modules.database import DATE_FMT, DATE_INPUT_FMT, load_employee_options, load_project_names
from modules.pages import _save_upload
from modules.pdf_templates import PdfDocument
from modules.petty_cash_db import (
    ATTACHMENT_TYPES,
    EXPENSE_EDITABLE,
    FUND_EDITABLE,
    PAYMENT_MODES,
    ensure_petty_cash_schema,
    expense_has_attachments,
    get_expense,
    get_fund_request,
    get_petty_balance,
    get_project_petty_metrics,
    link_fund_request_payment_voucher,
    list_expense_attachments,
    list_expenses,
    list_fund_requests,
    load_expense_categories,
    load_petty_cash_audit,
    load_project_dashboard,
    owner_dashboard_metrics,
    report_balance,
    report_employee_wise,
    report_expense_by_category,
    report_fund_request_history,
    report_ledger,
    report_project_wise,
    save_expense,
    save_fund_issue,
    save_fund_request,
    transition_expense,
)
from modules.roles import (
    can_approve_payments,
    can_prepare_workflow,
    can_settle_finance,
    can_verify_finance,
    is_management,
    is_site_role,
    is_super_admin,
)
from modules.workflow_ui import render_workflow_action_panel, render_workflow_status_steps

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PETTY_CSS = os.path.join(BASE_DIR, "styles", "petty_cash.css")


def _actor() -> str:
    return st.session_state.get("user_name", "User")


def _role() -> str:
    return st.session_state.get("user_role", "Admin")


def _inject_petty_css() -> None:
    if os.path.isfile(PETTY_CSS):
        with open(PETTY_CSS, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        @media (max-width: 768px) {
          .petty-metric-row [data-testid="column"] { min-width: 100% !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _parse_date(raw: str | None):
    if not raw:
        return datetime.now().date()
    try:
        return datetime.strptime(raw, DATE_FMT).date()
    except ValueError:
        return datetime.now().date()


def can_request_fund() -> bool:
    return is_site_role(_role()) or is_super_admin(_role()) or is_management(_role())


def can_issue_fund() -> bool:
    return can_settle_finance(_role()) or can_verify_finance(_role()) or is_super_admin(_role())


def can_enter_expense() -> bool:
    return is_site_role(_role()) or is_super_admin(_role())


def can_verify_expense() -> bool:
    return can_verify_finance(_role()) or is_super_admin(_role())


def can_final_approve_expense() -> bool:
    return can_approve_payments(_role()) or is_management(_role()) or is_super_admin(_role())


def can_view_owner_section() -> bool:
    return is_super_admin(_role()) or is_management(_role())


def _metric_row(metrics: dict, keys: list[tuple[str, str]]) -> None:
    cols = st.columns(len(keys))
    for col, (label, key) in zip(cols, keys):
        val = metrics.get(key, 0)
        if isinstance(val, float):
            col.metric(label, f"Rs {val:,.0f}")
        else:
            col.metric(label, val)


def _render_dashboard() -> None:
    st.markdown("### Petty Cash Dashboard")
    st.caption("Project-wise fund issued, expenses, pending verification, and balance in hand.")
    df = load_project_dashboard()
    if df.empty:
        st.info("No petty cash activity yet. Issue fund or create a fund request to begin.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    projects = [""] + df["Project"].tolist()
    pick = st.selectbox("Project detail", projects, key="pc_dash_proj")
    if pick:
        m = get_project_petty_metrics(pick)
        st.markdown(f"#### {pick}")
        _metric_row(
            m,
            [
                ("Fund Issued", "fund_issued"),
                ("Submitted", "expenses_submitted"),
                ("Approved", "expenses_approved"),
                ("Pending Verify", "pending_verification"),
                ("Balance", "balance_in_hand"),
            ],
        )


def _render_owner_section() -> None:
    if not can_view_owner_section():
        return
    st.markdown("### Owner / MD Overview")
    om = owner_dashboard_metrics()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Issued", f"Rs {om['total_issued']:,.0f}")
    c2.metric("Approved Expenses", f"Rs {om['total_expenses']:,.0f}")
    c3.metric("Submitted (open)", f"Rs {om['expenses_submitted']:,.0f}")
    c4.metric("Pending Approvals", om["pending_approvals"])
    c5.metric("Balance in Hand", f"Rs {om['balance_in_hand']:,.0f}")
    st.dataframe(load_project_dashboard(), use_container_width=True, hide_index=True)


def _render_fund_request_form(request_id: str | None = None) -> None:
    row = get_fund_request(request_id) if request_id else None
    if row and (row.get("status") or "Draft") not in FUND_EDITABLE:
        st.warning(f"Request is **{row.get('status')}** and cannot be edited.")
        return
    defaults = row or {}
    parent_options = [""]
    if defaults.get("project_name"):
        approved = list_fund_requests(project=defaults["project_name"])
        if not approved.empty:
            parent_options += [
                f"{r.document_no or r.request_id} — {r.status}"
                for _, r in approved.iterrows()
                if r.request_id != request_id
            ]

    with st.form("pc_fund_req" if not request_id else f"pc_fund_edit_{request_id}"):
        c1, c2 = st.columns(2)
        req_date = c1.date_input(
            "Request date",
            value=_parse_date(defaults.get("request_date")),
            format=DATE_INPUT_FMT,
        )
        projects = [""] + load_project_names()
        proj_idx = projects.index(defaults["project_name"]) if defaults.get("project_name") in projects else 0
        project = c2.selectbox("Project", projects, index=proj_idx)
        c1, c2 = st.columns(2)
        amount = c1.number_input(
            "Amount requested",
            min_value=0.0,
            step=500.0,
            value=float(defaults.get("amount_requested") or 0),
        )
        requested_by = c2.text_input("Requested by", value=defaults.get("requested_by") or _actor())
        purpose = st.text_input("Purpose", value=defaults.get("purpose") or "")
        remarks = st.text_area("Remarks", value=defaults.get("remarks") or "")
        parent_pick = st.selectbox(
            "Replenishment — link to prior fund request (optional)",
            parent_options,
            help="Use when requesting top-up because balance is low.",
        )
        parent_id = ""
        if parent_pick and " — " in parent_pick:
            parent_id = parent_pick.split(" — ", 1)[0].split(" ", 1)[0]
            if parent_id.startswith("PCFR"):
                pass
            else:
                fr = list_fund_requests()
                if not fr.empty:
                    match = fr[fr["document_no"] == parent_pick.split(" — ", 1)[0]]
                    if not match.empty:
                        parent_id = match.iloc[0]["request_id"]

        if st.form_submit_button("Save request", type="primary"):
            try:
                rid = save_fund_request(
                    {
                        "request_id": request_id,
                        "request_date": req_date,
                        "project_name": project,
                        "requested_by": requested_by,
                        "amount_requested": amount,
                        "purpose": purpose,
                        "remarks": remarks,
                        "parent_request_id": parent_id,
                    },
                    _actor(),
                )
                st.success(f"Saved fund request **{rid}**.")
                st.session_state["pc_fund_selected"] = rid
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def _render_fund_request_detail(request_id: str) -> None:
    row = get_fund_request(request_id)
    if not row:
        st.error("Fund request not found.")
        return
    st.markdown(f"### {row.get('document_no') or request_id}")
    status = normalize_status(row.get("status"), "petty_cash_fund_request")
    st.caption(
        f"**{status}** · {row.get('project_name')} · Rs {float(row.get('amount_requested') or 0):,.2f}"
    )
    render_workflow_status_steps(status)
    if render_workflow_action_panel(
        "petty_cash_fund_request",
        request_id,
        status,
        key_prefix=f"pcfr_{request_id}",
        show_payment_ref=True,
    ):
        st.rerun()

    if row.get("payment_voucher_id"):
        st.info(f"Linked payment voucher: `{row['payment_voucher_id']}`")

    c1, c2 = st.columns(2)
    if c1.button("Link Petty Cash Payment Voucher", key=f"link_pv_{request_id}"):
        st.session_state["pc_link_voucher_request"] = request_id
    if st.session_state.get("pc_link_voucher_request") == request_id:
        vid = st.text_input("Payment voucher ID (type: Petty Cash Payment)", key=f"pv_id_{request_id}")
        if st.button("Save link", key=f"save_pv_{request_id}"):
            if vid.strip():
                link_fund_request_payment_voucher(request_id, vid.strip(), _actor())
                st.success("Linked.")
                st.session_state.pop("pc_link_voucher_request", None)
                st.rerun()

    if status in FUND_EDITABLE:
        with st.expander("Edit request"):
            _render_fund_request_form(request_id)

    audit = load_petty_cash_audit("fund_request", request_id)
    if not audit.empty:
        with st.expander("Audit log"):
            st.dataframe(audit, use_container_width=True, hide_index=True)


def _render_fund_requests_tab() -> None:
    st.markdown("### Petty Cash Fund Requests")
    st.caption("Draft → Prepared → Checked (Accounts) → Approved (Management) → Payment Released → Paid")
    if can_request_fund():
        with st.expander("New fund request / replenishment", expanded=False):
            _render_fund_request_form()
    else:
        st.info("Your role cannot create fund requests.")

    df = list_fund_requests(limit=300)
    if df.empty:
        st.info("No fund requests yet.")
        return
    show_cols = [
        c
        for c in (
            "document_no",
            "request_date",
            "project_name",
            "requested_by",
            "amount_requested",
            "purpose",
            "status",
        )
        if c in df.columns
    ]
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
    labels = {
        f"{r.document_no or r.request_id} | {r.project_name} | Rs {float(r.amount_requested or 0):,.0f} | {r.status}": r.request_id
        for _, r in df.iterrows()
    }
    pick = st.selectbox("Open request", [""] + list(labels.keys()), key="pc_fund_pick")
    if pick:
        _render_fund_request_detail(labels[pick])


def _render_fund_issue_tab() -> None:
    st.markdown("### Petty Cash Fund Issue")
    st.caption("After management approval, accounts issues float to site in-charge. Updates opening balance.")
    if not can_issue_fund():
        st.warning("Only accounts staff can issue petty cash funds.")
        return

    approved = list_fund_requests()
    if not approved.empty:
        approved = approved[approved["status"].isin(["Approved", "Payment Released", "Paid"])]

    staff_labels, staff_map = [], {}
    for eid, ename in load_employee_options():
        lbl = f"{eid} — {ename}" if eid else ename
        staff_labels.append(lbl)
        staff_map[lbl] = (eid, ename)

    with st.form("pc_issue_form"):
        c1, c2, c3 = st.columns(3)
        project = c1.selectbox("Project", [""] + load_project_names())
        if project:
            st.caption(f"Current balance: **Rs {get_petty_balance(project):,.2f}**")
        staff_pick = c2.selectbox("Employee", [""] + staff_labels)
        issue_date = c3.date_input("Issue date", format=DATE_INPUT_FMT)
        amount = c1.number_input("Amount issued", min_value=0.0, step=500.0)
        payment_mode = c2.selectbox("Payment mode", PAYMENT_MODES)
        reference_no = c3.text_input("Reference no.")
        fund_req_id = ""
        if not approved.empty:
            fr_labels = {
                f"{r.document_no} — {r.project_name} — Rs {float(r.amount_requested or 0):,.0f}": r.request_id
                for _, r in approved.iterrows()
            }
            fr_pick = st.selectbox("Linked fund request (optional)", [""] + list(fr_labels.keys()))
            if fr_pick:
                fund_req_id = fr_labels[fr_pick]
        remarks = st.text_area("Remarks")
        if st.form_submit_button("Issue fund", type="primary"):
            eid, ename = staff_map.get(staff_pick, ("", staff_pick.split(" — ", 1)[-1] if staff_pick else ""))
            try:
                iid = save_fund_issue(
                    {
                        "project_name": project,
                        "employee_id": eid,
                        "employee_name": ename,
                        "issue_amount": amount,
                        "issue_date": issue_date,
                        "payment_mode": payment_mode,
                        "reference_no": reference_no,
                        "fund_request_id": fund_req_id,
                        "remarks": remarks,
                    },
                    _actor(),
                )
                st.success(f"Fund issued. ID: **{iid}**. New balance: Rs {get_petty_balance(project):,.2f}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def _collect_attachments(expense_no: str, key_prefix: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for att_type in ATTACHMENT_TYPES:
        up = st.file_uploader(
            f"{att_type} (optional extra)",
            key=f"{key_prefix}_att_{att_type}",
            accept_multiple=True,
        )
        if up:
            files = up if isinstance(up, list) else [up]
            for f in files:
                path = _save_upload(f, "uploads/petty_cash", f"{expense_no}_{att_type}")
                out.append((att_type, path))
    return out


def _render_expense_form(expense_no: str | None = None) -> None:
    row = get_expense(expense_no) if expense_no else None
    if row and (row.get("status") or "Draft") not in EXPENSE_EDITABLE:
        st.warning(f"Expense is **{row.get('status')}** and cannot be edited.")
        return
    defaults = row or {}
    categories = load_expense_categories()

    with st.form("pc_exp_form" if not expense_no else f"pc_exp_edit_{expense_no}"):
        c1, c2, c3 = st.columns(3)
        exp_date = c1.date_input("Date", value=_parse_date(defaults.get("expense_date")), format=DATE_INPUT_FMT)
        projects = [""] + load_project_names()
        proj_idx = projects.index(defaults["project_name"]) if defaults.get("project_name") in projects else 0
        project = c2.selectbox("Project", projects, index=proj_idx)
        if project:
            st.caption(f"Balance: Rs {get_petty_balance(project):,.2f}")
        cat_idx = 0
        if defaults.get("expense_category") in categories:
            cat_idx = categories.index(defaults["expense_category"])
        category = c3.selectbox("Expense category", categories, index=cat_idx)
        c1, c2 = st.columns(2)
        vendor = c1.text_input("Vendor name", value=defaults.get("vendor_name") or "")
        amount = c2.number_input("Amount", min_value=0.0, value=float(defaults.get("amount") or 0))
        description = st.text_area("Description", value=defaults.get("description") or "")
        payment_mode = st.selectbox(
            "Payment mode",
            PAYMENT_MODES,
            index=PAYMENT_MODES.index(defaults["payment_mode"])
            if defaults.get("payment_mode") in PAYMENT_MODES
            else 0,
        )
        st.markdown("**Attachments (required before submit)** — Invoice, Bill, Receipt, Photo")
        if st.form_submit_button("Save expense", type="primary"):
            try:
                eno = save_expense(
                    {
                        "expense_no": expense_no,
                        "expense_date": exp_date,
                        "project_name": project,
                        "expense_category": category,
                        "vendor_name": vendor,
                        "description": description,
                        "amount": amount,
                        "payment_mode": payment_mode,
                    },
                    _actor(),
                )
                st.session_state["pc_exp_selected"] = eno
                st.info("Open the saved expense below to upload attachments, then submit for verification.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def _render_expense_workflow(expense_no: str, row: dict) -> None:
    status = normalize_status(row.get("status"), "petty_cash_expense")
    st.caption(f"Status: **{status}**")
    comment = st.text_input("Comments", key=f"pc_exp_cmt_{expense_no}")

    actions: list[tuple[str, str, bool]] = []
    if status in EXPENSE_EDITABLE and can_enter_expense():
        if expense_has_attachments(expense_no):
            actions.append(("Submit for verification", "Prepared", can_prepare_workflow(_role(), "petty_cash")))
        else:
            st.warning("Add attachments before submitting.")

    if status == "Prepared" and can_verify_expense():
        actions.extend(
            [
                ("Verify (Accounts)", "Checked", True),
                ("Return for correction", "Returned", True),
            ]
        )
    if status == "Checked":
        if can_final_approve_expense():
            actions.append(("Final approve", "Approved", True))
        if can_verify_expense():
            actions.extend(
                [
                    ("Reject", "Rejected", True),
                    ("Return for correction", "Returned", True),
                ]
            )

    for label, target, allowed in actions:
        if not allowed:
            continue
        if st.button(label, key=f"pc_exp_{target}_{expense_no}"):
            ok, msg = transition_expense(expense_no, target, _actor(), comments=comment)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


def _render_expense_detail(expense_no: str) -> None:
    row = get_expense(expense_no)
    if not row:
        st.error("Expense not found.")
        return
    st.markdown(f"### Expense {expense_no}")
    st.caption(
        f"{row.get('project_name')} · {row.get('expense_category')} · Rs {float(row.get('amount') or 0):,.2f}"
    )

    st.markdown("#### Attachments")
    existing = list_expense_attachments(expense_no)
    if not existing.empty:
        st.dataframe(existing[["attachment_type", "file_path", "uploaded_at"]], hide_index=True)
    if (row.get("status") or "Draft") in EXPENSE_EDITABLE:
        new_atts = _collect_attachments(expense_no, f"det_{expense_no}")
        if new_atts and st.button("Save attachments", key=f"save_att_{expense_no}"):
            from modules.database import get_conn
            from modules.petty_cash_db import save_expense_attachments

            conn = get_conn()
            save_expense_attachments(conn, expense_no, new_atts, _actor())
            conn.commit()
            conn.close()
            st.rerun()

    _render_expense_workflow(expense_no, row)

    if (row.get("status") or "Draft") in EXPENSE_EDITABLE:
        with st.expander("Edit expense"):
            _render_expense_form(expense_no)

    audit = load_petty_cash_audit("expense", expense_no)
    if not audit.empty:
        with st.expander("Audit log"):
            st.dataframe(audit, use_container_width=True, hide_index=True)


def _render_expenses_tab() -> None:
    st.markdown("### Petty Cash Expenses")
    st.caption("Site entry → Accounts verification → Final approval. Attachments required.")
    if can_enter_expense():
        with st.expander("New expense", expanded=False):
            _render_expense_form()
    df = list_expenses(limit=300)
    if df.empty:
        st.info("No petty cash expenses yet.")
        return
    cols = [
        c
        for c in (
            "expense_no",
            "expense_date",
            "project_name",
            "expense_category",
            "vendor_name",
            "amount",
            "status",
        )
        if c in df.columns
    ]
    st.dataframe(df[cols], use_container_width=True, hide_index=True)
    labels = {
        f"{r.expense_no} | {r.project_name} | Rs {float(r.amount or 0):,.0f} | {r.status}": r.expense_no
        for _, r in df.iterrows()
    }
    pick = st.selectbox("Open expense", [""] + list(labels.keys()), key="pc_exp_pick")
    if pick:
        _render_expense_detail(labels[pick])


def _render_expense_approval_tab() -> None:
    st.markdown("### Expense Verification & Approval")
    pending = list_expenses(limit=500)
    if pending.empty:
        st.info("No expenses.")
        return
    pending = pending[pending["status"].isin(["Prepared", "Checked"])]
    if pending.empty:
        st.success("No expenses pending verification or final approval.")
        return
    for _, r in pending.iterrows():
        with st.expander(f"{r.expense_no} — {r.status} — Rs {float(r.amount or 0):,.2f}"):
            _render_expense_detail(r.expense_no)


def _pdf_table_report(title: str, df: pd.DataFrame) -> bytes | None:
    if df.empty:
        return None
    doc = PdfDocument()
    doc.add_company_block(title, date_value=datetime.now().strftime(DATE_FMT))
    headers = list(df.columns)
    rows = [[str(v) for v in row] for row in df.itertuples(index=False, name=None)]
    doc.add_data_table(headers, rows)
    doc.add_footer()
    return doc.build()


def _render_reports_tab() -> None:
    st.markdown("### Petty Cash Reports")
    projects = [""] + load_project_names()
    project = st.selectbox("Filter by project (optional)", projects, key="pc_rpt_proj")

    reports = {
        "Petty Cash Ledger": lambda: report_ledger(project or None),
        "Balance Report": report_balance,
        "Expense by Category": lambda: report_expense_by_category(project or None),
        "Project-wise Summary": report_project_wise,
        "Employee-wise Issues": report_employee_wise,
        "Fund Request History": lambda: report_fund_request_history(project or None),
    }
    name = st.selectbox("Report", list(reports.keys()))
    df = reports[name]()
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, file_name=f"{name.replace(' ', '_').lower()}.csv", mime="text/csv")
    pdf = _pdf_table_report(name, df)
    if pdf:
        st.download_button("Download PDF", pdf, file_name=f"{name.replace(' ', '_').lower()}.pdf", mime="application/pdf")


def page_petty_cash(*, initial_tab: str | None = None) -> None:
    ensure_petty_cash_schema()
    _inject_petty_css()
    st.subheader("Petty Cash Fund Management")
    st.caption(
        "Control project-wise petty cash issued to site in-charge; live balance = fund issued − approved expenses."
    )

    tabs = ["Dashboard", "Fund Requests", "Fund Issue", "Expenses", "Expense Approval", "Reports"]
    if can_view_owner_section():
        tabs.append("Owner Overview")

    default_idx = 0
    if initial_tab:
        mapping = {
            "dashboard": 0,
            "request": 1,
            "issue": 2,
            "expense": 3,
            "approval": 4,
            "reports": 5,
            "owner": 6,
        }
        default_idx = mapping.get(initial_tab, 0)

    tab_objs = st.tabs(tabs)
    with tab_objs[0]:
        _render_dashboard()
    with tab_objs[1]:
        _render_fund_requests_tab()
    with tab_objs[2]:
        _render_fund_issue_tab()
    with tab_objs[3]:
        _render_expenses_tab()
    with tab_objs[4]:
        _render_expense_approval_tab()
    with tab_objs[5]:
        _render_reports_tab()
    if can_view_owner_section() and len(tab_objs) > 6:
        with tab_objs[6]:
            _render_owner_section()


def page_petty_cash_dashboard() -> None:
    page_petty_cash(initial_tab="dashboard")


def page_petty_fund_requests() -> None:
    page_petty_cash(initial_tab="request")


def page_petty_expenses() -> None:
    page_petty_cash(initial_tab="expense")


def page_petty_expense_approval() -> None:
    page_petty_cash(initial_tab="approval")
