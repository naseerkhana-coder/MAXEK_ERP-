"""Route sidebar page keys to existing module screens."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from modules.billing import page_billing
from modules.dpr import page_dpr
from modules.finance import page_finance, page_finance_accounts_hub
from modules.navigation import all_page_keys, page_label
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
from modules.erp_screens import (
    page_asset_breakdown,
    page_asset_fuel,
    page_asset_maintenance,
    page_bank_reconciliation,
    page_calendar,
    page_cheque_management,
    page_controlled_document,
    page_designation_master,
    page_driver_register,
    page_employee_transfer,
    page_grn,
    page_leave_approval,
    page_leave_management,
    page_low_stock_alert,
    page_material_category,
    page_material_return,
    page_overtime_management,
    page_purchase_requisition,
    page_quotation_comparison,
    page_rfq_management,
    page_site_wise_stock,
    page_staff_category,
    page_stock_adjustment,
    page_stock_transfer,
    page_stock_valuation,
    page_trip_sheet,
    page_unit_master,
    page_vehicle_allocation,
    page_vehicle_cost_reports,
    page_vehicle_fuel,
    page_vehicle_insurance,
    page_vehicle_register_quick,
    page_vehicle_service,
    page_vendor_rating,
    page_whatsapp_sending,
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


def _coming_soon(title: str, workflow: str = "") -> Callable[[], None]:
    def handler():
        st.subheader(title)
        if workflow:
            st.caption(workflow)
        st.info("This screen is configured in the ERP menu. Implementation is in progress.")

    return handler


# —— Dashboard ——
def page_dashboard():
    from modules.ui import render_dashboard_home

    render_dashboard_home(st.session_state.get("user_name", "User"))


def page_dash_pending():
    from modules.finance_workflow import render_approval_inbox

    st.subheader("Pending Approvals")
    render_approval_inbox("Pending", ["Submitted", "Verified", "PM Approved"])


def page_dash_notifications():
    from modules.ui import _render_dashboard_notifications

    st.subheader("Notifications")
    _render_dashboard_notifications()


# —— Masters ——
def page_masters_company():
    masters_company_form()


def page_masters_vendors():
    masters_vendors_form()


def page_masters_employees():
    page_employee_management()


def page_masters_accounts():
    from modules.database import load_chart_of_accounts

    st.subheader("Chart of Accounts")
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


def page_fin_contra():
    from modules.finance_screens import page_journal_voucher

    st.subheader("Contra Voucher")
    page_journal_voucher()


# —— GST ——
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


# —— Subcontractor / Work Orders ——
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


# —— Inventory / Store ——
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
    from modules.worker_payroll import page_worker_payroll

    page_worker_payroll()


def page_pay_payslips():
    from modules.worker_payroll import page_worker_payroll

    page_worker_payroll()


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


def page_site_dpr():
    page_dpr()


def page_boq_billing():
    page_billing()


# —— Settings ——
def page_settings_system():
    page_settings()


def page_settings_users():
    st.session_state.settings_focus = "users"
    page_settings()


def page_settings_dashboard():
    st.session_state.settings_focus = "dashboard"
    page_settings()


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


def page_appr_purchase():
    from modules.finance_workflow import render_approval_inbox

    st.subheader("Purchase Approval")
    render_approval_inbox("Purchase", ["Submitted", "Verified", "PM Approved"])


def page_appr_payment():
    from modules.finance_workflow import render_approval_inbox

    st.subheader("Payment Approval")
    render_approval_inbox("Payment", ["Submitted", "Verified", "PM Approved"])


def page_appr_petty():
    from modules.finance_workflow import render_approval_inbox

    st.subheader("Petty Cash Approval")
    render_approval_inbox("Petty Cash", ["Submitted", "Verified", "PM Approved"])


# —— Correspondence / Documents ——
def page_corr_dashboard():
    from modules.correspondence import page_corr_dashboard as _page

    _page()


def page_corr_incoming():
    from modules.correspondence import page_corr_incoming as _page

    _page()


def page_corr_outgoing():
    from modules.correspondence import page_corr_outgoing as _page

    _page()


def page_corr_drafting():
    from modules.correspondence import page_corr_drafting as _page

    _page()


def page_corr_email():
    from modules.correspondence import page_corr_email as _page

    _page()


def page_corr_approval():
    from modules.correspondence import page_corr_approval as _page

    _page()


def page_corr_tracking():
    from modules.correspondence import page_corr_tracking as _page

    _page()


def page_corr_authority():
    from modules.correspondence import page_corr_authority as _page

    _page()


def page_corr_archive():
    from modules.correspondence import page_corr_archive as _page

    _page()


# Explicit routes for implemented screens (new menu keys → handlers)
PAGE_ROUTES: dict[str, Callable[[], None]] = {
    # Dashboard
    "dash_mgmt": page_dashboard,
    "dash_project": page_rpt_project,
    "dash_accounts": page_rpt_financial,
    "dash_hr": page_pay_attendance,
    "dash_store": page_inv_stock,
    "dash_pending": page_dash_pending,
    "dash_notifications": page_dash_notifications,
    "dash_calendar": page_calendar,
    # Master Management
    "master_client": lambda: _open_clients("clients"),
    "master_client_create": lambda: _open_clients("clients"),
    "master_client_contacts": lambda: _open_clients("clients"),
    "master_client_gst": lambda: _open_clients("clients"),
    "master_client_contract": lambda: _open_clients("clients"),
    "master_client_docs": lambda: _open_clients("clients"),
    "master_contractor": lambda: _open_subcontractors(),
    "master_contractor_main": lambda: _open_subcontractors(),
    "master_contractor_sub": lambda: _open_subcontractors(),
    "master_contractor_class": lambda: _open_subcontractors(),
    "master_contractor_agreement": lambda: _open_subcontractors(),
    "master_vendor": page_masters_vendors,
    "master_vendor_supplier": page_masters_vendors,
    "master_vendor_service": page_masters_vendors,
    "master_vendor_material": page_masters_vendors,
    "master_vendor_rating": page_vendor_rating,
    "master_employee": page_masters_employees,
    "master_employee_create": page_masters_employees,
    "master_labour": page_masters_employees,
    "master_staff_category": page_staff_category,
    "master_designation": page_designation_master,
    "master_branch": page_masters_company,
    "master_department": page_masters_company,
    "master_material": page_inv_stock,
    "master_material_create": page_inv_stock,
    "master_material_category": page_material_category,
    "master_unit": page_unit_master,
    "master_equipment": page_inv_tools,
    "master_equipment_create": page_inv_tools,
    "master_machinery": page_inv_tools,
    "master_vehicle": page_vehicle_register_quick,
    "master_vehicle_register": page_vehicle_register_quick,
    "master_driver": page_driver_register,
    "master_location": page_masters_company,
    "master_site": lambda: _open_clients("projects"),
    # Project Management
    "proj_setup": lambda: _open_clients("projects"),
    "proj_create": lambda: _open_clients("projects"),
    "proj_code": lambda: _open_clients("projects"),
    "proj_client_link": lambda: _open_clients("projects"),
    "proj_contract_value": lambda: _open_clients("projects"),
    "proj_documents": lambda: _open_clients("projects"),
    "proj_site_mgmt": lambda: _open_clients("projects"),
    "proj_site_create": lambda: _open_clients("projects"),
    "proj_site_team": lambda: _open_clients("projects"),
    "proj_site_budget": page_proj_budget,
    "proj_boq": page_proj_boq,
    "proj_boq_approval": page_proj_boq,
    "proj_boq_revision": page_proj_boq,
    "proj_wo_internal": page_sub_work_orders,
    "proj_wo_sub": page_sub_work_orders,
    "proj_dpr_daily": page_site_dpr,
    "proj_dpr_weekly": page_proj_progress,
    "proj_dpr_monthly": page_proj_progress,
    "proj_bill_client": page_boq_billing,
    "proj_bill_ra": page_boq_billing,
    "proj_bill_final": page_boq_billing,
    "proj_cost_labour": page_proj_cost_control,
    "proj_cost_material": page_proj_cost_control,
    "proj_cost_equipment": page_proj_cost_control,
    "proj_cost_overhead": page_proj_cost_control,
    "proj_cost_pnl": page_rpt_profit_loss,
    # Purchase Management
    "purch_requisition": page_purchase_requisition,
    "purch_rfq": page_rfq_management,
    "purch_quotation": page_quotation_comparison,
    "purch_order": page_inv_purchase,
    "purch_grn": page_grn,
    "purch_invoice": page_fin_purchase_invoice,
    "purch_vendor_payment": page_sub_payments,
    "purch_approval": page_appr_purchase,
    # Store & Inventory
    "store_receipt": page_inv_stock,
    "store_issue": page_inv_material_issue,
    "store_return": page_material_return,
    "store_transfer": page_stock_transfer,
    "store_adjustment": page_stock_adjustment,
    "store_site_stock": page_site_wise_stock,
    "store_low_stock": page_low_stock_alert,
    "store_valuation": page_stock_valuation,
    "store_reports": page_rpt_inventory,
    # HR & Payroll
    "hr_attendance": page_pay_attendance,
    "hr_leave": page_leave_management,
    "hr_transfer": page_employee_transfer,
    "hr_overtime": page_overtime_management,
    "hr_payroll": page_pay_payroll,
    "hr_salary_slip": page_pay_payslips,
    "hr_labour_attendance": page_pay_attendance,
    "hr_reports": page_rpt_payroll,
    # Accounts & Finance
    "acc_coa": page_masters_accounts,
    "acc_cost_center": page_proj_budget,
    "acc_receipt": page_fin_receipts,
    "acc_payment": page_fin_payments,
    "acc_journal": page_fin_journal,
    "acc_contra": page_fin_contra,
    "acc_bank_recon": page_bank_reconciliation,
    "acc_cheque": page_cheque_management,
    "acc_gst_purchase": page_gst_payment,
    "acc_gst_sales": page_gst_register,
    "acc_gst_reports": page_rpt_gst,
    "acc_trial_balance": page_rpt_financial,
    "acc_pl": page_rpt_profit_loss,
    "acc_balance_sheet": page_rpt_balance_sheet,
    "acc_outstanding": page_fin_creditors,
    "acc_cash_book": page_fin_receipts,
    "acc_bank_book": page_fin_payments,
    # Petty Cash
    "petty_request": page_fin_petty_cash,
    "petty_allocation": page_fin_petty_cash,
    "petty_expense": page_fin_expense_entry,
    "petty_invoice": page_fin_purchase_invoice,
    "petty_verification": page_appr_petty,
    "petty_approval": page_appr_petty,
    "petty_settlement": page_fin_petty_cash,
    "petty_reports": page_fin_petty_cash,
    # Asset & Equipment
    "asset_register": page_asset_register,
    "asset_allocation": page_asset_transfer,
    "asset_fuel": page_asset_fuel,
    "asset_maintenance": page_asset_maintenance,
    "asset_breakdown": page_asset_breakdown,
    "asset_costing": page_asset_depreciation,
    # Vehicle Management
    "veh_allocation": page_vehicle_allocation,
    "veh_trip": page_trip_sheet,
    "veh_fuel": page_vehicle_fuel,
    "veh_service": page_vehicle_service,
    "veh_insurance": page_vehicle_insurance,
    "veh_cost": page_vehicle_cost_reports,
    # Document & Letter Management
    "doc_incoming": page_corr_incoming,
    "doc_register": page_corr_incoming,
    "doc_assign": page_corr_authority,
    "doc_followup": page_corr_tracking,
    "doc_reply": page_corr_tracking,
    "doc_outgoing": page_corr_outgoing,
    "doc_draft": page_corr_drafting,
    "doc_approval": page_corr_approval,
    "doc_email": page_corr_email,
    "doc_whatsapp": page_whatsapp_sending,
    "doc_contract": page_corr_archive,
    "doc_drawings": lambda: page_controlled_document("Drawing", "Drawings"),
    "doc_site": lambda: page_controlled_document("Site", "Site Documents"),
    "doc_legal": lambda: page_controlled_document("Legal", "Legal Documents"),
    # Approval Center
    "appr_purchase": page_appr_purchase,
    "appr_payment": page_appr_payment,
    "appr_petty": page_appr_petty,
    "appr_leave": page_leave_approval,
    "appr_work_order": page_sub_work_orders,
    "appr_vendor": page_masters_vendors,
    "appr_client": lambda: _open_clients("clients"),
    "appr_project": lambda: _open_clients("projects"),
    # Reports & MIS
    "rpt_proj_status": page_rpt_project,
    "rpt_cost_analysis": page_proj_cost_control,
    "rpt_budget_actual": page_proj_budget,
    "rpt_receivable": page_fin_receipts,
    "rpt_payable": page_fin_creditors,
    "rpt_gst": page_rpt_gst,
    "rpt_stock": page_rpt_inventory,
    "rpt_material_consumption": page_rpt_inventory,
    "rpt_attendance": page_pay_attendance,
    "rpt_payroll": page_rpt_payroll,
    "rpt_company_profit": page_rpt_profit_loss,
    "rpt_project_profit": page_rpt_profit_loss,
    "rpt_cash_flow": page_rpt_financial,
    # Settings & Administration
    "settings_users": page_settings_users,
    "settings_roles": page_settings_users,
    "settings_email": page_settings_system,
    "settings_whatsapp": page_settings_system,
    "settings_number_series": page_settings_system,
    "settings_backup": page_settings_system,
    "settings_audit": page_settings_system,
    "settings_erp": page_settings_system,
}


def _build_page_handlers() -> dict[str, Callable[[], None]]:
    handlers = dict(PAGE_ROUTES)
    for key in all_page_keys():
        if key not in handlers:
            handlers[key] = _coming_soon(page_label(key))
    return handlers


PAGE_HANDLERS = _build_page_handlers()
