"""DPR measurement book, steel BBS, photos, and audit — database helpers."""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from modules.database import DATE_FMT, _add_column_if_missing, generate_id, get_conn
from modules.dpr_measurements import boq_measurement_type_label, normalize_boq_unit

APPROVED_DPR_STATUSES = (
    "Submitted",
    "Engineer Approved",
    "Client Approved",
    "Billed",
)


def ensure_dpr_measurement_schema(conn=None):
    """Create extension tables and columns for DPR / measurement book."""
    own = conn is None
    conn = conn or get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS dpr_steel_bbs_rows(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bbs_row_id TEXT,
            dpr_id TEXT,
            boq_item_id TEXT,
            boq_line_id TEXT,
            bar_mark TEXT,
            diameter_mm REAL,
            spacing_mm REAL,
            nos REAL,
            length_m REAL,
            weight_kg REAL,
            weight_mt REAL,
            remarks TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS dpr_photos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id TEXT,
            dpr_id TEXT,
            file_path TEXT,
            caption TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT
        );
        CREATE TABLE IF NOT EXISTS dpr_audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id TEXT,
            dpr_id TEXT,
            action TEXT,
            detail_json TEXT,
            user_name TEXT,
            created_at TEXT
        );
        """
    )
    for col, typ in (
        ("work_category", "TEXT"),
        ("location_text", "TEXT"),
        ("engineer_name", "TEXT"),
    ):
        _add_column_if_missing(cur, "dpr_reports", col, typ)
    for col, typ in (
        ("width_3", "REAL"),
        ("thickness", "REAL"),
        ("row_index", "INTEGER"),
        ("include_in_client_bill", "INTEGER DEFAULT 1"),
    ):
        _add_column_if_missing(cur, "dpr_measurements", col, typ)
    for col, typ in (
        ("shape_code", "TEXT"),
        ("dim_a", "REAL"),
        ("dim_b", "REAL"),
        ("dim_c", "REAL"),
        ("dim_d", "REAL"),
        ("dim_e", "REAL"),
        ("dim_f", "REAL"),
        ("shape_image_path", "TEXT"),
    ):
        _add_column_if_missing(cur, "dpr_steel_bbs_rows", col, typ)
    for col, typ in (("billable_quantity", "REAL DEFAULT 0"),):
        _add_column_if_missing(cur, "dpr_boq_lines", col, typ)
    if own:
        conn.commit()
        conn.close()


def _timestamp() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def log_dpr_audit(dpr_id: str, action: str, detail: dict | None, user_name: str, conn=None):
    own = conn is None
    conn = conn or get_conn()
    audit_id = generate_id("DPA", "dpr_audit_log", conn=conn)
    conn.execute(
        """
        INSERT INTO dpr_audit_log(audit_id, dpr_id, action, detail_json, user_name, created_at)
        VALUES(?,?,?,?,?,?)
        """,
        (
            audit_id,
            dpr_id or "",
            action,
            json.dumps(detail or {}),
            user_name or "System",
            _timestamp(),
        ),
    )
    if own:
        conn.commit()
        conn.close()


def load_boq_meta_for_item(boq_item_id: str) -> dict:
    """Unit, measurement type label, billing flag from project BOQ."""
    if not boq_item_id:
        return {}
    conn = get_conn()
    row = conn.execute(
        """
        SELECT boq_item_id, boq_number, description, unit, quantity, approved_rate, status
        FROM project_boq_items WHERE boq_item_id = ? LIMIT 1
        """,
        (boq_item_id,),
    ).fetchone()
    conn.close()
    if not row:
        return {}
    unit = row[3] or ""
    unit_family = normalize_boq_unit(unit)
    return {
        "boq_item_id": row[0],
        "boq_number": row[1] or "",
        "description": row[2] or "",
        "unit": unit,
        "unit_family": unit_family,
        "measurement_type": boq_measurement_type_label(unit_family),
        "billing_type": "Rate × measured qty",
        "quantity": float(row[4] or 0),
        "approved_rate": float(row[5] or 0),
        "status": row[6] or "",
    }


def load_measurement_book(
    project_name: str = "",
    boq_item_id: str = "",
    date_from: str = "",
    date_to: str = "",
    approved_only: bool = True,
) -> pd.DataFrame:
    """Cumulative measurement register by project / BOQ from DPR lines."""
    conn = get_conn()
    sql = """
        SELECT
            d.project_name,
            d.project_id,
            COALESCE(bl.boq_item_id, m.boq_item_id, d.boq_item_id) AS boq_item_id,
            COALESCE(bl.boq_number, d.boq_number) AS boq_number,
            COALESCE(bl.boq_description, d.boq_description) AS boq_description,
            COALESCE(bl.unit, m.unit, d.unit) AS unit,
            COUNT(DISTINCT d.dpr_id) AS dpr_count,
            COUNT(m.id) AS measurement_rows,
            ROUND(SUM(COALESCE(m.calculated_quantity, 0)), 4) AS cumulative_qty,
            MIN(d.dpr_date) AS first_dpr_date,
            MAX(d.dpr_date) AS last_dpr_date
        FROM dpr_measurements m
        INNER JOIN dpr_reports d ON d.dpr_id = m.dpr_id
        LEFT JOIN dpr_boq_lines bl ON bl.line_id = m.boq_line_id
        WHERE 1=1
    """
    params: list = []
    if project_name:
        sql += " AND d.project_name = ?"
        params.append(project_name)
    if boq_item_id:
        sql += " AND COALESCE(bl.boq_item_id, m.boq_item_id, d.boq_item_id) = ?"
        params.append(boq_item_id)
    if date_from:
        sql += " AND d.dpr_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND d.dpr_date <= ?"
        params.append(date_to)
    if approved_only:
        placeholders = ",".join("?" * len(APPROVED_DPR_STATUSES))
        sql += f" AND d.status IN ({placeholders})"
        params.extend(APPROVED_DPR_STATUSES)
    sql += """
        GROUP BY d.project_name, d.project_id,
                 COALESCE(bl.boq_item_id, m.boq_item_id, d.boq_item_id),
                 COALESCE(bl.boq_number, d.boq_number),
                 COALESCE(bl.boq_description, d.boq_description),
                 COALESCE(bl.unit, m.unit, d.unit)
        ORDER BY boq_number
    """
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def load_measurement_book_detail(
    project_name: str,
    boq_item_id: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 500,
) -> pd.DataFrame:
    """Line-level measurement history for measurement sheet export."""
    conn = get_conn()
    sql = """
        SELECT
            d.dpr_id, d.dpr_date, d.status, d.site_incharge_name,
            COALESCE(d.engineer_name, '') AS engineer_name,
            COALESCE(d.location_text, '') AS location_text,
            COALESCE(d.work_category, '') AS work_category,
            COALESCE(bl.boq_number, d.boq_number) AS boq_number,
            m.measurement_type, m.measurement_method,
            m.length_1, m.length_2, m.width_1, m.width_2,
            COALESCE(m.width_3, 0) AS width_3,
            m.height, m.depth, COALESCE(m.thickness, 0) AS thickness,
            m.nos, m.avg_length, m.avg_width, m.avg_depth,
            m.calculated_quantity, m.unit,
            m.dimensions_json,
            COALESCE(m.include_in_client_bill, 1) AS include_in_client_bill
        FROM dpr_measurements m
        INNER JOIN dpr_reports d ON d.dpr_id = m.dpr_id
        LEFT JOIN dpr_boq_lines bl ON bl.line_id = m.boq_line_id
        WHERE d.project_name = ?
    """
    params: list = [project_name]
    if boq_item_id:
        sql += " AND COALESCE(bl.boq_item_id, m.boq_item_id, d.boq_item_id) = ?"
        params.append(boq_item_id)
    if date_from:
        sql += " AND d.dpr_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND d.dpr_date <= ?"
        params.append(date_to)
    sql += " ORDER BY d.dpr_date DESC, m.id DESC LIMIT ?"
    params.append(int(limit))
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def persist_steel_bbs_rows(conn, dpr_id: str, rows: list, boq_item_id: str = "", boq_line_id: str = ""):
    conn.execute("DELETE FROM dpr_steel_bbs_rows WHERE dpr_id = ?", (dpr_id,))
    for row in rows or []:
        bbs_id = generate_id("BBS", "dpr_steel_bbs_rows", conn=conn)
        conn.execute(
            """
            INSERT INTO dpr_steel_bbs_rows(
                bbs_row_id, dpr_id, boq_item_id, boq_line_id,
                bar_mark, shape_code, diameter_mm, spacing_mm, nos,
                dim_a, dim_b, dim_c, dim_d, dim_e, dim_f,
                length_m, weight_kg, weight_mt, shape_image_path, remarks, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                bbs_id,
                dpr_id,
                row.get("boq_item_id") or boq_item_id,
                row.get("boq_line_id") or boq_line_id,
                row.get("bar_mark", ""),
                row.get("shape_code", "STRAIGHT"),
                float(row.get("diameter_mm") or 0),
                float(row.get("spacing_mm") or 0),
                float(row.get("nos") or 0),
                float(row.get("dim_a") or 0),
                float(row.get("dim_b") or 0),
                float(row.get("dim_c") or 0),
                float(row.get("dim_d") or 0),
                float(row.get("dim_e") or 0),
                float(row.get("dim_f") or 0),
                float(row.get("length_m") or 0),
                float(row.get("weight_kg") or 0),
                float(row.get("weight_mt") or 0),
                row.get("shape_image_path", ""),
                row.get("remarks", ""),
                _timestamp(),
            ),
        )


def load_steel_bbs_for_dpr(dpr_id: str) -> list[dict]:
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT bar_mark, shape_code, diameter_mm, spacing_mm, nos,
               dim_a, dim_b, dim_c, dim_d, dim_e, dim_f,
               length_m, weight_kg, weight_mt, shape_image_path, remarks,
               boq_item_id, boq_line_id
        FROM dpr_steel_bbs_rows WHERE dpr_id = ? ORDER BY id
        """,
        conn,
        params=(dpr_id,),
    )
    conn.close()
    return df.to_dict("records") if not df.empty else []


def persist_dpr_photos(conn, dpr_id: str, paths: list[str], user_name: str):
    conn.execute("DELETE FROM dpr_photos WHERE dpr_id = ?", (dpr_id,))
    for path in paths or []:
        if not path:
            continue
        photo_id = generate_id("DPP", "dpr_photos", conn=conn)
        conn.execute(
            """
            INSERT INTO dpr_photos(photo_id, dpr_id, file_path, caption, uploaded_by, uploaded_at)
            VALUES(?,?,?,?,?,?)
            """,
            (photo_id, dpr_id, path, "", user_name or "User", _timestamp()),
        )


def parse_dpr_date_for_filter(value) -> str:
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime(DATE_FMT)
    return str(value).strip()[:10]


def billable_qty_from_measurements(conn, dpr_id: str, boq_line_id: str = "") -> float:
    """Sum measurement qty where include_in_client_bill is set (default legacy = all)."""
    sql = """
        SELECT COALESCE(SUM(calculated_quantity), 0)
        FROM dpr_measurements
        WHERE dpr_id = ? AND COALESCE(include_in_client_bill, 1) = 1
    """
    params: list = [dpr_id]
    if boq_line_id:
        sql += " AND boq_line_id = ?"
        params.append(boq_line_id)
    row = conn.execute(sql, params).fetchone()
    return round(float((row or [0])[0] or 0), 4)


def recalculate_dpr_quantities(dpr_id: str, user_name: str = "System") -> dict:
    """Re-sum progress and billable qty from stored measurement rows."""
    conn = get_conn()
    lines = conn.execute(
        """
        SELECT line_id, boq_item_id, billing_measurement
        FROM dpr_boq_lines WHERE dpr_id = ?
        """,
        (dpr_id,),
    ).fetchall()
    total_progress = 0.0
    total_billable = 0.0
    any_billing = False
    if lines:
        for line_id, boq_item_id, billing_flag in lines:
            prog = conn.execute(
                """
                SELECT COALESCE(SUM(calculated_quantity), 0)
                FROM dpr_measurements WHERE dpr_id = ? AND boq_line_id = ?
                """,
                (dpr_id, line_id),
            ).fetchone()[0]
            bill = billable_qty_from_measurements(conn, dpr_id, line_id)
            prog = round(float(prog or 0), 4)
            bill = round(float(bill or 0), 4)
            total_progress += prog
            if str(billing_flag or "").upper() == "YES":
                any_billing = True
                total_billable += bill
            conn.execute(
                """
                UPDATE dpr_boq_lines
                SET progress_quantity = ?, billable_quantity = ?
                WHERE line_id = ?
                """,
                (prog, bill if str(billing_flag or "").upper() == "YES" else 0.0, line_id),
            )
    else:
        prog = conn.execute(
            """
            SELECT COALESCE(SUM(calculated_quantity), 0)
            FROM dpr_measurements WHERE dpr_id = ?
            """,
            (dpr_id,),
        ).fetchone()[0]
        total_progress = round(float(prog or 0), 4)
        report = conn.execute(
            "SELECT billing_measurement FROM dpr_reports WHERE dpr_id = ?",
            (dpr_id,),
        ).fetchone()
        if report and str(report[0] or "").upper() == "YES":
            any_billing = True
            total_billable = billable_qty_from_measurements(conn, dpr_id)

    header_billing = "Yes" if any_billing else "No"
    conn.execute(
        """
        UPDATE dpr_reports
        SET progress_quantity = ?, billing_measurement = ?
        WHERE dpr_id = ?
        """,
        (total_progress, header_billing, dpr_id),
    )
    log_dpr_audit(
        dpr_id,
        "recalculate",
        {"progress_quantity": total_progress, "billable_quantity": total_billable},
        user_name,
        conn=conn,
    )
    conn.commit()
    try:
        from modules.phase3_integration import run_after_dpr_recalc

        run_after_dpr_recalc(dpr_id, conn=conn)
        conn.commit()
    except Exception:
        pass
    conn.close()
    return {
        "progress_quantity": total_progress,
        "billable_quantity": total_billable,
        "billing_measurement": header_billing,
    }


def load_steel_bbs_report(
    project_name: str = "",
    date_from: str = "",
    date_to: str = "",
    dpr_id: str = "",
) -> pd.DataFrame:
    conn = get_conn()
    sql = """
        SELECT
            b.bbs_row_id, b.bar_mark, b.shape_code, b.diameter_mm, b.spacing_mm,
            b.nos, b.dim_a, b.dim_b, b.dim_c, b.dim_d, b.dim_e, b.dim_f,
            b.length_m, b.weight_kg, b.weight_mt, b.shape_image_path, b.remarks,
            d.dpr_id, d.dpr_date, d.project_name, d.engineer_name, d.status
        FROM dpr_steel_bbs_rows b
        INNER JOIN dpr_reports d ON d.dpr_id = b.dpr_id
        WHERE 1=1
    """
    params: list = []
    if project_name:
        sql += " AND d.project_name = ?"
        params.append(project_name)
    if date_from:
        sql += " AND d.dpr_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND d.dpr_date <= ?"
        params.append(date_to)
    if dpr_id:
        sql += " AND d.dpr_id = ?"
        params.append(dpr_id)
    sql += " ORDER BY d.dpr_date DESC, b.id"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df
