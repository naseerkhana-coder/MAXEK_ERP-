"""Multiple BOQ items per DPR — line storage and progress helpers."""

from __future__ import annotations

import json

import pandas as pd

from modules.database import generate_id, get_boq_progress_stats, get_conn


def line_progress_qty(measurements: list) -> float:
    return round(sum(float(m.get("calculated_quantity") or 0) for m in (measurements or [])), 4)


def build_boq_line(
    boq_row_id: str,
    boq_item_id: str,
    boq_number: str,
    boq_description: str,
    unit: str,
    billing_measurement: str,
    stats: dict,
    measurements: list,
    line_id: str = "",
) -> dict:
    return {
        "line_id": line_id or "",
        "boq_row_id": boq_row_id,
        "boq_item_id": boq_item_id,
        "boq_number": boq_number,
        "boq_description": boq_description,
        "unit": unit,
        "billing_measurement": billing_measurement,
        "stats": dict(stats or {}),
        "measurements": list(measurements or []),
        "progress_quantity": line_progress_qty(measurements),
    }


def header_summary_from_boq_lines(boq_lines: list) -> dict:
    if not boq_lines:
        return {}
    multi = len(boq_lines) > 1
    first = boq_lines[0]
    total_progress = sum(float(ln.get("progress_quantity") or 0) for ln in boq_lines)
    any_billing = any(str(ln.get("billing_measurement") or "").upper() == "YES" for ln in boq_lines)
    return {
        "boq_item_id": first.get("boq_item_id", ""),
        "boq_number": f"{len(boq_lines)} BOQ items" if multi else first.get("boq_number", ""),
        "boq_description": "; ".join(
            f"{ln.get('boq_number', '')}: {str(ln.get('boq_description', ''))[:40]}"
            for ln in boq_lines[:5]
        )
        + (" …" if len(boq_lines) > 5 else ""),
        "unit": first.get("unit", ""),
        "billing_measurement": "Yes" if any_billing else "No",
        "progress_quantity": total_progress,
        "total_boq_quantity": sum(float((ln.get("stats") or {}).get("total_qty") or 0) for ln in boq_lines),
        "done_quantity": sum(float((ln.get("stats") or {}).get("done_qty") or 0) for ln in boq_lines),
        "billed_quantity": sum(float((ln.get("stats") or {}).get("billed_qty") or 0) for ln in boq_lines),
        "balance_quantity": sum(float((ln.get("stats") or {}).get("balance_qty") or 0) for ln in boq_lines),
        "pending_billing_quantity": sum(
            float((ln.get("stats") or {}).get("pending_billing_qty") or 0) for ln in boq_lines
        ),
    }


def enrich_boq_lines_for_save(boq_lines: list, edit_dpr_id: str = "") -> list:
    """Attach done/balance stats per line after progress is applied."""
    old_by_line = {}
    if edit_dpr_id:
        conn = get_conn()
        rows = conn.execute(
            """
            SELECT line_id, boq_item_id, progress_quantity
            FROM dpr_boq_lines WHERE dpr_id = ?
            """,
            (edit_dpr_id,),
        ).fetchall()
        conn.close()
        for row in rows:
            old_by_line[row[0]] = float(row[2] or 0)

    enriched = []
    for line in boq_lines:
        bid = line["boq_item_id"]
        stats = get_boq_progress_stats(bid)
        prog = line_progress_qty(line.get("measurements"))
        old_prog = old_by_line.get(line.get("line_id"), 0.0)
        done_after = float(stats["done_qty"]) - old_prog + prog
        balance_after = max(float(stats["total_qty"]) - done_after, 0.0)
        enriched.append(
            {
                **line,
                "progress_quantity": prog,
                "stats": stats,
                "total_boq_quantity": stats["total_qty"],
                "done_quantity": done_after,
                "billed_quantity": float(stats["billed_qty"]),
                "balance_quantity": balance_after,
                "pending_billing_quantity": float(stats["pending_billing_qty"]),
            }
        )
    return enriched


def _measurement_from_sql_row(row, cols) -> dict:
    data = dict(zip(cols, row))
    dims = {}
    try:
        dims = json.loads(data.get("dimensions_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        dims = {}
    return {
        "measurement_type": data.get("measurement_type"),
        "measurement_method": data.get("measurement_method") or "Normal",
        "unit": data.get("unit") or data.get("measurement_type"),
        "qty": float(data.get("qty") or 0),
        "length_1": float(data.get("length_1") or 0),
        "length_2": float(data.get("length_2") or 0),
        "width_1": float(data.get("width_1") or 0),
        "width_2": float(data.get("width_2") or 0),
        "depth": float(data.get("depth") or data.get("avg_depth") or 0),
        "height": float(data.get("height") or 0),
        "avg_length": float(data.get("avg_length") or 0),
        "avg_width": float(data.get("avg_width") or 0),
        "avg_depth": float(data.get("avg_depth") or 0),
        "calculated_quantity": float(data.get("calculated_quantity") or 0),
        "nos": float(data.get("nos") or 0),
        "dia_mm": float(data.get("dia_mm") or 0),
        "bend": float(data.get("bend") or 0),
        "dimensions_json": data.get("dimensions_json") or "",
        "boq_item_id": data.get("boq_item_id") or "",
        "boq_line_id": data.get("boq_line_id") or "",
        "preview_lines": [],
    }


def load_boq_lines_for_dpr(dpr_id: str) -> list:
    conn = get_conn()
    line_df = pd.read_sql_query(
        """
        SELECT line_id, boq_item_id, boq_number, boq_description, unit, billing_measurement,
               total_boq_quantity, done_quantity, billed_quantity, balance_quantity,
               pending_billing_quantity, progress_quantity
        FROM dpr_boq_lines WHERE dpr_id = ? ORDER BY id
        """,
        conn,
        params=(dpr_id,),
    )
    if line_df.empty:
        conn.close()
        return []

    meas_df = pd.read_sql_query(
        """
        SELECT measurement_type, measurement_method, width_1, width_2, length_1, length_2,
               height, depth, nos, dia_mm, bend, avg_width, avg_length, avg_depth, qty,
               calculated_quantity, unit, dimensions_json, boq_item_id, boq_line_id
        FROM dpr_measurements WHERE dpr_id = ? ORDER BY id
        """,
        conn,
        params=(dpr_id,),
    )
    conn.close()

    lines = []
    for _, ln in line_df.iterrows():
        line_id = ln["line_id"]
        meas_rows = meas_df[meas_df["boq_line_id"] == line_id] if "boq_line_id" in meas_df.columns else meas_df
        if meas_rows.empty and "boq_item_id" in meas_df.columns:
            meas_rows = meas_df[meas_df["boq_item_id"] == ln["boq_item_id"]]
        measurements = [row.to_dict() for _, row in meas_rows.iterrows()]
        for m in measurements:
            if not m.get("preview_lines"):
                m["preview_lines"] = []
        lines.append(
            {
                "line_id": line_id,
                "boq_row_id": "",
                "boq_item_id": ln["boq_item_id"],
                "boq_number": ln["boq_number"],
                "boq_description": ln["boq_description"],
                "unit": ln["unit"],
                "billing_measurement": ln["billing_measurement"],
                "stats": {
                    "total_qty": ln["total_boq_quantity"],
                    "done_qty": ln["done_quantity"],
                    "billed_qty": ln["billed_quantity"],
                    "balance_qty": ln["balance_quantity"],
                    "pending_billing_qty": ln["pending_billing_quantity"],
                },
                "measurements": measurements,
                "progress_quantity": float(ln["progress_quantity"] or 0),
            }
        )
    return lines


def load_legacy_single_boq_line(dpr_id: str, report: dict) -> list:
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT measurement_type, measurement_method, width_1, width_2, length_1, length_2,
               height, depth, nos, dia_mm, bend, avg_width, avg_length, avg_depth, qty,
               calculated_quantity, unit, dimensions_json, boq_item_id, boq_line_id
        FROM dpr_measurements WHERE dpr_id = ? ORDER BY id
        """,
        conn,
        params=(dpr_id,),
    )
    conn.close()
    measurements = [row.to_dict() for _, row in df.iterrows()]
    if not report.get("boq_item_id"):
        return []
    stats = get_boq_progress_stats(report["boq_item_id"])
    return [
        build_boq_line(
            "",
            report["boq_item_id"],
            report.get("boq_number") or "",
            report.get("boq_description") or "",
            report.get("unit") or "",
            report.get("billing_measurement") or "No",
            stats,
            measurements,
            line_id="legacy",
        )
    ]


def flatten_measurements(boq_lines: list) -> list:
    out = []
    for line in boq_lines:
        lid = line.get("line_id") or ""
        bid = line.get("boq_item_id") or ""
        for m in line.get("measurements") or []:
            row = dict(m)
            row["boq_item_id"] = bid
            row["boq_line_id"] = lid
            out.append(row)
    return out


def persist_boq_lines(conn, dpr_id: str, boq_lines: list) -> None:
    conn.execute("DELETE FROM dpr_boq_lines WHERE dpr_id = ?", (dpr_id,))
    for line in boq_lines:
        line_id = line.get("line_id") or generate_id("DBL", "dpr_boq_lines", conn=conn)
        line["line_id"] = line_id
        conn.execute(
            """
            INSERT INTO dpr_boq_lines(
                line_id, dpr_id, boq_item_id, boq_number, boq_description, unit,
                billing_measurement, total_boq_quantity, done_quantity, billed_quantity,
                balance_quantity, pending_billing_quantity, progress_quantity
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                line_id,
                dpr_id,
                line["boq_item_id"],
                line.get("boq_number", ""),
                line.get("boq_description", ""),
                line.get("unit", ""),
                line.get("billing_measurement", "No"),
                line.get("total_boq_quantity", 0),
                line.get("done_quantity", 0),
                line.get("billed_quantity", 0),
                line.get("balance_quantity", 0),
                line.get("pending_billing_quantity", 0),
                line.get("progress_quantity", 0),
            ),
        )


def delete_boq_lines_for_dpr(conn, dpr_id: str) -> None:
    conn.execute("DELETE FROM dpr_boq_lines WHERE dpr_id = ?", (dpr_id,))
