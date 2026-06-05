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
        "TON": "Steel (TON/MT) — BBS or shape → weight in MT",
    }
    return labels.get(unit_family, f"Unit {unit_family}")


def boq_measurement_type_label(unit_family: str) -> str:
    """Human-readable measurement type from BOQ unit."""
    unit_family = normalize_boq_unit(unit_family)
    mapping = {
        "M3": "Volume (M3)",
        "SQM": "Area (M2/SQM)",
        "RM": "Running metre",
        "NOS": "Count (Nos)",
        "KG": "Weight (Kg)",
        "TON": "Steel (Ton/MT)",
    }
    return mapping.get(unit_family, unit_family or "General")


def should_use_average_width(widths: list) -> bool:
    """Use average width when two or more non-zero widths are entered."""
    return len(_parse_values(widths)) >= 2


BBS_SHAPE_OPTIONS = (
    ("STRAIGHT", "Straight Bar"),
    ("RING", "Ring"),
    ("STIRRUP", "Stirrup"),
    ("L_BAR", "L Bar"),
    ("U_BAR", "U Bar"),
    ("BENT_UP", "Bent Up Bar"),
    ("BENT_BAR", "Bent Bar"),
    ("CUSTOM", "Custom Shape"),
)


def bbs_shape_label(shape_code: str) -> str:
    code = str(shape_code or "").strip().upper()
    for key, label in BBS_SHAPE_OPTIONS:
        if key == code:
            return label
    return code or "Shape"


def compute_bbs_length_m(shape_code: str, dims: dict) -> float:
    """Total cut length (m) from shape code and leg fields A–F (mm unless noted)."""
    code = str(shape_code or "STRAIGHT").strip().upper()
    a = float(dims.get("dim_a") or dims.get("a") or 0)
    b = float(dims.get("dim_b") or dims.get("b") or 0)
    c = float(dims.get("dim_c") or dims.get("c") or 0)
    d = float(dims.get("dim_d") or dims.get("d") or 0)
    e = float(dims.get("dim_e") or dims.get("e") or 0)
    f = float(dims.get("dim_f") or dims.get("f") or 0)
    length_m = float(dims.get("length_m") or 0)

    if length_m > 0:
        return round(length_m, 4)

    mm_total = 0.0
    if code in {"STRAIGHT", "CUSTOM"}:
        mm_total = a or length_m * 1000
    elif code in {"RING", "STIRRUP"}:
        mm_total = a + b + c + d + e + f
        if mm_total <= 0:
            mm_total = 2 * (a + b) if a and b else 0
    elif code == "L_BAR":
        mm_total = a + b
    elif code == "U_BAR":
        mm_total = a + b + c
    elif code in {"BENT_UP", "BENT_BAR"}:
        bend = float(dims.get("bend_factor") or dims.get("bend") or 1.0) or 1.0
        mm_total = (a + b) * bend
    else:
        mm_total = sum(v for v in (a, b, c, d, e, f) if v > 0)

    if mm_total <= 0:
        return 0.0
    return round(mm_total / 1000.0, 4)


def compute_steel_bbs_row(
    bar_mark: str,
    dia_mm: float,
    spacing_mm: float,
    nos: float,
    length_m: float,
    *,
    shape_code: str = "STRAIGHT",
    dim_a: float = 0,
    dim_b: float = 0,
    dim_c: float = 0,
    dim_d: float = 0,
    dim_e: float = 0,
    dim_f: float = 0,
    shape_image_path: str = "",
) -> dict:
    dims = {
        "dim_a": dim_a,
        "dim_b": dim_b,
        "dim_c": dim_c,
        "dim_d": dim_d,
        "dim_e": dim_e,
        "dim_f": dim_f,
        "length_m": length_m,
    }
    cut_length_m = compute_bbs_length_m(shape_code, dims)
    if cut_length_m <= 0 and length_m > 0:
        cut_length_m = float(length_m)
    weight_kg = steel_bbs_weight_kg(nos, cut_length_m, dia_mm)
    weight_mt = round(weight_kg / 1000.0, 4)
    return {
        "bar_mark": (bar_mark or "").strip(),
        "shape_code": str(shape_code or "STRAIGHT").upper(),
        "shape_name": bbs_shape_label(shape_code),
        "diameter_mm": float(dia_mm or 0),
        "spacing_mm": float(spacing_mm or 0),
        "nos": float(nos or 0),
        "dim_a": float(dim_a or 0),
        "dim_b": float(dim_b or 0),
        "dim_c": float(dim_c or 0),
        "dim_d": float(dim_d or 0),
        "dim_e": float(dim_e or 0),
        "dim_f": float(dim_f or 0),
        "length_m": cut_length_m,
        "weight_kg": weight_kg,
        "weight_mt": weight_mt,
        "shape_image_path": shape_image_path or "",
        "remarks": "",
    }


def measurement_include_in_bill(default_yes: bool = True) -> int:
    return 1 if default_yes else 0


def steel_bbs_weight_kg(nos: float, length_m: float, dia_mm: float) -> float:
    if nos <= 0 or length_m <= 0 or dia_mm <= 0:
        return 0.0
    return round((float(dia_mm) ** 2 * float(length_m) * float(nos)) / 162.0, 4)


def steel_bbs_weight_mt(nos: float, length_m: float, dia_mm: float) -> float:
    return round(steel_bbs_weight_kg(nos, length_m, dia_mm) / 1000.0, 4)


def sum_measurement_rows(rows: list, unit_family: str) -> float:
    """Sum calculated quantities across measurement rows (same unit family)."""
    unit_family = normalize_boq_unit(unit_family)
    return round(
        sum(float(r.get("calculated_quantity") or 0) for r in (rows or [])),
        4,
    )


def sum_billable_measurement_rows(rows: list) -> float:
    """Sum quantities marked for client billing."""
    return round(
        sum(
            float(r.get("calculated_quantity") or 0)
            for r in (rows or [])
            if int(r.get("include_in_client_bill", 1) or 0) == 1
        ),
        4,
    )


def build_structured_measurement_record(
    unit_family: str,
    *,
    length: float = 0,
    width: float = 0,
    width_2: float = 0,
    width_3: float = 0,
    depth: float = 0,
    height: float = 0,
    thickness: float = 0,
    nos: float = 0,
    force_average_width: bool | None = None,
) -> dict:
    """
    Single measurement row with explicit L/W/W2/W3/D/H/thickness/Nos.
    Average width applies when W2 or W3 is filled (or force_average_width=True).
    """
    unit_family = normalize_boq_unit(unit_family)
    widths = [width, width_2, width_3]
    depths = []
    if depth > 0:
        depths.append(depth)
    elif height > 0:
        depths.append(height)
    elif thickness > 0:
        depths.append(thickness)
    lengths = [length] if length > 0 else []
    use_avg = force_average_width
    if use_avg is None:
        use_avg = should_use_average_width(widths)
    method = "Average" if use_avg and should_use_average_width(widths) else "Normal"
    qty = float(nos or 0) if unit_family == "NOS" else float(nos or 0)
    if unit_family == "NOS":
        qty = max(qty, float(nos or 0))
    calc = compute_measurement(unit_family, lengths, widths, depths, qty, method)
    record = build_measurement_record(unit_family, method, lengths, widths, depths, qty)
    record["width_3"] = float(width_3 or 0)
    record["thickness"] = float(thickness or 0)
    record["height"] = float(height or 0)
    dims = json.loads(record.get("dimensions_json") or "{}")
    dims.update(
        {
            "width_3": float(width_3 or 0),
            "thickness": float(thickness or 0),
            "height": float(height or 0),
            "structured_row": True,
        }
    )
    record["dimensions_json"] = json.dumps(dims)
    record["preview_lines"] = calc.get("preview_lines") or record.get("preview_lines")
    return record


def bbs_rows_to_steel_measurements(bbs_rows: list) -> list:
    """Convert steel BBS schedule rows to DPR measurement records (TON)."""
    out = []
    for row in bbs_rows or []:
        mt = float(row.get("weight_mt") or steel_bbs_weight_mt(
            row.get("nos", 0), row.get("length_m", 0), row.get("diameter_mm", 0)
        ))
        if mt <= 0:
            continue
        mark = row.get("bar_mark") or "BBS"
        dia = float(row.get("diameter_mm") or 0)
        dims = {
            "bbs": True,
            "bar_mark": mark,
            "shape_code": row.get("shape_code") or "STRAIGHT",
            "diameter_mm": dia,
            "spacing_mm": float(row.get("spacing_mm") or 0),
            "nos": float(row.get("nos") or 0),
            "dim_a": float(row.get("dim_a") or 0),
            "dim_b": float(row.get("dim_b") or 0),
            "dim_c": float(row.get("dim_c") or 0),
            "dim_d": float(row.get("dim_d") or 0),
            "dim_e": float(row.get("dim_e") or 0),
            "dim_f": float(row.get("dim_f") or 0),
            "length_m": float(row.get("length_m") or 0),
            "weight_kg": float(row.get("weight_kg") or 0),
            "shape_image_path": row.get("shape_image_path") or "",
        }
        out.append(
            {
                "measurement_type": f"Steel BBS {mark}",
                "measurement_method": "BBS",
                "unit": "TON",
                "qty": float(row.get("nos") or 0),
                "nos": float(row.get("nos") or 0),
                "dia_mm": dia,
                "length_1": float(row.get("length_m") or 0),
                "calculated_quantity": mt,
                "dimensions_json": json.dumps(dims),
                "preview_lines": [
                    f"BBS {mark}: Ø{dia:g}mm × L{row.get('length_m', 0):g}m × {row.get('nos', 0):g} nos",
                    f"Weight = {mt:g} MT",
                ],
            }
        )
    return out


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
