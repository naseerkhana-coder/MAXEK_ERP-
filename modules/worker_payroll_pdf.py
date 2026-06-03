"""PDF salary slip generation for worker payroll."""

from __future__ import annotations

import os
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from modules.branding import ERP_LEGAL_NAME
from modules.database import load_company_master
from modules.worker_payroll_db import get_payroll_run, list_deductions

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generate_worker_salary_slip_pdf(run_id: str) -> bytes:
    run = get_payroll_run(run_id)
    if not run:
        raise ValueError("Payroll run not found.")

    company = load_company_master()
    company_name = (company.get("company_name") or ERP_LEGAL_NAME).strip()
    company_addr = (company.get("address") or company.get("registered_address") or "").strip()
    deductions = list_deductions(run_id)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=16, spaceAfter=8)
    sub_style = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=10, textColor=colors.grey)

    story = [
        Paragraph(company_name, title_style),
    ]
    if company_addr:
        story.append(Paragraph(company_addr.replace("\n", "<br/>"), sub_style))
    story.extend([
        Paragraph("Worker Salary Slip", styles["Heading2"]),
        Spacer(1, 0.3 * cm),
    ])

    meta = [
        ["Worker Name", run.get("worker_name") or "—"],
        ["Worker ID", run.get("worker_id") or "—"],
        ["Category", run.get("hour_category") or "—"],
        ["Salary Period", f"{run.get('period_start')} to {run.get('period_end')}"],
        ["Cycle", run.get("cycle_type") or "—"],
        ["Payment Status", run.get("workflow_status") or "—"],
        ["Payment Date", run.get("payment_date") or "—"],
        ["Payment Mode", run.get("payment_mode") or "—"],
        ["Reference", run.get("payment_reference") or "—"],
    ]
    meta_table = Table(meta, colWidths=[5 * cm, 11 * cm])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 0.4 * cm))

    hours = [
        ["Worked Days", str(int(run.get("worked_days") or 0))],
        ["Worked Hours", f"{float(run.get('worked_hours') or 0):,.2f}"],
        ["OT Hours", f"{float(run.get('ot_hours') or 0):,.2f}"],
    ]
    h_table = Table(hours, colWidths=[5 * cm, 11 * cm])
    h_table.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story.append(h_table)
    story.append(Spacer(1, 0.3 * cm))

    gross = float(run.get("gross_salary") or 0)
    ot_amt = float(run.get("ot_amount") or 0)
    base = round(gross - ot_amt, 2)
    pay_rows = [
        ["Gross Salary (base)", f"Rs {base:,.2f}"],
        ["Overtime", f"Rs {ot_amt:,.2f}"],
        ["Gross Total", f"Rs {gross:,.2f}"],
    ]
    for d in deductions:
        pay_rows.append(
            [
                f"Less: {d.get('deduction_type')}",
                f"Rs {float(d.get('amount') or 0):,.2f}",
            ]
        )
    if not deductions:
        pay_rows.append(["Less: Deductions", f"Rs {float(run.get('total_deductions') or 0):,.2f}"])
    pay_rows.append(["Net Payable", f"Rs {float(run.get('net_salary') or 0):,.2f}"])

    pay_table = Table(pay_rows, colWidths=[8 * cm, 8 * cm])
    pay_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eff6ff")),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#2563eb")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(pay_table)
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph("Authorized Signature: _________________________", sub_style))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph("This is a system-generated salary slip.", sub_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
