from weasyprint import HTML
import io

def html_to_pdf_bytes(html_text: str) -> bytes:
    pdf_io = io.BytesIO()
    HTML(string=html_text).write_pdf(pdf_io)
    pdf_io.seek(0)
    return pdf_io.read()