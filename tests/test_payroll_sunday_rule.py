"""Payroll: Sunday-excluded working-day rule, staff selector and dashboard.

Rule under test (monthly salaried staff):
    working_days = calendar_days - sundays
    daily_rate   = monthly_salary / working_days
    payable      = daily_rate * payable_working_days   (rounded once, at the end)
"""
from __future__ import annotations

import calendar
import io
import os
import re
import sys
import tempfile
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("MAXEK_SKIP_DEMO_SEED", "1")

import app as app_module  # noqa: E402
from payroll_calc import (  # noqa: E402
    count_sundays,
    month_day_counts,
    monthly_pay_breakdown,
    period_day_counts,
    prorate_by_working_days,
    resolve_payable_days,
    round_money,
)
from payroll_service import (  # noqa: E402
    build_payroll_dashboard,
    calculate_monthly_staff_pay,
    calculate_staff_period_pay,
    calculate_worker_period_pay,
    ensure_no_payroll_overlap,
    explain_payroll_eligibility,
    export_register_rows,
    fetch_holidays,
    list_eligible_employees,
    period_from_month_year,
    serialize_eligible_employee,
)
from store_service import ensure_store_schema  # noqa: E402

# (year, month, calendar_days, sundays) covering 28/29/30/31-day months with 4 and 5 Sundays.
MONTH_CASES = [
    (2026, 2, 28, 4),   # 28 days, 4 Sundays
    (2032, 2, 29, 5),   # 29 days (leap), 5 Sundays
    (2028, 2, 29, 4),   # 29 days (leap), 4 Sundays
    (2026, 4, 30, 4),   # 30 days, 4 Sundays
    (2026, 11, 30, 5),  # 30 days, 5 Sundays
    (2026, 10, 31, 4),  # 31 days, 4 Sundays  (the 27 working day example)
    (2026, 8, 31, 5),   # 31 days, 5 Sundays
]


def _oracle_counts(year, month):
    """Independent day count: walk every date and test weekday()."""
    days = [date(year, month, d) for d in range(1, calendar.monthrange(year, month)[1] + 1)]
    sundays = [d for d in days if d.weekday() == 6]
    return len(days), len(sundays)


def _working_dates(year, month):
    last = calendar.monthrange(year, month)[1]
    return [date(year, month, d) for d in range(1, last + 1) if date(year, month, d).weekday() != 6]


def _money(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ─────────────────────────────── pure calculation ───────────────────────────────


@pytest.mark.parametrize("year,month,cal_days,sundays", MONTH_CASES)
def test_day_counts_cover_28_29_30_31_and_4_5_sundays(year, month, cal_days, sundays):
    assert _oracle_counts(year, month) == (cal_days, sundays)  # the table itself is right
    counts = month_day_counts(month, year)
    assert counts == {
        "calendar_days": cal_days,
        "sundays": sundays,
        "working_days": cal_days - sundays,
    }


def test_count_sundays_handles_partial_and_edge_ranges():
    assert count_sundays("2026-10-04", "2026-10-04") == 1  # a single Sunday
    assert count_sundays("2026-10-05", "2026-10-10") == 0  # Mon-Sat
    assert count_sundays("2026-10-01", "2026-10-31") == 4
    assert count_sundays("2026-10-31", "2026-10-01") == 0  # reversed range
    assert period_day_counts("bad", "2026-10-01")["working_days"] == 0


def test_spec_example_27_working_days():
    counts = month_day_counts(10, 2026)
    assert counts["working_days"] == 27
    full = monthly_pay_breakdown(27000, start="2026-10-01", end="2026-10-31", payable_days=27)
    assert full["payable_salary"] == 27000.00
    assert full["daily_rate"] == 1000.0
    two_absent = monthly_pay_breakdown(27000, start="2026-10-01", end="2026-10-31", payable_days=25)
    assert two_absent["payable_salary"] == 25000.00


@pytest.mark.parametrize("year,month,cal_days,sundays", MONTH_CASES)
@pytest.mark.parametrize("salary", [1000, 12345, 27000, 33333.33, 99999.99])
def test_full_attendance_always_pays_full_monthly_salary(year, month, cal_days, sundays, salary):
    wd = cal_days - sundays
    start, end = period_from_month_year(month, year)
    result = monthly_pay_breakdown(salary, start=start, end=end, payable_days=wd)
    assert result["payable_salary"] == _money(salary)


@pytest.mark.parametrize("year,month,cal_days,sundays", MONTH_CASES)
def test_unpaid_absences_use_the_selected_months_rate(year, month, cal_days, sundays):
    wd = cal_days - sundays
    start, end = period_from_month_year(month, year)
    result = monthly_pay_breakdown(30000, start=start, end=end, payable_days=wd - 3)
    expected = _money(Decimal(30000) / Decimal(wd) * Decimal(wd - 3))
    assert result["payable_salary"] == expected


def test_rounding_happens_only_on_the_final_amount():
    # 10000 / 27 = 370.370370...; rounding the rate first would give 7407.40, exact gives 7407.41.
    result = monthly_pay_breakdown(10000, start="2026-10-01", end="2026-10-31", payable_days=20)
    assert result["payable_salary"] == 7407.41
    assert round(round(10000 / 27, 2) * 20, 2) == 7407.4  # what early rounding would have produced


def test_payable_days_are_capped_so_sundays_can_never_overpay():
    assert resolve_payable_days(27, present_days=31)["payable_days"] == 27
    assert resolve_payable_days(27, present_days=27)["unpaid_absence_days"] == 0


def test_summary_entry_with_sundays_included_is_bounded_by_recorded_absences():
    # worked=29 (Sundays included) with 2 recorded absences is 25 payable days, not 27.
    assert resolve_payable_days(27, present_days=29, recorded_absent_days=2)["payable_days"] == 25
    assert resolve_payable_days(27, present_days=25, recorded_absent_days=2)["payable_days"] == 25
    # A half day is half an absence.
    assert resolve_payable_days(27, present_days=25.5, recorded_absent_days=1, half_days=1)["payable_days"] == 25.5


def test_paid_holidays_only_fill_spare_capacity():
    assert resolve_payable_days(27, present_days=26, paid_holiday_days=1)["payable_days"] == 27
    assert resolve_payable_days(27, present_days=27, paid_holiday_days=2)["payable_days"] == 27
    assert resolve_payable_days(27, present_days=24, paid_holiday_days=2)["payable_days"] == 26


def test_prorate_travel_allowance_never_exceeds_the_full_amount():
    assert prorate_by_working_days(1000, 27, 27) == 1000
    assert prorate_by_working_days(1000, 25, 27) == round_money(1000 * 25 / 27)
    assert prorate_by_working_days(1000, 31, 27) == 1000


# ─────────────────────────────── database fixtures ───────────────────────────────


@pytest.fixture()
def ctx(tmp_path):
    """Fresh app database; yields (db, app) inside an app context."""
    app = app_module.app
    app.config["TESTING"] = True
    original_db = app_module.DB_PATH
    original_reports = app_module.REPORTS_DIR
    app_module.DB_PATH = str(tmp_path / "maxek.db")
    app_module.REPORTS_DIR = str(tmp_path)
    with app.app_context():
        db = app_module.get_db()
        ensure_store_schema(db)  # init_db() on a brand-new file expects the store tables
        db.commit()
        app_module.init_db()
        app_module.prepare_payroll_page_db(db)
        yield db, app
    app_module.DB_PATH = original_db
    app_module.REPORTS_DIR = original_reports


def add_staff(db, name, code, *, salary=27000, salary_type="Monthly", status="Active",
              joining="2025-01-01", holiday_pay="No", ot="No", ot_rate=0, pf=0, esi=0):
    db.execute(
        "INSERT INTO staff(employee_code, staff_name, department, salary_type, salary_amount, "
        "ot_applicable, ot_rate_per_hour, holiday_pay_applicable, joining_date, status, "
        "pf_applicable, esi_applicable, pf_rate, esi_rate) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,12,0.75)",
        (code, name, "Accounts", salary_type, salary, ot, ot_rate, holiday_pay, joining, status, pf, esi),
    )
    db.commit()
    return db.execute("SELECT id FROM staff WHERE employee_code=?", (code,)).fetchone()[0]


def add_attendance(db, staff_id, day, status="Present", ot_hours=0.0, hours=8.0):
    db.execute(
        "INSERT INTO attendance(worker_id, worker_source, attendance_date, status, total_hours, "
        "ot_hours, approval_status) VALUES(?, 'staff', ?, ?, ?, ?, 'Approved')",
        (staff_id, day.isoformat(), status, hours, ot_hours),
    )


def attend(db, staff_id, days, **kwargs):
    for d in days:
        add_attendance(db, staff_id, d, **kwargs)
    db.commit()


def pay(db, staff_id, year, month):
    start, end = period_from_month_year(month, year)
    row = dict(db.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone())
    return calculate_monthly_staff_pay(db, row, start, end, fetch_holidays(db, start, end, "staff"))


# ─────────────────────────── monthly staff calculation (DB) ───────────────────────────


@pytest.mark.parametrize("year,month,cal_days,sundays", MONTH_CASES)
def test_daily_attendance_full_month_pays_full_salary(ctx, year, month, cal_days, sundays):
    db, _ = ctx
    sid = add_staff(db, "Full Month", "EMP100", salary=27000)
    attend(db, sid, _working_dates(year, month))  # present every day except Sundays
    calc = pay(db, sid, year, month)
    wd = cal_days - sundays
    assert calc["working_days"] == wd and calc["sundays"] == sundays and calc["calendar_days"] == cal_days
    assert calc["payable_days"] == wd and calc["unpaid_absence_days"] == 0
    assert calc["gross_salary"] == 27000.00 and calc["net_salary"] == 27000.00


@pytest.mark.parametrize("year,month,cal_days,sundays", MONTH_CASES)
def test_daily_attendance_unpaid_absences_reduce_by_that_months_rate(ctx, year, month, cal_days, sundays):
    db, _ = ctx
    sid = add_staff(db, "Two Absent", "EMP101", salary=27000)
    dates = _working_dates(year, month)
    attend(db, sid, dates[2:])  # first two working days unpaid
    calc = pay(db, sid, year, month)
    wd = cal_days - sundays
    assert calc["unpaid_absence_days"] == 2
    assert calc["gross_salary"] == _money(Decimal(27000) / Decimal(wd) * Decimal(wd - 2))


def test_spec_example_through_the_service(ctx):
    db, _ = ctx
    sid = add_staff(db, "Spec", "EMP102", salary=27000)
    attend(db, sid, _working_dates(2026, 10)[2:])
    calc = pay(db, sid, 2026, 10)
    assert calc["working_days"] == 27
    assert calc["gross_salary"] == 25000.00
    assert calc["daily_rate"] == 1000.0


def test_sundays_are_not_unpaid_absences(ctx):
    db, _ = ctx
    sid = add_staff(db, "Sunday Off", "EMP103", salary=27000)
    attend(db, sid, _working_dates(2026, 10))  # no Sunday rows at all
    assert pay(db, sid, 2026, 10)["gross_salary"] == 27000.00


def test_sunday_attendance_neither_overpays_nor_offsets_weekday_absence(ctx):
    db, _ = ctx
    a = add_staff(db, "Works Sundays", "EMP104", salary=27000)
    attend(db, a, _working_dates(2026, 10) + [date(2026, 10, 4), date(2026, 10, 11)])
    calc = pay(db, a, 2026, 10)
    assert calc["gross_salary"] == 27000.00 and calc["sunday_worked_days"] == 2

    b = add_staff(db, "Swaps", "EMP105", salary=27000)
    attend(db, b, _working_dates(2026, 10)[2:] + [date(2026, 10, 4), date(2026, 10, 11)])
    calc = pay(db, b, 2026, 10)
    assert calc["gross_salary"] == 25000.00  # business question: see report


def test_duplicate_attendance_rows_for_one_day_count_once(ctx):
    db, _ = ctx
    sid = add_staff(db, "Two Projects", "EMP106", salary=27000)
    dates = _working_dates(2026, 10)
    attend(db, sid, dates)
    attend(db, sid, dates[:5])  # second row per day (e.g. two projects)
    assert pay(db, sid, 2026, 10)["gross_salary"] == 27000.00


def test_half_days_count_as_half(ctx):
    db, _ = ctx
    sid = add_staff(db, "Half", "EMP107", salary=27000)
    dates = _working_dates(2026, 10)
    attend(db, sid, dates[:-2])
    attend(db, sid, dates[-2:], status="Half Day")
    assert pay(db, sid, 2026, 10)["gross_salary"] == 26000.00


@pytest.mark.parametrize(
    "worked,half,absent,expected",
    [
        (27, 0, 0, 27000.00),   # full attendance
        (25, 0, 2, 25000.00),   # the example: 2 unpaid working-day absences
        (29, 0, 2, 25000.00),   # entered on a calendar basis (Sundays included)
        (31, 0, 0, 27000.00),   # calendar-month entry, nothing absent: still just the month
        (24, 2, 1, 25000.00),   # 24 + 2 halves = 25 present, 1 absent + 2 half days -> 25
    ],
)
def test_monthly_summary_path(ctx, worked, half, absent, expected):
    db, _ = ctx
    sid = add_staff(db, "Summary", "EMP108", salary=27000)
    db.execute(
        "INSERT INTO staff_monthly_attendance(staff_id, year_month, worked_days, half_days, "
        "absent_days, ot_hours, approval_status) VALUES(?,?,?,?,?,?,?)",
        (sid, "2026-10", worked, half, absent, 0, "Approved"),
    )
    db.commit()
    assert pay(db, sid, 2026, 10)["gross_salary"] == expected


def test_joining_mid_month_is_prorated_on_working_days_only(ctx):
    db, _ = ctx
    sid = add_staff(db, "Joiner", "EMP109", salary=27000, joining="2026-10-15")
    attend(db, sid, [d for d in _working_dates(2026, 10) if d >= date(2026, 10, 15)])
    calc = pay(db, sid, 2026, 10)
    assert calc["payable_days"] == 15  # 15th-31st is 17 days, minus Sundays 18th and 25th
    assert calc["gross_salary"] == 15000.00


def test_holiday_pay_rule_is_preserved(ctx):
    db, _ = ctx
    db.execute("INSERT INTO holidays(holiday_date, holiday_name) VALUES('2026-10-14','Mid-month')")  # Wednesday
    db.execute("INSERT INTO holidays(holiday_date, holiday_name) VALUES('2026-10-04','On a Sunday')")
    db.commit()
    dates = [d for d in _working_dates(2026, 10) if d != date(2026, 10, 14)]

    paid = add_staff(db, "Paid Holiday", "EMP110", salary=27000, holiday_pay="Yes")
    attend(db, paid, dates)
    calc = pay(db, paid, 2026, 10)
    assert calc["gross_salary"] == 27000.00   # holiday paid; the Sunday holiday is not paid twice
    assert calc["holiday_pay"] == 1000.00

    unpaid = add_staff(db, "Unpaid Holiday", "EMP111", salary=27000, holiday_pay="No")
    attend(db, unpaid, dates)
    calc = pay(db, unpaid, 2026, 10)
    assert calc["gross_salary"] == 26000.00   # existing rule: unworked holiday is unpaid
    assert calc["holiday_pay"] == 0


def test_overtime_statutory_deductions_and_travel_keep_their_rules(ctx):
    db, _ = ctx
    sid = add_staff(db, "Everything", "EMP112", salary=27000, ot="Yes", ot_rate=100, pf=1)
    db.execute(
        "INSERT INTO staff_travel_tiers(staff_id, continuous_months, travel_mode, allowance_amount, sort_order) "
        "VALUES(?,0,'Bus',1000,0)",
        (sid,),
    )
    db.commit()
    dates = _working_dates(2026, 10)
    attend(db, sid, dates[2:])
    add_attendance(db, sid, dates[5], ot_hours=2.0)  # extra row carrying overtime
    db.commit()
    calc = pay(db, sid, 2026, 10)
    assert calc["ot_amount"] == 200.00
    assert calc["travel_allowance"] == round_money(1000 * 25 / 27)
    assert calc["gross_salary"] == round_money(25000 + 200 + calc["travel_allowance"])
    assert calc["deductions"] == 1800.00  # PF 12% on the 15,000 wage ceiling, unchanged rule
    assert calc["net_salary"] == round_money(calc["gross_salary"] - 1800)


def test_daily_wage_staff_use_the_unchanged_separate_calculation(ctx):
    db, _ = ctx
    sid = add_staff(db, "Daily Wage", "EMP113", salary=900, salary_type="Daily")
    attend(db, sid, _working_dates(2026, 10)[:10])
    start, end = period_from_month_year(10, 2026)
    row = dict(db.execute("SELECT * FROM staff WHERE id=?", (sid,)).fetchone())
    routed = calculate_staff_period_pay(db, row, start, end, [])
    direct = calculate_worker_period_pay(db, row, start, end, [], employee_type="staff")
    assert routed == direct
    assert routed["gross_salary"] == 9000.00 and "calc_basis" not in routed


def test_date_range_run_uses_the_same_rule_over_the_period(ctx):
    db, _ = ctx
    sid = add_staff(db, "Range", "EMP114", salary=24000)
    attend(db, sid, [d for d in _working_dates(2026, 10) if d.day <= 14])
    row = dict(db.execute("SELECT * FROM staff WHERE id=?", (sid,)).fetchone())
    calc = calculate_monthly_staff_pay(db, row, "2026-10-01", "2026-10-14", [])
    # 14 calendar days, Sundays on the 4th and 11th -> 12 working days, all attended.
    assert (calc["calendar_days"], calc["sundays"], calc["working_days"]) == (14, 2, 12)
    assert calc["gross_salary"] == 24000.00


# ───────────────────────── staff selector (the "Nabeel" problem) ─────────────────────────


def _selector(db, year=2026, month=10, **kw):
    start, end = period_from_month_year(month, year)
    return list_eligible_employees(
        db, "company_staff", period_start=start, period_end=end, include_without_data=True, **kw
    )


@pytest.mark.parametrize("raw_status", ["Active", "active", " ACTIVE ", "", None])
def test_status_spelling_does_not_hide_active_staff(ctx, raw_status):
    db, _ = ctx
    add_staff(db, "Nabeel", "EMP200", status="Active")
    db.execute("UPDATE staff SET status=? WHERE employee_code='EMP200'", (raw_status,))
    db.commit()
    assert [e["employee_name"] for e in _selector(db)] == ["Nabeel"]


def test_inactive_staff_stay_out(ctx):
    db, _ = ctx
    add_staff(db, "Left Company", "EMP201", status="Inactive")
    assert _selector(db) == []


def test_eligible_staff_without_attendance_are_listed_but_blocked_with_a_reason(ctx):
    db, _ = ctx
    sid = add_staff(db, "Nabeel", "EMP202")
    rows = _selector(db)
    assert len(rows) == 1 and rows[0]["has_period_data"] is False
    payload = serialize_eligible_employee(rows[0])
    assert payload["selectable"] is False and "attendance" in payload["blocked_reason"].lower()
    # By default (what generation uses) data-less staff are still excluded.
    start, end = period_from_month_year(10, 2026)
    assert list_eligible_employees(db, "company_staff", period_start=start, period_end=end) == []
    # Once data exists the same person is selectable.
    attend(db, sid, _working_dates(2026, 10))
    assert serialize_eligible_employee(_selector(db)[0])["selectable"] is True


def test_each_person_appears_exactly_once(ctx):
    db, _ = ctx
    add_staff(db, "Nabeel", "EMP203")
    db.execute(
        "INSERT INTO workers(worker_code, worker_name, worker_category, salary_type, salary_amount, status) "
        "VALUES('emp203', ' nabeel ', 'Company Staff', 'Monthly', 27000, 'Active')"
    )  # same person re-entered as a company worker
    db.execute(
        "INSERT INTO workers(worker_code, worker_name, worker_category, salary_type, salary_amount, status) "
        "VALUES('W-9', 'Different Person', 'Company Staff', 'Daily', 900, 'Active')"
    )
    db.commit()
    names = [e["employee_name"].strip().lower() for e in _selector(db)]
    assert names.count("nabeel") == 1 and "different person" in names
    assert [e["employee_type"] for e in _selector(db) if e["employee_name"] == "Nabeel"] == ["staff"]


def test_sub_contractor_workers_do_not_leak_into_company_staff(ctx):
    db, _ = ctx
    db.execute(
        "INSERT INTO workers(worker_code, worker_name, worker_category, salary_type, salary_amount, status) "
        "VALUES('S-1', 'Sub Worker', 'Sub Contractor Staff', 'Daily', 700, 'Active')"
    )
    db.commit()
    assert _selector(db) == []


def test_eligibility_explainer_names_the_actual_reason(ctx):
    db, _ = ctx
    add_staff(db, "Nabeel", "EMP204", status="Inactive")
    start, end = period_from_month_year(10, 2026)
    (report,) = explain_payroll_eligibility(db, "nabeel", period_start=start, period_end=end)
    assert report["listed"] is False and report["selectable"] is False
    assert any("Inactive" in r for r in report["reasons"])

    db.execute("UPDATE staff SET status='Active' WHERE employee_code='EMP204'")
    db.commit()
    (report,) = explain_payroll_eligibility(db, "EMP204", period_start=start, period_end=end)
    assert report["listed"] is True and report["selectable"] is False
    assert any("attendance" in r.lower() for r in report["reasons"])
    assert explain_payroll_eligibility(db, "n") == []  # too short to search


# ─────────────────────────── duplicate prevention & history ───────────────────────────


def _generate(db, staff_ids, *, month=10, year=2026):
    start, end = period_from_month_year(month, year)
    return app_module._generate_payroll_run_selected(
        db,
        run_type="monthly", period_start=start, period_end=end, month=month, year=year,
        project_id=None, department=None,
        employees=[("staff", sid) for sid in staff_ids],
        employment_category="company_staff", created_by="tester",
    )


def test_payroll_cannot_be_generated_twice_and_history_is_kept(ctx):
    db, _ = ctx
    sid = add_staff(db, "Once Only", "EMP300")
    attend(db, sid, _working_dates(2026, 10))
    run_id = _generate(db, [sid, sid])  # a double-posted selection collapses to one line
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM payroll_lines WHERE payroll_run_id=?", (run_id,)).fetchone()[0] == 1
    with pytest.raises(ValueError, match="already exists"):
        _generate(db, [sid])
    db.rollback()
    assert db.execute("SELECT COUNT(*) FROM payroll_runs").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM payroll_lines").fetchone()[0] == 1
    # Another month is a different period and is fine.
    attend(db, sid, _working_dates(2026, 11))
    _generate(db, [sid], month=11)
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM payroll_runs").fetchone()[0] == 2


def test_overlapping_date_range_is_also_blocked(ctx):
    db, _ = ctx
    sid = add_staff(db, "Overlap", "EMP301")
    attend(db, sid, _working_dates(2026, 10))
    _generate(db, [sid])
    db.commit()
    with pytest.raises(ValueError, match="already exists"):
        ensure_no_payroll_overlap(db, [("staff", sid)], "2026-10-20", "2026-11-05")
    ensure_no_payroll_overlap(db, [("staff", sid)], "2026-11-01", "2026-11-30")  # no overlap: fine


def test_generated_lines_store_the_day_basis_for_every_report(ctx):
    db, _ = ctx
    sid = add_staff(db, "Snapshot", "EMP302")
    attend(db, sid, _working_dates(2026, 10)[2:])
    run_id = _generate(db, [sid])
    db.commit()
    line = db.execute("SELECT * FROM payroll_lines WHERE payroll_run_id=?", (run_id,)).fetchone()
    assert (line["working_days"], line["present_days"], line["gross_salary"]) == (27, 25, 25000.00)
    (row,) = export_register_rows(db, run_id)
    assert row["working_days"] == 27 and row["payable_days"] == 25 and row["daily_rate"] == 1000.0
    assert row["calc_basis"].startswith("Working days excl. Sundays")


def test_legacy_lines_are_not_restated(ctx):
    db, _ = ctx
    sid = add_staff(db, "Old Run", "EMP303")
    db.execute(
        "INSERT INTO payroll_runs(run_ref, run_type, period_start, period_end, month, year, status, "
        "approval_status, locked, draft_saved) VALUES('PR-OLD','monthly','2026-09-01','2026-09-30',9,2026,"
        "'Approved','Approved',0,1)"
    )
    run_id = db.execute("SELECT id FROM payroll_runs WHERE run_ref='PR-OLD'").fetchone()[0]
    db.execute(
        "INSERT INTO payroll_lines(payroll_run_id, employee_type, staff_id, employee_code, employee_name, "
        "salary_type, base_salary, working_days, present_days, gross_salary, net_salary, payment_status) "
        "VALUES(?, 'staff', ?, 'EMP303', 'Old Run', 'Monthly', 27000, 30, 28, 25200, 25200, 'Pending')",
        (run_id, sid),
    )
    db.commit()
    (row,) = export_register_rows(db, run_id)
    assert row["working_days"] == 30 and row["payable_days"] == 28
    assert row["calc_basis"].startswith("Legacy")
    dash = build_payroll_dashboard(db, month=9, year=2026)
    (line_row,) = [r for r in dash["rows"] if r["code"] == "EMP303"]
    assert line_row["legacy"] is True and line_row["net"] == 25200 and line_row["status"] == "approved"


# ─────────────────────────────────── dashboard data ───────────────────────────────────


def test_dashboard_summary_filters_and_pagination(ctx):
    db, _ = ctx
    ids = []
    for i in range(30):
        sid = add_staff(db, f"Person {i:02d}", f"EMP4{i:02d}", salary=27000)
        ids.append(sid)
        if i < 27:
            attend(db, sid, _working_dates(2026, 10))
    add_staff(db, "No Data Person", "EMP499")
    _generate(db, ids[:10])
    db.commit()

    dash = build_payroll_dashboard(db, month=10, year=2026, per_page=10)
    s = dash["summary"]
    assert s["staff_count"] == 31 and s["generated_count"] == 10
    assert s["gross"] == 270000.00 and s["net"] == 270000.00 and s["deductions"] == 0
    assert s["not_generated"] == 17 and s["no_data"] == 4
    assert dash["month_status"]["key"] == "partial"
    assert (dash["total"], dash["pages"], len(dash["rows"])) == (31, 4, 10)
    assert dash["day_counts"]["working_days"] == 27

    last = build_payroll_dashboard(db, month=10, year=2026, per_page=10, page=99)
    assert last["page"] == 4 and len(last["rows"]) == 1  # page is clamped, not an error

    found = build_payroll_dashboard(db, month=10, year=2026, query="person 07")
    assert [r["name"] for r in found["rows"]] == ["Person 07"] and found["summary"]["staff_count"] == 31
    drafts = build_payroll_dashboard(db, month=10, year=2026, status="draft", per_page=100)
    assert drafts["total"] == 10
    nodata = build_payroll_dashboard(db, month=10, year=2026, status="no_data", per_page=100)
    assert "No Data Person" in [r["name"] for r in nodata["rows"]]
    empty = build_payroll_dashboard(db, month=2, year=2030)
    assert empty["summary"]["generated_count"] == 0 and empty["month_status"]["key"] == "not_started"


# ───────────────────────────── pages (HTTP) ─────────────────────────────


@pytest.fixture()
def client(ctx):
    db, app = ctx
    client = app.test_client()
    resp = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
    assert resp.status_code == 200
    return client


def _rows_in(html: str) -> int:
    body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    return body.count("<tr>")


def test_dashboard_page_renders_cards_table_filters_and_pagination(ctx, client):
    db, _ = ctx
    for i in range(60):
        sid = add_staff(db, f"Worker {i:02d}", f"EMP5{i:02d}", salary=27000)
        attend(db, sid, _working_dates(2026, 10)[:3])
    html = client.get("/payroll?month=10&year=2026").get_data(as_text=True)
    assert "Payroll status" in html and "27 working days" in html and "31 calendar" in html
    for label in ("Staff", "Gross salary", "Deductions", "Net payable"):
        assert label in html
    for col in ("Employee", "Monthly salary", "Working days", "Payable days", "Net salary", "Status"):
        assert col in html
    assert "₹ 27,000.00" in html  # Indian-grouped currency
    assert _rows_in(html) == 25 and "Showing 1&ndash;25 of 60" in html
    assert 'rel="next"' in html and "page=2" in html

    page3 = client.get("/payroll?month=10&year=2026&page=3&per_page=25").get_data(as_text=True)
    assert _rows_in(page3) == 10
    only = client.get("/payroll?month=10&year=2026&q=Worker+42").get_data(as_text=True)
    assert _rows_in(only) == 1 and "Worker 42" in only
    none = client.get("/payroll?month=10&year=2026&q=zzzzzz").get_data(as_text=True)
    assert "No employees match these filters" in none
    empty_month = client.get("/payroll?month=1&year=2020").get_data(as_text=True)
    assert "Not started" in empty_month
    runs = client.get("/payroll?tab=runs").get_data(as_text=True)
    assert "No payroll runs yet" in runs
    assert client.get("/payroll?month=99&year=1").status_code == 200  # bad params fall back, no 500


def test_dashboard_with_no_staff_shows_empty_state(client):
    html = client.get("/payroll?month=10&year=2026").get_data(as_text=True)
    assert "No active employees for this selection" in html


def test_dashboard_error_is_shown_not_a_server_error(ctx, client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(app_module, "build_payroll_dashboard", boom)
    resp = client.get("/payroll?month=10&year=2026")
    assert resp.status_code == 200 and "could not be loaded" in resp.get_data(as_text=True)


def test_selector_endpoint_lists_nabeel_with_a_reason_then_selectable(ctx, client):
    db, _ = ctx
    sid = add_staff(db, "Nabeel", "EMP600", status="active")
    url = "/payroll/eligible-employees?employment_category=company_staff&month=10&year=2026"
    data = client.get(url).get_json()
    (row,) = data["employees"]
    assert row["employee_name"] == "Nabeel" and row["selectable"] is False
    assert "attendance" in row["blocked_reason"].lower() and data["message"]

    attend(db, sid, _working_dates(2026, 10))
    (row,) = client.get(url).get_json()["employees"]
    assert row["selectable"] is True

    why = client.get("/payroll/eligibility-check?q=nabeel&month=10&year=2026").get_json()
    assert why["results"][0]["selectable"] is True


def test_generate_twice_is_rejected_and_payslip_register_export_show_the_rule(ctx, client):
    db, _ = ctx
    sid = add_staff(db, "Slip Person", "EMP700", salary=27000)
    attend(db, sid, _working_dates(2026, 10)[2:])
    form = {
        "form_action": "generate", "gen_mode": "monthly", "month": "10", "year": "2026",
        "employment_category": "company_staff", "employee_ids": [f"staff:{sid}"],
    }
    first = client.post("/payroll", data=form, follow_redirects=True)
    assert "Payroll calculated" in first.get_data(as_text=True)
    second = client.post("/payroll", data=form, follow_redirects=True)
    assert "Payroll already exists for this period" in second.get_data(as_text=True)
    assert db.execute("SELECT COUNT(*) FROM payroll_runs").fetchone()[0] == 1

    line_id = db.execute("SELECT id FROM payroll_lines").fetchone()[0]
    run_id = db.execute("SELECT id FROM payroll_runs").fetchone()[0]
    slip = client.get(f"/payroll/print/{line_id}").get_data(as_text=True)
    assert "Working Days (excl. Sundays)" in slip and "Calendar Days / Sundays" in slip
    assert "31 / 4" in slip and "25.0 / 27" in slip.replace("\n", "")
    register = client.get(f"/payroll/print-run/{run_id}").get_data(as_text=True)
    assert "Working days" in register and "Payable days" in register and "25000.00" in register
    export = client.get(f"/payroll/export/{run_id}")
    assert export.status_code == 200
    import pandas as pd

    frame = pd.read_excel(io.BytesIO(export.data))
    assert {"working_days", "payable_days", "daily_rate", "calc_basis"} <= set(frame.columns)
    assert frame.loc[0, "payable_days"] == 25 and frame.loc[0, "gross_salary"] == 25000

    dash = client.get("/payroll?month=10&year=2026").get_data(as_text=True)
    assert "Draft" in dash and "₹ 25,000.00" in dash
    view = client.get(f"/payroll?view={run_id}").get_data(as_text=True)
    assert "Payable days" in view


def test_inr_filter_groups_the_indian_way(ctx):
    from app import inr_filter

    assert inr_filter(1234567.5) == "₹ 12,34,567.50"
    assert inr_filter(27000) == "₹ 27,000.00"
    assert inr_filter(999) == "₹ 999.00"
    assert inr_filter(-1500.5) == "-₹ 1,500.50"
    assert inr_filter(None) == "—" and inr_filter("x") == "—"
    assert re.fullmatch(r"₹ 1,00,000\.00", inr_filter(100000))
