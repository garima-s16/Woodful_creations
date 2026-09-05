"""Product PDF generation - reportlab Platypus using the shared
Woodful document design system. Split out of the former
shared/pdf_generator.py - see modules/sales/pdf_generator.py's
docstring for why."""
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from app.modules.catalog.models import Product
from app.shared.document_style import (
    format_inr, get_styles, build_header, section_table, build_footer_text, pdf_text,
)


def generate_product_pdf(product: Product) -> BytesIO:
    """Product Master detail document."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.6 * inch, bottomMargin=0.7 * inch,
                             leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    styles = get_styles()
    elements = build_header("PRODUCT", product.product_code, datetime.utcnow().strftime("%d %b %Y"), product.business_id)

    dims = "-"
    if product.length and product.width and product.height:
        dims = f"{product.length}\u00d7{product.width}\u00d7{product.height} {product.dimension_unit or ''}".strip()

    elements.append(section_table(
        [[("PRODUCT NAME", product.name), ("TYPE", product.product_type.title())],
         [("CATEGORY", product.category or "-"), ("SUBCATEGORY", product.subcategory or "-")],
         [("UNIT", product.unit), ("DIMENSIONS", dims)],
         [("PRIMARY MATERIAL", product.primary_material or "-"), ("FINISH", product.finish or "-")],
         [("DEFAULT RATE", format_inr(product.selling_price) if product.selling_price is not None else "-"),
          ("GST %", f"{float(product.gst_percent)}%" if product.gst_percent is not None else "-")],
         [("STATUS", "Active" if product.is_active else "Inactive"), ("", "")]],
        [3.5 * inch, 3.5 * inch],
    ))

    if product.specifications:
        elements.append(Spacer(1, 14))
        elements.append(Paragraph(
            f'<font color="#70685D" size="8">DESCRIPTION / SPECIFICATIONS</font><br/>{pdf_text(product.specifications)}',
            styles["body"],
        ))

    if product.notes:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f'<font color="#70685D" size="8">NOTES</font><br/>{pdf_text(product.notes)}', styles["body"]))

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(build_footer_text(), styles["footer"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


