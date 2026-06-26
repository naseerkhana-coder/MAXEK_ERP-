# Phase 2 — Cursor Tasks

> **Rules:** Follow [MAXEK_ERP_RULES.md](./MAXEK_ERP_RULES.md) for all development work.

Copy-paste each task into a new Cursor chat. Follow [MAXEK_ERP_RULES.md](./MAXEK_ERP_RULES.md) on every task: no UI redesign, no module renames, no unrelated file changes, fix backend before frontend, test before commit.

**Project path:** `C:\Users\rajee\Documents\New project\MAXEK_ERP`  
**Framework reference:** [FRAMEWORK.md](./FRAMEWORK.md)  
**Validation baseline:** [PHASE2_MODULE_VALIDATION.md](./PHASE2_MODULE_VALIDATION.md)  
**Done criteria:** [MODULE_DEFINITION_OF_DONE.md](./MODULE_DEFINITION_OF_DONE.md) — all 20 browser checks must pass.

Use `move_agent_to_root` with the project path before editing.

---

## Fix order overview

| Order | Module area | Priority |
|-------|-------------|----------|
| 1 | Project Management | Reference implementation |
| 2 | BOQ | High traffic |
| 3 | DPR | High traffic |
| 4 | Procurement | RFQ/PO/GRN gaps |
| 5 | Subcontract + Work Order | Hidden nav |
| 6 | Store & Inventory | Toolbar parity |
| 7 | HR & Payroll | Leave/timesheets |
| 8 | Finance & Accounts | Voucher lists |
| 9 | Plant & Fleet | Virtual nav mapping |
| 10 | QA / QC | Registers vs labels |
| 11 | Administration | DMS + registers |
| 12 | Reports | Hub stubs |
| 13 | Planning & WBS | Toolbar migration |

---

## 1. Project Management

### Task: Project Management — Delete with workflow guard

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, add maker-only delete for projects:

1. Add POST delete handling in projects() in app.py with workflow guard (module_id project_creation).
2. Block delete when child records exist (BOQ, DPR, or other linked tables — check existing schema).
3. Wire toolbar Delete on erp_standard_toolbar via workflow_modals or erp-framework.js delete flow.
4. Do NOT change other modules.

Follow MAXEK_ERP_RULES.md and FRAMEWORK.md. Test: create test project, verify delete blocked when children exist, verify workflow roles. Commit when all MODULE_DEFINITION_OF_DONE items for delete pass.
```

### Task: Project Management — Toolbar gaps (status filter, server search)

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, complete Project Management list toolbar gaps on /projects:

1. Verify server-side filtering for q, status, date_from, date_to, sort GET params in projects() using erp_framework.apply_list_filters or equivalent.
2. Ensure erp_standard_toolbar status_options and sort_options actually filter the list (not UI-only).
3. Document in template comments that Open/View/Edit remain row-level per FRAMEWORK.md.
4. Add date range filters if missing from toolbar.
5. Do NOT redesign projects.html layout.

Test full toolbar checklist in PHASE2_MODULE_VALIDATION.md Module 1. Commit only this module.
```

### Task: Project Management — Clients toolbar upgrade

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, upgrade templates/clients.html from erp_module_toolbar to erp_standard_toolbar matching projects.html pattern:

- Add ModuleConfig for clients in erp_framework.py if missing.
- Wire server export route if only client CSV exists.
- Keep row-level workflow actions. Scope: clients module only.
```

---

## 2. BOQ

### Task: BOQ — Adopt erp_module_toolbar

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, replace templates/boq.html legacy erp-table-toolbar with erp_module_toolbar matching clients.html:

- search_placeholder, add_url to existing new BOQ form anchor
- export_name='boq' or wire server export if /boq export route added
- print_target pointing to BOQ list table
- Keep existing page_actions AI button via extra_buttons
- Preserve workflow delete (form_action=delete_boq) on rows

Do not remove BOQ Multiple Item Entry route. Test list search, export, print. Commit: BOQ toolbar only.
```

### Task: BOQ — Server Excel export

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, add GET /boq-management/export (or equivalent) using erp_framework.export_rows_to_excel for BOQ list rows. Wire export_url on erp_module_toolbar. Keep client CSV as fallback only if needed. BOQ module files only.
```

---

## 3. DPR

### Task: DPR — Standard toolbar on measurement list

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, add erp_module_toolbar to templates/dpr.html main measurement list section:

- Client search on measurement table
- Export Excel (client CSV minimum; server export if straightforward)
- Print target for measurement list region
- Do not change DPR workflow logic or client-bill tab export behavior

Test DPR entry, pending, and costing tabs still work. DPR templates and routes only.
```

### Task: DPR — List filters

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, add status and date filters to DPR list (project + date range minimum) via GET params and backend filter in dpr route handler. Integrate into toolbar extra_buttons or migrate to erp_standard_toolbar if Projects pattern fits. DPR scope only.
```

---

## 4. Procurement

### Task: Procurement — RFQ / Quotation Comparison routes or doc

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, resolve RFQ and Quotation Comparison gap in ui_shell_config.py STANDARD_SUB_LABELS vs actual routes:

Option A: Add dedicated routes and list templates for RFQ and quotation comparison.
Option B: Update STANDARD_SUB_LABELS and sub-toolbar to point to PO-embedded quotation flow in purchase_orders.html, and add in-app help text on PO screen.

Pick the option that matches existing business flow (check purchase_orders.html for embedded quotations). Update nav only — do not remove MR/PR/PO/GRN. Document choice in a comment in ui_shell_config.py.
```

### Task: Procurement — PO and GRN toolbar

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, migrate purchase_orders.html and GRN list template from page_actions-only to erp_module_toolbar (match material_request.html). Preserve workflow modals and row actions. Procurement templates only.
```

---

## 5. Subcontract + Work Order

### Task: Subcontract — Restore main toolbar access

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, restore subcontract-management visibility:

1. Review build_main_toolbar() in ui_shell_config.py — currently pops subcontract-management.
2. Either re-add to MAIN_TOOLBAR_SLUGS or add prominent link from Projects/Procurement toolbar to /dept/subcontract.
3. Validate /dept/subcontract portal tiles match NAV_GROUPS subcontract-management items.
4. Do not rename modules. Nav config + dept portal template only unless a single link addition is needed elsewhere.
```

### Task: Work Order — Unify naming and entry point

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, align Work Order user entry:

1. Document primary WO route (/subcontract-payments vs project form WO fields) in template page title.
2. Add sub-toolbar or dept tile label "Work Orders" pointing to subcontract_work_orders list.
3. Add erp_module_toolbar to subcontract payments/WO list if missing.
Subcontract module files only.
```

---

## 6. Store & Inventory

### Task: Store — Receipt, Issue, Transfer toolbar parity

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, add erp_module_toolbar to store receipt, store issue, and material transfer list templates (match store_materials.html). Include search, print, and export_name per screen. Preserve existing POST handlers. Store templates only.
```

### Task: Store — Inventory list export

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, add export and print to /inventory read-only list via erp_module_toolbar or page_actions extension. No schema changes unless required for export columns.
```

---

## 7. HR & Payroll

### Task: HR — Leave and timesheets toolbar

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, migrate leave-request and timesheet list templates to erp_module_toolbar (match staff.html). Keep attendance and payroll unchanged unless broken. HR templates only.
```

### Task: HR — Payroll salary screen alignment

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, review salary/payroll split screens — ensure payroll.html toolbar pattern is consistent and /reports links for salary reports are correct. Fix only HR payroll templates and routes.
```

---

## 8. Finance & Accounts

### Task: Finance — Payment voucher list toolbar

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, add erp_module_toolbar to payment voucher list template under /accounts. Wire search (client minimum), print, export. Do not change voucher posting logic. Accounts templates only.
```

### Task: Finance — Receipt and journal voucher lists

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, repeat erp_module_toolbar adoption for receipt voucher and journal voucher list screens. Match payment voucher task pattern. One commit per voucher type or single focused commit for all three list pages.
```

### Task: Finance — Treasury stub report wiring

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, audit report_registry.py treasury entries marked stub — wire at least bank reconciliation and cash book reports to existing print routes or mark as screen-only in corporate_reports_hub.html. Reports config only unless a small route fix is required.
```

---

## 9. Plant & Fleet

### Task: Plant & Fleet — Fix virtual toolbar route mapping

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, fix ui_shell_config.py VIRTUAL_TOOLBAR_ENTRIES mismatches:

- Tyre Register label → verify fleet_vehicle_documents is correct endpoint or rename label to match actual screen
- Breakdown Register → fleet_running_log
- Audit all fleet-mechanical and plant-operations items against app.py route names

Update labels or active_endpoints only — no module renames. Test each sub-toolbar link loads without 404.
```

### Task: Plant — Hub to list toolbar migration

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, add erp_module_toolbar to plant asphalt and RMC production list views (highest traffic plant screens). Plant templates only.
```

---

## 10. QA / QC

### Task: QA/QC — QC master toolbar

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, add erp_module_toolbar to /qc-master list template. Full CRUD already exists — wire search, export, print. QC templates only.
```

### Task: QA/QC — NCR and cube register nav truth

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, audit quality-control nav items vs routes for NCR, cube register, asphalt testing. Either implement missing list screens or remove/hide stub labels from NAV_GROUPS and STANDARD_SUB_LABELS. Document in template if screen-only.
```

---

## 11. Administration

### Task: Administration — Office registers toolbar

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, add erp_module_toolbar to inward/outward register list templates under office-admin. Search + print minimum. Admin templates only.
```

### Task: Administration — Corporate DMS nav

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, add Corporate DMS (/settings/corporate-dms) to settings or admin-compliance sub-toolbar with correct label. Verify route loads. Nav config + one settings link only.
```

---

## 12. Reports

### Task: Reports — Wire corporate hub stubs

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, open templates/corporate_reports_hub.html and report_registry.py:

1. For each report marked stub, either wire to /reports/run?report=slug or link to module print route.
2. Update hub card status from stub to wired or screen-only with clear user message.
3. Do not remove legacy /reports until redirects are documented.

Reports registry and hub template only.
```

### Task: Reports — Legacy /reports deprecation plan

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, add redirect or banner on GET /reports pointing users to /reports/corporate for module reports. Keep attendance/salary quick access if still needed. Minimal template change only.
```

---

## 13. Planning & WBS

### Task: Planning — Adopt module toolbar on cost planning

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, replace page_actions-only export/print on cost-planning list area with erp_module_toolbar. Preserve WBS tab embedding at #wbs-view — do not split WBS to a new route unless already planned. Planning templates only.
```

### Task: Planning — WBS standalone access (optional)

```
In C:\Users\rajee\Documents\New project\MAXEK_ERP, if product owner wants WBS as standalone screen: add /wbs route that renders cost-planning template with #wbs-view focused (deep link). Otherwise skip and document tab-only access in FRAMEWORK.md. User must confirm before implementing.
```

---

## Commit convention

After each task:

```bash
git add <scoped files only>
git commit -m "fix(<module>): <short description per conventional commits>"
```

Phase 2 doc commit (already done separately):

```
docs: Phase 2 module validation and framework documentation
```

---

## Task completion checklist

Before marking any task done, verify in browser:

- [ ] Module opens from nav without 404
- [ ] New / Save / View / Edit / Delete work (where applicable)
- [ ] Search and filters work
- [ ] Export Excel and Print work
- [ ] No console errors
- [ ] All 20 items in MODULE_DEFINITION_OF_DONE.md pass for that screen
