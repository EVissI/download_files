from aiogram.fsm.state import State, StatesGroup

class GeneralStates(StatesGroup):
    admin_panel = State()
    promo_view = State()
    excel_view = State()
    payment_view = State()