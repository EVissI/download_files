from aiogram import Router
from bot.routers.autoanalize.batch import batch_auto_analyze_router
from bot.routers.autoanalize.autoanaliz import auto_analyze_router

setup_autoanalize_router = Router()

setup_autoanalize_router.include_routers(batch_auto_analyze_router, auto_analyze_router)