"""Persist company, branch, and project selection per user."""

from __future__ import annotations

import json
from typing import Any

from company_master_service import list_branches, list_companies


def _table_exists(db, table: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def ensure_user_context_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_work_context(
            user_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            company_id INTEGER,
            company_code TEXT,
            branch_id INTEGER,
            branch_name TEXT,
            project_id INTEGER,
            updated_at TEXT,
            updated_by TEXT
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_dashboard_preferences(
            user_id INTEGER PRIMARY KEY,
            role_profile TEXT,
            favorite_modules TEXT,
            dashboard_cards TEXT,
            quick_actions TEXT,
            reports TEXT,
            ui_theme TEXT,
            updated_at TEXT
        )
        """
    )
    cols = {r[1] for r in db.execute("PRAGMA table_info(user_dashboard_preferences)").fetchall()}
    if "ui_theme" not in cols:
        db.execute("ALTER TABLE user_dashboard_preferences ADD COLUMN ui_theme TEXT")
        db.commit()


def load_user_context(db, user_id: int) -> dict[str, Any] | None:
    if not _table_exists(db, "user_work_context"):
        return None
    row = db.execute(
        "SELECT * FROM user_work_context WHERE user_id=?",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def save_user_context(
    db,
    user_id: int,
    *,
    customer_id: int | None = None,
    company_id: int | None = None,
    company_code: str | None = None,
    branch_id: int | None = None,
    branch_name: str | None = None,
    project_id: int | None = None,
    updated_by: str = "",
) -> dict[str, Any]:
    ensure_user_context_schema(db)
    existing = load_user_context(db, user_id) or {}
    payload = {
        "customer_id": customer_id if customer_id is not None else existing.get("customer_id"),
        "company_id": company_id if company_id is not None else existing.get("company_id"),
        "company_code": company_code if company_code is not None else existing.get("company_code"),
        "branch_id": branch_id if branch_id is not None else existing.get("branch_id"),
        "branch_name": branch_name if branch_name is not None else existing.get("branch_name"),
        "project_id": project_id if project_id is not None else existing.get("project_id"),
    }
    from datetime import datetime

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """
        INSERT INTO user_work_context(
            user_id, customer_id, company_id, company_code,
            branch_id, branch_name, project_id, updated_at, updated_by
        ) VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
            customer_id=excluded.customer_id,
            company_id=excluded.company_id,
            company_code=excluded.company_code,
            branch_id=excluded.branch_id,
            branch_name=excluded.branch_name,
            project_id=excluded.project_id,
            updated_at=excluded.updated_at,
            updated_by=excluded.updated_by
        """,
        (
            user_id,
            payload["customer_id"],
            payload["company_id"],
            payload["company_code"],
            payload["branch_id"],
            payload["branch_name"],
            payload["project_id"],
            now,
            updated_by,
        ),
    )
    db.commit()
    return payload


def apply_context_to_session(session_obj: dict, ctx: dict[str, Any] | None) -> None:
    if not ctx:
        return
    if ctx.get("company_code"):
        session_obj["company_code"] = ctx["company_code"]
    if ctx.get("company_id"):
        session_obj["company_id"] = ctx["company_id"]
    if ctx.get("customer_id"):
        session_obj["customer_id"] = ctx["customer_id"]
    if ctx.get("branch_id"):
        session_obj["branch_id"] = ctx["branch_id"]
    if ctx.get("branch_name"):
        session_obj["branch"] = ctx["branch_name"]
    if ctx.get("project_id"):
        session_obj["selected_project_id"] = ctx["project_id"]


def list_context_companies(db, customer_id: int | None) -> list[dict[str, Any]]:
    try:
        companies = list_companies(db)
        if customer_id:
            companies = [c for c in companies if c.get("customer_id") in (None, customer_id)]
        return [
            {
                "id": c["id"],
                "name": c.get("trade_name") or c.get("legal_name") or c.get("company_code") or f"Company {c['id']}",
                "code": c.get("company_code"),
            }
            for c in companies
        ]
    except Exception:
        return []


def list_context_branches(db, company_id: int | None) -> list[dict[str, Any]]:
    if not company_id:
        return []
    try:
        branches = list_branches(db, int(company_id))
        return [
            {
                "id": b["id"],
                "name": b.get("branch_name") or f"Branch {b['id']}",
                "is_head_office": bool(b.get("is_head_office")),
            }
            for b in branches
        ]
    except Exception:
        return []


def list_context_projects(db, branch_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
    if not _table_exists(db, "projects"):
        return []
    deleted = ""
    cols = [r[1] for r in db.execute("PRAGMA table_info(projects)").fetchall()]
    if "is_deleted" in cols:
        deleted = " AND (is_deleted IS NULL OR is_deleted=0)"
    branch_filter = ""
    params: list[Any] = []
    if branch_id and "branch_id" in cols:
        branch_filter = " AND branch_id=?"
        params.append(branch_id)
    params.append(limit)
    sql = (
        f"SELECT id, project_name FROM projects WHERE status != 'Closed'{deleted}{branch_filter} "
        "ORDER BY project_name LIMIT ?"
    )
    try:
        rows = db.execute(sql, tuple(params)).fetchall()
        return [{"id": r["id"], "name": r["project_name"]} for r in rows]
    except Exception:
        return []
