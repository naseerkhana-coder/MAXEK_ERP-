"""Worker Payroll — 8hr/10hr categories, attendance, salary cycles, approval, PDF slips."""

from __future__ import annotations

import calendar
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from modules.branding import ERP_LEGAL_NAME, ERP_VERSION
from modules.database import DATE_FMT, calculate_hours, next_worker_id, parse_flexible_time
from modules.pages import _save_upload
from modules.worker_payroll_db import (
    add_deduction,
    calculate_period,
    delete_deduction,
    delete_worker_attendance,
    ensure_worker_payroll_schema,
    get_payroll_run,
    get_worker,
    list_active_workers,
    list_all_workers,
    list_deductions,
    list_payroll_runs,
    load_worker_attendance,
    recalculate_run_net,
    save_payment,
    save_payroll_run,
    save_worker_attendance,
    save_worker_profile,
    salary_report_df,
    update_run_status,
)
from modules.worker_payroll_engine import (
    DEDUCTION_TYPES,
    PAYMENT_MODES,
    WORKFLOW_STATUSES,
    WORKFLOW_STEPS,
    calculate_daily_pay,
    hourly_rate,
    ot_hourly_rate,
    standard_hours_for_category,
    workflow_step_index,
)
from modules.worker_payroll_pdf import generate_worker_salary_slip_pdf

WORKER_CATEGORY_OPTIONS = ("8 Hr", "10 Hr")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _parse_date(d) -> str:
    if hasattr(d, "strftime"):
        return d.strftime(DATE_FMT)
    return str(d)


def _period_presets():
    today = datetime.now()
    y, m = today.year, today.month
    last_day = calendar.monthrange(y, m)[1]
    advance_end = datetime(y, m, min(15, last_day))
    advance_start = datetime(y, m, 1)
    final_start = datetime(y, m, 16 if last_day >= 16 else last_day)
    final_end = datetime(y, m, last_day)
    return {
        "Advance (1st – 15th)": (advance_start.date(), advance_end.date()),
        "Final (16th – month end)": (final_start.date(), final_end.date()),
        "Full month": (advance_start.date(), final_end.date()),
    }


def _render_workflow_steps(workflow_status: str | None = None):
    current = workflow_step_index(workflow_status or "Draft")
    parts = []
    for idx, label in enumerate(WORKFLOW_STEPS):
        if idx < current:
            parts.append(f"✓ {label}")
        elif idx == current:
            parts.append(f"**→ {label}**")
        else:
            parts.append(label)
    st.caption(" · ".join(parts))


def _render_workers_tab():
    st.markdown("#### Worker profiles")
    st.caption("Category A = 8 hours/day · Category B = 10 hours/day. OT rate defaults to Daily Wage ÷ standard hours.")

    edit_id = st.session_state.get("wp_edit_worker")

    if edit_id:
        w = get_worker(edit_id)
        if not w:
            st.session_state.pop("wp_edit_worker", None)
            st.rerun()
    else:
        w = {}

    c1, c2 = st.columns(2)
    with c1:
        subcontractor = st.text_input("Sub Contractor (for new ID)", value=w.get("subcontractor_name") or "")
        worker_id = w.get("worker_id") or (
            next_worker_id(subcontractor) if subcontractor else ""
        )
        if worker_id:
            st.caption(f"Worker ID: **{worker_id}**")
        worker_name = st.text_input("Name", value=w.get("worker_name") or "")
        hour_category = st.selectbox(
            "Category",
            WORKER_CATEGORY_OPTIONS,
            index=0 if (w.get("hour_category") or "8 Hr") in ("8 Hr", "Category A") else 1,
        )
    with c2:
        daily_wage = st.number_input("Daily Wage Rate (₹)", min_value=0.0, step=50.0, value=float(w.get("daily_wage_rate") or 0))
        std = standard_hours_for_category(hour_category)
        default_ot = hourly_rate(daily_wage, std) if daily_wage else float(w.get("ot_rate") or 0)
        ot_rate = st.number_input("OT Rate (₹/hr)", min_value=0.0, step=10.0, value=float(w.get("ot_rate") or default_ot))
        joining = st.text_input("Joining Date (DD/MM/YYYY)", value=w.get("joining_date") or "")
        status = st.selectbox("Status", ["Active", "Inactive"], index=0 if (w.get("status") or "Active") == "Active" else 1)

    if st.button("Save worker", type="primary"):
        if not worker_name.strip():
            st.error("Worker name is required.")
        elif not worker_id:
            st.error("Sub contractor name required to generate Worker ID.")
        else:
            save_worker_profile(
                worker_id,
                worker_name.strip(),
                hour_category,
                daily_wage,
                ot_rate,
                joining.strip(),
                status,
                subcontractor_name=subcontractor.strip(),
            )
            st.session_state.pop("wp_edit_worker", None)
            st.success(f"Worker {worker_id} saved.")
            st.rerun()

    if edit_id and st.button("Cancel edit"):
        st.session_state.pop("wp_edit_worker", None)
        st.rerun()

    st.divider()
    show_inactive = st.checkbox("Show inactive workers", key="wp_show_inactive")
    workers = list_all_workers(active_only=not show_inactive)
    if workers.empty:
        st.info("No workers yet. Save a profile above.")
        return
    display = workers.copy()
    display["OT Rate (calc)"] = display.apply(
        lambda r: ot_hourly_rate(float(r["daily_wage_rate"]), standard_hours_for_category(r["hour_category"]), float(r["ot_rate"])),
        axis=1,
    )
    st.dataframe(
        display[
            [
                "worker_id",
                "worker_name",
                "hour_category",
                "daily_wage_rate",
                "OT Rate (calc)",
                "joining_date",
                "status",
            ]
        ],
        width="stretch",
        hide_index=True,
    )
    pick = st.selectbox(
        "Edit worker",
        [""] + [f"{r.worker_id} — {r.worker_name}" for r in workers.itertuples()],
        key="wp_pick_edit",
    )
    if pick and st.button("Load for edit"):
        st.session_state["wp_edit_worker"] = pick.split(" — ")[0]
        st.rerun()


def _hours_from_times(worker: dict, in_time: str, out_time: str, break_hrs: float):
    std = standard_hours_for_category(worker.get("hour_category"))
    try:
        worked, _legacy_ot = calculate_hours(in_time, out_time, break_hrs, std, ot_allowed=True)
    except ValueError as exc:
        st.error(str(exc))
        return 0.0, 0.0
    pay = calculate_daily_pay(
        float(worker.get("daily_wage_rate") or 0),
        std,
        worked,
        float(worker.get("ot_rate") or 0) or None,
    )
    return worked, pay["ot_hours"]


def _render_attendance_tab():
    st.markdown("#### Daily attendance")
    workers = list_active_workers()
    if workers.empty:
        st.warning("Add workers in the Workers tab first.")
        return

    labels = {f"{r.worker_id} — {r.worker_name}": r.worker_id for r in workers.itertuples()}
    pick = st.selectbox("Worker", list(labels.keys()), key="wp_att_worker")
    worker_id = labels[pick]
    worker = get_worker(worker_id)

    edit_att = st.session_state.get("wp_edit_att")
    att_default = {}
    if edit_att:
        conn_rows = load_worker_attendance(worker_id, "01/01/2000", "31/12/2099")
        att_default = next((r for r in conn_rows if r["id"] == edit_att), {})

    std = standard_hours_for_category(worker.get("hour_category"))
    st.info(f"**{worker.get('hour_category')}** worker · Standard **{std:g}h**/day · Daily wage **₹{float(worker.get('daily_wage_rate') or 0):,.2f}**")

    c1, c2, c3, c4 = st.columns(4)
    att_date = c1.date_input("Date", value=datetime.now().date(), key="wp_att_date")
    in_time = c2.text_input("Check In", value=att_default.get("in_time") or att_default.get("start_time") or "", placeholder="08:00")
    out_time = c3.text_input("Check Out", value=att_default.get("out_time") or att_default.get("end_time") or "", placeholder="18:00")
    break_hrs = c4.number_input("Break (hrs)", min_value=0.0, step=0.5, value=0.0)

    worked, ot_h = _hours_from_times(worker, in_time, out_time, break_hrs)
    if in_time and out_time:
        pay = calculate_daily_pay(
            float(worker.get("daily_wage_rate") or 0),
            std,
            worked,
            float(worker.get("ot_rate") or 0) or None,
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Worked hours", f"{worked:g}")
        m2.metric("OT hours", f"{ot_h:g}")
        m3.metric("Day pay", f"₹{pay['gross_pay']:,.2f}")

    remarks = st.text_input("Remarks", value=att_default.get("remarks") or "")
    if st.button("Save attendance", type="primary"):
        if not in_time or not out_time:
            st.error("Check in and check out are required.")
        else:
            save_worker_attendance(
                worker_id,
                worker.get("worker_name") or "",
                _parse_date(att_date),
                parse_flexible_time(in_time, False) or in_time,
                parse_flexible_time(out_time, True) or out_time,
                worked,
                ot_h,
                remarks,
                record_id=int(edit_att) if edit_att else None,
            )
            st.session_state.pop("wp_edit_att", None)
            st.success("Attendance saved.")
            st.rerun()

    from_d = st.date_input("List from", value=datetime.now().replace(day=1).date(), key="wp_att_list_from")
    to_d = st.date_input("List to", value=datetime.now().date(), key="wp_att_list_to")
    rows = load_worker_attendance(worker_id, _parse_date(from_d), _parse_date(to_d))
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        ids = {f"{r['attendance_date']} ({r['total_hours']}h)": r["id"] for r in rows}
        sel = st.selectbox("Edit / delete entry", [""] + list(ids.keys()))
        if sel:
            rid = ids[sel]
            b1, b2 = st.columns(2)
            if b1.button("Edit selected"):
                st.session_state["wp_edit_att"] = rid
                st.rerun()
            if b2.button("Delete selected"):
                delete_worker_attendance(rid)
                st.success("Deleted.")
                st.rerun()
    else:
        st.caption("No attendance in this range.")


def _render_salary_tab():
    st.markdown("#### Salary period")
    _render_workflow_steps("Draft")
    workers = list_active_workers()
    if workers.empty:
        st.warning("Add workers first.")
        return

    labels = {f"{r.worker_id} — {r.worker_name}": r.worker_id for r in workers.itertuples()}
    pick = st.selectbox("Worker", list(labels.keys()), key="wp_sal_worker")
    worker_id = labels[pick]

    presets = _period_presets()
    preset = st.selectbox("Quick period", list(presets.keys()), key="wp_sal_preset")
    p_start, p_end = presets[preset]
    c1, c2 = st.columns(2)
    from_d = c1.date_input("From date", value=p_start, key="wp_sal_from")
    to_d = c2.date_input("To date", value=p_end, key="wp_sal_to")
    from_s, to_s = _parse_date(from_d), _parse_date(to_d)

    b1, b2 = st.columns(2)
    view = b1.button("View Salary", type="primary", width="stretch")
    generate = b2.button("Generate Salary", width="stretch")

    if view or generate:
        summary = calculate_period(worker_id, from_s, to_s)
        if not summary:
            st.error("Could not calculate.")
            return

        st.session_state["wp_last_summary"] = summary
        run_id = summary.get("run_id")
        deductions = list_deductions(run_id) if run_id else []
        total_ded = sum(float(d.get("amount") or 0) for d in deductions)
        gross = float(summary.get("gross_salary") or 0)
        ot_amt = float(summary.get("ot_amount") or 0)
        base_gross = round(gross - ot_amt, 2)
        net = max(0.0, gross - total_ded)

        st.markdown("##### Earnings")
        e1, e2, e3, e4, e5 = st.columns(5)
        e1.metric("Worked days", summary.get("worked_days"))
        e2.metric("Worked hours", f"{summary.get('worked_hours', 0):g}")
        e3.metric("OT hours", f"{summary.get('ot_hours', 0):g}")
        e4.metric("Base gross", f"₹{base_gross:,.2f}")
        e5.metric("Gross + OT", f"₹{gross:,.2f}")

        if summary.get("day_lines"):
            st.dataframe(pd.DataFrame(summary["day_lines"]), width="stretch", hide_index=True)

        if generate:
            status = "Calculated"
            rid = save_payroll_run(summary, total_ded, status)
            summary["run_id"] = rid
            run_id = rid
            st.session_state["wp_active_run"] = rid
            st.success(f"Salary generated — Run ID **{rid}** · Status **{status}**")
            st.rerun()

        if run_id:
            st.markdown("##### Deductions")
            deductions = list_deductions(run_id)
            if deductions:
                st.dataframe(
                    pd.DataFrame(deductions)[
                        ["deduction_type", "deduction_date", "amount", "remarks", "deduction_id"]
                    ],
                    width="stretch",
                    hide_index=True,
                )
                del_labels = {
                    f"{d['deduction_type']} · {d['deduction_date']} · ₹{float(d['amount']):,.0f}": d["deduction_id"]
                    for d in deductions
                }
                del_pick = st.selectbox("Remove deduction", [""] + list(del_labels.keys()), key="wp_del_ded")
                if del_pick and st.button("Delete deduction", key="wp_del_ded_btn"):
                    delete_deduction(del_labels[del_pick])
                    st.success("Deduction removed.")
                    st.rerun()
            with st.form("wp_add_ded", clear_on_submit=True):
                d1, d2, d3 = st.columns(3)
                dtype = d1.selectbox("Type", DEDUCTION_TYPES)
                ddate = d2.date_input("Date")
                damt = d3.number_input("Amount", min_value=0.0, step=50.0)
                drem = st.text_input("Remarks")
                if st.form_submit_button("Add deduction"):
                    add_deduction(run_id, worker_id, dtype, _parse_date(ddate), damt, drem)
                    st.rerun()
            total_ded = sum(float(d.get("amount") or 0) for d in list_deductions(run_id))
            net = recalculate_run_net(run_id)
            if st.button("Recalculate net", key="wp_recalc_net"):
                st.rerun()
        else:
            st.caption("Click **Generate Salary** to save this period and add deductions.")

        st.markdown(f"### Net payable: **₹{net:,.2f}**")
        st.caption(f"Gross ₹{gross:,.2f} (base ₹{base_gross:,.2f} + OT ₹{ot_amt:,.2f}) − deductions ₹{total_ded:,.2f}")

        if summary.get("workflow_status"):
            _render_workflow_steps(summary.get("workflow_status"))
            st.caption(f"Saved status: **{summary.get('workflow_status')}** · Run **{run_id or '—'}**")


def _render_review_tab():
    st.markdown("#### Salary review & approval")
    _render_workflow_steps("Calculated")

    pending = list_payroll_runs(status=None)
    if pending.empty:
        st.info("No payroll runs yet.")
        return

    options = {
        f"{r.worker_name} | {r.period_start}–{r.period_end} | {r.workflow_status} | ₹{r.net_salary:,.0f}": r.run_id
        for r in pending.itertuples()
    }
    pick = st.selectbox("Select payroll run", list(options.keys()), key="wp_review_pick")
    run_id = options[pick]
    run = get_payroll_run(run_id)
    _render_workflow_steps(run.get("workflow_status"))
    st.dataframe(pd.DataFrame([run]), width="stretch", hide_index=True)

    deductions = list_deductions(run_id)
    if deductions:
        st.dataframe(pd.DataFrame(deductions), width="stretch", hide_index=True)

    status = run.get("workflow_status") or "Draft"
    c1, c2, c3 = st.columns(3)
    if status in ("Draft", "Calculated") and c1.button("Mark Calculated", width="stretch"):
        update_run_status(run_id, "Calculated")
        st.rerun()
    if status in ("Draft", "Calculated") and c2.button("Approve", type="primary", width="stretch"):
        update_run_status(run_id, "Approved")
        st.success("Approved.")
        st.rerun()
    if status == "Approved":
        st.info("Approved — complete payment in the Payment tab.")


def _render_payment_tab():
    st.markdown("#### Payment entry")
    _render_workflow_steps("Approved")

    approved = list_payroll_runs(status="Approved")
    if approved.empty:
        st.info("No approved payroll awaiting payment.")
        return

    options = {
        f"{r.worker_name} | ₹{r.net_salary:,.0f}": r.run_id for r in approved.itertuples()
    }
    pick = st.selectbox("Approved payroll", list(options.keys()), key="wp_pay_pick")
    run_id = options[pick]
    run = get_payroll_run(run_id)

    st.metric("Net payable", f"₹{float(run.get('net_salary') or 0):,.2f}")

    pay_date = st.date_input("Payment date", value=datetime.now().date())
    pay_mode = st.selectbox("Payment mode", PAYMENT_MODES)
    reference = st.text_input("Reference number")
    remarks = st.text_area("Remarks")

    st.markdown("**Attachments** (saved under `uploads/worker_payroll/`)")
    receipt = st.file_uploader("Payment receipt / attachment", key="wp_receipt")
    bank = st.file_uploader("Bank transfer proof", key="wp_bank")
    sheet = st.file_uploader("Signed salary sheet", key="wp_sheet")

    if st.button("Complete payment", type="primary"):
        rp = _save_upload(receipt, "uploads/worker_payroll", f"{run_id}_receipt") if receipt else ""
        bp = _save_upload(bank, "uploads/worker_payroll", f"{run_id}_bank") if bank else ""
        sp = _save_upload(sheet, "uploads/worker_payroll", f"{run_id}_sheet") if sheet else ""
        save_payment(run_id, _parse_date(pay_date), pay_mode, reference, remarks, rp, bp, sp)
        st.success("Payment recorded. Status: **Paid**")
        st.rerun()


def _render_reports_tab():
    st.markdown("#### Worker salary report")
    c1, c2 = st.columns(2)
    from_d = c1.date_input("From", value=datetime.now().replace(day=1).date(), key="wp_rpt_from")
    to_d = c2.date_input("To", value=datetime.now().date(), key="wp_rpt_to")
    df = salary_report_df(_parse_date(from_d), _parse_date(to_d))
    if df.empty:
        st.info("No payroll data in range.")
    else:
        st.dataframe(df, width="stretch", hide_index=True)
        st.download_button(
            "Export CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=f"worker_salary_report_{_parse_date(from_d).replace('/', '-')}.csv",
            mime="text/csv",
            key="wp_rpt_csv",
        )


def _render_payslip_tab():
    st.markdown("#### Salary slip (PDF)")
    runs = list_payroll_runs()
    if runs.empty:
        st.info("Generate payroll first.")
        return
    options = {
        f"{r.worker_name} | {r.period_start}–{r.period_end} | {r.workflow_status}": r.run_id
        for r in runs.itertuples()
    }
    pick = st.selectbox("Payroll run", list(options.keys()), key="wp_slip_pick")
    run_id = options[pick]
    if st.button("Download PDF salary slip", type="primary"):
        try:
            pdf_bytes = generate_worker_salary_slip_pdf(run_id)
            st.download_button(
                "Download PDF",
                data=pdf_bytes,
                file_name=f"salary_slip_{run_id}.pdf",
                mime="application/pdf",
                width="stretch",
            )
        except Exception as exc:
            st.error(str(exc))


def page_worker_payroll():
    ensure_worker_payroll_schema()
    st.subheader("Worker Payroll")
    st.caption(
        f"{ERP_LEGAL_NAME} · 8hr & 10hr workers · Actual hours salary · "
        "Advance (1–15) & Final (16–end) cycles"
    )

    tabs = st.tabs(
        [
            "Process Payroll",
            "Workers",
            "Attendance",
            "Salary",
            "Review",
            "Payment",
            "Reports",
            "Salary Slip",
        ]
    )
    with tabs[0]:
        from modules.pages import page_payroll

        page_payroll()
    with tabs[1]:
        _render_workers_tab()
    with tabs[2]:
        _render_attendance_tab()
    with tabs[3]:
        _render_salary_tab()
    with tabs[4]:
        _render_review_tab()
    with tabs[5]:
        _render_payment_tab()
    with tabs[6]:
        _render_reports_tab()
    with tabs[7]:
        _render_payslip_tab()
