# MAXEK ERP — Shared UI Framework

This document describes the **actual** shared framework in the codebase as of Phase 2 validation. Use it when migrating department modules to a consistent list-page pattern.

**Related:** [MAXEK_ERP_RULES.md](./MAXEK_ERP_RULES.md) · [MODULE_DEFINITION_OF_DONE.md](./MODULE_DEFINITION_OF_DONE.md) · [PHASE2_MODULE_VALIDATION.md](./PHASE2_MODULE_VALIDATION.md)

---

## Architecture overview

| Layer | Location | Role |
|-------|----------|------|
| Toolbar macros | `templates/macros/erp_ui.html` | List-page chrome (`erp_module_toolbar`, `erp_standard_toolbar`) |
| Shell / navigation | `ui_shell_config.py` | Main toolbar order, sub-toolbar labels, virtual nav groups |
| Client utilities | `static/js/maxek-ui.js` | Client search, CSV export, scoped print |
| Full toolbar JS | `static/js/erp-framework.js` | Row selection + toolbar CRUD for `erp_standard_toolbar` |
| Python helpers | `erp_framework.py` | Breadcrumbs, list filters, Excel export, report routing |
| Reports | `report_registry.py`, `/reports/run` | Corporate hub and standard run routing |
| Base layout | `templates/base_maxek.html` | Loads shell JS, breadcrumbs, department sub-bar |

**Reference implementation:** Project Management (`/projects`, `templates/projects.html`) — uses `erp_standard_toolbar` with workflow modals and server export.

**Adoption snapshot (Phase 2 audit):** ~8 list screens use `erp_module_toolbar`; only **Projects** uses the full `erp_standard_toolbar`. Most other modules still rely on `page_actions` and legacy `erp-table-toolbar`.

---

## Toolbar macros — what the framework provides vs what modules add

### `erp_module_toolbar` (minimal, widely adopted)

Defined in `templates/macros/erp_ui.html`. Layout:

```
┌─────────────────────────────────────────────────────┐
│  Search  |  Add New  |  Export Excel  |  Print     │
└─────────────────────────────────────────────────────┘
```

**Provided by the macro:**

| Control | Mechanism |
|---------|-----------|
| Search | Client-side filter (`data-table-search`) **or** server GET when `search_name` is set |
| Add New | Link (`add_url`), trigger selector (`add_trigger_selector`), or onclick |
| Export Excel | Server URL (`export_url`) **or** client CSV (`export_name` → `data-table-export`) |
| Print | New-tab URL (`print_url`) **or** scoped print (`data-erp-print` + `print_target`) |
| Extra actions | Raw HTML via `extra_buttons` (e.g. AI assist on BOQ) |

**Not in the macro — modules add these at row or page level:**

| Control | Typical pattern |
|---------|-----------------|
| Open | Row link, hub modal (e.g. Project 360), or double-click |
| View | Row **View** link → `?view=<id>` |
| Edit | Row **Edit** link → `?edit=<id>` (often workflow-gated) |
| Delete | Row delete form, `maker_row_actions`, or workflow modal |
| Status filter | Custom dropdown/tabs in template (not standardized) |
| Date filter | Per-screen date inputs (rare on lists) |
| Sort | Column headers or custom controls |
| Refresh | Full page reload or custom button in `page_actions` |
| Export PDF | Dedicated print route or `?print=1` (not in macro) |

**Screens using `erp_module_toolbar` today:** `clients`, `staff`, `attendance`, `payroll`, `material_request`, `purchase_request`, `store_materials`, `erp_admin/customers`.

**Example:**

```jinja
{% from 'macros/erp_ui.html' import erp_module_toolbar, erp_module_table_panel %}

<div class="erp-module-layout">
  {{ erp_module_toolbar(
    search_placeholder='Search clients...',
    add_url='#add-client',
    export_name='clients',
    print_target='#client-records'
  ) }}
  {% call erp_module_table_panel(id='client-records', title='Client List') %}
    <table>...</table>
  {% endcall %}
</div>
```

**Macro parameters:**

| Param | Purpose |
|-------|---------|
| `search_placeholder` | Input hint text |
| `search_name` | GET form field for server-side search (omit for client-only) |
| `add_url` / `add_trigger_selector` / `add_onclick` | New record entry |
| `add_label` | Button label (default "Add New") |
| `export_url` | Full URL for server Excel export |
| `export_name` | Client CSV filename stem (`data-table-export`) |
| `print_enabled` | Show Print button (default true) |
| `print_url` | Open print view in new tab |
| `print_target` | CSS selector for scoped table print |
| `extra_buttons` | Additional toolbar HTML |

---

### `erp_standard_toolbar` (full Phase 1 target)

Same file. Intended end-state toolbar with three groups:

```
CRUD:     New · Open · View · Edit · Delete
Filters:  Search · Status · Date range · Sort · Refresh
Export:   Excel · PDF · Print
```

Requires `static/js/erp-framework.js`. User must **select a table row** before Open/View/Edit/Delete.

**Currently wired on:** `templates/projects.html` only.

```jinja
{{ erp_standard_toolbar(
  module_endpoint='projects',
  search_name='q',
  new_url=url_for('projects') ~ '#add-project',
  export_url=url_for('projects_export'),
  export_pdf_url=url_for('projects') ~ '?print=1',
  print_target='#project-list',
  table_target='#project-list',
  delete_table='projects',
  module_id='project_creation',
  status_options=[{'value': 'Active', 'label': 'Active'}],
  sort_options=[{'value': 1, 'label': 'Name'}]
) }}
```

**Table rows for toolbar CRUD:**

```html
<tr data-erp-row-id="{{ row.id }}"
    data-erp-row-status="{{ row.status }}"
    data-erp-row-date="{{ row.created_at }}">
```

Include `workflow_modals()` when Delete should follow workflow rules.

`erp_module_toolbar` is documented as a backward-compatible wrapper; new migrations should target `erp_standard_toolbar` where full CRUD from the toolbar is required.

---

## `ui_shell_config.py` — navigation and toolbar

### Main toolbar (`MAIN_TOOLBAR_SLUGS`)

Ordered top-level departments:

Dashboard → Projects → Planning → Procurement → Store → Accounts → HR & Payroll → Fleet & Mechanical → Plant Operations → Quality Control → Administration → Reports → Settings

### Virtual toolbar entries (`VIRTUAL_TOOLBAR_ENTRIES`)

Some toolbar slots are **not** direct `NAV_GROUPS` slugs:

| Slug | Purpose |
|------|---------|
| `store-section` | Store hub split from Procurement (receipt, issue, transfer, stock) |
| `fleet-mechanical` | Fleet subset (vehicles, fuel, job card, tyre register, breakdown) |
| `plant-operations` | Plant production subset (asphalt, RMC, crusher, dispatch) |

### Hidden from main toolbar (`build_main_toolbar`)

These `NAV_GROUPS` slugs exist in code but are **removed** from the top toolbar:

- `plant-machinery` (replaced by virtual fleet + plant entries)
- `subcontract-management` (reachable via `/dept/subcontract` portal)
- `approvals`, `erp-administration`

### Sub-toolbar standard labels (`STANDARD_SUB_LABELS`)

Per-department ordered labels for the department sub-bar. Example for Procurement:

Material Request → Purchase Request → RFQ → Quotation Comparison → Purchase Order → GRN

**Note:** RFQ and Quotation Comparison appear in labels but may not have dedicated routes (quotations can be embedded in PO screens).

### Helpers

| Function | Purpose |
|----------|---------|
| `build_main_toolbar(nav_groups)` | Ordered main toolbar from `NAV_GROUPS` + virtual entries |
| `filter_sub_toolbar_items(nav_group)` | Align sub-bar items to `STANDARD_SUB_LABELS` |
| `resolve_active_toolbar_slug(endpoint, ...)` | Highlight correct main toolbar tab |

---

## `static/js/maxek-ui.js` — export and print

Loaded globally from `base_maxek.html`. Handles list utilities for **both** toolbar macros.

### Client-side search

- Inputs with `data-table-search` or `data-erp-module-search` filter visible table rows in the nearest module table panel.
- If the search input has a `name` attribute inside a GET form, submission is left to the server (no client filter).

### Export Excel (client CSV)

- Buttons with `data-table-export="<filename>"` export **visible** table rows to `<filename>.csv`.
- If `data-export-url` is set, navigates to server export instead.
- Server export is preferred for large lists and filtered data — add `/module/export` routes via `erp_framework.export_rows_to_excel()`.

### Print

- Buttons with `data-erp-print` and optional `data-erp-print-target="#selector"` print only the targeted region.
- Adds `erp-print-table-only` / `erp-print-focus` classes during print, then cleans up on `afterprint`.
- Without a target, falls back to `window.print()`.

### Add trigger

- `data-erp-add-trigger` clicks a hidden or modal opener (used when Add cannot be a simple anchor).

---

## How modules should adopt the framework

Follow [MAXEK_ERP_RULES.md](./MAXEK_ERP_RULES.md): no UI redesign, reuse templates, fix backend before frontend.

### 1. List page layout

```jinja
{% from 'macros/erp_ui.html' import erp_standard_toolbar, erp_module_form_panel, erp_module_table_panel %}

<div class="erp-module-layout">
  {{ erp_standard_toolbar(...) }}   {# or erp_module_toolbar for minimal migration #}
  {% call erp_module_form_panel(id='add-record', title='...') %}...{% endcall %}
  {% call erp_module_table_panel(id='data-table', title='Records') %}
    <table data-erp-crud-table>...</table>
  {% endcall %}
</div>
```

### 2. CRUD route convention

| Action | URL pattern |
|--------|-------------|
| List | `GET /module` |
| Create | `POST /module` from `#add-record` or `?new=1` |
| View | `GET /module?view=<id>` |
| Edit | `GET /module?edit=<id>#form-anchor` + `POST` |
| Delete | `POST` with workflow guard or `form_action=delete_*` |

Use `module_page_context()` from `erp_framework.py` for breadcrumbs:

**Dashboard → Department hub → Module list → View/Edit**

### 3. Row-level vs toolbar-level actions

| Pattern | When to use |
|---------|-------------|
| Toolbar CRUD (`erp_standard_toolbar`) | Master lists where users select a row then Open/View/Edit/Delete |
| Row actions (`maker_row_actions`, links) | Workflow-gated records, multi-status rows, or gradual migration |
| Both | Acceptable during Phase 2 — document which actions live where |

**Open/View/Edit/Delete are often row-level** even on `erp_module_toolbar` screens. The macro provides Search, New, Export Excel, and Print only.

### 4. Navigation

- Register module under correct `NAV_GROUPS` slug in `app.py`.
- Ensure sub-bar labels match `STANDARD_SUB_LABELS` or update aliases in `ui_shell_config.py`.
- Department hubs: `/dept/<slug>` or `/<module>/dashboard`.
- Use `erp_breadcrumb` / `breadcrumb_items` instead of hard-coded breadcrumb HTML.

### 5. Reports

- Register in `report_registry.py` (`wired` / `stub` / `screen`).
- Corporate hub: `/reports/corporate`
- Standard runner: `GET /reports/run?report=<slug>&action=view|excel|pdf`
- Module pages: `erp_report_runner` macro
- Print views: `corporate_report_action_bar` + `static/js/report-actions.js`

### 6. Definition of Done

A module is complete only when all 20 items in [MODULE_DEFINITION_OF_DONE.md](./MODULE_DEFINITION_OF_DONE.md) pass in the browser.

---

## Migration path (Phase 2)

1. **Minimal:** Replace legacy `erp-table-toolbar` with `erp_module_toolbar` (Search, New, Export, Print).
2. **Standard:** Upgrade to `erp_standard_toolbar` + `erp-framework.js` row selection.
3. **Backend:** Add server `q`/`status`/`date_from`/`date_to`/`sort` GET params; add `/export` route.
4. **Workflow:** Wire `workflow_modals()` and toolbar Delete policy.
5. **Nav:** Fix sub-toolbar label ↔ route mismatches; restore hidden departments if required.
6. **Reports:** Wire stubs in corporate hub or document screen-only report flows.

See [PHASE2_CURSOR_TASKS.md](./PHASE2_CURSOR_TASKS.md) for copy-paste tasks per module.

---

## Phase 1 / Phase 2 file index

| File | Notes |
|------|-------|
| `templates/macros/erp_ui.html` | `erp_module_toolbar`, `erp_standard_toolbar`, `erp_report_runner` |
| `ui_shell_config.py` | Main toolbar, virtual entries, `STANDARD_SUB_LABELS` |
| `static/js/maxek-ui.js` | Search, CSV export, print |
| `static/js/erp-framework.js` | Full toolbar CRUD |
| `erp_framework.py` | `ModuleConfig`, filters, export helpers |
| `report_registry.py` | Report catalog |
| `templates/projects.html` | Reference list page |
| `tests/test_erp_framework.py` | Framework unit tests |
