"""Idempotent synchronisation of reference data (permissions, system roles, defaults).

Runs on every application start and can be run manually with ``python -m app.cli bootstrap``.
It inserts what is missing and refreshes descriptions, but never overwrites values that
administrators may have changed (settings, achievement texts, notification templates).
"""

from __future__ import annotations

import logging

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Achievement, NotificationTemplate, Permission, PremiumPlan, Role, SystemSetting
from app.security.permissions import PERMISSION_INFO
from app.services.defaults import (
    DEFAULT_ACHIEVEMENTS,
    DEFAULT_NOTIFICATION_TEMPLATES,
    DEFAULT_PREMIUM_PLANS,
    SYSTEM_ROLES,
)
from app.services.settings import SETTING_DEFINITIONS

logger = logging.getLogger(__name__)


async def sync_reference_data(session: AsyncSession) -> None:
    # Permissions: the code is the single source of truth.
    permission_rows = [
        {"code": perm.value, "group": group, "description": description}
        for perm, (group, description) in PERMISSION_INFO.items()
    ]
    statement = insert(Permission).values(permission_rows)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[Permission.code],
            set_={"group": statement.excluded.group, "description": statement.excluded.description},
        )
    )
    await session.execute(delete(Permission).where(Permission.code.not_in([row["code"] for row in permission_rows])))

    # System roles.
    role_statement = insert(Role).values(
        [
            {"code": role.code, "name": role.name, "description": role.description, "is_system": True}
            for role in SYSTEM_ROLES
        ]
    )
    await session.execute(role_statement.on_conflict_do_update(index_elements=[Role.code], set_={"is_system": True}))

    # Settings: insert defaults only; refresh descriptions.
    settings_statement = insert(SystemSetting).values(
        [{"key": d.key, "value": d.default, "description": d.description} for d in SETTING_DEFINITIONS]
    )
    await session.execute(
        settings_statement.on_conflict_do_update(
            index_elements=[SystemSetting.key], set_={"description": settings_statement.excluded.description}
        )
    )

    await session.execute(
        insert(Achievement)
        .values(
            [
                {
                    "code": seed.code,
                    "title": seed.title,
                    "description": seed.description,
                    "icon": seed.icon,
                    "criteria": seed.criteria,
                    "threshold": seed.threshold,
                    "sort_order": index,
                }
                for index, seed in enumerate(DEFAULT_ACHIEVEMENTS)
            ]
        )
        .on_conflict_do_nothing(index_elements=[Achievement.code])
    )

    await session.execute(
        insert(NotificationTemplate)
        .values(
            [
                {"type": seed.type, "title": seed.title, "body": seed.body, "is_critical": seed.is_critical}
                for seed in DEFAULT_NOTIFICATION_TEMPLATES
            ]
        )
        .on_conflict_do_nothing(index_elements=[NotificationTemplate.type])
    )

    # Premium plans: created once; prices and availability are then the super admin's.
    await session.execute(
        insert(PremiumPlan)
        .values(
            [
                {
                    "code": plan.code,
                    "title": plan.title,
                    "description": plan.description,
                    "stars": plan.stars,
                    "days": plan.days,
                    "price_uzs": plan.price_uzs,
                    "sort_order": index,
                }
                for index, plan in enumerate(DEFAULT_PREMIUM_PLANS, start=1)
            ]
        )
        .on_conflict_do_nothing(index_elements=[PremiumPlan.code])
    )
    await session.commit()
    logger.info("Reference data synchronised")
