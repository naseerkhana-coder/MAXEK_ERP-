#!/usr/bin/env python3
"""Test Flask login compatibility against production users schema (read-only).

Usage on VPS (before systemd cutover):
  cp -a database/maxek_payroll.db /tmp/maxek_login_test.db
  python deploy/test_login_compatibility.py /tmp/maxek_login_test.db
  python deploy/test_login_compatibility.py /tmp/maxek_login_test.db myuser mypassword

Does NOT modify the database file.
"""
from __future__ import annotations

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import authenticate_user, is_bcrypt_hash, verify_password, user_is_active, get_user_id


def cols(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def password_kind(value: str | None) -> str:
    if not value:
        return "empty"
    if is_bcrypt_hash(value):
        return "bcrypt"
    if value.startswith("pbkdf2:") or value.startswith("scrypt:"):
        return "werkzeug-hash"
    if len(value) <= 32:
        return "plain-text"
    return "other"


def main() -> int:
    db_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "database", "maxek_payroll.db")
    test_user = sys.argv[2] if len(sys.argv) > 2 else None
    test_pass = sys.argv[3] if len(sys.argv) > 3 else None

    if not os.path.isfile(db_path):
        print(f"ERROR: not found: {db_path}")
        return 1

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    print("=" * 60)
    print(" Flask login compatibility (read-only)")
    print("=" * 60)
    print(f"Database: {db_path}")
    print()

    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    if "users" not in tables:
        print("FAIL: no users table")
        return 1

    user_cols = cols(conn, "users")
    print("users columns:", ", ".join(user_cols))
    print()

    blockers = []

    print("--- Password handling (app.py) ---")
    print("  bcrypt ($2a$/$2b$/$2y$): bcrypt.checkpw()")
    print("  legacy: plain-text equality")
    print()

    if "password" not in user_cols:
        blockers.append("missing column: password")
    else:
        rows = conn.execute("SELECT username, password FROM users LIMIT 10").fetchall()
        kinds: dict[str, int] = {}
        for row in rows:
            k = password_kind(row["password"])
            kinds[k] = kinds.get(k, 0) + 1
        print("  Password formats (sample up to 10):")
        for k, n in sorted(kinds.items()):
            print(f"    {k}: {n}")

    print()
    print("--- Account status ---")
    if "is_disabled" in user_cols or "account_locked" in user_cols:
        print("  Using is_disabled / account_locked (production schema)")
        active = conn.execute(
            "SELECT COUNT(*) FROM users WHERE "
            "(is_disabled IS NULL OR is_disabled IN (0, '0', 'false', 'False', '')) "
            "AND (account_locked IS NULL OR account_locked IN (0, '0', 'false', 'False', ''))"
        ).fetchone()[0]
        print(f"  Unlocked & enabled users (approx): {active}")
    elif "status" in user_cols:
        print("  Using status='Active' (Flask legacy schema)")
        active = conn.execute(
            "SELECT COUNT(*) FROM users WHERE status='Active'"
        ).fetchone()[0]
        print(f"  Active users: {active}")
    else:
        blockers.append("no status or is_disabled/account_locked columns")

    if "id" not in user_cols and "user_id" not in user_cols:
        blockers.append("missing id/user_id column")
    elif "user_id" in user_cols and "id" not in user_cols:
        print("  Primary key: user_id (supported via get_user_id())")

    print()
    print("--- Credential test (authenticate_user) ---")
    if test_user and test_pass:
        user = authenticate_user(conn, test_user, test_pass)
        if user:
            uid = get_user_id(user)
            print(f"  PASS  '{test_user}' authenticated (user_id={uid})")
        else:
            print(f"  FAIL  '{test_user}' not authenticated (wrong password or account inactive)")
            return 2
    else:
        sample = conn.execute("SELECT username FROM users LIMIT 1").fetchone()
        if sample:
            user = authenticate_user(conn, sample["username"], "__invalid__")
            if user is None:
                print(f"  OK    authenticate_user() runs for user '{sample['username']}'")
            else:
                blockers.append("invalid password unexpectedly accepted")
        else:
            blockers.append("users table is empty")

    print()
    print("=" * 60)
    if blockers:
        print(" VERDICT: NOT READY")
        for b in blockers:
            print(f"   - {b}")
        print("=" * 60)
        return 2

    print(" VERDICT: COMPATIBLE — run with username/password to confirm credentials")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
