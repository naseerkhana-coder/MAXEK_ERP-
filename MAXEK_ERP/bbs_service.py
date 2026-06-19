"""Bar Bending Schedule (BBS) reports — steel qty by diameter, weight totals."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from accounts_service import _safe_float

MODULE_ID = "bbs_report"
RECORD_TABLE = "bbs_reports"
DIAMETERS = (8, 10, 12, 16, 20, 25, 32)


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_column(db, table: str, column: str, col_type: str) -> None:
    if not _table_exists(db, table):
        return
    try:
        cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except Exception:
        pass


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _round3(value: float) -> float:
    return round(float(value or 0), 3)


def ensure_bbs_schema(db) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS bbs_reports(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_no TEXT UNIQUE NOT NULL,
            project_id INTEGER NOT NULL,
            project_name TEXT,
            building_number TEXT,
            measurement_from TEXT,
            measurement_to TEXT,
            report_date TEXT,
            cutting_bending TEXT DEFAULT 'Cutting & Bending',
            weight_up_to_12mm REAL DEFAULT 0,
            weight_above_12mm REAL DEFAULT 0,
            prepared_by TEXT,
            verified_by TEXT,
            checked_by TEXT,
            remarks TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("ref_no", "TEXT"), ("project_id", "INTEGER"), ("project_name", "TEXT"),
        ("building_number", "TEXT"), ("measurement_from", "TEXT"), ("measurement_to", "TEXT"),
        ("report_date", "TEXT"), ("cutting_bending", "TEXT"),
        ("weight_up_to_12mm", "REAL DEFAULT 0"), ("weight_above_12mm", "REAL DEFAULT 0"),
        ("prepared_by", "TEXT"), ("verified_by", "TEXT"), ("checked_by", "TEXT"),
        ("remarks", "TEXT"), ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
        ("created_by", "TEXT"), ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "bbs_reports", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS bbs_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bbs_id INTEGER NOT NULL,
            line_no INTEGER DEFAULT 1,
            description TEXT,
            side TEXT,
            unit TEXT DEFAULT 'Mt',
            nos REAL DEFAULT 0,
            num_bars INTEGER DEFAULT 0,
            cutting_length REAL DEFAULT 0,
            diameter_mm REAL DEFAULT 0,
            steel_qty_8 REAL DEFAULT 0,
            steel_qty_10 REAL DEFAULT 0,
            steel_qty_12 REAL DEFAULT 0,
            steel_qty_16 REAL DEFAULT 0,
            steel_qty_20 REAL DEFAULT 0,
            steel_qty_25 REAL DEFAULT 0,
            steel_qty_32 REAL DEFAULT 0,
            total_qty REAL DEFAULT 0,
            remarks TEXT,
            FOREIGN KEY(bbs_id) REFERENCES bbs_reports(id) ON DELETE CASCADE
        )
    """)
    for col, ctype in (
        ("bbs_id", "INTEGER"), ("line_no", "INTEGER DEFAULT 1"),
        ("description", "TEXT"), ("side", "TEXT"), ("unit", "TEXT"),
        ("nos", "REAL DEFAULT 0"), ("num_bars", "INTEGER DEFAULT 0"),
        ("cutting_length", "REAL DEFAULT 0"), ("diameter_mm", "REAL DEFAULT 0"),
        ("steel_qty_8", "REAL DEFAULT 0"), ("steel_qty_10", "REAL DEFAULT 0"),
        ("steel_qty_12", "REAL DEFAULT 0"), ("steel_qty_16", "REAL DEFAULT 0"),
        ("steel_qty_20", "REAL DEFAULT 0"), ("steel_qty_25", "REAL DEFAULT 0"),
        ("steel_qty_32", "REAL DEFAULT 0"), ("total_qty", "REAL DEFAULT 0"), ("remarks", "TEXT"),
    ):
        _ensure_column(db, "bbs_lines", col, ctype)


def _next_ref_no(db) -> str:
    year = datetime.now().strftime("%Y")
    row = db.execute(
        "SELECT ref_no FROM bbs_reports WHERE ref_no LIKE ? ORDER BY id DESC LIMIT 1",
        (f"MAX/BBS/{year}/%",),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"/(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"MAX/BBS/{year}/{seq:03d}"


def _steel_weight_mt(num_bars: int, cutting_length: float, diameter_mm: float) -> float:
    """Weight in metric tonnes: D² × L × N / 162000 (L in metres)."""
    if not num_bars or not cutting_length or not diameter_mm:
        return 0.0
    length_m = cutting_length / 1000.0 if cutting_length > 50 else cutting_length
    return (diameter_mm ** 2) * length_m * num_bars / 162000.0


def _diameter_col(dia: int) -> str:
    return f"steel_qty_{dia}"


def _parse_lines_from_form(form) -> list[dict[str, Any]]:
    descriptions = form.getlist("line_description[]")
    sides = form.getlist("line_side[]")
    units = form.getlist("line_unit[]")
    nos_list = form.getlist("line_nos[]")
    num_bars_list = form.getlist("line_num_bars[]")
    cls = form.getlist("line_cl[]")
    dias = form.getlist("line_dia[]")
    remarks_list = form.getlist("line_remarks[]")
    qty_fields = {d: form.getlist(f"line_qty_{d}[]") for d in DIAMETERS}

    lines: list[dict[str, Any]] = []
    count = max(len(descriptions), 1)
    for idx in range(count):
        desc = (descriptions[idx] if idx < len(descriptions) else "").strip()
        if not desc:
            continue
        dia = _safe_float(dias[idx] if idx < len(dias) else 0)
        num_bars = int(_safe_float(num_bars_list[idx] if idx < len(num_bars_list) else 0))
        cl = _safe_float(cls[idx] if idx < len(cls) else 0)
        line: dict[str, Any] = {
            "description": desc,
            "side": sides[idx] if idx < len(sides) else "",
            "unit": units[idx] if idx < len(units) else "Mt",
            "nos": _safe_float(nos_list[idx] if idx < len(nos_list) else 0),
            "num_bars": num_bars,
            "cutting_length": cl,
            "diameter_mm": dia,
            "remarks": remarks_list[idx] if idx < len(remarks_list) else "",
        }
        total = 0.0
        for d in DIAMETERS:
            raw_qty = qty_fields[d][idx] if idx < len(qty_fields[d]) else 0
            qty = _safe_float(raw_qty)
            if qty <= 0 and int(dia) == d and num_bars and cl:
                qty = _round3(_steel_weight_mt(num_bars, cl, d))
            line[_diameter_col(d)] = qty
            total += qty
        if total <= 0 and dia and num_bars and cl:
            col = _diameter_col(int(dia)) if int(dia) in DIAMETERS else None
            if col:
                w = _round3(_steel_weight_mt(num_bars, cl, dia))
                line[col] = w
                total = w
        line["total_qty"] = _round3(total)
        lines.append(line)
    return lines


def _compute_weight_totals(lines: list[dict[str, Any]]) -> tuple[float, float]:
    up_to_12 = 0.0
    above_12 = 0.0
    for line in lines:
        for d in DIAMETERS:
            qty = _safe_float(line.get(_diameter_col(d)))
            if d <= 12:
                up_to_12 += qty
            else:
                above_12 += qty
    return _round3(up_to_12), _round3(above_12)


def _diameter_totals(lines: list[dict[str, Any]]) -> dict[int, float]:
    totals = {d: 0.0 for d in DIAMETERS}
    for line in lines:
        for d in DIAMETERS:
            totals[d] += _safe_float(line.get(_diameter_col(d)))
    return {d: _round3(v) for d, v in totals.items()}


def save_bbs_report(db, form, username: str, bbs_id: int | None = None) -> int:
    project_id = int(form.get("project_id") or 0)
    if not project_id:
        raise ValueError("Project is required.")
    proj = db.execute(
        "SELECT project_name FROM projects WHERE id=?", (project_id,)
    ).fetchone()
    if not proj:
        raise ValueError("Project not found.")

    lines = _parse_lines_from_form(form)
    if not lines:
        raise ValueError("Add at least one BBS line.")

    up_12, above_12 = _compute_weight_totals(lines)
    now = _now_ts()
    header = {
        "project_id": project_id,
        "project_name": proj["project_name"],
        "building_number": (form.get("building_number") or "").strip(),
        "measurement_from": (form.get("measurement_from") or "").strip(),
        "measurement_to": (form.get("measurement_to") or "").strip(),
        "report_date": (form.get("report_date") or _today()).strip(),
        "cutting_bending": (form.get("cutting_bending") or "Cutting & Bending").strip(),
        "weight_up_to_12mm": up_12,
        "weight_above_12mm": above_12,
        "prepared_by": (form.get("prepared_by") or "MAXEK SUPERVISOR").strip(),
        "verified_by": (form.get("verified_by") or "EKK Engineer QS").strip(),
        "checked_by": (form.get("checked_by") or "EKK Planning Manager").strip(),
        "remarks": (form.get("remarks") or "").strip(),
    }

    if bbs_id:
        db.execute(
            """
            UPDATE bbs_reports SET
                project_id=?, project_name=?, building_number=?,
                measurement_from=?, measurement_to=?, report_date=?,
                cutting_bending=?, weight_up_to_12mm=?, weight_above_12mm=?,
                prepared_by=?, verified_by=?, checked_by=?, remarks=?, modified_at=?
            WHERE id=?
            """,
            (
                header["project_id"], header["project_name"], header["building_number"],
                header["measurement_from"], header["measurement_to"], header["report_date"],
                header["cutting_bending"], header["weight_up_to_12mm"], header["weight_above_12mm"],
                header["prepared_by"], header["verified_by"], header["checked_by"],
                header["remarks"], now, bbs_id,
            ),
        )
    else:
        ref_no = (form.get("ref_no") or "").strip() or _next_ref_no(db)
        db.execute(
            """
            INSERT INTO bbs_reports(
                ref_no, project_id, project_name, building_number,
                measurement_from, measurement_to, report_date, cutting_bending,
                weight_up_to_12mm, weight_above_12mm,
                prepared_by, verified_by, checked_by, remarks,
                approval_status, created_by, created_at, modified_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                ref_no, header["project_id"], header["project_name"], header["building_number"],
                header["measurement_from"], header["measurement_to"], header["report_date"],
                header["cutting_bending"], header["weight_up_to_12mm"], header["weight_above_12mm"],
                header["prepared_by"], header["verified_by"], header["checked_by"], header["remarks"],
                "Pending Checker", username, now, now,
            ),
        )
        bbs_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])

    db.execute("DELETE FROM bbs_lines WHERE bbs_id=?", (bbs_id,))
    for idx, line in enumerate(lines, start=1):
        db.execute(
            """
            INSERT INTO bbs_lines(
                bbs_id, line_no, description, side, unit, nos, num_bars,
                cutting_length, diameter_mm,
                steel_qty_8, steel_qty_10, steel_qty_12, steel_qty_16,
                steel_qty_20, steel_qty_25, steel_qty_32, total_qty, remarks
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                bbs_id, idx, line["description"], line["side"], line["unit"],
                line["nos"], line["num_bars"], line["cutting_length"], line["diameter_mm"],
                line.get("steel_qty_8", 0), line.get("steel_qty_10", 0), line.get("steel_qty_12", 0),
                line.get("steel_qty_16", 0), line.get("steel_qty_20", 0), line.get("steel_qty_25", 0),
                line.get("steel_qty_32", 0), line["total_qty"], line["remarks"],
            ),
        )
    return bbs_id


def get_bbs_report(db, bbs_id: int) -> dict[str, Any] | None:
    row = db.execute(
        """
        SELECT b.*, p.project_code
        FROM bbs_reports b
        LEFT JOIN projects p ON b.project_id = p.id
        WHERE b.id=?
        """,
        (bbs_id,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    lines = db.execute(
        "SELECT * FROM bbs_lines WHERE bbs_id=? ORDER BY line_no, id",
        (bbs_id,),
    ).fetchall()
    data["lines"] = [dict(l) for l in lines]
    data["diameter_totals"] = _diameter_totals(data["lines"])
    return data


def list_bbs_reports(db, search: str = "", project_id: int | None = None) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if search:
        clauses.append("(b.ref_no LIKE ? OR b.project_name LIKE ? OR b.building_number LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    if project_id:
        clauses.append("b.project_id=?")
        params.append(project_id)
    sql = f"""
        SELECT b.*, p.project_code
        FROM bbs_reports b
        LEFT JOIN projects p ON b.project_id = p.id
        WHERE {' AND '.join(clauses)}
        ORDER BY b.report_date DESC, b.id DESC
    """
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def list_projects_for_bbs(db) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT id, project_code, project_name FROM projects "
        "WHERE status IS NULL OR status != 'Inactive' ORDER BY project_name"
    ).fetchall()
    return [dict(r) for r in rows]


def delete_bbs_report(db, bbs_id: int) -> None:
    db.execute("DELETE FROM bbs_lines WHERE bbs_id=?", (bbs_id,))
    db.execute("DELETE FROM bbs_reports WHERE id=?", (bbs_id,))
