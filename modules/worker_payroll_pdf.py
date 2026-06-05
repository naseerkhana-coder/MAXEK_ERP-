"""PDF salary slip generation for worker payroll (delegates to document_pdfs)."""

from modules.document_pdfs import generate_worker_salary_slip_pdf

__all__ = ["generate_worker_salary_slip_pdf"]
