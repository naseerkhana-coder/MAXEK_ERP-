# Phase 2 — Cursor Tasks (Copy-Paste Ready)

**Project:** MAXEK Construction ERP  
**Governance:** [MAXEK_ERP_RULES.md](./MAXEK_ERP_RULES.md) · [MODULE_DEFINITION_OF_DONE.md](./MODULE_DEFINITION_OF_DONE.md)  
**Framework:** [FRAMEWORK.md](./FRAMEWORK.md) · **Validation:** [PHASE2_MODULE_VALIDATION.md](./PHASE2_MODULE_VALIDATION.md)

Run **one task at a time**. Do not redesign UI, rename modules, or remove features. Fix backend before frontend. A task is complete only when all 20 Definition of Done items pass in the browser.

---

## How to use

1. Copy the task block for the module you are fixing.
2. Paste into a new Cursor chat (Agent mode).
3. After the fix, verify against [MODULE_DEFINITION_OF_DONE.md](./MODULE_DEFINITION_OF_DONE.md).
4. Commit with a focused message; push when the module passes sign-off.

**Recommended order:** follow section numbers below (matches [PHASE2_MODULE_VALIDATION.md § Recommended fix order](./PHASE2_MODULE_VALIDATION.md#recommended-fix-order)).

---

## 1. Project Management

Reference module — `/projects` already uses `erp_standard_toolbar` (Phase 1). Close remaining gaps first.

### Task 1A — Delete with workflow guard

```
Fix Project Management delete in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Rules: docs/MAXEK_ERP_RULES.md, docs/FRAMEWORK.md, docs/MODULE_DEFINITION_OF_DONE.md

Add maker-only soft-delete for projects in app.py projects() handler and wire toolbar Delete in templates/projects.html.
Use workflow guard for module_id project_creation.
Block delete when BOQ or DPR child records exist for the project.
Do not change other modules.
Test all 20 DoD items for /projects when done.
```

### Task 1B — Toolbar gaps (search, filters, PDF)

```
Fix Project Management toolbar gaps in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Reference: templates/projects.html (erp_standard_toolbar), docs/FRAMEWORK.md

Add server-side search via apply_list_filters and ?q= on /projects.
Verify status filter, date filter, sort, and refresh work end-to-end with erp_standard_toolbar.
Add Export PDF or document why PDF is deferred (DoD item 15).
Keep Open/View/Edit as row-level actions per FRAMEWORK.md.
Do not redesign UI.
Test all 20 DoD items for /projects when done.
```

### Task 1C — Orphan sub-modules (nav only)

```
Add sidebar or dept-hub links for Project Management orphan routes in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP

Add NAV_GROUPS or projects dashboard tile links for:
- /client-billing (Client Billing)
- /project-photos (Project Photos)
- /securities-guarantees (Securities & Guarantees)

Do not rename modules or change existing URLs.
Follow ui_shell_config.py patterns.
```

---

## 2. Planning & WBS

### Task 2A — Adopt erp_standard_toolbar on cost planning

```
Migrate Planning & WBS list to erp_standard_toolbar in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Template: templates/cost_planning.html
Reference: templates/projects.html, docs/FRAMEWORK.md

Replace page_actions-only toolbar with erp_standard_toolbar on the cost plan list.
Wire module_page_context from erp_framework.py.
Keep WBS embedded tab; do not split into a new module.
Add server Excel export route if missing.
Test DoD on /cost-planning.
```

---

## 3. BOQ

### Task 3A — Adopt erp_standard_toolbar

```
Migrate BOQ management to erp_standard_toolbar in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Template: templates/boq.html
Reference: templates/projects.html, docs/FRAMEWORK.md

Replace legacy erp-table-toolbar with erp_standard_toolbar.
Keep page_actions AI button and existing delete_boq workflow.
Wire export to existing print/export routes where possible.
Do not change BOQ business logic.
Test DoD on /boq-management.
```

### Task 3B — BOQ Multiple Entry edit/view

```
Fix BOQ Multiple Entry CRUD gaps in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Route: /boq-multiple-entry

Add edit and view routes for recent BOQ entries per MAXEK_ERP_AUDIT_REPORT.md partial status.
Reuse existing templates and workflow (boq module).
Do not redesign UI.
```

---

## 4. DPR

### Task 4A — Standard toolbar on DPR list

```
Add erp_standard_toolbar to DPR entry list in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Template: templates/dpr.html
Reference: docs/FRAMEWORK.md

Add search, export, and print on the main measurement list (not only client-bill tab).
Use erp_standard_toolbar and data-erp-row-id on list rows.
Preserve workflow on measurements.
Test DoD on /dpr-entry.
```

---

## 5. Procurement

### Task 5A — PO and GRN toolbar parity

```
Migrate Purchase Order and GRN screens to erp_standard_toolbar in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Templates: templates/purchase_orders.html, store receipt template
Reference: templates/material_request.html (already uses erp_module_toolbar — migrate to erp_standard_toolbar)

Match MR/PR toolbar pattern.
Wire export and print targets.
Test DoD on /purchase/orders and /store-receipt.
```

### Task 5B — RFQ / Quotation Comparison

```
Resolve RFQ and Quotation Comparison nav vs routes in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP

STANDARD_SUB_LABELS references RFQ and quotation comparison but no dedicated routes exist.
Either:
  (A) Add /purchase/rfq and /purchase/quotation-comparison routes with minimal list screens, OR
  (B) Update STANDARD_SUB_LABELS and nav to point to PO-embedded quotation flow in purchase_orders.html and document in docs/PHASE2_MODULE_VALIDATION.md.

Do not remove procurement features. Pick (A) or (B) and implement consistently.
```

---

## 6. Store & Inventory

### Task 6A — GRN, issue, transfer toolbar

```
Migrate Store GRN, Issue, and Transfer to erp_standard_toolbar in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Templates: store-receipt, store-issue, material-transfer templates
Reference: docs/FRAMEWORK.md

Add erp_standard_toolbar with workflow delete where applicable.
Inventory (/inventory) may remain read-only; document if Export/Delete N/A.
Test DoD on each screen.
```

---

## 7. Work Order

### Task 7A — Unified Work Order nav label

```
Align Work Order navigation in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Primary route: /subcontract-payments (subcontract_work_orders)

Add clear "Work Orders" label in Subcontract nav or dept hub pointing to /subcontract-payments WO section.
Do not rename subcontract_payments endpoint.
Document private project WO fields on /projects as secondary entry.
```

---

## 8. Subcontract

### Task 8A — Restore main toolbar access

```
Restore Subcontract department access from main toolbar in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Files: ui_shell_config.py, build_main_toolbar in app.py

subcontract-management is in NAV_GROUPS but removed from main toolbar.
Re-include in build_main_toolbar OR add prominent dept portal link on dashboard.
Validate /dept/subcontract tiles match NAV_GROUPS.
Do not rename modules.
```

### Task 8B — Subcontractor screens toolbar migration

```
Migrate subcontractor list screens to erp_standard_toolbar in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Templates: templates/subcontractors.html, templates/subcontract_payments.html, templates/workers.html

Follow templates/projects.html pattern.
Test DoD on /subcontractors and /subcontract-payments.
```

---

## 9. QA / QC

### Task 9A — QC master standard toolbar

```
Migrate QC Master to erp_standard_toolbar in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Templates: templates/qc_master.html, /quality-control routes

Add erp_standard_toolbar and module_page_context.
Add sidebar entry under Projects or dedicated QC nav if missing.
Test DoD on /qc-master.
```

### Task 9B — NCR / cube register vs labels

```
Audit QA/QC nav labels vs implemented routes in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP

Compare STANDARD_SUB_LABELS and nav entries for NCR, cube register, asphalt testing against actual routes.
Either wire routes or remove/relabel stub entries.
Update docs/PHASE2_MODULE_VALIDATION.md if nav changes.
```

---

## 10. Plant & Fleet

### Task 10A — Sidebar for Plant and Fleet hubs

```
Add Plant and Fleet to sidebar or main toolbar in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Routes: /plant, /fleet

plant-machinery nav group exists but main toolbar uses virtual fleet-mechanical + plant-operations.
Ensure users can reach /plant and /fleet without deep links.
Fix virtual toolbar label → route mismatches (e.g. Tyre Register → fleet_vehicle_documents).
Do not rename modules.
```

### Task 10B — Plant sub-module toolbar sample

```
Migrate one Plant sub-module list to erp_standard_toolbar as template in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP

Pick plant_dashboard or one production list (e.g. asphalt).
Apply erp_standard_toolbar per FRAMEWORK.md.
Document pattern for remaining plant sub-modules in commit message.
```

---

## 11. HR & Payroll

### Task 11A — Leave request nav + toolbar

```
Fix Leave Request module in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Route: /leave-request

Add Workforce nav entry for Leave Request.
Migrate to erp_standard_toolbar.
Workflow module leave_request already registered — verify Delete uses workflow_modals.
Test all 20 DoD items.
```

### Task 11B — Timesheets and salary screens

```
Migrate timesheets and salary processing to erp_standard_toolbar in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Routes: /timesheets, /salary, /timesheet

Clarify nav: /timesheet vs /timesheets — align NAV_GROUPS with working forms.
Apply erp_standard_toolbar where list CRUD exists.
Test DoD per screen.
```

### Task 11C — Staff/attendance/payroll migration to standard toolbar

```
Upgrade HR screens from erp_module_toolbar to erp_standard_toolbar in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Templates: staff.html, attendance.html, payroll.html

Follow templates/projects.html.
Preserve existing workflow modules.
Test DoD on /staff, /attendance, /payroll.
```

---

## 12. Finance & Accounts

### Task 12A — Petty cash / voucher list toolbar

```
Add erp_standard_toolbar to Accounts voucher list screens in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP

Start with /petty_cash and /accounts/receipts as pilot.
Use erp_framework export helpers where applicable.
Treasury stubs (CSV import, email alerts) — document as Phase 2+ if not fixing now.
Test DoD on pilot screens.
```

### Task 12B — Treasury sub-screens (incremental)

```
Migrate one Treasury list screen to erp_standard_toolbar in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Route: /treasury/bank-guarantees (reference — already ✅ in gap audit)

Use bank-guarantees as pattern for payments, receipts, cheques lists.
One screen per task; do not batch entire treasury in one pass.
```

---

## 13. Administration

### Task 13A — Corporate DMS nav

```
Add Corporate DMS to Settings navigation in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Route: /settings/corporate-dms

Link from Settings NAV_GROUPS or settings.html.
Optional: erp_standard_toolbar on DMS document list for admin users.
Test module opens from menu (DoD item 2).
```

### Task 13B — Office admin registers toolbar

```
Migrate one Office Administration register to erp_standard_toolbar in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Hub: /office-admin

Pick inward or outward register as pilot.
Follow FRAMEWORK.md.
```

---

## 14. Reports

### Task 14A — Wire corporate hub stubs

```
Wire one stub report in corporate reports hub in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Files: report_registry.py, templates/corporate_reports_hub.html

Change one stub entry to wired with /reports/run routing per FRAMEWORK.md.
Add erp_report_runner on source module list if needed.
Test Run Report (DoD item 17).
```

### Task 14B — Legacy /reports scope

```
Clarify or expand legacy /reports route in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Route: /reports (currently attendance + salary only)

Either redirect Project Reports nav to /reports/corporate?category=projects OR add project report links to /reports.
Update NAV_GROUPS label if needed. Do not remove attendance/salary reports.
Document decision in docs/PHASE2_MODULE_VALIDATION.md.
```

---

## Cross-cutting tasks

### Task X1 — Migrate erp_module_toolbar → erp_standard_toolbar (batch)

```
Migrate remaining erp_module_toolbar screens to erp_standard_toolbar in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP

Grep templates for erp_module_toolbar. Migrate one module per commit:
clients, staff, attendance, payroll, material_request, purchase_request, store_materials.

Reference: templates/projects.html, docs/FRAMEWORK.md
Test DoD after each migration.
```

### Task X2 — Orphan module nav (gap audit)

```
Add NAV_GROUPS entries for gap-audit orphan modules in MAXEK ERP.

Project: C:\Users\rajee\Documents\New project\MAXEK_ERP
Reference: docs/MODULE_GAP_AUDIT_14.md

Add menu entries for modules with routes but no sidebar:
- /project-photos
- /client-billing
- /leave-request
- /settings/corporate-dms
- /fleet (or link from Office hub)
- /plant

One nav change per commit where possible.
```

---

## Task completion checklist

Before marking any task done:

- [ ] All 20 items in [MODULE_DEFINITION_OF_DONE.md](./MODULE_DEFINITION_OF_DONE.md) pass
- [ ] No new 404/500 errors in browser DevTools
- [ ] [MAXEK_ERP_RULES.md](./MAXEK_ERP_RULES.md) followed (no UI redesign, no unrelated modules)
- [ ] Focused git commit with clear message
- [ ] [PHASE2_MODULE_VALIDATION.md](./PHASE2_MODULE_VALIDATION.md) updated if nav or scope changed
