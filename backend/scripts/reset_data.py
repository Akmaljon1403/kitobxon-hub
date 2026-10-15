"""One-time cleanup before the public launch: remove the data entered during testing (members, event
history, attendance, tests, payments, support, notifications, …) and keep the club's configuration and
identity (super admins, settings, feature switches, texts, faculties, the book catalogue, premium plans,
the taught stickers/emoji and the rental signing key).

SAFE BY DEFAULT: running it prints what WOULD be deleted (a dry run) and changes nothing. It deletes only
when you pass --apply AND type the confirmation phrase, and everything happens in one transaction, so a
failure rolls back with no half-cleared database. It refuses to touch a database that has no super admin
(so you never lock yourself out).

    python scripts/reset_data.py            # dry run: just the counts
    python scripts/reset_data.py --apply    # really delete (asks you to type a phrase)

WHAT IT KEEPS:
    super admins and their roles/permissions, roles, permissions, system_settings, feature_flags,
    text_overrides, notification_templates, faculties, books + book_quotes, campaigns, seasons,
    premium_plans, custom_emojis, channel_stickers, licence_issuer.

WHAT IT REMOVES:
    every non-super-admin user (which, by the database's own cascade rules, also removes that member's
    attendance, test attempts, scores, reading, certificates, missions, rewards, premium, payments,
    contributions, support, notifications and sign-in tokens), plus the standalone operational tables:
    events (and shifts/sessions/tokens/registrations/feedback), tests (and questions/options),
    notifications, channel_posts, payments_chat_links, reports (and photos), giveaways,
    referral_contests, rental organizations/licences/payments, contributions and the audit log.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import func, select, text

from app.core.database import get_engine, get_session_factory
from app.models import Role, User, UserRole
from app.models.enums import SystemRole

# Operational data emptied directly. Only "parents" are listed; TRUNCATE … CASCADE also clears each one's
# children (events → shifts/sessions/tokens/registrations/feedback, tests → questions/options/attempts/…,
# support_tickets → messages, contributions → likes, reports → photos, rentals → licences/payments). This
# runs BEFORE the members are removed, because some ledgers (scores, payments, certificates) are protected
# from an accidental member delete (ON DELETE RESTRICT).
WIPE_TABLES = (
    # members' activity and ledgers
    "score_transactions",
    "attendance_records",
    "attendance_sessions",
    "test_attempts",
    "tests",
    "certificates",
    "user_achievements",
    "user_notification_settings",
    "user_missions",
    "book_reads",
    "book_reflections",
    "reading_logs",
    "shelf_items",
    "saved_quotes",
    "contributions",
    "user_rewards",
    "reward_codes",
    "card_payments",
    "payments",
    "premium_subscriptions",
    "premium_discounts",
    "support_tickets",
    "login_tokens",
    "bot_fsm_states",
    # club-wide operational history
    "events",
    "notifications",
    "channel_posts",
    "payments_chat_links",
    "reports",
    "giveaways",
    "referral_contests",
    "rental_organizations",
    "audit_logs",
)


async def _counts(session) -> dict[str, int]:
    members = await session.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.id.not_in(
                select(UserRole.user_id)
                .join(Role, Role.id == UserRole.role_id)
                .where(Role.code == SystemRole.SUPER_ADMIN)
            )
        )
    )
    counts = {"non-super-admin users": int(members or 0)}
    for table_name in WIPE_TABLES:
        counts[table_name] = int(await session.scalar(text(f"SELECT count(*) FROM {table_name}")) or 0)  # noqa: S608 — WIPE_TABLES is a trusted constant, not user input
    return counts


async def report() -> int:
    """Print what would be deleted; return the number of super admins (0 means refuse to wipe)."""
    factory = get_session_factory()
    async with factory() as session:
        supers = int(
            await session.scalar(
                select(func.count())
                .select_from(UserRole)
                .join(Role, Role.id == UserRole.role_id)
                .where(Role.code == SystemRole.SUPER_ADMIN)
            )
            or 0
        )
        if supers == 0:
            return 0
        counts = await _counts(session)

    print(f"\nSuper admins (kept): {supers}")
    print("Would delete:")
    for name, number in counts.items():
        print(f"  {number:>8}  {name}")
    print(
        "\nKept: super admins, settings, features, texts, faculties, books, seasons, premium plans, "
        "stickers/emoji, the licence key."
    )
    return supers


async def wipe() -> None:
    factory = get_session_factory()
    async with factory() as session:
        # Empty the operational tables first (one statement; CASCADE clears their children), then remove the
        # members — now nothing references them, so the protected ledgers no longer block the delete. The
        # members' own config rows (roles, permissions, personal missions) go with them by cascade.
        await session.execute(
            text(f"TRUNCATE TABLE {', '.join(WIPE_TABLES)} RESTART IDENTITY CASCADE")
        )
        await session.execute(
            text(
                "DELETE FROM users WHERE id NOT IN "
                "(SELECT ur.user_id FROM user_roles ur JOIN roles r ON r.id = ur.role_id "
                " WHERE r.code = :code)"
            ),
            {"code": SystemRole.SUPER_ADMIN.value},
        )
        await session.commit()
    await get_engine().dispose()
    print("\n✅ Done. The club starts clean; configuration and super admins are kept.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear the testing data before the public launch.")
    parser.add_argument("--apply", action="store_true", help="really delete (otherwise a dry run)")
    do_apply = parser.parse_args().apply

    super_count = asyncio.run(report())
    if super_count == 0:
        raise SystemExit("ABORTED: no super admin found — refusing to wipe (you would be locked out).")
    if not do_apply:
        print("\nDRY RUN — nothing was changed. Re-run with --apply to delete.")
    else:
        print("\n⚠️  This permanently deletes the data above and cannot be undone.")
        if input("Type exactly  TOZALASH  to proceed: ").strip() != "TOZALASH":
            raise SystemExit("Cancelled — nothing was changed.")
        asyncio.run(wipe())
