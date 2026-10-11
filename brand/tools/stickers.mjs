// Telegram stickers (512 × 512, transparent, white die-cut outline) in the brand's colours.
import { C, FONTS, id, lucide, mark, star4, svgDoc } from './lib.mjs'

const N = 1024

/** The white die-cut outline and a soft shadow around everything inside. */
const outline = (fid) => `<filter id="${fid}" x="-10%" y="-10%" width="120%" height="120%">
  <feMorphology in="SourceAlpha" operator="dilate" radius="20" result="fat"/>
  <feGaussianBlur in="fat" stdDeviation="9" result="soft"/>
  <feOffset in="soft" dx="0" dy="10" result="drop"/>
  <feFlood flood-color="#0B1F3B" flood-opacity="0.28"/><feComposite in2="drop" operator="in" result="shadow"/>
  <feFlood flood-color="#FFFFFF"/><feComposite in2="fat" operator="in" result="white"/>
  <feMerge><feMergeNode in="shadow"/><feMergeNode in="white"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>`

/** A caption in one or two lines, navy on white (it gets the die-cut outline too). */
function caption(lines, y, size = 96) {
  return lines
    .map(
      (line, i) =>
        `<text x="512" y="${y + i * size * 1.08}" text-anchor="middle" font-family="Nunito" font-weight="900" font-size="${size}"
          fill="${C.navy}" stroke="#FFFFFF" stroke-width="${size * 0.22}" stroke-linejoin="round" paint-order="stroke">${line}</text>`,
    )
    .join('')
}

function sticker(art, lines, { captionY = 860, size = 96 } = {}) {
  const f = id('st')
  return svgDoc(N, N, `<g filter="url(#${f})">${art}${caption(lines, captionY, size)}</g>`, { fonts: FONTS.sticker, defs: outline(f) })
}

const face = (cx, cy, s = 1, mood = 'happy') => `
  <ellipse cx="${cx - 62 * s}" cy="${cy}" rx="${34 * s}" ry="${40 * s}" fill="#FFFFFF"/>
  <ellipse cx="${cx + 62 * s}" cy="${cy}" rx="${34 * s}" ry="${40 * s}" fill="#FFFFFF"/>
  <circle cx="${cx - 56 * s}" cy="${cy + 8 * s}" r="${18 * s}" fill="${C.navy950}"/>
  <circle cx="${cx + 68 * s}" cy="${cy + 8 * s}" r="${18 * s}" fill="${C.navy950}"/>
  <circle cx="${cx - 50 * s}" cy="${cy}" r="${6 * s}" fill="#FFFFFF"/>
  <circle cx="${cx + 74 * s}" cy="${cy}" r="${6 * s}" fill="#FFFFFF"/>
  <ellipse cx="${cx - 112 * s}" cy="${cy + 62 * s}" rx="${24 * s}" ry="${14 * s}" fill="#F08A8A" fill-opacity="0.55"/>
  <ellipse cx="${cx + 112 * s}" cy="${cy + 62 * s}" rx="${24 * s}" ry="${14 * s}" fill="#F08A8A" fill-opacity="0.55"/>
  ${mood === 'happy'
    ? `<path d="M${cx - 40 * s} ${cy + 66 * s} Q${cx} ${cy + 116 * s} ${cx + 40 * s} ${cy + 66 * s}" fill="#7A2E2E" stroke="${C.navy950}" stroke-width="${8 * s}" stroke-linejoin="round"/>`
    : `<path d="M${cx - 34 * s} ${cy + 74 * s} Q${cx} ${cy + 100 * s} ${cx + 34 * s} ${cy + 74 * s}" fill="none" stroke="${C.navy950}" stroke-width="${10 * s}" stroke-linecap="round"/>`}`

/** A small open book (cream pages, gold boards) centred on (cx, cy), `w` wide. */
const openBook = (cx, cy, w, pageColor = C.cream) => {
  const h = w * 0.42
  return `<path d="M${cx} ${cy + h * 0.62} C${cx - w * 0.2} ${cy + h * 0.4} ${cx - w * 0.38} ${cy + h * 0.42} ${cx - w * 0.52} ${cy + h * 0.5} L${cx - w * 0.52} ${cy - h * 0.38} L${cx} ${cy - h * 0.2} L${cx + w * 0.52} ${cy - h * 0.38} L${cx + w * 0.52} ${cy + h * 0.5} C${cx + w * 0.38} ${cy + h * 0.42} ${cx + w * 0.2} ${cy + h * 0.4} ${cx} ${cy + h * 0.62} Z" fill="${C.gold}"/>
    <path d="M${cx} ${cy + h * 0.5} C${cx - w * 0.18} ${cy + h * 0.28} ${cx - w * 0.34} ${cy + h * 0.3} ${cx - w * 0.47} ${cy + h * 0.36} L${cx - w * 0.47} ${cy - h * 0.5} C${cx - w * 0.3} ${cy - h * 0.6} ${cx - w * 0.12} ${cy - h * 0.55} ${cx} ${cy - h * 0.36} Z" fill="${pageColor}"/>
    <path d="M${cx} ${cy + h * 0.5} C${cx + w * 0.18} ${cy + h * 0.28} ${cx + w * 0.34} ${cy + h * 0.3} ${cx + w * 0.47} ${cy + h * 0.36} L${cx + w * 0.47} ${cy - h * 0.5} C${cx + w * 0.3} ${cy - h * 0.6} ${cx + w * 0.12} ${cy - h * 0.55} ${cx} ${cy - h * 0.36} Z" fill="#FFFFFF"/>
    <path d="M${cx} ${cy - h * 0.36} L${cx} ${cy + h * 0.5}" stroke="${C.gold600}" stroke-width="${w * 0.012}"/>
    <g stroke="${C.navy}" stroke-opacity="0.25" stroke-width="${w * 0.014}" stroke-linecap="round">
      ${[0, 1, 2].map((i) => `<path d="M${cx - w * 0.4} ${cy - h * 0.28 + i * h * 0.22} H${cx - w * 0.08} M${cx + w * 0.08} ${cy - h * 0.28 + i * h * 0.22} H${cx + w * 0.4}"/>`).join('')}
    </g>`
}

/** A closed book lying flat; (x, y) is its bottom-left corner. */
const flatBook = (x, y, w, h, color, band = C.gold) => `
  <rect x="${x}" y="${y - h}" width="${w}" height="${h}" rx="${h * 0.22}" fill="${color}"/>
  <rect x="${x + w * 0.05}" y="${y - h * 0.78}" width="${w * 0.88}" height="${h * 0.56}" rx="${h * 0.12}" fill="${C.paper}"/>
  <path d="M${x + w * 0.08} ${y - h * 0.58} H${x + w * 0.9} M${x + w * 0.08} ${y - h * 0.42} H${x + w * 0.9}" stroke="#D8CDB6" stroke-width="${h * 0.05}"/>
  <rect x="${x + w * 0.82}" y="${y - h}" width="${w * 0.05}" height="${h}" fill="${band}"/>`

const sparkles = (points) => points.map(([x, y, r]) => star4(x, y, r, C.gold)).join('')

const ART = {
  // A cheerful book reading a smaller book.
  oqi: () => `
    <rect x="292" y="120" width="440" height="560" rx="46" fill="${C.navy}"/>
    <rect x="292" y="120" width="70" height="560" rx="30" fill="${C.navy700}"/>
    <path d="M292 166 V120 H338 Z M732 166 V120 H686 Z" fill="${C.gold}"/>
    <rect x="292" y="606" width="440" height="20" fill="${C.gold}" fill-opacity="0.8"/>
    ${face(530, 300, 1)}
    <path d="M360 520 Q300 560 330 610" fill="none" stroke="${C.navy}" stroke-width="34" stroke-linecap="round"/>
    <path d="M700 520 Q760 560 730 610" fill="none" stroke="${C.navy}" stroke-width="34" stroke-linecap="round"/>
    ${openBook(530, 610, 400)}
    ${sparkles([[220, 200, 34], [810, 160, 26], [840, 420, 18]])}`,
  // A stack of books with a sprout: every book is a new chance.
  imkoniyat: () => `
    ${flatBook(250, 690, 520, 110, C.navy)}
    ${flatBook(290, 580, 450, 100, C.green, C.gold300)}
    ${flatBook(270, 480, 480, 100, '#7A2E2E')}
    <path d="M520 380 C520 300 510 250 520 190" fill="none" stroke="#2E7D4F" stroke-width="22" stroke-linecap="round"/>
    <path d="M518 270 C450 270 400 230 390 170 C460 160 510 200 518 270 Z" fill="#3FA06A"/>
    <path d="M522 230 C590 236 650 200 664 140 C590 128 534 168 522 230 Z" fill="#5CBF84"/>
    ${sparkles([[230, 250, 30], [800, 300, 26], [760, 160, 18]])}`,
  // The club's mug with a heart of steam.
  dost: () => `
    <path d="M700 380 C820 380 820 560 700 560" fill="none" stroke="${C.navy}" stroke-width="46"/>
    <path d="M260 300 H730 V600 Q730 690 640 690 H350 Q260 690 260 600 Z" fill="${C.navy}"/>
    <ellipse cx="495" cy="300" rx="235" ry="40" fill="#3A2416"/>
    <rect x="260" y="330" width="470" height="18" fill="${C.gold}"/>
    ${mark(495, 500, 230, 'mono', C.gold)}
    <path d="M495 250 C430 190 400 140 440 110 C470 88 495 110 495 130 C495 110 520 88 550 110 C590 140 560 190 495 250 Z" fill="#F08A8A"/>
    ${sparkles([[220, 200, 28], [800, 190, 30]])}`,
  // An open book with a ribbon bookmark: one more page today.
  sahifa: () => `
    ${openBook(512, 430, 700)}
    <path d="M560 270 V560 L605 520 L650 560 V270 Z" fill="${C.navy}"/>
    ${star4(605, 420, 30, C.gold)}
    <path d="M300 640 L760 300" stroke="${C.gold600}" stroke-width="0"/>
    ${sparkles([[200, 230, 30], [820, 200, 26]])}`,
  // Reading is the biggest investment: a book, gold coins and a rising arrow.
  sarmoya: () => `
    ${openBook(430, 520, 560)}
    ${[0, 1, 2, 3].map((i) => `<ellipse cx="760" cy="${640 - i * 46}" rx="110" ry="36" fill="${C.gold600}"/><ellipse cx="760" cy="${628 - i * 46}" rx="110" ry="36" fill="${C.gold}"/><ellipse cx="760" cy="${628 - i * 46}" rx="70" ry="20" fill="none" stroke="${C.gold300}" stroke-width="8"/>`).join('')}
    <path d="M240 330 L420 230 L520 300 L740 150" fill="none" stroke="${C.green}" stroke-width="40" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M690 120 L790 130 L760 225 Z" fill="${C.green}"/>
    ${sparkles([[180, 200, 26], [850, 330, 22]])}`,
  // Dreams live in books: the moon and stars rising out of an open book.
  orzu: () => `
    <circle cx="512" cy="380" r="270" fill="${C.navy}"/>
    <path d="M600 210 A150 150 0 1 0 640 470 A120 120 0 1 1 600 210 Z" fill="${C.gold300}"/>
    ${sparkles([[380, 250, 26], [420, 400, 16], [690, 330, 20], [330, 340, 12]])}
    ${openBook(512, 600, 640)}`,
  // Well done: a trophy with a star.
  barakalla: () => `
    <path d="M330 200 H694 V330 Q694 520 512 560 Q330 520 330 330 Z" fill="${C.gold}"/>
    <path d="M330 240 H240 Q230 400 380 440" fill="none" stroke="${C.gold}" stroke-width="40" stroke-linecap="round"/>
    <path d="M694 240 H784 Q794 400 644 440" fill="none" stroke="${C.gold}" stroke-width="40" stroke-linecap="round"/>
    <rect x="470" y="550" width="84" height="90" fill="${C.gold600}"/>
    <rect x="370" y="630" width="284" height="70" rx="14" fill="${C.navy}"/>
    ${star4(512, 360, 90, '#FFFFFF')}
    ${sparkles([[200, 160, 30], [840, 160, 30], [860, 520, 20]])}`,
  // Welcome: the mark on its round badge with a waving sparkle.
  xush: () => `
    <circle cx="512" cy="400" r="300" fill="${C.gold}"/>
    <circle cx="512" cy="400" r="276" fill="${C.navy}"/>
    ${mark(512, 410, 380, 'dark')}
    ${sparkles([[180, 180, 34], [850, 220, 28], [860, 560, 20]])}`,
}

const STICKERS = [
  ['01-oqi', 'oqi', ['O‘qi!'], { captionY: 830, size: 120 }],
  ['02-har-bir-kitob-yangi-imkoniyat', 'imkoniyat', ['Har bir kitob —', 'yangi imkoniyat'], { captionY: 800, size: 84 }],
  ['03-kitob-eng-yaxshi-dost', 'dost', ['Kitob —', 'eng yaxshi do‘st'], { captionY: 800, size: 88 }],
  ['04-bugun-ham-bir-sahifa', 'sahifa', ['Bugun ham', 'bir sahifa...'], { captionY: 780, size: 92 }],
  ['05-oqish-eng-katta-sarmoya', 'sarmoya', ['O‘qish —', 'eng katta sarmoya'], { captionY: 800, size: 84 }],
  ['06-orzular-kitoblarda', 'orzu', ['Orzular', 'kitoblarda...'], { captionY: 800, size: 92 }],
  ['07-barakalla', 'barakalla', ['Barakalla!'], { captionY: 850, size: 120 }],
  ['08-xush-kelibsiz', 'xush', ['Xush kelibsiz!'], { captionY: 850, size: 108 }],
]

export function stickers(add) {
  for (const [file, art, lines, options] of STICKERS) {
    // Fitted to the drawing (Telegram wants 512 px on the longer side); the pad keeps the outline.
    add(`10_Stikerlar/${file}`, N, N, sticker(ART[art](), lines, options), { fit: 64, sizes: [512, 2048], preview: '#E9EEF5' })
  }
  void lucide
}
