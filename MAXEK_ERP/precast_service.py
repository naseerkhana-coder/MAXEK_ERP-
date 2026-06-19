"""Precast Yard module — yard master registry and dashboard helpers."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

PRECAST_YARD_STATUSES = ("Active", "Inactive", "Under Maintenance")

PRECAST_YARD_SUBTOOLBAR = (
    {
        "endpoint": "precast_yard",
        "label": "Dashboard",
        "icon": "fa-gauge-high",
        "active_endpoints": ["precast_yard"],
    },
    {
        "endpoint": "precast_yard_yards",
        "label": "Yard Master",
        "icon": "fa-warehouse",
        "active_endpoints": ["precast_yard_yards"],
    },
    {
        "endpoint": "plant_precast_production",
        "label": "Production",
        "icon": "fa-border-all",
        "active_endpoints": ["plant_precast_production"],
    },
    {
        "endpoint": "plant_precast_dispatch",
        "label": "Dispatch",
        "icon": "fa-dolly",
        "active_endpoints": ["plant_precast_dispatch"],
    },
    {
        "endpoint": "plant_qc",
        "label": "QC Records",
        "icon": "fa-vial",
        "active_endpoints": ["plant_qc"],
        "query": {"source": "Precast"},
    },
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


def _next_yard_code(db) -> str:
    rows = db.execute(
        "SELECT yard_code FROM precast_yards WHERE yard_code LIKE 'PY-%' ORDER BY yard_code DESC LIMIT 1"
    ).fetchall()
    seq = 1
    if rows and rows[0][0]:
        m = re.search(r"PY-(\d+)$", rows[0][0])
        if m:
            seq = int(m.group(1)) + 1
    return f"PY-{seq:03d}"


def ensure_precast_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS precast_yards(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            yard_code TEXT UNIQUE NOT NULL,
            yard_name TEXT NOT NULL,
            location TEXT,
            capacity TEXT,
            plant_id INTEGER,
            incharge TEXT,
            status TEXT DEFAULT 'Active',
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(plant_id) REFERENCES plants(id)
        )
        """
    )
    for col, ctype in (
        ("yard_code", "TEXT"),
        ("yard_name", "TEXT"),
        ("location", "TEXT"),
        ("capacity", "TEXT"),
        ("plant_id", "INTEGER"),
        ("incharge", "TEXT"),
        ("status", "TEXT DEFAULT 'Active'"),
        ("remarks", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "precast_yards", col, ctype)


def list_precast_yards(
    db,
    search: str = "",
    status_filter: str = "",
) -> list[dict[str, Any]]:
    if not _table_exists(db, "precast_yards"):
        return []
    clauses = ["1=1"]
    params: list[Any] = []
    if search:
        clauses.append(
            "(yard_code LIKE ? OR yard_name LIKE ? OR location LIKE ? OR incharge LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])
    if status_filter:
        clauses.append("status=?")
        params.append(status_filter)
    sql = f"""
        SELECT py.*, p.plant_name, p.plant_id AS linked_plant_code
        FROM precast_yards py
        LEFT JOIN plants p ON p.id = py.plant_id
        WHERE {' AND '.join(clauses)}
        ORDER BY py.yard_name COLLATE NOCASE
    """
    return [dict(row) for row in db.execute(sql, params).fetchall()]


def get_precast_yard(db, yard_id: int | None) -> dict[str, Any] | None:
    if not yard_id or not _table_exists(db, "precast_yards"):
        return None
    row = db.execute(
        """
        SELECT py.*, p.plant_name, p.plant_id AS linked_plant_code
        FROM precast_yards py
        LEFT JOIN plants p ON p.id = py.plant_id
        WHERE py.id=?
        """,
        (yard_id,),
    ).fetchone()
    return dict(row) if row else None


def save_precast_yard(
    db,
    form: dict,
    username: str,
    yard_id: int | None = None,
) -> int:
    yard_name = (form.get("yard_name") or "").strip()
    if not yard_name:
        raise ValueError("Yard name is required.")
    status = (form.get("status") or "Active").strip()
    if status not in PRECAST_YARD_STATUSES:
        raise ValueError("Invalid yard status.")
    plant_raw = (form.get("plant_id") or "").strip()
    plant_id = int(plant_raw) if plant_raw else None
    now = _now_ts()
    payload = (
        yard_name,
        (form.get("location") or "").strip(),
        (form.get("capacity") or "").strip(),
        plant_id,
        (form.get("incharge") or "").strip(),
        status,
        (form.get("remarks") or "").strip(),
        now,
    )
    if yard_id:
        db.execute(
            """
            UPDATE precast_yards SET
                yard_name=?, location=?, capacity=?, plant_id=?, incharge=?,
                status=?, remarks=?, modified_at=?
            WHERE id=?
            """,
            (*payload, yard_id),
        )
        return yard_id
    yard_code = (form.get("yard_code") or "").strip() or _next_yard_code(db)
    db.execute(
        """
        INSERT INTO precast_yards(
            yard_code, yard_name, location, capacity, plant_id, incharge,
            status, remarks, created_by, created_at, modified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (yard_code, *payload, username, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_precast_yard(db, yard_id: int) -> None:
    if not get_precast_yard(db, yard_id):
        raise ValueError("Precast yard not found.")
    db.execute("DELETE FROM precast_yards WHERE id=?", (yard_id,))


def precast_yard_dashboard_stats(db) -> dict[str, Any]:
    stats = {
        "total_yards": 0,
        "active_yards": 0,
        "today_production_qty": 0.0,
        "today_dispatch_qty": 0.0,
        "stock_units": 0.0,
        "casting_count": 0,
        "ready_count": 0,
    }
    if _table_exists(db, "precast_yards"):
        stats["total_yards"] = db.execute("SELECT COUNT(*) FROM precast_yards").fetchone()[0]
        stats["active_yards"] = db.execute(
            "SELECT COUNT(*) FROM precast_yards WHERE status='Active'"
        ).fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    if _table_exists(db, "precast_production"):
        row = db.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(qty), 0)
            FROM precast_production WHERE casting_date=?
            """,
            (today,),
        ).fetchone()
        if row:
            stats["casting_count"] = row[0] or 0
            stats["today_production_qty"] = float(row[1] or 0)
        ready = db.execute(
            "SELECT COUNT(*) FROM precast_production WHERE status='Ready'"
        ).fetchone()
        stats["ready_count"] = ready[0] if ready else 0
    if _table_exists(db, "precast_dispatch"):
        row = db.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(qty), 0)
            FROM precast_dispatch WHERE dispatch_date=?
            """,
            (today,),
        ).fetchone()
        if row:
            stats["today_dispatch_qty"] = float(row[1] or 0)
    if _table_exists(db, "plant_stock"):
        row = db.execute(
            """
            SELECT COALESCE(SUM(closing), 0) FROM plant_stock
            WHERE material_type LIKE 'PRECAST:%'
            """
        ).fetchone()
        stats["stock_units"] = float(row[0] or 0) if row else 0.0
    return stats
