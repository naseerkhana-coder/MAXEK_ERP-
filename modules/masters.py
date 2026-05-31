"""Master data entry screens for MAXEK ERP."""

from datetime import datetime

import streamlit as st

from modules.database import (
    DATE_FMT,
    load_chart_of_accounts,
    load_company_master,
    load_vendors,
    save_company_master,
    save_vendor,
)

VENDOR_TYPES = ["Supplier", "Subcontractor", "Service Provider"]


def _current_user():
    return st.session_state.get("user_name", "User")


def page_masters_company():
    st.subheader("Company Master")
    st.caption("Company profile, GST, and financial year defaults.")

    company = load_company_master()
    with st.form("company_master_form"):
        c1, c2 = st.columns(2)
        company_name = c1.text_input("Company Name", value=company.get("company_name", "MAXEK PRIVATE LIMITED"))
        gst_number = c2.text_input("GST Number", value=company.get("gst_number", ""))
        phone = c1.text_input("Phone", value=company.get("phone", ""))
        email = c2.text_input("Email", value=company.get("email", ""))
        financial_year = c1.text_input("Financial Year", value=company.get("financial_year", f"{datetime.now().year}-{datetime.now().year + 1}"))
        address = st.text_area("Address", value=company.get("address", ""))
        if st.form_submit_button("SAVE COMPANY", type="primary", use_container_width=True):
            save_company_master(
                {
                    "company_id": company.get("company_id"),
                    "company_name": company_name.strip(),
                    "gst_number": gst_number.strip(),
                    "address": address.strip(),
                    "phone": phone.strip(),
                    "email": email.strip(),
                    "financial_year": financial_year.strip(),
                },
                _current_user(),
            )
            st.success("Company master saved.")
            st.rerun()


def page_masters_vendors():
    st.subheader("Vendor Master")
    st.caption("Suppliers, subcontractors, and service providers.")

    tab_add, tab_list, tab_accounts = st.tabs(["Add / Edit", "Vendor List", "Chart of Accounts"])

    with tab_add:
        vendors_df = load_vendors()
        vendor_options = ["— New Vendor —"] + (
            vendors_df["vendor_id"].tolist() if not vendors_df.empty else []
        )
        selected = st.selectbox("Select vendor to edit", vendor_options, key="vendor_edit_select")
        row = {}
        if selected != "— New Vendor —" and not vendors_df.empty:
            match = vendors_df[vendors_df["vendor_id"] == selected]
            if not match.empty:
                row = match.iloc[0].to_dict()

        with st.form("vendor_master_form"):
            c1, c2 = st.columns(2)
            vendor_type = c1.selectbox(
                "Vendor Type",
                VENDOR_TYPES,
                index=VENDOR_TYPES.index(row.get("vendor_type", "Supplier"))
                if row.get("vendor_type") in VENDOR_TYPES
                else 0,
            )
            supplier_name = c2.text_input("Supplier Name", value=row.get("supplier_name", ""))
            gst_number = c1.text_input("GST Number", value=row.get("gst_number", ""))
            contact_person = c2.text_input("Contact Person", value=row.get("contact_person", ""))
            mobile = c1.text_input("Mobile", value=row.get("mobile", ""))
            email = c2.text_input("Email", value=row.get("email", ""))
            address = st.text_area("Address", value=row.get("address", ""))
            if st.form_submit_button("SAVE VENDOR", type="primary", use_container_width=True):
                if not supplier_name.strip():
                    st.error("Supplier name is required.")
                else:
                    vid = save_vendor(
                        {
                            "vendor_id": row.get("vendor_id"),
                            "vendor_type": vendor_type,
                            "supplier_name": supplier_name.strip(),
                            "gst_number": gst_number.strip(),
                            "contact_person": contact_person.strip(),
                            "mobile": mobile.strip(),
                            "email": email.strip(),
                            "address": address.strip(),
                            "status": row.get("status", "Active"),
                        },
                        _current_user(),
                    )
                    st.success(f"Vendor saved. ID: {vid}")
                    st.rerun()

    with tab_list:
        df = load_vendors()
        if df.empty:
            st.info("No vendors yet. Subcontractors are synced on database init.")
        else:
            st.dataframe(
                df[
                    [
                        "vendor_id",
                        "vendor_type",
                        "supplier_name",
                        "gst_number",
                        "contact_person",
                        "mobile",
                        "email",
                        "status",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

    with tab_accounts:
        coa = load_chart_of_accounts()
        if coa.empty:
            st.info("Chart of accounts will seed on first database init.")
        else:
            st.dataframe(coa, use_container_width=True, hide_index=True)
