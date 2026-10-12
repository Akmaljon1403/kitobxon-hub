"""«🏢 Ijara» — the owner's panel for copies of Kitobxon Hub rented to other organisations.

Every organisation runs its own copy (its own server, database and bot), so their data never meets
the club's or each other's. On the owner's own server these tables only keep the paperwork:

* ``LicenceIssuer`` — the owner's signing key (made in the panel; the private half is stored encrypted);
* ``RentalOrganization`` — who rents a copy, the plan, the contact and where their copy runs;
* ``RentalLicence`` — every licence key given to an organisation (until when, how many members);
* ``RentalPayment`` — what the organisation paid.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LicenceIssuer(Base):
    __tablename__ = "licence_issuer"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    private_key_enc: Mapped[str] = mapped_column(Text)  # AES-GCM with a key derived from SECRET_KEY
    public_key: Mapped[str] = mapped_column(String(128))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class RentalOrganization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rental_organizations"
    __table_args__ = (CheckConstraint("max_members IS NULL OR max_members > 0", name="max_members_positive"),)

    name: Mapped[str] = mapped_column(String(200))
    contact_person: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(40))
    telegram: Mapped[str | None] = mapped_column(String(64))
    plan: Mapped[str] = mapped_column(String(16), default="MEDIUM", server_default="MEDIUM")
    max_members: Mapped[int | None] = mapped_column(Integer)
    price_uzs: Mapped[int | None] = mapped_column(BigInteger)  # the agreed price for one billing period
    billing: Mapped[str] = mapped_column(String(16), default="YEARLY", server_default="YEARLY")
    server_url: Mapped[str | None] = mapped_column(String(255))
    bot_username: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column()


class RentalLicence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rental_licences"
    __table_args__ = (Index("ix_rental_licences_organization_id", "organization_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rental_organizations.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(Text)
    expires_on: Mapped[date] = mapped_column()
    max_members: Mapped[int | None] = mapped_column(Integer)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    issued_at: Mapped[datetime] = mapped_column(server_default=func.now())


class RentalPayment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rental_payments"
    __table_args__ = (
        CheckConstraint("amount_uzs > 0", name="amount_positive"),
        Index("ix_rental_payments_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rental_organizations.id", ondelete="CASCADE"))
    amount_uzs: Mapped[int] = mapped_column(BigInteger)
    paid_on: Mapped[date] = mapped_column()
    note: Mapped[str | None] = mapped_column(String(255))
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
