"""MAXEK ERP – Payroll calculation and generation service."""

from __future__ import annotations

import json
from calendar import monthrange
from datetime import datetime, timedelta

from payroll_calc import (
    CALC_BASIS,
    employment_window,
    in_window,
    is_sunday,
    monthly_pay_breakdown,
    parse_iso_date,
    period_day_counts,
    prorate_by_working_days,
    resolve_payable_days,
    round_money,
)


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
    row["calc"] = parse_calc_snapshot(row.get("calc_snapshot"))
    return row


def parse_calc_snapshot(raw) -> dict:
    """Decode a payroll line's stored calculation snapshot (``{}`` if absent/invalid)."""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def line_day_basis(line: dict) -> dict:
    """Day-basis figures for display (payslip, register, dashboard, export).

    Lines generated before the Sunday-excluded rule keep their stored values and
    are flagged ``legacy`` so reports never silently restate historic payroll.
    """
    calc = line.get("calc") or parse_calc_snapshot(line.get("calc_snapshot"))
    current = calc.get("calc_basis") == CALC_BASIS
    working = calc.get("working_days") if current else line.get("working_days")
    payable = (
        calc.get("payable_days")
        if current and calc.get("payable_days") is not None
        else line.get("present_days")
    )
    return {
        "legacy": not current,
        "calendar_days": calc.get("calendar_days") if current else None,
        "sundays": calc.get("sundays") if current else None,
        "working_days": working,
        "payable_days": payable,
        "unpaid_absence_days": calc.get("unpaid_absence_days") if current else None,
        "daily_rate": calc.get("daily_rate") if current else None,
        "sunday_worked_days": calc.get("sunday_worked_days") if current else None,
        # Employment window (current lines only); lets reports show joiners/leavers.
        "joining_date": calc.get("joining_date") if current else None,
        "exit_date": calc.get("exit_date") if current else None,
        "window_start": calc.get("window_start") if current else None,
        "window_end": calc.get("window_end") if current else None,
        "restricted": bool(calc.get("employment_restricted")) if current else False,
        "entitled_working_days": calc.get("entitled_working_days") if current else None,
    }


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
    """Aggregate daily attendance rows.

    ``present_days`` keeps the historical row-based count. ``working_present_days``
    is the Sunday-aware figure used by monthly payroll: one weight per distinct
    date (a day is never counted twice), Sunday dates excluded and reported
    separately as ``sunday_present_days``.
    """
    present_days = 0
    total_hours = 0.0
    ot_hours = 0.0
    present_dates: set[str] = set()
    date_weight: dict[str, float] = {}
    for row in attendance_rows:
        status = (row.get("status") or "Present").strip()
        status_lower = status.lower()
        if status_lower in ("present", "half day", "half-day"):
            weight = 1.0 if status_lower == "present" else 0.5
            present_days += 1 if status_lower == "present" else 0.5
            att_date = row.get("attendance_date")
            if att_date:
                key = str(att_date)[:10]
                present_dates.add(key)
                date_weight[key] = max(date_weight.get(key, 0.0), weight)
        total_hours += float(row.get("total_hours") or 0)
        ot_hours += float(row.get("ot_hours") or 0)
    sunday_present = sum(w for d, w in date_weight.items() if is_sunday(d))
    working_present = sum(w for d, w in date_weight.items() if not is_sunday(d))
    return {
        "present_days": present_days,
        "working_present_days": working_present,
        "sunday_present_days": sunday_present,
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


class PayrollAttendanceError(ValueError):
    """Attendance cannot establish payable days for the employment window."""


def _summary_window_issue(summary: dict, window: dict, staff_row: dict) -> str | None:
    """Why a monthly-summary entry cannot be trusted for a restricted window, or None.

    A monthly entry is only totals, so it cannot say *which* days were worked. It is
    accepted for a partial-period employee only when it explicitly accounts for the
    employment window: worked + half + absent days must equal the window's working
    days (or its calendar days, the Sunday-inclusive convention already allowed for
    monthly entries). Otherwise the entry plainly covers days outside the window and
    we refuse to guess how its absences should be split.
    """
    entered = round(
        float(summary.get("worked_days") or 0)
        + float(summary.get("half_days") or 0)
        + float(summary.get("absent_days") or 0),
        2,
    )
    if entered in (float(window["working_days"]), float(window["calendar_days"])):
        return None
    who = staff_row.get("staff_name") or staff_row.get("employee_code") or f"staff #{staff_row.get('id')}"
    return (
        f"{who}: the monthly attendance entry totals {entered:g} days (worked + half + absent) but "
        f"employment in this period runs {window['window_start']} to {window['window_end']} "
        f"({window['working_days']} working days, {window['calendar_days']} calendar days). "
        "Enter dated attendance for those dates, or correct the monthly entry so it covers only "
        f"that range ({window['working_days']} days, or {window['calendar_days']} counting Sundays)."
    )


def _monthly_attendance_basis(db, staff_row: dict, start: str, end: str, window: dict | None) -> dict:
    """Pick the attendance source for a monthly-salaried employee.

    * Unrestricted window: existing precedence (monthly summary, else dated rows).
    * Restricted window (joined or left inside the period): a monthly summary is used
      only if it validates against the window; otherwise dated attendance inside the
      window is used; otherwise ``PayrollAttendanceError`` explains what is needed.
    Nothing is ever guessed.
    """
    summary = _fetch_monthly_attendance_summary(db, staff_row["id"], start, end)
    restricted = bool(window and window["restricted"])
    if not restricted:
        if summary:
            return {"summary": summary, "rows": []}
        return {"summary": None, "rows": fetch_attendance_for_employee(db, "staff", staff_row["id"], start, end)}
    if window["working_days"] == 0 and not window.get("window_start"):
        return {"summary": None, "rows": []}  # not employed at all in this period: nothing payable
    issue = None
    if summary:
        issue = _summary_window_issue(summary, window, staff_row)
        if issue is None:
            return {"summary": summary, "rows": []}
    rows = [
        r
        for r in fetch_attendance_for_employee(db, "staff", staff_row["id"], start, end)
        if in_window(r.get("attendance_date"), window)
    ]
    if rows:
        return {"summary": None, "rows": rows}
    if issue:
        raise PayrollAttendanceError(issue)
    return {"summary": None, "rows": []}


def validate_monthly_attendance_basis(db, staff_rows: list[dict], start: str, end: str) -> list[str]:
    """Problems that would stop monthly staff being calculated; empty list when fine."""
    problems: list[str] = []
    for row in staff_rows:
        if (row.get("salary_type") or "Monthly").strip() != "Monthly":
            continue
        window = employment_window(row.get("joining_date"), row.get("exit_date"), start, end)
        try:
            _monthly_attendance_basis(db, row, start, end, window)
        except PayrollAttendanceError as exc:
            problems.append(str(exc))
    return problems


def calculate_monthly_staff_pay(
    db,
    staff_row: dict,
    start: str,
    end: str,
    holidays: list[dict] | None = None,
) -> dict:
    """Monthly staff pay for a payroll period.

    Rule (see ``payroll_calc``): working days = calendar days - Sundays;
    daily rate = monthly salary / working days; payable salary = daily rate x
    payable working days. Sundays are never unpaid absences. OT, statutory
    deductions, holiday pay, travel allowance and advances keep their existing
    rules; only the day basis they pro-rate on has changed.
    """
    staff_id = staff_row["id"]
    components = _fetch_staff_salary_components(db, staff_id)
    monthly_salary = _effective_monthly_salary(staff_row, components)
    ot_applicable = (staff_row.get("ot_applicable") or "No") == "Yes"
    ot_rate = float(staff_row.get("ot_rate_per_hour") or 0)
    holiday_pay = (staff_row.get("holiday_pay_applicable") or "No") == "Yes"
    counts = period_day_counts(start, end)
    working_days = counts["working_days"]
    # Employment window: joining date .. exit date (either may be missing), inclusive.
    # The divisor stays the FULL period's working days; the window only limits how
    # many days can be payable. Staff employed for the whole period are unrestricted
    # and are calculated exactly as before.
    window = employment_window(staff_row.get("joining_date"), staff_row.get("exit_date"), start, end)
    restricted = bool(window and window["restricted"])
    entitled_working_days = window["working_days"] if window else working_days
    # A holiday on a Sunday is already a non-working day: never pay it twice.
    holiday_dates = {
        str(h["holiday_date"])[:10]
        for h in (holidays or [])
        if not is_sunday(h["holiday_date"]) and (not restricted or in_window(h["holiday_date"], window))
    }
    basis = _monthly_attendance_basis(db, staff_row, start, end, window)
    monthly_summary = basis["summary"]
    sunday_worked_days = 0.0
    recorded_absent_days = None
    if monthly_summary:
        # Monthly summary entries already account for holidays (existing rule).
        # For a restricted window the entry has been validated as an explicit
        # in-window entry, so its figures are used as entered - never re-assigned.
        recorded_absent_days = float(monthly_summary.get("absent_days") or 0)
        resolved = resolve_payable_days(
            entitled_working_days,
            present_days=monthly_summary["present_days"],
            recorded_absent_days=recorded_absent_days,
            half_days=monthly_summary.get("half_days") or 0,
        )
        ot_hours = float(monthly_summary["ot_hours"] or 0)
    else:
        # Dated attendance. Rows before joining / after exit earn neither days nor
        # overtime; Sunday overtime inside the window is kept (Sundays add no
        # payable day, but their OT hours are still summed).
        att_summary = summarize_attendance(basis["rows"])
        sunday_worked_days = float(att_summary["sunday_present_days"])
        paid_holidays = 0
        if holiday_pay and holiday_dates:
            paid_holidays = _count_unworked_holidays(
                holiday_dates, att_summary["present_dates"]
            )
        resolved = resolve_payable_days(
            entitled_working_days,
            present_days=att_summary["working_present_days"],
            paid_holiday_days=paid_holidays,
        )
        ot_hours = float(att_summary["ot_hours"])

    breakdown = monthly_pay_breakdown(
        monthly_salary,
        start=start,
        end=end,
        payable_days=resolved["payable_days"],
        paid_holiday_days=resolved["paid_holiday_days"],
    )
    ot_amount = round_money(ot_hours * ot_rate) if ot_applicable else 0.0
    travel_allowance = 0.0
    if resolved["payable_days"] > 0:
        travel_allowance = prorate_by_working_days(
            _travel_allowance_for_staff(db, staff_id, staff_row, end),
            resolved["payable_days"],
            working_days,
        )
    gross_before_deductions = round_money(
        breakdown["earned_base"] + ot_amount + breakdown["holiday_pay"] + travel_allowance
    )
    deductions = _staff_statutory_deductions(staff_row, components, gross_before_deductions)
    net = round_money(max(gross_before_deductions - deductions, 0))
    return {
        "calc_basis": CALC_BASIS,
        "base_salary": monthly_salary,
        "calendar_days": counts["calendar_days"],
        "sundays": counts["sundays"],
        "working_days": working_days,
        "joining_date": window["joining_date"] if window else None,
        "exit_date": window["exit_date"] if window else None,
        "window_start": window["window_start"] if window else None,
        "window_end": window["window_end"] if window else None,
        "employment_restricted": restricted,
        "entitled_working_days": entitled_working_days,
        "not_employed_days": working_days - entitled_working_days,
        "present_days": resolved["worked_working_days"],
        "payable_days": resolved["payable_days"],
        "unpaid_absence_days": resolved["unpaid_absence_days"],
        "leave_days": resolved["unpaid_absence_days"],
        "recorded_absent_days": recorded_absent_days,
        "sunday_worked_days": sunday_worked_days,
        "daily_rate": breakdown["daily_rate"],
        "earned_base": breakdown["earned_base"],
        "attendance_source": monthly_summary.get("source") if monthly_summary else "daily",
        "ot_hours": ot_hours,
        "ot_amount": ot_amount,
        "holiday_pay": breakdown["holiday_pay"],
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


def serialize_eligible_employee(emp: dict, *, overlap: list[dict] | None = None) -> dict:
    """JSON-safe selector row.

    ``selectable`` is False (with a human ``blocked_reason``) when the employee is
    listed for visibility but cannot be put into a run for the period: no
    attendance/timesheet data, or payroll already exists for an overlapping period.
    """
    et = emp["employee_type"]
    if et == "staff":
        type_label = "Monthly Staff" if (emp.get("salary_type") or "Monthly") == "Monthly" else "Daily Staff"
    elif et == "company_worker":
        type_label = "Company Worker"
    else:
        type_label = "Sub Contractor"
    blocked_reason = ""
    if overlap:
        first = overlap[0]
        blocked_reason = (
            f"Payroll already exists: {first.get('run_ref') or 'Run #' + str(first.get('run_id'))} "
            f"({first.get('run_status') or 'Draft'})"
        )
    elif emp.get("has_period_data") is False:
        blocked_reason = "No attendance or timesheet data for this period"
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
        "selectable": not blocked_reason,
        "blocked_reason": blocked_reason,
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


def _active_status_sql(column: str = "status") -> str:
    """Case/space-insensitive 'Active' test; blank or NULL status counts as Active."""
    return f"LOWER(COALESCE(NULLIF(TRIM({column}), ''), 'Active')) = 'active'"


def _norm_text(value) -> str:
    return " ".join(str(value or "").split()).lower()


def _dedupe_employees(employees: list[dict]) -> list[dict]:
    """Show each person once.

    The same person recorded in both ``staff`` and ``workers`` (same code AND name,
    ignoring case/spacing) collapses to the first record, staff first. Records with
    a blank code or name are never merged.
    """
    seen: set[tuple] = set()
    unique: list[dict] = []
    for emp in employees:
        code = _norm_text(emp.get("employee_code"))
        name = _norm_text(emp.get("employee_name"))
        key = (
            ("person", code, name)
            if code and name
            else (emp["employee_type"], emp["employee_id"])
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(emp)
    return unique


def list_eligible_employees(
    db,
    employee_type: str | None,
    project_id: int | None = None,
    department: str | None = None,
    employee_ids: list[int] | None = None,
    *,
    period_start: str | None = None,
    period_end: str | None = None,
    include_without_data: bool = False,
) -> list[dict]:
    """Active employees eligible for a payroll category, each listed exactly once.

    By default employees with no attendance/monthly-summary/timesheet data for the
    period are dropped (payroll generation needs data). With
    ``include_without_data=True`` they stay in the list flagged
    ``has_period_data=False`` so a missing person is explained, not invisible.
    """
    results = []
    if employee_type == "company_staff":
        types = ["staff", "company_worker"]
    elif employee_type in EMPLOYEE_TYPES:
        types = [employee_type]
    else:
        types = list(EMPLOYEE_TYPES)

    if "staff" in types and _table_exists(db, "staff"):
        params: list = []
        if period_start and "exit_date" in _table_columns(db, "staff"):
            # Staff with an exit date are judged by that date, not by current status:
            # someone who left during (or after) the period still gets that payroll,
            # even if now marked Inactive. Someone who left before it does not.
            # Staff without an exit date keep the original Active-only rule.
            blank_exit = "(s.exit_date IS NULL OR TRIM(s.exit_date) = '')"
            where = (
                f"(({_active_status_sql('s.status')} AND {blank_exit}) "
                f"OR (NOT {blank_exit} AND SUBSTR(TRIM(s.exit_date), 1, 10) >= ?))"
            )
            params.append(period_start)
        else:
            where = _active_status_sql("s.status")
        query = (
            "SELECT s.*, s.staff_name AS employee_name, s.employee_code AS employee_code "
            f"FROM staff s WHERE {where}"
        )
        if department and "department" in _table_columns(db, "staff"):
            query += " AND s.department=?"
            params.append(department)
        if employee_ids:
            query += f" AND s.id IN ({','.join('?' * len(employee_ids))})"
            params.extend(employee_ids)
        query += " ORDER BY s.staff_name"
        for row in db.execute(query, params).fetchall():
            item = dict(row)
            item["employee_type"] = "staff"
            item["employee_id"] = item["id"]
            results.append(item)

    worker_types = [t for t in types if t in ("company_worker", "subcontractor")]
    if worker_types and _table_exists(db, "workers"):
        query = (
            "SELECT w.*, w.worker_name AS employee_name, w.worker_code AS employee_code "
            f"FROM workers w WHERE {_active_status_sql('w.status')}"
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

    results = _dedupe_employees(results)
    results.sort(
        key=lambda e: (_norm_text(e.get("employee_name")), _norm_text(e.get("employee_code")))
    )

    if period_start and period_end:
        for emp in results:
            emp["has_period_data"] = employee_has_period_data(
                db, emp["employee_type"], emp["employee_id"], period_start, period_end
            )
        if not include_without_data:
            results = [emp for emp in results if emp["has_period_data"]]
    return results


# ---------------------------------------------------------------------------
# Duplicate prevention
# ---------------------------------------------------------------------------


def payroll_overlap_index(
    db, period_start: str, period_end: str
) -> dict[tuple[str, int], list[dict]]:
    """Existing payroll lines whose run overlaps the period, keyed (type, employee id)."""
    index: dict[tuple[str, int], list[dict]] = {}
    if not period_start or not period_end:
        return index
    if not _table_exists(db, "payroll_lines") or not _table_exists(db, "payroll_runs"):
        return index
    pr_cols = _table_columns(db, "payroll_runs")
    pl_cols = _table_columns(db, "payroll_lines")
    name_sql = "pl.employee_name" if "employee_name" in pl_cols else "NULL"
    code_sql = "pl.employee_code" if "employee_code" in pl_cols else "NULL"
    ref_sql = "pr.run_ref" if "run_ref" in pr_cols else "NULL"
    start_ym = period_start[:7]
    end_ym = period_end[:7]
    clauses = []
    params: list = []
    if "period_start" in pr_cols and "period_end" in pr_cols:
        clauses.append("(pr.period_start <= ? AND pr.period_end >= ?)")
        params.extend([period_end, period_start])
    if "month" in pr_cols and "year" in pr_cols:
        clauses.append(
            "(pr.month IS NOT NULL AND pr.year IS NOT NULL AND "
            "printf('%04d-%02d', pr.year, pr.month) BETWEEN ? AND ?)"
        )
        params.extend([start_ym, end_ym])
    if not clauses:
        return index
    rows = db.execute(
        "SELECT pl.id AS line_id, pl.payroll_run_id AS run_id, pl.employee_type, "
        f"pl.staff_id, pl.worker_id, {name_sql} AS employee_name, {code_sql} AS employee_code, "
        f"{ref_sql} AS run_ref, pr.status AS run_status "
        "FROM payroll_lines pl JOIN payroll_runs pr ON pl.payroll_run_id = pr.id "
        f"WHERE {' OR '.join(clauses)} ORDER BY pr.id DESC, pl.id DESC",
        params,
    ).fetchall()
    for raw in rows:
        row = dict(raw)
        emp_id = row["staff_id"] if row["employee_type"] == "staff" else row["worker_id"]
        if not emp_id:
            continue
        index.setdefault((row["employee_type"], int(emp_id)), []).append(row)
    return index


def ensure_no_payroll_overlap(
    db, employees: list[tuple[str, int]], period_start: str, period_end: str
) -> None:
    """Raise ``ValueError`` if any employee already has payroll for an overlapping period.

    Existing payroll is never modified or removed here: payroll history is kept,
    and a draft run must be deleted explicitly before the period can be re-run.
    """
    index = payroll_overlap_index(db, period_start, period_end)
    clashes = []
    seen: set[tuple[str, int]] = set()
    for key in employees:
        key = (key[0], int(key[1]))
        if key in seen:
            continue
        seen.add(key)
        hits = index.get(key)
        if hits:
            first = hits[0]
            label = first.get("employee_name") or first.get("employee_code") or f"{key[0]} #{key[1]}"
            clashes.append(
                f"{label} ({first.get('run_ref') or 'Run #' + str(first.get('run_id'))}, "
                f"{first.get('run_status') or 'Draft'})"
            )
    if clashes:
        shown = "; ".join(clashes[:8])
        more = f" and {len(clashes) - 8} more" if len(clashes) > 8 else ""
        raise ValueError(
            "Payroll already exists for this period: "
            f"{shown}{more}. Deselect them, or delete the draft run first to regenerate."
        )


# ---------------------------------------------------------------------------
# Selector diagnostics
# ---------------------------------------------------------------------------


def ensure_attendance_covers_employment(db, staff_rows: list[dict], period_start: str, period_end: str) -> None:
    """Raise ``ValueError`` (before any run is created) if monthly attendance can't
    establish payable days inside someone's joining/exit window."""
    problems = validate_monthly_attendance_basis(db, staff_rows, period_start, period_end)
    if problems:
        shown = " | ".join(problems[:5])
        more = f" (+{len(problems) - 5} more)" if len(problems) > 5 else ""
        raise ValueError(f"Attendance does not match employment dates - {shown}{more}")


def ensure_staff_not_departed(db, employees: list[tuple[str, int]], period_start: str) -> None:
    """Refuse payroll for staff whose exit date is before the period starts.

    Selection by explicit id bypasses ``list_eligible_employees``, so the same
    rule is enforced here. Staff without an exit date are never affected.
    """
    ids = [int(eid) for et, eid in employees if et == "staff"]
    if not ids or not period_start or "exit_date" not in _table_columns(db, "staff"):
        return
    rows = db.execute(
        "SELECT staff_name, employee_code, exit_date FROM staff "
        f"WHERE id IN ({','.join('?' * len(ids))}) "
        "AND exit_date IS NOT NULL AND TRIM(exit_date) <> '' "
        "AND SUBSTR(TRIM(exit_date), 1, 10) < ?",
        [*ids, period_start],
    ).fetchall()
    if rows:
        who = "; ".join(
            f"{r['staff_name'] or r['employee_code']} (left {str(r['exit_date'])[:10]})" for r in rows[:8]
        )
        raise ValueError(
            f"Cannot generate payroll for staff who left before this period: {who}. Deselect them."
        )


def explain_payroll_eligibility(
    db,
    query: str,
    *,
    employment_category: str = "company_staff",
    period_start: str | None = None,
    period_end: str | None = None,
) -> list[dict]:
    """Explain, record by record, why a person is or is not in the payroll selector.

    Mirrors ``list_eligible_employees`` check for check, so the answer cannot drift
    from the real filters. Read-only.
    """
    needle = (query or "").strip()
    if len(needle) < 2:
        return []
    like = f"%{needle}%"
    category_types = {
        "company_staff": {"staff", "company_worker"},
        "subcontractor": {"subcontractor"},
    }.get(employment_category, set(EMPLOYEE_TYPES))
    listed = {
        (e["employee_type"], e["employee_id"])
        for e in list_eligible_employees(
            db,
            employment_category if employment_category in PAYROLL_EMPLOYMENT_CATEGORIES else None,
            period_start=period_start,
            period_end=period_end,
            include_without_data=True,
        )
    }
    overlaps = (
        payroll_overlap_index(db, period_start, period_end)
        if period_start and period_end
        else {}
    )
    matches: list[dict] = []
    if _table_exists(db, "staff"):
        for row in db.execute(
            "SELECT * FROM staff WHERE staff_name LIKE ? OR employee_code LIKE ? "
            "ORDER BY staff_name LIMIT 20",
            (like, like),
        ).fetchall():
            item = dict(row)
            item.update(
                employee_type="staff",
                employee_id=item["id"],
                employee_name=item.get("staff_name"),
                employee_code=item.get("employee_code"),
            )
            matches.append(item)
    if _table_exists(db, "workers"):
        for row in db.execute(
            "SELECT * FROM workers WHERE worker_name LIKE ? OR worker_code LIKE ? "
            "ORDER BY worker_name LIMIT 20",
            (like, like),
        ).fetchall():
            item = dict(row)
            cat = (item.get("worker_category") or "Company Staff").strip()
            item.update(
                employee_type="subcontractor" if cat == "Sub Contractor Staff" else "company_worker",
                employee_id=item["id"],
                employee_name=item.get("worker_name"),
                employee_code=item.get("worker_code"),
            )
            matches.append(item)

    report = []
    for emp in matches:
        et = emp["employee_type"]
        key = (et, emp["employee_id"])
        reasons: list[str] = []  # why the person is not listed at all
        blocked: list[str] = []  # why a listed person cannot be selected
        checks: list[dict] = []

        raw_status = emp.get("status")
        is_active = _norm_text(raw_status or "Active") == "active"
        exit_raw = str(emp.get("exit_date") or "").strip()[:10] if et == "staff" else ""
        if exit_raw and period_start:
            # Same rule as list_eligible_employees: an exit date overrides status.
            left_before = exit_raw < period_start
            checks.append({
                "check": "Exit date is not before the period",
                "ok": not left_before,
                "detail": f"exit date = {exit_raw}; status = {raw_status!r} (ignored when an exit date is set)",
            })
            if left_before:
                reasons.append(f"Exit date {exit_raw} is before the period starts ({period_start}).")
        else:
            checks.append({
                "check": "Status is Active",
                "ok": is_active,
                "detail": f"status = {raw_status!r}",
            })
            if not is_active:
                reasons.append(f"Status is {raw_status!r}, not Active.")

        in_category = et in category_types
        checks.append({
            "check": "Employment category matches",
            "ok": in_category,
            "detail": f"record is {payroll_employment_filter(et) or et}; selector is {employment_category}",
        })
        if not in_category:
            reasons.append(
                f"Record is {payroll_employment_filter(et) or et}, "
                f"but the selector is set to {employment_category}."
            )

        if period_start and period_end:
            has_data = employee_has_period_data(db, et, emp["employee_id"], period_start, period_end)
            checks.append({
                "check": "Attendance / timesheet data in period",
                "ok": has_data,
                "detail": f"{period_start} to {period_end}",
            })
            if not has_data:
                blocked.append("No attendance, monthly summary or timesheet data in the period.")
            hits = overlaps.get(key)
            checks.append({
                "check": "Not already in a payroll run for the period",
                "ok": not hits,
                "detail": (hits[0].get("run_ref") or f"Run #{hits[0].get('run_id')}") if hits else "",
            })
            if hits:
                blocked.append(
                    f"Already in {hits[0].get('run_ref') or 'Run #' + str(hits[0].get('run_id'))} "
                    f"({hits[0].get('run_status')})."
                )
        salary = float(emp.get("salary_amount") or 0)
        checks.append({
            "check": "Salary configured",
            "ok": salary > 0,
            "detail": f"{emp.get('salary_type') or '-'} {salary:g}",
        })
        if "company_id" in emp or "customer_id" in emp:
            checks.append({
                "check": "Company association (informational)",
                "ok": True,
                "detail": (
                    f"customer_id={emp.get('customer_id')!r}, company_id={emp.get('company_id')!r}"
                    " - not used by the payroll selector"
                ),
            })
        is_listed = key in listed
        if not is_listed and not reasons:
            reasons.append(
                "Hidden as a duplicate of another record with the same code and name."
            )
        report.append({
            "employee_type": et,
            "employee_id": emp["employee_id"],
            "employee_name": emp.get("employee_name") or "",
            "employee_code": emp.get("employee_code") or "",
            "listed": is_listed,
            "selectable": is_listed and not blocked,
            "reasons": reasons + blocked,
            "checks": checks,
        })
    return report


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
    ensure_no_payroll_overlap(
        db,
        [(e["employee_type"], e["employee_id"]) for e in employees],
        period_start,
        period_end,
    )
    ensure_attendance_covers_employment(
        db, [e for e in employees if e["employee_type"] == "staff"], period_start, period_end
    )

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
    """Register/export rows: stored line values plus the shared day-basis figures."""
    rows = fetch_payroll_lines(db, run_id=run_id)
    for row in rows:
        basis = line_day_basis(row)
        row["working_days"] = basis["working_days"]
        row["payable_days"] = basis["payable_days"]
        row["daily_rate"] = basis["daily_rate"]
        row["calc_basis"] = "Working days excl. Sundays" if not basis["legacy"] else "Legacy (calendar days)"
        row["exit_date"] = basis["exit_date"] or ""
        row["employed_from"] = basis["window_start"] or ""
        row["employed_to"] = basis["window_end"] or ""
    return rows


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


# ---------------------------------------------------------------------------
# Payroll dashboard
# ---------------------------------------------------------------------------

DASHBOARD_STATUS_LABELS = {
    "not_generated": "Not generated",
    "no_data": "No attendance",
    "draft": "Draft",
    "in_approval": "In approval",
    "approved": "Approved",
    "paid": "Paid",
}
DASHBOARD_STATUS_FILTERS = tuple(DASHBOARD_STATUS_LABELS)
DASHBOARD_PAGE_SIZES = (10, 25, 50, 100)
_PROGRESS_ORDER = ("draft", "in_approval", "approved", "paid")


def _line_status_key(run_status: str | None, payment_status: str | None) -> str:
    status = (run_status or "Draft").strip()
    pay = (payment_status or "Pending").strip()
    if status == "Paid" or pay == "Paid":
        return "paid"
    if status == "Approved":
        return "approved"
    if status in ("Pending Verification", "Pending Checker", "Pending Approval"):
        return "in_approval"
    return "draft"


def _period_lines(db, period_start: str, period_end: str, year: int, month: int) -> dict[tuple, dict]:
    """Latest payroll line per employee for the month (history is never merged away)."""
    out: dict[tuple, dict] = {}
    if not _table_exists(db, "payroll_lines") or not _table_exists(db, "payroll_runs"):
        return out
    pr_cols = _table_columns(db, "payroll_runs")
    clauses, params = [], []
    if "period_start" in pr_cols and "period_end" in pr_cols:
        clauses.append("(pr.period_start <= ? AND pr.period_end >= ?)")
        params.extend([period_end, period_start])
    if "month" in pr_cols and "year" in pr_cols:
        clauses.append("(pr.year = ? AND pr.month = ?)")
        params.extend([year, month])
    if not clauses:
        return out
    ref_sql = "pr.run_ref" if "run_ref" in pr_cols else "NULL"
    rows = db.execute(
        f"SELECT pl.*, {ref_sql} AS run_ref, pr.status AS run_status "
        "FROM payroll_lines pl JOIN payroll_runs pr ON pl.payroll_run_id = pr.id "
        f"WHERE {' OR '.join(clauses)} ORDER BY pr.id DESC, pl.id DESC",
        params,
    ).fetchall()
    for raw in rows:
        line = dict(raw)
        emp_id = line.get("staff_id") if line.get("employee_type") == "staff" else line.get("worker_id")
        if not emp_id:
            continue
        out.setdefault((line["employee_type"], int(emp_id)), line)
    return out


def _dashboard_row(emp: dict | None, line: dict | None, day_counts: dict) -> dict:
    et = (emp or line or {}).get("employee_type")
    if line:
        calc = parse_calc_snapshot(line.get("calc_snapshot"))
        line["calc"] = calc
        basis = line_day_basis(line)
        gross = float(line.get("gross_salary") or 0)
        deductions = float(line.get("deductions") or 0) + float(line.get("advance_deduction") or 0)
        net = float(line.get("net_salary") or 0)
        status = _line_status_key(line.get("run_status"), line.get("payment_status"))
        salary_type = line.get("salary_type") or (emp or {}).get("salary_type") or "Monthly"
        return {
            "employee_type": et,
            "employee_id": (emp or {}).get("employee_id")
            or (line.get("staff_id") if et == "staff" else line.get("worker_id")),
            "code": line.get("employee_code") or (emp or {}).get("employee_code") or "",
            "name": line.get("employee_name") or (emp or {}).get("employee_name") or "",
            "department": line.get("department") or (emp or {}).get("department") or "",
            "salary_type": salary_type,
            "monthly_salary": float(line.get("base_salary") or 0),
            "working_days": basis["working_days"],
            "payable_days": basis["payable_days"],
            "exit_date": basis["exit_date"],
            "legacy": basis["legacy"],
            "gross": gross,
            "deductions": deductions,
            "net": net,
            "status": status,
            "status_label": DASHBOARD_STATUS_LABELS[status],
            "run_id": line.get("payroll_run_id"),
            "run_ref": line.get("run_ref"),
            "line_id": line.get("id"),
            "blocked_reason": "",
        }
    emp = emp or {}
    has_data = emp.get("has_period_data", True)
    salary_type = emp.get("salary_type") or ("Monthly" if et == "staff" else "Daily")
    status = "not_generated" if has_data else "no_data"
    return {
        "employee_type": et,
        "employee_id": emp.get("employee_id"),
        "code": emp.get("employee_code") or "",
        "name": emp.get("employee_name") or "",
        "department": emp.get("department") or "",
        "salary_type": salary_type,
        "monthly_salary": float(emp.get("salary_amount") or 0),
        "working_days": day_counts["working_days"] if salary_type == "Monthly" else None,
        "payable_days": None,
        "legacy": False,
        "gross": None,
        "deductions": None,
        "net": None,
        "status": status,
        "status_label": DASHBOARD_STATUS_LABELS[status],
        "run_id": None,
        "run_ref": None,
        "line_id": None,
        "blocked_reason": "" if has_data else "No attendance or timesheet data for this month",
    }


def _month_status(rows: list[dict]) -> dict:
    """One status for the whole month, from the weakest generated line."""
    generated = [r for r in rows if r["status"] in _PROGRESS_ORDER]
    pending = [r for r in rows if r["status"] == "not_generated"]
    if not generated:
        return {"key": "not_started", "label": "Not started", "tone": "muted"}
    weakest = min(generated, key=lambda r: _PROGRESS_ORDER.index(r["status"]))["status"]
    label = DASHBOARD_STATUS_LABELS[weakest]
    if pending:
        return {"key": "partial", "label": f"Partially generated · {label}", "tone": "warn"}
    tone = {"draft": "warn", "in_approval": "info", "approved": "info", "paid": "ok"}[weakest]
    return {"key": weakest, "label": label, "tone": tone}


def build_payroll_dashboard(
    db,
    *,
    month: int,
    year: int,
    query: str = "",
    category: str = "",
    status: str = "",
    department: str = "",
    page: int = 1,
    per_page: int = 25,
) -> dict:
    """Everything the payroll dashboard shows for one month, one page of rows at a time.

    Summary cards and the month status cover the whole scope (category + department)
    so searching or paging never changes the totals.
    """
    period_start, period_end = period_from_month_year(month, year)
    day_counts = period_day_counts(period_start, period_end)
    category = category if category in PAYROLL_EMPLOYMENT_CATEGORIES else ""
    employees = list_eligible_employees(
        db,
        category or None,
        department=department or None,
        period_start=period_start,
        period_end=period_end,
        include_without_data=True,
    )
    lines = _period_lines(db, period_start, period_end, year, month)

    rows: list[dict] = []
    used: set[tuple] = set()
    for emp in employees:
        key = (emp["employee_type"], emp["employee_id"])
        line = lines.get(key)
        if line:
            used.add(key)
        rows.append(_dashboard_row(emp, line, day_counts))
    for key, line in lines.items():  # paid-before-deactivation etc.: keep the history visible
        if key in used:
            continue
        if category and payroll_employment_filter(key[0]) != category:
            continue
        if department and (line.get("department") or "") != department:
            continue
        rows.append(_dashboard_row(None, line, day_counts))
    rows.sort(key=lambda r: (_norm_text(r["name"]), _norm_text(r["code"])))

    generated = [r for r in rows if r["status"] in _PROGRESS_ORDER]
    summary = {
        "staff_count": len(rows),
        "generated_count": len(generated),
        "gross": round_money(sum(r["gross"] or 0 for r in generated)),
        "deductions": round_money(sum(r["deductions"] or 0 for r in generated)),
        "net": round_money(sum(r["net"] or 0 for r in generated)),
        "net_unpaid": round_money(sum(r["net"] or 0 for r in generated if r["status"] != "paid")),
        "not_generated": sum(1 for r in rows if r["status"] == "not_generated"),
        "no_data": sum(1 for r in rows if r["status"] == "no_data"),
    }
    month_status = _month_status(rows)

    needle = _norm_text(query)
    filtered = rows
    if needle:
        filtered = [
            r for r in filtered
            if needle in _norm_text(r["name"])
            or needle in _norm_text(r["code"])
            or needle in _norm_text(r["department"])
        ]
    if status in DASHBOARD_STATUS_FILTERS:
        filtered = [r for r in filtered if r["status"] == status]

    per_page = per_page if per_page in DASHBOARD_PAGE_SIZES else 25
    total = len(filtered)
    pages = max((total + per_page - 1) // per_page, 1)
    page = min(max(page, 1), pages)
    first = (page - 1) * per_page
    return {
        "month": month,
        "year": year,
        "month_label": format_year_month_label(f"{year:04d}-{month:02d}"),
        "period_start": period_start,
        "period_end": period_end,
        "day_counts": day_counts,
        "summary": summary,
        "month_status": month_status,
        "rows": filtered[first:first + per_page],
        "total": total,
        "scope_total": len(rows),
        "page": page,
        "pages": pages,
        "per_page": per_page,
        "first_index": first + 1 if total else 0,
        "last_index": min(first + per_page, total),
        "status_counts": {
            key: sum(1 for r in rows if r["status"] == key) for key in DASHBOARD_STATUS_FILTERS
        },
    }


def fetch_payroll_runs_page(db, *, page: int = 1, per_page: int = 10) -> dict:
    """Paginated payroll run history (newest first), with employee summaries."""
    if not _table_exists(db, "payroll_runs"):
        return {"runs": [], "total": 0, "page": 1, "pages": 1, "per_page": per_page}
    total = db.execute("SELECT COUNT(*) FROM payroll_runs").fetchone()[0]
    pages = max((total + per_page - 1) // per_page, 1)
    page = min(max(page, 1), pages)
    runs = [
        dict(r)
        for r in db.execute(
            "SELECT pr.*, p.project_name FROM payroll_runs pr "
            "LEFT JOIN projects p ON pr.project_id = p.id "
            "ORDER BY pr.id DESC LIMIT ? OFFSET ?",
            (per_page, (page - 1) * per_page),
        ).fetchall()
    ]
    attach_run_employee_summaries(db, runs)
    return {"runs": runs, "total": total, "page": page, "pages": pages, "per_page": per_page}
