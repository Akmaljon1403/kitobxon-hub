"""Optional AI drafting of report wording with the Claude API.

The model receives only the facts snapshot (loaded from the database) and the admin's own
notes, and is told to use nothing else. It writes formal Uzbek prose; it never decides any
fact. Whatever it returns is still checked for unknown numbers (``reports.number_issues``)
and must be reviewed and approved by an admin before a PDF is produced.

Configuration: ``AI_API_KEY`` (Anthropic API key) and ``AI_MODEL`` (default claude-opus-5-5).
Without a key the template draft is used instead.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import anthropic

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.models import Report
from app.models.enums import ReportKind

logger = logging.getLogger(__name__)

# Models that accept the server-side refusal fallback ("default" form).
_FALLBACK_MODELS = ("claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5")

SYSTEM_PROMPT = """\
Siz universitet kitobxonlar klubining rasmiy hisobotlarini yozuvchi yordamchisiz.
Vazifa: berilgan FAKTLAR va ADMIN YOZUVLARI asosida o'zbek tilida (lotin yozuvida),
rasmiy-ish uslubida hisobot matnini yozish (bitta tadbir, davr faoliyati yoki umumiy mavzu).

Qat'iy qoidalar:
- Faqat berilgan faktlar va admin yozuvlaridagi ma'lumotlardan foydalaning.
- Hech qanday raqam, sana, ism, joy, natija yoki yutuqni o'ylab topmang. Faktlarda bo'lmagan
  raqamni yozmang (masalan, foiz yoki sonni o'zingiz hisoblamang).
- Biror bo'lim uchun ma'lumot berilmagan bo'lsa, umumiy va faktlarsiz bitta jumla yozing yoki
  bo'limni tashlab keting.
- Matnni so'rovda ko'rsatilgan sarlavhalar bilan yozing (har biri alohida qatorda, "## " bilan).
- Sarlavhalardan tashqari belgilash (qalin, ro'yxat belgisi, jadval) ishlatmang; xatboshilarni
  bo'sh qator bilan ajrating.
- Faqat hisobot matnini qaytaring: kirish so'zi yoki izohsiz."""


@dataclass(frozen=True)
class AiDraft:
    text: str
    model: str


def is_configured() -> bool:
    return get_settings().ai_api_key is not None


HEADINGS = {
    ReportKind.EVENT: ("Kirish", "Tadbirning borishi", "Ishtirok", "Natijalar", "Xulosa", "Takliflar"),
    ReportKind.PERIOD: ("Kirish", "Tadbirlar", "A'zolar va kitobxonlik", "Eng faol a'zolar", "Xulosa", "Takliflar"),
    ReportKind.GENERAL: ("Kirish", "Amalga oshirilgan ishlar", "Natijalar", "Xulosa", "Takliflar"),
}


def build_prompt(report: Report) -> str:
    notes = {
        "hisobot_nomi": report.title,
        "maqsad": report.objective,
        "faoliyat_tavsifi": report.activity_description,
        "natijalar": report.results,
        "xulosa": report.conclusion,
        "takliflar": report.recommendations,
    }
    return (
        "FAKTLAR (ma'lumotlar bazasidan):\n"
        + json.dumps(report.facts_snapshot or {}, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n\nADMIN YOZUVLARI:\n"
        + json.dumps({key: value for key, value in notes.items() if value}, ensure_ascii=False, indent=2)
        + "\n\nSARLAVHALAR:\n"
        + "\n".join(f"## {heading}" for heading in HEADINGS[ReportKind(report.kind)])
        + "\n\nShu ma'lumotlar asosida hisobot matnini yozing."
    )


def _client() -> anthropic.AsyncAnthropic:
    settings = get_settings()
    assert settings.ai_api_key is not None
    return anthropic.AsyncAnthropic(api_key=settings.ai_api_key.get_secret_value(), timeout=180.0, max_retries=2)


async def draft_report(report: Report) -> AiDraft:
    if not is_configured():
        raise ServiceUnavailableError(
            "AI_NOT_CONFIGURED", "AI yordamchi sozlanmagan. «Shablon bo'yicha qoralama» tugmasidan foydalaning."
        )
    model = get_settings().ai_model
    extra: dict[str, object] = {}
    if model in _FALLBACK_MODELS:
        # If a safety classifier declines, the API retries on Anthropic's recommended model.
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    try:
        response = await _client().beta.messages.create(
            model=model,
            max_tokens=16000,
            output_config={"effort": "medium"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_prompt(report)}],
            **extra,  # type: ignore[arg-type]
        )
    except anthropic.AuthenticationError as exc:
        logger.error("AI drafting: invalid API key")
        raise ServiceUnavailableError("AI_AUTH_FAILED", "AI kaliti noto'g'ri. AI_API_KEY ni tekshiring.") from exc
    except anthropic.RateLimitError as exc:
        raise ServiceUnavailableError("AI_BUSY", "AI hozir band. Bir daqiqadan so'ng qayta urinib ko'ring.") from exc
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
        logger.warning("AI drafting failed: %s", exc)
        raise ServiceUnavailableError(
            "AI_UNAVAILABLE", "AI bilan bog'lanib bo'lmadi. Keyinroq urinib ko'ring."
        ) from exc

    if response.stop_reason == "refusal":
        raise ServiceUnavailableError(
            "AI_REFUSED", "AI bu hisobotni yozishni rad etdi. Shablon bo'yicha qoralamadan foydalaning."
        )
    text = "\n".join(block.text for block in response.content if block.type == "text").strip()
    if not text:
        raise ServiceUnavailableError("AI_EMPTY", "AI bo'sh javob qaytardi. Qayta urinib ko'ring.")
    if response.stop_reason == "max_tokens":
        logger.warning("AI draft was cut at max_tokens (report %s)", report.id)
    return AiDraft(text=text, model=response.model)
