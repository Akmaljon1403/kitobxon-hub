# Kitobxon — brend to'plami

Hamma logotip, avatar, pechat, watermark, ikonka, tugma, banner, post va stikerlar **koddan**
yasaladi (vektor, 4K), shuning uchun istalgan vaqtda bir buyruq bilan qayta yaratish mumkin:

```bash
cd e2e && npm ci        # bir marta: Playwright (Chromium) kerak
node brand/tools/build.mjs            # hammasi (≈7 daqiqa)
node brand/tools/build.mjs Pechat     # faqat yo'lida «Pechat» bo'lganlar
```

Natija:

- `brand/out/` — tayyor to'plam (PNG/JPG papkalarda, `SVG/`, brend doskasi, PDF qo'llanma, `OQING.txt`);
- `brand/Kitobxon-Brend-4K.zip` — egalariga beriladigan arxiv;
- ilovalar ishlatadigan nusxalar: `backend/app/brand/` (sertifikat pechati va belgisi, bot avatari),
  `miniapp/public/`, `admin/public/` (favicon, ikonka, logotip).

`out/` va zip gitga qo'shilmaydi (katta) — ular har safar shu skriptdan chiqadi.

| Fayl | Nima |
|---|---|
| `tools/mark.mjs` | Belgi geometriyasi (ochiq kitob + pero uchi + yulduz) va ranglar |
| `tools/lib.mjs` | Nom, «— BOT —», shior, bot manzili (`HANDLE`), umumiy yordamchilar |
| `tools/logos.mjs`, `avatars.mjs`, `seal.mjs`, `watermarks.mjs` | Logotip, avatar, pechat, watermark |
| `tools/iconset.mjs`, `social.mjs`, `scenes.mjs`, `stickers.mjs` | Ikonkalar va tugmalar, banner/postlar, sahnalar, stikerlar |
| `tools/extras.mjs` | Brend doskasi, PDF qo'llanma, zip va ilovalarga nusxalash |
| `fonts/` | Libre Baskerville, Montserrat, Lora, Nunito — SIL Open Font License |
| `tools/icondata.mjs` | Lucide (ISC) va Simple Icons (CC0) ikonka chiziqlari |

Ranglar: to'q ko'k `#0B1F3B`, oltin `#D4AF37`, krem `#F8F6F2`, kulrang `#9CA3AF`, yashil `#0E5F46`.
