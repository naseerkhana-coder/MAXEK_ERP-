from modules.database import format_decimal_hours


def test_format_decimal_hours_zero():
    assert format_decimal_hours(0) == "00:00"
    assert format_decimal_hours(None) == "00:00"


def test_format_decimal_hours_whole_and_fractional():
    assert format_decimal_hours(8) == "08:00"
    assert format_decimal_hours(8.5) == "08:30"
    assert format_decimal_hours(1.25) == "01:15"


def test_format_decimal_hours_rounding():
    assert format_decimal_hours(7.99) == "07:59"
