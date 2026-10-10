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


class CardReceipt(StatesGroup):
    """A member paid to the club's card and is sending the receipt (plan or amount in the data)."""

    waiting = State()


class CardReject(StatesGroup):
    """The super admin is writing why a card payment is rejected (payment id in the data)."""

    waiting = State()


class ChannelPostEdit(StatesGroup):
    """An admin is writing a new text for an automatic channel post (post id in the data)."""

    waiting = State()


class ChannelStickers(StatesGroup):
    """An admin is sending stickers to be used in the channel posts (/stiker)."""

    waiting = State()


class CustomEmojiCollect(StatesGroup):
    """An admin is sending premium emoji to use inside the bot's messages (/emoji)."""

    waiting = State()
