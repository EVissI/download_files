from aiogram import Router
from bot.routers.start import start_router
from bot.routers.stat import stat_router
from bot.routers.autoanaliz import auto_analyze_router
from bot.routers.profile import profile_router

setup_router = Router()

setup_router.include_routers(
    start_router,
    stat_router,
    auto_analyze_router,
    profile_router
)