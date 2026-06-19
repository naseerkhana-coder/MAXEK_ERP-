"""MAXEK ERP – Payroll calculation and generation service."""

from __future__ import annotations

import json
from calendar import monthrange
from datetime import datetime, timedelta


EMPLOYEE_TYPES = ("staff", "company_worker", "subcontractor")
PAYROLL_EMPLOYMENT_CATEGORIES = ("company_staff", "subcontractor")

PAYROLL_RUN_STATUSES = (
    "Draft",
    "Pending Verification",
    "Pending Checker",
    "Pending Approval",
    "Approved",  # ready for payment
    "Paid",
)


def calculate_daily_wage(
    daily_wage: float,
    worked_hours: float,
    ot_rate_per_hour: float = 0.0,
    ot_applicable: bool = False,
    standard_hours: float = 8.0,
) -> dict:
    """
    FRS daily wage rules:
    - <8 hrs: (daily_wage/8) * worked_hours
    - =8 hrs: full daily wage
    - >8 hrs: daily_wage + (extra_hours * ot_rate)
    """
    daily_wage = float(daily_wage or 0)
    worked_hours = max(float(worked_hours or 0), 0.0)
    standard_hours = float(standard_hours or 8.0) or 8.0
    ot_rate = float(ot_rate_per_hour or 0)

    if worked_hours <= 0:
        return {
            "normal_wage": 0.0,
            "ot_hours": 0.0,
            "ot_amount": 0.0,
            "gross": 0.0,
        }

    if worked_hours < standard_hours:
        hourly = daily_wage / standard_hours
        normal = round(hourly * worked_hours, 2)
        ot_hours = 0.0
        ot_amount = 0.0
    elif worked_hours <= standard_hours:
        normal = round(daily_wage, 2)
        ot_hours = 0.0
        ot_amount = 0.0
    else:
        normal = round(daily_wage, 2)
        ot_hours = round(worked_hours - standard_hours, 2)
        ot_amount = round(ot_hours * ot_rate, 2) if ot_applicable and ot_rate else 0.0

    return {
        "normal_wage": normal,
        "ot_hours": ot_hours,
        "ot_amount": ot_amount,
        "gross": round(normal + ot_amount, 2),
    }


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(value[: len(fmt.replace("%", "0"))], fmt)
        except ValueError:
            continue
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def period_from_month_year(month: int, year: int) -> tuple[str, str]:
    last_day = monthrange(year, month)[1]
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{last_day:02d}"
    return start, end


def count_calendar_days(start: str, end: str) -> int:
    s = _parse_date(start)
    e = _parse_date(end)
    if not s or not e:
        return 0
    return (e - s).days + 1


def _row_employee_identity(row: dict) -> tuple[str, str]:
    """Resolve display code/name from a staff or worker row."""
    code = (
        row.get("employee_code")
        or row.get("worker_code")
        or ""
    ).strip()
    name = (
        row.get("employee_name")
        or row.get("staff_name")
        or row.get("worker_name")
        or ""
    ).strip()
    return code, name


def _build_payroll_line_join_sql(db) -> tuple[str, str]:
    """Schema-safe payroll line query for legacy VPS databases."""
    pr_cols = _table_columns(db, "payroll_runs")
    pl_cols = _table_columns(db, "payroll_lines")
    staff_cols = _table_columns(db, "staff")
    worker_cols = _table_columns(db, "workers")

    run_fields: list[str] = []
    for col in ("run_ref", "period_start", "period_end", "month", "year"):
        run_fields.append(
            f"pr.{col}" if col in pr_cols else f"NULL AS {col}"
        )

    staff_fields: list[str] = []
    staff_fields.append(
        "s.staff_name AS _staff_name"
        if "staff_name" in staff_cols
        else "NULL AS _staff_name"
    )
    staff_fields.append(
        "s.employee_code AS _staff_code"
        if "employee_code" in staff_cols
        else "NULL AS _staff_code"
    )

    worker_fields: list[str] = []
    worker_fields.append(
        "w.worker_name AS _worker_name"
        if "worker_name" in worker_cols
        else "NULL AS _worker_name"
    )
    worker_fields.append(
        "w.worker_code AS _worker_code"
        if "worker_code" in worker_cols
        else "NULL AS _worker_code"
    )

    select_extra = ", ".join(run_fields + staff_fields + worker_fields)
    join_sql = (
        f"SELECT pl.*, {select_extra} "
        "FROM payroll_lines pl "
        "JOIN payroll_runs pr ON pl.payroll_run_id = pr.id "
        "LEFT JOIN staff s ON pl.staff_id = s.id "
        "LEFT JOIN workers w ON pl.worker_id = w.id"
    )

    pl_name = "pl.employee_name" if "employee_name" in pl_cols else "NULL"
    s_name = "s.staff_name" if "staff_name" in staff_cols else "NULL"
    w_name = "w.worker_name" if "worker_name" in worker_cols else "NULL"
    order_sql = (
        f"COALESCE(NULLIF(TRIM({pl_name}), ''), {s_name}, {w_name}), pl.id"
    )
    return join_sql, order_sql


def _enrich_payroll_line(row: dict) -> dict:
    """Populate employee_name/code from snapshot or joined staff/worker rows."""
    name = (row.get("employee_name") or "").strip()
    code = (row.get("employee_code") or "").strip()
    if not name:
        name = (row.get("_staff_name") or row.get("_worker_name") or "").strip()
    if not code:
        code = (row.get("_staff_code") or row.get("_worker_code") or "").strip()
    row["employee_name"] = name
    row["employee_code"] = code
    for key in ("_staff_name", "_staff_code", "_worker_name", "_worker_code"):
        row.pop(key, None)
    return row


def attach_run_employee_summaries(db, runs: list[dict]) -> None:
    """Add employee_summary text to each payroll run for list/dashboard views."""
    if not runs:
        return
    run_ids = [int(r["id"]) for r in runs if r.get("id") is not None]
    if not run_ids:
        return
    placeholders = ",".join("?" * len(run_ids))
    pl_cols = _table_columns(db, "payroll_lines")
    staff_cols = _table_columns(db, "staff")
    worker_cols = _table_columns(db, "workers")
    pl_name = (
        "pl.employee_name"
        if "employee_name" in pl_cols
        else "NULL AS employee_name"
    )
    pl_code = (
        "pl.employee_code"
        if "employee_code" in pl_cols
        else "NULL AS employee_code"
    )
    staff_name = (
        "s.staff_name AS _staff_name"
        if "staff_name" in staff_cols
        else "NULL AS _staff_name"
    )
    staff_code = (
        "s.employee_code AS _staff_code"
        if "employee_code" in staff_cols
        else "NULL AS _staff_code"
    )
    worker_name = (
        "w.worker_name AS _worker_name"
        if "worker_name" in worker_cols
        else "NULL AS _worker_name"
    )
    worker_code = (
        "w.worker_code AS _worker_code"
        if "worker_code" in worker_cols
        else "NULL AS _worker_code"
    )
    query = (
        f"SELECT pl.payroll_run_id, {pl_name}, {pl_code}, "
        f"{staff_name}, {staff_code}, {worker_name}, {worker_code} "
        "FROM payroll_lines pl "
        "LEFT JOIN staff s ON pl.staff_id = s.id "
        "LEFT JOIN workers w ON pl.worker_id = w.id "
        f"WHERE pl.payroll_run_id IN ({placeholders}) "
        "ORDER BY pl.payroll_run_id, pl.id"
    )
    grouped: dict[int, list[str]] = {rid: [] for rid in run_ids}
    for raw in db.execute(query, run_ids).fetchall():
        line = _enrich_payroll_line(dict(raw))
        label_parts = []
        if line.get("employee_code"):
            label_parts.append(str(line["employee_code"]))
        if line.get("employee_name"):
            label_parts.append(str(line["employee_name"]))
        label = " — ".join(label_parts) if label_parts else "—"
        grouped.setdefault(line["payroll_run_id"], []).append(label)
    for run in runs:
        labels = grouped.get(int(run["id"]), [])
        if not labels:
            run["employee_summary"] = "—"
        elif len(labels) <= 3:
            run["employee_summary"] = ", ".join(labels)
        else:
            run["employee_summary"] = ", ".join(labels[:3]) + f" (+{len(labels) - 3} more)"


def fetch_payroll_lines(
    db,
    *,
    run_id: int | None = None,
    line_id: int | None = None,
    approval_status: str | None = None,
    payment_status_not: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Payroll lines with staff/worker names joined when snapshot fields are blank."""
    join_sql, default_order = _build_payroll_line_join_sql(db)
    pl_cols = _table_columns(db, "payroll_lines")
    query = join_sql + " WHERE 1=1"
    params: list = []
    if run_id is not None:
        query += " AND pl.payroll_run_id=?"
        params.append(run_id)
    if line_id is not None:
        query += " AND pl.id=?"
        params.append(line_id)
    if approval_status is not None and "approval_status" in pl_cols:
        query += " AND pl.approval_status=?"
        params.append(approval_status)
    if payment_status_not is not None and "payment_status" in pl_cols:
        query += " AND pl.payment_status != ?"
        params.append(payment_status_not)
    if payment_status_not is not None:
        query += " ORDER BY pl.id DESC"
    else:
        query += f" ORDER BY {default_order}"
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    return [_enrich_payroll_line(dict(r)) for r in db.execute(query, params).fetchall()]


def fetch_holidays(db, start: str, end: str, employee_type: str | None = None) -> list[dict]:
    query = (
        "SELECT h.*, GROUP_CONCAT(ha.applies_to) AS applies_to "
        "FROM holidays h "
        "LEFT JOIN holiday_applicability ha ON h.id = ha.holiday_id "
        "WHERE h.holiday_date BETWEEN ? AND ? "
        "GROUP BY h.id ORDER BY h.holiday_date"
    )
    rows = [dict(r) for r in db.execute(query, (start, end)).fetchall()]
    if not employee_type:
        return rows
    filtered = []
    for row in rows:
        applies = (row.get("applies_to") or "").split(",")
        applies = [a.strip() for a in applies if a.strip()]
        if not applies or employee_type in applies:
            filtered.append(row)
    return filtered


def fetch_attendance_for_employee(
    db,
    employee_type: str,
    employee_id: int,
    start: str,
    end: str,
) -> list[dict]:
    if employee_type == "staff":
        worker_source = "staff"
    else:
        worker_source = "worker"
    rows = db.execute(
        "SELECT * FROM attendance "
        "WHERE worker_id=? AND COALESCE(worker_source, 'worker')=? "
        "AND attendance_date BETWEEN ? AND ? "
        "AND COALESCE(approval_status, 'Approved') NOT IN ('Rejected by Checker', 'Rejected by Approver') "
        "ORDER BY attendance_date",
        (employee_id, worker_source, start, end),
    ).fetchall()
    return [dict(r) for r in rows]


def summarize_attendance(attendance_rows: list[dict]) -> dict:
    present_days = 0
    total_hours = 0.0
    ot_hours = 0.0
    present_dates: set[str] = set()
    for row in attendance_rows:
        status = (row.get("status") or "Present").strip()
        status_lower = status.lower()
        if status_lower in ("present", "half day", "half-day"):
            present_days += 1 if status_lower == "present" else 0.5
            att_date = row.get("attendance_date")
            if att_date:
                present_dates.add(str(att_date)[:10])
        total_hours += float(row.get("total_hours") or 0)
        ot_hours += float(row.get("ot_hours") or 0)
    return {
        "present_days": present_days,
        "total_hours": round(total_hours, 2),
        "ot_hours": round(ot_hours, 2),
        "attendance_count": len(attendance_rows),
        "present_dates": present_dates,
    }


def _component_amount(components: list[dict], names: tuple[str, ...]) -> float:
    lowered = {n.lower() for n in names}
    for comp in components:
        if (comp.get("component_name") or "").strip().lower() in lowered:
            return float(comp.get("amount") or 0)
    return 0.0


def _fetch_staff_salary_components(db, staff_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT component_name, amount FROM staff_salary_components "
        "WHERE staff_id=? ORDER BY sort_order, id",
        (staff_id,),
    ).fetchall()
    return [
        {"component_name": r["component_name"], "amount": float(r["amount"] or 0)}
        for r in rows
    ]


def _effective_monthly_salary(staff_row: dict, components: list[dict]) -> float:
    """Monthly gross from split-up, excluding benefits already provided by company."""
    if not components:
        return float(staff_row.get("salary_amount") or 0)
    room_provided = (staff_row.get("company_room_provided") or "No") == "Yes"
    food_provided = (staff_row.get("company_food_provided") or "No") == "Yes"
    total = 0.0
    for comp in components:
        name = (comp.get("component_name") or "").strip()
        name_lower = name.lower()
        if room_provided and "room rent" in name_lower:
            continue
        if food_provided and "food" in name_lower:
            continue
        total += float(comp.get("amount") or 0)
    if total > 0:
        return round(total, 2)
    return float(staff_row.get("salary_amount") or 0)


def _continuous_months(joining_date: str | None, period_end: str) -> int:
    start = _parse_date(joining_date or "")
    end = _parse_date(period_end)
    if not start or not end or end < start:
        return 0
    return max((end.year - start.year) * 12 + (end.month - start.month), 0)


def _travel_allowance_for_staff(db, staff_id: int, staff_row: dict, period_end: str) -> float:
    rows = db.execute(
        "SELECT continuous_months, travel_mode, allowance_amount FROM staff_travel_tiers "
        "WHERE staff_id=? ORDER BY continuous_months DESC, sort_order, id",
        (staff_id,),
    ).fetchall()
    if not rows:
        return 0.0
    tenure_months = _continuous_months(staff_row.get("joining_date"), period_end)
    eligible = [dict(r) for r in rows if int(r["continuous_months"] or 0) <= tenure_months]
    if not eligible:
        return 0.0
    best = max(eligible, key=lambda r: int(r["continuous_months"] or 0))
    return round(float(best.get("allowance_amount") or 0), 2)


def _count_unworked_holidays(holiday_dates: set[str], present_dates: set[str]) -> int:
    """Pay holiday only for declared holidays where the employee did not work."""
    return sum(1 for hd in holiday_dates if hd not in present_dates)


def _staff_statutory_deductions(
    staff_row: dict,
    components: list[dict],
    earned_gross: float,
) -> float:
    """Employee PF/ESI deductions for net pay (Indian payroll defaults)."""
    deductions = 0.0
    if staff_row.get("pf_applicable"):
        pf_base = _component_amount(components, ("Basic Salary", "Basic"))
        da = _component_amount(components, ("DA",))
        pf_wages = pf_base + da if pf_base > 0 else earned_gross
        pf_wages = min(pf_wages, 15000.0)
        pf_rate = float(staff_row.get("pf_rate") or 12)
        deductions += round(pf_wages * pf_rate / 100.0, 2)
    if staff_row.get("esi_applicable") and earned_gross <= 21000:
        esi_rate = float(staff_row.get("esi_rate") or 0.75)
        deductions += round(earned_gross * esi_rate / 100.0, 2)
    return round(deductions, 2)


def _fetch_monthly_attendance_summary(db, staff_id: int, start: str, end: str) -> dict | None:
    try:
        from attendance_service import fetch_monthly_attendance_for_period

        return fetch_monthly_attendance_for_period(db, staff_id, start, end)
    except Exception:
        return None


def calculate_monthly_staff_pay(
    db,
    staff_row: dict,
    start: str,
    end: str,
    holidays: list[dict] | None = None,
) -> dict:
    """Monthly staff: pro-rata base + OT + unworked holidays + travel tier − PF/ESI."""
    staff_id = staff_row["id"]
    components = _fetch_staff_salary_components(db, staff_id)
    monthly_salary = _effective_monthly_salary(staff_row, components)
    ot_applicable = (staff_row.get("ot_applicable") or "No") == "Yes"
    ot_rate = float(staff_row.get("ot_rate_per_hour") or 0)
    holiday_pay = (staff_row.get("holiday_pay_applicable") or "No") == "Yes"
    working_days = count_calendar_days(start, end)
    holiday_dates = {str(h["holiday_date"])[:10] for h in (holidays or [])}
    monthly_summary = _fetch_monthly_attendance_summary(db, staff_id, start, end)
    if monthly_summary:
        present_days = monthly_summary["present_days"]
        present_dates = monthly_summary.get("present_dates") or set()
        att_summary = {
            "present_days": present_days,
            "ot_hours": monthly_summary["ot_hours"],
            "present_dates": present_dates,
            "attendance_count": 1,
            "total_hours": 0.0,
        }
    else:
        attendance = fetch_attendance_for_employee(db, "staff", staff_id, start, end)
        att_summary = summarize_attendance(attendance)
        present_days = att_summary["present_days"]
        present_dates = att_summary["present_dates"]
    per_day = monthly_salary / working_days if working_days else 0.0
    earned_base = round(per_day * present_days, 2)
    ot_amount = round(att_summary["ot_hours"] * ot_rate, 2) if ot_applicable else 0.0
    holiday_amount = 0.0
    if holiday_pay and holiday_dates and not monthly_summary:
        unworked_holidays = _count_unworked_holidays(holiday_dates, present_dates)
        holiday_amount = round(unworked_holidays * per_day, 2)
    travel_allowance = 0.0
    if present_days > 0:
        travel_allowance = _travel_allowance_for_staff(db, staff_id, staff_row, end)
        if working_days and present_days < working_days:
            travel_allowance = round(travel_allowance * present_days / working_days, 2)
    gross_before_deductions = round(
        earned_base + ot_amount + holiday_amount + travel_allowance, 2
    )
    deductions = _staff_statutory_deductions(staff_row, components, gross_before_deductions)
    net = round(max(gross_before_deductions - deductions, 0), 2)
    if monthly_summary and monthly_summary.get("absent_days") is not None:
        absent_val = float(monthly_summary.get("absent_days") or 0)
        leave_days = absent_val if absent_val > 0 else max(working_days - present_days, 0)
    else:
        leave_days = max(working_days - present_days, 0)
    return {
        "base_salary": monthly_salary,
        "working_days": working_days,
        "present_days": present_days,
        "leave_days": round(leave_days, 2),
        "attendance_source": monthly_summary.get("source") if monthly_summary else "daily",
        "ot_hours": att_summary["ot_hours"],
        "ot_amount": ot_amount,
        "holiday_pay": holiday_amount,
        "travel_allowance": travel_allowance,
        "gross_salary": gross_before_deductions,
        "deductions": deductions,
        "advance_deduction": 0.0,
        "net_salary": net,
    }


def calculate_staff_period_pay(
    db,
    staff_row: dict,
    start: str,
    end: str,
    holidays: list[dict] | None = None,
) -> dict:
    """Route staff payroll by salary_type: Monthly vs Daily."""
    salary_type = (staff_row.get("salary_type") or "Monthly").strip()
    if salary_type == "Monthly":
        return calculate_monthly_staff_pay(db, staff_row, start, end, holidays)
    return calculate_worker_period_pay(
        db,
        staff_row,
        start,
        end,
        holidays,
        employee_type="staff",
    )


def calculate_worker_period_pay(
    db,
    worker_row: dict,
    start: str,
    end: str,
    holidays: list[dict] | None = None,
    *,
    employee_type: str | None = None,
) -> dict:
    """Daily/hourly worker (or daily staff) pay aggregated over date range."""
    worker_id = worker_row["id"]
    if employee_type:
        resolved_type = employee_type
    else:
        resolved_type = (
            "subcontractor"
            if (worker_row.get("worker_category") or "") == "Sub Contractor Staff"
            else "company_worker"
        )
    salary_type = (worker_row.get("salary_type") or "Daily").strip()
    rate_amount = float(worker_row.get("salary_amount") or 0)
    ot_applicable = (worker_row.get("ot_applicable") or "No") == "Yes"
    ot_rate = float(worker_row.get("ot_rate_per_hour") or 0)
    standard_hours = float(worker_row.get("working_hours") or 8) or 8.0
    attendance = fetch_attendance_for_employee(db, resolved_type, worker_id, start, end)
    normal_total = 0.0
    ot_total = 0.0
    ot_hours_total = 0.0
    present_days = 0.0
    present_dates: set[str] = set()
    for row in attendance:
        status = (row.get("status") or "Present").strip().lower()
        if status not in ("present", "half day", "half-day"):
            continue
        att_date = row.get("attendance_date")
        if att_date:
            present_dates.add(str(att_date)[:10])
        hours = float(row.get("total_hours") or 0)
        day_fraction = 1.0 if status == "present" else 0.5
        if salary_type == "Hourly":
            hourly_rate = rate_amount
            normal_total += round(hours * hourly_rate, 2)
            present_days += day_fraction
        else:
            calc = calculate_daily_wage(
                rate_amount, hours, ot_rate, ot_applicable, standard_hours
            )
            normal_total += calc["normal_wage"]
            ot_total += calc["ot_amount"]
            ot_hours_total += calc["ot_hours"]
            present_days += day_fraction
    holiday_amount = 0.0
    if (worker_row.get("holiday_pay_applicable") or "No") == "Yes" and holidays:
        holiday_dates = {str(h["holiday_date"])[:10] for h in holidays}
        unpaid_holidays = _count_unworked_holidays(holiday_dates, present_dates)
        if salary_type == "Hourly":
            holiday_amount = round(unpaid_holidays * rate_amount * standard_hours, 2)
        else:
            holiday_amount = round(unpaid_holidays * rate_amount, 2)
    gross = round(normal_total + ot_total + holiday_amount, 2)
    working_days = count_calendar_days(start, end)
    return {
        "base_salary": rate_amount,
        "working_days": working_days,
        "present_days": present_days,
        "leave_days": max(working_days - present_days, 0),
        "ot_hours": round(ot_hours_total, 2),
        "ot_amount": round(ot_total, 2),
        "holiday_pay": holiday_amount,
        "gross_salary": gross,
        "deductions": 0.0,
        "advance_deduction": 0.0,
        "net_salary": gross,
        "normal_wage": round(normal_total, 2),
    }


def payroll_employment_filter(employee_type: str) -> str:
    if employee_type in ("staff", "company_worker"):
        return "company_staff"
    if employee_type == "subcontractor":
        return "subcontractor"
    return ""


_ATTENDANCE_REJECTED = ("Rejected by Checker", "Rejected by Approver")


def _year_months_in_period(start: str, end: str) -> list[str]:
    ym_start = (start or "")[:7]
    ym_end = (end or "")[:7]
    if not ym_start or not ym_end or len(ym_start) < 7 or len(ym_end) < 7:
        return []
    sy, sm = int(ym_start[:4]), int(ym_start[5:7])
    ey, em = int(ym_end[:4]), int(ym_end[5:7])
    months: list[str] = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _has_daily_attendance(
    db,
    employee_id: int,
    worker_source: str,
    period_start: str,
    period_end: str,
) -> bool:
    row = db.execute(
        "SELECT 1 FROM attendance "
        "WHERE worker_id=? AND COALESCE(worker_source, 'worker')=? "
        "AND attendance_date BETWEEN ? AND ? "
        "AND COALESCE(approval_status, 'Approved') NOT IN (?, ?) "
        "LIMIT 1",
        (employee_id, worker_source, period_start, period_end, *_ATTENDANCE_REJECTED),
    ).fetchone()
    return row is not None


def _has_staff_monthly_attendance(db, staff_id: int, year_months: list[str]) -> bool:
    if not year_months or not _table_exists(db, "staff_monthly_attendance"):
        return False
    placeholders = ",".join("?" * len(year_months))
    try:
        row = db.execute(
            f"SELECT 1 FROM staff_monthly_attendance "
            f"WHERE staff_id=? AND year_month IN ({placeholders}) "
            "AND COALESCE(approval_status, 'Approved') NOT IN (?, ?) "
            "LIMIT 1",
            (staff_id, *year_months, *_ATTENDANCE_REJECTED),
        ).fetchone()
    except Exception:
        return False
    return row is not None


def _has_employee_timesheet(
    db,
    *,
    staff_id: int | None = None,
    worker_id: int | None = None,
    year_months: list[str],
) -> bool:
    if not year_months or not _table_exists(db, "employee_monthly_timesheets"):
        return False
    placeholders = ",".join("?" * len(year_months))
    try:
        if staff_id is not None:
            row = db.execute(
                f"SELECT 1 FROM employee_monthly_timesheets "
                f"WHERE staff_id=? AND year_month IN ({placeholders}) LIMIT 1",
                (staff_id, *year_months),
            ).fetchone()
            return row is not None
        if worker_id is not None:
            row = db.execute(
                f"SELECT 1 FROM employee_monthly_timesheets "
                f"WHERE worker_id=? AND year_month IN ({placeholders}) LIMIT 1",
                (worker_id, *year_months),
            ).fetchone()
            return row is not None
    except Exception:
        return False
    return False


def employee_has_period_data(
    db,
    employee_type: str,
    employee_id: int,
    period_start: str,
    period_end: str,
) -> bool:
    """True when the employee has attendance/summary/timesheet data for the payroll period."""
    if not period_start or not period_end:
        return True
    year_months = _year_months_in_period(period_start, period_end)
    if employee_type == "staff":
        if _has_daily_attendance(db, employee_id, "staff", period_start, period_end):
            return True
        if _has_staff_monthly_attendance(db, employee_id, year_months):
            return True
        return _has_employee_timesheet(db, staff_id=employee_id, year_months=year_months)
    if employee_type == "company_worker":
        if _has_daily_attendance(db, employee_id, "worker", period_start, period_end):
            return True
        return _has_employee_timesheet(db, worker_id=employee_id, year_months=year_months)
    if employee_type == "subcontractor":
        return _has_daily_attendance(db, employee_id, "worker", period_start, period_end)
    return False


def serialize_eligible_employee(emp: dict) -> dict:
    et = emp["employee_type"]
    if et == "staff":
        type_label = "Monthly Staff"
    elif et == "company_worker":
        type_label = "Company Worker"
    else:
        type_label = "Sub Contractor"
    return {
        "employee_type": et,
        "employee_id": emp["employee_id"],
        "employee_name": (
            emp.get("employee_name")
            or emp.get("staff_name")
            or emp.get("worker_name")
            or ""
        ),
        "employee_code": (
            emp.get("employee_code")
            or emp.get("worker_code")
            or ""
        ),
        "department": emp.get("department") or "",
        "emp_filter": payroll_employment_filter(et),
        "type_label": type_label,
    }


_MONTH_LABELS = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(db, table: str) -> set[str]:
    if not _table_exists(db, table):
        return set()
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}


def format_year_month_label(year_month: str) -> str:
    if not year_month or len(year_month) < 7:
        return year_month or ""
    try:
        month_num = int(year_month[5:7])
    except ValueError:
        return year_month
    if 1 <= month_num <= 12:
        return f"{_MONTH_LABELS[month_num]} {year_month[:4]}"
    return year_month


def _year_month_cutoff(months_back: int) -> str:
    now = datetime.now()
    y, m = now.year, now.month - int(months_back or 0)
    while m <= 0:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}"


def run_covers_year_month(run: dict, year_month: str) -> bool:
    if not year_month or len(year_month) < 7:
        return False
    try:
        month_num = int(year_month[5:7])
        year_num = int(year_month[:4])
    except ValueError:
        return False
    if run.get("month") and run.get("year"):
        return int(run["year"]) == year_num and int(run["month"]) == month_num
    month_start, month_end = period_from_month_year(month_num, year_num)
    period_start = (run.get("period_start") or "")[:10]
    period_end = (run.get("period_end") or "")[:10]
    if not period_start or not period_end:
        return False
    return period_start <= month_end and period_end >= month_start


def _classify_payroll_coverage(run_status: str, payment_status: str | None) -> str:
    status = (run_status or "Draft").strip()
    pay = (payment_status or "Pending").strip()
    if status == "Draft":
        return "draft"
    if status == "Paid" or pay == "Paid":
        return "paid"
    if status == "Approved":
        return "unpaid" if pay != "Paid" else "paid"
    if status in ("Pending Verification", "Pending Checker", "Pending Approval"):
        return "in_progress"
    return "in_progress"


_COVERAGE_RANK = {"none": 0, "draft": 1, "unpaid": 2, "in_progress": 3, "paid": 4}


def _collect_attendance_month_entries(db) -> dict[tuple[str, int, str], set[str]]:
    """Map (employee_type, employee_id, year_month) -> attendance data sources."""
    entries: dict[tuple[str, int, str], set[str]] = {}
    rejected = _ATTENDANCE_REJECTED

    def add(employee_type: str, employee_id: int, year_month: str, source: str) -> None:
        ym = (year_month or "")[:7]
        if len(ym) < 7:
            return
        key = (employee_type, int(employee_id), ym)
        entries.setdefault(key, set()).add(source)

    if _table_exists(db, "staff_monthly_attendance"):
        try:
            for row in db.execute(
                "SELECT m.staff_id, m.year_month "
                "FROM staff_monthly_attendance m "
                "JOIN staff s ON s.id = m.staff_id "
                "WHERE COALESCE(s.status, 'Active') = 'Active' "
                "AND COALESCE(m.approval_status, 'Approved') NOT IN (?, ?)",
                rejected,
            ).fetchall():
                add("staff", row["staff_id"], row["year_month"], "monthly_attendance")
        except Exception:
            pass

    for row in db.execute(
        "SELECT a.worker_id AS staff_id, substr(a.attendance_date, 1, 7) AS year_month "
        "FROM attendance a "
        "JOIN staff s ON s.id = a.worker_id "
        "WHERE COALESCE(a.worker_source, 'worker') = 'staff' "
        "AND COALESCE(s.status, 'Active') = 'Active' "
        "AND COALESCE(a.approval_status, 'Approved') NOT IN (?, ?) "
        "GROUP BY a.worker_id, year_month",
        rejected,
    ).fetchall():
        add("staff", row["staff_id"], row["year_month"], "daily_attendance")

    for row in db.execute(
        "SELECT a.worker_id, substr(a.attendance_date, 1, 7) AS year_month, w.worker_category "
        "FROM attendance a "
        "JOIN workers w ON w.id = a.worker_id "
        "WHERE COALESCE(a.worker_source, 'worker') = 'worker' "
        "AND COALESCE(w.status, 'Active') = 'Active' "
        "AND COALESCE(a.approval_status, 'Approved') NOT IN (?, ?) "
        "GROUP BY a.worker_id, year_month",
        rejected,
    ).fetchall():
        category = (row["worker_category"] or "Company Staff").strip()
        employee_type = (
            "subcontractor" if category == "Sub Contractor Staff" else "company_worker"
        )
        add(employee_type, row["worker_id"], row["year_month"], "daily_attendance")

    if _table_exists(db, "employee_monthly_timesheets"):
        for row in db.execute(
            "SELECT staff_id, worker_id, year_month "
            "FROM employee_monthly_timesheets "
            "WHERE year_month IS NOT NULL AND TRIM(year_month) != ''"
        ).fetchall():
            ym = row["year_month"]
            if row["staff_id"]:
                add("staff", row["staff_id"], ym, "timesheet")
            if row["worker_id"]:
                worker = db.execute(
                    "SELECT worker_category FROM workers WHERE id=?",
                    (row["worker_id"],),
                ).fetchone()
                if not worker:
                    continue
                category = (worker["worker_category"] or "Company Staff").strip()
                employee_type = (
                    "subcontractor"
                    if category == "Sub Contractor Staff"
                    else "company_worker"
                )
                add(employee_type, row["worker_id"], ym, "timesheet")

    return entries


def _build_payroll_coverage_index(db) -> dict[tuple[str, int, str], dict]:
    index: dict[tuple[str, int, str], dict] = {}
    if not _table_exists(db, "payroll_lines") or not _table_exists(db, "payroll_runs"):
        return index
    try:
        rows = db.execute(
            "SELECT pl.employee_type, pl.staff_id, pl.worker_id, pl.payment_status, "
            "pr.id AS run_id, pr.status AS run_status, pr.period_start, pr.period_end, "
            "pr.month, pr.year "
            "FROM payroll_lines pl "
            "JOIN payroll_runs pr ON pl.payroll_run_id = pr.id"
        ).fetchall()
    except Exception:
        return index
    for raw in rows:
        row = dict(raw)
        employee_type = row["employee_type"]
        employee_id = row["staff_id"] if employee_type == "staff" else row["worker_id"]
        if not employee_id:
            continue
        run = {
            "period_start": row["period_start"],
            "period_end": row["period_end"],
            "month": row["month"],
            "year": row["year"],
        }
        if row.get("month") and row.get("year"):
            year_months = [f"{int(row['year']):04d}-{int(row['month']):02d}"]
        else:
            year_months = _year_months_in_period(row["period_start"], row["period_end"])
        payroll_status = _classify_payroll_coverage(
            row["run_status"], row.get("payment_status")
        )
        for ym in year_months:
            key = (employee_type, int(employee_id), ym)
            existing = index.get(key)
            if existing is None or _COVERAGE_RANK[payroll_status] > _COVERAGE_RANK[
                existing["payroll_status"]
            ]:
                index[key] = {
                    "payroll_status": payroll_status,
                    "run_id": row["run_id"],
                    "run_status": row["run_status"],
                }
    return index


_DATA_SOURCE_LABELS = {
    "monthly_attendance": "Monthly attendance",
    "daily_attendance": "Daily attendance",
    "timesheet": "Timesheet",
}

_PENDING_PAYROLL_STATUSES = frozenset({"none", "draft", "unpaid"})

_PENDING_STATUS_LABELS = {
    "none": "Not generated",
    "draft": "Draft only",
    "unpaid": "Approved — unpaid",
}


def list_pending_payroll_months(
    db,
    *,
    months_back: int = 24,
    year_month_filter: str | None = None,
) -> list[dict]:
    """
    Staff/workers with attendance or timesheet data but no finalized payroll for that month.

    Pending when payroll_status is none (no run), draft (draft run only), or unpaid
    (approved run, payment not recorded). in_progress and paid runs are excluded.
    """
    attendance_entries = _collect_attendance_month_entries(db)
    coverage = _build_payroll_coverage_index(db)
    cutoff = _year_month_cutoff(months_back)
    ym_filter = (year_month_filter or "")[:7] if year_month_filter else None

    staff_cols = _table_columns(db, "staff")
    staff_dept_sql = ", department" if "department" in staff_cols else ""
    staff_rows = {
        r["id"]: dict(r)
        for r in db.execute(
            f"SELECT id, employee_code, staff_name{staff_dept_sql} FROM staff "
            "WHERE COALESCE(status, 'Active') = 'Active'"
        ).fetchall()
    }
    worker_cols = _table_columns(db, "workers")
    worker_select = (
        "SELECT id, worker_code, worker_name, worker_category, project_id "
        "FROM workers WHERE COALESCE(status, 'Active') = 'Active'"
    )
    if _table_exists(db, "workers") and "department" in worker_cols:
        worker_select = (
            "SELECT id, worker_code, worker_name, worker_category, department, project_id "
            "FROM workers WHERE COALESCE(status, 'Active') = 'Active'"
        )
    worker_rows = {
        r["id"]: dict(r)
        for r in db.execute(worker_select).fetchall()
    }

    pending: list[dict] = []
    for (employee_type, employee_id, year_month), sources in attendance_entries.items():
        if year_month < cutoff:
            continue
        if ym_filter and year_month != ym_filter:
            continue
        cov = coverage.get((employee_type, employee_id, year_month))
        payroll_status = cov["payroll_status"] if cov else "none"
        if payroll_status not in _PENDING_PAYROLL_STATUSES:
            continue

        if employee_type == "staff":
            emp = staff_rows.get(employee_id)
            if not emp:
                continue
            employee_code = (emp.get("employee_code") or "").strip()
            employee_name = (emp.get("staff_name") or "").strip()
            department = emp.get("department") or ""
            project_id = None
        else:
            emp = worker_rows.get(employee_id)
            if not emp:
                continue
            employee_code = (emp.get("worker_code") or "").strip()
            employee_name = (emp.get("worker_name") or "").strip()
            department = emp.get("department") or ""
            project_id = emp.get("project_id")

        type_label = serialize_eligible_employee(
            {"employee_type": employee_type, "employee_id": employee_id}
        )["type_label"]
        source_labels = ", ".join(
            _DATA_SOURCE_LABELS.get(src, src.replace("_", " ").title())
            for src in sorted(sources)
        )
        month_num = int(year_month[5:7])
        year_num = int(year_month[:4])
        pending.append(
            {
                "employee_type": employee_type,
                "employee_id": employee_id,
                "employee_code": employee_code,
                "employee_name": employee_name,
                "year_month": year_month,
                "month_label": format_year_month_label(year_month),
                "month": month_num,
                "year": year_num,
                "type_label": type_label,
                "employment_category": payroll_employment_filter(employee_type),
                "department": department,
                "project_id": project_id,
                "data_source": source_labels,
                "payroll_status": payroll_status,
                "status_label": _PENDING_STATUS_LABELS.get(
                    payroll_status, payroll_status
                ),
                "run_id": cov["run_id"] if cov else None,
            }
        )

    pending.sort(
        key=lambda row: (row["year_month"], row["employee_name"], row["employee_code"]),
        reverse=True,
    )
    return pending


def summarize_pending_payroll_months(pending: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for row in pending:
        ym = row["year_month"]
        counts[ym] = counts.get(ym, 0) + 1
    summary = [
        {
            "year_month": ym,
            "month_label": format_year_month_label(ym),
            "count": count,
        }
        for ym, count in counts.items()
    ]
    summary.sort(key=lambda item: item["year_month"], reverse=True)
    return summary


def list_eligible_employees(
    db,
    employee_type: str | None,
    project_id: int | None = None,
    department: str | None = None,
    employee_ids: list[int] | None = None,
    *,
    period_start: str | None = None,
    period_end: str | None = None,
) -> list[dict]:
    results = []
    if employee_type == "company_staff":
        types = ["staff", "company_worker"]
    elif employee_type in EMPLOYEE_TYPES:
        types = [employee_type]
    else:
        types = list(EMPLOYEE_TYPES)

    if "staff" in types:
        query = (
            "SELECT s.*, s.staff_name AS employee_name, s.employee_code AS employee_code "
            "FROM staff s WHERE 1=1"
        )
        params: list = []
        if department and "department" in _table_columns(db, "staff"):
            query += " AND department=?"
            params.append(department)
        if employee_ids:
            query += f" AND id IN ({','.join('?' * len(employee_ids))})"
            params.extend(employee_ids)
        query += " AND COALESCE(status, 'Active')='Active' ORDER BY staff_name"
        for row in db.execute(query, params).fetchall():
            item = dict(row)
            item["employee_type"] = "staff"
            item["employee_id"] = item["id"]
            results.append(item)

    worker_types = [t for t in types if t in ("company_worker", "subcontractor")]
    if worker_types:
        query = (
            "SELECT w.*, w.worker_name AS employee_name, w.worker_code AS employee_code "
            "FROM workers w WHERE COALESCE(w.status, 'Active')='Active'"
        )
        params = []
        if project_id:
            query += " AND w.project_id=?"
            params.append(project_id)
        if employee_ids:
            query += f" AND w.id IN ({','.join('?' * len(employee_ids))})"
            params.extend(employee_ids)
        for row in db.execute(query, params).fetchall():
            item = dict(row)
            cat = (item.get("worker_category") or "Company Staff").strip()
            et = "subcontractor" if cat == "Sub Contractor Staff" else "company_worker"
            if et not in worker_types:
                continue
            item["employee_type"] = et
            item["employee_id"] = item["id"]
            results.append(item)

    if period_start and period_end:
        results = [
            emp
            for emp in results
            if employee_has_period_data(
                db, emp["employee_type"], emp["employee_id"], period_start, period_end
            )
        ]
    return results


def generate_payroll_run(
    db,
    *,
    run_type: str,
    period_start: str,
    period_end: str,
    month: int | None,
    year: int | None,
    project_id: int | None,
    department: str | None,
    employee_type: str | None,
    employee_ids: list[int] | None,
    created_by: str,
) -> tuple[int, list[int]]:
    """Create draft payroll run and line items. Returns (run_id, line_ids)."""
    employees = list_eligible_employees(
        db,
        employee_type,
        project_id,
        department,
        employee_ids,
        period_start=period_start,
        period_end=period_end,
    )
    if not employees:
        raise ValueError("No eligible employees found for payroll generation.")

    run_ref = f"PR-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO payroll_runs("
        "run_ref, run_type, period_start, period_end, month, year, project_id, department, "
        "employee_type, status, approval_status, locked, draft_saved, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run_ref,
            run_type,
            period_start,
            period_end,
            month,
            year,
            project_id if employee_type not in ("company_staff", "staff", "all") else None,
            department,
            employee_type or "all",
            "Draft",
            "Draft",
            0,
            0,
            created_by,
            now,
        ),
    )
    run_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    line_ids = []
    total_gross = 0.0
    total_net = 0.0

    for emp in employees:
        et = emp["employee_type"]
        holidays = fetch_holidays(db, period_start, period_end, et)
        if et == "staff":
            calc = calculate_staff_period_pay(db, emp, period_start, period_end, holidays)
        else:
            calc = calculate_worker_period_pay(db, emp, period_start, period_end, holidays)

        total_gross += calc["gross_salary"]
        total_net += calc["net_salary"]
        emp_code, emp_name = _row_employee_identity(emp)
        db.execute(
            "INSERT INTO payroll_lines("
            "payroll_run_id, employee_type, staff_id, worker_id, employee_code, employee_name, "
            "department, project_id, salary_type, base_salary, working_days, present_days, "
            "leave_days, ot_hours, ot_amount, holiday_pay, gross_salary, deductions, "
            "advance_deduction, net_salary, verification_status, approval_status, payment_status, "
            "locked, calc_snapshot"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                et,
                emp["id"] if et == "staff" else None,
                emp["id"] if et != "staff" else None,
                emp_code,
                emp_name,
                emp.get("department") or "",
                emp.get("project_id") or project_id,
                emp.get("salary_type") or "Monthly",
                calc["base_salary"],
                calc["working_days"],
                calc["present_days"],
                calc["leave_days"],
                calc["ot_hours"],
                calc["ot_amount"],
                calc.get("holiday_pay", 0),
                calc["gross_salary"],
                calc.get("deductions", 0),
                calc.get("advance_deduction", 0),
                calc["net_salary"],
                "Pending",
                "Draft",
                "Pending",
                0,
                json.dumps(calc),
            ),
        )
        line_ids.append(db.execute("SELECT last_insert_rowid()").fetchone()[0])

    db.execute(
        "UPDATE payroll_runs SET total_gross=?, total_net=?, employee_count=? WHERE id=?",
        (round(total_gross, 2), round(total_net, 2), len(line_ids), run_id),
    )
    return run_id, line_ids


def export_register_rows(db, run_id: int) -> list[dict]:
    return fetch_payroll_lines(db, run_id=run_id)


def get_employee_profile(db, employee_type: str, employee_id: int) -> dict | None:
    if employee_type == "staff":
        row = db.execute("SELECT * FROM staff WHERE id=?", (employee_id,)).fetchone()
        if not row:
            return None
        profile = dict(row)
        profile["employee_type"] = "staff"
        profile["employee_name"] = profile.get("staff_name")
        profile["employee_code"] = profile.get("employee_code")
        revisions = db.execute(
            "SELECT * FROM salary_revisions WHERE employee_type='staff' AND staff_id=? "
            "ORDER BY effective_date DESC, id DESC",
            (employee_id,),
        ).fetchall()
    else:
        row = db.execute("SELECT * FROM workers WHERE id=?", (employee_id,)).fetchone()
        if not row:
            return None
        profile = dict(row)
        cat = (profile.get("worker_category") or "Company Staff").strip()
        profile["employee_type"] = "subcontractor" if cat == "Sub Contractor Staff" else "company_worker"
        profile["employee_name"] = profile.get("worker_name")
        profile["employee_code"] = profile.get("worker_code")
        revisions = db.execute(
            "SELECT * FROM salary_revisions WHERE employee_type IN ('company_worker','subcontractor') "
            "AND worker_id=? ORDER BY effective_date DESC, id DESC",
            (employee_id,),
        ).fetchall()

    profile["salary_revisions"] = [dict(r) for r in revisions]
    et = profile["employee_type"]
    eid = employee_id
    src = "staff" if et == "staff" else "worker"
    att = db.execute(
        "SELECT COUNT(*) AS c, SUM(total_hours) AS hrs FROM attendance "
        "WHERE worker_id=? AND COALESCE(worker_source, 'worker')=?",
        (eid, src),
    ).fetchone()
    profile["attendance_summary"] = {
        "records": att["c"] if att else 0,
        "total_hours": float(att["hrs"] or 0) if att else 0,
    }
    if et == "staff":
        payroll_lines = db.execute(
            "SELECT * FROM payroll_lines WHERE staff_id=? ORDER BY id DESC LIMIT 12",
            (employee_id,),
        ).fetchall()
    else:
        payroll_lines = db.execute(
            "SELECT * FROM payroll_lines WHERE worker_id=? ORDER BY id DESC LIMIT 12",
            (employee_id,),
        ).fetchall()
    profile["payroll_summary"] = [dict(r) for r in payroll_lines]
    return profile
