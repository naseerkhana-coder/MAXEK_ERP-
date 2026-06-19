"""Employee Monthly Timesheet — daily register per staff/worker, monthly submit."""

from __future__ import annotations

import calendar
import re
from datetime import datetime
from typing import Any

from accounts_service import _safe_float

MODULE_ID = "employee_timesheet"
RECORD_TABLE = "employee_monthly_timesheets"
TIMESHEET_STATUSES = ("Draft", "Submitted", "Approved", "Rejected")


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


def _round2(value: float) -> float:
    return round(float(value or 0), 2)


def parse_year_month(raw: str) -> tuple[int, int]:
    return _parse_year_month(raw)


def _parse_year_month(raw: str) -> tuple[int, int]:
    raw = (raw or "").strip()
    m = re.match(r"^(\d{4})-(\d{1,2})$", raw)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^([A-Za-z]{3})-(\d{2,4})$", raw)
    if m:
        month = datetime.strptime(m.group(1), "%b").month
        year = int(m.group(2))
        if year < 100:
            year += 2000
        return year, month
    now = datetime.now()
    return now.year, now.month


def year_month_label(year: int, month: int) -> str:
    return datetime(year, month, 1).strftime("%b-%y")


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def ensure_employee_timesheet_schema(db) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS employee_monthly_timesheets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timesheet_ref TEXT UNIQUE,
            employee_source TEXT NOT NULL DEFAULT 'staff',
            staff_id INTEGER,
            worker_id INTEGER,
            subcontractor_id INTEGER,
            project_id INTEGER,
            year_month TEXT NOT NULL,
            sub_display_name TEXT,
            sub_display_code TEXT,
            employee_name TEXT,
            employee_code TEXT,
            designation TEXT,
            working_days REAL DEFAULT 0,
            leave_days REAL DEFAULT 0,
            holiday_days REAL DEFAULT 0,
            overtime_hours REAL DEFAULT 0,
            total_days REAL DEFAULT 0,
            total_salary_paid REAL DEFAULT 0,
            supervisor_signature TEXT,
            remarks TEXT,
            timesheet_status TEXT DEFAULT 'Draft',
            approval_status TEXT DEFAULT 'Pending Checker',
            submitted_at TEXT,
            approved_at TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(staff_id) REFERENCES staff(id),
            FOREIGN KEY(worker_id) REFERENCES workers(id),
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("timesheet_ref", "TEXT"), ("employee_source", "TEXT DEFAULT 'staff'"),
        ("staff_id", "INTEGER"), ("worker_id", "INTEGER"), ("subcontractor_id", "INTEGER"),
        ("project_id", "INTEGER"), ("year_month", "TEXT"),
        ("sub_display_name", "TEXT"), ("sub_display_code", "TEXT"),
        ("employee_name", "TEXT"), ("employee_code", "TEXT"), ("designation", "TEXT"),
        ("working_days", "REAL DEFAULT 0"), ("leave_days", "REAL DEFAULT 0"),
        ("holiday_days", "REAL DEFAULT 0"), ("overtime_hours", "REAL DEFAULT 0"),
        ("total_days", "REAL DEFAULT 0"), ("total_salary_paid", "REAL DEFAULT 0"),
        ("supervisor_signature", "TEXT"), ("remarks", "TEXT"),
        ("timesheet_status", "TEXT DEFAULT 'Draft'"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
        ("submitted_at", "TEXT"), ("approved_at", "TEXT"),
        ("created_by", "TEXT"), ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "employee_monthly_timesheets", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS employee_timesheet_days(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timesheet_id INTEGER NOT NULL,
            day_num INTEGER NOT NULL,
            start_time TEXT,
            start_ampm TEXT,
            end_time TEXT,
            end_ampm TEXT,
            break_hours REAL DEFAULT 0,
            overtime_hours REAL DEFAULT 0,
            project_name TEXT,
            salary_advance REAL DEFAULT 0,
            supervisor_sign TEXT,
            remarks TEXT,
            FOREIGN KEY(timesheet_id) REFERENCES employee_monthly_timesheets(id) ON DELETE CASCADE,
            UNIQUE(timesheet_id, day_num)
        )
    """)
    for col, ctype in (
        ("timesheet_id", "INTEGER"), ("day_num", "INTEGER"),
        ("start_time", "TEXT"), ("start_ampm", "TEXT"), ("end_time", "TEXT"), ("end_ampm", "TEXT"),
        ("break_hours", "REAL DEFAULT 0"), ("overtime_hours", "REAL DEFAULT 0"),
        ("project_name", "TEXT"), ("salary_advance", "REAL DEFAULT 0"),
        ("supervisor_sign", "TEXT"), ("remarks", "TEXT"),
    ):
        _ensure_column(db, "employee_timesheet_days", col, ctype)


def _next_timesheet_ref(db, year: int, month: int) -> str:
    ym = f"{year:04d}{month:02d}"
    row = db.execute(
        "SELECT timesheet_ref FROM employee_monthly_timesheets "
        "WHERE timesheet_ref LIKE ? ORDER BY id DESC LIMIT 1",
        (f"TS-{ym}-%",),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"-(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"TS-{ym}-{seq:04d}"


def _employee_snapshot(db, employee_source: str, employee_id: int) -> dict[str, Any]:
    if employee_source == "worker":
        row = db.execute(
            """
            SELECT w.id, w.worker_code AS employee_code, w.worker_name AS employee_name,
                   w.designation, w.subcontractor_id, w.project_id,
                   s.subcontractor_name, s.subcontractor_code
            FROM workers w
            LEFT JOIN subcontractors s ON w.subcontractor_id = s.id
            WHERE w.id=?
            """,
            (employee_id,),
        ).fetchone()
        if not row:
            raise ValueError("Worker not found.")
        data = dict(row)
        data["employee_source"] = "worker"
        data["staff_id"] = None
        data["worker_id"] = employee_id
        data["sub_display_name"] = data.get("subcontractor_name") or ""
        data["sub_display_code"] = data.get("subcontractor_code") or ""
        return data

    row = db.execute(
        "SELECT id, employee_code, staff_name AS employee_name, designation "
        "FROM staff WHERE id=?",
        (employee_id,),
    ).fetchone()
    if not row:
        raise ValueError("Staff member not found.")
    data = dict(row)
    data["employee_source"] = "staff"
    data["staff_id"] = employee_id
    data["worker_id"] = None
    data["subcontractor_id"] = None
    data["sub_display_name"] = ""
    data["sub_display_code"] = ""
    return data


def _ensure_day_rows(db, timesheet_id: int, year: int, month: int) -> None:
    total_days = days_in_month(year, month)
    for day in range(1, total_days + 1):
        exists = db.execute(
            "SELECT id FROM employee_timesheet_days WHERE timesheet_id=? AND day_num=?",
            (timesheet_id, day),
        ).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO employee_timesheet_days(timesheet_id, day_num) VALUES(?,?)",
                (timesheet_id, day),
            )


def _parse_days_from_form(form, year: int, month: int) -> list[dict[str, Any]]:
    total = days_in_month(year, month)
    days: list[dict[str, Any]] = []
    for day in range(1, total + 1):
        prefix = f"day_{day}_"
        days.append({
            "day_num": day,
            "start_time": (form.get(f"{prefix}start_time") or "").strip(),
            "start_ampm": (form.get(f"{prefix}start_ampm") or "").strip(),
            "end_time": (form.get(f"{prefix}end_time") or "").strip(),
            "end_ampm": (form.get(f"{prefix}end_ampm") or "").strip(),
            "break_hours": _safe_float(form.get(f"{prefix}break_hours")),
            "overtime_hours": _safe_float(form.get(f"{prefix}overtime_hours")),
            "project_name": (form.get(f"{prefix}project_name") or "").strip(),
            "salary_advance": _safe_float(form.get(f"{prefix}salary_advance")),
            "supervisor_sign": (form.get(f"{prefix}supervisor_sign") or "").strip(),
            "remarks": (form.get(f"{prefix}remarks") or "").strip(),
        })
    return days


def _compute_summary(days: list[dict[str, Any]]) -> dict[str, float]:
    working = 0.0
    ot_total = 0.0
    advance_total = 0.0
    for day in days:
        has_work = bool(
            day.get("start_time") or day.get("end_time") or day.get("project_name")
        )
        if has_work:
            working += 1
        ot_total += _safe_float(day.get("overtime_hours"))
        advance_total += _safe_float(day.get("salary_advance"))
    return {
        "working_days": working,
        "overtime_hours": _round2(ot_total),
        "total_days": working,
        "total_salary_paid": _round2(advance_total),
    }


def save_monthly_timesheet(
    db, form, username: str, timesheet_id: int | None = None
) -> int:
    employee_source = (form.get("employee_source") or "staff").strip()
    try:
        employee_id = int(form.get("employee_id") or 0)
    except ValueError:
        employee_id = 0
    year_month_raw = (form.get("year_month") or "").strip()
    year, month = _parse_year_month(year_month_raw)
    year_month = f"{year:04d}-{month:02d}"

    if not employee_id and not timesheet_id:
        raise ValueError("Select an employee.")

    if timesheet_id:
        existing = db.execute(
            "SELECT * FROM employee_monthly_timesheets WHERE id=?",
            (timesheet_id,),
        ).fetchone()
        if not existing:
            raise ValueError("Timesheet not found.")
        if existing["timesheet_status"] == "Approved":
            raise ValueError("Approved timesheets cannot be edited.")
        year, month = _parse_year_month(existing["year_month"])
        snap = dict(existing)
    else:
        snap = _employee_snapshot(db, employee_source, employee_id)
        dup = db.execute(
            """
            SELECT id FROM employee_monthly_timesheets
            WHERE year_month=? AND (
                (employee_source='staff' AND staff_id=?) OR
                (employee_source='worker' AND worker_id=?)
            )
            """,
            (year_month, snap.get("staff_id"), snap.get("worker_id")),
        ).fetchone()
        if dup:
            raise ValueError("A timesheet for this employee and month already exists.")

    days = _parse_days_from_form(form, year, month)
    summary = _compute_summary(days)
    summary["leave_days"] = _safe_float(form.get("leave_days"))
    summary["holiday_days"] = _safe_float(form.get("holiday_days"))
    summary["total_days"] = _safe_float(form.get("total_days")) or summary["total_days"]
    summary["total_salary_paid"] = _safe_float(form.get("total_salary_paid")) or summary["total_salary_paid"]
    summary["working_days"] = _safe_float(form.get("working_days")) or summary["working_days"]
    summary["overtime_hours"] = _safe_float(form.get("overtime_hours")) or summary["overtime_hours"]

    now = _now_ts()
    header = {
        "project_id": int(form["project_id"]) if form.get("project_id") else snap.get("project_id"),
        "sub_display_name": (form.get("sub_display_name") or snap.get("sub_display_name") or "").strip(),
        "sub_display_code": (form.get("sub_display_code") or snap.get("sub_display_code") or "").strip(),
        "employee_name": (form.get("employee_name") or snap.get("employee_name") or "").strip(),
        "employee_code": (form.get("employee_code") or snap.get("employee_code") or "").strip(),
        "designation": (form.get("designation") or snap.get("designation") or "").strip(),
        "supervisor_signature": (form.get("supervisor_signature") or "").strip(),
        "remarks": (form.get("remarks") or "").strip(),
        **summary,
    }

    if timesheet_id:
        db.execute(
            """
            UPDATE employee_monthly_timesheets SET
                project_id=?, sub_display_name=?, sub_display_code=?,
                employee_name=?, employee_code=?, designation=?,
                working_days=?, leave_days=?, holiday_days=?, overtime_hours=?,
                total_days=?, total_salary_paid=?, supervisor_signature=?, remarks=?,
                modified_at=?
            WHERE id=?
            """,
            (
                header["project_id"], header["sub_display_name"], header["sub_display_code"],
                header["employee_name"], header["employee_code"], header["designation"],
                header["working_days"], header["leave_days"], header["holiday_days"],
                header["overtime_hours"], header["total_days"], header["total_salary_paid"],
                header["supervisor_signature"], header["remarks"], now, timesheet_id,
            ),
        )
    else:
        ref = _next_timesheet_ref(db, year, month)
        db.execute(
            """
            INSERT INTO employee_monthly_timesheets(
                timesheet_ref, employee_source, staff_id, worker_id, subcontractor_id,
                project_id, year_month, sub_display_name, sub_display_code,
                employee_name, employee_code, designation,
                working_days, leave_days, holiday_days, overtime_hours, total_days,
                total_salary_paid, supervisor_signature, remarks,
                timesheet_status, approval_status, created_by, created_at, modified_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                ref, snap["employee_source"], snap.get("staff_id"), snap.get("worker_id"),
                snap.get("subcontractor_id"), header["project_id"], year_month,
                header["sub_display_name"], header["sub_display_code"],
                header["employee_name"], header["employee_code"], header["designation"],
                header["working_days"], header["leave_days"], header["holiday_days"],
                header["overtime_hours"], header["total_days"], header["total_salary_paid"],
                header["supervisor_signature"], header["remarks"],
                "Draft", "Pending Checker", username, now, now,
            ),
        )
        timesheet_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])

    _ensure_day_rows(db, timesheet_id, year, month)
    for day in days:
        db.execute(
            """
            UPDATE employee_timesheet_days SET
                start_time=?, start_ampm=?, end_time=?, end_ampm=?,
                break_hours=?, overtime_hours=?, project_name=?,
                salary_advance=?, supervisor_sign=?, remarks=?
            WHERE timesheet_id=? AND day_num=?
            """,
            (
                day["start_time"], day["start_ampm"], day["end_time"], day["end_ampm"],
                day["break_hours"], day["overtime_hours"], day["project_name"],
                day["salary_advance"], day["supervisor_sign"], day["remarks"],
                timesheet_id, day["day_num"],
            ),
        )
    return timesheet_id


def submit_timesheet(db, timesheet_id: int, username: str) -> None:
    row = db.execute(
        "SELECT timesheet_status FROM employee_monthly_timesheets WHERE id=?",
        (timesheet_id,),
    ).fetchone()
    if not row:
        raise ValueError("Timesheet not found.")
    if row["timesheet_status"] not in ("Draft", "Rejected"):
        raise ValueError("Only draft or rejected timesheets can be submitted.")
    db.execute(
        """
        UPDATE employee_monthly_timesheets SET
            timesheet_status='Submitted', approval_status='Pending Checker',
            submitted_at=?, modified_at=?
        WHERE id=?
        """,
        (_now_ts(), _now_ts(), timesheet_id),
    )


def approve_timesheet(db, timesheet_id: int) -> None:
    db.execute(
        """
        UPDATE employee_monthly_timesheets SET
            timesheet_status='Approved', approval_status='Approved',
            approved_at=?, modified_at=?
        WHERE id=?
        """,
        (_now_ts(), _now_ts(), timesheet_id),
    )


def get_monthly_timesheet(db, timesheet_id: int) -> dict[str, Any] | None:
    row = db.execute(
        """
        SELECT t.*, p.project_name, p.project_code
        FROM employee_monthly_timesheets t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.id=?
        """,
        (timesheet_id,),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    year, month = _parse_year_month(data["year_month"])
    data["year"], data["month"] = year, month
    data["month_label"] = year_month_label(year, month)
    data["days_in_month"] = days_in_month(year, month)
    days = db.execute(
        "SELECT * FROM employee_timesheet_days WHERE timesheet_id=? ORDER BY day_num",
        (timesheet_id,),
    ).fetchall()
    data["days"] = [dict(d) for d in days]
    return data


def list_monthly_timesheets(
    db, search: str = "", year_month: str = "", status: str = ""
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if search:
        clauses.append(
            "(t.employee_name LIKE ? OR t.employee_code LIKE ? OR t.timesheet_ref LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like])
    if year_month:
        clauses.append("t.year_month=?")
        params.append(year_month)
    if status:
        clauses.append("t.timesheet_status=?")
        params.append(status)
    sql = f"""
        SELECT t.*, p.project_name
        FROM employee_monthly_timesheets t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE {' AND '.join(clauses)}
        ORDER BY t.year_month DESC, t.employee_name
    """
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def list_staff_for_timesheet(db) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT id, employee_code, staff_name, designation FROM staff "
        "WHERE status IS NULL OR status='Active' ORDER BY staff_name"
    ).fetchall()
    return [dict(r) for r in rows]


def list_workers_for_timesheet(db, subcontractor_id: int | None = None) -> list[dict[str, Any]]:
    clauses = ["(w.status IS NULL OR w.status='Active')"]
    params: list[Any] = []
    if subcontractor_id:
        clauses.append("w.subcontractor_id=?")
        params.append(subcontractor_id)
    sql = f"""
        SELECT w.id, w.worker_code, w.worker_name, w.designation,
               s.subcontractor_name, s.subcontractor_code
        FROM workers w
        LEFT JOIN subcontractors s ON w.subcontractor_id = s.id
        WHERE {' AND '.join(clauses)}
        ORDER BY w.worker_name
    """
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def list_projects_for_timesheet(db) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT id, project_code, project_name FROM projects "
        "WHERE status IS NULL OR status != 'Inactive' ORDER BY project_name"
    ).fetchall()
    return [dict(r) for r in rows]


def delete_timesheet(db, timesheet_id: int) -> None:
    db.execute("DELETE FROM employee_timesheet_days WHERE timesheet_id=?", (timesheet_id,))
    db.execute("DELETE FROM employee_monthly_timesheets WHERE id=?", (timesheet_id,))
