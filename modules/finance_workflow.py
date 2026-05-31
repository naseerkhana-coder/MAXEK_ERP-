"""Finance & Petty Cash approval workflow — Modules 1–10."""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

from modules.database import (
    BASE_DIR,
    DATE_FMT,
    DATE_INPUT_FMT,
    check_petty_cash_limit,
    duplicate_site_expense_invoice,
    generate_id,
    get_conn,
    get_escalation_rules,
    get_finance_kpi_summary,
    get_project_profit_kpis,
    get_petty_cash_balance,
    get_petty_cash_handler,
    get_project_petty_limit,
    get_site_expense,
    get_supplier_payment_md_limit,
    load_finance_dashboard_table,
    load_budget_vs_actual,
    load_cash_book,
    load_bank_book,
    load_direct_payments,
    load_escalated_finance_items,
    load_finance_audit,
    load_gst_register,
    load_petty_cash_balances,
    load_petty_cash_requests,
    load_project_finance_settings,
    load_project_names,
    load_project_staff_options,
    load_site_expenses,
    load_site_expense_lines,
    log_finance_audit,
    next_document_number,
    post_payment_to_ledger,
    post_site_expense_to_ledger,
    save_finance_setting,
    save_project_finance_settings,
    save_site_expense_lines,
    set_petty_cash_handler,
)
from modules.pages import _save_upload
from modules.roles import (
    can_delete_approved_finance,
    can_settle_finance,
    can_verify_finance,
    is_accounts_manager,
    is_accounts_staff,
    is_management,
    is_site_role as check_site_role,
)

EXPENSE_CATEGORIES = [
    "Material",
    "Labour",
    "Fuel",
    "Transport",
    "Equipment",
    "Accommodation",
    "Site Expense",
    "Office Expense",
    "Other",
]
GST_RATES = [0, 5, 12, 18, 28]
TAX_TYPES = ["CGST+SGST", "IGST"]
PAYMENT_SOURCES = ["Petty Cash", "Cash", "Bank"]
EXPENSE_STATUSES = ["Draft", "Submitted", "Verified", "PM Approved", "Approved", "Rejected", "Returned"]
PETTY_PRIORITIES = ["Normal", "Urgent"]
DIRECT_PAYMENT_TYPES = [
    "Supplier Payment",
    "Subcontractor Payment",
    "Salary Payment",
    "Advance Payment",
    "Utility Payment",
    "Equipment Payment",
]
PAYMENT_METHODS = ["Bank", "Cash", "Cheque", "UPI"]
ITEM_UNITS = ["Nos", "Kg", "Bag", "Meter", "Litre", "Ton", "SQM", "M3"]
DEFAULT_LINE_ITEMS = 1
MAX_LINE_ITEMS = 50
EXPENSE_ENTRY_LABEL = "Expense Entry"


def _user():
    return st.session_state.get("user_name", "User")


def _role():
    return st.session_state.get("user_role", "Admin")


def _is_site():
    return check_site_role(_role())


def _is_accounts():
    return is_accounts_staff(_role())


def _is_accounts_manager():
    return is_accounts_manager(_role())


def _can_verify():
    return can_verify_finance(_role())


def _is_pm():
    return _role() in {"Admin", "Project Manager", "MD", "Super Admin"}


def _is_pm_only():
    """Project Manager approval step (petty cash expense workflow)."""
    return _role() in {"Project Manager", "Admin", "MD", "Super Admin"}


def _is_management():
    return is_management(_role())


def _ts():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _calc_tax(taxable, gst_rate, tax_type):
    taxable = float(taxable or 0)
    rate = float(gst_rate or 0)
    if taxable <= 0 or rate <= 0:
        return 0.0, 0.0, 0.0, 0.0
    total_tax = round(taxable * rate / 100, 2)
    if tax_type == "IGST":
        return 0.0, 0.0, total_tax, total_tax
    half = round(total_tax / 2, 2)
    return half, half, total_tax, total_tax


def _parse_site_expense_lines(prefix="se"):
    lines = []
    for idx in range(_get_line_count(prefix)):
        item = str(st.session_state.get(f"{prefix}_item_{idx}", "") or "").strip()
        hsn = str(st.session_state.get(f"{prefix}_hsn_{idx}", "") or "").strip()
        unit = st.session_state.get(f"{prefix}_unit_{idx}", "Nos")
        qty = float(st.session_state.get(f"{prefix}_qty_{idx}", 0) or 0)
        rate = float(st.session_state.get(f"{prefix}_rate_{idx}", 0) or 0)
        if not item and qty <= 0:
            continue
        taxable = round(qty * rate, 2)
        gst_rate = float(st.session_state.get(f"{prefix}_gst_{idx}", 0) or 0)
        tax_type = st.session_state.get(f"{prefix}_tax_type_{idx}", "CGST+SGST")
        cgst, sgst, igst, line_tax = _calc_tax(taxable, gst_rate, tax_type)
        line_total = round(taxable + line_tax, 2)
        lines.append(
            {
                "item_name": item,
                "hsn_code": hsn,
                "unit": unit,
                "quantity": qty,
                "rate": rate,
                "taxable_amount": taxable,
                "gst_rate": gst_rate,
                "tax_type": tax_type,
                "cgst": cgst,
                "sgst": sgst,
                "igst": igst,
                "line_tax": line_tax,
                "line_total": line_total,
            }
        )
    return lines


def _aggregate_expense_lines(lines):
    subtotal = round(sum(float(l.get("taxable_amount") or 0) for l in lines), 2)
    total_cgst = round(sum(float(l.get("cgst") or 0) for l in lines), 2)
    total_sgst = round(sum(float(l.get("sgst") or 0) for l in lines), 2)
    total_igst = round(sum(float(l.get("igst") or 0) for l in lines), 2)
    total_tax = round(sum(float(l.get("line_tax") or 0) for l in lines), 2)
    grand_total = round(sum(float(l.get("line_total") or 0) for l in lines), 2)
    return {
        "taxable_amount": subtotal,
        "total_cgst": total_cgst,
        "total_sgst": total_sgst,
        "total_igst": total_igst,
        "total_tax": total_tax,
        "total_invoice_value": grand_total,
    }


def _line_count_key(prefix):
    return f"{prefix}_line_count"


def _get_line_count(prefix):
    return max(
        DEFAULT_LINE_ITEMS,
        min(int(st.session_state.get(_line_count_key(prefix), DEFAULT_LINE_ITEMS)), MAX_LINE_ITEMS),
    )


def _reset_expense_line_fields(prefix):
    st.session_state.pop(f"{prefix}_edit_loaded", None)
    st.session_state[_line_count_key(prefix)] = DEFAULT_LINE_ITEMS
    for idx in range(MAX_LINE_ITEMS):
        for suffix in ("item", "hsn", "unit", "qty", "rate", "gst", "tax_type"):
            st.session_state.pop(f"{prefix}_{suffix}_{idx}", None)


def _render_line_item_controls(prefix):
    count_key = _line_count_key(prefix)
    count = _get_line_count(prefix)
    c1, c2, c3 = st.columns([1, 1, 3])
    if c1.button("➕ Add item", key=f"{prefix}_add_line", width="stretch"):
        st.session_state[count_key] = min(count + 1, MAX_LINE_ITEMS)
        st.rerun()
    if count > DEFAULT_LINE_ITEMS and c2.button("➖ Remove last item", key=f"{prefix}_remove_line", width="stretch"):
        st.session_state[count_key] = max(DEFAULT_LINE_ITEMS, count - 1)
        st.rerun()
    c3.caption(f"**{count}** item line(s) shown. Use **Add item** to add more (up to {MAX_LINE_ITEMS}).")


def _render_invoice_line_grid(prefix):
    line_count = _get_line_count(prefix)
    h1, h2, h3, h4, h5, h6, h7, h8, h9 = st.columns([2, 1, 1, 1, 1, 1, 1, 1, 1])
    h1.markdown("**Item**")
    h2.markdown("**HSN**")
    h3.markdown("**Unit**")
    h4.markdown("**Qty**")
    h5.markdown("**Rate**")
    h6.markdown("**Taxable**")
    h7.markdown("**GST %**")
    h8.markdown("**Tax type**")
    h9.markdown("**Total**")

    preview_subtotal = 0.0
    preview_tax = 0.0
    preview_total = 0.0
    for idx in range(line_count):
        r1, r2, r3, r4, r5, r6, r7, r8, r9 = st.columns([2, 1, 1, 1, 1, 1, 1, 1, 1])
        r1.text_input("Item", key=f"{prefix}_item_{idx}", label_visibility="collapsed", placeholder="Item name")
        r2.text_input("HSN", key=f"{prefix}_hsn_{idx}", label_visibility="collapsed")
        r3.selectbox("Unit", ITEM_UNITS, key=f"{prefix}_unit_{idx}", label_visibility="collapsed")
        qty = r4.number_input("Qty", min_value=0.0, step=1.0, key=f"{prefix}_qty_{idx}", label_visibility="collapsed")
        rate = r5.number_input("Rate", min_value=0.0, step=1.0, key=f"{prefix}_rate_{idx}", label_visibility="collapsed")
        taxable = round(float(qty or 0) * float(rate or 0), 2)
        r6.markdown(f"{taxable:,.2f}")
        gst_rate = r7.selectbox("GST", GST_RATES, key=f"{prefix}_gst_{idx}", label_visibility="collapsed")
        tax_type = r8.selectbox("Tax", TAX_TYPES, key=f"{prefix}_tax_type_{idx}", label_visibility="collapsed")
        _, _, _, line_tax = _calc_tax(taxable, gst_rate, tax_type)
        line_total = round(taxable + line_tax, 2)
        r9.markdown(f"**{line_total:,.2f}**")
        if taxable > 0 or str(st.session_state.get(f"{prefix}_item_{idx}", "")).strip():
            preview_subtotal += taxable
            preview_tax += line_tax
            preview_total += line_total
    return preview_subtotal, preview_tax, preview_total


def _prime_site_expense_line_fields(edit_id, prefix="se"):
    if not edit_id:
        return
    load_key = f"{prefix}_edit_loaded"
    if st.session_state.get(load_key) == edit_id:
        return
    row = get_site_expense(edit_id) or {}
    if row.get("project_name"):
        st.session_state[f"{prefix}_project"] = row["project_name"]
    lines_df = load_site_expense_lines(edit_id)
    if lines_df.empty:
        row = get_site_expense(edit_id) or {}
        if float(row.get("taxable_amount") or 0) > 0 or float(row.get("quantity") or 0) > 0:
            lines_df = pd.DataFrame(
                [
                    {
                        "item_name": row.get("description") or "Item",
                        "hsn_code": "",
                        "unit": "Nos",
                        "quantity": row.get("quantity") or 0,
                        "rate": row.get("rate") or 0,
                        "taxable_amount": row.get("taxable_amount") or 0,
                        "gst_rate": row.get("gst_rate") or 0,
                        "tax_type": row.get("tax_type") or "CGST+SGST",
                    }
                ]
            )
    for idx in range(MAX_LINE_ITEMS):
        for suffix in ("item", "hsn", "unit", "qty", "rate", "gst", "tax_type"):
            st.session_state.pop(f"{prefix}_{suffix}_{idx}", None)
    tax_types = TAX_TYPES
    records = lines_df.to_dict("records")
    st.session_state[_line_count_key(prefix)] = max(
        DEFAULT_LINE_ITEMS,
        min(len(records) if records else DEFAULT_LINE_ITEMS, MAX_LINE_ITEMS),
    )
    for idx, line in enumerate(records):
        if idx >= MAX_LINE_ITEMS:
            break
        st.session_state[f"{prefix}_item_{idx}"] = line.get("item_name", "")
        st.session_state[f"{prefix}_hsn_{idx}"] = line.get("hsn_code", "")
        st.session_state[f"{prefix}_unit_{idx}"] = line.get("unit", "Nos")
        st.session_state[f"{prefix}_qty_{idx}"] = float(line.get("quantity") or 0)
        st.session_state[f"{prefix}_rate_{idx}"] = float(line.get("rate") or 0)
        gst_val = int(float(line.get("gst_rate") or 0))
        st.session_state[f"{prefix}_gst_{idx}"] = gst_val if gst_val in GST_RATES else 0
        tt = line.get("tax_type") or "CGST+SGST"
        st.session_state[f"{prefix}_tax_type_{idx}"] = tt if tt in tax_types else "CGST+SGST"
    st.session_state[load_key] = edit_id


def _render_site_expense_lines_table(expense_id, title="Invoice line items"):
    lines = load_site_expense_lines(expense_id)
    if lines.empty:
        row = get_site_expense(expense_id) or {}
        if float(row.get("taxable_amount") or 0) > 0:
            st.markdown(f"#### {title}")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Item": row.get("description") or "Item",
                            "Qty": row.get("quantity"),
                            "Rate": row.get("rate"),
                            "Taxable": row.get("taxable_amount"),
                            "GST %": row.get("gst_rate"),
                            "Tax": row.get("total_tax"),
                            "Total": row.get("total_invoice_value"),
                        }
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        return
    st.markdown(f"#### {title}")
    show = lines.rename(
        columns={
            "item_name": "Item",
            "hsn_code": "HSN",
            "unit": "Unit",
            "quantity": "Qty",
            "rate": "Rate",
            "taxable_amount": "Taxable (Rs)",
            "gst_rate": "GST %",
            "tax_type": "Tax Type",
            "cgst": "CGST",
            "sgst": "SGST",
            "igst": "IGST",
            "line_tax": "Line Tax",
            "line_total": "Line Total",
        }
    )
    cols = [c for c in ["Item", "HSN", "Unit", "Qty", "Rate", "Taxable (Rs)", "GST %", "Tax Type", "CGST", "SGST", "IGST", "Line Tax", "Line Total"] if c in show.columns]
    st.dataframe(show[cols], width="stretch", hide_index=True)
    totals = _aggregate_expense_lines(lines.to_dict("records"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Subtotal", f"Rs {totals['taxable_amount']:,.2f}")
    c2.metric("Total tax", f"Rs {totals['total_tax']:,.2f}")
    c3.metric("CGST / SGST / IGST", f"{totals['total_cgst']:,.2f} / {totals['total_sgst']:,.2f} / {totals['total_igst']:,.2f}")
    c4.metric("Grand total", f"Rs {totals['total_invoice_value']:,.2f}")


def _resolve_upload_path(file_path):
    if not file_path:
        return ""
    raw = str(file_path).strip()
    if os.path.isabs(raw) and os.path.isfile(raw):
        return raw
    abs_path = os.path.join(BASE_DIR, raw.replace("\\", "/"))
    if os.path.isfile(abs_path):
        return abs_path
    return ""


def _render_bill_viewer(file_path, label="Attachment", key_suffix=""):
    abs_path = _resolve_upload_path(file_path)
    if not abs_path:
        st.caption(f"No {label.lower()} uploaded.")
        return
    rel = os.path.relpath(abs_path, BASE_DIR).replace("\\", "/")
    file_name = os.path.basename(abs_path)
    uniq = str(key_suffix or abs(hash(abs_path)))
    with st.expander(f"View {label}", expanded=False):
        st.caption(f"File: `{rel}`")
        ext = os.path.splitext(abs_path)[1].lower()
        with open(abs_path, "rb") as f:
            data = f.read()
        if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
            st.image(data, caption=file_name, width="stretch")
        elif ext == ".pdf":
            try:
                st.pdf(data, height=480)
            except Exception:
                st.info("PDF preview is not available in this browser. Download the file to open it.")
        elif ext in {".txt", ".csv", ".log"}:
            try:
                st.text(data.decode("utf-8", errors="replace")[:8000])
            except Exception:
                st.info("Text preview not available. Download the file to open it.")
        else:
            st.info(f"Preview not available for `{ext or 'this file type'}`. Download to open.")
        st.download_button(
            f"Download {label}",
            data=data,
            file_name=file_name,
            key=f"dl_{uniq}_{label}",
        )


def _render_attachment_slot(existing_path, label, uploader_key, key_suffix=""):
    """Upload field with view option for an already saved file."""
    if existing_path:
        _render_bill_viewer(existing_path, label, key_suffix=f"slot_{key_suffix}")
    else:
        st.caption(f"No {label.lower()} uploaded yet.")
    return st.file_uploader(f"Upload {label}", key=uploader_key)


def _render_audit_trail(entity_type, entity_id):
    audit = load_finance_audit(entity_type, entity_id, limit=50)
    if audit.empty:
        return
    st.markdown("#### Audit trail")
    st.dataframe(
        audit[["action_at", "actor", "action", "old_status", "new_status", "comments"]],
        width="stretch",
        hide_index=True,
    )


def _render_dashboard():
    st.markdown("### Accounts Dashboard")
    st.caption(
        "Summary row shows company totals. Project rows show budget, spend, petty cash, and pending approvals."
    )
    fk = get_finance_kpi_summary()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Cash Balance", f"Rs {fk['cash_balance']:,.0f}")
    c2.metric("Bank Balance", f"Rs {fk['bank_balance']:,.0f}")
    c3.metric("Creditors", f"Rs {fk['creditors']:,.0f}")
    c4.metric("Debtors", f"Rs {fk['debtors']:,.0f}")
    c5.metric("Monthly Expenses", f"Rs {fk['monthly_expenses']:,.0f}")
    p1, p2, p3 = st.columns(3)
    p1.metric("Petty Issued", f"Rs {fk['petty_issued']:,.0f}")
    p2.metric("Petty Utilized", f"Rs {fk['petty_utilized']:,.0f}")
    p3.metric("Pending Verification", fk["petty_pending_verify"])

    profit_df = get_project_profit_kpis()
    if not profit_df.empty:
        st.markdown("#### Project budget & profit")
        st.dataframe(
            profit_df.rename(
                columns={
                    "project_name": "Project",
                    "budget": "Budget (Rs)",
                    "actual_total": "Actual Cost (Rs)",
                    "variance": "Variance (Rs)",
                    "profit": "Profit (Rs)",
                    "utilization_pct": "Budget Used %",
                }
            ),
            width="stretch",
            hide_index=True,
        )

    try:
        dashboard_df = load_finance_dashboard_table()
    except Exception as exc:
        st.error(f"Dashboard could not load: {exc}")
        return

    if dashboard_df.empty:
        st.info("No finance data yet. Add projects and expenses to populate the dashboard.")
        return

    money_cols = [
        "Budget (Rs)",
        "Actual Spend (Rs)",
        "Variance (Rs)",
        "Petty Balance (Rs)",
        "Petty Limit (Rs)",
        "Today's Expense (Rs)",
    ]
    count_cols = [
        "Pending Verify",
        "Pending Approval",
        "Approved",
        "Rejected",
        "Petty Requests",
        "Escalated",
    ]
    col_config = {
        "S.No": st.column_config.TextColumn("S.No", width="small"),
        "Project Name": st.column_config.TextColumn("Project Name", width="medium"),
        "Petty Handler": st.column_config.TextColumn("Petty Handler", width="medium"),
        "Budget Used %": st.column_config.NumberColumn("Budget Used %", format="%.1f"),
        "Status": st.column_config.TextColumn("Status", width="small"),
    }
    for col in money_cols:
        col_config[col] = st.column_config.NumberColumn(col, format="%.2f")
    for col in count_cols:
        col_config[col] = st.column_config.NumberColumn(col, format="%d")

    st.dataframe(
        dashboard_df,
        width="stretch",
        hide_index=True,
        column_config=col_config,
    )


def _staff_select_options(project_name=None):
    options = [("", "Select staff")]
    name_map = {"": ""}
    for row in load_project_staff_options(project_name):
        eid, ename = row[0], row[1]
        etype = row[2] if len(row) > 2 else ""
        proj = row[3] if len(row) > 3 else ""
        name_map[eid] = ename
        label = f"{eid} - {ename}"
        if etype:
            label += f" ({etype})"
        if proj and (not project_name or proj != project_name):
            label += f" — {proj}"
        options.append((eid, label))
    return options, name_map


def _render_petty_cash_request():
    st.markdown("### Module 1 — Petty Cash Request")
    st.caption("Site → Accounts verify → Management approve → Finance release. Balance updates on release.")
    projects = [""] + load_project_names()

    c1, c2 = st.columns(2)
    project = c1.selectbox("Project *", projects, key="pcr_project_pick")
    staff_options, staff_names = _staff_select_options(project)
    staff_ids = [eid for eid, _ in staff_options]
    staff_labels = dict(staff_options)
    if project and len(staff_options) <= 1:
        st.info("No staff found for this project. Assign staff to the project in Employee Management, or pick another project.")

    with st.form("pcr_new", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        req_date = c1.date_input("Date", format=DATE_INPUT_FMT)
        staff_id = c2.selectbox(
            "Staff (Requesting) *",
            staff_ids,
            format_func=lambda eid: staff_labels.get(eid, "Select staff"),
        )
        priority = c3.selectbox("Priority", PETTY_PRIORITIES)
        balance = get_petty_cash_balance(project) if project else 0.0
        handler = get_petty_cash_handler(project) if project else {}
        handler_name = handler.get("staff_name") or "Not assigned"
        st.caption(
            f"Project: **{project or '—'}** · Petty cash handled by: **{handler_name}** · "
            f"Balance in hand: **Rs {balance:,.2f}**"
        )
        c4, c5 = st.columns(2)
        amount = c4.number_input("Requested amount (Rs) *", min_value=0.0, step=500.0)
        reason = c5.text_input("Reason *")
        remarks = st.text_area("Remarks")
        attachment = st.file_uploader("Attachment", key="pcr_attach")
        if st.form_submit_button("SUBMIT REQUEST", type="primary", width="stretch"):
            if not project:
                st.error("Project is required.")
            elif not staff_id:
                st.error("Please select the staff member requesting petty cash.")
            elif amount <= 0:
                st.error("Requested amount must be greater than zero.")
            elif not reason.strip():
                st.error("Reason is required.")
            else:
                staff_name = staff_names.get(staff_id, "")
                rid = generate_id("PCR", "petty_cash_requests")
                doc = _save_upload(attachment, "uploads/finance/petty_requests", rid)
                conn = get_conn()
                conn.execute(
                    """
                    INSERT INTO petty_cash_requests(
                        request_id, request_date, project_name, staff_id, staff_name, requested_by,
                        current_balance, requested_amount, reason, priority, remarks, attachment,
                        status, created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        rid,
                        req_date.strftime(DATE_FMT),
                        project,
                        staff_id,
                        staff_name,
                        _user(),
                        balance,
                        float(amount),
                        reason.strip(),
                        priority,
                        remarks.strip(),
                        doc,
                        "Submitted",
                        _ts(),
                    ),
                )
                log_finance_audit(conn, "petty_cash_request", rid, "Submit", _user(), "", "Submitted", remarks)
                conn.commit()
                conn.close()
                st.success(f"Petty cash request submitted: {rid}")
                st.rerun()

    st.markdown("#### Petty cash balance by project")
    bal_df = load_petty_cash_balances()
    if bal_df.empty:
        st.info("No petty cash balance yet.")
    else:
        st.dataframe(bal_df, width="stretch", hide_index=True)

    st.markdown("#### Request queue")
    df = load_petty_cash_requests(limit=100)
    if df.empty:
        st.info("No petty cash requests yet.")
        return
    if "staff_name" not in df.columns:
        df["staff_name"] = ""
    display_cols = [
        "request_id",
        "request_date",
        "project_name",
        "staff_name",
        "requested_by",
        "requested_amount",
        "priority",
        "status",
        "current_balance",
    ]
    st.dataframe(
        df[[c for c in display_cols if c in df.columns]].rename(
            columns={
                "staff_name": "Staff (Requesting)",
                "requested_by": "Submitted By",
            }
        ),
        width="stretch",
        hide_index=True,
    )

    options = {
        f"{r['request_id']} | {r['project_name']} | {r.get('staff_name') or '—'} | Rs {float(r['requested_amount']):,.0f} | {r['status']}": r[
            "request_id"
        ]
        for _, r in df.iterrows()
        if r["status"] in ("Submitted", "Verified", "Approved")
    }
    if not options:
        return
    pick = st.selectbox("Select request for action", [""] + list(options.keys()), key="pcr_action_pick")
    if not pick:
        return
    rid = options[pick]
    row = df[df["request_id"] == rid].iloc[0].to_dict()
    st.markdown(
        f"**Staff:** {row.get('staff_name') or '—'} · **Submitted by:** {row.get('requested_by') or '—'}"
    )
    st.markdown("#### Attachments")
    _render_bill_viewer(row.get("attachment"), "Request attachment", key_suffix=f"pcr_{rid}")
    comments = st.text_input("Comments", key=f"pcr_comments_{rid}")
    c1, c2, c3, c4 = st.columns(4)
    if _can_verify() and row["status"] == "Submitted" and c1.button("VERIFY", key=f"pcr_verify_{rid}"):
        conn = get_conn()
        conn.execute(
            "UPDATE petty_cash_requests SET status='Verified', verified_by=?, verified_at=? WHERE request_id=?",
            (_user(), _ts(), rid),
        )
        log_finance_audit(conn, "petty_cash_request", rid, "Verify", _user(), "Submitted", "Verified", comments)
        conn.commit()
        conn.close()
        st.success("Verified.")
        st.rerun()
    if _is_management() and row["status"] == "Verified" and c2.button("APPROVE", key=f"pcr_appr_{rid}"):
        conn = get_conn()
        conn.execute(
            "UPDATE petty_cash_requests SET status='Approved', approved_by=?, approved_at=? WHERE request_id=?",
            (_user(), _ts(), rid),
        )
        log_finance_audit(conn, "petty_cash_request", rid, "Approve", _user(), "Verified", "Approved", comments)
        conn.commit()
        conn.close()
        st.success("Approved by management.")
        st.rerun()
    if _is_management() and row["status"] in ("Submitted", "Verified") and c3.button("REJECT", key=f"pcr_rej_{rid}"):
        if not comments.strip():
            st.error("Rejection reason required in comments.")
        else:
            conn = get_conn()
            conn.execute(
                """
                UPDATE petty_cash_requests
                SET status='Rejected', rejection_reason=?, approved_by=?, approved_at=?
                WHERE request_id=?
                """,
                (comments.strip(), _user(), _ts(), rid),
            )
            log_finance_audit(conn, "petty_cash_request", rid, "Reject", _user(), row["status"], "Rejected", comments)
            conn.commit()
            conn.close()
            st.success("Request rejected.")
            st.rerun()
    if _is_accounts_manager() and row["status"] == "Approved" and c4.button("RELEASE AMOUNT", key=f"pcr_rel_{rid}"):
        ok, msg = check_petty_cash_limit(row["project_name"], float(row["requested_amount"] or 0))
        if not ok:
            st.error(msg)
        else:
            conn = get_conn()
            conn.execute(
                """
                UPDATE petty_cash_requests
                SET status='Released', released_by=?, released_at=?, released_amount=requested_amount
                WHERE request_id=?
                """,
                (_user(), _ts(), rid),
            )
            staff_id = str(row.get("staff_id") or "")
            staff_name = str(row.get("staff_name") or "")
            if staff_name:
                set_petty_cash_handler(row["project_name"], staff_id, staff_name, _user())
            log_finance_audit(conn, "petty_cash_request", rid, "Release", _user(), "Approved", "Released", comments)
            conn.commit()
            conn.close()
            st.success(f"Rs {float(row['requested_amount']):,.2f} released. Petty cash balance updated.")
            st.rerun()
    limit = get_project_petty_limit(row.get("project_name", ""))
    handler = get_petty_cash_handler(row.get("project_name", ""))
    if handler.get("staff_name"):
        st.caption(f"Petty cash currently handled by: **{handler['staff_name']}**")
    if limit > 0:
        st.caption(f"Petty cash limit for project: Rs {limit:,.2f}")
    _render_audit_trail("petty_cash_request", rid)


def _save_site_expense(
    status,
    expense_id=None,
    inv_upload=None,
    bill_upload=None,
    sup_upload=None,
    form_values=None,
    key_prefix="se",
    correction_note="",
):
    form = form_values or st.session_state
    project = form.get(f"{key_prefix}_project", "")
    supplier = (form.get(f"{key_prefix}_supplier") or "").strip()
    invoice_no = (form.get(f"{key_prefix}_invoice") or "").strip()
    lines = _parse_site_expense_lines(key_prefix)
    if not lines:
        st.error("Add at least one invoice line item (item name with qty × rate).")
        return False
    totals = _aggregate_expense_lines(lines)
    taxable = totals["taxable_amount"]
    cgst = totals["total_cgst"]
    sgst = totals["total_sgst"]
    igst = totals["total_igst"]
    total_tax = totals["total_tax"]
    total = totals["total_invoice_value"]
    payment_source = form.get(f"{key_prefix}_pay_source", "Petty Cash")
    tax_type = "Mixed" if len({l.get("tax_type") for l in lines}) > 1 else lines[0].get("tax_type", "CGST+SGST")
    gst_rate = lines[0].get("gst_rate", 0) if len(lines) == 1 else 0
    qty = sum(float(l.get("quantity") or 0) for l in lines)
    rate = lines[0].get("rate", 0) if len(lines) == 1 else 0
    exp_date = form.get(f"{key_prefix}_date")
    if hasattr(exp_date, "strftime"):
        exp_date_str = exp_date.strftime(DATE_FMT)
    else:
        exp_date_str = datetime.now().strftime(DATE_FMT)

    if duplicate_site_expense_invoice(supplier, invoice_no, exclude_id=expense_id):
        st.error("Duplicate invoice detected for this supplier. Check invoice number.")
        return False
    if status == "Submitted" and payment_source == "Petty Cash" and project:
        bal = get_petty_cash_balance(project)
        if total > bal:
            st.warning(f"Warning: amount exceeds current petty cash (Rs {bal:,.2f}). Will deduct only after final approval.")

    eid = expense_id or generate_id("SEX", "site_expenses")
    doc_no = None
    if not expense_id:
        conn_tmp = get_conn()
        doc_no = next_document_number("expense_entry", conn=conn_tmp)
        conn_tmp.commit()
        conn_tmp.close()
    inv_doc = _save_upload(inv_upload, "uploads/finance/invoices", eid)
    bill_doc = _save_upload(bill_upload, "uploads/finance/bills", f"{eid}_bill")
    sup_doc = _save_upload(sup_upload, "uploads/finance/supporting", f"{eid}_sup")
    desc = form.get(f"{key_prefix}_desc", "") or "; ".join(l["item_name"] for l in lines[:3])
    remarks = form.get(f"{key_prefix}_remarks", "")
    if correction_note:
        remarks = f"{remarks}\n[Accounts correction: {correction_note}]".strip()

    conn = get_conn()
    if expense_id:
        old = get_site_expense(expense_id) or {}
        keep_submitted = old.get("status") == "Submitted" and status == "Draft"
        save_status = "Submitted" if keep_submitted else status
        conn.execute(
            """
            UPDATE site_expenses SET
                expense_date=?, project_name=?, supplier=?, invoice_no=?, expense_category=?,
                description=?, quantity=?, rate=?, taxable_amount=?, gst_rate=?, tax_type=?,
                total_cgst=?, total_sgst=?, total_igst=?, total_tax=?, total_invoice_value=?,
                payment_source=?, invoice_upload=COALESCE(NULLIF(?,''), invoice_upload),
                bill_photo=COALESCE(NULLIF(?,''), bill_photo),
                supporting_docs=COALESCE(NULLIF(?,''), supporting_docs),
                remarks=?, status=?, updated_at=?,
                submitted_by=?, submitted_at=?
            WHERE expense_id=? AND COALESCE(is_void, 0) = 0
            """,
            (
                exp_date_str,
                project,
                supplier,
                invoice_no,
                form.get(f"{key_prefix}_category", ""),
                desc,
                qty,
                rate,
                taxable,
                gst_rate,
                tax_type,
                cgst,
                sgst,
                igst,
                total_tax,
                total,
                payment_source,
                inv_doc,
                bill_doc,
                sup_doc,
                remarks,
                save_status,
                _ts(),
                old.get("submitted_by", "") if save_status == "Submitted" else (_user() if save_status == "Submitted" else old.get("submitted_by", "")),
                old.get("submitted_at", "") if save_status == "Submitted" else (_ts() if save_status == "Submitted" else old.get("submitted_at", "")),
                expense_id,
            ),
        )
        audit_action = "Accounts correction" if correction_note else "Edit"
        if old.get("status") == "Returned" and save_status == "Submitted":
            audit_action = "Resubmitted"
        elif old.get("status") == "Returned" and save_status == "Draft":
            audit_action = "Returned"
        log_finance_audit(conn, "site_expense", eid, audit_action, _user(), old.get("status", ""), save_status, remarks)
    else:
        conn.execute(
            """
            INSERT INTO site_expenses(
                expense_id, document_no, expense_date, project_name, supplier, invoice_no, expense_category,
                description, quantity, rate, taxable_amount, gst_rate, tax_type,
                total_cgst, total_sgst, total_igst, total_tax, total_invoice_value,
                payment_source, invoice_upload, bill_photo, supporting_docs, remarks, status,
                submitted_by, submitted_at, created_by, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                eid,
                doc_no or "",
                exp_date_str,
                project,
                supplier,
                invoice_no,
                form.get(f"{key_prefix}_category", ""),
                desc,
                qty,
                rate,
                taxable,
                gst_rate,
                tax_type,
                cgst,
                sgst,
                igst,
                total_tax,
                total,
                payment_source,
                inv_doc,
                bill_doc,
                sup_doc,
                remarks,
                status,
                _user() if status == "Submitted" else "",
                _ts() if status == "Submitted" else "",
                _user(),
                _ts(),
                _ts(),
            ),
        )
        log_finance_audit(
            conn,
            "site_expense",
            eid,
            "Created",
            _user(),
            "",
            status,
            remarks,
            {"document_no": doc_no},
        )
    save_site_expense_lines(conn, eid, lines)
    conn.commit()
    conn.close()
    label = doc_no or eid
    st.success(f"Expense {'submitted' if status == 'Submitted' else 'saved'}: {label}")
    return True


def _can_edit_expense(row):
    status = row.get("status", "")
    creator = row.get("created_by", "")
    if status in ("Draft", "Returned") and (creator == _user() or _can_verify() or _role() == "Admin"):
        return True
    if status == "Submitted" and _can_verify():
        return True
    if status in ("Approved", "PM Approved", "Verified") and can_delete_approved_finance(_role()):
        return True
    return False


def _render_verification_correction_form(expense_id):
    edit_row = get_site_expense(expense_id) or {}
    _prime_site_expense_line_fields(expense_id, prefix="ver")
    projects = [""] + load_project_names()
    st.markdown("##### Edit correction (Accounts)")
    st.caption("Update invoice details. Expense stays **Submitted** until you approve, reject, or return it.")
    _render_line_item_controls("ver")
    with st.form(f"ver_correction_{expense_id}"):
        c1, c2, c3, c4 = st.columns(4)
        exp_val = edit_row.get("expense_date")
        try:
            default_date = datetime.strptime(str(exp_val)[:10], DATE_FMT).date() if exp_val else datetime.now().date()
        except ValueError:
            default_date = datetime.now().date()
        c1.date_input("Date *", value=default_date, format=DATE_INPUT_FMT, key="ver_date")
        project_idx = projects.index(edit_row["project_name"]) if edit_row.get("project_name") in projects else 0
        c2.selectbox("Project *", projects, index=project_idx, key="ver_project")
        c3.text_input("Supplier / Vendor *", value=edit_row.get("supplier", ""), key="ver_supplier")
        c4.text_input("Invoice number *", value=edit_row.get("invoice_no", ""), key="ver_invoice")
        cats = EXPENSE_CATEGORIES
        cat_idx = cats.index(edit_row["expense_category"]) if edit_row.get("expense_category") in cats else 0
        c5, c6 = st.columns(2)
        c5.selectbox("Expense category *", cats, index=cat_idx, key="ver_category")
        c6.text_input("Invoice note", value=edit_row.get("description", ""), key="ver_desc")
        st.markdown("**Invoice line items**")
        _render_invoice_line_grid("ver")
        ps_idx = PAYMENT_SOURCES.index(edit_row["payment_source"]) if edit_row.get("payment_source") in PAYMENT_SOURCES else 0
        st.selectbox("Payment source", PAYMENT_SOURCES, index=ps_idx, key="ver_pay_source")
        correction_note = st.text_input("Correction note (optional)")
        st.text_area("Remarks", value=edit_row.get("remarks", ""), key="ver_remarks")
        c1, c2 = st.columns(2)
        save = c1.form_submit_button("SAVE CORRECTION", type="primary")
        cancel = c2.form_submit_button("CANCEL EDIT")
        if cancel:
            st.session_state.pop("ver_correction_id", None)
            st.session_state.pop("ver_edit_loaded", None)
            st.rerun()
        if save:
            if not st.session_state.get("ver_supplier", "").strip():
                st.error("Supplier is required.")
            else:
                ok = _save_site_expense(
                    "Submitted",
                    expense_id,
                    key_prefix="ver",
                    correction_note=correction_note or _user(),
                )
                if ok:
                    st.session_state.pop("ver_correction_id", None)
                    st.session_state.pop("ver_edit_loaded", None)
                    st.rerun()


def _render_site_expense_entry():
    st.markdown(f"### Module 2 — {EXPENSE_ENTRY_LABEL}")
    st.caption(
        "Site staff and office staff can enter supplier invoices here. "
        "Add multiple items under one invoice — each line has its own GST. "
        "Petty cash balance is NOT deducted until expense is fully Approved."
    )
    projects = [""] + load_project_names()

    editable = load_site_expenses(limit=200)
    allowed_statuses = ["Draft", "Returned"]
    if _can_verify() or _role() == "Admin":
        allowed_statuses.append("Submitted")
    editable = editable[editable["status"].isin(allowed_statuses)] if not editable.empty else editable
    edit_id = None
    if not editable.empty and (_is_site() or _can_verify() or _role() == "Admin"):
        edit_labels = {
            f"{r['expense_id']} | {r['supplier']} | {r['status']}": r["expense_id"]
            for _, r in editable.iterrows()
            if _can_edit_expense(r.to_dict())
        }
        if edit_labels:
            pick = st.selectbox("Edit draft / returned / pending expense", [""] + list(edit_labels.keys()), key="se_edit_pick")
            if pick:
                edit_id = edit_labels[pick]
    prev_edit = st.session_state.get("se_active_edit_id")
    if edit_id != prev_edit:
        if edit_id:
            _prime_site_expense_line_fields(edit_id, prefix="se")
        else:
            _reset_expense_line_fields("se")
        st.session_state["se_active_edit_id"] = edit_id
    elif edit_id:
        _prime_site_expense_line_fields(edit_id, prefix="se")
    elif _line_count_key("se") not in st.session_state:
        st.session_state[_line_count_key("se")] = DEFAULT_LINE_ITEMS

    edit_row = get_site_expense(edit_id) if edit_id else {}
    if edit_row is None:
        edit_row = {}

    _render_line_item_controls("se")
    with st.form("site_expense_form"):
        c1, c2, c3, c4 = st.columns(4)
        exp_date = c1.date_input("Date *", value=datetime.now().date(), format=DATE_INPUT_FMT, key="se_date")
        project_idx = projects.index(edit_row["project_name"]) if edit_row.get("project_name") in projects else 0
        project = c2.selectbox("Project *", projects, index=project_idx, key="se_project")
        supplier = c3.text_input("Supplier / Vendor *", value=edit_row.get("supplier", ""), key="se_supplier")
        invoice_no = c4.text_input("Invoice number *", value=edit_row.get("invoice_no", ""), key="se_invoice")

        c5, c6 = st.columns(2)
        cats = EXPENSE_CATEGORIES
        cat_idx = cats.index(edit_row["expense_category"]) if edit_row.get("expense_category") in cats else 0
        category = c5.selectbox("Expense category *", cats, index=cat_idx, key="se_category")
        desc = c6.text_input("Invoice note / reference (optional)", value=edit_row.get("description", ""), key="se_desc")

        st.markdown("#### Invoice items — add lines with individual GST")
        preview_subtotal, preview_tax, preview_total = _render_invoice_line_grid("se")

        st.markdown("#### Invoice totals")
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Subtotal (taxable)", f"Rs {preview_subtotal:,.2f}")
        t2.metric("Total tax", f"Rs {preview_tax:,.2f}")
        t3.metric("Total incl. tax", f"Rs {preview_total:,.2f}")
        t4.caption("CGST/SGST or IGST is calculated per line.")

        ps_idx = PAYMENT_SOURCES.index(edit_row["payment_source"]) if edit_row.get("payment_source") in PAYMENT_SOURCES else 0
        pay_source = st.selectbox("Payment source", PAYMENT_SOURCES, index=ps_idx, key="se_pay_source")
        if pay_source == "Petty Cash" and project:
            bal = get_petty_cash_balance(project)
            lim = get_project_petty_limit(project)
            handler = get_petty_cash_handler(project)
            handler_name = handler.get("staff_name") or "Not assigned"
            st.caption(
                f"Petty cash handled by: **{handler_name}** · Balance: Rs {bal:,.2f} (deducts only after approval)"
            )
            if lim > 0:
                st.caption(f"Project petty cash limit: Rs {lim:,.2f}")

        b1, b2, b3 = st.columns(3)
        edit_key = edit_id or "new"
        with b1:
            inv_upload = _render_attachment_slot(
                edit_row.get("invoice_upload"),
                "Invoice",
                "se_inv_upload",
                key_suffix=f"se_inv_{edit_key}",
            )
        with b2:
            bill_upload = _render_attachment_slot(
                edit_row.get("bill_photo"),
                "Bill photo",
                "se_bill_upload",
                key_suffix=f"se_bill_{edit_key}",
            )
        with b3:
            sup_upload = _render_attachment_slot(
                edit_row.get("supporting_docs"),
                "Supporting documents",
                "se_sup_upload",
                key_suffix=f"se_sup_{edit_key}",
            )
        remarks = st.text_area("Remarks", value=edit_row.get("remarks", ""), key="se_remarks")

        save_draft = st.form_submit_button("SAVE DRAFT")
        submit = st.form_submit_button("SUBMIT FOR VERIFICATION", type="primary")

        if save_draft or submit:
            if not project or not supplier.strip():
                st.error("Project and supplier are required.")
            elif submit and not invoice_no.strip():
                st.error("Invoice number is required for submission.")
            elif preview_total <= 0:
                st.error("Add at least one line item with amount greater than zero.")
            else:
                ok = _save_site_expense(
                    "Submitted" if submit else "Draft",
                    edit_id,
                    inv_upload=inv_upload,
                    bill_upload=bill_upload,
                    sup_upload=sup_upload,
                )
                if ok:
                    st.session_state.pop("se_edit_loaded", None)
                    st.session_state.pop("se_active_edit_id", None)
                    _reset_expense_line_fields("se")
                    st.rerun()

    st.markdown("#### My recent expenses")
    mine = load_site_expenses(limit=50)
    if not mine.empty:
        st.dataframe(
            mine[
                [
                    "expense_id",
                    "expense_date",
                    "project_name",
                    "supplier",
                    "invoice_no",
                    "expense_category",
                    "total_invoice_value",
                    "payment_source",
                    "status",
                ]
            ],
            width="stretch",
            hide_index=True,
        )


def _expense_action(expense_id, action, new_status, comments="", extra_sql=None, extra_params=None):
    row = get_site_expense(expense_id)
    if not row:
        st.error("Expense not found.")
        return
    conn = get_conn()
    if extra_sql:
        conn.execute(extra_sql, extra_params or ())
    else:
        conn.execute(
            "UPDATE site_expenses SET status=?, updated_at=? WHERE expense_id=? AND COALESCE(is_void, 0) = 0",
            (new_status, _ts(), expense_id),
        )
    audit_action = action
    if new_status == "Approved":
        audit_action = "Posted to Accounts"
        post_site_expense_to_ledger(conn, row, _user())
    log_finance_audit(conn, "site_expense", expense_id, audit_action, _user(), row.get("status", ""), new_status, comments)
    conn.commit()
    conn.close()
    doc = row.get("document_no") or expense_id
    st.success(f"Expense {doc}: {audit_action}")
    st.rerun()


def _render_verification():
    st.markdown("### Module 3 — Accounts Verification")
    st.caption("Pending petty cash and other expenses — **Approve**, **Reject**, **Return for correction**, or **Edit correction**.")
    if not (_can_verify() or _is_management()):
        st.warning("Only Accounts / Management can verify expenses.")
        return

    queue = load_site_expenses(status="Submitted")
    if queue.empty:
        st.info("No expenses pending accounts verification.")
        return

    filter_mode = st.radio("Show", ["All pending", "Petty cash only"], horizontal=True, key="ver_filter")
    if filter_mode == "Petty cash only" and "payment_source" in queue.columns:
        queue = queue[queue["payment_source"] == "Petty Cash"]
        if queue.empty:
            st.info("No petty cash expenses pending verification.")
            return

    show_cols = [c for c in ["expense_id", "expense_date", "project_name", "supplier", "invoice_no", "payment_source", "total_invoice_value", "status"] if c in queue.columns]
    st.dataframe(queue[show_cols], width="stretch", hide_index=True)

    options = {
        f"{r['expense_id']} | {r.get('payment_source', '')} | {r['supplier']} | Rs {float(r['total_invoice_value']):,.0f}": r["expense_id"]
        for _, r in queue.iterrows()
    }
    pick = st.selectbox("Select expense to verify", [""] + list(options.keys()), key="ver_pick")
    if not pick:
        return

    eid = options[pick]
    row = get_site_expense(eid) or {}
    is_petty = row.get("payment_source") == "Petty Cash"

    st.markdown("#### Expense details")
    st.markdown(
        f"**{row.get('document_no') or eid}** · **{row.get('supplier', '')}** · Invoice `{row.get('invoice_no', '')}` · "
        f"Project: {row.get('project_name', '')} · Payment: **{row.get('payment_source', '')}** · "
        f"Total: Rs {float(row.get('total_invoice_value') or 0):,.2f}"
    )
    if is_petty:
        handler = get_petty_cash_handler(row.get("project_name", ""))
        bal = get_petty_cash_balance(row.get("project_name", ""))
        st.caption(
            f"Petty cash handled by: **{handler.get('staff_name') or 'Not assigned'}** · "
            f"Balance: Rs {bal:,.2f}"
        )

    _render_site_expense_lines_table(eid)
    st.markdown("#### Attachments")
    _render_bill_viewer(row.get("invoice_upload"), "Invoice", key_suffix=f"ver_inv_{eid}")
    _render_bill_viewer(row.get("bill_photo"), "Bill photo", key_suffix=f"ver_bill_{eid}")
    _render_bill_viewer(row.get("supporting_docs"), "Supporting docs", key_suffix=f"ver_sup_{eid}")

    correction_id = st.session_state.get("ver_correction_id")
    if correction_id == eid:
        _render_verification_correction_form(eid)
        return

    comments = st.text_area("Comments / verification notes", key=f"ver_comments_{eid}")
    st.markdown("#### Actions")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("APPROVE (Verify)", type="primary", key=f"ver_ok_{eid}"):
        _expense_action(
            eid,
            "Verify",
            "Verified",
            comments,
            "UPDATE site_expenses SET status='Verified', verified_by=?, verified_at=?, verification_remarks=?, updated_at=? WHERE expense_id=?",
            (_user(), _ts(), comments, _ts(), eid),
        )
    if c2.button("REJECT", key=f"ver_rej_{eid}"):
        if not comments.strip():
            st.error("Rejection reason required in comments.")
        else:
            _expense_action(
                eid,
                "Reject",
                "Rejected",
                comments,
                "UPDATE site_expenses SET status='Rejected', rejected_by=?, rejected_at=?, rejection_reason=?, updated_at=? WHERE expense_id=?",
                (_user(), _ts(), comments, _ts(), eid),
            )
    if c3.button("RETURN FOR CORRECTION", key=f"ver_ret_{eid}"):
        if not comments.strip():
            st.error("Return reason required in comments.")
        else:
            _expense_action(
                eid,
                "Return",
                "Returned",
                comments,
                "UPDATE site_expenses SET status='Returned', returned_by=?, returned_at=?, return_reason=?, updated_at=? WHERE expense_id=?",
                (_user(), _ts(), comments, _ts(), eid),
            )
    if c4.button("EDIT CORRECTION", key=f"ver_edit_{eid}"):
        st.session_state["ver_correction_id"] = eid
        _prime_site_expense_line_fields(eid, prefix="ver")
        st.rerun()

    _render_audit_trail("site_expense", eid)


def _render_approvals():
    st.markdown("### Module 4 — Approval System")
    st.caption(
        "Petty cash expense: Site Staff → Accounts Verification → PM Approval → Posted to Accounts. "
        "Petty cash balance deducts at final posting."
    )

    for level_status, next_status, label, roles_ok, remark_field in [
        ("Verified", "PM Approved", "Level 2 — Project Manager", _is_pm_only(), "pm_remarks"),
        ("PM Approved", "Approved", "Level 3 — Posted to Accounts (Accounts Manager)", _is_accounts_manager(), "management_remarks"),
    ]:
        st.markdown(f"#### {label}")
        df = load_site_expenses(status=level_status)
        if df.empty:
            st.info(f"No expenses at status: {level_status}")
            continue
        st.dataframe(df[["expense_id", "project_name", "supplier", "total_invoice_value", "status"]], width="stretch", hide_index=True)
        options = {f"{r['expense_id']} | {r['project_name']} | Rs {float(r['total_invoice_value']):,.0f}": r["expense_id"] for _, r in df.iterrows()}
        pick = st.selectbox("Select", [""] + list(options.keys()), key=f"appr_{level_status}")
        if not pick:
            continue
        eid = options[pick]
        row = get_site_expense(eid) or {}
        _render_site_expense_lines_table(eid, title="Invoice items")
        st.markdown("#### Attachments")
        _render_bill_viewer(row.get("invoice_upload"), "Invoice", key_suffix=f"appr_inv_{eid}")
        _render_bill_viewer(row.get("bill_photo"), "Bill photo", key_suffix=f"appr_bill_{eid}")
        _render_bill_viewer(row.get("supporting_docs"), "Supporting docs", key_suffix=f"appr_sup_{eid}")
        comments = st.text_input("Comments", key=f"appr_c_{level_status}_{eid}")
        if not roles_ok:
            st.warning("Your role cannot action this approval level.")
            continue
        c1, c2, c3 = st.columns(3)
        if c1.button(f"APPROVE → {next_status}", key=f"appr_ok_{level_status}_{eid}"):
            blocked = False
            if next_status == "Approved" and row.get("payment_source") == "Petty Cash":
                bal = get_petty_cash_balance(row.get("project_name", ""))
                amt = float(row.get("total_invoice_value") or 0)
                if amt > bal:
                    st.error(f"Cannot approve: petty cash balance Rs {bal:,.2f} is less than expense Rs {amt:,.2f}.")
                    blocked = True
            if not blocked:
                actor_field = "approved_by" if next_status == "Approved" else "pm_approved_by"
                time_field = "approved_at" if next_status == "Approved" else "pm_approved_at"
                rem_field = remark_field
                _expense_action(
                    eid,
                    "Approve",
                    next_status,
                    comments,
                    f"UPDATE site_expenses SET status=?, {actor_field}=?, {time_field}=?, {rem_field}=?, updated_at=? WHERE expense_id=?",
                    (next_status, _user(), _ts(), comments, _ts(), eid),
                )
        escalated_ids = {x["expense_id"] for x in load_escalated_finance_items()}
        if eid in escalated_ids and _is_management():
            st.warning("This item is escalated — overdue for approval.")
            if st.button("FORCE APPROVE (ESCALATED)", key=f"appr_force_{level_status}_{eid}"):
                actor_field = "approved_by" if next_status == "Approved" else "pm_approved_by"
                time_field = "approved_at" if next_status == "Approved" else "pm_approved_at"
                rem_field = remark_field
                _expense_action(
                    eid,
                    "Escalated Approve",
                    next_status,
                    comments or "Escalated approval by management",
                    f"UPDATE site_expenses SET status=?, {actor_field}=?, {time_field}=?, {rem_field}=?, updated_at=? WHERE expense_id=?",
                    (next_status, _user(), _ts(), comments or "Escalated approval", _ts(), eid),
                )
        if c2.button("RETURN", key=f"appr_ret_{level_status}_{eid}"):
            _expense_action(
                eid,
                "Return",
                "Returned",
                comments,
                "UPDATE site_expenses SET status='Returned', returned_by=?, returned_at=?, return_reason=?, updated_at=? WHERE expense_id=?",
                (_user(), _ts(), comments, _ts(), eid),
            )
        if c3.button("REJECT", key=f"appr_rej_{level_status}_{eid}"):
            _expense_action(
                eid,
                "Reject",
                "Rejected",
                comments,
                "UPDATE site_expenses SET status='Rejected', rejected_by=?, rejected_at=?, rejection_reason=?, updated_at=? WHERE expense_id=?",
                (_user(), _ts(), comments, _ts(), eid),
            )


def _render_direct_payment():
    st.markdown("### Module 9 — Direct Payment Entry")
    st.caption("Accounts-only payments: Verification → Approval → Paid.")
    if not (_is_accounts() or _is_management()):
        st.warning("Direct payments are entered by Accounts Executive / Accounts Manager.")
        return
    projects = [""] + load_project_names()
    with st.form("direct_pay_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        pay_date = c1.date_input("Date", format=DATE_INPUT_FMT)
        pay_type = c2.selectbox("Payment type *", DIRECT_PAYMENT_TYPES)
        project = c3.selectbox("Project", projects)
        c4, c5, c6 = st.columns(3)
        party = c4.text_input("Party name *")
        amount = c5.number_input("Amount (Rs) *", min_value=0.0, step=100.0)
        method = c6.selectbox("Payment method", PAYMENT_METHODS)
        ref = st.text_input("Reference number")
        remarks = st.text_input("Remarks")
        attach = st.file_uploader("Attachment", key="dp_attach")
        if st.form_submit_button("SUBMIT PAYMENT", type="primary", width="stretch"):
            if not party.strip() or amount <= 0:
                st.error("Party name and amount are required.")
            else:
                pid = generate_id("DPY", "direct_payments")
                conn = get_conn()
                doc_no = next_document_number("payment_voucher", conn=conn)
                doc = _save_upload(attach, "uploads/finance/payments", pid)
                conn.execute(
                    """
                    INSERT INTO direct_payments(
                        payment_id, document_no, payment_date, payment_type, project_name, party_name,
                        amount, payment_method, reference_number, attachment, remarks,
                        status, created_by, created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        pid,
                        doc_no,
                        pay_date.strftime(DATE_FMT),
                        pay_type,
                        project,
                        party.strip(),
                        float(amount),
                        method,
                        ref,
                        doc,
                        remarks,
                        "Submitted",
                        _user(),
                        _ts(),
                    ),
                )
                log_finance_audit(
                    conn,
                    "direct_payment",
                    pid,
                    "Created",
                    _user(),
                    "",
                    "Submitted",
                    remarks,
                    {"document_no": doc_no},
                )
                conn.commit()
                conn.close()
                st.success(f"Payment submitted: {doc_no}")
                st.rerun()

    df = load_direct_payments(limit=100)
    if df.empty:
        st.info("No direct payments yet.")
        return
    st.dataframe(df, width="stretch", hide_index=True)
    pending = df[df["status"].isin(["Submitted", "Verified", "Approved"])]
    if pending.empty:
        return
    if not (_is_accounts_manager() or _is_management() or _can_verify()):
        st.warning("Accounts staff required to action supplier payments.")
        return
    options = {f"{r['payment_id']} | {r['party_name']} | Rs {float(r['amount']):,.0f} | {r['status']}": r["payment_id"] for _, r in pending.iterrows()}
    pick = st.selectbox("Action payment", [""] + list(options.keys()), key="dp_action")
    if not pick:
        return
    pid = options[pick]
    row = df[df["payment_id"] == pid].iloc[0].to_dict()
    st.markdown("#### Attachments")
    _render_bill_viewer(row.get("attachment"), "Payment attachment", key_suffix=f"dp_{pid}")
    md_limit = get_supplier_payment_md_limit()
    st.caption(f"MD approval required above Rs {md_limit:,.0f}")
    comments = st.text_input("Comments", key=f"dp_c_{pid}")
    c1, c2, c3 = st.columns(3)
    amt = float(row.get("amount") or 0)
    if row["status"] == "Submitted" and _is_accounts_manager() and c1.button("VERIFY (Accounts Manager)", key=f"dp_v_{pid}"):
        conn = get_conn()
        conn.execute(
            "UPDATE direct_payments SET status='Verified', verified_by=?, verified_at=? WHERE payment_id=?",
            (_user(), _ts(), pid),
        )
        log_finance_audit(conn, "direct_payment", pid, "Accounts Manager Verification", _user(), "Submitted", "Verified", comments)
        conn.commit()
        conn.close()
        st.rerun()
    needs_md = amt > md_limit
    can_approve = (_is_management() and needs_md) or (_is_accounts_manager() and not needs_md)
    if row["status"] == "Verified" and can_approve and c2.button(
        "MD APPROVE" if needs_md else "APPROVE", key=f"dp_a_{pid}"
    ):
        conn = get_conn()
        conn.execute(
            "UPDATE direct_payments SET status='Approved', approved_by=?, approved_at=? WHERE payment_id=?",
            (_user(), _ts(), pid),
        )
        log_finance_audit(
            conn,
            "direct_payment",
            pid,
            "MD Approval" if needs_md else "Approve",
            _user(),
            "Verified",
            "Approved",
            comments,
        )
        conn.commit()
        conn.close()
        st.rerun()
    elif row["status"] == "Verified" and needs_md and not _is_management():
        st.info("Amount exceeds limit — MD approval required.")
    if row["status"] == "Approved" and _is_accounts_manager() and c3.button("MARK PAID / POST", key=f"dp_p_{pid}"):
        conn = get_conn()
        conn.execute(
            "UPDATE direct_payments SET status='Paid', paid_by=?, paid_at=? WHERE payment_id=?",
            (_user(), _ts(), pid),
        )
        post_payment_to_ledger(
            conn,
            amt,
            row.get("party_name", ""),
            row.get("payment_method", ""),
            row.get("project_name", ""),
            "direct_payment",
            pid,
            _user(),
            f"Supplier payment {row.get('document_no') or pid}",
        )
        log_finance_audit(conn, "direct_payment", pid, "Posted to Ledger", _user(), "Approved", "Paid", comments)
        conn.commit()
        conn.close()
        st.rerun()
    _render_audit_trail("direct_payment", pid)


def _render_reports_controls():
    st.markdown("### Reports & Controls")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Budget vs Actual", "Cash / Bank / GST", "Petty Cash Limits", "Escalation Rules", "Escalated Queue"]
    )

    with tab1:
        st.markdown("#### Budget vs Actual Monitoring")
        bva = load_budget_vs_actual()
        if bva.empty:
            st.info("No projects found.")
        else:
            show = bva[
                [
                    "project_name",
                    "budget",
                    "site_expenses",
                    "direct_payments",
                    "legacy_finance",
                    "actual_total",
                    "variance",
                    "utilization_pct",
                ]
            ].rename(
                columns={
                    "project_name": "Project",
                    "budget": "Budget (Rs)",
                    "site_expenses": "Expenses (Rs)",
                    "direct_payments": "Direct Payments (Rs)",
                    "legacy_finance": "Legacy Finance (Rs)",
                    "actual_total": "Actual Total (Rs)",
                    "variance": "Variance (Rs)",
                    "utilization_pct": "Utilization %",
                }
            )
            st.dataframe(show, width="stretch", hide_index=True)
            over = bva[bva["utilization_pct"] >= 90]
            if not over.empty:
                st.warning(f"{len(over)} project(s) at or above 90% budget utilization.")

    with tab2:
        st.markdown("#### Cash Book · Bank Book · GST Register")
        c1, c2 = st.columns(2)
        d_from = c1.date_input("From date", value=None, format=DATE_INPUT_FMT, key="rep_from")
        d_to = c2.date_input("To date", value=None, format=DATE_INPUT_FMT, key="rep_to")
        df_from = d_from.strftime(DATE_FMT) if d_from else None
        df_to = d_to.strftime(DATE_FMT) if d_to else None

        st.markdown("##### Cash Book")
        cash_df = load_cash_book(df_from, df_to)
        if cash_df.empty:
            st.info("No cash book entries.")
        else:
            st.dataframe(cash_df, width="stretch", hide_index=True)
            st.download_button(
                "Download Cash Book CSV",
                cash_df.to_csv(index=False).encode("utf-8"),
                "cash_book.csv",
                "text/csv",
                key="dl_cash",
            )

        st.markdown("##### Bank Book")
        bank_df = load_bank_book(df_from, df_to)
        if bank_df.empty:
            st.info("No bank book entries.")
        else:
            st.dataframe(bank_df, width="stretch", hide_index=True)
            st.download_button(
                "Download Bank Book CSV",
                bank_df.to_csv(index=False).encode("utf-8"),
                "bank_book.csv",
                "text/csv",
                key="dl_bank",
            )

        st.markdown("##### GST Register")
        gst_df = load_gst_register(df_from, df_to)
        if gst_df.empty:
            st.info("No GST entries.")
        else:
            st.dataframe(gst_df, width="stretch", hide_index=True)
            total_tax = float(gst_df["total_tax"].sum()) if "total_tax" in gst_df.columns else 0
            st.metric("Total GST in period", f"Rs {total_tax:,.2f}")
            st.download_button(
                "Download GST Register CSV",
                gst_df.to_csv(index=False).encode("utf-8"),
                "gst_register.csv",
                "text/csv",
                key="dl_gst",
            )

    with tab3:
        st.markdown("#### Petty Cash Limit per Project")
        if not (_is_accounts_manager() or _is_management()):
            st.warning("Only Accounts / Management can edit limits.")
        settings_df = load_project_finance_settings()
        if settings_df.empty:
            st.info("Add projects first in Clients & Projects.")
        else:
            display_settings = settings_df.copy()
            display_settings["Petty Cash Handler"] = display_settings.apply(
                lambda r: str(r.get("petty_cash_handler_name") or "").strip()
                or get_petty_cash_handler(r.get("project_name", "")).get("staff_name")
                or "—",
                axis=1,
            )
            st.dataframe(
                display_settings.rename(
                    columns={
                        "project_name": "Project",
                        "project_budget": "Project Budget (Rs)",
                        "petty_cash_limit": "Petty Cash Limit (Rs)",
                        "expense_budget": "Expense Budget (Rs)",
                    }
                )[["Project", "Project Budget (Rs)", "Petty Cash Limit (Rs)", "Expense Budget (Rs)", "Petty Cash Handler"]],
                width="stretch",
                hide_index=True,
            )
        if _is_accounts_manager() or _is_management():
            with st.form("petty_limits_form"):
                project = st.selectbox("Project", load_project_names(), key="lim_project")
                row = (
                    settings_df[settings_df["project_name"] == project].iloc[0].to_dict()
                    if project and not settings_df.empty and project in settings_df["project_name"].values
                    else {}
                )
                handler = get_petty_cash_handler(project) if project else {}
                staff_options, staff_names = _staff_select_options(project)
                staff_ids = [eid for eid, _ in staff_options]
                staff_labels = dict(staff_options)
                current_handler_id = str(row.get("petty_cash_handler_id") or handler.get("staff_id") or "")
                if current_handler_id and current_handler_id not in staff_ids:
                    staff_ids.append(current_handler_id)
                    staff_labels[current_handler_id] = f"{current_handler_id} - {handler.get('staff_name', current_handler_id)}"
                c1, c2 = st.columns(2)
                petty_limit = c1.number_input(
                    "Petty cash limit (Rs) — 0 = unlimited",
                    min_value=0.0,
                    value=float(row.get("petty_cash_limit") or 0),
                    step=1000.0,
                )
                expense_budget = c2.number_input(
                    "Expense budget override (Rs) — 0 = use project budget",
                    min_value=0.0,
                    value=float(row.get("expense_budget") or 0),
                    step=1000.0,
                )
                handler_id = st.selectbox(
                    "Petty cash handler (staff holding cash on site)",
                    staff_ids,
                    index=staff_ids.index(current_handler_id) if current_handler_id in staff_ids else 0,
                    format_func=lambda eid: staff_labels.get(eid, "Select staff"),
                    key="lim_handler",
                )
                if st.form_submit_button("SAVE LIMITS", type="primary"):
                    handler_name = staff_names.get(handler_id, "") if handler_id else ""
                    save_project_finance_settings(
                        project,
                        petty_limit,
                        expense_budget,
                        _user(),
                        handler_id=handler_id or "",
                        handler_name=handler_name,
                    )
                    st.success(f"Limits and handler saved for {project}.")
                    st.rerun()

    with tab4:
        st.markdown("#### Approval Escalation Rules")
        st.caption("Items exceeding these hours appear as escalated on Dashboard and Approvals.")
        rules = get_escalation_rules()
        if _is_accounts_manager() or _is_management():
            with st.form("escalation_rules_form"):
                h1 = st.number_input(
                    "Hours before Submitted → escalated (Accounts overdue)",
                    min_value=1.0,
                    value=float(rules["hours_submitted"]),
                    step=1.0,
                )
                h2 = st.number_input(
                    "Hours before Verified → escalated (PM overdue)",
                    min_value=1.0,
                    value=float(rules["hours_verified"]),
                    step=1.0,
                )
                h3 = st.number_input(
                    "Hours before PM Approved → escalated (Management overdue)",
                    min_value=1.0,
                    value=float(rules["hours_pm_approved"]),
                    step=1.0,
                )
                if st.form_submit_button("SAVE ESCALATION RULES", type="primary"):
                    save_finance_setting("finance_escalation_hours_submitted", h1)
                    save_finance_setting("finance_escalation_hours_verified", h2)
                    save_finance_setting("finance_escalation_hours_pm_approved", h3)
                    st.success("Escalation rules updated.")
                    st.rerun()
        else:
            st.info(
                f"Accounts overdue: {rules['hours_submitted']}h · "
                f"PM overdue: {rules['hours_verified']}h · "
                f"Management overdue: {rules['hours_pm_approved']}h"
            )

    with tab5:
        st.markdown("#### Escalated Items Queue")
        escalated = load_escalated_finance_items()
        if not escalated:
            st.success("No escalated items — all approvals are within time limits.")
        else:
            st.dataframe(pd.DataFrame(escalated), width="stretch", hide_index=True)


def _render_registers():
    st.markdown("### Registers & Bill viewer (Modules 6 & 10)")
    tab1, tab2, tab3 = st.tabs(["Expense invoices", "Petty cash requests", "Direct payments"])
    with tab1:
        df = load_site_expenses(limit=300)
        if df.empty:
            st.info("No expense invoices yet.")
        else:
            st.dataframe(df, width="stretch", hide_index=True)
            eid = st.selectbox("View bill / audit", df["expense_id"].tolist(), key="reg_se")
            if eid:
                row = get_site_expense(eid) or {}
                _render_site_expense_lines_table(eid)
                st.markdown("#### Attachments")
                _render_bill_viewer(row.get("invoice_upload"), "Invoice", key_suffix=f"reg_inv_{eid}")
                _render_bill_viewer(row.get("bill_photo"), "Bill photo", key_suffix=f"reg_bill_{eid}")
                _render_bill_viewer(row.get("supporting_docs"), "Supporting docs", key_suffix=f"reg_sup_{eid}")
                _render_audit_trail("site_expense", eid)
    with tab2:
        pcr_df = load_petty_cash_requests(limit=200)
        if pcr_df.empty:
            st.info("No petty cash requests yet.")
        else:
            st.dataframe(pcr_df, width="stretch", hide_index=True)
            rid = st.selectbox("View attachment / audit", pcr_df["request_id"].tolist(), key="reg_pcr")
            if rid:
                row = pcr_df[pcr_df["request_id"] == rid].iloc[0].to_dict()
                _render_bill_viewer(row.get("attachment"), "Request attachment", key_suffix=f"reg_pcr_{rid}")
                _render_audit_trail("petty_cash_request", rid)
    with tab3:
        dp_df = load_direct_payments(limit=200)
        if dp_df.empty:
            st.info("No direct payments yet.")
        else:
            st.dataframe(dp_df, width="stretch", hide_index=True)
            pid = st.selectbox("View attachment", dp_df["payment_id"].tolist(), key="reg_dp")
            if pid:
                row = dp_df[dp_df["payment_id"] == pid].iloc[0].to_dict()
                _render_bill_viewer(row.get("attachment"), "Payment attachment", key_suffix=f"reg_dp_{pid}")


# Finance submenu toolbar (matches sidebar Finance section).
FINANCE_TOOLBAR_ITEMS = [
    ("expense", EXPENSE_ENTRY_LABEL, None),
    (
        "purchase",
        "Purchase Invoice",
        {"Admin", "Accountant", "Accounts Manager", "Accounts Executive", "MD", "Project Manager"},
    ),
    ("petty", "Petty Cash", None),
    (
        "payments",
        "Payments",
        {"Admin", "Accountant", "Accounts Manager", "Accounts Executive", "MD", "Project Manager"},
    ),
    (
        "receipts",
        "Receipts",
        {
            "Admin",
            "Accountant",
            "Accounts Manager",
            "Accounts Executive",
            "MD",
            "Project Manager",
            "Site Engineer",
        },
    ),
    ("journal", "Journal Voucher", {"Admin", "Accountant", "Accounts Manager"}),
    ("creditors", "Creditors", {"Admin", "Accountant", "Accounts Manager", "MD"}),
]


def _has_finance_module_access():
    return _is_site() or _is_accounts() or _is_management()


def _visible_finance_nav():
    role = _role()
    visible = []
    for key, label, roles in FINANCE_TOOLBAR_ITEMS:
        if roles is None or role in roles:
            visible.append((key, label))
    return visible


def _render_finance_toolbar():
    items = _visible_finance_nav()
    if not items:
        return
    keys = [k for k, _ in items]
    if st.session_state.get("finance_view") not in keys:
        st.session_state.finance_view = keys[0] if keys else "expense"

    st.markdown('<div class="maxek-finance-toolbar">', unsafe_allow_html=True)
    row_size = 5
    for start in range(0, len(items), row_size):
        row = items[start : start + row_size]
        cols = st.columns(len(row))
        for col, (key, label) in zip(cols, row):
            with col:
                if st.button(
                    label,
                    key=f"fin_nav_{key}",
                    type="primary" if st.session_state.finance_view == key else "secondary",
                    width="stretch",
                ):
                    if st.session_state.finance_view != key:
                        st.session_state.finance_view = key
                        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.divider()


def _render_finance_view():
    view = st.session_state.get("finance_view", "expense")
    if view == "petty":
        _render_petty_cash_request()
    elif view == "expense":
        _render_site_expense_entry()
    elif view == "purchase":
        from modules.finance import page_finance_accounts_hub

        page_finance_accounts_hub(entry_type="expense_voucher")
    elif view == "payments":
        from modules.finance import page_finance_accounts_hub

        page_finance_accounts_hub(entry_type="payment_out")
    elif view == "receipts":
        from modules.finance import page_finance_accounts_hub

        page_finance_accounts_hub(entry_type="cash_receipt")
    elif view == "journal":
        st.markdown("### Journal Voucher")
        st.info("Journal voucher entry is planned. Use Payments or Expense Entry for now.")
    elif view == "creditors":
        st.markdown("### Creditors")
        st.info("Creditor ledger view is planned. Use Reports → Financial for transaction history.")
    elif view == "direct":
        _render_direct_payment()
    elif view == "verify":
        _render_verification()
    elif view == "dashboard":
        _render_dashboard()
    elif view == "register":
        _render_registers()
    else:
        _render_site_expense_entry()


def render_gst_register_panel():
    """GST register — used from GST & TDS menu and Reports."""
    st.caption("Output/input GST from approved site expenses and invoices.")
    c1, c2 = st.columns(2)
    d_from = c1.date_input("From date", value=None, format=DATE_INPUT_FMT, key="gst_reg_from")
    d_to = c2.date_input("To date", value=None, format=DATE_INPUT_FMT, key="gst_reg_to")
    df_from = d_from.strftime(DATE_FMT) if d_from else None
    df_to = d_to.strftime(DATE_FMT) if d_to else None
    gst_df = load_gst_register(df_from, df_to)
    if gst_df.empty:
        st.info("No GST entries in this period.")
        return
    total_tax = float(gst_df.get("total_tax", gst_df.get("gst_amount", pd.Series([0]))).sum())
    st.metric("Total GST in period", f"Rs {total_tax:,.2f}")
    st.dataframe(gst_df, width="stretch", hide_index=True)


def render_budget_panel():
    """Budget vs actual — Projects → Budget / Cost Control."""
    st.caption("Project-wise budget and actual spend.")
    projects = [""] + load_project_names()
    project = st.selectbox("Project", projects, key="budget_panel_project")
    if not project:
        st.info("Select a project.")
        return
    df = load_budget_vs_actual(project)
    if df.empty:
        st.info("No budget lines for this project yet. Configure in Reports & Controls → Budget vs Actual.")
        return
    st.dataframe(df, width="stretch", hide_index=True)


def render_approval_inbox(title: str, statuses: list[str]):
    """Approvals queue filtered by status (sidebar Approvals section)."""
    st.subheader(f"Approvals — {title}")
    st.caption("Site expense invoices in the workflow.")
    if not (_is_pm() or _is_management() or _is_accounts()):
        st.warning("Approvals are for PM, Management, and Accounts.")
        return
    any_rows = False
    for status in statuses:
        df = load_site_expenses(status=status)
        if df.empty:
            continue
        any_rows = True
        st.markdown(f"#### {status}")
        st.dataframe(
            df[["expense_id", "project_name", "supplier", "total_invoice_value", "status"]],
            width="stretch",
            hide_index=True,
        )
    if not any_rows:
        st.info(f"No items with status: {', '.join(statuses)}")
        return
    if title == "Pending" and _can_verify() and "Submitted" in statuses:
        st.divider()
        _render_verification()
    elif title == "Pending" and (_is_pm() or _is_management()):
        st.divider()
        _render_approvals()


def page_finance_workflow():
    st.subheader("Finance")
    st.caption("Expense · Purchase invoice · Petty cash · Payments · Receipts · Journal · Creditors.")

    if not _has_finance_module_access():
        _render_dashboard()
        st.info("Your role has limited finance access. Contact Accounts for payments.")
        return

    if not st.session_state.pop("_finance_hide_toolbar", False):
        _render_finance_toolbar()
    _render_finance_view()
