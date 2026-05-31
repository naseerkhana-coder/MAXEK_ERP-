"""Route sidebar page keys to existing module screens."""

from __future__ import annotations

import streamlit as st

from modules.billing import page_billing
from modules.dpr import page_dpr
from modules.finance import page_finance, page_finance_accounts_hub
from modules.navigation import page_label
from modules.pages import (
    page_attendance,
    page_clients_projects,
    page_employee_management,
    page_masters_users,
    page_payroll,
    page_reports,
    page_settings,
    page_subcontractors,
)
from modules.masters import page_masters_company as masters_company_form, page_masters_vendors as masters_vendors_form
from modules.store import page_store


def _open_finance(view: str):
    st.session_state.finance_view = view
    st.session_state._finance_hide_toolbar = True
    page_finance()


def _open_finance_hub(entry_type: str | None = None):
    st.session_state._finance_hub_entry_type = entry_type
    st.session_state._finance_hide_toolbar = True
    page_finance_accounts_hub(entry_type=entry_type)


def _open_settings(focus: str | None = None):
    st.session_state.settings_focus = focus
    page_settings()


def _open_clients(tab: str):
    st.session_state.clients_projects_tab = tab
    page_clients_projects()


def _open_store(tab: str):
    st.session_state.store_tab = tab
    page_store()


def _open_subcontractors(hint_tab: str | None = None):
    if hint_tab:
        st.session_state.subcontractor_hint = hint_tab
    page_subcontractors()


# —— Dashboard ——
def page_dashboard():
    from modules.ui import render_dashboard_home

    render_dashboard_home(st.session_state.get("user_name", "User"))


# —— Masters ——
def page_masters_company():
    masters_company_form()


def page_masters_projects():
    _open_clients("projects")


def page_masters_vendors():
    masters_vendors_form()


def page_masters_employees():
    page_employee_management()


def page_masters_accounts():
    from modules.database import load_chart_of_accounts

    st.subheader("Accounts Master")
    st.caption("Chart of accounts — source for Trial Balance, P&L, and Balance Sheet.")
    coa = load_chart_of_accounts(active_only=False)
    if coa.empty:
        st.info("Chart of accounts seeds automatically on database init.")
    else:
        st.dataframe(coa, use_container_width=True, hide_index=True)
    if st.button("Open account settings", key="masters_accounts_settings"):
        _open_settings(focus="accounts")


def page_masters_users_route():
    page_masters_users()


# —— Finance ——
def page_fin_expense_entry():
    _open_finance("expense")


def page_fin_purchase_invoice():
    _open_finance_hub("expense_voucher")


def page_fin_petty_cash():
    _open_finance("petty")


def page_fin_payments():
    _open_finance_hub("payment_out")


def page_fin_receipts():
    _open_finance_hub("cash_receipt")


def page_fin_journal():
    from modules.finance_screens import page_journal_voucher

    page_journal_voucher()


def page_fin_creditors():
    from modules.finance_screens import page_creditors

    page_creditors()


# —— GST & TDS ——
def page_gst_register():
    from modules.finance_workflow import render_gst_register_panel

    st.subheader("GST Register")
    render_gst_register_panel()


def page_gst_payment():
    from modules.gst_tds import page_gst_payment as _page

    _page()


def page_tds_register():
    from modules.gst_tds import page_tds_register as _page

    _page()


def page_tds_payment():
    from modules.gst_tds import page_tds_payment as _page

    _page()


# —— Subcontractor ——
def page_sub_work_orders():
    from modules.subcontractor_screens import page_work_orders

    page_work_orders()


def page_sub_bill_entry():
    _open_subcontractors("Bills")


def page_sub_payments():
    st.subheader("Subcontractor Payments")
    st.caption("Direct payments to sub contractors.")
    _open_finance("direct")


def page_sub_security():
    from modules.subcontractor_screens import page_security_deposit

    page_security_deposit()


# —— Inventory ——
def page_inv_purchase():
    from modules.inventory import page_inv_purchase as _page

    st.session_state.store_tab = "new"
    _page()


def page_inv_stock():
    _open_store("register")


def page_inv_material_issue():
    from modules.inventory import page_material_issue

    page_material_issue()


def page_inv_tools():
    from modules.inventory import page_tools

    page_tools()


# —— Assets ——
def page_asset_register():
    from modules.assets import page_asset_register as _page

    _page()


def page_asset_transfer():
    from modules.assets import page_asset_transfer as _page

    _page()


def page_asset_depreciation():
    from modules.assets import page_asset_depreciation as _page

    _page()


# —— Payroll ——
def page_pay_attendance():
    page_attendance()


def page_pay_payroll():
    page_payroll()


def page_pay_payslips():
    st.subheader("Payslips")
    st.caption("Payroll run and payslip view.")
    page_payroll()


# —— Projects ——
def page_proj_boq():
    _open_clients("projects")


def page_proj_budget():
    from modules.finance_workflow import render_budget_panel

    st.subheader("Project Budget")
    render_budget_panel()


def page_proj_cost_control():
    from modules.finance_workflow import render_budget_panel

    st.subheader("Cost Control")
    render_budget_panel()


def page_proj_progress():
    page_dpr()


# —— Reports ——
def page_rpt_financial():
    from modules.financial_reports import page_trial_balance_report

    tab_ops, tab_tb = st.tabs(["Operational Reports", "Trial Balance (GL)"])
    with tab_ops:
        page_reports()
    with tab_tb:
        page_trial_balance_report()


def page_rpt_profit_loss():
    from modules.financial_reports import page_profit_loss_report

    page_profit_loss_report()


def page_rpt_balance_sheet():
    from modules.financial_reports import page_balance_sheet_report

    page_balance_sheet_report()


def page_rpt_gst():
    page_gst_register()


def page_rpt_tds():
    from modules.gst_tds import page_tds_report

    page_tds_report()


def page_rpt_project():
    page_reports()


def page_rpt_inventory():
    _open_store("register")


def page_rpt_payroll():
    page_reports()


# —— Approvals ——
def page_appr_pending():
    from modules.finance_workflow import render_approval_inbox

    render_approval_inbox("Pending", ["Submitted", "Verified", "PM Approved"])


def page_appr_returned():
    from modules.finance_workflow import render_approval_inbox

    render_approval_inbox("Returned", ["Returned"])


def page_appr_approved():
    from modules.finance_workflow import render_approval_inbox

    render_approval_inbox("Approved", ["Approved"])


def page_appr_rejected():
    from modules.finance_workflow import render_approval_inbox

    render_approval_inbox("Rejected", ["Rejected"])


PAGE_HANDLERS = {
    "dashboard": page_dashboard,
    "masters_company": page_masters_company,
    "masters_projects": page_masters_projects,
    "masters_vendors": page_masters_vendors,
    "masters_employees": page_masters_employees,
    "masters_accounts": page_masters_accounts,
    "masters_users": page_masters_users_route,
    "fin_expense_entry": page_fin_expense_entry,
    "fin_purchase_invoice": page_fin_purchase_invoice,
    "fin_petty_cash": page_fin_petty_cash,
    "fin_payments": page_fin_payments,
    "fin_receipts": page_fin_receipts,
    "fin_journal": page_fin_journal,
    "fin_creditors": page_fin_creditors,
    "gst_register": page_gst_register,
    "gst_payment": page_gst_payment,
    "tds_register": page_tds_register,
    "tds_payment": page_tds_payment,
    "sub_work_orders": page_sub_work_orders,
    "sub_bill_entry": page_sub_bill_entry,
    "sub_payments": page_sub_payments,
    "sub_security": page_sub_security,
    "inv_purchase": page_inv_purchase,
    "inv_stock": page_inv_stock,
    "inv_material_issue": page_inv_material_issue,
    "inv_tools": page_inv_tools,
    "asset_register": page_asset_register,
    "asset_transfer": page_asset_transfer,
    "asset_depreciation": page_asset_depreciation,
    "pay_attendance": page_pay_attendance,
    "pay_payroll": page_pay_payroll,
    "pay_payslips": page_pay_payslips,
    "proj_boq": page_proj_boq,
    "proj_budget": page_proj_budget,
    "proj_cost_control": page_proj_cost_control,
    "proj_progress": page_proj_progress,
    "rpt_financial": page_rpt_financial,
    "rpt_profit_loss": page_rpt_profit_loss,
    "rpt_balance_sheet": page_rpt_balance_sheet,
    "rpt_gst": page_rpt_gst,
    "rpt_tds": page_rpt_tds,
    "rpt_project": page_rpt_project,
    "rpt_inventory": page_rpt_inventory,
    "rpt_payroll": page_rpt_payroll,
    "appr_pending": page_appr_pending,
    "appr_returned": page_appr_returned,
    "appr_approved": page_appr_approved,
    "appr_rejected": page_appr_rejected,
}
