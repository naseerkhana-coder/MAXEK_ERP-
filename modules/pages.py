"""ERP page content for MAXEK Streamlit app."""

import base64
import os
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

from modules.database import (
    BASE_DIR,
    DASHBOARD_ROLES,
    DASHBOARD_SECTION_LABELS,
    DASHBOARD_SECTION_ORDER_DEFAULT,
    DATE_FMT,
    calculate_hours,
    ensure_district,
    ensure_region,
    generate_id,
    get_dashboard_settings,
    get_dashboard_role_visibility,
    get_conn,
    get_employee,
    load_active_holidays,
    load_subcontractor_boq_rates,
    load_client_names,
    load_countries,
    load_employee_options,
    load_lookup,
    load_project_names,
    load_managers,
    load_subcontractor_labour_rate,
    load_subcontractor_names,
    load_weekly_off_rules,
    parse_month_value,
    payroll_preview,
    save_dashboard_role_visibility,
    save_dashboard_settings,
    subcontractor_bill_preview,
)
from modules.ui import location_dropdowns


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
    for key, value in {
        "employee_type": "Company Staff",
        "employee_name": "",
        "employee_mobile": "",
        "employee_address": "",
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
    }.items():
        st.session_state[key] = value
    for idx in range(1, 6):
        st.session_state[f"employee_allowance_head_{idx}"] = ""
        st.session_state[f"employee_allowance_amount_{idx}"] = 0.0


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
    if a1.button("DELETE MANPOWER RATE", type="secondary", width="stretch", key="delete_labour_rate_btn"):
        conn = get_conn()
        conn.execute("DELETE FROM subcontractor_labour_rates WHERE rate_id=?", (selected_rate_id,))
        conn.commit()
        conn.close()
        st.success("Manpower rate deleted.")
        st.rerun()

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
    if b1.button("DELETE BOQ RATE", type="secondary", width="stretch", key="delete_boq_rate_btn"):
        conn = get_conn()
        conn.execute("DELETE FROM subcontractor_boq_rates WHERE boq_rate_id=?", (selected_rate_id,))
        conn.commit()
        conn.close()
        st.success("BOQ rate deleted.")
        st.rerun()

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

    departments = [""] + load_lookup("departments", "department_name")
    designations = [""] + load_lookup("designations", "designation_name")
    project_names = [""] + load_project_names()
    subcontractors = [""] + load_subcontractor_names()
    allowance_heads = load_lookup("allowance_heads", "head_name")

    st.markdown("### Basic Details")
    c1, c2, c3 = st.columns(3)
    employee_type = c1.selectbox("Employee Type", ["Company Staff", "Sub Contractor Worker"], key="employee_type")
    preview_prefix = "EMP" if employee_type == "Company Staff" else "WRK"
    c1.caption(f"Employee ID (preview): {generate_id(preview_prefix, 'employees')}")
    employee_name = c2.text_input("Employee Name", key="employee_name")
    photo = c3.file_uploader("Photo Upload", type=["jpg", "jpeg", "png"], key="employee_photo")
    if photo is not None:
        _render_photo_preview(uploaded_file=photo)
    mobile_number = c1.text_input("Mobile Number", key="employee_mobile")
    address = c2.text_area("Address", key="employee_address")
    blood_group = c3.text_input("Blood Group", key="employee_blood_group")

    country, region, district = location_dropdowns(
        "employee_location",
        default_country="",
        default_region="",
        default_district="",
        allow_blank=True,
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
    if employee_type == "Company Staff":
        company_or_sub = j1.selectbox("Company", ["MAXEK PRIVATE LIMITED"], key="employee_company")
    else:
        company_or_sub = j1.selectbox(
            "Sub Contractor",
            subcontractors,
            index=0,
            key="employee_company",
        )
    project_name = j2.selectbox("Project", project_names, index=0, key="employee_project")
    department = j3.selectbox("Department", departments, index=0, key="employee_department")

    k1, k2, k3 = st.columns(3)
    designation = k1.selectbox("Designation", designations, index=0, key="employee_designation")
    allowance_amounts = {}
    allowance_total = 0.0
    basic_salary = 0.0
    if employee_type == "Company Staff":
        salary_type = k2.selectbox("Salary Type", ["Monthly", "Daily"], key="employee_salary_type")
        basic_salary = k3.number_input("Basic Salary", min_value=0.0, step=100.0, key="employee_basic_salary")
        allowance_amounts, allowance_total = _render_employee_allowance_inputs(allowance_heads, prefix="employee")
        salary_amount = basic_salary + allowance_total
        st.metric("Total Salary (Rs)", f"{salary_amount:,.2f}")
        l1, l2, l3 = st.columns(3)
        ot_applicable = l1.selectbox("OT Applicable", ["Yes", "No"], key="employee_ot_applicable")
        ot_rate = l2.number_input("OT Rate", min_value=0.0, step=10.0, key="employee_ot_rate")
        l3.empty()
    else:
        salary_type = "Daily"
        salary_amount = 0.0
        ot_applicable = "No"
        ot_rate = 0.0
        k2.caption("Salary and OT rates come from Sub Contractor labour rate or BOQ settings.")
        k3.empty()

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

    if st.button("SAVE EMPLOYEE", type="primary", width="stretch"):
        if not employee_name.strip():
            st.error("Employee Name is required.")
        elif employee_type == "Sub Contractor Worker" and not company_or_sub:
            st.error("Please select a Sub Contractor.")
        else:
            employee_prefix = "EMP" if employee_type == "Company Staff" else "WRK"
            employee_id = generate_id(employee_prefix, "employees")
            photo_path = _save_upload(photo, "uploads/employees", employee_id)
            dob_text = date_of_birth.strftime(DATE_FMT) if date_of_birth else ""
            conn = get_conn()
            conn.execute(
                """
                INSERT INTO employees(
                    employee_id, employee_type, employee_name, photo, mobile_number,
                    address, country, region, district, native_place, blood_group, aadhaar_number,
                    pan_number, date_of_birth, joining_date, leaving_date, status,
                    company_or_subcontractor, project_name, department, designation,
                    reporting_manager, salary_type, salary_amount, basic_salary,
                    ot_applicable, ot_rate, shift, experience, skills, remarks
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                    basic_salary if employee_type == "Company Staff" else 0.0,
                    ot_applicable,
                    ot_rate,
                    "",
                    experience,
                    "",
                    remarks,
                ),
            )
            if employee_type == "Company Staff":
                _save_employee_allowance_components(conn, employee_id, allowance_amounts)
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
            else:
                conn.execute(
                    """
                    INSERT INTO workers(worker_id, subcontractor_name, worker_name, trade_name, joining_date,
                                        salary, overtime_rate, photo, status, region, manager_name, country, state)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                    ),
                )
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
            _clear_employee_form_keys()
            st.session_state.employee_last_saved_id = employee_id
            st.rerun()

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
        st.markdown("### Company Details")
        c1, c2, c3 = st.columns(3)
        company_name = c1.text_input("Company Name", key="sub_company_name")
        contact_person = c2.text_input("Contact Person", key="sub_contact_person")
        mobile_number = c3.text_input("Mobile Number", key="sub_mobile_number")
        aadhaar_number = c1.text_input("Aadhaar Number", key="sub_aadhaar_number")
        pan_number = c2.text_input("PAN Number", key="sub_pan_number")
        address = c3.text_area("Address", key="sub_address")
        country, region, district = location_dropdowns(
            "subcontractor_location",
            default_country="",
            default_region="",
            default_district="",
            allow_blank=True,
        )
        d1, d2 = st.columns(2)
        active_projects = d1.multiselect("Projects (select all applicable projects)", projects, key="sub_active_projects")
        status = d2.selectbox("Status", ["Active", "Inactive"], key="sub_status")
        agreement_upload = st.file_uploader("Agreement Upload", key="sub_agreement_upload")

        rate_projects = active_projects if active_projects else projects
        rate_project_options = [""] + rate_projects

        st.markdown("### Manpower Rate Based")
        st.caption("Add designation-wise daily rates per project — e.g. Carpenter Rs 800/day for 8 Hours or 10 Hours. Not salary based.")
        m1, m2, m3, m4 = st.columns(4)
        draft_designation_pick = m1.selectbox(
            "Designation",
            [""] + designation_options,
            key="sub_draft_designation_pick",
        )
        draft_designation_custom = m1.text_input(
            "Or type designation",
            key="sub_draft_designation_custom",
            placeholder="Carpenter",
        )
        draft_labour_project = m2.selectbox("Project", rate_project_options, index=0, key="sub_draft_labour_project")
        draft_working_hours = m3.selectbox(
            "Working Hours",
            ["8 Hours", "10 Hours", "12 Hours"],
            key="sub_draft_working_hours",
        )
        draft_daily_rate = m4.number_input("Daily Rate (Rs)", min_value=0.0, step=50.0, key="sub_draft_daily_rate")
        n1, n2, n3 = st.columns(3)
        draft_ot_applicable = n1.selectbox("OT Applicable", ["Yes", "No"], key="sub_draft_ot_applicable")
        default_ot = draft_daily_rate / max(1.0, float(draft_working_hours.split()[0])) if draft_daily_rate else 0.0
        draft_ot_rate = n2.number_input("OT Rate (Rs/hr)", min_value=0.0, step=10.0, value=float(default_ot), key="sub_draft_ot_rate")
        if n3.button("ADD MANPOWER RATE", width="stretch", key="add_sub_draft_labour_rate"):
            designation = (draft_designation_custom or draft_designation_pick or "").strip()
            if not designation:
                st.error("Designation is required for manpower rate.")
            elif not draft_labour_project:
                st.error("Project is required for manpower rate.")
            elif draft_daily_rate <= 0:
                st.error("Daily rate must be greater than zero.")
            else:
                st.session_state.sub_draft_labour_rates.append(
                    {
                        "designation": designation,
                        "project_name": draft_labour_project,
                        "working_hours": draft_working_hours,
                        "daily_rate": draft_daily_rate,
                        "ot_applicable": draft_ot_applicable,
                        "ot_rate": draft_ot_rate if draft_ot_applicable == "Yes" else 0.0,
                        "status": "Active",
                    }
                )
                st.success(f"Manpower rate added: {designation} | {draft_labour_project} | {draft_working_hours}")
                st.rerun()

        if st.session_state.sub_draft_labour_rates:
            labour_df = pd.DataFrame(st.session_state.sub_draft_labour_rates)
            labour_df = labour_df.rename(
                columns={
                    "designation": "Designation",
                    "project_name": "Project",
                    "working_hours": "Working Hours",
                    "daily_rate": "Daily Rate",
                    "ot_applicable": "OT",
                    "ot_rate": "OT Rate",
                }
            )
            st.dataframe(labour_df, width="stretch", hide_index=True)
            for idx in range(len(st.session_state.sub_draft_labour_rates)):
                if st.button(f"Remove manpower rate #{idx + 1}", key=f"remove_sub_draft_labour_{idx}"):
                    st.session_state.sub_draft_labour_rates.pop(idx)
                    st.rerun()
        else:
            st.info("No manpower rates added yet. Example: Carpenter | Skyline Tower | 8 Hours | Rs 800/day.")

        st.markdown("### BOQ / Measurement Based")
        st.caption("Add measurement-based rates per project — e.g. Shuttering Work SQM Rs 100, Steel Fixing Ton Rs 6000.")
        b1, b2, b3, b4 = st.columns(4)
        draft_boq_project = b1.selectbox("Project", rate_project_options, index=0, key="sub_draft_boq_project")
        draft_boq_item = b2.text_input("BOQ Item", key="sub_draft_boq_item", placeholder="Shuttering Work")
        draft_boq_unit = b3.text_input("Unit", key="sub_draft_boq_unit", placeholder="SQM, Ton, RMT")
        draft_boq_rate = b4.number_input("Rate (Rs)", min_value=0.0, step=100.0, key="sub_draft_boq_rate")
        if st.button("ADD BOQ RATE", width="stretch", key="add_sub_draft_boq_rate"):
            if not draft_boq_project:
                st.error("Project is required for BOQ rate.")
            elif not draft_boq_item.strip():
                st.error("BOQ Item is required.")
            elif not draft_boq_unit.strip():
                st.error("Unit is required.")
            elif draft_boq_rate <= 0:
                st.error("BOQ rate must be greater than zero.")
            else:
                st.session_state.sub_draft_boq_rates.append(
                    {
                        "project_name": draft_boq_project,
                        "boq_item": draft_boq_item.strip(),
                        "unit": draft_boq_unit.strip(),
                        "rate": draft_boq_rate,
                        "status": "Active",
                    }
                )
                st.success(f"BOQ rate added: {draft_boq_item.strip()} | {draft_boq_project}")
                st.rerun()

        if st.session_state.sub_draft_boq_rates:
            boq_df = pd.DataFrame(st.session_state.sub_draft_boq_rates)
            boq_df = boq_df.rename(
                columns={
                    "project_name": "Project",
                    "boq_item": "BOQ Item",
                    "unit": "Unit",
                    "rate": "Rate",
                }
            )
            st.dataframe(boq_df, width="stretch", hide_index=True)
            for idx in range(len(st.session_state.sub_draft_boq_rates)):
                if st.button(f"Remove BOQ rate #{idx + 1}", key=f"remove_sub_draft_boq_{idx}"):
                    st.session_state.sub_draft_boq_rates.pop(idx)
                    st.rerun()
        else:
            st.info("No BOQ rates added yet.")

        if st.button("SAVE SUB CONTRACTOR", type="primary", width="stretch", key="save_sub_contractor_master"):
            if not company_name.strip():
                st.error("Company Name is required.")
            else:
                subcontractor_id = generate_id("SC", "subcontractors")
                agreement_path = _save_upload(agreement_upload, "uploads/subcontractors", subcontractor_id)
                trade_summary = ", ".join(
                    sorted({row["designation"] for row in st.session_state.sub_draft_labour_rates})
                )
                conn = get_conn()
                conn.execute(
                    """
                    INSERT INTO subcontractors(
                        subcontractor_id, subcontractor_name, company_name, contact_person,
                        contact_number, aadhaar_number, pan_card_number, address, country, region,
                        district, trade, agreement_upload, active_projects, worker_count, status, state
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        subcontractor_id,
                        company_name,
                        company_name,
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
                    ),
                )
                for row in st.session_state.sub_draft_labour_rates:
                    _insert_subcontractor_labour_rate(conn, company_name, row)
                for row in st.session_state.sub_draft_boq_rates:
                    _insert_subcontractor_boq_rate(conn, company_name, row)
                if agreement_path:
                    conn.execute(
                        """
                        INSERT INTO document_uploads(entity_type, entity_id, document_type, file_path, uploaded_at)
                        VALUES(?,?,?,?,?)
                        """,
                        ("subcontractor", subcontractor_id, "Agreement", agreement_path, datetime.now().strftime("%d/%m/%Y %H:%M")),
                    )
                conn.commit()
                conn.close()
                labour_count = len(st.session_state.sub_draft_labour_rates)
                boq_count = len(st.session_state.sub_draft_boq_rates)
                _reset_subcontractor_draft()
                st.success(
                    f"Sub contractor saved. ID: {subcontractor_id} | "
                    f"{labour_count} manpower rate(s), {boq_count} BOQ rate(s)."
                )
                st.rerun()

        conn = get_conn()
        st.markdown("### Saved Sub Contractors")
        st.dataframe(
            pd.read_sql_query(
                """
                SELECT subcontractor_id, COALESCE(company_name, subcontractor_name) AS company_name,
                       contact_person, contact_number, active_projects, trade AS designations,
                       country, region, district, status
                FROM subcontractors
                ORDER BY id DESC
                """,
                conn,
            ),
            width="stretch",
            hide_index=True,
        )
        conn.close()

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


def page_attendance():
    st.subheader("Attendance")
    employee_options = load_employee_options()
    employee_map = {f"{employee_id} - {employee_name}": employee_id for employee_id, employee_name in employee_options}
    if not employee_map:
        st.warning("Add employees first.")
        return

    selected = st.selectbox("Employee", list(employee_map.keys()))
    employee = get_employee(employee_map[selected])
    if not employee:
        st.error("Employee not found.")
        return

    c1, c2, c3 = st.columns(3)
    c1.text_input("Employee Type", value=employee.get("employee_type", ""), disabled=True)
    c2.text_input("Department", value=employee.get("department", ""), disabled=True)
    c3.text_input("Designation", value=employee.get("designation", ""), disabled=True)
    d1, d2, d3 = st.columns(3)
    attendance_date = d1.date_input("Date")
    in_time = d2.text_input("In Time", value="08:00")
    out_time = d3.text_input("Out Time", value="17:00")
    project_names = [""] + load_project_names()
    project_default = employee.get("project_name", "")
    project_index = project_names.index(project_default) if project_default in project_names else 0
    e1, e2, e3 = st.columns(3)
    break_time = e1.number_input("Break Time", min_value=0.0, step=0.5, value=1.0)
    project_name = e2.selectbox("Project", project_names, index=project_index)
    sub_contractor = e3.text_input(
        "Sub Contractor",
        value=employee.get("company_or_subcontractor", "") if employee.get("employee_type") == "Sub Contractor Worker" else "",
    )

    fixed_working_hours = 8.0
    applied_rate = float(employee.get("salary_amount") or 0)
    applied_ot_rate = float(employee.get("ot_rate") or 0)
    ot_allowed = (employee.get("ot_applicable") or "").lower() == "yes"
    if employee.get("employee_type") == "Sub Contractor Worker":
        w1, w2, w3 = st.columns(3)
        working_hours = w1.selectbox("Working Hours", ["8 Hours", "10 Hours", "12 Hours"], key="attendance_working_hours")
        rate_card = load_subcontractor_labour_rate(
            sub_contractor,
            project_name,
            employee.get("designation", ""),
            working_hours,
        )
        fixed_working_hours = float(rate_card.get("fixed_hours") or working_hours.split()[0]) if rate_card else float(working_hours.split()[0])
        applied_rate = float(rate_card.get("rate") or employee.get("salary_amount") or 0) if rate_card else float(employee.get("salary_amount") or 0)
        ot_allowed = str(rate_card.get("ot_applicable") or "No").lower() == "yes" if rate_card else ot_allowed
        applied_ot_rate = float(rate_card.get("ot_rate") or 0) if rate_card else (applied_rate / fixed_working_hours if ot_allowed and fixed_working_hours else 0.0)
        if rate_card:
            w2.caption(
                f"Labour rate: Rs {applied_rate:,.2f} ({working_hours}). "
                f"OT {'on' if ot_allowed else 'off'} at Rs {applied_ot_rate:,.2f}/hr."
            )
        else:
            w2.caption("No active labour rate for this subcontractor / project / designation / hours.")
        w3.empty()

    total_hours, ot_hours = calculate_hours(in_time, out_time, break_time, fixed_working_hours, ot_allowed)
    f1, f2 = st.columns(2)
    f1.text_input("Total Hours", value=str(total_hours), disabled=True)
    f2.text_input("OT Hours", value=str(ot_hours), disabled=True)

    applicable_for = "Company Staff" if employee.get("employee_type") == "Company Staff" else "Sub Contractor Workers"
    attendance_date_str = attendance_date.strftime(DATE_FMT)
    holiday_df = load_active_holidays(attendance_date_str, applicable_for, project_name)
    weekly_off_df = load_weekly_off_rules(applicable_for, project_name)
    attendance_category = "Regular"
    payment_type = "Regular"
    holiday_name = ""
    default_status = "Present"
    if not holiday_df.empty:
        holiday = holiday_df.iloc[0]
        attendance_category = "Holiday"
        payment_type = holiday.get("payment_type", "Paid")
        holiday_name = holiday.get("holiday_name", "")
        marking_type = str(holiday.get("attendance_marking_type", "Holiday Only"))
        if marking_type == "Auto Present":
            default_status = "Present"
        elif marking_type == "Paid Leave":
            default_status = "Leave"
        else:
            default_status = "Holiday"
        st.caption(f"Holiday: {holiday_name} | Payment: {payment_type} | Marking: {marking_type}")
    else:
        weekday_name = attendance_date.strftime("%A")
        weekly_match = weekly_off_df[weekly_off_df["weekly_off_day"] == weekday_name] if not weekly_off_df.empty else pd.DataFrame()
        if not weekly_match.empty:
            off_rule = weekly_match.iloc[0]
            attendance_category = "Weekly Off"
            payment_type = off_rule.get("payment_type", "Unpaid")
            default_status = "Week Off"
            st.caption(f"Weekly off: {weekday_name} | Payment: {payment_type}")

    status_options = ["Present", "Absent", "Half Day", "Leave", "Holiday", "Week Off"]
    status = st.selectbox("Status", status_options, index=status_options.index(default_status) if default_status in status_options else 0)
    remarks = st.text_area("Remarks")

    if st.button("SAVE ATTENDANCE", type="primary", width="stretch"):
        conn = get_conn()
        attendance_date_str = attendance_date.strftime(DATE_FMT)
        duplicate = conn.execute(
            "SELECT id FROM attendance WHERE employee_id=? AND attendance_date=?",
            (employee["employee_id"], attendance_date_str),
        ).fetchone()
        if duplicate:
            conn.close()
            st.error("Attendance already saved for this employee on this date.")
        else:
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
            st.success("Attendance saved.")
            st.rerun()

    conn = get_conn()
    st.dataframe(
        pd.read_sql_query(
            """
            SELECT attendance_date, employee_id, employee_name, employee_type,
                   project_name, total_hours, ot_hours, applied_rate, attendance_category, status
            FROM attendance
            ORDER BY id DESC LIMIT 100
            """,
            conn,
        ),
        width="stretch",
        hide_index=True,
    )
    conn.close()


def page_payroll():
    st.subheader("Payroll")
    payroll_tab, advance_tab = st.tabs(["Payroll Calculation", "Sub Contractor Advances"])

    with payroll_tab:
        employee_options = load_employee_options()
        employee_map = {f"{employee_id} - {employee_name}": employee_id for employee_id, employee_name in employee_options}
        if not employee_map:
            st.info("Add employees first.")
        else:
            selected = st.selectbox("Employee", list(employee_map.keys()), key="payroll_employee_select")
            payroll_month = st.date_input("Payroll Month", key="payroll_month_select")
            preview = payroll_preview(employee_map[selected], payroll_month.strftime("%m/%Y"))
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Base Salary", f"Rs {preview['base_salary']:,.2f}")
            p2.metric("OT Amount", f"Rs {preview['ot_amount']:,.2f}")
            p3.metric("Working Days", int(preview["working_days"]))
            p4.metric("OT Hours", preview["ot_hours"])
            st.caption(f"Paid holidays / weekly offs counted: {int(preview.get('paid_non_working_days', 0))}")
            deductions = st.number_input("Advance / Other Deductions", min_value=0.0, step=100.0)
            net_salary = max(0.0, preview["base_salary"] + preview["ot_amount"] - deductions)
            st.success(f"Net Salary: Rs {net_salary:,.2f}")
            if st.button("GENERATE PAYROLL", type="primary", width="stretch"):
                payroll_id = generate_id("PY", "payroll")
                conn = get_conn()
                conn.execute(
                    """
                    INSERT INTO payroll(
                        payroll_id, employee_id, worker_id, payroll_month, base_salary,
                        ot_amount, deductions, salary, net_salary, salary_status, paid_date
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        payroll_id,
                        employee_map[selected],
                        employee_map[selected],
                        payroll_month.strftime("%m/%Y"),
                        preview["base_salary"],
                        preview["ot_amount"],
                        deductions,
                        net_salary,
                        net_salary,
                        "PAID",
                        datetime.now().strftime(DATE_FMT),
                    ),
                )
                conn.commit()
                conn.close()
                st.success(f"Payroll generated. ID: {payroll_id}")
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

    conn = get_conn()
    st.markdown("### Payroll Register")
    st.dataframe(
        pd.read_sql_query(
            """
            SELECT payroll_id, employee_id, payroll_month, base_salary, ot_amount,
                   deductions, net_salary, salary_status, paid_date
            FROM payroll
            ORDER BY id DESC
            """,
            conn,
        ),
        width="stretch",
        hide_index=True,
    )
    conn.close()


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
CLIENT_STATUS_OPTIONS = ["On Going", "Completed", "On Hold", "Inactive"]
PROJECT_STATUS_OPTIONS = ["On Going", "Completed", "On Hold", "Inactive"]


def _ensure_project_draft_boq():
    st.session_state.setdefault("project_draft_boq_items", [])


def _reset_project_draft_boq():
    st.session_state.project_draft_boq_items = []


def _insert_project_boq_item(conn, project_id, project_name, client_name, row):
    boq_item_id = generate_id("PB", "project_boq_items")
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

    if st.button("SAVE CLIENT", type="primary", width="stretch"):
        if not company_name.strip():
            st.error("Company Name is required.")
        else:
            client_id = generate_id("CL", "clients")
            saved_name = company_name.strip()
            document_path = _save_upload(document_upload, "uploads/clients", client_id)
            conn = get_conn()
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
            st.success(f"Client saved. ID: {client_id}")
            st.rerun()

    conn = get_conn()
    st.markdown("#### Saved Clients")
    st.dataframe(
        pd.read_sql_query(
            """
            SELECT client_id, COALESCE(company_name, client_name) AS company_name,
                   contact_person, mobile, work_order_no, total_work_amount, status
            FROM clients
            ORDER BY id DESC
            """,
            conn,
        ),
        width="stretch",
        hide_index=True,
    )
    conn.close()


def _render_projects_tab():
    _ensure_project_draft_boq()
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
            if st.button(f"Remove BOQ line #{idx + 1}", key=f"remove_project_draft_boq_{idx}"):
                st.session_state.project_draft_boq_items.pop(idx)
                st.rerun()
    else:
        st.info("No BOQ lines added yet.")

    if st.button("SAVE PROJECT", type="primary", width="stretch"):
        if client_pick == NEW_CLIENT_OPTION:
            st.error("Save the new client first (Quick add client), or select an existing client.")
        elif not project_name.strip():
            st.error("Project Name is required.")
        else:
            project_id = generate_id("PR", "projects")
            saved_project_name = project_name.strip()
            document_path = _save_upload(document_upload, "uploads/projects", project_id)
            conn = get_conn()
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
            _reset_project_draft_boq()
            st.success(
                f"Project saved. ID: {project_id}"
                + (f" · {boq_count} BOQ line(s)." if boq_count else "")
            )
            st.rerun()

    conn = get_conn()
    st.markdown("#### Saved Projects")
    st.dataframe(
        pd.read_sql_query(
            """
            SELECT project_id, project_name, client_name, work_order_no, amount AS total_work_amount,
                   country, region, district, site_incharge, budget, status
            FROM projects
            ORDER BY id DESC
            """,
            conn,
        ),
        width="stretch",
        hide_index=True,
    )
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
        "SELECT payroll_id, employee_id, payroll_month, base_salary, ot_amount, deductions, net_salary, salary_status FROM payroll ORDER BY id DESC",
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
    reports = [
        ("attendance_report.xlsx", attendance_df),
        ("salary_report.xlsx", payroll_df),
        ("expense_report.xlsx", expense_df),
        ("client_payment_report.xlsx", payment_df),
        ("finance_register.xlsx", finance_df),
        ("ot_report.xlsx", attendance_df[["attendance_date", "employee_id", "employee_name", "project_name", "ot_hours"]] if not attendance_df.empty else attendance_df),
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
    tabs = st.tabs(
        [
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
    )
    with tabs[0]:
        _settings_dashboard()
    with tabs[1]:
        _settings_users()
    with tabs[2]:
        _settings_lookup("countries", "country_name", "Country")
    with tabs[3]:
        _settings_regions()
    with tabs[4]:
        _settings_districts()
    with tabs[5]:
        _settings_holidays()
    with tabs[6]:
        _settings_weekly_offs()
    with tabs[7]:
        _settings_lookup("departments", "department_name", "Department")
    with tabs[8]:
        _settings_lookup("designations", "designation_name", "Designation")
    with tabs[9]:
        _settings_lookup("payment_heads", "head_name", "Payment Head")
    with tabs[10]:
        _settings_lookup("expense_heads", "head_name", "Expense Head")
    with tabs[11]:
        _settings_rule_table("salary_rules", "Salary Rule")
    with tabs[12]:
        _settings_rule_table("ot_rules", "OT Rule")
    with tabs[13]:
        _settings_managers()


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
    country, region, district = location_dropdowns("settings_manager_location", default_country="India")
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
                (new_manager.strip(), country, region, district, contact_number.strip()),
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


def _settings_users():
    st.markdown("### User Creation")
    st.caption("Create login users for Admin, MD, HR, Accountant, Project Manager, and Site Engineer.")

    with st.form("users_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        full_name = c1.text_input("Full Name")
        username = c2.text_input("Username")
        password = c3.text_input("Password", type="password")
        role = c1.selectbox(
            "Role",
            ["Admin", "MD", "HR", "Accountant", "Project Manager", "Site Engineer"],
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
