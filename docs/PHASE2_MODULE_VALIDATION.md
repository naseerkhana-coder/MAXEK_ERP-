# Phase 2 — Module Validation

**Project:** MAXEK Construction ERP  
**Repository:** https://github.com/naseerkhana-coder/NASEER  
**Validated:** June 2026 (read-only audit + framework doc backfill)

This document records Phase 2 validation of all 14 department modules against the shared framework described in [FRAMEWORK.md](./FRAMEWORK.md).

**Related standards:**

- [MODULE_DEFINITION_OF_DONE.md](./MODULE_DEFINITION_OF_DONE.md) — 20-item browser checklist for sign-off
- [MAXEK_ERP_RULES.md](./MAXEK_ERP_RULES.md) — development constraints for all fixes
- [PHASE2_CURSOR_TASKS.md](./PHASE2_CURSOR_TASKS.md) — copy-paste fix tasks per module

---

## Key findings

1. **All 14 modules exist** — routes, templates, and backend code are present. No greenfield modules required.
2. **Framework adoption is partial** — ~8 screens use `erp_module_toolbar`; only **Projects** uses full `erp_standard_toolbar`. Most modules still use `page_actions` + legacy toolbars.
3. **`FRAMEWORK.md` was missing at audit time** — now documents the actual macro contract (`erp_module_toolbar` vs `erp_standard_toolbar`).
4. **Subcontract and Plant are hidden from the main toolbar** — `build_main_toolbar()` drops `subcontract-management` and `plant-machinery`; access is via department portals and virtual fleet/plant entries.
5. **Project Management is the best reference** — workflow, hub modal, `erp_standard_toolbar` — but still lacks Delete, full filter wiring, and PDF export on the list.
6. **Procurement labels exceed routes** — RFQ and Quotation Comparison appear in `STANDARD_SUB_LABELS` without dedicated list routes.

---

## Framework baseline

| Artifact | Path |
|----------|------|
| Toolbar macros | `templates/macros/erp_ui.html` |
| Shell / nav | `ui_shell_config.py` |
| Client export/print | `static/js/maxek-ui.js` |
| Full toolbar CRUD | `static/js/erp-framework.js` |
| Python helpers | `erp_framework.py` |

**What `erp_module_toolbar` provides:** Search, Add New, Export Excel, Print.

**Not in the macro (per-screen today):** Open, View, Edit, Delete, Status filter, Date filter, Sort, Refresh, Export PDF — typically row-level, `page_actions`, or absent.

---

## Master summary — 14 modules

| # | Module | Exists | Overall | Toolbar | CRUD | Navigation | Reports |
|---|--------|--------|---------|---------|------|------------|---------|
| 1 | Project Management | ✅ | ⚠️ Partial | ⚠️ | ⚠️ | ✅ | ⚠️ |
| 2 | Planning & WBS | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ✅ |
| 3 | BOQ | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 4 | DPR | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 5 | Procurement | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 6 | Store & Inventory | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 7 | Work Order | ✅ | ⚠️ Partial | ⚠️ | ✅ | ⚠️ | ⚠️ |
| 8 | Subcontract | ✅ | ⚠️ Partial | ⚠️ | ✅ | ⚠️ | ⚠️ |
| 9 | QA / QC | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 10 | Plant & Fleet | ✅ | ⚠️ Partial | ⚠️ | ✅ | ⚠️ | ⚠️ |
| 11 | HR & Payroll | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 12 | Finance & Accounts | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 13 | Administration | ✅ | ⚠️ Partial | ⚠️ | ✅ | ✅ | ⚠️ |
| 14 | Reports | ✅ | ⚠️ Partial | ⚠️ | N/A | ✅ | ⚠️ |

**Legend:** ✅ Meets standard · ⚠️ Partial · ❌ Missing

**Missing entirely:** 0 modules.

---

## 1. Project Management

**Overall:** ⚠️ Partial — best framework reference; gaps in Delete and filters.

### Code map

| Area | Route(s) | Template | Backend |
|------|----------|----------|---------|
| Dept hub | `/projects/dashboard` | dashboard pattern | `projects_dashboard()` |
| Project CRUD | `/projects` | `projects.html` | `projects()` → `projects` table, workflow `project_creation` |
| Client master | `/clients` | `clients.html` | `clients()` |
| Documents | `/project-documents` | `project_documents_register.html` | columns on `projects` |
| Photos | `/project-photos` | photo templates | `project_photos` |
| Client billing | `/client-billing` | billing templates | `client_bills` |
| Securities | `/securities-guarantees` | securities template | guarantees tables |

**Nav:** `NAV_GROUPS` slug `project-management`; main toolbar **Projects**.

### Toolbar checklist (`/projects`)

| Control | Status | Notes |
|---------|--------|-------|
| New | ✅ | `erp_standard_toolbar` → `#add-project` |
| Open | ⚠️ | Project 360 hub modal, not toolbar Open |
| View | ⚠️ | Row View link |
| Edit | ⚠️ | Row Edit (workflow-gated); approved → Hub only |
| Delete | ❌ | No delete handler for projects |
| Search | ⚠️ | `search_name='q'` wired; verify server-side filter |
| Status filter | ⚠️ | Options in toolbar; verify list filtering |
| Date filter | ❌ | Not on list |
| Sort | ⚠️ | Sort options in toolbar; verify backend |
| Refresh | ⚠️ | Via toolbar refresh if wired |
| Export Excel | ✅ | Server `/projects/export` |
| Export PDF | ⚠️ | `?print=1` placeholder |
| Print | ✅ | `data-erp-print` on `#project-list` |

### CRUD trace

```
Add New → #add-project → POST /projects → INSERT projects + workflow
View    → GET /projects?view={id} → read-only card + workflow tabs
Edit    → GET /projects?edit={id} → role check → POST update
List    → GET /projects → SELECT projects (+ client join)
Delete  → NOT IMPLEMENTED
```

### Navigation

- ✅ Dashboard → Project Dashboard → module tiles
- ✅ Breadcrumbs: Home > Projects
- ✅ Back on view screen
- ⚠️ Sub-screens (billing, photos, documents) use mixed legacy layouts

### Reports

- ⚠️ Nav **Project Reports** → `/reports` (attendance/salary only)
- ✅ Corporate hub has project category entries (mixed wired/stub)

### Phase 2 gaps

- Implement Delete with workflow guard and child-record checks (BOQ/DPR)
- Complete server-side status/search/sort filtering
- Align Open/View/Edit policy with [FRAMEWORK.md](./FRAMEWORK.md)

---

## 2. Planning & WBS

**Overall:** ⚠️ Partial

| Area | Detail |
|------|--------|
| Routes | `/cost-planning`, `/wbs` → redirect to `#wbs-view`, APIs `/api/cost-planning/*` |
| Service | `cost_planning_service.py` |
| Toolbar | `page_actions` (Export, Print, Reports) — not `erp_module_toolbar` |
| CRUD | ✅ Cost planning and WBS operations |
| Nav | ✅ `engineering-smartqto` / Planning toolbar |
| Reports | ✅ Planning-related reports in hub |

**Gaps:** No standard status/date filters; WBS embedded as tab, not standalone screen; migrate toolbar.

---

## 3. BOQ

**Overall:** ⚠️ Partial

| Area | Detail |
|------|--------|
| Routes | `/boq-management`, `/boq-multiple-entry`, `/boq-print/<id>` |
| Toolbar | Legacy table search; New in `page_actions` |
| CRUD | ✅ Full + workflow + delete (`form_action=delete_boq`) |
| Nav | ✅ Under Projects sub-labels and Planning |
| Reports | ⚠️ Print route exists; no list Excel/PDF |

**Gaps:** Adopt `erp_module_toolbar` or `erp_standard_toolbar`; wire export.

---

## 4. DPR

**Overall:** ⚠️ Partial

| Area | Detail |
|------|--------|
| Routes | `/dpr-entry`, pending/costing tabs, print/export on client-bill tab |
| Toolbar | No standard module toolbar on main measurement list |
| CRUD | ✅ Workflow on measurements |
| Nav | ✅ DPR in Projects sub-labels |
| Reports | ⚠️ Module print routes; hub stubs |

**Gaps:** Add search/export toolbar to main list; standardize filters.

---

## 5. Procurement

**Overall:** ⚠️ Partial

| Area | Detail |
|------|--------|
| Routes | MR, PR, PO, GRN under `store-procurement` nav |
| Toolbar | MR + PR use `erp_module_toolbar`; PO/GRN use `page_actions` only |
| CRUD | ✅ Full procurement flow |
| Nav | ✅ Procurement main toolbar + sub-labels |
| Reports | ⚠️ Partial hub wiring |

**Gaps:** RFQ and Quotation Comparison in `STANDARD_SUB_LABELS` but **no dedicated routes** (quotations embedded in PO); migrate PO/GRN to standard toolbar.

---

## 6. Store & Inventory

**Overall:** ⚠️ Partial

| Area | Detail |
|------|--------|
| Routes | `/store` hub, `/store-receipt`, `/store-issue`, `/material-transfer`, `/inventory` |
| Toolbar | `store_materials` uses `erp_module_toolbar`; receipt/issue/transfer legacy |
| CRUD | ✅ Store transactions |
| Nav | ✅ Virtual **Store** toolbar (`store-section`) |
| Reports | ⚠️ Limited store reports |

**Gaps:** GRN/issue/transfer toolbar parity; inventory read-focused.

---

## 7. Work Order

**Overall:** ⚠️ Partial

| Area | Detail |
|------|--------|
| Routes | `/subcontract-payments` (subcontract WOs + payments); private WO fields on `/projects` |
| Toolbar | Legacy / none unified |
| CRUD | ✅ WO records in subcontract tables |
| Nav | ⚠️ Not in main toolbar as "Work Order" |
| Reports | ⚠️ Payment/WO prints partial |

**Gaps:** No unified Work Order module label; align naming and nav with subcontract.

---

## 8. Subcontract

**Overall:** ⚠️ Partial

| Area | Detail |
|------|--------|
| Routes | `/subcontract`, `/subcontractors`, `/workers`, `/sub-billing`, `/subcontract-payments` |
| Toolbar | Legacy on most screens |
| CRUD | ✅ Subcontractor, worker, billing flows |
| Nav | ⚠️ `subcontract-management` in `NAV_GROUPS` but **removed from main toolbar** |
| Reports | ⚠️ Billing prints |

**Gaps:** Restore main-toolbar or prominent dept portal access; migrate toolbars; validate `/dept/subcontract` tiles.

---

## 9. QA / QC

**Overall:** ⚠️ Partial

| Area | Detail |
|------|--------|
| Routes | `/qc-master`, `/quality-control`, `/plant/qc` |
| Toolbar | Legacy / custom per screen |
| CRUD | ✅ QC master CRUD |
| Nav | ✅ `qc` in main toolbar |
| Reports | ⚠️ Cube register, NCR, asphalt testing — labels vs stubs |

**Gaps:** Standard toolbar; clarify NCR/cube register implementations vs nav labels.

---

## 10. Plant & Fleet

**Overall:** ⚠️ Partial

| Area | Detail |
|------|--------|
| Routes | `/plant/*`, `/fleet/*`, treasury equipment costing |
| Toolbar | Legacy; hub-based access |
| CRUD | ✅ Production, fleet, maintenance records |
| Nav | ⚠️ `plant-machinery` hidden; virtual `fleet-mechanical` + `plant-operations` |
| Reports | ⚠️ Plant production reports partial |

**Gaps:** Virtual sub-toolbar labels don't match all routes (e.g. Tyre Register → `fleet_vehicle_documents`); many sub-modules only via `/plant` hub.

---

## 11. HR & Payroll

**Overall:** ⚠️ Partial

| Area | Detail |
|------|--------|
| Routes | `/staff`, `/attendance`, `/payroll`, `/leave-request`, `/timesheet`, `/timesheets` |
| Toolbar | staff, attendance, payroll use `erp_module_toolbar` |
| CRUD | ✅ Employee, attendance, payroll workflows |
| Nav | ✅ HR & Payroll main toolbar |
| Reports | ⚠️ `/reports` limited to attendance/salary |

**Gaps:** Leave/timesheets legacy toolbars; salary screen separate from payroll toolbar pattern.

---

## 12. Finance & Accounts

**Overall:** ⚠️ Partial

| Area | Detail |
|------|--------|
| Routes | `/accounts/*`, `/treasury/*`, `/petty_cash` |
| Toolbar | Sub-toolbar grouped (Masters \| Transactions \| Books) — good nav UX |
| CRUD | ✅ Voucher and ledger operations |
| Nav | ✅ Accounts main toolbar |
| Reports | ⚠️ Many treasury stubs |

**Gaps:** Individual voucher list screens lack `erp_module_toolbar` / `erp_standard_toolbar`.

---

## 13. Administration

**Overall:** ⚠️ Partial

| Area | Detail |
|------|--------|
| Routes | `/office-admin`, inward/outward, letters, agreements, `/settings/corporate-dms` |
| Toolbar | Legacy forms and registers |
| CRUD | ✅ Office register CRUD |
| Nav | ✅ `admin-compliance` slug |
| Reports | ⚠️ Letter/agreement prints |

**Gaps:** Corporate DMS not prominent in settings nav; legacy form layouts.

---

## 14. Reports

**Overall:** ⚠️ Partial (module is the reporting layer itself)

| Area | Detail |
|------|--------|
| Routes | `/reports/corporate` (hub), `/reports`, `/reports/workflow-audit`, module print routes |
| Toolbar | Hub uses report cards; legacy `/reports` minimal |
| CRUD | N/A |
| Nav | ✅ Reports main toolbar |
| Reports | ⚠️ Corporate hub wired vs stub counts; legacy `/reports` = attendance + salary only |

**Gaps:** Wire stubs in corporate hub; expand or deprecate legacy `/reports`; document "open module → print" flows.

---

## Recommended fix order

1. **Project Management** — Delete policy, toolbar filter gaps, reference completion
2. **BOQ + DPR** — high traffic; adopt standard toolbar
3. **Procurement** — PO, GRN, RFQ/quotation comparison (routes or document embedded flow)
4. **Subcontract + Work Order** — restore nav visibility; unify WO naming
5. **Store & Inventory** — receipt/issue/transfer toolbar parity
6. **HR & Payroll** — leave, timesheets, salary screens
7. **Finance & Accounts** — voucher list screens (large surface)
8. **Plant & Fleet** — virtual toolbar ↔ route mapping
9. **QA/QC** — NCR/cube registers vs labels
10. **Administration** — DMS nav + office registers
11. **Reports** — wire corporate hub stubs
12. **Planning & WBS** — toolbar migration (lower traffic than BOQ/DPR)

Detailed copy-paste tasks: [PHASE2_CURSOR_TASKS.md](./PHASE2_CURSOR_TASKS.md).

---

## Sign-off

A module is **not** Phase 2 complete until all 20 items in [MODULE_DEFINITION_OF_DONE.md](./MODULE_DEFINITION_OF_DONE.md) pass. Use the sign-off template in that document per module.
