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
        "<link rel='preconnect' href='https://fonts.googleapis.com'>"
        "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
        "<link href='https://fonts.googleapis.com/css2?family=Noto+Sans:ital,wght@0,100..900;1,100..900&display=swap' rel='stylesheet'>"
        "<style>"
        "@font-face { font-family: 'Noto Color Emoji'; src: url('https://fonts.gstatic.com/s/notocoloremoji/v24/0qyu3P9YP_5z81k1aW4u6Nty1eL5oK8A2oqUoI.ttf') format('truetype'); }"
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