"""
Чтение файлов из multipart-формы своими руками.

Штатное `files: list[UploadFile] = File(...)` строгое: если браузер прислал
часть без `filename`, Starlette отдаёт её строкой, и FastAPI отвечает 422 со
списком объектов в `detail` - на экране у пользователя из этого получается
«[object Object]», а причина теряется. На телефонах такое встречается.

Поэтому разбираем форму сами: берём всё, что похоже на файл, под обоими
именами поля, а про пустую форму сообщаем по-русски своим же 400.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.datastructures import UploadFile as StarletteUploadFile

# «files» шлёт наш фронт; «file» - запасное имя, его используют некоторые
# клиенты и ручные загрузки.
FIELD_NAMES = ("files", "file")


async def read_uploads(request: Request) -> list[StarletteUploadFile]:
    """Файлы из формы запроса. Пусто - значит клиент не прислал ни одного."""
    try:
        form = await request.form()
    except Exception as exc:  # тело не multipart или оборвалось на полпути
        raise HTTPException(
            status_code=400, detail="Не удалось прочитать файл из запроса"
        ) from exc

    uploads: list[StarletteUploadFile] = []
    for field in FIELD_NAMES:
        for item in form.getlist(field):
            if isinstance(item, StarletteUploadFile):
                uploads.append(item)
    return uploads


async def require_uploads(request: Request) -> list[StarletteUploadFile]:
    """То же, но с понятной ошибкой вместо 422, когда файлов нет."""
    uploads = await read_uploads(request)
    if not uploads:
        raise HTTPException(status_code=400, detail="Файлы не выбраны")
    return uploads
