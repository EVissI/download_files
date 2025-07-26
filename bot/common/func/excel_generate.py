from datetime import datetime
from typing import Optional
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from bot.common.func.func import determine_rank
from bot.db.dao import UserDAO, DetailedAnalysisDAO

from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner



async def generate_detailed_analysis_report(
    dao: DetailedAnalysisDAO,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> io.BytesIO:
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Детальный анализ"

        # Стили
        header_font = Font(bold=True)
        header_fill = PatternFill(
            start_color="CCCCCC", end_color="CCCCCC", fill_type="solid"
        )
        center_align = Alignment(horizontal="center")

        # Заголовки
        headers = [
            "ID анализа",
            "ID пользователя",
            "Имя игрока",
            "Дата анализа",
            "Плохие ходы",
            "Очень плохие ходы",
            "Ошибка (Chequerplay)",
            "Рейтинг Chequerplay",
            "Очень удачные броски",
            "Удачные броски",
            "Неудачные броски",
            "Очень неудачные броски",
            "Рейтинг удачи",
            "Рейтинг кубика",
            "Общая ошибка",
            "Общий рейтинг",
        ]

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col)
            cell.value = header
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align

        analyses = await dao.get_all_detailed_analyzes(start_date, end_date)
        current_row = 2

        for analysis in analyses:
            ws.cell(row=current_row, column=1).value = analysis.id
            ws.cell(row=current_row, column=2).value = analysis.user_id
            ws.cell(row=current_row, column=3).value = analysis.player_name
            ws.cell(row=current_row, column=4).value = (
                analysis.created_at.strftime("%Y-%m-%d")
                if analysis.created_at
                else "N/A"
            )
            ws.cell(row=current_row, column=5).value = analysis.moves_marked_bad
            ws.cell(row=current_row, column=6).value = analysis.moves_marked_very_bad
            ws.cell(row=current_row, column=7).value = analysis.error_rate_chequer
            ws.cell(row=current_row, column=8).value = analysis.chequerplay_rating
            ws.cell(row=current_row, column=9).value = analysis.rolls_marked_very_lucky
            ws.cell(row=current_row, column=10).value = analysis.rolls_marked_lucky
            ws.cell(row=current_row, column=11).value = analysis.rolls_marked_unlucky
            ws.cell(row=current_row, column=12).value = (
                analysis.rolls_marked_very_unlucky
            )
            ws.cell(row=current_row, column=13).value = analysis.luck_rating
            ws.cell(row=current_row, column=14).value = analysis.cube_decision_rating
            ws.cell(row=current_row, column=15).value = analysis.snowie_error_rate
            ws.cell(row=current_row, column=16).value = analysis.overall_rating
            current_row += 1

        column_widths = {
            "A": 15,
            "B": 15,
            "C": 20,
            "D": 20,
            "E": 15,
            "F": 15,
            "G": 15,
            "H": 20,
            "I": 15,
            "J": 15,
            "K": 15,
            "L": 15,
            "M": 20,
            "N": 20,
            "O": 15,
            "P": 20,
        }

        for col, width in column_widths.items():
            ws.column_dimensions[col].width = width

        excel_buffer = io.BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)

        logger.info(f"Сгенерирован Excel отчет с {current_row-2} записями")
        return excel_buffer

    except Exception as e:
        logger.error(f"Ошибка при генерации Excel отчета: {e}")
        raise


async def generate_detailed_user_analysis_report(
    dao: DetailedAnalysisDAO,
    player_name: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
) -> io.BytesIO:
    """
    Генерирует Excel отчет со статистикой детального анализа по player_name.

    Args:
        dao: DetailedAnalysisDAO instance
        player_name: Игровое имя для фильтрации (обязательно)
        start_date: Начальная дата для фильтрации
        end_date: Конечная дата для фильтрации

    Returns:
        io.BytesIO: Excel файл в виде буфера байтов
    """
    wb = Workbook()
    ws = wb.active
    ws.title = f"Детальный анализ {player_name or ''}"

    # Стили
    header_font = Font(bold=True)
    header_fill = PatternFill(
        start_color="CCCCCC", end_color="CCCCCC", fill_type="solid"
    )
    center_align = Alignment(horizontal="center")

    # Заголовки
    headers = [
        "ID анализа",
        "ID пользователя",
        "Имя игрока",
        "Дата анализа",
        "Плохие ходы",
        "Очень плохие ходы",
        "Ошибка (Chequerplay)",
        "Рейтинг Chequerplay",
        "Очень удачные броски",
        "Удачные броски",
        "Неудачные броски",
        "Очень неудачные броски",
        "Рейтинг удачи",
        "Рейтинг кубика",
        "Общая ошибка",
        "Общий рейтинг",
    ]

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # Получаем данные детального анализа по player_name
    try:
        if not player_name:
            raise ValueError("Не указано игровое имя (player_name)")

        analyses = await dao.get_detailed_analyzes_by_player_name(
            player_name, start_date, end_date
        )
        current_row = 2

        for analysis in analyses:
            ws.cell(row=current_row, column=1).value = analysis.id
            ws.cell(row=current_row, column=2).value = analysis.user_id
            ws.cell(row=current_row, column=3).value = analysis.player_name
            ws.cell(row=current_row, column=4).value = (
                analysis.created_at.strftime("%Y-%m-%d")
                if analysis.created_at
                else "N/A"
            )
            ws.cell(row=current_row, column=5).value = analysis.moves_marked_bad
            ws.cell(row=current_row, column=6).value = analysis.moves_marked_very_bad
            ws.cell(row=current_row, column=7).value = analysis.error_rate_chequer
            ws.cell(row=current_row, column=8).value = analysis.chequerplay_rating
            ws.cell(row=current_row, column=9).value = analysis.rolls_marked_very_lucky
            ws.cell(row=current_row, column=10).value = analysis.rolls_marked_lucky
            ws.cell(row=current_row, column=11).value = analysis.rolls_marked_unlucky
            ws.cell(row=current_row, column=12).value = (
                analysis.rolls_marked_very_unlucky
            )
            ws.cell(row=current_row, column=13).value = analysis.luck_rating
            ws.cell(row=current_row, column=14).value = analysis.cube_decision_rating
            ws.cell(row=current_row, column=15).value = analysis.snowie_error_rate
            ws.cell(row=current_row, column=16).value = analysis.overall_rating

            current_row += 1

        # Устанавливаем ширину столбцов
        column_widths = {
            "A": 15,  # ID анализа
            "B": 15,  # ID пользователя
            "C": 20,  # Имя игрока
            "D": 20,  # Дата анализа
            "E": 15,  # Плохие ходы
            "F": 15,  # Очень плохие ходы
            "G": 15,  # Ошибка (Chequerplay)
            "H": 20,  # Рейтинг Chequerplay
            "I": 15,  # Очень удачные броски
            "J": 15,  # Удачные броски
            "K": 15,  # Неудачные броски
            "L": 15,  # Очень неудачные броски
            "M": 20,  # Рейтинг удачи
            "N": 20,  # Рейтинг кубика
            "O": 15,  # Общая ошибка
            "P": 20,  # Общий рейтинг
        }

        for col, width in column_widths.items():
            ws.column_dimensions[col].width = width

        # Сохраняем в буфер
        excel_buffer = io.BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)

        logger.info(
            f"Сгенерирован Excel отчет с {current_row-2} записями для {player_name}"
        )
        return excel_buffer

    except Exception as e:
        logger.error(f"Ошибка при генерации Excel отчета: {e}")
        raise
