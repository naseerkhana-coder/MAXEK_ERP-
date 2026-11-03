"""MAXEK ERP - shared payroll day-count and monthly-salary maths.

This module is the single source of truth for the *monthly salaried staff* rule:

    calendar_days   = actual days in the payroll period (month/year aware)
    sundays         = actual Sundays in that period
    working_days    = calendar_days - sundays
    daily_rate      = monthly_salary / working_days            (never rounded)
    payable_salary  = daily_rate * payable_working_days        (rounded once, to paise)

Sundays are never an unpaid absence. Attendance recorded on a Sunday does not add
to payable working days (see ``resolve_payable_days``).

Everything here is pure (no database access) so payroll generation, previews,
payslips, registers, exports and the dashboard can all share it. Daily-wage /
hourly calculations deliberately live elsewhere and do not use this module.

Rounding policy: intermediate values (daily rate, ratios) are kept as exact
``Decimal`` values. Only final monetary amounts are rounded, half-up to 2 places.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

SUNDAY_WEEKDAY = 6  # datetime.weekday(): Monday=0 ... Sunday=6
CALC_BASIS = "working_days_ex_sundays_v1"
MONEY_QUANTUM = Decimal("0.01")
_ZERO = Decimal("0")


def to_decimal(value: Any) -> Decimal:
    """Convert numbers/strings/None to Decimal without binary-float noise."""
    if isinstance(value, Decimal):
        return value
    if value is None or value == "":
        return _ZERO
    try:
        return Decimal(str(value))
    except Exception:  # pragma: no cover - defensive; invalid input counts as 0
        return _ZERO


def round_money(value: Any) -> float:
    """Round a final monetary amount half-up to 2 decimals."""
    return float(to_decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP))


def parse_iso_date(value: Any) -> date | None:
    """Parse ``YYYY-MM-DD`` (extra time text ignored) or ``date``/``datetime``."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()[:10]
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def is_sunday(value: Any) -> bool:
    parsed = parse_iso_date(value)
    return parsed is not None and parsed.weekday() == SUNDAY_WEEKDAY


def count_sundays(start: Any, end: Any) -> int:
    """Number of Sundays between two dates, inclusive."""
    s, e = parse_iso_date(start), parse_iso_date(end)
    if not s or not e or e < s:
        return 0
    first_sunday = s + timedelta(days=(SUNDAY_WEEKDAY - s.weekday()) % 7)
    if first_sunday > e:
        return 0
    return (e - first_sunday).days // 7 + 1


def period_day_counts(start: Any, end: Any) -> dict[str, int]:
    """Calendar days, Sundays and working days (calendar - Sundays) for a period."""
    s, e = parse_iso_date(start), parse_iso_date(end)
    if not s or not e or e < s:
        return {"calendar_days": 0, "sundays": 0, "working_days": 0}
    calendar_days = (e - s).days + 1
    sundays = count_sundays(s, e)
    return {
        "calendar_days": calendar_days,
        "sundays": sundays,
        "working_days": calendar_days - sundays,
    }


def month_day_counts(month: int, year: int) -> dict[str, int]:
    """Day counts for a whole calendar month (28/29/30/31 days aware)."""
    last_day = monthrange(int(year), int(month))[1]
    return period_day_counts(
        f"{int(year):04d}-{int(month):02d}-01",
        f"{int(year):04d}-{int(month):02d}-{last_day:02d}",
    )


def employment_window(joining_date: Any, exit_date: Any, start: Any, end: Any) -> dict[str, Any] | None:
    """Days an employee can be paid for inside a payroll period.

    The window runs from the later of the period start and the **joining date** to
    the earlier of the period end and the **exit date**, both ends inclusive. Either
    date may be missing: a missing exit date does not disable joining-date proration
    (and vice versa). An exit on a Sunday simply ends the window on that Sunday
    (Sundays are never working days, so nothing extra is paid).

    ``restricted`` is False when the window covers the whole period - the ordinary
    case for staff who joined earlier and have not left - so such records behave
    exactly as they did before windows existed. The daily-rate divisor is always the
    *full period's* working days; the window only limits how many of those days can
    be payable. Returns ``None`` only for an unusable period.
    """
    s, e = parse_iso_date(start), parse_iso_date(end)
    if not s or not e or e < s:
        return None
    joined = parse_iso_date(joining_date)
    exit_on = parse_iso_date(exit_date)
    win_start = max(s, joined) if joined else s
    win_end = min(e, exit_on) if exit_on else e
    base = {
        "joining_date": joined.isoformat() if joined else None,
        "exit_date": exit_on.isoformat() if exit_on else None,
    }
    if win_end < win_start:
        return {
            **base,
            "window_start": None,
            "window_end": None,
            "restricted": True,
            "calendar_days": 0,
            "sundays": 0,
            "working_days": 0,
        }
    return {
        **base,
        "window_start": win_start.isoformat(),
        "window_end": win_end.isoformat(),
        "restricted": (win_start, win_end) != (s, e),
        **period_day_counts(win_start, win_end),
    }


def in_window(value: Any, window: dict[str, Any] | None) -> bool:
    """True if ``value`` falls inside ``window`` (always True when there is no window)."""
    if window is None:
        return True
    d = parse_iso_date(value)
    if d is None or not window.get("window_start"):
        return False
    return window["window_start"] <= d.isoformat() <= window["window_end"]


def resolve_payable_days(
    working_days: Any,
    *,
    present_days: Any,
    recorded_absent_days: Any = None,
    half_days: Any = 0,
    paid_holiday_days: Any = 0,
) -> dict[str, float]:
    """Payable working days for a monthly salaried employee.

    * ``present_days`` must already exclude Sundays when it comes from daily
      attendance. For monthly summary entries (which may be keyed on calendar
      days) it is simply capped at ``working_days`` so Sunday-inclusive entries
      cannot exceed a full month.
    * ``recorded_absent_days`` (monthly summary only) bounds payable days from
      above: ``working_days - absent - 0.5 * half_days``. This keeps an entry such
      as worked=29 / absent=2 (Sundays included) from being paid in full.
    * ``paid_holiday_days`` are declared, unworked holidays that fall on working
      days and are payable under the employee's holiday-pay rule. They can only
      fill remaining capacity, so payable days never exceed ``working_days``.
    """
    wd = max(to_decimal(working_days), _ZERO)
    present = min(max(to_decimal(present_days), _ZERO), wd)
    ceiling = wd
    absent = to_decimal(recorded_absent_days)
    if absent > _ZERO:
        ceiling = max(wd - absent - to_decimal(half_days) * Decimal("0.5"), _ZERO)
    worked = min(present, ceiling)
    holiday = min(max(to_decimal(paid_holiday_days), _ZERO), wd - worked)
    payable = worked + holiday
    return {
        "worked_working_days": float(worked),
        "paid_holiday_days": float(holiday),
        "payable_days": float(payable),
        "unpaid_absence_days": float(max(wd - payable, _ZERO)),
    }


def daily_rate(monthly_salary: Any, working_days: Any) -> Decimal:
    """Exact (unrounded) per-working-day rate."""
    wd = to_decimal(working_days)
    if wd <= _ZERO:
        return _ZERO
    return to_decimal(monthly_salary) / wd


def prorate_by_working_days(amount: Any, payable_days: Any, working_days: Any) -> float:
    """Pro-rate a monthly amount (e.g. travel allowance) by payable/working days."""
    wd = to_decimal(working_days)
    if wd <= _ZERO:
        return 0.0
    ratio = min(max(to_decimal(payable_days) / wd, _ZERO), Decimal("1"))
    return round_money(to_decimal(amount) * ratio)


def monthly_pay_breakdown(
    monthly_salary: Any,
    *,
    start: Any,
    end: Any,
    payable_days: Any,
    paid_holiday_days: Any = 0,
) -> dict[str, Any]:
    """Salary figures for one monthly-salaried employee and period.

    ``payable_days`` is the *total* payable working days (worked + paid holidays).
    ``earned_base`` is the part earned by worked days; ``holiday_pay`` is the part
    earned by paid holidays; both are rounded as final amounts, and
    ``payable_salary`` equals their sum so printed lines always add up.
    """
    counts = period_day_counts(start, end)
    wd = counts["working_days"]
    rate = daily_rate(monthly_salary, wd)
    payable = to_decimal(payable_days)
    holiday_days = min(to_decimal(paid_holiday_days), payable)
    worked_days = payable - holiday_days
    earned_base = round_money(rate * worked_days)
    holiday_pay = round_money(rate * holiday_days)
    return {
        **counts,
        "monthly_salary": round_money(monthly_salary),
        # Display value only; every amount above is computed from the exact rate.
        "daily_rate": float(rate.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "payable_days": float(payable),
        "worked_days_paid": float(worked_days),
        "earned_base": earned_base,
        "holiday_pay": holiday_pay,
        "payable_salary": round_money(Decimal(str(earned_base)) + Decimal(str(holiday_pay))),
        "calc_basis": CALC_BASIS,
    }
