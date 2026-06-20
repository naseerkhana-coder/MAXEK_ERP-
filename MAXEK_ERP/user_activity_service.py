"""User activity monitoring — login sessions, page views, and idle time reports."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

# Default idle threshold (minutes) when gap between page views exceeds this value.
DEFAULT_IDLE_THRESHOLD_MINUTES = 15

# Retention policy (days) — document for ops; optional purge via purge_old_activity().
DEFAULT_RETENTION_DAYS = 90

_PAGE_ACTIVITY_SKIP_PREFIXES = (
    "/static/",
    "/favicon",
    "/api/",
    "/health",
    "/_debug",
)

_PAGE_ACTIVITY_SKIP_ENDPOINTS = frozenset(
    {
        "static",
        "login",
        "logout",
        "forgot_password",
        "index",
    }
)


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt, size in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(text[:size], fmt)
        except ValueError:
            continue
    return None


def _format_duration(seconds: int | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def parse_user_agent(user_agent: str | None) -> tuple[str, str]:
    """Return (browser, device_name) from User-Agent header."""
    ua = (user_agent or "").strip()
    if not ua:
        return "Unknown", "Unknown"

    browser = "Unknown"
    lowered = ua.lower()
    if "edg/" in lowered or "edge/" in lowered:
        browser = "Edge"
    elif "opr/" in lowered or "opera" in lowered:
        browser = "Opera"
    elif "chrome/" in lowered and "chromium" not in lowered:
        browser = "Chrome"
    elif "firefox/" in lowered:
        browser = "Firefox"
    elif "safari/" in lowered and "chrome" not in lowered:
        browser = "Safari"
    elif "msie" in lowered or "trident/" in lowered:
        browser = "Internet Explorer"

    device = "Desktop"
    if "mobile" in lowered or "iphone" in lowered or "android" in lowered:
        device = "Mobile"
    elif "ipad" in lowered or "tablet" in lowered:
        device = "Tablet"

    return browser, device


def ensure_user_activity_schema(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_login_sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            employee_name TEXT,
            role TEXT,
            login_date TEXT,
            login_time TEXT NOT NULL,
            logout_time TEXT,
            total_session_seconds INTEGER,
            ip_address TEXT,
            device_name TEXT,
            browser TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_login_sessions_user
        ON user_login_sessions(user_id, login_time)
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_page_activity(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            employee_name TEXT,
            session_id INTEGER,
            module_name TEXT,
            page_path TEXT,
            endpoint TEXT,
            viewed_at TEXT NOT NULL,
            duration_seconds INTEGER,
            FOREIGN KEY (session_id) REFERENCES user_login_sessions(id)
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_page_activity_user
        ON user_page_activity(user_id, viewed_at)
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_idle_periods(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            employee_name TEXT,
            session_id INTEGER,
            idle_start TEXT NOT NULL,
            idle_end TEXT,
            idle_seconds INTEGER,
            FOREIGN KEY (session_id) REFERENCES user_login_sessions(id)
        )
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_idle_periods_user
        ON user_idle_periods(user_id, idle_start)
        """
    )


def log_login(
    db,
    *,
    user_id: int,
    employee_name: str | None,
    role: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> int:
    ensure_user_activity_schema(db)
    now = datetime.now()
    login_date = now.strftime("%Y-%m-%d")
    login_time = now.strftime("%Y-%m-%d %H:%M:%S")
    browser, device = parse_user_agent(user_agent)
    cur = db.execute(
        """
        INSERT INTO user_login_sessions(
            user_id, employee_name, role, login_date, login_time,
            ip_address, device_name, browser, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            user_id,
            employee_name or "",
            role or "",
            login_date,
            login_time,
            ip_address or "",
            device,
            browser,
            login_time,
        ),
    )
    db.commit()
    return int(cur.lastrowid)


def log_logout(db, session_id: int | None) -> None:
    if not session_id:
        return
    ensure_user_activity_schema(db)
    row = db.execute(
        "SELECT login_time FROM user_login_sessions WHERE id=? AND logout_time IS NULL",
        (session_id,),
    ).fetchone()
    if not row:
        return
    logout_time = _now_ts()
    login_dt = _parse_ts(row["login_time"])
    logout_dt = _parse_ts(logout_time)
    total_seconds = None
    if login_dt and logout_dt:
        total_seconds = max(0, int((logout_dt - login_dt).total_seconds()))
    db.execute(
        """
        UPDATE user_login_sessions
        SET logout_time=?, total_session_seconds=?
        WHERE id=? AND logout_time IS NULL
        """,
        (logout_time, total_seconds, session_id),
    )
    db.commit()


def should_track_page_view(*, method: str, path: str, endpoint: str | None) -> bool:
    if method.upper() != "GET":
        return False
    if endpoint in _PAGE_ACTIVITY_SKIP_ENDPOINTS:
        return False
    normalized = path or ""
    for prefix in _PAGE_ACTIVITY_SKIP_PREFIXES:
        if normalized.startswith(prefix):
            return False
    if re.search(r"\.(css|js|png|jpg|jpeg|gif|svg|ico|woff2?|map)$", normalized, re.I):
        return False
    return True


def resolve_module_name(endpoint: str | None, nav_group_label: str | None) -> str:
    if nav_group_label:
        return nav_group_label
    if endpoint:
        return endpoint.replace("_", " ").title()
    return "Unknown"


def _record_idle_gap(
    db,
    *,
    user_id: int,
    employee_name: str,
    session_id: int | None,
    idle_start: datetime,
    idle_end: datetime,
    threshold_seconds: int,
) -> None:
    gap = int((idle_end - idle_start).total_seconds())
    if gap < threshold_seconds:
        return
    db.execute(
        """
        INSERT INTO user_idle_periods(
            user_id, employee_name, session_id, idle_start, idle_end, idle_seconds
        ) VALUES (?,?,?,?,?,?)
        """,
        (
            user_id,
            employee_name,
            session_id,
            idle_start.strftime("%Y-%m-%d %H:%M:%S"),
            idle_end.strftime("%Y-%m-%d %H:%M:%S"),
            gap,
        ),
    )


def log_page_view(
    db,
    *,
    user_id: int,
    employee_name: str | None,
    session_id: int | None,
    module_name: str,
    page_path: str,
    endpoint: str | None,
    idle_threshold_minutes: int = DEFAULT_IDLE_THRESHOLD_MINUTES,
    last_page_activity_id: int | None = None,
    last_viewed_at: str | None = None,
) -> tuple[int, str]:
    """Log a page view; update prior view duration and idle gaps when applicable."""
    ensure_user_activity_schema(db)
    viewed_at = _now_ts()
    threshold_seconds = idle_threshold_minutes * 60
    viewed_dt = _parse_ts(viewed_at)

    if last_page_activity_id and last_viewed_at and viewed_dt:
        prev_dt = _parse_ts(last_viewed_at)
        if prev_dt:
            gap_seconds = max(0, int((viewed_dt - prev_dt).total_seconds()))
            if gap_seconds >= threshold_seconds:
                _record_idle_gap(
                    db,
                    user_id=user_id,
                    employee_name=employee_name or "",
                    session_id=session_id,
                    idle_start=prev_dt,
                    idle_end=viewed_dt,
                    threshold_seconds=threshold_seconds,
                )
                active_seconds = 0
            else:
                active_seconds = gap_seconds
            db.execute(
                "UPDATE user_page_activity SET duration_seconds=? WHERE id=?",
                (active_seconds, last_page_activity_id),
            )

    cur = db.execute(
        """
        INSERT INTO user_page_activity(
            user_id, employee_name, session_id, module_name,
            page_path, endpoint, viewed_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            user_id,
            employee_name or "",
            session_id,
            module_name,
            page_path,
            endpoint or "",
            viewed_at,
        ),
    )
    db.commit()
    return int(cur.lastrowid), viewed_at


def _date_bounds(date_from: str | None, date_to: str | None) -> tuple[str, str]:
    today = datetime.now().date()
    start = date_from or (today - timedelta(days=30)).isoformat()
    end = date_to or today.isoformat()
    return start, end


def get_activity_dashboard(
    db,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    ensure_user_activity_schema(db)
    start, end = _date_bounds(date_from, date_to)
    start_ts = f"{start} 00:00:00"
    end_ts = f"{end} 23:59:59"

    login_stats = db.execute(
        """
        SELECT
            COUNT(*) AS total_logins,
            COUNT(DISTINCT user_id) AS unique_users,
            COALESCE(SUM(total_session_seconds), 0) AS total_session_seconds
        FROM user_login_sessions
        WHERE login_time BETWEEN ? AND ?
        """,
        (start_ts, end_ts),
    ).fetchone()

    page_stats = db.execute(
        """
        SELECT COUNT(*) AS page_views, COUNT(DISTINCT user_id) AS active_users
        FROM user_page_activity
        WHERE viewed_at BETWEEN ? AND ?
        """,
        (start_ts, end_ts),
    ).fetchone()

    idle_stats = db.execute(
        """
        SELECT COALESCE(SUM(idle_seconds), 0) AS total_idle_seconds
        FROM user_idle_periods
        WHERE idle_start BETWEEN ? AND ?
        """,
        (start_ts, end_ts),
    ).fetchone()

    return {
        "date_from": start,
        "date_to": end,
        "total_logins": login_stats["total_logins"] if login_stats else 0,
        "unique_users": login_stats["unique_users"] if login_stats else 0,
        "total_session_seconds": login_stats["total_session_seconds"] if login_stats else 0,
        "page_views": page_stats["page_views"] if page_stats else 0,
        "active_users": page_stats["active_users"] if page_stats else 0,
        "total_idle_seconds": idle_stats["total_idle_seconds"] if idle_stats else 0,
    }


def get_login_report(
    db,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    ensure_user_activity_schema(db)
    start, end = _date_bounds(date_from, date_to)
    rows = db.execute(
        """
        SELECT
            id, user_id, employee_name, role, login_date, login_time,
            logout_time, total_session_seconds, ip_address, device_name, browser
        FROM user_login_sessions
        WHERE login_time BETWEEN ? AND ?
        ORDER BY login_time DESC
        """,
        (f"{start} 00:00:00", f"{end} 23:59:59"),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["total_time_display"] = _format_duration(item.get("total_session_seconds"))
        result.append(item)
    return result


def get_screen_activity_report(
    db,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    ensure_user_activity_schema(db)
    start, end = _date_bounds(date_from, date_to)
    rows = db.execute(
        """
        SELECT
            user_id,
            employee_name,
            module_name,
            SUM(COALESCE(duration_seconds, 0)) AS time_spent_seconds,
            COUNT(*) AS page_views
        FROM user_page_activity
        WHERE viewed_at BETWEEN ? AND ?
        GROUP BY user_id, employee_name, module_name
        ORDER BY time_spent_seconds DESC, employee_name ASC
        """,
        (f"{start} 00:00:00", f"{end} 23:59:59"),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["time_spent_display"] = _format_duration(item.get("time_spent_seconds"))
        result.append(item)
    return result


def get_idle_report(
    db,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    idle_threshold_minutes: int = DEFAULT_IDLE_THRESHOLD_MINUTES,
) -> list[dict[str, Any]]:
    """Per-user active vs idle minutes from page durations and recorded idle gaps."""
    ensure_user_activity_schema(db)
    start, end = _date_bounds(date_from, date_to)
    start_ts = f"{start} 00:00:00"
    end_ts = f"{end} 23:59:59"

    active_rows = db.execute(
        """
        SELECT user_id, employee_name, SUM(COALESCE(duration_seconds, 0)) AS active_seconds
        FROM user_page_activity
        WHERE viewed_at BETWEEN ? AND ?
        GROUP BY user_id, employee_name
        """,
        (start_ts, end_ts),
    ).fetchall()

    idle_rows = db.execute(
        """
        SELECT user_id, employee_name, SUM(COALESCE(idle_seconds, 0)) AS idle_seconds
        FROM user_idle_periods
        WHERE idle_start BETWEEN ? AND ?
        GROUP BY user_id, employee_name
        """,
        (start_ts, end_ts),
    ).fetchall()

    by_user: dict[int, dict[str, Any]] = {}
    for row in active_rows:
        by_user[row["user_id"]] = {
            "user_id": row["user_id"],
            "employee_name": row["employee_name"] or "—",
            "active_seconds": int(row["active_seconds"] or 0),
            "idle_seconds": 0,
        }
    for row in idle_rows:
        entry = by_user.setdefault(
            row["user_id"],
            {
                "user_id": row["user_id"],
                "employee_name": row["employee_name"] or "—",
                "active_seconds": 0,
                "idle_seconds": 0,
            },
        )
        entry["idle_seconds"] = int(row["idle_seconds"] or 0)
        if not entry["employee_name"] or entry["employee_name"] == "—":
            entry["employee_name"] = row["employee_name"] or "—"

    result = []
    for entry in by_user.values():
        active_min = round(entry["active_seconds"] / 60, 1)
        idle_min = round(entry["idle_seconds"] / 60, 1)
        result.append(
            {
                **entry,
                "active_minutes": active_min,
                "idle_minutes": idle_min,
                "active_display": _format_duration(entry["active_seconds"]),
                "idle_display": _format_duration(entry["idle_seconds"]),
                "idle_threshold_minutes": idle_threshold_minutes,
            }
        )
    result.sort(key=lambda r: (r["employee_name"] or "").lower())
    return result


def purge_old_activity(db, retention_days: int = DEFAULT_RETENTION_DAYS) -> dict[str, int]:
    """Optional maintenance — delete rows older than retention_days."""
    ensure_user_activity_schema(db)
    cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
    counts = {}
    for table, column in (
        ("user_login_sessions", "login_time"),
        ("user_page_activity", "viewed_at"),
        ("user_idle_periods", "idle_start"),
    ):
        cur = db.execute(f"DELETE FROM {table} WHERE {column} < ?", (cutoff,))
        counts[table] = cur.rowcount
    db.commit()
    return counts
