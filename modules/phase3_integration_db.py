"""Phase 3 integration — schema, BOQ/billing/profitability sync queries."""

from __future__ import annotations

from typing import Any

import pandas as pd

from modules.database import _add_column_if_missing, generate_id, get_conn, scalar_query

# DPR statuses that count toward BOQ executed quantity (post engineer approval).
EXECUTED_DPR_STATUSES = ("Engineer Approved", "Client Approved", "Billed")

# Statuses eligible for client billing (billable measurements).
BILLABLE_DPR_STATUSES = EXECUTED_DPR_STATUSES


def ensure_phase3_schema(conn=None) -> None:
    own = conn is None
    conn = conn or get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS boq_material_map(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            map_id TEXT UNIQUE,
            boq_item_id TEXT NOT NULL,
            material_id TEXT,
            material_code TEXT,
            material_name TEXT NOT NULL,
            qty_per_unit REAL NOT NULL DEFAULT 0,
            unit TEXT,
            remarks TEXT,
            created_at TEXT
        )
        """
    )
    for col, typ in (
        ("executed_quantity", "REAL DEFAULT 0"),
        ("balance_boq_quantity", "REAL DEFAULT 0"),
        ("client_billed_quantity", "REAL DEFAULT 0"),
        ("revenue_earned", "REAL DEFAULT 0"),
    ):
        _add_column_if_missing(cur, "project_boq_items", col, typ)
    if own:
        conn.commit()
        conn.close()


def _status_placeholders(statuses: tuple[str, ...]) -> str:
    return ",".join("?" * len(statuses))


def _sum_progress_for_boq(conn, boq_item_id: str, statuses: tuple[str, ...]) -> float:
    ph = _status_placeholders(statuses)
    params = (boq_item_id, *statuses, boq_item_id, *statuses)
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(q), 0) FROM (
            SELECT r.progress_quantity AS q
            FROM dpr_reports r
            WHERE r.boq_item_id = ?
              AND COALESCE(r.status, '') IN ({ph})
              AND NOT EXISTS (SELECT 1 FROM dpr_boq_lines bl WHERE bl.dpr_id = r.dpr_id)
            UNION ALL
            SELECT bl.progress_quantity AS q
            FROM dpr_boq_lines bl
            INNER JOIN dpr_reports r ON r.dpr_id = bl.dpr_id
            WHERE bl.boq_item_id = ?
              AND COALESCE(r.status, '') IN ({ph})
        )
        """,
        params,
    ).fetchone()
    return round(float((row or [0])[0] or 0), 4)


def _sum_billable_for_boq(conn, boq_item_id: str, statuses: tuple[str, ...]) -> float:
    ph = _status_placeholders(statuses)
    params: list = [boq_item_id, *statuses, boq_item_id, *statuses]
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(q), 0) FROM (
            SELECT COALESCE(
                (SELECT SUM(m.calculated_quantity)
                 FROM dpr_measurements m
                 WHERE m.dpr_id = r.dpr_id AND COALESCE(m.include_in_client_bill, 1) = 1),
                CASE WHEN UPPER(COALESCE(r.billing_measurement, '')) = 'YES'
                     THEN r.progress_quantity ELSE 0 END
            ) AS q
            FROM dpr_reports r
            WHERE r.boq_item_id = ?
              AND COALESCE(r.status, '') IN ({ph})
              AND NOT EXISTS (SELECT 1 FROM dpr_boq_lines bl WHERE bl.dpr_id = r.dpr_id)
            UNION ALL
            SELECT COALESCE(
                (SELECT SUM(m.calculated_quantity)
                 FROM dpr_measurements m
                 WHERE m.dpr_id = bl.dpr_id AND bl.line_id = m.boq_line_id
                   AND COALESCE(m.include_in_client_bill, 1) = 1),
                CASE WHEN UPPER(COALESCE(bl.billing_measurement, '')) = 'YES'
                     THEN bl.billable_quantity ELSE 0 END
            ) AS q
            FROM dpr_boq_lines bl
            INNER JOIN dpr_reports r ON r.dpr_id = bl.dpr_id
            WHERE bl.boq_item_id = ?
              AND COALESCE(r.status, '') IN ({ph})
        )
        """,
        params,
    ).fetchone()
    return round(float((row or [0])[0] or 0), 4)


def _sum_client_billed_for_boq(conn, boq_item_id: str) -> float:
    from_lines = conn.execute(
        """
        SELECT COALESCE(SUM(quantity), 0)
        FROM client_bill_lines WHERE boq_item_id = ?
        """,
        (boq_item_id,),
    ).fetchone()[0]
    from_dpr = conn.execute(
        """
        SELECT COALESCE(SUM(COALESCE(client_billed_quantity, 0)), 0)
        FROM dpr_reports WHERE boq_item_id = ?
        """,
        (boq_item_id,),
    ).fetchone()[0]
    return round(max(float(from_lines or 0), float(from_dpr or 0)), 4)


def sync_boq_item_quantities(
    *,
    project_id: str | None = None,
    boq_item_id: str | None = None,
    conn=None,
) -> int:
    """Recompute executed / balance / billed / revenue on project_boq_items."""
    own = conn is None
    conn = conn or get_conn()
    ensure_phase3_schema(conn)
    clauses = ["1=1"]
    params: list = []
    if project_id:
        clauses.append("(project_id = ? OR project_name = ?)")
        params.extend([project_id, project_id])
    if boq_item_id:
        clauses.append("boq_item_id = ?")
        params.append(boq_item_id)
    rows = conn.execute(
        f"""
        SELECT boq_item_id, COALESCE(quantity, 0), COALESCE(approved_rate, 0)
        FROM project_boq_items WHERE {" AND ".join(clauses)}
        """,
        params,
    ).fetchall()
    updated = 0
    for bid, total_qty, rate in rows:
        executed = _sum_progress_for_boq(conn, bid, EXECUTED_DPR_STATUSES)
        billed = _sum_client_billed_for_boq(conn, bid)
        balance = round(max(float(total_qty or 0) - executed, 0.0), 4)
        revenue = round(executed * float(rate or 0), 2)
        conn.execute(
            """
            UPDATE project_boq_items
            SET executed_quantity = ?, balance_boq_quantity = ?,
                client_billed_quantity = ?, revenue_earned = ?
            WHERE boq_item_id = ?
            """,
            (executed, balance, billed, revenue, bid),
        )
        updated += 1
    if own:
        conn.commit()
        conn.close()
    return updated


def sync_project_progress_percent(project_id: str = "", project_name: str = "", conn=None) -> float:
    """Update projects.progress_percent from BOQ value-weighted execution."""
    own = conn is None
    conn = conn or get_conn()
    ensure_phase3_schema(conn)
    clauses = []
    params: list = []
    if project_id:
        clauses.append("(project_id = ? OR project_name = ?)")
        params.extend([project_id, project_name or project_id])
    elif project_name:
        clauses.append("project_name = ?")
        params.append(project_name)
    else:
        if own:
            conn.close()
        return 0.0
    where = " AND ".join(clauses)
    row = conn.execute(
        f"""
        SELECT
            COALESCE(SUM(quantity * COALESCE(approved_rate, 0)), 0),
            COALESCE(SUM(COALESCE(executed_quantity, 0) * COALESCE(approved_rate, 0)), 0)
        FROM project_boq_items WHERE {where}
        """,
        params,
    ).fetchone()
    total_val = float(row[0] or 0)
    done_val = float(row[1] or 0)
    pct = round(min(100.0, (done_val / total_val) * 100.0), 2) if total_val > 0 else 0.0
    conn.execute(
        """
        UPDATE projects SET progress_percent = ?
        WHERE (project_id = ? OR project_name = ?)
        """,
        (pct, project_id or project_name, project_name or project_id),
    )
    if own:
        conn.commit()
        conn.close()
    return pct


def get_boq_integration_stats(boq_item_id: str) -> dict[str, Any]:
    """BOQ progress stats used by DPR UI and dashboards (phase 3 source of truth)."""
    conn = get_conn()
    ensure_phase3_schema(conn)
    boq_df = pd.read_sql_query(
        """
        SELECT quantity, unit, boq_number, description, project_name, project_id,
               COALESCE(approved_rate, 0) AS approved_rate,
               COALESCE(executed_quantity, 0) AS executed_quantity,
               COALESCE(balance_boq_quantity, 0) AS balance_boq_quantity,
               COALESCE(client_billed_quantity, 0) AS client_billed_quantity,
               COALESCE(revenue_earned, 0) AS revenue_earned
        FROM project_boq_items WHERE boq_item_id = ? LIMIT 1
        """,
        conn,
        params=(boq_item_id,),
    )
    if boq_df.empty:
        conn.close()
        return {
            "total_qty": 0.0,
            "done_qty": 0.0,
            "executed_qty": 0.0,
            "billed_qty": 0.0,
            "balance_qty": 0.0,
            "pending_billing_qty": 0.0,
            "revenue_earned": 0.0,
            "unit": "",
            "boq_number": "",
            "description": "",
            "approved_rate": 0.0,
        }
    sync_boq_item_quantities(boq_item_id=boq_item_id, conn=conn)
    boq_df = pd.read_sql_query(
        """
        SELECT quantity, unit, boq_number, description,
               COALESCE(executed_quantity, 0) AS executed_quantity,
               COALESCE(balance_boq_quantity, 0) AS balance_boq_quantity,
               COALESCE(client_billed_quantity, 0) AS client_billed_quantity,
               COALESCE(revenue_earned, 0) AS revenue_earned,
               COALESCE(approved_rate, 0) AS approved_rate
        FROM project_boq_items WHERE boq_item_id = ? LIMIT 1
        """,
        conn,
        params=(boq_item_id,),
    )
    row = boq_df.iloc[0]
    total_qty = float(row["quantity"] or 0)
    executed = float(row["executed_quantity"] or 0)
    billed = float(row["client_billed_quantity"] or 0)
    billable = _sum_billable_for_boq(conn, boq_item_id, BILLABLE_DPR_STATUSES)
    pending_billing = round(max(billable - billed, 0.0), 4)
    conn.close()
    balance = float(row["balance_boq_quantity"] or max(total_qty - executed, 0))
    return {
        "total_qty": total_qty,
        "done_qty": executed,
        "executed_qty": executed,
        "billed_qty": billed,
        "balance_qty": balance,
        "pending_billing_qty": pending_billing,
        "revenue_earned": float(row["revenue_earned"] or 0),
        "unit": row["unit"] or "",
        "boq_number": row["boq_number"] or "",
        "description": row["description"] or "",
        "approved_rate": float(row["approved_rate"] or 0),
    }


def billing_quantities_for_dpr(dpr_id: str) -> dict[str, float]:
    conn = get_conn()
    report = conn.execute(
        """
        SELECT progress_quantity, COALESCE(client_billed_quantity, 0),
               UPPER(COALESCE(billing_measurement, '')) AS billing_flag
        FROM dpr_reports WHERE dpr_id = ?
        """,
        (dpr_id,),
    ).fetchone()
    billable = 0.0
    if report:
        if str(report[2] or "") == "YES":
            billable = conn.execute(
                """
                SELECT COALESCE(SUM(calculated_quantity), 0)
                FROM dpr_measurements
                WHERE dpr_id = ? AND COALESCE(include_in_client_bill, 1) = 1
                """,
                (dpr_id,),
            ).fetchone()[0]
            if float(billable or 0) <= 0:
                billable = float(report[0] or 0)
        else:
            lines = conn.execute(
                """
                SELECT line_id FROM dpr_boq_lines
                WHERE dpr_id = ? AND UPPER(COALESCE(billing_measurement, '')) = 'YES'
                """,
                (dpr_id,),
            ).fetchall()
            for (line_id,) in lines:
                billable += float(
                    conn.execute(
                        """
                        SELECT COALESCE(SUM(calculated_quantity), 0)
                        FROM dpr_measurements
                        WHERE dpr_id = ? AND boq_line_id = ?
                          AND COALESCE(include_in_client_bill, 1) = 1
                        """,
                        (dpr_id, line_id),
                    ).fetchone()[0]
                    or 0
                )
    billed = float((report or [0, 0])[1] or 0) if report else 0.0
    from_bills = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM client_bill_lines WHERE dpr_id = ?",
        (dpr_id,),
    ).fetchone()[0]
    billed = max(billed, float(from_bills or 0))
    conn.close()
    billable = round(float(billable or 0), 4)
    billed = round(billed, 4)
    return {
        "billable_qty": billable,
        "billed_qty": billed,
        "pending_billing_qty": round(max(billable - billed, 0.0), 4),
        "balance_billing_qty": round(max(billable - billed, 0.0), 4),
    }


def validate_client_bill_lines(lines: list[dict]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for i, line in enumerate(lines or [], start=1):
        dpr_id = str(line.get("dpr_id") or "").strip()
        qty = float(line.get("quantity") or 0)
        if qty <= 0:
            errors.append(f"Line {i}: quantity must be positive.")
            continue
        if not dpr_id:
            continue
        bq = billing_quantities_for_dpr(dpr_id)
        pending = bq["pending_billing_qty"]
        if qty > pending + 0.0001:
            errors.append(
                f"Line {i} (DPR {dpr_id}): bill qty {qty:,.4f} exceeds pending {pending:,.4f}."
            )
    return (len(errors) == 0, errors)


def load_boq_material_map(boq_item_id: str) -> list[dict]:
    conn = get_conn()
    ensure_phase3_schema(conn)
    df = pd.read_sql_query(
        """
        SELECT map_id, boq_item_id, material_id, material_code, material_name,
               qty_per_unit, unit, remarks
        FROM boq_material_map WHERE boq_item_id = ?
        ORDER BY material_name
        """,
        conn,
        params=(boq_item_id,),
    )
    conn.close()
    return df.to_dict("records") if not df.empty else []


def estimate_material_consumption(
    boq_item_id: str,
    progress_qty: float,
) -> pd.DataFrame:
    maps = load_boq_material_map(boq_item_id)
    if not maps or progress_qty <= 0:
        return pd.DataFrame(
            columns=["material_name", "material_code", "qty_per_unit", "estimated_qty", "unit"]
        )
    rows = []
    for m in maps:
        per = float(m.get("qty_per_unit") or 0)
        rows.append(
            {
                "material_name": m.get("material_name"),
                "material_code": m.get("material_code"),
                "qty_per_unit": per,
                "estimated_qty": round(per * progress_qty, 4),
                "unit": m.get("unit") or "",
            }
        )
    return pd.DataFrame(rows)


def aggregate_project_revenue(project_name: str, conn=None) -> dict[str, float]:
    own = conn is None
    conn = conn or get_conn()
    ensure_phase3_schema(conn)
    sync_boq_item_quantities(project_id=project_name, conn=conn)
    row = conn.execute(
        """
        SELECT COALESCE(SUM(revenue_earned), 0),
               COALESCE(SUM(executed_quantity * COALESCE(approved_rate, 0)), 0),
               COALESCE(SUM(client_billed_quantity * COALESCE(approved_rate, 0)), 0)
        FROM project_boq_items
        WHERE project_name = ? OR project_id = ?
        """,
        (project_name, project_name),
    ).fetchone()
    if own:
        conn.close()
    return {
        "revenue_earned": round(float(row[0] or 0), 2),
        "work_done_value": round(float(row[1] or 0), 2),
        "billed_revenue": round(float(row[2] or 0), 2),
    }


def check_integration_alerts(
    *,
    boq_item_id: str = "",
    project_name: str = "",
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    conn = get_conn()
    ensure_phase3_schema(conn)
    clauses = ["1=1"]
    params: list = []
    if boq_item_id:
        clauses.append("boq_item_id = ?")
        params.append(boq_item_id)
    if project_name:
        clauses.append("(project_name = ? OR project_id = ?)")
        params.extend([project_name, project_name])
    df = pd.read_sql_query(
        f"""
        SELECT boq_item_id, boq_number, project_name, quantity,
               COALESCE(executed_quantity, 0) AS executed_quantity,
               COALESCE(client_billed_quantity, 0) AS client_billed_quantity
        FROM project_boq_items WHERE {" AND ".join(clauses)}
        """,
        conn,
        params=params or None,
    )
    conn.close()
    for _, r in df.iterrows():
        total = float(r["quantity"] or 0)
        executed = float(r["executed_quantity"] or 0)
        billed = float(r["client_billed_quantity"] or 0)
        label = f"{r.get('boq_number') or r['boq_item_id']} ({r.get('project_name') or ''})"
        if total > 0 and executed > total + 0.0001:
            alerts.append(
                {
                    "level": "warning",
                    "code": "boq_exceeded",
                    "message": f"BOQ exceeded: executed {executed:,.2f} > BOQ {total:,.2f} — {label}",
                }
            )
        if executed > 0 and billed > executed + 0.0001:
            alerts.append(
                {
                    "level": "warning",
                    "code": "billing_exceeded",
                    "message": f"Billing exceeded execution: billed {billed:,.2f} > executed {executed:,.2f} — {label}",
                }
            )
        if total > 0 and executed / total > 1.0:
            alerts.append(
                {
                    "level": "warning",
                    "code": "progress_exceeded",
                    "message": f"Progress exceeds contract quantity on {label}",
                }
            )
    return alerts


def save_boq_material_map_row(
    boq_item_id: str,
    material_name: str,
    qty_per_unit: float,
    *,
    material_code: str = "",
    material_id: str = "",
    unit: str = "",
    remarks: str = "",
) -> str:
    conn = get_conn()
    ensure_phase3_schema(conn)
    map_id = generate_id("BMM", "boq_material_map", id_column="map_id", conn=conn)
    from datetime import datetime

    conn.execute(
        """
        INSERT INTO boq_material_map(
            map_id, boq_item_id, material_id, material_code, material_name,
            qty_per_unit, unit, remarks, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            map_id,
            boq_item_id,
            material_id,
            material_code,
            material_name,
            float(qty_per_unit),
            unit,
            remarks,
            datetime.now().strftime("%d/%m/%Y %H:%M"),
        ),
    )
    conn.commit()
    conn.close()
    return map_id


# --- Register report queries ---


def load_dpr_register(
    project_name: str = "",
    date_from: str = "",
    date_to: str = "",
) -> pd.DataFrame:
    conn = get_conn()
    sql = """
        SELECT dpr_id, dpr_date, project_name, boq_number, boq_description, unit,
               progress_quantity, done_quantity, billed_quantity, balance_quantity,
               pending_billing_quantity, status, engineer_approval, client_approval
        FROM dpr_reports WHERE 1=1
    """
    params: list = []
    if project_name:
        sql += " AND project_name = ?"
        params.append(project_name)
    if date_from:
        sql += " AND dpr_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND dpr_date <= ?"
        params.append(date_to)
    sql += " ORDER BY dpr_date DESC, id DESC"
    df = pd.read_sql_query(sql, conn, params=params or None)
    conn.close()
    return df


def load_measurement_book_register(
    project_name: str = "",
    date_from: str = "",
    date_to: str = "",
) -> pd.DataFrame:
    from modules.dpr_measurement_db import load_measurement_book

    return load_measurement_book(
        project_name=project_name,
        date_from=date_from,
        date_to=date_to,
        approved_only=True,
    )


def load_bbs_register(
    project_name: str = "",
    date_from: str = "",
    date_to: str = "",
) -> pd.DataFrame:
    from modules.dpr_measurement_db import load_steel_bbs_report

    return load_steel_bbs_report(project_name=project_name, date_from=date_from, date_to=date_to)


def load_client_billing_register(
    project_name: str = "",
    date_from: str = "",
    date_to: str = "",
) -> pd.DataFrame:
    conn = get_conn()
    sql = """
        SELECT b.bill_no, b.bill_date, b.client_name, b.project_name, b.status,
               b.total_amount, b.grand_total,
               l.dpr_id, l.boq_number, l.description, l.unit, l.quantity, l.rate, l.amount
        FROM client_bills b
        JOIN client_bill_lines l ON l.bill_id = b.bill_id
        WHERE 1=1
    """
    params: list = []
    if project_name:
        sql += " AND b.project_name = ?"
        params.append(project_name)
    if date_from:
        sql += " AND b.bill_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND b.bill_date <= ?"
        params.append(date_to)
    sql += " ORDER BY b.bill_date DESC, l.id"
    df = pd.read_sql_query(sql, conn, params=params or None)
    conn.close()
    return df


def load_quantity_progress_report(project_name: str = "") -> pd.DataFrame:
    conn = get_conn()
    ensure_phase3_schema(conn)
    sync_boq_item_quantities(project_id=project_name, conn=conn)
    clauses = ["1=1"]
    params: list = []
    if project_name:
        clauses.append("(project_name = ? OR project_id = ?)")
        params.extend([project_name, project_name])
    df = pd.read_sql_query(
        f"""
        SELECT project_name, boq_number, description, unit, quantity AS boq_qty,
               COALESCE(executed_quantity, 0) AS executed_qty,
               COALESCE(balance_boq_quantity, 0) AS balance_qty,
               COALESCE(client_billed_quantity, 0) AS billed_qty,
               COALESCE(revenue_earned, 0) AS revenue_earned,
               COALESCE(approved_rate, 0) AS rate
        FROM project_boq_items
        WHERE {" AND ".join(clauses)}
        ORDER BY project_name, boq_number
        """,
        conn,
        params=params or None,
    )
    conn.close()
    return df


def load_boq_consumption_report(project_name: str = "") -> pd.DataFrame:
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
               m.material_name, m.material_code, m.qty_per_unit, m.unit AS map_unit,
               COALESCE(b.executed_quantity, 0) AS executed_boq_qty,
               ROUND(COALESCE(b.executed_quantity, 0) * m.qty_per_unit, 4) AS estimated_material_qty
        FROM boq_material_map m
        JOIN project_boq_items b ON b.boq_item_id = m.boq_item_id
        WHERE {" AND ".join(clauses)}
        ORDER BY b.project_name, b.boq_number, m.material_name
        """,
        conn,
        params=params or None,
    )
    conn.close()
    return df
