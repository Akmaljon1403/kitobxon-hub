import { useRef, useState } from 'react'

import { useAsync } from '../hooks/useAsync'
import { ApiError } from '../services/api'
import { useAuth } from '../store/auth'
import type { CardPayment, PremiumPlan } from '../types/api'
import { formatDate } from '../utils/format'
import { haptic } from '../utils/telegram'
import { Button, Card } from './ui'

export function formatUzs(amount: number): string {
  return `${amount.toLocaleString('ru-RU').replace(/,/g, ' ')} so'm`
}

const STATUS: Record<CardPayment['status'], string> = {
  PENDING: '⏳ Tekshirilmoqda',
  APPROVED: '✅ Tasdiqlandi',
  REJECTED: '❌ Rad etildi',
}

/** Pay to the club's card and send the receipt; the super admin confirms and Premium switches on. */
export function CardPaymentSection({ card, plans, onDone }: { card: { number: string; holder: string }; plans: PremiumPlan[]; onDone: () => void }) {
  const { api, upload } = useAuth()
  const cardPlans = plans.filter((plan) => plan.price_uzs)
  const [choice, setChoice] = useState<string>(cardPlans[0]?.id ?? 'donation')
  const [amount, setAmount] = useState('20000')
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)
  const [notice, setNotice] = useState<{ text: string; error?: boolean } | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const history = useAsync((signal) => api<CardPayment[]>('/api/v1/me/premium/card-payments', { signal }))

  const plan = cardPlans.find((item) => item.id === choice)
  const price = plan ? plan.price_uzs ?? 0 : Number(amount.replace(/\D/g, '')) || 0

  async function send(file: File) {
    setBusy(true)
    setNotice(null)
    try {
      const form = new FormData()
      form.append('file', file)
      if (plan) form.append('plan_id', plan.id)
      else form.append('amount_uzs', String(price))
      await upload('/api/v1/me/premium/card-payments', form, 'POST')
      haptic('success')
      setNotice({ text: "✅ Chek qabul qilindi! Admin tekshirgach, Premium avtomatik yoqiladi va sizga xabar keladi." })
      history.reload()
      onDone()
    } catch (error) {
      haptic('error')
      setNotice({ text: error instanceof ApiError ? error.message : "Chekni yuborib bo'lmadi.", error: true })
    } finally {
      setBusy(false)
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(card.number.replace(/\s/g, ''))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard is not available in every webview; the number is still visible
    }
  }

  return (
    <Card className="flex flex-col gap-3">
      <p className="text-sm text-app-hint">Telegram Stars bo'lmasa — klub kartasiga to'lab, chekni yuboring. Admin tasdiqlagach Premium o'zi yoqiladi.</p>

      <div className="flex flex-col gap-1.5">
        {cardPlans.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setChoice(item.id)}
            className={`flex items-center justify-between rounded-xl px-3 py-2.5 text-left ${choice === item.id ? 'bg-app-button/10 ring-1 ring-app-button' : 'bg-app-surface'}`}
          >
            <span className="font-medium">💎 Premium {item.title}</span>
            <span className="tabular-nums">{formatUzs(item.price_uzs ?? 0)}</span>
          </button>
        ))}
        <button
          type="button"
          onClick={() => setChoice('donation')}
          className={`flex items-center justify-between rounded-xl px-3 py-2.5 text-left ${choice === 'donation' ? 'bg-app-button/10 ring-1 ring-app-button' : 'bg-app-surface'}`}
        >
          <span className="font-medium">❤️ Hissa</span>
          <span className="text-app-hint">istalgan summa</span>
        </button>
        {choice === 'donation' && (
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/\D/g, '').slice(0, 9))}
            inputMode="numeric"
            aria-label="Hissa summasi (so'm)"
            className="w-full rounded-xl bg-app-surface px-3 py-2.5 text-[15px] outline-none"
          />
        )}
      </div>

      <div className="flex flex-col gap-1 rounded-xl bg-app-surface p-3">
        <span className="text-xs text-app-hint">1) {formatUzs(price)} ni shu kartaga o'tkazing</span>
        <button type="button" onClick={() => void copy()} className="flex items-center justify-between gap-2 text-left">
          <span className="font-mono text-lg tracking-wider">{card.number}</span>
          <span className="text-sm text-app-link">{copied ? '✓ Nusxalandi' : '📋 Nusxa'}</span>
        </button>
        {card.holder && <span className="text-sm text-app-hint">Egasi: {card.holder}</span>}
      </div>

      <Button loading={busy} disabled={busy || price < 1000} onClick={() => fileInput.current?.click()}>
        🧾 2) Chekni (skrinshot) yuborish
      </Button>
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        className="hidden"
        aria-label="To'lov cheki"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) void send(file)
          e.target.value = ''
        }}
      />
      {notice && (
        <p role={notice.error ? 'alert' : 'status'} className={`text-center text-sm ${notice.error ? 'text-app-danger' : 'text-app-link'}`}>
          {notice.text}
        </p>
      )}

      {history.state.status === 'success' && history.state.data.length > 0 && (
        <div className="flex flex-col gap-1 border-t border-app-hint/15 pt-2 text-sm">
          <span className="text-xs font-medium text-app-hint">Mening to'lovlarim</span>
          {history.state.data.map((item) => (
            <div key={item.id} className="flex flex-col">
              <span className="flex justify-between gap-2">
                <span>
                  {item.plan_title ? `💎 ${item.plan_title}` : '❤️ Hissa'} · {formatUzs(item.amount_uzs)}
                </span>
                <span className="shrink-0">{STATUS[item.status]}</span>
              </span>
              <span className="text-xs text-app-hint">
                {formatDate(item.created_at)}
                {item.reject_reason && ` · ${item.reject_reason}`}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
