"""Finance screens — journal voucher and creditors."""

from datetime import datetime

import pandas as pd
import streamlit as st

from modules.database import (
    DATE_FMT,
    DATE_INPUT_FMT,
    create_manual_journal,
    get_conn,
    kpi_stats,
    load_chart_of_accounts,
    load_creditors_summary,
    load_ledger_entries,
    load_project_names,
)
from modules.roles import is_accounts_staff


def _actor():
    return st.session_state.get("user_name", "User")


def _accounts_only():
    role = st.session_state.get("user_role", "Admin")
    if not is_accounts_staff(role):
        st.warning("This screen is for Accounts roles.")
        return False
    return True


def load_journal_entries_recent(limit=50):
    conn = get_conn()
    df = pd.read_sql_query(
        """
        SELECT journal_id, document_no, entry_date, source_type, narration,
               total_debit, total_credit, posted_by, posted_at
        FROM journal_entries
        ORDER BY id DESC
        LIMIT ?
        """,
        conn,
        params=(int(limit),),
    )
    conn.close()
    return df


def page_journal_voucher():
    st.subheader("Journal Voucher")
    st.caption("Manual double-entry journal — debit must equal credit.")

    if not _accounts_only():
        return

    coa = load_chart_of_accounts()
    account_names = (
        coa["account_name"].tolist() if not coa.empty else ["Cash", "Bank", "Creditors", "General Expense"]
    )
    projects = [""] + load_project_names()

    tab_new, tab_recent, tab_ledger = st.tabs(["New JV", "Recent Journals", "Ledger Inquiry"])
    with tab_new:
        with st.form("journal_voucher_form"):
            c1, c2 = st.columns(2)
            entry_date = c1.date_input("Entry date", value=datetime.now().date(), format=DATE_INPUT_FMT)
            project = c2.selectbox("Project (optional)", projects)
            narration = st.text_area("Narration")
            st.markdown("**Line 1 — Debit**")
            d1_acc = st.selectbox("Debit account", account_names, key="jv_d1_acc")
            d1_amt = st.number_input("Debit amount", min_value=0.0, step=1.0, value=0.0, key="jv_d1_amt")
            st.markdown("**Line 2 — Credit**")
            c1_acc = st.selectbox("Credit account", account_names, key="jv_c1_acc", index=min(1, len(account_names) - 1))
            c1_amt = st.number_input("Credit amount", min_value=0.0, step=1.0, value=0.0, key="jv_c1_amt")
            party = st.text_input("Party name (optional)")
            if st.form_submit_button("POST JOURNAL", type="primary", use_container_width=True):
                lines = [
                    {"account_name": d1_acc, "debit": d1_amt, "credit": 0, "party_name": party, "remarks": narration},
                    {"account_name": c1_acc, "debit": 0, "credit": c1_amt, "party_name": party, "remarks": narration},
                ]
                try:
                    jid, doc = create_manual_journal(
                        {
                            "entry_date": entry_date.strftime(DATE_FMT),
                            "narration": narration.strip() or "Manual journal",
                            "project_name": project,
                            "lines": lines,
                        },
                        _actor(),
                    )
                    st.success(f"Journal posted: {doc} ({jid})")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with tab_recent:
        df = load_journal_entries_recent()
        if df.empty:
            st.info("No journal entries yet.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_ledger:
        acc = st.selectbox("Account", [""] + account_names, key="jv_ledger_acc")
        if acc:
            led = load_ledger_entries(account_name=acc, limit=100)
            if led.empty:
                st.info("No lines for this account.")
            else:
                st.dataframe(led, use_container_width=True, hide_index=True)


def page_creditors():
    st.subheader("Creditors")
    st.caption("Outstanding supplier / creditor balances.")

    stats = kpi_stats()
    st.metric("Total creditors (system KPI)", f"Rs {stats.get('creditors', 0):,.2f}")

    df = load_creditors_summary()
    if df.empty:
        st.info("No outstanding creditor balances from site expenses.")
    else:
        st.metric("Outstanding (detail total)", f"Rs {float(df['outstanding'].sum()):,.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True)
