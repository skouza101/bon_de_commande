"""PDF Generation Engine for Tyre Invoices.

Compiles clean, simple A4 PDF invoices in French using ReportLab with
proper Arabic/RTL text support for client names. Falls back to
WeasyPrint or xhtml2pdf when available.
"""

import asyncio
import logging
import os
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import settings
from consolidator import ConsolidatedInvoice

logger = logging.getLogger(__name__)

# Locate template directory relative to this file
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Initialize Jinja2 environment
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

# Windows system fonts directory
FONTS_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def _has_arabic(text: str) -> bool:
    """Check if text contains any Arabic script characters."""
    for ch in text:
        if unicodedata.category(ch).startswith("L"):
            try:
                name = unicodedata.name(ch, "")
                if "ARABIC" in name:
                    return True
            except ValueError:
                pass
    return False


def _reshape_arabic(text: str) -> str:
    """Reshape and apply BiDi algorithm to Arabic text for correct PDF rendering."""
    if not _has_arabic(text):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except ImportError:
        logger.warning("arabic_reshaper or python-bidi not installed; Arabic text may render incorrectly.")
        return text


class PDFGenerator:
    """Renders consolidated invoice data to clean, simple A4 PDF documents."""

    def __init__(self, template_name: str = "invoice_template.html"):
        self.template_name = template_name
        self.template = jinja_env.get_template(self.template_name)

    def render_html(
        self,
        invoice: ConsolidatedInvoice,
        company_name: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> str:
        """Render HTML string from Jinja2 template with invoice context."""
        company = company_name or settings.company_name
        curr = currency or settings.currency

        logo_path = Path(__file__).parent / "static" / "img" / "logo.png"
        logo_base64 = ""
        if logo_path.exists():
            import base64
            logo_base64 = base64.b64encode(logo_path.read_bytes()).decode("utf-8")

        return self.template.render(
            invoice=invoice,
            company_name=company,
            company_address=settings.company_address,
            company_phone=settings.company_phone,
            company_email=settings.company_email,
            currency=curr,
            logo_base64=logo_base64,
        )

    def render_magaza_html(
        self,
        invoice: ConsolidatedInvoice,
        company_name: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> str:
        """Render HTML string from Magaza Jinja2 template with grouped items."""
        from collections import OrderedDict
        company = company_name or settings.company_name
        curr = currency or settings.currency

        logo_path = Path(__file__).parent / "static" / "img" / "pneus_logo.png"
        if not logo_path.exists():
            logo_path = Path(__file__).parent / "static" / "img" / "logo.png"
        logo_base64 = ""
        if logo_path.exists():
            import base64
            logo_base64 = base64.b64encode(logo_path.read_bytes()).decode("utf-8")

        grouped_items: Dict[str, List[Any]] = OrderedDict()
        for item in invoice.items:
            d = (getattr(item, "depot", None) or "magaza 1").strip()
            if d not in grouped_items:
                grouped_items[d] = []
            grouped_items[d].append(item)

        template = jinja_env.get_template("invoice_magaza_template.html")
        return template.render(
            invoice=invoice,
            grouped_items=grouped_items,
            company_name=company,
            company_address=settings.company_address,
            company_phone=settings.company_phone,
            company_email=settings.company_email,
            currency=curr,
            logo_base64=logo_base64,
        )

    def _compile_with_weasyprint(self, html_content: str, output_path: Path) -> bool:
        """Attempt to compile PDF using WeasyPrint (Linux / Docker)."""
        try:
            import weasyprint
            weasyprint.HTML(string=html_content).write_pdf(str(output_path))
            logger.info(f"Generated PDF with WeasyPrint: {output_path}")
            return True
        except (ImportError, OSError, Exception) as e:
            logger.warning(
                f"WeasyPrint unavailable ({e}). Using pure-Python PDF compiler."
            )
            return False

    def _compile_with_xhtml2pdf(self, html_content: str, output_path: Path) -> bool:
        """Attempt to compile PDF using xhtml2pdf."""
        try:
            from xhtml2pdf import pisa

            with open(output_path, "wb") as pdf_file:
                pisa_status = pisa.CreatePDF(
                    src=html_content,
                    dest=pdf_file,
                    encoding="utf-8",
                )
            if not pisa_status.err:
                logger.info(f"Generated PDF with xhtml2pdf: {output_path}")
                return True
            logger.warning(f"xhtml2pdf reported error: {pisa_status.err}")
            return False
        except Exception as e:
            logger.warning(f"xhtml2pdf compilation failed: {e}")
            return False

    def _register_fonts(self):
        """Register TrueType fonts that support Arabic glyphs for ReportLab."""
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # Use Arial (ships with Windows) — supports Arabic, Latin, and French
        font_map = {
            "Arial": "arial.ttf",
            "Arial-Bold": "arialbd.ttf",
            "Arial-Italic": "ariali.ttf",
            "Arial-BoldItalic": "arialbi.ttf",
        }
        for font_name, font_file in font_map.items():
            font_path = os.path.join(FONTS_DIR, font_file)
            if os.path.isfile(font_path):
                try:
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                except Exception:
                    pass  # Already registered or unavailable

    def _compile_with_reportlab(
        self, invoice: ConsolidatedInvoice, output_path: Path
    ) -> bool:
        """Compile a clean, minimalist A4 PDF invoice directly using ReportLab matching reference style."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate,
                Paragraph,
                Spacer,
                Table,
                TableStyle,
                HRFlowable,
                Image as RLImage,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

            self._register_fonts()

            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                rightMargin=45,
                leftMargin=45,
                topMargin=40,
                bottomMargin=40,
            )

            styles = getSampleStyleSheet()

            # --- Typography Styles ---
            s_company_line = ParagraphStyle(
                "CompanyLine", parent=styles["Normal"],
                fontName="Arial", fontSize=10, leading=14, textColor=colors.black
            )
            s_facture_title = ParagraphStyle(
                "FactureTitle", parent=styles["Normal"],
                fontName="Arial-Bold", fontSize=20, leading=24, textColor=colors.black, alignment=TA_RIGHT
            )
            s_section_hdr = ParagraphStyle(
                "SectionHdr", parent=styles["Normal"],
                fontName="Arial-Bold", fontSize=13, leading=17, textColor=colors.black
            )
            s_client_line = ParagraphStyle(
                "ClientLine", parent=styles["Normal"],
                fontName="Arial", fontSize=10.5, leading=15, textColor=colors.black
            )
            s_th = ParagraphStyle(
                "TH", parent=styles["Normal"],
                fontName="Arial-Bold", fontSize=9.5, leading=13, textColor=colors.black
            )
            s_td = ParagraphStyle(
                "TD", parent=styles["Normal"],
                fontName="Arial", fontSize=9.5, leading=13, textColor=colors.black
            )
            s_tot_lbl = ParagraphStyle(
                "TotLbl", parent=styles["Normal"],
                fontName="Arial-Bold", fontSize=10, leading=14, textColor=colors.black
            )
            s_tot_val = ParagraphStyle(
                "TotVal", parent=styles["Normal"],
                fontName="Arial-Bold", fontSize=10, leading=14, textColor=colors.black
            )

            story = []
            page_width = A4[0] - 90  # 45+45 margins

            # ============================================================
            # 1. HEADER BLOCK — Logo + Company details Left, Facture Right
            # ============================================================
            left_flowables = []

            # Logo
            logo_path = Path(__file__).parent / "static" / "img" / "pneus_logo.png"
            if not logo_path.exists():
                logo_path = Path(__file__).parent / "static" / "img" / "logo.png"
            if logo_path.exists():
                try:
                    left_flowables.append(RLImage(str(logo_path), width=44, height=44))
                    left_flowables.append(Spacer(1, 8))
                except Exception as img_err:
                    logger.warning(f"Could not embed logo in PDF: {img_err}")

            # Company details
            left_flowables.append(Paragraph(f"<b>Nom de la Société :</b> {settings.company_name}", s_company_line))
            left_flowables.append(Paragraph(f"<b>Adresse :</b> {settings.company_address}", s_company_line))
            left_flowables.append(Paragraph(f"<b>Téléphone :</b> {settings.company_phone}", s_company_line))
            left_flowables.append(Paragraph(f"<b>Email :</b> {settings.company_email}", s_company_line))

            right_flowables = [
                Paragraph("<b>Facture</b>", s_facture_title)
            ]

            hdr_table = Table([[left_flowables, right_flowables]], colWidths=[page_width * 0.65, page_width * 0.35])
            hdr_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (0, 0), "TOP"),
                ("VALIGN", (1, 0), (1, 0), "BOTTOM"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(hdr_table)

            # Solid black horizontal dividing line
            story.append(HRFlowable(width="100%", thickness=1.5, color=colors.black, spaceBefore=4, spaceAfter=20))

            # ============================================================
            # 2. CLIENT INFORMATION BLOCK
            # ============================================================
            story.append(Paragraph("<b>Les informations du client</b>", s_section_hdr))
            story.append(Spacer(1, 8))

            client_display = _reshape_arabic(invoice.client_name or "")
            client_address_display = _reshape_arabic(invoice.client_address or "")
            trans_date_display = invoice.transaction_date or invoice.date_str
            trans_status_display = invoice.transaction_status or "En attente"

            story.append(Paragraph(f"<b>Nom :</b> {client_display}", s_client_line))
            story.append(Paragraph(f"<b>Adresse :</b> {client_address_display}", s_client_line))
            story.append(Paragraph(f"<b>Date de la transaction :</b> {trans_date_display}", s_client_line))
            story.append(Paragraph(f"<b>Statut de la transaction :</b> {trans_status_display}", s_client_line))

            story.append(Spacer(1, 20))

            # ============================================================
            # 3. ARTICLES ACHETÉS TABLE
            # ============================================================
            story.append(Paragraph("<b>Articles achetés</b>", s_section_hdr))
            story.append(Spacer(1, 8))

            col_widths = [
                page_width * 0.26,   # Référence
                page_width * 0.26,   # Marque
                page_width * 0.12,   # Qte
                page_width * 0.18,   # Prix unitaire
                page_width * 0.18,   # Total
            ]

            header_row = [
                Paragraph("<b>Référence</b>", s_th),
                Paragraph("<b>Marque</b>", s_th),
                Paragraph("<b>Qte</b>", s_th),
                Paragraph(f"<b>Prix unitaire ({settings.currency})</b>", s_th),
                Paragraph(f"<b>Total ({settings.currency})</b>", s_th),
            ]
            table_data = [header_row]

            from consolidator import split_dimension_and_brand

            for item in invoice.items:
                raw_ref = item.reference or item.description
                brand_text = item.brand or ""
                dim, parsed_brand = split_dimension_and_brand(raw_ref)
                ref_text = dim or raw_ref
                final_brand = brand_text or parsed_brand or ""

                table_data.append([
                    Paragraph(ref_text, s_td),
                    Paragraph(final_brand, s_td),
                    Paragraph(str(item.quantity), s_td),
                    Paragraph(f"{item.unit_price:.2f}", s_td),
                    Paragraph(f"{item.subtotal:.2f}", s_td),
                ])

            # Total row (Montant total:)
            table_data.append([
                Paragraph("<b>Montant total:</b>", s_tot_lbl),
                "",
                "",
                "",
                Paragraph(f"<b>{invoice.grand_total:.2f}</b>", s_tot_val),
            ])

            items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
            items_table.setStyle(TableStyle([
                # Header row
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("TOPPADDING", (0, 0), (-1, 0), 7),
                # Data rows
                ("TOPPADDING", (0, 1), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                # Full grid border
                ("GRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#666666")),
                ("LINEBELOW", (0, 0), (-1, 0), 1.2, colors.black),
                # Total row span across first 4 columns
                ("SPAN", (0, -1), (3, -1)),
                ("LINEABOVE", (0, -1), (-1, -1), 1.2, colors.black),
            ]))
            story.append(items_table)

            doc.build(story)
            logger.info(f"Generated clean PDF with ReportLab: {output_path}")
            return True
        except Exception as e:
            logger.error(f"ReportLab compilation failed: {e}", exc_info=True)
            return False

    def generate_pdf_sync(
        self,
        invoice: ConsolidatedInvoice,
        output_filename: Optional[str] = None,
    ) -> Path:
        """Synchronously generate standard PDF invoice file from ConsolidatedInvoice data.

        Args:
            invoice: Consolidated invoice data.
            output_filename: Optional custom filename.

        Returns:
            Path to the saved PDF file.
        """
        settings.setup_directories()

        # Sanitize invoice reference for filename
        sanitized_ref = invoice.invoice_ref.replace("#", "").replace("/", "_").strip()
        filename = output_filename or f"Facture_{sanitized_ref}.pdf"
        output_path = settings.output_dir / filename

        html_content = self.render_html(invoice)

        # 1. Try WeasyPrint (Linux / Docker standard)
        if self._compile_with_weasyprint(html_content, output_path):
            return output_path

        # 2. Try ReportLab (Native Python vector PDF engine)
        if self._compile_with_reportlab(invoice, output_path):
            return output_path

        # 3. Try xhtml2pdf (HTML fallback)
        if self._compile_with_xhtml2pdf(html_content, output_path):
            return output_path

        raise RuntimeError(
            f"Failed to generate PDF for invoice {invoice.invoice_ref} with all engines."
        )

    async def generate_pdf(
        self,
        invoice: ConsolidatedInvoice,
        output_filename: Optional[str] = None,
    ) -> Path:
        """Asynchronously generate standard PDF invoice file without blocking event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.generate_pdf_sync, invoice, output_filename
        )

    def _compile_magaza_with_reportlab(
        self, invoice: ConsolidatedInvoice, output_path: Path
    ) -> bool:
        """Compile a Magaza-grouped A4 PDF invoice directly using ReportLab matching reference style."""
        try:
            from collections import OrderedDict
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate,
                Paragraph,
                Spacer,
                Table,
                TableStyle,
                HRFlowable,
                Image as RLImage,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
            from consolidator import split_dimension_and_brand

            self._register_fonts()

            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=A4,
                rightMargin=40,
                leftMargin=40,
                topMargin=35,
                bottomMargin=35,
            )

            styles = getSampleStyleSheet()

            s_company_line = ParagraphStyle(
                "MCompanyLine", parent=styles["Normal"],
                fontName="Arial", fontSize=9.5, leading=13.5, textColor=colors.black
            )
            s_facture_title = ParagraphStyle(
                "MFactureTitle", parent=styles["Normal"],
                fontName="Arial-Bold", fontSize=18, leading=22, textColor=colors.black, alignment=TA_RIGHT
            )
            s_section_hdr = ParagraphStyle(
                "MSectionHdr", parent=styles["Normal"],
                fontName="Arial-Bold", fontSize=12, leading=16, textColor=colors.black
            )
            s_client_line = ParagraphStyle(
                "MClientLine", parent=styles["Normal"],
                fontName="Arial", fontSize=10, leading=14, textColor=colors.black
            )
            s_magaza_title = ParagraphStyle(
                "MMagazaTitle", parent=styles["Normal"],
                fontName="Arial-Bold", fontSize=13, leading=17, textColor=colors.black
            )
            s_th = ParagraphStyle(
                "MTH", parent=styles["Normal"],
                fontName="Arial-Bold", fontSize=9, leading=12, textColor=colors.black
            )
            s_td = ParagraphStyle(
                "MTD", parent=styles["Normal"],
                fontName="Arial", fontSize=9, leading=12, textColor=colors.black
            )
            s_tot_lbl = ParagraphStyle(
                "MTotLbl", parent=styles["Normal"],
                fontName="Arial-Bold", fontSize=10, leading=14, textColor=colors.black
            )
            s_tot_val = ParagraphStyle(
                "MTotVal", parent=styles["Normal"],
                fontName="Arial-Bold", fontSize=10, leading=14, textColor=colors.black, alignment=TA_RIGHT
            )

            story = []
            page_width = A4[0] - 80  # 40+40 margins

            # Group Items by Depot
            grouped_items: Dict[str, List[Any]] = OrderedDict()
            for item in invoice.items:
                d = (getattr(item, "depot", None) or "magaza 1").strip()
                if d not in grouped_items:
                    grouped_items[d] = []
                grouped_items[d].append(item)

            col_widths = [
                page_width * 0.23,   # Référence
                page_width * 0.12,   # Marque
                page_width * 0.13,   # Dépôt
                page_width * 0.12,   # Quantité
                page_width * 0.20,   # Prix unitaire (MAD)
                page_width * 0.20,   # Total (MAD)
            ]

            for depot_name, items_list in grouped_items.items():
                story.append(Paragraph(f"<b>{depot_name}</b>", s_magaza_title))
                story.append(Spacer(1, 4))

                table_data = [[
                    Paragraph("<b>Référence</b>", s_th),
                    Paragraph("<b>Marque</b>", s_th),
                    Paragraph("<b>Dépôt</b>", s_th),
                    Paragraph("<b>Quantité</b>", s_th),
                    Paragraph(f"<b>Prix unitaire ({settings.currency})</b>", s_th),
                    Paragraph(f"<b>Total ({settings.currency})</b>", s_th),
                ]]

                for item in items_list:
                    raw_ref = item.reference or item.description
                    brand_text = item.brand or ""
                    dim, parsed_brand = split_dimension_and_brand(raw_ref)
                    ref_text = dim or raw_ref
                    final_brand = brand_text or parsed_brand or ""
                    item_depot = getattr(item, "depot", None) or depot_name

                    table_data.append([
                        Paragraph(ref_text, s_td),
                        Paragraph(final_brand, s_td),
                        Paragraph(item_depot, s_td),
                        Paragraph(str(item.quantity), s_td),
                        Paragraph(f"{item.unit_price:.2f}", s_td),
                        Paragraph(f"{item.subtotal:.2f}", s_td),
                    ])

                magaza_table = Table(table_data, colWidths=col_widths, repeatRows=1)
                magaza_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("TOPPADDING", (0, 0), (-1, 0), 6),
                    ("TOPPADDING", (0, 1), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.75, colors.HexColor("#444444")),
                    ("BOX", (0, 0), (-1, -1), 1.0, colors.black),
                ]))
                story.append(magaza_table)
                story.append(Spacer(1, 12))

            # Grand Total Summary Bar
            total_table = Table([
                [
                    Paragraph(f"<b>Total Pièces : {invoice.total_quantity} pcs</b>", s_tot_lbl),
                    Paragraph(f"<b>Montant Total Global : {invoice.grand_total:.2f} {settings.currency}</b>", s_tot_val),
                ]
            ], colWidths=[page_width * 0.5, page_width * 0.5])
            total_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
                ("BOX", (0, 0), (-1, -1), 1.2, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(Spacer(1, 6))
            story.append(total_table)

            doc.build(story)
            logger.info(f"Generated clean Magaza PDF with ReportLab: {output_path}")
            return True
        except Exception as e:
            logger.error(f"ReportLab Magaza compilation failed: {e}", exc_info=True)
            return False

    def generate_magaza_pdf_sync(
        self,
        invoice: ConsolidatedInvoice,
        output_filename: Optional[str] = None,
    ) -> Path:
        """Synchronously generate Magaza-grouped PDF invoice file.

        Args:
            invoice: Consolidated invoice data with depots.
            output_filename: Optional custom filename.

        Returns:
            Path to the saved PDF file.
        """
        settings.setup_directories()

        sanitized_ref = invoice.invoice_ref.replace("#", "").replace("/", "_").strip()
        filename = output_filename or f"Facture_Magaza_{sanitized_ref}.pdf"
        output_path = settings.output_dir / filename

        html_content = self.render_magaza_html(invoice)

        # 1. Try WeasyPrint
        if self._compile_with_weasyprint(html_content, output_path):
            return output_path

        # 2. Try ReportLab
        if self._compile_magaza_with_reportlab(invoice, output_path):
            return output_path

        # 3. Try xhtml2pdf
        if self._compile_with_xhtml2pdf(html_content, output_path):
            return output_path

        raise RuntimeError(
            f"Failed to generate Magaza PDF for invoice {invoice.invoice_ref} with all engines."
        )

    async def generate_magaza_pdf(
        self,
        invoice: ConsolidatedInvoice,
        output_filename: Optional[str] = None,
    ) -> Path:
        """Asynchronously generate Magaza-grouped PDF invoice file.

        Args:
            invoice: Consolidated invoice data with depots.
            output_filename: Optional custom filename.

        Returns:
            Path to the saved PDF file.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.generate_magaza_pdf_sync, invoice, output_filename
        )


# Global PDF generator instance
pdf_generator = PDFGenerator()
