"""Phase 3 integration — BOQ sync, billing guard, alerts."""

from __future__ import annotations

import os
import tempfile

import pytest

from modules import database as db
from modules.database import get_conn, generate_id
from modules.phase3_integration_db import (
    check_integration_alerts,
    ensure_phase3_schema,
    get_boq_integration_stats,
    save_boq_material_map_row,
    sync_boq_item_quantities,
    validate_client_bill_lines,
    estimate_material_consumption,
    EXECUTED_DPR_STATUSES,
)


@pytest.fixture
def phase3_db(monkeypatch):
    """Minimal DB for phase 3 tests (avoids full init_db side effects)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(db, "DB_PATH", path)
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT, project_name TEXT, client_name TEXT,
            status TEXT, amount REAL, budget REAL, progress_percent REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS project_boq_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boq_item_id TEXT, project_id TEXT, project_name TEXT, client_name TEXT,
            boq_number TEXT, description TEXT, quantity REAL, unit TEXT,
            approved_rate REAL, amount REAL, status TEXT
        );
        CREATE TABLE IF NOT EXISTS dpr_reports(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dpr_id TEXT, dpr_date TEXT, project_name TEXT, project_id TEXT,
            boq_item_id TEXT, boq_number TEXT, boq_description TEXT, unit TEXT,
            billing_measurement TEXT, progress_quantity REAL, status TEXT,
            client_billed_quantity REAL DEFAULT 0, billed_quantity REAL DEFAULT 0,
            created_by TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS dpr_boq_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id TEXT, dpr_id TEXT, boq_item_id TEXT, progress_quantity REAL,
            billing_measurement TEXT, billable_quantity REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS dpr_measurements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dpr_id TEXT, boq_line_id TEXT, boq_item_id TEXT,
            calculated_quantity REAL, include_in_client_bill INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS client_bills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id TEXT, bill_no TEXT, bill_date TEXT, project_name TEXT,
            total_amount REAL, status TEXT
        );
        CREATE TABLE IF NOT EXISTS client_bill_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id TEXT, bill_id TEXT, dpr_id TEXT, boq_item_id TEXT,
            quantity REAL, rate REAL, amount REAL
        );
        """
    )
    ensure_phase3_schema(conn)
    conn.commit()
    conn.close()
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


def _seed_project_boq(conn, project_name="P3 Test Project", qty=100.0, rate=500.0):
    pid = generate_id("PRJ", "projects", id_column="project_id", conn=conn)
    conn.execute(
        """
        INSERT INTO projects(project_id, project_name, client_name, status, amount, budget)
        VALUES(?,?,?,?,?,?)
        """,
        (pid, project_name, "Test Client", "Active", qty * rate, qty * rate),
    )
    boq_id = generate_id("PB", "project_boq_items", id_column="boq_item_id", conn=conn)
    conn.execute(
        """
        INSERT INTO project_boq_items(
            boq_item_id, project_id, project_name, client_name, boq_number,
            description, quantity, unit, approved_rate, amount, status
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            boq_id,
            pid,
            project_name,
            "Test Client",
            "BOQ-001",
            "Concrete M30",
            qty,
            "cum",
            rate,
            qty * rate,
            "Approved",
        ),
    )
    conn.commit()
    return pid, boq_id, project_name


def _insert_dpr(conn, dpr_id, project_name, boq_item_id, progress, status):
    conn.execute(
        """
        INSERT INTO dpr_reports(
            dpr_id, dpr_date, project_name, boq_item_id, boq_number, boq_description,
            unit, billing_measurement, progress_quantity, status, created_by, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            dpr_id,
            "01/06/2026",
            project_name,
            boq_item_id,
            "BOQ-001",
            "Concrete",
            "cum",
            "Yes",
            progress,
            status,
            "tester",
            "01/06/2026",
        ),
    )


def test_sync_boq_executed_and_balance(phase3_db):
    conn = get_conn()
    ensure_phase3_schema(conn)
    _, boq_id, pname = _seed_project_boq(conn, qty=50.0)
    _insert_dpr(conn, "DPR-P3-1", pname, boq_id, 20.0, "Client Approved")
    _insert_dpr(conn, "DPR-P3-2", pname, boq_id, 10.0, "Engineer Approved")
    conn.commit()
    conn.close()

    sync_boq_item_quantities(boq_item_id=boq_id)
    stats = get_boq_integration_stats(boq_id)
    assert stats["executed_qty"] == pytest.approx(30.0)
    assert stats["balance_qty"] == pytest.approx(20.0)
    assert stats["revenue_earned"] == pytest.approx(30.0 * 500.0)


def test_duplicate_billing_guard(phase3_db):
    conn = get_conn()
    ensure_phase3_schema(conn)
    _, boq_id, pname = _seed_project_boq(conn)
    dpr_id = "DPR-BILL-1"
    _insert_dpr(conn, dpr_id, pname, boq_id, 25.0, "Client Approved")
    conn.execute(
        "UPDATE dpr_reports SET client_billed_quantity = 15 WHERE dpr_id = ?",
        (dpr_id,),
    )
    conn.commit()
    conn.close()

    ok, errs = validate_client_bill_lines(
        [{"dpr_id": dpr_id, "quantity": 15.0, "boq_item_id": boq_id}]
    )
    assert not ok
    assert any("exceeds pending" in e.lower() for e in errs)

    ok2, _ = validate_client_bill_lines(
        [{"dpr_id": dpr_id, "quantity": 10.0, "boq_item_id": boq_id}]
    )
    assert ok2


def test_boq_exceeded_alert(phase3_db):
    conn = get_conn()
    ensure_phase3_schema(conn)
    _, boq_id, pname = _seed_project_boq(conn, qty=10.0)
    _insert_dpr(conn, "DPR-OVER", pname, boq_id, 15.0, "Client Approved")
    conn.commit()
    conn.close()

    sync_boq_item_quantities(boq_item_id=boq_id)
    alerts = check_integration_alerts(boq_item_id=boq_id)
    codes = {a["code"] for a in alerts}
    assert "boq_exceeded" in codes


def test_material_consumption_estimate(phase3_db):
    conn = get_conn()
    ensure_phase3_schema(conn)
    _, boq_id, _ = _seed_project_boq(conn)
    conn.close()
    save_boq_material_map_row(boq_id, "Cement", 5.5, material_code="CEM-01", unit="bag")
    df = estimate_material_consumption(boq_id, 10.0)
    assert len(df) == 1
    assert float(df.iloc[0]["estimated_qty"]) == pytest.approx(55.0)


def test_executed_statuses_tuple():
    assert "Client Approved" in EXECUTED_DPR_STATUSES
    assert "Draft" not in EXECUTED_DPR_STATUSES
