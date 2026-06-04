"""Payment Voucher — create, workflow, PDF, print, and email."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from modules.approval_workflow import normalize_status
from modules.branding import ERP_LEGAL_NAME
from modules.database import DATE_FMT, DATE_INPUT_FMT, load_employee_options, load_project_names, load_subcontractor_names, load_vendors
from modules.document_pdfs import generate_payment_voucher_pdf
from modules.notifications import send_email_notification, smtp_config
from modules.pages import _save_upload
from modules.payment_voucher_db import (
    PAYMENT_MODES,
    PAYMENT_TYPES,
    ensure_payment_voucher_schema,
    get_payment_voucher,
    list_payment_vouchers,
    load_payment_voucher_audit,
    save_payment_voucher,
    voucher_is_editable,
)
from modules.roles import can_create_payment_vouchers


def _actor() -> str:
    return st.session_state.get("user_name", "User")


def _role() -> str:
    return st.session_state.get("user_role", "Admin")


def _payment_voucher_html(row: dict) -> str:
    from modules.pdf_templates import format_inr

    approval_rows = []
    for label, by_key, date_key in (
        ("Prepared", "prepared_by", "prepared_date"),
        ("Checked", "checked_by", "checked_date"),
        ("Approved", "approved_by", "approved_date"),
        ("Payment Released", "payment_released_by", "payment_released_date"),
        ("Paid", "paid_by", "paid_date"),
    ):
        by = row.get(by_key) or ""
        dt = row.get(date_key) or ""
        if by or dt:
            approval_rows.append(f"<tr><td>{label}</td><td>{by or '—'}</td><td>{dt or '—'}</td></tr>")
    approval_html = (
        "<table><tr><th>Step</th><th>By</th><th>Date</th></tr>" + "".join(approval_rows) + "</table>"
        if approval_rows
        else "<p>—</p>"
    )
    return f"""
    <html><head><meta charset="utf-8"/>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 24px; }}
      h2 {{ color: #1a365d; }}
      table.kv td {{ padding: 6px 12px; border: none; }}
      table.kv td:first-child {{ font-weight: bold; width: 180px; }}
      .amount {{ font-size: 1.25em; font-weight: bold; color: #1a365d; }}
      @media print {{ button {{ display: none; }} }}
    </style></head><body>
    <h2>{ERP_LEGAL_NAME}</h2>
    <h3>Payment Voucher</h3>
    <table class="kv">
      <tr><td>Voucher No</td><td>{row.get('voucher_no') or row.get('voucher_id')}</td></tr>
      <tr><td>Date</td><td>{row.get('payment_date') or row.get('voucher_date')}</td></tr>
      <tr><td>Payment Type</td><td>{row.get('payment_type') or '—'}</td></tr>
      <tr><td>Payee</td><td>{row.get('payee_name') or row.get('supplier') or '—'}</td></tr>
      <tr><td>Project</td><td>{row.get('project_name') or '—'}</td></tr>
      <tr><td>Mode</td><td>{row.get('payment_mode') or '—'}</td></tr>
      <tr><td>Reference</td><td>{row.get('reference_no') or '—'}</td></tr>
      <tr><td>Status</td><td>{row.get('status') or '—'}</td></tr>
      <tr><td>Remarks</td><td>{row.get('remarks') or '—'}</td></tr>
      <tr><td>Amount</td><td class="amount">{format_inr(row.get('amount'))}</td></tr>
    </table>
    <h4>Approval chain</h4>
    {approval_html}
    </body></html>
    """


def _render_pdf_actions(row: dict, key_prefix: str) -> None:
    voucher_id = row["voucher_id"]
    st.markdown("#### Download / Print / Email")
    try:
        pdf_bytes = generate_payment_voucher_pdf(voucher_id)
    except Exception as exc:
        st.error(str(exc))
        pdf_bytes = None

    html = _payment_voucher_html(row)
    c1, c2, c3 = st.columns(3)
    if pdf_bytes:
        c1.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=f"payment_voucher_{row.get('voucher_no') or voucher_id}.pdf",
            mime="application/pdf",
            key=f"{key_prefix}_dl_pdf",
            use_container_width=True,
        )
    else:
        c1.caption("PDF unavailable.")
    c2.download_button(
        "Download HTML (print)",
        data=html,
        file_name=f"payment_voucher_{row.get('voucher_no') or voucher_id}.html",
        mime="text/html",
        key=f"{key_prefix}_dl_html",
        use_container_width=True,
    )
    with c3:
        _render_email_panel(row, pdf_bytes, key_prefix)

    st.caption("Use browser Print (Ctrl+P) on the preview below.")
    st.components.v1.html(html, height=420, scrolling=True)


def _render_email_panel(row: dict, pdf_bytes: bytes | None, key_prefix: str) -> None:
    cfg = smtp_config()
    if not cfg.get("configured"):
        st.warning("SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM in environment or app settings.")
        return

    default_to = ""
    payee_id = row.get("payee_id") or ""
    if row.get("payment_type") == "Vendor Payment" and payee_id:
        vendors = load_vendors()
        if not vendors.empty:
            match = vendors[vendors["vendor_id"] == payee_id]
            if not match.empty:
                default_to = str(match.iloc[0].get("email") or "")

    to_addr = st.text_input("Email to", value=default_to, key=f"{key_prefix}_email_to")
    if st.button("Email PDF", key=f"{key_prefix}_email_btn", use_container_width=True):
        if not to_addr.strip():
            st.error("Enter recipient email.")
            return
        subject = f"Payment Voucher {row.get('voucher_no') or row.get('voucher_id')}"
        body = (
            f"Please find payment voucher {row.get('voucher_no')} dated {row.get('payment_date')} "
            f"for {row.get('payee_name')} — amount as per attached PDF.\n\n— {ERP_LEGAL_NAME}"
        )
        if pdf_bytes:
            ok = _send_voucher_email_with_pdf(to_addr.strip(), subject, body, pdf_bytes, row)
        else:
            ok = send_email_notification(to_addr.strip(), subject, body)
        if ok:
            st.success(f"Email sent to {to_addr.strip()}.")
        else:
            st.error("Email could not be sent. Check SMTP settings and logs.")


def _send_voucher_email_with_pdf(to_address: str, subject: str, body: str, pdf_bytes: bytes, row: dict) -> bool:
    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    cfg = smtp_config()
    if not cfg.get("configured") or not (cfg.get("password") or cfg.get("port") == 25):
        return send_email_notification(to_address, subject, body)

    from_addr = cfg["from_addr"] or cfg["user"]
    if not from_addr:
        return False

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    fname = f"payment_voucher_{row.get('voucher_no') or row.get('voucher_id')}.pdf"
    part = MIMEApplication(pdf_bytes, _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename=fname)
    msg.attach(part)

    try:
        if cfg["use_tls"]:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if cfg["password"]:
                    server.login(cfg["user"], cfg["password"])
                server.sendmail(from_addr, [to_address], msg.as_string())
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
                if cfg["password"]:
                    server.login(cfg["user"], cfg["password"])
                server.sendmail(from_addr, [to_address], msg.as_string())
        return True
    except Exception:
        return False


def _payee_inputs(payment_type: str, key_prefix: str) -> tuple[str, str]:
    payee_id = ""
    payee_name = ""
    if payment_type == "Employee Payment":
        options = load_employee_options()
        labels = [f"{eid} — {ename}" for eid, ename in options]
        pick = st.selectbox("Employee", [""] + labels, key=f"{key_prefix}_emp")
        if pick:
            payee_id = pick.split(" — ", 1)[0]
            payee_name = pick.split(" — ", 1)[-1] if " — " in pick else pick
    elif payment_type == "Subcontractor Payment":
        subs = [""] + load_subcontractor_names()
        payee_name = st.selectbox("Subcontractor", subs, key=f"{key_prefix}_sub")
    elif payment_type == "Vendor Payment":
        vendors = load_vendors()
        if vendors.empty:
            payee_name = st.text_input("Vendor name", key=f"{key_prefix}_vnd_txt")
        else:
            labels = {
                f"{r.supplier_name} ({r.vendor_id})": r.vendor_id
                for _, r in vendors.iterrows()
                if r.get("supplier_name")
            }
            pick = st.selectbox("Vendor", [""] + list(labels.keys()), key=f"{key_prefix}_vnd")
            if pick:
                payee_id = labels[pick]
                payee_name = pick.split(" (", 1)[0]
    else:
        payee_name = st.text_input("Payee / petty cash account", key=f"{key_prefix}_pc")
    return payee_id, payee_name


def _render_voucher_form(voucher_id: str | None = None) -> None:
    row = get_payment_voucher(voucher_id) if voucher_id else None
    if row and not voucher_is_editable(row.get("status")):
        st.warning(f"This voucher is **{normalize_status(row.get('status'), 'payment_voucher')}** and cannot be edited.")
        return

    defaults = row or {}

    def _parse_vdate(raw: str | None):
        if not raw:
            return datetime.now().date()
        try:
            return datetime.strptime(raw, DATE_FMT).date()
        except ValueError:
            return datetime.now().date()

    with st.form("pv_form" if not voucher_id else f"pv_edit_{voucher_id}", clear_on_submit=not voucher_id):
        c1, c2, c3 = st.columns(3)
        vdate = c1.date_input(
            "Voucher date",
            value=_parse_vdate(defaults.get("payment_date") or defaults.get("voucher_date")),
            format=DATE_INPUT_FMT,
        )
        payment_type = c2.selectbox(
            "Payment type",
            PAYMENT_TYPES,
            index=PAYMENT_TYPES.index(defaults["payment_type"])
            if defaults.get("payment_type") in PAYMENT_TYPES
            else 0,
        )
        payment_mode = c3.selectbox(
            "Payment mode",
            PAYMENT_MODES,
            index=PAYMENT_MODES.index(defaults["payment_mode"])
            if defaults.get("payment_mode") in PAYMENT_MODES
            else 1,
        )
        if row:
            st.text_input("Payee", value=defaults.get("payee_name") or defaults.get("supplier") or "", disabled=True)
            payee_id = defaults.get("payee_id") or ""
            payee_name = defaults.get("payee_name") or defaults.get("supplier") or ""
        else:
            payee_id, payee_name = _payee_inputs(payment_type, "pv_form")

        projects = [""] + load_project_names()
        proj_idx = 0
        if defaults.get("project_name") in projects:
            proj_idx = projects.index(defaults["project_name"])
        c1, c2, c3 = st.columns(3)
        project_name = c1.selectbox("Project", projects, index=proj_idx)
        amount = c2.number_input("Amount", min_value=0.0, step=100.0, value=float(defaults.get("amount") or 0))
        reference_no = c3.text_input("Reference no.", value=defaults.get("reference_no") or "")
        remarks = st.text_area("Remarks", value=defaults.get("remarks") or "")
        upload = st.file_uploader("Attachment", key=f"pv_att_{voucher_id or 'new'}")

        if st.form_submit_button("Save voucher", type="primary", use_container_width=True):
            att_path = defaults.get("attachment") or ""
            if upload:
                att_path = _save_upload(upload, "uploads/finance/payment_vouchers", voucher_id or "pv_new")
            try:
                vid, vno = save_payment_voucher(
                    {
                        "voucher_id": voucher_id,
                        "payment_type": payment_type,
                        "payee_id": payee_id,
                        "payee_name": payee_name,
                        "voucher_date": vdate,
                        "payment_mode": payment_mode,
                        "amount": amount,
                        "reference_no": reference_no,
                        "project_name": project_name,
                        "remarks": remarks,
                        "attachment": att_path,
                    },
                    _actor(),
                )
                st.success(f"Saved payment voucher **{vno or vid}**.")
                st.session_state["pv_selected"] = vid
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def _render_voucher_detail(voucher_id: str) -> None:
    row = get_payment_voucher(voucher_id)
    if not row:
        st.error("Voucher not found.")
        return

    st.markdown(f"### {row.get('voucher_no') or voucher_id}")
    status = normalize_status(row.get("status"), "payment_voucher")
    st.caption(f"Status: **{status}** · Type: {row.get('payment_type')} · Payee: {row.get('payee_name')}")

    from modules.workflow_ui import render_workflow_action_panel, render_workflow_status_steps

    render_workflow_status_steps(status)
    if render_workflow_action_panel(
        "payment_voucher",
        voucher_id,
        status,
        key_prefix="pv_wf",
        show_payment_ref=True,
    ):
        st.rerun()

    if voucher_is_editable(row.get("status")):
        with st.expander("Edit voucher", expanded=False):
            _render_voucher_form(voucher_id)

    _render_pdf_actions(row, f"pv_{voucher_id}")

    audit = load_payment_voucher_audit(voucher_id)
    if not audit.empty:
        with st.expander("Audit log", expanded=False):
            st.dataframe(audit, use_container_width=True, hide_index=True)


def page_payment_voucher() -> None:
    ensure_payment_voucher_schema()
    st.subheader("Payment Voucher")
    st.caption("Draft → Prepared → Checked → Approved → Payment Released → Paid")

    if not can_create_payment_vouchers(_role()):
        st.warning("Your role cannot create payment vouchers.")
        return

    tab_list, tab_new = st.tabs(["Voucher register", "New voucher"])

    with tab_new:
        _render_voucher_form()

    with tab_list:
        df = list_payment_vouchers(limit=300)
        if df.empty:
            st.info("No payment vouchers yet. Create one under **New voucher**.")
        else:
            st.dataframe(
                df[
                    [
                        c
                        for c in (
                            "voucher_no",
                            "payment_date",
                            "payment_type",
                            "payee_name",
                            "amount",
                            "payment_mode",
                            "status",
                        )
                        if c in df.columns
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
            labels = {
                f"{r.voucher_no or r.voucher_id} | {r.payment_date} | {r.payee_name} | {r.status}": r.voucher_id
                for _, r in df.iterrows()
            }
            pick = st.selectbox("Open voucher", [""] + list(labels.keys()), key="pv_open_pick")
            if pick:
                _render_voucher_detail(labels[pick])
