# Kitobxon Hub'ni institut serveriga ko'chirish

Bu qo'llanma institutning IT mutaxassisi va klub rahbari uchun. Unda Render'dagi ishlab turgan
tizimni institutning o'z serveriga **ma'lumotlarni yo'qotmasdan** ko'chirish va keyin yillar
davomida dasturchisiz ishlatish yozilgan. Ko'chirish taxminan 1–2 soat oladi.

> ⚠️ Ko'chirishdan keyin kodga o'zgartirish kiritish rejalashtirilmagan. Shuning uchun quyidagi
> hamma narsa avtomatik: yangi o'quv yili, eski yozuvlarni tozalash, faol bo'lmagan a'zolar,
> zaxira nusxa. Sizdan faqat server yoqiq turishi va oyda bir marta tekshirish talab qilinadi.

---

## 1. Serverga talablar

| Nima | Talab |
|---|---|
| Server | Linux (Ubuntu 22.04/24.04), **2 protsessor yadrosi, 4 GB xotira, 40 GB disk** (5 000 a'zogacha) |
| Dastur | Docker va Docker Compose (`curl -fsSL https://get.docker.com \| sh`) |
| Internet | Server **internetdan ochiq** bo'lishi kerak: 80 va 443 portlar |
| Domen | Masalan `kitobxon.fjsti.uz` — server IP manziliga yo'naltirilgan (DNS'da **A** yozuv) |

Nega internetdan ochiq bo'lishi shart: Telegram botga xabarlarni va a'zolarning telefonidagi ilova
(Mini App) serverga **faqat HTTPS orqali, internetdan** keladi. HTTPS sertifikatini tizim o'zi
oladi va yangilab turadi (Let's Encrypt, bepul).

> 💡 Institut tarmog'ida tashqi IP berib bo'lmasa: **Cloudflare Tunnel** (bepul) — serverga
> `cloudflared` o'rnatiladi va domen tunnel orqali ulanadi; portlarni ochish shart bo'lmaydi.
> Bunda Caddy o'rniga tunnel `http://localhost:80` ga yo'naltiriladi.

### Qancha a'zoni ko'taradi

Yuklama sinovi (3 000 a'zo, uch yillik ball tarixi — 450 000 yozuv, bir vaqtda 100 kishi
ilovani ochmoqda): bitta jarayon soniyasiga ~120 so'rovga javob beradi, bitta so'rov o'rtacha
15–20 ms. Ilovani ochish ~6 so'rov, demak bir daqiqada **1 000 dan ortiq a'zo** bir vaqtda
ochishi mumkin. Juda katta klub uchun `.env` da `WEB_CONCURRENCY=2` qiling.

---

## 2. O'rnatish

```bash
# 1) kodni yuklab olish
sudo mkdir -p /srv && cd /srv
sudo git clone https://github.com/Akmaljon1403/kitobxon-hub.git
cd kitobxon-hub/infra/institute

# 2) sozlamalar fayli
sudo cp env.example .env
sudo nano .env
```

`.env` faylida to'ldiring:

| Qator | Nima yoziladi |
|---|---|
| `DOMAIN` | `kitobxon.fjsti.uz` (sizning domeningiz, `https://` siz) |
| `PUBLIC_BASE_URL` | `https://kitobxon.fjsti.uz` |
| `POSTGRES_PASSWORD` | `openssl rand -hex 24` buyrug'i chiqargan qator |
| `SECRET_KEY`, `BOT_TOKEN`, `BOT_USERNAME`, `SUPER_ADMIN_TELEGRAM_IDS` | **Render → Environment** dan aynan nusxalang |
| `STORAGE_*` | Render'da R2 ishlatilgan bo'lsa — o'sha qiymatlar (fayllarni ko'chirish shart emas). Aks holda `STORAGE_BACKEND=local` |

> ❗ `SECRET_KEY` ni **o'zgartirmang** — u bilan sovg'a promokodlari shifrlangan. Boshqa kalit
> qo'yilsa, saqlangan promokodlarni o'qib bo'lmaydi.

```bash
# 3) fayllar uchun papka (ilova 10001 raqamli foydalanuvchi nomidan yozadi)
sudo mkdir -p data/storage && sudo chown 10001 data/storage
sudo chmod 600 .env
```

---

## 3. Ma'lumotlarni Render'dan ko'chirish

1. **Render'ni to'xtating**: Render → xizmat → **Settings** → **Suspend Web Service**. (Ikkita server
   bir vaqtda ishlasa, bot xabarlari ikkiga bo'linadi.)
2. **Eng yangi zaxira nusxani oling**: GitHub → repozitoriy → **Actions** → **Database backup** →
   **Run workflow** → tugagach, run ichidagi **Artifacts** dan faylni yuklab oling
   (`kitobxon-....dump.gpg`). Uni serverga ko'chiring (masalan `scp`).
3. Bazani ishga tushirib, nusxani tiklang:

   ```bash
   cd /srv/kitobxon-hub/infra/institute
   sudo docker compose up -d db
   # zaxira paroli — GitHub'dagi BACKUP_PASSPHRASE (yozganda ekranda ko'rinmaydi)
   read -rs -p "Zaxira paroli: " PASS; echo
   gpg --batch --quiet --pinentry-mode loopback --passphrase "$PASS" -d kitobxon-XXXX.dump.gpg > /tmp/kitobxon.dump
   sudo docker compose exec -T db pg_restore -U kitobxon -d kitobxon --no-owner --no-privileges < /tmp/kitobxon.dump
   rm /tmp/kitobxon.dump
   ```

4. **Hammasini ishga tushiring**:

   ```bash
   sudo docker compose up -d --build     # birinchi marta 5–10 daqiqa
   sudo docker compose ps                # app — healthy, caddy — running
   curl -fsS https://kitobxon.fjsti.uz/health
   ```

   Ilova ishga tushganda o'zi: bazani yangi versiyaga moslaydi, Telegram'ga yangi manzilni
   (webhook) va menyu tugmasini ro'yxatdan o'tkazadi.

5. Agar @BotFather'da Mini App manzili qo'lda kiritilgan bo'lsa (`/mybots → Bot Settings →
   Configure Mini App`), uni `https://kitobxon.fjsti.uz/app/` ga almashtiring.
6. **Tekshirish**: admin panel (`https://kitobxon.fjsti.uz/admin/`) → **Sozlamalar → 🩺 Tizim
   holati** — hammasi ✅ bo'lsin. Botga `/start` yozing, ilovani oching, reytingni ko'ring.
7. Bir hafta muammosiz ishlagach, Render xizmatini va Neon bazasini o'chirishingiz mumkin.
   **Neon'ni o'chirishdan oldin** 4-bo'limdagi zaxira bir marta muvaffaqiyatli ishlaganiga ishonch
   hosil qiling.

---

## 4. Har kungi zaxira nusxa (majburiy)

```bash
# parol — uzun tasodifiy qator; uni qog'ozga yozib, seyfda saqlang
sudo sh -c 'openssl rand -hex 32 > /root/.kitobxon-backup-pass && chmod 600 /root/.kitobxon-backup-pass'
# sinab ko'rish
sudo /srv/kitobxon-hub/infra/institute/backup.sh
# har kecha 02:30 da
echo '30 2 * * * root /srv/kitobxon-hub/infra/institute/backup.sh >> /var/log/kitobxon-backup.log 2>&1' | sudo tee /etc/cron.d/kitobxon-backup
```

Skript bazani va yuklangan fayllarni shifrlaydi, nusxa ochilishini tekshiradi va 14 kundan
eskilarini o'chiradi (`/srv/kitobxon-backups`). **Nusxalarni boshqa joyga ham ko'chiring**
(institutning boshqa serveri yoki tashqi disk) — server diski buzilsa, faqat shular qoladi.

Tiklash (yangi serverda yoki xato bo'lganda):

```bash
sudo gpg --batch --quiet --pinentry-mode loopback --passphrase-file /root/.kitobxon-backup-pass \
  -d kitobxon-YYYY-MM-DD-HHMM.dump.gpg > /tmp/k.dump
sudo docker compose stop app
sudo docker compose exec -T db pg_restore -U kitobxon -d kitobxon --clean --if-exists --no-owner < /tmp/k.dump
sudo gpg --batch --quiet --pinentry-mode loopback --passphrase-file /root/.kitobxon-backup-pass \
  -d kitobxon-files-YYYY-MM-DD-HHMM.tar.gpg | sudo tar -C data -xf -
sudo docker compose start app
```

Semestrda bir marta tiklashni sinab ko'ring (alohida kompyuterda).

---

## 5. Kuzatish

* **UptimeRobot** (bepul): `https://kitobxon.fjsti.uz/health` va `.../health/db` ni har 5
  daqiqada tekshirsin, ishlamay qolsa e-pochta/Telegram'ga xabar bersin.
* **Admin panel → Tizim holati**: oyda bir marta qarang (disk hajmi, xabarlar navbati, bot).
* Jurnal: `sudo docker compose logs --tail 200 app`.
* Disk: `df -h` — 80% dan oshsa, eski zaxira nusxalarni boshqa joyga olib, o'chiring.

Server qayta yoqilganda hammasi o'zi ishga tushadi (`restart: unless-stopped`).

---

## 6. O'zi bajariladigan ishlar (aralashish shart emas)

| Qachon | Nima bo'ladi |
|---|---|
| Har daqiqa | Xabarlar, eslatmalar, testlarni yopish, kanal postlari |
| Har kuni 04:00 | Eski yetkazilgan xabarlar (120 kun), test signallari (400 kun), eski bot suhbat holatlari tozalanadi. Audit jurnali **hech qachon** o'chmaydi |
| Har kuni 11:00 | Uzoq vaqt (sozlamada 365 kun) kirmagan a'zolarga eslatma; bir haftadan keyin «faol emas» (qaytsa — o'zi faollashadi) |
| Har yili 1-sentabr | Kurslar bittaga oshadi (oxirgi kursdagilar o'zgarmaydi), «2027–2028 o'quv yili» mavsumi boshlanadi — reyting va hisobotlar yillar bo'yicha aralashmaydi |

Bularni **Admin panel → Sozlamalar** da o'zgartirish mumkin: `academic.*` (o'quv yili boshlanish
kuni, kurslarni oshirish, mavsum), `membership.inactive_days` (0 — o'chirish).

---

## 7. Yangilash (agar kelajakda kerak bo'lsa)

```bash
cd /srv/kitobxon-hub && sudo git pull
cd infra/institute && sudo ./backup.sh && sudo docker compose up -d --build
```

## 8. Muammo bo'lsa

| Belgi | Sabab va yechim |
|---|---|
| Bot javob bermaydi | `docker compose ps` — app ishlayaptimi? Tizim holatida «Telegram webhook» xatosini o'qing. Domen va HTTPS ishlashini `curl https://DOMEN/health` bilan tekshiring |
| Ilova ochilmaydi, «Ulanib bo'lmadi» | HTTPS sertifikati: `docker compose logs caddy`. 80/443 portlar ochiq va DNS to'g'ri bo'lishi kerak |
| «Ma'lumotlar bazasiga ulanib bo'lmadi» | `docker compose ps db`; `.env` dagi `POSTGRES_PASSWORD` baza yaratilgandagi bilan bir xil bo'lsin |
| Disk to'ldi | Eski zaxiralarni ko'chiring/o'chiring; `docker system prune` (ishlamayotgan eski obrazlar) |
