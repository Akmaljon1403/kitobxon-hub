// Banners and posts: the Telegram channel banner, link previews, the bot's description picture,
// a story, a quote card, a motivation post and a features card — all in 4K.
import { C, FONTS, HANDLE, LABEL, NAME, SLOGAN, brandIcon, glow, id, labelLeft, lucide, mark, svgDoc, textWidth, wordmark } from './lib.mjs'
import { landscape, library } from './scenes.mjs'

const ALL = [...FONTS.logo, ...FONTS.ui, ...FONTS.quote]

/** The bot's Telegram handle with the Telegram icon in front; `anchor` middle centres the pair. */
const handle = (x, y, size, color = C.cream, anchor = 'start') => {
  const text = textWidth(HANDLE, size)
  const total = size * 1.5 + text
  const left = anchor === 'middle' ? x - total / 2 : x
  return `${brandIcon('telegram', left + size * 0.55, y - size * 0.36, size * 1.1, C.gold)}
    <text x="${left + size * 1.5}" y="${y}" font-family="Montserrat" font-weight="600" font-size="${size}" fill="${color}">${HANDLE}</text>`
}

/** A dark panel fading into the picture (so text stays readable). */
const fade = (gid, direction = 'left', strength = 0.92) =>
  `<linearGradient id="${gid}" x1="${direction === 'left' ? 1 : 0}" y1="${direction === 'up' ? 1 : 0}" x2="${direction === 'left' ? 0 : 0}" y2="${direction === 'up' ? 0 : direction === 'down' ? 1 : 0}">
    <stop offset="0" stop-color="${C.navy950}" stop-opacity="${strength}"/><stop offset="0.55" stop-color="${C.navy950}" stop-opacity="${strength * 0.75}"/>
    <stop offset="1" stop-color="${C.navy950}" stop-opacity="0"/></linearGradient>`

function telegramBanner(w, h, { quote = 'Bir kitob —\nming dunyo' } = {}) {
  const scene = library(w, h, { lamp: [0.3, 0.1], seed: 9 })
  const panel = id('pn')
  const lines = quote.split('\n')
  const s = h / 2160
  return svgDoc(
    w,
    h,
    `${scene.body}
     <rect x="${w * 0.45}" width="${w * 0.55}" height="${h}" fill="url(#${panel})"/>
     ${lines.map((line, i) => `<text x="${w * 0.94}" y="${h * 0.17 + i * 120 * s}" text-anchor="end" font-family="Lora" font-style="italic" font-weight="500" font-size="${104 * s}" fill="${C.cream}" fill-opacity="0.9">${line}</text>`).join('')}
     ${mark(w * 0.75, h * 0.44, 640 * s, 'dark')}
     ${wordmark(w * 0.75, h * 0.72, 250 * s, { ink: C.cream, gold: C.gold, tagline: SLOGAN })}
     ${handle(w * 0.75, h * 0.92, 64 * s, C.cream, 'middle')}`,
    { fonts: ALL, defs: scene.defs + fade(panel, 'left', 0.95) },
  )
}

function wideBanner(w, h) {
  const scene = library(w, h, { lamp: [0.88, 0.05], seed: 13, deskItems: false })
  const panel = id('pn')
  const s = Math.min(h / 1280, w / 3840)
  const cy = h / 2
  const x = w * 0.08
  return svgDoc(
    w,
    h,
    `${scene.body}
     <rect width="${w * 0.75}" height="${h}" fill="url(#${panel})"/>
     ${mark(x + 330 * s, cy - 20 * s, 640 * s, 'dark')}
     <text x="${x + 760 * s}" y="${cy - 10 * s}" font-family="Libre Baskerville" font-weight="700" font-size="${280 * s}" fill="${C.cream}">${NAME}</text>
     ${labelLeft(x + 772 * s, cy + 160 * s, 280 * s, C.gold)}
     <text x="${x + 772 * s}" y="${cy + 330 * s}" font-family="Montserrat" font-weight="500" font-size="${80 * s}" fill="${C.cream}" fill-opacity="0.92">${SLOGAN}</text>
     ${handle(x + 770 * s, cy + 470 * s, 60 * s, C.cream)}`,
    { fonts: ALL, defs: scene.defs + fade(panel, 'right', 0.96) },
  )
}

function descriptionPicture(w, h) {
  const scene = library(w, h, { lamp: [0.5, 0.06], seed: 21 })
  const veil = id('vl')
  const s = h / 2160
  return svgDoc(
    w,
    h,
    `${scene.body}
     <rect width="${w}" height="${h}" fill="url(#${veil})"/>
     ${mark(w / 2, h * 0.37, 700 * s, 'dark')}
     ${wordmark(w / 2, h * 0.74, 260 * s, { ink: C.cream, gold: C.gold, tagline: SLOGAN })}`,
    {
      fonts: ALL,
      defs: scene.defs + `<radialGradient id="${veil}" cx="0.5" cy="0.5" r="0.7"><stop offset="0" stop-color="${C.navy950}" stop-opacity="0.75"/><stop offset="1" stop-color="${C.navy950}" stop-opacity="0.3"/></radialGradient>`,
    },
  )
}

function story(w, h) {
  const scene = library(w, h, { lamp: [0.7, 0.07], seed: 17 })
  const panel = id('pn')
  const s = w / 2160
  return svgDoc(
    w,
    h,
    `${scene.body}
     <rect y="${h * 0.18}" width="${w}" height="${h * 0.62}" fill="url(#${panel})"/>
     ${mark(w / 2, h * 0.36, 1100 * s, 'dark')}
     ${wordmark(w / 2, h * 0.6, 380 * s, { ink: C.cream, gold: C.gold })}
     <text x="${w / 2}" y="${h * 0.7}" text-anchor="middle" font-family="Montserrat" font-weight="500" font-size="${92 * s}" fill="${C.cream}">${SLOGAN}</text>
     <rect x="${w / 2 - 560 * s}" y="${h * 0.9 - 110 * s}" width="${1120 * s}" height="${170 * s}" rx="${85 * s}" fill="${C.navy}" fill-opacity="0.85" stroke="${C.gold}" stroke-width="${4 * s}"/>
     ${handle(w / 2, h * 0.9, 76 * s, C.cream, 'middle')}`,
    {
      fonts: ALL,
      defs:
        scene.defs +
        `<radialGradient id="${panel}" cx="0.5" cy="0.5" r="0.6"><stop offset="0" stop-color="${C.navy950}" stop-opacity="0.85"/><stop offset="1" stop-color="${C.navy950}" stop-opacity="0"/></radialGradient>`,
    },
  )
}

function motivation(w, h, quote) {
  const scene = landscape(w, h, { seed: 6 })
  const s = w / 2160
  const veil = id('vl')
  const lines = quote.split('\n')
  return svgDoc(
    w,
    h,
    `${scene.body}
     <rect width="${w}" height="${h * 0.5}" fill="url(#${veil})"/>
     ${lines.map((line, i) => `<text x="${w * 0.08}" y="${h * 0.12 + i * 150 * s}" font-family="Lora" font-style="italic" font-weight="600" font-size="${120 * s}" fill="${C.cream}">${line}</text>`).join('')}
     <rect x="${w * 0.08}" y="${h * 0.12 + lines.length * 150 * s - 40 * s}" width="${180 * s}" height="${8 * s}" rx="${4 * s}" fill="${C.gold}"/>
     <rect y="${h * 0.7}" width="${w}" height="${h * 0.3}" fill="url(#${veil}b)"/>
     ${mark(w / 2, h * 0.83, 420 * s, 'dark')}
     ${wordmark(w / 2, h * 0.93, 150 * s, { ink: C.cream, gold: C.gold })}`,
    {
      fonts: ALL,
      defs:
        scene.defs +
        `<linearGradient id="${veil}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${C.navy950}" stop-opacity="0.75"/><stop offset="1" stop-color="${C.navy950}" stop-opacity="0"/></linearGradient>` +
        `<linearGradient id="${veil}b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${C.navy950}" stop-opacity="0"/><stop offset="1" stop-color="${C.navy950}" stop-opacity="0.85"/></linearGradient>`,
    },
  )
}

function quoteCard(w, h, quote) {
  const back = id('bg')
  const halo = id('gl')
  const s = w / 2160
  const lines = quote.split('\n')
  return svgDoc(
    w,
    h,
    `<rect width="${w}" height="${h}" fill="url(#${back})"/>
     <circle cx="${w / 2}" cy="${h * 0.32}" r="${w * 0.5}" fill="url(#${halo})"/>
     <rect x="${60 * s}" y="${60 * s}" width="${w - 120 * s}" height="${h - 120 * s}" rx="${40 * s}" fill="none" stroke="${C.gold}" stroke-opacity="0.6" stroke-width="${4 * s}"/>
     ${mark(w / 2, h * 0.27, 560 * s, 'dark')}
     ${lines.map((line, i) => `<text x="${w / 2}" y="${h * 0.56 + i * 140 * s}" text-anchor="middle" font-family="Lora" font-style="italic" font-weight="500" font-size="${112 * s}" fill="${C.cream}">${line}</text>`).join('')}
     <rect x="${w / 2 - 90 * s}" y="${h * 0.56 + lines.length * 140 * s - 20 * s}" width="${180 * s}" height="${7 * s}" rx="${3 * s}" fill="${C.gold}"/>
     ${wordmark(w / 2, h * 0.86, 140 * s, { ink: C.cream, gold: C.gold })}`,
    {
      fonts: ALL,
      defs:
        `<linearGradient id="${back}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${C.navy700}"/><stop offset="1" stop-color="${C.navy950}"/></linearGradient>` +
        glow(halo, C.gold, 0.14),
    },
  )
}

const FEATURES = [
  ['book-open', 'Kitoblar va o‘qish muddatlari'],
  ['calendar-days', 'Tadbirlar va QR davomat'],
  ['clipboard-check', 'Kitoblar bo‘yicha testlar'],
  ['trophy', 'Ballar, reyting va yutuqlar'],
  ['award', 'Sertifikatlar va kitobxon pasporti'],
  ['users', 'Do‘stlar va kitobxonlar hamjamiyati'],
]

function featuresCard(w, h) {
  const back = id('bg')
  const halo = id('gl')
  const s = w / 2160
  const rows = FEATURES.map(([icon, text], i) => {
    const y = h * 0.42 + i * 300 * s
    return `<rect x="${170 * s}" y="${y - 120 * s}" width="${w - 340 * s}" height="${230 * s}" rx="${115 * s}" fill="${C.navy}" fill-opacity="0.75" stroke="${C.gold}" stroke-opacity="0.45" stroke-width="${3 * s}"/>
      <circle cx="${300 * s}" cy="${y - 5 * s}" r="${78 * s}" fill="${C.gold}" fill-opacity="0.14" stroke="${C.gold}" stroke-width="${4 * s}"/>
      ${lucide(icon, 300 * s, y - 5 * s, 86 * s, C.gold, 1.8)}
      <text x="${430 * s}" y="${y + 26 * s}" font-family="Montserrat" font-weight="600" font-size="${76 * s}" fill="${C.cream}">${text}</text>`
  }).join('')
  return svgDoc(
    w,
    h,
    `<rect width="${w}" height="${h}" fill="url(#${back})"/>
     <circle cx="${w / 2}" cy="${h * 0.12}" r="${w * 0.6}" fill="url(#${halo})"/>
     ${mark(w / 2, h * 0.13, 640 * s, 'dark')}
     ${wordmark(w / 2, h * 0.28, 260 * s, { ink: C.cream, gold: C.gold })}
     ${rows}
     ${handle(w / 2, h * 0.95, 72 * s, C.cream, 'middle')}`,
    {
      fonts: ALL,
      defs:
        `<linearGradient id="${back}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${C.navy700}"/><stop offset="1" stop-color="${C.navy950}"/></linearGradient>` +
        glow(halo, C.gold, 0.12),
    },
  )
}

export function social(add) {
  add('08_Banner/telegram-kanal-banner-16x9', 3840, 2160, telegramBanner(3840, 2160), { sizes: [3840, 1920], opaque: true })
  add('08_Banner/keng-banner-3x1', 3840, 1280, wideBanner(3840, 1280), { sizes: [3840, 1920], opaque: true })
  add('08_Banner/havola-rasmi-og', 3840, 2016, wideBanner(3840, 2016), { sizes: [3840, 1200], opaque: true })
  add('08_Banner/bot-tavsif-rasmi', 3840, 2160, descriptionPicture(3840, 2160), { sizes: [3840, 640], opaque: true })
  add('09_Postlar/story-status-9x16', 2160, 3840, story(2160, 3840), { sizes: [2160, 1080], opaque: true })
  add('09_Postlar/motivatsiya-post-4x5', 2160, 2700, motivation(2160, 2700, 'Kitob o‘qish — bu\no‘z hayotingizga\nyangi nuqtai nazar\ntopishdir.'), { sizes: [2160, 1080], opaque: true })
  add('09_Postlar/iqtibos-post-1x1', 2160, 2160, quoteCard(2160, 2160, 'Bugun bir kitob o‘qi,\nertaga yangi sen bo‘l.'), { sizes: [2160, 1080], opaque: true })
  add('09_Postlar/imkoniyatlar-kartasi-9x16', 2160, 3840, featuresCard(2160, 3840), { sizes: [2160, 1080], opaque: true })
}
