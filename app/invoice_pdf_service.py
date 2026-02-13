"""
Professional GST-compliant Invoice PDF generator using ReportLab.
Generates on-demand — no file storage.
"""
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Invoice, Company, Payment


# ── Colors ───────────────────────────────────────────────────────────
BRAND_DARK = colors.HexColor("#1a1a2e")
BRAND_PRIMARY = colors.HexColor("#6366f1")
BRAND_LIGHT = colors.HexColor("#f1f5f9")
BORDER_COLOR = colors.HexColor("#cbd5e1")
TEXT_DARK = colors.HexColor("#0f172a")
TEXT_MUTED = colors.HexColor("#64748b")
GREEN = colors.HexColor("#16a34a")
RED = colors.HexColor("#dc2626")
AMBER = colors.HexColor("#d97706")


def generate_invoice_pdf(db: Session, invoice: Invoice) -> io.BytesIO:
    """
    Generate a professional GST-compliant invoice PDF.
    Returns a BytesIO buffer ready to stream.
    """
    company = db.query(Company).filter(Company.id == invoice.company_id).first()

    # Calculate payment totals
    total_paid = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.invoice_id == invoice.id,
        Payment.payment_type == "received",
    ).scalar() or 0.0

    total_refunded = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
        Payment.invoice_id == invoice.id,
        Payment.payment_type == "refund",
    ).scalar() or 0.0

    net_paid = total_paid - total_refunded
    outstanding = invoice.total - net_paid

    # ── Build PDF ────────────────────────────────────────────────────
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # Custom styles
    style_title = ParagraphStyle(
        "InvTitle", parent=styles["Heading1"],
        fontSize=22, textColor=BRAND_DARK, spaceAfter=2 * mm,
    )
    style_subtitle = ParagraphStyle(
        "InvSubtitle", parent=styles["Normal"],
        fontSize=9, textColor=TEXT_MUTED,
    )
    style_label = ParagraphStyle(
        "Label", parent=styles["Normal"],
        fontSize=8, textColor=TEXT_MUTED, spaceAfter=1 * mm,
    )
    style_value = ParagraphStyle(
        "Value", parent=styles["Normal"],
        fontSize=10, textColor=TEXT_DARK,
    )
    style_bold = ParagraphStyle(
        "Bold", parent=styles["Normal"],
        fontSize=10, textColor=TEXT_DARK, fontName="Helvetica-Bold",
    )
    style_right = ParagraphStyle(
        "Right", parent=styles["Normal"],
        fontSize=10, textColor=TEXT_DARK, alignment=TA_RIGHT,
    )
    style_right_bold = ParagraphStyle(
        "RightBold", parent=styles["Normal"],
        fontSize=10, textColor=TEXT_DARK, alignment=TA_RIGHT, fontName="Helvetica-Bold",
    )

    # ── Header: Company + Invoice Info ───────────────────────────────
    company_name = company.name if company else "Company"
    company_addr = company.address or ""
    company_phone = company.phone or ""
    company_gst = company.gst_number or ""

    inv_date = invoice.created_at.strftime("%d %b %Y") if invoice.created_at else ""

    # Status badge
    status_map = {
        "paid": ("PAID", GREEN),
        "partially_paid": ("PARTIALLY PAID", AMBER),
        "unpaid": ("UNPAID", RED),
        "cancelled": ("CANCELLED", TEXT_MUTED),
    }
    status_text, status_color = status_map.get(invoice.status, ("UNKNOWN", TEXT_MUTED))

    # Left: Company info
    left_info = []
    left_info.append(Paragraph(f"<b>{company_name}</b>", ParagraphStyle(
        "CompName", parent=styles["Normal"], fontSize=16, textColor=BRAND_DARK,
        fontName="Helvetica-Bold",
    )))
    if company_addr:
        left_info.append(Paragraph(company_addr, style_subtitle))
    if company_phone:
        left_info.append(Paragraph(f"Phone: {company_phone}", style_subtitle))
    if company_gst:
        left_info.append(Paragraph(f"<b>GSTIN:</b> {company_gst}", ParagraphStyle(
            "GST", parent=styles["Normal"], fontSize=9, textColor=BRAND_PRIMARY,
        )))

    # Right: Invoice details
    right_info = []
    right_info.append(Paragraph("TAX INVOICE", ParagraphStyle(
        "TaxInv", parent=styles["Normal"], fontSize=14, textColor=BRAND_PRIMARY,
        alignment=TA_RIGHT, fontName="Helvetica-Bold",
    )))
    right_info.append(Paragraph(f"<b>#{invoice.invoice_number}</b>", ParagraphStyle(
        "InvNum", parent=styles["Normal"], fontSize=11, textColor=TEXT_DARK,
        alignment=TA_RIGHT, fontName="Helvetica-Bold",
    )))
    right_info.append(Paragraph(f"Date: {inv_date}", ParagraphStyle(
        "InvDate", parent=styles["Normal"], fontSize=9, textColor=TEXT_MUTED,
        alignment=TA_RIGHT,
    )))
    right_info.append(Spacer(1, 3 * mm))
    right_info.append(Paragraph(f"<b>{status_text}</b>", ParagraphStyle(
        "Status", parent=styles["Normal"], fontSize=10, textColor=status_color,
        alignment=TA_RIGHT, fontName="Helvetica-Bold",
    )))

    # Combine into header table
    header_table = Table(
        [[left_info, right_info]],
        colWidths=[doc.width * 0.55, doc.width * 0.45],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 6 * mm))

    # ── Divider ──────────────────────────────────────────────────────
    elements.append(HRFlowable(
        width="100%", thickness=1, color=BORDER_COLOR, spaceAfter=6 * mm,
    ))

    # ── Bill To ──────────────────────────────────────────────────────
    elements.append(Paragraph("BILL TO", style_label))
    elements.append(Paragraph(f"<b>{invoice.customer_name}</b>", style_bold))
    if invoice.customer_email:
        elements.append(Paragraph(invoice.customer_email, style_subtitle))
    if invoice.customer_phone:
        elements.append(Paragraph(invoice.customer_phone, style_subtitle))
    elements.append(Spacer(1, 6 * mm))

    # ── Items Table ──────────────────────────────────────────────────
    gst_pct = invoice.tax_percent

    # Header row
    table_header = [
        Paragraph("<b>#</b>", ParagraphStyle("TH", fontSize=8, textColor=colors.white, fontName="Helvetica-Bold")),
        Paragraph("<b>Item</b>", ParagraphStyle("TH", fontSize=8, textColor=colors.white, fontName="Helvetica-Bold")),
        Paragraph("<b>Qty</b>", ParagraphStyle("TH", fontSize=8, textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
        Paragraph("<b>Rate</b>", ParagraphStyle("TH", fontSize=8, textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
        Paragraph(f"<b>GST ({gst_pct}%)</b>", ParagraphStyle("TH", fontSize=8, textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
        Paragraph("<b>Amount</b>", ParagraphStyle("TH", fontSize=8, textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
    ]

    table_data = [table_header]
    for idx, item in enumerate(invoice.items, 1):
        line_subtotal = item.unit_price * item.quantity
        line_gst = line_subtotal * (gst_pct / 100)
        line_total = line_subtotal + line_gst

        table_data.append([
            Paragraph(str(idx), ParagraphStyle("TD", fontSize=9, textColor=TEXT_DARK)),
            Paragraph(item.product_name, ParagraphStyle("TD", fontSize=9, textColor=TEXT_DARK)),
            Paragraph(str(item.quantity), ParagraphStyle("TD", fontSize=9, textColor=TEXT_DARK, alignment=TA_RIGHT)),
            Paragraph(f"₹{item.unit_price:,.2f}", ParagraphStyle("TD", fontSize=9, textColor=TEXT_DARK, alignment=TA_RIGHT)),
            Paragraph(f"₹{line_gst:,.2f}", ParagraphStyle("TD", fontSize=9, textColor=TEXT_DARK, alignment=TA_RIGHT)),
            Paragraph(f"₹{line_total:,.2f}", ParagraphStyle("TD", fontSize=9, textColor=TEXT_DARK, alignment=TA_RIGHT, fontName="Helvetica-Bold")),
        ])

    col_widths = [25, doc.width * 0.32, 45, 75, 75, 85]
    items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        # Body
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        # Zebra striping
        *[("BACKGROUND", (0, i), (-1, i), BRAND_LIGHT) for i in range(2, len(table_data), 2)],
        # Borders
        ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND_DARK),
        ("LINEBELOW", (0, -1), (-1, -1), 1, BORDER_COLOR),
        ("LINEAFTER", (0, 0), (-2, -1), 0.5, BORDER_COLOR),
        # Alignment
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 6 * mm))

    # ── Totals Section ───────────────────────────────────────────────
    def _total_row(label, value, bold=False, color=TEXT_DARK):
        s = style_right_bold if bold else style_right
        return [
            "", "", "",
            Paragraph(label, ParagraphStyle("TL", fontSize=9, textColor=TEXT_MUTED, alignment=TA_RIGHT)),
            Paragraph(f"₹{value:,.2f}", ParagraphStyle("TV", fontSize=10 if bold else 9, textColor=color,
                                                         alignment=TA_RIGHT, fontName="Helvetica-Bold" if bold else "Helvetica")),
        ]

    totals_data = [
        _total_row("Subtotal", invoice.subtotal),
        _total_row(f"GST ({gst_pct}%)", invoice.tax_amount),
    ]
    if invoice.discount > 0:
        totals_data.append(_total_row("Discount", invoice.discount))
    totals_data.append(_total_row("Grand Total", invoice.total, bold=True, color=BRAND_PRIMARY))

    elements.append(Spacer(1, 2 * mm))
    totals_data.append(_total_row("Total Paid", net_paid, color=GREEN))
    totals_data.append(_total_row("Outstanding", outstanding, bold=True, color=RED if outstanding > 0 else GREEN))

    totals_table = Table(
        totals_data,
        colWidths=[doc.width * 0.15, doc.width * 0.15, doc.width * 0.2, doc.width * 0.25, doc.width * 0.25],
    )
    totals_table.setStyle(TableStyle([
        ("LINEABOVE", (3, -3), (-1, -3), 1, BRAND_DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 10 * mm))

    # ── Notes ────────────────────────────────────────────────────────
    if invoice.notes:
        elements.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_COLOR, spaceAfter=3 * mm))
        elements.append(Paragraph("NOTES", style_label))
        elements.append(Paragraph(invoice.notes, style_subtitle))
        elements.append(Spacer(1, 6 * mm))

    # ── Footer ───────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_COLOR, spaceAfter=3 * mm))
    elements.append(Paragraph(
        "Thank you for your business!",
        ParagraphStyle("Footer", fontSize=9, textColor=TEXT_MUTED, alignment=TA_CENTER),
    ))
    elements.append(Paragraph(
        f"Generated on {datetime.now().strftime('%d %b %Y %H:%M')} • {company_name}",
        ParagraphStyle("FooterSm", fontSize=7, textColor=TEXT_MUTED, alignment=TA_CENTER, spaceBefore=2 * mm),
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer
