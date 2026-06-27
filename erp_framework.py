"""MAXEK ERP shared framework — navigation, CRUD conventions, list filters, exports, reports."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from flask import url_for

CRUD_VIEW_PARAM = "view"
CRUD_EDIT_PARAM = "edit"
CRUD_NEW_PARAM = "new"


@dataclass(frozen=True)
class ModuleConfig:
    """Declarative module metadata for list/CRUD pages."""

    slug: str
    endpoint: str
    list_label: str
    department_label: str
    department_endpoint: str = "projects_dashboard"
    department_slug: str | None = None
    form_anchor: str = "#add-record"
    delete_table: str = ""
    module_id: str = ""
    view_param: str = CRUD_VIEW_PARAM
    edit_param: str = CRUD_EDIT_PARAM


PROJECTS_MODULE = ModuleConfig(
    slug="projects",
    endpoint="projects",
    list_label="Project List",
    department_label="Projects",
    department_endpoint="projects_dashboard",
    form_anchor="#add-project",
    delete_table="projects",
    module_id="project_creation",
)


@dataclass
class CrudRequestState:
    view_id: int | None = None
    edit_id: int | None = None
    new: bool = False

    @property
    def mode(self) -> str:
        if self.view_id:
            return "view"
        if self.edit_id:
            return "edit"
        if self.new:
            return "create"
        return "list"


def parse_crud_request(
    request=None,
    *,
    view_param: str = CRUD_VIEW_PARAM,
    edit_param: str = CRUD_EDIT_PARAM,
    new_param: str = CRUD_NEW_PARAM,
) -> CrudRequestState:
    from flask import request as flask_request

    req = request or flask_request
    view_id = req.args.get(view_param, type=int)
    edit_id = req.args.get(edit_param, type=int)
    is_new = bool(req.args.get(new_param)) or req.args.get(new_param) == "1"
    return CrudRequestState(view_id=view_id, edit_id=edit_id, new=is_new)


def build_breadcrumb_items(
    module: ModuleConfig,
    *,
    current_label: str | None = None,
) -> list[dict[str, Any]]:
    """Dashboard → Department → Module → current page."""
    dept_url = (
        url_for("department_portal", slug=module.department_slug)
        if module.department_slug
        else url_for(module.department_endpoint)
    )
    crumbs: list[dict[str, Any]] = [
        {"label": "Dashboard", "url": url_for("dashboard")},
        {"label": module.department_label, "url": dept_url},
        {"label": module.list_label, "url": url_for(module.endpoint)},
    ]
    if current_label and current_label != module.list_label:
        crumbs.append({"label": current_label})
    return crumbs


def crud_urls(module: ModuleConfig, record_id: int | None = None) -> dict[str, str]:
    base = url_for(module.endpoint)
    urls = {
        "list": base,
        "new": f"{base}{module.form_anchor}",
        "view": base,
        "edit": base,
        "open": base,
    }
    if record_id is not None:
        urls["view"] = url_for(module.endpoint, **{module.view_param: record_id})
        urls["edit"] = url_for(module.endpoint, **{module.edit_param: record_id}) + module.form_anchor
        urls["open"] = urls["view"]
    return urls


def module_page_context(
    module: ModuleConfig,
    *,
    current_label: str | None = None,
    crud: CrudRequestState | None = None,
) -> dict[str, Any]:
    crud_state = crud or parse_crud_request()
    label = current_label or module.list_label
    return {
        "page_title": label,
        "breadcrumb_items": build_breadcrumb_items(module, current_label=label),
        "module_back_url": url_for(module.department_endpoint),
        "module_list_url": url_for(module.endpoint),
        "crud": crud_state,
        "module_config": module,
    }


def apply_list_filters(
    rows: Sequence[Mapping[str, Any] | Any],
    *,
    status: str | None = None,
    status_field: str = "status",
    workflow: str | None = None,
    workflow_field: str = "approval_status",
    date_from: str | None = None,
    date_to: str | None = None,
    date_field: str = "created_at",
    search: str | None = None,
    search_fields: Iterable[str] = ("name", "title"),
    sort: str | None = None,
    sort_column: int | None = None,
) -> list[dict[str, Any]]:
    """Filter and sort list rows in Python (suitable for modest datasets)."""
    result = [dict(row) for row in rows]
    term = (search or "").strip().lower()
    if term:
        fields = tuple(search_fields)
        result = [
            row
            for row in result
            if any(term in str(row.get(field) or "").lower() for field in fields)
            or term in str(row.get("id") or "").lower()
        ]
    if status:
        result = [row for row in result if str(row.get(status_field) or "") == status]
    if workflow:
        result = [row for row in result if str(row.get(workflow_field) or "") == workflow]
    if date_from or date_to:
        filtered: list[dict[str, Any]] = []
        for row in result:
            raw = str(row.get(date_field) or "")[:10]
            if not raw:
                continue
            if date_from and raw < date_from:
                continue
            if date_to and raw > date_to:
                continue
            filtered.append(row)
        result = filtered
    if sort_column is not None:
        result.sort(key=lambda row: _sortable_cell(row, sort_column))
    elif sort == "id_asc":
        result.sort(key=lambda row: row.get("id") or 0)
    elif sort == "name_asc":
        result.sort(key=lambda row: str(row.get("project_name") or row.get("name") or "").lower())
    elif sort == "name_desc":
        result.sort(
            key=lambda row: str(row.get("project_name") or row.get("name") or "").lower(),
            reverse=True,
        )
    else:
        result.sort(key=lambda row: row.get("id") or 0, reverse=True)
    return result


def _sortable_cell(row: dict[str, Any], column_index: int) -> str:
    keys = list(row.keys())
    if column_index < len(keys):
        return str(row.get(keys[column_index]) or "").lower()
    return ""


def export_rows_to_excel(
    rows: Sequence[Mapping[str, Any] | Any],
    stem: str,
    *,
    columns: list[tuple[str, str]],
) -> tuple[io.BytesIO, str]:
    """Build an in-memory Excel workbook for download."""
    import pandas as pd

    data = []
    for row in rows:
        item = dict(row)
        data.append({label: item.get(key, "") for key, label in columns})
    frame = pd.DataFrame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name="Export")
    buffer.seek(0)
    return buffer, f"{stem}_export.xlsx"


def report_run_target(
    slug: str,
    report_def: Mapping[str, Any],
    args: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve standard /reports/run action to a Flask endpoint + values."""
    action = (args.get("action") or "view").lower()
    status = report_def.get("status", "stub")

    if status == "wired":
        record_id = args.get("record_id")
        if not record_id:
            return {"error": "wired_record_required"}
        endpoint = report_def.get("print_endpoint")
        param = report_def.get("print_param")
        if not endpoint or not param:
            return {"error": "misconfigured"}
        return {"endpoint": endpoint, "values": {param: record_id}}

    if status == "screen":
        endpoint = report_def.get("screen_endpoint")
        if not endpoint:
            return {"error": "misconfigured"}
        return {"endpoint": endpoint, "values": {}}

    if action == "excel":
        return {"endpoint": "corporate_report_export", "values": {"slug": slug}}

    return {
        "endpoint": "corporate_report_stub_print",
        "values": {"slug": slug},
    }


# Backward-compatible aliases
build_breadcrumbs = build_breadcrumb_items
filter_rows_by_context = apply_list_filters
resolve_report_run_target = report_run_target
