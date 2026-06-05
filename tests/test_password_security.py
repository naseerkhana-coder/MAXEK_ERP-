"""Password hashing, verification, and login audit."""

from modules.database import get_conn, log_login_attempt
from modules.password_security import (
    hash_password,
    is_password_hashed,
    validate_password_policy,
    verify_password,
)


def test_hash_and_verify():
    stored = hash_password("Secret#1")
    assert is_password_hashed(stored)
    assert verify_password("Secret#1", stored)
    assert not verify_password("wrong", stored)


def test_legacy_plaintext_verify_and_rehash_flag():
    assert verify_password("legacy", "legacy")
    assert not is_password_hashed("legacy")


def test_password_policy():
    assert validate_password_policy("Abcd1234") is None
    assert validate_password_policy("weak") is not None


def test_login_history_logged(tmp_db):
    log_login_attempt("admin", True, ip_address="127.0.0.1")
    log_login_attempt("admin", False)
    conn = get_conn()
    rows = conn.execute(
        "SELECT username, success FROM login_history ORDER BY id"
    ).fetchall()
    conn.close()
    assert len(rows) >= 2
    assert rows[-2][1] == 1
    assert rows[-1][1] == 0
