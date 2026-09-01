from __future__ import annotations

from weasyprint import HTML
import io
import re
from datetime import datetime
from urllib.parse import quote

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

def make_page(text: str, font_size:int) -> HTML:
    """Создаёт HTML-страницу (WeasyPrint HTML объект)"""
    text = replace_emoji_with_twemoji_svg(text)
    full_html = f"""
    <html>
      <head>
        <meta charset='UTF-8'>
        <style>
          body {{ font-family: 'Noto Sans', sans-serif; font-size: {font_size}px; }}
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


ANALYSIS_TABLE_CSS = """
@page { size: A4; margin: 12mm; }
body {
  font-family: 'Noto Sans', 'DejaVu Sans', sans-serif;
  font-size: 11px;
  color: #111;
}
h2 { font-size: 14px; margin: 0 0 10px; }
.analyze-vs { font-weight: 700; font-size: 13px; margin: 0 0 12px; }
.analyze-block { margin-bottom: 14px; page-break-inside: avoid; }
.analyze-block h3 { font-size: 12px; margin: 0 0 6px; color: #333; }
img.emoji { width: 1em; height: 1em; vertical-align: middle; display: inline-block; }
.analyze-table { width: 100%; border-collapse: collapse; }
.analyze-table th, .analyze-table td {
  border: 1px solid #444;
  padding: 5px 8px;
  text-align: left;
}
.analyze-table thead th { background: #e6e6e6; }
.analyze-table tbody th { background: #f3f3f3; font-weight: 600; }
.page { page-break-after: always; }
"""


def make_analysis_tables_page(html_fragment: str) -> HTML:
    """PDF-страница из HTML-таблиц веб-кабинета (без ASCII/псевдографики)."""
    html_fragment = replace_emoji_with_twemoji_svg(html_fragment)
    full_html = (
        "<html><head><meta charset='UTF-8'>"
        f"<style>{ANALYSIS_TABLE_CSS}</style></head>"
        f"<body><div class='page'>{html_fragment}</div></body></html>"
    )
    return HTML(string=full_html, encoding="utf-8")


def analysis_tables_to_pdf_bytes(html_fragment: str) -> bytes:
    html_fragment = replace_emoji_with_twemoji_svg(html_fragment)
    pdf_io = io.BytesIO()
    full_html = (
        "<html><head><meta charset='UTF-8'>"
        f"<style>{ANALYSIS_TABLE_CSS}</style></head>"
        f"<body>{html_fragment}</body></html>"
    )
    HTML(string=full_html, encoding="utf-8").write_pdf(pdf_io)
    pdf_io.seek(0)
    return pdf_io.read()


def analysis_pdf_filename(
    metrics: dict | None,
    original_filename: str | None = None,
) -> str:
    date = datetime.now().strftime("%d.%m.%Y_%H.%M")
    names = list((metrics or {}).keys())
    if len(names) >= 2:
        p1, p2 = names[0], names[1]
        try:
            e1 = abs(float((metrics.get(p1) or {}).get("snowie_error_rate") or 0))
            e2 = abs(float((metrics.get(p2) or {}).get("snowie_error_rate") or 0))
            base = f"{p1} ({e1:.1f}) - {p2} ({e2:.1f})_{date}"
        except (TypeError, ValueError):
            base = f"{p1}_vs_{p2}_{date}"
    elif original_filename:
        stem = original_filename.replace("\\", "/").split("/")[-1]
        if "." in stem:
            stem = stem.rsplit(".", 1)[0]
        base = f"{stem}_{date}"
    else:
        base = f"analysis_{date}"
    safe = re.sub(r'[\\/:*?"<>|]+', ".", str(base)).replace(" ", "")
    return f"{safe or 'analysis'}.pdf"


def pdf_content_disposition(filename: str) -> str:
    raw = (filename or "analysis.pdf").replace("\\", "/").split("/")[-1].strip()
    if not raw.lower().endswith(".pdf"):
        raw += ".pdf"
    ascii_name = (
        "".join(c if c.isascii() and c not in '"\\' else "_" for c in raw)[:180]
        or "analysis.pdf"
    )
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(raw)}"