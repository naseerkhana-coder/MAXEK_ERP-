"""Fixed assets — register, transfer, depreciation."""

from datetime import datetime

import streamlit as st

from modules.database import (
    DATE_FMT,
    DATE_INPUT_FMT,
    load_asset_depreciation,
    load_asset_transfers,
    load_assets,
    save_asset,
    save_asset_depreciation,
    save_asset_transfer,
)


def _actor():
    return st.session_state.get("user_name", "User")


def page_asset_register():
    st.subheader("Asset Register")
    st.caption("Company fixed assets — plant, machinery, vehicles, and equipment.")

    tab_add, tab_list = st.tabs(["Add Asset", "Asset List"])
    with tab_add:
        with st.form("asset_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            code = c1.text_input("Asset code")
            name = c2.text_input("Asset name")
            c3, c4 = st.columns(2)
            purchase_date = c3.date_input("Purchase date", value=None, format=DATE_INPUT_FMT)
            cost = c4.number_input("Cost (Rs)", min_value=0.0, step=1000.0, value=0.0)
            c5, c6 = st.columns(2)
            location = c5.text_input("Location")
            assigned = c6.text_input("Assigned to")
            status = st.selectbox("Status", ["Active", "Disposed", "Under maintenance"])
            if st.form_submit_button("SAVE ASSET", type="primary", use_container_width=True):
                if not name.strip():
                    st.error("Asset name is required.")
                else:
                    save_asset(
                        {
                            "asset_code": code.strip(),
                            "asset_name": name.strip(),
                            "purchase_date": purchase_date.strftime(DATE_FMT) if purchase_date else "",
                            "cost": cost,
                            "location": location.strip(),
                            "assigned_to": assigned.strip(),
                            "status": status,
                        }
                    )
                    st.success("Asset saved.")
                    st.rerun()

    with tab_list:
        df = load_assets()
        if df.empty:
            st.info("No assets registered yet.")
        else:
            st.metric("Total asset cost", f"Rs {float(df['cost'].sum()):,.2f}")
            st.dataframe(df, use_container_width=True, hide_index=True)


def page_asset_transfer():
    st.subheader("Asset Transfer")
    st.caption("Move assets between locations or assignees.")

    assets = load_assets()
    asset_options = [""]
    asset_map = {}
    if not assets.empty:
        for _, r in assets.iterrows():
            label = f"{r['asset_code']} | {r['asset_name']} @ {r['location'] or '—'}"
            asset_options.append(label)
            asset_map[label] = r.to_dict()

    with st.form("asset_transfer_form", clear_on_submit=True):
        sel = st.selectbox("Asset", asset_options)
        row = asset_map.get(sel, {})
        c1, c2 = st.columns(2)
        from_loc = c1.text_input("From location", value=row.get("location", ""))
        to_loc = c2.text_input("To location")
        transfer_date = st.date_input("Transfer date", value=datetime.now().date(), format=DATE_INPUT_FMT)
        remarks = st.text_input("Remarks")
        if st.form_submit_button("RECORD TRANSFER", type="primary", use_container_width=True):
            if not sel or not row.get("asset_id"):
                st.error("Select an asset.")
            elif not to_loc.strip():
                st.error("To location is required.")
            else:
                save_asset_transfer(
                    {
                        "asset_id": row["asset_id"],
                        "from_location": from_loc.strip(),
                        "to_location": to_loc.strip(),
                        "transfer_date": transfer_date.strftime(DATE_FMT),
                        "remarks": remarks.strip(),
                    },
                    _actor(),
                )
                st.success("Asset transfer recorded.")
                st.rerun()

    st.divider()
    hist = load_asset_transfers()
    if hist.empty:
        st.info("No transfers yet.")
    else:
        st.dataframe(hist, use_container_width=True, hide_index=True)


def page_asset_depreciation():
    st.subheader("Depreciation")
    st.caption("Record periodic depreciation by asset.")

    assets = load_assets()
    asset_options = [""]
    asset_map = {}
    if not assets.empty:
        for _, r in assets.iterrows():
            label = f"{r['asset_code']} | {r['asset_name']}"
            asset_options.append(label)
            asset_map[label] = r.to_dict()

    with st.form("depreciation_form", clear_on_submit=True):
        sel = st.selectbox("Asset", asset_options)
        row = asset_map.get(sel, {})
        c1, c2 = st.columns(2)
        period = c1.text_input("Period (e.g. FY2025-26 / Mar-2026)")
        amount = c2.number_input("Depreciation amount (Rs)", min_value=0.0, step=100.0, value=0.0)
        remarks = st.text_input("Remarks")
        if st.form_submit_button("SAVE DEPRECIATION", type="primary", use_container_width=True):
            if not row.get("asset_id"):
                st.error("Select an asset.")
            elif amount <= 0:
                st.error("Amount must be greater than zero.")
            else:
                save_asset_depreciation(
                    {
                        "asset_id": row["asset_id"],
                        "period": period.strip(),
                        "amount": amount,
                        "remarks": remarks.strip(),
                    },
                    _actor(),
                )
                st.success("Depreciation recorded.")
                st.rerun()

    st.divider()
    hist = load_asset_depreciation()
    if hist.empty:
        st.info("No depreciation entries yet.")
    else:
        st.dataframe(hist, use_container_width=True, hide_index=True)
