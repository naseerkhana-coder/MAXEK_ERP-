"""Profile update, password change, token reset, and admin security."""

from modules.database import get_conn
from modules.notifications import build_password_reset_link_email
from modules.password_security import hash_password, verify_password, validate_password_policy
from modules.user_account import (
    admin_unlock_user_account,
    change_password,
    create_password_reset_token,
    create_password_reset_token_by_email,
    ensure_user_account_schema,
    login_allowed_for_username,
    reset_password_with_token,
    update_user_profile,
    user_must_change_password,
)


def _seed_user(conn, user_id="USR900", username="acctuser", password="OldPass-99"):
    ensure_user_account_schema(conn)
    conn.execute(
        """
        INSERT INTO users(user_id, full_name, username, password, role, mobile, email)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            "Account Test",
            username,
            hash_password(password),
            "Admin",
            "9000000000",
            "acct@test.local",
        ),
    )
    conn.commit()


def test_validate_password_policy():
    assert validate_password_policy("short") is not None
    assert validate_password_policy("NoDigitsHere!") is not None
    assert validate_password_policy("GoodPass1") is None


def test_update_profile(tmp_db):
    conn = get_conn()
    _seed_user(conn)
    conn.close()
    ok, msg = update_user_profile("USR900", full_name="Updated Name", mobile="111", email="new@test.local")
    assert ok, msg
    conn = get_conn()
    row = conn.execute(
        "SELECT full_name, mobile, email FROM users WHERE user_id = ?", ("USR900",)
    ).fetchone()
    audits = conn.execute(
        "SELECT action FROM user_account_audit WHERE user_id = ?", ("USR900",)
    ).fetchall()
    conn.close()
    assert row[0] == "Updated Name"
    assert row[2] == "new@test.local"
    assert any(a[0] == "Profile Updated" for a in audits)


def test_change_password(tmp_db):
    conn = get_conn()
    _seed_user(conn)
    conn.execute("UPDATE users SET must_change_password = 1 WHERE user_id = 'USR900'")
    conn.commit()
    conn.close()
    ok, msg = change_password("USR900", "OldPass-99", "NewPass-88")
    assert ok, msg
    assert not user_must_change_password("USR900")
    conn = get_conn()
    stored = conn.execute("SELECT password FROM users WHERE user_id = ?", ("USR900",)).fetchone()[0]
    audits = conn.execute(
        "SELECT action FROM user_account_audit WHERE user_id = ?", ("USR900",)
    ).fetchall()
    conn.close()
    assert verify_password("NewPass-88", stored)
    assert not verify_password("OldPass-99", stored)
    assert any(a[0] == "Password Changed" for a in audits)


def test_reset_password_with_token(tmp_db):
    conn = get_conn()
    _seed_user(conn)
    conn.close()
    token, _uid, err = create_password_reset_token("acctuser")
    assert token and not err
    ok, msg = reset_password_with_token(token, "TokenPass-77")
    assert ok, msg
    conn = get_conn()
    stored = conn.execute("SELECT password FROM users WHERE user_id = ?", ("USR900",)).fetchone()[0]
    conn.close()
    assert verify_password("TokenPass-77", stored)
    ok2, _ = reset_password_with_token(token, "Another-99")
    assert not ok2


def test_reset_password_token_by_email(tmp_db):
    conn = get_conn()
    _seed_user(conn)
    conn.close()
    token, uid, err = create_password_reset_token_by_email("acct@test.local")
    assert token and uid == "USR900" and not err


def test_disabled_user_login_blocked(tmp_db):
    conn = get_conn()
    _seed_user(conn)
    conn.execute("UPDATE users SET is_disabled = 1 WHERE user_id = 'USR900'")
    conn.commit()
    conn.close()
    allowed, msg = login_allowed_for_username("acctuser")
    assert not allowed
    assert "disabled" in msg.lower()


def test_unlock_user_audit(tmp_db):
    conn = get_conn()
    _seed_user(conn)
    conn.execute("UPDATE users SET account_locked = 1 WHERE user_id = 'USR900'")
    conn.commit()
    conn.close()
    ok, _ = admin_unlock_user_account("Admin", "USR900", actor_id="USR900")
    assert ok
    conn = get_conn()
    audits = conn.execute(
        "SELECT action FROM user_account_audit WHERE user_id = 'USR900'"
    ).fetchall()
    conn.close()
    assert any(a[0] == "User Unlocked" for a in audits)


def test_build_password_reset_link_email():
    subj, body = build_password_reset_link_email("alice", "https://erp.example/?reset_token=abc", 24)
    assert "alice" in body
    assert "reset_token=abc" in body
    assert "24" in body
    assert subj
