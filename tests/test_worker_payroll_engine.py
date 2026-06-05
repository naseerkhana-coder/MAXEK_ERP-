"""Tests for worker payroll hour-based pay rules."""

from datetime import datetime

from modules.worker_payroll_engine import (
    apply_deductions,
    calculate_daily_pay,
    next_workflow_status,
    period_cycle_label,
    workflow_step_index,
)


def test_8hr_full_day():
    r = calculate_daily_pay(800, 8, 8)
    assert r["base_pay"] == 800
    assert r["ot_hours"] == 0
    assert r["gross_pay"] == 800


def test_8hr_partial_six_hours():
    r = calculate_daily_pay(800, 8, 6)
    assert r["base_pay"] == 600
    assert r["ot_hours"] == 0
    assert r["gross_pay"] == 600


def test_8hr_partial_seven_hours():
    r = calculate_daily_pay(800, 8, 7)
    assert r["base_pay"] == 700
    assert r["gross_pay"] == 700


def test_8hr_overtime():
    r = calculate_daily_pay(800, 8, 10)
    assert r["base_pay"] == 800
    assert r["ot_hours"] == 2
    assert r["ot_pay"] == 200
    assert r["gross_pay"] == 1000


def test_8hr_overtime_not_eligible():
    r = calculate_daily_pay(800, 8, 10, ot_eligible=False)
    assert r["base_pay"] == 800
    assert r["ot_hours"] == 2
    assert r["ot_pay"] == 0
    assert r["gross_pay"] == 800


def test_10hr_partial_eight_hours():
    r = calculate_daily_pay(1000, 10, 8)
    assert r["base_pay"] == 800
    assert r["gross_pay"] == 800


def test_10hr_full_day():
    r = calculate_daily_pay(1000, 10, 10)
    assert r["base_pay"] == 1000
    assert r["ot_hours"] == 0
    assert r["gross_pay"] == 1000


def test_10hr_daily_800_twelve_hours():
    r = calculate_daily_pay(800, 10, 12)
    assert r["base_pay"] == 800
    assert r["ot_hours"] == 2
    assert r["ot_pay"] == 160
    assert r["gross_pay"] == 960


def test_deductions_net():
    d = apply_deductions(1000, 200, [{"amount": 100}, {"amount": 50}])
    assert d["gross_salary"] == 1000
    assert d["total_deductions"] == 150
    assert d["net_salary"] == 850


def test_10hr_overtime():
    r = calculate_daily_pay(1000, 10, 12)
    assert r["base_pay"] == 1000
    assert r["ot_hours"] == 2
    assert r["ot_pay"] == 200
    assert r["gross_pay"] == 1200


def test_10hr_overtime_not_eligible():
    r = calculate_daily_pay(1000, 10, 12, ot_eligible="No")
    assert r["base_pay"] == 1000
    assert r["ot_pay"] == 0
    assert r["gross_pay"] == 1000


def test_period_cycle_advance():
    start = datetime(2026, 6, 1)
    end = datetime(2026, 6, 15)
    assert period_cycle_label(start, end) == "Advance"


def test_period_cycle_final():
    start = datetime(2026, 6, 16)
    end = datetime(2026, 6, 30)
    assert period_cycle_label(start, end) == "Final"


def test_workflow_steps():
    assert workflow_step_index("Draft") == 0
    assert workflow_step_index("Prepared") == 1
    assert workflow_step_index("Calculated") == 1
    assert workflow_step_index("Approved") == 3
    assert workflow_step_index("Paid") == 5


def test_workflow_next_status():
    assert next_workflow_status("Draft") == "Prepared"
    assert next_workflow_status("Prepared") == "Checked"
    assert next_workflow_status("Checked") == "Approved"
    assert next_workflow_status("Paid") is None
