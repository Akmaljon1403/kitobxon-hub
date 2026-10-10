"""Twelve certificate designs (A4 landscape) and the club's own uploaded backgrounds.

Every design is a full-page SVG background (frame and ornaments) plus a palette for the text drawn
on top. New certificates take the designs in turn («ketma-ket»): all places of one test share a
design, the next test gets the next one. A Premium member may switch their copy to another design;
the certificate itself (its number and check code) stays one and the same.
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from urllib.parse import quote

CUSTOM = "custom"  # an image the admins uploaded for an event or a test


@dataclass(frozen=True)
class Palette:
    paper: str
    ink: str  # main text
    primary: str  # title, name
    accent: str  # rules, medal ring
    muted: str


@dataclass(frozen=True)
class Design:
    code: str
    title: str
    palette: Palette
    svg: str  # the background, 297 x 210 (mm)

    def background_uri(self) -> str:
        return "data:image/svg+xml;charset=utf-8," + quote(self.svg)


def _svg(paper: str, body: str, defs: str = "") -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="297mm" height="210mm" viewBox="0 0 297 210">'
        f'<defs>{defs}</defs><rect width="297" height="210" fill="{paper}"/>{body}</svg>'
    )


def _frame(color: str, inset: float, width: float, extra: str = "") -> str:
    return (
        f'<rect x="{inset}" y="{inset}" width="{297 - 2 * inset}" height="{210 - 2 * inset}" '
        f'fill="none" stroke="{color}" stroke-width="{width}" {extra}/>'
    )


def _corners(shape: str, color: str, inset: float, size: float) -> str:
    points = [(inset, inset), (297 - inset, inset), (inset, 210 - inset), (297 - inset, 210 - inset)]
    parts = []
    for x, y in points:
        if shape == "diamond":
            parts.append(
                f'<rect x="{x - size / 2}" y="{y - size / 2}" width="{size}" height="{size}" fill="{color}" '
                f'transform="rotate(45 {x} {y})"/>'
            )
        elif shape == "circle":
            parts.append(f'<circle cx="{x}" cy="{y}" r="{size / 2}" fill="{color}"/>')
        elif shape == "square":
            parts.append(
                f'<rect x="{x - size / 2}" y="{y - size / 2}" width="{size}" height="{size}" fill="none" '
                f'stroke="{color}" stroke-width="0.8"/>'
                f'<rect x="{x - size / 4}" y="{y - size / 4}" width="{size / 2}" height="{size / 2}" fill="{color}"/>'
            )
    return "".join(parts)


def _classic() -> Design:
    green, gold = "#1f5c40", "#c9a24e"
    body = _frame(green, 9, 3.2) + _frame(gold, 13.5, 0.6) + _corners("diamond", gold, 13.5, 7)
    return Design(
        "classic", "Klassik", Palette("#fffdf7", "#1c2b24", "#1f5c40", gold, "#5b6b63"), _svg("#fffdf7", body)
    )


def _royal() -> Design:
    navy, gold = "#14254d", "#c9a24e"
    body = (
        f'<rect width="297" height="24" fill="{navy}"/><rect y="186" width="297" height="24" fill="{navy}"/>'
        f'<rect y="24" width="297" height="1.2" fill="{gold}"/><rect y="184.8" width="297" height="1.2" fill="{gold}"/>'
        + "".join(f'<circle cx="{12 + i * 13.6}" cy="12" r="1.3" fill="{gold}"/>' for i in range(21))
        + "".join(f'<circle cx="{12 + i * 13.6}" cy="198" r="1.3" fill="{gold}"/>' for i in range(21))
        + _frame(gold, 28, 0.4, 'stroke-dasharray="2 1.5"')
    )
    return Design("royal", "Qirollik", Palette("#fdfbf5", "#1c2333", navy, gold, "#56607a"), _svg("#fdfbf5", body))


def _ruby() -> Design:
    wine, gold = "#7d1d35", "#c9a24e"
    corners = "".join(
        f'<path d="M{x} {y} m{sx * 0} {sy * 34} a34 34 0 0 {flag} {sx * 34} {-sy * 34}" fill="none" stroke="{gold}" '
        f'stroke-width="0.9"/>'
        f'<path d="M{x} {y} m0 {sy * 26} a26 26 0 0 {flag} {sx * 26} {-sy * 26}" fill="none" stroke="{gold}" '
        f'stroke-width="0.5"/>'
        for x, y, sx, sy, flag in ((10, 10, 1, 1, 1), (287, 10, -1, 1, 0), (10, 200, 1, -1, 0), (287, 200, -1, -1, 1))
    )
    body = _frame(wine, 7, 6) + _frame(gold, 12, 0.7) + corners
    return Design("ruby", "Yoqut", Palette("#fff8f6", "#2b1a1f", wine, gold, "#6d5a5f"), _svg("#fff8f6", body))


def _emerald() -> Design:
    shades = ("#0f766e", "#14b8a6", "#99f6e4")
    body = (
        f'<polygon points="0,0 66,0 0,48" fill="{shades[0]}"/><polygon points="0,0 42,0 0,70" fill="{shades[1]}" '
        f'opacity="0.55"/><polygon points="0,0 24,0 0,24" fill="{shades[2]}"/>'
        f'<polygon points="297,210 231,210 297,162" fill="{shades[0]}"/><polygon points="297,210 255,210 297,140" '
        f'fill="{shades[1]}" opacity="0.55"/><polygon points="297,210 273,210 297,186" fill="{shades[2]}"/>'
        + _frame("#0f766e", 14, 0.5)
    )
    return Design(
        "emerald", "Zumrad", Palette("#f6fcfa", "#12302b", "#0f766e", "#14b8a6", "#4b6b65"), _svg("#f6fcfa", body)
    )


def _sunrise() -> Design:
    defs = (
        '<linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#f97316"/>'
        '<stop offset="1" stop-color="#facc15"/></linearGradient>'
    )
    rays = "".join(
        f'<line x1="258" y1="36" x2="{258 + 34 * math.cos(math.radians(a)):.1f}" '
        f'y2="{36 + 34 * math.sin(math.radians(a)):.1f}" stroke="#fdba74" stroke-width="1.2"/>'
        for a in range(0, 360, 20)
    )
    body = (
        rays
        + '<circle cx="258" cy="36" r="16" fill="url(#g)"/>'
        + '<path d="M0 192 C60 182 110 202 170 192 C220 184 260 188 297 180 L297 210 L0 210 Z" fill="url(#g)"/>'
        + '<path d="M0 200 C70 192 120 208 180 200 C230 194 270 198 297 192 L297 210 L0 210 Z" fill="#ea580c" '
        'opacity="0.55"/>' + _frame("#ea580c", 10, 0.6)
    )
    return Design(
        "sunrise", "Tong", Palette("#fffaf2", "#33210f", "#c2410c", "#f59e0b", "#7a5f45"), _svg("#fffaf2", body, defs)
    )


def _ocean() -> Design:
    blues = ("#0c4a6e", "#0369a1", "#38bdf8")
    body = (
        f'<path d="M0 0 L297 0 L297 18 C240 30 190 10 140 22 C90 34 40 14 0 26 Z" fill="{blues[0]}"/>'
        f'<path d="M0 26 C40 14 90 34 140 22 C190 10 240 30 297 18 L297 24 C240 36 190 16 140 28 C90 40 40 20 0 32 Z" '
        f'fill="{blues[2]}"/>'
        f'<path d="M0 210 L297 210 L297 186 C250 176 200 198 150 188 C100 178 50 198 0 186 Z" fill="{blues[1]}"/>'
        f'<path d="M0 194 C50 206 100 186 150 196 C200 206 250 184 297 194 L297 210 L0 210 Z" fill="{blues[0]}"/>'
    )
    return Design(
        "ocean", "Okean", Palette("#f4faff", "#0f2233", "#0c4a6e", "#0ea5e9", "#4a6377"), _svg("#f4faff", body)
    )


def _lavender() -> Design:
    purple = "#7c3aed"
    flowers = "".join(
        "".join(
            f'<circle cx="{x + 5 * math.cos(math.radians(a)):.1f}" cy="{y + 5 * math.sin(math.radians(a)):.1f}" '
            f'r="3.4" fill="#c4b5fd" opacity="0.85"/>'
            for a in range(0, 360, 60)
        )
        + f'<circle cx="{x}" cy="{y}" r="2.6" fill="#facc15"/>'
        for x, y in ((24, 24), (273, 24), (24, 186), (273, 186))
    )
    body = (
        _frame(purple, 10, 1.1, 'stroke-dasharray="0.1 3" stroke-linecap="round"')
        + _frame("#a78bfa", 14, 0.5)
        + flowers
    )
    return Design(
        "lavender", "Lavanda", Palette("#fbf8ff", "#241a33", "#6d28d9", "#a78bfa", "#655a78"), _svg("#fbf8ff", body)
    )


def _minimal() -> Design:
    body = (
        '<rect width="12" height="210" fill="#111827"/><rect x="12" width="2" height="210" fill="#f59e0b"/>'
        + '<rect x="24" y="12" width="261" height="186" fill="none" stroke="#d1d5db" stroke-width="0.4"/>'
    )
    return Design(
        "minimal", "Minimal", Palette("#ffffff", "#111827", "#111827", "#f59e0b", "#6b7280"), _svg("#ffffff", body)
    )


def _vintage() -> Design:
    brown = "#6b4423"
    defs = (
        '<radialGradient id="p" cx="0.5" cy="0.5" r="0.75"><stop offset="0.55" stop-color="#f7eedb"/>'
        '<stop offset="1" stop-color="#e3cfa4"/></radialGradient>'
    )
    body = (
        '<rect width="297" height="210" fill="url(#p)"/>'
        + _frame(brown, 9, 1.6)
        + _frame(brown, 12.5, 0.5)
        + _corners("square", brown, 12.5, 10)
    )
    return Design(
        "vintage",
        "Vintage",
        Palette("#f4ead3", "#2f2114", "#5a3518", "#8b5e34", "#6e5a45"),
        _svg("#f4ead3", body, defs),
    )


def _gold() -> Design:
    gold = "#d4af37"
    defs = (
        '<linearGradient id="d" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22252b"/>'
        '<stop offset="1" stop-color="#121418"/></linearGradient>'
    )
    body = (
        '<rect width="297" height="210" fill="url(#d)"/>'
        + _frame(gold, 9, 1.8)
        + _frame(gold, 13, 0.5)
        + _corners("diamond", gold, 13, 6)
    )
    return Design("gold", "Oltin", Palette("#181a1f", "#f3ead2", gold, gold, "#bfb59a"), _svg("#181a1f", body, defs))


def _book() -> Design:
    green, brown = "#166534", "#92400e"
    lines = "".join(
        f'<path d="M{110 + i * 0} {14 + i * 2.2} Q129 {9 + i * 2.2} 148.5 {16 + i * 2.2}" fill="none" stroke="#bbf7d0" '
        f'stroke-width="0.35"/>'
        f'<path d="M{148.5} {16 + i * 2.2} Q168 {9 + i * 2.2} 187 {14 + i * 2.2}" fill="none" stroke="#bbf7d0" '
        f'stroke-width="0.35"/>'
        for i in range(1, 6)
    )
    body = (
        f'<path d="M104 12 Q126 4 148.5 14 Q171 4 193 12 L193 32 Q171 24 148.5 34 Q126 24 104 32 Z" fill="{green}"/>'
        + lines
        + '<line x1="148.5" y1="14" x2="148.5" y2="34" stroke="#bbf7d0" stroke-width="0.5"/>'
        + f'<rect x="10" y="198" width="277" height="1.2" fill="{brown}"/>'
        + f'<rect x="10" y="201" width="277" height="0.5" fill="{brown}"/>'
        + _frame(green, 8, 0.6)
    )
    return Design("book", "Kitob", Palette("#fffef8", "#1d2b1f", green, brown, "#5d6b5c"), _svg("#fffef8", body))


def _stars() -> Design:
    defs = (
        '<linearGradient id="n" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b1633"/>'
        '<stop offset="1" stop-color="#1e3a6e"/></linearGradient>'
    )
    stars = []
    seed = 17
    for _ in range(140):
        seed = (seed * 1103515245 + 12345) % 2**31
        x = 6 + seed % 285
        seed = (seed * 1103515245 + 12345) % 2**31
        y = 6 + seed % 198
        if 26 < x < 271 and 18 < y < 202:
            continue  # keep the text area clear
        seed = (seed * 1103515245 + 12345) % 2**31
        stars.append(f'<circle cx="{x}" cy="{y}" r="{0.3 + (seed % 10) / 10:.1f}" fill="#fef3c7" opacity="0.9"/>')
    body = '<rect width="297" height="210" fill="url(#n)"/>' + "".join(stars) + _frame("#fcd34d", 11, 0.6)
    return Design(
        "stars",
        "Yulduzli tun",
        Palette("#0f1e3d", "#f8fafc", "#fcd34d", "#fcd34d", "#c7d2fe"),
        _svg("#0f1e3d", body, defs),
    )


DESIGNS: tuple[Design, ...] = (
    _classic(),
    _royal(),
    _ruby(),
    _emerald(),
    _sunrise(),
    _ocean(),
    _lavender(),
    _minimal(),
    _vintage(),
    _gold(),
    _book(),
    _stars(),
)
BY_CODE = {design.code: design for design in DESIGNS}
CUSTOM_PALETTE = Palette("#ffffff", "#1c2b24", "#14402c", "#c9a24e", "#4b5d54")


def get(code: str | None) -> Design:
    return BY_CODE.get(code or "", DESIGNS[0])


def next_after(code: str | None) -> Design:
    """The design after ``code`` in the rotation (the first one when there is none yet)."""
    if code not in BY_CODE:
        return DESIGNS[0]
    index = [design.code for design in DESIGNS].index(code)
    return DESIGNS[(index + 1) % len(DESIGNS)]


def image_uri(data: bytes, content_type: str = "image/jpeg") -> str:
    return f"data:{content_type};base64,{base64.b64encode(data).decode()}"
