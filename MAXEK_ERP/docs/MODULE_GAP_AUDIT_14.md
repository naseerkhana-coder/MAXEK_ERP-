# MAXEK ERP — 14-Module Gap Audit

**Audit date:** 2026-06-20  
**Sources:** `app.py` `NAV_GROUPS`, route handlers, `CREATE TABLE` / `ensure_*_schema` across services.

Legend: **✅** Working end-to-end | **⚠️** Partial / reachable only via deep link or embedded UI | **❌** Missing route, screen, or schema

---

## Summary Table

| # | Module | Menu | Screen | Database | Working |
|---|--------|------|--------|----------|---------|
| 1 | Company Master | Settings → Company Settings → **Company Master** button | `/settings/company-master` (`company_master.html`) | `companies`, `company_branches`, `company_gst_registrations`, `company_directors_partners`, `company_documents`, `company_country_field_config` | ✅ |
| 2 | Project Documents | Projects → Create/Edit Project (embedded file uploads) | `/projects` — agreement, work order, BG, security deposit attachments on project form | `projects` columns: `agreement_document`, `work_order_document`, `bank_guarantee_document`, `security_deposit_document` | ⚠️ |
| 3 | Project Photos | **None** (orphan route) | `/project-photos`, `/project-photos/timeline`, `/project-photos/reports` | `project_photos` | ⚠️ |
| 4 | WBS | Projects → **Planning** (WBS is sub-feature) | `/cost-planning`, `/api/cost-planning/wbs/<project_id>`, `/cost-planning/reports` (WBS Report) | `cost_plans`, `cost_plan_activities`, `cost_plan_materials`, `cost_plan_manpower`, `cost_plan_machinery`, `micro_plan_entries` | ✅ |
| 5 | Client Billing | **None** (orphan route) | `/client-billing`, `/client-billing/form`, `/client-billing/reports`, `/client-billing/print/<id>` | `client_bills`, `client_bill_lines`, `client_bill_deductions`, `client_bill_attachments` | ⚠️ |
| 6 | Salary Increment | Workforce → **Employees** (increment section on staff form) | `/staff` (`staff_salary_increments`); also `/payroll/revisions` (`salary_revisions`) | `staff_salary_increments`, `salary_revisions` | ⚠️ |
| 7 | Leave | **None** (orphan route) | `/leave-request` | `leave_requests` | ⚠️ |
| 8 | Work Orders | Subcontract → **Subcontract Payments** | `/subcontract-payments` (WO create/edit + payment ledger) | `subcontract_work_orders`, `subcontract_payment_entries` | ✅ |
| 9 | Rate Revision | Subcontract → Subcontractor (rate cards); Payroll sub-route | `/subcontractors` (manpower/BOQ rates), `/payroll/revisions` | `subcontractor_manpower_rates`, `subcontractor_boq_rates`, `salary_revisions` | ⚠️ |
| 10 | Fleet | **None** (hub at `/fleet`; link from Office hub only) | `/fleet`, `/fleet/vehicles`, `/fleet/vehicle-documents`, `/fleet/running-log`, `/fleet/diesel/*` | `fleet_vehicles`, `fleet_vehicle_documents`, `fleet_running_log`, `diesel_purchases`, `diesel_issues`, `diesel_stock`, `fleet_service_history`, `fleet_breakdowns` | ⚠️ |
| 11 | Plant | **None** (hub at `/plant`) | `/plant` + asphalt/RMC/wet-mix/crusher/precast/QC/costing/maintenance sub-routes | `plants`, `asphalt_*`, `rmc_*`, `wetmix_*`, `crusher_*`, `precast_*`, `plant_qc_records`, `plant_material_rates`, `plant_maintenance_jobs`, `plant_stock` | ⚠️ |
| 12 | QC | **None** (orphan routes) | `/quality-control`, `/qc-master`; plant QC at `/plant/qc` | `qc_tests` (site), `plant_qc_records` (plant) | ⚠️ |
| 13 | Documents | **None** (Corporate DMS orphan) | `/settings/corporate-dms` | `corporate_dms_folders`, `corporate_dms_documents`, `corporate_dms_versions` | ⚠️ |
| 14 | BG/Treasury | Accounts → **Bank & Treasury** → Bank Guarantees | `/treasury`, `/treasury/bank-guarantees` (+ payments, receipts, cheques, PDC, FD, etc.) | `bank_guarantees`, `bank_accounts`, `bank_payments`, `bank_receipts`, `bank_cheques`, `pdc_register`, `fixed_deposits`, `letters_of_credit`, `bank_overdrafts`, `treasury_security_deposits` | ✅ |

---

## Notes by Module

### 1. Company Master — ✅
Full CRUD on company, branches, GST, directors, document vault. Linked from Settings page (`settings.html` → Company Master button). Not a direct sidebar item but reachable from Settings nav group.

### 2. Project Documents — ⚠️
Document upload/view is embedded in project create/edit. No standalone document register, versioning, or sidebar entry. Files stored under `static/uploads/projects/`.

### 3. Project Photos — ⚠️
Complete register with timeline and print reports. Route and schema exist; **not in `NAV_GROUPS`**.

### 4. WBS — ✅
WBS tree, activities, and WBS Report live inside Cost Planning. No separate "WBS" menu label — users reach it via Projects → Planning.

### 5. Client Billing — ⚠️
Full RA billing with workflow (`client_billing` in `DEFAULT_MODULES`), DPR import, print, reports. **Not in sidebar** — must use direct URL or dashboard tile.

### 6. Salary Increment — ⚠️
Two parallel paths: `staff_salary_increments` on Employees form; `salary_revisions` on `/payroll/revisions`. No dedicated "Salary Increment" menu label; payroll revisions not listed as its own nav item.

### 7. Leave — ⚠️
Full CRUD + workflow (`leave_request`). **Not in sidebar.**

### 8. Work Orders — ✅
Subcontract work orders and payment entries with workflow on payments. Accessible from Subcontract → Subcontract Payments.

### 9. Rate Revision — ⚠️
Subcontractor rate cards (manpower + BOQ) on subcontractor master; salary revisions on payroll revisions page. No unified "Rate Revision" module or menu.

### 10. Fleet — ⚠️
Six sub-modules with full CRUD. Dashboard hub at `/fleet` works; **not in `NAV_GROUPS`**. Reachable via Office hub link or direct URL.

### 11. Plant — ⚠️
13+ sub-modules with production, dispatch, QC, costing. Dashboard at `/plant` works; **not in sidebar**.

### 12. QC — ⚠️
Site QC master (`qc_tests`) and plant QC (`plant_qc_records`) are separate screens. Neither appears in sidebar.

### 13. Documents — ⚠️
Corporate DMS with folders, versions, admin upload. Route `/settings/corporate-dms` exists; **not linked in Settings `NAV_GROUPS`**.

### 14. BG/Treasury — ✅
Treasury hub in Accounts sidebar. Bank guarantees registered with workflow (`bank_guarantee` in `DEFAULT_MODULES`). Full treasury sub-module surface under `/treasury/*`.

---

## Counts

| Status | Count |
|--------|-------|
| ✅ Working | 4 |
| ⚠️ Partial | 10 |
| ❌ Missing | 0 |

**Primary gap pattern:** 10 of 14 modules have working screens and database tables but lack sidebar navigation or are embedded inside another screen.
