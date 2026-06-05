# MAXEK ERP — Phase 1 Executive Summary

**Date:** June 2026  
**Baseline:** [FINAL_REQUIREMENTS_CONFIRMATION.md](./FINAL_REQUIREMENTS_CONFIRMATION.md)  
**Detail:** [PHASE1_GAP_ANALYSIS.md](./PHASE1_GAP_ANALYSIS.md)  
**Evidence:** Repository audit (`web_app.py`, `modules/*`, `database/`, `frontend/`, `api/`, `tests/`)

---

## 1. Overall Project Completion %

**58%** — weighted toward the ten Phase 1 go-live modules in FINAL §Phase 1 Go-Live Priority (75% weight) and four supporting modules in this report (25% weight).

| Weight bucket | Modules | Avg. % |
|---------------|---------|--------|
| Phase 1 priority (×0.75) | Dashboard, Attendance, Payroll, Subcontractor Billing, Inventory, Purchase, Petty Cash, Accounts, Document Management, Reports | **57.9%** |
| Supporting (×0.25) | Authentication, User Management, Worker Management, Letter Management | **67.5%** |

**What is in place:** Streamlit ERP with ~149 routed pages (`modules/erp_router.py`), corporate theme (`styles/theme.css`, `modules/ui.py`), SQLite schema across `modules/database.py` / `modules/erp_data.py`, worker payroll engine with unit tests (`modules/worker_payroll_engine.py`, `tests/test_worker_payroll_engine.py`), finance and correspondence flows, PDF generators (`modules/document_pdfs.py`).

**What holds the score down:** Critical gaps vs approved FINAL requirements (multi-project attendance, stock ledger, API in repo, plaintext passwords), incomplete cross-cutting workflow/notifications/roles, and minimal automated test coverage (3 test modules).

---

## 2. Module-wise Completion %

| Module | Complete % | Evidence (repository paths) |
|--------|------------|-----------------------------|
| **Dashboard** | 62% | `modules/ui.py` (`page_dashboard`, KPI cards, `_render_dashboard_notifications`), `modules/erp_router.py` (`page_dashboard`, `page_dash_pending`, `page_dash_notifications`), `modules/database.py` (`kpi_stats`, `dashboard_notifications`) |
| **Authentication** | 68% | `modules/ui.py` (`show_login_page`, SQL login ~778–779), `web_app.py` (`_init_session_state`, `logged_in`), `modules/database.py` (`users`, `login_history`) |
| **User Management** | 72% | `modules/pages.py` (User Management ~5141+, user insert), `modules/roles.py` (`can_manage_users`), `modules/erp_router.py` (`page_settings_users`, `page_masters_users_route`) |
| **Attendance** | 52% | `modules/pages.py` (`page_attendance`, duplicate-day guard ~1847–1856), `modules/database.py` (`attendance`), `frontend/src/pages/Attendance.jsx` (secondary UI) |
| **Payroll** | 68% | `modules/worker_payroll_engine.py` (8hr/10hr, OT, `WORKFLOW_STATUSES`), `modules/worker_payroll_db.py`, `modules/worker_payroll.py`, `modules/pages.py` (staff payroll), `tests/test_worker_payroll_engine.py` |
| **Worker Management** | 70% | `modules/database.py` (`employees`, `workers`, `staff`), `modules/pages.py` (employee/worker screens), `modules/erp_router.py` (`page_masters_employees`) |
| **Subcontractor Billing** | 58% | `modules/billing.py`, `modules/database.py` (`subcontractor_labour_rates`, `subcontractor_bills`, `subcontractor_bill_preview`), `modules/document_pdfs.py` (`generate_subcontractor_bill_pdf`) |
| **Inventory** | 48% | `modules/erp_screens.py` (return, transfer, site stock), `modules/inventory.py`, `modules/store.py`, `modules/database.py` (`stock_register`, `material_issues`, `save_material_issue` — insert only) |
| **Purchase** | 62% | `modules/erp_screens.py` (requisition, RFQ, quotation, GRN), `modules/erp_data.py` (`purchase_rfqs`, `purchase_quotations`, `grn_entries`), `modules/navigation.py` (procurement menu) |
| **Accounts** | 63% | `modules/finance.py`, `modules/finance_workflow.py`, `modules/finance_screens.py`, `modules/gst_tds.py`, `modules/database.py` (COA, vouchers, GST/TDS, `finance_audit_log`) |
| **Petty Cash** | 58% | `modules/finance_workflow.py` (`EXPENSE_STATUSES`), `modules/navigation.py` (petty routes), `modules/database.py` (`petty_cash_requests`, `petty_cash_issues`, `petty_cash_expenses`) |
| **Document Management** | 48% | `modules/erp_screens.py` (`page_controlled_document`), `modules/erp_data.py` (`controlled_documents`), `modules/pages.py` (uploads), `modules/database.py` (`document_uploads`) |
| **Letter Management** | 60% | `modules/correspondence.py`, `modules/correspondence_data.py` (inward/outward/drafts/authority/inbox/audit), `modules/erp_router.py` (`page_corr_*` routes) |
| **Reports** | 58% | `modules/financial_reports.py`, `modules/pages.py` (Excel exports), `modules/document_pdfs.py`, `modules/erp_router.py` (`page_rpt_*`) |

**UI note:** Primary application is Streamlit (`web_app.py`). React `frontend/` has 7 pages (login, attendance, payroll approvals, DPR, store, expenses, home) and is not a full ERP shell.

---

## 3. Critical Gaps Blocking Go-Live

| # | Gap | Why it blocks go-live | Evidence |
|---|-----|----------------------|----------|
| 1 | **Multi-project same-day attendance** | FINAL §2 requires multiple projects per worker per day; code enforces one row per `employee_id` + date | `modules/pages.py` ~1847–1856; payroll/sub-bill rollups assume single row |
| 2 | **Inventory auto-deduction / live stock** | Issues do not reduce `stock_register`; project stock cannot be trusted | `modules/database.py` `save_material_issue` ~6521–6546 |
| 3 | **Mobile API not in repository** | Mobile entry and API-ready architecture cannot be deployed from this tree | `api/README.md` documents `uvicorn api_app:app`; **no `api_app.py`** in workspace |
| 4 | **Plaintext password authentication** | Unacceptable for production ERP | `modules/ui.py` ~778–779; `users.password TEXT`; `modules/pages.py` ~5187–5194 inserts plaintext |

---

## 4. High Priority Development Tasks

Ordered by risk to Phase 1 sign-off (after critical blockers):

1. **Unified approval workflow** — Map payroll, petty cash, purchase, subcontractor bills to FINAL §7: Draft → Prepared → Checked → Approved → Payment Released → Paid, with audit on every transition (`modules/finance_workflow.py`, `modules/worker_payroll_engine.py`, `modules/database.py` `log_finance_audit`).
2. **Approved role matrix** — Add/rename Purchase, Store, Management, Subcontractor, Client (View Only); wire `allowed_pages_for_role` in `modules/navigation.py` (`modules/roles.py`).
3. **In-app + email notifications** — Replace KPI-only hints with event-driven inbox and outbound email (`modules/database.py` `dashboard_notifications` ~5730+).
4. **Subcontractor designation-wise billing** — Explicit days/hours/OT/rate lines on bills, not only aggregated preview (`modules/database.py` `subcontractor_bill_preview`, `modules/billing.py`).
5. **Document version control** — Revision history beyond single `version` text field (`modules/erp_data.py` `controlled_documents`, `modules/erp_screens.py`).
6. **Food & camp recovery module** — Daily entry, monthly recovery, worker ledger (FINAL §6; today: `food_allowance` / engine deduction type only).
7. **Advance partial recovery** — Row-level settlement vs bulk `mark_advances_deducted` (`modules/database.py` ~5477+).
8. **PDF / Excel / Print parity** — Sweep Phase 1 routes (~149 keys in `erp_router.py`) for export on every screen (`modules/document_pdfs.py`, `modules/pages.py`).
9. **Purchase → payment E2E** — Harden RFQ → GRN → invoice → payment; add missing `purchase_orders` table if PO register is required (`database.py` references `purchase_orders` in KPI query without `CREATE TABLE`).
10. **Automated tests** — Expand beyond 3 files for attendance, stock, workflow, and payroll edge cases (`tests/`).

---

## 5. Existing Database Tables (grouped)

Sources: `CREATE TABLE` in `modules/database.py`, `modules/worker_payroll_db.py`, `modules/erp_data.py`, `modules/correspondence_data.py`.

### Core / authentication (`database.py`)

`users`, `app_settings`, `login_history`

### Organisation / masters (`database.py`)

`countries`, `regions`, `districts`, `departments`, `designations`, `payment_heads`, `expense_heads`, `salary_rules`, `ot_rules`, `managers`, `company_master`, `vendors`, `material_master`, `document_sequences`

### Clients / projects / site reporting (`database.py`)

`clients`, `projects`, `client_boq_items`, `project_boq_items`, `dpr_reports`, `dpr_measurements`, `dpr_manpower`, `dpr_steel_shapes`, `dpr_boq_lines`, `client_bills`, `client_bill_lines`

### HR / labour (`database.py` + `erp_data.py`)

`employees`, `staff`, `workers`, `attendance`, `payroll`, `allowance_heads`, `employee_allowance_components`, `employee_salary_revisions`, `employee_bonus`, `employee_bata`, `holiday_master`, `weekly_off_settings`, `leave_requests`, `employee_transfers`, `overtime_entries`

### Worker payroll (`worker_payroll_db.py`)

`worker_payroll_runs`, `worker_payroll_deductions`

### Subcontractors (`database.py`)

`subcontractors`, `subcontractor_advance`, `subcontractor_labour_rates`, `subcontractor_boq_rates`, `subcontractor_boq_entries`, `subcontractor_bills`, `subcontractor_bill_entries`, `subcontractor_work_orders`, `security_deposit_register`

### Finance / accounts (`database.py`)

`payments`, `expenses`, `material_requests`, `expense_invoices`, `expense_invoice_lines`, `petty_cash_requests`, `site_expenses`, `site_expense_lines`, `direct_payments`, `finance_audit_log`, `chart_of_accounts`, `journal_entries`, `ledger_lines`, `project_finance_settings`, `finance_transactions`, `employee_advance`, `expense_entries`, `payment_vouchers`, `receipt_vouchers`, `gst_ledger`, `gst_payments`, `tds_deductions`, `tds_payments`

### Petty cash (parallel models) (`database.py`)

`petty_cash_issues`, `petty_cash_expenses`

### Store / inventory (`database.py` + `erp_data.py`)

`stock_register`, `material_issues`, `purchase_rfqs`, `purchase_quotations`, `grn_entries`, `stock_returns`, `stock_transfers`, `stock_adjustments`

### Assets / vehicles / calendar (`database.py` + `erp_data.py`)

`asset_register`, `asset_transfers`, `asset_depreciation`, `tools_register`, `asset_fuel_logs`, `asset_maintenance`, `asset_breakdowns`, `vehicles`, `vehicle_allocations`, `vehicle_trips`, `vehicle_fuel_logs`, `vehicle_services`, `vehicle_insurance`, `calendar_events`

### Documents (`database.py` + `erp_data.py`)

`document_uploads`, `controlled_documents`

### Correspondence / letters (`correspondence_data.py`)

`correspondence_inward`, `correspondence_outward`, `correspondence_drafts`, `correspondence_authority`, `correspondence_email_inbox`, `correspondence_audit_log`

### ERP reference data (`erp_data.py`)

`erp_units`, `erp_material_categories`, `erp_staff_categories`, `erp_vendor_ratings`, `erp_drivers`, `bank_reconciliations`, `cheque_register`

---

## 6. Missing Database Tables (for FINAL requirements)

| Requirement (FINAL) | Gap | Suggested table / change |
|---------------------|-----|--------------------------|
| Multi-project same-day attendance (§2) | One row per worker/day enforced in app | Allow multiple `attendance` rows; unique on `(employee_id, attendance_date, project_name)`; optional `attendance_line_id` |
| Document version control (§9) | Single `version` text on `controlled_documents` | `document_versions` (parent_id, version_no, file_path, uploaded_by, superseded_at, is_current) |
| In-app notifications (§12) | KPI-derived messages only | `erp_notifications` (user_id, event_type, entity_type, entity_id, message, read_at, created_at) |
| Email notifications (§12) | No ERP event outbox | `notification_queue` or SMTP settings + delivery log |
| Inventory auto-deduction (§8) | Issues do not move qty | `stock_movements` (material_code, project_name, qty_delta, ref_type, ref_id, created_at) **or** transactional updates to `stock_register` |
| Food & camp recovery (§6) | No dedicated ledger | `food_camp_daily_entries`, `food_camp_recovery_runs` |
| Unified workflow audit (§7) | Partial (`finance_audit_log` only) | `workflow_audit_log` (entity_type, entity_id, from_status, to_status, actor, comments, created_at) |
| Role permission matrix (§1) | Permissions in Python only | `role_permissions` (role, page_key, can_read, can_write, can_approve) |
| GPS-ready attendance (§2 future) | No geo columns | Add `latitude`, `longitude`, `capture_source` on `attendance` |
| Purchase orders (procurement chain) | KPI queries `purchase_orders` but no `CREATE TABLE` | `purchase_orders`, `purchase_order_lines` (and link to GRN / invoice) |
| Subcontractor / client portal (§1 roles) | No external user tables | `portal_users` (linked to subcontractor_id or client_id, role, credentials) |

---

## 7. Existing User Roles (`modules/roles.py`)

Defined in `ERP_USER_ROLES`:

| Role | Permission groups (helpers) |
|------|----------------------------|
| Super Admin | `SUPER_ADMIN_ROLES`, full user management, payment approval |
| Admin | Same as super-admin tier for most checks |
| MD | Mapped to management; display alias “Super Admin (Owner / MD)” |
| HR & Payroll | `HR_PAYROLL_ROLES` |
| HR | Normalized to HR & Payroll in `resolve_role_pages` |
| Accountant | Accounts staff; maps to Accounts Manager for pages |
| Accounts Manager | `ACCOUNTS_MANAGER_ROLES`, financial statements, settlements |
| Accounts Executive | `ACCOUNTS_EXECUTIVE_ROLES`, verify finance |
| Project Manager | `PROJECT_MANAGER_ROLES`, material/expense approval |
| Site Engineer | `SITE_ENGINEER_ROLES`, site expense drafts |
| Store Keeper | `STORE_KEEPER_ROLES`, issue/receive/stock |

Permission logic is **code-based** (`can_manage_users`, `can_approve_payments`, `can_issue_materials`, etc.), not loaded from a database matrix.

---

## 8. Missing User Roles vs Approved List

**Approved (FINAL §1):** Super Admin, Management, HR, Accounts, Purchase, Store, Project Manager, Site Engineer, Subcontractor, Client (View Only).

| Approved role | Status in codebase |
|---------------|-------------------|
| Super Admin | **Present** |
| Management | **Partial** — MD / Admin act as management; no role label “Management” |
| HR | **Present** (HR, HR & Payroll) |
| Accounts | **Partial** — split across Accountant, Accounts Manager, Accounts Executive |
| Purchase | **Missing** — no dedicated role; procurement uses PM / store / admin rules |
| Store | **Partial** — “Store Keeper” exists; not named “Store” |
| Project Manager | **Present** |
| Site Engineer | **Present** |
| Subcontractor | **Missing** — no external subcontractor login role |
| Client (View Only) | **Missing** — client master data exists; no view-only client user role |

---

## 9. Security Readiness Status

| Area | Status | Evidence |
|------|--------|----------|
| **Password storage** | **Not ready** | Plaintext `users.password`; login `WHERE username=? AND password=?` in `modules/ui.py`; new users stored plaintext in `modules/pages.py` |
| **Session management** | **Partial** | Streamlit `st.session_state` in `web_app.py` (`logged_in`, `user_name`, `user_role`); no documented server-side session expiry or idle timeout |
| **Authorization** | **Partial** | Role helpers in `modules/roles.py`; page allow-list in `modules/navigation.py` — not per-action on all entities |
| **Audit trail** | **Partial** | `finance_audit_log`, `correspondence_audit_log`; not universal for attendance, payroll runs, inventory |
| **API security** | **Not ready** | `api/README.md` describes Bearer auth and endpoints; **`api_app.py` absent** — cannot verify token handling, HTTPS, or scope |
| **SQL injection** | **Mostly parameterized** | Login and attendance paths use bound parameters; continued audit needed on dynamic SQL builders |
| **Production secrets** | **Review required** | Ensure deploy credentials and DB paths are not committed; see `DEPLOY.md` |

**Security readiness summary:** **Not production-ready** until password hashing, API implementation, and hardened session/API policies are delivered.

---

## 10. Recommended Phase 1 Go-Live Scope

### Include in a controlled pilot (after P0 fixes on attendance scope and passwords)

- **Streamlit ERP** for masters, **single-project** attendance (explicitly scoped), worker payroll 8hr/10hr (`modules/worker_payroll.py`), staff payroll subset, petty cash and accounts with **documented** status names, correspondence/letters, existing PDF/Excel where already wired.
- **Roles:** Super Admin, MD, HR & Payroll, Accounts Manager, Project Manager, Site Engineer, Store Keeper.
- **Reports:** Attendance, payroll, subcontractor bill, P&L/cash flow where role allows — with manual reconciliation for stock.

### Defer until post–Phase 1 remediation

- Multi-project same-day attendance (until schema + UI + payroll aggregation ship).
- Mobile app production use (until `api_app.py` or equivalent is in repo and secured).
- WhatsApp, GPS capture, BOQ/tender/equipment/AI modules (FINAL §11–14).
- Full React SPA parity with Streamlit (~149 routes).

### Exclude from “production” label until fixed

Plaintext passwords, negative/unreconciled stock, unified six-step workflow, email notifications, Client/Subcontractor/Purchase roles.

---

## 11. Estimated Remaining Development Time

Assumes one senior full-stack developer; hours include implementation and basic QA (not full business UAT).

| # | Task | Hours | Days (8h) |
|---|------|-------|-----------|
| 1 | Multi-project attendance + payroll/sub-bill aggregation | 100 | 12.5 |
| 2 | Stock ledger + auto deduction (issue/return/transfer/GRN) | 80 | 10 |
| 3 | Unified workflow + cross-module audit | 72 | 9 |
| 4 | Password hashing + login/user-create hardening | 20 | 2.5 |
| 5 | `api_app.py` in repo + mobile attendance API + smoke tests | 56 | 7 |
| 6 | Role matrix (Purchase, Client, Subcontractor, Management naming) | 32 | 4 |
| 7 | Email + in-app notification system | 40 | 5 |
| 8 | Document version control | 56 | 7 |
| 9 | Subcontractor designation-wise bill lines + exports | 40 | 5 |
| 10 | Food/camp recovery module | 40 | 5 |
| 11 | Advance partial recovery (row-level) | 24 | 3 |
| 12 | PDF/Excel/print sweep on Phase 1 routes | 96 | 12 |
| 13 | Dashboard actionable inbox + Phase 1 KPIs | 24 | 3 |
| 14 | Purchase → payment E2E + `purchase_orders` schema | 32 | 4 |
| 15 | Automated test expansion | 48 | 6 |

**Total:** ~760 hours ≈ **95 working days** (~4–5 calendar months with one developer). Parallel UAT can overlap the final 3–4 weeks once items 1–5 are complete.

**Minimum path to narrow UAT (items 1, 4, 6 + single-project scope document):** ~152 hours (~19 days).

---

## 12. Final Recommendation

### **Needs Major Development**

**Reasons:**

1. **Four critical blockers** violate approved FINAL requirements or basic production security: multi-project attendance design, inventory stock accuracy, missing in-repo API (`api_app.py`), and plaintext passwords.
2. **Cross-cutting Phase 1 requirements** — unified six-step approval workflow, email + actionable in-app notifications, document version history, and full approved role matrix — are only partially implemented.
3. **Test coverage is insufficient** for finance/payroll/inventory go-live (3 test modules under `tests/`).
4. **Overall weighted completion (~58%)** reflects strong scaffolding but not acceptance against FINAL §Phase 1 Go-Live Priority and cross-cutting checklist.

**Not selected:**

- *Ready for Production* — security and critical functional gaps preclude this.
- *Ready for UAT* — only appropriate after explicit scope reduction (e.g. single-project sites, Streamlit-only, manual stock reconciliation) **and** password hashing; full FINAL UAT still requires major items above.
- *Needs Minor Development* — gap count and breaking-change items (attendance model, stock ledger, API layer) exceed “minor”.

**Next step:** Execute P0 tasks (§3–4, items 1–5 in §11), then run the acceptance checklist in [PHASE1_GAP_ANALYSIS.md](./PHASE1_GAP_ANALYSIS.md) against the ten Phase 1 modules in FINAL §Phase 1 Go-Live Priority.

---

*Generated from repository state, June 2026. Re-verify whether `api_app.py` exists only on a deployment host and was omitted from git.*
