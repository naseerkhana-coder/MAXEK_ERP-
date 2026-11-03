"""Payroll: optional staff exit date.

Rule under test: with an exit date, a monthly-salaried employee is paid through that
date (inclusive); the daily-rate divisor stays the FULL month's working days
(calendar days - Sundays). With no exit date nothing changes.

October 2026: 31 days, Sundays on 4/11/18/25 -> 27 working days, daily rate 27000/27 = 1000.
"""
from __future__ import annotations

from datetime import date

import pytest

from payroll_calc import employment_window, in_window
from payroll_service import (
    ensure_staff_not_departed,
    explain_payroll_eligibility,
    list_eligible_employees,
    period_from_month_year,
)

# Reuse the fixtures/helpers of the Sunday-rule suite (same temp-DB harness).
from test_payroll_sunday_rule import (  # noqa: F401  (ctx/client are pytest fixtures)
    _generate,
    _working_dates,
    add_attendance,
    add_staff,
    attend,
    client,
    ctx,
    pay,
)


def set_exit(db, sid, exit_date):
    db.execute("UPDATE staff SET exit_date=? WHERE id=?", (exit_date, sid))
    db.commit()


def oct_days(first, last):
    return [d for d in _working_dates(2026, 10) if date(2026, 10, first) <= d <= date(2026, 10, last)]


# ───────────────────────────── pure window maths ─────────────────────────────


def test_no_exit_date_means_no_window():
    assert employment_window("2025-01-01", None, "2026-10-01", "2026-10-31") is None
    assert employment_window("2025-01-01", "", "2026-10-01", "2026-10-31") is None
    assert employment_window("2025-01-01", "not-a-date", "2026-10-01", "2026-10-31") is None
    assert in_window("2026-10-20", None) is True


def test_window_is_inclusive_and_excludes_sundays_from_working_days():
    w = employment_window("2025-01-01", "2026-10-15", "2026-10-01", "2026-10-31")
    assert (w["window_start"], w["window_end"]) == ("2026-10-01", "2026-10-15")
    assert (w["calendar_days"], w["sundays"], w["working_days"]) == (15, 2, 13)
    assert in_window("2026-10-15", w) and not in_window("2026-10-16", w)
    sunday = employment_window("2025-01-01", "2026-10-18", "2026-10-01", "2026-10-31")
    assert sunday["working_days"] == 15  # Sundays 4, 11, 18 are not working days
    saturday = employment_window("2025-01-01", "2026-10-17", "2026-10-01", "2026-10-31")
    assert saturday["working_days"] == 15  # a Sunday exit pays exactly what the Saturday before does


def test_window_edges():
    # Exit on/after the period end -> whole month; before it starts -> nothing.
    assert employment_window(None, "2026-10-31", "2026-10-01", "2026-10-31")["working_days"] == 27
    assert employment_window(None, "2027-03-01", "2026-10-01", "2026-10-31")["working_days"] == 27
    gone = employment_window(None, "2026-09-30", "2026-10-01", "2026-10-31")
    assert gone["working_days"] == 0 and gone["window_start"] is None
    assert in_window("2026-10-05", gone) is False
    # Exit before joining is an empty window rather than a crash.
    assert employment_window("2026-10-20", "2026-10-10", "2026-10-01", "2026-10-31")["working_days"] == 0


# ───────────────────────────── salary calculation ─────────────────────────────


def test_mid_month_exit_is_prorated_through_exit_date_with_full_month_divisor(ctx):
    db, _ = ctx
    sid = add_staff(db, "Mid Leaver", "EXT100", salary=27000)
    attend(db, sid, oct_days(1, 15))
    set_exit(db, sid, "2026-10-15")
    calc = pay(db, sid, 2026, 10)
    assert calc["working_days"] == 27            # divisor is the full month
    assert calc["entitled_working_days"] == 13   # 1st-15th minus Sundays 4th and 11th
    assert calc["daily_rate"] == 1000.0
    assert calc["payable_days"] == 13
    assert calc["gross_salary"] == 13000.00
    assert calc["unpaid_absence_days"] == 0      # days after the exit are not "absences"
    assert calc["not_employed_days"] == 14
    assert calc["exit_date"] == "2026-10-15"


def test_exit_date_is_paid_inclusive(ctx):
    db, _ = ctx
    sid = add_staff(db, "Inclusive", "EXT101")
    attend(db, sid, oct_days(1, 16))             # 16th (Friday) worked
    set_exit(db, sid, "2026-10-16")
    assert pay(db, sid, 2026, 10)["gross_salary"] == 14000.00  # 14 working days, 16th included


def test_unpaid_absence_before_exit_still_reduces_pay(ctx):
    db, _ = ctx
    sid = add_staff(db, "Absent Leaver", "EXT102")
    attend(db, sid, [d for d in oct_days(1, 15) if d != date(2026, 10, 7)])
    set_exit(db, sid, "2026-10-15")
    calc = pay(db, sid, 2026, 10)
    assert calc["payable_days"] == 12 and calc["gross_salary"] == 12000.00
    assert calc["unpaid_absence_days"] == 1


def test_attendance_after_exit_date_is_not_paid(ctx):
    db, _ = ctx
    sid = add_staff(db, "Stray Rows", "EXT103")
    attend(db, sid, _working_dates(2026, 10))    # whole month recorded by mistake
    set_exit(db, sid, "2026-10-15")
    assert pay(db, sid, 2026, 10)["gross_salary"] == 13000.00


@pytest.mark.parametrize(
    "exit_date,expected_days",
    [
        ("2026-10-17", 15),   # Saturday
        ("2026-10-18", 15),   # Sunday: nothing extra for the Sunday itself
        ("2026-10-19", 16),   # Monday
        ("2026-10-04", 3),    # first Sunday of the month
    ],
)
def test_sunday_and_neighbouring_exits(ctx, exit_date, expected_days):
    db, _ = ctx
    sid = add_staff(db, "Sunday Exit", "EXT110")
    attend(db, sid, _working_dates(2026, 10))
    set_exit(db, sid, exit_date)
    calc = pay(db, sid, 2026, 10)
    assert calc["payable_days"] == expected_days
    assert calc["gross_salary"] == expected_days * 1000.0


def test_joining_and_leaving_in_the_same_month(ctx):
    db, _ = ctx
    sid = add_staff(db, "Short Stay", "EXT120", joining="2026-10-08")
    attend(db, sid, _working_dates(2026, 10))    # attendance outside the stay must not count
    set_exit(db, sid, "2026-10-22")
    calc = pay(db, sid, 2026, 10)
    assert calc["entitled_working_days"] == 13   # 8th-22nd = 15 days minus Sundays 11th, 18th
    assert calc["working_days"] == 27
    assert calc["gross_salary"] == 13000.00


def test_exit_at_or_after_period_end_pays_the_whole_month(ctx):
    db, _ = ctx
    for code, exit_date in (("EXT130", "2026-10-31"), ("EXT131", "2026-12-31")):
        sid = add_staff(db, code, code)
        attend(db, sid, _working_dates(2026, 10))
        set_exit(db, sid, exit_date)
        assert pay(db, sid, 2026, 10)["gross_salary"] == 27000.00


def test_period_after_departure_pays_nothing(ctx):
    db, _ = ctx
    sid = add_staff(db, "Long Gone", "EXT140")
    attend(db, sid, _working_dates(2026, 11))
    set_exit(db, sid, "2026-10-15")
    calc = pay(db, sid, 2026, 11)
    assert calc["payable_days"] == 0 and calc["gross_salary"] == 0 and calc["net_salary"] == 0


def test_no_exit_date_is_calculated_exactly_as_before(ctx):
    db, _ = ctx
    plain = add_staff(db, "No Exit", "EXT150")
    attend(db, plain, [d for d in _working_dates(2026, 10) if d.day not in (6, 7)])
    calc = pay(db, plain, 2026, 10)
    assert calc["gross_salary"] == 25000.00 and calc["exit_date"] is None
    assert calc["entitled_working_days"] == calc["working_days"] == 27 and calc["not_employed_days"] == 0
    # A blank string (what an empty form field would store) behaves like NULL.
    set_exit(db, plain, "")
    assert pay(db, plain, 2026, 10)["gross_salary"] == 25000.00


def test_paid_holiday_after_exit_is_not_paid(ctx):
    db, _ = ctx
    db.execute("INSERT INTO holidays(holiday_date, holiday_name) VALUES('2026-10-14','Before exit')")
    db.execute("INSERT INTO holidays(holiday_date, holiday_name) VALUES('2026-10-21','After exit')")
    db.commit()
    sid = add_staff(db, "Holiday Leaver", "EXT160", holiday_pay="Yes")
    attend(db, sid, [d for d in oct_days(1, 15) if d != date(2026, 10, 14)])
    set_exit(db, sid, "2026-10-15")
    calc = pay(db, sid, 2026, 10)
    assert calc["holiday_pay"] == 1000.00        # the 14th only
    assert calc["gross_salary"] == 13000.00


def test_monthly_summary_path_respects_exit_date(ctx):
    db, _ = ctx
    sid = add_staff(db, "Summary Leaver", "EXT170")
    db.execute(
        "INSERT INTO staff_monthly_attendance(staff_id, year_month, worked_days, half_days, "
        "absent_days, ot_hours, approval_status) VALUES(?,?,?,?,?,?,?)",
        (sid, "2026-10", 13, 0, 14, 0, "Approved"),   # 14 absent = the days after the exit
    )
    db.commit()
    set_exit(db, sid, "2026-10-15")
    calc = pay(db, sid, 2026, 10)
    assert calc["gross_salary"] == 13000.00 and calc["unpaid_absence_days"] == 0

    # Genuine absence before the exit date is still charged.
    db.execute("UPDATE staff_monthly_attendance SET worked_days=12, absent_days=15 WHERE staff_id=?", (sid,))
    db.commit()
    assert pay(db, sid, 2026, 10)["gross_salary"] == 12000.00


# ───────────────────────────── overtime is untouched ─────────────────────────────


def test_sunday_attendance_adds_no_payable_day_but_keeps_its_overtime(ctx):
    db, _ = ctx
    sid = add_staff(db, "OT Person", "EXT180", ot="Yes", ot_rate=100)
    attend(db, sid, oct_days(1, 3))              # Thu-Sat
    add_attendance(db, sid, date(2026, 10, 4), ot_hours=3.0)   # Sunday, 3 OT hours
    add_attendance(db, sid, date(2026, 10, 5), ot_hours=2.0)   # Monday, 2 OT hours
    db.commit()
    calc = pay(db, sid, 2026, 10)
    assert calc["payable_days"] == 4             # Sunday not counted as a payable day
    assert calc["sunday_worked_days"] == 1.0
    assert calc["ot_hours"] == 5.0 and calc["ot_amount"] == 500.00   # both OT entries kept
    assert calc["gross_salary"] == 4000.00 + 500.00


def test_overtime_inside_the_employment_window_is_unaffected_by_exit_date(ctx):
    db, _ = ctx
    plain = add_staff(db, "OT Plain", "EXT181", ot="Yes", ot_rate=100)
    leaver = add_staff(db, "OT Leaver", "EXT182", ot="Yes", ot_rate=100)
    for sid in (plain, leaver):
        attend(db, sid, oct_days(1, 15), ot_hours=1.0)
        add_attendance(db, sid, date(2026, 10, 11), ot_hours=4.0)  # a Sunday inside the window
        db.commit()
    set_exit(db, leaver, "2026-10-15")
    a, b = pay(db, plain, 2026, 10), pay(db, leaver, 2026, 10)
    assert a["ot_amount"] == b["ot_amount"] == (13 * 1.0 + 4.0) * 100
    assert b["gross_salary"] == 13000.00 + 1700.00


# ───────────────────────────── eligibility ─────────────────────────────


def _listed(db, month=10, year=2026):
    start, end = period_from_month_year(month, year)
    return {
        e["staff_name"]
        for e in list_eligible_employees(
            db, "company_staff", period_start=start, period_end=end, include_without_data=True
        )
        if e["employee_type"] == "staff"
    }


def test_staff_who_left_during_the_month_stay_eligible_even_if_now_inactive(ctx):
    db, _ = ctx
    left = add_staff(db, "Left In Oct", "EXT200", status="Inactive")
    set_exit(db, left, "2026-10-15")
    long_gone = add_staff(db, "Left In Sep", "EXT201", status="Inactive")
    set_exit(db, long_gone, "2026-09-30")
    still_active_but_gone = add_staff(db, "Active But Gone", "EXT202", status="Active")
    set_exit(db, still_active_but_gone, "2026-09-10")
    inactive_no_date = add_staff(db, "Inactive No Date", "EXT203", status="Inactive")
    working = add_staff(db, "Working", "EXT204")
    leaves_later = add_staff(db, "Leaves Dec", "EXT205")
    set_exit(db, leaves_later, "2026-12-31")

    october = _listed(db)
    assert "Left In Oct" in october
    assert "Leaves Dec" in october and "Working" in october
    assert "Left In Sep" not in october and "Active But Gone" not in october
    assert "Inactive No Date" not in october        # unchanged rule: inactive, no exit date
    assert "Left In Oct" not in _listed(db, month=11)   # but not for the month after
    assert "Left In Sep" in _listed(db, month=9)        # an earlier month can still be re-run/viewed


def test_inactive_leaver_gets_final_payroll_and_cannot_be_paid_twice(ctx):
    db, _ = ctx
    sid = add_staff(db, "Final Pay", "EXT210", status="Inactive")
    attend(db, sid, oct_days(1, 15))
    set_exit(db, sid, "2026-10-15")
    run_id = _generate(db, [sid])
    db.commit()
    line = db.execute("SELECT * FROM payroll_lines WHERE payroll_run_id=?", (run_id,)).fetchone()
    assert line["gross_salary"] == 13000.00
    with pytest.raises(ValueError, match="already exists"):     # duplicate protection intact
        _generate(db, [sid])
    db.rollback()
    assert db.execute("SELECT COUNT(*) FROM payroll_runs").fetchone()[0] == 1


def test_selecting_staff_who_left_before_the_period_is_refused(ctx):
    db, _ = ctx
    sid = add_staff(db, "Departed", "EXT220")
    attend(db, sid, _working_dates(2026, 10))
    set_exit(db, sid, "2026-09-30")
    with pytest.raises(ValueError, match="left before this period"):
        _generate(db, [sid])
    db.rollback()
    assert db.execute("SELECT COUNT(*) FROM payroll_runs").fetchone()[0] == 0
    ensure_staff_not_departed(db, [("staff", sid)], "2026-09-01")   # earlier period: fine


def test_approved_payroll_keeps_its_stored_amounts_when_an_exit_date_is_added_later(ctx):
    db, _ = ctx
    sid = add_staff(db, "Already Paid", "EXT230")
    attend(db, sid, _working_dates(2026, 10))
    run_id = _generate(db, [sid])
    db.execute("UPDATE payroll_runs SET status='Paid' WHERE id=?", (run_id,))
    db.commit()
    before = dict(db.execute("SELECT * FROM payroll_lines WHERE payroll_run_id=?", (run_id,)).fetchone())
    set_exit(db, sid, "2026-10-10")                  # edited afterwards
    after = dict(db.execute("SELECT * FROM payroll_lines WHERE payroll_run_id=?", (run_id,)).fetchone())
    assert before == after and after["gross_salary"] == 27000.00


def test_eligibility_check_explains_exit_date(ctx):
    db, _ = ctx
    sid = add_staff(db, "Explain Me", "EXT240", status="Inactive")
    attend(db, sid, _working_dates(2026, 10))
    set_exit(db, sid, "2026-09-15")
    start, end = period_from_month_year(10, 2026)
    (report,) = explain_payroll_eligibility(db, "EXT240", period_start=start, period_end=end)
    assert report["listed"] is False
    assert any("Exit date 2026-09-15 is before the period" in r for r in report["reasons"])
    set_exit(db, sid, "2026-10-20")
    (report,) = explain_payroll_eligibility(db, "EXT240", period_start=start, period_end=end)
    assert report["listed"] is True


# ───────────────────────────── staff form ─────────────────────────────


def _staff_form(**extra):
    form = {
        "employee_code": "FRM1", "staff_name": "Form Person", "department": "Accounts",
        "salary_type": "Monthly", "salary_amount": "27000", "ot_applicable": "No",
        "ot_rate_per_hour": "0", "holiday_pay_applicable": "No", "working_hours": "8",
        "joining_date": "2026-01-10", "status": "Active", "company_room_provided": "No",
        "company_food_provided": "No",
    }
    form.update(extra)
    return form


def test_staff_form_saves_exit_date_and_blank_means_none(ctx, client):
    db, _ = ctx
    resp = client.post("/staff", data=_staff_form(exit_date="2026-10-15"), follow_redirects=True)
    assert resp.status_code == 200
    row = db.execute("SELECT * FROM staff WHERE staff_name='Form Person'").fetchone()
    assert row is not None and row["exit_date"] == "2026-10-15"
    html = client.get(f"/staff?edit={row['id']}").get_data(as_text=True)
    assert 'name="exit_date"' in html and 'value="2026-10-15"' in html

    client.post("/staff", data=_staff_form(staff_id=str(row["id"]), exit_date=""), follow_redirects=True)
    assert db.execute("SELECT exit_date FROM staff WHERE id=?", (row["id"],)).fetchone()[0] is None


def test_staff_form_rejects_bad_exit_dates(ctx, client):
    db, _ = ctx
    for bad in ("31/10/2026", "2026-13-40", "2025-12-31"):   # last one is before joining (2026-01-10)
        client.post("/staff", data=_staff_form(staff_name="Bad Exit", exit_date=bad), follow_redirects=True)
    assert db.execute("SELECT COUNT(*) FROM staff WHERE staff_name='Bad Exit'").fetchone()[0] == 0
    ok = client.post("/staff", data=_staff_form(staff_name="Good Exit", exit_date="2026-01-10"), follow_redirects=True)
    assert ok.status_code == 200   # exit on the joining day itself is allowed
    assert db.execute("SELECT exit_date FROM staff WHERE staff_name='Good Exit'").fetchone()[0] == "2026-01-10"
