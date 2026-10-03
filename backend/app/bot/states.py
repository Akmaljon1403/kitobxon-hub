from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    first_name = State()
    last_name = State()
    phone = State()
    faculty = State()
    course = State()
    group = State()
    confirm = State()


class AttendanceCode(StatesGroup):
    """The member pressed «✅ Davomat» while attendance is open; the next text is the code."""

    waiting = State()


class SupportCompose(StatesGroup):
    """A member is writing to the club's administrators."""

    waiting = State()


class SupportReply(StatesGroup):
    """An administrator is answering a member (the ticket id is in the state data)."""

    waiting = State()


class FeedbackComment(StatesGroup):
    """A member is writing a comment about an event (the event id is in the state data)."""

    waiting = State()


class PassportPhoto(StatesGroup):
    """A member is sending a picture for their Kitobxon passport."""

    waiting = State()
