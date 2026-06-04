# MAXEK ERP — Phase 1 Gap Analysis

**Baseline:** [FINAL_REQUIREMENTS_CONFIRMATION.md](./FINAL_REQUIREMENTS_CONFIRMATION.md)  
**Compared to:** Current codebase (`web_app.py` Streamlit ERP, `modules/*`, SQLite in `database/`)  
**Date:** June 2026

Legend: **DONE** = meets requirement for Phase 1 use · **PARTIAL** = started but gaps remain · **NOT STARTED** = missing or placeholder only

---

## Executive Summary

The ERP has substantial Phase 1 scaffolding: Streamlit UI with corporate theme (`styles/theme.css`), dashboards (`modules/ui.py`), attendance/payroll (`modules/pages.py`, `modules/worker_payroll*.py`), subcontractor billing (`modules/billing.py`, `modules/database.py`), purchase/store/finance flows (`modules/erp_screens.py`, `modules/finance_workflow.py`, `modules/store.py`), controlled documents (`modules/erp_screens.py`), and PDF generators (`modules/document_pdfs.py`). The largest **breaking-change** risk is **multi-project same-day attendance** (today: one row per employee per day). The largest **delivery** gaps are **standard approval states**, **email notifications**, **inventory auto-deduction**, **document version control**, **food/camp recovery module**, and **approved role names** (Purchase, Client view-only, Subcontractor portal).

---

## Phase 1 Modules

### 1. Dashboard

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/ui.py` (`page_dashboard`, KPI cards, role visibility), `modules/erp_router.py` (`dash_mgmt`, `dash_pending`, `dash_notifications`), `modules/database.py` (`kpi_stats`, `dashboard_notifications`) |
| **Gaps** | Notifications are static KPI hints, not actionable inbox; no email tie-in; executive KPI set not fully aligned to Phase 1 sign-off metrics |
| **Complexity** | **M** |

---

### 2. Attendance

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/pages.py` (`page_attendance`, `_persist_attendance_entry`), `modules/database.py` (`attendance` table), `frontend/src/pages/Attendance.jsx` (secondary UI) |
| **Gaps** | **Multi-project same day:** app enforces one record per `employee_id` + `attendance_date` (`pages.py` ~1847–1856) — conflicts with requirement; no GPS fields; mobile API folder has README only (`api/README.md`), no `api_app` in repo |
| **Breaking change** | Remove unique-per-day assumption; allow multiple rows per worker/day (split hours/OT by project); payroll and subcontractor bill aggregation must sum by project |
| **Complexity** | **L** (schema + UI + payroll/sub billing) |

---

### 3. Payroll

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/worker_payroll_engine.py` (8hr/10hr rules, OT), `modules/worker_payroll.py`, `modules/worker_payroll_db.py`, `modules/pages.py` (staff payroll, advance summary), `tests/test_worker_payroll_engine.py` |
| **Gaps** | Worker module workflow is `Draft → Calculated → Approved → Paid`, not the six-step finance standard; staff vs worker paths split; approval on attendance page defers to payroll (`pages.py` ~2082–2083) |
| **Complexity** | **M** (workflow alignment + testing) |

---

### 4. Subcontractor Billing

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/billing.py`, `modules/database.py` (`subcontractor_labour_rates`, `subcontractor_bill_preview`, `subcontractor_timesheet_day_amount`), `modules/pages.py` (rate editors by designation/labour_type), `modules/document_pdfs.py` (`generate_subcontractor_bill_pdf`) |
| **Gaps** | Billing aggregates attendance by subcontractor/month, not a clear **designation-wise days/hours/OT line bill**; approval/payment states differ from global workflow; Excel on reports tab, not necessarily per bill screen |
| **Complexity** | **M** |

---

### 5. Inventory

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/erp_screens.py` (`page_material_return`, `page_stock_transfer`, `page_site_wise_stock`), `modules/inventory.py`, `modules/store.py`, `modules/database.py` (`stock_register`, `material_issues`) |
| **Gaps** | **Auto stock deduction:** `save_material_issue` inserts into `material_issues` only — does not decrement `stock_register` (`database.py` ~6521–6546); project-wise stock view is issue-list oriented, not live qty ledger |
| **Complexity** | **L** (stock ledger + issue/return/transfer hooks) |

---

### 6. Purchase

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/erp_screens.py` (requisition, RFQ, quotation, GRN), `modules/navigation.py` (procurement menu), `modules/database.py` / `modules/erp_data.py` (purchase tables) |
| **Gaps** | Full PO → invoice → vendor payment chain exists in README/navigation but Phase 1 testing needs end-to-end verification; purchase approval uses material-request style statuses, not global six-step workflow |
| **Complexity** | **M** |

---

### 7. Petty Cash

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/finance_workflow.py`, `modules/navigation.py` (`petty_request`, `petty_expense`), `modules/database.py` (petty balances, site expenses, audit via `log_finance_audit`) |
| **Gaps** | Statuses: `Draft`, `Submitted`, `Verified`, `PM Approved`, `Approved`, etc. — not `Prepared` / `Checked` / `Payment Released`; settlement vs “Paid” naming |
| **Complexity** | **M** |

---

### 8. Accounts

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/finance.py`, `modules/finance_workflow.py`, `modules/finance_screens.py`, `modules/gst_tds.py`, `modules/database.py` (ledger, vouchers, GST/TDS) |
| **Gaps** | Role names differ (`Accountant`, `Accounts Manager` vs required “Accounts”); supplier payment limits and MD approval exist but not unified workflow labels; not all vouchers expose PDF on same screen |
| **Complexity** | **M** |

---

### 9. Document Management

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/erp_screens.py` (`page_controlled_document` — contracts, drawings, site, etc.), `modules/correspondence.py`, `modules/pages.py` (uploads), `doc_site` in navigation |
| **Gaps** | Version is a single text field on register — **no revision history**, check-in/out, or immutable prior versions; site photos not a dedicated versioned DMS |
| **Complexity** | **L** |

---

### 10. Reports

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/pages.py` (Excel exports ~4539+), `modules/financial_reports.py` (P&L, balance sheet), `modules/document_pdfs.py`, `modules/erp_router.py` (`rpt_*` pages) |
| **Gaps** | Material consumption and project cost reports need explicit Phase 1 PDF+Excel parity; cash flow / P&L exist for accounts roles but may lack Excel on every view |
| **Complexity** | **M** |

---

## Cross-Cutting Requirements

### User roles & permissions

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/roles.py` (`ERP_USER_ROLES`, permission helpers) |
| **Present** | Super Admin, Project Manager, Site Engineer, HR, store keeper, accounts variants |
| **Missing / rename** | **Management** (MD partially maps), **Purchase**, **Store** (Store Keeper close), **Subcontractor**, **Client (View Only)** |
| **Complexity** | **M** |

---

### Approval workflow (Draft → … → Paid)

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/finance_workflow.py` (`EXPENSE_STATUSES`), `modules/worker_payroll_engine.py` (`WORKFLOW_STATUSES`), `modules/database.py` (`log_finance_audit`), `modules/store.py` (material request statuses) |
| **Gaps** | No single enum across payroll, petty cash, purchase, subcontractor bills; missing **Prepared**, **Checked**, **Payment Released**; audit exists for finance entities, not all modules |
| **Complexity** | **L** |

---

### Multi-project attendance (same day)

| Status | **NOT STARTED** (blocked by current design) |
|--------|---------------------------------------------|
| **Evidence** | Unique check in `modules/pages.py`; `attendance` schema allows `project_name` but one row per day |
| **Complexity** | **L** (see Attendance) |

---

### Advance management

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/finance.py` (staff advance), `modules/database.py` (`employee_advance`, `get_employee_advance_summary`, `mark_advances_deducted`), subcontractor advance in `pages.py` |
| **Gaps** | Partial recovery: UI supports `current_deduction` < open balance, but `mark_advances_deducted` marks all open paid advances for the month when payroll saves — row-level partial settlement needs refinement |
| **Complexity** | **M** |

---

### Food & camp recovery

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `employee` `food_allowance`, attendance preview divides monthly/26 (`pages.py` ~1777–1778); `worker_payroll_engine.DEDUCTION_TYPES` includes `"Food Recovery"` |
| **Gaps** | No **daily entry** screen, no **monthly recovery** run, no dedicated worker-wise camp ledger |
| **Complexity** | **M** |

---

### Inventory auto-deduction

| Status | **NOT STARTED** |
|--------|-------------|
| **Evidence** | Issues logged only (`save_material_issue`) |
| **Complexity** | **L** (with Inventory module) |

---

### Document version control

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `version` field on controlled document register (`erp_screens.py` ~910) |
| **Gaps** | No version chain, diff, or “current vs superseded” |
| **Complexity** | **L** |

---

### Notifications (in-app + email)

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `dashboard_notifications()` in `modules/database.py` — KPI-based messages only; `modules/correspondence.py` IMAP inbox for letters, not ERP event email |
| **Gaps** | No outbound email on approval/payroll/inventory events; WhatsApp stub (`page_whatsapp_sending`) |
| **Complexity** | **M** |

---

### PDF & Excel (every module)

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `modules/document_pdfs.py`, `modules/pdf_templates.py`, Excel helpers in `pages.py` |
| **Gaps** | Coverage uneven across ~170 routes; many screens are data entry only |
| **Complexity** | **L** (breadth) |

---

### Mobile / API-ready architecture

| Status | **PARTIAL** |
|--------|-------------|
| **Evidence** | `api/README.md` documents endpoints; `mobile/` Capacitor scaffold; responsive CSS |
| **Gaps** | **No FastAPI app in repository** under `api/`; Phase 1 mobile entry not shippable from this tree alone |
| **Complexity** | **L** |

---

### UI (executive dashboard, blue theme, sidebar)

| Status | **DONE** / **PARTIAL** |
|--------|------------------------|
| **Evidence** | `styles/theme.css`, `modules/sidebar.py`, `modules/ui.py`, login in `web_app.py` |
| **Gaps** | React `frontend/` exists but primary app is Streamlit; “ERPNext/Odoo style” is approximate |
| **Complexity** | **S** (polish) |

---

## Ordered Implementation Backlog (highest risk / gap first)

| Priority | Item | Status | Complexity | Rationale |
|----------|------|--------|------------|-----------|
| 1 | Multi-project same-day attendance + payroll/sub-bill aggregation | NOT STARTED | **L** | Breaking schema/UI assumption; blocks field reality |
| 2 | Unified approval workflow + audit (`Prepared` → `Checked` → `Payment Released` → `Paid`) | PARTIAL | **L** | Compliance and Phase 1 sign-off across modules |
| 3 | Inventory ledger + auto deduction on issue/return/transfer | NOT STARTED | **L** | Stock accuracy for projects |
| 4 | Approved role matrix (Purchase, Client view-only, Subcontractor, Management naming) | PARTIAL | **M** | Security model for go-live |
| 5 | Email notifications for workflow events | PARTIAL | **M** | Required channel alongside in-app |
| 6 | Food & camp recovery module (daily + monthly + worker ledger) | PARTIAL | **M** | Distinct from ad-hoc food_allowance/26 |
| 7 | Advance partial recovery (row-level settlement) | PARTIAL | **M** | Payroll correctness |
| 8 | Subcontractor designation-wise bill lines (days/hours/OT/rates) | PARTIAL | **M** | Client-facing billing accuracy |
| 9 | Document version control (revisions, supersede) | PARTIAL | **L** | DMS requirement |
| 10 | Mobile API implementation in repo + attendance POST | PARTIAL | **L** | Mobile entry requirement |
| 11 | PDF/Excel/Print parity sweep on Phase 1 routes | PARTIAL | **L** | Breadth QA |
| 12 | Dashboard actionable notifications + Phase 1 KPIs | PARTIAL | **M** | Executive visibility |
| 13 | GPS-ready attendance fields (capture off until mobile) | NOT STARTED | **S** | Future-proof schema |
| 14 | Purchase → payment E2E test hardening | PARTIAL | **M** | Phase 1 module #6 |

---

## Breaking Changes to Plan Explicitly

1. **Attendance:** Allow multiple `attendance` rows per `(employee_id, attendance_date)` differentiated by `project_name` (and optionally drop app-level duplicate check). Migrate historical data; update `subcontractor_bill_preview` and payroll period rollups to aggregate splits.
2. **Approval statuses:** Migrating finance/payroll/subcontractor records to new status vocabulary — needs mapping table and UI label updates (`finance_workflow.py`, `worker_payroll_engine.py`, billing tables).
3. **Stock:** Introducing `stock_register` quantity updates may require opening balance import before go-live.

---

## Key File Index

| Area | Files |
|------|--------|
| App entry | `web_app.py` |
| Routing | `modules/erp_router.py`, `modules/navigation.py` |
| Attendance / HR UI | `modules/pages.py` |
| Worker payroll | `modules/worker_payroll.py`, `modules/worker_payroll_engine.py`, `modules/worker_payroll_db.py` |
| Roles | `modules/roles.py` |
| Finance / petty | `modules/finance_workflow.py`, `modules/finance.py` |
| Store / inventory screens | `modules/store.py`, `modules/inventory.py`, `modules/erp_screens.py` |
| Subcontractor billing | `modules/billing.py`, `modules/database.py` |
| PDFs | `modules/document_pdfs.py`, `modules/pdf_templates.py` |
| Dashboard / UI | `modules/ui.py`, `styles/theme.css` |
| Data layer | `modules/database.py`, `modules/erp_data.py` |
| Mobile (docs only) | `api/README.md`, `mobile/` |

---

## Suggested Phase 1 Test Checklist (acceptance)

- [ ] Each Phase 1 module reachable from sidebar with role-appropriate access  
- [ ] 8hr and 10hr worker payroll matches rules for under/standard/over hours  
- [ ] Subcontractor bill PDF matches designation rates for sample month  
- [ ] Material issue reduces project stock; return/transfer reconcile  
- [ ] Petty cash and accounts payment follow audit trail end-to-end  
- [ ] Controlled document upload with version increment  
- [ ] Reports: attendance, payroll, sub bill, material, project cost, cash flow, P&L — PDF + Excel  
- [ ] In-app notification on pending approval; email received for same event  
