import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import BufferedInputFile
from flask import flash, redirect, request, url_for
from flask_appbuilder import ModelView, expose, has_access, permission_name
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_wtf.csrf import generate_csrf
from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from bot.config import create_bot_for_sync_context, scheduler, settings
from bot.db.models import Broadcast, BroadcastStatus, BroadcastUser, User, UserGroup, UserInGroup

MEMBERS_PAGE_SIZE = 25
MSK = ZoneInfo("Europe/Moscow")
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
MAX_MEDIA_SIZE_BYTES = 20 * 1024 * 1024


def _run_telegram_sync(action):
    async def _runner():
        return await action()

    return asyncio.run(_runner())


def _get_admin_created_by() -> int:
    if settings.ROOT_ADMIN_IDS:
        return int(settings.ROOT_ADMIN_IDS[0])
    raise ValueError("ROOT_ADMIN_IDS не задан")


def _get_member_user_ids(session, group_id: int) -> set[int]:
    rows = session.execute(
        select(UserInGroup.user_id).where(UserInGroup.group_id == group_id)
    ).scalars()
    return set(rows)


def _get_group_members(session, group_id: int) -> list[User]:
    return list(
        session.execute(
            select(User)
            .join(UserInGroup, User.id == UserInGroup.user_id)
            .where(UserInGroup.group_id == group_id)
            .order_by(User.id)
        )
        .scalars()
        .all()
    )


def _get_scheduled_broadcasts_for_group(session, group_id: int) -> list[Broadcast]:
    return list(
        session.execute(
            select(Broadcast)
            .where(
                Broadcast.group == "user_group",
                Broadcast.group_id == group_id,
                Broadcast.status == BroadcastStatus.SCHEDULED,
            )
            .order_by(Broadcast.run_time)
        )
        .scalars()
        .all()
    )


def _add_users_to_group(session, group_id: int, user_ids: list[int]) -> int:
    existing_ids = _get_member_user_ids(session, group_id)
    new_ids = [uid for uid in user_ids if uid not in existing_ids]
    if not new_ids:
        return 0
    session.add_all(
        [
            UserInGroup(user_id=user_id, group_id=group_id)
            for user_id in new_ids
        ]
    )
    session.commit()
    return len(new_ids)


def _remove_users_from_group(session, group_id: int, user_ids: list[int]) -> int:
    if not user_ids:
        return 0
    result = session.execute(
        delete(UserInGroup).where(
            UserInGroup.group_id == group_id,
            UserInGroup.user_id.in_(user_ids),
        )
    )
    session.commit()
    return result.rowcount or 0


def _parse_scheduled_at(raw_value: str) -> datetime:
    value = (raw_value or "").strip()
    if not value:
        raise ValueError("Укажите дату и время рассылки.")

    normalized = value.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(normalized, fmt)
            return parsed.replace(tzinfo=MSK)
        except ValueError:
            continue
    raise ValueError("Неверный формат даты. Используйте поле выбора даты и времени.")


def _default_broadcast_name(group_name: str) -> str:
    stamp = datetime.now(MSK).strftime("%d.%m.%Y %H:%M")
    return f"Группа «{group_name}» — {stamp}"


async def _upload_media_to_telegram(
    file_bytes: bytes, filename: str, content_type: str
) -> tuple[str, str]:
    admin_id = _get_admin_created_by()
    tg_bot = create_bot_for_sync_context()
    try:
        if content_type in ALLOWED_IMAGE_TYPES:
            message = await tg_bot.send_photo(
                chat_id=admin_id,
                photo=BufferedInputFile(file_bytes, filename=filename),
                caption="[служебное] медиа для рассылки из веб-админки",
            )
            return message.photo[-1].file_id, "photo"
        if content_type in ALLOWED_VIDEO_TYPES:
            message = await tg_bot.send_video(
                chat_id=admin_id,
                video=BufferedInputFile(file_bytes, filename=filename),
                caption="[служебное] медиа для рассылки из веб-админки",
            )
            return message.video.file_id, "video"
        raise ValueError("Поддерживаются только изображения (JPEG, PNG, WebP, GIF) и видео (MP4, MOV, WebM).")
    finally:
        await tg_bot.session.close()


async def _send_to_user(
    tg_bot,
    user_id: int,
    text: str,
    media_id: str | None = None,
    media_type: str | None = None,
) -> bool:
    try:
        if media_id and media_type == "photo":
            await tg_bot.send_photo(chat_id=user_id, photo=media_id, caption=text)
        elif media_id and media_type == "video":
            await tg_bot.send_video(chat_id=user_id, video=media_id, caption=text)
        else:
            await tg_bot.send_message(chat_id=user_id, text=text)
        return True
    except TelegramForbiddenError:
        return False
    except TelegramBadRequest:
        return False
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after)
        return await _send_to_user(tg_bot, user_id, text, media_id, media_type)
    except Exception:
        return False


async def _broadcast_to_users(
    user_ids: list[int],
    text: str,
    media_id: str | None = None,
    media_type: str | None = None,
) -> tuple[int, int]:
    if not user_ids:
        return 0, 0

    tg_bot = create_bot_for_sync_context()
    successful = 0
    failed = 0
    try:
        for user_id in user_ids:
            if await _send_to_user(tg_bot, user_id, text, media_id, media_type):
                successful += 1
            else:
                failed += 1
            await asyncio.sleep(0.1)
    finally:
        await tg_bot.session.close()

    return successful, failed


def _create_scheduled_broadcast(
    session,
    *,
    group_id: int,
    broadcast_name: str,
    text: str,
    user_ids: list[int],
    run_time: datetime,
    media_id: str | None = None,
    media_type: str | None = None,
) -> Broadcast:
    broadcast = Broadcast(
        name=broadcast_name,
        text=text,
        media_id=media_id,
        media_type=media_type,
        group_id=group_id,
        group="user_group",
        run_time=run_time,
        status=BroadcastStatus.SCHEDULED,
        created_by=_get_admin_created_by(),
    )
    session.add(broadcast)
    session.flush()

    if user_ids:
        session.execute(
            insert(BroadcastUser),
            [{"broadcast_id": broadcast.id, "user_id": user_id} for user_id in user_ids],
        )

    session.commit()
    from bot.routers.admin.notify import run_broadcast_job

    scheduler.add_job(
        run_broadcast_job,
        "date",
        run_date=run_time,
        args=[broadcast.id],
        id=f"broadcast_{broadcast.id}",
        replace_existing=True,
    )
    return broadcast


def _cancel_scheduled_broadcast(session, broadcast_id: int, group_id: int) -> bool:
    broadcast = session.get(Broadcast, broadcast_id)
    if (
        not broadcast
        or broadcast.status != BroadcastStatus.SCHEDULED
        or broadcast.group != "user_group"
        or broadcast.group_id != group_id
    ):
        return False

    broadcast.status = BroadcastStatus.CANCELLED
    session.commit()

    job_id = f"broadcast_{broadcast_id}"
    job = scheduler.get_job(job_id)
    if job:
        scheduler.remove_job(job_id)
    return True


def _read_uploaded_media() -> tuple[bytes, str, str] | tuple[None, None, None]:
    upload = request.files.get("media_file")
    if not upload or not upload.filename:
        return None, None, None

    content_type = (upload.mimetype or "").split(";")[0].strip().lower()
    filename = os.path.basename(upload.filename)
    file_bytes = upload.read()
    if not file_bytes:
        raise ValueError("Загруженный файл пуст.")
    if len(file_bytes) > MAX_MEDIA_SIZE_BYTES:
        raise ValueError("Размер файла не должен превышать 20 МБ.")
    return file_bytes, filename, content_type


def _format_run_time_msk(run_time: datetime) -> str:
    if run_time.tzinfo is None:
        run_time = run_time.replace(tzinfo=MSK)
    return run_time.astimezone(MSK).strftime("%d.%m.%Y %H:%M (МСК)")


class FabUserGroupsModelView(ModelView):
    """Группы пользователей (уникальное имя класса — blueprint FAB)."""

    route_base = "/fabusergroups"
    datamodel = SQLAInterface(UserGroup)
    show_template = "show_user_group.html"

    list_title = "Группы пользователей"
    add_title = "Создать группу"
    edit_title = "Редактировать группу"
    show_title = "Группа пользователей"

    list_columns = ["id", "name", "members_count"]
    show_columns = ["id", "name", "members_count"]
    add_columns = edit_columns = ["name"]
    search_columns = ["name"]

    label_columns = {
        "id": "ID",
        "name": "Название",
        "members_count": "Участников",
    }

    def get_query(self):
        return super().get_query().options(selectinload(UserGroup.users))

    def render_template(self, template, **kwargs):
        kwargs.setdefault(
            "ug_fab_endpoint", getattr(self, "endpoint", self.__class__.__name__)
        )
        kwargs.setdefault("csrf_token_value", generate_csrf())
        if template == self.show_template:
            pk = kwargs.get("pk")
            if pk is not None:
                group = self.datamodel.get(pk)
                session = self.datamodel.session
                kwargs.setdefault("group_name", group.name if group else "")
                kwargs.setdefault("members", _get_group_members(session, int(pk)))
                kwargs.setdefault(
                    "scheduled_broadcasts",
                    _get_scheduled_broadcasts_for_group(session, int(pk)),
                )
                kwargs.setdefault("format_run_time_msk", _format_run_time_msk)
        return super().render_template(template, **kwargs)

    @expose("/add_members/<int:pk>", methods=["GET", "POST"])
    @has_access
    @permission_name("show")
    def add_members(self, pk: int):
        group = self.datamodel.get(pk)
        if not group:
            flash("Группа не найдена", "danger")
            return redirect(url_for(f"{self.endpoint}.list"))

        session = self.datamodel.session
        member_ids = _get_member_user_ids(session, pk)

        if request.method == "POST":
            raw_ids = request.form.getlist("user_ids")
            try:
                user_ids = [int(value) for value in raw_ids]
            except (TypeError, ValueError):
                flash("Некорректный список пользователей.", "warning")
                return redirect(url_for(f"{self.endpoint}.add_members", pk=str(pk)))

            if not user_ids:
                flash("Выберите хотя бы одного пользователя.", "warning")
                return redirect(url_for(f"{self.endpoint}.add_members", pk=str(pk)))

            try:
                added_count = _add_users_to_group(session, pk, user_ids)
            except SQLAlchemyError as exc:
                session.rollback()
                flash(f"Ошибка добавления пользователей: {exc}", "danger")
                return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

            if added_count:
                flash(
                    f"В группу «{group.name}» добавлено пользователей: {added_count}.",
                    "success",
                )
            else:
                flash("Выбранные пользователи уже состоят в группе.", "info")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        search = (request.args.get("search") or "").strip()
        try:
            page = max(0, int(request.args.get("page", 0)))
        except (TypeError, ValueError):
            page = 0

        query = select(User).order_by(User.id)
        if search:
            search_like = f"%{search}%"
            filters = [
                User.username.ilike(search_like),
                User.admin_insert_name.ilike(search_like),
                User.player_username.ilike(search_like),
                User.first_name.ilike(search_like),
                User.last_name.ilike(search_like),
            ]
            if search.isdigit():
                filters.append(User.id == int(search))
            query = query.where(or_(*filters))

        total_count = session.execute(
            select(func.count()).select_from(query.order_by(None).subquery())
        ).scalar_one()
        users = list(
            session.execute(query.offset(page * MEMBERS_PAGE_SIZE).limit(MEMBERS_PAGE_SIZE))
            .scalars()
            .all()
        )

        total_pages = max(1, (total_count + MEMBERS_PAGE_SIZE - 1) // MEMBERS_PAGE_SIZE)
        if page >= total_pages:
            page = max(0, total_pages - 1)
            users = list(
                session.execute(
                    query.offset(page * MEMBERS_PAGE_SIZE).limit(MEMBERS_PAGE_SIZE)
                )
                .scalars()
                .all()
            )

        return self.render_template(
            "user_group_add_members.html",
            pk=pk,
            group_name=group.name,
            users=users,
            member_ids=member_ids,
            search=search,
            page=page,
            total_pages=total_pages,
            total_count=total_count,
            page_size=MEMBERS_PAGE_SIZE,
        )

    @expose("/remove_members/<int:pk>", methods=["POST"])
    @has_access
    @permission_name("show")
    def remove_members(self, pk: int):
        group = self.datamodel.get(pk)
        if not group:
            flash("Группа не найдена", "danger")
            return redirect(url_for(f"{self.endpoint}.list"))

        raw_ids = request.form.getlist("user_ids")
        try:
            user_ids = [int(value) for value in raw_ids]
        except (TypeError, ValueError):
            flash("Некорректный список пользователей.", "warning")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        if not user_ids:
            flash("Выберите участников для удаления.", "warning")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        session = self.datamodel.session
        try:
            removed_count = _remove_users_from_group(session, pk, user_ids)
        except SQLAlchemyError as exc:
            session.rollback()
            flash(f"Ошибка удаления участников: {exc}", "danger")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        flash(
            f"Из группы «{group.name}» удалено участников: {removed_count}.",
            "success",
        )
        return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

    @expose("/broadcast/<int:pk>", methods=["POST"])
    @has_access
    @permission_name("show")
    def broadcast(self, pk: int):
        group = self.datamodel.get(pk)
        if not group:
            flash("Группа не найдена", "danger")
            return redirect(url_for(f"{self.endpoint}.list"))

        message_text = (request.form.get("message_text") or "").strip()
        if not message_text:
            flash("Текст сообщения не может быть пустым.", "warning")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        broadcast_name = (request.form.get("broadcast_name") or "").strip()
        if not broadcast_name:
            broadcast_name = _default_broadcast_name(group.name)

        send_mode = (request.form.get("send_mode") or "immediate").strip()
        scheduled_at_raw = (request.form.get("scheduled_at") or "").strip()

        session = self.datamodel.session
        members = _get_group_members(session, pk)
        if not members:
            flash("В группе нет участников для рассылки.", "warning")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        user_ids = [member.id for member in members]
        media_id = None
        media_type = None

        try:
            file_bytes, filename, content_type = _read_uploaded_media()
            if file_bytes:
                async def _upload():
                    return await _upload_media_to_telegram(file_bytes, filename, content_type)

                media_id, media_type = _run_telegram_sync(_upload)
        except ValueError as exc:
            flash(str(exc), "warning")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))
        except Exception as exc:
            flash(f"Не удалось загрузить медиа в Telegram: {exc}", "danger")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        if send_mode == "scheduled":
            try:
                run_time = _parse_scheduled_at(scheduled_at_raw)
            except ValueError as exc:
                flash(str(exc), "warning")
                return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

            now_msk = datetime.now(MSK)
            if run_time <= now_msk:
                flash("Время рассылки должно быть позже текущего момента (МСК).", "warning")
                return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

            try:
                _create_scheduled_broadcast(
                    session,
                    group_id=pk,
                    broadcast_name=broadcast_name,
                    text=message_text,
                    user_ids=user_ids,
                    run_time=run_time,
                    media_id=media_id,
                    media_type=media_type,
                )
            except SQLAlchemyError as exc:
                session.rollback()
                flash(f"Ошибка планирования рассылки: {exc}", "danger")
                return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))
            except Exception as exc:
                session.rollback()
                flash(f"Ошибка планирования рассылки: {exc}", "danger")
                return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

            flash(
                f"Рассылка «{broadcast_name}» запланирована на {_format_run_time_msk(run_time)}.",
                "success",
            )
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        try:
            async def _send():
                return await _broadcast_to_users(
                    user_ids, message_text, media_id=media_id, media_type=media_type
                )

            successful, failed = _run_telegram_sync(_send)
        except Exception as exc:
            flash(f"Ошибка рассылки: {exc}", "danger")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        media_note = ""
        if media_id:
            media_note = f" (медиа: {media_type})"

        flash(
            f"Рассылка в группу «{group.name}» завершена{media_note}. "
            f"Доставлено: {successful}, не доставлено: {failed}.",
            "success" if successful else "warning",
        )
        return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

    @expose("/cancel_broadcast/<int:pk>/<int:broadcast_id>", methods=["POST"])
    @has_access
    @permission_name("show")
    def cancel_broadcast(self, pk: int, broadcast_id: int):
        group = self.datamodel.get(pk)
        if not group:
            flash("Группа не найдена", "danger")
            return redirect(url_for(f"{self.endpoint}.list"))

        session = self.datamodel.session
        try:
            cancelled = _cancel_scheduled_broadcast(session, broadcast_id, pk)
        except SQLAlchemyError as exc:
            session.rollback()
            flash(f"Ошибка отмены рассылки: {exc}", "danger")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        if cancelled:
            flash("Запланированная рассылка отменена.", "success")
        else:
            flash("Рассылка не найдена или уже не запланирована.", "warning")
        return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))
