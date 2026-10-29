"""«📚 Mening mutolaam» in the bot: /oqidim (write today's pages in the diary), /javonim (my shelf in
short) and /kartam («🪪 Kitobxonlik kartam» as a picture). The full pages are in the Mini App."""

from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import access, keyboards, texts
from app.bot.filters import ActiveMember
from app.core.errors import AppError
from app.models import User
from app.models.enums import ShelfStatus
from app.services import reading_journal, share_cards

logger = logging.getLogger(__name__)

router = Router(name="reading")
router.message.filter(ActiveMember())
router.callback_query.filter(ActiveMember())


def _progress(item: dict) -> str:
    if item["pages_total"]:
        return texts.READ_PROGRESS.format(read=item["pages_read"], total=item["pages_total"], percent=item["percent"])
    return texts.READ_PROGRESS_PAGES.format(read=item["pages_read"])


@router.message(Command("oqidim"))
async def log_today(
    message: Message, command: CommandObject, state: FSMContext, db: AsyncSession, member: User
) -> None:
    """/oqidim 25 [izoh] — 25 pages of the book on «O'qiyapman», in today's diary."""
    await state.clear()
    if await access.gate(message, db, member, "shelf"):
        return
    current = await reading_journal.current_reading(db, member)
    if current is None:
        await message.answer(texts.READ_NO_BOOK, reply_markup=keyboards.reading_links())
        return
    item, book = await reading_journal.get_item(db, member, current.id)
    title = html.escape(book.title if book else item.title or "—")
    parts = (command.args or "").split(maxsplit=1)
    if not parts or not parts[0].isdigit():
        stats = await reading_journal.stats(db, member)
        await message.answer(
            texts.READ_HOW.format(title=title, today=stats["today_pages"], streak=stats["streak"]),
            reply_markup=keyboards.reading_links(),
        )
        return
    try:
        await reading_journal.log_pages(
            db, member, item.id, pages=int(parts[0]), note=parts[1] if len(parts) > 1 else None
        )
    except AppError as exc:
        await message.answer(exc.message)
        return
    item, book = await reading_journal.get_item(db, member, item.id)
    described = reading_journal.describe(item, book)
    stats = await reading_journal.stats(db, member)
    text = texts.READ_LOGGED.format(
        title=title,
        pages=int(parts[0]),
        progress=_progress(described),
        today=stats["today_pages"],
        streak=stats["streak"],
    )
    if described["pages_total"] and item.pages_read >= described["pages_total"]:
        text += texts.READ_MAYBE_DONE
    await message.answer(text, reply_markup=keyboards.reading_links())


@router.message(Command("javonim"))
@router.callback_query(F.data == "shelf:open")
async def my_shelf(event: Message | CallbackQuery, state: FSMContext, db: AsyncSession, member: User) -> None:
    message = event.message if isinstance(event, CallbackQuery) else event
    if isinstance(event, CallbackQuery):
        await event.answer()
    else:
        await state.clear()
    if not isinstance(message, Message) or await access.gate(event, db, member, "shelf"):
        return
    items = await reading_journal.shelf(db, member)
    stats = await reading_journal.stats(db, member)
    reading = [item for item in items if item["status"] == ShelfStatus.READING][:5]
    lines = [
        texts.SHELF_LINE.format(title=html.escape(item["title"]), progress=_progress(item)) for item in reading
    ] or [texts.SHELF_NOTHING]
    text = texts.SHELF_SUMMARY.format(
        reading="\n".join(lines),
        want=stats["shelf"].get("WANT", 0),
        finished=stats["shelf"].get("FINISHED", 0),
        week=stats["week_pages"],
        streak=stats["streak"],
        best=stats["best_streak"],
        year=stats["finished_this_year"],
    )
    await message.answer(text, reply_markup=keyboards.reading_links(missions=True))


@router.message(Command("kartam"))
async def my_card(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    """«🪪 Kitobxonlik kartam»: the reader's numbers as a picture to share."""
    await state.clear()
    if await access.gate(message, db, member, "reading_card"):
        return
    from app.bot.setup import resolve_bot_username

    if message.bot is not None:
        await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)
    try:
        data = await share_cards.reading_card_data(
            db, member, share_cards.footer_text(await resolve_bot_username(message.bot))
        )
        image = share_cards.reading_card(data)
    except Exception:
        logger.exception("Reading card failed for %s", member.id)
        await message.answer(texts.FILE_FAILED)
        return
    await message.answer_photo(
        BufferedInputFile(image, filename=share_cards.card_filename(member)),
        caption=texts.CARD_CAPTION,
        reply_markup=keyboards.reading_links(),
    )
