"""Material planning & consumption control — planned (BOQ/DPR) vs actual (issues)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from modules.database import DATE_FMT, _add_column_if_missing, generate_id, get_conn
from modules.phase3_integration_db import (
    EXECUTED_DPR_STATUSES,
    ensure_phase3_schema,
    estimate_material_consumption,
    load_boq_material_map,
    save_boq_material_map_row,
)

MATERIAL_CATEGORIES: tuple[str, ...] = (
    "Cement",
    "Steel",
    "Sand",
    "Aggregate",
    "Blocks",
    "Electrical Materials",
    "Plumbing Materials",
    "Other",
)


def ensure_material_planning_schema(conn=None) -> None:
    own = conn is None
    conn = conn or get_conn()
    ensure_phase3_schema(conn)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS material_planning_snapshots(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id TEXT UNIQUE,
            project_name TEXT NOT NULL,
            period_from TEXT,
            period_to TEXT,
            material_key TEXT,
            material_name TEXT,
            material_code TEXT,
            unit TEXT,
            planned_qty REAL DEFAULT 0,
            actual_qty REAL DEFAULT 0,
            variance_qty REAL DEFAULT 0,
            created_at TEXT
        )
        """
    )
    if own:
        conn.commit()
        conn.close()


def material_key(material_code: str, material_name: str) -> str:
    code = (material_code or "").strip().lower()
    name = (material_name or "").strip().lower()
    return code or name or "unknown"


def delete_boq_material_map_row(map_id: str) -> bool:
    if not map_id:
        return False
    conn = get_conn()
    ensure_phase3_schema(conn)
    cur = conn.execute("DELETE FROM boq_material_map WHERE map_id = ?", (map_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def _status_placeholders(statuses: tuple[str, ...]) -> str:
    return ",".join("?" * len(statuses))


def _sum_progress_for_boq_period(
    conn,
    boq_item_id: str,
    statuses: tuple[str, ...],
    date_from: str = "",
    date_to: str = "",
) -> float:
    ph = _status_placeholders(statuses)
    date_clause = ""
    date_params: list = []
    if date_from:
        date_clause += " AND r.dpr_date >= ?"
        date_params.append(date_from)
    if date_to:
        date_clause += " AND r.dpr_date <= ?"
        date_params.append(date_to)
    params: list = [boq_item_id, *statuses, *date_params, boq_item_id, *statuses, *date_params]
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(q), 0) FROM (
            SELECT r.progress_quantity AS q
            FROM dpr_reports r
            WHERE r.boq_item_id = ?
              AND COALESCE(r.status, '') IN ({ph})
              AND NOT EXISTS (SELECT 1 FROM dpr_boq_lines bl WHERE bl.dpr_id = r.dpr_id)
              {date_clause}
            UNION ALL
            SELECT bl.progress_quantity AS q
            FROM dpr_boq_lines bl
            INNER JOIN dpr_reports r ON r.dpr_id = bl.dpr_id
            WHERE bl.boq_item_id = ?
              AND COALESCE(r.status, '') IN ({ph})
              {date_clause}
        )
        """,
        params,
    ).fetchone()
    return round(float((row or [0])[0] or 0), 4)


def planned_qty_for_progress(progress_qty: float, qty_per_unit: float) -> float:
    return round(float(progress_qty or 0) * float(qty_per_unit or 0), 4)


def calc_planned_material_rows(
    boq_item_id: str,
    progress_qty: float,
) -> list[dict[str, Any]]:
    df = estimate_material_consumption(boq_item_id, progress_qty)
    if df.empty:
        return []
    rows = []
    for _, r in df.iterrows():
        est = float(r.get("estimated_qty") or 0)
        rows.append(
            {
                "material_name": r.get("material_name"),
                "material_code": r.get("material_code"),
                "material_key": material_key(r.get("material_code"), r.get("material_name")),
                "qty_per_unit": float(r.get("qty_per_unit") or 0),
                "planned_qty": est,
                "unit": r.get("unit") or "",
            }
        )
    return rows


def load_project_boq_items_for_mapping(project_name: str) -> pd.DataFrame:
    conn = get_conn()
    ensure_phase3_schema(conn)
    df = pd.read_sql_query(
        """
        SELECT boq_item_id, boq_number, description, unit, quantity,
               COALESCE(executed_quantity, 0) AS executed_quantity
        FROM project_boq_items
        WHERE project_name = ? OR project_id = ?
        ORDER BY boq_number, description
        """,
        conn,
        params=(project_name, project_name),
    )
    conn.close()
    return df


def _aggregate_planned_rows(
    project_name: str,
    *,
    date_from: str = "",
    date_to: str = "",
    use_executed_totals: bool = False,
) -> pd.DataFrame:
    conn = get_conn()
    ensure_phase3_schema(conn)
    boq_df = pd.read_sql_query(
        """
        SELECT boq_item_id, boq_number, description,
               COALESCE(executed_quantity, 0) AS executed_quantity
        FROM project_boq_items
        WHERE project_name = ? OR project_id = ?
        """,
        conn,
        params=(project_name, project_name),
    )
    if boq_df.empty:
        conn.close()
        return pd.DataFrame(
            columns=[
                "material_key",
                "material_name",
                "material_code",
                "unit",
                "planned_qty",
            ]
        )
    accum: dict[str, dict] = {}
    for _, boq in boq_df.iterrows():
        bid = boq["boq_item_id"]
        maps = load_boq_material_map(bid)
        if not maps:
            continue
        if use_executed_totals and not date_from and not date_to:
            prog = float(boq["executed_quantity"] or 0)
        else:
            prog = _sum_progress_for_boq_period(
                conn,
                bid,
                EXECUTED_DPR_STATUSES,
                date_from=date_from,
                date_to=date_to,
            )
        if prog <= 0:
            continue
        for m in maps:
            key = material_key(m.get("material_code"), m.get("material_name"))
            add = planned_qty_for_progress(prog, float(m.get("qty_per_unit") or 0))
            if key not in accum:
                accum[key] = {
                    "material_key": key,
                    "material_name": m.get("material_name"),
                    "material_code": m.get("material_code"),
                    "unit": m.get("unit") or "",
                    "planned_qty": 0.0,
                }
            accum[key]["planned_qty"] = round(accum[key]["planned_qty"] + add, 4)
    conn.close()
    if not accum:
        return pd.DataFrame(
            columns=[
                "material_key",
                "material_name",
                "material_code",
                "unit",
                "planned_qty",
            ]
        )
    return pd.DataFrame(list(accum.values()))


def load_actual_issues_by_project(
    project_name: str,
    *,
    date_from: str = "",
    date_to: str = "",
) -> pd.DataFrame:
    conn = get_conn()
    sql = """
        SELECT material_code, material_name,
               COALESCE(SUM(quantity), 0) AS actual_qty,
               COUNT(*) AS issue_count
        FROM material_issues
        WHERE project_name = ?
    """
    params: list = [project_name]
    if date_from:
        sql += " AND issue_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND issue_date <= ?"
        params.append(date_to)
    sql += " GROUP BY material_code, material_name"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    if df.empty:
        return pd.DataFrame(
            columns=[
                "material_key",
                "material_name",
                "material_code",
                "unit",
                "actual_qty",
                "issue_count",
            ]
        )
    df["material_key"] = df.apply(
        lambda r: material_key(r.get("material_code"), r.get("material_name")),
        axis=1,
    )
    df["unit"] = ""
    return df


def load_planned_vs_actual(
    project_name: str,
    *,
    date_from: str = "",
    date_to: str = "",
) -> pd.DataFrame:
    if not project_name:
        return pd.DataFrame()
    use_totals = not date_from and not date_to
    planned = _aggregate_planned_rows(
        project_name,
        date_from=date_from,
        date_to=date_to,
        use_executed_totals=use_totals,
    )
    actual = load_actual_issues_by_project(
        project_name, date_from=date_from, date_to=date_to
    )
    if planned.empty and actual.empty:
        return pd.DataFrame()
    if planned.empty:
        planned = pd.DataFrame(columns=["material_key", "material_name", "material_code", "unit", "planned_qty"])
    if actual.empty:
        actual = pd.DataFrame(columns=["material_key", "material_name", "material_code", "unit", "actual_qty"])
    merged = pd.merge(
        planned,
        actual[["material_key", "material_name", "material_code", "actual_qty", "issue_count"]],
        on="material_key",
        how="outer",
        suffixes=("_plan", "_act"),
    )
    if "material_name_plan" in merged.columns:
        merged["material_name"] = merged["material_name_plan"].combine_first(
            merged.get("material_name_act")
        )
    elif "material_name" not in merged.columns:
        merged["material_name"] = merged.get("material_name_act", "")
    if "material_code_plan" in merged.columns:
        merged["material_code"] = merged["material_code_plan"].combine_first(
            merged.get("material_code_act", "")
        )
    merged["planned_qty"] = merged["planned_qty"].fillna(0).astype(float)
    merged["actual_qty"] = merged["actual_qty"].fillna(0).astype(float)
    merged["variance_qty"] = (merged["actual_qty"] - merged["planned_qty"]).round(4)
    merged["variance_status"] = merged["variance_qty"].apply(_variance_label)
    merged["is_excess"] = merged["variance_qty"] > 0.0001
    merged["unit"] = merged.get("unit", "").fillna("")
    cols = [
        "material_name",
        "material_code",
        "unit",
        "planned_qty",
        "actual_qty",
        "variance_qty",
        "variance_status",
        "is_excess",
    ]
    if "issue_count" in merged.columns:
        cols.append("issue_count")
    return merged[cols].sort_values("material_name", na_position="last")


def _variance_label(variance: float) -> str:
    if variance > 0.0001:
        return "Excess (Surplus)"
    if variance < -0.0001:
        return "Shortage"
    return "Balanced"


def load_variance_report(
    project_name: str = "",
    *,
    date_from: str = "",
    date_to: str = "",
) -> pd.DataFrame:
    if project_name:
        return load_planned_vs_actual(project_name, date_from=date_from, date_to=date_to)
    from modules.database import load_project_names

    frames = []
    for pname in load_project_names():
        df = load_planned_vs_actual(pname, date_from=date_from, date_to=date_to)
        if not df.empty:
            df = df.copy()
            df.insert(0, "project_name", pname)
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def load_boq_item_consumption_report(
    project_name: str = "",
    *,
    date_from: str = "",
    date_to: str = "",
) -> pd.DataFrame:
    conn = get_conn()
    ensure_phase3_schema(conn)
    clauses = ["1=1"]
    params: list = []
    if project_name:
        clauses.append("(b.project_name = ? OR b.project_id = ?)")
        params.extend([project_name, project_name])
    df = pd.read_sql_query(
        f"""
        SELECT b.project_name, b.boq_number, b.description AS boq_description,
               b.boq_item_id, m.material_name, m.material_code, m.qty_per_unit,
               m.unit AS map_unit,
               COALESCE(b.executed_quantity, 0) AS executed_boq_qty
        FROM boq_material_map m
        JOIN project_boq_items b ON b.boq_item_id = m.boq_item_id
        WHERE {" AND ".join(clauses)}
        ORDER BY b.project_name, b.boq_number, m.material_name
        """,
        conn,
        params=params or None,
    )
    conn.close()
    if df.empty:
        return df
    rows = []
    for _, r in df.iterrows():
        bid = r["boq_item_id"]
        if date_from or date_to:
            conn2 = get_conn()
            prog = _sum_progress_for_boq_period(
                conn2,
                bid,
                EXECUTED_DPR_STATUSES,
                date_from=date_from,
                date_to=date_to,
            )
            conn2.close()
        else:
            prog = float(r["executed_boq_qty"] or 0)
        planned = planned_qty_for_progress(prog, float(r["qty_per_unit"] or 0))
        rows.append(
            {
                **r.to_dict(),
                "period_progress_qty": prog,
                "planned_material_qty": planned,
            }
        )
    return pd.DataFrame(rows)


def load_project_material_summary(
    *,
    date_from: str = "",
    date_to: str = "",
) -> pd.DataFrame:
    from modules.database import load_project_names

    summaries = []
    for pname in load_project_names():
        df = load_planned_vs_actual(pname, date_from=date_from, date_to=date_to)
        planned_total = float(df["planned_qty"].sum()) if not df.empty else 0.0
        actual_total = float(df["actual_qty"].sum()) if not df.empty else 0.0
        excess_count = int((df["is_excess"]).sum()) if not df.empty and "is_excess" in df.columns else 0
        summaries.append(
            {
                "project_name": pname,
                "material_lines": len(df),
                "planned_qty_total": round(planned_total, 4),
                "actual_qty_total": round(actual_total, 4),
                "variance_total": round(actual_total - planned_total, 4),
                "excess_materials": excess_count,
            }
        )
    return pd.DataFrame(summaries)


def save_material_planning_snapshot(
    project_name: str,
    period_from: str,
    period_to: str,
    rows: list[dict],
) -> str:
    conn = get_conn()
    ensure_material_planning_schema(conn)
    snapshot_id = generate_id(
        "MPS",
        "material_planning_snapshots",
        id_column="snapshot_id",
        conn=conn,
    )
    ts = datetime.now().strftime("%d/%m/%Y %H:%M")
    for row in rows:
        conn.execute(
            """
            INSERT INTO material_planning_snapshots(
                snapshot_id, project_name, period_from, period_to,
                material_key, material_name, material_code, unit,
                planned_qty, actual_qty, variance_qty, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                snapshot_id,
                project_name,
                period_from,
                period_to,
                row.get("material_key", ""),
                row.get("material_name", ""),
                row.get("material_code", ""),
                row.get("unit", ""),
                float(row.get("planned_qty") or 0),
                float(row.get("actual_qty") or 0),
                float(row.get("variance_qty") or 0),
                ts,
            ),
        )
    conn.commit()
    conn.close()
    return snapshot_id


__all__ = [
    "MATERIAL_CATEGORIES",
    "calc_planned_material_rows",
    "delete_boq_material_map_row",
    "ensure_material_planning_schema",
    "load_actual_issues_by_project",
    "load_boq_item_consumption_report",
    "load_planned_vs_actual",
    "load_project_boq_items_for_mapping",
    "load_project_material_summary",
    "load_variance_report",
    "planned_qty_for_progress",
    "save_boq_material_map_row",
    "save_material_planning_snapshot",
]
