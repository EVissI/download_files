from aiogram import Router
from bot.common.middlewares.sub_middleware import SubscriptionMiddleware
from bot.routers.start import start_router
from bot.routers.stat import stat_router
from bot.routers.autoanaliz import auto_analyze_router
from bot.routers.profile import profile_router
from bot.routers.admin.setup import admin_setup_router
from bot.routers.activate_promo import activate_promo_router
from bot.routers.payment import payment_router
from bot.routers.contact_info import contact_router
setup_router = Router()

auto_analyze_router.message.middleware(SubscriptionMiddleware())

setup_router.include_routers(
    start_router,
    stat_router,
    auto_analyze_router,
    profile_router,
    admin_setup_router,
    activate_promo_router,
    payment_router,
    contact_router
)