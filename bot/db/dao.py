from loguru import logger
from bot.db.base import BaseDAO
from bot.db.models import User, Analysis, DetailedAnalysis
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime
from typing import Optional, List


class UserDAO(BaseDAO[User]):
    model = User

    async def get_all_users_with_games(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[User]:
        """
        Получает всех пользователей с их проанализированными играми.

        Args:
            start_date: Начальная дата для фильтрации игр
            end_date: Конечная дата для фильтрации игр

        Returns:
            List[User]: Список пользователей с их играми
        """
        try:
            # Формируем базовые условия для фильтрации
            conditions = []
            if start_date:
                conditions.append(Analysis.created_at >= start_date)
            if end_date:
                conditions.append(Analysis.created_at <= end_date)

            # Получаем ID пользователей с анализами за указанный период
            user_ids_query = select(Analysis.user_id).where(*conditions).distinct()
            user_ids_result = await self._session.execute(user_ids_query)
            user_ids = [row[0] for row in user_ids_result]

            if not user_ids:
                logger.info("Нет пользователей с анализами за указанный период")
                return []

            # Получаем пользователей с их анализами
            query = (
                select(self.model)
                .where(self.model.id.in_(user_ids))
                .options(
                    selectinload(
                        self.model.user_game_analisis.and_(*conditions)
                        if conditions
                        else self.model.user_game_analisis
                    )
                )
            )

            result = await self._session.execute(query)
            users = result.scalars().all()

            # Подробное логирование
            logger.info(f"Загружено {len(users)} пользователей с их играми")
            for user in users:
                logger.debug(
                    f"Пользователь {user.id} имеет {len(user.user_game_analisis)} анализов"
                )
                for analysis in user.user_game_analisis:
                    logger.debug(f"Анализ created_at: {analysis.created_at}")

            return users

        except SQLAlchemyError as e:
            logger.error(f"Ошибка при загрузке пользователей с играми: {e}")
            raise

    async def get_user_with_games(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Optional[User]:
        """
        Получает пользователя с его проанализированными играми.

        Args:
            user_id: ID пользователя
            start_date: Начальная дата для фильтрации игр
            end_date: Конечная дата для фильтрации игр

        Returns:
            Optional[User]: Пользователь с его играми или None
        """
        try:
            query = (
                select(self.model)
                .join(self.model.user_game_analisis)  # Явный join
                .options(selectinload(self.model.user_game_analisis))
                .filter(self.model.id == user_id)
            )

            if start_date or end_date:
                if start_date and end_date:
                    query = query.filter(
                        Analysis.created_at.between(start_date, end_date)
                    )
                elif start_date:
                    query = query.filter(Analysis.created_at >= start_date)
                else:
                    query = query.filter(Analysis.created_at <= end_date)
            query = query.distinct()
            result = await self._session.execute(query)
            user = result.scalar_one_or_none()
            if user:
                logger.info(
                    f"Загружен пользователь {user_id} с {len(user.user_game_analisis)} играми"
                )
            else:
                logger.info(f"Пользователь {user_id} не найден")
            return user
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при загрузке пользователя {user_id} с играми: {e}")
            raise
    
class AnalisisDAO(BaseDAO[Analysis]):
    model = Analysis

    async def get_average_analysis_by_user(self, user_id: int) -> dict:
        """
        Возвращает средние значения по каждому параметру анализа для указанного пользователя.
        """
        try:
            logger.info(
                f"Вычисление средних значений анализа для пользователя с ID {user_id}."
            )
            query = select(
                func.avg(self.model.mistake_total).label("avg_mistake_total"),
                func.avg(self.model.mistake_doubling).label("avg_mistake_doubling"),
                func.avg(self.model.mistake_taking).label("avg_mistake_taking"),
                func.avg(self.model.luck).label("avg_luck"),
                func.avg(self.model.pr).label("avg_pr"),
            ).filter(self.model.id == user_id)

            result = await self._session.execute(query)
            averages = result.fetchone()

            logger.debug(f"Полученные средние значения: {averages}")

            return {
                "mistake_total": averages.avg_mistake_total or 0,
                "mistake_doubling": averages.avg_mistake_doubling or 0,
                "mistake_taking": averages.avg_mistake_taking or 0,
                "luck": averages.avg_luck or 0.0,
                "pr": averages.avg_pr or 0.0,
            }

        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при вычислении средних значений для пользователя {user_id}: {e}"
            )
            raise


class DetailedAnalysisDAO(BaseDAO[DetailedAnalysis]):
    model = DetailedAnalysis

    async def get_average_analysis_by_user(self, user_id: int) -> dict:
        try:
            logger.info(
                f"Вычисление средних значений анализа для пользователя {user_id}"
            )
            query = select(
                # Chequerplay averages
                func.avg(self.model.moves_marked_bad).label("avg_moves_marked_bad"),
                func.avg(self.model.moves_marked_very_bad).label(
                    "avg_moves_marked_very_bad"
                ),
                func.avg(self.model.error_rate_chequer).label("avg_error_rate_chequer"),
                # Luck averages
                func.avg(self.model.rolls_marked_very_lucky).label(
                    "avg_rolls_marked_very_lucky"
                ),
                func.avg(self.model.rolls_marked_lucky).label("avg_rolls_marked_lucky"),
                func.avg(self.model.rolls_marked_unlucky).label(
                    "avg_rolls_marked_unlucky"
                ),
                func.avg(self.model.rolls_marked_very_unlucky).label(
                    "avg_rolls_marked_very_unlucky"
                ),
                func.avg(self.model.rolls_rate_chequer).label("avg_rolls_rate_chequer"),
                # Overall averages
                func.avg(self.model.snowie_error_rate).label("avg_snowie_error_rate"),
            ).filter(self.model.user_id == user_id)

            result = await self._session.execute(query)
            averages = result.fetchone()

            return {
                "moves_marked_bad": float(averages.avg_moves_marked_bad or 0),
                "moves_marked_very_bad": float(averages.avg_moves_marked_very_bad or 0),
                "error_rate_chequer": float(averages.avg_error_rate_chequer or 0),
                "rolls_marked_very_lucky": float(averages.avg_rolls_marked_very_lucky or 0),
                "rolls_marked_lucky": float(averages.avg_rolls_marked_lucky or 0),
                "rolls_marked_unlucky": float(averages.avg_rolls_marked_unlucky or 0),
                "rolls_marked_very_unlucky": float(averages.avg_rolls_marked_very_unlucky or 0),
                "rolls_rate_chequer": float(averages.avg_rolls_rate_chequer or 0),
                "snowie_error_rate": float(averages.avg_snowie_error_rate or 0),
            }

        except SQLAlchemyError as e:
            logger.error(f"Ошибка при вычислении средних значений: {e}")
            raise
    
    async def get_all_detailed_analyzes(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[DetailedAnalysis]:
        try:
            conditions = []
            if start_date:
                conditions.append(self.model.created_at >= start_date)
            if end_date:
                conditions.append(self.model.created_at <= end_date)

            async with self._session as session:
                analysis_ids_query = select(self.model.id).where(*conditions).distinct()
                analysis_ids_result = await session.execute(analysis_ids_query)
                analysis_ids = [row[0] for row in analysis_ids_result.fetchall()]

                if not analysis_ids:
                    logger.info("Нет записей детального анализа за указанный период")
                    return []

                query = (
                    select(self.model)
                    .where(self.model.id.in_(analysis_ids))
                    .options(selectinload(self.model.user))
                )

                result = await session.execute(query)
                analyses = result.scalars().all()

                logger.info(f"Загружено {len(analyses)} записей детального анализа")
                for analysis in analyses:
                    logger.debug(
                        f"Анализ {analysis.id} для пользователя {analysis.user_id} имеет {len(analysis.user.detailed_analyzes)} записей, created_at: {analysis.created_at}"
                    )

                return analyses

        except SQLAlchemyError as e:
            logger.error(f"Ошибка при загрузке записей детального анализа: {e}")
            raise

    async def get_detailed_analyzes_by_user(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[DetailedAnalysis]:
        """
        Получает записи детального анализа для конкретного пользователя с фильтрацией по дате.

        Args:
            user_id: ID пользователя
            start_date: Начальная дата для фильтрации анализов
            end_date: Конечная дата для фильтрации анализов

        Returns:
            List[DetailedAnalysis]: Список записей детального анализа для пользователя
        """
        try:
            # Формируем базовые условия для фильтрации
            conditions = [self.model.user_id == user_id]
            if start_date or end_date:
                if start_date and end_date:
                    conditions.append(self.model.created_at.between(start_date, end_date))
                elif start_date:
                    conditions.append(self.model.created_at >= start_date)
                else:
                    conditions.append(self.model.created_at <= end_date)

            # Основной запрос с фильтрацией
            query = (
                select(self.model)
                .where(*conditions)
                .options(selectinload(self.model.user))  # Load user relationship
            )

            result = await self._session.execute(query)
            analyses = result.scalars().all()

            if not analyses:
                logger.info(f"Нет записей детального анализа для пользователя {user_id} за указанный период")
                return []

            # Подробное логирование
            logger.info(f"Загружено {len(analyses)} записей детального анализа для пользователя {user_id}")
            for analysis in analyses:
                logger.debug(
                    f"Анализ {analysis.id}, created_at: {analysis.created_at}"
                )

            return analyses

        except SQLAlchemyError as e:
            logger.error(f"Ошибка при загрузке записей детального анализа для пользователя {user_id}: {e}")
            raise