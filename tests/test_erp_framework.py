"""Tests for MAXEK ERP shared framework helpers."""

import pytest

from erp_framework import (
    PROJECTS_MODULE,
    apply_list_filters,
    build_breadcrumb_items,
    crud_urls,
    module_page_context,
    parse_crud_request,
    report_run_target,
)


@pytest.fixture
def app_ctx(app):
    with app.test_request_context("/projects"):
        yield


def test_parse_crud_request_view_and_edit(app):
    with app.test_request_context("/projects?view=5&edit=3"):
        state = parse_crud_request()
        assert state.view_id == 5
        assert state.edit_id == 3
        assert state.mode == "view"


def test_build_breadcrumb_items(app_ctx):
    crumbs = build_breadcrumb_items(PROJECTS_MODULE, current_label="Project List")
    assert crumbs[0]["label"] == "Dashboard"
    assert crumbs[1]["label"] == "Projects"
    assert crumbs[-1]["label"] == "Project List"
    assert crumbs[-1].get("url") is None


def test_crud_urls(app_ctx):
    urls = crud_urls(PROJECTS_MODULE, record_id=42)
    assert urls["view"].endswith("view=42")
    assert urls["edit"].endswith("edit=42")


def test_apply_list_filters_status_and_search():
    rows = [
        {"project_name": "Alpha Bridge", "status": "Active"},
        {"project_name": "Beta Road", "status": "Completed"},
    ]
    filtered = apply_list_filters(rows, status="Active", search="alpha", search_fields=("project_name",))
    assert len(filtered) == 1
    assert filtered[0]["project_name"] == "Alpha Bridge"


def test_module_page_context_list_mode(app_ctx):
    ctx = module_page_context(PROJECTS_MODULE)
    assert ctx["page_title"] == PROJECTS_MODULE.list_label
    assert "breadcrumb_items" in ctx
    assert ctx["crud"].mode == "list"


def test_report_run_target_stub():
    target = report_run_target(
        "dpr_report",
        {"status": "stub", "label": "DPR Report"},
        {"action": "excel"},
    )
    assert target["endpoint"] == "corporate_report_export"
    assert target["values"]["slug"] == "dpr_report"


def test_report_run_target_wired_requires_record():
    target = report_run_target(
        "client_ra_bill",
        {
            "status": "wired",
            "print_endpoint": "client_billing_print",
            "print_param": "bill_id",
        },
        {},
    )
    assert target["error"] == "wired_record_required"
