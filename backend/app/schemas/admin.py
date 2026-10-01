from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PermissionOut(BaseModel):
    code: str
    group: str
    description: str


class AdminSelfOut(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    roles: list[str]
    permissions: list[str]
    is_super_admin: bool


class AdminOut(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str
    telegram_username: str | None
    roles: list[str]
    direct_permissions: list[str]
    effective_permissions: list[str]


class AppointAdminIn(BaseModel):
    user_id: uuid.UUID
    permissions: list[str] = Field(default_factory=list, max_length=100)
    extra_roles: list[str] = Field(default_factory=list, max_length=20)


class AdminPermissionsIn(BaseModel):
    permissions: list[str] = Field(max_length=100)


class AdminRolesIn(BaseModel):
    roles: list[str] = Field(min_length=1, max_length=20)


class RoleOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]


class RoleCreateIn(BaseModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,31}$", description="Upper-case identifier, e.g. EVENT_MANAGER")
    name: str = Field(min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=1000)
    permissions: list[str] = Field(default_factory=list, max_length=100)


class RoleUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=64)
    description: str | None = Field(default=None, max_length=1000)
    permissions: list[str] | None = Field(default=None, max_length=100)


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_name: str | None
    action: str
    entity_type: str
    entity_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    reason: str | None
    request_id: str | None
    created_at: datetime
