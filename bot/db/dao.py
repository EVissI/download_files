from loguru import logger
from bot.db.base import BaseDAO
from bot.db.models import User, Analysis, DetailedAnalysis, Promocode, UserPromocode
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone
from typing import Optional, List


class UserDAO(BaseDAO[User]):
    model = User

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
        """
        Получает все записи детального анализа с необязательной фильтрацией по дате.
        """
        try:
            query = select(self.model)
            if start_date or end_date:
                if start_date and end_date:
                    query = query.where(self.model.created_at.between(start_date, end_date))
                elif start_date:
                    query = query.where(self.model.created_at >= start_date)
                else:
                    query = query.where(self.model.created_at <= end_date)
            query = query.options(selectinload(self.model.user))
            result = await self._session.execute(query)
            analyses = result.scalars().all()
            logger.info(f"Загружено {len(analyses)} записей детального анализа (всего)")
            return analyses
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при загрузке всех записей детального анализа: {e}")
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


class PromoCodeDAO(BaseDAO[Promocode]):
    model = Promocode

    async def find_by_code(self, code: str) -> Optional[Promocode]:
        """
        Находит промокод по его коду.
        """
        try:
            query = select(self.model).where(self.model.code == code)
            result = await self._session.execute(query)
            promocode = result.scalar_one_or_none()
            return promocode
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при поиске промокода по коду '{code}': {e}")
            raise

    async def get_active_promo_codes(self) -> List[Promocode]:
        """
        Получает все активные промокоды.
        """
        try:
            query = select(self.model).where(self.model.is_active == True)
            result = await self._session.execute(query)
            promo_codes = result.scalars().all()
            logger.info(f"Загружено {len(promo_codes)} активных промокодов")
            return promo_codes
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при загрузке активных промокодов: {e}")
            raise
    
    async def validate_promo_code(self, code: str, user_id: int) -> bool:
        """
        Проверяет, можно ли активировать промокод для пользователя.
        """
        try:
            promocode = await self.find_by_code(code)
            if not promocode:
                return False
            if not promocode.is_active:
                return False
            if promocode.max_usage is not None and promocode.activate_count is not None:
                if promocode.activate_count >= promocode.max_usage:
                    return False

            query = select(UserPromocode).where(
                UserPromocode.user_id == user_id,
                UserPromocode.promocode_id == promocode.id
            )
            result = await self._session.execute(query)
            user_promo = result.scalar_one_or_none()
            if user_promo:
                return False
            return True
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при валидации промокода '{code}': {e}")
            return False
    
    async def activate_promo_code(self, code: str, user_id: int) -> bool:
        """
        Активирует промокод для пользователя (добавляет запись в user_promocode, увеличивает activate_count и продлевает подписку).
        """
        try:
            promocode = await self.find_by_code(code)
            if not promocode:
                return False

            # Продлеваем подписку пользователю
            user = await self._session.get(User, user_id)
            if not user:
                return False  # Не создавать нового пользователя

            # Добавляем запись о том, что пользователь активировал промокод
            user_promo = UserPromocode(user_id=user_id, promocode_id=promocode.id)
            self._session.add(user_promo)

            # Увеличиваем счетчик активаций
            promocode.activate_count = (promocode.activate_count or 0) + 1

            now = datetime.now(timezone.utc)
            if user.end_sub_time and user.end_sub_time > now:
                user.end_sub_time += timedelta(days=promocode.discount_days)
            else:
                user.end_sub_time = now + timedelta(days=promocode.discount_days)

            await self._session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при активации промокода '{code}': {e}")
            await self._session.rollback()
            return False