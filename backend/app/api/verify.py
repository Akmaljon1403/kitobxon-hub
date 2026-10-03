"""Public page behind the QR codes on passports and certificates: ``/v/<code>``.

Shows only what is printed on the document itself, so a QR code reveals nothing new.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.api.deps import DbSession
from app.models import Faculty, User
from app.models.enums import UserStatus
from app.security.rate_limit import RateLimit, limit_by_ip
from app.services import certificates as certificate_service
from app.services import passport as passport_service
from app.services.report_pdf import _environment
from app.services.settings import get_setting
from app.utils.timezone import format_date, format_datetime

router = APIRouter(tags=["verification"])
VERIFY_LIMIT = RateLimit("verify", limit=60, window_seconds=60)


@router.get(
    "/v/{code}",
    response_class=HTMLResponse,
    include_in_schema=False,
    dependencies=[Depends(limit_by_ip(VERIFY_LIMIT))],
)
async def verify(code: str, db: DbSession) -> HTMLResponse:
    page = {"valid": False, "icon": "⚠️", "heading": "Kod topilmadi", "rows": []}
    page["state"] = "Bunday hujjat klub tizimida yo'q. Kodni tekshirib, qayta urinib ko'ring."
    code = code[:40]
    member = await passport_service.member_by_code(db, code)
    if member is not None:
        faculty = (
            await db.scalar(select(Faculty.name).where(Faculty.id == member.faculty_id)) if member.faculty_id else None
        )
        active = member.status == UserStatus.ACTIVE
        results = await passport_service.live_results(db, member) if active else None
        page = {
            "valid": active,
            "icon": "🪪" if active else "⛔",
            "heading": "Kitobxon pasporti",
            "state": ("✓ Haqiqiy — 💎 Premium a'zo" if results and results["premium"] else "✓ Haqiqiy — faol a'zo")
            if active
            else "A'zolik to'xtatilgan",
            "rows": [
                ("A'zo", f"{member.last_name} {member.first_name}"),
                ("A'zo raqami", passport_service.member_number(member)),
                ("Fakultet", faculty or "—"),
                ("Kurs, guruh", f"{member.course or '—'}-kurs, {member.group_name or '—'}"),
                ("A'zo bo'lgan sana", format_date(member.registered_at or member.created_at)),
            ],
        }
        if results:
            page["stats"] = [
                (f"{results['points']:,}".replace(",", " "), "ball"),
                (f"{results['rank']}-o'rin" if results["rank"] else "—", "umumiy reyting"),
                (f"{results['month_rank']}-o'rin" if results["month_rank"] else "—", "shu oy"),
                (str(results["books"]), "kitob o'qigan"),
                (str(results["events"]), "tadbirda qatnashgan"),
                (str(results["tests"]), "testdan o'tgan"),
                (str(results["achievements"]), "yutuq"),
                (str(len(results["certificates"])), "sertifikat"),
            ]
            page["certificates"] = results["certificates"]
    else:
        certificate = await certificate_service.by_code(db, code)
        if certificate is not None:
            owner = await db.get(User, certificate.user_id)
            revoked = certificate.revoked_at is not None
            page = {
                "valid": not revoked,
                "icon": "⛔" if revoked else "🎓",
                "heading": "Sertifikat",
                "state": f"Bekor qilingan ({format_date(certificate.revoked_at)})"
                if revoked
                else "✓ Haqiqiy sertifikat",
                "rows": [
                    ("Kimga berilgan", f"{owner.last_name} {owner.first_name}" if owner else "—"),
                    ("Sertifikat", certificate.title),
                    ("Nima uchun", certificate.description),
                    ("Berilgan sana", format_date(certificate.issued_at)),
                    ("Tekshirish kodi", certificate_service.display_code(certificate.verify_code)),
                ],
            }
    html = (
        _environment()
        .get_template("verify.html")
        .render(
            **page,
            organization=await get_setting(db, "org.organization_name"),
            club=await get_setting(db, "org.club_name"),
            checked_at=format_datetime(datetime.now(UTC)),
        )
    )
    return HTMLResponse(html, status_code=200 if page["rows"] else 404)
