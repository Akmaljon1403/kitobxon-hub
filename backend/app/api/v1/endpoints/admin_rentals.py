"""Super admin: «🏢 Ijara» — copies of Kitobxon Hub rented to other organisations (only on the owner's
own server): the signing key, the organisations, their licence keys and payments."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.api.deps import DbSession, SuperAdminDep
from app.services import rentals

router = APIRouter(prefix="/admin/rentals", tags=["admin: rentals"])


class KeyIn(BaseModel):
    private_pem: str | None = Field(default=None, max_length=2000, description="A key made earlier with licence_tool")


class OrganizationIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    contact_person: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    telegram: str | None = Field(default=None, max_length=64)
    plan: Literal["SMALL", "MEDIUM", "LARGE", "CUSTOM"] = "MEDIUM"
    max_members: int | None = Field(default=None, ge=1, le=1_000_000)
    price_uzs: int | None = Field(default=None, ge=0, le=10_000_000_000)
    billing: Literal["YEARLY", "MONTHLY"] = "YEARLY"
    server_url: str | None = Field(default=None, max_length=255)
    bot_username: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=2000)
    archived: bool = False


class LicenceIn(BaseModel):
    expires_on: date
    max_members: int | None = Field(default=None, ge=1, le=1_000_000)


class PaymentIn(BaseModel):
    amount_uzs: int = Field(gt=0, le=10_000_000_000)
    paid_on: date
    note: str | None = Field(default=None, max_length=255)


@router.get("", summary="The key, the organisations and the totals")
async def overview(_: SuperAdminDep, db: DbSession) -> dict[str, Any]:
    return await rentals.overview(db)


@router.post("/key", summary="Make the owner's signing key (once)")
async def create_key(payload: KeyIn, current: SuperAdminDep, db: DbSession) -> dict[str, str]:
    row = await rentals.create_key(db, actor_id=current.user.id, private_pem=payload.private_pem)
    return {"public_key": row.public_key}


@router.post("/organizations", status_code=status.HTTP_201_CREATED, summary="A new organisation")
async def create(payload: OrganizationIn, current: SuperAdminDep, db: DbSession) -> dict[str, Any]:
    org = await rentals.save(db, actor_id=current.user.id, organization_id=None, data=payload.model_dump())
    return await rentals.details(db, org.id)


@router.get("/organizations/{organization_id}", summary="An organisation with its licences and payments")
async def details(organization_id: uuid.UUID, _: SuperAdminDep, db: DbSession) -> dict[str, Any]:
    return await rentals.details(db, organization_id)


@router.put("/organizations/{organization_id}", summary="Change an organisation")
async def update(
    organization_id: uuid.UUID, payload: OrganizationIn, current: SuperAdminDep, db: DbSession
) -> dict[str, Any]:
    await rentals.save(db, actor_id=current.user.id, organization_id=organization_id, data=payload.model_dump())
    return await rentals.details(db, organization_id)


@router.post("/organizations/{organization_id}/licences", summary="Give a licence key")
async def issue(
    organization_id: uuid.UUID, payload: LicenceIn, current: SuperAdminDep, db: DbSession
) -> dict[str, Any]:
    return await rentals.issue(
        db,
        actor_id=current.user.id,
        organization_id=organization_id,
        expires_on=payload.expires_on,
        max_members=payload.max_members,
    )


@router.post("/organizations/{organization_id}/payments", status_code=status.HTTP_201_CREATED, summary="A payment")
async def add_payment(
    organization_id: uuid.UUID, payload: PaymentIn, current: SuperAdminDep, db: DbSession
) -> dict[str, Any]:
    row = await rentals.add_payment(
        db, actor_id=current.user.id, organization_id=organization_id, **payload.model_dump()
    )
    return {"id": row.id}


@router.delete("/payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a payment")
async def delete_payment(payment_id: uuid.UUID, current: SuperAdminDep, db: DbSession) -> Response:
    await rentals.delete_payment(db, actor_id=current.user.id, payment_id=payment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
