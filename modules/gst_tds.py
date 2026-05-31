"""GST and TDS screens for MAXEK ERP."""

from datetime import datetime

import streamlit as st

from modules.database import (
    DATE_FMT,
    DATE_INPUT_FMT,
    load_gst_payments,
    load_tds_deductions,
    load_tds_payments,
    save_gst_payment,
    save_tds_deduction,
    save_tds_payment,
)
from modules.roles import is_accounts_staff


def _actor():
    return st.session_state.get("user_name", "User")


def _accounts_only():
    role = st.session_state.get("user_role", "Admin")
    if not is_accounts_staff(role):
        st.warning("GST/TDS payment entry is for Accounts roles.")
        return False
    return True


def page_gst_payment():
    st.subheader("GST Payment")
    st.caption("Record GST challan payments to government. Post to ledger when marked for posting.")

    tab_new, tab_list = st.tabs(["New Payment", "Payment History"])
    with tab_new:
        if not _accounts_only():
            return
        with st.form("gst_payment_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            challan = c1.text_input("Challan / reference no.")
            period = c2.text_input("Period (e.g. Apr-2026)")
            c3, c4 = st.columns(2)
            pay_date = c3.date_input("Payment date", value=datetime.now().date(), format=DATE_INPUT_FMT)
            amount = c4.number_input("Amount (Rs)", min_value=0.0, step=100.0, value=0.0)
            post_gl = st.checkbox("Post to general ledger", value=True)
            if st.form_submit_button("SAVE GST PAYMENT", type="primary", use_container_width=True):
                if amount <= 0:
                    st.error("Amount must be greater than zero.")
                else:
                    status = "posted" if post_gl else "saved"
                    save_gst_payment(
                        {
                            "challan_no": challan.strip(),
                            "period": period.strip(),
                            "payment_date": pay_date.strftime(DATE_FMT),
                            "amount": amount,
                            "status": status,
                        },
                        _actor(),
                    )
                    st.success("GST payment saved.")
                    st.rerun()

    with tab_list:
        df = load_gst_payments()
        if df.empty:
            st.info("No GST payments recorded yet.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)


def page_tds_register():
    st.subheader("TDS Register")
    st.caption("TDS deductions on vendor payments and subcontractor bills.")

    tab_add, tab_list = st.tabs(["Record Deduction", "Deduction Register"])
    with tab_add:
        if not _accounts_only():
            return
        with st.form("tds_deduction_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            vendor = c1.text_input("Vendor / party name")
            invoice_ref = c2.text_input("Invoice reference")
            c3, c4, c5 = st.columns(3)
            section = c3.text_input("TDS section", value="194C")
            tds_pct = c4.number_input("TDS %", min_value=0.0, max_value=100.0, value=1.0, step=0.1)
            amount = c5.number_input("TDS amount (Rs)", min_value=0.0, step=10.0, value=0.0)
            post_gl = st.checkbox("Post to ledger", value=False)
            if st.form_submit_button("SAVE DEDUCTION", type="primary", use_container_width=True):
                if not vendor.strip():
                    st.error("Vendor name is required.")
                elif amount <= 0:
                    st.error("TDS amount must be greater than zero.")
                else:
                    save_tds_deduction(
                        {
                            "vendor": vendor.strip(),
                            "invoice_ref": invoice_ref.strip(),
                            "section": section.strip(),
                            "tds_pct": tds_pct,
                            "amount": amount,
                            "post_ledger": "yes" if post_gl else "no",
                        },
                        _actor(),
                    )
                    st.success("TDS deduction saved.")
                    st.rerun()

    with tab_list:
        df = load_tds_deductions()
        if df.empty:
            st.info("No TDS deductions yet.")
        else:
            st.metric("Total TDS deducted", f"Rs {float(df['amount'].sum()):,.2f}")
            st.dataframe(df, use_container_width=True, hide_index=True)


def page_tds_payment():
    st.subheader("TDS Payment")
    st.caption("TDS remittance to government (challan).")

    tab_new, tab_list = st.tabs(["New Payment", "Payment History"])
    with tab_new:
        if not _accounts_only():
            return
        with st.form("tds_payment_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            challan = c1.text_input("Challan no.")
            period = c2.text_input("Period")
            c3, c4 = st.columns(2)
            pay_date = c3.date_input("Payment date", value=datetime.now().date(), format=DATE_INPUT_FMT)
            amount = c4.number_input("Amount (Rs)", min_value=0.0, step=100.0, value=0.0)
            post_gl = st.checkbox("Post to ledger (Dr TDS Payable, Cr Bank)", value=True)
            if st.form_submit_button("SAVE TDS PAYMENT", type="primary", use_container_width=True):
                if amount <= 0:
                    st.error("Amount must be greater than zero.")
                else:
                    save_tds_payment(
                        {
                            "challan_no": challan.strip(),
                            "period": period.strip(),
                            "payment_date": pay_date.strftime(DATE_FMT),
                            "amount": amount,
                            "post_ledger": "yes" if post_gl else "no",
                        },
                        _actor(),
                    )
                    st.success("TDS payment saved.")
                    st.rerun()

    with tab_list:
        df = load_tds_payments()
        if df.empty:
            st.info("No TDS payments recorded yet.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)


def page_tds_report():
    st.subheader("TDS Report")
    st.caption("Summary of TDS deductions and payments.")
    ded = load_tds_deductions(limit=500)
    pay = load_tds_payments(limit=500)
    c1, c2 = st.columns(2)
    c1.metric("Total deducted", f"Rs {float(ded['amount'].sum()) if not ded.empty else 0:,.2f}")
    c2.metric("Total paid", f"Rs {float(pay['amount'].sum()) if not pay.empty else 0:,.2f}")
    st.markdown("#### Deductions")
    if ded.empty:
        st.info("No deductions.")
    else:
        st.dataframe(ded, use_container_width=True, hide_index=True)
    st.markdown("#### Payments")
    if pay.empty:
        st.info("No payments.")
    else:
        st.dataframe(pay, use_container_width=True, hide_index=True)
