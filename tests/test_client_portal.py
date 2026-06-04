"""Client portal — project scoping and bill approval workflow."""

from __future__ import annotations

from modules.client_portal_db import (
    CLIENT_REVIEW_PENDING,
    CLIENT_REVIEW_REJECTED,
    BILL_STATUS_CLIENT_APPROVED,
    BILL_STATUS_CLIENT_REJECTED,
    BILL_STATUS_PENDING_CLIENT,
    approve_client_bill,
    assign_client_project,
    authenticate_portal_user,
    client_assigned_project_ids,
    create_portal_user,
    ensure_client_portal_schema,
    get_client_bill_for_portal,
    project_belongs_to_client,
    reject_client_bill,
    submit_bill_for_client_review,
)
from modules.database import get_conn


def _seed_client_and_project(conn, *, client_id="CLI-TEST", project_id="PRJ-TEST"):
    conn.execute(
        """
        INSERT INTO clients(client_id, client_name, email, mobile, status)
        VALUES(?,?,?,?,?)
        """,
        (client_id, "Test Client Ltd", "client@test.com", "9999999999", "Active"),
    )
    conn.execute(
        """
        INSERT INTO projects(project_id, project_name, client_name, status)
        VALUES(?,?,?,?)
        """,
        (project_id, "Test Tower", "Test Client Ltd", "Active"),
    )
    conn.commit()


def _seed_bill(conn, *, bill_id="CBL-TEST", client_name="Test Client Ltd", project_name="Test Tower"):
    conn.execute(
        """
        INSERT INTO client_bills(
            bill_id, bill_no, bill_date, client_name, project_name,
            total_amount, status, created_by, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            bill_id,
            "CB-001",
            "01/01/2026",
            client_name,
            project_name,
            100000.0,
            "Generated",
            "Tester",
            "01/01/2026 10:00:00",
        ),
    )
    conn.commit()


def test_project_scoping_only_assigned_projects(tmp_db):
    ensure_client_portal_schema()
    conn = get_conn()
    _seed_client_and_project(conn, client_id="CLI-A", project_id="PRJ-A")
    conn.execute(
        """
        INSERT INTO projects(project_id, project_name, client_name, status)
        VALUES(?,?,?,?)
        """,
        ("PRJ-OTHER", "Other Site", "Test Client Ltd", "Active"),
    )
    conn.commit()
    conn.close()

    assign_client_project("CLI-A", "PRJ-A", "Test Tower", assigned_by="Admin")
    assert project_belongs_to_client("CLI-A", project_id="PRJ-A")
    assert not project_belongs_to_client("CLI-A", project_id="PRJ-OTHER")
    assert "PRJ-A" in client_assigned_project_ids("CLI-A")


def test_bill_approval_state_machine(tmp_db):
    ensure_client_portal_schema()
    conn = get_conn()
    _seed_client_and_project(conn)
    _seed_bill(conn)
    conn.close()

    assign_client_project("CLI-TEST", "PRJ-TEST", "Test Tower")
    create_portal_user(
        "CLI-TEST",
        email="portal@test.com",
        mobile="8888888888",
        password="SecurePass1",
        display_name="Portal User",
    )

    ok, err = submit_bill_for_client_review("CBL-TEST", actor="Accounts")
    assert ok, err
    bill = get_client_bill_for_portal("CLI-TEST", "CBL-TEST", "Test Client Ltd")
    assert bill is not None
    assert bill["client_review_status"] == CLIENT_REVIEW_PENDING
    assert bill["status"] == BILL_STATUS_PENDING_CLIENT

    ok, err = approve_client_bill(
        "CBL-TEST",
        "CLI-TEST",
        "Test Client Ltd",
        portal_user_id="CPU-???",
        display_name="Portal User",
        comment="Looks good",
    )
    assert ok, err
    bill = get_client_bill_for_portal("CLI-TEST", "CBL-TEST", "Test Client Ltd")
    assert bill["status"] == BILL_STATUS_CLIENT_APPROVED

    conn = get_conn()
    _seed_bill(conn, bill_id="CBL-REJ", project_name="Test Tower")
    conn.close()
    submit_bill_for_client_review("CBL-REJ", actor="Accounts")
    ok, err = reject_client_bill(
        "CBL-REJ",
        "CLI-TEST",
        "Test Client Ltd",
        display_name="Portal User",
        comment="Rates incorrect",
    )
    assert ok, err
    bill = get_client_bill_for_portal("CLI-TEST", "CBL-REJ", "Test Client Ltd")
    assert bill["status"] == BILL_STATUS_CLIENT_REJECTED
    assert bill["client_review_status"] == CLIENT_REVIEW_REJECTED


def test_reject_requires_comment(tmp_db):
    ensure_client_portal_schema()
    conn = get_conn()
    _seed_client_and_project(conn)
    _seed_bill(conn, bill_id="CBL-NOCMT")
    conn.close()
    assign_client_project("CLI-TEST", "PRJ-TEST", "Test Tower")
    submit_bill_for_client_review("CBL-NOCMT", actor="Accounts")
    ok, err = reject_client_bill("CBL-NOCMT", "CLI-TEST", "Test Client Ltd", comment="")
    assert not ok
    assert "comment" in err.lower()


def test_portal_login_email_or_mobile(tmp_db):
    ensure_client_portal_schema()
    conn = get_conn()
    _seed_client_and_project(conn)
    conn.close()
    create_portal_user(
        "CLI-TEST",
        email="login@test.com",
        mobile="7777777777",
        password="SecurePass1",
    )
    user, err = authenticate_portal_user("login@test.com", "SecurePass1")
    assert user and not err
    user2, err2 = authenticate_portal_user("7777777777", "SecurePass1")
    assert user2 and not err2
    bad, err3 = authenticate_portal_user("login@test.com", "wrong")
    assert bad is None
    assert err3
