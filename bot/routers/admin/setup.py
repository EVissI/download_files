from aiogram import Router
from bot.common.filters.role_filter import RoleFilter
from bot.db.models import User
from bot.routers.admin.command_router import commands_router
from bot.routers.admin.excel_view.setup import excel_setup_router

admin_setup_router = Router()
admin_setup_router.message.filter(RoleFilter(
                                        User.Role.ADMIN.value
                                        ))
admin_setup_router.include_routers(
    commands_router,
    excel_setup_router
)