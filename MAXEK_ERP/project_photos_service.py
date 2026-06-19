"""Project Photo Management — Phase C. Separate from DPR/BOQ core modules."""

from __future__ import annotations

import os
import re
from calendar import monthrange
from datetime import datetime
from typing import Any

PHOTO_CATEGORIES = (
    "Before Start",
    "During Execution",
    "After Completion",
    "DPR Photos",
    "Safety",
    "Quality",
    "Progress",
    "Client Visit",
    "Drone",
)

REPORT_TYPES: dict[str, str] = {
    "monthly_progress": "Monthly Progress Album",
    "client_presentation": "Client Presentation Album",
    "dpr_photo": "DPR Photo Report",
    "completion": "Completion Report",
}

CLIENT_PRESENTATION_CATEGORIES = ("Progress", "Client Visit", "Quality", "During Execution")
COMPLETION_CATEGORIES = ("Before Start", "After Completion", "During Execution")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_PHOTO_UPLOAD_BYTES = 10 * 1024 * 1024
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


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


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _file_kind(ext: str) -> str:
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext == ".pdf":
        return "pdf"
    return "other"


def validate_photo_upload(file_storage, required: bool = True) -> tuple[str | None, str | None, str | None]:
    """Return (ext, file_kind, error_message)."""
    if not file_storage or not file_storage.filename:
        if required:
            return None, None, "Select a photo or document to upload."
        return None, None, None
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None, None, "Allowed file types: JPG, PNG, PDF."
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_PHOTO_UPLOAD_BYTES:
        return None, None, "File is too large (maximum 10 MB)."
    return ext, _file_kind(ext), None


def ensure_project_photos_schema(db) -> None:
    """Idempotent project photos table (Phase C)."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS project_photos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            photo_date TEXT,
            location TEXT,
            description TEXT,
            file_path TEXT NOT NULL,
            original_filename TEXT,
            file_type TEXT,
            uploaded_by TEXT,
            created_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for col, ctype in (
        ("project_id", "INTEGER"),
        ("category", "TEXT"),
        ("photo_date", "TEXT"),
        ("location", "TEXT"),
        ("description", "TEXT"),
        ("file_path", "TEXT"),
        ("original_filename", "TEXT"),
        ("file_type", "TEXT"),
        ("uploaded_by", "TEXT"),
        ("created_at", "TEXT"),
    ):
        _ensure_column(db, "project_photos", col, ctype)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_photos_project ON project_photos(project_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_photos_date ON project_photos(photo_date)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_photos_category ON project_photos(category)"
    )


def list_projects_for_photos(db) -> list[dict[str, Any]]:
    rows = db.execute(
        """
        SELECT id, project_code, project_name
        FROM projects
        WHERE status IS NULL OR status != 'Inactive'
        ORDER BY project_name
        """
    ).fetchall()
    return [dict(r) for r in rows]


def _photo_search_sql(
    project_id: int | None = None,
    category: str = "",
    search: str = "",
    date_from: str = "",
    date_to: str = "",
    uploaded_by: str = "",
    categories: tuple[str, ...] | None = None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if project_id:
        clauses.append("pp.project_id = ?")
        params.append(project_id)
    if category:
        clauses.append("pp.category = ?")
        params.append(category)
    if categories:
        placeholders = ",".join("?" for _ in categories)
        clauses.append(f"pp.category IN ({placeholders})")
        params.extend(categories)
    if date_from:
        clauses.append("pp.photo_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("pp.photo_date <= ?")
        params.append(date_to)
    if uploaded_by:
        clauses.append("LOWER(pp.uploaded_by) LIKE ?")
        params.append(f"%{uploaded_by.lower()}%")
    if search:
        like = f"%{search.lower()}%"
        clauses.append(
            "("
            "LOWER(p.project_name) LIKE ? OR LOWER(p.project_code) LIKE ? OR "
            "LOWER(pp.location) LIKE ? OR LOWER(pp.description) LIKE ? OR "
            "LOWER(pp.uploaded_by) LIKE ? OR LOWER(pp.category) LIKE ?"
            ")"
        )
        params.extend([like, like, like, like, like, like])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def search_project_photos(
    db,
    search: str = "",
    project_id: int | None = None,
    category: str = "",
    date_from: str = "",
    date_to: str = "",
    uploaded_by: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    where, params = _photo_search_sql(
        project_id=project_id,
        category=category,
        search=search,
        date_from=date_from,
        date_to=date_to,
        uploaded_by=uploaded_by,
    )
    sql = f"""
        SELECT pp.*, p.project_code, p.project_name
        FROM project_photos pp
        JOIN projects p ON p.id = pp.project_id
        {where}
        ORDER BY pp.photo_date DESC, pp.id DESC
        LIMIT ?
    """
    params.append(limit)
    rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def list_photos_timeline(
    db,
    search: str = "",
    project_id: int | None = None,
    category: str = "",
    date_from: str = "",
    date_to: str = "",
    uploaded_by: str = "",
) -> list[dict[str, Any]]:
    """Return photos grouped by photo_date for timeline view."""
    photos = search_project_photos(
        db,
        search=search,
        project_id=project_id,
        category=category,
        date_from=date_from,
        date_to=date_to,
        uploaded_by=uploaded_by,
        limit=1000,
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for photo in photos:
        day = photo.get("photo_date") or "Undated"
        grouped.setdefault(day, []).append(photo)
    timeline = []
    for day in sorted(grouped.keys(), reverse=True):
        timeline.append({"date": day, "photos": grouped[day]})
    return timeline


def get_project_photo(db, photo_id: int) -> dict[str, Any] | None:
    row = db.execute(
        """
        SELECT pp.*, p.project_code, p.project_name
        FROM project_photos pp
        JOIN projects p ON p.id = pp.project_id
        WHERE pp.id=?
        """,
        (photo_id,),
    ).fetchone()
    return dict(row) if row else None


def save_project_photo(
    db,
    form: dict,
    stored_filename: str,
    original_filename: str,
    file_type: str,
    uploaded_by: str,
) -> int:
    project_id = int(form.get("project_id") or 0)
    if not project_id:
        raise ValueError("Select a project.")
    category = (form.get("category") or "").strip()
    if category not in PHOTO_CATEGORIES:
        raise ValueError("Select a valid photo category.")
    if not stored_filename:
        raise ValueError("File upload failed.")
    photo_date = (form.get("photo_date") or _today()).strip()
    location = (form.get("location") or "").strip()
    description = (form.get("description") or "").strip()
    now = _now_ts()
    cur = db.execute(
        """
        INSERT INTO project_photos(
            project_id, category, photo_date, location, description,
            file_path, original_filename, file_type, uploaded_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_id,
            category,
            photo_date,
            location,
            description,
            stored_filename,
            original_filename,
            file_type,
            uploaded_by,
            now,
        ),
    )
    return int(cur.lastrowid)


def delete_project_photo(db, photo_id: int, dest_dir: str) -> str | None:
    row = get_project_photo(db, photo_id)
    if not row:
        raise ValueError("Photo not found.")
    db.execute("DELETE FROM project_photos WHERE id=?", (photo_id,))
    file_path = row.get("file_path")
    if file_path:
        full = os.path.join(dest_dir, file_path)
        if os.path.isfile(full):
            try:
                os.remove(full)
            except OSError:
                pass
    return file_path


def _month_bounds(year_month: str) -> tuple[str, str]:
    """year_month as YYYY-MM -> (first day, last day)."""
    m = re.match(r"^(\d{4})-(\d{2})$", (year_month or "").strip())
    if not m:
        today = datetime.now()
        year, month = today.year, today.month
    else:
        year, month = int(m.group(1)), int(m.group(2))
    start = f"{year:04d}-{month:02d}-01"
    last_day = monthrange(year, month)[1]
    end = f"{year:04d}-{month:02d}-{last_day:02d}"
    return start, end


def photos_for_report(
    db,
    report_type: str,
    project_id: int | None = None,
    year_month: str = "",
    category: str = "",
    date_from: str = "",
    date_to: str = "",
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Return (title, photos, meta) for print report."""
    if report_type not in REPORT_TYPES:
        raise ValueError("Invalid report type.")
    title = REPORT_TYPES[report_type]
    categories: tuple[str, ...] | None = None
    meta: dict[str, Any] = {"report_type": report_type}

    if report_type == "monthly_progress":
        d_from, d_to = _month_bounds(year_month)
        meta["period"] = f"{d_from} to {d_to}"
        date_from, date_to = d_from, d_to
    elif report_type == "client_presentation":
        categories = CLIENT_PRESENTATION_CATEGORIES
        meta["categories"] = ", ".join(categories)
    elif report_type == "dpr_photo":
        category = category or "DPR Photos"
        meta["category"] = category
    elif report_type == "completion":
        categories = COMPLETION_CATEGORIES
        meta["categories"] = ", ".join(categories)

    where, params = _photo_search_sql(
        project_id=project_id,
        category=category,
        date_from=date_from,
        date_to=date_to,
        categories=categories,
    )
    sql = f"""
        SELECT pp.*, p.project_code, p.project_name
        FROM project_photos pp
        JOIN projects p ON p.id = pp.project_id
        {where}
        ORDER BY pp.category, pp.photo_date, pp.id
    """
    rows = db.execute(sql, params).fetchall()
    photos = [dict(r) for r in rows]

    project_label = "All Projects"
    if project_id:
        prow = db.execute(
            "SELECT project_code, project_name FROM projects WHERE id=?",
            (project_id,),
        ).fetchone()
        if prow:
            project_label = f"{prow['project_code'] or ''} — {prow['project_name']}".strip(" —")

    meta["project_label"] = project_label
    meta["photo_count"] = len(photos)
    meta["generated_at"] = _now_ts()
    return title, photos, meta


def photo_register_stats(db, project_id: int | None = None) -> dict[str, Any]:
    where = "WHERE project_id=?" if project_id else ""
    params: tuple[Any, ...] = (project_id,) if project_id else ()
    total = db.execute(
        f"SELECT COUNT(*) FROM project_photos {where}",
        params,
    ).fetchone()[0]
    by_cat_rows = db.execute(
        f"""
        SELECT category, COUNT(*) AS cnt
        FROM project_photos {where}
        GROUP BY category
        ORDER BY cnt DESC
        """,
        params,
    ).fetchall()
    return {
        "total": int(total or 0),
        "by_category": {r["category"]: int(r["cnt"]) for r in by_cat_rows},
    }
