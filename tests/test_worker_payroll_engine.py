"""Tests for worker payroll hour-based pay rules."""

from modules.worker_payroll_engine import calculate_daily_pay


def test_8hr_full_day():
    r = calculate_daily_pay(800, 8, 8)
    assert r["base_pay"] == 800
    assert r["ot_hours"] == 0
    assert r["gross_pay"] == 800


def test_8hr_partial():
    r = calculate_daily_pay(800, 8, 7)
    assert r["base_pay"] == 700
    assert r["gross_pay"] == 700


def test_8hr_overtime():
    r = calculate_daily_pay(800, 8, 10)
    assert r["base_pay"] == 800
    assert r["ot_hours"] == 2
    assert r["ot_pay"] == 200
    assert r["gross_pay"] == 1000


def test_10hr_partial():
    r = calculate_daily_pay(800, 10, 8)
    assert r["base_pay"] == 640
    assert r["gross_pay"] == 640


def test_10hr_overtime():
    r = calculate_daily_pay(800, 10, 12)
    assert r["base_pay"] == 800
    assert r["ot_hours"] == 2
    assert r["ot_pay"] == 160
    assert r["gross_pay"] == 960
