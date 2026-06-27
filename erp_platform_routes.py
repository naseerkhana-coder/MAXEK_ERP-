"""ERP platform API routes — search, context, badges, attachments, audit."""

from __future__ import annotations

import os

from flask import Blueprint, jsonify, request, send_file, session, url_for

from attachment_service import (
    delete_attachment,
    get_attachment,
    list_attachments,
    save_attachment,
)
from audit_trail_service import list_audit_trail
from badge_counts_service import get_live_badge_counts
from dashboard_prefs_service import infer_role_profile, load_dashboard_preferences, save_dashboard_preferences
from global_search_service import global_search, search_category_keys
from user_context_service import (
    list_context_branches,
    list_context_companies,
    list_context_projects,
    load_user_context,
    save_user_context,
)

erp_platform_bp = Blueprint("erp_platform", __name__, url_prefix="/api/erp")


def _login_required_json():
    if not session.get("user_id"):
        return jsonify({"error": "Not authenticated"}), 401
    return None


@erp_platform_bp.route("/search")
def api_erp_search():
    denied = _login_required_json()
    if denied:
        return denied
    from app import get_db, is_admin_user

    q = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "all").strip() or "all"
    limit = request.args.get("limit", type=int) or 12
    if len(q) < 2:
        return jsonify({"results": [], "categories": search_category_keys()})
    cat = None if category == "all" else category
    hits = global_search(get_db(), q, category=cat, limit=limit)
    for hit in hits:
        endpoint = hit["endpoint"]
        view_param = hit.get("view_param") or "view"
        try:
            hit["url"] = url_for(endpoint, **{view_param: hit["id"]})
        except Exception:
            hit["url"] = f"/{endpoint}?{view_param}={hit['id']}"
    return jsonify({"results": hits, "query": q, "category": category})


@erp_platform_bp.route("/badges")
def api_erp_badges():
    denied = _login_required_json()
    if denied:
        return denied
    from app import get_db, is_admin_user

    counts = get_live_badge_counts(get_db(), session.get("user_id"), is_admin_user())
    return jsonify({"badges": counts, "ts": __import__("time").time()})


@erp_platform_bp.route("/context", methods=["GET", "POST"])
def api_erp_context():
    denied = _login_required_json()
    if denied:
        return denied
    from app import get_db

    db = get_db()
    user_id = int(session["user_id"])
    if request.method == "GET":
        ctx = load_user_context(db, user_id) or {}
        company_id = ctx.get("company_id") or session.get("company_id")
        return jsonify(
            {
                "context": {
                    "company_id": company_id,
                    "company_code": ctx.get("company_code") or session.get("company_code"),
                    "branch_id": ctx.get("branch_id") or session.get("branch_id"),
                    "branch_name": ctx.get("branch_name") or session.get("branch"),
                    "project_id": ctx.get("project_id") or session.get("selected_project_id"),
                },
                "companies": list_context_companies(db),
                "branches": list_context_branches(db, company_id),
                "projects": list_context_projects(db, ctx.get("branch_id")),
            }
        )
    data = request.get_json(silent=True) or {}
    if not data and request.form:
        data = request.form.to_dict()
    company_id = data.get("company_id")
    branch_id = data.get("branch_id")
    project_id = data.get("project_id")
    try:
        company_id = int(company_id) if company_id not in (None, "", "null") else None
    except (TypeError, ValueError):
        company_id = None
    try:
        branch_id = int(branch_id) if branch_id not in (None, "", "null") else None
    except (TypeError, ValueError):
        branch_id = None
    try:
        project_id = int(project_id) if project_id not in (None, "", "null") else None
    except (TypeError, ValueError):
        project_id = None
    branch_name = (data.get("branch_name") or "").strip()
    company_code = (data.get("company_code") or session.get("company_code") or "").strip()
    if branch_id and not branch_name:
        branches = list_context_branches(db, company_id or session.get("company_id"))
        match = next((b for b in branches if b["id"] == branch_id), None)
        if match:
            branch_name = match["name"]
    payload = save_user_context(
        db,
        user_id,
        customer_id=session.get("customer_id"),
        company_id=company_id or session.get("company_id"),
        company_code=company_code or None,
        branch_id=branch_id,
        branch_name=branch_name or None,
        project_id=project_id,
        updated_by=session.get("username") or "",
    )
    if company_id:
        session["company_id"] = company_id
    if company_code:
        session["company_code"] = company_code
    if branch_id:
        session["branch_id"] = branch_id
    if branch_name:
        session["branch"] = branch_name
    if project_id is not None:
        session["selected_project_id"] = project_id if project_id else None
    return jsonify({"ok": True, "context": payload})


@erp_platform_bp.route("/dashboard-preferences", methods=["GET", "POST"])
def api_dashboard_preferences():
    denied = _login_required_json()
    if denied:
        return denied
    from app import get_db

    db = get_db()
    user_id = int(session["user_id"])
    if request.method == "GET":
        prefs = load_dashboard_preferences(db, user_id)
        if prefs.get("role_profile") == "default":
            prefs["role_profile"] = infer_role_profile(
                session.get("department"), session.get("role")
            )
        return jsonify({"preferences": prefs})
    data = request.get_json(silent=True) or {}
    prefs = save_dashboard_preferences(
        db,
        user_id,
        role_profile=data.get("role_profile"),
        favorite_modules=data.get("favorite_modules"),
        dashboard_cards=data.get("dashboard_cards"),
        quick_actions=data.get("quick_actions"),
        reports=data.get("reports"),
        ui_theme=data.get("ui_theme"),
    )
    return jsonify({"ok": True, "preferences": prefs})


@erp_platform_bp.route("/attachments/<record_table>/<int:record_id>")
def api_list_attachments(record_table: str, record_id: int):
    denied = _login_required_json()
    if denied:
        return denied
    from app import get_db

    items = list_attachments(get_db(), record_table, record_id)
    return jsonify({"attachments": items})


@erp_platform_bp.route("/attachments", methods=["POST"])
def api_upload_attachment():
    denied = _login_required_json()
    if denied:
        return denied
    from app import UPLOADS_DIR, get_db

    module_id = request.form.get("module_id", "")
    record_table = request.form.get("record_table", "")
    record_id = request.form.get("record_id", type=int)
    replace_id = request.form.get("replace_id", type=int)
    file = request.files.get("file")
    if not module_id or not record_table or not record_id or not file:
        return jsonify({"error": "module_id, record_table, record_id, and file are required"}), 400
    try:
        att = save_attachment(
            get_db(),
            UPLOADS_DIR,
            file,
            module_id=module_id,
            record_table=record_table,
            record_id=record_id,
            uploaded_by=session.get("username") or "",
            replace_id=replace_id,
        )
        return jsonify({"ok": True, "attachment": att})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@erp_platform_bp.route("/attachments/<int:attachment_id>/download")
def api_download_attachment(attachment_id: int):
    denied = _login_required_json()
    if denied:
        return denied
    from app import get_db

    att = get_attachment(get_db(), attachment_id)
    if not att or not att.get("is_active"):
        return jsonify({"error": "Not found"}), 404
    path = att.get("stored_path")
    if not path or not os.path.isfile(path):
        return jsonify({"error": "File missing"}), 404
    return send_file(path, as_attachment=True, download_name=att.get("original_filename"))


@erp_platform_bp.route("/attachments/<int:attachment_id>", methods=["DELETE"])
def api_delete_attachment(attachment_id: int):
    denied = _login_required_json()
    if denied:
        return denied
    from app import get_db

    ok = delete_attachment(
        get_db(),
        attachment_id,
        deleted_by=session.get("username") or "",
        hard=False,
    )
    return jsonify({"ok": ok})


@erp_platform_bp.route("/audit/<record_table>/<int:record_id>")
def api_audit_trail(record_table: str, record_id: int):
    denied = _login_required_json()
    if denied:
        return denied
    from app import get_db

    trail = list_audit_trail(get_db(), record_table, record_id)
    return jsonify({"audit": trail})
