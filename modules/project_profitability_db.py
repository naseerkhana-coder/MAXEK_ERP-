"""Project profitability — schema, cost mapping, and aggregation queries."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import pandas as pd

from modules.database import get_conn, load_budget_vs_actual

# Cost head keys (align with dashboard spec)
HEAD_LABOUR = "labour"
HEAD_MATERIAL = "material"
HEAD_MACHINERY = "machinery"
HEAD_OVERHEAD = "overhead"

LABOUR_SUBHEADS = ("worker_salary", "staff_salary", "ot_amount")
MATERIAL_SUBHEADS = (
    "cement",
    "steel",
    "sand",
    "aggregate",
    "blocks",
    "electrical",
    "plumbing",
    "other_materials",
)
MACHINERY_SUBHEADS = (
    "excavator",
    "jcb",
    "crane",
    "generator",
    "equipment_rental",
    "fuel",
    "maintenance",
)
OVERHEAD_SUBHEADS = (
    "office_salary",
    "office_rent",
    "electricity",
    "internet",
    "mobile_bills",
    "software",
    "administration",
)

STAFF_EMPLOYEE_TYPES = (
    "Monthly Staff",
    "Daily Wage Staff",
    "Company Staff",
)

DEFAULT_MAPPINGS: list[tuple[str, str, str, str, str]] = [
    # source_type, match_kind (contains|exact|regex), match_value, cost_head, sub_head
    ("expense_category", "exact", "Labour", HEAD_LABOUR, "worker_salary"),
    ("expense_category", "exact", "Material", HEAD_MATERIAL, "other_materials"),
    ("expense_category", "exact", "Fuel", HEAD_MACHINERY, "fuel"),
    ("expense_category", "exact", "Equipment", HEAD_MACHINERY, "equipment_rental"),
    ("expense_category", "exact", "Office Expense", HEAD_OVERHEAD, "administration"),
    ("expense_head", "contains", "labour", HEAD_LABOUR, "worker_salary"),
    ("expense_head", "contains", "salary", HEAD_LABOUR, "staff_salary"),
    ("expense_head", "contains", "material", HEAD_MATERIAL, "other_materials"),
    ("expense_head", "contains", "fuel", HEAD_MACHINERY, "fuel"),
    ("expense_head", "contains", "rent", HEAD_OVERHEAD, "office_rent"),
    ("expense_head", "contains", "electric", HEAD_OVERHEAD, "electricity"),
    ("expense_head", "contains", "internet", HEAD_OVERHEAD, "internet"),
    ("expense_head", "contains", "mobile", HEAD_OVERHEAD, "mobile_bills"),
    ("expense_head", "contains", "software", HEAD_OVERHEAD, "software"),
    ("item_name", "contains", "cement", HEAD_MATERIAL, "cement"),
    ("item_name", "contains", "steel", HEAD_MATERIAL, "steel"),
    ("item_name", "contains", "sand", HEAD_MATERIAL, "sand"),
    ("item_name", "contains", "aggregate", HEAD_MATERIAL, "aggregate"),
    ("item_name", "contains", "block", HEAD_MATERIAL, "blocks"),
    ("item_name", "contains", "electr", HEAD_MATERIAL, "electrical"),
    ("item_name", "contains", "plumb", HEAD_MATERIAL, "plumbing"),
    ("item_name", "contains", "excavator", HEAD_MACHINERY, "excavator"),
    ("item_name", "contains", "jcb", HEAD_MACHINERY, "jcb"),
    ("item_name", "contains", "crane", HEAD_MACHINERY, "crane"),
    ("item_name", "contains", "generator", HEAD_MACHINERY, "generator"),
    ("payment_type", "contains", "salary", HEAD_LABOUR, "staff_salary"),
    ("payment_type", "contains", "equipment", HEAD_MACHINERY, "equipment_rental"),
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def ensure_profitability_schema(conn=None) -> None:
    own = conn is None
    if own:
        conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS profitability_cost_mapping(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            match_kind TEXT NOT NULL DEFAULT 'contains',
            match_value TEXT NOT NULL,
            cost_head TEXT NOT NULL,
            sub_head TEXT NOT NULL,
            priority INTEGER DEFAULT 100,
            is_active INTEGER DEFAULT 1,
            UNIQUE(source_type, match_kind, match_value, cost_head, sub_head)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS project_variations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            variation_id TEXT UNIQUE,
            project_id TEXT,
            project_name TEXT NOT NULL,
            description TEXT,
            amount REAL DEFAULT 0,
            status TEXT DEFAULT 'Approved',
            approved_date TEXT,
            created_at TEXT
        )
        """
    )
    for source_type, match_kind, match_value, cost_head, sub_head in DEFAULT_MAPPINGS:
        cur.execute(
            """
            INSERT OR IGNORE INTO profitability_cost_mapping(
                source_type, match_kind, match_value, cost_head, sub_head, priority
            ) VALUES(?,?,?,?,?,?)
            """,
            (source_type, match_kind, match_value, cost_head, sub_head, 100),
        )
    conn.commit()
    if own:
        conn.close()


def load_cost_mappings(conn=None) -> list[dict[str, Any]]:
    own = conn is None
    if own:
        conn = get_conn()
    ensure_profitability_schema(conn)
    rows = conn.execute(
        """
        SELECT source_type, match_kind, match_value, cost_head, sub_head, priority
        FROM profitability_cost_mapping
        WHERE is_active = 1
        ORDER BY priority ASC, id ASC
        """
    ).fetchall()
    if own:
        conn.close()
    return [
        {
            "source_type": r[0],
            "match_kind": r[1],
            "match_value": r[2],
            "cost_head": r[3],
            "sub_head": r[4],
            "priority": r[5],
        }
        for r in rows
    ]


def _match_mapping(
    mappings: list[dict[str, Any]],
    source_type: str,
    text: str,
) -> tuple[str, str] | None:
    val = _norm(text)
    if not val:
        return None
    for row in mappings:
        if row["source_type"] != source_type:
            continue
        mv = _norm(row["match_value"])
        kind = (row["match_kind"] or "contains").lower()
        if kind == "exact" and val == mv:
            return row["cost_head"], row["sub_head"]
        if kind == "contains" and mv in val:
            return row["cost_head"], row["sub_head"]
        if kind == "regex":
            try:
                if re.search(row["match_value"], text or "", re.I):
                    return row["cost_head"], row["sub_head"]
            except re.error:
                pass
    return None


def classify_cost(
    *,
    expense_category: str = "",
    expense_head: str = "",
    item_name: str = "",
    payment_type: str = "",
    description: str = "",
    mappings: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """Return (cost_head, sub_head)."""
    if mappings is None:
        mappings = load_cost_mappings()
    checks = [
        ("expense_category", expense_category),
        ("expense_head", expense_head),
        ("item_name", item_name),
        ("payment_type", payment_type),
        ("item_name", description),
    ]
    for source_type, text in checks:
        hit = _match_mapping(mappings, source_type, text)
        if hit:
            return hit
    if _norm(expense_category) == "transport":
        return HEAD_OVERHEAD, "administration"
    if _norm(expense_category) in {"site expense", "other"}:
        return HEAD_OVERHEAD, "administration"
    return HEAD_MATERIAL, "other_materials"


def profit_traffic_light(profit_pct: float | None, net_profit: float) -> tuple[str, str, str]:
    """Return (status_key, css_class, label)."""
    if net_profit < 0:
        return "critical", "profit-light-critical", "Loss — Critical Alert"
    if profit_pct is None:
        return "red", "profit-light-red", "Profit % N/A"
    if profit_pct > 20:
        return "green", "profit-light-green", "Strong (>20%)"
    if profit_pct >= 10:
        return "yellow", "profit-light-yellow", "Moderate (10–20%)"
    return "red", "profit-light-red", "Low (<10%)"


def calc_profit_pct(net_profit: float, project_value: float) -> float | None:
    if float(project_value or 0) <= 0:
        return None
    return round((float(net_profit) / float(project_value)) * 100, 2)


def pm_assigned_project_names(
    user_name: str,
    username: str = "",
    conn=None,
) -> set[str]:
    """Projects assigned to a PM via site_incharge (existing ERP pattern)."""
    own = conn is None
    if own:
        conn = get_conn()
    names: set[str] = set()
    for candidate in {user_name, username}:
        c = (candidate or "").strip()
        if not c:
            continue
        rows = conn.execute(
            """
            SELECT project_name FROM projects
            WHERE TRIM(COALESCE(site_incharge, '')) = ?
               OR TRIM(COALESCE(site_incharge, '')) LIKE ?
            """,
            (c, f"%{c}%"),
        ).fetchall()
        names.update(r[0] for r in rows if r[0])
    if own:
        conn.close()
    return names


def can_access_profitability(role: str) -> bool:
    from modules.roles import can_access_profitability_dashboard

    return can_access_profitability_dashboard(role)


def can_view_owner_profitability(role: str) -> bool:
    from modules.roles import is_management, is_super_admin

    return is_super_admin(role) or is_management(role) or (role or "").strip() in {
        "General Manager",
        "Managing Director",
    }


def _date_clause(column: str, date_from: str | None, date_to: str | None) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []
    if date_from:
        clauses.append(f"DATE({column}) >= DATE(?)")
        params.append(date_from)
    if date_to:
        clauses.append(f"DATE({column}) <= DATE(?)")
        params.append(date_to)
    if not clauses:
        return "", []
    return " AND " + " AND ".join(clauses), params


def load_projects_base(
    *,
    project_name: str | None = None,
    client_name: str | None = None,
    allowed_names: set[str] | None = None,
) -> pd.DataFrame:
    conn = get_conn()
    ensure_profitability_schema(conn)
    clauses = ["COALESCE(p.project_name, '') != ''"]
    params: list = []
    if project_name:
        clauses.append("p.project_name = ?")
        params.append(project_name)
    if client_name:
        clauses.append("p.client_name = ?")
        params.append(client_name)
    if allowed_names is not None:
        if not allowed_names:
            conn.close()
            return pd.DataFrame()
        placeholders = ",".join("?" * len(allowed_names))
        clauses.append(f"p.project_name IN ({placeholders})")
        params.extend(sorted(allowed_names))
    sql = f"""
        SELECT p.project_id, p.project_name, p.client_name, p.status,
               COALESCE(p.amount, 0) AS contract_value,
               COALESCE(p.budget, 0) AS budget,
               p.start_date, p.end_date, p.site_incharge
        FROM projects p
        WHERE {" AND ".join(clauses)}
        ORDER BY p.project_name
    """
    df = pd.read_sql_query(sql, conn, params=params or None)
    conn.close()
    return df


def approved_variation_total(project_name: str, conn=None) -> float:
    own = conn is None
    if own:
        conn = get_conn()
    ensure_profitability_schema(conn)
    row = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM project_variations
        WHERE project_name = ? AND LOWER(COALESCE(status, '')) = 'approved'
        """,
        (project_name,),
    ).fetchone()
    total = float(row[0] or 0)
    if total <= 0:
        row2 = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM project_boq_items
            WHERE project_name = ?
              AND LOWER(COALESCE(status, '')) = 'approved'
              AND (
                LOWER(COALESCE(boq_number, '')) LIKE '%var%'
                OR LOWER(COALESCE(description, '')) LIKE '%variation%'
              )
            """,
            (project_name,),
        ).fetchone()
        total = float(row2[0] or 0)
    if own:
        conn.close()
    return total


def _empty_cost_buckets() -> dict[str, Any]:
    labour = {k: 0.0 for k in LABOUR_SUBHEADS}
    material = {k: 0.0 for k in MATERIAL_SUBHEADS}
    machinery = {k: 0.0 for k in MACHINERY_SUBHEADS}
    overhead = {k: 0.0 for k in OVERHEAD_SUBHEADS}
    return {
        HEAD_LABOUR: labour,
        HEAD_MATERIAL: material,
        HEAD_MACHINERY: machinery,
        HEAD_OVERHEAD: overhead,
    }


def _add_cost(buckets: dict, head: str, sub: str, amount: float) -> None:
    amt = float(amount or 0)
    if amt == 0:
        return
    if head not in buckets:
        return
    if sub not in buckets[head]:
        sub = list(buckets[head].keys())[0]
    buckets[head][sub] = round(buckets[head][sub] + amt, 2)


def aggregate_project_costs(
    project_name: str,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    mappings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Aggregate all cost heads for one project."""
    if mappings is None:
        mappings = load_cost_mappings()
    buckets = _empty_cost_buckets()
    conn = get_conn()
    ensure_profitability_schema(conn)

    d_se, p_se = _date_clause("expense_date", date_from, date_to)
    site_lines = pd.read_sql_query(
        f"""
        SELECT se.expense_category, se.project_name, sel.item_name, sel.line_total
        FROM site_expenses se
        JOIN site_expense_lines sel ON sel.expense_id = se.expense_id
        WHERE se.status = 'Approved' AND se.project_name = ?{d_se}
        """,
        conn,
        params=[project_name, *p_se],
    )
    for _, row in site_lines.iterrows():
        head, sub = classify_cost(
            expense_category=str(row.get("expense_category") or ""),
            item_name=str(row.get("item_name") or ""),
            mappings=mappings,
        )
        _add_cost(buckets, head, sub, row.get("line_total"))

    d_se2, p_se2 = _date_clause("expense_date", date_from, date_to)
    site_hdr = pd.read_sql_query(
        f"""
        SELECT expense_category, total_invoice_value
        FROM site_expenses
        WHERE status = 'Approved' AND project_name = ?{d_se2}
        """,
        conn,
        params=[project_name, *p_se2],
    )
    for _, row in site_hdr.iterrows():
        head, sub = classify_cost(
            expense_category=str(row.get("expense_category") or ""),
            mappings=mappings,
        )
        _add_cost(buckets, head, sub, row.get("total_invoice_value"))

    d_inv, p_inv = _date_clause("ei.expense_date", date_from, date_to)
    inv_lines = pd.read_sql_query(
        f"""
        SELECT ei.exp_type, eil.item_name, eil.amount, ei.project_name
        FROM expense_invoices ei
        JOIN expense_invoice_lines eil ON eil.invoice_id = ei.invoice_id
        WHERE ei.project_name = ?{d_inv}
        """,
        conn,
        params=[project_name, *p_inv],
    )
    for _, row in inv_lines.iterrows():
        head, sub = classify_cost(
            expense_head=str(row.get("exp_type") or ""),
            item_name=str(row.get("item_name") or ""),
            mappings=mappings,
        )
        _add_cost(buckets, head, sub, row.get("amount"))

    d_ex, p_ex = _date_clause("expense_date", date_from, date_to)
    exp_rows = pd.read_sql_query(
        f"""
        SELECT expense_head, amount FROM expenses
        WHERE project_name = ?{d_ex}
        """,
        conn,
        params=[project_name, *p_ex],
    )
    for _, row in exp_rows.iterrows():
        head, sub = classify_cost(expense_head=str(row.get("expense_head") or ""), mappings=mappings)
        _add_cost(buckets, head, sub, row.get("amount"))

    d_ee, p_ee = _date_clause("expense_date", date_from, date_to)
    ee_rows = pd.read_sql_query(
        f"""
        SELECT expense_head, amount FROM expense_entries
        WHERE project_name = ? AND LOWER(COALESCE(status, '')) IN ('approved', 'posted', 'paid'){d_ee}
        """,
        conn,
        params=[project_name, *p_ee],
    )
    for _, row in ee_rows.iterrows():
        head, sub = classify_cost(expense_head=str(row.get("expense_head") or ""), mappings=mappings)
        _add_cost(buckets, head, sub, row.get("amount"))

    d_pay, p_pay = _date_clause("payment_date", date_from, date_to)
    payments = pd.read_sql_query(
        f"""
        SELECT payment_head, payment_type, amount
        FROM payments WHERE project_name = ?{d_pay}
        """,
        conn,
        params=[project_name, *p_pay],
    )
    for _, row in payments.iterrows():
        head, sub = classify_cost(
            expense_head=str(row.get("payment_head") or ""),
            payment_type=str(row.get("payment_type") or ""),
            mappings=mappings,
        )
        _add_cost(buckets, head, sub, row.get("amount"))

    d_dp, p_dp = _date_clause("payment_date", date_from, date_to)
    dps = pd.read_sql_query(
        f"""
        SELECT payment_type, amount FROM direct_payments
        WHERE project_name = ? AND status = 'Paid'{d_dp}
        """,
        conn,
        params=[project_name, *p_dp],
    )
    for _, row in dps.iterrows():
        head, sub = classify_cost(payment_type=str(row.get("payment_type") or ""), mappings=mappings)
        _add_cost(buckets, head, sub, row.get("amount"))

    d_ft, p_ft = _date_clause("transaction_date", date_from, date_to)
    fts = pd.read_sql_query(
        f"""
        SELECT category_head, transaction_type, amount
        FROM finance_transactions
        WHERE project_name = ? AND status = 'Settled'{d_ft}
        """,
        conn,
        params=[project_name, *p_ft],
    )
    for _, row in fts.iterrows():
        head, sub = classify_cost(
            expense_head=str(row.get("category_head") or ""),
            payment_type=str(row.get("transaction_type") or ""),
            mappings=mappings,
        )
        _add_cost(buckets, head, sub, row.get("amount"))

    d_att, p_att = _date_clause("attendance_date", date_from, date_to)
    ot_rows = pd.read_sql_query(
        f"""
        SELECT COALESCE(ot_hours, overtime, 0) AS ot_h,
               COALESCE(applied_ot_rate, 0) AS ot_rate,
               COALESCE(overtime, 0) AS legacy_ot
        FROM attendance
        WHERE project_name = ?
          AND COALESCE(ot_hours, overtime, 0) > 0{d_att}
        """,
        conn,
        params=[project_name, *p_att],
    )
    for _, row in ot_rows.iterrows():
        ot_h = float(row.get("ot_h") or 0)
        rate = float(row.get("ot_rate") or 0)
        if rate <= 0:
            rate = float(row.get("legacy_ot") or 0)
        _add_cost(buckets, HEAD_LABOUR, "ot_amount", ot_h * rate)

    payroll_filter = ""
    payroll_params: list = []
    if date_from or date_to:
        if date_from:
            payroll_filter += " AND payroll_month >= ?"
            payroll_params.append(date_from[:7] if len(date_from) >= 7 else date_from)
        if date_to:
            payroll_filter += " AND payroll_month <= ?"
            payroll_params.append(date_to[:7] if len(date_to) >= 7 else date_to)
    staff_pay = pd.read_sql_query(
        f"""
        SELECT COALESCE(p.net_salary, p.salary, 0) AS amt
        FROM payroll p
        INNER JOIN employees e ON e.employee_id = p.employee_id
        WHERE e.project_name = ?
          AND COALESCE(e.employee_type, '') IN (
              'Monthly Staff', 'Daily Wage Staff', 'Company Staff'
          ){payroll_filter}
        """,
        conn,
        params=[project_name, *payroll_params],
    )
    for _, row in staff_pay.iterrows():
        _add_cost(buckets, HEAD_LABOUR, "staff_salary", row.get("amt"))

    d_sub, p_sub = _date_clause("created_at", date_from, date_to)
    sub_lab = conn.execute(
        f"""
        SELECT COALESCE(SUM(net_amount), 0)
        FROM subcontractor_bill_entries
        WHERE project_name = ?{d_sub}
        """,
        [project_name, *p_sub],
    ).fetchone()
    if sub_lab:
        _add_cost(buckets, HEAD_LABOUR, "worker_salary", sub_lab[0])

    conn.close()

    labour_total = round(sum(buckets[HEAD_LABOUR].values()), 2)
    material_total = round(sum(buckets[HEAD_MATERIAL].values()), 2)
    machinery_total = round(sum(buckets[HEAD_MACHINERY].values()), 2)
    overhead_total = round(sum(buckets[HEAD_OVERHEAD].values()), 2)
    total_cost = round(labour_total + material_total + machinery_total + overhead_total, 2)

    return {
        "buckets": buckets,
        "labour_total": labour_total,
        "material_total": material_total,
        "machinery_total": machinery_total,
        "overhead_total": overhead_total,
        "total_cost": total_cost,
    }


def build_project_profitability_row(
    project_row: pd.Series | dict,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    pname = str(project_row.get("project_name") or "")
    contract = float(project_row.get("contract_value") or project_row.get("amount") or 0)
    variations = approved_variation_total(pname)
    project_value = round(contract + variations, 2)
    try:
        from modules.phase3_integration_db import aggregate_project_revenue

        revenue = aggregate_project_revenue(pname)
        work_done_value = revenue["work_done_value"]
        revenue_earned = revenue["revenue_earned"]
        billed_revenue = revenue["billed_revenue"]
    except Exception:
        work_done_value = 0.0
        revenue_earned = 0.0
        billed_revenue = 0.0
    costs = aggregate_project_costs(pname, date_from=date_from, date_to=date_to)
    total_cost = costs["total_cost"]
    net_profit = round(work_done_value - total_cost, 2) if work_done_value > 0 else round(project_value - total_cost, 2)
    profit_base = work_done_value if work_done_value > 0 else project_value
    profit_pct = calc_profit_pct(net_profit, profit_base)
    status_key, css_class, status_label = profit_traffic_light(profit_pct, net_profit)
    return {
        "project_id": project_row.get("project_id"),
        "project_name": pname,
        "client_name": project_row.get("client_name"),
        "contract_value": contract,
        "variation_value": variations,
        "project_value": project_value,
        "work_done_value": work_done_value,
        "revenue_earned": revenue_earned,
        "billed_revenue": billed_revenue,
        "labour_total": costs["labour_total"],
        "material_total": costs["material_total"],
        "machinery_total": costs["machinery_total"],
        "overhead_total": costs["overhead_total"],
        "total_cost": total_cost,
        "net_profit": net_profit,
        "profit_pct": profit_pct,
        "traffic_status": status_key,
        "traffic_class": css_class,
        "traffic_label": status_label,
        "buckets": costs["buckets"],
        "budget": float(project_row.get("budget") or 0),
    }


def load_profitability_summary(
    *,
    project_name: str | None = None,
    client_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    allowed_names: set[str] | None = None,
) -> pd.DataFrame:
    projects = load_projects_base(
        project_name=project_name,
        client_name=client_name,
        allowed_names=allowed_names,
    )
    if projects.empty:
        return pd.DataFrame()
    rows = [
        {
            k: v
            for k, v in build_project_profitability_row(r, date_from=date_from, date_to=date_to).items()
            if k != "buckets"
        }
        for _, r in projects.iterrows()
    ]
    return pd.DataFrame(rows)


def owner_dashboard_metrics(
    summary: pd.DataFrame,
) -> dict[str, float]:
    if summary.empty:
        return {
            "total_revenue": 0.0,
            "total_cost": 0.0,
            "total_profit": 0.0,
        }
    return {
        "total_revenue": round(float(summary["project_value"].sum()), 2),
        "total_cost": round(float(summary["total_cost"].sum()), 2),
        "total_profit": round(float(summary["net_profit"].sum()), 2),
    }


def load_budget_vs_actual_profitability(project_name: str | None = None) -> pd.DataFrame:
    bva = load_budget_vs_actual(project_name)
    if bva.empty:
        return bva
    bva = bva.copy()
    bva.rename(columns={"actual_total": "actual_cost"}, inplace=True)
    return bva


def labour_cost_detail(
    project_name: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    conn = get_conn()
    d_att, p_att = _date_clause("attendance_date", date_from, date_to)
    df = pd.read_sql_query(
        f"""
        SELECT 'OT' AS cost_type, attendance_date AS txn_date,
               COALESCE(worker_name, employee_name) AS party,
               COALESCE(ot_hours, overtime, 0) AS qty,
               COALESCE(applied_ot_rate, 0) AS rate,
               ROUND(COALESCE(ot_hours, overtime, 0) * COALESCE(applied_ot_rate, 0), 2) AS amount
        FROM attendance
        WHERE project_name = ?
          AND COALESCE(ot_hours, overtime, 0) > 0{d_att}
        UNION ALL
        SELECT 'Staff Payroll' AS cost_type, p.payroll_month AS txn_date,
               e.employee_name AS party, 1 AS qty, COALESCE(p.net_salary, p.salary, 0) AS rate,
               COALESCE(p.net_salary, p.salary, 0) AS amount
        FROM payroll p
        JOIN employees e ON e.employee_id = p.employee_id
        WHERE e.project_name = ?
          AND COALESCE(e.employee_type, '') IN (
              'Monthly Staff', 'Daily Wage Staff', 'Company Staff'
          )
        """,
        conn,
        params=[project_name, *p_att, project_name],
    )
    conn.close()
    return df


def material_cost_detail(project_name: str, date_from: str | None = None, date_to: str | None = None) -> pd.DataFrame:
    conn = get_conn()
    d_se, p_se = _date_clause("se.expense_date", date_from, date_to)
    df = pd.read_sql_query(
        f"""
        SELECT se.expense_date AS txn_date, sel.item_name, sel.quantity, sel.rate,
               sel.line_total AS amount, se.expense_category
        FROM site_expenses se
        JOIN site_expense_lines sel ON sel.expense_id = se.expense_id
        WHERE se.status = 'Approved' AND se.project_name = ?{d_se}
        ORDER BY se.expense_date DESC
        """,
        conn,
        params=[project_name, *p_se],
    )
    conn.close()
    return df
