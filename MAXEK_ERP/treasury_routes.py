"""Flask routes for Bank & Treasury module."""

import os
from datetime import datetime, timedelta

from flask import flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

from treasury_service import (
    BANK_ACCOUNT_TYPES,
    BANK_DOCUMENT_ENTITY_TYPES,
    BANK_DOCUMENT_TYPES,
    BANK_PAYMENT_TYPES,
    BG_TYPES,
    CHEQUE_STATUSES,
    DOCUMENT_TYPE_DEFAULT_ENTITY,
    FD_STATUSES,
    PDC_STATUSES,
    PDC_TYPES,
    RECON_STATUSES,
    SECURITY_DEPOSIT_STATUSES,
    SECURITY_DEPOSIT_TYPES,
    TREASURY_ALLOWED_EXTENSIONS,
    account_360_data,
    account_dashboard_stats,
    allowed_cheque_status_transitions,
    allowed_pdc_status_transitions,
    bg_expiry_alerts,
    close_fd,
    create_cheque,
    create_fd,
    create_pdc,
    delete_bank_document,
    ensure_treasury_schema,
    get_bank_book_rows,
    get_bank_document,
    get_bank_document_entity_options,
    get_bg_register_rows,
    get_cheque,
    get_fd,
    get_od_register_rows,
    get_pdc,
    get_treasury_cash_flow_summary,
    get_cash_flow_forecast,
    CASH_FLOW_FORECAST_PERIODS,
    list_bank_accounts,
    list_bank_documents,
    list_bank_guarantees,
    list_bank_payments,
    list_bank_receipts,
    list_bank_reconciliation,
    list_cheques,
    list_fds,
    list_letters_of_credit,
    list_overdrafts,
    list_pdc,
    list_treasury_security_deposits,
    renew_fd,
    save_bank_account,
    save_bank_guarantee,
    save_bank_payment,
    save_bank_receipt,
    save_letter_of_credit,
    save_treasury_security_deposit,
    treasury_hub_stats,
    upcoming_maturity_alerts,
    upcoming_pdc_due_alerts,
    update_cheque,
    update_cheque_status,
    update_fd,
    update_pdc,
    update_pdc_status,
    upload_bank_document,
    validate_treasury_document_upload,
)
from budget_service import (
    BUDGET_CATEGORIES,
    budget_alerts,
    ensure_budget_schema,
    get_project_budget,
    get_project_budget_lines,
    get_project_budget_summary,
    list_project_budget_overview,
    save_project_budgets,
)
from profitability_service import (
    ensure_profitability_schema,
    get_project_profitability,
    list_all_projects_profitability,
)


def register_treasury_routes(app, *, login_required, get_db, query_db, is_admin_user,
                               create_approval_request, get_edit_role_for_user,
                               _workflow_view_context, _module_edit_context, _complete_module_save,
                               treasury_docs_dir=None, save_file_fn=None):
    """Register treasury blueprint-style routes on the Flask app."""
    docs_dir = treasury_docs_dir or os.path.join("static", "uploads", "treasury")

    def _save_upload(file_storage):
        if save_file_fn:
            return save_file_fn(file_storage, docs_dir)
        return None

    def _prepare_treasury_db(db):
        ensure_treasury_schema(db)
        ensure_budget_schema(db)
        ensure_profitability_schema(db)
        db.commit()

    def _treasury_projects():
        return query_db("SELECT id, project_name FROM projects ORDER BY project_name")

    def _treasury_vendors():
        return query_db(
            "SELECT id, code, name FROM vendors WHERE is_active=1 ORDER BY name"
        )

    def _treasury_accounts(active_only=True):
        return list_bank_accounts(get_db(), active_only=active_only)

    def _workflow_page(module_id, table, endpoint, record_sql, save_fn, template, extra=None):
        db = get_db()
        _prepare_treasury_db(db)
        if request.method == "POST":
            ctx = _module_edit_context(module_id, table, endpoint)
            if ctx[0] == "redirect":
                return redirect(ctx[1])
            record_id, edit_role = ctx
            try:
                if record_id:
                    save_fn(db, request.form, session.get("username", ""), record_id)
                    _complete_module_save(db, module_id, table, record_id, edit_role)
                else:
                    new_id = save_fn(db, request.form, session.get("username", ""))
                    create_approval_request(
                        db, module_id, new_id, table,
                        session.get("username", ""), session.get("user_id"),
                    )
                    db.commit()
                    flash("Saved. Status: Pending Checker.")
                return redirect(url_for(endpoint))
            except ValueError as exc:
                flash(str(exc))
                return redirect(request.referrer or url_for(endpoint, new=1))
        state = _module_page_state(module_id, table, endpoint, record_sql)
        if state.get("redirect"):
            return redirect(state["redirect"])
        ctx = {
            "rows": extra["list_fn"](db) if extra and extra.get("list_fn") else [],
            "view_record": state.get("view_record"),
            "edit_record": state.get("edit_record"),
            "history": state.get("history"),
            "can_reopen": state.get("can_reopen", False),
            "approval_id": state.get("approval_id"),
            "module_id": module_id,
            "show_form": bool(request.args.get("new")) or state.get("edit_record"),
            "default_date": datetime.now().strftime("%Y-%m-%d"),
            "accounts": _treasury_accounts(),
            "projects": _treasury_projects(),
        }
        if extra:
            ctx.update(extra.get("template_ctx", {}))
        if state.get("view_record") and extra and extra.get("view_sql"):
            row = db.execute(extra["view_sql"], (state["view_record"]["id"],)).fetchone()
            if row:
                ctx["view_record"] = dict(row)
        if state.get("edit_record") and extra and extra.get("view_sql"):
            row = db.execute(extra["view_sql"], (state["edit_record"]["id"],)).fetchone()
            if row:
                ctx["edit_record"] = dict(row)
        return render_template(template, **ctx)

    def _module_page_state(module_id, table, endpoint, record_sql):
        view_id = request.args.get("view")
        edit_id = request.args.get("edit")
        view_record = edit_record = None
        wf_ctx = {}
        if view_id:
            view_record = query_db(record_sql, (view_id,), one=True)
            if view_record:
                wf_ctx = _workflow_view_context(
                    module_id, view_record["id"], table, view_record["approval_status"]
                )
        elif edit_id:
            edit_record = query_db(record_sql, (edit_id,), one=True)
            if edit_record:
                edit_role = get_edit_role_for_user(
                    get_db(), session.get("user_id"), module_id,
                    edit_record["approval_status"], is_admin_user(),
                )
                if not edit_role:
                    flash("This record is locked and cannot be edited.")
                    return {"redirect": url_for(endpoint, view=edit_id)}
                wf_ctx = {"edit_role": edit_role}
        return {
            "view_record": dict(view_record) if view_record else None,
            "edit_record": dict(edit_record) if edit_record else None,
            **wf_ctx,
        }

    @app.route("/treasury")
    @app.route("/bank")
    @login_required
    def treasury_hub():
        db = get_db()
        _prepare_treasury_db(db)
        stats = treasury_hub_stats(db)
        pdc_alerts = upcoming_pdc_due_alerts(db)
        fd_alerts = upcoming_maturity_alerts(db)
        modules = [
            {"endpoint": "treasury_bank_accounts", "label": "Bank Master", "icon": "fa-building-columns", "description": "Bank account master — branches, IFSC, balances, OD limits."},
            {"endpoint": "treasury_daily_dashboard", "label": "Daily Dashboard", "icon": "fa-calendar-day", "description": "Today's liquidity, MTD flows, BG alerts."},
            {"endpoint": "treasury_control_center", "label": "Control Center", "icon": "fa-shield-halved", "description": "Management view — exposure, approval matrix, audit."},
            {"endpoint": "treasury_payments", "label": "Payments", "icon": "fa-money-bill-transfer", "description": "Bank payments with workflow and approval tiers."},
            {"endpoint": "treasury_receipts", "label": "Receipts", "icon": "fa-hand-holding-dollar", "description": "Client and other bank receipts."},
            {"endpoint": "treasury_reconciliation", "label": "Reconciliation", "icon": "fa-scale-balanced", "description": "Matched / unmatched bank statement items."},
            {"endpoint": "treasury_overdrafts", "label": "OD Management", "icon": "fa-chart-line", "description": "Overdraft limits and utilization."},
            {"endpoint": "treasury_bank_guarantees", "label": "Bank Guarantees", "icon": "fa-file-contract", "description": "BG register with expiry alerts."},
            {"endpoint": "treasury_letters_of_credit", "label": "Letters of Credit", "icon": "fa-passport", "description": "LC tracking and utilization."},
            {"endpoint": "treasury_security_deposits", "label": "Security Deposits", "icon": "fa-vault", "description": "EMD / SD deposits by project."},
            {"endpoint": "treasury_reports", "label": "Reports", "icon": "fa-chart-pie", "description": "Bank book, BG register, OD register, cash flow."},
            {"endpoint": "treasury_cheques", "label": "Cheque Management", "icon": "fa-money-check", "description": "Cheque register — issue, deposit, clear, bounce."},
            {"endpoint": "treasury_pdc_register", "label": "PDC Register", "icon": "fa-calendar-check", "description": "Post-dated cheques — received & issued, due alerts."},
            {"endpoint": "treasury_fixed_deposits", "label": "FD Management", "icon": "fa-piggy-bank", "description": "Fixed deposits — interest accrual, maturity alerts, renew/close."},
            {"endpoint": "treasury_cash_flow_forecast", "label": "Cash Flow Forecast", "icon": "fa-chart-area", "description": "7/30/90-day and project completion cash projections."},
            {"endpoint": "treasury_document_vault", "label": "Document Vault", "icon": "fa-folder-open", "description": "Bank forms, BG copies, FD receipts, treasury & loan documents."},
            {"endpoint": "treasury_budget_control", "label": "Budget Control", "icon": "fa-chart-pie", "description": "Project spending vs approved budget — committed, actual, alerts."},
            {"endpoint": "treasury_project_profitability", "label": "Project Profitability", "icon": "fa-chart-line", "description": "Contract value, billing, receipts vs costs — gross and net profit by project."},
        ]
        return render_template("treasury/hub.html", stats=stats, modules=modules, pdc_alerts=pdc_alerts, fd_alerts=fd_alerts)

    @app.route("/treasury/accounts", methods=["GET", "POST"])
    @login_required
    def treasury_bank_accounts():
        db = get_db()
        _prepare_treasury_db(db)
        if request.method == "POST":
            record_id = request.form.get("record_id", "").strip()
            try:
                rid = int(record_id) if record_id else None
                save_bank_account(db, request.form, session.get("username", ""), rid)
                db.commit()
                flash("Bank account saved.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("treasury_bank_accounts"))
        view_id = request.args.get("view")
        edit_id = request.args.get("edit")
        view_record = edit_record = None
        if view_id:
            from treasury_service import get_bank_account
            view_record = get_bank_account(db, int(view_id))
        elif edit_id:
            from treasury_service import get_bank_account
            edit_record = get_bank_account(db, int(edit_id))
        return render_template(
            "treasury/bank_accounts.html",
            rows=list_bank_accounts(db),
            view_record=view_record,
            edit_record=edit_record,
            show_form=bool(request.args.get("new")) or edit_record,
            account_types=BANK_ACCOUNT_TYPES,
        )

    @app.route("/treasury/accounts/<int:account_id>/dashboard")
    @login_required
    def treasury_account_dashboard(account_id):
        db = get_db()
        _prepare_treasury_db(db)
        stats = account_dashboard_stats(db, account_id)
        return render_template("treasury/account_dashboard.html", stats=stats)

    @app.route("/treasury/accounts/<int:account_id>/360")
    @login_required
    def treasury_account_360(account_id):
        db = get_db()
        _prepare_treasury_db(db)
        data = account_360_data(db, account_id)
        return render_template("treasury/account_360.html", data=data)

    pay_view_sql = (
        "SELECT p.*, ba.bank_name, ba.account_number FROM bank_payments p "
        "LEFT JOIN bank_accounts ba ON p.bank_account_id = ba.id WHERE p.id=?"
    )

    @app.route("/treasury/payments", methods=["GET", "POST"])
    @login_required
    def treasury_payments():
        db = get_db()
        _prepare_treasury_db(db)
        module_id, table, endpoint = "bank_payment", "bank_payments", "treasury_payments"
        filter_account_id = request.args.get("account_id", type=int)
        if request.method == "POST":
            ctx = _module_edit_context(module_id, table, endpoint)
            if ctx[0] == "redirect":
                return redirect(ctx[1])
            record_id, edit_role = ctx
            try:
                if record_id:
                    save_bank_payment(db, request.form, session.get("username", ""), record_id)
                    _complete_module_save(db, module_id, table, record_id, edit_role)
                else:
                    new_id = save_bank_payment(db, request.form, session.get("username", ""))
                    create_approval_request(
                        db, module_id, new_id, table,
                        session.get("username", ""), session.get("user_id"),
                    )
                    db.commit()
                    flash("Payment saved. Status: Pending Checker.")
                return redirect(url_for(endpoint, account_id=filter_account_id) if filter_account_id else url_for(endpoint))
            except ValueError as exc:
                flash(str(exc))
                return redirect(request.referrer or url_for(endpoint, new=1))
        state = _module_page_state(module_id, table, endpoint, "SELECT * FROM bank_payments WHERE id=?")
        if state.get("redirect"):
            return redirect(state["redirect"])
        view_record = state.get("view_record")
        edit_record = state.get("edit_record")
        if view_record:
            row = db.execute(pay_view_sql, (view_record["id"],)).fetchone()
            if row:
                view_record = dict(row)
        if edit_record:
            row = db.execute(pay_view_sql, (edit_record["id"],)).fetchone()
            if row:
                edit_record = dict(row)
        rows = list_bank_payments(db, filter_account_id)
        return render_template(
            "treasury/payments.html",
            rows=rows,
            view_record=view_record,
            edit_record=edit_record,
            history=state.get("history"),
            can_reopen=state.get("can_reopen", False),
            approval_id=state.get("approval_id"),
            module_id=module_id,
            show_form=bool(request.args.get("new")) or edit_record,
            default_date=datetime.now().strftime("%Y-%m-%d"),
            accounts=_treasury_accounts(),
            payment_types=BANK_PAYMENT_TYPES,
            filter_account_id=filter_account_id,
        )

    rec_view_sql = (
        "SELECT r.*, ba.bank_name, ba.account_number FROM bank_receipts r "
        "LEFT JOIN bank_accounts ba ON r.bank_account_id = ba.id WHERE r.id=?"
    )

    @app.route("/treasury/receipts", methods=["GET", "POST"])
    @login_required
    def treasury_receipts():
        db = get_db()
        _prepare_treasury_db(db)
        module_id, table, endpoint = "bank_receipt", "bank_receipts", "treasury_receipts"
        filter_account_id = request.args.get("account_id", type=int)
        if request.method == "POST":
            ctx = _module_edit_context(module_id, table, endpoint)
            if ctx[0] == "redirect":
                return redirect(ctx[1])
            record_id, edit_role = ctx
            try:
                if record_id:
                    save_bank_receipt(db, request.form, session.get("username", ""), record_id)
                    _complete_module_save(db, module_id, table, record_id, edit_role)
                else:
                    new_id = save_bank_receipt(db, request.form, session.get("username", ""))
                    create_approval_request(
                        db, module_id, new_id, table,
                        session.get("username", ""), session.get("user_id"),
                    )
                    db.commit()
                    flash("Receipt saved. Status: Pending Checker.")
                return redirect(url_for(endpoint, account_id=filter_account_id) if filter_account_id else url_for(endpoint))
            except ValueError as exc:
                flash(str(exc))
                return redirect(request.referrer or url_for(endpoint, new=1))
        state = _module_page_state(module_id, table, endpoint, "SELECT * FROM bank_receipts WHERE id=?")
        if state.get("redirect"):
            return redirect(state["redirect"])
        view_record = state.get("view_record")
        edit_record = state.get("edit_record")
        if view_record:
            row = db.execute(rec_view_sql, (view_record["id"],)).fetchone()
            if row:
                view_record = dict(row)
        if edit_record:
            row = db.execute(rec_view_sql, (edit_record["id"],)).fetchone()
            if row:
                edit_record = dict(row)
        return render_template(
            "treasury/receipts.html",
            rows=list_bank_receipts(db, filter_account_id),
            view_record=view_record,
            edit_record=edit_record,
            history=state.get("history"),
            can_reopen=state.get("can_reopen", False),
            approval_id=state.get("approval_id"),
            module_id=module_id,
            show_form=bool(request.args.get("new")) or edit_record,
            default_date=datetime.now().strftime("%Y-%m-%d"),
            accounts=_treasury_accounts(),
            filter_account_id=filter_account_id,
        )

    @app.route("/treasury/reconciliation")
    @login_required
    def treasury_reconciliation():
        db = get_db()
        _prepare_treasury_db(db)
        filter_account_id = request.args.get("account_id", type=int)
        filter_status = request.args.get("status", "").strip() or None
        rows = list_bank_reconciliation(db, filter_account_id, filter_status)
        counts = {"matched": 0, "unmatched": 0, "pending": 0}
        for row in rows:
            st = (row.get("status") or "pending").lower()
            if st in counts:
                counts[st] += 1
        return render_template(
            "treasury/reconciliation.html",
            rows=rows,
            accounts=_treasury_accounts(),
            recon_statuses=RECON_STATUSES,
            filter_account_id=filter_account_id,
            filter_status=filter_status,
            counts=counts,
        )

    @app.route("/treasury/overdrafts")
    @login_required
    def treasury_overdrafts():
        db = get_db()
        _prepare_treasury_db(db)
        return render_template("treasury/overdrafts.html", rows=list_overdrafts(db))

    bg_view_sql = (
        "SELECT g.*, ba.bank_name, ba.account_number, p.project_name FROM bank_guarantees g "
        "LEFT JOIN bank_accounts ba ON g.bank_account_id = ba.id "
        "LEFT JOIN projects p ON g.project_id = p.id WHERE g.id=?"
    )

    @app.route("/treasury/bank-guarantees", methods=["GET", "POST"])
    @login_required
    def treasury_bank_guarantees():
        db = get_db()
        _prepare_treasury_db(db)
        module_id, table, endpoint = "bank_guarantee", "bank_guarantees", "treasury_bank_guarantees"
        if request.method == "POST":
            ctx = _module_edit_context(module_id, table, endpoint)
            if ctx[0] == "redirect":
                return redirect(ctx[1])
            record_id, edit_role = ctx
            try:
                if record_id:
                    save_bank_guarantee(db, request.form, session.get("username", ""), record_id)
                    _complete_module_save(db, module_id, table, record_id, edit_role)
                else:
                    new_id = save_bank_guarantee(db, request.form, session.get("username", ""))
                    create_approval_request(
                        db, module_id, new_id, table,
                        session.get("username", ""), session.get("user_id"),
                    )
                    db.commit()
                    flash("BG saved. Status: Pending Checker.")
                return redirect(url_for(endpoint))
            except ValueError as exc:
                flash(str(exc))
                return redirect(request.referrer or url_for(endpoint, new=1))
        state = _module_page_state(module_id, table, endpoint, "SELECT * FROM bank_guarantees WHERE id=?")
        if state.get("redirect"):
            return redirect(state["redirect"])
        view_record = state.get("view_record")
        edit_record = state.get("edit_record")
        if view_record:
            row = db.execute(bg_view_sql, (view_record["id"],)).fetchone()
            if row:
                view_record = dict(row)
        if edit_record:
            row = db.execute(bg_view_sql, (edit_record["id"],)).fetchone()
            if row:
                edit_record = dict(row)
        return render_template(
            "treasury/bank_guarantees.html",
            rows=list_bank_guarantees(db),
            alerts=bg_expiry_alerts(db),
            view_record=view_record,
            edit_record=edit_record,
            history=state.get("history"),
            can_reopen=state.get("can_reopen", False),
            approval_id=state.get("approval_id"),
            module_id=module_id,
            show_form=bool(request.args.get("new")) or edit_record,
            accounts=_treasury_accounts(),
            projects=_treasury_projects(),
            bg_types=BG_TYPES,
        )

    @app.route("/treasury/letters-of-credit", methods=["GET", "POST"])
    @login_required
    def treasury_letters_of_credit():
        db = get_db()
        _prepare_treasury_db(db)
        if request.method == "POST":
            record_id = request.form.get("record_id", "").strip()
            try:
                rid = int(record_id) if record_id else None
                save_letter_of_credit(db, request.form, session.get("username", ""), rid)
                db.commit()
                flash("LC saved.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("treasury_letters_of_credit"))
        edit_id = request.args.get("edit", type=int)
        edit_record = None
        if edit_id:
            row = db.execute("SELECT * FROM letters_of_credit WHERE id=?", (edit_id,)).fetchone()
            edit_record = dict(row) if row else None
        return render_template(
            "treasury/letters_of_credit.html",
            rows=list_letters_of_credit(db),
            edit_record=edit_record,
            show_form=bool(request.args.get("new")) or edit_record,
            accounts=_treasury_accounts(),
        )

    @app.route("/treasury/security-deposits", methods=["GET", "POST"])
    @login_required
    def treasury_security_deposits():
        db = get_db()
        _prepare_treasury_db(db)
        if request.method == "POST":
            record_id = request.form.get("record_id", "").strip()
            try:
                rid = int(record_id) if record_id else None
                save_treasury_security_deposit(db, request.form, session.get("username", ""), rid)
                db.commit()
                flash("Security deposit saved.")
            except ValueError as exc:
                flash(str(exc))
            return redirect(url_for("treasury_security_deposits"))
        edit_id = request.args.get("edit", type=int)
        edit_record = None
        if edit_id:
            rows = list_treasury_security_deposits(db)
            edit_record = next((r for r in rows if r["id"] == edit_id), None)
        return render_template(
            "treasury/security_deposits.html",
            rows=list_treasury_security_deposits(db),
            edit_record=edit_record,
            show_form=bool(request.args.get("new")) or edit_record,
            accounts=_treasury_accounts(),
            projects=_treasury_projects(),
            deposit_types=SECURITY_DEPOSIT_TYPES,
            deposit_statuses=SECURITY_DEPOSIT_STATUSES,
        )

    @app.route("/treasury/daily-dashboard")
    @login_required
    def treasury_daily_dashboard():
        db = get_db()
        _prepare_treasury_db(db)
        return render_template(
            "treasury/daily_dashboard.html",
            stats=treasury_hub_stats(db),
            cash_flow=get_treasury_cash_flow_summary(db),
            alerts=bg_expiry_alerts(db),
            accounts=list_bank_accounts(db, active_only=True),
        )

    @app.route("/treasury/control-center")
    @login_required
    def treasury_control_center():
        db = get_db()
        _prepare_treasury_db(db)
        matrix = [dict(r) for r in db.execute(
            "SELECT * FROM payment_approval_matrix WHERE is_active=1 ORDER BY sort_order, min_amount"
        ).fetchall()]
        audit_logs = [dict(r) for r in db.execute(
            "SELECT * FROM treasury_audit_log ORDER BY created_at DESC LIMIT 30"
        ).fetchall()]
        return render_template(
            "treasury/control_center.html",
            stats=treasury_hub_stats(db),
            matrix=matrix,
            audit_logs=audit_logs,
        )

    @app.route("/treasury/reports")
    @login_required
    def treasury_reports():
        db = get_db()
        _prepare_treasury_db(db)
        report = request.args.get("report", "bank_book")
        filter_account_id = request.args.get("account_id", type=int)
        report_types = {
            "bank_book": "Bank Book",
            "bg_register": "BG Register",
            "od_register": "OD Register",
            "cash_flow": "Cash Flow Summary",
        }
        if report not in report_types:
            report = "bank_book"
        return render_template(
            "treasury/reports.html",
            report=report,
            report_types=report_types,
            bank_book=get_bank_book_rows(db, filter_account_id),
            bg_rows=get_bg_register_rows(db),
            od_rows=get_od_register_rows(db),
            cash_flow=get_treasury_cash_flow_summary(db),
            accounts=_treasury_accounts(),
            filter_account_id=filter_account_id,
        )

    @app.route("/treasury/cheques")
    @login_required
    def treasury_cheques():
        db = get_db()
        _prepare_treasury_db(db)
        filter_account_id = request.args.get("account_id", type=int)
        filter_status = request.args.get("status", "").strip() or None
        date_from = request.args.get("date_from", "").strip() or None
        date_to = request.args.get("date_to", "").strip() or None
        rows = list_cheques(db, filter_account_id, filter_status, date_from, date_to)
        status_counts = {s: 0 for s in CHEQUE_STATUSES}
        for row in rows:
            st = row.get("status") or "Issued"
            if st in status_counts:
                status_counts[st] += 1
        return render_template(
            "treasury/cheques.html",
            rows=rows,
            accounts=_treasury_accounts(),
            cheque_statuses=CHEQUE_STATUSES,
            filter_account_id=filter_account_id,
            filter_status=filter_status,
            date_from=date_from,
            date_to=date_to,
            status_counts=status_counts,
        )

    @app.route("/treasury/cheques/new", methods=["GET", "POST"])
    @login_required
    def treasury_cheque_new():
        db = get_db()
        _prepare_treasury_db(db)
        if request.method == "POST":
            try:
                new_id = create_cheque(db, request.form, session.get("username", ""))
                db.commit()
                flash("Cheque created.")
                return redirect(url_for("treasury_cheque_detail", cheque_id=new_id))
            except ValueError as exc:
                flash(str(exc))
        return render_template(
            "treasury/cheque_form.html",
            edit_record=None,
            accounts=_treasury_accounts(),
            default_date=datetime.now().strftime("%Y-%m-%d"),
        )

    @app.route("/treasury/cheques/<int:cheque_id>", methods=["GET", "POST"])
    @login_required
    def treasury_cheque_detail(cheque_id):
        db = get_db()
        _prepare_treasury_db(db)
        cheque = get_cheque(db, cheque_id)
        if not cheque:
            flash("Cheque not found.")
            return redirect(url_for("treasury_cheques"))
        if request.method == "POST":
            try:
                update_cheque(db, request.form, session.get("username", ""), cheque_id)
                db.commit()
                flash("Cheque updated.")
                return redirect(url_for("treasury_cheque_detail", cheque_id=cheque_id))
            except ValueError as exc:
                flash(str(exc))
        if request.args.get("edit"):
            return render_template(
                "treasury/cheque_form.html",
                edit_record=cheque,
                accounts=_treasury_accounts(),
                default_date=datetime.now().strftime("%Y-%m-%d"),
            )
        audit_rows = [
            dict(r) for r in db.execute(
                "SELECT * FROM treasury_audit_log WHERE entity_type='bank_cheque' AND entity_id=? "
                "ORDER BY created_at DESC LIMIT 20",
                (cheque_id,),
            ).fetchall()
        ]
        return render_template(
            "treasury/cheque_view.html",
            cheque=cheque,
            audit_rows=audit_rows,
            allowed_transitions=allowed_cheque_status_transitions(cheque.get("status") or "Issued"),
            cheque_statuses=CHEQUE_STATUSES,
            accounts=_treasury_accounts(),
            default_date=datetime.now().strftime("%Y-%m-%d"),
        )

    @app.route("/treasury/cheques/<int:cheque_id>/status", methods=["POST"])
    @login_required
    def treasury_cheque_status(cheque_id):
        db = get_db()
        _prepare_treasury_db(db)
        new_status = (request.form.get("status") or "").strip()
        remarks = (request.form.get("remarks") or "").strip()
        try:
            update_cheque_status(
                db, cheque_id, new_status, session.get("username", ""), remarks,
            )
            db.commit()
            flash(f"Cheque status updated to {new_status}.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("treasury_cheque_detail", cheque_id=cheque_id))

    @app.route("/treasury/pdc-register")
    @login_required
    def treasury_pdc_register():
        db = get_db()
        _prepare_treasury_db(db)
        filter_type = request.args.get("type", "").strip() or None
        filter_account_id = request.args.get("account_id", type=int)
        filter_status = request.args.get("status", "").strip() or None
        due_soon = request.args.get("due_soon") == "1"
        date_from = request.args.get("date_from", "").strip() or None
        date_to = request.args.get("date_to", "").strip() or None
        rows = list_pdc(
            db, filter_type, filter_account_id, filter_status,
            due_soon, date_from, date_to,
        )
        status_counts = {s: 0 for s in PDC_STATUSES}
        type_counts = {t: 0 for t in PDC_TYPES}
        for row in rows:
            st = row.get("status") or "Pending"
            if st in status_counts:
                status_counts[st] += 1
            tp = row.get("pdc_type") or "Received"
            if tp in type_counts:
                type_counts[tp] += 1
        due_alerts = upcoming_pdc_due_alerts(db)
        return render_template(
            "treasury/pdc_register.html",
            rows=rows,
            accounts=_treasury_accounts(),
            pdc_types=PDC_TYPES,
            pdc_statuses=PDC_STATUSES,
            filter_type=filter_type,
            filter_account_id=filter_account_id,
            filter_status=filter_status,
            due_soon=due_soon,
            date_from=date_from,
            date_to=date_to,
            status_counts=status_counts,
            type_counts=type_counts,
            due_alerts=due_alerts,
        )

    @app.route("/treasury/pdc-register/new", methods=["GET", "POST"])
    @login_required
    def treasury_pdc_new():
        db = get_db()
        _prepare_treasury_db(db)
        if request.method == "POST":
            try:
                new_id = create_pdc(db, request.form, session.get("username", ""))
                db.commit()
                flash("PDC created.")
                return redirect(url_for("treasury_pdc_detail", pdc_id=new_id))
            except ValueError as exc:
                flash(str(exc))
        return render_template(
            "treasury/pdc_form.html",
            edit_record=None,
            accounts=_treasury_accounts(),
            projects=_treasury_projects(),
            vendors=_treasury_vendors(),
            pdc_types=PDC_TYPES,
            default_date=datetime.now().strftime("%Y-%m-%d"),
        )

    @app.route("/treasury/pdc-register/<int:pdc_id>", methods=["GET", "POST"])
    @login_required
    def treasury_pdc_detail(pdc_id):
        db = get_db()
        _prepare_treasury_db(db)
        pdc = get_pdc(db, pdc_id)
        if not pdc:
            flash("PDC not found.")
            return redirect(url_for("treasury_pdc_register"))
        if request.method == "POST":
            try:
                update_pdc(db, request.form, session.get("username", ""), pdc_id)
                db.commit()
                flash("PDC updated.")
                return redirect(url_for("treasury_pdc_detail", pdc_id=pdc_id))
            except ValueError as exc:
                flash(str(exc))
        if request.args.get("edit"):
            return render_template(
                "treasury/pdc_form.html",
                edit_record=pdc,
                accounts=_treasury_accounts(),
                projects=_treasury_projects(),
                vendors=_treasury_vendors(),
                pdc_types=PDC_TYPES,
                default_date=datetime.now().strftime("%Y-%m-%d"),
            )
        audit_rows = [
            dict(r) for r in db.execute(
                "SELECT * FROM treasury_audit_log WHERE entity_type='pdc_register' AND entity_id=? "
                "ORDER BY created_at DESC LIMIT 20",
                (pdc_id,),
            ).fetchall()
        ]
        days_left = None
        if pdc.get("cheque_date") and pdc.get("status") in ("Pending", "Deposited"):
            try:
                due = datetime.strptime(str(pdc["cheque_date"])[:10], "%Y-%m-%d").date()
                days_left = (due - datetime.now().date()).days
            except ValueError:
                pass
        return render_template(
            "treasury/pdc_view.html",
            pdc=pdc,
            audit_rows=audit_rows,
            allowed_transitions=allowed_pdc_status_transitions(pdc.get("status") or "Pending"),
            pdc_statuses=PDC_STATUSES,
            days_left=days_left,
        )

    @app.route("/treasury/pdc-register/<int:pdc_id>/status", methods=["POST"])
    @login_required
    def treasury_pdc_status(pdc_id):
        db = get_db()
        _prepare_treasury_db(db)
        new_status = (request.form.get("status") or "").strip()
        remarks = (request.form.get("remarks") or "").strip()
        try:
            update_pdc_status(
                db, pdc_id, new_status, session.get("username", ""), remarks,
            )
            db.commit()
            flash(f"PDC status updated to {new_status}.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("treasury_pdc_detail", pdc_id=pdc_id))

    @app.route("/treasury/fixed-deposits")
    @login_required
    def treasury_fixed_deposits():
        db = get_db()
        _prepare_treasury_db(db)
        filter_account_id = request.args.get("account_id", type=int)
        filter_status = request.args.get("status", "").strip() or None
        maturing_soon = request.args.get("maturing_soon") == "1"
        rows = list_fds(db, filter_account_id, filter_status, maturing_soon)
        status_counts = {s: 0 for s in FD_STATUSES}
        for row in rows:
            st = row.get("status") or "Active"
            if st in status_counts:
                status_counts[st] += 1
        maturity_alerts = upcoming_maturity_alerts(db)
        return render_template(
            "treasury/fixed_deposits.html",
            rows=rows,
            accounts=_treasury_accounts(),
            fd_statuses=FD_STATUSES,
            filter_account_id=filter_account_id,
            filter_status=filter_status,
            maturing_soon=maturing_soon,
            status_counts=status_counts,
            maturity_alerts=maturity_alerts,
        )

    @app.route("/treasury/fixed-deposits/new", methods=["GET", "POST"])
    @login_required
    def treasury_fd_new():
        db = get_db()
        _prepare_treasury_db(db)
        if request.method == "POST":
            try:
                new_id = create_fd(db, request.form, session.get("username", ""))
                db.commit()
                flash("Fixed deposit created.")
                return redirect(url_for("treasury_fd_detail", fd_id=new_id))
            except ValueError as exc:
                flash(str(exc))
        return render_template(
            "treasury/fd_form.html",
            edit_record=None,
            accounts=_treasury_accounts(),
            default_date=datetime.now().strftime("%Y-%m-%d"),
        )

    @app.route("/treasury/fixed-deposits/<int:fd_id>", methods=["GET", "POST"])
    @login_required
    def treasury_fd_detail(fd_id):
        db = get_db()
        _prepare_treasury_db(db)
        fd = get_fd(db, fd_id)
        if not fd:
            flash("Fixed deposit not found.")
            return redirect(url_for("treasury_fixed_deposits"))
        if request.method == "POST":
            try:
                update_fd(db, request.form, session.get("username", ""), fd_id)
                db.commit()
                flash("Fixed deposit updated.")
                return redirect(url_for("treasury_fd_detail", fd_id=fd_id))
            except ValueError as exc:
                flash(str(exc))
        if request.args.get("edit"):
            return render_template(
                "treasury/fd_form.html",
                edit_record=fd,
                accounts=_treasury_accounts(),
                default_date=datetime.now().strftime("%Y-%m-%d"),
            )
        audit_rows = [
            dict(r) for r in db.execute(
                "SELECT * FROM treasury_audit_log WHERE entity_type='fixed_deposit' AND entity_id=? "
                "ORDER BY created_at DESC LIMIT 20",
                (fd_id,),
            ).fetchall()
        ]
        renewed_from = None
        if fd.get("renewed_from_id"):
            renewed_from = get_fd(db, fd["renewed_from_id"])
        return render_template(
            "treasury/fd_view.html",
            fd=fd,
            audit_rows=audit_rows,
            renewed_from=renewed_from,
            fd_statuses=FD_STATUSES,
            accounts=_treasury_accounts(),
            default_date=datetime.now().strftime("%Y-%m-%d"),
        )

    @app.route("/treasury/fixed-deposits/<int:fd_id>/close", methods=["POST"])
    @login_required
    def treasury_fd_close(fd_id):
        db = get_db()
        _prepare_treasury_db(db)
        remarks = (request.form.get("remarks") or "").strip()
        try:
            close_fd(db, fd_id, session.get("username", ""), remarks)
            db.commit()
            flash("Fixed deposit closed.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("treasury_fd_detail", fd_id=fd_id))

    @app.route("/treasury/fixed-deposits/<int:fd_id>/renew", methods=["GET", "POST"])
    @login_required
    def treasury_fd_renew(fd_id):
        db = get_db()
        _prepare_treasury_db(db)
        fd = get_fd(db, fd_id)
        if not fd:
            flash("Fixed deposit not found.")
            return redirect(url_for("treasury_fixed_deposits"))
        if fd.get("status") != "Active":
            flash("Only active fixed deposits can be renewed.")
            return redirect(url_for("treasury_fd_detail", fd_id=fd_id))
        if request.method == "POST":
            try:
                new_id = renew_fd(db, fd_id, request.form, session.get("username", ""))
                db.commit()
                flash("Fixed deposit renewed.")
                return redirect(url_for("treasury_fd_detail", fd_id=new_id))
            except ValueError as exc:
                flash(str(exc))
        today = datetime.now()
        default_start = today.strftime("%Y-%m-%d")
        default_maturity = (today + timedelta(days=365)).strftime("%Y-%m-%d")
        suggested_number = f"{fd.get('fd_number', 'FD')}-R1"
        return render_template(
            "treasury/fd_form.html",
            edit_record={
                "bank_account_id": fd.get("bank_account_id"),
                "fd_number": suggested_number,
                "amount": (fd.get("amount") or 0) + (fd.get("accrued_interest_calc") or 0),
                "interest_rate": fd.get("interest_rate"),
                "start_date": default_start,
                "maturity_date": default_maturity,
                "remarks": f"Renewed from {fd.get('fd_number')}",
            },
            accounts=_treasury_accounts(),
            default_date=default_start,
            renew_from=fd,
        )

    @app.route("/treasury/cash-flow-forecast")
    @login_required
    def treasury_cash_flow_forecast():
        db = get_db()
        _prepare_treasury_db(db)
        period = (request.args.get("period") or "30").strip()
        if period not in CASH_FLOW_FORECAST_PERIODS:
            period = "30"
        project_id = request.args.get("project_id", type=int)
        forecast = get_cash_flow_forecast(db, period, project_id)
        return render_template(
            "treasury/cash_flow_forecast.html",
            forecast=forecast,
            period=period,
            filter_project_id=project_id,
            periods=CASH_FLOW_FORECAST_PERIODS,
        )

    @app.route("/treasury/document-vault")
    @login_required
    def treasury_document_vault():
        db = get_db()
        _prepare_treasury_db(db)
        document_type = request.args.get("document_type", "").strip() or None
        entity_type = request.args.get("entity_type", "").strip() or None
        entity_id = request.args.get("entity_id", type=int)
        search = request.args.get("q", "").strip() or None
        rows = list_bank_documents(
            db,
            document_type=document_type,
            entity_type=entity_type,
            entity_id=entity_id,
            search=search,
        )
        entity_options = get_bank_document_entity_options(db)
        return render_template(
            "treasury/document_vault.html",
            rows=rows,
            document_types=BANK_DOCUMENT_TYPES,
            entity_types=BANK_DOCUMENT_ENTITY_TYPES,
            entity_options=entity_options,
            filter_document_type=document_type,
            filter_entity_type=entity_type,
            filter_entity_id=entity_id,
            search=search or "",
            allowed_extensions=", ".join(sorted(ext.lstrip(".") for ext in TREASURY_ALLOWED_EXTENSIONS)),
        )

    @app.route("/treasury/document-vault/upload", methods=["GET", "POST"])
    @login_required
    def treasury_document_vault_upload():
        db = get_db()
        _prepare_treasury_db(db)
        entity_options = get_bank_document_entity_options(db)
        if request.method == "POST":
            file_storage = request.files.get("document_file")
            upload_error = validate_treasury_document_upload(file_storage)
            if upload_error:
                flash(upload_error)
                return redirect(url_for("treasury_document_vault_upload"))
            original_filename = secure_filename(file_storage.filename)
            file_storage.seek(0, os.SEEK_END)
            file_size = file_storage.tell()
            file_storage.seek(0)
            saved_name = _save_upload(file_storage)
            if not saved_name:
                flash("File upload failed.")
                return redirect(url_for("treasury_document_vault_upload"))
            try:
                doc_id = upload_bank_document(
                    db,
                    request.form,
                    saved_name,
                    original_filename,
                    file_size,
                    session.get("username", ""),
                )
                db.commit()
                flash("Document uploaded.")
                return redirect(url_for("treasury_document_vault_view", doc_id=doc_id))
            except ValueError as exc:
                flash(str(exc))
                return redirect(url_for("treasury_document_vault_upload"))
        return render_template(
            "treasury/document_upload.html",
            document_types=BANK_DOCUMENT_TYPES,
            entity_types=BANK_DOCUMENT_ENTITY_TYPES,
            entity_options=entity_options,
            default_entity_map=DOCUMENT_TYPE_DEFAULT_ENTITY,
            allowed_extensions=", ".join(sorted(ext.lstrip(".") for ext in TREASURY_ALLOWED_EXTENSIONS)),
        )

    @app.route("/treasury/document-vault/<int:doc_id>")
    @login_required
    def treasury_document_vault_view(doc_id):
        db = get_db()
        _prepare_treasury_db(db)
        doc = get_bank_document(db, doc_id)
        if not doc:
            flash("Document not found.")
            return redirect(url_for("treasury_document_vault"))
        return render_template("treasury/document_view.html", doc=doc)

    @app.route("/treasury/document-vault/<int:doc_id>/download")
    @login_required
    def treasury_document_vault_download(doc_id):
        db = get_db()
        _prepare_treasury_db(db)
        doc = get_bank_document(db, doc_id)
        if not doc or not doc.get("file_path"):
            flash("File not available for download.")
            return redirect(url_for("treasury_document_vault_view", doc_id=doc_id))
        safe_name = secure_filename(doc["file_path"])
        path = os.path.join(docs_dir, safe_name)
        if not os.path.isfile(path):
            flash("File not found on server.")
            return redirect(url_for("treasury_document_vault_view", doc_id=doc_id))
        download_name = secure_filename(doc.get("original_filename") or safe_name)
        return send_from_directory(docs_dir, safe_name, as_attachment=True, download_name=download_name)

    @app.route("/treasury/document-vault/<int:doc_id>/delete", methods=["POST"])
    @login_required
    def treasury_document_vault_delete(doc_id):
        db = get_db()
        _prepare_treasury_db(db)
        try:
            delete_bank_document(db, doc_id, session.get("username", ""))
            db.commit()
            flash("Document archived.")
        except ValueError as exc:
            flash(str(exc))
        return redirect(url_for("treasury_document_vault"))

    @app.route("/treasury/budget-control")
    @login_required
    def treasury_budget_control():
        db = get_db()
        _prepare_treasury_db(db)
        fiscal_year = (request.args.get("fiscal_year") or "").strip() or None
        overview = list_project_budget_overview(db, fiscal_year)
        alerts = budget_alerts(db, fiscal_year)
        return render_template(
            "treasury/budget_control.html",
            overview=overview,
            alerts=alerts,
            fiscal_year=fiscal_year,
        )

    @app.route("/treasury/budget-control/project/<int:project_id>")
    @login_required
    def treasury_budget_control_project(project_id):
        db = get_db()
        _prepare_treasury_db(db)
        fiscal_year = (request.args.get("fiscal_year") or "").strip() or None
        project = get_project_budget(db, project_id)
        if not project:
            flash("Project not found.")
            return redirect(url_for("treasury_budget_control"))
        lines = get_project_budget_lines(db, project_id, fiscal_year)
        summary = get_project_budget_summary(db, project_id, fiscal_year)
        audit_rows = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM treasury_audit_log WHERE entity_type='project_budget' "
                "AND entity_id=? ORDER BY created_at DESC LIMIT 15",
                (project_id,),
            ).fetchall()
        ]
        return render_template(
            "treasury/project_budget.html",
            project=project,
            lines=lines,
            summary=summary,
            fiscal_year=fiscal_year,
            audit_rows=audit_rows,
        )

    @app.route("/treasury/budget-control/project/<int:project_id>/edit", methods=["GET", "POST"])
    @login_required
    def treasury_budget_control_edit(project_id):
        db = get_db()
        _prepare_treasury_db(db)
        fiscal_year = (request.args.get("fiscal_year") or "").strip() or None
        project = get_project_budget(db, project_id)
        if not project:
            flash("Project not found.")
            return redirect(url_for("treasury_budget_control"))
        if request.method == "POST":
            try:
                save_project_budgets(
                    db,
                    project_id,
                    request.form,
                    session.get("username", ""),
                    fiscal_year=request.form.get("fiscal_year") or fiscal_year,
                )
                db.commit()
                flash("Project budget saved.")
                return redirect(url_for("treasury_budget_control_project", project_id=project_id))
            except ValueError as exc:
                flash(str(exc))
        lines = get_project_budget_lines(db, project_id, fiscal_year, sync_modules=True)
        line_map = {ln["category"]: ln for ln in lines if ln["category"] != "Total"}
        return render_template(
            "treasury/budget_form.html",
            project=project,
            categories=BUDGET_CATEGORIES,
            line_map=line_map,
            fiscal_year=fiscal_year,
        )

    @app.route("/treasury/project-profitability")
    @login_required
    def treasury_project_profitability():
        db = get_db()
        _prepare_treasury_db(db)
        fiscal_year = (request.args.get("fiscal_year") or "").strip() or None
        show_all = request.args.get("all_projects") == "1"
        rows = list_all_projects_profitability(
            db, fiscal_year, active_only=not show_all,
        )
        summary = {
            "project_count": len(rows),
            "total_contract": round(sum(r["contract_value"] for r in rows), 2),
            "total_billing": round(sum(r["client_billing"] for r in rows), 2),
            "total_receipts": round(sum(r["receipts"] for r in rows), 2),
            "total_net_profit": round(sum(r["net_profit"] for r in rows), 2),
        }
        return render_template(
            "treasury/project_profitability.html",
            rows=rows,
            summary=summary,
            fiscal_year=fiscal_year,
            show_all=show_all,
        )

    @app.route("/treasury/project-profitability/<int:project_id>")
    @login_required
    def treasury_project_profitability_detail(project_id):
        db = get_db()
        _prepare_treasury_db(db)
        fiscal_year = (request.args.get("fiscal_year") or "").strip() or None
        pnl = get_project_profitability(db, project_id, fiscal_year)
        if not pnl:
            flash("Project not found.")
            return redirect(url_for("treasury_project_profitability"))
        return render_template(
            "treasury/project_profitability_detail.html",
            pnl=pnl,
            fiscal_year=fiscal_year,
        )

    # Phase 2 scaffold routes
    _phase2 = [
        ("treasury_contract_management", "Contract Management"),
        ("treasury_claims", "Claims Management"),
        ("treasury_equipment_costing", "Equipment Costing"),
        ("treasury_labour_productivity", "Labour Productivity"),
        ("treasury_command_center", "Management Command Center"),
        ("treasury_alert_engine", "Alert Engine"),
        ("treasury_document_numbering", "Document Numbering"),
        ("treasury_backup_system", "Backup System"),
    ]

    for endpoint, feature_name in _phase2:
        def _make_view(name=feature_name, ep=endpoint):
            @login_required
            def view():
                return render_template(
                    "treasury/coming_soon.html",
                    feature_name=name,
                    page_title=name,
                    breadcrumbs=(
                        f'<a href="{url_for("dashboard")}">Home</a> &gt; '
                        f'<a href="{url_for("treasury_hub")}">Treasury</a> &gt; {name}'
                    ),
                )
            return view
        app.add_url_rule(
            f"/treasury/{endpoint.replace('treasury_', '').replace('_', '-')}",
            endpoint=endpoint,
            view_func=_make_view(),
        )
