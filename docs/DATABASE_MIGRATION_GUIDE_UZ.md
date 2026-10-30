# Ma'lumotlar bazasi migratsiyalari qo'llanmasi

Baza sxemasi (jadvallar, ustunlar) **Alembic** migratsiyalari bilan boshqariladi.
Har bir o'zgarish — `backend/migrations/versions/` papkasidagi raqamli fayl
(`0001`, `0002`, … `0031`). Bu usul baza o'zgarishini xavfsiz, qaytariladigan va
har bir serverда bir xil qiladi.

> Oddiy holatda hech narsa qilish shart emas: ilova har ishga tushganda
> (`start.sh`) baza avtomatik eng so'nggi holatga keltiriladi (`alembic upgrade head`).

---

## 1. Kundalik amallar

Barcha buyruqlar `backend/` papkasida bajariladi (`DATABASE_URL` o'rnatilgan holda):

```bash
alembic upgrade head      # bazani eng so'nggi holatga keltirish
alembic current           # baza hozir qaysi migratsiyada ekanini ko'rish
alembic history           # barcha migratsiyalar ro'yxati
alembic downgrade -1      # oxirgi migratsiyani bitta ortga qaytarish (ehtiyotkorlik bilan)
```

Ishlab chiqarishда `upgrade head` deployning bir qismi — qo'lda qilish shart emas.

---

## 2. Yangi migratsiya yozish (dasturchi uchun)

1. Modelni (`backend/app/models/…`) o'zgartiring.
2. Qoralama yarating:

   ```bash
   alembic revision --autogenerate -m "qisqa izoh"
   ```

3. Yaratilgan faylni **albatta o'qib chiqing** — autogenerate hamma narsani
   to'g'ri topmaydi. Fayl boshida `revision` va `down_revision` (oldingi raqam)
   to'g'ri ekanini tekshiring.
4. `upgrade()` va `downgrade()` ikkalasi ham to'liq bo'lsin (orqaga qaytarish ham
   ishlashi kerak).
5. Sinang: `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head`.

---

## 3. Muhim qoidalar (xavfsizlik)

- **Ma'lumotni yo'qotmang.** Jadval yoki ustunni o'chirishdan oldin, u endi hech
  qayerda ishlatilmasligiga ishonch hosil qiling. Tarix (ballar, hisobotlar,
  davomat) saqlanib qolishi kerak.
- **Migratsiya qaytariladigan bo'lsin.** `downgrade()` ham to'g'ri yozilsin.
- **Enum qiymatlari — VARCHAR + CHECK.** Loyihada enumlar PostgreSQL native enum
  emas, balki matn (`VARCHAR`) + `CHECK` cheklov sifatida saqlanadi (`enum_column`).
  Yangi enum qiymati qo'shilганда CHECK cheklovini kengaytirish kerak — bu **xom
  SQL** bilan qilinadi, chunki `op.drop_constraint` nom konvensiyasini qayta
  qo'llab, nomni buzadi. Namuna: `0029`, `0030` migratsiyalari:

  ```python
  op.execute("ALTER TABLE jadval DROP CONSTRAINT ck_jadval_enumnomi")
  op.execute("ALTER TABLE jadval ADD CONSTRAINT ck_jadval_enumnomi "
             "CHECK (ustun IN ('ESKI', 'YANGI'))")
  ```

  Cheklov nomi `ck_<jadval>_<enumnomi>` ko'rinishida (konvensiya
  `backend/app/models/base.py` da).
- **Katta jadvalда ehtiyot bo'ling.** Ko'p satrli jadvalга ustun qo'shganda
  `server_default` bering yoki bosqichma-bosqich qiling.

---

## 4. Muammo bo'lsa

- Deploy `alembic upgrade head` da to'xtasa — odatda `DATABASE_URL` noto'g'ri
  (parol yo'q yoki oxiri kesilgan) yoki baza mavjud emas. Xato matnini tekshiring.
- Ikki dasturchi bir vaqtда migratsiya yozsa, `down_revision` to'qnashishi mumkin
  («multiple heads»). `alembic heads` bilan ko'ring, kerak bo'lsa `alembic merge`.
- Bazani eski holatга qaytarish kerak bo'lsa — bu migratsiya emas, **tiklash**:
  [`BACKUP_RESTORE_GUIDE_UZ.md`](BACKUP_RESTORE_GUIDE_UZ.md).

**Bog'liq:** [`DATABASE.md`](DATABASE.md) (sxema tafsiloti),
[`DEPLOYMENT_GUIDE_UZ.md`](DEPLOYMENT_GUIDE_UZ.md).
