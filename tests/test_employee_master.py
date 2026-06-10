"""Employee Master — emp code generation and duplicate checks."""

from __future__ import annotations

import sqlite3

import pytest

from modules.database import (
    employee_category_from_type,
    employee_id_exists,
    employee_type_from_category,
    find_duplicate_employee_ids,
    generate_id,
    init_db,
    next_worker_id,
    preview_employee_code,
)


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "emp_master_test.db"
    monkeypatch.setattr("modules.database.DB_PATH", str(db_path))
    monkeypatch.setattr("modules.database.BASE_DIR", str(tmp_path))
    init_db()
    yield db_path


def test_preview_employee_code_company_staff(temp_db):
    code = preview_employee_code("Company Staff")
    assert code.startswith("EMP")
    assert code.endswith("101") or int(code.replace("EMP", "")) >= 101


def test_preview_employee_code_subcontractor(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO subcontractors(subcontractor_name, subcontractor_id) VALUES(?, ?)",
        ("Test Subcontractor", "TE100"),
    )
    conn.commit()
    conn.close()
    code = preview_employee_code("Subcontractor", "Test Subcontractor")
    assert code.upper().startswith("TE")
    assert code.endswith("101") or int("".join(c for c in code if c.isdigit()) or "101") >= 101


def test_naseer_subcontractor_worker_id(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO subcontractors(subcontractor_name, subcontractor_id) VALUES(?, ?)",
        ("Naseer", "NA100"),
    )
    conn.commit()
    conn.close()
    code = next_worker_id("Naseer")
    assert code.startswith("NA")
    assert int("".join(c for c in code if c.isdigit()) or "0") >= 101


def test_subcontractor_prefix_disambiguation(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO subcontractors(subcontractor_name, subcontractor_id) VALUES(?, ?)",
        ("Maksood Ali", "MA100"),
    )
    conn.execute(
        "INSERT INTO subcontractors(subcontractor_name, subcontractor_id) VALUES(?, ?)",
        ("Majid Khan", "MK100"),
    )
    conn.commit()
    conn.close()
    code1 = next_worker_id("Maksood Ali")
    code2 = next_worker_id("Majid Khan")
    assert code1.startswith("MA")
    assert code2.startswith("MK") or code2.startswith("MAJ") or code2 != code1


def test_category_type_mapping():
    assert employee_type_from_category("Company Staff") == "Company Staff"
    assert employee_type_from_category("Daily Worker") == "Daily Wage Staff"
    assert employee_type_from_category("Subcontractor") == "Sub Contractor Worker"
    assert employee_category_from_type("Daily Wage Staff") == "Daily Worker"


def test_duplicate_employee_detection(temp_db):
    conn = sqlite3.connect(str(temp_db))
    for _ in range(2):
        conn.execute(
            """
            INSERT INTO employees(employee_id, employee_name, employee_type, status)
            VALUES(?,?,?,?)
            """,
            ("EMP999", "Dup Test", "Company Staff", "Active"),
        )
    conn.commit()
    conn.close()
    dupes = find_duplicate_employee_ids()
    assert any(d["employee_id"] == "EMP999" for d in dupes)
    assert employee_id_exists("EMP999")


def test_generate_id_increments(temp_db):
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO employees(employee_id, employee_name, status) VALUES(?,?,?)",
        ("EMP105", "A", "Active"),
    )
    conn.commit()
    conn.close()
    nxt = generate_id("EMP", "employees")
    assert nxt == "EMP106"
