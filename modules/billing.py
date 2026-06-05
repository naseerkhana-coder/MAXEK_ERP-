"""Client and Sub Contractor billing with printable bills."""

from datetime import datetime

import pandas as pd
import streamlit as st

from modules.branding import ERP_LEGAL_NAME
from modules.document_pdfs import generate_client_invoice_pdf, generate_subcontractor_bill_pdf
from modules.database import (
    DATE_FMT,
    generate_id,
    get_conn,
    log_finance_audit,
    next_document_number,
    load_client_names,
    load_pending_client_bill_dprs,
    load_project_boq_by_project,
    load_project_names,
    load_subcontractor_names,
    parse_month_value,
    subcontractor_bill_preview,
    subcontractor_manpower_bill_preview,
    subcontractor_quantity_bill_preview,
)


def _timestamp():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _bill_html(title, header_rows, line_rows, totals, footer=""):
    header_html = "".join(f"<tr><td><strong>{k}</strong></td><td>{v}</td></tr>" for k, v in header_rows)
    lines_html = ""
    if line_rows:
        cols = line_rows[0].keys()
        lines_html += "<tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr>"
        for row in line_rows:
            lines_html += "<tr>" + "".join(f"<td>{row[c]}</td>" for c in cols) + "</tr>"
    totals_html = "".join(f"<tr><td colspan='4' align='right'><strong>{k}</strong></td><td><strong>{v}</strong></td></tr>" for k, v in totals)
    return f"""
    <html><head><meta charset="utf-8"/>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 24px; }}
      h2 {{ color: #1a365d; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
      th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
      th {{ background: #edf2f7; }}
      .totals td {{ border: none; }}
      @media print {{ button {{ display: none; }} }}
    </style></head><body>
    <h2>{ERP_LEGAL_NAME}</h2>
    <h3>{title}</h3>
    <table>{header_html}</table>
    <table>{lines_html}</table>
    <table class="totals">{totals_html}</table>
    <p>{footer}</p>
    </body></html>
    """


def _render_print_download(html, filename, *, pdf_bytes=None, pdf_filename=None):
    st.markdown("#### Download / Print")
    c1, c2 = st.columns(2)
    if pdf_bytes and pdf_filename:
        c1.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=pdf_filename,
            mime="application/pdf",
            width="stretch",
            key=f"pdf_{pdf_filename}",
        )
    else:
        c1.caption("PDF not available for this bill.")
    c2.download_button(
        "Download HTML",
        data=html,
        file_name=filename,
        mime="text/html",
        width="stretch",
        key=f"html_{filename}",
    )
    st.caption("Or use browser Print (Ctrl+P) on the preview below → Save as PDF.")
    st.components.v1.html(html, height=480, scrolling=True)


def _render_client_bill_tab():
    st.markdown("### Client Bill")
    st.caption("Amount = Quantity × BOQ approved rate. Source: DPR measurements marked for billing.")
    pending_df = load_pending_client_bill_dprs()
    if not pending_df.empty:
        st.markdown("#### Pending from DPR (ready to invoice client)")
        show_df = pending_df.copy()
        show_df["pending_amount"] = show_df["pending_qty"] * show_df["approved_rate"]
        show_df["already_billed_qty"] = show_df["client_billed_quantity"]
        show_df["balance_billing_qty"] = show_df["pending_qty"]
        st.dataframe(
            show_df[
                [
                    "dpr_id",
                    "dpr_date",
                    "project_name",
                    "client_name",
                    "boq_number",
                    "billable_progress",
                    "already_billed_qty",
                    "balance_billing_qty",
                    "pending_qty",
                    "approved_rate",
                    "pending_amount",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

    st.session_state.setdefault("client_bill_draft_lines", [])
    clients = [""] + load_client_names()
    projects = [""] + load_project_names()

    h1, h2, h3 = st.columns(3)
    bill_date = h1.date_input("Bill Date", key="cb_bill_date")
    client_name = h2.selectbox("Client", clients, key="cb_client")
    project_name = h3.selectbox("Project", projects, key="cb_project")

    if pending_df.empty:
        st.info("No DPR quantities pending client bill. Mark DPR as billed first (DPR → Pending Billing).")
    else:
        dpr_options = {
            f"{row['dpr_id']} | {row['boq_number']} | pending {row['pending_qty']:,.2f} {row['unit']}": row
            for _, row in pending_df.iterrows()
        }
        pick_label = st.selectbox("Add line from DPR", [""] + list(dpr_options.keys()), key="cb_dpr_pick")
        a1, a2, a3 = st.columns(3)
        if pick_label and pick_label in dpr_options:
            row = dpr_options[pick_label]
            max_qty = float(row["pending_qty"])
            add_qty = a1.number_input("Bill Quantity", min_value=0.0, max_value=max_qty, value=max_qty, step=0.01)
            rate = float(row["approved_rate"])
            a2.metric("Rate (Rs)", f"{rate:,.2f}")
            a3.metric("Line Amount", f"{add_qty * rate:,.2f}")
            if st.button("ADD LINE TO BILL", key="cb_add_line"):
                st.session_state.client_bill_draft_lines.append(
                    {
                        "dpr_id": row["dpr_id"],
                        "boq_item_id": row["boq_item_id"],
                        "boq_number": row["boq_number"],
                        "description": row["boq_description"],
                        "unit": row["unit"],
                        "quantity": add_qty,
                        "rate": rate,
                        "amount": add_qty * rate,
                    }
                )
                st.rerun()

    boq_df = load_project_boq_by_project(project_name) if project_name else pd.DataFrame()
    if not boq_df.empty:
        with st.expander("Manual BOQ line (without DPR)"):
            boq_map = {}
            seen_labels: dict[str, int] = {}
            for _, r in boq_df.iterrows():
                base = f"{r['boq_number']} | {str(r.get('description') or '')[:30]}"
                seen_labels[base] = seen_labels.get(base, 0) + 1
                label = base
                if seen_labels[base] > 1 and "id" in boq_df.columns:
                    label = f"{base} (#{int(r['id'])})"
                boq_map[label] = r
            manual_pick = st.selectbox("BOQ", [""] + list(boq_map.keys()), key="cb_manual_boq")
            m1, m2 = st.columns(2)
            manual_qty = m1.number_input("Quantity", min_value=0.0, step=0.01, key="cb_manual_qty")
            if manual_pick in boq_map:
                mr = boq_map[manual_pick]
                manual_rate = float(mr["approved_rate"] or 0)
                m2.metric("Rate", f"{manual_rate:,.2f}")
                if st.button("ADD MANUAL LINE", key="cb_add_manual"):
                    if manual_qty <= 0:
                        st.error("Quantity required.")
                    else:
                        st.session_state.client_bill_draft_lines.append(
                            {
                                "dpr_id": "",
                                "boq_item_id": mr["boq_item_id"],
                                "boq_number": mr["boq_number"],
                                "description": mr["description"],
                                "unit": mr["unit"],
                                "quantity": manual_qty,
                                "rate": manual_rate,
                                "amount": manual_qty * manual_rate,
                            }
                        )
                        st.rerun()

    if st.session_state.client_bill_draft_lines:
        draft_df = pd.DataFrame(st.session_state.client_bill_draft_lines)
        st.dataframe(draft_df, width="stretch", hide_index=True)
        total = draft_df["amount"].sum()
        st.success(f"Bill total: Rs {total:,.2f}")
        remarks = st.text_input("Bill Remarks", key="cb_remarks")
        if st.button("GENERATE CLIENT BILL", type="primary", width="stretch"):
            from modules.phase3_integration import run_after_client_bill_saved
            from modules.phase3_integration_db import validate_client_bill_lines

            ok, errs = validate_client_bill_lines(st.session_state.client_bill_draft_lines)
            if not ok:
                for err in errs:
                    st.error(err)
                st.stop()
            bill_id = generate_id("CBL", "client_bills")
            bill_no = generate_id("CB", "client_bills")
            conn = get_conn()
            conn.execute(
                """
                INSERT INTO client_bills(
                    bill_id, bill_no, bill_date, client_name, project_name,
                    total_amount, remarks, status, created_by, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    bill_id,
                    bill_no,
                    bill_date.strftime(DATE_FMT),
                    client_name,
                    project_name,
                    float(total),
                    remarks,
                    "Generated",
                    st.session_state.get("user_name", "User"),
                    _timestamp(),
                ),
            )
            for line in st.session_state.client_bill_draft_lines:
                line_id = generate_id("CBN", "client_bill_lines")
                conn.execute(
                    """
                    INSERT INTO client_bill_lines(
                        line_id, bill_id, dpr_id, boq_item_id, boq_number, description, unit, quantity, rate, amount
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        line_id,
                        bill_id,
                        line.get("dpr_id", ""),
                        line.get("boq_item_id", ""),
                        line["boq_number"],
                        line["description"],
                        line["unit"],
                        line["quantity"],
                        line["rate"],
                        line["amount"],
                    ),
                )
                if line.get("dpr_id"):
                    conn.execute(
                        """
                        UPDATE dpr_reports
                        SET client_billed_quantity = COALESCE(client_billed_quantity, 0) + ?
                        WHERE dpr_id = ?
                        """,
                        (line["quantity"], line["dpr_id"]),
                    )
            conn.commit()
            conn.close()
            try:
                run_after_client_bill_saved(project_name)
            except Exception:
                pass
            st.session_state.client_bill_draft_lines = []
            st.session_state["print_client_bill_id"] = bill_id
            st.success(f"Client bill created. Bill No: {bill_no}")
            st.rerun()


SUBCONTRACTOR_BILL_MODES = {
    "Measurement Based Billing (BOQ)": ("Quantity", subcontractor_quantity_bill_preview),
    "Payroll Based Billing (Attendance)": ("Manpower", subcontractor_manpower_bill_preview),
}


def _render_subcontractor_billing_tab():
    st.markdown("### Subcontractor Billing")
    st.caption(
        "**Measurement Based** — BOQ / quantity entries from subcontractor BOQ. "
        "**Payroll Based** — attendance × rates (designation-wise labour + OT)."
    )
    mode_label = st.radio(
        "Bill type",
        list(SUBCONTRACTOR_BILL_MODES.keys()),
        horizontal=True,
        key="sub_bill_mode",
    )
    bill_type, preview_fn = SUBCONTRACTOR_BILL_MODES[mode_label]
    _render_sub_bill_tab(bill_type, preview_fn, f"Sub Contractor — {mode_label}", mode_label=mode_label)


def _render_sub_bill_tab(bill_type, preview_fn, title, mode_label: str = ""):
    st.markdown(f"### {title}")
    if mode_label:
        st.info(f"Billing mode: **{mode_label}**")
    subcontractors = [""] + load_subcontractor_names()
    c1, c2 = st.columns(2)
    sub_name = c1.selectbox("Sub Contractor", subcontractors, key=f"sub_bill_{bill_type}")
    bill_month_date = c2.date_input("Bill Month", key=f"sub_month_{bill_type}")
    bill_month = parse_month_value(bill_month_date.strftime("%m/%Y"))
    if not sub_name:
        return
    preview = preview_fn(sub_name, bill_month)
    p1, p2, p3, p4, p5 = st.columns(5)
    if bill_type == "Quantity":
        p1.metric("BOQ / Measurement", f"Rs {preview['boq_amount']:,.2f}")
        p2.metric("Advance", f"Rs {preview['advance_amount']:,.2f}")
        p3.metric("Net Payable", f"Rs {preview['net_amount']:,.2f}")
        p4.caption("Labour/OT excluded in measurement mode.")
        p5.empty()
    else:
        p1.metric("Labour", f"Rs {preview['labour_amount']:,.2f}")
        p2.metric("OT", f"Rs {preview.get('ot_amount', 0):,.2f}")
        p3.metric("Advance", f"Rs {preview['advance_amount']:,.2f}")
        p4.metric("Net Payable", f"Rs {preview['net_amount']:,.2f}")
        p5.caption("BOQ excluded in payroll mode.")
    remarks = st.text_input("Remarks", key=f"sub_rem_{bill_type}")
    if st.button(f"GENERATE BILL", type="primary", width="stretch", key=f"gen_{bill_type}"):
        bill_id = generate_id("SBL", "subcontractor_bills")
        labour_total = float(preview["labour_amount"]) + float(preview.get("ot_amount", 0))
        conn = get_conn()
        doc_no = next_document_number("subcontractor_bill", conn=conn)
        conn.execute(
            """
            INSERT INTO subcontractor_bills(
                bill_id, document_no, bill_date, bill_month, subcontractor_name, bill_type,
                labour_amount, ot_amount, boq_amount, advance_amount, total_amount, net_amount, remarks, status
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                bill_id,
                doc_no,
                datetime.now().strftime(DATE_FMT),
                preview["bill_month"],
                sub_name,
                bill_type,
                preview["labour_amount"],
                preview.get("ot_amount", 0),
                preview["boq_amount"],
                preview["advance_amount"],
                preview["total_amount"],
                preview["net_amount"],
                remarks,
                "Draft",
            ),
        )
        log_finance_audit(
            conn,
            "subcontractor_bill",
            bill_id,
            "Created",
            st.session_state.get("user_name", "User"),
            "",
            "Generated",
            remarks,
            {"document_no": doc_no},
        )
        conn.commit()
        conn.close()
        st.session_state[f"print_sub_bill_id"] = bill_id
        st.success(f"Bill generated: {doc_no}")
        st.rerun()


def _render_bill_register_tab():
    st.markdown("### Bill Register & Print")
    conn = get_conn()
    client_df = pd.read_sql_query(
        """
        SELECT bill_no, bill_date, client_name, project_name, total_amount, status, bill_id
        FROM client_bills ORDER BY id DESC
        """,
        conn,
    )
    sub_df = pd.read_sql_query(
        """
        SELECT bill_id, document_no, bill_date, bill_month, subcontractor_name,
               COALESCE(bill_type, 'Combined') AS bill_type,
               labour_amount, ot_amount, boq_amount, advance_amount, net_amount, status
        FROM subcontractor_bills ORDER BY id DESC
        """,
        conn,
    )
    conn.close()

    st.markdown("#### Client Bills")
    st.dataframe(client_df.drop(columns=["bill_id"], errors="ignore"), width="stretch", hide_index=True)
    if not client_df.empty:
        from modules.client_portal_db import submit_bill_for_client_review

        submit_pick = st.selectbox(
            "Submit to client for review",
            [""] + client_df["bill_no"].tolist(),
            key="reg_client_submit_review",
        )
        if submit_pick and st.button("Send to Client Portal", key="reg_client_submit_btn"):
            bill_id = client_df[client_df["bill_no"] == submit_pick].iloc[0]["bill_id"]
            ok, err = submit_bill_for_client_review(
                bill_id, actor=st.session_state.get("user_name", "User")
            )
            if ok:
                st.success(f"Bill {submit_pick} sent for client review.")
                st.rerun()
            else:
                st.error(err)
        cb_pick = st.selectbox("Print client bill", [""] + client_df["bill_no"].tolist(), key="reg_client_bill")
        if cb_pick:
            row = client_df[client_df["bill_no"] == cb_pick].iloc[0]
            bill_id = row["bill_id"]
            conn = get_conn()
            lines = pd.read_sql_query(
                "SELECT boq_number, description, unit, quantity, rate, amount FROM client_bill_lines WHERE bill_id = ?",
                conn,
                params=(bill_id,),
            )
            conn.close()
            line_rows = [
                {
                    "BOQ No": r["boq_number"],
                    "Description": r["description"],
                    "Unit": r["unit"],
                    "Qty": f"{r['quantity']:,.2f}",
                    "Rate": f"{r['rate']:,.2f}",
                    "Amount": f"Rs {r['amount']:,.2f}",
                }
                for _, r in lines.iterrows()
            ]
            html = _bill_html(
                "CLIENT BILL / INVOICE",
                [
                    ("Bill No", row["bill_no"]),
                    ("Bill Date", row["bill_date"]),
                    ("Client", row["client_name"]),
                    ("Project", row["project_name"]),
                ],
                line_rows,
                [("Total Amount", f"Rs {row['total_amount']:,.2f}")],
            )
            try:
                pdf = generate_client_invoice_pdf(bill_id)
            except Exception:
                pdf = None
            _render_print_download(
                html,
                f"{row['bill_no']}.html",
                pdf_bytes=pdf,
                pdf_filename=f"{row['bill_no']}.pdf",
            )

    st.markdown("#### Sub Contractor Bills")
    st.dataframe(sub_df, width="stretch", hide_index=True)
    if not sub_df.empty:
        sb_pick = st.selectbox("Print sub contractor bill", [""] + sub_df["bill_id"].tolist(), key="reg_sub_bill")
        if sb_pick:
            row = sub_df[sub_df["bill_id"] == sb_pick].iloc[0]
            bt = row["bill_type"]
            totals = [("Advance Deduction", f"Rs {row['advance_amount']:,.2f}"), ("Net Payable", f"Rs {row['net_amount']:,.2f}")]
            if bt == "Quantity":
                totals = [
                    ("BOQ / Measurement Amount", f"Rs {row['boq_amount']:,.2f}"),
                    *totals,
                ]
            elif bt == "Manpower":
                totals = [
                    ("Labour Amount", f"Rs {row['labour_amount']:,.2f}"),
                    ("OT Amount", f"Rs {row.get('ot_amount', 0):,.2f}"),
                    *totals,
                ]
            else:
                totals = [
                    ("Labour Amount", f"Rs {row['labour_amount']:,.2f}"),
                    ("OT Amount", f"Rs {row.get('ot_amount', 0):,.2f}"),
                    ("BOQ / Quantity Amount", f"Rs {row['boq_amount']:,.2f}"),
                    *totals,
                ]
            mode_title = "Measurement Based" if bt == "Quantity" else ("Payroll Based" if bt == "Manpower" else bt)
            html = _bill_html(
                f"SUB CONTRACTOR BILL — {mode_title}",
                [
                    ("Bill No", row.get("document_no") or row["bill_id"]),
                    ("Bill Date", row["bill_date"]),
                    ("Bill Month", row["bill_month"]),
                    ("Sub Contractor", row["subcontractor_name"]),
                    ("Billing Mode", mode_title),
                    ("Status", row.get("status", "")),
                ],
                [],
                totals,
            )
            try:
                pdf = generate_subcontractor_bill_pdf(sb_pick)
            except Exception:
                pdf = None
            doc_name = row.get("document_no") or sb_pick
            _render_print_download(
                html,
                f"{doc_name}.html",
                pdf_bytes=pdf,
                pdf_filename=f"{doc_name}.pdf",
            )

    st.markdown("#### Subcontractor bill workflow")
    if not sub_df.empty:
        wf_options = {
            f"{r.get('document_no') or r['bill_id']} | {r['subcontractor_name']} | {r.get('status', '')}": r["bill_id"]
            for r in sub_df.to_dict("records")
        }
        wf_pick = st.selectbox("Select bill for approval", [""] + list(wf_options.keys()), key="sub_bill_wf")
        if wf_pick:
            from modules.approval_workflow import normalize_status
            from modules.workflow_ui import render_workflow_action_panel, render_workflow_status_steps

            bill_id = wf_options[wf_pick]
            sub_row = sub_df[sub_df["bill_id"] == bill_id].iloc[0]
            status = normalize_status(sub_row.get("status"), "subcontractor_bill")
            render_workflow_status_steps(status)
            if render_workflow_action_panel("subcontractor_bill", bill_id, status, key_prefix="sbl"):
                st.rerun()

    st.markdown("#### Client bill workflow")
    if not client_df.empty:
        cb_wf = {
            f"{r['bill_no']} | {r['client_name']} | {r.get('status', '')}": r["bill_id"]
            for r in client_df.to_dict("records")
        }
        cb_pick_wf = st.selectbox("Select client bill for approval", [""] + list(cb_wf.keys()), key="client_bill_wf")
        if cb_pick_wf:
            from modules.approval_workflow import normalize_status
            from modules.workflow_ui import render_workflow_action_panel, render_workflow_status_steps

            bill_id = cb_wf[cb_pick_wf]
            cb_row = client_df[client_df["bill_id"] == bill_id].iloc[0]
            status = normalize_status(cb_row.get("status"), "client_bill")
            render_workflow_status_steps(status)
            if render_workflow_action_panel("client_bill", bill_id, status, key_prefix="cbl"):
                st.rerun()


def page_billing():
    st.subheader("Billing")
    tabs = st.tabs(
        [
            "Client Bill",
            "Subcontractor Billing",
            "Sub — Combined (legacy)",
            "Register & Print",
        ]
    )
    with tabs[0]:
        _render_client_bill_tab()
    with tabs[1]:
        _render_subcontractor_billing_tab()
    with tabs[2]:
        _render_sub_bill_tab("Combined", subcontractor_bill_preview, "Sub Contractor Combined Bill (legacy)")
    with tabs[3]:
        _render_bill_register_tab()
