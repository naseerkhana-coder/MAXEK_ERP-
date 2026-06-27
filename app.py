from flask import Flask, g, render_template, request, redirect, url_for, session, flash, send_file, send_from_directory, jsonify, make_response, abort
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import sqlite3
import os
import json
import re
import pandas as pd
import bcrypt
from datetime import datetime, timedelta
from calendar import monthrange
from zoneinfo import ZoneInfo

from cost_planning_service import (
    DEFAULT_COST_ACTIVITIES,
    MICRO_PLAN_PERIODS,
    COST_PLAN_REPORTS,
    ensure_cost_planning_tables,
    prepare_cost_planning_db,
    get_boq_item_context,
    aggregate_dpr_actuals,
    build_wbs_tree,
    get_cost_plan_dashboard,
    load_cost_plan_detail,
    save_cost_plan_from_form,
    save_micro_plan_from_form,
    list_cost_plans,
    export_cost_plan_register_rows,
    build_monitoring_row,
)

from payroll_service import (
    calculate_daily_wage,
    generate_payroll_run,
    export_register_rows,
    fetch_payroll_lines,
    attach_run_employee_summaries,
    get_employee_profile,
    list_eligible_employees,
    list_pending_payroll_months,
    summarize_pending_payroll_months,
    period_from_month_year,
    calculate_staff_period_pay,
    calculate_worker_period_pay,
    employee_has_period_data,
    serialize_eligible_employee,
    _row_employee_identity,
    PAYROLL_RUN_STATUSES,
    EMPLOYEE_TYPES,
    PAYROLL_EMPLOYMENT_CATEGORIES,
    payroll_employment_filter,
)

from attendance_service import (
    MODULE_ID as MONTHLY_ATTENDANCE_MODULE_ID,
    RECORD_TABLE as MONTHLY_ATTENDANCE_TABLE,
    ensure_staff_monthly_attendance_schema,
    list_monthly_staff_for_attendance,
    list_monthly_attendance_records,
    get_monthly_attendance_record,
    save_monthly_attendance_from_form,
    list_trades_for_subcontractor,
    list_subcontractor_workers_for_attendance,
    save_bulk_subcontractor_attendance,
    SUBCONTRACTOR_ATTENDANCE_STATUSES,
)

from accounts_service import (
    ACCOUNT_TYPES,
    PAYMENT_SOURCES,
    PAYMENT_STATUSES,
    GST_RATES,
    TAX_TYPES,
    TDS_SECTIONS,
    FILING_STATUSES,
    ensure_accounts_schema,
    chart_accounts_grouped,
    list_chart_of_accounts,
    list_expense_chart_heads,
    list_income_chart_heads,
    save_chart_account,
    save_account_expense,
    load_account_expense,
    list_account_expenses,
    save_payment_voucher,
    load_payment_voucher,
    list_payment_vouchers,
    save_receipt_voucher,
    load_receipt_voucher,
    list_receipt_vouchers,
    list_settled_petty_cash,
    get_gst_purchase_register,
    get_gst_sales_register,
    accounts_hub_stats,
    chart_accounts_for_js,
    chart_heads_payload,
    post_journal_on_approval,
    void_journal_for_reference,
    get_cash_book_v2,
    get_bank_book_v2,
    get_day_book,
    get_general_ledger,
    get_vendor_ledger,
    get_client_ledger,
    get_trial_balance,
    get_profit_and_loss,
    get_balance_sheet,
    get_cash_flow_summary,
    get_project_profitability,
    list_tds_register,
    list_gst_filing_periods,
    update_gst_filing_status,
    get_gstr_summary,
    list_pf_esi_register,
    build_pf_esi_from_payroll,
    update_pf_esi_filing_status,
    create_expense_draft_from_petty_cash,
    export_report_excel,
    export_report_csv,
    export_tally_xml,
    save_account_attachment,
    list_account_attachments,
    list_unpaid_expenses_for_vendor,
    get_petty_cash_balance,
    get_chart_account_by_code,
)

from treasury_service import (
    ensure_treasury_schema,
    post_treasury_on_approval,
    void_treasury_on_reversal,
    seed_treasury_demo_data,
)
from budget_service import ensure_budget_schema, seed_budget_demo_data
from profitability_service import ensure_profitability_schema, seed_profitability_demo_data
from contract_service import ensure_contract_schema, seed_contract_demo_data
from claims_service import ensure_claims_schema, seed_claims_demo_data
from equipment_costing_service import (
    ensure_equipment_costing_schema,
    seed_equipment_costing_demo_data,
)
from labour_productivity_service import (
    ensure_labour_productivity_schema,
    seed_labour_productivity_demo_data,
)
from treasury_routes import register_treasury_routes
from alert_engine_service import (
    ensure_alert_engine_schema,
    generate_alerts,
    get_alert_counts_by_severity,
)
from document_numbering_service import (
    ensure_document_numbering_schema,
    seed_default_sequences,
)
from backup_service import (
    ensure_backup_schema,
    run_scheduled_backup_if_due,
)
from user_activity_service import (
    DEFAULT_IDLE_THRESHOLD_MINUTES,
    ensure_user_activity_schema,
    get_activity_dashboard,
    get_idle_report,
    get_login_report,
    get_screen_activity_report,
    log_login,
    log_logout,
    log_page_view,
    resolve_module_name,
    should_track_page_view,
)

from office_fleet_service import (
    INWARD_MODES,
    OUTWARD_MODES,
    DOCUMENT_TYPES,
    LETTER_TYPES,
    AGREEMENT_TYPES,
    LEGAL_DOC_TYPES,
    VEHICLE_TYPES,
    FUEL_TYPES,
    VEHICLE_STATUSES,
    VEHICLE_DOC_TYPES,
    EXPIRY_ALERT_DAYS as OFFICE_EXPIRY_ALERT_DAYS,
    OFFICE_ALLOWED_EXTENSIONS,
    MAX_OFFICE_UPLOAD_BYTES,
    ensure_office_fleet_schema,
    office_dashboard_stats,
    fleet_dashboard_stats,
    list_inward,
    get_inward,
    save_inward,
    delete_inward,
    list_outward,
    get_outward,
    save_outward,
    delete_outward,
    list_letters,
    get_letter,
    save_letter,
    delete_letter,
    list_quotations,
    load_quotation,
    save_quotation,
    delete_quotation,
    list_po_register,
    list_agreements,
    get_agreement,
    save_agreement,
    delete_agreement,
    list_legal_documents,
    get_legal_document,
    save_legal_document,
    delete_legal_document,
    list_vehicles,
    get_vehicle,
    save_vehicle,
    delete_vehicle,
    list_vehicle_documents,
    get_vehicle_document,
    save_vehicle_document,
    delete_vehicle_document,
    list_running_logs,
    get_running_log,
    save_running_log,
    delete_running_log,
    list_diesel_purchases,
    save_diesel_purchase,
    list_diesel_issues,
    save_diesel_issue,
    list_diesel_ledger,
    get_diesel_stock_balance,
)

from qc_service import (
    QC_TEST_STATUSES,
    APPLICABLE_MATERIALS,
    TEST_FREQUENCIES,
    ensure_qc_schema,
    list_qc_tests,
    get_qc_test,
    save_qc_test,
    delete_qc_test,
)

from plant_service import (
    PLANT_TYPES,
    PLANT_STATUSES,
    SHIFTS as PLANT_SHIFTS,
    ASPHALT_MIX_TYPES,
    RMC_GRADES,
    PRECAST_PRODUCT_TYPES,
    PRECAST_STATUSES,
    CRUSHER_OUTPUT_GRADES,
    MSAND_GRADES,
    QC_SOURCE_MODULES,
    QC_TEST_TYPES,
    QC_PASS_FAIL,
    MAINTENANCE_JOB_TYPES,
    MAINTENANCE_STATUSES,
    ensure_plant_schema,
    plant_dashboard_stats,
    list_plants,
    get_plant,
    save_plant,
    delete_plant,
    list_active_plants,
    list_crusher_msand_plants,
    list_asphalt_production,
    get_asphalt_production,
    save_asphalt_production,
    delete_asphalt_production,
    list_asphalt_dispatch,
    get_asphalt_dispatch,
    save_asphalt_dispatch,
    delete_asphalt_dispatch,
    list_rmc_production,
    get_rmc_production,
    save_rmc_production,
    delete_rmc_production,
    list_rmc_dispatch,
    get_rmc_dispatch,
    save_rmc_dispatch,
    delete_rmc_dispatch,
    list_wetmix_production,
    get_wetmix_production,
    save_wetmix_production,
    delete_wetmix_production,
    list_precast_production,
    get_precast_production,
    save_precast_production,
    delete_precast_production,
    list_precast_dispatch,
    get_precast_dispatch,
    save_precast_dispatch,
    delete_precast_dispatch,
    list_plant_stock,
    list_crusher_production,
    get_crusher_production,
    save_crusher_production,
    delete_crusher_production,
    list_plant_qc,
    get_plant_qc,
    save_plant_qc,
    delete_plant_qc,
    list_maintenance_jobs,
    get_maintenance_job,
    save_maintenance_job,
    delete_maintenance_job,
    plant_costing_summary,
    get_plant_360,
)

from precast_service import (
    PRECAST_YARD_STATUSES,
    PRECAST_YARD_SUBTOOLBAR,
    ensure_precast_schema,
    list_precast_yards,
    get_precast_yard,
    save_precast_yard,
    delete_precast_yard,
    precast_yard_dashboard_stats,
)

from helpdesk_service import (
    HELP_TOPIC_CATEGORIES,
    HELP_TOPIC_STATUSES,
    HELP_DESK_SUBTOOLBAR,
    ensure_helpdesk_schema,
    list_help_topics,
    get_help_topic,
    save_help_topic,
    delete_help_topic,
)

from ui_shell_config import (
    APP_VERSION_LABEL,
    DASHBOARD_SHELL_FAVORITES,
    DASHBOARD_SHELL_NAV_GROUPS,
    GLOBAL_SEARCH_CATEGORIES,
    HELP_CENTER_ITEMS,
    MAIN_DASHBOARD_BOTTOM_WIDGETS,
    MAIN_DASHBOARD_DEPARTMENT_SLUGS,
    MAIN_DASHBOARD_PORTAL_ALIASES,
    VIRTUAL_TOOLBAR_ENTRIES,
    accounts_sub_toolbar_sections,
    build_main_toolbar,
    filter_sub_toolbar_items,
    get_department_portal_menu,
    portal_menu_as_nav_group,
    quick_panel_for_slug,
    resolve_active_toolbar_slug,
    resolve_department_portal_slug,
)

from super_admin_service import (
    CUSTOMER_ADMIN_CREATABLE_ROLES,
    CUSTOMER_ADMIN_ROLE,
    ERP_ADMIN_SUBTOOLBAR,
    PLATFORM_CUSTOMER_CODE,
    SUPER_ADMIN_ROLE,
    authenticate_tenant_user,
    assert_user_limit_not_exceeded,
    bootstrap_super_admin,
    ensure_super_admin_schema,
    get_customer_by_code,
    get_customer_by_id,
    is_customer_admin_user as _is_customer_admin_row,
    is_super_admin_user as _is_super_admin_row,
    seed_super_admin_data,
    sync_customer_usage_counts,
)
from erp_admin_routes import register_erp_admin_routes
from api_routes import register_api_routes
from ai_routes import register_ai_routes
from erp_platform_routes import erp_platform_bp
from auth_jwt import ensure_jwt_schema
from tenant_isolation import ensure_tenant_isolation_schema
from user_context_service import (
    apply_context_to_session,
    ensure_user_context_schema,
    list_context_branches,
    list_context_companies,
    list_context_projects,
    load_user_context,
    save_user_context,
)
from user_permission_service import (
    PERMISSION_DEPARTMENT_CHOICES,
    apply_user_tab_permissions_to_nav_groups,
    build_department_tab_catalog,
    ensure_user_tab_permissions_schema,
    filter_portal_menu_for_user,
    get_user_department_tab_state,
    nav_slug_to_permission_department,
    save_user_department_tab_permissions,
)
from badge_counts_service import badge_for_endpoint, get_live_badge_counts
from attachment_service import ensure_attachment_schema
from audit_trail_service import ensure_audit_schema, list_audit_trail
from dashboard_prefs_service import (
    filter_command_centre_dept_cards,
    filter_command_centre_kpis,
    filter_command_centre_quick_actions,
    infer_role_profile,
    load_dashboard_preferences,
    normalize_ui_theme,
    save_dashboard_preferences,
)

from company_master_service import (
    COMPANY_COUNTRIES,
    COMPANY_STATUSES,
    DIRECTOR_TYPES,
    COMPANY_DOC_TYPES,
    ensure_company_master_schema,
    list_companies,
    get_company,
    save_company,
    delete_company,
    list_branches,
    get_branch,
    save_branch,
    delete_branch,
    list_gst_registrations,
    save_gst_registration,
    delete_gst_registration,
    list_directors,
    get_director,
    save_director,
    delete_director,
    list_company_documents,
    get_company_document,
    save_company_document,
    delete_company_document,
    collect_company_expiry_alerts,
    sync_company_expiry_notifications,
    list_country_field_config,
    GCC_CONFIGURABLE_COUNTRIES,
)

from client_billing_service import (
    MODULE_ID as CLIENT_BILLING_MODULE_ID,
    RECORD_TABLE as CLIENT_BILLING_TABLE,
    EXTRA_LINE_TYPES,
    ATTACHMENT_TYPES,
    BILLING_ALLOWED_EXTENSIONS,
    MAX_BILLING_UPLOAD_BYTES,
    ensure_client_billing_schema,
    import_dpr_measurements,
    import_dpr_for_billing,
    save_client_bill,
    get_client_bill,
    list_client_bills,
    delete_client_bill,
    save_bill_attachment,
    delete_bill_attachment,
    mark_bill_paid,
    on_bill_certified,
    list_billing_reports,
    client_ledger_rows,
    list_projects_for_billing,
    list_clients_for_billing,
    enrich_bill_for_print,
    get_company_bank_for_print,
    GST_TAX_TYPES,
    list_gst_bills_for_ra,
    build_gst_bill_defaults_from_ra,
    suggest_gst_tax_type,
    save_client_gst_bill,
    get_client_gst_bill,
    create_gst_bill_from_ra,
)

from employee_timesheet_service import (
    MODULE_ID as EMPLOYEE_TIMESHEET_MODULE_ID,
    RECORD_TABLE as EMPLOYEE_TIMESHEET_TABLE,
    TIMESHEET_STATUSES,
    ensure_employee_timesheet_schema,
    save_monthly_timesheet,
    submit_timesheet,
    approve_timesheet,
    get_monthly_timesheet,
    list_monthly_timesheets,
    list_staff_for_timesheet,
    list_workers_for_timesheet,
    list_projects_for_timesheet,
    delete_timesheet,
    days_in_month,
    year_month_label,
    parse_year_month,
)

from bbs_service import (
    MODULE_ID as BBS_MODULE_ID,
    RECORD_TABLE as BBS_TABLE,
    DIAMETERS,
    ensure_bbs_schema,
    save_bbs_report,
    get_bbs_report,
    list_bbs_reports,
    list_projects_for_bbs,
    delete_bbs_report,
)

from subcontractor_billing_service import (
    MODULE_ID as SUB_BILLING_MODULE_ID,
    RECORD_TABLE as SUB_BILLING_TABLE,
    DEFAULT_DECLARATION,
    ensure_subcontractor_billing_schema,
    save_subcontractor_bill,
    get_subcontractor_bill,
    list_subcontractor_bills,
    list_subcontractors_for_billing,
    import_worker_lines_template,
    delete_subcontractor_bill,
)

from subcontract_payment_service import (
    MODULE_ID as SUB_PAYMENT_MODULE_ID,
    WORK_ORDER_TABLE as SUB_PAYMENT_WO_TABLE,
    PAYMENT_TABLE as SUB_PAYMENT_ENTRY_TABLE,
    ensure_subcontract_payment_schema,
    save_work_order,
    save_payment_entry,
    apply_payment_on_approval,
    get_work_order,
    list_work_order_ledger,
    list_subcontractors_for_payments,
    ledger_summary,
    refresh_work_order_paid_totals,
)

from project_photos_service import (
    PHOTO_CATEGORIES,
    REPORT_TYPES as PHOTO_REPORT_TYPES,
    ensure_project_photos_schema,
    validate_photo_upload,
    list_projects_for_photos,
    search_project_photos,
    list_photos_timeline,
    get_project_photo,
    save_project_photo,
    delete_project_photo,
    photos_for_report,
    photo_register_stats,
)

from corporate_dms_service import (
    DOCUMENT_TYPES as DMS_DOCUMENT_TYPES,
    ensure_corporate_dms_schema,
    validate_dms_upload,
    list_folders,
    folder_tree,
    save_folder,
    search_documents,
    get_document,
    get_version,
    save_document,
    delete_document,
    collect_dms_expiry_alerts,
    sync_dms_expiry_notifications,
    register_stats as dms_register_stats,
)

from corporate_template_service import (
    FONT_OPTIONS,
    PDF_ORIENTATIONS,
    ensure_corporate_template_schema,
    validate_template_upload,
    list_templates,
    get_template,
    get_active_template,
    save_template,
    delete_template,
    set_default_template,
    build_print_context,
)

from report_registry import (
    REPORT_CATEGORIES,
    get_report_def,
    reports_by_category,
    count_by_status,
)

from corporate_report_data_service import (
    load_standard_report_data,
    get_stub_template,
    get_report_columns,
)

from document_numbering_service import peek_next_number, DOC_TYPES

from store_service import (
    MATERIAL_CATEGORIES,
    MATERIAL_UNITS,
    VENDOR_DOC_TYPES,
    VENDOR_TYPES,
    VENDOR_TYPE_OPTIONS,
    TRADE_CATEGORY_OPTIONS,
    vendor_types_list,
    vendor_trade_categories_list,
    list_subcontract_eligible_vendors,
    vendor_is_subcontract_eligible,
    GST_RATES as STORE_GST_RATES,
    ensure_store_schema,
    save_material,
    list_materials,
    get_material,
    resolve_material_request_from_form,
    export_materials_excel,
    import_materials_excel,
    save_vendor,
    list_vendors,
    get_vendor,
    generate_vendor_code,
    save_vendor_document,
    list_vendor_documents,
    save_purchase_order,
    load_purchase_order,
    list_purchase_orders,
    save_store_receipt,
    load_store_receipt,
    list_store_receipts,
    save_store_issue,
    load_store_issue,
    list_store_issues,
    save_material_transfer,
    load_material_transfer,
    list_material_transfers,
    MATERIAL_TRANSFER_TYPES,
    get_stock_balance,
    post_stock_on_approval,
    void_stock_for_reference,
    list_inventory_stock,
    store_dashboard_stats,
    get_project_material_qty_stats,
    get_project_planned_materials,
)

from workflow_service import (
    ALLOWED_RECORD_TABLES,
    create_approval_request,
    advance_approval,
    reopen_transaction,
    resubmit_record,
    can_maker_edit,
    can_maker_delete,
    can_user_edit,
    delete_workflow_record,
    user_matches_stage,
    get_edit_role_for_user,
    get_approval_request,
    get_approval_request_by_id,
    get_pending_counts,
    get_pending_items,
    get_workflow_queue,
    get_workflow_for_module,
    get_module_workflow_mode,
    workflow_mode_requires_checker,
    workflow_mode_requires_approver,
    summarize_approval_item,
    is_pending_for_role,
    get_user_workflow_preview,
    count_user_pending_workflows,
    format_reference_no,
    seed_workflow_master,
    migrate_workflow_statuses,
    sync_workflow_designations,
    seed_demo_users,
    seed_demo_sample_data,
    status_display,
    display_status_from_workflow,
    display_status,
    maker_status_message,
    get_dashboard_counters,
    get_approval_summary,
    get_workflow_audit_report,
    get_workflow_access_for_designation,
    get_workflow_access_label,
    user_workflow_capabilities,
    get_user_workflow_role,
    is_admin_role,
    get_recent_activities,
    get_approval_history,
    get_notifications,
    mark_notifications_read,
    create_notification,
    WORKFLOW_STATUS,
    WORKFLOW_MODES,
    WORKFLOW_MODE_LABELS,
    DEFAULT_WORKFLOW_MODE,
    STATUS_APPROVED,
    RECORD_PENDING_CHECKER,
    RECORD_PENDING_APPROVAL,
    RECORD_APPROVED,
    RECORD_REJECTED_CHECKER,
    RECORD_REJECTED_APPROVER,
)

APP_VERSION = "1.0.0"

BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def is_bcrypt_hash(stored_password):
    if not stored_password:
        return False
    return str(stored_password).startswith(BCRYPT_PREFIXES)


def verify_password(stored_password, provided_password):
    if stored_password is None or provided_password is None:
        return False
    stored = str(stored_password)
    provided = str(provided_password)
    if is_bcrypt_hash(stored):
        try:
            return bcrypt.checkpw(provided.encode("utf-8"), stored.encode("utf-8"))
        except (ValueError, TypeError):
            return False
    return stored == provided


def hash_password(plain_password):
    return bcrypt.hashpw(
        plain_password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def _is_truthy(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in ("1", "true", "yes", "y")


def user_is_active(user_row):
    if user_row is None:
        return False
    keys = user_row.keys()
    if "is_disabled" in keys or "account_locked" in keys:
        disabled = _is_truthy(user_row["is_disabled"]) if "is_disabled" in keys else False
        locked = _is_truthy(user_row["account_locked"]) if "account_locked" in keys else False
        return not disabled and not locked
    if "status" in keys:
        return str(user_row["status"] or "").strip().lower() == "active"
    return True


def get_user_id(user_row):
    if user_row is None:
        return None
    keys = user_row.keys()
    if "id" in keys and user_row["id"] is not None:
        return user_row["id"]
    if "user_id" in keys:
        return user_row["user_id"]
    return None


def _row_val(user_row, key, default=""):
    if key not in user_row.keys():
        return default
    val = user_row[key]
    return val if val is not None else default


def get_user_display_name(user_row):
    return (
        _row_val(user_row, "employee_name")
        or _row_val(user_row, "full_name")
        or _row_val(user_row, "username")
    )


def authenticate_user(db, username, password, company_code=None):
    if company_code is not None and not str(company_code).strip():
        company_code = None
    if company_code is not None:
        user, _err = authenticate_tenant_user(
            db,
            company_code,
            username,
            password,
            verify_password_fn=verify_password,
            user_is_active_fn=user_is_active,
        )
        return user
    user = db.execute(
        "SELECT * FROM users WHERE username=?",
        (username.strip(),),
    ).fetchone()
    if not user or not user_is_active(user):
        return None
    if not verify_password(user["password"], password):
        return None
    return user


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "maxek.db")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
PHOTOS_DIR = os.path.join(BASE_DIR, "static", "photos")
UPLOADS_DIR = os.path.join(BASE_DIR, "static", "uploads")
STAFF_DOCS_DIR = os.path.join(UPLOADS_DIR, "staff")
WORKER_DOCS_DIR = os.path.join(UPLOADS_DIR, "workers")
SUBCONTRACTOR_DOCS_DIR = os.path.join(UPLOADS_DIR, "subcontractors")
CLIENT_DOCS_DIR = os.path.join(UPLOADS_DIR, "clients")
PROJECT_DOCS_DIR = os.path.join(UPLOADS_DIR, "projects")
DPR_DOCS_DIR = os.path.join(UPLOADS_DIR, "dpr")
PETTY_CASH_DOCS_DIR = os.path.join(UPLOADS_DIR, "petty_cash")
ACCOUNTS_DOCS_DIR = os.path.join(UPLOADS_DIR, "accounts")
STORE_DOCS_DIR = os.path.join(UPLOADS_DIR, "store")
VENDOR_UPLOADS_DIR = os.path.join(UPLOADS_DIR, "vendors")
SECURITIES_DOCS_DIR = os.path.join(UPLOADS_DIR, "securities")
TREASURY_DOCS_DIR = os.path.join(UPLOADS_DIR, "treasury")
OFFICE_DOCS_DIR = os.path.join(UPLOADS_DIR, "office")
FLEET_DOCS_DIR = os.path.join(UPLOADS_DIR, "fleet")
COMPANY_DOCS_DIR = os.path.join(UPLOADS_DIR, "company")
BILLING_DOCS_DIR = os.path.join(UPLOADS_DIR, "client_billing")
PROJECT_PHOTOS_DIR = os.path.join(UPLOADS_DIR, "project_photos")
CORPORATE_DMS_DIR = os.path.join(UPLOADS_DIR, "corporate_dms")
CORPORATE_TEMPLATE_DIR = os.path.join(UPLOADS_DIR, "corporate_templates")
SUPPORT_TICKETS_DIR = os.path.join(UPLOADS_DIR, "support")
DPR_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
PETTY_CASH_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx"}
SECURITIES_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"}
MAX_PETTY_CASH_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SECURITIES_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PROJECT_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_REQUEST_BODY_BYTES = 32 * 1024 * 1024
PROJECT_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
SECURITY_TYPES = (
    "Treasury Deposit",
    "Security Deposit",
    "Performance Bank Guarantee",
    "Additional Bank Guarantee",
    "Pending Bill Retention",
    "EMD",
)
SECURITY_STATUSES = (
    "Draft",
    "Active",
    "Expiring Soon",
    "Maturity Pending",
    "Release Requested",
    "Released",
    "Extended",
    "Invoked",
    "Refunded",
    "Forfeited",
    "Matured",
    "Closed",
)
SECURITY_EXPIRY_ALERT_DAYS = (90, 60, 30, 7)
PETTY_CASH_STATUSES = (
    "Draft", "Submitted", "Approved", "Rejected",
    "Funds Transferred", "Amount Received",
    "Settlement Pending", "Settled", "Closed",
)
PETTY_CASH_EXPENSE_CATEGORIES = (
    "Travel", "Food", "Materials", "Fuel", "Office", "Maintenance", "Other",
)
DPR_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
MAX_DPR_UPLOAD_BYTES = 10 * 1024 * 1024

os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(PHOTOS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STAFF_DOCS_DIR, exist_ok=True)
os.makedirs(WORKER_DOCS_DIR, exist_ok=True)
os.makedirs(SUBCONTRACTOR_DOCS_DIR, exist_ok=True)
os.makedirs(CLIENT_DOCS_DIR, exist_ok=True)
os.makedirs(PROJECT_DOCS_DIR, exist_ok=True)
os.makedirs(DPR_DOCS_DIR, exist_ok=True)
os.makedirs(PETTY_CASH_DOCS_DIR, exist_ok=True)
os.makedirs(ACCOUNTS_DOCS_DIR, exist_ok=True)
os.makedirs(STORE_DOCS_DIR, exist_ok=True)
os.makedirs(OFFICE_DOCS_DIR, exist_ok=True)
os.makedirs(FLEET_DOCS_DIR, exist_ok=True)
os.makedirs(COMPANY_DOCS_DIR, exist_ok=True)
os.makedirs(BILLING_DOCS_DIR, exist_ok=True)
os.makedirs(PROJECT_PHOTOS_DIR, exist_ok=True)
os.makedirs(CORPORATE_DMS_DIR, exist_ok=True)
os.makedirs(CORPORATE_TEMPLATE_DIR, exist_ok=True)
os.makedirs(SECURITIES_DOCS_DIR, exist_ok=True)
os.makedirs(TREASURY_DOCS_DIR, exist_ok=True)

GOV_DEPARTMENTS = ["PWD", "NH", "KIIFB", "Kerala PWD", "NHAI", "Other"]
GUARANTEE_TYPES = ["Performance Guarantee", "Bank Guarantee", "Both"]
PROJECT_GUARANTEE_TYPES = (
    "Bank Guarantee",
    "Performance Guarantee",
    "Treasury Deposit",
)
MAX_MAKER_ASSIGNMENTS = 15
BOQ_UNITS = ["Nos", "Sqm", "Sqft", "Rmt", "Kg", "MT", "Ltr", "Cum", "Hour", "Day", "LS", "Set", "Bag"]
MAX_BOQ_LINES = 25
MAX_BOQ_BULK_LINES = 100
STEEL_DIAMETERS_MM = [8, 10, 12, 16, 20, 25, 32, 40]
VOLUME_UNITS = {"Cum", "cum", "m3", "M3", "CUM"}
AREA_UNITS = {"Sqm", "sqm", "m2", "M2", "SQM", "Sqft"}
STEEL_UNITS = {"Kg", "kg", "MT", "mt", "Ton", "ton", "Tonne", "tonne"}
DEFAULT_STEEL_SHAPES = [
    ("Straight", 1, "straight"),
    ("L-Shape", 2, "perimeter"),
    ("U-Shape", 3, "perimeter"),
    ("Rectangle", 4, "perimeter"),
    ("Pentagon", 5, "perimeter"),
    ("Ring / Hexagon", 6, "perimeter"),
]
MANPOWER_TRADES = [
    "Carpenter",
    "Steel Fixer",
    "Helper",
    "Mason",
    "Electrician",
    "Plumber",
    "Painter",
]
MAX_MANPOWER_TRADES = 7
SUBCONTRACTOR_RATE_TYPES = (
    "Labour Supply",
    "Item Rate Contract",
    "Measurement Based Contract",
    "Lump Sum Contract",
)
SUBCONTRACTOR_RATE_TYPE_CHOICES = (
    {"value": "Labour Supply", "label": "Labour Supply"},
    {"value": "Item Rate Contract", "label": "Item Rate Contract"},
    {"value": "Measurement Based Contract", "label": "Measurement Based Contract"},
    {"value": "Lump Sum Contract", "label": "Lump Sum Contract"},
)
# Legacy rate_type values stored before work-type rename
_SUBCONTRACTOR_LEGACY_RATE_TYPES = {
    "Manpower": "Labour Supply",
    "BOQ Base Rate": "Measurement Based Contract",
}

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret")
app.config["JWT_SECRET_KEY"] = os.environ.get("MAXEK_JWT_SECRET") or app.secret_key
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BODY_BYTES


@app.errorhandler(RequestEntityTooLarge)
def handle_request_entity_too_large(error):
    flash(
        "Upload too large. Maximum total request size is 32 MB "
        "(10 MB per project document)."
    )
    return redirect(request.referrer or url_for("projects"))


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


@app.before_request
def _bootstrap_db_schema():
    ensure_runtime_schema()


@app.before_request
def _track_user_page_activity():
    if not session.get("user_id"):
        return
    endpoint = request.endpoint or ""
    if not should_track_page_view(
        method=request.method,
        path=request.path,
        endpoint=endpoint,
    ):
        return
    try:
        nav_group = active_nav_group(endpoint)
        module_name = resolve_module_name(endpoint, nav_group.get("label") if nav_group else None)
        db = get_db()
        page_id, viewed_at = log_page_view(
            db,
            user_id=session["user_id"],
            employee_name=session.get("employee_name"),
            session_id=session.get("login_session_id"),
            module_name=module_name,
            page_path=request.path,
            endpoint=endpoint,
            idle_threshold_minutes=DEFAULT_IDLE_THRESHOLD_MINUTES,
            last_page_activity_id=session.get("last_page_activity_id"),
            last_viewed_at=session.get("last_page_viewed_at"),
        )
        session["last_page_activity_id"] = page_id
        session["last_page_viewed_at"] = viewed_at
    except Exception:
        app.logger.exception("User page activity tracking failed")


def save_file(file_storage, dest_folder):
    if file_storage and file_storage.filename:
        try:
            os.makedirs(dest_folder, exist_ok=True)
            filename = secure_filename(file_storage.filename)
            timestamp = int(datetime.utcnow().timestamp())
            saved_name = f"{timestamp}_{filename}"
            path = os.path.join(dest_folder, saved_name)
            file_storage.save(path)
            return saved_name
        except OSError:
            return None
    return None


def _validate_project_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in PROJECT_ALLOWED_EXTENSIONS:
        return "Allowed project document types: PDF, JPG, PNG."
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_PROJECT_UPLOAD_BYTES:
        return f"{file_storage.filename} is too large (maximum 10 MB per file)."
    return None


def _validate_dpr_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None, None, "Select a file to upload."
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in DPR_ALLOWED_EXTENSIONS:
        return None, None, "Allowed file types: PDF, JPG, PNG."
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_DPR_UPLOAD_BYTES:
        return None, None, "File is too large (maximum 10 MB)."
    return ext, size, None


def generate_employee_code(db):
    rows = db.execute(
        "SELECT employee_code FROM staff WHERE employee_code LIKE 'EMP%'"
    ).fetchall()
    max_code = 100
    for row in rows:
        code = str(row["employee_code"] or "").strip().upper()
        number = code[3:]
        if number.isdigit():
            max_code = max(max_code, int(number))
    return f"EMP{max_code + 1}"


def _clean_name_letters(name):
    return "".join(ch for ch in (name or "").upper() if ch.isalnum())


def subcontractor_name_prefix(name):
    """First two letters of cleaned name."""
    letters = _clean_name_letters(name)
    if len(letters) >= 2:
        return letters[:2]
    if letters:
        return (letters + "U")[:2]
    return "SU"


def subcontractor_code_prefix(code_or_name):
    """Two-letter prefix from stored ID (SA100 -> SA) or from a name."""
    raw = str(code_or_name or "").strip().upper()
    letters = "".join(ch for ch in raw if ch.isalnum())
    if not letters:
        return "SU"
    alpha_end = 0
    while alpha_end < len(letters) and letters[alpha_end].isalpha():
        alpha_end += 1
    if alpha_end > 0 and alpha_end < len(letters) and letters[alpha_end:].isdigit():
        alpha = letters[:alpha_end]
        if len(alpha) >= 2:
            return alpha[:2]
        return (alpha + "U")[:2]
    return subcontractor_name_prefix(raw)


def _subcontractor_prefix_candidates(name):
    """Try 1st+2nd letters, then 1st+3rd, 1st+4th, … when prefixes collide."""
    letters = _clean_name_letters(name)
    if not letters:
        return ["SU"]
    candidates = []

    def add(prefix):
        if prefix and len(prefix) == 2 and prefix not in candidates:
            candidates.append(prefix)

    if len(letters) >= 2:
        add(letters[:2])
    if len(letters) >= 3:
        add(letters[0] + letters[2])
    if len(letters) >= 4:
        add(letters[0] + letters[3])
    if len(letters) >= 5:
        add(letters[0] + letters[4])
    if len(letters) >= 6:
        add(letters[0] + letters[5])
    add("SU")
    return candidates


def _subcontractor_prefix_in_use(db, prefix, exclude_id=None):
    prefix = (prefix or "").upper()
    rows = db.execute(
        "SELECT id, subcontractor_code FROM subcontractors "
        "WHERE subcontractor_code IS NOT NULL AND TRIM(subcontractor_code) != ''"
    ).fetchall()
    for row in rows:
        if exclude_id is not None and row["id"] == exclude_id:
            continue
        if subcontractor_code_prefix(row["subcontractor_code"]) == prefix:
            return True
    return False


def resolve_subcontractor_prefix(db, name, exclude_id=None):
    for prefix in _subcontractor_prefix_candidates(name):
        if not _subcontractor_prefix_in_use(db, prefix, exclude_id=exclude_id):
            return prefix
    return _subcontractor_prefix_candidates(name)[0]


def _max_prefix_code_number(db, prefix):
    max_num = 99
    for table, column in (("subcontractors", "subcontractor_code"), ("workers", "worker_code")):
        rows = db.execute(
            f"SELECT {column} AS code FROM {table} WHERE {column} LIKE ?",
            (f"{prefix}%",),
        ).fetchall()
        for row in rows:
            code = str(row["code"] or "").strip().upper()
            if not code.startswith(prefix):
                continue
            number = code[len(prefix):]
            if number.isdigit():
                max_num = max(max_num, int(number))
    return max_num


def generate_subcontractor_code(db, name):
    prefix = resolve_subcontractor_prefix(db, name)
    max_num = _max_prefix_code_number(db, prefix)
    next_num = 100 if max_num < 100 else max_num + 1
    return f"{prefix}{next_num}"


def subcontractor_code_from_vendor(vendor_row):
    """Subcontractor ID is the linked vendor code (e.g. VEN101)."""
    code = str(vendor_row.get("code") or "").strip().upper()
    if code:
        return code
    vendor_id = vendor_row.get("id")
    if vendor_id:
        return f"VEN{vendor_id}"
    return ""


def normalize_subcontractor_rate_type(rate_type):
    """Map stored work type (including legacy values) to current choice."""
    text = str(rate_type or "").strip()
    if text in SUBCONTRACTOR_RATE_TYPES:
        return text
    return _SUBCONTRACTOR_LEGACY_RATE_TYPES.get(text, "Labour Supply")


def subcontractor_rate_type_label(rate_type):
    normalized = normalize_subcontractor_rate_type(rate_type)
    for choice in SUBCONTRACTOR_RATE_TYPE_CHOICES:
        if choice["value"] == normalized:
            return choice["label"]
    return rate_type or "—"


def subcontractor_uses_manpower_rates(rate_type):
    return normalize_subcontractor_rate_type(rate_type) == "Labour Supply"


def subcontractor_uses_boq_rates(rate_type):
    return normalize_subcontractor_rate_type(rate_type) in (
        "Item Rate Contract",
        "Measurement Based Contract",
    )


def generate_worker_code(db, worker_category, subcontractor_id=None):
    if worker_category == "Sub Contractor Staff" and subcontractor_id:
        sub = db.execute(
            "SELECT subcontractor_code, subcontractor_name FROM subcontractors WHERE id=?",
            (subcontractor_id,),
        ).fetchone()
        if sub:
            if sub["subcontractor_code"]:
                prefix = subcontractor_code_prefix(sub["subcontractor_code"])
            elif sub["subcontractor_name"]:
                prefix = resolve_subcontractor_prefix(db, sub["subcontractor_name"])
            else:
                prefix = "SU"
            max_num = _max_prefix_code_number(db, prefix)
            next_num = max_num + 1 if max_num >= 100 else 101
            return f"{prefix}{next_num}"
    rows = db.execute("SELECT worker_code FROM workers WHERE worker_code LIKE 'WRK%'").fetchall()
    max_code = 100
    for row in rows:
        code = str(row["worker_code"] or "").strip().upper()
        number = code[3:]
        if number.isdigit():
            max_code = max(max_code, int(number))
    return f"WRK{max_code + 1}"


def backfill_subcontractor_codes(db):
    rows = db.execute(
        "SELECT s.id, s.subcontractor_name, s.vendor_id, v.code AS vendor_code "
        "FROM subcontractors s "
        "LEFT JOIN vendors v ON s.vendor_id = v.id "
        "WHERE s.subcontractor_code IS NULL OR TRIM(s.subcontractor_code) = '' "
        "ORDER BY s.id"
    ).fetchall()
    for row in rows:
        if row["vendor_code"]:
            code = str(row["vendor_code"]).strip().upper()
        else:
            code = generate_subcontractor_code(db, row["subcontractor_name"])
        db.execute(
            "UPDATE subcontractors SET subcontractor_code=? WHERE id=?",
            (code, row["id"]),
        )


def ensure_subcontractor_rate_tables(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS subcontractor_manpower_rates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcontractor_id INTEGER NOT NULL,
            trade_name TEXT,
            rate_unit TEXT,
            working_hours REAL,
            rate_amount REAL,
            salary_amount REAL,
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS subcontractor_boq_rates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcontractor_id INTEGER NOT NULL,
            project_id INTEGER,
            boq_item_id INTEGER,
            boq_number TEXT,
            item_description TEXT,
            unit TEXT,
            rate REAL,
            quantity REAL,
            total_amount REAL,
            line_no INTEGER,
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for table, column, col_type in (
        ("subcontractor_manpower_rates", "subcontractor_id", "INTEGER"),
        ("subcontractor_manpower_rates", "trade_name", "TEXT"),
        ("subcontractor_manpower_rates", "rate_unit", "TEXT"),
        ("subcontractor_manpower_rates", "working_hours", "REAL"),
        ("subcontractor_manpower_rates", "rate_amount", "REAL"),
        ("subcontractor_manpower_rates", "salary_amount", "REAL"),
        ("subcontractor_boq_rates", "subcontractor_id", "INTEGER"),
        ("subcontractor_boq_rates", "project_id", "INTEGER"),
        ("subcontractor_boq_rates", "boq_item_id", "INTEGER"),
        ("subcontractor_boq_rates", "boq_number", "TEXT"),
        ("subcontractor_boq_rates", "item_description", "TEXT"),
        ("subcontractor_boq_rates", "unit", "TEXT"),
        ("subcontractor_boq_rates", "rate", "REAL"),
        ("subcontractor_boq_rates", "quantity", "REAL"),
        ("subcontractor_boq_rates", "total_amount", "REAL"),
        ("subcontractor_boq_rates", "line_no", "INTEGER"),
    ):
        _ensure_column(db, table, column, col_type)


def _parse_subcontractor_manpower_rates():
    trades = request.form.getlist("mp_trade_name[]")
    units = request.form.getlist("mp_rate_unit[]")
    working_hours_list = request.form.getlist("mp_working_hours[]")
    salary_amounts = request.form.getlist("mp_salary_amount[]")
    rows = []
    for idx, trade in enumerate(trades):
        trade_name = (trade or "").strip()
        if not trade_name:
            continue
        rate_unit = units[idx].strip() if idx < len(units) else "Day"
        try:
            working_hours = float(working_hours_list[idx] or 8) if idx < len(working_hours_list) else 8.0
        except ValueError:
            working_hours = 8.0
        if working_hours <= 0:
            working_hours = 8.0
        try:
            salary_amount = float(salary_amounts[idx] or 0) if idx < len(salary_amounts) else 0.0
        except ValueError:
            salary_amount = 0.0
        if salary_amount <= 0:
            continue
        rate_amount = (
            round(salary_amount / working_hours, 2)
            if rate_unit == "Hour"
            else salary_amount
        )
        rows.append({
            "trade_name": trade_name,
            "rate_unit": rate_unit or "Day",
            "working_hours": working_hours,
            "rate_amount": rate_amount,
            "salary_amount": salary_amount,
        })
    if len(rows) > MAX_MANPOWER_TRADES:
        return None, f"Maximum {MAX_MANPOWER_TRADES} trade rates allowed."
    return rows, None


def _parse_subcontractor_boq_rates():
    project_id = request.form.get("boq_project_id", "").strip()
    item_ids = request.form.getlist("sb_boq_item_id[]")
    boq_numbers = request.form.getlist("sb_boq_number[]")
    descriptions = request.form.getlist("sb_item_description[]")
    units = request.form.getlist("sb_unit[]")
    rates = request.form.getlist("sb_rate[]")
    quantities = request.form.getlist("sb_quantity[]")
    totals = request.form.getlist("sb_total_amount[]")
    rows = []
    for idx, item_id in enumerate(item_ids):
        if not (item_id or "").strip() and not (descriptions[idx] if idx < len(descriptions) else "").strip():
            continue
        try:
            rate_val = float(rates[idx] or 0) if idx < len(rates) else 0.0
        except ValueError:
            rate_val = 0.0
        try:
            qty_val = float(quantities[idx] or 0) if idx < len(quantities) else 0.0
        except ValueError:
            qty_val = 0.0
        try:
            total_val = float(totals[idx] or 0) if idx < len(totals) else 0.0
        except ValueError:
            total_val = round(rate_val * qty_val, 2)
        if total_val <= 0 and rate_val <= 0:
            continue
        rows.append({
            "boq_item_id": int(item_id) if (item_id or "").strip().isdigit() else None,
            "boq_number": boq_numbers[idx].strip() if idx < len(boq_numbers) else "",
            "item_description": descriptions[idx].strip() if idx < len(descriptions) else "",
            "unit": units[idx].strip() if idx < len(units) else "",
            "rate": rate_val,
            "quantity": qty_val,
            "total_amount": total_val if total_val > 0 else round(rate_val * qty_val, 2),
            "line_no": idx + 1,
        })
    return project_id or None, rows


def _insert_subcontractor_manpower_rates(db, subcontractor_id, manpower_rows):
    for row in manpower_rows:
        db.execute(
            "INSERT INTO subcontractor_manpower_rates("
            "subcontractor_id, trade_name, rate_unit, working_hours, rate_amount, salary_amount"
            ") VALUES(?,?,?,?,?,?)",
            (
                subcontractor_id, row["trade_name"], row["rate_unit"],
                row["working_hours"], row["rate_amount"], row["salary_amount"],
            ),
        )


def _insert_subcontractor_boq_rates(db, subcontractor_id, project_id, boq_rows):
    for line in boq_rows:
        db.execute(
            "INSERT INTO subcontractor_boq_rates("
            "subcontractor_id, project_id, boq_item_id, boq_number, item_description, "
            "unit, rate, quantity, total_amount, line_no"
            ") VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                subcontractor_id, project_id, line["boq_item_id"],
                line["boq_number"], line["item_description"], line["unit"],
                line["rate"], line["quantity"], line["total_amount"], line["line_no"],
            ),
        )


def _sync_subcontractor_rates(db, subcontractor_id, rate_type, is_update=False):
    rate_type = normalize_subcontractor_rate_type(rate_type)
    if subcontractor_uses_manpower_rates(rate_type):
        db.execute("DELETE FROM subcontractor_boq_rates WHERE subcontractor_id=?", (subcontractor_id,))
        manpower_rows, mp_error = _parse_subcontractor_manpower_rates()
        if mp_error:
            return mp_error
        if not manpower_rows:
            if is_update:
                return None
            return "Add at least one manpower trade rate."
        db.execute(
            "DELETE FROM subcontractor_manpower_rates WHERE subcontractor_id=?",
            (subcontractor_id,),
        )
        _insert_subcontractor_manpower_rates(db, subcontractor_id, manpower_rows)
        return None
    if subcontractor_uses_boq_rates(rate_type):
        db.execute(
            "DELETE FROM subcontractor_manpower_rates WHERE subcontractor_id=?",
            (subcontractor_id,),
        )
        project_id, boq_rows = _parse_subcontractor_boq_rates()
        if boq_rows:
            if not project_id:
                return "Select a project for BOQ / item rates."
            db.execute(
                "DELETE FROM subcontractor_boq_rates WHERE subcontractor_id=?",
                (subcontractor_id,),
            )
            _insert_subcontractor_boq_rates(db, subcontractor_id, project_id, boq_rows)
        elif not is_update:
            return "Add at least one BOQ / item rate line."
        return None
    if rate_type == "Lump Sum Contract":
        return None
    return None


def _subcontractor_dependent_counts(db, subcontractor_id):
    workers = db.execute(
        "SELECT COUNT(*) AS c FROM workers WHERE subcontractor_id=?",
        (subcontractor_id,),
    ).fetchone()["c"]
    requests = db.execute(
        "SELECT COUNT(*) AS c FROM subcontract_requests WHERE subcontractor_id=?",
        (subcontractor_id,),
    ).fetchone()["c"]
    return int(workers or 0), int(requests or 0)


def generate_client_code(db):
    rows = db.execute("SELECT client_code FROM clients WHERE client_code LIKE 'CLT%'").fetchall()
    max_code = 100
    for row in rows:
        code = str(row["client_code"] or "").strip().upper()
        number = code[3:]
        if number.isdigit():
            max_code = max(max_code, int(number))
    return f"CLT{max_code + 1}"


def extract_name_prefix(name):
    """First two letters of a name (uppercase, letters only); pad single letter."""
    letters = re.sub(r"[^A-Za-z]", "", str(name or ""))
    if len(letters) >= 2:
        return letters[:2].upper()
    if len(letters) == 1:
        return (letters[0] * 2).upper()
    return "XX"


def parse_prefixed_number(code):
    """Parse codes like MA100 into (prefix, number) or (None, None)."""
    text = str(code or "").strip().upper()
    if len(text) < 4 or not text[:2].isalpha():
        return None, None
    suffix = text[2:]
    if not suffix.isdigit():
        return None, None
    return text[:2], int(suffix)


def ensure_number_sequences_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS number_sequences(
            prefix TEXT PRIMARY KEY,
            last_number INTEGER NOT NULL DEFAULT 99
        )
    """)


def _max_prefixed_number_for_prefix(db, prefix):
    max_num = 99
    prefix = str(prefix or "").upper()
    like_pattern = f"{prefix}%"
    for table, column in (("projects", "project_code"), ("boq_master", "boq_number")):
        if not _table_exists(db, table):
            continue
        rows = db.execute(
            f"SELECT {column} AS code FROM {table} WHERE {column} LIKE ?",
            (like_pattern,),
        ).fetchall()
        for row in rows:
            row_prefix, number = parse_prefixed_number(row["code"])
            if row_prefix == prefix and number is not None:
                max_num = max(max_num, number)
    return max_num


def sync_prefix_sequence(db, prefix):
    """Raise number_sequences.last_number to match existing project/BOQ codes."""
    ensure_number_sequences_table(db)
    prefix = str(prefix or "").upper()
    max_num = _max_prefixed_number_for_prefix(db, prefix)
    db.execute(
        "INSERT INTO number_sequences(prefix, last_number) VALUES(?, ?) "
        "ON CONFLICT(prefix) DO NOTHING",
        (prefix, max_num),
    )
    db.execute(
        "UPDATE number_sequences SET last_number = MAX(last_number, ?) WHERE prefix=?",
        (max_num, prefix),
    )


def allocate_next_prefixed_number(db, prefix):
    """Allocate next number for prefix (shared by projects and BOQ masters)."""
    prefix = str(prefix or "").upper()
    sync_prefix_sequence(db, prefix)
    db.execute(
        "UPDATE number_sequences SET last_number = last_number + 1 WHERE prefix=?",
        (prefix,),
    )
    row = db.execute(
        "SELECT last_number FROM number_sequences WHERE prefix=?",
        (prefix,),
    ).fetchone()
    return f"{prefix}{int(row['last_number'])}"


def peek_next_prefixed_number(db, prefix):
    """Preview next number without consuming the sequence."""
    prefix = str(prefix or "").upper()
    sync_prefix_sequence(db, prefix)
    row = db.execute(
        "SELECT last_number FROM number_sequences WHERE prefix=?",
        (prefix,),
    ).fetchone()
    last_number = int(row["last_number"]) if row else 99
    counter_next = last_number + 1
    existing_max = _max_prefixed_number_for_prefix(db, prefix)
    return f"{prefix}{max(counter_next, existing_max + 1)}"


def generate_project_code(db, project_name):
    """Return next project number: 2-letter prefix from name + running sequence from 100."""
    prefix = extract_name_prefix(project_name)
    return allocate_next_prefixed_number(db, prefix)


def peek_project_code(db, project_name):
    if not str(project_name or "").strip():
        return "—"
    prefix = extract_name_prefix(project_name)
    return peek_next_prefixed_number(db, prefix)


def get_workflow_modules():
    return query_db(
        "SELECT module_id, module_name FROM workflow_master WHERE status='Active' ORDER BY module_name"
    )


def ensure_user_maker_assignments_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS user_maker_assignments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            slot_no INTEGER NOT NULL,
            department TEXT,
            module_id TEXT,
            status TEXT DEFAULT 'Active',
            UNIQUE(user_id, slot_no),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)


def save_user_maker_assignments(db, user_id, departments, module_ids, statuses):
    ensure_user_maker_assignments_table(db)
    db.execute("DELETE FROM user_maker_assignments WHERE user_id=?", (user_id,))
    for idx, dept in enumerate(departments):
        module_id = module_ids[idx] if idx < len(module_ids) else ""
        status = statuses[idx] if idx < len(statuses) else "Active"
        dept = (dept or "").strip()
        module_id = (module_id or "").strip()
        if not dept and not module_id:
            continue
        db.execute(
            "INSERT INTO user_maker_assignments(user_id, slot_no, department, module_id, status) "
            "VALUES(?,?,?,?,?)",
            (user_id, idx + 1, dept, module_id, status or "Active"),
        )


def get_user_maker_assignments(db, user_id):
    ensure_user_maker_assignments_table(db)
    return query_db(
        "SELECT * FROM user_maker_assignments WHERE user_id=? ORDER BY slot_no",
        (user_id,),
    )


def _ensure_boq_schema_columns(db):
    """Backfill BOQ columns for VPS databases created before soft-delete support."""
    for table, column, col_type in (
        ("boq_master", "modified_by", "TEXT"),
        ("boq_master", "modified_at", "TEXT"),
        ("boq_master", "deleted_by", "TEXT"),
        ("boq_master", "deleted_at", "TEXT"),
        ("boq_master", "is_deleted", "INTEGER DEFAULT 0"),
        ("boq_items", "boq_id", "INTEGER"),
        ("boq_items", "line_no", "INTEGER"),
        ("boq_items", "item_code", "TEXT"),
        ("boq_items", "created_at", "TEXT"),
        ("boq_items", "modified_by", "TEXT"),
        ("boq_items", "modified_at", "TEXT"),
        ("boq_items", "deleted_by", "TEXT"),
        ("boq_items", "deleted_at", "TEXT"),
        ("boq_items", "is_deleted", "INTEGER DEFAULT 0"),
    ):
        _ensure_column(db, table, column, col_type)


def ensure_boq_master_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS boq_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boq_number TEXT,
            project_id INTEGER,
            total_amount REAL DEFAULT 0,
            line_count INTEGER DEFAULT 0,
            created_by TEXT,
            modified_by TEXT,
            deleted_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            created_at TEXT,
            modified_at TEXT,
            deleted_at TEXT,
            is_deleted INTEGER DEFAULT 0,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    _ensure_boq_schema_columns(db)


def generate_boq_number(db, project_id):
    """BOQ master number: same prefix+sequence rules as projects (per project name prefix)."""
    project = db.execute(
        "SELECT project_name FROM projects WHERE id=?",
        (project_id,),
    ).fetchone()
    if not project:
        return allocate_next_prefixed_number(db, "XX")
    prefix = extract_name_prefix(project["project_name"])
    return allocate_next_prefixed_number(db, prefix)


def peek_boq_number(db, project_id):
    project = db.execute(
        "SELECT project_name FROM projects WHERE id=?",
        (project_id,),
    ).fetchone()
    if not project:
        return "—"
    prefix = extract_name_prefix(project["project_name"])
    return peek_next_prefixed_number(db, prefix)


def boq_item_code(line_no):
    return f"BOQ{int(line_no)}"


def ensure_dpr_measurement_tables(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS steel_shapes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shape_name TEXT NOT NULL,
            side_count INTEGER DEFAULT 1,
            formula_type TEXT DEFAULT 'straight',
            created_by TEXT,
            created_at TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS dpr_measurements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            report_date TEXT,
            boq_item_id INTEGER,
            boq_number TEXT,
            boq_description TEXT,
            unit TEXT,
            calculated_quantity REAL DEFAULT 0,
            measurement_type TEXT,
            bill_client INTEGER DEFAULT 0,
            for_costing INTEGER DEFAULT 0,
            billing_status TEXT DEFAULT 'none',
            costing_status TEXT DEFAULT 'none',
            measurement_data TEXT,
            created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            created_at TEXT,
            work_description TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(boq_item_id) REFERENCES boq_items(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS dpr_steel_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            measurement_id INTEGER,
            line_description TEXT,
            num_bars INTEGER DEFAULT 0,
            cutting_length REAL DEFAULT 0,
            diameter_mm REAL DEFAULT 0,
            shape_id INTEGER,
            side_measurements TEXT,
            quantity REAL DEFAULT 0,
            FOREIGN KEY(measurement_id) REFERENCES dpr_measurements(id),
            FOREIGN KEY(shape_id) REFERENCES steel_shapes(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS dpr_manpower(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            measurement_id INTEGER,
            subcontractor_id INTEGER,
            worker_id INTEGER,
            worker_name TEXT,
            trade_name TEXT,
            hours_worked REAL DEFAULT 0,
            remarks TEXT,
            FOREIGN KEY(measurement_id) REFERENCES dpr_measurements(id),
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id),
            FOREIGN KEY(worker_id) REFERENCES workers(id)
        )
    """)
    count = db.execute("SELECT COUNT(*) AS c FROM steel_shapes").fetchone()["c"]
    if count == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for name, sides, formula in DEFAULT_STEEL_SHAPES:
            db.execute(
                "INSERT INTO steel_shapes(shape_name, side_count, formula_type, created_by, created_at) "
                "VALUES(?,?,?,?,?)",
                (name, sides, formula, "system", now),
            )
    _ensure_dpr_measurement_columns(db)
    db.commit()


def _ensure_dpr_measurement_columns(db):
    """Backfill columns when dpr_measurements was created from an older/partial schema."""
    for table, column, col_type in (
        ("dpr_measurements", "project_id", "INTEGER"),
        ("dpr_measurements", "report_date", "TEXT"),
        ("dpr_measurements", "boq_item_id", "INTEGER"),
        ("dpr_measurements", "boq_number", "TEXT"),
        ("dpr_measurements", "boq_description", "TEXT"),
        ("dpr_measurements", "unit", "TEXT"),
        ("dpr_measurements", "calculated_quantity", "REAL DEFAULT 0"),
        ("dpr_measurements", "measurement_type", "TEXT"),
        ("dpr_measurements", "bill_client", "INTEGER DEFAULT 0"),
        ("dpr_measurements", "for_costing", "INTEGER DEFAULT 0"),
        ("dpr_measurements", "billing_status", "TEXT DEFAULT 'none'"),
        ("dpr_measurements", "costing_status", "TEXT DEFAULT 'none'"),
        ("dpr_measurements", "measurement_data", "TEXT"),
        ("dpr_measurements", "created_by", "TEXT"),
        ("dpr_measurements", "approval_status", "TEXT DEFAULT 'Pending Checker'"),
        ("dpr_measurements", "created_at", "TEXT"),
        ("dpr_measurements", "work_description", "TEXT"),
        ("dpr_steel_lines", "measurement_id", "INTEGER"),
        ("dpr_steel_lines", "line_description", "TEXT"),
        ("dpr_steel_lines", "num_bars", "INTEGER DEFAULT 0"),
        ("dpr_steel_lines", "cutting_length", "REAL DEFAULT 0"),
        ("dpr_steel_lines", "diameter_mm", "REAL DEFAULT 0"),
        ("dpr_steel_lines", "shape_id", "INTEGER"),
        ("dpr_steel_lines", "side_measurements", "TEXT"),
        ("dpr_steel_lines", "quantity", "REAL DEFAULT 0"),
        ("dpr_manpower", "measurement_id", "INTEGER"),
        ("dpr_manpower", "subcontractor_id", "INTEGER"),
        ("dpr_manpower", "worker_id", "INTEGER"),
        ("dpr_manpower", "worker_name", "TEXT"),
        ("dpr_manpower", "trade_name", "TEXT"),
        ("dpr_manpower", "hours_worked", "REAL DEFAULT 0"),
        ("dpr_manpower", "remarks", "TEXT"),
        ("dpr_measurements", "dpr_status", "TEXT DEFAULT 'submitted'"),
        ("dpr_measurements", "modified_at", "TEXT"),
        ("dpr_measurements", "modified_by", "TEXT"),
    ):
        _ensure_column(db, table, column, col_type)


DEFAULT_DPR_ACTIVITIES = (
    "Excavation",
    "PCC",
    "Steel Fixing",
    "Shuttering",
    "Concreting",
    "Slab Work",
    "Plastering",
    "Block Work",
    "Waterproofing",
    "Finishing",
)


DEFAULT_EQUIPMENT_MASTER = (
    ("EX-01", "Excavator", "Excavator", "Company Owned", 2500.0, 0.0, 0.0),
    ("JE-01", "JCB Loader", "Loader", "Company Owned", 1800.0, 0.0, 0.0),
    ("CR-01", "Mobile Crane", "Crane", "Hired Equipment", 3500.0, 0.0, 0.0),
    ("TK-01", "Tipper Truck", "Truck", "Hired Equipment", 0.0, 45.0, 1500.0),
    ("MX-01", "Concrete Mixer", "Mixer", "Company Owned", 800.0, 0.0, 0.0),
    ("CP-01", "Concrete Pump", "Pump", "Hired Equipment", 4000.0, 0.0, 0.0),
    ("VL-01", "Vibrator", "Vibrator", "Company Owned", 400.0, 0.0, 0.0),
    ("GN-01", "Generator", "Generator", "Company Owned", 600.0, 0.0, 0.0),
)


def ensure_equipment_master_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS equipment_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reg_no TEXT UNIQUE,
            equipment_name TEXT NOT NULL,
            equipment_type TEXT,
            owner_type TEXT DEFAULT 'Company Owned',
            hourly_rate REAL DEFAULT 0,
            km_rate REAL DEFAULT 0,
            trip_rate REAL DEFAULT 0,
            status TEXT DEFAULT 'Active',
            created_at TEXT
        )
    """)
    count = db.execute("SELECT COUNT(*) AS c FROM equipment_master").fetchone()["c"]
    if count == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for reg_no, name, eq_type, owner, hourly, km, trip in DEFAULT_EQUIPMENT_MASTER:
            db.execute(
                "INSERT INTO equipment_master(reg_no, equipment_name, equipment_type, owner_type, "
                "hourly_rate, km_rate, trip_rate, status, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (reg_no, name, eq_type, owner, hourly, km, trip, "Active", now),
            )
    db.commit()


def ensure_dpr_attachments_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS dpr_attachments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            report_date TEXT,
            measurement_id INTEGER,
            original_filename TEXT,
            stored_filename TEXT NOT NULL,
            file_ext TEXT,
            file_size INTEGER DEFAULT 0,
            notes TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(measurement_id) REFERENCES dpr_measurements(id)
        )
    """)


def _petty_cash_table_columns(db, table):
    if not _table_exists(db, table):
        return set()
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}


def _backfill_petty_cash_legacy_columns(db):
    """Copy legacy VPS petty_cash_requests columns into the new FRS schema."""
    if not _table_exists(db, "petty_cash_requests"):
        return
    cols = _petty_cash_table_columns(db, "petty_cash_requests")

    if "reason" in cols and "purpose" in cols:
        db.execute(
            "UPDATE petty_cash_requests SET purpose=reason "
            "WHERE (purpose IS NULL OR TRIM(purpose)='') "
            "AND reason IS NOT NULL AND TRIM(reason)!=''"
        )
    if "requested_amount" in cols and "required_amount" in cols:
        db.execute(
            "UPDATE petty_cash_requests SET required_amount=requested_amount "
            "WHERE (required_amount IS NULL OR required_amount=0) "
            "AND requested_amount IS NOT NULL AND requested_amount>0"
        )
    if "requested_by" in cols and "staff_name" in cols:
        db.execute(
            "UPDATE petty_cash_requests SET staff_name=requested_by "
            "WHERE (staff_name IS NULL OR TRIM(staff_name)='') "
            "AND requested_by IS NOT NULL AND TRIM(requested_by)!=''"
        )
    if "released_amount" in cols and "transferred_amount" in cols:
        db.execute(
            "UPDATE petty_cash_requests SET transferred_amount=released_amount "
            "WHERE (transferred_amount IS NULL OR transferred_amount=0) "
            "AND released_amount IS NOT NULL AND released_amount>0"
        )
    if "request_number" in cols:
        if "document_no" in cols:
            db.execute(
                "UPDATE petty_cash_requests SET request_number=document_no "
                "WHERE (request_number IS NULL OR TRIM(request_number)='') "
                "AND document_no IS NOT NULL AND TRIM(document_no)!=''"
            )
        if "request_id" in cols:
            db.execute(
                "UPDATE petty_cash_requests SET request_number=CAST(request_id AS TEXT) "
                "WHERE (request_number IS NULL OR TRIM(request_number)='') "
                "AND request_id IS NOT NULL AND TRIM(CAST(request_id AS TEXT))!=''"
            )
        db.execute(
            "UPDATE petty_cash_requests SET request_number='PCR-LEGACY-' || id "
            "WHERE request_number IS NULL OR TRIM(request_number)=''"
        )
    if "prepared_by" in cols and "created_by" in cols:
        db.execute(
            "UPDATE petty_cash_requests SET created_by=prepared_by "
            "WHERE (created_by IS NULL OR TRIM(created_by)='') "
            "AND prepared_by IS NOT NULL AND TRIM(prepared_by)!=''"
        )
    if "approval_status" in cols:
        if "approved_by" in cols:
            db.execute(
                "UPDATE petty_cash_requests SET approval_status='Approved' "
                "WHERE (approval_status IS NULL OR TRIM(approval_status)='' "
                "OR approval_status='Draft') "
                "AND approved_by IS NOT NULL AND TRIM(approved_by)!=''"
            )
        if "verified_by" in cols:
            db.execute(
                "UPDATE petty_cash_requests SET approval_status='Pending Approver' "
                "WHERE (approval_status IS NULL OR TRIM(approval_status)='' "
                "OR approval_status='Draft') "
                "AND verified_by IS NOT NULL AND TRIM(verified_by)!='' "
                "AND (approved_by IS NULL OR TRIM(approved_by)='')"
            )
        db.execute(
            "UPDATE petty_cash_requests SET approval_status='Draft' "
            "WHERE approval_status IS NULL OR TRIM(approval_status)=''"
        )
    if "project_id" in cols and "project_name" in cols:
        db.execute(
            "UPDATE petty_cash_requests SET project_id=("
            "SELECT p.id FROM projects p "
            "WHERE p.project_name=petty_cash_requests.project_name "
            "ORDER BY p.id LIMIT 1"
            ") WHERE project_id IS NULL "
            "AND project_name IS NOT NULL AND TRIM(project_name)!=''"
        )
    if "modified_at" in cols and "created_at" in cols:
        db.execute(
            "UPDATE petty_cash_requests SET modified_at=created_at "
            "WHERE (modified_at IS NULL OR TRIM(modified_at)='') "
            "AND created_at IS NOT NULL AND TRIM(created_at)!=''"
        )
    if "settlement_remarks" in cols and "rejection_reason" in cols:
        db.execute(
            "UPDATE petty_cash_requests SET settlement_remarks=rejection_reason "
            "WHERE (settlement_remarks IS NULL OR TRIM(settlement_remarks)='') "
            "AND rejection_reason IS NOT NULL AND TRIM(rejection_reason)!=''"
        )


def ensure_petty_cash_tables(db):
    """Create petty cash FRS tables and ensure dependent schema exists."""
    _ensure_column(db, "projects", "project_code", "TEXT")
    ensure_department_master(db)
    db.execute("""
        CREATE TABLE IF NOT EXISTS petty_cash_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_number TEXT UNIQUE,
            request_date TEXT,
            project_id INTEGER,
            staff_id INTEGER,
            staff_name TEXT,
            employee_code TEXT,
            department TEXT,
            purpose TEXT,
            description TEXT,
            required_amount REAL DEFAULT 0,
            priority TEXT DEFAULT 'Normal',
            remarks TEXT,
            status TEXT DEFAULT 'Draft',
            approval_status TEXT DEFAULT 'Draft',
            transferred_amount REAL DEFAULT 0,
            expenses_total REAL DEFAULT 0,
            settlement_remarks TEXT,
            settlement_submitted_at TEXT,
            settlement_reviewed_at TEXT,
            settlement_reviewed_by TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(staff_id) REFERENCES staff(id)
        )
    """)
    for column, col_type in (
        ("request_number", "TEXT"),
        ("request_date", "TEXT"),
        ("project_id", "INTEGER"),
        ("staff_id", "INTEGER"),
        ("staff_name", "TEXT"),
        ("employee_code", "TEXT"),
        ("department", "TEXT"),
        ("purpose", "TEXT"),
        ("description", "TEXT"),
        ("required_amount", "REAL DEFAULT 0"),
        ("priority", "TEXT DEFAULT 'Normal'"),
        ("remarks", "TEXT"),
        ("status", "TEXT DEFAULT 'Draft'"),
        ("approval_status", "TEXT DEFAULT 'Draft'"),
        ("transferred_amount", "REAL DEFAULT 0"),
        ("expenses_total", "REAL DEFAULT 0"),
        ("settlement_remarks", "TEXT"),
        ("settlement_submitted_at", "TEXT"),
        ("settlement_reviewed_at", "TEXT"),
        ("settlement_reviewed_by", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "petty_cash_requests", column, col_type)
    db.execute("""
        CREATE TABLE IF NOT EXISTS petty_cash_transfers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            transfer_date TEXT,
            amount REAL DEFAULT 0,
            bank_name TEXT,
            account_number TEXT,
            utr_number TEXT,
            reference_number TEXT,
            payment_mode TEXT,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            FOREIGN KEY(request_id) REFERENCES petty_cash_requests(id)
        )
    """)
    for column, col_type in (
        ("request_id", "INTEGER"),
        ("transfer_date", "TEXT"),
        ("amount", "REAL DEFAULT 0"),
        ("bank_name", "TEXT"),
        ("account_number", "TEXT"),
        ("utr_number", "TEXT"),
        ("reference_number", "TEXT"),
        ("payment_mode", "TEXT"),
        ("remarks", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
    ):
        _ensure_column(db, "petty_cash_transfers", column, col_type)
    db.execute("""
        CREATE TABLE IF NOT EXISTS petty_cash_expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            expense_category TEXT,
            description TEXT,
            vendor TEXT,
            bill_number TEXT,
            amount REAL DEFAULT 0,
            staff_id INTEGER,
            staff_name TEXT,
            employee_code TEXT,
            created_by TEXT,
            created_at TEXT,
            FOREIGN KEY(request_id) REFERENCES petty_cash_requests(id),
            FOREIGN KEY(staff_id) REFERENCES staff(id)
        )
    """)
    for column, col_type in (
        ("request_id", "INTEGER"),
        ("expense_category", "TEXT"),
        ("description", "TEXT"),
        ("vendor", "TEXT"),
        ("bill_number", "TEXT"),
        ("amount", "REAL DEFAULT 0"),
        ("staff_id", "INTEGER"),
        ("staff_name", "TEXT"),
        ("employee_code", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
    ):
        _ensure_column(db, "petty_cash_expenses", column, col_type)
    db.execute("""
        CREATE TABLE IF NOT EXISTS petty_cash_attachments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            expense_id INTEGER,
            original_filename TEXT,
            stored_filename TEXT NOT NULL,
            file_ext TEXT,
            file_size INTEGER DEFAULT 0,
            uploaded_by TEXT,
            uploaded_at TEXT,
            FOREIGN KEY(request_id) REFERENCES petty_cash_requests(id),
            FOREIGN KEY(expense_id) REFERENCES petty_cash_expenses(id)
        )
    """)
    for column, col_type in (
        ("request_id", "INTEGER"),
        ("expense_id", "INTEGER"),
        ("original_filename", "TEXT"),
        ("stored_filename", "TEXT"),
        ("file_ext", "TEXT"),
        ("file_size", "INTEGER DEFAULT 0"),
        ("uploaded_by", "TEXT"),
        ("uploaded_at", "TEXT"),
    ):
        _ensure_column(db, "petty_cash_attachments", column, col_type)
    _backfill_petty_cash_legacy_columns(db)
    try:
        db.commit()
    except sqlite3.Error:
        pass


def ensure_security_guarantees_tables(db):
    """Security Deposit / Treasury / Bank Guarantee register tables."""
    _ensure_column(db, "projects", "project_code", "TEXT")
    db.execute("""
        CREATE TABLE IF NOT EXISTS security_guarantees(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            register_number TEXT UNIQUE,
            security_type TEXT NOT NULL,
            project_id INTEGER,
            project_name TEXT,
            project_code TEXT,
            client_name TEXT,
            agreement_number TEXT,
            agreement_date TEXT,
            work_order_number TEXT,
            contract_value REAL DEFAULT 0,
            deposit_amount REAL DEFAULT 0,
            bank_name TEXT,
            branch_name TEXT,
            account_number TEXT,
            instrument_number TEXT,
            challan_number TEXT,
            bg_number TEXT,
            beneficiary_name TEXT,
            issuing_bank TEXT,
            deposit_date TEXT,
            issue_date TEXT,
            expiry_date TEXT,
            maturity_date TEXT,
            release_date TEXT,
            extension_date TEXT,
            interest_rate REAL DEFAULT 0,
            interest_amount REAL DEFAULT 0,
            total_recoverable REAL DEFAULT 0,
            tender_number TEXT,
            tender_date TEXT,
            tender_authority TEXT,
            emd_mode TEXT,
            bill_number TEXT,
            bill_date TEXT,
            retention_percent REAL DEFAULT 0,
            bill_amount REAL DEFAULT 0,
            retention_amount REAL DEFAULT 0,
            claim_period TEXT,
            status TEXT DEFAULT 'Draft',
            release_remarks TEXT,
            extension_remarks TEXT,
            remarks TEXT,
            released_by TEXT,
            approved_by TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_by TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for column, col_type in (
        ("register_number", "TEXT"),
        ("security_type", "TEXT"),
        ("project_id", "INTEGER"),
        ("project_name", "TEXT"),
        ("project_code", "TEXT"),
        ("client_name", "TEXT"),
        ("agreement_number", "TEXT"),
        ("agreement_date", "TEXT"),
        ("work_order_number", "TEXT"),
        ("contract_value", "REAL DEFAULT 0"),
        ("deposit_amount", "REAL DEFAULT 0"),
        ("bank_name", "TEXT"),
        ("branch_name", "TEXT"),
        ("account_number", "TEXT"),
        ("instrument_number", "TEXT"),
        ("challan_number", "TEXT"),
        ("bg_number", "TEXT"),
        ("beneficiary_name", "TEXT"),
        ("issuing_bank", "TEXT"),
        ("deposit_date", "TEXT"),
        ("issue_date", "TEXT"),
        ("expiry_date", "TEXT"),
        ("maturity_date", "TEXT"),
        ("release_date", "TEXT"),
        ("extension_date", "TEXT"),
        ("interest_rate", "REAL DEFAULT 0"),
        ("interest_amount", "REAL DEFAULT 0"),
        ("total_recoverable", "REAL DEFAULT 0"),
        ("tender_number", "TEXT"),
        ("tender_date", "TEXT"),
        ("tender_authority", "TEXT"),
        ("emd_mode", "TEXT"),
        ("bill_number", "TEXT"),
        ("bill_date", "TEXT"),
        ("retention_percent", "REAL DEFAULT 0"),
        ("bill_amount", "REAL DEFAULT 0"),
        ("retention_amount", "REAL DEFAULT 0"),
        ("claim_period", "TEXT"),
        ("payment_mode", "TEXT"),
        ("utr_number", "TEXT"),
        ("payment_reference", "TEXT"),
        ("status", "TEXT DEFAULT 'Draft'"),
        ("release_remarks", "TEXT"),
        ("extension_remarks", "TEXT"),
        ("remarks", "TEXT"),
        ("released_by", "TEXT"),
        ("approved_by", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("modified_by", "TEXT"),
        ("modified_at", "TEXT"),
    ):
        _ensure_column(db, "security_guarantees", column, col_type)
    db.execute("""
        CREATE TABLE IF NOT EXISTS security_guarantee_attachments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            security_id INTEGER NOT NULL,
            original_filename TEXT,
            stored_filename TEXT NOT NULL,
            file_ext TEXT,
            file_size INTEGER DEFAULT 0,
            uploaded_by TEXT,
            uploaded_at TEXT,
            FOREIGN KEY(security_id) REFERENCES security_guarantees(id)
        )
    """)
    for column, col_type in (
        ("security_id", "INTEGER"),
        ("original_filename", "TEXT"),
        ("stored_filename", "TEXT"),
        ("file_ext", "TEXT"),
        ("file_size", "INTEGER DEFAULT 0"),
        ("uploaded_by", "TEXT"),
        ("uploaded_at", "TEXT"),
    ):
        _ensure_column(db, "security_guarantee_attachments", column, col_type)
    try:
        db.commit()
    except sqlite3.Error:
        pass


def ensure_project_guarantees_table(db):
    """Repeatable bank / performance / treasury / pending-bill rows on project creation."""
    _ensure_column(db, "projects", "completion_months", "REAL")
    _ensure_column(db, "projects", "completion_mode", "TEXT")
    db.execute("""
        CREATE TABLE IF NOT EXISTS project_guarantees(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            sort_order INTEGER DEFAULT 0,
            guarantee_type TEXT NOT NULL,
            amount REAL DEFAULT 0,
            bank_guarantee_number TEXT,
            bank_guarantee_issued_date TEXT,
            bank_guarantee_expiry_date TEXT,
            document_filename TEXT,
            treasury_deposit_number TEXT,
            issued_date TEXT,
            maturity_date TEXT,
            pending_bill_ref TEXT,
            pending_bill_label TEXT,
            pledged_amount REAL DEFAULT 0,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    for column, col_type in (
        ("project_id", "INTEGER"),
        ("sort_order", "INTEGER DEFAULT 0"),
        ("guarantee_type", "TEXT"),
        ("amount", "REAL DEFAULT 0"),
        ("bank_guarantee_number", "TEXT"),
        ("bank_guarantee_issued_date", "TEXT"),
        ("bank_guarantee_expiry_date", "TEXT"),
        ("document_filename", "TEXT"),
        ("treasury_deposit_number", "TEXT"),
        ("issued_date", "TEXT"),
        ("maturity_date", "TEXT"),
        ("pending_bill_ref", "TEXT"),
        ("pending_bill_label", "TEXT"),
        ("pledged_amount", "REAL DEFAULT 0"),
        ("bill_pledging", "INTEGER DEFAULT 0"),
    ):
        _ensure_column(db, "project_guarantees", column, col_type)
    try:
        db.commit()
    except sqlite3.Error:
        pass


def ensure_project_client_bill_submissions_table(db):
    """Track client bill submissions per government project."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS project_client_bill_submissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            sort_order INTEGER DEFAULT 0,
            submitted_date TEXT,
            submitted_amount REAL DEFAULT 0,
            approved_amount REAL DEFAULT 0,
            follow_up_notes TEXT,
            created_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    for column, col_type in (
        ("project_id", "INTEGER"),
        ("sort_order", "INTEGER DEFAULT 0"),
        ("submitted_date", "TEXT"),
        ("submitted_amount", "REAL DEFAULT 0"),
        ("approved_amount", "REAL DEFAULT 0"),
        ("follow_up_notes", "TEXT"),
        ("created_at", "TEXT"),
    ):
        _ensure_column(db, "project_client_bill_submissions", column, col_type)
    try:
        db.commit()
    except sqlite3.Error:
        pass


def _load_project_client_bill_submissions(db, project_id):
    if not project_id or not _table_exists(db, "project_client_bill_submissions"):
        return []
    rows = db.execute(
        "SELECT * FROM project_client_bill_submissions WHERE project_id=? "
        "ORDER BY sort_order, id",
        (project_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _bill_submission_summary(submissions):
    total_submitted = sum(float(r.get("submitted_amount") or 0) for r in submissions)
    total_approved = sum(float(r.get("approved_amount") or 0) for r in submissions)
    pending = max(total_submitted - total_approved, 0.0)
    return {
        "total_submitted": round(total_submitted, 2),
        "total_approved": round(total_approved, 2),
        "pending_amount": round(pending, 2),
        "row_count": len(submissions),
    }


def _parse_client_bill_submissions_from_form():
    dates = request.form.getlist("bill_submission_date[]")
    submitted = request.form.getlist("bill_submission_submitted_amount[]")
    approved = request.form.getlist("bill_submission_approved_amount[]")
    follow_ups = request.form.getlist("bill_submission_follow_up[]")
    row_ids = request.form.getlist("bill_submission_id[]")
    row_count = max(len(dates), len(submitted), len(approved), len(follow_ups))
    rows = []
    for idx in range(row_count):
        submitted_date = (dates[idx] if idx < len(dates) else "").strip()
        try:
            submitted_val = float((submitted[idx] if idx < len(submitted) else "") or 0)
            approved_val = float((approved[idx] if idx < len(approved) else "") or 0)
        except ValueError:
            return None, "Enter valid amounts for client bill submissions."
        follow_up = (follow_ups[idx] if idx < len(follow_ups) else "").strip()
        if not submitted_date and submitted_val <= 0 and approved_val <= 0 and not follow_up:
            continue
        if submitted_val > 0 and not submitted_date:
            return None, "Submitted date is required for each client bill submission row."
        rows.append({
            "id": (row_ids[idx] if idx < len(row_ids) else "").strip() or None,
            "submitted_date": submitted_date,
            "submitted_amount": submitted_val,
            "approved_amount": approved_val,
            "follow_up_notes": follow_up,
            "sort_order": len(rows),
        })
    return rows, None


def _save_project_client_bill_submissions(db, project_id, submission_rows):
    ensure_project_client_bill_submissions_table(db)
    existing = {
        row["id"]: row
        for row in _load_project_client_bill_submissions(db, project_id)
    }
    kept_ids = []
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for row in submission_rows or []:
        row_id = row.get("id")
        if row_id and str(row_id).isdigit() and int(row_id) in existing:
            kept_ids.append(int(row_id))
            db.execute(
                "UPDATE project_client_bill_submissions SET sort_order=?, submitted_date=?, "
                "submitted_amount=?, approved_amount=?, follow_up_notes=? "
                "WHERE id=? AND project_id=?",
                (
                    row["sort_order"],
                    row.get("submitted_date") or "",
                    row.get("submitted_amount") or 0,
                    row.get("approved_amount") or 0,
                    row.get("follow_up_notes") or "",
                    int(row_id),
                    project_id,
                ),
            )
        else:
            db.execute(
                "INSERT INTO project_client_bill_submissions("
                "project_id, sort_order, submitted_date, submitted_amount, "
                "approved_amount, follow_up_notes, created_at"
                ") VALUES(?,?,?,?,?,?,?)",
                (
                    project_id,
                    row["sort_order"],
                    row.get("submitted_date") or "",
                    row.get("submitted_amount") or 0,
                    row.get("approved_amount") or 0,
                    row.get("follow_up_notes") or "",
                    now_ts,
                ),
            )
            kept_ids.append(db.execute("SELECT last_insert_rowid()").fetchone()[0])
    if existing:
        remove_ids = [gid for gid in existing if gid not in kept_ids]
        if remove_ids:
            ph = ",".join("?" * len(remove_ids))
            db.execute(
                f"DELETE FROM project_client_bill_submissions WHERE project_id=? AND id IN ({ph})",
                (project_id, *remove_ids),
            )


def _list_project_pending_bills(db, project_id):
    """Pending client bills and DPR measurements available for guarantee pledging."""
    if not project_id:
        return []
    options = []
    if _table_exists(db, "client_bills"):
        bill_rows = db.execute(
            "SELECT id, bill_number, bill_date, net_payable, paid_amount, bill_status "
            "FROM client_bills WHERE project_id=? "
            "AND COALESCE(net_payable, 0) > COALESCE(paid_amount, 0) "
            "ORDER BY bill_date DESC, id DESC",
            (project_id,),
        ).fetchall()
        for row in bill_rows:
            outstanding = float(row["net_payable"] or 0) - float(row["paid_amount"] or 0)
            label = f"Bill {row['bill_number']} — ₹{outstanding:.2f} outstanding"
            if row["bill_date"]:
                label += f" ({row['bill_date']})"
            options.append({
                "ref": f"bill:{row['id']}",
                "label": label,
                "amount": round(outstanding, 2),
            })
    if _table_exists(db, "dpr_measurements"):
        dpr_rows = db.execute(
            "SELECT m.id, m.report_date, m.boq_description, "
            "ROUND(m.calculated_quantity * COALESCE(bi.rate, 0), 2) AS bill_amount "
            "FROM dpr_measurements m "
            "LEFT JOIN boq_items bi ON m.boq_item_id = bi.id "
            "WHERE m.project_id=? AND m.bill_client=1 AND m.billing_status='pending' "
            "AND COALESCE(m.dpr_status, 'submitted') != 'draft' "
            "ORDER BY m.report_date DESC, m.id DESC",
            (project_id,),
        ).fetchall()
        for row in dpr_rows:
            amount = float(row["bill_amount"] or 0)
            desc = (row["boq_description"] or "Measurement")[:60]
            label = f"DPR #{row['id']} — {desc} — ₹{amount:.2f}"
            if row["report_date"]:
                label += f" ({row['report_date']})"
            options.append({
                "ref": f"dpr:{row['id']}",
                "label": label,
                "amount": round(amount, 2),
            })
    return options


def _load_project_guarantees(db, project_id):
    if not project_id or not _table_exists(db, "project_guarantees"):
        return []
    rows = db.execute(
        "SELECT * FROM project_guarantees WHERE project_id=? ORDER BY sort_order, id",
        (project_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _legacy_project_guarantee_rows(project_row):
    """Map legacy single guarantee columns to row dicts when project_guarantees is empty."""
    if not project_row:
        return []
    project_row = dict(project_row)
    rows = []
    guarantee_type = (project_row.get("guarantee_type") or "").strip()
    if guarantee_type in ("Bank Guarantee", "Both", "Performance Guarantee"):
        gtype = (
            "Bank Guarantee"
            if guarantee_type in ("Bank Guarantee", "Both")
            else "Performance Guarantee"
        )
        rows.append({
            "guarantee_type": gtype,
            "amount": project_row.get("bank_guarantee_amount") or 0,
            "bank_guarantee_number": project_row.get("bank_guarantee_number") or "",
            "bank_guarantee_issued_date": project_row.get("bank_guarantee_issued_date") or "",
            "bank_guarantee_expiry_date": project_row.get("bank_guarantee_expiry_date") or "",
            "document_filename": project_row.get("bank_guarantee_document") or "",
        })
    if project_row.get("treasury_deposit_number") or float(project_row.get("security_deposit_amount") or 0) > 0:
        rows.append({
            "guarantee_type": "Treasury Deposit",
            "amount": project_row.get("security_deposit_amount") or 0,
            "treasury_deposit_number": project_row.get("treasury_deposit_number") or "",
            "issued_date": project_row.get("security_deposit_issued_date") or "",
            "maturity_date": project_row.get("security_deposit_maturity_date") or "",
            "document_filename": project_row.get("security_deposit_document") or "",
        })
    return rows


def _parse_project_guarantees_from_form():
    types = request.form.getlist("guarantee_row_type[]")
    amounts = request.form.getlist("guarantee_row_amount[]")
    bg_numbers = request.form.getlist("guarantee_row_bg_number[]")
    bg_issued = request.form.getlist("guarantee_row_bg_issued[]")
    bg_expiry = request.form.getlist("guarantee_row_bg_expiry[]")
    treasury_numbers = request.form.getlist("guarantee_row_treasury_number[]")
    treasury_issued = request.form.getlist("guarantee_row_treasury_issued[]")
    treasury_maturity = request.form.getlist("guarantee_row_treasury_maturity[]")
    pending_refs = request.form.getlist("guarantee_row_pending_ref[]")
    pledged_amounts = request.form.getlist("guarantee_row_pledged_amount[]")
    bill_pledging_flags = request.form.getlist("guarantee_row_bill_pledging[]")
    existing_docs = request.form.getlist("guarantee_row_existing_doc[]")
    row_ids = request.form.getlist("guarantee_row_id[]")

    rows = []
    row_count = max(
        len(types), len(amounts), len(bg_numbers), len(treasury_numbers), len(pending_refs),
    )
    for idx in range(row_count):
        gtype = (types[idx] if idx < len(types) else "").strip()
        if not gtype:
            continue
        try:
            amount_val = float((amounts[idx] if idx < len(amounts) else "") or 0)
        except ValueError:
            return None, "Enter valid guarantee amounts."
        pending_ref = (pending_refs[idx] if idx < len(pending_refs) else "").strip()
        try:
            pledged_val = float((pledged_amounts[idx] if idx < len(pledged_amounts) else "") or 0)
        except ValueError:
            return None, "Enter valid pledged amounts for bill pledging."
        bill_pledging = (bill_pledging_flags[idx] if idx < len(bill_pledging_flags) else "0").strip() in (
            "1", "true", "yes", "on",
        )
        if bill_pledging and not pending_ref:
            return None, "Select a pending bill when bill pledging is enabled."
        bg_number = (bg_numbers[idx] if idx < len(bg_numbers) else "").strip()
        bg_issue = (bg_issued[idx] if idx < len(bg_issued) else "").strip()
        bg_exp = (bg_expiry[idx] if idx < len(bg_expiry) else "").strip()
        treasury_number = (treasury_numbers[idx] if idx < len(treasury_numbers) else "").strip()
        treasury_issue = (treasury_issued[idx] if idx < len(treasury_issued) else "").strip()
        treasury_exp = (treasury_maturity[idx] if idx < len(treasury_maturity) else "").strip()
        existing_doc = (existing_docs[idx] if idx < len(existing_docs) else "").strip()
        if gtype in ("Bank Guarantee", "Performance Guarantee"):
            if amount_val <= 0 and not bg_number and not bg_issue and not bg_exp and not bill_pledging and not existing_doc:
                continue
        elif gtype == "Treasury Deposit":
            if amount_val <= 0 and not treasury_number and not treasury_issue and not treasury_exp and not existing_doc:
                continue
        rows.append({
            "id": (row_ids[idx] if idx < len(row_ids) else "").strip() or None,
            "guarantee_type": gtype,
            "amount": amount_val,
            "bank_guarantee_number": bg_number,
            "bank_guarantee_issued_date": bg_issue,
            "bank_guarantee_expiry_date": bg_exp,
            "treasury_deposit_number": treasury_number,
            "issued_date": treasury_issue,
            "maturity_date": treasury_exp,
            "pending_bill_ref": pending_ref if bill_pledging else "",
            "pledged_amount": pledged_val or amount_val if bill_pledging else 0,
            "bill_pledging": 1 if bill_pledging else 0,
            "document_filename": existing_doc,
            "sort_order": len(rows),
        })
    return rows, None


def _pending_bill_label(db, pending_ref):
    if not pending_ref or ":" not in pending_ref:
        return ""
    source, raw_id = pending_ref.split(":", 1)
    if not raw_id.isdigit():
        return pending_ref
    if source == "bill" and _table_exists(db, "client_bills"):
        row = db.execute(
            "SELECT bill_number FROM client_bills WHERE id=?", (int(raw_id),),
        ).fetchone()
        return f"Bill {row['bill_number']}" if row else pending_ref
    if source == "dpr" and _table_exists(db, "dpr_measurements"):
        row = db.execute(
            "SELECT id, boq_description FROM dpr_measurements WHERE id=?", (int(raw_id),),
        ).fetchone()
        if row:
            desc = (row["boq_description"] or "Measurement")[:40]
            return f"DPR #{row['id']} — {desc}"
    return pending_ref


def _save_project_guarantees(db, project_id, guarantee_rows, existing_project=None):
    """Replace project guarantee rows and handle per-row document uploads."""
    ensure_project_guarantees_table(db)
    existing_by_id = {}
    if existing_project:
        for row in _load_project_guarantees(db, project_id):
            existing_by_id[row["id"]] = row

    kept_ids = []
    for idx, row in enumerate(guarantee_rows or []):
        doc_key = f"guarantee_row_document_{idx}"
        upload = request.files.get(doc_key)
        if upload and upload.filename:
            upload_error = _validate_project_upload(upload)
            if upload_error:
                return upload_error
            stored = save_file(upload, PROJECT_DOCS_DIR)
            if stored:
                row["document_filename"] = stored
        elif row.get("id") and int(row["id"]) in existing_by_id:
            row["document_filename"] = existing_by_id[int(row["id"])].get("document_filename") or ""

        pending_label = _pending_bill_label(db, row.get("pending_bill_ref") or "")
        row_id = row.get("id")
        if row_id and str(row_id).isdigit() and int(row_id) in existing_by_id:
            kept_ids.append(int(row_id))
            db.execute(
                "UPDATE project_guarantees SET sort_order=?, guarantee_type=?, amount=?, "
                "bank_guarantee_number=?, bank_guarantee_issued_date=?, bank_guarantee_expiry_date=?, "
                "document_filename=?, treasury_deposit_number=?, issued_date=?, maturity_date=?, "
                "pending_bill_ref=?, pending_bill_label=?, pledged_amount=?, bill_pledging=? "
                "WHERE id=? AND project_id=?",
                (
                    row["sort_order"], row["guarantee_type"], row["amount"],
                    row.get("bank_guarantee_number") or "",
                    row.get("bank_guarantee_issued_date") or "",
                    row.get("bank_guarantee_expiry_date") or "",
                    row.get("document_filename") or "",
                    row.get("treasury_deposit_number") or "",
                    row.get("issued_date") or "",
                    row.get("maturity_date") or "",
                    row.get("pending_bill_ref") or "",
                    pending_label,
                    row.get("pledged_amount") or 0,
                    row.get("bill_pledging") or 0,
                    int(row_id), project_id,
                ),
            )
        else:
            db.execute(
                "INSERT INTO project_guarantees("
                "project_id, sort_order, guarantee_type, amount, bank_guarantee_number, "
                "bank_guarantee_issued_date, bank_guarantee_expiry_date, document_filename, "
                "treasury_deposit_number, issued_date, maturity_date, pending_bill_ref, "
                "pending_bill_label, pledged_amount, bill_pledging"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    project_id, row["sort_order"], row["guarantee_type"], row["amount"],
                    row.get("bank_guarantee_number") or "",
                    row.get("bank_guarantee_issued_date") or "",
                    row.get("bank_guarantee_expiry_date") or "",
                    row.get("document_filename") or "",
                    row.get("treasury_deposit_number") or "",
                    row.get("issued_date") or "",
                    row.get("maturity_date") or "",
                    row.get("pending_bill_ref") or "",
                    pending_label,
                    row.get("pledged_amount") or 0,
                    row.get("bill_pledging") or 0,
                ),
            )
            kept_ids.append(db.execute("SELECT last_insert_rowid()").fetchone()[0])

    if existing_by_id:
        placeholders = ",".join("?" * len(existing_by_id)) if existing_by_id else ""
        if placeholders:
            remove_ids = [gid for gid in existing_by_id if gid not in kept_ids]
            if remove_ids:
                ph = ",".join("?" * len(remove_ids))
                db.execute(
                    f"DELETE FROM project_guarantees WHERE project_id=? AND id IN ({ph})",
                    (project_id, *remove_ids),
                )
    return None


def _apply_gov_completion_fields(start_date, end_date, completion_mode, completion_months_raw, gov_completion_date):
    """Resolve government project completion into end_date and stored month/date fields."""
    mode = (completion_mode or "months").strip().lower()
    completion_months_val = None
    completion_time = ""
    if mode == "date":
        resolved_end = (gov_completion_date or end_date or "").strip()
        return resolved_end, completion_time, completion_months_val, "date"
    try:
        months = float(completion_months_raw or 0)
    except ValueError:
        months = 0
    if months > 0:
        completion_months_val = months
        completion_time = str(int(months) if months == int(months) else months)
    resolved_end = (end_date or "").strip()
    if start_date and months > 0 and not resolved_end:
        try:
            start = datetime.strptime(start_date[:10], "%Y-%m-%d")
            month_int = int(months)
            day = start.day
            year = start.year + (start.month - 1 + month_int) // 12
            month = (start.month - 1 + month_int) % 12 + 1
            last_day = monthrange(year, month)[1]
            resolved_end = datetime(year, month, min(day, last_day)).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return resolved_end, completion_time, completion_months_val, "months"


def _security_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generate_security_register_number(db):
    year = datetime.now().strftime("%Y")
    prefix = f"SG-{year}-"
    rows = db.execute(
        "SELECT register_number FROM security_guarantees WHERE register_number LIKE ?",
        (prefix + "%",),
    ).fetchall()
    max_seq = 0
    for row in rows:
        raw = str(row["register_number"] or "")
        suffix = raw.split("-")[-1]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:04d}"


def _save_security_attachment(db, record_id, file_storage, username):
    """Persist an uploaded security document if a file was provided."""
    ext, size, err = _validate_securities_upload(file_storage)
    if err:
        return err
    stored = save_file(file_storage, SECURITIES_DOCS_DIR)
    if not stored:
        return "Unable to save uploaded file."
    db.execute(
        "INSERT INTO security_guarantee_attachments("
        "security_id, original_filename, stored_filename, file_ext, file_size, uploaded_by, uploaded_at"
        ") VALUES(?,?,?,?,?,?,?)",
        (
            record_id,
            file_storage.filename,
            stored,
            ext,
            size,
            username,
            _security_timestamp(),
        ),
    )
    return None


def _validate_securities_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None, None, "Select a file to upload."
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in SECURITIES_ALLOWED_EXTENSIONS:
        return None, None, "Allowed file types: PDF, JPG, PNG, DOC, DOCX."
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_SECURITIES_UPLOAD_BYTES:
        return None, None, "File is too large (maximum 10 MB)."
    return ext, size, None


def _security_record_sql():
    return (
        "SELECT s.*, p.project_name AS live_project_name, p.project_code AS live_project_code "
        "FROM security_guarantees s "
        "LEFT JOIN projects p ON s.project_id = p.id "
    )


def _load_security_record(db, record_id):
    return db.execute(
        _security_record_sql() + "WHERE s.id=?",
        (record_id,),
    ).fetchone()


def _project_client_name(project_row):
    if not project_row:
        return ""
    if project_row.get("project_type") == "Government":
        return project_row.get("gov_department") or ""
    return (
        project_row.get("private_client_name")
        or project_row.get("company_name")
        or project_row.get("client_name")
        or ""
    )


def _project_contract_value(project_row):
    if not project_row:
        return 0.0
    for key in ("approved_total_amount", "quoted_amount", "work_order_amount", "budget"):
        val = project_row.get(key)
        if val is not None and float(val or 0) > 0:
            return float(val)
    return 0.0


def _load_project_security_snapshot(db, project_id):
    if not project_id:
        return {}
    row = db.execute(
        "SELECT p.*, c.client_name, c.company_name FROM projects p "
        "LEFT JOIN clients c ON p.client_id = c.id WHERE p.id=?",
        (project_id,),
    ).fetchone()
    if not row:
        return {}
    row = dict(row)
    return {
        "project_id": row["id"],
        "project_name": row.get("project_name") or "",
        "project_code": row.get("project_code") or str(row["id"]),
        "client_name": _project_client_name(row),
        "agreement_number": row.get("agreement_number") or "",
        "agreement_date": row.get("agreement_date") or "",
        "work_order_number": row.get("work_order_number") or "",
        "contract_value": _project_contract_value(row),
    }


def _calculate_security_interest(principal, rate, start_date, end_date):
    if not principal or not rate or not start_date or not end_date:
        return 0.0
    try:
        start = datetime.strptime(str(start_date)[:10], "%Y-%m-%d")
        end = datetime.strptime(str(end_date)[:10], "%Y-%m-%d")
        days = max((end - start).days, 0)
        return round(float(principal) * float(rate) / 100.0 * days / 365.0, 2)
    except (ValueError, TypeError):
        return 0.0


def _security_effective_end_date(record):
    rec = dict(record) if not isinstance(record, dict) else record
    return (
        rec.get("maturity_date")
        or rec.get("expiry_date")
        or rec.get("extension_date")
        or ""
    )


def _security_days_until_expiry(record, today=None):
    end_date = _security_effective_end_date(record)
    if not end_date:
        return None
    if today is None:
        today = datetime.now().date()
    try:
        end = datetime.strptime(str(end_date)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    return (end - today).days


def _security_expiry_bucket(days):
    if days is None:
        return None
    if days < 0:
        return "overdue"
    for threshold in SECURITY_EXPIRY_ALERT_DAYS:
        if days <= threshold:
            return str(threshold)
    return None


def _parse_security_form():
    def _f(name, default=""):
        return request.form.get(name, default).strip()

    def _float(name, default=0.0):
        try:
            return float(request.form.get(name, default) or 0)
        except ValueError:
            return default

    security_type = _f("security_type")
    project_id = _f("project_id") or None
    deposit_amount = _float("deposit_amount")
    interest_rate = _float("interest_rate")
    issue_date = _f("issue_date") or _f("deposit_date")
    maturity_date = _f("maturity_date") or _f("expiry_date")
    interest_amount = _float("interest_amount")
    if security_type in ("Treasury Deposit", "Security Deposit") and interest_rate and not interest_amount:
        interest_amount = _calculate_security_interest(
            deposit_amount, interest_rate, issue_date, maturity_date,
        )
    total_recoverable = _float("total_recoverable")
    if security_type in ("Treasury Deposit", "Security Deposit") and not total_recoverable:
        total_recoverable = round(deposit_amount + interest_amount, 2)
    retention_percent = _float("retention_percent")
    bill_amount = _float("bill_amount")
    retention_amount = _float("retention_amount")
    if security_type == "Pending Bill Retention" and not retention_amount and bill_amount and retention_percent:
        retention_amount = round(bill_amount * retention_percent / 100.0, 2)
    if security_type == "Pending Bill Retention" and not deposit_amount:
        deposit_amount = retention_amount
    return {
        "security_type": security_type,
        "project_id": int(project_id) if project_id else None,
        "project_name": _f("project_name"),
        "project_code": _f("project_code"),
        "client_name": _f("client_name"),
        "agreement_number": _f("agreement_number"),
        "agreement_date": _f("agreement_date"),
        "work_order_number": _f("work_order_number"),
        "contract_value": _float("contract_value"),
        "deposit_amount": deposit_amount,
        "bank_name": _f("bank_name"),
        "branch_name": _f("branch_name"),
        "account_number": _f("account_number"),
        "instrument_number": _f("instrument_number"),
        "challan_number": _f("challan_number"),
        "bg_number": _f("bg_number"),
        "beneficiary_name": _f("beneficiary_name"),
        "issuing_bank": _f("issuing_bank"),
        "deposit_date": _f("deposit_date"),
        "issue_date": _f("issue_date"),
        "expiry_date": _f("expiry_date"),
        "maturity_date": _f("maturity_date"),
        "release_date": _f("release_date"),
        "extension_date": _f("extension_date"),
        "interest_rate": interest_rate,
        "interest_amount": interest_amount,
        "total_recoverable": total_recoverable,
        "tender_number": _f("tender_number"),
        "tender_date": _f("tender_date"),
        "tender_authority": _f("tender_authority"),
        "emd_mode": _f("emd_mode"),
        "bill_number": _f("bill_number"),
        "bill_date": _f("bill_date"),
        "retention_percent": retention_percent,
        "bill_amount": bill_amount,
        "retention_amount": retention_amount,
        "claim_period": _f("claim_period"),
        "status": _f("status", "Draft"),
        "release_remarks": _f("release_remarks"),
        "extension_remarks": _f("extension_remarks"),
        "remarks": _f("remarks"),
        "released_by": _f("released_by"),
        "approved_by": _f("approved_by"),
    }


def _security_can_edit(record):
    if not record:
        return False
    rec = dict(record)
    return rec.get("status") in ("Draft", "Active", "Expiring Soon", "Maturity Pending", "Release Requested")


def _security_dashboard_stats(db):
    today = datetime.now().date()
    rows = db.execute("SELECT * FROM security_guarantees").fetchall()
    outstanding_statuses = {
        "Active", "Expiring Soon", "Maturity Pending", "Release Requested", "Extended",
    }
    released_statuses = {"Released", "Refunded", "Matured", "Closed"}
    stats = {
        "total_records": len(rows),
        "total_outstanding": 0.0,
        "total_released": 0.0,
        "by_type": {t: 0 for t in SECURITY_TYPES},
        "expiring": {str(d): [] for d in SECURITY_EXPIRY_ALERT_DAYS},
        "expiring_overdue": [],
    }
    for row in rows:
        rec = dict(row)
        st = rec.get("status") or "Draft"
        amt = float(rec.get("deposit_amount") or 0)
        sec_type = rec.get("security_type") or ""
        if sec_type in stats["by_type"]:
            stats["by_type"][sec_type] += 1
        if st in outstanding_statuses:
            stats["total_outstanding"] += amt
        if st in released_statuses:
            stats["total_released"] += amt
        if st in outstanding_statuses:
            days = _security_days_until_expiry(rec, today)
            bucket = _security_expiry_bucket(days)
            if bucket == "overdue":
                stats["expiring_overdue"].append(rec)
            elif bucket:
                stats["expiring"][bucket].append(rec)
    return stats


def _stub_security_expiry_notifications(db):
    """Optional email alerts stub — logs expiring records only."""
    stats = _security_dashboard_stats(db)
    for bucket, records in stats["expiring"].items():
        for rec in records:
            print(
                f"[SECURITY ALERT STUB] {rec.get('register_number')} expires within {bucket} days",
            )


def _petty_cash_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generate_petty_cash_request_number(db):
    year = datetime.now().strftime("%Y")
    prefix = f"PCR-{year}-"
    rows = db.execute(
        "SELECT request_number FROM petty_cash_requests WHERE request_number LIKE ?",
        (prefix + "%",),
    ).fetchall()
    max_seq = 0
    for row in rows:
        raw = str(row["request_number"] or "")
        suffix = raw.split("-")[-1]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:04d}"


def _validate_petty_cash_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None, None, "Select a file to upload."
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in PETTY_CASH_ALLOWED_EXTENSIONS:
        return None, None, "Allowed file types: PDF, JPG, PNG, DOC, XLS."
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_PETTY_CASH_UPLOAD_BYTES:
        return None, None, "File is too large (maximum 10 MB)."
    return ext, size, None


def _petty_cash_request_sql():
    return (
        "SELECT r.*, p.project_name, p.project_code "
        "FROM petty_cash_requests r "
        "LEFT JOIN projects p ON r.project_id = p.id "
    )


def _load_petty_cash_request(db, request_id):
    row = db.execute(
        _petty_cash_request_sql() + "WHERE r.id=?",
        (request_id,),
    ).fetchone()
    return dict(row) if row else None


def _refresh_petty_cash_expense_total(db, request_id):
    total = db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM petty_cash_expenses WHERE request_id=?",
        (request_id,),
    ).fetchone()["total"]
    db.execute(
        "UPDATE petty_cash_requests SET expenses_total=?, modified_at=? WHERE id=?",
        (float(total or 0), _petty_cash_timestamp(), request_id),
    )
    return float(total or 0)


def _petty_cash_available_balance(request_row):
    transferred = float(request_row.get("transferred_amount") or 0)
    expenses = float(request_row.get("expenses_total") or 0)
    return max(transferred - expenses, 0.0)


def _petty_cash_dashboard_summary(db):
    """Aggregate petty cash KPIs for list dashboard cards."""
    ensure_petty_cash_tables(db)
    row = db.execute(
        """
        SELECT
            COALESCE(SUM(
                CASE WHEN status = 'Closed'
                  AND COALESCE(transferred_amount, 0) > COALESCE(expenses_total, 0)
                THEN COALESCE(transferred_amount, 0) - COALESCE(expenses_total, 0)
                ELSE 0 END
            ), 0) AS opening_balance,
            COALESCE(SUM(
                CASE WHEN status IN (
                    'Funds Transferred', 'Amount Received',
                    'Settlement Pending', 'Settled', 'Closed'
                ) THEN COALESCE(transferred_amount, 0) ELSE 0 END
            ), 0) AS amount_received,
            COALESCE(SUM(COALESCE(expenses_total, 0)), 0) AS total_expenses,
            COALESCE(SUM(
                CASE WHEN status NOT IN ('Draft', 'Rejected', 'Closed')
                  AND COALESCE(transferred_amount, 0) > COALESCE(expenses_total, 0)
                THEN COALESCE(transferred_amount, 0) - COALESCE(expenses_total, 0)
                ELSE 0 END
            ), 0) AS current_balance,
            COALESCE(SUM(CASE WHEN status = 'Settlement Pending' THEN 1 ELSE 0 END), 0)
                AS pending_settlement,
            COALESCE(SUM(
                CASE WHEN status IN ('Approved', 'Submitted')
                  OR approval_status IN ('Pending Checker', 'Pending Approval')
                THEN 1 ELSE 0 END
            ), 0) AS approved_requests
        FROM petty_cash_requests
        """
    ).fetchone()
    if not row:
        return {
            "opening_balance": 0.0,
            "amount_received": 0.0,
            "total_expenses": 0.0,
            "current_balance": 0.0,
            "pending_settlement": 0,
            "approved_requests": 0,
        }
    return {
        "opening_balance": float(row["opening_balance"] or 0),
        "amount_received": float(row["amount_received"] or 0),
        "total_expenses": float(row["total_expenses"] or 0),
        "current_balance": float(row["current_balance"] or 0),
        "pending_settlement": int(row["pending_settlement"] or 0),
        "approved_requests": int(row["approved_requests"] or 0),
    }


PETTY_CASH_WORKFLOW_STEPS = (
    "Request",
    "Approval",
    "Fund Transfer",
    "Amount Received",
    "Expenses",
    "Settlement",
    "Closed",
)


def _petty_cash_workflow_index(status):
    """Map request status to workflow progress step index."""
    mapping = {
        "Draft": 0,
        "Submitted": 0,
        "Rejected": 0,
        "Approved": 1,
        "Funds Transferred": 2,
        "Amount Received": 3,
        "Settlement Pending": 5,
        "Settled": 5,
        "Closed": 6,
    }
    return mapping.get(status or "Draft", 0)


def _petty_cash_can_edit_request(request_row):
    status = request_row.get("status") or "Draft"
    approval = request_row.get("approval_status") or "Draft"
    if status == "Draft":
        return True
    if status == "Rejected":
        return True
    if status == "Submitted" and approval in (
        RECORD_PENDING_CHECKER,
        RECORD_REJECTED_CHECKER,
        RECORD_REJECTED_APPROVER,
    ):
        return True
    return False


def _petty_cash_can_delete_request(request_row):
    status = request_row.get("status") or "Draft"
    approval = request_row.get("approval_status") or "Draft"
    if status == "Draft":
        return True
    if status == "Rejected":
        return True
    if status == "Submitted" and approval == RECORD_PENDING_CHECKER:
        return True
    return False


def _parse_petty_cash_request_form():
    return {
        "request_date": request.form.get("request_date", "").strip(),
        "project_id": request.form.get("project_id") or None,
        "staff_id": request.form.get("staff_id") or None,
        "staff_name": request.form.get("staff_name", "").strip(),
        "employee_code": request.form.get("employee_code", "").strip(),
        "department": request.form.get("department", "").strip(),
        "purpose": request.form.get("purpose", "").strip(),
        "description": request.form.get("description", "").strip(),
        "required_amount": request.form.get("required_amount", "0").strip(),
        "priority": request.form.get("priority", "Normal").strip() or "Normal",
        "remarks": request.form.get("remarks", "").strip(),
    }


def prepare_dpr_page_db(db):
    """Ensure DPR tables and related columns exist before rendering DPR pages."""
    ensure_dpr_measurement_tables(db)
    ensure_equipment_master_table(db)
    ensure_dpr_attachments_table(db)
    _ensure_column(db, "subcontractors", "subcontractor_code", "TEXT")
    _ensure_column(db, "projects", "project_code", "TEXT")
    _ensure_column(db, "boq_items", "boq_id", "INTEGER")
    _ensure_column(db, "boq_items", "project_id", "INTEGER")
    if _table_exists(db, "project_expenses"):
        _ensure_column(db, "project_expenses", "dpr_measurement_id", "INTEGER")
    db.commit()


def prepare_workers_page_db(db):
    """Ensure worker and subcontractor rate schema before worker pages."""
    ensure_subcontractor_rate_tables(db)
    worker_columns = (
        ("worker_code", "TEXT"),
        ("aadhaar_number", "TEXT"),
        ("worker_category", "TEXT DEFAULT 'Company Staff'"),
        ("subcontractor_id", "INTEGER"),
        ("bank_account", "TEXT"),
        ("bank_name", "TEXT"),
        ("ifsc_code", "TEXT"),
        ("branch_name", "TEXT"),
        ("pan_number", "TEXT"),
        ("id_proof", "TEXT"),
        ("aadhaar_document", "TEXT"),
        ("pan_document", "TEXT"),
        ("photo", "TEXT"),
        ("mobile", "TEXT"),
        ("designation", "TEXT"),
        ("salary_type", "TEXT"),
        ("salary_amount", "REAL"),
        ("ot_applicable", "TEXT"),
        ("working_hours", "REAL"),
        ("joining_date", "TEXT"),
        ("status", "TEXT"),
        ("date_of_birth", "TEXT"),
        ("gender", "TEXT"),
    )
    for column, col_type in worker_columns:
        _ensure_column(db, "workers", column, col_type)
    db.commit()


def prepare_head_office_expenses_db(db):
    """Ensure daily expense schema includes chart account head."""
    _prepare_accounts_db(db)
    _ensure_column(db, "head_office_expenses", "chart_account_id", "INTEGER")
    db.commit()


STAFF_SALARY_COMPONENT_OPTIONS = [
    "Basic Salary",
    "Room Rent",
    "Travel Expense",
    "Telephone",
    "HRA",
    "DA",
    "Special Allowance",
    "Medical Allowance",
    "Food Allowance",
    "Other",
]


def ensure_staff_hr_tables(db):
    """Salary split-up, increments, travel tiers, company provision flags."""
    _ensure_column(db, "staff", "company_room_provided", "TEXT DEFAULT 'No'")
    _ensure_column(db, "staff", "company_food_provided", "TEXT DEFAULT 'No'")
    db.execute("""
        CREATE TABLE IF NOT EXISTS staff_salary_components(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            component_name TEXT NOT NULL,
            amount REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY(staff_id) REFERENCES staff(id) ON DELETE CASCADE
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS staff_salary_increments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            effective_date TEXT,
            previous_amount REAL DEFAULT 0,
            new_amount REAL DEFAULT 0,
            increment_amount REAL DEFAULT 0,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            FOREIGN KEY(staff_id) REFERENCES staff(id) ON DELETE CASCADE
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS staff_travel_tiers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            continuous_months INTEGER NOT NULL,
            travel_mode TEXT NOT NULL,
            allowance_amount REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY(staff_id) REFERENCES staff(id) ON DELETE CASCADE
        )
    """)
    db.commit()


def ensure_payroll_tables(db):
    """Payroll runs, lines, revisions, holidays, payments."""
    staff_columns = (
        ("employee_code", "TEXT"),
        ("department", "TEXT"),
        ("designation", "TEXT"),
        ("designation_id", "INTEGER"),
        ("salary_type", "TEXT"),
        ("salary_amount", "REAL"),
        ("ot_applicable", "TEXT"),
        ("ot_rate_per_hour", "REAL DEFAULT 0"),
        ("holiday_pay_applicable", "TEXT DEFAULT 'No'"),
        ("working_hours", "REAL"),
        ("status", "TEXT"),
        ("bank_account", "TEXT"),
        ("bank_name", "TEXT"),
        ("ifsc_code", "TEXT"),
        ("branch_name", "TEXT"),
    )
    for column, col_type in staff_columns:
        _ensure_column(db, "staff", column, col_type)

    worker_columns = (
        ("worker_code", "TEXT"),
        ("salary_type", "TEXT"),
        ("salary_amount", "REAL"),
        ("ot_applicable", "TEXT"),
        ("ot_rate_per_hour", "REAL DEFAULT 0"),
        ("holiday_pay_applicable", "TEXT DEFAULT 'No'"),
        ("working_hours", "REAL"),
        ("worker_category", "TEXT DEFAULT 'Company Staff'"),
        ("project_id", "INTEGER"),
        ("department", "TEXT"),
        ("status", "TEXT"),
        ("bank_account", "TEXT"),
        ("bank_name", "TEXT"),
        ("ifsc_code", "TEXT"),
        ("branch_name", "TEXT"),
    )
    for column, col_type in worker_columns:
        _ensure_column(db, "workers", column, col_type)

    _ensure_column(db, "attendance", "worker_source", "TEXT DEFAULT 'worker'")
    _ensure_column(db, "attendance", "approval_status", "TEXT DEFAULT 'Pending Checker'")
    _ensure_column(db, "attendance", "trade_id", "INTEGER")
    _ensure_column(db, "attendance", "designation_id", "INTEGER")
    db.execute("""
        CREATE TABLE IF NOT EXISTS salary_revisions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_type TEXT NOT NULL,
            staff_id INTEGER,
            worker_id INTEGER,
            previous_amount REAL DEFAULT 0,
            revised_amount REAL DEFAULT 0,
            increment_amount REAL DEFAULT 0,
            effective_date TEXT,
            reason TEXT,
            approved_by TEXT,
            created_by TEXT,
            created_at TEXT,
            FOREIGN KEY(staff_id) REFERENCES staff(id),
            FOREIGN KEY(worker_id) REFERENCES workers(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS holidays(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            holiday_date TEXT NOT NULL,
            holiday_name TEXT NOT NULL,
            holiday_type TEXT DEFAULT 'Public',
            created_by TEXT,
            created_at TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS holiday_applicability(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            holiday_id INTEGER NOT NULL,
            applies_to TEXT NOT NULL,
            FOREIGN KEY(holiday_id) REFERENCES holidays(id) ON DELETE CASCADE
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS payroll_runs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_ref TEXT,
            run_type TEXT DEFAULT 'monthly',
            period_start TEXT,
            period_end TEXT,
            month INTEGER,
            year INTEGER,
            project_id INTEGER,
            department TEXT,
            employee_type TEXT,
            status TEXT DEFAULT 'Draft',
            approval_status TEXT DEFAULT 'Draft',
            verification_status TEXT DEFAULT 'Pending',
            locked INTEGER DEFAULT 0,
            total_gross REAL DEFAULT 0,
            total_deductions REAL DEFAULT 0,
            total_net REAL DEFAULT 0,
            employee_count INTEGER DEFAULT 0,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            modified_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS payroll_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payroll_run_id INTEGER NOT NULL,
            employee_type TEXT NOT NULL,
            staff_id INTEGER,
            worker_id INTEGER,
            employee_code TEXT,
            employee_name TEXT,
            department TEXT,
            project_id INTEGER,
            salary_type TEXT,
            base_salary REAL DEFAULT 0,
            working_days REAL DEFAULT 0,
            present_days REAL DEFAULT 0,
            leave_days REAL DEFAULT 0,
            ot_hours REAL DEFAULT 0,
            ot_amount REAL DEFAULT 0,
            holiday_pay REAL DEFAULT 0,
            gross_salary REAL DEFAULT 0,
            deductions REAL DEFAULT 0,
            advance_deduction REAL DEFAULT 0,
            net_salary REAL DEFAULT 0,
            verification_status TEXT DEFAULT 'Pending',
            approval_status TEXT DEFAULT 'Draft',
            payment_status TEXT DEFAULT 'Pending',
            locked INTEGER DEFAULT 0,
            calc_snapshot TEXT,
            remarks TEXT,
            FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs(id) ON DELETE CASCADE,
            FOREIGN KEY(staff_id) REFERENCES staff(id),
            FOREIGN KEY(worker_id) REFERENCES workers(id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS salary_payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payroll_run_id INTEGER,
            payroll_line_id INTEGER,
            payment_date TEXT,
            payment_mode TEXT,
            bank_name TEXT,
            utr_ref TEXT,
            gross_amount REAL DEFAULT 0,
            deductions REAL DEFAULT 0,
            net_amount REAL DEFAULT 0,
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs(id),
            FOREIGN KEY(payroll_line_id) REFERENCES payroll_lines(id)
        )
    """)
    for table, columns in (
        (
            "payroll_runs",
            (
                ("run_ref", "TEXT"),
                ("run_type", "TEXT DEFAULT 'monthly'"),
                ("period_start", "TEXT"),
                ("period_end", "TEXT"),
                ("month", "INTEGER"),
                ("year", "INTEGER"),
                ("project_id", "INTEGER"),
                ("department", "TEXT"),
                ("employee_type", "TEXT"),
                ("status", "TEXT DEFAULT 'Draft'"),
                ("approval_status", "TEXT DEFAULT 'Draft'"),
                ("verification_status", "TEXT DEFAULT 'Pending'"),
                ("locked", "INTEGER DEFAULT 0"),
                ("total_gross", "REAL DEFAULT 0"),
                ("total_deductions", "REAL DEFAULT 0"),
                ("total_net", "REAL DEFAULT 0"),
                ("employee_count", "INTEGER DEFAULT 0"),
                ("remarks", "TEXT"),
                ("created_by", "TEXT"),
                ("created_at", "TEXT"),
                ("modified_at", "TEXT"),
                ("draft_saved", "INTEGER DEFAULT 0"),
            ),
        ),
        (
            "payroll_lines",
            (
                ("employee_code", "TEXT"),
                ("employee_name", "TEXT"),
                ("department", "TEXT"),
                ("project_id", "INTEGER"),
                ("salary_type", "TEXT"),
                ("base_salary", "REAL DEFAULT 0"),
                ("working_days", "REAL DEFAULT 0"),
                ("present_days", "REAL DEFAULT 0"),
                ("leave_days", "REAL DEFAULT 0"),
                ("ot_hours", "REAL DEFAULT 0"),
                ("ot_amount", "REAL DEFAULT 0"),
                ("holiday_pay", "REAL DEFAULT 0"),
                ("gross_salary", "REAL DEFAULT 0"),
                ("deductions", "REAL DEFAULT 0"),
                ("advance_deduction", "REAL DEFAULT 0"),
                ("net_salary", "REAL DEFAULT 0"),
                ("verification_status", "TEXT DEFAULT 'Pending'"),
                ("approval_status", "TEXT DEFAULT 'Draft'"),
                ("payment_status", "TEXT DEFAULT 'Pending'"),
                ("locked", "INTEGER DEFAULT 0"),
                ("calc_snapshot", "TEXT"),
                ("remarks", "TEXT"),
            ),
        ),
    ):
        for column, col_type in columns:
            _ensure_column(db, table, column, col_type)
    staff_cols = {
        row[1] for row in db.execute("PRAGMA table_info(staff)").fetchall()
    } if _table_exists(db, "staff") else set()
    if "staff_name" in staff_cols and "employee_code" in staff_cols:
        db.execute(
            "UPDATE payroll_lines SET employee_name = ("
            "SELECT staff_name FROM staff WHERE staff.id = payroll_lines.staff_id"
            "), employee_code = ("
            "SELECT employee_code FROM staff WHERE staff.id = payroll_lines.staff_id"
            ") WHERE staff_id IS NOT NULL AND ("
            "employee_name IS NULL OR TRIM(employee_name) = '' OR "
            "employee_code IS NULL OR TRIM(employee_code) = ''"
            ")"
        )
    worker_cols = {
        row[1] for row in db.execute("PRAGMA table_info(workers)").fetchall()
    } if _table_exists(db, "workers") else set()
    if "worker_name" in worker_cols and "worker_code" in worker_cols:
        db.execute(
            "UPDATE payroll_lines SET employee_name = ("
            "SELECT worker_name FROM workers WHERE workers.id = payroll_lines.worker_id"
            "), employee_code = ("
            "SELECT worker_code FROM workers WHERE workers.id = payroll_lines.worker_id"
            ") WHERE worker_id IS NOT NULL AND ("
            "employee_name IS NULL OR TRIM(employee_name) = '' OR "
            "employee_code IS NULL OR TRIM(employee_code) = ''"
            ")"
        )
    db.commit()


APP_TIMEZONE_OPTIONS = [
    ("Asia/Kolkata", "India — IST (Asia/Kolkata)"),
    ("Asia/Colombo", "Sri Lanka — SLST (Asia/Colombo)"),
    ("Asia/Kathmandu", "Nepal — NPT (Asia/Kathmandu)"),
    ("Asia/Dhaka", "Bangladesh — BST (Asia/Dhaka)"),
    ("Asia/Karachi", "Pakistan — PKT (Asia/Karachi)"),
    ("Asia/Dubai", "UAE — GST (Asia/Dubai)"),
    ("Asia/Riyadh", "Saudi Arabia — AST (Asia/Riyadh)"),
    ("Asia/Qatar", "Qatar — AST (Asia/Qatar)"),
    ("Asia/Singapore", "Singapore — SGT (Asia/Singapore)"),
    ("Asia/Kuala_Lumpur", "Malaysia — MYT (Asia/Kuala_Lumpur)"),
    ("Asia/Bangkok", "Thailand — ICT (Asia/Bangkok)"),
    ("Asia/Jakarta", "Indonesia — WIB (Asia/Jakarta)"),
    ("Asia/Manila", "Philippines — PHT (Asia/Manila)"),
    ("Asia/Hong_Kong", "Hong Kong — HKT (Asia/Hong_Kong)"),
    ("Asia/Shanghai", "China — CST (Asia/Shanghai)"),
    ("Asia/Tokyo", "Japan — JST (Asia/Tokyo)"),
    ("Asia/Seoul", "South Korea — KST (Asia/Seoul)"),
    ("Australia/Sydney", "Australia — AEST (Australia/Sydney)"),
    ("Europe/London", "United Kingdom — GMT/BST (Europe/London)"),
    ("Europe/Paris", "France — CET (Europe/Paris)"),
    ("Europe/Berlin", "Germany — CET (Europe/Berlin)"),
    ("America/New_York", "United States — Eastern (America/New_York)"),
    ("America/Chicago", "United States — Central (America/Chicago)"),
    ("America/Los_Angeles", "United States — Pacific (America/Los_Angeles)"),
    ("UTC", "UTC"),
]


def ensure_app_settings_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS app_settings(
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT
        )
    """)
    row = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key=?",
        ("timezone",),
    ).fetchone()
    if not row:
        db.execute(
            "INSERT INTO app_settings(setting_key, setting_value) VALUES(?,?)",
            ("timezone", "Asia/Kolkata"),
        )
    db.commit()


def get_app_setting(db, key, default=None):
    ensure_app_settings_table(db)
    row = db.execute(
        "SELECT setting_value FROM app_settings WHERE setting_key=?",
        (key,),
    ).fetchone()
    if not row or row["setting_value"] is None:
        return default
    return row["setting_value"]


def set_app_setting(db, key, value):
    ensure_app_settings_table(db)
    db.execute(
        "INSERT INTO app_settings(setting_key, setting_value) VALUES(?,?) "
        "ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value",
        (key, value),
    )
    db.commit()


DEFAULT_DASHBOARD_DISPLAY = {
    "hero": True,
    "context_bar": True,
    "kpis": True,
    "charts": True,
    "approval_summary": True,
    "activities": True,
    "notifications": True,
    "approval_center": True,
    "workflow_queue": False,
}


def get_dashboard_display_settings(db=None):
    if db is None:
        db = get_db()
    raw = get_app_setting(db, "dashboard_display")
    if not raw:
        return dict(DEFAULT_DASHBOARD_DISPLAY)
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return dict(DEFAULT_DASHBOARD_DISPLAY)
    if not isinstance(parsed, dict):
        return dict(DEFAULT_DASHBOARD_DISPLAY)
    merged = dict(DEFAULT_DASHBOARD_DISPLAY)
    for key in DEFAULT_DASHBOARD_DISPLAY:
        if key in parsed:
            merged[key] = bool(parsed[key])
    return merged


def set_dashboard_display_settings(db, settings):
    normalized = dict(DEFAULT_DASHBOARD_DISPLAY)
    for key in DEFAULT_DASHBOARD_DISPLAY:
        if key in settings:
            normalized[key] = bool(settings[key])
    set_app_setting(db, "dashboard_display", json.dumps(normalized))
    return normalized


def get_app_timezone(db=None):
    if db is None:
        db = get_db()
    tz_name = get_app_setting(db, "timezone", "Asia/Kolkata")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def get_app_now(db=None):
    return datetime.now(get_app_timezone(db))


def format_app_datetime(dt=None, fmt="%A, %d %b %Y | %H:%M", db=None):
    if dt is None:
        dt = get_app_now(db)
    elif isinstance(dt, str):
        text = dt.strip()
        if not text:
            return "—"
        parsed = None
        for parse_fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, parse_fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            return text
        dt = parsed.replace(tzinfo=get_app_timezone(db))
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_app_timezone(db))
    else:
        dt = dt.astimezone(get_app_timezone(db))
    return dt.strftime(fmt)


@app.template_filter("app_datetime")
def app_datetime_filter(value, fmt="%d %b %Y %H:%M"):
    if value is None or value == "":
        return "—"
    return format_app_datetime(value, fmt=fmt)


def ensure_staff_bonus_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS staff_bonus(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            bonus_period TEXT NOT NULL,
            worked_days REAL DEFAULT 0,
            leave_days REAL DEFAULT 0,
            held_ot_hours REAL DEFAULT 0,
            method TEXT NOT NULL,
            per_day_rate REAL DEFAULT 0,
            calculated_amount REAL DEFAULT 0,
            rounded_amount REAL DEFAULT 0,
            final_amount REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'pending',
            remarks TEXT,
            created_by TEXT,
            created_at TEXT,
            paid_at TEXT,
            FOREIGN KEY(staff_id) REFERENCES staff(id) ON DELETE CASCADE,
            UNIQUE(staff_id, bonus_period)
        )
    """)
    db.commit()


def _bonus_period_bounds(year, month):
    period = f"{year:04d}-{month:02d}"
    last_day = monthrange(year, month)[1]
    period_start = f"{year:04d}-{month:02d}-01"
    period_end = f"{year:04d}-{month:02d}-{last_day:02d}"
    return period, period_start, period_end


def compute_staff_bonus_attendance_stats(db, staff_id, year, month):
    """Worked/leave days in period; cumulative held OT through month end."""
    _, period_start, period_end = _bonus_period_bounds(year, month)
    year_month = f"{year:04d}-{month:02d}"
    monthly_row = db.execute(
        "SELECT worked_days, half_days, absent_days, ot_hours, approval_status "
        "FROM staff_monthly_attendance WHERE staff_id=? AND year_month=?",
        (staff_id, year_month),
    ).fetchone()
    if monthly_row and (monthly_row["approval_status"] or "") not in (
        "Rejected by Checker",
        "Rejected by Approver",
    ):
        worked_days = float(monthly_row["worked_days"] or 0) + float(monthly_row["half_days"] or 0) * 0.5
        leave_days = float(monthly_row["absent_days"] or 0)
        held_ot_hours = float(monthly_row["ot_hours"] or 0)
    else:
        rows = db.execute(
            "SELECT status, ot_hours FROM attendance "
            "WHERE worker_id=? AND COALESCE(worker_source, 'worker')='staff' "
            "AND attendance_date BETWEEN ? AND ?",
            (staff_id, period_start, period_end),
        ).fetchall()
        worked_days = 0.0
        leave_days = 0.0
        for row in rows:
            status = (row["status"] or "Present").strip()
            if status == "Present":
                worked_days += 1.0
            elif status == "Half Day":
                worked_days += 0.5
                leave_days += 0.5
            elif status == "Absent":
                leave_days += 1.0
        ot_row = db.execute(
            "SELECT COALESCE(SUM(ot_hours), 0) AS total_ot FROM attendance "
            "WHERE worker_id=? AND COALESCE(worker_source, 'worker')='staff' "
            "AND attendance_date <= ?",
            (staff_id, period_end),
        ).fetchone()
        held_ot_hours = float(ot_row["total_ot"] or 0) if ot_row else 0.0
    staff_row = db.execute(
        "SELECT salary_type, salary_amount FROM staff WHERE id=?",
        (staff_id,),
    ).fetchone()
    suggested_per_day = 0.0
    if staff_row:
        salary_amount = float(staff_row["salary_amount"] or 0)
        salary_type = (staff_row["salary_type"] or "Monthly").strip()
        days_in_month = monthrange(year, month)[1]
        if salary_type == "Daily":
            suggested_per_day = salary_amount
        elif days_in_month > 0:
            suggested_per_day = round(salary_amount / days_in_month, 2)
    return {
        "worked_days": round(worked_days, 2),
        "leave_days": round(leave_days, 2),
        "held_ot_hours": round(held_ot_hours, 2),
        "suggested_per_day_rate": suggested_per_day,
        "period_start": period_start,
        "period_end": period_end,
    }


def prepare_staff_page_db(db):
    ensure_staff_hr_tables(db)
    ensure_staff_bonus_table(db)
    ensure_payroll_tables(db)
    _ensure_column(db, "staff", "date_of_birth", "TEXT")
    _ensure_column(db, "staff", "gender", "TEXT")
    db.commit()


def prepare_payroll_page_db(db):
    ensure_payroll_tables(db)
    try:
        ensure_staff_monthly_attendance_schema(db)
    except Exception:
        app.logger.exception("Staff monthly attendance schema ensure failed")
    try:
        ensure_employee_timesheet_schema(db)
    except Exception:
        app.logger.exception("Employee timesheet schema ensure failed")
    prepare_workers_page_db(db)


def _generate_payroll_run_selected(
    db,
    *,
    run_type,
    period_start,
    period_end,
    month,
    year,
    project_id,
    department,
    employees,
    employment_category,
    created_by,
):
    """Generate payroll for explicit (employee_type, id) pairs."""
    from payroll_service import fetch_holidays

    if not employees:
        raise ValueError("No employees selected.")
    if employment_category == "company_staff":
        project_id = None
    run_ref = f"PR-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO payroll_runs("
        "run_ref, run_type, period_start, period_end, month, year, project_id, department, "
        "employee_type, status, approval_status, locked, draft_saved, created_by, created_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run_ref, run_type, period_start, period_end, month, year, project_id, department,
            employment_category or "selected", "Draft", "Draft", 0, 0, created_by, now,
        ),
    )
    run_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    total_gross = total_net = 0.0
    line_count = 0
    for et, eid in employees:
        if et == "staff":
            emp = db.execute(
                "SELECT s.*, s.staff_name AS employee_name, s.employee_code AS employee_code "
                "FROM staff s WHERE id=?",
                (eid,),
            ).fetchone()
        else:
            emp = db.execute(
                "SELECT w.*, w.worker_name AS employee_name, w.worker_code AS employee_code "
                "FROM workers w WHERE id=?",
                (eid,),
            ).fetchone()
        if not emp:
            continue
        emp = dict(emp)
        emp["employee_type"] = et
        holidays = fetch_holidays(db, period_start, period_end, et)
        if et == "staff":
            calc = calculate_staff_period_pay(db, emp, period_start, period_end, holidays)
        else:
            calc = calculate_worker_period_pay(db, emp, period_start, period_end, holidays)
        total_gross += calc["gross_salary"]
        total_net += calc["net_salary"]
        emp_code, emp_name = _row_employee_identity(emp)
        db.execute(
            "INSERT INTO payroll_lines("
            "payroll_run_id, employee_type, staff_id, worker_id, employee_code, employee_name, "
            "department, project_id, salary_type, base_salary, working_days, present_days, "
            "leave_days, ot_hours, ot_amount, holiday_pay, gross_salary, deductions, "
            "advance_deduction, net_salary, verification_status, approval_status, payment_status, "
            "locked, calc_snapshot"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id, et,
                eid if et == "staff" else None,
                eid if et != "staff" else None,
                emp_code,
                emp_name,
                emp.get("department") or "",
                emp.get("project_id") or project_id,
                emp.get("salary_type") or "Monthly",
                calc["base_salary"], calc["working_days"], calc["present_days"],
                calc["leave_days"], calc["ot_hours"], calc["ot_amount"],
                calc.get("holiday_pay", 0), calc["gross_salary"],
                calc.get("deductions", 0), calc.get("advance_deduction", 0),
                calc["net_salary"], "Pending", "Draft", "Pending", 0,
                json.dumps(calc),
            ),
        )
        line_count += 1
    if line_count == 0:
        db.execute("DELETE FROM payroll_runs WHERE id=?", (run_id,))
        raise ValueError("No valid employees found for selected list.")
    db.execute(
        "UPDATE payroll_runs SET total_gross=?, total_net=?, employee_count=? WHERE id=?",
        (round(total_gross, 2), round(total_net, 2), line_count, run_id),
    )
    return run_id


def _sync_payroll_run_after_workflow(db, approval_id):
    """Keep payroll_runs.status aligned with workflow outcome."""
    req = db.execute(
        "SELECT record_id, record_table FROM approval_requests WHERE id=?",
        (approval_id,),
    ).fetchone()
    if not req or req["record_table"] != "payroll_runs":
        return
    run = db.execute(
        "SELECT approval_status FROM payroll_runs WHERE id=?",
        (req["record_id"],),
    ).fetchone()
    if not run:
        return
    approval = run["approval_status"] or "Draft"
    status_map = {
        RECORD_PENDING_CHECKER: "Pending Checker",
        RECORD_PENDING_APPROVAL: "Pending Approval",
        RECORD_APPROVED: "Approved",
        RECORD_REJECTED_CHECKER: "Draft",
        RECORD_REJECTED_APPROVER: "Draft",
        "Draft": "Draft",
    }
    run_status = status_map.get(approval, approval)
    db.execute(
        "UPDATE payroll_runs SET status=? WHERE id=?",
        (run_status, req["record_id"]),
    )
    if approval == RECORD_APPROVED:
        db.execute(
            "UPDATE payroll_lines SET approval_status=? WHERE payroll_run_id=?",
            (RECORD_APPROVED, req["record_id"]),
        )


def _prepare_store_db(db):
    ensure_store_schema(db)


def _prepare_office_fleet_db(db):
    try:
        ensure_office_fleet_schema(db)
    except Exception:
        app.logger.exception("Office fleet schema ensure failed")


def _prepare_plant_db(db):
    try:
        ensure_plant_schema(db)
    except Exception:
        app.logger.exception("Plant schema ensure failed")


def _prepare_precast_db(db):
    try:
        ensure_precast_schema(db)
        ensure_plant_schema(db)
    except Exception:
        app.logger.exception("Precast yard schema ensure failed")


def _prepare_helpdesk_db(db):
    try:
        ensure_helpdesk_schema(db)
    except Exception:
        app.logger.exception("Help desk schema ensure failed")


def _prepare_qc_db(db):
    try:
        ensure_qc_schema(db)
    except Exception:
        app.logger.exception("QC schema ensure failed")


def _prepare_company_master_db(db):
    try:
        ensure_company_master_schema(db)
    except Exception:
        app.logger.exception("Company master schema ensure failed")


def _prepare_client_billing_db(db):
    try:
        ensure_client_billing_schema(db)
    except Exception:
        app.logger.exception("Client billing schema ensure failed")


def _prepare_employee_timesheet_db(db):
    try:
        ensure_employee_timesheet_schema(db)
    except Exception:
        app.logger.exception("Employee timesheet schema ensure failed")


def _prepare_bbs_db(db):
    try:
        ensure_bbs_schema(db)
    except Exception:
        app.logger.exception("BBS schema ensure failed")


def _prepare_sub_billing_db(db):
    try:
        ensure_subcontractor_billing_schema(db)
    except Exception:
        app.logger.exception("Subcontractor billing schema ensure failed")


def _prepare_subcontract_payments_db(db):
    try:
        ensure_subcontract_payment_schema(db)
    except Exception:
        app.logger.exception("Subcontract payment schema ensure failed")


def _prepare_project_photos_db(db):
    try:
        ensure_project_photos_schema(db)
    except Exception:
        app.logger.exception("Project photos schema ensure failed")


def _prepare_corporate_dms_db(db):
    try:
        ensure_corporate_dms_schema(db)
    except Exception:
        app.logger.exception("Corporate DMS schema ensure failed")


def _prepare_corporate_template_db(db):
    try:
        ensure_corporate_template_schema(db)
    except Exception:
        app.logger.exception("Corporate template schema ensure failed")


def _build_corporate_report_context(db, report_slug, **kwargs):
    """Shared print context for standardized MAXEK reports."""
    report_def = get_report_def(report_slug) or {}
    doc_type_key = report_def.get("doc_type_key")
    doc_number = kwargs.pop("document_number", "") or ""
    if not doc_number and doc_type_key and doc_type_key in DOC_TYPES:
        try:
            doc_number = peek_next_number(db, doc_type_key)
        except Exception:
            doc_number = f"MAXEK/{report_slug.upper()}/{datetime.now().strftime('%Y%m%d')}"
    elif not doc_number:
        doc_number = f"MAXEK/{report_slug.upper()}/{datetime.now().strftime('%Y%m%d')}"
    ctx = build_print_context(
        db,
        report_slug=report_slug,
        document_type=report_def.get("label", report_slug.replace("_", " ").title()),
        document_number=doc_number,
        export_url=url_for("corporate_report_export", slug=report_slug),
        **kwargs,
    )
    return ctx


def _save_corporate_template_assets(form_files):
    """Save uploaded template asset files; returns dict of field -> stored filename."""
    stored = {}
    field_map = {
        "company_logo": "company_logo_path",
        "watermark_logo": "watermark_logo_path",
        "company_seal": "company_seal_path",
        "signatory_image": "signatory_image_path",
    }
    for form_key, db_field in field_map.items():
        upload = form_files.get(form_key)
        if upload and upload.filename:
            ext, err = validate_template_upload(upload)
            if err:
                raise ValueError(err)
            stored[db_field] = save_file(upload, CORPORATE_TEMPLATE_DIR)
    return stored


def _validate_billing_upload(file_storage, required=False):
    if not file_storage or not file_storage.filename:
        if required:
            return None, "Attachment is required."
        return None, None
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in BILLING_ALLOWED_EXTENSIONS:
        return None, "Allowed file types: PDF, JPG, DOC, XLSX."
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_BILLING_UPLOAD_BYTES:
        return None, "File is too large (maximum 10 MB)."
    return ext, None


def _sync_client_billing_after_workflow(db, approval_id):
    """Certify client bill and mark linked DPR measurements when approved."""
    req = db.execute(
        "SELECT module_id, record_id, record_table, workflow_status FROM approval_requests WHERE id=?",
        (approval_id,),
    ).fetchone()
    if not req:
        return
    req = dict(req)
    if req["record_table"] != CLIENT_BILLING_TABLE or req["module_id"] != CLIENT_BILLING_MODULE_ID:
        return
    if req["workflow_status"] == STATUS_APPROVED:
        on_bill_certified(db, req["record_id"])
    elif req["workflow_status"] in (STATUS_REJECTED_CHECKER, STATUS_REJECTED_APPROVER):
        db.execute(
            "UPDATE client_bills SET bill_status='Draft' WHERE id=?",
            (req["record_id"],),
        )


def _validate_office_upload(file_storage, required=False):
    if not file_storage or not file_storage.filename:
        if required:
            return None, "Document attachment is required."
        return None, None
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in OFFICE_ALLOWED_EXTENSIONS:
        return None, "Allowed file types: PDF, JPG, DOC, XLSX."
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_OFFICE_UPLOAD_BYTES:
        return None, "File is too large (maximum 10 MB)."
    return ext, None


def _sync_store_after_workflow(db, approval_id):
    """Post stock ledger entries when GRN / store issues are approved."""
    req = db.execute(
        "SELECT module_id, record_id, record_table, workflow_status FROM approval_requests WHERE id=?",
        (approval_id,),
    ).fetchone()
    if not req:
        return
    req = dict(req)
    if req["record_table"] not in ("store_receipts", "store_issues", "material_transfers"):
        return
    if req["workflow_status"] != STATUS_APPROVED:
        void_stock_for_reference(db, req["record_table"], req["record_id"])
        return
    ensure_store_schema(db)
    try:
        post_stock_on_approval(
            db,
            req["record_table"],
            req["record_id"],
            session.get("username", "system"),
        )
    except ValueError as exc:
        flash(str(exc), "warning")


def _sync_subcontract_payments_after_workflow(db, approval_id):
    """Recalculate paid totals when subcontract payment entries are approved."""
    req = db.execute(
        "SELECT module_id, record_id, record_table, workflow_status FROM approval_requests WHERE id=?",
        (approval_id,),
    ).fetchone()
    if not req:
        return
    req = dict(req)
    if req["record_table"] != SUB_PAYMENT_ENTRY_TABLE:
        return
    ensure_subcontract_payment_schema(db)
    if req["workflow_status"] == STATUS_APPROVED:
        apply_payment_on_approval(db, req["record_id"])
    else:
        row = db.execute(
            "SELECT work_order_id FROM subcontract_payment_entries WHERE id=?",
            (req["record_id"],),
        ).fetchone()
        if row:
            refresh_work_order_paid_totals(db, row["work_order_id"])


def _sync_accounts_after_workflow(db, approval_id):
    """Auto-post journal entries when accounts vouchers are approved."""
    req = db.execute(
        "SELECT module_id, record_id, record_table, workflow_status FROM approval_requests WHERE id=?",
        (approval_id,),
    ).fetchone()
    if not req:
        return
    req = dict(req)
    if req["workflow_status"] != STATUS_APPROVED:
        if req["record_table"] in ("account_expenses", "payment_vouchers", "receipt_vouchers"):
            void_journal_for_reference(db, req["record_table"], req["record_id"])
        return
    if req["record_table"] not in ("account_expenses", "payment_vouchers", "receipt_vouchers"):
        return
    ensure_accounts_schema(db)
    post_journal_on_approval(
        db,
        req["record_table"],
        req["record_id"],
        session.get("username", "system"),
    )


def _sync_treasury_after_workflow(db, approval_id):
    """Update bank balances when treasury payments/receipts are approved."""
    req = db.execute(
        "SELECT module_id, record_id, record_table, workflow_status FROM approval_requests WHERE id=?",
        (approval_id,),
    ).fetchone()
    if not req:
        return
    req = dict(req)
    treasury_tables = ("bank_payments", "bank_receipts", "bank_guarantees")
    if req["record_table"] not in treasury_tables:
        return
    ensure_treasury_schema(db)
    if req["workflow_status"] != STATUS_APPROVED:
        if req["record_table"] in ("bank_payments", "bank_receipts"):
            void_treasury_on_reversal(db, req["record_table"], req["record_id"], session.get("username", "system"))
        return
    post_treasury_on_approval(
        db,
        req["record_table"],
        req["record_id"],
        session.get("username", "system"),
    )


def prepare_hr_bonus_db(db):
    ensure_staff_bonus_table(db)
    ensure_app_settings_table(db)


def _fetch_staff_salary_components(db, staff_id):
    rows = db.execute(
        "SELECT component_name, amount FROM staff_salary_components "
        "WHERE staff_id=? ORDER BY sort_order, id",
        (staff_id,),
    ).fetchall()
    return [{"component_name": r["component_name"], "amount": float(r["amount"] or 0)} for r in rows]


def _fetch_staff_travel_tiers(db, staff_id):
    rows = db.execute(
        "SELECT continuous_months, travel_mode, allowance_amount FROM staff_travel_tiers "
        "WHERE staff_id=? ORDER BY sort_order, continuous_months, id",
        (staff_id,),
    ).fetchall()
    return [
        {
            "continuous_months": int(r["continuous_months"] or 0),
            "travel_mode": r["travel_mode"] or "One Side",
            "allowance_amount": float(r["allowance_amount"] or 0),
        }
        for r in rows
    ]


def _fetch_staff_salary_increments(db, staff_id):
    rows = db.execute(
        "SELECT * FROM staff_salary_increments WHERE staff_id=? "
        "ORDER BY effective_date DESC, id DESC",
        (staff_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _save_staff_salary_components(db, staff_id, components):
    db.execute("DELETE FROM staff_salary_components WHERE staff_id=?", (staff_id,))
    for idx, comp in enumerate(components):
        name = (comp.get("component_name") or "").strip()
        if not name:
            continue
        try:
            amount = float(comp.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0
        db.execute(
            "INSERT INTO staff_salary_components(staff_id, component_name, amount, sort_order) "
            "VALUES(?,?,?,?)",
            (staff_id, name, amount, idx),
        )


def _save_staff_travel_tiers(db, staff_id, tiers):
    db.execute("DELETE FROM staff_travel_tiers WHERE staff_id=?", (staff_id,))
    for idx, tier in enumerate(tiers):
        try:
            months = int(tier.get("continuous_months") or 0)
        except (TypeError, ValueError):
            months = 0
        if months <= 0:
            continue
        mode = (tier.get("travel_mode") or "One Side").strip()
        if mode not in ("One Side", "Both Side"):
            mode = "One Side"
        try:
            allowance = float(tier.get("allowance_amount") or 0)
        except (TypeError, ValueError):
            allowance = 0.0
        db.execute(
            "INSERT INTO staff_travel_tiers(staff_id, continuous_months, travel_mode, "
            "allowance_amount, sort_order) VALUES(?,?,?,?,?)",
            (staff_id, months, mode, allowance, idx),
        )


def _parse_staff_hr_json(raw, default):
    try:
        data = json.loads(raw or "[]")
        return data if isinstance(data, list) else default
    except json.JSONDecodeError:
        return default


def _unit_measurement_type(unit):
    u = (unit or "").strip()
    if u in VOLUME_UNITS:
        return "volume"
    if u in AREA_UNITS:
        return "area"
    if u in STEEL_UNITS:
        return "steel"
    return "simple"


def _average_readings(values):
    nums = []
    for v in values:
        try:
            n = float(v)
            if n > 0:
                nums.append(n)
        except (TypeError, ValueError):
            continue
    return round(sum(nums) / len(nums), 4) if nums else 0.0


def _steel_bar_weight_kg(diameter_mm, length_m, num_bars):
    d = float(diameter_mm or 0)
    length = float(length_m or 0)
    bars = int(num_bars or 0)
    if d <= 0 or length <= 0 or bars <= 0:
        return 0.0
    return round((d * d * length * bars) / 162.0, 4)


def _cutting_length_from_shape(formula_type, sides, manual_length):
    manual = float(manual_length or 0)
    if formula_type == "straight":
        return manual
    side_vals = []
    for s in sides or []:
        try:
            v = float(s)
            if v > 0:
                side_vals.append(v)
        except (TypeError, ValueError):
            continue
    if side_vals:
        return round(sum(side_vals) / 1000.0, 4)
    return manual


def _parse_dpr_measurement_payload(payload, unit):
    mtype = _unit_measurement_type(unit)
    result = {"type": mtype, "quantity": 0.0, "data": payload}
    if mtype == "volume":
        avg_l = _average_readings(payload.get("lengths") or [])
        avg_w = _average_readings(payload.get("widths") or [])
        avg_d = _average_readings(payload.get("depths") or [])
        qty = round(avg_l * avg_w * avg_d, 4)
        result["quantity"] = qty
        result["data"] = {
            "lengths": payload.get("lengths") or [],
            "widths": payload.get("widths") or [],
            "depths": payload.get("depths") or [],
            "avg_length": avg_l,
            "avg_width": avg_w,
            "avg_depth": avg_d,
        }
    elif mtype == "area":
        avg_l = _average_readings(payload.get("lengths") or [])
        avg_w = _average_readings(payload.get("widths") or [])
        qty = round(avg_l * avg_w, 4)
        result["quantity"] = qty
        result["data"] = {
            "lengths": payload.get("lengths") or [],
            "widths": payload.get("widths") or [],
            "avg_length": avg_l,
            "avg_width": avg_w,
        }
    elif mtype == "steel":
        lines = []
        total_qty = 0.0
        unit_norm = (unit or "").strip().upper()
        for line in payload.get("lines") or []:
            cutting_m = _cutting_length_from_shape(
                line.get("formula_type", "straight"),
                line.get("side_measurements") or [],
                line.get("cutting_length"),
            )
            weight_kg = _steel_bar_weight_kg(
                line.get("diameter_mm"),
                cutting_m,
                line.get("num_bars"),
            )
            if unit_norm == "MT":
                line_qty = round(weight_kg / 1000.0, 4)
            else:
                line_qty = weight_kg
            line["cutting_length_m"] = cutting_m
            line["quantity"] = line_qty
            lines.append(line)
            total_qty += line_qty
        result["quantity"] = round(total_qty, 4)
        result["data"] = {"lines": lines}
    else:
        rows = payload.get("rows") or []
        use_average = bool(payload.get("use_average"))
        if rows:
            qty_vals = []
            for row in rows:
                try:
                    qty_vals.append(float(row.get("quantity") or 0))
                except (TypeError, ValueError):
                    qty_vals.append(0.0)
            positive = [v for v in qty_vals if v > 0]
            if use_average and positive:
                total = round(sum(positive) / len(positive), 4)
            else:
                total = round(sum(qty_vals), 4)
            result["quantity"] = total
            result["data"] = {
                "rows": rows,
                "use_average": use_average,
                "total_quantity": round(sum(qty_vals), 4),
                "average_quantity": round(sum(positive) / len(positive), 4) if positive else 0.0,
            }
        else:
            try:
                result["quantity"] = round(float(payload.get("quantity") or 0), 4)
            except (TypeError, ValueError):
                result["quantity"] = 0.0
    return result


CLIENT_BILL_SQL = """
    SELECT m.*, p.project_code, p.project_name, p.client_id, p.private_client_name,
           c.company_name, c.client_name, c.gst_number, c.address AS client_address,
           COALESCE(bi.rate, 0) AS boq_rate,
           ROUND(m.calculated_quantity * COALESCE(bi.rate, 0), 2) AS bill_amount
    FROM dpr_measurements m
    LEFT JOIN projects p ON m.project_id = p.id
    LEFT JOIN clients c ON p.client_id = c.id
    LEFT JOIN boq_items bi ON m.boq_item_id = bi.id
"""


def _fetch_client_bill_rows(measurement_ids=None, pending_only=True):
    clauses = []
    params = []
    if pending_only:
        clauses.append("m.bill_client=1 AND m.billing_status='pending'")
        clauses.append("COALESCE(m.dpr_status, 'submitted') != 'draft'")
    if measurement_ids:
        placeholders = ",".join("?" * len(measurement_ids))
        clauses.append(f"m.id IN ({placeholders})")
        params.extend(measurement_ids)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return query_db(
        CLIENT_BILL_SQL + where + " ORDER BY m.report_date DESC, m.id DESC",
        params,
    )


def _manpower_line_cost(mp_row):
    hours = float(mp_row.get("hours_worked") or 0)
    if hours <= 0:
        return 0.0
    subcontractor_id = mp_row.get("subcontractor_id")
    trade = (mp_row.get("trade_name") or "").strip()
    if subcontractor_id and trade:
        rate = get_subcontractor_manpower_rate(subcontractor_id, trade)
        if rate:
            rate_unit = (rate["rate_unit"] or "Day").strip()
            rate_amount = float(rate["rate_amount"] or 0)
            salary_amount = float(rate["salary_amount"] or 0)
            if rate_unit == "Hour":
                return round(hours * rate_amount, 2)
            working_hours = float(rate["working_hours"] or 8) or 8
            day_rate = rate_amount or salary_amount
            return round((hours / working_hours) * day_rate, 2)
    worker_id = mp_row.get("worker_id")
    if worker_id:
        worker = query_db(
            "SELECT salary_type, salary_amount, working_hours FROM workers WHERE id=?",
            (worker_id,),
            one=True,
        )
        if worker:
            working_hours = float(worker["working_hours"] or 8) or 8
            salary = float(worker["salary_amount"] or 0)
            if (worker["salary_type"] or "").strip() == "Hourly":
                return round(hours * salary, 2)
            return round((hours / working_hours) * salary, 2)
    return 0.0


def _push_dpr_to_project_costing(db, measurement_id):
    row = query_db(
        CLIENT_BILL_SQL + " WHERE m.id=?",
        (measurement_id,),
        one=True,
    )
    if not row:
        return False, "Measurement not found."
    measurement = dict(row)
    if not measurement["for_costing"]:
        return False, "Measurement is not flagged for costing."
    if measurement["costing_status"] == "linked":
        return False, "Already linked to Project Costing."

    mp_rows = query_db(
        "SELECT mp.*, s.subcontractor_name FROM dpr_manpower mp "
        "LEFT JOIN subcontractors s ON mp.subcontractor_id = s.id "
        "WHERE mp.measurement_id=?",
        (measurement_id,),
    )
    created_by = session.get("username", "")
    expense_ids = []
    total_amount = 0.0

    work_amount = float(measurement["bill_amount"] or 0)
    if work_amount > 0:
        work_desc = (
            f"DPR #{measurement_id}: {measurement['boq_number'] or ''} — "
            f"{measurement['boq_description'] or ''} "
            f"({measurement['calculated_quantity']} {measurement['unit']})"
        )
        if measurement.get("work_description"):
            work_desc = f"{measurement['work_description']} | {work_desc}"
        db.execute(
            "INSERT INTO project_expenses(project_id, expense_date, expense_category, amount, "
            "description, dpr_measurement_id, created_by, approval_status) VALUES(?,?,?,?,?,?,?,?)",
            (
                measurement["project_id"],
                measurement["report_date"],
                "DPR Work Progress",
                work_amount,
                work_desc,
                measurement_id,
                created_by,
                RECORD_PENDING_CHECKER,
            ),
        )
        expense_ids.append(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        total_amount += work_amount

    for mp in mp_rows:
        mp_dict = dict(mp)
        amount = _manpower_line_cost(mp_dict)
        worker_label = mp_dict.get("worker_name") or "Worker"
        sub_label = mp_dict.get("subcontractor_name") or "Company"
        trade = mp_dict.get("trade_name") or "Manpower"
        desc = (
            f"DPR #{measurement_id} manpower — {sub_label}, {worker_label}, "
            f"{trade}, {mp_dict.get('hours_worked') or 0} hrs"
        )
        if mp_dict.get("remarks"):
            desc += f" ({mp_dict['remarks']})"
        db.execute(
            "INSERT INTO project_expenses(project_id, expense_date, expense_category, amount, "
            "description, dpr_measurement_id, created_by, approval_status) VALUES(?,?,?,?,?,?,?,?)",
            (
                measurement["project_id"],
                measurement["report_date"],
                f"DPR Manpower — {trade}",
                amount,
                desc,
                measurement_id,
                created_by,
                RECORD_PENDING_CHECKER,
            ),
        )
        expense_ids.append(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        total_amount += amount

    if not expense_ids:
        return False, "No costing lines to create (add manpower or ensure BOQ rate exists)."

    for expense_id in expense_ids:
        create_approval_request(
            db, "project_expenses", expense_id, "project_expenses", created_by, session.get("user_id")
        )

    db.execute(
        "UPDATE dpr_measurements SET costing_status='linked' WHERE id=?",
        (measurement_id,),
    )
    db.commit()
    return True, f"Created {len(expense_ids)} expense line(s), total {total_amount:,.2f}."


def get_project_options_for_boq():
    return query_db(
        "SELECT id, project_code, project_name FROM projects "
        "WHERE status IS NULL OR status != 'Inactive' ORDER BY project_name"
    )


ATTENDANCE_WORKER_JOIN_SQL = (
    "LEFT JOIN workers w ON a.worker_id = w.id "
    "AND COALESCE(a.worker_source, 'worker') = 'worker' "
    "LEFT JOIN staff s ON a.worker_id = s.id AND a.worker_source = 'staff'"
)


def format_attendance_worker_ref(worker_id, worker_source=None):
    if worker_id is None or str(worker_id).strip() == "":
        return ""
    source = (worker_source or "worker").strip().lower()
    prefix = "s" if source == "staff" else "w"
    return f"{prefix}:{int(worker_id)}"


def parse_attendance_worker_ref(ref):
    value = (ref or "").strip()
    if not value:
        return None, "worker"
    if value.startswith("s:"):
        try:
            return int(value[2:]), "staff"
        except ValueError:
            return None, "staff"
    if value.startswith("w:"):
        try:
            return int(value[2:]), "worker"
        except ValueError:
            return None, "worker"
    try:
        return int(value), "worker"
    except ValueError:
        return None, "worker"


def get_attendance_worker_options():
    """Legacy combined list; prefer get_attendance_form_worker_data() for the form."""
    data = get_attendance_form_worker_data()
    return data["company_staff"]


def resolve_trade_id_by_name(trade_name):
    name = (trade_name or "").strip()
    if not name:
        return None
    row = query_db(
        "SELECT id FROM trades WHERE trade_name=? AND status='Active'",
        (name,),
        one=True,
    )
    return row["id"] if row else None


def resolve_designation_id_by_name(designation_name):
    name = (designation_name or "").strip()
    if not name:
        return None
    row = query_db(
        "SELECT id FROM designations WHERE designation_name=? AND status='Active'",
        (name,),
        one=True,
    )
    return row["id"] if row else None


def attendance_master_ids_for_worker(worker_id, worker_source):
    """Designation/trade IDs from employee master for attendance auto-fill."""
    if not worker_id:
        return {"designation_id": None, "trade_id": None}
    if (worker_source or "worker") == "staff":
        row = query_db(
            "SELECT designation_id FROM staff WHERE id=?",
            (worker_id,),
            one=True,
        )
        desig_id = row["designation_id"] if row else None
        return {"designation_id": desig_id, "trade_id": None}
    row = query_db(
        "SELECT designation, worker_category FROM workers WHERE id=?",
        (worker_id,),
        one=True,
    )
    if not row:
        return {"designation_id": None, "trade_id": None}
    category = (row.get("worker_category") or "Company Staff").strip()
    desig_text = row.get("designation") or ""
    if category == "Sub Contractor Staff":
        return {
            "designation_id": None,
            "trade_id": resolve_trade_id_by_name(desig_text),
        }
    return {
        "designation_id": resolve_designation_id_by_name(desig_text),
        "trade_id": None,
    }


def get_attendance_form_worker_data():
    """Company staff, subcontractors, and subcontractor workers for attendance form."""
    staff_rows = query_db(
        "SELECT s.id, s.employee_code AS worker_code, s.staff_name AS worker_name, s.photo, "
        "s.designation_id "
        "FROM staff s "
        "WHERE s.status IS NULL OR s.status = 'Active' "
        "ORDER BY s.staff_name, s.employee_code"
    )
    company_worker_rows = query_db(
        "SELECT id, worker_code, worker_name, photo, designation FROM workers "
        "WHERE (status IS NULL OR status = 'Active') "
        "AND COALESCE(worker_category, 'Company Staff') != 'Sub Contractor Staff' "
        "ORDER BY worker_name, worker_code"
    )
    subcontractor_rows = query_db(
        "SELECT id, subcontractor_code, subcontractor_name FROM subcontractors "
        "WHERE status IS NULL OR status = 'Active' "
        "ORDER BY subcontractor_name"
    )
    subcontractor_worker_rows = query_db(
        "SELECT id, worker_code, worker_name, photo, subcontractor_id, designation, working_hours "
        "FROM workers "
        "WHERE (status IS NULL OR status = 'Active') "
        "AND COALESCE(worker_category, 'Company Staff') = 'Sub Contractor Staff' "
        "AND subcontractor_id IS NOT NULL "
        "ORDER BY worker_name, worker_code"
    )
    company_staff = []
    for row in staff_rows:
        item = dict(row)
        item["worker_source"] = "staff"
        item["ref"] = format_attendance_worker_ref(item["id"], "staff")
        item["trade_id"] = None
        company_staff.append(item)
    for row in company_worker_rows:
        item = dict(row)
        item["worker_source"] = "worker"
        item["ref"] = format_attendance_worker_ref(item["id"], "worker")
        item["designation_id"] = resolve_designation_id_by_name(item.get("designation"))
        item["trade_id"] = None
        company_staff.append(item)
    company_staff.sort(
        key=lambda item: (
            (item.get("worker_name") or "").lower(),
            (item.get("worker_code") or "").lower(),
        )
    )
    subcontractor_workers = []
    for row in subcontractor_worker_rows:
        item = dict(row)
        item["worker_source"] = "worker"
        item["ref"] = format_attendance_worker_ref(item["id"], "worker")
        item["designation_id"] = None
        item["trade_id"] = resolve_trade_id_by_name(item.get("designation"))
        subcontractor_workers.append(item)
    return {
        "company_staff": company_staff,
        "subcontractors": [dict(row) for row in subcontractor_rows],
        "subcontractor_workers": subcontractor_workers,
    }


def get_attendance_edit_worker_context(edit_record):
    """Derive staff type and subcontractor for attendance edit form."""
    if not edit_record:
        return {"staff_type": "", "subcontractor_id": ""}
    edit_record = dict(edit_record)
    if (edit_record.get("worker_source") or "worker") == "staff":
        return {"staff_type": "Company Staff", "subcontractor_id": ""}
    worker_row = query_db(
        "SELECT worker_category, subcontractor_id FROM workers WHERE id=?",
        (edit_record["worker_id"],),
        one=True,
    )
    if not worker_row:
        return {"staff_type": "Company Staff", "subcontractor_id": ""}
    worker_row = dict(worker_row)
    worker_category = (worker_row.get("worker_category") or "Company Staff").strip()
    if worker_category == "Sub Contractor Staff" and worker_row.get("subcontractor_id"):
        return {
            "staff_type": "Sub Contractor Staff",
            "subcontractor_id": str(worker_row["subcontractor_id"]),
        }
    return {"staff_type": "Company Staff", "subcontractor_id": ""}


def get_attendance_project_options():
    return query_db(
        "SELECT id, project_code, project_name FROM projects "
        "WHERE status IS NULL OR status != 'Inactive' ORDER BY project_name"
    )


def ensure_trades_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS trades(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_name TEXT UNIQUE,
            status TEXT DEFAULT 'Active'
        )
    """)
    _ensure_column(db, "trades", "status", "TEXT DEFAULT 'Active'")
    db.execute(
        "UPDATE trades SET status='Active' WHERE status IS NULL OR TRIM(status)=''"
    )
    for trade_name in MANPOWER_TRADES:
        try:
            db.execute(
                "INSERT INTO trades(trade_name, status) VALUES(?, 'Active')",
                (trade_name,),
            )
        except sqlite3.IntegrityError:
            pass


def ensure_designations_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS designations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            designation_name TEXT UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)
    _ensure_column(db, "designations", "description", "TEXT")
    _ensure_column(db, "designations", "status", "TEXT DEFAULT 'Active'")
    db.execute(
        "UPDATE designations SET status='Active' "
        "WHERE status IS NULL OR TRIM(status)=''"
    )


def ensure_attendance_master_schema(db):
    """Trades/designations and attendance FK columns used by timesheet joins."""
    ensure_trades_table(db)
    ensure_designations_table(db)
    _ensure_column(db, "attendance", "worker_source", "TEXT DEFAULT 'worker'")
    _ensure_column(db, "attendance", "approval_status", "TEXT DEFAULT 'Pending Checker'")
    _ensure_column(db, "attendance", "trade_id", "INTEGER")
    _ensure_column(db, "attendance", "designation_id", "INTEGER")


def get_active_trades():
    return query_db(
        "SELECT id, trade_name FROM trades WHERE status='Active' ORDER BY trade_name"
    )


def get_active_designations():
    return query_db(
        "SELECT id, designation_name FROM designations "
        "WHERE status='Active' ORDER BY designation_name"
    )


def format_decimal_hours(value):
    """Convert decimal hours (e.g. 8.5) to h:mm for display."""
    if value is None or value == "":
        return "0:00"
    try:
        total_minutes = int(round(float(value) * 60))
    except (TypeError, ValueError):
        return "0:00"
    if total_minutes < 0:
        total_minutes = 0
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}:{minutes:02d}"


def safe_url_for(endpoint, **values):
    """url_for that survives partial deploys (missing routes on VPS)."""
    try:
        return url_for(endpoint, **values)
    except Exception:
        app.logger.warning("safe_url_for: missing or invalid endpoint %r", endpoint)
        return "#"


def _dept_portal_return_url(default_slug="projects"):
    """Return URL for post-save navigation — dept workspace (new UI), not legacy module shell."""
    raw = (request.args.get("dept") or request.form.get("dept") or "").strip()
    if raw:
        slug = resolve_department_portal_slug(raw)
        return url_for("department_portal", slug=slug)
    referrer = request.referrer or ""
    match = re.search(r"/dept/([^/?#]+)", referrer)
    if match:
        slug = resolve_department_portal_slug(match.group(1))
        return url_for("department_portal", slug=slug)
    return url_for("department_portal", slug=resolve_department_portal_slug(default_slug))


app.jinja_env.globals["format_decimal_hours"] = format_decimal_hours
app.jinja_env.globals["safe_url_for"] = safe_url_for


def _create_trade_from_form(db):
    name = request.form.get("trade_name", "").strip()
    if not name:
        flash("Enter a trade name.")
        return None
    try:
        db.execute(
            "INSERT INTO trades(trade_name, status) VALUES(?, 'Active')",
            (name,),
        )
        db.commit()
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]
    except sqlite3.IntegrityError:
        row = db.execute(
            "SELECT id FROM trades WHERE trade_name=?", (name,)
        ).fetchone()
        return row["id"] if row else None


def _create_designation_from_form(db):
    name = request.form.get("designation_name", "").strip()
    if not name:
        flash("Enter a designation name.")
        return None
    try:
        db.execute(
            "INSERT INTO designations(designation_name, status) VALUES(?, 'Active')",
            (name,),
        )
        db.commit()
        return db.execute("SELECT last_insert_rowid()").fetchone()[0]
    except sqlite3.IntegrityError:
        row = db.execute(
            "SELECT id FROM designations WHERE designation_name=?", (name,)
        ).fetchone()
        return row["id"] if row else None


ATTENDANCE_MASTER_JOIN_SQL = (
    "LEFT JOIN trades t ON a.trade_id = t.id "
    "LEFT JOIN designations ad ON a.designation_id = ad.id"
)


def _parse_boq_line_items(max_lines=None):
    if max_lines is None:
        max_lines = MAX_BOQ_LINES
    descriptions = request.form.getlist("item_description[]")
    quantities = request.form.getlist("quantity[]")
    units = request.form.getlist("unit[]")
    rates = request.form.getlist("rate[]")
    lines = []
    row_count = max(len(descriptions), len(quantities), len(units), len(rates))
    for idx in range(min(row_count, max_lines)):
        desc = (descriptions[idx] if idx < len(descriptions) else "").strip()
        qty_raw = quantities[idx] if idx < len(quantities) else ""
        rate_raw = rates[idx] if idx < len(rates) else ""
        unit = (units[idx] if idx < len(units) else "").strip() or BOQ_UNITS[0]
        if unit not in BOQ_UNITS:
            unit = BOQ_UNITS[0]
        if not desc and not str(qty_raw).strip() and not str(rate_raw).strip():
            continue
        if not desc:
            return None, "Each BOQ line item must have a description."
        try:
            qty = float(qty_raw or 0)
            rate = float(rate_raw or 0)
        except ValueError:
            return None, "Enter valid quantity and rate for all BOQ line items."
        lines.append({
            "line_no": len(lines) + 1,
            "item_description": desc,
            "quantity": qty,
            "unit": unit,
            "rate": rate,
            "amount": round(qty * rate, 2),
        })
    return lines, None


DEFAULT_DEPARTMENTS = [
    "Head Office", "Accounts", "Site Operations", "Store", "Purchase",
    "HR & Payroll", "Projects", "Management",
]


def ensure_department_master(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS departments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_name TEXT UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)
    cols = [row[1] for row in db.execute("PRAGMA table_info(departments)").fetchall()]
    if "department_name" not in cols:
        db.execute("ALTER TABLE departments ADD COLUMN department_name TEXT")
    if "description" not in cols:
        db.execute("ALTER TABLE departments ADD COLUMN description TEXT")
    if "status" not in cols:
        db.execute("ALTER TABLE departments ADD COLUMN status TEXT DEFAULT 'Active'")
    row = db.execute("SELECT COUNT(*) AS count FROM departments").fetchone()
    if int(row["count"]) == 0:
        db.executemany(
            "INSERT INTO departments(department_name, status) VALUES(?, 'Active')",
            [(dept,) for dept in DEFAULT_DEPARTMENTS],
        )
        db.commit()


def get_departments():
    ensure_department_master(get_db())
    rows = query_db("SELECT department_name FROM departments WHERE status='Active' ORDER BY department_name")
    return [row["department_name"] for row in rows] or DEFAULT_DEPARTMENTS


def _table_exists(db, table):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_column(db, table, column, col_type):
    if not _table_exists(db, table):
        return
    cols = [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def ensure_approval_requests_schema(db):
    """Create or upgrade approval_requests for legacy VPS databases."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS approval_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            record_table TEXT NOT NULL,
            current_stage TEXT DEFAULT 'checker',
            workflow_status TEXT DEFAULT 'pending_checker',
            maker_user_id INTEGER,
            checker_user_id INTEGER,
            approver_user_id INTEGER,
            maker_action_at TEXT,
            checker_action_at TEXT,
            approver_action_at TEXT,
            rejection_reason TEXT,
            created_by TEXT,
            created_at TEXT,
            UNIQUE(module_id, record_id, record_table)
        )
    """)
    for column, col_type in (
        ("module_id", "TEXT"),
        ("record_id", "INTEGER"),
        ("record_table", "TEXT"),
        ("current_stage", "TEXT DEFAULT 'checker'"),
        ("workflow_status", "TEXT DEFAULT 'pending_checker'"),
        ("maker_user_id", "INTEGER"),
        ("checker_user_id", "INTEGER"),
        ("approver_user_id", "INTEGER"),
        ("maker_action_at", "TEXT"),
        ("checker_action_at", "TEXT"),
        ("approver_action_at", "TEXT"),
        ("rejection_reason", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT"),
        ("checker_comment", "TEXT"),
        ("approver_comment", "TEXT"),
    ):
        _ensure_column(db, "approval_requests", column, col_type)


def ensure_account_transactions_table(db):
    """Create account_transactions and project joins used by Accounts modules."""
    _ensure_column(db, "projects", "project_code", "TEXT")
    db.execute("""
        CREATE TABLE IF NOT EXISTS account_transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_type TEXT,
            project_id INTEGER,
            transaction_date TEXT,
            party_name TEXT,
            account_head TEXT,
            amount REAL,
            payment_mode TEXT,
            reference_no TEXT,
            tax_percent REAL,
            remarks TEXT,
            created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    for column, col_type in (
        ("transaction_type", "TEXT"),
        ("project_id", "INTEGER"),
        ("transaction_date", "TEXT"),
        ("party_name", "TEXT"),
        ("account_head", "TEXT"),
        ("amount", "REAL"),
        ("payment_mode", "TEXT"),
        ("reference_no", "TEXT"),
        ("tax_percent", "REAL"),
        ("remarks", "TEXT"),
        ("created_by", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'Pending Checker'"),
    ):
        _ensure_column(db, "account_transactions", column, col_type)


def ensure_workflow_master_schema(db):
    """Create or upgrade workflow_master for legacy VPS databases."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS workflow_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_name TEXT NOT NULL,
            module_id TEXT UNIQUE NOT NULL,
            workflow_role_mapping TEXT,
            maker_designation_id INTEGER,
            checker_designation_id INTEGER,
            approver_designation_id INTEGER,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY(maker_designation_id) REFERENCES designations(id),
            FOREIGN KEY(checker_designation_id) REFERENCES designations(id),
            FOREIGN KEY(approver_designation_id) REFERENCES designations(id)
        )
    """)
    for column, col_type in (
        ("module_name", "TEXT"),
        ("module_id", "TEXT"),
        ("workflow_role_mapping", "TEXT"),
        ("maker_designation_id", "INTEGER"),
        ("checker_designation_id", "INTEGER"),
        ("approver_designation_id", "INTEGER"),
        ("workflow_mode", f"TEXT DEFAULT '{DEFAULT_WORKFLOW_MODE}'"),
        ("status", "TEXT DEFAULT 'Active'"),
    ):
        _ensure_column(db, "workflow_master", column, col_type)


def ensure_notifications_schema(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            notification_type TEXT,
            module_id TEXT,
            record_id INTEGER,
            record_table TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    for column, col_type in (
        ("notification_type", "TEXT"),
        ("module_id", "TEXT"),
        ("record_id", "INTEGER"),
        ("record_table", "TEXT"),
        ("is_read", "INTEGER DEFAULT 0"),
        ("created_at", "TEXT"),
    ):
        _ensure_column(db, "notifications", column, col_type)


_SCHEMA_BOOTSTRAPPED = False
_SUPER_ADMIN_BOOTSTRAPPED = False
_BACKUP_SCHEDULE_CHECKED = False


def _bootstrap_super_admin_runtime(db, *, force=False):
    """Run platform schema + seed once per worker; safe to call repeatedly."""
    global _SUPER_ADMIN_BOOTSTRAPPED
    if _SUPER_ADMIN_BOOTSTRAPPED and not force:
        return
    bootstrap_super_admin(db, hash_password_fn=hash_password)
    _SUPER_ADMIN_BOOTSTRAPPED = True


def ensure_runtime_schema(db=None, force=False):
    """Idempotent schema sync for gunicorn/VPS when init_db is not run at import."""
    global _SCHEMA_BOOTSTRAPPED
    if _SCHEMA_BOOTSTRAPPED and not force:
        return
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if db is None:
        db = get_db()
    ensure_approval_requests_schema(db)
    ensure_account_transactions_table(db)
    ensure_accounts_schema(db)
    try:
        ensure_store_schema(db)
    except Exception:
        app.logger.exception("Store schema bootstrap failed")
    try:
        ensure_office_fleet_schema(db)
    except Exception:
        app.logger.exception("Office fleet schema bootstrap failed")
    try:
        ensure_plant_schema(db)
    except Exception:
        app.logger.exception("Plant schema bootstrap failed")
    try:
        ensure_precast_schema(db)
    except Exception:
        app.logger.exception("Precast yard schema bootstrap failed")
    try:
        ensure_helpdesk_schema(db)
    except Exception:
        app.logger.exception("Help desk schema bootstrap failed")
    try:
        _bootstrap_super_admin_runtime(db)
    except Exception:
        app.logger.exception("Super admin schema bootstrap failed")
        _SUPER_ADMIN_BOOTSTRAPPED = False
    try:
        ensure_qc_schema(db)
    except Exception:
        app.logger.exception("QC schema bootstrap failed")
    try:
        ensure_company_master_schema(db)
    except Exception:
        app.logger.exception("Company master schema bootstrap failed")
    try:
        ensure_client_billing_schema(db)
    except Exception:
        app.logger.exception("Client billing schema bootstrap failed")
    try:
        ensure_project_photos_schema(db)
    except Exception:
        app.logger.exception("Project photos schema bootstrap failed")
    try:
        ensure_employee_timesheet_schema(db)
    except Exception:
        app.logger.exception("Employee timesheet schema bootstrap failed")
    try:
        ensure_bbs_schema(db)
    except Exception:
        app.logger.exception("BBS schema bootstrap failed")
    try:
        ensure_subcontractor_billing_schema(db)
    except Exception:
        app.logger.exception("Subcontractor billing schema bootstrap failed")
    try:
        ensure_subcontract_payment_schema(db)
    except Exception:
        app.logger.exception("Subcontract payment schema bootstrap failed")
    try:
        ensure_corporate_dms_schema(db)
    except Exception:
        app.logger.exception("Corporate DMS schema bootstrap failed")
    try:
        ensure_corporate_template_schema(db)
    except Exception:
        app.logger.exception("Corporate template schema bootstrap failed")
    try:
        ensure_user_context_schema(db)
        ensure_attachment_schema(db)
        ensure_audit_schema(db)
        ensure_user_tab_permissions_schema(db)
    except Exception:
        app.logger.exception("ERP platform schema bootstrap failed")
    _create_transaction_tables(db.cursor())
    for table in (
        "material_requests",
        "purchase_requests",
        "purchase_orders",
        "store_receipts",
        "store_issues",
    ):
        _ensure_column(db, table, "approval_status", "TEXT DEFAULT 'Pending Checker'")
    _ensure_column(db, "material_requests", "request_date", "TEXT")
    _ensure_column(db, "material_requests", "material_id", "INTEGER")
    ensure_petty_cash_tables(db)
    ensure_security_guarantees_tables(db)
    ensure_project_guarantees_table(db)
    ensure_treasury_schema(db)
    ensure_budget_schema(db)
    ensure_contract_schema(db)
    ensure_claims_schema(db)
    ensure_equipment_costing_schema(db)
    ensure_labour_productivity_schema(db)
    ensure_alert_engine_schema(db)
    ensure_document_numbering_schema(db)
    seed_default_sequences(db)
    ensure_backup_schema(db)
    ensure_cost_planning_tables(db)
    ensure_payroll_tables(db)
    ensure_attendance_master_schema(db)
    try:
        ensure_staff_monthly_attendance_schema(db)
    except Exception:
        app.logger.exception("Staff monthly attendance schema bootstrap failed")
    ensure_boq_master_table(db)
    ensure_dpr_measurement_tables(db)
    _ensure_column(db, "users", "designation_id", "INTEGER")
    _ensure_column(db, "users", "workflow_role", "TEXT")
    _ensure_column(db, "users", "reporting_manager", "TEXT")
    _ensure_column(db, "users", "employee_name", "TEXT")
    _ensure_column(db, "users", "department", "TEXT")
    _ensure_column(db, "users", "status", "TEXT DEFAULT 'Active'")
    _ensure_column(db, "users", "role", "TEXT")
    ensure_app_settings_table(db)
    ensure_workflow_master_schema(db)
    ensure_notifications_schema(db)
    ensure_user_activity_schema(db)
    try:
        ensure_jwt_schema(db)
        ensure_tenant_isolation_schema(db)
    except Exception:
        app.logger.exception("JWT / tenant isolation schema bootstrap failed")
    try:
        migrate_workflow_statuses(db)
        seed_workflow_master(db)
        sync_workflow_designations(db)
    except sqlite3.OperationalError:
        pass
    db.commit()
    _SCHEMA_BOOTSTRAPPED = True
    _run_startup_backup_schedule(db)


def _run_startup_backup_schedule(db=None):
    """Lightweight scheduled backup check once per process after schema is ready."""
    global _BACKUP_SCHEDULE_CHECKED
    if _BACKUP_SCHEDULE_CHECKED:
        return
    if db is None:
        db = get_db()
    try:
        ensure_backup_schema(db)
        result = run_scheduled_backup_if_due(db, DB_PATH)
        _BACKUP_SCHEDULE_CHECKED = True
        if result.get("created"):
            app.logger.info(
                "Scheduled backups created on startup: %s",
                result.get("created"),
            )
    except Exception:
        app.logger.exception("Startup backup schedule check failed")


def _create_transaction_tables(cursor):
    tables = [
        """CREATE TABLE IF NOT EXISTS material_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, request_date TEXT, item_name TEXT,
            quantity REAL, unit TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS purchase_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, request_date TEXT, item_description TEXT,
            quantity REAL, estimated_cost REAL, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS payroll_records(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT, department TEXT, total_amount REAL,
            employee_count INTEGER, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker')""",
        """CREATE TABLE IF NOT EXISTS daily_timesheets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, timesheet_date TEXT, supervisor TEXT,
            total_workers INTEGER, total_hours REAL, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS project_expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, expense_date TEXT, expense_category TEXT,
            amount REAL, description TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS head_office_expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date TEXT, expense_category TEXT, amount REAL,
            department TEXT, description TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker')""",
        """CREATE TABLE IF NOT EXISTS subcontract_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, subcontractor_id INTEGER, work_description TEXT,
            contract_amount REAL, start_date TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id))""",
        """CREATE TABLE IF NOT EXISTS boq_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, boq_date TEXT, item_code TEXT, item_description TEXT,
            quantity REAL, unit TEXT, rate REAL, amount REAL, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS dpr_entries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, report_date TEXT, prepared_by TEXT,
            work_done TEXT, manpower_count INTEGER, material_used TEXT,
            issues TEXT, progress_percent REAL, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS manager_tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, task_date TEXT, manager_name TEXT,
            action_item TEXT, priority TEXT, target_date TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS account_transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_type TEXT, project_id INTEGER, transaction_date TEXT,
            party_name TEXT, account_head TEXT, amount REAL, payment_mode TEXT,
            reference_no TEXT, tax_percent REAL, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS leave_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_name TEXT, leave_type TEXT, from_date TEXT, to_date TEXT,
            days REAL, reason TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker')""",
        """CREATE TABLE IF NOT EXISTS store_issues(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, issue_date TEXT, item_name TEXT,
            quantity REAL, unit TEXT, issued_to TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
        """CREATE TABLE IF NOT EXISTS store_receipts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER, receipt_date TEXT, item_name TEXT,
            quantity REAL, unit TEXT, supplier TEXT, remarks TEXT, created_by TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(project_id) REFERENCES projects(id))""",
    ]
    for sql in tables:
        cursor.execute(sql)


def init_db():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staff(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT,
            staff_name TEXT,
            mobile TEXT,
            email TEXT,
            department TEXT,
            designation TEXT,
            salary_type TEXT,
            salary_amount REAL,
            ot_applicable TEXT,
            working_hours REAL,
            joining_date TEXT,
            photo TEXT,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subcontractors(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcontractor_name TEXT,
            company_name TEXT,
            mobile TEXT,
            email TEXT,
            address TEXT,
            work_type TEXT,
            payment_mode TEXT,
            working_hours REAL,
            gst_number TEXT,
            id_proof TEXT,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_name TEXT UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            company_name TEXT,
            mobile TEXT,
            email TEXT,
            address TEXT,
            gst_number TEXT,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            client_id INTEGER,
            location TEXT,
            start_date TEXT,
            end_date TEXT,
            project_manager TEXT,
            budget REAL,
            status TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_code TEXT,
            worker_name TEXT,
            mobile TEXT,
            aadhaar_number TEXT,
            photo TEXT,
            worker_category TEXT,
            designation TEXT,
            salary_type TEXT,
            salary_amount REAL,
            ot_applicable TEXT,
            working_hours REAL,
            subcontractor_id INTEGER,
            project_id INTEGER,
            joining_date TEXT,
            status TEXT,
            FOREIGN KEY(subcontractor_id) REFERENCES subcontractors(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER,
            project_id INTEGER,
            attendance_date TEXT,
            in_time TEXT,
            out_time TEXT,
            break_hours REAL,
            total_hours REAL,
            ot_hours REAL,
            status TEXT,
            FOREIGN KEY(worker_id) REFERENCES workers(id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS petty_cash(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            expense_date TEXT,
            expense_type TEXT,
            amount REAL,
            payment_mode TEXT,
            remarks TEXT,
            created_by TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS salary(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER,
            month TEXT,
            total_days INTEGER,
            normal_wage REAL,
            ot_amount REAL,
            advance_deduction REAL,
            final_salary REAL,
            payment_status TEXT,
            approval_status TEXT DEFAULT 'Pending Checker',
            FOREIGN KEY(worker_id) REFERENCES workers(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS designations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            designation_name TEXT UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'Active'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_name TEXT UNIQUE,
            status TEXT DEFAULT 'Active'
        )
    """)
    _ensure_column(db, "designations", "description", "TEXT")
    _ensure_column(db, "designations", "status", "TEXT DEFAULT 'Active'")
    db.execute(
        "UPDATE designations SET status='Active' WHERE status IS NULL OR TRIM(status)=''"
    )
    ensure_trades_table(db)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_master(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_name TEXT NOT NULL,
            module_id TEXT UNIQUE NOT NULL,
            workflow_role_mapping TEXT,
            maker_designation_id INTEGER,
            checker_designation_id INTEGER,
            approver_designation_id INTEGER,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY(maker_designation_id) REFERENCES designations(id),
            FOREIGN KEY(checker_designation_id) REFERENCES designations(id),
            FOREIGN KEY(approver_designation_id) REFERENCES designations(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id TEXT NOT NULL,
            record_id INTEGER NOT NULL,
            record_table TEXT NOT NULL,
            current_stage TEXT DEFAULT 'checker',
            workflow_status TEXT DEFAULT 'pending_checker',
            maker_user_id INTEGER,
            checker_user_id INTEGER,
            approver_user_id INTEGER,
            maker_action_at TEXT,
            checker_action_at TEXT,
            approver_action_at TEXT,
            rejection_reason TEXT,
            created_by TEXT,
            created_at TEXT,
            UNIQUE(module_id, record_id, record_table)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            notification_type TEXT,
            module_id TEXT,
            record_id INTEGER,
            record_table TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approval_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            approval_request_id INTEGER,
            module_id TEXT,
            record_id INTEGER,
            record_table TEXT,
            action TEXT,
            actor_user_id INTEGER,
            actor_username TEXT,
            remarks TEXT,
            created_at TEXT,
            FOREIGN KEY(approval_request_id) REFERENCES approval_requests(id)
        )
    """)
    _ensure_column(db, "users", "designation_id", "INTEGER")
    _ensure_column(db, "users", "workflow_role", "TEXT")
    _ensure_column(db, "users", "reporting_manager", "TEXT")
    _ensure_column(db, "users", "employee_name", "TEXT")
    _ensure_column(db, "users", "department", "TEXT")
    _ensure_column(db, "users", "status", "TEXT DEFAULT 'Active'")
    _ensure_column(db, "users", "role", "TEXT")
    db.execute(
        "UPDATE users SET status='Active' WHERE status IS NULL OR TRIM(status)=''"
    )
    _ensure_column(db, "staff", "designation_id", "INTEGER")
    _ensure_column(db, "staff", "reporting_manager", "TEXT")
    _ensure_column(db, "staff", "workflow_role", "TEXT")
    _ensure_column(db, "staff", "aadhaar_number", "TEXT")
    _ensure_column(db, "staff", "pan_number", "TEXT")
    _ensure_column(db, "staff", "bank_account", "TEXT")
    _ensure_column(db, "staff", "bank_name", "TEXT")
    _ensure_column(db, "staff", "ifsc_code", "TEXT")
    _ensure_column(db, "staff", "branch_name", "TEXT")
    _ensure_column(db, "staff", "id_proof", "TEXT")
    _ensure_column(db, "staff", "aadhaar_document", "TEXT")
    _ensure_column(db, "staff", "pan_document", "TEXT")
    _ensure_column(db, "workers", "worker_code", "TEXT")
    _ensure_column(db, "workers", "aadhaar_number", "TEXT")
    _ensure_column(db, "workers", "worker_category", "TEXT DEFAULT 'Company Staff'")
    _ensure_column(db, "workers", "subcontractor_id", "INTEGER")
    _ensure_column(db, "workers", "project_id", "INTEGER")
    db.execute(
        "UPDATE workers SET worker_category='Company Staff' "
        "WHERE worker_category IS NULL OR TRIM(worker_category)=''"
    )
    _ensure_column(db, "workers", "bank_account", "TEXT")
    _ensure_column(db, "workers", "bank_name", "TEXT")
    _ensure_column(db, "workers", "ifsc_code", "TEXT")
    _ensure_column(db, "workers", "branch_name", "TEXT")
    _ensure_column(db, "workers", "pan_number", "TEXT")
    _ensure_column(db, "workers", "id_proof", "TEXT")
    _ensure_column(db, "workers", "aadhaar_document", "TEXT")
    _ensure_column(db, "workers", "pan_document", "TEXT")
    ensure_workflow_master_schema(db)
    ensure_approval_requests_schema(db)
    _ensure_column(db, "petty_cash", "approval_status", "TEXT DEFAULT 'Pending Checker'")
    _ensure_column(db, "attendance", "approval_status", "TEXT DEFAULT 'Pending Checker'")
    _ensure_column(db, "attendance", "worker_source", "TEXT DEFAULT 'worker'")
    _ensure_column(db, "attendance", "trade_id", "INTEGER")
    _ensure_column(db, "attendance", "designation_id", "INTEGER")
    _ensure_column(db, "notifications", "notification_type", "TEXT")
    _ensure_column(db, "notifications", "module_id", "TEXT")
    _ensure_column(db, "notifications", "record_id", "INTEGER")
    _ensure_column(db, "notifications", "record_table", "TEXT")
    _ensure_column(db, "approval_audit", "actor_username", "TEXT")
    _ensure_column(db, "salary", "approval_status", "TEXT DEFAULT 'Pending Checker'")
    _ensure_column(db, "clients", "client_code", "TEXT")
    _ensure_column(db, "clients", "contact_person", "TEXT")
    _ensure_column(db, "clients", "pan_number", "TEXT")
    _ensure_column(db, "projects", "project_code", "TEXT")
    _ensure_column(db, "projects", "project_type", "TEXT")
    _ensure_column(db, "projects", "gov_department", "TEXT")
    _ensure_column(db, "projects", "agreement_number", "TEXT")
    _ensure_column(db, "projects", "agreement_date", "TEXT")
    _ensure_column(db, "projects", "completion_time", "TEXT")
    _ensure_column(db, "projects", "completion_months", "REAL")
    _ensure_column(db, "projects", "completion_mode", "TEXT")
    _ensure_column(db, "projects", "quoted_amount", "REAL")
    _ensure_column(db, "projects", "security_deposit_pct", "REAL")
    _ensure_column(db, "projects", "guarantee_type", "TEXT")
    _ensure_column(db, "projects", "bank_guarantee_number", "TEXT")
    _ensure_column(db, "projects", "bank_guarantee_issued_date", "TEXT")
    _ensure_column(db, "projects", "bank_guarantee_expiry_date", "TEXT")
    _ensure_column(db, "projects", "bank_guarantee_amount", "REAL")
    _ensure_column(db, "projects", "treasury_deposit_number", "TEXT")
    _ensure_column(db, "projects", "security_deposit_amount", "REAL")
    _ensure_column(db, "projects", "security_deposit_issued_date", "TEXT")
    _ensure_column(db, "projects", "security_deposit_maturity_date", "TEXT")
    _ensure_column(db, "projects", "agreement_document", "TEXT")
    _ensure_column(db, "projects", "bank_guarantee_document", "TEXT")
    _ensure_column(db, "projects", "security_deposit_document", "TEXT")
    _ensure_column(db, "projects", "work_order_number", "TEXT")
    _ensure_column(db, "projects", "work_order_date", "TEXT")
    _ensure_column(db, "projects", "work_order_amount", "REAL")
    _ensure_column(db, "projects", "project_contact_person", "TEXT")
    _ensure_column(db, "projects", "private_client_name", "TEXT")
    _ensure_column(db, "projects", "work_order_document", "TEXT")
    _ensure_column(db, "projects", "approved_total_amount", "REAL")
    _ensure_column(db, "projects", "created_by", "TEXT")
    _ensure_column(db, "projects", "created_at", "TEXT")
    _ensure_column(db, "projects", "modified_by", "TEXT")
    _ensure_column(db, "projects", "modified_at", "TEXT")
    _ensure_column(db, "projects", "budget", "REAL")
    _ensure_column(db, "projects", "approval_status", "TEXT DEFAULT 'Approved'")
    ensure_number_sequences_table(db)
    try:
        db.execute(
            "UPDATE projects SET approval_status='Approved' WHERE approval_status IS NULL"
        )
        db.execute(
            "UPDATE projects SET approved_total_amount = budget "
            "WHERE approved_total_amount IS NULL AND budget IS NOT NULL"
        )
    except sqlite3.OperationalError:
        pass
    _ensure_column(db, "users", "staff_id", "INTEGER")
    _ensure_column(db, "subcontractors", "subcontractor_code", "TEXT")
    _ensure_column(db, "subcontractors", "date_of_birth", "TEXT")
    _ensure_column(db, "subcontractors", "id_number", "TEXT")
    _ensure_column(db, "subcontractors", "id_document", "TEXT")
    _ensure_column(db, "subcontractors", "photo", "TEXT")
    _ensure_column(db, "subcontractors", "pan_number", "TEXT")
    _ensure_column(db, "subcontractors", "pan_document", "TEXT")
    _ensure_column(db, "subcontractors", "bank_account", "TEXT")
    _ensure_column(db, "subcontractors", "bank_name", "TEXT")
    _ensure_column(db, "subcontractors", "ifsc_code", "TEXT")
    _ensure_column(db, "subcontractors", "branch_name", "TEXT")
    _ensure_column(db, "subcontractors", "rate_type", "TEXT")
    _ensure_column(db, "subcontractors", "id_proof", "TEXT")
    _ensure_column(db, "subcontractors", "vendor_id", "INTEGER")
    _ensure_column(db, "head_office_expenses", "chart_account_id", "INTEGER")
    _ensure_column(db, "staff", "date_of_birth", "TEXT")
    _ensure_column(db, "staff", "gender", "TEXT")
    _ensure_column(db, "workers", "date_of_birth", "TEXT")
    _ensure_column(db, "workers", "gender", "TEXT")
    ensure_subcontractor_rate_tables(db)
    backfill_subcontractor_codes(db)
    ensure_user_maker_assignments_table(db)
    ensure_boq_master_table(db)
    _create_transaction_tables(cursor)
    ensure_dpr_measurement_tables(db)
    ensure_petty_cash_tables(db)
    ensure_accounts_schema(db)
    ensure_security_guarantees_tables(db)
    ensure_project_guarantees_table(db)
    ensure_treasury_schema(db)
    ensure_budget_schema(db)
    ensure_profitability_schema(db)
    ensure_contract_schema(db)
    ensure_claims_schema(db)
    ensure_equipment_costing_schema(db)
    ensure_labour_productivity_schema(db)
    ensure_alert_engine_schema(db)
    ensure_document_numbering_schema(db)
    seed_default_sequences(db)
    ensure_backup_schema(db)
    ensure_cost_planning_tables(db)
    ensure_staff_hr_tables(db)
    ensure_staff_bonus_table(db)
    ensure_payroll_tables(db)
    ensure_app_settings_table(db)
    _ensure_column(db, "project_expenses", "dpr_measurement_id", "INTEGER")
    _ensure_column(db, "boq_items", "boq_id", "INTEGER")
    _ensure_column(db, "boq_items", "line_no", "INTEGER")
    _ensure_column(db, "boq_items", "created_at", "TEXT")
    _ensure_column(db, "boq_items", "modified_by", "TEXT")
    _ensure_column(db, "boq_items", "modified_at", "TEXT")
    _ensure_column(db, "boq_items", "deleted_by", "TEXT")
    _ensure_column(db, "boq_items", "deleted_at", "TEXT")
    _ensure_column(db, "boq_items", "is_deleted", "INTEGER DEFAULT 0")
    _ensure_column(db, "boq_master", "modified_by", "TEXT")
    _ensure_column(db, "boq_master", "modified_at", "TEXT")
    _ensure_column(db, "boq_master", "deleted_by", "TEXT")
    _ensure_column(db, "boq_master", "deleted_at", "TEXT")
    _ensure_column(db, "boq_master", "is_deleted", "INTEGER DEFAULT 0")
    db.commit()
    ensure_department_master(db)
    seed_workflow_master(db)
    migrate_workflow_statuses(db)
    sync_workflow_designations(db)
    db.commit()
    cursor.execute("SELECT * FROM users LIMIT 1")
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users(username, password, role, status, employee_name, department, workflow_role) "
            "VALUES(?,?,?,?,?,?,?)",
            ("admin", "admin", "Admin", "Active", "System Administrator", "Head Office", "Administrator"),
        )
        db.commit()
    if not os.environ.get("MAXEK_SKIP_DEMO_SEED"):
        seed_demo_users(db)
        seed_demo_sample_data(db)
        ensure_treasury_schema(db)
        seed_treasury_demo_data(db)
        seed_budget_demo_data(db)
        seed_profitability_demo_data(db)
        seed_contract_demo_data(db)
        seed_claims_demo_data(db)
        seed_equipment_costing_demo_data(db)
        seed_labour_productivity_demo_data(db)
        db.commit()
    try:
        _bootstrap_super_admin_runtime(db, force=True)
        db.commit()
    except Exception:
        app.logger.exception("Super admin bootstrap failed during init_db")
    try:
        generate_alerts(db)
    except Exception:
        pass


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def login_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def is_admin_user():
    if not session.get("user_id"):
        return False
    wf = (session.get("workflow_role") or "").lower()
    role = (session.get("role") or "").lower()
    if wf == "administrator" or role in ("admin", "administrator"):
        return True
    return is_admin_role(get_db(), session.get("user_id"), session.get("role"))


GUEST_NAV_SLUGS = frozenset(
    {
        "dashboard",
        "project-management",
        "subcontract-management",
        "store-procurement",
        "approvals",
    }
)
HR_NAV_SLUGS = frozenset({"dashboard", "hr-payroll", "approvals"})
ERP_ADMIN_NAV_SLUG = "erp-administration"

ERP_ADMIN_ACTIVE_ENDPOINTS = [
    "erp_admin_customers",
    "erp_admin_licenses",
    "erp_admin_subscriptions",
    "erp_admin_user_limits",
    "erp_admin_branch_limits",
    "erp_admin_storage_limits",
    "erp_admin_login_monitoring",
    "erp_admin_support_tickets",
    "erp_admin_change_requests",
    "erp_admin_settings",
    "erp_admin_audit_logs",
    "erp_admin_system_health",
]


def is_guest_user():
    return (session.get("role") or "").strip().lower() == "guest"


def is_hr_base_user():
    if is_admin_user():
        return False
    role = (session.get("role") or "").strip().lower()
    dept = (session.get("department") or "").strip()
    wf = (session.get("workflow_role") or "").strip().lower()
    return role == "user" and dept == "HR & Payroll" and wf == "maker"


def filter_nav_groups_for_user(nav_groups, guest=False, hr_base=False, super_admin=False):
    if guest:
        allowed = GUEST_NAV_SLUGS
        return [group for group in nav_groups if group.get("slug") in allowed]
    if hr_base:
        allowed = HR_NAV_SLUGS
        return [group for group in nav_groups if group.get("slug") in allowed]
    if not super_admin:
        return [group for group in nav_groups if group.get("slug") != ERP_ADMIN_NAV_SLUG]
    return nav_groups


def is_super_admin_user():
    if not session.get("user_id"):
        return False
    user = query_db("SELECT * FROM users WHERE id=?", (session["user_id"],), one=True)
    if not user:
        return False
    try:
        return _is_super_admin_row(get_db(), user)
    except Exception:
        app.logger.exception("Super admin role check failed for user_id=%s", session.get("user_id"))
        return False


def is_customer_admin_user():
    if not session.get("user_id"):
        return False
    user = query_db("SELECT * FROM users WHERE id=?", (session["user_id"],), one=True)
    if not user:
        return False
    return _is_customer_admin_row(user)


def super_admin_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        if not is_super_admin_user():
            flash("Super Admin access required.")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        if not is_admin_user():
            flash("Administrator access required.")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)

    return wrapper


MODULE_ROUTES = {
    "petty_cash": "petty_cash",
    "securities_guarantees": "securities_guarantees",
    "material_request": "material_request",
    "purchase_request": "purchase_request",
    "purchase_order": "purchase_orders",
    "payroll": "payroll",
    "daily_timesheet": "attendance",
    "monthly_staff_attendance": "attendance",
    "employee_timesheet": "employee_timesheets_form",
    "project_expenses": "project_expenses",
    "head_office_expenses": "head_office_expenses",
    "subcontract": "subcontract_request",
    "subcontract_payments": "subcontract_payments",
    "subcontractor_billing": "sub_billing_form",
    "boq": "boq_management",
    "boq_bulk": "boq_multiple_entry",
    "dpr": "dpr_entry",
    "project_creation": "projects",
    "cost_planning": "cost_planning",
    "project_documents": "project_documents",
    "manager_tool": "manager_tool",
    "account_expense": "accounts_expenses",
    "payment_voucher": "accounts_payments",
    "receipt_voucher": "accounts_receipts",
    "account_receipt": "accounts_receipts",
    "account_payment": "accounts_payments",
    "account_gst": "accounts_gst_register",
    "account_tds": "account_tds",
    "leave_request": "leave_request",
    "store_issue": "store_issue",
    "material_transfer": "material_transfer",
    "store_receipt": "store_receipt",
    "client_billing": "client_billing_form",
    "bank_payment": "treasury_payments",
    "bank_receipt": "treasury_receipts",
    "bank_guarantee": "treasury_bank_guarantees",
}


CLIENT_BILLING_NAV_ACTIVE = [
    "client_billing_register",
    "client_billing_form",
    "client_billing_reports",
    "client_billing_print",
    "client_billing_import_dpr",
    "client_billing_attachment",
    "client_billing_gst_form",
    "client_billing_gst_print",
    "client_billing_gst_generate",
]

PROJECT_PHOTOS_NAV_ACTIVE = [
    "project_photos_register",
    "project_photos_timeline",
    "project_photos_reports",
    "project_photos_report_print",
    "project_photos_file",
]

FLEET_NAV_ACTIVE = [
    "fleet_dashboard",
    "fleet_vehicles",
    "fleet_vehicle_print",
    "fleet_vehicle_documents",
    "fleet_running_log",
    "fleet_diesel_purchase",
    "fleet_diesel_stock",
    "fleet_diesel_issue",
    "fleet_document_download",
]

OFFICE_NAV_ACTIVE = [
    "office_admin",
    "office_inward",
    "office_outward",
    "office_letters",
    "office_letter_print",
    "office_quotations",
    "office_quotation_print",
    "office_po_register",
    "office_agreements",
    "office_legal",
    "office_document_download",
]

PLANT_NAV_ACTIVE = [
    "plant_dashboard",
    "plant_plants",
    "plant_asphalt_production",
    "plant_asphalt_dispatch",
    "plant_asphalt_dispatch_print",
    "plant_rmc_production",
    "plant_rmc_dispatch",
    "plant_rmc_dispatch_print",
    "plant_wetmix_production",
    "plant_precast_production",
    "precast_yard",
    "precast_yard_yards",
    "plant_precast_dispatch",
    "plant_crusher_production",
    "plant_qc",
    "plant_maintenance",
    "plant_costing",
    "plant_360",
]

PROJECTS_NAV_ACTIVE = [
    "projects_dashboard",
    "projects",
    "clients",
    "boq_management",
    "boq_multiple_entry",
    "boq_print",
    "cost_planning",
    "cost_planning_export",
    "cost_planning_print",
    "cost_planning_reports",
    "wbs_redirect",
    "dpr_entry",
    "dpr_entry_legacy",
    "dpr_client_bill_pending",
    "dpr_costing_pending",
    "dpr_client_bill_print",
    "dpr_client_bill_export",
    "project_expenses",
    *CLIENT_BILLING_NAV_ACTIVE,
    "project_photos_register",
    "project_photos_timeline",
    "project_photos_reports",
    "project_photos_report_print",
    "project_photos_file",
    "project_documents",
    "project_document_download",
    "reports",
    "workflow_audit_report",
]

HR_NAV_ACTIVE = [
    "staff",
    "employee_profile",
    "staff_bonus",
    "attendance",
    "employee_timesheets",
    "employee_timesheets_form",
    "employee_timesheets_submit",
    "employee_timesheets_print",
    "timesheet",
    "leave_request",
    "payroll",
    "payroll_payments",
    "payroll_print_slip",
    "payroll_export_register",
    "payroll_holidays",
    "salary",
]

WORKFORCE_NAV_ACTIVE = [
    "workforce_dashboard",
    *HR_NAV_ACTIVE,
    "payroll_revisions",
]

MASTERS_NAV_ACTIVE = [
    "masters_dashboard",
    "clients",
    "purchase_vendors",
    "masters_vendors",
    "treasury_equipment_costing",
    "treasury_equipment_costing_new",
    "treasury_equipment_costing_detail",
    "treasury_bank_accounts",
    "accounts_chart_of_accounts",
]

SUBCONTRACT_NAV_ACTIVE = [
    "subcontract_dashboard",
    "workers",
    "subcontractors",
    "attendance",
    "timesheet",
    "sub_billing_register",
    "sub_billing_form",
    "sub_billing_print",
    "sub_billing_abstract_print",
    "sub_billing_import_workers",
    "subcontract_payments",
]

STORE_PROCUREMENT_NAV_ACTIVE = [
    "store",
    "store_materials",
    "material_request",
    "purchase_request",
    "purchase_orders",
    "purchase_order_print",
    "purchase",
    "purchase_vendors",
    "store_receipt",
    "store_issue",
    "material_transfer",
    "inventory",
]


def _safe_scalar_count(db, sql, params=(), default=0):
    try:
        row = db.execute(sql, params).fetchone()
        if not row:
            return default
        return row[0] if isinstance(row, tuple) else row["c"]
    except Exception:
        return default


def _render_department_hub(
    title,
    section,
    stat_cards,
    modules,
    module_section_title="Modules",
    report_modules=None,
    report_section_title="Reports",
    ticket_types=None,
    ticket_section_title="Ticket types",
    command_centre_mode=False,
    **extra_template_context,
):
    breadcrumbs = f'<a href="{url_for("dashboard")}">Home</a> &gt; {section}'
    context = {
        "hub_title": title,
        "breadcrumbs_html": breadcrumbs,
        "stat_cards": stat_cards,
        "modules": modules,
        "module_section_title": module_section_title,
        "report_modules": report_modules,
        "report_section_title": report_section_title,
        "ticket_types": ticket_types,
        "ticket_section_title": ticket_section_title,
        "command_centre_mode": command_centre_mode,
    }
    context.update(extra_template_context)
    return render_template("department_dashboard.html", **context)


def _workflow_view_context(module_id, record_id, record_table, approval_status):
    db = get_db()
    user_id = session.get("user_id")
    admin = is_admin_user()
    history = get_approval_history(db, module_id, record_id, record_table)
    edit_role = get_edit_role_for_user(db, user_id, module_id, approval_status, admin)
    req = get_approval_request(db, module_id, record_id, record_table)
    audit_trail = list_audit_trail(db, record_table, record_id)
    return {
        "history": history,
        "edit_role": edit_role,
        "can_reopen": admin and approval_status == RECORD_APPROVED and req,
        "approval_id": req["id"] if req else None,
        "audit_trail": audit_trail,
    }


def _enrich_approval_items(db, items, role="checker", include_history=False):
    return [
        summarize_approval_item(db, item, role_type=role, include_history=include_history)
        for item in items
    ]


def _split_approval_items(items, role):
    pending = [i for i in items if i.get("is_pending")]
    history = [i for i in items if not i.get("is_pending")]
    return pending, history


def _history_for_record(module_id, record_id, record_table):
    return get_approval_history(get_db(), module_id, record_id, record_table)


APPROVAL_MODULE_GROUPS = {
    "purchase": (
        "purchase_request",
        "purchase_order",
        "cost_planning",
        "boq",
        "project_creation",
        "dpr",
    ),
    "store": ("material_request", "store_issue", "store_receipt", "material_transfer"),
    "timesheet": ("daily_timesheet", "monthly_staff_attendance", "employee_timesheet"),
    "payroll": ("payroll", "leave_request"),
    "payment": (
        "account_payment",
        "payment_voucher",
        "petty_cash",
        "client_billing",
        "subcontractor_billing",
        "subcontract_payments",
        "bank_guarantee",
        "bank_payment",
        "bank_receipt",
        "account_receipt",
        "receipt_voucher",
    ),
}

NAV_GROUPS = [
    {
        "label": "Dashboard",
        "icon": "fa-gauge-high",
        "slug": "dashboard",
        "items": [
            {
                "endpoint": "dashboard",
                "label": "Executive Dashboard",
                "icon": "fa-house",
                "active_endpoints": ["dashboard", "dashboard_choice_b"],
            },
            {
                "endpoint": "projects_dashboard",
                "label": "Project Dashboard",
                "icon": "fa-layer-group",
                "active_endpoints": PROJECTS_NAV_ACTIVE,
            },
            {
                "endpoint": "workforce_dashboard",
                "label": "HR Dashboard",
                "icon": "fa-users",
                "active_endpoints": ["workforce_dashboard"],
            },
            {
                "endpoint": "store",
                "label": "Store Dashboard",
                "icon": "fa-warehouse",
                "active_endpoints": STORE_PROCUREMENT_NAV_ACTIVE,
            },
            {
                "endpoint": "accounts_hub",
                "label": "Accounts Dashboard",
                "icon": "fa-landmark",
                "active_endpoints": ["accounts_hub"],
            },
            {
                "endpoint": "plant_dashboard",
                "label": "Plant Dashboard",
                "icon": "fa-industry",
                "active_endpoints": PLANT_NAV_ACTIVE,
            },
            {
                "endpoint": "qc_master",
                "label": "QC Dashboard",
                "icon": "fa-flask",
                "active_endpoints": ["qc_master", "plant_qc"],
            },
            {
                "endpoint": "approvals",
                "label": "Approval Dashboard",
                "icon": "fa-clipboard-check",
                "active_endpoints": ["approvals", "approval_detail", "approval_action"],
            },
            {
                "endpoint": "notifications",
                "label": "Notifications",
                "icon": "fa-bell",
                "active_endpoints": ["notifications"],
            },
            {
                "endpoint": "payroll_holidays",
                "label": "Calendar",
                "icon": "fa-calendar-days",
                "active_endpoints": ["payroll_holidays"],
            },
            {
                "endpoint": "dashboard",
                "label": "KPI Summary",
                "icon": "fa-chart-line",
                "anchor": "overview",
                "active_endpoints": ["dashboard"],
            },
        ],
    },
    {
        "label": "Project Management",
        "icon": "fa-diagram-project",
        "slug": "project-management",
        "items": [
            {
                "endpoint": "clients",
                "label": "Client Master",
                "icon": "fa-building-user",
                "active_endpoints": ["clients"],
            },
            {
                "endpoint": "projects",
                "label": "Project List",
                "icon": "fa-list",
                "anchor": "project-list",
                "active_endpoints": ["projects"],
            },
            {
                "endpoint": "projects",
                "label": "Create Project",
                "icon": "fa-circle-plus",
                "anchor": "add-project",
                "active_endpoints": ["projects"],
            },
            {
                "endpoint": "boq_management",
                "label": "BOQ Master",
                "icon": "fa-table-list",
                "active_endpoints": ["boq_management", "boq_multiple_entry", "boq_print"],
            },
            {
                "endpoint": "cost_planning",
                "label": "Planning",
                "icon": "fa-calendar-days",
                "active_endpoints": [
                    "cost_planning",
                    "cost_planning_export",
                    "cost_planning_print",
                    "cost_planning_reports",
                ],
            },
            {
                "endpoint": "wbs_redirect",
                "label": "WBS",
                "icon": "fa-sitemap",
                "active_endpoints": ["wbs_redirect"],
            },
            {
                "endpoint": "dpr_entry",
                "label": "DPR",
                "icon": "fa-clipboard-list",
                "active_endpoints": [
                    "dpr_entry",
                    "dpr_entry_legacy",
                    "dpr_costing_pending",
                    "dpr_client_bill_print",
                    "dpr_client_bill_export",
                ],
            },
            {
                "endpoint": "project_expenses",
                "label": "Project Costing",
                "icon": "fa-indian-rupee-sign",
                "active_endpoints": ["project_expenses"],
            },
            {
                "endpoint": "client_billing_register",
                "label": "Client Billing",
                "icon": "fa-file-invoice-dollar",
                "active_endpoints": CLIENT_BILLING_NAV_ACTIVE,
            },
            {
                "endpoint": "dpr_client_bill_pending",
                "label": "Client Bill Pending",
                "icon": "fa-hourglass-half",
                "active_endpoints": ["dpr_client_bill_pending"],
            },
            {
                "endpoint": "project_photos_register",
                "label": "Project Photos",
                "icon": "fa-camera",
                "active_endpoints": PROJECT_PHOTOS_NAV_ACTIVE,
            },
            {
                "endpoint": "project_documents",
                "label": "Project Documents",
                "icon": "fa-folder-open",
                "active_endpoints": ["project_documents", "project_document_download"],
            },
            {
                "endpoint": "reports",
                "label": "Project Reports",
                "icon": "fa-chart-pie",
                "active_endpoints": ["reports", "download_report"],
            },
        ],
    },
    {
        "label": "Engineering & SmartQTO",
        "icon": "fa-drafting-compass",
        "slug": "engineering-smartqto",
        "items": [
            {
                "endpoint": "boq_management",
                "label": "SmartQTO",
                "icon": "fa-calculator",
                "active_endpoints": ["boq_management", "boq_multiple_entry", "boq_print"],
            },
            {
                "endpoint": "boq_management",
                "label": "Quantity Tracking",
                "icon": "fa-ruler-combined",
                "active_endpoints": ["boq_management", "boq_multiple_entry", "boq_print"],
            },
            {
                "endpoint": "dpr_client_bill_pending",
                "label": "Measurement Book",
                "icon": "fa-book",
                "active_endpoints": ["dpr_client_bill_pending", "dpr_client_bill_print", "dpr_client_bill_export"],
            },
            {
                "endpoint": "cost_planning",
                "label": "Rate Analysis",
                "icon": "fa-chart-line",
                "active_endpoints": [
                    "cost_planning",
                    "cost_planning_export",
                    "cost_planning_print",
                    "cost_planning_reports",
                ],
            },
            {
                "endpoint": "project_documents",
                "label": "Drawing Register",
                "icon": "fa-compass-drafting",
                "active_endpoints": ["project_documents", "project_document_download"],
            },
            {
                "endpoint": "project_documents",
                "label": "Technical Documents",
                "icon": "fa-file-lines",
                "active_endpoints": ["project_documents", "project_document_download"],
            },
            {
                "endpoint": "reports",
                "label": "Engineering Reports",
                "icon": "fa-file-excel",
                "active_endpoints": ["reports", "cost_planning_reports", "download_report"],
            },
        ],
    },
    {
        "label": "HR & Payroll",
        "icon": "fa-users",
        "slug": "hr-payroll",
        "active_endpoints": WORKFORCE_NAV_ACTIVE,
        "items": [
            {
                "endpoint": "staff",
                "label": "Employee Master",
                "icon": "fa-user-tie",
                "active_endpoints": ["staff", "employee_profile", "staff_bonus"],
            },
            {
                "endpoint": "attendance",
                "label": "Attendance",
                "icon": "fa-calendar-check",
                "active_endpoints": ["attendance"],
            },
            {
                "endpoint": "timesheet",
                "label": "Daily Timesheet",
                "icon": "fa-clock",
                "active_endpoints": ["timesheet"],
            },
            {
                "endpoint": "employee_timesheets",
                "label": "Monthly Timesheet",
                "icon": "fa-table",
                "active_endpoints": [
                    "employee_timesheets",
                    "employee_timesheets_form",
                    "employee_timesheets_submit",
                    "employee_timesheets_print",
                ],
            },
            {
                "endpoint": "leave_request",
                "label": "Leave",
                "icon": "fa-plane-departure",
                "active_endpoints": ["leave_request"],
            },
            {
                "endpoint": "payroll",
                "label": "Payroll",
                "icon": "fa-money-check-dollar",
                "active_endpoints": [
                    "payroll",
                    "payroll_payments",
                    "payroll_print_slip",
                    "payroll_export_register",
                ],
            },
            {
                "endpoint": "salary",
                "label": "Salary Processing",
                "icon": "fa-wallet",
                "active_endpoints": ["salary"],
            },
            {
                "endpoint": "payroll_revisions",
                "label": "Salary Revision",
                "icon": "fa-chart-line",
                "active_endpoints": ["payroll_revisions"],
            },
            {
                "endpoint": "reports",
                "label": "HR Reports",
                "icon": "fa-file-excel",
                "active_endpoints": ["reports", "download_report"],
            },
        ],
    },
    {
        "label": "Subcontract Management",
        "icon": "fa-people-group",
        "slug": "subcontract-management",
        "items": [
            {
                "endpoint": "subcontract_dashboard",
                "label": "Subcontract Dashboard",
                "icon": "fa-gauge-high",
                "active_endpoints": SUBCONTRACT_NAV_ACTIVE,
            },
            {
                "endpoint": "subcontractors",
                "label": "Subcontractor Creation",
                "icon": "fa-user-plus",
                "anchor": "add-subcontractor",
                "active_endpoints": ["subcontractors"],
            },
            {
                "endpoint": "subcontractors",
                "label": "Subcontractor List",
                "icon": "fa-list",
                "anchor": "subcontractor-list",
                "active_endpoints": ["subcontractors"],
            },
            {
                "endpoint": "workers",
                "label": "Workers",
                "icon": "fa-hard-hat",
                "anchor": "add-worker",
                "active_endpoints": ["workers"],
            },
            {
                "endpoint": "attendance",
                "label": "Worker Attendance",
                "icon": "fa-calendar-check",
                "anchor": "add-attendance",
                "query": {"nav": "subcontract"},
                "active_endpoints": ["attendance"],
            },
            {
                "endpoint": "timesheet",
                "label": "Worker Timesheet",
                "icon": "fa-clock",
                "query": {"nav": "subcontract"},
                "active_endpoints": ["timesheet"],
            },
            {
                "endpoint": "sub_billing_register",
                "label": "Subcontract Bills",
                "icon": "fa-file-invoice",
                "active_endpoints": [
                    "sub_billing_register",
                    "sub_billing_form",
                    "sub_billing_print",
                    "sub_billing_abstract_print",
                    "sub_billing_import_workers",
                ],
            },
            {
                "endpoint": "subcontract_payments",
                "label": "Subcontract Payments",
                "icon": "fa-money-bill-transfer",
                "active_endpoints": ["subcontract_payments"],
            },
        ],
    },
    {
        "label": "Store & Procurement",
        "icon": "fa-warehouse",
        "slug": "store-procurement",
        "items": [
            {
                "endpoint": "purchase_vendors",
                "label": "Vendor Master",
                "icon": "fa-truck-field",
                "anchor": "add-vendor",
                "active_endpoints": ["purchase_vendors", "masters_vendors"],
            },
            {
                "endpoint": "store_materials",
                "label": "Material Master",
                "icon": "fa-boxes-stacked",
                "active_endpoints": ["store_materials"],
            },
            {
                "endpoint": "material_request",
                "label": "MR",
                "icon": "fa-clipboard-list",
                "active_endpoints": ["material_request"],
            },
            {
                "endpoint": "purchase_request",
                "label": "PR",
                "icon": "fa-file-circle-plus",
                "active_endpoints": ["purchase_request"],
            },
            {
                "endpoint": "purchase_orders",
                "label": "PO",
                "icon": "fa-file-invoice",
                "active_endpoints": ["purchase_orders", "purchase_order_print", "purchase"],
            },
            {
                "endpoint": "store_receipt",
                "label": "GRN",
                "icon": "fa-dolly",
                "query": {"new": 1},
                "anchor": "grn-form",
                "active_endpoints": ["store_receipt"],
            },
            {
                "endpoint": "store_receipt",
                "label": "Store Receipt",
                "icon": "fa-arrow-right-to-bracket",
                "anchor": "grn-register",
                "active_endpoints": ["store_receipt"],
            },
            {
                "endpoint": "store_issue",
                "label": "Store Issue",
                "icon": "fa-arrow-right-from-bracket",
                "active_endpoints": ["store_issue"],
            },
            {
                "endpoint": "material_transfer",
                "label": "Transfer",
                "icon": "fa-truck-ramp-box",
                "active_endpoints": ["material_transfer"],
            },
            {
                "endpoint": "inventory",
                "label": "Inventory",
                "icon": "fa-boxes-stacked",
                "active_endpoints": ["inventory"],
            },
            {
                "endpoint": "inventory",
                "label": "Store Reports",
                "icon": "fa-chart-column",
                "active_endpoints": ["inventory"],
            },
        ],
    },
    {
        "label": "Accounts & Finance",
        "icon": "fa-landmark",
        "slug": "accounts-finance",
        "items": [
            {
                "endpoint": "accounts_hub",
                "label": "Accounts Hub",
                "icon": "fa-gauge-high",
                "active_endpoints": ["accounts_hub"],
            },
            {
                "endpoint": "accounts_chart_of_accounts",
                "label": "Chart of Accounts",
                "icon": "fa-sitemap",
                "active_endpoints": ["accounts_chart_of_accounts"],
            },
            {
                "endpoint": "treasury_bank_accounts",
                "label": "Bank Master",
                "icon": "fa-building-columns",
                "active_endpoints": ["treasury_bank_accounts"],
            },
            {
                "endpoint": "petty_cash",
                "label": "Petty Cash",
                "icon": "fa-wallet",
                "active_endpoints": ["petty_cash"],
            },
            {
                "endpoint": "head_office_expenses",
                "label": "Daily Expenses",
                "icon": "fa-file-invoice",
                "active_endpoints": ["head_office_expenses", "accounts_expenses"],
            },
            {
                "endpoint": "accounts_expenses",
                "label": "Expense / Purchase",
                "icon": "fa-receipt",
                "active_endpoints": ["accounts_expenses"],
            },
            {
                "endpoint": "accounts_receipts",
                "label": "Receipts",
                "icon": "fa-hand-holding-dollar",
                "active_endpoints": ["accounts_receipts"],
            },
            {
                "endpoint": "accounts_payments",
                "label": "Payments",
                "icon": "fa-money-bill-transfer",
                "active_endpoints": ["accounts_payments"],
            },
            {
                "endpoint": "accounts_cash_book_v2",
                "label": "Cash Book",
                "icon": "fa-book",
                "active_endpoints": ["accounts_cash_book_v2", "cash_book"],
            },
            {
                "endpoint": "accounts_bank_book_v2",
                "label": "Bank Book",
                "icon": "fa-building-columns",
                "active_endpoints": ["accounts_bank_book_v2", "bank_book"],
            },
            {
                "endpoint": "accounts_day_book",
                "label": "Day Book",
                "icon": "fa-calendar-day",
                "active_endpoints": ["accounts_day_book"],
            },
            {
                "endpoint": "accounts_general_ledger",
                "label": "General Ledger",
                "icon": "fa-book-open",
                "active_endpoints": ["accounts_general_ledger", "ledger"],
            },
            {
                "endpoint": "accounts_vendor_ledger",
                "label": "Vendor Ledger",
                "icon": "fa-truck",
                "active_endpoints": ["accounts_vendor_ledger"],
            },
            {
                "endpoint": "accounts_client_ledger",
                "label": "Client Ledger",
                "icon": "fa-users",
                "active_endpoints": ["accounts_client_ledger"],
            },
            {
                "endpoint": "accounts_gst_register",
                "label": "GST",
                "icon": "fa-percent",
                "active_endpoints": ["accounts_gst_register", "account_gst"],
            },
            {
                "endpoint": "account_tds",
                "label": "TDS",
                "icon": "fa-file-contract",
                "active_endpoints": ["account_tds", "accounts_tds_register"],
            },
            {
                "endpoint": "accounts_pf_register",
                "label": "PF Register",
                "icon": "fa-building",
                "active_endpoints": ["accounts_pf_register"],
            },
            {
                "endpoint": "accounts_esi_register",
                "label": "ESI Register",
                "icon": "fa-heart-pulse",
                "active_endpoints": ["accounts_esi_register"],
            },
            {
                "endpoint": "treasury_hub",
                "label": "Bank & Treasury",
                "icon": "fa-vault",
                "active_endpoints": [
                    "treasury_hub",
                    "treasury_bank_accounts",
                    "treasury_payments",
                    "treasury_receipts",
                    "treasury_cheques",
                    "treasury_cheque_new",
                    "treasury_cheque_detail",
                    "treasury_cheque_status",
                    "treasury_budget_control",
                    "treasury_budget_control_project",
                    "treasury_budget_control_edit",
                    "treasury_project_profitability",
                    "treasury_contract_management",
                    "treasury_contract_management_new",
                    "treasury_contract_management_detail",
                    "treasury_contract_management_project",
                    "treasury_equipment_costing",
                    "treasury_labour_productivity",
                    "treasury_labour_productivity_new",
                    "treasury_labour_productivity_detail",
                    "treasury_labour_productivity_project",
                    "treasury_document_vault",
                    "treasury_cash_flow_forecast",
                    "treasury_command_center",
                    "treasury_alert_engine",
                    "treasury_alert_engine_settings",
                    "treasury_alert_engine_refresh",
                    "treasury_alert_engine_dismiss",
                    "treasury_bank_guarantees",
                ],
            },
            {
                "endpoint": "securities_guarantees",
                "label": "Securities Register",
                "icon": "fa-shield-halved",
                "active_endpoints": ["securities_guarantees", "securities_guarantees_export"],
            },
            {
                "endpoint": "treasury_bank_guarantees",
                "label": "Treasury Bank Guarantees",
                "icon": "fa-file-shield",
                "active_endpoints": ["treasury_bank_guarantees"],
            },
            {
                "endpoint": "treasury_cheques",
                "label": "Cheque Management",
                "icon": "fa-money-check",
                "active_endpoints": [
                    "treasury_cheques",
                    "treasury_cheque_new",
                    "treasury_cheque_detail",
                    "treasury_cheque_status",
                ],
            },
            {
                "endpoint": "accounts_reports",
                "label": "Financial Reports",
                "icon": "fa-chart-line",
                "active_endpoints": ["accounts_reports", "accounts_tally_export"],
            },
        ],
    },
    {
        "label": "Plant & Machinery",
        "icon": "fa-industry",
        "slug": "plant-machinery",
        "items": [
            {
                "endpoint": "plant_dashboard",
                "label": "Plant Dashboard",
                "icon": "fa-gauge-high",
                "active_endpoints": PLANT_NAV_ACTIVE,
            },
            {
                "endpoint": "fleet_dashboard",
                "label": "Fleet Dashboard",
                "icon": "fa-truck",
                "active_endpoints": FLEET_NAV_ACTIVE,
            },
            {
                "endpoint": "plant_plants",
                "label": "Plant Master",
                "icon": "fa-industry",
                "active_endpoints": ["plant_plants"],
            },
            {
                "endpoint": "treasury_equipment_costing",
                "label": "Equipment Master",
                "icon": "fa-screwdriver-wrench",
                "active_endpoints": [
                    "treasury_equipment_costing",
                    "treasury_equipment_costing_new",
                    "treasury_equipment_costing_detail",
                ],
            },
            {
                "endpoint": "fleet_vehicles",
                "label": "Vehicle Master",
                "icon": "fa-car",
                "active_endpoints": ["fleet_vehicles", "fleet_vehicle_print"],
            },
            {
                "endpoint": "fleet_vehicle_documents",
                "label": "Vehicle Documents",
                "icon": "fa-file-contract",
                "active_endpoints": ["fleet_vehicle_documents", "fleet_document_download"],
            },
            {
                "endpoint": "fleet_running_log",
                "label": "Running Log",
                "icon": "fa-road",
                "active_endpoints": ["fleet_running_log"],
            },
            {
                "endpoint": "fleet_diesel_purchase",
                "label": "Diesel Purchase",
                "icon": "fa-gas-pump",
                "active_endpoints": ["fleet_diesel_purchase"],
            },
            {
                "endpoint": "fleet_diesel_stock",
                "label": "Diesel Stock",
                "icon": "fa-oil-can",
                "active_endpoints": ["fleet_diesel_stock"],
            },
            {
                "endpoint": "fleet_diesel_issue",
                "label": "Diesel Issue",
                "icon": "fa-droplet",
                "active_endpoints": ["fleet_diesel_issue"],
            },
            {
                "endpoint": "plant_asphalt_production",
                "label": "Asphalt Production",
                "icon": "fa-flask",
                "active_endpoints": [
                    "plant_asphalt_production",
                    "plant_asphalt_dispatch",
                    "plant_asphalt_dispatch_print",
                ],
            },
            {
                "endpoint": "plant_rmc_production",
                "label": "RMC Production",
                "icon": "fa-cubes",
                "active_endpoints": [
                    "plant_rmc_production",
                    "plant_rmc_dispatch",
                    "plant_rmc_dispatch_print",
                ],
            },
            {
                "endpoint": "plant_wetmix_production",
                "label": "Wet Mix Production",
                "icon": "fa-layer-group",
                "active_endpoints": ["plant_wetmix_production"],
            },
            {
                "endpoint": "precast_yard",
                "label": "Precast Yard",
                "icon": "fa-border-all",
                "active_endpoints": [
                    "precast_yard",
                    "precast_yard_yards",
                    "plant_precast_production",
                    "plant_precast_dispatch",
                ],
            },
            {
                "endpoint": "plant_crusher_production",
                "label": "Crusher Production",
                "icon": "fa-hammer",
                "active_endpoints": ["plant_crusher_production"],
            },
            {
                "endpoint": "plant_maintenance",
                "label": "Maintenance",
                "icon": "fa-screwdriver-wrench",
                "active_endpoints": ["plant_maintenance"],
            },
            {
                "endpoint": "plant_costing",
                "label": "Production Costing",
                "icon": "fa-indian-rupee-sign",
                "active_endpoints": ["plant_costing"],
            },
            {
                "endpoint": "plant_360",
                "label": "Plant 360",
                "icon": "fa-circle-nodes",
                "active_endpoints": ["plant_360"],
            },
        ],
    },
    {
        "label": "QC",
        "icon": "fa-flask",
        "slug": "qc",
        "items": [
            {
                "endpoint": "qc_master",
                "label": "QC Master",
                "icon": "fa-flask",
                "active_endpoints": ["qc_master"],
            },
            {
                "endpoint": "qc_master",
                "label": "Material Testing",
                "icon": "fa-vial",
                "active_endpoints": ["qc_master"],
            },
            {
                "endpoint": "plant_qc",
                "label": "Plant QC Tests",
                "icon": "fa-microscope",
                "active_endpoints": ["plant_qc"],
            },
            {
                "endpoint": "plant_qc",
                "label": "Inspection",
                "icon": "fa-magnifying-glass",
                "active_endpoints": ["plant_qc"],
            },
            {
                "endpoint": "qc_master",
                "label": "Test Reports",
                "icon": "fa-file-medical",
                "active_endpoints": ["qc_master"],
            },
            {
                "endpoint": "qc_master",
                "label": "NCR",
                "icon": "fa-triangle-exclamation",
                "active_endpoints": ["qc_master"],
            },
            {
                "endpoint": "reports",
                "label": "QC Reports",
                "icon": "fa-chart-column",
                "active_endpoints": ["reports", "download_report"],
            },
        ],
    },
    {
        "label": "Administration & Compliance",
        "icon": "fa-building",
        "slug": "admin-compliance",
        "active_endpoints": OFFICE_NAV_ACTIVE
        + [
            "corporate_dms",
            "corporate_dms_file",
            "corporate_dms_download",
        ],
        "items": [
            {
                "endpoint": "office_admin",
                "label": "Office Dashboard",
                "icon": "fa-gauge-high",
                "active_endpoints": ["office_admin"],
            },
            {
                "endpoint": "office_inward",
                "label": "Letter In / Inward Register",
                "icon": "fa-inbox",
                "active_endpoints": ["office_inward"],
            },
            {
                "endpoint": "office_outward",
                "label": "Letter Out / Outward Register",
                "icon": "fa-paper-plane",
                "active_endpoints": ["office_outward"],
            },
            {
                "endpoint": "office_letters",
                "label": "Letter Preparation / General Letters",
                "icon": "fa-envelope-open-text",
                "active_endpoints": ["office_letters", "office_letter_print"],
            },
            {
                "endpoint": "office_quotations",
                "label": "Quotations",
                "icon": "fa-file-signature",
                "active_endpoints": ["office_quotations", "office_quotation_print"],
            },
            {
                "endpoint": "office_po_register",
                "label": "PO Register",
                "icon": "fa-file-invoice",
                "active_endpoints": ["office_po_register"],
            },
            {
                "endpoint": "office_agreements",
                "label": "Agreements",
                "icon": "fa-handshake",
                "active_endpoints": ["office_agreements"],
            },
            {
                "endpoint": "office_legal",
                "label": "Legal Documents",
                "icon": "fa-scale-balanced",
                "active_endpoints": ["office_legal"],
            },
            {
                "endpoint": "corporate_dms",
                "label": "Corporate DMS",
                "icon": "fa-folder-tree",
                "active_endpoints": [
                    "corporate_dms",
                    "corporate_dms_file",
                    "corporate_dms_download",
                ],
            },
            {
                "endpoint": "corporate_dms",
                "label": "Compliance",
                "icon": "fa-shield-halved",
                "active_endpoints": [
                    "corporate_dms",
                    "corporate_dms_file",
                    "corporate_dms_download",
                ],
            },
        ],
    },
    {
        "label": "Approvals",
        "icon": "fa-clipboard-check",
        "slug": "approvals",
        "items": [
            {
                "endpoint": "approvals",
                "label": "Workflow Center",
                "icon": "fa-clipboard-list",
                "active_endpoints": ["approvals", "approval_detail", "approval_action"],
            },
            {
                "endpoint": "approvals",
                "label": "Purchase Approvals",
                "icon": "fa-cart-shopping",
                "query": {"module": "purchase"},
                "active_endpoints": ["approvals", "approval_detail", "approval_action"],
            },
            {
                "endpoint": "approvals",
                "label": "Store Approvals",
                "icon": "fa-warehouse",
                "query": {"module": "store"},
                "active_endpoints": ["approvals", "approval_detail", "approval_action"],
            },
            {
                "endpoint": "approvals",
                "label": "Timesheet Approvals",
                "icon": "fa-clock",
                "query": {"module": "timesheet"},
                "active_endpoints": ["approvals", "approval_detail", "approval_action"],
            },
            {
                "endpoint": "approvals",
                "label": "Payroll Approvals",
                "icon": "fa-money-check-dollar",
                "query": {"module": "payroll"},
                "active_endpoints": ["approvals", "approval_detail", "approval_action"],
            },
            {
                "endpoint": "approvals",
                "label": "Payment Approvals",
                "icon": "fa-money-bill-transfer",
                "query": {"module": "payment"},
                "active_endpoints": ["approvals", "approval_detail", "approval_action"],
            },
        ],
    },
    {
        "label": "Reports & Analytics",
        "icon": "fa-chart-line",
        "slug": "reports-analytics",
        "items": [
            {
                "endpoint": "corporate_reports_hub",
                "label": "Corporate Reports Registry",
                "icon": "fa-file-lines",
                "active_endpoints": [
                    "corporate_reports_hub",
                    "corporate_report_stub_print",
                    "corporate_report_export",
                    "corporate_report_verify",
                ],
            },
            {
                "endpoint": "reports",
                "label": "HR & Workforce Reports",
                "icon": "fa-users",
                "active_endpoints": ["reports", "download_report"],
            },
            {
                "endpoint": "reports",
                "label": "Project Reports",
                "icon": "fa-diagram-project",
                "active_endpoints": ["reports", "download_report"],
            },
            {
                "endpoint": "workflow_audit_report",
                "label": "Workflow Audit",
                "icon": "fa-route",
                "active_endpoints": ["workflow_audit_report"],
            },
            {
                "endpoint": "accounts_reports",
                "label": "Financial Reports",
                "icon": "fa-landmark",
                "active_endpoints": ["accounts_reports", "accounts_tally_export"],
            },
            {
                "endpoint": "client_billing_reports",
                "label": "Client Billing Reports",
                "icon": "fa-file-invoice-dollar",
                "active_endpoints": ["client_billing_reports"],
            },
            {
                "endpoint": "project_photos_reports",
                "label": "Project Photo Reports",
                "icon": "fa-camera",
                "active_endpoints": ["project_photos_reports", "project_photos_report_print"],
            },
            {
                "endpoint": "cost_planning_reports",
                "label": "Cost Planning Reports",
                "icon": "fa-chart-pie",
                "active_endpoints": ["cost_planning_reports"],
            },
        ],
    },
    {
        "label": "Settings",
        "icon": "fa-gear",
        "slug": "settings",
        "items": [
            {
                "endpoint": "user_settings",
                "label": "Users",
                "icon": "fa-user-gear",
                "active_endpoints": ["user_settings"],
            },
            {
                "endpoint": "user_management",
                "label": "Roles & Permissions",
                "icon": "fa-user-shield",
                "active_endpoints": ["user_management"],
            },
            {
                "endpoint": "workflow_settings",
                "label": "Workflow Settings",
                "icon": "fa-diagram-project",
                "active_endpoints": ["workflow_settings", "workflow_matrix"],
            },
            {
                "endpoint": "settings",
                "label": "Company Settings",
                "icon": "fa-building",
                "active_endpoints": ["settings"],
            },
            {
                "endpoint": "company_master",
                "label": "Company Master",
                "icon": "fa-building-columns",
                "active_endpoints": ["company_master", "company_document_download"],
            },
            {
                "endpoint": "corporate_template_master",
                "label": "Corporate Template Master",
                "icon": "fa-palette",
                "active_endpoints": [
                    "corporate_template_master",
                    "corporate_template_asset",
                ],
            },
            {
                "endpoint": "user_activity_monitor",
                "label": "Activity Monitor",
                "icon": "fa-chart-line",
                "active_endpoints": ["user_activity_monitor"],
            },
            {
                "endpoint": "customer_support_tickets",
                "label": "Support Tickets",
                "icon": "fa-life-ring",
                "active_endpoints": ["customer_support_tickets", "erp_admin_support_tickets"],
            },
        ],
    },
    {
        "label": "ERP Administration",
        "icon": "fa-shield-halved",
        "slug": ERP_ADMIN_NAV_SLUG,
        "items": [
            {
                "endpoint": "erp_admin_customers",
                "label": "Customer Master",
                "icon": "fa-building-user",
                "active_endpoints": ERP_ADMIN_ACTIVE_ENDPOINTS,
            },
            {
                "endpoint": "erp_admin_licenses",
                "label": "License Master",
                "icon": "fa-key",
                "active_endpoints": ERP_ADMIN_ACTIVE_ENDPOINTS,
            },
            {
                "endpoint": "erp_admin_subscriptions",
                "label": "Subscription Management",
                "icon": "fa-credit-card",
                "active_endpoints": ERP_ADMIN_ACTIVE_ENDPOINTS,
            },
            {
                "endpoint": "erp_admin_user_limits",
                "label": "User Limits",
                "icon": "fa-users-gear",
                "active_endpoints": ERP_ADMIN_ACTIVE_ENDPOINTS,
            },
            {
                "endpoint": "erp_admin_branch_limits",
                "label": "Branch Limits",
                "icon": "fa-code-branch",
                "active_endpoints": ERP_ADMIN_ACTIVE_ENDPOINTS,
            },
            {
                "endpoint": "erp_admin_storage_limits",
                "label": "Storage Limits",
                "icon": "fa-hard-drive",
                "active_endpoints": ERP_ADMIN_ACTIVE_ENDPOINTS,
            },
            {
                "endpoint": "erp_admin_login_monitoring",
                "label": "Login Monitoring",
                "icon": "fa-right-to-bracket",
                "active_endpoints": ERP_ADMIN_ACTIVE_ENDPOINTS,
            },
            {
                "endpoint": "erp_admin_support_tickets",
                "label": "Support Tickets",
                "icon": "fa-life-ring",
                "active_endpoints": ERP_ADMIN_ACTIVE_ENDPOINTS + ["customer_support_tickets"],
            },
            {
                "endpoint": "erp_admin_change_requests",
                "label": "Change Requests",
                "icon": "fa-code-pull-request",
                "active_endpoints": ERP_ADMIN_ACTIVE_ENDPOINTS,
            },
            {
                "endpoint": "erp_admin_settings",
                "label": "ERP Settings",
                "icon": "fa-sliders",
                "active_endpoints": ERP_ADMIN_ACTIVE_ENDPOINTS,
            },
            {
                "endpoint": "erp_admin_audit_logs",
                "label": "Audit Logs",
                "icon": "fa-list-check",
                "active_endpoints": ERP_ADMIN_ACTIVE_ENDPOINTS,
            },
            {
                "endpoint": "erp_admin_system_health",
                "label": "System Health",
                "icon": "fa-heart-pulse",
                "active_endpoints": ERP_ADMIN_ACTIVE_ENDPOINTS,
            },
        ],
    },
]

NAV_ITEMS = [
    item
    for group in NAV_GROUPS
    for item in (
        group.get("items")
        or [
            {
                "endpoint": group.get("endpoint"),
                "label": group["label"],
                "icon": group["icon"],
                "active_endpoints": group.get("active_endpoints", []),
            }
        ]
    )
]


def get_nav_group_by_slug(slug):
    legacy_slug_map = {
        "workforce": "hr-payroll",
        "hr": "hr-payroll",
        "hr_payroll": "hr-payroll",
        "projects": "project-management",
        "engineering": "engineering-smartqto",
        "engineering-qto": "engineering-smartqto",
        "subcontract": "subcontract-management",
        "office": "admin-compliance",
        "administration": "admin-compliance",
        "fleet": "plant-machinery",
        "masters": "store-procurement",
        "accounts": "accounts-finance",
        "plant": "plant-machinery",
    }
    slug = legacy_slug_map.get(slug, slug)
    for group in NAV_GROUPS:
        if group.get("slug") == slug:
            return group
    return None


def active_nav_group(endpoint, nav_slug=None):
    if endpoint == "department_portal" and nav_slug:
        portal = get_department_portal(nav_slug)
        if portal:
            return portal_menu_as_nav_group(portal)
    if endpoint in ("dashboard", "dashboard_choice_b"):
        return get_nav_group_by_slug("dashboard")
    if endpoint in ("purchase_vendors", "masters_vendors", "masters_dashboard"):
        return get_nav_group_by_slug("store-procurement")
    if endpoint == "clients":
        return get_nav_group_by_slug("project-management")
    if endpoint in FLEET_NAV_ACTIVE or endpoint in PLANT_NAV_ACTIVE:
        plant_group = get_nav_group_by_slug("plant-machinery")
        if plant_group:
            return plant_group
    if endpoint in ("approvals", "approval_action", "approval_detail"):
        return get_nav_group_by_slug("approvals")
    if endpoint == "department_hub" and nav_slug:
        group = get_nav_group_by_slug(nav_slug)
        if group:
            return group
    nav_slug = nav_slug or request.args.get("nav")
    if nav_slug == "subcontract":
        nav_slug = "subcontract-management"
    if nav_slug:
        group = get_nav_group_by_slug(nav_slug)
        if group:
            for item in group.get("items", []):
                if endpoint in item.get("active_endpoints", []):
                    return group
            if endpoint in group.get("active_endpoints", []):
                return group
    module_key = request.args.get("module", "").strip()
    if module_key and endpoint in ("approvals", "approval_action", "approval_detail"):
        return get_nav_group_by_slug("approvals")
    for group in NAV_GROUPS:
        for item in group.get("items", []):
            if endpoint in item.get("active_endpoints", []):
                if endpoint in SUBCONTRACT_NAV_ACTIVE and request.args.get("nav") == "subcontract":
                    return get_nav_group_by_slug("subcontract-management")
                if endpoint in ("attendance", "timesheet") and request.args.get("nav") == "subcontract":
                    continue
                return group
        if endpoint in group.get("active_endpoints", []):
            return group
    return get_nav_group_by_slug("dashboard")


PRECAST_MODULE_ENDPOINTS = frozenset({
    "precast_yard",
    "precast_yard_yards",
    "plant_precast_production",
    "plant_precast_dispatch",
})


def module_sub_toolbar_for_request(endpoint):
    if endpoint in PRECAST_MODULE_ENDPOINTS:
        return PRECAST_YARD_SUBTOOLBAR, "Precast Yard"
    if endpoint == "plant_qc" and request.args.get("source") == "Precast":
        return PRECAST_YARD_SUBTOOLBAR, "Precast Yard"
    return None, None


PRO_SHELL_EXCLUDED_ENDPOINTS = frozenset({"login", "logout"})


def endpoint_uses_pro_shell(endpoint):
    """Use the pro sidebar shell on authenticated HTML pages (not login/print)."""
    if not session.get("user_id"):
        return False
    ep = endpoint or ""
    if ep in PRO_SHELL_EXCLUDED_ENDPOINTS:
        return False
    if ep.endswith("_print"):
        return False
    return True


def get_approval_widgets():
    if not session.get("user_id"):
        return {"maker": 0, "checker": 0, "approver": 0}
    return get_pending_counts(get_db(), session.get("user_id"), is_admin_user())


@app.context_processor
def inject_maxek_layout():
    if not session.get("user_id"):
        return {}
    username = session.get("username") or "Administrator"
    user_id = session.get("user_id")
    db = get_db()
    try:
        widgets = get_pending_counts(db, user_id, is_admin_user())
    except sqlite3.OperationalError:
        ensure_runtime_schema(db, force=True)
        try:
            widgets = get_pending_counts(db, user_id, is_admin_user())
        except sqlite3.OperationalError:
            widgets = {"maker": 0, "checker": 0, "approver": 0}
    try:
        dashboard_counters = get_dashboard_counters(db, user_id, username, is_admin_user())
    except sqlite3.OperationalError:
        ensure_runtime_schema(db, force=True)
        try:
            dashboard_counters = get_dashboard_counters(db, user_id, username, is_admin_user())
        except sqlite3.OperationalError:
            dashboard_counters = {
                "maker": {
                    "pending_verification": 0,
                    "pending_approval": 0,
                    "approved": 0,
                    "rejected": 0,
                },
                "checker": {
                    "pending_verification": 0,
                    "verified_today": 0,
                    "rejected_today": 0,
                },
                "approver": {
                    "pending_approval": 0,
                    "approved_today": 0,
                    "rejected_today": 0,
                },
            }
    try:
        approval_summary = get_approval_summary(db)
    except sqlite3.OperationalError:
        approval_summary = {}
    try:
        workflow_caps = user_workflow_capabilities(db, user_id, is_admin_user())
    except sqlite3.OperationalError:
        workflow_caps = {}
    try:
        notifs = get_notifications(db, user_id, limit=10, unread_only=True)
    except sqlite3.OperationalError:
        notifs = []
    try:
        system_alert_counts = get_alert_counts_by_severity(db)
    except Exception:
        ensure_runtime_schema(db, force=True)
        try:
            system_alert_counts = get_alert_counts_by_severity(db)
        except Exception:
            system_alert_counts = {"info": 0, "warning": 0, "critical": 0, "total": 0}
    approval_total = widgets["maker"] + widgets["checker"] + widgets["approver"]
    nav_slug = (request.view_args or {}).get("slug") if request.endpoint in ("department_hub", "department_portal") else None
    current_nav_group = active_nav_group(request.endpoint, nav_slug)
    on_department_portal = request.endpoint == "department_portal"
    guest_user = is_guest_user()
    hr_base_user = is_hr_base_user()
    super_admin = is_super_admin_user()
    visible_nav_groups = filter_nav_groups_for_user(
        NAV_GROUPS, guest=guest_user, hr_base=hr_base_user, super_admin=super_admin
    )
    tab_perm_full_access = is_admin_user() or super_admin or guest_user
    if user_id and not tab_perm_full_access:
        visible_nav_groups = apply_user_tab_permissions_to_nav_groups(
            db,
            user_id,
            visible_nav_groups,
            full_access=False,
            department_slug_for_nav=nav_slug_to_permission_department,
        )
    try:
        app_timezone = get_app_setting(get_db(), "timezone", "Asia/Kolkata")
    except sqlite3.OperationalError:
        app_timezone = "Asia/Kolkata"
    module_sub_toolbar, module_sub_toolbar_label = module_sub_toolbar_for_request(request.endpoint)
    main_toolbar = build_main_toolbar(visible_nav_groups)
    active_toolbar_slug = resolve_active_toolbar_slug(
        request.endpoint, nav_slug, visible_nav_groups
    )
    if on_department_portal and nav_slug:
        dept_portal = get_department_portal(nav_slug)
        if dept_portal:
            active_toolbar_slug = dept_portal["slug"]
            portal_menu = enrich_portal_menu_open_counts(
                db, get_department_portal_menu(dept_portal["slug"])
            )
            portal_menu = filter_portal_menu_for_user(
                db,
                user_id,
                dept_portal["slug"],
                portal_menu,
                full_access=is_admin_user() or super_admin or guest_user,
            )
            dept_portal_view = dict(dept_portal)
            dept_portal_view["menu"] = portal_menu
            current_nav_group = portal_menu_as_nav_group(dept_portal_view)
    if active_toolbar_slug in VIRTUAL_TOOLBAR_ENTRIES:
        virtual = VIRTUAL_TOOLBAR_ENTRIES[active_toolbar_slug]
        current_nav_group = {
            "slug": active_toolbar_slug,
            "label": virtual["label"],
            "icon": virtual.get("icon", "fa-folder"),
            "items": virtual.get("items", []),
        }
    elif not current_nav_group:
        current_nav_group = get_nav_group_by_slug(active_toolbar_slug or "dashboard") or {
            "slug": "dashboard",
            "label": "Dashboard",
            "icon": "fa-gauge-high",
            "items": [],
        }
    sub_toolbar_items = [] if on_department_portal else filter_sub_toolbar_items(current_nav_group)
    sub_toolbar_sections = None
    if not on_department_portal and active_toolbar_slug == "accounts-finance":
        sub_toolbar_sections = accounts_sub_toolbar_sections()
        sub_toolbar_items = [
            item
            for section in sub_toolbar_sections
            for item in section.get("items", [])
        ]
    try:
        live_badges = get_live_badge_counts(db, user_id, is_admin_user())
    except Exception:
        live_badges = {}
    for item in sub_toolbar_items:
        badge_val = badge_for_endpoint(item.get("endpoint", ""), live_badges)
        if badge_val:
            item["badge"] = badge_val
    company_id = session.get("company_id")
    context_branches = list_context_branches(db, company_id)
    branch_options = (
        [b["name"] for b in context_branches]
        if context_branches
        else ["Head Office", "Chennai Site", "Walajabad Unit"]
    )
    header_projects = list_context_projects(db, session.get("branch_id"))
    if not header_projects:
        try:
            project_rows = db.execute(
                "SELECT id, project_name FROM projects WHERE status != 'Closed' ORDER BY project_name LIMIT 50"
            ).fetchall()
            header_projects = [
                {"id": row["id"], "name": row["project_name"]} for row in project_rows
            ]
        except sqlite3.OperationalError:
            header_projects = []
    context_companies = list_context_companies(db, session.get("customer_id"))
    company_display_name = (
        session.get("customer_name")
        or session.get("company_code")
        or "MAXEK Technologies"
    )
    status_strip = {
        "server_status": "healthy",
        "server_label": "Online",
        "database_status": "healthy",
        "database_label": "Connected",
        "user_label": f"User: {session.get('employee_name') or username}",
        "version": APP_VERSION_LABEL,
        "last_backup": format_app_datetime(),
    }
    try:
        ui_theme = normalize_ui_theme(load_dashboard_preferences(db, user_id).get("ui_theme"))
    except Exception:
        ui_theme = normalize_ui_theme(None)
    username_display = session.get("employee_name") or (
        username.title() if username.islower() else username
    )
    use_pro_shell = endpoint_uses_pro_shell(request.endpoint)
    pro_shell_dashboard = request.endpoint in ("dashboard", "dashboard_choice_b")
    role_label = session.get("role") or "Owner"
    try:
        if is_super_admin_user():
            role_label = "Owner"
    except Exception:
        pass
    return {
        "nav_groups": visible_nav_groups,
        "nav_items": [
            item
            for group in visible_nav_groups
            for item in (
                group.get("items")
                or [
                    {
                        "endpoint": group.get("endpoint"),
                        "label": group["label"],
                        "icon": group["icon"],
                        "active_endpoints": group.get("active_endpoints", []),
                    }
                ]
            )
        ],
        "current_nav_group": current_nav_group,
        "module_sub_toolbar": module_sub_toolbar,
        "module_sub_toolbar_label": module_sub_toolbar_label,
        "is_guest_user": guest_user,
        "is_hr_base_user": hr_base_user,
        "is_super_admin_user": super_admin,
        "company_code": session.get("company_code"),
        "timestamp": format_app_datetime(),
        "app_timezone": app_timezone,
        "admin_initial": username[0].upper(),
        "branches": branch_options,
        "selected_branch": session.get("branch", branch_options[0] if branch_options else "Head Office"),
        "context_companies": context_companies,
        "selected_company_id": company_id,
        "live_badge_counts": live_badges,
        "notification_count": len(notifs) or approval_total,
        "approval_total": approval_total,
        "approval_widgets": widgets,
        "dashboard_counters": dashboard_counters,
        "approval_summary": approval_summary,
        "workflow_caps": workflow_caps,
        "user_notifications": notifs,
        "system_alert_counts": system_alert_counts,
        "display_status": display_status,
        "maker_status_message": maker_status_message,
        "format_decimal_hours": format_decimal_hours,
        "safe_url_for": safe_url_for,
        "hide_module_nav": use_pro_shell or on_department_portal or request.endpoint in ("dashboard", "dashboard_choice_b"),
        "department_portals": get_department_portals(),
        "main_toolbar": main_toolbar,
        "active_toolbar_slug": active_toolbar_slug,
        "sub_toolbar_items": sub_toolbar_items,
        "sub_toolbar_sections": sub_toolbar_sections,
        "quick_panel_links": quick_panel_for_slug(active_toolbar_slug),
        "global_search_categories": GLOBAL_SEARCH_CATEGORIES,
        "help_center_items": HELP_CENTER_ITEMS,
        "company_display_name": company_display_name,
        "header_projects": header_projects,
        "selected_project_id": session.get("selected_project_id"),
        "status_strip": status_strip,
        "hide_quick_panel": use_pro_shell or request.endpoint in ("login", "dashboard", "dashboard_choice_b", "department_portal"),
        "hide_action_panel": use_pro_shell or request.endpoint in ("login", "dashboard", "dashboard_choice_b", "department_portal"),
        "ui_theme": ui_theme,
        "use_pro_shell": use_pro_shell,
        "pro_shell_dashboard": pro_shell_dashboard,
        "pro_shell_department_portal": on_department_portal,
        "welcome_name": username_display,
        "command_centre_branch": session.get("branch", branch_options[0] if branch_options else "Head Office"),
        "command_user_role": role_label,
        "dashboard_shell_favorites": DASHBOARD_SHELL_FAVORITES,
        "dashboard_shell_nav_groups": DASHBOARD_SHELL_NAV_GROUPS,
    }


@app.route("/")
def index():
    return redirect(url_for("login"))


_LOGIN_REMEMBER_MAX_AGE = 365 * 24 * 60 * 60


def _login_remember_cookies(username, company_code):
    """Persist last login identity for pre-fill on next visit."""
    resp = make_response(redirect(url_for("dashboard")))
    resp.set_cookie(
        "maxek_last_username",
        username,
        max_age=_LOGIN_REMEMBER_MAX_AGE,
        httponly=False,
        samesite="Lax",
    )
    resp.set_cookie(
        "maxek_last_company_code",
        company_code or "",
        max_age=_LOGIN_REMEMBER_MAX_AGE,
        httponly=False,
        samesite="Lax",
    )
    return resp


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    remembered_user = request.cookies.get("maxek_last_username", "").strip()
    default_company_code = request.cookies.get("maxek_last_company_code", "").strip()
    if request.method == "POST":
        company_code = request.form.get("company_code", "").strip() or None
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        remember = request.form.get("remember") == "on"
        user = authenticate_user(get_db(), username, password, company_code=company_code)
        if user:
            session.clear()
            user_id = get_user_id(user)
            session["user_id"] = user_id
            session["username"] = user["username"]
            session["role"] = _row_val(user, "role")
            session["workflow_role"] = _row_val(user, "workflow_role")
            session["department"] = _row_val(user, "department")
            session["employee_name"] = get_user_display_name(user)
            customer_id = user["customer_id"] if "customer_id" in user.keys() else None
            session["customer_id"] = customer_id
            resolved_company_code = company_code
            if customer_id:
                try:
                    customer = get_customer_by_id(get_db(), customer_id)
                except Exception:
                    app.logger.exception("Failed to load customer for session (customer_id=%s)", customer_id)
                    customer = None
                if customer:
                    session["company_code"] = customer["customer_code"]
                    session["customer_name"] = customer["company_name"]
                    resolved_company_code = customer["customer_code"]
            elif company_code:
                session["company_code"] = company_code.upper()
                resolved_company_code = company_code.upper()
            try:
                login_session_id = log_login(
                    get_db(),
                    user_id=user_id,
                    employee_name=session.get("employee_name"),
                    role=session.get("role"),
                    ip_address=(
                        (request.headers.get("X-Forwarded-For") or request.remote_addr or "")
                        .split(",")[0]
                        .strip()
                    ),
                    user_agent=request.headers.get("User-Agent"),
                )
                session["login_session_id"] = login_session_id
            except Exception:
                app.logger.exception("Failed to log user login session")
            if remember:
                session.permanent = True
                app.permanent_session_lifetime = timedelta(days=30)
            try:
                ctx = load_user_context(get_db(), user_id)
                apply_context_to_session(session, ctx)
                prefs = load_dashboard_preferences(get_db(), user_id)
                if prefs.get("role_profile") == "default":
                    inferred = infer_role_profile(session.get("department"), session.get("role"))
                    save_dashboard_preferences(get_db(), user_id, role_profile=inferred)
            except Exception:
                app.logger.exception("Failed to restore user work context")
            return _login_remember_cookies(username, resolved_company_code or "")
        flash("Invalid username or password, or account is inactive.")
    return render_template(
        "login.html",
        app_version=APP_VERSION,
        remembered_user=remembered_user,
        default_company_code=default_company_code,
        remembered_usernames=[remembered_user] if remembered_user else [],
    )


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = query_db("SELECT * FROM users WHERE username=?", (username,), one=True)
        if user:
            flash("Password reset request received. Contact your system administrator.")
        else:
            flash("If that username exists, an administrator will reset your password.")
        return redirect(url_for("login"))
    return render_template("forgot_password.html", app_version=APP_VERSION)


@app.route("/logout")
def logout():
    try:
        log_logout(get_db(), session.get("login_session_id"))
    except Exception:
        app.logger.exception("Failed to log user logout session")
    session.clear()
    return redirect(url_for("login"))


COMMAND_CENTRE_CARD_META = [
    {
        "slug": "accounts",
        "card_label": "Accounts",
        "category": "FINANCE",
        "description": "Ledger, vouchers, TDS/GST & financial reports",
        "icon": "fa-landmark",
        "accent": "#3b82f6",
    },
    {
        "slug": "projects",
        "card_label": "Project Management",
        "category": "OPERATIONS",
        "description": "Projects, BOQ, DPR, billing & progress tracking",
        "icon": "fa-diagram-project",
        "accent": "#8b5cf6",
    },
    {
        "slug": "store",
        "card_label": "Store",
        "category": "INVENTORY",
        "description": "Material requests, receipts, issues & stock control",
        "icon": "fa-warehouse",
        "accent": "#f59e0b",
    },
    {
        "slug": "hr-payroll",
        "card_label": "HR and Payroll",
        "category": "PEOPLE",
        "description": "Employees, attendance, leave & payroll processing",
        "icon": "fa-users",
        "accent": "#ec4899",
    },
    {
        "slug": "vehicle",
        "card_label": "Vehicle",
        "category": "FLEET",
        "description": "Vehicle master, running log, fuel & document tracking",
        "icon": "fa-truck",
        "accent": "#0ea5e9",
    },
    {
        "slug": "planning-wbs",
        "card_label": "Planning and Costing",
        "category": "ENGINEERING",
        "description": "WBS, BOQ, rate analysis & cost planning",
        "icon": "fa-drafting-compass",
        "accent": "#14b8a6",
    },
    {
        "slug": "plant-machinery",
        "card_label": "Plant",
        "category": "PLANT",
        "description": "Asphalt, RMC, crusher, wet mix & plant operations",
        "icon": "fa-industry",
        "accent": "#10b981",
    },
    {
        "slug": "engineering",
        "card_label": "Planning & WBS",
        "category": "ENGINEERING",
        "description": "BOQ, WBS, rate analysis, quantity tracking & drawings",
        "icon": "fa-drafting-compass",
        "accent": "#14b8a6",
    },
    {
        "slug": "administration",
        "card_label": "Administration",
        "category": "CORPORATE",
        "description": "Office registers, agreements, legal docs & compliance",
        "icon": "fa-building",
        "accent": "#64748b",
    },
    {
        "slug": "qc",
        "card_label": "QC",
        "category": "QUALITY",
        "description": "Material testing, plant QC, inspections & NCR",
        "icon": "fa-flask",
        "accent": "#06b6d4",
    },
    {
        "slug": "subcontract",
        "card_label": "Subcontractor",
        "category": "CONTRACTS",
        "description": "Subcontractors, worker billing & payments",
        "icon": "fa-people-group",
        "accent": "#ef4444",
    },
]

DEPARTMENT_ACCENT_EXTRAS = {
    "consultancy": "#0f766e",
    "procurement": "#f97316",
    "qc": "#06b6d4",
    "vehicle": "#0ea5e9",
    "plant-machinery": "#10b981",
    "planning-wbs": "#14b8a6",
    "tender": "#a855f7",
    "reports": "#6366f1",
    "mechanical": "#10b981",
    "engineering": "#14b8a6",
    "administration": "#64748b",
}


def get_department_accent(slug):
    slug = resolve_department_portal_slug(slug)
    for meta in COMMAND_CENTRE_CARD_META:
        if meta["slug"] == slug:
            return meta["accent"]
    return DEPARTMENT_ACCENT_EXTRAS.get(slug, "#e30613")


def get_department_portals():
    return [
        {
            "slug": "consultancy",
            "card_label": "Consultancy ERP",
            "title": "MAXEK CONSULTANCY ERP",
            "icon": "fa-briefcase",
            "nav_slug": "project-management",
            "summary_title": "Consultancy Workflow Summary",
            "quick_tabs": [
                {"endpoint": "clients", "label": "Clients"},
                {"endpoint": "projects", "label": "Projects", "anchor": "project-list"},
                {"endpoint": "boq_management", "label": "QTO / BOQ"},
                {"endpoint": "cost_planning", "label": "Estimation"},
                {"endpoint": "client_billing_register", "label": "Billing"},
            ],
            "menu": [
                {"endpoint": "clients", "label": "Client & Enquiry Register", "icon": "fa-address-book", "active_endpoints": ["clients"]},
                {"endpoint": "projects", "label": "Project Assignment Master", "icon": "fa-folder-tree", "anchor": "project-list", "active_endpoints": ["projects"]},
                {"endpoint": "projects", "label": "Tender Review", "icon": "fa-file-signature", "anchor": "project-list", "active_endpoints": ["projects"]},
                {"endpoint": "project_documents", "label": "Drawing & Document Register", "icon": "fa-compass-drafting", "active_endpoints": ["project_documents", "project_document_download"]},
                {"endpoint": "boq_management", "label": "Quantity Take-Off / BOQ", "icon": "fa-table-list", "active_endpoints": ["boq_management", "boq_multiple_entry", "boq_print"]},
                {"endpoint": "cost_planning", "label": "Rate Analysis & Estimate", "icon": "fa-calculator", "active_endpoints": ["cost_planning", "cost_planning_reports"]},
                {"endpoint": "wbs_redirect", "label": "Planning & Cash Flow", "icon": "fa-timeline", "active_endpoints": ["wbs_redirect"]},
                {"endpoint": "client_billing_register", "label": "Consultancy Billing", "icon": "fa-file-invoice-dollar", "active_endpoints": CLIENT_BILLING_NAV_ACTIVE},
                {"endpoint": "reports", "label": "Corporate MIS Reports", "icon": "fa-chart-pie", "active_endpoints": ["reports", "download_report"]},
            ],
        },
        {
            "slug": "projects",
            "card_label": "Projects",
            "title": "PROJECT DEPARTMENT",
            "icon": "fa-diagram-project",
            "nav_slug": "project-management",
            "summary_title": "Project Dashboard Summary",
            "quick_tabs": [
                {"endpoint": "projects", "label": "Active Projects", "anchor": "project-list"},
                {"endpoint": "boq_management", "label": "BOQ"},
                {"endpoint": "dpr_entry", "label": "DPR"},
                {"endpoint": "client_billing_register", "label": "Billing"},
                {"endpoint": "dpr_entry", "label": "Progress"},
            ],
            "menu": [
                {"endpoint": "projects", "label": "Project Master", "icon": "fa-folder-tree", "active_endpoints": ["projects"]},
                {"endpoint": "boq_management", "label": "BOQ Management", "icon": "fa-table-list", "active_endpoints": ["boq_management", "boq_multiple_entry", "boq_print"]},
                {"endpoint": "dpr_entry", "label": "DPR Entry", "icon": "fa-clipboard-list", "active_endpoints": ["dpr_entry", "dpr_entry_legacy"]},
                {"endpoint": "client_billing_register", "label": "Client Billing", "icon": "fa-file-invoice-dollar", "active_endpoints": CLIENT_BILLING_NAV_ACTIVE},
                {"endpoint": "wbs_redirect", "label": "WBS Planning", "icon": "fa-sitemap", "active_endpoints": ["wbs_redirect"]},
                {"endpoint": "cost_planning", "label": "Costing", "icon": "fa-indian-rupee-sign", "active_endpoints": ["cost_planning", "project_expenses"]},
                {"endpoint": "reports", "label": "Project Reports", "icon": "fa-chart-pie", "active_endpoints": ["reports", "download_report"]},
            ],
        },
        {
            "slug": "accounts",
            "card_label": "Accounts",
            "title": "ACCOUNTS DEPARTMENT",
            "icon": "fa-landmark",
            "nav_slug": "accounts-finance",
            "summary_title": "Accounts Summary",
            "menu": [
                {"endpoint": "petty_cash", "label": "Petty Cash", "icon": "fa-wallet", "active_endpoints": ["petty_cash"]},
                {"endpoint": "accounts_expenses", "label": "Expenses", "icon": "fa-receipt", "active_endpoints": ["accounts_expenses", "head_office_expenses"]},
                {"endpoint": "accounts_receipts", "label": "Receipts", "icon": "fa-hand-holding-dollar", "active_endpoints": ["accounts_receipts"]},
                {"endpoint": "accounts_gst_register", "label": "GST", "icon": "fa-percent", "active_endpoints": ["accounts_gst_register", "account_gst"]},
                {"endpoint": "account_tds", "label": "TDS", "icon": "fa-file-contract", "active_endpoints": ["account_tds", "accounts_tds_register"]},
                {"endpoint": "accounts_expenses", "label": "Vendor Bills", "icon": "fa-file-invoice", "active_endpoints": ["accounts_expenses"]},
                {"endpoint": "accounts_bank_book_v2", "label": "Bank Book", "icon": "fa-building-columns", "active_endpoints": ["accounts_bank_book_v2", "bank_book"]},
                {"endpoint": "accounts_cash_book_v2", "label": "Cash Book", "icon": "fa-book", "active_endpoints": ["accounts_cash_book_v2", "cash_book"]},
                {"endpoint": "accounts_reports", "label": "Reports", "icon": "fa-chart-line", "active_endpoints": ["accounts_reports"]},
            ],
        },
        {
            "slug": "store",
            "card_label": "Store",
            "title": "STORE DEPARTMENT",
            "icon": "fa-warehouse",
            "nav_slug": "store-procurement",
            "summary_title": "Store Summary",
            "menu": [
                {"endpoint": "material_request", "label": "Material Request", "icon": "fa-clipboard-list", "active_endpoints": ["material_request"]},
                {"endpoint": "store_receipt", "label": "Store Receipt", "icon": "fa-arrow-right-to-bracket", "active_endpoints": ["store_receipt"]},
                {"endpoint": "store_issue", "label": "Store Issue", "icon": "fa-arrow-right-from-bracket", "active_endpoints": ["store_issue"]},
                {"endpoint": "purchase_request", "label": "Purchase Request", "icon": "fa-file-circle-plus", "active_endpoints": ["purchase_request"]},
                {"endpoint": "inventory", "label": "Stock Register", "icon": "fa-boxes-stacked", "active_endpoints": ["inventory"]},
                {"endpoint": "inventory", "label": "Inventory Reports", "icon": "fa-chart-column", "active_endpoints": ["inventory"]},
            ],
        },
        {
            "slug": "hr-payroll",
            "card_label": "HR and Payroll",
            "title": "HR & PAYROLL DEPARTMENT",
            "icon": "fa-users",
            "nav_slug": "hr-payroll",
            "summary_title": "Workforce Summary",
            "menu": [
                {"endpoint": "staff", "label": "Employee Master", "icon": "fa-user-tie", "active_endpoints": ["staff", "employee_profile"]},
                {"endpoint": "attendance", "label": "Attendance", "icon": "fa-calendar-check", "active_endpoints": ["attendance"]},
                {"endpoint": "timesheet", "label": "Timesheet", "icon": "fa-clock", "active_endpoints": ["timesheet", "employee_timesheets"]},
                {"endpoint": "payroll", "label": "Payroll", "icon": "fa-money-check-dollar", "active_endpoints": ["payroll", "payroll_payments"]},
                {"endpoint": "salary", "label": "Salary Payment", "icon": "fa-wallet", "active_endpoints": ["salary"]},
                {"endpoint": "leave_request", "label": "Leave Management", "icon": "fa-plane-departure", "active_endpoints": ["leave_request"]},
                {"endpoint": "accounts_pf_register", "label": "PF / ESI", "icon": "fa-building", "active_endpoints": ["accounts_pf_register", "accounts_esi_register"]},
                {"endpoint": "reports", "label": "Reports", "icon": "fa-file-excel", "active_endpoints": ["reports", "download_report"]},
            ],
        },
        {
            "slug": "vehicle",
            "card_label": "Vehicle",
            "title": "VEHICLE & FLEET DEPARTMENT",
            "icon": "fa-truck",
            "nav_slug": "fleet-mechanical",
            "summary_title": "Fleet Summary",
            "menu": [
                {"endpoint": "fleet_vehicles", "label": "Vehicle Master", "icon": "fa-car", "active_endpoints": ["fleet_vehicles", "fleet_vehicle_print"]},
                {"endpoint": "fleet_vehicle_documents", "label": "Vehicle Documents", "icon": "fa-id-card", "active_endpoints": ["fleet_vehicle_documents", "fleet_document_download"]},
                {"endpoint": "fleet_running_log", "label": "Running Log", "icon": "fa-road", "active_endpoints": ["fleet_running_log"]},
                {"endpoint": "fleet_diesel_purchase", "label": "Diesel Purchase", "icon": "fa-gas-pump", "active_endpoints": ["fleet_diesel_purchase"]},
                {"endpoint": "fleet_diesel_stock", "label": "Diesel Stock", "icon": "fa-oil-can", "active_endpoints": ["fleet_diesel_stock"]},
                {"endpoint": "fleet_diesel_issue", "label": "Diesel Issue", "icon": "fa-arrow-right-from-bracket", "active_endpoints": ["fleet_diesel_issue"]},
            ],
        },
        {
            "slug": "mechanical",
            "card_label": "Mechanical",
            "title": "MECHANICAL DEPARTMENT",
            "icon": "fa-gears",
            "nav_slug": "plant-machinery",
            "summary_title": "Plant & Equipment Summary",
            "menu": [
                {"endpoint": "plant_plants", "label": "Plant Master", "icon": "fa-industry", "active_endpoints": ["plant_plants"]},
                {"endpoint": "plant_maintenance", "label": "Maintenance", "icon": "fa-screwdriver-wrench", "active_endpoints": ["plant_maintenance"]},
                {"endpoint": "fleet_diesel_stock", "label": "Fuel & Diesel", "icon": "fa-gas-pump", "active_endpoints": ["fleet_diesel_stock"]},
                {"endpoint": "plant_maintenance", "label": "Breakdown Log", "icon": "fa-triangle-exclamation", "active_endpoints": ["plant_maintenance"]},
                {"endpoint": "plant_dashboard", "label": "Equipment Dashboard", "icon": "fa-gauge-high", "active_endpoints": ["plant_dashboard"]},
                {"endpoint": "reports", "label": "Reports", "icon": "fa-chart-line", "active_endpoints": ["reports", "download_report"]},
            ],
        },
        {
            "slug": "engineering",
            "card_label": "Engineering",
            "title": "ENGINEERING DEPARTMENT",
            "icon": "fa-drafting-compass",
            "nav_slug": "engineering-smartqto",
            "summary_title": "Engineering & SmartQTO Summary",
            "menu": [
                {"endpoint": "boq_management", "label": "SmartQTO / BOQ", "icon": "fa-calculator", "active_endpoints": ["boq_management", "boq_multiple_entry", "boq_print"]},
                {"endpoint": "dpr_client_bill_pending", "label": "Measurement Book", "icon": "fa-book", "active_endpoints": ["dpr_client_bill_pending", "dpr_client_bill_print"]},
                {"endpoint": "cost_planning", "label": "Rate Analysis", "icon": "fa-chart-line", "active_endpoints": ["cost_planning", "cost_planning_reports"]},
                {"endpoint": "project_documents", "label": "Drawing Register", "icon": "fa-compass-drafting", "active_endpoints": ["project_documents", "project_document_download"]},
                {"endpoint": "reports", "label": "Engineering Reports", "icon": "fa-file-excel", "active_endpoints": ["reports", "download_report"]},
            ],
        },
        {
            "slug": "subcontract",
            "card_label": "Subcontractor",
            "title": "SUBCONTRACT DEPARTMENT",
            "icon": "fa-people-group",
            "nav_slug": "subcontract-management",
            "summary_title": "Subcontract Summary",
            "menu": [
                {"endpoint": "subcontract_dashboard", "label": "Subcontract Dashboard", "icon": "fa-gauge-high", "active_endpoints": ["subcontract_dashboard"]},
                {"endpoint": "subcontractors", "label": "Subcontractors", "icon": "fa-user-plus", "active_endpoints": ["subcontractors"]},
                {"endpoint": "workers", "label": "Workers", "icon": "fa-hard-hat", "active_endpoints": ["workers"]},
                {"endpoint": "sub_billing_register", "label": "Subcontract Bills", "icon": "fa-file-invoice", "active_endpoints": ["sub_billing_register", "sub_billing_form"]},
                {"endpoint": "subcontract_payments", "label": "Payments", "icon": "fa-money-bill-transfer", "active_endpoints": ["subcontract_payments"]},
            ],
        },
        {
            "slug": "procurement",
            "card_label": "Procurement",
            "title": "PROCUREMENT DEPARTMENT",
            "icon": "fa-cart-shopping",
            "nav_slug": "store-procurement",
            "summary_title": "Procurement Summary",
            "menu": [
                {"endpoint": "purchase_vendors", "label": "Vendor Master", "icon": "fa-truck-field", "active_endpoints": ["purchase_vendors", "masters_vendors"]},
                {"endpoint": "purchase_request", "label": "Purchase Request", "icon": "fa-file-circle-plus", "active_endpoints": ["purchase_request"]},
                {"endpoint": "purchase_orders", "label": "Purchase Orders", "icon": "fa-file-invoice", "active_endpoints": ["purchase_orders", "purchase"]},
                {"endpoint": "store_receipt", "label": "GRN / Receipt", "icon": "fa-dolly", "active_endpoints": ["store_receipt"]},
                {"endpoint": "purchase_orders", "label": "Vendor Bills", "icon": "fa-file-invoice-dollar", "active_endpoints": ["purchase_orders"]},
                {"endpoint": "inventory", "label": "Reports", "icon": "fa-chart-column", "active_endpoints": ["inventory"]},
            ],
        },
        {
            "slug": "qc",
            "card_label": "QC",
            "title": "QUALITY CONTROL DEPARTMENT",
            "icon": "fa-flask",
            "nav_slug": "qc",
            "summary_title": "QC Summary",
            "menu": [
                {"endpoint": "qc_master", "label": "QC Test Master", "icon": "fa-vial", "active_endpoints": ["qc_master"]},
                {"endpoint": "plant_qc", "label": "Plant QC", "icon": "fa-flask", "active_endpoints": ["plant_qc"]},
                {"endpoint": "reports", "label": "QC Reports", "icon": "fa-file-excel", "active_endpoints": ["reports", "download_report"]},
            ],
        },
        {
            "slug": "tender",
            "card_label": "Tender",
            "title": "TENDER DEPARTMENT",
            "icon": "fa-file-signature",
            "nav_slug": "project-management",
            "summary_title": "Tender Summary",
            "menu": [
                {"endpoint": "projects", "label": "Tender Register", "icon": "fa-list", "anchor": "project-list", "active_endpoints": ["projects"]},
                {"endpoint": "projects", "label": "Bid Tracking", "icon": "fa-chart-line", "anchor": "project-list", "active_endpoints": ["projects"]},
                {"endpoint": "boq_management", "label": "BOQ / Estimation", "icon": "fa-calculator", "active_endpoints": ["boq_management"]},
                {"endpoint": "reports", "label": "Tender Reports", "icon": "fa-file-excel", "active_endpoints": ["reports", "download_report"]},
            ],
        },
        {
            "slug": "reports",
            "card_label": "Reports",
            "title": "REPORTS DEPARTMENT",
            "icon": "fa-chart-pie",
            "nav_slug": "dashboard",
            "summary_title": "Reports Hub",
            "menu": [
                {"endpoint": "reports", "label": "Operational Reports", "icon": "fa-file-excel", "active_endpoints": ["reports", "download_report"]},
                {"endpoint": "accounts_reports", "label": "Financial Reports", "icon": "fa-chart-line", "active_endpoints": ["accounts_reports"]},
                {"endpoint": "cost_planning_reports", "label": "Project Reports", "icon": "fa-diagram-project", "active_endpoints": ["cost_planning_reports"]},
                {"endpoint": "inventory", "label": "Store Reports", "icon": "fa-warehouse", "active_endpoints": ["inventory"]},
                {"endpoint": "payroll", "label": "Payroll Reports", "icon": "fa-money-check-dollar", "active_endpoints": ["payroll"]},
            ],
        },
        {
            "slug": "administration",
            "card_label": "Administration & Compliance",
            "title": "ADMINISTRATION & COMPLIANCE",
            "icon": "fa-building",
            "nav_slug": "admin-compliance",
            "summary_title": "Office & compliance summary",
            "menu": [
                {"endpoint": "office_admin", "label": "Office Dashboard", "icon": "fa-gauge-high", "active_endpoints": ["office_admin"]},
                {"endpoint": "office_inward", "label": "Letter In / Inward Register", "icon": "fa-inbox", "active_endpoints": ["office_inward"]},
                {"endpoint": "office_outward", "label": "Letter Out / Outward Register", "icon": "fa-paper-plane", "active_endpoints": ["office_outward"]},
                {"endpoint": "office_letters", "label": "Letter Preparation", "icon": "fa-envelope-open-text", "active_endpoints": ["office_letters", "office_letter_print"]},
                {"endpoint": "office_agreements", "label": "Agreements", "icon": "fa-handshake", "active_endpoints": ["office_agreements"]},
                {"endpoint": "office_legal", "label": "Legal Documents", "icon": "fa-scale-balanced", "active_endpoints": ["office_legal"]},
                {"endpoint": "corporate_dms", "label": "Corporate DMS", "icon": "fa-folder-tree", "active_endpoints": ["corporate_dms", "corporate_dms_file", "corporate_dms_download"]},
                {"endpoint": "fleet_dashboard", "label": "Fleet Dashboard", "icon": "fa-truck", "active_endpoints": ["fleet_dashboard"]},
            ],
        },
    ]


def get_department_portal(slug):
    slug = resolve_department_portal_slug(slug)
    for portal in get_department_portals():
        if portal["slug"] == slug:
            enriched = dict(portal)
            enriched["accent"] = get_department_accent(slug)
            enriched["menu"] = get_department_portal_menu(slug)
            return enriched
    return None


def department_portal_stat_cards(slug, db):
    return get_workspace_standard_stat_cards(db, slug)


@app.route("/dept/<slug>")
@login_required
def department_portal(slug):
    portal = get_department_portal(slug)
    if not portal:
        flash("Department not found.")
        return redirect(url_for("dashboard"))
    if is_guest_user() and portal["nav_slug"] not in GUEST_NAV_SLUGS:
        flash("This module is not available for demo guest accounts.")
        return redirect(url_for("dashboard"))
    if is_hr_base_user() and portal["nav_slug"] not in HR_NAV_SLUGS:
        flash("This module is not available for HR base accounts.")
        return redirect(url_for("dashboard"))
    db = get_db()
    stat_cards = department_portal_stat_cards(portal["slug"], db)
    menu = enrich_portal_menu_open_counts(db, get_department_portal_menu(portal["slug"]))
    menu = filter_portal_menu_for_user(
        db,
        session.get("user_id"),
        portal["slug"],
        menu,
        full_access=is_admin_user() or is_super_admin_user() or is_guest_user(),
    )
    portal_view = dict(portal)
    portal_view["menu"] = menu
    return render_template(
        "department_workspace.html",
        portal=portal_view,
        stat_cards=stat_cards,
        page_title=portal_view.get("title") or portal_view.get("card_label"),
        report_modules=build_workspace_report_modules(portal["slug"]),
        ticket_types=get_workspace_ticket_types(db, portal["slug"]),
        **_command_centre_sidebar_context(db, active_slug=portal["slug"]),
    )


@app.route("/department/<slug>")
@login_required
def department_hub(slug):
    portal = get_department_portal(slug)
    if portal:
        return redirect(url_for("department_portal", slug=portal["slug"]))
    if is_guest_user() and slug not in GUEST_NAV_SLUGS:
        flash("This module is not available for demo guest accounts.")
        return redirect(url_for("dashboard"))
    if is_hr_base_user() and slug not in HR_NAV_SLUGS:
        flash("This module is not available for HR base accounts.")
        return redirect(url_for("dashboard"))
    group = get_nav_group_by_slug(slug)
    if not group:
        flash("Department not found.")
        return redirect(url_for("dashboard"))
    items = group.get("items") or []
    if items:
        first = items[0]
        try:
            target = url_for(first["endpoint"])
            if first.get("anchor"):
                target = f"{target}#{first['anchor']}"
            return redirect(target)
        except Exception:
            app.logger.exception(
                "Department hub redirect failed for slug=%s endpoint=%s",
                slug,
                first.get("endpoint"),
            )
            flash("That module is not available yet. Select a module from the toolbar when ready.")
    return render_template("department_hub.html", nav_group=group)


def build_system_rows(user_id=None, admin=False, limit=5):
    """Dashboard workflow preview — user-scoped pending only, minimal fields."""
    db = get_db()
    if user_id is None:
        user_id = session.get("user_id")
    if not admin:
        admin = is_admin_user()
    rows = []
    for item in get_user_workflow_preview(db, user_id, admin, limit=limit):
        rows.append(
            {
                "ref": item["reference_no"],
                "label": item["module_name"],
                "date_created": item["date"],
                "submitted_by": item["maker_name"],
                "status": "pending",
                "status_label": item["status_label"],
                "action_url": url_for("approval_detail", approval_id=item["approval_id"]),
                "action_label": "View",
            }
        )
    return rows


def get_dashboard_live_tables(db):
    """Live dashboard table rows for home page widgets."""
    live = {
        "dpr_today": [],
        "recent_material_requests": [],
        "payroll_summary": [],
        "pending_approvals": [],
        "project_status": [],
    }

    try:
        rows = db.execute(
            """
            SELECT m.id, m.report_date, p.project_name, m.boq_number, m.boq_description,
                   COALESCE(m.calculated_quantity, 0) AS qty, COALESCE(m.unit, '') AS unit,
                   COALESCE(m.approval_status, 'Pending Checker') AS approval_status,
                   COALESCE(m.created_by, '') AS created_by
            FROM dpr_measurements m
            LEFT JOIN projects p ON m.project_id = p.id
            WHERE m.report_date = date('now')
            ORDER BY m.id DESC
            LIMIT 12
            """
        ).fetchall()
        live["dpr_today"] = [
            {
                "id": row["id"],
                "date": row["report_date"] or "—",
                "project": row["project_name"] or "—",
                "boq": row["boq_number"] or row["boq_description"] or "—",
                "qty": row["qty"],
                "unit": row["unit"] or "—",
                "status": row["approval_status"],
                "entered_by": row["created_by"] or "—",
                "action_url": url_for("dpr_entry", view=row["id"]),
            }
            for row in rows
        ]
    except Exception:
        pass

    try:
        rows = db.execute(
            """
            SELECT m.id, COALESCE(m.request_date, '') AS request_date, p.project_name,
                   COALESCE(m.item_name, '') AS item_name, COALESCE(m.quantity, 0) AS quantity,
                   COALESCE(m.unit, '') AS unit,
                   COALESCE(m.approval_status, 'Pending Checker') AS approval_status,
                   COALESCE(m.created_by, '') AS created_by
            FROM material_requests m
            LEFT JOIN projects p ON m.project_id = p.id
            ORDER BY m.id DESC
            LIMIT 8
            """
        ).fetchall()
        live["recent_material_requests"] = [
            {
                "id": row["id"],
                "date": row["request_date"] or "—",
                "project": row["project_name"] or "—",
                "item": row["item_name"] or "—",
                "qty": row["quantity"],
                "unit": row["unit"] or "—",
                "status": row["approval_status"],
                "requested_by": row["created_by"] or "—",
                "action_url": url_for("material_request", view=row["id"]),
            }
            for row in rows
        ]
    except Exception:
        pass

    try:
        rows = db.execute(
            """
            SELECT id, COALESCE(period_month, '') AS period_month, COALESCE(period_year, '') AS period_year,
                   COALESCE(total_gross, 0) AS total_gross, COALESCE(total_net, 0) AS total_net,
                   COALESCE(employee_count, 0) AS employee_count,
                   COALESCE(status, 'Draft') AS status
            FROM payroll_runs
            ORDER BY id DESC
            LIMIT 4
            """
        ).fetchall()
        live["payroll_summary"] = [
            {
                "id": row["id"],
                "period": f"{row['period_month']} {row['period_year']}".strip() or "—",
                "employees": row["employee_count"],
                "gross": row["total_gross"],
                "net": row["total_net"],
                "status": row["status"],
                "action_url": url_for("payroll", view=row["id"]),
            }
            for row in rows
        ]
    except Exception:
        pass

    try:
        rows = db.execute(
            """
            SELECT module_id, COUNT(*) AS pending_count
            FROM approval_requests
            WHERE workflow_status NOT IN ('approved', 'rejected')
            GROUP BY module_id
            ORDER BY pending_count DESC
            LIMIT 8
            """
        ).fetchall()
        live["pending_approvals"] = [
            {
                "module": (row["module_id"] or "general").replace("_", " ").title(),
                "count": row["pending_count"],
                "action_url": url_for("approvals"),
            }
            for row in rows
        ]
    except Exception:
        pass

    try:
        rows = db.execute(
            """
            SELECT id, COALESCE(project_name, '') AS project_name, COALESCE(project_code, '') AS project_code,
                   COALESCE(status, 'Active') AS status, COALESCE(location, '') AS location
            FROM projects
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()
        live["project_status"] = [
            {
                "id": row["id"],
                "name": row["project_name"] or row["project_code"] or "—",
                "code": row["project_code"] or "—",
                "status": row["status"],
                "location": row["location"] or "—",
                "action_url": url_for("projects", view=row["id"]),
            }
            for row in rows
        ]
    except Exception:
        pass

    return live


def _format_dashboard_currency(amount):
    try:
        value = float(amount or 0)
    except (TypeError, ValueError):
        value = 0.0
    if abs(value) >= 10000000:
        return f"₹ {value / 10000000:.2f}Cr"
    if abs(value) >= 100000:
        return f"₹ {value / 100000:.2f}L"
    return f"₹ {value:,.0f}"


def _dashboard_cash_balance(db):
    """Petty cash on hand, falling back to active bank balance."""
    petty_total = 0.0
    if _table_exists(db, "petty_cash_requests"):
        try:
            petty_row = db.execute(
                "SELECT COALESCE(SUM(COALESCE(transferred_amount, 0) - COALESCE(expenses_total, 0)), 0) AS total "
                "FROM petty_cash_requests "
                "WHERE approval_status IN ('Approved', 'Settled', 'Released')"
            ).fetchone()
            petty_total = float(petty_row["total"] if petty_row else 0)
        except Exception:
            petty_total = 0.0
    if petty_total > 0:
        return round(petty_total, 2)
    for table in ("bank_accounts", "treasury_bank_accounts"):
        if not _table_exists(db, table):
            continue
        try:
            bank_row = db.execute(
                f"SELECT COALESCE(SUM(current_balance), 0) AS total FROM {table} "
                "WHERE COALESCE(is_active, 1)=1"
            ).fetchone()
            bank_total = float(bank_row["total"] if bank_row else 0)
            if bank_total > 0:
                return round(bank_total, 2)
        except Exception:
            continue
    return round(petty_total, 2)


def get_dashboard_stats(db):
    """Aggregate KPI and chart data for the home dashboard."""
    try:
        total_projects = query_db("SELECT COUNT(*) AS count FROM projects", one=True)["count"]
        active_projects = query_db(
            "SELECT COUNT(*) AS count FROM projects WHERE status='Active'", one=True
        )["count"]
        active_workers = query_db(
            "SELECT COUNT(*) AS count FROM workers WHERE status='Active'", one=True
        )["count"]
        active_staff = query_db(
            "SELECT COUNT(*) AS count FROM staff WHERE status='Active'", one=True
        )["count"]
    except Exception:
        app.logger.exception("Dashboard base counts query failed")
        total_projects = active_projects = active_workers = active_staff = 0
    pending_mrs = 0
    material_requests_total = 0
    try:
        pending_mrs = db.execute(
            "SELECT COUNT(*) AS c FROM material_requests "
            "WHERE approval_status IN ('Pending Checker', 'Pending Approval')"
        ).fetchone()["c"]
        material_requests_total = db.execute(
            "SELECT COUNT(*) AS c FROM material_requests"
        ).fetchone()["c"]
    except Exception:
        pass
    dpr_today_count = 0
    try:
        dpr_today_count = db.execute(
            "SELECT COUNT(*) AS c FROM dpr_measurements WHERE report_date=date('now')"
        ).fetchone()["c"]
    except Exception:
        try:
            dpr_today_count = db.execute(
                "SELECT COUNT(*) AS c FROM dpr_entries WHERE report_date=date('now')"
            ).fetchone()["c"]
        except Exception:
            pass
    workflow_tasks = 0
    try:
        workflow_tasks = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests "
            "WHERE workflow_status NOT IN ('approved')"
        ).fetchone()["c"]
    except Exception:
        app.logger.exception("Dashboard workflow task count query failed")
    pending_approvals_count = 0
    try:
        pending_approvals_count = db.execute(
            "SELECT COUNT(*) AS c FROM approval_requests "
            "WHERE workflow_status NOT IN ('approved', 'rejected')"
        ).fetchone()["c"]
    except Exception:
        pending_approvals_count = workflow_tasks
    cash_balance = _dashboard_cash_balance(db)
    total_employees = (active_staff or 0) + (active_workers or 0)
    store_metric = pending_mrs
    try:
        store_stats = store_dashboard_stats(db)
        store_metric = store_stats.get("pending_material_requests") or pending_mrs
    except Exception:
        pass

    featured = None
    try:
        featured = query_db(
            "SELECT project_name, location, status FROM projects "
            "WHERE status='Active' ORDER BY id DESC LIMIT 1",
            one=True,
        )
    except Exception:
        app.logger.exception("Dashboard featured project query failed")
    progress_pct = 80
    if featured and total_projects:
        progress_pct = min(95, 50 + active_projects * 10)

    try:
        attendance_rows = query_db(
            "SELECT attendance_date, COUNT(*) AS cnt FROM attendance "
            "WHERE attendance_date >= date('now', '-6 days') "
            "GROUP BY attendance_date ORDER BY attendance_date ASC"
        )
    except Exception:
        app.logger.exception("Dashboard attendance trend query failed")
        attendance_rows = []
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    counts_by_day = [row["cnt"] for row in attendance_rows]
    while len(counts_by_day) < 7:
        counts_by_day.append(0)
    counts_by_day = counts_by_day[-7:]
    max_cnt = max(counts_by_day) if counts_by_day else 1
    if max_cnt == 0:
        max_cnt = 1
    attendance_bars = []
    for i, label in enumerate(day_labels):
        cnt = counts_by_day[i] if i < len(counts_by_day) else 0
        attendance_bars.append(
            {
                "label": label,
                "count": cnt,
                "height": int((cnt / max_cnt) * 100) if cnt else 8,
            }
        )

    present_today = 0
    try:
        present_today = db.execute(
            "SELECT COUNT(*) AS c FROM attendance WHERE attendance_date=date('now') AND status='Present'"
        ).fetchone()["c"]
    except Exception:
        pass

    health_score = min(100, 40 + active_projects * 10 + min(active_workers, 30))
    health_segments = [
        {"label": "Product Dev", "pct": min(95, 60 + active_projects * 5), "color": "#3B82F6"},
        {"label": "Operations", "pct": min(90, 30 + active_workers), "color": "#10B981"},
        {"label": "Site Logistics", "pct": min(85, 20 + pending_mrs * 8), "color": "#F59E0B"},
    ]

    return {
        "total_projects": total_projects,
        "active_projects": active_projects,
        "active_workers": active_workers,
        "active_staff": active_staff,
        "total_employees": total_employees,
        "pending_mrs": pending_mrs,
        "material_requests_total": material_requests_total,
        "store_metric": store_metric,
        "dpr_today_count": dpr_today_count,
        "cash_balance": cash_balance,
        "cash_display": _format_dashboard_currency(cash_balance),
        "pending_approvals_count": pending_approvals_count,
        "workflow_tasks": workflow_tasks,
        "featured_project": featured,
        "progress_pct": progress_pct,
        "attendance_bars": attendance_bars,
        "present_today": present_today or active_workers,
        "health_score": health_score,
        "health_segments": health_segments,
    }


def _build_dashboard_chart_series(stats):
    """Demo chart coordinates for the main dashboard hero chart (SVG-ready)."""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    active = stats.get("active_projects") or 1
    workforce = stats.get("total_employees") or 10
    cash = stats.get("cash_balance") or 0
    pending = stats.get("pending_approvals_count") or 0

    def _wave(base, amp, phase=0):
        points = []
        for i in range(12):
            val = base + amp * ((i + phase) % 4 - 1.5)
            y = max(8, min(92, 55 - val * 2))
            x = 8 + i * (84 / 11)
            points.append({"x": round(x, 1), "y": round(y, 1), "label": months[i]})
        return points

    return {
        "title": "Operations Overview",
        "months": months,
        "series": [
            {
                "key": "revenue",
                "label": "Revenue",
                "color": "#FF4D97",
                "points": _wave(active * 3, 6, 0),
            },
            {
                "key": "workforce",
                "label": "Workforce",
                "color": "#4ADE80",
                "points": _wave(workforce / 8, 8, 1),
            },
            {
                "key": "pending",
                "label": "Pending",
                "color": "#3B82F6",
                "points": _wave(pending + 2, 10, 2),
            },
            {
                "key": "cash",
                "label": "Cash Flow",
                "color": "#E5E7EB",
                "points": _wave(min(cash / 100000, 20) + 5, 5, 3),
            },
        ],
        "expense_rows": [
            {"label": "Labour & Wages", "pct": 38, "color": "#FF4D97"},
            {"label": "Materials", "pct": 27, "color": "#3B82F6"},
            {"label": "Plant & Equipment", "pct": 18, "color": "#4ADE80"},
            {"label": "Overheads", "pct": 11, "color": "#F59E0B"},
            {"label": "Subcontract", "pct": 6, "color": "#A78BFA"},
        ],
    }


DEPARTMENT_WORKFLOW_MODULES = {
    "consultancy": ("boq", "cost_planning", "project_creation", "dpr", "client_billing"),
    "projects": ("boq", "project_creation", "dpr", "cost_planning"),
    "accounts": APPROVAL_MODULE_GROUPS["payment"] + ("petty_cash",),
    "store": APPROVAL_MODULE_GROUPS["store"],
    "procurement": ("purchase_request", "purchase_order"),
    "hr-payroll": APPROVAL_MODULE_GROUPS["payroll"] + APPROVAL_MODULE_GROUPS["timesheet"],
    "engineering": ("boq", "cost_planning"),
    "subcontract": ("subcontractor_billing", "subcontract_payments"),
    "tender": ("boq", "project_creation"),
    "vehicle": (),
    "mechanical": (),
    "qc": (),
    "administration": (),
    "reports": tuple(module for group in APPROVAL_MODULE_GROUPS.values() for module in group),
}

DEPARTMENT_REPORT_CATEGORIES = {
    "consultancy": ("engineering", "billing"),
    "projects": ("billing", "management"),
    "accounts": ("accounts", "management"),
    "store": ("stores",),
    "procurement": ("stores",),
    "hr-payroll": ("payroll",),
    "engineering": ("engineering", "management"),
    "subcontract": ("billing",),
    "mechanical": ("fleet_mechanical", "plant_operations"),
    "vehicle": ("fleet_mechanical",),
    "qc": ("engineering",),
    "tender": ("billing",),
    "administration": ("management",),
    "reports": ("management", "engineering", "billing", "payroll", "accounts", "stores", "fleet_mechanical"),
}

ENDPOINT_WORKFLOW_MODULE = {
    "material_request": "material_request",
    "purchase_request": "purchase_request",
    "purchase_orders": "purchase_order",
    "purchase": "purchase_order",
    "petty_cash": "petty_cash",
    "payroll": "payroll",
    "leave_request": "leave_request",
    "boq_management": "boq",
    "dpr_entry": "dpr",
    "client_billing_register": "client_billing",
    "cost_planning": "cost_planning",
    "projects": "project_creation",
    "accounts_expenses": "account_payment",
    "accounts_payments": "payment_voucher",
    "accounts_receipts": "account_receipt",
    "store_issue": "store_issue",
    "store_receipt": "store_receipt",
    "sub_billing_register": "subcontractor_billing",
    "subcontract_payments": "subcontract_payments",
    "timesheet": "daily_timesheet",
    "employee_timesheets": "employee_timesheet",
}

WORKFLOW_TICKET_TYPE_META = {
    "purchase": {"label": "Purchase workflows", "icon": "fa-cart-shopping"},
    "store": {"label": "Store workflows", "icon": "fa-warehouse"},
    "timesheet": {"label": "Timesheet workflows", "icon": "fa-clock"},
    "payroll": {"label": "Payroll workflows", "icon": "fa-money-check-dollar"},
    "payment": {"label": "Payment workflows", "icon": "fa-landmark"},
}


def _department_workflow_module_ids(slug=None):
    if not slug:
        return tuple(module for group in APPROVAL_MODULE_GROUPS.values() for module in group)
    slug = resolve_department_portal_slug(slug)
    return DEPARTMENT_WORKFLOW_MODULES.get(slug, ())


def _pending_workflow_count(db, module_ids):
    if not module_ids or not _table_exists(db, "approval_requests"):
        return 0
    placeholders = ",".join("?" * len(module_ids))
    return _safe_scalar_count(
        db,
        "SELECT COUNT(*) AS c FROM approval_requests "
        f"WHERE module_id IN ({placeholders}) "
        "AND workflow_status IN ('pending_checker', 'pending_approval')",
        tuple(module_ids),
    )


def _workspace_open_items_count(db, slug=None):
    module_ids = _department_workflow_module_ids(slug)
    return _pending_workflow_count(db, module_ids)


def _workspace_completed_count(db, slug=None):
    module_ids = _department_workflow_module_ids(slug)
    if not _table_exists(db, "approval_requests"):
        return 0
    base_sql = (
        "SELECT COUNT(*) AS c FROM approval_requests "
        "WHERE workflow_status='approved' "
        "AND date(COALESCE(approver_action_at, checker_action_at, created_at)) >= date('now', 'start of month')"
    )
    if not module_ids:
        return _safe_scalar_count(db, base_sql)
    placeholders = ",".join("?" * len(module_ids))
    return _safe_scalar_count(db, f"{base_sql} AND module_id IN ({placeholders})", tuple(module_ids))


def _workspace_month_amount(db, slug=None):
    total = 0.0
    slug = resolve_department_portal_slug(slug) if slug else None
    scopes = {slug} if slug else None
    try:
        if scopes is None or scopes & {"accounts", "projects", "consultancy", "engineering", "reports"}:
            if _table_exists(db, "client_bills"):
                row = db.execute(
                    "SELECT COALESCE(SUM(net_amount), 0) AS total FROM client_bills "
                    "WHERE date(COALESCE(bill_date, created_at)) >= date('now', 'start of month') "
                    "AND approval_status IN ('Approved', 'Certified', 'Paid')"
                ).fetchone()
                total += float(row["total"] or 0)
        if scopes is None or scopes & {"accounts", "reports"}:
            if _table_exists(db, "account_expenses"):
                row = db.execute(
                    "SELECT COALESCE(SUM(amount), 0) AS total FROM account_expenses "
                    "WHERE date(expense_date) >= date('now', 'start of month')"
                ).fetchone()
                total += float(row["total"] or 0)
        if scopes is None or scopes & {"hr-payroll", "reports"}:
            if _table_exists(db, "payroll_run_lines"):
                row = db.execute(
                    "SELECT COALESCE(SUM(net_pay), 0) AS total FROM payroll_run_lines prl "
                    "JOIN payroll_runs pr ON pr.id = prl.payroll_run_id "
                    "WHERE date(COALESCE(pr.run_date, pr.created_at)) >= date('now', 'start of month')"
                ).fetchone()
                total += float(row["total"] or 0)
        if scopes is None or scopes & {"store", "procurement", "reports"}:
            if _table_exists(db, "purchase_orders"):
                row = db.execute(
                    "SELECT COALESCE(SUM(grand_total), 0) AS total FROM purchase_orders "
                    "WHERE date(COALESCE(order_date, created_at)) >= date('now', 'start of month') "
                    "AND approval_status IN ('Approved', 'approved', 'Pending Approval', 'Pending Checker')"
                ).fetchone()
                total += float(row["total"] or 0)
    except Exception:
        app.logger.exception("Workspace month amount query failed for slug=%s", slug)
    return total


def _format_workspace_inr(amount):
    amount = float(amount or 0)
    if amount <= 0:
        return "₹0"
    if amount >= 10000000:
        return f"₹{round(amount / 10000000, 1)} CR"
    if amount >= 100000:
        return f"₹{round(amount / 100000, 1)} L"
    if amount >= 1000:
        return f"₹{round(amount / 1000, 1)} K"
    return f"₹{int(amount)}"


def get_workspace_standard_stat_cards(db, slug=None):
    open_items = _workspace_open_items_count(db, slug)
    pending_approvals = open_items
    month_amount = _workspace_month_amount(db, slug)
    completed = _workspace_completed_count(db, slug)
    return [
        {"label": "Open items", "value": open_items, "warn": open_items > 0},
        {"label": "Pending approvals", "value": pending_approvals, "warn": pending_approvals > 0},
        {"label": "This month ₹", "value": _format_workspace_inr(month_amount)},
        {"label": "Completed", "value": completed},
    ]


def build_workspace_report_modules(slug=None, limit=6):
    slug = resolve_department_portal_slug(slug) if slug else None
    category_slugs = DEPARTMENT_REPORT_CATEGORIES.get(slug or "reports", ("management",))
    modules = []
    for category in REPORT_CATEGORIES:
        if category["slug"] not in category_slugs:
            continue
        for report in category["reports"]:
            mod = {
                "label": report["label"],
                "icon": category["icon"],
                "action_label": "Run",
            }
            if report.get("screen_endpoint"):
                mod["endpoint"] = report["screen_endpoint"]
            elif report.get("print_endpoint"):
                mod["endpoint"] = report["print_endpoint"]
                if report.get("print_param"):
                    mod["query"] = {report["print_param"]: 1}
            else:
                mod["endpoint"] = "reports"
                mod["query"] = {"report": report["slug"]}
            modules.append(mod)
            if len(modules) >= limit:
                return modules
    return modules


def get_workspace_ticket_types(db, slug=None):
    module_ids = set(_department_workflow_module_ids(slug))
    ticket_types = []
    for group_key, group_modules in APPROVAL_MODULE_GROUPS.items():
        scoped = [module for module in group_modules if not module_ids or module in module_ids]
        if not scoped:
            continue
        count = _pending_workflow_count(db, tuple(scoped))
        meta = WORKFLOW_TICKET_TYPE_META.get(
            group_key,
            {"label": group_key.replace("_", " ").title(), "icon": "fa-ticket"},
        )
        ticket_types.append(
            {
                "endpoint": "approvals",
                "query": {"module": scoped[0]},
                "label": meta["label"],
                "icon": meta["icon"],
                "description": "Workflow pending items",
                "open_count": count or None,
            }
        )
    return ticket_types


def enrich_portal_menu_open_counts(db, menu):
    enriched = []
    for item in menu:
        row = dict(item)
        module_id = ENDPOINT_WORKFLOW_MODULE.get(item.get("endpoint"))
        if module_id:
            count = _pending_workflow_count(db, (module_id,))
            if count:
                row["open_count"] = count
        enriched.append(row)
    return enriched


def command_centre_cards_to_modules(cards):
    modules = []
    for card in cards:
        modules.append(
            {
                "href": url_for("department_portal", slug=card["slug"]),
                "label": card["card_label"],
                "icon": card["icon"],
                "description": card.get("description", ""),
                "open_count": _workspace_open_items_count(get_db(), card["slug"]) or None,
            }
        )
    return modules


def _command_centre_sidebar_context(db, active_slug="command-centre", show_sidebar=False):
    """Layout context for Command Centre pages.

    Main dashboard and department workspaces use the in-page dept grid / left tool
    rail only — not the global command-centre sidebar (avoids duplicate navigation).
    """
    username = session.get("username") or "Administrator"
    welcome = session.get("employee_name") or (username.title() if username.islower() else username)
    role_label = session.get("role") or "Owner"
    try:
        if is_super_admin_user():
            role_label = "Owner"
    except Exception:
        pass
    return {
        "welcome_name": welcome,
        "show_command_sidebar": show_sidebar,
        "command_active_slug": active_slug,
        "command_sidebar_items": get_command_centre_sidebar_items(db) if show_sidebar else [],
        "command_centre_branch": session.get("branch", "Head Office"),
        "command_user_role": role_label,
    }


def _command_centre_sidebar_badges(db):
    badges = {}
    try:
        _prepare_accounts_db(db)
        acc = accounts_hub_stats(db)
        journal_pending = 0
        if _table_exists(db, "journal_entries"):
            journal_pending = _safe_scalar_count(
                db,
                "SELECT COUNT(*) AS c FROM journal_entries "
                "WHERE approval_status IN ('Pending Checker', 'Pending Approval')",
            )
        badges["accounts"] = (acc.get("pending_expenses") or 0) + journal_pending
    except Exception:
        badges["accounts"] = 0
    badges["hr-payroll"] = _safe_scalar_count(
        db,
        "SELECT COUNT(*) AS c FROM leave_requests "
        "WHERE approval_status IN ('Pending', 'Pending Checker', 'Pending Approval')",
    )
    try:
        _prepare_store_db(db)
        store = store_dashboard_stats(db)
        badges["store"] = (store.get("pending_material_requests") or 0) + (
            store.get("pending_purchase_requests") or 0
        )
    except Exception:
        badges["store"] = _safe_scalar_count(
            db,
            "SELECT COUNT(*) AS c FROM material_requests "
            "WHERE approval_status IN ('Pending Checker', 'Pending Approval')",
        )
    badges["subcontract"] = 0
    if _table_exists(db, "subcontractor_bills"):
        badges["subcontract"] = _safe_scalar_count(
            db,
            "SELECT COUNT(*) AS c FROM subcontractor_bills "
            "WHERE approval_status IN ('Pending Checker', 'Pending Approval', 'Pending')",
        )
    badges["mechanical"] = 0
    try:
        _prepare_plant_db(db)
        plant = plant_dashboard_stats(db)
        badges["mechanical"] = plant.get("open_maintenance_jobs") or 0
    except Exception:
        pass
    badges["administration"] = 0
    try:
        _prepare_office_fleet_db(db)
        badges["administration"] = office_dashboard_stats(db).get("expiry_alerts") or 0
    except Exception:
        pass
    return badges


def get_command_centre_sidebar_items(db):
    badges = _command_centre_sidebar_badges(db)
    items = []
    for meta in COMMAND_CENTRE_CARD_META:
        badge = badges.get(meta["slug"], 0)
        items.append(
            {
                "slug": meta["slug"],
                "label": meta["card_label"],
                "icon": meta["icon"],
                "badge": badge if badge else None,
            }
        )
    return items


def _command_centre_card_stats(db, slug):
    stat_cards = department_portal_stat_cards(slug, db)
    pills = []
    if slug == "accounts":
        try:
            _prepare_accounts_db(db)
            acc = accounts_hub_stats(db)
            journal_pending = 0
            if _table_exists(db, "journal_entries"):
                journal_pending = _safe_scalar_count(
                    db,
                    "SELECT COUNT(*) AS c FROM journal_entries "
                    "WHERE approval_status IN ('Pending Checker', 'Pending Approval')",
                )
            pills = [
                {"label": "Chart heads", "value": str(acc.get("chart_heads", 0))},
                {
                    "label": "Journals pending",
                    "value": str(journal_pending),
                    "tone": "warn" if journal_pending else None,
                },
            ]
        except Exception:
            pass
    elif slug == "projects":
        active = _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM projects WHERE status='Active'")
        total = _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM projects")
        on_schedule = "—"
        if total:
            on_schedule = f"{min(99, max(50, int(active / total * 100)))}%"
        pills = [
            {"label": "Active projects", "value": str(active)},
            {"label": "On schedule", "value": on_schedule, "tone": "ok"},
        ]
    elif slug == "hr-payroll":
        employees = _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM staff WHERE status='Active'")
        workers = _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM workers WHERE status='Active'")
        leave_pending = _safe_scalar_count(
            db,
            "SELECT COUNT(*) AS c FROM leave_requests "
            "WHERE approval_status IN ('Pending', 'Pending Checker', 'Pending Approval')",
        )
        pills = [
            {"label": "Employees", "value": str(employees + workers)},
            {"label": "Leave pending", "value": str(leave_pending), "tone": "warn" if leave_pending else None},
        ]
    elif slug == "store":
        open_pos = _safe_scalar_count(
            db,
            "SELECT COUNT(*) AS c FROM purchase_orders "
            "WHERE approval_status IN ('Pending Checker', 'Pending Approval', 'Pending', 'Draft')",
        )
        overdue_pos = 0
        if _table_exists(db, "purchase_orders"):
            try:
                overdue_pos = _safe_scalar_count(
                    db,
                    "SELECT COUNT(*) AS c FROM purchase_orders "
                    "WHERE due_date IS NOT NULL AND due_date < date('now') "
                    "AND approval_status NOT IN ('Approved', 'approved', 'Rejected', 'rejected')",
                )
            except Exception:
                overdue_pos = 0
        pills = [
            {"label": "Open POs", "value": str(open_pos)},
            {"label": "Overdue", "value": str(overdue_pos), "tone": "danger" if overdue_pos else None},
        ]
    elif slug == "engineering":
        active_boqs = _safe_scalar_count(
            db,
            "SELECT COUNT(*) AS c FROM boq_master WHERE COALESCE(is_deleted, 0)=0",
        )
        open_nois = _safe_scalar_count(
            db,
            "SELECT COUNT(*) AS c FROM boq_master "
            "WHERE COALESCE(is_deleted, 0)=0 AND approval_status NOT IN ('Approved', 'approved')",
        )
        pills = [
            {"label": "Active BOQs", "value": str(active_boqs)},
            {"label": "Open NOIs", "value": "Clear" if open_nois == 0 else str(open_nois), "tone": "ok" if open_nois == 0 else "warn"},
        ]
    elif slug == "subcontract":
        contractors = _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM subcontractors")
        bills_pending = 0
        if _table_exists(db, "subcontractor_bills"):
            bills_pending = _safe_scalar_count(
                db,
                "SELECT COUNT(*) AS c FROM subcontractor_bills "
                "WHERE approval_status IN ('Pending Checker', 'Pending Approval', 'Pending')",
            )
        pills = [
            {"label": "Contractors", "value": str(contractors)},
            {"label": "Bills pending", "value": str(bills_pending), "tone": "warn" if bills_pending else None},
        ]
    elif slug == "mechanical":
        machines = _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM plants") if _table_exists(db, "plants") else 0
        due_service = 0
        try:
            _prepare_plant_db(db)
            plant = plant_dashboard_stats(db)
            due_service = plant.get("open_maintenance_jobs") or 0
            machines = plant.get("active_plants") or machines
        except Exception:
            pass
        pills = [
            {"label": "Machines", "value": str(machines)},
            {"label": "Due service", "value": str(due_service), "tone": "warn" if due_service else None},
        ]
    if not pills and stat_cards:
        pills = [
            {"label": card["label"], "value": str(card["value"])}
            for card in stat_cards[:2]
        ]
    return pills


def get_command_centre_kpis(db):
    stats = get_dashboard_stats(db)
    accounts = {}
    try:
        _prepare_accounts_db(db)
        accounts = accounts_hub_stats(db)
    except Exception:
        pass
    pending_expenses = accounts.get("pending_expenses", 0)
    journal_pending = 0
    if _table_exists(db, "journal_entries"):
        journal_pending = _safe_scalar_count(
            db,
            "SELECT COUNT(*) AS c FROM journal_entries "
            "WHERE approval_status IN ('Pending Checker', 'Pending Approval')",
        )
    open_pos = _safe_scalar_count(
        db,
        "SELECT COUNT(*) AS c FROM purchase_orders "
        "WHERE approval_status IN ('Pending Checker', 'Pending Approval', 'Pending', 'Draft')",
    )
    overdue_pos = 0
    if _table_exists(db, "purchase_orders"):
        try:
            overdue_pos = _safe_scalar_count(
                db,
                "SELECT COUNT(*) AS c FROM purchase_orders "
                "WHERE due_date IS NOT NULL AND due_date < date('now') "
                "AND approval_status NOT IN ('Approved', 'approved', 'Rejected', 'rejected')",
            )
        except Exception:
            pass
    revenue_cr = None
    if _table_exists(db, "client_bills"):
        try:
            row = db.execute(
                "SELECT COALESCE(SUM(net_amount), 0) AS total FROM client_bills "
                "WHERE approval_status IN ('Approved', 'Certified', 'Paid')"
            ).fetchone()
            total = float(row["total"] or 0)
            revenue_cr = round(total / 10000000, 1) if total else 0
        except Exception:
            revenue_cr = None
    new_joins = _safe_scalar_count(
        db,
        "SELECT COUNT(*) AS c FROM staff WHERE date(created_at) >= date('now', 'start of month')",
    ) if _table_exists(db, "staff") else 0
    return [
        {
            "key": "active_projects",
            "label": "Active Projects",
            "value": stats.get("active_projects", 0),
            "hint": f"{stats.get('total_projects', 0)} total sites",
            "hint_tone": "ok",
        },
        {
            "key": "workforce",
            "label": "Workforce",
            "value": stats.get("total_employees", 0),
            "hint": f"{new_joins} new joins" if new_joins else "All staff",
            "hint_tone": "ok" if new_joins else "muted",
        },
        {
            "key": "revenue",
            "label": "Revenue (₹ CR)",
            "value": revenue_cr if revenue_cr is not None else "—",
            "hint": "From approved billing" if revenue_cr is not None else "No billing data",
            "hint_tone": "ok" if revenue_cr else "muted",
        },
        {
            "key": "pending_expenses",
            "label": "Pending Expenses",
            "value": pending_expenses,
            "hint": "All cleared" if pending_expenses == 0 else f"{pending_expenses} awaiting",
            "hint_tone": "muted" if pending_expenses == 0 else "warn",
        },
        {
            "key": "open_pos",
            "label": "Open POs",
            "value": open_pos,
            "hint": f"{overdue_pos} overdue" if overdue_pos else "On track",
            "hint_tone": "warn" if overdue_pos else "ok",
        },
        {
            "key": "journal_entries",
            "label": "Journal Entries",
            "value": journal_pending,
            "hint": "Pending review" if journal_pending else "Up to date",
            "hint_tone": "warn" if journal_pending else "muted",
        },
    ]


def get_command_centre_cards(db):
    meta_by_slug = {meta["slug"]: meta for meta in COMMAND_CENTRE_CARD_META}
    cards = []
    for slug, label in MAIN_DASHBOARD_DEPARTMENT_SLUGS:
        portal = get_department_portal(slug)
        if not portal:
            continue
        canonical_slug = portal["slug"]
        meta = meta_by_slug.get(slug) or meta_by_slug.get(canonical_slug)
        if not meta:
            continue
        cards.append(
            {
                **meta,
                "slug": slug,
                "card_label": label,
                "stat_pills": _command_centre_card_stats(db, canonical_slug),
            }
        )
    return cards


def get_command_centre_recent_activity(db, limit=6):
    activities = get_recent_activities(db, limit=limit)
    tone_map = {
        "approved": "ok",
        "verified": "ok",
        "created": "info",
        "submitted": "info",
        "rejected": "danger",
        "reopened": "warn",
    }
    feed = []
    for row in activities:
        action_key = row.get("action_key") or ""
        title = row.get("module") or "Activity"
        detail = row.get("remarks") or f"{row.get('action', 'Updated')} · {row.get('document', '')}"
        feed.append(
            {
                "title": title,
                "detail": detail.strip(),
                "time": row.get("time") or row.get("date") or "—",
                "tone": tone_map.get(action_key, "info"),
            }
        )
    if feed:
        return feed
    return [
        {"title": "No recent activity", "detail": "Workflow actions will appear here.", "time": "—", "tone": "muted"},
    ]


def get_command_centre_workflow_stat_cards(db):
    """Aggregated workflow KPIs for the main Command Centre dashboard."""
    return get_workspace_standard_stat_cards(db)


def _department_open_count(db, slug, badges):
    open_count = badges.get(slug, 0) or _workspace_open_items_count(db, slug)
    return open_count if open_count else 0


def get_command_centre_department_modules(db):
    """Department launcher tiles — each links to /dept/<slug> with open counts."""
    badges = _command_centre_sidebar_badges(db)
    meta_by_slug = {meta["slug"]: meta for meta in COMMAND_CENTRE_CARD_META}
    modules = []
    for portal in get_department_portals():
        slug = portal["slug"]
        meta = meta_by_slug.get(slug, {})
        open_count = _department_open_count(db, slug, badges)
        modules.append(
            {
                "href": url_for("department_portal", slug=slug),
                "label": meta.get("card_label") or portal.get("card_label") or portal["title"],
                "icon": portal.get("icon") or meta.get("icon") or "fa-folder",
                "description": meta.get("description") or portal.get("summary_title") or "",
                "open_count": open_count if open_count else None,
            }
        )
    return modules


def get_command_centre_report_modules():
    """Quick report launcher tiles with Run action."""
    return [
        {
            "endpoint": "reports",
            "label": "Operational Reports",
            "icon": "fa-file-excel",
            "description": "Attendance, salary & operational exports",
            "action_label": "Run",
        },
        {
            "endpoint": "accounts_reports",
            "label": "Financial Reports",
            "icon": "fa-chart-line",
            "description": "P&L, balance sheet & ledger",
            "action_label": "Run",
        },
        {
            "endpoint": "cost_planning_reports",
            "label": "Project Reports",
            "icon": "fa-diagram-project",
            "description": "Cost planning & BOQ analysis",
            "action_label": "Run",
        },
        {
            "endpoint": "inventory",
            "label": "Store Reports",
            "icon": "fa-warehouse",
            "description": "Stock register & inventory",
            "action_label": "Run",
        },
    ]


def get_command_centre_ticket_types(db):
    """Help-desk / workflow ticket entry points for the main dashboard."""
    pending_approvals = get_dashboard_stats(db).get("pending_approvals_count") or 0
    support_open = 0
    if _table_exists(db, "erp_support_tickets"):
        support_open = _safe_scalar_count(
            db,
            "SELECT COUNT(*) AS c FROM erp_support_tickets WHERE status IN ('Open', 'In Progress')",
        )
    tickets = [
        {
            "endpoint": "approvals",
            "label": "Workflow approvals",
            "icon": "fa-clipboard-check",
            "description": "Pending checker & approver queue",
            "open_count": pending_approvals if pending_approvals else None,
        },
        {
            "endpoint": "help_desk",
            "label": "Help desk",
            "icon": "fa-circle-question",
            "description": "User manual & tutorials",
        },
    ]
    if _table_exists(db, "erp_support_tickets"):
        tickets.append(
            {
                "endpoint": "customer_support_tickets",
                "label": "Support tickets",
                "icon": "fa-headset",
                "description": "ERP support & issue tracking",
                "open_count": support_open if support_open else None,
            }
        )
    return tickets


def render_choice_b_dashboard():
    db = get_db()
    month_year = datetime.now().strftime("%b %Y")

    def _dashboard_payload(getter, default, label):
        try:
            return getter()
        except Exception:
            app.logger.exception("Dashboard payload failed: %s", label)
            return default

    user_prefs = _dashboard_payload(
        lambda: load_dashboard_preferences(db, session.get("user_id")),
        {},
        "user_dashboard_prefs",
    )
    favorite_modules = user_prefs.get("favorite_modules") if user_prefs else None
    dashboard_cards = user_prefs.get("dashboard_cards") if user_prefs else None

    command_centre_kpis = _dashboard_payload(
        lambda: get_command_centre_kpis(db),
        [],
        "command_centre_kpis",
    )
    command_centre_cards = _dashboard_payload(
        lambda: get_command_centre_cards(db),
        [],
        "command_centre_cards",
    )
    sidebar_context = _command_centre_sidebar_context(db, active_slug="command-centre")
    stats = _dashboard_payload(lambda: get_dashboard_stats(db), {}, "dashboard_stats")
    chart_series = _build_dashboard_chart_series(stats)

    return render_template(
        "dashboard.html",
        department_portals=get_department_portals(),
        command_centre_kpis=command_centre_kpis,
        command_centre_cards=command_centre_cards,
        command_centre_bottom_widgets=MAIN_DASHBOARD_BOTTOM_WIDGETS,
        command_centre_month=month_year,
        user_dashboard_prefs=user_prefs,
        dashboard_shell_favorites=DASHBOARD_SHELL_FAVORITES,
        dashboard_shell_nav_groups=DASHBOARD_SHELL_NAV_GROUPS,
        dashboard_chart_series=chart_series,
        dashboard_stats=stats,
        **sidebar_context,
    )


@app.route("/dashboard")
@login_required
def dashboard():
    return render_choice_b_dashboard()


@app.route("/dashboard/choice-b")
@login_required
def dashboard_choice_b():
    return redirect(url_for("dashboard"))


@app.route("/workforce")
@login_required
def workforce_dashboard():
    db = get_db()
    stat_cards = [
        {"label": "Active Employees", "value": _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM staff WHERE status='Active'")},
        {"label": "Present Today", "value": _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM attendance WHERE attendance_date=date('now') AND status='Present'")},
        {"label": "Pending Leave", "value": _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM leave_requests WHERE approval_status IN ('Pending', 'Pending Checker', 'Pending Approval')")},
        {"label": "Open Timesheets", "value": _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM employee_monthly_timesheets WHERE approval_status IN ('Draft', 'Pending Checker', 'Pending Approval')")},
    ]
    modules = [
        {"endpoint": "staff", "label": "Employees", "icon": "fa-user-tie", "description": "Employee master, profiles & bonus"},
        {"endpoint": "attendance", "label": "Attendance", "icon": "fa-calendar-check", "description": "Daily staff attendance register"},
        {"endpoint": "employee_timesheets", "label": "Monthly Timesheets", "icon": "fa-table", "description": "Monthly employee timesheet submission"},
        {"endpoint": "timesheet", "label": "Daily Timesheet Register", "icon": "fa-clock", "description": "Daily labour timesheet entries"},
        {"endpoint": "leave_request", "label": "Leave Management", "icon": "fa-plane-departure", "description": "Leave applications & approvals"},
        {"endpoint": "payroll", "label": "Payroll", "icon": "fa-money-check-dollar", "description": "Payroll processing & slips"},
        {"endpoint": "payroll_revisions", "label": "Rate Revisions", "icon": "fa-chart-line", "description": "Salary rate revision history"},
        {"endpoint": "salary", "label": "Salary Processing", "icon": "fa-wallet", "description": "Monthly salary calculation & payment"},
    ]
    return _render_department_hub("Workforce Dashboard", "Workforce", stat_cards, modules, "Workforce modules")


@app.route("/staff", methods=["GET", "POST"])
@login_required
def staff():
    db = get_db()
    prepare_staff_page_db(db)
    edit_id = request.args.get("edit", type=int)
    editing_staff = None
    editing_components = []
    editing_travel_tiers = []
    editing_salary_increments = []
    if edit_id:
        editing_staff = db.execute("SELECT * FROM staff WHERE id=?", (edit_id,)).fetchone()
        if not editing_staff:
            flash("Employee record not found.")
            return redirect(url_for("staff"))
        editing_components = _fetch_staff_salary_components(db, edit_id)
        editing_travel_tiers = _fetch_staff_travel_tiers(db, edit_id)
        editing_salary_increments = _fetch_staff_salary_increments(db, edit_id)
    designations = query_db(
        "SELECT id, designation_name FROM designations WHERE status='Active' ORDER BY designation_name"
    )
    departments = get_departments()
    staff_list = query_db("SELECT staff_name FROM staff WHERE status='Active' ORDER BY staff_name")
    if request.method == "POST":
        form_action = request.form.get("form_action", "").strip()
        if form_action == "add_increment":
            inc_staff_id = request.form.get("staff_id", "").strip()
            effective_date = request.form.get("effective_date", "").strip()
            new_amount_raw = request.form.get("new_salary_amount", "").strip()
            remarks = request.form.get("increment_remarks", "").strip()
            if not inc_staff_id:
                flash("Employee not found for increment.")
                return redirect(url_for("staff"))
            staff_row = db.execute("SELECT * FROM staff WHERE id=?", (inc_staff_id,)).fetchone()
            if not staff_row:
                flash("Employee not found.")
                return redirect(url_for("staff"))
            try:
                new_amount = float(new_amount_raw or 0)
            except ValueError:
                flash("Enter a valid new salary amount.")
                return redirect(url_for("staff", edit=inc_staff_id) + "#salary-increment")
            if new_amount <= 0:
                flash("New salary must be greater than zero.")
                return redirect(url_for("staff", edit=inc_staff_id) + "#salary-increment")
            previous = float(staff_row["salary_amount"] or 0)
            increment_amt = round(new_amount - previous, 2)
            created_at = get_app_now(db).strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "INSERT INTO staff_salary_increments(staff_id, effective_date, previous_amount, "
                "new_amount, increment_amount, remarks, created_by, created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    inc_staff_id,
                    effective_date or get_app_now(db).strftime("%Y-%m-%d"),
                    previous,
                    new_amount,
                    increment_amt,
                    remarks,
                    session.get("username", ""),
                    created_at,
                ),
            )
            db.execute(
                "INSERT INTO salary_revisions(employee_type, staff_id, previous_amount, revised_amount, "
                "increment_amount, effective_date, reason, approved_by, created_by, created_at) "
                "VALUES('staff',?,?,?,?,?,?,?,?,?)",
                (
                    inc_staff_id,
                    previous,
                    new_amount,
                    increment_amt,
                    effective_date or get_app_now(db).strftime("%Y-%m-%d"),
                    remarks,
                    session.get("username", ""),
                    session.get("username", ""),
                    created_at,
                ),
            )
            db.execute(
                "UPDATE staff SET salary_amount=? WHERE id=?",
                (new_amount, inc_staff_id),
            )
            if previous > 0:
                components = _fetch_staff_salary_components(db, int(inc_staff_id))
                if components:
                    ratio = new_amount / previous
                    scaled = [
                        {
                            "component_name": c["component_name"],
                            "amount": round(float(c["amount"] or 0) * ratio, 2),
                        }
                        for c in components
                    ]
                    _save_staff_salary_components(db, int(inc_staff_id), scaled)
            db.commit()
            flash(f"Salary increment recorded: {previous:,.2f} → {new_amount:,.2f}")
            return redirect(url_for("staff", edit=inc_staff_id) + "#salary-increment")

        staff_id = request.form.get("staff_id", "").strip()
        staff_name = request.form.get("staff_name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        email = request.form.get("email", "").strip()
        department = request.form.get("department", "").strip()
        designation_id = request.form.get("designation_id", "") or None
        reporting_manager = request.form.get("reporting_manager", "").strip()
        workflow_role = request.form.get("workflow_role", "").strip()
        salary_type = request.form.get("salary_type", "").strip()
        salary_amount = request.form.get("salary_amount", "0").strip()
        ot_applicable = request.form.get("ot_applicable", "No").strip()
        ot_rate_per_hour = request.form.get("ot_rate_per_hour", "0").strip()
        holiday_pay_applicable = request.form.get("holiday_pay_applicable", "No").strip()
        working_hours = request.form.get("working_hours", "0").strip()
        joining_date = request.form.get("joining_date", "").strip()
        date_of_birth = request.form.get("date_of_birth", "").strip()
        gender = request.form.get("gender", "").strip()
        status = request.form.get("status", "Active").strip()
        aadhaar_number = request.form.get("aadhaar_number", "").strip()
        pan_number = request.form.get("pan_number", "").strip()
        bank_account = request.form.get("bank_account", "").strip()
        bank_name = request.form.get("bank_name", "").strip()
        ifsc_code = request.form.get("ifsc_code", "").strip()
        branch_name = request.form.get("branch_name", "").strip()
        company_room_provided = request.form.get("company_room_provided", "No").strip()
        company_food_provided = request.form.get("company_food_provided", "No").strip()
        components = _parse_staff_hr_json(request.form.get("salary_components_payload"), [])
        travel_tiers = _parse_staff_hr_json(request.form.get("travel_tiers_payload"), [])
        if salary_type == "Monthly":
            basic_salary_raw = request.form.get("basic_salary", "").strip()
            has_basic_component = any(
                (c.get("component_name") or "").strip().lower() == "basic salary"
                for c in components
            )
            if basic_salary_raw and not has_basic_component:
                try:
                    basic_val = float(basic_salary_raw)
                except ValueError:
                    basic_val = 0.0
                if basic_val > 0:
                    components.insert(0, {"component_name": "Basic Salary", "amount": basic_val})
            comp_total = sum(
                float(c.get("amount") or 0)
                for c in components
                if (c.get("component_name") or "").strip()
            )
            if comp_total > 0:
                salary_amount = str(comp_total)
            elif basic_salary_raw:
                try:
                    salary_amount = str(float(basic_salary_raw))
                except ValueError:
                    pass
        existing_staff = None
        if staff_id:
            existing_staff = db.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
            if not existing_staff:
                flash("Employee record not found.")
                return redirect(url_for("staff"))
        photo = save_file(request.files.get("photo"), PHOTOS_DIR)
        id_proof = save_file(request.files.get("id_proof"), STAFF_DOCS_DIR)
        aadhaar_document = save_file(request.files.get("aadhaar_document"), STAFF_DOCS_DIR)
        pan_document = save_file(request.files.get("pan_document"), STAFF_DOCS_DIR)
        if existing_staff:
            photo = photo or existing_staff["photo"]
            id_proof = id_proof or existing_staff["id_proof"]
            aadhaar_document = aadhaar_document or existing_staff["aadhaar_document"]
            pan_document = pan_document or existing_staff["pan_document"]
        employee_code = existing_staff["employee_code"] if existing_staff else generate_employee_code(db)
        designation_name = ""
        if designation_id:
            drow = db.execute(
                "SELECT designation_name FROM designations WHERE id=?", (designation_id,)
            ).fetchone()
            designation_name = drow["designation_name"] if drow else ""
        try:
            salary_amount_val = float(salary_amount or 0)
            working_hours_val = float(working_hours or 0)
            ot_rate_val = float(ot_rate_per_hour or 0)
        except ValueError:
            flash("Enter valid numeric values for salary and working hours.")
            return redirect(url_for("staff"))
        values = (
            employee_code, staff_name, mobile, email, department, designation_name,
            designation_id, reporting_manager, workflow_role or None,
            salary_type, salary_amount_val, ot_applicable, ot_rate_val, holiday_pay_applicable,
            working_hours_val,
            joining_date, date_of_birth, gender, photo, status, aadhaar_number, pan_number,
            bank_account, bank_name, ifsc_code, branch_name,
            id_proof, aadhaar_document, pan_document,
            company_room_provided or "No", company_food_provided or "No",
        )
        if existing_staff:
            db.execute(
                "UPDATE staff SET employee_code=?, staff_name=?, mobile=?, email=?, department=?, "
                "designation=?, designation_id=?, reporting_manager=?, workflow_role=?, salary_type=?, "
                "salary_amount=?, ot_applicable=?, ot_rate_per_hour=?, holiday_pay_applicable=?, "
                "working_hours=?, joining_date=?, date_of_birth=?, gender=?, photo=?, status=?, "
                "aadhaar_number=?, pan_number=?, bank_account=?, bank_name=?, ifsc_code=?, "
                "branch_name=?, id_proof=?, aadhaar_document=?, pan_document=?, "
                "company_room_provided=?, company_food_provided=? WHERE id=?",
                values + (staff_id,),
            )
            saved_id = int(staff_id)
            flash(f"Employee updated. Employee Code: {employee_code}")
        else:
            db.execute(
                "INSERT INTO staff(employee_code, staff_name, mobile, email, department, designation, "
                "designation_id, reporting_manager, workflow_role, salary_type, salary_amount, "
                "ot_applicable, ot_rate_per_hour, holiday_pay_applicable, working_hours, joining_date, "
                "date_of_birth, gender, photo, status, "
                "aadhaar_number, pan_number, bank_account, bank_name, ifsc_code, branch_name, id_proof, "
                "aadhaar_document, pan_document, company_room_provided, company_food_provided) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            saved_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            flash(f"Employee saved. Employee Code: {employee_code}")
        if salary_type == "Monthly":
            _save_staff_salary_components(db, saved_id, components)
            _save_staff_travel_tiers(db, saved_id, travel_tiers)
        else:
            db.execute("DELETE FROM staff_salary_components WHERE staff_id=?", (saved_id,))
            db.execute("DELETE FROM staff_travel_tiers WHERE staff_id=?", (saved_id,))
        db.commit()
        return redirect(url_for("staff"))
    rows_raw = query_db(
        "SELECT s.*, d.designation_name AS designation_label "
        "FROM staff s LEFT JOIN designations d ON s.designation_id = d.id "
        "ORDER BY s.id DESC"
    )
    rows = []
    for r in rows_raw:
        row = dict(r)
        row["workflow_access"] = get_workflow_access_label(
            db, row.get("designation_id"), row.get("workflow_role")
        )
        if row.get("workflow_role"):
            row["workflow_access"] = row["workflow_role"]
        elif row.get("designation_id"):
            row["workflow_access"] = get_workflow_access_for_designation(
                db, row["designation_id"]
            )
        row["display_designation"] = row.get("designation_label") or row.get("designation") or "—"
        row["salary_components"] = _fetch_staff_salary_components(db, row["id"])
        row["travel_tiers"] = _fetch_staff_travel_tiers(db, row["id"])
        row["salary_increments"] = _fetch_staff_salary_increments(db, row["id"])
        rows.append(row)
    editing_basic_salary = ""
    for component in editing_components:
        if (component.get("component_name") or "").strip().lower() == "basic salary":
            editing_basic_salary = component.get("amount") or ""
            break
    if editing_basic_salary == "" and editing_staff and editing_staff["salary_type"] == "Monthly":
        editing_basic_salary = editing_staff["salary_amount"] or ""
    return render_template(
        "staff.html",
        rows=rows,
        designations=designations,
        departments=departments,
        staff_list=staff_list,
        next_employee_code=generate_employee_code(db),
        editing_staff=editing_staff,
        editing_components=editing_components,
        editing_travel_tiers=editing_travel_tiers,
        editing_salary_increments=editing_salary_increments,
        editing_basic_salary=editing_basic_salary,
        salary_component_options=STAFF_SALARY_COMPONENT_OPTIONS,
    )


@app.route("/api/staff-bonus/attendance-stats")
@login_required
def api_staff_bonus_attendance_stats():
    staff_id = request.args.get("staff_id", type=int)
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not staff_id or not year or not month:
        return jsonify({"error": "staff_id, year, and month are required"}), 400
    if month < 1 or month > 12:
        return jsonify({"error": "Invalid month"}), 400
    db = get_db()
    staff_row = db.execute(
        "SELECT id, employee_code, staff_name FROM staff WHERE id=?",
        (staff_id,),
    ).fetchone()
    if not staff_row:
        return jsonify({"error": "Employee not found"}), 404
    stats = compute_staff_bonus_attendance_stats(db, staff_id, year, month)
    period, _, _ = _bonus_period_bounds(year, month)
    existing = db.execute(
        "SELECT id, payment_status, final_amount FROM staff_bonus "
        "WHERE staff_id=? AND bonus_period=?",
        (staff_id, period),
    ).fetchone()
    return jsonify({
        "staff_id": staff_id,
        "employee_code": staff_row["employee_code"],
        "staff_name": staff_row["staff_name"],
        "bonus_period": period,
        **stats,
        "existing_bonus_id": existing["id"] if existing else None,
        "existing_payment_status": existing["payment_status"] if existing else None,
        "existing_final_amount": float(existing["final_amount"] or 0) if existing else None,
    })


@app.route("/staff-bonus", methods=["GET", "POST"])
@login_required
def staff_bonus():
    db = get_db()
    prepare_hr_bonus_db(db)
    active_tab = request.args.get("tab", "calculation")
    if active_tab not in ("calculation", "payment"):
        active_tab = "calculation"

    staff_options = query_db(
        "SELECT id, employee_code, staff_name, salary_type, salary_amount "
        "FROM staff WHERE status='Active' ORDER BY staff_name"
    )
    now = get_app_now(db)
    default_year = now.year
    default_month = now.month

    if request.method == "POST":
        form_action = request.form.get("form_action", "save_bonus").strip()

        if form_action == "mark_paid":
            bonus_id = request.form.get("bonus_id", type=int)
            if not bonus_id:
                flash("Invalid bonus record.")
                return redirect(url_for("staff_bonus", tab="payment"))
            row = db.execute(
                "SELECT id, payment_status FROM staff_bonus WHERE id=?",
                (bonus_id,),
            ).fetchone()
            if not row:
                flash("Bonus record not found.")
                return redirect(url_for("staff_bonus", tab="payment"))
            if (row["payment_status"] or "").lower() == "paid":
                flash("Bonus is already marked paid.")
                return redirect(url_for("staff_bonus", tab="payment"))
            paid_at = get_app_now(db).strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "UPDATE staff_bonus SET payment_status='paid', paid_at=? WHERE id=?",
                (paid_at, bonus_id),
            )
            db.commit()
            flash("Bonus marked as paid.")
            return redirect(url_for("staff_bonus", tab="payment"))

        staff_id = request.form.get("staff_id", type=int)
        year = request.form.get("bonus_year", type=int)
        month = request.form.get("bonus_month", type=int)
        method = (request.form.get("method") or "auto").strip().lower()
        if method not in ("auto", "manual"):
            method = "auto"
        remarks = request.form.get("remarks", "").strip()
        worked_days_raw = request.form.get("worked_days", "0").strip()
        leave_days_raw = request.form.get("leave_days", "0").strip()
        held_ot_raw = request.form.get("held_ot_hours", "0").strip()
        per_day_rate_raw = request.form.get("per_day_rate", "0").strip()
        manual_amount_raw = request.form.get("manual_amount", "0").strip()
        rounded_amount_raw = request.form.get("rounded_amount", "0").strip()

        if not staff_id or not year or not month:
            flash("Select employee, month, and year.")
            return redirect(url_for("staff_bonus", tab="calculation"))
        if month < 1 or month > 12:
            flash("Invalid month.")
            return redirect(url_for("staff_bonus", tab="calculation"))

        staff_row = db.execute("SELECT id FROM staff WHERE id=?", (staff_id,)).fetchone()
        if not staff_row:
            flash("Employee not found.")
            return redirect(url_for("staff_bonus", tab="calculation"))

        try:
            worked_days = float(worked_days_raw or 0)
            leave_days = float(leave_days_raw or 0)
            held_ot_hours = float(held_ot_raw or 0)
            per_day_rate = float(per_day_rate_raw or 0)
            manual_amount = float(manual_amount_raw or 0)
            rounded_amount = float(rounded_amount_raw or 0)
        except ValueError:
            flash("Enter valid numeric values.")
            return redirect(url_for("staff_bonus", tab="calculation"))

        if method == "auto":
            calculated_amount = round(per_day_rate * worked_days, 2)
        else:
            calculated_amount = round(manual_amount, 2)

        if rounded_amount <= 0:
            rounded_amount = calculated_amount
        final_amount = round(rounded_amount, 2)
        bonus_period, _, _ = _bonus_period_bounds(year, month)
        created_at = get_app_now(db).strftime("%Y-%m-%d %H:%M:%S")

        existing = db.execute(
            "SELECT id, payment_status FROM staff_bonus WHERE staff_id=? AND bonus_period=?",
            (staff_id, bonus_period),
        ).fetchone()
        if existing and (existing["payment_status"] or "").lower() == "paid":
            flash("Cannot modify a bonus that is already paid.")
            return redirect(url_for("staff_bonus", tab="payment"))

        if existing:
            db.execute(
                "UPDATE staff_bonus SET worked_days=?, leave_days=?, held_ot_hours=?, method=?, "
                "per_day_rate=?, calculated_amount=?, rounded_amount=?, final_amount=?, "
                "payment_status='pending', remarks=?, created_by=?, created_at=?, paid_at=NULL "
                "WHERE id=?",
                (
                    worked_days, leave_days, held_ot_hours, method,
                    per_day_rate, calculated_amount, rounded_amount, final_amount,
                    remarks, session.get("username", ""), created_at, existing["id"],
                ),
            )
            flash(f"Bonus updated for {bonus_period}. Payment status: pending.")
        else:
            db.execute(
                "INSERT INTO staff_bonus(staff_id, bonus_period, worked_days, leave_days, "
                "held_ot_hours, method, per_day_rate, calculated_amount, rounded_amount, "
                "final_amount, payment_status, remarks, created_by, created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    staff_id, bonus_period, worked_days, leave_days, held_ot_hours,
                    method, per_day_rate, calculated_amount, rounded_amount, final_amount,
                    "pending", remarks, session.get("username", ""), created_at,
                ),
            )
            flash(f"Bonus saved for {bonus_period}. Payment status: pending.")
        db.commit()
        return redirect(url_for("staff_bonus", tab="payment"))

    bonus_rows = query_db(
        "SELECT b.*, s.employee_code, s.staff_name FROM staff_bonus b "
        "JOIN staff s ON b.staff_id = s.id "
        "ORDER BY b.bonus_period DESC, b.id DESC"
    )
    payment_filter = request.args.get("payment_filter", "all")
    if payment_filter == "pending":
        bonus_rows = [r for r in bonus_rows if (r["payment_status"] or "").lower() == "pending"]
    elif payment_filter == "paid":
        bonus_rows = [r for r in bonus_rows if (r["payment_status"] or "").lower() == "paid"]

    return render_template(
        "staff_bonus.html",
        staff_options=staff_options,
        bonus_rows=bonus_rows,
        active_tab=active_tab,
        default_year=default_year,
        default_month=default_month,
        payment_filter=payment_filter,
        app_now_display=format_app_datetime(db=db),
    )


@app.route("/subcontract")
@login_required
def subcontract_dashboard():
    db = get_db()
    stat_cards = [
        {"label": "Active Workers", "value": _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM workers WHERE status='Active'")},
        {"label": "Subcontractors", "value": _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM subcontractors WHERE COALESCE(is_deleted, 0)=0")},
        {"label": "Pending Bills", "value": _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM subcontractor_bills WHERE approval_status IN ('Draft', 'Pending Checker', 'Pending Approval')")},
        {"label": "Pending Payments", "value": _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM subcontract_payments WHERE payment_status='Pending'")},
    ]
    modules = [
        {"endpoint": "workers", "label": "Workers", "icon": "fa-hard-hat", "description": "Labour worker registry & skills"},
        {"endpoint": "subcontractors", "label": "Subcontractor Creation", "icon": "fa-user-plus", "description": "Register new subcontractor firms"},
        {"endpoint": "subcontractors", "label": "Subcontractor List", "icon": "fa-list", "description": "Browse all active subcontractors"},
        {"endpoint": "attendance", "label": "Worker Attendance", "icon": "fa-calendar-day", "description": "Daily worker attendance on site"},
        {"endpoint": "timesheet", "label": "Worker Timesheet", "icon": "fa-stopwatch", "description": "Worker hours & productivity"},
        {"endpoint": "sub_billing_register", "label": "Subcontract Bills", "icon": "fa-file-invoice-dollar", "description": "RA bills & measurement sheets"},
        {"endpoint": "subcontract_payments", "label": "Subcontract Payments", "icon": "fa-hand-holding-dollar", "description": "Payment vouchers to subcontractors"},
    ]
    return _render_department_hub("Subcontract Dashboard", "Subcontract", stat_cards, modules, "Subcontract modules")


@app.route("/subcontractors", methods=["GET", "POST"])
@login_required
def subcontractors():
    db = get_db()
    _prepare_store_db(db)
    ensure_subcontractor_rate_tables(db)
    ensure_trades_table(db)
    projects = query_db(
        "SELECT id, project_code, project_name FROM projects ORDER BY project_name"
    )
    trades = get_active_trades()
    select_trade = request.args.get("select_trade", type=int)
    select_trade_name = None
    if select_trade:
        trade_row = query_db(
            "SELECT trade_name FROM trades WHERE id=? AND status='Active'",
            (select_trade,),
            one=True,
        )
        if trade_row:
            select_trade_name = trade_row["trade_name"]
    edit_id = request.args.get("edit", type=int)
    editing_subcontractor = None
    editing_manpower_rates = []
    editing_boq_rates = []
    editing_boq_project_id = None
    if edit_id:
        editing_subcontractor = query_db(
            "SELECT s.*, v.code AS vendor_code, v.name AS vendor_name, v.phone AS vendor_phone, "
            "v.gstin AS vendor_gstin, v.address AS vendor_address, v.vendor_types, v.trade_categories "
            "FROM subcontractors s "
            "LEFT JOIN vendors v ON s.vendor_id = v.id WHERE s.id=?",
            (edit_id,),
            one=True,
        )
        if not editing_subcontractor:
            flash("Subcontractor record not found.")
            return redirect(url_for("subcontractors"))
        editing_subcontractor = dict(editing_subcontractor)
        editing_subcontractor["normalized_rate_type"] = normalize_subcontractor_rate_type(
            editing_subcontractor.get("rate_type")
        )
        editing_subcontractor["vendor_trade_display"] = ", ".join(
            vendor_trade_categories_list(editing_subcontractor)
        ) or "—"
        editing_manpower_rates = query_db(
            "SELECT trade_name, rate_unit, working_hours, rate_amount, salary_amount "
            "FROM subcontractor_manpower_rates WHERE subcontractor_id=? ORDER BY trade_name",
            (edit_id,),
        )
        editing_boq_rates = query_db(
            "SELECT r.*, p.project_code, p.project_name FROM subcontractor_boq_rates r "
            "LEFT JOIN projects p ON r.project_id = p.id "
            "WHERE r.subcontractor_id=? ORDER BY r.line_no, r.id",
            (edit_id,),
        )
        if editing_boq_rates:
            editing_boq_project_id = editing_boq_rates[0]["project_id"]

    if request.method == "POST":
        form_action = request.form.get("form_action", "create").strip()
        if form_action == "add_trade":
            new_id = _create_trade_from_form(db)
            preserve_edit = request.form.get("subcontractor_id", type=int)
            if new_id:
                flash("Trade added and selected in the form.")
                redirect_kwargs = {"select_trade": new_id}
                if preserve_edit:
                    redirect_kwargs["edit"] = preserve_edit
                return redirect(
                    url_for("subcontractors", **redirect_kwargs) + "#add-subcontractor"
                )
            preserve_edit = request.form.get("subcontractor_id", type=int)
            if preserve_edit:
                return redirect(
                    url_for("subcontractors", edit=preserve_edit) + "#add-subcontractor"
                )
            return redirect(url_for("subcontractors") + "#add-subcontractor")
        if form_action == "delete":
            sub_id = request.form.get("subcontractor_id", type=int)
            if not sub_id:
                flash("Invalid subcontractor.")
                return redirect(url_for("subcontractors"))
            existing = query_db(
                "SELECT id, subcontractor_name FROM subcontractors WHERE id=?",
                (sub_id,),
                one=True,
            )
            if not existing:
                flash("Subcontractor record not found.")
                return redirect(url_for("subcontractors"))
            worker_count, request_count = _subcontractor_dependent_counts(db, sub_id)
            if worker_count or request_count:
                parts = []
                if worker_count:
                    parts.append(f"{worker_count} worker(s)")
                if request_count:
                    parts.append(f"{request_count} bill/payment request(s)")
                flash(
                    f"Cannot delete {existing['subcontractor_name']} — linked to "
                    f"{', '.join(parts)}. Set status to Inactive instead."
                )
                return redirect(url_for("subcontractors"))
            db.execute(
                "DELETE FROM subcontractor_manpower_rates WHERE subcontractor_id=?",
                (sub_id,),
            )
            db.execute(
                "DELETE FROM subcontractor_boq_rates WHERE subcontractor_id=?",
                (sub_id,),
            )
            if _table_exists(db, "dpr_manpower"):
                db.execute("DELETE FROM dpr_manpower WHERE subcontractor_id=?", (sub_id,))
            db.execute("DELETE FROM subcontractors WHERE id=?", (sub_id,))
            db.commit()
            flash(f"Subcontractor {existing['subcontractor_name']} deleted.")
            return redirect(url_for("subcontractors"))

        if form_action == "add_boq_rates":
            subcontractor_id = request.form.get("existing_subcontractor_id", "").strip()
            if not subcontractor_id.isdigit():
                flash("Select a subcontractor to add BOQ rates.")
                return redirect(url_for("subcontractors") + "#add-boq-rates")
            project_id, boq_rows = _parse_subcontractor_boq_rates()
            if not project_id:
                flash("Select a project for BOQ rates.")
                return redirect(url_for("subcontractors") + "#add-boq-rates")
            if not boq_rows:
                flash("Add at least one BOQ line item.")
                return redirect(url_for("subcontractors") + "#add-boq-rates")
            _insert_subcontractor_boq_rates(db, int(subcontractor_id), project_id, boq_rows)
            db.execute(
                "UPDATE subcontractors SET rate_type=? WHERE id=?",
                ("Measurement Based Contract", int(subcontractor_id)),
            )
            db.commit()
            flash(f"Added {len(boq_rows)} BOQ rate line(s) to subcontractor.")
            return redirect(url_for("subcontractors"))

        subcontractor_id_raw = request.form.get("subcontractor_id", "").strip()
        existing = None
        if subcontractor_id_raw.isdigit():
            existing = query_db(
                "SELECT * FROM subcontractors WHERE id=?",
                (int(subcontractor_id_raw),),
                one=True,
            )
            if not existing:
                flash("Subcontractor record not found.")
                return redirect(url_for("subcontractors"))

        vendor_id_raw = request.form.get("vendor_id", "").strip()
        if not vendor_id_raw.isdigit():
            flash("Select a vendor before creating a subcontractor.")
            if existing:
                return redirect(url_for("subcontractors", edit=existing["id"]) + "#add-subcontractor")
            return redirect(url_for("subcontractors") + "#add-subcontractor")
        vendor_id = int(vendor_id_raw)
        vendor_row = get_vendor(db, vendor_id)
        if not vendor_row:
            flash("Selected vendor not found.")
            return redirect(url_for("subcontractors") + "#add-subcontractor")
        if not vendor_is_subcontract_eligible(vendor_row):
            flash(
                "Selected vendor is not eligible for subcontract work. "
                "Set vendor type to Subcontractor, Labour Contractor, or Supplier + Subcontractor "
                "in Vendor Master first."
            )
            if existing:
                return redirect(url_for("subcontractors", edit=existing["id"]) + "#add-subcontractor")
            return redirect(url_for("subcontractors") + "#add-subcontractor")

        duplicate_vendor = query_db(
            "SELECT id, subcontractor_name FROM subcontractors WHERE vendor_id=? AND id!=?",
            (vendor_id, existing["id"] if existing else -1),
            one=True,
        )
        if duplicate_vendor:
            flash(
                f"Vendor already linked to subcontractor "
                f"{duplicate_vendor['subcontractor_name'] or duplicate_vendor['id']}."
            )
            if existing:
                return redirect(url_for("subcontractors", edit=existing["id"]) + "#add-subcontractor")
            return redirect(url_for("subcontractors") + "#add-subcontractor")

        subcontractor_name = (vendor_row.get("name") or "").strip()
        if not subcontractor_name:
            flash("Selected vendor has no name. Update the vendor master first.")
            return redirect(url_for("subcontractors") + "#add-subcontractor")

        subcontractor_code = subcontractor_code_from_vendor(vendor_row)
        if not subcontractor_code:
            flash("Selected vendor has no vendor code.")
            return redirect(url_for("subcontractors") + "#add-subcontractor")

        rate_type = normalize_subcontractor_rate_type(
            request.form.get("rate_type", "Labour Supply").strip()
        )
        status = request.form.get("status", "Active").strip()
        if existing:
            subcontractor_id = existing["id"]
            db.execute(
                "UPDATE subcontractors SET vendor_id=?, subcontractor_code=?, "
                "subcontractor_name=?, rate_type=?, status=? WHERE id=?",
                (
                    vendor_id,
                    subcontractor_code,
                    subcontractor_name,
                    rate_type,
                    status,
                    subcontractor_id,
                ),
            )
        else:
            cursor = db.execute(
                "INSERT INTO subcontractors("
                "vendor_id, subcontractor_code, subcontractor_name, rate_type, status"
                ") VALUES(?,?,?,?,?)",
                (
                    vendor_id,
                    subcontractor_code,
                    subcontractor_name,
                    rate_type,
                    status,
                ),
            )
            subcontractor_id = cursor.lastrowid

        rate_error = _sync_subcontractor_rates(
            db, subcontractor_id, rate_type, is_update=bool(existing)
        )
        if rate_error:
            flash(rate_error)
            if existing:
                return redirect(url_for("subcontractors", edit=subcontractor_id) + "#add-subcontractor")
            return redirect(url_for("subcontractors") + "#add-subcontractor")

        db.commit()
        if existing:
            flash(f"Subcontractor updated: {subcontractor_code or subcontractor_id}")
        else:
            flash(f"Subcontractor saved. Sub Contractor ID: {subcontractor_code}")
        return redirect(url_for("subcontractors"))

    rows_raw = query_db(
        "SELECT s.*, v.code AS vendor_code, v.name AS vendor_name, "
        "(SELECT COUNT(*) FROM subcontractor_manpower_rates m WHERE m.subcontractor_id=s.id) AS manpower_rate_count, "
        "(SELECT COUNT(*) FROM subcontractor_boq_rates b WHERE b.subcontractor_id=s.id) AS boq_rate_count "
        "FROM subcontractors s "
        "LEFT JOIN vendors v ON s.vendor_id = v.id "
        "ORDER BY s.id DESC"
    )
    rows = []
    for row in rows_raw:
        item = dict(row)
        item["rate_type_label"] = subcontractor_rate_type_label(item.get("rate_type"))
        rows.append(item)
    _prepare_store_db(db)
    subcontract_vendors = list_subcontract_eligible_vendors(db, active_only=True)
    for vendor in subcontract_vendors:
        vendor["vendor_types_display"] = ", ".join(vendor_types_list(vendor)) or "—"
        vendor["trade_categories_display"] = ", ".join(vendor_trade_categories_list(vendor)) or "—"
    return render_template(
        "subcontractors.html",
        rows=rows,
        vendors=subcontract_vendors,
        projects=projects,
        trades=trades,
        max_manpower_trades=MAX_MANPOWER_TRADES,
        rate_types=SUBCONTRACTOR_RATE_TYPE_CHOICES,
        editing_subcontractor=editing_subcontractor,
        editing_manpower_rates=editing_manpower_rates,
        editing_boq_rates=editing_boq_rates,
        editing_boq_project_id=editing_boq_project_id,
        select_trade_name=select_trade_name,
    )


@app.route("/api/subcontractors/preview-code")
@login_required
def api_subcontractor_preview_code():
    vendor_id = request.args.get("vendor_id", "").strip()
    if not vendor_id.isdigit():
        return jsonify({"code": ""})
    db = get_db()
    _prepare_store_db(db)
    vendor_row = get_vendor(db, int(vendor_id))
    if not vendor_row:
        return jsonify({"code": ""})
    return jsonify({"code": subcontractor_code_from_vendor(vendor_row)})


@app.route("/api/subcontractors/<int:subcontractor_id>/manpower-rates")
@login_required
def api_subcontractor_manpower_rates(subcontractor_id):
    rows = query_db(
        "SELECT trade_name, rate_unit, working_hours, rate_amount, salary_amount "
        "FROM subcontractor_manpower_rates WHERE subcontractor_id=? "
        "ORDER BY trade_name",
        (subcontractor_id,),
    )
    return jsonify([dict(row) for row in rows])


@app.route("/api/projects/<int:project_id>/boq-items")
@login_required
def api_project_boq_items(project_id):
    rows = query_db(
        "SELECT bi.id, bi.boq_id, bi.line_no, COALESCE(bi.item_code, '') AS item_code, "
        "COALESCE(bi.item_description, '') AS item_description, "
        "COALESCE(bi.quantity, 0) AS quantity, "
        "COALESCE(bi.unit, '') AS unit, "
        "COALESCE(bi.rate, 0) AS rate, "
        "COALESCE(bi.amount, 0) AS amount, "
        "COALESCE(bm.boq_number, '') AS boq_number "
        "FROM boq_items bi "
        "LEFT JOIN boq_master bm ON bi.boq_id = bm.id "
        "WHERE COALESCE(bi.project_id, bm.project_id)=? "
        "AND COALESCE(bi.is_deleted, 0)=0 AND COALESCE(bm.is_deleted, 0)=0 "
        "ORDER BY bm.id DESC, bi.line_no, bi.id",
        (project_id,),
    )
    return jsonify([dict(row) for row in rows])


@app.route("/clients", methods=["GET", "POST"])
@login_required
def clients():
    db = get_db()
    if request.method == "POST":
        if _create_client_from_form():
            flash("Client saved.")
        return redirect(url_for("clients"))
    rows = query_db("SELECT * FROM clients ORDER BY id DESC")
    next_client_code = generate_client_code(db)
    return render_template("clients.html", rows=rows, next_client_code=next_client_code)


def _create_client_from_form():
    company_name = request.form.get("company_name", "").strip()
    contact_person = request.form.get("contact_person", "").strip()
    client_name = request.form.get("client_name", "").strip() or company_name or contact_person
    mobile = request.form.get("mobile", "").strip()
    email = request.form.get("email", "").strip()
    address = request.form.get("address", "").strip()
    gst_number = request.form.get("gst_number", "").strip()
    pan_number = request.form.get("pan_number", "").strip()
    status = request.form.get("status", "Active").strip()
    if not company_name:
        flash("Company name is required.")
        return None
    db = get_db()
    client_code = generate_client_code(db)
    cursor = db.execute(
        "INSERT INTO clients(client_code, client_name, company_name, contact_person, mobile, email, "
        "address, gst_number, pan_number, status) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            client_code, client_name, company_name, contact_person, mobile, email,
            address, gst_number, pan_number, status,
        ),
    )
    db.commit()
    return cursor.lastrowid


def _handle_add_vendor_form(db, endpoint, form_hash="", redirect_kwargs=None):
    if request.form.get("form_action") != "add_vendor":
        return None
    try:
        vendor_id = save_vendor(db, request.form, None)
        db.commit()
        flash("Vendor saved and selected in the form.")
        kwargs = dict(redirect_kwargs or {})
        kwargs["select_vendor"] = vendor_id
        return redirect(url_for(endpoint, **kwargs) + form_hash)
    except (ValueError, sqlite3.IntegrityError) as exc:
        flash(str(exc) if str(exc) else "Unable to save vendor — code may already exist.")
        return redirect(url_for(endpoint, **(redirect_kwargs or {})) + form_hash)


def _handle_add_chart_head_form(db, endpoint, form_hash="", redirect_kwargs=None):
    if request.form.get("form_action") != "add_chart_head":
        return None
    try:
        head_id = save_chart_account(db, request.form, None)
        db.commit()
        flash("Account head saved and selected in the form.")
        kwargs = dict(redirect_kwargs or {})
        kwargs["select_chart_head"] = head_id
        return redirect(url_for(endpoint, **kwargs) + form_hash)
    except (ValueError, sqlite3.IntegrityError) as exc:
        flash(str(exc) if str(exc) else "Unable to save account head — code may already exist.")
        return redirect(url_for(endpoint, **(redirect_kwargs or {})) + form_hash)


@app.route("/api/staff/<int:staff_id>")
@login_required
def api_staff_detail(staff_id):
    row = query_db(
        "SELECT s.*, d.designation_name FROM staff s "
        "LEFT JOIN designations d ON s.designation_id = d.id WHERE s.id=?",
        (staff_id,),
        one=True,
    )
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dict(row))


def _build_project_hub_index(db, project_ids):
    """Aggregate BOQ, securities, and cost plans per project for the Project 360 hub."""
    if not project_ids:
        return {}
    ensure_boq_master_table(db)
    ensure_security_guarantees_tables(db)
    ensure_project_guarantees_table(db)
    prepare_cost_planning_db(db)
    placeholders = ",".join("?" * len(project_ids))
    hub = {
        pid: {"boqs": [], "securities": [], "cost_plans": []}
        for pid in project_ids
    }
    boq_rows = query_db(
        "SELECT id, boq_number, project_id, total_amount, line_count, approval_status, created_at "
        "FROM boq_master WHERE project_id IN ({}) AND COALESCE(is_deleted, 0)=0 "
        "ORDER BY id DESC".format(placeholders),
        tuple(project_ids),
    )
    for row in boq_rows:
        pid = row["project_id"]
        if pid in hub:
            hub[pid]["boqs"].append(dict(row))
    security_rows = query_db(
        _security_record_sql()
        + "WHERE s.project_id IN ({}) ORDER BY s.id DESC".format(placeholders),
        tuple(project_ids),
    )
    for row in security_rows:
        pid = row["project_id"]
        if pid in hub:
            hub[pid]["securities"].append(dict(row))
    for pid in project_ids:
        hub[pid]["cost_plans"] = list_cost_plans(db, pid)
    return hub


@app.route("/projects/dashboard")
@login_required
def projects_dashboard():
    """Legacy project dashboard — redirect to Command Centre dept workspace."""
    return redirect(url_for("department_portal", slug="projects"))


@app.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    db = get_db()
    module_id, table, endpoint = "project_creation", "projects", "projects"
    user_id = session.get("user_id")
    admin = is_admin_user()
    wf_ctx = {}
    clients = query_db(
        "SELECT id, client_name, company_name, contact_person FROM clients ORDER BY company_name, client_name"
    )
    edit_id = request.args.get("edit", type=int)
    view_project_id = request.args.get("view", type=int)
    editing_project = view_project = None

    project_sql = (
        "SELECT p.*, c.client_name, c.company_name FROM projects p "
        "LEFT JOIN clients c ON p.client_id = c.id WHERE p.id=?"
    )

    if edit_id:
        editing_project = query_db(project_sql, (edit_id,), one=True)
        if not editing_project:
            flash("Project record not found.")
            return redirect(url_for("projects"))
        editing_project = dict(editing_project)
        edit_role = get_edit_role_for_user(
            db, user_id, module_id, editing_project.get("approval_status"), admin
        )
        if not edit_role:
            flash("This record is locked and cannot be edited.")
            return redirect(url_for(endpoint, view=edit_id))
        wf_ctx = {"edit_role": edit_role}
    elif view_project_id:
        view_project = query_db(project_sql, (view_project_id,), one=True)
        if not view_project:
            flash("Project record not found.")
            return redirect(url_for("projects"))
        view_project = dict(view_project)
        wf_ctx = _workflow_view_context(
            module_id, view_project["id"], table, view_project.get("approval_status")
        )

    if request.method == "POST":
        if request.form.get("form_action") == "create_client":
            new_client_id = _create_client_from_form()
            if new_client_id:
                flash("Client saved. It has been selected in the project form.")
                return redirect(
                    url_for("projects", select_client=new_client_id) + "#add-project"
                )
            return redirect(url_for("projects") + "#add-project")

        if request.form.get("form_action") == "save_bill_submissions":
            bill_project_id = request.form.get("bill_project_id", "").strip()
            if not bill_project_id or not bill_project_id.isdigit():
                flash("Select a government project.")
                return redirect(url_for("projects") + "#client-bill-pending")
            project_row = db.execute(
                "SELECT id, project_type FROM projects WHERE id=?",
                (int(bill_project_id),),
            ).fetchone()
            if not project_row or project_row["project_type"] != "Government":
                flash("Bill submissions apply to government projects only.")
                return redirect(url_for("projects") + "#client-bill-pending")
            bill_submission_rows, bill_submission_error = _parse_client_bill_submissions_from_form()
            if bill_submission_error:
                flash(bill_submission_error)
                return redirect(
                    url_for("projects", bill_project=int(bill_project_id)) + "#client-bill-pending"
                )
            _save_project_client_bill_submissions(db, int(bill_project_id), bill_submission_rows)
            db.commit()
            flash("Client bill submissions saved.")
            return redirect(
                url_for("projects", bill_project=int(bill_project_id)) + "#client-bill-pending"
            )

        project_id = request.form.get("project_id", "").strip()
        existing_project = None
        if project_id:
            existing_project = db.execute(
                "SELECT * FROM projects WHERE id=?", (project_id,)
            ).fetchone()
            if not existing_project:
                flash("Project record not found.")
                return redirect(url_for("projects"))

        project_type = request.form.get("project_type", "Private").strip()
        project_name = request.form.get("project_name", "").strip()
        client_id = request.form.get("client_id", "") or None
        private_client_name = request.form.get("private_client_name", "").strip()
        location = request.form.get("location", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        approved_total_amount = request.form.get("approved_total_amount", "0").strip()
        status = request.form.get("status", "Active").strip()
        gov_department = request.form.get("gov_department", "").strip()
        agreement_number = request.form.get("agreement_number", "").strip()
        agreement_date = request.form.get("agreement_date", "").strip()
        completion_time = request.form.get("completion_time", "").strip()
        completion_mode = request.form.get("completion_mode", "months").strip()
        completion_months_raw = request.form.get("completion_months", "").strip()
        gov_completion_date = request.form.get("gov_completion_date", "").strip()
        quoted_amount = request.form.get("quoted_amount", "0").strip()
        security_deposit_pct = request.form.get("security_deposit_pct", "0").strip()
        guarantee_type = request.form.get("guarantee_type", "").strip()
        bank_guarantee_number = request.form.get("bank_guarantee_number", "").strip()
        bank_guarantee_issued_date = request.form.get("bank_guarantee_issued_date", "").strip()
        bank_guarantee_expiry_date = request.form.get("bank_guarantee_expiry_date", "").strip()
        bank_guarantee_amount = request.form.get("bank_guarantee_amount", "0").strip()
        treasury_deposit_number = request.form.get("treasury_deposit_number", "").strip()
        security_deposit_amount = request.form.get("security_deposit_amount", "0").strip()
        security_deposit_issued_date = request.form.get("security_deposit_issued_date", "").strip()
        security_deposit_maturity_date = request.form.get("security_deposit_maturity_date", "").strip()
        work_order_number = request.form.get("work_order_number", "").strip()
        work_order_date = request.form.get("work_order_date", "").strip()
        work_order_amount = request.form.get("work_order_amount", "0").strip()
        project_contact_person = request.form.get("project_contact_person", "").strip()

        if not project_name:
            flash("Project name is required.")
            return redirect(url_for("projects"))

        if project_type == "Government" and not gov_department:
            flash("Select a government department.")
            return redirect(url_for("projects") + "#add-project")

        guarantee_rows, guarantee_error = _parse_project_guarantees_from_form()
        if guarantee_error:
            flash(guarantee_error)
            return redirect(url_for("projects"))

        bill_submission_rows = []
        bill_submission_error = None

        try:
            approved_total_val = float(approved_total_amount or 0)
            quoted_val = float(quoted_amount or 0)
            sd_pct_val = float(security_deposit_pct or 0)
            bg_amount_val = float(bank_guarantee_amount or 0)
            sd_amount_val = float(security_deposit_amount or 0)
            wo_amount_val = float(work_order_amount or 0)
        except ValueError:
            flash("Enter valid numeric amounts.")
            return redirect(url_for("projects"))

        for upload_field in (
            "agreement_document",
            "bank_guarantee_document",
            "security_deposit_document",
            "work_order_document",
        ):
            upload_error = _validate_project_upload(request.files.get(upload_field))
            if upload_error:
                flash(upload_error)
                return redirect(url_for("projects"))

        agreement_document = save_file(request.files.get("agreement_document"), PROJECT_DOCS_DIR)
        bank_guarantee_document = save_file(
            request.files.get("bank_guarantee_document"), PROJECT_DOCS_DIR
        )
        security_deposit_document = save_file(
            request.files.get("security_deposit_document"), PROJECT_DOCS_DIR
        )
        work_order_document = save_file(request.files.get("work_order_document"), PROJECT_DOCS_DIR)

        project_code = (
            existing_project["project_code"]
            if existing_project and existing_project["project_code"]
            else generate_project_code(db, project_name)
        )
        if project_type == "Government":
            private_client_name = ""
            client_id = None
            work_order_number = ""
            work_order_date = ""
            wo_amount_val = 0
            work_order_document = ""
            project_contact_person = ""
            agreement_number = ""
            agreement_date = ""
            agreement_document = ""
            completion_months_val = None
            end_date, completion_time, completion_months_val, completion_mode = _apply_gov_completion_fields(
                start_date, end_date, completion_mode, completion_months_raw, gov_completion_date,
            )
            # Legacy columns: mirror first guarantee row of each kind for Project 360 / reports
            guarantee_type = ""
            bank_guarantee_number = ""
            bank_guarantee_issued_date = ""
            bank_guarantee_expiry_date = ""
            bg_amount_val = 0
            treasury_deposit_number = ""
            security_deposit_issued_date = ""
            security_deposit_maturity_date = ""
            bank_guarantee_document = ""
            security_deposit_document = ""
            for grow in guarantee_rows or []:
                gtype = grow.get("guarantee_type")
                if gtype in ("Bank Guarantee", "Performance Guarantee") and not guarantee_type:
                    guarantee_type = gtype
                    bank_guarantee_number = grow.get("bank_guarantee_number") or ""
                    bank_guarantee_issued_date = grow.get("bank_guarantee_issued_date") or ""
                    bank_guarantee_expiry_date = grow.get("bank_guarantee_expiry_date") or ""
                    bg_amount_val = float(grow.get("amount") or 0)
                    bank_guarantee_document = grow.get("document_filename") or ""
                elif gtype == "Treasury Deposit" and not treasury_deposit_number:
                    treasury_deposit_number = grow.get("treasury_deposit_number") or ""
                    security_deposit_issued_date = grow.get("issued_date") or ""
                    security_deposit_maturity_date = grow.get("maturity_date") or ""
                    if float(grow.get("amount") or 0) > 0:
                        sd_amount_val = float(grow.get("amount") or 0)
                    security_deposit_document = grow.get("document_filename") or ""
            if existing_project:
                if not bank_guarantee_document:
                    bank_guarantee_document = existing_project.get("bank_guarantee_document") or ""
                if not security_deposit_document:
                    security_deposit_document = existing_project.get("security_deposit_document") or ""
            else:
                agreement_document = ""
        else:
            guarantee_rows = []
            bill_submission_rows = []
            gov_department = ""
            agreement_number = ""
            agreement_date = ""
            completion_time = ""
            completion_months_val = None
            completion_mode = ""
            gov_completion_date = ""
            quoted_val = wo_amount_val or approved_total_val
            sd_pct_val = 0
            guarantee_type = ""
            bank_guarantee_number = ""
            bank_guarantee_issued_date = ""
            bank_guarantee_expiry_date = ""
            bg_amount_val = 0
            treasury_deposit_number = ""
            sd_amount_val = 0
            security_deposit_issued_date = ""
            security_deposit_maturity_date = ""
            agreement_document = ""
            bank_guarantee_document = ""
            security_deposit_document = ""
            if existing_project:
                work_order_document = (
                    work_order_document or existing_project["work_order_document"] or ""
                )
            else:
                work_order_document = work_order_document or ""

        project_values = (
            project_name, project_type, client_id, private_client_name, location,
            start_date, end_date, "", approved_total_val, approved_total_val, status, gov_department,
            agreement_number, agreement_date, completion_time, completion_months_val, completion_mode,
            quoted_val, sd_pct_val,
            guarantee_type, bank_guarantee_number, bank_guarantee_issued_date,
            bank_guarantee_expiry_date, bg_amount_val, treasury_deposit_number, sd_amount_val,
            security_deposit_issued_date, security_deposit_maturity_date, agreement_document,
            bank_guarantee_document, security_deposit_document, work_order_number,
            work_order_date, wo_amount_val, project_contact_person, work_order_document,
        )
        username = session.get("username", "")
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if existing_project:
            edit_role = get_edit_role_for_user(
                db, user_id, module_id, existing_project["approval_status"], admin
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=project_id))
            db.execute(
                "UPDATE projects SET project_name=?, project_type=?, client_id=?, private_client_name=?, "
                "location=?, start_date=?, end_date=?, project_manager=?, budget=?, approved_total_amount=?, "
                "status=?, gov_department=?, agreement_number=?, agreement_date=?, completion_time=?, "
                "completion_months=?, completion_mode=?, "
                "quoted_amount=?, security_deposit_pct=?, guarantee_type=?, bank_guarantee_number=?, "
                "bank_guarantee_issued_date=?, bank_guarantee_expiry_date=?, bank_guarantee_amount=?, "
                "treasury_deposit_number=?, security_deposit_amount=?, security_deposit_issued_date=?, "
                "security_deposit_maturity_date=?, agreement_document=?, bank_guarantee_document=?, "
                "security_deposit_document=?, work_order_number=?, work_order_date=?, work_order_amount=?, "
                "project_contact_person=?, work_order_document=?, modified_by=?, modified_at=? WHERE id=?",
                project_values + (username, now_ts, project_id),
            )
            save_err = _save_project_guarantees(
                db, int(project_id), guarantee_rows, existing_project=existing_project,
            )
            if save_err:
                flash(save_err)
                return redirect(url_for("projects", edit=project_id) + "#add-project")
            _complete_module_save(db, module_id, table, int(project_id), edit_role)
            return redirect(url_for(endpoint, view=project_id))

        db.execute(
            "INSERT INTO projects("
            "project_code, project_name, project_type, client_id, private_client_name, location, "
            "start_date, end_date, project_manager, budget, approved_total_amount, status, "
            "gov_department, agreement_number, "
            "agreement_date, completion_time, completion_months, completion_mode, "
            "quoted_amount, security_deposit_pct, guarantee_type, "
            "bank_guarantee_number, bank_guarantee_issued_date, bank_guarantee_expiry_date, "
            "bank_guarantee_amount, treasury_deposit_number, security_deposit_amount, "
            "security_deposit_issued_date, security_deposit_maturity_date, agreement_document, "
            "bank_guarantee_document, security_deposit_document, work_order_number, work_order_date, "
            "work_order_amount, project_contact_person, work_order_document, created_by, created_at, "
            "approval_status"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (project_code,) + project_values + (username, now_ts, RECORD_PENDING_CHECKER),
        )
        new_project_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        save_err = _save_project_guarantees(db, new_project_id, guarantee_rows)
        if save_err:
            flash(save_err)
            return redirect(url_for("projects") + "#add-project")
        create_approval_request(
            db, module_id, new_project_id, table, username, user_id
        )
        db.commit()
        flash(f"Project saved — Pending Checker. Project Number: {project_code}")
        return redirect(url_for(endpoint, view=new_project_id))

    rows = query_db(
        "SELECT p.*, c.client_name, c.company_name FROM projects p "
        "LEFT JOIN clients c ON p.client_id = c.id ORDER BY p.id DESC"
    )
    project_ids = [row["id"] for row in rows]
    hub_index = _build_project_hub_index(db, project_ids)
    if view_project_id and view_project_id not in project_ids and not view_project:
        flash("Project record not found.")
        return redirect(url_for("projects"))
    next_project_code = "Auto from name"
    selected_client_id = request.args.get("select_client", type=int)
    if editing_project and not selected_client_id:
        selected_client_id = editing_project["client_id"]
    show_project_form = bool(editing_project or selected_client_id)
    bill_project_id = request.args.get("bill_project", type=int)
    if bill_project_id:
        module_active_anchor = "client-bill-pending"
    elif show_project_form:
        module_active_anchor = "add-project"
    else:
        module_active_anchor = "project-list"
    ensure_project_guarantees_table(db)
    project_guarantees = []
    pending_bill_options = []
    project_bill_submissions = []
    bill_submission_summary = _bill_submission_summary([])
    gov_projects = query_db(
        "SELECT id, project_code, project_name, gov_department FROM projects "
        "WHERE project_type='Government' ORDER BY project_name, id DESC"
    )
    if editing_project:
        project_guarantees = _load_project_guarantees(db, editing_project["id"])
        if not project_guarantees:
            project_guarantees = _legacy_project_guarantee_rows(editing_project)
        pending_bill_options = _list_project_pending_bills(db, editing_project["id"])
    if bill_project_id:
        project_bill_submissions = _load_project_client_bill_submissions(db, bill_project_id)
        bill_submission_summary = _bill_submission_summary(project_bill_submissions)
    return render_template(
        "projects.html",
        rows=rows,
        clients=clients,
        gov_departments=GOV_DEPARTMENTS,
        gov_projects=gov_projects,
        bill_project_id=bill_project_id,
        guarantee_types=GUARANTEE_TYPES,
        project_guarantee_types=PROJECT_GUARANTEE_TYPES,
        project_guarantees=project_guarantees,
        pending_bill_options=pending_bill_options,
        project_bill_submissions=project_bill_submissions,
        bill_submission_summary=bill_submission_summary,
        next_project_code=next_project_code,
        selected_client_id=selected_client_id,
        editing_project=editing_project,
        view_project=view_project,
        hub_index=hub_index,
        view_project_id=view_project_id,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
        module_id=module_id,
        show_project_form=show_project_form,
        module_active_anchor=module_active_anchor,
    )


def _worker_dependent_counts(db, worker_id):
    attendance = db.execute(
        "SELECT COUNT(*) AS c FROM attendance "
        "WHERE worker_id=? AND COALESCE(worker_source, 'worker')='worker'",
        (worker_id,),
    ).fetchone()["c"]
    salary = db.execute(
        "SELECT COUNT(*) AS c FROM salary WHERE worker_id=?",
        (worker_id,),
    ).fetchone()["c"]
    dpr_count = 0
    if _table_exists(db, "dpr_manpower"):
        dpr_count = db.execute(
            "SELECT COUNT(*) AS c FROM dpr_manpower WHERE worker_id=?",
            (worker_id,),
        ).fetchone()["c"]
    return int(attendance or 0), int(salary or 0), int(dpr_count or 0)


def get_subcontractor_manpower_rate(subcontractor_id, trade_name):
    """Look up salary and hours for a subcontractor trade."""
    trade_name = (trade_name or "").strip()
    if not subcontractor_id or not trade_name:
        return None
    return query_db(
        "SELECT trade_name, rate_unit, working_hours, rate_amount, salary_amount "
        "FROM subcontractor_manpower_rates "
        "WHERE subcontractor_id=? AND trade_name=?",
        (subcontractor_id, trade_name),
        one=True,
    )


@app.route("/workers", methods=["GET", "POST"])
@login_required
def workers():
    db = get_db()
    prepare_workers_page_db(db)
    subcontractors = query_db(
        "SELECT id, subcontractor_name, subcontractor_code FROM subcontractors "
        "ORDER BY subcontractor_name"
    )
    edit_id = request.args.get("edit", type=int)
    editing_worker = None
    if edit_id:
        editing_worker = query_db(
            "SELECT * FROM workers WHERE id=? "
            "AND COALESCE(worker_category, 'Company Staff') = 'Sub Contractor Staff'",
            (edit_id,),
            one=True,
        )
        if not editing_worker:
            flash("Subcontractor worker record not found.")
            return redirect(url_for("workers"))

    if request.method == "POST":
        form_action = request.form.get("form_action", "save").strip()
        if form_action == "delete":
            worker_id = request.form.get("worker_id", type=int)
            if not worker_id:
                flash("Invalid worker.")
                return redirect(url_for("workers"))
            existing = query_db(
                "SELECT id, worker_name FROM workers WHERE id=? "
                "AND COALESCE(worker_category, 'Company Staff') = 'Sub Contractor Staff'",
                (worker_id,),
                one=True,
            )
            if not existing:
                flash("Worker record not found.")
                return redirect(url_for("workers"))
            att_count, sal_count, dpr_count = _worker_dependent_counts(db, worker_id)
            if att_count or sal_count or dpr_count:
                parts = []
                if att_count:
                    parts.append(f"{att_count} attendance record(s)")
                if sal_count:
                    parts.append(f"{sal_count} salary record(s)")
                if dpr_count:
                    parts.append(f"{dpr_count} DPR manpower link(s)")
                flash(
                    f"Cannot delete {existing['worker_name']} — linked to "
                    f"{', '.join(parts)}. Set status to Inactive instead."
                )
                return redirect(url_for("workers"))
            db.execute("DELETE FROM workers WHERE id=?", (worker_id,))
            db.commit()
            flash(f"Worker {existing['worker_name']} deleted.")
            return redirect(url_for("workers"))

        worker_name = request.form.get("worker_name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        date_of_birth = request.form.get("date_of_birth", "").strip()
        gender = request.form.get("gender", "").strip()
        aadhaar_number = request.form.get("aadhaar_number", "").strip()
        pan_number = request.form.get("pan_number", "").strip()
        trade_name = request.form.get("trade_name", "").strip()
        subcontractor_id = request.form.get("subcontractor_id", "").strip()
        joining_date = request.form.get("joining_date", "").strip()
        status = request.form.get("status", "Active").strip()
        worker_category = "Sub Contractor Staff"

        worker_id_raw = request.form.get("worker_id", "").strip()
        existing = None
        if worker_id_raw.isdigit():
            existing = query_db(
                "SELECT * FROM workers WHERE id=? "
                "AND COALESCE(worker_category, 'Company Staff') = 'Sub Contractor Staff'",
                (int(worker_id_raw),),
                one=True,
            )
            if not existing:
                flash("Worker record not found.")
                return redirect(url_for("workers"))

        if not worker_name:
            flash("Worker name is required.")
            if existing:
                return redirect(url_for("workers", edit=existing["id"]) + "#add-worker")
            return redirect(url_for("workers") + "#add-worker")
        if not subcontractor_id or not str(subcontractor_id).isdigit():
            flash("Select a valid subcontractor first.")
            if existing:
                return redirect(url_for("workers", edit=existing["id"]) + "#add-worker")
            return redirect(url_for("workers") + "#add-worker")
        subcontractor_id_int = int(subcontractor_id)
        if not trade_name:
            flash("Select a trade from the subcontractor manpower rates.")
            if existing:
                return redirect(url_for("workers", edit=existing["id"]) + "#add-worker")
            return redirect(url_for("workers") + "#add-worker")

        rate_row = get_subcontractor_manpower_rate(subcontractor_id_int, trade_name)
        if not rate_row:
            flash("Selected trade is not configured on the subcontractor manpower rates.")
            if existing:
                return redirect(url_for("workers", edit=existing["id"]) + "#add-worker")
            return redirect(url_for("workers") + "#add-worker")

        rate_row = dict(rate_row)
        designation = trade_name
        rate_unit = (rate_row.get("rate_unit") or "Day").strip()
        salary_type = "Daily" if rate_unit == "Day" else "Hourly"
        salary_amount_val = float(rate_row.get("salary_amount") or 0)
        working_hours_val = float(rate_row.get("working_hours") or 0)

        try:
            photo = save_file(request.files.get("photo"), PHOTOS_DIR)
            id_proof = save_file(request.files.get("id_proof"), WORKER_DOCS_DIR)
            aadhaar_document = save_file(request.files.get("aadhaar_document"), WORKER_DOCS_DIR)
            pan_document = save_file(request.files.get("pan_document"), WORKER_DOCS_DIR)

            if existing:
                existing_row = dict(existing)
                photo = photo or existing_row.get("photo")
                id_proof = id_proof or existing_row.get("id_proof")
                aadhaar_document = aadhaar_document or existing_row.get("aadhaar_document")
                pan_document = pan_document or existing_row.get("pan_document")
                worker_code = existing_row.get("worker_code")
                db.execute(
                    "UPDATE workers SET worker_code=?, worker_name=?, mobile=?, date_of_birth=?, gender=?, "
                    "aadhaar_number=?, pan_number=?, "
                    "photo=?, id_proof=?, aadhaar_document=?, pan_document=?, worker_category=?, designation=?, "
                    "salary_type=?, salary_amount=?, ot_applicable=?, working_hours=?, subcontractor_id=?, "
                    "joining_date=?, status=? WHERE id=?",
                    (
                        worker_code, worker_name, mobile, date_of_birth, gender, aadhaar_number, pan_number,
                        photo, id_proof, aadhaar_document, pan_document,
                        worker_category, designation, salary_type, salary_amount_val,
                        "No", working_hours_val, subcontractor_id_int, joining_date, status,
                        existing_row["id"],
                    ),
                )
                flash(f"Worker updated: {worker_code or existing_row['id']}")
            else:
                worker_code = generate_worker_code(db, worker_category, subcontractor_id_int)
                db.execute(
                    "INSERT INTO workers(worker_code, worker_name, mobile, date_of_birth, gender, aadhaar_number, pan_number, "
                    "photo, id_proof, aadhaar_document, pan_document, worker_category, designation, "
                    "salary_type, salary_amount, ot_applicable, working_hours, subcontractor_id, "
                    "joining_date, status) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        worker_code, worker_name, mobile, date_of_birth, gender, aadhaar_number, pan_number,
                        photo, id_proof, aadhaar_document, pan_document,
                        worker_category, designation, salary_type, salary_amount_val,
                        "No", working_hours_val, subcontractor_id_int, joining_date, status,
                    ),
                )
                flash(f"Worker saved. Worker ID: {worker_code}")

            db.commit()
        except sqlite3.OperationalError as exc:
            db.rollback()
            flash(f"Could not save worker — database needs an update. Contact admin. ({exc})")
            if existing:
                return redirect(url_for("workers", edit=existing["id"]) + "#add-worker")
            return redirect(url_for("workers") + "#add-worker")
        except (TypeError, ValueError) as exc:
            db.rollback()
            flash(f"Could not save worker — check salary/rate values. ({exc})")
            return redirect(url_for("workers") + "#add-worker")
        return redirect(url_for("workers"))

    rows = query_db(
        "SELECT w.*, s.subcontractor_name, s.subcontractor_code FROM workers w "
        "LEFT JOIN subcontractors s ON w.subcontractor_id = s.id "
        "WHERE COALESCE(w.worker_category, 'Company Staff') = 'Sub Contractor Staff' "
        "ORDER BY w.id DESC"
    )
    subcontractor_options = []
    for item in subcontractors:
        subcontractor_options.append({
            "id": item["id"],
            "subcontractor_name": item["subcontractor_name"],
            "subcontractor_code": item["subcontractor_code"],
            "next_worker_code": generate_worker_code(db, "Sub Contractor Staff", item["id"]),
        })
    default_sub_code = ""
    if subcontractor_options:
        default_sub_code = subcontractor_options[0]["next_worker_code"]
    return render_template(
        "workers.html",
        rows=rows,
        subcontractors=subcontractor_options,
        next_worker_code=default_sub_code,
        editing_worker=editing_worker,
    )


@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    module_id, table, endpoint = "daily_timesheet", "attendance", "attendance"
    monthly_module_id = MONTHLY_ATTENDANCE_MODULE_ID
    monthly_table = MONTHLY_ATTENDANCE_TABLE
    db = get_db()
    ensure_attendance_master_schema(db)
    ensure_staff_monthly_attendance_schema(db)
    db.commit()
    record_sql = (
        "SELECT a.*, "
        "COALESCE(w.worker_name, s.staff_name) AS worker_name, "
        "COALESCE(w.worker_code, s.employee_code) AS worker_code, "
        "p.project_name, p.project_code, "
        "t.trade_name, ad.designation_name "
        "FROM attendance a "
        f"{ATTENDANCE_WORKER_JOIN_SQL} "
        "LEFT JOIN projects p ON a.project_id = p.id "
        f"{ATTENDANCE_MASTER_JOIN_SQL} "
        "WHERE a.id=?"
    )
    attendance_workers = get_attendance_form_worker_data()
    monthly_staff = list_monthly_staff_for_attendance(db)
    monthly_rows = list_monthly_attendance_records(db)
    projects = get_attendance_project_options()
    trades = get_active_trades()
    designations = get_active_designations()
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_monthly_id = request.args.get("view_monthly", type=int)
    edit_monthly_id = request.args.get("edit_monthly", type=int)
    attendance_mode = request.args.get("mode", "daily")
    select_trade = request.args.get("select_trade", type=int)
    select_designation = request.args.get("select_designation", type=int)
    subcontractor_nav = request.args.get("nav") == "subcontract"
    if subcontractor_nav:
        attendance_mode = "daily"
    view_record = edit_record = view_monthly_record = edit_monthly_record = None
    edit_worker_ctx = {"staff_type": "", "subcontractor_id": ""}
    monthly_wf_ctx = {}
    wf_ctx = {}
    if view_id:
        view_record = query_db(record_sql, (view_id,), one=True)
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = query_db(record_sql, (edit_id,), one=True)
        if edit_record:
            edit_role = get_edit_role_for_user(
                get_db(), session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}
            edit_worker_ctx = get_attendance_edit_worker_context(edit_record)
            attendance_mode = "daily"
    elif view_monthly_id:
        view_monthly_record = get_monthly_attendance_record(db, view_monthly_id)
        if view_monthly_record:
            monthly_wf_ctx = _workflow_view_context(
                monthly_module_id,
                view_monthly_record["id"],
                monthly_table,
                view_monthly_record["approval_status"],
            )
            attendance_mode = "monthly"
    elif edit_monthly_id:
        edit_monthly_record = get_monthly_attendance_record(db, edit_monthly_id)
        if edit_monthly_record:
            edit_role = get_edit_role_for_user(
                get_db(), session.get("user_id"), monthly_module_id,
                edit_monthly_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This monthly record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view_monthly=edit_monthly_id))
            monthly_wf_ctx = {"edit_role": edit_role}
            attendance_mode = "monthly"
    if request.method == "POST":
        form_action = request.form.get("form_action", "save").strip()
        db = get_db()
        if form_action == "add_trade":
            new_id = _create_trade_from_form(db)
            if new_id:
                flash("Trade added and selected in the form.")
                return redirect(
                    url_for(endpoint, select_trade=new_id) + "#add-attendance"
                )
            return redirect(url_for(endpoint) + "#add-attendance")
        if form_action == "add_designation":
            new_id = _create_designation_from_form(db)
            if new_id:
                flash("Designation added and selected in the form.")
                return redirect(
                    url_for(endpoint, select_designation=new_id) + "#add-attendance"
                )
            return redirect(url_for(endpoint) + "#add-attendance")
        if form_action == "save_monthly":
            try:
                if request.form.get("record_id", "").strip():
                    ctx = _module_edit_context(
                        monthly_module_id, monthly_table, endpoint
                    )
                    if ctx[0] == "redirect":
                        return redirect(ctx[1] + "?mode=monthly#monthly-attendance")
                    rid, edit_role = ctx
                    save_monthly_attendance_from_form(
                        db,
                        request.form,
                        username=session.get("username", ""),
                        record_id=rid,
                    )
                    _complete_module_save(
                        db, monthly_module_id, monthly_table, rid, edit_role
                    )
                    db.commit()
                    flash("Monthly attendance updated.")
                    return redirect(url_for(endpoint, mode="monthly") + "#monthly-attendance")
                new_id = save_monthly_attendance_from_form(
                    db,
                    request.form,
                    username=session.get("username", ""),
                )
                create_approval_request(
                    db, monthly_module_id, new_id, monthly_table,
                    session.get("username", ""), session.get("user_id")
                )
                db.commit()
                flash("Monthly attendance saved. Status: Pending Checker.")
                return redirect(url_for(endpoint, mode="monthly") + "#monthly-attendance")
            except ValueError as exc:
                flash(str(exc))
                return redirect(url_for(endpoint, mode="monthly") + "#monthly-attendance")

        if form_action == "save_sub_bulk":
            try:
                saved_count = save_bulk_subcontractor_attendance(
                    db,
                    request.form,
                    username=session.get("username", ""),
                    create_approval_request=create_approval_request,
                    module_id=module_id,
                    table=table,
                    user_id=session.get("user_id"),
                )
                db.commit()
                flash(
                    f"Saved {saved_count} attendance record(s). Status: Pending Checker."
                )
                nav_q = "?nav=subcontract" if subcontractor_nav else ""
                return redirect(url_for(endpoint) + nav_q + "#sub-bulk-attendance")
            except ValueError as exc:
                flash(str(exc))
                nav_q = "?nav=subcontract" if subcontractor_nav else ""
                return redirect(url_for(endpoint) + nav_q + "#sub-bulk-attendance")

        worker_ref = request.form.get("worker_id", "")
        worker_id, worker_source = parse_attendance_worker_ref(worker_ref)
        project_id = request.form.get("project_id", "")
        attendance_date = request.form.get("attendance_date", "").strip()
        in_time = request.form.get("in_time", "").strip()
        out_time = request.form.get("out_time", "").strip()
        break_hours = request.form.get("break_hours", "0").strip()
        status = request.form.get("status", "Present").strip()
        trade_id = request.form.get("trade_id", "").strip() or None
        designation_id = request.form.get("designation_id", "").strip() or None
        if worker_id:
            master_ids = attendance_master_ids_for_worker(worker_id, worker_source)
            if not designation_id and master_ids.get("designation_id"):
                designation_id = str(master_ids["designation_id"])
            if not trade_id and master_ids.get("trade_id"):
                trade_id = str(master_ids["trade_id"])
        record_id = request.form.get("record_id", "").strip()
        try:
            start_dt = datetime.strptime(in_time, "%H:%M")
            end_dt = datetime.strptime(out_time, "%H:%M")
            break_hours_val = float(break_hours or 0)
            total_hours = (end_dt - start_dt).seconds / 3600 - break_hours_val
            if total_hours < 0:
                total_hours += 24
            ot_hours = max(total_hours - 8, 0)
        except Exception:
            flash("Enter valid attendance time values.")
            return redirect(url_for(endpoint))
        if record_id:
            ctx = _module_edit_context(module_id, table, endpoint)
            if ctx[0] == "redirect":
                return redirect(ctx[1])
            rid, edit_role = ctx
            db.execute(
                "UPDATE attendance SET worker_id=?, worker_source=?, project_id=?, attendance_date=?, "
                "in_time=?, out_time=?, break_hours=?, total_hours=?, ot_hours=?, status=?, "
                "trade_id=?, designation_id=? WHERE id=?",
                (
                    worker_id, worker_source, project_id or None, attendance_date,
                    in_time, out_time, break_hours_val, total_hours, ot_hours, status,
                    trade_id, designation_id, rid,
                ),
            )
            _complete_module_save(db, module_id, table, rid, edit_role)
            return redirect(url_for(endpoint))
        db.execute(
            "INSERT INTO attendance(worker_id, worker_source, project_id, attendance_date, "
            "in_time, out_time, break_hours, total_hours, ot_hours, status, approval_status, "
            "trade_id, designation_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                worker_id, worker_source, project_id or None, attendance_date,
                in_time, out_time, break_hours_val, total_hours, ot_hours, status,
                "Pending Checker", trade_id, designation_id,
            ),
        )
        record_id_new = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        create_approval_request(
            db, module_id, record_id_new, table,
            session.get("username", ""), session.get("user_id")
        )
        db.commit()
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows_sql = (
        "SELECT a.*, "
        "COALESCE(w.worker_name, s.staff_name) AS worker_name, "
        "COALESCE(w.worker_code, s.employee_code) AS worker_code, "
        "p.project_name, p.project_code, "
        "t.trade_name, ad.designation_name "
        "FROM attendance a "
        f"{ATTENDANCE_WORKER_JOIN_SQL} "
        "LEFT JOIN projects p ON a.project_id = p.id "
        f"{ATTENDANCE_MASTER_JOIN_SQL} "
    )
    if subcontractor_nav:
        rows_sql += (
            "WHERE COALESCE(w.worker_category, '') = 'Sub Contractor Staff' "
            "ORDER BY a.id DESC"
        )
    else:
        rows_sql += "ORDER BY a.id DESC"
    rows = query_db(rows_sql)
    return render_template(
        "attendance.html",
        rows=rows,
        monthly_rows=monthly_rows,
        monthly_staff=monthly_staff,
        company_staff=attendance_workers["company_staff"],
        subcontractors=attendance_workers["subcontractors"],
        subcontractor_workers=attendance_workers["subcontractor_workers"],
        projects=projects,
        trades=trades,
        designations=designations,
        select_trade=select_trade,
        select_designation=select_designation,
        attendance_mode=attendance_mode,
        subcontractor_nav=subcontractor_nav,
        sub_attendance_statuses=SUBCONTRACTOR_ATTENDANCE_STATUSES,
        view_record=view_record,
        edit_record=edit_record,
        view_monthly_record=view_monthly_record,
        edit_monthly_record=edit_monthly_record,
        edit_staff_type=edit_worker_ctx["staff_type"],
        edit_subcontractor_id=edit_worker_ctx["subcontractor_id"],
        history=wf_ctx.get("history") or monthly_wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role") or monthly_wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False) or monthly_wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id") or monthly_wf_ctx.get("approval_id"),
    )


@app.route("/petty_cash", methods=["GET", "POST"])
@login_required
def petty_cash():
    db = get_db()
    ensure_petty_cash_tables(db)
    module_id = "petty_cash"
    record_table = "petty_cash_requests"
    username = session.get("username", "")
    user_id = session.get("user_id")

    if request.method == "POST":
        form_action = request.form.get("form_action", "save_draft").strip()
        request_id = request.form.get("request_id", "").strip()

        if form_action == "delete_request":
            if not request_id:
                flash("Invalid delete request.")
                return redirect(url_for("petty_cash"))
            row = _load_petty_cash_request(db, request_id)
            if not row or not _petty_cash_can_delete_request(row):
                flash("This request cannot be deleted.")
                return redirect(url_for("petty_cash"))
            db.execute("DELETE FROM petty_cash_attachments WHERE request_id=?", (request_id,))
            db.execute("DELETE FROM petty_cash_expenses WHERE request_id=?", (request_id,))
            db.execute("DELETE FROM petty_cash_transfers WHERE request_id=?", (request_id,))
            db.execute("DELETE FROM approval_requests WHERE module_id=? AND record_id=? AND record_table=?", (
                module_id, request_id, record_table,
            ))
            db.execute("DELETE FROM petty_cash_requests WHERE id=?", (request_id,))
            db.commit()
            flash("Petty cash request deleted.")
            return redirect(url_for("petty_cash"))

        if form_action in ("save_draft", "submit_request", "save_request"):
            payload = _parse_petty_cash_request_form()
            try:
                amount_val = float(payload["required_amount"] or 0)
            except ValueError:
                flash("Enter a valid required amount.")
                return redirect(request.referrer or url_for("petty_cash", new=1))
            if not payload["request_date"]:
                flash("Request date is required.")
                return redirect(request.referrer or url_for("petty_cash", new=1))
            if not payload["purpose"]:
                flash("Purpose is required.")
                return redirect(request.referrer or url_for("petty_cash", new=1))
            if amount_val <= 0:
                flash("Required amount must be greater than zero.")
                return redirect(request.referrer or url_for("petty_cash", new=1))

            now = _petty_cash_timestamp()
            submit_now = form_action == "submit_request"
            if request_id:
                existing = _load_petty_cash_request(db, request_id)
                if not existing or not _petty_cash_can_edit_request(existing):
                    flash("This request cannot be edited.")
                    return redirect(url_for("petty_cash", view=request_id))
                status = "Submitted" if submit_now else (existing.get("status") or "Draft")
                approval_status = (
                    RECORD_PENDING_CHECKER if submit_now
                    else (existing.get("approval_status") or "Draft")
                )
                db.execute(
                    "UPDATE petty_cash_requests SET request_date=?, project_id=?, staff_id=?, "
                    "staff_name=?, employee_code=?, department=?, purpose=?, description=?, "
                    "required_amount=?, priority=?, remarks=?, status=?, approval_status=?, "
                    "modified_by=?, modified_at=? WHERE id=?",
                    (
                        payload["request_date"], payload["project_id"], payload["staff_id"],
                        payload["staff_name"], payload["employee_code"], payload["department"],
                        payload["purpose"], payload["description"], amount_val,
                        payload["priority"], payload["remarks"], status, approval_status,
                        username, now, request_id,
                    ),
                )
                if submit_now:
                    existing_req = db.execute(
                        "SELECT id FROM approval_requests WHERE module_id=? AND record_id=? AND record_table=?",
                        (module_id, request_id, record_table),
                    ).fetchone()
                    if existing_req:
                        resubmit_record(db, module_id, int(request_id), record_table, user_id)
                    else:
                        create_approval_request(
                            db, module_id, int(request_id), record_table, username, user_id,
                        )
                    flash("Request submitted for approval.")
                else:
                    flash("Draft saved.")
                db.commit()
                return redirect(url_for("petty_cash", view=request_id))

            request_number = generate_petty_cash_request_number(db)
            status = "Submitted" if submit_now else "Draft"
            approval_status = RECORD_PENDING_CHECKER if submit_now else "Draft"
            db.execute(
                "INSERT INTO petty_cash_requests("
                "request_number, request_date, project_id, staff_id, staff_name, employee_code, "
                "department, purpose, description, required_amount, priority, remarks, status, "
                "approval_status, created_by, created_at, modified_by, modified_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    request_number, payload["request_date"], payload["project_id"],
                    payload["staff_id"], payload["staff_name"], payload["employee_code"],
                    payload["department"], payload["purpose"], payload["description"],
                    amount_val, payload["priority"], payload["remarks"], status,
                    approval_status, username, now, username, now,
                ),
            )
            new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            if submit_now:
                create_approval_request(
                    db, module_id, new_id, record_table, username, user_id,
                )
                flash(f"Request {request_number} submitted for approval.")
            else:
                flash(f"Draft {request_number} saved.")
            db.commit()
            return redirect(url_for("petty_cash", view=new_id))

        if form_action == "save_transfer" and request_id:
            row = _load_petty_cash_request(db, request_id)
            if not row or row.get("status") not in ("Approved", "Funds Transferred"):
                flash("Fund transfer is only allowed for approved requests.")
                return redirect(url_for("petty_cash", view=request_id))
            try:
                transfer_amount = float(request.form.get("transfer_amount", "0") or 0)
            except ValueError:
                flash("Enter a valid transfer amount.")
                return redirect(url_for("petty_cash", transfer=request_id))
            if transfer_amount <= 0:
                flash("Transfer amount must be greater than zero.")
                return redirect(url_for("petty_cash", transfer=request_id))
            now = _petty_cash_timestamp()
            db.execute(
                "INSERT INTO petty_cash_transfers("
                "request_id, transfer_date, amount, bank_name, account_number, utr_number, "
                "reference_number, payment_mode, remarks, created_by, created_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    request_id,
                    request.form.get("transfer_date", "").strip(),
                    transfer_amount,
                    request.form.get("bank_name", "").strip(),
                    request.form.get("account_number", "").strip(),
                    request.form.get("utr_number", "").strip(),
                    request.form.get("reference_number", "").strip(),
                    request.form.get("payment_mode", "Bank Transfer").strip(),
                    request.form.get("transfer_remarks", "").strip(),
                    username, now,
                ),
            )
            db.execute(
                "UPDATE petty_cash_requests SET transferred_amount=?, status=?, "
                "modified_by=?, modified_at=? WHERE id=?",
                (transfer_amount, "Funds Transferred", username, now, request_id),
            )
            db.commit()
            flash("Fund transfer recorded.")
            return redirect(url_for("petty_cash", view=request_id))

        if form_action == "confirm_received" and request_id:
            row = _load_petty_cash_request(db, request_id)
            if not row or row.get("status") != "Funds Transferred":
                flash("Amount can only be confirmed after funds are transferred.")
                return redirect(url_for("petty_cash", view=request_id))
            db.execute(
                "UPDATE petty_cash_requests SET status=?, modified_by=?, modified_at=? WHERE id=?",
                ("Amount Received", username, _petty_cash_timestamp(), request_id),
            )
            db.commit()
            flash("Amount received confirmed. You may now record expenses.")
            return redirect(url_for("petty_cash", expenses=request_id))

        if form_action == "add_expense" and request_id:
            row = _load_petty_cash_request(db, request_id)
            if not row or row.get("status") not in (
                "Amount Received", "Settlement Pending", "Funds Transferred",
            ):
                flash("Expenses can be recorded after amount is received.")
                return redirect(url_for("petty_cash", view=request_id))
            try:
                expense_amount = float(request.form.get("expense_amount", "0") or 0)
            except ValueError:
                flash("Enter a valid expense amount.")
                return redirect(url_for("petty_cash", expenses=request_id))
            if expense_amount <= 0:
                flash("Expense amount must be greater than zero.")
                return redirect(url_for("petty_cash", expenses=request_id))
            transferred = float(row.get("transferred_amount") or 0)
            current_total = float(row.get("expenses_total") or 0)
            if current_total + expense_amount > transferred + 0.001:
                flash("Expense exceeds available balance.")
                return redirect(url_for("petty_cash", expenses=request_id))
            staff_id = request.form.get("expense_staff_id") or row.get("staff_id")
            staff_name = request.form.get("expense_staff_name", "").strip() or row.get("staff_name")
            employee_code = request.form.get("expense_employee_code", "").strip() or row.get("employee_code")
            now = _petty_cash_timestamp()
            db.execute(
                "INSERT INTO petty_cash_expenses("
                "request_id, expense_category, description, vendor, bill_number, amount, "
                "staff_id, staff_name, employee_code, created_by, created_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    request_id,
                    request.form.get("expense_category", "Other").strip(),
                    request.form.get("expense_description", "").strip(),
                    request.form.get("vendor", "").strip(),
                    request.form.get("bill_number", "").strip(),
                    expense_amount,
                    staff_id, staff_name, employee_code, username, now,
                ),
            )
            expense_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            upload = request.files.get("expense_attachment")
            if upload and upload.filename:
                ext, size, err = _validate_petty_cash_upload(upload)
                if err:
                    flash(err)
                    return redirect(url_for("petty_cash", expenses=request_id))
                stored = save_file(upload, PETTY_CASH_DOCS_DIR)
                if stored:
                    db.execute(
                        "INSERT INTO petty_cash_attachments("
                        "request_id, expense_id, original_filename, stored_filename, "
                        "file_ext, file_size, uploaded_by, uploaded_at"
                        ") VALUES(?,?,?,?,?,?,?,?)",
                        (
                            request_id, expense_id, upload.filename, stored,
                            ext, size, username, now,
                        ),
                    )
            _refresh_petty_cash_expense_total(db, request_id)
            if row.get("status") == "Funds Transferred":
                db.execute(
                    "UPDATE petty_cash_requests SET status=? WHERE id=?",
                    ("Amount Received", request_id),
                )
            db.commit()
            flash("Expense added.")
            return redirect(url_for("petty_cash", expenses=request_id))

        if form_action == "delete_expense" and request_id:
            expense_id = request.form.get("expense_id", "").strip()
            if expense_id:
                db.execute(
                    "DELETE FROM petty_cash_attachments WHERE expense_id=?",
                    (expense_id,),
                )
                db.execute(
                    "DELETE FROM petty_cash_expenses WHERE id=? AND request_id=?",
                    (expense_id, request_id),
                )
                _refresh_petty_cash_expense_total(db, request_id)
                db.commit()
                flash("Expense removed.")
            return redirect(url_for("petty_cash", expenses=request_id))

        if form_action == "upload_request_attachment" and request_id:
            upload = request.files.get("request_attachment")
            ext, size, err = _validate_petty_cash_upload(upload)
            if err:
                flash(err)
                return redirect(url_for("petty_cash", view=request_id))
            stored = save_file(upload, PETTY_CASH_DOCS_DIR)
            if not stored:
                flash("Unable to save uploaded file.")
                return redirect(url_for("petty_cash", view=request_id))
            db.execute(
                "INSERT INTO petty_cash_attachments("
                "request_id, expense_id, original_filename, stored_filename, "
                "file_ext, file_size, uploaded_by, uploaded_at"
                ") VALUES(?,?,?,?,?,?,?,?)",
                (
                    request_id, None, upload.filename, stored,
                    ext, size, username, _petty_cash_timestamp(),
                ),
            )
            db.commit()
            flash("Attachment uploaded.")
            return redirect(url_for("petty_cash", view=request_id))

        if form_action == "submit_settlement" and request_id:
            row = _load_petty_cash_request(db, request_id)
            if not row or row.get("status") not in ("Amount Received", "Settlement Pending"):
                flash("Settlement can be submitted after expenses are recorded.")
                return redirect(url_for("petty_cash", view=request_id))
            expenses_total = _refresh_petty_cash_expense_total(db, request_id)
            if expenses_total <= 0:
                flash("Add at least one expense before settlement.")
                return redirect(url_for("petty_cash", settle=request_id))
            now = _petty_cash_timestamp()
            db.execute(
                "UPDATE petty_cash_requests SET status=?, settlement_remarks=?, "
                "settlement_submitted_at=?, modified_by=?, modified_at=? WHERE id=?",
                (
                    "Settlement Pending",
                    request.form.get("settlement_remarks", "").strip(),
                    now, username, now, request_id,
                ),
            )
            db.commit()
            flash("Settlement submitted for accounts review.")
            return redirect(url_for("petty_cash", view=request_id))

        if form_action == "approve_settlement" and request_id:
            row = _load_petty_cash_request(db, request_id)
            if not row or row.get("status") != "Settlement Pending":
                flash("No settlement pending for this request.")
                return redirect(url_for("petty_cash", view=request_id))
            comment = request.form.get("settlement_comment", "").strip()
            if not comment:
                flash("Approval comment is mandatory.")
                return redirect(url_for("petty_cash", view=request_id))
            now = _petty_cash_timestamp()
            db.execute(
                "UPDATE petty_cash_requests SET status=?, settlement_reviewed_at=?, "
                "settlement_reviewed_by=?, modified_by=?, modified_at=? WHERE id=?",
                ("Settled", now, username, username, now, request_id),
            )
            if request.form.get("create_expense_draft") == "1":
                ensure_accounts_schema(db)
                exp_id = create_expense_draft_from_petty_cash(db, request_id, username)
                if exp_id:
                    create_approval_request(
                        db, "account_expense", exp_id, "account_expenses",
                        username, session.get("user_id"),
                    )
                    flash(f"Settlement approved. Expense draft #{exp_id} created.")
                else:
                    flash("Settlement approved.")
            else:
                flash("Settlement approved.")
            db.commit()
            return redirect(url_for("petty_cash", view=request_id))

        if form_action == "reject_settlement" and request_id:
            row = _load_petty_cash_request(db, request_id)
            if not row or row.get("status") != "Settlement Pending":
                flash("No settlement pending for this request.")
                return redirect(url_for("petty_cash", view=request_id))
            comment = request.form.get("settlement_comment", "").strip()
            if not comment:
                flash("Rejection comment is mandatory.")
                return redirect(url_for("petty_cash", view=request_id))
            now = _petty_cash_timestamp()
            db.execute(
                "UPDATE petty_cash_requests SET status=?, settlement_remarks=?, "
                "settlement_reviewed_at=?, settlement_reviewed_by=?, modified_by=?, "
                "modified_at=? WHERE id=?",
                (
                    "Amount Received", comment, now, username, username, now, request_id,
                ),
            )
            db.commit()
            flash("Settlement rejected. Staff may revise expenses.")
            return redirect(url_for("petty_cash", expenses=request_id))

        if form_action == "close_request" and request_id:
            row = _load_petty_cash_request(db, request_id)
            if not row or row.get("status") != "Settled":
                flash("Only settled requests can be closed.")
                return redirect(url_for("petty_cash", view=request_id))
            db.execute(
                "UPDATE petty_cash_requests SET status=?, modified_by=?, modified_at=? WHERE id=?",
                ("Closed", username, _petty_cash_timestamp(), request_id),
            )
            db.commit()
            flash("Request closed.")
            return redirect(url_for("petty_cash", view=request_id))

    filter_status = request.args.get("status", "").strip()
    filter_project = request.args.get("project_id", "").strip()
    filter_q = request.args.get("q", "").strip()
    filter_date_from = request.args.get("date_from", "").strip()
    filter_date_to = request.args.get("date_to", "").strip()
    clauses = []
    args = []
    if filter_status:
        clauses.append("r.status=?")
        args.append(filter_status)
    if filter_project:
        clauses.append("r.project_id=?")
        args.append(filter_project)
    if filter_date_from:
        clauses.append("r.request_date >= ?")
        args.append(filter_date_from)
    if filter_date_to:
        clauses.append("r.request_date <= ?")
        args.append(filter_date_to)
    if filter_q:
        clauses.append(
            "(r.request_number LIKE ? OR r.staff_name LIKE ? OR r.purpose LIKE ?)"
        )
        like = f"%{filter_q}%"
        args.extend([like, like, like])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = query_db(
        _petty_cash_request_sql() + where + " ORDER BY r.id DESC",
        tuple(args),
    )
    status_counts = {
        row["status"]: row["c"]
        for row in db.execute(
            "SELECT status, COUNT(*) AS c FROM petty_cash_requests GROUP BY status"
        ).fetchall()
    }

    projects = query_db(
        "SELECT id, project_name, project_code FROM projects ORDER BY project_name"
    )
    staff_list = query_db(
        "SELECT id, staff_name, employee_code, department FROM staff "
        "WHERE COALESCE(status, 'Active')='Active' ORDER BY staff_name"
    )
    departments = query_db(
        "SELECT department_name FROM departments WHERE status='Active' ORDER BY department_name"
    )

    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    show_new = request.args.get("new")
    transfer_id = request.args.get("transfer")
    expenses_id = request.args.get("expenses")
    settle_id = request.args.get("settle")

    view_record = edit_record = transfer_record = expenses_record = settle_record = None
    expenses = transfers = attachments = []
    wf_ctx = {}
    available_balance = 0.0

    if view_id:
        view_record = _load_petty_cash_request(db, view_id)
        if view_record:
            expenses = query_db(
                "SELECT * FROM petty_cash_expenses WHERE request_id=? ORDER BY id",
                (view_id,),
            )
            transfers = query_db(
                "SELECT * FROM petty_cash_transfers WHERE request_id=? ORDER BY id DESC",
                (view_id,),
            )
            attachments = query_db(
                "SELECT * FROM petty_cash_attachments WHERE request_id=? ORDER BY id DESC",
                (view_id,),
            )
            available_balance = _petty_cash_available_balance(view_record)
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], record_table, view_record["approval_status"],
            )
    elif edit_id:
        edit_record = _load_petty_cash_request(db, edit_id)
        if edit_record and not _petty_cash_can_edit_request(edit_record):
            flash("This request is locked and cannot be edited.")
            return redirect(url_for("petty_cash", view=edit_id))
    elif transfer_id:
        transfer_record = _load_petty_cash_request(db, transfer_id)
        if not transfer_record:
            flash("Request not found.")
            return redirect(url_for("petty_cash"))
    elif expenses_id:
        expenses_record = _load_petty_cash_request(db, expenses_id)
        if expenses_record:
            expenses = query_db(
                "SELECT * FROM petty_cash_expenses WHERE request_id=? ORDER BY id",
                (expenses_id,),
            )
            attachments = query_db(
                "SELECT * FROM petty_cash_attachments WHERE request_id=? ORDER BY id DESC",
                (expenses_id,),
            )
            available_balance = _petty_cash_available_balance(expenses_record)
    elif settle_id:
        settle_record = _load_petty_cash_request(db, settle_id)
        if settle_record:
            expenses = query_db(
                "SELECT * FROM petty_cash_expenses WHERE request_id=? ORDER BY id",
                (settle_id,),
            )
            available_balance = _petty_cash_available_balance(settle_record)

    workflow = get_workflow_for_module(db, module_id)
    next_request_number = generate_petty_cash_request_number(db)
    petty_summary = _petty_cash_dashboard_summary(db)
    workflow_active_index = (
        _petty_cash_workflow_index(view_record.get("status"))
        if view_record
        else 0
    )

    return render_template(
        "petty_cash.html",
        rows=rows,
        projects=projects,
        staff_list=staff_list,
        departments=departments,
        workflow=workflow,
        view_record=view_record,
        edit_record=edit_record,
        transfer_record=transfer_record,
        expenses_record=expenses_record,
        settle_record=settle_record,
        expenses=expenses,
        transfers=transfers,
        attachments=attachments,
        available_balance=available_balance,
        status_counts=status_counts,
        petty_summary=petty_summary,
        workflow_steps=PETTY_CASH_WORKFLOW_STEPS,
        workflow_active_index=workflow_active_index,
        filter_status=filter_status,
        filter_project=filter_project,
        filter_q=filter_q,
        filter_date_from=filter_date_from,
        filter_date_to=filter_date_to,
        show_new=show_new,
        next_request_number=next_request_number,
        expense_categories=PETTY_CASH_EXPENSE_CATEGORIES,
        petty_cash_statuses=PETTY_CASH_STATUSES,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
        is_admin=is_admin_user(),
        module_id=module_id,
        record_table=record_table,
    )


@app.route("/petty_cash/attachment/<int:attachment_id>")
@login_required
def petty_cash_attachment(attachment_id):
    db = get_db()
    ensure_petty_cash_tables(db)
    row = db.execute(
        "SELECT * FROM petty_cash_attachments WHERE id=?", (attachment_id,)
    ).fetchone()
    if not row:
        abort(404)
    path = os.path.join(PETTY_CASH_DOCS_DIR, row["stored_filename"])
    if not os.path.isfile(path):
        abort(404)
    return send_from_directory(
        PETTY_CASH_DOCS_DIR,
        row["stored_filename"],
        as_attachment=True,
        download_name=row["original_filename"] or row["stored_filename"],
    )


@app.route("/securities-guarantees", methods=["GET", "POST"])
@login_required
def securities_guarantees():
    db = get_db()
    ensure_security_guarantees_tables(db)
    ensure_project_guarantees_table(db)
    username = session.get("username", "")

    if request.method == "POST":
        form_action = request.form.get("form_action", "save_record").strip()
        record_id = request.form.get("record_id", "").strip()

        if form_action == "delete_record":
            if not record_id:
                flash("Invalid delete request.")
                return redirect(url_for("securities_guarantees"))
            row = _load_security_record(db, record_id)
            if not row or dict(row).get("status") not in ("Draft",):
                flash("Only draft records can be deleted.")
                return redirect(url_for("securities_guarantees"))
            attachments = db.execute(
                "SELECT stored_filename FROM security_guarantee_attachments WHERE security_id=?",
                (record_id,),
            ).fetchall()
            for att in attachments:
                path = os.path.join(SECURITIES_DOCS_DIR, att["stored_filename"])
                if os.path.isfile(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            db.execute(
                "DELETE FROM security_guarantee_attachments WHERE security_id=?",
                (record_id,),
            )
            db.execute("DELETE FROM security_guarantees WHERE id=?", (record_id,))
            db.commit()
            flash("Security record deleted.")
            return redirect(url_for("securities_guarantees"))

        if form_action in ("save_record", "save_and_new", "activate_record", "request_release", "mark_released"):
            payload = _parse_security_form()
            save_and_new = form_action == "save_and_new"
            if form_action == "save_and_new":
                form_action = "save_record"
            if payload["security_type"] not in SECURITY_TYPES:
                flash("Select a valid security type.")
                return redirect(request.referrer or url_for("securities_guarantees", new=1))
            if not payload["project_id"]:
                flash("Project is required.")
                return redirect(request.referrer or url_for("securities_guarantees", new=1))
            if payload["deposit_amount"] <= 0 and payload["security_type"] != "Pending Bill Retention":
                flash("Deposit / guarantee amount must be greater than zero.")
                return redirect(request.referrer or url_for("securities_guarantees", new=1))

            snapshot = _load_project_security_snapshot(db, payload["project_id"])
            if snapshot:
                payload["project_name"] = snapshot["project_name"] or payload["project_name"]
                payload["project_code"] = snapshot["project_code"] or payload["project_code"]
                payload["client_name"] = snapshot["client_name"] or payload["client_name"]
                if not payload["agreement_number"]:
                    payload["agreement_number"] = snapshot["agreement_number"]
                if not payload["agreement_date"]:
                    payload["agreement_date"] = snapshot["agreement_date"]
                if not payload["work_order_number"]:
                    payload["work_order_number"] = snapshot["work_order_number"]
                if not payload["contract_value"]:
                    payload["contract_value"] = snapshot["contract_value"]

            now = _security_timestamp()
            if form_action == "activate_record":
                payload["status"] = "Active"
            elif form_action == "request_release":
                payload["status"] = "Release Requested"
            elif form_action == "mark_released":
                payload["status"] = "Released"
                payload["released_by"] = username
                if not payload["release_date"]:
                    payload["release_date"] = datetime.now().strftime("%Y-%m-%d")

            columns = (
                "security_type", "project_id", "project_name", "project_code", "client_name",
                "agreement_number", "agreement_date", "work_order_number", "contract_value",
                "deposit_amount", "bank_name", "branch_name", "account_number",
                "instrument_number", "challan_number", "bg_number", "beneficiary_name",
                "issuing_bank", "deposit_date", "issue_date", "expiry_date", "maturity_date",
                "release_date", "extension_date", "interest_rate", "interest_amount",
                "total_recoverable", "tender_number", "tender_date", "tender_authority",
                "emd_mode", "bill_number", "bill_date", "retention_percent", "bill_amount",
                "retention_amount", "claim_period",
                "status", "release_remarks", "extension_remarks", "remarks",
                "released_by", "approved_by",
            )
            values = tuple(payload[c] for c in columns)

            if record_id:
                existing = _load_security_record(db, record_id)
                if not existing or not _security_can_edit(existing):
                    flash("This record cannot be edited.")
                    return redirect(url_for("securities_guarantees", view=record_id))
                set_clause = ", ".join(f"{c}=?" for c in columns)
                db.execute(
                    f"UPDATE security_guarantees SET {set_clause}, modified_by=?, modified_at=? WHERE id=?",
                    values + (username, now, record_id),
                )
                upload_err = _save_security_attachment(
                    db, record_id, request.files.get("security_attachment"), username,
                )
                db.commit()
                if upload_err:
                    flash(f"Record updated. Attachment note: {upload_err}")
                else:
                    flash("Security record updated.")
                if save_and_new:
                    return redirect(url_for(
                        "securities_guarantees",
                        new=1,
                        project_id=payload["project_id"],
                    ) + "#new-record")
                return redirect(url_for("securities_guarantees", view=record_id))

            register_number = generate_security_register_number(db)
            placeholders = ", ".join("?" for _ in columns)
            col_names = ", ".join(columns)
            db.execute(
                f"INSERT INTO security_guarantees(register_number, {col_names}, created_by, created_at, modified_by, modified_at) "
                f"VALUES(?, {placeholders}, ?, ?, ?, ?)",
                (register_number,) + values + (username, now, username, now),
            )
            new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            upload_err = _save_security_attachment(
                db, new_id, request.files.get("security_attachment"), username,
            )
            db.commit()
            if upload_err:
                flash(f"Record {register_number} saved. Attachment note: {upload_err}")
            else:
                flash(f"Record {register_number} saved.")
            if save_and_new:
                return redirect(url_for(
                    "securities_guarantees",
                    new=1,
                    project_id=payload["project_id"],
                ) + "#new-record")
            return redirect(url_for("securities_guarantees", view=new_id))

        if form_action == "upload_attachment" and record_id:
            upload = request.files.get("security_attachment")
            ext, size, err = _validate_securities_upload(upload)
            if err:
                flash(err)
                return redirect(url_for("securities_guarantees", view=record_id))
            stored = save_file(upload, SECURITIES_DOCS_DIR)
            if not stored:
                flash("Unable to save uploaded file.")
                return redirect(url_for("securities_guarantees", view=record_id))
            db.execute(
                "INSERT INTO security_guarantee_attachments("
                "security_id, original_filename, stored_filename, file_ext, file_size, uploaded_by, uploaded_at"
                ") VALUES(?,?,?,?,?,?,?)",
                (
                    record_id, upload.filename, stored, ext, size,
                    username, _security_timestamp(),
                ),
            )
            db.commit()
            flash("Document uploaded.")
            return redirect(url_for("securities_guarantees", view=record_id))

        if form_action == "delete_attachment":
            attachment_id = request.form.get("attachment_id", "").strip()
            if attachment_id:
                att = db.execute(
                    "SELECT * FROM security_guarantee_attachments WHERE id=?",
                    (attachment_id,),
                ).fetchone()
                if att:
                    path = os.path.join(SECURITIES_DOCS_DIR, att["stored_filename"])
                    if os.path.isfile(path):
                        try:
                            os.remove(path)
                        except OSError:
                            pass
                    db.execute(
                        "DELETE FROM security_guarantee_attachments WHERE id=?",
                        (attachment_id,),
                    )
                    db.commit()
                    flash("Attachment removed.")
            return redirect(url_for("securities_guarantees", view=record_id or None))

    filter_type = request.args.get("security_type", "").strip()
    filter_status = request.args.get("status", "").strip()
    filter_project = request.args.get("project_id", "").strip()
    filter_q = request.args.get("q", "").strip()
    preselect_type = request.args.get("security_type", "").strip()
    if preselect_type and preselect_type not in SECURITY_TYPES:
        preselect_type = ""
    clauses = []
    args = []
    if filter_type:
        clauses.append("s.security_type=?")
        args.append(filter_type)
    if filter_status:
        clauses.append("s.status=?")
        args.append(filter_status)
    if filter_project:
        clauses.append("s.project_id=?")
        args.append(filter_project)
    if filter_q:
        clauses.append(
            "(s.register_number LIKE ? OR s.project_name LIKE ? OR s.client_name LIKE ? "
            "OR s.bg_number LIKE ? OR s.instrument_number LIKE ?)"
        )
        like = f"%{filter_q}%"
        args.extend([like, like, like, like, like])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = query_db(
        _security_record_sql() + where + " ORDER BY s.id DESC",
        tuple(args),
    )

    projects = query_db(
        "SELECT id, project_name, project_code FROM projects ORDER BY project_name"
    )
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    show_new = request.args.get("new")
    view_record = edit_record = None
    attachments = []
    if view_id:
        row = _load_security_record(db, view_id)
        if row:
            view_record = dict(row)
            attachments = query_db(
                "SELECT * FROM security_guarantee_attachments WHERE security_id=? ORDER BY id DESC",
                (view_id,),
            )
        else:
            flash("Security record not found.")
    elif edit_id:
        row = _load_security_record(db, edit_id)
        if row:
            edit_record = dict(row)
            if not _security_can_edit(edit_record):
                flash("This record is locked and cannot be edited.")
                return redirect(url_for("securities_guarantees", view=edit_id))
        else:
            flash("Security record not found.")

    dashboard = _security_dashboard_stats(db)
    _stub_security_expiry_notifications(db)
    next_register_number = generate_security_register_number(db)

    return render_template(
        "securities_guarantees.html",
        rows=rows,
        projects=projects,
        view_record=view_record,
        edit_record=edit_record,
        attachments=attachments,
        dashboard=dashboard,
        filter_type=filter_type,
        filter_status=filter_status,
        filter_project=filter_project,
        filter_q=filter_q,
        preselect_type=preselect_type,
        show_new=show_new,
        next_register_number=next_register_number,
        security_types=SECURITY_TYPES,
        security_statuses=SECURITY_STATUSES,
        expiry_alert_days=SECURITY_EXPIRY_ALERT_DAYS,
    )


@app.route("/securities-guarantees/print/<int:record_id>")
@login_required
def securities_guarantee_print(record_id):
    db = get_db()
    ensure_security_guarantees_tables(db)
    ensure_project_guarantees_table(db)
    record = _load_security_record(db, record_id)
    if not record:
        flash("Security record not found.")
        return redirect(url_for("securities_guarantees"))
    attachments = query_db(
        "SELECT * FROM security_guarantee_attachments WHERE security_id=? ORDER BY id",
        (record_id,),
    )
    return render_template(
        "securities_guarantee_print.html",
        record=dict(record),
        attachments=attachments,
        autoprint=request.args.get("print") == "1",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/securities-guarantees/export")
@login_required
def securities_guarantees_export():
    db = get_db()
    ensure_security_guarantees_tables(db)
    ensure_project_guarantees_table(db)
    rows = query_db(_security_record_sql() + "ORDER BY s.id DESC")
    if not rows:
        flash("No security records to export.")
        return redirect(url_for("securities_guarantees"))
    records = []
    for row in rows:
        row = dict(row)
        records.append({
            "Register No": row.get("register_number"),
            "Type": row.get("security_type"),
            "Project Code": row.get("project_code"),
            "Project Name": row.get("project_name"),
            "Client": row.get("client_name"),
            "Agreement No": row.get("agreement_number"),
            "Amount": row.get("deposit_amount"),
            "BG / Instrument No": row.get("bg_number") or row.get("instrument_number"),
            "Issue Date": row.get("issue_date") or row.get("deposit_date"),
            "Expiry / Maturity": row.get("expiry_date") or row.get("maturity_date"),
            "Interest": row.get("interest_amount"),
            "Total Recoverable": row.get("total_recoverable"),
            "Status": row.get("status"),
            "Bank": row.get("bank_name") or row.get("issuing_bank"),
            "Created By": row.get("created_by"),
            "Created At": row.get("created_at"),
        })
    df = pd.DataFrame(records)
    filename = f"security_register_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    file_path = os.path.join(REPORTS_DIR, filename)
    df.to_excel(file_path, index=False)
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


@app.route("/securities-guarantees/attachment/<int:attachment_id>")
@login_required
def securities_guarantee_attachment(attachment_id):
    db = get_db()
    ensure_security_guarantees_tables(db)
    ensure_project_guarantees_table(db)
    row = db.execute(
        "SELECT * FROM security_guarantee_attachments WHERE id=?",
        (attachment_id,),
    ).fetchone()
    if not row:
        abort(404)
    path = os.path.join(SECURITIES_DOCS_DIR, row["stored_filename"])
    if not os.path.isfile(path):
        abort(404)
    return send_from_directory(
        SECURITIES_DOCS_DIR,
        row["stored_filename"],
        as_attachment=True,
        download_name=row["original_filename"] or row["stored_filename"],
    )


@app.route("/api/projects/<int:project_id>/security-details")
@login_required
def api_project_security_details(project_id):
    db = get_db()
    snapshot = _load_project_security_snapshot(db, project_id)
    if not snapshot:
        return jsonify({"error": "Project not found."}), 404
    return jsonify(snapshot)


@app.route("/salary", methods=["GET", "POST"])
@login_required
def salary():
    module_id, table, endpoint = "payroll", "salary", "salary"
    record_sql = (
        "SELECT s.*, w.worker_name FROM salary s "
        "LEFT JOIN workers w ON s.worker_id = w.id WHERE s.id=?"
    )
    workers = query_db("SELECT id, worker_name FROM workers ORDER BY worker_name")
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = query_db(record_sql, (view_id,), one=True)
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = query_db(record_sql, (edit_id,), one=True)
        if edit_record:
            edit_role = get_edit_role_for_user(
                get_db(), session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}
    if request.method == "POST":
        worker_id = request.form.get("worker_id", "")
        month = request.form.get("month", "").strip()
        total_days = request.form.get("total_days", "0").strip()
        normal_wage = request.form.get("normal_wage", "0").strip()
        ot_amount = request.form.get("ot_amount", "0").strip()
        advance_deduction = request.form.get("advance_deduction", "0").strip()
        payment_status = request.form.get("payment_status", "Pending").strip()
        record_id = request.form.get("record_id", "").strip()
        try:
            total_days_val = int(total_days or 0)
            normal_wage_val = float(normal_wage or 0)
            ot_amount_val = float(ot_amount or 0)
            advance_deduction_val = float(advance_deduction or 0)
            final_salary = normal_wage_val + ot_amount_val - advance_deduction_val
        except ValueError:
            flash("Enter valid numeric salary values.")
            return redirect(url_for(endpoint))
        db = get_db()
        if record_id:
            ctx = _module_edit_context(module_id, table, endpoint)
            if ctx[0] == "redirect":
                return redirect(ctx[1])
            rid, edit_role = ctx
            db.execute(
                "UPDATE salary SET worker_id=?, month=?, total_days=?, normal_wage=?, "
                "ot_amount=?, advance_deduction=?, final_salary=?, payment_status=? WHERE id=?",
                (
                    worker_id or None, month, total_days_val, normal_wage_val,
                    ot_amount_val, advance_deduction_val, final_salary, payment_status, rid,
                ),
            )
            _complete_module_save(db, module_id, table, rid, edit_role)
            return redirect(url_for(endpoint))
        db.execute(
            "INSERT INTO salary(worker_id, month, total_days, normal_wage, ot_amount, advance_deduction, final_salary, payment_status, approval_status) VALUES(?,?,?,?,?,?,?,?,?)",
            (worker_id or None, month, total_days_val, normal_wage_val, ot_amount_val, advance_deduction_val, final_salary, payment_status, "Pending Checker")
        )
        record_id_new = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        create_approval_request(
            db, module_id, record_id_new, table,
            session.get("username", ""), session.get("user_id")
        )
        db.commit()
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT s.*, w.worker_name FROM salary s LEFT JOIN workers w ON s.worker_id = w.id ORDER BY s.id DESC"
    )
    return render_template(
        "salary.html", rows=rows, workers=workers,
        view_record=view_record, edit_record=edit_record,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/reports", methods=["GET", "POST"])
@login_required
def reports():
    workers = query_db("SELECT id, worker_name FROM workers ORDER BY worker_name")
    report_rows = None
    file_url = None
    if request.method == "POST":
        report_type = request.form.get("report_type", "attendance")
        worker_ref = request.form.get("worker_id", "")
        worker_id, worker_source = parse_attendance_worker_ref(worker_ref)
        from_date = request.form.get("from_date", "").strip()
        to_date = request.form.get("to_date", "").strip()
        try:
            if report_type == "attendance":
                query = (
                    "SELECT a.attendance_date, "
                    "COALESCE(w.worker_name, s.staff_name) AS worker_name, "
                    "p.project_name, a.in_time, a.out_time, a.break_hours, a.total_hours, a.ot_hours, a.status "
                    f"FROM attendance a {ATTENDANCE_WORKER_JOIN_SQL} "
                    "LEFT JOIN projects p ON a.project_id = p.id "
                    "WHERE a.worker_id = ? AND COALESCE(a.worker_source, 'worker') = ? "
                    "AND a.attendance_date BETWEEN ? AND ?"
                )
                df = pd.read_sql_query(
                    query, get_db(), params=(worker_id, worker_source, from_date, to_date)
                )
            else:
                query = (
                    "SELECT s.month, w.worker_name, s.total_days, s.normal_wage, s.ot_amount, s.advance_deduction, s.final_salary, s.payment_status "
                    "FROM salary s LEFT JOIN workers w ON s.worker_id = w.id "
                    "WHERE s.worker_id = ? AND s.month = ?"
                )
                df = pd.read_sql_query(query, get_db(), params=(worker_id or None, from_date))
            if df.empty:
                flash("No records found for the selected criteria.")
            else:
                filename = f"{report_type}_report_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
                file_path = os.path.join(REPORTS_DIR, filename)
                df.to_excel(file_path, index=False)
                file_url = url_for("download_report", filename=filename)
                report_rows = df.to_dict(orient="records")
        except Exception as exc:
            flash(f"Unable to generate report: {exc}")
    return render_template("reports.html", workers=workers, report_rows=report_rows, file_url=file_url)


@app.route("/reports/download/<filename>")
@login_required
def download_report(filename):
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if is_guest_user():
        flash("Settings are not available for demo guest accounts.")
        return redirect(url_for("dashboard"))
    if is_hr_base_user():
        flash("Settings are not available for HR base accounts.")
        return redirect(url_for("dashboard"))
    db = get_db()
    ensure_app_settings_table(db)
    ensure_department_master(db)
    if request.method == "POST":
        form_type = request.form.get("form_type", "department").strip()
        if form_type == "company":
            timezone = request.form.get("timezone", "Asia/Kolkata").strip()
            valid_tz = {tz for tz, _ in APP_TIMEZONE_OPTIONS}
            if timezone not in valid_tz:
                flash("Select a valid timezone.")
                return redirect(url_for("settings") + "#company-settings")
            set_app_setting(db, "timezone", timezone)
            flash("Company settings updated.")
            return redirect(url_for("settings") + "#company-settings")
        if form_type == "dashboard_display":
            display_settings = {
                key: request.form.get(f"dash_{key}") == "on"
                for key in DEFAULT_DASHBOARD_DISPLAY
            }
            set_dashboard_display_settings(db, display_settings)
            flash("Dashboard display settings saved.")
            redirect_target = request.form.get("redirect_to", "settings").strip()
            if redirect_target == "dashboard":
                return redirect(url_for("dashboard"))
            return redirect(url_for("settings") + "#dashboard-display")
        if form_type == "user_dashboard_preferences":
            role_profile = request.form.get("role_profile", "default").strip()
            cards = [c.strip() for c in request.form.getlist("dashboard_cards") if c.strip()]
            modules = [m.strip() for m in request.form.getlist("favorite_modules") if m.strip()]
            actions = [a.strip() for a in request.form.getlist("quick_actions") if a.strip()]
            reports = [r.strip() for r in request.form.getlist("reports") if r.strip()]
            save_dashboard_preferences(
                db,
                session.get("user_id"),
                role_profile=role_profile or infer_role_profile(session.get("department"), session.get("role")),
                favorite_modules=modules,
                dashboard_cards=cards,
                quick_actions=actions,
                reports=reports,
            )
            flash("Your dashboard preferences were saved.")
            return redirect(url_for("settings") + "#dashboard-preferences")
        department_name = request.form.get("department_name", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("status", "Active").strip()
        if not department_name:
            flash("Department name is required.")
            return redirect(url_for("settings") + "#department-master")
        try:
            db.execute(
                "INSERT INTO departments(department_name, description, status) VALUES(?,?,?)",
                (department_name, description, status),
            )
            db.commit()
            flash("Department created.")
        except sqlite3.IntegrityError:
            flash("Department already exists.")
        return redirect(url_for("settings") + "#department-master")
    departments = query_db("SELECT * FROM departments ORDER BY department_name")
    current_timezone = get_app_setting(db, "timezone", "Asia/Kolkata")
    dashboard_display = get_dashboard_display_settings(db)
    user_dashboard_prefs = load_dashboard_preferences(db, session.get("user_id"))
    return render_template(
        "settings.html",
        departments=departments,
        timezone_options=APP_TIMEZONE_OPTIONS,
        current_timezone=current_timezone,
        dashboard_display=dashboard_display,
        user_dashboard_prefs=user_dashboard_prefs,
        dashboard_display_options=[
            ("hero", "Welcome header & quick actions"),
            ("context_bar", "Featured project & progress bar"),
            ("kpis", "KPI summary cards"),
            ("charts", "Attendance & health charts"),
            ("approval_summary", "Maker / checker / approved counters"),
            ("activities", "Recent activities (Operations)"),
            ("notifications", "Notifications panel (Operations)"),
            ("approval_center", "Approval center links (Operations)"),
            ("workflow_queue", "Workflow queue table (Operations)"),
        ],
        app_now_display=format_app_datetime(db=db),
    )


@app.route("/settings/company-master", methods=["GET", "POST"])
@admin_required
def company_master():
    db = get_db()
    _prepare_company_master_db(db)
    company_id = request.args.get("company_id", type=int) or request.form.get("company_id", type=int)

    if request.method == "POST":
        action = request.form.get("form_action", "save_company").strip()
        redirect_cid = request.form.get("company_id", type=int) or company_id
        try:
            if action == "save_company":
                rid = request.form.get("company_id", type=int)
                new_id = save_company(db, request.form, session.get("username", ""), rid)
                db.commit()
                flash("Company saved.")
                return redirect(url_for("company_master", company_id=new_id))
            if action == "delete_company" and redirect_cid:
                delete_company(db, redirect_cid)
                db.commit()
                flash("Company deleted.")
                return redirect(url_for("company_master"))
            if action == "save_branch" and redirect_cid:
                bid = request.form.get("branch_id", type=int)
                save_branch(
                    db,
                    request.form,
                    session.get("username", ""),
                    bid,
                    customer_id=session.get("customer_id"),
                )
                db.commit()
                flash("Branch saved.")
                return redirect(url_for("company_master", company_id=redirect_cid))
            if action == "delete_branch":
                bid = request.form.get("branch_id", type=int)
                if bid:
                    delete_branch(db, bid)
                    db.commit()
                    flash("Branch deleted.")
                return redirect(url_for("company_master", company_id=redirect_cid))
            if action == "save_director" and redirect_cid:
                did = request.form.get("director_id", type=int)
                save_director(db, request.form, session.get("username", ""), did)
                db.commit()
                flash("Director / partner saved.")
                return redirect(url_for("company_master", company_id=redirect_cid))
            if action == "delete_director":
                did = request.form.get("director_id", type=int)
                if did:
                    delete_director(db, did)
                    db.commit()
                    flash("Director / partner removed.")
                return redirect(url_for("company_master", company_id=redirect_cid))
            if action == "save_gst" and redirect_cid:
                gid = request.form.get("gst_id", type=int)
                save_gst_registration(db, request.form, redirect_cid, gid)
                db.commit()
                flash("GST registration saved.")
                return redirect(url_for("company_master", company_id=redirect_cid))
            if action == "delete_gst":
                gid = request.form.get("gst_id", type=int)
                if gid:
                    delete_gst_registration(db, gid)
                    db.commit()
                    flash("GST registration deleted.")
                return redirect(url_for("company_master", company_id=redirect_cid))
            if action == "save_document" and redirect_cid:
                stored = None
                upload = request.files.get("document_file")
                if upload and upload.filename:
                    ext, err = _validate_office_upload(upload)
                    if err:
                        flash(err)
                        return redirect(url_for("company_master", company_id=redirect_cid))
                    stored = save_file(upload, COMPANY_DOCS_DIR)
                doc_id = request.form.get("document_id", type=int)
                save_company_document(
                    db,
                    request.form,
                    session.get("username", ""),
                    stored,
                    doc_id,
                )
                db.commit()
                flash("Document saved.")
                return redirect(url_for("company_master", company_id=redirect_cid))
            if action == "delete_document":
                doc_id = request.form.get("document_id", type=int)
                if doc_id:
                    delete_company_document(db, doc_id)
                    db.commit()
                    flash("Document removed.")
                return redirect(url_for("company_master", company_id=redirect_cid))
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save record.")
            if redirect_cid:
                return redirect(url_for("company_master", company_id=redirect_cid))
            return redirect(url_for("company_master"))

    try:
        sync_company_expiry_notifications(db, create_notification)
        db.commit()
    except Exception:
        app.logger.exception("Company expiry notification sync failed")

    search = request.args.get("q", "")
    country_filter = request.args.get("country", "")
    selected_company = get_company(db, company_id) if company_id else None
    edit_branch = get_branch(db, request.args.get("edit_branch", type=int)) if company_id else None
    edit_director = get_director(db, request.args.get("edit_director", type=int)) if company_id else None
    edit_document = (
        get_company_document(db, request.args.get("edit_document", type=int)) if company_id else None
    )
    edit_gst = None
    if company_id and request.args.get("edit_gst", type=int):
        gid = request.args.get("edit_gst", type=int)
        rows = list_gst_registrations(db, company_id)
        edit_gst = next((g for g in rows if g.get("id") == gid), None)

    gcc_config = {}
    for c in GCC_CONFIGURABLE_COUNTRIES:
        gcc_config[c] = [
            {
                "key": row["field_key"],
                "label": row["field_label"],
                "type": row.get("field_type") or "text",
                "required": bool(row.get("is_required")),
                "options": row.get("options") or [],
            }
            for row in list_country_field_config(db, c)
        ]

    return render_template(
        "company_master.html",
        companies=list_companies(db, search, country_filter),
        search=search,
        country_filter=country_filter,
        company_countries=COMPANY_COUNTRIES,
        company_statuses=COMPANY_STATUSES,
        director_types=DIRECTOR_TYPES,
        company_doc_types=COMPANY_DOC_TYPES,
        selected_company=selected_company,
        show_company_form=bool(request.args.get("new")) or bool(selected_company),
        branches=list_branches(db, company_id) if company_id else [],
        directors=list_directors(db, company_id) if company_id else [],
        documents=list_company_documents(db, company_id) if company_id else [],
        gst_regs=list_gst_registrations(db, company_id) if company_id else [],
        edit_branch=edit_branch,
        edit_director=edit_director,
        edit_document=edit_document,
        edit_gst=edit_gst,
        expiry_alerts=collect_company_expiry_alerts(db),
        gcc_field_config_json=json.dumps(gcc_config),
    )


@app.route("/settings/company-master/download/<filename>")
@login_required
def company_document_download(filename):
    safe = secure_filename(filename)
    path = os.path.join(COMPANY_DOCS_DIR, safe)
    if not os.path.isfile(path):
        flash("File not found.")
        return redirect(url_for("company_master"))
    return send_from_directory(COMPANY_DOCS_DIR, safe, as_attachment=True)


@app.route("/settings/corporate-template-master", methods=["GET", "POST"])
@admin_required
def corporate_template_master():
    db = get_db()
    _prepare_corporate_template_db(db)
    template_id = request.args.get("template_id", type=int) or request.form.get("template_id", type=int)

    if request.method == "POST":
        action = request.form.get("form_action", "save").strip()
        try:
            if action == "delete":
                tid = request.form.get("template_id", type=int)
                if tid:
                    delete_template(db, tid)
                    db.commit()
                    flash("Template deleted.")
                return redirect(url_for("corporate_template_master"))
            if action == "set_default":
                tid = request.form.get("template_id", type=int)
                if tid:
                    set_default_template(db, tid)
                    db.commit()
                    flash("Default template updated.")
                return redirect(url_for("corporate_template_master"))
            if action == "save":
                stored = _save_corporate_template_assets(request.files)
                tid = request.form.get("template_id", type=int)
                new_id = save_template(
                    db,
                    request.form,
                    session.get("username", ""),
                    stored,
                    tid,
                )
                db.commit()
                flash("Corporate template saved.")
                return redirect(url_for("corporate_template_master", template_id=new_id))
        except ValueError as exc:
            flash(str(exc))
            if template_id:
                return redirect(url_for("corporate_template_master", template_id=template_id))
            return redirect(url_for("corporate_template_master"))

    selected = get_template(db, template_id) if template_id else None
    show_form = bool(request.args.get("new")) or bool(selected)
    return render_template(
        "corporate_template_master.html",
        templates=list_templates(db),
        selected_template=selected,
        show_form=show_form,
        font_options=FONT_OPTIONS,
        pdf_orientations=PDF_ORIENTATIONS,
    )


@app.route("/settings/corporate-template-master/asset/<filename>")
@login_required
def corporate_template_asset(filename):
    safe = secure_filename(filename)
    path = os.path.join(CORPORATE_TEMPLATE_DIR, safe)
    if not os.path.isfile(path):
        abort(404)
    return send_from_directory(CORPORATE_TEMPLATE_DIR, safe)


@app.route("/reports/corporate")
@login_required
def corporate_reports_hub():
    return render_template(
        "corporate_reports_hub.html",
        categories=reports_by_category(),
        status_counts=count_by_status(),
    )


@app.route("/reports/standard/<slug>/print")
@login_required
def corporate_report_stub_print(slug):
    db = get_db()
    _prepare_corporate_template_db(db)
    report_def = get_report_def(slug)
    if not report_def:
        flash("Unknown report type.")
        return redirect(url_for("corporate_reports_hub"))
    if report_def.get("status") == "wired":
        flash("This report is opened from its module record. Use Print on the document form.")
        return redirect(url_for("corporate_reports_hub"))
    if report_def.get("status") == "screen":
        endpoint = report_def.get("screen_endpoint")
        if endpoint:
            return redirect(url_for(endpoint))
        return redirect(url_for("corporate_reports_hub"))
    ctx = _build_corporate_report_context(
        db,
        slug,
        prepared_by=session.get("username", ""),
        back_url=url_for("corporate_reports_hub"),
        page_orientation="portrait",
    )
    report_data = load_standard_report_data(
        db,
        slug,
        project_id=request.args.get("project_id", type=int),
    )
    template_name = get_stub_template(slug, not report_data.get("stub", True))
    is_stub = report_data.get("stub", True)
    return render_template(
        template_name,
        ctx=ctx,
        report_label=report_def.get("label", slug),
        stub=is_stub,
        rows=report_data.get("rows") or [],
        summary=report_data.get("summary") or {},
        columns=get_report_columns(slug),
    )


@app.route("/reports/standard/<slug>/export")
@login_required
def corporate_report_export(slug):
    db = get_db()
    report_def = get_report_def(slug)
    if not report_def:
        flash("Unknown report type.")
        return redirect(url_for("corporate_reports_hub"))
    ctx = _build_corporate_report_context(
        db,
        slug,
        prepared_by=session.get("username", ""),
    )
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "Report": report_def.get("label"),
                "Category": report_def.get("category_slug", ""),
                "Document Number": ctx.get("document_number"),
                "Date": ctx.get("report_date"),
                "Prepared By": ctx.get("prepared_by"),
                "Verification Code": ctx.get("verification_code"),
                "Status": report_def.get("status"),
                "Note": "Stub export — full report content pending implementation",
            }
        ]
    )
    filename = f"maxek_{slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(REPORTS_DIR, filename)
    df.to_excel(filepath, index=False)
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


@app.route("/reports/verify")
def corporate_report_verify():
    slug = (request.args.get("slug") or "").strip()
    doc_number = (request.args.get("doc") or "").strip()
    code = (request.args.get("code") or "").strip().upper()
    report_def = get_report_def(slug)
    expected_ctx = build_print_context(
        get_db(),
        report_slug=slug,
        document_number=doc_number,
    )
    expected = (expected_ctx.get("verification_code") or "").upper()
    verified = bool(report_def and code and expected and code == expected)
    return render_template(
        "report_verify.html",
        verified=verified,
        report_label=report_def.get("label") if report_def else slug,
        doc_number=doc_number,
        code=code,
    )


def _department_tabs_payload(department_slug: str) -> tuple[dict | None, dict | None, list[dict]]:
    portal = get_department_portal(department_slug)
    nav_slug = portal["nav_slug"] if portal else department_slug
    nav_group = get_nav_group_by_slug(nav_slug)
    catalog = build_department_tab_catalog(department_slug, portal=portal, nav_group=nav_group)
    return portal, nav_group, catalog


@app.route("/api/settings/users/<int:user_id>/department-tabs", methods=["GET"])
@admin_required
def api_user_department_tabs_get(user_id):
    department_slug = (request.args.get("department") or "").strip()
    if not department_slug:
        return jsonify({"error": "department query parameter is required"}), 400
    valid_slugs = {slug for slug, _ in PERMISSION_DEPARTMENT_CHOICES}
    if department_slug not in valid_slugs:
        return jsonify({"error": "Unknown department"}), 400
    user = query_db("SELECT id FROM users WHERE id=?", (user_id,), one=True)
    if not user:
        return jsonify({"error": "User not found"}), 404
    _, _, catalog = _department_tabs_payload(department_slug)
    db = get_db()
    tabs = get_user_department_tab_state(db, user_id, department_slug, catalog)
    dept_label = dict(PERMISSION_DEPARTMENT_CHOICES).get(department_slug, department_slug)
    return jsonify(
        {
            "user_id": user_id,
            "department": department_slug,
            "department_label": dept_label,
            "tabs": tabs,
        }
    )


@app.route("/api/settings/users/<int:user_id>/department-tabs", methods=["POST"])
@admin_required
def api_user_department_tabs_save(user_id):
    payload = request.get_json(silent=True) or {}
    department_slug = (payload.get("department") or "").strip()
    granted_tabs = payload.get("tabs") or []
    if not department_slug:
        return jsonify({"error": "department is required"}), 400
    valid_slugs = {slug for slug, _ in PERMISSION_DEPARTMENT_CHOICES}
    if department_slug not in valid_slugs:
        return jsonify({"error": "Unknown department"}), 400
    if not isinstance(granted_tabs, list):
        return jsonify({"error": "tabs must be a list"}), 400
    user = query_db("SELECT id FROM users WHERE id=?", (user_id,), one=True)
    if not user:
        return jsonify({"error": "User not found"}), 404
    _, _, catalog = _department_tabs_payload(department_slug)
    db = get_db()
    save_user_department_tab_permissions(
        db, user_id, department_slug, [str(k) for k in granted_tabs], catalog
    )
    db.commit()
    return jsonify({"ok": True, "saved": len(granted_tabs)})


@app.route("/settings/users", methods=["GET", "POST"])
@admin_required
def user_settings():
    db = get_db()
    designations = query_db(
        "SELECT id, designation_name FROM designations WHERE status='Active' ORDER BY designation_name"
    )
    departments = get_departments()
    workflow_roles = ["Maker", "Checker", "Approver", "Administrator"]
    system_roles = ["Maker", "Checker", "Approver", "Admin"]

    if request.method == "POST":
        action = request.form.get("action", "save")
        user_id = request.form.get("user_id", "").strip()
        if action == "toggle" and user_id:
            row = db.execute("SELECT status FROM users WHERE id=?", (user_id,)).fetchone()
            if row:
                new_status = "Inactive" if row["status"] == "Active" else "Active"
                db.execute("UPDATE users SET status=? WHERE id=?", (new_status, user_id))
                db.commit()
                flash(f"User status updated to {new_status}.")
            return redirect(url_for("user_settings"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        staff_id = request.form.get("staff_id", "") or None
        employee_name = request.form.get("employee_name", "").strip()
        department = request.form.get("department", "").strip()
        designation_id = request.form.get("designation_id") or None
        role = request.form.get("role", "Maker").strip()
        workflow_role = request.form.get("workflow_role", "Maker").strip()
        status = request.form.get("status", "Active").strip()
        maker_departments = request.form.getlist("maker_department[]")
        maker_modules = request.form.getlist("maker_module[]")
        maker_statuses = request.form.getlist("maker_status[]")

        if staff_id and not employee_name:
            srow = db.execute(
                "SELECT staff_name FROM staff WHERE id=?", (staff_id,)
            ).fetchone()
            if srow:
                employee_name = srow["staff_name"]

        if not username or not employee_name:
            flash("Select employee from master and ensure username is set.")
            return redirect(url_for("user_settings"))

        saved_user_id = user_id
        if user_id:
            if password:
                db.execute(
                    "UPDATE users SET username=?, password=?, staff_id=?, employee_name=?, department=?, "
                    "designation_id=?, role=?, workflow_role=?, status=? WHERE id=?",
                    (username, password, staff_id, employee_name, department, designation_id,
                     role, workflow_role, status, user_id),
                )
            else:
                db.execute(
                    "UPDATE users SET username=?, staff_id=?, employee_name=?, department=?, "
                    "designation_id=?, role=?, workflow_role=?, status=? WHERE id=?",
                    (username, staff_id, employee_name, department, designation_id,
                     role, workflow_role, status, user_id),
                )
            saved_user_id = user_id
            flash("User updated successfully.")
        else:
            if not password:
                flash("Password is required for new users.")
                return redirect(url_for("user_settings"))
            try:
                cur = db.execute(
                    "INSERT INTO users(username, password, staff_id, employee_name, department, "
                    "designation_id, role, workflow_role, status) VALUES(?,?,?,?,?,?,?,?,?)",
                    (username, password, staff_id, employee_name, department, designation_id,
                     role, workflow_role, status),
                )
                saved_user_id = cur.lastrowid
                flash("User created successfully.")
            except sqlite3.IntegrityError:
                flash("Username already exists.")
                return redirect(url_for("user_settings"))

        if saved_user_id and workflow_role == "Maker":
            save_user_maker_assignments(
                db, saved_user_id, maker_departments, maker_modules, maker_statuses
            )
        elif saved_user_id:
            ensure_user_maker_assignments_table(db)
            db.execute("DELETE FROM user_maker_assignments WHERE user_id=?", (saved_user_id,))

        db.commit()
        return redirect(url_for("user_settings"))

    edit_id = request.args.get("edit")
    edit_user = None
    maker_assignments = []
    if edit_id:
        edit_user = query_db(
            "SELECT u.*, d.designation_name FROM users u "
            "LEFT JOIN designations d ON u.designation_id = d.id WHERE u.id=?",
            (edit_id,),
            one=True,
        )
        if edit_user:
            maker_assignments = get_user_maker_assignments(db, edit_id)

    staff_rows = query_db(
        "SELECT s.id, s.employee_code, s.staff_name, s.department, s.designation_id, "
        "d.designation_name FROM staff s "
        "LEFT JOIN designations d ON s.designation_id = d.id "
        "WHERE s.status='Active' ORDER BY s.staff_name"
    )
    workflow_modules = get_workflow_modules()

    rows = query_db(
        "SELECT u.*, d.designation_name FROM users u "
        "LEFT JOIN designations d ON u.designation_id = d.id ORDER BY u.id DESC"
    )
    enriched = []
    for row in rows:
        r = dict(row)
        r["workflow_access"] = get_workflow_access_label(
            db, r.get("designation_id"), r.get("workflow_role")
        )
        if r.get("workflow_role"):
            r["workflow_access"] = r["workflow_role"]
        enriched.append(r)

    return render_template(
        "users.html",
        rows=enriched,
        designations=designations,
        departments=departments,
        workflow_roles=workflow_roles,
        system_roles=system_roles,
        edit_user=edit_user,
        staff_rows=staff_rows,
        workflow_modules=workflow_modules,
        maker_assignments=maker_assignments,
        max_maker_slots=MAX_MAKER_ASSIGNMENTS,
        permission_departments=PERMISSION_DEPARTMENT_CHOICES,
    )


USER_MGMT_WORKFLOW_ROLES = ("Maker", "Checker", "Approver", "Administrator")
USER_MGMT_SYSTEM_ROLES = ("User", "Guest", "Admin", "Customer Admin", "Manager", "Cashier", "Accountant", "Store Keeper", "HR User")


@app.route("/admin/users", methods=["GET", "POST"])
@login_required
def user_management():
    """Standalone user creation — not tied to company staff."""
    if not is_admin_user() and not is_customer_admin_user():
        flash("Administrator access required.")
        return redirect(url_for("dashboard"))
    db = get_db()
    tenant_customer_id = session.get("customer_id")
    allowed_system_roles = USER_MGMT_SYSTEM_ROLES
    if is_customer_admin_user() and not is_super_admin_user():
        allowed_system_roles = CUSTOMER_ADMIN_CREATABLE_ROLES

    if request.method == "POST":
        action = request.form.get("action", "create")
        user_id = request.form.get("user_id", "").strip()

        if action == "toggle" and user_id:
            row = db.execute("SELECT status FROM users WHERE id=?", (user_id,)).fetchone()
            if row:
                new_status = "Inactive" if row["status"] == "Active" else "Active"
                db.execute("UPDATE users SET status=? WHERE id=?", (new_status, user_id))
                db.commit()
                flash(f"User status updated to {new_status}.")
            return redirect(url_for("user_management", tab="list"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        display_name = request.form.get("display_name", "").strip()
        workflow_role = request.form.get("workflow_role", "Maker").strip()
        system_role = request.form.get("system_role", "User").strip()
        status = request.form.get("status", "Active").strip()

        if workflow_role not in USER_MGMT_WORKFLOW_ROLES:
            flash("Invalid workflow role selected.")
            return redirect(url_for("user_management", tab="create"))

        if system_role not in allowed_system_roles:
            flash("Invalid system role selected.")
            return redirect(url_for("user_management", tab="create"))

        if is_customer_admin_user() and not is_super_admin_user():
            if system_role in ("Admin", SUPER_ADMIN_ROLE, "Customer Admin"):
                flash("Customer Admins cannot assign that role.")
                return redirect(url_for("user_management", tab="create"))

        if workflow_role == "Administrator":
            system_role = "Admin"

        if not username:
            flash("Username is required.")
            return redirect(url_for("user_management", tab="create"))

        if not password:
            flash("Password is required.")
            return redirect(url_for("user_management", tab="create"))

        if password != confirm_password:
            flash("Password and confirmation do not match.")
            return redirect(url_for("user_management", tab="create"))

        if len(password) < 4:
            flash("Password must be at least 4 characters.")
            return redirect(url_for("user_management", tab="create"))

        employee_name = display_name or username

        existing = db.execute(
            "SELECT id FROM users WHERE username=? AND (customer_id IS ? OR (customer_id IS NULL AND ? IS NULL))",
            (username, tenant_customer_id, tenant_customer_id),
        ).fetchone()
        if existing:
            flash("Username already exists. Choose a different login ID.")
            return redirect(url_for("user_management", tab="create"))

        if tenant_customer_id:
            try:
                assert_user_limit_not_exceeded(db, tenant_customer_id)
            except ValueError as exc:
                flash(str(exc))
                return redirect(url_for("user_management", tab="create"))

        try:
            db.execute(
                "INSERT INTO users(username, password, role, workflow_role, employee_name, status, customer_id) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    username,
                    hash_password(password),
                    system_role,
                    workflow_role,
                    employee_name,
                    status,
                    tenant_customer_id,
                ),
            )
            db.commit()
            if tenant_customer_id:
                sync_customer_usage_counts(db, tenant_customer_id)
                db.commit()
            flash(f"User '{username}' created successfully.")
            return redirect(url_for("user_management", tab="list"))
        except sqlite3.IntegrityError:
            flash("Username already exists.")
            return redirect(url_for("user_management", tab="create"))

    rows = query_db(
        "SELECT u.*, d.designation_name, s.staff_name AS linked_staff_name "
        "FROM users u "
        "LEFT JOIN designations d ON u.designation_id = d.id "
        "LEFT JOIN staff s ON u.staff_id = s.id "
        + ("WHERE u.customer_id=? " if tenant_customer_id and not is_super_admin_user() else "")
        + "ORDER BY u.id DESC",
        (tenant_customer_id,) if tenant_customer_id and not is_super_admin_user() else (),
    )
    enriched = []
    for row in rows:
        r = dict(row)
        if r.get("workflow_role"):
            r["workflow_access"] = r["workflow_role"]
        else:
            r["workflow_access"] = get_workflow_access_label(
                db, r.get("designation_id"), r.get("workflow_role")
            )
        r["user_type"] = "Staff-linked" if r.get("staff_id") else "Standalone"
        enriched.append(r)

    active_tab = request.args.get("tab", "create")
    if active_tab not in ("create", "list"):
        active_tab = "create"

    return render_template(
        "user_management.html",
        rows=enriched,
        workflow_roles=USER_MGMT_WORKFLOW_ROLES,
        system_roles=allowed_system_roles,
        active_tab=active_tab,
    )


@app.route("/settings/user-activity")
@admin_required
def user_activity_monitor():
    db = get_db()
    date_from = request.args.get("from_date", "").strip() or None
    date_to = request.args.get("to_date", "").strip() or None
    active_tab = request.args.get("tab", "dashboard")
    if active_tab not in ("dashboard", "login", "screen", "idle"):
        active_tab = "dashboard"

    dashboard = get_activity_dashboard(db, date_from=date_from, date_to=date_to)
    login_rows = get_login_report(db, date_from=date_from, date_to=date_to)
    screen_rows = get_screen_activity_report(db, date_from=date_from, date_to=date_to)
    idle_rows = get_idle_report(
        db,
        date_from=date_from,
        date_to=date_to,
        idle_threshold_minutes=DEFAULT_IDLE_THRESHOLD_MINUTES,
    )

    return render_template(
        "user_activity.html",
        active_tab=active_tab,
        date_from=dashboard["date_from"],
        date_to=dashboard["date_to"],
        dashboard=dashboard,
        login_rows=login_rows,
        screen_rows=screen_rows,
        idle_rows=idle_rows,
        idle_threshold_minutes=DEFAULT_IDLE_THRESHOLD_MINUTES,
        retention_days=90,
    )


@app.route("/settings/workflow", methods=["GET", "POST"])
@app.route("/settings/workflow-matrix", methods=["GET", "POST"])
@login_required
def workflow_settings():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "add_designation":
            name = request.form.get("designation_name", "").strip()
            if name:
                try:
                    db.execute(
                        "INSERT INTO designations(designation_name, status) VALUES(?, 'Active')",
                        (name,),
                    )
                    db.commit()
                    flash(f"Designation '{name}' added.")
                except sqlite3.IntegrityError:
                    flash("Designation already exists.")
        else:
            module_id = request.form.get("module_id", "").strip()
            maker_id = request.form.get("maker_designation_id", "") or None
            checker_id = request.form.get("checker_designation_id", "") or None
            approver_id = request.form.get("approver_designation_id", "") or None
            workflow_mode = request.form.get("workflow_mode", DEFAULT_WORKFLOW_MODE).strip()
            if workflow_mode not in WORKFLOW_MODES:
                workflow_mode = DEFAULT_WORKFLOW_MODE
            if workflow_mode == "maker_only" and not maker_id:
                flash("Maker designation is required for Maker-only mode.")
                return redirect(url_for("workflow_settings"))
            if workflow_mode_requires_checker(workflow_mode) and not checker_id:
                flash("Checker designation is required for this workflow mode.")
                return redirect(url_for("workflow_settings"))
            if workflow_mode_requires_approver(workflow_mode) and not approver_id:
                flash("Approver designation is required for this workflow mode.")
                return redirect(url_for("workflow_settings"))
            if workflow_mode == "checker_approver_only" and not checker_id:
                flash("Checker designation is required for Checker + Approver mode.")
                return redirect(url_for("workflow_settings"))
            maker_name = db.execute(
                "SELECT designation_name FROM designations WHERE id=?", (maker_id,)
            ).fetchone() if maker_id else None
            checker_name = db.execute(
                "SELECT designation_name FROM designations WHERE id=?", (checker_id,)
            ).fetchone() if checker_id else None
            approver_name = db.execute(
                "SELECT designation_name FROM designations WHERE id=?", (approver_id,)
            ).fetchone() if approver_id else None
            parts = [
                maker_name["designation_name"] if maker_name else None,
                checker_name["designation_name"] if checker_name else None,
                approver_name["designation_name"] if approver_name else None,
            ]
            flow = " → ".join(p for p in parts if p) or WORKFLOW_MODE_LABELS.get(workflow_mode, workflow_mode)
            db.execute(
                "UPDATE workflow_master SET maker_designation_id=?, checker_designation_id=?, "
                "approver_designation_id=?, workflow_role_mapping=?, workflow_mode=? WHERE module_id=?",
                (maker_id, checker_id, approver_id, flow, workflow_mode, module_id),
            )
            db.commit()
            flash("Workflow configuration saved.")
        return redirect(url_for("workflow_settings"))

    workflows = query_db(
        "SELECT wm.*, "
        "dm.designation_name AS maker_designation, "
        "dc.designation_name AS checker_designation, "
        "da.designation_name AS approver_designation "
        "FROM workflow_master wm "
        "LEFT JOIN designations dm ON wm.maker_designation_id = dm.id "
        "LEFT JOIN designations dc ON wm.checker_designation_id = dc.id "
        "LEFT JOIN designations da ON wm.approver_designation_id = da.id "
        "ORDER BY wm.module_name"
    )
    designations = query_db(
        "SELECT * FROM designations WHERE status='Active' ORDER BY designation_name"
    )
    return render_template(
        "workflow_settings.html",
        workflows=workflows,
        designations=designations,
        workflow_modes=WORKFLOW_MODES,
        workflow_mode_labels=WORKFLOW_MODE_LABELS,
        default_workflow_mode=DEFAULT_WORKFLOW_MODE,
    )


@app.route("/reports/workflow-audit")
@login_required
def workflow_audit_report():
    db = get_db()
    module_id = request.args.get("module_id", "")
    status_key = request.args.get("status", "")
    modules = query_db(
        "SELECT module_id, module_name FROM workflow_master ORDER BY module_name"
    )
    rows = get_workflow_audit_report(
        db,
        module_id=module_id or None,
        status_filter=status_key or None,
    )
    export = request.args.get("export")
    if export == "xlsx" and rows:
        df = pd.DataFrame(rows)
        filename = f"workflow_audit_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
        file_path = os.path.join(REPORTS_DIR, filename)
        df.to_excel(file_path, index=False)
        return send_from_directory(REPORTS_DIR, filename, as_attachment=True)
    return render_template(
        "workflow_audit_report.html",
        rows=rows,
        modules=modules,
        selected_module=module_id,
        selected_status=status_key,
    )


@app.route("/approvals")
@app.route("/approvals/<role>")
@login_required
def approvals(role="checker"):
    db = get_db()
    user_id = session.get("user_id")
    admin = is_admin_user()
    caps = user_workflow_capabilities(db, user_id, admin)
    if role == "maker" and not caps.get("can_create") and not admin:
        role = "checker"
    if role == "checker" and not caps.get("can_verify") and not admin:
        role = "approver" if caps.get("can_approve") else "maker"
    if role == "approver" and not caps.get("can_approve") and not admin:
        role = "checker" if caps.get("can_verify") else "maker"
    tab = request.args.get("tab", "pending").strip()
    if tab not in ("pending", "history"):
        tab = "pending"
    module_key = request.args.get("module", "").strip()
    module_ids = APPROVAL_MODULE_GROUPS.get(module_key)
    counts = get_pending_counts(db, user_id, admin)
    raw_items = get_pending_items(db, user_id, role, admin)
    if module_ids:
        raw_items = [item for item in raw_items if item.get("module_id") in module_ids]
    items = _enrich_approval_items(db, raw_items, role=role, include_history=False)
    pending_items, history_items = _split_approval_items(items, role)
    display_items = pending_items if tab == "pending" else history_items
    return render_template(
        "approvals.html",
        role=role,
        tab=tab,
        module_filter=module_key,
        counts=counts,
        pending_items=pending_items,
        history_items=history_items,
        items=display_items,
        module_routes=MODULE_ROUTES,
    )


@app.route("/approvals/detail/<int:approval_id>")
@login_required
def approval_detail(approval_id):
    db = get_db()
    user_id = session.get("user_id")
    admin = is_admin_user()
    item = get_approval_request_by_id(db, approval_id)
    if not item:
        flash("Approval record not found.")
        return redirect(url_for("approvals"))
    role = request.args.get("role", "checker").strip()
    if role not in ("maker", "checker", "approver"):
        role = "checker"
    enriched = summarize_approval_item(db, item, role_type=role, include_history=True)
    mod_route = MODULE_ROUTES.get(item.get("module_id"), "dashboard")
    return render_template(
        "approval_detail.html",
        item=enriched,
        role=role,
        module_route=mod_route,
        module_routes=MODULE_ROUTES,
    )


@app.route("/approvals/action", methods=["POST"])
@login_required
def approval_action():
    approval_id = request.form.get("approval_id", "")
    action = request.form.get("action", "")
    comments = request.form.get("comments", "")
    ok, message = advance_approval(
        get_db(),
        int(approval_id),
        session.get("user_id"),
        action,
        comments,
        is_admin_user(),
    )
    if ok:
        _sync_payroll_run_after_workflow(get_db(), int(approval_id))
        _sync_accounts_after_workflow(get_db(), int(approval_id))
        _sync_treasury_after_workflow(get_db(), int(approval_id))
        _sync_store_after_workflow(get_db(), int(approval_id))
        _sync_subcontract_payments_after_workflow(get_db(), int(approval_id))
        _sync_client_billing_after_workflow(get_db(), int(approval_id))
    get_db().commit()
    flash(message, "success" if ok else "warning")
    role = request.form.get("role") or request.args.get("role") or "checker"
    return redirect(request.referrer or url_for("approvals", role=role))


@app.route("/workflow/reopen", methods=["POST"])
@login_required
def workflow_reopen():
    if not is_admin_user():
        flash("Only System Administrator can reopen transactions.")
        return redirect(request.referrer or url_for("dashboard"))
    approval_id = request.form.get("approval_id", "")
    reason = request.form.get("reason", "")
    ok, message = reopen_transaction(
        get_db(), int(approval_id), session.get("user_id"), reason, True
    )
    if ok:
        db = get_db()
        req = db.execute(
            "SELECT record_table, record_id FROM approval_requests WHERE id=?",
            (int(approval_id),),
        ).fetchone()
        if req and req["record_table"] in ("account_expenses", "payment_vouchers", "receipt_vouchers"):
            void_journal_for_reference(db, req["record_table"], req["record_id"])
        if req and req["record_table"] in ("bank_payments", "bank_receipts"):
            void_treasury_on_reversal(db, req["record_table"], req["record_id"], session.get("username", "system"))
        if req and req["record_table"] in ("store_receipts", "store_issues", "material_transfers"):
            void_stock_for_reference(db, req["record_table"], req["record_id"])
    get_db().commit()
    flash(message, "success" if ok else "warning")
    return redirect(request.referrer or url_for("approvals"))


@app.route("/workflow/delete", methods=["POST"])
@login_required
def workflow_delete_record():
    table = request.form.get("table", "").strip()
    record_id = request.form.get("record_id", "").strip()
    module_id = request.form.get("module_id", "").strip()
    redirect_to = request.form.get("redirect_to", "dashboard").strip()
    if redirect_to not in MODULE_ROUTES.values() and redirect_to not in (
        "dashboard", "attendance", "timesheet", "approvals", "notifications",
    ):
        redirect_to = "dashboard"
    if not table or not record_id or not module_id:
        flash("Invalid delete request.")
        return redirect(url_for(redirect_to))
    db = get_db()
    ok, message = delete_workflow_record(
        db, table, record_id, module_id,
        session.get("user_id"), is_admin_user(),
    )
    if ok:
        db.commit()
        flash(message, "success")
    else:
        flash(message, "warning")
    return redirect(url_for(redirect_to))


@app.route("/notifications")
@login_required
def notifications():
    db = get_db()
    user_id = session.get("user_id")
    items = get_notifications(db, user_id, limit=50)
    return render_template("notifications.html", items=items)


@app.route("/notifications/read", methods=["POST"])
@login_required
def notifications_read():
    mark_notifications_read(get_db(), session.get("user_id"))
    get_db().commit()
    return redirect(request.referrer or url_for("notifications"))


def _submit_module_request(module_id, table, fields_sql, values):
    db = get_db()
    db.execute(f"INSERT INTO {table}({fields_sql}) VALUES({','.join('?' * len(values))})", values)
    record_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    create_approval_request(
        db, module_id, record_id, table,
        session.get("username", ""), session.get("user_id")
    )
    db.commit()


def _module_edit_context(module_id, table, endpoint):
    record_id = request.form.get("record_id", "").strip()
    if not record_id:
        return None, None
    db = get_db()
    existing = db.execute(
        f"SELECT approval_status FROM {table} WHERE id=?", (record_id,)
    ).fetchone()
    if not existing:
        flash("Record not found.")
        return "redirect", url_for(endpoint)
    edit_role = get_edit_role_for_user(
        db, session.get("user_id"), module_id,
        existing["approval_status"], is_admin_user(),
    )
    if not edit_role:
        flash("This record is locked and cannot be edited.")
        return "redirect", url_for(endpoint)
    return int(record_id), edit_role


def _complete_module_save(db, module_id, table, record_id, edit_role):
    accounts_tables = ("account_expenses", "payment_vouchers", "receipt_vouchers")
    treasury_tables = ("bank_payments", "bank_receipts")
    if edit_role == "maker":
        if table in accounts_tables:
            void_journal_for_reference(db, table, record_id)
        if table in treasury_tables:
            void_treasury_on_reversal(db, table, record_id, session.get("username", "system"))
        db.execute(
            f"UPDATE {table} SET approval_status=? WHERE id=?",
            ("Pending Checker", record_id),
        )
        resubmit_record(db, module_id, record_id, table, session.get("user_id"))
        flash("Saved. Status: Pending Checker.")
    else:
        flash("Changes saved. Record remains locked at current workflow stage.")
    db.commit()


def _module_view_fields(table_columns, row_keys, record):
    """Build view-mode field rows in Python (avoids Jinja zip()/index mismatches)."""
    if not record:
        return []
    if len(table_columns) != len(row_keys):
        app.logger.warning(
            "Module view field mismatch: %d columns vs %d keys",
            len(table_columns),
            len(row_keys),
        )
    rec = dict(record)
    return [
        {"label": col, "key": key, "value": rec.get(key)}
        for col, key in zip(table_columns, row_keys)
    ]


def _module_page_state(module_id, table, endpoint, record_sql):
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = query_db(record_sql, (view_id,), one=True)
        if view_record:
            view_record = dict(view_record)
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record.get("approval_status")
            )
    elif edit_id:
        edit_record = query_db(record_sql, (edit_id,), one=True)
        if edit_record:
            edit_record = dict(edit_record)
            edit_role = get_edit_role_for_user(
                get_db(), session.get("user_id"), module_id,
                edit_record.get("approval_status"), is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return {"redirect": url_for(endpoint, view=edit_id)}
            wf_ctx = {"edit_role": edit_role}
    return {
        "view_record": view_record,
        "edit_record": edit_record,
        "history": wf_ctx.get("history"),
        "edit_role": wf_ctx.get("edit_role"),
        "can_reopen": bool(wf_ctx.get("can_reopen", False)),
        "approval_id": wf_ctx.get("approval_id"),
        "audit_trail": wf_ctx.get("audit_trail"),
        "module_id": module_id,
    }


def _enrich_module_rows_edit_access(rows, module_id):
    """Attach can_edit per row using workflow edit rules (maker/checker/approver)."""
    db = get_db()
    user_id = session.get("user_id")
    admin = is_admin_user()
    enriched = []
    for row in rows:
        r = dict(row)
        edit_role = get_edit_role_for_user(
            db, user_id, module_id, r.get("approval_status"), admin
        )
        r["can_edit"] = bool(edit_role)
        r["row_edit_role"] = edit_role
        enriched.append(r)
    return enriched


@app.route("/material-request", methods=["GET", "POST"])
@login_required
def material_request():
    db = get_db()
    _prepare_store_db(db)
    module_id, table, endpoint = "material_request", "material_requests", "material_request"
    record_sql = (
        "SELECT m.*, p.project_name, mat.code AS material_code "
        "FROM material_requests m "
        "LEFT JOIN projects p ON m.project_id = p.id "
        "LEFT JOIN materials mat ON m.material_id = mat.id "
        "WHERE m.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    materials = list_materials(db, active_only=True)
    workflow = get_workflow_for_module(db, module_id)
    select_material = request.args.get("select_material", type=int)
    if request.method == "POST":
        form_action = request.form.get("form_action", "save").strip()
        if form_action == "add_material":
            try:
                new_id = save_material(db, request.form, None)
                db.commit()
                flash("Material added and selected in the form.")
                return redirect(
                    url_for(endpoint, select_material=new_id) + "#material-request-form"
                )
            except (ValueError, sqlite3.IntegrityError) as exc:
                flash(str(exc) if str(exc) else "Unable to save material — code may already exist.")
                return redirect(url_for(endpoint) + "#material-request-form")
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        try:
            material_id, item_name, unit = resolve_material_request_from_form(db, request.form)
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.referrer or url_for(endpoint))
        if record_id:
            db.execute(
                "UPDATE material_requests SET project_id=?, request_date=?, material_id=?, item_name=?, "
                "quantity=?, unit=?, remarks=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("request_date", ""),
                    material_id,
                    item_name,
                    float(request.form.get("quantity") or 0),
                    unit,
                    request.form.get("remarks", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, request_date, material_id, item_name, quantity, unit, remarks, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("request_date", ""),
                material_id,
                item_name,
                float(request.form.get("quantity") or 0),
                unit,
                request.form.get("remarks", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT m.*, p.project_name, mat.code AS material_code "
        "FROM material_requests m "
        "LEFT JOIN projects p ON m.project_id = p.id "
        "LEFT JOIN materials mat ON m.material_id = mat.id "
        "ORDER BY m.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    table_columns = ["Date", "Project", "Material", "Qty", "By"]
    row_keys = ["request_date", "project_name", "item_name", "quantity", "created_by"]
    return render_template(
        "material_request.html",
        module_title="Store / Material Request",
        workflow=workflow,
        projects=projects,
        materials=materials,
        categories=MATERIAL_CATEGORIES,
        units=MATERIAL_UNITS,
        select_material=select_material,
        table_columns=table_columns,
        row_keys=row_keys,
        view_fields=_module_view_fields(table_columns, row_keys, page.get("view_record")),
        rows=_enrich_module_rows_edit_access([dict(r) for r in rows], module_id),
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/purchase-request", methods=["GET", "POST"])
@login_required
def purchase_request():
    module_id, table, endpoint = "purchase_request", "purchase_requests", "purchase_request"
    record_sql = (
        "SELECT pr.*, p.project_name FROM purchase_requests pr "
        "LEFT JOIN projects p ON pr.project_id = p.id WHERE pr.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE purchase_requests SET project_id=?, request_date=?, item_description=?, "
                "quantity=?, estimated_cost=?, remarks=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("request_date", ""),
                    request.form.get("item_description", ""),
                    float(request.form.get("quantity") or 0),
                    float(request.form.get("estimated_cost") or 0),
                    request.form.get("remarks", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, request_date, item_description, quantity, estimated_cost, remarks, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("request_date", ""),
                request.form.get("item_description", ""),
                float(request.form.get("quantity") or 0),
                float(request.form.get("estimated_cost") or 0),
                request.form.get("remarks", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT pr.*, p.project_name FROM purchase_requests pr "
        "LEFT JOIN projects p ON pr.project_id = p.id ORDER BY pr.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    table_columns = ["Date", "Project", "Description", "Cost", "By"]
    row_keys = ["request_date", "project_name", "item_description", "estimated_cost", "created_by"]
    return render_template(
        "module_request.html",
        module_title="Purchase Request",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "request_date", "label": "Request Date", "type": "date", "required": True},
            {"name": "item_description", "label": "Item Description", "type": "text", "required": True},
            {"name": "quantity", "label": "Quantity", "type": "number", "required": True},
            {"name": "estimated_cost", "label": "Estimated Cost", "type": "number", "required": True},
            {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
        ],
        table_columns=table_columns,
        row_keys=row_keys,
        view_fields=_module_view_fields(table_columns, row_keys, page.get("view_record")),
        rows=_enrich_module_rows_edit_access([dict(r) for r in rows], module_id),
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/project-expenses", methods=["GET", "POST"])
@login_required
def project_expenses():
    module_id, table, endpoint = "project_expenses", "project_expenses", "project_expenses"
    record_sql = (
        "SELECT e.*, p.project_name FROM project_expenses e "
        "LEFT JOIN projects p ON e.project_id = p.id WHERE e.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE project_expenses SET project_id=?, expense_date=?, expense_category=?, "
                "amount=?, description=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("expense_date", ""),
                    request.form.get("expense_category", ""),
                    float(request.form.get("amount") or 0),
                    request.form.get("description", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, expense_date, expense_category, amount, description, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("expense_date", ""),
                request.form.get("expense_category", ""),
                float(request.form.get("amount") or 0),
                request.form.get("description", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT e.*, p.project_name FROM project_expenses e "
        "LEFT JOIN projects p ON e.project_id = p.id "
        + ("WHERE e.dpr_measurement_id=?" if request.args.get("dpr_measurement_id", type=int) else "")
        + " ORDER BY e.id DESC",
        ((request.args.get("dpr_measurement_id", type=int),) if request.args.get("dpr_measurement_id", type=int) else ()),
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Project Expenses",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "expense_date", "label": "Expense Date", "type": "date", "required": True},
            {"name": "expense_category", "label": "Category", "type": "text", "required": True},
            {"name": "amount", "label": "Amount", "type": "number", "required": True},
            {"name": "description", "label": "Description", "type": "textarea", "required": False},
        ],
        table_columns=["Date", "Project", "Category", "Amount", "DPR", "By"],
        row_keys=["expense_date", "project_name", "expense_category", "amount", "dpr_measurement_id", "created_by"],
        view_fields=_module_view_fields(
            ["Date", "Project", "Category", "Amount", "DPR", "By"],
            ["expense_date", "project_name", "expense_category", "amount", "dpr_measurement_id", "created_by"],
            page.get("view_record"),
        ),
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/head-office-expenses", methods=["GET", "POST"])
@login_required
def head_office_expenses():
    db = get_db()
    prepare_head_office_expenses_db(db)
    module_id, table, endpoint = "head_office_expenses", "head_office_expenses", "head_office_expenses"
    record_sql = (
        "SELECT h.*, c.code AS account_code, c.name AS account_name "
        "FROM head_office_expenses h "
        "LEFT JOIN chart_accounts c ON h.chart_account_id = c.id WHERE h.id=?"
    )
    if request.method == "POST":
        inline = _handle_add_chart_head_form(db, endpoint, "#head-office-expenses-form")
        if inline:
            return inline
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        chart_account_id = request.form.get("chart_account_id", "").strip()
        if not chart_account_id.isdigit():
            flash("Select a Head of Account.")
            return redirect(url_for(endpoint) + "#head-office-expenses-form")
        expense_date = request.form.get("expense_date", "")
        expense_category = request.form.get("expense_category", "")
        amount = float(request.form.get("amount") or 0)
        department = request.form.get("department", "")
        description = request.form.get("description", "")
        if record_id:
            db.execute(
                "UPDATE head_office_expenses SET chart_account_id=?, expense_date=?, expense_category=?, "
                "amount=?, department=?, description=? WHERE id=?",
                (
                    int(chart_account_id),
                    expense_date,
                    expense_category,
                    amount,
                    department,
                    description,
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id,
            table,
            "chart_account_id, expense_date, expense_category, amount, department, description, created_by, approval_status",
            (
                int(chart_account_id),
                expense_date,
                expense_category,
                amount,
                department,
                description,
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))

    rows = query_db(
        "SELECT h.*, c.code AS account_code, c.name AS account_name "
        "FROM head_office_expenses h "
        "LEFT JOIN chart_accounts c ON h.chart_account_id = c.id "
        "ORDER BY h.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    view_record = page.get("view_record")
    edit_record = page.get("edit_record")
    wf_ctx = {}
    if view_record:
        wf_ctx = _workflow_view_context(
            module_id, view_record["id"], table, view_record.get("approval_status")
        )
    elif edit_record:
        wf_ctx = {"edit_role": page.get("edit_role")}
    departments = [
        row["department_name"]
        for row in query_db(
            "SELECT department_name FROM departments WHERE status='Active' ORDER BY department_name"
        )
    ]
    chart_heads = list_expense_chart_heads(db)
    return render_template(
        "head_office_expenses.html",
        rows=[dict(r) for r in rows],
        view_record=view_record,
        edit_record=edit_record,
        chart_heads=chart_heads,
        chart_heads_json=chart_accounts_for_js(db),
        account_types=ACCOUNT_TYPES,
        departments=departments,
        default_date=datetime.now().strftime("%Y-%m-%d"),
        select_chart_head=request.args.get("select_chart_head", type=int),
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role") or page.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
        module_endpoint=endpoint,
        delete_table=table,
        module_id=module_id,
    )


@app.route("/subcontract-request", methods=["GET", "POST"])
@login_required
def subcontract_request():
    module_id, table, endpoint = "subcontract", "subcontract_requests", "subcontract_request"
    record_sql = (
        "SELECT s.*, p.project_name, sc.subcontractor_name FROM subcontract_requests s "
        "LEFT JOIN projects p ON s.project_id = p.id "
        "LEFT JOIN subcontractors sc ON s.subcontractor_id = sc.id WHERE s.id=?"
    )
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    subcontractors = query_db("SELECT id, subcontractor_name FROM subcontractors ORDER BY subcontractor_name")
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE subcontract_requests SET project_id=?, subcontractor_id=?, work_description=?, "
                "contract_amount=?, start_date=?, remarks=? WHERE id=?",
                (
                    request.form.get("project_id") or None,
                    request.form.get("subcontractor_id") or None,
                    request.form.get("work_description", ""),
                    float(request.form.get("contract_amount") or 0),
                    request.form.get("start_date", ""),
                    request.form.get("remarks", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "project_id, subcontractor_id, work_description, contract_amount, start_date, remarks, created_by, approval_status",
            (
                request.form.get("project_id") or None,
                request.form.get("subcontractor_id") or None,
                request.form.get("work_description", ""),
                float(request.form.get("contract_amount") or 0),
                request.form.get("start_date", ""),
                request.form.get("remarks", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(
        "SELECT s.*, p.project_name, sc.subcontractor_name FROM subcontract_requests s "
        "LEFT JOIN projects p ON s.project_id = p.id "
        "LEFT JOIN subcontractors sc ON s.subcontractor_id = sc.id ORDER BY s.id DESC"
    )
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Subcontract",
        workflow=workflow,
        form_fields=[
            {"name": "project_id", "label": "Project", "type": "select", "required": True,
             "options": [{"value": p["id"], "label": p["project_name"]} for p in projects]},
            {"name": "subcontractor_id", "label": "Subcontractor", "type": "select", "required": True,
             "options": [{"value": s["id"], "label": s["subcontractor_name"]} for s in subcontractors]},
            {"name": "work_description", "label": "Work Description", "type": "text", "required": True},
            {"name": "contract_amount", "label": "Contract Amount", "type": "number", "required": True},
            {"name": "start_date", "label": "Start Date", "type": "date", "required": True},
            {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
        ],
        table_columns=["Project", "Subcontractor", "Amount", "Start", "By"],
        row_keys=["project_name", "subcontractor_name", "contract_amount", "start_date", "created_by"],
        view_fields=_module_view_fields(
            ["Project", "Subcontractor", "Amount", "Start", "By"],
            ["project_name", "subcontractor_name", "contract_amount", "start_date", "created_by"],
            page.get("view_record"),
        ),
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


def _project_options():
    return [
        {"value": project["id"], "label": project["project_name"]}
        for project in query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    ]


def _render_standard_module(module_id, table, endpoint, module_title, form_fields,
                            table_columns, row_keys, record_sql, rows_sql,
                            insert_fields, value_getter, update_sql, update_getter):
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(update_sql, (*update_getter(), record_id))
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table, insert_fields,
            (*value_getter(), session.get("username", ""), "Pending Checker"),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db(rows_sql)
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title=module_title,
        workflow=workflow,
        form_fields=form_fields,
        table_columns=table_columns,
        row_keys=row_keys,
        view_fields=_module_view_fields(table_columns, row_keys, page.get("view_record")),
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


def _insert_boq_lines(db, boq_id, project_id, lines, actor, now_ts=None):
    if now_ts is None:
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for line in lines:
        item_code = boq_item_code(line["line_no"])
        db.execute(
            "INSERT INTO boq_items(boq_id, line_no, item_code, project_id, item_description, quantity, unit, "
            "rate, amount, created_by, created_at, approval_status, is_deleted) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0)",
            (
                boq_id, line["line_no"], item_code, project_id, line["item_description"],
                line["quantity"], line["unit"], line["rate"], line["amount"],
                actor, now_ts, RECORD_PENDING_CHECKER,
            ),
        )


@app.route("/boq-management", methods=["GET", "POST"])
@login_required
def boq_management():
    db = get_db()
    ensure_boq_master_table(db)
    module_id, table, endpoint = "boq", "boq_master", "boq_management"
    user_id = session.get("user_id")
    admin = is_admin_user()
    wf_ctx = {}

    if request.method == "POST":
        form_action = request.form.get("form_action", "").strip()
        if form_action == "delete_boq":
            boq_id = request.form.get("boq_id", "").strip()
            if not boq_id.isdigit():
                flash("Invalid BOQ delete request.")
                return redirect(url_for(endpoint))
            existing_boq = query_db(
                "SELECT * FROM boq_master WHERE id=? AND COALESCE(is_deleted, 0)=0",
                (boq_id,),
                one=True,
            )
            if not existing_boq:
                flash("BOQ record not found.")
                return redirect(url_for(endpoint))
            status = existing_boq["approval_status"] or RECORD_PENDING_CHECKER
            if not admin:
                if not can_maker_delete(status):
                    flash("This BOQ cannot be deleted after verification.")
                    return redirect(url_for(endpoint))
                if not user_matches_stage(db, user_id, module_id, "maker", admin):
                    flash("You are not authorized to delete this BOQ.")
                    return redirect(url_for(endpoint))
            username = session.get("username", "")
            now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "UPDATE boq_master SET is_deleted=1, deleted_by=?, deleted_at=? WHERE id=?",
                (username, now_ts, boq_id),
            )
            db.execute(
                "UPDATE boq_items SET is_deleted=1, deleted_by=?, deleted_at=? WHERE boq_id=?",
                (username, now_ts, boq_id),
            )
            approval = get_approval_request(db, module_id, int(boq_id), table)
            if approval:
                db.execute(
                    "DELETE FROM approval_audit WHERE approval_request_id=?",
                    (approval["id"],),
                )
                db.execute("DELETE FROM approval_requests WHERE id=?", (approval["id"],))
            db.commit()
            flash(f"BOQ {existing_boq['boq_number']} deleted.")
            return redirect(url_for(endpoint))

        project_id = request.form.get("project_id", "").strip()
        boq_id = request.form.get("boq_id", "").strip()
        lines, parse_error = _parse_boq_line_items()

        if not project_id:
            flash("Select a project.")
            return redirect(url_for(endpoint) + "#boq-form")
        if parse_error:
            flash(parse_error)
            return redirect(url_for(endpoint) + "#boq-form")
        if not lines:
            flash("Add at least one BOQ line item with a description.")
            return redirect(url_for(endpoint) + "#boq-form")
        if len(lines) > MAX_BOQ_LINES:
            flash(f"Maximum {MAX_BOQ_LINES} line items allowed per BOQ.")
            return redirect(url_for(endpoint) + "#boq-form")

        total_amount = round(sum(line["amount"] for line in lines), 2)
        created_by = session.get("username", "")
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if boq_id:
            existing_boq = query_db(
                "SELECT * FROM boq_master WHERE id=? AND COALESCE(is_deleted, 0)=0",
                (boq_id,),
                one=True,
            )
            if not existing_boq:
                flash("BOQ record not found.")
                return redirect(url_for(endpoint) + "#boq-form")
            edit_role = get_edit_role_for_user(
                db, user_id, module_id, existing_boq["approval_status"], admin
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=boq_id))
            boq_number = existing_boq["boq_number"]
            db.execute(
                "UPDATE boq_master SET project_id=?, total_amount=?, line_count=?, "
                "modified_by=?, modified_at=? WHERE id=?",
                (project_id, total_amount, len(lines), created_by, created_at, boq_id),
            )
            db.execute("DELETE FROM boq_items WHERE boq_id=?", (boq_id,))
            _insert_boq_lines(db, boq_id, project_id, lines, created_by, created_at)
            _complete_module_save(db, module_id, table, int(boq_id), edit_role)
            return redirect(url_for(endpoint, view=boq_id))

        boq_number = generate_boq_number(db, int(project_id))
        db.execute(
            "INSERT INTO boq_master(boq_number, project_id, total_amount, line_count, "
            "created_by, approval_status, created_at) VALUES(?,?,?,?,?,?,?)",
            (
                boq_number,
                project_id,
                total_amount,
                len(lines),
                created_by,
                RECORD_PENDING_CHECKER,
                created_at,
            ),
        )
        new_boq_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        _insert_boq_lines(db, new_boq_id, project_id, lines, created_by, created_at)

        create_approval_request(
            db, "boq", new_boq_id, "boq_master", created_by, session.get("user_id")
        )
        db.commit()
        flash(
            f"BOQ {boq_number} saved — {len(lines)} item(s), total amount {total_amount:,.2f}."
        )
        return redirect(_dept_portal_return_url("projects"))

    edit_id = request.args.get("edit", type=int)
    editing_boq = None
    editing_lines = []
    if edit_id:
        editing_boq = query_db(
            "SELECT m.*, p.project_code, p.project_name FROM boq_master m "
            "LEFT JOIN projects p ON m.project_id = p.id "
            "WHERE m.id=? AND COALESCE(m.is_deleted, 0)=0",
            (edit_id,),
            one=True,
        )
        if not editing_boq:
            flash("BOQ record not found.")
            return redirect(url_for(endpoint))
        edit_role = get_edit_role_for_user(
            db, user_id, module_id, editing_boq["approval_status"], admin
        )
        if not edit_role:
            flash("This record is locked and cannot be edited.")
            return redirect(url_for(endpoint, view=edit_id))
        wf_ctx = {"edit_role": edit_role}
        editing_lines = query_db(
            "SELECT * FROM boq_items WHERE boq_id=? AND COALESCE(is_deleted, 0)=0 "
            "ORDER BY line_no, id",
            (edit_id,),
        )

    view_id = request.args.get("view", type=int) if not edit_id else None
    view_boq = None
    view_lines = []
    if view_id:
        view_boq = query_db(
            "SELECT m.*, p.project_code, p.project_name FROM boq_master m "
            "LEFT JOIN projects p ON m.project_id = p.id "
            "WHERE m.id=? AND COALESCE(m.is_deleted, 0)=0",
            (view_id,),
            one=True,
        )
        if view_boq:
            wf_ctx = _workflow_view_context(
                module_id, view_boq["id"], table, view_boq["approval_status"]
            )
            view_lines = query_db(
                "SELECT * FROM boq_items WHERE boq_id=? AND COALESCE(is_deleted, 0)=0 "
                "ORDER BY line_no, id",
                (view_id,),
            )

    show_continue_prompt = request.args.get("continue_prompt") == "1"
    saved_boq_number = request.args.get("saved", "").strip()
    prefill_project_id = request.args.get("project_id", type=int)
    continue_project_id = (
        prefill_project_id if show_continue_prompt else None
    )

    projects = get_project_options_for_boq()
    preview_project_id = (
        editing_boq["project_id"] if editing_boq
        else (continue_project_id if show_continue_prompt else prefill_project_id)
    )
    boq_form_project_id = (
        editing_boq["project_id"] if editing_boq
        else (continue_project_id or prefill_project_id)
    )
    next_boq_number = (
        editing_boq["boq_number"] if editing_boq
        else (peek_boq_number(db, preview_project_id) if preview_project_id else "Select project")
    )
    rows = query_db(
        "SELECT m.*, p.project_code, p.project_name FROM boq_master m "
        "LEFT JOIN projects p ON m.project_id = p.id "
        "WHERE COALESCE(m.is_deleted, 0)=0 ORDER BY m.id DESC"
    )

    return render_template(
        "boq.html",
        projects=projects,
        next_boq_number=next_boq_number,
        boq_units=BOQ_UNITS,
        max_boq_lines=MAX_BOQ_LINES,
        rows=[dict(r) for r in rows],
        view_boq=dict(view_boq) if view_boq else None,
        view_lines=[dict(line) for line in view_lines],
        editing_boq=dict(editing_boq) if editing_boq else None,
        editing_lines=[dict(line) for line in editing_lines],
        show_continue_prompt=show_continue_prompt and bool(saved_boq_number),
        saved_boq_number=saved_boq_number,
        continue_project_id=continue_project_id,
        boq_form_project_id=boq_form_project_id,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/boq-multiple-entry", methods=["GET", "POST"])
@login_required
def boq_multiple_entry():
    db = get_db()
    ensure_boq_master_table(db)
    module_id, table, endpoint = "boq", "boq_master", "boq_multiple_entry"
    user_id = session.get("user_id")
    admin = is_admin_user()
    wf_ctx = {}

    if request.method == "POST":
        project_id = request.form.get("project_id", "").strip()
        boq_id = request.form.get("boq_id", "").strip()
        lines, parse_error = _parse_boq_line_items(max_lines=MAX_BOQ_BULK_LINES)

        if not project_id:
            flash("Select a project.")
            return redirect(url_for(endpoint))
        if parse_error:
            flash(parse_error)
            return redirect(url_for(endpoint))
        if not lines:
            flash("Add at least one BOQ line item with a description.")
            return redirect(url_for(endpoint))
        if len(lines) > MAX_BOQ_BULK_LINES:
            flash(f"Maximum {MAX_BOQ_BULK_LINES} line items allowed per BOQ.")
            return redirect(url_for(endpoint))

        total_amount = round(sum(line["amount"] for line in lines), 2)
        created_by = session.get("username", "")
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if boq_id:
            existing_boq = query_db(
                "SELECT * FROM boq_master WHERE id=? AND COALESCE(is_deleted, 0)=0",
                (boq_id,),
                one=True,
            )
            if not existing_boq:
                flash("BOQ record not found.")
                return redirect(url_for(endpoint))
            edit_role = get_edit_role_for_user(
                db, user_id, module_id, existing_boq["approval_status"], admin
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=boq_id))
            db.execute(
                "UPDATE boq_master SET project_id=?, total_amount=?, line_count=?, "
                "modified_by=?, modified_at=? WHERE id=?",
                (project_id, total_amount, len(lines), created_by, created_at, boq_id),
            )
            db.execute("DELETE FROM boq_items WHERE boq_id=?", (boq_id,))
            _insert_boq_lines(db, int(boq_id), project_id, lines, created_by, created_at)
            _complete_module_save(db, module_id, table, int(boq_id), edit_role)
            return redirect(url_for(endpoint, view=boq_id))

        boq_number = generate_boq_number(db, int(project_id))
        db.execute(
            "INSERT INTO boq_master(boq_number, project_id, total_amount, line_count, "
            "created_by, approval_status, created_at) VALUES(?,?,?,?,?,?,?)",
            (
                boq_number,
                project_id,
                total_amount,
                len(lines),
                created_by,
                RECORD_PENDING_CHECKER,
                created_at,
            ),
        )
        new_boq_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        _insert_boq_lines(db, new_boq_id, project_id, lines, created_by, created_at)
        create_approval_request(
            db, "boq", new_boq_id, "boq_master", created_by, session.get("user_id")
        )
        db.commit()
        flash(
            f"BOQ {boq_number} saved — {len(lines)} item(s), total amount {total_amount:,.2f}."
        )
        return redirect(_dept_portal_return_url("projects"))

    edit_id = request.args.get("edit", type=int)
    editing_boq = None
    editing_lines = []
    if edit_id:
        editing_boq = query_db(
            "SELECT m.*, p.project_code, p.project_name FROM boq_master m "
            "LEFT JOIN projects p ON m.project_id = p.id "
            "WHERE m.id=? AND COALESCE(m.is_deleted, 0)=0",
            (edit_id,),
            one=True,
        )
        if not editing_boq:
            flash("BOQ record not found.")
            return redirect(url_for(endpoint))
        edit_role = get_edit_role_for_user(
            db, user_id, module_id, editing_boq["approval_status"], admin
        )
        if not edit_role:
            flash("This record is locked and cannot be edited.")
            return redirect(url_for(endpoint, view=edit_id))
        wf_ctx = {"edit_role": edit_role}
        editing_lines = query_db(
            "SELECT * FROM boq_items WHERE boq_id=? AND COALESCE(is_deleted, 0)=0 "
            "ORDER BY line_no, id",
            (edit_id,),
        )

    view_id = request.args.get("view", type=int) if not edit_id else None
    view_boq = None
    view_lines = []
    if view_id:
        view_boq = query_db(
            "SELECT m.*, p.project_code, p.project_name FROM boq_master m "
            "LEFT JOIN projects p ON m.project_id = p.id "
            "WHERE m.id=? AND COALESCE(m.is_deleted, 0)=0",
            (view_id,),
            one=True,
        )
        if view_boq:
            wf_ctx = _workflow_view_context(
                module_id, view_boq["id"], table, view_boq["approval_status"]
            )
            view_lines = query_db(
                "SELECT * FROM boq_items WHERE boq_id=? AND COALESCE(is_deleted, 0)=0 "
                "ORDER BY line_no, id",
                (view_id,),
            )

    boq_form_project_id = request.args.get("project_id", type=int)
    if editing_boq:
        boq_form_project_id = editing_boq["project_id"]
    projects = get_project_options_for_boq()
    preview_project_id = boq_form_project_id
    next_boq_number = (
        editing_boq["boq_number"] if editing_boq
        else (peek_boq_number(db, preview_project_id) if preview_project_id else "Select project")
    )
    recent_rows = query_db(
        "SELECT m.*, p.project_name FROM boq_master m "
        "LEFT JOIN projects p ON m.project_id = p.id "
        "WHERE COALESCE(m.is_deleted, 0)=0 ORDER BY m.id DESC LIMIT 15"
    )
    saved_boq_number = request.args.get("saved", "").strip()
    return render_template(
        "boq_multiple_entry.html",
        projects=projects,
        next_boq_number=next_boq_number,
        boq_units=BOQ_UNITS,
        max_boq_lines=MAX_BOQ_BULK_LINES,
        default_row_count=10,
        boq_form_project_id=boq_form_project_id,
        recent_rows=[dict(r) for r in recent_rows],
        saved_boq_number=saved_boq_number,
        saved_boq_id=request.args.get("saved_id", type=int),
        saved_line_count=request.args.get("saved_lines", type=int),
        saved_total=request.args.get("saved_total", type=float),
        continue_project_id=boq_form_project_id if saved_boq_number else None,
        view_boq=dict(view_boq) if view_boq else None,
        view_lines=[dict(line) for line in view_lines],
        editing_boq=dict(editing_boq) if editing_boq else None,
        editing_lines=[dict(line) for line in editing_lines],
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/api/projects/<int:project_id>/next-boq-number")
@login_required
def api_project_next_boq_number(project_id):
    db = get_db()
    ensure_boq_master_table(db)
    return jsonify({"next_boq_number": peek_boq_number(db, project_id)})


@app.route("/api/projects/next-code")
@login_required
def api_project_next_code():
    name = request.args.get("name", "").strip()
    db = get_db()
    return jsonify({"next_project_code": peek_project_code(db, name)})


@app.route("/boq-print/<int:boq_id>")
@login_required
def boq_print(boq_id):
    boq = query_db(
        "SELECT m.*, p.project_code, p.project_name FROM boq_master m "
        "LEFT JOIN projects p ON m.project_id = p.id "
        "WHERE m.id=? AND COALESCE(m.is_deleted, 0)=0",
        (boq_id,),
        one=True,
    )
    if not boq:
        flash("BOQ record not found.")
        return redirect(url_for("boq_management"))
    lines = query_db(
        "SELECT * FROM boq_items WHERE boq_id=? AND COALESCE(is_deleted, 0)=0 "
        "ORDER BY line_no, id",
        (boq_id,),
    )
    return render_template(
        "boq_print.html",
        boq=dict(boq),
        lines=[dict(line) for line in lines],
        autoprint=request.args.get("print") == "1",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/api/steel-shapes", methods=["GET", "POST"])
@login_required
def api_steel_shapes():
    db = get_db()
    ensure_dpr_measurement_tables(db)
    if request.method == "POST":
        shape_name = request.form.get("shape_name", "").strip()
        try:
            side_count = int(request.form.get("side_count") or 1)
        except ValueError:
            side_count = 1
        formula_type = request.form.get("formula_type", "perimeter").strip() or "perimeter"
        if not shape_name:
            return jsonify({"error": "Shape name is required."}), 400
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "INSERT INTO steel_shapes(shape_name, side_count, formula_type, created_by, created_at) "
            "VALUES(?,?,?,?,?)",
            (shape_name, max(1, side_count), formula_type, session.get("username", ""), now),
        )
        db.commit()
        row = query_db("SELECT * FROM steel_shapes ORDER BY id DESC LIMIT 1", one=True)
        return jsonify(dict(row))
    rows = query_db("SELECT * FROM steel_shapes ORDER BY shape_name, id")
    return jsonify([dict(r) for r in rows])


@app.route("/api/subcontractors/<int:subcontractor_id>/workers")
@login_required
def api_subcontractor_workers(subcontractor_id):
    rows = query_db(
        "SELECT id, worker_code, worker_name, designation FROM workers "
        "WHERE subcontractor_id=? AND (status IS NULL OR status = 'Active') "
        "ORDER BY worker_name",
        (subcontractor_id,),
    )
    return jsonify([dict(r) for r in rows])


@app.route("/api/subcontractors/<int:subcontractor_id>/attendance-trades")
@login_required
def api_subcontractor_attendance_trades(subcontractor_id):
    db = get_db()
    return jsonify(list_trades_for_subcontractor(db, subcontractor_id))


@app.route("/api/subcontractors/<int:subcontractor_id>/attendance-workers")
@login_required
def api_subcontractor_attendance_workers(subcontractor_id):
    db = get_db()
    trade_id = request.args.get("trade_id", type=int)
    trade_name = request.args.get("trade_name", "").strip() or None
    workers = list_subcontractor_workers_for_attendance(
        db,
        subcontractor_id,
        trade_id=trade_id,
        trade_name=trade_name,
    )
    return jsonify(workers)


@app.route("/api/dpr/workers")
@login_required
def api_dpr_workers():
    """Workers for DPR manpower — company staff or subcontractor workers."""
    sub_id = request.args.get("subcontractor_id", "").strip()
    if sub_id:
        rows = query_db(
            "SELECT id, worker_code, worker_name, designation, 'worker' AS worker_source "
            "FROM workers "
            "WHERE subcontractor_id=? AND (status IS NULL OR status = 'Active') "
            "ORDER BY worker_name, worker_code",
            (sub_id,),
        )
        return jsonify([dict(r) for r in rows])

    staff_rows = query_db(
        "SELECT s.id, s.employee_code AS worker_code, s.staff_name AS worker_name, "
        "COALESCE(s.designation, d.designation_name, '') AS designation, 'staff' AS worker_source "
        "FROM staff s "
        "LEFT JOIN designations d ON s.designation_id = d.id "
        "WHERE s.status IS NULL OR s.status = 'Active' "
        "ORDER BY s.staff_name, s.employee_code"
    )
    worker_rows = query_db(
        "SELECT id, worker_code, worker_name, designation, 'worker' AS worker_source "
        "FROM workers "
        "WHERE (status IS NULL OR status = 'Active') "
        "AND COALESCE(worker_category, 'Company Staff') != 'Sub Contractor Staff' "
        "ORDER BY worker_name, worker_code"
    )
    combined = [dict(r) for r in staff_rows] + [dict(r) for r in worker_rows]
    combined.sort(
        key=lambda item: (
            (item.get("worker_name") or "").lower(),
            (item.get("worker_code") or "").lower(),
        )
    )
    return jsonify(combined)


@app.route("/api/dpr/equipment")
@login_required
def api_dpr_equipment():
    db = get_db()
    prepare_dpr_page_db(db)
    rows = query_db(
        "SELECT id, reg_no, equipment_name, equipment_type, owner_type, "
        "hourly_rate, km_rate, trip_rate FROM equipment_master "
        "WHERE status IS NULL OR status = 'Active' "
        "ORDER BY equipment_type, equipment_name, reg_no"
    )
    return jsonify([dict(r) for r in rows])


@app.route("/api/dpr/activities")
@login_required
def api_dpr_activities():
    return jsonify(list(DEFAULT_DPR_ACTIVITIES))


@app.route("/api/dpr/boq-progress")
@login_required
def api_dpr_boq_progress():
    boq_item_id = request.args.get("boq_item_id", type=int)
    report_date = request.args.get("report_date", "").strip()
    today_qty = request.args.get("today_qty", type=float) or 0.0
    if not boq_item_id:
        return jsonify({"error": "boq_item_id required"}), 400

    boq_row = query_db(
        "SELECT bi.id, bi.quantity, bi.unit, bi.item_description, COALESCE(bm.boq_number, '') AS boq_number "
        "FROM boq_items bi LEFT JOIN boq_master bm ON bi.boq_id = bm.id WHERE bi.id=?",
        (boq_item_id,),
        one=True,
    )
    if not boq_row:
        return jsonify({"error": "BOQ item not found"}), 404

    boq_qty = float(boq_row["quantity"] or 0)
    executed_row = query_db(
        "SELECT COALESCE(SUM(calculated_quantity), 0) AS total "
        "FROM dpr_measurements WHERE boq_item_id=? AND COALESCE(dpr_status, 'submitted') != 'draft'",
        (boq_item_id,),
        one=True,
    )
    total_executed = float(executed_row["total"] or 0) if executed_row else 0.0
    today_row = None
    if report_date:
        today_row = query_db(
            "SELECT COALESCE(SUM(calculated_quantity), 0) AS total "
            "FROM dpr_measurements WHERE boq_item_id=? AND report_date=? "
            "AND COALESCE(dpr_status, 'submitted') != 'draft'",
            (boq_item_id, report_date),
            one=True,
        )
    today_saved = float(today_row["total"] or 0) if today_row else 0.0
    today_total = round(today_saved + today_qty, 4)
    balance = round(max(boq_qty - total_executed, 0), 4)
    completion = round((total_executed / boq_qty) * 100, 2) if boq_qty > 0 else 0.0
    projected_executed = round(total_executed + today_qty, 4)
    projected_balance = round(max(boq_qty - projected_executed, 0), 4)
    projected_completion = round((projected_executed / boq_qty) * 100, 2) if boq_qty > 0 else 0.0

    return jsonify({
        "boq_item_id": boq_item_id,
        "boq_number": boq_row["boq_number"],
        "boq_description": boq_row["item_description"],
        "unit": boq_row["unit"],
        "boq_quantity": round(boq_qty, 4),
        "today_quantity": today_total,
        "today_entered": round(today_qty, 4),
        "total_executed": round(total_executed, 4),
        "balance_quantity": balance,
        "completion_percent": completion,
        "projected_executed": projected_executed,
        "projected_balance": projected_balance,
        "projected_completion_percent": projected_completion,
    })


def _save_dpr_site_attachment_from_form():
    project_id = request.form.get("attach_project_id", "").strip()
    report_date = request.form.get("attach_report_date", "").strip()
    measurement_id = request.form.get("attach_measurement_id", "").strip()
    notes = request.form.get("attach_notes", "").strip()
    upload = request.files.get("site_dpr_file")

    if not project_id:
        flash("Select a project for the site DPR upload.")
        return None
    if not report_date:
        flash("Report date is required for site DPR upload.")
        return None

    ext, size, err = _validate_dpr_upload(upload)
    if err:
        flash(err)
        return None

    stored_name = save_file(upload, DPR_DOCS_DIR)
    if not stored_name:
        flash("Unable to save uploaded file.")
        return None

    db = get_db()
    prepare_dpr_page_db(db)
    measurement_id_val = None
    if measurement_id:
        try:
            measurement_id_val = int(measurement_id)
        except ValueError:
            measurement_id_val = None

    cur = db.execute(
        "INSERT INTO dpr_attachments("
        "project_id, report_date, measurement_id, original_filename, stored_filename, "
        "file_ext, file_size, notes, uploaded_by, uploaded_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            project_id,
            report_date,
            measurement_id_val,
            upload.filename,
            stored_name,
            ext,
            size,
            notes,
            session.get("username", ""),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    db.commit()
    flash("Site DPR document uploaded.")
    return {
        "project_id": int(project_id),
        "report_date": report_date,
        "attachment_id": cur.lastrowid,
    }


def _can_edit_dpr_measurement(db, user_id, row, is_admin=False):
    """Draft: creator or DPR maker; submitted: workflow roles or creator on maker-editable stages."""
    username = session.get("username", "")
    if is_admin:
        return "maker"

    dpr_status = (row.get("dpr_status") or "").lower()
    approval_status = row.get("approval_status") or "Draft"
    is_creator = (row.get("created_by") or "") == username
    is_module_maker = user_matches_stage(db, user_id, "dpr", "maker", is_admin)

    if dpr_status == "draft":
        if is_creator or is_module_maker:
            return "maker"
        return None

    role = get_edit_role_for_user(db, user_id, "dpr", approval_status, is_admin)
    if role:
        return role

    maker_editable_statuses = {
        RECORD_PENDING_CHECKER,
        RECORD_REJECTED_CHECKER,
        RECORD_REJECTED_APPROVER,
        "Draft",
    }
    if approval_status in maker_editable_statuses and (is_creator or is_module_maker):
        return "maker"
    return None


DPR_RECORD_SQL = (
    "SELECT m.*, p.project_code, p.project_name FROM dpr_measurements m "
    "LEFT JOIN projects p ON m.project_id = p.id WHERE m.id=?"
)


def _dpr_view_extras(db, measurement_id):
    mp_rows = query_db(
        "SELECT mp.*, s.subcontractor_name FROM dpr_manpower mp "
        "LEFT JOIN subcontractors s ON mp.subcontractor_id = s.id "
        "WHERE mp.measurement_id=? ORDER BY mp.id",
        (measurement_id,),
    )
    steel_rows = query_db(
        "SELECT * FROM dpr_steel_lines WHERE measurement_id=? ORDER BY id",
        (measurement_id,),
    )
    measurement_data = {}
    row = query_db(
        "SELECT measurement_data FROM dpr_measurements WHERE id=?",
        (measurement_id,),
        one=True,
    )
    if row and row["measurement_data"]:
        try:
            measurement_data = json.loads(row["measurement_data"])
        except json.JSONDecodeError:
            measurement_data = {}
    return {
        "manpower": [dict(r) for r in mp_rows],
        "steel_lines": [dict(r) for r in steel_rows],
        "measurement_data": measurement_data,
    }


def _persist_dpr_measurement_children(db, measurement_id, parsed, manpower_rows, for_costing=False):
    db.execute("DELETE FROM dpr_steel_lines WHERE measurement_id=?", (measurement_id,))
    db.execute("DELETE FROM dpr_manpower WHERE measurement_id=?", (measurement_id,))
    if parsed["type"] == "steel":
        for line in parsed["data"].get("lines") or []:
            db.execute(
                "INSERT INTO dpr_steel_lines(measurement_id, line_description, num_bars, cutting_length, "
                "diameter_mm, shape_id, side_measurements, quantity) VALUES(?,?,?,?,?,?,?,?)",
                (
                    measurement_id,
                    line.get("description", ""),
                    int(line.get("num_bars") or 0),
                    float(line.get("cutting_length_m") or 0),
                    float(line.get("diameter_mm") or 0),
                    line.get("shape_id") or None,
                    json.dumps(line.get("side_measurements") or []),
                    float(line.get("quantity") or 0),
                ),
            )
    if for_costing:
        for mp in manpower_rows:
            worker_id = mp.get("worker_id") or None
            worker_source = (mp.get("worker_source") or "worker").strip()
            if worker_id and worker_source == "staff":
                worker_id = None
            elif worker_id:
                try:
                    worker_id = int(worker_id)
                except (TypeError, ValueError):
                    worker_id = None
            db.execute(
                "INSERT INTO dpr_manpower(measurement_id, subcontractor_id, worker_id, worker_name, "
                "trade_name, hours_worked, remarks) VALUES(?,?,?,?,?,?,?)",
                (
                    measurement_id,
                    mp.get("subcontractor_id") or None,
                    worker_id,
                    mp.get("worker_name", ""),
                    mp.get("trade_name", ""),
                    float(mp.get("hours_worked") or 0),
                    mp.get("remarks", ""),
                ),
            )


def _save_dpr_measurement_from_form():
    project_id = request.form.get("project_id", "").strip()
    report_date = request.form.get("report_date", "").strip()
    boq_item_id = request.form.get("boq_item_id", "").strip()
    boq_number = request.form.get("boq_number", "").strip()
    boq_description = request.form.get("boq_description", "").strip()
    unit = request.form.get("unit", "").strip()
    work_description = request.form.get("work_description", "").strip()
    bill_client = 1 if _is_truthy(request.form.get("bill_client")) else 0
    for_costing = 1 if _is_truthy(request.form.get("for_costing")) else 0
    payload_raw = request.form.get("measurement_payload", "{}")
    manpower_raw = request.form.get("manpower_payload", "[]")
    materials_raw = request.form.get("materials_payload", "[]")
    equipment_raw = request.form.get("equipment_payload", "[]")
    activities_raw = request.form.get("activities_payload", "[]")
    additional_details = request.form.get("additional_details", "").strip()
    dpr_status = (request.form.get("dpr_status") or "submitted").strip().lower()
    if dpr_status not in ("draft", "submitted"):
        dpr_status = "submitted"

    if not project_id:
        flash("Select a project.")
        return None
    if not report_date:
        flash("Report date is required.")
        return None
    if not boq_item_id:
        flash("Select a BOQ line item.")
        return None

    try:
        payload = json.loads(payload_raw or "{}")
    except json.JSONDecodeError:
        flash("Invalid measurement data.")
        return None
    try:
        manpower_rows = json.loads(manpower_raw or "[]")
    except json.JSONDecodeError:
        manpower_rows = []
    try:
        materials_rows = json.loads(materials_raw or "[]")
    except json.JSONDecodeError:
        materials_rows = []
    try:
        equipment_rows = json.loads(equipment_raw or "[]")
    except json.JSONDecodeError:
        equipment_rows = []
    try:
        activities_rows = json.loads(activities_raw or "[]")
    except json.JSONDecodeError:
        activities_rows = []

    parsed = _parse_dpr_measurement_payload(payload, unit)
    if parsed["quantity"] <= 0 and dpr_status != "draft":
        flash("Enter valid measurements — calculated quantity is zero.")
        return None

    if not bill_client and not for_costing:
        for_costing = 1

    measurement_store = dict(parsed["data"])
    if materials_rows:
        measurement_store["materials"] = materials_rows
    if equipment_rows:
        measurement_store["equipment"] = equipment_rows
    if activities_rows:
        measurement_store["activities"] = activities_rows
    if additional_details:
        measurement_store["additional_details"] = additional_details

    db = get_db()
    prepare_dpr_page_db(db)
    created_by = session.get("username", "")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    billing_status = "pending" if bill_client and dpr_status == "submitted" else "none"
    costing_status = "pending" if for_costing and dpr_status == "submitted" else "none"
    approval_status = RECORD_PENDING_CHECKER if dpr_status == "submitted" else "Draft"

    measurement_id_raw = request.form.get("measurement_id", "").strip()
    if measurement_id_raw:
        try:
            measurement_id = int(measurement_id_raw)
        except (TypeError, ValueError):
            flash("Invalid DPR record.")
            return None
        existing = query_db(
            "SELECT * FROM dpr_measurements WHERE id=?", (measurement_id,), one=True
        )
        if not existing:
            flash("DPR record not found.")
            return None
        existing = dict(existing)
        edit_role = _can_edit_dpr_measurement(
            db, session.get("user_id"), existing, is_admin_user()
        )
        if not edit_role:
            flash("This record is locked and cannot be edited.")
            return None
        was_draft = (existing.get("dpr_status") or "").lower() == "draft"
        if dpr_status == "submitted" and was_draft:
            billing_status = "pending" if bill_client else "none"
            costing_status = "pending" if for_costing else "none"
        elif existing.get("billing_status") == "billed":
            billing_status = existing["billing_status"]
        elif not bill_client:
            billing_status = existing.get("billing_status") or "none"
        if existing.get("costing_status") == "linked":
            costing_status = existing["costing_status"]
        db.execute(
            "UPDATE dpr_measurements SET project_id=?, report_date=?, boq_item_id=?, boq_number=?, "
            "boq_description=?, unit=?, calculated_quantity=?, measurement_type=?, bill_client=?, "
            "for_costing=?, billing_status=?, costing_status=?, measurement_data=?, work_description=?, "
            "approval_status=?, dpr_status=?, modified_at=?, modified_by=? WHERE id=?",
            (
                project_id,
                report_date,
                boq_item_id,
                boq_number,
                boq_description,
                unit,
                parsed["quantity"],
                parsed["type"],
                bill_client,
                for_costing,
                billing_status,
                costing_status,
                json.dumps(measurement_store),
                work_description,
                approval_status if dpr_status == "submitted" else existing.get("approval_status") or "Draft",
                dpr_status,
                created_at,
                created_by,
                measurement_id,
            ),
        )
        _persist_dpr_measurement_children(db, measurement_id, parsed, manpower_rows, for_costing)
        if dpr_status == "submitted":
            if edit_role == "maker":
                if was_draft:
                    db.execute(
                        "UPDATE dpr_measurements SET approval_status=? WHERE id=?",
                        (RECORD_PENDING_CHECKER, measurement_id),
                    )
                    create_approval_request(
                        db, "dpr", measurement_id, "dpr_measurements",
                        created_by, session.get("user_id"),
                    )
                    db.commit()
                    flash("DPR submitted — Pending Checker.")
                else:
                    _complete_module_save(
                        db, "dpr", "dpr_measurements", measurement_id, edit_role
                    )
            else:
                db.commit()
                flash("Changes saved. Record remains at current workflow stage.")
        else:
            db.commit()
            flash("DPR draft saved.")
        return {
            "id": measurement_id,
            "quantity": parsed["quantity"],
            "project_id": project_id,
            "boq_number": boq_number,
            "boq_description": boq_description,
            "bill_client": bill_client,
            "dpr_status": dpr_status,
        }

    db.execute(
        "INSERT INTO dpr_measurements(project_id, report_date, boq_item_id, boq_number, "
        "boq_description, unit, calculated_quantity, measurement_type, bill_client, for_costing, "
        "billing_status, costing_status, measurement_data, work_description, created_by, approval_status, "
        "created_at, dpr_status, modified_at, modified_by) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            project_id,
            report_date,
            boq_item_id,
            boq_number,
            boq_description,
            unit,
            parsed["quantity"],
            parsed["type"],
            bill_client,
            for_costing,
            billing_status,
            costing_status,
            json.dumps(measurement_store),
            work_description,
            created_by,
            approval_status,
            created_at,
            dpr_status,
            created_at,
            created_by,
        ),
    )
    measurement_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    _persist_dpr_measurement_children(db, measurement_id, parsed, manpower_rows, for_costing)

    if dpr_status == "submitted":
        create_approval_request(
            db, "dpr", measurement_id, "dpr_measurements", created_by, session.get("user_id")
        )
    db.commit()
    return {
        "id": measurement_id,
        "quantity": parsed["quantity"],
        "project_id": project_id,
        "boq_number": boq_number,
        "boq_description": boq_description,
        "bill_client": bill_client,
        "dpr_status": dpr_status,
    }


@app.route("/dpr-entry", methods=["GET", "POST"])
@login_required
def dpr_entry():
    db = get_db()
    prepare_dpr_page_db(db)
    module_id, table, endpoint = "dpr", "dpr_measurements", "dpr_entry"
    user_id = session.get("user_id")
    admin = is_admin_user()
    wf_ctx = {}
    view_record = editing_measurement = None
    view_extras = {"manpower": [], "steel_lines": [], "measurement_data": {}}

    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    can_edit_dpr = False
    if view_id:
        view_record = query_db(DPR_RECORD_SQL, (view_id,), one=True)
        if not view_record:
            flash("DPR record not found.")
            return redirect(url_for(endpoint))
        view_record = dict(view_record)
        view_extras = _dpr_view_extras(db, view_id)
        can_edit_dpr = bool(
            _can_edit_dpr_measurement(db, user_id, view_record, admin)
        )
        wf_ctx = _workflow_view_context(
            module_id, view_record["id"], table, view_record.get("approval_status")
        )
    elif edit_id:
        editing_measurement = query_db(DPR_RECORD_SQL, (edit_id,), one=True)
        if not editing_measurement:
            flash("DPR record not found.")
            return redirect(url_for(endpoint))
        editing_measurement = dict(editing_measurement)
        edit_role = _can_edit_dpr_measurement(db, user_id, editing_measurement, admin)
        if not edit_role:
            flash("This record is locked and cannot be edited.")
            return redirect(url_for(endpoint, view=edit_id))
        wf_ctx = {"edit_role": edit_role}
        view_extras = _dpr_view_extras(db, edit_id)

    if request.method == "POST":
        form_action = request.form.get("form_action", "save_measurement").strip()
        if form_action == "upload_site_dpr":
            uploaded = _save_dpr_site_attachment_from_form()
            if uploaded:
                return redirect(
                    url_for(
                        "dpr_entry",
                        attach_project_id=uploaded["project_id"],
                        attach_report_date=uploaded["report_date"],
                    )
                    + "#dpr-site-upload"
                )
            return redirect(url_for("dpr_entry") + "#dpr-site-upload")

        saved = _save_dpr_measurement_from_form()
        if not saved:
            return redirect(url_for("dpr_entry") + "#dpr-form")

        flash(
            f"DPR {'draft saved' if saved.get('dpr_status') == 'draft' else 'measurement saved'} — "
            f"qty {saved['quantity']:,.4f} for {saved['boq_description']}."
            + (
                " Sent to Client Bill Pending."
                if saved.get("bill_client") and saved.get("dpr_status") != "draft"
                else " Recorded for costing / quantity."
                if saved.get("dpr_status") != "draft"
                else ""
            )
        )
        if saved.get("dpr_status") == "draft":
            edit_q = f"&edit={saved['id']}" if saved.get("id") else ""
            return redirect(url_for("dpr_entry") + edit_q + "#dpr-form")
        if saved.get("id") and request.form.get("measurement_id"):
            return redirect(url_for("dpr_entry", view=saved["id"]))
        return redirect(
            url_for(
                "dpr_entry",
                continue_prompt=1,
                project_id=saved["project_id"],
                boq_number=saved["boq_number"],
                saved_qty=saved["quantity"],
            )
            + "#dpr-form"
        )

    projects = get_project_options_for_boq()
    subcontractors = query_db(
        "SELECT id, subcontractor_name, subcontractor_code FROM subcontractors "
        "WHERE status IS NULL OR status = 'Active' ORDER BY subcontractor_name"
    )
    steel_shapes = query_db("SELECT * FROM steel_shapes ORDER BY shape_name, id")
    records_raw = query_db(
        "SELECT m.*, p.project_code, p.project_name FROM dpr_measurements m "
        "LEFT JOIN projects p ON m.project_id = p.id ORDER BY m.id DESC LIMIT 100"
    )
    records = []
    for r in records_raw:
        row = dict(r)
        row["can_edit"] = bool(
            _can_edit_dpr_measurement(db, user_id, row, admin)
        )
        records.append(row)
    attach_filter_project = request.args.get("attach_project_id", type=int)
    attach_filter_date = request.args.get("attach_report_date", "").strip()
    attach_sql = (
        "SELECT a.*, p.project_code, p.project_name, m.boq_number, m.boq_description "
        "FROM dpr_attachments a "
        "LEFT JOIN projects p ON a.project_id = p.id "
        "LEFT JOIN dpr_measurements m ON a.measurement_id = m.id "
        "WHERE 1=1"
    )
    attach_params = []
    if attach_filter_project:
        attach_sql += " AND a.project_id=?"
        attach_params.append(attach_filter_project)
    if attach_filter_date:
        attach_sql += " AND a.report_date=?"
        attach_params.append(attach_filter_date)
    attach_sql += " ORDER BY a.id DESC LIMIT 100"
    dpr_attachments = query_db(attach_sql, tuple(attach_params))

    show_continue_prompt = request.args.get("continue_prompt") == "1"
    continue_project_id = request.args.get("project_id", type=int) if show_continue_prompt else None
    continue_boq_number = request.args.get("boq_number", "").strip() if show_continue_prompt else ""
    saved_qty = request.args.get("saved_qty", "")

    return render_template(
        "dpr.html",
        projects=[dict(p) for p in projects],
        subcontractors=[dict(s) for s in subcontractors],
        steel_shapes=[dict(s) for s in steel_shapes],
        steel_diameters=STEEL_DIAMETERS_MM,
        records=[dict(r) for r in records],
        dpr_attachments=[dict(a) for a in dpr_attachments],
        dpr_activities=list(DEFAULT_DPR_ACTIVITIES),
        attach_filter_project=attach_filter_project,
        attach_filter_date=attach_filter_date,
        show_continue_prompt=show_continue_prompt,
        continue_project_id=continue_project_id,
        continue_boq_number=continue_boq_number,
        saved_qty=saved_qty,
        active_tab="entry",
        view_record=view_record,
        editing_measurement=editing_measurement,
        view_extras=view_extras,
        can_edit_dpr=can_edit_dpr,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
        module_id=module_id,
    )


def _dpr_attachment_mimetype(row):
    ext = (row["file_ext"] or os.path.splitext(row["stored_filename"] or "")[1] or "").lower()
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    return DPR_MIME_TYPES.get(ext, "application/octet-stream")


@app.route("/dpr-attachments/<int:attachment_id>")
@login_required
def dpr_attachment_file(attachment_id):
    db = get_db()
    prepare_dpr_page_db(db)
    row = query_db("SELECT * FROM dpr_attachments WHERE id=?", (attachment_id,), one=True)
    if not row:
        abort(404)
    path = os.path.join(DPR_DOCS_DIR, row["stored_filename"])
    if not os.path.isfile(path):
        abort(404)
    as_attachment = request.args.get("download") == "1"
    download_name = row["original_filename"] or row["stored_filename"]
    mimetype = _dpr_attachment_mimetype(row)
    if as_attachment:
        return send_file(
            path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=download_name,
            conditional=True,
        )
    response = make_response(
        send_file(path, mimetype=mimetype, as_attachment=False, conditional=True)
    )
    safe_name = secure_filename(download_name) or row["stored_filename"]
    response.headers["Content-Disposition"] = f'inline; filename="{safe_name}"'
    return response


@app.route("/dpr-client-bill-pending", methods=["GET", "POST"])
@login_required
def dpr_client_bill_pending():
    db = get_db()
    prepare_dpr_page_db(db)

    if request.method == "POST" and request.form.get("form_action") == "mark_billed":
        bill_id = request.form.get("measurement_id", type=int)
        if bill_id:
            db.execute(
                "UPDATE dpr_measurements SET billing_status='billed' WHERE id=?",
                (bill_id,),
            )
            db.commit()
            flash("Measurement marked as billed to client.")

    pending_bills = _fetch_client_bill_rows()
    projects = get_project_options_for_boq()
    subcontractors = query_db(
        "SELECT id, subcontractor_name FROM subcontractors "
        "WHERE status IS NULL OR status = 'Active' ORDER BY subcontractor_name"
    )
    steel_shapes = query_db("SELECT * FROM steel_shapes ORDER BY shape_name, id")

    return render_template(
        "dpr.html",
        projects=[dict(p) for p in projects],
        subcontractors=[dict(s) for s in subcontractors],
        steel_shapes=[dict(s) for s in steel_shapes],
        steel_diameters=STEEL_DIAMETERS_MM,
        records=[],
        pending_bills=[dict(r) for r in pending_bills],
        show_continue_prompt=False,
        continue_project_id=None,
        continue_boq_number="",
        saved_qty="",
        active_tab="client_bill",
    )


@app.route("/dpr-costing-pending", methods=["GET", "POST"])
@login_required
def dpr_costing_pending():
    db = get_db()
    prepare_dpr_page_db(db)

    if request.method == "POST" and request.form.get("form_action") == "mark_costed":
        rec_id = request.form.get("measurement_id", type=int)
        if rec_id:
            db.execute(
                "UPDATE dpr_measurements SET costing_status='completed' WHERE id=?",
                (rec_id,),
            )
            db.commit()
            flash("Measurement marked as costed.")
    elif request.method == "POST" and request.form.get("form_action") == "push_to_costing":
        rec_id = request.form.get("measurement_id", type=int)
        if rec_id:
            ok, message = _push_dpr_to_project_costing(db, rec_id)
            if ok:
                flash(f"{message} View in Project Costing.")
            else:
                flash(message)

    costing_pending = query_db(
        "SELECT m.*, p.project_code, p.project_name FROM dpr_measurements m "
        "LEFT JOIN projects p ON m.project_id = p.id "
        "WHERE m.for_costing=1 AND m.costing_status IN ('pending', 'linked') "
        "ORDER BY m.report_date DESC, m.id DESC"
    )
    costing_ids = [row["id"] for row in costing_pending]
    manpower_map = {}
    if costing_ids:
        placeholders = ",".join("?" * len(costing_ids))
        mp_rows = query_db(
            f"SELECT mp.*, s.subcontractor_name FROM dpr_manpower mp "
            f"LEFT JOIN subcontractors s ON mp.subcontractor_id = s.id "
            f"WHERE mp.measurement_id IN ({placeholders})",
            costing_ids,
        )
        for row in mp_rows:
            manpower_map.setdefault(row["measurement_id"], []).append(dict(row))

    resources_map = {}
    for row in costing_pending:
        try:
            data = json.loads(row["measurement_data"] or "{}")
        except (json.JSONDecodeError, TypeError):
            data = {}
        resources_map[row["id"]] = {
            "materials": data.get("materials") or [],
            "equipment": data.get("equipment") or [],
            "additional": data.get("additional_details") or "",
        }

    projects = get_project_options_for_boq()
    subcontractors = query_db(
        "SELECT id, subcontractor_name FROM subcontractors "
        "WHERE status IS NULL OR status = 'Active' ORDER BY subcontractor_name"
    )
    steel_shapes = query_db("SELECT * FROM steel_shapes ORDER BY shape_name, id")

    return render_template(
        "dpr.html",
        projects=[dict(p) for p in projects],
        subcontractors=[dict(s) for s in subcontractors],
        steel_shapes=[dict(s) for s in steel_shapes],
        steel_diameters=STEEL_DIAMETERS_MM,
        records=[],
        costing_pending=[dict(r) for r in costing_pending],
        manpower_map=manpower_map,
        resources_map=resources_map,
        show_continue_prompt=False,
        continue_project_id=None,
        continue_boq_number="",
        saved_qty="",
        active_tab="costing",
    )


@app.route("/dpr-client-bill-print")
@login_required
def dpr_client_bill_print():
    ids_param = request.args.get("ids", "").strip()
    measurement_ids = None
    if ids_param:
        measurement_ids = [int(x) for x in ids_param.split(",") if x.strip().isdigit()]
    pending_only = not measurement_ids
    rows = _fetch_client_bill_rows(measurement_ids=measurement_ids, pending_only=pending_only)
    if measurement_ids and not rows:
        rows = _fetch_client_bill_rows(measurement_ids=measurement_ids, pending_only=False)
    bills = [dict(r) for r in rows]
    total_amount = round(sum(float(b.get("bill_amount") or 0) for b in bills), 2)
    db = get_db()
    _prepare_corporate_template_db(db)
    first = bills[0] if bills else {}
    ctx = _build_corporate_report_context(
        db,
        "measurement_sheet",
        document_number=str(first.get("id") or ""),
        project_name=first.get("project_name") or "",
        project_id=str(first.get("project_id") or ""),
        prepared_by=session.get("username", ""),
        report_date=first.get("report_date"),
        back_url=url_for("dpr_client_bill_pending"),
        page_orientation="portrait",
    )
    return render_template(
        "dpr_client_bill_print.html",
        bills=bills,
        total_amount=total_amount,
        ctx=ctx,
        autoprint=request.args.get("print") == "1",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/dpr-client-bill-print/<int:measurement_id>")
@login_required
def dpr_client_bill_print_one(measurement_id):
    rows = _fetch_client_bill_rows(measurement_ids=[measurement_id], pending_only=False)
    bills = [dict(r) for r in rows]
    if not bills:
        flash("Client bill measurement not found.")
        return redirect(url_for("dpr_client_bill_pending"))
    total_amount = round(sum(float(b.get("bill_amount") or 0) for b in bills), 2)
    db = get_db()
    _prepare_corporate_template_db(db)
    first = bills[0]
    ctx = _build_corporate_report_context(
        db,
        "measurement_sheet",
        document_number=str(first.get("id") or measurement_id),
        project_name=first.get("project_name") or "",
        project_id=str(first.get("project_id") or ""),
        prepared_by=session.get("username", ""),
        report_date=first.get("report_date"),
        back_url=url_for("dpr_client_bill_pending"),
        page_orientation="portrait",
    )
    return render_template(
        "dpr_client_bill_print.html",
        bills=bills,
        total_amount=total_amount,
        ctx=ctx,
        autoprint=request.args.get("print") == "1",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/dpr-client-bill-export")
@login_required
def dpr_client_bill_export():
    rows = _fetch_client_bill_rows()
    if not rows:
        flash("No pending client bills to export.")
        return redirect(url_for("dpr_client_bill_pending"))
    records = []
    for row in rows:
        row = dict(row)
        client_name = row["company_name"] or row["client_name"] or row["private_client_name"] or ""
        records.append({
            "Date": row["report_date"],
            "Project Code": row["project_code"] or row["project_id"],
            "Project Name": row["project_name"],
            "Client": client_name,
            "BOQ No": row["boq_number"],
            "Description": row["boq_description"],
            "Work Description": row.get("work_description") or "",
            "Unit": row["unit"],
            "Quantity": row["calculated_quantity"],
            "Rate": row["boq_rate"],
            "Amount": row["bill_amount"],
            "GST No": row["gst_number"] or "",
        })
    df = pd.DataFrame(records)
    filename = f"client_bill_pending_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    file_path = os.path.join(REPORTS_DIR, filename)
    df.to_excel(file_path, index=False)
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


@app.route("/dpr-entry-legacy", methods=["GET", "POST"])
@login_required
def dpr_entry_legacy():
    fields = [
        {"name": "project_id", "label": "Project", "type": "select", "required": True, "options": _project_options()},
        {"name": "report_date", "label": "Report Date", "type": "date", "required": True},
        {"name": "prepared_by", "label": "Prepared By", "type": "text", "required": True},
        {"name": "work_done", "label": "Work Done", "type": "textarea", "required": True},
        {"name": "manpower_count", "label": "Manpower Count", "type": "number", "required": False},
        {"name": "material_used", "label": "Material Used", "type": "textarea", "required": False},
        {"name": "issues", "label": "Issues / Delay Reasons", "type": "textarea", "required": False},
        {"name": "progress_percent", "label": "Progress %", "type": "number", "required": False},
    ]
    return _render_standard_module(
        "dpr", "dpr_entries", "dpr_entry", "DPR Entry", fields,
        ["Date", "Project", "Prepared By", "Manpower", "Progress %"],
        ["report_date", "project_name", "prepared_by", "manpower_count", "progress_percent"],
        "SELECT d.*, p.project_name FROM dpr_entries d LEFT JOIN projects p ON d.project_id = p.id WHERE d.id=?",
        "SELECT d.*, p.project_name FROM dpr_entries d LEFT JOIN projects p ON d.project_id = p.id ORDER BY d.id DESC",
        "project_id, report_date, prepared_by, work_done, manpower_count, material_used, issues, progress_percent, created_by, approval_status",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("report_date", ""),
            request.form.get("prepared_by", ""),
            request.form.get("work_done", ""),
            int(float(request.form.get("manpower_count") or 0)),
            request.form.get("material_used", ""),
            request.form.get("issues", ""),
            float(request.form.get("progress_percent") or 0),
        ),
        "UPDATE dpr_entries SET project_id=?, report_date=?, prepared_by=?, work_done=?, manpower_count=?, material_used=?, issues=?, progress_percent=? WHERE id=?",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("report_date", ""),
            request.form.get("prepared_by", ""),
            request.form.get("work_done", ""),
            int(float(request.form.get("manpower_count") or 0)),
            request.form.get("material_used", ""),
            request.form.get("issues", ""),
            float(request.form.get("progress_percent") or 0),
        ),
    )


@app.route("/manager-tool", methods=["GET", "POST"])
@login_required
def manager_tool():
    fields = [
        {"name": "project_id", "label": "Project", "type": "select", "required": False, "options": _project_options()},
        {"name": "task_date", "label": "Task Date", "type": "date", "required": True},
        {"name": "manager_name", "label": "Manager Name", "type": "text", "required": True},
        {"name": "action_item", "label": "Action Item", "type": "textarea", "required": True},
        {"name": "priority", "label": "Priority", "type": "select", "required": True,
         "options": [{"value": "High", "label": "High"}, {"value": "Medium", "label": "Medium"}, {"value": "Low", "label": "Low"}]},
        {"name": "target_date", "label": "Target Date", "type": "date", "required": False},
        {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
    ]
    return _render_standard_module(
        "manager_tool", "manager_tasks", "manager_tool", "Manager Action Items", fields,
        ["Date", "Project", "Manager", "Priority", "Target"],
        ["task_date", "project_name", "manager_name", "priority", "target_date"],
        "SELECT m.*, p.project_name FROM manager_tasks m LEFT JOIN projects p ON m.project_id = p.id WHERE m.id=?",
        "SELECT m.*, p.project_name FROM manager_tasks m LEFT JOIN projects p ON m.project_id = p.id ORDER BY m.id DESC",
        "project_id, task_date, manager_name, action_item, priority, target_date, remarks, created_by, approval_status",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("task_date", ""),
            request.form.get("manager_name", ""),
            request.form.get("action_item", ""),
            request.form.get("priority", ""),
            request.form.get("target_date", ""),
            request.form.get("remarks", ""),
        ),
        "UPDATE manager_tasks SET project_id=?, task_date=?, manager_name=?, action_item=?, priority=?, target_date=?, remarks=? WHERE id=?",
        lambda: (
            request.form.get("project_id") or None,
            request.form.get("task_date", ""),
            request.form.get("manager_name", ""),
            request.form.get("action_item", ""),
            request.form.get("priority", ""),
            request.form.get("target_date", ""),
            request.form.get("remarks", ""),
        ),
    )


def _prepare_accounts_db(db):
    ensure_petty_cash_tables(db)
    ensure_accounts_schema(db)
    db.commit()


def _accounts_projects():
    return query_db("SELECT id, project_name FROM projects ORDER BY project_name")


def _accounts_date_range():
    from_date = request.args.get("from_date", "").strip() or None
    to_date = request.args.get("to_date", "").strip() or None
    if not from_date and not to_date:
        today = datetime.now()
        from_date = today.replace(day=1).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")
    return from_date, to_date


def _accounts_book_v2(page_title, rows, account_label="Account", show_exports=False):
    receipts = sum(_safe_float(r.get("debit")) for r in rows)
    payments = sum(_safe_float(r.get("credit")) for r in rows)
    return render_template(
        "accounts_book_v2.html",
        page_title=page_title,
        rows=rows,
        receipts=receipts,
        payments=payments,
        balance=round(receipts - payments, 2),
        from_date=request.args.get("from_date", ""),
        to_date=request.args.get("to_date", ""),
        account_label=account_label,
        show_exports=show_exports,
    )


def _safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


@app.route("/accounts")
@login_required
def accounts_hub():
    db = get_db()
    _prepare_accounts_db(db)
    stats = accounts_hub_stats(db)
    modules = [
        {"endpoint": "accounts_chart_of_accounts", "label": "Chart of Accounts", "icon": "fa-sitemap", "description": "Head of accounts master — assets, liabilities, income, expense."},
        {"endpoint": "accounts_expenses", "label": "Expense / Purchase", "icon": "fa-file-invoice", "description": "Multi-line GST expense and purchase entries."},
        {"endpoint": "accounts_payments", "label": "Payment Vouchers", "icon": "fa-money-bill-transfer", "description": "Vendor payments with TDS, allocations, attachments."},
        {"endpoint": "accounts_receipts", "label": "Receipt Vouchers", "icon": "fa-hand-holding-dollar", "description": "Client receipts with project and invoice reference."},
        {"endpoint": "accounts_gst_register", "label": "GST Register", "icon": "fa-percent", "description": "Purchase/sales register, GSTR summary, filing status."},
        {"endpoint": "accounts_tds_register", "label": "TDS Register", "icon": "fa-file-contract", "description": "TDS deducted, due dates, filing placeholders."},
        {"endpoint": "accounts_pf_register", "label": "PF Register", "icon": "fa-building", "description": "Provident fund contributions from payroll/staff."},
        {"endpoint": "accounts_esi_register", "label": "ESI Register", "icon": "fa-heart-pulse", "description": "ESI contributions and filing alerts."},
        {"endpoint": "accounts_vendor_ledger", "label": "Vendor Ledger", "icon": "fa-truck", "description": "Vendor-wise expense and payment running balance."},
        {"endpoint": "accounts_client_ledger", "label": "Client Ledger", "icon": "fa-users", "description": "Client receipt ledger with balance."},
        {"endpoint": "accounts_cash_book_v2", "label": "Cash Book", "icon": "fa-book", "description": "CoA-based cash and petty cash movements."},
        {"endpoint": "accounts_bank_book_v2", "label": "Bank Book", "icon": "fa-building-columns", "description": "CoA-based bank account movements."},
        {"endpoint": "accounts_day_book", "label": "Day Book", "icon": "fa-calendar-day", "description": "Chronological journal entries across all accounts."},
        {"endpoint": "accounts_general_ledger", "label": "General Ledger", "icon": "fa-book-open", "description": "Full double-entry ledger by account head."},
        {"endpoint": "accounts_reports", "label": "Financial Reports", "icon": "fa-chart-line", "description": "Trial balance, P&L, balance sheet, cash flow, project cost."},
        {"endpoint": "accounts_tally_export", "label": "Tally Export", "icon": "fa-file-export", "description": "Export journal vouchers as Tally XML."},
        {"endpoint": "petty_cash", "label": "Petty Cash", "icon": "fa-wallet", "description": "Petty cash requests, transfers, settlement, expense draft."},
        {"endpoint": "cash_book", "label": "Cash Book (Legacy)", "icon": "fa-book", "description": "Legacy approved cash transactions."},
        {"endpoint": "bank_book", "label": "Bank Book (Legacy)", "icon": "fa-building-columns", "description": "Legacy approved bank transactions."},
        {"endpoint": "ledger", "label": "Ledger (Legacy)", "icon": "fa-book-open", "description": "Legacy combined transactions."},
    ]
    return render_template("accounts_hub.html", stats=stats, modules=modules)


@app.route("/accounts/chart-of-accounts", methods=["GET", "POST"])
@login_required
def accounts_chart_of_accounts():
    db = get_db()
    _prepare_accounts_db(db)
    if request.method == "POST" and request.form.get("form_action") == "save_head":
        account_id = request.form.get("account_id", "").strip()
        try:
            save_chart_account(db, request.form, int(account_id) if account_id else None)
            db.commit()
            flash("Chart head saved.")
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save — code may already exist.")
        return redirect(url_for("accounts_chart_of_accounts"))
    grouped = chart_accounts_grouped(db)
    return render_template(
        "accounts_chart_of_accounts.html",
        grouped=grouped,
        account_types=ACCOUNT_TYPES,
    )


@app.route("/accounts/expenses", methods=["GET", "POST"])
@login_required
def accounts_expenses():
    db = get_db()
    _prepare_accounts_db(db)
    module_id, table, endpoint = "account_expense", "account_expenses", "accounts_expenses"
    if request.method == "POST":
        inline = _handle_add_chart_head_form(db, endpoint, "#expense-form", {"new": 1})
        if inline:
            return inline
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        try:
            if record_id:
                save_account_expense(db, request.form, session.get("username", ""), record_id)
                upload = request.files.get("attachment")
                if upload and upload.filename:
                    stored = save_file(upload, ACCOUNTS_DOCS_DIR)
                    if stored:
                        save_account_attachment(db, "expense", record_id, stored, session.get("username", ""))
                        db.execute(
                            "UPDATE account_expenses SET attachment_filename=? WHERE id=?",
                            (stored, record_id),
                        )
                _complete_module_save(db, module_id, table, record_id, edit_role)
            else:
                new_id = save_account_expense(db, request.form, session.get("username", ""))
                upload = request.files.get("attachment")
                if upload and upload.filename:
                    stored = save_file(upload, ACCOUNTS_DOCS_DIR)
                    if stored:
                        save_account_attachment(db, "expense", new_id, stored, session.get("username", ""))
                        db.execute(
                            "UPDATE account_expenses SET attachment_filename=? WHERE id=?",
                            (stored, new_id),
                        )
                create_approval_request(
                    db, module_id, new_id, table,
                    session.get("username", ""), session.get("user_id"),
                )
                db.commit()
                flash("Expense saved. Status: Pending Checker.")
            return redirect(url_for(endpoint))
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.referrer or url_for(endpoint, new=1))
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = load_account_expense(db, int(view_id))
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = load_account_expense(db, int(edit_id))
        if edit_record:
            edit_role = get_edit_role_for_user(
                db, session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}
    show_form = bool(request.args.get("new")) or edit_record
    rows = list_account_expenses(db)
    chart_heads = list_chart_of_accounts(db)
    return render_template(
        "accounts_expenses.html",
        rows=rows,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        chart_heads=chart_heads,
        chart_heads_json=chart_accounts_for_js(db),
        projects=_accounts_projects(),
        petty_cash_options=list_settled_petty_cash(db),
        payment_sources=PAYMENT_SOURCES,
        payment_statuses=PAYMENT_STATUSES,
        gst_rates=GST_RATES,
        tds_sections=TDS_SECTIONS,
        default_date=datetime.now().strftime("%Y-%m-%d"),
        prefill_head=request.args.get("head_id", type=int),
        select_chart_head=request.args.get("select_chart_head", type=int),
        account_types=ACCOUNT_TYPES,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/accounts/payments", methods=["GET", "POST"])
@login_required
def accounts_payments():
    db = get_db()
    _prepare_accounts_db(db)
    module_id, table, endpoint = "payment_voucher", "payment_vouchers", "accounts_payments"
    if request.method == "POST":
        inline = _handle_add_chart_head_form(db, endpoint, "#voucher-form", {"new": 1})
        if inline:
            return inline
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        try:
            upload = request.files.get("attachment")
            if record_id:
                vid = save_payment_voucher(db, request.form, session.get("username", ""), record_id)
                if upload and upload.filename:
                    stored = save_file(upload, ACCOUNTS_DOCS_DIR)
                    if stored:
                        db.execute(
                            "UPDATE payment_vouchers SET attachment_filename=? WHERE id=?",
                            (stored, vid),
                        )
                _complete_module_save(db, module_id, table, record_id, edit_role)
            else:
                new_id = save_payment_voucher(db, request.form, session.get("username", ""))
                upload = request.files.get("attachment")
                if upload and upload.filename:
                    stored = save_file(upload, ACCOUNTS_DOCS_DIR)
                    if stored:
                        db.execute(
                            "UPDATE payment_vouchers SET attachment_filename=? WHERE id=?",
                            (stored, new_id),
                        )
                create_approval_request(
                    db, module_id, new_id, table,
                    session.get("username", ""), session.get("user_id"),
                )
                db.commit()
                flash("Payment voucher saved. Status: Pending Checker.")
            return redirect(url_for(endpoint))
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.referrer or url_for(endpoint, new=1))
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = load_payment_voucher(db, int(view_id))
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = load_payment_voucher(db, int(edit_id))
        if edit_record:
            edit_role = get_edit_role_for_user(
                db, session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}
    expense_heads = list_expense_chart_heads(db)
    return render_template(
        "accounts_payment_voucher.html",
        rows=list_payment_vouchers(db),
        view_record=view_record,
        edit_record=edit_record,
        show_form=bool(request.args.get("new")) or edit_record,
        projects=_accounts_projects(),
        expense_heads=expense_heads,
        chart_heads=expense_heads,
        chart_heads_json=chart_accounts_for_js(db),
        payment_statuses=PAYMENT_STATUSES,
        tds_sections=TDS_SECTIONS,
        unpaid_expenses=list_unpaid_expenses_for_vendor(
            db, (edit_record or {}).get("vendor_name") or request.args.get("vendor", "")
        ) if (edit_record or request.args.get("vendor")) else [],
        default_date=datetime.now().strftime("%Y-%m-%d"),
        select_chart_head=request.args.get("select_chart_head", type=int),
        account_types=ACCOUNT_TYPES,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/accounts/receipts", methods=["GET", "POST"])
@login_required
def accounts_receipts():
    db = get_db()
    _prepare_accounts_db(db)
    module_id, table, endpoint = "receipt_voucher", "receipt_vouchers", "accounts_receipts"
    if request.method == "POST":
        inline = _handle_add_chart_head_form(db, endpoint, "#receipt-form", {"new": 1})
        if inline:
            return inline
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        try:
            upload = request.files.get("attachment")
            if record_id:
                rid = save_receipt_voucher(db, request.form, session.get("username", ""), record_id)
                if upload and upload.filename:
                    stored = save_file(upload, ACCOUNTS_DOCS_DIR)
                    if stored:
                        save_account_attachment(db, "receipt", rid, stored, session.get("username", ""))
                        db.execute(
                            "UPDATE receipt_vouchers SET attachment_filename=? WHERE id=?",
                            (stored, rid),
                        )
                _complete_module_save(db, module_id, table, record_id, edit_role)
            else:
                new_id = save_receipt_voucher(db, request.form, session.get("username", ""))
                if upload and upload.filename:
                    stored = save_file(upload, ACCOUNTS_DOCS_DIR)
                    if stored:
                        save_account_attachment(db, "receipt", new_id, stored, session.get("username", ""))
                        db.execute(
                            "UPDATE receipt_vouchers SET attachment_filename=? WHERE id=?",
                            (stored, new_id),
                        )
                create_approval_request(
                    db, module_id, new_id, table,
                    session.get("username", ""), session.get("user_id"),
                )
                db.commit()
                flash("Receipt voucher saved. Status: Pending Checker.")
            return redirect(url_for(endpoint))
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.referrer or url_for(endpoint, new=1))
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = load_receipt_voucher(db, int(view_id))
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = load_receipt_voucher(db, int(edit_id))
        if edit_record:
            edit_role = get_edit_role_for_user(
                db, session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}
    income_heads = list_income_chart_heads(db)
    view_attachments = []
    if view_record:
        view_attachments = list_account_attachments(db, "receipt", view_record["id"])
    return render_template(
        "accounts_receipt_voucher.html",
        rows=list_receipt_vouchers(db),
        view_record=view_record,
        edit_record=edit_record,
        view_attachments=view_attachments,
        show_form=bool(request.args.get("new")) or edit_record,
        projects=_accounts_projects(),
        income_heads=income_heads,
        chart_heads=income_heads,
        chart_heads_json=chart_accounts_for_js(db),
        gst_rates=GST_RATES,
        tax_types=TAX_TYPES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
        select_chart_head=request.args.get("select_chart_head", type=int),
        account_types=ACCOUNT_TYPES,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/accounts/gst-register", methods=["GET", "POST"])
@login_required
def accounts_gst_register():
    db = get_db()
    _prepare_accounts_db(db)
    if request.method == "POST" and request.form.get("form_action") == "update_filing":
        period_id = request.form.get("period_id", type=int)
        if period_id:
            update_gst_filing_status(
                db,
                period_id,
                request.form.get("filing_status", "Pending"),
                request.form.get("filed_date") or None,
            )
            db.commit()
            flash("GST filing status updated.")
        return redirect(url_for("accounts_gst_register"))
    from_date, to_date = _accounts_date_range()
    gstr = get_gstr_summary(db, from_date, to_date)
    export = request.args.get("export")
    if export == "excel":
        rows = get_gst_purchase_register(db)
        buf = export_report_excel(rows, "GST Purchase")
        return send_file(buf, as_attachment=True, download_name="gst_purchase.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if export == "sales_excel":
        rows = get_gst_sales_register(db)
        buf = export_report_excel(rows, "GST Sales")
        return send_file(buf, as_attachment=True, download_name="gst_sales.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if export == "gstr_summary":
        gstr_rows = [{
            "purchase_taxable": gstr.get("purchase_taxable", 0),
            "purchase_cgst": gstr.get("purchase_cgst", 0),
            "purchase_sgst": gstr.get("purchase_sgst", 0),
            "purchase_igst": gstr.get("purchase_igst", 0),
            "sales_taxable": gstr.get("sales_taxable", 0),
            "sales_cgst": gstr.get("sales_cgst", 0),
            "sales_sgst": gstr.get("sales_sgst", 0),
            "sales_igst": gstr.get("sales_igst", 0),
            "net_cgst": gstr.get("net_cgst", 0),
            "net_sgst": gstr.get("net_sgst", 0),
            "net_igst": gstr.get("net_igst", 0),
            "from_date": from_date or "",
            "to_date": to_date or "",
        }]
        buf = export_report_excel(gstr_rows, "GSTR Summary")
        return send_file(buf, as_attachment=True, download_name="gstr_summary.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if export == "csv":
        import csv
        from io import StringIO
        si = StringIO()
        writer = csv.writer(si)
        rows = get_gst_purchase_register(db)
        if rows:
            writer.writerow(list(rows[0].keys()))
            for r in rows:
                writer.writerow([r.get(k) for k in rows[0].keys()])
        resp = make_response(si.getvalue())
        resp.headers["Content-Type"] = "text/csv"
        resp.headers["Content-Disposition"] = "attachment; filename=gst_purchase.csv"
        return resp
    if export == "sales_csv":
        import csv
        from io import StringIO
        si = StringIO()
        writer = csv.writer(si)
        rows = get_gst_sales_register(db)
        if rows:
            writer.writerow(list(rows[0].keys()))
            for r in rows:
                writer.writerow([r.get(k) for k in rows[0].keys()])
        resp = make_response(si.getvalue())
        resp.headers["Content-Type"] = "text/csv"
        resp.headers["Content-Disposition"] = "attachment; filename=gst_sales.csv"
        return resp
    return render_template(
        "accounts_gst_register.html",
        purchase_rows=get_gst_purchase_register(db),
        sales_rows=get_gst_sales_register(db),
        filing_periods=list_gst_filing_periods(db),
        gstr=gstr,
        from_date=from_date,
        to_date=to_date,
        filing_statuses=FILING_STATUSES,
    )


@app.route("/api/accounts/petty-cash-settled")
@login_required
def api_accounts_petty_cash_settled():
    db = get_db()
    _prepare_accounts_db(db)
    items = []
    for row in list_settled_petty_cash(db):
        items.append({
            "id": row["id"],
            "label": f"{row.get('request_number') or row['id']} — {row.get('staff_name') or '—'} "
                     f"(₹{float(row.get('transferred_amount') or 0):.2f})",
            "transferred_amount": float(row.get("transferred_amount") or 0),
            "project_id": row.get("project_id"),
        })
    return jsonify({"items": items})


@app.route("/accounts/gst")
@login_required
def account_gst():
    return redirect(url_for("accounts_gst_register"))


def _account_transaction_page(transaction_type, module_id, endpoint, title):
    ensure_account_transactions_table(get_db())
    fields = [
        {"name": "project_id", "label": "Project", "type": "select", "required": False, "options": _project_options()},
        {"name": "transaction_date", "label": "Date", "type": "date", "required": True},
        {"name": "party_name", "label": "Party Name", "type": "text", "required": True},
        {"name": "account_head", "label": "Account Head", "type": "text", "required": True},
        {"name": "amount", "label": "Amount", "type": "number", "required": True},
        {"name": "payment_mode", "label": "Payment Mode", "type": "select", "required": True,
         "options": [{"value": "Cash", "label": "Cash"}, {"value": "Bank", "label": "Bank"}, {"value": "UPI", "label": "UPI"}, {"value": "Cheque", "label": "Cheque"}]},
        {"name": "reference_no", "label": "Reference No", "type": "text", "required": False},
        {"name": "tax_percent", "label": "Tax %", "type": "number", "required": False},
        {"name": "remarks", "label": "Remarks", "type": "textarea", "required": False},
    ]
    return _render_standard_module(
        module_id, "account_transactions", endpoint, title, fields,
        ["Date", "Project", "Party", "Head", "Amount"],
        ["transaction_date", "project_name", "party_name", "account_head", "amount"],
        "SELECT a.*, p.project_name FROM account_transactions a LEFT JOIN projects p ON a.project_id = p.id WHERE a.id=?",
        "SELECT a.*, p.project_name FROM account_transactions a LEFT JOIN projects p ON a.project_id = p.id "
        f"WHERE a.transaction_type='{transaction_type}' ORDER BY a.id DESC",
        "transaction_type, project_id, transaction_date, party_name, account_head, amount, payment_mode, reference_no, tax_percent, remarks, created_by, approval_status",
        lambda: (
            transaction_type,
            request.form.get("project_id") or None,
            request.form.get("transaction_date", ""),
            request.form.get("party_name", ""),
            request.form.get("account_head", ""),
            float(request.form.get("amount") or 0),
            request.form.get("payment_mode", ""),
            request.form.get("reference_no", ""),
            float(request.form.get("tax_percent") or 0),
            request.form.get("remarks", ""),
        ),
        "UPDATE account_transactions SET transaction_type=?, project_id=?, transaction_date=?, party_name=?, account_head=?, amount=?, payment_mode=?, reference_no=?, tax_percent=?, remarks=? WHERE id=?",
        lambda: (
            transaction_type,
            request.form.get("project_id") or None,
            request.form.get("transaction_date", ""),
            request.form.get("party_name", ""),
            request.form.get("account_head", ""),
            float(request.form.get("amount") or 0),
            request.form.get("payment_mode", ""),
            request.form.get("reference_no", ""),
            float(request.form.get("tax_percent") or 0),
            request.form.get("remarks", ""),
        ),
    )


@app.route("/accounts/receipts/legacy", methods=["GET", "POST"])
@login_required
def account_receipts_legacy():
    return _account_transaction_page("Receipt", "account_receipt", "account_receipts_legacy", "Accounts Receipts (Legacy)")


@app.route("/accounts/payments/legacy", methods=["GET", "POST"])
@login_required
def account_payments_legacy():
    return _account_transaction_page("Payment", "account_payment", "account_payments_legacy", "Accounts Payments (Legacy)")


@app.route("/accounts/tds", methods=["GET", "POST"])
@login_required
def account_tds():
    return redirect(url_for("accounts_tds_register"))


def _accounts_book(title, payment_mode=None):
    ensure_account_transactions_table(get_db())
    params = []
    where = "WHERE a.approval_status='Approved'"
    if payment_mode:
        where += " AND a.payment_mode=?"
        params.append(payment_mode)
    rows = query_db(
        "SELECT a.*, p.project_name FROM account_transactions a "
        "LEFT JOIN projects p ON a.project_id = p.id "
        f"{where} ORDER BY a.transaction_date DESC, a.id DESC",
        tuple(params),
    )
    receipts = sum(float(row["amount"] or 0) for row in rows if row["transaction_type"] == "Receipt")
    payments = sum(float(row["amount"] or 0) for row in rows if row["transaction_type"] != "Receipt")
    return render_template(
        "accounts_book.html",
        page_title=title,
        rows=rows,
        receipts=receipts,
        payments=payments,
        balance=receipts - payments,
    )


@app.route("/accounts/cash-book")
@login_required
def cash_book():
    return _accounts_book("Cash Book", "Cash")


@app.route("/accounts/bank-book")
@login_required
def bank_book():
    return _accounts_book("Bank Book", "Bank")


@app.route("/accounts/ledger")
@login_required
def ledger():
    return _accounts_book("Ledger")


@app.route("/accounts/cash-book-v2")
@login_required
def accounts_cash_book_v2():
    db = get_db()
    _prepare_accounts_db(db)
    from_date, to_date = _accounts_date_range()
    return _accounts_book_v2("Cash Book (CoA)", get_cash_book_v2(db, from_date, to_date), "Cash / Petty")


@app.route("/accounts/bank-book-v2")
@login_required
def accounts_bank_book_v2():
    db = get_db()
    _prepare_accounts_db(db)
    from_date, to_date = _accounts_date_range()
    return _accounts_book_v2("Bank Book (CoA)", get_bank_book_v2(db, from_date, to_date), "Bank")


@app.route("/accounts/day-book")
@login_required
def accounts_day_book():
    db = get_db()
    _prepare_accounts_db(db)
    from_date, to_date = _accounts_date_range()
    rows = get_day_book(db, from_date, to_date)
    export = request.args.get("export")
    if export == "excel":
        buf = export_report_excel(rows, "Day Book")
        return send_file(
            buf,
            as_attachment=True,
            download_name="day_book.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    if export == "csv":
        resp = make_response(export_report_csv(rows))
        resp.headers["Content-Type"] = "text/csv"
        resp.headers["Content-Disposition"] = "attachment; filename=day_book.csv"
        return resp
    return _accounts_book_v2("Day Book", rows, "All Accounts", show_exports=True)


@app.route("/accounts/general-ledger")
@login_required
def accounts_general_ledger():
    db = get_db()
    _prepare_accounts_db(db)
    from_date, to_date = _accounts_date_range()
    account_id = request.args.get("account_id", type=int)
    rows = get_general_ledger(db, account_id, from_date, to_date)
    return render_template(
        "accounts_book_v2.html",
        page_title="General Ledger",
        rows=rows,
        receipts=sum(_safe_float(r.get("debit")) for r in rows),
        payments=sum(_safe_float(r.get("credit")) for r in rows),
        balance=round(sum(_safe_float(r.get("debit")) - _safe_float(r.get("credit")) for r in rows), 2),
        from_date=from_date or "",
        to_date=to_date or "",
        account_label="All Accounts",
        chart_heads=list_chart_of_accounts(db),
        selected_account_id=account_id,
    )


@app.route("/accounts/vendor-ledger")
@login_required
def accounts_vendor_ledger():
    db = get_db()
    _prepare_accounts_db(db)
    from_date, to_date = _accounts_date_range()
    vendor = request.args.get("vendor", "").strip()
    rows = get_vendor_ledger(db, vendor, from_date, to_date) if vendor else []
    vendors = db.execute(
        "SELECT DISTINCT vendor_name FROM account_expenses WHERE vendor_name IS NOT NULL AND TRIM(vendor_name)!='' "
        "UNION SELECT DISTINCT vendor_name FROM payment_vouchers WHERE vendor_name IS NOT NULL AND TRIM(vendor_name)!='' "
        "ORDER BY vendor_name"
    ).fetchall()
    return render_template(
        "accounts_party_ledger.html",
        page_title="Vendor Ledger",
        party_label="Vendor",
        party_name=vendor,
        parties=[r["vendor_name"] for r in vendors],
        rows=rows,
        from_date=from_date or "",
        to_date=to_date or "",
    )


@app.route("/accounts/client-ledger")
@login_required
def accounts_client_ledger():
    db = get_db()
    _prepare_accounts_db(db)
    from_date, to_date = _accounts_date_range()
    client = request.args.get("client", "").strip()
    rows = get_client_ledger(db, client, from_date, to_date) if client else []
    clients = db.execute(
        "SELECT DISTINCT client_name FROM receipt_vouchers WHERE client_name IS NOT NULL AND TRIM(client_name)!='' "
        "ORDER BY client_name"
    ).fetchall()
    return render_template(
        "accounts_party_ledger.html",
        page_title="Client Ledger",
        party_label="Client",
        party_name=client,
        parties=[r["client_name"] for r in clients],
        rows=rows,
        from_date=from_date or "",
        to_date=to_date or "",
    )


@app.route("/accounts/tds-register", methods=["GET", "POST"])
@login_required
def accounts_tds_register():
    db = get_db()
    _prepare_accounts_db(db)
    if request.method == "POST" and request.form.get("form_action") == "update_filing":
        tds_id = request.form.get("tds_id", type=int)
        if tds_id:
            db.execute(
                "UPDATE tds_register SET filing_status=?, filed_date=?, remarks=? WHERE id=?",
                (
                    request.form.get("filing_status", "Pending"),
                    request.form.get("filed_date") or None,
                    request.form.get("remarks", "").strip(),
                    tds_id,
                ),
            )
            db.commit()
            flash("TDS filing status updated.")
        return redirect(url_for("accounts_tds_register"))
    return render_template(
        "accounts_tds_register.html",
        rows=list_tds_register(db),
        filing_statuses=FILING_STATUSES,
    )


@app.route("/accounts/pf-register", methods=["GET", "POST"])
@login_required
def accounts_pf_register():
    db = get_db()
    _prepare_accounts_db(db)
    if request.method == "POST":
        if request.form.get("form_action") == "generate":
            month = request.form.get("period_month", type=int) or datetime.now().month
            year = request.form.get("period_year", type=int) or datetime.now().year
            count = build_pf_esi_from_payroll(db, month, year)
            db.commit()
            flash(f"Generated {count} PF/ESI register rows for {month}/{year}.")
            return redirect(url_for("accounts_pf_register"))
        if request.form.get("form_action") == "update_filing":
            reg_id = request.form.get("register_id", type=int)
            if reg_id:
                update_pf_esi_filing_status(
                    db,
                    reg_id,
                    request.form.get("filing_status", "Pending"),
                    request.form.get("filed_date") or None,
                    request.form.get("remarks", ""),
                )
                db.commit()
                flash("PF filing status updated.")
            return redirect(url_for("accounts_pf_register"))
    return render_template(
        "accounts_pf_esi_register.html",
        page_title="PF Register",
        register_type="PF",
        rows=[r for r in list_pf_esi_register(db, "PF")],
        filing_statuses=FILING_STATUSES,
    )


@app.route("/accounts/esi-register", methods=["GET", "POST"])
@login_required
def accounts_esi_register():
    db = get_db()
    _prepare_accounts_db(db)
    if request.method == "POST":
        if request.form.get("form_action") == "generate":
            month = request.form.get("period_month", type=int) or datetime.now().month
            year = request.form.get("period_year", type=int) or datetime.now().year
            count = build_pf_esi_from_payroll(db, month, year)
            db.commit()
            flash(f"Generated {count} PF/ESI register rows for {month}/{year}.")
            return redirect(url_for("accounts_esi_register"))
        if request.form.get("form_action") == "update_filing":
            reg_id = request.form.get("register_id", type=int)
            if reg_id:
                update_pf_esi_filing_status(
                    db,
                    reg_id,
                    request.form.get("filing_status", "Pending"),
                    request.form.get("filed_date") or None,
                    request.form.get("remarks", ""),
                )
                db.commit()
                flash("ESI filing status updated.")
            return redirect(url_for("accounts_esi_register"))
    return render_template(
        "accounts_pf_esi_register.html",
        page_title="ESI Register",
        register_type="ESI",
        rows=[r for r in list_pf_esi_register(db, "ESI")],
        filing_statuses=FILING_STATUSES,
    )


@app.route("/accounts/reports")
@login_required
def accounts_reports():
    db = get_db()
    _prepare_accounts_db(db)
    from_date, to_date = _accounts_date_range()
    report = request.args.get("report", "trial_balance")
    export = request.args.get("export")
    data: dict = {}
    rows: list = []
    if report == "trial_balance":
        rows = get_trial_balance(db, from_date, to_date)
        data = {"rows": rows}
    elif report == "profit_loss":
        data = get_profit_and_loss(db, from_date, to_date)
    elif report == "balance_sheet":
        data = get_balance_sheet(db, to_date)
    elif report == "cash_flow":
        data = get_cash_flow_summary(db, from_date, to_date)
    elif report == "project_profitability":
        project_id = request.args.get("project_id", type=int)
        rows = get_project_profitability(db, project_id, from_date, to_date)
        data = {"rows": rows}
    if export == "excel":
        export_rows = rows or data.get("rows") or data.get("income", []) + data.get("expenses", [])
        if not export_rows and report == "profit_loss":
            export_rows = data.get("income", []) + data.get("expenses", [])
        buf = export_report_excel(export_rows or [{"report": report}], report)
        return send_file(
            buf,
            as_attachment=True,
            download_name=f"{report}.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    if export == "csv":
        export_rows = rows or data.get("rows") or []
        if not export_rows and report == "profit_loss":
            export_rows = data.get("income", []) + data.get("expenses", [])
        elif not export_rows and report == "balance_sheet":
            export_rows = data.get("assets", []) + data.get("liabilities", [])
        elif not export_rows and report == "cash_flow":
            export_rows = data.get("cash_lines", []) + data.get("bank_lines", [])
        resp = make_response(export_report_csv(export_rows or [{"report": report}]))
        resp.headers["Content-Type"] = "text/csv"
        resp.headers["Content-Disposition"] = f"attachment; filename={report}.csv"
        return resp
    return render_template(
        "accounts_reports.html",
        report=report,
        data=data,
        rows=rows,
        from_date=from_date or "",
        to_date=to_date or "",
        projects=_accounts_projects(),
    )


@app.route("/accounts/tally-export")
@login_required
def accounts_tally_export():
    db = get_db()
    _prepare_accounts_db(db)
    from_date, to_date = _accounts_date_range()
    if request.args.get("download"):
        xml = export_tally_xml(db, from_date, to_date)
        resp = make_response(xml)
        resp.headers["Content-Type"] = "application/xml"
        resp.headers["Content-Disposition"] = "attachment; filename=tally_vouchers.xml"
        return resp
    count = db.execute("SELECT COUNT(*) AS c FROM journal_entries WHERE is_void=0").fetchone()["c"]
    return render_template(
        "accounts_tally_export.html",
        from_date=from_date or "",
        to_date=to_date or "",
        journal_count=count,
    )


@app.route("/accounts/attachments/<entity_type>/<int:entity_id>/<path:filename>")
@login_required
def accounts_attachment_download(entity_type, entity_id, filename):
    if entity_type not in ("expense", "payment", "receipt"):
        abort(404)
    safe = os.path.basename(filename)
    return send_from_directory(ACCOUNTS_DOCS_DIR, safe, as_attachment=True)


@app.route("/api/accounts/chart-heads")
@login_required
def api_accounts_chart_heads():
    db = get_db()
    _prepare_accounts_db(db)
    account_type = request.args.get("account_type", "").strip() or None
    heads = chart_heads_payload(db, account_type=account_type)
    return jsonify({"heads": heads, "count": len(heads)})


@app.route("/api/accounts/petty-cash-balance/<int:request_id>")
@login_required
def api_accounts_petty_cash_balance(request_id):
    db = get_db()
    _prepare_accounts_db(db)
    return jsonify({"balance": get_petty_cash_balance(db, request_id)})


@app.route("/api/accounts/unpaid-expenses")
@login_required
def api_accounts_unpaid_expenses():
    db = get_db()
    _prepare_accounts_db(db)
    vendor = request.args.get("vendor", "").strip()
    items = []
    for row in list_unpaid_expenses_for_vendor(db, vendor):
        due = _safe_float(row.get("grand_total")) - _safe_float(row.get("amount_paid"))
        items.append({
            "id": row["id"],
            "label": f"#{row['id']} {row.get('invoice_number') or ''} — ₹{due:.2f} due",
            "due_amount": due,
        })
    return jsonify({"items": items})


@app.route("/leave-request", methods=["GET", "POST"])
@login_required
def leave_request():
    module_id, table, endpoint = "leave_request", "leave_requests", "leave_request"
    record_sql = "SELECT * FROM leave_requests WHERE id=?"
    workflow = get_workflow_for_module(get_db(), module_id)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        if record_id:
            db = get_db()
            db.execute(
                "UPDATE leave_requests SET employee_name=?, leave_type=?, from_date=?, "
                "to_date=?, days=?, reason=? WHERE id=?",
                (
                    request.form.get("employee_name", ""),
                    request.form.get("leave_type", ""),
                    request.form.get("from_date", ""),
                    request.form.get("to_date", ""),
                    float(request.form.get("days") or 0),
                    request.form.get("reason", ""),
                    record_id,
                ),
            )
            _complete_module_save(db, module_id, table, record_id, edit_role)
            return redirect(url_for(endpoint))
        _submit_module_request(
            module_id, table,
            "employee_name, leave_type, from_date, to_date, days, reason, created_by, approval_status",
            (
                request.form.get("employee_name", ""),
                request.form.get("leave_type", ""),
                request.form.get("from_date", ""),
                request.form.get("to_date", ""),
                float(request.form.get("days") or 0),
                request.form.get("reason", ""),
                session.get("username", ""),
                "Pending Checker",
            ),
        )
        flash("Saved. Status: Pending Checker.")
        return redirect(url_for(endpoint))
    rows = query_db("SELECT * FROM leave_requests ORDER BY id DESC")
    page = _module_page_state(module_id, table, endpoint, record_sql)
    if page.get("redirect"):
        return redirect(page["redirect"])
    return render_template(
        "module_request.html",
        module_title="Leave Request",
        workflow=workflow,
        form_fields=[
            {"name": "employee_name", "label": "Employee Name", "type": "text", "required": True},
            {"name": "leave_type", "label": "Leave Type", "type": "text", "required": True},
            {"name": "from_date", "label": "From Date", "type": "date", "required": True},
            {"name": "to_date", "label": "To Date", "type": "date", "required": True},
            {"name": "days", "label": "Days", "type": "number", "required": True},
            {"name": "reason", "label": "Reason", "type": "textarea", "required": False},
        ],
        table_columns=["Employee", "Type", "From", "To", "Days"],
        row_keys=["employee_name", "leave_type", "from_date", "to_date", "days"],
        view_fields=_module_view_fields(
            ["Employee", "Type", "From", "To", "Days"],
            ["employee_name", "leave_type", "from_date", "to_date", "days"],
            page.get("view_record"),
        ),
        rows=[dict(r) for r in rows],
        module_endpoint=endpoint,
        delete_table=table,
        **page,
    )


@app.route("/store-issue", methods=["GET", "POST"])
@login_required
def store_issue():
    db = get_db()
    _prepare_store_db(db)
    module_id, table, endpoint = "store_issue", "store_issues", "store_issue"
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    materials = list_materials(db, active_only=True)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        try:
            if record_id:
                save_store_issue(db, request.form, session.get("username", ""), record_id)
                _complete_module_save(db, module_id, table, record_id, edit_role)
            else:
                new_id = save_store_issue(db, request.form, session.get("username", ""))
                create_approval_request(
                    db, module_id, new_id, table,
                    session.get("username", ""), session.get("user_id"),
                )
                db.commit()
                flash("Store issue saved. Status: Pending Checker.")
            return redirect(url_for(endpoint))
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.referrer or url_for(endpoint, new=1))
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = load_store_issue(db, int(view_id))
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = load_store_issue(db, int(edit_id))
        if edit_record:
            edit_role = get_edit_role_for_user(
                db, session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}
    show_form = bool(request.args.get("new")) or edit_record
    rows = list_store_issues(db)
    return render_template(
        "store_issue.html",
        rows=rows,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        projects=projects,
        materials=materials,
        default_date=datetime.now().strftime("%Y-%m-%d"),
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/material-transfer", methods=["GET", "POST"])
@login_required
def material_transfer():
    db = get_db()
    _prepare_store_db(db)
    module_id, table, endpoint = "material_transfer", "material_transfers", "material_transfer"
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    materials = list_materials(db, active_only=True)
    if request.method == "POST":
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        try:
            if record_id:
                save_material_transfer(db, request.form, session.get("username", ""), record_id)
                _complete_module_save(db, module_id, table, record_id, edit_role)
            else:
                new_id = save_material_transfer(db, request.form, session.get("username", ""))
                create_approval_request(
                    db, module_id, new_id, table,
                    session.get("username", ""), session.get("user_id"),
                )
                db.commit()
                flash("Material transfer saved. Status: Pending Checker.")
            return redirect(url_for(endpoint))
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.referrer or url_for(endpoint, new=1))
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = load_material_transfer(db, int(view_id))
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = load_material_transfer(db, int(edit_id))
        if edit_record:
            if edit_record.get("stock_posted"):
                flash("Cannot edit transfer after stock has been posted.")
                return redirect(url_for(endpoint, view=edit_id))
            edit_role = get_edit_role_for_user(
                db, session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}
    show_form = bool(request.args.get("new")) or edit_record
    rows = list_material_transfers(db)
    return render_template(
        "material_transfer.html",
        rows=rows,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        projects=projects,
        materials=materials,
        transfer_types=MATERIAL_TRANSFER_TYPES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/store-receipt", methods=["GET", "POST"])
@login_required
def store_receipt():
    db = get_db()
    _prepare_store_db(db)
    module_id, table, endpoint = "store_receipt", "store_receipts", "store_receipt"
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    materials = list_materials(db, active_only=True)
    vendors = list_vendors(db, active_only=True)
    purchase_orders = [
        po for po in list_purchase_orders(db)
        if po.get("approval_status") == RECORD_APPROVED
    ]
    if request.method == "POST":
        inline = _handle_add_vendor_form(db, endpoint, "#grn-form", {"new": 1})
        if inline:
            return inline
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        try:
            if record_id:
                save_store_receipt(db, request.form, session.get("username", ""), record_id)
                _complete_module_save(db, module_id, table, record_id, edit_role)
            else:
                new_id = save_store_receipt(db, request.form, session.get("username", ""))
                create_approval_request(
                    db, module_id, new_id, table,
                    session.get("username", ""), session.get("user_id"),
                )
                db.commit()
                flash("GRN saved. Status: Pending Checker.")
            return redirect(url_for(endpoint))
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.referrer or url_for(endpoint, new=1))
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = load_store_receipt(db, int(view_id))
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = load_store_receipt(db, int(edit_id))
        if edit_record:
            if edit_record.get("stock_posted"):
                flash("Cannot edit GRN after stock has been posted.")
                return redirect(url_for(endpoint, view=edit_id))
            edit_role = get_edit_role_for_user(
                db, session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}
    show_form = bool(request.args.get("new")) or edit_record
    rows = list_store_receipts(db)
    if show_form or edit_record:
        module_active_anchor = "grn-form"
    else:
        module_active_anchor = "grn-register"
    return render_template(
        "store_grn.html",
        rows=rows,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        projects=projects,
        materials=materials,
        vendors=vendors,
        purchase_orders=purchase_orders,
        default_date=datetime.now().strftime("%Y-%m-%d"),
        select_vendor=request.args.get("select_vendor", type=int),
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
        next_vendor_code=generate_vendor_code(db),
        vendor_types=VENDOR_TYPES,
        module_active_anchor=module_active_anchor,
    )


@app.route("/store")
@login_required
def store():
    db = get_db()
    try:
        _prepare_store_db(db)
        stats = store_dashboard_stats(db)
    except Exception:
        app.logger.exception("Store dashboard failed")
        stats = {
            "materials": 0,
            "vendors": 0,
            "pending_material_requests": 0,
            "pending_purchase_requests": 0,
            "pending_purchase_orders": 0,
            "pending_grn": 0,
            "low_stock_count": 0,
            "low_stock_items": [],
            "stock_items": 0,
            "approx_stock_value": 0.0,
        }
    modules = [
        {"endpoint": "store_materials", "label": "Material Master", "icon": "fa-boxes-stacked", "description": "Item codes, HSN, GST, reorder levels"},
        {"endpoint": "material_request", "label": "Material Request", "icon": "fa-clipboard-list", "description": "Site material requisitions"},
        {"endpoint": "purchase_request", "label": "Purchase Request", "icon": "fa-file-circle-plus", "description": "Internal purchase requests"},
        {"endpoint": "purchase_orders", "label": "Purchase Orders", "icon": "fa-file-invoice", "description": "Vendor PO with workflow"},
        {"endpoint": "store_receipt", "label": "GRN / Receipt", "icon": "fa-dolly", "description": "Goods receipt & stock in"},
        {"endpoint": "store_issue", "label": "Store Issue", "icon": "fa-arrow-right-from-bracket", "description": "Issue materials with stock check"},
        {"endpoint": "material_transfer", "label": "Material Transfer", "icon": "fa-truck-ramp-box", "description": "Store-to-store, store-to-site, site-to-site"},
        {"endpoint": "inventory", "label": "Inventory", "icon": "fa-warehouse", "description": "Stock balances & low-stock alerts"},
    ]
    return render_template("store_dashboard.html", stats=stats, modules=modules)


@app.route("/store/materials", methods=["GET", "POST"])
@login_required
def store_materials():
    db = get_db()
    _prepare_store_db(db)
    if request.method == "POST":
        action = request.form.get("form_action", "save_material")
        if action == "add_vendor":
            inline = _handle_add_vendor_form(db, "store_materials", "#mat-form-panel", {"mat_open": "new"})
            if inline:
                return inline
        if action == "import_materials":
            upload = request.files.get("import_file")
            if not upload or not upload.filename:
                flash("Select an Excel file to import.")
            else:
                count, errors = import_materials_excel(db, upload, session.get("username", ""))
                db.commit()
                flash(f"Imported {count} material(s).")
                for err in errors[:5]:
                    flash(err, "warning")
            return redirect(url_for("store_materials"))
        try:
            mid = request.form.get("material_id", "").strip()
            save_material(db, request.form, int(mid) if mid else None)
            db.commit()
            flash("Material saved.")
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save — code may already exist.")
        return redirect(url_for("store_materials"))
    if request.args.get("export") == "excel":
        buf = export_materials_excel(db)
        return send_file(
            buf,
            as_attachment=True,
            download_name="materials.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    rows = list_materials(db)
    return render_template(
        "store_materials.html",
        rows=rows,
        categories=MATERIAL_CATEGORIES,
        units=MATERIAL_UNITS,
        gst_rates=STORE_GST_RATES,
        vendors=list_vendors(db, active_only=True),
        select_vendor=request.args.get("select_vendor", type=int),
        mat_open=request.args.get("mat_open"),
        next_vendor_code=generate_vendor_code(db),
        vendor_types=VENDOR_TYPES,
    )


@app.route("/api/vendors/<int:vendor_id>")
@login_required
def api_vendor_detail(vendor_id):
    db = get_db()
    _prepare_store_db(db)
    vendor_row = get_vendor(db, vendor_id)
    if not vendor_row:
        return jsonify({"error": "Not found"}), 404
    payload = dict(vendor_row)
    payload["vendor_types"] = vendor_types_list(vendor_row)
    payload["trade_categories"] = vendor_trade_categories_list(vendor_row)
    payload["trade_display"] = ", ".join(payload["trade_categories"]) or "—"
    return jsonify(payload)


@app.route("/masters")
@login_required
def masters_dashboard():
    db = get_db()
    stat_cards = [
        {"label": "Clients", "value": _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM clients")},
        {"label": "Vendors", "value": _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM vendors")},
        {"label": "Equipment Records", "value": _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM equipment_master")},
        {"label": "Bank Accounts", "value": _safe_scalar_count(db, "SELECT COUNT(*) AS c FROM treasury_bank_accounts")},
    ]
    modules = [
        {"endpoint": "clients", "label": "Client Master", "icon": "fa-building", "description": "Client companies & contacts"},
        {"endpoint": "purchase_vendors", "label": "Vendor Master", "icon": "fa-truck-field", "description": "Suppliers, subcontractors & service vendors"},
        {"endpoint": "treasury_equipment_costing", "label": "Equipment Master", "icon": "fa-truck-monster", "description": "Owned & hired equipment registry"},
        {"endpoint": "treasury_bank_accounts", "label": "Bank Master", "icon": "fa-building-columns", "description": "Company bank accounts & IFSC"},
    ]
    return _render_department_hub("Master Dashboard", "Masters", stat_cards, modules, "Master data")


@app.route("/masters/vendors")
@login_required
def masters_vendors():
    return redirect(url_for("purchase_vendors"))


@app.route("/purchase/vendors", methods=["GET", "POST"])
@login_required
def purchase_vendors():
    db = get_db()
    _prepare_store_db(db)
    edit_id = request.args.get("edit", type=int)
    view_id = request.args.get("view", type=int)
    editing_vendor = get_vendor(db, edit_id) if edit_id else None
    if edit_id and not editing_vendor:
        flash("Vendor record not found.")
        return redirect(url_for("purchase_vendors"))
    view_vendor = get_vendor(db, view_id) if view_id and not editing_vendor else None
    view_docs = list_vendor_documents(db, view_id) if view_vendor else []
    if view_vendor:
        view_vendor = dict(view_vendor)
        view_vendor["vendor_types_display"] = ", ".join(vendor_types_list(view_vendor)) or "—"
        view_vendor["trade_categories_display"] = ", ".join(vendor_trade_categories_list(view_vendor)) or "—"
    if request.method == "POST":
        try:
            vid = request.form.get("vendor_id", "").strip()
            uploads = {}
            for field in (
                "photo",
                "pan_document",
                "aadhaar_document",
                "gst_document",
                "bank_proof_document",
            ):
                upload = request.files.get(field)
                if upload and upload.filename:
                    stored = save_file(upload, VENDOR_UPLOADS_DIR)
                    if stored:
                        uploads[field] = stored
            vendor_id = save_vendor(
                db,
                request.form,
                int(vid) if vid else None,
                uploads=uploads,
            )
            for extra in request.files.getlist("other_documents"):
                if extra and extra.filename:
                    stored = save_file(extra, VENDOR_UPLOADS_DIR)
                    if stored:
                        save_vendor_document(
                            db,
                            vendor_id,
                            stored,
                            "Other",
                            session.get("username", ""),
                        )
            upload = request.files.get("vendor_doc")
            if upload and upload.filename:
                stored = save_file(upload, VENDOR_UPLOADS_DIR)
                if stored:
                    save_vendor_document(
                        db,
                        vendor_id,
                        stored,
                        request.form.get("doc_type", "Other"),
                        session.get("username", ""),
                    )
            db.commit()
            flash("Vendor saved.")
            if vid:
                return redirect(url_for("purchase_vendors", edit=vendor_id) + "#add-vendor")
            return redirect(url_for("purchase_vendors", view=vendor_id) + "#vendor-list")
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save vendor.")
        return redirect(url_for("purchase_vendors") + "#add-vendor")
    rows = list_vendors(db)
    for row in rows:
        row["vendor_types_display"] = ", ".join(vendor_types_list(row)) or "—"
        row["trade_categories_display"] = ", ".join(vendor_trade_categories_list(row)) or "—"
    editing_types = vendor_types_list(editing_vendor) if editing_vendor else []
    editing_trades = vendor_trade_categories_list(editing_vendor) if editing_vendor else []
    return render_template(
        "purchase_vendors.html",
        rows=rows,
        editing_vendor=editing_vendor,
        editing_vendor_types=editing_types,
        editing_trade_categories=editing_trades,
        view_vendor=view_vendor,
        view_docs=view_docs,
        doc_types=VENDOR_DOC_TYPES,
        vendor_types=VENDOR_TYPE_OPTIONS,
        trade_categories=TRADE_CATEGORY_OPTIONS,
        next_vendor_code=generate_vendor_code(db),
    )


@app.route("/purchase/vendors/<int:vendor_id>/docs/<path:filename>")
@login_required
def vendor_document_download(vendor_id, filename):
    safe = os.path.basename(filename)
    for folder in (VENDOR_UPLOADS_DIR, STORE_DOCS_DIR):
        path = os.path.join(folder, safe)
        if os.path.isfile(path):
            return send_from_directory(folder, safe, as_attachment=True)
    abort(404)


@app.route("/purchase")
@login_required
def purchase():
    return redirect(url_for("purchase_orders"))


@app.route("/purchase/orders", methods=["GET", "POST"])
@login_required
def purchase_orders():
    db = get_db()
    _prepare_store_db(db)
    module_id, table, endpoint = "purchase_order", "purchase_orders", "purchase_orders"
    if request.method == "POST":
        inline = _handle_add_vendor_form(db, endpoint, "#po-form", {"new": 1})
        if inline:
            return inline
        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        try:
            if record_id:
                save_purchase_order(db, request.form, session.get("username", ""), record_id)
                _complete_module_save(db, module_id, table, record_id, edit_role)
            else:
                new_id = save_purchase_order(db, request.form, session.get("username", ""))
                create_approval_request(
                    db, module_id, new_id, table,
                    session.get("username", ""), session.get("user_id"),
                )
                db.commit()
                flash("Purchase order saved. Status: Pending Checker.")
            return redirect(url_for(endpoint))
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.referrer or url_for(endpoint, new=1))
    view_id = request.args.get("view")
    edit_id = request.args.get("edit")
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = load_purchase_order(db, int(view_id))
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
    elif edit_id:
        edit_record = load_purchase_order(db, int(edit_id))
        if edit_record:
            edit_role = get_edit_role_for_user(
                db, session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}
    show_form = bool(request.args.get("new")) or edit_record
    rows = list_purchase_orders(db)
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    return render_template(
        "purchase_orders.html",
        rows=rows,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        vendors=list_vendors(db, active_only=True),
        materials=list_materials(db, active_only=True),
        projects=projects,
        gst_rates=STORE_GST_RATES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
        select_vendor=request.args.get("select_vendor", type=int),
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
        next_vendor_code=generate_vendor_code(db),
        vendor_types=VENDOR_TYPES,
    )


@app.route("/purchase/orders/<int:po_id>/print")
@login_required
def purchase_order_print(po_id):
    db = get_db()
    _prepare_store_db(db)
    po = load_purchase_order(db, po_id)
    if not po:
        flash("Purchase order not found.")
        return redirect(url_for("purchase_orders"))
    _prepare_corporate_template_db(db)
    ctx = _build_corporate_report_context(
        db,
        "purchase_order",
        document_number=po.get("po_number") or "",
        project_name=po.get("project_name") or "",
        project_id=str(po.get("project_id") or ""),
        prepared_by=session.get("username", ""),
        report_date=po.get("order_date"),
        back_url=url_for("purchase_orders", view=po["id"]),
        page_orientation="portrait",
    )
    return render_template(
        "purchase_order_print.html",
        po=po,
        ctx=ctx,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        autoprint=request.args.get("print") == "1",
    )


@app.route("/store/stock-balance")
@login_required
def store_stock_balance_api():
    db = get_db()
    _prepare_store_db(db)
    material_id = request.args.get("material_id", type=int)
    project_id = request.args.get("project_id", type=int)
    if not material_id:
        return jsonify({"balance": 0})
    balance = get_stock_balance(db, material_id, project_id)
    return jsonify({"balance": balance, "material_id": material_id, "project_id": project_id})


@app.route("/store/project-material-qty")
@login_required
def store_project_material_qty_api():
    db = get_db()
    _prepare_store_db(db)
    try:
        prepare_cost_planning_db(db)
    except Exception:
        pass
    project_id = request.args.get("project_id", type=int)
    material_id = request.args.get("material_id", type=int)
    exclude_request_id = request.args.get("exclude_request_id", type=int)
    if not project_id or not material_id:
        return jsonify({"error": "project_id and material_id are required"}), 400
    stats = get_project_material_qty_stats(db, project_id, material_id, exclude_request_id)
    return jsonify(stats)


@app.route("/store/project-planned-materials")
@login_required
def store_project_planned_materials_api():
    db = get_db()
    _prepare_store_db(db)
    try:
        prepare_cost_planning_db(db)
    except Exception:
        pass
    project_id = request.args.get("project_id", type=int)
    if not project_id:
        return jsonify({"error": "project_id is required"}), 400
    return jsonify(get_project_planned_materials(db, project_id))


@app.route("/inventory")
@login_required
def inventory():
    db = get_db()
    _prepare_store_db(db)
    rows = list_inventory_stock(db)
    low_stock_count = sum(1 for r in rows if r.get("low_stock"))
    return render_template("store_inventory.html", rows=rows, low_stock_count=low_stock_count)


@app.route("/timesheet")
@login_required
def timesheet():
    db = get_db()
    ensure_attendance_master_schema(db)
    db.commit()
    rows = query_db(
        "SELECT a.id, a.attendance_date, a.in_time AS start_time, a.out_time AS end_time, "
        "a.break_hours, a.total_hours AS worked_hours, a.ot_hours AS overtime, "
        "a.approval_status, "
        "COALESCE(w.worker_name, s.staff_name) AS worker_name, "
        "COALESCE(w.worker_code, s.employee_code) AS worker_code, "
        "p.project_name, p.project_code, "
        "t.trade_name, ad.designation_name "
        "FROM attendance a "
        f"{ATTENDANCE_WORKER_JOIN_SQL} "
        "LEFT JOIN projects p ON a.project_id = p.id "
        f"{ATTENDANCE_MASTER_JOIN_SQL} "
        "ORDER BY a.id DESC LIMIT 50"
    )
    return render_template("timesheet.html", rows=rows)


@app.route("/wbs")
@login_required
def wbs_redirect():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        return redirect(url_for("cost_planning", project_id=project_id) + "#wbs-view")
    return redirect(url_for("cost_planning") + "#wbs-view")


PROJECT_DOC_FIELDS = (
    ("agreement_document", "Agreement"),
    ("work_order_document", "Work Order"),
    ("bank_guarantee_document", "Bank Guarantee"),
    ("security_deposit_document", "Security Deposit"),
)


@app.route("/project-documents")
@login_required
def project_documents():
    search = request.args.get("q", "").strip()
    clauses = ["1=1"]
    params = []
    if search:
        clauses.append("(project_code LIKE ? OR project_name LIKE ? OR work_order_number LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    rows = query_db(
        "SELECT id, project_code, project_name, work_order_number, "
        "agreement_document, work_order_document, bank_guarantee_document, security_deposit_document "
        f"FROM projects WHERE {' AND '.join(clauses)} ORDER BY project_name",
        params,
    )
    doc_rows = []
    for row in rows:
        item = dict(row)
        item["documents"] = [
            {"field": field, "label": label, "filename": item.get(field) or ""}
            for field, label in PROJECT_DOC_FIELDS
            if item.get(field)
        ]
        item["doc_count"] = len(item["documents"])
        doc_rows.append(item)
    return render_template(
        "project_documents_register.html",
        rows=doc_rows,
        search=search,
        doc_fields=PROJECT_DOC_FIELDS,
    )


@app.route("/project-documents/download/<int:project_id>/<doc_field>")
@login_required
def project_document_download(project_id, doc_field):
    allowed = {field for field, _ in PROJECT_DOC_FIELDS}
    if doc_field not in allowed:
        flash("Invalid document type.")
        return redirect(url_for("project_documents"))
    row = query_db(
        f"SELECT {doc_field} FROM projects WHERE id=?",
        (project_id,),
        one=True,
    )
    if not row or not row[doc_field]:
        flash("Document not found.")
        return redirect(url_for("project_documents"))
    path = os.path.join(PROJECT_DOCS_DIR, row[doc_field])
    if not os.path.isfile(path):
        flash("Document file missing on server.")
        return redirect(url_for("project_documents"))
    return send_from_directory(
        PROJECT_DOCS_DIR,
        row[doc_field],
        as_attachment=request.args.get("download") == "1",
    )


@app.route("/cost-planning", methods=["GET", "POST"])
@login_required
def cost_planning():
    db = get_db()
    prepare_cost_planning_db(db)
    ensure_boq_master_table(db)
    ensure_equipment_master_table(db)

    if request.method == "POST":
        form_action = request.form.get("form_action", "save_plan").strip()
        username = session.get("username", "")

        if form_action == "delete_plan":
            plan_id = request.form.get("cost_plan_id", "").strip()
            if plan_id.isdigit():
                db.execute("DELETE FROM cost_plans WHERE id=?", (plan_id,))
                db.commit()
                flash("Cost plan deleted.")
            return redirect(url_for("cost_planning", project_id=request.form.get("project_id")))

        if form_action == "save_micro":
            entry_id, err = save_micro_plan_from_form(db, request.form, username)
            if err:
                flash(err)
            else:
                db.commit()
                flash("Micro plan entry saved.")
            return redirect(
                url_for(
                    "cost_planning",
                    project_id=request.form.get("micro_project_id"),
                    plan=request.form.get("micro_cost_plan_id"),
                )
                + "#micro-planning"
            )

        module_id, table = "cost_planning", "cost_plans"
        cost_plan_id_raw = request.form.get("cost_plan_id", "").strip()
        is_edit = cost_plan_id_raw.isdigit()
        edit_role = None
        if is_edit:
            existing = db.execute(
                "SELECT approval_status FROM cost_plans WHERE id=?",
                (cost_plan_id_raw,),
            ).fetchone()
            if not existing:
                flash("Cost plan not found.")
                return redirect(url_for("cost_planning"))
            edit_role = get_edit_role_for_user(
                db,
                session.get("user_id"),
                module_id,
                existing["approval_status"],
                is_admin_user(),
            )
            if not edit_role:
                flash("This cost plan is locked and cannot be edited.")
                return redirect(url_for("cost_planning", view=cost_plan_id_raw))

        plan_id, err = save_cost_plan_from_form(db, request.form, username)
        if err:
            flash(err)
            return redirect(url_for("cost_planning") + "#cost-plan-form")
        if is_edit:
            _complete_module_save(db, module_id, table, plan_id, edit_role)
        else:
            db.execute(
                "UPDATE cost_plans SET approval_status=? WHERE id=?",
                (RECORD_PENDING_CHECKER, plan_id),
            )
            create_approval_request(
                db, module_id, plan_id, table, username, session.get("user_id")
            )
            db.commit()
            flash("Cost plan saved. Status: Pending Checker.")
        return redirect(
            url_for("cost_planning", project_id=request.form.get("project_id"), plan=plan_id)
            + "#cost-plan-form"
        )

    filter_project = request.args.get("project_id", type=int)
    view_plan_id = request.args.get("plan", type=int) or request.args.get("view", type=int)
    edit_plan_id = request.args.get("edit", type=int)

    editing_plan = None
    if edit_plan_id:
        editing_plan = load_cost_plan_detail(db, edit_plan_id)

    view_plan = None
    if view_plan_id and not edit_plan_id:
        view_plan = load_cost_plan_detail(db, view_plan_id)

    projects = get_project_options_for_boq()
    plan_rows = list_cost_plans(db, filter_project)
    monitoring_rows = [build_monitoring_row(db, row) for row in plan_rows]
    dashboard = get_cost_plan_dashboard(db, filter_project)
    wbs_tree = build_wbs_tree(db, filter_project) if filter_project else []

    boq_masters = []
    if filter_project:
        boq_masters = [
            dict(r)
            for r in query_db(
                "SELECT id, boq_number FROM boq_master "
                "WHERE project_id=? AND COALESCE(is_deleted, 0)=0 ORDER BY id DESC",
                (filter_project,),
            )
        ]

    equipment_options = [
        dict(r)
        for r in query_db(
            "SELECT id, reg_no, equipment_name, equipment_type, hourly_rate "
            "FROM equipment_master WHERE status IS NULL OR status = 'Active' "
            "ORDER BY equipment_type, equipment_name"
        )
    ]

    micro_entries = []
    active_plan = editing_plan or view_plan
    if active_plan:
        micro_entries = active_plan.get("micro_plans") or []

    prefill_boq_item = request.args.get("boq_item_id", type=int)
    prefill_context = get_boq_item_context(db, prefill_boq_item) if prefill_boq_item else None

    return render_template(
        "cost_planning.html",
        projects=projects,
        filter_project=filter_project,
        boq_masters=boq_masters,
        plan_rows=plan_rows,
        monitoring_rows=monitoring_rows,
        dashboard=dashboard,
        wbs_tree=wbs_tree,
        editing_plan=editing_plan,
        view_plan=view_plan,
        active_plan=active_plan,
        micro_entries=micro_entries,
        default_activities=list(DEFAULT_COST_ACTIVITIES),
        micro_periods=list(MICRO_PLAN_PERIODS),
        equipment_options=equipment_options,
        prefill_context=prefill_context,
        prefill_boq_item=prefill_boq_item,
        default_material_rows=[
            {"material_name": "Cement", "material_unit": "kg", "consumption_factor": 320, "rate": 0},
            {"material_name": "Steel", "material_unit": "kg", "consumption_factor": 110, "rate": 0},
        ],
        default_manpower_rows=[
            {"trade_name": "Mason", "planned_manpower": 0, "hours_per_unit": 0.5, "labour_rate": 0},
            {"trade_name": "Helper", "planned_manpower": 0, "hours_per_unit": 1.0, "labour_rate": 0},
        ],
        default_machinery_rows=[
            {"equipment_type": "Excavator", "hours_per_unit": 0.3, "hourly_rate": 1500},
        ],
    )


@app.route("/api/cost-planning/boq-item/<int:boq_item_id>")
@login_required
def api_cost_planning_boq_item(boq_item_id):
    db = get_db()
    prepare_cost_planning_db(db)
    ctx = get_boq_item_context(db, boq_item_id)
    if not ctx:
        return jsonify({"error": "BOQ item not found"}), 404
    existing = db.execute(
        "SELECT id FROM cost_plans WHERE boq_item_id=?",
        (boq_item_id,),
    ).fetchone()
    ctx["existing_cost_plan_id"] = existing["id"] if existing else None
    ctx["dpr_actuals"] = aggregate_dpr_actuals(db, boq_item_id)
    return jsonify(ctx)


@app.route("/api/cost-planning/activities")
@login_required
def api_cost_planning_activities():
    custom = request.args.get("q", "").strip()
    activities = list(DEFAULT_COST_ACTIVITIES)
    if custom and custom not in activities:
        activities = [custom] + activities
    return jsonify(activities)


@app.route("/api/cost-planning/dpr-actuals")
@login_required
def api_cost_planning_dpr_actuals():
    boq_item_id = request.args.get("boq_item_id", type=int)
    activity_name = request.args.get("activity_name", "").strip() or None
    if not boq_item_id:
        return jsonify({"error": "boq_item_id required"}), 400
    db = get_db()
    prepare_cost_planning_db(db)
    return jsonify(aggregate_dpr_actuals(db, boq_item_id, activity_name))


@app.route("/api/cost-planning/wbs/<int:project_id>")
@login_required
def api_cost_planning_wbs(project_id):
    db = get_db()
    prepare_cost_planning_db(db)
    return jsonify(build_wbs_tree(db, project_id))


@app.route("/api/cost-planning/monitoring/<int:project_id>")
@login_required
def api_cost_planning_monitoring(project_id):
    db = get_db()
    prepare_cost_planning_db(db)
    plans = list_cost_plans(db, project_id)
    return jsonify({
        "dashboard": get_cost_plan_dashboard(db, project_id),
        "rows": [build_monitoring_row(db, row) for row in plans],
    })


@app.route("/cost-planning/export")
@login_required
def cost_planning_export():
    db = get_db()
    prepare_cost_planning_db(db)
    project_id = request.args.get("project_id", type=int)
    rows = export_cost_plan_register_rows(db, project_id)
    if not rows:
        flash("No cost plans to export.")
        return redirect(url_for("cost_planning", project_id=project_id))
    df = pd.DataFrame(rows)
    filename = f"cost_plan_register_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    file_path = os.path.join(REPORTS_DIR, filename)
    df.to_excel(file_path, index=False)
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


@app.route("/cost-planning/print")
@login_required
def cost_planning_print():
    db = get_db()
    prepare_cost_planning_db(db)
    project_id = request.args.get("project_id", type=int)
    if not project_id:
        flash("Select a project for the summary print.")
        return redirect(url_for("cost_planning"))
    project = query_db(
        "SELECT * FROM projects WHERE id=?",
        (project_id,),
        one=True,
    )
    if not project:
        flash("Project not found.")
        return redirect(url_for("cost_planning"))
    plans = list_cost_plans(db, project_id)
    monitoring_rows = [build_monitoring_row(db, row) for row in plans]
    dashboard = get_cost_plan_dashboard(db, project_id)
    return render_template(
        "cost_planning_print.html",
        project=dict(project),
        monitoring_rows=monitoring_rows,
        dashboard=dashboard,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        autoprint=request.args.get("print") == "1",
    )


@app.route("/cost-planning/reports")
@login_required
def cost_planning_reports():
    return render_template(
        "cost_planning_reports.html",
        reports=list(COST_PLAN_REPORTS),
        projects=get_project_options_for_boq(),
    )


@app.route("/payroll", methods=["GET", "POST"])
@login_required
def payroll():
    db = get_db()
    prepare_payroll_page_db(db)
    module_id = "payroll"
    record_table = "payroll_runs"
    username = session.get("username", "")
    user_id = session.get("user_id")

    if request.method == "POST":
        form_action = request.form.get("form_action", "generate").strip()

        if form_action == "save_draft":
            run_id = request.form.get("run_id", type=int)
            if run_id:
                run = db.execute(
                    "SELECT * FROM payroll_runs WHERE id=? AND locked=0", (run_id,)
                ).fetchone()
                if run and (run["status"] or "") == "Draft":
                    now = get_app_now(db).strftime("%Y-%m-%d %H:%M:%S")
                    db.execute(
                        "UPDATE payroll_runs SET draft_saved=1, modified_at=? WHERE id=?",
                        (now, run_id),
                    )
                    db.commit()
                    flash("Payroll draft saved. You can print or proceed to payment when ready.")
                else:
                    flash("Only unlocked draft runs can be saved.")
            return redirect(url_for("payroll", view=run_id))

        if form_action == "proceed_to_payment":
            run_id = request.form.get("run_id", type=int)
            if run_id:
                run = db.execute(
                    "SELECT * FROM payroll_runs WHERE id=? AND locked=0", (run_id,)
                ).fetchone()
                if not run:
                    flash("Payroll run not found.")
                    return redirect(url_for("payroll"))
                run = dict(run)
                if run.get("status") != "Draft":
                    flash("Only draft payroll runs can be finalized for payment.")
                    return redirect(url_for("payroll", view=run_id))
                if not run.get("draft_saved"):
                    flash("Save the draft before proceeding to payment.")
                    return redirect(url_for("payroll", view=run_id))
                now = get_app_now(db).strftime("%Y-%m-%d %H:%M:%S")
                db.execute(
                    "UPDATE payroll_runs SET status=?, approval_status=?, modified_at=? WHERE id=?",
                    ("Approved", RECORD_APPROVED, now, run_id),
                )
                db.execute(
                    "UPDATE payroll_lines SET approval_status=? WHERE payroll_run_id=?",
                    (RECORD_APPROVED, run_id),
                )
                db.commit()
                flash("Payroll marked ready for payment. Record salary payments under Payments.")
                return redirect(url_for("payroll_payments"))
            return redirect(url_for("payroll"))

        if form_action == "delete_run":
            run_id = request.form.get("run_id", type=int)
            if run_id:
                run = db.execute(
                    "SELECT * FROM payroll_runs WHERE id=? AND locked=0", (run_id,)
                ).fetchone()
                if run and (run["status"] or "") == "Draft":
                    db.execute("DELETE FROM payroll_lines WHERE payroll_run_id=?", (run_id,))
                    db.execute(
                        "DELETE FROM approval_requests WHERE module_id=? AND record_id=? AND record_table=?",
                        (module_id, run_id, record_table),
                    )
                    db.execute("DELETE FROM payroll_runs WHERE id=?", (run_id,))
                    db.commit()
                    flash("Draft payroll run deleted.")
                else:
                    flash("Only unlocked draft runs can be deleted.")
            return redirect(url_for("payroll"))

        if form_action == "submit_verification":
            run_id = request.form.get("run_id", type=int)
            if run_id:
                run = db.execute("SELECT * FROM payroll_runs WHERE id=? AND locked=0", (run_id,)).fetchone()
                if run and run["status"] == "Draft":
                    db.execute(
                        "UPDATE payroll_runs SET status=?, verification_status=? WHERE id=?",
                        ("Pending Verification", "Pending", run_id),
                    )
                    db.commit()
                    flash("Payroll submitted for employee verification.")
            return redirect(url_for("payroll", view=run_id))

        if form_action == "submit_checker":
            run_id = request.form.get("run_id", type=int)
            if run_id:
                run = db.execute("SELECT * FROM payroll_runs WHERE id=? AND locked=0", (run_id,)).fetchone()
                if run and run["status"] in ("Draft", "Pending Verification"):
                    db.execute(
                        "UPDATE payroll_runs SET status=?, approval_status=? WHERE id=?",
                        ("Pending Checker", RECORD_PENDING_CHECKER, run_id),
                    )
                    db.execute(
                        "UPDATE payroll_lines SET approval_status=? WHERE payroll_run_id=?",
                        (RECORD_PENDING_CHECKER, run_id),
                    )
                    existing_req = db.execute(
                        "SELECT id FROM approval_requests WHERE module_id=? AND record_id=? AND record_table=?",
                        (module_id, run_id, record_table),
                    ).fetchone()
                    if existing_req:
                        resubmit_record(db, module_id, run_id, record_table, user_id)
                    else:
                        create_approval_request(db, module_id, run_id, record_table, username, user_id)
                    db.commit()
                    flash("Payroll submitted for checker verification.")
            return redirect(url_for("payroll", view=run_id))

        if form_action == "verify_line":
            line_id = request.form.get("line_id", type=int)
            if line_id:
                db.execute(
                    "UPDATE payroll_lines SET verification_status='Verified' WHERE id=? AND locked=0",
                    (line_id,),
                )
                db.commit()
                flash("Employee line verified.")
            return redirect(request.referrer or url_for("payroll"))

        if form_action == "update_line":
            line_id = request.form.get("line_id", type=int)
            run_id = request.form.get("run_id", type=int)
            if line_id and run_id:
                run = db.execute("SELECT locked, status FROM payroll_runs WHERE id=?", (run_id,)).fetchone()
                if run and not run["locked"] and run["status"] == "Draft":
                    try:
                        gross = float(request.form.get("gross_salary") or 0)
                        deductions = float(request.form.get("deductions") or 0)
                        advance = float(request.form.get("advance_deduction") or 0)
                        net = round(gross - deductions - advance, 2)
                    except ValueError:
                        flash("Invalid amounts.")
                        return redirect(url_for("payroll", view=run_id))
                    db.execute(
                        "UPDATE payroll_lines SET gross_salary=?, deductions=?, advance_deduction=?, "
                        "net_salary=?, remarks=? WHERE id=?",
                        (
                            gross, deductions, advance, net,
                            request.form.get("remarks", "").strip(),
                            line_id,
                        ),
                    )
                    totals = db.execute(
                        "SELECT SUM(gross_salary) AS g, SUM(net_salary) AS n FROM payroll_lines WHERE payroll_run_id=?",
                        (run_id,),
                    ).fetchone()
                    db.execute(
                        "UPDATE payroll_runs SET total_gross=?, total_net=?, modified_at=? WHERE id=?",
                        (
                            totals["g"] or 0,
                            totals["n"] or 0,
                            get_app_now(db).strftime("%Y-%m-%d %H:%M:%S"),
                            run_id,
                        ),
                    )
                    db.commit()
                    flash("Payroll line updated.")
            return redirect(url_for("payroll", view=run_id))

        if form_action == "reopen_run":
            run_id = request.form.get("run_id", type=int)
            reason = request.form.get("reopen_reason", "").strip()
            if run_id and is_admin_user():
                if not reason:
                    flash("Reopen reason is required.")
                    return redirect(url_for("payroll", view=run_id))
                req = db.execute(
                    "SELECT id FROM approval_requests WHERE module_id=? AND record_id=? AND record_table=?",
                    (module_id, run_id, record_table),
                ).fetchone()
                if req:
                    ok, msg = reopen_transaction(db, req["id"], user_id, reason, True)
                    flash(msg)
                db.execute(
                    "UPDATE payroll_runs SET locked=0, status='Pending Checker' WHERE id=?",
                    (run_id,),
                )
                db.execute("UPDATE payroll_lines SET locked=0 WHERE payroll_run_id=?", (run_id,))
                db.commit()
            return redirect(url_for("payroll", view=run_id))

        if form_action == "generate":
            gen_mode = request.form.get("gen_mode", "monthly").strip()
            employment_category = (
                request.form.get("employment_category")
                or request.form.get("employee_type")
                or ""
            ).strip()
            if employment_category == "all":
                employment_category = ""
            project_id = request.form.get("project_id", type=int)
            if employment_category == "company_staff":
                project_id = None
            department = request.form.get("department", "").strip() or None
            selected = request.form.getlist("employee_ids")
            if employment_category not in PAYROLL_EMPLOYMENT_CATEGORIES:
                flash("Select employment type: Company Staff or Sub Contractor.")
                return redirect(url_for("payroll") + "#generate-payroll")
            if not selected:
                flash("Select at least one employee for this payroll run.")
                return redirect(url_for("payroll") + "#generate-payroll")

            parsed_employees = []
            for ref in selected:
                ref = str(ref).strip()
                if ":" not in ref:
                    continue
                et, eid = ref.split(":", 1)
                et = et.strip()
                if not eid.isdigit():
                    continue
                if payroll_employment_filter(et) != employment_category:
                    continue
                parsed_employees.append((et, int(eid)))
            if not parsed_employees:
                flash("No valid employees selected for the chosen employment type.")
                return redirect(url_for("payroll") + "#generate-payroll")

            try:
                if gen_mode == "monthly":
                    month = int(request.form.get("month") or 0)
                    year = int(request.form.get("year") or 0)
                    if not month or not year:
                        raise ValueError("Month and year required.")
                    period_start, period_end = period_from_month_year(month, year)
                    run_type = "monthly"
                else:
                    period_start = request.form.get("period_start", "").strip()
                    period_end = request.form.get("period_end", "").strip()
                    month = year = None
                    if not period_start or not period_end:
                        raise ValueError("Date range required.")
                    run_type = "date_range"

                parsed_employees = [
                    (et, eid)
                    for et, eid in parsed_employees
                    if employee_has_period_data(db, et, eid, period_start, period_end)
                ]
                if not parsed_employees:
                    if gen_mode == "monthly":
                        flash("No staff with attendance/data for this month.")
                    else:
                        flash("No staff with attendance/data for this period.")
                    return redirect(url_for("payroll") + "#generate-payroll")

                run_id = _generate_payroll_run_selected(
                    db,
                    run_type=run_type,
                    period_start=period_start,
                    period_end=period_end,
                    month=month,
                    year=year,
                    project_id=project_id,
                    department=department,
                    employees=parsed_employees,
                    employment_category=employment_category,
                    created_by=username,
                )
                db.commit()
                flash(
                    f"Payroll calculated — Run #{run_id}. Review lines, then click Save Draft."
                )
                return redirect(url_for("payroll", view=run_id))
            except ValueError as exc:
                flash(str(exc))
                return redirect(url_for("payroll") + "#generate-payroll")

    view_id = request.args.get("view", type=int)
    view_run = view_lines = None
    wf_ctx = {}
    if view_id:
        view_run = db.execute("SELECT * FROM payroll_runs WHERE id=?", (view_id,)).fetchone()
        if view_run:
            view_run = dict(view_run)
            view_lines = fetch_payroll_lines(db, run_id=view_id)
            wf_ctx = _workflow_view_context(
                module_id, view_id, record_table, view_run.get("approval_status")
            )

    runs = [
        dict(r) for r in db.execute(
            "SELECT pr.*, p.project_name FROM payroll_runs pr "
            "LEFT JOIN projects p ON pr.project_id = p.id "
            "ORDER BY pr.id DESC LIMIT 100"
        ).fetchall()
    ]
    attach_run_employee_summaries(db, runs)
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    departments = get_departments()
    now = get_app_now(db)
    pending_month_filter = request.args.get("pending_month", "").strip() or None
    try:
        pending_payroll = list_pending_payroll_months(
            db,
            year_month_filter=pending_month_filter,
        )
        pending_month_summary = summarize_pending_payroll_months(pending_payroll)
    except Exception:
        app.logger.exception("Pending payroll dashboard failed")
        pending_payroll = []
        pending_month_summary = []
    return render_template(
        "payroll.html",
        runs=runs,
        view_run=view_run,
        view_lines=view_lines,
        projects=projects,
        departments=departments,
        pending_payroll=pending_payroll,
        pending_month_summary=pending_month_summary,
        pending_month_filter=pending_month_filter,
        employee_types=EMPLOYEE_TYPES,
        employment_categories=PAYROLL_EMPLOYMENT_CATEGORIES,
        current_month=now.month,
        current_year=now.year,
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False) or is_admin_user(),
        approval_id=wf_ctx.get("approval_id"),
        module_id=module_id,
    )


@app.route("/payroll/eligible-employees")
@login_required
def payroll_eligible_employees():
    """JSON list of employees with attendance/data for the selected payroll period."""
    db = get_db()
    prepare_payroll_page_db(db)
    gen_mode = request.args.get("gen_mode", "monthly").strip()
    employment_category = request.args.get("employment_category", "").strip()
    if employment_category == "all":
        employment_category = ""
    department = request.args.get("department", "").strip() or None
    project_id = request.args.get("project_id", type=int)
    if employment_category == "company_staff":
        project_id = None

    period_start = period_end = None
    empty_message = "Select employment type and period to load staff."
    if gen_mode == "monthly":
        month = request.args.get("month", type=int)
        year = request.args.get("year", type=int)
        if month and year:
            period_start, period_end = period_from_month_year(month, year)
            empty_message = "No staff with attendance/data for this month."
        else:
            return jsonify({"employees": [], "message": "Select month and year."})
    else:
        period_start = request.args.get("period_start", "").strip() or None
        period_end = request.args.get("period_end", "").strip() or None
        if not period_start or not period_end:
            return jsonify({"employees": [], "message": "Select from and to dates."})
        empty_message = "No staff with attendance/data for this period."

    if employment_category not in PAYROLL_EMPLOYMENT_CATEGORIES:
        return jsonify({"employees": [], "message": "Select employment type."})

    employees = list_eligible_employees(
        db,
        employment_category,
        project_id,
        department,
        period_start=period_start,
        period_end=period_end,
    )
    payload = [serialize_eligible_employee(emp) for emp in employees]
    message = empty_message if not payload else ""
    return jsonify({"employees": payload, "message": message})


@app.route("/payroll/holidays", methods=["GET", "POST"])
@login_required
def payroll_holidays():
    db = get_db()
    prepare_payroll_page_db(db)
    if request.method == "POST":
        form_action = request.form.get("form_action", "save").strip()
        if form_action == "delete":
            hid = request.form.get("holiday_id", type=int)
            if hid:
                db.execute("DELETE FROM holiday_applicability WHERE holiday_id=?", (hid,))
                db.execute("DELETE FROM holidays WHERE id=?", (hid,))
                db.commit()
                flash("Holiday deleted.")
            return redirect(url_for("payroll_holidays"))
        holiday_date = request.form.get("holiday_date", "").strip()
        holiday_name = request.form.get("holiday_name", "").strip()
        holiday_type = request.form.get("holiday_type", "Public").strip()
        applies = request.form.getlist("applies_to")
        if not holiday_date or not holiday_name:
            flash("Holiday date and name are required.")
            return redirect(url_for("payroll_holidays"))
        now = get_app_now(db).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "INSERT INTO holidays(holiday_date, holiday_name, holiday_type, created_by, created_at) "
            "VALUES(?,?,?,?,?)",
            (holiday_date, holiday_name, holiday_type, session.get("username", ""), now),
        )
        hid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        for target in applies:
            if target in EMPLOYEE_TYPES:
                db.execute(
                    "INSERT INTO holiday_applicability(holiday_id, applies_to) VALUES(?,?)",
                    (hid, target),
                )
        db.commit()
        flash("Holiday saved.")
        return redirect(url_for("payroll_holidays"))

    rows = db.execute(
        "SELECT h.*, GROUP_CONCAT(ha.applies_to) AS applies_to "
        "FROM holidays h LEFT JOIN holiday_applicability ha ON h.id = ha.holiday_id "
        "GROUP BY h.id ORDER BY h.holiday_date DESC"
    ).fetchall()
    return render_template(
        "payroll_holidays.html",
        rows=[dict(r) for r in rows],
        employee_types=EMPLOYEE_TYPES,
    )


@app.route("/payroll/payments", methods=["GET", "POST"])
@login_required
def payroll_payments():
    db = get_db()
    prepare_payroll_page_db(db)
    if request.method == "POST":
        line_id = request.form.get("payroll_line_id", type=int)
        if not line_id:
            flash("Select a payroll line.")
            return redirect(url_for("payroll_payments"))
        line = db.execute(
            "SELECT pl.*, pr.locked AS run_locked, pr.status AS run_status "
            "FROM payroll_lines pl JOIN payroll_runs pr ON pl.payroll_run_id = pr.id "
            "WHERE pl.id=?",
            (line_id,),
        ).fetchone()
        if not line:
            flash("Payroll line not found.")
            return redirect(url_for("payroll_payments"))
        line = dict(line)
        if line.get("run_status") != "Approved" and line.get("approval_status") != RECORD_APPROVED:
            flash("Payroll must be approved before payment.")
            return redirect(url_for("payroll_payments"))
        try:
            net_amount = float(request.form.get("net_amount") or line["net_salary"] or 0)
            gross_amount = float(request.form.get("gross_amount") or line["gross_salary"] or 0)
            deductions = float(request.form.get("deductions") or line["deductions"] or 0)
        except ValueError:
            flash("Invalid payment amounts.")
            return redirect(url_for("payroll_payments"))
        now = get_app_now(db).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "INSERT INTO salary_payments(payroll_run_id, payroll_line_id, payment_date, payment_mode, "
            "bank_name, utr_ref, gross_amount, deductions, net_amount, remarks, created_by, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                line["payroll_run_id"],
                line_id,
                request.form.get("payment_date", "").strip() or get_app_now(db).strftime("%Y-%m-%d"),
                request.form.get("payment_mode", "Bank Transfer").strip(),
                request.form.get("bank_name", "").strip(),
                request.form.get("utr_ref", "").strip(),
                gross_amount,
                deductions,
                net_amount,
                request.form.get("remarks", "").strip(),
                session.get("username", ""),
                now,
            ),
        )
        db.execute(
            "UPDATE payroll_lines SET payment_status='Paid', locked=1 WHERE id=?",
            (line_id,),
        )
        unpaid = db.execute(
            "SELECT COUNT(*) AS c FROM payroll_lines "
            "WHERE payroll_run_id=? AND payment_status != 'Paid'",
            (line["payroll_run_id"],),
        ).fetchone()["c"]
        if unpaid == 0:
            db.execute(
                "UPDATE payroll_runs SET status='Paid', locked=1 WHERE id=?",
                (line["payroll_run_id"],),
            )
        db.commit()
        flash("Salary payment recorded.")
        return redirect(url_for("payroll_payments"))

    pending_lines = fetch_payroll_lines(
        db,
        approval_status=RECORD_APPROVED,
        payment_status_not="Paid",
        limit=200,
    )
    payments = db.execute(
        "SELECT sp.*, "
        "COALESCE(NULLIF(TRIM(pl.employee_name), ''), s.staff_name, w.worker_name) AS employee_name, "
        "COALESCE(NULLIF(TRIM(pl.employee_code), ''), s.employee_code, w.worker_code) AS employee_code, "
        "pr.run_ref "
        "FROM salary_payments sp "
        "JOIN payroll_lines pl ON sp.payroll_line_id = pl.id "
        "JOIN payroll_runs pr ON sp.payroll_run_id = pr.id "
        "LEFT JOIN staff s ON pl.staff_id = s.id "
        "LEFT JOIN workers w ON pl.worker_id = w.id "
        "ORDER BY sp.id DESC LIMIT 100"
    ).fetchall()
    return render_template(
        "payroll_payments.html",
        pending_lines=pending_lines,
        payments=[dict(r) for r in payments],
    )


@app.route("/payroll/print-run/<int:run_id>")
@login_required
def payroll_print_run(run_id):
    db = get_db()
    prepare_payroll_page_db(db)
    run = db.execute("SELECT * FROM payroll_runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        flash("Payroll run not found.")
        return redirect(url_for("payroll"))
    run = dict(run)
    try:
        lines = fetch_payroll_lines(db, run_id=run_id)
    except sqlite3.OperationalError:
        app.logger.exception("Payroll register print failed for run_id=%s", run_id)
        flash("Could not load payroll register. Please contact support if this persists.")
        return redirect(url_for("payroll", view=run_id))
    _prepare_corporate_template_db(db)
    ctx = _build_corporate_report_context(
        db,
        "payroll_summary",
        document_number=run.get("run_ref") or str(run_id),
        prepared_by=session.get("username", ""),
        report_date=run.get("period_end") or run.get("period_start"),
        back_url=url_for("payroll", view=run_id),
        page_orientation="landscape",
    )
    return render_template(
        "payroll_run_print.html",
        run=run,
        lines=lines,
        ctx=ctx,
        print_mode=request.args.get("print") == "1",
    )


@app.route("/payroll/print/<int:line_id>")
@login_required
def payroll_print_slip(line_id):
    db = get_db()
    prepare_payroll_page_db(db)
    line_rows = fetch_payroll_lines(db, line_id=line_id)
    if not line_rows:
        flash("Pay slip not found.")
        return redirect(url_for("payroll"))
    line = line_rows[0]
    bank = {}
    if line.get("staff_id"):
        row = db.execute(
            "SELECT bank_account, bank_name, ifsc_code, branch_name FROM staff WHERE id=?",
            (line["staff_id"],),
        ).fetchone()
        bank = dict(row) if row else {}
    elif line.get("worker_id"):
        row = db.execute(
            "SELECT bank_account, bank_name, ifsc_code, branch_name FROM workers WHERE id=?",
            (line["worker_id"],),
        ).fetchone()
        bank = dict(row) if row else {}
    payment = db.execute(
        "SELECT * FROM salary_payments WHERE payroll_line_id=? ORDER BY id DESC LIMIT 1",
        (line_id,),
    ).fetchone()
    _prepare_corporate_template_db(db)
    ctx = _build_corporate_report_context(
        db,
        "salary_slip",
        document_number=line.get("employee_code") or str(line_id),
        prepared_by=session.get("username", ""),
        report_date=line.get("period_end") or line.get("period_start"),
        back_url=url_for("payroll", view=line.get("payroll_run_id")),
        page_orientation="portrait",
    )
    return render_template(
        "payroll_print_slip.html",
        line=line,
        bank=bank,
        payment=dict(payment) if payment else None,
        ctx=ctx,
        print_mode=request.args.get("print") == "1",
    )


@app.route("/payroll/export/<int:run_id>")
@login_required
def payroll_export_register(run_id):
    db = get_db()
    prepare_payroll_page_db(db)
    rows = export_register_rows(db, run_id)
    if not rows:
        flash("No payroll data to export.")
        return redirect(url_for("payroll", view=run_id))
    df = pd.DataFrame(rows)
    cols = [
        "run_ref", "employee_code", "employee_name", "employee_type", "department",
        "period_start", "period_end", "base_salary", "present_days", "ot_hours",
        "ot_amount", "holiday_pay", "gross_salary", "deductions", "advance_deduction",
        "net_salary", "payment_status", "verification_status", "approval_status",
    ]
    export_cols = [c for c in cols if c in df.columns]
    df = df[export_cols]
    filename = f"payroll_register_{run_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.xlsx"
    file_path = os.path.join(REPORTS_DIR, filename)
    df.to_excel(file_path, index=False)
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


@app.route("/employee/<employee_type>/<int:employee_id>")
@login_required
def employee_profile(employee_type, employee_id):
    db = get_db()
    prepare_payroll_page_db(db)
    if employee_type not in EMPLOYEE_TYPES:
        flash("Invalid employee type.")
        return redirect(url_for("staff"))
    profile = get_employee_profile(db, employee_type, employee_id)
    if not profile:
        flash("Employee not found.")
        return redirect(url_for("staff"))
    revisions = profile.get("salary_revisions") or []
    return render_template(
        "employee_profile.html",
        profile=profile,
        employee_type=employee_type,
        revisions=revisions,
        print_mode=request.args.get("print") == "1",
    )


@app.route("/payroll/revisions", methods=["GET", "POST"])
@login_required
def payroll_revisions():
    db = get_db()
    prepare_payroll_page_db(db)
    if request.method == "POST":
        employee_type = request.form.get("employee_type", "").strip()
        staff_id = request.form.get("staff_id", type=int)
        worker_id = request.form.get("worker_id", type=int)
        try:
            revised = float(request.form.get("revised_amount") or 0)
        except ValueError:
            flash("Enter valid revised amount.")
            return redirect(url_for("payroll_revisions"))
        previous = 0.0
        if employee_type == "staff" and staff_id:
            row = db.execute("SELECT salary_amount FROM staff WHERE id=?", (staff_id,)).fetchone()
            previous = float(row["salary_amount"] or 0) if row else 0
        elif worker_id:
            row = db.execute("SELECT salary_amount FROM workers WHERE id=?", (worker_id,)).fetchone()
            previous = float(row["salary_amount"] or 0) if row else 0
        increment = round(revised - previous, 2)
        now = get_app_now(db).strftime("%Y-%m-%d %H:%M:%S")
        effective = request.form.get("effective_date", "").strip() or get_app_now(db).strftime("%Y-%m-%d")
        db.execute(
            "INSERT INTO salary_revisions(employee_type, staff_id, worker_id, previous_amount, "
            "revised_amount, increment_amount, effective_date, reason, approved_by, created_by, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                employee_type,
                staff_id if employee_type == "staff" else None,
                worker_id if employee_type != "staff" else None,
                previous,
                revised,
                increment,
                effective,
                request.form.get("reason", "").strip(),
                request.form.get("approved_by", "").strip() or session.get("username", ""),
                session.get("username", ""),
                now,
            ),
        )
        if employee_type == "staff" and staff_id:
            db.execute("UPDATE staff SET salary_amount=? WHERE id=?", (revised, staff_id))
        elif worker_id:
            db.execute("UPDATE workers SET salary_amount=? WHERE id=?", (revised, worker_id))
        db.commit()
        flash("Salary revision saved.")
        return redirect(url_for("payroll_revisions"))

    revisions = db.execute(
        "SELECT sr.*, "
        "COALESCE(s.staff_name, w.worker_name) AS employee_name, "
        "COALESCE(s.employee_code, w.worker_code) AS employee_code "
        "FROM salary_revisions sr "
        "LEFT JOIN staff s ON sr.staff_id = s.id "
        "LEFT JOIN workers w ON sr.worker_id = w.id "
        "ORDER BY sr.effective_date DESC, sr.id DESC LIMIT 200"
    ).fetchall()
    staff_list = query_db("SELECT id, employee_code, staff_name FROM staff ORDER BY staff_name")
    worker_list = query_db(
        "SELECT id, worker_code, worker_name FROM workers ORDER BY worker_name"
    )
    return render_template(
        "payroll_revisions.html",
        revisions=[dict(r) for r in revisions],
        staff_list=staff_list,
        worker_list=worker_list,
        employee_types=EMPLOYEE_TYPES,
    )


# --- Office Administration & Fleet Management (Phase 1 MVP) ---


@app.route("/office")
@app.route("/office-admin")
@login_required
def office_admin():
    db = get_db()
    try:
        _prepare_office_fleet_db(db)
        stats = office_dashboard_stats(db)
    except Exception:
        app.logger.exception("Office dashboard failed")
        stats = {
            "inward_count": 0, "outward_count": 0, "letters_count": 0,
            "quotations_count": 0, "agreements_count": 0, "legal_count": 0,
            "expiry_alerts": 0, "expiring": {}, "expiring_overdue": [],
            "alert_days": OFFICE_EXPIRY_ALERT_DAYS,
        }
    modules = [
        {"endpoint": "office_inward", "label": "Letter In / Inward Register", "icon": "fa-inbox", "description": "Incoming documents & correspondence"},
        {"endpoint": "office_outward", "label": "Letter Out / Outward Register", "icon": "fa-paper-plane", "description": "Dispatched documents with attachments"},
        {"endpoint": "office_letters", "label": "Letter Preparation / General Letters", "icon": "fa-envelope-open-text", "description": "Official letters with print view"},
        {"endpoint": "office_quotations", "label": "Quotations", "icon": "fa-file-invoice", "description": "Client quotations with GST lines"},
        {"endpoint": "office_po_register", "label": "PO Register", "icon": "fa-clipboard-list", "description": "Read-only view of store purchase orders"},
        {"endpoint": "office_agreements", "label": "Agreements", "icon": "fa-handshake", "description": "Agreement register with attachments"},
        {"endpoint": "office_legal", "label": "Legal Documents", "icon": "fa-scale-balanced", "description": "Legal docs with expiry alerts"},
        {"endpoint": "fleet_dashboard", "label": "Fleet Dashboard", "icon": "fa-truck", "description": "Vehicles, diesel stock & alerts"},
    ]
    return render_template("office_dashboard.html", stats=stats, modules=modules)


@app.route("/fleet")
@login_required
def fleet_dashboard():
    db = get_db()
    try:
        _prepare_office_fleet_db(db)
        stats = fleet_dashboard_stats(db)
    except Exception:
        app.logger.exception("Fleet dashboard failed")
        stats = {
            "active_vehicles": 0, "total_vehicles": 0, "running_logs": 0,
            "diesel_stock_liters": 0, "diesel_purchases": 0, "diesel_issues": 0,
            "expiry_alerts": 0, "expiring": {}, "expiring_overdue": [],
            "alert_days": OFFICE_EXPIRY_ALERT_DAYS,
        }
    modules = [
        {"endpoint": "fleet_vehicles", "label": "Vehicle Master", "icon": "fa-car", "description": "Registration, make, model, status"},
        {"endpoint": "fleet_vehicle_documents", "label": "Vehicle Documents", "icon": "fa-id-card", "description": "RC, insurance, fitness, permits"},
        {"endpoint": "fleet_running_log", "label": "Running Log", "icon": "fa-road", "description": "Daily KM with auto total"},
        {"endpoint": "fleet_diesel_purchase", "label": "Diesel Purchase", "icon": "fa-gas-pump", "description": "Bulk diesel inward"},
        {"endpoint": "fleet_diesel_stock", "label": "Diesel Stock", "icon": "fa-oil-can", "description": "Stock ledger & balance"},
        {"endpoint": "fleet_diesel_issue", "label": "Diesel Issue", "icon": "fa-arrow-right-from-bracket", "description": "Issue diesel to vehicles"},
    ]
    try:
        return render_template("fleet_dashboard.html", stats=stats, modules=modules)
    except Exception:
        app.logger.exception("Fleet dashboard template render failed")
        flash("Fleet dashboard could not be loaded. Please try Office Admin or contact support.", "warning")
        return redirect(url_for("office_admin"))


def _office_projects():
    return query_db("SELECT id, project_name FROM projects ORDER BY project_name")


@app.route("/office/inward", methods=["GET", "POST"])
@login_required
def office_inward():
    db = get_db()
    _prepare_office_fleet_db(db)
    search = request.args.get("q", "")
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            delete_inward(db, int(rid))
            db.commit()
            flash("Inward record deleted.")
            return redirect(url_for("office_inward"))
        try:
            upload = request.files.get("attachment")
            stored = None
            if upload and upload.filename:
                _, err = _validate_office_upload(upload)
                if err:
                    raise ValueError(err)
                stored = save_file(upload, OFFICE_DOCS_DIR)
            save_inward(
                db, request.form, session.get("username", ""),
                int(rid) if rid else None, stored,
            )
            db.commit()
            flash("Inward record saved.")
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save inward record.")
        return redirect(url_for("office_inward"))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_inward(db, view_id) if view_id else None
    edit_record = get_inward(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "office_inward.html",
        rows=list_inward(db, search),
        search=search,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        projects=_office_projects(),
        document_types=DOCUMENT_TYPES,
        modes=INWARD_MODES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/office/outward", methods=["GET", "POST"])
@login_required
def office_outward():
    db = get_db()
    _prepare_office_fleet_db(db)
    search = request.args.get("q", "")
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            delete_outward(db, int(rid))
            db.commit()
            flash("Outward record deleted.")
            return redirect(url_for("office_outward"))
        try:
            upload = request.files.get("attachment")
            stored = None
            if upload and upload.filename:
                _, err = _validate_office_upload(upload, required=not rid)
                if err:
                    raise ValueError(err)
                stored = save_file(upload, OFFICE_DOCS_DIR)
            elif not rid:
                raise ValueError("Document attachment is required for outward register.")
            save_outward(
                db, request.form, session.get("username", ""),
                int(rid) if rid else None, stored,
            )
            db.commit()
            flash("Outward record saved.")
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save outward record.")
        return redirect(url_for("office_outward"))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_outward(db, view_id) if view_id else None
    edit_record = get_outward(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "office_outward.html",
        rows=list_outward(db, search),
        search=search,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        projects=_office_projects(),
        document_types=DOCUMENT_TYPES,
        modes=OUTWARD_MODES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/office/letters", methods=["GET", "POST"])
@login_required
def office_letters():
    db = get_db()
    _prepare_office_fleet_db(db)
    search = request.args.get("q", "")
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            delete_letter(db, int(rid))
            db.commit()
            flash("Letter deleted.")
            return redirect(url_for("office_letters"))
        try:
            save_letter(db, request.form, session.get("username", ""), int(rid) if rid else None)
            db.commit()
            flash("Letter saved.")
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save letter.")
        return redirect(url_for("office_letters"))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_letter(db, view_id) if view_id else None
    edit_record = get_letter(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "office_letters.html",
        rows=list_letters(db, search),
        search=search,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        projects=_office_projects(),
        letter_types=LETTER_TYPES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/office/letters/<int:letter_id>/print")
@login_required
def office_letter_print(letter_id):
    db = get_db()
    _prepare_office_fleet_db(db)
    letter = get_letter(db, letter_id)
    if not letter:
        flash("Letter not found.")
        return redirect(url_for("office_letters"))
    return render_template(
        "letter_print.html",
        letter=letter,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        autoprint=request.args.get("print") == "1",
    )


@app.route("/office/quotations", methods=["GET", "POST"])
@login_required
def office_quotations():
    db = get_db()
    _prepare_office_fleet_db(db)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            delete_quotation(db, int(rid))
            db.commit()
            flash("Quotation deleted.")
            return redirect(url_for("office_quotations"))
        try:
            save_quotation(db, request.form, session.get("username", ""), int(rid) if rid else None)
            db.commit()
            flash("Quotation saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("office_quotations"))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = load_quotation(db, view_id) if view_id else None
    edit_record = load_quotation(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "office_quotations.html",
        rows=list_quotations(db),
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        projects=_office_projects(),
        gst_rates=STORE_GST_RATES,
        tax_types=TAX_TYPES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/office/quotations/<int:quotation_id>/print")
@login_required
def office_quotation_print(quotation_id):
    db = get_db()
    _prepare_office_fleet_db(db)
    quotation = load_quotation(db, quotation_id)
    if not quotation:
        flash("Quotation not found.")
        return redirect(url_for("office_quotations"))
    return render_template(
        "quotation_print.html",
        quotation=quotation,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        autoprint=request.args.get("print") == "1",
    )


@app.route("/office/po-register")
@login_required
def office_po_register():
    db = get_db()
    _prepare_office_fleet_db(db)
    _prepare_store_db(db)
    search = request.args.get("q", "")
    return render_template(
        "office_po_register.html",
        rows=list_po_register(db, search),
        search=search,
    )


@app.route("/office/agreements", methods=["GET", "POST"])
@login_required
def office_agreements():
    db = get_db()
    _prepare_office_fleet_db(db)
    search = request.args.get("q", "")
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            delete_agreement(db, int(rid))
            db.commit()
            flash("Agreement deleted.")
            return redirect(url_for("office_agreements"))
        try:
            upload = request.files.get("attachment")
            stored = None
            if upload and upload.filename:
                _, err = _validate_office_upload(upload)
                if err:
                    raise ValueError(err)
                stored = save_file(upload, OFFICE_DOCS_DIR)
            save_agreement(
                db, request.form, session.get("username", ""),
                int(rid) if rid else None, stored,
            )
            db.commit()
            flash("Agreement saved.")
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save agreement.")
        return redirect(url_for("office_agreements"))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_agreement(db, view_id) if view_id else None
    edit_record = get_agreement(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "office_agreements.html",
        rows=list_agreements(db, search),
        search=search,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        projects=_office_projects(),
        agreement_types=AGREEMENT_TYPES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/office/legal", methods=["GET", "POST"])
@login_required
def office_legal():
    db = get_db()
    _prepare_office_fleet_db(db)
    search = request.args.get("q", "")
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            delete_legal_document(db, int(rid))
            db.commit()
            flash("Legal document removed.")
            return redirect(url_for("office_legal"))
        try:
            upload = request.files.get("attachment")
            stored = None
            if upload and upload.filename:
                _, err = _validate_office_upload(upload)
                if err:
                    raise ValueError(err)
                stored = save_file(upload, OFFICE_DOCS_DIR)
            save_legal_document(
                db, request.form, session.get("username", ""),
                int(rid) if rid else None, stored,
            )
            db.commit()
            flash("Legal document saved.")
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save legal document.")
        return redirect(url_for("office_legal"))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_legal_document(db, view_id) if view_id else None
    edit_record = get_legal_document(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "office_legal.html",
        rows=list_legal_documents(db, search),
        search=search,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        legal_doc_types=LEGAL_DOC_TYPES,
        alert_days=OFFICE_EXPIRY_ALERT_DAYS,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/office/docs/<path:filename>")
@login_required
def office_document_download(filename):
    safe = os.path.basename(filename)
    path = os.path.join(OFFICE_DOCS_DIR, safe)
    if not os.path.isfile(path):
        abort(404)
    return send_from_directory(OFFICE_DOCS_DIR, safe, as_attachment=True)


@app.route("/fleet/docs/<path:filename>")
@login_required
def fleet_document_download(filename):
    safe = os.path.basename(filename)
    path = os.path.join(FLEET_DOCS_DIR, safe)
    if not os.path.isfile(path):
        abort(404)
    return send_from_directory(FLEET_DOCS_DIR, safe, as_attachment=True)


@app.route("/fleet/vehicles", methods=["GET", "POST"])
@login_required
def fleet_vehicles():
    db = get_db()
    _prepare_office_fleet_db(db)
    search = request.args.get("q", "")
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            delete_vehicle(db, int(rid))
            db.commit()
            flash("Vehicle deleted.")
            return redirect(url_for("fleet_vehicles"))
        try:
            save_vehicle(db, request.form, session.get("username", ""), int(rid) if rid else None)
            db.commit()
            flash("Vehicle saved.")
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save vehicle.")
        return redirect(url_for("fleet_vehicles"))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_vehicle(db, view_id) if view_id else None
    edit_record = get_vehicle(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "fleet_vehicles.html",
        rows=list_vehicles(db, search),
        search=search,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        projects=_office_projects(),
        vehicle_types=VEHICLE_TYPES,
        fuel_types=FUEL_TYPES,
        vehicle_statuses=VEHICLE_STATUSES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/fleet/vehicles/<int:vehicle_id>/print")
@login_required
def fleet_vehicle_print(vehicle_id):
    db = get_db()
    _prepare_office_fleet_db(db)
    vehicle = get_vehicle(db, vehicle_id)
    if not vehicle:
        flash("Vehicle not found.")
        return redirect(url_for("fleet_vehicles"))
    docs = list_vehicle_documents(db, vehicle_id)
    _prepare_corporate_template_db(db)
    ctx = _build_corporate_report_context(
        db,
        "vehicle_log_book",
        document_number=vehicle.get("registration_number") or "",
        project_name=vehicle.get("project_name") or "",
        project_id=str(vehicle.get("project_id") or ""),
        prepared_by=session.get("username", ""),
        back_url=url_for("fleet_vehicles", view=vehicle_id),
        page_orientation="portrait",
    )
    return render_template(
        "vehicle_print.html",
        vehicle=vehicle,
        documents=docs,
        ctx=ctx,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        autoprint=request.args.get("print") == "1",
    )


@app.route("/fleet/vehicle-documents", methods=["GET", "POST"])
@login_required
def fleet_vehicle_documents():
    db = get_db()
    _prepare_office_fleet_db(db)
    vehicle_filter = request.args.get("vehicle_id", type=int)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            delete_vehicle_document(db, int(rid))
            db.commit()
            flash("Vehicle document deleted.")
            return redirect(url_for("fleet_vehicle_documents", vehicle_id=vehicle_filter))
        try:
            upload = request.files.get("attachment")
            stored = None
            if upload and upload.filename:
                _, err = _validate_office_upload(upload)
                if err:
                    raise ValueError(err)
                stored = save_file(upload, FLEET_DOCS_DIR)
            save_vehicle_document(
                db, request.form, session.get("username", ""),
                int(rid) if rid else None, stored,
            )
            db.commit()
            flash("Vehicle document saved.")
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save vehicle document.")
        vf = request.form.get("vehicle_id") or vehicle_filter
        return redirect(url_for("fleet_vehicle_documents", vehicle_id=vf))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_vehicle_document(db, view_id) if view_id else None
    edit_record = get_vehicle_document(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "fleet_vehicle_documents.html",
        rows=list_vehicle_documents(db, vehicle_filter),
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        vehicles=list_vehicles(db),
        vehicle_filter=vehicle_filter,
        doc_types=VEHICLE_DOC_TYPES,
        alert_days=OFFICE_EXPIRY_ALERT_DAYS,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/fleet/running-log", methods=["GET", "POST"])
@login_required
def fleet_running_log():
    db = get_db()
    _prepare_office_fleet_db(db)
    vehicle_filter = request.args.get("vehicle_id", type=int)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            delete_running_log(db, int(rid))
            db.commit()
            flash("Running log entry deleted.")
            return redirect(url_for("fleet_running_log", vehicle_id=vehicle_filter))
        try:
            save_running_log(db, request.form, session.get("username", ""), int(rid) if rid else None)
            db.commit()
            flash("Running log saved.")
        except ValueError as exc:
            flash(str(exc))
        vf = request.form.get("vehicle_id") or vehicle_filter
        return redirect(url_for("fleet_running_log", vehicle_id=vf))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_running_log(db, view_id) if view_id else None
    edit_record = get_running_log(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "fleet_running_log.html",
        rows=list_running_logs(db, vehicle_filter),
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        vehicles=list_vehicles(db),
        vehicle_filter=vehicle_filter,
        projects=_office_projects(),
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/fleet/diesel/purchase", methods=["GET", "POST"])
@login_required
def fleet_diesel_purchase():
    db = get_db()
    _prepare_office_fleet_db(db)
    if request.method == "POST":
        try:
            save_diesel_purchase(db, request.form, session.get("username", ""))
            db.commit()
            flash("Diesel purchase recorded.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("fleet_diesel_purchase"))
    return render_template(
        "fleet_diesel_purchase.html",
        rows=list_diesel_purchases(db),
        stock_balance=get_diesel_stock_balance(db),
        show_form=bool(request.args.get("new")),
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/fleet/diesel/stock")
@login_required
def fleet_diesel_stock():
    db = get_db()
    _prepare_office_fleet_db(db)
    return render_template(
        "fleet_diesel_stock.html",
        ledger=list_diesel_ledger(db),
        stock_balance=get_diesel_stock_balance(db),
        purchases=list_diesel_purchases(db)[:20],
        issues=list_diesel_issues(db)[:20],
    )


@app.route("/fleet/diesel/issue", methods=["GET", "POST"])
@login_required
def fleet_diesel_issue():
    db = get_db()
    _prepare_office_fleet_db(db)
    if request.method == "POST":
        try:
            save_diesel_issue(db, request.form, session.get("username", ""))
            db.commit()
            flash("Diesel issue recorded.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("fleet_diesel_issue"))
    return render_template(
        "fleet_diesel_issue.html",
        rows=list_diesel_issues(db),
        stock_balance=get_diesel_stock_balance(db),
        vehicles=list_vehicles(db),
        projects=_office_projects(),
        show_form=bool(request.args.get("new")),
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


# --- Plant Operations (Phase 2) ---


def _plant_projects():
    return query_db("SELECT id, project_name FROM projects ORDER BY project_name")


def _plant_fleet_vehicles(db):
    try:
        _prepare_office_fleet_db(db)
        return list_vehicles(db)
    except Exception:
        return []


@app.route("/plant")
@login_required
def plant_dashboard():
    db = get_db()
    try:
        _prepare_plant_db(db)
        stats = plant_dashboard_stats(db)
    except Exception:
        app.logger.exception("Plant dashboard failed")
        stats = {
            "total_plants": 0,
            "active_plants": 0,
            "today_production_count": 0,
            "today_dispatch_count": 0,
            "today_production_ton": 0.0,
            "today_dispatch_ton": 0.0,
            "today_rmc_production_count": 0,
            "today_rmc_production_m3": 0.0,
            "today_rmc_dispatch_count": 0,
            "today_wetmix_production_count": 0,
            "today_wetmix_production_qty": 0.0,
            "precast_stock_units": 0.0,
            "today_precast_dispatch_count": 0,
            "low_stock_alerts": 0,
            "today_qc_count": 0,
            "qc_fail_count": 0,
            "open_maintenance_jobs": 0,
            "today_crusher_production_ton": 0.0,
            "today_crusher_production_count": 0,
        }
    modules = [
        {"endpoint": "plant_360", "label": "Plant 360° View", "icon": "fa-circle-nodes", "description": "Unified plant snapshot — production, stock, QC & maintenance"},
        {"endpoint": "plant_plants", "label": "Plant Master", "icon": "fa-industry", "description": "Asphalt, RMC, crusher & other plant sites"},
        {"endpoint": "plant_asphalt_production", "label": "Asphalt Production", "icon": "fa-flask", "description": "Daily mix production with material consumption"},
        {"endpoint": "plant_asphalt_dispatch", "label": "Asphalt Dispatch", "icon": "fa-truck-ramp-box", "description": "Outbound dispatch & stock balance"},
        {"endpoint": "plant_rmc_production", "label": "RMC Production", "icon": "fa-cubes", "description": "Concrete batching by grade (m³)"},
        {"endpoint": "plant_rmc_dispatch", "label": "RMC Dispatch", "icon": "fa-truck", "description": "Transit mixer dispatch & challan"},
        {"endpoint": "plant_wetmix_production", "label": "Wet Mix Production", "icon": "fa-layer-group", "description": "WMM / GSB production entries"},
        {"endpoint": "precast_yard", "label": "Precast Yard", "icon": "fa-border-all", "description": "Yard registry, casting, curing, dispatch & stock"},
        {"endpoint": "plant_crusher_production", "label": "Crusher / M-Sand", "icon": "fa-hammer", "description": "Aggregate & manufactured sand production"},
        {"endpoint": "plant_qc", "label": "Plant QC", "icon": "fa-vial", "description": "Sample tests & quality records"},
        {"endpoint": "plant_costing", "label": "Production Costing", "icon": "fa-indian-rupee-sign", "description": "Material cost summary by production"},
        {"endpoint": "plant_maintenance", "label": "Maintenance Jobs", "icon": "fa-screwdriver-wrench", "description": "Equipment maintenance job cards"},
        {"endpoint": "fleet_diesel_stock", "label": "Fleet Diesel", "icon": "fa-gas-pump", "description": "Diesel stock linked from fleet module"},
    ]
    return render_template("plant_dashboard.html", stats=stats, modules=modules)


@app.route("/plant/plants", methods=["GET", "POST"])
@login_required
def plant_plants():
    db = get_db()
    _prepare_plant_db(db)
    search = request.args.get("q", "")
    plant_type_filter = request.args.get("plant_type", "")
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_plant(db, int(rid))
                db.commit()
                flash("Plant deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("plant_plants"))
        try:
            save_plant(db, request.form, session.get("username", ""), int(rid) if rid else None)
            db.commit()
            flash("Plant saved.")
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save plant.")
        return redirect(url_for("plant_plants"))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_plant(db, view_id) if view_id else None
    edit_record = get_plant(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "plant_master.html",
        rows=list_plants(db, search, plant_type_filter),
        search=search,
        plant_type_filter=plant_type_filter,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        projects=_plant_projects(),
        plant_types=PLANT_TYPES,
        plant_statuses=PLANT_STATUSES,
    )


@app.route("/plant/asphalt/production", methods=["GET", "POST"])
@login_required
def plant_asphalt_production():
    db = get_db()
    _prepare_plant_db(db)
    search = request.args.get("q", "")
    plant_filter = request.args.get("plant_id", type=int)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_asphalt_production(db, int(rid))
                db.commit()
                flash("Production entry deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("plant_asphalt_production", plant_id=plant_filter))
        try:
            save_asphalt_production(
                db, request.form, session.get("username", ""), int(rid) if rid else None
            )
            db.commit()
            flash("Production entry saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("plant_asphalt_production", plant_id=plant_filter))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_asphalt_production(db, view_id) if view_id else None
    edit_record = get_asphalt_production(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    consumption_values = {}
    if edit_record and edit_record.get("consumption"):
        for item in edit_record["consumption"]:
            consumption_values[item.get("material", "")] = item.get("qty", "")
    return render_template(
        "plant_asphalt_production.html",
        rows=list_asphalt_production(db, plant_filter, search),
        search=search,
        plant_filter=plant_filter,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        plants=list_active_plants(db, "Asphalt"),
        projects=_plant_projects(),
        mix_types=ASPHALT_MIX_TYPES,
        shifts=PLANT_SHIFTS,
        consumption_values=consumption_values,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/plant/asphalt/dispatch", methods=["GET", "POST"])
@login_required
def plant_asphalt_dispatch():
    db = get_db()
    _prepare_plant_db(db)
    search = request.args.get("q", "")
    plant_filter = request.args.get("plant_id", type=int)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_asphalt_dispatch(db, int(rid))
                db.commit()
                flash("Dispatch deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("plant_asphalt_dispatch", plant_id=plant_filter))
        try:
            save_asphalt_dispatch(
                db, request.form, session.get("username", ""), int(rid) if rid else None
            )
            db.commit()
            flash("Dispatch saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("plant_asphalt_dispatch", plant_id=plant_filter))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_asphalt_dispatch(db, view_id) if view_id else None
    edit_record = get_asphalt_dispatch(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "plant_asphalt_dispatch.html",
        rows=list_asphalt_dispatch(db, plant_filter, search),
        stock_rows=list_plant_stock(db, plant_filter),
        search=search,
        plant_filter=plant_filter,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        plants=list_active_plants(db, "Asphalt"),
        projects=_plant_projects(),
        vehicles=_plant_fleet_vehicles(db),
        mix_types=ASPHALT_MIX_TYPES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/plant/asphalt/dispatch/<int:dispatch_id>/print")
@login_required
def plant_asphalt_dispatch_print(dispatch_id):
    db = get_db()
    _prepare_plant_db(db)
    record = get_asphalt_dispatch(db, dispatch_id)
    if not record:
        flash("Dispatch not found.")
        return redirect(url_for("plant_asphalt_dispatch"))
    _prepare_corporate_template_db(db)
    ctx = _build_corporate_report_context(
        db,
        "asphalt_plant_production",
        document_number=record.get("dispatch_number") or "",
        project_name=record.get("project_name") or "",
        project_id=str(record.get("project_id") or ""),
        prepared_by=session.get("username", ""),
        report_date=record.get("dispatch_date"),
        back_url=url_for("plant_asphalt_dispatch", view=record["id"]),
        page_orientation="portrait",
    )
    return render_template(
        "plant_asphalt_dispatch_print.html",
        record=record,
        ctx=ctx,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        autoprint=request.args.get("print") == "1",
    )


@app.route("/plant/rmc/production", methods=["GET", "POST"])
@login_required
def plant_rmc_production():
    db = get_db()
    _prepare_plant_db(db)
    search = request.args.get("q", "")
    plant_filter = request.args.get("plant_id", type=int)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_rmc_production(db, int(rid))
                db.commit()
                flash("RMC production entry deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("plant_rmc_production", plant_id=plant_filter))
        try:
            save_rmc_production(
                db, request.form, session.get("username", ""), int(rid) if rid else None
            )
            db.commit()
            flash("RMC production saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("plant_rmc_production", plant_id=plant_filter))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_rmc_production(db, view_id) if view_id else None
    edit_record = get_rmc_production(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    consumption_values = {}
    if edit_record and edit_record.get("consumption"):
        for item in edit_record["consumption"]:
            consumption_values[item.get("material", "")] = item.get("qty", "")
    return render_template(
        "plant_rmc_production.html",
        rows=list_rmc_production(db, plant_filter, search),
        search=search,
        plant_filter=plant_filter,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        plants=list_active_plants(db, "Concrete/RMC"),
        projects=_plant_projects(),
        grades=RMC_GRADES,
        shifts=PLANT_SHIFTS,
        consumption_values=consumption_values,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/plant/rmc/dispatch", methods=["GET", "POST"])
@login_required
def plant_rmc_dispatch():
    db = get_db()
    _prepare_plant_db(db)
    search = request.args.get("q", "")
    plant_filter = request.args.get("plant_id", type=int)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_rmc_dispatch(db, int(rid))
                db.commit()
                flash("RMC dispatch deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("plant_rmc_dispatch", plant_id=plant_filter))
        try:
            save_rmc_dispatch(
                db, request.form, session.get("username", ""), int(rid) if rid else None
            )
            db.commit()
            flash("RMC dispatch saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("plant_rmc_dispatch", plant_id=plant_filter))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_rmc_dispatch(db, view_id) if view_id else None
    edit_record = get_rmc_dispatch(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "plant_rmc_dispatch.html",
        rows=list_rmc_dispatch(db, plant_filter, search),
        stock_rows=[s for s in list_plant_stock(db, plant_filter) if (s.get("material_type") or "").startswith("RMC:")],
        search=search,
        plant_filter=plant_filter,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        plants=list_active_plants(db, "Concrete/RMC"),
        projects=_plant_projects(),
        vehicles=_plant_fleet_vehicles(db),
        grades=RMC_GRADES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/plant/rmc/dispatch/<int:dispatch_id>/print")
@login_required
def plant_rmc_dispatch_print(dispatch_id):
    db = get_db()
    _prepare_plant_db(db)
    record = get_rmc_dispatch(db, dispatch_id)
    if not record:
        flash("Dispatch not found.")
        return redirect(url_for("plant_rmc_dispatch"))
    _prepare_corporate_template_db(db)
    ctx = _build_corporate_report_context(
        db,
        "concrete_plant_production",
        document_number=record.get("dispatch_number") or "",
        project_name=record.get("project_name") or "",
        project_id=str(record.get("project_id") or ""),
        prepared_by=session.get("username", ""),
        report_date=record.get("dispatch_date"),
        back_url=url_for("plant_rmc_dispatch", view=record["id"]),
        page_orientation="portrait",
    )
    return render_template(
        "plant_rmc_dispatch_print.html",
        record=record,
        ctx=ctx,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        autoprint=request.args.get("print") == "1",
    )


@app.route("/plant/wetmix/production", methods=["GET", "POST"])
@login_required
def plant_wetmix_production():
    db = get_db()
    _prepare_plant_db(db)
    search = request.args.get("q", "")
    plant_filter = request.args.get("plant_id", type=int)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_wetmix_production(db, int(rid))
                db.commit()
                flash("Wet mix production deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("plant_wetmix_production", plant_id=plant_filter))
        try:
            save_wetmix_production(
                db, request.form, session.get("username", ""), int(rid) if rid else None
            )
            db.commit()
            flash("Wet mix production saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("plant_wetmix_production", plant_id=plant_filter))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_wetmix_production(db, view_id) if view_id else None
    edit_record = get_wetmix_production(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    consumption_values = {}
    if edit_record and edit_record.get("consumption"):
        for item in edit_record["consumption"]:
            consumption_values[item.get("material", "")] = item.get("qty", "")
    return render_template(
        "plant_wetmix_production.html",
        rows=list_wetmix_production(db, plant_filter, search),
        stock_rows=[s for s in list_plant_stock(db, plant_filter) if (s.get("material_type") or "").startswith("WETMIX:")],
        search=search,
        plant_filter=plant_filter,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        plants=list_active_plants(db, "Wet Mix"),
        consumption_values=consumption_values,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/plant/precast/production", methods=["GET", "POST"])
@login_required
def plant_precast_production():
    db = get_db()
    _prepare_plant_db(db)
    search = request.args.get("q", "")
    plant_filter = request.args.get("plant_id", type=int)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_precast_production(db, int(rid))
                db.commit()
                flash("Precast production deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("plant_precast_production", plant_id=plant_filter))
        try:
            save_precast_production(
                db, request.form, session.get("username", ""), int(rid) if rid else None
            )
            db.commit()
            flash("Precast production saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("plant_precast_production", plant_id=plant_filter))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_precast_production(db, view_id) if view_id else None
    edit_record = get_precast_production(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "plant_precast_production.html",
        rows=list_precast_production(db, plant_filter, search),
        stock_rows=[s for s in list_plant_stock(db, plant_filter) if (s.get("material_type") or "").startswith("PRECAST:")],
        search=search,
        plant_filter=plant_filter,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        plants=list_active_plants(db, "Precast Yard"),
        product_types=PRECAST_PRODUCT_TYPES,
        precast_statuses=PRECAST_STATUSES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/plant/precast-yard", methods=["GET"])
@login_required
def precast_yard():
    db = get_db()
    _prepare_precast_db(db)
    try:
        stats = precast_yard_dashboard_stats(db)
        yards = list_precast_yards(db)
    except Exception:
        app.logger.exception("Precast yard dashboard failed")
        stats = precast_yard_dashboard_stats(db)
        yards = []
    return render_template(
        "precast_yard.html",
        stats=stats,
        yards=yards,
    )


@app.route("/plant/precast-yard/yards", methods=["GET", "POST"])
@login_required
def precast_yard_yards():
    db = get_db()
    _prepare_precast_db(db)
    search = request.args.get("q", "")
    status_filter = request.args.get("status", "")
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_precast_yard(db, int(rid))
                db.commit()
                flash("Precast yard deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("precast_yard_yards"))
        try:
            save_precast_yard(
                db, request.form, session.get("username", ""), int(rid) if rid else None
            )
            db.commit()
            flash("Precast yard saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("precast_yard_yards"))
    edit_id = request.args.get("edit", type=int)
    edit_record = get_precast_yard(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "precast_yard_yards.html",
        yards=list_precast_yards(db, search, status_filter),
        search=search,
        status_filter=status_filter,
        edit_record=edit_record,
        show_form=show_form,
        plants=list_active_plants(db, "Precast Yard"),
        yard_statuses=PRECAST_YARD_STATUSES,
    )


@app.route("/plant/precast/dispatch", methods=["GET", "POST"])
@login_required
def plant_precast_dispatch():
    db = get_db()
    _prepare_plant_db(db)
    search = request.args.get("q", "")
    plant_filter = request.args.get("plant_id", type=int)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_precast_dispatch(db, int(rid))
                db.commit()
                flash("Precast dispatch deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("plant_precast_dispatch", plant_id=plant_filter))
        try:
            save_precast_dispatch(
                db, request.form, session.get("username", ""), int(rid) if rid else None
            )
            db.commit()
            flash("Precast dispatch saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("plant_precast_dispatch", plant_id=plant_filter))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_precast_dispatch(db, view_id) if view_id else None
    edit_record = get_precast_dispatch(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "plant_precast_dispatch.html",
        rows=list_precast_dispatch(db, plant_filter, search),
        stock_rows=[s for s in list_plant_stock(db, plant_filter) if (s.get("material_type") or "").startswith("PRECAST:")],
        search=search,
        plant_filter=plant_filter,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        plants=list_active_plants(db, "Precast Yard"),
        projects=_plant_projects(),
        vehicles=_plant_fleet_vehicles(db),
        product_types=PRECAST_PRODUCT_TYPES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/plant/crusher/production", methods=["GET", "POST"])
@login_required
def plant_crusher_production():
    db = get_db()
    _prepare_plant_db(db)
    search = request.args.get("q", "")
    plant_filter = request.args.get("plant_id", type=int)
    plants = list_crusher_msand_plants(db)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_crusher_production(db, int(rid))
                db.commit()
                flash("Crusher/M-Sand production deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("plant_crusher_production", plant_id=plant_filter))
        try:
            save_crusher_production(
                db, request.form, session.get("username", ""), int(rid) if rid else None
            )
            db.commit()
            flash("Production entry saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("plant_crusher_production", plant_id=plant_filter))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_crusher_production(db, view_id) if view_id else None
    edit_record = get_crusher_production(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    consumption_values = {}
    if edit_record and edit_record.get("consumption"):
        for item in edit_record["consumption"]:
            consumption_values[item.get("material", "")] = item.get("qty", "")
    selected_plant_type = (edit_record or view_record or {}).get("plant_type") or "Crusher"
    output_grades = MSAND_GRADES if selected_plant_type == "M-Sand" else CRUSHER_OUTPUT_GRADES
    return render_template(
        "plant_crusher_production.html",
        rows=list_crusher_production(db, plant_filter, search),
        search=search,
        plant_filter=plant_filter,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        plants=plants,
        output_grades=output_grades,
        crusher_grades=CRUSHER_OUTPUT_GRADES,
        msand_grades=MSAND_GRADES,
        shifts=PLANT_SHIFTS,
        consumption_values=consumption_values,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/quality-control", methods=["GET", "POST"])
@app.route("/qc-master", methods=["GET", "POST"])
@login_required
def qc_master():
    db = get_db()
    _prepare_qc_db(db)
    search = request.args.get("q", "")
    material_filter = request.args.get("material", "")
    status_filter = request.args.get("status", "")
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_qc_test(db, int(rid))
                db.commit()
                flash("QC test deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("qc_master"))
        try:
            save_qc_test(db, request.form, session.get("username", ""), int(rid) if rid else None)
            db.commit()
            flash("QC test saved.")
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save QC test.")
        return redirect(url_for("qc_master"))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_qc_test(db, view_id) if view_id else None
    edit_record = get_qc_test(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "qc_master.html",
        rows=list_qc_tests(db, search, material_filter, status_filter),
        search=search,
        material_filter=material_filter,
        status_filter=status_filter,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        applicable_materials=APPLICABLE_MATERIALS,
        test_frequencies=TEST_FREQUENCIES,
        test_statuses=QC_TEST_STATUSES,
    )


@app.route("/plant/qc", methods=["GET", "POST"])
@login_required
def plant_qc():
    db = get_db()
    _prepare_plant_db(db)
    search = request.args.get("q", "")
    plant_filter = request.args.get("plant_id", type=int)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_plant_qc(db, int(rid))
                db.commit()
                flash("QC record deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("plant_qc", plant_id=plant_filter))
        try:
            save_plant_qc(db, request.form, session.get("username", ""), int(rid) if rid else None)
            db.commit()
            flash("QC record saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("plant_qc", plant_id=plant_filter))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_plant_qc(db, view_id) if view_id else None
    edit_record = get_plant_qc(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "plant_qc.html",
        rows=list_plant_qc(db, plant_filter, search),
        search=search,
        plant_filter=plant_filter,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        plants=list_active_plants(db),
        source_modules=QC_SOURCE_MODULES,
        test_types=QC_TEST_TYPES,
        pass_fail_options=QC_PASS_FAIL,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/plant/maintenance", methods=["GET", "POST"])
@login_required
def plant_maintenance():
    db = get_db()
    _prepare_plant_db(db)
    search = request.args.get("q", "")
    plant_filter = request.args.get("plant_id", type=int)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_maintenance_job(db, int(rid))
                db.commit()
                flash("Maintenance job deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("plant_maintenance", plant_id=plant_filter))
        try:
            save_maintenance_job(
                db, request.form, session.get("username", ""), int(rid) if rid else None
            )
            db.commit()
            flash("Maintenance job saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("plant_maintenance", plant_id=plant_filter))
    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = get_maintenance_job(db, view_id) if view_id else None
    edit_record = get_maintenance_job(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    return render_template(
        "plant_maintenance.html",
        rows=list_maintenance_jobs(db, plant_filter, search),
        search=search,
        plant_filter=plant_filter,
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        plants=list_active_plants(db),
        job_types=MAINTENANCE_JOB_TYPES,
        job_statuses=MAINTENANCE_STATUSES,
        default_date=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/plant/costing")
@login_required
def plant_costing():
    db = get_db()
    _prepare_plant_db(db)
    today = datetime.now().strftime("%Y-%m-%d")
    month_start = datetime.now().strftime("%Y-%m-01")
    date_from = request.args.get("from", month_start)
    date_to = request.args.get("to", today)
    plant_filter = request.args.get("plant_id", type=int)
    summary = plant_costing_summary(db, date_from, date_to, plant_filter)
    return render_template(
        "plant_costing.html",
        summary=summary,
        date_from=date_from,
        date_to=date_to,
        plant_filter=plant_filter,
        plants=list_active_plants(db),
    )


@app.route("/plant/360")
@login_required
def plant_360():
    db = get_db()
    _prepare_plant_db(db)
    plant_id = request.args.get("plant_id", type=int)
    data = get_plant_360(db, plant_id) if plant_id else None
    return render_template(
        "plant_360.html",
        plants=list_plants(db),
        plant_id=plant_id,
        data=data,
    )


# --- Client Billing (Phase B) — read-only DPR/BOQ integration ---

@app.route("/client-billing")
@login_required
def client_billing_register():
    db = get_db()
    _prepare_client_billing_db(db)
    search = request.args.get("q", "")
    project_filter = request.args.get("project_id", type=int)
    return render_template(
        "client_billing_register.html",
        rows=list_client_bills(db, search, project_filter),
        search=search,
        project_filter=project_filter,
        projects=list_projects_for_billing(db),
    )


@app.route("/client-billing/form", methods=["GET", "POST"])
@login_required
def client_billing_form():
    db = get_db()
    _prepare_client_billing_db(db)
    module_id, table, endpoint = CLIENT_BILLING_MODULE_ID, CLIENT_BILLING_TABLE, "client_billing_form"

    if request.method == "POST":
        action = request.form.get("form_action", "save")
        if action == "mark_paid":
            bill_id = request.form.get("bill_id", type=int)
            if bill_id:
                try:
                    mark_bill_paid(db, bill_id)
                    db.commit()
                    flash("Bill marked as paid.")
                except ValueError as exc:
                    flash(str(exc))
            return redirect(url_for(endpoint, view=bill_id))
        if action == "generate_gst":
            bill_id = request.form.get("bill_id", type=int)
            if bill_id:
                try:
                    gst_id = create_gst_bill_from_ra(db, bill_id, session.get("username", ""))
                    db.commit()
                    flash("GST bill draft created from approved RA bill.")
                    return redirect(url_for("client_billing_gst_form", edit=gst_id))
                except ValueError as exc:
                    flash(str(exc))
            return redirect(url_for(endpoint, view=bill_id))

        ctx = _module_edit_context(module_id, table, endpoint)
        if ctx[0] == "redirect":
            return redirect(ctx[1])
        record_id, edit_role = ctx
        try:
            if record_id:
                new_id = save_client_bill(db, request.form, session.get("username", ""), record_id)
                upload = request.files.get("attachment")
                if upload and upload.filename:
                    _, err = _validate_billing_upload(upload)
                    if err:
                        raise ValueError(err)
                    stored = save_file(upload, BILLING_DOCS_DIR)
                    if stored:
                        save_bill_attachment(
                            db, new_id, request.form.get("attachment_type") or "Supporting Document",
                            stored, upload.filename, session.get("username", ""),
                        )
                _complete_module_save(db, module_id, table, new_id, edit_role)
            else:
                new_id = save_client_bill(db, request.form, session.get("username", ""))
                upload = request.files.get("attachment")
                if upload and upload.filename:
                    _, err = _validate_billing_upload(upload)
                    if err:
                        raise ValueError(err)
                    stored = save_file(upload, BILLING_DOCS_DIR)
                    if stored:
                        save_bill_attachment(
                            db, new_id, request.form.get("attachment_type") or "Supporting Document",
                            stored, upload.filename, session.get("username", ""),
                        )
                create_approval_request(
                    db, module_id, new_id, table,
                    session.get("username", ""), session.get("user_id"),
                )
                db.commit()
                flash("Client bill saved. Status: Pending Checker.")
            return redirect(url_for(endpoint, view=new_id))
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save client bill.")
            return redirect(request.referrer or url_for(endpoint, new=1))

    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = edit_record = None
    wf_ctx = {}
    if view_id:
        view_record = get_client_bill(db, view_id)
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], table, view_record["approval_status"]
            )
        else:
            flash("Client bill not found.")
            return redirect(url_for("client_billing_register"))
    elif edit_id:
        edit_record = get_client_bill(db, edit_id)
        if edit_record:
            edit_role = get_edit_role_for_user(
                db, session.get("user_id"), module_id,
                edit_record["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_id))
            wf_ctx = {"edit_role": edit_role}

    show_form = bool(request.args.get("new")) or edit_record
    today = datetime.now().strftime("%Y-%m-%d")
    gst_bills = list_gst_bills_for_ra(db, view_id) if view_id else []
    suggested_tax_type = suggest_gst_tax_type(db, view_id) if view_id else "CGST_SGST"
    return render_template(
        "client_billing_form.html",
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        wf_ctx=wf_ctx,
        history=wf_ctx.get("history"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
        edit_role=wf_ctx.get("edit_role"),
        projects=list_projects_for_billing(db),
        clients=list_clients_for_billing(db),
        extra_types=EXTRA_LINE_TYPES,
        attachment_types=ATTACHMENT_TYPES,
        form_defaults={"bill_date": today, "period_from": today, "period_to": today},
        gst_bills=gst_bills,
        gst_tax_types=GST_TAX_TYPES,
        suggested_tax_type=suggested_tax_type,
    )


@app.route("/client-billing/import-dpr", methods=["POST"])
@login_required
def client_billing_import_dpr():
    db = get_db()
    _prepare_client_billing_db(db)
    payload = request.get_json(silent=True) or {}
    project_id = payload.get("project_id") or request.form.get("project_id", type=int)
    period_from = (payload.get("period_from") or request.form.get("period_from") or "").strip()
    period_to = (payload.get("period_to") or request.form.get("period_to") or "").strip()
    bill_id = payload.get("bill_id") or request.form.get("bill_id", type=int)
    if not project_id:
        return jsonify({"ok": False, "error": "Project is required."})
    try:
        payload_data = import_dpr_for_billing(
            db, int(project_id), period_from, period_to, bill_id
        )
        return jsonify({
            "ok": True,
            "lines": payload_data["lines"],
            "measurements": payload_data["measurements"],
        })
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)})


@app.route("/client-billing/gst", methods=["GET", "POST"])
@login_required
def client_billing_gst_form():
    db = get_db()
    _prepare_client_billing_db(db)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        edit_id = request.form.get("gst_bill_id", type=int)
        try:
            gst_id = save_client_gst_bill(
                db, request.form, session.get("username", ""), edit_id
            )
            db.commit()
            flash("GST bill finalized." if action == "finalize" else "GST bill saved.")
            return redirect(url_for("client_billing_gst_form", view=gst_id))
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.referrer or url_for("client_billing_register"))

    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    ra_bill_id = request.args.get("ra_bill", type=int)
    view_record = edit_record = None
    if view_id:
        view_record = get_client_gst_bill(db, view_id)
    elif edit_id:
        edit_record = get_client_gst_bill(db, edit_id)
    elif ra_bill_id:
        try:
            defaults = build_gst_bill_defaults_from_ra(db, ra_bill_id)
            edit_record = defaults
            edit_record["lines"] = defaults.get("lines") or []
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("client_billing_form", view=ra_bill_id))

    show_form = bool(edit_record) or bool(ra_bill_id)
    return render_template(
        "client_billing_gst_form.html",
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        gst_tax_types=GST_TAX_TYPES,
        form_defaults={"invoice_date": datetime.now().strftime("%Y-%m-%d"), "gst_percent": 18},
    )


@app.route("/client-billing/gst/print/<int:gst_bill_id>")
@login_required
def client_billing_gst_print(gst_bill_id):
    db = get_db()
    _prepare_client_billing_db(db)
    bill = get_client_gst_bill(db, gst_bill_id)
    if not bill:
        flash("GST bill not found.")
        return redirect(url_for("client_billing_register"))
    _prepare_corporate_template_db(db)
    ctx = _build_corporate_report_context(
        db,
        "client_invoice",
        document_number=bill.get("gst_bill_number") or "",
        project_name=bill.get("project_name") or "",
        project_id=str(bill.get("project_id") or ""),
        prepared_by=session.get("username", ""),
        report_date=bill.get("invoice_date"),
        back_url=url_for("client_billing_gst_form", view=bill["id"]),
        page_orientation="portrait",
    )
    return render_template(
        "client_billing_gst_print.html",
        bill=bill,
        bank=get_company_bank_for_print(db),
        ctx=ctx,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        autoprint=request.args.get("print") == "1",
    )


@app.route("/client-billing/print/<int:bill_id>")
@login_required
def client_billing_print(bill_id):
    db = get_db()
    _prepare_client_billing_db(db)
    bill = get_client_bill(db, bill_id)
    if not bill:
        flash("Client bill not found.")
        return redirect(url_for("client_billing_register"))
    bill = enrich_bill_for_print(bill)
    _prepare_corporate_template_db(db)
    ctx = _build_corporate_report_context(
        db,
        "client_ra_bill",
        document_number=bill.get("bill_number") or bill.get("ra_number") or "",
        project_name=bill.get("project_name") or "",
        project_id=str(bill.get("project_id") or ""),
        prepared_by=session.get("username", ""),
        report_date=bill.get("bill_date"),
        back_url=url_for("client_billing_form", view=bill["id"]),
        page_orientation="portrait",
    )
    return render_template(
        "client_billing_print.html",
        bill=bill,
        bank=get_company_bank_for_print(db),
        ctx=ctx,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        autoprint=request.args.get("print") == "1",
    )


@app.route("/client-billing/reports")
@login_required
def client_billing_reports():
    db = get_db()
    _prepare_client_billing_db(db)
    report_type = request.args.get("report", "register")
    project_filter = request.args.get("project_id", type=int)
    client_filter = request.args.get("client_id", type=int)
    report_tabs = [
        {"key": "register", "label": "Bill Register"},
        {"key": "pending", "label": "Pending Bills"},
        {"key": "certified", "label": "Certified Bills"},
        {"key": "paid", "label": "Paid Bills"},
        {"key": "outstanding", "label": "Outstanding"},
        {"key": "ledger", "label": "Client Ledger"},
    ]
    ledger_rows = []
    rows = []
    if report_type == "ledger":
        ledger_rows = client_ledger_rows(db, client_filter, project_filter)
    else:
        rows = list_billing_reports(db, report_type, project_filter, client_filter)
    return render_template(
        "client_billing_reports.html",
        report_type=report_type,
        report_tabs=report_tabs,
        rows=rows,
        ledger_rows=ledger_rows,
        project_filter=project_filter,
        client_filter=client_filter,
        projects=list_projects_for_billing(db),
        clients=list_clients_for_billing(db),
    )


@app.route("/client-billing/attachment/<int:attachment_id>")
@login_required
def client_billing_attachment(attachment_id):
    db = get_db()
    _prepare_client_billing_db(db)
    row = db.execute(
        "SELECT stored_filename, original_filename FROM client_bill_attachments WHERE id=?",
        (attachment_id,),
    ).fetchone()
    if not row:
        abort(404)
    path = os.path.join(BILLING_DOCS_DIR, row["stored_filename"])
    if not os.path.isfile(path):
        abort(404)
    ext = os.path.splitext(row["stored_filename"] or "")[1].lower()
    mimetype = "application/pdf" if ext == ".pdf" else None
    return send_file(
        path,
        as_attachment=request.args.get("download") == "1",
        download_name=row["original_filename"] or row["stored_filename"],
        mimetype=mimetype,
    )


# --- Project Photo Management (Phase C) — separate from DPR/BOQ ---


def _project_photos_filters():
    return {
        "search": request.args.get("q", ""),
        "project_filter": request.args.get("project_id", type=int),
        "category_filter": request.args.get("category", ""),
        "date_from": request.args.get("date_from", ""),
        "date_to": request.args.get("date_to", ""),
        "uploaded_by_filter": request.args.get("uploaded_by", ""),
    }


@app.route("/project-photos", methods=["GET", "POST"])
@login_required
def project_photos_register():
    db = get_db()
    _prepare_project_photos_db(db)
    filters = _project_photos_filters()

    if request.method == "POST":
        action = request.form.get("form_action", "upload")
        if action == "delete":
            photo_id = request.form.get("photo_id", type=int)
            if photo_id:
                try:
                    delete_project_photo(db, photo_id, PROJECT_PHOTOS_DIR)
                    db.commit()
                    flash("Photo deleted.")
                except ValueError as exc:
                    flash(str(exc))
            return redirect(url_for("project_photos_register", **{k: v for k, v in {
                "q": filters["search"],
                "project_id": filters["project_filter"],
                "category": filters["category_filter"],
                "date_from": filters["date_from"],
                "date_to": filters["date_to"],
                "uploaded_by": filters["uploaded_by_filter"],
            }.items() if v}))

        upload = request.files.get("photo_file")
        ext, file_kind, err = validate_photo_upload(upload, required=True)
        if err:
            flash(err)
            return redirect(url_for("project_photos_register", new=1))
        stored = save_file(upload, PROJECT_PHOTOS_DIR)
        if not stored:
            flash("Unable to save uploaded file.")
            return redirect(url_for("project_photos_register", new=1))
        try:
            save_project_photo(
                db,
                request.form,
                stored,
                upload.filename,
                file_kind or "other",
                session.get("username", ""),
            )
            db.commit()
            flash("Photo uploaded.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("project_photos_register", project_id=request.form.get("project_id")))

    photos = search_project_photos(
        db,
        search=filters["search"],
        project_id=filters["project_filter"],
        category=filters["category_filter"],
        date_from=filters["date_from"],
        date_to=filters["date_to"],
        uploaded_by=filters["uploaded_by_filter"],
    )
    stats = photo_register_stats(db, filters["project_filter"])
    return render_template(
        "project_photos_register.html",
        photos=photos,
        projects=list_projects_for_photos(db),
        categories=PHOTO_CATEGORIES,
        stats=stats,
        show_upload=bool(request.args.get("new")),
        default_date=datetime.now().strftime("%Y-%m-%d"),
        **filters,
    )


@app.route("/project-photos/timeline")
@login_required
def project_photos_timeline():
    db = get_db()
    _prepare_project_photos_db(db)
    filters = _project_photos_filters()
    timeline = list_photos_timeline(
        db,
        search=filters["search"],
        project_id=filters["project_filter"],
        category=filters["category_filter"],
        date_from=filters["date_from"],
        date_to=filters["date_to"],
        uploaded_by=filters["uploaded_by_filter"],
    )
    return render_template(
        "project_photos_timeline.html",
        timeline=timeline,
        projects=list_projects_for_photos(db),
        categories=PHOTO_CATEGORIES,
        **filters,
    )


@app.route("/project-photos/reports")
@login_required
def project_photos_reports():
    db = get_db()
    _prepare_project_photos_db(db)
    return render_template(
        "project_photos_reports.html",
        projects=list_projects_for_photos(db),
        categories=PHOTO_CATEGORIES,
        report_types=PHOTO_REPORT_TYPES,
        default_month=datetime.now().strftime("%Y-%m"),
    )


@app.route("/project-photos/report/print")
@login_required
def project_photos_report_print():
    db = get_db()
    _prepare_project_photos_db(db)
    report_type = request.args.get("report_type", "monthly_progress")
    project_id = request.args.get("project_id", type=int)
    try:
        title, photos, meta = photos_for_report(
            db,
            report_type=report_type,
            project_id=project_id,
            year_month=request.args.get("year_month", ""),
            category=request.args.get("category", ""),
            date_from=request.args.get("date_from", ""),
            date_to=request.args.get("date_to", ""),
        )
    except ValueError as exc:
        flash(str(exc))
        return redirect(url_for("project_photos_reports"))
    return render_template(
        "project_photos_report.html",
        title=title,
        photos=photos,
        meta=meta,
    )


@app.route("/project-photos/file/<int:photo_id>")
@login_required
def project_photos_file(photo_id):
    db = get_db()
    _prepare_project_photos_db(db)
    row = get_project_photo(db, photo_id)
    if not row:
        abort(404)
    path = os.path.join(PROJECT_PHOTOS_DIR, row["file_path"])
    if not os.path.isfile(path):
        abort(404)
    ext = os.path.splitext(row["file_path"])[1].lower()
    mimetype = DPR_MIME_TYPES.get(ext) if ext in DPR_MIME_TYPES else None
    return send_file(
        path,
        mimetype=mimetype,
        as_attachment=request.args.get("download") == "1",
        download_name=row.get("original_filename") or row["file_path"],
    )


# --- Employee Monthly Timesheets ---


@app.route("/timesheets")
@login_required
def employee_timesheets():
    db = get_db()
    _prepare_employee_timesheet_db(db)
    year_month = request.args.get("year_month", "")
    if year_month and len(year_month) == 7:
        year_month = f"{year_month[:4]}-{year_month[5:7]}"
    return render_template(
        "employee_timesheets.html",
        rows=list_monthly_timesheets(
            db,
            search=request.args.get("q", ""),
            year_month=year_month,
            status=request.args.get("status", ""),
        ),
        search=request.args.get("q", ""),
        year_month_filter=request.args.get("year_month", ""),
        status_filter=request.args.get("status", ""),
        statuses=TIMESHEET_STATUSES,
    )


@app.route("/timesheets/form", methods=["GET", "POST"])
@login_required
def employee_timesheets_form():
    db = get_db()
    _prepare_employee_timesheet_db(db)
    if request.method == "POST":
        edit_id = request.form.get("timesheet_id", type=int)
        year_month_saved = (request.form.get("year_month") or "").strip()
        project_id_saved = (request.form.get("project_id") or "").strip()
        try:
            ts_id = save_monthly_timesheet(
                db, request.form, session.get("username", ""), edit_id
            )
            db.commit()
            flash("Monthly timesheet saved.")
            if edit_id:
                return redirect(url_for("employee_timesheets_form", view=ts_id))
            redirect_kwargs: dict = {"new": 1}
            if year_month_saved:
                redirect_kwargs["year_month"] = year_month_saved
            if project_id_saved:
                redirect_kwargs["project_id"] = project_id_saved
            return redirect(url_for("employee_timesheets_form", **redirect_kwargs))
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.referrer or url_for("employee_timesheets_form", new=1))
        except sqlite3.OperationalError as exc:
            app.logger.exception("Monthly timesheet save failed")
            flash(f"Could not save timesheet — database schema needs an update. ({exc})")
            return redirect(request.referrer or url_for("employee_timesheets_form", new=1))

    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = edit_record = None
    day_rows: list[dict] = []
    if view_id:
        view_record = get_monthly_timesheet(db, view_id)
    elif edit_id:
        edit_record = get_monthly_timesheet(db, edit_id)
        if edit_record:
            day_rows = edit_record.get("days") or []

    show_form = bool(request.args.get("new")) or edit_record
    if show_form and not day_rows:
        ym = request.args.get("year_month") or datetime.now().strftime("%Y-%m")
        year, month = parse_year_month(ym)
        total = days_in_month(year, month)
        day_rows = [{"day_num": d} for d in range(1, total + 1)]

    today_ym = datetime.now().strftime("%Y-%m")
    preserve_ym = request.args.get("year_month", "").strip()
    preserve_project_id = request.args.get("project_id", type=int)
    return render_template(
        "employee_timesheet_form.html",
        view_record=view_record,
        edit_record=edit_record,
        show_form=show_form,
        day_rows=day_rows,
        staff_list=list_staff_for_timesheet(db),
        workers_list=list_workers_for_timesheet(db),
        projects=list_projects_for_timesheet(db),
        form_defaults={
            "year_month": preserve_ym or today_ym,
            "project_id": preserve_project_id,
        },
    )


@app.route("/timesheets/submit/<int:timesheet_id>", methods=["POST"])
@login_required
def employee_timesheets_submit(timesheet_id):
    db = get_db()
    _prepare_employee_timesheet_db(db)
    module_id, table = "employee_timesheet", "employee_monthly_timesheets"
    try:
        submit_timesheet(db, timesheet_id, session.get("username", ""))
        if not get_approval_request(db, module_id, timesheet_id, table):
            create_approval_request(
                db,
                module_id,
                timesheet_id,
                table,
                session.get("username", ""),
                session.get("user_id"),
            )
        db.commit()
        flash("Timesheet submitted for approval.")
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for("employee_timesheets_form", view=timesheet_id))


@app.route("/timesheets/print/<int:timesheet_id>")
@login_required
def employee_timesheets_print(timesheet_id):
    db = get_db()
    _prepare_employee_timesheet_db(db)
    sheet = get_monthly_timesheet(db, timesheet_id)
    if not sheet:
        flash("Timesheet not found.")
        return redirect(url_for("employee_timesheets"))
    _prepare_corporate_template_db(db)
    ctx = _build_corporate_report_context(
        db,
        "timesheet",
        document_number=sheet.get("timesheet_ref") or str(timesheet_id),
        project_name=sheet.get("primary_project_name") or "",
        prepared_by=session.get("username", ""),
        report_date=sheet.get("month_label"),
        back_url=url_for("employee_timesheets_form", view=sheet["id"]),
        page_orientation="landscape",
    )
    return render_template(
        "employee_timesheet_print.html",
        sheet=sheet,
        ctx=ctx,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        autoprint=request.args.get("print") == "1",
    )


# --- BBS Reports ---


@app.route("/bbs")
@login_required
def bbs_register():
    db = get_db()
    _prepare_bbs_db(db)
    return render_template(
        "bbs_register.html",
        rows=list_bbs_reports(db, request.args.get("q", ""), request.args.get("project_id", type=int)),
        search=request.args.get("q", ""),
        project_filter=request.args.get("project_id", type=int),
        projects=list_projects_for_bbs(db),
    )


@app.route("/bbs/form", methods=["GET", "POST"])
@login_required
def bbs_form():
    db = get_db()
    _prepare_bbs_db(db)
    if request.method == "POST":
        edit_id = request.form.get("bbs_id", type=int)
        try:
            bbs_id = save_bbs_report(db, request.form, session.get("username", ""), edit_id)
            db.commit()
            flash("BBS report saved.")
            return redirect(url_for("bbs_form", view=bbs_id))
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.referrer or url_for("bbs_form", new=1))

    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = edit_record = None
    if view_id:
        view_record = get_bbs_report(db, view_id)
    elif edit_id:
        edit_record = get_bbs_report(db, edit_id)

    today = datetime.now().strftime("%Y-%m-%d")
    return render_template(
        "bbs_form.html",
        view_record=view_record,
        edit_record=edit_record,
        show_form=bool(request.args.get("new")) or edit_record,
        projects=list_projects_for_bbs(db),
        diameters=DIAMETERS,
        form_defaults={"report_date": today, "measurement_from": today, "measurement_to": today, "lines": []},
    )


@app.route("/bbs/print/<int:bbs_id>")
@login_required
def bbs_print(bbs_id):
    db = get_db()
    _prepare_bbs_db(db)
    _prepare_corporate_template_db(db)
    report = get_bbs_report(db, bbs_id)
    if not report:
        flash("BBS report not found.")
        return redirect(url_for("bbs_register"))
    ctx = _build_corporate_report_context(
        db,
        "bbs_report",
        document_number=report.get("ref_no") or "",
        project_name=report.get("project_name") or "",
        project_id=str(report.get("project_id") or ""),
        prepared_by=report.get("prepared_by") or session.get("username", ""),
        report_date=report.get("report_date"),
        back_url=url_for("bbs_form", view=report["id"]),
        page_orientation="landscape",
    )
    return render_template(
        "bbs_print.html",
        report=report,
        diameters=DIAMETERS,
        ctx=ctx,
        autoprint=request.args.get("print") == "1",
    )


# --- Sub-contractor Billing ---


@app.route("/subcontract-payments", methods=["GET", "POST"])
@login_required
def subcontract_payments():
    db = get_db()
    _prepare_subcontract_payments_db(db)
    module_id = SUB_PAYMENT_MODULE_ID
    wo_table = SUB_PAYMENT_WO_TABLE
    endpoint = "subcontract_payments"
    projects = query_db("SELECT id, project_name FROM projects ORDER BY project_name")
    subcontractors = list_subcontractors_for_payments(db)

    if request.method == "POST":
        action = request.form.get("form_action", "save_work_order")
        try:
            if action == "save_work_order":
                record_id, edit_role = None, None
                if request.form.get("record_id", "").strip():
                    ctx = _module_edit_context(module_id, wo_table, endpoint)
                    if ctx[0] == "redirect":
                        return redirect(ctx[1])
                    record_id, edit_role = ctx
                saved_id = save_work_order(
                    db, request.form, session.get("username", ""), record_id
                )
                if record_id:
                    _complete_module_save(db, module_id, wo_table, saved_id, edit_role)
                else:
                    create_approval_request(
                        db, module_id, saved_id, wo_table,
                        session.get("username", ""), session.get("user_id"),
                    )
                    db.commit()
                    flash("Work order saved. Status: Pending Checker.")
                return redirect(url_for(endpoint, view=saved_id))
            if action == "save_payment":
                pay_id = request.form.get("payment_id", type=int)
                saved_pay_id = save_payment_entry(
                    db, request.form, session.get("username", ""), pay_id
                )
                if not pay_id:
                    create_approval_request(
                        db, module_id, saved_pay_id, SUB_PAYMENT_ENTRY_TABLE,
                        session.get("username", ""), session.get("user_id"),
                    )
                db.commit()
                flash("Payment entry saved. Status: Pending Checker.")
                wo_id = request.form.get("work_order_id", type=int)
                return redirect(url_for(endpoint, view=wo_id))
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.referrer or url_for(endpoint))

    view_id = request.args.get("view", type=int)
    edit_wo_id = request.args.get("edit_wo", type=int)
    view_record = edit_wo = None
    wf_ctx = {}
    if view_id:
        view_record = get_work_order(db, view_id)
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id, view_record["id"], wo_table, view_record["approval_status"]
            )
    elif edit_wo_id:
        edit_wo = get_work_order(db, edit_wo_id)
        if edit_wo:
            edit_role = get_edit_role_for_user(
                db, session.get("user_id"), module_id,
                edit_wo["approval_status"], is_admin_user(),
            )
            if not edit_role:
                flash("This work order is locked and cannot be edited.")
                return redirect(url_for(endpoint, view=edit_wo_id))
            wf_ctx = {"edit_role": edit_role}

    search = request.args.get("q", "")
    return render_template(
        "subcontract_payments.html",
        ledger_rows=list_work_order_ledger(db, search),
        summary=ledger_summary(db),
        subcontractors=subcontractors,
        projects=projects,
        view_record=view_record,
        edit_wo=edit_wo,
        show_wo_form=bool(request.args.get("new_wo")) or edit_wo,
        show_pay_form=bool(request.args.get("new_pay")),
        prefill_wo_id=request.args.get("wo_id", type=int),
        search=search,
        default_date=datetime.now().strftime("%Y-%m-%d"),
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/sub-billing")
@login_required
def sub_billing_register():
    db = get_db()
    _prepare_sub_billing_db(db)
    return render_template(
        "sub_billing_register.html",
        rows=list_subcontractor_bills(
            db, request.args.get("q", ""), request.args.get("subcontractor_id", type=int)
        ),
        search=request.args.get("q", ""),
        sub_filter=request.args.get("subcontractor_id", type=int),
        subcontractors=list_subcontractors_for_billing(db),
    )


@app.route("/sub-billing/form", methods=["GET", "POST"])
@login_required
def sub_billing_form():
    db = get_db()
    _prepare_sub_billing_db(db)
    module_id = SUB_BILLING_MODULE_ID
    table = SUB_BILLING_TABLE
    wf_ctx = {}

    if request.method == "POST":
        edit_id = request.form.get("bill_id", type=int)
        edit_role = None
        if edit_id:
            existing = db.execute(
                f"SELECT approval_status FROM {table} WHERE id=?",
                (edit_id,),
            ).fetchone()
            if not existing:
                flash("Sub-contractor bill not found.")
                return redirect(url_for("sub_billing_register"))
            edit_role = get_edit_role_for_user(
                db,
                session.get("user_id"),
                module_id,
                existing["approval_status"],
                is_admin_user(),
            )
            if not edit_role:
                flash("This record is locked and cannot be edited.")
                return redirect(url_for("sub_billing_form", view=edit_id))
        try:
            bill_id = save_subcontractor_bill(
                db, request.form, session.get("username", ""), edit_id
            )
            if edit_id:
                _complete_module_save(db, module_id, table, bill_id, edit_role)
            else:
                create_approval_request(
                    db,
                    module_id,
                    bill_id,
                    table,
                    session.get("username", ""),
                    session.get("user_id"),
                )
                db.commit()
                flash("Sub-contractor bill saved. Status: Pending Checker.")
            return redirect(url_for("sub_billing_form", view=bill_id))
        except ValueError as exc:
            flash(str(exc))
            return redirect(request.referrer or url_for("sub_billing_form", new=1))

    view_id = request.args.get("view", type=int)
    edit_id = request.args.get("edit", type=int)
    view_record = edit_record = None
    if view_id:
        view_record = get_subcontractor_bill(db, view_id)
        if view_record:
            wf_ctx = _workflow_view_context(
                module_id,
                view_record["id"],
                table,
                view_record.get("approval_status"),
            )
    elif edit_id:
        edit_record = get_subcontractor_bill(db, edit_id)
        if edit_record:
            edit_role = get_edit_role_for_user(
                db,
                session.get("user_id"),
                module_id,
                edit_record.get("approval_status"),
                is_admin_user(),
            )
            wf_ctx = {"edit_role": edit_role}

    today = datetime.now().strftime("%Y-%m-%d")
    return render_template(
        "sub_billing_form.html",
        view_record=view_record,
        edit_record=edit_record,
        show_form=bool(request.args.get("new")) or edit_record,
        subcontractors=list_subcontractors_for_billing(db),
        default_declaration=DEFAULT_DECLARATION,
        form_defaults={"bill_date": today},
        history=wf_ctx.get("history"),
        edit_role=wf_ctx.get("edit_role"),
        can_reopen=wf_ctx.get("can_reopen", False),
        approval_id=wf_ctx.get("approval_id"),
    )


@app.route("/sub-billing/import-workers")
@login_required
def sub_billing_import_workers():
    db = get_db()
    _prepare_sub_billing_db(db)
    subcontractor_id = request.args.get("subcontractor_id", type=int)
    if not subcontractor_id:
        return jsonify({"ok": False, "error": "Sub-contractor is required."})
    lines = import_worker_lines_template(db, subcontractor_id)
    return jsonify({"ok": True, "lines": lines})


@app.route("/sub-billing/print/<int:bill_id>")
@login_required
def sub_billing_print(bill_id):
    db = get_db()
    _prepare_sub_billing_db(db)
    bill = get_subcontractor_bill(db, bill_id)
    if not bill:
        flash("Sub-contractor bill not found.")
        return redirect(url_for("sub_billing_register"))
    _prepare_corporate_template_db(db)
    ctx = _build_corporate_report_context(
        db,
        "subcontractor_bill",
        document_number=bill.get("bill_number") or str(bill_id),
        project_name=bill.get("project_name") or "",
        project_id=str(bill.get("project_id") or ""),
        prepared_by=session.get("username", ""),
        report_date=bill.get("period_to") or bill.get("period_from"),
        back_url=url_for("sub_billing_form", view=bill["id"]),
        page_orientation="portrait",
    )
    return render_template(
        "sub_billing_print.html",
        bill=bill,
        ctx=ctx,
        autoprint=request.args.get("print") == "1",
    )


@app.route("/sub-billing/abstract/<int:bill_id>")
@login_required
def sub_billing_abstract_print(bill_id):
    db = get_db()
    _prepare_sub_billing_db(db)
    bill = get_subcontractor_bill(db, bill_id)
    if not bill:
        flash("Sub-contractor bill not found.")
        return redirect(url_for("sub_billing_register"))
    if not bill.get("declaration_text"):
        bill["declaration_text"] = DEFAULT_DECLARATION
    return render_template(
        "sub_billing_abstract_print.html",
        bill=bill,
        default_declaration=DEFAULT_DECLARATION,
        autoprint=request.args.get("print") == "1",
    )


# --- Corporate DMS (Phase D) ---


def _corporate_dms_filters():
    return {
        "search": request.args.get("q", ""),
        "folder_filter": request.args.get("folder_id", type=int),
        "doc_type_filter": request.args.get("doc_type", ""),
        "expiry_status_filter": request.args.get("expiry_status", ""),
    }


@app.route("/settings/corporate-dms", methods=["GET", "POST"])
@admin_required
def corporate_dms():
    db = get_db()
    _prepare_corporate_dms_db(db)
    filters = _corporate_dms_filters()

    if request.method == "POST":
        action = request.form.get("form_action", "save_document")
        redirect_args = {k: v for k, v in {
            "folder_id": filters["folder_filter"],
            "q": filters["search"],
            "doc_type": filters["doc_type_filter"],
            "expiry_status": filters["expiry_status_filter"],
        }.items() if v}
        try:
            if action == "save_folder":
                save_folder(db, request.form)
                db.commit()
                flash("Folder saved.")
                return redirect(url_for("corporate_dms", **redirect_args))
            if action == "delete_document":
                doc_id = request.form.get("document_id", type=int)
                if doc_id:
                    delete_document(db, doc_id)
                    db.commit()
                    flash("Document deleted.")
                return redirect(url_for("corporate_dms", **redirect_args))
            if action == "save_document":
                doc_id = request.form.get("document_id", type=int)
                upload = request.files.get("document_file")
                stored = None
                original = None
                if upload and upload.filename:
                    _, err = validate_dms_upload(upload, required=not doc_id)
                    if err:
                        raise ValueError(err)
                    stored = save_file(upload, CORPORATE_DMS_DIR)
                    original = upload.filename
                elif not doc_id:
                    raise ValueError("Upload a document file.")
                new_id = save_document(
                    db,
                    request.form,
                    stored,
                    original,
                    session.get("username", ""),
                    doc_id,
                )
                db.commit()
                flash("Document saved.")
                return redirect(url_for("corporate_dms", folder_id=request.form.get("folder_id", type=int) or filters["folder_filter"]))
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(str(exc) if str(exc) else "Unable to save.")
            return redirect(url_for("corporate_dms", **redirect_args))

    try:
        sync_dms_expiry_notifications(db, create_notification)
        db.commit()
    except Exception:
        app.logger.exception("Corporate DMS expiry notification sync failed")

    view_document = None
    view_id = request.args.get("view_document", type=int)
    if view_id:
        view_document = get_document(db, view_id)

    edit_document = None
    edit_id = request.args.get("edit_document", type=int)
    if edit_id:
        edit_document = get_document(db, edit_id)

    documents = search_documents(
        db,
        search=filters["search"],
        folder_id=filters["folder_filter"],
        doc_type=filters["doc_type_filter"],
        expiry_status=filters["expiry_status_filter"],
    )
    return render_template(
        "corporate_dms_register.html",
        documents=documents,
        folders=list_folders(db),
        folder_tree=folder_tree(db),
        document_types=DMS_DOCUMENT_TYPES,
        stats=dms_register_stats(db, filters["folder_filter"]),
        expiry_alerts=collect_dms_expiry_alerts(db),
        show_upload=bool(request.args.get("new")),
        edit_document=edit_document,
        view_document=view_document,
        default_date=datetime.now().strftime("%Y-%m-%d"),
        **filters,
    )


def _corporate_dms_file_path(db, document_id: int, version_id: int | None = None):
    doc = db.execute(
        "SELECT id, current_version FROM corporate_dms_documents WHERE id=? AND is_active=1",
        (document_id,),
    ).fetchone()
    if not doc:
        return None, None
    if version_id:
        version = get_version(db, version_id)
        if not version or version.get("document_id") != document_id:
            return None, None
        return version.get("file_path"), version.get("original_filename")
    row = db.execute(
        "SELECT file_path, original_filename FROM corporate_dms_versions "
        "WHERE document_id=? AND version_no=?",
        (document_id, doc["current_version"]),
    ).fetchone()
    if not row:
        return None, None
    return row["file_path"], row["original_filename"]


@app.route("/settings/corporate-dms/file/<int:document_id>")
@login_required
def corporate_dms_file(document_id):
    db = get_db()
    _prepare_corporate_dms_db(db)
    filename, _ = _corporate_dms_file_path(db, document_id)
    if not filename:
        flash("File not found.")
        return redirect(url_for("corporate_dms"))
    path = os.path.join(CORPORATE_DMS_DIR, secure_filename(filename))
    if not os.path.isfile(path):
        flash("File not found.")
        return redirect(url_for("corporate_dms"))
    return send_from_directory(CORPORATE_DMS_DIR, secure_filename(filename))


@app.route("/settings/corporate-dms/download/<int:document_id>")
@login_required
def corporate_dms_download(document_id):
    db = get_db()
    _prepare_corporate_dms_db(db)
    version_id = request.args.get("version_id", type=int)
    filename, original = _corporate_dms_file_path(db, document_id, version_id)
    if not filename:
        flash("File not found.")
        return redirect(url_for("corporate_dms"))
    safe = secure_filename(filename)
    path = os.path.join(CORPORATE_DMS_DIR, safe)
    if not os.path.isfile(path):
        flash("File not found.")
        return redirect(url_for("corporate_dms"))
    download_name = secure_filename(original) if original else safe
    return send_from_directory(CORPORATE_DMS_DIR, safe, as_attachment=True, download_name=download_name)


@app.route("/help-desk")
@login_required
def help_desk():
    db = get_db()
    _prepare_helpdesk_db(db)
    search = request.args.get("q", "")
    category_filter = request.args.get("category", "")
    topics = list_help_topics(db, search=search, category_filter=category_filter, status_filter="Active")
    return render_template(
        "help_desk.html",
        topics=topics,
        search=search,
        category_filter=category_filter,
        categories=HELP_TOPIC_CATEGORIES,
        sub_toolbar=HELP_DESK_SUBTOOLBAR,
    )


@app.route("/help-desk/contact")
@login_required
def help_contact():
    return render_template(
        "help_contact.html",
        sub_toolbar=HELP_DESK_SUBTOOLBAR,
    )


@app.route("/help-desk/admin", methods=["GET", "POST"])
@login_required
@admin_required
def help_desk_admin():
    db = get_db()
    _prepare_helpdesk_db(db)
    if request.method == "POST":
        action = request.form.get("form_action", "save")
        rid = request.form.get("record_id", "").strip()
        if action == "delete" and rid:
            try:
                delete_help_topic(db, int(rid))
                db.commit()
                flash("Help topic deleted.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("help_desk_admin"))
        try:
            save_help_topic(
                db, request.form, session.get("username", ""), int(rid) if rid else None
            )
            db.commit()
            flash("Help topic saved.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("help_desk_admin"))
    edit_id = request.args.get("edit", type=int)
    edit_record = get_help_topic(db, edit_id) if edit_id else None
    show_form = bool(request.args.get("new")) or edit_record
    topics = list_help_topics(db, status_filter="", include_inactive=True)
    return render_template(
        "help_desk_admin.html",
        topics=topics,
        edit_record=edit_record,
        show_form=show_form,
        categories=HELP_TOPIC_CATEGORIES,
        topic_statuses=HELP_TOPIC_STATUSES,
        sub_toolbar=HELP_DESK_SUBTOOLBAR,
    )


app.jinja_env.globals.setdefault("safe_url_for", safe_url_for)

register_treasury_routes(
    app,
    login_required=login_required,
    get_db=get_db,
    query_db=query_db,
    is_admin_user=is_admin_user,
    create_approval_request=create_approval_request,
    get_edit_role_for_user=get_edit_role_for_user,
    _workflow_view_context=_workflow_view_context,
    _module_edit_context=_module_edit_context,
    _complete_module_save=_complete_module_save,
    treasury_docs_dir=TREASURY_DOCS_DIR,
    save_file_fn=save_file,
    db_path=DB_PATH,
)

register_erp_admin_routes(
    app,
    login_required=login_required,
    super_admin_required=super_admin_required,
    get_db=get_db,
    is_super_admin_user=is_super_admin_user,
    get_login_report=get_login_report,
    db_path=DB_PATH,
    support_uploads_dir=SUPPORT_TICKETS_DIR,
)

app.config["GET_DB"] = get_db
register_api_routes(
    app,
    get_db=get_db,
    hash_password=hash_password,
    verify_password=verify_password,
    authenticate_user=authenticate_user,
    user_is_active=user_is_active,
    get_user_id=get_user_id,
    get_user_display_name=get_user_display_name,
)

register_ai_routes(
    app,
    login_required=login_required,
    get_db=get_db,
    project_docs_dir=PROJECT_DOCS_DIR,
    dpr_docs_dir=DPR_DOCS_DIR,
)

app.register_blueprint(erp_platform_bp)

if __name__ == "__main__":
    with app.app_context():
        init_db()
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode)
