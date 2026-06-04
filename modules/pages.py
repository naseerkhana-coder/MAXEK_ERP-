"""ERP page content for MAXEK Streamlit app."""

import base64
import calendar
import os
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import streamlit as st

from modules.branding import ERP_LEGAL_NAME
from modules.database import (
    BASE_DIR,
    DASHBOARD_ROLES,
    DASHBOARD_SECTION_LABELS,
    DASHBOARD_SECTION_ORDER_DEFAULT,
    DATE_FMT,
    ATTENDANCE_DEFAULT_BREAK_HOURS,
    ATTENDANCE_DEFAULT_IN_TIME,
    ATTENDANCE_DEFAULT_OUT_TIME,
    calculate_hours,
    format_decimal_hours,
    get_today_attendance_kpis,
    parse_flexible_time,
    ensure_district,
    ensure_region,
    generate_id,
    get_dashboard_settings,
    get_dashboard_role_visibility,
    get_conn,
    get_employee,
    delete_attendance_record,
    delete_payroll_record,
    get_attendance_record,
    get_employee_advance_ledger,
    get_employee_advance_summary,
    get_payroll_record,
    list_employee_payrolls,
    list_payroll_by_workflow,
    mark_advances_deducted,
    update_attendance_record,
    load_active_holidays,
    load_subcontractor_boq_rates,
    load_client_names,
    load_countries,
    load_employee_options,
    load_payroll_employee_options,
    load_payroll_staff_options,
    load_lookup,
    load_project_names,
    load_managers,
    load_subcontractor_labour_rate,
    load_subcontractor_names,
    load_weekly_off_rules,
    next_subcontractor_id,
    next_worker_id,
    mark_payroll_paid,
    parse_month_value,
    payroll_preview,
    save_dashboard_role_visibility,
    save_dashboard_settings,
    resolve_subcontractor_name,
    save_payroll_record,
    subcontractor_bill_preview,
    subcontractor_timesheet_day_amount,
    update_payroll_workflow,
)
from modules.roles import ERP_USER_ROLES, can_manage_users, display_role_name, is_management, is_super_admin
from modules.payroll_engine import (
    ATTENDANCE_STATUSES,
    PAYMENT_MODES,
    PAYMENT_STATUSES,
    WEEKDAY_NAMES,
    build_month_attendance_summary,
    infer_attendance_category,
    is_payroll_staff,
)
from modules.ui import (
    cancel_delete_confirm,
    location_dropdowns,
    render_delete_confirm_dialog,
    render_page_breadcrumbs,
    start_delete_confirm,
)
from modules.worker_payroll_engine import calculate_daily_pay, hourly_rate


def _is_internal_staff(employee_type):
    return (employee_type or "").strip() in ("Monthly Staff", "Daily Wage Staff", "Company Staff")


def _parse_db_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], DATE_FMT).date()
    except ValueError:
        return None


def _pop_widget_keys(keys):
    for key in keys:
        st.session_state.pop(key, None)


def _resolve_pay_to_name(pay_to_type, pay_to_value):
    if not pay_to_value:
        return ""
    if pay_to_type == "Employee" and " - " in pay_to_value:
        return pay_to_value.split(" - ", 1)[1]
    return pay_to_value


def _load_employee_allowance_components(employee_id):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT allowance_head, COALESCE(amount, 0) AS amount
        FROM employee_allowance_components
        WHERE employee_id = ?
          AND UPPER(COALESCE(status, 'ACTIVE')) = 'ACTIVE'
        ORDER BY id
        """,
        conn,
        params=(employee_id,),
    )
    conn.close()
    return df


def _save_employee_allowance_components(conn, employee_id, allowance_amounts):
    conn.execute("DELETE FROM employee_allowance_components WHERE employee_id = ?", (employee_id,))
    for head, amount in (allowance_amounts or {}).items():
        if head and float(amount or 0) > 0:
            conn.execute(
                """
                INSERT INTO employee_allowance_components(employee_id, allowance_head, amount, status)
                VALUES(?,?,?,?)
                """,
                (employee_id, head, float(amount), "Active"),
            )


def _render_employee_allowance_inputs(allowance_heads, prefix="employee"):
    amounts = {}
    total_allowance = 0.0
    head_options = [""] + allowance_heads
    st.caption("Select allowance heads and enter amounts. Total salary = Basic + allowances.")
    for idx in range(1, 6):
        c1, c2 = st.columns([2, 1])
        head = c1.selectbox(f"Allowance {idx}", head_options, key=f"{prefix}_allowance_head_{idx}")
        amount = c2.number_input(f"Amount {idx} (Rs)", min_value=0.0, step=100.0, key=f"{prefix}_allowance_amount_{idx}")
        if head and amount > 0:
            amounts[head] = amounts.get(head, 0.0) + float(amount)
            total_allowance += float(amount)
    return amounts, total_allowance


def _render_photo_preview(uploaded_file=None, saved_path=""):
    image_bytes = None
    mime = "image/jpeg"
    if uploaded_file is not None:
        image_bytes = uploaded_file.getvalue()
        mime = uploaded_file.type or mime
    elif saved_path:
        abs_path = os.path.join(BASE_DIR, saved_path.replace("/", os.sep))
        if os.path.isfile(abs_path):
            with open(abs_path, "rb") as f:
                image_bytes = f.read()
            ext = os.path.splitext(abs_path)[1].lower()
            mime = "image/png" if ext == ".png" else "image/jpeg"
    if not image_bytes:
        return
    encoded = base64.b64encode(image_bytes).decode()
    st.markdown(
        f"""
        <div style="text-align:center;margin:0.5rem 0;">
          <img src="data:{mime};base64,{encoded}"
               alt="Employee photo"
               style="width:120px;height:150px;object-fit:cover;border:1px solid #cbd5e1;border-radius:8px;" />
          <div style="font-size:0.75rem;color:#64748b;margin-top:0.25rem;">Passport size preview</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _clear_employee_form_keys():
    keys = [
        "employee_type",
        "employee_name",
        "employee_mobile",
        "employee_whatsapp",
        "employee_address",
        "employee_gender",
        "employee_blood_group",
        "employee_native_place",
        "employee_aadhaar",
        "employee_pan",
        "employee_status",
        "employee_experience",
        "employee_remarks",
        "employee_basic_salary",
        "employee_ot_applicable",
        "employee_ot_rate",
        "employee_dob",
        "employee_joining",
        "employee_leaving",
        "employee_location_country",
        "employee_location_region",
        "employee_location_district",
        "employee_account_holder_name",
        "employee_bank_account",
        "employee_ifsc_code",
        "employee_bank_name",
        "employee_branch_name",
        "employee_company",
        "employee_project",
        "employee_department",
        "employee_designation",
        "employee_salary_type",
        "employee_weekly_off",
        "employee_paid_holiday",
        "employee_payroll_status",
        "employee_photo",
        "employee_edit_id",
    ]
    for idx in range(1, 6):
        keys.extend([f"employee_allowance_head_{idx}", f"employee_allowance_amount_{idx}"])
    _pop_widget_keys(keys)
    st.session_state.pop("employee_delete_pending_id", None)
    st.session_state.pop("employee_delete_pending_label", None)
    for key, value in {
        "employee_type": "Monthly Staff",
        "employee_weekly_off": "Sunday",
        "employee_paid_holiday": "Yes",
        "employee_payroll_status": "Active",
        "employee_name": "",
        "employee_mobile": "",
        "employee_whatsapp": "",
        "employee_address": "",
        "employee_gender": "",
        "employee_blood_group": "",
        "employee_native_place": "",
        "employee_aadhaar": "",
        "employee_pan": "",
        "employee_status": "Active",
        "employee_experience": "",
        "employee_remarks": "",
        "employee_basic_salary": 0.0,
        "employee_ot_applicable": "No",
        "employee_ot_rate": 0.0,
        "employee_location_country": "",
        "employee_location_region": "",
        "employee_location_district": "",
        "employee_account_holder_name": "",
        "employee_bank_account": "",
        "employee_ifsc_code": "",
        "employee_bank_name": "",
        "employee_branch_name": "",
        "employee_company": "",
        "employee_project": "",
        "employee_department": "",
        "employee_designation": "",
        "employee_salary_type": "Monthly",
    }.items():
        st.session_state[key] = value
    for idx in range(1, 6):
        st.session_state[f"employee_allowance_head_{idx}"] = ""
        st.session_state[f"employee_allowance_amount_{idx}"] = 0.0
    for date_key in ("employee_dob", "employee_joining", "employee_leaving", "employee_photo"):
        st.session_state.pop(date_key, None)


def _ensure_session_select(key, options, fallback=None):
    value = st.session_state.get(key)
    if value not in options:
        if fallback is not None:
            st.session_state[key] = fallback
        elif "" in options:
            st.session_state[key] = ""
        elif options:
            st.session_state[key] = options[0]
        else:
            st.session_state.pop(key, None)


def _options_with_saved(options, session_key):
    saved = st.session_state.get(session_key)
    if saved and saved not in options:
        return list(options) + [saved]
    return options


def _load_employee_into_form(row):
    if row is None or (hasattr(row, "empty") and row.empty):
        return
    if not isinstance(row, dict):
        row = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    employee_id = row.get("employee_id")
    if not employee_id:
        return
    _clear_employee_form_keys()
    st.session_state.employee_edit_id = employee_id
    st.session_state.employee_type = row.get("employee_type") or "Company Staff"
    st.session_state.employee_name = row.get("employee_name") or ""
    st.session_state.employee_mobile = row.get("mobile_number") or ""
    st.session_state.employee_whatsapp = row.get("whatsapp_number") or ""
    st.session_state.employee_address = row.get("address") or ""
    gender_opts = ["", "Male", "Female", "Other"]
    gender = row.get("gender") or ""
    st.session_state.employee_gender = gender if gender in gender_opts else ""
    st.session_state.employee_blood_group = row.get("blood_group") or ""
    st.session_state.employee_native_place = row.get("native_place") or ""
    st.session_state.employee_aadhaar = row.get("aadhaar_number") or ""
    st.session_state.employee_pan = row.get("pan_number") or ""
    st.session_state.employee_account_holder_name = row.get("account_holder_name") or ""
    st.session_state.employee_bank_account = row.get("bank_account") or ""
    st.session_state.employee_ifsc_code = row.get("ifsc_code") or ""
    st.session_state.employee_bank_name = row.get("bank_name") or ""
    st.session_state.employee_branch_name = row.get("branch_name") or ""
    st.session_state.employee_status = row.get("status") or "Active"
    st.session_state.employee_experience = row.get("experience") or ""
    st.session_state.employee_remarks = row.get("remarks") or ""
    st.session_state.employee_basic_salary = float(row.get("basic_salary") or 0.0)
    st.session_state.employee_ot_applicable = row.get("ot_applicable") or "No"
    st.session_state.employee_ot_rate = float(row.get("ot_rate") or 0.0)
    st.session_state.employee_location_country = row.get("country") or ""
    st.session_state.employee_location_region = row.get("region") or ""
    st.session_state.employee_location_district = row.get("district") or ""
    if _is_internal_staff(st.session_state.get("employee_type")):
        st.session_state.employee_company = ERP_LEGAL_NAME
    else:
        st.session_state.employee_company = row.get("company_or_subcontractor") or ""
    st.session_state.employee_project = row.get("project_name") or ""
    st.session_state.employee_department = row.get("department") or ""
    st.session_state.employee_designation = row.get("designation") or ""
    st.session_state.employee_salary_type = row.get("salary_type") or "Monthly"
    st.session_state.employee_weekly_off = row.get("weekly_off_day") or "Sunday"
    st.session_state.employee_paid_holiday = row.get("paid_holiday_eligibility") or "Yes"
    st.session_state.employee_payroll_status = row.get("payroll_status") or row.get("status") or "Active"
    if st.session_state.employee_type == "Company Staff":
        st.session_state.employee_type = "Monthly Staff"
    dob = _parse_db_date(row.get("date_of_birth"))
    if dob:
        st.session_state.employee_dob = dob
    joining = _parse_db_date(row.get("joining_date"))
    if joining:
        st.session_state.employee_joining = joining
    leaving = _parse_db_date(row.get("leaving_date"))
    if leaving:
        st.session_state.employee_leaving = leaving
    allowance_df = _load_employee_allowance_components(employee_id)
    allowance_heads = load_lookup("allowance_heads", "head_name")
    head_options = [""] + allowance_heads
    for idx in range(1, 6):
        st.session_state[f"employee_allowance_head_{idx}"] = ""
        st.session_state[f"employee_allowance_amount_{idx}"] = 0.0
    for idx, (_, allowance_row) in enumerate(allowance_df.head(5).iterrows(), start=1):
        head = allowance_row["allowance_head"]
        st.session_state[f"employee_allowance_head_{idx}"] = head if head in head_options else ""
        st.session_state[f"employee_allowance_amount_{idx}"] = float(allowance_row["amount"])


def _delete_employee(employee_id):
    conn = get_conn()
    conn.execute("DELETE FROM employee_allowance_components WHERE employee_id = ?", (employee_id,))
    conn.execute("DELETE FROM document_uploads WHERE entity_type = 'employee' AND entity_id = ?", (employee_id,))
    conn.execute("DELETE FROM staff WHERE staff_id = ?", (employee_id,))
    conn.execute("DELETE FROM workers WHERE worker_id = ?", (employee_id,))
    conn.execute("DELETE FROM employees WHERE employee_id = ?", (employee_id,))
    conn.commit()
    conn.close()


def _ensure_subcontractor_draft():
    st.session_state.setdefault("sub_draft_labour_rates", [])
    st.session_state.setdefault("sub_draft_boq_rates", [])


def _reset_subcontractor_draft():
    st.session_state.sub_draft_labour_rates = []
    st.session_state.sub_draft_boq_rates = []


def _insert_subcontractor_labour_rate(conn, subcontractor_name, row):
    working_hours = row["working_hours"]
    ot_applicable = row["ot_applicable"]
    fixed_hours = float(working_hours.split()[0])
    rate_id = generate_id("LR", "subcontractor_labour_rates")
    conn.execute(
        """
        INSERT INTO subcontractor_labour_rates(
            rate_id, subcontractor_name, project_name, labour_type,
            working_hours, fixed_hours, rate, ot_applicable, ot_rate, status
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            rate_id,
            subcontractor_name,
            row["project_name"],
            row["designation"],
            working_hours,
            fixed_hours,
            row["daily_rate"],
            ot_applicable,
            row["ot_rate"] if ot_applicable == "Yes" else 0.0,
            row.get("status", "Active"),
        ),
    )
    return rate_id


def _rename_subcontractor_linked_names(conn, old_name, new_name):
    """When company/subcontractor display name changes, keep linked rows consistent."""
    if not old_name or not new_name or old_name == new_name:
        return
    for table, col in (
        ("subcontractor_labour_rates", "subcontractor_name"),
        ("subcontractor_boq_rates", "subcontractor_name"),
        ("subcontractor_boq_entries", "subcontractor_name"),
        ("subcontractor_bills", "subcontractor_name"),
        ("subcontractor_advance", "subcontractor_name"),
        ("workers", "subcontractor_name"),
    ):
        conn.execute(f"UPDATE {table} SET {col} = ? WHERE {col} = ?", (new_name, old_name))
    conn.execute(
        "UPDATE employees SET company_or_subcontractor = ? WHERE company_or_subcontractor = ?",
        (new_name, old_name),
    )


def _trade_summary_from_labour_rates(conn, sub_name):
    rows = conn.execute(
        """
        SELECT DISTINCT labour_type FROM subcontractor_labour_rates
        WHERE subcontractor_name = ? AND COALESCE(TRIM(labour_type), '') != ''
        """,
        (sub_name,),
    ).fetchall()
    types = sorted({str(r[0]).strip() for r in rows if r and r[0]})
    return ", ".join(types)


def _insert_subcontractor_boq_rate(conn, subcontractor_name, row):
    boq_rate_id = generate_id("BQ", "subcontractor_boq_rates")
    conn.execute(
        """
        INSERT INTO subcontractor_boq_rates(
            boq_rate_id, project_name, boq_item, unit, rate, subcontractor_name, status
        ) VALUES(?,?,?,?,?,?,?)
        """,
        (
            boq_rate_id,
            row["project_name"],
            row["boq_item"],
            row["unit"],
            row["rate"],
            subcontractor_name,
            row.get("status", "Active"),
        ),
    )
    return boq_rate_id


def _update_subcontractor_labour_rate(conn, rate_id, subcontractor_name, row):
    working_hours = row["working_hours"]
    ot_applicable = row["ot_applicable"]
    fixed_hours = float(working_hours.split()[0])
    conn.execute(
        """
        UPDATE subcontractor_labour_rates
        SET subcontractor_name=?, project_name=?, labour_type=?,
            working_hours=?, fixed_hours=?, rate=?, ot_applicable=?, ot_rate=?, status=?
        WHERE rate_id=?
        """,
        (
            subcontractor_name,
            row["project_name"],
            row["designation"],
            working_hours,
            fixed_hours,
            row["daily_rate"],
            ot_applicable,
            row["ot_rate"] if ot_applicable == "Yes" else 0.0,
            row.get("status", "Active"),
            rate_id,
        ),
    )


def _update_subcontractor_boq_rate(conn, boq_rate_id, subcontractor_name, row):
    conn.execute(
        """
        UPDATE subcontractor_boq_rates
        SET project_name=?, boq_item=?, unit=?, rate=?, subcontractor_name=?, status=?
        WHERE boq_rate_id=?
        """,
        (
            row["project_name"],
            row["boq_item"],
            row["unit"],
            row["rate"],
            subcontractor_name,
            row.get("status", "Active"),
            boq_rate_id,
        ),
    )


def _render_labour_rate_editor(subcontractors, project_options, designation_options):
    conn = get_conn()
    labour_df = pd.read_sql_query(
        """
        SELECT rate_id, subcontractor_name, project_name, labour_type,
               working_hours, rate, ot_applicable, ot_rate, status
        FROM subcontractor_labour_rates
        ORDER BY id DESC
        """,
        conn,
    )
    conn.close()
    if labour_df.empty:
        return

    st.markdown("#### Edit / Delete Manpower Rate")
    rate_labels = {
        f"{row['rate_id']} | {row['subcontractor_name']} | {row['labour_type']} | {row['project_name']} | {row['working_hours']}": row["rate_id"]
        for _, row in labour_df.iterrows()
    }
    selected_label = st.selectbox("Select manpower rate", [""] + list(rate_labels.keys()), key="edit_labour_pick")
    selected_rate_id = rate_labels.get(selected_label)
    if not selected_rate_id:
        return

    row = labour_df[labour_df["rate_id"] == selected_rate_id].iloc[0]
    a1, a2 = st.columns(2)

    def _confirm_delete_labour_rate(rate_id):
        conn = get_conn()
        conn.execute("DELETE FROM subcontractor_labour_rates WHERE rate_id=?", (rate_id,))
        conn.commit()
        conn.close()
        st.success("Manpower rate deleted.")
        st.rerun()

    render_delete_confirm_dialog("saved_labour_rate", _confirm_delete_labour_rate)
    if a1.button("DELETE MANPOWER RATE", type="secondary", width="stretch", key="delete_labour_rate_btn"):
        start_delete_confirm("saved_labour_rate", selected_label, selected_rate_id)

    sub_index = subcontractors.index(row["subcontractor_name"]) if row["subcontractor_name"] in subcontractors else 0
    project_index = project_options.index(row["project_name"]) if row["project_name"] in project_options else 0
    designation = row["labour_type"]
    designation_index = designation_options.index(designation) if designation in designation_options else 0
    hours_index = ["8 Hours", "10 Hours", "12 Hours"].index(row["working_hours"]) if row["working_hours"] in ["8 Hours", "10 Hours", "12 Hours"] else 0
    ot_index = 0 if str(row["ot_applicable"]).lower() == "yes" else 1
    status_index = 0 if row["status"] == "Active" else 1

    with st.expander("Edit selected manpower rate", expanded=True):
        e1, e2, e3, e4 = st.columns(4)
        edit_sub = e1.selectbox("Sub Contractor", subcontractors, index=sub_index, key="edit_labour_sub")
        edit_project = e2.selectbox("Project", project_options, index=project_index, key="edit_labour_project")
        edit_designation_pick = e3.selectbox(
            "Designation",
            [""] + designation_options,
            index=designation_index + 1 if designation in designation_options else 0,
            key="edit_labour_designation_pick",
        )
        edit_designation_custom = e4.text_input(
            "Or type designation",
            value=designation if designation not in designation_options else "",
            key="edit_labour_designation_custom",
        )
        f1, f2, f3, f4, f5 = st.columns(5)
        edit_hours = f1.selectbox("Working Hours", ["8 Hours", "10 Hours", "12 Hours"], index=hours_index, key="edit_labour_hours")
        edit_rate = f2.number_input("Daily Rate (Rs)", min_value=0.0, step=50.0, value=float(row["rate"]), key="edit_labour_rate")
        edit_ot = f3.selectbox("OT Applicable", ["Yes", "No"], index=ot_index, key="edit_labour_ot")
        edit_ot_rate = f4.number_input("OT Rate (Rs/hr)", min_value=0.0, step=10.0, value=float(row["ot_rate"] or 0), key="edit_labour_ot_rate")
        edit_status = f5.selectbox("Status", ["Active", "Inactive"], index=status_index, key="edit_labour_status")
        if st.button("UPDATE MANPOWER RATE", type="primary", width="stretch", key="update_labour_rate_btn"):
            edit_designation = (edit_designation_custom or edit_designation_pick or "").strip()
            if not edit_sub or not edit_project or not edit_designation:
                st.error("Sub Contractor, Project, and Designation are required.")
            elif edit_rate <= 0:
                st.error("Daily rate must be greater than zero.")
            else:
                conn = get_conn()
                _update_subcontractor_labour_rate(
                    conn,
                    selected_rate_id,
                    edit_sub,
                    {
                        "designation": edit_designation,
                        "project_name": edit_project,
                        "working_hours": edit_hours,
                        "daily_rate": edit_rate,
                        "ot_applicable": edit_ot,
                        "ot_rate": edit_ot_rate,
                        "status": edit_status,
                    },
                )
                conn.commit()
                conn.close()
                st.success("Manpower rate updated.")
                st.rerun()


def _render_boq_rate_editor(subcontractors, project_options):
    conn = get_conn()
    boq_df = pd.read_sql_query(
        """
        SELECT boq_rate_id, project_name, boq_item, unit, rate, subcontractor_name, status
        FROM subcontractor_boq_rates
        ORDER BY id DESC
        """,
        conn,
    )
    conn.close()
    if boq_df.empty:
        return

    st.markdown("#### Edit / Delete BOQ Rate")
    rate_labels = {
        f"{row['boq_rate_id']} | {row['subcontractor_name']} | {row['boq_item']} | {row['project_name']}": row["boq_rate_id"]
        for _, row in boq_df.iterrows()
    }
    selected_label = st.selectbox("Select BOQ rate", [""] + list(rate_labels.keys()), key="edit_boq_pick")
    selected_rate_id = rate_labels.get(selected_label)
    if not selected_rate_id:
        return

    row = boq_df[boq_df["boq_rate_id"] == selected_rate_id].iloc[0]
    b1, b2 = st.columns(2)

    def _confirm_delete_boq_rate(rate_id):
        conn = get_conn()
        conn.execute("DELETE FROM subcontractor_boq_rates WHERE boq_rate_id=?", (rate_id,))
        conn.commit()
        conn.close()
        st.success("BOQ rate deleted.")
        st.rerun()

    render_delete_confirm_dialog("saved_boq_rate", _confirm_delete_boq_rate)
    if b1.button("DELETE BOQ RATE", type="secondary", width="stretch", key="delete_boq_rate_btn"):
        start_delete_confirm("saved_boq_rate", selected_label, selected_rate_id)

    sub_index = subcontractors.index(row["subcontractor_name"]) if row["subcontractor_name"] in subcontractors else 0
    project_index = project_options.index(row["project_name"]) if row["project_name"] in project_options else 0
    status_index = 0 if row["status"] == "Active" else 1

    with st.expander("Edit selected BOQ rate", expanded=True):
        e1, e2, e3, e4 = st.columns(4)
        edit_sub = e1.selectbox("Sub Contractor", subcontractors, index=sub_index, key="edit_boq_sub")
        edit_project = e2.selectbox("Project", project_options, index=project_index, key="edit_boq_project")
        edit_item = e3.text_input("BOQ Item", value=str(row["boq_item"]), key="edit_boq_item")
        edit_unit = e4.text_input("Unit", value=str(row["unit"]), key="edit_boq_unit")
        f1, f2 = st.columns(2)
        edit_rate = f1.number_input("Rate (Rs)", min_value=0.0, step=100.0, value=float(row["rate"]), key="edit_boq_rate_value")
        edit_status = f2.selectbox("Status", ["Active", "Inactive"], index=status_index, key="edit_boq_status")
        if st.button("UPDATE BOQ RATE", type="primary", width="stretch", key="update_boq_rate_btn"):
            if not edit_sub or not edit_project or not edit_item.strip() or not edit_unit.strip():
                st.error("Sub Contractor, Project, BOQ Item, and Unit are required.")
            elif edit_rate <= 0:
                st.error("BOQ rate must be greater than zero.")
            else:
                conn = get_conn()
                _update_subcontractor_boq_rate(
                    conn,
                    selected_rate_id,
                    edit_sub,
                    {
                        "project_name": edit_project,
                        "boq_item": edit_item.strip(),
                        "unit": edit_unit.strip(),
                        "rate": edit_rate,
                        "status": edit_status,
                    },
                )
                conn.commit()
                conn.close()
                st.success("BOQ rate updated.")
                st.rerun()


def page_employee_management():
    st.subheader("Employee Management")
    last_saved_id = st.session_state.pop("employee_last_saved_id", "")
    if last_saved_id:
        st.success(f"Employee saved. ID: {last_saved_id}")

    conn = get_conn()
    employees_df = pd.read_sql_query(
        """
        SELECT employee_id, employee_name, employee_type, mobile_number, date_of_birth, joining_date,
               country, region, district, department, designation, project_name,
               salary_type, salary_amount, basic_salary, status, photo
        FROM employees
        ORDER BY id DESC
        """,
        conn,
    )
    conn.close()

    _render_saved_record_toolbar(
        "employee",
        employees_df,
        "employee_id",
        ["employee_name", "employee_type", "department"],
        _load_employee_into_form,
        _delete_employee,
        _clear_employee_form_keys,
        "employee_form_mode",
        new_label="Add new employee",
        edit_label="Edit / delete employee",
    )

    edit_id = st.session_state.get("employee_edit_id")
    if edit_id:
        st.info(f"Editing employee **{edit_id}**. Change fields below and click UPDATE EMPLOYEE, or switch to Add new employee.")

    departments = [""] + load_lookup("departments", "department_name")
    designations = [""] + load_lookup("designations", "designation_name")
    project_names = [""] + load_project_names()
    subcontractors = [""] + load_subcontractor_names()
    allowance_heads = load_lookup("allowance_heads", "head_name")

    _ensure_session_select(
        "employee_type",
        ["Monthly Staff", "Daily Wage Staff", "Sub Contractor Worker"],
        "Monthly Staff",
    )
    if _is_internal_staff(st.session_state.get("employee_type")):
        _ensure_session_select("employee_company", [ERP_LEGAL_NAME], ERP_LEGAL_NAME)
        _ensure_session_select("employee_weekly_off", WEEKDAY_NAMES, "Sunday")
        _ensure_session_select("employee_paid_holiday", ["Yes", "No"], "Yes")
        _ensure_session_select(
            "employee_payroll_status",
            ["Active", "Hold Salary", "Resigned", "Terminated"],
            "Active",
        )
    else:
        subcontractors = _options_with_saved(subcontractors, "employee_company")
        _ensure_session_select("employee_company", subcontractors)
    project_names = _options_with_saved(project_names, "employee_project")
    _ensure_session_select("employee_project", project_names)
    departments = _options_with_saved(departments, "employee_department")
    _ensure_session_select("employee_department", departments)
    designations = _options_with_saved(designations, "employee_designation")
    _ensure_session_select("employee_designation", designations)
    _ensure_session_select("employee_gender", ["", "Male", "Female", "Other"])
    _ensure_session_select("employee_status", ["Active", "Inactive", "Left"], "Active")
    if _is_internal_staff(st.session_state.get("employee_type")):
        _ensure_session_select("employee_ot_applicable", ["Yes", "No"], "No")
        head_options = [""] + allowance_heads
        for idx in range(1, 6):
            _ensure_session_select(f"employee_allowance_head_{idx}", head_options)

    st.markdown("### Basic Details")
    c1, c2, c3 = st.columns(3)
    employee_type = c1.selectbox(
        "Employee Type",
        ["Monthly Staff", "Daily Wage Staff", "Sub Contractor Worker"],
        key="employee_type",
    )
    if edit_id:
        c1.caption(f"Worker ID: {edit_id}" if employee_type == "Sub Contractor Worker" else f"Employee ID: {edit_id}")
    else:
        if employee_type == "Sub Contractor Worker" and st.session_state.get("employee_company"):
            c1.caption(f"Worker ID (preview): {next_worker_id(st.session_state.get('employee_company'))}")
        elif employee_type == "Sub Contractor Worker":
            c1.caption("Worker ID (preview): select Subcontractor")
        else:
            c1.caption(f"Employee ID (preview): {generate_id('EMP', 'employees')}")

    # Sub contractor selection must be first for worker
    if employee_type == "Sub Contractor Worker":
        company_or_sub = c2.selectbox("Select Subcontractor", subcontractors, index=0, key="employee_company")
    else:
        company_or_sub = c2.selectbox("Company", [ERP_LEGAL_NAME], key="employee_company")

    employee_name = c3.text_input("Worker Name" if employee_type == "Sub Contractor Worker" else "Employee Name", key="employee_name")

    p1, p2, p3 = st.columns(3)
    mobile_number = p1.text_input("Mobile Number", key="employee_mobile")
    whatsapp_number = p2.text_input("WhatsApp Number", key="employee_whatsapp")
    photo = p3.file_uploader("Photo Upload", type=["jpg", "jpeg", "png"], key="employee_photo")
    if photo is not None:
        _render_photo_preview(uploaded_file=photo)
    g1, g2, g3 = st.columns(3)
    gender = g1.selectbox("Gender", ["", "Male", "Female", "Other"], key="employee_gender")
    blood_group = g2.text_input("Blood Group", key="employee_blood_group")
    address = g3.text_area("Address", key="employee_address")

    country, region, district = location_dropdowns(
        "employee_location",
        default_country="",
        default_region="",
        default_district="",
        allow_blank=True,
        show_region=False,
        show_district=False,
    )

    d1, d2, d3 = st.columns(3)
    date_of_birth = d1.date_input("Date of Birth", value=None, key="employee_dob")
    native_place = d2.text_input("Native Place", key="employee_native_place")
    aadhaar_number = d3.text_input("Aadhaar Number", key="employee_aadhaar")

    e1, e2, e3 = st.columns(3)
    pan_number = e1.text_input("PAN Number", key="employee_pan")
    joining_date = e2.date_input("Joining Date", key="employee_joining")
    leaving_date = e3.date_input("Leaving Date", value=None, key="employee_leaving")
    status = st.selectbox("Status", ["Active", "Inactive", "Left"], key="employee_status")

    st.markdown("### Job Details")
    with st.expander("Add New Department / Designation"):
        n1, n2 = st.columns(2)
        new_department = n1.text_input("New Department", key="new_employee_department")
        new_designation = n2.text_input("New Designation", key="new_employee_designation")
        p1, p2 = st.columns(2)
        if p1.button("ADD DEPARTMENT", width="stretch", key="add_employee_department"):
            if new_department.strip():
                conn = get_conn()
                conn.execute(
                    "INSERT OR IGNORE INTO departments(department_name) VALUES(?)",
                    (new_department.strip(),),
                )
                conn.commit()
                conn.close()
                st.success("Department added.")
                st.rerun()
        if p2.button("ADD DESIGNATION", width="stretch", key="add_employee_designation"):
            if new_designation.strip():
                conn = get_conn()
                conn.execute(
                    "INSERT OR IGNORE INTO designations(designation_name) VALUES(?)",
                    (new_designation.strip(),),
                )
                conn.commit()
                conn.close()
                st.success("Designation added.")
                st.rerun()

    j1, j2, j3 = st.columns(3)
    project_name = j1.selectbox("Project", project_names, index=0, key="employee_project")
    department = j2.selectbox("Department", departments, index=0, key="employee_department")
    j3.empty()

    k1, k2, k3 = st.columns(3)
    designation = k1.selectbox("Designation", designations, index=0, key="employee_designation")
    allowance_amounts = {}
    allowance_total = 0.0
    basic_salary = 0.0
    weekly_off_day = "Sunday"
    paid_holiday_eligibility = "Yes"
    payroll_status = "Active"
    if _is_internal_staff(employee_type):
        st.markdown("### Payroll Settings")
        ps1, ps2, ps3, ps4 = st.columns(4)
        weekly_off_day = ps1.selectbox("Weekly Off Day", WEEKDAY_NAMES, key="employee_weekly_off")
        paid_holiday_eligibility = ps2.selectbox("Paid Holiday Eligibility", ["Yes", "No"], key="employee_paid_holiday")
        payroll_status = ps3.selectbox(
            "Payroll Status",
            ["Active", "Hold Salary", "Resigned", "Terminated"],
            key="employee_payroll_status",
        )
        ot_applicable = ps4.selectbox("OT Applicable", ["Yes", "No"], key="employee_ot_applicable")
        salary_type = "Monthly" if employee_type == "Monthly Staff" else "Daily"
        st.session_state.employee_salary_type = salary_type
        basic_salary = k2.number_input(
            "Monthly Salary (Rs)" if employee_type == "Monthly Staff" else "Daily Wage (Rs)",
            min_value=0.0,
            step=100.0,
            key="employee_basic_salary",
        )
        allowance_amounts, allowance_total = _render_employee_allowance_inputs(allowance_heads, prefix="employee")
        salary_amount = basic_salary + allowance_total
        st.metric("Total Salary (Rs)", f"{salary_amount:,.2f}")
        ot_rate = k3.number_input("OT Rate (per hour)", min_value=0.0, step=10.0, key="employee_ot_rate")
    else:
        salary_type = "Daily"
        salary_amount = 0.0
        ot_applicable = "No"
        ot_rate = 0.0
        k2.caption("Salary and OT rates come from Sub Contractor labour rate or BOQ settings.")
        k3.empty()

    if _is_internal_staff(employee_type):
        st.markdown("### Account Details (Staff)")
        b1, b2, b3, b4, b5 = st.columns(5)
        account_holder_name = b1.text_input("Account Holder Name", key="employee_account_holder_name")
        bank_account = b2.text_input("Account Number", key="employee_bank_account")
        ifsc_code = b3.text_input("IFSC Code", key="employee_ifsc_code")
        bank_name = b4.text_input("Bank Name", key="employee_bank_name")
        branch_name = b5.text_input("Branch", key="employee_branch_name")
    else:
        account_holder_name = ""
        bank_account = ""
        ifsc_code = ""
        bank_name = ""
        branch_name = ""

    e4, e5 = st.columns(2)
    experience = e4.text_input("Experience", key="employee_experience")
    remarks = e5.text_input("Remarks", key="employee_remarks")

    st.markdown("### Document Attachments")
    u1, u2, u3 = st.columns(3)
    aadhaar_doc = u1.file_uploader("Aadhaar", key="emp_aadhaar_doc")
    pan_doc = u2.file_uploader("PAN", key="emp_pan_doc")
    passport_doc = u3.file_uploader("Passport", key="emp_passport_doc")
    visa_doc = u1.file_uploader("Visa", key="emp_visa_doc")
    certificate_doc = u2.file_uploader("Certificates", key="emp_cert_doc")
    agreement_doc = u3.file_uploader("Agreement", key="emp_agreement_doc")

    save_label = f"UPDATE EMPLOYEE ({edit_id})" if edit_id else "SAVE EMPLOYEE"
    if st.button(save_label, type="primary", width="stretch"):
        if not employee_name.strip():
            st.error("Employee Name is required.")
        elif employee_type == "Sub Contractor Worker" and not company_or_sub:
            st.error("Please select a Sub Contractor.")
        elif mobile_number and not _is_valid_mobile(mobile_number):
            st.error("Mobile number is invalid. Please enter at least 8 digits.")
        elif whatsapp_number and not _is_valid_mobile(whatsapp_number):
            st.error("WhatsApp number is invalid. Please enter at least 8 digits.")
        else:
            if employee_type == "Sub Contractor Worker":
                employee_id = edit_id or next_worker_id(company_or_sub)
            else:
                employee_id = edit_id or generate_id("EMP", "employees")
            photo_path = _save_upload(photo, "uploads/employees", employee_id)
            dob_text = date_of_birth.strftime(DATE_FMT) if date_of_birth else ""
            conn = get_conn()
            if edit_id:
                if not photo_path:
                    existing = conn.execute(
                        "SELECT photo FROM employees WHERE employee_id = ?",
                        (employee_id,),
                    ).fetchone()
                    photo_path = existing[0] if existing else ""
                conn.execute(
                    """
                    UPDATE employees SET
                        employee_type = ?, employee_name = ?, photo = ?, mobile_number = ?,
                        address = ?, country = ?, region = ?, district = ?, native_place = ?,
                        blood_group = ?, aadhaar_number = ?, pan_number = ?, date_of_birth = ?,
                        joining_date = ?, leaving_date = ?, status = ?,
                        company_or_subcontractor = ?, project_name = ?, department = ?, designation = ?,
                        salary_type = ?, salary_amount = ?, basic_salary = ?,
                        ot_applicable = ?, ot_rate = ?, experience = ?, remarks = ?,
                        whatsapp_number = ?, gender = ?,
                        weekly_off_day = ?, paid_holiday_eligibility = ?, payroll_status = ?,
                        account_holder_name = ?, bank_account = ?, bank_name = ?, ifsc_code = ?, branch_name = ?
                    WHERE employee_id = ?
                    """,
                    (
                        employee_type,
                        employee_name,
                        photo_path,
                        mobile_number,
                        address,
                        country,
                        region,
                        district,
                        native_place,
                        blood_group,
                        aadhaar_number,
                        pan_number,
                        dob_text,
                        joining_date.strftime(DATE_FMT),
                        leaving_date.strftime(DATE_FMT) if status == "Left" and leaving_date else "",
                        status,
                        company_or_sub,
                        project_name,
                        department,
                        designation,
                        salary_type,
                        salary_amount,
                        basic_salary if _is_internal_staff(employee_type) else 0.0,
                        ot_applicable,
                        ot_rate,
                        experience,
                        remarks,
                        whatsapp_number,
                        gender,
                        weekly_off_day if _is_internal_staff(employee_type) else "",
                        paid_holiday_eligibility if _is_internal_staff(employee_type) else "",
                        payroll_status if _is_internal_staff(employee_type) else status,
                        account_holder_name,
                        bank_account,
                        bank_name,
                        ifsc_code,
                        branch_name,
                        employee_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO employees(
                        employee_id, employee_type, employee_name, photo, mobile_number,
                        address, country, region, district, native_place, blood_group, aadhaar_number,
                        pan_number, date_of_birth, joining_date, leaving_date, status,
                        company_or_subcontractor, project_name, department, designation,
                        reporting_manager, salary_type, salary_amount, basic_salary,
                        ot_applicable, ot_rate, shift, experience, skills, remarks,
                        whatsapp_number, gender, weekly_off_day, paid_holiday_eligibility, payroll_status,
                        account_holder_name, bank_account, bank_name, ifsc_code, branch_name
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        employee_id,
                        employee_type,
                        employee_name,
                        photo_path,
                        mobile_number,
                        address,
                        country,
                        region,
                        district,
                        native_place,
                        blood_group,
                        aadhaar_number,
                        pan_number,
                        dob_text,
                        joining_date.strftime(DATE_FMT),
                        leaving_date.strftime(DATE_FMT) if status == "Left" and leaving_date else "",
                        status,
                        company_or_sub,
                        project_name,
                        department,
                        designation,
                        "",
                        salary_type,
                        salary_amount,
                        basic_salary if _is_internal_staff(employee_type) else 0.0,
                        ot_applicable,
                        ot_rate,
                        "",
                        experience,
                        "",
                        remarks,
                        whatsapp_number,
                        gender,
                        weekly_off_day if _is_internal_staff(employee_type) else "",
                        paid_holiday_eligibility if _is_internal_staff(employee_type) else "",
                        payroll_status if _is_internal_staff(employee_type) else status,
                        account_holder_name,
                        bank_account,
                        bank_name,
                        ifsc_code,
                        branch_name,
                    ),
                )
            if _is_internal_staff(employee_type):
                _save_employee_allowance_components(conn, employee_id, allowance_amounts)
                conn.execute("DELETE FROM staff WHERE staff_id = ?", (employee_id,))
                conn.execute(
                    """
                    INSERT INTO staff(staff_id, staff_name, department, designation, mobile, salary, region, manager_name, country, state)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        employee_id,
                        employee_name,
                        department,
                        designation,
                        mobile_number,
                        salary_amount,
                        region,
                        "",
                        country,
                        region,
                    ),
                )
                conn.execute("DELETE FROM workers WHERE worker_id = ?", (employee_id,))
            else:
                conn.execute("DELETE FROM workers WHERE worker_id = ?", (employee_id,))
                conn.execute(
                    """
                    INSERT INTO workers(worker_id, subcontractor_name, worker_name, trade_name, joining_date,
                                        salary, overtime_rate, photo, status, region, manager_name, country, state,
                                        whatsapp_number, gender)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        employee_id,
                        company_or_sub,
                        employee_name,
                        designation,
                        joining_date.strftime(DATE_FMT),
                        salary_amount,
                        ot_rate,
                        photo_path,
                        status,
                        region,
                        "",
                        country,
                        region,
                        whatsapp_number,
                        gender,
                    ),
                )
                conn.execute("DELETE FROM staff WHERE staff_id = ?", (employee_id,))
            for doc_type, uploaded in [
                ("Aadhaar", aadhaar_doc),
                ("PAN", pan_doc),
                ("Passport", passport_doc),
                ("Visa", visa_doc),
                ("Certificates", certificate_doc),
                ("Agreement", agreement_doc),
            ]:
                doc_path = _save_upload(uploaded, "uploads/employees", f"{employee_id}_{doc_type.lower()}")
                if doc_path:
                    conn.execute(
                        """
                        INSERT INTO document_uploads(entity_type, entity_id, document_type, file_path, uploaded_at)
                        VALUES(?,?,?,?,?)
                        """,
                        ("employee", employee_id, doc_type, doc_path, datetime.now().strftime("%d/%m/%Y %H:%M")),
                    )
            conn.commit()
            conn.close()
            st.session_state["employee_form_reset"] = True
            st.session_state.pop("employee_form_mode", None)
            st.session_state.employee_form_mode_prev = "Add new employee"
            st.session_state.employee_last_saved_id = employee_id
            st.rerun()

    conn = get_conn()
    allowance_summary_df = pd.read_sql_query(
        """
        SELECT employee_id,
               GROUP_CONCAT(allowance_head, ', ') AS allowance_heads,
               COALESCE(SUM(amount), 0) AS allowance_total
        FROM employee_allowance_components
        WHERE UPPER(COALESCE(status, 'ACTIVE')) = 'ACTIVE'
        GROUP BY employee_id
        """,
        conn,
    )
    conn.close()
    if not allowance_summary_df.empty:
        employees_df = employees_df.merge(allowance_summary_df, on="employee_id", how="left")
        employees_df["allowance_heads"] = employees_df["allowance_heads"].fillna("")
        employees_df["allowance_total"] = employees_df["allowance_total"].fillna(0)

    st.markdown("### Employee Register")
    st.dataframe(employees_df.drop(columns=["photo"], errors="ignore"), width="stretch", hide_index=True)

    st.markdown("### View Full Staff Details")
    if employees_df.empty:
        st.caption("No employees saved yet.")
    else:
        pick_labels = {
            f"{row['employee_id']} | {row['employee_name']}": row["employee_id"]
            for _, row in employees_df.iterrows()
        }
        pick = st.selectbox("Select Staff", [""] + list(pick_labels.keys()), key="view_employee_pick")
        if pick and pick in pick_labels:
            emp_id = pick_labels[pick]
            row = employees_df[employees_df["employee_id"] == emp_id].iloc[0]
            c1, c2 = st.columns([1, 2])
            with c1:
                _render_photo_preview(saved_path=row.get("photo", "") or "")
            with c2:
                for col in [
                    "employee_id",
                    "employee_name",
                    "employee_type",
                    "date_of_birth",
                    "mobile_number",
                    "department",
                    "designation",
                    "project_name",
                    "basic_salary",
                    "allowance_heads",
                    "allowance_total",
                    "salary_amount",
                    "status",
                ]:
                    if col in row.index:
                        st.write(f"**{col.replace('_', ' ').title()}:** {row.get(col, '')}")
            allowance_df = _load_employee_allowance_components(emp_id)
            if not allowance_df.empty:
                st.markdown("#### Allowance Split-up")
                st.dataframe(allowance_df, width="stretch", hide_index=True)
            conn = get_conn()
            docs_df = pd.read_sql_query(
                """
                SELECT document_type, file_path, uploaded_at
                FROM document_uploads
                WHERE entity_type = 'employee' AND entity_id = ?
                ORDER BY id DESC
                """,
                conn,
                params=(emp_id,),
            )
            conn.close()
            st.markdown("#### Attached Documents")
            if docs_df.empty:
                st.caption("No attached documents for this staff.")
            else:
                st.dataframe(docs_df, width="stretch", hide_index=True)


def page_subcontractors():
    st.subheader("Sub Contractors")
    hint = st.session_state.pop("subcontractor_hint", None)
    if hint:
        st.caption(f"Go to tab: **{hint}**")
    _ensure_subcontractor_draft()
    projects = load_project_names()
    project_options = [""] + projects
    designations = load_lookup("designations", "designation_name")
    designation_options = sorted(set(designations + ["Carpenter", "Mason", "Helper", "Steel Fixer", "Electrician", "Plumber"]))
    subcontractors = [""] + load_subcontractor_names()
    tabs = st.tabs(
        [
            "Add Sub Contractor",
            "Manpower Rates",
            "BOQ / Measurement Rates",
            "BOQ Entries",
            "Bills",
        ]
    )

    with tabs[0]:
        conn = get_conn()
        subs_df = pd.read_sql_query(
            """
            SELECT subcontractor_id, COALESCE(company_name, subcontractor_name) AS company_name,
                   subcontractor_name, contact_person, contact_number, aadhaar_number,
                   pan_card_number, address, account_holder_name, bank_account, bank_name, ifsc_code, branch_name,
                   country, region, district, active_projects, trade, status
            FROM subcontractors
            ORDER BY id DESC
            """,
            conn,
        )
        conn.close()

        _render_saved_record_toolbar(
            "subcontractor",
            subs_df,
            "subcontractor_id",
            ["company_name", "contact_person", "contact_number"],
            _load_subcontractor_into_form,
            _delete_subcontractor,
            _clear_subcontractor_form,
            "subcontractor_form_mode",
            new_label="Add new sub contractor",
            edit_label="Edit / delete sub contractor",
        )

        edit_id = st.session_state.get("sub_edit_id")
        if edit_id:
            st.info(
                f"Editing sub contractor **{edit_id}**. Change fields below and click UPDATE SUB CONTRACTOR, "
                "or switch to Add new sub contractor."
            )

        st.markdown("### Company Details")
        c1, c2, c3 = st.columns(3)
        company_name = c1.text_input("Company Name", key="sub_company_name")
        contact_person = c2.text_input("Sub Contractor Name", key="sub_contact_person")
        mobile_number = c3.text_input("Mobile Number", key="sub_mobile_number")
        aadhaar_number = c1.text_input("Aadhaar Number", key="sub_aadhaar_number")
        pan_number = c2.text_input("PAN Number", key="sub_pan_number")
        address = c3.text_area("Address", key="sub_address")

        st.markdown("### Account Details (Sub Contractor)")
        a1, a2, a3, a4 = st.columns(4)
        account_holder_name = a1.text_input("Account Holder Name", key="sub_account_holder_name")
        bank_account = a2.text_input("Account Number", key="sub_bank_account")
        ifsc_code = a3.text_input("IFSC Code", key="sub_ifsc_code")
        bank_name = a4.text_input("Bank Name", key="sub_bank_name")
        branch_name = st.text_input("Branch", key="sub_branch_name")
        country, region, district = location_dropdowns(
            "subcontractor_location",
            default_country="",
            default_region="",
            default_district="",
            allow_blank=True,
            show_region=False,
            show_district=False,
        )
        d1, d2 = st.columns(2)
        active_projects = d1.multiselect("Projects (select all applicable projects)", projects, key="sub_active_projects")
        status = d2.selectbox("Status", ["Active", "Inactive"], key="sub_status")
        agreement_upload = st.file_uploader("Agreement Upload", key="sub_agreement_upload")

        st.caption(
            "After saving, add **manpower rates** and **BOQ / measurement rates** in the "
            "**Manpower Rates** and **BOQ / Measurement Rates** tabs on this page."
        )

        save_label = f"UPDATE SUB CONTRACTOR ({edit_id})" if edit_id else "SAVE SUB CONTRACTOR"
        if st.button(save_label, type="primary", width="stretch", key="save_sub_contractor_master"):
            if not company_name.strip():
                st.error("Company Name is required.")
            else:
                saved_name = company_name.strip()
                conn = get_conn()
                if edit_id:
                    old_row = conn.execute(
                        "SELECT subcontractor_name FROM subcontractors WHERE subcontractor_id = ?",
                        (edit_id,),
                    ).fetchone()
                    old_name = (old_row[0] or "").strip() if old_row else ""
                    existing = conn.execute(
                        "SELECT agreement_upload FROM subcontractors WHERE subcontractor_id = ?",
                        (edit_id,),
                    ).fetchone()
                    agreement_path = existing[0] if existing else ""
                    if agreement_upload is not None:
                        agreement_path = _save_upload(agreement_upload, "uploads/subcontractors", edit_id)
                    if old_name and old_name != saved_name:
                        _rename_subcontractor_linked_names(conn, old_name, saved_name)
                    trade_summary = _trade_summary_from_labour_rates(conn, saved_name)
                    conn.execute(
                        """
                        UPDATE subcontractors SET
                            subcontractor_name = ?, company_name = ?, contact_person = ?,
                            contact_number = ?, aadhaar_number = ?, pan_card_number = ?,
                            address = ?, account_holder_name = ?, bank_account = ?, bank_name = ?, ifsc_code = ?, branch_name = ?,
                            country = ?, region = ?, district = ?,
                            trade = ?, agreement_upload = ?, active_projects = ?, status = ?, state = ?
                        WHERE subcontractor_id = ?
                        """,
                        (
                            saved_name,
                            saved_name,
                            contact_person,
                            mobile_number,
                            aadhaar_number,
                            pan_number,
                            address,
                            account_holder_name,
                            bank_account,
                            bank_name,
                            ifsc_code,
                            branch_name,
                            country,
                            region,
                            district,
                            trade_summary,
                            agreement_path,
                            ", ".join(active_projects),
                            status,
                            region,
                            edit_id,
                        ),
                    )
                    subcontractor_id = edit_id
                else:
                    trade_summary = ""
                    subcontractor_id = next_subcontractor_id(saved_name)
                    agreement_path = _save_upload(agreement_upload, "uploads/subcontractors", subcontractor_id)
                    conn.execute(
                        """
                        INSERT INTO subcontractors(
                            subcontractor_id, subcontractor_name, company_name, contact_person,
                            contact_number, aadhaar_number, pan_card_number, address, country, region,
                            district, trade, agreement_upload, active_projects, worker_count, status, state,
                            account_holder_name, bank_account, bank_name, ifsc_code, branch_name
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            subcontractor_id,
                            saved_name,
                            saved_name,
                            contact_person,
                            mobile_number,
                            aadhaar_number,
                            pan_number,
                            address,
                            country,
                            region,
                            district,
                            trade_summary,
                            agreement_path,
                            ", ".join(active_projects),
                            0,
                            status,
                            region,
                            account_holder_name,
                            bank_account,
                            bank_name,
                            ifsc_code,
                            branch_name,
                        ),
                    )
                if agreement_path and not edit_id:
                    conn.execute(
                        """
                        INSERT INTO document_uploads(entity_type, entity_id, document_type, file_path, uploaded_at)
                        VALUES(?,?,?,?,?)
                        """,
                        ("subcontractor", subcontractor_id, "Agreement", agreement_path, datetime.now().strftime("%d/%m/%Y %H:%M")),
                    )
                conn.commit()
                conn.close()
                st.session_state["subcontractor_form_reset"] = True
                st.session_state.pop("subcontractor_form_mode", None)
                st.session_state.subcontractor_form_mode_prev = "Add new sub contractor"
                st.success(
                    f"Sub contractor {'updated' if edit_id else 'saved'}. ID: {subcontractor_id}. "
                    "Add or edit manpower and BOQ rates in the **Manpower Rates** and **BOQ / Measurement Rates** tabs."
                )
                st.rerun()

        st.markdown("### Saved Sub Contractors")
        st.dataframe(
            subs_df[
                [
                    "subcontractor_id",
                    "company_name",
                    "contact_person",
                    "contact_number",
                    "active_projects",
                    "trade",
                    "country",
                    "region",
                    "district",
                    "status",
                ]
            ].rename(columns={"trade": "designations", "contact_person": "Sub Contractor Name"}),
            width="stretch",
            hide_index=True,
        )

    with tabs[1]:
        st.markdown("### Manpower Rate Based System")
        st.caption("Daily rate per designation / project / working hours — not monthly salary.")
        c1, c2, c3, c4 = st.columns(4)
        rate_subcontractor = c1.selectbox("Sub Contractor", subcontractors, index=0, key="labour_rate_subcontractor")
        rate_project = c2.selectbox("Project", project_options, index=0, key="labour_rate_project")
        labour_type = c3.selectbox(
            "Designation",
            [""] + designation_options,
            key="labour_rate_designation_pick",
        )
        labour_type_custom = c4.text_input("Or type designation", key="labour_rate_type")
        d0, d1, d2, d3, d4 = st.columns(5)
        working_hours = d0.selectbox("Working Hours", ["8 Hours", "10 Hours", "12 Hours"], key="labour_rate_hours")
        rate = d1.number_input("Daily Rate (Rs)", min_value=0.0, step=50.0, key="labour_rate_amount")
        ot_applicable = d2.selectbox("OT Applicable", ["Yes", "No"], key="labour_rate_ot_applicable")
        default_ot_rate = rate / max(1.0, float(working_hours.split()[0])) if rate else 0.0
        ot_rate = d3.number_input("OT Rate (Rs/hr)", min_value=0.0, step=10.0, value=float(default_ot_rate), key="labour_rate_ot_rate")
        rate_status = d4.selectbox("Status", ["Active", "Inactive"], key="labour_rate_status")
        if st.button("SAVE MANPOWER RATE", type="primary", width="stretch", key="save_labour_rate"):
            designation = (labour_type_custom or labour_type or "").strip()
            if not rate_subcontractor or not rate_project or not designation:
                st.error("Sub Contractor, Project, and Designation are required.")
            elif rate <= 0:
                st.error("Daily rate must be greater than zero.")
            else:
                conn = get_conn()
                _insert_subcontractor_labour_rate(
                    conn,
                    rate_subcontractor,
                    {
                        "designation": designation,
                        "project_name": rate_project,
                        "working_hours": working_hours,
                        "daily_rate": rate,
                        "ot_applicable": ot_applicable,
                        "ot_rate": ot_rate,
                        "status": rate_status,
                    },
                )
                conn.commit()
                conn.close()
                st.success("Manpower rate saved.")
                st.rerun()

        conn = get_conn()
        st.dataframe(
            pd.read_sql_query(
                """
                SELECT rate_id, subcontractor_name, project_name, labour_type AS designation,
                       working_hours, rate AS daily_rate, ot_applicable, ot_rate, status
                FROM subcontractor_labour_rates
                ORDER BY id DESC
                """,
                conn,
            ),
            width="stretch",
            hide_index=True,
        )
        conn.close()
        _render_labour_rate_editor(subcontractors, project_options, designation_options)

    with tabs[2]:
        st.markdown("### BOQ / Measurement Based System")
        c1, c2, c3, c4 = st.columns(4)
        boq_project = c1.selectbox("Project", project_options, index=0, key="boq_project")
        boq_item = c2.text_input("BOQ Item", key="boq_item")
        boq_unit = c3.text_input("Unit", key="boq_unit")
        boq_subcontractor = c4.selectbox("Sub Contractor", subcontractors, index=0, key="boq_subcontractor")
        d1, d2 = st.columns(2)
        boq_rate = d1.number_input("Rate", min_value=0.0, step=100.0, key="boq_rate")
        boq_status = d2.selectbox("Status", ["Active", "Inactive"], key="boq_status")
        if st.button("SAVE BOQ RATE", type="primary", width="stretch", key="save_boq_rate"):
            if not boq_project or not boq_item.strip() or not boq_unit.strip() or not boq_subcontractor:
                st.error("Project, BOQ Item, Unit, and Sub Contractor are required.")
            else:
                boq_rate_id = generate_id("BQ", "subcontractor_boq_rates")
                conn = get_conn()
                conn.execute(
                    """
                    INSERT INTO subcontractor_boq_rates(
                        boq_rate_id, project_name, boq_item, unit, rate, subcontractor_name, status
                    ) VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        boq_rate_id,
                        boq_project,
                        boq_item.strip(),
                        boq_unit.strip(),
                        boq_rate,
                        boq_subcontractor,
                        boq_status,
                    ),
                )
                conn.commit()
                conn.close()
                st.success(f"BOQ rate saved. ID: {boq_rate_id}")
                st.rerun()

        conn = get_conn()
        st.dataframe(
            pd.read_sql_query(
                """
                SELECT boq_rate_id, project_name, boq_item, unit, rate, subcontractor_name, status
                FROM subcontractor_boq_rates
                ORDER BY id DESC
                """,
                conn,
            ),
            width="stretch",
            hide_index=True,
        )
        conn.close()
        _render_boq_rate_editor(subcontractors, project_options)

    with tabs[3]:
        st.markdown("### BOQ Quantity Entry")
        c1, c2, c3 = st.columns(3)
        boq_entry_date = c1.date_input("Entry Date", key="boq_entry_date")
        boq_entry_subcontractor = c2.selectbox("Sub Contractor", subcontractors, index=0, key="boq_entry_subcontractor")
        boq_entry_project = c3.selectbox("Project", project_options, index=0, key="boq_entry_project")
        boq_rates_df = load_subcontractor_boq_rates(boq_entry_subcontractor or None, boq_entry_project or None)
        boq_options = (
            {
                f"{row['boq_item']} | {row['unit']} | Rs {float(row['rate']):,.2f}": row
                for _, row in boq_rates_df.iterrows()
            }
            if not boq_rates_df.empty
            else {}
        )
        selected_boq = st.selectbox("BOQ Item", list(boq_options.keys()) if boq_options else [""])
        selected_boq_row = boq_options.get(selected_boq) if boq_options else None
        d1, d2, d3 = st.columns(3)
        boq_unit_display = d1.text_input(
            "Unit",
            value=str(selected_boq_row["unit"]) if selected_boq_row is not None else "",
            disabled=True,
            key="boq_entry_unit",
        )
        boq_rate_display = float(selected_boq_row["rate"]) if selected_boq_row is not None else 0.0
        d2.number_input(
            "Rate",
            value=boq_rate_display,
            disabled=True,
            key="boq_entry_rate",
        )
        boq_quantity = d3.number_input("Quantity", min_value=0.0, step=1.0, key="boq_entry_quantity")
        boq_amount = boq_quantity * boq_rate_display
        st.success(f"BOQ Amount: Rs {boq_amount:,.2f}")
        boq_entry_remarks = st.text_input("Remarks", key="boq_entry_remarks")
        if st.button("SAVE BOQ ENTRY", type="primary", width="stretch", key="save_boq_entry"):
            if selected_boq_row is None:
                st.error("Please select a BOQ item.")
            else:
                boq_entry_id = generate_id("BQE", "subcontractor_boq_entries")
                conn = get_conn()
                conn.execute(
                    """
                    INSERT INTO subcontractor_boq_entries(
                        boq_entry_id, entry_date, subcontractor_name, project_name, boq_item,
                        unit, rate, quantity, amount, remarks
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        boq_entry_id,
                        boq_entry_date.strftime(DATE_FMT),
                        str(selected_boq_row["subcontractor_name"]),
                        str(selected_boq_row["project_name"]),
                        str(selected_boq_row["boq_item"]),
                        str(selected_boq_row["unit"]),
                        boq_rate_display,
                        boq_quantity,
                        boq_amount,
                        boq_entry_remarks.strip(),
                    ),
                )
                conn.commit()
                conn.close()
                st.success(f"BOQ entry saved. ID: {boq_entry_id}")
                st.rerun()

        conn = get_conn()
        st.dataframe(
            pd.read_sql_query(
                """
                SELECT boq_entry_id, entry_date, subcontractor_name, project_name,
                       boq_item, unit, rate, quantity, amount
                FROM subcontractor_boq_entries
                ORDER BY id DESC
                """,
                conn,
            ),
            width="stretch",
            hide_index=True,
        )
        conn.close()

    with tabs[4]:
        st.markdown("### Sub Contractor Bill Generation")
        c1, c2 = st.columns(2)
        bill_subcontractor = c1.selectbox("Sub Contractor", subcontractors, index=0, key="bill_subcontractor")
        bill_month_date = c2.date_input("Bill Month", key="bill_month_date")
        bill_month = bill_month_date.strftime("%m/%Y")
        if bill_subcontractor:
            bill_preview = subcontractor_bill_preview(bill_subcontractor, bill_month)
            p1, p2, p3, p4, p5 = st.columns(5)
            p1.metric("Labour", f"Rs {bill_preview['labour_amount']:,.2f}")
            p2.metric("OT", f"Rs {bill_preview['ot_amount']:,.2f}")
            p3.metric("BOQ", f"Rs {bill_preview['boq_amount']:,.2f}")
            p4.metric("Advances", f"Rs {bill_preview['advance_amount']:,.2f}")
            p5.metric("Net Bill", f"Rs {bill_preview['net_amount']:,.2f}")
            bill_remarks = st.text_input("Bill Remarks", key="subcontractor_bill_remarks")
            if st.button("GENERATE SUB CONTRACTOR BILL", type="primary", width="stretch", key="generate_subcontractor_bill"):
                bill_id = generate_id("SBL", "subcontractor_bills")
                conn = get_conn()
                conn.execute(
                    """
                    INSERT INTO subcontractor_bills(
                        bill_id, bill_date, bill_month, subcontractor_name, bill_type,
                        labour_amount, ot_amount, boq_amount, advance_amount, total_amount, net_amount, remarks, status
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        bill_id,
                        datetime.now().strftime(DATE_FMT),
                        bill_preview["bill_month"],
                        bill_subcontractor,
                        "Combined",
                        bill_preview["labour_amount"],
                        bill_preview["ot_amount"],
                        bill_preview["boq_amount"],
                        bill_preview["advance_amount"],
                        bill_preview["total_amount"],
                        bill_preview["net_amount"],
                        bill_remarks.strip(),
                        "Generated",
                    ),
                )
                conn.commit()
                conn.close()
                st.success(f"Sub contractor bill generated. ID: {bill_id}")
                st.rerun()

        conn = get_conn()
        st.dataframe(
            pd.read_sql_query(
                """
                SELECT bill_id, bill_date, bill_month, subcontractor_name,
                       labour_amount, boq_amount, advance_amount, total_amount, net_amount, status
                FROM subcontractor_bills
                ORDER BY id DESC
                """,
                conn,
            ),
            width="stretch",
            hide_index=True,
        )
        conn.close()


def _attendance_widget_suffix(edit_id):
    return f"_e{int(edit_id)}" if edit_id else "_new"


def _attendance_kpi_cards_html(kpis):
    cards = [
        ("Total Workers Today", kpis.get("total_workers", 0), "Active employees", "accent-blue"),
        ("Present", kpis.get("present", 0), f"Entries on {kpis.get('date', '')}", "accent-green"),
        ("Absent", kpis.get("absent", 0), "Marked absent today", "accent-red"),
        ("Late", kpis.get("late", 0), "In after 08:30", "accent-orange"),
        ("OT Workers", kpis.get("ot_workers", 0), "OT hours recorded", "accent-purple"),
        ("Attendance %", f"{kpis.get('attendance_pct', 0):g}%", "Present vs active roster", "accent-yellow"),
    ]
    parts = ['<div class="maxek-attendance-kpi-grid">']
    for label, value, helper, accent in cards:
        cls = f"maxek-attendance-kpi-card {accent}".strip()
        parts.append(
            f'<div class="{cls}">'
            f'<div class="maxek-attendance-kpi-label">{label}</div>'
            f'<div class="maxek-attendance-kpi-value">{value}</div>'
            f'<div class="maxek-attendance-kpi-helper">{helper}</div>'
            f"</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def _attendance_daily_wage(employee):
    wage = float(employee.get("salary_amount") or 0)
    if (employee.get("employee_type") or "").strip() == "Monthly Staff" and wage:
        return round(wage / 26, 2)
    return wage


def _attendance_standard_hours(working_category_label, fallback=8.0):
    text = str(working_category_label or "").strip()
    if "10" in text:
        return 10.0
    return float(fallback or 8.0)


def _attendance_pay_preview(
    employee,
    status,
    total_hours,
    ot_hours,
    applied_rate,
    applied_ot_rate,
    ot_allowed,
    fixed_working_hours=8.0,
):
    """Day pay preview for salary panel and day total field."""
    if (employee.get("employee_type") or "") == "Sub Contractor Worker":
        labour, ot_pay, gross = subcontractor_timesheet_day_amount(
            status, applied_rate, ot_hours, applied_ot_rate, ot_allowed
        )
        return {
            "daily_wage": float(applied_rate or 0),
            "hourly_rate": float(applied_ot_rate or 0) if ot_allowed else 0.0,
            "base_pay": labour,
            "ot_pay": ot_pay,
            "gross": gross,
            "preview_ot_hours": float(ot_hours or 0),
        }

    daily_wage = _attendance_daily_wage(employee)
    standard = float(fixed_working_hours or 8.0)
    stored_ot = float(employee.get("ot_rate") or 0) or None
    pay = calculate_daily_pay(daily_wage, standard, total_hours, stored_ot)
    return {
        "daily_wage": daily_wage,
        "hourly_rate": pay["hourly_rate"],
        "base_pay": pay["base_pay"],
        "ot_pay": pay["ot_pay"],
        "gross": pay["gross_pay"],
        "preview_ot_hours": pay["ot_hours"],
    }


def _attendance_salary_preview_html(employee, pay_preview, total_hours, ot_hours, attendance_date):
    adv = get_employee_advance_summary(employee.get("employee_id"), 0.0)
    advance_ded = min(float(adv.get("open_balance") or 0), float(pay_preview.get("gross") or 0))
    food_monthly = float(employee.get("food_allowance") or 0)
    food_ded = round(food_monthly / 26, 2) if food_monthly else 0.0
    fine_ded = 0.0
    gross = float(pay_preview.get("gross") or 0)
    net = max(0.0, gross - advance_ded - food_ded - fine_ded)

    cells = [
        _payroll_grid_cell("Daily wage", f"Rs {pay_preview.get('daily_wage', 0):,.2f}"),
        _payroll_grid_cell("Worked hours", format_decimal_hours(total_hours)),
        _payroll_grid_cell("OT hours", format_decimal_hours(ot_hours)),
        _payroll_grid_cell("Hourly rate", f"Rs {pay_preview.get('hourly_rate', 0):,.2f}"),
        _payroll_grid_cell("Gross (day)", f"Rs {gross:,.2f}"),
        _payroll_grid_cell("Advance ded.", f"Rs {advance_ded:,.2f}"),
        _payroll_grid_cell("Food ded.", f"Rs {food_ded:,.2f}"),
        _payroll_grid_cell("Fine ded.", f"Rs {fine_ded:,.2f}"),
    ]
    return f"""
        <div class="maxek-attendance-salary-panel">
          <h4>Salary preview · {attendance_date.strftime(DATE_FMT)}</h4>
          <div class="maxek-attendance-salary-grid">
            {''.join(cells)}
            <div class="maxek-attendance-net">
              <span>Net payable (estimate)</span>
              <strong>Rs {net:,.2f}</strong>
            </div>
          </div>
        </div>
        """


def _render_attendance_salary_preview(employee, pay_preview, total_hours, ot_hours, attendance_date):
    st.markdown(
        _attendance_salary_preview_html(employee, pay_preview, total_hours, ot_hours, attendance_date),
        unsafe_allow_html=True,
    )
    st.caption("Fine deductions are applied in payroll when configured.")


def _persist_attendance_entry(
    employee,
    edit_id,
    project_name,
    attendance_date,
    status,
    in_time,
    out_time,
    break_time,
    remarks,
    fixed_working_hours,
    applied_rate,
    applied_ot_rate,
    ot_allowed,
    sub_contractor,
    working_hours_label="",
):
    """Save or update one attendance row; returns (ok, message)."""
    try:
        in_time, out_time = _normalize_attendance_times(in_time, out_time)
    except ValueError as exc:
        return False, str(exc)
    if status in ("Present", "Half Day") and (not in_time or not out_time):
        return False, "In Time and Out Time are required for Present / Half Day."

    total_hours, ot_hours = _safe_attendance_hours(
        in_time, out_time, break_time, fixed_working_hours, ot_allowed
    )
    conn = get_conn()
    attendance_date_str = attendance_date.strftime(DATE_FMT)
    if not edit_id:
        duplicate = conn.execute(
            "SELECT id FROM attendance WHERE employee_id=? AND attendance_date=?",
            (employee["employee_id"], attendance_date_str),
        ).fetchone()
        if duplicate:
            conn.close()
            return False, "Attendance already saved for this employee on this date."
    else:
        duplicate = conn.execute(
            "SELECT id FROM attendance WHERE employee_id=? AND attendance_date=? AND id != ?",
            (employee["employee_id"], attendance_date_str, edit_id),
        ).fetchone()
        if duplicate:
            conn.close()
            return False, "Another timesheet already exists for this date."

    attendance_category, payment_type, holiday_name = infer_attendance_category(
        employee, attendance_date, status
    )
    if employee.get("employee_type") == "Sub Contractor Worker":
        sub_contractor = resolve_subcontractor_name(
            sub_contractor or employee.get("company_or_subcontractor") or ""
        )

    fields = {
        "project_name": project_name,
        "attendance_date": attendance_date_str,
        "in_time": in_time,
        "out_time": out_time,
        "break_hours": break_time,
        "total_hours": total_hours,
        "ot_hours": ot_hours,
        "status": status,
        "remarks": remarks,
        "worked_hours": total_hours,
        "overtime": ot_hours,
        "start_time": in_time,
        "end_time": out_time,
        "attendance_category": attendance_category,
        "payment_type": payment_type,
        "holiday_name": holiday_name,
        "fixed_working_hours": fixed_working_hours,
        "applied_rate": applied_rate,
        "applied_ot_rate": applied_ot_rate,
    }
    day_labour, day_ot, day_total = subcontractor_timesheet_day_amount(
        status, applied_rate, ot_hours, applied_ot_rate, ot_allowed
    )

    if edit_id:
        update_attendance_record(edit_id, fields)
        conn.close()
        if employee.get("employee_type") == "Sub Contractor Worker":
            return (
                True,
                f"Timesheet updated. Worked {format_decimal_hours(total_hours)} · "
                f"OT {format_decimal_hours(ot_hours)} · Pay Rs {day_total:,.2f}.",
            )
        return (
            True,
            f"Timesheet updated. Worked {format_decimal_hours(total_hours)} · "
            f"OT {format_decimal_hours(ot_hours)}.",
        )

    conn.execute(
        """
        INSERT INTO attendance(
            employee_id, employee_name, employee_type, department, designation,
            project_name, sub_contractor, attendance_date, in_time, out_time,
            break_hours, total_hours, ot_hours, status, remarks,
            worker_id, worker_name, start_time, end_time, worked_hours, overtime, work_description,
            fixed_working_hours, applied_rate, applied_ot_rate, attendance_category, payment_type, holiday_name
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            employee["employee_id"],
            employee["employee_name"],
            employee["employee_type"],
            employee.get("department", ""),
            employee.get("designation", ""),
            project_name,
            sub_contractor,
            attendance_date_str,
            in_time,
            out_time,
            break_time,
            total_hours,
            ot_hours,
            status,
            remarks,
            employee["employee_id"],
            employee["employee_name"],
            in_time,
            out_time,
            total_hours,
            ot_hours,
            remarks,
            fixed_working_hours,
            applied_rate,
            applied_ot_rate,
            attendance_category,
            payment_type,
            holiday_name,
        ),
    )
    conn.commit()
    conn.close()
    if employee.get("employee_type") == "Sub Contractor Worker":
        return (
            True,
            f"Attendance saved. Worked {format_decimal_hours(total_hours)} · "
            f"OT {format_decimal_hours(ot_hours)} · "
            f"Pay Rs {day_total:,.2f} (day Rs {day_labour:,.2f} + OT Rs {day_ot:,.2f}).",
        )
    return (
        True,
        f"Attendance saved. Worked {format_decimal_hours(total_hours)} · "
        f"OT {format_decimal_hours(ot_hours)}.",
    )


def _format_attendance_hours_df(df: pd.DataFrame) -> pd.DataFrame:
    """Show total_hours / ot_hours as HH:MM in grids and Excel exports."""
    if df is None or df.empty:
        return df
    out = df.copy()
    for col in ("total_hours", "ot_hours", "worked_hours", "overtime"):
        if col in out.columns:
            out[col] = out[col].apply(format_decimal_hours)
    return out


def _normalize_attendance_times(in_time, out_time):
    """Parse flexible in/out times; returns (HH:MM, HH:MM) or raises ValueError."""
    in_raw = str(in_time or "").strip()
    out_raw = str(out_time or "").strip()
    if not in_raw and not out_raw:
        return "", ""
    try:
        in_norm = parse_flexible_time(in_raw, is_out_time=False) if in_raw else ""
        out_norm = parse_flexible_time(out_raw, is_out_time=True) if out_raw else ""
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if in_raw and not in_norm:
        raise ValueError("Invalid In Time.")
    if out_raw and not out_norm:
        raise ValueError("Invalid Out Time.")
    return in_norm, out_norm


def _safe_attendance_hours(in_time, out_time, break_time, fixed_hours, ot_allowed):
    if not str(in_time or "").strip() or not str(out_time or "").strip():
        return 0.0, 0.0
    try:
        in_norm, out_norm = _normalize_attendance_times(in_time, out_time)
        if not in_norm or not out_norm:
            return 0.0, 0.0
        return calculate_hours(in_norm, out_norm, break_time, fixed_hours, ot_allowed)
    except (ValueError, TypeError) as exc:
        st.session_state["attendance_hours_error"] = str(exc)
        return 0.0, 0.0


def _render_subcontractor_payment_panel(
    sub_contractor,
    project_name,
    designation,
    working_hours,
    status,
    total_hours,
    ot_hours,
    applied_rate,
    applied_ot_rate,
    ot_allowed,
    rate_card,
    attendance_date,
    fixed_working_hours,
):
    st.markdown("### Sub Contractor Payment (this timesheet)")
    if not sub_contractor:
        st.warning("No sub contractor linked on this worker. Set **Company / Sub Contractor** in Employee Master.")
        return
    sub_name = resolve_subcontractor_name(sub_contractor)
    if not rate_card:
        st.warning(
            f"No active manpower rate found for **{sub_name}** · project **{project_name or '—'}** · "
            f"**{designation or '—'}** · **{working_hours}**. "
            "Add it under **Sub Contractors → Manpower Rates**."
        )
    else:
        st.caption(
            f"Rate card: Rs {applied_rate:,.2f}/day · OT {'Yes' if ot_allowed else 'No'}"
            + (f" · Rs {applied_ot_rate:,.2f}/hr OT" if ot_allowed else "")
            + f" · {fixed_working_hours:g}h standard shift"
        )
    labour_pay, ot_pay, total_pay = subcontractor_timesheet_day_amount(
        status, applied_rate, ot_hours, applied_ot_rate, ot_allowed
    )
    p1, p2, p3, p4, p5 = st.columns(5)
    p1.metric("Worked Hours", format_decimal_hours(total_hours))
    p2.metric("OT Hours", format_decimal_hours(ot_hours))
    p3.metric("Day Pay", f"Rs {labour_pay:,.2f}")
    p4.metric("OT Pay", f"Rs {ot_pay:,.2f}")
    p5.metric("Total Pay", f"Rs {total_pay:,.2f}")
    if status in ("Present", "Half Day") and total_hours <= 0:
        st.info("Enter **In Time** and **Out Time** (e.g. 8 and 5) to calculate OT hours.")
    bill_month = attendance_date.strftime("%m/%Y")
    preview = subcontractor_bill_preview(sub_name, bill_month)
    st.markdown(f"#### Sub contractor month total — {bill_month}")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Labour", f"Rs {preview['labour_amount']:,.2f}")
    m2.metric("OT", f"Rs {preview['ot_amount']:,.2f}")
    m3.metric("BOQ", f"Rs {preview['boq_amount']:,.2f}")
    m4.metric("Advances", f"Rs {preview['advance_amount']:,.2f}")
    m5.metric("Net Bill", f"Rs {preview['net_amount']:,.2f}")
    st.caption("Generate formal bill under **Sub Contractors → Bills** tab.")


def page_attendance():
    st.markdown('<div class="maxek-attendance-page">', unsafe_allow_html=True)
    kpis = get_today_attendance_kpis()

    render_page_breadcrumbs(
        "Home",
        "HR & Payroll",
        "Attendance Entry",
        title="Attendance Entry",
        subtitle="Present · Absent · Leave · Half Day — weekly off and holidays flow to payroll automatically.",
    )

    st.markdown(_attendance_kpi_cards_html(kpis), unsafe_allow_html=True)

    st.markdown('<div class="maxek-page-toolbar-wrap maxek-toolbar-attendance">', unsafe_allow_html=True)
    qa = st.columns(5)
    draft_quick = qa[0].button("Save Draft", key="attendance_qa_draft", width="stretch")
    submit_quick = qa[1].button("Submit", key="attendance_qa_submit", width="stretch")
    if qa[2].button("Approve", key="attendance_qa_approve", width="stretch"):
        st.info("Approval workflow is managed under Payroll.")
    if qa[3].button("Generate Salary", key="attendance_qa_salary", width="stretch"):
        st.session_state.page = "hr_payroll"
        st.rerun()
    if qa[4].button("Print", key="attendance_qa_print", width="stretch"):
        st.info("Print/export will be available in a future update.")
    st.markdown("</div>", unsafe_allow_html=True)

    employee_options = load_employee_options()
    employee_map = {f"{employee_id} - {employee_name}": employee_id for employee_id, employee_name in employee_options}
    if not employee_map:
        st.warning("Add employees first.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    pick_labels = list(employee_map.keys())
    if st.session_state.get("attendance_employee_pick") not in pick_labels:
        st.session_state.pop("attendance_employee_pick", None)

    employee = None
    employee_id = None
    edit_id = st.session_state.get("attendance_edit_id")
    edit_record = None

    st.markdown('<div class="maxek-attendance-card maxek-attendance-form-card">', unsafe_allow_html=True)
    st.markdown('<div class="maxek-attendance-card-title">Timesheet entry</div>', unsafe_allow_html=True)

    st.markdown('<div class="maxek-attendance-layout">', unsafe_allow_html=True)
    form_col, preview_col = st.columns([2.8, 1.2], gap="medium")

    with form_col:
        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        selected = r1c1.selectbox("Employee", pick_labels, key="attendance_employee_pick")
        employee_id = employee_map[selected]
        previous_employee_id = st.session_state.get("attendance_active_employee_id")
        if previous_employee_id is not None and previous_employee_id != employee_id:
            st.session_state["attendance_active_employee_id"] = employee_id
            st.session_state.pop("attendance_edit_id", None)
            st.rerun()
        st.session_state["attendance_active_employee_id"] = employee_id

        employee = get_employee(employee_id)
        if not employee:
            st.error("Employee not found.")
            st.markdown("</div></div>", unsafe_allow_html=True)
            return

        if edit_id:
            edit_record = get_attendance_record(edit_id)
            rec_emp = (edit_record or {}).get("employee_id") or (edit_record or {}).get("worker_id")
            if not edit_record or str(rec_emp) != str(employee_id):
                st.session_state.pop("attendance_edit_id", None)
                edit_id = None
                edit_record = None

        project_names = [""] + load_project_names()
        project_default = (
            (edit_record.get("project_name") if edit_record else employee.get("project_name")) or ""
        )
        if project_default and project_default not in project_names:
            project_names = project_names + [project_default]
        project_index = project_names.index(project_default) if project_default in project_names else 0

        status_default = (
            edit_record.get("status") if edit_record else ATTENDANCE_STATUSES[0]
        ) or ATTENDANCE_STATUSES[0]
        status_index = ATTENDANCE_STATUSES.index(status_default) if status_default in ATTENDANCE_STATUSES else 0

        date_default = (
            _parse_db_date(edit_record.get("attendance_date"))
            if edit_record
            else date.today()
        ) or date.today()

        in_default = (
            edit_record.get("in_time") or edit_record.get("start_time") or ""
            if edit_record
            else ATTENDANCE_DEFAULT_IN_TIME
        )
        out_default = (
            edit_record.get("out_time") or edit_record.get("end_time") or ""
            if edit_record
            else ATTENDANCE_DEFAULT_OUT_TIME
        )
        break_default = (
            float(edit_record.get("break_hours") or 0)
            if edit_record
            else ATTENDANCE_DEFAULT_BREAK_HOURS
        )
        remarks_default = (edit_record.get("remarks") or "") if edit_record else ""

        fwh = float(edit_record.get("fixed_working_hours") or 8) if edit_record else 8.0
        wh_default = f"{int(fwh)} Hours"
        working_categories = ["8 Hours", "10 Hours"]
        if wh_default == "12 Hours":
            working_categories = ["8 Hours", "10 Hours", "12 Hours"]
        if wh_default not in working_categories:
            wh_default = "8 Hours"
        wh_index = working_categories.index(wh_default)

        widget_suffix = _attendance_widget_suffix(edit_id)
        if edit_id:
            st.markdown(
                f'<div class="maxek-attendance-edit-banner">Editing timesheet #{edit_id} · '
                f"{date_default.strftime(DATE_FMT)} · {status_default} · {project_default or '—'}"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("Cancel edit", key="attendance_cancel_edit", width="content"):
                st.session_state.pop("attendance_edit_id", None)
                st.rerun()

        project_name = r1c2.selectbox(
            "Project",
            project_names,
            index=project_index,
            key=f"attendance_project{widget_suffix}",
        )
        attendance_date = r1c3.date_input(
            "Date",
            value=date_default,
            key=f"attendance_entry_date{widget_suffix}",
        )
        status = r1c4.selectbox(
            "Status",
            ATTENDANCE_STATUSES,
            index=status_index,
            key=f"attendance_entry_status{widget_suffix}",
        )

        r2c1, r2c2, r2c3, r2c4 = st.columns(4)
        in_time = r2c1.text_input(
            "In Time",
            value=in_default,
            key=f"attendance_in_time{widget_suffix}",
            placeholder="8 or 08:00",
        )
        out_time = r2c2.text_input(
            "Out Time",
            value=out_default,
            key=f"attendance_out_time{widget_suffix}",
            placeholder="5 or 17:00",
        )
        break_time = r2c3.number_input(
            "Break Hours",
            min_value=0.0,
            step=0.5,
            value=break_default,
            key=f"attendance_break_hours{widget_suffix}",
        )
        working_hours = r2c4.selectbox(
            "Working Category",
            working_categories,
            index=wh_index,
            key=f"attendance_working_hours{widget_suffix}",
        )

    fixed_working_hours = _attendance_standard_hours(working_hours, 8.0)
    applied_rate = float(employee.get("salary_amount") or 0)
    applied_ot_rate = float(employee.get("ot_rate") or 0)
    ot_allowed = (employee.get("ot_applicable") or "").lower() == "yes"
    sub_contractor = (
        employee.get("company_or_subcontractor", "")
        if employee.get("employee_type") == "Sub Contractor Worker"
        else ""
    )
    rate_card = None
    if employee.get("employee_type") == "Sub Contractor Worker":
        sub_contractor = resolve_subcontractor_name(sub_contractor or employee.get("company_or_subcontractor") or "")
        rate_card = load_subcontractor_labour_rate(
            sub_contractor,
            project_name,
            employee.get("designation", ""),
            working_hours,
        )
        fixed_working_hours = (
            float(rate_card.get("fixed_hours") or working_hours.split()[0])
            if rate_card
            else float(working_hours.split()[0])
        )
        applied_rate = (
            float(rate_card.get("rate") or employee.get("salary_amount") or 0)
            if rate_card
            else float(employee.get("salary_amount") or 0)
        )
        ot_allowed = str(rate_card.get("ot_applicable") or "No").lower() == "yes" if rate_card else ot_allowed
        applied_ot_rate = (
            float(rate_card.get("ot_rate") or 0)
            if rate_card
            else (applied_rate / fixed_working_hours if ot_allowed and fixed_working_hours else 0.0)
        )
    elif not applied_ot_rate and ot_allowed and fixed_working_hours:
        applied_ot_rate = hourly_rate(_attendance_daily_wage(employee), fixed_working_hours)

    st.session_state.pop("attendance_hours_error", None)
    total_hours, ot_hours = _safe_attendance_hours(
        in_time, out_time, break_time, fixed_working_hours, ot_allowed
    )
    if st.session_state.get("attendance_hours_error"):
        st.warning(st.session_state["attendance_hours_error"])

    pay_preview = _attendance_pay_preview(
        employee,
        status,
        total_hours,
        ot_hours,
        applied_rate,
        applied_ot_rate,
        ot_allowed,
        fixed_working_hours,
    )
    day_total_display = pay_preview["gross"]

    attendance_category, payment_type, holiday_name = infer_attendance_category(
        employee, attendance_date, status
    )
    if attendance_category == "Holiday Worked":
        with form_col:
            st.info(f"Holiday worked: {holiday_name or 'Paid holiday'} — OT calculated automatically.")
    elif attendance_category == "Weekly Off Worked":
        with form_col:
            st.info("Weekly off day with attendance — counted as Weekly Off Worked with OT.")

    with form_col:
        r3c1, r3c2, r3c3, r3c4 = st.columns(4)
        r3c1.text_input(
            "Worked Hours",
            value=format_decimal_hours(total_hours),
            disabled=True,
            key=f"att_show_worked{widget_suffix}",
            help="Out − In − Break (HH:MM)",
        )
        r3c2.text_input(
            "OT Hours",
            value=format_decimal_hours(ot_hours),
            disabled=True,
            key=f"att_show_ot{widget_suffix}",
        )
        r3c3.text_input(
            "Hourly Rate",
            value=f"Rs {pay_preview.get('hourly_rate', 0):,.2f}",
            disabled=True,
            key=f"att_show_rate{widget_suffix}",
        )
        r3c4.text_input(
            "Day Total",
            value=f"Rs {day_total_display:,.2f}",
            disabled=True,
            key=f"att_show_pay{widget_suffix}",
        )

        remarks = st.text_input(
            "Remarks",
            value=remarks_default,
            key=f"attendance_remarks{widget_suffix}",
        )
        st.caption(
            "Worked = Out − In − Break. Under standard hours: pro-rata pay; at standard: full day; above: full day + OT. "
            "Times use shorthand (In **8**, Out **5** / **17**)."
        )
        try:
            preview_in, preview_out = _normalize_attendance_times(in_time, out_time)
            if preview_in or preview_out:
                st.caption(f"Saved as: In **{preview_in or '—'}** · Out **{preview_out or '—'}**")
        except ValueError as exc:
            st.warning(str(exc))

    with preview_col:
        _render_attendance_salary_preview(employee, pay_preview, total_hours, ot_hours, attendance_date)

    st.markdown("</div>", unsafe_allow_html=True)

    if employee.get("employee_type") == "Sub Contractor Worker":
        with form_col:
            _render_subcontractor_payment_panel(
                sub_contractor,
                project_name,
                employee.get("designation", ""),
                working_hours,
                status,
                total_hours,
                ot_hours,
                applied_rate,
                applied_ot_rate,
                ot_allowed,
                rate_card,
                attendance_date,
                fixed_working_hours,
            )

    st.markdown("</div>", unsafe_allow_html=True)

    with form_col:
        save_label = f"Update timesheet (#{edit_id})" if edit_id else "Save attendance"
        save_clicked = st.button(
            save_label, type="primary", width="stretch", key=f"attendance_save_btn{widget_suffix}"
        )
    if save_clicked or submit_quick or draft_quick:
        save_remarks = remarks
        if draft_quick and not save_clicked:
            draft_tag = "[Draft]"
            if draft_tag not in (save_remarks or ""):
                save_remarks = f"{draft_tag} {save_remarks}".strip()
        ok, message = _persist_attendance_entry(
            employee,
            edit_id,
            project_name,
            attendance_date,
            status,
            in_time,
            out_time,
            break_time,
            save_remarks,
            fixed_working_hours,
            applied_rate,
            applied_ot_rate,
            ot_allowed,
            sub_contractor,
            working_hours,
        )
        if ok:
            st.session_state.pop("attendance_edit_id", None)
            if draft_quick and not save_clicked:
                st.success(f"Draft saved. {message}")
            else:
                st.success(message)
            st.rerun()
        else:
            st.error(message)

    _render_attendance_timesheet_list(employee_id, employee)

    st.markdown('<div class="maxek-attendance-card">', unsafe_allow_html=True)
    st.markdown('<div class="maxek-attendance-card-title">Quick actions</div>', unsafe_allow_html=True)
    qa_row = st.columns(4)
    if qa_row[0].button("Mark all present", key="att_qa_all_present", width="stretch"):
        st.info("Bulk mark present will be available in a future update.")
    if qa_row[1].button("Export timesheet", key="att_qa_export", width="stretch"):
        st.info("Export uses the Excel download on Payroll reports.")
    if qa_row[2].button("Open payroll", key="att_qa_payroll", width="stretch"):
        st.session_state.page = "hr_payroll"
        st.rerun()
    if qa_row[3].button("Employee master", key="att_qa_employee", width="stretch"):
        st.session_state.page = "master_employee"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def _attendance_row_amount(row, employee):
    ot_allowed_row = float(row.get("applied_ot_rate") or 0) > 0
    if (employee.get("employee_type") or "") == "Sub Contractor Worker":
        _, _, total = subcontractor_timesheet_day_amount(
            row.get("status"),
            row.get("applied_rate"),
            row.get("ot_hours"),
            row.get("applied_ot_rate"),
            ot_allowed_row,
        )
        return total
    pay = _attendance_pay_preview(
        employee,
        row.get("status"),
        float(row.get("total_hours") or 0),
        float(row.get("ot_hours") or 0),
        float(row.get("applied_rate") or 0),
        float(row.get("applied_ot_rate") or 0),
        ot_allowed_row,
        float(row.get("fixed_working_hours") or 8),
    )
    return pay["gross"]


def _render_attendance_timesheet_list(employee_id, employee):
    st.markdown('<div class="maxek-attendance-table-wrap">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="maxek-attendance-card-title">Saved timesheets — {employee.get("employee_name", "")}</div>',
        unsafe_allow_html=True,
    )
    conn = get_conn()
    history_df = pd.read_sql_query(
        """
        SELECT id, attendance_date, project_name, in_time, out_time, break_hours,
               total_hours, ot_hours, applied_rate, applied_ot_rate, fixed_working_hours,
               attendance_category, status, remarks
        FROM attendance
        WHERE employee_id = ?
        ORDER BY attendance_date DESC, id DESC
        LIMIT 80
        """,
        conn,
        params=(employee_id,),
    )
    conn.close()
    if history_df.empty:
        st.caption("No timesheet entries for this employee yet.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    table_rows = []
    for _, row in history_df.iterrows():
        amount = _attendance_row_amount(row, employee)
        table_rows.append(
            {
                "Date": row["attendance_date"],
                "Project": row["project_name"] or "—",
                "In": row["in_time"] or "—",
                "Out": row["out_time"] or "—",
                "Worked": format_decimal_hours(row["total_hours"]),
                "OT": format_decimal_hours(row["ot_hours"]),
                "Amount": f"Rs {amount:,.2f}",
                "Status": row["status"],
                "Actions": "Edit · View",
                "_id": int(row["id"]),
            }
        )
    st.dataframe(
        pd.DataFrame(table_rows).drop(columns=["_id"]),
        width="stretch",
        hide_index=True,
    )

    options = {
        f"{r['Date']} · {r['Status']} · {r['Project']} · {r['Worked']}": r["_id"]
        for r in table_rows
    }
    pick_key = "attendance_ts_pick"
    if st.session_state.get(pick_key) not in options:
        st.session_state.pop(pick_key, None)
    view_key = "attendance_ts_view_id"
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    pick = c1.selectbox("Select row", list(options.keys()), key=pick_key)
    ts_id = options[pick]

    if c2.button("Edit", width="stretch", key="attendance_ts_edit"):
        st.session_state["attendance_edit_id"] = int(ts_id)
        st.session_state.pop(view_key, None)
        st.rerun()

    if c3.button("View", width="stretch", key="attendance_ts_view"):
        st.session_state[view_key] = int(ts_id)

    if c4.button("Delete", width="stretch", key="attendance_ts_delete"):
        start_delete_confirm("attendance_ts", pick, ts_id)

    view_id = st.session_state.get(view_key)
    if view_id:
        rec = get_attendance_record(view_id)
        if rec:
            with st.expander(f"Timesheet detail #{view_id}", expanded=True):
                st.markdown(
                    f"**{rec.get('attendance_date')}** · {rec.get('status')} · "
                    f"{rec.get('project_name') or '—'}"
                )
                st.write(
                    f"In **{rec.get('in_time') or '—'}** · Out **{rec.get('out_time') or '—'}** · "
                    f"Worked **{format_decimal_hours(rec.get('total_hours'))}** · "
                    f"OT **{format_decimal_hours(rec.get('ot_hours'))}**"
                )
                if rec.get("remarks"):
                    st.caption(rec.get("remarks"))
                if rec.get("attendance_category"):
                    st.caption(f"Category: {rec.get('attendance_category')}")

    def _do_delete_ts(record_id):
        delete_attendance_record(record_id)
        if int(st.session_state.get("attendance_edit_id") or 0) == int(record_id):
            st.session_state.pop("attendance_edit_id", None)
        st.session_state.pop(pick_key, None)
        st.session_state.pop(view_key, None)
        st.success("Timesheet deleted.")
        st.rerun()

    render_delete_confirm_dialog("attendance_ts", _do_delete_ts, message="Delete this timesheet entry?")
    st.markdown("</div>", unsafe_allow_html=True)


def _payroll_grid_cell(label, value):
    return f"""
    <div class="maxek-payroll-cell">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
    """


def _render_payroll_summary(summary, net_salary=None, deductions=0.0):
    gross = (
        float(summary.get("normal_salary_amount") or 0)
        + float(summary.get("weekly_off_paid_amount") or 0)
        + float(summary.get("holiday_paid_amount") or 0)
        + float(summary.get("ot_amount") or 0)
    )
    if net_salary is None:
        net_salary = max(0.0, gross - float(deductions or 0))

    attendance_cells = "".join(
        [
            _payroll_grid_cell("Total month days", int(summary.get("total_month_days") or 0)),
            _payroll_grid_cell("Worked days", int(summary.get("worked_days") or 0)),
            _payroll_grid_cell("Leave days", int(summary.get("leave_days") or 0)),
            _payroll_grid_cell("Half days", int(summary.get("half_days") or 0)),
            _payroll_grid_cell("Absent days", int(summary.get("absent_days") or 0)),
            _payroll_grid_cell("Paid weekly off", int(summary.get("paid_weekly_off_days") or 0)),
            _payroll_grid_cell("Paid holidays", int(summary.get("paid_holiday_days") or 0)),
        ]
    )
    hour_cells = "".join(
        [
            _payroll_grid_cell("Worked hours", summary.get("total_worked_hours") or 0),
            _payroll_grid_cell("Total OT hours", summary.get("total_ot_hours") or 0),
            _payroll_grid_cell("Holiday OT", summary.get("holiday_ot_hours") or 0),
            _payroll_grid_cell("Weekly off OT", summary.get("weekly_off_ot_hours") or 0),
        ]
    )
    if float(summary.get("ot_held_hours") or 0) > 0:
        hour_cells += _payroll_grid_cell("OT held (not paid)", summary.get("ot_held_hours"))

    salary_cells = "".join(
        [
            _payroll_grid_cell("Normal salary", f"Rs {summary.get('normal_salary_amount', 0):,.2f}"),
            _payroll_grid_cell("Weekly off paid", f"Rs {summary.get('weekly_off_paid_amount', 0):,.2f}"),
            _payroll_grid_cell("Holiday paid", f"Rs {summary.get('holiday_paid_amount', 0):,.2f}"),
            _payroll_grid_cell("OT amount", f"Rs {summary.get('ot_amount', 0):,.2f}"),
            _payroll_grid_cell("Deductions", f"Rs {float(deductions or 0):,.2f}"),
            _payroll_grid_cell("Gross salary", f"Rs {gross:,.2f}"),
        ]
    )

    html = f"""
    <div class="maxek-payroll-board">
      <div class="maxek-payroll-panel">
        <h4>Attendance summary</h4>
        <div class="maxek-payroll-grid">{attendance_cells}</div>
      </div>
      <div class="maxek-payroll-panel">
        <h4>Hour summary</h4>
        <div class="maxek-payroll-grid">{hour_cells}</div>
      </div>
      <div class="maxek-payroll-panel">
        <h4>Salary summary</h4>
        <div class="maxek-payroll-grid">{salary_cells}</div>
      </div>
    </div>
    <div class="maxek-payroll-net">
      <span>Net salary payable</span>
      <strong>Rs {net_salary:,.2f}</strong>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def _render_payroll_advance_summary(employee_id, payroll_month, current_deduction=0.0):
    """Read-only advance info for payroll (entries are in Finance → Staff Advance)."""
    ledger = get_employee_advance_ledger(employee_id, payroll_month)
    summary = get_employee_advance_summary(employee_id, current_deduction)

    st.markdown("#### Advance summary (read-only)")
    st.caption("Staff advances are created in **Finance → Staff Advance**. Payroll only applies deductions.")

    if ledger.get("last_paid_month"):
        st.markdown(
            f'<div class="maxek-advance-banner">'
            f"<strong>Last salary paid:</strong> {ledger['last_paid_month']} "
            f"on {ledger.get('last_paid_date') or '—'} "
            f"(Rs {ledger.get('last_paid_amount', 0):,.2f})"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="maxek-advance-summary">
          <div class="maxek-advance-sum-row">
            <span>Advance taken</span><strong>Rs {summary['advance_taken']:,.2f}</strong>
          </div>
          <div class="maxek-advance-sum-row">
            <span>Already deducted</span><strong>Rs {summary['already_deducted']:,.2f}</strong>
          </div>
          <div class="maxek-advance-sum-row">
            <span>Previous balance (open)</span><strong>Rs {summary['previous_balance']:,.2f}</strong>
          </div>
          <div class="maxek-advance-sum-row highlight">
            <span>Current deduction</span><strong>Rs {summary['current_deduction']:,.2f}</strong>
          </div>
          <div class="maxek-advance-sum-row">
            <span>Balance remaining</span><strong>Rs {summary['balance_remaining']:,.2f}</strong>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    open_rows = ledger.get("open_advances") or []
    if open_rows:
        st.caption("Open paid advances (awaiting payroll deduction):")
        show_cols = ["advance_id", "advance_date", "amount", "payment_mode", "reason", "remarks", "status"]
        df = pd.DataFrame(open_rows)
        cols = [c for c in show_cols if c in df.columns]
        st.dataframe(df[cols] if cols else df, width="stretch", hide_index=True)

    return {**ledger, **summary}


def _payroll_month_year_selectors(key_prefix="payroll"):
    months = list(calendar.month_name)[1:]
    years = [str(y) for y in range(datetime.now().year - 2, datetime.now().year + 2)]
    c1, c2 = st.columns(2)
    month_name = c1.selectbox("Month", months, index=datetime.now().month - 1, key=f"{key_prefix}_month")
    year = c2.selectbox("Year", years, index=years.index(str(datetime.now().year)), key=f"{key_prefix}_year")
    month_num = months.index(month_name) + 1
    return f"{month_num:02d}/{year}"


PAYROLL_TYPE_FILTER_OPTIONS = [
    "All",
    "Monthly Staff",
    "Daily Wage Staff",
    "Company Staff",
    "Sub Contractor Worker",
    "Site Worker",
]


def _payroll_needs_period_dates(employee_type: str) -> bool:
    return (employee_type or "").strip() in (
        "Daily Wage Staff",
        "Sub Contractor Worker",
        "Site Worker",
    )


def _payroll_resolve_person(employee_id: str) -> dict | None:
    """Employee master row, or site worker profile keyed by worker_id."""
    employee = get_employee(employee_id)
    if employee:
        return employee
    try:
        from modules.worker_payroll_db import get_worker

        worker = get_worker(employee_id)
    except Exception:
        worker = None
    if not worker:
        return None
    return {
        "employee_id": worker.get("worker_id") or employee_id,
        "employee_name": worker.get("worker_name") or "",
        "employee_type": "Site Worker",
        "hour_category": worker.get("hour_category"),
        "daily_wage_rate": worker.get("daily_wage_rate"),
        "ot_rate": worker.get("ot_rate"),
    }


def _adapt_worker_period_summary(raw: dict, person: dict, payroll_month: str, period_start, period_end) -> dict:
    gross = float(raw.get("gross_salary") or 0)
    ot_amount = float(raw.get("ot_amount") or 0)
    base = float(raw.get("base_salary") or max(0.0, gross - ot_amount))
    ps = period_start.strftime(DATE_FMT) if period_start else ""
    pe = period_end.strftime(DATE_FMT) if period_end else ""
    return {
        "employee_id": person.get("employee_id") or "",
        "employee_name": person.get("employee_name") or "",
        "employee_type": "Site Worker",
        "payroll_month": payroll_month or raw.get("payroll_month") or "",
        "payroll_year": (payroll_month or "").split("/")[-1] if payroll_month else "",
        "payroll_period_start": ps,
        "payroll_period_end": pe,
        "worked_days": int(raw.get("worked_days") or 0),
        "leave_days": 0,
        "half_days": 0,
        "absent_days": 0,
        "paid_weekly_off_days": 0,
        "paid_holiday_days": 0,
        "total_worked_hours": float(raw.get("worked_hours") or 0),
        "total_ot_hours": float(raw.get("ot_hours") or 0),
        "holiday_ot_hours": 0.0,
        "weekly_off_ot_hours": 0.0,
        "normal_ot_hours": float(raw.get("ot_hours") or 0),
        "ot_amount": ot_amount,
        "ot_held_hours": 0.0,
        "normal_salary_amount": base,
        "weekly_off_paid_amount": 0.0,
        "holiday_paid_amount": 0.0,
        "normal_ot_amount": ot_amount,
        "deductions": 0.0,
        "net_salary": gross,
        "payable_days": float(raw.get("worked_days") or 0),
        "day_lines": raw.get("day_lines") or [],
    }


def _payroll_employee_label_map(type_filter="All"):
    employee_map = {}
    filt = None if type_filter in (None, "", "All") else type_filter
    for row in load_payroll_employee_options(employee_type_filter=filt):
        if len(row) >= 3:
            employee_id, employee_name, employee_type = row[0], row[1], row[2]
            label = f"{employee_id} - {employee_name} ({employee_type})"
        else:
            employee_id, employee_name = row[0], row[1]
            label = f"{employee_id} - {employee_name}"
        employee_map[label] = employee_id
    return employee_map


def _payroll_staff_label_map():
    return _payroll_employee_label_map("All")


def _load_payroll_records_df(employee_id=None, limit=200):
    conn = get_conn()
    sql = """
        SELECT p.payroll_id, p.employee_id,
               COALESCE(NULLIF(p.employee_name, ''), e.employee_name, p.employee_id) AS employee_name,
               p.payroll_month, p.net_salary, p.deductions,
               COALESCE(p.workflow_status, p.salary_status, '') AS status,
               COALESCE(p.payment_status, '') AS payment_status,
               p.paid_date
        FROM payroll p
        LEFT JOIN employees e ON e.employee_id = p.employee_id
    """
    params = []
    if employee_id:
        sql += " WHERE p.employee_id = ?"
        params.append(employee_id)
    sql += " ORDER BY p.id DESC LIMIT ?"
    params.append(limit)
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def _render_delete_saved_payroll(employee_id=None, key_prefix="payroll_del"):
    st.markdown("#### Delete saved payroll")
    st.caption(
        "Remove incorrect payroll rows (including old records wrongly marked PAID). "
        "Attendance/timesheet data is not deleted — only the payroll record."
    )
    df = _load_payroll_records_df(employee_id)
    if df.empty:
        st.info("No saved payroll records to delete.")
        return

    def _status_label(row):
        status = str(row.get("status") or "")
        payment = str(row.get("payment_status") or "")
        if payment.upper() == "PAID" or status.upper() == "PAID":
            return "PAID"
        return status or "—"

    options = {
        (
            f"{row['payroll_id']} | {row['payroll_month']} | {_status_label(row)} | "
            f"Rs {float(row['net_salary'] or 0):,.2f}"
        ): row["payroll_id"]
        for _, row in df.iterrows()
    }
    pick_key = f"{key_prefix}_pick"
    if st.session_state.get(pick_key) not in options:
        st.session_state.pop(pick_key, None)
    c1, c2 = st.columns([4, 1])
    pick = c1.selectbox("Select payroll to delete", list(options.keys()), key=pick_key)
    payroll_id = options[pick]

    def _do_delete(record_id):
        delete_payroll_record(record_id)
        st.session_state.pop(pick_key, None)
        st.success(f"Payroll {record_id} deleted.")
        st.rerun()

    if c2.button("DELETE", type="primary", width="stretch", key=f"{key_prefix}_btn"):
        row = df[df["payroll_id"] == payroll_id].iloc[0]
        label = f"{payroll_id} ({row['payroll_month']}, {_status_label(row)})"
        start_delete_confirm(f"{key_prefix}_confirm", label, payroll_id)

    render_delete_confirm_dialog(
        f"{key_prefix}_confirm",
        _do_delete,
        message="Delete this saved payroll record?",
    )

    st.dataframe(
        df[
            [
                "payroll_id",
                "employee_name",
                "payroll_month",
                "net_salary",
                "deductions",
                "status",
                "payment_status",
                "paid_date",
            ]
        ].rename(columns={"status": "workflow_status"}),
        width="stretch",
        hide_index=True,
    )


def _payroll_hr_fingerprint(employee_id, payroll_month, deductions, period_start=None, period_end=None):
    ps = period_start.strftime(DATE_FMT) if period_start else ""
    pe = period_end.strftime(DATE_FMT) if period_end else ""
    return f"{employee_id}|{payroll_month}|{float(deductions or 0):.2f}|{ps}|{pe}"


def _payroll_hr_is_verified(fingerprint: str) -> bool:
    return st.session_state.get("payroll_hr_verified_fp") == fingerprint


def _payroll_hr_mark_verified(fingerprint: str) -> None:
    st.session_state["payroll_hr_verified_fp"] = fingerprint


def _payroll_hr_clear_verified() -> None:
    st.session_state.pop("payroll_hr_verified_fp", None)


def _render_payroll_hr_step_indicator(verified: bool) -> None:
    if verified:
        st.caption("**Step 1:** Enter details ✓ → **Step 2:** Review & confirm *(current)*")
    else:
        st.caption("**Step 1:** Enter details *(current)* → **Step 2:** Review & confirm")


def page_payroll():
    st.subheader("Payroll")
    st.caption(
        "Process payroll for company staff, daily wage staff, sub-contractor workers, and site workers. "
        "Review the full breakdown before saving."
    )
    role = st.session_state.get("user_role", "Admin")
    hr_tab, md_tab, accounts_tab, advance_tab = st.tabs(
        ["Process Payroll", "MD Approval", "Accounts Payment", "Sub Contractor Advances"]
    )

    with hr_tab:
        type_filter = st.selectbox(
            "Employee type",
            PAYROLL_TYPE_FILTER_OPTIONS,
            key="payroll_type_filter",
        )
        employee_map = _payroll_employee_label_map(type_filter)
        if not employee_map:
            st.info(
                "No employees for this type. Add staff in **Employee Management** "
                "(Monthly / Daily / Sub Contractor Worker) or site workers under **Worker profiles**."
            )
        else:
            selected = st.selectbox("Employee", list(employee_map.keys()), key="payroll_employee_select")
            employee_id = employee_map[selected]
            person = _payroll_resolve_person(employee_id)
            if not person:
                st.warning("Could not load employee or worker profile.")
            else:
                employee_type = str(person.get("employee_type") or "").strip()
                employee_name = person.get("employee_name") or selected.split(" - ", 1)[-1]
                payroll_month = _payroll_month_year_selectors("hr_payroll")
                period_start = None
                period_end = None
                if _payroll_needs_period_dates(employee_type):
                    label = {
                        "Daily Wage Staff": "Daily wage staff",
                        "Sub Contractor Worker": "Sub-contractor worker",
                        "Site Worker": "Site worker (8hr/10hr)",
                    }.get(employee_type, "Employee")
                    st.caption(f"{label}: select the salary period dates (e.g. 1–15 or 16–month end).")
                    m, y = payroll_month.split("/")
                    month_start = datetime.strptime(f"01/{m}/{y}", DATE_FMT)
                    month_end = datetime.strptime(
                        f"{calendar.monthrange(int(y), int(m))[1]:02d}/{m}/{y}",
                        DATE_FMT,
                    )
                    p1, p2, _ = st.columns([1, 1, 2])
                    period_start = p1.date_input(
                        "From date",
                        value=month_start.date(),
                        key=f"payroll_period_start_{employee_id}_{payroll_month.replace('/', '_')}",
                    )
                    period_end = p2.date_input(
                        "To date",
                        value=month_end.date(),
                        key=f"payroll_period_end_{employee_id}_{payroll_month.replace('/', '_')}",
                    )
                ded_key = f"payroll_deductions_{employee_id}_{payroll_month.replace('/', '_')}"
                ledger_preview = get_employee_advance_ledger(employee_id, payroll_month)
                suggested_deduction = float(
                    ledger_preview.get("open_balance") or ledger_preview.get("for_month_total") or 0
                )
                if ded_key not in st.session_state:
                    st.session_state[ded_key] = suggested_deduction
                if employee_type == "Site Worker":
                    from modules.worker_payroll_db import calculate_period

                    ps = period_start.strftime(DATE_FMT) if period_start else ""
                    pe = period_end.strftime(DATE_FMT) if period_end else ""
                    if not ps or not pe:
                        st.warning("Select from and to dates for site worker payroll.")
                        summary = None
                    else:
                        raw = calculate_period(employee_id, ps, pe)
                        summary = (
                            _adapt_worker_period_summary(raw, person, payroll_month, period_start, period_end)
                            if raw
                            else None
                        )
                else:
                    summary = build_month_attendance_summary(employee_id, payroll_month, period_start, period_end)
                if not summary:
                    st.warning("Could not load payroll summary.")
                else:
                    if period_start and period_end:
                        summary["payroll_period_start"] = period_start.strftime(DATE_FMT)
                        summary["payroll_period_end"] = period_end.strftime(DATE_FMT)
                    pending_fp = _payroll_hr_fingerprint(
                        employee_id,
                        payroll_month,
                        float(st.session_state.get(ded_key, suggested_deduction)),
                        period_start,
                        period_end,
                    )
                    on_review_step = _payroll_hr_is_verified(pending_fp)

                    if on_review_step:
                        deductions = float(st.session_state.get(ded_key, suggested_deduction))
                    else:
                        deductions = st.number_input(
                            "Deductions (advance / other)",
                            min_value=0.0,
                            step=100.0,
                            key=ded_key,
                        )
                    if employee_type != "Site Worker":
                        _render_payroll_advance_summary(employee_id, payroll_month, deductions)
                    else:
                        st.markdown("#### Deductions")
                        st.caption("Site workers: enter advance / other deductions for this period.")

                    day_lines = summary.get("day_lines") or []
                    if day_lines:
                        st.markdown("#### Daily breakdown")
                        st.dataframe(pd.DataFrame(day_lines), width="stretch", hide_index=True)

                    net_salary = max(
                        0.0,
                        float(summary.get("normal_salary_amount") or 0)
                        + float(summary.get("weekly_off_paid_amount") or 0)
                        + float(summary.get("holiday_paid_amount") or 0)
                        + float(summary.get("ot_amount") or 0)
                        - deductions,
                    )
                    fingerprint = _payroll_hr_fingerprint(
                        employee_id, payroll_month, deductions, period_start, period_end
                    )
                    verified = _payroll_hr_is_verified(fingerprint)
                    _render_payroll_hr_step_indicator(verified)

                    existing = get_payroll_record(employee_id, payroll_month)
                    if employee_type == "Site Worker" and period_start and period_end:
                        st.caption(
                            f"Site worker · {person.get('hour_category') or '8hr/10hr'} · "
                            f"Period {period_start.strftime(DATE_FMT)} – {period_end.strftime(DATE_FMT)}"
                        )
                    if existing:
                        st.info(
                            f"Saved payroll status: **{existing.get('workflow_status') or existing.get('salary_status')}**"
                        )

                    period_label = payroll_month
                    if period_start and period_end:
                        period_label = (
                            f"{payroll_month} ({period_start.strftime(DATE_FMT)} – "
                            f"{period_end.strftime(DATE_FMT)})"
                        )

                    if not verified:
                        st.info(
                            "Review the advance summary and deductions above. "
                            "Click **Review & Verify** to see the full payroll breakdown before saving."
                        )
                        if st.button(
                            "Review & Verify", type="primary", width="stretch", key="payroll_hr_review_btn"
                        ):
                            _payroll_hr_mark_verified(fingerprint)
                            st.rerun()
                    else:
                        st.markdown("#### Review & verify payroll")
                        st.markdown(
                            f"**Employee:** {employee_name} ({employee_id})  \n"
                            f"**Type:** {employee_type}  \n"
                            f"**Pay period:** {period_label}  \n"
                            f"**Deductions:** Rs {deductions:,.2f}"
                        )
                        _render_payroll_summary(summary, net_salary=net_salary, deductions=deductions)
                        st.caption(
                            "Confirm the breakdown above is correct, then save as draft or submit to MD."
                        )
                        if st.button("← Back to edit", key="payroll_hr_back_btn"):
                            _payroll_hr_clear_verified()
                            st.rerun()
                        c1, c2 = st.columns(2)

                        def _persist_payroll(workflow_status: str) -> str:
                            summary["deductions"] = deductions
                            summary["net_salary"] = net_salary
                            pid = save_payroll_record(summary, deductions, workflow_status)
                            if employee_type != "Site Worker":
                                mark_advances_deducted(employee_id, pid, payroll_month)
                            elif employee_type == "Site Worker":
                                from modules.worker_payroll_db import calculate_period, save_payroll_run
                                from modules.worker_payroll_engine import normalize_workflow_status

                                ps = summary.get("payroll_period_start") or ""
                                pe = summary.get("payroll_period_end") or ""
                                raw = calculate_period(employee_id, ps, pe) if ps and pe else {}
                                if raw:
                                    raw["worker_id"] = employee_id
                                    save_payroll_run(
                                        raw,
                                        deductions,
                                        normalize_workflow_status(workflow_status),
                                    )
                            return pid

                        if c1.button(
                            "Confirm & Save as Draft",
                            type="primary",
                            width="stretch",
                            key="payroll_hr_save_draft",
                        ):
                            pid = _persist_payroll("Draft")
                            _payroll_hr_clear_verified()
                            st.success(f"Payroll saved as Draft. ID: {pid}")
                            st.rerun()
                        if c2.button("Confirm & Submit to MD", width="stretch", key="payroll_hr_submit_md"):
                            pid = _persist_payroll("Submitted to MD")
                            update_payroll_workflow(pid, "Submitted to MD")
                            _payroll_hr_clear_verified()
                            st.success(f"Payroll submitted to MD. ID: {pid}")
                            st.rerun()

                st.divider()
                _render_delete_saved_payroll(employee_id, key_prefix="hr_payroll_del")

    with md_tab:
        if not is_management(role):
            st.info("MD / Super Admin approval is required here.")
        else:
            pending = list_payroll_by_workflow("Submitted to MD")
            if pending.empty:
                st.info("No payroll pending MD approval.")
            else:
                labels = {
                    f"{row['employee_name']} | {row['payroll_month']} | Rs {row['net_salary']:,.2f}": row["payroll_id"]
                    for _, row in pending.iterrows()
                }
                pick = st.selectbox("Select payroll", list(labels.keys()), key="md_payroll_pick")
                payroll_id = labels[pick]
                row = pending[pending["payroll_id"] == payroll_id].iloc[0]
                st.markdown(f"**Employee:** {row['employee_name']}  |  **Month:** {row['payroll_month']}")
                md_summary = build_month_attendance_summary(row["employee_id"], row["payroll_month"])
                if md_summary:
                    _render_payroll_summary(
                        md_summary,
                        net_salary=float(row.get("net_salary") or 0),
                        deductions=float(row.get("deductions") or 0),
                    )
                else:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Worked Days", int(row.get("worked_days") or 0))
                    m2.metric("Paid WO Days", int(row.get("paid_weekly_off_days") or 0))
                    m3.metric("Paid Holidays", int(row.get("paid_holiday_days") or 0))
                    m4.metric("OT Hours", row.get("total_ot_hours") or 0)
                    m5, m6 = st.columns(2)
                    m5.metric("OT Amount", f"Rs {row.get('ot_amount', 0):,.2f}")
                    m6.metric("Net Salary", f"Rs {row.get('net_salary', 0):,.2f}")
                md_remarks = st.text_input("MD Remarks", key="md_payroll_remarks")
                a1, a2, a3 = st.columns(3)
                if a1.button("APPROVE", type="primary", width="stretch"):
                    update_payroll_workflow(payroll_id, "MD Approved", md_remarks)
                    st.success("Payroll MD Approved.")
                    st.rerun()
                if a2.button("REJECT", width="stretch"):
                    update_payroll_workflow(payroll_id, "Rejected", md_remarks)
                    st.warning("Payroll rejected.")
                    st.rerun()
                if a3.button("SEND BACK", width="stretch"):
                    update_payroll_workflow(payroll_id, "Sent Back", md_remarks)
                    st.info("Payroll sent back to HR.")
                    st.rerun()

    with accounts_tab:
        approved = list_payroll_by_workflow("MD Approved", payment_status="Pending")
        if approved.empty:
            st.info("No MD-approved payroll ready for payment.")
        else:
            labels = {
                f"{row['employee_name']} | {row['payroll_month']} | Rs {row['net_salary']:,.2f}": row["payroll_id"]
                for _, row in approved.iterrows()
            }
            pick = st.selectbox("Select payroll", list(labels.keys()), key="accounts_payroll_pick")
            payroll_id = labels[pick]
            row = approved[approved["payroll_id"] == payroll_id].iloc[0]
            st.markdown(f"**Employee:** {row['employee_name']}  |  **Net Salary:** Rs {row['net_salary']:,.2f}")
            payment_mode = st.selectbox("Payment Mode", PAYMENT_MODES, key="accounts_payment_mode")
            if st.button("MARK PAYMENT COMPLETED", type="primary", width="stretch"):
                mark_payroll_paid(payroll_id, payment_mode)
                st.success(f"Payment marked as Paid via {payment_mode}.")
                st.rerun()

    with advance_tab:
        subcontractors = [""] + load_subcontractor_names()
        with st.form("advance_form", clear_on_submit=True):
            a1, a2, a3 = st.columns(3)
            subcontractor = a1.selectbox("Sub Contractor", subcontractors, index=0)
            advance_date = a2.date_input("Advance Date")
            amount = a3.number_input("Amount", min_value=0.0, step=100.0)
            remarks = st.text_input("Remarks")
            if st.form_submit_button("SAVE ADVANCE", type="primary", width="stretch"):
                if not subcontractor:
                    st.error("Please select a Sub Contractor.")
                elif amount <= 0:
                    st.error("Amount must be greater than zero.")
                else:
                    advance_id = generate_id("ADV", "subcontractor_advance")
                    conn = get_conn()
                    conn.execute(
                        """
                        INSERT INTO subcontractor_advance(advance_id, subcontractor_name, advance_date, amount, remarks)
                        VALUES(?,?,?,?,?)
                        """,
                        (advance_id, subcontractor, advance_date.strftime(DATE_FMT), amount, remarks),
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"Advance saved. ID: {advance_id}")
                    st.rerun()

        conn = get_conn()
        st.dataframe(
            pd.read_sql_query(
                "SELECT advance_id, subcontractor_name, advance_date, amount, remarks FROM subcontractor_advance ORDER BY id DESC",
                conn,
            ),
            width="stretch",
            hide_index=True,
        )
        conn.close()

    st.markdown("### Payroll Register — all staff")
    _render_delete_saved_payroll(employee_id=None, key_prefix="register_payroll_del")


def page_payments():
    from modules.finance import page_finance

    page_finance()
    return

    st.subheader("Payments")
    clients = [""] + load_client_names()
    projects = [""] + load_project_names()
    payment_types = [""] + load_lookup("payment_heads", "head_name")
    payment_heads = [""] + load_lookup("payment_heads", "head_name")
    payment_modes = ["Cash", "Bank Transfer", "Cheque", "UPI"]
    employee_options = load_employee_options()
    employee_labels = [f"{employee_id} - {employee_name}" for employee_id, employee_name in employee_options]
    subcontractors = [""] + load_subcontractor_names()

    with st.form("payment_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        payment_date = c1.date_input("Date")
        payment_type = c2.selectbox("Payment Type", payment_types, index=0)
        payment_mode = c3.selectbox("Payment Mode", payment_modes)
        payment_head = c1.selectbox("Payment Head", payment_heads, index=0)
        pay_to_type = c2.selectbox("Pay To Type", ["Employee", "Sub Contractor", "Vendor", "Client", "Other"])
        if pay_to_type == "Employee":
            pay_to_name = c3.selectbox("Pay To Name", [""] + employee_labels, index=0)
        elif pay_to_type == "Sub Contractor":
            pay_to_name = c3.selectbox("Pay To Name", subcontractors, index=0)
        elif pay_to_type == "Client":
            pay_to_name = c3.selectbox("Pay To Name", clients, index=0)
        else:
            pay_to_name = c3.text_input("Pay To Name")
        project_name = c1.selectbox("Project", projects, index=0)
        client_name = c2.selectbox("Client", clients, index=0)
        amount = c3.number_input("Amount", min_value=0.0, step=100.0)
        reference_number = c1.text_input("Reference Number")
        remarks = c2.text_input("Remarks")
        bill_upload = c3.file_uploader("Bill Upload", key="payment_bill")
        if st.form_submit_button("SAVE PAYMENT", type="primary", width="stretch"):
            resolved_pay_to = _resolve_pay_to_name(pay_to_type, pay_to_name)
            if amount <= 0:
                st.error("Amount must be greater than zero.")
            elif pay_to_type in {"Employee", "Sub Contractor", "Client"} and not resolved_pay_to:
                st.error("Please select who the payment is for.")
            else:
                voucher_number = generate_id("PAY", "payments")
                bill_path = _save_upload(bill_upload, "uploads/bills", voucher_number)
                conn = get_conn()
                conn.execute(
                    """
                    INSERT INTO payments(
                        voucher_number, payment_date, payment_type, payment_head,
                        pay_to_type, pay_to_name, project_name, client_name, amount,
                        payment_mode, reference_number, remarks, bill_upload, status
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        voucher_number,
                        payment_date.strftime(DATE_FMT),
                        payment_type,
                        payment_head,
                        pay_to_type,
                        resolved_pay_to,
                        project_name,
                        client_name,
                        amount,
                        payment_mode,
                        reference_number,
                        remarks,
                        bill_path,
                        "Paid",
                    ),
                )
                conn.commit()
                conn.close()
                st.success(f"Payment saved. Voucher: {voucher_number}")
                st.rerun()

    conn = get_conn()
    st.dataframe(
        pd.read_sql_query(
            """
            SELECT voucher_number, payment_date, payment_type, pay_to_name,
                   project_name, amount, status
            FROM payments
            ORDER BY id DESC
            """,
            conn,
        ),
        width="stretch",
        hide_index=True,
    )
    conn.close()


def page_expenses():
    from modules.finance import page_finance

    page_finance()
    return

    st.subheader("Expenses")
    clients = [""] + load_client_names()
    projects = [""] + load_project_names()
    expense_heads = [""] + load_lookup("expense_heads", "head_name")
    payment_modes = ["Cash", "Bank Transfer", "Cheque", "UPI"]

    with st.form("expense_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        expense_date = c1.date_input("Date")
        expense_head = c2.selectbox("Expense Head", expense_heads, index=0)
        paid_to = c3.text_input("Paid To")
        project_name = c1.selectbox("Project", projects, index=0)
        client_name = c2.selectbox("Client", clients, index=0)
        amount = c3.number_input("Amount", min_value=0.0, step=100.0)
        payment_mode = c1.selectbox("Payment Mode", payment_modes)
        approved_by = c2.text_input("Approved By")
        bill_upload = c3.file_uploader("Bill Upload", key="expense_bill")
        remarks = st.text_input("Remarks")
        if st.form_submit_button("SAVE EXPENSE", type="primary", width="stretch"):
            if amount <= 0:
                st.error("Amount must be greater than zero.")
            elif not expense_head:
                st.error("Please select an Expense Head.")
            else:
                expense_id = generate_id("EXP", "expenses")
                bill_path = _save_upload(bill_upload, "uploads/bills", expense_id)
                conn = get_conn()
                conn.execute(
                    """
                    INSERT INTO expenses(
                        expense_id, expense_date, expense_head, project_name,
                        client_name, paid_to, amount, payment_mode, approved_by, bill_upload, remarks
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        expense_id,
                        expense_date.strftime(DATE_FMT),
                        expense_head,
                        project_name,
                        client_name,
                        paid_to,
                        amount,
                        payment_mode,
                        approved_by,
                        bill_path,
                        remarks,
                    ),
                )
                conn.commit()
                conn.close()
                st.success(f"Expense saved. ID: {expense_id}")
                st.rerun()

    conn = get_conn()
    st.dataframe(
        pd.read_sql_query(
            """
            SELECT expense_id, expense_date, expense_head, project_name,
                   paid_to, amount, payment_mode
            FROM expenses
            ORDER BY id DESC
            """,
            conn,
        ),
        width="stretch",
        hide_index=True,
    )
    conn.close()


NEW_CLIENT_OPTION = "+ Add new client"
RECORD_PICK_PLACEHOLDER = "— Select a record —"
CLIENT_STATUS_OPTIONS = ["On Going", "Completed", "On Hold", "Inactive"]
PROJECT_STATUS_OPTIONS = ["On Going", "Completed", "On Hold", "Inactive"]


def _record_label(row, id_column, display_columns):
    parts = [
        str(row[col]).strip()
        for col in display_columns
        if col in row.index and str(row[col]).strip()
    ]
    label = " | ".join(parts) if parts else str(row[id_column])
    return f"{label} ({row[id_column]})"


def _render_draft_remove_button(confirm_key, idx, label, session_list_key):
    def _remove_item(index):
        st.session_state[session_list_key].pop(index)
        st.rerun()

    render_delete_confirm_dialog(confirm_key, _remove_item)
    if st.button(f"Remove {label}", key=f"{confirm_key}_btn"):
        start_delete_confirm(confirm_key, label, idx)


def _render_saved_record_toolbar(
    section_key,
    records,
    id_column,
    display_columns,
    load_handler,
    delete_handler,
    clear_handler,
    form_mode_key,
    new_label="Add new",
    edit_label="Edit / delete",
):
    if st.session_state.pop(f"{section_key}_form_reset", False):
        clear_handler()

    confirm_key = f"{section_key}_record"

    prev_mode = st.session_state.get(f"{section_key}_form_mode_prev", new_label)
    form_mode = st.radio(
        "Action",
        [new_label, edit_label],
        horizontal=True,
        key=form_mode_key,
    )
    if form_mode == new_label and prev_mode != new_label:
        cancel_delete_confirm(confirm_key)
        clear_handler()
    if form_mode == edit_label and prev_mode == new_label:
        st.session_state.pop(f"{section_key}_pick", None)
    st.session_state[f"{section_key}_form_mode_prev"] = form_mode

    if form_mode == edit_label and not records.empty:
        options = {
            _record_label(row, id_column, display_columns): row[id_column]
            for _, row in records.iterrows()
        }
        pick_key = f"{section_key}_pick"
        pick_labels = [RECORD_PICK_PLACEHOLDER] + list(options.keys())
        if st.session_state.get(pick_key) not in pick_labels:
            st.session_state.pop(pick_key, None)
        c1, c2, c3 = st.columns([3, 1, 1])
        pick = c1.selectbox(
            "Select saved record",
            pick_labels,
            key=pick_key,
        )
        if c2.button("LOAD", type="primary", width="stretch", key=f"{section_key}_load"):
            if pick == RECORD_PICK_PLACEHOLDER:
                st.warning("Select a saved record first, then click LOAD.")
            else:
                cancel_delete_confirm(confirm_key)
                record_id = options[pick]
                row = records[records[id_column] == record_id].iloc[0]
                load_handler(row)
                st.rerun()
        if c3.button("DELETE", width="stretch", key=f"{section_key}_delete"):
            if pick == RECORD_PICK_PLACEHOLDER:
                st.warning("Select a saved record first, then click DELETE.")
            else:
                record_id = options[pick]
                start_delete_confirm(confirm_key, pick, record_id)
    elif form_mode == edit_label:
        st.info("No saved records yet.")

    def _confirm_delete_record(record_id):
        delete_handler(record_id)
        st.session_state[f"{section_key}_form_reset"] = True
        st.session_state.pop(form_mode_key, None)
        st.session_state.pop(f"{section_key}_pick", None)
        st.session_state[f"{section_key}_form_mode_prev"] = new_label
        st.success(f"Deleted {record_id}.")
        st.rerun()

    render_delete_confirm_dialog(confirm_key, _confirm_delete_record)

    return form_mode


def _is_valid_mobile(value: str) -> bool:
    text = str(value or "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    return len(digits) >= 8


def _client_widget_keys():
    return [
        "client_company_name",
        "client_contact_person",
        "client_mobile",
        "client_email",
        "client_gst_number",
        "client_pan_number",
        "client_address",
        "client_location_country",
        "client_location_region",
        "client_location_district",
        "client_agreement_start",
        "client_agreement_end",
        "client_status",
        "client_work_order_no",
        "client_total_work_amount",
        "client_notes",
        "client_doc",
        "client_edit_id",
    ]


def _clear_client_form():
    _pop_widget_keys(_client_widget_keys())
    st.session_state.pop("client_delete_pending_id", None)
    st.session_state.pop("client_delete_pending_label", None)
    st.session_state.pop("client_edit_id", None)
    for key, value in {
        "client_company_name": "",
        "client_contact_person": "",
        "client_mobile": "",
        "client_email": "",
        "client_gst_number": "",
        "client_pan_number": "",
        "client_address": "",
        "client_location_country": "",
        "client_location_region": "",
        "client_location_district": "",
        "client_status": CLIENT_STATUS_OPTIONS[0],
        "client_work_order_no": "",
        "client_total_work_amount": 0.0,
        "client_notes": "",
    }.items():
        st.session_state[key] = value
    for date_key in ("client_agreement_start", "client_agreement_end", "client_doc"):
        st.session_state.pop(date_key, None)


def _load_client_into_form(row):
    _clear_client_form()
    st.session_state.client_edit_id = row["client_id"]
    st.session_state.client_company_name = row.get("company_name") or row.get("client_name") or ""
    st.session_state.client_contact_person = row.get("contact_person") or ""
    st.session_state.client_mobile = row.get("mobile") or ""
    st.session_state.client_email = row.get("email") or ""
    st.session_state.client_gst_number = row.get("gst_number") or ""
    st.session_state.client_pan_number = row.get("pan_number") or ""
    st.session_state.client_address = row.get("address") or ""
    st.session_state.client_location_country = row.get("country") or ""
    st.session_state.client_location_region = row.get("region") or ""
    st.session_state.client_location_district = row.get("district") or ""
    st.session_state.client_status = row.get("status") or CLIENT_STATUS_OPTIONS[0]
    st.session_state.client_work_order_no = row.get("work_order_no") or ""
    st.session_state.client_total_work_amount = float(row.get("total_work_amount") or 0.0)
    st.session_state.client_notes = row.get("notes") or ""
    agreement_start = _parse_db_date(row.get("agreement_start_date"))
    if agreement_start:
        st.session_state.client_agreement_start = agreement_start
    agreement_end = _parse_db_date(row.get("agreement_end_date"))
    if agreement_end:
        st.session_state.client_agreement_end = agreement_end


def _delete_client(client_id):
    conn = get_conn()
    conn.execute("DELETE FROM clients WHERE client_id = ?", (client_id,))
    conn.commit()
    conn.close()


def _project_widget_keys():
    return [
        "project_client_pick",
        "project_name",
        "project_code",
        "project_location",
        "project_location_master_country",
        "project_location_master_region",
        "project_location_master_district",
        "project_site_incharge",
        "project_start_date",
        "project_end_date",
        "project_labour_count",
        "project_budget",
        "project_status",
        "project_work_order_no",
        "project_total_work_amount",
        "project_remarks",
        "project_doc",
        "project_edit_id",
        "project_draft_boq_number",
        "project_draft_boq_description",
        "project_draft_boq_unit",
        "project_draft_boq_qty",
        "project_draft_boq_rate",
    ]


def _clear_project_form():
    _pop_widget_keys(_project_widget_keys())
    st.session_state.pop("project_edit_id", None)
    st.session_state.pop("project_delete_pending_id", None)
    st.session_state.pop("project_delete_pending_label", None)
    for key, value in {
        "project_client_pick": "",
        "project_name": "",
        "project_code": "",
        "project_location": "",
        "project_location_master_country": "",
        "project_location_master_region": "",
        "project_location_master_district": "",
        "project_site_incharge": "",
        "project_labour_count": 0,
        "project_budget": 0.0,
        "project_status": PROJECT_STATUS_OPTIONS[0],
        "project_work_order_no": "",
        "project_total_work_amount": 0.0,
        "project_remarks": "",
        "project_draft_boq_number": "",
        "project_draft_boq_description": "",
        "project_draft_boq_unit": "",
        "project_draft_boq_qty": 0.0,
        "project_draft_boq_rate": 0.0,
    }.items():
        st.session_state[key] = value
    for date_key in ("project_start_date", "project_end_date", "project_doc"):
        st.session_state.pop(date_key, None)
    _reset_project_draft_boq()


def _load_project_into_form(row):
    _clear_project_form()
    project_id = row["project_id"]
    st.session_state.project_edit_id = project_id
    client_name = row.get("client_name") or ""
    st.session_state.project_client_pick = client_name
    st.session_state.project_name = row.get("project_name") or ""
    st.session_state.project_code = row.get("project_code") or ""
    st.session_state.project_location = row.get("location") or ""
    st.session_state.project_location_master_country = row.get("country") or ""
    st.session_state.project_location_master_region = row.get("region") or ""
    st.session_state.project_location_master_district = row.get("district") or ""
    st.session_state.project_site_incharge = row.get("site_incharge") or ""
    st.session_state.project_labour_count = int(row.get("labour_count") or 0)
    st.session_state.project_budget = float(row.get("budget") or 0.0)
    st.session_state.project_status = row.get("status") or PROJECT_STATUS_OPTIONS[0]
    st.session_state.project_work_order_no = row.get("work_order_no") or ""
    st.session_state.project_total_work_amount = float(row.get("amount") or 0.0)
    st.session_state.project_remarks = row.get("remarks") or ""
    start_date = _parse_db_date(row.get("start_date"))
    if start_date:
        st.session_state.project_start_date = start_date
    end_date = _parse_db_date(row.get("end_date"))
    if end_date:
        st.session_state.project_end_date = end_date
    conn = get_conn()
    boq_df = pd.read_sql_query(
        """
        SELECT boq_number, description, unit, quantity, approved_rate, amount
        FROM project_boq_items
        WHERE project_id = ?
        ORDER BY id
        """,
        conn,
        params=(project_id,),
    )
    conn.close()
    st.session_state.project_draft_boq_items = [
        {
            "boq_number": r["boq_number"],
            "description": r["description"],
            "unit": r["unit"],
            "quantity": float(r["quantity"]),
            "approved_rate": float(r["approved_rate"]),
            "amount": float(r["amount"]),
        }
        for _, r in boq_df.iterrows()
    ]


def _delete_project(project_id):
    conn = get_conn()
    conn.execute("DELETE FROM project_boq_items WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM document_uploads WHERE entity_type = 'project' AND entity_id = ?", (project_id,))
    conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
    conn.commit()
    conn.close()


def _subcontractor_widget_keys():
    return [
        "sub_company_name",
        "sub_contact_person",
        "sub_mobile_number",
        "sub_aadhaar_number",
        "sub_pan_number",
        "sub_address",
        "sub_account_holder_name",
        "sub_bank_account",
        "sub_bank_name",
        "sub_ifsc_code",
        "sub_branch_name",
        "subcontractor_location_country",
        "subcontractor_location_region",
        "subcontractor_location_district",
        "sub_active_projects",
        "sub_status",
        "sub_agreement_upload",
        "sub_edit_id",
    ]


def _clear_subcontractor_form():
    _pop_widget_keys(_subcontractor_widget_keys())
    for k in (
        "sub_draft_designation_pick",
        "sub_draft_designation_custom",
        "sub_draft_labour_project",
        "sub_draft_working_hours",
        "sub_draft_daily_rate",
        "sub_draft_ot_applicable",
        "sub_draft_ot_rate",
        "sub_draft_boq_project",
        "sub_draft_boq_item",
        "sub_draft_boq_unit",
        "sub_draft_boq_rate",
    ):
        st.session_state.pop(k, None)
    st.session_state.pop("sub_edit_id", None)
    st.session_state.pop("subcontractor_delete_pending_id", None)
    st.session_state.pop("subcontractor_delete_pending_label", None)
    for key, value in {
        "sub_company_name": "",
        "sub_contact_person": "",
        "sub_mobile_number": "",
        "sub_aadhaar_number": "",
        "sub_pan_number": "",
        "sub_address": "",
        "sub_account_holder_name": "",
        "sub_bank_account": "",
        "sub_bank_name": "",
        "sub_ifsc_code": "",
        "sub_branch_name": "",
        "subcontractor_location_country": "",
        "subcontractor_location_region": "",
        "subcontractor_location_district": "",
        "sub_status": "Active",
        "sub_active_projects": [],
    }.items():
        st.session_state[key] = value
    st.session_state.pop("sub_agreement_upload", None)
    _reset_subcontractor_draft()


def _load_subcontractor_into_form(row):
    _clear_subcontractor_form()
    subcontractor_id = row["subcontractor_id"]
    st.session_state.sub_edit_id = subcontractor_id
    name = row.get("company_name") or row.get("subcontractor_name") or ""
    st.session_state.sub_company_name = name
    st.session_state.sub_contact_person = row.get("contact_person") or ""
    st.session_state.sub_mobile_number = row.get("contact_number") or ""
    st.session_state.sub_aadhaar_number = row.get("aadhaar_number") or ""
    st.session_state.sub_pan_number = row.get("pan_card_number") or ""
    st.session_state.sub_address = row.get("address") or ""
    st.session_state.sub_account_holder_name = row.get("account_holder_name") or ""
    st.session_state.sub_bank_account = row.get("bank_account") or ""
    st.session_state.sub_bank_name = row.get("bank_name") or ""
    st.session_state.sub_ifsc_code = row.get("ifsc_code") or ""
    st.session_state.sub_branch_name = row.get("branch_name") or ""
    st.session_state.subcontractor_location_country = row.get("country") or ""
    st.session_state.subcontractor_location_region = row.get("region") or ""
    st.session_state.subcontractor_location_district = row.get("district") or ""
    st.session_state.sub_status = row.get("status") or "Active"
    active_projects = row.get("active_projects") or ""
    st.session_state.sub_active_projects = [
        part.strip() for part in str(active_projects).split(",") if part.strip()
    ]
    _reset_subcontractor_draft()


def _delete_subcontractor(subcontractor_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT subcontractor_name, company_name FROM subcontractors WHERE subcontractor_id = ?",
        (subcontractor_id,),
    ).fetchone()
    name = ""
    if row:
        name = row[0] or row[1] or ""
    if name:
        conn.execute("DELETE FROM subcontractor_labour_rates WHERE subcontractor_name = ?", (name,))
        conn.execute("DELETE FROM subcontractor_boq_rates WHERE subcontractor_name = ?", (name,))
    conn.execute("DELETE FROM document_uploads WHERE entity_type = 'subcontractor' AND entity_id = ?", (subcontractor_id,))
    conn.execute("DELETE FROM subcontractors WHERE subcontractor_id = ?", (subcontractor_id,))
    conn.commit()
    conn.close()


def _ensure_project_draft_boq():
    st.session_state.setdefault("project_draft_boq_items", [])


def _reset_project_draft_boq():
    st.session_state.project_draft_boq_items = []


def _insert_project_boq_item(conn, project_id, project_name, client_name, row):
    boq_item_id = generate_id("PB", "project_boq_items", conn=conn)
    quantity = float(row["quantity"])
    approved_rate = float(row["approved_rate"])
    amount = float(row.get("amount", quantity * approved_rate))
    conn.execute(
        """
        INSERT INTO project_boq_items(
            boq_item_id, project_id, project_name, client_name, boq_number, description,
            quantity, unit, approved_rate, amount, status
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            boq_item_id,
            project_id,
            project_name,
            client_name,
            row["boq_number"],
            row["description"],
            quantity,
            row["unit"],
            approved_rate,
            amount,
            row.get("status", "Active"),
        ),
    )
    return boq_item_id


def _insert_quick_client(company_name, contact_person, mobile):
    client_id = generate_id("CL", "clients")
    conn = get_conn()
    today = datetime.now().strftime(DATE_FMT)
    conn.execute(
        """
        INSERT INTO clients(
            client_id, client_name, company_name, contact_person, mobile,
            alternate_number, email, gst_number, pan_number, address,
            country, region, district, city, agreement_start_date, agreement_end_date,
            client_type, status, notes, document_upload, work_order_no, total_work_amount
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            client_id,
            company_name,
            company_name,
            contact_person,
            mobile,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            today,
            today,
            "",
            "On Going",
            "",
            "",
            "",
            0.0,
        ),
    )
    conn.commit()
    conn.close()
    return client_id, company_name


def _render_clients_tab():
    conn = get_conn()
    clients_df = pd.read_sql_query(
        """
        SELECT client_id, COALESCE(company_name, client_name) AS company_name, client_name,
               contact_person, mobile, email, gst_number, pan_number, address,
               country, region, district, agreement_start_date, agreement_end_date,
               status, notes, work_order_no, total_work_amount
        FROM clients
        ORDER BY id DESC
        """,
        conn,
    )
    conn.close()

    _render_saved_record_toolbar(
        "client",
        clients_df,
        "client_id",
        ["company_name", "contact_person", "mobile"],
        _load_client_into_form,
        _delete_client,
        _clear_client_form,
        "client_form_mode",
        new_label="Add new client",
        edit_label="Edit / delete client",
    )

    edit_id = st.session_state.get("client_edit_id")
    if edit_id:
        st.info(f"Editing client **{edit_id}**. Change fields below and click UPDATE CLIENT, or switch to Add new client.")

    c1, c2, c3 = st.columns(3)
    company_name = c1.text_input("Company Name", key="client_company_name")
    contact_person = c2.text_input("Contact Person", key="client_contact_person")
    mobile = c3.text_input("Mobile Number", key="client_mobile")
    email = c1.text_input("Email", key="client_email")
    gst_number = c2.text_input("GST Number", key="client_gst_number")
    pan_number = c3.text_input("PAN Number", key="client_pan_number")
    address = st.text_area("Address", key="client_address")
    country, region, district = location_dropdowns(
        "client_location",
        default_country="",
        default_region="",
        default_district="",
        allow_blank=True,
        show_region=False,
        show_district=False,
    )
    d1, d2, d3 = st.columns(3)
    agreement_start = d1.date_input("Agreement Start Date", key="client_agreement_start")
    agreement_end = d2.date_input("Agreement End Date", key="client_agreement_end")
    status = d3.selectbox("Status", CLIENT_STATUS_OPTIONS, key="client_status")
    w1, w2, w3 = st.columns(3)
    work_order_no = w1.text_input("Work Order Number", key="client_work_order_no")
    total_work_amount = w2.number_input(
        "Total Work Amount (Rs)",
        min_value=0.0,
        step=1000.0,
        key="client_total_work_amount",
    )
    notes = w3.text_area("Notes", key="client_notes")
    document_upload = st.file_uploader("Document Upload", key="client_doc")

    save_label = f"UPDATE CLIENT ({edit_id})" if edit_id else "SAVE CLIENT"
    if st.button(save_label, type="primary", width="stretch"):
        if not company_name.strip():
            st.error("Company Name is required.")
        else:
            saved_name = company_name.strip()
            conn = get_conn()
            if edit_id:
                existing = conn.execute(
                    "SELECT document_upload FROM clients WHERE client_id = ?",
                    (edit_id,),
                ).fetchone()
                document_path = existing[0] if existing else ""
                if document_upload is not None:
                    document_path = _save_upload(document_upload, "uploads/clients", edit_id)
                conn.execute(
                    """
                    UPDATE clients SET
                        client_name = ?, company_name = ?, contact_person = ?, mobile = ?,
                        email = ?, gst_number = ?, pan_number = ?, address = ?,
                        country = ?, region = ?, district = ?, city = ?,
                        agreement_start_date = ?, agreement_end_date = ?,
                        status = ?, notes = ?, document_upload = ?,
                        work_order_no = ?, total_work_amount = ?
                    WHERE client_id = ?
                    """,
                    (
                        saved_name,
                        saved_name,
                        contact_person,
                        mobile,
                        email,
                        gst_number,
                        pan_number,
                        address,
                        country,
                        region,
                        district,
                        district,
                        agreement_start.strftime(DATE_FMT),
                        agreement_end.strftime(DATE_FMT),
                        status,
                        notes,
                        document_path,
                        work_order_no,
                        total_work_amount,
                        edit_id,
                    ),
                )
                client_id = edit_id
            else:
                client_id = generate_id("CL", "clients")
                document_path = _save_upload(document_upload, "uploads/clients", client_id)
                conn.execute(
                    """
                    INSERT INTO clients(
                        client_id, client_name, company_name, contact_person, mobile,
                        alternate_number, email, gst_number, pan_number, address,
                        country, region, district, city, agreement_start_date, agreement_end_date,
                        client_type, status, notes, document_upload, work_order_no, total_work_amount
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        client_id,
                        saved_name,
                        saved_name,
                        contact_person,
                        mobile,
                        "",
                        email,
                        gst_number,
                        pan_number,
                        address,
                        country,
                        region,
                        district,
                        district,
                        agreement_start.strftime(DATE_FMT),
                        agreement_end.strftime(DATE_FMT),
                        "",
                        status,
                        notes,
                        document_path,
                        work_order_no,
                        total_work_amount,
                    ),
                )
            conn.commit()
            conn.close()
            st.session_state["client_form_reset"] = True
            st.session_state.pop("client_form_mode", None)
            st.session_state.client_form_mode_prev = "Add new client"
            st.success(f"Client {'updated' if edit_id else 'saved'}. ID: {client_id}")
            st.rerun()

    st.markdown("#### Saved Clients")
    st.dataframe(
        clients_df[
            [
                "client_id",
                "company_name",
                "contact_person",
                "mobile",
                "work_order_no",
                "total_work_amount",
                "status",
            ]
        ],
        width="stretch",
        hide_index=True,
    )


def _render_projects_tab():
    _ensure_project_draft_boq()
    conn = get_conn()
    projects_df = pd.read_sql_query(
        """
        SELECT project_id, project_name, client_name, project_code, location,
               country, region, district, site_incharge, start_date, end_date,
               labour_count, budget, status, remarks, work_order_no, amount
        FROM projects
        ORDER BY id DESC
        """,
        conn,
    )
    conn.close()

    _render_saved_record_toolbar(
        "project",
        projects_df,
        "project_id",
        ["project_name", "client_name"],
        _load_project_into_form,
        _delete_project,
        _clear_project_form,
        "project_form_mode",
        new_label="Add new project",
        edit_label="Edit / delete project",
    )

    edit_id = st.session_state.get("project_edit_id")
    if edit_id:
        st.info(f"Editing project **{edit_id}**. Change fields below and click UPDATE PROJECT, or switch to Add new project.")

    client_options = ["", NEW_CLIENT_OPTION] + load_client_names()
    if st.session_state.get("project_client_pick") not in client_options:
        st.session_state["project_client_pick"] = ""

    c1, c2, c3 = st.columns(3)
    client_pick = c1.selectbox("Client Name", client_options, key="project_client_pick")
    client_name = ""
    if client_pick == NEW_CLIENT_OPTION:
        with st.expander("Quick add client", expanded=True):
            qc1, qc2, qc3 = st.columns(3)
            quick_company = qc1.text_input("Company Name", key="quick_client_company")
            quick_contact = qc2.text_input("Contact Person", key="quick_client_contact")
            quick_mobile = qc3.text_input("Mobile Number", key="quick_client_mobile")
            if st.button("Save client & use for this project", key="quick_client_save"):
                if not quick_company.strip():
                    st.error("Company Name is required.")
                else:
                    client_id, saved_name = _insert_quick_client(
                        quick_company.strip(),
                        quick_contact,
                        quick_mobile,
                    )
                    st.session_state["project_client_pick"] = saved_name
                    st.success(f"Client saved. ID: {client_id}")
                    st.rerun()
    else:
        client_name = client_pick
    project_name = c2.text_input("Project Name", key="project_name")
    project_code = c3.text_input("Project Code", key="project_code")
    location = c1.text_input("Location", key="project_location")
    country, region, district = location_dropdowns(
        "project_location_master",
        default_country="",
        default_region="",
        default_district="",
        allow_blank=True,
        show_region=False,
        show_district=False,
    )
    d1, d2, d3 = st.columns(3)
    site_incharge = d1.text_input("Site Incharge", key="project_site_incharge")
    start_date = d2.date_input("Start Date", key="project_start_date")
    end_date = d3.date_input("End Date", key="project_end_date")
    e1, e2, e3 = st.columns(3)
    labour_count = e1.number_input("Labour Count", min_value=0, step=1, key="project_labour_count")
    budget = e2.number_input("Budget", min_value=0.0, step=1000.0, key="project_budget")
    status = e3.selectbox("Status", PROJECT_STATUS_OPTIONS, key="project_status")
    p1, p2, p3 = st.columns(3)
    work_order_no = p1.text_input("Work Order Number", key="project_work_order_no")
    total_work_amount = p2.number_input(
        "Total Work Amount (Rs)",
        min_value=0.0,
        step=1000.0,
        key="project_total_work_amount",
    )
    remarks = p3.text_area("Remarks", key="project_remarks")
    document_upload = st.file_uploader("Document Upload", key="project_doc")

    st.markdown("### Project BOQ Items")
    st.caption("Add multiple BOQ lines for this project. Amount = Quantity × Approved Rate.")
    b1, b2, b3, b4 = st.columns(4)
    draft_boq_number = b1.text_input("BOQ Number", key="project_draft_boq_number")
    draft_description = b2.text_input("Description", key="project_draft_boq_description")
    draft_unit = b3.text_input("Unit", key="project_draft_boq_unit", placeholder="SQM, Nos, RMT")
    draft_quantity = b4.number_input("Quantity", min_value=0.0, step=1.0, key="project_draft_boq_qty")
    r1, r2, r3 = st.columns(3)
    draft_approved_rate = r1.number_input(
        "Approved Rate (Rs)",
        min_value=0.0,
        step=100.0,
        key="project_draft_boq_rate",
    )
    draft_amount = draft_quantity * draft_approved_rate
    r2.metric("Amount (Rs)", f"{draft_amount:,.2f}")
    if r3.button("ADD BOQ LINE", width="stretch", key="project_add_boq_line"):
        if not draft_boq_number.strip():
            st.error("BOQ Number is required.")
        elif not draft_description.strip():
            st.error("Description is required.")
        elif not draft_unit.strip():
            st.error("Unit is required.")
        elif draft_quantity <= 0:
            st.error("Quantity must be greater than zero.")
        elif draft_approved_rate <= 0:
            st.error("Approved Rate must be greater than zero.")
        else:
            st.session_state.project_draft_boq_items.append(
                {
                    "boq_number": draft_boq_number.strip(),
                    "description": draft_description.strip(),
                    "unit": draft_unit.strip(),
                    "quantity": draft_quantity,
                    "approved_rate": draft_approved_rate,
                    "amount": draft_amount,
                }
            )
            st.success(f"BOQ line added: {draft_boq_number.strip()}")
            st.rerun()

    if st.session_state.project_draft_boq_items:
        boq_preview = pd.DataFrame(st.session_state.project_draft_boq_items)
        boq_preview = boq_preview.rename(
            columns={
                "boq_number": "BOQ Number",
                "description": "Description",
                "quantity": "Quantity",
                "unit": "Unit",
                "approved_rate": "Approved Rate",
                "amount": "Amount",
            }
        )
        st.dataframe(boq_preview, width="stretch", hide_index=True)
        for idx in range(len(st.session_state.project_draft_boq_items)):
            _render_draft_remove_button(
                f"project_draft_boq_{idx}",
                idx,
                f"BOQ line #{idx + 1}",
                "project_draft_boq_items",
            )
    else:
        st.info("No BOQ lines added yet.")

    if st.button(
        f"UPDATE PROJECT ({edit_id})" if edit_id else "SAVE PROJECT",
        type="primary",
        width="stretch",
    ):
        if client_pick == NEW_CLIENT_OPTION:
            st.error("Save the new client first (Quick add client), or select an existing client.")
        elif not project_name.strip():
            st.error("Project Name is required.")
        else:
            saved_project_name = project_name.strip()
            conn = get_conn()
            if edit_id:
                project_id = edit_id
                conn.execute(
                    """
                    UPDATE projects SET
                        project_name = ?, client_name = ?, project_code = ?, location = ?,
                        country = ?, region = ?, district = ?, site_incharge = ?,
                        start_date = ?, end_date = ?, labour_count = ?, budget = ?,
                        status = ?, remarks = ?, work_order_no = ?, amount = ?
                    WHERE project_id = ?
                    """,
                    (
                        saved_project_name,
                        client_name,
                        project_code,
                        location,
                        country,
                        region,
                        district,
                        site_incharge,
                        start_date.strftime(DATE_FMT),
                        end_date.strftime(DATE_FMT),
                        labour_count,
                        budget,
                        status,
                        remarks,
                        work_order_no,
                        total_work_amount,
                        project_id,
                    ),
                )
                document_path = _save_upload(document_upload, "uploads/projects", project_id)
                if document_path:
                    conn.execute(
                        """
                        INSERT INTO document_uploads(entity_type, entity_id, document_type, file_path, uploaded_at)
                        VALUES(?,?,?,?,?)
                        """,
                        ("project", project_id, "Project Document", document_path, datetime.now().strftime("%d/%m/%Y %H:%M")),
                    )
                conn.execute("DELETE FROM project_boq_items WHERE project_id = ?", (project_id,))
                boq_count = 0
                for row in st.session_state.project_draft_boq_items:
                    _insert_project_boq_item(conn, project_id, saved_project_name, client_name, row)
                    boq_count += 1
            else:
                project_id = generate_id("PR", "projects")
                document_path = _save_upload(document_upload, "uploads/projects", project_id)
                conn.execute(
                    """
                    INSERT INTO projects(
                        project_id, project_name, client_name, project_code, location,
                        country, region, district, site_incharge, start_date, end_date, labour_count,
                        budget, status, remarks, work_order_no, amount
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        project_id,
                        saved_project_name,
                        client_name,
                        project_code,
                        location,
                        country,
                        region,
                        district,
                        site_incharge,
                        start_date.strftime(DATE_FMT),
                        end_date.strftime(DATE_FMT),
                        labour_count,
                        budget,
                        status,
                        remarks,
                        work_order_no,
                        total_work_amount,
                    ),
                )
                if document_path:
                    conn.execute(
                        """
                        INSERT INTO document_uploads(entity_type, entity_id, document_type, file_path, uploaded_at)
                        VALUES(?,?,?,?,?)
                        """,
                        ("project", project_id, "Project Document", document_path, datetime.now().strftime("%d/%m/%Y %H:%M")),
                    )
                boq_count = 0
                for row in st.session_state.project_draft_boq_items:
                    _insert_project_boq_item(conn, project_id, saved_project_name, client_name, row)
                    boq_count += 1
            conn.commit()
            conn.close()
            st.session_state["project_form_reset"] = True
            st.session_state.pop("project_form_mode", None)
            st.session_state.project_form_mode_prev = "Add new project"
            st.success(
                f"Project {'updated' if edit_id else 'saved'}. ID: {project_id}"
                + (f" · {boq_count} BOQ line(s)." if boq_count else "")
            )
            st.rerun()

    st.markdown("#### Saved Projects")
    st.dataframe(
        projects_df[
            [
                "project_id",
                "project_name",
                "client_name",
                "work_order_no",
                "amount",
                "country",
                "region",
                "district",
                "site_incharge",
                "budget",
                "status",
            ]
        ].rename(columns={"amount": "total_work_amount"}),
        width="stretch",
        hide_index=True,
    )
    conn = get_conn()
    st.markdown("#### Saved Project BOQ Items")
    st.dataframe(
        pd.read_sql_query(
            """
            SELECT boq_item_id, project_id, project_name, client_name, boq_number, description,
                   quantity, unit, approved_rate, amount
            FROM project_boq_items
            ORDER BY id DESC
            """,
            conn,
        ),
        width="stretch",
        hide_index=True,
    )
    conn.close()


def page_clients_projects():
    st.subheader("Clients & Projects")
    focus = st.session_state.pop("clients_projects_tab", None)
    if focus == "projects":
        _render_projects_tab()
        with st.expander("Clients", expanded=False):
            _render_clients_tab()
    elif focus == "clients":
        _render_clients_tab()
        with st.expander("Projects", expanded=False):
            _render_projects_tab()
    else:
        tab_clients, tab_projects = st.tabs(["Clients", "Projects"])
        with tab_clients:
            _render_clients_tab()
        with tab_projects:
            _render_projects_tab()


def page_reports():
    st.subheader("Reports")
    conn = get_conn()
    attendance_df = pd.read_sql_query(
        "SELECT attendance_date, employee_id, employee_name, employee_type, project_name, total_hours, ot_hours, status FROM attendance ORDER BY id DESC",
        conn,
    )
    payroll_df = pd.read_sql_query(
        """
        SELECT payroll_id, employee_id, employee_name, payroll_month, payroll_year,
               worked_days, paid_weekly_off_days, paid_holiday_days, total_ot_hours,
               normal_salary_amount, ot_amount, deductions, net_salary,
               workflow_status, payment_status, payment_mode
        FROM payroll ORDER BY id DESC
        """,
        conn,
    )
    ot_report_df = pd.read_sql_query(
        """
        SELECT attendance_date, employee_name, project_name, attendance_category,
               total_hours, ot_hours, status
        FROM attendance
        WHERE COALESCE(ot_hours, overtime, 0) > 0
        ORDER BY id DESC
        """,
        conn,
    )
    expense_df = pd.read_sql_query(
        "SELECT expense_id, expense_date, expense_head, project_name, amount, paid_to FROM expenses ORDER BY id DESC",
        conn,
    )
    payment_df = pd.read_sql_query(
        "SELECT voucher_number, payment_date, payment_type, pay_to_name, project_name, amount FROM payments ORDER BY id DESC",
        conn,
    )
    finance_df = pd.read_sql_query(
        """
        SELECT transaction_id, transaction_type, transaction_date, project_name, category_head,
               pay_to_name, amount, status, funding_source
        FROM finance_transactions
        ORDER BY id DESC
        """,
        conn,
    )
    employee_df = pd.read_sql_query(
        "SELECT employee_id, employee_name, joining_date, leaving_date, status FROM employees ORDER BY id DESC",
        conn,
    )
    project_labor_df = pd.read_sql_query(
        """
        SELECT project_name, COUNT(*) AS attendance_entries, ROUND(COALESCE(SUM(total_hours), 0), 2) AS total_hours
        FROM attendance
        GROUP BY project_name
        ORDER BY project_name
        """,
        conn,
    )
    subcontractor_bill_df = pd.read_sql_query(
        """
        SELECT bill_id, bill_date, bill_month, subcontractor_name,
               labour_amount, boq_amount, advance_amount, total_amount, net_amount, status
        FROM subcontractor_bills
        ORDER BY id DESC
        """,
        conn,
    )
    boq_summary_df = pd.read_sql_query(
        """
        SELECT project_name, subcontractor_name, boq_item, unit,
               ROUND(COALESCE(SUM(quantity), 0), 2) AS total_quantity,
               ROUND(COALESCE(AVG(rate), 0), 2) AS average_rate,
               ROUND(COALESCE(SUM(amount), 0), 2) AS total_amount
        FROM subcontractor_boq_entries
        GROUP BY project_name, subcontractor_name, boq_item, unit
        ORDER BY project_name, subcontractor_name, boq_item
        """,
        conn,
    )
    conn.close()

    tabs = st.tabs(
        [
            "Attendance Report",
            "Salary Report",
            "Expense Report",
            "Client Payment Report",
            "Finance Register",
            "OT Report",
            "Employee Joining Report",
            "Employee Exit Report",
            "Project Wise Labour Report",
            "Sub Contractor Bill Report",
            "BOQ Measurement Summary",
        ]
    )
    attendance_display_df = _format_attendance_hours_df(attendance_df)
    ot_report_display_df = _format_attendance_hours_df(ot_report_df)
    reports = [
        ("attendance_report.xlsx", attendance_display_df),
        ("salary_report.xlsx", payroll_df),
        ("expense_report.xlsx", expense_df),
        ("client_payment_report.xlsx", payment_df),
        ("finance_register.xlsx", finance_df),
        ("ot_report.xlsx", ot_report_display_df),
        ("employee_joining_report.xlsx", employee_df[["employee_id", "employee_name", "joining_date", "status"]] if not employee_df.empty else employee_df),
        ("employee_exit_report.xlsx", employee_df[["employee_id", "employee_name", "leaving_date", "status"]] if not employee_df.empty else employee_df),
        ("project_wise_labour_report.xlsx", project_labor_df),
        ("subcontractor_bill_report.xlsx", subcontractor_bill_df),
        ("boq_measurement_summary.xlsx", boq_summary_df),
    ]
    for tab, (file_name, df) in zip(tabs, reports):
        with tab:
            st.dataframe(df, width="stretch", hide_index=True)
            _download_dataframe(df, file_name)


def page_settings():
    st.subheader("Settings & Masters")
    tab_labels = [
        "Dashboard",
        "Users",
        "Countries",
        "Regions",
        "Districts",
        "Holidays",
        "Weekly Offs",
        "Departments",
        "Designations",
        "Payment Heads",
        "Expense Heads",
        "Salary Rules",
        "OT Rules",
        "Managers",
    ]
    focus = st.session_state.pop("settings_focus", None)
    focus_index = {
        "dashboard": 0,
        "users": 1,
        "accounts": 9,
        "company": 0,
    }.get(focus or "", None)

    tabs = st.tabs(tab_labels)
    tab_handlers = [
        _settings_dashboard,
        _settings_users,
        lambda: _settings_lookup("countries", "country_name", "Country"),
        _settings_regions,
        _settings_districts,
        _settings_holidays,
        _settings_weekly_offs,
        lambda: _settings_lookup("departments", "department_name", "Department"),
        lambda: _settings_lookup("designations", "designation_name", "Designation"),
        lambda: _settings_lookup("payment_heads", "head_name", "Payment Head"),
        lambda: _settings_lookup("expense_heads", "head_name", "Expense Head"),
        lambda: _settings_rule_table("salary_rules", "Salary Rule"),
        lambda: _settings_rule_table("ot_rules", "OT Rule"),
        _settings_managers,
    ]
    if focus == "accounts":
        st.caption("Payment heads and expense heads (accounts master).")
        with tabs[9]:
            tab_handlers[9]()
        with tabs[10]:
            tab_handlers[10]()
        return
    if focus_index is not None:
        with tabs[focus_index]:
            tab_handlers[focus_index]()
        return
    for tab, handler in zip(tabs, tab_handlers):
        with tab:
            handler()


def _settings_dashboard():
    st.markdown("### Dashboard Settings")
    st.caption("Control dashboard sections, order, role access, and sidebar cash flow visibility.")
    current = get_dashboard_settings()
    current_role_visibility = get_dashboard_role_visibility()

    st.markdown("#### General Visibility")
    c1, c2 = st.columns(2)
    show_welcome = c1.checkbox("Show Welcome Header", value=current.get("show_welcome", True))
    show_kpis = c2.checkbox("Show KPI Cards", value=current.get("show_kpis", True))
    show_attendance_overview = c1.checkbox(
        "Show Attendance Overview",
        value=current.get("show_attendance_overview", True),
    )
    show_project_overview = c2.checkbox(
        "Show Project Overview",
        value=current.get("show_project_overview", True),
    )
    show_expense_overview = c1.checkbox(
        "Show Expenses Overview",
        value=current.get("show_expense_overview", True),
    )
    show_recent_payments = c2.checkbox(
        "Show Recent Payments",
        value=current.get("show_recent_payments", True),
    )
    show_notifications = c1.checkbox(
        "Show Notifications",
        value=current.get("show_notifications", True),
    )
    show_sidebar_cashflow = c2.checkbox(
        "Show Sidebar Cash Flow",
        value=current.get("show_sidebar_cashflow", True),
    )

    st.markdown("#### Section Order")
    order_rows = []
    current_order = current.get("section_order", DASHBOARD_SECTION_ORDER_DEFAULT[:])
    for index, section_key in enumerate(current_order, start=1):
        order_rows.append(
            {
                "Section Key": section_key,
                "Section": DASHBOARD_SECTION_LABELS[section_key],
                "Sort Order": index,
            }
        )
    order_df = pd.DataFrame(order_rows)
    edited_order_df = st.data_editor(
        order_df,
        width="stretch",
        hide_index=True,
        disabled=["Section Key", "Section"],
        key="dashboard_order_editor",
    )

    st.markdown("#### Role-Wise Dashboard Visibility")
    role_rows = []
    for role in DASHBOARD_ROLES:
        row = {"Role": role}
        for section_key, label in DASHBOARD_SECTION_LABELS.items():
            row[label] = current_role_visibility.get(role, {}).get(section_key, True)
        role_rows.append(row)
    role_df = pd.DataFrame(role_rows)
    edited_role_df = st.data_editor(
        role_df,
        width="stretch",
        hide_index=True,
        disabled=["Role"],
        key="dashboard_role_visibility_editor",
    )

    if st.button("SAVE DASHBOARD SETTINGS", type="primary", width="stretch", key="save_dashboard_settings_button"):
        sorted_order_df = edited_order_df.sort_values(["Sort Order", "Section"])
        section_order = sorted_order_df["Section Key"].tolist()
        role_visibility = {}
        for _, row in edited_role_df.iterrows():
            role_name = row["Role"]
            role_visibility[role_name] = {
                section_key: bool(row[label])
                for section_key, label in DASHBOARD_SECTION_LABELS.items()
            }

        save_dashboard_settings(
            {
                "show_welcome": show_welcome,
                "show_kpis": show_kpis,
                "show_attendance_overview": show_attendance_overview,
                "show_project_overview": show_project_overview,
                "show_expense_overview": show_expense_overview,
                "show_recent_payments": show_recent_payments,
                "show_notifications": show_notifications,
                "show_sidebar_cashflow": show_sidebar_cashflow,
                "section_order": section_order,
            }
        )
        save_dashboard_role_visibility(role_visibility)
        st.success("Dashboard settings saved.")
        st.rerun()


def _settings_holidays():
    st.markdown("### Holiday Master")
    projects = ["All Projects"] + load_project_names()
    c1, c2, c3 = st.columns(3)
    holiday_name = c1.text_input("Holiday Name", key="holiday_name")
    holiday_date = c2.date_input("Holiday Date", key="holiday_date")
    holiday_type = c3.selectbox("Holiday Type", ["National", "Company", "Festival"], key="holiday_type")
    d1, d2, d3 = st.columns(3)
    applicable_for = d1.selectbox("Applicable For", ["Company Staff", "Sub Contractor Workers", "All"], key="holiday_applicable_for")
    payment_type = d2.selectbox("Payment Type", ["Paid", "Unpaid"], key="holiday_payment_type")
    project_name = d3.selectbox("Project", projects, key="holiday_project_name")
    e1, e2, e3 = st.columns(3)
    attendance_marking_type = e1.selectbox(
        "Attendance Marking Type",
        ["Auto Present", "Paid Leave", "Holiday Only"],
        key="holiday_attendance_marking_type",
    )
    approval_status = e2.selectbox("Approval Status", ["Approved", "Pending"], key="holiday_approval_status")
    remarks = e3.text_input("Remarks", key="holiday_remarks")
    if st.button("SAVE HOLIDAY", type="primary", width="stretch", key="save_holiday"):
        if not holiday_name.strip():
            st.error("Holiday Name is required.")
        else:
            holiday_id = generate_id("HOL", "holiday_master")
            conn = get_conn()
            conn.execute(
                """
                INSERT INTO holiday_master(
                    holiday_id, holiday_name, holiday_date, holiday_type, applicable_for,
                    payment_type, project_name, attendance_marking_type, approval_status, remarks
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    holiday_id,
                    holiday_name.strip(),
                    holiday_date.strftime(DATE_FMT),
                    holiday_type,
                    applicable_for,
                    payment_type,
                    project_name,
                    attendance_marking_type,
                    approval_status,
                    remarks.strip(),
                ),
            )
            conn.commit()
            conn.close()
            st.success(f"Holiday saved. ID: {holiday_id}")
            st.rerun()
    conn = get_conn()
    holiday_df = pd.read_sql_query(
        """
        SELECT holiday_id, holiday_name, holiday_date, holiday_type, applicable_for,
               payment_type, project_name, attendance_marking_type, approval_status
        FROM holiday_master
        ORDER BY holiday_date DESC, id DESC
        """,
        conn,
    )
    st.dataframe(holiday_df, width="stretch", hide_index=True)
    conn.close()

    pending_holidays = {
        f"{row['holiday_date']} | {row['holiday_name']} | {row['applicable_for']}": row["holiday_id"]
        for _, row in holiday_df.iterrows()
        if str(row.get("approval_status", "")).strip() == "Pending"
    }
    if pending_holidays:
        st.markdown("#### Holiday Approval")
        c1, c2 = st.columns(2)
        selected_pending_holiday = c1.selectbox(
            "Pending Holiday",
            list(pending_holidays.keys()),
            key="holiday_pending_select",
        )
        approval_action = c2.selectbox(
            "Action",
            ["Approved", "Rejected"],
            key="holiday_pending_action",
        )
        if st.button("UPDATE HOLIDAY STATUS", type="secondary", width="stretch", key="holiday_update_status"):
            conn = get_conn()
            conn.execute(
                "UPDATE holiday_master SET approval_status = ? WHERE holiday_id = ?",
                (approval_action, pending_holidays[selected_pending_holiday]),
            )
            conn.commit()
            conn.close()
            st.success(f"Holiday marked as {approval_action}.")
            st.rerun()

    approved_holidays = {
        f"{row['holiday_date']} | {row['holiday_name']} | {row['applicable_for']}": row["holiday_id"]
        for _, row in holiday_df.iterrows()
        if str(row.get("approval_status", "")).strip() == "Approved"
    }
    if approved_holidays:
        selected_holiday = st.selectbox(
            "Approved Holiday For Auto Attendance",
            list(approved_holidays.keys()),
            key="holiday_auto_attendance_select",
        )
        if st.button("AUTO CREATE HOLIDAY ATTENDANCE", type="secondary", width="stretch", key="holiday_auto_attendance_button"):
            created_rows = _auto_create_holiday_attendance(approved_holidays[selected_holiday])
            st.success(f"Holiday attendance created for {created_rows} employee(s).")
            st.rerun()


def _settings_weekly_offs():
    st.markdown("### Weekly Off Settings")
    projects = ["All Projects"] + load_project_names()
    c1, c2, c3, c4 = st.columns(4)
    weekly_off_day = c1.selectbox(
        "Weekly Off Day",
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        key="weekly_off_day",
    )
    payment_type = c2.selectbox("Payment Type", ["Paid", "Unpaid"], key="weekly_off_payment_type")
    applicable_for = c3.selectbox("Applicable For", ["Company Staff", "Sub Contractor Workers", "All"], key="weekly_off_applicable_for")
    project_name = c4.selectbox("Project", projects, key="weekly_off_project")
    d1, d2 = st.columns(2)
    status = d1.selectbox("Status", ["Active", "Inactive"], key="weekly_off_status")
    remarks = d2.text_input("Remarks", key="weekly_off_remarks")
    if st.button("SAVE WEEKLY OFF", type="primary", width="stretch", key="save_weekly_off"):
        weekly_off_id = generate_id("WOF", "weekly_off_settings")
        conn = get_conn()
        conn.execute(
            """
            INSERT INTO weekly_off_settings(
                weekly_off_id, weekly_off_day, payment_type, applicable_for, project_name, status, remarks
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                weekly_off_id,
                weekly_off_day,
                payment_type,
                applicable_for,
                project_name,
                status,
                remarks.strip(),
            ),
        )
        conn.commit()
        conn.close()
        st.success(f"Weekly off saved. ID: {weekly_off_id}")
        st.rerun()
    conn = get_conn()
    st.dataframe(
        pd.read_sql_query(
            """
            SELECT weekly_off_id, weekly_off_day, payment_type, applicable_for, project_name, status, remarks
            FROM weekly_off_settings
            ORDER BY id DESC
            """,
            conn,
        ),
        width="stretch",
        hide_index=True,
    )
    conn.close()


def _auto_create_holiday_attendance(holiday_id):
    conn = get_conn()
    holiday_df = pd.read_sql_query(
        "SELECT * FROM holiday_master WHERE holiday_id = ? LIMIT 1",
        conn,
        params=(holiday_id,),
    )
    if holiday_df.empty:
        conn.close()
        return 0

    holiday = holiday_df.iloc[0].to_dict()
    if str(holiday.get("approval_status", "")).strip() != "Approved":
        conn.close()
        return 0

    sql = "SELECT * FROM employees WHERE COALESCE(employee_id, '') != ''"
    params = []
    applicable_for = holiday.get("applicable_for", "All")
    if applicable_for == "Company Staff":
        sql += " AND employee_type = ?"
        params.append("Company Staff")
    elif applicable_for == "Sub Contractor Workers":
        sql += " AND employee_type = ?"
        params.append("Sub Contractor Worker")
    if holiday.get("project_name") not in ("", "All Projects", None):
        sql += " AND COALESCE(project_name, '') = ?"
        params.append(holiday.get("project_name"))

    employee_df = pd.read_sql_query(sql, conn, params=params or None)
    created = 0
    for _, employee in employee_df.iterrows():
        employee_id = employee["employee_id"]
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM attendance WHERE COALESCE(employee_id, worker_id) = ? AND attendance_date = ?",
            (employee_id, holiday["holiday_date"]),
        )
        if cur.fetchone()[0]:
            continue

        fixed_hours = 8.0
        applied_rate = 0.0
        applied_ot_rate = 0.0
        if employee.get("employee_type") == "Sub Contractor Worker" and str(holiday.get("payment_type", "Paid")) == "Paid":
            rate_card = load_subcontractor_labour_rate(
                employee.get("company_or_subcontractor", ""),
                employee.get("project_name", ""),
                employee.get("designation", ""),
                "8 Hours",
            )
            if rate_card:
                fixed_hours = float(rate_card.get("fixed_hours") or 8.0)
                applied_rate = float(rate_card.get("rate") or 0.0)
                applied_ot_rate = float(rate_card.get("ot_rate") or 0.0)
            else:
                applied_rate = float(employee.get("salary_amount") or 0.0)

        marking_type = str(holiday.get("attendance_marking_type", "Holiday Only"))
        if marking_type == "Auto Present":
            status = "Present"
            total_hours = fixed_hours if str(holiday.get("payment_type", "Paid")) == "Paid" else 0.0
        elif marking_type == "Paid Leave":
            status = "Leave"
            total_hours = 0.0
        else:
            status = "Holiday"
            total_hours = 0.0

        if str(holiday.get("payment_type", "Paid")) != "Paid":
            applied_rate = 0.0
            applied_ot_rate = 0.0

        conn.execute(
            """
            INSERT INTO attendance(
                employee_id, employee_name, employee_type, department, designation,
                project_name, sub_contractor, attendance_date, in_time, out_time,
                break_hours, total_hours, ot_hours, status, remarks,
                worker_id, worker_name, start_time, end_time, worked_hours, overtime, work_description,
                fixed_working_hours, applied_rate, applied_ot_rate, attendance_category, payment_type, holiday_name
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                employee_id,
                employee.get("employee_name", ""),
                employee.get("employee_type", ""),
                employee.get("department", ""),
                employee.get("designation", ""),
                employee.get("project_name", ""),
                employee.get("company_or_subcontractor", "") if employee.get("employee_type") == "Sub Contractor Worker" else "",
                holiday["holiday_date"],
                "",
                "",
                0.0,
                total_hours,
                0.0,
                status,
                holiday.get("remarks", ""),
                employee_id,
                employee.get("employee_name", ""),
                "",
                "",
                total_hours,
                0.0,
                holiday.get("holiday_name", ""),
                fixed_hours,
                applied_rate,
                applied_ot_rate,
                "Holiday",
                holiday.get("payment_type", "Paid"),
                holiday.get("holiday_name", ""),
            ),
        )
        created += 1

    conn.commit()
    conn.close()
    return created


def _settings_lookup(table, column, label):
    with st.form(f"{table}_form", clear_on_submit=True):
        value = st.text_input(label)
        if st.form_submit_button(f"SAVE {label.upper()}", type="primary", width="stretch"):
            if value.strip():
                conn = get_conn()
                conn.execute(f"INSERT OR IGNORE INTO {table}({column}) VALUES(?)", (value.strip(),))
                conn.commit()
                conn.close()
                st.success(f"{label} saved.")
                st.rerun()
    conn = get_conn()
    st.dataframe(
        pd.read_sql_query(f"SELECT {column} FROM {table} ORDER BY {column}", conn),
        width="stretch",
        hide_index=True,
    )
    conn.close()


def _settings_regions():
    st.markdown("### Region / State Master")
    countries = load_countries() or ["India"]
    selected_country = st.selectbox("Country", countries, key="settings_region_country")
    region_name = st.text_input("Add New Region / State", key="settings_region_name")
    if st.button("SAVE REGION / STATE", type="primary", width="stretch", key="settings_region_save"):
        if not region_name.strip():
            st.error("Region / State name is required.")
        else:
            ensure_region(selected_country, region_name.strip())
            st.success("Region / State saved.")
            st.rerun()
    conn = get_conn()
    st.dataframe(
        pd.read_sql_query(
            """
            SELECT c.country_name AS country, r.region_name AS region
            FROM regions r
            LEFT JOIN countries c ON c.id = r.country_id
            ORDER BY c.country_name, r.region_name
            """,
            conn,
        ),
        width="stretch",
        hide_index=True,
    )
    conn.close()


def _settings_districts():
    st.markdown("### District Master")
    country, region, _ = location_dropdowns("settings_district_location", default_country="India")
    district_name = st.text_input("Add New District", key="settings_district_name")
    if st.button("SAVE DISTRICT", type="primary", width="stretch", key="settings_district_save"):
        if not region:
            st.error("Please select a Region / State.")
        elif not district_name.strip():
            st.error("District name is required.")
        else:
            ensure_district(country, region, district_name.strip())
            st.success("District saved.")
            st.rerun()
    conn = get_conn()
    st.dataframe(
        pd.read_sql_query(
            """
            SELECT c.country_name AS country, r.region_name AS region, d.district_name AS district
            FROM districts d
            LEFT JOIN regions r ON r.id = d.region_id
            LEFT JOIN countries c ON c.id = r.country_id
            ORDER BY c.country_name, r.region_name, d.district_name
            """,
            conn,
        ),
        width="stretch",
        hide_index=True,
    )
    conn.close()


def _settings_rule_table(table, label):
    with st.form(f"{table}_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        rule_name = c1.text_input(f"{label} Name")
        description = c2.text_input("Description")
        if st.form_submit_button(f"SAVE {label.upper()}", type="primary", width="stretch"):
            if rule_name.strip():
                conn = get_conn()
                conn.execute(
                    f"INSERT INTO {table}(rule_name, description) VALUES(?, ?)",
                    (rule_name.strip(), description.strip()),
                )
                conn.commit()
                conn.close()
                st.success(f"{label} saved.")
                st.rerun()
    conn = get_conn()
    st.dataframe(
        pd.read_sql_query(f"SELECT rule_name, description FROM {table} ORDER BY id DESC", conn),
        width="stretch",
        hide_index=True,
    )
    conn.close()


def _settings_managers():
    st.markdown("### Manager Master")
    country, region, district = location_dropdowns(
        "settings_manager_location",
        default_country="India",
        show_region=False,
        show_district=False,
    )
    c1, c2 = st.columns(2)
    new_manager = c1.text_input("Manager Name", key="settings_manager_name")
    contact_number = c2.text_input("Contact Number", key="settings_manager_contact")
    if st.button("SAVE MANAGER", type="primary", width="stretch", key="settings_manager_save"):
        if not new_manager.strip():
            st.error("Manager Name is required.")
        else:
            conn = get_conn()
            conn.execute(
                "INSERT INTO managers(manager_name, country, region, district, contact_number) VALUES(?,?,?,?,?)",
                (new_manager.strip(), country, "", "", contact_number.strip()),
            )
            conn.commit()
            conn.close()
            st.success("Manager saved.")
            st.rerun()
    conn = get_conn()
    st.dataframe(
        pd.read_sql_query(
            "SELECT manager_name, country, region, district, contact_number FROM managers ORDER BY country, region, district, manager_name",
            conn,
        ),
        width="stretch",
        hide_index=True,
    )
    conn.close()


def page_masters_users():
    st.subheader("User Management")
    if not can_manage_users(st.session_state.get("user_role", "Admin")):
        st.error("Only Super Admin (Owner / MD) can create and manage users.")
        return
    _settings_users()


def _settings_users():
    st.markdown("### User Creation")
    st.caption(
        "Create login users for Super Admin, System Admin, HR, Accounts, Project Manager, and Site Engineer."
    )

    with st.form("users_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        full_name = c1.text_input("Full Name")
        username = c2.text_input("Username")
        password = c3.text_input("Password", type="password")
        role = c1.selectbox(
            "Role",
            ERP_USER_ROLES,
        )
        mobile = c2.text_input("Mobile")
        confirm_password = c3.text_input("Confirm Password", type="password")

        if st.form_submit_button("CREATE USER", type="primary", width="stretch"):
            if not full_name.strip() or not username.strip() or not password.strip():
                st.error("Full Name, Username, and Password are required.")
            elif password != confirm_password:
                st.error("Password and Confirm Password do not match.")
            else:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute(
                    "SELECT COUNT(*) FROM users WHERE LOWER(username)=LOWER(?)",
                    (username.strip(),),
                )
                exists = cur.fetchone()[0]

                if exists:
                    conn.close()
                    st.error("Username already exists. Please choose another username.")
                else:
                    user_id = generate_id("USR", "users")
                    conn.execute(
                        """
                        INSERT INTO users(user_id, full_name, username, password, role, mobile)
                        VALUES(?,?,?,?,?,?)
                        """,
                        (
                            user_id,
                            full_name.strip(),
                            username.strip(),
                            password,
                            role,
                            mobile.strip(),
                        ),
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"User created successfully. ID: {user_id}")
                    st.rerun()

    user_search = st.text_input("Search Users", placeholder="Search by name, username, or role")
    conn = get_conn()
    query = """
        SELECT user_id, full_name, username, role, mobile
        FROM users
    """
    params = ()
    if user_search.strip():
        query += """
            WHERE full_name LIKE ? OR username LIKE ? OR role LIKE ?
        """
        search_value = f"%{user_search.strip()}%"
        params = (search_value, search_value, search_value)
    query += " ORDER BY id DESC"
    users_df = pd.read_sql_query(query, conn, params=params)
    if not users_df.empty and "role" in users_df.columns:
        users_df = users_df.copy()
        users_df["role"] = users_df["role"].map(lambda r: display_role_name(str(r)))
    st.dataframe(users_df, width="stretch", hide_index=True)
    conn.close()


def _save_upload(uploaded_file, folder, prefix):
    if not uploaded_file:
        return ""
    ext = os.path.splitext(uploaded_file.name)[1] or ".bin"
    rel_path = os.path.join(folder, f"{prefix}{ext}")
    abs_path = os.path.join(BASE_DIR, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return rel_path.replace("\\", "/")


def _download_dataframe(df, file_name):
    if df.empty:
        st.info("No data available for this report.")
        return
    buf = BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    st.download_button(
        "Download Excel",
        data=buf,
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
