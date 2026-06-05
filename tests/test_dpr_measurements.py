"""DPR measurement book calculations — average width, quantities, BBS weight."""

from modules.dpr_measurements import (
    average_dimension,
    build_structured_measurement_record,
    compute_bbs_length_m,
    compute_measurement,
    compute_steel_bbs_row,
    should_use_average_width,
    steel_bbs_weight_kg,
)


def test_average_width_two_values():
    avg, formula, _ = average_dimension([2.0, 4.0])
    assert avg == 3.0
    assert "2" in formula and "4" in formula


def test_average_width_three_values():
    avg, _, _ = average_dimension([2.0, 4.0, 6.0])
    assert avg == 4.0
    assert should_use_average_width([2.0, 4.0, 6.0])


def test_m3_quantity_with_average_width():
    calc = compute_measurement("M3", [10.0], [2.0, 4.0, 6.0], [1.5], 2.0, "Average")
    assert calc["avg_width"] == 4.0
    assert calc["calculated_quantity"] == round(10.0 * 4.0 * 1.5 * 2.0, 4)


def test_m2_structured_row_sum():
    row = build_structured_measurement_record(
        "SQM",
        length=5.0,
        width=2.0,
        width_2=4.0,
        nos=3.0,
    )
    assert row["avg_width"] == 3.0
    assert row["calculated_quantity"] == round(5.0 * 3.0 * 3.0, 4)


def test_bbs_weight_formula():
    kg = steel_bbs_weight_kg(nos=10, length_m=12.0, dia_mm=16.0)
    expected = round((16.0**2 * 12.0 * 10) / 162.0, 4)
    assert kg == expected


def test_bbs_l_bar_length_and_weight():
    length_m = compute_bbs_length_m("L_BAR", {"dim_a": 1000, "dim_b": 500})
    assert length_m == 1.5
    row = compute_steel_bbs_row("M1", 12, 0, 5, 0, shape_code="L_BAR", dim_a=1000, dim_b=500)
    assert row["length_m"] == 1.5
    assert row["weight_kg"] > 0
    assert row["weight_mt"] == round(row["weight_kg"] / 1000.0, 4)
