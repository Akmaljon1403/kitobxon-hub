from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    first_name = State()
    last_name = State()
    phone = State()
    faculty = State()
    course = State()
    group = State()
    confirm = State()
