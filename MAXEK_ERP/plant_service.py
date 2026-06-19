"""Plant Operations Management — Phase 3 (QC, costing, crusher/M-sand, maintenance, 360°).

Phase 4 backlog (not implemented):
- Mix design library, equipment utilization log
- Crusher/M-sand dispatch, advanced consolidated reports
- Full diesel ledger integration with fleet, multi-plant profitability
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from accounts_service import _safe_float

PLANT_TYPES = (
    "Asphalt",
    "Concrete/RMC",
    "Crusher",
    "Wet Mix",
    "M-Sand",
    "Precast Yard",
    "Manufacturing Unit",
)
PLANT_STATUSES = ("Active", "Inactive", "Under Maintenance")
SHIFTS = ("Day", "Night", "General")
ASPHALT_MIX_TYPES = ("DBM", "BC", "SDBC", "MSS", "WMM", "Other")
RMC_GRADES = ("M20", "M25", "M30", "M40", "Other")
RMC_CONSUMPTION_MATERIALS = ("cement", "sand", "aggregate", "admixture", "water")
WETMIX_CONSUMPTION_MATERIALS = ("aggregate", "cement", "water", "additive")
PRECAST_PRODUCT_TYPES = ("Drain", "Slab", "Kerb", "Cover Block", "Other")
PRECAST_STATUSES = ("Casting", "Curing", "Ready", "Dispatched")
CONSUMPTION_MATERIALS = ("aggregate", "bitumen", "filler", "diesel")
STOCK_UNIT_TON = "Ton"
STOCK_UNIT_LITER = "L"
STOCK_UNIT_M3 = "m³"
CRUSHER_OUTPUT_GRADES = ("20mm", "12mm", "6mm", "Dust", "GSB", "Other")
MSAND_GRADES = ("M-Sand", "P-Sand", "Plaster Sand", "Other")
CRUSHER_CONSUMPTION_MATERIALS = ("boulder", "power_kwh", "diesel")
QC_SOURCE_MODULES = (
    "Asphalt", "RMC", "Wet Mix", "Crusher", "M-Sand", "Precast", "General",
)
QC_TEST_TYPES = (
    "Marshall Stability", "Flow Value", "Gradation", "Slump", "Compressive Strength",
    "Fineness Modulus", "Moisture Content", "Bitumen Content", "Other",
)
QC_PASS_FAIL = ("Pass", "Fail", "Pending")
MAINTENANCE_JOB_TYPES = ("Preventive", "Breakdown", "Scheduled", "Inspection")
MAINTENANCE_STATUSES = ("Open", "In Progress", "Completed", "Cancelled")
DEFAULT_MATERIAL_RATES: dict[str, tuple[float, str]] = {
    "aggregate": (850.0, STOCK_UNIT_TON),
    "bitumen": (52000.0, STOCK_UNIT_TON),
    "filler": (1200.0, STOCK_UNIT_TON),
    "diesel": (95.0, STOCK_UNIT_LITER),
    "cement": (4200.0, STOCK_UNIT_TON),
    "sand": (900.0, STOCK_UNIT_TON),
    "admixture": (180.0, STOCK_UNIT_LITER),
    "water": (0.05, STOCK_UNIT_LITER),
    "boulder": (650.0, STOCK_UNIT_TON),
    "power_kwh": (8.5, "kWh"),
}


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(db, table: str, column: str) -> bool:
    if not _table_exists(db, table):
        return False
    cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


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


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _count_table(db, table: str, where: str = "", params: tuple = ()) -> int:
    if not _table_exists(db, table):
        return 0
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql += f" WHERE {where}"
    row = db.execute(sql, params).fetchone()
    return int(row[0]) if row else 0


def _next_plant_id(db) -> str:
    year = datetime.now().strftime("%Y")
    base = f"PLT-{year}-"
    if not _table_exists(db, "plants"):
        return f"{base}0001"
    row = db.execute(
        "SELECT plant_id FROM plants WHERE plant_id LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{base}%",),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"-(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"{base}{seq:04d}"


def _next_doc_number(db, prefix: str, table: str, column: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    base = f"{prefix}-{today}-"
    if not _table_exists(db, table):
        return f"{base}001"
    row = db.execute(
        f"SELECT {column} FROM {table} WHERE {column} LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{base}%",),
    ).fetchone()
    seq = 1
    if row and row[0]:
        m = re.search(r"-(\d+)$", str(row[0]))
        if m:
            seq = int(m.group(1)) + 1
    return f"{base}{seq:03d}"


def ensure_plant_schema(db) -> None:
    """Idempotent plant operations schema (Phase 2)."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS plants(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id TEXT UNIQUE NOT NULL,
            plant_name TEXT NOT NULL,
            plant_type TEXT,
            capacity TEXT,
            location TEXT,
            project_id INTEGER,
            incharge TEXT,
            status TEXT DEFAULT 'Active',
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("plant_id", "TEXT"), ("plant_name", "TEXT"), ("plant_type", "TEXT"),
        ("capacity", "TEXT"), ("location", "TEXT"), ("project_id", "INTEGER"),
        ("incharge", "TEXT"), ("status", "TEXT DEFAULT 'Active'"), ("remarks", "TEXT"),
        ("created_by", "TEXT"), ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "plants", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS asphalt_production(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            production_date TEXT,
            plant_id INTEGER NOT NULL,
            project_id INTEGER,
            mix_type TEXT,
            batch_number TEXT,
            qty_ton REAL DEFAULT 0,
            shift TEXT,
            operator TEXT,
            consumption_json TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(plant_id) REFERENCES plants(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("production_date", "TEXT"), ("plant_id", "INTEGER"), ("project_id", "INTEGER"),
        ("mix_type", "TEXT"), ("batch_number", "TEXT"), ("qty_ton", "REAL DEFAULT 0"),
        ("shift", "TEXT"), ("operator", "TEXT"), ("consumption_json", "TEXT"),
        ("remarks", "TEXT"), ("created_by", "TEXT"), ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "asphalt_production", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS asphalt_dispatch(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dispatch_number TEXT UNIQUE NOT NULL,
            dispatch_date TEXT,
            plant_id INTEGER NOT NULL,
            project_id INTEGER,
            vehicle_number TEXT,
            mix_type TEXT,
            qty_ton REAL DEFAULT 0,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(plant_id) REFERENCES plants(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("dispatch_number", "TEXT"), ("dispatch_date", "TEXT"), ("plant_id", "INTEGER"),
        ("project_id", "INTEGER"), ("vehicle_number", "TEXT"), ("mix_type", "TEXT"),
        ("qty_ton", "REAL DEFAULT 0"), ("remarks", "TEXT"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "asphalt_dispatch", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS plant_stock(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL,
            material_type TEXT NOT NULL,
            opening REAL DEFAULT 0,
            production REAL DEFAULT 0,
            dispatch REAL DEFAULT 0,
            closing REAL DEFAULT 0,
            unit TEXT DEFAULT 'Ton',
            updated_at TEXT,
            UNIQUE(plant_id, material_type),
            FOREIGN KEY(plant_id) REFERENCES plants(id)
        )
    """)
    for col, ctype in (
        ("plant_id", "INTEGER"), ("material_type", "TEXT"),
        ("opening", "REAL DEFAULT 0"), ("production", "REAL DEFAULT 0"),
        ("dispatch", "REAL DEFAULT 0"), ("closing", "REAL DEFAULT 0"),
        ("unit", "TEXT DEFAULT 'Ton'"), ("updated_at", "TEXT"),
    ):
        _ensure_column(db, "plant_stock", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS rmc_production(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            production_date TEXT,
            plant_id INTEGER NOT NULL,
            project_id INTEGER,
            grade TEXT,
            qty_m3 REAL DEFAULT 0,
            shift TEXT,
            operator TEXT,
            consumption_json TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(plant_id) REFERENCES plants(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("production_date", "TEXT"), ("plant_id", "INTEGER"), ("project_id", "INTEGER"),
        ("grade", "TEXT"), ("qty_m3", "REAL DEFAULT 0"), ("shift", "TEXT"),
        ("operator", "TEXT"), ("consumption_json", "TEXT"), ("remarks", "TEXT"),
        ("created_by", "TEXT"), ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "rmc_production", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS rmc_dispatch(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dispatch_number TEXT UNIQUE NOT NULL,
            dispatch_date TEXT,
            plant_id INTEGER NOT NULL,
            project_id INTEGER,
            vehicle_number TEXT,
            qty_m3 REAL DEFAULT 0,
            loading_time TEXT,
            dispatch_time TEXT,
            delivery_time TEXT,
            remarks TEXT,
            grade TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(plant_id) REFERENCES plants(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("dispatch_number", "TEXT"), ("dispatch_date", "TEXT"), ("plant_id", "INTEGER"),
        ("project_id", "INTEGER"), ("vehicle_number", "TEXT"), ("qty_m3", "REAL DEFAULT 0"),
        ("loading_time", "TEXT"), ("dispatch_time", "TEXT"), ("delivery_time", "TEXT"),
        ("remarks", "TEXT"), ("grade", "TEXT"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "rmc_dispatch", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS wetmix_production(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            production_date TEXT,
            plant_id INTEGER NOT NULL,
            material_mix TEXT,
            qty REAL DEFAULT 0,
            operator TEXT,
            consumption_json TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(plant_id) REFERENCES plants(id)
        )
    """)
    for col, ctype in (
        ("production_date", "TEXT"), ("plant_id", "INTEGER"), ("material_mix", "TEXT"),
        ("qty", "REAL DEFAULT 0"), ("operator", "TEXT"), ("consumption_json", "TEXT"),
        ("remarks", "TEXT"), ("created_by", "TEXT"), ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "wetmix_production", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS precast_production(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL,
            product_type TEXT,
            qty REAL DEFAULT 0,
            casting_date TEXT,
            curing_date TEXT,
            status TEXT DEFAULT 'Casting',
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(plant_id) REFERENCES plants(id)
        )
    """)
    for col, ctype in (
        ("plant_id", "INTEGER"), ("product_type", "TEXT"), ("qty", "REAL DEFAULT 0"),
        ("casting_date", "TEXT"), ("curing_date", "TEXT"), ("status", "TEXT DEFAULT 'Casting'"),
        ("remarks", "TEXT"), ("created_by", "TEXT"), ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "precast_production", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS precast_dispatch(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dispatch_number TEXT UNIQUE NOT NULL,
            dispatch_date TEXT,
            plant_id INTEGER NOT NULL,
            project_id INTEGER,
            product_type TEXT,
            qty REAL DEFAULT 0,
            vehicle_number TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(plant_id) REFERENCES plants(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("dispatch_number", "TEXT"), ("dispatch_date", "TEXT"), ("plant_id", "INTEGER"),
        ("project_id", "INTEGER"), ("product_type", "TEXT"), ("qty", "REAL DEFAULT 0"),
        ("vehicle_number", "TEXT"), ("remarks", "TEXT"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "precast_dispatch", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS plant_qc_records(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qc_date TEXT,
            plant_id INTEGER NOT NULL,
            sample_id TEXT,
            source_module TEXT,
            test_type TEXT,
            result_value REAL,
            result_unit TEXT,
            pass_fail TEXT DEFAULT 'Pending',
            tested_by TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(plant_id) REFERENCES plants(id)
        )
    """)
    for col, ctype in (
        ("qc_date", "TEXT"), ("plant_id", "INTEGER"), ("sample_id", "TEXT"),
        ("source_module", "TEXT"), ("test_type", "TEXT"), ("result_value", "REAL"),
        ("result_unit", "TEXT"), ("pass_fail", "TEXT DEFAULT 'Pending'"),
        ("tested_by", "TEXT"), ("remarks", "TEXT"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "plant_qc_records", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS plant_material_rates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER,
            material_key TEXT NOT NULL,
            rate_per_unit REAL DEFAULT 0,
            unit TEXT,
            effective_from TEXT,
            created_at TEXT,
            UNIQUE(plant_id, material_key)
        )
    """)
    for col, ctype in (
        ("plant_id", "INTEGER"), ("material_key", "TEXT"),
        ("rate_per_unit", "REAL DEFAULT 0"), ("unit", "TEXT"),
        ("effective_from", "TEXT"), ("created_at", "TEXT"),
    ):
        _ensure_column(db, "plant_material_rates", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS plant_maintenance_jobs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_number TEXT UNIQUE NOT NULL,
            plant_id INTEGER NOT NULL,
            equipment_name TEXT,
            job_date TEXT,
            job_type TEXT,
            status TEXT DEFAULT 'Open',
            description TEXT,
            downtime_hours REAL DEFAULT 0,
            cost REAL DEFAULT 0,
            assigned_to TEXT,
            completed_date TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(plant_id) REFERENCES plants(id)
        )
    """)
    for col, ctype in (
        ("job_number", "TEXT"), ("plant_id", "INTEGER"), ("equipment_name", "TEXT"),
        ("job_date", "TEXT"), ("job_type", "TEXT"), ("status", "TEXT DEFAULT 'Open'"),
        ("description", "TEXT"), ("downtime_hours", "REAL DEFAULT 0"),
        ("cost", "REAL DEFAULT 0"), ("assigned_to", "TEXT"), ("completed_date", "TEXT"),
        ("remarks", "TEXT"), ("created_by", "TEXT"), ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "plant_maintenance_jobs", col, ctype)

    db.execute("""
        CREATE TABLE IF NOT EXISTS crusher_production(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            production_date TEXT,
            plant_id INTEGER NOT NULL,
            output_grade TEXT,
            qty_ton REAL DEFAULT 0,
            shift TEXT,
            operator TEXT,
            consumption_json TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(plant_id) REFERENCES plants(id)
        )
    """)
    for col, ctype in (
        ("production_date", "TEXT"), ("plant_id", "INTEGER"), ("output_grade", "TEXT"),
        ("qty_ton", "REAL DEFAULT 0"), ("shift", "TEXT"), ("operator", "TEXT"),
        ("consumption_json", "TEXT"), ("remarks", "TEXT"), ("created_by", "TEXT"),
        ("created_at", "TEXT"), ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "crusher_production", col, ctype)

    _seed_default_material_rates(db)
    db.commit()


def _empty_plant_dashboard_stats() -> dict[str, Any]:
    return {
        "total_plants": 0,
        "active_plants": 0,
        "today_production_count": 0,
        "today_dispatch_count": 0,
        "today_production_ton": 0.0,
        "today_dispatch_ton": 0.0,
        "today_rmc_production_count": 0,
        "today_rmc_production_m3": 0.0,
        "today_rmc_dispatch_count": 0,
        "today_wetmix_production_count": 0,
        "today_wetmix_production_qty": 0.0,
        "precast_stock_units": 0.0,
        "today_precast_dispatch_count": 0,
        "low_stock_alerts": 0,
        "today_qc_count": 0,
        "qc_fail_count": 0,
        "open_maintenance_jobs": 0,
        "today_crusher_production_ton": 0.0,
        "today_crusher_production_count": 0,
    }


def plant_dashboard_stats(db) -> dict[str, Any]:
    try:
        today = _today()
        active = 0
        if _table_exists(db, "plants") and _column_exists(db, "plants", "status"):
            row = db.execute(
                "SELECT COUNT(*) FROM plants WHERE status='Active'"
            ).fetchone()
            active = int(row[0]) if row else 0

        today_prod_count = _count_table(
            db, "asphalt_production", "production_date=?", (today,)
        )
        today_disp_count = _count_table(
            db, "asphalt_dispatch", "dispatch_date=?", (today,)
        )
        today_prod_ton = 0.0
        today_disp_ton = 0.0
        if _table_exists(db, "asphalt_production"):
            row = db.execute(
                "SELECT COALESCE(SUM(qty_ton),0) FROM asphalt_production WHERE production_date=?",
                (today,),
            ).fetchone()
            today_prod_ton = float(row[0] or 0)
        if _table_exists(db, "asphalt_dispatch"):
            row = db.execute(
                "SELECT COALESCE(SUM(qty_ton),0) FROM asphalt_dispatch WHERE dispatch_date=?",
                (today,),
            ).fetchone()
            today_disp_ton = float(row[0] or 0)

        if _table_exists(db, "asphalt_dispatch"):
            row = db.execute(
                "SELECT COALESCE(SUM(qty_ton),0) FROM asphalt_dispatch WHERE dispatch_date=?",
                (today,),
            ).fetchone()
            today_disp_ton = float(row[0] or 0)

        today_rmc_prod_count = _count_table(
            db, "rmc_production", "production_date=?", (today,)
        )
        today_rmc_prod_m3 = 0.0
        if _table_exists(db, "rmc_production"):
            row = db.execute(
                "SELECT COALESCE(SUM(qty_m3),0) FROM rmc_production WHERE production_date=?",
                (today,),
            ).fetchone()
            today_rmc_prod_m3 = float(row[0] or 0)
        today_rmc_disp_count = _count_table(
            db, "rmc_dispatch", "dispatch_date=?", (today,)
        )
        today_wetmix_count = _count_table(
            db, "wetmix_production", "production_date=?", (today,)
        )
        today_wetmix_qty = 0.0
        if _table_exists(db, "wetmix_production"):
            row = db.execute(
                "SELECT COALESCE(SUM(qty),0) FROM wetmix_production WHERE production_date=?",
                (today,),
            ).fetchone()
            today_wetmix_qty = float(row[0] or 0)
        precast_stock = 0.0
        if _table_exists(db, "plant_stock"):
            row = db.execute(
                "SELECT COALESCE(SUM(closing),0) FROM plant_stock WHERE material_type LIKE 'PRECAST:%'"
            ).fetchone()
            precast_stock = float(row[0] or 0)
        today_precast_disp = _count_table(
            db, "precast_dispatch", "dispatch_date=?", (today,)
        )
        today_qc_count = _count_table(db, "plant_qc_records", "qc_date=?", (today,))
        qc_fail_count = 0
        if _table_exists(db, "plant_qc_records"):
            row = db.execute(
                "SELECT COUNT(*) FROM plant_qc_records WHERE pass_fail='Fail' AND qc_date>=?",
                (datetime.now().strftime("%Y-%m-01"),),
            ).fetchone()
            qc_fail_count = int(row[0] or 0)
        open_maint = 0
        if _table_exists(db, "plant_maintenance_jobs"):
            row = db.execute(
                "SELECT COUNT(*) FROM plant_maintenance_jobs WHERE status IN ('Open','In Progress')"
            ).fetchone()
            open_maint = int(row[0] or 0)
        today_crusher_count = _count_table(
            db, "crusher_production", "production_date=?", (today,)
        )
        today_crusher_ton = 0.0
        if _table_exists(db, "crusher_production"):
            row = db.execute(
                "SELECT COALESCE(SUM(qty_ton),0) FROM crusher_production WHERE production_date=?",
                (today,),
            ).fetchone()
            today_crusher_ton = float(row[0] or 0)

        return {
            "total_plants": _count_table(db, "plants"),
            "active_plants": active,
            "today_production_count": today_prod_count,
            "today_dispatch_count": today_disp_count,
            "today_production_ton": today_prod_ton,
            "today_dispatch_ton": today_disp_ton,
            "today_rmc_production_count": today_rmc_prod_count,
            "today_rmc_production_m3": today_rmc_prod_m3,
            "today_rmc_dispatch_count": today_rmc_disp_count,
            "today_wetmix_production_count": today_wetmix_count,
            "today_wetmix_production_qty": today_wetmix_qty,
            "precast_stock_units": precast_stock,
            "today_precast_dispatch_count": today_precast_disp,
            "low_stock_alerts": 0,
            "today_qc_count": today_qc_count,
            "qc_fail_count": qc_fail_count,
            "open_maintenance_jobs": open_maint,
            "today_crusher_production_ton": today_crusher_ton,
            "today_crusher_production_count": today_crusher_count,
        }
    except Exception:
        return _empty_plant_dashboard_stats()


def _build_consumption_json(form) -> str:
    items: list[dict[str, Any]] = []
    for mat in CONSUMPTION_MATERIALS:
        qty = _safe_float(form.get(f"consumption_{mat}"))
        if qty > 0:
            unit = STOCK_UNIT_LITER if mat == "diesel" else STOCK_UNIT_TON
            items.append({"material": mat, "qty": qty, "unit": unit})
    return json.dumps(items)


def _build_material_consumption_json(form, materials: tuple[str, ...], units: dict[str, str] | None = None) -> str:
    items: list[dict[str, Any]] = []
    default_units = units or {}
    for mat in materials:
        qty = _safe_float(form.get(f"consumption_{mat}"))
        if qty > 0:
            unit = default_units.get(mat, STOCK_UNIT_TON)
            items.append({"material": mat, "qty": qty, "unit": unit})
    return json.dumps(items)


def _rmc_stock_key(grade: str) -> str:
    return f"RMC:{(grade or 'Other').strip()}"


def _wetmix_stock_key(material_mix: str) -> str:
    return f"WETMIX:{(material_mix or 'Mix').strip()}"


def _precast_stock_key(product_type: str) -> str:
    return f"PRECAST:{(product_type or 'Other').strip()}"


def _parse_consumption_json(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _get_stock_row(db, plant_id: int, material_type: str) -> dict | None:
    if not _table_exists(db, "plant_stock"):
        return None
    row = db.execute(
        "SELECT * FROM plant_stock WHERE plant_id=? AND material_type=?",
        (plant_id, material_type),
    ).fetchone()
    return dict(row) if row else None


def _ensure_stock_row(db, plant_id: int, material_type: str, unit: str = STOCK_UNIT_TON) -> None:
    if _get_stock_row(db, plant_id, material_type):
        return
    db.execute(
        "INSERT INTO plant_stock(plant_id, material_type, opening, production, dispatch, closing, unit, updated_at) "
        "VALUES(?,?,0,0,0,0,?,?)",
        (plant_id, material_type, unit, _now_ts()),
    )


def _apply_stock_delta(
    db,
    plant_id: int,
    material_type: str,
    production_delta: float = 0,
    dispatch_delta: float = 0,
    unit: str = STOCK_UNIT_TON,
) -> None:
    _ensure_stock_row(db, plant_id, material_type, unit)
    row = _get_stock_row(db, plant_id, material_type)
    if not row:
        return
    opening = float(row.get("opening") or 0)
    production = float(row.get("production") or 0) + production_delta
    dispatch = float(row.get("dispatch") or 0) + dispatch_delta
    closing = opening + production - dispatch
    if closing < -0.001:
        raise ValueError(
            f"Insufficient stock for {material_type}. "
            f"Available {opening + float(row.get('production') or 0) - float(row.get('dispatch') or 0):.2f} "
            f"{unit}, dispatch would exceed balance."
        )
    db.execute(
        "UPDATE plant_stock SET production=?, dispatch=?, closing=?, updated_at=? "
        "WHERE plant_id=? AND material_type=?",
        (production, dispatch, closing, _now_ts(), plant_id, material_type),
    )


def list_plant_stock(db, plant_id: int | None = None) -> list[dict]:
    if not _table_exists(db, "plant_stock"):
        return []
    sql = (
        "SELECT s.*, p.plant_name, p.plant_id AS plant_code FROM plant_stock s "
        "JOIN plants p ON s.plant_id = p.id "
    )
    params: tuple = ()
    if plant_id:
        sql += "WHERE s.plant_id=? "
        params = (plant_id,)
    sql += "ORDER BY p.plant_name, s.material_type LIMIT 500"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def get_plant_stock_balance(db, plant_id: int, material_type: str) -> float:
    row = _get_stock_row(db, plant_id, material_type)
    if not row:
        return 0.0
    return float(row.get("closing") or 0)


# --- Plant Master ---
def list_plants(db, search: str = "", plant_type: str = "") -> list[dict]:
    if not _table_exists(db, "plants"):
        return []
    sql = (
        "SELECT pl.*, p.project_name FROM plants pl "
        "LEFT JOIN projects p ON pl.project_id = p.id WHERE 1=1 "
    )
    params: list[Any] = []
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (pl.plant_id LIKE ? OR pl.plant_name LIKE ? OR pl.location LIKE ?) "
        params.extend([q, q, q])
    if plant_type.strip():
        sql += "AND pl.plant_type=? "
        params.append(plant_type.strip())
    sql += "ORDER BY pl.plant_name ASC LIMIT 500"
    return [dict(r) for r in db.execute(sql, tuple(params)).fetchall()]


def list_active_plants(db, plant_type: str = "") -> list[dict]:
    if not _table_exists(db, "plants"):
        return []
    sql = "SELECT id, plant_id, plant_name, plant_type FROM plants WHERE status='Active' "
    params: tuple = ()
    if plant_type.strip():
        sql += "AND plant_type=? "
        params = (plant_type.strip(),)
    sql += "ORDER BY plant_name"
    return [dict(r) for r in db.execute(sql, params).fetchall()]


def get_plant(db, record_id: int) -> dict | None:
    if not _table_exists(db, "plants"):
        return None
    row = db.execute(
        "SELECT pl.*, p.project_name FROM plants pl "
        "LEFT JOIN projects p ON pl.project_id = p.id WHERE pl.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_plant(db, form, username: str, record_id: int | None = None) -> int:
    name = (form.get("plant_name") or "").strip()
    if not name:
        raise ValueError("Plant name is required.")
    plant_type = (form.get("plant_type") or "Asphalt").strip()
    if plant_type not in PLANT_TYPES:
        raise ValueError("Invalid plant type.")
    status = (form.get("status") or "Active").strip()
    if status not in PLANT_STATUSES:
        raise ValueError("Invalid plant status.")
    project_id = form.get("project_id") or None
    now = _now_ts()
    fields = (
        name,
        plant_type,
        (form.get("capacity") or "").strip(),
        (form.get("location") or "").strip(),
        project_id,
        (form.get("incharge") or "").strip(),
        status,
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_plant(db, record_id)
        if not existing:
            raise ValueError("Plant not found.")
        db.execute(
            "UPDATE plants SET plant_name=?, plant_type=?, capacity=?, location=?, "
            "project_id=?, incharge=?, status=?, remarks=?, modified_at=? WHERE id=?",
            (*fields, now, record_id),
        )
        return record_id
    plant_id_code = _next_plant_id(db)
    db.execute(
        "INSERT INTO plants(plant_id, plant_name, plant_type, capacity, location, "
        "project_id, incharge, status, remarks, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (plant_id_code, *fields, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_plant(db, record_id: int) -> None:
    for table in (
        "asphalt_production", "asphalt_dispatch",
        "rmc_production", "rmc_dispatch",
        "wetmix_production", "precast_production", "precast_dispatch",
        "crusher_production", "plant_qc_records", "plant_maintenance_jobs",
    ):
        if _count_table(db, table, "plant_id=?", (record_id,)):
            raise ValueError(f"Cannot delete plant with {table.replace('_', ' ')} records.")
    db.execute("DELETE FROM plant_stock WHERE plant_id=?", (record_id,))
    db.execute("DELETE FROM plants WHERE id=?", (record_id,))


# --- Asphalt Production ---
def list_asphalt_production(db, plant_id: int | None = None, search: str = "") -> list[dict]:
    if not _table_exists(db, "asphalt_production"):
        return []
    sql = (
        "SELECT a.*, pl.plant_name, pl.plant_id AS plant_code, p.project_name "
        "FROM asphalt_production a "
        "JOIN plants pl ON a.plant_id = pl.id "
        "LEFT JOIN projects p ON a.project_id = p.id WHERE 1=1 "
    )
    params: list[Any] = []
    if plant_id:
        sql += "AND a.plant_id=? "
        params.append(plant_id)
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (a.batch_number LIKE ? OR a.mix_type LIKE ? OR a.operator LIKE ?) "
        params.extend([q, q, q])
    sql += "ORDER BY a.production_date DESC, a.id DESC LIMIT 500"
    rows = db.execute(sql, tuple(params)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["consumption"] = _parse_consumption_json(item.get("consumption_json"))
        result.append(item)
    return result


def get_asphalt_production(db, record_id: int) -> dict | None:
    if not _table_exists(db, "asphalt_production"):
        return None
    row = db.execute(
        "SELECT a.*, pl.plant_name, pl.plant_id AS plant_code, p.project_name "
        "FROM asphalt_production a "
        "JOIN plants pl ON a.plant_id = pl.id "
        "LEFT JOIN projects p ON a.project_id = p.id WHERE a.id=?",
        (record_id,),
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["consumption"] = _parse_consumption_json(item.get("consumption_json"))
    return item


def save_asphalt_production(
    db, form, username: str, record_id: int | None = None
) -> int:
    plant_id = form.get("plant_id")
    if not plant_id:
        raise ValueError("Plant is required.")
    plant_id = int(plant_id)
    prod_date = (form.get("production_date") or _today()).strip()
    mix_type = (form.get("mix_type") or "Other").strip()
    qty = _safe_float(form.get("qty_ton"))
    if qty <= 0:
        raise ValueError("Production quantity (ton) must be greater than zero.")
    batch = (form.get("batch_number") or "").strip()
    if not batch:
        batch = _next_doc_number(db, "ASP-BATCH", "asphalt_production", "batch_number")
    consumption_json = _build_consumption_json(form)
    now = _now_ts()
    fields = (
        prod_date,
        plant_id,
        form.get("project_id") or None,
        mix_type,
        batch,
        qty,
        (form.get("shift") or "Day").strip(),
        (form.get("operator") or "").strip(),
        consumption_json,
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_asphalt_production(db, record_id)
        if not existing:
            raise ValueError("Production record not found.")
        old_plant = int(existing["plant_id"])
        old_mix = existing.get("mix_type") or "Other"
        old_qty = float(existing.get("qty_ton") or 0)
        if old_plant != plant_id or old_mix != mix_type:
            _apply_stock_delta(db, old_plant, old_mix, production_delta=-old_qty)
            _apply_stock_delta(db, plant_id, mix_type, production_delta=qty)
        else:
            _apply_stock_delta(db, plant_id, mix_type, production_delta=qty - old_qty)
        db.execute(
            "UPDATE asphalt_production SET production_date=?, plant_id=?, project_id=?, "
            "mix_type=?, batch_number=?, qty_ton=?, shift=?, operator=?, consumption_json=?, "
            "remarks=?, modified_at=? WHERE id=?",
            (*fields, now, record_id),
        )
        return record_id
    _apply_stock_delta(db, plant_id, mix_type, production_delta=qty)
    db.execute(
        "INSERT INTO asphalt_production(production_date, plant_id, project_id, mix_type, "
        "batch_number, qty_ton, shift, operator, consumption_json, remarks, "
        "created_by, created_at, modified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (*fields, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_asphalt_production(db, record_id: int) -> None:
    existing = get_asphalt_production(db, record_id)
    if not existing:
        return
    plant_id = int(existing["plant_id"])
    mix_type = existing.get("mix_type") or "Other"
    qty = float(existing.get("qty_ton") or 0)
    _apply_stock_delta(db, plant_id, mix_type, production_delta=-qty)
    db.execute("DELETE FROM asphalt_production WHERE id=?", (record_id,))


# --- Asphalt Dispatch ---
def list_asphalt_dispatch(db, plant_id: int | None = None, search: str = "") -> list[dict]:
    if not _table_exists(db, "asphalt_dispatch"):
        return []
    sql = (
        "SELECT d.*, pl.plant_name, pl.plant_id AS plant_code, p.project_name "
        "FROM asphalt_dispatch d "
        "JOIN plants pl ON d.plant_id = pl.id "
        "LEFT JOIN projects p ON d.project_id = p.id WHERE 1=1 "
    )
    params: list[Any] = []
    if plant_id:
        sql += "AND d.plant_id=? "
        params.append(plant_id)
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (d.dispatch_number LIKE ? OR d.vehicle_number LIKE ?) "
        params.extend([q, q])
    sql += "ORDER BY d.dispatch_date DESC, d.id DESC LIMIT 500"
    return [dict(r) for r in db.execute(sql, tuple(params)).fetchall()]


def get_asphalt_dispatch(db, record_id: int) -> dict | None:
    if not _table_exists(db, "asphalt_dispatch"):
        return None
    row = db.execute(
        "SELECT d.*, pl.plant_name, pl.plant_id AS plant_code, p.project_name "
        "FROM asphalt_dispatch d "
        "JOIN plants pl ON d.plant_id = pl.id "
        "LEFT JOIN projects p ON d.project_id = p.id WHERE d.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_asphalt_dispatch(
    db, form, username: str, record_id: int | None = None
) -> int:
    plant_id = form.get("plant_id")
    if not plant_id:
        raise ValueError("Plant is required.")
    plant_id = int(plant_id)
    disp_date = (form.get("dispatch_date") or _today()).strip()
    mix_type = (form.get("mix_type") or "Other").strip()
    qty = _safe_float(form.get("qty_ton"))
    if qty <= 0:
        raise ValueError("Dispatch quantity (ton) must be greater than zero.")
    vehicle = (form.get("vehicle_number") or "").strip()
    now = _now_ts()
    fields = (
        disp_date,
        plant_id,
        form.get("project_id") or None,
        vehicle,
        mix_type,
        qty,
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_asphalt_dispatch(db, record_id)
        if not existing:
            raise ValueError("Dispatch record not found.")
        old_plant = int(existing["plant_id"])
        old_mix = existing.get("mix_type") or "Other"
        old_qty = float(existing.get("qty_ton") or 0)
        _apply_stock_delta(db, old_plant, old_mix, dispatch_delta=-old_qty)
        _apply_stock_delta(db, plant_id, mix_type, dispatch_delta=qty)
        db.execute(
            "UPDATE asphalt_dispatch SET dispatch_date=?, plant_id=?, project_id=?, "
            "vehicle_number=?, mix_type=?, qty_ton=?, remarks=?, modified_at=? WHERE id=?",
            (*fields, now, record_id),
        )
        return record_id
    dispatch_number = _next_doc_number(db, "ASP-DSP", "asphalt_dispatch", "dispatch_number")
    _apply_stock_delta(db, plant_id, mix_type, dispatch_delta=qty)
    db.execute(
        "INSERT INTO asphalt_dispatch(dispatch_number, dispatch_date, plant_id, project_id, "
        "vehicle_number, mix_type, qty_ton, remarks, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (dispatch_number, *fields, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_asphalt_dispatch(db, record_id: int) -> None:
    existing = get_asphalt_dispatch(db, record_id)
    if not existing:
        return
    plant_id = int(existing["plant_id"])
    mix_type = existing.get("mix_type") or "Other"
    qty = float(existing.get("qty_ton") or 0)
    _apply_stock_delta(db, plant_id, mix_type, dispatch_delta=qty)
    db.execute("DELETE FROM asphalt_dispatch WHERE id=?", (record_id,))


# --- RMC Production ---
def list_rmc_production(db, plant_id: int | None = None, search: str = "") -> list[dict]:
    if not _table_exists(db, "rmc_production"):
        return []
    sql = (
        "SELECT a.*, pl.plant_name, pl.plant_id AS plant_code, p.project_name "
        "FROM rmc_production a "
        "JOIN plants pl ON a.plant_id = pl.id "
        "LEFT JOIN projects p ON a.project_id = p.id WHERE 1=1 "
    )
    params: list[Any] = []
    if plant_id:
        sql += "AND a.plant_id=? "
        params.append(plant_id)
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (a.grade LIKE ? OR a.operator LIKE ?) "
        params.extend([q, q])
    sql += "ORDER BY a.production_date DESC, a.id DESC LIMIT 500"
    result = []
    for row in db.execute(sql, tuple(params)).fetchall():
        item = dict(row)
        item["consumption"] = _parse_consumption_json(item.get("consumption_json"))
        result.append(item)
    return result


def get_rmc_production(db, record_id: int) -> dict | None:
    if not _table_exists(db, "rmc_production"):
        return None
    row = db.execute(
        "SELECT a.*, pl.plant_name, pl.plant_id AS plant_code, p.project_name "
        "FROM rmc_production a "
        "JOIN plants pl ON a.plant_id = pl.id "
        "LEFT JOIN projects p ON a.project_id = p.id WHERE a.id=?",
        (record_id,),
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["consumption"] = _parse_consumption_json(item.get("consumption_json"))
    return item


def save_rmc_production(db, form, username: str, record_id: int | None = None) -> int:
    plant_id = form.get("plant_id")
    if not plant_id:
        raise ValueError("Plant is required.")
    plant_id = int(plant_id)
    prod_date = (form.get("production_date") or _today()).strip()
    grade = (form.get("grade") or "Other").strip()
    if grade not in RMC_GRADES:
        grade = "Other"
    qty = _safe_float(form.get("qty_m3"))
    if qty <= 0:
        raise ValueError("Production quantity (m³) must be greater than zero.")
    stock_key = _rmc_stock_key(grade)
    consumption_json = _build_material_consumption_json(
        form,
        RMC_CONSUMPTION_MATERIALS,
        {"cement": STOCK_UNIT_TON, "sand": STOCK_UNIT_TON, "aggregate": STOCK_UNIT_TON,
         "admixture": STOCK_UNIT_LITER, "water": STOCK_UNIT_LITER},
    )
    now = _now_ts()
    fields = (
        prod_date, plant_id, form.get("project_id") or None, grade, qty,
        (form.get("shift") or "Day").strip(),
        (form.get("operator") or "").strip(),
        consumption_json,
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_rmc_production(db, record_id)
        if not existing:
            raise ValueError("Production record not found.")
        old_plant = int(existing["plant_id"])
        old_key = _rmc_stock_key(existing.get("grade") or "Other")
        old_qty = float(existing.get("qty_m3") or 0)
        if old_plant != plant_id or old_key != stock_key:
            _apply_stock_delta(db, old_plant, old_key, production_delta=-old_qty, unit=STOCK_UNIT_M3)
            _apply_stock_delta(db, plant_id, stock_key, production_delta=qty, unit=STOCK_UNIT_M3)
        else:
            _apply_stock_delta(db, plant_id, stock_key, production_delta=qty - old_qty, unit=STOCK_UNIT_M3)
        db.execute(
            "UPDATE rmc_production SET production_date=?, plant_id=?, project_id=?, grade=?, "
            "qty_m3=?, shift=?, operator=?, consumption_json=?, remarks=?, modified_at=? WHERE id=?",
            (*fields, now, record_id),
        )
        return record_id
    _apply_stock_delta(db, plant_id, stock_key, production_delta=qty, unit=STOCK_UNIT_M3)
    db.execute(
        "INSERT INTO rmc_production(production_date, plant_id, project_id, grade, qty_m3, "
        "shift, operator, consumption_json, remarks, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (*fields, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_rmc_production(db, record_id: int) -> None:
    existing = get_rmc_production(db, record_id)
    if not existing:
        return
    plant_id = int(existing["plant_id"])
    stock_key = _rmc_stock_key(existing.get("grade") or "Other")
    qty = float(existing.get("qty_m3") or 0)
    _apply_stock_delta(db, plant_id, stock_key, production_delta=-qty, unit=STOCK_UNIT_M3)
    db.execute("DELETE FROM rmc_production WHERE id=?", (record_id,))


# --- RMC Dispatch ---
def list_rmc_dispatch(db, plant_id: int | None = None, search: str = "") -> list[dict]:
    if not _table_exists(db, "rmc_dispatch"):
        return []
    sql = (
        "SELECT d.*, pl.plant_name, pl.plant_id AS plant_code, p.project_name "
        "FROM rmc_dispatch d "
        "JOIN plants pl ON d.plant_id = pl.id "
        "LEFT JOIN projects p ON d.project_id = p.id WHERE 1=1 "
    )
    params: list[Any] = []
    if plant_id:
        sql += "AND d.plant_id=? "
        params.append(plant_id)
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (d.dispatch_number LIKE ? OR d.vehicle_number LIKE ?) "
        params.extend([q, q])
    sql += "ORDER BY d.dispatch_date DESC, d.id DESC LIMIT 500"
    return [dict(r) for r in db.execute(sql, tuple(params)).fetchall()]


def get_rmc_dispatch(db, record_id: int) -> dict | None:
    if not _table_exists(db, "rmc_dispatch"):
        return None
    row = db.execute(
        "SELECT d.*, pl.plant_name, pl.plant_id AS plant_code, p.project_name "
        "FROM rmc_dispatch d "
        "JOIN plants pl ON d.plant_id = pl.id "
        "LEFT JOIN projects p ON d.project_id = p.id WHERE d.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_rmc_dispatch(db, form, username: str, record_id: int | None = None) -> int:
    plant_id = form.get("plant_id")
    if not plant_id:
        raise ValueError("Plant is required.")
    plant_id = int(plant_id)
    disp_date = (form.get("dispatch_date") or _today()).strip()
    grade = (form.get("grade") or "Other").strip()
    if grade not in RMC_GRADES:
        grade = "Other"
    stock_key = _rmc_stock_key(grade)
    qty = _safe_float(form.get("qty_m3"))
    if qty <= 0:
        raise ValueError("Dispatch quantity (m³) must be greater than zero.")
    now = _now_ts()
    fields = (
        disp_date, plant_id, form.get("project_id") or None,
        (form.get("vehicle_number") or "").strip(),
        qty,
        (form.get("loading_time") or "").strip(),
        (form.get("dispatch_time") or "").strip(),
        (form.get("delivery_time") or "").strip() or None,
        (form.get("remarks") or "").strip(),
        grade,
    )
    if record_id:
        existing = get_rmc_dispatch(db, record_id)
        if not existing:
            raise ValueError("Dispatch record not found.")
        old_plant = int(existing["plant_id"])
        old_key = _rmc_stock_key(existing.get("grade") or "Other")
        old_qty = float(existing.get("qty_m3") or 0)
        _apply_stock_delta(db, old_plant, old_key, dispatch_delta=-old_qty, unit=STOCK_UNIT_M3)
        _apply_stock_delta(db, plant_id, stock_key, dispatch_delta=qty, unit=STOCK_UNIT_M3)
        db.execute(
            "UPDATE rmc_dispatch SET dispatch_date=?, plant_id=?, project_id=?, vehicle_number=?, "
            "qty_m3=?, loading_time=?, dispatch_time=?, delivery_time=?, remarks=?, grade=?, "
            "modified_at=? WHERE id=?",
            (*fields, now, record_id),
        )
        return record_id
    dispatch_number = _next_doc_number(db, "RMC-DSP", "rmc_dispatch", "dispatch_number")
    _apply_stock_delta(db, plant_id, stock_key, dispatch_delta=qty, unit=STOCK_UNIT_M3)
    db.execute(
        "INSERT INTO rmc_dispatch(dispatch_number, dispatch_date, plant_id, project_id, "
        "vehicle_number, qty_m3, loading_time, dispatch_time, delivery_time, remarks, grade, "
        "created_by, created_at, modified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (dispatch_number, *fields, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_rmc_dispatch(db, record_id: int) -> None:
    existing = get_rmc_dispatch(db, record_id)
    if not existing:
        return
    plant_id = int(existing["plant_id"])
    stock_key = _rmc_stock_key(existing.get("grade") or "Other")
    qty = float(existing.get("qty_m3") or 0)
    _apply_stock_delta(db, plant_id, stock_key, dispatch_delta=-qty, unit=STOCK_UNIT_M3)
    db.execute("DELETE FROM rmc_dispatch WHERE id=?", (record_id,))


# --- Wet Mix Production ---
def list_wetmix_production(db, plant_id: int | None = None, search: str = "") -> list[dict]:
    if not _table_exists(db, "wetmix_production"):
        return []
    sql = (
        "SELECT w.*, pl.plant_name, pl.plant_id AS plant_code "
        "FROM wetmix_production w "
        "JOIN plants pl ON w.plant_id = pl.id WHERE 1=1 "
    )
    params: list[Any] = []
    if plant_id:
        sql += "AND w.plant_id=? "
        params.append(plant_id)
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (w.material_mix LIKE ? OR w.operator LIKE ?) "
        params.extend([q, q])
    sql += "ORDER BY w.production_date DESC, w.id DESC LIMIT 500"
    result = []
    for row in db.execute(sql, tuple(params)).fetchall():
        item = dict(row)
        item["consumption"] = _parse_consumption_json(item.get("consumption_json"))
        result.append(item)
    return result


def get_wetmix_production(db, record_id: int) -> dict | None:
    if not _table_exists(db, "wetmix_production"):
        return None
    row = db.execute(
        "SELECT w.*, pl.plant_name, pl.plant_id AS plant_code "
        "FROM wetmix_production w "
        "JOIN plants pl ON w.plant_id = pl.id WHERE w.id=?",
        (record_id,),
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["consumption"] = _parse_consumption_json(item.get("consumption_json"))
    return item


def save_wetmix_production(db, form, username: str, record_id: int | None = None) -> int:
    plant_id = form.get("plant_id")
    if not plant_id:
        raise ValueError("Plant is required.")
    plant_id = int(plant_id)
    prod_date = (form.get("production_date") or _today()).strip()
    material_mix = (form.get("material_mix") or "WMM").strip()
    qty = _safe_float(form.get("qty"))
    if qty <= 0:
        raise ValueError("Production quantity must be greater than zero.")
    stock_key = _wetmix_stock_key(material_mix)
    consumption_json = _build_material_consumption_json(
        form,
        WETMIX_CONSUMPTION_MATERIALS,
        {"water": STOCK_UNIT_LITER, "additive": STOCK_UNIT_LITER},
    )
    now = _now_ts()
    fields = (
        prod_date, plant_id, material_mix, qty,
        (form.get("operator") or "").strip(),
        consumption_json,
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_wetmix_production(db, record_id)
        if not existing:
            raise ValueError("Production record not found.")
        old_plant = int(existing["plant_id"])
        old_key = _wetmix_stock_key(existing.get("material_mix") or "WMM")
        old_qty = float(existing.get("qty") or 0)
        if old_plant != plant_id or old_key != stock_key:
            _apply_stock_delta(db, old_plant, old_key, production_delta=-old_qty)
            _apply_stock_delta(db, plant_id, stock_key, production_delta=qty)
        else:
            _apply_stock_delta(db, plant_id, stock_key, production_delta=qty - old_qty)
        db.execute(
            "UPDATE wetmix_production SET production_date=?, plant_id=?, material_mix=?, qty=?, "
            "operator=?, consumption_json=?, remarks=?, modified_at=? WHERE id=?",
            (*fields, now, record_id),
        )
        return record_id
    _apply_stock_delta(db, plant_id, stock_key, production_delta=qty)
    db.execute(
        "INSERT INTO wetmix_production(production_date, plant_id, material_mix, qty, operator, "
        "consumption_json, remarks, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (*fields, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_wetmix_production(db, record_id: int) -> None:
    existing = get_wetmix_production(db, record_id)
    if not existing:
        return
    plant_id = int(existing["plant_id"])
    stock_key = _wetmix_stock_key(existing.get("material_mix") or "WMM")
    qty = float(existing.get("qty") or 0)
    _apply_stock_delta(db, plant_id, stock_key, production_delta=-qty)
    db.execute("DELETE FROM wetmix_production WHERE id=?", (record_id,))


# --- Precast Production ---
def list_precast_production(db, plant_id: int | None = None, search: str = "") -> list[dict]:
    if not _table_exists(db, "precast_production"):
        return []
    sql = (
        "SELECT pr.*, pl.plant_name, pl.plant_id AS plant_code "
        "FROM precast_production pr "
        "JOIN plants pl ON pr.plant_id = pl.id WHERE 1=1 "
    )
    params: list[Any] = []
    if plant_id:
        sql += "AND pr.plant_id=? "
        params.append(plant_id)
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (pr.product_type LIKE ? OR pr.status LIKE ?) "
        params.extend([q, q])
    sql += "ORDER BY pr.casting_date DESC, pr.id DESC LIMIT 500"
    return [dict(r) for r in db.execute(sql, tuple(params)).fetchall()]


def get_precast_production(db, record_id: int) -> dict | None:
    if not _table_exists(db, "precast_production"):
        return None
    row = db.execute(
        "SELECT pr.*, pl.plant_name, pl.plant_id AS plant_code "
        "FROM precast_production pr "
        "JOIN plants pl ON pr.plant_id = pl.id WHERE pr.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_precast_production(db, form, username: str, record_id: int | None = None) -> int:
    plant_id = form.get("plant_id")
    if not plant_id:
        raise ValueError("Plant is required.")
    plant_id = int(plant_id)
    product_type = (form.get("product_type") or "Other").strip()
    if product_type not in PRECAST_PRODUCT_TYPES:
        product_type = "Other"
    qty = _safe_float(form.get("qty"))
    if qty <= 0:
        raise ValueError("Production quantity must be greater than zero.")
    status = (form.get("status") or "Casting").strip()
    if status not in PRECAST_STATUSES:
        status = "Casting"
    stock_key = _precast_stock_key(product_type)
    now = _now_ts()
    fields = (
        plant_id, product_type, qty,
        (form.get("casting_date") or _today()).strip(),
        (form.get("curing_date") or "").strip() or None,
        status,
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_precast_production(db, record_id)
        if not existing:
            raise ValueError("Production record not found.")
        old_plant = int(existing["plant_id"])
        old_key = _precast_stock_key(existing.get("product_type") or "Other")
        old_qty = float(existing.get("qty") or 0)
        if old_plant != plant_id or old_key != stock_key:
            _apply_stock_delta(db, old_plant, old_key, production_delta=-old_qty, unit="Nos")
            _apply_stock_delta(db, plant_id, stock_key, production_delta=qty, unit="Nos")
        else:
            _apply_stock_delta(db, plant_id, stock_key, production_delta=qty - old_qty, unit="Nos")
        db.execute(
            "UPDATE precast_production SET plant_id=?, product_type=?, qty=?, casting_date=?, "
            "curing_date=?, status=?, remarks=?, modified_at=? WHERE id=?",
            (*fields, now, record_id),
        )
        return record_id
    _apply_stock_delta(db, plant_id, stock_key, production_delta=qty, unit="Nos")
    db.execute(
        "INSERT INTO precast_production(plant_id, product_type, qty, casting_date, curing_date, "
        "status, remarks, created_by, created_at, modified_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (*fields, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_precast_production(db, record_id: int) -> None:
    existing = get_precast_production(db, record_id)
    if not existing:
        return
    plant_id = int(existing["plant_id"])
    stock_key = _precast_stock_key(existing.get("product_type") or "Other")
    qty = float(existing.get("qty") or 0)
    _apply_stock_delta(db, plant_id, stock_key, production_delta=-qty, unit="Nos")
    db.execute("DELETE FROM precast_production WHERE id=?", (record_id,))


# --- Precast Dispatch ---
def list_precast_dispatch(db, plant_id: int | None = None, search: str = "") -> list[dict]:
    if not _table_exists(db, "precast_dispatch"):
        return []
    sql = (
        "SELECT d.*, pl.plant_name, pl.plant_id AS plant_code, p.project_name "
        "FROM precast_dispatch d "
        "JOIN plants pl ON d.plant_id = pl.id "
        "LEFT JOIN projects p ON d.project_id = p.id WHERE 1=1 "
    )
    params: list[Any] = []
    if plant_id:
        sql += "AND d.plant_id=? "
        params.append(plant_id)
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (d.dispatch_number LIKE ? OR d.vehicle_number LIKE ?) "
        params.extend([q, q])
    sql += "ORDER BY d.dispatch_date DESC, d.id DESC LIMIT 500"
    return [dict(r) for r in db.execute(sql, tuple(params)).fetchall()]


def get_precast_dispatch(db, record_id: int) -> dict | None:
    if not _table_exists(db, "precast_dispatch"):
        return None
    row = db.execute(
        "SELECT d.*, pl.plant_name, pl.plant_id AS plant_code, p.project_name "
        "FROM precast_dispatch d "
        "JOIN plants pl ON d.plant_id = pl.id "
        "LEFT JOIN projects p ON d.project_id = p.id WHERE d.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_precast_dispatch(db, form, username: str, record_id: int | None = None) -> int:
    plant_id = form.get("plant_id")
    if not plant_id:
        raise ValueError("Plant is required.")
    plant_id = int(plant_id)
    disp_date = (form.get("dispatch_date") or _today()).strip()
    product_type = (form.get("product_type") or "Other").strip()
    if product_type not in PRECAST_PRODUCT_TYPES:
        product_type = "Other"
    stock_key = _precast_stock_key(product_type)
    qty = _safe_float(form.get("qty"))
    if qty <= 0:
        raise ValueError("Dispatch quantity must be greater than zero.")
    now = _now_ts()
    fields = (
        disp_date, plant_id, form.get("project_id") or None,
        product_type, qty,
        (form.get("vehicle_number") or "").strip(),
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_precast_dispatch(db, record_id)
        if not existing:
            raise ValueError("Dispatch record not found.")
        old_plant = int(existing["plant_id"])
        old_key = _precast_stock_key(existing.get("product_type") or "Other")
        old_qty = float(existing.get("qty") or 0)
        _apply_stock_delta(db, old_plant, old_key, dispatch_delta=-old_qty, unit="Nos")
        _apply_stock_delta(db, plant_id, stock_key, dispatch_delta=qty, unit="Nos")
        db.execute(
            "UPDATE precast_dispatch SET dispatch_date=?, plant_id=?, project_id=?, "
            "product_type=?, qty=?, vehicle_number=?, remarks=?, modified_at=? WHERE id=?",
            (*fields, now, record_id),
        )
        return record_id
    dispatch_number = _next_doc_number(db, "PRC-DSP", "precast_dispatch", "dispatch_number")
    _apply_stock_delta(db, plant_id, stock_key, dispatch_delta=qty, unit="Nos")
    db.execute(
        "INSERT INTO precast_dispatch(dispatch_number, dispatch_date, plant_id, project_id, "
        "product_type, qty, vehicle_number, remarks, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (dispatch_number, *fields, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_precast_dispatch(db, record_id: int) -> None:
    existing = get_precast_dispatch(db, record_id)
    if not existing:
        return
    plant_id = int(existing["plant_id"])
    stock_key = _precast_stock_key(existing.get("product_type") or "Other")
    qty = float(existing.get("qty") or 0)
    _apply_stock_delta(db, plant_id, stock_key, dispatch_delta=-qty, unit="Nos")
    db.execute("DELETE FROM precast_dispatch WHERE id=?", (record_id,))


def _seed_default_material_rates(db) -> None:
    if not _table_exists(db, "plant_material_rates"):
        return
    count = _count_table(db, "plant_material_rates")
    if count > 0:
        return
    now = _now_ts()
    for material_key, (rate, unit) in DEFAULT_MATERIAL_RATES.items():
        db.execute(
            "INSERT OR IGNORE INTO plant_material_rates(plant_id, material_key, rate_per_unit, unit, effective_from, created_at) "
            "VALUES(NULL,?,?,?,?,?)",
            (material_key, rate, unit, _today(), now),
        )


def _crusher_stock_key(plant_type: str, output_grade: str) -> str:
    prefix = "MSAND" if (plant_type or "").strip() == "M-Sand" else "CRUSHER"
    return f"{prefix}:{(output_grade or 'Other').strip()}"


def list_crusher_msand_plants(db) -> list[dict]:
    if not _table_exists(db, "plants"):
        return []
    sql = (
        "SELECT id, plant_id, plant_name, plant_type FROM plants "
        "WHERE status='Active' AND plant_type IN ('Crusher','M-Sand') ORDER BY plant_name"
    )
    return [dict(r) for r in db.execute(sql).fetchall()]


def _output_grades_for_plant_type(plant_type: str) -> tuple[str, ...]:
    if (plant_type or "").strip() == "M-Sand":
        return MSAND_GRADES
    return CRUSHER_OUTPUT_GRADES


# --- Crusher / M-Sand Production ---
def list_crusher_production(db, plant_id: int | None = None, search: str = "") -> list[dict]:
    if not _table_exists(db, "crusher_production"):
        return []
    sql = (
        "SELECT c.*, pl.plant_name, pl.plant_id AS plant_code, pl.plant_type "
        "FROM crusher_production c "
        "JOIN plants pl ON c.plant_id = pl.id WHERE 1=1 "
    )
    params: list[Any] = []
    if plant_id:
        sql += "AND c.plant_id=? "
        params.append(plant_id)
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (c.output_grade LIKE ? OR c.operator LIKE ?) "
        params.extend([q, q])
    sql += "ORDER BY c.production_date DESC, c.id DESC LIMIT 500"
    result = []
    for row in db.execute(sql, tuple(params)).fetchall():
        item = dict(row)
        item["consumption"] = _parse_consumption_json(item.get("consumption_json"))
        result.append(item)
    return result


def get_crusher_production(db, record_id: int) -> dict | None:
    if not _table_exists(db, "crusher_production"):
        return None
    row = db.execute(
        "SELECT c.*, pl.plant_name, pl.plant_id AS plant_code, pl.plant_type "
        "FROM crusher_production c "
        "JOIN plants pl ON c.plant_id = pl.id WHERE c.id=?",
        (record_id,),
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["consumption"] = _parse_consumption_json(item.get("consumption_json"))
    return item


def save_crusher_production(db, form, username: str, record_id: int | None = None) -> int:
    plant_id = form.get("plant_id")
    if not plant_id:
        raise ValueError("Plant is required.")
    plant_id = int(plant_id)
    plant = get_plant(db, plant_id)
    if not plant:
        raise ValueError("Plant not found.")
    plant_type = plant.get("plant_type") or "Crusher"
    if plant_type not in ("Crusher", "M-Sand"):
        raise ValueError("Selected plant must be Crusher or M-Sand type.")
    prod_date = (form.get("production_date") or _today()).strip()
    output_grade = (form.get("output_grade") or "Other").strip()
    allowed = _output_grades_for_plant_type(plant_type)
    if output_grade not in allowed:
        output_grade = "Other"
    qty = _safe_float(form.get("qty_ton"))
    if qty <= 0:
        raise ValueError("Production quantity (ton) must be greater than zero.")
    stock_key = _crusher_stock_key(plant_type, output_grade)
    consumption_json = _build_material_consumption_json(
        form,
        CRUSHER_CONSUMPTION_MATERIALS,
        {"diesel": STOCK_UNIT_LITER, "power_kwh": "kWh"},
    )
    now = _now_ts()
    fields = (
        prod_date, plant_id, output_grade, qty,
        (form.get("shift") or "Day").strip(),
        (form.get("operator") or "").strip(),
        consumption_json,
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_crusher_production(db, record_id)
        if not existing:
            raise ValueError("Production record not found.")
        old_plant = int(existing["plant_id"])
        old_type = existing.get("plant_type") or "Crusher"
        old_key = _crusher_stock_key(old_type, existing.get("output_grade") or "Other")
        old_qty = float(existing.get("qty_ton") or 0)
        if old_plant != plant_id or old_key != stock_key:
            _apply_stock_delta(db, old_plant, old_key, production_delta=-old_qty)
            _apply_stock_delta(db, plant_id, stock_key, production_delta=qty)
        else:
            _apply_stock_delta(db, plant_id, stock_key, production_delta=qty - old_qty)
        db.execute(
            "UPDATE crusher_production SET production_date=?, plant_id=?, output_grade=?, qty_ton=?, "
            "shift=?, operator=?, consumption_json=?, remarks=?, modified_at=? WHERE id=?",
            (*fields, now, record_id),
        )
        return record_id
    _apply_stock_delta(db, plant_id, stock_key, production_delta=qty)
    db.execute(
        "INSERT INTO crusher_production(production_date, plant_id, output_grade, qty_ton, shift, "
        "operator, consumption_json, remarks, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (*fields, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_crusher_production(db, record_id: int) -> None:
    existing = get_crusher_production(db, record_id)
    if not existing:
        return
    plant_id = int(existing["plant_id"])
    stock_key = _crusher_stock_key(
        existing.get("plant_type") or "Crusher",
        existing.get("output_grade") or "Other",
    )
    qty = float(existing.get("qty_ton") or 0)
    _apply_stock_delta(db, plant_id, stock_key, production_delta=-qty)
    db.execute("DELETE FROM crusher_production WHERE id=?", (record_id,))


# --- Plant QC ---
def list_plant_qc(db, plant_id: int | None = None, search: str = "") -> list[dict]:
    if not _table_exists(db, "plant_qc_records"):
        return []
    sql = (
        "SELECT q.*, pl.plant_name, pl.plant_id AS plant_code "
        "FROM plant_qc_records q "
        "JOIN plants pl ON q.plant_id = pl.id WHERE 1=1 "
    )
    params: list[Any] = []
    if plant_id:
        sql += "AND q.plant_id=? "
        params.append(plant_id)
    if search.strip():
        qterm = f"%{search.strip()}%"
        sql += "AND (q.sample_id LIKE ? OR q.test_type LIKE ? OR q.tested_by LIKE ?) "
        params.extend([qterm, qterm, qterm])
    sql += "ORDER BY q.qc_date DESC, q.id DESC LIMIT 500"
    return [dict(r) for r in db.execute(sql, tuple(params)).fetchall()]


def get_plant_qc(db, record_id: int) -> dict | None:
    if not _table_exists(db, "plant_qc_records"):
        return None
    row = db.execute(
        "SELECT q.*, pl.plant_name, pl.plant_id AS plant_code "
        "FROM plant_qc_records q "
        "JOIN plants pl ON q.plant_id = pl.id WHERE q.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_plant_qc(db, form, username: str, record_id: int | None = None) -> int:
    plant_id = form.get("plant_id")
    if not plant_id:
        raise ValueError("Plant is required.")
    plant_id = int(plant_id)
    qc_date = (form.get("qc_date") or _today()).strip()
    source_module = (form.get("source_module") or "General").strip()
    if source_module not in QC_SOURCE_MODULES:
        source_module = "General"
    test_type = (form.get("test_type") or "Other").strip()
    pass_fail = (form.get("pass_fail") or "Pending").strip()
    if pass_fail not in QC_PASS_FAIL:
        pass_fail = "Pending"
    rv_raw = form.get("result_value")
    result_value = _safe_float(rv_raw) if rv_raw not in (None, "") else None
    now = _now_ts()
    fields = (
        qc_date, plant_id,
        (form.get("sample_id") or "").strip(),
        source_module, test_type,
        result_value,
        (form.get("result_unit") or "").strip(),
        pass_fail,
        (form.get("tested_by") or "").strip(),
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_plant_qc(db, record_id)
        if not existing:
            raise ValueError("QC record not found.")
        sample_id = fields[2] or existing.get("sample_id")
        if not sample_id:
            sample_id = _next_doc_number(db, "QC", "plant_qc_records", "sample_id")
        db.execute(
            "UPDATE plant_qc_records SET qc_date=?, plant_id=?, sample_id=?, source_module=?, "
            "test_type=?, result_value=?, result_unit=?, pass_fail=?, tested_by=?, remarks=?, "
            "modified_at=? WHERE id=?",
            (fields[0], fields[1], sample_id, *fields[3:], now, record_id),
        )
        return record_id
    sample_id = fields[2] or _next_doc_number(db, "QC", "plant_qc_records", "sample_id")
    db.execute(
        "INSERT INTO plant_qc_records(qc_date, plant_id, sample_id, source_module, test_type, "
        "result_value, result_unit, pass_fail, tested_by, remarks, created_by, created_at, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (fields[0], fields[1], sample_id, *fields[3:], username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_plant_qc(db, record_id: int) -> None:
    db.execute("DELETE FROM plant_qc_records WHERE id=?", (record_id,))


# --- Maintenance Job Cards ---
def list_maintenance_jobs(db, plant_id: int | None = None, search: str = "") -> list[dict]:
    if not _table_exists(db, "plant_maintenance_jobs"):
        return []
    sql = (
        "SELECT m.*, pl.plant_name, pl.plant_id AS plant_code "
        "FROM plant_maintenance_jobs m "
        "JOIN plants pl ON m.plant_id = pl.id WHERE 1=1 "
    )
    params: list[Any] = []
    if plant_id:
        sql += "AND m.plant_id=? "
        params.append(plant_id)
    if search.strip():
        q = f"%{search.strip()}%"
        sql += "AND (m.job_number LIKE ? OR m.equipment_name LIKE ? OR m.assigned_to LIKE ?) "
        params.extend([q, q, q])
    sql += "ORDER BY m.job_date DESC, m.id DESC LIMIT 500"
    return [dict(r) for r in db.execute(sql, tuple(params)).fetchall()]


def get_maintenance_job(db, record_id: int) -> dict | None:
    if not _table_exists(db, "plant_maintenance_jobs"):
        return None
    row = db.execute(
        "SELECT m.*, pl.plant_name, pl.plant_id AS plant_code "
        "FROM plant_maintenance_jobs m "
        "JOIN plants pl ON m.plant_id = pl.id WHERE m.id=?",
        (record_id,),
    ).fetchone()
    return dict(row) if row else None


def save_maintenance_job(db, form, username: str, record_id: int | None = None) -> int:
    plant_id = form.get("plant_id")
    if not plant_id:
        raise ValueError("Plant is required.")
    plant_id = int(plant_id)
    job_date = (form.get("job_date") or _today()).strip()
    job_type = (form.get("job_type") or "Preventive").strip()
    if job_type not in MAINTENANCE_JOB_TYPES:
        job_type = "Preventive"
    status = (form.get("status") or "Open").strip()
    if status not in MAINTENANCE_STATUSES:
        status = "Open"
    equipment = (form.get("equipment_name") or "").strip()
    if not equipment:
        raise ValueError("Equipment name is required.")
    now = _now_ts()
    completed_date = (form.get("completed_date") or "").strip() or None
    if status == "Completed" and not completed_date:
        completed_date = _today()
    fields = (
        job_date, plant_id, equipment, job_type, status,
        (form.get("description") or "").strip(),
        _safe_float(form.get("downtime_hours")),
        _safe_float(form.get("cost")),
        (form.get("assigned_to") or "").strip(),
        completed_date,
        (form.get("remarks") or "").strip(),
    )
    if record_id:
        existing = get_maintenance_job(db, record_id)
        if not existing:
            raise ValueError("Maintenance job not found.")
        db.execute(
            "UPDATE plant_maintenance_jobs SET job_date=?, plant_id=?, equipment_name=?, job_type=?, "
            "status=?, description=?, downtime_hours=?, cost=?, assigned_to=?, completed_date=?, "
            "remarks=?, modified_at=? WHERE id=?",
            (*fields, now, record_id),
        )
        return record_id
    job_number = _next_doc_number(db, "MNT", "plant_maintenance_jobs", "job_number")
    db.execute(
        "INSERT INTO plant_maintenance_jobs(job_number, job_date, plant_id, equipment_name, job_type, "
        "status, description, downtime_hours, cost, assigned_to, completed_date, remarks, "
        "created_by, created_at, modified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (job_number, *fields, username, now, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_maintenance_job(db, record_id: int) -> None:
    db.execute("DELETE FROM plant_maintenance_jobs WHERE id=?", (record_id,))


def get_material_rate(db, plant_id: int | None, material_key: str) -> float:
    if not _table_exists(db, "plant_material_rates"):
        return DEFAULT_MATERIAL_RATES.get(material_key, (0.0, ""))[0]
    if plant_id:
        row = db.execute(
            "SELECT rate_per_unit FROM plant_material_rates WHERE plant_id=? AND material_key=?",
            (plant_id, material_key),
        ).fetchone()
        if row:
            return float(row[0] or 0)
    row = db.execute(
        "SELECT rate_per_unit FROM plant_material_rates WHERE plant_id IS NULL AND material_key=?",
        (material_key,),
    ).fetchone()
    if row:
        return float(row[0] or 0)
    return DEFAULT_MATERIAL_RATES.get(material_key, (0.0, ""))[0]


def _consumption_cost(db, plant_id: int, consumption: list[dict[str, Any]]) -> float:
    total = 0.0
    for item in consumption:
        mat = (item.get("material") or "").strip()
        qty = float(item.get("qty") or 0)
        if qty <= 0 or not mat:
            continue
        rate = get_material_rate(db, plant_id, mat)
        total += qty * rate
    return total


def plant_costing_summary(
    db,
    date_from: str,
    date_to: str,
    plant_id: int | None = None,
) -> dict[str, Any]:
    """Aggregate production output and estimated material cost for a date range."""
    lines: list[dict[str, Any]] = []
    total_output_qty = 0.0
    total_material_cost = 0.0

    def _add_line(
        module: str,
        prod_date: str,
        pid: int,
        plant_name: str,
        output_label: str,
        output_qty: float,
        output_unit: str,
        consumption: list[dict[str, Any]],
    ) -> None:
        nonlocal total_output_qty, total_material_cost
        if plant_id and pid != plant_id:
            return
        if prod_date < date_from or prod_date > date_to:
            return
        mat_cost = _consumption_cost(db, pid, consumption)
        total_output_qty += output_qty
        total_material_cost += mat_cost
        lines.append({
            "module": module,
            "date": prod_date,
            "plant_id": pid,
            "plant_name": plant_name,
            "output": output_label,
            "output_qty": output_qty,
            "output_unit": output_unit,
            "material_cost": mat_cost,
            "cost_per_unit": (mat_cost / output_qty) if output_qty > 0 else 0.0,
        })

    if _table_exists(db, "asphalt_production"):
        sql = (
            "SELECT a.production_date, a.plant_id, a.mix_type, a.qty_ton, a.consumption_json, pl.plant_name "
            "FROM asphalt_production a JOIN plants pl ON a.plant_id=pl.id "
            "WHERE a.production_date BETWEEN ? AND ?"
        )
        params: tuple = (date_from, date_to)
        if plant_id:
            sql += " AND a.plant_id=?"
            params = (date_from, date_to, plant_id)
        for row in db.execute(sql, params).fetchall():
            r = dict(row)
            _add_line(
                "Asphalt", r["production_date"], int(r["plant_id"]), r["plant_name"],
                r.get("mix_type") or "Mix", float(r.get("qty_ton") or 0), STOCK_UNIT_TON,
                _parse_consumption_json(r.get("consumption_json")),
            )

    for table, module, qty_col, unit, label_col in (
        ("rmc_production", "RMC", "qty_m3", STOCK_UNIT_M3, "grade"),
        ("wetmix_production", "Wet Mix", "qty", STOCK_UNIT_TON, "material_mix"),
        ("crusher_production", "Crusher/M-Sand", "qty_ton", STOCK_UNIT_TON, "output_grade"),
    ):
        if not _table_exists(db, table):
            continue
        sql = (
            f"SELECT t.production_date, t.plant_id, t.{label_col}, t.{qty_col}, t.consumption_json, pl.plant_name "
            f"FROM {table} t JOIN plants pl ON t.plant_id=pl.id "
            "WHERE t.production_date BETWEEN ? AND ?"
        )
        params = (date_from, date_to)
        if plant_id:
            sql += " AND t.plant_id=?"
            params = (date_from, date_to, plant_id)
        for row in db.execute(sql, params).fetchall():
            r = dict(row)
            _add_line(
                module, r["production_date"], int(r["plant_id"]), r["plant_name"],
                r.get(label_col) or module, float(r.get(qty_col) or 0), unit,
                _parse_consumption_json(r.get("consumption_json")),
            )

    lines.sort(key=lambda x: (x["date"], x["plant_name"]), reverse=True)
    return {
        "lines": lines,
        "total_lines": len(lines),
        "total_output_qty": total_output_qty,
        "total_material_cost": total_material_cost,
        "avg_cost_per_unit": (total_material_cost / total_output_qty) if total_output_qty > 0 else 0.0,
    }


def get_plant_360(db, plant_id: int) -> dict[str, Any] | None:
    plant = get_plant(db, plant_id)
    if not plant:
        return None
    today = _today()
    month_start = datetime.now().strftime("%Y-%m-01")
    stock = list_plant_stock(db, plant_id)
    qc_recent = list_plant_qc(db, plant_id)[:5]
    maint_open = [
        j for j in list_maintenance_jobs(db, plant_id)
        if j.get("status") in ("Open", "In Progress")
    ][:5]
    costing_month = plant_costing_summary(db, month_start, today, plant_id)

    def _sum_prod(table: str, qty_col: str, date_col: str = "production_date") -> float:
        if not _table_exists(db, table):
            return 0.0
        row = db.execute(
            f"SELECT COALESCE(SUM({qty_col}),0) FROM {table} WHERE plant_id=? AND {date_col}=?",
            (plant_id, today),
        ).fetchone()
        return float(row[0] or 0)

    production_today = {
        "asphalt_ton": _sum_prod("asphalt_production", "qty_ton"),
        "rmc_m3": _sum_prod("rmc_production", "qty_m3"),
        "wetmix_ton": _sum_prod("wetmix_production", "qty"),
        "crusher_ton": _sum_prod("crusher_production", "qty_ton"),
        "precast_nos": _sum_prod("precast_production", "qty", "casting_date"),
    }
    return {
        "plant": plant,
        "stock": stock,
        "qc_recent": qc_recent,
        "maintenance_open": maint_open,
        "costing_month": costing_month,
        "production_today": production_today,
    }
