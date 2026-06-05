"""Material planning — planned qty, variance sign, excess detection."""

from __future__ import annotations

import os
import tempfile

import pytest

from modules import database as db
from modules.database import get_conn, generate_id
from modules.material_planning_db import (
    ensure_material_planning_schema,
    load_planned_vs_actual,
    planned_qty_for_progress,
    save_boq_material_map_row,
)
from modules.phase3_integration_db import ensure_phase3_schema


@pytest.fixture
def mp_db(monkeypatch):
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
            boq_item_id TEXT, project_id TEXT, project_name TEXT,
            boq_number TEXT, description TEXT, quantity REAL, unit TEXT,
            approved_rate REAL, executed_quantity REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS dpr_reports(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dpr_id TEXT, dpr_date TEXT, project_name TEXT, project_id TEXT,
            boq_item_id TEXT, progress_quantity REAL, status TEXT
        );
        CREATE TABLE IF NOT EXISTS dpr_boq_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_id TEXT, dpr_id TEXT, boq_item_id TEXT, progress_quantity REAL
        );
        CREATE TABLE IF NOT EXISTS material_issues(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id TEXT UNIQUE, issue_no TEXT, project_name TEXT,
            material_code TEXT, material_name TEXT, quantity REAL,
            issue_date TEXT, status TEXT
        );
        """
    )
    ensure_phase3_schema(conn)
    ensure_material_planning_schema(conn)
    conn.commit()
    conn.close()
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


def _seed(conn, executed: float = 10.0):
    conn.execute(
        "INSERT INTO projects(project_id, project_name) VALUES('P1', 'Test Tower')"
    )
    boq_id = generate_id("BOQ", "project_boq_items", id_column="boq_item_id", conn=conn)
    conn.execute(
        """
        INSERT INTO project_boq_items(
            boq_item_id, project_id, project_name, boq_number, description,
            quantity, unit, executed_quantity
        ) VALUES(?, 'P1', 'Test Tower', '1.1', 'Concrete M30', 100, 'M3', ?)
        """,
        (boq_id, executed),
    )
    conn.execute(
        """
        INSERT INTO dpr_reports(
            dpr_id, dpr_date, project_name, boq_item_id, progress_quantity, status
        ) VALUES('DPR-1', '01/06/2026', 'Test Tower', ?, ?, 'Engineer Approved')
        """,
        (boq_id, executed),
    )
    return boq_id


def test_planned_qty_calculation():
    assert planned_qty_for_progress(10.0, 320.0) == pytest.approx(3200.0)
    assert planned_qty_for_progress(0, 5) == 0.0


def test_variance_sign_and_excess(mp_db):
    conn = get_conn()
    boq_id = _seed(conn, executed=10.0)
    conn.commit()
    conn.close()

    save_boq_material_map_row(boq_id, "Cement", 320.0, material_code="CEM", unit="Kg")
    save_boq_material_map_row(boq_id, "Sand", 0.45, material_code="SND", unit="M3")

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO material_issues(
            issue_id, project_name, material_code, material_name, quantity, issue_date
        ) VALUES('MI-1', 'Test Tower', 'CEM', 'Cement', 3500, '15/06/2026')
        """
    )
    conn.execute(
        """
        INSERT INTO material_issues(
            issue_id, project_name, material_code, material_name, quantity, issue_date
        ) VALUES('MI-2', 'Test Tower', 'SND', 'Sand', 3.0, '15/06/2026')
        """
    )
    conn.commit()
    conn.close()

    df = load_planned_vs_actual("Test Tower")
    cement = df[df["material_code"] == "CEM"].iloc[0]
    sand = df[df["material_code"] == "SND"].iloc[0]

    assert float(cement["planned_qty"]) == pytest.approx(3200.0)
    assert float(cement["actual_qty"]) == pytest.approx(3500.0)
    assert float(cement["variance_qty"]) == pytest.approx(300.0)
    assert bool(cement["is_excess"]) is True
    assert cement["variance_status"] == "Excess (Surplus)"

    assert float(sand["planned_qty"]) == pytest.approx(4.5)
    assert float(sand["actual_qty"]) == pytest.approx(3.0)
    assert float(sand["variance_qty"]) == pytest.approx(-1.5)
    assert bool(sand["is_excess"]) is False
    assert sand["variance_status"] == "Shortage"
