"""CSV files for Excel, protected against formula injection.

Excel runs a cell that starts with ``=``, ``+``, ``-`` or ``@`` as a formula. Member names,
group names and titles end up in exported files, so such cells get a leading apostrophe,
which Excel shows as plain text.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from typing import Any, TextIO

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return "'" + value
    return value


class _SafeWriter:
    def __init__(self, buffer: TextIO) -> None:
        self._writer = csv.writer(buffer, delimiter=";")

    def writerow(self, row: Iterable[Any]) -> None:
        self._writer.writerow([safe_cell(value) for value in row])


def excel_writer(buffer: TextIO) -> _SafeWriter:
    """A semicolon-separated CSV writer (what Excel expects in the Uzbek locale)."""
    return _SafeWriter(buffer)
