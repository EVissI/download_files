from loguru import logger
import pytz
import codecs
import secrets
from bot.config import settings
from bot.db.base import BaseDAO
from bot.db.models import (
    Broadcast,
    BroadcastStatus,
    BroadcastUser,
    ContentCardActivationLink,
    ContentCardActivationLinkStatus,
    ContentCard,
    ContentCardFolder,
    ContentCardFolderItem,
    ContentCardFolderLink,
    ContentCardPool,
    MatchAnalysis,
    MatchAnalysisActivationLink,
    MatchAnalysisActivationLinkStatus,
    MatchAnalysisFolder,
    MatchAnalysisFolderItem,
    MatchAnalysisFolderLink,
    MessagesTexts,
    ServiceType,
    User,
    Analysis,
    DetailedAnalysis,
    Promocode,
    PromocodeType,
    UserAnalizePayment,
    UserAnalizePaymentService,
    UserContentCard,
    UserMatchAnalysis,
    UserGroup,
    UserInGroup,
    UserPromocode,
    AnalizePayment,
    UserPromocodeService,
    AnalizePaymentServiceQuantity,
    PromocodeServiceQuantity,
    MessageForNew,
    HintViewerWebUpload,
    HintViewerWebUploadStatus,
    HintWebFolder,
    HintWebFolderItem,
    WebUser,
)
from sqlalchemy import String, cast, delete, func, insert, literal, not_, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.orm import load_only, selectinload
from datetime import datetime, timedelta, timezone
from typing import Optional, List


class AnalizePaymentServiceQuantityDAO(BaseDAO[AnalizePaymentServiceQuantity]):
    model = AnalizePaymentServiceQuantity


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

    async def get_total_balance_dict(self, user_id: int) -> dict[str, Optional[int]]:
        """
        Возвращает общий баланс для всех типов услуг в формате словаря.
        Если для какого-либо типа услуг баланс неограничен, значение будет None.
        """
        try:
            balance_dict = {}
            service_types = [
                ServiceType.MATCH,
                ServiceType.MONEYGAME,
                ServiceType.SHORT_BOARD,
                ServiceType.HINTS,
                ServiceType.POKAZ,
                ServiceType.COMMENTS,
                ServiceType.SCRINSHOT,
            ]

            for service_type in service_types:
                # Передаём объект перечисления, а не строку
                balance = await self.get_total_analiz_balance(user_id, service_type)
                balance_dict[service_type.name] = balance

            return balance_dict
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при получении общего баланса для пользователя {user_id}: {e}"
            )
            raise

    async def update_admin_insert_name(
        self, user_id: int, admin_insert_name: str
    ) -> Optional[User]:
        """
        Обновляет поле admin_insert_name для пользователя с заданным user_id.
        Возвращает обновлённый объект User или None, если пользователь не найден или при ошибке.
        """
        try:
            user = await self._session.get(self.model, user_id)
            if not user:
                logger.warning(
                    f"User with id {user_id} not found for admin_insert_name update"
                )
                return None

            user.admin_insert_name = admin_insert_name
            await self._session.commit()
            # Обновляем объект из сессии, чтобы вернуть актуальные данные
            await self._session.refresh(user)
            logger.info(
                f"Updated admin_insert_name for user {user_id} -> {admin_insert_name}"
            )
            return user
        except SQLAlchemyError as e:
            logger.error(f"Error updating admin_insert_name for user {user_id}: {e}")
            await self._session.rollback()
            return None

    async def get_total_analiz_balance(
        self, user_id: int, service_type: ServiceType
    ) -> Optional[int]:
        """
        Calculates the total balance for a specific service type for a user
        from active UserPromocodeService and UserAnalizePaymentService records.
        Returns None if any active record has a None balance (indicating unlimited balance).
        """
        try:
            # Преобразуем объект перечисления в значение для ENUM
            service_type_value = service_type.name

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
                    UserPromocodeService.service_type
                    == service_type_value,  # Передаем значение ENUM
                    UserPromocodeService.remaining_quantity.is_(None),
                )
            )
            promo_service_none_result = await self._session.execute(
                promo_service_none_query
            )
            if promo_service_none_result.scalar_one_or_none():
                logger.info(
                    f"User {user_id} has unlimited balance for service '{service_type_value}' in UserPromocodeService"
                )
                return None

            # Check for any None balance in active UserAnalizePaymentService for the given service type
            payment_service_none_query = (
                select(UserAnalizePaymentService)
                .join(
                    UserAnalizePayment,
                    UserAnalizePayment.id
                    == UserAnalizePaymentService.user_analize_payment_id,
                )
                .where(
                    UserAnalizePayment.user_id == user_id,
                    UserAnalizePayment.is_active == True,
                    UserAnalizePaymentService.service_type
                    == service_type_value,  # Передаем значение ENUM
                    UserAnalizePaymentService.remaining_quantity.is_(None),
                )
            )
            payment_service_none_result = await self._session.execute(
                payment_service_none_query
            )
            if payment_service_none_result.scalar_one_or_none():
                logger.info(
                    f"User {user_id} has unlimited balance for service '{service_type_value}' in UserAnalizePaymentService"
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
                    UserPromocodeService.service_type
                    == service_type_value,  # Передаем значение ENUM
                )
            )
            promo_service_result = await self._session.execute(promo_service_query)
            promo_service_balance = promo_service_result.scalar() or 0

            # Get sum of balances from active UserAnalizePaymentService for the given service type
            payment_service_query = (
                select(func.sum(UserAnalizePaymentService.remaining_quantity))
                .join(
                    UserAnalizePayment,
                    UserAnalizePayment.id
                    == UserAnalizePaymentService.user_analize_payment_id,
                )
                .where(
                    UserAnalizePayment.user_id == user_id,
                    UserAnalizePayment.is_active == True,
                    UserAnalizePaymentService.service_type
                    == service_type_value,  # Передаем значение ENUM
                )
            )
            payment_service_result = await self._session.execute(payment_service_query)
            payment_service_balance = payment_service_result.scalar() or 0

            # Calculate total balance
            total_balance = promo_service_balance + payment_service_balance
            logger.info(
                f"Total balance for service '{service_type_value}' for user {user_id}: {total_balance}"
            )
            return total_balance
        except SQLAlchemyError as e:
            logger.error(
                f"Error calculating total balance for service '{service_type.name}' for user {user_id}: {e}"
            )
            raise

    async def decrease_analiz_balance(self, user_id: int, service_type: str) -> bool:
        """
        Decreases analiz_balance by 1 from the oldest active UserPromocodeService or UserAnalizePaymentService.
        Returns True if balance was decreased successfully or if remaining_quantity is None, False otherwise.
        """
        try:
            # Find the oldest active UserPromocodeService with remaining_quantity > 0 or NULL
            promo_service_query = (
                select(UserPromocodeService)
                .join(
                    UserPromocode,
                    UserPromocode.id == UserPromocodeService.user_promocode_id,
                )
                .where(
                    UserPromocode.user_id == user_id,
                    UserPromocode.is_active == True,
                    UserPromocodeService.service_type == service_type,
                    (UserPromocodeService.remaining_quantity > 0)
                    | (UserPromocodeService.remaining_quantity.is_(None)),
                )
                .order_by(UserPromocode.created_at.asc())
                .limit(1)
            )
            promo_service_result = await self._session.execute(promo_service_query)
            promo_service = promo_service_result.scalar()

            if promo_service:
                if promo_service.remaining_quantity is None:
                    logger.info(
                        f"Found UserPromocodeService ID {promo_service.id} with NULL remaining_quantity for user {user_id}"
                    )
                    return True
                # Decrease balance if remaining_quantity > 0
                promo_service.remaining_quantity -= 1
                if promo_service.remaining_quantity == 0:
                    promo_service.is_active = False
                logger.info(
                    f"Decreased balance for user {user_id} from UserPromocodeService ID {promo_service.id}"
                )
                return True

            # Find the oldest active UserAnalizePaymentService with remaining_quantity > 0 or NULL
            payment_service_query = (
                select(UserAnalizePaymentService)
                .join(
                    UserAnalizePayment,
                    UserAnalizePayment.id
                    == UserAnalizePaymentService.user_analize_payment_id,
                )
                .where(
                    UserAnalizePayment.user_id == user_id,
                    UserAnalizePayment.is_active == True,
                    UserAnalizePaymentService.service_type == service_type,
                    (UserAnalizePaymentService.remaining_quantity > 0)
                    | (UserAnalizePaymentService.remaining_quantity.is_(None)),
                )
                .order_by(UserAnalizePayment.created_at.asc())
                .limit(1)
            )
            payment_service_result = await self._session.execute(payment_service_query)
            payment_service = payment_service_result.scalar()

            if payment_service:
                if payment_service.remaining_quantity is None:
                    logger.info(
                        f"Found UserAnalizePaymentService ID {payment_service.id} with NULL remaining_quantity for user {user_id}"
                    )
                    return True
                # Decrease balance if remaining_quantity > 0
                payment_service.remaining_quantity -= 1
                if payment_service.remaining_quantity == 0:
                    payment_service.is_active = False
                logger.info(
                    f"Decreased balance for user {user_id} from UserAnalizePaymentService ID {payment_service.id}"
                )
                return True

            # No active records with balance > 0 or NULL
            logger.info(
                f"No active records with balance > 0 or NULL for user {user_id}"
            )
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error decreasing analiz_balance for user {user_id}: {e}")
            await self._session.rollback()
            return False

    async def decrease_analiz_balance_batch(
        self, user_id: int, service_type: str, amount: int
    ) -> int:
        """
        Списывает amount единиц баланса за один проход.
        Сначала потребляет из UserPromocodeService (по старейшим), затем из UserAnalizePaymentService.
        Возвращает фактически списанное количество.
        """
        if amount <= 0:
            return 0
        try:
            service_type_value = service_type if isinstance(service_type, str) else service_type.name

            # Получаем все промо-сервисы по порядку
            promo_query = (
                select(UserPromocodeService)
                .join(
                    UserPromocode,
                    UserPromocode.id == UserPromocodeService.user_promocode_id,
                )
                .where(
                    UserPromocode.user_id == user_id,
                    UserPromocode.is_active == True,
                    UserPromocodeService.service_type == service_type_value,
                    (UserPromocodeService.remaining_quantity > 0)
                    | (UserPromocodeService.remaining_quantity.is_(None)),
                )
                .order_by(UserPromocode.created_at.asc())
            )
            promo_result = await self._session.execute(promo_query)
            promo_services = list(promo_result.scalars().all())

            # Получаем все платёжные сервисы по порядку
            payment_query = (
                select(UserAnalizePaymentService)
                .join(
                    UserAnalizePayment,
                    UserAnalizePayment.id
                    == UserAnalizePaymentService.user_analize_payment_id,
                )
                .where(
                    UserAnalizePayment.user_id == user_id,
                    UserAnalizePayment.is_active == True,
                    UserAnalizePaymentService.service_type == service_type_value,
                    (UserAnalizePaymentService.remaining_quantity > 0)
                    | (UserAnalizePaymentService.remaining_quantity.is_(None)),
                )
                .order_by(UserAnalizePayment.created_at.asc())
            )
            payment_result = await self._session.execute(payment_query)
            payment_services = list(payment_result.scalars().all())

            # Объединяем: сначала промо, потом платежи
            all_services = promo_services + payment_services
            remaining_to_deduct = amount
            deducted = 0

            for service in all_services:
                if remaining_to_deduct <= 0:
                    break
                if service.remaining_quantity is None:
                    # Безлимит — списываем всё оставшееся
                    deducted += remaining_to_deduct
                    remaining_to_deduct = 0
                    break
                take = min(service.remaining_quantity, remaining_to_deduct)
                service.remaining_quantity -= take
                remaining_to_deduct -= take
                deducted += take
                if service.remaining_quantity == 0 and hasattr(service, "is_active"):
                    service.is_active = False

            logger.info(
                f"Batch decreased balance for user {user_id}: deducted {deducted} of {amount}"
            )
            return deducted
        except SQLAlchemyError as e:
            logger.error(
                f"Error batch decreasing analiz_balance for user {user_id}: {e}"
            )
            await self._session.rollback()
            return 0

    async def check_expired_records(self, user_id: int) -> list[dict]:
        """
        Checks if any UserPromocode or UserAnalizePayment records for the user have expired based on duration_days.
        Marks expired records as inactive (is_active = False).
        Returns a list of dictionaries containing details of expired records.
        """
        try:
            current_time = datetime.now(timezone.utc)
            expired_records = []

            # Check UserPromocode records
            promo_query = select(UserPromocode).where(
                UserPromocode.user_id == user_id,
                UserPromocode.is_active == True,
                UserPromocode.expires_at.isnot(None),
            )
            promo_result = await self._session.execute(promo_query)
            promo_records = promo_result.scalars().all()

            for user_promo in promo_records:
                expiration_date = user_promo.expires_at
                if expiration_date is None:
                    continue
                if expiration_date.tzinfo is None:
                    expiration_date = expiration_date.replace(tzinfo=timezone.utc)
                if current_time > expiration_date:
                    user_promo.is_active = False
                    expired_records.append(
                        {
                            "type": "UserPromocode",
                            "id": user_promo.id,
                            "expiration_date": expiration_date.isoformat(),
                        }
                    )
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
                    expired_records.append(
                        {
                            "type": "UserAnalizePayment",
                            "id": user_payment.id,
                            "expiration_date": expiration_date.isoformat(),
                        }
                    )
                    logger.info(
                        f"Deactivated expired UserAnalizePayment ID {user_payment.id} for user {user_id}"
                    )

            if expired_records:
                await self._session.commit()
                logger.info(
                    f"Expired records updated for user {user_id}: {len(expired_records)} records"
                )
            else:
                logger.info(f"No expired records found for user {user_id}")

            return expired_records
        except SQLAlchemyError as e:
            logger.error(f"Error checking expired records for user {user_id}: {e}")
            await self._session.rollback()
            return []


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

    async def get_detailed_analyzes_by_user_id(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[DetailedAnalysis]:
        """
        Получает записи детального анализа для конкретного user_id с необязательной фильтрацией по дате.
        """
        try:
            conditions = [self.model.user_id == user_id]
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
                f"Загружено {len(analyses)} записей детального анализа для user_id {user_id}"
            )
            return analyses
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при загрузке записей детального анализа для user_id {user_id}: {e}"
            )
            raise

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

    async def validate_promo_code(self, code: str, user_id: int) -> tuple[bool, str]:
        """
        Проверяет, можно ли активировать промокод для пользователя.
        Возвращает (is_valid, reason_code).
        """
        try:
            query = (
                select(Promocode)
                .where(Promocode.code == code)
            )
            result = await self._session.execute(query)
            promocode = result.scalar_one_or_none()
            if not promocode:
                return False, "not_found"
            if not promocode.is_active:
                return False, "inactive"
            if promocode.max_usage is not None and promocode.activate_count is not None:
                if promocode.activate_count >= promocode.max_usage:
                    return False, "limit_reached"

            query = select(UserPromocode).where(
                UserPromocode.user_id == user_id,
                UserPromocode.promocode_id == promocode.id,
            )
            result = await self._session.execute(query)
            user_promo = result.scalar_one_or_none()
            if user_promo:
                return False, "already_used"

            if promocode.promocode_type == PromocodeType.CARDS:
                cards_to_issue = max(0, promocode.cards_issue_quantity or 0)
                if cards_to_issue <= 0:
                    return False, "cards_quantity_invalid"

                pool = promocode.card_pool or ContentCardPool.CARDS
                if isinstance(pool, str):
                    try:
                        pool = ContentCardPool(pool)
                    except ValueError:
                        pool = ContentCardPool.CARDS

                if pool == ContentCardPool.MATCH_ANALYSIS:
                    all_ma_query = (
                        select(MatchAnalysis.id)
                        .where(MatchAnalysis.is_ready.is_(True))
                        .order_by(MatchAnalysis.id.asc())
                    )
                    all_ma_result = await self._session.execute(all_ma_query)
                    all_ma_ids = [
                        row[0] for row in all_ma_result.all() if row[0] is not None
                    ]
                    if not all_ma_ids:
                        return False, "cards_not_configured"
                    existing_ma_result = await self._session.execute(
                        select(UserMatchAnalysis.match_analysis_id).where(
                            UserMatchAnalysis.user_id == user_id
                        )
                    )
                    existing_ma_ids = {
                        row[0]
                        for row in existing_ma_result.all()
                        if row[0] is not None
                    }
                    available_ma = [
                        mid for mid in all_ma_ids if mid not in existing_ma_ids
                    ]
                    if not available_ma:
                        return False, "no_new_cards"
                else:
                    all_cards_query = (
                        select(ContentCard.id)
                        .where(
                            ContentCard.is_ready.is_(True),
                            ContentCard.card_pool == pool.value,
                        )
                        .order_by(ContentCard.id.asc())
                    )
                    all_cards_result = await self._session.execute(all_cards_query)
                    all_card_ids = [
                        row[0] for row in all_cards_result.all() if row[0] is not None
                    ]
                    if not all_card_ids:
                        return False, "cards_not_configured"

                    existing_card_ids_query = select(
                        UserContentCard.content_card_id
                    ).where(UserContentCard.user_id == user_id)
                    existing_card_ids_result = await self._session.execute(
                        existing_card_ids_query
                    )
                    existing_card_ids = {
                        row[0]
                        for row in existing_card_ids_result.all()
                        if row[0] is not None
                    }
                    available_cards = [
                        card_id
                        for card_id in all_card_ids
                        if card_id not in existing_card_ids
                    ]
                    if not available_cards:
                        return False, "no_new_cards"

            return True, "ok"
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при валидации промокода '{code}': {e}")
            return False, "db_error"

    async def activate_promo_code(self, code: str, user_id: int) -> bool:
        """
        Активирует промокод для пользователя:
        - regular: создаёт балансы в user_promocode_service;
        - cards: привязывает N карточек к пользователю через user_content_cards.
        """
        try:
            # Находим промокод по коду с явной загрузкой связанных данных
            query = (
                select(Promocode)
                .where(Promocode.code == code)
                .options(
                    selectinload(Promocode.services),
                )
            )
            result = await self._session.execute(query)
            promocode = result.scalar_one_or_none()

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
                expires_at=UserPromocode.initial_expires_at(promocode.duration_days),
            )
            self._session.add(user_promo)

            if promocode.promocode_type == PromocodeType.CARDS:
                cards_to_issue = max(0, promocode.cards_issue_quantity or 0)
                pool = promocode.card_pool or ContentCardPool.CARDS
                if isinstance(pool, str):
                    try:
                        pool = ContentCardPool(pool)
                    except ValueError:
                        pool = ContentCardPool.CARDS

                if cards_to_issue > 0 and pool == ContentCardPool.MATCH_ANALYSIS:
                    all_ma_query = (
                        select(MatchAnalysis.id)
                        .where(MatchAnalysis.is_ready.is_(True))
                        .order_by(MatchAnalysis.id.asc())
                    )
                    all_ma_result = await self._session.execute(all_ma_query)
                    all_ma_ids = [
                        row[0] for row in all_ma_result.all() if row[0] is not None
                    ]
                    existing_ma_result = await self._session.execute(
                        select(UserMatchAnalysis.match_analysis_id).where(
                            UserMatchAnalysis.user_id == user_id
                        )
                    )
                    existing_ma_ids = {
                        row[0]
                        for row in existing_ma_result.all()
                        if row[0] is not None
                    }
                    issued_now = 0
                    for mid in all_ma_ids:
                        if mid in existing_ma_ids:
                            continue
                        self._session.add(
                            UserMatchAnalysis(
                                user_id=user_id,
                                match_analysis_id=mid,
                            )
                        )
                        existing_ma_ids.add(mid)
                        issued_now += 1
                        if issued_now >= cards_to_issue:
                            break
                    user_promo.issued_cards_count = issued_now
                elif cards_to_issue > 0:
                    all_cards_query = (
                        select(ContentCard.id)
                        .where(
                            ContentCard.is_ready.is_(True),
                            ContentCard.card_pool == pool.value,
                        )
                        .order_by(ContentCard.id.asc())
                    )
                    all_cards_result = await self._session.execute(all_cards_query)
                    all_card_ids = [
                        row[0] for row in all_cards_result.all() if row[0] is not None
                    ]

                    # Исключаем уже выданные пользователю карточки и сохраняем общий порядок.
                    existing_card_ids_query = select(
                        UserContentCard.content_card_id
                    ).where(UserContentCard.user_id == user_id)
                    existing_card_ids_result = await self._session.execute(
                        existing_card_ids_query
                    )
                    existing_card_ids = {
                        row[0]
                        for row in existing_card_ids_result.all()
                        if row[0] is not None
                    }

                    issued_now = 0
                    for card_id in all_card_ids:
                        if card_id in existing_card_ids:
                            continue
                        self._session.add(
                            UserContentCard(
                                user_id=user_id,
                                content_card_id=card_id,
                                source_user_promocode=user_promo,
                            )
                        )
                        existing_card_ids.add(card_id)
                        issued_now += 1
                        if issued_now >= cards_to_issue:
                            break
                    user_promo.issued_cards_count = issued_now
            else:
                # Создаём записи в UserPromocodeService для каждой услуги regular-промокода.
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

    async def find_one_or_none_by_id_with_services(
        self, payment_id: int
    ) -> Optional[AnalizePayment]:
        """
        Находит пакет услуг по ID с подгруженными связанными сервисами.
        """
        try:
            query = (
                select(self.model)
                .where(self.model.id == payment_id)
                .options(
                    selectinload(
                        self.model.services
                    )  # Явная загрузка связанных сервисов
                )
            )
            result = await self._session.execute(query)
            payment = result.scalars().one_or_none()
            if payment:
                logger.info(
                    f"Загружен пакет услуг с ID {payment_id} и {len(payment.services)} связанными сервисами"
                )
            else:
                logger.warning(f"Пакет услуг с ID {payment_id} не найден")
            return payment
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при загрузке пакета услуг с ID {payment_id}: {e}")
            raise

    async def get_active_payments(self) -> List[AnalizePayment]:
        """
        Получает все активные пакеты услуг с подгруженными связанными услугами.
        """
        try:
            query = (
                select(self.model)
                .where(self.model.is_active == True)
                .options(
                    selectinload(self.model.services)  # Явная загрузка связанных услуг
                )
            )
            result = await self._session.execute(query)
            payments = result.scalars().all()
            logger.info(f"Загружено {len(payments)} активных пакетов услуг")
            return payments
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при загрузке активных пакетов услуг: {e}")
            raise

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


class ContentCardDAO(BaseDAO[ContentCard]):
    model = ContentCard

    async def find_one_by_file_name(self, file_name: str) -> ContentCard | None:
        """Первая карточка с данным file_name (в БД нет unique на поле)."""
        try:
            query = (
                select(self.model)
                .where(self.model.file_name == file_name)
                .limit(1)
            )
            result = await self._session.execute(query)
            return result.scalars().first()
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при поиске ContentCard по file_name={file_name!r}: {e}"
            )
            raise

    async def find_for_user_by_file_name(
        self, user_id: int, file_name: str
    ) -> ContentCard | None:
        """Карточка с данным file_name, связанная с пользователем (для upsert)."""
        try:
            query = (
                select(self.model)
                .join(
                    UserContentCard,
                    UserContentCard.content_card_id == self.model.id,
                )
                .where(
                    UserContentCard.user_id == user_id,
                    self.model.file_name == file_name,
                )
                .limit(1)
            )
            result = await self._session.execute(query)
            return result.scalars().first()
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при поиске ContentCard для user_id={user_id} "
                f"file_name={file_name!r}: {e}"
            )
            raise

    async def find_one_by_id_with_users(self, card_id: int) -> ContentCard | None:
        """Карточка по id со связями user_content_cards (без вложенного user)."""
        try:
            query = (
                select(self.model)
                .where(self.model.id == card_id)
                .options(selectinload(self.model.users))
            )
            result = await self._session.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при загрузке ContentCard id={card_id} с users: {e}"
            )
            raise


class UserContentCardDAO(BaseDAO[UserContentCard]):
    model = UserContentCard

    async def get_all_with_content_card(self) -> list[UserContentCard]:
        """Все связи пользователь–карточка с подгруженным ContentCard."""
        try:
            query = select(self.model).options(selectinload(self.model.content_card))
            result = await self._session.execute(query)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении UserContentCard с карточками: {e}")
            raise

    async def get_all_by_user(self, user_id: int) -> list[UserContentCard]:
        """Связи пользователя с подгруженными карточками."""
        try:
            query = (
                select(self.model)
                .where(self.model.user_id == user_id)
                .options(
                    selectinload(self.model.content_card).load_only(
                        ContentCard.id,
                        ContentCard.card_pool,
                        ContentCard.labels,
                        ContentCard.notes,
                        ContentCard.is_ready,
                    )
                )
            )
            result = await self._session.execute(query)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при получении UserContentCard для user_id={user_id}: {e}"
            )
            raise

    async def find_one_by_user_and_card(
        self, user_id: int, content_card_id: int
    ) -> UserContentCard | None:
        """Одна связь по паре (user_id, content_card_id), удобно перед созданием."""
        try:
            query = select(self.model).where(
                self.model.user_id == user_id,
                self.model.content_card_id == content_card_id,
            )
            result = await self._session.execute(query)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при поиске UserContentCard user_id={user_id} "
                f"content_card_id={content_card_id}: {e}"
            )
            raise


class ContentCardActivationLinkDAO(BaseDAO[ContentCardActivationLink]):
    model = ContentCardActivationLink

    @staticmethod
    def _normalize_card_ids(card_ids: list[int] | None) -> list[int]:
        seen: set[int] = set()
        normalized: list[int] = []
        for raw_id in card_ids or []:
            try:
                card_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if card_id < 1 or card_id in seen:
                continue
            seen.add(card_id)
            normalized.append(card_id)
        return normalized

    async def create_link(self, card_ids: list[int]) -> ContentCardActivationLink:
        normalized_card_ids = self._normalize_card_ids(card_ids)
        if not normalized_card_ids:
            raise ValueError("Нужно передать хотя бы один корректный content_card_id")

        activation_link = ContentCardActivationLink(
            link=secrets.token_urlsafe(24),
            status=ContentCardActivationLinkStatus.UNACTIVATE,
            card_ids=normalized_card_ids,
        )
        self._session.add(activation_link)
        await self._session.flush()
        return activation_link

    async def find_one_by_link(self, link_value: str) -> ContentCardActivationLink | None:
        query = (
            select(self.model)
            .where(self.model.link == str(link_value or "").strip())
            .limit(1)
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def activate_link_and_issue_cards(
        self, link_value: str, user_id: int
    ) -> dict[str, int | str]:
        cleaned_link = str(link_value or "").strip()
        if not cleaned_link:
            return {"ok": 0, "reason": "invalid_link"}

        link_query = (
            select(self.model)
            .where(self.model.link == cleaned_link)
            .with_for_update()
            .limit(1)
        )
        link_result = await self._session.execute(link_query)
        activation_link = link_result.scalar_one_or_none()
        if not activation_link:
            return {"ok": 0, "reason": "not_found"}

        if activation_link.status == ContentCardActivationLinkStatus.ACTIVATE:
            return {"ok": 0, "reason": "already_activated"}

        user = await self._session.get(User, user_id)
        if not user:
            return {"ok": 0, "reason": "user_not_found"}

        requested_card_ids = self._normalize_card_ids(activation_link.card_ids)
        if not requested_card_ids:
            return {"ok": 0, "reason": "no_cards"}

        existing_cards_result = await self._session.execute(
            select(ContentCard.id).where(ContentCard.id.in_(requested_card_ids))
        )
        existing_card_ids = {
            int(card_id)
            for card_id in existing_cards_result.scalars().all()
            if card_id is not None
        }
        valid_card_ids = [card_id for card_id in requested_card_ids if card_id in existing_card_ids]
        if not valid_card_ids:
            return {"ok": 0, "reason": "cards_not_found"}

        existing_user_links_result = await self._session.execute(
            select(UserContentCard.content_card_id).where(
                UserContentCard.user_id == user_id,
                UserContentCard.content_card_id.in_(valid_card_ids),
            )
        )
        already_has_ids = {
            int(card_id)
            for card_id in existing_user_links_result.scalars().all()
            if card_id is not None
        }
        to_issue_ids = [card_id for card_id in valid_card_ids if card_id not in already_has_ids]
        for card_id in to_issue_ids:
            self._session.add(UserContentCard(user_id=user_id, content_card_id=card_id))

        activation_link.status = ContentCardActivationLinkStatus.ACTIVATE
        activation_link.activated_by_user_id = user_id
        activation_link.activated_at = datetime.now(timezone.utc)

        await self._session.flush()
        return {
            "ok": 1,
            "reason": "ok",
            "issued_count": len(to_issue_ids),
            "already_had_count": len(already_has_ids),
            "total_count": len(valid_card_ids),
            "link_id": int(activation_link.id),
        }


class ContentCardFolderDAO(BaseDAO[ContentCardFolder]):
    """
    DAO для управления деревом папок карточек.
    Папки образуют иерархию (parent_id → children); карточки привязаны через ContentCardFolderItem.
    """

    model = ContentCardFolder

    # ------------------------------------------------------------------
    # Базовые операции с папками
    # ------------------------------------------------------------------

    async def get_all_folders(self) -> list[ContentCardFolder]:
        result = await self._session.execute(
            select(ContentCardFolder).order_by(
                ContentCardFolder.parent_id.asc().nullsfirst(),
                ContentCardFolder.sort_order.asc(),
                ContentCardFolder.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_folder_by_id(self, folder_id: int) -> ContentCardFolder | None:
        result = await self._session.execute(
            select(ContentCardFolder).where(ContentCardFolder.id == folder_id)
        )
        return result.scalar_one_or_none()

    async def create_folder(
        self,
        name: str,
        parent_id: int | None,
        sort_order: int,
        admin_id: int | None,
        folder_pool: ContentCardPool | None = None,
    ) -> ContentCardFolder:
        folder = ContentCardFolder(
            name=name[:255],
            parent_id=parent_id,
            sort_order=sort_order,
            created_by_admin_id=admin_id,
            folder_pool=folder_pool or ContentCardPool.CARDS,
        )
        self._session.add(folder)
        await self._session.flush()
        return folder

    async def update_folder(
        self,
        folder_id: int,
        name: str | None = None,
        sort_order: int | None = None,
    ) -> ContentCardFolder | None:
        folder = await self.get_folder_by_id(folder_id)
        if not folder:
            return None
        if name is not None:
            folder.name = name[:255]
        if sort_order is not None:
            folder.sort_order = sort_order
        folder.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return folder

    async def move_folder(
        self,
        folder_id: int,
        new_parent_id: int | None,
        new_sort_order: int,
    ) -> ContentCardFolder | None:
        """Перенести папку в другого родителя; защита от циклов."""
        folder = await self.get_folder_by_id(folder_id)
        if not folder:
            return None
        if new_parent_id is not None:
            # Проверяем, что new_parent_id не является потомком folder_id
            if await self._is_descendant(folder_id, new_parent_id):
                raise ValueError(
                    f"Нельзя переместить папку {folder_id} внутрь своего потомка {new_parent_id}"
                )
        folder.parent_id = new_parent_id
        folder.sort_order = new_sort_order
        folder.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return folder

    async def _collect_descendant_folder_ids(self, root_folder_id: int) -> list[int]:
        """BFS: все id вложенных папок (без root_folder_id)."""
        all_folders = await self.get_all_folders()
        children_map: dict[int | None, list[int]] = {}
        for f in all_folders:
            children_map.setdefault(f.parent_id, []).append(f.id)

        result: list[int] = []
        queue: list[int] = list(children_map.get(root_folder_id, []))
        while queue:
            current = queue.pop(0)
            result.append(current)
            queue.extend(children_map.get(current, []))
        return result

    async def delete_folder(self, folder_id: int) -> bool:
        """
        Удалить папку и все вложенные подпапки рекурсивно.
        Связи карточек и ссылки на папки удаляются каскадно (FK ON DELETE CASCADE).
        """
        folder = await self.get_folder_by_id(folder_id)
        if not folder:
            return False

        descendant_ids = await self._collect_descendant_folder_ids(folder_id)
        ids_to_delete = descendant_ids + [folder_id]
        await self._session.execute(
            delete(ContentCardFolder).where(ContentCardFolder.id.in_(ids_to_delete))
        )
        await self._session.flush()
        return True

    # ------------------------------------------------------------------
    # Проверка дерева (anti-cycle)
    # ------------------------------------------------------------------

    async def _is_descendant(self, ancestor_id: int, candidate_id: int) -> bool:
        """
        Возвращает True, если candidate_id является потомком ancestor_id.
        BFS по parent_id вверх (ancestor_id — вершина, проверяем путь от candidate).
        """
        visited: set[int] = set()
        current_id: int | None = candidate_id
        while current_id is not None:
            if current_id in visited:
                break  # Цикл в уже существующем дереве — прерываем
            visited.add(current_id)
            if current_id == ancestor_id:
                return True
            result = await self._session.execute(
                select(ContentCardFolder.parent_id).where(ContentCardFolder.id == current_id)
            )
            row = result.scalar_one_or_none()
            current_id = row
        return False

    # ------------------------------------------------------------------
    # Резолв карточек по ветке (BFS, дедупликация)
    # ------------------------------------------------------------------

    async def collect_card_ids_for_folder_tree(
        self, root_folder_id: int, include_children: bool = True
    ) -> list[int]:
        """
        Собрать id карточек из папки root_folder_id и (если include_children) всех потомков.
        Возвращает дедуплицированный список; порядок стабильный (BFS, sort_order).
        """
        all_folders = await self.get_all_folders()
        # Построить словарь parent_id → [child_id] для BFS
        children_map: dict[int | None, list[int]] = {}
        for f in all_folders:
            children_map.setdefault(f.parent_id, []).append(f.id)

        folder_ids_to_process: list[int] = [root_folder_id]
        if include_children:
            queue: list[int] = [root_folder_id]
            while queue:
                current = queue.pop(0)
                for child_id in children_map.get(current, []):
                    if child_id not in folder_ids_to_process:
                        folder_ids_to_process.append(child_id)
                        queue.append(child_id)

        result = await self._session.execute(
            select(ContentCardFolderItem.content_card_id)
            .where(ContentCardFolderItem.folder_id.in_(folder_ids_to_process))
            .order_by(
                ContentCardFolderItem.folder_id.asc(),
                ContentCardFolderItem.sort_order.asc(),
                ContentCardFolderItem.id.asc(),
            )
        )
        seen: set[int] = set()
        deduped: list[int] = []
        for cid in result.scalars().all():
            if cid not in seen:
                seen.add(cid)
                deduped.append(cid)
        return deduped

    # ------------------------------------------------------------------
    # Управление карточками внутри папки
    # ------------------------------------------------------------------

    async def get_folder_items(self, folder_id: int) -> list[ContentCardFolderItem]:
        result = await self._session.execute(
            select(ContentCardFolderItem)
            .where(ContentCardFolderItem.folder_id == folder_id)
            .order_by(ContentCardFolderItem.sort_order.asc(), ContentCardFolderItem.id.asc())
        )
        return list(result.scalars().all())

    async def add_card_to_folder(
        self, folder_id: int, content_card_id: int, sort_order: int = 0
    ) -> ContentCardFolderItem | None:
        """Добавить карточку в папку. Если уже есть — вернуть None (нет ошибки)."""
        existing = await self._session.execute(
            select(ContentCardFolderItem).where(
                ContentCardFolderItem.folder_id == folder_id,
                ContentCardFolderItem.content_card_id == content_card_id,
            )
        )
        if existing.scalar_one_or_none():
            return None
        item = ContentCardFolderItem(
            folder_id=folder_id,
            content_card_id=content_card_id,
            sort_order=sort_order,
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def remove_card_from_folder(
        self, folder_id: int, content_card_id: int
    ) -> bool:
        result = await self._session.execute(
            select(ContentCardFolderItem).where(
                ContentCardFolderItem.folder_id == folder_id,
                ContentCardFolderItem.content_card_id == content_card_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            return False
        await self._session.delete(item)
        await self._session.flush()
        return True

    async def get_folder_card_ids(self, folder_id: int) -> list[int]:
        """Прямые карточки папки (без подпапок), в порядке sort_order."""
        result = await self._session.execute(
            select(ContentCardFolderItem.content_card_id)
            .where(ContentCardFolderItem.folder_id == folder_id)
            .order_by(
                ContentCardFolderItem.sort_order.asc(),
                ContentCardFolderItem.id.asc(),
            )
        )
        return [int(cid) for cid in result.scalars().all() if cid is not None]

    async def add_cards_to_folder(
        self, folder_id: int, card_ids: list[int]
    ) -> int:
        """Добавить карточки в папку (без дубликатов). Возвращает число новых привязок."""
        existing_ids = set(await self.get_folder_card_ids(folder_id))
        added = 0
        next_order = len(existing_ids)
        for cid in card_ids:
            if cid in existing_ids:
                continue
            self._session.add(
                ContentCardFolderItem(
                    folder_id=folder_id,
                    content_card_id=cid,
                    sort_order=next_order,
                )
            )
            existing_ids.add(cid)
            next_order += 1
            added += 1
        if added:
            await self._session.flush()
        return added

    async def set_folder_items(
        self,
        folder_id: int,
        card_ids_ordered: list[int],
    ) -> None:
        """
        Батч-замена карточек в папке: удалить те, которых нет в card_ids_ordered,
        добавить новые, проставить sort_order.
        """
        existing_res = await self._session.execute(
            select(ContentCardFolderItem).where(ContentCardFolderItem.folder_id == folder_id)
        )
        existing_items = {
            item.content_card_id: item for item in existing_res.scalars().all()
        }
        desired_ids = list(dict.fromkeys(card_ids_ordered))  # дедупликация с сохранением порядка

        for item in existing_items.values():
            if item.content_card_id not in desired_ids:
                await self._session.delete(item)

        for order, cid in enumerate(desired_ids):
            if cid in existing_items:
                existing_items[cid].sort_order = order
            else:
                self._session.add(
                    ContentCardFolderItem(
                        folder_id=folder_id,
                        content_card_id=cid,
                        sort_order=order,
                    )
                )
        await self._session.flush()


class ContentCardFolderLinkDAO(BaseDAO[ContentCardFolderLink]):
    """DAO для многоразовых ссылок на папки дерева."""

    model = ContentCardFolderLink

    async def get_link_for_folder(self, folder_id: int) -> ContentCardFolderLink | None:
        """Найти активную ссылку для папки (первую)."""
        result = await self._session.execute(
            select(ContentCardFolderLink)
            .where(
                ContentCardFolderLink.folder_id == folder_id,
                ContentCardFolderLink.is_active == True,  # noqa: E712
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_link(
        self, folder_id: int, admin_id: int | None
    ) -> ContentCardFolderLink:
        link = ContentCardFolderLink(
            link_token=secrets.token_urlsafe(24),
            folder_id=folder_id,
            is_active=True,
            created_by_admin_id=admin_id,
        )
        self._session.add(link)
        await self._session.flush()
        return link

    async def get_or_create_link(
        self, folder_id: int, admin_id: int | None
    ) -> ContentCardFolderLink:
        existing = await self.get_link_for_folder(folder_id)
        if existing:
            return existing
        return await self.create_link(folder_id, admin_id)

    async def find_by_token(self, token: str) -> ContentCardFolderLink | None:
        result = await self._session.execute(
            select(ContentCardFolderLink)
            .where(
                ContentCardFolderLink.link_token == str(token or "").strip(),
                ContentCardFolderLink.is_active == True,  # noqa: E712
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def deactivate_link(self, link_id: int) -> bool:
        result = await self._session.execute(
            select(ContentCardFolderLink).where(ContentCardFolderLink.id == link_id)
        )
        link = result.scalar_one_or_none()
        if not link:
            return False
        link.is_active = False
        link.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return True


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


class BroadcastDAO(BaseDAO[Broadcast]):
    model = Broadcast

    async def get_unique_content_broadcasts(self) -> List[Broadcast]:
        """
        Получает все рассылки со статусом SENT, выбирая только одну рассылку с уникальным текстом (с наименьшим id).
        """
        try:
            # Подзапрос для получения минимального id для каждого уникального content
            subquery = (
                select(func.min(self.model.id).label("min_id"))
                .where(self.model.status == BroadcastStatus.SENT)
                .group_by(self.model.text)
                .subquery()
            )

            # Основной запрос, который выбирает полные записи Broadcast, где id совпадает с min_id
            query = (
                select(self.model)
                .where(
                    self.model.status == BroadcastStatus.SENT,
                    self.model.id.in_(select(subquery.c.min_id)),
                )
                .order_by(self.model.id)
            )
            result = await self._session.execute(query)
            broadcasts = result.scalars().all()
            logger.info(
                f"Загружено {len(broadcasts)} уникальных рассылок со статусом SENT"
            )
            return broadcasts
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при загрузке уникальных рассылок: {e}")
            raise

    async def get_scheduled_broadcasts(self) -> List[Broadcast]:
        """
        Получает все запланированные рассылки, которые еще не были отправлены.
        """
        try:
            query = select(self.model).where(
                self.model.status == BroadcastStatus.SCHEDULED
            )
            result = await self._session.execute(query)
            broadcasts = result.scalars().all()
            logger.info(f"Загружено {len(broadcasts)} запланированных рассылок")
            return broadcasts
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при загрузке запланированных рассылок: {e}")
            raise

    async def update_status(self, broadcast_id: int, status: BroadcastStatus) -> bool:
        """
        Обновляет статус рассылки по id.
        Возвращает True при успешном обновлении, False при ошибке или если запись не найдена.
        """
        try:
            broadcast = await self._session.get(self.model, broadcast_id)
            if not broadcast:
                logger.warning(
                    f"Broadcast with id {broadcast_id} not found for status update"
                )
                return False

            broadcast.status = status
            await self._session.commit()
            logger.info(f"Broadcast {broadcast_id} status updated to {status}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при обновлении статуса рассылки {broadcast_id}: {e}")
            await self._session.rollback()
            return False

    async def add_recipients_to_broadcast(
        self, broadcast_id: int, user_ids: List[int]
    ) -> bool:
        """
        Добавляет записи в таблицу BroadcastUser, связывая broadcast_id с указанными user_ids.
        Возвращает True при успешном добавлении, False при ошибке или если broadcast_id не существует.
        """
        try:
            # Проверяем, существует ли рассылка
            broadcast = await self._session.get(self.model, broadcast_id)
            if not broadcast:
                logger.warning(f"Broadcast with id {broadcast_id} not found")
                return False

            # Создаем список словарей для массовой вставки
            broadcast_user_entries = [
                {"broadcast_id": broadcast_id, "user_id": user_id}
                for user_id in user_ids
            ]

            # Выполняем массовую вставку в таблицу BroadcastUser
            await self._session.execute(insert(BroadcastUser), broadcast_user_entries)
            logger.info(f"Added {len(user_ids)} recipients to broadcast {broadcast_id}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error adding recipients to broadcast {broadcast_id}: {e}")
            await self._session.rollback()
            return False

    async def get_recipients_for_broadcast(self, broadcast_id: int) -> List[int]:
        """
        Получает список user_id, прикрепленных к указанной рассылке через таблицу BroadcastUser.
        Возвращает пустой список, если рассылка не найдена или у нее нет получателей.
        """
        try:
            # Проверяем, существует ли рассылка
            broadcast = await self._session.get(self.model, broadcast_id)
            if not broadcast:
                logger.warning(f"Broadcast with id {broadcast_id} not found")
                return []

            # Запрашиваем user_id из таблицы BroadcastUser
            query = select(BroadcastUser.user_id).where(
                BroadcastUser.broadcast_id == broadcast_id
            )
            result = await self._session.execute(query)
            user_ids = [row.user_id for row in result.fetchall()]
            logger.info(
                f"Retrieved {len(user_ids)} recipients for broadcast {broadcast_id}"
            )
            return user_ids
        except SQLAlchemyError as e:
            logger.error(
                f"Error retrieving recipients for broadcast {broadcast_id}: {e}"
            )
            return []


class MessageForNewDAO(BaseDAO[MessageForNew]):
    model = MessageForNew

    async def upsert_message_for_new(
        self,
        dispatch_day: str,
        dispatch_time: str,
        text: str,
        lang_code: str = "en",
    ) -> MessageForNew | None:
        """
        Создаёт или обновляет запись MessageForNew по (dispatch_day, lang_code).
        Если запись с такими значениями есть — обновляет поля dispatch_time и text.
        Возвращает созданный/обновлённый объект или None при ошибке.
        """
        try:
            query = select(self.model).where(
                self.model.lang_code == lang_code,
            )
            result = await self._session.execute(query)
            record = result.scalar_one_or_none()

            if record:
                record.dispatch_time = dispatch_time
                record.text = text
                action = "updated"
            else:
                record = self.model(
                    dispatch_day=dispatch_day,
                    dispatch_time=dispatch_time,
                    text=text,
                    lang_code=lang_code,
                )
                self._session.add(record)
                action = "created"
            logger.info(f"MessageForNew {action}: day={dispatch_day}, lang={lang_code}")
            return record
        except SQLAlchemyError as e:
            logger.error(
                f"Error upserting MessageForNew (day={dispatch_day}, lang={lang_code}): {e}"
            )
            await self._session.rollback()
            return None

    async def get_by_lang_code(self, lang_code: str) -> Optional[MessageForNew]:
        """
        Возвращает запись MessageForNew по lang_code или None, если не найдена.
        Если на вход приходит не 'ru' или 'en' — используется 'en'.
        """
        try:
            lang = (lang_code or "").lower()
            if lang not in ("ru", "en"):
                lang = "en"

            query = select(self.model).where(self.model.lang_code == lang)
            result = await self._session.execute(query)
            record = result.scalar_one_or_none()
            if record:
                logger.info(
                    f"Loaded MessageForNew for lang={lang}, day={record.dispatch_day}"
                )
            else:
                logger.info(f"No MessageForNew found for lang={lang}")
            return record
        except SQLAlchemyError as e:
            logger.error(f"Error loading MessageForNew for lang={lang_code}: {e}")
            raise


class UserGroupDAO(BaseDAO[UserGroup]):
    model = UserGroup

    async def get_users_in_group(self, group_id: int) -> list[User]:
        """
        Получить всех пользователей, входящих в указанную группу.
        """
        try:
            query = (
                select(User)
                .join(UserInGroup, User.id == UserInGroup.user_id)
                .where(UserInGroup.group_id == group_id)
            )
            result = await self._session.execute(query)
            return result.scalars().all()

        except SQLAlchemyError as e:
            logger.error(f"Ошибка при получении пользователей группы {group_id}: {e}")
            raise

    async def add_users_to_group(self, group_id: int, user_ids: list[int]) -> UserGroup:
        """
        Добавить пользователей в группу по списку user_ids.
        """
        try:
            # достаем группу вместе с текущими пользователями
            query = (
                select(self.model)
                .where(self.model.id == group_id)
                .options(selectinload(self.model.users))
            )
            result = await self._session.execute(query)
            group = result.scalar_one_or_none()

            if not group:
                raise ValueError(f"Группа с id={group_id} не найдена")

            # получаем id уже привязанных пользователей
            existing_user_ids = {u.user_id for u in group.users}

            # фильтруем только новых
            new_user_ids = set(user_ids) - existing_user_ids

            # создаем объекты UserInGroup
            new_relations = [
                UserInGroup(user_id=user_id, group_id=group_id)
                for user_id in new_user_ids
            ]

            self._session.add_all(new_relations)
            await self._session.commit()
            await self._session.refresh(group)

            return group

        except SQLAlchemyError as e:
            await self._session.rollback()
            logger.error(f"Ошибка при добавлении пользователей в группу: {e}")
            raise

    async def remove_users_from_group(
        self, group_id: int, user_ids: list[int]
    ) -> UserGroup:
        """
        Удалить пользователей из группы по списку user_ids.
        """
        try:
            # проверяем, что группа существует
            query = (
                select(self.model)
                .where(self.model.id == group_id)
                .options(selectinload(self.model.users))
            )
            result = await self._session.execute(query)
            group = result.scalar_one_or_none()

            if not group:
                raise ValueError(f"Группа с id={group_id} не найдена")

            # удаляем связи
            await self._session.execute(
                delete(UserInGroup).where(
                    UserInGroup.group_id == group_id,
                    UserInGroup.user_id.in_(user_ids),
                )
            )
            await self._session.commit()
            await self._session.refresh(group)

            return group

        except SQLAlchemyError as e:
            await self._session.rollback()
            logger.error(f"Ошибка при удалении пользователей из группы: {e}")
            raise

    async def delete_group(self, group_id: int) -> None:
        """
        Удалить группу целиком вместе с записями UserInGroup.
        """
        try:
            # Сначала удаляем связи
            await self._session.execute(
                delete(UserInGroup).where(UserInGroup.group_id == group_id)
            )

            # Потом саму группу
            await self._session.execute(
                delete(self.model).where(self.model.id == group_id)
            )

            await self._session.commit()

        except SQLAlchemyError as e:
            await self._session.rollback()
            logger.error(f"Ошибка при удалении группы: {e}")
            raise


class MessagesTextsDAO(BaseDAO[MessagesTexts]):

    model = MessagesTexts

    async def get_by_code(self, code: str) -> Optional[MessagesTexts]:
        """
        Получает запись MessagesTexts по коду.
        """
        try:
            query = select(self.model).where(self.model.code == code)
            result = await self._session.execute(query)
            message_text = result.scalar_one_or_none()
            return message_text
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при получении записи MessagesTexts по коду '{code}': {e}"
            )
            raise

    async def get_text(self, code: str, lang_code: str, **kwargs) -> Optional[str]:
        """
        Получает запись MessagesTexts по коду, обрабатывает escape-последовательности (включая \\n) и форматирует текст с использованием kwargs.
        """
        try:
            query = select(self.model).where(self.model.code == code)
            result = await self._session.execute(query)
            message_text = result.scalar_one_or_none()
            if message_text:
                if lang_code == "ru":
                    text = (
                        message_text.text_ru.replace("\\n", "\n")
                        .replace("\\t", "\t")
                        .replace('\\"', '"')
                        .replace("\\'", "'")
                    )
                else:
                    text = (
                        message_text.text_en.replace("\\n", "\n")
                        .replace("\\t", "\t")
                        .replace('\\"', '"')
                        .replace("\\'", "'")
                    )
                if kwargs:
                    return text.format(**kwargs)
                else:
                    return text
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при получении записи MessagesTexts по коду '{code}': {e}"
            )
            raise


class MatchAnalysisDAO(BaseDAO[MatchAnalysis]):
    model = MatchAnalysis

    async def list_all_ordered(self) -> list[MatchAnalysis]:
        """Все сохранённые анализы, новые сверху (без тяжёлого analysis в выборке — грузим целиком)."""
        try:
            query = select(self.model).order_by(self.model.id.desc())
            result = await self._session.execute(query)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при списке MatchAnalysis: {e}")
            raise

    async def list_for_user_ordered(self, user_id: int) -> list[MatchAnalysis]:
        """Анализы, выданные пользователю (UserMatchAnalysis). Тяжёлый JSON analysis не грузится."""
        try:
            from sqlalchemy.orm import defer

            query = (
                select(self.model)
                .options(defer(self.model.analysis))
                .join(
                    UserMatchAnalysis,
                    UserMatchAnalysis.match_analysis_id == self.model.id,
                )
                .where(UserMatchAnalysis.user_id == user_id)
                .order_by(self.model.id.desc())
            )
            result = await self._session.execute(query)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при списке MatchAnalysis для user={user_id}: {e}")
            raise

    async def list_for_user_summaries(self, user_id: int) -> list:
        """Список кабинета без полного JSON analysis (только сводка для тайлов)."""
        try:
            query = text(
                """
                SELECT
                    m.id,
                    m.title,
                    m.source_game_id,
                    m.notes,
                    m.is_ready,
                    m.created_by_user_id,
                    m.created_at,
                    m.updated_at,
                    m.analysis -> 'game_info' AS game_info,
                    COALESCE(
                        CASE
                            WHEN jsonb_typeof(COALESCE(m.analysis -> 'games', '[]'::jsonb)) = 'array'
                            THEN jsonb_array_length(COALESCE(m.analysis -> 'games', '[]'::jsonb))
                            ELSE 0
                        END,
                        0
                    ) AS games_count,
                    (
                        SELECT COUNT(*)::int
                        FROM jsonb_array_elements(
                            CASE
                                WHEN jsonb_typeof(COALESCE(m.analysis -> 'games', '[]'::jsonb)) = 'array'
                                THEN COALESCE(m.analysis -> 'games', '[]'::jsonb)
                                ELSE '[]'::jsonb
                            END
                        ) AS g
                        CROSS JOIN LATERAL jsonb_array_elements(
                            CASE
                                WHEN jsonb_typeof(COALESCE(g -> 'moves', '[]'::jsonb)) = 'array'
                                THEN COALESCE(g -> 'moves', '[]'::jsonb)
                                ELSE '[]'::jsonb
                            END
                        ) AS mv
                        WHERE COALESCE(mv ->> 'audioS3Key', '') <> ''
                    ) AS audio_count,
                    (
                        SELECT COALESCE(SUM(
                            CASE
                                WHEN COALESCE(mv ->> 'audioS3Key', '') = '' THEN 0
                                ELSE COALESCE(
                                    NULLIF(mv ->> 'audioDurationSec', '')::double precision,
                                    0
                                )
                            END
                        ), 0)
                        FROM jsonb_array_elements(
                            CASE
                                WHEN jsonb_typeof(COALESCE(m.analysis -> 'games', '[]'::jsonb)) = 'array'
                                THEN COALESCE(m.analysis -> 'games', '[]'::jsonb)
                                ELSE '[]'::jsonb
                            END
                        ) AS g
                        CROSS JOIN LATERAL jsonb_array_elements(
                            CASE
                                WHEN jsonb_typeof(COALESCE(g -> 'moves', '[]'::jsonb)) = 'array'
                                THEN COALESCE(g -> 'moves', '[]'::jsonb)
                                ELSE '[]'::jsonb
                            END
                        ) AS mv
                    ) AS audio_seconds
                FROM match_analyses m
                INNER JOIN user_match_analyses uma
                    ON uma.match_analysis_id = m.id
                WHERE uma.user_id = :uid
                ORDER BY m.id DESC
                """
            )
            result = await self._session.execute(query, {"uid": int(user_id)})
            return list(result.mappings().all())
        except SQLAlchemyError as e:
            logger.error(
                f"Ошибка при сводке MatchAnalysis для user={user_id}: {e}"
            )
            raise

    async def user_has_access(self, user_id: int, match_analysis_id: int) -> bool:
        if user_id in settings.ROOT_ADMIN_IDS:
            return True
        from bot.common.service.cabinet_admin import is_cabinet_admin

        if is_cabinet_admin(user_id):
            return True
        result = await self._session.execute(
            select(UserMatchAnalysis.id)
            .where(
                UserMatchAnalysis.user_id == user_id,
                UserMatchAnalysis.match_analysis_id == match_analysis_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def count_ready_for_issue(self) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(MatchAnalysis)
            .where(MatchAnalysis.is_ready.is_(True))
        )
        return int(result.scalar() or 0)


class MatchAnalysisActivationLinkDAO(BaseDAO[MatchAnalysisActivationLink]):
    model = MatchAnalysisActivationLink

    @staticmethod
    def _normalize_ids(raw_ids: list[int] | None) -> list[int]:
        seen: set[int] = set()
        normalized: list[int] = []
        for raw_id in raw_ids or []:
            try:
                mid = int(raw_id)
            except (TypeError, ValueError):
                continue
            if mid < 1 or mid in seen:
                continue
            seen.add(mid)
            normalized.append(mid)
        return normalized

    async def create_link(
        self, match_analysis_ids: list[int]
    ) -> MatchAnalysisActivationLink:
        normalized = self._normalize_ids(match_analysis_ids)
        if not normalized:
            raise ValueError("Нужно передать хотя бы один корректный match_analysis_id")
        activation_link = MatchAnalysisActivationLink(
            link=secrets.token_urlsafe(24),
            status=MatchAnalysisActivationLinkStatus.UNACTIVATE,
            match_analysis_ids=normalized,
        )
        self._session.add(activation_link)
        await self._session.flush()
        return activation_link

    async def find_one_by_link(
        self, link_value: str
    ) -> MatchAnalysisActivationLink | None:
        query = (
            select(self.model)
            .where(self.model.link == str(link_value or "").strip())
            .limit(1)
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def activate_link_and_issue(
        self, link_value: str, user_id: int
    ) -> dict[str, int | str]:
        cleaned_link = str(link_value or "").strip()
        if not cleaned_link:
            return {"ok": 0, "reason": "invalid_link"}

        link_query = (
            select(self.model)
            .where(self.model.link == cleaned_link)
            .with_for_update()
            .limit(1)
        )
        link_result = await self._session.execute(link_query)
        activation_link = link_result.scalar_one_or_none()
        if not activation_link:
            return {"ok": 0, "reason": "not_found"}

        if activation_link.status == MatchAnalysisActivationLinkStatus.ACTIVATE:
            return {"ok": 0, "reason": "already_activated"}

        user = await self._session.get(User, user_id)
        if not user:
            return {"ok": 0, "reason": "user_not_found"}

        requested_ids = self._normalize_ids(activation_link.match_analysis_ids)
        if not requested_ids:
            return {"ok": 0, "reason": "no_cards"}

        existing_result = await self._session.execute(
            select(MatchAnalysis.id).where(MatchAnalysis.id.in_(requested_ids))
        )
        existing_ids = {
            int(mid) for mid in existing_result.scalars().all() if mid is not None
        }
        valid_ids = [mid for mid in requested_ids if mid in existing_ids]
        if not valid_ids:
            return {"ok": 0, "reason": "cards_not_found"}

        existing_user_links = await self._session.execute(
            select(UserMatchAnalysis.match_analysis_id).where(
                UserMatchAnalysis.user_id == user_id,
                UserMatchAnalysis.match_analysis_id.in_(valid_ids),
            )
        )
        already_has_ids = {
            int(mid)
            for mid in existing_user_links.scalars().all()
            if mid is not None
        }
        to_issue_ids = [mid for mid in valid_ids if mid not in already_has_ids]
        for mid in to_issue_ids:
            self._session.add(
                UserMatchAnalysis(user_id=user_id, match_analysis_id=mid)
            )

        activation_link.status = MatchAnalysisActivationLinkStatus.ACTIVATE
        activation_link.activated_by_user_id = user_id
        activation_link.activated_at = datetime.now(timezone.utc)

        await self._session.flush()
        return {
            "ok": 1,
            "reason": "ok",
            "issued_count": len(to_issue_ids),
            "already_had_count": len(already_has_ids),
            "total_count": len(valid_ids),
            "link_id": int(activation_link.id),
        }


class MatchAnalysisFolderDAO(BaseDAO[MatchAnalysisFolder]):
    """DAO дерева папок анализов матча."""

    model = MatchAnalysisFolder

    async def get_all_folders(self) -> list[MatchAnalysisFolder]:
        result = await self._session.execute(
            select(MatchAnalysisFolder).order_by(
                MatchAnalysisFolder.parent_id.asc().nullsfirst(),
                MatchAnalysisFolder.sort_order.asc(),
                MatchAnalysisFolder.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_folder_by_id(self, folder_id: int) -> MatchAnalysisFolder | None:
        result = await self._session.execute(
            select(MatchAnalysisFolder).where(MatchAnalysisFolder.id == folder_id)
        )
        return result.scalar_one_or_none()

    async def create_folder(
        self,
        name: str,
        parent_id: int | None,
        sort_order: int,
        admin_id: int | None,
    ) -> MatchAnalysisFolder:
        folder = MatchAnalysisFolder(
            name=name[:255],
            parent_id=parent_id,
            sort_order=sort_order,
            created_by_admin_id=admin_id,
        )
        self._session.add(folder)
        await self._session.flush()
        return folder

    async def update_folder(
        self,
        folder_id: int,
        name: str | None = None,
        sort_order: int | None = None,
    ) -> MatchAnalysisFolder | None:
        folder = await self.get_folder_by_id(folder_id)
        if not folder:
            return None
        if name is not None:
            folder.name = name[:255]
        if sort_order is not None:
            folder.sort_order = sort_order
        folder.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return folder

    async def move_folder(
        self,
        folder_id: int,
        new_parent_id: int | None,
        new_sort_order: int,
    ) -> MatchAnalysisFolder | None:
        folder = await self.get_folder_by_id(folder_id)
        if not folder:
            return None
        if new_parent_id is not None:
            if await self._is_descendant(folder_id, new_parent_id):
                raise ValueError(
                    f"Нельзя переместить папку {folder_id} внутрь своего потомка {new_parent_id}"
                )
        folder.parent_id = new_parent_id
        folder.sort_order = new_sort_order
        folder.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return folder

    async def _collect_descendant_folder_ids(self, root_folder_id: int) -> list[int]:
        all_folders = await self.get_all_folders()
        children_map: dict[int | None, list[int]] = {}
        for f in all_folders:
            children_map.setdefault(f.parent_id, []).append(f.id)

        result: list[int] = []
        queue: list[int] = list(children_map.get(root_folder_id, []))
        while queue:
            current = queue.pop(0)
            result.append(current)
            queue.extend(children_map.get(current, []))
        return result

    async def delete_folder(self, folder_id: int) -> bool:
        folder = await self.get_folder_by_id(folder_id)
        if not folder:
            return False
        descendant_ids = await self._collect_descendant_folder_ids(folder_id)
        ids_to_delete = descendant_ids + [folder_id]
        await self._session.execute(
            delete(MatchAnalysisFolder).where(MatchAnalysisFolder.id.in_(ids_to_delete))
        )
        await self._session.flush()
        return True

    async def _is_descendant(self, ancestor_id: int, candidate_id: int) -> bool:
        visited: set[int] = set()
        current_id: int | None = candidate_id
        while current_id is not None:
            if current_id in visited:
                break
            visited.add(current_id)
            if current_id == ancestor_id:
                return True
            result = await self._session.execute(
                select(MatchAnalysisFolder.parent_id).where(
                    MatchAnalysisFolder.id == current_id
                )
            )
            current_id = result.scalar_one_or_none()
        return False

    async def collect_match_ids_for_folder_tree(
        self, root_folder_id: int, include_children: bool = True
    ) -> list[int]:
        all_folders = await self.get_all_folders()
        children_map: dict[int | None, list[int]] = {}
        for f in all_folders:
            children_map.setdefault(f.parent_id, []).append(f.id)

        folder_ids_to_process: list[int] = [root_folder_id]
        if include_children:
            queue: list[int] = [root_folder_id]
            while queue:
                current = queue.pop(0)
                for child_id in children_map.get(current, []):
                    if child_id not in folder_ids_to_process:
                        folder_ids_to_process.append(child_id)
                        queue.append(child_id)

        result = await self._session.execute(
            select(MatchAnalysisFolderItem.match_analysis_id)
            .where(MatchAnalysisFolderItem.folder_id.in_(folder_ids_to_process))
            .order_by(
                MatchAnalysisFolderItem.folder_id.asc(),
                MatchAnalysisFolderItem.sort_order.asc(),
                MatchAnalysisFolderItem.id.asc(),
            )
        )
        seen: set[int] = set()
        deduped: list[int] = []
        for mid in result.scalars().all():
            if mid not in seen:
                seen.add(mid)
                deduped.append(mid)
        return deduped

    async def get_folder_match_ids(self, folder_id: int) -> list[int]:
        result = await self._session.execute(
            select(MatchAnalysisFolderItem.match_analysis_id)
            .where(MatchAnalysisFolderItem.folder_id == folder_id)
            .order_by(
                MatchAnalysisFolderItem.sort_order.asc(),
                MatchAnalysisFolderItem.id.asc(),
            )
        )
        return [int(mid) for mid in result.scalars().all() if mid is not None]

    async def add_matches_to_folder(self, folder_id: int, match_ids: list[int]) -> int:
        existing_ids = set(await self.get_folder_match_ids(folder_id))
        added = 0
        next_order = len(existing_ids)
        for mid in match_ids:
            if mid in existing_ids:
                continue
            self._session.add(
                MatchAnalysisFolderItem(
                    folder_id=folder_id,
                    match_analysis_id=mid,
                    sort_order=next_order,
                )
            )
            existing_ids.add(mid)
            next_order += 1
            added += 1
        if added:
            await self._session.flush()
        return added

    async def remove_match_from_folder(
        self, folder_id: int, match_analysis_id: int
    ) -> bool:
        result = await self._session.execute(
            select(MatchAnalysisFolderItem).where(
                MatchAnalysisFolderItem.folder_id == folder_id,
                MatchAnalysisFolderItem.match_analysis_id == match_analysis_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            return False
        await self._session.delete(item)
        await self._session.flush()
        return True

    async def set_folder_items(
        self,
        folder_id: int,
        match_ids_ordered: list[int],
    ) -> None:
        existing_res = await self._session.execute(
            select(MatchAnalysisFolderItem).where(
                MatchAnalysisFolderItem.folder_id == folder_id
            )
        )
        existing_items = {
            item.match_analysis_id: item for item in existing_res.scalars().all()
        }
        desired_ids = list(dict.fromkeys(match_ids_ordered))

        for item in existing_items.values():
            if item.match_analysis_id not in desired_ids:
                await self._session.delete(item)

        for order, mid in enumerate(desired_ids):
            if mid in existing_items:
                existing_items[mid].sort_order = order
            else:
                self._session.add(
                    MatchAnalysisFolderItem(
                        folder_id=folder_id,
                        match_analysis_id=mid,
                        sort_order=order,
                    )
                )
        await self._session.flush()


class MatchAnalysisFolderLinkDAO(BaseDAO[MatchAnalysisFolderLink]):
    model = MatchAnalysisFolderLink

    async def get_link_for_folder(
        self, folder_id: int
    ) -> MatchAnalysisFolderLink | None:
        result = await self._session.execute(
            select(MatchAnalysisFolderLink)
            .where(
                MatchAnalysisFolderLink.folder_id == folder_id,
                MatchAnalysisFolderLink.is_active == True,  # noqa: E712
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_link(
        self, folder_id: int, admin_id: int | None
    ) -> MatchAnalysisFolderLink:
        link = MatchAnalysisFolderLink(
            link_token=secrets.token_urlsafe(24),
            folder_id=folder_id,
            is_active=True,
            created_by_admin_id=admin_id,
        )
        self._session.add(link)
        await self._session.flush()
        return link

    async def get_or_create_link(
        self, folder_id: int, admin_id: int | None
    ) -> MatchAnalysisFolderLink:
        existing = await self.get_link_for_folder(folder_id)
        if existing:
            return existing
        return await self.create_link(folder_id, admin_id)

    async def find_by_token(self, token: str) -> MatchAnalysisFolderLink | None:
        result = await self._session.execute(
            select(MatchAnalysisFolderLink)
            .where(
                MatchAnalysisFolderLink.link_token == str(token or "").strip(),
                MatchAnalysisFolderLink.is_active == True,  # noqa: E712
            )
            .limit(1)
        )
        return result.scalar_one_or_none()


class WebUserDAO(BaseDAO[WebUser]):
    model = WebUser

    async def get_by_login(self, login: str) -> WebUser | None:
        normalized = (login or "").strip()
        if not normalized:
            return None
        result = await self._session.execute(
            select(WebUser).where(WebUser.login == normalized)
        )
        return result.scalar_one_or_none()


_WEB_UPLOAD_DONE = HintViewerWebUploadStatus.DONE.value
_WEB_UPLOAD_ERROR = HintViewerWebUploadStatus.ERROR.value


def web_upload_job_filter(
    job_id: str,
    *,
    game_id: str | None = None,
    original_filename: str | None = None,
):
    conditions = [HintViewerWebUpload.job_id == job_id]
    if game_id:
        conditions.append(HintViewerWebUpload.game_id == game_id)
    elif original_filename:
        conditions.append(HintViewerWebUpload.original_filename == original_filename)
    return conditions


def apply_web_upload_status(
    row: HintViewerWebUpload,
    status: str,
    *,
    game_id: str | None = None,
    error_message: str | None = None,
    finished: bool = False,
    red_player: str | None = None,
    black_player: str | None = None,
) -> bool:
    """Обновляет строку истории. Готовый анализ не откатывается в очередь."""
    changed = False
    if game_id and row.game_id != game_id:
        row.game_id = game_id
        changed = True
    if red_player and row.red_player != red_player:
        row.red_player = red_player
        changed = True
    if black_player and row.black_player != black_player:
        row.black_player = black_player
        changed = True

    if row.status == _WEB_UPLOAD_DONE and status != _WEB_UPLOAD_DONE:
        return changed
    if row.status == _WEB_UPLOAD_ERROR and status not in {
        _WEB_UPLOAD_DONE,
        _WEB_UPLOAD_ERROR,
    }:
        return changed

    if row.status != status:
        row.status = status
        changed = True
    if status == _WEB_UPLOAD_DONE and row.error_message:
        row.error_message = None
        changed = True
    elif status == _WEB_UPLOAD_ERROR and error_message is not None:
        if row.error_message != error_message:
            row.error_message = error_message
            changed = True
    if finished or status in {_WEB_UPLOAD_DONE, _WEB_UPLOAD_ERROR}:
        if row.finished_at is None:
            row.finished_at = datetime.now(timezone.utc)
            changed = True
    return changed


class HintViewerWebUploadDAO(BaseDAO[HintViewerWebUpload]):
    model = HintViewerWebUpload

    async def create_upload(
        self,
        *,
        session_id: str,
        original_filename: str,
        user_id: int | None = None,
        game_id: str | None = None,
        job_id: str | None = None,
        batch_id: str | None = None,
        red_player: str | None = None,
        black_player: str | None = None,
        status: str = HintViewerWebUploadStatus.QUEUED.value,
        service: str = "hints",
        error_message: str | None = None,
    ) -> HintViewerWebUpload:
        row = HintViewerWebUpload(
            user_id=user_id,
            session_id=session_id,
            game_id=game_id,
            job_id=job_id,
            batch_id=batch_id,
            original_filename=original_filename,
            red_player=red_player,
            black_player=black_player,
            status=status,
            service=service or "hints",
            error_message=error_message,
        )
        if status in {
            HintViewerWebUploadStatus.DONE.value,
            HintViewerWebUploadStatus.ERROR.value,
        }:
            row.finished_at = datetime.now(timezone.utc)
        self._session.add(row)
        await self._session.flush()
        return row

    def _user_service_filter(self, user_id: int, service: str | None):
        conditions = [HintViewerWebUpload.user_id == user_id]
        if service:
            conditions.append(HintViewerWebUpload.service == service)
        return conditions

    def _folder_membership_filter(self, folder_id: int | None):
        if folder_id is None:
            return []
        return [
            HintViewerWebUpload.id.in_(
                select(HintWebFolderItem.upload_id).where(
                    HintWebFolderItem.folder_id == folder_id
                )
            )
        ]

    async def list_for_user(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0,
        service: str | None = None,
        folder_id: int | None = None,
    ) -> list[HintViewerWebUpload]:
        result = await self._session.execute(
            select(HintViewerWebUpload)
            .where(
                *self._user_service_filter(user_id, service),
                *self._folder_membership_filter(folder_id),
            )
            .order_by(HintViewerWebUpload.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_for_user(
        self,
        user_id: int,
        service: str | None = None,
        folder_id: int | None = None,
    ) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(HintViewerWebUpload)
            .where(
                *self._user_service_filter(user_id, service),
                *self._folder_membership_filter(folder_id),
            )
        )
        return int(result.scalar_one() or 0)

    async def get_owned_upload_ids(
        self,
        user_id: int,
        upload_ids: list[int],
        service: str | None = "hints",
    ) -> list[int]:
        ids = [int(x) for x in upload_ids if x is not None]
        if not ids:
            return []
        result = await self._session.execute(
            select(HintViewerWebUpload.id).where(
                *self._user_service_filter(user_id, service),
                HintViewerWebUpload.id.in_(ids),
            )
        )
        found = {int(x) for x in result.scalars().all()}
        return [uid for uid in ids if uid in found]

    def _history_group_key(self):
        return func.coalesce(
            func.nullif(HintViewerWebUpload.batch_id, ""),
            func.concat(literal("id:"), cast(HintViewerWebUpload.id, String)),
        )

    async def count_groups_for_user(
        self, user_id: int, service: str | None = None
    ) -> int:
        grp = self._history_group_key()
        sub = (
            select(grp.label("grp"))
            .where(*self._user_service_filter(user_id, service))
            .group_by(grp)
            .subquery()
        )
        result = await self._session.execute(select(func.count()).select_from(sub))
        return int(result.scalar_one() or 0)

    async def list_grouped_for_user(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0,
        service: str | None = None,
    ) -> list[list[HintViewerWebUpload]]:
        grp = self._history_group_key()
        grouped = (
            select(
                grp.label("grp"),
                func.max(HintViewerWebUpload.id).label("sort_id"),
                func.max(HintViewerWebUpload.batch_id).label("batch_id"),
            )
            .where(*self._user_service_filter(user_id, service))
            .group_by(grp)
            .order_by(func.max(HintViewerWebUpload.id).desc())
            .limit(max(1, int(limit or 10)))
            .offset(max(0, int(offset or 0)))
            .subquery()
        )
        keys_result = await self._session.execute(
            select(grouped.c.grp, grouped.c.batch_id, grouped.c.sort_id).order_by(
                grouped.c.sort_id.desc()
            )
        )
        keys = list(keys_result.all())
        if not keys:
            return []
        batch_ids = [row.batch_id for row in keys if row.batch_id]
        single_ids: list[int] = []
        for row in keys:
            if row.batch_id:
                continue
            grp_val = str(row.grp or "")
            if grp_val.startswith("id:"):
                try:
                    single_ids.append(int(grp_val[3:]))
                except ValueError:
                    continue
        conditions = [*self._user_service_filter(user_id, service)]
        id_filters = []
        if batch_ids:
            id_filters.append(HintViewerWebUpload.batch_id.in_(batch_ids))
        if single_ids:
            id_filters.append(HintViewerWebUpload.id.in_(single_ids))
        if not id_filters:
            return []
        rows_result = await self._session.execute(
            select(HintViewerWebUpload)
            .where(*conditions, or_(*id_filters))
            .order_by(HintViewerWebUpload.id.asc())
        )
        all_rows = list(rows_result.scalars().all())
        by_batch: dict[str, list[HintViewerWebUpload]] = {}
        by_id: dict[int, HintViewerWebUpload] = {}
        for row in all_rows:
            by_id[row.id] = row
            if row.batch_id:
                by_batch.setdefault(row.batch_id, []).append(row)
        groups: list[list[HintViewerWebUpload]] = []
        for key in keys:
            if key.batch_id:
                children = by_batch.get(key.batch_id) or []
                if children:
                    groups.append(children)
                continue
            grp_val = str(key.grp or "")
            if grp_val.startswith("id:"):
                try:
                    sid = int(grp_val[3:])
                except ValueError:
                    continue
                row = by_id.get(sid)
                if row is not None:
                    groups.append([row])
        return groups

    async def list_by_batch_id(
        self,
        user_id: int,
        batch_id: str,
        service: str | None = None,
    ) -> list[HintViewerWebUpload]:
        bid = (batch_id or "").strip()
        if not bid:
            return []
        result = await self._session.execute(
            select(HintViewerWebUpload)
            .where(
                *self._user_service_filter(user_id, service),
                HintViewerWebUpload.batch_id == bid,
            )
            .order_by(HintViewerWebUpload.id.asc())
        )
        return list(result.scalars().all())

    async def find_for_user_game(
        self,
        user_id: int,
        game_id: str,
        service: str | None = None,
    ) -> HintViewerWebUpload | None:
        gid = (game_id or "").strip()
        if not gid:
            return None
        result = await self._session.execute(
            select(HintViewerWebUpload)
            .where(
                *self._user_service_filter(user_id, service),
                HintViewerWebUpload.game_id == gid,
            )
            .order_by(HintViewerWebUpload.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_session(
        self, session_id: str, limit: int = 50
    ) -> list[HintViewerWebUpload]:
        result = await self._session.execute(
            select(HintViewerWebUpload)
            .where(HintViewerWebUpload.session_id == session_id)
            .order_by(HintViewerWebUpload.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        upload_id: int,
        status: str,
        *,
        game_id: str | None = None,
        error_message: str | None = None,
        finished: bool = False,
    ) -> None:
        row = await self._session.get(HintViewerWebUpload, upload_id)
        if not row:
            return
        apply_web_upload_status(
            row,
            status,
            game_id=game_id,
            error_message=error_message,
            finished=finished,
        )

    async def list_open_for_user(
        self,
        user_id: int,
        service: str | None = None,
        limit: int = 100,
    ) -> list[HintViewerWebUpload]:
        conditions = [
            *self._user_service_filter(user_id, service),
            HintViewerWebUpload.status.in_(
                (
                    HintViewerWebUploadStatus.QUEUED.value,
                    HintViewerWebUploadStatus.PROCESSING.value,
                )
            ),
        ]
        result = await self._session.execute(
            select(HintViewerWebUpload)
            .where(*conditions)
            .order_by(HintViewerWebUpload.id.desc())
            .limit(max(1, min(int(limit or 100), 200)))
        )
        return list(result.scalars().all())

    async def update_status_for_job(
        self,
        job_id: str,
        status: str,
        *,
        original_filename: str | None = None,
        game_id: str | None = None,
        error_message: str | None = None,
        finished: bool = False,
        red_player: str | None = None,
        black_player: str | None = None,
    ) -> None:
        query = select(HintViewerWebUpload).where(
            *web_upload_job_filter(
                job_id,
                game_id=game_id,
                original_filename=original_filename,
            )
        )
        result = await self._session.execute(query)
        for row in result.scalars().all():
            apply_web_upload_status(
                row,
                status,
                game_id=game_id,
                error_message=error_message,
                finished=finished,
                red_player=red_player,
                black_player=black_player,
            )


class HintWebFolderDAO(BaseDAO[HintWebFolder]):
    """Персональные папки веб-кабинета: отдельное дерево на пользователя и сервис."""

    model = HintWebFolder

    def _scope(self, user_id: int, service: str):
        return (
            HintWebFolder.user_id == user_id,
            HintWebFolder.service == (service or "hints"),
        )

    async def get_all_folders(
        self, user_id: int, service: str = "hints"
    ) -> list[HintWebFolder]:
        result = await self._session.execute(
            select(HintWebFolder)
            .where(*self._scope(user_id, service))
            .order_by(
                HintWebFolder.parent_id.asc().nullsfirst(),
                HintWebFolder.sort_order.asc(),
                HintWebFolder.id.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_folder_for_user(
        self, folder_id: int, user_id: int, service: str = "hints"
    ) -> HintWebFolder | None:
        result = await self._session.execute(
            select(HintWebFolder).where(
                HintWebFolder.id == folder_id,
                *self._scope(user_id, service),
            )
        )
        return result.scalar_one_or_none()

    async def next_sort_order(
        self, user_id: int, parent_id: int | None, service: str = "hints"
    ) -> int:
        parent_cond = (
            HintWebFolder.parent_id.is_(None)
            if parent_id is None
            else HintWebFolder.parent_id == parent_id
        )
        result = await self._session.execute(
            select(func.coalesce(func.max(HintWebFolder.sort_order), -1)).where(
                *self._scope(user_id, service),
                parent_cond,
            )
        )
        return int(result.scalar_one() or -1) + 1

    async def create_folder(
        self,
        user_id: int,
        name: str,
        parent_id: int | None,
        sort_order: int | None = None,
        service: str = "hints",
    ) -> HintWebFolder:
        folder_service = service or "hints"
        if parent_id is not None:
            parent = await self.get_folder_for_user(
                parent_id, user_id, folder_service
            )
            if not parent:
                raise ValueError("Родительская папка не найдена")
        order = (
            sort_order
            if sort_order is not None
            else await self.next_sort_order(user_id, parent_id, folder_service)
        )
        folder = HintWebFolder(
            user_id=user_id,
            name=name[:255],
            parent_id=parent_id,
            sort_order=order,
            service=folder_service,
        )
        self._session.add(folder)
        await self._session.flush()
        return folder

    async def update_folder(
        self,
        folder_id: int,
        user_id: int,
        name: str | None = None,
        sort_order: int | None = None,
        service: str = "hints",
    ) -> HintWebFolder | None:
        folder = await self.get_folder_for_user(folder_id, user_id, service)
        if not folder:
            return None
        if name is not None:
            folder.name = name[:255]
        if sort_order is not None:
            folder.sort_order = sort_order
        folder.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return folder

    async def move_folder(
        self,
        folder_id: int,
        user_id: int,
        new_parent_id: int | None,
        new_sort_order: int | None = None,
        service: str = "hints",
    ) -> HintWebFolder | None:
        folder = await self.get_folder_for_user(folder_id, user_id, service)
        if not folder:
            return None
        if new_parent_id is not None:
            new_parent = await self.get_folder_for_user(
                new_parent_id, user_id, service
            )
            if not new_parent:
                raise ValueError("Родительская папка не найдена")
            if await self._is_descendant(
                folder_id, new_parent_id, user_id, service
            ):
                raise ValueError(
                    f"Нельзя переместить папку {folder_id} внутрь своего потомка {new_parent_id}"
                )
        folder.parent_id = new_parent_id
        folder.sort_order = (
            new_sort_order
            if new_sort_order is not None
            else await self.next_sort_order(user_id, new_parent_id, service)
        )
        folder.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return folder

    async def _collect_descendant_folder_ids(
        self, root_folder_id: int, user_id: int, service: str = "hints"
    ) -> list[int]:
        all_folders = await self.get_all_folders(user_id, service)
        children_map: dict[int | None, list[int]] = {}
        for f in all_folders:
            children_map.setdefault(f.parent_id, []).append(f.id)
        result: list[int] = []
        queue: list[int] = list(children_map.get(root_folder_id, []))
        while queue:
            current = queue.pop(0)
            result.append(current)
            queue.extend(children_map.get(current, []))
        return result

    async def delete_folder(
        self, folder_id: int, user_id: int, service: str = "hints"
    ) -> bool:
        folder = await self.get_folder_for_user(folder_id, user_id, service)
        if not folder:
            return False
        descendant_ids = await self._collect_descendant_folder_ids(
            folder_id, user_id, service
        )
        ids_to_delete = descendant_ids + [folder_id]
        await self._session.execute(
            delete(HintWebFolder).where(
                HintWebFolder.user_id == user_id,
                HintWebFolder.service == (service or "hints"),
                HintWebFolder.id.in_(ids_to_delete),
            )
        )
        await self._session.flush()
        return True

    async def _is_descendant(
        self,
        ancestor_id: int,
        candidate_id: int,
        user_id: int,
        service: str = "hints",
    ) -> bool:
        visited: set[int] = set()
        current_id: int | None = candidate_id
        while current_id is not None:
            if current_id in visited:
                break
            visited.add(current_id)
            if current_id == ancestor_id:
                return True
            result = await self._session.execute(
                select(HintWebFolder.parent_id).where(
                    HintWebFolder.id == current_id,
                    *self._scope(user_id, service),
                )
            )
            current_id = result.scalar_one_or_none()
        return False

    async def get_direct_counts(
        self, user_id: int, service: str = "hints"
    ) -> dict[int, int]:
        result = await self._session.execute(
            select(
                HintWebFolderItem.folder_id,
                func.count(HintWebFolderItem.id),
            )
            .join(HintWebFolder, HintWebFolder.id == HintWebFolderItem.folder_id)
            .where(*self._scope(user_id, service))
            .group_by(HintWebFolderItem.folder_id)
        )
        return {int(row[0]): int(row[1]) for row in result.all()}

    async def get_child_folders(
        self, folder_id: int, user_id: int, service: str = "hints"
    ) -> list[HintWebFolder]:
        result = await self._session.execute(
            select(HintWebFolder)
            .where(
                *self._scope(user_id, service),
                HintWebFolder.parent_id == folder_id,
            )
            .order_by(HintWebFolder.sort_order.asc(), HintWebFolder.id.asc())
        )
        return list(result.scalars().all())

    async def get_folder_upload_ids(self, folder_id: int) -> list[int]:
        result = await self._session.execute(
            select(HintWebFolderItem.upload_id)
            .where(HintWebFolderItem.folder_id == folder_id)
            .order_by(
                HintWebFolderItem.sort_order.asc(),
                HintWebFolderItem.id.asc(),
            )
        )
        return [int(uid) for uid in result.scalars().all() if uid is not None]

    async def add_uploads_to_folder(
        self, folder_id: int, upload_ids: list[int]
    ) -> int:
        existing_ids = set(await self.get_folder_upload_ids(folder_id))
        added = 0
        next_order = len(existing_ids)
        for uid in upload_ids:
            if uid in existing_ids:
                continue
            self._session.add(
                HintWebFolderItem(
                    folder_id=folder_id,
                    upload_id=uid,
                    sort_order=next_order,
                )
            )
            existing_ids.add(uid)
            next_order += 1
            added += 1
        if added:
            await self._session.flush()
        return added

    async def remove_upload_from_folder(
        self, folder_id: int, upload_id: int
    ) -> bool:
        result = await self._session.execute(
            select(HintWebFolderItem).where(
                HintWebFolderItem.folder_id == folder_id,
                HintWebFolderItem.upload_id == upload_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            return False
        await self._session.delete(item)
        await self._session.flush()
        return True
