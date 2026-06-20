"""User activity monitoring — login, page views, logout, and admin report route."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, get_db, init_db, query_db
from user_activity_service import (
    ensure_user_activity_schema,
    get_login_report,
    get_screen_activity_report,
    log_login,
    log_logout,
    log_page_view,
    should_track_page_view,
)


def _admin_id():
    row = query_db("SELECT id FROM users WHERE username=?", ("admin",), one=True)
    assert row, "admin user missing — run init_db()"
    return row["id"]


def run_tests():
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  PASS  {name}")
            passed += 1
        else:
            print(f"  FAIL  {name} — {detail}")
            failed += 1

    check("should_track_page_view skips static", not should_track_page_view(method="GET", path="/static/css/x.css", endpoint="static"))
    check("should_track_page_view skips api", not should_track_page_view(method="GET", path="/api/health", endpoint=None))
    check("should_track_page_view allows dashboard GET", should_track_page_view(method="GET", path="/dashboard", endpoint="dashboard"))
    check("should_track_page_view skips POST", not should_track_page_view(method="POST", path="/dashboard", endpoint="dashboard"))

    admin_id = None
    with app.app_context():
        init_db()
        db = get_db()
        ensure_user_activity_schema(db)
        admin_id = _admin_id()
        session_id = log_login(
            db,
            user_id=admin_id,
            employee_name="Test Admin",
            role="Admin",
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
        )
        check("log_login returns session id", session_id > 0)
        page_id, viewed_at = log_page_view(
            db,
            user_id=admin_id,
            employee_name="Test Admin",
            session_id=session_id,
            module_name="Dashboard",
            page_path="/dashboard",
            endpoint="dashboard",
        )
        check("log_page_view returns id", page_id > 0)
        check("log_page_view timestamp", bool(viewed_at))
        log_logout(db, session_id)
        login_rows = get_login_report(db)
        check("login report has row", len(login_rows) >= 1, f"got {len(login_rows)}")
        if login_rows:
            row = login_rows[0]
            check("logout recorded", row.get("logout_time") is not None)
            check("session seconds computed", (row.get("total_session_seconds") or 0) >= 0)
        screen_rows = get_screen_activity_report(db)
        check("screen report has module row", len(screen_rows) >= 1, f"got {len(screen_rows)}")

    app.config["TESTING"] = True
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["username"] = "admin"
        sess["role"] = "Admin"
        sess["workflow_role"] = "Administrator"
        sess["employee_name"] = "Administrator"
    code = client.get("/settings/user-activity").status_code
    check("GET /settings/user-activity → 200", code == 200, f"got {code}")

    before_logins = 0
    before_pages = 0
    with app.app_context():
        db = get_db()
        before_logins = db.execute("SELECT COUNT(*) AS c FROM user_login_sessions").fetchone()["c"]
        before_pages = db.execute("SELECT COUNT(*) AS c FROM user_page_activity").fetchone()["c"]

    client.get("/logout")
    login_resp = client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        follow_redirects=False,
    )
    check("POST /login redirects", login_resp.status_code in (302, 303), f"got {login_resp.status_code}")
    dash = client.get("/dashboard")
    check("GET /dashboard after login → 200", dash.status_code == 200, f"got {dash.status_code}")
    client.get("/logout")

    with app.app_context():
        db = get_db()
        after_logins = db.execute("SELECT COUNT(*) AS c FROM user_login_sessions").fetchone()["c"]
        after_pages = db.execute("SELECT COUNT(*) AS c FROM user_page_activity").fetchone()["c"]
        check("integration login session row", after_logins > before_logins, f"{before_logins} -> {after_logins}")
        check("integration page activity row", after_pages > before_pages, f"{before_pages} -> {after_pages}")

    print(f"\n{'=' * 40}\nResults: {passed} passed, {failed} failed\n")
    return failed == 0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
