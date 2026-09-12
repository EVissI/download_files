"""
Расширения файлов матчей.

Яндекс.Браузер на телефонах отдаёт выбранный матч с расширением .bin вместо
.mat, поэтому .bin принимается наравне с .mat во всех точках загрузки. Дальше
по коду такого расширения нет: имя сразу приводится к .mat, и gnubg, S3 и
история видят обычный матч.
"""

from __future__ import annotations

from pathlib import Path

# Расширения, которые считаются матчем на входе.
MAT_UPLOAD_EXTENSIONS = (".mat", ".bin")


def is_mat_upload_name(name: str | None) -> bool:
    return str(name or "").lower().endswith(MAT_UPLOAD_EXTENSIONS)


def as_mat_name(name: str | None) -> str:
    """Имя для хранения: всё, что пришло не с .mat, сохраняем как .mat."""
    raw = str(name or "").strip() or "match.mat"
    if raw.lower().endswith(".mat"):
        return raw
    return f"{Path(raw).stem}.mat"
