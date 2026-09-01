"""Одно follow-up сообщение после анализа вместо пачки SendMessage."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from aiogram.types import Message
from loguru import logger

from bot.common.func.pro_analysis_order import create_pro_order
from bot.common.func.telegram_safe import safe_answer, safe_bot_send
from bot.common.kbds.inline.autoanalize import get_analyze_actions_kb

if TYPE_CHECKING:
    from fluentogram import TranslatorRunner
    from bot.db.dao import MessagesTextsDAO
    from bot.db.models import User


async def send_analyze_followup(
    message: Message,
    *,
    i18n: "TranslatorRunner",
    user_info: "User",
    context: str,
    file_id: str = "",
    file_path: str | None = None,
    file_name: str | None = None,
    include_pdf: bool = True,
    include_hints: bool = True,
    include_pro: bool = True,
    service: str = "autoanaliz",
    message_dao: "MessagesTextsDAO | None" = None,
) -> None:
    """
    PDF / анализ ошибок / заказ эксперта — одним сообщением с кнопками.
    """
    request_id = None
    if include_pro:
        try:
            request_id = await create_pro_order(
                user_id=user_info.id,
                username=getattr(message.from_user, "username", None)
                or getattr(user_info, "username", None),
                service=service,
                file_path=file_path,
                file_name=file_name
                or (os.path.basename(file_path) if file_path else None),
            )
        except Exception as exc:
            logger.error("create_pro_order failed: {}", exc)

    parts: list[str] = []
    if include_hints:
        parts.append(i18n.auto.analyze.ask_hints())
    if include_pdf:
        pdf_text = None
        if message_dao is not None:
            try:
                pdf_text = await message_dao.get_text(
                    "analyze_ask_pdf", user_info.lang_code
                )
            except Exception:
                pdf_text = None
        parts.append(pdf_text or i18n.auto.analyze.ask_pdf())
    if include_pro:
        parts.append(i18n.pro.analysis.ask())

    text = "\n\n".join(part for part in parts if part)
    if not text:
        return

    markup = get_analyze_actions_kb(
        i18n,
        context,
        file_id=file_id,
        include_pdf=include_pdf,
        include_hints=include_hints,
        pro_request_id=request_id,
    )
    await safe_answer(message, text, reply_markup=markup)


async def send_analyze_followup_chat(
    bot,
    chat_id: int,
    *,
    i18n: "TranslatorRunner",
    user_info: "User",
    context: str,
    file_id: str = "",
    file_path: str | None = None,
    file_name: str | None = None,
    username: str | None = None,
    include_pdf: bool = True,
    include_hints: bool = True,
    include_pro: bool = True,
    service: str = "autoanaliz",
    message_dao: "MessagesTextsDAO | None" = None,
) -> None:
    request_id = None
    if include_pro:
        try:
            request_id = await create_pro_order(
                user_id=user_info.id,
                username=username or getattr(user_info, "username", None),
                service=service,
                file_path=file_path,
                file_name=file_name
                or (os.path.basename(file_path) if file_path else None),
            )
        except Exception as exc:
            logger.error("create_pro_order failed: {}", exc)

    parts: list[str] = []
    if include_hints:
        parts.append(i18n.auto.analyze.ask_hints())
    if include_pdf:
        pdf_text = None
        if message_dao is not None:
            try:
                pdf_text = await message_dao.get_text(
                    "analyze_ask_pdf", user_info.lang_code
                )
            except Exception:
                pdf_text = None
        parts.append(pdf_text or i18n.auto.analyze.ask_pdf())
    if include_pro:
        parts.append(i18n.pro.analysis.ask())

    text = "\n\n".join(part for part in parts if part)
    if not text:
        return

    markup = get_analyze_actions_kb(
        i18n,
        context,
        file_id=file_id,
        include_pdf=include_pdf,
        include_hints=include_hints,
        pro_request_id=request_id,
    )
    await safe_bot_send(bot, chat_id, text, reply_markup=markup)
