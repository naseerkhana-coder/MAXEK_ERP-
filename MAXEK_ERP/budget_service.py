"""Project budget control — schema, cost tracking, alerts."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from treasury_service import log_treasury_audit

BUDGET_CATEGORIES = ("Material", "Labour", "Equipment", "Subcontract", "Overhead")
BUDGET_CATEGORY_ALL = "Total"
BUDGET_LINE_CATEGORIES = BUDGET_CATEGORIES + (BUDGET_CATEGORY_ALL,)

ALERT_BUDGET_EXCEEDED = "budget_exceeded"
ALERT_COST_OVERRUN = "cost_overrun"


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _balance(budget_amount: float, committed_cost: float, actual_cost: float) -> float:
    return round(budget_amount - committed_cost - actual_cost, 2)


def _enrich_budget_row(row: dict) -> dict:
    budget_amount = _safe_float(row.get("budget_amount"))
    committed_cost = _safe_float(row.get("committed_cost"))
    actual_cost = _safe_float(row.get("actual_cost"))
    utilized = round(committed_cost + actual_cost, 2)
    pct_used = round((utilized / budget_amount) * 100, 1) if budget_amount > 0 else 0.0
    balance = _balance(budget_amount, committed_cost, actual_cost)
    alerts: list[str] = []
    if budget_amount > 0:
        if utilized > budget_amount:
            alerts.append(ALERT_BUDGET_EXCEEDED)
        if actual_cost > budget_amount:
            alerts.append(ALERT_COST_OVERRUN)
    out = dict(row)
    out.update(
        {
            "budget_amount": budget_amount,
            "committed_cost": committed_cost,
            "actual_cost": actual_cost,
            "balance": balance,
            "utilized": utilized,
            "pct_used": pct_used,
            "alerts": alerts,
            "has_alert": bool(alerts),
        }
    )
    return out



def _fy_filter(fiscal_year: str | None) -> tuple[str, tuple]:
    fy = (fiscal_year or "").strip() or None
    if fy:
        return "fiscal_year = ?", (fy,)
    return "fiscal_year IS NULL", ()


def ensure_budget_schema(db) -> None:
    """Idempotent budget control schema."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS project_budgets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            budget_amount REAL DEFAULT 0,
            committed_cost REAL DEFAULT 0,
            actual_cost REAL DEFAULT 0,
            fiscal_year TEXT,
            notes TEXT,
            updated_at TEXT,
            updated_by TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            UNIQUE(project_id, category, fiscal_year)
        )
    """)
    for column, col_type in (
        ("project_id", "INTEGER"),
        ("category", "TEXT"),
        ("budget_amount", "REAL DEFAULT 0"),
        ("committed_cost", "REAL DEFAULT 0"),
        ("actual_cost", "REAL DEFAULT 0"),
        ("fiscal_year", "TEXT"),
        ("notes", "TEXT"),
        ("updated_at", "TEXT"),
        ("updated_by", "TEXT"),
    ):
        if _table_exists(db, "project_budgets"):
            cols = [r[1] for r in db.execute("PRAGMA table_info(project_budgets)").fetchall()]
            if column not in cols:
                db.execute(f"ALTER TABLE project_budgets ADD COLUMN {column} {col_type}")


def _module_costs_material(db, project_id: int) -> dict[str, float]:
    committed = actual = 0.0
    if _table_exists(db, "purchase_requests"):
        row = db.execute(
            "SELECT COALESCE(SUM(estimated_cost), 0) AS total FROM purchase_requests "
            "WHERE project_id=? AND COALESCE(approval_status, '') NOT IN ('Approved', 'Rejected')",
            (project_id,),
        ).fetchone()
        committed += _safe_float(row["total"] if row else 0)
    if _table_exists(db, "purchase_orders"):
        row = db.execute(
            "SELECT COALESCE(SUM(grand_total), 0) AS total FROM purchase_orders "
            "WHERE project_id=? AND COALESCE(approval_status, '') = 'Approved'",
            (project_id,),
        ).fetchone()
        actual += _safe_float(row["total"] if row else 0)
    if _table_exists(db, "project_expenses"):
        row = db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM project_expenses "
            "WHERE project_id=? AND LOWER(COALESCE(expense_category, '')) LIKE '%material%'",
            (project_id,),
        ).fetchone()
        actual += _safe_float(row["total"] if row else 0)
    return {"committed": round(committed, 2), "actual": round(actual, 2)}


def _module_costs_labour(db, project_id: int) -> dict[str, float]:
    committed = actual = 0.0
    if _table_exists(db, "payroll_lines"):
        row = db.execute(
            "SELECT COALESCE(SUM(net_salary), 0) AS total FROM payroll_lines "
            "WHERE project_id=?",
            (project_id,),
        ).fetchone()
        actual += _safe_float(row["total"] if row else 0)
    if _table_exists(db, "payroll_runs"):
        row = db.execute(
            "SELECT COALESCE(SUM(total_amount), 0) AS total FROM payroll_runs "
            "WHERE project_id=? AND COALESCE(approval_status, '') NOT IN ('Approved', 'Rejected')",
            (project_id,),
        ).fetchone()
        committed += _safe_float(row["total"] if row else 0)
    return {"committed": round(committed, 2), "actual": round(actual, 2)}


def _module_costs_subcontract(db, project_id: int) -> dict[str, float]:
    committed = actual = 0.0
    if _table_exists(db, "subcontract_requests"):
        pending = db.execute(
            "SELECT COALESCE(SUM(contract_amount), 0) AS total FROM subcontract_requests "
            "WHERE project_id=? AND COALESCE(approval_status, '') NOT IN ('Approved', 'Rejected')",
            (project_id,),
        ).fetchone()
        committed += _safe_float(pending["total"] if pending else 0)
        approved = db.execute(
            "SELECT COALESCE(SUM(contract_amount), 0) AS total FROM subcontract_requests "
            "WHERE project_id=? AND COALESCE(approval_status, '') = 'Approved'",
            (project_id,),
        ).fetchone()
        actual += _safe_float(approved["total"] if approved else 0)
    return {"committed": round(committed, 2), "actual": round(actual, 2)}


def _module_costs_equipment(db, project_id: int) -> dict[str, float]:
    actual = 0.0
    if _table_exists(db, "project_expenses"):
        row = db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM project_expenses "
            "WHERE project_id=? AND LOWER(COALESCE(expense_category, '')) LIKE '%equip%'",
            (project_id,),
        ).fetchone()
        actual += _safe_float(row["total"] if row else 0)
    return {"committed": 0.0, "actual": round(actual, 2)}


def _module_costs_overhead(db, project_id: int) -> dict[str, float]:
    committed = actual = 0.0
    if _table_exists(db, "petty_cash"):
        row = db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM petty_cash WHERE project_id=?",
            (project_id,),
        ).fetchone()
        actual += _safe_float(row["total"] if row else 0)
    if _table_exists(db, "project_expenses"):
        row = db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM project_expenses "
            "WHERE project_id=? AND LOWER(COALESCE(expense_category, '')) LIKE '%overhead%'",
            (project_id,),
        ).fetchone()
        actual += _safe_float(row["total"] if row else 0)
    return {"committed": round(committed, 2), "actual": round(actual, 2)}


MODULE_COST_HOOKS = {
    "Material": _module_costs_material,
    "Labour": _module_costs_labour,
    "Equipment": _module_costs_equipment,
    "Subcontract": _module_costs_subcontract,
    "Overhead": _module_costs_overhead,
}


def sync_budget_costs_from_modules(db, project_id: int, fiscal_year: str | None = None) -> None:
    """Pull committed/actual from integrated modules when data exists; preserve manual overrides if higher."""
    ensure_budget_schema(db)
    fy = fiscal_year or None
    for category, hook in MODULE_COST_HOOKS.items():
        costs = hook(db, project_id)
        if costs["committed"] == 0 and costs["actual"] == 0:
            continue
        fy_sql, fy_args = _fy_filter(fy)
        existing = db.execute(
            f"SELECT id, committed_cost, actual_cost FROM project_budgets "
            f"WHERE project_id=? AND category=? AND {fy_sql}",
            (project_id, category, *fy_args),
        ).fetchone()
        if existing:
            new_committed = max(_safe_float(existing["committed_cost"]), costs["committed"])
            new_actual = max(_safe_float(existing["actual_cost"]), costs["actual"])
            if new_committed != _safe_float(existing["committed_cost"]) or new_actual != _safe_float(
                existing["actual_cost"]
            ):
                db.execute(
                    "UPDATE project_budgets SET committed_cost=?, actual_cost=?, updated_at=? "
                    "WHERE id=?",
                    (new_committed, new_actual, _now_ts(), existing["id"]),
                )
        else:
            db.execute(
                "INSERT INTO project_budgets("
                "project_id, category, budget_amount, committed_cost, actual_cost, "
                "fiscal_year, updated_at"
                ") VALUES(?,?,?,?,?,?,?)",
                (project_id, category, 0, costs["committed"], costs["actual"], fy, _now_ts()),
            )
    _recompute_total_row(db, project_id, fy)


def _recompute_total_row(db, project_id: int, fiscal_year: str | None = None) -> None:
    fy = fiscal_year or None
    fy_sql, fy_args = _fy_filter(fy)
    rows = db.execute(
        f"SELECT category, budget_amount, committed_cost, actual_cost FROM project_budgets "
        f"WHERE project_id=? AND category != ? AND {fy_sql}",
        (project_id, BUDGET_CATEGORY_ALL, *fy_args),
    ).fetchall()
    if not rows:
        return
    totals = {
        "budget_amount": sum(_safe_float(r["budget_amount"]) for r in rows),
        "committed_cost": sum(_safe_float(r["committed_cost"]) for r in rows),
        "actual_cost": sum(_safe_float(r["actual_cost"]) for r in rows),
    }
    existing = db.execute(
        f"SELECT id FROM project_budgets WHERE project_id=? AND category=? AND {fy_sql}",
        (project_id, BUDGET_CATEGORY_ALL, *fy_args),
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE project_budgets SET budget_amount=?, committed_cost=?, actual_cost=?, "
            "updated_at=? WHERE id=?",
            (
                totals["budget_amount"],
                totals["committed_cost"],
                totals["actual_cost"],
                _now_ts(),
                existing["id"],
            ),
        )
    else:
        db.execute(
            "INSERT INTO project_budgets("
            "project_id, category, budget_amount, committed_cost, actual_cost, fiscal_year, updated_at"
            ") VALUES(?,?,?,?,?,?,?)",
            (
                project_id,
                BUDGET_CATEGORY_ALL,
                totals["budget_amount"],
                totals["committed_cost"],
                totals["actual_cost"],
                fy,
                _now_ts(),
            ),
        )


def list_project_budget_overview(db, fiscal_year: str | None = None) -> list[dict]:
    """All projects with rolled-up budget summary."""
    ensure_budget_schema(db)
    fy = fiscal_year or None
    projects = db.execute(
        "SELECT id, project_name, location, status, budget AS project_budget "
        "FROM projects ORDER BY project_name"
    ).fetchall()
    overview: list[dict] = []
    for project in projects:
        proj = dict(project)
        sync_budget_costs_from_modules(db, proj["id"], fy)
        summary = get_project_budget_summary(db, proj["id"], fy)
        overview.append(
            {
                "project_id": proj["id"],
                "project_name": proj["project_name"],
                "location": proj.get("location"),
                "status": proj.get("status"),
                "project_budget": _safe_float(proj.get("project_budget")),
                **summary,
            }
        )
    return overview


def get_project_budget_lines(
    db, project_id: int, fiscal_year: str | None = None, *, sync_modules: bool = True
) -> list[dict]:
    ensure_budget_schema(db)
    fy = fiscal_year or None
    if sync_modules:
        sync_budget_costs_from_modules(db, project_id, fy)
    fy_sql, fy_args = _fy_filter(fy)
    rows = db.execute(
        f"SELECT * FROM project_budgets WHERE project_id=? AND {fy_sql} "
        "ORDER BY CASE category "
        "WHEN 'Material' THEN 1 WHEN 'Labour' THEN 2 WHEN 'Equipment' THEN 3 "
        "WHEN 'Subcontract' THEN 4 WHEN 'Overhead' THEN 5 WHEN 'Total' THEN 99 ELSE 50 END",
        (project_id, *fy_args),
    ).fetchall()
    return [_enrich_budget_row(dict(r)) for r in rows]


def get_project_budget_summary(db, project_id: int, fiscal_year: str | None = None) -> dict:
    lines = get_project_budget_lines(db, project_id, fiscal_year, sync_modules=False)
    total_line = next((ln for ln in lines if ln["category"] == BUDGET_CATEGORY_ALL), None)
    if total_line:
        base = total_line
    elif lines:
        base = _enrich_budget_row(
            {
                "category": BUDGET_CATEGORY_ALL,
                "budget_amount": sum(ln["budget_amount"] for ln in lines if ln["category"] != BUDGET_CATEGORY_ALL),
                "committed_cost": sum(ln["committed_cost"] for ln in lines if ln["category"] != BUDGET_CATEGORY_ALL),
                "actual_cost": sum(ln["actual_cost"] for ln in lines if ln["category"] != BUDGET_CATEGORY_ALL),
            }
        )
    else:
        base = _enrich_budget_row(
            {"category": BUDGET_CATEGORY_ALL, "budget_amount": 0, "committed_cost": 0, "actual_cost": 0}
        )
    return {
        "budget_amount": base["budget_amount"],
        "committed_cost": base["committed_cost"],
        "actual_cost": base["actual_cost"],
        "balance": base["balance"],
        "utilized": base["utilized"],
        "pct_used": base["pct_used"],
        "alerts": base["alerts"],
        "has_alert": base["has_alert"],
        "line_count": len(lines),
    }


def get_project_budget(db, project_id: int) -> dict | None:
    row = db.execute(
        "SELECT id, project_name, location, status, budget FROM projects WHERE id=?",
        (project_id,),
    ).fetchone()
    return dict(row) if row else None


def save_project_budgets(
    db,
    project_id: int,
    form_data: dict,
    username: str,
    fiscal_year: str | None = None,
) -> None:
    ensure_budget_schema(db)
    project = get_project_budget(db, project_id)
    if not project:
        raise ValueError("Project not found.")
    fy = (fiscal_year or form_data.get("fiscal_year") or "").strip() or None
    for category in BUDGET_CATEGORIES:
        prefix = category.lower().replace(" ", "_")
        budget_amount = _safe_float(form_data.get(f"{prefix}_budget"))
        committed_cost = _safe_float(form_data.get(f"{prefix}_committed"))
        actual_cost = _safe_float(form_data.get(f"{prefix}_actual"))
        notes = (form_data.get(f"{prefix}_notes") or "").strip()
        fy_sql, fy_args = _fy_filter(fy)
        existing = db.execute(
            f"SELECT id FROM project_budgets WHERE project_id=? AND category=? AND {fy_sql}",
            (project_id, category, *fy_args),
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE project_budgets SET budget_amount=?, committed_cost=?, actual_cost=?, "
                "notes=?, updated_at=?, updated_by=? WHERE id=?",
                (
                    budget_amount,
                    committed_cost,
                    actual_cost,
                    notes,
                    _now_ts(),
                    username,
                    existing["id"],
                ),
            )
        else:
            db.execute(
                "INSERT INTO project_budgets("
                "project_id, category, budget_amount, committed_cost, actual_cost, "
                "fiscal_year, notes, updated_at, updated_by"
                ") VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    project_id,
                    category,
                    budget_amount,
                    committed_cost,
                    actual_cost,
                    fy,
                    notes,
                    _now_ts(),
                    username,
                ),
            )
    _recompute_total_row(db, project_id, fy)
    log_treasury_audit(
        db,
        "project_budget",
        project_id,
        "updated",
        username,
        f"Budget lines saved{f' FY {fy}' if fy else ''}",
    )


def budget_alerts(db, fiscal_year: str | None = None) -> list[dict]:
    """Projects/categories with budget exceeded or cost overrun."""
    ensure_budget_schema(db)
    fy = fiscal_year or None
    alerts: list[dict] = []
    for item in list_project_budget_overview(db, fy):
        if item.get("has_alert"):
            alerts.append(
                {
                    "project_id": item["project_id"],
                    "project_name": item["project_name"],
                    "category": BUDGET_CATEGORY_ALL,
                    "alert_types": item.get("alerts") or [],
                    "budget_amount": item["budget_amount"],
                    "utilized": item["utilized"],
                    "actual_cost": item["actual_cost"],
                }
            )
        for line in get_project_budget_lines(db, item["project_id"], fy, sync_modules=False):
            if line.get("has_alert") and line["category"] != BUDGET_CATEGORY_ALL:
                alerts.append(
                    {
                        "project_id": item["project_id"],
                        "project_name": item["project_name"],
                        "category": line["category"],
                        "alert_types": line["alerts"],
                        "budget_amount": line["budget_amount"],
                        "utilized": line["utilized"],
                        "actual_cost": line["actual_cost"],
                    }
                )
    return alerts


def seed_budget_demo_data(db) -> None:
    if os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        return
    ensure_budget_schema(db)
    count = db.execute("SELECT COUNT(*) AS c FROM project_budgets").fetchone()["c"]
    if count > 0:
        return
    project = db.execute(
        "SELECT id, budget FROM projects WHERE project_name LIKE '%Demo Highway%' "
        "OR status='Active' ORDER BY id LIMIT 1"
    ).fetchone()
    if not project:
        return
    project_id = project["id"]
    demo_lines = [
        ("Material", 8_000_000, 2_100_000, 8_350_000, "Steel & cement — actual exceeds budget"),
        ("Labour", 5_000_000, 450_000, 2_150_000, "Site labour payroll"),
        ("Equipment", 2_000_000, 320_000, 1_120_000, "Plant hire & fuel"),
        ("Subcontract", 6_000_000, 1_800_000, 3_400_000, "Civil subcontract RA bills"),
        ("Overhead", 1_000_000, 80_000, 420_000, "Site office & utilities"),
    ]
    ts = _now_ts()
    for category, budget_amt, committed, actual, notes in demo_lines:
        db.execute(
            "INSERT INTO project_budgets("
            "project_id, category, budget_amount, committed_cost, actual_cost, notes, updated_at, updated_by"
            ") VALUES(?,?,?,?,?,?,?,?)",
            (project_id, category, budget_amt, committed, actual, notes, ts, "demo"),
        )
    _recompute_total_row(db, project_id, None)
    log_treasury_audit(
        db,
        "project_budget",
        project_id,
        "seeded",
        "demo",
        "Demo budget control lines for Demo Highway Phase-1",
    )
