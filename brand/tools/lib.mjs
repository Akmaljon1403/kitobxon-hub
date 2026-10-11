// Shared drawing helpers: documents, the mark placed by its visual centre, the wordmark, icons.
import { BRANDS, LUCIDE } from './icondata.mjs'
import { C, MARK_BOX, markDark, markDefs, markLight, markMono } from './mark.mjs'
import { readFileSync } from 'node:fs'

import { fontFaces } from './render.mjs'

const METRICS = JSON.parse(readFileSync(new URL('./metrics.json', import.meta.url), 'utf8'))

export { C }
export const NAME = 'Kitobxon'
export const LABEL = 'BOT'
export const HANDLE = '@kitobxonhub_bot'
export const SLOGAN = 'Yaxshi kitob — yaxshi kelajak'
export const SLOGANS = [
  'Yaxshi kitob — yaxshi kelajak',
  'Kitob o‘qish — o‘sish demak',
  'Har bir kitob — yangi imkoniyat',
  'O‘qish — erkinlik',
  'Bir kitob — ming dunyo',
]

export const FONTS = {
  logo: ['Libre Baskerville 700', 'Montserrat 700', 'Montserrat 500'],
  ui: ['Montserrat 500', 'Montserrat 600', 'Montserrat 700', 'Montserrat 800'],
  quote: ['Lora 500 italic', 'Lora 600 italic'],
  sticker: ['Nunito 900', 'Nunito 800'],
}
export const ALL_FONTS = [...new Set(Object.values(FONTS).flat())]

let uid = 0
export const id = (prefix = 'g') => `${prefix}${++uid}`

export const svgDoc = (w, h, body, { fonts = null, defs = '' } = {}) =>
  `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}">` +
  `<defs>${fonts ? `<style>${fontFaces(fonts)}</style>` : ''}${defs}</defs>${body}</svg>`

/** The mark drawn so that its visual centre is (cx, cy) and its drawing is `width` wide. */
export function mark(cx, cy, width, kind = 'dark', color = C.navy) {
  const k = width / MARK_BOX.w
  const tag = id('mk')
  const body =
    kind === 'dark'
      ? markDefs(tag) + markDark(tag)
      : kind === 'light'
        ? markDefs(tag) + markLight(tag)
        : markMono(color, tag)
  return `<g transform="translate(${(cx - MARK_BOX.cx * k).toFixed(2)} ${(cy - MARK_BOX.cy * k).toFixed(2)}) scale(${k.toFixed(5)})">${body}</g>`
}
export const markHeight = (width) => (width * MARK_BOX.h) / MARK_BOX.w

/** «Kitobxon» with «— BOT —» under it (centred on x). `size` is the font size of the name. */
export function wordmark(x, y, size, { ink = C.cream, gold = C.gold, label = LABEL, tagline = null, tagColor = null } = {}) {
  const ls = size * 0.22
  const fs = size * 0.26
  const ly = y + size * 0.56
  const half = (label.length * fs * 0.74 + (label.length - 1) * ls) / 2
  const gap = size * 0.2
  const line = size * 0.5
  const t = size * 0.024
  return `
  <text x="${x}" y="${y}" text-anchor="middle" font-family="Libre Baskerville" font-weight="700" font-size="${size}"
    letter-spacing="${size * -0.01}" fill="${ink}">${NAME}</text>
  <text x="${x + ls / 2}" y="${ly}" text-anchor="middle" font-family="Montserrat" font-weight="700" font-size="${fs}"
    letter-spacing="${ls}" fill="${gold}">${label}</text>
  <rect x="${x - half - gap - line}" y="${ly - fs * 0.36 - t / 2}" width="${line}" height="${t}" rx="${t / 2}" fill="${gold}"/>
  <rect x="${x + half + gap}" y="${ly - fs * 0.36 - t / 2}" width="${line}" height="${t}" rx="${t / 2}" fill="${gold}"/>
  ${tagline ? `<text x="${x}" y="${ly + size * 0.62}" text-anchor="middle" font-family="Montserrat" font-weight="500"
    font-size="${size * 0.25}" letter-spacing="${size * 0.004}" fill="${tagColor ?? ink}">${tagline}</text>` : ''}`
}

/** A Lucide icon (24 grid) centred on (cx, cy), `size` wide, drawn as lines. */
export const lucide = (name, cx, cy, size, color, stroke = 1.75) =>
  `<g transform="translate(${cx - size / 2} ${cy - size / 2}) scale(${size / 24})" fill="none" stroke="${color}"
    stroke-width="${stroke}" stroke-linecap="round" stroke-linejoin="round">${LUCIDE[name]}</g>`

/** A brand mark (Simple Icons, 24 grid, filled). */
export const brandIcon = (name, cx, cy, size, color) =>
  `<g transform="translate(${cx - size / 2} ${cy - size / 2}) scale(${size / 24})"><path d="${BRANDS[name]}" fill="${color}"/></g>`

export const goldGradient = (gid, angle = 'v') =>
  `<linearGradient id="${gid}" x1="0" y1="0" x2="${angle === 'v' ? 0.3 : 1}" y2="${angle === 'v' ? 1 : 0.4}">
    <stop offset="0" stop-color="${C.gold300}"/><stop offset="0.5" stop-color="${C.gold}"/><stop offset="1" stop-color="${C.gold600}"/>
  </linearGradient>`

export const navyRadial = (gid, cx = 0.5, cy = 0.35) =>
  `<radialGradient id="${gid}" cx="${cx}" cy="${cy}" r="0.85">
    <stop offset="0" stop-color="${C.navy600}"/><stop offset="0.55" stop-color="${C.navy}"/><stop offset="1" stop-color="${C.navy950}"/>
  </radialGradient>`

/** A soft glow (lamp light, halo). */
export const glow = (gid, color = C.gold, opacity = 0.35) =>
  `<radialGradient id="${gid}"><stop offset="0" stop-color="${color}" stop-opacity="${opacity}"/>
    <stop offset="1" stop-color="${color}" stop-opacity="0"/></radialGradient>`

/** A faint field of four-pointed stars. */
export function starField(w, h, color, opacity, step, r, seed = 7) {
  let d = ''
  let s = seed
  const rnd = () => ((s = (s * 9301 + 49297) % 233280) / 233280)
  for (let y = step / 2; y < h; y += step) {
    for (let x = step / 2; x < w; x += step) {
      const px = x + (rnd() - 0.5) * step * 0.8
      const py = y + (rnd() - 0.5) * step * 0.8
      const rr = r * (0.4 + rnd() * 0.9)
      d += `M${px.toFixed(1)} ${(py - rr).toFixed(1)} Q${(px + rr * 0.18).toFixed(1)} ${(py - rr * 0.18).toFixed(1)} ${(px + rr).toFixed(1)} ${py.toFixed(1)} Q${(px + rr * 0.18).toFixed(1)} ${(py + rr * 0.18).toFixed(1)} ${px.toFixed(1)} ${(py + rr).toFixed(1)} Q${(px - rr * 0.18).toFixed(1)} ${(py + rr * 0.18).toFixed(1)} ${(px - rr).toFixed(1)} ${py.toFixed(1)} Q${(px - rr * 0.18).toFixed(1)} ${(py - rr * 0.18).toFixed(1)} ${px.toFixed(1)} ${(py - rr).toFixed(1)} Z `
    }
  }
  return `<path d="${d}" fill="${color}" fill-opacity="${opacity}"/>`
}

/** A four-pointed star centred on (x, y). */
export const star4 = (x, y, r, fill) =>
  `<path d="M${x} ${y - r} Q${x + r * 0.17} ${y - r * 0.17} ${x + r} ${y} Q${x + r * 0.17} ${y + r * 0.17} ${x} ${y + r} Q${x - r * 0.17} ${y + r * 0.17} ${x - r} ${y} Q${x - r * 0.17} ${y - r * 0.17} ${x} ${y - r} Z" fill="${fill}"/>`

/** Text set on a circle, letter by letter (exact advance widths, so the spacing is even).
 * `top` text reads clockwise over the top; otherwise it reads left to right along the bottom, upright.
 * The text is centred on twelve (top) or six (bottom) o'clock; `tracking` adds space between letters (em). */
export function arcText(text, { cx, cy, r, size, font = 'Montserrat 700', top = true, tracking = 0.12, fill = 'currentColor' }) {
  const widths = METRICS[font]
  const [family, weight] = [font.replace(/ \d+$/, ''), font.match(/\d+$/)[0]]
  const advance = [...text].map((ch) => ((widths[ch] ?? 0.6) + tracking) * size)
  const total = advance.reduce((a, b) => a + b, 0) - tracking * size
  let at = -total / 2
  return [...text]
    .map((ch, i) => {
      const middle = at + ((widths[ch] ?? 0.6) * size) / 2
      at += advance[i]
      if (ch === ' ') return ''
      const angle = (middle / r) * (180 / Math.PI) // degrees along the arc from the centre line
      const deg = top ? -90 + angle : 90 - angle
      const rad = (deg * Math.PI) / 180
      const x = cx + r * Math.cos(rad)
      const y = cy + r * Math.sin(rad)
      const rotate = top ? deg + 90 : deg - 90
      const esc = ch === '&' ? '&amp;' : ch === '<' ? '&lt;' : ch
      return `<text x="0" y="0" transform="translate(${x.toFixed(2)} ${y.toFixed(2)}) rotate(${rotate.toFixed(2)})" text-anchor="middle"
        font-family="${family}" font-weight="${weight}" font-size="${size}" fill="${fill}">${esc}</text>`
    })
    .join('')
}

/** How far (degrees) a text spans on a circle of radius r. */
export function arcSpan(text, r, size, font = 'Montserrat 700', tracking = 0.12) {
  const widths = METRICS[font]
  const total = [...text].reduce((sum, ch) => sum + ((widths[ch] ?? 0.6) + tracking) * size, 0) - tracking * size
  return (total / r) * (180 / Math.PI)
}

/** The width of a line of Montserrat (bold metrics; a hair wide for lighter weights). */
export function textWidth(text, size, font = 'Montserrat 700') {
  const widths = METRICS[font]
  return [...text].reduce((sum, ch) => sum + (widths[ch] ?? 0.6), 0) * size * 0.97
}

/** «— BOT —» set from the left edge (horizontal logos and banners); `size` is the name's font size. */
export function labelLeft(x, y, size, gold, label = LABEL) {
  const ls = size * 0.22
  const fs = size * 0.26
  const line = size * 0.42
  const gap = size * 0.16
  const t = size * 0.024
  const text = textWidth(label, fs) + (label.length - 1) * ls
  return `<rect x="${x}" y="${y - fs * 0.36 - t / 2}" width="${line}" height="${t}" rx="${t / 2}" fill="${gold}"/>
    <text x="${x + line + gap}" y="${y}" font-family="Montserrat" font-weight="700" font-size="${fs}" letter-spacing="${ls}" fill="${gold}">${label}</text>
    <rect x="${x + line + gap + text + gap}" y="${y - fs * 0.36 - t / 2}" width="${line}" height="${t}" rx="${t / 2}" fill="${gold}"/>`
}
