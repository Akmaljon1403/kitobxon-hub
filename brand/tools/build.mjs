// Kitobxon brand kit: every logo, avatar, seal, watermark, icon, banner, post and sticker is drawn
// in code and rendered in 4K, so the whole identity can be re-made with one command:
//
//     node brand/tools/build.mjs            (everything)
//     node brand/tools/build.mjs logo seal  (only assets whose path contains one of the words)
//
// Output: brand/out/ (PNG in folders + SVG sources + a contact sheet), brand/Kitobxon-Brend.zip,
// and the copies the apps use (backend/app/brand, miniapp/public, admin/public).

import { execFileSync } from 'node:child_process'
import { copyFileSync, existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { done, fitSvg, htmlTo, svgToPng } from './render.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const ROOT = join(here, '..', '..')
const OUT = join(ROOT, 'brand', 'out')
const only = process.argv.slice(2)

const assets = []
/** Register an asset: `path` without extension, the SVG and its own size, and the PNG widths. */
const add = (path, w, h, svg, options = {}) => {
  if (only.length && !only.some((word) => path.includes(word))) return
  assets.push({ path, w, h, svg, sizes: options.sizes ?? [w], ...options })
}

const modules = ['logos', 'avatars', 'seal', 'watermarks', 'iconset', 'social', 'stickers']
for (const name of modules) {
  const file = join(here, `${name}.mjs`)
  if (!existsSync(file)) continue
  const module = await import(file)
  module[name](add)
}

if (!only.length) rmSync(OUT, { recursive: true, force: true })
mkdirSync(OUT, { recursive: true })
const rendered = []
for (const asset of assets) {
  if (asset.fit !== undefined) {
    const fitted = await fitSvg(asset.svg, asset.fit)
    asset.svg = fitted.svg
    asset.w = fitted.w
    asset.h = fitted.h
  }
  const svgFile = join(OUT, 'SVG', `${asset.path}.svg`)
  mkdirSync(dirname(svgFile), { recursive: true })
  writeFileSync(svgFile, asset.svg)
  for (const width of asset.sizes) {
    const height = Math.round((width * asset.h) / asset.w)
    const suffix = asset.sizes.length > 1 ? `-${width}px` : ''
    // Opaque pictures in 4K are stored as high-quality JPEG (a PNG of a painted scene is 5–10× larger).
    const jpeg = asset.opaque && Math.max(width, height) >= 2000
    const file = join(OUT, `${asset.path}${suffix}.${jpeg ? 'jpg' : 'png'}`)
    mkdirSync(dirname(file), { recursive: true })
    writeFileSync(file, await svgToPng(asset.svg, width, height, { background: asset.background ?? null, jpeg }))
    rendered.push({ file, asset, width })
  }
  console.log('✓', asset.path)
}

// A contact sheet to look at everything at once (not part of the kit).
const thumbs = assets
  .map((asset) => {
    const data = Buffer.from(asset.svg).toString('base64')
    return `<figure style="background:${asset.preview ?? '#fff'}"><img src="data:image/svg+xml;base64,${data}"><figcaption>${asset.path}</figcaption></figure>`
  })
  .join('')
const sheet = `<!doctype html><html><body style="margin:0;padding:16px;background:#ddd;font:12px sans-serif;display:flex;flex-wrap:wrap;gap:12px">
  <style>figure{margin:0;width:300px;height:300px;display:flex;flex-direction:column;align-items:center;justify-content:center;border-radius:8px;overflow:hidden}
  img{max-width:280px;max-height:250px}figcaption{margin-top:6px;color:#888;font-size:10px}</style>${thumbs}</body></html>`
writeFileSync(join(OUT, '..', 'contact-sheet.png'), await htmlTo(sheet, { width: 1600, height: 900 }))

const extras = await import(join(here, 'extras.mjs')).catch(() => null)
if (extras && !only.length) await extras.finish({ OUT, ROOT, rendered, copyFileSync, execFileSync, writeFileSync, mkdirSync, svgToPng, htmlTo })
await done()
