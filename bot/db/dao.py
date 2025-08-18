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
    UserPromocodeService,
    PromocodeServiceQuantity,
)
from sqlalchemy import func, literal, not_, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone
from typing import Optional, List


class PromocodeServiceQuantityDAO(BaseDAO[PromocodeServiceQuantity]):
    model = PromocodeServiceQuantity


class UserDAO(BaseDAO[User]):
    model = User

    async def get_users_with_payments(self) -> list[User]:
        """
        Получить всех пользователей, у которых есть активные записи в UserAnalizePayment или UserPromocode,
        с подгруженными объектами UserAnalizePayment, AnalizePayment и UserPromocode.
        """
        try:
            query = (
                select(self.model)
                .outerjoin(self.model.analize_payments_assoc)
                .outerjoin(self.model.used_promocodes)
                .where(
                    or_(
                        UserAnalizePayment.is_active == True,
                        UserPromocode.is_active == True,
                    )
                )
                .options(
                    selectinload(self.model.analize_payments_assoc).selectinload(
                        self.model.analize_payments_assoc.property.mapper.class_.analize_payment
                    ),
                    selectinload(self.model.used_promocodes),
                )
            )
            result = await self._session.execute(query)
            return result.scalars().unique().all()
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при получении пользователей с платежами или промокодами: {e}"
            )
            raise

    async def get_users_without_payments(self) -> list[User]:
        """
        Получить всех пользователей, у которых нет активных записей в UserAnalizePayment и UserPromocode.
        """
        try:
            subquery = (
                select(UserAnalizePayment.user_id)
                .where(UserAnalizePayment.is_active == True)
                .union(
                    select(UserPromocode.user_id).where(UserPromocode.is_active == True)
                )
            )
            query = select(self.model).where(not_(self.model.id.in_(subquery)))
            result = await self._session.execute(query)
            return result.scalars().unique().all()
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при получении пользователей без платежей и промокодов: {e}"
            )
            raise

    async def get_users_with_payments(self) -> list[User]:
        """
        Получить всех пользователей, у которых есть записи в UserAnalizePayment,
        с подгруженными объектами UserAnalizePayment и AnalizePayment.
        """
        try:
            query = (
                select(self.model)
                .join(self.model.analize_payments_assoc)
                .options(
                    selectinload(self.model.analize_payments_assoc).selectinload(
                        self.model.analize_payments_assoc.property.mapper.class_.analize_payment
                    )
                )
            )
            result = await self._session.execute(query)
            return result.scalars().unique().all()
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении пользователей с платежами: {e}")
            raise

    async def get_total_analiz_balance(self, user_id: int, service_type: str) -> Optional[int]:
        """
        Calculates the total balance for a specific service type for a user
        from active UserPromocodeService and UserAnalizePayment records.
        Returns None if any active record has a None balance (indicating unlimited balance).
        """
        try:
            # Check for any None balance in active UserPromocodeService for the given service type
            promo_service_none_query = (
                select(UserPromocodeService)
                .join(
                    UserPromocode,
                    UserPromocode.id == UserPromocodeService.user_promocode_id,
                )
                .where(
                    UserPromocode.user_id == user_id,
                    UserPromocode.is_active == True,
                    UserPromocodeService.service_type == service_type,  # Передаём объект перечисления
                    UserPromocodeService.remaining_quantity.is_(None),
                )
            )
            promo_service_none_result = await self._session.execute(promo_service_none_query)
            if promo_service_none_result.scalar_one_or_none():
                logger.info(
                    f"User {user_id} has unlimited balance for service '{service_type.value}' in UserPromocodeService"
                )
                return None

            # Check for any None balance in active UserAnalizePayment for the given service type
            payment_none_query = select(UserAnalizePayment).where(
                UserAnalizePayment.user_id == user_id,
                UserAnalizePayment.is_active == True,
                UserAnalizePayment.current_analize_balance.is_(None),
            )
            payment_none_result = await self._session.execute(payment_none_query)
            if payment_none_result.scalar_one_or_none():
                logger.info(
                    f"User {user_id} has unlimited balance for service '{service_type}' in UserAnalizePayment"
                )
                return None

            # Get sum of balances from active UserPromocodeService for the given service type
            promo_service_query = (
                select(func.sum(UserPromocodeService.remaining_quantity))
                .join(
                    UserPromocode,
                    UserPromocode.id == UserPromocodeService.user_promocode_id,
                )
                .where(
                    UserPromocode.user_id == user_id,
                    UserPromocode.is_active == True,
                    UserPromocodeService.service_type == service_type,  # Передаём объект перечисления
                )
            )
            promo_service_result = await self._session.execute(promo_service_query)
            promo_service_balance = promo_service_result.scalar() or 0
            # Get sum of balances from active UserAnalizePayment for the given service type
            payment_query = select(
                func.sum(UserAnalizePayment.current_analize_balance)
            ).where(
                UserAnalizePayment.user_id == user_id,
                UserAnalizePayment.is_active == True,
            )
            payment_result = await self._session.execute(payment_query)
            payment_balance = payment_result.scalar() or 0

            # Calculate total balance
            total_balance = promo_service_balance + payment_balance
            logger.info(f"Total balance for service '{service_type}' for user {user_id}: {total_balance}")
            return total_balance
        except SQLAlchemyError as e:
            logger.error(
                f"Error calculating total balance for service '{service_type}' for user {user_id}: {e}"
            )
            raise

    async def decrease_analiz_balance(self, user_id: int) -> bool:
        """
        Decreases analiz_balance by 1 from the oldest active UserPromocodeService or UserAnalizePayment.
        Returns True if balance was decreased successfully, False otherwise.
        """
        try:
            # Find the oldest active UserPromocodeService with remaining_quantity > 0
            promo_service_query = (
                select(UserPromocodeService)
                .join(
                    UserPromocode,
                    UserPromocode.id == UserPromocodeService.user_promocode_id,
                )
                .where(
                    UserPromocode.user_id == user_id,
                    UserPromocode.is_active == True,
                    UserPromocodeService.remaining_quantity > 0,
                )
                .order_by(UserPromocode.created_at.asc())
            )
            promo_service_result = await self._session.execute(promo_service_query)
            promo_service = promo_service_result.scalar_one_or_none()

            if promo_service:
                # Decrease balance in UserPromocodeService
                promo_service.remaining_quantity -= 1
                if promo_service.remaining_quantity == 0:
                    promo_service.is_active = False
                await self._session.commit()
                logger.info(
                    f"Decreased balance for user {user_id} from UserPromocodeService ID {promo_service.id}"
                )
                return True

            # Find the oldest active UserAnalizePayment with current_analize_balance > 0
            payment_query = (
                select(UserAnalizePayment)
                .where(
                    UserAnalizePayment.user_id == user_id,
                    UserAnalizePayment.is_active == True,
                    UserAnalizePayment.current_analize_balance > 0,
                )
                .order_by(UserAnalizePayment.created_at.asc())
            )
            payment_result = await self._session.execute(payment_query)
            payment = payment_result.scalar_one_or_none()

            if payment:
                # Decrease balance in UserAnalizePayment
                payment.current_analize_balance -= 1
                if payment.current_analize_balance == 0:
                    payment.is_active = False
                await self._session.commit()
                logger.info(
                    f"Decreased balance for user {user_id} from UserAnalizePayment ID {payment.id}"
                )
                return True

            # No active records with balance > 0
            logger.info(f"No active records with balance > 0 for user {user_id}")
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error decreasing analiz_balance for user {user_id}: {e}")
            await self._session.rollback()
            return False

    async def check_expired_records(self, user_id: int) -> bool:
        """
        Checks if any UserPromocode or UserAnalizePayment records for the user have expired based on duration_days.
        Marks expired records as inactive (is_active = False).
        Returns True if any records were marked as expired, False otherwise.
        """
        try:
            current_time = datetime.now(timezone.utc)
            any_expired = False

            # Check UserPromocode records
            promo_query = (
                select(UserPromocode, Promocode.duration_days)
                .join(Promocode, UserPromocode.promocode_id == Promocode.id)
                .where(
                    UserPromocode.user_id == user_id,
                    UserPromocode.is_active == True,
                    Promocode.duration_days.isnot(None),
                )
            )
            promo_result = await self._session.execute(promo_query)
            promo_records = promo_result.all()

            for user_promo, duration_days in promo_records:
                expiration_date = user_promo.created_at + timedelta(days=duration_days)
                if expiration_date.tzinfo is None:
                    expiration_date = expiration_date.replace(tzinfo=timezone.utc)
                if current_time > expiration_date:
                    user_promo.is_active = False
                    any_expired = True
                    logger.info(
                        f"Deactivated expired UserPromocode ID {user_promo.id} for user {user_id}"
                    )

            # Check UserAnalizePayment records
            payment_query = (
                select(UserAnalizePayment, AnalizePayment.duration_days)
                .join(
                    AnalizePayment,
                    UserAnalizePayment.analize_payment_id == AnalizePayment.id,
                )
                .where(
                    UserAnalizePayment.user_id == user_id,
                    UserAnalizePayment.is_active == True,
                    AnalizePayment.duration_days.isnot(None),
                )
            )
            payment_result = await self._session.execute(payment_query)
            payment_records = payment_result.all()

            for user_payment, duration_days in payment_records:
                expiration_date = user_payment.created_at + timedelta(
                    days=duration_days
                )
                if expiration_date.tzinfo is None:
                    expiration_date = expiration_date.replace(tzinfo=timezone.utc)
                if current_time > expiration_date:
                    user_payment.is_active = False
                    any_expired = True
                    logger.info(
                        f"Deactivated expired UserAnalizePayment ID {user_payment.id} for user {user_id}"
                    )

            if any_expired:
                await self._session.commit()
                logger.info(f"Expired records updated for user {user_id}")
            else:
                logger.info(f"No expired records found for user {user_id}")

            return any_expired
        except SQLAlchemyError as e:
            logger.error(f"Error checking expired records for user {user_id}: {e}")
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

    async def get_all_unique_player_names(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[str]:
        """
        Получает все уникальные имена игроков из записей детального анализа с необязательной фильтрацией по дате.
        """
        try:
            query = select(func.distinct(self.model.player_name))
            if start_date or end_date:
                if start_date and end_date:
                    query = query.where(
                        self.model.created_at.between(start_date, end_date)
                    )
                elif start_date:
                    query = query.where(self.model.created_at >= start_date)
                else:
                    query = query.where(self.model.created_at <= end_date)

            result = await self._session.execute(query)
            player_names = [row[0] for row in result.fetchall()]
            logger.info(f"Загружено {len(player_names)} уникальных имен игроков")
            return player_names
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при загрузке уникальных имен игроков: {e}")
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
        Получает все активные промокоды с подгруженными услугами.
        """
        try:
            query = (
                select(self.model)
                .where(self.model.is_active == True)
                .options(
                    selectinload(self.model.services)
                )  # Явная загрузка связанных данных
            )
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
        Активирует промокод для пользователя (добавляет запись в user_promocode, увеличивает activate_count и создает записи в user_promocode_service).
        """
        try:
            # Находим промокод по коду
            promocode = await self.find_by_code(code)
            if not promocode:
                return False

            # Проверяем, существует ли пользователь
            user = await self._session.get(User, user_id)
            if not user:
                return False  # Не создавать нового пользователя

            # Добавляем запись о том, что пользователь активировал промокод
            user_promo = UserPromocode(
                user_id=user_id,
                promocode_id=promocode.id,
            )
            self._session.add(user_promo)

            # Создаём записи в UserPromocodeService для каждой услуги, связанной с промокодом
            for service in promocode.services:
                user_promo_service = UserPromocodeService(
                    user_promocode=user_promo,
                    service_type=service.service_type,
                    remaining_quantity=service.quantity,
                )
                self._session.add(user_promo_service)

            # Увеличиваем счётчик активаций промокода
            promocode.activate_count = (promocode.activate_count or 0) + 1

            # Сохраняем изменения
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
