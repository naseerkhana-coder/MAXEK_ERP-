"""Smoke tests for unified PDF document generation."""

from modules.document_pdfs import (
    generate_client_invoice_pdf,
    generate_payment_voucher_pdf,
    generate_purchase_invoice_pdf,
    generate_staff_payslip_pdf,
    generate_subcontractor_bill_pdf,
    generate_worker_salary_slip_pdf,
)
from modules.pdf_templates import PdfDocument, format_inr, get_company_context


def test_format_inr():
    assert format_inr(1234.5) == "₹ 1,234.50"
    assert format_inr(0) == "₹ 0.00"


def test_company_context_has_name():
    ctx = get_company_context()
    assert ctx.get("company_name")


def test_minimal_pdf_document_builds():
    doc = PdfDocument()
    doc.add_company_block("Test Document", ref_label="Ref", ref_value="T-001", date_value="01/01/2026")
    doc.add_totals_table([("Net Payable", format_inr(100))])
    doc.add_footer("Test footer.")
    pdf = doc.build()
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"


def test_worker_salary_slip_raises_when_missing():
    try:
        generate_worker_salary_slip_pdf("__nonexistent_run__")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_staff_payslip_raises_when_missing():
    try:
        generate_staff_payslip_pdf("__nonexistent_payroll__")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_client_invoice_raises_when_missing():
    try:
        generate_client_invoice_pdf("__nonexistent_bill__")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_subcontractor_bill_raises_when_missing():
    try:
        generate_subcontractor_bill_pdf("__nonexistent_scb__")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_purchase_invoice_raises_when_missing():
    try:
        generate_purchase_invoice_pdf("__nonexistent_inv__")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_payment_voucher_raises_when_missing():
    try:
        generate_payment_voucher_pdf("__nonexistent_pv__")
        raised = False
    except ValueError:
        raised = True
    assert raised
