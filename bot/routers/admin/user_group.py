from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from bot.common.kbds.inline.paginate import PaginatedCallback, PaginatedCheckboxCallback, get_paginated_checkbox_keyboard, get_paginated_keyboard
from bot.common.kbds.inline.user_group import get_user_group_kb, UserGroupCallback
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub
from bot.db.dao import UserDAO, UserGroupDAO
from bot.db.schemas import SGroup

user_group_router = Router()

class UserGroupState(StatesGroup):
    group_name = State()

@user_group_router.message(F.text == AdminKeyboard.get_kb_text().get('users_group'))
async def handle_user_groups(message: Message):
    await message.answer(
        'Выберите действие с группами',
        reply_markup=get_user_group_kb()
    )

@user_group_router.callback_query(UserGroupCallback.filter())
async def handle_user_group_actions(callback: CallbackQuery, callback_data: UserGroupCallback,
                                    state:FSMContext, i18n, session_without_commit):
    action = callback_data.action
    match action:
        case "create_group":
            await callback.message.delete()
            await callback.message.answer('Дайте название новой группы',reply_markup=get_cancel_kb(i18n))
            await state.set_state(UserGroupState.group_name)
        case "delete_group":
            await callback.message.delete()
            groups = await UserGroupDAO(session_without_commit).find_all()
            await callback.message.answer(
                "Выберите группу для удаления:",
                reply_markup=get_paginated_keyboard(
                    items=groups,
                    context='delete_group',
                    get_display_text=lambda group: group.name,
                    get_item_id=lambda group: group.id,
                    page=0,
                    items_per_page=5,
                    with_back_butn=True
                )
            )
        case "add_users":
            await callback.message.delete()
            groups = await UserGroupDAO(session_without_commit).find_all()
            await callback.message.answer(
                "Выберите группу для добавления пользователей:",
                reply_markup=get_paginated_keyboard(
                    items=groups,
                    context='add_users_to_group',
                    get_display_text=lambda group: group.name,
                    get_item_id=lambda group: group.id,
                    page=0,
                    items_per_page=5,
                    with_back_butn=True
                )
            )
        case "delete_users":
            await callback.message.delete()
            groups = await UserGroupDAO(session_without_commit).find_all()
            await callback.message.answer(
                "Выберите группу для удаления пользователей:",
                reply_markup=get_paginated_keyboard(
                    items=groups,
                    context='delete_users_to_group',
                    get_display_text=lambda group: group.name,
                    get_item_id=lambda group: group.id,
                    page=0,
                    items_per_page=5,
                    with_back_butn=True
                )
            )
        case "group_view":
            await callback.answer()
            groups = await UserGroupDAO(session_without_commit).find_all()
            for g in groups:
                users = await UserGroupDAO(session_without_commit).get_users_in_group(g.id)
                if not users:
                    continue
                message = f'<b>Участники группы {g.name}:</b>\n'
                for u in users:
                    message += f'- {u.admin_insert_name or u.username or u.id}\n'
                await callback.message.answer(message)

        case _:
            await callback.message.answer("Неизвестное действие.")

@user_group_router.message(F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")),
                           StateFilter(UserGroupState.group_name))
async def cancel_group_creation(message: Message, state: FSMContext, i18n):
    await state.clear()
    await state.set_state(GeneralStates.admin_panel)
    await message.answer(
        'Выберите действие с группами',
        reply_markup=get_user_group_kb()
    )

@user_group_router.message(F.text, StateFilter(UserGroupState.group_name))
async def create_user_group(message: Message, state: FSMContext, i18n, session_without_commit):
    group_name = message.text.strip()
    await UserGroupDAO(session_without_commit).add(SGroup(name=group_name))
    await session_without_commit.commit()
    await message.answer(f'Группа "{group_name}" успешно создана.', reply_markup=AdminKeyboard.build())
    await state.clear()
    await state.set_state(GeneralStates.admin_panel)
    await message.answer(
        'Выберите действие с группами',
        reply_markup=get_user_group_kb()
    )
    
@user_group_router.callback_query(PaginatedCallback.filter(F.context == "delete_group"))
async def handle_delete_group_pagination(callback: CallbackQuery, callback_data: PaginatedCallback,
                                       session_without_commit, i18n):
    match callback_data.action:
        case "select":
            group_id = callback_data.item_id
            group = await UserGroupDAO(session_without_commit).find_one_or_none_by_id(group_id)
            if group:
                await callback.message.answer(f'Группа "{group.name}" успешно удалена.')
                await UserGroupDAO(session_without_commit).delete_group(group_id)
                await callback.message.answer(
                    'Выберите действие с группами',
                    reply_markup=get_user_group_kb()
                )
            else:
                await callback.message.answer("Группа не найдена.")
            await callback.message.delete()
        case 'prev' | 'next':
            groups = await UserGroupDAO(session_without_commit).find_all()
            keyboard = get_paginated_keyboard(
                items=groups,
                context='delete_group',
                get_display_text=lambda group: group.name,
                get_item_id=lambda group: group.id,
                page=callback_data.page,
                items_per_page=5,
                with_back_butn=True
            )
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        case 'back':
            await callback.message.delete()
            await callback.message.answer(
                'Выберите действие с группами',
                reply_markup=get_user_group_kb()
            )


@user_group_router.callback_query(PaginatedCallback.filter(F.context == "add_users_to_group"))
async def handle_delete_group_pagination(callback: CallbackQuery, callback_data: PaginatedCallback,
                                        state:FSMContext,
                                        session_without_commit, i18n):
    match callback_data.action:
        case "select":
            await callback.message.delete()
            group_id = callback_data.item_id
            await state.update_data(selected_group_id=group_id)
            users = await UserDAO(session_without_commit).find_all()
            await callback.message.answer(
                'Выберите юзеров для добавления в группу',
                reply_markup=get_paginated_checkbox_keyboard(
                    items=users,
                    context="add_users_to_group",
                    get_display_text=lambda user: f"{user.admin_insert_name or user.username or user.id}",
                    get_item_id=lambda user: user.id,
                    selected_ids=set(),
                    page=0,
                    items_per_page=5,
                    with_back_butn=True
                )
            )
        case 'prev' | 'next':
            groups = await UserGroupDAO(session_without_commit).find_all()
            keyboard = get_paginated_keyboard(
                items=groups,
                context='delete_group',
                get_display_text=lambda group: group.name,
                get_item_id=lambda group: group.id,
                page=callback_data.page,
                items_per_page=5,
                with_back_butn=True
            )
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        case 'back':
            await callback.message.delete()
            await callback.message.answer(
                'Выберите действие с группами',
                reply_markup=get_user_group_kb()
            )


@user_group_router.callback_query(PaginatedCheckboxCallback.filter(F.context == 'add_users_to_group'), StateFilter(GeneralStates.admin_panel))
async def process_targets(callback: CallbackQuery, callback_data: PaginatedCheckboxCallback, state: FSMContext, session_without_commit, i18n):
    """
    Обработка чекбокс-пагинации для выбора конкретных пользователей.
    Выбранные id хранятся в FSM state под ключом 'broadcast_specific_selected'.
    """
    await callback.answer()  # быстро закроем loading
    STORAGE_KEY = "add_users_to_group_selected"
    # загрузим текущее состояние выбранных id из state
    data = await state.get_data()
    sel_list = data.get(STORAGE_KEY, [])
    sel_set = set(sel_list)
    # подгружаем всех пользователей для построения клавиатуры
    users = await UserDAO(session_without_commit).find_all()

    # действия: toggle / prev / next / done
    action = callback_data.action
    item_id = int(callback_data.item_id or 0)
    page = int(callback_data.page or 0)

    if action == "toggle":
        if item_id in sel_set:
            sel_set.remove(item_id)
        else:
            sel_set.add(item_id)
        # сохраняем обновлённый набор в state
        await state.update_data({STORAGE_KEY: list(sel_set)})
        kb = get_paginated_checkbox_keyboard(
            items=users,
            context="add_users_to_group",
            get_display_text=lambda u: f"{u.admin_insert_name or u.username or u.id}",
            get_item_id=lambda u: u.id,
            selected_ids=sel_set,
            page=page,
            items_per_page=5,
            with_back_butn=True
        )
        await callback.message.edit_text("Выберите пользователей:", reply_markup=kb)
        return

    if action in ("prev", "next"):
        # просто перестроим клавиатуру на нужной странице
        kb = get_paginated_checkbox_keyboard(
            items=users,
            context="add_users_to_group",
            get_display_text=lambda u: f"{u.admin_insert_name or u.username or u.id}",
            get_item_id=lambda u: u.id,
            selected_ids=sel_set,
            page=page,
            items_per_page=5,
            with_back_butn=True
        )
        await callback.message.edit_text("Выберите пользователей:", reply_markup=kb)
        return
    if action == "back":
        await callback.message.delete()
        groups = await UserGroupDAO(session_without_commit).find_all()
        await callback.message.answer(
                "Выберите группу для добавления пользователей:",
                reply_markup=get_paginated_keyboard(
                    items=groups,
                    context='add_users_to_group',
                    get_display_text=lambda group: group.name,
                    get_item_id=lambda group: group.id,
                    page=0,
                    items_per_page=5,
                    with_back_butn=True
                )
            )
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)
        return

    if action == "done":
        if not sel_set:
            await callback.message.answer("Не выбрано ни одного пользователя.")
            return
        await callback.message.delete()
        state_data = await state.get_data()
        group_id = state_data.get("selected_group_id")
        await UserGroupDAO(session_without_commit).add_users_to_group(group_id, list(sel_set))
        group = await UserGroupDAO(session_without_commit).find_one_or_none_by_id(group_id)
        info = f"Пользователи:"
        for us in sel_set:
            user = await UserDAO(session_without_commit).find_one_or_none_by_id(us)
            info += f"\n- {user.admin_insert_name or user.username or user.id}"
        info += f"\nуспешно добавлены в группу '{group.name}'"
        await callback.message.answer(info)
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)
        return
    
@user_group_router.callback_query(PaginatedCallback.filter(F.context == "delete_users_to_group"))
async def handle_delete_group_pagination(callback: CallbackQuery, callback_data: PaginatedCallback,state:FSMContext, session_without_commit, i18n):
    match callback_data.action:
        case "select":
            await callback.message.delete()
            group_id = callback_data.item_id
            await state.update_data(selected_group_id=group_id)
            group = await UserGroupDAO(session_without_commit).find_one_or_none_by_id(group_id)
            users = await UserGroupDAO(session_without_commit).get_users_in_group(group_id)
            await callback.message.answer(
                f'Выберите юзеров для удаления из группы "{group.name}"',
                reply_markup=get_paginated_checkbox_keyboard(
                    items=users,
                    context="delete_users_to_group",
                    get_display_text=lambda user: f"{user.admin_insert_name or user.username or user.id}",
                    get_item_id=lambda user: user.id,
                    selected_ids=set(),
                    page=0,
                    items_per_page=5,
                    with_back_butn=True
                )
            )
        case 'prev' | 'next':
            groups = await UserGroupDAO(session_without_commit).find_all()
            keyboard = get_paginated_keyboard(
                items=groups,
                context='delete_group',
                get_display_text=lambda group: group.name,
                get_item_id=lambda group: group.id,
                page=callback_data.page,
                items_per_page=5,
                with_back_butn=True
            )
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        case 'back':
            await callback.message.delete()
            await callback.message.answer(
                'Выберите действие с группами',
                reply_markup=get_user_group_kb()
            )

@user_group_router.callback_query(PaginatedCheckboxCallback.filter(F.context == 'delete_users_to_group'), StateFilter(GeneralStates.admin_panel))
async def process_targets(callback: CallbackQuery, callback_data: PaginatedCheckboxCallback, state:
    FSMContext, session_without_commit, i18n):
    await callback.answer() 
    STORAGE_KEY = "delete_users_to_group_selected"
    # загрузим текущее состояние выбранных id из state
    data = await state.get_data()
    sel_list = data.get(STORAGE_KEY, [])
    sel_set = set(sel_list)
    # подгружаем всех пользователей для построения клавиатуры
    state_data = await state.get_data()
    group_id = state_data.get("selected_group_id")
    users = await UserGroupDAO(session_without_commit).get_users_in_group(group_id)

    # действия: toggle / prev / next / done
    action = callback_data.action
    item_id = int(callback_data.item_id or 0)
    page = int(callback_data.page or 0)

    if action == "toggle":
        if item_id in sel_set:
            sel_set.remove(item_id)
        else:
            sel_set.add(item_id)
        # сохраняем обновлённый набор в state
        await state.update_data({STORAGE_KEY: list(sel_set)})
        kb = get_paginated_checkbox_keyboard(
            items=users,
            context="delete_users_to_group",
            get_display_text=lambda u: f"{u.admin_insert_name or u.username or u.id}",
            get_item_id=lambda u: u.id,
            selected_ids=sel_set,
            page=page,
            items_per_page=5,
            with_back_butn=True
        )
        await callback.message.edit_text("Выберите пользователей:", reply_markup=kb)
        return

    if action in ("prev", "next"):
        # просто перестроим клавиатуру на нужной странице
        kb = get_paginated_checkbox_keyboard(
            items=users,
            context="delete_users_to_group",
            get_display_text=lambda u: f"{u.admin_insert_name or u.username or u.id}",
            get_item_id=lambda u: u.id,
            selected_ids=sel_set,
            page=page,
            items_per_page=5,
            with_back_butn=True
        )
        await callback.message.edit_text("Выберите пользователей:", reply_markup=kb)
        return
    if action == "back":
        await callback.message.delete()
        groups = await UserGroupDAO(session_without_commit).find_all()
        await callback.message.answer(
                "Выберите группу для добавления пользователей:",
                reply_markup=get_paginated_keyboard(
                    items=groups,
                    context='add_users_to_group',
                    get_display_text=lambda group: group.name,
                    get_item_id=lambda group: group.id,
                    page=0,
                    items_per_page=5,
                    with_back_butn=True
                )
            )
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)
        return

    if action == "done":
        if not sel_set:
            await callback.message.answer("Не выбрано ни одного пользователя.")
            return
        await callback.message.delete()
        await UserGroupDAO(session_without_commit).remove_users_from_group(group_id, list(sel_set))
        group = await UserGroupDAO(session_without_commit).find_one_or_none_by_id(group_id)
        info = f"Пользователи:"
        for us in sel_set:
            user = await UserDAO(session_without_commit).find_one_or_none_by_id(us)
            info += f"\n- {user.admin_insert_name or user.username or user.id}"
        info += f"\nудалены из группы '{group.name}'"
        await callback.message.answer(info)
        await state.clear()
        await state.set_state(GeneralStates.admin_panel)
        return