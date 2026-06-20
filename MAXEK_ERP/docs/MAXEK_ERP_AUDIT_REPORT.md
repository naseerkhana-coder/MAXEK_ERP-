# MAXEK ERP Audit Report

**Workspace:** `C:\Users\rajee\Documents\New project\MAXEK_ERP`  
**Audit date:** 2026-06-20  
**Scope:** Navigation, routes, schemas, CRUD/approval/reports — audit only, no fixes.

---

## 1. Module List

### 1A. Sidebar modules (`NAV_GROUPS` in `app.py`)

| Slug | Label | Primary endpoints |
|------|-------|-------------------|
| `dashboard` | Dashboard | `dashboard`, `dashboard_choice_b` |
| `projects` | Projects | `projects`, `clients`, `boq_management`, `boq_multiple_entry`, `cost_planning`, `dpr_entry`, `project_expenses`, `reports` |
| `workforce` | Workforce | `staff`, `attendance`, `timesheet`, `payroll`, `salary` |
| `subcontract` | Subcontract | `subcontractors`, `workers`, `attendance`, `timesheet`, `sub_billing_register`, `subcontract_payments` |
| `store-procurement` | Store & Procurement | `store`, `material_request`, `purchase_request`, `purchase_orders`, `store_receipt`, `store_issue`, `material_transfer`, `inventory` |
| `accounts` | Accounts | `petty_cash`, `head_office_expenses`, `accounts_receipts`, `accounts_payments`, cash/bank books, GST, TDS, ledger, `accounts_reports`, treasury hub, cheques |
| `approvals` | Approvals | `approvals` (filtered by module group) |
| `settings` | Settings | `user_settings`, `user_management`, `settings`, `workflow_settings` |

### 1B. Workflow modules (`DEFAULT_MODULES` in `workflow_service.py`) — 30 entries

`petty_cash`, `material_request`, `purchase_request`, `purchase_order`, `payroll`, `daily_timesheet`, `monthly_staff_attendance`, `project_expenses`, `head_office_expenses`, `subcontract`, `boq`, `project_creation`, `dpr`, `client_billing`, `manager_tool`, `account_receipt`, `account_payment`, `account_expense`, `payment_voucher`, `receipt_voucher`, `account_gst`, `account_tds`, `leave_request`, `store_issue`, `store_receipt`, `material_transfer`, `subcontract_payments`, `bank_payment`, `bank_receipt`, `bank_guarantee`

### 1C. Route map modules (`MODULE_ROUTES` in `app.py`)

Same as above plus: `securities_guarantees`, `boq_bulk` → `boq_multiple_entry`, `account_gst`/`account_tds` aliases.

### 1D. Dashboard hub modules (not in sidebar)

| Hub route | Label | Sub-modules |
|-----------|-------|-------------|
| `/office`, `/office-admin` | Office Administration | Inward, Outward, Letters, Quotations, PO Register, Agreements, Legal, Fleet link |
| `/fleet` | Fleet Management | Vehicles, Documents, Running Log, Diesel Purchase/Stock/Issue |
| `/plant` | Plant Operations | Plant 360, Master, Asphalt/RMC/Wet Mix/Crusher/Precast production & dispatch, QC, Costing, Maintenance |

### 1E. Orphan / deep-link modules (routes exist, not in `NAV_GROUPS`)

| Module | Route prefix | Workflow registered? |
|--------|--------------|---------------------|
| Client Billing | `/client-billing` | Yes (`client_billing`) |
| BBS Reports | `/bbs` | No |
| Project Photos | `/project-photos` | No |
| Leave Request | `/leave-request` | Yes |
| Securities & Guarantees | `/securities-guarantees` | No (internal Draft/Active status) |
| Manager Tool | `/manager-tool` | Yes |
| Employee Monthly Timesheets | `/timesheets` | No (column only; not in `DEFAULT_MODULES`) |
| QC Master | `/quality-control`, `/qc-master` | No |
| Help Desk | `/help-desk` | No |
| Corporate DMS | `/settings/corporate-dms` | No |
| Staff Bonus | `/staff-bonus` | No |
| Clients | `/clients` (via Projects) | No |
| DPR Legacy | `/dpr-entry-legacy` | Legacy |

---

## 2. Menu List (Hierarchical)

Source: `NAV_GROUPS` rendered in `templates/base_maxek.html` via `nav_groups` context.

```
Dashboard
└── Dashboard

Projects
├── Project List          → /projects#project-list
├── Create Project        → /projects#add-project
├── BOQ Management        → /boq-management
├── BOQ Multiple Item Entry → /boq-multiple-entry
├── Planning              → /cost-planning
├── Progress Monitoring   → /dpr-entry
├── Project Costing       → /project-expenses
└── Project Reports       → /reports

Workforce
├── Employees             → /staff
├── Attendance            → /attendance
├── Timesheet             → /timesheet
├── Payroll               → /payroll
└── Salary Processing     → /salary

Subcontract
├── Subcontractor Creation → /subcontractors#add-subcontractor
├── Subcontractor List     → /subcontractors#subcontractor-list
├── Subcontractor Workers  → /workers
├── Worker Attendance      → /attendance?nav=subcontract
├── Worker Timesheet       → /timesheet?nav=subcontract
├── Subcontract Bills      → /sub-billing
└── Subcontract Payments   → /subcontract-payments

Store & Procurement
├── Store Dashboard        → /store
├── Material Request       → /material-request
├── Purchase Request       → /purchase-request
├── Purchase Order         → /purchase/orders
├── Delivery / GRN         → /store-receipt
├── Store Issue            → /store-issue
├── Material Transfer      → /material-transfer
└── Inventory Stock        → /inventory

Accounts
├── Petty Cash             → /petty_cash
├── Daily Expenses         → /head-office-expenses
├── Receipts               → /accounts/receipts
├── Payments               → /accounts/payments
├── Cash Book              → /accounts/cash-book
├── Bank Book              → /accounts/bank-book
├── GST                    → /accounts/gst-register
├── TDS                    → /accounts/tds
├── Ledger                 → /accounts/ledger (+ COA, GL, vendor/client)
├── Accounts Reports       → /accounts/reports
├── Bank & Treasury        → /treasury
└── Cheque Management      → /treasury/cheques

Approvals
├── Purchase Approval      → /approvals?module=purchase
├── Store Approval         → /approvals?module=store
├── Timesheet Approval     → /approvals?module=timesheet
├── Payroll Approval       → /approvals?module=payroll
└── Payment Approval       → /approvals?module=payment

Settings
├── Users                  → /settings/users
├── Roles & Permissions    → /admin/users
├── Company Settings       → /settings
└── Workflow Settings      → /settings/workflow
```

**Sub-toolbar:** When inside a department group, `base_maxek.html` renders a horizontal sub-bar duplicating the same items.

**Not in sidebar:** Office (`/office`), Fleet (`/fleet`), Plant (`/plant`), Client Billing, BBS, Project Photos, Leave, Securities, Manager Tool, `/timesheets`, Help Desk, Corporate DMS, QC Master.

---

## 3. Routes List

### 3A. Core (`app.py`) — selected full inventory

| Endpoint | Path | Methods |
|----------|------|---------|
| `index` | `/` | GET |
| `login` | `/login` | GET, POST |
| `forgot_password` | `/forgot-password` | GET, POST |
| `logout` | `/logout` | GET |
| `department_hub` | `/department/<slug>` | GET |
| `dashboard` | `/dashboard` | GET |
| `dashboard_choice_b` | `/dashboard/choice-b` | GET |
| `staff` | `/staff` | GET, POST |
| `staff_bonus` | `/staff-bonus` | GET, POST |
| `subcontractors` | `/subcontractors` | GET, POST |
| `clients` | `/clients` | GET, POST |
| `projects` | `/projects` | GET, POST |
| `workers` | `/workers` | GET, POST |
| `attendance` | `/attendance` | GET, POST |
| `petty_cash` | `/petty_cash` | GET, POST |
| `securities_guarantees` | `/securities-guarantees` | GET, POST |
| `salary` | `/salary` | GET, POST |
| `reports` | `/reports` | GET, POST |
| `settings` | `/settings` | GET, POST |
| `company_master` | `/settings/company-master` | GET, POST |
| `user_settings` | `/settings/users` | GET, POST |
| `user_management` | `/admin/users` | GET, POST |
| `workflow_settings` | `/settings/workflow`, `/settings/workflow-matrix` | GET, POST |
| `workflow_audit_report` | `/reports/workflow-audit` | GET |
| `approvals` | `/approvals`, `/approvals/<role>` | GET |
| `approval_detail` | `/approvals/detail/<approval_id>` | GET |
| `approval_action` | `/approvals/action` | POST |
| `material_request` | `/material-request` | GET, POST |
| `purchase_request` | `/purchase-request` | GET, POST |
| `project_expenses` | `/project-expenses` | GET, POST |
| `head_office_expenses` | `/head-office-expenses` | GET, POST |
| `subcontract_request` | `/subcontract-request` | GET, POST |
| `boq_management` | `/boq-management` | GET, POST |
| `boq_multiple_entry` | `/boq-multiple-entry` | GET, POST |
| `dpr_entry` | `/dpr-entry` | GET, POST |
| `cost_planning` | `/cost-planning` | GET, POST |
| `payroll` | `/payroll` | GET, POST |
| `leave_request` | `/leave-request` | GET, POST |
| `store_issue` | `/store-issue` | GET, POST |
| `material_transfer` | `/material-transfer` | GET, POST |
| `store_receipt` | `/store-receipt` | GET, POST |
| `store` | `/store` | GET |
| `purchase_orders` | `/purchase/orders` | GET, POST |
| `inventory` | `/inventory` | GET |
| `timesheet` | `/timesheet` | GET |
| `subcontract_payments` | `/subcontract-payments` | GET, POST |
| `sub_billing_register` | `/sub-billing` | GET |
| `sub_billing_form` | `/sub-billing/form` | GET, POST |
| `client_billing_form` | `/client-billing/form` | GET, POST |
| `employee_timesheets` | `/timesheets` | GET |
| `employee_timesheets_form` | `/timesheets/form` | GET, POST |
| `bbs_register` | `/bbs` | GET |
| `office_admin` | `/office`, `/office-admin` | GET |
| `fleet_dashboard` | `/fleet` | GET |
| `plant_dashboard` | `/plant` | GET |
| `help_desk` | `/help-desk` | GET |
| `corporate_dms` | `/settings/corporate-dms` | GET, POST |
| `manager_tool` | `/manager-tool` | GET, POST |
| `qc_master` | `/quality-control`, `/qc-master` | GET, POST |

Plus ~80 API/print/export/attachment routes (BOQ print, DPR attachments, payroll print/export, accounts ledgers, plant dispatch prints, etc.).

### 3B. Treasury (`treasury_routes.py` via `register_treasury_routes`)

| Endpoint (function name) | Path | Methods |
|--------------------------|------|---------|
| `treasury_hub` | `/treasury`, `/bank` | GET |
| `treasury_bank_accounts` | `/treasury/accounts` | GET, POST |
| `treasury_payments` | `/treasury/payments` | GET, POST |
| `treasury_receipts` | `/treasury/receipts` | GET, POST |
| `treasury_cheques` | `/treasury/cheques` | GET |
| `treasury_cheque_new` | `/treasury/cheques/new` | GET, POST |
| `treasury_cheque_detail` | `/treasury/cheques/<id>` | GET, POST |
| `treasury_pdc_register` | `/treasury/pdc-register` | GET |
| `treasury_fixed_deposits` | `/treasury/fixed-deposits` | GET |
| `treasury_cash_flow_forecast` | `/treasury/cash-flow-forecast` | GET |
| `treasury_document_vault` | `/treasury/document-vault` | GET |
| `treasury_budget_control` | `/treasury/budget-control` | GET |
| `treasury_project_profitability` | `/treasury/project-profitability` | GET |
| `treasury_contract_management` | `/treasury/contract-management` | GET |
| `treasury_claims` | `/treasury/claims` | GET |
| `treasury_equipment_costing` | `/treasury/equipment-costing` | GET |
| `treasury_labour_productivity` | `/treasury/labour-productivity` | GET |
| `treasury_alert_engine` | `/treasury/alert-engine` | GET |
| `treasury_command_center` | `/treasury/command-center` | GET |
| `treasury_backup_system` | `/treasury/backup-system` | GET |
| `treasury_document_numbering` | `/treasury/document-numbering` | GET |

(Full treasury file defines ~70 routes including CRUD sub-paths.)

---

## 4. Database Tables List

| Table | Source | Purpose |
|-------|--------|---------|
| **Core HR / master** | | |
| `users` | `init_db` | Login accounts, roles, workflow_role |
| `staff` | `init_db` | Employee master |
| `workers` | `init_db` | Subcontract / site workers |
| `subcontractors` | `init_db` | Subcontractor master |
| `clients` | `init_db` | Client master |
| `projects` | `init_db` | Project master + approval |
| `departments` | `init_db` | Department master |
| `designations` | `init_db` | Designation master |
| `trades` | `init_db` | Trade master |
| `attendance` | `init_db` | Daily attendance/timesheet rows |
| `staff_monthly_attendance` | `attendance_service` | Monthly staff attendance |
| `employee_monthly_timesheets` | `employee_timesheet_service` | Monthly employee timesheet header |
| `employee_timesheet_days` | `employee_timesheet_service` | Daily lines per timesheet |
| **Workflow** | | |
| `workflow_master` | `init_db` | Per-module maker/checker/approver config |
| `approval_requests` | `init_db` | Active approval queue |
| `approval_audit` | `init_db` | Approval action history |
| `notifications` | `init_db` | User notifications |
| `user_maker_assignments` | `app.py` | User→module maker slots |
| **BOQ / DPR / Planning** | | |
| `boq_master` | `app.py` | BOQ header (incl. bulk entry) |
| `boq_items` | `app.py` | BOQ line items |
| `steel_shapes` | `app.py` | DPR steel shape reference |
| `dpr_entries` | legacy + active DPR | Daily progress reports |
| `dpr_measurements` | `app.py` | DPR measurement lines |
| `dpr_steel_lines`, `dpr_manpower` | `app.py` | DPR detail lines |
| `dpr_attachments` | `app.py` | DPR file attachments |
| `equipment_master` | `app.py` / equipment costing | Equipment register |
| `cost_plans` + activity/material/manpower/machinery tables | `cost_planning_service` | Cost planning WBS |
| `micro_plan_entries` | `cost_planning_service` | Micro planning |
| **Store / procurement** | | |
| `vendors`, `materials`, `vendor_documents` | `store_service` | Vendor & material master |
| `material_requests` | `store_service` | Material requisitions |
| `purchase_requests` | legacy + store | Purchase requisitions |
| `purchase_orders`, `purchase_order_lines` | `store_service` | PO header/lines |
| `store_receipts`, `store_receipt_lines` | `store_service` | GRN |
| `store_issues` | `store_service` | Store issue |
| `material_transfers`, `material_transfer_lines` | `store_service` | Inter-project transfers |
| `stock_ledger` | `store_service` | Inventory movements |
| **Accounts** | | |
| `chart_of_accounts` | `accounts_service` | COA |
| `account_expenses`, `account_expense_lines` | `accounts_service` | Expense vouchers |
| `payment_vouchers`, `receipt_vouchers` | `accounts_service` | Payment/receipt vouchers |
| `journal_entries`, `journal_entry_lines` | `accounts_service` | Double-entry postings |
| `payment_allocations` | `accounts_service` | Payment allocation |
| `account_attachments` | `accounts_service` | Voucher attachments |
| `gst_filing_periods`, `tds_register`, `pf_esi_register` | `accounts_service` | Compliance registers |
| `petty_cash_requests`, `petty_cash_transfers`, `petty_cash_expenses`, `petty_cash_attachments` | `app.py` | Petty cash workflow |
| **Treasury** | | |
| `bank_accounts`, `bank_payments`, `bank_receipts` | `treasury_service` | Bank transactions |
| `bank_guarantees`, `bank_overdrafts`, `letters_of_credit` | `treasury_service` | BG/OD/LC |
| `bank_cheques`, `pdc_register`, `fixed_deposits` | `treasury_service` | Cheque/PDC/FD |
| `bank_reconciliation`, `treasury_security_deposits` | `treasury_service` | Recon & deposits |
| `bank_documents`, `payment_approval_matrix`, `treasury_audit_log` | `treasury_service` | Docs & audit |
| `project_budgets` | `budget_service` | Project budget control |
| `project_contracts` | `contract_service` | Contract management |
| `project_claims` | `claims_service` | Claims register |
| `equipment_cost_entries` | `equipment_costing_service` | Equipment cost entries |
| `labour_productivity_entries` | `labour_productivity_service` | Labour productivity |
| `system_alerts` | `alert_engine_service` | Alert engine |
| `document_number_sequences` | `document_numbering_service` | Doc numbering |
| `backup_runs` | `backup_service` | Backup history |
| **Payroll** | | |
| `payroll_runs`, `payroll_lines` | `app.py` | Payroll processing |
| `salary` | `init_db` | Legacy worker salary records |
| `salary_payments`, `salary_revisions` | `app.py` | Salary payments & revisions |
| `staff_salary_components`, `staff_salary_increments`, `staff_travel_tiers` | `app.py` | Staff compensation |
| `holidays`, `holiday_applicability`, `staff_bonus` | `app.py` | Holidays & bonus |
| **Subcontract** | | |
| `subcontract_requests` | legacy | Subcontract work requests |
| `subcontractor_manpower_rates`, `subcontractor_boq_rates` | `app.py` | Subcontractor rate cards |
| `subcontractor_bills`, `subcontractor_bill_lines` | `subcontractor_billing_service` | Sub billing |
| `subcontract_work_orders`, `subcontract_payment_entries` | `subcontract_payment_service` | WO ledger & payments |
| **Billing / photos / misc** | | |
| `client_bills` + lines/deductions/attachments | `client_billing_service` | Client RA bills |
| `bbs_reports`, `bbs_lines` | `bbs_service` | Bar bending schedule |
| `project_photos` | `project_photos_service` | Site photo log |
| `security_guarantees`, `security_guarantee_attachments` | `app.py` | Securities register |
| `leave_requests` | legacy | Leave applications |
| `manager_tasks` | legacy | Manager action items |
| **Office / fleet / plant** | | |
| `office_inward`, `office_outward`, `office_letters`, `office_quotations`, `office_quotation_lines`, `office_agreements`, `office_legal_documents` | `office_fleet_service` | Office admin |
| `fleet_vehicles`, `fleet_vehicle_documents`, `fleet_running_log`, `diesel_*`, `fleet_service_history`, `fleet_breakdowns` | `office_fleet_service` | Fleet |
| `plants`, `asphalt_*`, `rmc_*`, `wetmix_*`, `precast_*`, `crusher_*`, `plant_qc_records`, `plant_material_rates`, `plant_maintenance_jobs`, `plant_stock` | `plant_service` | Plant ops |
| `precast_yards` | `precast_service` | Precast yard registry |
| `qc_tests` | `qc_service` | QC master (site) |
| **DMS / help** | | |
| `corporate_dms_folders`, `corporate_dms_documents`, `corporate_dms_versions` | `corporate_dms_service` | Corporate DMS |
| `help_topics` | `helpdesk_service` | Help desk KB |
| `app_settings` | `app.py` | App configuration |
| `number_sequences` | `app.py` | Legacy numbering |
| **Company master** | | |
| `companies`, `company_branches`, `company_gst_registrations`, `company_directors_partners`, `company_documents`, `company_country_field_config` | `company_master_service` | Multi-company master |

---

## 5. Module Status Matrix

Legend: **C** Create | **E** Edit | **V** View/list | **A** Approval workflow | **R** Reports/export  
Overall: **Completed** = all applicable present | **Partial** = gaps | **Missing** = route/template absent or placeholder

### 5A. Sidebar menu items

| Menu item | C | E | V | A | R | Status | Gaps |
|-----------|---|---|---|---|---|--------|------|
| Dashboard | — | — | ✓ | — | ✓ KPIs | **Completed** | N/A |
| Project List / Create | ✓ | ✓ | ✓ | ✓ | ✓ hub | **Completed** | |
| BOQ Management | ✓ | ✓ | ✓ | ✓ | ✓ print | **Completed** | |
| BOQ Multiple Entry | ✓ | ✗ | △ recent list only | ✓ create | ✗ | **Partial** | No edit/view/detail; uses `boq` workflow on create only |
| Planning (Cost) | ✓ | ✓ | ✓ | ✗ | ✓ export/print/reports | **Partial** | Not in `DEFAULT_MODULES`; no approval |
| Progress Monitoring (DPR) | ✓ | ✓ | ✓ | ✓ | ✓ bill print/export | **Completed** | |
| Project Costing | ✓ | ✓ | ✓ | ✓ | △ | **Completed** | |
| Project Reports | △ | — | ✓ | — | ✓ Excel | **Partial** | Only attendance + salary reports |
| Employees (Staff) | ✓ | ✓ | ✓ | ✗ | △ | **Partial** | Master data; no workflow (OK) |
| Attendance | ✓ | ✓ | ✓ | ✓ daily+monthly | △ | **Completed** | |
| Timesheet (nav → `/timesheet`) | ✗ | ✗ | ✓ | ✗ | ✗ | **Partial** | Read-only list; create via `/attendance`; real forms at `/timesheets` |
| Payroll | ✓ | ✓ | ✓ | ✓ | ✓ print/export | **Completed** | |
| Salary Processing | ✓ | ✓ | ✓ | △ uses `payroll` id | △ | **Partial** | Overlaps payroll; legacy worker salary |
| Subcontractor CRUD | ✓ | ✓ | ✓ | ✗ | ✗ | **Partial** | Master only |
| Subcontractor Workers | ✓ | ✓ | ✓ | ✗ | ✗ | **Partial** | |
| Subcontract Bills | ✓ | ✓ | ✓ | ✗ column only | ✓ print/abstract | **Partial** | `subcontractor_billing` not in `DEFAULT_MODULES`; no `create_approval_request` |
| Subcontract Payments | ✓ | ✓ | ✓ | ✓ WO+payments | △ ledger | **Completed** | Payment reports limited |
| Store Dashboard | — | — | ✓ | — | △ | **Partial** | Hub only |
| Material Request | ✓ | ✓ | ✓ | ✓ | △ | **Completed** | |
| Purchase Request | ✓ | ✓ | ✓ | ✓ | △ | **Completed** | |
| Purchase Order | ✓ | ✓ | ✓ | ✓ | ✓ print | **Completed** | |
| Delivery / GRN | ✓ | ✓ | ✓ | ✓ | △ | **Completed** | |
| Store Issue | ✓ | ✓ | ✓ | ✓ | △ | **Completed** | |
| Material Transfer | ✓ | ✓ | ✓ | ✓ | △ | **Completed** | Recently implemented; full CRUD+workflow |
| Inventory Stock | — | — | ✓ | ✗ | △ | **Partial** | View/stock balance only (by design) |
| Petty Cash | ✓ | ✓ | ✓ | ✓ | △ | **Completed** | |
| Daily Expenses | ✓ | ✓ | ✓ | ✓ | △ | **Completed** | |
| Receipts / Payments | ✓ | ✓ | ✓ | ✓ | △ | **Completed** | |
| Cash / Bank Book | — | — | ✓ | — | ✓ | **Partial** | Read-only registers |
| GST / TDS | ✓ | ✓ | ✓ | ✓ | ✓ registers | **Completed** | |
| Ledger / COA | ✓ COA | ✓ | ✓ | △ COA | ✓ many reports | **Completed** | |
| Accounts Reports | — | — | ✓ | — | ✓ P&L/BS/Tally | **Completed** | |
| Bank & Treasury | ✓ | ✓ | ✓ | ✓ payments/recpts/BG | ✓ many | **Partial** | Large surface; some sub-screens admin-only |
| Cheque Management | ✓ | ✓ | ✓ | △ status flow | △ | **Partial** | Not separate workflow module |
| Approvals hub | — | — | ✓ | ✓ | ✓ audit | **Completed** | |
| Settings (all) | ✓ | ✓ | ✓ | — | △ | **Completed** | |

### 5B. Hub / orphan modules

| Module | C | E | V | A | R | Status | Gaps |
|--------|---|---|---|---|---|--------|------|
| Office Admin (8 sub) | ✓ | ✓ | ✓ | ✗ | △ expiry alerts | **Partial** | Not in sidebar; no workflow |
| Fleet (6 sub) | ✓ | ✓ | ✓ | ✗ | ✓ stock | **Partial** | Not in sidebar |
| Plant (13 sub) | ✓ | ✓ | ✓ | ✗ | ✓ costing/360 | **Partial** | Not in sidebar |
| Client Billing | ✓ | ✓ | ✓ | ✓ | ✓ reports/print | **Partial** | **Missing from nav** |
| Employee Timesheets (`/timesheets`) | ✓ | ✓ | ✓ | ✗ not wired | ✓ print | **Partial** | Nav points elsewhere; no `DEFAULT_MODULES` entry |
| BBS | ✓ | ✓ | ✓ | ✗ | ✓ print | **Partial** | Not in nav |
| Project Photos | ✓ | ✓ | ✓ | ✗ | ✓ reports | **Partial** | Not in nav |
| Leave Request | ✓ | ✓ | ✓ | ✓ | ✗ | **Partial** | **Not in nav** |
| Securities & Guarantees | ✓ | ✓ | ✓ | ✗ internal | ✓ export/print | **Partial** | **Not in nav**; custom status not standard workflow |
| Manager Tool | ✓ | ✓ | ✓ | ✓ | ✗ | **Partial** | **Not in nav** |
| QC Master | ✓ | ✓ | ✓ | ✗ | △ | **Partial** | Not in nav |
| Help Desk | △ admin | △ admin | ✓ | ✗ | — | **Partial** | User read-only KB |
| Corporate DMS | ✓ admin | ✓ | ✓ | ✗ | △ | **Partial** | Admin-only; not in settings nav |
| Company Master | ✓ | ✓ | ✓ | ✗ | △ docs | **Partial** | Linked from Settings page, not direct nav item |

---

## Executive Summary

### Status counts (≈70 functional areas)

| Status | Count | Notes |
|--------|-------|-------|
| **Completed** | **~28** | Core transactional modules with full CRUD + workflow + reports (MR, PO, GRN, DPR, payroll, accounts vouchers, material transfer, etc.) |
| **Partially Completed** | **~38** | Missing nav link, approval wiring, edit/view, or reports |
| **Missing / disconnected** | **~4** | Nav/route mismatch (`/timesheet` vs `/timesheets`); BOQ bulk edit; modules built but unreachable from sidebar |

### Top 10 priority gaps to close

1. **Add Office / Fleet / Plant / Client Billing to sidebar** — fully built hubs with no `NAV_GROUPS` entry.
2. **Fix Workforce Timesheet navigation** — sidebar goes to read-only `/timesheet`; monthly forms live at `/timesheets/form`.
3. **BOQ Multiple Entry** — add edit/view/detail + post-approval edit rules (create-only today).
4. **Subcontract Bills workflow** — schema has `approval_status`; not in `DEFAULT_MODULES`; handler never calls `create_approval_request`.
5. **Employee Monthly Timesheets workflow** — `approval_status` column + submit flow; not registered in `workflow_service` / Approval Center.
6. **Cost Planning approval** — no workflow module; plans can be deleted/edited without approval trail.
7. **Securities & Guarantees** — in `MODULE_ROUTES` but not nav; uses custom Draft/Active vs standard 3-step workflow.
8. **Leave Request & Manager Tool** — workflow-ready but not in sidebar.
9. **Project Reports scope** — only attendance + salary Excel; no project/DPR/BOQ consolidated exports from Projects menu.
10. **Approval groups incomplete** — `subcontract_payments`, `client_billing`, `securities`, `subcontractor_billing` absent from `APPROVAL_MODULE_GROUPS` filters.

### Critical missing items

- Sidebar navigation for **Office, Fleet, Plant, Client Billing, Leave, Securities, BBS, Project Photos**
- **Workflow registration** for: `subcontractor_billing`, `employee_timesheet`, `cost_planning` (if approval required)
- **BOQ Multiple Entry** edit/view workflow parity with BOQ Management
- **Timesheet** menu item functional parity (create/edit or redirect to `/timesheets`)
- **Corporate DMS** link under Settings (route exists, not in `NAV_GROUPS`)
- **`boq_bulk`** in `MODULE_ROUTES` but no matching `DEFAULT_MODULES` entry (uses `boq` at runtime)
