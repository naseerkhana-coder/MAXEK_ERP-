"""Profit & Loss and Balance Sheet reports for Super Admin / accounts."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.database import (
    DATE_FMT,
    DATE_INPUT_FMT,
    FINANCE_STATUS_SETTLED,
    FINANCE_STATUS_SUBMITTED,
    FINANCE_STATUS_MD_APPROVED,
    get_conn,
    kpi_stats,
    load_petty_cash_balances,
    load_project_names,
    load_trial_balance,
)
from modules.roles import can_view_financial_statements, is_super_admin


def _scalar(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return float(row[0] or 0) if row else 0.0


def load_profit_loss_summary(date_from: str | None = None, date_to: str | None = None) -> dict:
    conn = get_conn()
    date_clause = ""
    params: list = []
    if date_from:
        date_clause += " AND entry_date >= ?"
        params.append(date_from)
    if date_to:
        date_clause += " AND entry_date <= ?"
        params.append(date_to)

    client_receipts = _scalar(
        conn,
        f"""
        SELECT COALESCE(SUM(amount), 0) FROM payments
        WHERE 1=1
        {date_clause.replace("entry_date", "payment_date")}
        """,
        params,
    )
    cash_receipts = _scalar(
        conn,
        f"""
        SELECT COALESCE(SUM(amount), 0) FROM finance_transactions
        WHERE transaction_type = 'cash_receipt' AND status = ?
        {date_clause.replace("entry_date", "transaction_date")}
        """,
        [FINANCE_STATUS_SETTLED] + params,
    )
    billing_income = _scalar(
        conn,
        f"""
        SELECT COALESCE(SUM(total_amount), 0) FROM client_bills
        WHERE COALESCE(status, '') IN ('Approved', 'Paid', 'Submitted')
        {date_clause.replace("entry_date", "bill_date")}
        """,
        params,
    )

    site_expenses = _scalar(
        conn,
        f"""
        SELECT COALESCE(SUM(total_invoice_value), 0) FROM site_expenses
        WHERE status = 'Approved'
        {date_clause.replace("entry_date", "expense_date")}
        """,
        params,
    )
    finance_expenses = _scalar(
        conn,
        f"""
        SELECT COALESCE(SUM(amount), 0) FROM finance_transactions
        WHERE transaction_type IN ('expense_voucher', 'payment_out', 'petty_cash_issue')
          AND status = ?
        {date_clause.replace("entry_date", "transaction_date")}
        """,
        [FINANCE_STATUS_SETTLED] + params,
    )
    legacy_expenses = _scalar(
        conn,
        f"""
        SELECT COALESCE(SUM(amount), 0) FROM expenses
        WHERE 1=1
        {date_clause.replace("entry_date", "expense_date")}
        """,
        params,
    )
    payroll_paid = _scalar(
        conn,
        f"""
        SELECT COALESCE(SUM(net_salary), COALESCE(SUM(salary), 0)) FROM payroll
        WHERE UPPER(COALESCE(salary_status, payment_status, '')) IN ('PAID', 'PAID ')
           OR UPPER(COALESCE(payment_status, '')) = 'PAID'
        {date_clause.replace("entry_date", "payroll_month")}
        """,
        params,
    )
    direct_payments = _scalar(
        conn,
        f"""
        SELECT COALESCE(SUM(amount), 0) FROM direct_payments
        WHERE status = 'Paid'
        {date_clause.replace("entry_date", "payment_date")}
        """,
        params,
    )
    subcontractor_bills = _scalar(
        conn,
        f"""
        SELECT COALESCE(SUM(net_amount), 0) FROM subcontractor_bills
        WHERE COALESCE(status, '') IN ('Approved', 'Paid', 'Submitted')
        {date_clause.replace("entry_date", "bill_date")}
        """,
        params,
    )
    conn.close()

    income_lines = [
        ("Client receipts", client_receipts),
        ("Cash / bank receipts", cash_receipts),
        ("Client billing", billing_income),
    ]
    expense_lines = [
        ("Site expenses (approved)", site_expenses),
        ("Finance vouchers & payments", finance_expenses),
        ("Legacy expenses", legacy_expenses),
        ("Payroll (paid)", payroll_paid),
        ("Direct payments", direct_payments),
        ("Subcontractor bills", subcontractor_bills),
    ]
    total_income = sum(v for _, v in income_lines)
    total_expense = sum(v for _, v in expense_lines)
    return {
        "income_lines": income_lines,
        "expense_lines": expense_lines,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_profit": total_income - total_expense,
    }


def load_balance_sheet_summary(as_of: str | None = None) -> dict:
    stats = kpi_stats()
    conn = get_conn()

    petty_df = load_petty_cash_balances()
    petty_total = float(petty_df["balance"].sum()) if not petty_df.empty and "balance" in petty_df.columns else 0.0

    pending_receivables = _scalar(
        conn,
        """
        SELECT COALESCE(SUM(total_amount), 0) FROM client_bills
        WHERE COALESCE(status, '') NOT IN ('Paid', 'Rejected', 'Cancelled')
        """,
    )
    pending_payables = _scalar(
        conn,
        """
        SELECT COALESCE(SUM(total_invoice_value), 0) FROM site_expenses
        WHERE status IN ('Submitted', 'Verified', 'PM Approved', 'Approved')
        """,
    ) + _scalar(
        conn,
        """
        SELECT COALESCE(SUM(amount), 0) FROM finance_transactions
        WHERE status IN (?, ?) AND transaction_type IN ('expense_voucher', 'payment_out')
        """,
        (FINANCE_STATUS_SUBMITTED, FINANCE_STATUS_MD_APPROVED),
    )
    staff_advances = _scalar(
        conn,
        """
        SELECT COALESCE(SUM(amount), 0) FROM employee_advance
        WHERE COALESCE(payment_status, 'Paid') IN ('Paid', 'PAID')
          AND COALESCE(deducted_payroll_id, '') = ''
        """,
    )
    sub_advances = _scalar(conn, "SELECT COALESCE(SUM(amount), 0) FROM subcontractor_advance")
    payroll_payable = _scalar(
        conn,
        """
        SELECT COALESCE(SUM(net_salary), 0) FROM payroll
        WHERE workflow_status = 'MD Approved' AND UPPER(COALESCE(payment_status, '')) != 'PAID'
        """,
    )
    conn.close()

    cash_in_hand = float(stats.get("cash_in_hand") or 0)
    asset_lines = [
        ("Cash in hand", cash_in_hand),
        ("Petty cash (sites)", petty_total),
        ("Receivables (client billing)", pending_receivables),
    ]
    liability_lines = [
        ("Payables (expenses pending payment)", pending_payables),
        ("Payroll payable", payroll_payable),
        ("Staff advances", staff_advances),
        ("Subcontractor advances", sub_advances),
    ]
    total_assets = sum(v for _, v in asset_lines)
    total_liabilities = sum(v for _, v in liability_lines)
    equity = total_assets - total_liabilities
    return {
        "asset_lines": asset_lines,
        "liability_lines": liability_lines,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "equity": equity,
        "as_of": as_of or "Today",
    }


def _access_denied():
    st.error("Profit & Loss and Balance Sheet are available to Super Admin (Owner / MD) and Accounts only.")
    st.stop()


def page_profit_loss_report():
    role = st.session_state.get("user_role", "Admin")
    if not (is_super_admin(role) or can_view_financial_statements(role)):
        _access_denied()

    st.subheader("Profit & Loss Statement")
    st.caption("Summary income and expenses from receipts, billing, payroll, and project costs.")
    c1, c2 = st.columns(2)
    d_from = c1.date_input("From date", value=None, format=DATE_INPUT_FMT, key="pl_from")
    d_to = c2.date_input("To date", value=None, format=DATE_INPUT_FMT, key="pl_to")
    df_from = d_from.strftime(DATE_FMT) if d_from else None
    df_to = d_to.strftime(DATE_FMT) if d_to else None

    summary = load_profit_loss_summary(df_from, df_to)
    m1, m2, m3 = st.columns(3)
    m1.metric("Total income", f"Rs {summary['total_income']:,.2f}")
    m2.metric("Total expenses", f"Rs {summary['total_expense']:,.2f}")
    m3.metric("Net profit / (loss)", f"Rs {summary['net_profit']:,.2f}")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Income")
        st.dataframe(
            pd.DataFrame(summary["income_lines"], columns=["Head", "Amount (Rs)"]),
            width="stretch",
            hide_index=True,
        )
    with col_b:
        st.markdown("#### Expenses")
        st.dataframe(
            pd.DataFrame(summary["expense_lines"], columns=["Head", "Amount (Rs)"]),
            width="stretch",
            hide_index=True,
        )

    projects = load_project_names()
    if projects:
        st.markdown("#### All projects")
        conn = get_conn()
        proj_df = pd.read_sql_query(
            """
            SELECT project_name, client_name, status, region, district
            FROM projects
            ORDER BY project_name
            """,
            conn,
        )
        conn.close()
        st.dataframe(proj_df, width="stretch", hide_index=True)


def page_trial_balance_report():
    role = st.session_state.get("user_role", "Admin")
    if not (is_super_admin(role) or can_view_financial_statements(role)):
        _access_denied()

    st.subheader("Trial Balance")
    st.caption("Account-wise debit and credit totals from the general ledger.")
    c1, c2 = st.columns(2)
    d_from = c1.date_input("From date", value=None, format=DATE_INPUT_FMT, key="tb_from")
    d_to = c2.date_input("To date", value=None, format=DATE_INPUT_FMT, key="tb_to")
    df_from = d_from.strftime(DATE_FMT) if d_from else None
    df_to = d_to.strftime(DATE_FMT) if d_to else None

    tb = load_trial_balance(df_from, df_to)
    if tb.empty:
        st.info("No GL activity for this period. Post journals or approve finance documents to populate the ledger.")
        return
    total_dr = float(tb["total_debit"].sum())
    total_cr = float(tb["total_credit"].sum())
    m1, m2 = st.columns(2)
    m1.metric("Total debits", f"Rs {total_dr:,.2f}")
    m2.metric("Total credits", f"Rs {total_cr:,.2f}")
    st.dataframe(tb, use_container_width=True, hide_index=True)


def page_balance_sheet_report():
    role = st.session_state.get("user_role", "Admin")
    if not (is_super_admin(role) or can_view_financial_statements(role)):
        _access_denied()

    st.subheader("Balance Sheet")
    st.caption("Assets, liabilities, and equity snapshot from ERP transactions.")
    as_of = st.date_input("As of date", value=None, format=DATE_INPUT_FMT, key="bs_as_of")
    as_of_str = as_of.strftime(DATE_FMT) if as_of else None
    summary = load_balance_sheet_summary(as_of_str)

    m1, m2, m3 = st.columns(3)
    m1.metric("Total assets", f"Rs {summary['total_assets']:,.2f}")
    m2.metric("Total liabilities", f"Rs {summary['total_liabilities']:,.2f}")
    m3.metric("Equity", f"Rs {summary['equity']:,.2f}")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Assets")
        st.dataframe(
            pd.DataFrame(summary["asset_lines"], columns=["Head", "Amount (Rs)"]),
            width="stretch",
            hide_index=True,
        )
    with col_b:
        st.markdown("#### Liabilities")
        st.dataframe(
            pd.DataFrame(summary["liability_lines"], columns=["Head", "Amount (Rs)"]),
            width="stretch",
            hide_index=True,
        )

    petty_df = load_petty_cash_balances()
    if not petty_df.empty:
        st.markdown("#### Petty cash by project")
        st.dataframe(petty_df, width="stretch", hide_index=True)
