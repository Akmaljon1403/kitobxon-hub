// Logos: the mark alone, the stacked logo, the horizontal logo and the round badge.
import { C, FONTS, NAME, SLOGAN, glow, goldGradient, id, labelLeft, mark, navyRadial, svgDoc, wordmark } from './lib.mjs'

const MARK_KINDS = {
  'dark-bg': ['dark'],
  'light-bg': ['light'],
  white: ['mono', '#FFFFFF'],
  black: ['mono', '#111111'],
  gold: ['mono', C.gold],
  navy: ['mono', C.navy],
}

export function logos(add) {
  // The mark alone (transparent, square).
  for (const [suffix, [kind, color]] of Object.entries(MARK_KINDS)) {
    add(`01_Logotip/belgi/kitobxon-belgi-${suffix}`, 1000, 1000, svgDoc(1000, 1000, mark(500, 500, 860, kind, color)), {
      sizes: [4096, 1024, 512],
      preview: suffix === 'dark-bg' || suffix === 'white' || suffix === 'gold' ? C.navy : '#FFFFFF',
    })
  }

  // Stacked logo: mark, name, «— BOT —», slogan.
  const stacked = (ink, kind, tagColor, color) => {
    const body = mark(1000, 520, 1240, kind, color) + wordmark(1000, 1420, 330, { ink, gold: kind === 'mono' ? ink : C.gold, tagline: SLOGAN, tagColor })
    return svgDoc(2000, 2000, body, { fonts: FONTS.logo })
  }
  add('01_Logotip/asosiy/kitobxon-logo-dark-bg', 2000, 2000, stacked(C.cream, 'dark', C.cream), { fit: 80, sizes: [4096, 1024], preview: C.navy })
  add('01_Logotip/asosiy/kitobxon-logo-light-bg', 2000, 2000, stacked(C.navy, 'light', C.navy), { fit: 80, sizes: [4096, 1024] })
  add('01_Logotip/asosiy/kitobxon-logo-white', 2000, 2000, stacked('#FFFFFF', 'mono', '#FFFFFF', '#FFFFFF'), { fit: 80, sizes: [4096], preview: C.navy })
  add('01_Logotip/asosiy/kitobxon-logo-black', 2000, 2000, stacked('#111111', 'mono', '#111111', '#111111'), { fit: 80, sizes: [4096] })

  // The stacked logo on its navy card (as on the brand board), 4096 square.
  const card = id('bg')
  const lamp = id('gl')
  add(
    '01_Logotip/asosiy/kitobxon-logo-navy-card',
    2000,
    2000,
    svgDoc(
      2000,
      2000,
      `<rect width="2000" height="2000" fill="url(#${card})"/><circle cx="1000" cy="560" r="760" fill="url(#${lamp})"/>` +
        mark(1000, 640, 1060, 'dark') +
        wordmark(1000, 1460, 300, { ink: C.cream, gold: C.gold, tagline: SLOGAN }),
      { fonts: FONTS.logo, defs: navyRadial(card, 0.5, 0.3) + glow(lamp, C.gold, 0.16) },
    ),
    { sizes: [4096, 1080], opaque: true },
  )

  // Horizontal logo: the mark, then the name over «— BOT —».
  const horizontal = (ink, kind, color, gold = C.gold) => {
    const body =
      mark(330, 300, 660, kind, color) +
      `<text x="720" y="${300 + 40}" font-family="Libre Baskerville" font-weight="700" font-size="300" letter-spacing="-3" fill="${ink}">${NAME}</text>` +
      `<g>${labelLeft(736, 300 + 196, 300, gold)}</g>`
    return svgDoc(2400, 600, body, { fonts: FONTS.logo })
  }
  add('01_Logotip/gorizontal/kitobxon-gorizontal-dark-bg', 2400, 600, horizontal(C.cream, 'dark'), { fit: 60, sizes: [4096, 1600], preview: C.navy })
  add('01_Logotip/gorizontal/kitobxon-gorizontal-light-bg', 2400, 600, horizontal(C.navy, 'light'), { fit: 60, sizes: [4096, 1600] })
  add('01_Logotip/gorizontal/kitobxon-gorizontal-white', 2400, 600, horizontal('#FFFFFF', 'mono', '#FFFFFF', '#FFFFFF'), { fit: 60, sizes: [4096], preview: C.navy })
  add('01_Logotip/gorizontal/kitobxon-gorizontal-black', 2400, 600, horizontal('#111111', 'mono', '#111111', '#111111'), { fit: 60, sizes: [4096] })

  // Round badge: the mark in a navy disc with a gold ring (small places: watermarks on photos, stickers).
  for (const [suffix, fill, ring, kind] of [
    ['navy', C.navy, C.gold, 'dark'],
    ['cream', C.cream, C.gold, 'light'],
  ]) {
    const disc = id('bd')
    const gold = id('gg')
    add(
      `01_Logotip/nishon/kitobxon-nishon-${suffix}`,
      1000,
      1000,
      svgDoc(
        1000,
        1000,
        `<circle cx="500" cy="500" r="490" fill="url(#${gold})"/><circle cx="500" cy="500" r="458" fill="${suffix === 'navy' ? `url(#${disc})` : fill}"/>` +
          `<circle cx="500" cy="500" r="436" fill="none" stroke="${ring}" stroke-opacity="0.45" stroke-width="3"/>` +
          mark(500, 512, 600, kind),
        { defs: navyRadial(disc) + goldGradient(gold) },
      ),
      { sizes: [4096, 1024, 512], preview: '#FFFFFF' },
    )
  }
}
