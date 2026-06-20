"""Project Cost Planning, WBS, Micro Planning, and DPR monitoring helpers."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

DEFAULT_COST_ACTIVITIES = (
    "Excavation",
    "PCC",
    "Steel Fixing",
    "Shuttering",
    "Concreting",
    "Slab Work",
    "Plastering",
    "Block Work",
    "Waterproofing",
    "Finishing",
)

MICRO_PLAN_PERIODS = ("Daily", "Weekly", "Monthly")

COST_PLAN_REPORTS = (
    ("project_cost", "Project Cost Report"),
    ("boq_cost", "BOQ Cost Report"),
    ("material_planning", "Material Planning Report"),
    ("labour_planning", "Labour Planning Report"),
    ("equipment_planning", "Equipment Planning Report"),
    ("wbs", "WBS Report"),
    ("micro_planning", "Micro Planning Report"),
    ("planned_vs_actual", "Planned vs Actual Report"),
    ("cost_variance", "Cost Variance Report"),
    ("productivity", "Productivity Report"),
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
    cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def ensure_cost_planning_tables(db) -> None:
    """Create cost planning schema (idempotent)."""
    _ensure_column(db, "projects", "project_code", "TEXT")

    db.execute("""
        CREATE TABLE IF NOT EXISTS cost_plans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            boq_master_id INTEGER NOT NULL,
            boq_item_id INTEGER NOT NULL UNIQUE,
            boq_quantity REAL DEFAULT 0,
            boq_unit TEXT,
            plan_status TEXT DEFAULT 'Draft',
            approval_status TEXT DEFAULT 'Pending Checker',
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(boq_master_id) REFERENCES boq_master(id),
            FOREIGN KEY(boq_item_id) REFERENCES boq_items(id)
        )
    """)
    for column, col_type in (
        ("project_id", "INTEGER"),
        ("boq_master_id", "INTEGER"),
        ("boq_item_id", "INTEGER"),
        ("boq_quantity", "REAL DEFAULT 0"),
        ("boq_unit", "TEXT"),
        ("plan_status", "TEXT DEFAULT 'Draft'"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
        ("remarks", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "cost_plans", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS cost_plan_activities(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cost_plan_id INTEGER NOT NULL,
            boq_item_id INTEGER NOT NULL,
            activity_name TEXT NOT NULL,
            activity_unit TEXT,
            planned_qty REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            FOREIGN KEY(cost_plan_id) REFERENCES cost_plans(id) ON DELETE CASCADE,
            FOREIGN KEY(boq_item_id) REFERENCES boq_items(id)
        )
    """)
    for column, col_type in (
        ("cost_plan_id", "INTEGER"),
        ("boq_item_id", "INTEGER"),
        ("activity_name", "TEXT"),
        ("activity_unit", "TEXT"),
        ("planned_qty", "REAL DEFAULT 0"),
        ("sort_order", "INTEGER DEFAULT 0"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "cost_plan_activities", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS cost_plan_materials(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cost_plan_id INTEGER NOT NULL,
            activity_id INTEGER,
            material_name TEXT NOT NULL,
            material_unit TEXT,
            consumption_factor REAL DEFAULT 0,
            rate REAL DEFAULT 0,
            planned_qty REAL DEFAULT 0,
            planned_amount REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY(cost_plan_id) REFERENCES cost_plans(id) ON DELETE CASCADE,
            FOREIGN KEY(activity_id) REFERENCES cost_plan_activities(id) ON DELETE SET NULL
        )
    """)
    for column, col_type in (
        ("cost_plan_id", "INTEGER"),
        ("activity_id", "INTEGER"),
        ("material_name", "TEXT"),
        ("material_unit", "TEXT"),
        ("consumption_factor", "REAL DEFAULT 0"),
        ("rate", "REAL DEFAULT 0"),
        ("planned_qty", "REAL DEFAULT 0"),
        ("planned_amount", "REAL DEFAULT 0"),
        ("sort_order", "INTEGER DEFAULT 0"),
    ):
        _ensure_column(db, "cost_plan_materials", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS cost_plan_manpower(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cost_plan_id INTEGER NOT NULL,
            activity_id INTEGER,
            trade_name TEXT NOT NULL,
            planned_manpower REAL DEFAULT 0,
            hours_per_unit REAL DEFAULT 0,
            labour_rate REAL DEFAULT 0,
            planned_hours REAL DEFAULT 0,
            planned_amount REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY(cost_plan_id) REFERENCES cost_plans(id) ON DELETE CASCADE,
            FOREIGN KEY(activity_id) REFERENCES cost_plan_activities(id) ON DELETE SET NULL
        )
    """)
    for column, col_type in (
        ("cost_plan_id", "INTEGER"),
        ("activity_id", "INTEGER"),
        ("trade_name", "TEXT"),
        ("planned_manpower", "REAL DEFAULT 0"),
        ("hours_per_unit", "REAL DEFAULT 0"),
        ("labour_rate", "REAL DEFAULT 0"),
        ("planned_hours", "REAL DEFAULT 0"),
        ("planned_amount", "REAL DEFAULT 0"),
        ("sort_order", "INTEGER DEFAULT 0"),
    ):
        _ensure_column(db, "cost_plan_manpower", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS cost_plan_machinery(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cost_plan_id INTEGER NOT NULL,
            activity_id INTEGER,
            equipment_type TEXT NOT NULL,
            equipment_id INTEGER,
            hours_per_unit REAL DEFAULT 0,
            hourly_rate REAL DEFAULT 0,
            planned_hours REAL DEFAULT 0,
            planned_amount REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY(cost_plan_id) REFERENCES cost_plans(id) ON DELETE CASCADE,
            FOREIGN KEY(activity_id) REFERENCES cost_plan_activities(id) ON DELETE SET NULL
        )
    """)
    for column, col_type in (
        ("cost_plan_id", "INTEGER"),
        ("activity_id", "INTEGER"),
        ("equipment_type", "TEXT"),
        ("equipment_id", "INTEGER"),
        ("hours_per_unit", "REAL DEFAULT 0"),
        ("hourly_rate", "REAL DEFAULT 0"),
        ("planned_hours", "REAL DEFAULT 0"),
        ("planned_amount", "REAL DEFAULT 0"),
        ("sort_order", "INTEGER DEFAULT 0"),
    ):
        _ensure_column(db, "cost_plan_machinery", column, col_type)

    db.execute("""
        CREATE TABLE IF NOT EXISTS micro_plan_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cost_plan_id INTEGER NOT NULL,
            activity_id INTEGER,
            project_id INTEGER NOT NULL,
            plan_period TEXT DEFAULT 'Daily',
            plan_date TEXT NOT NULL,
            planned_qty REAL DEFAULT 0,
            planned_manpower REAL DEFAULT 0,
            planned_equipment TEXT,
            planned_material TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            FOREIGN KEY(cost_plan_id) REFERENCES cost_plans(id) ON DELETE CASCADE,
            FOREIGN KEY(activity_id) REFERENCES cost_plan_activities(id) ON DELETE SET NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for column, col_type in (
        ("cost_plan_id", "INTEGER"),
        ("activity_id", "INTEGER"),
        ("project_id", "INTEGER"),
        ("plan_period", "TEXT DEFAULT 'Daily'"),
        ("plan_date", "TEXT"),
        ("planned_qty", "REAL DEFAULT 0"),
        ("planned_manpower", "REAL DEFAULT 0"),
        ("planned_equipment", "TEXT"),
        ("planned_material", "TEXT"),
        ("remarks", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "micro_plan_entries", column, col_type)

    try:
        db.commit()
    except sqlite3.Error:
        pass


def prepare_cost_planning_db(db) -> None:
    ensure_cost_planning_tables(db)


def get_boq_item_context(db, boq_item_id: int) -> dict | None:
    row = db.execute(
        "SELECT bi.id, bi.boq_id, bi.project_id, bi.line_no, bi.item_code, "
        "bi.item_description, bi.quantity, bi.unit, bi.rate, bi.amount, "
        "COALESCE(bm.boq_number, '') AS boq_number, "
        "COALESCE(p.project_code, '') AS project_code, "
        "COALESCE(p.project_name, '') AS project_name "
        "FROM boq_items bi "
        "LEFT JOIN boq_master bm ON bi.boq_id = bm.id "
        "LEFT JOIN projects p ON COALESCE(bi.project_id, bm.project_id) = p.id "
        "WHERE bi.id=? AND COALESCE(bi.is_deleted, 0)=0",
        (boq_item_id,),
    ).fetchone()
    if not row:
        return None
    return dict(row)


def calc_material_line(boq_qty: float, consumption_factor: float, rate: float) -> tuple[float, float]:
    planned_qty = round(boq_qty * consumption_factor, 4)
    planned_amount = round(planned_qty * rate, 2)
    return planned_qty, planned_amount


def calc_manpower_line(boq_qty: float, hours_per_unit: float, labour_rate: float) -> tuple[float, float]:
    planned_hours = round(boq_qty * hours_per_unit, 4)
    planned_amount = round(planned_hours * labour_rate, 2)
    return planned_hours, planned_amount


def calc_machinery_line(boq_qty: float, hours_per_unit: float, hourly_rate: float) -> tuple[float, float]:
    planned_hours = round(boq_qty * hours_per_unit, 4)
    planned_amount = round(planned_hours * hourly_rate, 2)
    return planned_hours, planned_amount


def _parse_measurement_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _activity_name_matches(stored: str, target: str) -> bool:
    if not target:
        return True
    a = (stored or "").strip().lower()
    b = target.strip().lower()
    return a == b or b in a or a in b


def aggregate_dpr_actuals(db, boq_item_id: int, activity_name: str | None = None) -> dict:
    """Pull actual qty, manpower, equipment, materials from DPR (no duplicate entry)."""
    measurements = db.execute(
        "SELECT id, calculated_quantity, measurement_data, report_date "
        "FROM dpr_measurements "
        "WHERE boq_item_id=? AND COALESCE(dpr_status, 'submitted') != 'draft'",
        (boq_item_id,),
    ).fetchall()

    actual_qty = 0.0
    manpower_hours = 0.0
    manpower_headcount = 0
    equipment_hours = 0.0
    equipment_cost = 0.0
    material_qty_map: dict[str, float] = {}
    activity_qty_map: dict[str, float] = {}

    for measurement in measurements:
        m_id = measurement["id"]
        qty = _safe_float(measurement["calculated_quantity"])
        if activity_name:
            data = _parse_measurement_json(measurement["measurement_data"])
            acts = data.get("activities") or []
            matched = False
            for act in acts:
                if not isinstance(act, dict):
                    continue
                name = act.get("activity_name") or act.get("name") or ""
                if _activity_name_matches(name, activity_name):
                    matched = True
                    act_qty = _safe_float(act.get("quantity") or act.get("qty"))
                    activity_qty_map[name] = activity_qty_map.get(name, 0.0) + act_qty
            if matched:
                actual_qty += qty
        else:
            actual_qty += qty

        mp_rows = db.execute(
            "SELECT hours_worked FROM dpr_manpower WHERE measurement_id=?",
            (m_id,),
        ).fetchall()
        for mp in mp_rows:
            manpower_hours += _safe_float(mp["hours_worked"])
            manpower_headcount += 1

        data = _parse_measurement_json(measurement["measurement_data"])
        for eq in data.get("equipment") or []:
            if not isinstance(eq, dict):
                continue
            equipment_hours += _safe_float(eq.get("hours_used") or eq.get("worked_units"))
            equipment_cost += _safe_float(eq.get("amount"))

        for mat in data.get("materials") or []:
            if not isinstance(mat, dict):
                continue
            name = (mat.get("material_name") or mat.get("name") or "Material").strip()
            material_qty_map[name] = material_qty_map.get(name, 0.0) + _safe_float(
                mat.get("quantity") or mat.get("qty")
            )

        for act in data.get("activities") or []:
            if not isinstance(act, dict):
                continue
            name = (act.get("activity_name") or act.get("name") or "").strip()
            if not name:
                continue
            if activity_name and not _activity_name_matches(name, activity_name):
                continue
            activity_qty_map[name] = activity_qty_map.get(name, 0.0) + _safe_float(
                act.get("quantity") or act.get("qty")
            )

    boq_row = db.execute(
        "SELECT quantity FROM boq_items WHERE id=?",
        (boq_item_id,),
    ).fetchone()
    boq_qty = _safe_float(boq_row["quantity"] if boq_row else 0)
    progress_pct = round((actual_qty / boq_qty) * 100, 2) if boq_qty > 0 else 0.0

    return {
        "boq_item_id": boq_item_id,
        "activity_name": activity_name,
        "actual_quantity": round(actual_qty, 4),
        "actual_manpower_hours": round(manpower_hours, 2),
        "actual_manpower_headcount": manpower_headcount,
        "actual_equipment_hours": round(equipment_hours, 2),
        "actual_equipment_cost": round(equipment_cost, 2),
        "actual_materials": [
            {"material_name": k, "quantity": round(v, 4)} for k, v in sorted(material_qty_map.items())
        ],
        "actual_activities": [
            {"activity_name": k, "quantity": round(v, 4)} for k, v in sorted(activity_qty_map.items())
        ],
        "actual_progress_percent": progress_pct,
        "boq_quantity": round(boq_qty, 4),
    }


def sum_planned_totals(db, cost_plan_id: int) -> dict:
    mat = db.execute(
        "SELECT COALESCE(SUM(planned_amount), 0) AS total, COALESCE(SUM(planned_qty), 0) AS qty "
        "FROM cost_plan_materials WHERE cost_plan_id=?",
        (cost_plan_id,),
    ).fetchone()
    mp = db.execute(
        "SELECT COALESCE(SUM(planned_amount), 0) AS total, COALESCE(SUM(planned_hours), 0) AS hrs "
        "FROM cost_plan_manpower WHERE cost_plan_id=?",
        (cost_plan_id,),
    ).fetchone()
    mach = db.execute(
        "SELECT COALESCE(SUM(planned_amount), 0) AS total, COALESCE(SUM(planned_hours), 0) AS hrs "
        "FROM cost_plan_machinery WHERE cost_plan_id=?",
        (cost_plan_id,),
    ).fetchone()
    material_cost = _safe_float(mat["total"] if mat else 0)
    labour_cost = _safe_float(mp["total"] if mp else 0)
    machinery_cost = _safe_float(mach["total"] if mach else 0)
    total = round(material_cost + labour_cost + machinery_cost, 2)
    return {
        "material_cost": round(material_cost, 2),
        "labour_cost": round(labour_cost, 2),
        "machinery_cost": round(machinery_cost, 2),
        "total_planned_cost": total,
        "material_qty": round(_safe_float(mat["qty"] if mat else 0), 4),
        "labour_hours": round(_safe_float(mp["hrs"] if mp else 0), 2),
        "machinery_hours": round(_safe_float(mach["hrs"] if mach else 0), 2),
    }


def build_monitoring_row(db, plan_row: dict) -> dict:
    plan_id = plan_row["id"]
    boq_item_id = plan_row["boq_item_id"]
    boq_qty = _safe_float(plan_row.get("boq_quantity"))
    planned = sum_planned_totals(db, plan_id)
    actuals = aggregate_dpr_actuals(db, boq_item_id)
    actual_qty = actuals["actual_quantity"]
    actual_cost = round(
        actuals["actual_equipment_cost"]
        + (actuals["actual_manpower_hours"] * 0),  # labour cost from DPR not stored — use hours only
        2,
    )
    planned_progress = 100.0 if boq_qty <= 0 else round(
        min((planned["material_qty"] / boq_qty) * 100, 100), 2
    )
    actual_progress = actuals["actual_progress_percent"]
    labour_rate_proxy = (
        planned["labour_cost"] / planned["labour_hours"] if planned["labour_hours"] > 0 else 0
    )
    actual_labour_cost = round(actuals["actual_manpower_hours"] * labour_rate_proxy, 2)
    actual_cost = round(actual_labour_cost + actuals["actual_equipment_cost"], 2)

    return {
        **plan_row,
        **planned,
        **actuals,
        "actual_cost": actual_cost,
        "planned_quantity": boq_qty,
        "qty_variance": round(actual_qty - boq_qty, 4),
        "cost_variance": round(actual_cost - planned["total_planned_cost"], 2),
        "material_variance": round(actual_cost - planned["material_cost"], 2),
        "labour_variance": round(actual_labour_cost - planned["labour_cost"], 2),
        "machinery_variance": round(
            actuals["actual_equipment_cost"] - planned["machinery_cost"], 2
        ),
        "planned_progress_percent": planned_progress,
        "progress_variance": round(actual_progress - planned_progress, 2),
        "labour_productivity": round(
            (actual_qty / actuals["actual_manpower_hours"]) if actuals["actual_manpower_hours"] > 0 else 0,
            4,
        ),
        "machine_productivity": round(
            (actual_qty / actuals["actual_equipment_hours"])
            if actuals["actual_equipment_hours"] > 0
            else 0,
            4,
        ),
    }


def get_cost_plan_dashboard(db, project_id: int | None) -> dict:
    if not project_id:
        return {
            "plan_count": 0,
            "total_planned_cost": 0.0,
            "total_actual_cost": 0.0,
            "cost_variance": 0.0,
            "avg_planned_progress": 0.0,
            "avg_actual_progress": 0.0,
            "delayed_activities": 0,
        }

    plans = db.execute(
        "SELECT cp.*, bi.item_description, bi.item_code, bm.boq_number "
        "FROM cost_plans cp "
        "JOIN boq_items bi ON cp.boq_item_id = bi.id "
        "LEFT JOIN boq_master bm ON cp.boq_master_id = bm.id "
        "WHERE cp.project_id=? ORDER BY cp.id DESC",
        (project_id,),
    ).fetchall()

    total_planned = 0.0
    total_actual = 0.0
    planned_progress_sum = 0.0
    actual_progress_sum = 0.0
    delayed = 0

    for plan in plans:
        row = build_monitoring_row(db, dict(plan))
        total_planned += row["total_planned_cost"]
        total_actual += row["actual_cost"]
        planned_progress_sum += row["planned_progress_percent"]
        actual_progress_sum += row["actual_progress_percent"]
        if row["actual_progress_percent"] < row["planned_progress_percent"] - 5:
            delayed += 1

    count = len(plans)
    return {
        "plan_count": count,
        "total_planned_cost": round(total_planned, 2),
        "total_actual_cost": round(total_actual, 2),
        "cost_variance": round(total_actual - total_planned, 2),
        "avg_planned_progress": round(planned_progress_sum / count, 2) if count else 0.0,
        "avg_actual_progress": round(actual_progress_sum / count, 2) if count else 0.0,
        "delayed_activities": delayed,
    }


def build_wbs_tree(db, project_id: int) -> list[dict]:
    project = db.execute(
        "SELECT id, project_code, project_name FROM projects WHERE id=?",
        (project_id,),
    ).fetchone()
    if not project:
        return []

    boqs = db.execute(
        "SELECT id, boq_number FROM boq_master "
        "WHERE project_id=? AND COALESCE(is_deleted, 0)=0 ORDER BY id",
        (project_id,),
    ).fetchall()

    tree: list[dict] = [{
        "level": 1,
        "type": "project",
        "id": project["id"],
        "label": f"{project['project_code'] or project['id']} — {project['project_name']}",
        "children": [],
    }]

    for boq in boqs:
        boq_node = {
            "level": 2,
            "type": "boq",
            "id": boq["id"],
            "label": boq["boq_number"] or f"BOQ-{boq['id']}",
            "children": [],
        }
        items = db.execute(
            "SELECT bi.id, bi.item_code, bi.item_description, bi.quantity, bi.unit, cp.id AS cost_plan_id "
            "FROM boq_items bi "
            "LEFT JOIN cost_plans cp ON cp.boq_item_id = bi.id "
            "WHERE bi.boq_id=? AND COALESCE(bi.is_deleted, 0)=0 "
            "ORDER BY bi.line_no, bi.id",
            (boq["id"],),
        ).fetchall()

        for item in items:
            code = item["item_code"] or f"BOQ{item['id']}"
            item_node = {
                "level": 3,
                "type": "boq_item",
                "id": item["id"],
                "cost_plan_id": item["cost_plan_id"],
                "label": f"{code} — {item['item_description'] or 'Item'} ({item['quantity'] or 0} {item['unit'] or ''})",
                "children": [],
            }
            if item["cost_plan_id"]:
                activities = db.execute(
                    "SELECT id, activity_name, planned_qty, activity_unit "
                    "FROM cost_plan_activities WHERE cost_plan_id=? ORDER BY sort_order, id",
                    (item["cost_plan_id"],),
                ).fetchall()
                for act in activities:
                    actuals = aggregate_dpr_actuals(db, item["id"], act["activity_name"])
                    item_node["children"].append({
                        "level": 4,
                        "type": "activity",
                        "id": act["id"],
                        "label": act["activity_name"],
                        "planned_qty": act["planned_qty"],
                        "actual_qty": actuals["actual_quantity"],
                        "unit": act["activity_unit"] or item["unit"],
                    })
            boq_node["children"].append(item_node)
        tree[0]["children"].append(boq_node)

    return tree


def load_cost_plan_detail(db, cost_plan_id: int) -> dict | None:
    plan = db.execute(
        "SELECT cp.*, bi.item_description, bi.item_code, bi.rate, bi.amount, "
        "bm.boq_number, p.project_code, p.project_name "
        "FROM cost_plans cp "
        "JOIN boq_items bi ON cp.boq_item_id = bi.id "
        "LEFT JOIN boq_master bm ON cp.boq_master_id = bm.id "
        "LEFT JOIN projects p ON cp.project_id = p.id "
        "WHERE cp.id=?",
        (cost_plan_id,),
    ).fetchone()
    if not plan:
        return None

    plan_dict = dict(plan)
    plan_dict["materials"] = [
        dict(r) for r in db.execute(
            "SELECT * FROM cost_plan_materials WHERE cost_plan_id=? ORDER BY sort_order, id",
            (cost_plan_id,),
        ).fetchall()
    ]
    plan_dict["manpower"] = [
        dict(r) for r in db.execute(
            "SELECT * FROM cost_plan_manpower WHERE cost_plan_id=? ORDER BY sort_order, id",
            (cost_plan_id,),
        ).fetchall()
    ]
    plan_dict["machinery"] = [
        dict(r) for r in db.execute(
            "SELECT * FROM cost_plan_machinery WHERE cost_plan_id=? ORDER BY sort_order, id",
            (cost_plan_id,),
        ).fetchall()
    ]
    plan_dict["activities"] = [
        dict(r) for r in db.execute(
            "SELECT * FROM cost_plan_activities WHERE cost_plan_id=? ORDER BY sort_order, id",
            (cost_plan_id,),
        ).fetchall()
    ]
    plan_dict["micro_plans"] = [
        dict(r) for r in db.execute(
            "SELECT m.*, a.activity_name FROM micro_plan_entries m "
            "LEFT JOIN cost_plan_activities a ON m.activity_id = a.id "
            "WHERE m.cost_plan_id=? ORDER BY m.plan_date DESC, m.id DESC",
            (cost_plan_id,),
        ).fetchall()
    ]
    plan_dict["totals"] = sum_planned_totals(db, cost_plan_id)
    plan_dict["actuals"] = aggregate_dpr_actuals(db, plan_dict["boq_item_id"])
    plan_dict["monitoring"] = build_monitoring_row(db, plan_dict)
    return plan_dict


def _parse_activity_rows(form) -> list[dict]:
    names = form.getlist("activity_name[]")
    units = form.getlist("activity_unit[]")
    qtys = form.getlist("activity_planned_qty[]")
    rows = []
    for idx, name in enumerate(names):
        label = (name or "").strip()
        if not label:
            continue
        rows.append({
            "activity_name": label,
            "activity_unit": units[idx].strip() if idx < len(units) else "",
            "planned_qty": _safe_float(qtys[idx] if idx < len(qtys) else 0),
            "sort_order": idx,
        })
    return rows


def _parse_material_rows(form, boq_qty: float) -> list[dict]:
    names = form.getlist("material_name[]")
    units = form.getlist("material_unit[]")
    factors = form.getlist("consumption_factor[]")
    rates = form.getlist("material_rate[]")
    activity_ids = form.getlist("material_activity_id[]")
    rows = []
    for idx, name in enumerate(names):
        label = (name or "").strip()
        if not label:
            continue
        factor = _safe_float(factors[idx] if idx < len(factors) else 0)
        rate = _safe_float(rates[idx] if idx < len(rates) else 0)
        planned_qty, planned_amount = calc_material_line(boq_qty, factor, rate)
        act_id = activity_ids[idx].strip() if idx < len(activity_ids) else ""
        rows.append({
            "material_name": label,
            "material_unit": units[idx].strip() if idx < len(units) else "",
            "consumption_factor": factor,
            "rate": rate,
            "planned_qty": planned_qty,
            "planned_amount": planned_amount,
            "activity_id": int(act_id) if act_id.isdigit() else None,
            "sort_order": idx,
        })
    return rows


def _parse_manpower_rows(form, boq_qty: float) -> list[dict]:
    trades = form.getlist("trade_name[]")
    hours = form.getlist("hours_per_unit[]")
    rates = form.getlist("labour_rate[]")
    manpower = form.getlist("planned_manpower[]")
    activity_ids = form.getlist("manpower_activity_id[]")
    rows = []
    for idx, trade in enumerate(trades):
        label = (trade or "").strip()
        if not label:
            continue
        hpu = _safe_float(hours[idx] if idx < len(hours) else 0)
        rate = _safe_float(rates[idx] if idx < len(rates) else 0)
        planned_hours, planned_amount = calc_manpower_line(boq_qty, hpu, rate)
        act_id = activity_ids[idx].strip() if idx < len(activity_ids) else ""
        rows.append({
            "trade_name": label,
            "planned_manpower": _safe_float(manpower[idx] if idx < len(manpower) else 0),
            "hours_per_unit": hpu,
            "labour_rate": rate,
            "planned_hours": planned_hours,
            "planned_amount": planned_amount,
            "activity_id": int(act_id) if act_id.isdigit() else None,
            "sort_order": idx,
        })
    return rows


def _parse_machinery_rows(form, boq_qty: float) -> list[dict]:
    types = form.getlist("equipment_type[]")
    hours = form.getlist("machinery_hours_per_unit[]")
    rates = form.getlist("hourly_rate[]")
    equipment_ids = form.getlist("equipment_id[]")
    activity_ids = form.getlist("machinery_activity_id[]")
    rows = []
    for idx, eq_type in enumerate(types):
        label = (eq_type or "").strip()
        if not label:
            continue
        hpu = _safe_float(hours[idx] if idx < len(hours) else 0)
        rate = _safe_float(rates[idx] if idx < len(rates) else 0)
        planned_hours, planned_amount = calc_machinery_line(boq_qty, hpu, rate)
        eq_id_raw = equipment_ids[idx].strip() if idx < len(equipment_ids) else ""
        act_id = activity_ids[idx].strip() if idx < len(activity_ids) else ""
        rows.append({
            "equipment_type": label,
            "equipment_id": int(eq_id_raw) if eq_id_raw.isdigit() else None,
            "hours_per_unit": hpu,
            "hourly_rate": rate,
            "planned_hours": planned_hours,
            "planned_amount": planned_amount,
            "activity_id": int(act_id) if act_id.isdigit() else None,
            "sort_order": idx,
        })
    return rows


def save_cost_plan_from_form(db, form, username: str) -> tuple[int | None, str | None]:
    project_id = (form.get("project_id") or "").strip()
    boq_master_id = (form.get("boq_master_id") or "").strip()
    boq_item_id = (form.get("boq_item_id") or "").strip()
    cost_plan_id = (form.get("cost_plan_id") or "").strip()
    plan_status = (form.get("plan_status") or "Draft").strip()
    remarks = (form.get("remarks") or "").strip()

    if not project_id or not boq_master_id or not boq_item_id:
        return None, "Select project, BOQ, and BOQ item."

    ctx = get_boq_item_context(db, int(boq_item_id))
    if not ctx:
        return None, "BOQ item not found."

    boq_qty = _safe_float(ctx.get("quantity"))
    boq_unit = (ctx.get("unit") or "").strip()
    now = _now_ts()

    if cost_plan_id:
        existing = db.execute(
            "SELECT id FROM cost_plans WHERE id=?",
            (cost_plan_id,),
        ).fetchone()
        if not existing:
            return None, "Cost plan not found."
        db.execute(
            "UPDATE cost_plans SET project_id=?, boq_master_id=?, boq_item_id=?, "
            "boq_quantity=?, boq_unit=?, plan_status=?, remarks=?, modified_by=?, modified_at=? "
            "WHERE id=?",
            (
                project_id, boq_master_id, boq_item_id, boq_qty, boq_unit,
                plan_status, remarks, username, now, cost_plan_id,
            ),
        )
        plan_id = int(cost_plan_id)
        db.execute("DELETE FROM cost_plan_materials WHERE cost_plan_id=?", (plan_id,))
        db.execute("DELETE FROM cost_plan_manpower WHERE cost_plan_id=?", (plan_id,))
        db.execute("DELETE FROM cost_plan_machinery WHERE cost_plan_id=?", (plan_id,))
        db.execute("DELETE FROM cost_plan_activities WHERE cost_plan_id=?", (plan_id,))
    else:
        dup = db.execute(
            "SELECT id FROM cost_plans WHERE boq_item_id=?",
            (boq_item_id,),
        ).fetchone()
        if dup:
            return None, "Cost plan already exists for this BOQ item. Edit the existing plan."
        cur = db.execute(
            "INSERT INTO cost_plans(project_id, boq_master_id, boq_item_id, boq_quantity, boq_unit, "
            "plan_status, approval_status, remarks, created_by, created_at, modified_by, modified_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                project_id, boq_master_id, boq_item_id, boq_qty, boq_unit,
                plan_status, "Pending Checker", remarks, username, now, username, now,
            ),
        )
        plan_id = cur.lastrowid

    for act in _parse_activity_rows(form):
        db.execute(
            "INSERT INTO cost_plan_activities(cost_plan_id, boq_item_id, activity_name, activity_unit, "
            "planned_qty, sort_order, created_by, created_at, modified_by, modified_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                plan_id, boq_item_id, act["activity_name"], act["activity_unit"],
                act["planned_qty"], act["sort_order"], username, now, username, now,
            ),
        )

    for mat in _parse_material_rows(form, boq_qty):
        act_id = mat["activity_id"]
        db.execute(
            "INSERT INTO cost_plan_materials(cost_plan_id, activity_id, material_name, material_unit, "
            "consumption_factor, rate, planned_qty, planned_amount, sort_order) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (
                plan_id, act_id, mat["material_name"], mat["material_unit"],
                mat["consumption_factor"], mat["rate"], mat["planned_qty"],
                mat["planned_amount"], mat["sort_order"],
            ),
        )

    for mp in _parse_manpower_rows(form, boq_qty):
        db.execute(
            "INSERT INTO cost_plan_manpower(cost_plan_id, activity_id, trade_name, planned_manpower, "
            "hours_per_unit, labour_rate, planned_hours, planned_amount, sort_order) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (
                plan_id, mp["activity_id"], mp["trade_name"], mp["planned_manpower"],
                mp["hours_per_unit"], mp["labour_rate"], mp["planned_hours"],
                mp["planned_amount"], mp["sort_order"],
            ),
        )

    for mach in _parse_machinery_rows(form, boq_qty):
        db.execute(
            "INSERT INTO cost_plan_machinery(cost_plan_id, activity_id, equipment_type, equipment_id, "
            "hours_per_unit, hourly_rate, planned_hours, planned_amount, sort_order) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (
                plan_id, mach["activity_id"], mach["equipment_type"], mach["equipment_id"],
                mach["hours_per_unit"], mach["hourly_rate"], mach["planned_hours"],
                mach["planned_amount"], mach["sort_order"],
            ),
        )

    return plan_id, None


def save_micro_plan_from_form(db, form, username: str) -> tuple[int | None, str | None]:
    cost_plan_id = (form.get("micro_cost_plan_id") or "").strip()
    project_id = (form.get("micro_project_id") or "").strip()
    plan_period = (form.get("plan_period") or "Daily").strip()
    plan_date = (form.get("plan_date") or "").strip()
    activity_id = (form.get("micro_activity_id") or "").strip()
    planned_qty = _safe_float(form.get("micro_planned_qty"))
    planned_manpower = _safe_float(form.get("micro_planned_manpower"))
    planned_equipment = (form.get("micro_planned_equipment") or "").strip()
    planned_material = (form.get("micro_planned_material") or "").strip()
    remarks = (form.get("micro_remarks") or "").strip()
    entry_id = (form.get("micro_entry_id") or "").strip()

    if plan_period not in MICRO_PLAN_PERIODS:
        plan_period = "Daily"
    if not cost_plan_id or not project_id or not plan_date:
        return None, "Cost plan, project, and date are required for micro planning."

    now = _now_ts()
    act_id_val = int(activity_id) if activity_id.isdigit() else None

    if entry_id:
        db.execute(
            "UPDATE micro_plan_entries SET cost_plan_id=?, activity_id=?, project_id=?, plan_period=?, "
            "plan_date=?, planned_qty=?, planned_manpower=?, planned_equipment=?, planned_material=?, "
            "remarks=?, modified_by=?, modified_at=? WHERE id=?",
            (
                cost_plan_id, act_id_val, project_id, plan_period, plan_date,
                planned_qty, planned_manpower, planned_equipment, planned_material,
                remarks, username, now, entry_id,
            ),
        )
        return int(entry_id), None

    cur = db.execute(
        "INSERT INTO micro_plan_entries(cost_plan_id, activity_id, project_id, plan_period, plan_date, "
        "planned_qty, planned_manpower, planned_equipment, planned_material, remarks, "
        "created_by, created_at, modified_by, modified_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            cost_plan_id, act_id_val, project_id, plan_period, plan_date,
            planned_qty, planned_manpower, planned_equipment, planned_material,
            remarks, username, now, username, now,
        ),
    )
    return cur.lastrowid, None


def list_cost_plans(db, project_id: int | None = None) -> list[dict]:
    if project_id:
        rows = db.execute(
            "SELECT cp.*, bi.item_description, bi.item_code, bm.boq_number, "
            "p.project_code, p.project_name "
            "FROM cost_plans cp "
            "JOIN boq_items bi ON cp.boq_item_id = bi.id "
            "LEFT JOIN boq_master bm ON cp.boq_master_id = bm.id "
            "LEFT JOIN projects p ON cp.project_id = p.id "
            "WHERE cp.project_id=? ORDER BY cp.id DESC",
            (project_id,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT cp.*, bi.item_description, bi.item_code, bm.boq_number, "
            "p.project_code, p.project_name "
            "FROM cost_plans cp "
            "JOIN boq_items bi ON cp.boq_item_id = bi.id "
            "LEFT JOIN boq_master bm ON cp.boq_master_id = bm.id "
            "LEFT JOIN projects p ON cp.project_id = p.id "
            "ORDER BY cp.id DESC",
        ).fetchall()
    return [dict(r) for r in rows]


def export_cost_plan_register_rows(db, project_id: int | None = None) -> list[dict]:
    plans = list_cost_plans(db, project_id)
    export_rows = []
    for plan in plans:
        detail = load_cost_plan_detail(db, plan["id"])
        if not detail:
            continue
        mon = detail["monitoring"]
        export_rows.append({
            "Project": f"{plan.get('project_code') or ''} — {plan.get('project_name') or ''}",
            "BOQ": plan.get("boq_number") or "",
            "BOQ Item": plan.get("item_code") or "",
            "Description": plan.get("item_description") or "",
            "BOQ Qty": plan.get("boq_quantity") or 0,
            "Unit": plan.get("boq_unit") or "",
            "Material Cost": mon.get("material_cost", 0),
            "Labour Cost": mon.get("labour_cost", 0),
            "Machinery Cost": mon.get("machinery_cost", 0),
            "Total Planned Cost": mon.get("total_planned_cost", 0),
            "Actual Qty": mon.get("actual_quantity", 0),
            "Actual Cost": mon.get("actual_cost", 0),
            "Cost Variance": mon.get("cost_variance", 0),
            "Planned Progress %": mon.get("planned_progress_percent", 0),
            "Actual Progress %": mon.get("actual_progress_percent", 0),
            "Status": plan.get("plan_status") or "",
        })
    return export_rows
