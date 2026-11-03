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


def test_no_exit_date_does_not_restrict_an_established_employee():
    for exit_date in (None, "", "not-a-date"):
        w = employment_window("2025-01-01", exit_date, "2026-10-01", "2026-10-31")
        assert w["restricted"] is False and w["working_days"] == 27 and w["exit_date"] is None
    assert employment_window("2025-01-01", None, "bad", "2026-10-31") is None
    assert in_window("2026-10-20", None) is True


def test_missing_exit_date_does_not_disable_joining_date_proration():
    w = employment_window("2026-10-15", None, "2026-10-01", "2026-10-31")
    assert (w["window_start"], w["window_end"]) == ("2026-10-15", "2026-10-31")
    assert w["restricted"] is True and w["working_days"] == 15   # 17 days minus Sundays 18th, 25th
    assert employment_window(None, None, "2026-10-01", "2026-10-31")["restricted"] is False
    later = employment_window("2026-11-05", None, "2026-10-01", "2026-10-31")
    assert later["working_days"] == 0 and later["window_start"] is None   # joins after the period


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
    assert employment_window(None, "2026-10-31", "2026-10-01", "2026-10-31")["restricted"] is False
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


# ═════════════════════════ corrections: window, OT, summaries, display ═════════════════════════

from payroll_service import PayrollAttendanceError, validate_monthly_attendance_basis  # noqa: E402


def set_join(db, sid, joining):
    db.execute("UPDATE staff SET joining_date=? WHERE id=?", (joining, sid))
    db.commit()


def add_summary(db, sid, worked, half, absent, ot=0, ym="2026-10"):
    db.execute(
        "INSERT INTO staff_monthly_attendance(staff_id, year_month, worked_days, half_days, "
        "absent_days, ot_hours, approval_status) VALUES(?,?,?,?,?,?,?)",
        (sid, ym, worked, half, absent, ot, "Approved"),
    )
    db.commit()


# 1 ─ the window starts at the joining date even without an exit date

def test_joiner_without_exit_date_is_prorated_from_joining_date(ctx):
    db, _ = ctx
    sid = add_staff(db, "Joiner Only", "COR100", joining="2026-10-15")
    attend(db, sid, _working_dates(2026, 10))      # rows before joining must not be paid
    calc = pay(db, sid, 2026, 10)
    assert calc["exit_date"] is None and calc["employment_restricted"] is True
    assert calc["entitled_working_days"] == 15 and calc["working_days"] == 27
    assert calc["payable_days"] == 15 and calc["gross_salary"] == 15000.00
    assert calc["window_start"] == "2026-10-15" and calc["window_end"] == "2026-10-31"


def test_established_employee_without_exit_date_is_unchanged(ctx):
    db, _ = ctx
    sid = add_staff(db, "Established", "COR101", joining="2024-03-01")
    attend(db, sid, _working_dates(2026, 10))
    calc = pay(db, sid, 2026, 10)
    assert calc["employment_restricted"] is False and calc["gross_salary"] == 27000.00


def test_joining_and_exit_both_bound_the_window_inclusively(ctx):
    db, _ = ctx
    sid = add_staff(db, "Both Ends", "COR102", joining="2026-10-05")   # Monday
    set_exit(db, sid, "2026-10-09")                                    # Friday
    attend(db, sid, _working_dates(2026, 10))
    calc = pay(db, sid, 2026, 10)
    assert calc["entitled_working_days"] == 5 and calc["gross_salary"] == 5000.00


# 2 ─ attendance earnings and overtime outside the window are excluded

def test_overtime_before_joining_and_after_exit_is_excluded_but_in_window_sunday_ot_is_kept(ctx):
    db, _ = ctx
    sid = add_staff(db, "OT Window", "COR110", joining="2026-10-06", ot="Yes", ot_rate=100)
    set_exit(db, sid, "2026-10-15")
    add_attendance(db, sid, date(2026, 10, 5), ot_hours=9.0)    # Monday, before joining
    add_attendance(db, sid, date(2026, 10, 4), ot_hours=9.0)    # Sunday, before joining
    add_attendance(db, sid, date(2026, 10, 7), ot_hours=2.0)    # in window
    add_attendance(db, sid, date(2026, 10, 11), ot_hours=3.0)   # SUNDAY in window: kept
    add_attendance(db, sid, date(2026, 10, 16), ot_hours=9.0)   # after exit
    add_attendance(db, sid, date(2026, 10, 18), ot_hours=9.0)   # Sunday after exit
    db.commit()
    calc = pay(db, sid, 2026, 10)
    assert calc["ot_hours"] == 5.0 and calc["ot_amount"] == 500.00
    assert calc["payable_days"] == 1                 # only the 7th counts; the Sunday adds no day
    assert calc["sunday_worked_days"] == 1.0
    assert calc["gross_salary"] == 1000.00 + 500.00


def test_attendance_earnings_outside_the_window_are_excluded(ctx):
    db, _ = ctx
    sid = add_staff(db, "Outside Rows", "COR111", joining="2026-10-12")
    set_exit(db, sid, "2026-10-20")
    attend(db, sid, _working_dates(2026, 10))
    calc = pay(db, sid, 2026, 10)
    assert calc["entitled_working_days"] == 8        # 12th-20th = 9 days minus Sunday 18th
    assert calc["gross_salary"] == 8000.00


def test_overtime_for_unrestricted_staff_is_unchanged(ctx):
    db, _ = ctx
    sid = add_staff(db, "OT Normal", "COR112", ot="Yes", ot_rate=100)
    attend(db, sid, _working_dates(2026, 10), ot_hours=1.0)
    add_attendance(db, sid, date(2026, 10, 4), ot_hours=2.0)    # a Sunday
    db.commit()
    assert pay(db, sid, 2026, 10)["ot_amount"] == (27 + 2) * 100.0


# 3 ─ monthly summaries are validated, never guessed

def test_full_month_summary_for_a_leaver_is_refused_with_a_clear_message(ctx):
    db, _ = ctx
    sid = add_staff(db, "Summary Leaver", "COR120")
    add_summary(db, sid, 13, 0, 14)                  # whole-month totals: absences "probably" after exit
    set_exit(db, sid, "2026-10-15")
    with pytest.raises(PayrollAttendanceError) as exc:
        pay(db, sid, 2026, 10)
    msg = str(exc.value)
    assert "Summary Leaver" in msg and "27 days" in msg
    assert "2026-10-01 to 2026-10-15" in msg and "13 working days" in msg
    assert "dated attendance" in msg


def test_full_month_summary_for_a_joiner_without_exit_date_is_refused_too(ctx):
    db, _ = ctx
    sid = add_staff(db, "Summary Joiner", "COR121", joining="2026-10-15")
    add_summary(db, sid, 27, 0, 0)
    with pytest.raises(PayrollAttendanceError, match="2026-10-15 to 2026-10-31"):
        pay(db, sid, 2026, 10)


@pytest.mark.parametrize(
    "worked,half,absent,expected",
    [
        (13, 0, 0, 13000.00),   # explicit in-window entry, working-day basis
        (11, 0, 2, 11000.00),   # 2 genuine absences inside the window
        (15, 0, 0, 13000.00),   # calendar basis (Sundays included), capped at 13 working days
        (12, 1, 0, 12500.00),   # 12 full + 1 half day (halves are entries; present = 12.5)
    ],
)
def test_explicit_in_window_summary_entry_is_accepted_as_entered(ctx, worked, half, absent, expected):
    db, _ = ctx
    sid = add_staff(db, "Valid Summary", "COR122")
    add_summary(db, sid, worked, half, absent)
    set_exit(db, sid, "2026-10-15")
    assert pay(db, sid, 2026, 10)["gross_salary"] == expected


def test_dated_attendance_in_window_is_used_when_the_summary_does_not_fit(ctx):
    db, _ = ctx
    sid = add_staff(db, "Dated Wins", "COR123")
    add_summary(db, sid, 13, 0, 14)                  # invalid for the window
    attend(db, sid, oct_days(1, 15))
    set_exit(db, sid, "2026-10-15")
    assert pay(db, sid, 2026, 10)["gross_salary"] == 13000.00


def test_unrestricted_summary_behaviour_is_unchanged(ctx):
    db, _ = ctx
    sid = add_staff(db, "Plain Summary", "COR124")
    add_summary(db, sid, 25, 0, 2)
    assert pay(db, sid, 2026, 10)["gross_salary"] == 25000.00


def test_person_not_employed_in_the_period_needs_no_attendance_and_pays_nothing(ctx):
    db, _ = ctx
    sid = add_staff(db, "Left Earlier", "COR125")
    add_summary(db, sid, 27, 0, 0, ym="2026-11")
    set_exit(db, sid, "2026-10-15")
    assert pay(db, sid, 2026, 11)["gross_salary"] == 0


def test_validation_lists_every_problem_and_generation_creates_nothing(ctx):
    db, _ = ctx
    bad1 = add_staff(db, "Bad One", "COR130")
    bad2 = add_staff(db, "Bad Two", "COR131", joining="2026-10-20")
    good = add_staff(db, "Good One", "COR132")
    for sid in (bad1, bad2):
        add_summary(db, sid, 27, 0, 0)
    attend(db, good, _working_dates(2026, 10))
    set_exit(db, bad1, "2026-10-10")
    rows = [dict(db.execute("SELECT * FROM staff WHERE id=?", (s,)).fetchone()) for s in (bad1, bad2, good)]
    problems = validate_monthly_attendance_basis(db, rows, "2026-10-01", "2026-10-31")
    assert len(problems) == 2 and "Bad One" in problems[0] and "Bad Two" in problems[1]
    with pytest.raises(ValueError, match="Attendance does not match employment dates"):
        _generate(db, [bad1, bad2, good])
    db.rollback()
    assert db.execute("SELECT COUNT(*) FROM payroll_runs").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM payroll_lines").fetchone()[0] == 0


def test_validation_message_reaches_the_user_and_blocks_the_run(ctx, client):
    db, _ = ctx
    sid = add_staff(db, "Visible Error", "COR133")
    add_summary(db, sid, 27, 0, 0)
    set_exit(db, sid, "2026-10-15")
    form = {
        "form_action": "generate", "gen_mode": "monthly", "month": "10", "year": "2026",
        "employment_category": "company_staff", "employee_ids": [f"staff:{sid}"],
    }
    html = client.post("/payroll", data=form, follow_redirects=True).get_data(as_text=True)
    assert "Attendance does not match employment dates" in html and "Visible Error" in html
    assert db.execute("SELECT COUNT(*) FROM payroll_runs").fetchone()[0] == 0


# 4 ─ exit date is shown on detail, payslip, register, export and dashboard

def test_exit_date_is_shown_on_detail_payslip_register_export_and_dashboard(ctx, client):
    db, _ = ctx
    leaver = add_staff(db, "Shown Leaver", "COR140", status="Inactive")
    stayer = add_staff(db, "Shown Stayer", "COR141")
    attend(db, leaver, oct_days(1, 15))
    attend(db, stayer, _working_dates(2026, 10))
    set_exit(db, leaver, "2026-10-15")
    run_id = _generate(db, [leaver, stayer])
    db.commit()
    lines = {r["staff_id"]: r["id"] for r in db.execute("SELECT id, staff_id FROM payroll_lines")}

    slip = client.get(f"/payroll/print/{lines[leaver]}").get_data(as_text=True)
    assert "Exit Date" in slip and "2026-10-15" in slip and "Employed This Period" in slip
    stayer_slip = client.get(f"/payroll/print/{lines[stayer]}").get_data(as_text=True)
    assert "Exit Date" not in stayer_slip and "Employed This Period" not in stayer_slip

    register = client.get(f"/payroll/print-run/{run_id}").get_data(as_text=True)
    assert register.count("Exit: 2026-10-15") == 1          # only the leaver

    detail = client.get(f"/payroll?view={run_id}").get_data(as_text=True)
    assert detail.count("Exit: 2026-10-15") == 1

    dash = client.get("/payroll?month=10&year=2026").get_data(as_text=True)
    assert "Exit 2026-10-15" in dash

    import pandas as pd
    export = client.get(f"/payroll/export/{run_id}")
    frame = pd.read_excel(io.BytesIO(export.data))
    got = dict(zip(frame["employee_name"], frame["exit_date"].fillna("")))
    assert got["Shown Leaver"] == "2026-10-15" and got["Shown Stayer"] == ""


# 5 ─ history and duplicate protection survive the corrections

def test_paid_history_and_duplicate_protection_survive(ctx):
    db, _ = ctx
    sid = add_staff(db, "History", "COR150", joining="2026-10-15")
    attend(db, sid, _working_dates(2026, 10))
    run_id = _generate(db, [sid])
    db.execute("UPDATE payroll_runs SET status='Paid' WHERE id=?", (run_id,))
    db.commit()
    before = dict(db.execute("SELECT * FROM payroll_lines WHERE payroll_run_id=?", (run_id,)).fetchone())
    set_exit(db, sid, "2026-10-20")                  # edited afterwards
    set_join(db, sid, "2026-10-01")
    after = dict(db.execute("SELECT * FROM payroll_lines WHERE payroll_run_id=?", (run_id,)).fetchone())
    assert before == after and after["gross_salary"] == 15000.00
    with pytest.raises(ValueError, match="already exists"):
        _generate(db, [sid])
    db.rollback()
    assert db.execute("SELECT COUNT(*) FROM payroll_runs").fetchone()[0] == 1


import io  # noqa: E402
