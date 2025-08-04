import re
from weasyprint import HTML
import io

def convert_newlines_to_br(text: str) -> str:
    """Преобразует символы новой строки \n в HTML-тег <br>."""
    return text.replace("\n", "<br>")

def emoji_to_codepoint(emoji: str) -> str:
    return '-'.join(f"{ord(char):x}" for char in emoji)

def replace_emoji_with_twemoji_svg(text: str, size: int = 1) -> str:
    emoji_pattern = re.compile(
        r"([\U0001F600-\U0001F64F"  # emoticons
        r"\U0001F300-\U0001F5FF"  # symbols & pictographs
        r"\U0001F680-\U0001F6FF"  # transport & map symbols
        r"\U0001F1E0-\U0001F1FF"  # flags
        r"\U00002700-\U000027BF"  # Dingbats
        r"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        r"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        r"\U00002600-\U000026FF"  # Misc symbols
        r"]+)"
    )

    def repl(match):
        emoji = match.group(0)
        code = emoji_to_codepoint(emoji)
        url = f"https://twemoji.maxcdn.com/v/latest/svg/{code}.svg"
        return f"<img src='{url}' width='{size}' height='{size}' style='vertical-align:middle;'>"

    return emoji_pattern.sub(repl, text)

def html_to_pdf_bytes(html_text: str) -> bytes:
    html_text = replace_emoji_with_twemoji_svg(html_text)
    full_html = (
        "<html>"
        "<head>"
        "<meta charset='UTF-8'>"
        "<style>"
        "img { display: inline; }"
        "body { font-family: 'Noto Sans', sans-serif; }"
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