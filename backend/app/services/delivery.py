"""Files the bot sends to a member on request: the passport image and certificate PDFs."""

from __future__ import annotations

import html
import logging
from collections.abc import Awaitable

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ServiceUnavailableError
from app.models import Certificate, User
from app.services import certificates as certificate_service
from app.services import passport as passport_service

logger = logging.getLogger(__name__)


def optional_bot() -> Bot | None:
    from app.bot.setup import get_bot_runtime

    runtime = get_bot_runtime()
    return runtime.bot if runtime is not None else None


def runtime_bot() -> Bot:
    bot = optional_bot()
    if bot is None:
        raise ServiceUnavailableError("BOT_UNAVAILABLE", "Bot hozir ishlamayapti. Birozdan keyin urinib ko'ring.")
    return bot


async def explain_failures(sending: Awaitable[None]) -> None:
    """Turn Telegram errors into messages a member understands."""
    try:
        await sending
    except TelegramForbiddenError as exc:
        raise ConflictError(
            "BOT_BLOCKED", "Bot sizga yoza olmadi. Botni bloklamaganingizni tekshiring va unda /start bosing."
        ) from exc
    except (TelegramAPIError, OSError, TimeoutError) as exc:
        logger.warning("Sending a file through the bot failed: %s", exc)
        raise ServiceUnavailableError(
            "BOT_UNAVAILABLE", "Faylni bot orqali yuborib bo'lmadi. Birozdan keyin qayta urinib ko'ring."
        ) from exc


def passport_caption(user: User) -> str:
    return (
        f"🪪 <b>Kitobxon pasporti</b> · {passport_service.member_number(user)}\n"
        "Rasmni saqlab olishingiz yoki do'stlaringizga ulashishingiz mumkin."
    )


async def send_passport(bot: Bot, session: AsyncSession, user: User, *, as_file: bool = False) -> None:
    """As a photo (quick to view) or as a PNG file (full quality, for printing)."""
    image = await passport_service.render(session, user, bot=bot)
    upload = BufferedInputFile(image, filename=passport_service.filename(user))
    if as_file:
        await bot.send_document(user.telegram_id, upload, caption=passport_caption(user))
    else:
        await bot.send_photo(user.telegram_id, upload, caption=passport_caption(user))


async def send_certificate(bot: Bot, session: AsyncSession, user: User, certificate: Certificate) -> None:
    data = await certificate_service.pdf_bytes(session, certificate)
    await bot.send_document(
        user.telegram_id,
        BufferedInputFile(data, filename=certificate_service.filename(certificate)),
        caption=f"🎓 <b>{html.escape(certificate.title, quote=False)}</b>",
    )


async def send_portfolio(bot: Bot, session: AsyncSession, user: User) -> None:
    """The portfolio as a PDF (to show) and as Word (to edit or add to an application)."""
    from app.services import document_render, documents, portfolio

    data = await portfolio.render_pdf(session, user)
    await bot.send_document(
        user.telegram_id,
        BufferedInputFile(data, filename=portfolio.filename(user)),
        caption="🗂 <b>Kitobxonlik portfoliosi</b> — klubdagi barcha natijalaringiz bitta hujjatda. "
        "Rezyume va grant arizalariga ilova qilishingiz mumkin.",
    )
    document = await documents.portfolio_document(session, user)
    await bot.send_document(
        user.telegram_id,
        BufferedInputFile(await document_render.render(document, "docx"), filename=f"{document.filename}.docx"),
        caption="📝 Portfolio Word'da — kerak bo'lsa tahrirlab olasiz.",
    )


async def send_statement(bot: Bot, session: AsyncSession, user: User, fmt: str) -> None:
    """«Faoliyat ma'lumotnomasi» of this study year (PDF or Word)."""
    from app.services import document_render, documents

    document = await documents.statement(session, user)
    await bot.send_document(
        user.telegram_id,
        BufferedInputFile(await document_render.render(document, fmt), filename=f"{document.filename}.{fmt}"),
        caption="📄 <b>Faoliyat ma'lumotnomasi</b> — o'quv yili davomidagi klub faoliyatingiz. QR kod orqali "
        "istalgan kishi tekshira oladi.",
    )
