"""Multi-project attendance: same employee, same date, different projects."""

from datetime import datetime

import pytest
import sqlite3

from modules.database import DATE_FMT, get_conn, init_db
from modules.payroll_engine import build_month_attendance_summary


def _insert_attendance_row(conn, employee_id, project_name, date_str, hours, ot=0.0):
    conn.execute(
        """
        INSERT INTO attendance(
            employee_id, employee_name, employee_type, project_name, attendance_date,
            in_time, out_time, total_hours, ot_hours, status, worked_hours, overtime
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            employee_id,
            "Test Worker",
            "Company Worker",
            project_name,
            date_str,
            "08:00",
            "16:00",
            hours,
            ot,
            "Present",
            hours,
            ot,
        ),
    )


def test_unique_index_two_projects_same_day(tmp_db):
    conn = get_conn()
    day = "02/06/2026"
    _insert_attendance_row(conn, "EMP-MULTI-1", "Project A", day, 4.0)
    _insert_attendance_row(conn, "EMP-MULTI-1", "Project B", day, 4.0)
    conn.commit()
    rows = conn.execute(
        "SELECT project_name FROM attendance WHERE employee_id=? AND attendance_date=?",
        ("EMP-MULTI-1", day),
    ).fetchall()
    conn.close()
    assert len(rows) == 2


def test_unique_index_blocks_duplicate_project(tmp_db):
    conn = get_conn()
    day = "03/06/2026"
    _insert_attendance_row(conn, "EMP-MULTI-2", "Project A", day, 8.0)
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        _insert_attendance_row(conn, "EMP-MULTI-2", "Project A", day, 6.0)
        conn.commit()
    conn.close()


def test_payroll_summary_sums_hours_per_day(tmp_db):
    emp_id = "EMP-MULTI-3"
    day = "04/06/2026"
    conn = get_conn()
    _insert_attendance_row(conn, emp_id, "Project A", day, 4.0)
    _insert_attendance_row(conn, emp_id, "Project B", day, 4.0)
    conn.execute(
        """
        INSERT INTO employees(
            employee_id, employee_type, employee_name, salary_type, salary_amount,
            daily_wage, ot_eligible, ot_rate, status, weekly_off_day, paid_holiday_eligibility
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            emp_id,
            "Company Worker",
            "Test Worker",
            "Daily",
            0,
            800,
            "Yes",
            100,
            "Active",
            "Sunday",
            "Yes",
        ),
    )
    conn.commit()
    conn.close()

    summary = build_month_attendance_summary(emp_id, "06/2026")
    assert summary is not None
    assert summary["worked_days"] == 1
    assert summary["total_worked_hours"] == pytest.approx(8.0, abs=0.5)


def test_migration_creates_unique_index(tmp_db):
    conn = get_conn()
    indexes = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='attendance'"
    ).fetchall()
    conn.close()
    names = {r[0] for r in indexes}
    assert "idx_attendance_emp_date_project" in names
