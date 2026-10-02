"""Certificates (PDF) for winners: places 1-3 of a test, of the monthly ranking, or issued by hand."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import CertificateKind


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
