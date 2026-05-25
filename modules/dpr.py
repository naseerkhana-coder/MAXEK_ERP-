"""Daily Progress Report (DPR) module for MAXEK ERP."""

from datetime import datetime

import pandas as pd
import streamlit as st

from modules.database import (
    DATE_FMT,
    generate_id,
    get_boq_progress_stats,
    get_conn,
    load_company_staff_for_select,
    load_project_boq_by_project,
    load_project_names,
)
from modules.pages import _save_upload

MEASUREMENT_TYPES = [
    "Concrete",
    "Shuttering",
    "Brick Work",
    "Straight Bar",
    "Ring",
    "Bent Bar",
]
DPR_STATUS_DRAFT = "Draft"
DPR_STATUS_SUBMITTED = "Submitted"
DPR_STATUS_ENGINEER_APPROVED = "Engineer Approved"
DPR_STATUS_CLIENT_APPROVED = "Client Approved"
DPR_STATUS_BILLED = "Billed"
DPR_STATUS_REJECTED = "Rejected"


def _avg_dim(value_1, value_2):
    values = [float(v) for v in (value_1, value_2) if v is not None and float(v) > 0]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _steel_weight_ton(nos, length_m, dia_mm, multiplier=1.0):
    if nos <= 0 or length_m <= 0 or dia_mm <= 0:
        return 0.0
    kg = (float(dia_mm) ** 2 * float(length_m) * float(nos) * float(multiplier)) / 162.0
    return kg / 1000.0


def calculate_measurement_quantity(measurement_type, fields):
    w1 = fields.get("width_1", 0.0)
    w2 = fields.get("width_2", 0.0)
    l1 = fields.get("length_1", 0.0)
    l2 = fields.get("length_2", 0.0)
    height = fields.get("height", 0.0)
    depth = fields.get("depth", 0.0)
    nos = fields.get("nos", 0.0)
    dia_mm = fields.get("dia_mm", 0.0)
    bend = fields.get("bend", 1.0) or 1.0

    avg_w = _avg_dim(w1, w2)
    avg_l = _avg_dim(l1, l2)

    if measurement_type == "Concrete":
        h = depth if depth > 0 else height
        qty = avg_w * avg_l * h
        unit = "M3"
    elif measurement_type == "Brick Work":
        h = depth if depth > 0 else height
        qty = avg_w * avg_l * h
        unit = "M3"
    elif measurement_type == "Shuttering":
        qty = avg_l * height
        unit = "SQM"
    elif measurement_type == "Straight Bar":
        length_m = avg_l if avg_l > 0 else l1
        qty = _steel_weight_ton(nos, length_m, dia_mm)
        unit = "Ton"
        avg_w, avg_l = 0.0, length_m
    elif measurement_type == "Ring":
        w = avg_w if avg_w > 0 else w1
        l = avg_l if avg_l > 0 else l1
        qty = _steel_weight_ton(nos, w * l, dia_mm)
        unit = "Ton"
    elif measurement_type == "Bent Bar":
        l1v = l1 or avg_l
        l2v = l2 or depth or height
        qty = _steel_weight_ton(nos, l1v, dia_mm, multiplier=bend)
        unit = "Ton"
        avg_l = l1v
    else:
        qty = 0.0
        unit = ""

    return {
        "avg_width": avg_w,
        "avg_length": avg_l,
        "calculated_quantity": round(qty, 4),
        "unit": unit,
    }


def _ensure_dpr_drafts():
    st.session_state.setdefault("dpr_draft_measurements", [])
    st.session_state.setdefault("dpr_draft_manpower", [])


def _reset_dpr_drafts():
    st.session_state.dpr_draft_measurements = []
    st.session_state.dpr_draft_manpower = []


def _timestamp():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _staff_options():
    df = load_company_staff_for_select()
    if df.empty:
        return [""], {}
    labels = []
    mapping = {}
    for _, row in df.iterrows():
        label = f"{row['employee_id']} - {row['employee_name']}"
        labels.append(label)
        mapping[label] = (row["employee_id"], row["employee_name"])
    return [""] + labels, mapping


def _insert_dpr_records(
    conn,
    dpr_row,
    measurements,
    manpower_rows,
):
    conn.execute(
        """
        INSERT INTO dpr_reports(
            dpr_id, dpr_date, project_name, project_id, client_name, site_incharge_id, site_incharge_name,
            boq_item_id, boq_number, boq_description, unit, billing_measurement,
            total_boq_quantity, done_quantity, billed_quantity, balance_quantity,
            pending_billing_quantity, progress_quantity, remarks, document_upload, site_photo,
            weather, equipment_usage, delay_reason, engineer_approval, client_approval,
            status, created_by, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            dpr_row["dpr_id"],
            dpr_row["dpr_date"],
            dpr_row["project_name"],
            dpr_row.get("project_id", ""),
            dpr_row.get("client_name", ""),
            dpr_row["site_incharge_id"],
            dpr_row["site_incharge_name"],
            dpr_row["boq_item_id"],
            dpr_row["boq_number"],
            dpr_row["boq_description"],
            dpr_row["unit"],
            dpr_row["billing_measurement"],
            dpr_row["total_boq_quantity"],
            dpr_row["done_quantity"],
            dpr_row["billed_quantity"],
            dpr_row["balance_quantity"],
            dpr_row["pending_billing_quantity"],
            dpr_row["progress_quantity"],
            dpr_row["remarks"],
            dpr_row.get("document_upload", ""),
            dpr_row.get("site_photo", ""),
            dpr_row.get("weather", ""),
            dpr_row.get("equipment_usage", ""),
            dpr_row.get("delay_reason", ""),
            "Pending",
            "Pending",
            dpr_row["status"],
            dpr_row["created_by"],
            dpr_row["created_at"],
        ),
    )
    for row in measurements:
        measurement_id = generate_id("DPM", "dpr_measurements")
        conn.execute(
            """
            INSERT INTO dpr_measurements(
                measurement_id, dpr_id, measurement_type, width_1, width_2, length_1, length_2,
                height, depth, nos, dia_mm, bend, avg_width, avg_length, calculated_quantity, unit
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                measurement_id,
                dpr_row["dpr_id"],
                row["measurement_type"],
                row.get("width_1", 0),
                row.get("width_2", 0),
                row.get("length_1", 0),
                row.get("length_2", 0),
                row.get("height", 0),
                row.get("depth", 0),
                row.get("nos", 0),
                row.get("dia_mm", 0),
                row.get("bend", 0),
                row.get("avg_width", 0),
                row.get("avg_length", 0),
                row["calculated_quantity"],
                row.get("unit", ""),
            ),
        )
    for row in manpower_rows:
        manpower_id = generate_id("DPL", "dpr_manpower")
        conn.execute(
            """
            INSERT INTO dpr_manpower(manpower_id, dpr_id, labour_type, nos, working_hours, remarks)
            VALUES(?,?,?,?,?,?)
            """,
            (
                manpower_id,
                dpr_row["dpr_id"],
                row["labour_type"],
                int(row["nos"]),
                row["working_hours"],
                row.get("remarks", ""),
            ),
        )


def _render_measurement_fields(measurement_type):
    c1, c2, c3, c4 = st.columns(4)
    fields = {"measurement_type": measurement_type}
    if measurement_type in {"Concrete", "Brick Work"}:
        fields["length_1"] = c1.number_input("Length 1 (m)", min_value=0.0, step=0.01, key="dpr_m_len1")
        fields["length_2"] = c2.number_input("Length 2 (m)", min_value=0.0, step=0.01, key="dpr_m_len2")
        fields["width_1"] = c3.number_input("Width 1 (m)", min_value=0.0, step=0.01, key="dpr_m_w1")
        fields["width_2"] = c4.number_input("Width 2 (m)", min_value=0.0, step=0.01, key="dpr_m_w2")
        fields["depth"] = st.number_input("Depth / Height (m)", min_value=0.0, step=0.01, key="dpr_m_depth")
    elif measurement_type == "Shuttering":
        fields["length_1"] = c1.number_input("Length 1 (m)", min_value=0.0, step=0.01, key="dpr_m_len1")
        fields["length_2"] = c2.number_input("Length 2 (m)", min_value=0.0, step=0.01, key="dpr_m_len2")
        fields["height"] = c3.number_input("Height (m)", min_value=0.0, step=0.01, key="dpr_m_height")
        fields["width_1"] = 0.0
        fields["width_2"] = 0.0
    elif measurement_type == "Straight Bar":
        fields["nos"] = c1.number_input("Nos", min_value=0.0, step=1.0, key="dpr_m_nos")
        fields["length_1"] = c2.number_input("Length (m)", min_value=0.0, step=0.01, key="dpr_m_len1")
        fields["dia_mm"] = c3.number_input("Dia (mm)", min_value=0.0, step=1.0, key="dpr_m_dia")
    elif measurement_type == "Ring":
        fields["nos"] = c1.number_input("Nos", min_value=0.0, step=1.0, key="dpr_m_nos")
        fields["width_1"] = c2.number_input("Width (m)", min_value=0.0, step=0.01, key="dpr_m_w1")
        fields["length_1"] = c3.number_input("Length (m)", min_value=0.0, step=0.01, key="dpr_m_len1")
        fields["dia_mm"] = c4.number_input("Dia (mm)", min_value=0.0, step=1.0, key="dpr_m_dia")
    elif measurement_type == "Bent Bar":
        fields["nos"] = c1.number_input("Nos", min_value=0.0, step=1.0, key="dpr_m_nos")
        fields["length_1"] = c2.number_input("Length 1 (m)", min_value=0.0, step=0.01, key="dpr_m_len1")
        fields["length_2"] = c3.number_input("Length 2 (m)", min_value=0.0, step=0.01, key="dpr_m_len2")
        fields["bend"] = c4.number_input("Bend Factor", min_value=0.0, step=0.1, value=1.0, key="dpr_m_bend")
        fields["dia_mm"] = st.number_input("Dia (mm)", min_value=0.0, step=1.0, key="dpr_m_dia")
    return fields


def _render_new_dpr_tab():
    _ensure_dpr_drafts()
    st.markdown("### DPR Main Entry")
    projects = [""] + load_project_names()
    staff_labels, staff_map = _staff_options()

    m1, m2, m3 = st.columns(3)
    dpr_date = m1.date_input("Date", key="dpr_date")
    project_name = m2.selectbox("Project Name", projects, key="dpr_project")
    site_pick = m3.selectbox("Site Incharge", staff_labels, key="dpr_site_incharge")

    boq_df = load_project_boq_by_project(project_name) if project_name else pd.DataFrame()
    boq_options = [""]
    boq_lookup = {}
    if not boq_df.empty:
        for _, row in boq_df.iterrows():
            label = f"{row['boq_number']} | {row['description'][:40]}"
            boq_options.append(label)
            boq_lookup[label] = row

    b1, b2, b3 = st.columns(3)
    boq_pick = b1.selectbox("BOQ Number", boq_options, key="dpr_boq_pick")
    billing_measurement = b2.selectbox("Billing Measurement", ["No", "Yes"], key="dpr_billing")
    auto_dpr_no = generate_id("DPR", "dpr_reports")
    b3.text_input("DPR No (preview)", value=auto_dpr_no, disabled=True, key="dpr_no_preview")

    boq_desc = ""
    unit = ""
    stats = {
        "total_qty": 0.0,
        "done_qty": 0.0,
        "billed_qty": 0.0,
        "balance_qty": 0.0,
        "pending_billing_qty": 0.0,
    }
    boq_item_id = ""
    boq_number = ""
    project_id = ""
    if boq_pick and boq_pick in boq_lookup:
        row = boq_lookup[boq_pick]
        boq_item_id = row["boq_item_id"]
        boq_number = row["boq_number"]
        boq_desc = row["description"]
        unit = row["unit"]
        project_id = row.get("project_id", "")
        stats = get_boq_progress_stats(boq_item_id)

    d1, d2 = st.columns(2)
    d1.text_input("BOQ Description", value=boq_desc, disabled=True, key="dpr_boq_desc_display")
    d2.text_input("Unit", value=unit, disabled=True, key="dpr_unit_display")

    q1, q2, q3, q4, q5 = st.columns(5)
    q1.metric("BOQ Qty", f"{stats['total_qty']:,.2f}")
    q2.metric("Done Qty", f"{stats['done_qty']:,.2f}")
    q3.metric("Billed Qty", f"{stats['billed_qty']:,.2f}")
    q4.metric("Balance Qty", f"{stats['balance_qty']:,.2f}")
    q5.metric("Pending Billing", f"{stats['pending_billing_qty']:,.2f}")

    remarks = st.text_area("Remarks", key="dpr_remarks")
    e1, e2, e3 = st.columns(3)
    weather = e1.text_input("Weather", key="dpr_weather")
    equipment_usage = e2.text_input("Equipment Usage", key="dpr_equipment")
    delay_reason = e3.text_input("Delay Reason", key="dpr_delay")
    doc_upload = st.file_uploader("Shape / Sketch / Document Upload", key="dpr_doc")
    site_photo = st.file_uploader("Daily Site Photo", type=["jpg", "jpeg", "png"], key="dpr_photo")

    st.markdown("### Measurement Entry")
    st.caption("Supports Width 1/2 and Length 1/2 with auto average. Quantity is calculated by measurement type.")
    mt = st.selectbox("Measurement Type", MEASUREMENT_TYPES, key="dpr_measurement_type")
    fields = _render_measurement_fields(mt)
    calc = calculate_measurement_quantity(mt, fields)
    st.info(
        f"Calculated: {calc['calculated_quantity']:,.4f} {calc['unit']} "
        f"(Avg W: {calc['avg_width']:.3f}, Avg L: {calc['avg_length']:.3f})"
    )
    if st.button("ADD MEASUREMENT LINE", key="dpr_add_measurement"):
        if calc["calculated_quantity"] <= 0:
            st.error("Calculated quantity must be greater than zero.")
        else:
            entry = {**fields, **calc}
            st.session_state.dpr_draft_measurements.append(entry)
            st.success("Measurement line added.")
            st.rerun()

    if st.session_state.dpr_draft_measurements:
        st.dataframe(pd.DataFrame(st.session_state.dpr_draft_measurements), width="stretch", hide_index=True)
        for idx in range(len(st.session_state.dpr_draft_measurements)):
            if st.button(f"Remove measurement #{idx + 1}", key=f"dpr_rm_m_{idx}"):
                st.session_state.dpr_draft_measurements.pop(idx)
                st.rerun()

    st.markdown("### Manpower Entry")
    mp1, mp2, mp3, mp4 = st.columns(4)
    labour_type = mp1.text_input("Labour Type", key="dpr_labour_type", placeholder="Mason")
    labour_nos = mp2.number_input("Nos", min_value=0, step=1, key="dpr_labour_nos")
    working_hours = mp3.selectbox("Working Hours", ["8 Hours", "10 Hours", "12 Hours", "Custom"], key="dpr_hours")
    labour_remarks = mp4.text_input("Manpower Remarks", key="dpr_labour_remarks")
    if st.button("ADD MANPOWER LINE", key="dpr_add_manpower"):
        if not labour_type.strip():
            st.error("Labour type is required.")
        elif labour_nos <= 0:
            st.error("Nos must be greater than zero.")
        else:
            st.session_state.dpr_draft_manpower.append(
                {
                    "labour_type": labour_type.strip(),
                    "nos": labour_nos,
                    "working_hours": working_hours,
                    "remarks": labour_remarks,
                }
            )
            st.rerun()
    if st.session_state.dpr_draft_manpower:
        st.dataframe(pd.DataFrame(st.session_state.dpr_draft_manpower), width="stretch", hide_index=True)

    c_save, c_submit = st.columns(2)
    if c_save.button("SAVE DRAFT", width="stretch"):
        _save_dpr(
            dpr_date,
            project_name,
            project_id,
            site_pick,
            staff_map,
            boq_item_id,
            boq_number,
            boq_desc,
            unit,
            billing_measurement,
            stats,
            remarks,
            weather,
            equipment_usage,
            delay_reason,
            doc_upload,
            site_photo,
            DPR_STATUS_DRAFT,
        )
    if c_submit.button("SUBMIT DPR", type="primary", width="stretch"):
        _save_dpr(
            dpr_date,
            project_name,
            project_id,
            site_pick,
            staff_map,
            boq_item_id,
            boq_number,
            boq_desc,
            unit,
            billing_measurement,
            stats,
            remarks,
            weather,
            equipment_usage,
            delay_reason,
            doc_upload,
            site_photo,
            DPR_STATUS_SUBMITTED,
        )


def _save_dpr(
    dpr_date,
    project_name,
    project_id,
    site_pick,
    staff_map,
    boq_item_id,
    boq_number,
    boq_desc,
    unit,
    billing_measurement,
    stats,
    remarks,
    weather,
    equipment_usage,
    delay_reason,
    doc_upload,
    site_photo,
    status,
):
    if not project_name:
        st.error("Project Name is required.")
        return
    if not site_pick or site_pick not in staff_map:
        st.error("Site Incharge (staff) is required.")
        return
    if not boq_item_id:
        st.error("BOQ Number is required.")
        return
    if not st.session_state.dpr_draft_measurements:
        st.error("Add at least one measurement line.")
        return

    progress_qty = sum(float(m["calculated_quantity"]) for m in st.session_state.dpr_draft_measurements)
    staff_id, staff_name = staff_map[site_pick]
    dpr_id = generate_id("DPR", "dpr_reports")
    doc_path = _save_upload(doc_upload, "uploads/dpr", f"{dpr_id}_doc")
    photo_path = _save_upload(site_photo, "uploads/dpr", f"{dpr_id}_photo")

    updated_stats = get_boq_progress_stats(boq_item_id)
    done_after = float(updated_stats["done_qty"]) + progress_qty
    balance_after = max(float(stats["total_qty"]) - done_after, 0.0)

    client_name = ""
    conn_lookup = get_conn()
    client_row = conn_lookup.execute(
        "SELECT client_name FROM projects WHERE project_name = ? LIMIT 1",
        (project_name,),
    ).fetchone()
    conn_lookup.close()
    if client_row:
        client_name = client_row[0] or ""

    dpr_row = {
        "dpr_id": dpr_id,
        "dpr_date": dpr_date.strftime(DATE_FMT),
        "project_name": project_name,
        "project_id": project_id or "",
        "client_name": client_name,
        "site_incharge_id": staff_id,
        "site_incharge_name": staff_name,
        "boq_item_id": boq_item_id,
        "boq_number": boq_number,
        "boq_description": boq_desc,
        "unit": unit or updated_stats.get("unit", ""),
        "billing_measurement": billing_measurement,
        "total_boq_quantity": stats["total_qty"],
        "done_quantity": done_after,
        "billed_quantity": stats["billed_qty"],
        "balance_quantity": balance_after,
        "pending_billing_quantity": stats["pending_billing_qty"],
        "progress_quantity": progress_qty,
        "remarks": remarks,
        "document_upload": doc_path,
        "site_photo": photo_path,
        "weather": weather,
        "equipment_usage": equipment_usage,
        "delay_reason": delay_reason,
        "status": status,
        "created_by": st.session_state.get("user_name", "User"),
        "created_at": _timestamp(),
    }
    conn = get_conn()
    _insert_dpr_records(conn, dpr_row, st.session_state.dpr_draft_measurements, st.session_state.dpr_draft_manpower)
    conn.commit()
    conn.close()
    _reset_dpr_drafts()
    st.success(f"DPR saved. ID: {dpr_id} · Status: {status}")
    st.rerun()


def _render_approvals_tab(role):
    conn = get_conn()
    st.markdown("### Engineer & Client Approval")
    submitted = pd.read_sql_query(
        """
        SELECT dpr_id, dpr_date, project_name, boq_number, progress_quantity, unit, billing_measurement, status
        FROM dpr_reports WHERE status = ?
        ORDER BY id DESC
        """,
        conn,
        params=(DPR_STATUS_SUBMITTED,),
    )
    engineer_pending = pd.read_sql_query(
        """
        SELECT dpr_id, dpr_date, project_name, boq_number, progress_quantity, unit, billing_measurement, status
        FROM dpr_reports WHERE status = ?
        ORDER BY id DESC
        """,
        conn,
        params=(DPR_STATUS_ENGINEER_APPROVED,),
    )
    conn.close()

    user = st.session_state.get("user_name", "User")

    if not submitted.empty:
        st.markdown("#### Pending Engineer Approval")
        st.dataframe(submitted, width="stretch", hide_index=True)
        if role in {"Admin", "Project Manager"}:
            pick = st.selectbox("Select DPR", [""] + submitted["dpr_id"].tolist(), key="dpr_eng_pick")
            if pick and st.button("ENGINEER APPROVE", type="primary", key="dpr_eng_approve"):
                conn = get_conn()
                conn.execute(
                    """
                    UPDATE dpr_reports
                    SET status = ?, engineer_approval = 'Approved', engineer_approved_by = ?, engineer_approved_at = ?
                    WHERE dpr_id = ?
                    """,
                    (DPR_STATUS_ENGINEER_APPROVED, user, _timestamp(), pick),
                )
                conn.commit()
                conn.close()
                st.rerun()

    if not engineer_pending.empty:
        st.markdown("#### Pending Client Approval")
        st.dataframe(engineer_pending, width="stretch", hide_index=True)
        if role in {"Admin", "MD"}:
            pick = st.selectbox("Select DPR for client approval", [""] + engineer_pending["dpr_id"].tolist(), key="dpr_cli_pick")
            if pick and st.button("CLIENT APPROVE", type="primary", key="dpr_cli_approve"):
                conn = get_conn()
                conn.execute(
                    """
                    UPDATE dpr_reports
                    SET status = ?, client_approval = 'Approved', client_approved_by = ?, client_approved_at = ?
                    WHERE dpr_id = ?
                    """,
                    (DPR_STATUS_CLIENT_APPROVED, user, _timestamp(), pick),
                )
                conn.commit()
                conn.close()
                st.rerun()


def _render_billing_tab():
    st.markdown("### Pending Client Billing")
    st.caption(
        "Step 1: Mark measured qty here. Step 2: Create client invoice in **Billing → Client Bill** "
        "(amount = qty × BOQ rate, print/PDF)."
    )
    conn = get_conn()
    pending_df = pd.read_sql_query(
        """
        SELECT dpr_id, dpr_date, project_name, boq_number, boq_description, progress_quantity,
               billed_quantity, unit, status
        FROM dpr_reports
        WHERE UPPER(COALESCE(billing_measurement, '')) = 'YES'
          AND status IN (?, ?)
          AND COALESCE(progress_quantity, 0) > COALESCE(billed_quantity, 0)
        ORDER BY id DESC
        """,
        conn,
        params=(DPR_STATUS_ENGINEER_APPROVED, DPR_STATUS_CLIENT_APPROVED),
    )
    conn.close()
    if pending_df.empty:
        st.info("No pending billing measurements.")
        return
    st.dataframe(pending_df, width="stretch", hide_index=True)
    pick = st.selectbox("Select DPR to bill", [""] + pending_df["dpr_id"].tolist(), key="dpr_bill_pick")
    if not pick:
        return
    row = pending_df[pending_df["dpr_id"] == pick].iloc[0]
    max_bill = float(row["progress_quantity"]) - float(row["billed_quantity"])
    bill_qty = st.number_input("Bill Quantity (partial allowed)", min_value=0.0, max_value=max_bill, value=max_bill, step=0.01)
    if st.button("MARK BILLED", type="primary", key="dpr_mark_billed"):
        new_billed = float(row["billed_quantity"]) + bill_qty
        new_status = DPR_STATUS_BILLED if new_billed >= float(row["progress_quantity"]) else row["status"]
        conn = get_conn()
        conn.execute(
            """
            UPDATE dpr_reports
            SET billed_quantity = ?, status = ?
            WHERE dpr_id = ?
            """,
            (new_billed, new_status, pick),
        )
        conn.execute(
            """
            UPDATE dpr_measurements SET billed = 1, billed_quantity = calculated_quantity
            WHERE dpr_id = ?
            """,
            (pick,),
        )
        conn.commit()
        conn.close()
        st.success(f"Billed {bill_qty:,.4f} for {pick}")
        st.rerun()


def _render_history_tab():
    st.markdown("### DPR Register & Measurement History")
    conn = get_conn()
    dpr_df = pd.read_sql_query(
        """
        SELECT dpr_id, dpr_date, project_name, site_incharge_name, boq_number, boq_description,
               progress_quantity, unit, billing_measurement, balance_quantity, status,
               engineer_approval, client_approval, weather
        FROM dpr_reports
        ORDER BY id DESC
        LIMIT 300
        """,
        conn,
    )
    meas_df = pd.read_sql_query(
        """
        SELECT m.dpr_id, d.dpr_date, d.project_name, m.measurement_type, m.avg_width, m.avg_length,
               m.calculated_quantity, m.unit, m.billed
        FROM dpr_measurements m
        JOIN dpr_reports d ON d.dpr_id = m.dpr_id
        ORDER BY m.id DESC
        LIMIT 500
        """,
        conn,
    )
    mp_df = pd.read_sql_query(
        """
        SELECT d.dpr_id, d.dpr_date, d.project_name, m.labour_type, m.nos, m.working_hours, m.remarks
        FROM dpr_manpower m
        JOIN dpr_reports d ON d.dpr_id = m.dpr_id
        ORDER BY m.id DESC
        LIMIT 500
        """,
        conn,
    )
    conn.close()
    st.dataframe(dpr_df, width="stretch", hide_index=True)
    st.markdown("#### Measurement History")
    st.dataframe(meas_df, width="stretch", hide_index=True)
    st.markdown("#### Manpower History")
    st.dataframe(mp_df, width="stretch", hide_index=True)


def page_dpr():
    st.subheader("Daily Progress Report (DPR)")
    role = st.session_state.get("user_role", "Admin")
    tabs = st.tabs(["New DPR", "Approvals", "Pending Billing", "Register & History"])
    with tabs[0]:
        _render_new_dpr_tab()
    with tabs[1]:
        _render_approvals_tab(role)
    with tabs[2]:
        if role in {"Admin", "Accountant", "MD"}:
            _render_billing_tab()
        else:
            st.info("Billing is handled by Accounts / MD.")
    with tabs[3]:
        _render_history_tab()
