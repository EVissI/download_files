from aiogram import Router
from bot.common.middlewares.sub_middleware import AnalizMiddleware,ShortBoardMiddleware, HintsMiddleware
from bot.routers.start import start_router
from bot.routers.stat import stat_router
from bot.routers.autoanalize.setup import setup_autoanalize_router
from bot.routers.profile import profile_router
from bot.routers.admin.setup import admin_setup_router
from bot.routers.activate_promo import activate_promo_router
from bot.routers.payment import payment_router
from bot.routers.contact_info import contact_router
from bot.routers.short_board import short_board_router
from bot.routers.hint_viewer_router import hint_viewer_router
from bot.routers.file_router import file_router
from bot.routers.pokaz import pokaz_router
setup_router = Router()

short_board_router.message.middleware(ShortBoardMiddleware())
hint_viewer_router.message.middleware(HintsMiddleware())

setup_router.include_routers(
    file_router,  # Должен быть первым для перехвата файлов вне FSM
    start_router,
    stat_router,
    setup_autoanalize_router,
    profile_router,
    admin_setup_router,
    activate_promo_router,
    payment_router,
    contact_router,
    short_board_router,
    hint_viewer_router,
    pokaz_router
)