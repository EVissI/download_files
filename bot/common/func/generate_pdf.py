import re
from weasyprint import HTML
import io

def convert_newlines_to_br(text: str) -> str:
    """Преобразует символы новой строки \n в HTML-тег <br>."""
    return text.replace("\n", "<br>")

def emoji_to_codepoint(emoji: str) -> str:
    return '-'.join(f"{ord(char):x}" for char in emoji)

def replace_emoji_with_twemoji_svg(text: str) -> str:
    emoji_pattern = re.compile(
        r"([\U0001F600-\U0001F64F"
        r"\U0001F300-\U0001F5FF"
        r"\U0001F680-\U0001F6FF"
        r"\U0001F1E0-\U0001F1FF"
        r"\U00002700-\U000027BF"
        r"\U0001F900-\U0001F9FF"
        r"\U0001FA70-\U0001FAFF"
        r"\U00002600-\U000026FF"
        r"]+)"
    )

    def repl(match):
        emoji = match.group(0)
        code = '-'.join(f"{ord(c):x}" for c in emoji)
        url = f"https://twemoji.maxcdn.com/v/latest/svg/{code}.svg"
        return f"<img src='{url}' class='emoji'>"

    return emoji_pattern.sub(repl, text)

def html_to_pdf_bytes(html_text: str) -> bytes:
    html_text = replace_emoji_with_twemoji_svg(html_text)
    full_html = (
        "<html>"
        "<head>"
        "<meta charset='UTF-8'>"
        "<style>"
        "body { font-family: 'Noto Sans', sans-serif; font-size: 11px;}"
        "pre { white-space: pre-wrap; word-wrap: break-word; }"
        "img.emoji { width: 1em; height: 1em; vertical-align: left; display: inline-block; }"
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

def make_page(text: str) -> HTML:
    """Создаёт HTML-страницу (WeasyPrint HTML объект)"""
    text = replace_emoji_with_twemoji_svg(text)
    full_html = f"""
    <html>
      <head>
        <meta charset='UTF-8'>
        <style>
          body {{ font-family: 'Noto Sans', sans-serif; font-size: 11px; }}
          pre {{ white-space: pre-wrap; word-wrap: break-word; }}
          img.emoji {{ width: 1em; height: 1em; vertical-align: middle; display: inline-block; }}
          .page {{ page-break-after: always; }}
        </style>
      </head>
      <body>
        <div class="page">{convert_newlines_to_br(text)}</div>
      </body>
    </html>
    """
    return HTML(string=full_html, encoding="utf-8")


def merge_pages(pages: list[HTML]) -> bytes:
    """Объединяет список HTML-страниц в один PDF"""
    pdf_io = io.BytesIO()
    documents = [page.render() for page in pages]  # каждая страница → PDF document
    merged = documents[0]
    for doc in documents[1:]:
        merged.pages.extend(doc.pages)
    merged.write_pdf(pdf_io)
    pdf_io.seek(0)
    return pdf_io.read()