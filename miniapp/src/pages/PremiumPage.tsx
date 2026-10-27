import { useCallback, useState } from 'react'

import { CardCheckout, CardNumber, MyCardPayments, formatUzs } from '../components/CardPayment'
import { ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { PremiumPlan, PremiumStatus } from '../types/api'
import { formatDate } from '../utils/format'
import { navigate } from '../utils/router'
import { getWebApp, haptic } from '../utils/telegram'

const FREE_FOR_ALL = ['📚 Kitoblar va iqtiboslar', '📅 Tadbirlar va davomat', '📝 Testlar va natijalar', '🏆 Reyting va yutuqlar', '🪪 Kitobxon pasporti', '🎓 Sertifikatlar']

const FAQ: [string, string][] = [
  [
    "Qanday to'lash eng oson?",
    "Bank kartasi orqali: tarifni tanlang, summani klub kartasiga Click, Payme yoki bank ilovasidan o'tkazing va chekni (skrinshot) yuboring. Admin tekshirgach Premium o'zi yoqiladi.",
  ],
  [
    'Telegram Stars (⭐) nima?',
    "Telegram'ning ichki to'lov birligi. Stars bilan to'lov bir zumda o'tadi. Stars'ingiz yo'q bo'lsa — «⭐ Telegram Stars» usulini tanlang va o'sha yerda ularni karta orqali sotib oling: bosh admin chekni tasdiqlaydi, mas'ul admin Stars'ni Telegram'da sizga sovg'a qiladi va bot xabar beradi (profilingizda username bo'lishi kerak).",
  ],
  ['Bepul sinov bormi?', "Ha — ro'yxatdan o'tganingizda 7 kunlik Premium o'zi yoqiladi. Pul yechilmaydi, muddat tugagach o'zi to'xtaydi."],
  ["Muddat tugasa nima bo'ladi?", "Premium o'z-o'zidan uzaytirilmaydi, pul yechilmaydi. Xohlasangiz yana sotib olasiz — muddat oxiridan davom etadi."],
  ["Asosiy imkoniyatlar pullikmi?", "Yo'q. Kitob, tadbir, davomat, test, reyting va sertifikatlar hamma uchun bepul. Premium — qo'shimcha imkoniyatlar va klubga yordam."],
  ['Muammo bo‘lsa?', "Botda /paysupport — to'lovlar bo'yicha bosh admin javob beradi. Xato to'lov bo'lsa pul qaytariladi."],
]

function perMonth(plan: PremiumPlan): number {
  return Math.round((plan.stars / plan.days) * 30)
}

/** «💎 Premium»: what it gives, then step by step — the plan, how to pay (the bank card first), paying.
 * Below: buying Stars with the card and a gentle «support the club». */
export function PremiumPage() {
  const { api, refreshMe, me } = useAuth()
  const goBack = useCallback(() => navigate('/profile'), [])
  useBackButton(goBack)
  const { state, reload } = useAsync((signal) => api<PremiumStatus>('/api/v1/me/premium', { signal }))
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)
  const [openFaq, setOpenFaq] = useState<number | null>(null)
  const [planId, setPlanId] = useState<string | null>(null)
  const [method, setMethod] = useState<'card' | 'stars' | null>(null)
  const [starsPack, setStarsPack] = useState<number | null>(null)
  const [version, setVersion] = useState(0)
  const [donated, setDonated] = useState(false)

  async function pay(key: string, body: { plan_id?: string; amount?: number }) {
    const webApp = getWebApp()
    setBusy(key)
    setNotice(null)
    try {
      const { url } = await api<{ url: string }>('/api/v1/me/premium/invoice', { method: 'POST', body })
      if (!webApp?.openInvoice) {
        webApp?.openTelegramLink(url)
        return
      }
      webApp.openInvoice(url, (status) => {
        if (status === 'paid') {
          haptic('success')
          setNotice({ text: body.plan_id ? '🎉 Rahmat! Premium faollashtirildi.' : '❤️ Katta rahmat! Hissangiz qabul qilindi.' })
          // Telegram confirms to the bot first; give it a moment, then refresh.
          window.setTimeout(() => {
            reload()
            void refreshMe()
          }, 1500)
        } else if (status === 'failed') {
          haptic('error')
          setNotice({ text: "To'lov amalga oshmadi. Qayta urinib ko'ring.", error: true })
        }
      })
    } catch (error) {
      haptic('error')
      setNotice({ text: error instanceof ApiError ? error.message : "To'lov oynasini ochib bo'lmadi.", error: true })
    } finally {
      setBusy(null)
    }
  }

  if (state.status === 'loading') return <LoadingState />
  if (state.status === 'error') return <ErrorState message={state.error.message} onRetry={reload} />
  const status = state.data
  const cheapest = status.plans.length ? Math.min(...status.plans.map(perMonth)) : null
  const cheapestUzs = status.card ? Math.min(...status.plans.map((plan) => plan.price_uzs_now ?? plan.price_uzs ?? Infinity)) : Infinity
  const selectedPlan = status.plans.find((plan) => plan.id === planId) ?? null
  const selectedPlanUzs = selectedPlan ? selectedPlan.price_uzs_now ?? selectedPlan.price_uzs : null
  const perks = [
    ...status.premium_features.map((feature) => ({ icon: feature.title.split(' ')[0], title: feature.title.split(' ').slice(1).join(' '), description: feature.description })),
    ...status.perks,
  ]

  return (
    <div className="flex flex-col gap-3">
      <Card className="flex flex-col items-center gap-2 border-0 bg-brand-gradient py-8 text-center text-white shadow-[var(--shadow-brand)] ring-1 ring-white/10">
        <span aria-hidden className="text-5xl">
          💎
        </span>
        <h1 className="font-serif text-2xl font-bold">Kitobxon Premium</h1>
        {status.lifetime ? (
          <p className="text-sm text-gold-200">♾ Sizda umrbod Premium — barcha imkoniyatlar doim ochiq</p>
        ) : status.is_premium ? (
          <p className="text-sm text-gold-200">✅ Siz Premium a'zosiz — {formatDate(status.until)} gacha</p>
        ) : (
          <p className="max-w-xs text-sm text-gold-200">
            Qo'shimcha imkoniyatlar, oltin pasport va klub rivojiga hissa
            {status.store_open && Number.isFinite(cheapestUzs) ? (
              <> — {formatUzs(cheapestUzs)} dan</>
            ) : (
              cheapest !== null && status.store_open && <> — oyiga {cheapest} ⭐ dan</>
            )}
          </p>
        )}
      </Card>

      {notice && (
        <p role={notice.error ? 'alert' : 'status'} className={`text-center text-sm ${notice.error ? 'text-app-danger' : 'text-app-link'}`}>
          {notice.text}
        </p>
      )}

      {me?.premium_trial && status.is_premium && (
        <Card className="py-3 text-center text-sm ring-1 ring-brand-500/40">
          🎁 Sizda sovg'a — <b>sinov Premium</b>, {formatDate(status.until)} gacha. 💎 belgili imkoniyatlar shu sinov tufayli ochiq;
          yoqqan bo'lsa, quyida davom ettiring.
        </Card>
      )}

      {status.discount && (
        <Card className="py-3 text-center text-sm">
          🎟 Sizda Premium'ga <b>−{status.discount.percent}%</b> chegirma bor — {formatDate(status.discount.valid_until)} gacha. Narxlar
          allaqachon kamaytirilgan.
        </Card>
      )}

      {!status.store_open && !status.donations_open && (
        <Card className="py-8 text-center text-sm text-app-hint">Premium obuna hozircha yopiq. Ochilganda albatta xabar beramiz!</Card>
      )}

      {status.store_open && (
        <>
          <SectionTitle>Premium bilan nima olasiz</SectionTitle>
          <div className="grid grid-cols-2 gap-2">
            {perks.map((perk) => (
              <Card key={perk.title} className="flex flex-col gap-1 py-3">
                <span aria-hidden className="text-2xl">
                  {perk.icon}
                </span>
                <span className="text-sm font-semibold leading-snug">{perk.title}</span>
                <span className="text-xs leading-snug text-app-hint">{perk.description}</span>
              </Card>
            ))}
          </div>

          <SectionTitle>1. {status.is_premium ? 'Muddatni uzaytirish — tarif' : 'Tarifni tanlang'}</SectionTitle>
          <div className="flex flex-col gap-2">
            {status.plans.map((plan, index) => {
              const badge = index === status.plans.length - 1 && status.plans.length > 1 ? '🔥 Eng foydali' : index === 1 ? '⭐ Ommabop' : null
              const uzs = plan.price_uzs_now ?? plan.price_uzs
              const selected = plan.id === planId
              return (
                <button
                  key={plan.id}
                  type="button"
                  onClick={() => {
                    setPlanId(plan.id)
                    setMethod(status.card && uzs ? 'card' : 'stars')
                  }}
                  className={`flex items-center justify-between gap-3 rounded-2xl bg-app-section p-4 text-left ${selected ? 'ring-2 ring-brand-500' : badge ? 'ring-1 ring-brand-500/40' : ''}`}
                >
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2 font-semibold">
                      {selected ? '🔘' : '⚪️'} {plan.title}
                      {badge && <span className="rounded-full bg-brand-500/10 px-2 py-0.5 text-[11px] text-brand-600 dark:text-brand-300">{badge}</span>}
                    </p>
                    <p className="text-sm text-app-hint">{plan.description ?? `${plan.days} kun`}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    {status.card && uzs ? (
                      <>
                        <p className="font-semibold tabular-nums">{formatUzs(uzs)}</p>
                        <p className="text-xs text-app-hint">yoki {plan.stars_now ?? plan.stars} ⭐</p>
                      </>
                    ) : (
                      <p className="font-semibold">{plan.stars_now ?? plan.stars} ⭐</p>
                    )}
                    {plan.stars_now != null && plan.stars_now !== plan.stars && <p className="text-xs text-app-hint line-through">{plan.stars} ⭐</p>}
                  </div>
                </button>
              )
            })}
          </div>

          {selectedPlan && (
            <>
              <SectionTitle>2. To'lov usuli</SectionTitle>
              <div className="flex flex-col gap-2">
                {status.card && selectedPlanUzs ? (
                  <button
                    type="button"
                    onClick={() => setMethod('card')}
                    className={`flex flex-col gap-1 rounded-2xl p-4 text-left ${method === 'card' ? 'bg-brand-500/10 ring-2 ring-brand-500' : 'bg-app-section'}`}
                  >
                    <span className="flex items-center justify-between gap-2 font-semibold">
                      💳 Bank kartasi (Uzcard, Humo)
                      <span className="rounded-full bg-gold-gradient px-2 py-0.5 text-[11px] font-semibold text-brand-700">Tavsiya etiladi</span>
                    </span>
                    <span className="text-sm text-app-hint">Click, Payme yoki bank ilovasidan o'tkazasiz — eng oson yo'l. {formatUzs(selectedPlanUzs)}</span>
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => setMethod('stars')}
                  className={`flex flex-col gap-1 rounded-2xl p-4 text-left ${method === 'stars' ? 'bg-brand-500/10 ring-2 ring-brand-500' : 'bg-app-section'}`}
                >
                  <span className="font-semibold">⭐ Telegram Stars</span>
                  <span className="text-sm text-app-hint">
                    Telegram ichida bir zumda — {selectedPlan.stars_now ?? selectedPlan.stars} ⭐.
                    {status.card && (status.stars_packages ?? []).length > 0
                      ? " Stars'ingiz yo'qmi? Shu yerning o'zida karta orqali sotib olasiz."
                      : " Stars'ingiz bo'lsa qulay."}
                  </span>
                </button>
              </div>

              <SectionTitle>3. To'lash</SectionTitle>
              <Card>
                {method === 'card' && status.card && selectedPlanUzs ? (
                  <CardCheckout
                    key={selectedPlan.id}
                    card={status.card}
                    price={selectedPlanUzs}
                    what={`Premium ${selectedPlan.title}`}
                    form={{ plan_id: selectedPlan.id }}
                    onDone={() => setVersion((value) => value + 1)}
                  />
                ) : (
                  <div className="flex flex-col gap-3">
                    <Button loading={busy === selectedPlan.id} disabled={busy !== null} onClick={() => void pay(selectedPlan.id, { plan_id: selectedPlan.id })}>
                      {selectedPlan.stars_now ?? selectedPlan.stars} ⭐ bilan to'lash
                    </Button>
                    {status.card && (status.stars_packages ?? []).length > 0 && (
                      <StarsTopUp
                        status={status}
                        hasUsername={Boolean(me?.telegram_username)}
                        need={selectedPlan.stars_now ?? selectedPlan.stars}
                        pack={starsPack}
                        onPack={setStarsPack}
                        onDone={() => setVersion((value) => value + 1)}
                      />
                    )}
                  </div>
                )}
              </Card>
            </>
          )}

          <MyCardPayments version={version} />

          <SectionTitle>Bepul va Premium</SectionTitle>
          <Card className="text-sm">
            <div className="grid grid-cols-[minmax(0,1fr)_3.5rem_3.5rem] gap-y-1.5">
              <span className="font-medium text-app-hint">Imkoniyat</span>
              <span className="text-center font-medium text-app-hint">Bepul</span>
              <span className="text-center font-medium text-app-hint">💎</span>
              {FREE_FOR_ALL.map((item) => (
                <Row key={item} label={item} free />
              ))}
              {perks.map((perk) => (
                <Row key={perk.title} label={`${perk.icon} ${perk.title}`} free={false} />
              ))}
            </div>
          </Card>
        </>
      )}

      {!status.store_open && status.card && (status.stars_packages ?? []).length > 0 && (
        <>
          <SectionTitle>⭐ Telegram Stars sotib olish (karta orqali)</SectionTitle>
          <Card>
            <StarsTopUp
              status={status}
              hasUsername={Boolean(me?.telegram_username)}
              need={null}
              pack={starsPack}
              onPack={setStarsPack}
              onDone={() => setVersion((value) => value + 1)}
            />
          </Card>
        </>
      )}

      {(status.donations_open || status.card) && (
        <>
          <SectionTitle>🤝 Klubni qo'llab-quvvatlash</SectionTitle>
          <Card className="flex flex-col gap-3">
            <p className="text-sm text-app-hint">
              Klub talabalar tashabbusi bilan yashaydi: yangi kitoblar, davra suhbatlari, g'oliblarga sovg'alar. Klub sizga yoqsa va imkoningiz
              bo'lsa, istalgan miqdorda hissa qo'shishingiz mumkin — bu mutlaqo ixtiyoriy. 💛
            </p>
            {status.card && (
              <>
                <CardNumber card={status.card} label="Istalgan summani shu kartaga o'tkazing — chek yuborish shart emas" />
                {donated ? (
                  <p role="status" className="rounded-xl bg-brand-500/10 px-3 py-2 text-sm">
                    💛 <b>Chin dildan rahmat!</b> Hissangiz yangi kitoblar, qiziqarli tadbirlar va g'oliblarning quvonchiga aylanadi.
                  </p>
                ) : (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      haptic('success')
                      setDonated(true)
                    }}
                  >
                    💛 O'tkazdim
                  </Button>
                )}
              </>
            )}
            {status.donations_open && <p className="text-xs text-app-hint">{status.card ? 'yoki ' : ''}Telegram Stars bilan:</p>}
            <div className="grid grid-cols-4 gap-2">
              {(status.donations_open ? status.donation_amounts : []).map((amount) => (
                <Button
                  key={amount}
                  variant="secondary"
                  className="whitespace-nowrap px-1 text-sm"
                  loading={busy === `d${amount}`}
                  disabled={busy !== null}
                  onClick={() => void pay(`d${amount}`, { amount })}
                >
                  {amount} ⭐
                </Button>
              ))}
            </div>
          </Card>
        </>
      )}

      {(status.store_open || status.donations_open) && (
        <>
          <SectionTitle>Savollar</SectionTitle>
          <Card className="divide-y divide-app-hint/10 py-1">
            {FAQ.map(([question, answer], index) => (
              <div key={question}>
                <button
                  type="button"
                  aria-expanded={openFaq === index}
                  onClick={() => setOpenFaq(openFaq === index ? null : index)}
                  className="flex w-full items-center justify-between gap-2 py-2.5 text-left text-[15px] font-medium"
                >
                  {question}
                  <span className="text-app-hint">{openFaq === index ? '−' : '+'}</span>
                </button>
                {openFaq === index && <p className="pb-3 text-sm text-app-hint">{answer}</p>}
              </div>
            ))}
          </Card>
        </>
      )}

      <p className="px-2 text-center text-xs text-app-hint">
        To'lov {status.card ? 'bank kartasi yoki ' : ''}Telegram Stars orqali. Asosiy imkoniyatlar hamma uchun bepul. Savol bo'lsa — botda /paysupport.
      </p>
    </div>
  )
}

/** «⭐ Stars'ingiz yo'qmi?»: Stars bought with the bank card. The super admin confirms the receipt, the admin in
 * charge gifts the Stars in Telegram, and the bot says when they arrive. ``need``: the plan's price in Stars
 * (the smallest package that covers it is suggested). */
function StarsTopUp({
  status,
  hasUsername,
  need,
  pack,
  onPack,
  onDone,
}: {
  status: PremiumStatus
  hasUsername: boolean
  need: number | null
  pack: number | null
  onPack: (stars: number) => void
  onDone: () => void
}) {
  const packages = status.stars_packages ?? []
  const suggested = need === null ? null : (packages.find((item) => item.stars >= need) ?? null)
  const selected = packages.find((item) => item.stars === pack) ?? null
  if (!status.card) return null
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-app-hint/20 p-3">
      <div>
        <p className="font-semibold">⭐ Stars'ingiz yo'qmi? Karta orqali sotib oling</p>
        <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-sm text-app-hint">
          <li>To'plamni tanlang va summani kartaga o'tkazing, chekni yuboring.</li>
          <li>Bosh admin chekni tekshirib tasdiqlaydi.</li>
          <li>Mas'ul admin Stars'ni Telegram'da sizga sovg'a qiladi — bot xabar beradi.</li>
          <li>{need !== null ? "So'ng shu yerda «⭐ bilan to'lash» ni bosasiz." : "Stars'ni xohlagan narsangizga ishlatasiz."}</li>
        </ol>
      </div>
      {!hasUsername ? (
        <p className="rounded-xl bg-app-surface px-3 py-2 text-sm">
          ⚠️ Stars sovg'a qilinishi uchun Telegram profilingizda <b>username</b> bo'lishi kerak: Telegram → Sozlamalar → «Foydalanuvchi
          nomi». Qo'ygach, ilovani qayta oching.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-1.5">
            {packages.map((item) => (
              <button
                key={item.stars}
                type="button"
                onClick={() => onPack(item.stars)}
                className={`relative flex flex-col rounded-xl px-3 py-2 text-left ${pack === item.stars ? 'bg-brand-500/10 ring-1 ring-brand-500' : 'bg-app-surface'}`}
              >
                <span className="font-medium">⭐ {item.stars} Stars</span>
                <span className="text-sm tabular-nums text-app-hint">{formatUzs(item.price_uzs)}</span>
                {suggested?.stars === item.stars && (
                  <span className="mt-0.5 text-[11px] font-medium text-app-button">✓ tarif uchun yetadi</span>
                )}
              </button>
            ))}
          </div>
          {need !== null && !suggested && (
            <p className="text-xs text-app-hint">Tarif {need} ⭐ — bir nechta to'plam olishingiz yoki karta orqali to'g'ridan-to'g'ri to'lashingiz mumkin.</p>
          )}
          {selected && (
            <CardCheckout
              key={selected.stars}
              card={status.card}
              price={selected.price_uzs}
              what={`${selected.stars} Stars`}
              form={{ stars: String(selected.stars) }}
              onDone={onDone}
            />
          )}
        </>
      )}
    </div>
  )
}

function Row({ label, free }: { label: string; free: boolean }) {
  return (
    <>
      <span className="truncate">{label}</span>
      <span className="text-center">{free ? '✅' : '—'}</span>
      <span className="text-center">✅</span>
    </>
  )
}
