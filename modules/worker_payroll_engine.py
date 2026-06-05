"""Worker payroll calculation — 8hr / 10hr categories, OT, period totals."""

from __future__ import annotations

from datetime import datetime, timedelta

WORKER_CATEGORIES = {
    "8 Hr": 8.0,
    "10 Hr": 10.0,
    "Category A": 8.0,
    "Category B": 10.0,
    "8 Hour Worker": 8.0,
    "10 Hour Worker": 10.0,
}

WORKER_TYPES = (
    "Company Worker",
    "Subcontractor Worker",
    "Labour Supply Worker",
)

DUTY_CATEGORY_OPTIONS = ("8 Hour Worker", "10 Hour Worker")

# employee_type (DB) → canonical worker_type
EMPLOYEE_TYPE_TO_WORKER_TYPE: dict[str, str] = {
    "Company Worker": "Company Worker",
    "Sub Contractor Worker": "Subcontractor Worker",
    "Subcontractor Worker": "Subcontractor Worker",
    "Labour Supply Worker": "Labour Supply Worker",
    "Site Worker": "Subcontractor Worker",
}

# worker_type → employee_type for storage
WORKER_TYPE_TO_EMPLOYEE_TYPE: dict[str, str] = {
    "Company Worker": "Company Worker",
    "Subcontractor Worker": "Sub Contractor Worker",
    "Labour Supply Worker": "Labour Supply Worker",
}

PAYROLL_WORKER_EMPLOYEE_TYPES = frozenset(
    {
        "Company Worker",
        "Sub Contractor Worker",
        "Subcontractor Worker",
        "Labour Supply Worker",
        "Site Worker",
    }
)

DEDUCTION_TYPES = (
    "Advance Recovery",
    "Food Recovery",
    "Fine Deduction",
    "Loan Recovery",
    "Other Deductions",
)

from modules.approval_workflow import WORKFLOW_STATUSES as STANDARD_WORKFLOW_STATUSES
from modules.approval_workflow import can_transition, normalize_status as _normalize_canonical

WORKFLOW_STATUSES = STANDARD_WORKFLOW_STATUSES
WORKFLOW_STEPS = (
    "Draft",
    "Prepared",
    "Checked",
    "Approved",
    "Payment Released",
    "Paid",
)
PAYMENT_MODES = ("Cash", "Bank Transfer", "UPI", "Cheque")


def normalize_workflow_status(status: str) -> str:
    """Map legacy worker payroll statuses to standard workflow."""
    return _normalize_canonical(status, "worker_payroll")


def workflow_step_index(workflow_status: str) -> int:
    """Map stored status to UI workflow step (0-based)."""
    status = normalize_workflow_status(workflow_status)
    try:
        return WORKFLOW_STEPS.index(status)
    except ValueError:
        return 0


def next_workflow_status(current: str) -> str | None:
    """Return the next forward status in the worker payroll workflow, if any."""
    status = normalize_workflow_status(current)
    transitions = {
        "Draft": "Prepared",
        "Prepared": "Checked",
        "Checked": "Approved",
        "Approved": "Payment Released",
        "Payment Released": "Paid",
    }
    nxt = transitions.get(status)
    if nxt and can_transition(status, nxt):
        return nxt
    return None


def is_payroll_worker(employee_type: str | None = None, worker_type: str | None = None) -> bool:
    wt = (worker_type or "").strip()
    if wt in WORKER_TYPES:
        return True
    return (employee_type or "").strip() in PAYROLL_WORKER_EMPLOYEE_TYPES


def resolve_worker_type(employee_type: str | None = None, worker_type: str | None = None) -> str:
    wt = (worker_type or "").strip()
    if wt in WORKER_TYPES:
        return wt
    return EMPLOYEE_TYPE_TO_WORKER_TYPE.get((employee_type or "").strip(), "")


def resolve_employee_type(worker_type: str | None = None, employee_type: str | None = None) -> str:
    et = (employee_type or "").strip()
    if et in PAYROLL_WORKER_EMPLOYEE_TYPES or et in ("Monthly Staff", "Daily Wage Staff"):
        return et
    wt = (worker_type or "").strip()
    return WORKER_TYPE_TO_EMPLOYEE_TYPE.get(wt, et or "Sub Contractor Worker")


def ot_eligible_flag(value) -> bool:
    return str(value or "").strip().lower() in ("yes", "y", "true", "1")


def duty_category_from_record(record: dict) -> str:
    text = (
        (record or {}).get("duty_category")
        or (record or {}).get("hour_category")
        or ""
    ).strip()
    if text in DUTY_CATEGORY_OPTIONS:
        return text
    if "10" in text:
        return "10 Hour Worker"
    return "8 Hour Worker"


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
    *,
    ot_eligible: bool | str = True,
) -> dict:
    """
    Pay rules (8hr / 10hr workers):
    - worked < standard: (daily_wage / standard) * worked_hours, no OT
    - worked == standard: full daily_wage
    - worked > standard: daily_wage + OT (OT_rate * extra hours) when OT eligible
    """
    daily_wage = float(daily_wage or 0)
    standard_hours = float(standard_hours or 8)
    worked_hours = max(0.0, float(worked_hours or 0))
    eligible = ot_eligible_flag(ot_eligible) if not isinstance(ot_eligible, bool) else ot_eligible
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

    if worked_hours < standard_hours:
        base_pay = round(rate * worked_hours, 2)
        ot_hours = 0.0
        ot_pay = 0.0
    elif worked_hours == standard_hours:
        base_pay = round(daily_wage, 2)
        ot_hours = 0.0
        ot_pay = 0.0
    else:
        base_pay = round(daily_wage, 2)
        ot_hours = round(worked_hours - standard_hours, 2)
        ot_pay = round(ot_hours * ot_rate, 2) if eligible else 0.0

    return {
        "base_pay": base_pay,
        "ot_hours": ot_hours,
        "ot_pay": ot_pay,
        "gross_pay": round(base_pay + ot_pay, 2),
        "hourly_rate": rate,
        "ot_hourly_rate": ot_rate,
    }


def worker_daily_wage(record: dict) -> float:
    """Resolve daily wage from employee/worker master fields."""
    row = record or {}
    for key in ("daily_wage", "daily_wage_rate", "salary_amount", "salary", "basic_salary"):
        val = float(row.get(key) or 0)
        if val > 0:
            return val
    return 0.0


def build_period_payroll(attendance_rows: list[dict], worker: dict) -> dict:
    """Sum daily attendance into period totals."""
    daily_wage = worker_daily_wage(worker)
    duty = duty_category_from_record(worker)
    standard = standard_hours_for_category(duty)
    stored_ot = worker.get("ot_rate")
    ot_eligible = worker.get("ot_eligible")
    if ot_eligible is None:
        ot_eligible = worker.get("ot_applicable", "Yes")

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
        day = calculate_daily_pay(
            daily_wage,
            standard,
            hours,
            stored_ot,
            ot_eligible=ot_eligible,
        )
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
        "duty_category": duty,
        "day_lines": day_lines,
    }


def apply_deductions(gross: float, ot_amount: float, deductions: list[dict]) -> dict:
    """Net = gross - deductions. ``gross`` is already inclusive of OT when from period totals."""
    total_ded = round(sum(float(d.get("amount") or 0) for d in deductions), 2)
    gross_total = round(float(gross or 0), 2)
    net = round(max(0.0, gross_total - total_ded), 2)
    return {
        "gross_salary": gross_total,
        "ot_amount": round(float(ot_amount or 0), 2),
        "total_deductions": total_ded,
        "net_salary": net,
    }


def period_cycle_label(period_start: datetime, period_end: datetime) -> str:
    """Advance = 1st–15th; Final = 16th–month end."""
    if period_start.day == 1 and period_end.day <= 15:
        return "Advance"
    return "Final"
