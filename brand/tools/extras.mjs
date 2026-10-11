// After every asset is rendered: the brand board, the brand guide (PDF), the README, the zip for the
// owners, and the copies the apps use.
import { existsSync, readFileSync, readdirSync, rmSync, statSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'

import { C, HANDLE, SLOGANS } from './lib.mjs'
import { MENU_ICONS } from './iconset.mjs'
import { fontFaces } from './render.mjs'

const svg = (OUT, path) => readFileSync(join(OUT, 'SVG', `${path}.svg`))
const img = (OUT, path, style = '') => `<img style="${style}" src="data:image/svg+xml;base64,${svg(OUT, path).toString('base64')}">`

const PALETTE = [
  ['To‘q ko‘k (asosiy)', C.navy, '11, 31, 59'],
  ['Oltin', C.gold, '212, 175, 55'],
  ['Krem (sahifa)', C.cream, '248, 246, 242'],
  ['Kulrang', C.grey, '156, 163, 175'],
  ['Yashil', C.green, '14, 95, 70'],
]

const STYLE = `
  ${fontFaces()}
  * { box-sizing: border-box; }
  body { margin: 0; font-family: Montserrat; color: ${C.cream}; background: ${C.navy950}; }
  .tile { background: linear-gradient(160deg, ${C.navy700}, ${C.navy900}); border-radius: 36px; padding: 40px; position: relative; overflow: hidden;
    box-shadow: inset 0 0 0 2px rgba(212,175,55,.18); }
  .label { font-size: 26px; font-weight: 600; letter-spacing: 1px; color: ${C.grey}; text-align: center; margin-top: 18px; }
  h2 { font-family: 'Libre Baskerville'; font-weight: 700; font-size: 44px; margin: 0 0 24px; color: ${C.cream}; }
  .kicker { font-weight: 700; font-size: 22px; letter-spacing: 8px; color: ${C.gold}; text-transform: uppercase; }
  img { display: block; }
`

/** One big overview picture, like a designer's brand board (3840 × 2560). */
function board(OUT) {
  const icons = MENU_ICONS.slice(0, 10)
    .map(([file, , label]) => `<div style="text-align:center">${img(OUT, `06_Ikonkalar/menyu/${file}`, 'width:150px;margin:0 auto')}<div style="font-size:24px;margin-top:10px;color:${C.cream}">${label}</div></div>`)
    .join('')
  const swatches = PALETTE.map(
    ([name, hex]) => `<div style="text-align:center"><div style="width:150px;height:150px;border-radius:50%;background:${hex};margin:0 auto;box-shadow:0 0 0 4px rgba(212,175,55,.55)"></div>
      <div style="font-size:24px;margin-top:12px;font-weight:600">${hex}</div><div style="font-size:20px;color:${C.grey}">${name}</div></div>`,
  ).join('')
  const stickers = ['01-oqi', '02-har-bir-kitob-yangi-imkoniyat', '03-kitob-eng-yaxshi-dost', '04-bugun-ham-bir-sahifa', '06-orzular-kitoblarda', '07-barakalla']
    .map((s) => img(OUT, `10_Stikerlar/${s}`, 'width:100%;height:330px;object-fit:contain'))
    .join('')
  return `<!doctype html><html><head><meta charset="utf-8"><style>${STYLE}
    .grid { display: grid; gap: 40px; padding: 60px; width: 3840px; }
  </style></head><body><div class="grid" style="grid-template-columns: 1200px 1fr 1fr; grid-auto-rows: min-content">
    <div class="tile" style="grid-row: span 2; padding:0">${img(OUT, '01_Logotip/asosiy/kitobxon-logo-navy-card', 'width:1200px;height:1200px')}</div>
    <div class="tile" style="grid-column: span 2; display:flex; justify-content:space-around; align-items:center">
      <div>${img(OUT, '02_Avatar/telegram-bot-avatar', 'width:300px;border-radius:50%')}<div class="label">Bot avatari</div></div>
      <div>${img(OUT, '03_Ikonka_ilova/app-icon', 'width:300px')}<div class="label">Ilova ikonkasi</div></div>
      <div>${img(OUT, '02_Avatar/telegram-kanal-avatar', 'width:300px;border-radius:50%')}<div class="label">Kanal avatari</div></div>
      <div>${img(OUT, '02_Avatar/telegram-tolovlar-kanali-avatar', 'width:300px;border-radius:50%')}<div class="label">To‘lovlar kanali</div></div>
      <div>${img(OUT, '04_Pechat/kitobxon-pechat-oltin', 'width:300px')}<div class="label">Oltin pechat</div></div>
    </div>
    <div class="tile"><div class="kicker">Rang palitrasi</div><div style="display:flex;justify-content:space-between;margin-top:36px">${swatches}</div></div>
    <div class="tile"><div class="kicker">Shriftlar va shiorlar</div>
      <div style="font-family:'Libre Baskerville';font-weight:700;font-size:96px;margin-top:20px">Kitobxon</div>
      <div style="font-size:24px;color:${C.grey}">Libre Baskerville · Montserrat · Lora</div>
      <div style="margin-top:24px;font-size:30px;line-height:1.7">${SLOGANS.slice(0, 4).map((s) => `<span style="color:${C.gold}">✦</span> ${s}`).join('<br>')}</div>
    </div>
    <div class="tile" style="grid-column: span 3; display:grid; grid-template-columns: repeat(10, 1fr); gap: 20px">${icons}</div>
    <div class="tile" style="padding:0; grid-column: span 2">${img(OUT, '08_Banner/telegram-kanal-banner-16x9', 'width:100%')}</div>
    <div class="tile" style="display:flex;flex-direction:column;gap:22px;justify-content:center">
      ${['kitob-tavsiyalari', 'yangi-asarlar', 'maqsadlarim', 'hamjamiyat', 'bot-havolasi'].map((b) => img(OUT, `07_Tugmalar/tugma-${b}`, 'width:100%')).join('')}
    </div>
    <div class="tile" style="padding:30px; display:flex; gap:30px; justify-content:center; align-items:center; grid-column: span 2">
      ${img(OUT, '09_Postlar/story-status-9x16', 'height:1150px;border-radius:24px')}${img(OUT, '09_Postlar/motivatsiya-post-4x5', 'height:1150px;border-radius:24px')}${img(OUT, '09_Postlar/imkoniyatlar-kartasi-9x16', 'height:1150px;border-radius:24px')}
    </div>
    <div class="tile" style="display:grid;grid-template-columns:1fr 1fr;gap:20px;align-content:center;background:#E9EEF5">${stickers}</div>
  </div></body></html>`
}

/** The brand guide: six landscape pages (1920 × 1080). */
function guide(OUT) {
  const page = (title, kicker, body, n) => `<section class="page"><div class="kicker">${kicker}</div><h2>${title}</h2>${body}
    <footer><span>KITOBXON · BREND QO‘LLANMASI</span><span>${n} / 6</span></footer></section>`
  const card = (content, label, bg = '') => `<div class="card" style="${bg}">${content}<div class="label">${label}</div></div>`
  return `<!doctype html><html lang="uz"><head><meta charset="utf-8"><style>${STYLE}
    @page { size: 1920px 1080px; margin: 0; }
    .page { width: 1920px; height: 1080px; padding: 80px 100px; position: relative; overflow: hidden; page-break-after: always;
      background: radial-gradient(circle at 80% 10%, ${C.navy700}, ${C.navy950} 70%); }
    .cards { display: grid; gap: 28px; margin-top: 12px; }
    .card { background: rgba(255,255,255,.04); border-radius: 28px; padding: 28px; display:flex; flex-direction:column; align-items:center; justify-content:center;
      box-shadow: inset 0 0 0 2px rgba(212,175,55,.16); }
    p, li { font-size: 24px; line-height: 1.6; color: #DCE1EA; }
    footer { position: absolute; left: 100px; right: 100px; bottom: 40px; display: flex; justify-content: space-between; font-size: 18px; letter-spacing: 3px; color: ${C.grey}; }
    table { border-collapse: collapse; width: 100%; font-size: 22px; } td { padding: 12px 14px; border-bottom: 1px solid rgba(255,255,255,.08); vertical-align: top; }
    td:first-child { color: ${C.gold}; font-weight: 600; white-space: nowrap; }
  </style></head><body>
  ${page('Kitobxon', 'Brend qo‘llanmasi', `<div style="display:flex;gap:80px;align-items:center;margin-top:20px">
      ${img(OUT, '01_Logotip/asosiy/kitobxon-logo-dark-bg', 'width:640px')}
      <div><p style="font-size:30px">Ochiq kitob — <b>mutolaa</b>. O‘rtadagi pero uchi — <b>yozish va fikr</b>. Tepadagi yulduz — <b>yo‘l ko‘rsatuvchi nur</b>.</p>
      <p>To‘q ko‘k — ishonch va bilim, oltin — qadr va yutuq, krem — kitob sahifasi.</p>
      <p style="font-family:Lora;font-style:italic;font-size:40px;color:${C.gold}">«Yaxshi kitob — yaxshi kelajak»</p></div></div>`, 1)}
  ${page('Logotiplar', 'Variantlar', `<div class="cards" style="grid-template-columns: repeat(3, 1fr)">
      ${card(img(OUT, '01_Logotip/gorizontal/kitobxon-gorizontal-dark-bg', 'width:440px'), 'Gorizontal — to‘q fon')}
      ${card(img(OUT, '01_Logotip/gorizontal/kitobxon-gorizontal-light-bg', 'width:440px'), 'Gorizontal — och fon', 'background:#F8F6F2')}
      ${card(img(OUT, '01_Logotip/gorizontal/kitobxon-gorizontal-black', 'width:440px'), 'Bir rangli (chop etish)', 'background:#fff')}
      ${card(img(OUT, '01_Logotip/belgi/kitobxon-belgi-dark-bg', 'width:220px'), 'Belgi — to‘q fon')}
      ${card(img(OUT, '01_Logotip/belgi/kitobxon-belgi-light-bg', 'width:220px'), 'Belgi — och fon', 'background:#F8F6F2')}
      ${card(img(OUT, '01_Logotip/nishon/kitobxon-nishon-navy', 'width:220px'), 'Dumaloq nishon — kichik joylar')}
    </div>
    <p style="margin-top:28px">✓ Atrofida kamida belgi kengligining ¼ qismi bo‘sh joy qoldiring. Eng kichik o‘lcham: gorizontal logo — 160 px (30 mm), belgi — 32 px.<br>
    ✕ Logotipni cho‘zmang, aylantirmang, ranglarini o‘zgartirmang, soya qo‘shmang, chalkash fotosurat ustiga qo‘ymang.</p>`, 2)}
  ${page('Ranglar va shriftlar', 'Tizim', `<div class="cards" style="grid-template-columns: repeat(5, 1fr)">
      ${PALETTE.map(([name, hex, rgb]) => `<div class="card" style="align-items:flex-start"><div style="width:100%;height:170px;border-radius:20px;background:${hex};box-shadow:inset 0 0 0 2px rgba(255,255,255,.15)"></div>
        <div style="font-size:26px;font-weight:700;margin-top:16px">${name}</div><div style="font-size:22px;color:${C.grey}">HEX ${hex}<br>RGB ${rgb}</div></div>`).join('')}
    </div>
    <div class="cards" style="grid-template-columns: repeat(3, 1fr); margin-top: 32px">
      <div class="card" style="align-items:flex-start"><div style="font-family:'Libre Baskerville';font-weight:700;font-size:72px">Kitobxon</div><div class="label">Libre Baskerville — nom va sarlavhalar</div></div>
      <div class="card" style="align-items:flex-start"><div style="font-weight:700;font-size:56px;letter-spacing:8px;color:${C.gold}">BOT · 2026</div><div class="label">Montserrat — matn, tugma, raqam</div></div>
      <div class="card" style="align-items:flex-start"><div style="font-family:Lora;font-style:italic;font-weight:600;font-size:60px">Bir kitob — ming dunyo</div><div class="label">Lora Italic — iqtibos va shiorlar</div></div>
    </div>`, 3)}
  ${page('Avatar, pechat, watermark', 'Telegram va hujjatlar', `<div class="cards" style="grid-template-columns: repeat(4, 1fr)">
      ${card(img(OUT, '02_Avatar/telegram-bot-avatar', 'width:220px;border-radius:50%'), 'Bot')}
      ${card(img(OUT, '02_Avatar/telegram-kanal-avatar', 'width:220px;border-radius:50%'), 'Klub kanali')}
      ${card(img(OUT, '02_Avatar/telegram-tolovlar-kanali-avatar', 'width:220px;border-radius:50%'), 'To‘lovlar kanali')}
      ${card(img(OUT, '02_Avatar/telegram-adminlar-guruhi-avatar', 'width:220px;border-radius:50%'), 'Adminlar guruhi')}
      ${card(img(OUT, '04_Pechat/kitobxon-pechat-kok-siyoh', 'width:220px'), 'Pechat — sertifikat, xat', 'background:#fff')}
      ${card(img(OUT, '04_Pechat/kitobxon-pechat-oltin', 'width:220px'), 'Oltin pechat — to‘q dizayn')}
      ${card(img(OUT, '05_Watermark/watermark-belgi-oq', 'width:200px'), 'Watermark — oq', 'background:#555')}
      ${card(img(OUT, '05_Watermark/watermark-imzo-kulrang', 'width:300px'), 'Watermark — imzo', 'background:#fff')}
    </div><p style="margin-top:20px">Pechat — klubning o‘z belgisi (klub sertifikatlari va xatlari uchun), institutning rasmiy muhri emas. Watermarkni rasm ustiga 15–30% shaffoflikda qo‘ying.</p>`, 4)}
  ${page('Ikonkalar, tugmalar, stikerlar', 'Bot va kanal', `<div class="cards" style="grid-template-columns: repeat(10, 1fr); gap: 18px">
      ${MENU_ICONS.map(([file, , label]) => `<div style="text-align:center">${img(OUT, `06_Ikonkalar/menyu/${file}`, 'width:120px;margin:0 auto')}<div style="font-size:17px;margin-top:6px">${label}</div></div>`).join('')}
    </div>
    <div style="display:grid;grid-template-columns: 1fr 1fr;gap:28px;margin-top:28px">
      <div style="display:flex;flex-direction:column;gap:14px">${['kitob-tavsiyalari', 'yangi-asarlar', 'maqsadlarim', 'hamjamiyat'].map((b) => img(OUT, `07_Tugmalar/tugma-${b}`, 'width:640px')).join('')}</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;background:#E9EEF5;border-radius:28px;padding:16px">${['01-oqi', '02-har-bir-kitob-yangi-imkoniyat', '03-kitob-eng-yaxshi-dost', '04-bugun-ham-bir-sahifa', '05-oqish-eng-katta-sarmoya', '06-orzular-kitoblarda', '07-barakalla', '08-xush-kelibsiz'].map((s) => img(OUT, `10_Stikerlar/${s}`, 'width:170px;height:170px;object-fit:contain')).join('')}</div>
    </div>`, 5)}
  ${page('Qayerda nima ishlatiladi', 'Tez qo‘llanma', `<table>
      <tr><td>Bot rasmi</td><td>02_Avatar/telegram-bot-avatar-640px.png — @BotFather → Edit Botpic (yoki admin panel → Sozlamalar → Bot profili → «Klub avatarini o‘rnatish»)</td></tr>
      <tr><td>Bot tavsif rasmi</td><td>08_Banner/bot-tavsif-rasmi-640px.png — @BotFather → Edit Description Picture</td></tr>
      <tr><td>Klub kanali</td><td>Avatar: 02_Avatar/telegram-kanal-avatar-640px.png · Banner/post: 08_Banner, 09_Postlar</td></tr>
      <tr><td>To‘lovlar kanali</td><td>02_Avatar/telegram-tolovlar-kanali-avatar-640px.png</td></tr>
      <tr><td>Stikerlar</td><td>10_Stikerlar/*-512px.png — @Stickers botiga /newpack → har birini yuboring → emoji tanlang</td></tr>
      <tr><td>Sertifikat</td><td>Pechat va belgi tizimga qo‘yilgan — sertifikatlarda o‘zi chiqadi</td></tr>
      <tr><td>Sayt, ilova</td><td>03_Ikonka_ilova (favicon, ikonka), 08_Banner/havola-rasmi-og (havola rasmi)</td></tr>
      <tr><td>Bosma, chop etish</td><td>SVG papkasidagi vektor fayllar yoki 4096 px PNG; bir rangli — *-black / *-white</td></tr>
      <tr><td>Bot manzili</td><td>${HANDLE}</td></tr>
    </table>`, 6)}
  </body></html>`
}

const README = `KITOBXON — BREND TO‘PLAMI (4K)
================================

01_Logotip      Asosiy (vertikal), gorizontal, belgi, dumaloq nishon — to‘q fon, och fon, oq, qora, oltin.
                4096px — eng yuqori sifat (bosma, katta ekran); 1024/512px — tayyor kichik nusxalar.
02_Avatar       Telegram avatarlari: bot, klub kanali, to‘lovlar kanali, adminlar guruhi (640px — Telegram uchun tayyor).
03_Ikonka_ilova Ilova ikonkasi va favicon (16–4096px), maskable ikonka.
04_Pechat       Klub pechati: ko‘k siyoh (haqiqiy muhr ko‘rinishi), ko‘k, to‘q ko‘k, oltin.
05_Watermark    Belgi (kulrang, oq, qora), imzo (belgi + nom), takrorlanuvchi naqsh.
06_Ikonkalar    20 ta menyu ikonkasi va ijtimoiy tarmoq ikonkalari (Telegram, Instagram, YouTube, TikTok, sayt).
07_Tugmalar     Tugma namunalari (oltin, ko‘k, yashil, krem).
08_Banner       Telegram kanal banneri (3840×2160), keng banner (3:1), havola rasmi (OG), bot tavsif rasmi (640×360).
09_Postlar      Story/status (9:16), motivatsiya posti (4:5), iqtibos posti (1:1), imkoniyatlar kartasi (9:16).
10_Stikerlar    8 ta stiker — 512px (Telegram stikerlari uchun tayyor) va 2048px.
SVG             Hamma narsaning vektor manbasi (cheksiz kattalashtirsa bo‘ladi).
Kitobxon-brend-doskasi.jpg   Hammasi bitta rasmda.
Kitobxon-brend-qollanma.pdf  Qoidalar: ranglar, shriftlar, qayerda nima ishlatiladi.

Ranglar: to‘q ko‘k #0B1F3B · oltin #D4AF37 · krem #F8F6F2 · kulrang #9CA3AF · yashil #0E5F46
Shriftlar: Libre Baskerville (nom), Montserrat (matn), Lora Italic (iqtiboslar) — bepul (SIL Open Font License).

Telegram'da o‘rnatish:
• Bot rasmi: admin panel → Sozlamalar → 🤖 Bot profili → «Klub avatarini o‘rnatish» (yoki @BotFather → Edit Botpic).
• Bot tavsif rasmi: @BotFather → /mybots → bot → Edit Bot → Edit Description Picture → 08_Banner/bot-tavsif-rasmi-640px.png.
• Kanal avatari: kanal → tahrirlash → rasm → 02_Avatar/...-640px.png.
• Stiker to‘plami: @Stickers → /newpack → nom → 10_Stikerlar/*-512px.png fayllarini «fayl» sifatida yuboring → har biriga emoji.

Pechat — klubning o‘z belgisi (klub sertifikatlari va xatlari uchun), institutning rasmiy muhri emas.
Bot manzili rasmlarda: ${HANDLE} — boshqa bo‘lsa, brand/tools/lib.mjs dagi HANDLE ni o‘zgartirib, qayta yasang.
`

function folderSize(dir) {
  let total = 0
  for (const name of readdirSync(dir)) {
    const path = join(dir, name)
    total += statSync(path).isDirectory() ? folderSize(path) : statSync(path).size
  }
  return total
}

export async function finish({ OUT, ROOT, copyFileSync, execFileSync, writeFileSync, mkdirSync, htmlTo }) {
  writeFileSync(join(OUT, 'Kitobxon-brend-doskasi.jpg'), await htmlTo(board(OUT), { width: 3840, height: 2560, jpeg: true }))
  writeFileSync(join(OUT, 'Kitobxon-brend-qollanma.pdf'), await htmlTo(guide(OUT), { width: 1920, height: 1080, pdf: true }))
  writeFileSync(join(OUT, 'OQING.txt'), README)
  console.log('✓ board, guide, readme')

  // The copies the apps use.
  const copy = (from, to) => {
    mkdirSync(dirname(to), { recursive: true })
    copyFileSync(join(OUT, from), to)
  }
  const backend = join(ROOT, 'backend', 'app', 'brand')
  copy('01_Logotip/belgi/kitobxon-belgi-light-bg-1024px.png', join(backend, 'logo-mark.png'))
  copy('01_Logotip/belgi/kitobxon-belgi-dark-bg-1024px.png', join(backend, 'logo-mark-dark.png'))
  copy('01_Logotip/gorizontal/kitobxon-gorizontal-light-bg-1600px.png', join(backend, 'logo-horizontal.png'))
  copy('04_Pechat/kitobxon-pechat-kok-siyoh-600px.png', join(backend, 'seal.png'))
  copy('04_Pechat/kitobxon-pechat-oltin-600px.png', join(backend, 'seal-light.png'))
  copy('02_Avatar/telegram-bot-avatar-640px.png', join(backend, 'bot-avatar.png'))
  copy('01_Logotip/nishon/kitobxon-nishon-navy-512px.png', join(backend, 'logo-badge.png'))
  for (const app of ['miniapp', 'admin']) {
    const pub = join(ROOT, app, 'public')
    copy('03_Ikonka_ilova/app-icon-32px.png', join(pub, 'favicon-32.png'))
    copy('03_Ikonka_ilova/app-icon-16px.png', join(pub, 'favicon-16.png'))
    copy('03_Ikonka_ilova/app-icon-180px.png', join(pub, 'apple-touch-icon.png'))
    copy('03_Ikonka_ilova/app-icon-192px.png', join(pub, 'icon-192.png'))
    copy('03_Ikonka_ilova/app-icon-512px.png', join(pub, 'icon-512.png'))
    copy('01_Logotip/nishon/kitobxon-nishon-navy-512px.png', join(pub, 'brand', 'logo-badge.png'))
    copy('02_Avatar/telegram-bot-avatar-640px.png', join(pub, 'brand', 'bot-avatar.png'))
  }
  console.log('✓ copies for the apps')

  // Lossless squeeze of every PNG (Chromium writes them fast, not small).
  execFileSync(join(ROOT, 'backend', '.venv', 'bin', 'python'), ['-I', join(dirname(new URL(import.meta.url).pathname), 'squeeze.py'), OUT], { stdio: 'inherit' })

  // The zip for the owners (the contact sheet stays out).
  const zip = join(ROOT, 'brand', 'Kitobxon-Brend-4K.zip')
  rmSync(zip, { force: true })
  execFileSync('zip', ['-q', '-r', '-X', '-9', zip, '.'], { cwd: OUT })
  console.log(`✓ ${relative(ROOT, zip)} (${(statSync(zip).size / 1e6).toFixed(1)} MB; kit ${(folderSize(OUT) / 1e6).toFixed(1)} MB)`)
  void existsSync
}
