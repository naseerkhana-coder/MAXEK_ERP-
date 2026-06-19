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
