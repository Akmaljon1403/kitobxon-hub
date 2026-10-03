import { useCallback, useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Button, Card, SectionTitle } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useBackButton } from '../hooks/useBackButton'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { PremiumStatus } from '../types/api'
import { formatDate } from '../utils/format'
import { navigate } from '../utils/router'
import { getWebApp, haptic } from '../utils/telegram'

/** «💎 Premium»: plans and donations paid with Telegram Stars, right inside the Mini App. */
export function PremiumPage() {
  const { api, refreshMe } = useAuth()
  const goBack = useCallback(() => navigate('/profile'), [])
  useBackButton(goBack)
  const { state, reload } = useAsync((signal) => api<PremiumStatus>('/api/v1/me/premium', { signal }))
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)

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

  return (
    <div className="flex flex-col gap-3">
      <Card className="flex flex-col items-center gap-2 bg-gradient-to-br from-emerald-900 to-emerald-700 py-8 text-center text-white">
        <span aria-hidden className="text-5xl">
          💎
        </span>
        <h1 className="text-xl font-semibold">Kitobxon Premium</h1>
        {status.is_premium ? (
          <p className="text-sm text-emerald-100">✅ Siz Premium a'zosiz — {formatDate(status.until)} gacha</p>
        ) : (
          <p className="text-sm text-emerald-100">Qo'shimcha imkoniyatlar va klub rivojiga hissa</p>
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
          <SectionTitle>Premium bilan</SectionTitle>
          <Card className="flex flex-col gap-2 text-[15px]">
            {status.premium_features.map((feature) => (
              <p key={feature.code}>
                {feature.title} — <span className="text-app-hint">{feature.description}</span>
              </p>
            ))}
            <p>
              🌟 Oltin Kitobxon pasporti — <span className="text-app-hint">«Premium a'zo» belgisi bilan</span>
            </p>
          </Card>
          <SectionTitle>{status.is_premium ? 'Muddatni uzaytirish' : 'Tarifni tanlang'}</SectionTitle>
          <div className="flex flex-col gap-2">
            {status.plans.map((plan) => (
              <Card key={plan.id} className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold">{plan.title}</p>
                  <p className="text-sm text-app-hint">{plan.description ?? `${plan.days} kun`}</p>
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
            ))}
          </div>
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

      <p className="px-2 text-center text-xs text-app-hint">
        To'lov Telegram Stars orqali. Asosiy imkoniyatlar hamma uchun bepul. Savol bo'lsa — botda /paysupport.
      </p>
    </div>
  )
}
