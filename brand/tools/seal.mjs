// The club's round seal («pechat»): blue ink (clean and stamped), navy, and gold foil for dark designs.
// It is the club's own seal for its certificates and letters — not the institute's official one.
import { C, FONTS, arcSpan, arcText, goldGradient, id, star4, svgDoc } from './lib.mjs'
import { markMono } from './mark.mjs'

const TOP = 'KITOBXON • KITOBXONLAR KLUBI'
const BOTTOM = 'YAXSHI KITOB — YAXSHI KELAJAK'

function seal(color, { ink = false, foil = false } = {}) {
  const tag = id('seal')
  const paint = foil ? `url(#${tag}-foil)` : color
  const size = 64
  // The top text sits with its baseline on r = 450 (letters outward); the bottom text's cap line on 450.
  const top = arcText(TOP, { cx: 600, cy: 600, r: 450, size, top: true, tracking: 0.16, fill: paint })
  const bottom = arcText(BOTTOM, { cx: 600, cy: 600, r: 450 + size * 0.7, size, top: false, tracking: 0.1, fill: paint })
  // Stars where the two texts meet (left and right), half-way between their ends.
  const topSpan = arcSpan(TOP, 450, size, 'Montserrat 700', 0.16)
  const bottomSpan = arcSpan(BOTTOM, 450 + size * 0.7, size, 'Montserrat 700', 0.1)
  const gapMiddle = (180 - topSpan / 2 - bottomSpan / 2) / 2
  const starAt = (deg) => {
    const rad = (deg * Math.PI) / 180
    return star4(600 + 472 * Math.cos(rad), 600 + 472 * Math.sin(rad), 22, paint)
  }
  const dots = Array.from({ length: 96 }, (_, i) => {
    const a = (i / 96) * Math.PI * 2
    return `<circle cx="${(600 + 372 * Math.cos(a)).toFixed(2)}" cy="${(600 + 372 * Math.sin(a)).toFixed(2)}" r="4.6"/>`
  }).join('')
  const defs = `
    ${foil ? goldGradient(`${tag}-foil`, 'd') : ''}
    ${ink ? `<filter id="${tag}-ink" x="-5%" y="-5%" width="110%" height="110%">
      <feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="3" seed="11" result="blot"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.5" numOctaves="2" seed="4" result="grain"/>
      <feDisplacementMap in="SourceGraphic" in2="blot" scale="7" xChannelSelector="R" yChannelSelector="G" result="rough"/>
      <feColorMatrix in="grain" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.0 1.95" result="grainMask"/>
      <feComposite in="rough" in2="grainMask" operator="in" result="speckled"/>
      <feColorMatrix in="blot" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.1 1.5" result="blotMask"/>
      <feComposite in="speckled" in2="blotMask" operator="in"/>
    </filter>` : ''}`
  const centre = markMono(foil ? C.gold : color, `${tag}-m`)
  const body = `
  <g ${ink ? `filter="url(#${tag}-ink)" transform="rotate(-8 600 600)"` : ''} fill="${paint}" stroke="${paint}">
    <circle cx="600" cy="600" r="574" fill="none" stroke-width="22"/>
    <circle cx="600" cy="600" r="538" fill="none" stroke-width="7"/>
    <g stroke="none">${top}${bottom}${starAt(180 - gapMiddle)}${starAt(gapMiddle)}</g>
    <circle cx="600" cy="600" r="398" fill="none" stroke-width="10"/>
    <g stroke="none">${dots}</g>
    <g transform="translate(600 572) scale(0.5) translate(-512 -459)" stroke="none">${centre}</g>
    <text x="600" y="862" text-anchor="middle" font-family="Libre Baskerville" font-weight="700" font-size="64"
      letter-spacing="1" stroke="none">Kitobxon</text>
  </g>`
  return svgDoc(1200, 1200, body, { defs, fonts: FONTS.logo })
}

function sealAssets(add) {
  const sizes = { sizes: [4096, 1200, 600] }
  add('04_Pechat/kitobxon-pechat-kok-siyoh', 1200, 1200, seal(C.seal, { ink: true }), sizes)
  add('04_Pechat/kitobxon-pechat-kok', 1200, 1200, seal(C.seal), sizes)
  add('04_Pechat/kitobxon-pechat-navy', 1200, 1200, seal(C.navy), sizes)
  add('04_Pechat/kitobxon-pechat-oltin', 1200, 1200, seal(C.gold, { foil: true }), { ...sizes, preview: C.navy })
}

export { sealAssets as seal }
