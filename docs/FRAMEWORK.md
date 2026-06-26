# MAXEK ERP — Shared Framework (Phase 1)

> **Rules:** Follow [MAXEK_ERP_RULES.md](./MAXEK_ERP_RULES.md) for all development work.

Reusable patterns for every department module. Phase 1 standardizes the framework layer only; business logic stays in existing services.

## Components

| Layer | Location | Purpose |
|-------|----------|---------|
| Python helpers | `erp_framework.py` | CRUD params, breadcrumbs, list filters, Excel export, report routing |
| UI macros | `templates/macros/erp_ui.html` | `erp_standard_toolbar`, `erp_report_runner`, breadcrumbs, table panels |
| Client JS | `static/js/erp-framework.js` | Row selection, toolbar CRUD, client filters/sort |
| Base layout | `templates/base_maxek.html` | Shell nav, breadcrumbs, loads framework JS |
| Reports | `report_registry.py`, `/reports/run` | Report catalog and standard run routing |

## Reference module: Projects

`/projects` demonstrates the full pattern:

- `erp_standard_toolbar` with CRUD, filters, export, print
- `module_page_context(PROJECTS_MODULE)` for `breadcrumb_items` and `page_title`
- Selectable rows: `data-erp-row-id`, `data-erp-row-status`, `data-erp-row-date`
- Server Excel export: `/projects/export`

## 1. Standard toolbar

```jinja
{% from 'macros/erp_ui.html' import erp_standard_toolbar %}

{{ erp_standard_toolbar(
  module_endpoint='projects',
  search_placeholder='Search...',
  new_url=url_for('projects') ~ '#add-project',
  form_anchor='#add-project',
  export_url=url_for('projects_export'),
  print_target='#project-list',
  table_target='#project-list',
  delete_table='projects',
  module_id='project_creation',
  status_options=[{'value': 'Active', 'label': 'Active'}],
  sort_options=[{'value': 1, 'label': 'Name'}]
) }}
```

**Buttons:** New, Open, View, Edit, Delete | Search, Status, Date range, Sort, Refresh | Export Excel, Export PDF, Print

**Table rows:**

```html
<tr data-erp-row-id="{{ row.id }}"
    data-erp-row-status="{{ row.status }}"
    data-erp-row-date="{{ row.created_at }}">
```

Include `workflow_modals()` when toolbar Delete should use workflow delete rules.

Legacy pages may keep `erp_module_toolbar` until Phase 2.

## 2. Standard navigation

```python
from erp_framework import ModuleConfig, module_page_context

MY_MODULE = ModuleConfig(
    slug="staff",
    endpoint="staff",
    list_label="Employee List",
    department_label="HR & Payroll",
    department_endpoint="hr_dashboard",
    form_anchor="#add-staff",
    delete_table="staff",
    module_id="employee_master",
)

ctx = module_page_context(MY_MODULE, current_label="Employee List")
return render_template("staff.html", rows=rows, **ctx)
```

Hierarchy: **Dashboard → Department hub → Module list → View/Edit**

Use `erp_btn_back(module_back_url)` in `page_actions`.

## 3. Standard CRUD

| Action | URL |
|--------|-----|
| List | `/module` |
| Create | `/module#add-record` or `?new=1` |
| View | `/module?view=<id>` |
| Edit | `/module?edit=<id>#form-anchor` |

```python
from erp_framework import parse_crud_request, apply_list_filters, export_rows_to_excel

crud = parse_crud_request()
rows = apply_list_filters(rows, status=request.args.get("status"), search=request.args.get("q"), ...)
```

## 4. Standard reports

Registry entries in `report_registry.py` (`wired` / `stub` / `screen`).

**Run route:** `GET /reports/run?report=<slug>&action=view|excel&record_id=...`

**Runner form:**

```jinja
{{ erp_report_runner(report_slug='dpr_report', title='DPR Report', projects=projects) }}
```

Print views use `corporate_report_action_bar` + `static/js/report-actions.js`.

## Phase 2 gaps

- Migrate all list pages to `erp_standard_toolbar`
- Replace HTML `breadcrumbs` strings with `breadcrumb_items`
- Add `/export` routes where only client CSV exists
- Enforce workflow rules on toolbar Delete per module
- Server-side pagination for large lists
- Record pickers for wired reports on list pages

## Phase 1 files

- `erp_framework.py`
- `static/js/erp-framework.js`
- `templates/macros/erp_ui.html` — `erp_standard_toolbar`, `erp_report_runner`
- `templates/base_maxek.html`
- `static/css/maxek-dashboard.css`
- `app.py` — `report_run`, `projects_export`, projects context
- `templates/projects.html`
- `docs/FRAMEWORK.md`
- `tests/test_erp_framework.py`
