"""Project profitability — contract value, billing, receipts vs cost P&L."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from budget_service import (
    BUDGET_CATEGORIES,
    ensure_budget_schema,
    get_project_budget_lines,
    sync_budget_costs_from_modules,
)
from contract_service import get_effective_contract_value
from treasury_service import log_treasury_audit

DIRECT_COST_CATEGORIES = ("Material", "Labour", "Equipment", "Subcontract")
OVERHEAD_CATEGORY = "Overhead"


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(db, table: str, column: str) -> bool:
    if not _table_exists(db, table):
        return False
    cols = [r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def _ensure_column(db, table: str, column: str, col_type: str) -> None:
    if not _table_exists(db, table):
        return
    if not _column_exists(db, table, column):
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _round2(value: float) -> float:
    return round(_safe_float(value), 2)


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_profitability_schema(db) -> None:
    """Optional columns to link treasury receipts to projects."""
    ensure_budget_schema(db)
    _ensure_column(db, "bank_receipts", "project_id", "INTEGER")


def _project_contract_value(project_row: dict | None) -> float:
    if not project_row:
        return 0.0
    for key in ("approved_total_amount", "quoted_amount", "work_order_amount", "budget"):
        val = project_row.get(key)
        if val is not None and _safe_float(val) > 0:
            return _safe_float(val)
    return 0.0


def _load_project_row(db, project_id: int) -> dict | None:
    row = db.execute(
        """
        SELECT p.*, c.client_name, c.company_name
        FROM projects p
        LEFT JOIN clients c ON p.client_id = c.id
        WHERE p.id=?
        """,
        (project_id,),
    ).fetchone()
    return dict(row) if row else None


def _project_client_terms(project_row: dict) -> list[str]:
    terms: list[str] = []
    for key in (
        "gov_department",
        "private_client_name",
        "company_name",
        "client_name",
        "project_name",
    ):
        val = (project_row.get(key) or "").strip()
        if val and val not in terms:
            terms.append(val)
    return terms


def _client_billing_total(db, project_id: int) -> float:
    if not _table_exists(db, "client_bills"):
        return 0.0
    row = db.execute(
        """
        SELECT COALESCE(SUM(net_payable), 0) AS total
        FROM client_bills
        WHERE project_id=? AND approval_status='Approved'
        """,
        (project_id,),
    ).fetchone()
    return _round2(row["total"] if row else 0)


def _receipts_total(db, project_id: int, project_row: dict) -> float:
    total = 0.0
    if _table_exists(db, "receipt_vouchers"):
        row = db.execute(
            """
            SELECT COALESCE(SUM(COALESCE(grand_total, amount)), 0) AS total
            FROM receipt_vouchers
            WHERE project_id=? AND approval_status='Approved'
            """,
            (project_id,),
        ).fetchone()
        total += _safe_float(row["total"] if row else 0)
    if _table_exists(db, "bank_receipts"):
        if _column_exists(db, "bank_receipts", "project_id"):
            row = db.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total
                FROM bank_receipts
                WHERE project_id=? AND approval_status='Approved'
                """,
                (project_id,),
            ).fetchone()
            total += _safe_float(row["total"] if row else 0)
        seen_ids: set[int] = set()
        if _column_exists(db, "bank_receipts", "project_id"):
            for r in db.execute(
                "SELECT id FROM bank_receipts WHERE project_id=? AND approval_status='Approved'",
                (project_id,),
            ).fetchall():
                seen_ids.add(r["id"])
        for term in _project_client_terms(project_row):
            rows = db.execute(
                """
                SELECT id, amount FROM bank_receipts
                WHERE approval_status='Approved' AND client IS NOT NULL AND client != ''
                AND client LIKE ?
                """,
                (f"%{term}%",),
            ).fetchall()
            for r in rows:
                if r["id"] in seen_ids:
                    continue
                seen_ids.add(r["id"])
                total += _safe_float(r["amount"])
    return _round2(total)


def _costs_by_category(
    db, project_id: int, fiscal_year: str | None = None, *, sync_modules: bool = True
) -> dict[str, float]:
    if sync_modules:
        try:
            sync_budget_costs_from_modules(db, project_id, fiscal_year)
        except Exception:
            pass
    lines = get_project_budget_lines(db, project_id, fiscal_year, sync_modules=False)
    costs = {cat: 0.0 for cat in BUDGET_CATEGORIES}
    for line in lines:
        cat = line.get("category")
        if cat in costs:
            costs[cat] = _round2(line.get("actual_cost"))
    return costs


def _compute_profitability(
    *,
    contract_value: float,
    client_billing: float,
    receipts: float,
    material_cost: float,
    labour_cost: float,
    equipment_cost: float,
    subcontract_cost: float,
    overheads: float,
) -> dict[str, float]:
    direct_costs = _round2(material_cost + labour_cost + equipment_cost + subcontract_cost)
    revenue_base = client_billing if client_billing > 0 else receipts
    gross_profit = _round2(revenue_base - direct_costs)
    net_profit = _round2(gross_profit - overheads)
    profit_pct = round((net_profit / contract_value) * 100, 1) if contract_value > 0 else 0.0
    margin_on_billing = round((net_profit / client_billing) * 100, 1) if client_billing > 0 else 0.0
    return {
        "direct_costs": direct_costs,
        "revenue_base": revenue_base,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
        "profit_pct": profit_pct,
        "margin_on_billing": margin_on_billing,
    }


def get_project_profitability(
    db, project_id: int, fiscal_year: str | None = None, *, sync_modules: bool = True
) -> dict | None:
    """Detailed P&L for one project."""
    ensure_profitability_schema(db)
    project = _load_project_row(db, project_id)
    if not project:
        return None
    costs = _costs_by_category(db, project_id, fiscal_year, sync_modules=sync_modules)
    contract_value = get_effective_contract_value(db, project_id) or _project_contract_value(project)
    client_billing = _client_billing_total(db, project_id)
    receipts = _receipts_total(db, project_id, project)
    calc = _compute_profitability(
        contract_value=contract_value,
        client_billing=client_billing,
        receipts=receipts,
        material_cost=costs["Material"],
        labour_cost=costs["Labour"],
        equipment_cost=costs["Equipment"],
        subcontract_cost=costs["Subcontract"],
        overheads=costs["Overhead"],
    )
    billing_rows: list[dict] = []
    if _table_exists(db, "client_bills"):
        billing_rows = [
            dict(r)
            for r in db.execute(
                """
                SELECT bill_number, ra_number, bill_date, net_payable, bill_status, approval_status
                FROM client_bills
                WHERE project_id=?
                ORDER BY bill_date DESC, id DESC
                LIMIT 20
                """,
                (project_id,),
            ).fetchall()
        ]
    receipt_rows: list[dict] = []
    if _table_exists(db, "bank_receipts"):
        if _column_exists(db, "bank_receipts", "project_id"):
            receipt_rows = [
                dict(r)
                for r in db.execute(
                    """
                    SELECT receipt_date, client, amount, utr_number, approval_status, status
                    FROM bank_receipts
                    WHERE project_id=?
                    ORDER BY receipt_date DESC, id DESC
                    LIMIT 20
                    """,
                    (project_id,),
                ).fetchall()
            ]
        if not receipt_rows:
            terms = _project_client_terms(project)
            if terms:
                clauses = " OR ".join(["client LIKE ?"] * len(terms))
                params = [f"%{t}%" for t in terms]
                receipt_rows = [
                    dict(r)
                    for r in db.execute(
                        f"""
                        SELECT receipt_date, client, amount, utr_number, approval_status, status
                        FROM bank_receipts
                        WHERE client IS NOT NULL AND ({clauses})
                        ORDER BY receipt_date DESC, id DESC
                        LIMIT 20
                        """,
                        params,
                    ).fetchall()
                ]
    return {
        "project_id": project_id,
        "project_name": project.get("project_name") or "",
        "project_code": project.get("project_code") or "",
        "location": project.get("location"),
        "status": project.get("status"),
        "client_name": (
            project.get("company_name")
            or project.get("client_name")
            or project.get("private_client_name")
            or project.get("gov_department")
            or ""
        ),
        "contract_value": contract_value,
        "contract_value_source": _contract_value_source(project),
        "client_billing": client_billing,
        "receipts": receipts,
        "material_cost": costs["Material"],
        "labour_cost": costs["Labour"],
        "equipment_cost": costs["Equipment"],
        "subcontract_cost": costs["Subcontract"],
        "overheads": costs["Overhead"],
        "billing_rows": billing_rows,
        "receipt_rows": receipt_rows,
        **calc,
    }


def _contract_value_source(project: dict) -> str:
    for key, label in (
        ("approved_total_amount", "Approved total"),
        ("quoted_amount", "Quoted amount"),
        ("work_order_amount", "Work order"),
        ("budget", "Project budget"),
    ):
        if _safe_float(project.get(key)) > 0:
            return label
    return "Estimated"


def list_all_projects_profitability(
    db,
    fiscal_year: str | None = None,
    *,
    active_only: bool = True,
    sync_modules: bool = True,
) -> list[dict]:
    """Summary profitability for all projects."""
    ensure_profitability_schema(db)
    sql = "SELECT id FROM projects"
    if active_only:
        sql += " WHERE COALESCE(status, '') = 'Active'"
    sql += " ORDER BY project_name"
    project_ids = [r["id"] for r in db.execute(sql).fetchall()]
    rows: list[dict] = []
    for pid in project_ids:
        detail = get_project_profitability(db, pid, fiscal_year, sync_modules=sync_modules)
        if detail:
            rows.append(detail)
    return rows


def seed_profitability_demo_data(db) -> None:
    """Demo client billing + approved receipts for Demo Highway Phase-1."""
    if os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        return
    ensure_profitability_schema(db)
    try:
        from client_billing_service import ensure_client_billing_schema

        ensure_client_billing_schema(db)
    except ImportError:
        pass
    project = db.execute(
        """
        SELECT id, project_name, client_id, gov_department, approved_total_amount, budget
        FROM projects
        WHERE project_name LIKE '%Demo Highway%' OR status='Active'
        ORDER BY CASE WHEN project_name LIKE '%Demo Highway%' THEN 0 ELSE 1 END, id
        LIMIT 1
        """
    ).fetchone()
    if not project:
        return
    project_id = project["id"]
    ts = _now_ts()
    today = datetime.now().strftime("%Y-%m-%d")

    if _table_exists(db, "client_bills"):
        bill_count = db.execute(
            "SELECT COUNT(*) AS c FROM client_bills WHERE project_id=?",
            (project_id,),
        ).fetchone()["c"]
        if bill_count == 0:
            demo_bills = [
                ("RA-2026-DH-01", "RA-1", 8_500_000, "Mobilization & earthwork"),
                ("RA-2026-DH-02", "RA-2", 10_000_000, "Pavement layer — certified"),
            ]
            for bill_no, ra_no, net, remarks in demo_bills:
                db.execute(
                    """
                    INSERT INTO client_bills(
                        bill_number, ra_number, project_id, client_id, period_from, period_to,
                        bill_date, remarks, gross_amount, net_payable, bill_status,
                        approval_status, created_by, created_at, modified_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        bill_no,
                        ra_no,
                        project_id,
                        project["client_id"],
                        "2026-04-01",
                        "2026-05-31",
                        today,
                        remarks,
                        net,
                        net,
                        "Certified",
                        "Approved",
                        "demo",
                        ts,
                        ts,
                    ),
                )
            log_treasury_audit(
                db,
                "project_profitability",
                project_id,
                "seeded",
                "demo",
                "Demo client RA bills for profitability",
            )

    if _table_exists(db, "bank_receipts"):
        client_label = (project["gov_department"] or "NHAI Regional Office").strip()
        db.execute(
            """
            UPDATE bank_receipts
            SET approval_status='Approved', status='Cleared', client=?, project_id=?
            WHERE client LIKE '%NHAI%' OR client LIKE '%Highway%'
            """,
            (client_label, project_id),
        )
        approved_sum = db.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total FROM bank_receipts
            WHERE project_id=? AND approval_status='Approved'
            """,
            (project_id,),
        ).fetchone()["total"]
        if _safe_float(approved_sum) < 1_000_000:
            db.execute(
                """
                INSERT INTO bank_receipts(
                    receipt_date, bank_account_id, client, project_id, utr_number, amount,
                    receipt_type, remarks, status, approval_status, created_by, created_at
                )
                SELECT ?, id, ?, ?, 'UTR-DEMO-RA1', 8500000, 'Client Receipt',
                       'RA-1 collection — demo', 'Cleared', 'Approved', 'demo', ?
                FROM bank_accounts WHERE is_active=1 ORDER BY id LIMIT 1
                """,
                (today, client_label, project_id, ts),
            )
