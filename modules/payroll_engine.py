"""Attendance auto-logic and payroll calculation for MAXEK ERP."""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta

import pandas as pd

from modules.database import (
    DATE_FMT,
    get_conn,
    get_employee,
    load_active_holidays,
    load_weekly_off_rules,
)

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ATTENDANCE_STATUSES = ["Present", "Absent", "Leave", "Half Day"]
PAYROLL_STAFF_TYPES = {"Monthly Staff", "Daily Wage Staff", "Company Staff"}
from modules.approval_workflow import WORKFLOW_STATUSES

PAYROLL_WORKFLOW_STATUSES = WORKFLOW_STATUSES + ("Rejected", "Sent Back")
PAYMENT_MODES = ("Cash", "Bank Transfer", "UPI", "Cheque")
PAYMENT_STATUSES = ("Pending", "Paid")


def normalize_employee_type(employee_type):
    text = (employee_type or "").strip()
    if text == "Company Staff":
        return "Monthly Staff"
    return text


def is_payroll_staff(employee_type):
    text = (employee_type or "").strip()
    return text in PAYROLL_STAFF_TYPES or normalize_employee_type(text) in {"Monthly Staff", "Daily Wage Staff"}


def is_monthly_staff(employee_type):
    return normalize_employee_type(employee_type) == "Monthly Staff"


def is_daily_staff(employee_type):
    return normalize_employee_type(employee_type) == "Daily Wage Staff"


def _employee_applicable_for(employee):
    if (employee.get("employee_type") or "").strip() == "Sub Contractor Worker":
        return "Sub Contractor Workers"
    return "Company Staff"


def _month_date_range(payroll_month):
    month, year = payroll_month.split("/")
    month_i, year_i = int(month), int(year)
    days_in_month = calendar.monthrange(year_i, month_i)[1]
    start = datetime.strptime(f"01/{month}/{year}", DATE_FMT)
    end = start + timedelta(days=days_in_month)
    return start, end, days_in_month


def _employee_weekly_off_day(employee):
    day = (employee.get("weekly_off_day") or "").strip()
    if day:
        return day
    applicable = _employee_applicable_for(employee)
    project = employee.get("project_name") or ""
    rules = load_weekly_off_rules(applicable, project)
    if not rules.empty:
        return str(rules.iloc[0]["weekly_off_day"]).strip()
    return "Sunday"


def _holiday_on_date(date_str, applicable_for, project_name):
    df = load_active_holidays(date_str, applicable_for, project_name)
    if df.empty:
        return None
    row = df.iloc[0]
    return {
        "holiday_name": row.get("holiday_name") or "",
        "payment_type": (row.get("payment_type") or "Paid").strip(),
    }


def _is_paid_weekly_off(employee, weekday_name):
    applicable = _employee_applicable_for(employee)
    project = employee.get("project_name") or ""
    rules = load_weekly_off_rules(applicable, project)
    if rules.empty:
        return weekday_name == _employee_weekly_off_day(employee)
    match = rules[rules["weekly_off_day"] == weekday_name]
    if match.empty:
        return False
    return str(match.iloc[0].get("payment_type", "")).strip().lower() == "paid"


def _paid_holiday_eligible(employee):
    return (employee.get("paid_holiday_eligibility") or "Yes").strip().lower() == "yes"


def _ot_payable(employee):
    return (employee.get("ot_applicable") or "").strip().lower() == "yes"


def classify_attendance_day(employee, attendance_date, record=None):
    """Classify a single calendar day for payroll (with or without attendance row)."""
    applicable = _employee_applicable_for(employee)
    project = employee.get("project_name") or ""
    date_str = attendance_date.strftime(DATE_FMT)
    weekday = attendance_date.strftime("%A")
    weekly_off_day = _employee_weekly_off_day(employee)
    is_weekly_off = weekday == weekly_off_day
    holiday = _holiday_on_date(date_str, applicable, project)

    if record is not None:
        status = (record.get("status") or "Present").strip()
        ot_hours = float(record.get("ot_hours") or record.get("overtime") or 0)
        worked_hours = float(record.get("total_hours") or record.get("worked_hours") or 0)
        if holiday:
            return {
                "day_type": "holiday_worked",
                "status": status,
                "worked_hours": worked_hours,
                "ot_hours": ot_hours,
                "holiday_ot_hours": ot_hours,
                "weekly_off_ot_hours": 0.0,
            }
        if is_weekly_off:
            return {
                "day_type": "weekly_off_worked",
                "status": status,
                "worked_hours": worked_hours,
                "ot_hours": ot_hours,
                "holiday_ot_hours": 0.0,
                "weekly_off_ot_hours": ot_hours,
            }
        return {
            "day_type": "regular",
            "status": status,
            "worked_hours": worked_hours,
            "ot_hours": ot_hours,
            "holiday_ot_hours": 0.0,
            "weekly_off_ot_hours": 0.0,
        }

    if holiday and _paid_holiday_eligible(employee):
        return {
            "day_type": "paid_holiday",
            "status": "Paid Holiday",
            "worked_hours": 0.0,
            "ot_hours": 0.0,
            "holiday_ot_hours": 0.0,
            "weekly_off_ot_hours": 0.0,
        }
    if is_weekly_off and is_monthly_staff(employee.get("employee_type")) and _is_paid_weekly_off(employee, weekday):
        return {
            "day_type": "paid_weekly_off",
            "status": "Paid Weekly Off",
            "worked_hours": 0.0,
            "ot_hours": 0.0,
            "holiday_ot_hours": 0.0,
            "weekly_off_ot_hours": 0.0,
        }
    if is_weekly_off or holiday:
        return {
            "day_type": "non_working",
            "status": "Non Working",
            "worked_hours": 0.0,
            "ot_hours": 0.0,
            "holiday_ot_hours": 0.0,
            "weekly_off_ot_hours": 0.0,
        }
    return {
        "day_type": "absent",
        "status": "Absent",
        "worked_hours": 0.0,
        "ot_hours": 0.0,
        "holiday_ot_hours": 0.0,
        "weekly_off_ot_hours": 0.0,
    }


def infer_attendance_category(employee, attendance_date, status):
    """Set attendance_category when saving a row (no manual Holiday/Week Off status)."""
    applicable = _employee_applicable_for(employee)
    project = employee.get("project_name") or ""
    date_str = attendance_date.strftime(DATE_FMT)
    weekday = attendance_date.strftime("%A")
    holiday = _holiday_on_date(date_str, applicable, project)
    if holiday:
        return "Holiday Worked", holiday.get("payment_type", "Paid"), holiday.get("holiday_name", "")
    if weekday == _employee_weekly_off_day(employee):
        return "Weekly Off Worked", "Paid", ""
    return "Regular", "Regular", ""


def build_month_attendance_summary(employee_id, payroll_month, period_start=None, period_end=None):
    employee = get_employee(employee_id)
    if not employee or not payroll_month:
        return None

    start_date, end_date, total_month_days = _month_date_range(payroll_month)
    month, year = payroll_month.split("/")
    month_filter = f"%/{month}/{year}"

    conn = get_conn()
    attendance_df = pd.read_sql_query(
        """
        SELECT attendance_date, status, COALESCE(total_hours, worked_hours, 0) AS total_hours,
               COALESCE(ot_hours, overtime, 0) AS ot_hours,
               COALESCE(applied_ot_rate, 0) AS applied_ot_rate
        FROM attendance
        WHERE COALESCE(employee_id, worker_id) = ?
          AND attendance_date LIKE ?
        """,
        conn,
        params=(employee_id, month_filter),
    )
    conn.close()

    records_by_date = {}
    min_att_dt = None
    max_att_dt = None
    if not attendance_df.empty:
        for _, row in attendance_df.iterrows():
            date_str = str(row["attendance_date"])
            worked = float(row.get("total_hours") or 0)
            ot = float(row.get("ot_hours") or 0)
            status = str(row.get("status") or "Present").strip()
            if date_str in records_by_date:
                agg = records_by_date[date_str]
                agg["total_hours"] = float(agg.get("total_hours") or 0) + worked
                agg["ot_hours"] = float(agg.get("ot_hours") or 0) + ot
                agg["worked_hours"] = agg["total_hours"]
                agg["overtime"] = agg["ot_hours"]
                st_low = status.lower()
                prev = str(agg.get("status") or "").lower()
                if st_low == "present" or prev == "present":
                    agg["status"] = "Present"
                elif st_low == "half day" or prev == "half day":
                    agg["status"] = "Half Day"
                elif st_low == "leave" and prev not in ("present", "half day"):
                    agg["status"] = "Leave"
            else:
                rec = row.to_dict()
                rec["worked_hours"] = worked
                rec["overtime"] = ot
                records_by_date[date_str] = rec
            try:
                dt = datetime.strptime(date_str[:10], DATE_FMT)
                min_att_dt = dt if min_att_dt is None else min(min_att_dt, dt)
                max_att_dt = dt if max_att_dt is None else max(max_att_dt, dt)
            except ValueError:
                pass

    summary = {
        "employee_id": employee_id,
        "employee_name": employee.get("employee_name") or "",
        "employee_type": employee.get("employee_type") or "",
        "payroll_month": payroll_month,
        "payroll_year": year,
        "total_month_days": total_month_days,
        "worked_days": 0,
        "leave_days": 0,
        "half_days": 0,
        "absent_days": 0,
        "paid_weekly_off_days": 0,
        "paid_holiday_days": 0,
        "total_worked_hours": 0.0,
        "total_ot_hours": 0.0,
        "holiday_ot_hours": 0.0,
        "weekly_off_ot_hours": 0.0,
        "normal_ot_hours": 0.0,
        "ot_amount": 0.0,
        "ot_held_hours": 0.0,
        "normal_salary_amount": 0.0,
        "weekly_off_paid_amount": 0.0,
        "holiday_paid_amount": 0.0,
        "normal_ot_amount": 0.0,
        "deductions": 0.0,
        "net_salary": 0.0,
        "payable_days": 0.0,
    }

    ot_rate = float(employee.get("ot_rate") or 0)
    ot_pay = _ot_payable(employee)
    salary_amount = float(employee.get("salary_amount") or employee.get("basic_salary") or 0)
    daily_rate = salary_amount
    if is_monthly_staff(employee.get("employee_type")) and total_month_days:
        daily_rate = salary_amount / total_month_days

    # Payroll period rule:
    # - If explicit period_start/period_end is provided (daily wage partial period), calculate only inside that range.
    # - Else if attendance exists only for part of the month (e.g., 01..15), do NOT pay weekly-off/holiday
    #   outside the attendance date window.
    # - Else (full-month coverage or no attendance) calculate full month.
    calc_start = start_date
    calc_end = end_date
    if period_start and period_end:
        try:
            ps = period_start if isinstance(period_start, datetime) else datetime.strptime(str(period_start)[:10], DATE_FMT)
            pe = period_end if isinstance(period_end, datetime) else datetime.strptime(str(period_end)[:10], DATE_FMT)
            if pe < ps:
                ps, pe = pe, ps
            calc_start = max(start_date, ps)
            calc_end = min(end_date, pe + timedelta(days=1))
        except ValueError:
            # if bad inputs, fall back to auto logic
            pass
    elif min_att_dt and max_att_dt:
        # Full month coverage -> keep full month
        is_full_month = (
            min_att_dt.day == 1
            and min_att_dt.month == start_date.month
            and min_att_dt.year == start_date.year
            and max_att_dt.day == total_month_days
            and max_att_dt.month == start_date.month
            and max_att_dt.year == start_date.year
        )
        if not is_full_month:
            calc_start = max(start_date, min_att_dt)
            # end is exclusive; add 1 day
            calc_end = min(end_date, max_att_dt + timedelta(days=1))

    current = calc_start
    while current < calc_end:
        date_str = current.strftime(DATE_FMT)
        record = records_by_date.get(date_str)
        day = classify_attendance_day(employee, current, record)
        status = day["status"]

        if day["day_type"] == "paid_holiday":
            summary["paid_holiday_days"] += 1
            summary["payable_days"] += 1.0
            summary["holiday_paid_amount"] += daily_rate
        elif day["day_type"] == "paid_weekly_off":
            summary["paid_weekly_off_days"] += 1
            summary["payable_days"] += 1.0
            summary["weekly_off_paid_amount"] += daily_rate
        elif day["day_type"] == "absent":
            summary["absent_days"] += 1
        elif record is not None:
            st_norm = status.strip().lower()
            if st_norm == "present":
                summary["worked_days"] += 1
                summary["payable_days"] += 1.0
            elif st_norm == "leave":
                summary["leave_days"] += 1
                if is_monthly_staff(employee.get("employee_type")):
                    summary["payable_days"] += 1.0
            elif st_norm == "half day":
                summary["half_days"] += 1
                summary["payable_days"] += 0.5
            elif st_norm == "absent":
                summary["absent_days"] += 1

        summary["total_worked_hours"] += day["worked_hours"]
        summary["total_ot_hours"] += day["ot_hours"]
        summary["holiday_ot_hours"] += day["holiday_ot_hours"]
        summary["weekly_off_ot_hours"] += day["weekly_off_ot_hours"]
        if day["day_type"] == "regular" and day["ot_hours"] > 0:
            summary["normal_ot_hours"] += day["ot_hours"]

        current += timedelta(days=1)

    if is_monthly_staff(employee.get("employee_type")):
        summary["normal_salary_amount"] = round(
            (salary_amount / total_month_days) * summary["payable_days"] if total_month_days else 0,
            2,
        )
    else:
        summary["normal_salary_amount"] = round(summary["payable_days"] * daily_rate, 2)

    if ot_pay:
        summary["normal_ot_amount"] = round(summary["normal_ot_hours"] * ot_rate, 2)
        summary["ot_amount"] = round(summary["total_ot_hours"] * ot_rate, 2)
    else:
        summary["ot_held_hours"] = summary["total_ot_hours"]

    gross = (
        summary["normal_salary_amount"]
        + summary["weekly_off_paid_amount"]
        + summary["holiday_paid_amount"]
        + summary["ot_amount"]
    )
    summary["net_salary"] = round(max(0.0, gross - summary["deductions"]), 2)
    summary["base_salary"] = summary["normal_salary_amount"]
    summary["working_days"] = summary["worked_days"]
    summary["paid_non_working_days"] = summary["paid_weekly_off_days"] + summary["paid_holiday_days"]
    summary["ot_hours"] = round(summary["total_ot_hours"], 2)

    for key in summary:
        if isinstance(summary[key], float):
            summary[key] = round(summary[key], 2)

    return summary


def payroll_preview(employee_id, payroll_month=None):
    """Backward-compatible wrapper used across the app."""
    if not payroll_month:
        return {
            "base_salary": 0.0,
            "ot_amount": 0.0,
            "deductions": 0.0,
            "net_salary": 0.0,
            "working_days": 0,
            "ot_hours": 0.0,
            "paid_non_working_days": 0,
        }
    summary = build_month_attendance_summary(employee_id, payroll_month)
    if not summary:
        return {
            "base_salary": 0.0,
            "ot_amount": 0.0,
            "deductions": 0.0,
            "net_salary": 0.0,
            "working_days": 0,
            "ot_hours": 0.0,
            "paid_non_working_days": 0,
        }
    return summary
