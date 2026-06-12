"""Login auth helpers — bcrypt + plain text, production user schema."""
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bcrypt

from app import (
    authenticate_user,
    get_user_id,
    is_bcrypt_hash,
    user_is_active,
    verify_password,
)


def test_bcrypt_and_plain():
    plain_hash = bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode()
    assert is_bcrypt_hash(plain_hash)
    assert verify_password(plain_hash, "secret123")
    assert not verify_password(plain_hash, "wrong")
    assert verify_password("legacy", "legacy")
    assert not verify_password("legacy", "other")
    print("PASS verify_password bcrypt + plain")


def test_user_is_active_production_schema():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE users (user_id INTEGER, username TEXT, password TEXT, "
        "is_disabled INTEGER, account_locked INTEGER)"
    )
    conn.execute(
        "INSERT INTO users VALUES (1, 'active', 'x', 0, 0)"
    )
    conn.execute(
        "INSERT INTO users VALUES (2, 'disabled', 'x', 1, 0)"
    )
    conn.execute(
        "INSERT INTO users VALUES (3, 'locked', 'x', 0, 1)"
    )
    rows = {r["username"]: r for r in conn.execute("SELECT * FROM users")}
    assert user_is_active(rows["active"])
    assert not user_is_active(rows["disabled"])
    assert not user_is_active(rows["locked"])
    print("PASS user_is_active is_disabled/account_locked")


def test_authenticate_mixed_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT UNIQUE, "
            "password TEXT, role TEXT, full_name TEXT, is_disabled INTEGER DEFAULT 0, "
            "account_locked INTEGER DEFAULT 0)"
        )
        bcrypt_pw = bcrypt.hashpw(b"adminpass", bcrypt.gensalt()).decode()
        conn.execute(
            "INSERT INTO users(user_id, username, password, role, full_name) VALUES (?,?,?,?,?)",
            (1, "admin", bcrypt_pw, "Admin", "Admin User"),
        )
        conn.execute(
            "INSERT INTO users(user_id, username, password, role, full_name) VALUES (?,?,?,?,?)",
            (2, "nabeel", "plainpass", "Maker", "Nabeel"),
        )
        conn.commit()

        u1 = authenticate_user(conn, "admin", "adminpass")
        assert u1 and get_user_id(u1) == 1
        u2 = authenticate_user(conn, "nabeel", "plainpass")
        assert u2 and get_user_id(u2) == 2
        assert authenticate_user(conn, "admin", "wrong") is None
        conn.execute("UPDATE users SET is_disabled=1 WHERE username='nabeel'")
        conn.commit()
        assert authenticate_user(conn, "nabeel", "plainpass") is None
        print("PASS authenticate_user mixed bcrypt/plain + disabled")
        conn.close()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    test_bcrypt_and_plain()
    test_user_is_active_production_schema()
    test_authenticate_mixed_db()
    print("ALL LOGIN AUTH TESTS PASSED")
