"""Quality Control — Phase A: QC Master (test definitions)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

MODULE_ID = "qc_master"
RECORD_TABLE = "qc_tests"

QC_TEST_STATUSES = ("Active", "Inactive")

APPLICABLE_MATERIALS = (
    "Concrete",
    "Asphalt",
    "Aggregate",
    "Crusher / M-Sand",
    "Steel",
    "Road Work",
    "Soil",
    "Water",
    "General",
    "Other",
)

TEST_FREQUENCIES = (
    "Per Batch",
    "Daily",
    "Weekly",
    "Per 100 cum",
    "Per Lot",
    "Per Delivery",
    "As Required",
    "Other",
)


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


def ensure_qc_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS qc_tests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_code TEXT UNIQUE NOT NULL,
            test_name TEXT NOT NULL,
            applicable_material TEXT,
            frequency TEXT,
            acceptance_criteria TEXT,
            is_irc_code TEXT,
            status TEXT DEFAULT 'Active',
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT
        )
        """
    )
    for col, ctype in (
        ("test_code", "TEXT"),
        ("test_name", "TEXT"),
        ("applicable_material", "TEXT"),
        ("frequency", "TEXT"),
        ("acceptance_criteria", "TEXT"),
        ("is_irc_code", "TEXT"),
        ("status", "TEXT DEFAULT 'Active'"),
        ("remarks", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "qc_tests", col, ctype)


def list_qc_tests(
    db,
    search: str = "",
    material_filter: str = "",
    status_filter: str = "",
) -> list[dict[str, Any]]:
    if not _table_exists(db, RECORD_TABLE):
        return []
    clauses = ["1=1"]
    params: list[Any] = []
    if search:
        clauses.append(
            "(test_code LIKE ? OR test_name LIKE ? OR is_irc_code LIKE ? "
            "OR acceptance_criteria LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])
    if material_filter:
        clauses.append("applicable_material=?")
        params.append(material_filter)
    if status_filter:
        clauses.append("status=?")
        params.append(status_filter)
    sql = f"""
        SELECT * FROM qc_tests
        WHERE {' AND '.join(clauses)}
        ORDER BY test_code
    """
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def get_qc_test(db, test_id: int) -> dict[str, Any] | None:
    if not _table_exists(db, RECORD_TABLE):
        return None
    row = db.execute("SELECT * FROM qc_tests WHERE id=?", (test_id,)).fetchone()
    return dict(row) if row else None


def save_qc_test(db, form, username: str, test_id: int | None = None) -> int:
    test_code = (form.get("test_code") or "").strip().upper()
    test_name = (form.get("test_name") or "").strip()
    if not test_code:
        raise ValueError("Test code is required.")
    if not test_name:
        raise ValueError("Test name is required.")

    applicable_material = (form.get("applicable_material") or "").strip()
    frequency = (form.get("frequency") or "").strip()
    acceptance_criteria = (form.get("acceptance_criteria") or "").strip()
    is_irc_code = (form.get("is_irc_code") or "").strip()
    status = (form.get("status") or "Active").strip()
    remarks = (form.get("remarks") or "").strip()

    if status not in QC_TEST_STATUSES:
        status = "Active"

    dup = db.execute(
        "SELECT id FROM qc_tests WHERE test_code=? AND id!=?",
        (test_code, test_id or 0),
    ).fetchone()
    if dup:
        raise ValueError(f"Test code '{test_code}' already exists.")

    now = _now_ts()
    fields = (
        test_code,
        test_name,
        applicable_material,
        frequency,
        acceptance_criteria,
        is_irc_code,
        status,
        remarks,
    )

    if test_id:
        existing = get_qc_test(db, test_id)
        if not existing:
            raise ValueError("QC test not found.")
        db.execute(
            """
            UPDATE qc_tests SET
                test_code=?, test_name=?, applicable_material=?, frequency=?,
                acceptance_criteria=?, is_irc_code=?, status=?, remarks=?,
                modified_at=?
            WHERE id=?
            """,
            (*fields, now, test_id),
        )
        return test_id

    db.execute(
        """
        INSERT INTO qc_tests(
            test_code, test_name, applicable_material, frequency,
            acceptance_criteria, is_irc_code, status, remarks,
            created_by, created_at, modified_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (*fields, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_qc_test(db, test_id: int) -> None:
    if not get_qc_test(db, test_id):
        raise ValueError("QC test not found.")
    db.execute("DELETE FROM qc_tests WHERE id=?", (test_id,))
