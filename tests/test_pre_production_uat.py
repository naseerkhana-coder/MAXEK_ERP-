"""Pre-production UAT fixes: sub bill lines, petty cash report, email templates."""

from unittest.mock import patch

from modules.database import (
    load_petty_cash_report,
    subcontractor_bill_boq_lines,
    subcontractor_bill_payroll_lines,
)
from modules.notifications import (
    build_password_reset_email,
    build_payment_released_email,
    build_user_notification_email,
    send_password_reset_email,
)


def test_payroll_lines_aggregate_hours(tmp_db):
    from modules import database as db

    conn = db.get_conn()
    conn.execute(
        """
        INSERT INTO attendance(
            employee_id, employee_name, designation, sub_contractor, attendance_date,
            total_hours, ot_hours, status, applied_rate, applied_ot_rate
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "E1",
            "Worker A",
            "Mason",
            "Sub One",
            "01/06/2026",
            8.0,
            2.0,
            "PRESENT",
            500.0,
            100.0,
        ),
    )
    conn.execute(
        """
        INSERT INTO attendance(
            employee_id, employee_name, designation, sub_contractor, attendance_date,
            total_hours, ot_hours, status, applied_rate, applied_ot_rate
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "E2",
            "Worker B",
            "Helper",
            "Sub One",
            "02/06/2026",
            4.0,
            0.0,
            "HALF DAY",
            400.0,
            80.0,
        ),
    )
    conn.commit()
    conn.close()

    lines = subcontractor_bill_payroll_lines("Sub One", "06/2026")
    assert not lines.empty
    mason = lines[lines["designation"] == "Mason"].iloc[0]
    assert mason["worked_days"] == 1
    assert mason["worked_hours"] == 8.0
    assert mason["ot_hours"] == 2.0
    assert mason["labour_amount"] == 500.0
    assert mason["ot_amount"] == 200.0


def test_boq_lines_for_measurement_month(tmp_db):
    from modules import database as db

    conn = db.get_conn()
    conn.execute(
        """
        INSERT INTO subcontractor_boq_entries(
            boq_entry_id, entry_date, subcontractor_name, project_name,
            boq_item, unit, rate, quantity, amount
        ) VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            "BQE1",
            "15/06/2026",
            "Sub Two",
            "Site A",
            "Plaster",
            "sqm",
            50.0,
            10.0,
            500.0,
        ),
    )
    conn.commit()
    conn.close()

    lines = subcontractor_bill_boq_lines("Sub Two", "06/2026")
    assert len(lines) == 1
    assert float(lines.iloc[0]["quantity"]) == 10.0
    assert float(lines.iloc[0]["amount"]) == 500.0


def test_petty_cash_report_includes_site_petty(tmp_db):
    from modules import database as db

    conn = db.get_conn()
    conn.execute(
        """
        INSERT INTO petty_cash_requests(
            request_id, request_date, project_name, requested_amount, status, reason
        ) VALUES(?,?,?,?,?,?)
        """,
        ("PCR1", "01/06/2026", "Site A", 5000.0, "Submitted", "Float"),
    )
    conn.execute(
        """
        INSERT INTO site_expenses(
            expense_id, expense_date, project_name, supplier, total_invoice_value,
            payment_source, status, expense_category
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (
            "SE1",
            "02/06/2026",
            "Site A",
            "Vendor",
            1200.0,
            "Petty Cash",
            "Draft",
            "Materials",
        ),
    )
    conn.commit()
    conn.close()

    report = load_petty_cash_report()
    types = set(report["record_type"].tolist())
    assert "Petty Cash Request" in types
    assert "Site Expense (Petty)" in types


def test_email_template_builders():
    subj, body = build_password_reset_email("alice", "Temp-99")
    assert "Password reset" in subj
    assert "alice" in body
    assert "Temp-99" in body

    subj2, body2 = build_payment_released_email("Vendor Bill", "VB-1", "Rs 1,000")
    assert "Payment released" in subj2
    assert "VB-1" in body2

    subj3, body3 = build_user_notification_email("Alert", "Please review")
    assert "Alert" in subj3
    assert "Please review" in body3


@patch("modules.notifications.send_email_notification", return_value=True)
def test_send_password_reset_email(mock_send):
    assert send_password_reset_email("user@test.local", "bob", "xYz123")
    mock_send.assert_called_once()
