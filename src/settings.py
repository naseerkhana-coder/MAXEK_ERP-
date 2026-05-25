import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / "database"
DB_PATH = DB_DIR / "maxek_payroll.db"
BACKUP_DIR = DB_DIR / "backup"
PHOTOS_DIR = BASE_DIR / "photos"
WORKER_PHOTOS = PHOTOS_DIR / "workers"
SUBCONTRACTOR_PHOTOS = PHOTOS_DIR / "subcontractors"
REPORTS_DIR = BASE_DIR / "reports"
EXCEL_REPORTS = REPORTS_DIR / "excel"
PDF_REPORTS = REPORTS_DIR / "pdf"
ATTENDANCE_REPORTS = REPORTS_DIR / "attendance"
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
BACKGROUND_DIR = ASSETS_DIR / "background"
TEMP_DIR = BASE_DIR / "temp"

for path in (
    DB_DIR,
    BACKUP_DIR,
    WORKER_PHOTOS,
    SUBCONTRACTOR_PHOTOS,
    EXCEL_REPORTS,
    PDF_REPORTS,
    ATTENDANCE_REPORTS,
    ICONS_DIR,
    BACKGROUND_DIR,
    TEMP_DIR,
):
    path.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admin (
            username TEXT PRIMARY KEY,
            password TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS subcontractors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sub_code TEXT UNIQUE,
            sub_name TEXT,
            joining_date TEXT,
            bank_account TEXT,
            bank_name TEXT,
            ifsc_code TEXT,
            branch_name TEXT,
            date_of_birth TEXT,
            region TEXT,
            pan_number TEXT,
            contact_number TEXT
        )
        """
    )
    _ensure_subcontractor_columns(cursor)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT UNIQUE,
            sub_code TEXT,
            worker_name TEXT,
            age INTEGER,
            trade TEXT,
            joining_date TEXT,
            salary REAL,
            working_hr REAL,
            overtime_rate REAL,
            photo TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT,
            date TEXT,
            start_time TEXT,
            end_time TEXT,
            break_time REAL,
            worked_hours REAL,
            overtime REAL,
            project_name TEXT
        )
        """
    )
    cursor.execute("SELECT * FROM admin LIMIT 1")
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO admin (username, password) VALUES (?, ?)", ("admin", "1234"))
    conn.commit()


def _ensure_subcontractor_columns(cursor: sqlite3.Cursor) -> None:
    for column_definition in (
        "bank_name TEXT",
        "ifsc_code TEXT",
        "branch_name TEXT",
        "date_of_birth TEXT",
        "region TEXT",
    ):
        column_name = column_definition.split()[0]
        try:
            cursor.execute(f"ALTER TABLE subcontractors ADD COLUMN {column_definition}")
        except sqlite3.OperationalError:
            pass
