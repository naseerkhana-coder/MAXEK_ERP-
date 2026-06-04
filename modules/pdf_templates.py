"""Shared ReportLab PDF layout — company header, tables, totals, signature (MAXEK ERP)."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from modules.branding import ERP_LEGAL_NAME
from modules.database import load_company_master

PRIMARY = colors.HexColor("#1a365d")
ACCENT = colors.HexColor("#2563eb")
LIGHT_BG = colors.HexColor("#eff6ff")
HEADER_BG = colors.HexColor("#edf2f7")
MUTED = colors.grey


def format_inr(amount) -> str:
    """Indian Rupee display (₹ with thousands separator)."""
    return f"₹ {float(amount or 0):,.2f}"


def get_company_context() -> dict:
    company = load_company_master() or {}
    name = (company.get("company_name") or ERP_LEGAL_NAME).strip()
    address = (company.get("address") or "").strip()
    return {
        "company_name": name,
        "address": address,
        "gst_number": (company.get("gst_number") or "").strip(),
        "phone": (company.get("phone") or "").strip(),
        "email": (company.get("email") or "").strip(),
    }


class PdfDocument:
    """Build a single-page (or multi-flow) A4 PDF with consistent MAXEK styling."""

    def __init__(self, *, margins_cm: float = 1.5):
        self.buffer = BytesIO()
        m = margins_cm * cm
        self.doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            leftMargin=m,
            rightMargin=m,
            topMargin=m,
            bottomMargin=m,
        )
        self._styles = getSampleStyleSheet()
        self._title = ParagraphStyle(
            "DocTitle",
            parent=self._styles["Heading1"],
            fontSize=16,
            textColor=PRIMARY,
            spaceAfter=4,
        )
        self._company = ParagraphStyle(
            "CompanyName",
            parent=self._styles["Heading1"],
            fontSize=14,
            textColor=PRIMARY,
            spaceAfter=2,
        )
        self._sub = ParagraphStyle(
            "Sub",
            parent=self._styles["Normal"],
            fontSize=9,
            textColor=MUTED,
        )
        self._section = ParagraphStyle(
            "Section",
            parent=self._styles["Heading2"],
            fontSize=12,
            textColor=PRIMARY,
            spaceBefore=6,
            spaceAfter=6,
        )
        self.story: list = []

    def add_company_block(self, doc_title: str, *, ref_label: str = "", ref_value: str = "", date_label: str = "Date", date_value: str = ""):
        ctx = get_company_context()
        self.story.append(Paragraph(ctx["company_name"], self._company))
        if ctx["address"]:
            self.story.append(Paragraph(ctx["address"].replace("\n", "<br/>"), self._sub))
        contact = []
        if ctx["gst_number"]:
            contact.append(f"GSTIN: {ctx['gst_number']}")
        if ctx["phone"]:
            contact.append(f"Ph: {ctx['phone']}")
        if ctx["email"]:
            contact.append(ctx["email"])
        if contact:
            self.story.append(Paragraph(" · ".join(contact), self._sub))
        self.story.append(Spacer(1, 0.25 * cm))
        self.story.append(Paragraph(doc_title, self._title))
        if ref_value or date_value:
            meta = []
            if ref_label and ref_value:
                meta.append([ref_label, ref_value])
            if date_value:
                meta.append([date_label, date_value])
            self.add_key_value_table(meta, compact=True)
        self.story.append(Spacer(1, 0.2 * cm))

    def add_section(self, title: str) -> None:
        self.story.append(Paragraph(title, self._section))

    def add_key_value_table(self, rows: list[tuple[str, str]], *, compact: bool = False) -> None:
        if not rows:
            return
        data = [[k, v] for k, v in rows]
        table = Table(data, colWidths=[5 * cm, 11 * cm])
        pad = 4 if compact else 6
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9 if compact else 10),
                    ("TEXTCOLOR", (0, 0), (0, -1), PRIMARY),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        self.story.append(table)

    def add_data_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        *,
        col_widths: list[float] | None = None,
    ) -> None:
        if not headers:
            return
        data = [headers] + (rows or [])
        n = len(headers)
        if col_widths is None:
            total = 16.0
            col_widths = [total / n * cm] * n
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        self.story.append(table)

    def add_totals_table(
        self,
        rows: list[tuple[str, str]],
        *,
        highlight_last: bool = True,
        label_width_cm: float = 10.0,
    ) -> None:
        if not rows:
            return
        data = [[k, v] for k, v in rows]
        table = Table(data, colWidths=[label_width_cm * cm, 6 * cm])
        style_cmds = [
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
        if highlight_last and len(data) > 0:
            last = len(data) - 1
            style_cmds.extend(
                [
                    ("FONTNAME", (0, last), (-1, last), "Helvetica-Bold"),
                    ("BACKGROUND", (0, last), (-1, last), LIGHT_BG),
                    ("LINEABOVE", (0, last), (-1, last), 1, ACCENT),
                    ("TEXTCOLOR", (0, last), (-1, last), PRIMARY),
                ]
            )
        table.setStyle(TableStyle(style_cmds))
        self.story.append(table)

    def add_spacer(self, height_cm: float = 0.3) -> None:
        self.story.append(Spacer(1, height_cm * cm))

    def add_footer(self, note: str = "This is a system-generated document.") -> None:
        self.add_spacer(0.8)
        self.story.append(Paragraph("Authorized Signature: _________________________", self._sub))
        self.add_spacer(0.15)
        if note:
            self.story.append(Paragraph(note, self._sub))

    def build(self) -> bytes:
        self.doc.build(self.story)
        self.buffer.seek(0)
        return self.buffer.getvalue()
