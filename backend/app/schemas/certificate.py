from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import CertificateKind


class CertificateOut(BaseModel):
    id: uuid.UUID
    kind: CertificateKind
    place: int | None
    title: str
    description: str
    issued_at: datetime
    code: str
    verify_url: str | None = None  # the public page anyone can open to check the certificate


class CertificateMemberOut(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str
    member_number: str


class AdminCertificateOut(CertificateOut):
    member: CertificateMemberOut
    revoked_at: datetime | None
    revoke_reason: str | None


class CertificateIssueIn(BaseModel):
    user_id: uuid.UUID
    title: str = Field(min_length=3, max_length=120, description="Shown in lists, e.g. «Faol kitobxon»")
    description: str = Field(
        min_length=10, max_length=400, description="Printed under the name, e.g. «... uchun taqdim etiladi.»"
    )
    place: int | None = Field(default=None, ge=1, le=3)


class DownloadLinkIn(BaseModel):
    kind: Literal["passport", "certificate", "portfolio"]
    id: uuid.UUID | None = Field(default=None, description="The certificate (not needed for the passport or portfolio)")


class DownloadLinkOut(BaseModel):
    url: str
    filename: str
    expires_in: int


class PassportThemeOut(BaseModel):
    code: str
    title: str
    premium: bool
    colors: list[str]  # dark, light, accent (for the picker)
    selected: bool


class PassportThemeIn(BaseModel):
    theme: str = Field(max_length=16)
