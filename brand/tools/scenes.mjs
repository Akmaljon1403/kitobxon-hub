// Illustrated backgrounds (vector, so they stay sharp in 4K): a night library and a dusk landscape.
import { C, glow, id, mark, star4 } from './lib.mjs'

function random(seed) {
  let s = seed
  return () => ((s = (s * 9301 + 49297) % 233280) / 233280)
}

const SPINES = ['#3B2A1E', '#5A3A22', '#1C3A66', '#13294B', '#6B4E2E', '#7A5A1E', '#0E4A38', '#6E2A2A', '#2A3F5E', '#4A3424']

/** Rows of books on shelves filling (x, y, w, h). */
function shelves(x, y, w, h, rows, seed) {
  const rnd = random(seed)
  const rowH = h / rows
  let out = ''
  for (let r = 0; r < rows; r++) {
    const top = y + r * rowH
    const base = top + rowH - rowH * 0.08
    let cx = x
    while (cx < x + w) {
      const bw = rowH * (0.08 + rnd() * 0.1)
      const bh = rowH * (0.6 + rnd() * 0.3)
      const color = SPINES[Math.floor(rnd() * SPINES.length)]
      const lean = rnd() < 0.06 ? (rnd() - 0.5) * 14 : 0
      const gap = rnd() < 0.08 ? rowH * 0.12 : rowH * 0.008
      const band = rnd() < 0.55
      out += `<g transform="rotate(${lean.toFixed(1)} ${(cx + bw / 2).toFixed(1)} ${base.toFixed(1)})">
        <rect x="${cx.toFixed(1)}" y="${(base - bh).toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="${(bw * 0.08).toFixed(1)}" fill="${color}"/>
        <rect x="${cx.toFixed(1)}" y="${(base - bh).toFixed(1)}" width="${(bw * 0.18).toFixed(1)}" height="${bh.toFixed(1)}" fill="#fff" fill-opacity="0.05"/>
        ${band ? `<rect x="${cx.toFixed(1)}" y="${(base - bh * 0.86).toFixed(1)}" width="${bw.toFixed(1)}" height="${(bh * 0.035).toFixed(1)}" fill="${C.gold}" fill-opacity="0.55"/>
        <rect x="${cx.toFixed(1)}" y="${(base - bh * 0.2).toFixed(1)}" width="${bw.toFixed(1)}" height="${(bh * 0.035).toFixed(1)}" fill="${C.gold}" fill-opacity="0.45"/>` : ''}
      </g>`
      cx += bw + gap
    }
    out += `<rect x="${x}" y="${base.toFixed(1)}" width="${w}" height="${(rowH * 0.08).toFixed(1)}" fill="#2A1F17"/>
      <rect x="${x}" y="${base.toFixed(1)}" width="${w}" height="${(rowH * 0.012).toFixed(1)}" fill="#6B5034" fill-opacity="0.8"/>`
  }
  return out
}

/** A stack of closed books lying on the desk; (x, y) is the bottom-left corner. */
export function bookStack(x, y, unit, seed = 3) {
  const rnd = random(seed)
  const covers = ['#1C3A66', '#5A3A22', '#0E4A38', '#6E2A2A', '#13294B']
  let out = ''
  let top = y
  for (let i = 0; i < 4; i++) {
    const w = unit * (2.6 - i * 0.18 + rnd() * 0.3)
    const h = unit * (0.34 + rnd() * 0.1)
    const shift = (rnd() - 0.5) * unit * 0.4
    const bx = x + shift + i * unit * 0.08
    top -= h
    const color = covers[i % covers.length]
    out += `<rect x="${bx.toFixed(1)}" y="${top.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="${(h * 0.18).toFixed(1)}" fill="${color}"/>
      <rect x="${(bx + w * 0.04).toFixed(1)}" y="${(top + h * 0.2).toFixed(1)}" width="${(w * 0.9).toFixed(1)}" height="${(h * 0.6).toFixed(1)}" rx="${(h * 0.1).toFixed(1)}" fill="${C.paper}"/>
      <path d="M${(bx + w * 0.06).toFixed(1)} ${(top + h * 0.38).toFixed(1)} H${(bx + w * 0.92).toFixed(1)} M${(bx + w * 0.06).toFixed(1)} ${(top + h * 0.58).toFixed(1)} H${(bx + w * 0.92).toFixed(1)}" stroke="#CFC5B0" stroke-width="${(h * 0.04).toFixed(1)}"/>
      <rect x="${(bx + w * 0.86).toFixed(1)}" y="${top.toFixed(1)}" width="${(w * 0.035).toFixed(1)}" height="${h.toFixed(1)}" fill="${C.gold}" fill-opacity="0.7"/>`
  }
  return out
}

/** A navy mug with the gold mark and a wisp of steam; (x, y) is the bottom-left corner. */
export function mug(x, y, unit) {
  const w = unit * 1.5
  const h = unit * 1.7
  const g = id('mg')
  return `<defs><linearGradient id="${g}" x1="0" x2="1"><stop offset="0" stop-color="${C.navy600}"/><stop offset="0.45" stop-color="${C.navy}"/><stop offset="1" stop-color="${C.navy950}"/></linearGradient></defs>
    <path d="M${x + w * 0.95} ${y - h * 0.75} c${unit * 0.55} 0 ${unit * 0.55} ${h * 0.5} 0 ${h * 0.5}" fill="none" stroke="${C.navy}" stroke-width="${unit * 0.16}"/>
    <path d="M${x} ${y - h} h${w} v${h * 0.88} q0 ${h * 0.12} ${-w * 0.12} ${h * 0.12} h${-w * 0.76} q${-w * 0.12} 0 ${-w * 0.12} ${-h * 0.12} z" fill="url(#${g})"/>
    <ellipse cx="${x + w / 2}" cy="${y - h}" rx="${w / 2}" ry="${unit * 0.12}" fill="#2B1B10"/>
    <rect x="${x}" y="${y - h + unit * 0.12}" width="${w}" height="${unit * 0.05}" fill="${C.gold}" fill-opacity="0.7"/>
    ${mark(x + w / 2, y - h * 0.48, w * 0.58, 'mono', C.gold)}
    <g fill="none" stroke="#FFFFFF" stroke-opacity="0.18" stroke-width="${unit * 0.07}" stroke-linecap="round">
      <path d="M${x + w * 0.35} ${y - h * 1.12} c${-unit * 0.3} ${-unit * 0.4} ${unit * 0.3} ${-unit * 0.6} 0 ${-unit * 1.1}"/>
      <path d="M${x + w * 0.62} ${y - h * 1.15} c${-unit * 0.3} ${-unit * 0.4} ${unit * 0.3} ${-unit * 0.6} 0 ${-unit * 0.9}"/>
    </g>`
}

/** The night library: shelves in the dark, a warm lamp, a desk with books and the club's mug. */
export function library(w, h, { lamp = [0.78, 0.12], desk = true, seed = 5, deskItems = true } = {}) {
  const sky = id('lb')
  const halo = id('lh')
  const vignette = id('lv')
  const wood = id('lw')
  const rows = Math.max(3, Math.round(h / (w > h ? 420 : 520)))
  const deskY = h * (w > h ? 0.8 : 0.84)
  const unit = Math.min(w, h) * 0.07
  let bokeh = ''
  const rnd = random(seed + 11)
  for (let i = 0; i < 26; i++) {
    bokeh += `<circle cx="${(rnd() * w).toFixed(0)}" cy="${(rnd() * h * 0.7).toFixed(0)}" r="${(unit * (0.2 + rnd() * 0.6)).toFixed(0)}" fill="${C.gold300}" fill-opacity="${(0.03 + rnd() * 0.06).toFixed(3)}"/>`
  }
  return {
    defs: `<linearGradient id="${sky}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#10233F"/><stop offset="1" stop-color="${C.navy950}"/></linearGradient>
      ${glow(halo, '#F2C46B', 0.55)}
      <radialGradient id="${vignette}" cx="0.5" cy="0.45" r="0.75"><stop offset="0.55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.65"/></radialGradient>
      <linearGradient id="${wood}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4A3424"/><stop offset="0.08" stop-color="#2E2016"/><stop offset="1" stop-color="#140D08"/></linearGradient>`,
    body: `<rect width="${w}" height="${h}" fill="url(#${sky})"/>
      <g opacity="0.55">${shelves(0, h * 0.02, w, deskY - h * 0.02, rows, seed)}</g>
      <rect width="${w}" height="${h}" fill="${C.navy950}" fill-opacity="0.35"/>
      <circle cx="${w * lamp[0]}" cy="${h * lamp[1]}" r="${Math.max(w, h) * 0.45}" fill="url(#${halo})"/>
      <g>
        <path d="M${w * lamp[0] - unit * 0.9} ${h * lamp[1] - unit * 0.1} h${unit * 1.8} l${-unit * 0.35} ${-unit * 0.9} h${-unit * 1.1} z" fill="#1A140E"/>
        <ellipse cx="${w * lamp[0]}" cy="${h * lamp[1] - unit * 0.05}" rx="${unit * 0.75}" ry="${unit * 0.14}" fill="#FFE2A6" fill-opacity="0.9"/>
        <rect x="${w * lamp[0] - unit * 0.03}" y="0" width="${unit * 0.06}" height="${h * lamp[1] - unit}" fill="#1A140E"/>
      </g>
      ${bokeh}
      ${desk ? `<rect y="${deskY}" width="${w}" height="${h - deskY}" fill="url(#${wood})"/>
        <rect y="${deskY}" width="${w}" height="${unit * 0.06}" fill="#8A6A44" fill-opacity="0.6"/>` : ''}
      ${desk && deskItems ? bookStack(w * 0.06, deskY + unit * 0.05, unit) + mug(w * 0.06 + unit * 3.4, deskY + unit * 0.05, unit) : ''}
      <rect width="${w}" height="${h}" fill="url(#${vignette})"/>`,
  }
}

function ridge(w, base, amp, seed, step = 120) {
  const rnd = random(seed)
  const points = []
  for (let x = -step; x <= w + step * 2; x += step) {
    const wave = 0.55 + 0.45 * Math.sin(x / (w * 0.16) + seed) * Math.cos(x / (w * 0.37) + seed * 0.7)
    points.push([x, base - amp * wave * (0.82 + rnd() * 0.18)])
  }
  // A smooth line through the points (quadratic curves between their midpoints).
  let d = `M${points[0][0]} ${points[0][1].toFixed(1)}`
  for (let i = 1; i < points.length - 1; i++) {
    const [x, y] = points[i]
    const [nx, ny] = points[i + 1]
    d += ` Q${x} ${y.toFixed(1)} ${((x + nx) / 2).toFixed(1)} ${((y + ny) / 2).toFixed(1)}`
  }
  return d
}

/** A dusk landscape: sky, a low sun, three mountain ridges, a calm lake with the reflection. */
export function landscape(w, h, { seed = 4 } = {}) {
  const sky = id('ls')
  const sun = id('su')
  const lake = id('lk')
  const horizon = h * 0.6
  const ridges = [
    [horizon - h * 0.02, h * 0.22, '#2B3F66', 0.9],
    [horizon, h * 0.14, '#1C2C4C', 1],
    [horizon + h * 0.004, h * 0.07, '#0F1C33', 1],
  ]
  const mountains = ridges
    .map(([base, amp, color, opacity], i) => `<path d="${ridge(w, base, amp, seed + i * 5)} L${w + 240} ${horizon + 2} L-120 ${horizon + 2} Z" fill="${color}" fill-opacity="${opacity}"/>`)
    .join('')
  let shimmer = ''
  const rnd = random(seed + 3)
  for (let i = 0; i < 60; i++) {
    const y = horizon + (h - horizon) * (0.05 + rnd() * 0.9)
    const x = w * (0.35 + rnd() * 0.3)
    const len = w * (0.02 + rnd() * 0.08)
    shimmer += `<rect x="${(x - len / 2).toFixed(0)}" y="${y.toFixed(0)}" width="${len.toFixed(0)}" height="${(h * 0.0022).toFixed(1)}" rx="2" fill="#F6D9A0" fill-opacity="${(0.08 + rnd() * 0.25).toFixed(2)}"/>`
  }
  let reeds = ''
  for (let i = 0; i < 70; i++) {
    const x = rnd() * w
    if (x > w * 0.25 && x < w * 0.75) continue
    const hh = h * (0.05 + rnd() * 0.09)
    reeds += `<path d="M${x.toFixed(0)} ${h} q${(rnd() - 0.5) * 40} ${-hh / 2} ${(rnd() - 0.5) * 60} ${-hh}" stroke="#050B14" stroke-width="${(w * 0.002).toFixed(1)}" fill="none"/>`
  }
  let stars = ''
  for (let i = 0; i < 40; i++) stars += star4(rnd() * w, rnd() * h * 0.3, w * (0.002 + rnd() * 0.004), '#FFFFFF')
  return {
    defs: `<linearGradient id="${sky}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#0B1F3B"/><stop offset="0.35" stop-color="#2E4470"/><stop offset="0.62" stop-color="#C98F5A"/><stop offset="0.75" stop-color="#F2C98A"/></linearGradient>
      ${glow(sun, '#FFE7B0', 0.9)}
      <linearGradient id="${lake}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#C98F5A" stop-opacity="0.85"/><stop offset="0.25" stop-color="#2E4470"/><stop offset="1" stop-color="#081426"/></linearGradient>`,
    body: `<rect width="${w}" height="${h}" fill="url(#${sky})"/>
      <g opacity="0.5">${stars}</g>
      <circle cx="${w * 0.5}" cy="${horizon - h * 0.06}" r="${w * 0.5}" fill="url(#${sun})"/>
      <circle cx="${w * 0.5}" cy="${horizon - h * 0.05}" r="${w * 0.06}" fill="#FFF1CF"/>
      ${mountains}
      <rect y="${horizon}" width="${w}" height="${h - horizon}" fill="url(#${lake})"/>
      ${shimmer}
      ${reeds}`,
  }
}
