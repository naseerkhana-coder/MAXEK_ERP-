"""Staff monthly attendance — one summary record per monthly-salary staff per month."""

from __future__ import annotations

from datetime import datetime
from typing import Any

MODULE_ID = "monthly_staff_attendance"
RECORD_TABLE = "staff_monthly_attendance"


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _round2(value: float) -> float:
    return round(float(value or 0), 2)


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_column(db, table: str, column: str, col_type: str) -> None:
    if not _table_exists(db, table):
        return
    cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def ensure_staff_monthly_attendance_schema(db) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS staff_monthly_attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            year_month TEXT NOT NULL,
            worked_days REAL DEFAULT 0,
            half_days REAL DEFAULT 0,
            absent_days REAL DEFAULT 0,
            ot_hours REAL DEFAULT 0,
            project_id INTEGER,
            remarks TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(staff_id) REFERENCES staff(id),
            FOREIGN KEY(project_id) REFERENCES projects(id),
            UNIQUE(staff_id, year_month)
        )
    """)
    for col, ctype in (
        ("worked_days", "REAL DEFAULT 0"),
        ("half_days", "REAL DEFAULT 0"),
        ("absent_days", "REAL DEFAULT 0"),
        ("ot_hours", "REAL DEFAULT 0"),
        ("project_id", "INTEGER"),
        ("remarks", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, RECORD_TABLE, col, ctype)
    db.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS idx_staff_monthly_attendance_staff_month "
        f"ON {RECORD_TABLE}(staff_id, year_month)"
    )


def list_monthly_staff_for_attendance(db) -> list[dict]:
    rows = db.execute(
        "SELECT id, employee_code, staff_name, salary_type, photo "
        "FROM staff "
        "WHERE (status IS NULL OR status = 'Active') "
        "AND COALESCE(salary_type, 'Monthly') = 'Monthly' "
        "ORDER BY staff_name, employee_code"
    ).fetchall()
    return [dict(r) for r in rows]


def list_monthly_attendance_records(db) -> list[dict]:
    rows = db.execute(
        "SELECT m.*, s.staff_name, s.employee_code, "
        "p.project_name, p.project_code "
        f"FROM {RECORD_TABLE} m "
        "JOIN staff s ON m.staff_id = s.id "
        "LEFT JOIN projects p ON m.project_id = p.id "
        "ORDER BY m.year_month DESC, s.staff_name"
    ).fetchall()
    return [dict(r) for r in rows]


def get_monthly_attendance_record(db, record_id: int) -> dict | None:
    row = db.execute(
        "SELECT m.*, s.staff_name, s.employee_code, "
        "p.project_name, p.project_code "
        f"FROM {RECORD_TABLE} m "
        "JOIN staff s ON m.staff_id = s.id "
        "LEFT JOIN projects p ON m.project_id = p.id "
        "WHERE m.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def fetch_monthly_attendance_for_period(
    db,
    staff_id: int,
    start: str,
    end: str,
) -> dict | None:
    """Return aggregated monthly summary for payroll when approved records exist."""
    ym_start = (start or "")[:7]
    ym_end = (end or "")[:7]
    if not ym_start or not ym_end:
        return None
    rows = db.execute(
        f"SELECT * FROM {RECORD_TABLE} "
        "WHERE staff_id=? AND year_month >= ? AND year_month <= ? "
        "AND COALESCE(approval_status, 'Approved') NOT IN "
        "('Rejected by Checker', 'Rejected by Approver') "
        "ORDER BY year_month",
        (staff_id, ym_start, ym_end),
    ).fetchall()
    if not rows:
        return None
    worked = half = absent = ot = 0.0
    for row in rows:
        worked += float(row["worked_days"] or 0)
        half += float(row["half_days"] or 0)
        absent += float(row["absent_days"] or 0)
        ot += float(row["ot_hours"] or 0)
    present_days = worked + half * 0.5
    return {
        "worked_days": _round2(worked),
        "half_days": _round2(half),
        "absent_days": _round2(absent),
        "ot_hours": _round2(ot),
        "present_days": _round2(present_days),
        "present_dates": set(),
        "source": "monthly_summary",
    }


def _parse_monthly_form(form) -> dict[str, Any]:
    staff_id = form.get("monthly_staff_id", "").strip()
    year_month = form.get("monthly_year_month", "").strip()
    if not staff_id or not year_month:
        raise ValueError("Select staff and month.")
    try:
        worked_days = float(form.get("monthly_worked_days", "0") or 0)
        half_days = float(form.get("monthly_half_days", "0") or 0)
        absent_days = float(form.get("monthly_absent_days", "0") or 0)
        ot_hours = float(form.get("monthly_ot_hours", "0") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("Enter valid numeric values for days and OT hours.") from exc
    if worked_days < 0 or half_days < 0 or absent_days < 0 or ot_hours < 0:
        raise ValueError("Days and OT hours cannot be negative.")
    project_id = form.get("monthly_project_id", "").strip() or None
    remarks = form.get("monthly_remarks", "").strip()
    return {
        "staff_id": int(staff_id),
        "year_month": year_month,
        "worked_days": _round2(worked_days),
        "half_days": _round2(half_days),
        "absent_days": _round2(absent_days),
        "ot_hours": _round2(ot_hours),
        "project_id": int(project_id) if project_id else None,
        "remarks": remarks,
    }


def save_monthly_attendance_from_form(
    db,
    form,
    *,
    username: str,
    record_id: int | None = None,
) -> int:
    payload = _parse_monthly_form(form)
    now = _now_ts()
    if record_id:
        existing = db.execute(
            f"SELECT id FROM {RECORD_TABLE} WHERE id=?",
            (record_id,),
        ).fetchone()
        if not existing:
            raise ValueError("Monthly attendance record not found.")
        duplicate = db.execute(
            f"SELECT id FROM {RECORD_TABLE} "
            "WHERE staff_id=? AND year_month=? AND id!=?",
            (payload["staff_id"], payload["year_month"], record_id),
        ).fetchone()
        if duplicate:
            raise ValueError(
                "Another monthly attendance entry already exists for this staff and month."
            )
        db.execute(
            f"UPDATE {RECORD_TABLE} SET "
            "staff_id=?, year_month=?, worked_days=?, half_days=?, absent_days=?, "
            "ot_hours=?, project_id=?, remarks=?, modified_at=? "
            "WHERE id=?",
            (
                payload["staff_id"],
                payload["year_month"],
                payload["worked_days"],
                payload["half_days"],
                payload["absent_days"],
                payload["ot_hours"],
                payload["project_id"],
                payload["remarks"],
                now,
                record_id,
            ),
        )
        return record_id

    duplicate = db.execute(
        f"SELECT id FROM {RECORD_TABLE} WHERE staff_id=? AND year_month=?",
        (payload["staff_id"], payload["year_month"]),
    ).fetchone()
    if duplicate:
        raise ValueError(
            "Monthly attendance already exists for this staff and month. "
            "Use Edit to update it."
        )
    db.execute(
        f"INSERT INTO {RECORD_TABLE}("
        "staff_id, year_month, worked_days, half_days, absent_days, ot_hours, "
        "project_id, remarks, approval_status, created_by, created_at, modified_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            payload["staff_id"],
            payload["year_month"],
            payload["worked_days"],
            payload["half_days"],
            payload["absent_days"],
            payload["ot_hours"],
            payload["project_id"],
            payload["remarks"],
            "Pending Checker",
            username,
            now,
            now,
        ),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


SUBCONTRACTOR_ATTENDANCE_STATUSES = (
    "Present",
    "Absent",
    "Half Day",
    "Leave",
)


def compute_attendance_hours(
    in_time: str,
    out_time: str,
    break_hours: float = 0.0,
) -> tuple[float, float]:
    """Return (total_hours, ot_hours) from in/out times."""
    from datetime import datetime

    start_dt = datetime.strptime(in_time, "%H:%M")
    end_dt = datetime.strptime(out_time, "%H:%M")
    break_hours_val = float(break_hours or 0)
    total_hours = (end_dt - start_dt).seconds / 3600 - break_hours_val
    if total_hours < 0:
        total_hours += 24
    ot_hours = max(total_hours - 8, 0)
    return _round2(total_hours), _round2(ot_hours)


def _worker_trade_row(db, designation_text: str | None) -> dict | None:
    name = (designation_text or "").strip()
    if not name:
        return None
    row = db.execute(
        "SELECT id, trade_name FROM trades WHERE trade_name=? AND status='Active'",
        (name,),
    ).fetchone()
    return dict(row) if row else None


def list_trades_for_subcontractor(db, subcontractor_id: int) -> list[dict]:
    """Distinct trades (from worker designation) for a subcontractor's active workers."""
    rows = db.execute(
        "SELECT DISTINCT TRIM(designation) AS trade_name "
        "FROM workers "
        "WHERE subcontractor_id=? "
        "AND COALESCE(worker_category, 'Company Staff') = 'Sub Contractor Staff' "
        "AND (status IS NULL OR status = 'Active') "
        "AND designation IS NOT NULL AND TRIM(designation) != '' "
        "ORDER BY trade_name",
        (subcontractor_id,),
    ).fetchall()
    result = []
    for row in rows:
        trade_name = row["trade_name"]
        trade = _worker_trade_row(db, trade_name)
        result.append({
            "trade_name": trade_name,
            "trade_id": trade["id"] if trade else None,
        })
    return result


def list_subcontractor_workers_for_attendance(
    db,
    subcontractor_id: int,
    *,
    trade_id: int | None = None,
    trade_name: str | None = None,
) -> list[dict]:
    """Workers under subcontractor, optionally filtered by trade (designation)."""
    sql = (
        "SELECT w.id, w.worker_code, w.worker_name, w.photo, w.designation, "
        "w.working_hours, w.subcontractor_id "
        "FROM workers w "
        "WHERE w.subcontractor_id=? "
        "AND COALESCE(w.worker_category, 'Company Staff') = 'Sub Contractor Staff' "
        "AND (w.status IS NULL OR w.status = 'Active') "
    )
    params: list = [subcontractor_id]
    if trade_name:
        sql += "AND TRIM(w.designation) = ? "
        params.append(trade_name.strip())
    elif trade_id:
        trade_row = db.execute(
            "SELECT trade_name FROM trades WHERE id=? AND status='Active'",
            (trade_id,),
        ).fetchone()
        if not trade_row:
            return []
        sql += "AND TRIM(w.designation) = ? "
        params.append(trade_row["trade_name"])
    sql += "ORDER BY w.worker_name, w.worker_code"
    rows = db.execute(sql, params).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        trade = _worker_trade_row(db, item.get("designation"))
        item["trade_id"] = trade["id"] if trade else None
        item["trade_name"] = trade["trade_name"] if trade else (item.get("designation") or "")
        item["worker_ref"] = f"w:{item['id']}"
        items.append(item)
    return items


def save_bulk_subcontractor_attendance(
    db,
    form,
    *,
    username: str,
    create_approval_request,
    module_id: str,
    table: str,
    user_id=None,
) -> int:
    """Create one attendance row per selected subcontractor worker."""
    subcontractor_id = (form.get("bulk_subcontractor_id") or "").strip()
    attendance_date = (form.get("bulk_attendance_date") or "").strip()
    in_time = (form.get("bulk_in_time") or "").strip()
    out_time = (form.get("bulk_out_time") or "").strip()
    break_hours_raw = (form.get("bulk_break_hours") or "0").strip()
    project_id = (form.get("bulk_project_id") or "").strip() or None
    default_status = (form.get("bulk_default_status") or "Present").strip()
    worker_ids = form.getlist("bulk_workers")

    if not subcontractor_id:
        raise ValueError("Select a subcontractor.")
    if not attendance_date:
        raise ValueError("Attendance date is required.")
    if not in_time or not out_time:
        raise ValueError("In time and out time are required.")
    if not worker_ids:
        raise ValueError("Select at least one worker.")

    try:
        break_hours_val = float(break_hours_raw or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("Enter a valid break hours value.") from exc

    total_hours, ot_hours = compute_attendance_hours(in_time, out_time, break_hours_val)
    sub_id = int(subcontractor_id)
    saved = 0

    for wid_raw in worker_ids:
        try:
            worker_id = int(wid_raw)
        except (TypeError, ValueError):
            continue
        worker = db.execute(
            "SELECT id, designation FROM workers "
            "WHERE id=? AND subcontractor_id=? "
            "AND COALESCE(worker_category, 'Company Staff') = 'Sub Contractor Staff'",
            (worker_id, sub_id),
        ).fetchone()
        if not worker:
            continue
        status = (form.get(f"bulk_status_{worker_id}") or default_status).strip()
        if status not in SUBCONTRACTOR_ATTENDANCE_STATUSES:
            status = default_status if default_status in SUBCONTRACTOR_ATTENDANCE_STATUSES else "Present"
        trade = _worker_trade_row(db, worker["designation"])
        trade_id = trade["id"] if trade else None
        db.execute(
            "INSERT INTO attendance("
            "worker_id, worker_source, project_id, attendance_date, "
            "in_time, out_time, break_hours, total_hours, ot_hours, status, "
            "approval_status, trade_id, designation_id"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                worker_id,
                "worker",
                int(project_id) if project_id else None,
                attendance_date,
                in_time,
                out_time,
                break_hours_val,
                total_hours,
                ot_hours,
                status,
                "Pending Checker",
                trade_id,
                None,
            ),
        )
        record_id_new = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        create_approval_request(
            db, module_id, record_id_new, table, username, user_id
        )
        saved += 1

    if saved == 0:
        raise ValueError("No valid workers were saved.")
    return saved
