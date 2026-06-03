"""ERP screens for purchase, store, HR, accounts, assets, vehicles, and masters."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from modules.database import (
    DATE_FMT,
    DATE_INPUT_FMT,
    generate_id,
    get_conn,
    load_employee_options,
    load_lookup,
    load_material_requests,
    load_project_names,
    load_vendors,
    next_document_number,
)
from modules.erp_data import (
    ensure_erp_extension_tables,
    load_asset_breakdowns,
    load_asset_fuel_logs,
    load_asset_maintenance,
    load_bank_reconciliations,
    load_calendar_events,
    load_cheques,
    load_controlled_documents,
    load_drivers,
    load_employee_transfers,
    load_grn_entries,
    load_leave_requests,
    load_low_stock_items,
    load_overtime_entries,
    load_purchase_quotations,
    load_purchase_rfqs,
    load_simple_master,
    load_site_wise_stock,
    load_stock_adjustments,
    load_stock_returns,
    load_stock_transfers,
    load_stock_valuation,
    load_vehicle_allocations,
    load_vehicle_fuel_logs,
    load_vehicle_insurance,
    load_vehicle_services,
    load_vehicle_trips,
    load_vehicles,
    load_vendor_ratings,
    save_asset_breakdown,
    save_asset_fuel,
    save_asset_maintenance,
    save_bank_reconciliation,
    save_calendar_event,
    save_cheque,
    save_controlled_document,
    save_driver,
    save_employee_transfer,
    save_grn,
    save_leave_request,
    save_overtime_entry,
    save_purchase_quotation,
    save_purchase_rfq,
    save_simple_master,
    save_stock_adjustment,
    save_stock_return,
    save_stock_transfer,
    save_vehicle,
    save_vehicle_allocation,
    save_vehicle_fuel,
    save_vehicle_insurance,
    save_vehicle_service,
    save_vehicle_trip,
    save_vendor_rating,
    update_leave_status,
)
from modules.inventory import load_material_master


def _actor() -> str:
    return st.session_state.get("user_name", "User")


def _save_material_request(data: dict, actor: str) -> None:
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
            data.get("project_name", ""),
            data.get("item_name", ""),
            float(data.get("quantity", 0)),
            data.get("unit", "Nos"),
            data.get("required_date", ""),
            data.get("remarks", ""),
            data.get("status", "Pending"),
            actor,
            datetime.now().strftime(f"{DATE_FMT} %H:%M"),
        ),
    )
    conn.commit()
    conn.close()


def _list_form(title: str, caption: str, df, empty_msg: str = "No records yet.") -> None:
    st.subheader(title)
    if caption:
        st.caption(caption)
    if df is None or df.empty:
        st.info(empty_msg)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


# —— Dashboard ——
def page_calendar():
    ensure_erp_extension_tables()
    st.subheader("Calendar")
    st.caption("Project milestones, approvals due dates, and site events.")
    projects = [""] + load_project_names()
    tab_add, tab_view = st.tabs(["Add Event", "Events"])
    with tab_add:
        with st.form("calendar_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            event_date = c1.date_input("Date", value=datetime.now().date(), format=DATE_INPUT_FMT)
            event_type = c2.selectbox("Type", ["Meeting", "Inspection", "Delivery", "Billing", "Other"])
            title = st.text_input("Title")
            project = st.selectbox("Project", projects)
            description = st.text_area("Description")
            if st.form_submit_button("SAVE EVENT", type="primary", use_container_width=True):
                if not title.strip():
                    st.error("Title is required.")
                else:
                    save_calendar_event(
                        {
                            "event_date": event_date.strftime(DATE_FMT),
                            "title": title.strip(),
                            "event_type": event_type,
                            "project_name": project,
                            "description": description.strip(),
                        },
                        _actor(),
                    )
                    st.success("Event saved.")
                    st.rerun()
    with tab_view:
        month = st.text_input("Filter month (YYYY-MM)", value=datetime.now().strftime("%Y-%m"))
        events = load_calendar_events(month or None)
        _list_form("", "", events)


# —— Master screens ——
def page_unit_master():
    st.subheader("Unit Master")
    with st.form("unit_form", clear_on_submit=True):
        name = st.text_input("Unit name", placeholder="Bag, Kg, Nos…")
        if st.form_submit_button("SAVE", type="primary", use_container_width=True):
            if name.strip():
                save_simple_master("erp_units", "unit_id", "UN", "unit_name", name)
                st.success("Unit saved.")
                st.rerun()
    _list_form("", "", load_simple_master("erp_units", "unit_name"))


def page_material_category():
    st.subheader("Material Category")
    with st.form("mat_cat_form", clear_on_submit=True):
        name = st.text_input("Category name")
        if st.form_submit_button("SAVE", type="primary", use_container_width=True):
            if name.strip():
                save_simple_master("erp_material_categories", "category_id", "MC", "category_name", name)
                st.success("Category saved.")
                st.rerun()
    _list_form("", "", load_simple_master("erp_material_categories", "category_name"))


def page_staff_category():
    st.subheader("Staff Category")
    with st.form("staff_cat_form", clear_on_submit=True):
        name = st.text_input("Category name")
        if st.form_submit_button("SAVE", type="primary", use_container_width=True):
            if name.strip():
                save_simple_master("erp_staff_categories", "category_id", "SC", "category_name", name)
                st.success("Category saved.")
                st.rerun()
    _list_form("", "", load_simple_master("erp_staff_categories", "category_name"))


def page_designation_master():
    st.subheader("Designation")
    st.caption("Designations are managed in Settings → Departments & Designations.")
    desigs = load_lookup("designations", "designation_name")
    if desigs:
        st.dataframe({"Designation": desigs}, use_container_width=True, hide_index=True)
    else:
        st.info("Add designations from Settings.")


def page_vendor_rating():
    st.subheader("Vendor Rating")
    vendors = load_vendors()
    vendor_names = [""] + (vendors["supplier_name"].tolist() if not vendors.empty else [])
    with st.form("vendor_rating_form", clear_on_submit=True):
        vendor = st.selectbox("Vendor", vendor_names)
        rating = st.slider("Rating", 1.0, 5.0, 4.0, 0.5)
        remarks = st.text_input("Remarks")
        if st.form_submit_button("SAVE RATING", type="primary", use_container_width=True):
            if vendor:
                save_vendor_rating({"vendor_name": vendor, "rating": rating, "remarks": remarks.strip()}, _actor())
                st.success("Rating saved.")
                st.rerun()
    _list_form("", "", load_vendor_ratings())


def page_driver_register():
    st.subheader("Driver Register")
    with st.form("driver_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("Driver name")
        mobile = c2.text_input("Mobile")
        license_no = st.text_input("License number")
        if st.form_submit_button("SAVE DRIVER", type="primary", use_container_width=True):
            if name.strip():
                save_driver({"driver_name": name.strip(), "mobile": mobile.strip(), "license_no": license_no.strip()})
                st.success("Driver saved.")
                st.rerun()
    _list_form("", "", load_drivers())


# —— Purchase ——
def page_purchase_requisition():
    st.subheader("Purchase Requisition")
    projects = [""] + load_project_names()
    with st.form("pr_form", clear_on_submit=True):
        project = st.selectbox("Project", projects)
        c1, c2, c3 = st.columns(3)
        item = c1.text_input("Item / material")
        qty = c2.number_input("Quantity", min_value=0.01, value=1.0)
        unit = c3.selectbox("Unit", ["Nos", "Kg", "Bag", "Meter", "Ton"])
        required = st.date_input("Required date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        remarks = st.text_input("Remarks")
        if st.form_submit_button("SUBMIT REQUISITION", type="primary", use_container_width=True):
            if not project or not item.strip():
                st.error("Project and item are required.")
            else:
                _save_material_request(
                    {
                        "project_name": project,
                        "item_name": item.strip(),
                        "quantity": qty,
                        "unit": unit,
                        "required_date": required.strftime(DATE_FMT),
                        "remarks": remarks.strip(),
                        "status": "Pending",
                    },
                    _actor(),
                )
                st.success("Requisition submitted.")
                st.rerun()
    df = load_material_requests()
    _list_form("", "", df)


def page_rfq_management():
    st.subheader("RFQ Management")
    projects = [""] + load_project_names()
    with st.form("rfq_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        rfq_date = c1.date_input("RFQ date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        due = c2.date_input("Due date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        project = st.selectbox("Project", projects)
        summary = st.text_input("Item summary")
        vendors = st.text_input("Vendors invited (comma separated)")
        if st.form_submit_button("CREATE RFQ", type="primary", use_container_width=True):
            save_purchase_rfq(
                {
                    "rfq_date": rfq_date.strftime(DATE_FMT),
                    "due_date": due.strftime(DATE_FMT),
                    "project_name": project,
                    "item_summary": summary.strip(),
                    "vendors_invited": vendors.strip(),
                },
                _actor(),
            )
            st.success("RFQ created.")
            st.rerun()
    _list_form("", "", load_purchase_rfqs())


def page_quotation_comparison():
    st.subheader("Quotation Comparison")
    rfqs = load_purchase_rfqs()
    rfq_ids = [""] + (rfqs["rfq_id"].tolist() if not rfqs.empty else [])
    with st.form("quote_form", clear_on_submit=True):
        rfq_id = st.selectbox("RFQ", rfq_ids)
        c1, c2 = st.columns(2)
        vendor = c1.text_input("Vendor name")
        amount = c2.number_input("Quoted amount (Rs)", min_value=0.0, step=100.0)
        delivery = st.number_input("Delivery days", min_value=1, value=7)
        if st.form_submit_button("ADD QUOTATION", type="primary", use_container_width=True):
            if rfq_id and vendor.strip():
                save_purchase_quotation(
                    {
                        "rfq_id": rfq_id,
                        "vendor_name": vendor.strip(),
                        "quoted_amount": amount,
                        "delivery_days": int(delivery),
                    }
                )
                st.success("Quotation recorded.")
                st.rerun()
    quotes = load_purchase_quotations()
    if not quotes.empty:
        st.markdown("**Comparison**")
        st.dataframe(quotes.sort_values("quoted_amount"), use_container_width=True, hide_index=True)


def page_grn():
    st.subheader("GRN (Goods Received Note)")
    projects = [""] + load_project_names()
    with st.form("grn_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        grn_date = c1.date_input("GRN date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        po_ref = c2.text_input("PO reference")
        vendor = st.text_input("Vendor")
        project = st.selectbox("Project / site", projects)
        c3, c4, c5 = st.columns(3)
        material = c3.text_input("Material")
        qty = c4.number_input("Quantity", min_value=0.01, value=1.0)
        unit = c5.selectbox("Unit", ["Nos", "Kg", "Bag", "Meter", "Ton"])
        if st.form_submit_button("RECORD GRN", type="primary", use_container_width=True):
            save_grn(
                {
                    "grn_no": f"GRN-{datetime.now().strftime('%Y%m%d%H%M')}",
                    "grn_date": grn_date.strftime(DATE_FMT),
                    "po_ref": po_ref.strip(),
                    "vendor_name": vendor.strip(),
                    "project_name": project,
                    "material_name": material.strip(),
                    "quantity": qty,
                    "unit": unit,
                },
                _actor(),
            )
            st.success("GRN recorded.")
            st.rerun()
    _list_form("", "", load_grn_entries())


# —— Store ——
def page_material_return():
    st.subheader("Material Return")
    projects = [""] + load_project_names()
    materials = load_material_master()
    mat_opts = [""] + [f"{r['material_code']} | {r['material_name']}" for _, r in materials.iterrows()] if not materials.empty else [""]
    with st.form("return_form", clear_on_submit=True):
        project = st.selectbox("Project", projects)
        mat = st.selectbox("Material", mat_opts)
        qty = st.number_input("Return quantity", min_value=0.01, value=1.0)
        reason = st.text_input("Reason")
        ret_date = st.date_input("Return date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        if st.form_submit_button("RECORD RETURN", type="primary", use_container_width=True):
            if project and mat:
                parts = mat.split(" | ", 1)
                save_stock_return(
                    {
                        "return_date": ret_date.strftime(DATE_FMT),
                        "project_name": project,
                        "material_code": parts[0],
                        "material_name": parts[1] if len(parts) > 1 else parts[0],
                        "quantity": qty,
                        "reason": reason.strip(),
                    },
                    _actor(),
                )
                st.success("Return recorded.")
                st.rerun()
    _list_form("", "", load_stock_returns())


def page_stock_transfer():
    st.subheader("Stock Transfer")
    sites = [""] + load_project_names()
    materials = load_material_master()
    mat_opts = [""] + [f"{r['material_code']} | {r['material_name']}" for _, r in materials.iterrows()] if not materials.empty else [""]
    with st.form("transfer_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        from_site = c1.selectbox("From site", sites)
        to_site = c2.selectbox("To site", sites)
        mat = st.selectbox("Material", mat_opts)
        qty = st.number_input("Quantity", min_value=0.01, value=1.0)
        transfer_date = st.date_input("Transfer date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        if st.form_submit_button("TRANSFER", type="primary", use_container_width=True):
            if from_site and to_site and mat and from_site != to_site:
                parts = mat.split(" | ", 1)
                save_stock_transfer(
                    {
                        "transfer_date": transfer_date.strftime(DATE_FMT),
                        "from_site": from_site,
                        "to_site": to_site,
                        "material_code": parts[0],
                        "material_name": parts[1] if len(parts) > 1 else parts[0],
                        "quantity": qty,
                    },
                    _actor(),
                )
                st.success("Transfer recorded.")
                st.rerun()
    _list_form("", "", load_stock_transfers())


def page_stock_adjustment():
    st.subheader("Stock Adjustment")
    sites = [""] + load_project_names()
    with st.form("adj_form", clear_on_submit=True):
        site = st.selectbox("Site", sites)
        material = st.text_input("Material")
        c1, c2 = st.columns(2)
        old_qty = c1.number_input("Old quantity", min_value=0.0, value=0.0)
        new_qty = c2.number_input("New quantity", min_value=0.0, value=0.0)
        reason = st.text_input("Reason")
        if st.form_submit_button("ADJUST", type="primary", use_container_width=True):
            save_stock_adjustment(
                {
                    "adjustment_date": datetime.now().strftime(DATE_FMT),
                    "site_name": site,
                    "material_code": "",
                    "material_name": material.strip(),
                    "old_qty": old_qty,
                    "new_qty": new_qty,
                    "reason": reason.strip(),
                },
                _actor(),
            )
            st.success("Adjustment saved.")
            st.rerun()
    _list_form("", "", load_stock_adjustments())


def page_site_wise_stock():
    st.subheader("Site Wise Stock")
    st.caption("Material issued to each project site.")
    _list_form("", "", load_site_wise_stock(), "No site issues recorded yet.")


def page_low_stock_alert():
    st.subheader("Low Stock Alert")
    threshold = st.number_input("Alert below quantity", min_value=0.0, value=10.0)
    low = load_low_stock_items(threshold)
    if low.empty:
        st.success(f"No items below {threshold}.")
    else:
        st.warning(f"{len(low)} item(s) below threshold.")
        st.dataframe(low, use_container_width=True, hide_index=True)


def page_stock_valuation():
    st.subheader("Stock Valuation")
    val = load_stock_valuation()
    if not val.empty and "estimated_value" in val.columns:
        st.metric("Total estimated value", f"Rs {val['estimated_value'].sum():,.2f}")
    _list_form("", "", val)


# —— HR ——
def page_leave_management():
    st.subheader("Leave Management")
    employees = load_employee_options()
    emp_opts = [""] + [f"{eid} | {ename}" for eid, ename in employees]
    with st.form("leave_form", clear_on_submit=True):
        emp = st.selectbox("Employee", emp_opts)
        leave_type = st.selectbox("Leave type", ["Casual", "Sick", "Earned", "Unpaid"])
        c1, c2 = st.columns(2)
        from_d = c1.date_input("From", value=datetime.now().date(), format=DATE_INPUT_FMT)
        to_d = c2.date_input("To", value=datetime.now().date(), format=DATE_INPUT_FMT)
        days = (to_d - from_d).days + 1
        st.caption(f"Days: {max(days, 1)}")
        reason = st.text_input("Reason")
        if st.form_submit_button("APPLY LEAVE", type="primary", use_container_width=True):
            if emp:
                parts = emp.split(" | ", 1)
                save_leave_request(
                    {
                        "employee_id": parts[0],
                        "employee_name": parts[1] if len(parts) > 1 else parts[0],
                        "leave_type": leave_type,
                        "from_date": from_d.strftime(DATE_FMT),
                        "to_date": to_d.strftime(DATE_FMT),
                        "days": float(max(days, 1)),
                        "reason": reason.strip(),
                    }
                )
                st.success("Leave request submitted.")
                st.rerun()
    _list_form("", "", load_leave_requests())


def page_leave_approval():
    st.subheader("Leave Approval")
    pending = load_leave_requests(status="Pending")
    if pending.empty:
        st.info("No pending leave requests.")
        return
    for _, row in pending.iterrows():
        c1, c2, c3 = st.columns([4, 1, 1])
        c1.write(f"**{row['employee_name']}** — {row['leave_type']} ({row['from_date']} to {row['to_date']})")
        if c2.button("Approve", key=f"lv_ok_{row['leave_id']}"):
            update_leave_status(row["leave_id"], "Approved", _actor())
            st.rerun()
        if c3.button("Reject", key=f"lv_no_{row['leave_id']}"):
            update_leave_status(row["leave_id"], "Rejected", _actor())
            st.rerun()


def page_employee_transfer():
    st.subheader("Employee Transfer")
    employees = load_employee_options()
    emp_opts = [""] + [f"{eid} | {ename}" for eid, ename in employees]
    projects = [""] + load_project_names()
    with st.form("emp_xfer_form", clear_on_submit=True):
        emp = st.selectbox("Employee", emp_opts)
        c1, c2 = st.columns(2)
        from_p = c1.selectbox("From project", projects)
        to_p = c2.selectbox("To project", projects)
        xfer_date = st.date_input("Transfer date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        if st.form_submit_button("TRANSFER", type="primary", use_container_width=True):
            if emp and from_p and to_p:
                parts = emp.split(" | ", 1)
                save_employee_transfer(
                    {
                        "employee_id": parts[0],
                        "employee_name": parts[1] if len(parts) > 1 else parts[0],
                        "from_project": from_p,
                        "to_project": to_p,
                        "transfer_date": xfer_date.strftime(DATE_FMT),
                    },
                    _actor(),
                )
                st.success("Transfer recorded.")
                st.rerun()
    _list_form("", "", load_employee_transfers())


def page_overtime_management():
    st.subheader("Overtime Management")
    employees = load_employee_options()
    emp_opts = [""] + [f"{eid} | {ename}" for eid, ename in employees]
    projects = [""] + load_project_names()
    with st.form("ot_form", clear_on_submit=True):
        emp = st.selectbox("Employee", emp_opts)
        ot_date = st.date_input("OT date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        ot_hours = st.number_input("OT hours", min_value=0.5, step=0.5, value=2.0)
        project = st.selectbox("Project", projects)
        if st.form_submit_button("RECORD OT", type="primary", use_container_width=True):
            if emp:
                parts = emp.split(" | ", 1)
                save_overtime_entry(
                    {
                        "employee_id": parts[0],
                        "employee_name": parts[1] if len(parts) > 1 else parts[0],
                        "ot_date": ot_date.strftime(DATE_FMT),
                        "ot_hours": ot_hours,
                        "project_name": project,
                    }
                )
                st.success("Overtime recorded.")
                st.rerun()
    _list_form("", "", load_overtime_entries())


# —— Accounts ——
def page_bank_reconciliation():
    st.subheader("Bank Reconciliation")
    with st.form("recon_form", clear_on_submit=True):
        bank = st.text_input("Bank account")
        stmt_date = st.date_input("Statement date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        c1, c2 = st.columns(2)
        book = c1.number_input("Book balance (Rs)", value=0.0, step=100.0)
        bank_bal = c2.number_input("Bank balance (Rs)", value=0.0, step=100.0)
        remarks = st.text_input("Remarks")
        if st.form_submit_button("SAVE RECONCILIATION", type="primary", use_container_width=True):
            save_bank_reconciliation(
                {
                    "bank_account": bank.strip(),
                    "statement_date": stmt_date.strftime(DATE_FMT),
                    "book_balance": book,
                    "bank_balance": bank_bal,
                    "remarks": remarks.strip(),
                },
                _actor(),
            )
            st.success("Reconciliation saved.")
            st.rerun()
    df = load_bank_reconciliations()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)


def page_cheque_management():
    st.subheader("Cheque Management")
    with st.form("cheque_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        cheque_no = c1.text_input("Cheque number")
        bank = c2.text_input("Bank name")
        payee = st.text_input("Payee")
        amount = st.number_input("Amount (Rs)", min_value=0.0, step=100.0)
        cheque_date = st.date_input("Cheque date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        status = st.selectbox("Status", ["Issued", "Cleared", "Cancelled", "Bounced"])
        if st.form_submit_button("SAVE CHEQUE", type="primary", use_container_width=True):
            save_cheque(
                {
                    "cheque_no": cheque_no.strip(),
                    "bank_name": bank.strip(),
                    "payee": payee.strip(),
                    "amount": amount,
                    "cheque_date": cheque_date.strftime(DATE_FMT),
                    "status": status,
                }
            )
            st.success("Cheque saved.")
            st.rerun()
    _list_form("", "", load_cheques())


# —— Assets ——
def _asset_picker():
    from modules.database import load_assets

    assets = load_assets()
    opts = [""]
    mapping = {}
    if not assets.empty:
        for _, r in assets.iterrows():
            label = f"{r['asset_code']} | {r['asset_name']}"
            opts.append(label)
            mapping[label] = r.to_dict()
    return opts, mapping


def page_asset_fuel():
    st.subheader("Fuel Consumption")
    opts, mapping = _asset_picker()
    with st.form("asset_fuel_form", clear_on_submit=True):
        sel = st.selectbox("Asset", opts)
        row = mapping.get(sel, {})
        c1, c2 = st.columns(2)
        log_date = c1.date_input("Date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        fuel_qty = c2.number_input("Fuel (litres)", min_value=0.1, value=10.0)
        cost = st.number_input("Cost (Rs)", min_value=0.0, step=50.0)
        if st.form_submit_button("SAVE", type="primary", use_container_width=True):
            save_asset_fuel(
                {
                    "asset_id": row.get("asset_id", ""),
                    "asset_name": row.get("asset_name", sel),
                    "log_date": log_date.strftime(DATE_FMT),
                    "fuel_qty": fuel_qty,
                    "cost": cost,
                    "operator": _actor(),
                }
            )
            st.success("Fuel log saved.")
            st.rerun()
    _list_form("", "", load_asset_fuel_logs())


def page_asset_maintenance():
    st.subheader("Maintenance Schedule")
    opts, mapping = _asset_picker()
    with st.form("maint_form", clear_on_submit=True):
        sel = st.selectbox("Asset", opts)
        row = mapping.get(sel, {})
        sched = st.date_input("Scheduled date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        mtype = st.selectbox("Type", ["Preventive", "Corrective", "Inspection"])
        cost = st.number_input("Estimated cost (Rs)", min_value=0.0, step=100.0)
        if st.form_submit_button("SCHEDULE", type="primary", use_container_width=True):
            save_asset_maintenance(
                {
                    "asset_id": row.get("asset_id", ""),
                    "asset_name": row.get("asset_name", sel),
                    "scheduled_date": sched.strftime(DATE_FMT),
                    "maintenance_type": mtype,
                    "cost": cost,
                }
            )
            st.success("Maintenance scheduled.")
            st.rerun()
    _list_form("", "", load_asset_maintenance())


def page_asset_breakdown():
    st.subheader("Breakdown Register")
    opts, mapping = _asset_picker()
    with st.form("bd_form", clear_on_submit=True):
        sel = st.selectbox("Asset", opts)
        row = mapping.get(sel, {})
        bd_date = st.date_input("Breakdown date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        downtime = st.number_input("Downtime (hours)", min_value=0.5, value=4.0)
        repair = st.number_input("Repair cost (Rs)", min_value=0.0, step=100.0)
        if st.form_submit_button("RECORD", type="primary", use_container_width=True):
            save_asset_breakdown(
                {
                    "asset_id": row.get("asset_id", ""),
                    "asset_name": row.get("asset_name", sel),
                    "breakdown_date": bd_date.strftime(DATE_FMT),
                    "downtime_hours": downtime,
                    "repair_cost": repair,
                }
            )
            st.success("Breakdown recorded.")
            st.rerun()
    _list_form("", "", load_asset_breakdowns())


# —— Vehicles ——
def _vehicle_options():
    vehicles = load_vehicles()
    opts = [""] + (vehicles["vehicle_no"].tolist() if not vehicles.empty else [])
    return opts, vehicles


def page_vehicle_allocation():
    st.subheader("Vehicle Allocation")
    opts, _ = _vehicle_options()
    projects = [""] + load_project_names()
    with st.form("veh_alloc_form", clear_on_submit=True):
        veh = st.selectbox("Vehicle", opts)
        project = st.selectbox("Project", projects)
        c1, c2 = st.columns(2)
        from_d = c1.date_input("From", value=datetime.now().date(), format=DATE_INPUT_FMT)
        to_d = c2.date_input("To", value=datetime.now().date(), format=DATE_INPUT_FMT)
        driver = st.text_input("Driver")
        if st.form_submit_button("ALLOCATE", type="primary", use_container_width=True):
            save_vehicle_allocation(
                {
                    "vehicle_no": veh,
                    "project_name": project,
                    "from_date": from_d.strftime(DATE_FMT),
                    "to_date": to_d.strftime(DATE_FMT),
                    "driver_name": driver.strip(),
                }
            )
            st.success("Allocation saved.")
            st.rerun()
    _list_form("", "", load_vehicle_allocations())


def page_vehicle_register_quick():
    st.subheader("Vehicle Register")
    with st.form("veh_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        veh_no = c1.text_input("Vehicle number")
        vtype = c2.selectbox("Type", ["Truck", "Tipper", "Pickup", "Car", "Other"])
        make = st.text_input("Make / model")
        driver = st.text_input("Default driver")
        if st.form_submit_button("SAVE VEHICLE", type="primary", use_container_width=True):
            if veh_no.strip():
                save_vehicle(
                    {
                        "vehicle_no": veh_no.strip().upper(),
                        "vehicle_type": vtype,
                        "make_model": make.strip(),
                        "driver_name": driver.strip(),
                    }
                )
                st.success("Vehicle saved.")
                st.rerun()
    _list_form("", "", load_vehicles())


def page_trip_sheet():
    st.subheader("Trip Sheet")
    opts, _ = _vehicle_options()
    with st.form("trip_form", clear_on_submit=True):
        veh = st.selectbox("Vehicle", opts)
        trip_date = st.date_input("Trip date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        c1, c2 = st.columns(2)
        from_loc = c1.text_input("From")
        to_loc = c2.text_input("To")
        c3, c4 = st.columns(2)
        start_km = c3.number_input("Start KM", min_value=0.0, value=0.0)
        end_km = c4.number_input("End KM", min_value=0.0, value=0.0)
        purpose = st.text_input("Purpose")
        if st.form_submit_button("SAVE TRIP", type="primary", use_container_width=True):
            save_vehicle_trip(
                {
                    "vehicle_no": veh,
                    "trip_date": trip_date.strftime(DATE_FMT),
                    "from_location": from_loc.strip(),
                    "to_location": to_loc.strip(),
                    "start_km": start_km,
                    "end_km": end_km,
                    "purpose": purpose.strip(),
                    "driver_name": "",
                }
            )
            st.success("Trip saved.")
            st.rerun()
    _list_form("", "", load_vehicle_trips())


def page_vehicle_fuel():
    st.subheader("Fuel Tracking")
    opts, _ = _vehicle_options()
    with st.form("veh_fuel_form", clear_on_submit=True):
        veh = st.selectbox("Vehicle", opts)
        fuel_date = st.date_input("Date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        c1, c2, c3 = st.columns(3)
        litres = c1.number_input("Litres", min_value=0.1, value=20.0)
        rate = c2.number_input("Rate", min_value=0.1, value=95.0)
        odo = c3.number_input("Odometer", min_value=0.0, value=0.0)
        if st.form_submit_button("SAVE", type="primary", use_container_width=True):
            save_vehicle_fuel(
                {"vehicle_no": veh, "fuel_date": fuel_date.strftime(DATE_FMT), "litres": litres, "rate": rate, "odometer": odo}
            )
            st.success("Fuel entry saved.")
            st.rerun()
    df = load_vehicle_fuel_logs()
    if not df.empty and "amount" in df.columns:
        st.metric("Total fuel spend", f"Rs {df['amount'].sum():,.2f}")
    _list_form("", "", df)


def page_vehicle_service():
    st.subheader("Service Tracking")
    opts, _ = _vehicle_options()
    with st.form("veh_svc_form", clear_on_submit=True):
        veh = st.selectbox("Vehicle", opts)
        svc_date = st.date_input("Service date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        svc_type = st.selectbox("Service type", ["Routine", "Major", "Tyre", "Engine", "Other"])
        cost = st.number_input("Cost (Rs)", min_value=0.0, step=100.0)
        next_due = st.date_input("Next due", value=datetime.now().date(), format=DATE_INPUT_FMT)
        if st.form_submit_button("SAVE", type="primary", use_container_width=True):
            save_vehicle_service(
                {
                    "vehicle_no": veh,
                    "service_date": svc_date.strftime(DATE_FMT),
                    "service_type": svc_type,
                    "cost": cost,
                    "next_due_date": next_due.strftime(DATE_FMT),
                }
            )
            st.success("Service recorded.")
            st.rerun()
    _list_form("", "", load_vehicle_services())


def page_vehicle_insurance():
    st.subheader("Insurance Tracking")
    opts, _ = _vehicle_options()
    with st.form("veh_ins_form", clear_on_submit=True):
        veh = st.selectbox("Vehicle", opts)
        policy = st.text_input("Policy number")
        insurer = st.text_input("Insurer")
        c1, c2 = st.columns(2)
        from_d = c1.date_input("From", value=datetime.now().date(), format=DATE_INPUT_FMT)
        to_d = c2.date_input("To", value=datetime.now().date(), format=DATE_INPUT_FMT)
        premium = st.number_input("Premium (Rs)", min_value=0.0, step=500.0)
        if st.form_submit_button("SAVE", type="primary", use_container_width=True):
            save_vehicle_insurance(
                {
                    "vehicle_no": veh,
                    "policy_no": policy.strip(),
                    "insurer": insurer.strip(),
                    "from_date": from_d.strftime(DATE_FMT),
                    "to_date": to_d.strftime(DATE_FMT),
                    "premium": premium,
                }
            )
            st.success("Insurance saved.")
            st.rerun()
    _list_form("", "", load_vehicle_insurance())


def page_vehicle_cost_reports():
    st.subheader("Vehicle Cost Reports")
    fuel = load_vehicle_fuel_logs()
    service = load_vehicle_services()
    insurance = load_vehicle_insurance()
    c1, c2, c3 = st.columns(3)
    c1.metric("Fuel", f"Rs {fuel['amount'].sum():,.0f}" if not fuel.empty and "amount" in fuel.columns else "Rs 0")
    c2.metric("Service", f"Rs {service['cost'].sum():,.0f}" if not service.empty else "Rs 0")
    c3.metric("Insurance", f"Rs {insurance['premium'].sum():,.0f}" if not insurance.empty else "Rs 0")


# —— Documents ——
def page_whatsapp_sending():
    st.subheader("WhatsApp Sending")
    st.caption("Send approved letters via WhatsApp Business API.")
    st.info(
        "Configure WhatsApp in **Settings → WhatsApp Configuration**. "
        "Use **Outgoing Letters** to draft and approve content before sharing."
    )


def page_controlled_document(doc_type: str, title: str):
    st.subheader(title)
    projects = [""] + load_project_names()
    with st.form(f"doc_{doc_type}_form", clear_on_submit=True):
        doc_title = st.text_input("Document title")
        project = st.selectbox("Project", projects)
        version = st.text_input("Version", value="1.0")
        if st.form_submit_button("REGISTER DOCUMENT", type="primary", use_container_width=True):
            if doc_title.strip():
                save_controlled_document(
                    {
                        "doc_type": doc_type,
                        "doc_title": doc_title.strip(),
                        "project_name": project,
                        "version": version.strip(),
                        "file_path": "",
                    },
                    _actor(),
                )
                st.success("Document registered.")
                st.rerun()
    _list_form("", "", load_controlled_documents(doc_type))
