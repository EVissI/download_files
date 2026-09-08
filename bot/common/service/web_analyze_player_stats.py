"""Журнал PR игроков по веб-анализам."""

from __future__ import annotations

from typing import Any

from loguru import logger

from bot.db.dao import WebAnalyzePlayerStatDAO
from bot.db.database import async_session_maker
from bot.db.models import WebAnalyzePlayerStat


def normalize_player_name(name: str) -> str:
    return " ".join(str(name or "").split()).casefold()[:100]


def display_player_name(name: str) -> str:
    return " ".join(str(name or "").split())[:100]


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_str(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return (text or default)[:50]


def row_from_metrics(
    *,
    web_user_id: int,
    player_name: str,
    game_id: str,
    file_name: str | None,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    shown = display_player_name(player_name)
    return {
        "web_user_id": int(web_user_id),
        "player_name": shown,
        "player_name_norm": normalize_player_name(player_name),
        "game_id": str(game_id),
        "file_name": (file_name or None),
        "moves_marked_bad": _as_int(metrics.get("moves_marked_bad")),
        "moves_marked_very_bad": _as_int(metrics.get("moves_marked_very_bad")),
        "error_rate_chequer": _as_float(metrics.get("error_rate_chequer")),
        "chequerplay_rating": _as_str(metrics.get("chequerplay_rating"), "Нет данных"),
        "rolls_marked_very_lucky": _as_int(metrics.get("rolls_marked_very_lucky")),
        "rolls_marked_lucky": _as_int(metrics.get("rolls_marked_lucky")),
        "rolls_marked_unlucky": _as_int(metrics.get("rolls_marked_unlucky")),
        "rolls_marked_very_unlucky": _as_int(metrics.get("rolls_marked_very_unlucky")),
        "rolls_rate_chequer": _as_float(metrics.get("rolls_rate_chequer")),
        "luck_rating": _as_str(metrics.get("luck_rating"), "Нет данных"),
        "missed_doubles_below_cp": _as_float(metrics.get("missed_doubles_below_cp")),
        "missed_doubles_above_cp": _as_float(metrics.get("missed_doubles_above_cp")),
        "wrong_doubles_below_sp": _as_float(metrics.get("wrong_doubles_below_sp")),
        "wrong_doubles_above_tg": _as_float(metrics.get("wrong_doubles_above_tg")),
        "wrong_takes": _as_float(metrics.get("wrong_takes")),
        "wrong_passes": _as_float(metrics.get("wrong_passes")),
        "cube_error_rate": _as_float(metrics.get("cube_error_rate")),
        "cube_decision_rating": _as_str(
            metrics.get("cube_decision_rating"), "Нет данных"
        ),
        "snowie_error_rate": abs(_as_float(metrics.get("snowie_error_rate"))),
        "overall_rating": _as_str(metrics.get("overall_rating"), "Нет данных"),
    }


async def persist_web_analyze_player_stats(
    *,
    web_user_id: int | None,
    game_id: str,
    filename: str | None,
    metrics_by_player: dict[str, Any],
) -> None:
    if not web_user_id or not game_id or not isinstance(metrics_by_player, dict):
        return
    try:
        async with async_session_maker() as session:
            async with session.begin():
                dao = WebAnalyzePlayerStatDAO(session)
                for player_name, metrics in metrics_by_player.items():
                    name_norm = normalize_player_name(str(player_name))
                    if not name_norm:
                        continue
                    data = metrics if isinstance(metrics, dict) else {}
                    await dao.add_if_missing(
                        **row_from_metrics(
                            web_user_id=int(web_user_id),
                            player_name=str(player_name),
                            game_id=str(game_id),
                            file_name=filename,
                            metrics=data,
                        )
                    )
    except Exception:
        logger.exception(
            "web analyze player stats persist failed game_id={} user={}",
            game_id,
            web_user_id,
        )


def format_pr(value: float) -> str:
    return f"{float(value):.2f}"


def serialize_player_detail(
    rows: list[WebAnalyzePlayerStat],
    *,
    last: int | None,
    total_games: int,
) -> dict[str, Any]:
    values = [float(row.snowie_error_rate) for row in rows]
    avg = (sum(values) / len(values)) if values else 0.0
    name = rows[0].player_name if rows else ""
    return {
        "name": name,
        "avg_pr": avg,
        "avg_pr_text": format_pr(avg),
        "values": values,
        "values_text": ", ".join(format_pr(v) for v in values),
        "games": len(rows),
        "total_games": int(total_games),
        "last": last,
        "text": (
            f"{name}: {format_pr(avg)}:\n({', '.join(format_pr(v) for v in values)})"
            if rows
            else ""
        ),
    }
