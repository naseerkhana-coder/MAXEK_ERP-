# MAXEK ERP — Shared Framework (Phase 1)

This document describes the reusable framework every department module should adopt. Phase 1 standardizes patterns only; per-module business logic stays in existing services and routes.

## Overview

| Layer | Location | Purpose |
|-------|----------|---------|
| Python helpers | `erp_framework.py` | CRUD params, breadcrumbs, list filters, Excel export, report routing |
| UI macros | `templates/macros/erp_ui.html` | Toolbar, breadcrumbs, report runner, table panels |
| Client JS | `static/js/erp-framework.js` | Row selection, toolbar CRUD actions, client filters/sort |
| Base layout | `templates/base_maxek.html` | Shell nav, breadcrumbs, loads framework JS |
| Reports registry | `report_registry.py` | Report catalog and wired/stub/screen status |
| Report routes | `app.py` → `/reports/run`, `/reports/standard/<slug>/*` | Run, print, export |

## Reference module

**Project Management → Projects** (`/projects`) is wired as the reference implementation:

- `erp_standard_toolbar` with full CRUD + filter + export buttons
- `breadcrumb_items` from `module_page_context(PROJECTS_MODULE)`
- Selectable rows (`data-erp-row-id`, `data-erp-row-status`, `data-erp-row-date`)
- Server export at `/projects/export`

## 1. Standard toolbar

Use the `erp_standard_toolbar` macro on every list page:

```jinja
{% from 'macros/erp_ui.html' import erp_standard_toolbar %}

{{ erp_standard_toolbar(
  module_endpoint='staff',
  search_placeholder='Search employees...',
  export_url=url_for('staff_export'),
  print_target='#employee-records',
  table_target='#employee-records',
  delete_table='staff',
  module_id='employee_master',
  form_anchor='#add-staff',
  status_options=[{'value': 'Active', 'label': 'Active'}],
  sort_options=[{'value': 1, 'label': 'Name'}]
) }}
```

**Toolbar buttons (standard):**

- CRUD: New, Open, View, Edit, Delete (row must be selected except New)
- Filters: Search, Status, Date from/to, Sort, Refresh
- Export: Export Excel, Export PDF (print-to-PDF), Print

**Table rows must include:**

```html
<tr data-erp-row-id="{{ row.id }}"
    data-erp-row-status="{{ row.status }}"
    data-erp-row-date="{{ row.created_at }}">
```

For workflow delete, either include `workflow_modals()` and per-row `.js-delete-record` buttons, or set `data-delete-table` and `data-module-id` on the toolbar.

Legacy modules can keep `erp_module_toolbar` (search + add + export + print only) until migrated in Phase 2.

## 2. Standard navigation

### Breadcrumbs

In the route handler:

```python
from erp_framework import ModuleConfig, module_page_context

MY_MODULE = ModuleConfig(
    module_id="...",
    table="...",
    endpoint="staff",
    department_slug="hr-payroll",
    department_label="HR & Payroll",
    module_label="Employee Master",
    list_label="Employee List",
    hub_endpoint="hr_dashboard",  # optional
)

ctx = module_page_context(MY_MODULE, current_label="Employee List")
return render_template("staff.html", **ctx, rows=rows)
```

`base_maxek.html` renders `breadcrumb_items` automatically when `page_title` is set.

### Hierarchy

Dashboard → Department (portal/hub) → Module list → View/Edit

Use `erp_btn_back()` in `page_actions` to return to the department hub.

## 3. Standard CRUD pattern

### Query parameters (canonical)

| Action | URL pattern |
|--------|-------------|
| List | `/module` |
| Create | `/module?new=1#add-record` |
| View | `/module?view=<id>` |
| Edit | `/module?edit=<id>#add-record` |

### Route handler pattern

```python
@login_required
def my_module():
    crud = parse_crud_request()
    edit_id = crud.edit_id
    view_id = crud.view_id
    if request.method == "POST":
        # create or update
        return redirect(url_for("my_module", view=new_id))
    rows = ...
    ctx = module_page_context(MY_MODULE)
    return render_template("my_module.html", rows=rows, **ctx)
```

### Excel export

```python
@app.route("/my-module/export")
@login_required
def my_module_export():
    rows = ...
    buffer, filename = export_rows_to_excel(rows, "my_module", columns=[...])
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="...")
```

## 4. Standard report framework

### Registry

Add entries in `report_registry.py` with `status`: `wired`, `stub`, or `screen`.

### Run route

`GET /reports/run?report=<slug>&action=view|excel|record_id=...`

Dispatches to the correct print screen, corporate stub, or Excel export.

### Report runner form

```jinja
{% from 'macros/erp_ui.html' import erp_report_runner %}

{{ erp_report_runner(
  report_slug='dpr_report',
  title='DPR Report',
  projects=projects
) }}
```

Corporate print layouts use `corporate_report_action_bar` from `templates/macros/corporate_report.html` plus `static/js/report-actions.js`.

## Phase 2 gaps (per-module)

- Migrate remaining list pages from `erp_module_toolbar` to `erp_standard_toolbar`
- Replace raw `breadcrumbs` HTML strings with `breadcrumb_items`
- Add `/export` routes for modules that only have client-side CSV export
- Wire workflow delete rules per module on toolbar Delete
- Add server-side sort/pagination instead of client-only sort where datasets are large
- Connect wired reports to record pickers on module list pages

## Files added/changed in Phase 1

- `erp_framework.py` (new)
- `static/js/erp-framework.js` (new)
- `templates/macros/erp_ui.html` — `erp_standard_toolbar`, `erp_report_runner`
- `templates/base_maxek.html` — loads framework JS
- `static/css/maxek-dashboard.css` — toolbar groups, selected row
- `app.py` — `report_run`, `projects_export`, projects framework context
- `templates/projects.html` — reference wiring
- `docs/FRAMEWORK.md` (this file)
- `tests/test_erp_framework.py` (new)
