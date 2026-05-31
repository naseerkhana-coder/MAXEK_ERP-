"""Steel reinforcement shapes for DPR — length by shape code, weight in MT."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from modules.database import get_conn, generate_id

STEEL_DIAGRAM_DIR = Path(__file__).resolve().parents[1] / "assets" / "dpr_steel"
SHAPE_DIAGRAM_FILES = {
    "CHAIR": "chair.png",
    "RING": "ring.png",
    "STARTER": "starter.png",
    "BENT_BAR": "starter.png",
}

# Standard TMT / rebar diameters (mm)
STEEL_DIA_MM_OPTIONS = (8, 10, 12, 16, 20, 25, 28, 32, 36, 40)

# Built-in shapes (always available). Terms: key, label, multiplier (how many times in total length).
BUILTIN_STEEL_SHAPES = [
    {
        "shape_code": "STRAIGHT",
        "shape_name": "Straight Bar",
        "input_unit": "m",
        "terms": [{"key": "length_m", "label": "Length (m)", "mult": 1.0}],
        "diagram_hint": "Single straight bar — Length × Dia × Nos → MT",
    },
    {
        "shape_code": "RING",
        "shape_name": "Ring / Stirrup",
        "input_unit": "mm",
        "layout": "ring_6",
        "terms": [
            {"key": "length_1", "label": "Length 1 (mm)", "mult": 1.0},
            {"key": "length_2", "label": "Length 2 (mm)", "mult": 1.0},
            {"key": "width_1", "label": "Width 1 (mm)", "mult": 1.0},
            {"key": "width_2", "label": "Width 2 (mm)", "mult": 1.0},
            {"key": "bend_1", "label": "Bend inside 1 (mm)", "mult": 1.0},
            {"key": "bend_2", "label": "Bend inside 2 (mm)", "mult": 1.0},
        ],
        "diagram_hint": "6 measurements: L1 + L2 + W1 + W2 + Bend1 + Bend2 → total length (mm)",
    },
    {
        "shape_code": "CHAIR",
        "shape_name": "Chair / Spacer",
        "input_unit": "mm",
        "terms": [
            {"key": "height", "label": "Height (A) mm", "mult": 2.0},
            {"key": "bottom", "label": "Bottom leg (B) mm", "mult": 2.0},
            {"key": "top", "label": "Top (C) mm", "mult": 1.0},
        ],
        "diagram_hint": "2×Height + 2×Bottom + Top",
    },
    {
        "shape_code": "BENT_BAR",
        "shape_name": "Bent Bar",
        "input_unit": "mm",
        "terms": [
            {"key": "leg_1", "label": "Leg 1 (mm)", "mult": 1.0},
            {"key": "leg_2", "label": "Leg 2 (mm)", "mult": 1.0},
        ],
        "diagram_hint": "Leg1 + Leg2 (× bend factor optional below)",
    },
    {
        "shape_code": "STARTER",
        "shape_name": "Starter / L-bar with hook",
        "input_unit": "mm",
        "terms": [
            {"key": "vertical", "label": "Vertical leg (mm)", "mult": 1.0},
            {"key": "hook", "label": "Hook length (mm)", "mult": 1.0},
        ],
        "diagram_hint": "Vertical + hook per bar (enter Nos for bar count)",
    },
]


def steel_shape_diagram_path(shape_code: str) -> Path | None:
    """Return path to reference sketch for built-in shapes, if bundled."""
    fname = SHAPE_DIAGRAM_FILES.get(str(shape_code or "").strip().upper())
    if not fname:
        return None
    path = STEEL_DIAGRAM_DIR / fname
    return path if path.is_file() else None


def steel_weight_mt(nos: float, length_m: float, dia_mm: float) -> float:
    """Weight in metric tons: (dia² × length × nos) / 162 / 1000."""
    if nos <= 0 or length_m <= 0 or dia_mm <= 0:
        return 0.0
    kg = (float(dia_mm) ** 2 * float(length_m) * float(nos)) / 162.0
    return round(kg / 1000.0, 4)


def _apply_builtin_shape_overrides(shape: dict) -> dict:
    code = str(shape.get("shape_code") or "").upper()
    for builtin in BUILTIN_STEEL_SHAPES:
        if builtin["shape_code"].upper() != code:
            continue
        if len(shape.get("terms") or []) < len(builtin.get("terms") or []):
            shape["terms"] = builtin["terms"]
            shape["layout"] = builtin.get("layout") or shape.get("layout") or ""
            shape["diagram_hint"] = builtin.get("diagram_hint") or shape.get("diagram_hint") or ""
        break
    return shape


def _shape_from_row(row) -> dict:
    terms = row.get("terms_json") or row.get("terms")
    if isinstance(terms, str):
        terms = json.loads(terms)
    shape = {
        "shape_code": row["shape_code"],
        "shape_name": row["shape_name"],
        "input_unit": row.get("input_unit") or "mm",
        "layout": row.get("layout") or "",
        "terms": terms or [],
        "diagram_hint": row.get("diagram_hint") or "",
        "is_builtin": bool(row.get("is_builtin")),
        "shape_id": row.get("shape_id", ""),
    }
    if shape.get("is_builtin"):
        return _apply_builtin_shape_overrides(shape)
    return shape


def seed_steel_shapes_if_empty(conn=None):
    own = conn is None
    if own:
        conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM dpr_steel_shapes")
    if (cur.fetchone() or [0])[0] == 0:
        for shape in BUILTIN_STEEL_SHAPES:
            sid = generate_id("SS", "dpr_steel_shapes", conn=conn)
            cur.execute(
                """
                INSERT INTO dpr_steel_shapes(
                    shape_id, shape_code, shape_name, input_unit, terms_json, diagram_hint, is_builtin, status
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    sid,
                    shape["shape_code"],
                    shape["shape_name"],
                    shape["input_unit"],
                    json.dumps(shape["terms"]),
                    shape.get("diagram_hint", ""),
                    1,
                    "Active",
                ),
            )
    sync_builtin_steel_shapes(conn)
    if own:
        conn.commit()
        conn.close()


def sync_builtin_steel_shapes(conn=None):
    """Refresh built-in shape definitions (e.g. ring 6 fields) on existing databases."""
    own = conn is None
    if own:
        conn = get_conn()
    cur = conn.cursor()
    for shape in BUILTIN_STEEL_SHAPES:
        cur.execute(
            """
            UPDATE dpr_steel_shapes SET
                shape_name = ?, input_unit = ?, terms_json = ?, diagram_hint = ?, status = 'Active'
            WHERE UPPER(shape_code) = ? AND COALESCE(is_builtin, 0) = 1
            """,
            (
                shape["shape_name"],
                shape["input_unit"],
                json.dumps(shape["terms"]),
                shape.get("diagram_hint", ""),
                shape["shape_code"].upper(),
            ),
        )
        if cur.rowcount == 0:
            exists = cur.execute(
                "SELECT 1 FROM dpr_steel_shapes WHERE UPPER(shape_code) = ?",
                (shape["shape_code"].upper(),),
            ).fetchone()
            if not exists:
                sid = generate_id("SS", "dpr_steel_shapes", conn=conn)
                cur.execute(
                    """
                    INSERT INTO dpr_steel_shapes(
                        shape_id, shape_code, shape_name, input_unit, terms_json, diagram_hint, is_builtin, status
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        sid,
                        shape["shape_code"],
                        shape["shape_name"],
                        shape["input_unit"],
                        json.dumps(shape["terms"]),
                        shape.get("diagram_hint", ""),
                        1,
                        "Active",
                    ),
                )
    if own:
        conn.commit()
        conn.close()


def load_steel_shapes(active_only=True):
    seed_steel_shapes_if_empty()
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM dpr_steel_shapes"
    if active_only:
        sql += " WHERE UPPER(COALESCE(status,'ACTIVE')) = 'ACTIVE'"
    sql += " ORDER BY is_builtin DESC, shape_name"
    rows = conn.execute(sql).fetchall()
    conn.close()
    shapes = [_shape_from_row(dict(row)) for row in rows]
    if not shapes:
        return [dict(s, is_builtin=True, shape_id="") for s in BUILTIN_STEEL_SHAPES]
    return shapes


def get_steel_shape(shape_code: str) -> dict | None:
    code = str(shape_code or "").strip().upper()
    for shape in load_steel_shapes():
        if str(shape.get("shape_code", "")).upper() == code:
            return shape
    for shape in BUILTIN_STEEL_SHAPES:
        if shape["shape_code"].upper() == code:
            return dict(shape, is_builtin=True, shape_id="")
    return None


def compute_steel_measurement(shape: dict, dimensions: dict, dia_mm: float, nos: float, bend_factor: float = 1.0):
    """Return total length (m), weight MT, and preview lines."""
    terms = shape.get("terms") or []
    input_unit = (shape.get("input_unit") or "mm").lower()
    parts = []
    total_raw = 0.0
    for term in terms:
        key = term["key"]
        mult = float(term.get("mult") or 1)
        val = float(dimensions.get(key) or 0)
        if val <= 0:
            continue
        contrib = val * mult
        total_raw += contrib
        parts.append(f"{mult:g}×{_fmt(val)} {term.get('label', key)}")

    if shape.get("shape_code", "").upper() == "BENT_BAR" and bend_factor > 0:
        total_raw *= float(bend_factor)

    if input_unit == "mm":
        total_length_m = total_raw / 1000.0
    else:
        total_length_m = total_raw

    length_per_piece_m = total_length_m
    weight_mt = steel_weight_mt(nos, length_per_piece_m, dia_mm)

    lines = [
        f"Shape: {shape.get('shape_name')} ({shape.get('shape_code')})",
        shape.get("diagram_hint") or "",
    ]
    if parts:
        lines.append("Length: " + " + ".join(parts))
    lines.append(f"Total length / piece: {_fmt(length_per_piece_m)} m")
    lines.append(f"Dia: {_fmt(dia_mm)} mm · Nos: {_fmt(nos)}")
    lines.append(f"Weight: {_fmt(weight_mt)} MT  [(D²×L×N)/162÷1000]")

    return {
        "shape_code": shape.get("shape_code"),
        "shape_name": shape.get("shape_name"),
        "dimensions": dimensions,
        "dia_mm": float(dia_mm or 0),
        "nos": float(nos or 0),
        "bend_factor": float(bend_factor or 1),
        "total_length_m": round(length_per_piece_m, 4),
        "weight_mt": weight_mt,
        "preview_lines": [ln for ln in lines if ln],
    }


def parse_steel_dia_mm(dia_label_or_value) -> float:
    text = str(dia_label_or_value or "").strip().lower().replace("mm", "").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


def build_steel_measurement_record(calc: dict) -> dict:
    """Map steel calc to dpr_measurements row format."""
    dims = calc.get("dimensions") or {}
    shape = get_steel_shape(calc.get("shape_code") or "") or {}
    terms = shape.get("terms") or []
    code = str(calc.get("shape_code") or "").upper()
    if code == "RING":
        length_1 = float(dims.get("length_1", 0))
        length_2 = float(dims.get("length_2", 0))
        width_1 = float(dims.get("width_1", 0))
        width_2 = float(dims.get("width_2", 0))
        height = float(dims.get("bend_1", 0))
        depth = float(dims.get("bend_2", 0))
    else:
        length_1 = float(dims.get(terms[0]["key"], 0)) if terms else 0.0
        length_2 = float(dims.get(terms[1]["key"], 0)) if len(terms) > 1 else 0.0
        width_1 = float(dims.get(terms[2]["key"], 0)) if len(terms) > 2 else 0.0
        height = float(dims.get(terms[3]["key"], 0)) if len(terms) > 3 else 0.0
        depth = float(dims.get(terms[4]["key"], 0)) if len(terms) > 4 else 0.0
    return {
        "measurement_type": calc.get("shape_name") or "Steel",
        "measurement_method": calc.get("shape_code") or "STEEL",
        "unit": "TON",
        "qty": calc.get("nos") or 0,
        "length_1": length_1,
        "length_2": length_2,
        "width_1": width_1,
        "width_2": width_2 if code == "RING" else 0.0,
        "depth": depth,
        "height": height,
        "avg_length": calc.get("total_length_m") or 0,
        "avg_width": 0.0,
        "avg_depth": 0.0,
        "calculated_quantity": calc.get("weight_mt") or 0,
        "nos": calc.get("nos") or 0,
        "dia_mm": calc.get("dia_mm") or 0,
        "bend": calc.get("bend_factor") or 1,
        "preview_lines": calc.get("preview_lines") or [],
        "dimensions_json": json.dumps(
            {
                "steel_shape_code": calc.get("shape_code"),
                "steel_dimensions": dims,
                "total_length_m": calc.get("total_length_m"),
                "dia_mm": calc.get("dia_mm"),
                "nos": calc.get("nos"),
                "bend_factor": calc.get("bend_factor"),
                "weight_mt": calc.get("weight_mt"),
            }
        ),
    }


def save_custom_steel_shape(shape_code: str, shape_name: str, input_unit: str, terms: list, diagram_hint: str = ""):
    code = str(shape_code or "").strip().upper().replace(" ", "_")
    if not code or not shape_name.strip():
        raise ValueError("Shape code and name are required.")
    if not terms:
        raise ValueError("Add at least one measurement term.")
    conn = get_conn()
    existing = conn.execute(
        "SELECT shape_id FROM dpr_steel_shapes WHERE UPPER(shape_code) = ?",
        (code,),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE dpr_steel_shapes SET
                shape_name = ?, input_unit = ?, terms_json = ?, diagram_hint = ?, status = 'Active'
            WHERE UPPER(shape_code) = ?
            """,
            (shape_name.strip(), input_unit, json.dumps(terms), diagram_hint, code),
        )
    else:
        sid = generate_id("SS", "dpr_steel_shapes", conn=conn)
        conn.execute(
            """
            INSERT INTO dpr_steel_shapes(
                shape_id, shape_code, shape_name, input_unit, terms_json, diagram_hint, is_builtin, status
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (sid, code, shape_name.strip(), input_unit, json.dumps(terms), diagram_hint, 0, "Active"),
        )
    conn.commit()
    conn.close()


def _fmt(value):
    text = f"{float(value):.4f}".rstrip("0").rstrip(".")
    return text if text else "0"
