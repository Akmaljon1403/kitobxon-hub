// Icons: the bot's menu icons, social-network icons, and menu buttons — gold on navy, gold-ringed.
import { C, FONTS, HANDLE, brandIcon, goldGradient, id, lucide, navyRadial, svgDoc } from './lib.mjs'

export const MENU_ICONS = [
  ['kitoblar', 'book-open', 'Kitoblar'],
  ['asarlar', 'library', 'Asarlar'],
  ['tavsiyalar', 'star', 'Tavsiyalar'],
  ['yangiliklar', 'megaphone', 'Yangiliklar'],
  ['savollar', 'message-circle', 'Savollar'],
  ['statistika', 'chart-column', 'Statistika'],
  ['boglanish', 'send', "Bog'lanish"],
  ['sozlamalar', 'settings', 'Sozlamalar'],
  ['profil', 'user', 'Profil'],
  ['bosh-menyu', 'house', 'Bosh menyu'],
  ['tadbirlar', 'calendar-days', 'Tadbirlar'],
  ['davomat', 'qr-code', 'Davomat'],
  ['testlar', 'clipboard-check', 'Testlar'],
  ['reyting', 'trophy', 'Reyting'],
  ['sertifikat', 'award', 'Sertifikat'],
  ['sovgalar', 'gift', "Sovg'alar"],
  ['premium', 'crown', 'Premium'],
  ['dostlar', 'users', "Do'stlar"],
  ['belgi', 'bookmark', 'Saqlanganlar'],
  ['rivojlanish', 'trending-up', 'Rivojlanish'],
]

/** A round icon: navy disc, gold ring, a gold glyph (Lucide) or a brand mark. */
export function roundIcon(glyph, { brand = false, size = 1000 } = {}) {
  const disc = id('ic')
  const ring = id('rg')
  const c = size / 2
  // Solid gold for the glyph: a gradient stroke disappears on perfectly straight lines.
  const icon = brand ? brandIcon(glyph, c, c, size * 0.42, C.gold) : lucide(glyph, c, c, size * 0.46, C.gold, 1.7)
  return {
    defs: navyRadial(disc, 0.5, 0.3) + goldGradient(ring),
    body: `<circle cx="${c}" cy="${c}" r="${size * 0.49}" fill="url(#${ring})"/>
      <circle cx="${c}" cy="${c}" r="${size * 0.455}" fill="url(#${disc})"/>
      <circle cx="${c}" cy="${c}" r="${size * 0.43}" fill="none" stroke="${C.gold}" stroke-opacity="0.35" stroke-width="${size * 0.004}"/>
      ${icon}`,
  }
}

const BUTTONS = [
  ['kitob-tavsiyalari', 'Kitob tavsiyalari', 'book-open', 'gold'],
  ['yangi-asarlar', 'Yangi asarlar', 'sparkles', 'navy'],
  ['maqsadlarim', 'Maqsadlarim', 'target', 'green'],
  ['hamjamiyat', 'Hamjamiyat', 'users', 'cream'],
  ['sozlamalar', 'Sozlamalar', 'settings', 'navy'],
  ['bot-havolasi', HANDLE, 'telegram', 'navy'],
]
const BUTTON_STYLES = {
  gold: { fill: 'gold', text: C.navy, icon: C.navy, disc: 'rgba(11,31,59,0.12)', border: C.gold300 },
  navy: { fill: 'navy', text: C.cream, icon: C.gold, disc: 'rgba(212,175,55,0.14)', border: C.gold },
  green: { fill: C.green, text: C.cream, icon: C.gold, disc: 'rgba(212,175,55,0.16)', border: C.gold },
  cream: { fill: C.cream, text: C.navy, icon: C.navy, disc: 'rgba(11,31,59,0.08)', border: C.gold },
}

function button(label, icon, style) {
  const s = BUTTON_STYLES[style]
  const g = id('bt')
  const n = id('bn')
  const fill = s.fill === 'gold' ? `url(#${g})` : s.fill === 'navy' ? `url(#${n})` : s.fill
  const glyph = icon === 'telegram' ? brandIcon('telegram', 200, 200, 120, s.icon) : lucide(icon, 200, 200, 124, s.icon, 2)
  return svgDoc(
    2400,
    400,
    `<rect x="20" y="20" width="2360" height="360" rx="180" fill="${fill}" stroke="${s.border}" stroke-width="6"/>
     <circle cx="200" cy="200" r="118" fill="${s.disc}"/>${glyph}
     <text x="380" y="236" font-family="Montserrat" font-weight="600" font-size="104" fill="${s.text}">${label}</text>
     ${lucide('chevron-right', 2210, 200, 120, s.text, 2.4)}`,
    {
      fonts: FONTS.ui,
      defs:
        goldGradient(g, 'h') +
        `<linearGradient id="${n}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${C.navy700}"/><stop offset="1" stop-color="${C.navy900}"/></linearGradient>`,
    },
  )
}

export function iconset(add) {
  for (const [file, glyph] of MENU_ICONS) {
    const { defs, body } = roundIcon(glyph)
    add(`06_Ikonkalar/menyu/${file}`, 1000, 1000, svgDoc(1000, 1000, body, { defs }), { sizes: [1024, 512], preview: '#FFFFFF' })
  }
  for (const [file, glyph, brand] of [
    ['telegram', 'telegram', true],
    ['instagram', 'instagram', true],
    ['youtube', 'youtube', true],
    ['tiktok', 'tiktok', true],
    ['veb-sayt', 'globe', false],
  ]) {
    const { defs, body } = roundIcon(glyph, { brand })
    add(`06_Ikonkalar/ijtimoiy/${file}`, 1000, 1000, svgDoc(1000, 1000, body, { defs }), { sizes: [1024, 512], preview: '#FFFFFF' })
  }
  for (const [file, label, icon, style] of BUTTONS) {
    add(`07_Tugmalar/tugma-${file}`, 2400, 400, button(label, icon, style), { sizes: [2400, 1200], preview: '#FFFFFF' })
  }
}
