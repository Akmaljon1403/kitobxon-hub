// Telegram avatars (the bot, the club channel, the payments channel, the admins' group) and app icons.
import { C, glow, goldGradient, id, lucide, mark, navyRadial, starField, svgDoc } from './lib.mjs'

const S = 2048 // drawing size; rendered at 4096 and at the sizes Telegram and browsers use

function avatar({ light = false, badge = null, colors = null } = {}) {
  const back = id('bg')
  const ring = id('rg')
  const halo = id('gl')
  const defs =
    (light
      ? `<radialGradient id="${back}" cx="0.5" cy="0.35" r="0.85"><stop offset="0" stop-color="#FFFFFF"/><stop offset="0.6" stop-color="${C.cream}"/><stop offset="1" stop-color="${C.paper}"/></radialGradient>`
      : colors
        ? `<radialGradient id="${back}" cx="0.5" cy="0.35" r="0.85"><stop offset="0" stop-color="${colors[0]}"/><stop offset="1" stop-color="${colors[1]}"/></radialGradient>`
        : navyRadial(back)) +
    goldGradient(ring) +
    glow(halo, C.gold, light ? 0.1 : 0.18)
  const body = `
    <rect width="${S}" height="${S}" fill="url(#${back})"/>
    ${starField(S, S, light ? C.navy : C.gold, light ? 0.05 : 0.07, 170, 15)}
    <circle cx="${S / 2}" cy="${S * 0.45}" r="${S * 0.42}" fill="url(#${halo})"/>
    <circle cx="${S / 2}" cy="${S / 2}" r="${S * 0.462}" fill="none" stroke="url(#${ring})" stroke-width="${S * 0.016}"/>
    <circle cx="${S / 2}" cy="${S / 2}" r="${S * 0.437}" fill="none" stroke="${C.gold}" stroke-opacity="0.45" stroke-width="${S * 0.004}"/>
    ${mark(S / 2, S * 0.5, S * 0.6, light ? 'light' : 'dark')}
    ${badge ?? ''}`
  return svgDoc(S, S, body, { defs })
}

function badge(icon, fill) {
  const g = id('bg')
  const x = S * 0.735
  const y = S * 0.735
  const r = S * 0.15
  return `<defs>${goldGradient(g)}</defs>
    <circle cx="${x}" cy="${y}" r="${r + S * 0.022}" fill="${C.navy950}"/>
    <circle cx="${x}" cy="${y}" r="${r}" fill="url(#${g})"/>
    <circle cx="${x}" cy="${y}" r="${r * 0.82}" fill="${fill}"/>
    ${lucide(icon, x, y, r * 1.0, C.gold, 1.9)}`
}

/** A rounded-square app icon. `inset` leaves room for platforms that cut the corners (maskable). */
function appIcon({ radius = 0.225, border = true, inset = 0 } = {}) {
  const back = id('bg')
  const ring = id('rg')
  const halo = id('gl')
  const r = S * radius
  return svgDoc(
    S,
    S,
    `<rect width="${S}" height="${S}" rx="${r}" fill="url(#${back})"/>
     <circle cx="${S / 2}" cy="${S * 0.45}" r="${S * 0.42}" fill="url(#${halo})"/>
     ${border ? `<rect x="${S * 0.02}" y="${S * 0.02}" width="${S * 0.96}" height="${S * 0.96}" rx="${r * 0.92}" fill="none" stroke="url(#${ring})" stroke-width="${S * 0.022}"/>` : ''}
     ${mark(S / 2, S * 0.5, S * (0.7 - inset * 1.6), 'dark')}`,
    { defs: navyRadial(back) + goldGradient(ring) + glow(halo, C.gold, 0.16) },
  )
}

export function avatars(add) {
  const telegram = { sizes: [4096, 640], preview: '#FFFFFF', opaque: true }
  add('02_Avatar/telegram-bot-avatar', S, S, avatar(), telegram)
  add('02_Avatar/telegram-kanal-avatar', S, S, avatar({ light: true }), telegram)
  add('02_Avatar/telegram-tolovlar-kanali-avatar', S, S, avatar({ badge: badge('credit-card', C.navy) }), telegram)
  add(
    '02_Avatar/telegram-adminlar-guruhi-avatar',
    S,
    S,
    avatar({ badge: badge('shield-check', C.navy), colors: ['#25406B', C.navy950] }),
    telegram,
  )
  add('03_Ikonka_ilova/app-icon', S, S, appIcon(), { sizes: [4096, 1024, 512, 192, 180, 48, 32, 16], preview: '#FFFFFF' })
  add('03_Ikonka_ilova/app-icon-maskable', S, S, appIcon({ radius: 0, border: false, inset: 0.08 }), {
    sizes: [1024, 512, 192],
    opaque: true,
    preview: '#FFFFFF',
  })
}
