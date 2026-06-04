"""Database access for worker payroll module."""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

from modules.database import DATE_FMT, generate_id, get_conn
from modules.worker_payroll_engine import (
    WORKFLOW_STATUSES,
    build_period_payroll,
    period_cycle_label,
    standard_hours_for_category,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_worker_payroll_schema():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS worker_payroll_runs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT UNIQUE,
            worker_id TEXT,
            worker_name TEXT,
            hour_category TEXT,
            period_start TEXT,
            period_end TEXT,
            cycle_type TEXT,
            payroll_month TEXT,
            worked_days INTEGER DEFAULT 0,
            worked_hours REAL DEFAULT 0,
            ot_hours REAL DEFAULT 0,
            gross_salary REAL DEFAULT 0,
            ot_amount REAL DEFAULT 0,
            total_deductions REAL DEFAULT 0,
            net_salary REAL DEFAULT 0,
            workflow_status TEXT DEFAULT 'Draft',
            payment_date TEXT,
            payment_mode TEXT,
            payment_reference TEXT,
            payment_remarks TEXT,
            receipt_path TEXT,
            bank_proof_path TEXT,
            signed_sheet_path TEXT,
            created_at TEXT,
            approved_at TEXT,
            paid_at TEXT
        );
        CREATE TABLE IF NOT EXISTS worker_payroll_deductions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deduction_id TEXT UNIQUE,
            run_id TEXT,
            worker_id TEXT,
            deduction_type TEXT,
            deduction_date TEXT,
            amount REAL,
            remarks TEXT
        );
        """
    )
    for col, typ in (
        ("hour_category", "TEXT"),
        ("daily_wage_rate", "REAL"),
        ("ot_rate", "REAL"),
    ):
        try:
            cur.execute(f"ALTER TABLE workers ADD COLUMN {col} {typ}")
        except Exception:
            pass
    conn.commit()
    conn.close()


def list_active_workers():
    return list_all_workers(active_only=True)


def list_all_workers(active_only: bool = False):
    ensure_worker_payroll_schema()
    conn = get_conn()
    sql = """
        SELECT worker_id, worker_name, subcontractor_name, trade_name, joining_date,
               COALESCE(daily_wage_rate, salary, 0) AS daily_wage_rate,
               COALESCE(ot_rate, overtime_rate, 0) AS ot_rate,
               COALESCE(hour_category, '8 Hr') AS hour_category,
               COALESCE(status, 'Active') AS status
        FROM workers
    """
    if active_only:
        sql += " WHERE UPPER(COALESCE(status,'')) IN ('ACTIVE', 'Active', '')"
    sql += " ORDER BY worker_name"
    df = pd.read_sql_query(sql, conn)
    conn.close()
    return df


def get_worker(worker_id: str) -> dict | None:
    ensure_worker_payroll_schema()
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT worker_id, worker_name, subcontractor_name, trade_name, joining_date,
               COALESCE(daily_wage_rate, salary, 0) AS daily_wage_rate,
               COALESCE(ot_rate, overtime_rate, 0) AS ot_rate,
               COALESCE(hour_category, '8 Hr') AS hour_category,
               COALESCE(status, 'Active') AS status
        FROM workers WHERE worker_id = ?
        """,
        conn,
        params=(worker_id,),
    )
    conn.close()
    if df.empty:
        return None
    row = df.iloc[0].to_dict()
    std = standard_hours_for_category(row.get("hour_category"))
    wage = float(row.get("daily_wage_rate") or 0)
    if not float(row.get("ot_rate") or 0) and wage and std:
        row["ot_rate"] = round(wage / std, 2)
    return row


def save_worker_profile(
    worker_id: str,
    worker_name: str,
    hour_category: str,
    daily_wage_rate: float,
    ot_rate: float,
    joining_date: str,
    status: str,
    subcontractor_name: str = "",
    trade_name: str = "",
):
    ensure_worker_payroll_schema()
    conn = get_conn()
    existing = conn.execute("SELECT id FROM workers WHERE worker_id = ?", (worker_id,)).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE workers SET worker_name=?, hour_category=?, daily_wage_rate=?, salary=?,
                   ot_rate=?, overtime_rate=?, joining_date=?, status=?,
                   subcontractor_name=COALESCE(NULLIF(?, ''), subcontractor_name),
                   trade_name=COALESCE(NULLIF(?, ''), trade_name)
            WHERE worker_id=?
            """,
            (
                worker_name,
                hour_category,
                daily_wage_rate,
                daily_wage_rate,
                ot_rate,
                ot_rate,
                joining_date,
                status,
                subcontractor_name,
                trade_name,
                worker_id,
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO workers(
                worker_id, worker_name, subcontractor_name, trade_name, joining_date,
                salary, daily_wage_rate, overtime_rate, ot_rate, hour_category, status
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                worker_id,
                worker_name,
                subcontractor_name,
                trade_name,
                joining_date,
                daily_wage_rate,
                daily_wage_rate,
                ot_rate,
                ot_rate,
                hour_category,
                status,
            ),
        )
    conn.commit()
    conn.close()


def load_worker_attendance(worker_id: str, from_date: str, to_date: str) -> list[dict]:
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT id, attendance_date, in_time, out_time, start_time, end_time,
               COALESCE(total_hours, worked_hours, 0) AS total_hours,
               COALESCE(ot_hours, overtime, 0) AS ot_hours, status, remarks
        FROM attendance
        WHERE COALESCE(worker_id, employee_id) = ?
          AND attendance_date >= ? AND attendance_date <= ?
        ORDER BY attendance_date
        """,
        conn,
        params=(worker_id, from_date, to_date),
    )
    conn.close()
    return df.to_dict("records")


def save_worker_attendance(
    worker_id: str,
    worker_name: str,
    attendance_date: str,
    in_time: str,
    out_time: str,
    total_hours: float,
    ot_hours: float,
    remarks: str = "",
    record_id: int | None = None,
):
    conn = get_conn()
    worker = get_worker(worker_id) or {}
    std = standard_hours_for_category(worker.get("hour_category"))
    fields = (
        worker_id,
        worker_name,
        worker_id,
        worker_name,
        "Sub Contractor Worker",
        attendance_date,
        in_time,
        out_time,
        in_time,
        out_time,
        total_hours,
        total_hours,
        ot_hours,
        ot_hours,
        "Present",
        remarks,
        std,
    )
    if record_id:
        conn.execute(
            """
            UPDATE attendance SET
                worker_id=?, worker_name=?, employee_id=?, employee_name=?, employee_type=?,
                attendance_date=?, in_time=?, out_time=?, start_time=?, end_time=?,
                total_hours=?, worked_hours=?, ot_hours=?, overtime=?, status=?, remarks=?,
                fixed_working_hours=?
            WHERE id=?
            """,
            (*fields, record_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO attendance(
                worker_id, worker_name, employee_id, employee_name, employee_type,
                attendance_date, in_time, out_time, start_time, end_time,
                total_hours, worked_hours, ot_hours, overtime, status, remarks, fixed_working_hours
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            fields,
        )
    conn.commit()
    conn.close()


def delete_worker_attendance(record_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM attendance WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


def calculate_period(worker_id: str, period_start: str, period_end: str) -> dict:
    worker = get_worker(worker_id)
    if not worker:
        return {}
    rows = load_worker_attendance(worker_id, period_start, period_end)
    summary = build_period_payroll(rows, worker)
    try:
        ps = datetime.strptime(period_start[:10], DATE_FMT)
        pe = datetime.strptime(period_end[:10], DATE_FMT)
        summary["cycle_type"] = period_cycle_label(ps, pe)
        summary["payroll_month"] = ps.strftime("%m/%Y")
    except ValueError:
        summary["cycle_type"] = "Custom"
        summary["payroll_month"] = ""
    summary["worker_id"] = worker_id
    summary["worker_name"] = worker.get("worker_name") or ""
    summary["hour_category"] = worker.get("hour_category") or "8 Hr"
    summary["period_start"] = period_start
    summary["period_end"] = period_end
    conn = get_conn()
    row = conn.execute(
        """
        SELECT run_id, workflow_status, total_deductions, net_salary
        FROM worker_payroll_runs
        WHERE worker_id=? AND period_start=? AND period_end=?
        """,
        (worker_id, period_start, period_end),
    ).fetchone()
    conn.close()
    if row:
        summary["run_id"] = row[0]
        summary["workflow_status"] = row[1]
        summary["saved_deductions"] = float(row[2] or 0)
        summary["saved_net"] = float(row[3] or 0)
    return summary


def list_deductions(run_id: str) -> list[dict]:
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM worker_payroll_deductions WHERE run_id = ? ORDER BY deduction_date, id",
        conn,
        params=(run_id,),
    )
    conn.close()
    return df.to_dict("records")


def add_deduction(run_id: str, worker_id: str, deduction_type: str, deduction_date: str, amount: float, remarks: str):
    ensure_worker_payroll_schema()
    did = generate_id("WD", "worker_payroll_deductions", id_column="deduction_id")
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO worker_payroll_deductions(
            deduction_id, run_id, worker_id, deduction_type, deduction_date, amount, remarks
        ) VALUES(?,?,?,?,?,?,?)
        """,
        (did, run_id, worker_id, deduction_type, deduction_date, amount, remarks),
    )
    conn.commit()
    conn.close()
    recalculate_run_net(run_id)
    return did


def delete_deduction(deduction_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT run_id FROM worker_payroll_deductions WHERE deduction_id = ?",
        (deduction_id,),
    ).fetchone()
    conn.execute("DELETE FROM worker_payroll_deductions WHERE deduction_id = ?", (deduction_id,))
    conn.commit()
    conn.close()
    if row and row[0]:
        recalculate_run_net(row[0])


def recalculate_run_net(run_id: str) -> float:
    """Re-sum deductions and update net payable on a saved payroll run."""
    ensure_worker_payroll_schema()
    run = get_payroll_run(run_id)
    if not run:
        return 0.0
    deductions = list_deductions(run_id)
    total_ded = round(sum(float(d.get("amount") or 0) for d in deductions), 2)
    gross = float(run.get("gross_salary") or 0)
    net = round(max(0.0, gross - total_ded), 2)
    conn = get_conn()
    conn.execute(
        "UPDATE worker_payroll_runs SET total_deductions=?, net_salary=? WHERE run_id=?",
        (total_ded, net, run_id),
    )
    conn.commit()
    conn.close()
    return net


def save_payroll_run(summary: dict, deductions_total: float, workflow_status: str = "Calculated") -> str:
    ensure_worker_payroll_schema()
    run_id = summary.get("run_id") or generate_id("WR", "worker_payroll_runs", id_column="run_id")
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    gross = float(summary.get("gross_salary") or 0)
    ot_amt = float(summary.get("ot_amount") or 0)
    net = round(max(0.0, gross - float(deductions_total or 0)), 2)

    conn = get_conn()
    existing = conn.execute(
        """
        SELECT run_id FROM worker_payroll_runs
        WHERE worker_id=? AND period_start=? AND period_end=?
        """,
        (summary["worker_id"], summary["period_start"], summary["period_end"]),
    ).fetchone()
    if existing:
        run_id = existing[0]

    params = (
        summary.get("worker_name"),
        summary.get("hour_category"),
        summary.get("period_start"),
        summary.get("period_end"),
        summary.get("cycle_type"),
        summary.get("payroll_month"),
        int(summary.get("worked_days") or 0),
        float(summary.get("worked_hours") or 0),
        float(summary.get("ot_hours") or 0),
        gross,
        ot_amt,
        float(deductions_total or 0),
        net,
        workflow_status,
    )
    if existing:
        conn.execute(
            """
            UPDATE worker_payroll_runs SET
                worker_name=?, hour_category=?, period_start=?, period_end=?, cycle_type=?,
                payroll_month=?, worked_days=?, worked_hours=?, ot_hours=?, gross_salary=?,
                ot_amount=?, total_deductions=?, net_salary=?, workflow_status=?
            WHERE run_id=?
            """,
            (*params, run_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO worker_payroll_runs(
                run_id, worker_id, worker_name, hour_category, period_start, period_end,
                cycle_type, payroll_month, worked_days, worked_hours, ot_hours,
                gross_salary, ot_amount, total_deductions, net_salary, workflow_status, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                summary["worker_id"],
                *params,
                now,
            ),
        )
    conn.commit()
    conn.close()
    summary["run_id"] = run_id
    return run_id


def get_payroll_run(run_id: str) -> dict | None:
    ensure_worker_payroll_schema()
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM worker_payroll_runs WHERE run_id = ?", conn, params=(run_id,))
    conn.close()
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def list_payroll_runs(worker_id: str | None = None, status: str | None = None) -> pd.DataFrame:
    ensure_worker_payroll_schema()
    conn = get_conn()
    sql = "SELECT * FROM worker_payroll_runs WHERE 1=1"
    params: list = []
    if worker_id:
        sql += " AND worker_id = ?"
        params.append(worker_id)
    if status:
        sql += " AND workflow_status = ?"
        params.append(status)
    sql += " ORDER BY id DESC"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def update_run_status(run_id: str, workflow_status: str):
    ensure_worker_payroll_schema()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    conn = get_conn()
    if workflow_status == "Approved":
        conn.execute(
            "UPDATE worker_payroll_runs SET workflow_status=?, approved_at=? WHERE run_id=?",
            (workflow_status, now, run_id),
        )
    elif workflow_status == "Paid":
        conn.execute(
            "UPDATE worker_payroll_runs SET workflow_status=?, paid_at=? WHERE run_id=?",
            (workflow_status, now, run_id),
        )
    else:
        conn.execute(
            "UPDATE worker_payroll_runs SET workflow_status=? WHERE run_id=?",
            (workflow_status, run_id),
        )
    conn.commit()
    conn.close()


def save_payment(
    run_id: str,
    payment_date: str,
    payment_mode: str,
    payment_reference: str,
    payment_remarks: str,
    receipt_path: str = "",
    bank_proof_path: str = "",
    signed_sheet_path: str = "",
):
    ensure_worker_payroll_schema()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    conn = get_conn()
    conn.execute(
        """
        UPDATE worker_payroll_runs SET
            payment_date=?, payment_mode=?, payment_reference=?, payment_remarks=?,
            receipt_path=?, bank_proof_path=?, signed_sheet_path=?,
            workflow_status='Paid', paid_at=?
        WHERE run_id=?
        """,
        (
            payment_date,
            payment_mode,
            payment_reference,
            payment_remarks,
            receipt_path,
            bank_proof_path,
            signed_sheet_path,
            now,
            run_id,
        ),
    )
    conn.commit()
    conn.close()


def salary_report_df(from_date: str | None = None, to_date: str | None = None) -> pd.DataFrame:
    ensure_worker_payroll_schema()
    conn = get_conn()
    sql = """
        SELECT worker_id AS "Worker ID",
               worker_name AS "Worker Name",
               hour_category AS "Category",
               period_start AS "Period From",
               period_end AS "Period To",
               cycle_type AS "Cycle",
               payroll_month AS "Payroll Month",
               worked_days AS "Worked Days",
               worked_hours AS "Worked Hours",
               ot_hours AS "OT Hours",
               ROUND(gross_salary - ot_amount, 2) AS "Base Gross",
               ot_amount AS "OT Amount",
               gross_salary AS "Gross Salary",
               total_deductions AS "Deductions",
               net_salary AS "Net Salary",
               workflow_status AS "Payment Status",
               payment_date AS "Payment Date",
               payment_mode AS "Payment Mode",
               payment_reference AS "Reference",
               payment_remarks AS "Payment Remarks"
        FROM worker_payroll_runs
        WHERE 1=1
    """
    params: list = []
    if from_date:
        sql += " AND period_end >= ?"
        params.append(from_date)
    if to_date:
        sql += " AND period_start <= ?"
        params.append(to_date)
    sql += " ORDER BY period_end DESC, worker_name"
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df
