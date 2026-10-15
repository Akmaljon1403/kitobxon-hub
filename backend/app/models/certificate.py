"""Certificates (PDF) for winners: places 1-3 of a test, of the monthly ranking, or issued by hand."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, SmallInteger, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import CertificateKind


class CertificateTemplate(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """An admin-built certificate design: an uploaded page (PNG/JPG/PDF) and the elements placed on it.

    Each element (name, QR, seal, signature, date, …) carries its own position, size, font and colour,
    so the text sits exactly where the admin wants on their own design — no readability overlay is drawn.
    Certificates can be issued automatically (test winners) or by hand as a gift from a chosen template.
    """

    __tablename__ = "certificate_templates"
    __table_args__ = (
        # At most one template is the default used for automatic certificates.
        Index(
            "uq_certificate_templates_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default AND deleted_at IS NULL"),
        ),
    )

    name: Mapped[str] = mapped_column(String(160))
    # The uploaded design, fitted to object storage; a flat paper is used when none is set.
    background_key: Mapped[str | None] = mapped_column(String(512))
    # The prepared background's pixel size, so the editor and the PDF keep the same aspect (no stretch).
    bg_width: Mapped[int] = mapped_column(Integer, default=1754, server_default="1754")
    bg_height: Mapped[int] = mapped_column(Integer, default=1240, server_default="1240")
    # [{type, x, y, w, size, font, color, align, bold, italic, content}, …]; validated by the service.
    elements: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Certificate(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "certificates"
    __table_args__ = (
        CheckConstraint("place IS NULL OR place BETWEEN 1 AND 3", name="place_range"),
        Index("ix_certificates_user_id_issued_at", "user_id", "issued_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[CertificateKind] = mapped_column(enum_column(CertificateKind))
    place: Mapped[int | None] = mapped_column(SmallInteger)
    # "«O'tkan kunlar» bilim testi", "Oktabr oyi reytingi", ...
    title: Mapped[str] = mapped_column(String(255))
    # The sentence under the name, e.g. "bilim testida 1-o'rinni egallagani uchun".
    description: Mapped[str] = mapped_column(Text)
    test_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tests.id", ondelete="SET NULL"))
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    period: Mapped[str | None] = mapped_column(String(7))  # YYYY-MM for monthly certificates
    # One certificate per achievement (e.g. "test:<id>:<user>"), so re-running jobs is harmless.
    dedup_key: Mapped[str] = mapped_column(String(128), unique=True)
    # Printed on the certificate and in its QR code; anyone can check it at /v/<code>.
    verify_code: Mapped[str] = mapped_column(String(16), unique=True)
    issued_at: Mapped[datetime] = mapped_column(server_default=func.now())
    issued_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    revoked_at: Mapped[datetime | None] = mapped_column()
    revoke_reason: Mapped[str | None] = mapped_column(Text)
    file_key: Mapped[str | None] = mapped_column(String(512))
    # One of app.services.certificate_designs (taken in turn), or "custom" for an uploaded background.
    design: Mapped[str | None] = mapped_column(String(32))
    background_key: Mapped[str | None] = mapped_column(String(512))  # the uploaded background, if any
    # An admin-built design (app.services.certificate_templates). When set, it is drawn instead of ``design``.
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("certificate_templates.id", ondelete="SET NULL"))
    downloads: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    design_changes: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
