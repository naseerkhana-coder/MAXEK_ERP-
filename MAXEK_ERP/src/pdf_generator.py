from datetime import datetime
from pathlib import Path

from reportlab.pdfgen import canvas

from .settings import PDF_REPORTS


def create_payslip_pdf(filename: str, data: dict) -> Path:
    path = PDF_REPORTS / filename
    c = canvas.Canvas(str(path))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(180, 800, "MAXEK PAYSLIP")
    c.setFont("Helvetica", 12)
    c.drawString(50, 760, f"Worker ID: {data['worker_id']}")
    c.drawString(50, 740, f"Worker Name: {data['worker_name']}")
    c.drawString(50, 720, f"Salary Rate: {data['salary_rate']:.2f}")
    c.drawString(50, 700, f"Overtime Rate: {data['overtime_rate']:.2f}")
    c.drawString(50, 680, f"Total Hours: {data['total_hours']:.2f}")
    c.drawString(50, 660, f"Overtime Hours: {data['overtime_hours']:.2f}")
    c.drawString(50, 640, f"Normal Pay: {data['normal_pay']:.2f}")
    c.drawString(50, 620, f"Overtime Pay: {data['overtime_pay']:.2f}")
    c.drawString(50, 600, f"Total Pay: {data['total_pay']:.2f}")
    c.drawString(50, 560, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.save()
    return path
