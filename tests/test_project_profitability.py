"""Tests for project profitability calculations and traffic lights."""

from modules.project_profitability_db import (
    calc_profit_pct,
    profit_traffic_light,
)


def test_calc_profit_pct_normal():
    assert calc_profit_pct(25, 100) == 25.0
    assert calc_profit_pct(-10, 200) == -5.0


def test_calc_profit_pct_zero_project_value():
    assert calc_profit_pct(100, 0) is None
    assert calc_profit_pct(-50, 0) is None


def test_traffic_light_green():
    status, css, label = profit_traffic_light(25.0, 1000)
    assert status == "green"
    assert "green" in css
    assert "20" in label


def test_traffic_light_yellow():
    status, _, _ = profit_traffic_light(15.0, 500)
    assert status == "yellow"


def test_traffic_light_red():
    status, _, _ = profit_traffic_light(5.0, 500)
    assert status == "red"


def test_traffic_light_critical_loss():
    status, css, label = profit_traffic_light(30.0, -1)
    assert status == "critical"
    assert "critical" in css
    assert "Loss" in label


def test_traffic_light_loss_overrides_high_pct():
    status, _, _ = profit_traffic_light(50.0, -100)
    assert status == "critical"
