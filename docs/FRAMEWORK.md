# MAXEK ERP — Shared UI Framework (Phase 1)

This document describes the reusable framework every module should adopt. **Project Management (`projects`)** is the reference implementation.

## Components

| Layer | Location | Purpose |
|-------|----------|---------|
| Python helpers | `erp_framework.py` | Breadcrumbs, CRUD URL builders, list filters, Excel export, report routing |
| Toolbar macro | `templates/macros/erp_ui.html` → `erp_standard_toolbar` | Standard list-page actions |
| Report runner macro | `templates/macros/erp_ui.html` → `erp_report_runner` | Run / export reports |
| Navigation macros | `erp_breadcrumb`, `erp_btn_back` | Breadcrumbs and back button |
| Client JS | `static/js/erp-framework.js` | Row selection, toolbar CRUD, filters |
| Base layout | `templates/base_maxek.html` | Loads framework JS globally |

## Standard toolbar

Include on every **list** screen:

```jinja2
{% from 'macros/erp_ui.html' import erp_standard_toolbar, erp_module_table_panel %}

<div class="erp-module-layout">
  {{ erp_standard_toolbar(
    module_endpoint='projects',
    search_name='q',
    new_url=url_for('projects') ~ '#add-project',
    export_url=url_for('projects_export'),
    export_pdf_url=url_for('projects') ~ '?print=1',
    delete_table='projects',
    module_id='project_creation',
    status_options=[{'value': 'Active', 'label': 'Active'}],
    print_target='#project-list',
    table_target='#project-list',
  ) }}
  {% call erp_module_table_panel(id='project-list', title='Records') %}
    <table data-erp-crud-table>
      <tr data-record-id="{{ row.id }}" data-record-editable="1" data-record-deletable="1">...</tr>
    </table>
  {% endcall %}
</div>
```

Toolbar buttons: **New · Open · View · Edit · Delete · Search · Status · Date · Sort · Refresh · Export Excel · Export PDF · Print**

Select a table row (click) before using Open/View/Edit/Delete.

## Navigation

Use `module_page_context()` in the route handler:

```python
from erp_framework import PROJECTS_MODULE, module_page_context, parse_crud_request

framework_ctx = module_page_context(
    PROJECTS_MODULE,
    current_label="Project List",
    crud=parse_crud_request(),
)
return render_template("projects.html", **framework_ctx, rows=rows)
```

Breadcrumb trail: **Dashboard → Department → Module → Page**

`base_maxek.html` renders `breadcrumb_items` via `erp_breadcrumb`.

## CRUD route convention

| Action | URL pattern | Handler |
|--------|-------------|---------|
| List | `/projects` | GET |
| View | `/projects?view=<id>` | GET |
| Edit | `/projects?edit=<id>#form-anchor` | GET + POST |
| Create | `/projects#form-anchor` or `?new=1` | POST |
| Delete | POST `workflow_delete_record` | workflow modal |

Define a `ModuleConfig` in `erp_framework.py` per module (see `PROJECTS_MODULE`).

## List filters & export

Server-side filters via GET params: `q`, `status`, `date_from`, `date_to`, `sort`.

```python
rows = apply_list_filters(
    rows,
    status=request.args.get("status"),
    search=request.args.get("q"),
    search_fields=("project_name", "project_code"),
)
```

Excel export route example: `/projects/export` using `export_rows_to_excel()`.

## Reports

- Registry: `report_registry.py`
- Hub UI: `/reports/corporate`
- Standard runner: `/reports/run?report=<slug>&action=view|excel|pdf`
- Routing helper: `report_run_target()` in `erp_framework.py`

Use `erp_report_runner` macro on module report pages.

## Phase 2 gaps (per-module)

- Wire remaining modules to `erp_standard_toolbar` (currently only **Projects** is fully wired)
- Add `ModuleConfig` entries for each department module
- Server-side pagination for large lists
- Dedicated PDF generators (currently PDF uses print pipeline)
- Complete stub reports in `report_registry.py`
- Workflow-aware delete from toolbar on modules without workflow modals
