from aiogram import Router
from bot.routers.autoanalize.batch import batch_auto_analyze_router
from bot.routers.autoanalize.autoanaliz import auto_analyze_router

autoanalize_router = Router()

autoanalize_router.include_routers(batch_auto_analyze_router, auto_analyze_router)