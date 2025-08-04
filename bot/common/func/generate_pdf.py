from weasyprint import HTML
import io

def convert_newlines_to_br(text: str) -> str:
    """Преобразует символы новой строки \n в HTML-тег <br>."""
    return text.replace("\n", "<br>")

def html_to_pdf_bytes(html_text: str) -> bytes:
    full_html = (
        "<html>"
        "<head>"
        "<meta charset='UTF-8'>"
        "<style>"
        "@font-face { font-family: 'Noto Sans'; src: url('fonts/NotoSans-Regular.ttf') format('truetype'); }"
        "@font-face { font-family: 'Noto Color Emoji'; src: url('fonts/NotoColorEmoji.ttf') format('truetype'); }"
        "body { font-family: 'Noto Sans', 'Noto Color Emoji', sans-serif; }"
        "pre { white-space: pre-wrap; word-wrap: break-word; }"
        "</style>"
        "</head>"
        "<body>"
        f"{convert_newlines_to_br(html_text)}" 
        "</body>"
        "</html>"
    )
    pdf_io = io.BytesIO()
    HTML(string=full_html, encoding='utf-8').write_pdf(pdf_io)
    pdf_io.seek(0)
    return pdf_io.read()