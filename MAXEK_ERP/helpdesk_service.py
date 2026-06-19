"""Help Desk / Support — user manuals, tutorial videos, and topic registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

HELP_TOPIC_CATEGORIES = (
    "General",
    "Projects",
    "Payroll",
    "Store & Purchase",
    "Plant",
    "Accounts",
    "Admin",
    "Other",
)
HELP_TOPIC_STATUSES = ("Active", "Inactive")

HELP_DESK_SUBTOOLBAR = (
    {
        "endpoint": "help_desk",
        "label": "Help Topics",
        "icon": "fa-book-open",
        "active_endpoints": ["help_desk"],
    },
    {
        "endpoint": "help_contact",
        "label": "Contact Support",
        "icon": "fa-headset",
        "active_endpoints": ["help_contact"],
    },
    {
        "endpoint": "help_desk_admin",
        "label": "Manage Topics",
        "icon": "fa-pen-to-square",
        "active_endpoints": ["help_desk_admin"],
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


def ensure_helpdesk_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS help_topics(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT DEFAULT 'General',
            description TEXT,
            manual_url TEXT,
            video_url TEXT,
            sort_order INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT
        )
        """
    )
    for col, ctype in (
        ("title", "TEXT"),
        ("category", "TEXT DEFAULT 'General'"),
        ("description", "TEXT"),
        ("manual_url", "TEXT"),
        ("video_url", "TEXT"),
        ("sort_order", "INTEGER DEFAULT 0"),
        ("status", "TEXT DEFAULT 'Active'"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "help_topics", col, ctype)
    count = db.execute("SELECT COUNT(*) FROM help_topics").fetchone()[0]
    if count == 0:
        now = _now_ts()
        seeds = (
            (
                "Getting Started with MAXEK ERP",
                "General",
                "Overview of navigation, departments, and daily workflows.",
                "",
                "",
                1,
            ),
            (
                "Project & DPR Workflow",
                "Projects",
                "How to create projects, enter DPR, and track billing readiness.",
                "",
                "",
                2,
            ),
            (
                "Payroll Generation Guide",
                "Payroll",
                "Step-by-step payroll run, draft save, and payment processing.",
                "",
                "",
                3,
            ),
        )
        for title, category, description, manual_url, video_url, sort_order in seeds:
            db.execute(
                """
                INSERT INTO help_topics(
                    title, category, description, manual_url, video_url,
                    sort_order, status, created_by, created_at, modified_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'Active', 'system', ?, ?)
                """,
                (title, category, description, manual_url, video_url, sort_order, now, now),
            )


def list_help_topics(
    db,
    search: str = "",
    category_filter: str = "",
    status_filter: str = "Active",
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    if not _table_exists(db, "help_topics"):
        return []
    clauses = ["1=1"]
    params: list[Any] = []
    if search:
        clauses.append("(title LIKE ? OR description LIKE ? OR category LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    if category_filter:
        clauses.append("category=?")
        params.append(category_filter)
    if status_filter and not include_inactive:
        clauses.append("status=?")
        params.append(status_filter)
    elif include_inactive and status_filter:
        clauses.append("status=?")
        params.append(status_filter)
    sql = f"""
        SELECT * FROM help_topics
        WHERE {' AND '.join(clauses)}
        ORDER BY sort_order ASC, title COLLATE NOCASE ASC
    """
    return [dict(row) for row in db.execute(sql, params).fetchall()]


def get_help_topic(db, topic_id: int | None) -> dict[str, Any] | None:
    if not topic_id or not _table_exists(db, "help_topics"):
        return None
    row = db.execute("SELECT * FROM help_topics WHERE id=?", (topic_id,)).fetchone()
    return dict(row) if row else None


def save_help_topic(
    db,
    form: dict,
    username: str,
    topic_id: int | None = None,
) -> int:
    title = (form.get("title") or "").strip()
    if not title:
        raise ValueError("Topic title is required.")
    category = (form.get("category") or "General").strip()
    if category not in HELP_TOPIC_CATEGORIES:
        raise ValueError("Invalid category.")
    status = (form.get("status") or "Active").strip()
    if status not in HELP_TOPIC_STATUSES:
        raise ValueError("Invalid status.")
    try:
        sort_order = int(form.get("sort_order") or 0)
    except ValueError as exc:
        raise ValueError("Sort order must be a number.") from exc
    now = _now_ts()
    payload = (
        title,
        category,
        (form.get("description") or "").strip(),
        (form.get("manual_url") or "").strip(),
        (form.get("video_url") or "").strip(),
        sort_order,
        status,
        now,
    )
    if topic_id:
        db.execute(
            """
            UPDATE help_topics SET
                title=?, category=?, description=?, manual_url=?, video_url=?,
                sort_order=?, status=?, modified_at=?
            WHERE id=?
            """,
            (*payload, topic_id),
        )
        return topic_id
    db.execute(
        """
        INSERT INTO help_topics(
            title, category, description, manual_url, video_url,
            sort_order, status, created_by, created_at, modified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (*payload, username, now),
    )
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def delete_help_topic(db, topic_id: int) -> None:
    if not get_help_topic(db, topic_id):
        raise ValueError("Help topic not found.")
    db.execute("DELETE FROM help_topics WHERE id=?", (topic_id,))
