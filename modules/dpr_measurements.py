"""BOQ-unit-based flexible DPR measurement calculations."""

from __future__ import annotations

import json
import re


def normalize_boq_unit(unit):
    text = str(unit or "").strip().upper()
    text = text.replace("²", "2").replace("³", "3").replace(".", "").replace(" ", "")
    if text in {"SQM", "M2", "SQUAREMETER", "SQUAREMETRE", "SQMT"}:
        return "SQM"
    if text in {"M3", "CUM", "CUBICMETER", "CUBICMETRE"}:
        return "M3"
    if text in {"KG", "KGS", "KILOGRAM", "KILOGRAMS"}:
        return "KG"
    if text in {"RM", "RMT", "RUNNINGMETER", "RUNNINGMETRE", "RMT"}:
        return "RM"
    if text in {"NOS", "NO", "NUM", "NUMBERS", "EA", "EACH", "PCS", "PC"}:
        return "NOS"
    if text in {"TON", "MT", "TONNE", "TONNES"}:
        return "TON"
    if "SQM" in text or text == "M2":
        return "SQM"
    if "M3" in text or text == "CUM":
        return "M3"
    return text or "SQM"


def is_steel_boq_entry(unit_raw, description=""):
    """Steel shape entry only when BOQ unit is MT/Ton (not by description — area BOQ stays L×W average)."""
    _ = description
    if normalize_boq_unit(unit_raw) == "TON":
        return True
    unit_text = str(unit_raw or "").upper().replace(" ", "")
    return any(token in unit_text for token in ("MT", "TON", "TONNE", "METRICTON"))


def unit_entry_label(unit_family):
    labels = {
        "SQM": "Square metre (SQM) — Length × Width × Qty",
        "M3": "Cubic metre (M3) — Length × Width × Depth × Qty",
        "KG": "Kilogram (KG) — enter total quantity",
        "RM": "Running metre (RM) — Length × Qty",
        "NOS": "Numbers (NOS) — enter quantity",
        "TON": "Steel (TON/MT) — shape code, dimensions, dia, nos → weight in MT",
    }
    return labels.get(unit_family, f"Unit {unit_family}")


def _parse_values(raw_list):
    values = []
    for item in raw_list or []:
        try:
            val = float(item)
        except (TypeError, ValueError):
            continue
        if val > 0:
            values.append(val)
    return values


def average_dimension(values):
    nums = _parse_values(values)
    if not nums:
        return 0.0, "", ""
    if len(nums) == 1:
        v = nums[0]
        return v, str(v), str(v)
    parts = " + ".join(_fmt_num(n) for n in nums)
    avg = sum(nums) / len(nums)
    formula = f"({parts}) / {len(nums)}"
    return avg, formula, f"{formula} = {_fmt_num(avg)}"


def _fmt_num(value):
    text = f"{float(value):.4f}".rstrip("0").rstrip(".")
    return text if text else "0"


def compute_measurement(unit_family, lengths, widths, depths, qty, method="Normal"):
    unit_family = normalize_boq_unit(unit_family)
    qty_val = float(qty or 0)
    avg_l, l_formula, l_display = average_dimension(lengths)
    avg_w, w_formula, w_display = average_dimension(widths)
    avg_d, d_formula, d_display = average_dimension(depths)

    lines = []
    steps = []
    total = 0.0

    if unit_family == "SQM":
        if avg_l <= 0 or avg_w <= 0:
            return _empty_result(unit_family, method, lines)
        base = avg_l * avg_w
        if l_display:
            lines.append(f"Average Length: {l_display}")
        if w_display:
            lines.append(f"Average Width: {w_display}")
        if qty_val > 0:
            lines.append(f"Qty: {_fmt_num(qty_val)}")
            steps = [_fmt_num(avg_l), "×", _fmt_num(avg_w), "×", _fmt_num(qty_val)]
            total = base * qty_val
        else:
            steps = [_fmt_num(avg_l), "×", _fmt_num(avg_w)]
            total = base
        lines.append(f"Final: {' '.join(steps)} = {_fmt_num(total)} {unit_family}")

    elif unit_family == "M3":
        if avg_l <= 0 or avg_w <= 0 or avg_d <= 0:
            return _empty_result(unit_family, method, lines)
        base = avg_l * avg_w * avg_d
        if l_display:
            lines.append(f"Average Length: {l_display}")
        if w_display:
            lines.append(f"Average Width: {w_display}")
        if d_display:
            lines.append(f"Average Depth: {d_display}")
        if qty_val > 0:
            lines.append(f"Qty: {_fmt_num(qty_val)}")
            steps = [_fmt_num(avg_l), "×", _fmt_num(avg_w), "×", _fmt_num(avg_d), "×", _fmt_num(qty_val)]
            total = base * qty_val
        else:
            steps = [_fmt_num(avg_l), "×", _fmt_num(avg_w), "×", _fmt_num(avg_d)]
            total = base
        lines.append(f"Final: {' '.join(steps)} = {_fmt_num(total)} {unit_family}")

    elif unit_family == "RM":
        if avg_l <= 0:
            return _empty_result(unit_family, method, lines)
        if l_display:
            lines.append(f"Average Length: {l_display}")
        if qty_val > 0:
            lines.append(f"Qty: {_fmt_num(qty_val)}")
            steps = [_fmt_num(avg_l), "×", _fmt_num(qty_val)]
            total = avg_l * qty_val
        else:
            steps = [_fmt_num(avg_l)]
            total = avg_l
        lines.append(f"Final: {' '.join(steps)} = {_fmt_num(total)} {unit_family}")

    elif unit_family in {"NOS", "KG", "TON"}:
        if qty_val <= 0:
            return _empty_result(unit_family, method, lines)
        lines.append(f"Qty: {_fmt_num(qty_val)}")
        total = qty_val
        lines.append(f"Final: {_fmt_num(total)} {unit_family}")
        avg_l = avg_w = avg_d = 0.0

    else:
        if avg_l > 0 and avg_w > 0:
            base = avg_l * avg_w * (avg_d if avg_d > 0 else 1.0)
            total = base * qty_val if qty_val > 0 else base
        elif qty_val > 0:
            total = qty_val
        lines.append(f"Final: {_fmt_num(total)} {unit_family}")

    return {
        "unit_family": unit_family,
        "measurement_method": method,
        "avg_length": round(avg_l, 4),
        "avg_width": round(avg_w, 4),
        "avg_depth": round(avg_d, 4),
        "qty": qty_val,
        "calculated_quantity": round(total, 4),
        "unit": unit_family,
        "preview_lines": lines,
        "length_formula": l_formula,
        "width_formula": w_formula,
        "depth_formula": d_formula,
        "lengths": _parse_values(lengths),
        "widths": _parse_values(widths),
        "depths": _parse_values(depths),
    }


def _empty_result(unit_family, method, lines):
    return {
        "unit_family": unit_family,
        "measurement_method": method,
        "avg_length": 0.0,
        "avg_width": 0.0,
        "avg_depth": 0.0,
        "qty": 0.0,
        "calculated_quantity": 0.0,
        "unit": unit_family,
        "preview_lines": lines or ["Enter measurements to see preview."],
        "length_formula": "",
        "width_formula": "",
        "depth_formula": "",
        "lengths": [],
        "widths": [],
        "depths": [],
    }


def build_measurement_record(unit_family, method, lengths, widths, depths, qty):
    calc = compute_measurement(unit_family, lengths, widths, depths, qty, method)
    lengths_p = calc["lengths"]
    widths_p = calc["widths"]
    depths_p = calc["depths"]
    return {
        "measurement_type": calc["unit_family"],
        "measurement_method": method,
        "unit": calc["unit"],
        "qty": calc["qty"],
        "lengths": lengths_p,
        "widths": widths_p,
        "depths": depths_p,
        "length_1": lengths_p[0] if len(lengths_p) > 0 else 0.0,
        "length_2": lengths_p[1] if len(lengths_p) > 1 else 0.0,
        "width_1": widths_p[0] if len(widths_p) > 0 else 0.0,
        "width_2": widths_p[1] if len(widths_p) > 1 else 0.0,
        "depth": calc["avg_depth"],
        "height": 0.0,
        "avg_length": calc["avg_length"],
        "avg_width": calc["avg_width"],
        "avg_depth": calc["avg_depth"],
        "calculated_quantity": calc["calculated_quantity"],
        "preview_lines": calc["preview_lines"],
        "dimensions_json": json.dumps(
            {
                "method": method,
                "lengths": lengths_p,
                "widths": widths_p,
                "depths": depths_p,
                "qty": calc["qty"],
                "formulas": {
                    "length": calc["length_formula"],
                    "width": calc["width_formula"],
                    "depth": calc["depth_formula"],
                },
            }
        ),
        "nos": calc["qty"] if calc["unit_family"] == "NOS" else 0,
        "dia_mm": 0,
        "bend": 0,
    }
