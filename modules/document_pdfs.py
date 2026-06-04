"""
MAXEK ERP — PDF document generators (unified layout via pdf_templates).

| Function | Document |
|----------|----------|
| generate_worker_salary_slip_pdf | Worker salary slip (8hr/10hr) |
| generate_staff_payslip_pdf | Staff / monthly / daily wage payslip |
| generate_client_invoice_pdf | Client bill / sales invoice |
| generate_subcontractor_bill_pdf | Sub-contractor bill |
| generate_purchase_invoice_pdf | Purchase / expense invoice |
| generate_payment_voucher_pdf | Supplier payment voucher |
"""

from __future__ import annotations

import pandas as pd
from reportlab.lib.units import cm

from modules.database import (
    get_conn,
    subcontractor_bill_boq_lines,
    subcontractor_bill_payroll_lines,
)
from modules.pdf_templates import PdfDocument, format_inr
from modules.worker_payroll_db import get_payroll_run, list_deductions


def get_payroll_by_id(payroll_id: str) -> dict | None:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM payroll WHERE payroll_id = ?", conn, params=(payroll_id,))
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else None


def _load_client_bill(bill_id: str) -> tuple[dict | None, pd.DataFrame]:
    conn = get_conn()
    hdr = pd.read_sql_query("SELECT * FROM client_bills WHERE bill_id = ?", conn, params=(bill_id,))
    lines = pd.read_sql_query(
        """
        SELECT boq_number, description, unit, quantity, rate, amount
        FROM client_bill_lines WHERE bill_id = ?
        """,
        conn,
        params=(bill_id,),
    )
    conn.close()
    if hdr.empty:
        return None, lines
    return hdr.iloc[0].to_dict(), lines


def _load_subcontractor_bill(bill_id: str) -> dict | None:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM subcontractor_bills WHERE bill_id = ?", conn, params=(bill_id,))
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else None


def _load_expense_invoice(invoice_id: str) -> tuple[dict | None, pd.DataFrame]:
    conn = get_conn()
    hdr = pd.read_sql_query("SELECT * FROM expense_invoices WHERE invoice_id = ?", conn, params=(invoice_id,))
    lines = pd.read_sql_query(
        """
        SELECT item_name, hsn_code, unit, quantity, rate, amount
        FROM expense_invoice_lines WHERE invoice_id = ?
        """,
        conn,
        params=(invoice_id,),
    )
    conn.close()
    if hdr.empty:
        return None, lines
    return hdr.iloc[0].to_dict(), lines


def _load_payment_voucher(voucher_id: str) -> dict | None:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM payment_vouchers WHERE voucher_id = ?", conn, params=(voucher_id,))
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else None


def generate_worker_salary_slip_pdf(run_id: str) -> bytes:
    run = get_payroll_run(run_id)
    if not run:
        raise ValueError("Payroll run not found.")

    deductions = list_deductions(run_id)
    doc = PdfDocument()
    doc.add_company_block(
        "Worker Salary Slip",
        ref_label="Run ID",
        ref_value=run_id,
        date_label="Payment Date",
        date_value=run.get("payment_date") or "",
    )

    doc.add_key_value_table(
        [
            ("Worker Name", run.get("worker_name") or "—"),
            ("Worker ID", run.get("worker_id") or "—"),
            ("Category", run.get("hour_category") or "—"),
            ("Salary Period", f"{run.get('period_start')} to {run.get('period_end')}"),
            ("Cycle", run.get("cycle_type") or "—"),
            ("Payment Status", run.get("workflow_status") or "—"),
            ("Payment Mode", run.get("payment_mode") or "—"),
            ("Reference", run.get("payment_reference") or "—"),
        ]
    )
    doc.add_spacer(0.2)
    doc.add_section("Attendance")
    doc.add_key_value_table(
        [
            ("Worked Days", str(int(run.get("worked_days") or 0))),
            ("Worked Hours", f"{float(run.get('worked_hours') or 0):,.2f}"),
            ("OT Hours", f"{float(run.get('ot_hours') or 0):,.2f}"),
        ]
    )
    doc.add_spacer(0.2)
    doc.add_section("Pay Summary")

    gross = float(run.get("gross_salary") or 0)
    ot_amt = float(run.get("ot_amount") or 0)
    base = round(gross - ot_amt, 2)
    totals = [
        ("Gross Salary (base)", format_inr(base)),
        ("Overtime", format_inr(ot_amt)),
        ("Gross Total", format_inr(gross)),
    ]
    if deductions:
        for d in deductions:
            totals.append((f"Less: {d.get('deduction_type')}", format_inr(d.get("amount"))))
    else:
        totals.append(("Less: Deductions", format_inr(run.get("total_deductions"))))
    totals.append(("Net Payable", format_inr(run.get("net_salary"))))
    doc.add_totals_table(totals)
    doc.add_footer("This is a system-generated worker salary slip.")
    return doc.build()


def generate_staff_payslip_pdf(payroll_id: str) -> bytes:
    row = get_payroll_by_id(payroll_id)
    if not row:
        raise ValueError("Payroll record not found.")

    conn = get_conn()
    emp = pd.read_sql_query(
        "SELECT employee_type, designation, department FROM employees WHERE employee_id = ?",
        conn,
        params=(row.get("employee_id"),),
    )
    conn.close()
    emp_type = ""
    designation = ""
    if not emp.empty:
        emp_type = str(emp.iloc[0].get("employee_type") or "")
        designation = str(emp.iloc[0].get("designation") or "")

    period = row.get("payroll_month") or "—"
    ps = row.get("payroll_period_start") or ""
    pe = row.get("payroll_period_end") or ""
    if ps and pe:
        period = f"{period} ({ps} – {pe})"

    doc = PdfDocument()
    doc.add_company_block(
        "Staff Payslip",
        ref_label="Payroll ID",
        ref_value=payroll_id,
        date_label="Pay Period",
        date_value=period,
    )
    doc.add_key_value_table(
        [
            ("Employee Name", row.get("employee_name") or "—"),
            ("Employee ID", row.get("employee_id") or "—"),
            ("Employee Type", emp_type or "—"),
            ("Designation", designation or "—"),
            ("Workflow Status", row.get("workflow_status") or row.get("salary_status") or "—"),
            ("Payment Status", row.get("payment_status") or "—"),
            ("Payment Mode", row.get("payment_mode") or "—"),
            ("Paid Date", row.get("paid_date") or "—"),
        ]
    )
    doc.add_spacer(0.2)
    doc.add_section("Attendance Summary")
    doc.add_key_value_table(
        [
            ("Worked Days", str(int(row.get("worked_days") or 0))),
            ("Paid Weekly Off Days", str(int(row.get("paid_weekly_off_days") or 0))),
            ("Paid Holiday Days", str(int(row.get("paid_holiday_days") or 0))),
            ("Total OT Hours", f"{float(row.get('total_ot_hours') or 0):,.2f}"),
        ]
    )
    doc.add_spacer(0.2)
    doc.add_section("Pay Summary")
    base = float(row.get("normal_salary_amount") or row.get("base_salary") or 0)
    wo = float(row.get("weekly_off_paid_amount") or 0)
    hol = float(row.get("holiday_paid_amount") or 0)
    ot = float(row.get("ot_amount") or 0)
    ded = float(row.get("deductions") or 0)
    net = float(row.get("net_salary") or 0)
    doc.add_totals_table(
        [
            ("Basic / Normal Salary", format_inr(base)),
            ("Weekly Off (paid)", format_inr(wo)),
            ("Holiday (paid)", format_inr(hol)),
            ("Overtime", format_inr(ot)),
            ("Gross Earnings", format_inr(base + wo + hol + ot)),
            ("Less: Deductions", format_inr(ded)),
            ("Net Payable", format_inr(net)),
        ]
    )
    doc.add_footer("This is a system-generated staff payslip.")
    return doc.build()


def generate_client_invoice_pdf(bill_id: str) -> bytes:
    header, lines = _load_client_bill(bill_id)
    if not header:
        raise ValueError("Client bill not found.")

    doc = PdfDocument()
    doc.add_company_block(
        "Tax Invoice / Client Bill",
        ref_label="Invoice No",
        ref_value=header.get("bill_no") or bill_id,
        date_value=header.get("bill_date") or "",
    )
    doc.add_key_value_table(
        [
            ("Client", header.get("client_name") or "—"),
            ("Project", header.get("project_name") or "—"),
            ("Status", header.get("status") or "—"),
            ("Remarks", header.get("remarks") or "—"),
        ]
    )
    doc.add_spacer(0.2)
    doc.add_section("Line Items")
    table_rows = []
    for _, r in lines.iterrows():
        table_rows.append(
            [
                str(r.get("boq_number") or ""),
                str(r.get("description") or "")[:40],
                str(r.get("unit") or ""),
                f"{float(r.get('quantity') or 0):,.2f}",
                format_inr(r.get("rate")),
                format_inr(r.get("amount")),
            ]
        )
    doc.add_data_table(
        ["BOQ No", "Description", "Unit", "Qty", "Rate", "Amount"],
        table_rows,
        col_widths=[2.2 * cm, 4.5 * cm, 1.2 * cm, 1.5 * cm, 2.2 * cm, 2.4 * cm],
    )

    taxable = float(header.get("total_amount") or 0)
    gst_pct = float(header.get("gst_percent") or 0)
    gst_amt = float(header.get("gst_amount") or 0)
    grand = float(header.get("grand_total") or 0) or (taxable + gst_amt)
    totals = [("Taxable Amount", format_inr(taxable))]
    if gst_pct or gst_amt:
        totals.append((f"GST ({gst_pct:g}%)", format_inr(gst_amt)))
    totals.append(("Grand Total", format_inr(grand)))
    doc.add_spacer(0.2)
    doc.add_section("Totals")
    doc.add_totals_table(totals)
    doc.add_footer("This is a system-generated client invoice.")
    return doc.build()


def generate_subcontractor_bill_pdf(bill_id: str) -> bytes:
    row = _load_subcontractor_bill(bill_id)
    if not row:
        raise ValueError("Sub-contractor bill not found.")

    doc_no = row.get("document_no") or bill_id
    bill_type = row.get("bill_type") or "Combined"
    mode_title = (
        "Measurement Based (BOQ)"
        if bill_type == "Quantity"
        else ("Payroll Based (Attendance)" if bill_type == "Manpower" else bill_type)
    )
    doc = PdfDocument()
    doc.add_company_block(
        f"Sub-Contractor Bill — {mode_title}",
        ref_label="Bill No",
        ref_value=doc_no,
        date_value=row.get("bill_date") or "",
    )
    doc.add_key_value_table(
        [
            ("Sub-Contractor", row.get("subcontractor_name") or "—"),
            ("Bill Month", row.get("bill_month") or "—"),
            ("Billing Mode", mode_title),
            ("Status", row.get("status") or "—"),
            ("Remarks", row.get("remarks") or "—"),
        ]
    )
    sub_name = row.get("subcontractor_name") or ""
    bill_month = row.get("bill_month") or ""
    show_payroll = bill_type in ("Manpower", "Combined")
    show_measurement = bill_type in ("Quantity", "Combined")

    if show_payroll:
        payroll_lines = subcontractor_bill_payroll_lines(sub_name, bill_month)
        if not payroll_lines.empty:
            doc.add_spacer(0.3)
            doc.add_section("Payroll Summary — by Designation")
            table_rows = []
            for _, pl in payroll_lines.iterrows():
                table_rows.append(
                    [
                        str(pl.get("designation") or "")[:22],
                        str(int(pl.get("worked_days") or 0)),
                        f"{float(pl.get('worked_hours') or 0):,.2f}",
                        f"{float(pl.get('ot_hours') or 0):,.2f}",
                        format_inr(pl.get("labour_amount")),
                        format_inr(pl.get("ot_amount")),
                        format_inr(pl.get("line_total")),
                    ]
                )
            doc.add_data_table(
                ["Designation", "Days", "Worked Hrs", "OT Hrs", "Labour", "OT Amt", "Total"],
                table_rows,
                col_widths=[3.2 * cm, 1.1 * cm, 1.6 * cm, 1.4 * cm, 2.2 * cm, 2.2 * cm, 2.3 * cm],
            )

    if show_measurement:
        boq_lines = subcontractor_bill_boq_lines(sub_name, bill_month)
        if not boq_lines.empty:
            doc.add_spacer(0.3)
            doc.add_section("Measurement Based — BOQ Lines")
            table_rows = []
            for _, bl in boq_lines.iterrows():
                table_rows.append(
                    [
                        str(bl.get("project_name") or "")[:14],
                        str(bl.get("boq_item") or "")[:18],
                        str(bl.get("unit") or ""),
                        f"{float(bl.get('quantity') or 0):,.2f}",
                        format_inr(bl.get("rate")),
                        format_inr(bl.get("amount")),
                    ]
                )
            doc.add_data_table(
                ["Project", "BOQ Item", "Unit", "Qty", "Rate", "Amount"],
                table_rows,
                col_widths=[2.4 * cm, 3.2 * cm, 1.2 * cm, 1.5 * cm, 2.3 * cm, 2.4 * cm],
            )

    doc.add_spacer(0.3)
    doc.add_section("Bill Summary")
    labour = float(row.get("labour_amount") or 0)
    ot = float(row.get("ot_amount") or 0)
    boq = float(row.get("boq_amount") or 0)
    advance = float(row.get("advance_amount") or 0)
    total = float(row.get("total_amount") or 0) or (labour + ot + boq)
    net = float(row.get("net_amount") or 0)
    summary_rows = []
    if show_payroll:
        summary_rows.extend(
            [
                ("Labour Amount", format_inr(labour)),
                ("OT Amount", format_inr(ot)),
            ]
        )
    if show_measurement:
        summary_rows.append(("BOQ / Quantity Amount", format_inr(boq)))
    if not summary_rows:
        summary_rows = [
            ("Labour Amount", format_inr(labour)),
            ("OT Amount", format_inr(ot)),
            ("BOQ / Quantity Amount", format_inr(boq)),
        ]
    summary_rows.extend(
        [
            ("Gross Bill Total", format_inr(total)),
            ("Less: Advance Deduction", format_inr(advance)),
            ("Net Payable", format_inr(net)),
        ]
    )
    doc.add_totals_table(summary_rows)
    doc.add_footer("This is a system-generated sub-contractor bill.")
    return doc.build()


def generate_purchase_invoice_pdf(invoice_id: str) -> bytes:
    header, lines = _load_expense_invoice(invoice_id)
    if not header:
        raise ValueError("Purchase invoice not found.")

    doc_no = header.get("document_no") or invoice_id
    doc = PdfDocument()
    doc.add_company_block(
        "Purchase Invoice",
        ref_label="Document No",
        ref_value=doc_no,
        date_value=header.get("expense_date") or "",
    )
    doc.add_key_value_table(
        [
            ("Supplier", header.get("supplier") or "—"),
            ("Supplier Invoice No", header.get("invoice_no") or "—"),
            ("Project", header.get("project_name") or "—"),
            ("Expense Type", header.get("exp_type") or "—"),
            ("Tax Type", header.get("tax_type") or "—"),
            ("Payment Status", header.get("payment_status") or "—"),
        ]
    )
    if not lines.empty:
        doc.add_spacer(0.2)
        doc.add_section("Line Items")
        table_rows = []
        for _, r in lines.iterrows():
            table_rows.append(
                [
                    str(r.get("item_name") or "")[:30],
                    str(r.get("hsn_code") or ""),
                    str(r.get("unit") or ""),
                    f"{float(r.get('quantity') or 0):,.2f}",
                    format_inr(r.get("rate")),
                    format_inr(r.get("amount")),
                ]
            )
        doc.add_data_table(
            ["Item", "HSN", "Unit", "Qty", "Rate", "Amount"],
            table_rows,
            col_widths=[3.5 * cm, 1.5 * cm, 1.2 * cm, 1.3 * cm, 2.2 * cm, 2.3 * cm],
        )

    taxable = float(header.get("taxable_amount") or 0)
    tax = float(header.get("total_tax") or 0)
    total = float(header.get("total_invoice_value") or 0)
    doc.add_spacer(0.2)
    doc.add_section("Totals")
    doc.add_totals_table(
        [
            ("Taxable Amount", format_inr(taxable)),
            ("Total Tax (GST)", format_inr(tax)),
            ("Invoice Total", format_inr(total)),
        ]
    )
    doc.add_footer("This is a system-generated purchase invoice.")
    return doc.build()


def generate_payment_voucher_pdf(voucher_id: str) -> bytes:
    row = _load_payment_voucher(voucher_id)
    if not row:
        raise ValueError("Payment voucher not found.")

    payee = row.get("payee_name") or row.get("supplier") or "—"
    approval_lines = []
    for step, by_key, dt_key in (
        ("Prepared", "prepared_by", "prepared_date"),
        ("Checked", "checked_by", "checked_date"),
        ("Approved", "approved_by", "approved_date"),
        ("Payment Released", "payment_released_by", "payment_released_date"),
        ("Paid", "paid_by", "paid_date"),
    ):
        by_val = row.get(by_key) or ""
        dt_val = row.get(dt_key) or ""
        if by_val or dt_val:
            approval_lines.append((step, f"{by_val or '—'} ({dt_val or '—'})"))

    doc = PdfDocument()
    doc.add_company_block(
        "Payment Voucher",
        ref_label="Voucher No",
        ref_value=row.get("voucher_no") or voucher_id,
        date_value=row.get("payment_date") or row.get("voucher_date") or "",
    )
    doc.add_key_value_table(
        [
            ("Payment Type", row.get("payment_type") or "—"),
            ("Payee", payee),
            ("Project", row.get("project_name") or "—"),
            ("Payment Mode", row.get("payment_mode") or "—"),
            ("Reference No", row.get("reference_no") or "—"),
            ("Status", row.get("status") or "—"),
            ("Remarks", row.get("remarks") or "—"),
        ]
    )
    if approval_lines:
        doc.add_spacer(0.2)
        doc.add_section("Approval chain")
        doc.add_key_value_table(approval_lines)
    doc.add_spacer(0.3)
    doc.add_section("Payment")
    doc.add_totals_table([("Amount Paid", format_inr(row.get("amount")))], highlight_last=True)
    doc.add_footer("This is a system-generated payment voucher.")
    return doc.build()


def generate_project_progress_pdf(project_id: str, project_name: str) -> bytes:
    """Progress summary PDF for client portal (DPR aggregates)."""
    from modules.client_portal_db import compute_project_progress_percent
    from modules.database import get_conn
    from modules.pdf_templates import PdfDocument

    conn = get_conn()
    dprs = conn.execute(
        """
        SELECT dpr_date, progress_quantity, done_quantity, total_boq_quantity, status, remarks
        FROM dpr_reports
        WHERE project_id = ? OR project_name = ?
        ORDER BY dpr_date DESC
        LIMIT 50
        """,
        (project_id, project_name),
    ).fetchall()
    conn.close()

    pct = compute_project_progress_percent(project_id, project_name)
    doc = PdfDocument()
    doc.add_company_block("Project Progress Report", ref_label="Project", ref_value=project_name)
    doc.add_key_value_table(
        [
            ("Project", project_name),
            ("Completion (est.)", f"{pct:g}%"),
            ("DPR entries", str(len(dprs))),
        ]
    )
    if dprs:
        doc.add_spacer(0.2)
        doc.add_section("Recent progress entries")
        rows = []
        for d in dprs:
            rows.append(
                [
                    d[0] or "—",
                    f"{float(d[1] or d[2] or 0):,.2f}",
                    f"{float(d[3] or 0):,.2f}",
                    d[4] or "—",
                ]
            )
        doc.add_table(["Date", "Progress Qty", "BOQ Qty", "Status"], rows)
    doc.add_footer("This is a system-generated project progress report.")
    return doc.build()


def generate_measurement_book_pdf(
    project_name: str,
    summary_df=None,
    detail_df=None,
    date_from: str = "",
    date_to: str = "",
) -> bytes:
    """Measurement book / sheet PDF from DPR cumulative register."""
    from modules.pdf_templates import PdfDocument

    doc = PdfDocument()
    period = "All dates"
    if date_from and date_to:
        period = f"{date_from} to {date_to}"
    elif date_from:
        period = f"From {date_from}"
    elif date_to:
        period = f"Up to {date_to}"
    doc.add_company_block("Measurement Book", ref_label="Project", ref_value=project_name)
    doc.add_key_value_table([("Period", period)])
    if summary_df is not None and not summary_df.empty:
        doc.add_spacer(0.2)
        doc.add_section("Cumulative quantities by BOQ")
        rows = []
        for _, r in summary_df.iterrows():
            rows.append(
                [
                    str(r.get("boq_number") or "—"),
                    str(r.get("boq_description") or "—")[:50],
                    str(r.get("unit") or "—"),
                    f"{float(r.get('cumulative_qty') or 0):,.4f}",
                    str(int(r.get("dpr_count") or 0)),
                ]
            )
        doc.add_table(["BOQ", "Description", "Unit", "Cumulative Qty", "DPR Days"], rows)
    if detail_df is not None and not detail_df.empty:
        doc.add_spacer(0.2)
        doc.add_section("Measurement lines")
        rows = []
        for _, r in detail_df.head(80).iterrows():
            rows.append(
                [
                    str(r.get("dpr_date") or "—"),
                    str(r.get("boq_number") or "—"),
                    str(r.get("measurement_method") or "—"),
                    f"{float(r.get('calculated_quantity') or 0):,.4f}",
                    str(r.get("unit") or "—"),
                ]
            )
        doc.add_table(["Date", "BOQ", "Method", "Qty", "Unit"], rows)
        if len(detail_df) > 80:
            doc.add_spacer(0.1)
            doc.add_section(f"… and {len(detail_df) - 80} more lines (see system register).")
    doc.add_footer("Generated from MAXEK ERP DPR measurements. Bill via Client Bill workflow.")
    return doc.build()


def generate_bbs_report_pdf(
    project_name: str,
    bbs_df=None,
    date_from: str = "",
    date_to: str = "",
) -> bytes:
    """Bar Bending Schedule PDF for a project / period."""
    from modules.dpr_measurements import bbs_shape_label
    from modules.pdf_templates import PdfDocument

    doc = PdfDocument()
    period = "All dates"
    if date_from and date_to:
        period = f"{date_from} to {date_to}"
    elif date_from:
        period = f"From {date_from}"
    elif date_to:
        period = f"Up to {date_to}"
    doc.add_company_block("Bar Bending Schedule (BBS)", ref_label="Project", ref_value=project_name)
    doc.add_key_value_table([("Period", period)])
    if bbs_df is not None and not bbs_df.empty:
        doc.add_spacer(0.2)
        doc.add_section("BBS rows")
        rows = []
        for _, r in bbs_df.iterrows():
            shape = bbs_shape_label(r.get("shape_code") or "STRAIGHT")
            rows.append(
                [
                    str(r.get("dpr_date") or "—"),
                    str(r.get("bar_mark") or "—"),
                    shape,
                    f"{float(r.get('diameter_mm') or 0):g}",
                    f"{float(r.get('nos') or 0):g}",
                    f"{float(r.get('length_m') or 0):,.3f}",
                    f"{float(r.get('weight_kg') or 0):,.2f}",
                    f"{float(r.get('weight_mt') or 0):,.4f}",
                ]
            )
        doc.add_table(
            ["Date", "Mark", "Shape", "Dia mm", "Nos", "Length m", "Weight kg", "Weight MT"],
            rows,
        )
        total_mt = float(bbs_df["weight_mt"].sum()) if "weight_mt" in bbs_df.columns else 0.0
        doc.add_spacer(0.15)
        doc.add_key_value_table([("Total steel (MT)", f"{total_mt:,.4f}")])
    else:
        doc.add_section("No BBS rows for this filter.")
    doc.add_footer("Generated from MAXEK ERP steel BBS entries on approved DPRs.")
    return doc.build()


def generate_material_planning_report_pdf(title: str, df: pd.DataFrame) -> bytes:
    """Tabular export for planned vs actual / variance reports."""
    doc = PdfDocument()
    doc.add_company_block(title)
    if df is None or df.empty:
        doc.add_section("No rows for this report.")
    else:
        cols = [str(c) for c in df.columns.tolist()]
        rows = [[str(v) for v in row] for row in df.values.tolist()]
        doc.add_data_table(cols, rows)
    doc.add_footer("Material Planning — planned (BOQ/DPR) vs actual (store issues).")
    return doc.build()
