from loguru import logger
import pytz
from bot.db.base import BaseDAO
from bot.db.models import (
    User,
    Analysis,
    DetailedAnalysis,
    Promocode,
    UserAnalizePayment,
    UserPromocode,
    AnalizePayment,
)
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone
from typing import Optional, List


class UserDAO(BaseDAO[User]):
    model = User

    async def get_total_analiz_balance(self, user_id: int) -> int:
        """
        Calculates the total analiz_balance for a user from active UserPromocode and UserAnalizePayment records.
        """
        try:
            # Get sum of balances from active UserPromocode
            promo_query = select(func.sum(UserPromocode.current_analize_balance)).where(
                UserPromocode.user_id == user_id,
                UserPromocode.is_active == True
            )
            promo_result = await self._session.execute(promo_query)
            promo_balance = promo_result.scalar() or 0

            # Get sum of balances from active UserAnalizePayment
            payment_query = select(func.sum(UserAnalizePayment.current_analize_balance)).where(
                UserAnalizePayment.user_id == user_id,
                UserAnalizePayment.is_active == True
            )
            payment_result = await self._session.execute(payment_query)
            payment_balance = payment_result.scalar() or 0

            total_balance = promo_balance + payment_balance
            logger.info(f"Total analiz_balance for user {user_id}: {total_balance}")
            return total_balance
        except SQLAlchemyError as e:
            logger.error(f"Error calculating total analiz_balance for user {user_id}: {e}")
            raise

    async def decrease_analiz_balance(self, user_id: int) -> bool:
        """
        Decreases analiz_balance by 1 from the oldest active UserPromocode or UserAnalizePayment.
        Returns True if balance was decreased successfully, False otherwise.
        """
        try:
            # Find the oldest active record (UserPromocode or UserAnalizePayment)
            promo_query = select(
                UserPromocode,
                UserPromocode.created_at.label('created_at')
            ).where(
                UserPromocode.user_id == user_id,
                UserPromocode.is_active == True,
                UserPromocode.current_analize_balance > 0
            )
            
            payment_query = select(
                UserAnalizePayment,
                UserAnalizePayment.created_at.label('created_at')
            ).where(
                UserAnalizePayment.user_id == user_id,
                UserAnalizePayment.is_active == True,
                UserAnalizePayment.current_analize_balance > 0
            )

            # Combine queries using UNION
            union_query = promo_query.union(payment_query).order_by('created_at')
            
            result = await self._session.execute(union_query)
            oldest_record = result.first()

            if not oldest_record:
                logger.info(f"No active records with balance > 0 for user {user_id}")
                return False

            record = oldest_record[0]  # Get the actual record (UserPromocode or UserAnalizePayment)
            
            # Decrease balance
            record.current_analize_balance -= 1
            if record.current_analize_balance == 0:
                record.is_active = False
            
            await self._session.commit()
            logger.info(f"Decreased balance for user {user_id} from {record.__class__.__name__}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error decreasing analiz_balance for user {user_id}: {e}")
            await self._session.rollback()
            return False

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
                # Cube averages (новые поля)
                func.avg(self.model.missed_doubles_below_cp).label(
                    "avg_missed_doubles_below_cp"
                ),
                func.avg(self.model.missed_doubles_above_cp).label(
                    "avg_missed_doubles_above_cp"
                ),
                func.avg(self.model.wrong_doubles_below_sp).label(
                    "avg_wrong_doubles_below_sp"
                ),
                func.avg(self.model.wrong_doubles_above_tg).label(
                    "avg_wrong_doubles_above_tg"
                ),
                func.avg(self.model.wrong_takes).label("avg_wrong_takes"),
                func.avg(self.model.wrong_passes).label("avg_wrong_passes"),
                func.avg(self.model.cube_error_rate).label("avg_cube_error_rate"),
                # Overall averages
                func.avg(self.model.snowie_error_rate).label("avg_snowie_error_rate"),
            ).filter(self.model.user_id == user_id)

            result = await self._session.execute(query)
            averages = result.fetchone()

            return {
                "moves_marked_bad": float(averages.avg_moves_marked_bad or 0),
                "moves_marked_very_bad": float(averages.avg_moves_marked_very_bad or 0),
                "error_rate_chequer": float(averages.avg_error_rate_chequer or 0),
                "rolls_marked_very_lucky": float(
                    averages.avg_rolls_marked_very_lucky or 0
                ),
                "rolls_marked_lucky": float(averages.avg_rolls_marked_lucky or 0),
                "rolls_marked_unlucky": float(averages.avg_rolls_marked_unlucky or 0),
                "rolls_marked_very_unlucky": float(
                    averages.avg_rolls_marked_very_unlucky or 0
                ),
                "rolls_rate_chequer": float(averages.avg_rolls_rate_chequer or 0),
                # Новые cube поля
                "missed_doubles_below_cp": float(
                    averages.avg_missed_doubles_below_cp or 0
                ),
                "missed_doubles_above_cp": float(
                    averages.avg_missed_doubles_above_cp or 0
                ),
                "wrong_doubles_below_sp": float(
                    averages.avg_wrong_doubles_below_sp or 0
                ),
                "wrong_doubles_above_tg": float(
                    averages.avg_wrong_doubles_above_tg or 0
                ),
                "wrong_takes": float(averages.avg_wrong_takes or 0),
                "wrong_passes": float(averages.avg_wrong_passes or 0),
                "cube_error_rate": float(averages.avg_cube_error_rate or 0),
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
                    query = query.where(
                        self.model.created_at.between(start_date, end_date)
                    )
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

    async def get_detailed_analyzes_by_player_name(
        self,
        player_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[DetailedAnalysis]:
        """
        Получает записи детального анализа для конкретного игрового имени с фильтрацией по дате.
        """
        try:
            conditions = [self.model.player_name == player_name]
            if start_date and end_date:
                conditions.append(self.model.created_at.between(start_date, end_date))
            elif start_date:
                conditions.append(self.model.created_at >= start_date)
            elif end_date:
                conditions.append(self.model.created_at <= end_date)

            query = select(self.model).where(*conditions)
            result = await self._session.execute(query)
            analyses = result.scalars().all()
            logger.info(
                f"Загружено {len(analyses)} записей детального анализа для игрока {player_name}"
            )
            return analyses
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при загрузке записей детального анализа для игрока {player_name}: {e}"
            )
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
                UserPromocode.promocode_id == promocode.id,
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
        Активирует промокод для пользователя (добавляет запись в user_promocode, увеличивает activate_count и увеличивает analiz_balance).
        """
        try:
            promocode = await self.find_by_code(code)
            if not promocode:
                return False

            user = await self._session.get(User, user_id)
            if not user:
                return False  # Не создавать нового пользователя

            # Добавляем запись о том, что пользователь активировал промокод
            user_promo = UserPromocode(user_id=user_id, promocode_id=promocode.id, current_analize_balance=promocode.analiz_count)
            self._session.add(user_promo)

            # Увеличиваем счетчик активаций
            promocode.activate_count = (promocode.activate_count or 0) + 1


            await self._session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при активации промокода '{code}': {e}")
            await self._session.rollback()
            return False


class AnalizePaymentDAO(BaseDAO[AnalizePayment]):
    model = AnalizePayment

    async def get_all_payments(self) -> List[AnalizePayment]:
        """
        Получает все доступные пакеты услуг.
        """
        try:
            query = select(self.model)
            result = await self._session.execute(query)
            payments = result.scalars().all()
            logger.info(f"Загружено {len(payments)} пакетов услуг")
            return payments
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при загрузке пакетов услуг: {e}")
            raise

    async def deactivate(self, payment_id: int) -> bool:
        """
        Деактивирует пакет услуг (is_active = False) по id.
        """
        try:
            payment = await self._session.get(self.model, payment_id)
            if not payment:
                return False
            payment.is_active = False
            return True
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при деактивации пакета услуг {payment_id}: {e}")
            return False


class UserPromocodeDAO(BaseDAO[UserPromocode]):
    model = UserPromocode

    async def get_active_with_promocode(self) -> list[UserPromocode]:
        """
        Получить все активные записи UserPromocode с подгруженными объектами Promocode.
        """
        try:
            query = (
                select(self.model)
                .where(self.model.is_active == True)
                .options(selectinload(self.model.promocode))
            )
            result = await self._session.execute(query)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении активных UserPromocode: {e}")
            raise

    async def get_all_with_promocode(self) -> list[UserPromocode]:
        """
        Получить все записи UserPromocode с подгруженными объектами Promocode.
        """
        try:
            query = select(self.model).options(selectinload(self.model.promocode))
            result = await self._session.execute(query)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении UserPromocode: {e}")
            raise

    async def get_all_by_user(self, user_id: int) -> list[UserPromocode]:
        """
        Получить все записи UserPromocode для пользователя с подгруженными промокодами.
        """
        try:
            query = (
                select(self.model)
                .where(self.model.user_id == user_id)
                .options(selectinload(self.model.promocode))
            )
            result = await self._session.execute(query)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при получении UserPromocode для пользователя {user_id}: {e}"
            )
            raise


class UserAnalizePaymentDAO(BaseDAO[UserAnalizePayment]):
    model = UserAnalizePayment

    async def get_active_with_payment(self) -> list[UserAnalizePayment]:
        """
        Получить все активные записи UserAnalizePayment с подгруженными объектами AnalizePayment.
        """
        try:
            query = (
                select(self.model)
                .where(self.model.is_active == True)
                .options(selectinload(self.model.analize_payment))
            )
            result = await self._session.execute(query)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении активных UserAnalizePayment: {e}")
            raise

    async def get_all_with_payment(self) -> list[UserAnalizePayment]:
        """
        Получить все записи UserAnalizePayment с подгруженными объектами AnalizePayment.
        """
        try:
            query = select(self.model).options(selectinload(self.model.analize_payment))
            result = await self._session.execute(query)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении UserAnalizePayment: {e}")
            raise

    async def get_all_by_user(self, user_id: int) -> list[UserAnalizePayment]:
        """
        Получить все записи UserAnalizePayment для пользователя с подгруженными пакетами.
        """
        try:
            query = (
                select(self.model)
                .where(self.model.user_id == user_id)
                .options(selectinload(self.model.analize_payment))
            )
            result = await self._session.execute(query)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при получении UserAnalizePayment для пользователя {user_id}: {e}"
            )
            raise
