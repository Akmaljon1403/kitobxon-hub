"""One order for every list of faculties, courses and groups: the way people count.

Group names are compared by their numbers, not letter by letter: «301» < «1001», «5424» < «5524»,
«2-A» < «2-B» < «10-A». Lists go faculty → course → group → surname everywhere (documents,
analytics), so the same table looks the same in every report.
"""

from __future__ import annotations

import re
from typing import Any

_PARTS = re.compile(r"(\d+)")
LAST = "￿"  # empty values go to the end


def natural_key(value: str | None) -> tuple[Any, ...]:
    """«5424» → ((0, 5424, ''),); text and numbers alternate, numbers compared as numbers."""
    if not value:
        return ((1, 0, LAST),)
    parts = []
    for piece in _PARTS.split(value.strip().upper()):
        if not piece:
            continue
        parts.append((0, int(piece), "") if piece.isdigit() else (0, -1, piece))
    return tuple(parts)


def member_key(
    faculty_order: int | None,
    faculty_name: str | None,
    course: int | None,
    group: str | None,
    last_name: str | None = None,
    first_name: str | None = None,
) -> tuple[Any, ...]:
    """Faculty (its place in the list, then the name; no faculty last) → course → group → name."""
    return (
        faculty_name is None,
        faculty_order if faculty_order is not None else 1_000_000,
        (faculty_name or "").casefold(),
        course if course is not None else 1_000,
        natural_key(group),
        (last_name or "").casefold(),
        (first_name or "").casefold(),
    )
