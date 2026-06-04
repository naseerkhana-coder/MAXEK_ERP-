"""Worker payroll calculation — 8hr / 10hr categories, OT, period totals."""

from __future__ import annotations

from datetime import datetime, timedelta

WORKER_CATEGORIES = {
    "8 Hr": 8.0,
    "10 Hr": 10.0,
    "Category A": 8.0,
    "Category B": 10.0,
}

DEDUCTION_TYPES = (
    "Advance",
    "Food",
    "Fine",
    "Loan",
    "Other",
)

WORKFLOW_STATUSES = ("Draft", "Calculated", "Approved", "Paid")
WORKFLOW_STEPS = (
    "Attendance",
    "Calculation",
    "Review",
    "Approval",
    "Payment Entry",
    "Completed",
)
PAYMENT_MODES = ("Cash", "Bank Transfer", "UPI", "Cheque")


def normalize_workflow_status(status: str) -> str:
    """Map HR/unified payroll statuses onto worker payroll workflow."""
    text = (status or "Draft").strip()
    if text == "Submitted to MD":
        return "Calculated"
    if text in WORKFLOW_STATUSES:
        return text
    return "Draft"


def workflow_step_index(workflow_status: str) -> int:
    """Map stored status to UI workflow step (0-based)."""
    status = normalize_workflow_status(workflow_status)
    if status == "Paid":
        return len(WORKFLOW_STEPS) - 1
    if status == "Approved":
        return 4
    if status == "Calculated":
        return 2
    if status == "Draft":
        return 0
    return 1


def standard_hours_for_category(hour_category: str) -> float:
    text = (hour_category or "").strip()
    if text in WORKER_CATEGORIES:
        return WORKER_CATEGORIES[text]
    if "10" in text:
        return 10.0
    return 8.0


def hourly_rate(daily_wage: float, standard_hours: float) -> float:
    if standard_hours <= 0:
        return 0.0
    return round(float(daily_wage) / float(standard_hours), 2)


def ot_hourly_rate(daily_wage: float, standard_hours: float, stored_ot_rate: float | None = None) -> float:
    if stored_ot_rate and float(stored_ot_rate) > 0:
        return round(float(stored_ot_rate), 2)
    return hourly_rate(daily_wage, standard_hours)


def calculate_daily_pay(
    daily_wage: float,
    standard_hours: float,
    worked_hours: float,
    stored_ot_rate: float | None = None,
) -> dict:
    """
    Pay rules:
    - worked >= standard: full daily wage + OT for hours above standard
    - worked < standard: (daily_wage / standard) * worked_hours, no OT
    """
    daily_wage = float(daily_wage or 0)
    standard_hours = float(standard_hours or 8)
    worked_hours = max(0.0, float(worked_hours or 0))
    rate = hourly_rate(daily_wage, standard_hours)
    ot_rate = ot_hourly_rate(daily_wage, standard_hours, stored_ot_rate)

    if worked_hours <= 0:
        return {
            "base_pay": 0.0,
            "ot_hours": 0.0,
            "ot_pay": 0.0,
            "gross_pay": 0.0,
            "hourly_rate": rate,
            "ot_hourly_rate": ot_rate,
        }

    if worked_hours >= standard_hours:
        base_pay = daily_wage
        ot_hours = round(worked_hours - standard_hours, 2)
        ot_pay = round(ot_hours * ot_rate, 2)
    else:
        base_pay = round(rate * worked_hours, 2)
        ot_hours = 0.0
        ot_pay = 0.0

    return {
        "base_pay": round(base_pay, 2),
        "ot_hours": ot_hours,
        "ot_pay": ot_pay,
        "gross_pay": round(base_pay + ot_pay, 2),
        "hourly_rate": rate,
        "ot_hourly_rate": ot_rate,
    }


def period_cycle_label(period_start: datetime, period_end: datetime) -> str:
    """Advance = 1st–15th; Final = 16th–month end."""
    if period_start.day == 1 and period_end.day <= 15:
        return "Advance"
    return "Final"


def build_period_payroll(attendance_rows: list[dict], worker: dict) -> dict:
    """Sum daily attendance into period totals."""
    daily_wage = float(worker.get("daily_wage_rate") or worker.get("salary") or 0)
    standard = standard_hours_for_category(worker.get("hour_category") or "8 Hr")
    stored_ot = worker.get("ot_rate")

    worked_days = 0
    total_hours = 0.0
    total_ot_hours = 0.0
    gross = 0.0
    base_total = 0.0
    ot_total = 0.0
    day_lines: list[dict] = []

    for row in attendance_rows:
        hours = float(row.get("total_hours") or row.get("worked_hours") or 0)
        if hours <= 0 and not str(row.get("in_time") or "").strip():
            continue
        day = calculate_daily_pay(daily_wage, standard, hours, stored_ot)
        if hours > 0:
            worked_days += 1
        total_hours += hours
        total_ot_hours += day["ot_hours"]
        base_total += day["base_pay"]
        ot_total += day["ot_pay"]
        gross += day["gross_pay"]
        day_lines.append(
            {
                "attendance_date": row.get("attendance_date"),
                "worked_hours": hours,
                **day,
            }
        )

    return {
        "worked_days": worked_days,
        "worked_hours": round(total_hours, 2),
        "ot_hours": round(total_ot_hours, 2),
        "gross_salary": round(gross, 2),
        "base_salary": round(base_total, 2),
        "ot_amount": round(ot_total, 2),
        "standard_hours": standard,
        "daily_wage_rate": daily_wage,
        "day_lines": day_lines,
    }


def apply_deductions(gross: float, ot_amount: float, deductions: list[dict]) -> dict:
    total_ded = round(sum(float(d.get("amount") or 0) for d in deductions), 2)
    gross_total = round(float(gross or 0) + float(ot_amount or 0), 2)
    net = round(max(0.0, gross_total - total_ded), 2)
    return {
        "gross_salary": gross_total,
        "ot_amount": round(float(ot_amount or 0), 2),
        "total_deductions": total_ded,
        "net_salary": net,
    }
