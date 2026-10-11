// Watermarks: the mark in one colour (grey, white, black), a signature (mark + name) and a tiled pattern.
import { C, FONTS, LABEL, NAME, id, mark, svgDoc } from './lib.mjs'

export function watermarks(add) {
  for (const [suffix, color, preview] of [
    ['kulrang', C.grey, '#FFFFFF'],
    ['oq', '#FFFFFF', '#555555'],
    ['qora', '#111111', '#FFFFFF'],
  ]) {
    add(`05_Watermark/watermark-belgi-${suffix}`, 1000, 1000, svgDoc(1000, 1000, mark(500, 500, 860, 'mono', color)), {
      sizes: [4096, 1024],
      preview,
    })
    add(
      `05_Watermark/watermark-imzo-${suffix}`,
      2400,
      600,
      svgDoc(
        2400,
        600,
        mark(300, 300, 520, 'mono', color) +
          `<text x="640" y="330" font-family="Libre Baskerville" font-weight="700" font-size="250" fill="${color}">${NAME}</text>` +
          `<text x="650" y="470" font-family="Montserrat" font-weight="700" font-size="70" letter-spacing="40" fill="${color}">${LABEL}</text>`,
        { fonts: FONTS.logo },
      ),
      { fit: 40, sizes: [4096, 1600], preview },
    )
  }
  // A repeating pattern for photos and backgrounds (already faint; lay it over a picture as it is).
  for (const [suffix, color, opacity, preview] of [
    ['oq', '#FFFFFF', 0.12, '#555555'],
    ['navy', C.navy, 0.07, '#FFFFFF'],
  ]) {
    let body = ''
    const step = 480
    for (let row = 0; row < 9; row++) {
      for (let col = 0; col < 9; col++) {
        const x = col * step + (row % 2 ? step / 2 : 0) - step / 2
        const y = row * step - step / 4
        body += `<g transform="rotate(-20 ${x} ${y})">${mark(x, y, 200, 'mono', color)}</g>`
      }
    }
    add(`05_Watermark/watermark-naqsh-${suffix}`, 3840, 3840, svgDoc(3840, 3840, `<g opacity="${opacity}">${body}</g>`), { preview })
  }
  void id
}
