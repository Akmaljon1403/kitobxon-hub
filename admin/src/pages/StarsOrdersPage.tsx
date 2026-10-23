import { useState } from 'react'

import { ErrorState, LoadingState } from '../components/StateViews'
import { Badge, Button, Card, InlineError, PageHeader } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import { formatDateTime } from '../utils/format'

interface StarsOrder {
  id: string
  stars: number
  amount_uzs: number
  member_name: string
  member_username: string | null
  member_telegram_id: number
  approved_at: string | null
  approved_by: string | null
  delivered_at: string | null
  delivered_by: string | null
}

interface StarsOrders {
  items: StarsOrder[]
  waiting: number
  senders: string
}

const uzs = (value: number) => `${value.toLocaleString('ru-RU').replace(/,/g, ' ')} so'm`

/** «⭐ Stars buyurtmalari»: Stars bought with a bank card. The super admin confirmed the receipt; the admin
 * given «⭐ Stars yuborish» gifts them in Telegram (Fragment) and presses «✅ Yuborildi» — the member is told. */
export function StarsOrdersPage() {
  const { api } = useSession()
  const [tab, setTab] = useState<'waiting' | 'sent'>('waiting')
  const { state, reload } = useAsync((signal) => api<StarsOrders>(`/api/v1/admin/stars-orders?state=${tab}`, { signal }), [tab])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  async function delivered(order: StarsOrder) {
    if (!window.confirm(`${order.member_name} ga ⭐ ${order.stars} Stars yuborildimi? A'zoga xabar boradi.`)) return
    setBusy(order.id)
    setError(null)
    try {
      await api(`/api/v1/admin/stars-orders/${order.id}/delivered`, { method: 'POST' })
      reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Xatolik yuz berdi.')
    } finally {
      setBusy(null)
    }
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(text)
      window.setTimeout(() => setCopied(null), 1500)
    } catch {
      setCopied(null)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="⭐ Stars buyurtmalari"
        subtitle="A'zolar karta orqali sotib olgan Telegram Stars. Bosh admin chekni tasdiqlagach, buyurtma shu yerga va mas'ul adminga botda keladi."
      />
      <Card className="flex flex-col gap-2 p-4 text-sm">
        <p className="rounded-lg bg-amber-50 p-2.5 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          ⚠️ Muhim: bot Telegram Stars'ni o'zi avtomatik sotib ololmaydi va a'zoga yubora olmaydi — Telegram bunga API (imkoniyat)
          bermaydi. Shuning uchun bu har doim qo'lda bajariladi (atigi bir necha daqiqa). Tizim esa hammasini kuzatib boradi: kim
          to'ladi, kim tasdiqladi, kim yubordi.
        </p>
        <p className="font-semibold">Qanday yuboriladi</p>
        <ol className="list-decimal space-y-1 pl-5 text-app-hint">
          <li>
            <a className="text-app-link underline" href="https://fragment.com/stars/buy" target="_blank" rel="noreferrer">
              fragment.com/stars/buy
            </a>{' '}
            sahifasini oching (Telegram yoki TON hamyon bilan kiring).
          </li>
          <li>«Recipient» maydoniga a'zoning @username'ini yozing, miqdorni kiriting va to'lang.</li>
          <li>Stars bir necha daqiqada a'zoga tushadi — so'ng shu yerda «✅ Yuborildi» ni bosing.</li>
        </ol>
        {state.status === 'success' && (
          <p className="text-xs text-app-hint">Yangi buyurtmalar botda shularga keladi: {state.data.senders}</p>
        )}
      </Card>

      <div className="flex gap-2">
        <Button variant={tab === 'waiting' ? 'primary' : 'secondary'} onClick={() => setTab('waiting')}>
          ⏳ Yuborilishi kerak{state.status === 'success' ? ` (${state.data.waiting})` : ''}
        </Button>
        <Button variant={tab === 'sent' ? 'primary' : 'secondary'} onClick={() => setTab('sent')}>
          ✅ Yuborilganlar
        </Button>
      </div>
      <InlineError message={error} />

      {state.status === 'loading' && <LoadingState />}
      {state.status === 'error' && <ErrorState message={state.error.message} onRetry={reload} />}
      {state.status === 'success' && state.data.items.length === 0 && (
        <Card className="p-6 text-center text-sm text-app-hint">
          {tab === 'waiting' ? "Hozircha yuboriladigan Stars yo'q 🎉" : "Hali Stars yuborilmagan."}
        </Card>
      )}
      {state.status === 'success' &&
        state.data.items.map((order) => (
          <Card key={order.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="min-w-0">
              <p className="font-semibold">
                ⭐ {order.stars} Stars → {order.member_name}
              </p>
              <p className="text-sm text-app-hint">
                {order.member_username ? (
                  <>
                    <button type="button" className="text-app-link underline" onClick={() => void copy(`@${order.member_username}`)}>
                      @{order.member_username}
                    </button>
                    {copied === `@${order.member_username}` && ' ✓ nusxalandi'}
                    {' · '}
                    <a className="text-app-link underline" href={`https://t.me/${order.member_username}`} target="_blank" rel="noreferrer">
                      💬 Yozish
                    </a>
                  </>
                ) : (
                  <span className="text-app-danger">⚠️ @username yo‘q — Fragment faqat @username’ga yuboradi; a'zodan Telegram’da username qo‘yishni so‘rang</span>
                )}
                {' · '}to'langan {uzs(order.amount_uzs)}
              </p>
              <p className="text-xs text-app-hint">
                Tasdiqladi: {order.approved_by ?? '—'}, {formatDateTime(order.approved_at)}
                {order.delivered_at && ` · Yubordi: ${order.delivered_by ?? '—'}, ${formatDateTime(order.delivered_at)}`}
              </p>
            </div>
            {order.delivered_at ? (
              <Badge tone="success">Yuborildi</Badge>
            ) : (
              <Button loading={busy === order.id} disabled={busy !== null} onClick={() => void delivered(order)}>
                ✅ Yuborildi
              </Button>
            )}
          </Card>
        ))}
    </div>
  )
}
