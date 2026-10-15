from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CertificateKind

_HEX = r"^#[0-9a-fA-F]{6}$"
# The pieces an admin can place on a certificate design. Images: qr, seal, logo (square boxes).
ElementType = Literal[
    "name",
    "cert_title",
    "description",
    "place",
    "date",
    "member_number",
    "organization",
    "club",
    "signer",
    "code",
    "qr",
    "seal",
    "logo",
    "text",
]


class TemplateElement(BaseModel):
    """One positioned element. x/y/w are percentages of the page (top-left anchored)."""

    model_config = ConfigDict(extra="forbid")

    type: ElementType
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    w: float = Field(ge=1, le=100)
    size: float = Field(default=18, ge=4, le=200, description="Font size in points (ignored for images)")
    font: Literal["serif", "sans", "mono"] = "serif"
    color: str = Field(default="#1c2b24", pattern=_HEX)
    align: Literal["left", "center", "right"] = "center"
    bold: bool = False
    italic: bool = False
    # Image variant (seal/logo): on a dark design choose «light».
    variant: Literal["auto", "light", "dark"] = "auto"
    content: str = Field(default="", max_length=240, description="The literal text for a «text» element")


class TemplateUpsertIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    elements: list[TemplateElement] = Field(default_factory=list, max_length=40)
    is_default: bool = False


class TemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    has_background: bool
    bg_width: int
    bg_height: int
    elements: list[TemplateElement]
    is_default: bool
    updated_at: datetime


class CertificateOut(BaseModel):
    id: uuid.UUID
    kind: CertificateKind
    place: int | None
    title: str
    description: str
    issued_at: datetime
    code: str
    verify_url: str | None = None  # the public page anyone can open to check the certificate
    design: str | None = None


class CertificateRightsOut(BaseModel):
    can_download: bool
    downloads_left: int | None = Field(description="Free downloads left; null = unlimited (Premium)")
    premium: bool
    can_change_design: bool
    design_changes_left: int


class MyCertificateOut(CertificateOut):
    rights: CertificateRightsOut


class DesignOut(BaseModel):
    code: str
    title: str


class DesignIn(BaseModel):
    design: str = Field(min_length=2, max_length=32)


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
    template_id: uuid.UUID | None = Field(default=None, description="An admin-built design to use")
    message: str | None = Field(
        default=None, max_length=1000, description="A personal note sent with the certificate as a gift"
    )


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
