// The Kitobxon mark: an open book whose spine is a fountain-pen nib (reading and writing), with a
// four-pointed star above it (a guiding light). Drawn on a 1024 × 1024 grid centred on x = 512.

export const C = {
  navy950: '#050E1D',
  navy900: '#071628',
  navy: '#0B1F3B',
  navy700: '#132B4F',
  navy600: '#1C3A66',
  gold200: '#F6E7B0',
  gold300: '#EFD887',
  gold: '#D4AF37',
  gold600: '#B8922A',
  gold700: '#8C6D1C',
  cream: '#F8F6F2',
  paper: '#EFE9DC',
  grey: '#9CA3AF',
  green: '#0E5F46',
  ink: '#0B1F3B',
  seal: '#1E3A8A',
}

// ------------------------------------------------------------------------------------ geometry
export const STAR = 'M512 112 Q527 189 604 204 Q527 219 512 296 Q497 219 420 204 Q497 189 512 112 Z'
/** The right half is the left half mirrored around x = 512. */
const mirror = (path) => path.replace(/(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)/g, (_, x, y) => `${1024 - Number(x)} ${y}`)
// Pages rise like wings from the spine; their outer corners fan out a little at the top.
const PAGE_L = 'M474 344 C430 292 326 228 168 230 C178 372 186 512 194 654 C304 642 414 670 474 728 Z'
const PAGE_R = mirror(PAGE_L)
// The cover boards hug the outer and lower edges of the pages; a cream band is the page block.
const COVER_L =
  'M512 806 C432 750 292 724 138 736 C130 584 124 424 116 250 L168 230 C178 372 186 512 194 654 ' +
  'C304 642 414 670 474 728 L512 764 Z'
const COVER_R = mirror(COVER_L)
const BLOCK_L = 'M512 776 C430 722 298 698 150 708 L148 690 C296 680 428 704 512 758 Z'
const BLOCK_R = mirror(BLOCK_L)
// The nib: a rounded cap, a shoulder, then the point down to the cover's crease.
const NIB =
  'M512 326 C540 326 558 346 558 374 L558 494 C558 566 548 634 512 760 C476 634 466 566 466 494 ' +
  'L466 374 C466 346 484 326 512 326 Z'
const NIB_SLIT = 'M512 498 L512 740'
const NIB_HOLE = { cx: 512, cy: 480, r: 16 }
// Page lines (text) for the larger sizes.
const lines = (side) => {
  const s = side === 'l' ? -1 : 1
  const x = (v) => (512 + s * v).toFixed(1)
  return [0, 1, 2, 3, 4]
    .map((i) => {
      const y = 380 + i * 58
      const outer = i === 4 ? 210 : 290
      return `M${x(78)} ${y + 22} C${x(150)} ${y - 6} ${x(230)} ${y - 18} ${x(outer)} ${y - 14}`
    })
    .join(' ')
}

export function markDefs(id = 'm') {
  return `
  <linearGradient id="${id}-gold" x1="0" y1="0" x2="0.35" y2="1">
    <stop offset="0" stop-color="${C.gold300}"/>
    <stop offset="0.45" stop-color="${C.gold}"/>
    <stop offset="1" stop-color="${C.gold600}"/>
  </linearGradient>
  <linearGradient id="${id}-star" x1="0.5" y1="0" x2="0.5" y2="1">
    <stop offset="0" stop-color="${C.gold200}"/>
    <stop offset="0.55" stop-color="${C.gold}"/>
    <stop offset="1" stop-color="${C.gold600}"/>
  </linearGradient>
  <linearGradient id="${id}-page-l" x1="1" y1="0" x2="0" y2="0.2">
    <stop offset="0" stop-color="#E4DCCB"/>
    <stop offset="0.25" stop-color="${C.cream}"/>
    <stop offset="1" stop-color="#FFFFFF"/>
  </linearGradient>
  <linearGradient id="${id}-page-r" x1="0" y1="0" x2="1" y2="0.2">
    <stop offset="0" stop-color="#E4DCCB"/>
    <stop offset="0.25" stop-color="${C.cream}"/>
    <stop offset="1" stop-color="#FFFFFF"/>
  </linearGradient>
  <linearGradient id="${id}-nib" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="${C.navy600}"/>
    <stop offset="0.5" stop-color="${C.navy}"/>
    <stop offset="1" stop-color="${C.navy950}"/>
  </linearGradient>`
}

/** The full-colour mark for dark backgrounds: cream pages, gold boards and star, navy nib. */
export function markDark(id = 'm', { lines: withLines = false } = {}) {
  return `
  <g stroke-linejoin="round" stroke-linecap="round">
    <path d="${COVER_L} ${COVER_R}" fill="url(#${id}-gold)"/>
    <path d="${BLOCK_L} ${BLOCK_R}" fill="${C.gold300}" fill-opacity="0.85"/>
    <path d="${PAGE_L}" fill="url(#${id}-page-l)"/>
    <path d="${PAGE_R}" fill="url(#${id}-page-r)"/>
    ${withLines ? `<path d="${lines('l')} ${lines('r')}" fill="none" stroke="${C.navy}" stroke-opacity="0.16" stroke-width="10"/>` : ''}
    <path d="${NIB}" fill="url(#${id}-nib)" stroke="${C.navy950}" stroke-width="4"/>
    <path d="${NIB_SLIT}" stroke="${C.gold}" stroke-width="7"/>
    <circle cx="${NIB_HOLE.cx}" cy="${NIB_HOLE.cy}" r="${NIB_HOLE.r}" fill="${C.gold}"/>
    <path d="${STAR}" fill="url(#${id}-star)"/>
  </g>`
}

/** The full-colour mark for light backgrounds: navy pages, gold boards and star, the nib cut out. */
export function markLight(id = 'm') {
  return `
  <mask id="${id}-nibcut" maskUnits="userSpaceOnUse" x="0" y="0" width="1024" height="1024">
    <rect width="1024" height="1024" fill="#fff"/>
    <path d="${NIB}" fill="#000" stroke="#000" stroke-width="22"/>
  </mask>
  <g stroke-linejoin="round" stroke-linecap="round">
    <g mask="url(#${id}-nibcut)">
      <path d="${COVER_L} ${COVER_R}" fill="url(#${id}-gold)"/>
      <path d="${BLOCK_L} ${BLOCK_R}" fill="${C.gold600}"/>
      <path d="${PAGE_L} ${PAGE_R}" fill="${C.navy}"/>
    </g>
    <path d="${NIB}" fill="url(#${id}-gold)"/>
    <path d="${NIB_SLIT}" stroke="${C.navy}" stroke-width="7"/>
    <circle cx="${NIB_HOLE.cx}" cy="${NIB_HOLE.cy}" r="${NIB_HOLE.r}" fill="${C.navy}"/>
    <path d="${STAR}" fill="url(#${id}-star)"/>
  </g>`
}

/** One colour (stamps, watermarks, embossing): the nib, its slit and a hairline around the pages are cut out. */
export function markMono(color, id = 'mono', { opacity = 1 } = {}) {
  return `
  <mask id="${id}-cover" maskUnits="userSpaceOnUse" x="0" y="0" width="1024" height="1024">
    <rect width="1024" height="1024" fill="#fff"/>
    <path d="${PAGE_L} ${PAGE_R}" fill="#000" stroke="#000" stroke-width="26" stroke-linejoin="round"/>
    <path d="${BLOCK_L} ${BLOCK_R}" fill="#000"/>
  </mask>
  <mask id="${id}-pages" maskUnits="userSpaceOnUse" x="0" y="0" width="1024" height="1024">
    <rect width="1024" height="1024" fill="#fff"/>
    <path d="${NIB}" fill="#000" stroke="#000" stroke-width="24"/>
  </mask>
  <mask id="${id}-nib" maskUnits="userSpaceOnUse" x="0" y="0" width="1024" height="1024">
    <rect width="1024" height="1024" fill="#fff"/>
    <path d="${NIB_SLIT}" stroke="#000" stroke-width="9" stroke-linecap="round"/>
    <circle cx="${NIB_HOLE.cx}" cy="${NIB_HOLE.cy}" r="${NIB_HOLE.r}" fill="#000"/>
  </mask>
  <g fill="${color}" opacity="${opacity}">
    <path d="${COVER_L} ${COVER_R}" mask="url(#${id}-cover)"/>
    <path d="${PAGE_L} ${PAGE_R}" mask="url(#${id}-pages)"/>
    <path d="${NIB}" mask="url(#${id}-nib)"/>
    <path d="${STAR}"/>
  </g>`
}

/** The visual centre and size of the drawing inside its 1024 grid (for centring in avatars). */
export const MARK_BOX = { x: 116, y: 112, w: 792, h: 694, cx: 512, cy: 459 }
