from weasyprint import HTML
import io

def convert_newlines_to_br(text: str) -> str:
    """Преобразует символы новой строки \n в HTML-тег <br>."""
    return text.replace("\n", "<br>")

def html_to_pdf_bytes(html_text: str) -> bytes:
    pdf_io = io.BytesIO()
    HTML(string=convert_newlines_to_br(html_text)).write_pdf(pdf_io)
    pdf_io.seek(0)
    return pdf_io.read()