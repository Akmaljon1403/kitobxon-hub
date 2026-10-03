import { useCallback, useState } from 'react'

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
  ['Telegram Stars (⭐) nima?', "Telegram'ning ichki to'lov birligi. Uni Telegram ilovasida karta orqali sotib olasiz — «Sozlamalar → Telegram Stars»."],
  ["Muddat tugasa nima bo'ladi?", "Premium o'z-o'zidan uzaytirilmaydi, pul yechilmaydi. Xohlasangiz yana sotib olasiz — muddat oxiridan davom etadi."],
  ["Asosiy imkoniyatlar pullikmi?", "Yo'q. Kitob, tadbir, davomat, test, reyting va sertifikatlar hamma uchun bepul. Premium — qo'shimcha imkoniyatlar va klubga yordam."],
  ['Muammo bo‘lsa?', "Botda /paysupport yoki «✉️ Adminga yozish». Xato to'lov bo'lsa Stars qaytariladi."],
]

function perMonth(plan: PremiumPlan): number {
  return Math.round((plan.stars / plan.days) * 30)
}

/** «💎 Premium»: what it gives, plans paid with Telegram Stars, and donations. */
export function PremiumPage() {
  const { api, refreshMe } = useAuth()
  const goBack = useCallback(() => navigate('/profile'), [])
  useBackButton(goBack)
  const { state, reload } = useAsync((signal) => api<PremiumStatus>('/api/v1/me/premium', { signal }))
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)
  const [openFaq, setOpenFaq] = useState<number | null>(null)

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
  const perks = [
    ...status.premium_features.map((feature) => ({ icon: feature.title.split(' ')[0], title: feature.title.split(' ').slice(1).join(' '), description: feature.description })),
    ...status.perks,
  ]

  return (
    <div className="flex flex-col gap-3">
      <Card className="flex flex-col items-center gap-2 bg-gradient-to-br from-emerald-950 via-emerald-800 to-emerald-600 py-8 text-center text-white">
        <span aria-hidden className="text-5xl">
          💎
        </span>
        <h1 className="text-xl font-semibold">Kitobxon Premium</h1>
        {status.is_premium ? (
          <p className="text-sm text-emerald-100">✅ Siz Premium a'zosiz — {formatDate(status.until)} gacha</p>
        ) : (
          <p className="max-w-xs text-sm text-emerald-100">
            Qo'shimcha imkoniyatlar, oltin pasport va klub rivojiga hissa
            {cheapest !== null && status.store_open && <> — oyiga {cheapest} ⭐ dan</>}
          </p>
        )}
      </Card>

      {notice && (
        <p role={notice.error ? 'alert' : 'status'} className={`text-center text-sm ${notice.error ? 'text-app-danger' : 'text-app-link'}`}>
          {notice.text}
        </p>
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

          <SectionTitle>{status.is_premium ? 'Muddatni uzaytirish' : 'Tarifni tanlang'}</SectionTitle>
          <div className="flex flex-col gap-2">
            {status.plans.map((plan, index) => {
              const badge = index === status.plans.length - 1 && status.plans.length > 1 ? '🔥 Eng foydali' : index === 1 ? '⭐ Ommabop' : null
              return (
                <Card key={plan.id} className={`flex items-center justify-between gap-3 ${badge ? 'ring-1 ring-app-button/40' : ''}`}>
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2 font-semibold">
                      {plan.title}
                      {badge && <span className="rounded-full bg-app-button/10 px-2 py-0.5 text-[11px] text-app-button">{badge}</span>}
                    </p>
                    <p className="text-sm text-app-hint">{plan.description ?? `${plan.days} kun`}</p>
                    {plan.days > 31 && <p className="text-xs text-app-hint">≈ {perMonth(plan)} ⭐ / oy</p>}
                  </div>
                  <div className="w-28 shrink-0">
                    <Button
                      className="whitespace-nowrap px-2"
                      loading={busy === plan.id}
                      disabled={busy !== null}
                      onClick={() => void pay(plan.id, { plan_id: plan.id })}
                    >
                      {plan.stars} ⭐
                    </Button>
                  </div>
                </Card>
              )
            })}
          </div>

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

      {status.donations_open && (
        <>
          <SectionTitle>❤️ Klubni qo'llab-quvvatlash</SectionTitle>
          <Card className="flex flex-col gap-3">
            <p className="text-sm text-app-hint">Har qanday hissa kitoblar, tadbirlar va g'oliblarga sovg'alar uchun ishlatiladi.</p>
            <div className="grid grid-cols-4 gap-2">
              {status.donation_amounts.map((amount) => (
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
        To'lov Telegram Stars orqali. Asosiy imkoniyatlar hamma uchun bepul. Savol bo'lsa — botda /paysupport.
      </p>
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
