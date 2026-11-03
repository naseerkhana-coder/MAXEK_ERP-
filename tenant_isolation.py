"""Tenant isolation schema helpers and query filters."""

from __future__ import annotations

from typing import Any

# Tables that receive tenant columns (nullable for backward compatibility).
TENANT_SCOPED_TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("users", ("customer_id",)),
    ("companies", ("customer_id", "company_id", "branch_id")),
    ("company_branches", ("customer_id", "company_id", "branch_id")),
    ("projects", ("customer_id", "company_id", "branch_id")),
    ("staff", ("customer_id", "company_id", "branch_id")),
    ("clients", ("customer_id", "company_id", "branch_id")),
    ("subcontractors", ("customer_id", "company_id", "branch_id")),
    ("departments", ("customer_id",)),
    ("material_requests", ("customer_id", "company_id", "branch_id")),
    ("purchase_requests", ("customer_id", "company_id", "branch_id")),
    ("purchase_orders", ("customer_id", "company_id", "branch_id")),
    ("store_receipts", ("customer_id", "company_id", "branch_id")),
    ("store_issues", ("customer_id", "company_id", "branch_id")),
    ("payroll_records", ("customer_id", "company_id", "branch_id")),
    ("account_transactions", ("customer_id", "company_id", "branch_id")),
    ("petty_cash_requests", ("customer_id", "company_id", "branch_id")),
    ("company_letters", ("customer_id", "company_id", "branch_id")),
)

# Deferred — large module-specific tables; columns can be added in later phases.
DEFERRED_TENANT_TABLES = (
    "dpr_entries",
    "boq_items",
    "daily_timesheets",
    "project_expenses",
    "head_office_expenses",
    "leave_requests",
    "manager_tasks",
    "subcontract_requests",
    "notifications",
    "approval_requests",
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


def _index_exists(db, index_name: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,),
    ).fetchone()
    return row is not None


def ensure_tenant_isolation_schema(db) -> None:
    """Add nullable tenant columns to operational tables."""
    for table, columns in TENANT_SCOPED_TABLES:
        for column in columns:
            if column == "customer_id":
                _ensure_column(db, table, column, "INTEGER")
            elif column == "company_id":
                _ensure_column(db, table, column, "INTEGER")
            elif column == "branch_id":
                _ensure_column(db, table, column, "INTEGER")
    if _table_exists(db, "users") and not _index_exists(db, "idx_users_customer_username"):
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_customer_username "
            "ON users(customer_id, username)"
        )


def migrate_users_composite_username(db) -> None:
    """Replace global UNIQUE(username) with composite (customer_id, username)."""
    if not _table_exists(db, "users"):
        return
    if _index_exists(db, "uq_users_customer_username"):
        return

    legacy_cols = db.execute("PRAGMA table_info(users)").fetchall()
    legacy_names = [c[1] for c in legacy_cols]
    if "customer_id" not in legacy_names:
        _ensure_column(db, "users", "customer_id", "INTEGER")

    db.execute("ALTER TABLE users RENAME TO users_legacy_username_unique")
    db.execute(
        """
        CREATE TABLE users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT,
            role TEXT,
            status TEXT,
            workflow_role TEXT,
            employee_name TEXT,
            department TEXT,
            designation_id INTEGER,
            reporting_manager TEXT,
            staff_id INTEGER,
            customer_id INTEGER,
            company_id INTEGER,
            branch_id INTEGER,
            UNIQUE(customer_id, username)
        )
        """
    )
    new_cols = [c[1] for c in db.execute("PRAGMA table_info(users)").fetchall() if c[1] != "id"]
    legacy_cols = [c[1] for c in db.execute("PRAGMA table_info(users_legacy_username_unique)").fetchall()]
    shared = [c for c in new_cols if c in legacy_cols]
    if shared:
        col_sql = ", ".join(shared)
        db.execute(
            f"INSERT INTO users({col_sql}) SELECT {col_sql} FROM users_legacy_username_unique"
        )
    db.execute("DROP TABLE users_legacy_username_unique")
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_customer_username "
        "ON users(customer_id, username)"
    )


def get_tenant_context(session=None, jwt_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "customer_id": None,
        "company_id": None,
        "branch_id": None,
        "company_code": None,
    }
    if jwt_payload:
        ctx["customer_id"] = jwt_payload.get("customer_id")
        ctx["company_code"] = jwt_payload.get("company_code")
    elif session:
        ctx["customer_id"] = session.get("customer_id")
        ctx["company_code"] = session.get("company_code")
        ctx["branch_id"] = session.get("branch_id")
        ctx["company_id"] = session.get("company_id")
    return ctx


def tenant_where_clause(
    table_alias: str,
    ctx: dict[str, Any],
    *,
    include_branch: bool = False,
) -> tuple[str, list[Any]]:
    """Build SQL WHERE fragment scoped to tenant when customer_id is set."""
    if not ctx.get("customer_id"):
        return "", []
    prefix = f"{table_alias}." if table_alias else ""
    clauses = [f"{prefix}customer_id=?"]
    params: list[Any] = [ctx["customer_id"]]
    if include_branch and ctx.get("branch_id"):
        clauses.append(f"({prefix}branch_id IS NULL OR {prefix}branch_id=?)")
        params.append(ctx["branch_id"])
    return " AND ".join(clauses), params
