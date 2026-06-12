#!/usr/bin/env python3
"""Pre-migration database compatibility check (run on VPS before switching to Gunicorn).

Usage:
  python deploy/check_db_compatibility.py [/path/to/database.db]

Default path: database/maxek_payroll.db (Streamlit production)
Flask app expects: database/maxek.db (see app.py DB_PATH)
"""
from __future__ import annotations

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Tables Flask app.py reads/writes directly (minimum for core UI)
FLASK_CORE_TABLES = [
    "users",
    "staff",
    "subcontractors",
    "clients",
    "projects",
    "workers",
    "attendance",
    "petty_cash",
    "salary",
    "designations",
    "workflow_master",
    "approval_requests",
    "approval_audit",
    "notifications",
]

# Known Streamlit/production names → Flask names
STREAMLIT_TO_FLASK = {
    "employees": "staff",
    "petty_cash_requests": "petty_cash",
    "purchase_orders": "purchase_requests",
    "workflow_audit_log": "approval_audit",
    "dashboard_notifications": "notifications",
}

FLASK_USER_COLUMNS = {
    "id", "username", "password", "role", "status",
    "employee_name", "department", "workflow_role", "designation_id",
}


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.Error:
        return set()


def main() -> int:
    db_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "database", "maxek_payroll.db")
    if not os.path.isfile(db_path):
        print(f"ERROR: Database not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }

    print("=" * 60)
    print(" MAXEK ERP — Database compatibility check")
    print("=" * 60)
    print(f"Database file: {db_path}")
    print(f"Flask expects: {os.path.join(ROOT, 'database', 'maxek.db')}")
    print(f"Tables found:  {len(tables)}")
    print()

    # 1. Flask core tables
    print("--- Flask core tables ---")
    missing_core = []
    for t in FLASK_CORE_TABLES:
        if t in tables:
            print(f"  OK      {t}")
        else:
            print(f"  MISSING {t}")
            missing_core.append(t)

    # 2. Streamlit-only names (data exists but Flask won't read them)
    print()
    print("--- Streamlit table names (need rename/migration to Flask) ---")
    rename_needed = []
    for st, fl in STREAMLIT_TO_FLASK.items():
        if st in tables and fl not in tables:
            print(f"  RENAME/MIGRATE  {st}  →  {fl}")
            rename_needed.append((st, fl))
        elif st in tables and fl in tables:
            print(f"  BOTH EXIST      {st} and {fl} (merge or pick one)")
            rename_needed.append((st, fl))
        elif st in tables:
            print(f"  STREAMLIT ONLY  {st} (Flask table {fl} missing)")

    # 3. Users / login compatibility
    print()
    print("--- Login compatibility (users table) ---")
    if "users" not in tables:
        print("  FAIL  No users table — Flask login will not work")
        login_ok = False
    else:
        cols = table_columns(conn, "users")
        missing_cols = FLASK_USER_COLUMNS - cols
        if missing_cols:
            print(f"  WARN  Missing columns (migrate_production.py may ADD): {sorted(missing_cols)}")
        else:
            print("  OK    Required user columns present")
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        active = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE status='Active'"
        ).fetchone()["c"] if "status" in cols else count
        print(f"  Users: {count} total, {active} active (status='Active')")
        sample = conn.execute(
            "SELECT username, password, role, status FROM users LIMIT 3"
        ).fetchall()
        for row in sample:
            pwd = row["password"] or ""
            pwd_hint = "plain-text" if len(pwd) < 60 and not pwd.startswith("$") else "may-be-hashed"
            print(f"    - {row['username']} role={row['role']} status={row['status']} password={pwd_hint}")
        login_ok = count > 0

    # 4. migrate_production safety
    print()
    print("--- migrate_production.py behaviour ---")
    print("  Non-destructive: CREATE TABLE IF NOT EXISTS, ALTER ADD COLUMN only")
    print("  Does NOT: DROP tables, DELETE rows, rename Streamlit tables")
    print("  Does NOT: Copy employees→staff or petty_cash_requests→petty_cash")
    print("  With MAXEK_SKIP_DEMO_SEED=1: does not overwrite demo users")

    # 5. Verdict
    print()
    print("=" * 60)
    if missing_core or rename_needed:
        print(" VERDICT: NOT READY for direct Flask cutover")
        print()
        print(" This DB has production data under Streamlit table names.")
        print(" Copying to maxek.db + migrate_production.py will:")
        print("   - Preserve users (if plain-text passwords + status column)")
        print("   - Add empty Flask workflow tables")
        print("   - NOT expose employees/petty_cash_requests data in Flask UI")
        print()
        print(" Recommended before systemd switch:")
        print("   1. Backup: cp -a database/maxek_payroll.db backups/")
        print("   2. Plan data migration (rename tables or ETL script)")
        print("   3. Or run Flask on copy: cp maxek_payroll.db maxek.db, then migrate + test")
        code = 2
    elif login_ok:
        print(" VERDICT: Schema largely compatible — test login on port 8000 before cutover")
        code = 0
    else:
        print(" VERDICT: Schema issues — do not switch systemd yet")
        code = 2

    print("=" * 60)
    conn.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
