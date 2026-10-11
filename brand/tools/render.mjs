// Renders SVG/HTML to PNG/PDF with the bundled fonts, using the repository's Playwright Chromium.
import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const require = createRequire(join(here, '..', '..', 'e2e', 'package.json'))
const { chromium } = require('playwright')

export const FONTS = join(here, '..', 'fonts')
const FAMILIES = {
  lora: 'Lora',
  'libre-baskerville': 'Libre Baskerville',
  merriweather: 'Merriweather',
  'dm-serif-display': 'DM Serif Display',
  montserrat: 'Montserrat',
  nunito: 'Nunito',
}

// Every font file in brand/fonts: «<family>-latin-<weight>-<style>.woff».
const FACES = readdirSync(FONTS)
  .map((file) => file.match(/^(.+)-latin-(\d+)-(normal|italic)\.woff$/))
  .filter(Boolean)
  .map(([file, slug, weight, style]) => [FAMILIES[slug] ?? slug, Number(weight), style, file])

/** @font-face rules with the fonts inlined, so an SVG file carries its own letters.
 * `only` lists the faces an asset uses, e.g. ['Lora 700', 'Montserrat 600'] (all when null). */
export function fontFaces(only = null) {
  const key = (family, weight, style) => `${family} ${weight}${style === 'italic' ? ' italic' : ''}`
  return FACES.filter(([family, weight, style]) => !only || only.includes(key(family, weight, style)))
    .map(([family, weight, style, file]) => {
      const data = readFileSync(join(FONTS, file)).toString('base64')
      return `@font-face{font-family:'${family}';font-weight:${weight};font-style:${style};src:url(data:font/woff;base64,${data}) format('woff');}`
    })
    .join('\n')
}

let browser = null
async function page(scale = 1) {
  browser ??= await chromium.launch()
  const context = await browser.newContext({ deviceScaleFactor: scale })
  return context.newPage()
}

/** PNG (or JPEG) bytes of an SVG document rendered at width × height pixels (transparent where empty). */
export async function svgToPng(svg, width, height, { background = null, jpeg = false } = {}) {
  const p = await page()
  await p.setViewportSize({ width, height })
  const html = `<!doctype html><html><head><style>html,body{margin:0;padding:0;background:${background ?? 'transparent'}}
  svg{display:block;width:${width}px;height:${height}px}</style></head><body>${svg}</body></html>`
  await p.setContent(html)
  await p.evaluate(() => document.fonts.ready)
  const png = await p.screenshot(
    jpeg ? { type: 'jpeg', quality: 93 } : { omitBackground: background === null, type: 'png' },
  )
  await p.context().close()
  return png
}

/** The SVG with its viewBox tightened to the drawing plus `pad` units on every side. */
export async function fitSvg(svg, pad) {
  const p = await page()
  await p.setContent(`<!doctype html><html><body style="margin:0">${svg}</body></html>`)
  await p.evaluate(() => document.fonts.ready)
  const box = await p.evaluate(() => {
    const b = document.querySelector('svg').getBBox()
    return { x: b.x, y: b.y, w: b.width, h: b.height }
  })
  await p.context().close()
  const x = Math.floor(box.x - pad)
  const y = Math.floor(box.y - pad)
  const w = Math.ceil(box.w + pad * 2)
  const h = Math.ceil(box.h + pad * 2)
  return {
    svg: svg.replace(/viewBox="[^"]*" width="[^"]*" height="[^"]*"/, `viewBox="${x} ${y} ${w} ${h}" width="${w}" height="${h}"`),
    w,
    h,
  }
}

/** A full HTML page as PNG (`scale` multiplies the pixels) or as PDF. */
export async function htmlTo(html, { width, height, pdf = false, scale = 1, jpeg = false }) {
  const p = await page(scale)
  await p.setViewportSize({ width, height })
  await p.setContent(html)
  await p.evaluate(() => document.fonts.ready)
  const out = pdf
    ? await p.pdf({ width: `${width}px`, height: `${height}px`, printBackground: true })
    : await p.screenshot(jpeg ? { type: 'jpeg', quality: 93, fullPage: true } : { type: 'png', fullPage: true })
  await p.context().close()
  return out
}

export async function done() {
  await browser?.close()
}
