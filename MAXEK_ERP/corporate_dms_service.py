"""Corporate Document Management System — Phase D (settings / admin)."""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

DEFAULT_FOLDERS = (
    "Legal",
    "HR",
    "Finance",
    "Projects",
    "Compliance",
)

DOCUMENT_TYPES = (
    "Policy",
    "Contract",
    "Certificate",
    "License",
    "Report",
    "Circular",
    "Memo",
    "Other",
)

EXPIRY_ALERT_DAYS = (90, 60, 30, 7)
MAX_DMS_UPLOAD_BYTES = 10 * 1024 * 1024
DMS_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx"}


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


def _parse_date(value: str | None) -> date | None:
    if not value or not str(value).strip():
        return None
    try:
        return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_until(expiry_str: str | None, today: date | None = None) -> int | None:
    exp = _parse_date(expiry_str)
    if not exp:
        return None
    ref = today or date.today()
    return (exp - ref).days


def _expiry_bucket(days_left: int | None) -> str | None:
    if days_left is None:
        return None
    if days_left < 0:
        return "overdue"
    for threshold in EXPIRY_ALERT_DAYS:
        if days_left <= threshold:
            return str(threshold)
    return None


def _expiry_status_label(days_left: int | None) -> str:
    if days_left is None:
        return "—"
    if days_left < 0:
        return "Expired"
    if days_left <= 7:
        return f"Due in {days_left}d"
    if days_left <= 30:
        return f"Due in {days_left}d"
    return "Valid"


def validate_dms_upload(file_storage, required: bool = True) -> tuple[str | None, str | None]:
    if not file_storage or not file_storage.filename:
        if required:
            return None, "Select a document file to upload."
        return None, None
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in DMS_ALLOWED_EXTENSIONS:
        return None, "Allowed file types: PDF, JPG, PNG, DOC, DOCX, XLS, XLSX."
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_DMS_UPLOAD_BYTES:
        return None, "File is too large (maximum 10 MB)."
    return ext, None


def ensure_corporate_dms_schema(db) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS corporate_dms_folders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER,
            sort_order INTEGER DEFAULT 0,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            FOREIGN KEY(parent_id) REFERENCES corporate_dms_folders(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS corporate_dms_documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            doc_type TEXT,
            issue_date TEXT,
            expiry_date TEXT,
            tags TEXT,
            notes TEXT,
            current_version INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY(folder_id) REFERENCES corporate_dms_folders(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS corporate_dms_versions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            version_no INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            original_filename TEXT,
            change_notes TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT,
            FOREIGN KEY(document_id) REFERENCES corporate_dms_documents(id)
        )
    """)
    for col, ctype in (
        ("parent_id", "INTEGER"),
        ("sort_order", "INTEGER DEFAULT 0"),
        ("description", "TEXT"),
        ("is_active", "INTEGER DEFAULT 1"),
        ("created_at", "TEXT"),
    ):
        _ensure_column(db, "corporate_dms_folders", col, ctype)
    for col, ctype in (
        ("folder_id", "INTEGER"),
        ("title", "TEXT"),
        ("doc_type", "TEXT"),
        ("issue_date", "TEXT"),
        ("expiry_date", "TEXT"),
        ("tags", "TEXT"),
        ("notes", "TEXT"),
        ("current_version", "INTEGER DEFAULT 1"),
        ("is_active", "INTEGER DEFAULT 1"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ):
        _ensure_column(db, "corporate_dms_documents", col, ctype)
    for col, ctype in (
        ("document_id", "INTEGER"),
        ("version_no", "INTEGER"),
        ("file_path", "TEXT"),
        ("original_filename", "TEXT"),
        ("change_notes", "TEXT"),
        ("uploaded_by", "TEXT"),
        ("uploaded_at", "TEXT"),
    ):
        _ensure_column(db, "corporate_dms_versions", col, ctype)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_dms_docs_folder ON corporate_dms_documents(folder_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_dms_docs_expiry ON corporate_dms_documents(expiry_date)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_dms_versions_doc ON corporate_dms_versions(document_id)"
    )
    _seed_default_folders(db)


def _seed_default_folders(db) -> None:
    if not _table_exists(db, "corporate_dms_folders"):
        return
    count = db.execute("SELECT COUNT(*) FROM corporate_dms_folders").fetchone()[0]
    if count:
        return
    ts = _now_ts()
    for idx, name in enumerate(DEFAULT_FOLDERS):
        db.execute(
            "INSERT INTO corporate_dms_folders(name, parent_id, sort_order, is_active, created_at) "
            "VALUES(?, NULL, ?, 1, ?)",
            (name, idx, ts),
        )


def list_folders(db, include_inactive: bool = False) -> list[dict[str, Any]]:
    clause = "" if include_inactive else " WHERE is_active=1"
    rows = db.execute(
        f"SELECT * FROM corporate_dms_folders{clause} ORDER BY sort_order, name"
    ).fetchall()
    return [dict(r) for r in rows]


def folder_tree(db) -> list[dict[str, Any]]:
    folders = list_folders(db)
    by_parent: dict[int | None, list[dict[str, Any]]] = {}
    for folder in folders:
        pid = folder.get("parent_id")
        by_parent.setdefault(pid, []).append(folder)
    for children in by_parent.values():
        children.sort(key=lambda f: (f.get("sort_order") or 0, f.get("name") or ""))

    def build(parent_id: int | None) -> list[dict[str, Any]]:
        nodes = []
        for item in by_parent.get(parent_id, []):
            node = dict(item)
            node["children"] = build(item["id"])
            nodes.append(node)
        return nodes

    return build(None)


def get_folder(db, folder_id: int) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT * FROM corporate_dms_folders WHERE id=?",
        (folder_id,),
    ).fetchone()
    return dict(row) if row else None


def save_folder(db, form, folder_id: int | None = None) -> int:
    name = (form.get("folder_name") or form.get("name") or "").strip()
    if not name:
        raise ValueError("Folder name is required.")
    parent_id = form.get("parent_id", type=int)
    description = (form.get("description") or "").strip()
    sort_order = form.get("sort_order", type=int) or 0
    ts = _now_ts()
    if folder_id:
        db.execute(
            "UPDATE corporate_dms_folders SET name=?, parent_id=?, sort_order=?, description=? "
            "WHERE id=?",
            (name, parent_id, sort_order, description, folder_id),
        )
        return folder_id
    cur = db.execute(
        "INSERT INTO corporate_dms_folders(name, parent_id, sort_order, description, is_active, created_at) "
        "VALUES(?, ?, ?, ?, 1, ?)",
        (name, parent_id, sort_order, description, ts),
    )
    return int(cur.lastrowid)


def delete_folder(db, folder_id: int) -> None:
    doc_count = db.execute(
        "SELECT COUNT(*) FROM corporate_dms_documents WHERE folder_id=? AND is_active=1",
        (folder_id,),
    ).fetchone()[0]
    if doc_count:
        raise ValueError("Folder contains documents. Move or delete documents first.")
    child_count = db.execute(
        "SELECT COUNT(*) FROM corporate_dms_folders WHERE parent_id=? AND is_active=1",
        (folder_id,),
    ).fetchone()[0]
    if child_count:
        raise ValueError("Folder has sub-folders. Remove sub-folders first.")
    db.execute("UPDATE corporate_dms_folders SET is_active=0 WHERE id=?", (folder_id,))


def _doc_search_sql(
    folder_id: int | None = None,
    doc_type: str = "",
    search: str = "",
    expiry_status: str = "",
    today: date | None = None,
) -> tuple[str, list[Any]]:
    clauses = ["d.is_active=1"]
    params: list[Any] = []
    if folder_id:
        clauses.append("d.folder_id = ?")
        params.append(folder_id)
    if doc_type:
        clauses.append("d.doc_type = ?")
        params.append(doc_type)
    if search:
        like = f"%{search.lower()}%"
        clauses.append(
            "("
            "LOWER(d.title) LIKE ? OR LOWER(COALESCE(d.tags,'')) LIKE ? OR "
            "LOWER(COALESCE(d.notes,'')) LIKE ? OR LOWER(COALESCE(f.name,'')) LIKE ?"
            ")"
        )
        params.extend([like, like, like, like])
    ref = today or date.today()
    if expiry_status == "expired":
        clauses.append("d.expiry_date IS NOT NULL AND d.expiry_date != '' AND d.expiry_date < ?")
        params.append(ref.strftime("%Y-%m-%d"))
    elif expiry_status == "expiring":
        clauses.append("d.expiry_date IS NOT NULL AND d.expiry_date != '' AND d.expiry_date >= ?")
        params.append(ref.strftime("%Y-%m-%d"))
        max_date = ref.replace(year=ref.year + 1).strftime("%Y-%m-%d")
        clauses.append("d.expiry_date <= ?")
        params.append(max_date)
    elif expiry_status == "no_expiry":
        clauses.append("(d.expiry_date IS NULL OR d.expiry_date = '')")
    where = " WHERE " + " AND ".join(clauses)
    return where, params


def search_documents(
    db,
    search: str = "",
    folder_id: int | None = None,
    doc_type: str = "",
    expiry_status: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    today = date.today()
    where, params = _doc_search_sql(folder_id, doc_type, search, expiry_status, today)
    rows = db.execute(
        f"""
        SELECT d.*, f.name AS folder_name,
               v.file_path, v.original_filename, v.version_no AS latest_version_no
        FROM corporate_dms_documents d
        JOIN corporate_dms_folders f ON f.id = d.folder_id
        LEFT JOIN corporate_dms_versions v ON v.document_id = d.id AND v.version_no = d.current_version
        {where}
        ORDER BY d.updated_at DESC, d.id DESC
        LIMIT ?
        """,
        params + [limit],
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        days = _days_until(item.get("expiry_date"), today)
        item["days_left"] = days
        item["expiry_bucket"] = _expiry_bucket(days)
        item["expiry_status"] = _expiry_status_label(days)
        items.append(item)
    if expiry_status == "expiring":
        items = [i for i in items if i.get("expiry_bucket") in {str(d) for d in EXPIRY_ALERT_DAYS}]
    return items


def get_document(db, document_id: int) -> dict[str, Any] | None:
    row = db.execute(
        """
        SELECT d.*, f.name AS folder_name
        FROM corporate_dms_documents d
        JOIN corporate_dms_folders f ON f.id = d.folder_id
        WHERE d.id=? AND d.is_active=1
        """,
        (document_id,),
    ).fetchone()
    if not row:
        return None
    doc = dict(row)
    doc["versions"] = list_document_versions(db, document_id)
    days = _days_until(doc.get("expiry_date"))
    doc["days_left"] = days
    doc["expiry_bucket"] = _expiry_bucket(days)
    doc["expiry_status"] = _expiry_status_label(days)
    return doc


def list_document_versions(db, document_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM corporate_dms_versions WHERE document_id=? ORDER BY version_no DESC",
        (document_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_version(db, version_id: int) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT * FROM corporate_dms_versions WHERE id=?",
        (version_id,),
    ).fetchone()
    return dict(row) if row else None


def save_document(
    db,
    form,
    stored_filename: str | None,
    original_filename: str | None,
    username: str,
    document_id: int | None = None,
) -> int:
    folder_id_val = form.get("folder_id", type=int)
    title = (form.get("title") or "").strip()
    if not title:
        raise ValueError("Document title is required.")
    if not folder_id_val or not get_folder(db, folder_id_val):
        raise ValueError("Select a valid folder.")
    doc_type = (form.get("doc_type") or "Other").strip()
    issue_date = (form.get("issue_date") or "").strip()[:10] or None
    expiry_date = (form.get("expiry_date") or "").strip()[:10] or None
    tags = (form.get("tags") or "").strip()
    notes = (form.get("notes") or "").strip()
    change_notes = (form.get("change_notes") or "").strip()
    ts = _now_ts()

    if document_id:
        existing = db.execute(
            "SELECT current_version FROM corporate_dms_documents WHERE id=? AND is_active=1",
            (document_id,),
        ).fetchone()
        if not existing:
            raise ValueError("Document not found.")
        new_version = int(existing[0] or 1)
        if stored_filename:
            new_version += 1
            db.execute(
                "INSERT INTO corporate_dms_versions(document_id, version_no, file_path, original_filename, "
                "change_notes, uploaded_by, uploaded_at) VALUES(?,?,?,?,?,?,?)",
                (document_id, new_version, stored_filename, original_filename, change_notes, username, ts),
            )
        db.execute(
            "UPDATE corporate_dms_documents SET folder_id=?, title=?, doc_type=?, issue_date=?, expiry_date=?, "
            "tags=?, notes=?, current_version=?, updated_at=? WHERE id=?",
            (folder_id_val, title, doc_type, issue_date, expiry_date, tags, notes, new_version, ts, document_id),
        )
        return document_id

    if not stored_filename:
        raise ValueError("Upload a document file.")
    cur = db.execute(
        "INSERT INTO corporate_dms_documents(folder_id, title, doc_type, issue_date, expiry_date, tags, notes, "
        "current_version, is_active, created_by, created_at, updated_at) VALUES(?,?,?,?,?,?,?,1,1,?,?,?)",
        (folder_id_val, title, doc_type, issue_date, expiry_date, tags, notes, username, ts, ts),
    )
    doc_id = int(cur.lastrowid)
    db.execute(
        "INSERT INTO corporate_dms_versions(document_id, version_no, file_path, original_filename, "
        "change_notes, uploaded_by, uploaded_at) VALUES(?,1,?,?,?,?,?)",
        (doc_id, stored_filename, original_filename, change_notes or "Initial upload", username, ts),
    )
    return doc_id


def delete_document(db, document_id: int) -> None:
    row = db.execute(
        "SELECT id FROM corporate_dms_documents WHERE id=? AND is_active=1",
        (document_id,),
    ).fetchone()
    if not row:
        raise ValueError("Document not found.")
    db.execute(
        "UPDATE corporate_dms_documents SET is_active=0, updated_at=? WHERE id=?",
        (_now_ts(), document_id),
    )


def collect_dms_expiry_alerts(db) -> dict[str, Any]:
    today = date.today()
    rows = db.execute(
        """
        SELECT d.id, d.title, d.doc_type, d.expiry_date, d.folder_id, f.name AS folder_name
        FROM corporate_dms_documents d
        JOIN corporate_dms_folders f ON f.id = d.folder_id
        WHERE d.is_active=1 AND d.expiry_date IS NOT NULL AND d.expiry_date != ''
        """
    ).fetchall()
    buckets: dict[str, list[dict[str, Any]]] = {str(d): [] for d in EXPIRY_ALERT_DAYS}
    overdue: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        days = _days_until(item.get("expiry_date"), today)
        item["days_left"] = days
        bucket = _expiry_bucket(days)
        if bucket == "overdue":
            overdue.append(item)
        elif bucket:
            buckets[bucket].append(item)
    total = len(overdue) + sum(len(buckets[str(d)]) for d in EXPIRY_ALERT_DAYS)
    return {
        "expiring": buckets,
        "expiring_overdue": overdue,
        "total_alerts": total,
        "alert_days": EXPIRY_ALERT_DAYS,
    }


def sync_dms_expiry_notifications(db, notify_fn) -> int:
    alerts = collect_dms_expiry_alerts(db)
    if alerts["total_alerts"] == 0:
        return 0
    admin_rows = db.execute(
        "SELECT id FROM users WHERE status='Active' AND ("
        "LOWER(COALESCE(role,'')) IN ('admin','administrator') OR "
        "LOWER(COALESCE(workflow_role,''))='administrator'"
        ")"
    ).fetchall()
    admin_ids = [row[0] for row in admin_rows]
    if not admin_ids:
        return 0
    created = 0
    all_items = list(alerts["expiring_overdue"])
    for threshold in EXPIRY_ALERT_DAYS:
        all_items.extend(alerts["expiring"].get(str(threshold), []))
    seen: set[int] = set()
    for item in all_items:
        doc_id = item.get("id")
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        days = item.get("days_left")
        if days is not None and days < 0:
            msg = (
                f"Corporate DMS document expired: {item.get('title')} "
                f"({item.get('folder_name')}) — {item.get('expiry_date')}"
            )
        else:
            msg = (
                f"Corporate DMS document expiring in {days} days: {item.get('title')} "
                f"({item.get('folder_name')}) — {item.get('expiry_date')}"
            )
        for uid in admin_ids:
            existing = db.execute(
                "SELECT id FROM notifications WHERE user_id=? AND record_table='corporate_dms_documents' "
                "AND record_id=? AND is_read=0",
                (uid, doc_id),
            ).fetchone()
            if existing:
                continue
            notify_fn(
                db,
                uid,
                msg,
                "corporate_dms_expiry",
                "corporate_dms",
                doc_id,
                "corporate_dms_documents",
            )
            created += 1
    return created


def register_stats(db, folder_id: int | None = None) -> dict[str, Any]:
    where = " WHERE d.is_active=1"
    params: list[Any] = []
    if folder_id:
        where += " AND d.folder_id=?"
        params.append(folder_id)
    total = db.execute(
        f"SELECT COUNT(*) FROM corporate_dms_documents d{where}",
        params,
    ).fetchone()[0]
    by_type_rows = db.execute(
        f"""
        SELECT COALESCE(doc_type,'Other') AS doc_type, COUNT(*) AS cnt
        FROM corporate_dms_documents d{where}
        GROUP BY COALESCE(doc_type,'Other')
        ORDER BY cnt DESC
        """,
        params,
    ).fetchall()
    return {
        "total": total,
        "by_type": {r["doc_type"]: r["cnt"] for r in by_type_rows},
    }
