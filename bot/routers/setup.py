from aiogram import Router
from bot.routers.download_flie import download_router
from bot.routers.start import start_router
from bot.routers.admin.setup import admin_setup_router
from bot.routers.stat import stat_router
from bot.routers.autoanaliz import auto_analyze_router


setup_router = Router()

setup_router.include_routers(
    start_router,
    download_router,
    admin_setup_router,
    stat_router,
    auto_analyze_router
)