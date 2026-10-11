import { useState } from 'react'

import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useSession } from '../store/session'
import { Badge, Button, Card, InlineError } from './ui'

interface ChannelStatus {
  chat_id: string | null
  title: string | null
  ok: boolean
  problem: string | null
  sent?: boolean
}

/** «💳 To'lovlar kanali»: all receipts, payment questions and Stars payments go to one channel. */
export function PaymentsChannel() {
  const { api } = useSession()
  const status = useAsync((signal) => api<ChannelStatus>('/api/v1/admin/premium/payments-chat', { signal }))
  const summary = useAsync((signal) => api<{ text: string }>('/api/v1/admin/premium/money-summary?days=30', { signal }))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  async function test() {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const result = await api<ChannelStatus>('/api/v1/admin/premium/payments-chat/test', { method: 'POST' })
      setNotice(result.sent ? '✓ Kanalga sinov xabari yuborildi.' : null)
      if (!result.sent) setError(result.problem ?? "Kanalga yozib bo'lmadi.")
      status.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Yuborib bo'lmadi.")
    } finally {
      setBusy(false)
    }
  }

  const data = status.state.status === 'success' ? status.state.data : null
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-semibold">💳 To'lovlar kanali</h2>
        {data?.chat_id && data.ok && <Badge tone="success">ulangan: {data.title}</Badge>}
        {data?.chat_id && !data.ok && <Badge tone="warning">muammo bor</Badge>}
        {data && !data.chat_id && <Badge>sozlanmagan</Badge>}
      </div>
      <p className="text-sm text-app-hint">
        Cheklar (✅/❌ tugmalari bilan), to'lov bo'yicha savollar, Telegram Stars to'lovlari va har dushanba moliyaviy xulosa
        shu kanalga keladi — shaxsiy chatingiz toza qoladi. Ulash juda oson: <b>Telegram'da yopiq kanal oching → botni
        kanalga administrator qiling</b> → bot sizga botda «Bu kanal nima uchun?» deb so'raydi → «💳 To'lovlar kanali».
      </p>
      {data?.problem && <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{data.problem}</p>}
      <InlineError message={error} />
      {notice && <p className="text-sm text-emerald-700">{notice}</p>}
      {data?.chat_id && (
        <div>
          <Button variant="secondary" loading={busy} onClick={() => void test()}>
            🧪 Kanalga sinov xabari
          </Button>
        </div>
      )}
      {summary.state.status === 'success' && (
        <details className="rounded-lg bg-app-surface p-3 text-sm">
          <summary className="cursor-pointer font-medium">📊 So'nggi 30 kun: moliyaviy xulosa</summary>
          <p
            className="mt-2 whitespace-pre-line"
            dangerouslySetInnerHTML={{ __html: summary.state.data.text.replace(/<(?!\/?b>)[^>]*>/g, '') }}
          />
        </details>
      )}
    </Card>
  )
}
